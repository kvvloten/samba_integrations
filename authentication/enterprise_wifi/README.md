# Enterprise-WIFI connecting with AD machine credentials

**DISCLAIMER: Use of anything provided here is at your own risk!**

Automatically connect to company wifi with AD machine credentials before users login.


The operating environment for described configuration:

```text
                                          -------- 
  _____________________                  | Wifi   |             ---------------
 |  Windows 10 / Linux |                 | Access |            | Linux         |
 |  Domain-member      |   802.11/EAP    | Point  |   Radius   | Domain-member |      
 |          --------   | \............/  |        | \......../ |               |
 |         |  Wifi  |  |---------- PEAP -- + -- MSCHAPv2 ----->|  Freeradius   |
 |         | 802.1x |  |  ............   |        |  ........  |      V        |
 |          --------   | /            \  |        | /        \ |   ntlm_auth   |           --------------- 
 |                     |                 |        |            |      V        |          |               |
 |                     |                  --------             |   Winbind     | -------> |  Samba AD-DC  |
 |                     |                                       |               |          |               |
  ---------------------                                         ---------------            --------------- 
```

## Setup

Setup instructions are written for a Debian Bookworm server.

Assumptions:
- Windows 10 machine is joined as a domain-member or Linux machine joined as domain-member using Samba Winbind
- On Linux domain-members the network should be managed by NetworkManager
- The server for Freeradius is joined as a domain-member using Samba tooling (Winbind).
- Valid certificates are used on the domain controllers and on the Freeradius server.
- Samba-AD has a (nested-) group `PERMISSION-GROUP` that contains computers with permission to use enterprise-wifi 
- The wifi-enterprise network will be configured to use WPA2 and EAS 


Use of valid certificates is important to ensure secure authentication while a non-secure authentication method (NTLMv1) is used.

A simple CA is good enough to create valid certificates for each server, for example [EasyRSA](https://github.com/OpenVPN/easy-rsa) can be used.
 
The setup involves:
1. Freeradius
2. Wifi Access Point
3. Client - Windows 10 
4. Client - Linux 

The aim is to be able to automate everything. Therefore manual actions, especially in UIs, are avoided. 
The instructions below are an extracted from Ansible code.


## Setup steps

### 1. Freeradius

- Install freeradius:

```bash
apt-get install freeradius freeradius-common freeradius-utils makepasswd
usermod -a -G winbindd_priv,ssl-cert freerad

cat << EOF > /etc/freeradius/3.0/users
DEFAULT Auth-Type = ntlm_auth
EOF

cat << EOF > /etc/freeradius/3.0/clients.conf
# For testing enable:
#client localhost {
#    ipaddr = 127.0.0.1
#    secret = testing123
#}

# For each access-point add:
client <AP_HOSTNAME> {
       ipaddr = <AP_IPADDRESS>
       netmask = 32
       secret = <AP_SECRET>
       shortname = <AP_HOSTNAME>
}
EOF
# Replace:
#  <AP_HOSTNAME> with the short hostname of the access-point 
#  <AP_IPADDRESS> with the ipaddress of the access-point
#  <AP_SECRET> with a shared secret, generate it with: makepasswd --chars=32

rm /etc/freeradius/3.0/sites-enabled/default
rm /etc/freeradius/3.0/sites-enabled/inner-tunnel
```

- Copy `radius/proxy.conf` to `/etc/freeradius/3.0/proxy.conf`
- Edit: `/etc/freeradius/3.0/proxy.conf`:
  - Replace `<DNS-DOMAIN>`with the dns domain-name of your AD-domain

- Copy `radius/site-samba_default` to `/etc/freeradius/3.0/sites-available/samba_default`
- Copy `radius/site-samba_inner-tunnel` to `/etc/freeradius/3.0/sites-available/samba_inner-tunnel`

- Copy `radius/mod-eap` to `/etc/freeradius/3.0/mods-available/eap`
- Edit: `/etc/freeradius/3.0/mods-available/eap`:
  - Replace `<SSL_KEY_FILENAME>`with the filename of the ssl private key for this server
  - Replace `<SSL_CERT_FILENAME>`with the filename of the ssl certificate for this server

- Configure the modules `mschap` and `ntlm_auth`:

```bash
# Put your permission group here:
PERMISSION_GROUP="<PERMISSION_GROUP>"

DOMAIN="$(dnsdomainname)"
NETBIOS_DOMAIN="$(dnsdomainname | awk -F '.' '{print toupper($1)}')"

cat << EOF > /etc/freeradius/3.0/mods-available/mschap
# Microsoft CHAP authentication
#
#  This module supports MS-CHAP and MS-CHAPv2 authentication.
#  It also enforces the SMB-Account-Ctrl attribute.
#
mschap {
    use_mppe = yes
    with_ntdomain_hack = yes
    require_encryption = yes
    require_strong = yes
    ntlm_auth = "/usr/bin/ntlm_auth --allow-mschapv2 --request-nt-key \
                 --domain=${NETBIOS_DOMAIN} \
                 --require-membership-of=${NETBIOS_DOMAIN}\${PERMISSION_GROUP} \
                 {% raw %}--username=%{%{mschap:User-Name}:-00} \
                 --challenge=%{%{mschap:Challenge}:-00} \
                 --nt-response=%{%{mschap:NT-Response}:-00}{% endraw %}"

    pool {
        start = ${thread[pool].start_servers}
        min = ${thread[pool].min_spare_servers}
        max = ${thread[pool].max_servers}
        spare = ${thread[pool].max_spare_servers}
        uses = 0
        retry_delay = 30
        lifetime = 86400
        cleanup_interval = 300
        idle_timeout = 600
    }
    passchange {
    }
}
EOF

cat << EOF > /etc/freeradius/3.0/mods-available/ntlm_auth
exec ntlm_auth {
        wait = yes
        shell_escape = yes
        program = "/usr/bin/ntlm_auth --allow-mschapv2 --request-nt-key \
                   --domain=${NETBIOS_DOMAIN} \
                   --require-membership-of=${NETBIOS_DOMAIN}\${PERMISSION_GROUP} \
                   --username=%{mschap:User-Name} --password=%{User-Password}"
}
EOF

ln -s /etc/freeradius/3.0/sites-available/samba_default /etc/freeradius/3.0/sites-enabled/samba_default
ln -s /etc/freeradius/3.0/sites-available/samba_inner-tunnel /etc/freeradius/3.0/sites-enabled/samba_inner-tunnel

ln -s /etc/freeradius/3.0/mods-available/eap /etc/freeradius/3.0/mods-enabled/eap
ln -s /etc/freeradius/3.0/mods-available/mschap /etc/freeradius/3.0/mods-enabled/mschap
ln -s /etc/freeradius/3.0/mods-available/ntlm_auth /etc/freeradius/3.0/mods-enabled/ntlm_auth
```

- Concatenate your ca-certificate and crl.pem to `/etc/freeradius/3.0/ca_and_crl.pem`
- Create a script to automate this, and run it every time the crl is updated. 
  The script should look similar to this:

```bash
# Update the name of ca.pem and crl.pem for your environment
cat /etc/ssl/certs/ca.pem /etc/ssl/certs/crl.pem > /etc/freeradius/3.0/ca_and_crl.pem
systemctl restart freeradius
```

- Enable and start Freeradius:

```bash
systemctl enable freeradius
systemctl start freeradius
```


If you want to debug Freeradius: 
```bash
systemctl stop freeradius
# Run it manually and in the foreground
freeradius -X
# Try to connect from Windows and watch the output
#
# Test authentication from another console with (when the test client is enabled in clients.conf:
#  radtest <user> <user-pw> 127.0.0.1 10 <client-pw>
```


### 2. Wifi Access Point

On the Wifi access point:
- Wireless Security Mode: WPA2-Enterprise
- Radius Server: Name or IPaddress of the Freeradius server
- Radius Port: 1812
- Radius Secret: The secret generated for this access point on radius server

Out of scope for this setup, i.e. leave unconfigured: NAS-ID, NAS-PORT, NAS-IP, Radius Accounting


### 3. Client - Windows 10 

Ensure Windows can validate the certificate used by Freeradius, e.g. import the CA-certificate:

```cmd
# Copy the CA-certificate from the Linux machine as: cacert.pem 
certutil -decode cacert.pem cacert.der
certutil -enterprise -f -v -AddStore "Root" cacert.der
```

There are two ways to create the wifi profile for enterprise-wifi on Windows. 

1. The first one is to run a script to create it on the Windows client which are member of `PERMISSION-GROUP`.

- Get the SHA1 fingerprint of the CA-certificate and a hexadecimal representation of the SSID:

```bash
# On the Freeradius server, create a fingerprint of the CA-certificate
CERT_FILE="/etc/ssl/certs/<CA_CERT_FILENAME>"  # Replace <CA__CERT_FILENAME> with the filename of the ca-certificate 
openssl x509 -noout -fingerprint -sha1 -inform pem -in ${CERT_FILE} | awk -F= '{gsub(/:/," ",$2);print tolower($2)}'

# The fingerprint should be put in the Windows wifi profile, see <!--CA_CERT_FINGERPRINT--> below


SSID_NAME="<SSID-NAME>"  # Put the ssid of the enterprise wifi network here
echo -n "${SSID_NAME}" | od -A n -t x1 | awk '{gsub(/ /,"",$0);print toupper($0)}'

# The hexadecimal representation of the SIDD should be put in the Windows wifi profile, see <!--SSID-HEX--> below
```

Continue on the Windows machine:

- Create the directory `C:\ProgramData\WLAN`
- Copy `windows/wlan_profile.xml` to `C:\ProgramData\WLAN\wlan_profile.xml`
- Edit `C:\ProgramData\WLAN\wlan_profile.xml`:
  - Replace `<!--SSID-NAME-->` with the SSID of the wifi-network
  - Replace `<!--SSID-HEX-->` with the hexadecimal representation of the SSID
  - Replace `<!--FREERADIUS_FQDN-->` with the 
  - Replace `<!--CA_CERT_FINGERPRINT-->` with the fingerprint retrieved on the Freeradius server (see above)

- Apply the WLAN-profile:

```cmd
rem Put the name of the SSID here:
set SSID_NAME=<SIDD-NAME>
set WLAN_PROFILE=C:\ProgramData\WLAN\wlan_profile.xml

netsh wlan add profile filename=%WLAN_PROFILE% user=all
netsh wlan set profileparameter name=%SSID_NAME% connectionmode=auto
```

2. The second method is to create a GPO and filter it to the group `PERMISSION-GROUP`.

Unless most other GPOs is this one that ends almost completely in LDAP as a set of 7 records (instead of 3), where one
contains a base64 encoded xml file.  It is quite identical to the `wlan_profile.xml` with an extra xml wrapper 
called `WLANPolicy` around it.

For now the simplest way around it seems to be to create the GPO manually. 

A fairly good description can be found [here](https://aventistech.com/kb/deploy-wireless-network-with-group-policy/), 
however there are some adjustments:

- On the `Security` TAB, set the `Authentication Method` to `Computer authentication` 
- On `Advanced security settins`, `Single Sign On` will be greyed out due to computer authentication, this is expected
- On `Protected EAP Properties`, set `Notifications before connecting` to `Do not ask user to authorize new servers or trusted CAs`


#### Mutually exclusive wired- and wireless network connection

As a bonus you can make wired-network and wifi mutually exclusive, which will cause the machine to switch automatically 
to wired when a cable is connected and to enterprise-wifi (when on premise) when the cable is disconnected.

Install NSSM using Chocolatey

```powershell
# Install Chocolatey 
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
# Install NSSM
choco install nssm
```

- Create the directory `C:\ProgramData\WLAN`
- Copy `windows\WLANManager.ps1` to `C:\ProgramData\WLAN`

If you are using a GPO to manage the WLAN-profile, then disable or remove line 70 (`Configure-DomainWLAN`) in `WLANManager.ps1`

Configure and start WLANManager as a service using NSSM:

```cmd
set NSM_CMD=C:\ProgramData\chocolatey\lib\NSSM\tools\nssm.exe

rem Configure the WLANManager service:

%NSSM_CMD% install WLANManager C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe
%NSSM_CMD% set WLANManager AppParameters ^"-NoProfile -ExecutionPolicy Bypass -Command ^\^"^& 'c:^\ProgramData^\wlan^\WLANManager.ps1'^\^"^"
%NSSM_CMD% set WLANManager AppDirectory C:\Windows\System32\WindowsPowerShell\v1.0 
%NSSM_CMD% set WLANManager AppExit Default Restart
%NSSM_CMD% set WLANManager AppStdoutCreationDisposition 2
%NSSM_CMD% set WLANManager AppStderrCreationDisposition 2
%NSSM_CMD% set WLANManager AppRotateFiles 1
%NSSM_CMD% set WLANManager AppRotateSeconds 86400
%NSSM_CMD% set WLANManager AppRotateBytes 104858
%NSSM_CMD% set WLANManager DisplayName "Composers WLAN Manager"
%NSSM_CMD% set WLANManager ObjectName LocalSystem
%NSSM_CMD% set WLANManager Start SERVICE_AUTO_START
%NSSM_CMD% set WLANManager Type SERVICE_WIN32_OWN_PROCESS

rem Start the WLANManager service:
%NSSM_CMD% start WLANManager
```

If you run a DHCP server it can be setup to use static DHCP for the machine and the return the same IP-address for both 
the wired and wireless MAC-addresses of the machine. Not only will the machine switch fluently between wired and 
enterprise-wifi, but since the IP-address remains the same any session will survive the switch !


### 4. Client - Linux 

Note: Locations of files are based on Debian Bookworm 

Ensure the machine can validate the certificate used by Freeradius, i.e. copy the ca-certificate to `/etc/ssl/certs` as `ca.pem`

Run the code below to complete the setup:

```bash
SSID_NAME="<SIDD-NAME>"  # Put the ssid of the enterprise wifi network here
PRINCIPAL="host/$(hostname -f)"  # The principal of the machine account

curl -s https://gitlab.com/samba-team/samba/raw/v4182-stable/source4/scripting/bin/machineaccountpw > /usr/local/sbin/machineaccountpw
chmod 750 /usr/local/sbin/machineaccountpw

MACHINE_PW="$(/usr/local/sbin/machineaccountpw)"
UUID="$(uuidgen)"

# Create the configuration for NetworkManager 
mkdir /etc/NetworkManager/system-connections
cat << EOF > /etc/NetworkManager/system-connections/wifi_ep-composers.nmconnection
[connection]
id=Domain Enterprise Wifi
uuid=${UUID}
type=wifi

[wifi]
mode=infrastructure
ssid=${SSID_NAME}

[wifi-security]
key-mgmt=wpa-eap

[802-1x]
ca-cert=/etc/ssl/certs/ca.pem
eap=peap;
identity=${PRINCIPAL}
password=${MACHINE_PW}
phase2-auth=mschapv2

[ipv4]
method=auto

[ipv6]
addr-gen-mode=stable-privacy
method=auto

[proxy]
EOF
systemctl restart NetworkManager

# Ensure the password gets updated within a minute after Winbind decided to update it 
cat << EOF > /usr/local/sbin/nm_ep_wifi_password_change
#!/bin/bash

# When running from cron PATH is not set
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

SECRETS_FILE_TIMESTAMP="$(stat -c %Z /var/lib/samba/private/secrets.tdb)"
NM_FILE_TIMESTAMP="$(stat -c %Z /etc/NetworkManager/system-connections/wifi_ep-composers.nmconnection)"
CURRENT_TIMESTAMP=$(date +%s)
INTERVAL=60

[[ ${SECRETS_FILE_TIMESTAMP} -gt ${NM_FILE_TIMESTAMP} ]] ||
 [[ ${SECRETS_FILE_TIMESTAMP} -gt $((CURRENT_TIMESTAMP - INTERVAL)) ]] || exit 0 

MACHINE_PW="$(machineaccountpw)"
sed -i "s/password=.+/password=${MACHINE_PW}/" /etc/NetworkManager/system-connections/wifi_ep-composers.nmconnection
systemctl reload NetworkManager.service
EOF
chmod 750 /usr/local/sbin/nm_ep_wifi_password_change

echo "* * * * * /usr/local/sbin/nm_ep_wifi_password_change > /dev/null 2>&1" > /etc/cron.d/nm_ep_wifi_password_change
```

#### Mutually exclusive wired- and wireless network connection

As a bonus you can make wired-network and wifi mutually exclusive, which will cause the machine to switch automatically 
to wired when a cable is connected and to enterprise-wifi (when on premise) when the cable is disconnected.

To make this work just copy files to `/etc/NetworkManager/dispatcher.d` 
- `nm/02-wifi-on-while-wired-inactive.sh`
- `nm/zz-wifi-off-while-wired-active.sh`

Make them executable and restart NetworkManager:
```bash
chmod 755 /etc/NetworkManager/dispatcher.d/02-wifi-on-while-wired-inactive.sh
chmod 755 /etc/NetworkManager/dispatcher.d/zz-wifi-off-while-wired-active.sh
systemctl restart NetworkManager
```

If you run a DHCP server it can be setup to use static DHCP for the machine and the return the same IP-address for both 
the wired and wireless MAC-addresses of the machine. Not only will the machine switch fluently between wired and 
enterprise-wifi, but since the IP-address remains the same any session will survive the switch !
