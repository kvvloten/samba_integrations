# Integrations with Samba Active Directory

**DISCLAIMER: Use of anything provided here is at you own risk!**

## Topics

### Authentication

- Anonymous LDAP-proxy - Access to Samba-LDAP for legacy devices
- Privacyidea - multifactor- authentication and token authentication on top of Samba-AD
    - Openvpn-privacyidea - multifactor-authentication for OpenVPN
    - Ssh-privacyidea - split brain authentication for SSH: multifactor-authentication for internet access and default authentication for local network access
- Password-notifier - cron script to send notification mails on soon expiring passwords
- Self-service-password - self-service password change web-interface
- Apache-Kerberos+Basic-auth - Apache with Kerberos and Basic authentication fallback to Samba-AD
- Enterprise-WIFI - Automatically connect to company wifi with AD machine credentials before users login

More details are in [README](authentication/README.md)

### Domain-controller

- Operations scripts - set of simple scripts to ease the life of a system operator
- DC-Manage scripts - scripts to check and manage aspects of the domain-controller
- Sysvol permissions - alternative set of sysvol and LDAP permissions to be more Windows alike and to allow full management of GPOs by members of `Group Policy Creator Owners`
- GPO-from-JSON - generate GPOs from source files in JSON (and vice-versa)

More details are in [README](domain_controller/README.md)

### Fileserver

- Fileserver-search - everything required to use Spotlight search on a Samba fileserver

More details are in [README](fileserver/README.md)

### Mail

- Thunderbird-config - fully automated configuration for Thunderbird in the AD-domain

More details are in [README](mail/README.md)
