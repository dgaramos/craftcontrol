# Project instructions

Read `README.md` and every Markdown file under the ignored `roadmap/` directory
before changing the project.

- This agent runs on the Docker host outside all containers. It must never be
  deployed inside a container or depend on the CraftControl Server package.
- The endpoint surface is fixed: `/health`, `/status`, `/execute`, `/poll/<id>`.
  Do not add endpoints without a reviewed architecture decision.
- All field validation uses strict allowlists defined in `operations.py`. Never
  relax an allowlist or introduce shell execution to handle a new field type.
- Authentication is bearer-token only. The token is read from a file at startup
  and never logged or included in error responses.
- Docker operations go through the Docker SDK (`adapters/docker.py`). Filesystem
  writes are atomic (`adapters/filesystem.py`). Neither adapter shells out.
- Keep `HOST_AGENT_WORKERS` at 1. The queue is bounded; reject with 503 rather
  than growing unbounded.
- Tests use `FakeDocker` and `FakeFilesystem` — never require a live Docker
  daemon in the test suite.
- Do not add dependencies beyond `requirements.txt` without explicit approval.
- Never commit the token file, database, or roadmap.

Run `pytest tests/ -x -q` and `git diff --check` before handoff.
