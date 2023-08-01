# Openvpn with Privacyidea MFA and Samba authorization

OpenVPN setup with Privacyidea MFA authentication and Samba LDAP authorization based on nested group membership.

A description of how to setup Privacyidea with Samba backend is [here](../privacyidea/README.md)


Since OpenVPN sessions can be kept open for a long time a scheduled script will expire older sessions. 
This forces new authentication sequence and will lockout user that got disabled in Samba. 

The OpenVPN server is setup to push client configuration settings when a client connects. 
This keeps maintenance on the client.conf low.

## Setup

Setup instructions are written for a Debian Bullseye server.

In Bullseye `libpam-python` is Python-2 based which adds a lot of complexity to the setup of the venv (in Bookworm it is Python-3). 

Assumptions:
- A X509 certificate and a key file suitable for openvpn are available
- A X509 ca.crt file is available
- Samba-AD has a (nested-) group 'PERMISSION-GROUP' that contains users with permission to use OpenVPN 

### Setup steps

- Install packages

```bash
apt-get install python2 libpam-python libpam-ldap openvpn sqlite3 curl

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
 
- Create a python2 venv:

```bash
mkdir -p /opt/privacyidea_pam/get_pip_root
curl -s https://bootstrap.pypa.io/pip/2.7/get-pip.py > /opt/privacyidea_pam/get-pip.py
python2 /opt/privacyidea_pam/get-pip.py --no-python-version-warning --no-warn-script-location --prefix /opt/privacyidea_pam/get_pip_root
PYTHONPATH=/opt/privacyidea_pam/get_pip_root/lib/python2.7/site-packages \
   /opt/privacyidea_pam/get_pip_root/bin/pip2 install --prefix=/opt/privacyidea_pam/get_pip_root virtualenv
source /opt/privacyidea_pam/bin/activate
pip install pip setuptools wheel --upgrade
```

- Install privacyidea_pam

```bash
source /opt/privacyidea_pam/bin/activate
curl -s https://raw.githubusercontent.com/privacyidea/pam_python/master/privacyidea_pam.py > /opt/privacyidea_pam/lib/python2.7/site-packages/privacyidea_pam.py
pip install -r https://raw.githubusercontent.com/privacyidea/pam_python/master/requirements.txt
mkdir /etc/privacyidea
```

  Initialize Sqlite database for privacyidea_pam

```bash
touch /etc/privacyidea/pam.sqlite
chmod 0600 /etc/privacyidea/pam.sqlite
cat << EOF | sqlite3 /etc/privacyidea/pam.sqlite
CREATE TABLE authitems (counter int, user text, serial text, tokenowner text,otp text, tokentype text);
CREATE TABLE refilltokens (serial text, refilltoken text);
EOF 
```

- Copy `pam-openvpn` to `/etc/pam.d/openvpn`


- Create a service-account in Samba

```bash
# On one of the DCs:
samba-tool user create <SERVICE-ACCOUNT NAME>
# Ensure this account does not expire

# Get the DN and put it in slapd.conf
samba-tool user show <SERVICE-ACCOUNT NAME>
```

- Copy `pam_ldap.conf` to `/etc/pam_ldap.conf`
- Update permissions: `chmod 0640 /etc/pam_ldap.conf`
- Edit `/etc/pam_ldap.conf`:
  - Set DC hostnames in `uri`
  - Set DN of the SERVICE-ACCOUNT in `binddn`
  - Set password of the SERVICE-ACCOUNT in `bindpw`
  - Set base-DN in `base`
  - Set DN of the PERMISSION-GROUP in `pam_filter`


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
