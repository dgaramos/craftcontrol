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
