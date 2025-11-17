FROM haproxy:3.2.8-alpine

USER root

RUN apk add --no-cache gettext

COPY haproxy.cfg.template /usr/local/etc/haproxy/haproxy.cfg.template
RUN chown -R haproxy:haproxy /usr/local/etc/haproxy

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

USER haproxy

ENTRYPOINT ["/docker-entrypoint.sh"]
