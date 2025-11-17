#!/usr/bin/env python3
"""
OpenTelemetry High Availability Infrastructure Architecture Diagram Generator
"""

from diagrams import Diagram, Cluster, Edge
from diagrams.onprem.monitoring import Prometheus, Grafana
from diagrams.onprem.logging import Loki
from diagrams.programming.framework import Fastapi
from diagrams.onprem.network import HAProxy
from diagrams.generic.storage import Storage
from diagrams.generic.device import Mobile
from diagrams.generic.blank import Blank

graph_attr = {
    "fontsize": "20",
    "bgcolor": "white",
    "pad": "0.5",
    "fontname": "Sans-Serif Bold",
}

node_attr = {
    "fontsize": "14",
    "fontname": "Sans-Serif Bold",
}

edge_attr = {
    "fontsize": "12",
    "fontname": "Sans-Serif",
}

with Diagram("OpenTelemetry HA Infrastructure",
             filename="otel-infrastructure",
             outformat="png",
             show=False,
             direction="TB",
             graph_attr=graph_attr,
             node_attr=node_attr,
             edge_attr=edge_attr):

    # External clients
    clients = Mobile("External\nClients")

    # Virtual IP
    vip = Blank("VIP\n192.168.110.140")

    with Cluster("Node 1 (192.168.110.214) - MASTER"):
        with Cluster("Load Balancing"):
            keepalived1 = Blank("Keepalived\nPriority: 100")
            haproxy1 = HAProxy("HAProxy\n:4318")

        otel1 = Fastapi("OTel Aggregator\n:14318")

        with Cluster("Metrics Stack"):
            prom1 = Prometheus("Prometheus\n:9090")
            thanos1 = Storage("Thanos Sidecar\n:10901/10902")

        loki1 = Loki("Loki\n:3100")

        with Cluster("Object Storage Node 1"):
            minio1 = Storage("MinIO Node 1\n:9000\n/data1 + /data2")

    with Cluster("Node 2 (192.168.110.119) - BACKUP"):
        with Cluster("Load Balancing"):
            keepalived2 = Blank("Keepalived\nPriority: 90")
            haproxy2 = HAProxy("HAProxy\n:4318")

        otel2 = Fastapi("OTel Aggregator\n:14318")

        with Cluster("Metrics Stack"):
            prom2 = Prometheus("Prometheus\n:9090")
            thanos2 = Storage("Thanos Sidecar\n:10901/10902")

        loki2 = Loki("Loki\n:3100")

        with Cluster("Object Storage Node 2"):
            minio2 = Storage("MinIO Node 2\n:9000\n/data1 + /data2")

    with Cluster("MinIO Distributed Cluster"):
        bucket_thanos = Storage("Bucket:\nthanos-metrics")
        bucket_loki = Storage("Bucket:\nloki-data")

    # Connections - Client to VIP
    clients >> Edge(label="OTLP/HTTP", color="blue", style="bold") >> vip

    # VIP to Keepalived
    vip >> Edge(label="VRRP", color="red") >> keepalived1
    vip >> Edge(label="VRRP", color="red") >> keepalived2

    # Keepalived to HAProxy
    keepalived1 - Edge(color="red") - haproxy1
    keepalived2 - Edge(color="red") - haproxy2

    # HAProxy to OTel Aggregator
    haproxy1 >> Edge(label="Forward", color="blue") >> otel1
    haproxy2 >> Edge(label="Forward", color="blue") >> otel2

    # OTel to backends
    otel1 >> Edge(label="Metrics", color="green") >> prom1
    otel1 >> Edge(label="Logs", color="orange") >> loki1

    otel2 >> Edge(label="Metrics", color="green") >> prom2
    otel2 >> Edge(label="Logs", color="orange") >> loki2

    # Prometheus to Thanos
    prom1 - Edge(label="Scrape", style="dashed", color="green") - thanos1
    prom2 - Edge(label="Scrape", style="dashed", color="green") - thanos2

    # Thanos to MinIO buckets
    thanos1 >> Edge(label="Upload", color="purple", style="bold") >> bucket_thanos
    thanos2 >> Edge(label="Upload", color="purple", style="bold") >> bucket_thanos

    # Loki to MinIO buckets
    loki1 >> Edge(label="Store", color="orange", style="bold") >> bucket_loki
    loki2 >> Edge(label="Store", color="orange", style="bold") >> bucket_loki

    # MinIO nodes to buckets (Distributed Erasure Coding)
    minio1 >> Edge(label="Erasure\nCoding", color="brown", style="bold") >> bucket_thanos
    minio1 >> Edge(label="Erasure\nCoding", color="brown", style="bold") >> bucket_loki

    minio2 >> Edge(label="Erasure\nCoding", color="brown", style="bold") >> bucket_thanos
    minio2 >> Edge(label="Erasure\nCoding", color="brown", style="bold") >> bucket_loki

    # MinIO inter-node replication
    minio1 - Edge(label="Distributed\nCluster", color="brown", style="dotted") - minio2
