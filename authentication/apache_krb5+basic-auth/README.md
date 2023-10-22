# Apache with Kerberos and Basic authentication fallback to Samba-AD

**DISCLAIMER: Use of anything provided here is at you own risk!**

Apache authentication based on Kerberos-ticket against Samba-AD with fallback to Basic-auth if no ticket is offered.
Authorization uses LDAP in both cases, it reads nested groups to check group membership.   

```text
  ___________                    ___________                       _______________     
 |           |   Krb5-ticket    |  Apache   |  authn Krb5-ticket  |               |
 |  Browser  | ===============> |  server   | ------------------> |               |
 |           |                  |           | --+                 |               | 
  -----------                   :...........:   |  authz LDAP     |               |
                                :           :   +---------------> |  Samba AD-DC  |
  -----------                   :...........:   |
 |           |                  |  Apache   | --+                 |               |
 |  Browser  | ==============>  |  server   |      authn LDAP     |               |            
 |           |                  |           | ------------------> |               |  
  -----------                    -----------                       ---------------
```

## Setup

Setup instructions are written for a Debian Bookworm server.

In Bullseye `libpam-python` is Python-2 based which adds a lot of complexity to the setup of the venv (in Bookworm it is Python-3). 

Assumptions:
- Apache2 is set up and has a TLS enabled vhost ready to use. 
- Samba-AD has a (nested-) group `PERMISSION-GROUP` that contains users with permission to use the sample application 

### Steps

Create a service account on the DC

```bash
# On one of the DCs:
# Create a service account for Apache
samba-tool user create <SERVICE-ACCOUNT NAME>  # for example svc_<HOSTNAME>_apache
samba-tool user setexpiry --noexpiry <SERVICE-ACCOUNT NAME>
samba-tool spn add http/<HOSTNAME> <SERVICE-ACCOUNT NAME>
samba-tool domain exportkeytab -d 8 --principal=http/<HOSTNAME> ~/<SERVICE-ACCOUNT NAME>.keytab

# Get the DN
samba-tool user show <SERVICE-ACCOUNT NAME>
```

Continue on the Apache server.

```bash
apt-get install makepasswd apache2 libapache2-mod-auth-gssapi krb5-user
for module in session sesion_cookie session_crypto ldap authnz_ldap auth_gssapi; do
    a2enmod ${module}
done
mkdir /etc/keytab
mkdir /etc/systemd/system/apache2.service.d
mkdir -m 0750 /etc/apache2/conf-available/include
chown www-data:www-data /etc/apache2/conf-available/include

# Generate a SESSION_COOKIE_PASSPHRASE, use it on all apache servers with kerberos authentication in the domain
makepasswd --chars=32
# Generate GSSAPI_SESSION_KEY, use it on all apache servers with kerberos authentication in the domain
makepasswd --chars=32 | base64
```

- Copy the keytab file `~/<SERVICE-ACCOUNT NAME>.keytab` from the DC to `/etc/keytab/<SERVICE-ACCOUNT NAME>.keytab`
- Copy `systemd_override.conf` to `/etc/systemd/system/apache2.service.d/override.conf`
- Copy `authn_krb5_or_krb_basic-authz_ldap.conf` to `/etc/apache2/conf-available/include/authn_krb5_or_krb_basic-authz_ldap.conf`
- Edit `/etc/apache2/conf-available/include/authn_krb5_or_krb_basic-authz_ldap.conf`:
  - Replace `<GSSAPI_SESSION_KEY>` with the above generated `GSSAPI_SESSION_KEY`
  - Set DC hostnames in `<YOUR 1ST DC-SERVER>` and `<YOUR 2ND DC-SERVER>`
  - Set the base-DN of your user-accounts in `<BASE_DN>`
  - Set DN of the SERVICE-ACCOUNT for apache in `<SERVICE-ACCOUNT DN>` 
  - Set password of the SERVICE-ACCOUNT in `<SERVICE-ACCOUNT PASSWORD>`

- Copy `session_cookie_passphrase.conf` to `/etc/apache2/conf-available/include/session_cookie_passphrase.conf`
- Edit `/etc/apache2/conf-available/include/session_cookie_passphrase.conf`:
  - Replace `<SESSION_COOKIE_PASSPHRASE>` with the above generated `SESSION_COOKIE_PASSPHRASE`

- Copy `krb5.conf` to `/etc/krb5.conf`
- Edit `/etc/krb5.conf`:
  - Replace `SAMBA-REALM>` with the realm of your AD-domain
  - Replace `DNS-DOMAIN>`with the dns domain-name of your AD-domain

- Copy `vhost_krb5.conf` to `/etc/apache2/conf-available/vhost_krb5.conf`
- In the vhost that will contain protected websites add a line: `Include /etc/apache2/conf-available/vhost_krb5.conf`

```bash
chmod 0640 /etc/keytab/<SERVICE-ACCOUNT NAME>.keytab
chown root:www-data /etc/keytab/<SERVICE-ACCOUNT NAME>.keytab

systemctl restart apache2
```

At this point Apache is ready for Kerberos or Basic authentication and LDAP authorization. The only work left is to add protetected websites.


### Add one or more protected websites

The simpelest website example is just a directory list view:

Add this in the vhost configuration somewhere after the line `Include /etc/apache2/conf-available/vhost_krb5.conf`:

```bash
cat > /etc/apache2/conf-available/mywebsite.conf << EOF
Alias /mywebsite /var/www/mywebsite
<Directory /var/www/mywebsite>
    Define PERMISSION_GROUP acl-mywebsite-access
    Include /etc/apache2/conf-available/include/authn_krb5_or_krb_basic-authz_ldap.conf

    DirectoryIndex disabled
    Options +Indexes
    IndexOptions HTMLTable SuppressColumnsorting FancyIndexing SuppressHTMLPreamble
    IndexOptions SuppressLastModified SuppressDescription SuppressSize
    IndexIgnore ..
</Directory>
EOF

mkdir /var/www/mywebsite
touch /var/www/mywebsite/hello_world
```

- Update the vhost conf file, after the line `Include /etc/apache2/conf-available/vhost_krb5.conf` add a line `Include /etc/apache2/conf-available/mywebsite.conf`
- Reload Apache: `systemctl reload apache2`  

Now you can browse to `https://<WEBSERVER>/mywebsite`

You get access when:
1. you have a Kerberos-ticket (and your browser is configured to forward it to the server)
2. or you authenticate with user-id and password
3. and you are direct or indirect member of the LDAP group `acl-mywebsite-access` 


### Kerberos browser configuration

Browsers do not forward Kerberos-tickets by default, it must be enabled for specific domains explicitly. 

In general the automated method to get configuration (including this) is to use a GPO. The Firefox example below is just for quick manual testing. 

To enable Kerberos authentication in Firefox:

- Open Firefox and enter `about:config` in the address bar. Dismiss any warnings that appear.
- In the Filter field, enter negotiate.
- Double-click the `network.negotiate-auth.trusted-uris` preference. This preference lists the trusted sites for Kerberos authentication.
- In the dialog box, enter `<DNS-DOMAIN>`.
- Click the OK button.
- The domain that you just entered in the` network.negotiate-auth.trusted-uris` should now appear in Value column. The setting takes effect immediately; you do not have to restart Firefox.
