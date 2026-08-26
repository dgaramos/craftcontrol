from __future__ import annotations

from flask import Flask
from pathlib import Path

from .config import Settings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .services import ManagerService


def frontend_root(package_root: Path | None = None) -> Path:
    """Resolve frontend assets in both the monorepo and packaged image layouts."""
    package_root = package_root or Path(__file__).resolve().parent
    if package_root.parent.name == "server":
        return package_root.parent.parent / "client"
    return package_root.parent / "apps" / "client"


def create_app(settings: Settings | None = None, service: ManagerService | None = None) -> Flask:
    from .composition import compose_manager
    from .auth.http import auth_api, install_auth
    from .auth.service import AuthService
    from .routes import api

    settings = settings or Settings.from_env()
    service = service or compose_manager(settings)
    frontend = frontend_root()
    app = Flask(
        __name__,
        template_folder=str(frontend / "templates"),
        static_folder=str(frontend / "static"),
    )
    app.config["APP_NAME"] = "CraftControl"
    app.extensions["manager_service"] = service
    install_auth(app, AuthService(settings.database), settings.auth_mode, settings.auth_cookie_secure)
    app.register_blueprint(auth_api)
    app.register_blueprint(api)
    service.initialize()
    return app
