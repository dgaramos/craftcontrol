import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DeploymentSafetyTest(unittest.TestCase):
    def test_compose_mounts_explicit_application_boundaries(self) -> None:
        compose = (ROOT / "docker-compose.yml").read_text()
        self.assertIn("./apps/frontend/static:/app/apps/frontend/static:ro", compose)
        self.assertIn("./apps/frontend/templates:/app/apps/frontend/templates:ro", compose)
        self.assertIn("./apps/backend/minecraft_manager:/app/minecraft_manager:ro", compose)
        self.assertNotIn("./static:/app/static", compose)
        self.assertNotIn("./templates:/app/templates", compose)

    def test_deploy_command_anchors_compose_and_protects_state(self) -> None:
        script = (ROOT / "bin" / "deploy-craftcontrol").read_text()
        self.assertIn('docker compose --project-directory "$DEPLOY_ROOT"', script)
        self.assertIn('[[ "$(mount_source /data)" == "$DEPLOY_ROOT/data" ]]', script)
        self.assertIn('[[ "$(mount_source /minecraft-project)" == "$BEDROCK_ROOT" ]]', script)
        self.assertIn("craftcontrol backup create", script)
        self.assertIn("craftcontrol backup verify", script)
        self.assertIn('sha256sum "$ENV_FILE"', script)
        self.assertIn('sha256sum "$DATABASE_FILE"', script)
        self.assertIn("/api/auth/me", script)


if __name__ == "__main__":
    unittest.main()
