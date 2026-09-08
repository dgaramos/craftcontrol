"""The manager-side metric allowlist (issue #274).

`docs/telemetry-metrics.md` says every metric ships disabled and is enabled on
its own. These tests hold the manager to the half it controls: which names it
accepts, and how it reads a state the pack reported.
"""
from __future__ import annotations

import pytest

from src.telemetry.metrics import METRICS, UnknownMetric, dumps, loads, normalize, validate


def test_the_allowlist_names_every_switchable_metric() -> None:
    assert METRICS == (
        "itemUse", "blockInteractions", "entityInteractions", "containerInteractions",
    )


def _all(**overrides: bool) -> dict[str, bool]:
    """The full state with only the named metrics on."""
    return {metric: overrides.get(metric, False) for metric in METRICS}


def test_a_known_metric_is_accepted() -> None:
    assert validate("itemUse") == "itemUse"


@pytest.mark.parametrize("metric", ["chatCapture", "", "ITEMUSE", None, 1, ["itemUse"], "blockinteractions"])
def test_anything_outside_the_allowlist_is_refused(metric: object) -> None:
    with pytest.raises(UnknownMetric):
        validate(metric)


@pytest.mark.parametrize("reported", [None, {}, "broken", {"itemUse": "yes"}, {"itemUse": 1}])
def test_anything_but_an_explicit_true_reads_as_disabled(reported: object) -> None:
    # A metric the pack does not report is not enabled: an older pack or a
    # truncated payload must never read as opted in.
    assert normalize(reported) == _all()


def test_a_reported_metric_reads_back_enabled() -> None:
    assert normalize({"itemUse": True}) == _all(itemUse=True)


def test_an_unknown_reported_name_is_dropped() -> None:
    assert normalize({"itemUse": True, "chatCapture": True}) == _all(itemUse=True)


def test_persisted_state_round_trips() -> None:
    assert loads(dumps({"itemUse": True})) == _all(itemUse=True)


@pytest.mark.parametrize("raw", ["", None, "{not json", "[]", 7])
def test_a_damaged_persisted_value_reads_as_disabled(raw: object) -> None:
    assert loads(raw) == _all()


def test_each_interaction_metric_is_switchable_on_its_own() -> None:
    for metric in ("blockInteractions", "entityInteractions", "containerInteractions"):
        assert validate(metric) == metric
        state = normalize({metric: True})
        assert state[metric] is True
        assert sum(state.values()) == 1
