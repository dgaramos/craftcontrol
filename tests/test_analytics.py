import unittest

from flask import Flask

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


class AnalyticsHttpTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = FakeAnalyticsManager()
        app = Flask(__name__)
        app.extensions["manager_service"] = self.manager
        app.register_blueprint(analytics_api)
        self.client = app.test_client()

    def test_maps_activity_filters_to_application_service(self) -> None:
        response = self.client.get(
            "/api/analytics/activity?kind=deaths&player=VonCrush&source=structured&search=zombie&days=7&page=2&page_size=20"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.manager.arguments, ("deaths", "VonCrush", "structured", "zombie", 7, 2, 20))

    def test_rejects_non_numeric_pagination(self) -> None:
        response = self.client.get("/api/analytics/activity?page=not-a-number")
        self.assertEqual(response.status_code, 400)

    def test_maps_bounded_ranking_limit(self) -> None:
        response = self.client.get("/api/analytics/rankings?limit=12")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.manager.arguments, ("rankings", 12))


if __name__ == "__main__":
    unittest.main()
