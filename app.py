"""Compatibility entry point for local Flask tooling.

Production loads ``wsgi:app``. Application code lives in the
``minecraft_manager`` package.
"""

from minecraft_manager import create_app

app = create_app()
