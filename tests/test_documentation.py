from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def readme() -> str:
    return (ROOT / "README.md").read_text()


def test_readme_documents_current_monorepo_boundaries(readme: str) -> None:
    for path in ("apps/frontend/", "apps/backend/", "packages/contracts/", "packs/telemetry/", "versions.env"):
        assert path in readme
    for boundary in ("composition.js", "core/", "components/", "features/", "i18n/"):
        assert boundary in readme
    assert "modular monolith" in readme
    assert "compatibility overlay" in readme


def test_readme_surfaces_stack_contract_and_quality_badges(readme: str) -> None:
    for badge in ("Quality gates", "Python 3.12", "Flask 3", "SQLite", "Docker Compose", "Nginx", "JavaScript ES modules", "OpenAPI 3.1", "Swagger UI"):
        assert f'alt="{badge}"' in readme
    assert "actions/workflows/quality.yml/badge.svg?branch=main" in readme


def test_readme_documents_runtime_contract_and_security(readme: str) -> None:
    for claim in ("OpenAPI 3.1", "Swagger UI", "same-origin", "Server-Sent Events", "CSRF", "one Gunicorn worker"):
        assert claim in readme
    assert "Portuguese, English, and Spanish" in readme
    assert "Snapshots can recover lifetime aggregates" in readme


def test_readme_documents_independent_operations_and_safe_installation(readme: str) -> None:
    for command in (
        "bin/deploy-craftcontrol-frontend",
        "bin/deploy-craftcontrol-backend",
        "bin/deploy-craftcontrol-release",
        "bin/cutover-craftcontrol-split",
        "bin/check-frontend",
        "bin/check-backend",
        "bin/check-contracts",
        "bin/check-integration",
    ):
        assert command in readme
    assert "Never run a bare `docker compose up`" in readme
    assert "The immediate direction is:" not in readme


def test_local_reviewer_profile_is_shared_by_codex_and_claude() -> None:
    profile = ROOT / ".agent-review/craftcontrol/PROFILE.md"
    assert profile.is_file()

    for checklist in ("backend.md", "frontend.md", "contracts.md", "operations.md", "contribution.md"):
        assert (profile.parent / "references" / checklist).is_file()

    for entry_point in (
        ROOT / ".agents/skills/review-pr/SKILL.md",
        ROOT / ".claude/agents/review-pr/SKILL.md",
        ROOT / ".claude/agents/review-pr.md",
        ROOT / "AGENTS.md",
        ROOT / "CLAUDE.md",
    ):
        assert ".agent-review/craftcontrol/PROFILE.md" in entry_point.read_text()
