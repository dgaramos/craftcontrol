from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]

DOCUMENTATION_DIAGRAMS = {
    "README.md": 5,
    "README.pt-BR.md": 5,
    "docs/architecture.md": 5,
    "docs/automated-deployment.md": 1,
    "docs/backup-and-restore.md": 1,
    "docs/development-setup.md": 1,
    "docs/installation.md": 1,
    "docs/installation.pt-BR.md": 1,
    "docs/operation-lifecycle.md": 1,
    "packs/telemetry/README.md": 2,
}


@pytest.fixture(scope="module")
def readme() -> str:
    return (ROOT / "README.md").read_text()


def test_readme_documents_current_monorepo_boundaries(readme: str) -> None:
    for path in ("apps/client/", "apps/server/", "packages/contracts/", "packs/telemetry/", "versions.env"):
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


def test_runtime_boundaries_use_craftcontrol_product_names(readme: str) -> None:
    for name in (
        "CraftControl Client",
        "CraftControl Server",
        "CraftControl Host Agent",
        "CraftControl Telemetry Pack",
    ):
        assert name in readme

    architecture = (ROOT / "docs" / "architecture.md").read_text()
    for name in (
        "CraftControl Client",
        "CraftControl Server",
        "CraftControl Host Agent",
        "CraftControl Telemetry Pack",
    ):
        assert name in architecture


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


def test_documentation_diagrams_use_mermaid_fences() -> None:
    for relative_path, expected_count in DOCUMENTATION_DIAGRAMS.items():
        document = (ROOT / relative_path).read_text()
        diagrams = re.findall(r"```mermaid\n(.*?)\n```", document, flags=re.DOTALL)

        assert len(diagrams) == expected_count, relative_path
        assert all(
            diagram.startswith(("flowchart ", "stateDiagram-v2", "sequenceDiagram", "classDiagram", "erDiagram", "journey", "gantt"))
            for diagram in diagrams
        ), relative_path


def test_documentation_has_no_legacy_text_diagrams() -> None:
    legacy_markers = ("┌", "┐", "└", "┘", "├", "┤", "─►")

    for relative_path in DOCUMENTATION_DIAGRAMS:
        document = (ROOT / relative_path).read_text()
        text_fences = re.findall(r"```text\n(.*?)\n```", document, flags=re.DOTALL)

        assert not any(marker in fence for fence in text_fences for marker in legacy_markers), relative_path
