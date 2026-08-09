import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DeploymentSafetyTest(unittest.TestCase):
    def test_quality_gates_are_partitioned_and_automated(self) -> None:
        gates = ["frontend", "backend", "contracts", "integration"]
        for gate in gates:
            script = ROOT / "bin" / f"check-{gate}"
            self.assertTrue(script.is_file())
            self.assertIn(f"{gate} gate: ok", script.read_text())
        umbrella = (ROOT / "bin" / "check").read_text()
        self.assertIn("frontend backend contracts integration", umbrella)
        for workflow in (ROOT / ".github" / "workflows" / "quality.yml", ROOT / ".gitea" / "workflows" / "quality.yml"):
            self.assertTrue(workflow.is_file())
            self.assertIn("gate: [frontend, backend, contracts, integration]", workflow.read_text())

    def test_split_runtime_gate_uses_only_disposable_state(self) -> None:
        canary = (ROOT / "bin" / "check-split-runtime").read_text()
        self.assertIn("DATABASE_PATH=/tmp/manager.db", canary)
        self.assertIn("MINECRAFT_PROJECT=/tmp", canary)
        self.assertNotIn("/var/run/docker.sock", canary)
        self.assertIn("Content-Type: text/event-stream", canary)
        self.assertIn("X-Accel-Buffering: no", canary)
        self.assertIn("wait_removed", canary)
        self.assertIn("versions.env", canary)
        self.assertIn("/version.json", canary)

    def test_frontend_deploy_is_independent_guarded_and_reversible(self) -> None:
        script = (ROOT / "bin" / "deploy-craftcontrol-frontend").read_text()
        versions = (ROOT / "versions.env").read_text()
        self.assertIn("CRAFTCONTROL_FRONTEND_VERSION=0.1.2", versions)
        self.assertIn("CRAFTCONTROL_BACKEND_VERSION=0.1.0", versions)
        self.assertIn("split production topology is not active", script)
        self.assertIn("up -d --no-deps craftcontrol-frontend", script)
        self.assertIn("--rollback VERSION", script)
        self.assertIn("backend was recreated", script)
        self.assertIn("persistent data mount", script)
        self.assertIn("/version.json", script)

    def test_backend_deploy_is_backed_up_independent_and_reversible(self) -> None:
        script = (ROOT / "bin" / "deploy-craftcontrol-backend").read_text()
        self.assertIn("split production topology is not active", script)
        self.assertIn("craftcontrol backup create", script)
        self.assertIn("craftcontrol backup verify", script)
        self.assertIn("PRAGMA quick_check", script)
        self.assertIn("up -d --no-deps craftcontrol-backend", script)
        self.assertIn("frontend was recreated", script)
        self.assertIn("--rollback VERSION", script)
        self.assertIn("Bedrock is not healthy", script)

    def test_coordinated_release_uses_the_pinned_pair_and_component_commands(self) -> None:
        script = (ROOT / "bin" / "deploy-craftcontrol-release").read_text()
        self.assertIn("deploy-craftcontrol-backend", script)
        self.assertIn("deploy-craftcontrol-frontend", script)
        self.assertIn("CRAFTCONTROL_RELEASE_PAIR", script)
        self.assertIn("--rollback FRONTEND_VERSION BACKEND_VERSION", script)

    def test_cutover_proves_auth_csrf_sse_and_persistent_state(self) -> None:
        canary = (ROOT / "bin" / "check-split-auth").read_text()
        cutover = (ROOT / "bin" / "cutover-craftcontrol-split").read_text()
        snapshot = (ROOT / "bin" / "craftcontrol-state-snapshot").read_text()
        self.assertIn("/api/auth/claim", canary)
        self.assertIn("X-CSRF-Token", canary)
        self.assertIn('docker rm -f "$BACKEND"', canary)
        self.assertIn("content-type: text/event-stream", canary)
        self.assertIn("craftcontrol backup verify", cutover)
        self.assertIn("persistent-state invariants changed", cutover)
        self.assertIn("compatibility service restored", cutover)
        self.assertIn("--rollback", cutover)
        self.assertIn("PRAGMA quick_check", snapshot)

    def test_compose_mounts_explicit_application_boundaries(self) -> None:
        compose = (ROOT / "docker-compose.yml").read_text()
        self.assertIn("./apps/frontend/static:/app/apps/frontend/static:ro", compose)
        self.assertIn("./apps/frontend/templates:/app/apps/frontend/templates:ro", compose)
        self.assertIn("./apps/backend/minecraft_manager:/app/minecraft_manager:ro", compose)
        self.assertNotIn("./static:/app/static", compose)
        self.assertNotIn("./templates:/app/templates", compose)

    def test_split_images_isolate_privileged_backend_from_frontend(self) -> None:
        split = (ROOT / "docker-compose.split.yml").read_text()
        frontend = split.split("  craftcontrol-frontend:", 1)[1]
        backend = split.split("  craftcontrol-backend:", 1)[1].split("  craftcontrol-frontend:", 1)[0]
        self.assertIn("apps/backend/Dockerfile", backend)
        self.assertIn("/var/run/docker.sock", backend)
        self.assertIn("/minecraft-project", backend)
        self.assertIn("./data:/data", backend)
        self.assertIn("apps/frontend/Dockerfile", frontend)
        self.assertNotIn("/var/run/docker.sock", frontend)
        self.assertNotIn("/minecraft-project", frontend)
        self.assertNotIn("./data:/data", frontend)
        self.assertIn("read_only: true", frontend)

    def test_frontend_proxy_preserves_same_origin_and_sse_streaming(self) -> None:
        nginx = (ROOT / "apps" / "frontend" / "nginx.conf").read_text()
        self.assertIn("location /api/", nginx)
        self.assertIn("location = /api/events", nginx)
        self.assertIn("resolver 127.0.0.11", nginx)
        self.assertIn("set $craftcontrol_backend http://craftcontrol-backend:8082", nginx)
        self.assertIn("proxy_pass $craftcontrol_backend$request_uri", nginx)
        self.assertIn("proxy_set_header Host $http_host", nginx)
        self.assertIn("proxy_buffering off", nginx)
        self.assertIn("proxy_read_timeout 1h", nginx)

    def test_backend_image_does_not_bundle_frontend_application(self) -> None:
        backend = (ROOT / "apps" / "backend" / "Dockerfile").read_text()
        frontend = (ROOT / "apps" / "frontend" / "Dockerfile").read_text()
        self.assertNotIn("apps/frontend", backend)
        self.assertNotIn("minecraft_manager", frontend)
        self.assertIn("COPY apps/frontend/static", frontend)
        self.assertIn("chmod -R a=rX /usr/share/nginx/html", frontend)

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
        self.assertNotIn("| grep -q", script)


if __name__ == "__main__":
    unittest.main()
