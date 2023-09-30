# More Windows-like sysvol and LDAP permissions

**DISCLAIMER: Use of anything provided here is at you own risk!**

Reasons:
- With these settings Windows will not change permissions when it manages files on sysvol.
- GPOs can be managed from Windows by members of `Group Policy Creator Owners` instead of `Domain Admins`, which means login for `Domain Admins` can be disabled on Windows clients.  

NOTE: Never run `samba-tool ntacl sysvolreset` because it will reset all filesystem ACLs to Samba's default and hence undo the changes described here.


# Setup

Setup instructions are written for a Debian server.

Ensure your sysvol replication does not execute `samba-tool ntacl sysvolreset`!

Steps:
- Update DS-ACLs on the GPO container object to allow GPO creation by members of `Group Policy Creator Owners`
- Update filesystem ACLs on sysvol to allow members of `Group Policy Creator Owners` to update netlogon scripts, admx files and create GPOs.

## Change DS-ACL of GPO container object

**This setup should be executed on ONE of the Samba-DCs**, replication will take care of the others.


Apply DC-ACLs to `CN=Policies,CN=System,${BASE_DN}`:

```bash
BASE_DN="DC=$(dnsdomainname | sed 's/\./,DC=/g')"

cat << EOF > /tmp/gpo_dsacl.acls
O:DAG:DAD:ARAI
(A;;RPWPCRCCDCLCLORCWOWDSDDTSW;;;DA)
(A;;RPWPCRCCDCLCLORCWOWDSDDTSW;;;SY)
(A;;RPLCLORC;;;AU)
(OA;;CC;f30e3bc2-9ff0-11d1-b603-0000f80367c1;;PA)
(A;CIID;RPWPCRCCDCLCLORCWOWDSDDTSW;;;EA)
(A;CIID;LC;;;RU)
(A;CIID;RPWPCRCCLCLORCWOWDSDSW;;;BA)
(OA;CIIOID;RP;4c164200-20c0-11d0-a768-00aa006e0529;4828cc14-1437-45bc-9b07-ad6f015e5f28;RU)
(OA;CIIOID;RP;4c164200-20c0-11d0-a768-00aa006e0529;bf967aba-0de6-11d0-a285-00aa003049e2;RU)
(OA;CIIOID;RP;5f202010-79a5-11d0-9020-00c04fc2d4cf;4828cc14-1437-45bc-9b07-ad6f015e5f28;RU)
(OA;CIIOID;RP;5f202010-79a5-11d0-9020-00c04fc2d4cf;bf967aba-0de6-11d0-a285-00aa003049e2;RU)
(OA;CIIOID;RP;bc0ac240-79a9-11d0-9020-00c04fc2d4cf;4828cc14-1437-45bc-9b07-ad6f015e5f28;RU)
(OA;CIIOID;RP;bc0ac240-79a9-11d0-9020-00c04fc2d4cf;bf967aba-0de6-11d0-a285-00aa003049e2;RU)
(OA;CIIOID;RP;59ba2f42-79a2-11d0-9020-00c04fc2d3cf;4828cc14-1437-45bc-9b07-ad6f015e5f28;RU)
(OA;CIIOID;RP;59ba2f42-79a2-11d0-9020-00c04fc2d3cf;bf967aba-0de6-11d0-a285-00aa003049e2;RU)
(OA;CIIOID;RP;037088f8-0ae1-11d2-b422-00a0c968f939;4828cc14-1437-45bc-9b07-ad6f015e5f28;RU)
(OA;CIIOID;RP;037088f8-0ae1-11d2-b422-00a0c968f939;bf967aba-0de6-11d0-a285-00aa003049e2;RU)
(OA;CIIOID;RP;b7c69e6d-2cc7-11d2-854e-00a0c983f608;bf967a86-0de6-11d0-a285-00aa003049e2;ED)
(OA;CIIOID;RP;b7c69e6d-2cc7-11d2-854e-00a0c983f608;bf967a9c-0de6-11d0-a285-00aa003049e2;ED)
(OA;CIIOID;RP;b7c69e6d-2cc7-11d2-854e-00a0c983f608;bf967aba-0de6-11d0-a285-00aa003049e2;ED)
(OA;CIIOID;RPLCLORC;;4828cc14-1437-45bc-9b07-ad6f015e5f28;RU)
(OA;CIIOID;RPLCLORC;;bf967a9c-0de6-11d0-a285-00aa003049e2;RU)
(OA;CIIOID;RPLCLORC;;bf967aba-0de6-11d0-a285-00aa003049e2;RU)
(OA;CIID;RPWPCR;91e647de-d96f-4b70-9557-d63ff4f3ccd8;;PS)
(OA;CIID;RP;f30e3bbe-9ff0-11d1-b603-0000f80367c1;;PA)
(OA;CIID;RP;f30e3bbf-9ff0-11d1-b603-0000f80367c1;;PA)
(OA;CIID;WP;f30e3bbe-9ff0-11d1-b603-0000f80367c1;;PA)
(OA;CIID;WP;f30e3bbf-9ff0-11d1-b603-0000f80367c1;;PA)
S:AI
(OU;CIIOIDSA;WP;f30e3bbe-9ff0-11d1-b603-0000f80367c1;bf967aa5-0de6-11d0-a285-00aa003049e2;WD)
(OU;CIIOIDSA;WP;f30e3bbf-9ff0-11d1-b603-0000f80367c1;bf967aa5-0de6-11d0-a285-00aa003049e2;WD)
EOF

cat << EOF > /tmp/gpo_dsacl.ldif
dn: CN=Policies,CN=System,${BASE_DN}
changetype: modify
replace: nTSecurityDescriptor
nTSecurityDescriptor: $(cat /tmp/gpo_dsacl.acls | tr -d '\n')
EOF

ldbmodify -H /var/lib/samba/private/sam.ldb /tmp/gpo_dsacl.ldif

rm /tmp/gpo_dsacl.ldif /tmp/gpo_dsacl.acls
```

## Change filesystem ACLs

**This setup should be executed on ALL Samba-DCs**

Filesystem replication with rsync, osync or other will only synchronize changed files, ACL-changes are generally not detected as file changes.


The setup uses Posix-ACLs which have fewer options then NT-ACLs, there are pros and cons to this approach:
- Pro: readability: the ACL specification is much easier to understand in Linux then the specification of NT-ACLs
- Con: fewer options: Windows would set the owner of the sysvol directory to the `Domain Admins` group, this is not possible with Linux' native tools.

The compromise is to set ownership of the sysvol directory to `root` (which equals to the domain administrator) instead of `Domain Admins`.


Apply filesystem ACLs to the main directories of sysvol:

```bash
NETBIOS_DOMAIN="$(dnsdomainname | awk -F '.' '{print toupper($1)}')"
DNS_DOMAIN="$(dnsdomainname)"
DIRS="/var/lib/samba/sysvol/${DNS_DOMAIN} /var/lib/samba/sysvol/${DNS_DOMAIN}/scripts /var/lib/samba/sysvol/${DNS_DOMAIN}/Policies"
    
for DIR in $DIRS; do
    cat << EOF > /tmp/sysvol_dirs.acls
# file: ${DIR}
# owner: root
# group: BUILTIN\\administrators
user::rwx
user:NT Authority\\system:rwx
user:NT Authority\\authenticated users:r-x
user:${NETBIOS_DOMAIN}\\enterprise admins:rwx
user:${NETBIOS_DOMAIN}\\group policy creator owners:rwx
user:NT Authority\\enterprise domain controllers:r-x
user:${NETBIOS_DOMAIN}\\domain computers:r-x
group::rwx
group:NT Authority\\system:rwx
group:NT Authority\\authenticated users:r-x
group:${NETBIOS_DOMAIN}\\domain admins:rwx
group:${NETBIOS_DOMAIN}\\enterprise admins:rwx
group:${NETBIOS_DOMAIN}\\group policy creator owners:rwx
group:NT Authority\\enterprise domain controllers:r-x
group:${NETBIOS_DOMAIN}\\domain computers:r-x
mask::rwx
other::---
default:user::rwx
default:user:NT Authority\\system:rwx
default:user:NT Authority\\authenticated users:r-x
default:user:${NETBIOS_DOMAIN}\\domain admins:rwx
default:user:${NETBIOS_DOMAIN}\\enterprise admins:rwx
default:user:${NETBIOS_DOMAIN}\\group policy creator owners:rwx
default:user:NT Authority\\enterprise domain controllers:r-x
default:user:${NETBIOS_DOMAIN}\\domain computers:r-x
default:group::---
default:group:NT Authority\\system:rwx
default:group:NT Authority\\authenticated users:r-x
default:group:${NETBIOS_DOMAIN}\\domain admins:rwx
default:group:${NETBIOS_DOMAIN}\\enterprise admins:rwx
default:group:${NETBIOS_DOMAIN}\\group policy creator owners:rwx
default:group:NT Authority\\enterprise domain controllers:r-x
default:group:${NETBIOS_DOMAIN}\\domain computers:r-x
default:mask::rwx
default:other::---
EOF
    setfacl --set-file=/tmp/sysvol_dirs.acls ${DIR}

done
rm /tmp/sysvol_dirs.acls
```

Propagate ACLs on sysvol/scripts and sysvol/Polices/PolicyDefinitions down on all files and subdirectories:

- Copy the script `set_sysvol_acls` to `/usr/local/sbin`
- Make it executable `chmod 0750 /usr/local/sbinset_sysvol_acls`
- Run it: `set_sysvol_acls`

From now on members of `Group Policy Creator Owners` can create GPOs. Existing GPOs created by `Domain Admins` should be
must be updated by a domain admin to allow `Group Policy Creator Owners` members.

The permissions on current GPOs are left as they are. When GPOs are filtered to AD-groups the permissions cannot
be predicted and therefore it is better not to touch them. Either create custom scripts or use `gpmc.msc` in Windows 
to set the GPO permissions. `set_sysvol_acls` does change the ACLs on subdirectories in GPOs, it will read the permisions 
on toplevel of a GPO and propagate them down on the content.
