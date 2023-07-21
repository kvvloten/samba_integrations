# Tools and integrations for Samba-AD

Setup instructions are written for a Debian server.


## Anonymous LDAP-proxy

Anonymous LDAP-proxy in front of Samba-AD is useful for older devices (e.g. printers) that cannot do LDAPS (or starttls) with modern ciphers.

Setup details are in README [here](anonymous_ldap_proxy/README.md) 


## Cron- and management scripts for Samba-AD controllers

Cron scripts:

- Change DC password monthly
- Lock (disable) special users daily (extra security on certain users, e.g. admins)
- Check DC replication daily

Management scripts:

- Get all (nested) groups of a user, computer or group
- Get all (nested) users of a group
- Get user (or computer) account-control information
- Get GPO information (multiple scripts)

More details are the README [here](addc_scripts/README.md) 
