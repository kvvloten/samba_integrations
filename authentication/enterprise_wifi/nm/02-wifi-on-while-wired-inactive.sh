#!/bin/bash
export LC_ALL=C
interface="$1"
iface_mode="$2"
iface_type="$(nmcli dev | grep "${interface}" | tr -s ' ' | cut -d' ' -f2)"
iface_state="$(nmcli dev | grep "${interface}" | tr -s ' ' | cut -d' ' -f3)"
syslog_tag="wifi-wired-exclusive"

if [ "${iface_type}" == "ethernet" ]; then
    if [[ "${iface_mode}" != "up"  ]] || [[ "${iface_state}" != "connected" ]]; then
        logger -i -t "${syslog_tag}" "Interface $interface (ethernet) is down, enabling wifi ..."
        nmcli radio wifi on
    fi
fi
