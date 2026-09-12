from __future__ import annotations

from glob import glob
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


def test_reviewer_profile_declares_publishing_contract() -> None:
    profile = (ROOT / ".dr-agents" / "craftcontrol" / "PROFILE.md").read_text()
    for manifest in ("replies_json", "resolve_thread_ids_json", "inline_comments_json"):
        assert manifest in profile
    for expected in (
        "Cody DR | reply | available", "Cody DR | resolve-thread | available",
        "a personal GitHub account may publish only as a disclosed fallback when the requested App operation is unconfigured or unavailable before dispatch",
        "Without explicit user authorization, return publication-ready",
        "publish-cody-review.yml", "publish-claudio-review.yml",
    ):
        assert expected in profile


def test_local_reviewer_profile_is_referenced_by_project_entry_points() -> None:
    profile = ROOT / ".dr-agents/craftcontrol/PROFILE.md"
    assert profile.is_file()
    profile_text = profile.read_text()
    assert "AGENTS.md" in profile_text
    assert "Portuguese, English, and Spanish" in (ROOT / "AGENTS.md").read_text()
    for section in ("Backend", "Frontend", "Contracts", "Operations"):
        assert section in profile_text
    for entry_point in (ROOT / "AGENTS.md", ROOT / "CLAUDE.md"):
        assert ".dr-agents/craftcontrol/PROFILE.md" in entry_point.read_text()
    assert not (ROOT / ".agents/skills/review-pr/SKILL.md").exists()


def test_local_agents_do_not_shadow_global_lifecycle_skills() -> None:
    for agent in (ROOT / ".claude" / "agents").glob("*.md"):
        text = agent.read_text()
        if "---" not in text:
            continue
        frontmatter = text.split("---", maxsplit=2)[1].strip().splitlines()
        declared = [line.strip()[2:] for line in frontmatter if line.startswith("  - ")]
        assert not any(skill.startswith("claudio-dr:") for skill in declared)
    lifecycle = {"create-issue", "execute-issue", "handle-pr-findings", "implement", "review-pr", "ship-issue", "start-issue"}
    local_entries = {path.parent.name for path in (ROOT / ".agents" / "skills").glob("*/SKILL.md")}
    assert lifecycle.isdisjoint(local_entries)


def _top_level_block(config: str, key: str) -> list[str]:
    """Return the lines nested under a column-0 ``key:`` in a YAML document."""
    lines = config.splitlines()
    for index, line in enumerate(lines):
        if line == f"{key}:":
            break
    else:
        raise AssertionError(f"codecov.yml declares no top-level {key!r} block")
    block: list[str] = []
    for line in lines[index + 1 :]:
        if line and not line[0].isspace():
            break
        block.append(line)
    return block


def _declared_flag_paths(config: str) -> dict[str, list[str]]:
    """Map each flag declared in the top-level ``flags:`` block to its paths."""
    flags: dict[str, list[str]] = {}
    current: str | None = None
    for line in _top_level_block(config, "flags"):
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        if indent == 2 and stripped.endswith(":"):
            current = stripped[:-1]
            flags[current] = []
        elif stripped.startswith("- ") and current is not None:
            flags[current].append(stripped[2:].strip())
    return flags


def _coverage_status_names(config: str) -> set[str]:
    """Return every status name declared under ``coverage.status.*``."""
    names: set[str] = set()
    in_status = False
    for line in _top_level_block(config, "coverage"):
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        if indent == 2:
            in_status = stripped == "status:"
        elif indent == 6 and in_status and stripped.endswith(":"):
            names.add(stripped[:-1])
    return names


def test_dr_agents_flag_path_tracks_this_test_module_location() -> None:
    """The declared path is derived from this file, so the two cannot drift."""
    config = (ROOT / "codecov.yml").read_text()
    own_path = Path(__file__).resolve().relative_to(ROOT).as_posix()
    assert _declared_flag_paths(config)["dr-agents"] == [own_path]


def test_every_declared_codecov_flag_path_exists_in_the_working_tree() -> None:
    missing = {
        flag: path
        for flag, paths in _declared_flag_paths((ROOT / "codecov.yml").read_text()).items()
        for path in paths
        if not glob(str(ROOT / path)) and not glob(str(ROOT / path.rstrip("/")))
    }
    assert not missing, f"codecov.yml flag paths match no file: {missing}"


def test_dr_agents_gate_emits_no_coverage_and_codecov_declares_no_target() -> None:
    """These tests read configuration files; no importable module is measured."""
    gate = (ROOT / "bin" / "check-dr-agents").read_text()
    assert "--cov" not in gate
    assert "dr-agents" not in _coverage_status_names((ROOT / "codecov.yml").read_text())
