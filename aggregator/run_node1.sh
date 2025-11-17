#!/bin/bash
docker compose --env-file ./env-node1 -f ./docker-compose.yaml up -d
