"""HTTP blueprints grouped by CraftControl domain."""

from flask import Blueprint

from .analytics import analytics_api
from .audit import audit_api
from .core import core_api
from .docs import docs_api
from .operations import operations_api
from .players import players_api
from .server import server_api
from .telemetry import telemetry_api

api = Blueprint("api", __name__)
api.register_blueprint(core_api)
api.register_blueprint(docs_api)
api.register_blueprint(operations_api)
api.register_blueprint(players_api)
api.register_blueprint(server_api)
api.register_blueprint(telemetry_api)
api.register_blueprint(analytics_api)
api.register_blueprint(audit_api)

__all__ = ["analytics_api", "audit_api", "api", "core_api", "docs_api", "operations_api", "players_api", "server_api", "telemetry_api"]
