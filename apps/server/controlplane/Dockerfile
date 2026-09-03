FROM python:3.12-alpine

ARG CRAFTCONTROL_BACKEND_VERSION=0.1.0
LABEL org.opencontainers.image.title="CraftControl Server" \
      org.opencontainers.image.description="CraftControl server API and Bedrock operations" \
      org.opencontainers.image.version="${CRAFTCONTROL_BACKEND_VERSION}"

RUN apk add --no-cache docker-cli docker-cli-compose \
    && addgroup -S manager \
    && adduser -S -G manager manager

WORKDIR /app
COPY apps/server/controlplane/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY apps/server/controlplane/app.py apps/server/controlplane/wsgi.py ./
COPY apps/server/controlplane/src ./controlplane
COPY packages ./packages
COPY packs ./packs
COPY bin/craftcontrol /usr/local/bin/craftcontrol
RUN chmod 755 /usr/local/bin/craftcontrol

EXPOSE 8082
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8082/api/health || exit 1

CMD ["gunicorn", "--bind=0.0.0.0:8082", "--workers=1", "--threads=16", "--timeout=0", "--access-logfile=-", "wsgi:app"]
