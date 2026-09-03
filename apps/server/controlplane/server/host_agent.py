"""HTTP adapter implementing ContainerOperations via the CraftControl host agent.

The host agent runs on the Docker host outside all containers.  This adapter
replaces ``DockerOperations`` at the ``ContainerOperations`` boundary, routing
PREPARATION, RESTART, and HEALTH_WAIT stages through the agent instead of
calling Docker directly from inside the backend container.

See ``docs/bedrock-proxy-contract.md`` for the full API contract.
"""

from __future__ import annotations

import json
import logging
import math
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Protocol

from controlplane.core.schema import PROPERTY_NAMES

LOGGER = logging.getLogger(__name__)

# Maps backend uppercase schema keys (e.g. "GAMEMODE") to the host-agent's
# lowercase underscore field names (e.g. "gamemode").  Derived from the shared
# PROPERTY_NAMES table so there is one authoritative source for the mapping.
_SCHEMA_TO_AGENT_FIELD: dict[str, str] = {
    key: prop_name.replace("-", "_")
    for key, prop_name in PROPERTY_NAMES.items()
}


def _translate_intended_state(intended_state: dict[str, Any]) -> dict[str, Any]:
    """Translate backend schema keys to host-agent field names.

    The backend schema uses uppercase env-var style keys (e.g. ``GAMEMODE``,
    ``DIFFICULTY``).  The host-agent contract uses lowercase underscore keys
    (e.g. ``gamemode``, ``difficulty``).  This function maps across the
    boundary using the shared ``PROPERTY_NAMES`` table.

    Keys already in lowercase format are preserved unchanged via the
    ``_SCHEMA_TO_AGENT_FIELD.get(k, k)`` fallback, making the function
    idempotent for callers that already use the agent format.

    Raises ``ValueError`` when two keys in *intended_state* translate to the
    same target field with different values (e.g. ``"GAMEMODE"`` and
    ``"gamemode"`` both present but carrying different values).  Duplicate
    aliases with the same value are allowed and collapsed to one entry.
    """
    result: dict[str, Any] = {}
    for k, v in intended_state.items():
        target = _SCHEMA_TO_AGENT_FIELD.get(k, k)
        if target in result and result[target] != v:
            raise ValueError(
                f"intended_state contains conflicting values for field {target!r}: "
                f"keys {k!r} and an earlier equivalent key disagree"
            )
        result[target] = v
    return result


def _as_object(body: Any) -> dict[str, Any]:
    """Return *body* unchanged when it is a ``dict``; otherwise return ``{}``.

    The host agent always documents its successful responses as JSON objects,
    but network proxies, error pages, or unexpected agent builds may return a
    non-object JSON value (``null``, an array, a scalar).  Parsing those as-is
    and then calling ``.get()`` raises ``AttributeError``.  This helper
    normalises any non-dict body to an empty dict so every call site can use
    ``.get()`` safely without per-site type guards.
    """
    return body if isinstance(body, dict) else {}


class ReadTimeoutError(TimeoutError):
    """Raised when a read-phase timeout occurs after the TCP handshake completed.

    Unlike a connect-phase ``TimeoutError``, a ``ReadTimeoutError`` on a POST
    request means the request body was likely delivered to the server.  Callers
    must treat it as a post-delivery ambiguous failure and use recovery polling
    rather than surfacing an immediate pre-delivery error.
    """


# How long to wait between polling attempts after POST /v1/execute returns 202.
_POLL_INTERVAL_SECONDS = 5.0
# Maximum poll attempts while waiting for the agent to complete.
_MAX_POLL_ATTEMPTS = 120  # 120 * 5s = 10 minutes ceiling
# How many times to retry GET /v1/status after a post-delivery ambiguous failure.
_POST_DELIVERY_RETRY_COUNT = 3
_POST_DELIVERY_RETRY_INTERVAL_SECONDS = 5.0
# Absolute wall-clock ceiling for the combined poll+recovery cycle (seconds).
# Protects against unbounded mutual recursion between _poll_until_done and
# _poll_with_recovery when the agent alternates between "running" and unexpected
# responses.  Set to 15 minutes to cover the worst-case _MAX_POLL_ATTEMPTS window
# plus recovery headroom.
_GLOBAL_POLL_DEADLINE_SECONDS = 900.0


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
            ReadTimeoutError: when a timeout fires during the read phase,
                after the TCP handshake completed
                (post-delivery ambiguous — request was likely delivered).
            TimeoutError: when a connect timeout fires before TCP handshake
                (pre-delivery failure — request was never delivered).
            OSError: for all other transport-layer failures.  The caller must
                determine whether the request was delivered before failing.
        """
        ...  # pragma: no cover


class _UrllibClient:
    """Production HTTP client wrapping ``urllib.request``.

    An injectable *opener* callable can be supplied for testing; it defaults
    to ``urllib.request.urlopen``.  Tests should pass an explicit fake opener
    rather than monkey-patching the global.
    """

    def __init__(self, opener: Any = None) -> None:
        self._opener = opener if opener is not None else urllib.request.urlopen

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
            with self._opener(req, timeout=timeout) as resp:
                try:
                    raw = resp.read()
                except TimeoutError as exc:
                    # TCP handshake and request delivery completed; timeout
                    # occurred while reading the response body — treat as a
                    # read-phase (post-delivery ambiguous) failure.
                    raise ReadTimeoutError("read body timed out") from exc
                return resp.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            try:
                raw = exc.read()
            except TimeoutError as read_exc:
                raise ReadTimeoutError("read error body timed out") from read_exc
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
    replaces ``DockerOperations`` for lifecycle operations (PREPARATION, RESTART,
    HEALTH_WAIT) in the composition root.  A Docker socket mount is still required
    in all topologies because ``BedrockClient`` uses the Docker SDK directly for
    console operations and log streaming — those are not delegated to the agent.

    Authentication uses a shared secret read once at construction time.  No
    token value is written to logs, error messages, or API responses.

    Unavailability handling follows ``docs/bedrock-proxy-contract.md``:

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
        server_name: str = "minecraft-server",
        retry_interval: float = _POST_DELIVERY_RETRY_INTERVAL_SECONDS,
    ) -> None:
        if not math.isfinite(retry_interval) or retry_interval < 0:
            raise ValueError(
                f"retry_interval must be a non-negative finite number, got {retry_interval!r}"
            )
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._client: _HttpClient = http_client
        self._server_name = server_name
        self._retry_interval = retry_interval

    # ------------------------------------------------------------------
    # ContainerOperations interface
    # ------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """Return container-style status by querying the agent's Bedrock status endpoint.

        GET /v1/bedrock/status reports whether the Bedrock server container is
        running, which is distinct from agent process liveness (GET /v1/health).
        Any transport failure, non-200 response, or ``bedrock_running: false``
        body is mapped to "stopped" without raising.
        """
        url = f"{self._base_url}/v1/bedrock/status"
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            code, body = self._client.request("GET", url, headers=headers, timeout=10.0)
        except OSError:
            return {"online": False, "state": "stopped", "container": self._server_name}
        if code == 200 and _as_object(body).get("bedrock_running") is True:
            return {"online": True, "state": "running", "container": self._server_name}
        return {"online": False, "state": "stopped", "container": self._server_name}

    def execute(
        self,
        action: str,
        *,
        operation_id: str | None = None,
        intended_state: dict[str, Any] | None = None,
        health_timeout_seconds: int = 300,
        restart_timeout_seconds: int = 60,
    ) -> None:
        """Execute a server operation via the host agent.

        Only the ``"apply"`` and ``"restart"`` actions are supported; all
        others raise ``RuntimeError``.

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

        intended_state = _translate_intended_state(intended_state)

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
        except ReadTimeoutError:
            # Read-phase timeout: TCP handshake completed and request was sent,
            # but the response body read timed out.  The request was likely
            # delivered; poll for the operation status before declaring failure.
            LOGGER.warning(
                "host_agent POST /v1/execute read-phase timeout — "
                "entering recovery polling operation_id=%s",
                operation_id,
            )
            deadline = time.monotonic() + _GLOBAL_POLL_DEADLINE_SECONDS
            still_running = self._poll_with_recovery(operation_id, headers, deadline)
            if still_running:
                self._poll_until_done(operation_id, headers, deadline)
            return
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
            detail = _as_object(resp_body).get("message", "bad request")
            raise RuntimeError(f"host agent rejected request: {detail}")
        if code not in {200, 202}:
            # Post-delivery ambiguous failure: agent may have started execution.
            LOGGER.warning(
                "host_agent execute returned %d — polling for status operation_id=%s",
                code, operation_id,
            )
            deadline = time.monotonic() + _GLOBAL_POLL_DEADLINE_SECONDS
            still_running = self._poll_with_recovery(operation_id, headers, deadline)
            if still_running:
                self._poll_until_done(operation_id, headers, deadline)
            return

        # 202 Accepted: agent received the request; poll for terminal result.
        deadline = time.monotonic() + _GLOBAL_POLL_DEADLINE_SECONDS
        self._poll_until_done(operation_id, headers, deadline)

    # ------------------------------------------------------------------
    # Polling helpers
    # ------------------------------------------------------------------

    def _poll_until_done(
        self, operation_id: str, headers: dict[str, str], deadline: float
    ) -> None:
        """Poll GET /v1/status/{operation_id} until a terminal result is returned.

        *deadline* is an absolute ``time.monotonic()`` timestamp.  The method
        raises ``RuntimeError`` once the deadline is exceeded, bounding the
        polling cycle to the global ceiling set in ``_GLOBAL_POLL_DEADLINE_SECONDS``.

        When a transport error or unexpected status code is encountered, this
        method calls ``_poll_with_recovery`` and resumes its own loop if the
        operation is still running — there is no mutual recursion between the
        two helpers.

        Raises ``RuntimeError`` on failure outcomes or transport errors.
        """
        status_url = f"{self._base_url}/v1/status/{operation_id}"
        for _ in range(_MAX_POLL_ATTEMPTS):
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"host agent polling exceeded the global deadline for operation "
                    f"{operation_id!r} — explicit confirmation required before retry"
                )
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
                still_running = self._poll_with_recovery(operation_id, headers, deadline)
                if still_running:
                    time.sleep(_POLL_INTERVAL_SECONDS)
                    continue
                return

            if code == 200:
                status = _as_object(body).get("status")
                if status == "running":
                    time.sleep(_POLL_INTERVAL_SECONDS)
                    continue
                if status == "done":
                    self._handle_terminal_result(operation_id, _as_object(body))
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
            still_running = self._poll_with_recovery(operation_id, headers, deadline)
            if still_running:
                time.sleep(_POLL_INTERVAL_SECONDS)
                continue
            return

        raise RuntimeError(
            f"host agent did not return a terminal result within the polling window "
            f"for operation {operation_id!r}"
        )

    def _poll_with_recovery(
        self, operation_id: str, headers: dict[str, str], deadline: float
    ) -> bool:
        """Retry GET /v1/status up to three times after a post-delivery failure.

        Returns ``True`` if the operation is still running so that the caller
        (``_poll_until_done``) can resume its own loop.  Returns ``False`` after
        handling a terminal result via ``_handle_terminal_result``.  Raises
        ``RuntimeError`` when the outcome is ambiguous.

        This method never calls ``_poll_until_done`` — the polling loop always
        lives in the caller, eliminating mutual recursion.

        Per the host-agent contract, a ``404`` or repeated transport errors mean
        the outcome is ambiguous and explicit operator confirmation is required.
        """
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"host agent polling exceeded the global deadline for operation "
                f"{operation_id!r} — explicit confirmation required before retry"
            )
        status_url = f"{self._base_url}/v1/status/{operation_id}"
        last_error: str = "unknown"
        for attempt in range(_POST_DELIVERY_RETRY_COUNT):
            if attempt > 0:
                time.sleep(self._retry_interval)
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
            if code == 200 and _as_object(body).get("status") == "done":
                self._handle_terminal_result(operation_id, _as_object(body))
                return False
            if code == 200 and _as_object(body).get("status") == "running":
                # Still running; signal the caller to resume its own polling loop.
                return True
            last_error = f"HTTP {code}"

        raise RuntimeError(
            f"host agent result is ambiguous for operation {operation_id!r}: "
            f"the operation may have partially executed — explicit confirmation required before retry. "
            f"Last error: {last_error}"
        )

    @staticmethod
    def _handle_terminal_result(operation_id: str, body: dict[str, Any]) -> None:
        """Raise ``RuntimeError`` on error outcomes; return normally on success."""
        body = _as_object(body)
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
