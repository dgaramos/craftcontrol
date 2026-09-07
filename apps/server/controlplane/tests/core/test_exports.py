"""Serialization and ceilings shared by every export resource (issue #270).

Covers the format-neutral half of docs/exports.md: manifest fields, the JSON and
CSV representations, and the two ceilings that refuse rather than truncate.
"""

from __future__ import annotations

import json

import pytest

from src.core.exports import (
    BYTE_LIMIT,
    ROW_LIMIT,
    ExportTooLarge,
    Manifest,
    file_name,
    flatten,
    rfc3339,
    serialize_csv,
    serialize_json,
)


def _manifest(**overrides) -> Manifest:
    base = {
        "resource": "players.profiles",
        "format": "json",
        "filters": {"player": "Steve"},
        "row_count": 1,
        "generated_at": 1788806153.0,
        "timezone": "America/Sao_Paulo",
    }
    base.update(overrides)
    return Manifest(**base)


# -- manifest ---------------------------------------------------------------

def test_manifest_declares_every_contract_field() -> None:
    payload = _manifest().as_dict()
    assert set(payload) == {
        "export_schema_version", "resource", "format", "filters", "generated_at",
        "row_count", "timezone", "row_limit", "truncated",
    }
    assert payload["export_schema_version"] == 1
    assert payload["row_limit"] == ROW_LIMIT


def test_manifest_never_reports_a_truncated_payload() -> None:
    """An oversized export is refused, so `truncated` can only ever be false."""
    assert _manifest().as_dict()["truncated"] is False


def test_manifest_records_the_timezone_that_produced_day_keys() -> None:
    assert _manifest(timezone="Europe/Lisbon").as_dict()["timezone"] == "Europe/Lisbon"


def test_manifest_falls_back_to_the_deployment_timezone(monkeypatch) -> None:
    monkeypatch.setenv("TZ", "Europe/Lisbon")
    assert _manifest(timezone="").as_dict()["timezone"] == "Europe/Lisbon"


# -- JSON -------------------------------------------------------------------

def test_json_payload_carries_the_manifest_and_the_records() -> None:
    payload = json.loads(serialize_json(_manifest(), [{"id": "p1", "name": "Steve"}]))
    assert payload["manifest"]["resource"] == "players.profiles"
    assert payload["records"] == [{"id": "p1", "name": "Steve"}]


# -- CSV --------------------------------------------------------------------

def test_csv_writes_a_stable_header_and_lf_endings() -> None:
    body = serialize_csv([{"id": "p1", "name": "Steve"}], ["id", "name"])
    assert body == "id,name\np1,Steve\n"
    assert "\r\n" not in body


def test_csv_renders_nulls_as_empty_and_booleans_as_words() -> None:
    body = serialize_csv([{"id": "p1", "online": True, "close_reason": None}],
                         ["id", "online", "close_reason"])
    assert body.splitlines()[1] == "p1,true,"


def test_csv_quotes_values_containing_separators() -> None:
    body = serialize_csv([{"name": 'Steve, "the" builder'}], ["name"])
    assert body.splitlines()[1] == '"Steve, ""the"" builder"'


def test_csv_flattens_nested_values_into_dotted_columns() -> None:
    body = serialize_csv([{"player": {"id": "p1", "name": "Steve"}}], ["player.id", "player.name"])
    assert body.splitlines()[1] == "p1,Steve"


def test_csv_column_order_follows_the_declared_columns_not_the_record() -> None:
    body = serialize_csv([{"name": "Steve", "id": "p1"}], ["id", "name"])
    assert body.splitlines()[0] == "id,name"
    assert body.splitlines()[1] == "p1,Steve"


def test_flatten_joins_sequences_into_one_cell() -> None:
    assert flatten({"aliases": ["Steve", "Steven"]}) == {"aliases": "Steve Steven"}


# -- ceilings ---------------------------------------------------------------

def test_record_ceiling_refuses_before_serializing() -> None:
    from src.core.exports import enforce_row_limit

    enforce_row_limit(ROW_LIMIT)
    with pytest.raises(ExportTooLarge) as error:
        enforce_row_limit(ROW_LIMIT + 1)
    assert error.value.limit == "record"
    assert error.value.measured == ROW_LIMIT + 1


def test_byte_ceiling_measures_the_serialized_payload_not_the_record_count() -> None:
    """Two records can exceed the byte ceiling while the record ceiling passes."""
    oversized = [{"id": "p1", "note": "x" * 128}]
    with pytest.raises(ExportTooLarge) as error:
        serialize_json(_manifest(), oversized, allowed=64)
    assert error.value.limit == "byte"
    assert error.value.allowed == 64
    assert error.value.measured > 64


def test_byte_ceiling_applies_to_csv_including_its_header() -> None:
    with pytest.raises(ExportTooLarge):
        serialize_csv([{"id": "p1"}], ["id"], allowed=4)


def test_byte_ceiling_counts_utf8_bytes_not_characters() -> None:
    """A multibyte name costs more than its length in characters."""
    body = serialize_csv([{"name": "Ana"}], ["name"], allowed=64)
    assert len(body.encode("utf-8")) == len(body)
    with pytest.raises(ExportTooLarge):
        serialize_csv([{"name": "ãããããã"}], ["name"], allowed=len("name\nãããããã\n"))


def test_default_ceilings_match_the_documented_contract() -> None:
    assert ROW_LIMIT == 10_000
    assert BYTE_LIMIT == 5 * 1024 * 1024


# -- rendering helpers ------------------------------------------------------

def test_instants_render_as_rfc3339_utc_for_csv() -> None:
    assert rfc3339(1788806153) == "2026-09-07T18:35:53Z"
    assert rfc3339(None) == ""


def test_file_name_carries_the_resource_and_a_utc_stamp() -> None:
    assert file_name("players.profiles", "csv", 1788806153) == (
        "craftcontrol-players.profiles-20260907T183553Z.csv"
    )
