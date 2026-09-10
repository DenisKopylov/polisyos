"""Full-map reconciliation negatives for independently allocated locale parsers."""

from __future__ import annotations

import copy
import importlib
from pathlib import Path
from types import ModuleType

import pytest


def _gate() -> ModuleType:
    name = "tools.quality.validation.check_multilingual_locale_census"
    assert importlib.util.find_spec(name) is not None, "independent reconciliation gate is absent"
    return importlib.import_module(name)


@pytest.mark.parametrize("mutation", ["text", "path", "member", "nonstring", "empty"])
def test_same_counts_cannot_hide_a_corrupt_decisive_field(mutation: str) -> None:
    gate = _gate()
    left = {"en.json": {("x",): "X"}, "uk.json": {("x",): "\u0425"}}
    right = copy.deepcopy(left)
    if mutation == "text":
        right["uk.json"][("x",)] = "X"
    elif mutation == "path":
        right["uk.json"][("y",)] = right["uk.json"].pop(("x",))
    elif mutation == "member":
        right["xx.json"] = right.pop("uk.json")
    elif mutation == "nonstring":
        right["uk.json"][("x",)] = None
    else:
        right = {}
    with pytest.raises(ValueError, match=r"ambiguous|disagreement"):
        gate.reconcile_catalogues(left, right)


def test_exact_complete_maps_reconcile() -> None:
    gate = _gate()
    value = {"en.json": {("a", "b"): "text"}, "uk.json": {("a.b",): "текст"}}
    gate.reconcile_catalogues(value, copy.deepcopy(value))


def test_current_census_is_recomputed_with_semantic_claim_refused() -> None:
    gate = _gate()
    root = Path(__file__).resolve().parents[3]
    directory = root / "apps/runtime-dashboard/src/shared/i18n/locales"
    result = gate.measure_catalogues(directory)
    assert result["status"] == "independently_reconciled"
    assert result["file_denominator"] == len(list(directory.iterdir()))
    assert result["semantic_equivalence_established"] is False
    assert result["catalogues"]["en.json"]["string_leaves"] > 0
    assert result == gate.measure_catalogues(directory)


@pytest.mark.parametrize("parser", ["a", "b"])
def test_corrupting_one_actual_parser_result_fails_independent_comparison(parser: str) -> None:
    gate = _gate()
    root = Path(__file__).resolve().parents[3]
    directory = root / "apps/runtime-dashboard/src/shared/i18n/locales"
    with pytest.raises(ValueError, match="disagreement"):
        gate.measure_catalogues(directory, corrupt_parser=parser)
def test_measured_directory_is_the_emitted_source_denominator(tmp_path):
    """An alternate input must never receive the default catalogue's identity."""
    from tools.quality.validation import check_multilingual_locale_census as gate

    alternate = tmp_path / "alternate"
    alternate.mkdir()
    (alternate / "en.json").write_text('{"fixture": "candidate"}')
    result = gate.measure_catalogues(alternate)
    assert result["path_denominator"] == f"{alternate.resolve()}/*"
