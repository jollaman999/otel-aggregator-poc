FROM haproxy:3.2.8-alpine

COPY haproxy.cfg.template /usr/local/etc/haproxy/haproxy.cfg.template
COPY docker-entrypoint.sh /docker-entrypoint.sh

RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["haproxy", "-f", "/usr/local/etc/haproxy/haproxy.cfg"]
