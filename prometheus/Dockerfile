FROM prom/prometheus:v3.7.3

USER root

RUN apk add --no-cache gettext

COPY prometheus.yml.template /etc/prometheus/prometheus.yml.template
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

USER nobody

ENTRYPOINT ["/docker-entrypoint.sh"]
