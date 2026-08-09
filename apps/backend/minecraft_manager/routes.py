"""Compatibility blueprint aggregating domain HTTP modules.

Public URLs remain unchanged while route ownership lives under minecraft_manager.http.
"""

from flask import Blueprint

from .http import analytics_api, core_api, docs_api, players_api, server_api, telemetry_api

api = Blueprint("api", __name__)
api.register_blueprint(core_api)
api.register_blueprint(docs_api)
api.register_blueprint(players_api)
api.register_blueprint(server_api)
api.register_blueprint(telemetry_api)
api.register_blueprint(analytics_api)

__all__ = ["api"]
