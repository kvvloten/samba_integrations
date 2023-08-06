# Setup anonymous LDAP-proxy

**DISCLAIMER: Use of anything provided here is at you own risk!**

Anonymous LDAP-proxy in front of Samba-AD is useful for older devices (e.g. printers) that cannot do LDAPS (or starttls) with modern ciphers.

Access should be restricted to those older devices with iptables or nftables.

```text
  Anonymous    _____________                 _______________
  LDAP-query  |  anonymous  |  LDAP-query   |               |
 -----------> |  OpenLDAP   | ------------> |  Samba AD-DC  |
              |  proxy      |               |               |
               -------------                 ---------------
```

## Setup

**Do not use a Samba-AD-DC server to setup the LDAP-proxy!** 

Setup instructions are written for a Debian server.

LDAP-proxy uses the same listen-por (389) as Samba and you would have to set it up on each DC and add that redundancy in 
the config of your old devices (which may not have support for multiple servers). In other words, it is much simpeler to 
install it on another machine. 

- Install packages

```bash
apt-get install slapd ldap-utils
```

- Create a service-account in Samba

```bash
# On one of the DCs:
samba-tool user create <SERVICE-ACCOUNT NAME>
# Ensure this account does not expire

# Get the DN and put it in slapd.conf
samba-tool user show <SERVICE-ACCOUNT NAME>
```

- Copy `etc_default` to `/etc/default/slapd`
- Copy `logrotate.conf` to `/etc/logrotate.d/openldap_proxy.conf`
- Copy `slapd.conf` to `/etc/ldap/slapd.conf`
- Edit the `/etc/ldap/slapd.conf`:
  - Set the base-DN in `suffix`
  - Set the DC hostnames in `uri`
  - Set the DN of the SERVICE-ACCOUNT in `binddn`
  - Set the password of the SERVICE-ACCOUNT in `credentials`

```bash
chown openldap /etc/ldap/slapd.conf
chmod 700 /etc/ldap/slapd.conf
```

- Setup iptables or nftables to allow the specific device(s), an example for nftables is in `nftables.conf`. 
  Do check and update it for your needs.

## Test

On the machine where the LDAP-proxy is installed run:

```bash
ldapsearch -x -H ldap://localhost -s sub -b "<YOUR BASE-DN>" '(samaccountname=<SERVICE-ACCOUNT NAME>)'
```

Do note that most attributes in the output are in upper-case. 
It happens because the AD-schemas are not loaded in the LDAP-proxy. 
It may look ugly but does not matter because LDAP-attributes are not case-sensitive.

Received LDAP-queries are in the log-file in `/var/log/slapd.log`
