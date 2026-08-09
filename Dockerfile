FROM python:3.12-alpine

RUN apk add --no-cache docker-cli docker-cli-compose \
    && addgroup -S manager \
    && adduser -S -G manager manager

WORKDIR /app
COPY apps/backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY apps/backend/app.py apps/backend/wsgi.py ./
COPY apps/backend/minecraft_manager ./minecraft_manager
COPY apps ./apps
COPY packages ./packages
COPY packs ./packs
COPY bin/craftcontrol /usr/local/bin/craftcontrol
RUN chmod 755 /usr/local/bin/craftcontrol

# O grupo do socket varia por host; o Compose executa com o GID informado.
EXPOSE 8082
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8082/api/health || exit 1

CMD ["gunicorn", "--bind=0.0.0.0:8082", "--workers=1", "--threads=16", "--timeout=0", "--access-logfile=-", "wsgi:app"]
