#!/usr/bin/env bash
# Shared health wait for the deploy scripts.
#
# Sourced, not executed. The caller must define fail().

# Waits for a container to report "healthy".
#
# Docker only reports "healthy" after a successful probe, so the window must
# comfortably exceed the image health-check cadence (start period plus a few
# intervals). Three things end the wait early, each with the container logs:
# the container leaving the running state, and — because restart policies put a
# crashing container straight back into "running" with its health reset — any
# change to the restart counter. A container that flapped during the wait is
# never accepted as healthy, however healthy it looks afterwards.
wait_for_container_health() {
  local container="$1" label="$2" attempts="${3:-90}"
  local restarts state health

  restarts="$(docker inspect "$container" --format '{{.RestartCount}}' 2>/dev/null || true)"

  _report_unhealthy() {
    docker logs --tail 50 "$container" >&2 || true
    fail "$1"
  }

  for _ in $(seq 1 "$attempts"); do
    state="$(docker inspect "$container" --format '{{.State.Status}}' 2>/dev/null || true)"
    health="$(docker inspect "$container" --format '{{.State.Health.Status}}' 2>/dev/null || true)"
    if [[ "$(docker inspect "$container" --format '{{.RestartCount}}' 2>/dev/null || true)" != "$restarts" ]]; then
      _report_unhealthy "$label restarted while starting"
    fi
    [[ "$health" == "healthy" ]] && return 0
    if [[ "$state" != "running" && "$state" != "created" ]]; then
      _report_unhealthy "$label stopped while starting (state=$state)"
    fi
    sleep 2
  done

  _report_unhealthy "$label did not become healthy"
}
