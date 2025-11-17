FROM alpine:latest
RUN apk add --no-cache gettext
COPY --from=thanosio/thanos:v0.40.1 /bin/thanos /bin/thanos

RUN adduser \
    -D `#Dont assign a password` \
    -H `#Dont create home directory` \
    -u 1001 `#User id`\
    thanos

COPY docker-entrypoint-receiver.sh /docker-entrypoint-receiver.sh
RUN chmod +x /docker-entrypoint-receiver.sh

USER 1001

ENTRYPOINT ["/docker-entrypoint-receiver.sh"]
