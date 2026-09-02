from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from .config import Settings
from .server.console import BedrockClient
from .operations.backup import BackupService, docker_container_running
from .auth.service import AuthService
from .repository import StateRepository
from .telemetry.installer import TelemetryPackInstaller


class _Repository(Protocol):
    def initialize(self) -> None: ...


class _AuthService(Protocol):
    def bootstrap(self, player: str) -> str: ...
    def create_invitation(self, player: str, role: str) -> str: ...
    def create_recovery(self, player: str, lifetime: int) -> tuple[str, str]: ...


class _BackupService(Protocol):
    def create(self, world: str | None) -> Any: ...
    def list(self) -> Any: ...
    def verify(self, backup_id: str) -> Any: ...
    def prune(self, keep: int, *, confirmed: bool) -> Any: ...
    def restore(self, backup_id: str, *, confirmed: bool) -> Any: ...


class _Installer(Protocol):
    def status(self, world: str | None) -> Any: ...
    def install(self, world: str | None) -> Any: ...
    def disable(self, world: str | None) -> Any: ...
    def remove(self, world: str | None) -> Any: ...
    def rollback(self, backup: str | None) -> Any: ...


@dataclass
class CliDependencies:
    """Composition seam for the CLI: production defaults, replaceable in tests."""

    repository_factory: Callable[[Settings], _Repository] = field(
        default=lambda settings: StateRepository(settings.database)
    )
    auth_service_factory: Callable[[Settings], _AuthService] = field(
        default=lambda settings: AuthService(settings.database)
    )
    backup_service_factory: Callable[[Settings], _BackupService] = field(
        default=lambda settings: BackupService(
            settings.database,
            settings.project,
            settings.backup_root,
            BedrockClient(settings.container, [], settings.console_wait_seconds),
            lambda: docker_container_running(settings.container),
        )
    )
    installer_factory: Callable[[Settings, Path], _Installer] = field(
        default=lambda settings, project: TelemetryPackInstaller.bundled(project)
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="craftcontrol", description="CraftControl administration CLI")
    commands = root.add_subparsers(dest="command", required=True)
    telemetry = commands.add_parser("telemetry", help="Manage the CraftControl Telemetry Pack")
    actions = telemetry.add_subparsers(dest="action", required=True)
    for name in ("status", "install", "upgrade", "disable", "remove"):
        action = actions.add_parser(name)
        action.add_argument("--world")
        if name in {"remove"}:
            action.add_argument("--yes", action="store_true", help="Confirm removal of installed pack files")
    rollback = actions.add_parser("rollback")
    rollback.add_argument("--backup")
    rollback.add_argument("--yes", action="store_true", help="Confirm restoration of a previous pack backup")
    telemetry.add_argument("--project", type=Path, help=argparse.SUPPRESS)

    backup = commands.add_parser("backup", help="Create, verify, and restore coordinated backups")
    backup_actions = backup.add_subparsers(dest="action", required=True)
    create = backup_actions.add_parser("create")
    create.add_argument("--world")
    backup_actions.add_parser("list")
    verify = backup_actions.add_parser("verify")
    verify.add_argument("backup_id")
    prune = backup_actions.add_parser("prune")
    prune.add_argument("--keep", type=int, default=7)
    prune.add_argument("--yes", action="store_true", help="Delete backups beyond the retention count")
    restore = backup_actions.add_parser("restore")
    restore.add_argument("backup_id")
    restore.add_argument("--yes", action="store_true", help="Confirm offline replacement of world and manager database")

    auth = commands.add_parser("auth", help="Bootstrap and recover local panel access")
    auth_actions = auth.add_subparsers(dest="action", required=True)
    bootstrap = auth_actions.add_parser("bootstrap")
    bootstrap.add_argument("--player")
    invite = auth_actions.add_parser("invite")
    invite.add_argument("player")
    invite.add_argument("--role", choices=("owner", "operator", "viewer"), default="viewer")
    recover = auth_actions.add_parser("recover")
    recover.add_argument("player")
    return root


def main(
    argv: list[str] | None = None,
    *,
    settings: Settings | None = None,
    deps: CliDependencies | None = None,
) -> int:
    arguments = parser().parse_args(argv)
    settings = settings or Settings.from_env()
    deps = deps or CliDependencies()
    if arguments.command == "auth":
        deps.repository_factory(settings).initialize()
        service = deps.auth_service_factory(settings)
        if arguments.action == "bootstrap":
            player = arguments.player or settings.bootstrap_operator
            if not player:
                raise SystemExit("Pass --player or configure BOOTSTRAP_OPERATOR")
            token = service.bootstrap(player)
            result = {"action": "bootstrap", "player": player, "role": "owner", "token": token, "expires_in": 1800}
        elif arguments.action == "invite":
            token = service.create_invitation(arguments.player, arguments.role)
            result = {"action": "invite", "player": arguments.player, "role": arguments.role, "token": token, "expires_in": 900}
        elif arguments.action == "recover":
            token, role = service.create_recovery(arguments.player, lifetime=900)
            result = {"action": "recover", "player": arguments.player, "role": role, "token": token, "expires_in": 900}
        else:
            raise SystemExit("Unsupported auth action")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if arguments.command == "backup":
        service = deps.backup_service_factory(settings)
        if arguments.action == "create":
            result = service.create(arguments.world)
        elif arguments.action == "list":
            result = {"backups": service.list()}
        elif arguments.action == "verify":
            result = service.verify(arguments.backup_id)
        elif arguments.action == "prune":
            result = service.prune(arguments.keep, confirmed=arguments.yes)
        elif arguments.action == "restore":
            if not arguments.yes:
                raise SystemExit("Refusing to restore without --yes")
            result = service.restore(arguments.backup_id, confirmed=True)
        else:
            raise SystemExit("Unsupported backup action")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    project = arguments.project or settings.project
    installer = deps.installer_factory(settings, project)
    if arguments.action == "status":
        result = {"changed": False, "action": "status", "status": installer.status(arguments.world).to_dict()}
    elif arguments.action in {"install", "upgrade"}:
        result = installer.install(arguments.world)
        result["action"] = arguments.action
    elif arguments.action == "disable":
        result = installer.disable(arguments.world)
    elif arguments.action == "remove":
        if not arguments.yes:
            raise SystemExit("Refusing to remove pack files without --yes")
        result = installer.remove(arguments.world)
    elif arguments.action == "rollback":
        if not arguments.yes:
            raise SystemExit("Refusing to restore a backup without --yes")
        result = installer.rollback(arguments.backup)
    else:
        raise SystemExit("Unsupported telemetry action")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
