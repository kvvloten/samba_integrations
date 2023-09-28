# AD-integrated Postfix, Dovecot, SOGO mailserver


**DISCLAIMER: Use of anything provided here is at your own risk!**

The mailserver solution:

```text
                                            ---------------         Imap4 + Pwd
                                           |               | ------------------------> DMZ     
                                           |               |      Submission + Pwd
    -----------------                      |               | <------------------------ DMZ
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
           -     | |                  | |       Addressbooks  | |
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

 