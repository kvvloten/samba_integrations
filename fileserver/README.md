# Fileserver integrations for Samba-AD

**DISCLAIMER: Use of anything provided here is at you own risk!**


## Spotlight for Samba fileserver

Spotlight (Apple-search) for Samba.

Apart from configuration on the fileserver, quite some other components must be setup and configured to let this work.

```text
  _____________   Spotlight     __________   Files,   ______________   Scan files    _____________ 
 |             |  query        |          |  ACLs    | Filesystem   |  + meta data  |             |
 |  Apple Mac  | ------------> |          | -------> |  File        | <------------ |  FScrawler  |   
 |             |  Filesharing  |  Samba   |          |   +          |               |             |
  -------------                |  file    |       +- |  ACL         |                -------------
                               |  server  |       |   --------------                     | 
                               |          |       |                                      | Create     
                               |          | <-----+ Spotlight ACL info                   | documents
                               |          |                                              V    
                               |          |                 ______________          ______________ 
                               |          | -------------> |  Anonymous   |        |              | 
                                ----------  Spotlight      |  Opensearch  | -----> |  Opensearch  |
                      User authnz |         query          |  proxy       |   +--- |  (Elastic7)  | 
                                  V                         --------------    |     -------------- 
                                _______________                               |    |              |
                               |               | <----------------------------+    |  Opensearch  |
                               |  Samba AD-DC  |   user authnz                     |  Dashboard   |
                               |               |                       User -----> |  (Kibana)    |
                                ---------------                        WebUI        --------------
```

Setup details are in [README](fileserver_search/README.md) 
