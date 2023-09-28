# Thunderbird automatic configuration from Samba-AD

**DISCLAIMER: Use of anything provided here is at your own risk!**

The operating environment for described configuration:

```text
  ___________________       Kerberos         _______________ 
 |  Windows 10       | <------------------> |               |
 |  Domain-member    |                      |  Samba AD-DC  |
 |  _______________  |   Thunderbird GPO    |               | <--+
 | |               | | <------------------- |               |    |
 | |               | |  (generic settings)   ---------------     | LDAP-query
 | |  Thunderbird  | |                       _______________     | 
 | |               | |   Thunderbird MCD    |               |    |
 | |               | | <------------------- |  MailConfig   | ---+
 |  ---------------  |  (account settings)  |               |
  -------------------                        ---------------
      |  | |  | |
      |  | |  | |    Imap4   ----------- -----------
      |  | |  | +---------> |           |           |
      |  | |  | Submission  |  Dovecot  |  Postfix  |
      |  | |  +-----------> |           |           |
      |  | |                 ----------- -----------
      |  | |        CalDav   ___________
      |  | +--------------> |           |
      |  |         CardDav  |   SGOO    |                                          
      |  +----------------> |           |               __________________         
      |                      -----------               | DMZ-server       |            __   _    
      |                      _______________           |  ______________  |          _(  )_( )_  
      |    FileLink WebDav  |               |          | | Apache       | |         (          ) 
      +-------------------> | Apache WebDav | <------- | | ReverseProxy | | <----- (  INTERNET  )
                            |               |          |  --------------  |         (_   _    _) 
                             ---------------            -----------------             (_) (__)   
```

## Setup

Setup instructions are written for a Debian Bullseye server.


Assumptions:
- User accounts are administrated in Samba-AD.
- Users use `sAMAccountName` to login (i.e. not `mail` nor `userPrincipalName`).
- Users authenticate with their Kerberos-ticket whenever possible (TB addons cannot use Kerberos, hence Filelink uses a password).
- Samba-AD has a (nested-) group `PERMISSION-GROUP` that contains users with permission to use generic email resources, such as Apache + MCD, Apache WebDav, SOGO.
- Apache2 is setup on the mailconfig / filelink server and on the dmz-server and has a TLS enabled vhost ready to use. 
- Each service will use its own service-account to connect to Samba-AD.
- Dovecot (and Postfix) and SOGO are set up and available.

In order to generate GPOs from json Samba >= 4.19.0 is required!

Due to the use of Kerberos for authentication no passwords need to be stored in Thunderbird, this prevents account-lockups after a password change. 
As a result the user can authenticate only with his/her personal account to the mail-server, i.e. all personal-, delegated- and shared-mailboxes should be presented under this account in Thunderbird.
This leads to configuration on the mail-server side, in Samba-AD and on the Thunderbird client side.

 
The setup involves:
1. Samba-AD user and group preparations
2. Client side configuration on Windows
3. Group Policy Object (GPO) for Thunderbird containing generic settings and addon management 
4. MailConfig, MCD on Apache connected to Samba-AD containing all account and user specific settings
5. FileLink, Apache Webdav connected to Samba-AD 
6. Apache ReverseProxy for access by the mail recipient of files stored by FileLink on Apache WebDav
7. Manual FileLink settings in Thunderbird 

The aim is to be able to automate everything, therefore manual actions, especially in UIs are avoided. 
The instructions below are an extracted from Ansible code.

Setup of AD-integrated Dovecot (and Postfix) and SOGO (Webmail, CalDav/CardDav and Active-Sync server) will be covered elsewhere.


## Setup steps

### 1. Samba-AD user and group preparations

No schema modification to Samba-AD are required. 
Instead, existing attributes are used (or call it abused) to store the required information.

Postfix and Dovecot can use the same attributes to distribute and deliver email.

## User object
Attributes in the table have a special meaning to MailConfig

| attribute                      | single | purpose                                              |
|--------------------------------|--------|------------------------------------------------------|
| mail                           | 1      | domain mail address                                  |
| proxyAddresses                 | 0      | all personal mailboxes                               |
| url                            | 0      | all mail-aliases on all personal mailboxes           |
| otherMailbox                   | 0      | default mail address (the default identity in TB)    |
| primaryTelexNumber             | 1      | enable mailconfig: mailconfig=true, mailconfig=false |
| primaryInternationalISDNNumber | 1      | collected_addressbook=<ID>  (addressbook-ID in SOGO) |

Single indicates whether the attribute can store one value or multiple.

The attribute `mail` stores the domain mail-address, i.e. <user>@<ad-domain>, this is probably an internal address not usable on the internet.
`proxyAddresses` is the attribute used for all external (internet) mailboxes a uses has. 

`primaryInternationalISDNNumber` should contain a string `collected_addressbook=<ID>`, this allows Thunderbird to store collected addresses on the SOGO Carddav server.

`primaryTelexNumber` should contain a string: `mailconfig=true|false` to allow per user enable/disable of MailConfig, 
do note that this attribute is only relevant when MailConfig is configured to use it.

## Group object, Mail - shared mailbox
The name of a group for a shared-mailbox (`samAccountName`) should start with `mail_box-` to be recognized as a shared-mailbox. 


| attribute       | single | purpose                                      |
|-----------------|--------|----------------------------------------------|
| displayName     | 1      | human readable name - used in mail-signature |
| mail            | 1      | mailbox address                              |
| member          | 0      | mailbox users                                |
| info            | 1      | mail-signature organization name             |
| telephoneNumber | 1      | mail-signature phone number                  | 

Do not set `proxyAddresses` as it is used for other purposes (by Dovecot, check that manual when it becomes available)


### 2. Client side configuration on Windows

Install Thunderbird on Windows using Chocolatey

```powershell
# Install Chocolatey 
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
# Install TB
choco install thunderbird --version 102.13.0
```

Make Thunderbird query MailConfig on application startup:

- Copy `client_side/local-settings.js` to `C:\Program Files\Mozilla Thunderbird\defaults\pref\local-settings.js`
- Copy `client_side/mailconfig.cfg` to `C:\Program Files\Mozilla Thunderbird\mailconfig.cfg`
- Edit `C:\Program Files\Mozilla Thunderbird\mailconfig.cfg`
  - Replace `<MAILCONFIG_FQDN>`with the name of your mailconfig server


### 3. Group Policy Object (GPO) for Thunderbird

All generic settings and Thunderbird Addons to install or remove will be configured through a GPO.

The advantage of a GPO over MailConfig (MCD) is that it is much better documented and maintained.


Find the data of an Addon to use in a GPO:
- Lookup the Addon in Firefox at https://addons.thunderbird.net/nl/thunderbird/
- Download the Addon XPI via firefox, open it in a zipfile viewer and open manifest.json to find `applications.gecko.id` 
- The URL of the XPI is used in GPO keyname `"Software\\Policies\\Mozilla\\Thunderbird\\Extensions\\Install"`
- The `applications.gecko.id` is used in `"Software\\Policies\\Mozilla\\Thunderbird\\Extensions\\Locked"` and also in `"Software\\Policies\\Mozilla\\Thunderbird\\Extensions\\Uninstall"`


Here we create a GPO from a json file on a Samba-DC server. In order for this to work you need Samba >= 4.19.0 on the DCs.

Run the instructions on one of the DCs:

```bash
# On one of the DCs:
apt-get install tofrodos curl unzip

mkdir -p /opt/samba/policies/thunderbird
mkdir /opt/samba/admx
cd /opt/samba/admx
# Put the admx files in place
curl -o thunderbird.zip https://github.com/thundernest/policy-templates/archive/refs/heads/master.zip
unzip -d thunderbird thunderbird.zip
cp policy-templates-master/templates/esr91/windows/thunderbird.admx /var/lib/samba/sysvol/$(dnsdomainname)/Policies/PolicyDefinitions
cp policy-templates-master/templates/esr91/windows/en-US/thunderbird.adml /var/lib/samba/sysvol/$(dnsdomainname)/Policies/PolicyDefinitions/en-US
```

- Copy `policies/thunderbird.json` to `/opt/samba/policies/thunderbird/thunderbird.json`
- Edit `/opt/samba/policies/thunderbird/thunderbird.json`
  - Replace `<DOMAIN NAME>` with your domain name to allow Kerberos authentication within the domain
  - Open `polices/preferences.json`:
    - Change the preference to suite your needs 
    - Replace newlines (`\n`) with spaces
  - Paste the single line preferences.json at `<PASTE PREFERENCES HERE AS A SINGLE LINE>`
  - Check Addons that are installed by the GPO, they have `"keyname": "Software\\Policies\\Mozilla\\Thunderbird\\Extensions\\Install"`
  - Add Addons as you need, do not remove any of the three that are in currently there (if you do then also update MailConfig accordingly), ensure to increase the number in `"valuename"` for every Addon you add
  - It is also possible to uninstall Addons, add keys `"keyname": "Software\\Policies\\Mozilla\\Thunderbird\\Extensions\\Uninstall"` with increasing numbers in `valuename` 

Follow the steps in [gpo_from_json](../../domain_controller/gpo_from_json/README.md) to generate the GPO, use variables:
```bash
GPO_SRC_PATH="/opt/samba/policies/thunderbird"
GPO_SRC_FILE="thunderbird.json"
GPO_DISPLAY_NAME="thunderbird"
```

After this the GPO is ready and distributed to subscribed Windows machines.

### 4. MailConfig

This will set up Apache for MailConfig with Kerberos authentication. 
MailConfig is a Python WSGI-application that supplies user-configuration to Thunderbird through the MCD (Mission Control Desktop) method.   
Thunderbird will, on startup, download the user-configuration from MailConfig.

MailConfig configures:
- The user's domain mailbox (shared-mailboxes and delegated mailboxes must be presented in the shared namespace in the 
  user's mailbox, Dovecot should take care of this)  
- Mail identities and mail signatures (standardized mail-signatures for users and share-mailboxes)
- The FolderAccounts addon to ensure the proper identity is used for shared-mailboxes etc.
- Carddav addressbooks from SOGO
- Caldav calendars from SOGO
- The FileLink addon (setup is partially because not every option is available to MCD) 

MailConfig will get the user settings from Samba-AD and more generic items from a local configuration file.

- Create a service-accounts in Samba:

```bash
# On one of the DCs:
# Create a service account for MailConfig
samba-tool user create <MAILCONFIG SERVICE-ACCOUNT NAME>
samba-tool user setexpiry --noexpiry <MAILCONFIG SERVICE-ACCOUNT NAME>

# Get the DN
samba-tool user show <MAILCONFIG SERVICE-ACCOUNT NAME>
```

Continue on the MailConfig server 

- Setup Apache for Kerberos and Basic authentication, follow these [instructions](../../authentication/apache_krb5+basic-auth/README.md)  

Setup MailConfig

- Install setup a virtualenv:

```bash
apt-get install python3-pip python3-venv makepasswd libapache2-mod-wsgi-py3
a2enmod wsgi
mkdir -p /opt/mail/mailconfig
useradd -d /opt/mail/mailconfig/home -m -r -s /usr/sbin/nologin -U -G www-data wsgi-mailconfig
mkdir /opt/mail/mailconfig/venv
python3 -m venv /opt/mail/mailconfig/venv
source /opt/mail/mailconfig/venv/bin/activate
pip install pip setuptool wheel --upgrade
pip install python-ldap
mkdir /opt/mail/mailconfig/wsgi/thunderbird
mkdir /opt/mail/mailconfig/wsgi/signatures
mkdir -m 0750 /opt/mail/mailconfig/thunderbird_cache
chown wsgi-mailconfig.www-data /opt/mail/mailconfig/thunderbird_cache
```

- Copy files from `wsgi` to `/opt/mail/mailconfig/wsgi`:
  - `identities.py`
  - `ldap_support.py`
  - `mailboxes.py`
  - `mailconfig.wsgi`
  - `signature.py`
  - `thunderbird.py`
  - `config.json`

- Edit `/opt/mail/mailconfig/wsgi/config.json`
  - In section `enable`: 
    - Sending mailbox configuration by MailConfig is driven by `mailbox`, option are:
      - `disable`: disable mailbox configuration through MailConfig
      - `user_ldap_attribute` to check the MailConfig attribute of the user in LDAP before sending mailbox configuration
      - `domain` enable mailbox configuration for all domain users   
    - Sending mailbox configuration by MailConfig is driven by `settings`, option are:
      - `disable`: disable other TB settings through MailConfig
      - `user_ldap_attribute` to check the MailConfig attribute of the user in LDAP before sending other TB settings
      - `domain` enable other TB settings for all domain users
  - In section `ldap`: 
    - Set DC hostnames in `<YOUR 1ST DC-SERVER>` and `<YOUR 2ND DC-SERVER>`
    - Set the base-DN of your user-accounts and groups in `<BASE_DN>`
    - Set DN of the SERVICE-ACCOUNT for apache in `<SERVICE-ACCOUNT DN>` 
    - Set password of the SERVICE-ACCOUNT in `<SERVICE-ACCOUNT PASSWORD>`
    - Optionally set the names of one or more AD groups in `external_machine_groups`, these machines (laptops) 
      use password authentication instead of Kerberos (because they may not be able to retrieve a Kerberos-ticket on an external location) 
      and will always connect to `server_extern` and `url_extern`. 
      DNS views (split DNS) can make the external DNS-names also available internally.
  - In section `mail`: 
    - Set the internal mailserver FQDN in `server_intern` 
    - Set the external mailserver FQDN in `server_extern` 
    - Set your Samba-AD domain in `dns_domain` 
    - If you receive mail for multiple (external) domains and the mail-server is configured to deliver email in a per 
      domain subfolder of the inbox then set `mailbox_domain_folders` to `true`. This item is for personal mailboxes only, 
      it does not affect shared-mailbox settings. 
    - Set the maximum message size (in MB) of the mail-server in `maximum_message_size` 
    - Update `imap` and `smtp` settings as needed.
  - In section `carddav`: 
    - Update the `<IN/EXTERNAL-SOGO-FQDN>` in `url_intern` and `url_extern`
    - Set `<DOMAIN-ADDRESSBOOK-ID>` to match with `id` in `/etc/sogo/sogo.conf` in `SOGoUserSources`
    - Check and update other items to suite your needs.
  - In section `caldav`: 
    - Update the `<IN/EXTERNAL-SOGO-FQDN>` in `url_intern` and `url_extern`
    - Check and update other items to suite your needs.

- Copy files from `thunderbird` to `/opt/mail/mailconfig/wsgi/thunderbird`:
    - `folderaccount.j2`
    - `identities.j2`
    - `mailbox_domain_base.j2`
    - `mailbox_domain_settings.j2`
    - `mailbox_glue.j2`
    - `mailbox_end.j2`
    - `mailbox_start.j2`
    - `main_end.j2`
    - `main_start.j2`
    - `settings_addressbooks.j2`
    - `settings_calendar.j2`
    - `settings_filelink.j2`
    - `settings_mail.j2`

Mail signatures

Mail signatures will be generated by MailConfig for personal mailboxes as well as for shared-mailboxes

- Per mail-domain create:

```bash
# The mail domain is likely different from the Samba-AD domain, e.g. example.com
mkdir /opt/mail/mailconfig/wsgi/signatures/<MAIL-DOMAIN> 
mkdir /opt/mail/mailconfig/wsgi/signatures/<MAIL-DOMAIN>/files 

# Create a html Jinja2 template, here is a very simple example
cat > /opt/mail/mailconfig/wsgi/signatures/<MAIL-DOMAIN>/signature.html.j2 << EOF
<html>
  <head>
    <meta http-equiv="content-type" content="text/html">
  </head>
  <body>
    Kind regards,<br>
    <br>
    {{ fullname }}<br>
    {% if job_title is defined %}{{ job_title }}<br>{% endif %}
    <br>
{% if phone is defined %}
    <b>T&nbsp;&nbsp;</b>{{ phone }}<br/>
{% endif %}
{% if mobile is defined %}
    <b>M&nbsp;&nbsp;</b>{{ mobile }}<br/>
{% endif %}
    <b>E&nbsp;&nbsp;</b><a href="mailto:{{ mail_address }}"><b>{{ mail_address }}</b></a>
  </body>
</html>
EOF
```
  Available Jinja2 variables are:
  - `mail_address`: the mail-address of the mailbox
  - `fullname`: LDAP attribute `displayName` for the user or the shared-mailbox
  - `job_title`: LDAP attribute `title` (optional)
  - `phone`: LDAP attribute `telephoneNumber`(optional)
  - `mobile` LDAP attribute `mobile` (optional)
  - `picture_link_to['<FILENAME>')`: refers to an image file in the `files` subdirectory, dots (`.`) in the `<FILENAME>` must be replaced with underscores (`_`)   

  Optional attributes are unavailable if not set in LDAP, hence the should be surrounded by `{% if <attr> is defined %} ... {% endif %}`

  Images:
  - Should be stored in `/opt/mail/mailconfig/wsgi/signatures/<MAIL-DOMAIN>/files`
  - Should not exceed 64kB in size (smaller is better)
  - The filename should not contain underscores (`_`)
  - A link to your website can be inserted with: `<a href="http://www.example.com/"><img alt="example" src="{{ picture_link_to['logo_png'] }}"></a>`
  - Images will be base64 encoded and provided inline in the signature

Add MailConfig to Apache

- Copy `apache.conf` to `/etc/apache2/conf-availble/mailconfig.conf`
- Update the vhost conf file, after the line `Include /etc/apache2/conf-available/vhost_krb5.conf` add 
  a line `Include /etc/apache2/conf-available/mailconfig.conf`
- Reload Apache: `systemctl reload apache2`

Test the output of MailConfig by using a browser to load your configuration, press Ctrl-U to view it properly.

In Thunderbird open the error console (Ctrl-Shift-J) to view the log output of the MailConfig javascript

If Thunderbird shows a blank left-pane with just "Local Folders", the MailConfig javascript failed to setup the account. 
Thunderbird does usually not show any errors or other output when this happens, not even the error console. 
This makes debugging particularly difficult, try commenting out pieces of the config on the server to see what happens. 

#### Extra - Create the "Collected addresses" addressbook in SOGO and put it in user LDAP record

Update `<USERNAME>`, ensure the `COLLECTED_ADDRESSBOOK_TITLE` matches with the value in `config.json` in MailConfig, then run the script

```bash
USERNAME="<USERNAME>"
COLLECTED_ADDRESSBOOK_TITLE="Collected addresses (online)"
DNS_DOMAIN="$(dnsdomainname)"
TEMPDIR="$(mktemp -d)"

sogo-tool create-folder ${USERNAME} Contacts "${COLLECTED_ADDRESSBOOK_TITLE}"
sogo-tool backup ${TEMPDIR} ${USERNAME}

COLLECTED_ADDRESSBOOK_ID="$(awk '/"\/Users\/'${USERNAME}'@'${DNS_DOMAIN}'/ {sub(/ =/,":"); print $0} /displayname = "/{sub(/;/,""); sub(/ =/,":"); print $0 "},"}' ${TEMPDIR}/${USERNAME} | \
                            awk '/"'"${COLLECTED_ADDRESSBOOK_TITLE}"'"/{print $1}' | awk -F / '{print $5}')"

echo "Collected addressbook ID: ${COLLECTED_ADDRESSBOOK_ID}"
rm -r "${TEMPDIR}"
```

Go to the DC-controller and set the `COLLECTED_ADDRESSBOOK_ID` on the user record in LDAP

```bash
USERNAME="<USERNAME>"
COLLECTED_ADDRESSBOOK_ID="<COLLECTED_ADDRESSBOOK_ID>"

BASE_DN="DC=$(dnsdomainname | sed 's/\./,DC=/g')"
USER_DN="$(ldbsearch -H /var/lib/samba/private/sam.ldb -b "${BASE_DN}" "(UID=${OBJECT})" 2> /dev/null | grep 'dn:' | cut -d ' ' -f 2-)"

cat << EOF | ldbmodify -H /var/lib/samba/private/sam.ldb
dn: ${USER_DN}
changetype: modify
replace: primaryInternationalISDNNumber
primaryInternationalISDNNumber: ${COLLECTED_ADDRESSBOOK_ID}
EOF
```


#### Extra - Load identities in SOGO 

Retrieve a user's identities and put them in SOGO. 

Update `<USERNAME>` and run the script.

```bash
USERNAME="<USERNAME>"
TEMPFILE="$(mktemp)"

/opt/mail/mailconfig/venv/bin/python3 /opt/mail/mailconfig/wsgi/identities.py -t sogo -u ${USERNAME} > ${TEMPFILE}
sogo-tool -v user-preferences set defaults ${USERNAME} "SOGoMailIdentities" -f ${TEMPFILE}
rm ${TEMPFILE}
```

#### Extra - Get mail-signatures as html files 

Write mail-signatures per identity to file.


Update `<USERNAME>`, change `OUTPUT_PATH` to suite your needs and run the script.

```bash
USERNAME="<USERNAME>"
# /home/${USERNAME} is not a path on the MailConfig server, change the script to something better
OUTPUT_PATH="/home/${USERNAME}/signatures"
TEMPFILE="$(mktemp)"

mkdir ${OUTPUT_PATH}

/opt/mail/mailconfig/venv/bin/python3 /opt/mail/mailconfig/wsgi/identities.py -t sogo -u ${USERNAME} > ${TEMPFILE}
sogo-tool -v user-preferences set defaults ${USERNAME} "SOGoMailIdentities" -f ${TEMPFILE}
ITEMS=$(jq length ${TEMPFILE})
for (( c=1; c<=${ITEMS}; c++ )); do
    SIGNATURE="$(jq -r ".[${c}].signature" ${TEMPFILE})"
    if [[ -n "${SIGNATURE}" ]]; then
        IDENTITY="$(jq -r ".[${c}].email" ${TEMPFILE})"
        echo "${SIGNATURE}" > ${OUTPUT_PATH}/${IDENTITY}
    fi
done
rm ${TEMPFILE}
```



### 5. FileLink server

FileLink is an Addon that handles attachments which ar too big to send as part of a mail message. 
The attachment size at which FileLink is triggered is part of the configuration of MailConfig.  

```bash
apt-get install apache2
a2enmod dav
a2enmod dav_fs

mkdir /etc/systemd/system/apache2.service.d
mkdir -m 0750 /etc/apache2/conf-available/include
chown www-data.www-data /etc/apache2/conf-available/include

mkdir -m 0755 /var/lib/filelink

mkdir -m 0755 /var/www/davfs
chown www-data.www-data /var/www/davfs
```

- Copy `vhost_webdav.conf` to `/etc/apache2/conf-available/vhost_webdav.conf`
- In the vhost that will contain protected websites add a line: `Include /etc/apache2/conf-available/vhost_webdav.conf`

- Copy `apache.conf` to `/etc/apache2/conf-available/filelink.conf`
- Edit `/etc/apache2/conf-available/filelink.conf`;
  - Set `LimitXMLRequestBody` to the maximum size (in bytes) of a FileLink attachment (default set to 200MB)
- Update the vhost conf file, after the line `Include /etc/apache2/conf-available/vhost_webdav.conf` add a 
  line `Include /etc/apache2/conf-available/filelink.conf`
- Reload Apache: `systemctl reload apache2`  

- Copy `filelink_cleanup` to `/etc/cron.daily/filelink_cleanup`
- Edit `/etc/cron.daily/filelink_cleanup` if you want to set RETENTION_DAYS to another value than 60 days
- Make it executable: `chmod 0755 /etc/cron.daily/filelink_cleanup`


### 6. Apache ReverseProxy to FileLink files

On an internet facing host add the following to an Apache vhost to forward FileLink request to the internal FileLink server.

- Update the vhost conf file, insert the line `Include /etc/apache2/conf-available/revproxy_filelink.conf`
- Edit the varialble `INTERNAL_FILELINK_FQDN` to point to the internal server and run the script:

```bash
INTERNAL_FILELINK_FQDN="<INTERNAL-FILELINK-FQDN>"

cat > /etc/apache2/conf-available/revproxy_filelink.conf << EOF
<Location /filelink>
    ProxyPass https://${INTERNAL_FILELINK_FQDN}/filelink
    ProxyPassReverse https://${INTERNAL_FILELINK_FQDN}/filelink
</Location>
EOF

a2enmod proxy_http
systemctl restart apache2
```


### 7. Manual FileLink settings in Thunderbird

FileLink is an Addon to Thunderbird and cannot be fully configured by MailConfig (or any other MCD implementation).

The manual steps for each user are:

- Click in the left-pane on the mailbox entry
- Click under `Set up Another Account` on `FileLink`, the `settings` Windows opens
- In the box, click on available entry `WebDAV`
- Set `Private URL` to `https://<INTERNAL-FILELINK-FQDN>/filelink/` (do add a slash (`/`) at the end)
- Set `Public URL` to `https://<EXTERNAL-FILELINK-FQDN>/filelink/` (do add a slash (`/`) at the end)
- Click on `Save`
- Close the `Settings` Window

`<INTERNAL-FILELINK-FQDN>` is the FQDN to the host where FileLink was setup in ` 5. FileLink` 

`<EXTERNAL-FILELINK-FQDN>` is the FQDN where the ReverseProxy is made available

When you want to store the first attachment on the FileLink server, Thunderbird will ask for your password. 
This is unavoidable because Addons cannot use Kerberos authentication. 
