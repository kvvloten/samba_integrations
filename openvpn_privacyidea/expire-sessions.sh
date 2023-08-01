#!/bin/bash
# Path is not set when we run from cron
export PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin

TWELVEHOURS_EPOCH=$(( $(date -d yesterday +%s) + 43200 ))

function expire_clients
{
    local status_file=$1
    local management_port=$2
    local clients
    local session_start_time
    local session_start_epoch
    clients="$(awk -F, '
                BEGIN{ start = 0 }
                { if( $1 == "ROUTING TABLE" ){ exit }
                  if( start == 1 ){ print $1 }
                  if( $1 == "Common Name" ){ start = 1 }
                }' "/etc/openvpn/${status_file}" )"

    for client in ${clients}; do
        session_start_time="$(awk -F, "/^${client}/{print \$5}" "/etc/openvpn/${status_file}")"
        session_start_epoch="$(date -d "${session_start_time}" +%s)"
        if [[ ${session_start_epoch} -lt ${TWELVEHOURS_EPOCH} ]]; then
            logger "openvpn-session-expire: VPN session of ${client} started at ${session_start_time} has expired, closing now."
            echo -e "kill ${client}\nquit\n" | nc localhost "${management_port}"
        fi
    done
}

expire_clients openvpn-status-password.log 7504
