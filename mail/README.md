# Mail integrations for Samba-AD

**DISCLAIMER: Use of anything provided here is at you own risk!**


## AD-integrated Postfix, Dovecot, SOGO mailserver

The mailserver solution:

```text
                                            ---------------         Imap4 + Pwd
                                           |        :      | ------------------------> DMZ     
                                           | Rspamd :      |      Submission + Pwd
    -----------------                      |........       | <------------------------ DMZ
   |                 |                     |               |                  
   |                 |  Imap4 + Krb5       |               +----------------
   |  Domain-member  | <------------------ |               :                |  Smtp
   |                 |  Submission + Krb5  |   Dovecot     :    Postfix     | <------> DMZ
   |  Mail-client    | ------------------> |               :                |
   |  (Thunderbird)  |                     |               +----------------
   |                 |                     |               |        \       
   |                 |                     |               |\        \ LDAP     
    -----------------                      |       ........| \        \    
                 | |                       |      : Pigeon |  \        \     -------------  
                 | |                       |      : hole   |   \ Kr5b,  +-> |             | 
                 | |                        ---------------     \ LDAP      |             | 
                 | |                         |  ^     ^          +--------> |             | 
                 | |                Trusted  |  |     | Trusted             | Samba AD-DC | 
                 | |              Imap4 and  |  |     | Sieve               |             | 
                 | |             Submission  |  |     |              LDAP   |             | 
                 | |                         |  |     |      +------------> |             | 
                 | |                         |  |     |     /   Krb5,LDAP   |             | 
                 | |                         |  |     |    /  +-----------> |             | 
                 | |                         |  |     |   /  /               -------------  
   ---------     | |    Https + Krb5   ------|--|-----|--/------
  |         |    | |    or Formlogin  |  ----V--|-----V-/-----  |   Https + authn user
  | Browser | ----------------------> | |  SOGO Webmail       | | <------------------- DMZ
  |         |    | |                  | |       Sieve rules   | |
   ---------     | |                  | |       Calendars     | |
                 | |                  | |       Addressbooks  | |
                 | |                  | |.....................| |   Https
                 | |                  | |  SOGO Active Sync   | | <------------------- DMZ
                 | |                  | |                     | |
                 | |   CalDav + Krb5  | |.....................| |   Https + authn user
                 | +----------------> | |  SOGO CalDav        | | <------------------- DMZ
                 |                    | |                     | |
                 |    CardDav + Krb5  | |.....................| |   Https + authn user
                 +------------------> | |  SOGO CardDav       | | <------------------- DMZ
                                      | |                     | |
                                      |  ------------------^--  |    
                                      | Apache webserver   |    |    
                                       --------------------|----     
                                                           V         
                                                      ------------- 
                                                     |             |
                                                     |  Postresql  |
                                                     |             |
                                                      ------------- 
```

Setup details are in [README](domain_mailserver/README.md) 


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
