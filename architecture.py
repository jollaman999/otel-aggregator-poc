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

    # Virtual IP with multiple frontends
    with Cluster("Virtual IP (192.168.110.140)"):
        vip_otlp = Blank("OTLP :4318")
        vip_thanos_qf = Blank("Thanos QF :19193")
        vip_thanos_q = Blank("Thanos Q :9192")
        vip_loki = Blank("Loki :3100")

    with Cluster("Node 1 (192.168.110.214) - MASTER"):
        with Cluster("Load Balancing & HA"):
            keepalived1 = Blank("Keepalived\nPriority: 100")
            haproxy1 = HAProxy("HAProxy\n:4318/19193/9192/3100")

        otel1 = Fastapi("OTel Aggregator\n:14318")

        with Cluster("Metrics Collection"):
            prom1 = Prometheus("Prometheus\n:19090\nRetention: 2h")
            thanos_side1 = Storage("Thanos Sidecar\n:10901/:10902")

        with Cluster("Thanos Ingestion"):
            thanos_recv1 = Storage("Thanos Receiver\n:19291/:10907/:10909")

        with Cluster("Thanos Query Stack"):
            thanos_query1 = Storage("Thanos Query\n:19192/:10904")
            thanos_qf1 = Storage("Query Frontend\n:29193")
            thanos_store1 = Storage("Thanos Store\n:10905/:10906")

        thanos_compact1 = Storage("Thanos Compactor\n:10912")

        loki1 = Loki("Loki\n:13100")

        with Cluster("Object Storage Node 1"):
            minio1 = Storage("MinIO Node 1\n:9000\n/data1 + /data2")

    with Cluster("Node 2 (192.168.110.119) - BACKUP"):
        with Cluster("Load Balancing & HA"):
            keepalived2 = Blank("Keepalived\nPriority: 90")
            haproxy2 = HAProxy("HAProxy\n:4318/19193/9192/3100")

        otel2 = Fastapi("OTel Aggregator\n:14318")

        with Cluster("Metrics Collection"):
            prom2 = Prometheus("Prometheus\n:19090\nRetention: 2h")
            thanos_side2 = Storage("Thanos Sidecar\n:10901/:10902")

        with Cluster("Thanos Ingestion"):
            thanos_recv2 = Storage("Thanos Receiver\n:19291/:10907/:10909")

        with Cluster("Thanos Query Stack"):
            thanos_query2 = Storage("Thanos Query\n:19192/:10904")
            thanos_qf2 = Storage("Query Frontend\n:29193")
            thanos_store2 = Storage("Thanos Store\n:10905/:10906")

        thanos_compact2 = Storage("Thanos Compactor\n:10912")

        loki2 = Loki("Loki\n:13100")

        with Cluster("Object Storage Node 2"):
            minio2 = Storage("MinIO Node 2\n:9000\n/data1 + /data2")

    with Cluster("MinIO Distributed Cluster"):
        bucket_thanos = Storage("Bucket:\nthanos-metrics")
        bucket_loki = Storage("Bucket:\nloki-data")

    # Connections - Client to VIP
    clients >> Edge(label="OTLP/HTTP", color="blue", style="bold") >> vip_otlp
    clients >> Edge(label="Metrics Query (Cached)", color="purple", style="bold") >> vip_thanos_qf
    clients >> Edge(label="Metrics Query (Direct)", color="purple", style="dashed") >> vip_thanos_q
    clients >> Edge(label="Logs Query", color="orange", style="dashed") >> vip_loki

    # VIP to Keepalived (VRRP failover)
    vip_otlp >> Edge(label="VRRP", color="red") >> keepalived1
    vip_thanos_qf >> Edge(label="VRRP", color="red") >> keepalived1
    vip_thanos_q >> Edge(label="VRRP", color="red") >> keepalived1
    vip_loki >> Edge(label="VRRP", color="red") >> keepalived1

    vip_otlp >> Edge(label="VRRP", color="red") >> keepalived2
    vip_thanos_qf >> Edge(label="VRRP", color="red") >> keepalived2
    vip_thanos_q >> Edge(label="VRRP", color="red") >> keepalived2
    vip_loki >> Edge(label="VRRP", color="red") >> keepalived2

    # Keepalived to HAProxy
    keepalived1 - Edge(color="red") - haproxy1
    keepalived2 - Edge(color="red") - haproxy2

    # HAProxy load balancing to both nodes
    haproxy1 >> Edge(label="LB", color="blue") >> otel1
    haproxy1 >> Edge(label="LB", color="blue", style="dashed") >> otel2
    haproxy1 >> Edge(label="LB QF", color="purple") >> thanos_qf1
    haproxy1 >> Edge(label="LB QF", color="purple", style="dashed") >> thanos_qf2
    haproxy1 >> Edge(label="LB Q", color="purple", style="dotted") >> thanos_query1
    haproxy1 >> Edge(label="LB Q", color="purple", style="dotted") >> thanos_query2
    haproxy1 >> Edge(label="LB", color="orange") >> loki1
    haproxy1 >> Edge(label="LB", color="orange", style="dashed") >> loki2

    haproxy2 >> Edge(label="LB", color="blue", style="dashed") >> otel1
    haproxy2 >> Edge(label="LB", color="blue") >> otel2
    haproxy2 >> Edge(label="LB QF", color="purple", style="dashed") >> thanos_qf1
    haproxy2 >> Edge(label="LB QF", color="purple") >> thanos_qf2
    haproxy2 >> Edge(label="LB Q", color="purple", style="dotted") >> thanos_query1
    haproxy2 >> Edge(label="LB Q", color="purple", style="dotted") >> thanos_query2
    haproxy2 >> Edge(label="LB", color="orange", style="dashed") >> loki1
    haproxy2 >> Edge(label="LB", color="orange") >> loki2

    # OTel to local backends
    otel1 >> Edge(label="Remote Write", color="green") >> prom1
    otel1 >> Edge(label="Logs", color="orange") >> loki1

    otel2 >> Edge(label="Remote Write", color="green") >> prom2
    otel2 >> Edge(label="Logs", color="orange") >> loki2

    # Prometheus remote write to Thanos Receivers (both nodes)
    prom1 >> Edge(label="Remote Write", color="purple", style="bold") >> thanos_recv1
    prom1 >> Edge(label="Remote Write", color="purple", style="bold") >> thanos_recv2

    prom2 >> Edge(label="Remote Write", color="purple", style="bold") >> thanos_recv1
    prom2 >> Edge(label="Remote Write", color="purple", style="bold") >> thanos_recv2

    # Thanos Query Frontend to Query
    thanos_qf1 >> Edge(label="Query", color="purple") >> thanos_query1
    thanos_qf2 >> Edge(label="Query", color="purple") >> thanos_query2

    # Thanos Query to data sources
    thanos_query1 >> Edge(label="gRPC", color="purple", style="dashed") >> thanos_side1
    thanos_query1 >> Edge(label="gRPC", color="purple", style="dashed") >> thanos_recv1
    thanos_query1 >> Edge(label="gRPC", color="purple", style="dashed") >> thanos_store1

    thanos_query2 >> Edge(label="gRPC", color="purple", style="dashed") >> thanos_side2
    thanos_query2 >> Edge(label="gRPC", color="purple", style="dashed") >> thanos_recv2
    thanos_query2 >> Edge(label="gRPC", color="purple", style="dashed") >> thanos_store2

    # Cross-node Thanos Query access (commented out for simplicity)
    # thanos_query1 >> Edge(label="Cross-node", color="purple", style="dotted") >> thanos_side2
    # thanos_query1 >> Edge(label="Cross-node", color="purple", style="dotted") >> thanos_recv2
    # thanos_query2 >> Edge(label="Cross-node", color="purple", style="dotted") >> thanos_side1
    # thanos_query2 >> Edge(label="Cross-node", color="purple", style="dotted") >> thanos_recv1

    # Thanos Store to MinIO
    thanos_store1 >> Edge(label="Read", color="purple") >> bucket_thanos
    thanos_store2 >> Edge(label="Read", color="purple") >> bucket_thanos

    # Thanos Sidecar and Receiver to MinIO buckets
    thanos_side1 >> Edge(label="Upload", color="purple") >> bucket_thanos
    thanos_side2 >> Edge(label="Upload", color="purple") >> bucket_thanos

    thanos_recv1 >> Edge(label="Upload", color="purple") >> bucket_thanos
    thanos_recv2 >> Edge(label="Upload", color="purple") >> bucket_thanos

    # Thanos Compactor to MinIO
    thanos_compact1 >> Edge(label="Compact", color="purple") >> bucket_thanos
    thanos_compact2 >> Edge(label="Compact", color="purple") >> bucket_thanos

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

    # Thanos Receiver hashring replication
    thanos_recv1 - Edge(label="Hashring", color="purple", style="dotted") - thanos_recv2
