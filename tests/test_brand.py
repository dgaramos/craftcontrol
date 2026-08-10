import json
import re
import unittest
import xml.etree.ElementTree as element_tree
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "apps" / "frontend"


def frontend_script() -> str:
    static = FRONTEND / "static"
    return "\n".join((
        (static / "app.js").read_text(),
        (static / "js" / "composition.js").read_text(),
        (static / "js" / "features" / "settings" / "index.js").read_text(),
    ))


class CraftControlBrandTest(unittest.TestCase):
    def test_frontend_entrypoint_is_only_bootstrap_and_composition(self) -> None:
        entrypoint = (FRONTEND / "static" / "app.js").read_text()
        composition = (FRONTEND / "static" / "js" / "composition.js").read_text()
        settings = (FRONTEND / "static" / "js" / "features" / "settings" / "index.js").read_text()
        self.assertLessEqual(len(entrypoint.splitlines()), 5)
        self.assertIn("startApplication", entrypoint)
        self.assertIn("createNavigation", composition)
        self.assertIn("connectInvalidation", composition)
        self.assertIn("createSettingsFeature", settings)

    def test_template_uses_product_brand_and_dynamic_instance_name(self) -> None:
        template = (FRONTEND / "templates" / "index.html").read_text()
        self.assertIn("<title>CraftControl", template)
        self.assertIn("craftcontrol-mark.svg", template)
        self.assertIn('id="instance-name"', template)
        self.assertNotIn("MalavaziRamos · Gerenciador", template)

    def test_brand_assets_are_valid(self) -> None:
        root = element_tree.parse(FRONTEND / "static" / "craftcontrol-mark.svg").getroot()
        self.assertTrue(root.tag.endswith("svg"))
        manifest = json.loads((FRONTEND / "static" / "site.webmanifest").read_text())
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
        script = frontend_script()
        settings = (FRONTEND / "static" / "js" / "features" / "settings" / "index.js").read_text()
        players = "\n".join(
            path.read_text()
            for path in sorted((FRONTEND / "static" / "js" / "features" / "players").glob("*.js"))
        )
        self.assertIn('class="player-roster-row', players)
        self.assertIn('class="player-detail-screen"', players)
        self.assertIn("Minecraft permission", players)
        self.assertIn("CraftControl access", players)
        self.assertIn('class="player-server-settings', settings)
        self.assertIn("Somente leitura", script)

    def test_player_profile_consolidates_authoritative_individual_analytics(self) -> None:
        players = "\n".join(
            path.read_text()
            for path in sorted((FRONTEND / "static" / "js" / "features" / "players").glob("*.js"))
        )
        stylesheet = (FRONTEND / "static" / "players.css").read_text()
        self.assertIn('class="player-data-workspace"', players)
        self.assertIn("stats.killsByType", players)
        self.assertIn("stats.brokenByType", players)
        self.assertIn("stats.placedByType", players)
        self.assertIn("stats.dimensions", players)
        self.assertIn('id="compare-player-data"', players)
        self.assertIn('state.analytics.player = profile.name', players)
        self.assertIn('class="player-record-drawer"', players)
        self.assertIn("permanent aggregates", players)
        self.assertIn(".player-data-ranking", stylesheet)
        self.assertIn(".player-record-drawer", stylesheet)

    def test_player_feature_separates_workspace_profile_access_history_and_telemetry(self) -> None:
        feature_root = FRONTEND / "static" / "js" / "features" / "players"
        index = (feature_root / "index.js").read_text()
        script = frontend_script()
        for name, factory in {
            "workspace": "createPlayersWorkspace",
            "profile": "createPlayerProfile",
            "access": "createPlayerAccess",
            "history": "createPlayerHistory",
            "telemetry": "createPlayerTelemetry",
        }.items():
            module = (feature_root / f"{name}.js").read_text()
            self.assertIn(f"export function {factory}", module)
            self.assertIn(f'from "./{name}.js?v=4"', index)
        self.assertIn('from "./features/players/index.js?v=4"', script)
        self.assertNotIn("function renderPlayerCards", script)
        self.assertNotIn("function bindPlayerAccess", script)
        self.assertNotIn("function deathHistoryMarkup", script)
        self.assertNotIn("function playerDataMarkup", script)

    def test_browser_api_attaches_session_bound_csrf_header(self) -> None:
        api_script = (FRONTEND / "static" / "js" / "api.js").read_text()
        app_script = frontend_script()
        auth_script = (FRONTEND / "static" / "js" / "auth.js").read_text()
        self.assertIn('headers["X-CSRF-Token"] = csrfToken', api_script)
        self.assertIn('typeof data.csrf_token === "string"', api_script)
        self.assertIn('./api.js?v=4', app_script)
        self.assertIn('./api.js?v=4', auth_script)

    def test_authentication_can_reveal_passwords_accessibly(self) -> None:
        auth_script = (FRONTEND / "static" / "js" / "auth.js").read_text()
        stylesheet = (FRONTEND / "static" / "auth.css").read_text()
        ui_root = element_tree.parse(FRONTEND / "static" / "craftcontrol-ui.svg").getroot()
        symbols = {node.attrib.get("id") for node in ui_root.iter() if node.tag.endswith("symbol")}
        self.assertIn("password-toggle", auth_script)
        self.assertIn("aria-pressed", auth_script)
        self.assertIn('class="auth-switch"', auth_script)
        self.assertIn('id="auth-title"', auth_script)
        self.assertIn("words.claimTitle", auth_script)
        self.assertIn('showPassword: "Mostrar senha"', auth_script)
        self.assertIn('showPassword: "Show password"', auth_script)
        self.assertIn('showPassword: "Mostrar contraseña"', auth_script)
        self.assertIn(".password-toggle", stylesheet)
        self.assertIn("ui-eye", symbols)

    def test_player_timeline_separates_action_from_localized_timestamp(self) -> None:
        history = (FRONTEND / "static" / "js" / "features" / "players" / "history.js").read_text()
        time_component = (FRONTEND / "static" / "js" / "components" / "time.js").read_text()
        stylesheet = (FRONTEND / "static" / "players.css").read_text()
        self.assertIn('class="timeline-action"', history)
        self.assertIn('class="timeline-timestamp"', time_component)
        self.assertIn('month: "short"', time_component)
        self.assertIn(".timeline-timestamp", stylesheet)

    def test_deaths_localize_game_terms_and_separate_source_from_timestamp(self) -> None:
        script = frontend_script()
        terms = (FRONTEND / "static" / "js" / "i18n" / "game-terms.js").read_text()
        history = (FRONTEND / "static" / "js" / "features" / "players" / "history.js").read_text()
        stylesheet = (FRONTEND / "static" / "players.css").read_text()
        template = (FRONTEND / "templates" / "index.html").read_text()
        self.assertIn('entityExplosion: ["creeper", "Explosão de criatura", "Entity explosion"]', terms)
        self.assertIn('skeleton: ["skeleton", "Esqueleto", "Skeleton"]', terms)
        self.assertIn('/static/craftcontrol-mobs.svg#mob-', terms)
        self.assertIn('class="death-entry-header"', history)
        self.assertIn(".death-source", stylesheet)
        self.assertIn('id="release-tags"', template)

    def test_players_and_analytics_receive_localized_dimension_names(self) -> None:
        script = frontend_script()
        terms = (FRONTEND / "static" / "js" / "i18n" / "game-terms.js").read_text()
        self.assertIn("function dimensionName(identifier)", terms)
        self.assertIn("blockIcon, dimensionName, gameTermMarkup", script)
        self.assertIn("blockTermMarkup, dimensionName, formatRankingValue", script)
        self.assertIn("formatDuration, dimensionName, localeTag", script)

    def test_original_creature_icon_pack_has_expected_pixel_art_symbols(self) -> None:
        root = element_tree.parse(FRONTEND / "static" / "craftcontrol-mobs.svg").getroot()
        symbols = {node.attrib.get("id") for node in root.iter() if node.tag.endswith("symbol")}
        expected = {
            "mob-unknown", "mob-zombie", "mob-drowned", "mob-skeleton", "mob-creeper",
            "mob-spider", "mob-enderman", "mob-cow", "mob-pig", "mob-sheep",
            "mob-chicken", "mob-witch", "mob-ghast", "mob-blaze", "mob-player",
            "mob-arrow", "mob-trident",
        }
        self.assertTrue(expected.issubset(symbols))

    def test_custom_ui_and_block_sprites_cover_core_interface_semantics(self) -> None:
        ui_root = element_tree.parse(FRONTEND / "static" / "craftcontrol-ui.svg").getroot()
        block_root = element_tree.parse(FRONTEND / "static" / "craftcontrol-blocks.svg").getroot()
        ui_symbols = {node.attrib.get("id") for node in ui_root.iter() if node.tag.endswith("symbol")}
        block_symbols = {node.attrib.get("id") for node in block_root.iter() if node.tag.endswith("symbol")}
        self.assertTrue({
            "ui-home", "ui-world", "ui-players", "ui-data", "ui-rules", "ui-server",
            "ui-refresh", "ui-save", "ui-warning", "ui-activity", "ui-deaths",
            "ui-rankings", "ui-blocks", "ui-combat", "ui-exploration", "ui-periods",
            "ui-logout",
        }.issubset(ui_symbols))
        self.assertTrue({
            "block-unknown", "block-stone", "block-deepslate", "block-dirt", "block-grass",
            "block-log", "block-planks", "block-diamond", "block-iron", "block-gold",
            "block-redstone", "block-lapis", "block-emerald", "block-ancient-debris",
        }.issubset(block_symbols))

    def test_mobile_topbar_prioritizes_status_and_icon_actions(self) -> None:
        stylesheet = (FRONTEND / "static" / "app.css").read_text()
        auth_stylesheet = (FRONTEND / "static" / "auth.css").read_text()
        auth_script = (FRONTEND / "static" / "js" / "auth.js").read_text()
        self.assertIn("@media (max-width: 620px)", stylesheet)
        self.assertIn(".release-tags { display: none; }", stylesheet)
        self.assertIn('.language-picker > button span, .language-picker > button b { display: none; }', stylesheet)
        self.assertIn("nav { top: 60px; }", stylesheet)
        self.assertIn("#identity button > span { display: none; }", auth_stylesheet)
        self.assertIn("#ui-logout", auth_script)

    def test_split_frontend_reports_its_own_release_version(self) -> None:
        script = frontend_script()
        server = (FRONTEND / "static" / "js" / "features" / "server" / "index.js").read_text()
        dockerfile = (FRONTEND / "Dockerfile").read_text()
        nginx = (FRONTEND / "nginx.conf").read_text()
        self.assertIn('fetch("/version.json", { cache: "no-store" })', server)
        self.assertIn("UI v", server)
        self.assertIn("CRAFTCONTROL_FRONTEND_VERSION=0.3.0", dockerfile)
        self.assertIn("/version.json", nginx)

    def test_world_rules_server_and_auth_have_feature_boundaries(self) -> None:
        script = frontend_script()
        expectations = {
            "world/index.js": "createWorldFeature",
            "rules/index.js": "createRulesFeature",
            "server/index.js": "createServerFeature",
            "auth/bootstrap.js": "startAuthenticatedApplication",
        }
        for relative, factory in expectations.items():
            module = (FRONTEND / "static" / "js" / "features" / relative).read_text()
            self.assertIn(f"function {factory}", module)
        self.assertIn("getWorldFeature().renderWorld()", script)
        self.assertIn("getRulesFeature().renderRules()", script)
        self.assertIn("getServerFeature().renderServer()", script)
        self.assertNotIn("function renderTimePanel", script)
        self.assertNotIn("function loadTelemetryPack", script)
        self.assertNotIn("requireSession().then", script)

    def test_frontend_core_owns_shared_state_and_dom_primitives(self) -> None:
        script = frontend_script()
        state_module = (FRONTEND / "static" / "js" / "core" / "state.js").read_text()
        dom_module = (FRONTEND / "static" / "js" / "core" / "dom.js").read_text()
        self.assertIn('from "./core/state.js?v=4"', script)
        self.assertIn('from "./core/dom.js?v=4"', script)
        self.assertIn("export const state", state_module)
        self.assertIn("export function escapeHtml", dom_module)
        self.assertNotIn("const state = {", script)
        self.assertNotIn("function escapeHtml", script)

    def test_frontend_components_own_feedback_and_time_primitives(self) -> None:
        script = frontend_script()
        feedback = (FRONTEND / "static" / "js" / "components" / "feedback.js").read_text()
        time = (FRONTEND / "static" / "js" / "components" / "time.js").read_text()
        self.assertIn('from "./components/feedback.js?v=4"', script)
        self.assertIn('from "./components/time.js?v=4"', script)
        self.assertIn("export function toast", feedback)
        self.assertIn("export function timelineTimestamp", time)
        self.assertIn("export function formatDuration", time)
        self.assertNotIn("function toast", script)
        self.assertNotIn("function formatDuration", script)

    def test_analytics_activity_and_deaths_have_a_feature_boundary(self) -> None:
        script = frontend_script()
        index = (FRONTEND / "static" / "js" / "features" / "analytics" / "index.js").read_text()
        activity = (FRONTEND / "static" / "js" / "features" / "analytics" / "activity.js").read_text()
        self.assertIn('from "./features/analytics/index.js?v=4"', script)
        self.assertIn('from "./activity.js?v=4"', index)
        self.assertIn("export function createActivityView", activity)
        self.assertIn('"player.death"', activity)
        self.assertIn('es: "Murió"', activity)
        self.assertIn("activityView.eventsMarkup", index)
        self.assertIn("activityView.showDeathDetails", index)
        self.assertNotIn("function analyticsEventsMarkup", script)
        self.assertNotIn("function showDeathDetails", script)

    def test_interface_uses_custom_icons_and_bilingual_block_labels(self) -> None:
        script = frontend_script()
        terms = (FRONTEND / "static" / "js" / "i18n" / "game-terms.js").read_text()
        template = (FRONTEND / "templates" / "index.html").read_text()
        self.assertIn('stone: ["Pedra", "Stone"]', terms)
        self.assertIn('diamond_ore: ["Minério de diamante", "Diamond ore"]', terms)
        self.assertIn('cobblestone_wall: ["Muro de pedregulho", "Cobblestone wall"]', terms)
        self.assertIn('leaf_litter: ["Folhiço", "Leaf litter"]', terms)
        self.assertIn('stone_stairs: ["Escadas de pedra", "Stone stairs"]', terms)
        self.assertIn('stripped_birch_log: ["Tronco de bétula descascado", "Stripped birch log"]', terms)
        self.assertIn('reeds: ["Cana-de-açúcar", "Sugar cane"]', terms)
        self.assertIn('cobblestone: "Adoquín"', terms)
        self.assertIn('leaf_litter: "Hojarasca"', terms)
        self.assertIn('data-locale="es"', template)
        self.assertIn('ui-flag-br', template)
        self.assertIn('ui-flag-us', template)
        self.assertIn('ui-flag-es', template)
        i18n = (FRONTEND / "static" / "js" / "i18n" / "index.js").read_text()
        self.assertIn('import { es } from "./es.js?v=4"', i18n)
        self.assertIn("function blockTermMarkup", terms)
        self.assertIn("/static/craftcontrol-blocks.svg#block-", terms)
        self.assertIn("/static/craftcontrol-ui.svg#ui-", terms)
        self.assertIn("craftcontrol-ui.svg#ui-refresh", template)
        legacy_icons = re.compile(r"[☀☠⚔♛♟⚙◆◇◈▦▥▤☷⌂⌛♥▶↝➶✦✓↻⛏⚡⚠]")
        self.assertIsNone(legacy_icons.search(script))
        self.assertIsNone(legacy_icons.search(template))

    def test_recent_sessions_have_distinct_state_duration_and_period_layout(self) -> None:
        history = (FRONTEND / "static" / "js" / "features" / "players" / "history.js").read_text()
        stylesheet = (FRONTEND / "static" / "players.css").read_text()
        self.assertIn('class="session-state"', history)
        self.assertIn('class="session-duration"', history)
        self.assertIn('class="session-period"', history)
        self.assertIn("session.disconnected_at", history)
        self.assertIn(".session-item.is-inferred", stylesheet)

    def test_analytics_has_dedicated_bilingual_mobile_workspace(self) -> None:
        script = frontend_script()
        activity = (FRONTEND / "static" / "js" / "features" / "analytics" / "activity.js").read_text()
        analytics = "\n".join(
            path.read_text()
            for path in sorted((FRONTEND / "static" / "js" / "features" / "analytics").glob("*.js"))
        )
        state_module = (FRONTEND / "static" / "js" / "core" / "state.js").read_text()
        stylesheet = (FRONTEND / "static" / "analytics.css").read_text()
        template = (FRONTEND / "templates" / "index.html").read_text()
        self.assertIn('tabs: ["home", "world", "players", "analytics"', state_module)
        catalogs = "\n".join(
            (FRONTEND / "static" / "js" / "i18n" / f"{locale}.js").read_text()
            for locale in ("pt", "en", "es")
        )
        self.assertIn("Atividade do servidor", catalogs)
        self.assertIn("Server activity", catalogs)
        self.assertIn('["deaths", "deaths", "deathsView"]', analytics)
        self.assertIn("@media (max-width: 480px)", stylesheet)
        self.assertIn("analytics.css", template)
        self.assertIn('data-analytics-player=', activity)
        self.assertIn('id="analytics-death-dialog"', analytics)
        self.assertIn("respawnsOnly", analytics)
        self.assertIn('class="ranking-podium', analytics)
        self.assertIn("rankingsTitle", catalogs)
        self.assertIn(".podium-place.rank-1", stylesheet)
        self.assertIn('["combat", "combat", "combatView"]', analytics)
        self.assertIn("combatEmptyHelp", catalogs)
        self.assertIn(".combat-zero", stylesheet)
        self.assertIn('["exploration", "exploration", "explorationView"]', analytics)
        self.assertIn("explorationEmptyHelp", catalogs)
        self.assertIn(".exploration-zero", stylesheet)
        self.assertIn('["trends", "periods", "trendsView"]', analytics)
        self.assertIn("collectionStarted", catalogs)
        self.assertIn(".heatmap-grid", stylesheet)

    def test_analytics_panels_are_owned_by_separate_feature_modules(self) -> None:
        feature_root = FRONTEND / "static" / "js" / "features" / "analytics"
        index = (feature_root / "index.js").read_text()
        script = frontend_script()
        for name, factory in {
            "rankings": "createRankingsPanel",
            "blocks": "createBlocksPanel",
            "combat": "createCombatPanel",
            "exploration": "createExplorationPanel",
            "trends": "createTrendsPanel",
        }.items():
            module = (feature_root / f"{name}.js").read_text()
            self.assertIn(f"export function {factory}", module)
            self.assertIn(f'from "./{name}.js?v=4"', index)
        self.assertIn("createAnalyticsFeature", script)
        self.assertNotIn("async function renderRankingsPanel", script)
        self.assertNotIn("async function renderBlocksPanel", script)
        self.assertNotIn("async function renderCombatPanel", script)
        self.assertNotIn("async function renderExplorationPanel", script)
        self.assertNotIn("async function renderTrendsPanel", script)
