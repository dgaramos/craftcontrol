from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = Path(__file__).with_name("openapi.json")
OUTPUT_PATH = ROOT / "apps" / "client" / "static" / "js" / "api-contract.d.ts"


def type_expression(schema: dict[str, Any]) -> str:
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]
    if "const" in schema:
        return json.dumps(schema["const"])
    if "enum" in schema:
        return " | ".join(json.dumps(value) for value in schema["enum"])
    if "allOf" in schema:
        return " & ".join(type_expression(item) for item in schema["allOf"])
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        return " | ".join(type_expression({**schema, "type": value}) for value in schema_type)
    if schema_type == "string":
        return "string"
    if schema_type in {"integer", "number"}:
        return "number"
    if schema_type == "boolean":
        return "boolean"
    if schema_type == "null":
        return "null"
    if schema_type == "array":
        return f"Array<{type_expression(schema.get('items', {}))}>"
    if schema_type == "object" or "properties" in schema:
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        members = [
            f"{name}{'' if name in required else '?'}: {type_expression(value)};"
            for name, value in properties.items()
        ]
        additional = schema.get("additionalProperties")
        if additional is True or (not properties and additional is None):
            members.append("[key: string]: unknown;")
        elif isinstance(additional, dict):
            members.append(f"[key: string]: {type_expression(additional)};")
        return "{ " + " ".join(members) + " }"
    return "unknown"


def generate(spec: dict[str, Any]) -> str:
    version = spec["info"]["version"]
    lines = [
        "// Generated from packages/contracts/openapi.json.",
        "// Do not edit by hand; run: python packages/contracts/generate_types.py --write",
        f"export const contractVersion: {json.dumps(version)};",
        "",
    ]
    for name, schema in spec["components"]["schemas"].items():
        lines.append(f"export type {name} = {type_expression(schema)};")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate CraftControl frontend API types")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true", help="write the generated declaration file")
    action.add_argument("--check", action="store_true", help="fail when the declaration file is stale")
    action.add_argument("--stdout", action="store_true", help="print the generated declaration file")
    args = parser.parse_args()
    generated = generate(json.loads(SPEC_PATH.read_text()))
    if args.write:
        OUTPUT_PATH.write_text(generated)
        return 0
    if args.stdout:
        print(generated, end="")
        return 0
    if not OUTPUT_PATH.exists() or OUTPUT_PATH.read_text() != generated:
        print(f"stale generated API types: {OUTPUT_PATH}")
        return 1
    print("client API types: current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
