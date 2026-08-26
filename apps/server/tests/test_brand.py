"""Brand and infrastructure tests for non-JS assets.

JS structural contracts have been migrated to Jest — see apps/client/tests/.
This file covers assets that require Python tooling (SVG XML parsing, JSON,
Markdown, YAML) and that are not part of the JS module graph.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as element_tree
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FRONTEND = ROOT / "apps" / "frontend"


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
