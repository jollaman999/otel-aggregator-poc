# OpenTelemetry High Availability Infrastructure Documentation

## Overview

This document describes the High Availability (HA) OpenTelemetry infrastructure deployed across two nodes with automatic failover capabilities.

## Architecture Diagram

![OpenTelemetry HA Infrastructure](otel-infrastructure.png)

## Infrastructure Summary

### Node Information

| Node | IP Address | Role | Hostname |
|------|-----------|------|----------|
| Node 1 | 192.168.110.214 | MASTER | ish-otel-mid-1.novalocal |
| Node 2 | 192.168.110.119 | BACKUP | ish-otel-mid-2.novalocal |
| Virtual IP | 192.168.110.140 | Shared VIP | - |

### High Availability Components

- **Keepalived**: VRRP-based virtual IP management
  - Node 1: Priority 100 (MASTER)
  - Node 2: Priority 90 (BACKUP)
  - Router ID: 51
  - Virtual IP: 192.168.110.140

- **HAProxy**: Load balancer and traffic routing
  - OTLP HTTP endpoint: Port 4318
  - Stats endpoint: Port 8404
  - Backend: Local OTel Aggregator on port 14318

### Service Stack

Both nodes run identical service stacks with HAProxy load balancing across all services:

#### 1. OpenTelemetry Collector (Aggregator)
- **Image**: `cmp-otel-aggregator` (custom build based on `otel/opentelemetry-collector-contrib:0.139.0`)
- **Ports**:
  - 14318/tcp: OTLP HTTP receiver (internal)
  - 14317/tcp: OTLP gRPC receiver (internal)
  - 9464/tcp: Prometheus metrics endpoint
- **Functionality**:
  - Receives OTLP metrics and logs from HAProxy
  - Processes with batch, memory limiter, and resource processors
  - Exports metrics to local Prometheus via remote write (port 19090)
  - Exports logs to local Loki via OTLP/HTTP (port 13100)

#### 2. Prometheus
- **Image**: `cmp-prometheus` (custom build based on `prom/prometheus:v3.7.3`)
- **Port**: 19090 (internal, not exposed externally - use Thanos Query instead)
- **Configuration**:
  - Scrape interval: 5s
  - Evaluation interval: 15s
  - Retention: **2 hours** (short-term only, long-term via Thanos)
  - Block duration: 2h (min/max)
  - External labels: cluster='monitoring-ha', replica='node-name'
- **Storage**: `/data/volume/otel/prometheus`
- **Remote Write**: Writes to **both** Thanos Receivers (ports 19291) for HA
- **Scrape targets**:
  - prometheus (self): 127.0.0.1:19090
  - otel-aggregator: otel-aggregator:9464
  - thanos-sidecar: thanos-sidecar:10902

#### 3. Thanos Sidecar
- **Image**: `thanosio/thanos:v0.40.1`
- **Ports**:
  - 10901: gRPC
  - 10902: HTTP
- **Functionality**:
  - Uploads Prometheus 2h blocks to MinIO S3 storage
  - Provides long-term metrics storage
  - Enables multi-cluster querying
- **Storage backend**: MinIO S3-compatible object storage
- **Bucket**: `thanos-metrics`

#### 4. Thanos Receiver
- **Image**: `cmp-thanos-receiver` (custom build based on `thanosio/thanos:v0.40.1`)
- **Ports**:
  - 19291: Remote write endpoint (from Prometheus)
  - 10907: gRPC (for Thanos Query)
  - 10909: HTTP API
- **Functionality**:
  - Receives metrics via Prometheus remote write protocol
  - Implements hashring-based distribution across both receiver nodes
  - Stores received data to MinIO S3 storage
  - Local TSDB retention: 2h (then uploaded to object storage)
  - Replication factor: 1 (data distributed via hashring configuration)
- **Storage**: `/data/volume/otel/thanos-receiver` (local TSDB)
- **Bucket**: `thanos-metrics`
- **Hashring Configuration**: Both receivers in same hashring for load distribution

#### 5. Thanos Query
- **Image**: `thanosio/thanos:v0.40.1`
- **Ports**:
  - 19192: HTTP API (internal)
  - 10904: gRPC
- **Functionality**:
  - Unified query interface across all Thanos components
  - Queries Thanos Sidecar, Receiver, and Store via gRPC
  - Deduplicates metrics based on replica labels
  - Queries both local and peer node components
  - Supports auto-downsampling for long-term queries
- **Query Endpoints**:
  - Local & Peer Thanos Sidecars (10901)
  - Local & Peer Thanos Receivers (10907)
  - Local Thanos Store (10905)

#### 6. Thanos Query Frontend
- **Image**: `thanosio/thanos:v0.40.1`
- **Port**: 29193 (internal, exposed via HAProxy on port 19193)
- **Functionality**:
  - Query caching and splitting for improved performance
  - Splits large queries into smaller time ranges (24h intervals)
  - Caches query results with snappy compression
  - Max 5 retries per request for reliability
  - Frontend for Thanos Query (127.0.0.1:19192)
- **Exposed via HAProxy**: Clients access via VIP:19193

#### 7. Thanos Store Gateway
- **Image**: `thanosio/thanos:v0.40.1`
- **Ports**:
  - 10905: gRPC (for Thanos Query)
  - 10906: HTTP API
- **Functionality**:
  - Queries historical data from MinIO object storage
  - Serves data older than local TSDB retention
  - Index cache: 500MB
  - Chunk pool: 500MB
  - Provides access to all archived metrics
- **Storage**: `/data/volume/otel/thanos-store` (local cache)
- **Bucket**: `thanos-metrics`

#### 8. Thanos Compactor
- **Image**: `thanosio/thanos:v0.40.1`
- **Port**: 10912 (HTTP API)
- **Functionality**:
  - Compacts and downsamples data in object storage
  - Applies retention policies:
    - Raw resolution: 30 days
    - 5m resolution: 90 days
    - 1h resolution: 180 days
  - Delete delay: 48h (safety period before deletion)
  - Runs one instance per cluster (not both nodes simultaneously)
- **Storage**: `/data/volume/otel/thanos-compactor` (working directory)
- **Bucket**: `thanos-metrics`

#### 9. Loki
- **Image**: `grafana/loki:3.4.2`
- **Port**: 13100 (internal, exposed via HAProxy on port 3100)
- **Configuration**:
  - Schema: v13 (TSDB)
  - Storage: S3-compatible (MinIO)
  - Retention: 90 days
  - Bucket: `loki-data`
- **Storage paths**:
  - Chunks: `/loki/chunks`
  - Rules: `/loki/rules`
  - Index: `/loki/index`
  - Cache: `/loki/cache`

#### 10. MinIO (Distributed Mode)
- **Image**: `cmp-minio` (custom build based on `minio/minio:RELEASE.2025-02-07T23-21-09Z`)
- **Ports**:
  - 9000: S3 API
  - 9001: Web Console
- **Mode**: Distributed with erasure coding
- **Nodes**:
  - `http://192.168.110.214:9000/data{1...2}`
  - `http://192.168.110.119:9000/data{1...2}`
- **Buckets**:
  - `loki-data`: Loki log storage
  - `thanos-metrics`: Thanos metrics storage (from Sidecar and Receiver)
- **Volumes per node**:
  - `/data/volume/otel/minio/data1`
  - `/data/volume/otel/minio/data2`

#### 11. HAProxy
- **Image**: `cmp-haproxy` (custom build based on `haproxy:latest`)
- **Port**: 8404 (stats)
- **Frontends**:
  - **OTLP HTTP**: Port 4318 → Backend: OTel Aggregators (both nodes, port 14318)
  - **Thanos Query Frontend**: Port 19193 → Backend: Thanos Query Frontend (both nodes, port 29193)
  - **Thanos Query**: Port 9192 → Backend: Thanos Query (both nodes, port 19192)
  - **Loki**: Port 3100 → Backend: Loki instances (both nodes, port 13100)
- **Load Balancing**: Round-robin across both nodes
- **Health Checks**:
  - OTel: HTTP GET / every 2s
  - Thanos Query Frontend: HTTP GET /-/healthy every 2s (expect 200)
  - Thanos Query: HTTP GET /-/healthy every 2s (expect 200)
  - Loki: HTTP GET /ready every 2s (expect 200)

### Network Architecture

```
External Clients
      |
      | OTLP Ingestion, Metrics Queries, Logs Queries
      v
Virtual IP (192.168.110.140)
:4318 (OTLP), :19193 (Thanos QF), :9192 (Thanos Q), :3100 (Loki)
      |
      | VRRP Failover (Keepalived)
      v
+------------------+------------------+
|                                    |
v                                    v
Node 1 HAProxy                    Node 2 HAProxy
:4318/:19193/:9192/:3100          :4318/:19193/:9192/:3100
|                                    |
| Round-robin Load Balancing         |
v                                    v
+----------+----------+----------+----------+---+
|          |          |          |          |
v          v          v          v          v
OTel-1  Thanos-QF-1 Thanos-Q-1  Loki-1  [Node 2 services]
:14318    :29193     :19192     :13100

Metrics Flow:
OTel → Prometheus (2h retention) → Thanos Receiver (both nodes)
                  ↓
          Thanos Sidecar → MinIO

Query Flow:
Client → VIP:19193 → HAProxy → Thanos Query Frontend
                                      ↓
                                 Thanos Query
                                 ↓     ↓     ↓
                          Sidecar Receiver Store
                                 ↓     ↓     ↓
                               MinIO Object Storage

Compaction:
Thanos Compactor → MinIO (retention + downsampling)
```

## Data Flow

### Metrics Pipeline

1. **Ingestion**: External clients send OTLP metrics to VIP:4318
2. **Load Balancing**: HAProxy (on active VRRP node) load balances requests to OTel Aggregators on both nodes (round-robin)
3. **Processing**: OTel Collector processes with:
   - Memory limiter (4GB limit, 1GB spike)
   - Batch processor (1024 batch size)
   - Resource processor (adds aggregator node label)
4. **Local Storage** (Short-term):
   - Metrics written to local Prometheus (port 19090) via remote write API
   - Prometheus stores with **2h retention** in 2h blocks (reduced for Thanos-based architecture)
5. **Distributed Ingestion via Thanos Receiver**:
   - Each Prometheus instance writes to **both** Thanos Receivers (19291) via remote write
   - Thanos Receivers use hashring-based distribution for load sharing
   - Replication factor: 1 (hashring ensures even data distribution)
   - Data retention in Receiver TSDB: 2h (then uploaded to object storage)
6. **Long-term Storage** (Object Storage):
   - **Thanos Sidecar**: Uploads compacted 2h blocks from Prometheus to MinIO S3
   - **Thanos Receiver**: Uploads received data to MinIO S3 after 2h local retention
   - Both write to `thanos-metrics` bucket
   - Distributed across 4 data volumes (2 per node) with erasure coding
7. **Query Layer**:
   - **Clients query via VIP:19193** (not directly to Prometheus)
   - HAProxy routes to Thanos Query Frontend (load balanced)
   - Query Frontend → Thanos Query → Queries all data sources:
     - Thanos Sidecar (last 2h from Prometheus)
     - Thanos Receiver (last 2h ingested data)
     - Thanos Store (historical data from MinIO)
   - Automatic deduplication across replicas
8. **Data Retention & Compaction**:
   - **Thanos Compactor** runs retention policies:
     - Raw data: 30 days
     - 5m downsampled: 90 days
     - 1h downsampled: 180 days
   - Compacts blocks in MinIO for efficient storage
   - Runs on both nodes but coordinates via object storage locks

### Logs Pipeline

1. **Ingestion**: External clients send OTLP logs to VIP:4318
2. **Load Balancing**: HAProxy (on active VRRP node) load balances requests to OTel Aggregators on both nodes (round-robin)
3. **Processing**: OTel Collector processes logs with:
   - Memory limiter (4GB limit, 1GB spike)
   - Batch processor (1024 batch size)
   - Resource processor (adds aggregator node label)
4. **Storage**:
   - Logs sent to local Loki (port 13100) via OTLP/HTTP
   - Loki stores in MinIO S3 (`loki-data` bucket)
   - 90-day retention period
   - Query access via HAProxy on VIP:3100 (load balanced across both Loki instances)

## High Availability Features

### Automatic Failover

- **Keepalived VRRP**: Monitors HAProxy health
- **Health Check**: `/usr/bin/killall -0 haproxy` every 2 seconds
- **Failover Time**: ~3 seconds (advert_int: 1 second)
- **Authentication**: PASS auth with shared password

### Data Redundancy

- **MinIO Erasure Coding**: Distributed across 4 data volumes (2 per node)
- **Prometheus Local Storage**: 2h retention on each node (short-term buffer)
- **Thanos Receiver Hashring**: Distributes data across both receivers for load sharing
- **Prometheus Remote Write**: Writes to **both** Thanos Receivers for redundancy
- **Thanos Long-term Storage**: Both Sidecar and Receiver upload to MinIO
- **Thanos Query**: Queries all data sources (Sidecar, Receiver, Store) with deduplication
- **Query High Availability**: HAProxy load balances Thanos Query Frontend across both nodes
- **Historical Data Access**: Thanos Store provides access to all archived metrics
- **Loki Data**: Stored in distributed MinIO cluster with erasure coding
- **HAProxy Load Balancing**: Distributes all client requests across both nodes

### Health Checks

All services include comprehensive health checks:

| Service | Health Check Endpoint | Interval | Start Period |
|---------|----------------------|----------|--------------|
| HAProxy | Config validation | 10s | 120s |
| MinIO | http://127.0.0.1:9000/minio/health/live | 10s | 120s |
| OTel Aggregator | http://127.0.0.1:9464/metrics | 10s | 120s |
| Prometheus | http://127.0.0.1:19090/-/healthy | 10s | 120s |
| Thanos Sidecar | http://127.0.0.1:10902/-/healthy | 10s | 120s |
| Thanos Receiver | http://127.0.0.1:10909/-/healthy | 30s | 120s |
| Thanos Query | http://127.0.0.1:19192/-/healthy | 30s | 120s |
| Thanos Query Frontend | http://127.0.0.1:29193/-/healthy | 30s | 120s |
| Thanos Store | http://127.0.0.1:10906/-/healthy | 30s | 120s |
| Thanos Compactor | http://127.0.0.1:10912/-/healthy | 60s | 120s |
| Loki | http://127.0.0.1:13100/metrics | 10s | 120s |

## Configuration Files

### Node 1 (192.168.110.214)

Configuration files are located in `/data/docker/otel/` and backed up to `node1-192.168.110.214/`:

- `docker-compose.yaml`: Main orchestration file
- `.env`: Node-specific environment variables (NODE_NAME, NODE_IP, PEER_IP, etc.)
- `Dockerfile`: OTel Collector custom image
- `haproxy/haproxy.cfg.template`: HAProxy configuration template
- `haproxy/docker-entrypoint.sh`: HAProxy initialization script
- `keepalived/keepalived.conf.template`: Keepalived template
- `keepalived/setup-keepalived.sh`: Keepalived initialization script
- `loki/config.yaml`: Loki configuration
- `minio/Dockerfile`: MinIO custom image
- `minio/run.sh`: MinIO initialization and bucket setup script
- `otel-collector/config.yaml`: OTel Collector pipeline configuration
- `prometheus/prometheus.yml.template`: Prometheus scrape and remote write configuration
- `prometheus/docker-entrypoint.sh`: Prometheus initialization script
- `thanos/bucket.yml`: Thanos S3 bucket configuration
- `thanos/hashrings.json.template`: Thanos Receiver hashring configuration
- `thanos/Dockerfile`: Thanos Receiver custom image

### Node 2 (192.168.110.119)

Configuration files are identical to Node 1, with only `.env` differences:

- `NODE_NAME=mid-2` (vs `mid-1`)
- `NODE_IP=192.168.110.119` (vs `192.168.110.214`)
- `PEER_IP=192.168.110.214` (vs `192.168.110.119`)
- `KEEPALIVED_PRIORITY=90` (vs `100`)
- `KEEPALIVED_STATE=BACKUP` (vs `MASTER`)

All configuration files are backed up to `node2-192.168.110.119/`.

## Volume Mappings

### Node 1 & Node 2 (Identical)

| Service | Container Path | Host Path |
|---------|---------------|-----------|
| Prometheus | `/prometheus` | `/data/volume/otel/prometheus` |
| Thanos | `/prometheus` | `/data/volume/otel/prometheus` |
| Thanos | `/thanos` | `/data/volume/otel/thanos` |
| Loki | `/loki` | `/data/otel/volume/loki` |
| MinIO | `/data1` | `/data/volume/otel/minio/data1` |
| MinIO | `/data2` | `/data/volume/otel/minio/data2` |

## Port Matrix

| Service | VIP | Node 1 | Node 2 | Protocol | Purpose |
|---------|-----|--------|--------|----------|---------|
| **External Access (via HAProxy)** | | | | | |
| OTLP HTTP | :4318 | - | - | HTTP | OTLP HTTP ingestion (load balanced) |
| **Thanos Query Frontend** | **:19193** | - | - | HTTP | **Primary metrics query API with caching** |
| **Thanos Query** | **:9192** | - | - | HTTP | **Direct metrics query API (no cache)** |
| Loki Query | :3100 | - | - | HTTP | Logs query API (load balanced) |
| **HAProxy** | | | | | |
| Stats | - | :8404 | :8404 | HTTP | HAProxy statistics |
| **OTel Aggregator (Internal)** | | | | | |
| HTTP Receiver | - | :14318 | :14318 | HTTP | OTLP HTTP receiver (backend) |
| gRPC Receiver | - | :14317 | :14317 | gRPC | OTLP gRPC receiver (backend) |
| Metrics Endpoint | - | :9464 | :9464 | HTTP | Prometheus scrape endpoint |
| **Prometheus (Internal - Not exposed)** | | | | | |
| API/UI | - | :19090 | :19090 | HTTP | Prometheus API (internal only) |
| **Thanos Sidecar** | | | | | |
| gRPC | - | :10901 | :10901 | gRPC | Thanos Query connection |
| HTTP | - | :10902 | :10902 | HTTP | Thanos sidecar HTTP API |
| **Thanos Receiver** | | | | | |
| Remote Write | - | :19291 | :19291 | HTTP | Prometheus remote write endpoint |
| gRPC | - | :10907 | :10907 | gRPC | Thanos Query connection (hashring) |
| HTTP | - | :10909 | :10909 | HTTP | Thanos receiver HTTP API |
| **Thanos Query** | | | | | |
| HTTP API | - | :19192 | :19192 | HTTP | Thanos Query API (internal) |
| gRPC | - | :10904 | :10904 | gRPC | Thanos Query gRPC |
| **Thanos Query Frontend (via HAProxy)** | | | | | |
| HTTP API | - | :29193 | :29193 | HTTP | Query Frontend (backend for HAProxy) |
| **Thanos Store** | | | | | |
| gRPC | - | :10905 | :10905 | gRPC | Thanos Query connection |
| HTTP | - | :10906 | :10906 | HTTP | Thanos Store HTTP API |
| **Thanos Compactor** | | | | | |
| HTTP | - | :10912 | :10912 | HTTP | Thanos Compactor HTTP API |
| **Loki (Internal)** | | | | | |
| API | - | :13100 | :13100 | HTTP | Loki API (backend) |
| **MinIO** | | | | | |
| S3 API | - | :9000 | :9000 | HTTP | S3-compatible API |
| Console | - | :9001 | :9001 | HTTP | Web UI |

## Container Status

### Node 1 (192.168.110.214)

All containers running and healthy:
- haproxy-mid-1
- keepalived-mid-1
- minio-mid-1
- otel-aggregator-mid-1
- prometheus-mid-1
- thanos-sidecar-mid-1
- thanos-receiver-mid-1
- thanos-query-mid-1
- thanos-query-frontend-mid-1
- thanos-store-mid-1
- thanos-compactor-mid-1
- loki-mid-1

### Node 2 (192.168.110.119)

All containers running and healthy:
- haproxy-mid-2
- keepalived-mid-2
- minio-mid-2
- otel-aggregator-mid-2
- prometheus-mid-2
- thanos-sidecar-mid-2
- thanos-receiver-mid-2
- thanos-query-mid-2
- thanos-query-frontend-mid-2
- thanos-store-mid-2
- thanos-compactor-mid-2
- loki-mid-2

## Deployment Instructions

### Prerequisites

1. Docker and Docker Compose installed on both nodes
2. Network connectivity between nodes (192.168.110.214 and 192.168.110.119)
3. Storage volumes created at `/data/volume/otel/` and `/data/otel/volume/`

### Deployment Steps

1. **On each node**, create directory structure:
   ```bash
   mkdir -p /data/docker/otel
   cd /data/docker/otel
   ```

2. **Copy configuration files**:
   - For Node 1: Use files from `node1-192.168.110.214/`
   - For Node 2: Use files from `node2-192.168.110.119/`

3. **Build custom images**:
   ```bash
   docker-compose build
   ```

4. **Start services**:
   ```bash
   docker-compose up -d
   ```

5. **Verify health**:
   ```bash
   docker-compose ps
   docker-compose logs -f
   ```

### Testing Failover

1. **Check current VIP holder**:
   ```bash
   ip addr show | grep 192.168.110.140
   ```

2. **Stop Keepalived on master**:
   ```bash
   docker stop keepalived-mid-1
   ```

3. **Verify VIP moved to backup**:
   ```bash
   # On Node 2
   ip addr show | grep 192.168.110.140
   ```

4. **Test OTLP ingestion**:
   ```bash
   curl -X POST http://192.168.110.140:4318/v1/metrics \
     -H "Content-Type: application/json" \
     -d '{"resourceMetrics":[]}'
   ```

## Monitoring and Observability

### Access Points

#### Via Virtual IP (Load Balanced) - PRIMARY ACCESS POINTS
- **OTLP Ingestion**: http://192.168.110.140:4318/v1/metrics (metrics), http://192.168.110.140:4318/v1/logs (logs)
- **Thanos Query Frontend (Metrics)**: http://192.168.110.140:19193 - ⭐ **PRIMARY (with caching & splitting)**
- **Thanos Query (Metrics)**: http://192.168.110.140:9192 - **Direct query (no cache)**
- **Loki API (Logs)**: http://192.168.110.140:3100

#### Direct Node Access (for debugging/monitoring)
- **HAProxy Stats**: http://192.168.110.214:8404/stats (Node 1) or http://192.168.110.119:8404/stats (Node 2)
- **MinIO Console**: http://192.168.110.214:9001 (Node 1) or http://192.168.110.119:9001 (Node 2)
- **OTel Metrics**: http://192.168.110.214:9464/metrics (Node 1) or http://192.168.110.119:9464/metrics (Node 2)
- **Prometheus Direct** (not recommended): http://192.168.110.214:19090 (Node 1) or http://192.168.110.119:19090 (Node 2)
- **Loki Direct**: http://192.168.110.214:13100 (Node 1) or http://192.168.110.119:13100 (Node 2)
- **Thanos Sidecar**: http://192.168.110.214:10902 (Node 1) or http://192.168.110.119:10902 (Node 2)
- **Thanos Receiver**: http://192.168.110.214:10909 (Node 1) or http://192.168.110.119:10909 (Node 2)
- **Thanos Query**: http://192.168.110.214:19192 (Node 1) or http://192.168.110.119:19192 (Node 2)
- **Thanos Query Frontend**: http://192.168.110.214:29193 (Node 1) or http://192.168.110.119:29193 (Node 2)
- **Thanos Store**: http://192.168.110.214:10906 (Node 1) or http://192.168.110.119:10906 (Node 2)
- **Thanos Compactor**: http://192.168.110.214:10912 (Node 1) or http://192.168.110.119:10912 (Node 2)

### Key Metrics to Monitor

- **Keepalived**: VIP ownership, VRRP state, failover events
- **HAProxy**: Backend health (all backends), request rate, response times, active connections
- **OTel Collector**: Receiver accepted/refused metrics, exporter sent/failed metrics, batch processing
- **Prometheus**: Ingestion rate, storage usage (should stay under 2h), remote write queue length
- **Thanos Sidecar**: Upload success rate, block compaction status, uploaded blocks count
- **Thanos Receiver**: Remote write ingestion rate, hashring status, TSDB head compaction, upload success rate
- **Thanos Query**: Query latency, deduplication operations, store API calls
- **Thanos Query Frontend**: Cache hit rate, query split operations, retry count
- **Thanos Store**: Block loading status, index cache hit rate, chunk pool usage
- **Thanos Compactor**: Compaction progress, downsampling status, retention enforcement, block count
- **Loki**: Ingestion rate, query performance, stream count, chunk storage
- **MinIO**: Storage usage, API latency, erasure coding health, bucket replication status

## Troubleshooting

### Common Issues

1. **VIP not responding**:
   - Check Keepalived logs: `docker logs keepalived-mid-1`
   - Verify VRRP authentication matches on both nodes
   - Check firewall rules for VRRP (protocol 112)

2. **HAProxy backend down**:
   - Check OTel Aggregator health: `curl http://127.0.0.1:9464/metrics`
   - Review HAProxy logs: `docker logs haproxy-mid-1`

3. **MinIO bucket creation failed**:
   - Check MinIO logs: `docker logs minio-mid-1`
   - Verify distributed mode connectivity between nodes
   - Check network connectivity on port 9000

4. **Thanos not uploading blocks**:
   - Verify MinIO bucket access: Check `thanos/bucket.yml` credentials
   - Check Thanos logs: `docker logs thanos-sidecar-mid-1`
   - Verify Prometheus block creation: Check `/data/volume/otel/prometheus`

5. **Loki ingestion issues**:
   - Check Loki logs: `docker logs loki-mid-1`
   - Verify MinIO bucket permissions
   - Check OTel Collector exporter config

6. **Thanos Receiver not receiving metrics**:
   - Check Prometheus remote write configuration: `prometheus/prometheus.yml.template`
   - Verify Thanos Receiver health: `curl http://127.0.0.1:10909/-/healthy`
   - Check hashring configuration: `thanos/hashrings.json.template`
   - Review Thanos Receiver logs: `docker logs thanos-receiver-mid-1`
   - Verify both receiver endpoints are accessible from Prometheus

7. **HAProxy backend down**:
   - Check HAProxy stats: `curl http://127.0.0.1:8404/stats`
   - Verify backend service health checks
   - Review HAProxy logs for health check failures
   - Check if services are listening on correct ports:
     - OTel Aggregators: 14318
     - Thanos Query Frontend: 29193
     - Thanos Query: 19192
     - Loki: 13100

8. **Thanos Query returns no data**:
   - Verify Thanos Query can reach all stores: Check logs for "store registered"
   - Check Thanos Sidecar is accessible: `curl http://127.0.0.1:10902/-/healthy`
   - Check Thanos Receiver is accessible: `curl http://127.0.0.1:10909/-/healthy`
   - Check Thanos Store is accessible: `curl http://127.0.0.1:10906/-/healthy`
   - Verify MinIO bucket has data: Check MinIO console or `mc ls`
   - Check time ranges: Prometheus has 2h, older data in Store

9. **Thanos Compactor not compacting**:
   - Check Compactor logs: `docker logs thanos-compactor-mid-1`
   - Verify only one Compactor is active (object storage lock)
   - Check MinIO bucket permissions
   - Verify blocks are being uploaded by Sidecar/Receiver

## Security Considerations

### Current Configuration

- MinIO uses hardcoded credentials (should be rotated regularly)
- Keepalived authentication uses shared password
- All services run in host network mode (network_mode: host)
- No TLS/SSL encryption configured (insecure: true)

### Recommendations

1. **Enable TLS**:
   - Configure TLS for all HTTP endpoints
   - Use proper certificates (not self-signed in production)

2. **Secrets Management**:
   - Use Docker secrets or external secrets manager
   - Rotate MinIO credentials regularly
   - Use strong, unique passwords

3. **Network Isolation**:
   - Consider using Docker networks instead of host mode
   - Implement firewall rules to restrict access
   - Use VPN or private network for inter-node communication

4. **Access Control**:
   - Enable authentication on Prometheus and Loki
   - Restrict MinIO console access
   - Implement role-based access control (RBAC)

## Backup and Disaster Recovery

### Data Backup

1. **MinIO Data**:
   - Regularly backup `/data/volume/otel/minio/` on both nodes
   - Consider MinIO bucket replication to external storage

2. **Prometheus Data**:
   - Thanos provides long-term storage in MinIO
   - Backup MinIO `thanos-metrics` bucket

3. **Loki Data**:
   - Stored in MinIO `loki-data` bucket
   - Backup bucket or configure multi-site replication

4. **Configuration Files**:
   - All files backed up in `node1-192.168.110.214/` and `node2-192.168.110.119/`
   - Version control recommended (Git)

### Disaster Recovery Procedures

1. **Single Node Failure**:
   - Keepalived automatically fails over to backup node
   - No manual intervention required
   - Replace failed node and rejoin cluster

2. **Complete Cluster Failure**:
   - Restore MinIO data volumes from backup
   - Deploy containers using saved configuration files
   - Verify MinIO distributed mode connectivity
   - Start services in order: MinIO → Prometheus/Loki → Thanos → OTel → HAProxy → Keepalived

3. **Data Corruption**:
   - MinIO erasure coding provides protection
   - Restore from backup if corruption affects multiple nodes
   - Check Thanos compaction logs for metric recovery

## Performance Tuning

### Current Settings

- **OTel Collector**:
  - Memory limit: 4GB (spike: 1GB)
  - Batch size: 1024 (max: 2048)
  - Batch timeout: 10s

- **Prometheus**:
  - Scrape interval: 5s
  - Retention: 15 days
  - Block duration: 2h

- **Loki**:
  - Retention: 90 days

### Optimization Recommendations

1. **Increase batch size** if experiencing high throughput
2. **Adjust scrape intervals** based on metric cardinality
3. **Tune retention periods** based on storage capacity
4. **Configure resource limits** in docker-compose for better isolation
5. **Enable compression** in OTel Collector exporters

## Architecture Benefits

### High Availability Features

1. **VRRP Failover**: Keepalived provides automatic VIP failover between nodes (~3s failover time)
2. **Load Balancing**: HAProxy distributes traffic across both nodes for all services
3. **Data Redundancy**:
   - Prometheus remote write to both Thanos Receivers
   - MinIO distributed erasure coding across 4 volumes
   - Thanos Receiver hashring ensures data distribution
4. **Query High Availability**: Clients can query Prometheus and Loki via VIP with automatic load balancing
5. **Storage Redundancy**: Multiple layers of data persistence:
   - Local Prometheus storage (15 days)
   - Thanos Sidecar uploads (long-term)
   - Thanos Receiver uploads (long-term)

### Scalability

- **Horizontal Scaling**: Can add more Thanos Receivers to the hashring
- **Storage Scaling**: MinIO cluster can be expanded with more volumes
- **Query Scaling**: HAProxy can balance across additional backend nodes
- **Data Distribution**: Thanos Receiver hashring distributes metrics across nodes

## Future Enhancements

1. **Grafana Integration**: Add Grafana for visualization and dashboards
2. **Alertmanager**: Integrate Prometheus Alertmanager for alerting
3. **Thanos Query**: Deploy Thanos Query component for unified querying across all Prometheus instances
4. **Thanos Store Gateway**: Add Store Gateway for querying historical data from object storage
5. **Multi-site Replication**: Add third site for geo-redundancy
6. **Kubernetes Migration**: Consider migrating to Kubernetes for better orchestration
7. **Service Mesh**: Implement Istio or Linkerd for traffic management
8. **Centralized Logging**: Add Promtail for system log collection
9. **Metrics Federation**: Configure Prometheus federation for cross-cluster queries
10. **Trace Collection**: Add Jaeger or Tempo for distributed tracing support

## References

- OpenTelemetry Collector: https://opentelemetry.io/docs/collector/
- Prometheus: https://prometheus.io/docs/
- Thanos: https://thanos.io/
- Loki: https://grafana.com/docs/loki/
- MinIO: https://min.io/docs/
- HAProxy: http://www.haproxy.org/
- Keepalived: https://www.keepalived.org/

## Contact and Support

For issues or questions regarding this infrastructure:

1. Check logs: `docker-compose logs -f [service-name]`
2. Review health checks: `docker-compose ps`
3. Consult this documentation
4. Review upstream project documentation

## Summary

This is a production-grade OpenTelemetry observability platform with full Thanos integration for scalable, long-term metrics storage.

### Architecture Overview

**Ingestion Layer:**
- **Metrics**: OTLP → OTel Collector → Prometheus (2h local) → Thanos Receiver (distributed)
- **Logs**: OTLP → OTel Collector → Loki → MinIO

**Storage Layer:**
- **Short-term (2h)**: Prometheus local TSDB + Thanos Receiver TSDB
- **Long-term**: MinIO S3-compatible object storage with erasure coding
- **Retention**: 30d raw, 90d 5m downsample, 180d 1h downsample (via Thanos Compactor)

**Query Layer:**
- **Unified Query Interface**: Thanos Query aggregates data from:
  - Thanos Sidecar (recent Prometheus data)
  - Thanos Receiver (ingested data)
  - Thanos Store (historical data from object storage)
- **Query Frontend**: Caching + splitting for performance
- **Load Balanced**: HAProxy distributes queries across both nodes

**High Availability:**
- **VRRP Failover**: Automatic VIP failover with Keepalived (~3s)
- **Load Balancing**: Round-robin across all services on both nodes
- **Data Redundancy**:
  - Prometheus writes to both Thanos Receivers
  - MinIO distributed erasure coding (4 volumes)
  - Query deduplication across replicas

### Key Endpoints

#### For Applications (Ingestion)
- **Ingest OTLP Metrics**: http://192.168.110.140:4318/v1/metrics
- **Ingest OTLP Logs**: http://192.168.110.140:4318/v1/logs

#### For Users (Query)
- **Query Metrics (Thanos Frontend)**: http://192.168.110.140:19193 ⭐ **PRIMARY (Recommended)**
- **Query Metrics (Thanos Direct)**: http://192.168.110.140:9192 (No caching, for debugging)
- **Query Logs (Loki)**: http://192.168.110.140:3100

#### For Operators (Management)
- **HAProxy Stats**: http://{node-ip}:8404/stats
- **MinIO Console**: http://{node-ip}:9001

### Component Count
- **Per Node**: 12 containers (Keepalived, HAProxy, MinIO, OTel, Prometheus, 5 Thanos components, Loki)
- **Total**: 24 containers across 2 nodes
- **Thanos Components**: Sidecar, Receiver, Query, Query Frontend, Store, Compactor

### Key Benefits

1. **Scalability**: Unlimited metrics retention via object storage
2. **Performance**: 2h hot data in Prometheus, historical queries via Thanos Store
3. **Cost Efficiency**: Automatic downsampling reduces storage costs
4. **High Availability**: No single point of failure, automatic failover
5. **Unified Queries**: Single API for all metrics (recent + historical)
6. **Multi-tenancy Ready**: Thanos supports label-based multi-tenancy
7. **Global View**: Cross-replica deduplication and aggregation

---

**Last Updated**: 2025-11-17
**Infrastructure Version**: 3.0 (Full Thanos Stack)
**Components**: OTel Collector + Prometheus (2h) + Thanos (Full Stack: 6 components) + Loki + MinIO + HAProxy + Keepalived
**Maintained By**: Infrastructure Team
