# Windows-search on top of Spotlight for Samba

**DISCLAIMER: Use of anything provided here is at your own risk!**

WSP (Windows-search) on top of the Spotlight (Apple-search) setup for Samba


```text
  _____________   Spotlight     __________   Files,   ______________   Scan files    _____________ 
 |             |  query        |          |  ACLs    | Filesystem   |  + meta data  |             |
 |  Apple Mac  | ------------> |          | -------> |  File        | <------------ |  FScrawler  |   
 |             |  Filesharing  |  Samba   |          |   +          |               |             |
  -------------                |  file    |       +- |  ACL         |                -------------
                               |  server  |       |   --------------                     | 
                               |          |       |                                      | Create     
  -------------                |          | <-----+ Spotlight/WSP ACL info               | documents
 |             |  WSP query    |          |                                              V    
 |  MS Windows | ------------> |          |                 ______________          ______________ 
 |             |  Filesharing  |          | -------------> |  Anonymous   |        |              | 
  -------------                 ----------  Spotlight/WSP  |  Opensearch  | -----> |  Opensearch  |
                      User authnz |         query          |  proxy       |   +--- |  (Elastic7)  | 
                                  V                         --------------    |     -------------- 
                                _______________                               |    |              |
                               |               | <----------------------------+    |  Opensearch  |
                               |  Samba AD-DC  |   user authnz                     |  Dashboard   |
                               |               |                       User -----> |  (Kibana)    |
                                ---------------                        WebUI        --------------
```


Follow the documentation for [Spotlight](https://github.com/kvvloten/samba_addons/tree/main/fileserver_search) first

All together this is quite complex and hence not recommended without enough knowledge and skills :-) 

**The work on WSP is still experimental. 
Samba packages with the WSP patch the Samba packages are no longer production quality !!**

## Setup

Setup instructions are written for a Debian Bullseye server.

Samba current does not have support for authentication to Opensearch. 
An opensearch-proxy is setup which adds authentication over an encrypted connection. 
Since it listens to localhost only, this is secure enough.

Assumptions:
- A working Samba fileserver 
- Spotlight setup document in the link above is completed an working

If you really do not want to have Spotlight on your fileserver, do follow the Spotlight setup document but mark all shares with `spotlight = no`.

### Setup steps on Samba fileserver machine

On the Samba fileserver machine:
- Compile patched Debian Samba 4.17.10 packages
- Add Wsp to the Samba fileserver configuration
- Update filesystem permissions on shares for FScrawler


#### Build Samba Debian packages

The build process described below will build Debian packages for Bullseye with Samba 4.17.10


DO NOTE that: the Linux utility `wspsearch` is broken in the current patch, it coredumps and cannot be used.   


The build process uses docker to isolate all build dependencies in a container and keep your host clean.
Do note that docker manipulates iptables, if you do not want that, use another way to build the Debian packages

```bash
# setup docker for building packages
apt-get install docker.io git jq

# convert the 'current_wsp_417_wip' into a patch file
cd /usr/local/src
mkdir samba
cd samba

# create build directories
mkdir debian debian/build_container debian/packages debian/sources
```

- Copy `samba_packages/wsp_npower.patch` to `/usr/local/src/samba/wsp_npower.patch`
- Copy `samba_packages/wsp_debian.patch` to `/usr/local/src/samba/wsp_debian.patch`
- Copy `samba_packages/build` to `/usr/local/src/samba/debian/build_container`
- Copy `samba_packages/build_helper.sh` to `/usr/local/src/samba/debian/build_container`
- Copy `samba_packages/Dockerfile-debian-bullseye` to `/usr/local/src/samba/debian/build_container`

```bash
# Your name and email:
MAINTAINER_NAME="me"
MAINTAINER_EMAIL="me@localdomain.log"

# Noel Power's WSP work is using Samba 4.17
talloc_TAG="debian/2.3.4-3"
tevent_TAG="debian/0.13.0-3"
tdb_TAG="debian/1.4.7-3"
samba_TAG="debian/2%4.17.10+dfsg-0+deb12u1_bpo11+1"

VERSION="4.17.10"
EXTRA_VERSION="local1"  # update with every build (otherwise apt will not do anything on 'apt-get dist-upgrade'

cd /usr/local/src/samba/debian
mkdir packages/${VERSION}

# If you are using docker for other things on this machine, you probably don't want to do this:
docker ps -a -q | sort -u | xargs docker rm -f

# Create build container-image
cd build_container
docker build -t build-debian:bullseye -f Dockerfile-debian-bullseye .
cd -

for PKG in talloc tevent tdb samba; do
    TAG_VAR="${PKG}_TAG"
    SEMVER="$(echo ${!TAG_VAR} | sed -E 's/^debian\/([0-9]%)?([0-9.]+)[-+].+$/\2/')"
    mkdir -p sources/${PKG}
    # get source
    git clone https://salsa.debian.org/samba-team/${PKG}.git sources/${PKG}/${SEMVER}
    cd sources/${PKG}/${SEMVER}
    git checkout ${!TAG_VAR}
    cd -

    if [[ "${PKG}" == 'samba' ]]; then
        # Add the WSP-patch
        cp /usr/local/src/samba/wsp_npower.patch sources/${PKG}/${SEMVER}/debian/patches
        cp /usr/local/src/samba/wsp_debian.patch sources/${PKG}/${SEMVER}/debian/patches
        echo "wsp_npower.patch" >> sources/${PKG}/${SEMVER}/debian/patches/series
        echo "wsp_debian.patch" >> sources/${PKG}/${SEMVER}/debian/patches/series
        mv sources/${PKG}/${SEMVER}/debian/changelog .
        cat << EOF > sources/${PKG}/${SEMVER}/debian/changelog
samba ($(echo "${!TAG_VAR}" | awk -F / '{sub(/%/,":"); sub(/_/,"~"); print $2}')${EXTRA_VERSION}) unstable; urgency=medium

  * +wsp_npower.patch
  * +wsp_debian.patch
 -- ${MAINTAINER_NAME} <${MAINTAINER_EMAIL}>  $(date --rfc-email)

EOF
        cat ./changelog >> sources/${PKG}/${SEMVER}/debian/changelog
        rm ./changelog
    fi
    cd build_container
    ./build -i build-debian:bullseye -o /usr/local/src/samba/debian/packages/${VERSION} -d /usr/local/src/samba/debian/packages/${VERSION} /usr/local/src/samba/debian/sources/${PKG}/${SEMVER}
    cd -
done

apt-get install dpkg-dev
cd /usr/local/src/samba/debian/packages/${VERSION}
dpkg-scanpackages . /dev/null | gzip -9c > Packages.gz
cd -
echo "deb [trusted=yes] file:/usr/local/src/samba/debian/packages/${VERSION} ./"
apt-get update
```

Your packages are created in `/usr/local/src/samba/debian/packages/${VERSION}` and that directory is converted into a local apt source.

If you update your Samba fileserver (on the same machine), you should get your own packages installed:

```bash
apt-get dist-upgrade
```

In case your Samba fileserver has Samba >= 4.18.x installed, the above will not work as it will not downgrade.


#### Samba fileserver 

- Add settings to `/etc/samba/smb.conf` in the `[global]` section:

```
[global]
        # WSP
        wsp backend = elasticsearch
        elasticsearch:wspindex = samba_smb
        elasticsearch:wsp_mappings = /etc/samba/elasticsearch_mappings_wsp.json
        elasticsearch:wsp_acl_filtering = yes
        wsp result limit = 100
```

- In `/etc/samba/smb.conf`  add `wsp = yes` to each share section where Windows-search should be enabled.

- Copy `samba_fileserver/elasticsearch_mappings_wsp.json` to `/etc/samba/elasticsearch_mappings_wsp.json`

Test the configuration with `testparm`, if there are lines starting with `Unknown parameter encountered:` your
configuration is incorrect. If the errors point to the WSP parameters, then the installed packages do not have the WSP 
patches onboard. Fix this first!

Otherwise restart Samba: `systemctl restart smbd`

#### Samba share filesystem permissions 

Set ACLs on all shares that have wsp = yes` to allow access for FScrawler to the files

The description here assumes Posix ACLs are used on the shares. 
If NT-ACLs are used do not do the exact setup below but apply the same permissions using NT-ACL commands.

For each share with `wsp = yes`, do:
```bash
setfacl -Rm group:fscrawler:r-x "<SHARE-PATH>"
find "<SHARE-PATH>" -type d -exec setfacl -m default:group:fscrawler:r-x {} \;
```

Be aware that FScrawler is set up to run every 15 minutes, so it can take a while before files appear in the index changes.

Check the `"indexed"` counter in `/opt/fscrawler/etc/samba_smb_<BASENAME-OF-SHARE>/_status.json`, it should reflect the 
number of files on the share after the first run of FScrawler.    

Opensearch-dashboards can be used to view the detailed result of the indexing work, that appears in the `samba_smb` index. 


The Linux utility `wspsearch` is broken in the current patch, it coredumps and cannot be used.
That limits the test options, to queries from Windows.

Logging is in:
- `/var/log/apache2` for the apache proxy (shows WSP queries to Opensearch)
- `/var/log/samba/log.wspd` for samba WSP
- On the Opensearch-server `/var/log/opensearch/<CLUSTERNAME>.log` for opensearch

Browsing to Opensaerch-dashboards can help to see the indexed files.
