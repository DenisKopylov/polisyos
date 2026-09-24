"""Behavioral tests over all registered non-data ceiling dimensions."""

from __future__ import annotations

import copy
import importlib
import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

NOW = datetime(2026, 9, 10, tzinfo=UTC)


def ceiling_module():
    name = "polisyos.fabric.evidence.ceiling_relations"
    assert importlib.util.find_spec(name) is not None, "GY-AQ1 ceiling relation owner is missing"
    return importlib.import_module(name)


def vocabulary_payload():
    """Candidate definitions exercise algorithms; no institution is impersonated."""
    return {
        "version": "candidate-vocabulary:1",
        "exact_identities": {
            "claim_kind": ["claim:conditional"],
            "action_ref": ["action:inspect"],
            "subject_ref": ["subject:1@1"],
            "object_ref": ["object:1@1"],
            "operation": ["inspect"],
            "permitted_operations": ["inspect"],
            "prohibited_uses": ["public-approval"],
            "use": ["candidate-analysis"],
            "rule_version_ref": ["rule:1"],
            "reference_epoch_ref": ["epoch:1"],
            "downstream_gate_refs": ["gate:owner-reentry"],
        },
        "population_members": {
            "population:all@1": ["person:a", "person:b"],
            "population:a@1": ["person:a"],
        },
        "jurisdiction_order": {
            "action_refs": ["action:inspect"],
            "nodes": ["jurisdiction:whole", "jurisdiction:part"],
            "edges": [["jurisdiction:part", "jurisdiction:whole"]],
        },
        "purpose_order": {
            "nodes": ["purpose:research", "purpose:bounded-research"],
            "edges": [["purpose:bounded-research", "purpose:research"]],
        },
        "audience_order": {
            "nodes": ["audience:team", "audience:reviewer"],
            "edges": [["audience:reviewer", "audience:team"]],
        },
        "transport": [
            {
                "source": "context:source",
                "target": "context:target",
                "valid_from": "2026-09-01T00:00:00Z",
                "valid_until": "2026-10-01T00:00:00Z",
            }
        ],
        "evidence_claims": {"evidence:simulation": ["claim:conditional"]},
        "assumptions": {
            "assumption:stable@1": {
                "valid_from": "2026-09-01T00:00:00Z",
                "valid_until": "2026-10-01T00:00:00Z",
            }
        },
        "strength_order": {
            "nodes": ["strength:assumption", "strength:conditional"],
            "edges": [["strength:assumption", "strength:conditional"]],
        },
        "stage_order": {
            "nodes": ["stage:design", "stage:pilot"],
            "edges": [["stage:design", "stage:pilot"]],
        },
    }


def scope_payload():
    return {
        "claim_kind": "claim:conditional",
        "action_ref": "action:inspect",
        "subject_ref": "subject:1@1",
        "object_ref": "object:1@1",
        "valid_from": "2026-09-01T00:00:00Z",
        "valid_until": "2026-10-01T00:00:00Z",
        "review_at": "2026-09-30T00:00:00Z",
        "operation": "inspect",
        "permitted_operations": ["inspect"],
        "prohibited_uses": [],
        "use": "candidate-analysis",
        "population_ref": "population:a@1",
        "jurisdiction_ref": "jurisdiction:part",
        "purpose_ref": "purpose:bounded-research",
        "audience_ref": "audience:reviewer",
        "source_context_ref": "context:source",
        "target_context_ref": "context:target",
        "evidence_class_ref": "evidence:simulation",
        "assumption_refs": ["assumption:stable@1"],
        "claim_strength_ref": "strength:assumption",
        "commitment_stage_ref": "stage:design",
        "load": 1,
        "rule_version_ref": "rule:1",
        "reference_epoch_ref": "epoch:1",
        "downstream_gate_refs": ["gate:owner-reentry"],
    }


def ceiling_payload():
    payload = scope_payload()
    payload.update(
        population_ref="population:all@1",
        jurisdiction_ref="jurisdiction:whole",
        purpose_ref="purpose:research",
        audience_ref="audience:team",
        claim_strength_ref="strength:conditional",
        commitment_stage_ref="stage:pilot",
        load=10,
    )
    return payload


def evaluate(vocabulary=None, requested=None, ceiling=None):
    module = ceiling_module()
    return module.evaluate_ceiling(
        vocabulary=module.CeilingVocabulary.model_validate(vocabulary or vocabulary_payload()),
        requested=module.CeilingScope.model_validate(requested or scope_payload()),
        ceiling=module.CeilingScope.model_validate(ceiling or ceiling_payload()),
        at=NOW,
    )


def test_all_eight_registered_relations_have_positive_result():
    result = evaluate()
    assert result.permitted
    assert set(result.relations) == {item.value for item in ceiling_module().CeilingDimension}
    assert all(result.relations.values())


@pytest.mark.parametrize(
    ("dimension", "field", "value"),
    [
        ("population", "population_ref", "population:unknown"),
        ("jurisdiction", "jurisdiction_ref", "jurisdiction:sibling"),
        ("purpose_audience", "purpose_ref", "purpose:sibling"),
        ("source_target_context", "target_context_ref", "context:unproved"),
        ("evidence_class", "evidence_class_ref", "evidence:unregistered"),
        ("maintained_assumptions", "assumption_refs", ["assumption:changed@2"]),
        ("maximum_claim_strength", "claim_strength_ref", "strength:unknown"),
        ("maximum_commitment_stage", "load", 11),
    ],
)
def test_each_relation_sibling_falsifier(dimension, field, value):
    request = scope_payload()
    request[field] = value
    result = evaluate(requested=request)
    assert not result.permitted
    assert result.relations[dimension] is False


def test_unknown_ceiling_field_is_not_defaulted():
    module = ceiling_module()
    payload = ceiling_payload()
    payload["new_authority_dimension"] = "unproved"
    with pytest.raises(ValueError, match="extra_forbidden"):
        module.CeilingScope.model_validate(payload)


def test_complete_vocabulary_free_grows_by_data_and_malformed_sibling_refuses():
    vocabulary = vocabulary_payload()
    vocabulary["population_members"]["population:novel@1"] = ["person:a"]
    vocabulary["strength_order"]["nodes"].append("strength:novel-bounded")
    vocabulary["strength_order"]["edges"].append(["strength:novel-bounded", "strength:conditional"])
    request = scope_payload()
    request.update(population_ref="population:novel@1", claim_strength_ref="strength:novel-bounded")
    assert evaluate(vocabulary=vocabulary, requested=request).permitted
    malformed = copy.deepcopy(vocabulary)
    malformed["strength_order"]["edges"].append(["strength:conditional", "strength:novel-bounded"])
    with pytest.raises(ValueError, match="cycle"):
        evaluate(vocabulary=malformed, requested=request)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("object_ref", "object:1@2"),
        ("rule_version_ref", "rule:2"),
        ("reference_epoch_ref", "epoch:2"),
        ("operation", "mutate"),
        ("valid_until", "2026-11-01T00:00:00Z"),
    ],
)
def test_exact_and_time_controls_are_enforced(field, value):
    requested = scope_payload()
    requested[field] = value
    assert not evaluate(requested=requested).permitted


def test_jurisdiction_subordination_is_bound_to_the_demonstrated_act():
    request, ceiling = scope_payload(), ceiling_payload()
    request["action_ref"] = ceiling["action_ref"] = "action:new-competence"
    assert not evaluate(requested=request, ceiling=ceiling).permitted


@pytest.mark.parametrize(
    "field",
    [
        "subject_ref",
        "object_ref",
        "rule_version_ref",
        "reference_epoch_ref",
        "use",
        "downstream_gate_refs",
    ],
)
def test_same_unknown_exact_identity_on_both_sides_still_refuses(field):
    request, ceiling = scope_payload(), ceiling_payload()
    unknown = (
        ["unregistered:identity"] if field == "downstream_gate_refs" else "unregistered:identity"
    )
    request[field] = ceiling[field] = unknown
    assert not evaluate(requested=request, ceiling=ceiling).permitted


def test_real_registered_relation_denominator_matches_research_matrix_two_ways():
    module = ceiling_module()
    root = Path(__file__).resolve().parents[3]
    register = json.loads(
        (root / "src/polisyos/fabric/evidence/ceiling_vocabulary.json").read_text()
    )
    observed = set(register["relations"])
    assert observed == {member.value for member in module.CeilingDimension}
    source = (root / "docs/research/policy-operations/int-r2/amendment-ledger.md").read_text()
    matrix = source.split("### 4.2 Field-level")[1].split("### 4.3")[0]
    deferred = [
        line for line in matrix.splitlines() if "checkable_after_registered_mapping" in line
    ]
    assert len(observed) == len(deferred) == 8
    assert (
        sum(1 for value in register["relations"].values() if value["owner"] == module.__name__) == 8
    )
