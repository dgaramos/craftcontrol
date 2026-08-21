from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from .dependencies import manager
from ..auth.http import auth_service, require
from ..operations import ConflictingOperationError

server_api = Blueprint("server_api", __name__)


@server_api.put("/api/config")
@require("server.configure")
def update_config():
    try:
        changed = manager().save_settings(request.get_json(force=True))
    except ConflictingOperationError as error:
        return jsonify(error=str(error)), 409
    except (TypeError, ValueError) as error:
        return jsonify(error=str(error)), 400
    return jsonify(ok=True, restart_required=True, changed=changed)


@server_api.get("/api/status")
def status():
    return jsonify(manager().docker.status())


@server_api.post("/api/server/<action>")
def server_action(action: str):
    try:
        capability = {
            "start": "server.lifecycle.start", "restart": "server.lifecycle.restart",
            "apply": "server.configure", "stop": "server.lifecycle.stop",
        }.get(action)
        if capability is None:
            raise KeyError(action)
        auth_service().require_capability(g.user, capability)
        manager().docker.execute(action)
    except PermissionError:
        return jsonify(error="insufficient permission", capability=capability), 403
    except KeyError:
        return jsonify(error="Ação não permitida"), 404
    except RuntimeError as error:
        return jsonify(error=str(error)), 500
    return jsonify(ok=True, action=action)


@server_api.put("/api/gamerules/<rule>")
@require("world.manage")
def set_gamerule(rule: str):
    try:
        payload = request.get_json(force=True)
        value = manager().set_gamerule(rule, payload.get("value"))
    except KeyError:
        return jsonify(error="Gamerule não permitida"), 404
    except (AttributeError, TypeError, ValueError) as error:
        return jsonify(error=str(error)), 400
    except Exception as error:
        return jsonify(error=str(error)), 500
    return jsonify(ok=True, rule=rule, value=value)


@server_api.post("/api/world/<action>")
@require("world.manage")
def world_action(action: str):
    try:
        manager().run_world_action(action)
    except KeyError:
        return jsonify(error="Ação não permitida"), 404
    except Exception as error:
        return jsonify(error=str(error)), 500
    return jsonify(ok=True, action=action)


@server_api.post("/api/time/<action>")
@require("world.manage")
def time_action(action: str):
    try:
        result = manager().time_action(action, request.get_json(silent=True) or {})
    except KeyError:
        return jsonify(error="Ação não permitida"), 404
    except (TypeError, ValueError) as error:
        return jsonify(error=str(error)), 400
    except Exception as error:
        return jsonify(error=str(error)), 500
    return jsonify(ok=True, **result)
