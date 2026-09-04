"""Request-time access to dependencies composed during application startup."""

from __future__ import annotations

from flask import current_app

from ..runtime import ManagerService
from ..telemetry.installer import TelemetryPackInstaller


def manager() -> ManagerService:
    return current_app.extensions["manager_service"]


def telemetry_installer() -> TelemetryPackInstaller:
    mgr = manager()
    return TelemetryPackInstaller.bundled(mgr.files.env_file.parent, audit_service=mgr.audit_service)
