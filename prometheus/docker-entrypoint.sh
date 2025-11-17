#!/bin/sh

set -e

envsubst '${NODE_NAME} ${NODE_IP} ${PEER_IP}' < /etc/prometheus/prometheus.yml.template > /etc/prometheus/prometheus.yml

echo "Generated prometheus.yml:"
cat /etc/prometheus/prometheus.yml

exec /bin/prometheus "$@"
