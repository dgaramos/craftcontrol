"""Compatibility entry point for local Flask tooling.

Production loads ``wsgi:app``. Application code lives in the
``controlplane`` package.
"""

from src import create_app

app = create_app()
