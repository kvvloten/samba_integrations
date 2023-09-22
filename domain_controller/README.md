# Domain-controller integrations

**DISCLAIMER: Use of anything provided here is at you own risk!**


## DC-Manage scripts

Some scripts to schedule on the DC to enhance its functionality.

- Change DC password monthly
- Check DC replication daily
- Disable special users daily (extra security on certain users, e.g. admins)

- More details are in [README](manage_scripts/README.md) 

## Operations scripts

Set of scripts to ease the life of an operator.

- Get all (nested) groups of a user, computer or group
- Get all (nested) users of a group
- Get user (or computer) account-control information
- Get user (or computer) account expiry information
- Get user (or computer) misconfigured (potentially weak) configured kerberos encryption types
- Get GPO information (multiple scripts)

More details are in [README](operations_scripts/README.md) 

## More Windows-like sysvol ans LDAP permissions

Reasons:
- With these settings Windows will not change permissions when it manages files on sysvol.
- No `Domain-admin` required to manage GPOs, instead members of `Group Policy Creator Owners` can   

Setup details are in [README](sysvol_permissions/README.md) 

## Generate GPOs from source files in JSON

GPOs come in a number of forms depending on their generation (implementation time). 
All of them have an LDAP component and a set of files on the sysvol share under Policies. 
The oldest generation uses utf-16 ini-files, the next generation has utf-8 xml-files and the latest incarnation uses binary regpol-files. 

GPOs from will work on the latest generation GPO files: it generates regpol-files from json. 
This makes the json source files easily portable across domains and makes it possible to store the GPO as text in a versioning system (git).  

The Samba code to manage GPOs was largely written by David Mulder, who also wrote the book ["Group Policy on Linux"](https://dmulder.github.io/group-policy-book/) with a lot of technical information about GPOs (on just for Linux). 

Setup details are in [README](gpo_from_json/README.md) 
