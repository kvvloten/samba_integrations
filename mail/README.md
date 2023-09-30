# Mail integrations for Samba-AD

**DISCLAIMER: Use of anything provided here is at you own risk!**


## Thunderbird fully automated configuration

The operating environment for Thunderbird in the domain:

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

Setup details are in [README](thunderbird_config/README.md) 
