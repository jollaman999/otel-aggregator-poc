#!/bin/sh

set -e

envsubst '${NODE_IP} ${PEER_IP}' < /etc/thanos/hashrings.json.template > /etc/thanos/hashrings.json

echo "Generated hashrings.json:"
cat /etc/thanos/hashrings.json

exec "$@"
