from __future__ import annotations

# ruff: noqa: S101
import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from polisyos.runtime.quality.assurance_case import (
    PolicyDesignCaseAuthorityError,
    build_policy_design_case_concept_spine,
    build_policy_design_case_profile,
    build_policy_intent_envelope,
    policy_design_concept_spine_json_schema,
    validate_policy_design_case_concept_spine,
    validate_policy_design_case_profile,
)
from polisyos.runtime.quality.concept_spine import (
    build_policy_design_concept_spine_boundary_record,
)
from tests._helpers.hds_quality import blocking_codes, complete_quality_evidence, scorecard_for

if TYPE_CHECKING:
    from collections.abc import Callable


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _runtime_authority() -> dict[str, object]:
    return {
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "cas_ref": _sha("1"),
        "runtime_event_ref": "event://policy_design_case/concept_spine/case",
        "same_input_closure_ref": _sha("3"),
        "effective_mode_ref": _sha("e"),
        "schema_compatibility_ref": _sha("c"),
    }


def _capability_duty(capability: str) -> dict[str, object]:
    return {
        "capability": capability,
        "state": "selected",
        "owner": f"team-{capability}",
        "evidence_ref": _sha(capability[0]),
        "runtime_event_ref": f"event://policy_design_case/capability/{capability}",
        "required": True,
    }


def _capability_ledger() -> dict[str, object]:
    return {
        "schema_version": "policyos.runtime.policy_design_case.capability_ledger.v1",
        "ledger_ref": _sha("5"),
        "literature_evidence_required": True,
        "duties": [
            _capability_duty(capability)
            for capability in (
                "lex",
                "fabric",
                "scholar",
                "foundry",
                "scientist",
                "compiler",
                "review",
                "publication",
                "audit",
            )
        ],
    }


def _intent_envelope() -> dict[str, object]:
    return build_policy_intent_envelope(
        intent_id="intent-run-8-1",
        run_id="run-8-1",
        job_id="job-8-1",
        tenant_id="tenant-1",
        policy_problem="Wartime MSME credit access is constrained.",
        desired_outcome="Improve MSME survival.",
        proposed_intervention="Target wartime credit support to eligible MSMEs.",
        jurisdiction="UA",
        target_population="wartime MSMEs",
        policy_time="2026-05-15",
        data_time="2024-2026",
        requester_preferred_conclusion="expand credit support",
        requested_authority_level="production",
        objectives=["maximize MSME survival"],
        authoring_provenance={"captured_by": "test", "capture_ref": _sha("4")},
    )


def _fabric_entity_resolution() -> dict[str, object]:
    return {
        "schema_version": "fabric.entity_resolution.batch.v1",
        "batch_ref": "cas://sha256/" + "a" * 64,
        "records": [
            {
                "entity_id": "fabric:metric:msme_survival",
                "canonical_name": "MSME survival rate",
                "source": "fabric",
                "aliases": ["SME survival", "firm survival"],
                "attributes": {
                    "canonical_concept_id": "concept.msme_survival_rate",
                    "source_terms": "MSME survival rate, SME survival",
                    "metric_id": "msme_survival_rate",
                    "dataset_id": "ua_msme_panel",
                    "column_id": "survival_status",
                    "geography": "UA",
                    "population": "wartime MSMEs",
                    "time": "2024-2026",
                    "unit_id": "percent",
                    "currency": "UAH",
                    "price_base": "not_applicable",
                    "exchange_rate_ref": "not_applicable",
                    "inflation_adjustment_ref": "not_applicable",
                    "calendar": "gregorian",
                    "freshness_ref": "freshness.ua_msme_panel.2026-05-17",
                },
                "provenance_ref": "cas://sha256/" + "b" * 64,
            }
        ],
        "accepted_matches": [
            {
                "match_id": "entity_match_msme_survival",
                "left_entity_id": "fabric:metric:msme_survival",
                "right_entity_id": "registry:concept.msme_survival_rate",
                "confidence": 0.97,
                "override_status": "accepted",
            }
        ],
        "rejected_candidates": [
            {
                "match_id": "entity_match_msme_survival_alt",
                "left_entity_id": "fabric:metric:msme_survival",
                "right_entity_id": "registry:concept.credit_volume",
                "confidence": 0.41,
                "override_status": "rejected",
            }
        ],
    }


def _scientist_cross_graph() -> dict[str, object]:
    return {
        "schema_version": "2.1",
        "ontology_snapshot": [
            {
                "concept_id": "concept.msme_survival_rate",
                "concept_kind": "metric",
                "label": "MSME survival rate",
                "join_keys": {"metric_id": ["msme_survival_rate"]},
                "metadata": {
                    "aliases": ["SME survival", "firm survival"],
                    "legal_concept_ids": ["ua.credit_support.eligibility"],
                    "population": "wartime MSMEs",
                },
            }
        ],
        "needs": [
            {
                "need": {
                    "need_id": "need-msme-survival",
                    "need_type": "objective_metric",
                    "source_path": "problem_frame.objectives[0]",
                    "metric_id": "msme_survival_rate",
                    "geography": "UA",
                    "time_window": "2024-2026",
                    "labels": ["MSME survival"],
                },
                "resolved_concept_ids": ["concept.msme_survival_rate"],
                "legal_status": "allowed",
                "observability_status": "direct",
                "transport_status": "identified",
                "provenance_refs": ["cas://sha256/" + "d" * 64],
            }
        ],
        "bridges": [
            {
                "src_system": "scholar",
                "src_kind": "claim",
                "src_id": "claim.msme_survival_evidence",
                "dst_concept_id": "concept.msme_survival_rate",
                "relation": "claim_to_variable",
                "confidence": 0.86,
                "numerical_semantics": {
                    "unit_id": "percent",
                    "currency": "UAH",
                    "price_base": "not_applicable",
                    "exchange_rate_ref": "not_applicable",
                    "inflation_adjustment_ref": "not_applicable",
                    "geography": "UA",
                    "geography_level": "national",
                    "time": "2024-2026",
                    "time_basis": "calendar_year",
                    "calendar": "gregorian",
                    "freshness_ref": "freshness.ua_msme_panel.2026-05-17",
                },
                "provenance": ["cas://sha256/" + "e" * 64],
            }
        ],
    }


def _ir_linker() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "ok": True,
        "issues": [],
        "linked_metrics": [
            {
                "metric_id": "msme_survival_rate",
                "canonical_concept_id": "concept.msme_survival_rate",
                "unit_id": "percent",
                "objective_id": "objective.msme_survival",
                "tradeoff_id": "tradeoff.fiscal_cost",
                "method_requirement_id": "method.did.minimum_panel",
            }
        ],
    }


def _ir_registry() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "concepts": {
            "concept.msme_survival_rate": {
                "concept_id": "concept.msme_survival_rate",
                "name": "MSME survival rate",
                "notes": ["alias:SME survival", "source_term:firm survival"],
            }
        },
        "metrics": {
            "msme_survival_rate": {
                "metric_id": "msme_survival_rate",
                "unit_id": "percent",
                "description": "Share of MSMEs surviving through the target window.",
            }
        },
        "units": {
            "percent": {"kind": "rate", "base": "percent"},
            "uah": {"kind": "money", "currency": "UAH", "nominal_year": 2024},
        },
        "geo": {"areas": {"UA": {"geo_id": "UA", "name": "Ukraine"}}},
        "time": {
            "axes": {
                "calendar_year": {
                    "axis_id": "calendar_year",
                    "description": "Gregorian calendar year",
                }
            }
        },
    }


def _ir_world() -> dict[str, object]:
    return {
        "schema_version": "ir.world.concept_projection.v1",
        "world_refs": [
            {
                "world_id": "concept.sha256_" + "f" * 64,
                "canonical_concept_id": "concept.msme_survival_rate",
                "kind": "world.node",
                "provenance_ref": "cas://sha256/" + "f" * 64,
            }
        ],
        "dataset_bindings": [
            {
                "dataset_id": "ua_msme_panel",
                "columns": ["firm_id", "survival_status"],
                "metric_id": "msme_survival_rate",
                "canonical_concept_id": "concept.msme_survival_rate",
            }
        ],
        "legal_concept_bindings": [
            {
                "legal_concept_id": "ua.credit_support.eligibility",
                "canonical_concept_id": "concept.msme_survival_rate",
            }
        ],
        "method_requirement_bindings": [
            {
                "requirement_id": "method.did.minimum_panel",
                "canonical_concept_id": "concept.msme_survival_rate",
            }
        ],
        "objective_tradeoff_bindings": [
            {
                "objective_id": "objective.msme_survival",
                "tradeoff_id": "tradeoff.fiscal_cost",
                "canonical_concept_id": "concept.msme_survival_rate",
            }
        ],
        "geography": ["UA"],
        "population": ["wartime MSMEs"],
        "time": ["2024-2026"],
        "units": ["percent"],
        "currency": ["UAH"],
        "price_bases": ["not_applicable"],
        "exchange_rates": ["not_applicable"],
        "inflation_adjustments": ["not_applicable"],
        "calendars": ["gregorian"],
        "freshness": ["freshness.ua_msme_panel.2026-05-17"],
    }


def test_concept_spine_projects_runtime_concepts_over_fabric_scientist_ir_and_world() -> None:
    spine = build_policy_design_case_concept_spine(
        run_id="run-8-1",
        job_id="job-8-1",
        tenant_id="tenant-1",
        policy_intent_ref=_sha("4"),
        raw_user_terms=["MSME survival", "firm survival"],
        fabric_entity_resolution=_fabric_entity_resolution(),
        scientist_cross_graph=_scientist_cross_graph(),
        ir_linker=_ir_linker(),
        ir_registry=_ir_registry(),
        ir_world=_ir_world(),
        generated_at=datetime(2026, 5, 17, 9, 30, tzinfo=UTC),
    )

    validated_spine = validate_policy_design_case_concept_spine(spine)

    assert validated_spine["schema_version"] == (
        "policyos.runtime.policy_design_case.concept_spine.v1"
    )
    assert validated_spine["node_type"] == "concept_spine"
    assert validated_spine["status"] == "pass"
    assert validated_spine["blockers"] == []
    assert validated_spine["source_projection"]["components"] == [
        "fabric_entity_resolution",
        "scientist_cross_graph",
        "ir_linker",
        "ir_registry",
        "ir_world",
    ]
    assert validated_spine["canonical_concept_ids"] == ["concept.msme_survival_rate"]
    concept = validated_spine["canonical_concepts"][0]
    assert concept["canonical_concept_id"] == "concept.msme_survival_rate"
    assert {"SME survival", "firm survival"} <= set(concept["aliases"])
    assert {"MSME survival rate", "SME survival"} <= set(concept["source_terms"])
    assert concept["metric_bindings"] == [
        {
            "metric_id": "msme_survival_rate",
            "unit_id": "percent",
            "source_component": "ir_linker",
        }
    ]
    assert concept["dataset_column_bindings"] == [
        {
            "dataset_id": "ua_msme_panel",
            "column_ids": ["firm_id", "survival_status"],
            "metric_id": "msme_survival_rate",
            "source_component": "ir_world",
        }
    ]
    assert concept["legal_concept_bindings"] == [
        {
            "legal_concept_id": "ua.credit_support.eligibility",
            "source_component": "ir_world",
        }
    ]
    assert concept["method_requirement_bindings"] == [
        {
            "requirement_id": "method.did.minimum_panel",
            "source_component": "ir_world",
        }
    ]
    assert concept["objective_tradeoff_bindings"] == [
        {
            "objective_id": "objective.msme_survival",
            "tradeoff_id": "tradeoff.fiscal_cost",
            "source_component": "ir_world",
        }
    ]
    assert concept["geography"] == ["UA"]
    assert concept["population"] == ["wartime MSMEs"]
    assert concept["time"] == ["2024-2026"]
    assert concept["units"] == ["percent"]
    assert concept["currency"] == ["UAH"]
    assert concept["price_bases"] == ["not_applicable"]
    assert concept["exchange_rates"] == ["not_applicable"]
    assert concept["inflation_adjustments"] == ["not_applicable"]
    assert concept["calendars"] == ["gregorian"]
    assert concept["freshness"] == ["freshness.ua_msme_panel.2026-05-17"]
    assert len(concept["claim_numerical_semantics_refs"]) == 1
    claim_semantics = concept["claim_numerical_semantics_refs"][0]
    assert claim_semantics == {
        "claim_id": "claim.msme_survival_evidence",
        "canonical_concept_id": "concept.msme_survival_rate",
        "semantic_ref": claim_semantics["semantic_ref"],
        "unit_id": "percent",
        "currency": "UAH",
        "price_base": "not_applicable",
        "exchange_rate_ref": "not_applicable",
        "inflation_adjustment_ref": "not_applicable",
        "geography": "UA",
        "geography_level": "national",
        "time": "2024-2026",
        "time_basis": "calendar_year",
        "calendar": "gregorian",
        "freshness_ref": "freshness.ua_msme_panel.2026-05-17",
        "source_component": "scientist_cross_graph",
    }
    assert concept["world_refs"] == ["concept.sha256_" + "f" * 64]
    assert validated_spine["claim_numerical_semantics_refs"] == [
        {"canonical_concept_id": "concept.msme_survival_rate", **claim_semantics}
    ]
    assert {entry["concept_type"] for entry in validated_spine["reconciliation_trace"]} == {
        "metric",
        "dataset",
        "legal",
        "method",
        "objective",
        "claim",
    }
    assert all(
        entry["status"] == "resolved"
        for entry in validated_spine["reconciliation_trace"]
    )
    claim_entry = next(
        entry
        for entry in validated_spine["reconciliation_trace"]
        if entry["concept_type"] == "claim"
    )
    assert claim_entry["binding_refs"] == ["claim.msme_survival_evidence"]
    normalization_by_term = {
        entry["raw_term"]: entry for entry in validated_spine["normalization_trace"]
    }
    assert normalization_by_term["MSME survival"]["canonical_concept_refs"] == [
        "concept.msme_survival_rate"
    ]
    assert normalization_by_term["MSME survival"]["typed_blocker"] is None
    assert normalization_by_term["firm survival"]["canonical_concept_refs"] == [
        "concept.msme_survival_rate"
    ]

    case = build_policy_design_case_profile(
        case_id="pdc-run-8-1",
        run_id="run-8-1",
        job_id="job-8-1",
        tenant_id="tenant-1",
        effective_execution_profile="production",
        runtime_authority=_runtime_authority(),
        intent_envelope=_intent_envelope(),
        capability_ledger=_capability_ledger(),
        nodes=[validated_spine],
        generated_at=datetime(2026, 5, 17, 9, 30, tzinfo=UTC),
    )

    validated_case = validate_policy_design_case_profile(case)
    assert validated_case["nodes"] == [validated_spine]


def test_concept_spine_blocks_synonym_collision_with_normalization_trace() -> None:
    fabric = _fabric_entity_resolution()
    fabric["records"].append(
        {
            "entity_id": "fabric:metric:credit_volume",
            "canonical_name": "Credit volume",
            "aliases": ["SME survival"],
            "attributes": {
                "canonical_concept_id": "concept.credit_volume",
                "source_terms": "credit volume, SME survival",
                "geography": "UA",
                "population": "wartime MSMEs",
                "time": "2024-2026",
                "unit_id": "percent",
                "currency": "UAH",
                "calendar": "gregorian",
            },
            "provenance_ref": "cas://sha256/" + "9" * 64,
        }
    )
    scientist = _scientist_cross_graph()
    scientist["ontology_snapshot"].append(
        {
            "concept_id": "concept.credit_volume",
            "concept_kind": "metric",
            "label": "Credit volume",
            "metadata": {
                "aliases": ["SME survival"],
                "population": "wartime MSMEs",
            },
        }
    )
    linker = _ir_linker()
    linker["linked_metrics"].append(
        {
            "metric_id": "credit_volume_rate",
            "canonical_concept_id": "concept.credit_volume",
            "unit_id": "percent",
        }
    )
    registry = _ir_registry()
    registry["concepts"]["concept.credit_volume"] = {
        "concept_id": "concept.credit_volume",
        "name": "Credit volume",
        "notes": ["alias:SME survival", "source_term:credit volume"],
    }
    registry["metrics"]["credit_volume_rate"] = {
        "metric_id": "credit_volume_rate",
        "unit_id": "percent",
    }
    world = _ir_world()
    world["world_refs"].append(
        {
            "world_id": "concept.sha256_" + "9" * 64,
            "canonical_concept_id": "concept.credit_volume",
        }
    )
    world["dataset_bindings"].append(
        {
            "dataset_id": "ua_credit_panel",
            "columns": ["firm_id", "credit_volume"],
            "metric_id": "credit_volume_rate",
            "canonical_concept_id": "concept.credit_volume",
        }
    )
    world["legal_concept_bindings"].append(
        {
            "legal_concept_id": "ua.credit_volume.reporting",
            "canonical_concept_id": "concept.credit_volume",
        }
    )
    world["method_requirement_bindings"].append(
        {
            "requirement_id": "method.did.minimum_panel",
            "canonical_concept_id": "concept.credit_volume",
        }
    )
    world["objective_tradeoff_bindings"].append(
        {
            "objective_id": "objective.credit_volume",
            "tradeoff_id": "tradeoff.fiscal_cost",
            "canonical_concept_id": "concept.credit_volume",
        }
    )

    spine = build_policy_design_case_concept_spine(
        run_id="run-9-synonym",
        job_id="job-9-synonym",
        tenant_id="tenant-1",
        policy_intent_ref=_sha("4"),
        raw_user_terms=["SME survival"],
        fabric_entity_resolution=fabric,
        scientist_cross_graph=scientist,
        ir_linker=linker,
        ir_registry=registry,
        ir_world=world,
    )

    assert spine["status"] == "blocked"
    assert "policy_design_concept_synonym_collision" in {
        blocker["code"] for blocker in spine["blockers"]
    }
    collision = next(
        entry for entry in spine["normalization_trace"] if entry["raw_term"] == "SME survival"
    )
    assert collision["status"] == "blocked"
    assert collision["canonical_concept_refs"] == [
        "concept.credit_volume",
        "concept.msme_survival_rate",
    ]
    assert collision["typed_blocker"]["code"] == "policy_design_concept_synonym_collision"


@pytest.mark.parametrize(
    ("mutate_inputs", "blocker_code", "trace_dimension"),
    [
        (
            lambda _fabric, _scientist, _linker, _registry, world: world.update(
                {"units": ["index_points"]}
            ),
            "policy_design_concept_unit_mismatch",
            "units",
        ),
        (
            lambda _fabric, _scientist, _linker, _registry, world: world.update(
                {"geography": ["PL"]}
            ),
            "policy_design_concept_geography_mismatch",
            "geography",
        ),
        (
            lambda _fabric, _scientist, _linker, _registry, world: world.update(
                {"time": ["2019-2021"]}
            ),
            "policy_design_concept_time_mismatch",
            "time",
        ),
        (
            lambda _fabric, _scientist, _linker, _registry, world: world[
                "legal_concept_bindings"
            ].append(
                {
                    "legal_concept_id": "ua.tax.compliance.eligibility",
                    "canonical_concept_id": "concept.msme_survival_rate",
                }
            ),
            "policy_design_concept_legal_mismatch",
            "legal_concepts",
        ),
    ],
)
def test_concept_spine_blocks_reconciliation_mismatches(
    mutate_inputs: Callable[
        [
            dict[str, object],
            dict[str, object],
            dict[str, object],
            dict[str, object],
            dict[str, object],
        ],
        object,
    ],
    blocker_code: str,
    trace_dimension: str,
) -> None:
    fabric = _fabric_entity_resolution()
    scientist = _scientist_cross_graph()
    linker = _ir_linker()
    registry = _ir_registry()
    world = _ir_world()
    mutate_inputs(fabric, scientist, linker, registry, world)

    spine = build_policy_design_case_concept_spine(
        run_id=f"run-9-{trace_dimension}",
        job_id=f"job-9-{trace_dimension}",
        tenant_id="tenant-1",
        policy_intent_ref=_sha("4"),
        raw_user_terms=["MSME survival"],
        fabric_entity_resolution=fabric,
        scientist_cross_graph=scientist,
        ir_linker=linker,
        ir_registry=registry,
        ir_world=world,
    )

    assert spine["status"] == "blocked"
    assert blocker_code in {blocker["code"] for blocker in spine["blockers"]}
    assert any(
        mismatch["code"] == blocker_code
        for entry in spine["reconciliation_trace"]
        for mismatch in entry["mismatches"]
        if mismatch["dimension"] == trace_dimension
    )


@pytest.mark.parametrize(
    ("dimension", "override", "blocker_code"),
    [
        (
            "unit_id",
            {"unit_id": "basis_points"},
            "policy_design_claim_unit_mismatch",
        ),
        (
            "currency",
            {"currency": "USD"},
            "policy_design_claim_currency_mismatch",
        ),
        (
            "geography_level",
            {"geography_level": "regional"},
            "policy_design_claim_geography_level_mismatch",
        ),
        (
            "time_basis",
            {"time_basis": "fiscal_year"},
            "policy_design_claim_time_basis_mismatch",
        ),
        (
            "price_base",
            {"price_base": "constant_2024"},
            "policy_design_claim_price_base_mismatch",
        ),
        (
            "exchange_rate_ref",
            {"exchange_rate_ref": "nbu_usd_uah_2024"},
            "policy_design_claim_exchange_rate_mismatch",
        ),
        (
            "inflation_adjustment_ref",
            {"inflation_adjustment_ref": "cpi_ua_2024"},
            "policy_design_claim_inflation_adjustment_mismatch",
        ),
        (
            "calendar",
            {"calendar": "fiscal_ukraine"},
            "policy_design_claim_calendar_mismatch",
        ),
        (
            "freshness_ref",
            {"freshness_ref": "freshness.ua_msme_panel.2025-12-31"},
            "policy_design_claim_freshness_mismatch",
        ),
    ],
)
def test_concept_spine_blocks_claim_level_numerical_semantic_mismatches(
    dimension: str,
    override: dict[str, str],
    blocker_code: str,
) -> None:
    scientist = _scientist_cross_graph()
    base_semantics = {
        "unit_id": "percent",
        "currency": "UAH",
        "price_base": "not_applicable",
        "exchange_rate_ref": "not_applicable",
        "inflation_adjustment_ref": "not_applicable",
        "geography": "UA",
        "geography_level": "national",
        "time": "2024-2026",
        "time_basis": "calendar_year",
        "calendar": "gregorian",
        "freshness_ref": "freshness.ua_msme_panel.2026-05-17",
    }
    scientist["bridges"] = [
        {
            "src_system": "scholar",
            "src_kind": "claim",
            "src_id": "claim.mixed_numeric_semantics",
            "dst_concept_id": "concept.msme_survival_rate",
            "relation": "claim_to_variable",
            "confidence": 0.86,
            "numerical_semantics": base_semantics,
            "provenance": ["cas://sha256/" + "e" * 64],
        },
        {
            "src_system": "fabric",
            "src_kind": "claim",
            "src_id": "claim.mixed_numeric_semantics",
            "dst_concept_id": "concept.msme_survival_rate",
            "relation": "claim_to_variable",
            "confidence": 0.84,
            "numerical_semantics": {**base_semantics, **override},
            "provenance": ["cas://sha256/" + dimension[0] * 64],
        },
    ]

    spine = build_policy_design_case_concept_spine(
        run_id=f"run-10-1-{dimension}",
        job_id=f"job-10-1-{dimension}",
        tenant_id="tenant-1",
        policy_intent_ref=_sha("4"),
        raw_user_terms=["MSME survival"],
        fabric_entity_resolution=_fabric_entity_resolution(),
        scientist_cross_graph=scientist,
        ir_linker=_ir_linker(),
        ir_registry=_ir_registry(),
        ir_world=_ir_world(),
    )

    assert spine["status"] == "blocked"
    assert len(spine["claim_numerical_semantics_refs"]) == 2
    assert blocker_code in {blocker["code"] for blocker in spine["blockers"]}
    assert any(
        mismatch["code"] == blocker_code
        for entry in spine["reconciliation_trace"]
        for mismatch in entry["mismatches"]
        if mismatch["dimension"] == dimension
    )


def test_concept_spine_emits_blockers_for_unresolved_and_conflicting_concepts() -> None:
    fabric = _fabric_entity_resolution()
    fabric["unresolved"] = [
        {
            "source_term": "informal credit access",
            "source_component": "fabric_entity_resolution",
            "reason": "no accepted canonical match",
        }
    ]
    fabric["conflicts"] = [
        {
            "source_term": "credit support",
            "candidate_concept_ids": [
                "concept.credit_access",
                "concept.loan_volume",
            ],
            "source_component": "fabric_entity_resolution",
            "reason": "alias collision",
        }
    ]
    scientist = _scientist_cross_graph()
    scientist["needs"] = [
        {
            "need": {
                "need_id": "need-credit-access",
                "need_type": "objective_metric",
                "metric_id": "informal_credit_access",
                "labels": ["informal credit access"],
            },
            "resolved_concept_ids": [],
            "diagnostics": [
                {
                    "code": "unknown_concept",
                    "severity": "error",
                    "need_id": "need-credit-access",
                    "message": "No canonical concept found.",
                }
            ],
        }
    ]
    linker = _ir_linker()
    linker["ok"] = False
    linker["issues"] = [
        {
            "code": "unknown_concept",
            "severity": "error",
            "message": "Metric informal_credit_access is not registered.",
            "path": ["problem_frame", "objectives", 1],
            "ids": {"metric_id": "informal_credit_access"},
        }
    ]

    spine = build_policy_design_case_concept_spine(
        run_id="run-8-1",
        job_id="job-8-1",
        tenant_id="tenant-1",
        policy_intent_ref=_sha("4"),
        fabric_entity_resolution=fabric,
        scientist_cross_graph=scientist,
        ir_linker=linker,
        ir_registry=_ir_registry(),
        ir_world=_ir_world(),
    )

    assert spine["status"] == "blocked"
    blocker_codes = {blocker["code"] for blocker in spine["blockers"]}
    assert blocker_codes == {
        "policy_design_concept_unresolved",
        "policy_design_concept_conflict",
    }
    assert all(blocker["owner"] == "team-policy-semantics" for blocker in spine["blockers"])
    assert all(
        blocker["next_diagnostic_command"].startswith("uv run ")
        for blocker in spine["blockers"]
    )

    boundary = build_policy_design_concept_spine_boundary_record(spine)
    assert boundary["status"] == "blocked"
    assert boundary["producer_owner"] == "team-policy-semantics"
    assert boundary["reader_owner"] == "team-runtime-quality"
    assert boundary["record_family"] == "concept_and_jurisdiction_spine.v1"
    assert boundary["runtime_authority_envelope"]["provenance_kind"] == "runtime_blocker"
    assert {blocker["code"] for blocker in boundary["blockers"]} == blocker_codes

    missing_blocker = deepcopy(spine)
    missing_blocker["status"] = "pass"
    missing_blocker["blockers"] = []

    hidden_boundary = build_policy_design_concept_spine_boundary_record(missing_blocker)
    assert hidden_boundary["status"] == "failed"
    assert {
        issue["code"] for issue in hidden_boundary["issues"]
    } == {"policy_design_concept_spine_blocker_missing"}

    with pytest.raises(
        PolicyDesignCaseAuthorityError,
        match="policy_design_concept_spine_blocker_missing",
    ):
        validate_policy_design_case_concept_spine(missing_blocker)

    with pytest.raises(
        PolicyDesignCaseAuthorityError,
        match="policy_design_concept_spine_blocker_missing",
    ):
        build_policy_design_case_profile(
            case_id="pdc-run-8-1-blocked",
            run_id="run-8-1",
            job_id="job-8-1",
            tenant_id="tenant-1",
            effective_execution_profile="production",
            runtime_authority=_runtime_authority(),
            intent_envelope=_intent_envelope(),
            capability_ledger=_capability_ledger(),
            nodes=[missing_blocker],
        )


def test_serious_scorecard_requires_concept_spine_or_typed_blocker() -> None:
    evidence = complete_quality_evidence()
    evidence["policy_design_case"].pop("concept_spine", None)
    evidence["policy_design_case"].pop("nodes", None)

    scorecard = scorecard_for(quality_evidence=evidence)

    assert "policy_design_concept_spine_missing" in blocking_codes(scorecard)


def test_concept_spine_blocks_incomplete_binding_and_semantic_closure() -> None:
    spine = build_policy_design_case_concept_spine(
        run_id="run-8-1-incomplete",
        job_id="job-8-1-incomplete",
        tenant_id="tenant-1",
        policy_intent_ref=_sha("4"),
        fabric_entity_resolution={
            "schema_version": "fabric.entity_resolution.batch.v1",
            "records": [],
        },
        scientist_cross_graph={"schema_version": "2.1", "ontology_snapshot": [], "needs": []},
        ir_linker={"schema_version": "1.0", "ok": True, "linked_metrics": [], "issues": []},
        ir_registry={
            "schema_version": "1.0",
            "concepts": {
                "concept.incomplete": {
                    "concept_id": "concept.incomplete",
                    "name": "Incomplete concept",
                }
            },
        },
        ir_world={"schema_version": "ir.world.concept_projection.v1", "world_refs": []},
    )

    assert spine["status"] == "blocked"
    assert {blocker["code"] for blocker in spine["blockers"]} == {
        "policy_design_concept_binding_missing"
    }
    missing = spine["blockers"][0]["missing_fields_by_concept"]["concept.incomplete"]
    assert {
        "aliases",
        "source_terms",
        "metric_bindings",
        "dataset_column_bindings",
        "legal_concept_bindings",
        "method_requirement_bindings",
        "objective_tradeoff_bindings",
        "geography",
        "population",
        "time",
        "units",
        "currency",
        "calendars",
    } <= set(missing)


def test_concept_spine_rejects_static_inventory_authority() -> None:
    spine = build_policy_design_case_concept_spine(
        run_id="run-8-1-static",
        job_id="job-8-1-static",
        tenant_id="tenant-1",
        policy_intent_ref=_sha("4"),
        fabric_entity_resolution=_fabric_entity_resolution(),
        scientist_cross_graph=_scientist_cross_graph(),
        ir_linker=_ir_linker(),
        ir_registry=_ir_registry(),
        ir_world=_ir_world(),
    )
    spine["runtime_authority_envelope"] = {
        **spine["runtime_authority_envelope"],
        "authority_role": "not_authoritative",
        "provenance_kind": "static_inventory",
        "static_inventory_ref": "repo://architecture/name_registry.toml#concept-spine",
    }

    with pytest.raises(
        PolicyDesignCaseAuthorityError,
        match="policy_design_concept_spine_static_inventory_not_authority",
    ):
        validate_policy_design_case_concept_spine(spine)


def test_concept_spine_json_schema_lists_phase_8_1_fields() -> None:
    schema_path = (
        Path(__file__).resolve().parents[4]
        / "schemas"
        / "runtime_quality"
        / "policy_design_concept_spine_v1.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema == policy_design_concept_spine_json_schema()
    assert {
        "source_projection",
        "canonical_concept_ids",
        "canonical_concepts",
        "unresolved_concepts",
        "conflicting_concepts",
        "blockers",
        "status",
    } <= set(schema["required"])
