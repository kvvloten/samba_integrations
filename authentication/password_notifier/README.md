# Password notifier

**DISCLAIMER: Use of anything provided here is at you own risk!**

Send notification and warning mails to your users about password expiry

```text
         _____________                _______________
        |             |  LDAP-query  |               |
        |  Password   | -----------> |  Samba AD-DC  |
        |  notifier   |              |               |
        |             |              |               |
         -------------                ---------------
              |
              +--->  /usr/bin/sendmail
```


## Setup

Setup instructions are written for a Debian server.

Assumptions:

- The system must be properly configured to send mail a mail-server (MTA)
- password_notifier uses `/usr/sbin/sendmail` for sending mail, i.e. this binary must be installed

### Setup steps

- Install packages

```bash
apt-get install python3-pip python3-venv
# Required for python-ldap:
apt-get install gcc libldap2-dev libsasl2-dev python3.9-dev

mkdir /opt/password_notifier
python3 -m venv /opt/password_notifier
source /opt/privacyidea/venv/bin/activate
pip install pip setuptool wheel --upgrade 
pip install python-ldap
```

- Copy files to `/opt/password_notifier`:
  - `ldap_support.py`
  - `mail_notice.txt`
  - `mail_warning.txt`
  - `password_notifier.py`


- Create a service-account in Samba

```bash
# On one of the DCs:
samba-tool user create <SERVICE-ACCOUNT NAME>
# Ensure this account does not expire

# Get the DN and put it in slapd.conf
samba-tool user show <SERVICE-ACCOUNT NAME>
```

- Copy `config.json` to `/opt/password_notifier`
- Edit `/opt/password_notifier/config.json`:
  - Set DC hostnames in `uri`
  - Set DN of the SERVICE-ACCOUNT in `user`
  - Set password of the SERVICE-ACCOUNT in `password`
  - Set base-DN of your user-accounts in `user_dn`
  - Set sender mail-address in `mail_from`
  - Set password maximum age according to the password policy in `password_max_age`
  - Optionally change the email subjects `notice_subject` and `warning_subject`
  - Optionally change the notification days `notice_days` and `warning_days`


- Copy `cron.daily` to `/etc/cron.daily/password_notifier`
