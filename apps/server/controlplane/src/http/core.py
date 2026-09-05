from __future__ import annotations

import json

from flask import Blueprint, Response, jsonify, render_template, request, stream_with_context

from ..core.schema import GAMERULES, SETTINGS
from ..core.events import StreamCapacityError
from ..auth.http import require
from .dependencies import manager

core_api = Blueprint("core_api", __name__)


@core_api.get("/api/health")
def health():
    """Answer the container health check without touching runtime state."""
    return jsonify(ok=True)


@core_api.get("/")
def index() -> str:
    return render_template("index.html")


@core_api.get("/api/schema")
def schema():
    return jsonify(settings=SETTINGS, gamerules=GAMERULES)


@core_api.get("/api/config")
def config():
    current = manager().state()["settings"]
    if not current:
        manager().refresh()
        current = manager().state()["settings"]
    return jsonify(current)


@core_api.get("/api/state")
def state():
    return jsonify(manager().public_state())


@core_api.post("/api/refresh")
@require("server.configure")
def refresh():
    manager().refresh_async(reason="manual")
    return jsonify(ok=True, refreshing=True), 202


@core_api.get("/api/events")
def events():
    """Open a bounded SSE stream, preserving capacity for ordinary API calls."""
    try:
        after_id = int(request.headers.get("Last-Event-ID", "0") or 0)
    except ValueError:
        after_id = 0

    try:
        stream = manager().broker.stream(after_id)
    except StreamCapacityError:
        return jsonify(error="SSE connection capacity reached"), 503

    @stream_with_context
    def generate():
        for event in stream:
            if event is None:
                yield ": keepalive\n\n"
                continue
            payload = json.dumps({
                "topic": event.topic,
                "timestamp": event.timestamp,
                "source": event.source,
                "payload": event.payload,
            }, ensure_ascii=False)
            yield f"id: {event.id}\nevent: state\ndata: {payload}\n\n"

    response = Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })
    close = getattr(stream, "close", None)
    if close:
        response.call_on_close(close)
    return response
