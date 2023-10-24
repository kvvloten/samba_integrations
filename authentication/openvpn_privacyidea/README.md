# Openvpn with Privacyidea MFA and Samba authorization

**DISCLAIMER: Use of anything provided here is at you own risk!**

OpenVPN setup with Privacyidea MFA authentication and Samba LDAP authorization based on nested group membership.

A description of how to setup Privacyidea with Samba backend is [here](../privacyidea/README.md)


Since OpenVPN sessions can be kept open for a long time a scheduled script will expire older sessions. 
This forces new authentication sequence and will lockout user that got disabled in Samba. 

The OpenVPN server is setup to push client configuration settings when a client connects. 
This keeps maintenance on the client.conf low.

```text
  ___________              ___________ _______                  _______________  
 |           |     MFA    |           |       |    authn MFA   |               | 
 |  OpenVPN  | <========> |  Openvpn  |  Pam  | -------------> |  Privacyidea  | 
 |  client   |            |  server   |       | -+             |               | 
 |           |            |           |       |  |              ---------------  
  -----------              ----------- -------   |          LDAP     |  ^ LDAP
                                                 |          account  |  | attributes
                                                 |          validate V  |           
                                                 |              _______________  
                                                 | authz LDAP  |               | 
                                                 +-----------> |  Samba AD-DC  | 
                                                               |               | 
                                                                ---------------  
```


## Setup

Setup instructions are written for a Debian Bookworm server.

The setup partially overlaps with [SSHD with Privacyidea](../sshd_privacyidea/README.md), the sections 
'Create a python2 venv' and 'Install and configure privacyidea_pam' can be skipped here when they are already setup.

Assumptions:
- A X509 (server-) certificate and a key file suitable for openvpn are available
- A X509 ca.crt file is available
- Samba-AD has a (nested-) group `PERMISSION-GROUP` that contains users with permission to use OpenVPN 

### Setup steps

- Install packages

```bash
apt-get install libpam-ldap openvpn

# We do not want to use pam-ldap for standard logins:
pam-auth-update --remove ldap
mkdir /etc/openvpn/ccd_password /etc/openvpn/server
openvpn --genkey --secret /etc/openvpn/server/ta.key
```

- Copy your X509 certificate file to `/etc/openvpn/server/server.crt`
- Copy your X509 key file to `/etc/openvpn/server/server.key`
- Copy your X509 ca.crt to `/etc/openvpn/server/ca.crt`


- Copy `logrotate.conf` to `/etc/logrotate.d/openvpn.conf`
- Copy `cron_d` to `/etc/cron.d/openvpn_expire`
- Copy `etc_default` to `/etc/default/openvpn`


- Edit `/lib/systemd/system/openvpn@.service`:
  - Change `LimitNPROC=100` to `#LimitNPROC=100` 
  - Change `PrivateTmp=true` to `#PrivateTmp=true` 
- Run: `systemctl daemon-reload`

- Copy `server_password.conf` to `/etc/openvpn/server_password.conf`
- Edit `/etc/openvpn/server_password.conf`:
  - Set VPN network details in `server`

 
- Copy `DEFAULT` to `/etc/openvpn/ccd_password/DEFAULT`
- Edit `/etc/openvpn/ccd_password/DEFAULT`:
  - Set local network details in `route`
  - Set IP-addresses of Samba-DCs in `dhcp-option DNS`

 
- Copy `pam-openvpn` to `/etc/pam.d/openvpn`
- Edit `/etc/pam.d/openvpn`:
  - Set `<PRIVACYIDEA_BASE_URL>` to the URL of Privacyidea


- Create a python venv and install privacyidea_pam (skip this if already setup for SSHD + Privacyidea):

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


- Create a service-account in Samba (or skip if you re-use the account created for SSHD + Privacyidea)

```bash
# On one of the DCs:
samba-tool user create <SERVICE-ACCOUNT NAME>  # for example svc_<HOSTNAME>_openvpn
samba-tool user setexpiry --noexpiry <SERVICE-ACCOUNT NAME>

# Get the DN and put it in slapd.conf
samba-tool user show <SERVICE-ACCOUNT NAME>
```

- On upgrading from Bullseye:
  a per pam configuration is no longer supported, the global nslcd.conf is what is left,   
  remove `/etc/security/pam_ldap_openvpn.conf` 

- Copy `nslcd.conf` to `/etc/nslcd.conf`
- Update permissions: `chmod 0640 /etc/nslcd.conf`
- Update group: `chgrp nslcd /etc/nslcd.conf`
- Edit `/etc/nslcd.conf`:
  - Set DC hostnames in `uri`
  - Set DN of the SERVICE-ACCOUNT in `binddn`
  - Set password of the SERVICE-ACCOUNT in `bindpw`
  - Set base-DN in `base`
  - Set DN of the PERMISSION-GROUP in `filter passwd`

- Restart services:
```bash
systemctl restart nslcd
systemctl restart openvpn 
```

### OpenVPN Windows client configuration

- Install chocolatey on your Windows Machine:

```powershell
$env:chocolateyUseWindowsCompression='false'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))
```

- Install OpenVPN:
```powershell
choco install openvpn
mkdir "C:\Program Files\OpenVPN\config\client"
```

- Copy `client.conf` to `C:\Program Files\OpenVPN\config\client.ovpn`
- Edit `C:\Program Files\OpenVPN\config\client.ovpn`
  - Set server fqdn in `remote`

- Copy `ta.key` from the server `/etc/openvpn/server/ta.key`to Windows `C:\Program Files\OpenVPN\config\client\ta.key`  
- Copy `ca.crt` from the server `/etc/openvpn/server/ca.crt`to Windows `C:\Program Files\OpenVPN\config\client\ca.crt`  

Once you have setup your MFA-token in Privacyidea, you are ready to use OpenVPN 
