# Spotlight for Samba

**DISCLAIMER: Use of anything provided here is at you own risk!**

The Spotlight setup in Samba itself is documented on the Samba [wiki](https://wiki.samba.org/index.php/Spotlight_with_Elasticsearch_Backend)

```text
  _____________   Spotlight     __________   Files,   ______________   Scan files    _____________ 
 |             |  query        |          |  ACLs    | Filesystem   |  + meta data  |             |
 |  Apple Mac  | ------------> |          | -------> |  File        | <------------ |  FScrawler  |   
 |             |  Filesharing  |  Samba   |          |   +          |               |             |
  -------------                |  file    |       +- |  ACL         |                -------------
                               |  server  |       |   --------------                     | 
                               |          |       |                                      | Create     
                               |          | <-----+ Spotlight ACL info                   | documents
                               |          |                                              V    
                               |          |                 ______________          ______________ 
                               |          | -------------> |  Anonymous   |        |              | 
                                ----------  Spotlight      |  Opensearch  | -----> |  Opensearch  |
                      User authnz |         query          |  proxy       |   +--- |  (Elastic7)  | 
                                  V                         --------------    |     -------------- 
                                _______________                               |    |              |
                               |               | <----------------------------+    |  Opensearch  |
                               |  Samba AD-DC  |   user authnz                     |  Dashboard   |
                               |               |                       User -----> |  (Kibana)    |
                                ---------------                        WebUI        --------------
```

Components to be installed are: FScrawler, anonymous Opensearch proxy, opensearch and opensearch-dashboards. 
Samba fileserver needs configuration updates for Spotlight. 
The fileshares to be indexed need ACL updates for FScrawler indexing.

FScrawler, anonymous Opensearch proxy will be setup on machine that hosts the Samba fileserver. 
Opensearch and opensearch-dashboards go on another machine.

The source of FScrawler must be patched and compiled, all necessary steps are below. 

All together this is quite complex and hence not recommended without enough knowledge and skills :-) 


## Setup

Setup instructions are written for a Debian Bullseye server.

Design decisions:
- Security is part of the design and of the setup
- Opensearch and Opensearch-dashboards are broader usable (not exclusively for the fileserver), therefore it should be installed on another machine
- Opensearch is configured as a single node cluster
- Daemons (e.g. FScrawler) should not run as `root` if possible
- Filesystem permissions provide more fine-grained control on what can be accessed and indexed by FScrawler
- Webapplications should run behind a reverse-proxy, for extra control on access
- User access is based on RBAC and AD
- The setup uses default settings with regards to performance and scalability 

Assumptions:
- A working Samba fileserver 
- Another machine or container is available for setup of Opensearch
- Apache2 is setup on the same server as Opensearch and has a TLS enabled vhost ready to use. 
- A host X509 (server-) certificate and a key file for the Opensearch server
- A X509 (client-) certificate and a key file for the Opensearch admin-user

In case you want to use containers the to most logical choice is lxc-containers and for the fileserver that must be a privileged container.

Samba current does not have support for authentication to Opensearch (which is required). 
An opensearch-proxy is setup which adds authentication over an encrypted connection. Since it listens to localhost only, this is secure enough.

### Setup steps on Opensearch machine (or container)

On the Opensearch machine:
- Install Opensearch and configure users and roles
- Install Opensearch-dashboards

The Opensearch setup described creates a single-node cluster.

#### Opensearch

- Create a service-account in Samba

```bash
# On one of the DCs:
samba-tool user create <SERVICE-ACCOUNT NAME>
# Ensure this account does not expire

# Get the DN and put it in slapd.conf
samba-tool user show <SERVICE-ACCOUNT NAME>
```

- Create a permission-group in Samba for user unrestricted access to Opensearch-dashboards (and add users to the (nested-)group) 

```bash
# On one of the DCs:
samba-tool user group <PERMISSION-GROUP NAME>
```

- Install Opensearch:

```bash
apt-get install curl openjdk-11-jre-headless apache2
update-ca-certificates --fresh
useradd -d /nonexistent -M -r -s /usr/sbin/nologin -U opensearch

cat << EOF > /etc/apt/sources.list.d/opensearch.list
deb [arch=amd64 signed-by=/usr/share/keyrings/opensearch.gpg] https://artifacts.opensearch.org/releases/bundle/opensearch/2.x/apt stable main
EOF
curl -s https://artifacts.opensearch.org/publickeys/opensearch.pgp > /usr/share/keyrings/opensearch.gpg
apt-get update
apt-get install opensearch
rm /etc/init.d/opensearch
# Fix default variables file
rm /etc/default/opensearch
ln -s /etc/sysconfig/opensearch /etc/default/opensearch
sed -i 's/^OPENSEARCH_JAVA_HOME=/OPENSEARCH_JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64/' /etc/default/opensearch

# Move sample config out of the way
mv /etc/opensearch /etc/opensearch-example
mkdir /etc/opensearch
for DIR in jvm.options.d opensearch-notifications opensearch-notifications-core opensearch-observability opensearch-performance-analyzer opensearch-reports-scheduler opensearch-security private; do
    mkdir /etc/opensearch/${DIR}
done

# Certificates
chmod 0700 /etc/opensearch/private /etc/opensearch/opensearch-security
cp /etc/ssl/certs/ca-certificates.crt /etc/opensearch/private
cp /etc/ssl/certs/java/cacerts /etc/opensearch/private
```

- Copy the host X509 (server-) certificate and a key file to `/etc/opensearch/private` and name them `host.crt`, `host.key`  
- Copy the admin-user X509 (client-) certificate and a key file `/etc/opensearch/private` and name them `super_admin.crt`, `super_admin.key`

```bash
openssl pkcs8 -inform PEM -outform PEM -in /etc/opensearch/private/super_admin.key -topk8 -nocrypt -v1 PBE-SHA1-3DES -out /etc/opensearch/private/super_admin.pkcs8.key
chmod 0600 /etc/opensearch/private/*

SUPER_ADMIN_CN="$(openssl x509 -in /etc/opensearch/private/super_admin.crt -noout -subject | sed -e 's/subject=//g' -e 's/ = /=/g' -e 's/, /,/g')"
echo "${SUPER_ADMIN_DN}"
```

- Copy `opensearch/config/opensearch.yml` to `/etc/opensearch/opensearch.yml`
- Edit: `/etc/opensearch/opensearch.yml`:
  - Replace `<CLUSTERNAME>` with a cluster-name (e.g. the dns subdomain)
  - Replace `<HOSTNAME>`with the hostname
  - Replace `<SUPER_ADMIN_DN>` with the above printed SUPER_ADMIN_DN

- Copy `opensearch/config/jvm.options` to `/etc/opensearch/jvm.options`
- In `jvm.options`, the memory options are limited: `-Xms=512m` and `-Xmx=768m`, edit to change 

- Copy `opensearch/config/log4j2.properties` to `/etc/opensearch/log4j2.properties`
- Copy `opensearch/config/opensearch-notifications/notifications.yml` to `/etc/opensearch/opensearch-notifications/notifications.yml`
- Copy `opensearch/config/opensearch-notifications-core/notifications-core.yml` to `/etc/opensearch/opensearch-notifications-core/notifications-core.yml`
- Copy `opensearch/config/opensearch-observability/observability.yml` to `/etc/opensearch/opensearch-observability/observability.yml`
- Copy `opensearch/config/opensearch-reports-scheduler/reports-scheduler.yml` to `/etc/opensearch/opensearch-reports-scheduler/reports-scheduler.yml`
- Copy `opensearch/config/limits.conf` to `/etc/security/limits.d/opensearch.conf`


- Copy `opensearch/roles_static/*` to `/etc/opensearch/opensearch-security/`


- Copy `opensearch/roles_custom/config.yml` to `/etc/opensearch/opensearch-security/config.yml`
- Edit `/etc/opensearch/opensearch-security/config.yml`:
  - Replace `<YOUR 1ST DC-SERVER>` and `/<YOUR 2ND DC-SERVER>` with the DC hostnames (in 2 places in the file)
  - Replace `<SERVICE-ACCOUNT DN>` with the DN of the SERVICE-ACCOUNT (in 2 places in the file)
  - Replace `<SERVICE-ACCOUNT PASSWORD>` with the password of the SERVICE-ACCOUNT (in 2 places in the file)
  - Replace `<BASE-DN OF YOUR USER-ACCOUNTS>`with the base-DN of your user-accounts (in 2 places in the file)
  - Replace `<BASE-DN OF YOUR PERMISSION-GROUPS>`with the base-DN of your permission groups

- Generate passwords and hashes for Opensearch service-users:

```
# OPENSEARCH-ADMIN-PW
makepasswd --chars=32
/usr/share/opensearch/plugins/opensearch-security/tools/hash.sh

# OPENSEARCH-KIBANA-PW
makepasswd --chars=32
/usr/share/opensearch/plugins/opensearch-security/tools/hash.sh

# OPENSEARCH-LOCAL-FSCRAWLER-PW
makepasswd --chars=32
/usr/share/opensearch/plugins/opensearch-security/tools/hash.sh

# OPENSEARCH-LOCAL-SAMBA-PW
makepasswd --chars=32
/usr/share/opensearch/plugins/opensearch-security/tools/hash.sh
```

- The passwords of required in later steps, the hashes are used here
- Copy `opensearch/roles_custom/internal_users.yml` to `/etc/opensearch/opensearch-security/internal_users.yml`
- Edit `/etc/opensearch/opensearch-security/internal_users.yml`:
  - Replace `<OPENSEARCH-*-PW-HASH>` with the above created password hashes

- Copy `opensearch/roles_custom/roles_mapping.yml` to `/etc/opensearch/opensearch-security/roles_mapping.yml`
- Edit `/etc/opensearch/opensearch-security/roles_mapping.yml`:
  - Replace `<PERMISSION-GROUP NAME>` with the permission-group create on Samba DC

- Update the internal user and roles database:

```bash
CLUSTER_NAME="<CLUSTERNAME>"

# Fix owners and permissions
chown -R opensearch.opensearch /etc/opensearch 
chmod 0600 /etc/opensearch/opensearch-security/*

OPENSEARCH_JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64 /usr/share/opensearch/plugins/opensearch-security/tools/securityadmin.sh \
   --disable-host-name-verification \
   --clustername ${CLUSTER_NAME} \
   --configdir /etc/opensearch/opensearch-security \
   -cacert /etc/ssl/certs/ca.pem \
   -cert /etc/opensearch/private/super_admin.crt \
   -key /etc/opensearch/private/super_admin.pkcs8.key
```

- Disable performance-manager (opensearch fails on it):

```bash
/usr/share/opensearch/bin/opensearch-plugin remove opensearch-performance-analyzer
```
- Enable and start Opensearch:
```bash
systemctl enable opensearch
systemctl start opensearch

# Wait until it is started, starting Java can take minutes
# Check if it works:
curl -s --insecure --user "admin:<OPENSEARCH-ADMIN-PW>" https://localhost:9200/_cluster/health?pretty 
curl -s --insecure --user "admin:<OPENSEARCH-ADMIN-PW>" https://localhost:9200/_cat/nodes?v
```

#### Opensearch-dashboards

Opensearch-dashboards will be configured to be available at `https://<OPENSEARCH-FQDN>/kibana`

- Install Opensearch-dashboards:

```bash
apt-get install curl
cat << EOF > /etc/apt/sources.list.d/opensearch_dashboards.list
deb [arch=amd64 signed-by=/usr/share/keyrings/opensearch.gpg] https://artifacts.opensearch.org/releases/bundle/opensearch-dashboards/2.x/apt stable main
EOF
apt-get update
apt-get install opensearch-dashboards

rm /etc/init.d/opensearch-dashboards
```

- Copy `opensearch_dashboards/opensearch_dashboards.yml` to `/etc/opensearch_dashboards/opensearch_dashboards.ym`
- Edit: `/etc/opensearch_dashboards/opensearch_dashboards.yml`:
  - Replace `<HOSTNAME>`with the hostname
  - Replace `<OPENSEARCH-FQDN>` with the server-fqdn of the opensearch server
  - Replace `<OPENSEARCH-KIBANA-PW>` with the password of the kibana-user 

- Setup reverse-proxy on apache:

```bash
cat << EOF >> /etc/apache2/conf-available/opensearch_dashboards.conf
<Location /kibana>
    Require all granted
    
    ProxyPass http://127.0.0.1:5601/kibana
    ProxyPassReverse http://127.0.0.1:5601/kibana
</Location>
EOF

a2enmod http_proxy
```

- Edit `/etc/apache2/sites-enabled/default-ssl.conf` (or whatever is your TLS enabled vhost conf):
  - Insert a line `Include /etc/apache2/conf-available/opensearch_dashboards.conf` in the vhost
  - Restart apache `systemctl restart apache2`

When you browse to `https//<OPENSEARCH-FQDN>/kibana`, you should be able to login with any user defined in the 
permission-group you have put in Opensearch in `/etc/opensearch/opensearch-security/roles_mapping.yml`.
And you should see the `samba_smb` index, which is still empty.



### Setup steps on Samba fileserver machine (or container)

On the Samba fileserver machine:
- FScrawler: compile and install as a service
- Compile patched Debian Samba 4.17.10 packages
- Add Spotlight to the Samba fileserver configuration
- Update filesystem permissions on shares for FScrawler
- Opensearch-proxy to connect Samba with Opensearch

#### FScrawler

- Add indices to Opensearch and Opensearch-dashboards (Kibana):

```bash
OPENSEARCH_FQDN="<OPENSEARCH-FQDN>"
OPENSEARCH_ADMIN_PASSWORD="<OPENSEARCH-ADMIN-PW>"

# Add indices to Opensearch-dashboards
curl -s --request POST \
    --user "admin:${OPENSEARCH_ADMIN_PASSWORD}" \
    --header "Content-Type: application/json" \
    --data "{\"attributes\": {\"title\": \"samba_smb\", \"timeFieldName\": \"file.last_modified\"}}" \ 
    "https://${OPENSEARCH_FQDN}/kibana/api/saved_objects/index-pattern/samba_smb" 

curl -s --request POST \
    --user "admin:${OPENSEARCH_ADMIN_PASSWORD}" \
    --header "Content-Type: application/json" \
    --data "{\"attributes\": {\"title\": \"samba_smb_folder\"}}" \ 
    "https://${OPENSEARCH_FQDNL}/kibana/api/saved_objects/index-pattern/samba_smb_folder" 

# Add an index-template in Opensearch
curl -s --request POST \
    --user "admin:${OPENSEARCH_ADMIN_PASSWORD}" \
    --header "Content-Type: application/json" \
    --data "{\"index_patterns\": [\"samba_smb\"], \"template\": {\"settings\": {\"index.number_of_shards\": \"1\", \"index.number_of_replicas\": \"0\", \"index.refresh_interval\": \"1s\"}, \"mappings\": {}}}" \ 
    "https://${OPENSEARCH_FQDN}:9200/_index_template/samba_smb_template" 

curl -s --request POST \
    --user "admin:${OPENSEARCH_ADMIN_PASSWORD}" \
    --header "Content-Type: application/json" \
    --data "{\"index_patterns\": [\"samba_smb_folder\"], \"template\": {\"settings\": {\"index.number_of_shards\": \"1\", \"index.number_of_replicas\": \"0\", \"index.refresh_interval\": \"1s\"}, \"mappings\": {}}}" \ 
    "https://${OPENSEARCH_FQDN}:9200/_index_template/samba_smb_folder_template" 
```


- Build FScrawler: 

```bash
apt-get install maven git openjdk-11-jre-headless makepasswd
update-ca-certificates --fresh

cd /usr/local/src
git clone https://github.com/dadoonet/fscrawler.git
cd fscrawler

# Opensearch is binary compatible with elasticsearch 7. Because the version query fails, we hardcode the right version
cat << EOF | patch -p1
--- a/elasticsearch-client/src/main/java/fr/pilato/elasticsearch/crawler/fs/client/ElasticsearchClient.java     2023-03-27 21:40:44.580567110 +0200
+++ b/elasticsearch-client/src/main/java/fr/pilato/elasticsearch/crawler/fs/client/ElasticsearchClient.java     2023-03-27 21:52:47.076802247 +0200
@@ -230,12 +230,13 @@
             return version;
         }
         logger.debug("get version");
-        String response = httpGet(null);
+        // String response = httpGet(null);
         // We parse the response
-        DocumentContext document = parseJsonAsDocumentContext(response);
+        // DocumentContext document = parseJsonAsDocumentContext(response);
         // Cache the version and the major version
-        version = document.read("$.version.number");
-        majorVersion = extractMajorVersion(version);
+        // version = document.read("$.version.number");
+        // majorVersion = extractMajorVersion(version);
+        majorVersion = 7;
 
         logger.debug("get version returns {} and {} as the major version number", version, majorVersion);
         return version;
EOF
mvn package -Ddocker.skip

# The package 'fscrawler-distribution-2.10-SNAPSHOT.zip' is in 'distribution/target' 
```

- Install FScrawler:

```bash
useradd -d /opt/fscrawler -m -r -s /usr/sbin/nologin -U fscrawler
cd /opt/fscrawler
mkdir unpacked bin
cd unpacked
unzip /usr/local/src/fscrawler/distribution/target/fscrawler-distribution-2.10-SNAPSHOT.zip
cd -
ln -s unpacked/fscrawler-distribution-2.10-SNAPSHOT current
chmod 0755 current/bin/fscrawler
cat << EOF > /etc/default/fscrawler
JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
FS_JAVA_OPTS="-Xmx256m -Xms256m -DLOG_DIR=/opt/fscrawler/log -DLOG_LEVEL=trace -DDOC_LEVEL=debug"
EOF

usermod -s "/bin/bash" fscrawler
# As fscrawler user:
su - fscrawler
mkdir .fscrawler
ln -s .fscrawler etc
mkdir etc/samba_smb
usermod -s "/usr/sbin/nologin" fscrawler
```

- Copy `fscrawler/log4j2.xml` to `/opt/fscrawler/etc/log4j2.xml`

- For each share to index:
  - Determine the basename of the share-path, if the path is `/the/path/to/my/share`, the basename is `share`. 
  - `mkdir /opt/fscrawler/etc/samba_smb_<BASENAME-OF-SHARE>` 
  - Copy `fscrawler/share_settings.yml` to `/opt/fscrawler/etc/samba_smb_<BASENAME-OF-SHARE>/_share_settings.yml`
  - `chown fscrawler.fscrawler /opt/fscrawler/etc/samba_smb_<BASENAME-OF-SHARE>/_share_settings.yml`
  - Edit `/opt/fscrawler/etc/samba_smb/_share_settings.yml`:
    - Replace `<BASENAME-OF-SHARE>` with the basename of the share-path
    - Replace `"<PATH-OF-SHARE>` with the share-path
    - In `includes` set the sub-directory for each smb-share relative to the common root-path (the subdirs must start with a slash)
    - Replace `<OPENSEARCH-LOCAL-FSCRAWLER-PW>` with the opensearch service-account user password (`OPENSEARCH-LOCAL-FSCRAWLER-PW`)
    - Replace `<OPENSEARCH-FQDN>` with the opensearch hostname

- Copy `fscrawler/fscrawler_loop` to `/opt/fscrawler/bin/fscrawler_loop`
- Make it executable: `chmod +x /opt/fscrawler/bin/fscrawler_loop`
- Edit `/opt/fscrawler/bin/fscrawler_loop`:
  - For each share to index, set the basename of the share-path in `SHARE_NAMES`  


- Copy `fscrawler/systemd.unit` to `/lib/systemd/system/fscrawler.service`

```bash
systmctl daemon-reload
systmctl enable fscrawler
```

DO NOT START FScrawler before the filesystem permissions are set or it will not index existing files

FScrawler is ready and runs in its own user, which prevents indexing too much. 
Apart from the `_settings.yml`, the filesystem permissions determines what can be indexed. 

There is logging in:
- `/opt/fscrawler/log/fscrawler.log` 
- `/opt/fscrawler/log/documents.log` 
- `/opt/fscrawler/etc/samba_smb_<BASENAME-OF-SHARE>/_status.json` contains the current job status

Output of `fscrawler_loop` can be checked with `journalctl -f -u fscrawler.service`

FScrawler will index everything it finds at its first run and in subsequent runs it will use the last run time from
`/opt/fscrawler/etc/samba_smb_<BASENAME-OF-SHARE>/_status.json` and look at newer files only.

If the you are missing files in the index then try to remove the `_status.json` file, at the next run it will not know 
its indexing history and index everything again.


#### Samba fileserver 

- Add settings to `/etc/samba/smb.conf` in the `[global]` section:

```
[global]
        elasticsearch:address = localhost
        elasticsearch:port = 9200
        elasticsearch:use tls = no 

        # Spotlight 
        spotlight backend = elasticsearch
        elasticsearch:index = samb_smb
        elasticsearch:mappings = /usr/share/samba/mdssvc/elasticsearch_mappings.json
        elasticsearch:max results = 100
        elasticsearch:ignore unknown attribute = yes
        elasticsearch:ignore unknown type = yes       
```

- In `/etc/samba/smb.conf`  add `spotlight = yes` to each share section where Spotlight should be enabled.

Test the configuration with `testparm`, if there are lines starting with `Unknown parameter encountered:` your
configuration is incorrect. Fix it first!

Otherwise restart Samba: `systemctl restat smbd`

#### Samba share filesystem permissions 

Set ACLs on all shares that have `spotlight = yes` to allow access for fscrawler to the files

The description here assumes Posix ACLs are used on the shares. 
If NT-ACLs are used do not do the exact setup below but apply the same permissions using NT-ACL commands.

For each share with `spotlight = yes` do:
```bash
setfacl -Rm group:fscrawler:r-x "<SHARE-PATH>"
find "<SHARE-PATH>" -type d -exec setfacl -m default:group:fscrawler:r-x {} \;
```

This ensures fscrawler can only index files allowed by its group permission. 

Now it is the time to start fscrawler:
```bash
systmctl start fscrawler
```

Be aware that FScrawler is set up to run every 15 minutes, so it can take a while before files appear in the index changes.

Check the `"indexed"` counter in `/opt/fscrawler/etc/samba_smb_<BASENAME-OF-SHARE>/_status.json`, it should reflect the 
number of files on the share after the first run of FScrawler.    

Opensearch-dashboards can be used to view the detailed result of the indexing work, that appears in the `samba_smb` index. 


#### Opensearch-proxy

The Samba will connect to this proxy.

```bash
apt-get install apache2
```

- In `/etc/apache2/ports.conf` add a line: `Listen 127.0.0.1:9200`

- Create opensearch-proxy config
  - Do not forget to set the OPENSEARCH_ variables 

```bash
OPENSEARCH_PASSWORD="<OPENSEARCH-LOCAL-SAMBA-PW>"
OPENSEARCH_FQDN="<OPENSEARCH-FQDN>"

cat << EOF >> /etc/apache2/sites-available/opensearch_proxy.conf
<VirtualHost 127.0.0.1:9200 >
    DocumentRoot /var/www/opensearch_proxy
    SSLProxyEngine on

    <Location />
        AuthBasicFake "local_samba" "${OPENSEARCH_PASSWORD}"
        ProxyPass https://${OPENSEARCH_FQDN}:9200
        ProxyPassReverse https://${OPENSEARCH_FQDN}:9200
    </Location>
</VirtualHost>    
EOF

chgrp www-data /etc/apache2/sites-available/opensearch_proxy.conf
chmod 0640 /etc/apache2/sites-available/opensearch_proxy.conf
ln -s /etc/apache2/sites-available/opensearch_proxy.conf /etc/apache2/sites-enabled/opensearch_proxy.conf
mkdir /var/www/opensearch_proxy
a2enmod http_proxy
systemctl restart apache2
```

The Linux utility `mdsearch` can be used to check everything works.
It has a man page and takes the same arguments as the Mac utility `mdfind`.

For example, to find all jpeg images on a share run:
```bash
mdsearch -U<USER_NAME> <FILESERVER_HOSTNAME> <SHARE_NAME> 'kMDItemContentType=="public.jpeg"'
```

If this returns the expected output, everything is setup correctly and ready to use. 
Otherwise, check the logs to try and find the issue, some pointers are below.


Supported attribute- and mime-type mappings can be found in `/usr/share/samba/mdssvc/elasticsearch_mappings.json`

Logging is in:
- `/var/log/apache2` for the apache proxy (shows Samba queries to Opensearch)
- `/var/log/samba/og.rpcd_mdssvc` for Samba Spotlight
- On the Opensearch-server `/var/log/opensearch/<CLUSTERNAME>.log` for opensearch

Browsing to Opensaerch-dashboards can help to see the indexed files.
