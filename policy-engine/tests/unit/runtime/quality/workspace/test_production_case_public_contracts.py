"""Proposed native owner tests; copied to the mirrored test path at release."""

from __future__ import annotations

import copy
import json

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

import polisyos.pdc as pdc
from polisyos.runtime.quality.workspace import loop
from tests.unit.runtime.quality.workspace import (
    test_production_case_admission as admission_tests,
)
from tests.unit.runtime.quality.workspace import (
    test_production_case_proof_custody as proof_tests,
)
from tools.quality.validation import check_layer3_gy_loop_artifacts as owner

_actual_entry = admission_tests._actual_entry
production_input = admission_tests.production_input
REPO_ROOT = proof_tests.REPO_ROOT
actual_j_catalog = proof_tests.actual_j_catalog
actual_j_family_pair = proof_tests.actual_j_family_pair
gy_l_complete_live_population = proof_tests.gy_l_complete_live_population


@pytest.mark.parametrize("ordinary_owner", ["SearchLedger", "WorkspaceSearchLedger"])
@pytest.mark.parametrize("transport", ["typed", "json"])
def test_actual_production_refusal_is_not_an_ordinary_ledger(
    production_input, ordinary_owner, transport
):
    source, _, ref = production_input
    result = _actual_entry(source, ref)
    ordinary = getattr(pdc if ordinary_owner == "SearchLedger" else loop, ordinary_owner)
    value = result.search_ledger
    if transport == "json":
        value = value.model_dump(mode="json")
    # This is intentionally before checking new peer type names: the old
    # actual nullable subclass is admitted here despite its forbidden value.
    with pytest.raises(ValidationError):
        ordinary.model_validate(value)
    assert result.search_ledger.counterexample_conversion_rate is None


def test_actual_refusal_schema_and_complete_result_round_trip(production_input):
    source, _, ref = production_input
    result = _actual_entry(source, ref)
    raw = result.model_dump(mode="json")
    assert isinstance(result.workspace_contract, pdc.RefusedWorkspaceContract)
    assert isinstance(result.search_ledger, loop.RefusedWorkspaceSearchLedger)
    assert not isinstance(result.search_ledger, pdc.SearchLedger)
    assert not isinstance(result.workspace_contract, pdc.WorkspaceContract)
    schema = loop.WorkspaceSearchExitContract.model_json_schema(mode="validation")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(raw)
    restored = loop.WorkspaceSearchExitContract.model_validate_json(json.dumps(raw))
    assert restored.model_dump(mode="json") == raw
    assert type(restored.search_ledger) is type(result.search_ledger)
    assert type(restored.workspace_contract) is type(result.workspace_contract)
    assert "RefusedWorkspaceContract" in pdc.__all__
    assert "RefusedWorkspaceSearchLedger" in loop.__all__
    assert loop.workspace_exit_schema_version(restored) == "2.0"


@pytest.mark.parametrize(
    "field",
    [
        "counterexample_conversion_rate",
        "schema_version",
        "source_admission_ref",
        "population_state",
    ],
)
def test_refused_ledger_does_not_default_missing_semantic_fields(production_input, field):
    source, _, ref = production_input
    raw = _actual_entry(source, ref).search_ledger.model_dump(mode="json")
    raw.pop(field)
    with pytest.raises(ValidationError):
        loop.RefusedWorkspaceSearchLedger.model_validate(raw)


@pytest.mark.parametrize("value", [0.0, 1.0, "unknown"])
def test_refused_ledger_schema_cannot_claim_a_numeric_rate(production_input, value):
    source, _, ref = production_input
    raw = _actual_entry(source, ref).search_ledger.model_dump(mode="json")
    raw["counterexample_conversion_rate"] = value
    with pytest.raises(ValidationError):
        loop.RefusedWorkspaceSearchLedger.model_validate(raw)
    schema = loop.RefusedWorkspaceSearchLedger.model_json_schema(mode="validation")
    assert list(Draft202012Validator(schema).iter_errors(raw))


def test_search_quality_schema_keeps_recall_required_and_numeric_contract_unchanged():
    quality_schema = pdc.SearchQualityRecord.model_json_schema(mode="validation")
    assert "recall_at_known_seeds" in quality_schema["required"]
    assert (
        pdc.SearchLedger.model_json_schema()["properties"]["counterexample_conversion_rate"]["type"]
        == "number"
    )
    assert (
        loop.WorkspaceSearchLedger.model_json_schema()["properties"][
            "counterexample_conversion_rate"
        ]["type"]
        == "number"
    )
    for value in (0.0, 1.0):
        measured = pdc.SearchQualityRecord(recall_at_known_seeds=value, freshness_ok=True)
        assert measured.recall_at_known_seeds == value
    with pytest.raises(ValidationError):
        pdc.SearchQualityRecord(freshness_ok=True)
    with pytest.raises(ValidationError):
        pdc.SearchQualityRecord(recall_at_known_seeds=None, freshness_ok=True)


def test_real_durable_output_emits_and_reads_the_governed_refusal_dialect(actual_j_family_pair):
    _, _, observation = actual_j_family_pair
    _, raw = observation._checked_snapshot()
    custody = observation._checked_custody()["recorded_production_evidence"]
    refs = [
        raw["proof"]["output_search_exit_contract_ref"],
        raw["artifacts_index"]["search_ledger_ref"],
    ]
    for ref in refs:
        manifest = json.loads(custody["records"][ref]["manifest_json"])
        assert manifest["schema"]["version"] == "2.0"
    typed = loop.WorkspaceSearchExitContract.model_validate(raw["search_exit_contract"])
    assert typed.search_ledger.source_admission_ref == custody["admission_ref"]


@pytest.mark.parametrize("role", ["search_exit_contract_ref", "search_ledger_ref"])
def test_recorded_refusal_rejects_old_schema_dialect_with_all_content_markers(
    actual_j_family_pair, actual_j_catalog, role
):
    old, _, _ = actual_j_family_pair
    family = old._frozen_final_output()
    outcome = family[owner.OUTCOME_RUN_PATH]
    ref = outcome[role] if role == "search_exit_contract_ref" else outcome["artifacts_index"][role]
    record = outcome["recorded_production_evidence"]["records"][ref]
    manifest = json.loads(record["manifest_json"])
    before = copy.deepcopy(manifest)
    manifest["schema"]["version"] = "1.0"
    record["manifest_json"] = json.dumps(manifest)
    assert {**manifest, "schema": before["schema"]} == before
    with pytest.raises(owner.LoopFamilyCustodyError, match="contract_identity_drift"):
        owner._j_family_semantics(payloads=family, repo_root=REPO_ROOT, catalog=actual_j_catalog)
