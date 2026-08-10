import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublicDocumentationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.readme = (ROOT / "README.md").read_text()

    def test_readme_documents_current_monorepo_boundaries(self) -> None:
        for path in ("apps/frontend/", "apps/backend/", "packages/contracts/", "packs/telemetry/", "versions.env"):
            self.assertIn(path, self.readme)
        for boundary in ("composition.js", "core/", "components/", "features/", "i18n/"):
            self.assertIn(boundary, self.readme)
        self.assertIn("modular monolith", self.readme)
        self.assertIn("compatibility overlay", self.readme)

    def test_readme_surfaces_stack_contract_and_quality_badges(self) -> None:
        for badge in ("Quality gates", "Python 3.12", "Flask 3", "SQLite", "Docker Compose", "Nginx", "JavaScript ES modules", "OpenAPI 3.1", "Swagger UI"):
            self.assertIn(f'alt="{badge}"', self.readme)
        self.assertIn("actions/workflows/quality.yml/badge.svg?branch=main", self.readme)

    def test_readme_documents_runtime_contract_and_security(self) -> None:
        for claim in ("OpenAPI 3.1", "Swagger UI", "same-origin", "Server-Sent Events", "CSRF", "one Gunicorn worker"):
            self.assertIn(claim, self.readme)
        self.assertIn("Portuguese, English, and Spanish", self.readme)
        self.assertIn("Snapshots can recover lifetime aggregates", self.readme)

    def test_readme_documents_independent_operations_and_safe_installation(self) -> None:
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
            self.assertIn(command, self.readme)
        self.assertIn("Never run a bare `docker compose up`", self.readme)
        self.assertNotIn("The immediate direction is:", self.readme)


if __name__ == "__main__":
    unittest.main()
