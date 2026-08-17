"""Brand, UI, and frontend structural tests."""
from __future__ import annotations

import json
import re
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


def test_frontend_entrypoint_is_only_bootstrap_and_composition() -> None:
    entrypoint = (FRONTEND / "static" / "app.js").read_text()
    composition = (FRONTEND / "static" / "js" / "composition.js").read_text()
    settings = (FRONTEND / "static" / "js" / "features" / "settings" / "index.js").read_text()
    assert len(entrypoint.splitlines()) <= 5
    assert "startApplication" in entrypoint
    assert "createNavigation" in composition
    assert "connectInvalidation" in composition
    assert "createSettingsFeature" in settings


def test_template_uses_product_brand_and_dynamic_instance_name() -> None:
    template = (FRONTEND / "templates" / "index.html").read_text()
    assert "<title>CraftControl" in template
    assert "craftcontrol-mark.svg" in template
    assert 'id="instance-name"' in template
    assert "MalavaziRamos · Gerenciador" not in template


def test_brand_assets_are_valid() -> None:
    root = element_tree.parse(FRONTEND / "static" / "craftcontrol-mark.svg").getroot()
    assert root.tag.endswith("svg")
    manifest = json.loads((FRONTEND / "static" / "site.webmanifest").read_text())
    assert manifest["name"] == "CraftControl"
    assert manifest["icons"][0]["src"] == "/static/craftcontrol-mark.svg"


def test_readme_presents_craftcontrol_without_hiding_compatibility_names() -> None:
    readme = (ROOT / "README.md").read_text()
    assert "<h1>CraftControl</h1>" in readme
    assert "compatibility" in readme.casefold()
    assert "trusted private networks" in readme


def test_compose_uses_final_product_name() -> None:
    compose = (ROOT / "docker-compose.yml").read_text()
    assert "  craftcontrol:\n" in compose
    assert "container_name: craftcontrol" in compose
    assert "minecraft-bedrock-manager" not in compose


def test_player_workspace_separates_roster_profile_and_permission_scopes() -> None:
    script = frontend_script()
    settings = (FRONTEND / "static" / "js" / "features" / "settings" / "index.js").read_text()
    players = "\n".join(
        path.read_text()
        for path in sorted((FRONTEND / "static" / "js" / "features" / "players").glob("*.js"))
    )
    index_html = (FRONTEND / "templates" / "index.html").read_text()
    assert "tpl-player-roster-row" in index_html  # markup extracted to native template
    assert 'class="player-detail-screen"' in players
    assert "Minecraft permission" in players
    assert "CraftControl access" in players
    assert 'class="player-server-settings' in settings
    assert "Somente leitura" in script


def test_player_profile_consolidates_authoritative_individual_analytics() -> None:
    players = "\n".join(
        path.read_text()
        for path in sorted((FRONTEND / "static" / "js" / "features" / "players").glob("*.js"))
    )
    stylesheet = (FRONTEND / "static" / "players.css").read_text()
    assert 'class="player-data-workspace"' in players
    assert "stats.killsByType" in players
    assert "stats.brokenByType" in players
    assert "stats.placedByType" in players
    assert "stats.dimensions" in players
    assert 'id="compare-player-data"' in players
    assert 'state.analytics.player = profile.name' in players
    assert 'class="player-record-drawer"' in players
    assert "permanent aggregates" in players
    assert ".player-data-ranking" in stylesheet
    assert ".player-record-drawer" in stylesheet


def test_player_feature_separates_workspace_profile_access_history_and_telemetry() -> None:
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
        assert f"export function {factory}" in module
        assert f'from "./{name}.js?v=7"' in index
    assert 'from "./features/players/index.js?v=7"' in script
    assert "function renderPlayerCards" not in script
    assert "function bindPlayerAccess" not in script
    assert "function deathHistoryMarkup" not in script
    assert "function playerDataMarkup" not in script


def test_browser_api_attaches_session_bound_csrf_header() -> None:
    api_script = (FRONTEND / "static" / "js" / "api.js").read_text()
    app_script = frontend_script()
    auth_script = (FRONTEND / "static" / "js" / "auth.js").read_text()
    assert 'headers["X-CSRF-Token"] = csrfToken' in api_script
    assert 'typeof data.csrf_token === "string"' in api_script
    assert './api.js?v=7' in app_script
    assert './api.js?v=7' in auth_script


def test_authentication_can_reveal_passwords_accessibly() -> None:
    auth_script = (FRONTEND / "static" / "js" / "auth.js").read_text()
    stylesheet = (FRONTEND / "static" / "auth.css").read_text()
    ui_root = element_tree.parse(FRONTEND / "static" / "craftcontrol-ui.svg").getroot()
    symbols = {node.attrib.get("id") for node in ui_root.iter() if node.tag.endswith("symbol")}
    assert "password-toggle" in auth_script
    assert "aria-pressed" in auth_script
    assert 'class="auth-switch"' in auth_script
    assert 'const form = claim' in auth_script
    assert 'overlay.querySelector("form")' in auth_script
    assert 'id="claim-form" hidden' not in auth_script
    assert "words.claimTitle" in auth_script
    assert ".auth-card form[hidden]" in stylesheet
    assert 'showPassword: "Mostrar senha"' in auth_script
    assert 'showPassword: "Show password"' in auth_script
    assert 'showPassword: "Mostrar contraseña"' in auth_script
    assert ".password-toggle" in stylesheet
    assert "ui-eye" in symbols


def test_player_timeline_separates_action_from_localized_timestamp() -> None:
    history = (FRONTEND / "static" / "js" / "features" / "players" / "history.js").read_text()
    time_component = (FRONTEND / "static" / "js" / "components" / "time.js").read_text()
    stylesheet = (FRONTEND / "static" / "players.css").read_text()
    assert 'class="timeline-action"' in history
    assert 'class="timeline-timestamp"' in time_component
    assert 'month: "short"' in time_component
    assert ".timeline-timestamp" in stylesheet


def test_deaths_localize_game_terms_and_separate_source_from_timestamp() -> None:
    script = frontend_script()
    terms = (FRONTEND / "static" / "js" / "i18n" / "game-terms.js").read_text()
    history = (FRONTEND / "static" / "js" / "features" / "players" / "history.js").read_text()
    stylesheet = (FRONTEND / "static" / "players.css").read_text()
    template = (FRONTEND / "templates" / "index.html").read_text()
    assert 'entityExplosion: ["creeper", "Explosão de criatura", "Entity explosion"]' in terms
    assert 'skeleton: ["skeleton", "Esqueleto", "Skeleton"]' in terms
    assert '/static/craftcontrol-mobs.svg#mob-' in terms
    assert 'class="death-entry-header"' in history
    assert ".death-source" in stylesheet
    assert 'id="release-tags"' in template


def test_players_and_analytics_receive_localized_dimension_names() -> None:
    script = frontend_script()
    terms = (FRONTEND / "static" / "js" / "i18n" / "game-terms.js").read_text()
    assert "function dimensionName(identifier)" in terms
    assert "blockIcon, dimensionName, gameTermMarkup" in script
    assert "blockTermMarkup, dimensionName, formatRankingValue" in script
    assert "formatDuration, dimensionName, localeTag" in script


def test_original_creature_icon_pack_has_expected_pixel_art_symbols() -> None:
    root = element_tree.parse(FRONTEND / "static" / "craftcontrol-mobs.svg").getroot()
    symbols = {node.attrib.get("id") for node in root.iter() if node.tag.endswith("symbol")}
    expected = {
        "mob-unknown", "mob-zombie", "mob-drowned", "mob-skeleton", "mob-creeper",
        "mob-spider", "mob-enderman", "mob-cow", "mob-pig", "mob-sheep",
        "mob-chicken", "mob-witch", "mob-ghast", "mob-blaze", "mob-player",
        "mob-arrow", "mob-trident",
    }
    assert expected.issubset(symbols)


def test_custom_ui_and_block_sprites_cover_core_interface_semantics() -> None:
    ui_root = element_tree.parse(FRONTEND / "static" / "craftcontrol-ui.svg").getroot()
    block_root = element_tree.parse(FRONTEND / "static" / "craftcontrol-blocks.svg").getroot()
    ui_symbols = {node.attrib.get("id") for node in ui_root.iter() if node.tag.endswith("symbol")}
    block_symbols = {node.attrib.get("id") for node in block_root.iter() if node.tag.endswith("symbol")}
    assert {
        "ui-home", "ui-world", "ui-players", "ui-data", "ui-rules", "ui-server",
        "ui-refresh", "ui-save", "ui-warning", "ui-activity", "ui-deaths",
        "ui-rankings", "ui-blocks", "ui-combat", "ui-exploration", "ui-periods",
        "ui-logout",
    }.issubset(ui_symbols)
    assert {
        "block-unknown", "block-stone", "block-deepslate", "block-dirt", "block-grass",
        "block-log", "block-planks", "block-diamond", "block-iron", "block-gold",
        "block-redstone", "block-lapis", "block-emerald", "block-ancient-debris",
    }.issubset(block_symbols)


def test_mobile_topbar_prioritizes_status_and_icon_actions() -> None:
    stylesheet = (FRONTEND / "static" / "app.css").read_text()
    auth_stylesheet = (FRONTEND / "static" / "auth.css").read_text()
    auth_script = (FRONTEND / "static" / "js" / "auth.js").read_text()
    assert "@media (max-width: 620px)" in stylesheet
    assert ".release-tags { display: none; }" in stylesheet
    assert '.language-picker > button span, .language-picker > button b { display: none; }' in stylesheet
    assert "nav { top: 60px; }" in stylesheet
    assert "#identity button > span { display: none; }" in auth_stylesheet
    index_html = (FRONTEND / "templates" / "index.html").read_text()
    assert "#ui-logout" in index_html  # icon moved to tpl-identity native template


def test_mobile_page_scroll_is_bounded_and_navigation_resets_position() -> None:
    stylesheet = (FRONTEND / "static" / "app.css").read_text()
    navigation = (FRONTEND / "static" / "js" / "core" / "navigation.js").read_text()
    template = (FRONTEND / "templates" / "index.html").read_text()
    assert "overscroll-behavior-y: none" in stylesheet
    assert "min-height: 100dvh" in stylesheet
    assert "overflow-x: clip" in stylesheet
    assert 'window.scrollTo({ top: 0, left: 0, behavior: "auto" })' in navigation
    assert '/static/app.css?v=25' in template
    assert '/static/app.js?v=64' in template


def test_split_frontend_reports_its_own_release_version() -> None:
    script = frontend_script()
    server = (FRONTEND / "static" / "js" / "features" / "server" / "index.js").read_text()
    dockerfile = (FRONTEND / "Dockerfile").read_text()
    nginx = (FRONTEND / "nginx.conf").read_text()
    assert 'fetch("/version.json", { cache: "no-store" })' in server
    assert "UI v" in server
    assert "CRAFTCONTROL_FRONTEND_VERSION=0.3.6" in dockerfile
    assert "/version.json" in nginx


def test_world_rules_server_and_auth_have_feature_boundaries() -> None:
    script = frontend_script()
    expectations = {
        "world/index.js": "createWorldFeature",
        "rules/index.js": "createRulesFeature",
        "server/index.js": "createServerFeature",
        "auth/bootstrap.js": "startAuthenticatedApplication",
    }
    for relative, factory in expectations.items():
        module = (FRONTEND / "static" / "js" / "features" / relative).read_text()
        assert f"function {factory}" in module
    assert "getWorldFeature().renderWorld()" in script
    assert "getRulesFeature().renderRules()" in script
    assert "getServerFeature().renderServer()" in script
    assert "function renderTimePanel" not in script
    assert "function loadTelemetryPack" not in script
    assert "requireSession().then" not in script


def test_frontend_core_owns_shared_state_and_dom_primitives() -> None:
    script = frontend_script()
    state_module = (FRONTEND / "static" / "js" / "core" / "state.js").read_text()
    dom_module = (FRONTEND / "static" / "js" / "core" / "dom.js").read_text()
    assert 'from "./core/state.js?v=7"' in script
    assert 'from "./core/dom.js?v=7"' in script
    assert "export const state" in state_module
    assert "export function escapeHtml" in dom_module
    assert "const state = {" not in script
    assert "function escapeHtml" not in script


def test_frontend_components_own_feedback_and_time_primitives() -> None:
    script = frontend_script()
    feedback = (FRONTEND / "static" / "js" / "components" / "feedback.js").read_text()
    time = (FRONTEND / "static" / "js" / "components" / "time.js").read_text()
    assert 'from "./components/feedback.js?v=7"' in script
    assert 'from "./components/time.js?v=7"' in script
    assert "export function toast" in feedback
    assert "export function timelineTimestamp" in time
    assert "export function formatDuration" in time
    assert "function toast" not in script
    assert "function formatDuration" not in script


def test_analytics_activity_and_deaths_have_a_feature_boundary() -> None:
    script = frontend_script()
    index = (FRONTEND / "static" / "js" / "features" / "analytics" / "index.js").read_text()
    activity = (FRONTEND / "static" / "js" / "features" / "analytics" / "activity.js").read_text()
    assert 'from "./features/analytics/index.js?v=8"' in script
    assert 'from "./activity.js?v=7"' in index
    assert "export function createActivityView" in activity
    assert '"player.death"' in activity
    assert 'es: "Murió"' in activity
    assert "activityView.eventsMarkup" in index
    assert "activityView.showDeathDetails" in index
    assert "function analyticsEventsMarkup" not in script
    assert "function showDeathDetails" not in script


def test_interface_uses_custom_icons_and_bilingual_block_labels() -> None:
    script = frontend_script()
    terms = (FRONTEND / "static" / "js" / "i18n" / "game-terms.js").read_text()
    template = (FRONTEND / "templates" / "index.html").read_text()
    assert 'stone: ["Pedra", "Stone"]' in terms
    assert 'diamond_ore: ["Minério de diamante", "Diamond ore"]' in terms
    assert 'cobblestone_wall: ["Muro de pedregulho", "Cobblestone wall"]' in terms
    assert 'leaf_litter: ["Folhiço", "Leaf litter"]' in terms
    assert 'stone_stairs: ["Escadas de pedra", "Stone stairs"]' in terms
    assert 'stripped_birch_log: ["Tronco de bétula descascado", "Stripped birch log"]' in terms
    assert 'reeds: ["Cana-de-açúcar", "Sugar cane"]' in terms
    assert 'cobblestone: "Adoquín"' in terms
    assert 'leaf_litter: "Hojarasca"' in terms
    assert 'data-locale="es"' in template
    assert 'ui-flag-br' in template
    assert 'ui-flag-us' in template
    assert 'ui-flag-es' in template
    i18n = (FRONTEND / "static" / "js" / "i18n" / "index.js").read_text()
    assert 'import { es } from "./es.js?v=8"' in i18n
    assert "function blockTermMarkup" in terms
    assert "/static/craftcontrol-blocks.svg#block-" in terms
    assert "/static/craftcontrol-ui.svg#ui-" in terms
    assert "craftcontrol-ui.svg#ui-refresh" in template
    legacy_icons = re.compile(r"[☀☠⚔♛♟⚙◆◇◈▦▥▤☷⌂⌛♥▶↝➶✦✓↻⛏⚡⚠]")
    assert legacy_icons.search(script) is None
    assert legacy_icons.search(template) is None


def test_recent_sessions_have_distinct_state_duration_and_period_layout() -> None:
    history = (FRONTEND / "static" / "js" / "features" / "players" / "history.js").read_text()
    stylesheet = (FRONTEND / "static" / "players.css").read_text()
    assert 'class="session-state"' in history
    assert 'class="session-duration"' in history
    assert 'class="session-period"' in history
    assert "session.disconnected_at" in history
    assert ".session-item.is-inferred" in stylesheet


def test_analytics_has_dedicated_bilingual_mobile_workspace() -> None:
    script = frontend_script()
    activity = (FRONTEND / "static" / "js" / "features" / "analytics" / "activity.js").read_text()
    analytics = "\n".join(
        path.read_text()
        for path in sorted((FRONTEND / "static" / "js" / "features" / "analytics").glob("*.js"))
    )
    state_module = (FRONTEND / "static" / "js" / "core" / "state.js").read_text()
    stylesheet = (FRONTEND / "static" / "analytics.css").read_text()
    template = (FRONTEND / "templates" / "index.html").read_text()
    assert 'tabs: ["home", "world", "players", "analytics"' in state_module
    catalogs = "\n".join(
        (FRONTEND / "static" / "js" / "i18n" / f"{locale}.js").read_text()
        for locale in ("pt", "en", "es")
    )
    assert "Atividade do servidor" in catalogs
    assert "Server activity" in catalogs
    assert '["deaths", "deaths", "deathsView"]' in analytics
    assert "@media (max-width: 480px)" in stylesheet
    assert "analytics.css" in template
    assert 'data-analytics-player=' in activity
    assert 'id="analytics-death-dialog"' in analytics
    assert "respawnsOnly" in analytics
    assert 'class="ranking-podium' in analytics
    assert "rankingsTitle" in catalogs
    assert ".podium-place.rank-1" in stylesheet
    assert '["combat", "combat", "combatView"]' in analytics
    assert "combatEmptyHelp" in catalogs
    assert ".combat-zero" in stylesheet
    assert '["exploration", "exploration", "explorationView"]' in analytics
    assert "explorationEmptyHelp" in catalogs
    assert ".exploration-zero" in stylesheet
    assert '["trends", "periods", "trendsView"]' in analytics
    assert "collectionStarted" in catalogs
    assert ".heatmap-grid" in stylesheet
    assert ".trends-main-grid { display: grid; min-width: 0" in stylesheet
    assert ".calendar-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }" in stylesheet
    assert ".heatmap-scroll { width: 100%; max-width: 100%" in stylesheet


def test_activity_timeline_loads_incrementally_and_stops_at_the_last_page() -> None:
    analytics = (FRONTEND / "static" / "js" / "features" / "analytics" / "index.js").read_text()
    stylesheet = (FRONTEND / "static" / "analytics.css").read_text()
    catalogs = "\n".join(
        (FRONTEND / "static" / "js" / "i18n" / f"{locale}.js").read_text()
        for locale in ("pt", "en", "es")
    )
    assert 'const hasMore = result.page < result.pages' in analytics
    assert 'new window.IntersectionObserver' in analytics
    assert 'if (loadingActivity) return' in analytics
    assert 'activityObserver?.disconnect()' in analytics
    assert 'activityTimelineEnd' in analytics
    assert 'id="analytics-next"' not in analytics
    assert '.activity-scroll-sentinel' in stylesheet
    assert 'Fim da linha do tempo' in catalogs
    assert 'End of timeline' in catalogs
    assert 'Fin de la línea de tiempo' in catalogs


def test_analytics_panels_are_owned_by_separate_feature_modules() -> None:
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
        assert f"export function {factory}" in module
        assert f'from "./{name}.js?v=7"' in index
    assert "createAnalyticsFeature" in script
    assert "async function renderRankingsPanel" not in script
    assert "async function renderBlocksPanel" not in script
    assert "async function renderCombatPanel" not in script
    assert "async function renderExplorationPanel" not in script
    assert "async function renderTrendsPanel" not in script
