FROM nginx:1.29-alpine

ARG CRAFTCONTROL_FRONTEND_VERSION=0.3.6
LABEL org.opencontainers.image.title="CraftControl Client" \
      org.opencontainers.image.description="CraftControl browser client and same-origin API proxy" \
      org.opencontainers.image.version="${CRAFTCONTROL_FRONTEND_VERSION}"

COPY apps/client/nginx.conf /etc/nginx/conf.d/default.conf
COPY apps/client/templates/index.html /usr/share/nginx/html/index.html
COPY apps/client/static /usr/share/nginx/html/static
RUN printf '{"service":"frontend","version":"%s"}\n' "$CRAFTCONTROL_FRONTEND_VERSION" > /usr/share/nginx/html/version.json \
    && chmod -R a=rX /usr/share/nginx/html

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
