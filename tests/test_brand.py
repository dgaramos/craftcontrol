import json
import unittest
import xml.etree.ElementTree as element_tree
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CraftControlBrandTest(unittest.TestCase):
    def test_template_uses_product_brand_and_dynamic_instance_name(self) -> None:
        template = (ROOT / "templates" / "index.html").read_text()
        self.assertIn("<title>CraftControl", template)
        self.assertIn("craftcontrol-mark.svg", template)
        self.assertIn('id="instance-name"', template)
        self.assertNotIn("MalavaziRamos · Gerenciador", template)

    def test_brand_assets_are_valid(self) -> None:
        root = element_tree.parse(ROOT / "static" / "craftcontrol-mark.svg").getroot()
        self.assertTrue(root.tag.endswith("svg"))
        manifest = json.loads((ROOT / "static" / "site.webmanifest").read_text())
        self.assertEqual(manifest["name"], "CraftControl")
        self.assertEqual(manifest["icons"][0]["src"], "/static/craftcontrol-mark.svg")

    def test_readme_presents_craftcontrol_without_hiding_compatibility_names(self) -> None:
        readme = (ROOT / "README.md").read_text()
        self.assertIn("<h1>CraftControl</h1>", readme)
        self.assertIn("compatibility", readme.casefold())
        self.assertIn("trusted private networks", readme)

    def test_compose_uses_final_product_name(self) -> None:
        compose = (ROOT / "docker-compose.yml").read_text()
        self.assertIn("  craftcontrol:\n", compose)
        self.assertIn("container_name: craftcontrol", compose)
        self.assertNotIn("minecraft-bedrock-manager", compose)

    def test_player_workspace_separates_roster_profile_and_permission_scopes(self) -> None:
        script = (ROOT / "static" / "app.js").read_text()
        self.assertIn('class="player-roster-row', script)
        self.assertIn('class="player-detail-screen"', script)
        self.assertIn("Minecraft permission", script)
        self.assertIn("CraftControl access", script)
        self.assertIn('class="player-server-settings', script)
        self.assertIn("Somente leitura", script)

    def test_player_profile_consolidates_authoritative_individual_analytics(self) -> None:
        script = (ROOT / "static" / "app.js").read_text()
        stylesheet = (ROOT / "static" / "players.css").read_text()
        self.assertIn('class="player-data-workspace"', script)
        self.assertIn("stats.killsByType", script)
        self.assertIn("stats.brokenByType", script)
        self.assertIn("stats.placedByType", script)
        self.assertIn("stats.dimensions", script)
        self.assertIn('id="compare-player-data"', script)
        self.assertIn('state.analytics.player = profile.name', script)
        self.assertIn('class="player-record-drawer"', script)
        self.assertIn("permanent aggregates", script)
        self.assertIn(".player-data-ranking", stylesheet)
        self.assertIn(".player-record-drawer", stylesheet)

    def test_browser_api_attaches_session_bound_csrf_header(self) -> None:
        api_script = (ROOT / "static" / "js" / "api.js").read_text()
        app_script = (ROOT / "static" / "app.js").read_text()
        auth_script = (ROOT / "static" / "js" / "auth.js").read_text()
        self.assertIn('headers["X-CSRF-Token"] = csrfToken', api_script)
        self.assertIn('typeof data.csrf_token === "string"', api_script)
        self.assertIn('./js/api.js?v=1', app_script)
        self.assertIn('./api.js?v=1', auth_script)

    def test_player_timeline_separates_action_from_localized_timestamp(self) -> None:
        script = (ROOT / "static" / "app.js").read_text()
        stylesheet = (ROOT / "static" / "players.css").read_text()
        self.assertIn('class="timeline-action"', script)
        self.assertIn('class="timeline-timestamp"', script)
        self.assertIn('month: "short"', script)
        self.assertIn(".timeline-timestamp", stylesheet)

    def test_deaths_localize_game_terms_and_separate_source_from_timestamp(self) -> None:
        script = (ROOT / "static" / "app.js").read_text()
        stylesheet = (ROOT / "static" / "players.css").read_text()
        template = (ROOT / "templates" / "index.html").read_text()
        self.assertIn('entityExplosion: ["creeper", "Explosão de criatura", "Entity explosion"]', script)
        self.assertIn('skeleton: ["skeleton", "Esqueleto", "Skeleton"]', script)
        self.assertIn('/static/craftcontrol-mobs.svg#mob-', script)
        self.assertIn('class="death-entry-header"', script)
        self.assertIn(".death-source", stylesheet)
        self.assertIn('id="release-tags"', template)

    def test_original_creature_icon_pack_has_expected_pixel_art_symbols(self) -> None:
        root = element_tree.parse(ROOT / "static" / "craftcontrol-mobs.svg").getroot()
        symbols = {node.attrib.get("id") for node in root.iter() if node.tag.endswith("symbol")}
        expected = {
            "mob-unknown", "mob-zombie", "mob-drowned", "mob-skeleton", "mob-creeper",
            "mob-spider", "mob-enderman", "mob-cow", "mob-pig", "mob-sheep",
            "mob-chicken", "mob-witch", "mob-ghast", "mob-blaze", "mob-player",
            "mob-arrow", "mob-trident",
        }
        self.assertTrue(expected.issubset(symbols))

    def test_recent_sessions_have_distinct_state_duration_and_period_layout(self) -> None:
        script = (ROOT / "static" / "app.js").read_text()
        stylesheet = (ROOT / "static" / "players.css").read_text()
        self.assertIn('class="session-state"', script)
        self.assertIn('class="session-duration"', script)
        self.assertIn('class="session-period"', script)
        self.assertIn("session.disconnected_at", script)
        self.assertIn(".session-item.is-inferred", stylesheet)

    def test_analytics_has_dedicated_bilingual_mobile_workspace(self) -> None:
        script = (ROOT / "static" / "app.js").read_text()
        stylesheet = (ROOT / "static" / "analytics.css").read_text()
        template = (ROOT / "templates" / "index.html").read_text()
        self.assertIn('tabs: ["home", "world", "players", "analytics"', script)
        self.assertIn("Atividade do servidor", script)
        self.assertIn("Server activity", script)
        self.assertIn('data-analytics-view="deaths"', script)
        self.assertIn("@media (max-width: 480px)", stylesheet)
        self.assertIn("analytics.css", template)
        self.assertIn('data-analytics-player=', script)
        self.assertIn('id="analytics-death-dialog"', script)
        self.assertIn("respawnsOnly", script)
        self.assertIn('class="ranking-podium', script)
        self.assertIn("rankingsTitle", script)
        self.assertIn(".podium-place.rank-1", stylesheet)
        self.assertIn('data-analytics-view="combat"', script)
        self.assertIn("combatEmptyHelp", script)
        self.assertIn(".combat-zero", stylesheet)
        self.assertIn('data-analytics-view="exploration"', script)
        self.assertIn("explorationEmptyHelp", script)
        self.assertIn(".exploration-zero", stylesheet)
        self.assertIn('data-analytics-view="trends"', script)
        self.assertIn("collectionStarted", script)
        self.assertIn(".heatmap-grid", stylesheet)
