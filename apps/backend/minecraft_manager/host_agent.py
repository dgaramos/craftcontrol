"""HTTP adapter implementing ContainerOperations via the CraftControl host agent.

The host agent runs on the Docker host outside all containers.  This adapter
replaces ``DockerOperations`` at the ``ContainerOperations`` boundary, routing
PREPARATION, RESTART, and HEALTH_WAIT stages through the agent instead of
calling Docker directly from inside the backend container.

See ``docs/host-agent-contract.md`` for the full API contract.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Protocol

LOGGER = logging.getLogger(__name__)

# How long to wait between polling attempts after POST /v1/execute returns 202.
_POLL_INTERVAL_SECONDS = 5.0
# Maximum poll attempts while waiting for the agent to complete.
_MAX_POLL_ATTEMPTS = 120  # 120 * 5s = 10 minutes ceiling
# How many times to retry GET /v1/status after a post-delivery ambiguous failure.
_POST_DELIVERY_RETRY_COUNT = 3
_POST_DELIVERY_RETRY_INTERVAL_SECONDS = 5.0


class _HttpClient(Protocol):
    """Minimal HTTP client boundary used for test injection."""

    def request(
        self,
        method: str,
        url: str,
        *,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> tuple[int, dict[str, Any]]:
        """Send an HTTP request, return (status_code, parsed_json_body).

        Raises:
            ConnectionRefusedError: when the TCP connection was refused
                (pre-delivery failure — request was never delivered).
            TimeoutError: when a connect timeout fires before TCP handshake
                (pre-delivery failure — request was never delivered).
            OSError: for all other transport-layer failures.  The caller must
                determine whether the request was delivered before failing.
        """
        ...  # pragma: no cover


class _UrllibClient:
    """Production HTTP client wrapping ``urllib.request``."""

    def request(
        self,
        method: str,
        url: str,
        *,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> tuple[int, dict[str, Any]]:
        req = urllib.request.Request(url, data=body, method=method)
        for key, value in (headers or {}).items():
            req.add_header(key, value)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                return resp.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                body_dict: dict[str, Any] = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                body_dict = {}
            return exc.code, body_dict
        except urllib.error.URLError as exc:
            # Unwrap URLError to preserve the caller's exception classification:
            # - pre-delivery connect failure (ConnectionRefusedError, TimeoutError)
            # - read-phase timeout (TimeoutError raised after TCP handshake)
            # Re-raise the underlying reason when it is an OSError so that
            # execute() can distinguish connection-refused from timeouts.
            if isinstance(exc.reason, OSError):
                raise exc.reason from exc
            raise OSError(str(exc)) from exc


def _load_token(token_file: str) -> str:
    """Read the shared secret from *token_file*, stripping trailing whitespace."""
    path = Path(token_file)
    try:
        return path.read_text().strip()
    except OSError as exc:
        raise RuntimeError(
            f"host agent token file not readable: {token_file!r}: {exc}"
        ) from exc


class HostAgentContainerOperations:
    """``ContainerOperations`` implementation that delegates to the host agent.

    This adapter satisfies the ``ContainerOperations`` port structurally and
    can replace ``DockerOperations`` in the composition root.  The backend
    container does not require a Docker socket mount when this adapter is active.

    Authentication uses a shared secret read once at construction time.  No
    token value is written to logs, error messages, or API responses.

    Unavailability handling follows ``docs/host-agent-contract.md``:

    - Pre-delivery failures (connection refused, connect timeout) are surfaced
      as a ``RuntimeError`` immediately.
    - Post-delivery ambiguous failures trigger three retries of
      ``GET /v1/status/{operation_id}`` before the operation is failed with
      an ``executor_internal_error`` detail.
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        http_client: _HttpClient,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._client: _HttpClient = http_client

    # ------------------------------------------------------------------
    # ContainerOperations interface
    # ------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """Return container-style status by probing the agent's health endpoint.

        A successful GET /v1/health response is mapped to an "online" / "running"
        state.  Any transport failure or non-200 response is mapped to "stopped"
        without raising.
        """
        url = f"{self._base_url}/v1/health"
        try:
            code, _body = self._client.request("GET", url, timeout=10.0)
        except OSError:
            return {"online": False, "state": "stopped", "container": "host-agent"}
        if code == 200:
            return {"online": True, "state": "running", "container": "host-agent"}
        return {"online": False, "state": "stopped", "container": "host-agent"}

    def execute(
        self,
        action: str,
        *,
        operation_id: str | None = None,
        intended_state: dict[str, Any] | None = None,
        health_timeout_seconds: int = 120,
        restart_timeout_seconds: int = 120,
    ) -> None:
        """Execute a server operation via the host agent.

        Only the ``"apply"`` and ``"restart"`` actions are supported; all
        others raise ``KeyError``.

        Blocks until the agent reports a terminal result.  Raises
        ``RuntimeError`` on any failure so the ``ServerOperationService``
        records the RESTART stage as failed with the exception message.
        """
        if action not in {"apply", "restart"}:
            raise RuntimeError(
                f"HostAgentContainerOperations does not support action {action!r}; "
                "only 'apply' and 'restart' are implemented"
            )

        if not operation_id:
            raise ValueError("operation_id is required for HostAgentContainerOperations.execute")
        if intended_state is None:
            intended_state = {}

        payload = {
            "operation_id": operation_id,
            "intended_state": intended_state,
            "health_timeout_seconds": health_timeout_seconds,
            "restart_timeout_seconds": restart_timeout_seconds,
        }
        body = json.dumps(payload).encode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._token}",
        }

        # --- POST /v1/execute ---
        execute_url = f"{self._base_url}/v1/execute"
        post_delivered = False
        try:
            code, resp_body = self._client.request(
                "POST",
                execute_url,
                body=body,
                headers=headers,
                timeout=30.0,
            )
            post_delivered = True
        except ConnectionRefusedError as exc:
            # Pre-delivery failure: request never reached the agent.
            raise RuntimeError(
                "host agent unavailable: connection refused"
            ) from exc
        except TimeoutError as exc:
            # Pre-delivery failure: connect timeout.
            raise RuntimeError(
                "host agent unavailable: connection timed out"
            ) from exc
        except OSError as exc:
            # Ambiguous: could be post-delivery if TCP handshake had completed.
            # Treat as pre-delivery (safe) when we have no evidence of delivery.
            raise RuntimeError(
                f"host agent transport error before confirmation: {exc}"
            ) from exc

        if not post_delivered:
            # Should not be reached; defensive guard.
            raise RuntimeError("host agent execute did not complete")

        if code == 409:
            # Operation already in flight — surface as a conflict.
            raise RuntimeError(
                f"host agent conflict: operation {operation_id!r} is already in progress"
            )
        if code == 401:
            raise RuntimeError("host agent authentication failed")
        if code == 400:
            detail = resp_body.get("message", "bad request")
            raise RuntimeError(f"host agent rejected request: {detail}")
        if code not in {200, 202}:
            # Post-delivery ambiguous failure: agent may have started execution.
            LOGGER.warning(
                "host_agent execute returned %d — polling for status operation_id=%s",
                code, operation_id,
            )
            self._poll_with_recovery(operation_id, headers)
            return

        # 202 Accepted: agent received the request; poll for terminal result.
        self._poll_until_done(operation_id, headers)

    # ------------------------------------------------------------------
    # Polling helpers
    # ------------------------------------------------------------------

    def _poll_until_done(self, operation_id: str, headers: dict[str, str]) -> None:
        """Poll GET /v1/status/{operation_id} until a terminal result is returned.

        Raises ``RuntimeError`` on failure outcomes or transport errors.
        """
        status_url = f"{self._base_url}/v1/status/{operation_id}"
        for _ in range(_MAX_POLL_ATTEMPTS):
            try:
                code, body = self._client.request(
                    "GET", status_url, headers=headers, timeout=10.0
                )
            except OSError as exc:
                # Post-delivery transport error: try recovery polling.
                LOGGER.warning(
                    "host_agent status transport error operation_id=%s: %s — entering recovery",
                    operation_id, exc,
                )
                self._poll_with_recovery(operation_id, headers)
                return

            if code == 200:
                status = body.get("status")
                if status == "running":
                    time.sleep(_POLL_INTERVAL_SECONDS)
                    continue
                if status == "done":
                    self._handle_terminal_result(operation_id, body)
                    return

            if code == 404:
                raise RuntimeError(
                    f"host agent reports unknown operation {operation_id!r}; "
                    "the agent may have restarted — explicit confirmation required before retry"
                )
            # Unexpected response: attempt recovery.
            LOGGER.warning(
                "host_agent status returned unexpected %d operation_id=%s — entering recovery",
                code, operation_id,
            )
            self._poll_with_recovery(operation_id, headers)
            return

        raise RuntimeError(
            f"host agent did not return a terminal result within the polling window "
            f"for operation {operation_id!r}"
        )

    def _poll_with_recovery(self, operation_id: str, headers: dict[str, str]) -> None:
        """Retry GET /v1/status up to three times after a post-delivery failure.

        Per the host-agent contract, a ``404`` or repeated transport errors mean
        the outcome is ambiguous and explicit operator confirmation is required.
        """
        status_url = f"{self._base_url}/v1/status/{operation_id}"
        last_error: str = "unknown"
        for attempt in range(_POST_DELIVERY_RETRY_COUNT):
            if attempt > 0:
                time.sleep(_POST_DELIVERY_RETRY_INTERVAL_SECONDS)
            try:
                code, body = self._client.request(
                    "GET", status_url, headers=headers, timeout=10.0
                )
            except OSError as exc:
                last_error = str(exc)
                LOGGER.warning(
                    "host_agent recovery poll %d/%d transport error operation_id=%s: %s",
                    attempt + 1, _POST_DELIVERY_RETRY_COUNT, operation_id, exc,
                )
                continue
            if code == 200 and body.get("status") == "done":
                self._handle_terminal_result(operation_id, body)
                return
            if code == 200 and body.get("status") == "running":
                # Still running; back to normal polling.
                self._poll_until_done(operation_id, headers)
                return
            last_error = f"HTTP {code}: {body}"

        raise RuntimeError(
            f"host agent result is ambiguous for operation {operation_id!r}: "
            f"the operation may have partially executed — explicit confirmation required before retry. "
            f"Last error: {last_error}"
        )

    @staticmethod
    def _handle_terminal_result(operation_id: str, body: dict[str, Any]) -> None:
        """Raise ``RuntimeError`` on error outcomes; return normally on success."""
        outcome = body.get("outcome")
        if outcome == "ok":
            LOGGER.info(
                "host_agent operation completed successfully operation_id=%s executor_ref=%s",
                operation_id, body.get("executor_ref"),
            )
            return
        # outcome == "error"
        failed_stage = body.get("failed_stage") or "unknown"
        error_code = body.get("error_code") or "executor_internal_error"
        detail = body.get("detail") or "no detail provided"
        raise RuntimeError(
            f"host agent operation failed at stage {failed_stage!r}: {detail} "
            f"(error_code={error_code!r})"
        )
