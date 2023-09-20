# Operation scripts for Samba-AD controllers

**DISCLAIMER: Use of anything provided here is at you own risk!**

There are two groups of scripts:
- user information retrieval
- GPO management

To install: copy all scripts to `/usr/local/sbin` and make them executable


### User information scripts

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


### GPO management scripts

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
