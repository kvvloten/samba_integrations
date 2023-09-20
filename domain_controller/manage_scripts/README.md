# DC-Manage scripts for Samba-AD controllers

**DISCLAIMER: Use of anything provided here is at you own risk!**

Setup instructions are written for a Debian server.

**All of these scripts should be installed on ALL Samba-DCs**


### Change DC password monthly

On a domain-member Winbind will take care of updating the machine password regularly, 
but on a domain-controller that does not happen. This script will take fix that.

Update the DC machine account and the kerberos-tgt password monthly.

Steps:

- Copy `dc_password_change` to `/usr/local/sbin`
- Copy `has_fsmo_roles` to `/usr/local/sbin`

```bash
curl https://gitlab.com/samba-team/samba/-/raw/master/source4/scripting/devel/chgtdcpass > /usr/local/sbin/chgtdcpass
curl https://gitlab.com/samba-team/samba/-/raw/master/source4/scripting/devel/chgkrbtgtpass > /usr/local/sbin/chgkrbtgtpass

for FILE in chgtdcpass chgkrbtgtpass dc_password_change has_fsmo_roles; do
    chmod +x /usr/local/sbin/${FILE}
done
cat << EOF > /etc/cron.monthly/dc_password_change
/usr/local/sbin/dc_password_change > /dev/null 2>&1
EOF
chmod +x /etc/cron.monthly/dc_password_change
```

### Check DC replication daily

DC replication is of vital importance for a properly working domain, a daily check and notification provides a valuable warning in case of issues. 

The `samba_check_db_replication` script is a slightly modified / improved version of Louis van Belle's script.

Edit the `/usr/local/sbin/samba_check_db_replication`:
- Set the domain-admin password in `SAMBA_NT_ADMIN_PASS`
- Set a mail-address in `EMAIL_REPORT_ADDRESS`, replication issues will be reported here
- Set `CONFIGURED` to `yes` 

Schedule in cron-daily:

```bash
chmod +x /usr/local/sbin/samba_check_db_replication

cat << EOF > /etc/cron.daily/samba_check_db_replication
/usr/local/sbin/samba_check_db_replication > /dev/null 2>&1
EOF
chmod +x /etc/cron.daily/samba_check_db_replication
```

### Disable special users daily

Disable the account of members of a group when the script is run.

- Copy `has_fsmo_roles` to `/usr/local/sbin`
- Copy `special_users_auto_lock` to `/usr/local/sbin`
- Edit `/usr/local/sbin/special_users_auto_lock`:
  - Set the auto-lock group-name in `AUTOLOCK_GROUP`

```bash
chmod +x /usr/local/sbin/has_fsmo_roles
chmod +x /usr/local/sbin/special_users_auto_lock

cat << EOF > /etc/cron.daily/special_users_auto_lock
/usr/local/sbin/special_users_auto_lock > /dev/null 2>&1
EOF
chmod +x /etc/cron.daily/special_users_auto_lock
```

Every day at midnight all users in the specified group are disabled. 
This is useful for sensitive accounts such as Administrators to ensure they can only be used when explicitly 
enabled and only for one day.
