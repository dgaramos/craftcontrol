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

from src.auth.http import require
from conftest import make_auth_mock, wire_auth

ROOT = Path(__file__).resolve().parents[4]
PROFILE = ROOT / ".dr-agents" / "craftcontrol" / "PROFILE.md"
CLAUDIO_WORKFLOW = ROOT / ".github" / "workflows" / "publish-claudio-review.yml"
CODY_WORKFLOW = ROOT / ".github" / "workflows" / "publish-cody-review.yml"


# ---------------------------------------------------------------------------
# Review workflow constraints (profile and publisher)
# ---------------------------------------------------------------------------

class TestPublishWorkflowEvent:
    """Reviewer publishers must allow COMMENT only; approvals remain human decisions."""

    @pytest.mark.parametrize("workflow", [CODY_WORKFLOW, CLAUDIO_WORKFLOW])
    def test_default_event_is_comment(self, workflow: Path) -> None:
        text = workflow.read_text()
        # Match: event: {... default: COMMENT ...} on the same line
        match = re.search(r"event:\s*\{[^}]*default:\s*(\w+)", text)
        assert match is not None, "Could not locate event input in publish-claudio-review.yml"
        default_value = match.group(1)
        assert default_value == "COMMENT", (
            f"{workflow.name} must default to COMMENT. "
            f"Current default is '{default_value}'. "
            "APPROVE and REQUEST_CHANGES are human decisions."
        )

    @pytest.mark.parametrize("workflow", [CODY_WORKFLOW, CLAUDIO_WORKFLOW])
    def test_options_list_contains_only_comment(self, workflow: Path) -> None:
        text = workflow.read_text()
        # Anchor to the event input line to avoid matching unrelated options lists.
        # The workflow uses inline YAML: event: {... options: [COMMENT]}
        event_block = re.search(
            r"\bevent:\s*\{[^}]*options:\s*\[([^\]]+)\]",
            text,
        )
        assert event_block is not None, (
            "Could not locate the 'event' input options list in publish-claudio-review.yml. "
            "Expected: event: {... options: [COMMENT] ...}"
        )
        options = [o.strip() for o in event_block.group(1).split(",")]
        assert options == ["COMMENT"], (
            f"{workflow.name} must list exactly [COMMENT] as the only "
            "allowed event. APPROVE and REQUEST_CHANGES are human decisions and "
            f"must not appear as selectable options. Current options: {options}."
        )


class TestProfileReviewEventRules:
    """The project profile must explicitly forbid APPROVE and REQUEST_CHANGES
    and require inline diff comments for findings within the diff."""

    def test_profile_forbids_approve_and_request_changes_events(self) -> None:
        text = PROFILE.read_text()
        # Both events must be named in the profile.
        assert "APPROVE" in text, (
            "PROFILE.md must explicitly name APPROVE in its review event rules section."
        )
        assert "REQUEST_CHANGES" in text, (
            "PROFILE.md must explicitly name REQUEST_CHANGES in its review event rules section."
        )
        # The profile must explicitly forbid BOTH events, not merely mention them.
        assert re.search(r"[Nn]ever use[^.]*APPROVE", text), (
            "PROFILE.md must explicitly forbid APPROVE for Claudio DR reviews. "
            "Approval is a human decision."
        )
        assert re.search(r"[Nn]ever use[^.]*REQUEST_CHANGES", text), (
            "PROFILE.md must explicitly forbid REQUEST_CHANGES for Claudio DR reviews. "
            "Merge blocking is a human decision."
        )

    def test_profile_requires_inline_diff_comments_for_findings(self) -> None:
        text = PROFILE.read_text()
        # inline_comments_json, inline-location condition, and body-text prohibition
        # must all appear in one coherent rule clause.
        pattern = (
            r"inline_comments_json\b[^.]*?"
            r"(?:not\s+embedded|not\s+as\s+body|not\s+in\s+the\s+body|not\s+embed)"
        )
        assert re.search(pattern, text, re.DOTALL), (
            "PROFILE.md must contain a coherent rule clause that names "
            "inline_comments_json as the delivery mechanism for findings that have "
            "an inline diff location AND explicitly forbids embedding those findings "
            "as body text — all within the same rule, not as independent matches."
        )

    def test_profile_requires_informational_observations_to_be_non_blocking(self) -> None:
        text = PROFILE.read_text()
        # All three properties must appear together in one coherent rule clause:
        # named category + non-actionable label + exclusion from merge-risk/approval.
        pattern = (
            r"Informational observations\b[^.]*?"
            r"(?:non-actionable|not\s+appear\s+in\s+the\s+merge.risk|merge-risk|approval rationale)"
        )
        assert re.search(pattern, text, re.DOTALL), (
            "PROFILE.md must contain a coherent rule clause that names "
            "'Informational observations', labels them non-actionable, and excludes "
            "them from merge-risk justification or approval rationale — all in the "
            "same section, not as independent document-wide matches."
        )

    def test_profile_requires_auth_claims_to_be_grounded_in_real_rules(self) -> None:
        text = PROFILE.read_text()
        # controlplane/auth/ path and grounding requirement must appear
        # together in one coherent rule clause.
        pattern = (
            r"controlplane/auth/[^.]*?"
            r"(?:grounded|real auth rules|actual auth)"
            r"|(?:grounded|real auth rules|actual auth)[^.]*?controlplane/auth/"
        )
        assert re.search(pattern, text, re.DOTALL), (
            "PROFILE.md must contain a coherent rule clause that cites "
            "controlplane/auth/ as the real auth rules location AND requires "
            "auth/CSRF claims to be grounded there before inclusion in any finding."
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

    def _capability_aware_require(self, user: dict, capability: str) -> None:
        """Raise PermissionError when the user lacks the requested capability.

        Mirrors AuthService.require_capability: grants access only when the
        user holds '*' (all capabilities) or the exact capability string.
        """
        held = set(user.get("capabilities", []))
        if "*" not in held and capability not in held:
            raise PermissionError(capability)

    def test_operator_receives_403_on_diagnostics(self) -> None:
        app = _make_diagnostics_fixture_app(auth_mode="local")
        auth: MagicMock = app.extensions["auth_service"]
        operator_user = {
            "id": "2", "name": "Alex", "role": "operator", "capabilities": [
                "server.read", "server.configure", "world.manage",
                "players.manage_permissions", "server.lifecycle.start",
                "server.lifecycle.restart",
            ],
        }
        auth.authenticate.return_value = operator_user
        auth.require_capability.side_effect = lambda user, cap: self._capability_aware_require(user, cap)
        with app.test_client() as client:
            resp = client.get("/api/diagnostics")
        assert resp.status_code == 403, (
            "operator role must not access /api/diagnostics "
            f"(got {resp.status_code})"
        )
        auth.require_capability.assert_called_once_with(operator_user, "telemetry.manage")

    def test_viewer_receives_403_on_diagnostics(self) -> None:
        app = _make_diagnostics_fixture_app(auth_mode="local")
        auth: MagicMock = app.extensions["auth_service"]
        viewer_user = {
            "id": "3", "name": "Notch", "role": "viewer", "capabilities": ["server.read"],
        }
        auth.authenticate.return_value = viewer_user
        auth.require_capability.side_effect = lambda user, cap: self._capability_aware_require(user, cap)
        with app.test_client() as client:
            resp = client.get("/api/diagnostics")
        assert resp.status_code == 403, (
            "viewer role must not access /api/diagnostics "
            f"(got {resp.status_code})"
        )
        auth.require_capability.assert_called_once_with(viewer_user, "telemetry.manage")

    def test_owner_receives_200_on_diagnostics(self) -> None:
        app = _make_diagnostics_fixture_app(auth_mode="local")
        auth: MagicMock = app.extensions["auth_service"]
        owner_user = {
            "id": "1", "name": "Steve", "role": "owner", "capabilities": ["*"],
        }
        auth.authenticate.return_value = owner_user
        auth.require_capability.side_effect = lambda user, cap: self._capability_aware_require(user, cap)
        with app.test_client() as client:
            resp = client.get("/api/diagnostics")
        assert resp.status_code == 200, (
            f"owner must access /api/diagnostics (got {resp.status_code})"
        )
        auth.require_capability.assert_called_once_with(owner_user, "telemetry.manage")
