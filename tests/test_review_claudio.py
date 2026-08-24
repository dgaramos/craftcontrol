"""Regression tests for Claudio DR review classification and approval behavior.

Fixture: PR #254 (feat(observability): add local telemetry diagnostics).

These tests enforce:
- The Claudio DR publish workflow uses COMMENT as the default event (never
  APPROVE or REQUEST_CHANGES by default).
- The project profile explicitly restricts review events and forbids embedding
  findings in the review body when an inline diff location is available.
- A capability-protected GET endpoint requires a 403 test for non-owner roles;
  the gap identified in the PR #254 review is addressed here via a self-
  contained local fixture that replicates the @require decorator pattern
  without depending on the PR #254 code being merged.

See issue #255: fix(agents): ground Claudio DR review findings.
"""
from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from flask import Blueprint, Flask, jsonify

from minecraft_manager.auth.http import require
from tests.conftest import make_auth_mock, wire_auth

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / ".agent-review" / "craftcontrol" / "PROFILE.md"
CLAUDIO_WORKFLOW = ROOT / ".github" / "workflows" / "publish-claudio-review.yml"


# ---------------------------------------------------------------------------
# Review workflow constraints (profile and publisher)
# ---------------------------------------------------------------------------

class TestPublishWorkflowEvent:
    """The Claudio DR publisher must default to COMMENT, not APPROVE or REQUEST_CHANGES."""

    def test_default_event_is_comment(self) -> None:
        text = CLAUDIO_WORKFLOW.read_text()
        # Match: event: {... default: COMMENT ...} on the same line
        match = re.search(r"event:\s*\{[^}]*default:\s*(\w+)", text)
        assert match is not None, "Could not locate event input in publish-claudio-review.yml"
        default_value = match.group(1)
        assert default_value == "COMMENT", (
            "publish-claudio-review.yml must default to COMMENT. "
            f"Current default is '{default_value}'. "
            "APPROVE and REQUEST_CHANGES are human decisions."
        )

    def test_comment_appears_before_approve_and_request_changes_in_options(self) -> None:
        text = CLAUDIO_WORKFLOW.read_text()
        # Find the options list: options: [COMMENT, REQUEST_CHANGES, APPROVE]
        match = re.search(r"options:\s*\[([^\]]+)\]", text)
        assert match is not None, "Could not locate event options list in publish-claudio-review.yml"
        options_str = match.group(1)
        options = [o.strip() for o in options_str.split(",")]
        assert options[0] == "COMMENT", (
            "COMMENT must be the first listed option so it is the most visible "
            f"choice. Current order: {options}."
        )


class TestProfileReviewEventRules:
    """The project profile must explicitly forbid APPROVE and REQUEST_CHANGES
    and require inline diff comments for findings within the diff."""

    def test_profile_forbids_approve_and_request_changes_events(self) -> None:
        text = PROFILE.read_text()
        assert "APPROVE" in text and "REQUEST_CHANGES" in text, (
            "PROFILE.md must explicitly name both APPROVE and REQUEST_CHANGES "
            "in its review event rules section."
        )
        # The text must prohibit these events, not just mention them.
        assert re.search(r"[Nn]ever use[^.]*(?:APPROVE|REQUEST_CHANGES)", text), (
            "PROFILE.md must explicitly forbid APPROVE and REQUEST_CHANGES "
            "for Claudio DR reviews."
        )

    def test_profile_requires_inline_diff_comments_for_findings(self) -> None:
        text = PROFILE.read_text()
        assert "inline" in text and "inline_comments_json" in text, (
            "PROFILE.md must require that findings within the diff are delivered "
            "as inline diff comments, not as body text."
        )

    def test_profile_requires_informational_observations_to_be_non_blocking(self) -> None:
        text = PROFILE.read_text()
        assert "non-actionable" in text or "Informational observations" in text, (
            "PROFILE.md must state that informational observations are non-actionable "
            "and must not appear in merge-risk justification."
        )

    def test_profile_requires_auth_claims_to_be_grounded_in_real_rules(self) -> None:
        text = PROFILE.read_text()
        assert "auth/" in text or "real auth" in text or "repository's real auth" in text, (
            "PROFILE.md must require auth/CSRF claims to be grounded in the "
            "repository's actual auth rules before inclusion in a finding."
        )


# ---------------------------------------------------------------------------
# Diagnostics RBAC regression (PR #254 gap: no 403 test for non-owner roles)
#
# The Claudio DR review of PR #254 noted: "test_diagnostics_returns_manager_data
# runs with auth_mode='disabled'. No test asserts that an operator or viewer
# session receives 403."
#
# These tests use a self-contained local fixture that replicates the @require
# decorator pattern from PR #254 so they can run on main before #254 merges.
# They will also cover the real route once #254 is merged and the fixture is
# superseded by test_http_handlers.py.
# ---------------------------------------------------------------------------

def _make_diagnostics_fixture_app(*, auth_mode: str = "local") -> Flask:
    """Minimal Flask app with a capability-protected GET /api/diagnostics route.

    This fixture replicates the route shape introduced in PR #254 without
    importing from the branch-only telemetry blueprint, so the test is
    self-contained and runnable on main.
    """
    fixture_api = Blueprint("fixture_diagnostics", __name__)

    @fixture_api.get("/api/diagnostics")
    @require("telemetry.manage")
    def diagnostics():  # type: ignore[return-value]
        return jsonify({"telemetry": {}, "broker": {}, "runtime_refreshing": False})

    app = Flask(__name__)
    auth = make_auth_mock()
    wire_auth(app, auth, mode=auth_mode)
    app.register_blueprint(fixture_api)
    return app


class TestDiagnosticsRBAC:
    """GET /api/diagnostics must return 403 for non-owner roles.

    The endpoint is decorated with @require('telemetry.manage'). Only the
    'owner' role holds '*' (all capabilities). Operator and viewer roles must
    be denied.
    """

    def test_operator_receives_403_on_diagnostics(self) -> None:
        app = _make_diagnostics_fixture_app(auth_mode="local")
        auth: MagicMock = app.extensions["auth_service"]
        auth.authenticate.return_value = {
            "id": "2", "name": "Alex", "role": "operator", "capabilities": [
                "server.read", "server.configure", "world.manage",
                "players.manage_permissions", "server.lifecycle.start",
                "server.lifecycle.restart",
            ],
        }
        auth.require_capability.side_effect = PermissionError("insufficient permission")
        with app.test_client() as client:
            resp = client.get("/api/diagnostics")
        assert resp.status_code == 403, (
            "operator role must not access /api/diagnostics "
            f"(got {resp.status_code})"
        )
        auth.require_capability.assert_called_once()

    def test_viewer_receives_403_on_diagnostics(self) -> None:
        app = _make_diagnostics_fixture_app(auth_mode="local")
        auth: MagicMock = app.extensions["auth_service"]
        auth.authenticate.return_value = {
            "id": "3", "name": "Notch", "role": "viewer", "capabilities": ["server.read"],
        }
        auth.require_capability.side_effect = PermissionError("insufficient permission")
        with app.test_client() as client:
            resp = client.get("/api/diagnostics")
        assert resp.status_code == 403, (
            "viewer role must not access /api/diagnostics "
            f"(got {resp.status_code})"
        )
        auth.require_capability.assert_called_once()

    def test_owner_receives_200_on_diagnostics(self) -> None:
        app = _make_diagnostics_fixture_app(auth_mode="local")
        auth: MagicMock = app.extensions["auth_service"]
        auth.authenticate.return_value = {
            "id": "1", "name": "Steve", "role": "owner", "capabilities": ["*"],
        }
        auth.require_capability.return_value = None
        with app.test_client() as client:
            resp = client.get("/api/diagnostics")
        assert resp.status_code == 200, (
            f"owner must access /api/diagnostics (got {resp.status_code})"
        )
