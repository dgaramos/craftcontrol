"""HTTP blueprints grouped by CraftControl domain."""

from .players import players_api
from .telemetry import telemetry_api

__all__ = ["players_api", "telemetry_api"]
