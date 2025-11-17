#!/bin/bash

set -e

NODE_IP="${NODE_IP}"
INTERFACE=$(ip -o -4 addr show | grep "${NODE_IP}" | awk '{print $2}')

if [ -z "$INTERFACE" ]; then
    echo "Error: Could not find interface with IP ${NODE_IP}"
    exit 1
fi

echo "Found interface: $INTERFACE for IP: $NODE_IP"

sed -e "s/INTERFACE_PLACEHOLDER/${INTERFACE}/g" \
    -e "s/\${KEEPALIVED_STATE}/${KEEPALIVED_STATE}/g" \
    -e "s/\${ROUTER_ID}/${ROUTER_ID}/g" \
    -e "s/\${KEEPALIVED_PRIORITY}/${KEEPALIVED_PRIORITY}/g" \
    -e "s/\${NODE_IP}/${NODE_IP}/g" \
    -e "s/\${PEER_IP}/${PEER_IP}/g" \
    -e "s/\${VIP}/${VIP}/g" \
    /etc/keepalived/keepalived.conf.template > /etc/keepalived/keepalived.conf

cat /etc/keepalived/keepalived.conf

exec keepalived -n -l -D -f /etc/keepalived/keepalived.conf
