# Claude project guide

Follow `AGENTS.md`. Read `README.md` and the private ignored `roadmap/` before
work. This is a minimal host-level HTTP agent — its operation surface is fixed
and intentionally narrow. Do not expand the endpoint surface or introduce shell
execution without explicit approval.

When writing or modifying tests:
- `sys.path` manipulation belongs only in `tests/conftest.py`.
- Shared fakes and builders belong in `tests/helpers.py`.
- Never patch stdlib (`pathlib.Path`, `subprocess`, `socket`) — add an injection
  point to the production class instead.
- Use `fake_run()` from `helpers.py` for subprocess result stubs.
