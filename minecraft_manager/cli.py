from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import Settings
from .bedrock import BedrockClient
from .operations.backup import BackupService, docker_container_running
from .telemetry_installer import TelemetryPackInstaller


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
    return root


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    settings = Settings.from_env()
    if arguments.command == "backup":
        service = BackupService(
            settings.database,
            settings.project,
            settings.backup_root,
            BedrockClient(settings.container, [], settings.console_wait_seconds),
            lambda: docker_container_running(settings.container),
        )
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
    installer = TelemetryPackInstaller.bundled(project)
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
