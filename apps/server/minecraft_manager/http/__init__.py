"""HTTP blueprints grouped by CraftControl domain."""

from .core import core_api
from .docs import docs_api
from .operations import operations_api
from .players import players_api
from .server import server_api
from .telemetry import telemetry_api
from .analytics import analytics_api

__all__ = ["analytics_api", "core_api", "docs_api", "operations_api", "players_api", "server_api", "telemetry_api"]
