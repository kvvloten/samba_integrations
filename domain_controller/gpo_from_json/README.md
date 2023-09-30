# Manage GPOs from source files in JSON (and vice-versa)

**DISCLAIMER: Use of anything provided here is at your own risk!**

GPOs come in a number of forms depending on their generation (implementation time). 
All of them have an LDAP component and a set of files on the sysvol share under Policies. 
The oldest generation uses utf-16 ini-files, the next generation has utf-8 xml-files and the latest incarnation uses binary regpol-files. 

GPOs from will work on the latest generation GPO files: it generates regpol-files from json. 
This makes the json source files easily portable across domains and makes it possible to store the GPO as text in a versioning system (git).  

The Samba code to manage GPOs was largely written by David Mulder, who also wrote the book ["Group Policy on Linux"](https://dmulder.github.io/group-policy-book/) with a lot of technical information about GPOs (on just for Linux). 


## Steps to create or update a GPO from JSON source file

- Create a directory `/opt/samba/policies/${GPO_NAME}` and put the JSON-file `<GPO_NAME>.json` in it 
- Set `<GPO-NAME>` in below bash code and run it

```bash
GPO_NAME="<GPO-NAME>"
SAMBA_ADMIN_PASSWORD="<ADMINISTRATOR_PASSWORD>""

GPO_SRC_PATH="/opt/samba/policies/${GPO_NAME}"
GPO_SRC_FILE="${GPO_NAME}.json"
BASE_DN="DC=$(dnsdomainname | sed 's/\./,DC=/g')"

samba-tool gpo create "${GPO_NAME}" -H /var/lib/samba/private/sam.ldb --username=administrator --password="${SAMBA_ADMIN_PASSWORD}"
# The above command can create the GPO on any DC,
#  wait until sysvol replication has made it available on the local DC, 
while [[ ! -d /var/lib/samba/sysvol/$(dnsdomainname)/Policies/${GPO_UUID} ]]; do
    sleep 30
done

GPO_UUID="$(samba-tool gpo listall -H /var/lib/samba/private/sam.ldb | \
            awk 'BEGIN{RS="\n\n";FS="\n"} $2 ~ /display name : '${GPO_NAME}'/{print $1 " : " $5}' | \
            awk -F ' : ' '{print $2}')"

GPO_VERSION="$(samba-tool gpo listall -H /var/lib/samba/private/sam.ldb | \
            awk 'BEGIN{RS="\n\n";FS="\n"} $2 ~ /display name : '${GPO_NAME}'/{print $1 " : " $5}' | \
            awk -F ' : ' '{print $4}')"

samba-tool gpo load "${GPO_UUID}" -H /var/lib/samba/private/sam.ldb \
                    --replace --content ${GPO_SRC_PATH}/${GPO_SRC_FILE} \
                    --username=administrator --password="${SAMBA_ADMIN_PASSWORD}"

# The above command can create the GPO content on any DC,
#  wait until sysvol replication has made it available on the local DC, 
while [[ ! -f /var/lib/samba/sysvol/$(dnsdomainname)/Policies/${GPO_UUID}/Machine/Registry.pol ]]; do
    sleep 30
done

GPO_VERSION_MACHINE=$(( (GPO_VERSION % 65536) + 1 ))
GPO_VERSION_USER=$(( (GPO_VERSION / 65536) + 1 ))
GPO_VERSION=$(( GPO_VERSION_USER + 65536 + GPO_VERSION_MACHINE))

cat > ${GPO_SRC_PATH}/GPT.INI << EOF
[General]
      Version=${GPO_VERSION}
      displayName=thunderbird
EOF      
todos < ${GPO_SRC_PATH}/GPT.INI > /var/lib/samba/sysvol/$(dnsdomainname)/Policies/${GPO_UUID}/GPT.INI

# The version number is stored in 2 places, in GPI.INI and in LDAP. 
#  update LDAP:
cat << EOF | ldbmodify -H /var/lib/samba/private/sam.ldb
dn: CN=${GPO_UUID},CN=Policies,CN=System,${BASE_DN}
changetype: modify
replace: versionNumber
versionNumber: ${GPO_VERSION}
EOF

samba-tool gpo setlink "${BASE_DN}" "${GPO_UUID}" -H /var/lib/samba/private/sam.ldb \
                    --username=administrator --password="${SAMBA_ADMIN_PASSWORD}"
```

The last command above links GPO to the directory BASE-DN, meaning it will be applied to any machine or user in AD. 
Best practice is to do this and apply a group to filter it to one or more groups of machines or users. 
This method provides a very fine-grained way of applying GPOs to objects (machines or users). 
It is simpeler to manage and more fine-grained than setting multiple OU links on the GPO. 

If you have not done it already, create one or more groups (`FILTER-GROUPS`) in Samba-AD add machines or users to it to 
which your GPO should be applied.

Continue setting up the group filter:

- Set `<GPO-DISPLAY-NAME>` in below bash code
- Set `<GPO_FILTER_GROUPS>` as a comma separated list of AD group-names in below bash code

```bash
GPO_NAME="<GPO-NAME>"
GPO_FILTER_GROUPS="<FILTER-GROUPS LIST>"

GPO_SRC_PATH="/opt/samba/policies/${GPO_NAME}"
GUID_GPO_LINK="f30e3bbe-9ff0-11d1-b603-0000f80367c1"
GUID_GPO_OPTIONS="f30e3bbf-9ff0-11d1-b603-0000f80367c1"
GUID_CLASS_OU="bf967aa5-0de6-11d0-a285-00aa003049e2"
GUID_CAR_APPLY_GPO="edacfd8f-ffb3-11d1-b41d-00a0c968f939"

BASE_DN="DC=$(dnsdomainname | sed 's/\./,DC=/g')"

FIRST_GROUP_SID="$(samba-tool group show $(echo "${GPO_FILTER_GROUPS}" | awk '{print $1}')  | awk '/objectSid:/{print $2}')"
NEXT_GROUP_SIDS=""
NEXT_GROUP_ACES=""
for FILTER_GROUP in $(echo "${GPO_FILTER_GROUPS}" | awk '{$1=""; print $0}'); do
    SID="$(samba-tool group show $(echo "${FILTER_GROUP}" | awk '{print $1}')  | awk '/objectSid:/{print $2}')"
    NEXT_GROUP_SIDS="${NEXT_GROUP_SIDS} ${SID}"
    NEXT_GROUP_ACES="${NEXT_GROUP_ACES} (A;CI;RPLCRC;;;${SID})"
done
# If empty set access to Domain Computers
[[ -n "${NEXT_GROUP_ACES}" ]] || NEXT_GROUP_ACES="(A;CI;RPLCRC;;;DC)" 

cat > ${GPO_SRC_PATH}/ds_acls.txt << EOF
O:DAG:DAD:PAR
(A;CI;RPWPCCDCLCLORCWOWDSDDTSW;;;DA)
(A;CI;RPWPCCDCLCLORCWOWDSDDTSW;;;EA)
(A;CIIO;RPWPCCDCLCLORCWOWDSDDTSW;;;CO)
(A;;RPWPCCDCLCLORCWOWDSDDTSW;;;DA)
(A;CI;RPWPCCDCLCLORCWOWDSDDTSW;;;SY)
(A;CI;RPLCLORC;;;ED)
(A;CI;RPLCRC;;;${FIRST_GROUP_SID})
(A;CI;RPLCRC;;;AU)
(A;CI;RPWPCCDCLCRCWOWDSD;;;PA)
$(for ACE in ${NEXT_GROUP_ACES}; do echo "${ACE})"; done)
(OA;CI;CR;${GUID_CAR_APPLY_GPO};;${FIRST_GROUP_SID})
$(for SID in ${NEXT_GROUP_SIDS}; do echo "(OA;CI;CR;${GUID_CAR_APPLY_GPO};;${SID})"; done)
S:AI
(OU;CIIOIDSA;WP;${GUID_GPO_LINK};${GUID_CLASS_OU};WD)
(OU;CIIOIDSA;WP;${GUID_GPO_OPTIONS};${GUID_CLASS_OU};WD)
EOF

cat << EOF | ldbmodify -H /var/lib/samba/private/sam.ldb
dn: CN=${GPO_UUID},CN=Policies,CN=System,${BASE_DN}
changetype: modify
replace: nTSecurityDescriptor
nTSecurityDescriptor: $(cat ${GPO_SRC_PATH}/ds_acls.txt | tr -d '\n')
EOF
```

Ensure the GPO files in the sysvol directory are at least readable for `NT Authority\\authenticated users` and 
`<NETBIOS_DOMAIN>\\domain computers:r-x` (do replace `<NETBIOS_DOMAIN>` with the AD domain name). 

Either apply the filesystem permissions in your own way or use the script below to apply Windows-like ACL in 
Posix-ACL format to the GPO.

*WARNING: `samba-tool  ntacl sysvolreset` will reset all permissions to a default and removes the group filtering permissions. 
Do not use it any longer, check [More Windows-like sysvol and LDAP permissions](../sysvol_permissions/README.md).*


```bash
GPO_NAME="<GPO-NAME>"
GPO_FILTER_GROUPS="<FILTER-GROUPS LIST>"

NETBIOS_DOMAIN="$(dnsdomainname | awk -F '.' '{print toupper($1)}')"
DNS_DOMAIN="$(dnsdomainname)"

GPO_UUID="$(samba-tool gpo listall -H /var/lib/samba/private/sam.ldb | \
            awk 'BEGIN{RS="\n\n";FS="\n"} $2 ~ /display name : '${GPO_NAME}'/{print $1 " : " $5}' | \
            awk -F ' : ' '{print $2}')"

N_GPO_FILTER_GROUPS=$(echo "${GPO_FILTER_GROUPS}" | wc -w)
cat << EOF > /tmp/sysvol_gpo_dirs.acls
# file: \{${GPO_UUID}\}
# owner: root
# group: ${NETBIOS_DOMAIN}\\domain admins
user::rwx
user:root:rwx
user:NT Authority\\system:rwx
user:NT Authority\\authenticated users:r-x
user:${NETBIOS_DOMAIN}\\domain admins:rwx
user:${NETBIOS_DOMAIN}\\enterprise admins:rwx
user:${NETBIOS_DOMAIN}\\group policy creator owners:rwx
user:NT Authority\\enterprise domain controllers:r-x
$([[ ${N_GPO_FILTER_GROUPS} -gt 1 ]] || echo "user:${NETBIOS_DOMAIN}\\domain computers:r-x") 
$(for GPO_FILTER_GROUP in ${GPO_FILTER_GROUPS}; do echo "${GPO_FILTER_GROUP})"; done)
{% for gpo_group in gposet.groups %}
user:${NETBIOS_DOMAIN}\\{{ gpo_group }}:r-x
{% endfor %}
group::rwx
group:NT Authority\\system:rwx
group:NT Authority\\authenticated users:r-x
group:${NETBIOS_DOMAIN}\\domain admins:rwx
group:${NETBIOS_DOMAIN}\\enterprise admins:rwx
group:${NETBIOS_DOMAIN}\\group policy creator owners:rwx
group:NT Authority\\enterprise domain controllers:r-x
$([[ ${N_GPO_FILTER_GROUPS} -gt 1 ]] || echo "group:${NETBIOS_DOMAIN}\\domain computers:r-x") 
{% for gpo_group in gposet.groups %}
group:${NETBIOS_DOMAIN}\\{{ gpo_group }}:r-x
{% endfor %}
mask::rwx
other::---
default:user::rwx
default:user:root:rwx
default:user:NT Authority\\system:rwx
default:user:NT Authority\\authenticated users:r-x
default:user:${NETBIOS_DOMAIN}\\domain admins:rwx
default:user:${NETBIOS_DOMAIN}\\enterprise admins:rwx
default:user:${NETBIOS_DOMAIN}\\group policy creator owners:rwx
default:user:NT Authority\\enterprise domain controllers:r-x
$([[ ${N_GPO_FILTER_GROUPS} -gt 1 ]] || echo "default:user:${NETBIOS_DOMAIN}\\domain computers:r-x") 
{% for gpo_group in gposet.groups %}
default:user:${NETBIOS_DOMAIN}\\{{ gpo_group }}:r-x
{% endfor %}
default:group::---
default:group:NT Authority\\system:rwx
default:group:NT Authority\\authenticated users:r-x
default:group:${NETBIOS_DOMAIN}\\domain admins:rwx
default:group:${NETBIOS_DOMAIN}\\enterprise admins:rwx
default:group:${NETBIOS_DOMAIN}\\group policy creator owners:rwx
default:group:NT Authority\\enterprise domain controllers:r-x
$([[ ${N_GPO_FILTER_GROUPS} -gt 1 ]] || echo "default:group:${NETBIOS_DOMAIN}\\domain computers:r-x") 
{% for gpo_group in gposet.groups %}
default:group:${NETBIOS_DOMAIN}\\{{ gpo_group }}:r-x
{% endfor %}
default:mask::rwx
default:other::---
EOF
grep '^default' /tmp/sysvol_gpo_dirs.acls | cut -d : -f 2- > /tmp/sysvol_gpo_files.acls

find /var/lib/samba/sysvol/${DNS_DOMAIN}/Policies/\{${GPO_UUID}\} -exec chown root."${NETBIOS_DOMAIN}\\domain admins" {} \;
find /var/lib/samba/sysvol/${DNS_DOMAIN}/Policies/\{${GPO_UUID}\} -type d -exec setfacl --set-file=/tmp/sysvol_gpo_dirs.acls {} \;
find /var/lib/samba/sysvol/${DNS_DOMAIN}/Policies/\{${GPO_UUID}\} -type f -exec setfacl --set-file=/tmp/sysvol_gpo_files.acls {} \;
rm /tmp/sysvol_gpo_dirs.acls
rm /tmp/sysvol_gpo_files.acls
```


At this point, the GPO is available on one of the DCs, wait until the sysvol share is replicated to the other DCs.

The result (including the group filtering) can be verified in GPMC on Windows. 

Now wait until Windows refreshes the GPOs (default 90 minutes) or run `gpupdate /force` on the Windows machine(s).


## Steps to create the JSON source file with Windows GPMC

Ensure the admx-files for the GPO you want to create are available on the sysvol share in `Policies/PolicyDefinitions`, 
as well as the adml-files in the proper language subdirectory.

On Windows open `gpmc.msc` and create a new policy, start the name with `test-` and add your settings.

When done return to the console of the DC. 

Set `<GPO-NAME>` to the name you used in `gpmc.msc`

```bash
GPO_NAME="<GPO-NAME>"

UUID="$(samba-tool gpo listall -H /var/lib/samba/private/sam.ldb 2>/dev/null | \
        awk 'BEGIN{RS="\n\n";FS="\n"} {print $1 " : " $2}' | \
        awk -F ' : ' '{print $2 " " $4}' | \
        awk '/^'${GPO_NAME}' /{print $2}')"

samba-tool gpo show "{${UUID}}"
```

Copy and paste the JSON output into a separate file (`/opt/samba/policies/<GPO-NAME>/<GPO-NAME>.json`) to be used as input for the generated GPO.

The `test-` GPO created with `gpmc.msc` is no longer necessary and can be removed.

