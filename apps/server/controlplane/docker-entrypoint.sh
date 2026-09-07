#!/bin/sh
# Provisions the internal TLS material for the frontend-to-backend hop.
#
# The frontend proxies every API call — including the session cookie — to this
# container. Without TLS that hop is cleartext on the Compose network. The key
# material is generated here at first start and lives only in the mounted
# volume: nothing is baked into the image and nothing is ever committed.
#
# TLS is opt-in by mounting the directory. Without it the server still starts
# over plain HTTP, so a monolith or a local run needs no certificates.
set -eu

TLS_DIR="${CRAFTCONTROL_TLS_DIR:-/tls}"
CA_DAYS="${CRAFTCONTROL_TLS_CA_DAYS:-3650}"
CERT_DAYS="${CRAFTCONTROL_TLS_CERT_DAYS:-825}"
BACKEND_NAME="${CRAFTCONTROL_TLS_BACKEND_NAME:-craftcontrol-backend}"

generate_material() {
    umask 077
    openssl req -x509 -newkey rsa:2048 -nodes -days "$CA_DAYS" -sha256 \
        -keyout "$TLS_DIR/ca.key" -out "$TLS_DIR/ca.crt" \
        -subj "/CN=CraftControl internal CA" >/dev/null 2>&1

    openssl req -newkey rsa:2048 -nodes -sha256 \
        -keyout "$TLS_DIR/server.key" -out "$TLS_DIR/server.csr" \
        -subj "/CN=$BACKEND_NAME" >/dev/null 2>&1

    # The proxy verifies the name, so the certificate must carry it. localhost
    # and the loopback address are for the container's own health probe.
    cat > "$TLS_DIR/server.ext" <<EXT
subjectAltName = DNS:$BACKEND_NAME, DNS:localhost, IP:127.0.0.1
extendedKeyUsage = serverAuth
EXT

    openssl x509 -req -in "$TLS_DIR/server.csr" -days "$CERT_DAYS" -sha256 \
        -CA "$TLS_DIR/ca.crt" -CAkey "$TLS_DIR/ca.key" -CAcreateserial \
        -extfile "$TLS_DIR/server.ext" -out "$TLS_DIR/server.crt" >/dev/null 2>&1

    rm -f "$TLS_DIR/server.csr" "$TLS_DIR/server.ext"
    # The proxy container reads the CA as a different user; the private keys
    # stay readable only by this one.
    chmod 644 "$TLS_DIR/ca.crt"
    chmod 600 "$TLS_DIR/ca.key" "$TLS_DIR/server.key"
    chmod 644 "$TLS_DIR/server.crt"
    echo "craftcontrol: generated internal TLS material in $TLS_DIR" >&2
}

if [ -d "$TLS_DIR" ] && [ ! -f "$TLS_DIR/server.crt" ]; then
    generate_material
fi

if [ -f "$TLS_DIR/server.crt" ] && [ -f "$TLS_DIR/server.key" ]; then
    set -- "$@" "--certfile=$TLS_DIR/server.crt" "--keyfile=$TLS_DIR/server.key"
fi

exec "$@"
