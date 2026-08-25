"""BedrockFileSystem — concrete FileSystem adapter for server.properties."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from ports import FileSystem

logger = logging.getLogger("host-agent")


class BedrockFileSystem:
    """FileSystem adapter: merge-writes server.properties in the Bedrock data directory.

    Reads the existing file (if present), updates only the keys supplied in
    ``updates``, and preserves all other lines (comments, blank lines, unknown
    keys) in their original order.  The write is made atomic via a ``.tmp``
    rename so a crash mid-write never corrupts the original file.
    """

    def __init__(
        self,
        bedrock_data: str,
        read_text: Callable[..., str] | None = None,
    ) -> None:
        self._data_dir = Path(bedrock_data)
        # Injectable for testing; defaults to Path.read_text behaviour.
        self._read_text: Callable[..., str] = read_text or (lambda p, **kw: p.read_text(**kw))

    def write_server_properties(self, updates: dict[str, str]) -> None:
        """Merge *updates* (prop_key → rendered value) into server.properties."""
        if not updates:
            logger.info("No configuration fields to write in prepare stage")
            return

        data_dir = self._data_dir
        props_file = data_dir / "server.properties"

        if not data_dir.is_dir():
            raise RuntimeError(f"Bedrock data directory not found: {data_dir}")

        # Read existing file to preserve unknown keys and comments.
        existing_lines: list[str] = []
        if props_file.exists():
            try:
                raw = self._read_text(props_file, encoding="utf-8")
                existing_lines = raw.splitlines(keepends=True)
            except OSError as exc:
                raise RuntimeError(
                    f"Cannot read existing server.properties; aborting to avoid data loss: {exc}"
                ) from exc

        # Merge: replace lines whose key appears in updates; collect written keys.
        merged: list[str] = []
        written: set[str] = set()
        for line in existing_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k = stripped.split("=", 1)[0].strip()
                if k in updates:
                    merged.append(f"{k}={updates[k]}\n")
                    written.add(k)
                    continue
            merged.append(line if line.endswith("\n") else line + "\n" if line else line)

        # Append keys not found in the existing file.
        for k, v in updates.items():
            if k not in written:
                merged.append(f"{k}={v}\n")

        tmp_file = props_file.with_suffix(".tmp")
        original_mode = props_file.stat().st_mode if props_file.exists() else 0o644
        try:
            tmp_file.write_text("".join(merged), encoding="utf-8")
            tmp_file.chmod(original_mode)
            tmp_file.replace(props_file)
        except OSError as exc:
            try:
                tmp_file.unlink(missing_ok=True)
            except OSError:
                pass
            raise RuntimeError(f"Failed to write server.properties: {exc}") from exc

        logger.info("Wrote/updated %d properties in %s", len(updates), props_file)


# Satisfy the structural Protocol check at import time.
_: FileSystem = BedrockFileSystem.__new__(BedrockFileSystem)
