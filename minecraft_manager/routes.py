from __future__ import annotations

from flask import Blueprint, current_app, jsonify, render_template, request

from .schema import GAMERULES, SETTINGS
from .services import ManagerService

api = Blueprint("api", __name__)


def service() -> ManagerService:
    return current_app.extensions["manager_service"]


@api.get("/")
def index() -> str:
    return render_template("index.html")


@api.get("/api/schema")
def schema():
    return jsonify(settings=SETTINGS, gamerules=GAMERULES)


@api.get("/api/config")
def config():
    current = service().state()["settings"]
    if not current:
        service().refresh()
        current = service().state()["settings"]
    return jsonify(current)


@api.get("/api/state")
def state():
    return jsonify(service().state())


@api.post("/api/refresh")
def refresh():
    service().refresh_async()
    return jsonify(ok=True, refreshing=True), 202


@api.put("/api/config")
def update_config():
    try:
        changed = service().save_settings(request.get_json(force=True))
    except (TypeError, ValueError) as error:
        return jsonify(error=str(error)), 400
    return jsonify(ok=True, restart_required=True, changed=changed)


@api.get("/api/status")
def status():
    return jsonify(service().docker.status())


@api.post("/api/server/<action>")
def server_action(action: str):
    try:
        service().docker.execute(action)
    except KeyError:
        return jsonify(error="Ação não permitida"), 404
    except RuntimeError as error:
        return jsonify(error=str(error)), 500
    return jsonify(ok=True, action=action)


@api.put("/api/gamerules/<rule>")
def set_gamerule(rule: str):
    try:
        payload = request.get_json(force=True)
        value = service().set_gamerule(rule, payload.get("value"))
    except KeyError:
        return jsonify(error="Gamerule não permitida"), 404
    except (AttributeError, TypeError, ValueError) as error:
        return jsonify(error=str(error)), 400
    except Exception as error:
        return jsonify(error=str(error)), 500
    return jsonify(ok=True, rule=rule, value=value)


@api.post("/api/world/<action>")
def world_action(action: str):
    try:
        service().run_world_action(action)
    except KeyError:
        return jsonify(error="Ação não permitida"), 404
    except Exception as error:
        return jsonify(error=str(error)), 500
    return jsonify(ok=True, action=action)


@api.post("/api/time/<action>")
def time_action(action: str):
    try:
        result = service().time_action(action, request.get_json(silent=True) or {})
    except KeyError:
        return jsonify(error="Ação não permitida"), 404
    except (TypeError, ValueError) as error:
        return jsonify(error=str(error)), 400
    except Exception as error:
        return jsonify(error=str(error)), 500
    return jsonify(ok=True, **result)
