# Project instructions

Read `README.md` and every Markdown file under the ignored `roadmap/` directory
before changing the project.

- This agent runs on the Docker host outside all containers. It must never be
  deployed inside a container or depend on the CraftControl Server package.
- The endpoint surface is fixed: `/health`, `/status`, `/execute`, `/poll/<id>`.
  Do not add endpoints without a reviewed architecture decision.
- All field validation uses strict allowlists defined in `host_agent/runtime/operations.py`. Never
  relax an allowlist or introduce shell execution to handle a new field type.
- Authentication is bearer-token only. The token is read from a file at startup
  and never logged or included in error responses.
- Docker operations go through the Docker SDK (`host_agent/adapters/docker.py`). Filesystem
  writes are atomic (`host_agent/adapters/filesystem.py`). Neither adapter shells out.
- Keep `HOST_AGENT_WORKERS` at 1. The queue is bounded; reject with 503 rather
  than growing unbounded.
- Do not add dependencies beyond `requirements.txt` without explicit approval.
- Never commit the token file, database, or roadmap.

## Package layout

The `host_agent/` named package organises modules by responsibility:

| Subpackage | Contents |
|---|---|
| `host_agent/auth/` | `auth.py` — shared-secret token loading and verification |
| `host_agent/http/` | `handler.py`, `router.py` — request parsing, routing, authentication |
| `host_agent/runtime/` | `operations.py`, `queue_worker.py` — executor and bounded thread pool |
| `host_agent/store/` | `store.py` — SQLite-backed operation persistence |
| `host_agent/preflight/` | `preflight.py` — startup self-check |
| `host_agent/adapters/` | `docker.py`, `filesystem.py`, `raknet.py` — infrastructure adapters |
| `host_agent/ports.py` | Protocol definitions for replaceable boundaries (at package root) |

`agent.py` remains the sole file at the service root and imports from `host_agent.*`.
New modules must not be added to the service root; place them in the owning subpackage above.

## Testing conventions

**sys.path bootstrap belongs in `tests/conftest.py` only.** Every test file that
currently repeats the `sys.path.insert` block should import from `conftest`
instead. New test files must never add their own `sys.path` manipulation.

**Shared helpers live in `tests/helpers.py`.** `FakeProbe`, `make_executor`, and
any other reusable builder or fake belong there — never inline them in a single
test file.

**Prefer constructor injection over `patch`.** `DockerComposeRunner`,
`BedrockFileSystem`, and `HealthProbe` already accept injected collaborators.
Pass fakes through those seams. Do not use `unittest.mock.patch` on stdlib
(`pathlib.Path`, `subprocess`, `socket`) — add an injection point to the
production class instead.

**Use a builder for subprocess results.** The repeated pattern
`MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))` belongs
in `helpers.py` as `fake_run(returncode=0, stdout="", stderr="")`. New tests must
use the builder; existing tests should be migrated when a file is touched.

Run `pytest tests/ -x -q` and `git diff --check` before handoff.
