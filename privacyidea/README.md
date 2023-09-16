# Privacyidea with Samba backend

**DISCLAIMER: Use of anything provided here is at your own risk!**

[Privacyidea](https://github.com/privacyidea/privacyidea) is a versatile multi-factor authentication system. When configured with Samba as backend users get MFA with their Samba user-id.  

Privacyidea supports a variety of tokens and integrations, e.g. Openvpn integration and 2FA for Windows domain-clients. A list of features is [here](https://www.privacyidea.org/about/features/)

```text
             | WebUI for users
             | to manage MFA tokens
             V 
         _______________                _______________
   MFA  |               |  LDAP-query  |               |
 -----> |  Privacyidea  | -----------> |  Samba AD-DC  |
        |               |              |               |
         ---------------                ---------------
```

## Setup

**Do not use a Samba-AD-DC server to setup Privacyidea!** 

Setup instructions are written for a Debian Bullseye server.

The instructions below will use a Postgresql database but other databases are supported, see [docuementation](https://privacyidea.readthedocs.io/en/latest/installation/pip.html#database)

Assumptions:
- Postgresql is already setup, possible on a different server.
- Apache2 is setup on the same server as Privacyidea and has a TLS enabled vhost ready to use. 
- Each service will use its own service-account to connect to Samba-AD

### Initial setup steps

- Install packages

```bash
# Set the version you want to use here:
PRIVACYIDEA_VERSION=3.8.1
# Versions can be found at: https://github.com/privacyidea/privacyidea/tags

apt-get install postgresql-client python3-pip python3-venv makepasswd apache2 libapache2-mod-wsgi-py3 jq curl
a2enmod wsgi

mkdir /etc/privacyidea /var/log/privacyidea /opt/privacyidea
useradd -d /opt/privacyidea/wsgi -m -r -s /usr/sbin/nologin -U -G www-data privacyidea
mkdir -m 0750 /opt/privacyidea/venv
python3 -m venv /opt/privacyidea/venv
source /opt/privacyidea/venv/bin/activate
pip install pip setuptool wheel --upgrade 
pip install psycopg2-binary
pip install -r https://raw.githubusercontent.com/privacyidea/privacyidea/v${PRIVACYIDEA_VERSION}/requirements.txt
pip install privacyidea==${PRIVACYIDEA_VERSION}
chmod -R privacyidea.www-data /opt/privacyidea/venv
chmod privacyidea /etc/privacyidea /var/log/privacyidea
```

- Copy `logrotate.conf` to `/etc/logrotate.d/privacyidea.conf`

On the Postgresql host:

- Create the database and user:

```bash
# DATABASE PASSWORD:
makepasswd --chars=32
sudo -i
su - postgres
psql
# In psql:
CREATE DATABASE privacyidea;
CREATE USER privacyidea WITH ENCRYPTED PASSWORD '<DATABASE PASSWORD>';
GRANT ALL PRIVILEGES ON DATABASE privacyidea TO privacyidea;
EXIT
```

- Add a line to /etc/postgresql/<version>/main/pg_hba.conf to enable access over the network for Privacyidea:
```text
hostssl privacyidea privacyidea <IP of Privacyidea-host>/32 scram-sha-256
```

Return to the Privacyidea host:

- Genereate 2 passwords of 24 chars:
```bash
# SECRET_KEY:
makepasswd --chars=24
# PI_PEPPER:
makepasswd --chars=24
```
- Copy `pi.cfg` to `/etc/privacyidea/pi.cfg`
- Edit the `/etc/privacyidea/pi.cfg`:
  - Set the `SECRET_KEY` and `PI_PEPPER`to the 24 char passwords
  - Set the DATABASE PASSWORD and database server fqdn in `SQLALCHEMY_DATABASE_URI`


- Initial setup commands:

```bash
usermod -s "/bin/bash" privacyidea
su - privacyidea
PRIVACYIDEA_CONFIGFILE="/etc/privacyidea/pi.cfg"
PI_CMD=/opt/privacyidea/venv/bin/pi-manage/bin/pi-manage
# ADMIN PASSWORD 
ADMIN_PASSWORD="$(makepasswd --chars=24)"
ADMIN_MAIL_ADDRESS="<YOUR-ADMIN-MAIL-ADDRESS>"

${PI_CMD} createdb
${PI_CMD} db upgrade -d /opt/privacyidea/venv/lib/privacyidea/migrations
${PI_CMD} create_audit_keys
${PI_CMD} create_enckey
${PI_CMD} admin add admin -e "${ADMIN_MAIL_ADDRESS}" -p "${ADMIN_PASSWORD}"  

usermod -s "/usr/sbin/nologin" privacyidea
```

- Copy `privacyidea.wsgi` to `/opt/privacyidea/wsgi/privacyidea.wsgi`
- If your python version is NOT python3.9 (default for Debian Bullseye) then edit the `/opt/privacyidea/wsgi/privacyidea.wsgi`:
  - Change `/opt/privacyidea/venv/lib/python3.9/site-packages` to match your environment


- Copy `apache.conf` to `/etc/apache2/conf-available/privacyidea.conf`
- The uri is set to `/pi` in `/etc/apache2/conf-available/privacyidea.conf`, change it if you want something else
- Edit `/etc/apache2/sites-enabled/default-ssl.conf` (or whatever is your TLS enabled vhost conf):
  - Insert a line `Include /etc/apache2/conf-available/privacyidea.conf` in the vhost
  - Reload apache `systemctl restart apache2`

### Test

- Open a broswser an navigate to Privacyidea `https://<YOUR SERVER FQDN>/pi`, you should get the login dialog
- Check if you can login with user `admin` and password `<ADMIN_PASSWORD>`
- If that works the initial setup is successful.

### Configure Privacyidea with Samba backend
 
- Create a service-account in Samba

```bash
# On one of the DCs:
samba-tool user create <SERVICE-ACCOUNT NAME>
samba-tool user setexpiry --noexpiry <SERVICE-ACCOUNT NAME>

# Get the DN and put it in slapd.conf
samba-tool user show <SERVICE-ACCOUNT NAME>
```

- Copy `resolvers_users.json` to `.` (current directory)
- Edit `resolvers_users.json`:
  - Set the base-DN of your user-accounts in `LDAPBASE`
  - Set the DC hostnames in `LDAPURI`
  - Set the DN of the SERVICE-ACCOUNT in `BINDDN`
  - Set the password of the SERVICE-ACCOUNT in `BINDPW`
  - Optionally change the `TLS_VERSION` (default is 2), 2=TLSv1.3,  5=TLSv1.2,  4=TLSv1.1,  3=TLSv1.0

```bash
# If not set already:
ADMIN_PASSWORD="<ADMIN_PASSWORD>"
BASE_URL="'https://<YOUR SERVER FQDN>/pi"
DOMAIN="$(dnsdomainname)"

# Authenticate with the admin user
TOKEN="$(curl -s --request POST \
     --header "Content-Type: application/json" \
     --data "{\"username\": \"admin\", \"password\": \"${ADMIN_PASSWORD}\"}" \ 
     "${BASE_URL}/auth" |
    jq -M '.result.value.token' | sed 's/\"//g')"     

# Create resolver for Samba (set backend to ldap)
curl -s --request POST \
    --header "Authorization: ${TOKEN}" \
    --header "Content-Type: application/json" \
    --data @resolvers_users.json \
    "${BASE_URL}/resolver/users_${DOMAIN}" 

# Create realm (users are in realms: 'user@realm')
curl -s --request POST \
    --header "Authorization: ${TOKEN}" \
    --header "Content-Type: application/json" \
    --data "{\"resolvers\": \"users_${DOMAIN}\", \"priority.users_${DOMAIN}\": 1}" \ 
    "${BASE_URL}/realm/${DOMAIN}" 

# Set the default realm (users in default realm can login without specifying the realm)
curl -s --request POST \
    --header "Authorization: ${TOKEN}" \
    "${BASE_URL}/defaultrealm/${DOMAIN}" 
```

The connection between Privacyidea and Samba is made. Users can login on Privacyidea with their domain user-id and password.

### Next steps:

- You probably want to setup a user selfservice policy, so that users can create MFA tokens of your choice.
- Setup policies for services to authenticate against Privacyidea
- Setup Privacyidea authentication in services that require MFA login


The Privacyidea manual is [here](https://privacyidea.readthedocs.io/en/latest/index.html)
