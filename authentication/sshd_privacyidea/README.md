# SSHD with Privacyidea MFA and Samba authorization (for access from internet)

**DISCLAIMER: Use of anything provided here is at you own risk!**

SSHD setup with Privacyidea MFA authentication and Samba LDAP authorization based on nested group membership.

The configuration uses a split setup aimed at a DMZ-host with SSHD open to the internal network and to the internet. 
On login from internet MFA (or public key authentication) is used, whereas users from local network follow the default login sequence. 
The default login for local network users is not touched by the setup below.

A description of how to setup Privacyidea with Samba backend is [here](../privacyidea/README.md)

```text
    __   _                  __________ _______                     _______________  
  _(  )_( )_               |          |       |       authn MFA   |               | 
 (          )     MFA      |  SSH     |  Pam  | ----------------> |  Privacyidea  | 
(  INTERNET  ) <=========> |  daemon  |       | ----+             |               | 
 (_   _    _)              |          |       |     |              ---------------  
   (_) (__)                :..........: ------      |          LDAP     |  ^ LDAP
                           :          :             |          account  |  | attributes
     ______                :          :             |          validate V  |           
    |  PC  |               :..........: ______      |              _______________  
     ------                |          |       |     | authz LDAP  |               | 
       |                   |  SSH     | Pam   |     +-----------> |  Samba AD-DC  | 
 ______|______ <========>  |  daemon  |       |                   |               | 
     |   LAN    password   |          |       |                    ---------------  
  ______                    ---------- -------                                       
 |  PC  |                                 |                     
  ------                                  +---> via nsswitch, e.g. files, systemd, winbind          
```

## Setup

Setup instructions are written for a Debian Bookworm server.


The setup partially overlaps with [Openvpn with Privacyidea](../openvpn_privacyidea/README.md), the sections 
'Create a python2 venv' and 'Install and configure privacyidea_pam' can be skipped here when they are already setup.

Assumptions:
- Samba-AD has a (nested-) group `PERMISSION-GROUP` that contains users with permission to login from internet on this server. 
- The users to login are known / can be resolved on the host (e.g. through winbind-nss)
- The users to login have a home-directory (or pam-mkhomedir should be added to create it) 

### Setup steps

- Install packages

```bash
apt-get install libpam-ldap sshd

# We do not want to use pam-ldap for standard logins:
pam-auth-update --remove ldap
```

- Copy `banner.txt` to `/etc/ssh/sshd_banner.txt`
- Append `block_sshd_config` at the end of `/etc/ssh/sshd_config`
- Edit `/etc/ssh/sshd_config`:
  - Change `<LOCAL_NETWORK_CIDR>` to the subnet-cidr of your local network


- Copy `pam_access-lan_lo.conf` to `/etc/security/pam_access-lan_lo.conf`
- Edit `/etc/security/pam_access-lan_lo.conf`:
  - Change `<LOCAL_NETWORK_CIDR>` to the subnet-cidr of your local network


- Copy `pam-sshd` to `/etc/pam.d/sshd`
- Edit `/etc/pam.d/sshd`:
  - Set `<PRIVACYIDEA_BASE_URL>` to the URL of Privacyidea


- Create a python venv and install privacyidea_pam (skip this if already setup for OpenVPN + Privacyidea):

```bash
# If a python2 venv was setup for Bullseye, remove that first:
rm -r /opt/privacyidea_pam

# Setup for Bookworm
python3 -m venv /opt/privacyidea_pam
source /opt/privacyidea_pam/bin/activate
pip install pip setuptool wheel --upgrade 
pip install requests certifi chardet idna passlib requests urllib3
curl -s https://raw.githubusercontent.com/privacyidea/pam_python/master/privacyidea_pam.py > /opt/privacyidea_pam/lib/python3.11/site-packages/privacyidea_pam.py

# Patch privacyidea_pam to work in a venv
cd /opt/privacyidea_pam/lib/python3.11/site-packages
cat << EOF | patch -p1
--- a/privacyidea_pam.py    2022-03-24 11:55:05.601712742 +0100
+++ b/privacyidea_pam.py    2022-03-24 17:11:27.569721976 +0100
@@ -39,6 +39,11 @@
 The code is tested in test_pam_module.py
 """
 
+import os
+import site
+FILE_PATH = os.path.dirname(os.path.abspath(__file__))
+site.addsitedir(FILE_PATH)
+
 import json
 import requests
 import syslog
EOF
cd -

# Configurions
mkdir /etc/privacyidea
touch /etc/privacyidea/pam.sqlite
chmod 0600 /etc/privacyidea/pam.sqlite
cat << EOF | sqlite3 /etc/privacyidea/pam.sqlite
CREATE TABLE authitems (counter int, user text, serial text, tokenowner text,otp text, tokentype text);
CREATE TABLE refilltokens (serial text, refilltoken text);
EOF 
```


- Create a service-account in Samba (or skip if you re-use the account created for OpenVPN + Privacyidea)

```bash
# On one of the DCs:
samba-tool user create <SERVICE-ACCOUNT NAME>  # for example svc_<HOSTNAME>_sshd
samba-tool user setexpiry --noexpiry <SERVICE-ACCOUNT NAME>

# Get the DN and put it in slapd.conf
samba-tool user show <SERVICE-ACCOUNT NAME>
```

- Copy `pam_ldap.conf` to `/etc/security/pam_ldap_sshd.conf`
- Update permissions: `chmod 0640 /etc/security/pam_ldap_sshd.conf`
- Edit `/etc/security/pam_ldap_sshd.conf`:
  - Set DC hostnames in `uri`
  - Set DN of the SERVICE-ACCOUNT in `binddn`
  - Set password of the SERVICE-ACCOUNT in `bindpw`
  - Set base-DN in `base`
  - Set DN of the PERMISSION-GROUP in `pam_filter`


- Restart sshd

Once you have setup your MFA-token in Privacyidea, you are ready to login to ssh with MFA from internet 
