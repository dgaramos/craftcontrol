from __future__ import annotations

from flask import Blueprint, jsonify, request

from .dependencies import manager

analytics_api = Blueprint("analytics_api", __name__)


@analytics_api.get("/api/analytics/activity")
def activity():
    try:
        result = manager().player_activity(
            request.args.get("kind", "all"),
            request.args.get("player", ""),
            request.args.get("source", "all"),
            request.args.get("search", ""),
            int(request.args.get("days", "0")),
            int(request.args.get("page", "1")),
            int(request.args.get("page_size", "25")),
        )
        return jsonify(result)
    except (TypeError, ValueError) as error:
        return jsonify(error=str(error)), 400


@analytics_api.get("/api/analytics/rankings")
def rankings():
    try:
        return jsonify(manager().player_rankings(int(request.args.get("limit", "10"))))
    except (TypeError, ValueError) as error:
        return jsonify(error=str(error)), 400


@analytics_api.get("/api/analytics/blocks")
def blocks():
    try:
        return jsonify(manager().block_analytics(int(request.args.get("limit", "10"))))
    except (TypeError, ValueError) as error:
        return jsonify(error=str(error)), 400


@analytics_api.get("/api/analytics/combat")
def combat():
    try:
        return jsonify(manager().combat_analytics(int(request.args.get("limit", "10"))))
    except (TypeError, ValueError) as error:
        return jsonify(error=str(error)), 400


@analytics_api.get("/api/analytics/exploration")
def exploration():
    try:
        return jsonify(manager().exploration_analytics(int(request.args.get("limit", "10"))))
    except (TypeError, ValueError) as error:
        return jsonify(error=str(error)), 400


@analytics_api.get("/api/analytics/periods")
def periods():
    try:
        days = int(request.args.get("days", "30"))
        limit = int(request.args.get("limit", "10"))
        if not (1 <= days <= 365):
            return jsonify(error="days must be between 1 and 365"), 400
        if not (1 <= limit <= 100):
            return jsonify(error="limit must be between 1 and 100"), 400
        return jsonify(manager().period_analytics(days, limit))
    except (TypeError, ValueError) as error:
        return jsonify(error=str(error)), 400
