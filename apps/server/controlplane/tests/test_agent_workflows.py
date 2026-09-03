from __future__ import annotations

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


def test_agent_workflow_flag_has_project_and_patch_coverage_statuses() -> None:
    config = (ROOT / "codecov.yml").read_text()
    assert config.count("dr-agents:") == 3
    assert "- apps/server/tests/test_agent_workflows.py" in config
