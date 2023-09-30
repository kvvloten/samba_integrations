# AD-integrated Postfix, Dovecot, SOGO mailserver


**DISCLAIMER: Use of anything provided here is at your own risk!**

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

The setup of the DMZ server is covered elsewhere shortly.

## Setup

Setup instructions are written for a Debian Bullseye server.


Assumptions:
- User accounts are administrated in Samba-AD.
- Users use `sAMAccountName` to login (i.e. not `mail` nor `userPrincipalName`).
- Samba-AD has a (nested-) group `PERMISSION-GROUP` that contains users with permission to use generic email resources, such as SOGO.
- Apache2 is setup on the mailserver and has a TLS enabled vhost ready to use. 
- Postgresql is available in the domain and is ready to host the SOGO database. 
- Each service will use its own service-account to connect to Samba-AD.
- A DMZ mail-relay server and Apache reverseproxy server is available to pass mail traffic to and from the Internet providers smart-host.
- The Internet provider takes care of spamfiltering and mail-signing (DKIM, SPF, etc.)


The setup involves:
1. Samba-AD user and group preparations
2. Postfix 
3. Dovecot 
4. Pigeonhole
5. Rspamd 
6. SOGO
7. SOGO-EAS

The aim is to be able to automate everything. Therefore manual actions, especially in UIs, are avoided. 
The instructions below are an extracted from Ansible code.

Setup of AD-integrated Dovecot (and Postfix) and SOGO (Webmail, CalDav/CardDav and Active-Sync server) will be covered elsewhere.


## Setup steps

### 1. Samba-AD user and group preparations

No schema modification to Samba-AD are required. 
Instead, existing attributes are used (or call it abused) to store the required information.

Thunderbird MailConfig (MCD) uses the same attributes for client configuration (see [Thunderbird automatic configuration from Samba-AD](../thunderbird_config/README.md).

#### User object
Attributes in the table have a special meaning to Postfix and/or Dovecot

| attribute                      | single | purpose                                              |
|--------------------------------|--------|------------------------------------------------------|
| mail                           | 1      | domain mail address                                  |
| proxyAddresses                 | 0      | all personal mailboxes                               |
| url                            | 0      | all mail-aliases on all personal mailboxes           |
| otherMailbox                   | 0      | default mail address (the default identity in TB)    |
| primaryTelexNumber             | 1      | enable mailconfig: mailconfig=true, mailconfig=false |
| primaryInternationalISDNNumber | 1      | collected_addressbook=<ID>  (addressbook-ID in SOGO) |

Single indicates whether the attribute can store one value or multiple.

The attribute `mail` stores the domain mail-address, i.e. <user>@<ad-domain>, this is probably an internal address not usable on the internet.
`proxyAddresses` is the attribute used for all external (internet) mailboxes a user has. 

The attributes `primaryInternationalISDNNumber` and `primaryTelexNumber` are used by MailConfig, check [Thunderbird automatic configuration from Samba-AD](../thunderbird_config/README.md)


#### Group object, Mail - shared mailbox
The name of a group for a shared-mailbox (`samAccountName`) should start with `mail_box-` to be recognized as a shared-mailbox. 


| attribute       | single | purpose                                      |
|-----------------|--------|----------------------------------------------|
| displayName     | 1      | human readable name - used in mail-signature |
| mail            | 1      | mailbox address                              |
| member          | 0      | mailbox users                                |
| proxyAddresses  | 0      | duplicate mail to these internal addresses   |
| info            | 1      | mail-signature organization name             |
| telephoneNumber | 1      | mail-signature phone number                  | 

The attributes `info` and `telephonNumber` are used by MailConfig, check [Thunderbird automatic configuration from Samba-AD](../thunderbird_config/README.md)


#### Group object, Mail - distribution list
The name of a group for a distribution list (`samAccountName`) should start with `mail_ist-` to be recognized as a mail distribution list. 

| attribute   | single | purpose                    |
|-------------|--------|----------------------------|
| displayName | 1      | human readable name        |
| mail        | 1      | mail address of the list   |
| member      | 0      | domain members of the list |
| description | 1      | scope=internal,global      |

`description` should contain a string: `scope=internal|global`, it determines whether the distribution list can be 
addressed from the internet (global) or just within the domain (internal). 
This can be used to prevent a list like `everyone@mydomain.com` to be accessible from outside.


### 2. Postfix

### 3. Dovecot 

### 4. Pigeonhole

### 5. Rspamd 

### 6. SOGO

### 7. SOGO-EAS
