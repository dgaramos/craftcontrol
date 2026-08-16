from flask import Flask

import pytest

from minecraft_manager.http.analytics import analytics_api


class FakeAnalyticsManager:
    def __init__(self) -> None:
        self.arguments = None

    def player_activity(self, kind, player, source, search, days, page, page_size):
        self.arguments = (kind, player, source, search, days, page, page_size)
        return {"events": [], "page": page, "pages": 1, "page_size": page_size, "total": 0, "summary": {}}

    def player_rankings(self, limit):
        self.arguments = ("rankings", limit)
        return {"period": "lifetime", "metrics": {}}

    def block_analytics(self, limit):
        self.arguments = ("blocks", limit)
        return {"period": "lifetime", "totals": {}}

    def combat_analytics(self, limit):
        self.arguments = ("combat", limit)
        return {"period": "lifetime", "totals": {}}

    def exploration_analytics(self, limit):
        self.arguments = ("exploration", limit)
        return {"period": "lifetime", "totals": {}}

    def period_analytics(self, days, limit):
        self.arguments = ("periods", days, limit)
        return {"period_days": days, "totals": {}}


@pytest.fixture
def analytics_client():
    manager = FakeAnalyticsManager()
    app = Flask(__name__)
    app.extensions["manager_service"] = manager
    app.register_blueprint(analytics_api)
    return app.test_client(), manager


def test_maps_activity_filters_to_application_service(analytics_client) -> None:
    client, manager = analytics_client
    response = client.get(
        "/api/analytics/activity?kind=deaths&player=VonCrush&source=structured&search=zombie&days=7&page=2&page_size=20"
    )
    assert response.status_code == 200
    assert manager.arguments == ("deaths", "VonCrush", "structured", "zombie", 7, 2, 20)


def test_rejects_non_numeric_pagination(analytics_client) -> None:
    client, _manager = analytics_client
    response = client.get("/api/analytics/activity?page=not-a-number")
    assert response.status_code == 400


def test_maps_bounded_ranking_limit(analytics_client) -> None:
    client, manager = analytics_client
    response = client.get("/api/analytics/rankings?limit=12")
    assert response.status_code == 200
    assert manager.arguments == ("rankings", 12)


def test_maps_bounded_block_analytics_limit(analytics_client) -> None:
    client, manager = analytics_client
    response = client.get("/api/analytics/blocks?limit=12")
    assert response.status_code == 200
    assert manager.arguments == ("blocks", 12)


def test_maps_bounded_combat_analytics_limit(analytics_client) -> None:
    client, manager = analytics_client
    response = client.get("/api/analytics/combat?limit=12")
    assert response.status_code == 200
    assert manager.arguments == ("combat", 12)


def test_maps_bounded_exploration_analytics_limit(analytics_client) -> None:
    client, manager = analytics_client
    response = client.get("/api/analytics/exploration?limit=12")
    assert response.status_code == 200
    assert manager.arguments == ("exploration", 12)


def test_maps_daily_analytics_period_and_limit(analytics_client) -> None:
    client, manager = analytics_client
    response = client.get("/api/analytics/periods?days=7&limit=12")
    assert response.status_code == 200
    assert manager.arguments == ("periods", 7, 12)
