from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import Settings
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
    return root


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    project = arguments.project or Settings.from_env().project
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
