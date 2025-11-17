FROM alpine:3.22.2
RUN apk add --no-cache gettext

COPY --from=prom/prometheus:v3.7.3 /bin/prometheus /bin/prometheus
COPY --from=prom/prometheus:v3.7.3 /bin/promtool /bin/promtool

RUN mkdir -p /prometheus /etc/prometheus && \
    chown -R nobody:nobody /prometheus /etc/prometheus

COPY prometheus.yml.template /etc/prometheus/prometheus.yml.template
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

USER nobody

WORKDIR /prometheus
EXPOSE 9090
VOLUME ["/prometheus"]

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["--config.file=/etc/prometheus/prometheus.yml", \
     "--storage.tsdb.path=/prometheus"]
