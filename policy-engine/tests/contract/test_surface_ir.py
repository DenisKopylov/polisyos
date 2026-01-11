from __future__ import annotations

from decimal import Decimal

import pytest
from polisyos.ir.kernel import (
    DEFAULT_CONSTRAINT_REGISTRY,
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_METRIC_REGISTRY,
    DEFAULT_SELECTOR_FIELD_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
    MergeRuleKind,
    MergeRuleRegistry,
    MergeRuleSpec,
)
from polisyos.ir.linker import link_policy
from polisyos.ir.surface import PolicyAdvisory, PolicySemantic, PolicySurfaceIR
from polisyos.ir.types import SelectorOperator
from pydantic import ValidationError

CTX_REF = "sha256:0000000000000000000000000000000000000000000000000000000000000000"


def _minimal_semantic() -> PolicySemantic:
    return PolicySemantic(
        context_snapshot_ref="sha256:0000000000000000000000000000000000000000000000000000000000000000",
        interventions=[
            {
                "intervention_id": "tax_cut",
                "kind": "income_tax",
                "target": {
                    "kind": "predicate",
                    "field": "id",
                    "operator": SelectorOperator.EQUALS,
                    "value": "all",
                },
                "schedule": {"start_step": 0, "duration_steps": 1},
                "params": {"rate": Decimal("0.1")},
            }
        ],
    )


def test_surface_ir_rejects_float_params() -> None:
    with pytest.raises(ValidationError):
        PolicySemantic(
            context_snapshot_ref=CTX_REF,
            interventions=[
                {
                    "intervention_id": "tax_cut",
                    "kind": "income_tax",
                    "target": {
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    "schedule": {"start_step": 0, "duration_steps": 1},
                    "params": {"rate": 0.1},
                }
            ],
        )


def test_semantic_payload_ignores_advisory() -> None:
    semantic = _minimal_semantic()
    policy_a = PolicySurfaceIR(semantic=semantic)
    policy_b = PolicySurfaceIR(
        semantic=semantic,
        advisory=PolicyAdvisory(
            entities=[
                {
                    "entity_id": "gov",
                    "entity_type": "agent",
                }
            ]
        ),
    )

    assert policy_a.semantic_fingerprint_payload() == policy_b.semantic_fingerprint_payload()


def test_linker_reports_missing_params() -> None:
    policy = PolicySurfaceIR(
        semantic=PolicySemantic(
            context_snapshot_ref=CTX_REF,
            interventions=[
                {
                    "intervention_id": "subsidy",
                    "kind": "tax_subsidy",
                    "target": {
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    "schedule": {"start_step": 0, "duration_steps": 1},
                    "params": {},
                }
            ],
        )
    )

    report = link_policy(
        policy,
        DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        constraint_registry=DEFAULT_CONSTRAINT_REGISTRY,
        metric_registry=DEFAULT_METRIC_REGISTRY,
        selector_field_registry=DEFAULT_SELECTOR_FIELD_REGISTRY,
    )
    assert report.ok is False
    assert any(issue.code == "missing_param" for issue in report.issues)


def test_linker_accepts_percent_rate() -> None:
    policy = PolicySurfaceIR(
        semantic=PolicySemantic(
            context_snapshot_ref=CTX_REF,
            interventions=[
                {
                    "intervention_id": "tax_cut",
                    "kind": "income_tax",
                    "target": {
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    "schedule": {"start_step": 0, "duration_steps": 1},
                    "params": {"rate": "15%"},
                }
            ],
        )
    )

    report = link_policy(
        policy,
        DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        constraint_registry=DEFAULT_CONSTRAINT_REGISTRY,
        metric_registry=DEFAULT_METRIC_REGISTRY,
        selector_field_registry=DEFAULT_SELECTOR_FIELD_REGISTRY,
    )
    assert report.ok is True


def test_linker_rejects_invalid_rate_string() -> None:
    policy = PolicySurfaceIR(
        semantic=PolicySemantic(
            context_snapshot_ref=CTX_REF,
            interventions=[
                {
                    "intervention_id": "tax_cut",
                    "kind": "income_tax",
                    "target": {
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    "schedule": {"start_step": 0, "duration_steps": 1},
                    "params": {"rate": "fifteen"},
                }
            ],
        )
    )

    report = link_policy(
        policy,
        DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        constraint_registry=DEFAULT_CONSTRAINT_REGISTRY,
        metric_registry=DEFAULT_METRIC_REGISTRY,
        selector_field_registry=DEFAULT_SELECTOR_FIELD_REGISTRY,
    )
    assert report.ok is False
    assert any(issue.code == "param_type" for issue in report.issues)


def test_semantic_fingerprint_normalizes_schedule() -> None:
    base_semantic = _minimal_semantic()
    policy_duration = PolicySurfaceIR(semantic=base_semantic)

    policy_end = PolicySurfaceIR(
        semantic=base_semantic.model_copy(
            update={
                "interventions": [
                    {
                        "intervention_id": "tax_cut",
                        "kind": "income_tax",
                        "target": {
                            "kind": "predicate",
                            "field": "id",
                            "operator": SelectorOperator.EQUALS,
                            "value": "all",
                        },
                        "schedule": {"start_step": 0, "end_step": 0},
                        "params": {"rate": Decimal("0.1")},
                    }
                ]
            }
        )
    )

    assert (
        policy_duration.semantic_fingerprint_payload() == policy_end.semantic_fingerprint_payload()
    )


def test_semantic_fingerprint_normalizes_numeric_strings() -> None:
    policy_a = PolicySurfaceIR(
        semantic=PolicySemantic(
            context_snapshot_ref=CTX_REF,
            interventions=[
                {
                    "intervention_id": "tax_cut",
                    "kind": "income_tax",
                    "target": {
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    "schedule": {"start_step": 0, "duration_steps": 1},
                    "params": {"rate": "0.2"},
                }
            ],
        )
    )
    policy_b = PolicySurfaceIR(
        semantic=PolicySemantic(
            context_snapshot_ref=CTX_REF,
            interventions=[
                {
                    "intervention_id": "tax_cut",
                    "kind": "income_tax",
                    "target": {
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    "schedule": {"start_step": 0, "duration_steps": 1},
                    "params": {"rate": "0.20"},
                }
            ],
        )
    )

    assert policy_a.semantic_fingerprint_payload(
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY
    ) == policy_b.semantic_fingerprint_payload(mechanism_registry=DEFAULT_MECHANISM_REGISTRY)


def test_linker_ignores_non_overlapping_error_merge() -> None:
    error_merge = MergeRuleRegistry(
        rules={"sum": MergeRuleSpec(rule_id="sum", kind=MergeRuleKind.ERROR)}
    )
    policy = PolicySurfaceIR(
        semantic=PolicySemantic(
            context_snapshot_ref=CTX_REF,
            interventions=[
                {
                    "intervention_id": "tax_cut_1",
                    "kind": "income_tax",
                    "target": {
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    "schedule": {"start_step": 0, "duration_steps": 1},
                    "params": {"rate": Decimal("0.1")},
                },
                {
                    "intervention_id": "tax_cut_2",
                    "kind": "income_tax",
                    "target": {
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    "schedule": {"start_step": 1, "duration_steps": 1},
                    "params": {"rate": Decimal("0.1")},
                },
            ],
        )
    )

    report = link_policy(
        policy,
        DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=error_merge,
        constraint_registry=DEFAULT_CONSTRAINT_REGISTRY,
        metric_registry=DEFAULT_METRIC_REGISTRY,
        selector_field_registry=DEFAULT_SELECTOR_FIELD_REGISTRY,
    )
    assert report.ok is True


def test_linker_reports_overlapping_error_merge() -> None:
    error_merge = MergeRuleRegistry(
        rules={"sum": MergeRuleSpec(rule_id="sum", kind=MergeRuleKind.ERROR)}
    )
    policy = PolicySurfaceIR(
        semantic=PolicySemantic(
            context_snapshot_ref=CTX_REF,
            interventions=[
                {
                    "intervention_id": "tax_cut_1",
                    "kind": "income_tax",
                    "target": {
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    "schedule": {"start_step": 0, "duration_steps": 1},
                    "params": {"rate": Decimal("0.1")},
                },
                {
                    "intervention_id": "tax_cut_2",
                    "kind": "income_tax",
                    "target": {
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    "schedule": {"start_step": 0, "duration_steps": 1},
                    "params": {"rate": Decimal("0.2")},
                },
            ],
        )
    )

    report = link_policy(
        policy,
        DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=error_merge,
        constraint_registry=DEFAULT_CONSTRAINT_REGISTRY,
        metric_registry=DEFAULT_METRIC_REGISTRY,
        selector_field_registry=DEFAULT_SELECTOR_FIELD_REGISTRY,
    )
    assert report.ok is False
    assert any(issue.code == "merge_conflict" for issue in report.issues)
