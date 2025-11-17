#!/bin/bash

set -e

OTEL_VERSION="0.139.0"
VIP="192.168.110.140"

echo "Installing OpenTelemetry Collector..."

cd /tmp
curl -L -o otelcol-contrib_${OTEL_VERSION}_linux_amd64.tar.gz https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v${OTEL_VERSION}/otelcol-contrib_${OTEL_VERSION}_linux_amd64.tar.gz
yum install -y tar || apt-get install -y tar
tar -xzf otelcol-contrib_${OTEL_VERSION}_linux_amd64.tar.gz
mv otelcol-contrib /usr/local/bin/
chmod +x /usr/local/bin/otelcol-contrib
chcon -t bin_t /usr/local/bin/otelcol-contrib

mkdir -p /etc/otelcol-contrib

cat > /etc/otelcol-contrib/config.yaml <<'EOF'
receivers:
  hostmetrics:
    collection_interval: 10s
    scrapers:
      cpu:
      disk:
      filesystem:
        exclude_fs_types:
          fs_types:
            - sysfs
            - tmpfs
            - devtmpfs
            - configfs
            - debugfs
            - tracefs
            - securityfs
            - sockfs
            - pipefs
            - rpc_pipefs
            - ramfs
            - hugetlbfs
            - devpts
            - autofs
            - efivarfs
            - mqueue
            - selinuxfs
            - pstore
            - fuseblk
            - fuse
            - fusectl
            - nsfs
            - squashfs
            - ecryptfs
            - overlay
            - fuse.fuse-overlayfs
            - nfs
            - nfs4
          match_type: strict
      memory:
      network:
        exclude:
          interfaces:
            - lo
            - veth.*
          match_type: regexp
      paging:
      processes:
      process:
        mute_process_name_error: true
        mute_process_exe_error: true
        mute_process_io_error: true
        mute_process_user_error: true

processors:
  batch:
    timeout: 10s
  resourcedetection:
    detectors: [system]

exporters:
  otlphttp:
    endpoint: http://VIP_PLACEHOLDER:4318
    compression: gzip

service:
  pipelines:
    metrics:
      receivers: [hostmetrics]
      processors: [resourcedetection, batch]
      exporters: [otlphttp]
EOF

sed -i "s/VIP_PLACEHOLDER/${VIP}/g" /etc/otelcol-contrib/config.yaml

cat > /etc/systemd/system/otelcol-contrib.service <<'EOF'
[Unit]
Description=OpenTelemetry Collector Contrib
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/otelcol-contrib --config=/etc/otelcol-contrib/config.yaml
Restart=on-failure
RestartSec=10s
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

chcon system_u:object_r:systemd_unit_file_t:s0 /etc/otelcol-contrib/config.yaml
chcon system_u:object_r:systemd_unit_file_t:s0 /etc/systemd/system/otelcol-contrib.service

systemctl daemon-reload
systemctl enable otelcol-contrib
systemctl start otelcol-contrib

echo "Installation complete!"
echo "Check status: systemctl status otelcol-contrib"
echo "Check logs: journalctl -u otelcol-contrib -f"
