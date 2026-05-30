from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
from pydantic import ValidationError

from polisyos.corpus import (
    FixtureRotationError,
    HiddenFixtureAccessError,
    UniversalCorpusSplit,
    load_universal_corpus_fixture,
    load_universal_corpus_fixtures,
    load_universal_corpus_manifest,
    select_universal_corpus_fixtures,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_universal_corpus_manifest_loads_complete_fixture_pack() -> None:
    manifest = load_universal_corpus_manifest()
    fixtures = load_universal_corpus_fixtures()

    assert manifest.schema_version == "policyos.universal_corpus_manifest.v1"
    assert len(fixtures) >= 12
    assert len({fixture.domain for fixture in fixtures}) >= 6
    assert {
        authority
        for fixture in fixtures
        for authority in fixture.intent.authority_levels
    } >= {"research", "governed", "production"}

    for fixture in fixtures:
        assert fixture.input_intent_ref == fixture.intent.intent_id
        assert fixture.claim_evidence_annotations.claims
        assert fixture.expert_adjudication.case_label
        assert fixture.expected_facets.facets
        assert fixture.expected_obligation_graph.frontier
        assert fixture.expected_claim_families.families
        assert set(fixture.expected_requirement_specs.families) == {
            "data",
            "legal",
            "method",
            "participation",
            "scholar",
        }
        assert {
            binding.status for binding in fixture.expected_adapter_bindings.bindings
        } >= {"selected", "rejected", "blocked"}
        assert {state.authority_level for state in fixture.expected_closeout_states.states} == {
            "research",
            "governed",
            "production",
        }
        assert fixture.expected_projection_truthfulness.projections


def test_universal_corpus_splits_require_explicit_hidden_access() -> None:
    public_fixtures = select_universal_corpus_fixtures(split=UniversalCorpusSplit.PUBLIC)
    rotating_fixtures = select_universal_corpus_fixtures(split=UniversalCorpusSplit.ROTATING)

    with pytest.raises(HiddenFixtureAccessError, match="hidden fixtures require explicit opt-in"):
        select_universal_corpus_fixtures(split=UniversalCorpusSplit.HIDDEN)

    hidden_fixtures = select_universal_corpus_fixtures(
        split=UniversalCorpusSplit.HIDDEN,
        include_hidden=True,
    )

    assert public_fixtures
    assert hidden_fixtures
    assert rotating_fixtures
    assert {fixture.split for fixture in public_fixtures} == {UniversalCorpusSplit.PUBLIC}
    assert {fixture.split for fixture in hidden_fixtures} == {UniversalCorpusSplit.HIDDEN}
    assert {fixture.split for fixture in rotating_fixtures} == {UniversalCorpusSplit.ROTATING}


def test_rotating_fixture_reused_in_consecutive_rounds_requires_ack(tmp_path: Path) -> None:
    root = tmp_path / "universal-corpus"
    root.mkdir()
    payload = _minimal_manifest_payload()
    payload["fixtures"] = [
        {
            "case_id": "case-overlap",
            "path": "cases/case-overlap.json",
            "split": "rotating",
            "domain": "housing",
            "authority_levels": ["research", "governed", "production"],
            "rotation_group": "truthfulness",
        }
    ]
    payload["rotation_policy"]["active_round_id"] = "round-current"
    payload["rotation_policy"]["previous_round_id"] = "round-previous"
    payload["rotation_policy"]["rounds"] = [
        {
            "round_id": "round-previous",
            "started_at": "2026-04-24T00:00:00Z",
            "rotating_case_ids": ["case-overlap"],
        },
        {
            "round_id": "round-current",
            "started_at": "2026-05-24T00:00:00Z",
            "rotating_case_ids": ["case-overlap"],
        },
    ]
    (root / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(FixtureRotationError, match="rotating_fixture_consecutive_reuse"):
        load_universal_corpus_manifest(root)

    payload["rotation_policy"]["acknowledgements"] = [
        {
            "case_id": "case-overlap",
            "round_id": "round-current",
            "ack_ref": "docs/archive/reports/2026-05-24-w11d-rotation-ack.md#case-overlap",
            "reason": "Reviewer-approved carryover to preserve production authority slice.",
        }
    ]
    (root / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")

    manifest = load_universal_corpus_manifest(root)

    assert manifest.rotation_policy.consecutive_reuse_case_ids == ("case-overlap",)


def test_case_without_claim_decomposition_annotation_is_rejected(tmp_path: Path) -> None:
    fixture_path = tmp_path / "case.json"
    payload = _minimal_fixture_payload()
    del payload["claim_evidence_annotations"]
    fixture_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError, match="claim_evidence_annotations"):
        load_universal_corpus_fixture(fixture_path)


def _minimal_manifest_payload() -> dict[str, Any]:
    return {
        "schema_version": "policyos.universal_corpus_manifest.v1",
        "fixture_schema_version": "policyos.universal_corpus_fixture.v1",
        "generated_at": "2026-05-24T00:00:00Z",
        "source_plan_ref": (
            "docs/plans/active/"
            "POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md#W11.D"
        ),
        "fixtures": [],
        "rotation_policy": {
            "policy_id": "w11d-universal-corpus-rotation-v1",
            "active_round_id": "round-current",
            "previous_round_id": None,
            "min_rotation_days": 30,
            "no_consecutive_round_reuse": True,
            "rounds": [],
            "acknowledgements": [],
        },
    }


def _minimal_fixture_payload() -> dict[str, Any]:
    return {
        "schema_version": "policyos.universal_corpus_fixture.v1",
        "case_id": "case-minimal",
        "title": "Minimal fixture",
        "domain": "housing",
        "split": "public",
        "source_case_ref": "docs/research/universal-policy-design/outcome-corpus/case-minimal.md",
        "redacted_source_hash": "sha256:" + "a" * 64,
        "input_intent_ref": "intent-case-minimal",
        "intent": {
            "intent_id": "intent-case-minimal",
            "text": "Design a governed housing subsidy.",
            "jurisdiction": "UA",
            "policy_time": "2026",
            "authority_levels": ["research", "governed", "production"],
            "instrument_type": "subsidy",
            "target_population": "low-income renters",
        },
        "claim_evidence_annotations": {
            "annotation_ref": "annotation://case-minimal",
            "claims": [
                {
                    "claim_id": "claim-case-minimal-need",
                    "claim_family": "need",
                    "text_ref": "case-minimal.md#need",
                    "evidence_refs": ["source://housing-need"],
                    "admissibility_label": "admissible",
                    "contestability_status": "reviewed",
                }
            ],
            "obligations": [
                {
                    "obligation_id": "obl-case-minimal-data",
                    "generated_from_facets": ["facet:instrument_type"],
                    "required_evidence_family": "administrative_housing_registry",
                    "status": "mandatory",
                }
            ],
        },
        "expert_adjudication": {
            "case_label": "limitation_required",
            "claim_labels": [
                {
                    "claim_id": "claim-case-minimal-need",
                    "label": "limitation_required",
                    "dimension_id": "evidence_admissibility",
                    "status_should_have_been": "publish_with_limitation",
                }
            ],
            "reviewer_topology_ref": "reviewer-topology://w11d/minimal",
        },
        "expected_facets": {
            "facets": [
                {
                    "facet_name": "instrument_type",
                    "expected_value": "subsidy",
                    "concept_ref": "concept://housing/subsidy",
                }
            ]
        },
        "expected_obligation_graph": {
            "frontier": [
                {
                    "obligation_id": "obl-case-minimal-data",
                    "family": "data",
                    "priority": "mandatory",
                    "source_class": "governed_rule",
                    "claim_refs": ["claim-case-minimal-need"],
                }
            ]
        },
        "expected_claim_families": {
            "families": [
                {
                    "claim_id": "claim-case-minimal-need",
                    "claim_family": "need",
                    "expected_support_status": "limited",
                }
            ]
        },
        "expected_requirement_specs": {
            "families": {
                "data": [{"requirement_id": "data-case-minimal"}],
                "legal": [{"requirement_id": "legal-case-minimal"}],
                "method": [{"requirement_id": "method-case-minimal"}],
                "participation": [{"requirement_id": "participation-case-minimal"}],
                "scholar": [{"requirement_id": "scholar-case-minimal"}],
            }
        },
        "expected_adapter_bindings": {
            "bindings": [
                {
                    "binding_id": "binding-selected",
                    "adapter": "fabric",
                    "status": "selected",
                    "requirement_id": "data-case-minimal",
                    "reason_code": "source_contract_satisfies_requirement",
                },
                {
                    "binding_id": "binding-rejected",
                    "adapter": "lex",
                    "status": "rejected",
                    "requirement_id": "legal-case-minimal",
                    "reason_code": "out_of_scope_authority",
                },
                {
                    "binding_id": "binding-blocked",
                    "adapter": "foundry",
                    "status": "blocked",
                    "requirement_id": "method-case-minimal",
                    "reason_code": "method_identification_missing",
                },
            ]
        },
        "expected_closeout_states": {
            "states": [
                {
                    "authority_level": "research",
                    "state": "publishable",
                    "required_surface_refs": ["audit://case-minimal/research"],
                },
                {
                    "authority_level": "governed",
                    "state": "limited",
                    "required_surface_refs": ["audit://case-minimal/governed"],
                },
                {
                    "authority_level": "production",
                    "state": "blocked",
                    "required_surface_refs": ["audit://case-minimal/production"],
                },
            ]
        },
        "expected_projection_truthfulness": {
            "projections": [
                {
                    "audience": "public",
                    "truthfulness": "limitation_required",
                    "must_disclose_refs": ["limitation://case-minimal/data"],
                    "may_not_claim": ["production closeout"],
                }
            ]
        },
    }
