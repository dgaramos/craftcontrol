# Project Instructions

## Purpose

Maintain CraftControl, a mobile-first control panel for Minecraft Bedrock servers. The application must remain usable without Prometheus, Grafana, the custom exporter, or a behavior pack.

## Required context

Before planning, reviewing, or changing this project, read `README.md` and every Markdown file under the local `roadmap/` directory when that directory exists. The roadmap is private operational context: do not stage, commit, publish, quote, or copy it into deployment artifacts.

## Agent review profile

The tool-neutral profile at `.dr-agents/craftcontrol/PROFILE.md` is the
authoritative CraftControl-specific review context. Load it and every applicable
layer checklist for any PR review, whether the reviewer is Cody DR, Claudio DR,
or another agent. The profile augments generic review skills; it does not
trigger a review automatically. If it is unavailable, use the `claudio-reviewer` agent. Never copy roadmap content, credentials, databases, or
world data into the profile or review output.

## Documentation principle

Each piece of technical information lives in exactly one authoritative document. READMEs and `AGENTS.md` introduce a topic in one or two sentences and point to the authoritative source; they never duplicate its content. When adding or changing a rule, write it once in the most specific owning document and add a pointer from every entry point that would otherwise contain a copy.

## Architecture

- Treat `docs/architecture.md` as the authoritative reference for dependency direction, constructor injection policy, Protocol-based boundaries, the event and consistency model, and deliberate non-goals.
- Keep CraftControl a modular monolith: organize by domain, retain layered use cases inside modules, and use ports/adapters only at meaningful persistence and infrastructure boundaries.
- Preserve the internal event broker, persisted operational events, SSE browser updates, targeted refreshes, and periodic full reconciliation.
- Keep one Gunicorn worker unless the process-local broker and runtime supervisors are redesigned for multiple workers.
- Do not add browser polling when an event-driven invalidation and targeted reconciliation is sufficient.
- Keep the manager independent from the exporter and observability stack.
- Use SQLite for local durable state and schema changes that migrate existing databases without deleting user data.
- Use the coordinated backup service for live world/database backups. Hold Bedrock saves only during the copy window, resume in `finally`, use SQLite's backup API, and verify checksums before restore.
- Restores are offline, explicitly confirmed, and must create a pre-restore recovery copy. Never restore `.env` automatically.

### Backend module placement

New backend implementation modules must not be created in the `controlplane` package root. Owning modules: `core/`, `server/`, `players/`, `telemetry/`, `operations/`, `runtime/`, `http/`, `auth/`, `audit/`. Compatibility facades may preserve an existing import path only; new behavior belongs in the owning module. The architecture-test allowlist is the temporary, reviewed exception list. See [`apps/server/controlplane/README.md`](apps/server/controlplane/README.md) for the full package layout.

## Player data invariants

- A disconnect updates presence and closes a session; it never removes a player profile.
- Use XUID internally as the stable identity, preserve aliases, and never expose XUID through public APIs or UI.
- Keep permanent player history separate from the rolling operational event retention.
- Make connect/disconnect, reconciliation, and death ingestion idempotent.
- Mark abrupt-stop session closures as inferred.
- Treat log-parsed deaths as derived and preserve their raw evidence. Do not present them as authoritative.
- A behavior pack may be offered only as an optional structured-data enhancement.

## Product and security rules

- Keep the interface responsive, touch-friendly, Minecraft-inspired, and fully
  available in the supported UI locales: Portuguese, English, and Spanish.
  This list is authoritative for agent review and implementation guidance.
- Prefer understandable controls and contextual explanations over dense administration forms.
- Do not add generic shell or arbitrary Bedrock-console endpoints.
- Validate all commands and values with explicit allowlists.
- Assume trusted-LAN deployment only until authentication, CSRF, TLS, and restricted Docker access are implemented.
- Keep panel roles independent from Minecraft operator status. Enforce capabilities in the backend, preserve the last owner, hash all passwords and tokens, and never expose session identifiers or credentials in logs.
- Never overwrite `.env`, `data/manager.db`, or Minecraft world data during deployment.
- Keep the embedded telemetry pack under `packs/telemetry/` synchronized from its standalone repository with Git subtree. Pack installation must use the shared installer, persistent Bedrock data, backups, atomic association updates, and explicit restart decisions.

## Quality gate

Run the quality gate documented in `CONTRIBUTING.md` before handoff.

## Testing conventions

**Test file placement.** Backend tests live under `apps/server/tests/` mirroring
the `controlplane/` submodule structure:

| Production module | Test subdirectory |
|---|---|
| `core/` | `tests/core/` |
| `server/` | `tests/server/` |
| `players/` | `tests/players/` |
| `telemetry/` | `tests/telemetry/` |
| `operations/` | `tests/operations/` |
| `runtime/` | `tests/runtime/` |
| `http/` | `tests/http/` |
| `audit/` | `tests/audit/` |

Cross-cutting tests (architecture, composition, CLI, config, deployment,
documentation, brand, analytics, OpenMCPi, agent workflows) live at the
`tests/` root. Never create a new test file in the `tests/` root for a
single-module concern — put it in the matching subdirectory. Each subdirectory
has an empty `__init__.py` for pytest discovery.

**Shared helpers.** Add new test utilities to the right file — never inline them
in a single test module:

- `tests/fakes.py` — injectable fakes that replace production adapters
- `tests/factories.py` — builder functions for domain objects and protocol
  envelopes (`telemetry_envelope`, `player_snapshot`, `audit_record`, `event`,
  etc.). Every domain model dataclass must have a factory here. Tests must use
  the factory instead of constructing the model directly. Add a factory when
  a new model is introduced; only add it when at least one test actually needs
  it — do not add factories speculatively.
- `tests/conftest.py` — pytest fixtures shared across the whole suite

**Capability assertions.** When testing that a route is protected, assert the
*exact* capability name that the handler checks — not just that a 403 is
returned. Use or extend the `assert_capability_required` helper in
`tests/http/test_http_handlers.py` as the model.

The canonical package-level architecture reference is
[`apps/server/controlplane/README.md`](apps/server/controlplane/README.md).

**Prefer constructor injection over monkey-patching.**

Inject infrastructure dependencies (subprocess runners, file readers, socket
factories, time functions) as constructor parameters with production defaults.
Tests pass fakes or `MagicMock` instances directly; they never use
`unittest.mock.patch` on stdlib modules (`pathlib.Path`, `subprocess`,
`socket`, `time`, etc.).

```python
# preferred — dependency injected, no patch needed in tests
class BedrockFileSystem:
    def __init__(self, data_dir: str, read_text=None):
        self._read_text = read_text or (lambda p, **kw: p.read_text(**kw))

# avoid — leaks into stdlib, breaks isolation, hides the seam
with patch.object(Path, "write_text", _fail):
    ...
```

When a class or function has no injection point and requires `patch`, add the
injection point instead of the patch. Reserve `patch` for third-party library
boundaries that cannot be refactored (e.g. a C-extension with no seam).

This rule applies to both `apps/backend/` and `deploy/host-agent/`.

## Production deployment

- Deploy only with `bin/deploy-craftcontrol` from a clean, published `main`.
- Never run a bare `docker compose up` from a development checkout; relative bind mounts can select development state.
- Run `bin/deploy-craftcontrol --check` before the mutating deployment. The guarded command owns mount validation, coordinated backup and verification, tracked-file synchronization, state checksum checks, rebuild, and production canaries.

## Pull requests and Git history

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full contribution workflow: branch naming, PR title format, metadata requirements (Project, Milestone, Label, Assignee), Conventional Commits, CodeRabbit interaction, and what not to commit.
