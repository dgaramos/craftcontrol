from __future__ import annotations

from flask import Blueprint, jsonify, request

from .dependencies import manager

players_api = Blueprint("players_api", __name__)


@players_api.get("/api/players")
def players():
    return jsonify(players=manager().players())


@players_api.get("/api/players/profile/<path:identity>")
def player_profile(identity: str):
    profile = manager().player_profile(identity)
    if profile is None:
        return jsonify(error="Jogador não encontrado"), 404
    return jsonify(profile)


@players_api.put("/api/players/<player>/operator")
def player_operator(player: str):
    try:
        payload = request.get_json(force=True)
        enabled = payload.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("valor booleano inválido")
        manager().set_player_operator(player, enabled)
    except (AttributeError, TypeError, ValueError) as error:
        return jsonify(error=str(error)), 400
    except Exception as error:
        return jsonify(error=str(error)), 500
    return jsonify(ok=True, player=player, operator=enabled)
