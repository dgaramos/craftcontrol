from pathlib import Path
import os
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")

if BASH is None:
    raise RuntimeError("bash is required to test the review publisher")


def test_component_deploy_canaries_use_the_production_port_default() -> None:
    for script_name in ("deploy-craftcontrol-frontend", "deploy-craftcontrol-backend"):
        script = (ROOT / "bin" / script_name).read_text()
        assert 'frontend_port="${CRAFTCONTROL_SPLIT_PORT:-8082}"' in script
        assert 'frontend_port="${CRAFTCONTROL_SPLIT_PORT:-18082}"' not in script


def test_quality_gates_are_partitioned_and_automated() -> None:
    gates = ["frontend", "backend", "contracts", "integration"]
    for gate in gates:
        script = ROOT / "bin" / f"check-{gate}"
        assert script.is_file()
        assert f"{gate} gate: ok" in script.read_text()
    assert (ROOT / "bin" / "check-contracts-frontend").is_file()
    umbrella = (ROOT / "bin" / "check").read_text()
    assert "contracts-frontend" in umbrella
    assert "frontend" in umbrella and "backend" in umbrella and "contracts" in umbrella and "integration" in umbrella
    for workflow in (ROOT / ".github" / "workflows" / "quality.yml", ROOT / ".gitea" / "workflows" / "quality.yml"):
        assert workflow.is_file()
        text = workflow.read_text()
        for job in ("backend", "contracts-backend", "contracts-frontend", "frontend", "integration"):
            assert job in text


def test_split_runtime_gate_uses_only_disposable_state() -> None:
    canary = (ROOT / "bin" / "check-split-runtime").read_text()
    assert "DATABASE_PATH=/tmp/manager.db" in canary
    assert "MINECRAFT_PROJECT=/tmp" in canary
    assert "/var/run/docker.sock" not in canary
    assert "Content-Type: text/event-stream" in canary
    assert "X-Accel-Buffering: no" in canary
    assert "wait_removed" in canary
    assert "versions.env" in canary
    assert "/version.json" in canary


def test_frontend_deploy_is_independent_guarded_and_reversible() -> None:
    script = (ROOT / "bin" / "deploy-craftcontrol-frontend").read_text()
    versions = (ROOT / "versions.env").read_text()
    assert "CRAFTCONTROL_FRONTEND_VERSION=0.3.6" in versions
    assert "CRAFTCONTROL_BACKEND_VERSION=0.1.0" in versions
    assert "split production topology is not active" in script
    assert "up -d --no-deps craftcontrol-frontend" in script
    assert "--rollback VERSION" in script
    assert "backend was recreated" in script
    assert "persistent data mount" in script
    assert "/version.json" in script
    assert "--prepare | --activate" in script
    assert "for attempt in 1 2 3" in script
    assert "frontend image build failed; retrying" in script
    assert script.index("compose build craftcontrol-frontend") < script.index(
        "compose up -d --no-deps craftcontrol-frontend"
    )


def test_backend_deploy_is_backed_up_independent_and_reversible() -> None:
    script = (ROOT / "bin" / "deploy-craftcontrol-backend").read_text()
    assert "split production topology is not active" in script
    assert "craftcontrol backup create" in script
    assert "craftcontrol backup verify" in script
    assert "PRAGMA quick_check" in script
    assert "up -d --no-deps craftcontrol-backend" in script
    assert "frontend was recreated" in script
    assert "--rollback VERSION" in script
    assert "Bedrock is not healthy" in script
    assert "--prepare | --activate" in script
    assert "for attempt in 1 2 3" in script
    assert "backend image build failed; retrying" in script
    assert script.index("compose build craftcontrol-backend") < script.index(
        "compose up -d --no-deps craftcontrol-backend"
    )


def test_coordinated_release_uses_the_pinned_pair_and_component_commands() -> None:
    script = (ROOT / "bin" / "deploy-craftcontrol-release").read_text()
    assert "deploy-craftcontrol-backend" in script
    assert "deploy-craftcontrol-frontend" in script
    assert "CRAFTCONTROL_RELEASE_PAIR" in script
    assert "--rollback FRONTEND_VERSION BACKEND_VERSION" in script
    assert 'deploy-craftcontrol-backend" --prepare' in script
    assert 'deploy-craftcontrol-frontend" --prepare' in script
    assert 'deploy-craftcontrol-backend" --activate' in script
    assert 'deploy-craftcontrol-frontend" --activate' in script
    assert script.index('deploy-craftcontrol-frontend" --prepare') < script.index(
        'deploy-craftcontrol-backend" --activate'
    )


def test_successful_main_quality_run_triggers_the_guarded_homelab_release() -> None:
    workflow = (ROOT / ".gitea" / "workflows" / "deploy.yml").read_text()
    runbook = (ROOT / "docs" / "automated-deployment.md").read_text()
    assert "workflow_run:" in workflow
    assert "branches: [main]" in workflow
    assert "runs-on: [self-hosted, homelab, craftcontrol]" in workflow
    assert "craftcontrol-homelab-production" in workflow
    assert "/usr/local/bin/craftcontrol-homelab-deploy" in workflow
    assert "GitHub-hosted runners never receive Docker or LAN access" in runbook


def test_cutover_proves_auth_csrf_sse_and_persistent_state() -> None:
    canary = (ROOT / "bin" / "check-split-auth").read_text()
    cutover = (ROOT / "bin" / "cutover-craftcontrol-split").read_text()
    snapshot = (ROOT / "bin" / "craftcontrol-state-snapshot").read_text()
    assert "/api/auth/claim" in canary
    assert "X-CSRF-Token" in canary
    assert 'docker rm -f "$BACKEND"' in canary
    assert "content-type: text/event-stream" in canary
    assert "craftcontrol backup verify" in cutover
    assert "persistent-state invariants changed" in cutover
    assert "compatibility service restored" in cutover
    assert "--rollback" in cutover
    assert "PRAGMA quick_check" in snapshot


def test_compose_mounts_explicit_application_boundaries() -> None:
    compose = (ROOT / "docker-compose.yml").read_text()
    assert "./apps/frontend/static:/app/apps/frontend/static:ro" in compose
    assert "./apps/frontend/templates:/app/apps/frontend/templates:ro" in compose
    assert "./apps/backend/minecraft_manager:/app/minecraft_manager:ro" in compose
    assert "./static:/app/static" not in compose
    assert "./templates:/app/templates" not in compose


def test_split_images_isolate_privileged_backend_from_frontend() -> None:
    split = (ROOT / "docker-compose.split.yml").read_text()
    frontend = split.split("  craftcontrol-frontend:", 1)[1]
    backend = split.split("  craftcontrol-backend:", 1)[1].split("  craftcontrol-frontend:", 1)[0]
    assert "apps/backend/Dockerfile" in backend
    assert "/var/run/docker.sock" in backend
    assert "/minecraft-project" in backend
    assert "./data:/data" in backend
    assert "apps/frontend/Dockerfile" in frontend
    assert "/var/run/docker.sock" not in frontend
    assert "/minecraft-project" not in frontend
    assert "./data:/data" not in frontend
    assert "read_only: true" in frontend


def test_frontend_proxy_preserves_same_origin_and_sse_streaming() -> None:
    nginx = (ROOT / "apps" / "frontend" / "nginx.conf").read_text()
    assert "location /api/" in nginx
    assert "location = /api/events" in nginx
    assert "resolver 127.0.0.11" in nginx
    assert "set $craftcontrol_backend http://craftcontrol-backend:8082" in nginx
    assert "proxy_pass $craftcontrol_backend$request_uri" in nginx
    assert "proxy_set_header Host $http_host" in nginx
    assert "proxy_buffering off" in nginx
    assert "proxy_read_timeout 1h" in nginx


def test_backend_image_does_not_bundle_frontend_application() -> None:
    backend = (ROOT / "apps" / "backend" / "Dockerfile").read_text()
    frontend = (ROOT / "apps" / "frontend" / "Dockerfile").read_text()
    assert "apps/frontend" not in backend
    assert "minecraft_manager" not in frontend
    assert "COPY apps/frontend/static" in frontend
    assert "chmod -R a=rX /usr/share/nginx/html" in frontend


def test_deploy_command_anchors_compose_and_protects_state() -> None:
    script = (ROOT / "bin" / "deploy-craftcontrol").read_text()
    assert 'docker compose --project-directory "$DEPLOY_ROOT"' in script
    assert '[[ "$(mount_source /data)" == "$DEPLOY_ROOT/data" ]]' in script
    assert '[[ "$(mount_source /minecraft-project)" == "$BEDROCK_ROOT" ]]' in script
    assert "craftcontrol backup create" in script
    assert "craftcontrol backup verify" in script
    assert 'sha256sum "$ENV_FILE"' in script
    assert 'sha256sum "$DATABASE_FILE"' in script
    assert "/api/auth/me" in script
    assert "| grep -q" not in script


def test_reviewer_publishers_support_thread_replies_without_creating_a_review() -> None:
    publisher = (ROOT / ".github" / "scripts" / "publish-review.sh").read_text()
    for name, reviewer in (
        ("publish-cody-review.yml", "cody"),
        ("publish-claudio-review.yml", "claudio"),
    ):
        workflow = (ROOT / ".github" / "workflows" / name).read_text()
        assert "inline_comments_json:" in workflow
        assert "reviewed_head_sha:" in workflow
        assert "replies_json:" in workflow
        assert "resolve_thread_ids_json:" in workflow
        assert "bash .github/scripts/publish-review.sh" in workflow
        assert "permission-pull-requests: write" in workflow
        assert f"{reviewer}-dr[bot]" in workflow

    assert "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}/comments" in publisher
    assert "reply target mismatch" in publisher
    assert "reply target must be top-level" in publisher
    assert "resolveReviewThread" in publisher
    assert "Publication report:" in publisher
    assert "PR head changed since review" in publisher
    assert "unexpected authenticated app" in publisher
    assert "installation/repositories" in publisher


def test_reviewer_publisher_rejects_unexpected_app_before_mutation(tmp_path: Path) -> None:
    fake_gh = tmp_path / "gh"
    fake_gh.write_text('#!/usr/bin/env bash\nif [[ "$1" == "api" && "$2" == "installation/repositories" ]]; then echo wrong-app; exit 0; fi\necho unexpected-gh-call >&2; exit 99\n')
    fake_gh.chmod(0o755)
    env = os.environ | {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "GH_TOKEN": "test",
        "GITHUB_REPOSITORY": "owner/repo",
        "PR_NUMBER": "1",
        "REVIEW_EVENT": "COMMENT",
        "REVIEWED_HEAD_SHA": "a" * 40,
        "EXPECTED_AUTHOR": "cody-dr[bot]",
        "REVIEW_BODY": "summary",
    }
    result = subprocess.run([BASH, ".github/scripts/publish-review.sh"], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert "unexpected authenticated app" in result.stderr


def test_reviewer_publisher_rejects_changed_head_before_mutation(tmp_path: Path) -> None:
    fake_gh = tmp_path / "gh"
    fake_gh.write_text('#!/usr/bin/env bash\nif [[ "$1" == "api" && "$2" == "installation/repositories" ]]; then echo cody-dr; exit 0; fi\nif [[ "$1" == "api" && "$3" == "--jq" ]]; then echo bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb; exit 0; fi\necho unexpected-gh-call >&2; exit 99\n')
    fake_gh.chmod(0o755)
    env = os.environ | {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "GH_TOKEN": "test",
        "GITHUB_REPOSITORY": "owner/repo",
        "PR_NUMBER": "1",
        "REVIEW_EVENT": "COMMENT",
        "REVIEWED_HEAD_SHA": "a" * 40,
        "EXPECTED_AUTHOR": "cody-dr[bot]",
        "REVIEW_BODY": "summary",
    }
    result = subprocess.run([BASH, ".github/scripts/publish-review.sh"], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert "PR head changed since review" in result.stderr


def test_reviewer_skills_dispatch_thread_replies_through_their_apps() -> None:
    cody = (ROOT / ".agents" / "skills" / "review-pr" / "SKILL.md").read_text()
    claudio = (ROOT / ".claude" / "agents" / "review-pr.md").read_text()
    for skill, reviewer in ((cody, "cody-dr"), (claudio, "claudio-dr")):
        assert "replies_json" in skill
        assert "resolve_thread_ids_json" in skill
        assert "inline_comments_json" in skill
        assert reviewer in skill
