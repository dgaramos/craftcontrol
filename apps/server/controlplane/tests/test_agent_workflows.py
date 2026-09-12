from __future__ import annotations

import re
from glob import glob
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


PROFILE = ROOT / ".dr-agents" / "craftcontrol" / "PROFILE.md"
WORKFLOWS_DIR = ROOT / ".github" / "workflows"

# A publisher stub filename is exactly ``publish-<lowercase-token>.yml``. The
# pattern is strict on purpose: a file that looks like a stub but does not match
# this shape -- a name containing a space, for instance -- is not a name any
# profile could declare, so it belongs to neither direction and is neither
# counted nor reported. The anchor also excludes ``reusable-publish-*.yml``,
# which stubs call and which are never dispatched as publishers themselves.
_STUB_NAME = re.compile(r"^publish-[a-z0-9-]+\.yml$")

# Candidates are matched with a leading run of name characters so a token inside
# ``reusable-publish-review.yml`` yields the full name and is then rejected by
# the anchored filter, instead of matching the ``publish-review.yml`` substring
# and counting as a declaration.
_CANDIDATE = re.compile(r"[a-z0-9-]*publish-[a-z0-9-]+\.yml")


def _declared_publishers() -> set[str]:
    return {n for n in _CANDIDATE.findall(PROFILE.read_text()) if _STUB_NAME.fullmatch(n)}


def _installed_publishers() -> set[str]:
    return {
        path.name
        for path in WORKFLOWS_DIR.iterdir()
        if path.is_file() and _STUB_NAME.fullmatch(path.name)
    }


def test_publisher_dispatch_sets_are_not_empty() -> None:
    """Guard against a silently-matching-nothing parser passing both directions."""
    assert PROFILE.is_file(), f"missing reviewer profile: {PROFILE}"
    assert WORKFLOWS_DIR.is_dir(), f"missing workflows directory: {WORKFLOWS_DIR}"
    assert _declared_publishers(), "no publisher workflows declared in the profile"
    assert _installed_publishers(), f"no publisher workflows installed in {WORKFLOWS_DIR}"


def test_every_declared_publisher_is_installed() -> None:
    """Forward direction: the profile may not name a publisher that is absent."""
    missing = sorted(_declared_publishers() - _installed_publishers())
    assert not missing, (
        "declared in profile but not installed in .github/workflows/: " + ", ".join(missing)
    )


def test_every_installed_publisher_is_declared() -> None:
    """Reverse direction: an installed publisher may not go undeclared.

    This is the direction that matters. A forward-only check -- such as the
    fixed-subset assertion this replaced -- stays green through exactly the
    drift it exists to catch.
    """
    undeclared = sorted(_installed_publishers() - _declared_publishers())
    assert not undeclared, (
        "installed in .github/workflows/ but not declared in profile: " + ", ".join(undeclared)
    )


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
