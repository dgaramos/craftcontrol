"""HTTP blueprints grouped by CraftControl domain."""

from .core import core_api
from .players import players_api
from .server import server_api
from .telemetry import telemetry_api

__all__ = ["core_api", "players_api", "server_api", "telemetry_api"]
