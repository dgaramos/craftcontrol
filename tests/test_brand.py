"""Brand, UI, and frontend structural tests."""
from __future__ import annotations

import json
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



def test_split_frontend_reports_its_own_release_version() -> None:
    script = frontend_script()
    server = (FRONTEND / "static" / "js" / "features" / "server" / "index.js").read_text()
    dockerfile = (FRONTEND / "Dockerfile").read_text()
    nginx = (FRONTEND / "nginx.conf").read_text()
    assert 'fetch("/version.json", { cache: "no-store" })' in server
    assert "UI v" in server
    assert "CRAFTCONTROL_FRONTEND_VERSION=0.3.6" in dockerfile
    assert "/version.json" in nginx



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
