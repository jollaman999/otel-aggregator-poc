#!/bin/sh
set -e

envsubst '${NODE_IP} ${PEER_IP}' < /usr/local/etc/haproxy/haproxy.cfg.template > /usr/local/etc/haproxy/haproxy.cfg

exec haproxy -f /usr/local/etc/haproxy/haproxy.cfg "$@"
