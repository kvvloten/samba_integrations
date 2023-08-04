# Self Service Password webinterface

Web interface to change in an LDAP directory. 
The project's github page is [here](https://github.com/ltb-project/self-service-password) 


## Setup

**It is not recommended to use a Samba-AD-DC server to setup the Self Service Password!** 
Self Service Password requires a webserver, which opens up an extra attach-vector to your DCs, therefore it is better to put it on another machine. 

Setup instructions are written for a Debian Bullseye server.

Assumptions:
- Apache2 is setup on the same server as Privacyidea and has a TLS enabled vhost ready to use. 

### Setup steps

- Install packages

```bash
apt-get install curl
cat << EOF > /etc/apt/sources.list.d/self_service_password.list
deb [arch=amd64 signed-by=/usr/share/keyrings/self_service_password.gpg] https://ltb-project.org/debian/stable stable main
EOF
curl -s https://ltb-project.org/wiki/lib/RPM-GPG-KEY-LTB-project > /usr/share/keyrings/self_service_password.gpg
apt-get update

apt-get install self-service-password smarty3 makepasswd apache2

# KEYPHRASE:
makepasswd --chars=32
```

- Create a service-account in Samba:

```bash
# On one of the DCs:
samba-tool user create <SERVICE-ACCOUNT NAME>
# Ensure this account does not expire

# Get the DN and put it in slapd.conf
samba-tool user show <SERVICE-ACCOUNT NAME>
```

- Allow password-change over LDAP in Samba:

```bash
# On one of the DCs:
samba-tool "samba-tool forest directory_service show"
# Look at the value of dsheuristics, we need to set digit 9 to a value of 1
#   if the current output shows 'dsheuristics: 000000000'
#   the new setting is: 'dsheuristics: 000000001'
# Determine the right value and put it in the variable:
DSHEURISTICS="000000001"
samba-tool forest directory_service dsheuristics "${DSHEURISTICS}"
```

- Copy `config.inc.php` to `/usr/share/self-service-password/conf/config.inc.php`
- Edit `/usr/share/self-service-password/conf/config.inc.php`:
  - Set DC hostnames in `$ldap_url`
  - Set DN of the SERVICE-ACCOUNT in `$ldap_binddn`
  - Set password of the SERVICE-ACCOUNT in `$ldap_bindpw`
  - Set the base-DN of your user-accounts in `$ldap_base`
  - Set password minimum password length according to the password policy in `$pwd_min_length`
  - Set KEYPHRASE in `$keyphrase`
  - With the current settings (change these to your needs):
    - unlock a user on password change
    - allows changing expired password (similar to Windows 10). 

- Copy `apache.conf` to `/etc/apache2/conf-available/self_service_password.conf`
- The uri is set to `/ssp` in `/etc/apache2/conf-available/self_service_password.conf`, change it if you want something else
- Edit `/etc/apache2/sites-enabled/default-ssl.conf` (or whatever is your TLS enabled vhost conf):
  - Insert a line `Include /etc/apache2/conf-available/self_service_password.conf` in the vhost
  - Reload apache `apachectl graceful`
