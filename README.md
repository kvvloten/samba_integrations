# Tools and integrations for Samba-AD

**DISCLAIMER: Use of anything provided here is at you own risk!**


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
- Get user (or computer) account expiry information
- Get user (or computer) misconfigured (potentially weak) configured kerberos encryption types
- Get GPO information (multiple scripts)

More details are the README [here](addc_scripts/README.md) 

## More Windows-like sysvol permissions

Reasons:
- With these settings Windows will not change permissions when it manages files on sysvol.
- GPOs can be managed from Windows by members of `Group Policy Creator Owners` instead of `Domain Admins`, which means login for `Domain Admins` can be disabled on Windows clients.  

Setup details are the README [here](sysvol_permissions/README.md) 
