FROM otel/opentelemetry-collector-contrib:0.139.0 AS otel

FROM alpine:3.22.2 AS prod

USER 0:0

RUN apk --no-cache add bash curl tzdata
RUN echo "Asia/Seoul" >  /etc/timezone
RUN cp -f /usr/share/zoneinfo/Asia/Seoul /etc/localtime

COPY --from=otel /otelcol-contrib /otelcol-contrib

ARG USER_UID=10001
ARG USER_GID=10001

USER 10001:1001

ENTRYPOINT ["/otelcol-contrib"]
CMD ["--config=/etc/otel-contrib/config.yaml"]

EXPOSE 4317/tcp 4318/tcp 55679/tcp
