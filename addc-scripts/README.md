# Cron and management scripts for Samba-AD controllers

**DISCLAIMER: Use of anything provided here is at your own risk!**

**This setup should be executed on ALL Samba-DCs**

## Setup

Setup instructions are written for a Debian server.

- Copy all scripts to `/usr/local/sbin` 
- Download two required scripts directly from the Samba repository and put them in `/usr/local/sbin`
    - https://gitlab.com/samba-team/samba/-/raw/master/source4/scripting/devel/chgtdcpass
    - https://gitlab.com/samba-team/samba/-/raw/master/source4/scripting/devel/chgkrbtgtpass

- Make all scripts executable:

```bash
cd /usr/local/sbin
chmod 0750 *
```

All scripts must be run as `root` and `/usr/local/sbin` enforces that 

## Cron scripts

### dc_password_change

Update the DC machine account and the kerberos-tgt password monthly.

Dependencies:
- `chgtdcpass`
- `chgkrbtgtpass`
- `has_fsmo_roles`

Schedule in cron-monthly:

```bash
cat << EOF > /etc/cron.monthly/dc_password_change
/usr/local/sbin/dc_password_change > /dev/null 2>&1
EOF
chmod +x /etc/cron.monthly/dc_password_change
```

### samba_check_db_replication

Check Samba database replication daily. 

Edit the `/usr/local/sbin/samba_check_db_replication`:
- Set the domain-admin password in `SAMBA_NT_ADMIN_PASS`
- Set a mail-address in `EMAIL_REPORT_ADDRESS`, replication issues will be reported here
- Set `CONFIGURED` to `yes` 

Schedule in cron-daily:

```bash
cat << EOF > /etc/cron.daily/samba_check_db_replication
/usr/local/sbin/samba_check_db_replication > /dev/null 2>&1
EOF
chmod +x /etc/cron.daily/samba_check_db_replication
```

### special_users_auto_lock

Lock (disable) users which are members of a specified group when the script is run.

Dependencies:
- `has_fsmo_roles`

Edit the `/usr/local/sbin/special_users_auto_lock`:
- Set the auto-lock group-name in `AUTOLOCK_GROUP`

Schedule in cron-daily:

```bash
cat << EOF > /etc/cron.daily/special_users_auto_lock
/usr/local/sbin/special_users_auto_lock > /dev/null 2>&1
EOF
chmod +x /etc/cron.daily/special_users_auto_lock
```

Every day at midnight all users in the specified group are disabled. 
This is useful for sensitive accounts such as Administrators to ensure they can only be used when explicitly enabled and only for one day.


## Management scripts

### User information

#### cat_user_account_control

Decodes the account-control field of a user or computer.

Usage: `cat_user_account_control <user|computer> <account-name>`

#### get_misconfigured_enctypes

Get all accounts with misconfigured kerberos encryption types

Do update the variable `EXPECTED_ENCTYPES` for your environment

Usage: `get_misconfigured_enctypes <user|computer>`

#### get_nested_groups

Lists all (nested) groups of a user, computer or group

Usage: `get_nested_groups <object-name> [with-gid]`

`<object-name>` the name of a user, computer or group

`with-gid` will only show results with attribute gidNumber set, this is only useful when your setup is using rfc2307

```bash
get_nexted_groups myuser
```

#### get_nested_users

Lists all (nested) users (and computers) of a group

Usage: `get_nested_groups <group-name>`

```bash
get_nexted_users mygroup
```

#### ls_user_account_expiry

Lists expiry time for user accounts matching the regular expression.

Output is reverse order (first expiring account at the end)

Usage: `ls_user_account_expiry <account-regex>`


### GPO management

#### cat_ldap_gpo

Show the three (top, machine, user) LDAP records for specified GPO. 

Usage: `cat_ldap_gpo {<UUID>}`

UUID must be encapsulated in curly brackets.

#### get_gpos

List all GPOs in LDAP: the UUID and the display name 

The list is sorted by UUID, except when `by-name` is passed, the sort order is by display name

Usage: `get_gpos [by-name]`

#### ls_ldap_gpos

Lists DN and display name of all GPO records in LDAP.  

Usage: `ls_ldap_gpos`

#### rm_ldap_gpo

Removes LDAP records of a GPO. While the filesystem part of a GPO is easy to remove with `rm`, the accompanying LDAP 
records can be removed with this script

Usage: `rm_ldap_gpo {<UUID>}`

UUID must be encapsulated in curly brackets.
