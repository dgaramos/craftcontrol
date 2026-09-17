#!/bin/sh
# Transport-aware Docker healthcheck for the Bedrock Dedicated Server container.
#
# Runs inside the itzg/minecraft-bedrock-server image (POSIX sh, awk, grep).
# Bedrock 1.26.50+ selects its transport in server.properties:
#
#   transport=raknet     Classic UDP transport. Readiness is a RakNet pong on
#                        server-port, queried with the bundled mc-monitor.
#   transport=nethernet  WebRTC-based transport. Nothing answers RakNet pings
#                        (server-port is not even bound), so readiness is the
#                        NetherNet discovery socket bound on UDP 7551.
#
# Any other value is unsupported and reported unhealthy. See
# docs/bedrock-proxy.md ("Bedrock 1.26.50+ transport migration").
#
# Environment overrides exist for tests only; the container defaults apply
# when the script runs as a Compose healthcheck.
set -u

properties="${BEDROCK_PROPERTIES:-/data/server.properties}"
proc_udp="${BEDROCK_PROC_NET_UDP:-/proc/net/udp}"
proc_udp6="${BEDROCK_PROC_NET_UDP6:-/proc/net/udp6}"
mc_monitor="${MC_MONITOR:-/usr/local/bin/mc-monitor}"

# NetherNet LAN discovery listens on UDP 7551; /proc/net/udp* lists ports in hex.
readonly NETHERNET_DISCOVERY_PORT=7551
readonly NETHERNET_DISCOVERY_PORT_HEX=1D7F

if [ ! -r "$properties" ]; then
  echo "bedrock-healthcheck: cannot read $properties" >&2
  exit 1
fi

property() {
  awk -F= -v key="$1" '$1 == key { sub(/\r$/, "", $2); print $2; exit }' "$properties"
}

transport="$(property transport | tr '[:upper:]' '[:lower:]')"
transport="${transport:-raknet}"

case "$transport" in
  raknet)
    port="$(property server-port)"
    exec "$mc_monitor" status-bedrock --host 127.0.0.1 --port "${port:-19132}"
    ;;
  nethernet)
    if cat "$proc_udp6" "$proc_udp" 2>/dev/null | grep -q -i ":${NETHERNET_DISCOVERY_PORT_HEX} "; then
      exit 0
    fi
    echo "bedrock-healthcheck: NetherNet discovery socket (UDP ${NETHERNET_DISCOVERY_PORT}) is not bound yet" >&2
    exit 1
    ;;
  *)
    echo "bedrock-healthcheck: unsupported transport '${transport}' (expected raknet or nethernet)" >&2
    exit 1
    ;;
esac
