from pathlib import Path
import os
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[3]
BASH = shutil.which("bash")

if BASH is None:
    raise RuntimeError("bash is required to test the review publisher")


def test_component_deploy_canaries_use_the_production_port_default() -> None:
    for script_name in ("deploy-craftcontrol-frontend", "deploy-craftcontrol-backend"):
        script = (ROOT / "bin" / script_name).read_text()
        assert 'frontend_port="${CRAFTCONTROL_SPLIT_PORT:-8082}"' in script
        assert 'frontend_port="${CRAFTCONTROL_SPLIT_PORT:-18082}"' not in script


def test_quality_gates_are_partitioned_and_automated() -> None:
    gates = ["frontend", "backend", "contracts", "dr-agents", "integration"]
    for gate in gates:
        script = ROOT / "bin" / f"check-{gate}"
        assert script.is_file()
        assert f"{gate} gate: ok" in script.read_text()
    assert (ROOT / "bin" / "check-contracts-frontend").is_file()
    umbrella = (ROOT / "bin" / "check").read_text()
    assert "contracts-frontend" in umbrella
    assert "frontend" in umbrella and "backend" in umbrella and "contracts" in umbrella and "dr-agents" in umbrella and "integration" in umbrella
    for workflow in (ROOT / ".github" / "workflows" / "quality.yml", ROOT / ".gitea" / "workflows" / "quality.yml"):
        assert workflow.is_file()
        text = workflow.read_text()
        for job in ("backend", "contracts-backend", "contracts-frontend", "frontend", "dr-agents", "integration"):
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
    workflow = (ROOT / ".gitea" / "workflows" / "quality.yml").read_text()
    runbook = (ROOT / "docs" / "automated-deployment.md").read_text()
    assert "branches: [main]" in workflow
    assert "needs: [integration]" in workflow
    assert "github.event_name == 'push'" in workflow
    assert "runs-on: [self-hosted, homelab, craftcontrol]" in workflow
    assert "craftcontrol-homelab-production" in workflow
    assert "/usr/local/bin/craftcontrol-homelab-deploy" in workflow
    assert "craftcontrol-bedrock-proxy-request-update" in workflow
    assert "deploy/bedrock-proxy services/bedrock-proxy" in workflow
    assert "Gitea-hosted runners never receive Docker or LAN access" in runbook


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
    assert "./apps/client/static:/app/apps/client/static:ro" in compose
    assert "./apps/client/templates:/app/apps/client/templates:ro" in compose
    assert "./apps/server/controlplane:/app/controlplane:ro" in compose
    assert "./static:/app/static" not in compose
    assert "./templates:/app/templates" not in compose


def test_split_images_isolate_privileged_backend_from_frontend() -> None:
    split = (ROOT / "docker-compose.split.yml").read_text()
    frontend_dockerfile = (ROOT / "apps" / "client" / "Dockerfile").read_text()
    backend_dockerfile = (ROOT / "apps" / "server" / "Dockerfile").read_text()
    frontend = split.split("  craftcontrol-frontend:", 1)[1]
    backend = split.split("  craftcontrol-backend:", 1)[1].split("  craftcontrol-frontend:", 1)[0]
    assert "apps/server/Dockerfile" in backend
    # The Docker socket is mounted read-only in the backend service.  BedrockClient
    # uses it for console operations (send, query_state, set_operator,
    # request_telemetry_snapshot) and EventRuntime uses it for log and Docker-event
    # streaming.  These are not covered by the host-agent contract.
    assert "/var/run/docker.sock" in backend
    assert "/minecraft-project" in backend
    assert "./data:/data" in backend
    assert "apps/client/Dockerfile" in frontend
    # The frontend never needs the Docker socket.
    assert "/var/run/docker.sock" not in frontend
    assert "/minecraft-project" not in frontend
    assert "./data:/data" not in frontend
    assert "read_only: true" in frontend
    assert 'org.opencontainers.image.title="CraftControl Client"' in frontend_dockerfile
    assert 'org.opencontainers.image.title="CraftControl Server"' in backend_dockerfile


def test_split_backend_reaches_host_agent_and_mounts_docker_socket() -> None:
    """Split-mode backend must configure the host agent AND mount the Docker socket.

    The host agent handles container lifecycle (ContainerOperations boundary).
    The Docker socket remains required for BedrockClient console operations and
    EventRuntime log/event streaming, which are not delegated to the host agent.
    """
    split = (ROOT / "docker-compose.split.yml").read_text()
    backend = split.split("  craftcontrol-backend:", 1)[1].split("  craftcontrol-frontend:", 1)[0]
    # Exact URL — must not be configurable via env substitution in this file.
    assert "BEDROCK_PROXY_URL: http://host-gateway:7890" in backend
    # Token file must be hard-coded to the volume mount destination with no
    # env substitution; overriding it via .env would silently break the adapter.
    assert "BEDROCK_PROXY_TOKEN_FILE: /run/bedrock-proxy-token" in backend
    assert "${HOST_AGENT_TOKEN_FILE" not in backend
    # extra_hosts mapping must use the special Docker host-gateway value.
    assert "host-gateway:host-gateway" in backend
    # Volume must bind-mount the token at the path the adapter reads.
    assert "/etc/craftcontrol/bedrock-proxy-token:/run/bedrock-proxy-token:ro" in backend
    # Docker socket must be mounted read-only for BedrockClient and EventRuntime.
    assert "/var/run/docker.sock:/var/run/docker.sock:ro" in backend


def test_host_agent_systemd_unit_is_present_and_well_formed() -> None:
    unit = (ROOT / "deploy" / "bedrock-proxy" / "systemd" / "craftcontrol-bedrock-proxy.service").read_text()
    assert "User=craftcontrol-agent" in unit
    assert "Group=craftcontrol-agent" in unit
    # Full ExecStart path — partial checks would miss wrong interpreter or path.
    assert "ExecStart=/usr/bin/python3 /opt/craftcontrol/bedrock-proxy/agent.py" in unit
    assert "Restart=on-failure" in unit
    assert "WantedBy=multi-user.target" in unit
    assert "docker.service" in unit
    assert "NoNewPrivileges=true" in unit
    assert "ProtectSystem=strict" in unit
    # ReadWritePaths must match HOST_AGENT_BEDROCK_DATA exactly.
    assert "ReadWritePaths=/opt/minecraft-bedrock" in unit
    # Secret file path must match the host-side token location.
    assert "BEDROCK_PROXY_SECRET_FILE=/etc/craftcontrol/bedrock-proxy-token" in unit


def test_host_agent_coverage_is_scoped_to_the_service_boundary() -> None:
    gate = (ROOT / "bin" / "check-bedrock-proxy").read_text()
    workflow = (ROOT / ".github" / "workflows" / "quality.yml").read_text()
    codecov = (ROOT / "codecov.yml").read_text()

    assert "services/bedrock-proxy/tests/" in gate
    assert "--cov=services/bedrock-proxy" in gate
    assert "--cov=deploy/bedrock-proxy" not in gate
    assert "files: coverage-bedrock-proxy.xml" in workflow
    assert "flags: bedrock-proxy" in workflow
    assert "component_id: host_agent" in codecov
    assert 'name: "bedrock-proxy"' in codecov
    assert "- services/bedrock-proxy/" in codecov
    assert "- deploy/bedrock-proxy/" not in codecov


def test_frontend_proxy_preserves_same_origin_and_sse_streaming() -> None:
    nginx = (ROOT / "apps" / "client" / "nginx.conf").read_text()
    assert "location /api/" in nginx
    assert "location = /api/events" in nginx
    assert "resolver 127.0.0.11" in nginx
    assert "set $craftcontrol_backend http://craftcontrol-backend:8082" in nginx
    assert "proxy_pass $craftcontrol_backend$request_uri" in nginx
    assert "proxy_set_header Host $http_host" in nginx
    assert "proxy_buffering off" in nginx
    assert "proxy_read_timeout 1h" in nginx


def test_backend_image_does_not_bundle_frontend_application() -> None:
    backend = (ROOT / "apps" / "server" / "Dockerfile").read_text()
    frontend = (ROOT / "apps" / "client" / "Dockerfile").read_text()
    assert "apps/client" not in backend
    assert "controlplane" not in frontend
    assert "COPY apps/client/static" in frontend
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


def test_deploy_mount_guards_use_a_portable_separator() -> None:
    mount_output = "\n".join(
        (
            "/srv/craftcontrol/data | /data",
            "/srv/minecraft | /minecraft-project",
            "/other | /other",
        )
    ) + "\n"
    awk_commands = [["awk"]]
    if shutil.which("busybox"):
        awk_commands.append(["busybox", "awk"])

    for script_name in ("deploy-craftcontrol", "deploy-craftcontrol-backend"):
        script = (ROOT / "bin" / script_name).read_text()
        assert "awk -F ' [|] '" in script
        assert "awk -F ' \\| '" not in script
        for awk_command in awk_commands:
            for destination, expected_source in (
                ("/data", "/srv/craftcontrol/data"),
                ("/minecraft-project", "/srv/minecraft"),
                ("/missing", ""),
            ):
                result = subprocess.run(
                    [
                        *awk_command,
                        "-F",
                        " [|] ",
                        "-v",
                        f"destination={destination}",
                        "$2 == destination {print $1}",
                    ],
                    input=mount_output,
                    text=True,
                    capture_output=True,
                    check=True,
                )
                expected_output = f"{expected_source}\n" if expected_source else ""
                assert result.stdout == expected_output


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
        assert f"PUBLISHER_APP_SLUG: ${{{{ steps.{reviewer}-token.outputs.app-slug }}}}" in workflow

    assert "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}/comments" in publisher
    assert "reply target mismatch" in publisher
    assert "reply target must be top-level" in publisher
    assert "resolveReviewThread" in publisher
    assert "reviewThreads(first: 100, after: $after)" in publisher
    assert "pageInfo { hasNextPage endCursor }" in publisher
    assert "graphql_args+=(-f after" in publisher
    assert "resolution target mismatch" in publisher
    assert "Publication report:" in publisher
    assert "PR head changed since review" in publisher
    assert "unexpected authenticated app" in publisher
    assert "PUBLISHER_APP_SLUG" in publisher


def test_app_publishers_allow_issues_without_project_metadata_and_verify_it_when_supplied() -> None:
    for reviewer in ("cody", "claudio"):
        issue_workflow = (
            ROOT / ".github" / "workflows" / f"publish-{reviewer}-issue.yml"
        ).read_text()
        metadata_workflow = (
            ROOT / ".github" / "workflows" / f"publish-{reviewer}-pr-metadata.yml"
        ).read_text()

        # Project fields are managed via the pr-metadata workflow, not the issue workflow.
        for field in ("project_owner", "project_number", "project_status"):
            assert f"{field}:" in metadata_workflow
        assert f"{reviewer}-dr[bot]" in issue_workflow
        assert "unexpected issue author" in issue_workflow
        assert "permission-organization-projects" not in issue_workflow
        assert "permission-organization-projects" not in metadata_workflow


def test_reviewer_publisher_rejects_unexpected_app_before_mutation(tmp_path: Path) -> None:
    fake_gh = tmp_path / "gh"
    fake_gh.write_text('#!/usr/bin/env bash\necho unexpected-gh-call >&2; exit 99\n')
    fake_gh.chmod(0o755)
    env = os.environ | {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "GH_TOKEN": "test",
        "GITHUB_REPOSITORY": "owner/repo",
        "PR_NUMBER": "1",
        "REVIEW_EVENT": "COMMENT",
        "REVIEWED_HEAD_SHA": "a" * 40,
        "EXPECTED_AUTHOR": "cody-dr[bot]",
        "PUBLISHER_APP_SLUG": "wrong-app",
        "REVIEW_BODY": "summary",
    }
    result = subprocess.run([BASH, ".github/scripts/publish-review.sh"], env=env, capture_output=True, text=True, cwd=ROOT)
    assert result.returncode != 0
    assert "unexpected authenticated app" in result.stderr


def test_reviewer_publisher_rejects_changed_head_before_mutation(tmp_path: Path) -> None:
    fake_gh = tmp_path / "gh"
    fake_gh.write_text('#!/usr/bin/env bash\nif [[ "$1" == "api" && "$3" == "--jq" ]]; then echo bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb; exit 0; fi\necho unexpected-gh-call >&2; exit 99\n')
    fake_gh.chmod(0o755)
    env = os.environ | {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "GH_TOKEN": "test",
        "GITHUB_REPOSITORY": "owner/repo",
        "PR_NUMBER": "1",
        "REVIEW_EVENT": "COMMENT",
        "REVIEWED_HEAD_SHA": "a" * 40,
        "EXPECTED_AUTHOR": "cody-dr[bot]",
        "PUBLISHER_APP_SLUG": "cody-dr",
        "REVIEW_BODY": "summary",
    }
    result = subprocess.run([BASH, ".github/scripts/publish-review.sh"], env=env, capture_output=True, text=True, cwd=ROOT)
    assert result.returncode != 0
    assert "PR head changed since review" in result.stderr


def test_reviewer_publisher_paginates_thread_validation_before_resolving(tmp_path: Path) -> None:
    fake_gh = tmp_path / "gh"
    call_log = tmp_path / "calls"
    fake_gh.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "printf '%s\\n' \"$*\" >> \"${FAKE_GH_CALL_LOG:?}\"\n"
        "if [[ \"$1 $2\" == 'api repos/owner/repo/pulls/1' ]]; then echo aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa; exit 0; fi\n"
        "if [[ \"$*\" == *'resolveReviewThread'* ]]; then echo true; exit 0; fi\n"
        "if [[ \"$1 $2 $3\" == 'api graphql -f' && \"$*\" == *'after=cursor-one'* ]]; then\n"
        "  echo '{\"data\":{\"repository\":{\"pullRequest\":{\"reviewThreads\":{\"nodes\":[{\"id\":\"thread-two\"}],\"pageInfo\":{\"hasNextPage\":false,\"endCursor\":null}}}}}}'\n"
        "  exit 0\n"
        "fi\n"
        "if [[ \"$1 $2 $3\" == 'api graphql -f' ]]; then\n"
        "  echo '{\"data\":{\"repository\":{\"pullRequest\":{\"reviewThreads\":{\"nodes\":[{\"id\":\"thread-one\"}],\"pageInfo\":{\"hasNextPage\":true,\"endCursor\":\"cursor-one\"}}}}}}'\n"
        "  exit 0\n"
        "fi\n"
        "echo unexpected-gh-call >&2; exit 99\n"
    )
    fake_gh.chmod(0o755)
    env = os.environ | {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "FAKE_GH_CALL_LOG": str(call_log),
        "GH_TOKEN": "test",
        "GITHUB_REPOSITORY": "owner/repo",
        "PR_NUMBER": "1",
        "REVIEW_EVENT": "COMMENT",
        "REVIEWED_HEAD_SHA": "a" * 40,
        "EXPECTED_AUTHOR": "cody-dr[bot]",
        "PUBLISHER_APP_SLUG": "cody-dr",
        "RESOLVE_THREAD_IDS_JSON": '["thread-two"]',
    }
    result = subprocess.run([BASH, ".github/scripts/publish-review.sh"], env=env, capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    assert "after=cursor-one" in call_log.read_text()
    assert "resolveReviewThread" in call_log.read_text()


def test_reviewer_publisher_rejects_thread_after_all_pages(tmp_path: Path) -> None:
    fake_gh = tmp_path / "gh"
    fake_gh.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$1 $2\" == 'api repos/owner/repo/pulls/1' ]]; then echo aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa; exit 0; fi\n"
        "if [[ \"$1 $2 $3\" == 'api graphql -f' ]]; then echo '{\"data\":{\"repository\":{\"pullRequest\":{\"reviewThreads\":{\"nodes\":[],\"pageInfo\":{\"hasNextPage\":false,\"endCursor\":null}}}}}}'; exit 0; fi\n"
        "echo unexpected-gh-call >&2; exit 99\n"
    )
    fake_gh.chmod(0o755)
    env = os.environ | {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "GH_TOKEN": "test",
        "GITHUB_REPOSITORY": "owner/repo",
        "PR_NUMBER": "1",
        "REVIEW_EVENT": "COMMENT",
        "REVIEWED_HEAD_SHA": "a" * 40,
        "EXPECTED_AUTHOR": "cody-dr[bot]",
        "PUBLISHER_APP_SLUG": "cody-dr",
        "RESOLVE_THREAD_IDS_JSON": '["missing-thread"]',
    }
    result = subprocess.run([BASH, ".github/scripts/publish-review.sh"], env=env, capture_output=True, text=True, cwd=ROOT)
    assert result.returncode != 0
    assert "resolution target mismatch" in result.stderr
