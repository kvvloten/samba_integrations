# Authentication integrations

**DISCLAIMER: Use of anything provided here is at you own risk!**


## Anonymous LDAP-proxy

Anonymous LDAP-proxy in front of Samba-AD is useful for older devices (e.g. printers) that cannot do LDAPS (or starttls) with modern ciphers.

```text
  Anonymous    _____________                 _______________
  LDAP-query  |  anonymous  |  LDAP-query   |               |
 -----------> |  OpenLDAP   | ------------> |  Samba AD-DC  |
              |  proxy      |               |               |
               -------------                 ---------------
```

Setup details are in [README](anonymous_ldap_proxy/README.md) 


## Privacyidea with Samba backend

Privacyidea is versatile multi-factor authentication system. When configured with Samba as backend users get MFA with their Samba user-id.

```text
  Anonymous    _____________                 _______________
  LDAP-query  |  anonymous  |  LDAP-query   |               |
 -----------> |  OpenLDAP   | ------------> |  Samba AD-DC  |
              |  proxy      |               |               |
               -------------                 ---------------
```

Setup details are in [README](privacyidea/README.md) 


## Openvpn with Privacyidea MFA and Samba authorization

OpenVPN setup with Privacyidea MFA authentication and Samba LDAP authorization based on nested group membership.

```text
  ___________              ___________ _______                  _______________  
 |           |     MFA    |           |       |    authn MFA   |               | 
 |  OpenVPN  | <========> |  Openvpn  |  Pam  | -------------> |  Privacyidea  | 
 |  client   |            |  server   |       | -+             |               | 
 |           |            |           |       |  |              ---------------  
  -----------              ----------- -------   |          LDAP     |  ^ LDAP
                                                 |          account  |  | attributes
                                                 |          validate V  |           
                                                 |              _______________  
                                                 | authz LDAP  |               | 
                                                 +-----------> |  Samba AD-DC  | 
                                                               |               | 
                                                                ---------------  
```

This requires the above 'Privacyidea' setup and has shared components with 'SSHD with Privacyidea'

Setup details are in [README](openvpn_privacyidea/README.md) 


## SSHD with Privacyidea MFA and Samba authorization (for access from internet)

SSHD split setup with Privacyidea MFA authentication and Samba LDAP authorization based on nested group membership for 
access from internet and default login for access from the local network.

```text
    __   _                  __________ _______                     _______________  
  _(  )_( )_               |          |       |       authn MFA   |               | 
 (          )     MFA      |  SSH     |  Pam  | ----------------> |  Privacyidea  | 
(  INTERNET  ) <=========> |  daemon  |       | ----+             |               | 
 (_   _    _)              |          |       |     |              ---------------  
   (_) (__)                :..........: ------      |          LDAP     |  ^ LDAP
                           :          :             |          account  |  | attributes
     ______                :          :             |          validate V  |           
    |  PC  |               :..........: ______      |              _______________  
     ------                |          |       |     | authz LDAP  |               | 
       |                   |  SSH     | Pam   |     +-----------> |  Samba AD-DC  | 
 ______|______ <========>  |  daemon  |       |                   |               | 
     |   LAN    password   |          |       |                    ---------------  
  ______                    ---------- -------                                       
 |  PC  |                                 |                     
  ------                                  +---> via nsswitch, e.g. files, systemd, winbind          
```

This requires the above 'Privacyidea' setup and has shared components with 'Openvpn with Privacyidea'

Setup details are in [README](sshd_privacyidea/README.md) 


## Password notifier

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

Setup details are in [README](password_notifier/README.md) 


## Self Service Password webinterface

Web interface to change in an LDAP directory.

```text
               ________________                          _______________
              |                |                        |               |
  User WebUI  |  Self-Service  |  LDAP password change  |  Samba AD-DC  |
  ----------> |  Password      | ---------------------> |               |
              |                |                        |               |
               ----------------                          ---------------
```

Setup details are in [README](password_notifier/README.md) 
