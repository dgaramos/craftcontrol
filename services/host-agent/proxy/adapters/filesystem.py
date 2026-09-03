"""BedrockFileSystem — concrete FileSystem adapter for server.properties."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from proxy.ports import FileSystem

logger = logging.getLogger("host-agent")


class BedrockFileSystem:
    """FileSystem adapter: merge-writes server.properties in the Bedrock data directory.

    Reads the existing file (if present), updates only the keys supplied in
    ``updates``, and preserves all other lines (comments, blank lines, unknown
    keys) in their original order. Existing files are updated in place so the
    Bedrock runtime retains their ownership, ACLs, and inode-based access
    contract. A new file is created atomically when none exists yet.
    """

    def __init__(
        self,
        bedrock_data: str,
        read_text: Callable[..., str] | None = None,
        write_text: Callable[..., Any] | None = None,
    ) -> None:
        self._data_dir = Path(bedrock_data)
        # Injectable for testing; defaults to Path.read_text behaviour.
        self._read_text: Callable[..., str] = read_text or (lambda p, **kw: p.read_text(**kw))
        self._write_text = write_text or (lambda p, text, **kw: p.write_text(text, **kw))

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

        rendered = "".join(merged)
        if props_file.exists():
            try:
                # The host agent normally runs under a different OS user than
                # the Bedrock container. Replacing this file would create a
                # new inode owned by the agent and can revoke the container's
                # write access. Keep the existing inode and its ACLs instead.
                with props_file.open("r+", encoding="utf-8") as handle:
                    handle.seek(0)
                    handle.write(rendered)
                    handle.truncate()
                    handle.flush()
                    os.fsync(handle.fileno())
            except OSError as exc:
                raise RuntimeError(f"Failed to write server.properties: {exc}") from exc

            logger.info("Wrote/updated %d properties in %s", len(updates), props_file)
            return

        tmp_file = props_file.with_suffix(".tmp")
        try:
            self._write_text(tmp_file, rendered, encoding="utf-8")
            tmp_file.replace(props_file)
        except OSError as exc:
            try:
                tmp_file.unlink(missing_ok=True)
            except OSError:
                pass
            raise RuntimeError(f"Failed to write server.properties: {exc}") from exc

        logger.info("Wrote/updated %d properties in %s", len(updates), props_file)


if TYPE_CHECKING:
    # Static check: BedrockFileSystem must satisfy the FileSystem Protocol.
    _: FileSystem = BedrockFileSystem.__new__(BedrockFileSystem)
