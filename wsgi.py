"""Compatibility entry point for the legacy ``wsgi:app`` target."""

from apps.backend.wsgi import app

__all__ = ["app"]
