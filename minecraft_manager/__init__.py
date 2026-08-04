from __future__ import annotations

from flask import Flask

from .config import Settings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .services import ManagerService


def create_app(settings: Settings | None = None, service: ManagerService | None = None) -> Flask:
    from .composition import compose_manager
    from .routes import api

    settings = settings or Settings.from_env()
    service = service or compose_manager(settings)
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config["APP_NAME"] = "CraftControl"
    app.extensions["manager_service"] = service
    app.register_blueprint(api)
    service.initialize()
    return app
