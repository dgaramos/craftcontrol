"""Tests for PlayerService use cases — validation, error paths, and delegation."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from minecraft_manager.players.service import PlayerService


@pytest.fixture
def repo() -> MagicMock:
    mock = MagicMock()
    mock.snapshot.return_value = {"players": {}, "known_players": {}, "bootstrap": {}}
    return mock


@pytest.fixture
def files() -> MagicMock:
    return MagicMock()


@pytest.fixture
def console() -> MagicMock:
    return MagicMock()


@pytest.fixture
def events() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(repo, files, console, events) -> PlayerService:
    return PlayerService(repo, files, console, events)


# ---------------------------------------------------------------------------
# refresh_permissions — error path
# ---------------------------------------------------------------------------

def test_refresh_permissions_publishes_failure_when_read_raises(service: PlayerService, files: MagicMock, events: MagicMock) -> None:
    files.read_permissions.side_effect = OSError("file missing")
    service.refresh_permissions()
    events.publish.assert_called_once_with(
        "permissions.reconciliation.failed",
        "permissions.json",
        {"error": "file missing"},
    )


def test_refresh_permissions_returns_early_on_error(service: PlayerService, files: MagicMock, repo: MagicMock) -> None:
    files.read_permissions.side_effect = OSError("file missing")
    service.refresh_permissions()
    repo.replace.assert_not_called()


def test_refresh_permissions_maps_xuid_to_name(service: PlayerService, files: MagicMock, repo: MagicMock, events: MagicMock) -> None:
    repo.snapshot.return_value = {"players": {}, "known_players": {"VonCrush": "999"}, "bootstrap": {}}
    files.read_permissions.return_value = [{"xuid": "999", "permission": "operator"}]
    service.refresh_permissions()
    repo.set_player_permission.assert_called_once_with("VonCrush", "operator", "permissions.json")


def test_refresh_permissions_skips_unknown_xuids(service: PlayerService, files: MagicMock, repo: MagicMock) -> None:
    repo.snapshot.return_value = {"players": {}, "known_players": {}, "bootstrap": {}}
    files.read_permissions.return_value = [{"xuid": "999", "permission": "operator"}]
    service.refresh_permissions()
    repo.set_player_permission.assert_not_called()


def test_refresh_permissions_skips_event_when_publish_false(service: PlayerService, files: MagicMock, events: MagicMock) -> None:
    files.read_permissions.return_value = []
    service.refresh_permissions(publish=False)
    events.publish.assert_not_called()


# ---------------------------------------------------------------------------
# bootstrap
# ---------------------------------------------------------------------------

def test_bootstrap_skips_when_no_operator_configured(service: PlayerService, console: MagicMock) -> None:
    service.bootstrap(["VonCrush"])
    console.set_operator.assert_not_called()


def test_bootstrap_skips_when_already_done(repo: MagicMock, files, console, events) -> None:
    repo.snapshot.return_value = {"players": {}, "known_players": {}, "bootstrap": {"operator": "done"}}
    svc = PlayerService(repo, files, console, events, bootstrap_operator="VonCrush")
    svc.bootstrap(["VonCrush"])
    console.set_operator.assert_not_called()


def test_bootstrap_skips_when_player_not_online(repo: MagicMock, files, console, events) -> None:
    svc = PlayerService(repo, files, console, events, bootstrap_operator="VonCrush")
    svc.bootstrap(["Nicole"])
    console.set_operator.assert_not_called()


def test_bootstrap_promotes_operator_when_player_online(repo: MagicMock, files, console, events) -> None:
    svc = PlayerService(repo, files, console, events, bootstrap_operator="VonCrush")
    svc.bootstrap(["VonCrush"])
    console.set_operator.assert_called_once_with("VonCrush", True)
    repo.store.assert_called_with("bootstrap", {"operator": "done"}, "manager")


# ---------------------------------------------------------------------------
# activity validation
# ---------------------------------------------------------------------------

def test_activity_invalid_kind_raises(service: PlayerService) -> None:
    with pytest.raises(ValueError, match="invalid activity kind"):
        service.activity("bogus", "", "all", "", 0, 1, 10)


def test_activity_invalid_source_raises(service: PlayerService) -> None:
    with pytest.raises(ValueError, match="invalid activity source"):
        service.activity("all", "", "bogus", "", 0, 1, 10)


def test_activity_invalid_days_raises(service: PlayerService) -> None:
    with pytest.raises(ValueError, match="invalid activity period"):
        service.activity("all", "", "all", "", 14, 1, 10)


def test_activity_page_zero_raises(service: PlayerService) -> None:
    with pytest.raises(ValueError, match="invalid pagination"):
        service.activity("all", "", "all", "", 0, 0, 10)


def test_activity_page_size_too_large_raises(service: PlayerService) -> None:
    with pytest.raises(ValueError, match="invalid pagination"):
        service.activity("all", "", "all", "", 0, 1, 51)


def test_activity_player_too_long_raises(service: PlayerService) -> None:
    with pytest.raises(ValueError, match="invalid activity filter"):
        service.activity("all", "x" * 65, "all", "", 0, 1, 10)


def test_activity_delegates_valid_params(service: PlayerService, repo: MagicMock) -> None:
    repo.player_activity.return_value = {"events": [{"type": "join"}]}
    result = service.activity("deaths", "VonCrush", "all", "", 7, 1, 10)
    repo.player_activity.assert_called_once_with("deaths", "VonCrush", "all", "", 7, 1, 10)
    assert result == {"events": [{"type": "join"}]}


# ---------------------------------------------------------------------------
# rankings validation
# ---------------------------------------------------------------------------

def test_rankings_limit_zero_raises(service: PlayerService) -> None:
    with pytest.raises(ValueError, match="invalid ranking limit"):
        service.rankings(0)


def test_rankings_limit_too_high_raises(service: PlayerService) -> None:
    with pytest.raises(ValueError, match="invalid ranking limit"):
        service.rankings(26)


def test_rankings_delegates_valid_limit(service: PlayerService, repo: MagicMock) -> None:
    repo.player_rankings.return_value = {"top": ["VonCrush"]}
    result = service.rankings(5)
    repo.player_rankings.assert_called_once_with(5)
    assert result == {"top": ["VonCrush"]}


# ---------------------------------------------------------------------------
# blocks validation
# ---------------------------------------------------------------------------

def test_blocks_limit_zero_raises(service: PlayerService) -> None:
    with pytest.raises(ValueError, match="invalid block analytics limit"):
        service.blocks(0)


def test_blocks_limit_too_high_raises(service: PlayerService) -> None:
    with pytest.raises(ValueError, match="invalid block analytics limit"):
        service.blocks(26)


def test_blocks_delegates_valid_limit(service: PlayerService, repo: MagicMock) -> None:
    repo.block_analytics.return_value = {"mined": 42}
    result = service.blocks(5)
    repo.block_analytics.assert_called_once_with(5)
    assert result == {"mined": 42}


# ---------------------------------------------------------------------------
# combat validation
# ---------------------------------------------------------------------------

def test_combat_limit_zero_raises(service: PlayerService) -> None:
    with pytest.raises(ValueError, match="invalid combat analytics limit"):
        service.combat(0)


def test_combat_limit_too_high_raises(service: PlayerService) -> None:
    with pytest.raises(ValueError, match="invalid combat analytics limit"):
        service.combat(26)


def test_combat_delegates_valid_limit(service: PlayerService, repo: MagicMock) -> None:
    repo.combat_analytics.return_value = {"kills": 7}
    result = service.combat(5)
    repo.combat_analytics.assert_called_once_with(5)
    assert result == {"kills": 7}


# ---------------------------------------------------------------------------
# exploration validation
# ---------------------------------------------------------------------------

def test_exploration_limit_zero_raises(service: PlayerService) -> None:
    with pytest.raises(ValueError, match="invalid exploration analytics limit"):
        service.exploration(0)


def test_exploration_limit_too_high_raises(service: PlayerService) -> None:
    with pytest.raises(ValueError, match="invalid exploration analytics limit"):
        service.exploration(26)


def test_exploration_delegates_valid_limit(service: PlayerService, repo: MagicMock) -> None:
    repo.exploration_analytics.return_value = {"biomes": 3}
    result = service.exploration(5)
    repo.exploration_analytics.assert_called_once_with(5)
    assert result == {"biomes": 3}


# ---------------------------------------------------------------------------
# periods validation
# ---------------------------------------------------------------------------

def test_periods_invalid_days_raises(service: PlayerService) -> None:
    with pytest.raises(ValueError, match="invalid analytics period"):
        service.periods(days=14)


def test_periods_limit_zero_raises(service: PlayerService) -> None:
    with pytest.raises(ValueError, match="invalid period analytics limit"):
        service.periods(days=7, limit=0)


def test_periods_limit_too_high_raises(service: PlayerService) -> None:
    with pytest.raises(ValueError, match="invalid period analytics limit"):
        service.periods(days=7, limit=26)


def test_periods_delegates_valid_params(service: PlayerService, repo: MagicMock) -> None:
    repo.period_analytics.return_value = {"sessions": 12}
    result = service.periods(days=7, limit=5)
    repo.period_analytics.assert_called_once_with(7, 5)
    assert result == {"sessions": 12}
