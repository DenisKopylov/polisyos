from __future__ import annotations

# ruff: noqa: S101
import json
from copy import deepcopy
from pathlib import Path

import pytest

from polisyos.runtime.quality.evidence_line import (
    EVIDENCE_LINE_SCHEMA_VERSION,
    SUPPORTED_EVIDENCE_LINE_STRANDS,
    EvidenceLineError,
    validate_evidence_line_record,
)
from polisyos.runtime.quality.evidence_portfolio import (
    EVIDENCE_PORTFOLIO_DESIGN_SCHEMA_VERSION,
)
from tests._helpers.hds_quality import sha

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_PATH = (
    REPO_ROOT / "schemas/runtime_quality/policy_design_evidence_line_v1.schema.json"
)


def _portfolio_design() -> dict[str, object]:
    return {
        "schema_version": EVIDENCE_PORTFOLIO_DESIGN_SCHEMA_VERSION,
        "portfolio_id": "portfolio-rec-1",
        "claim_ids": ["rec_1"],
        "predeclared": True,
        "declared_at": "2026-05-17T08:00:00+00:00",
        "declared_before_producer_execution": True,
        "authority_level": "production",
        "strands": [
            {
                "strand_id": "data-method-literature",
                "claim_id": "rec_1",
                "authority_level": "production",
                "candidate_data_source_families": [
                    "production_msme_panel",
                    "administrative_credit_registry",
                ],
                "candidate_method_families": [
                    "causal_effect_estimation",
                    "quasi_experimental_panel",
                ],
                "defensible_specification_space": {
                    "primary_estimand": "ATT",
                    "allowed_models": ["two_way_fixed_effects", "event_study"],
                },
                "inclusion_rules": [
                    "Include production datasets with firm survival and credit exposure.",
                ],
                "exclusion_rules": [
                    "Exclude fixture or survey-only sources without legal use rights.",
                ],
                "disconfirming_lines": [
                    {
                        "line_id": "placebo-pre-period",
                        "required": True,
                        "evidence_family": "negative_control",
                    }
                ],
                "synthesis_rules": {"strategy": "triangulate_independent_lines"},
                "stopping_rules": {
                    "minimum_effective_independent_evidence_count": 2,
                },
                "cost_proportionality": {"budget_tier": "standard"},
            }
        ],
        "candidate_data_source_families": [
            "production_msme_panel",
            "administrative_credit_registry",
        ],
        "candidate_method_families": [
            "causal_effect_estimation",
            "quasi_experimental_panel",
        ],
        "inclusion_rules": ["Prefer production administrative sources."],
        "exclusion_rules": ["Reject local fixture sources."],
        "disconfirming_lines": ["placebo-pre-period"],
        "synthesis_rules": {"strategy": "triangulate_independent_lines"},
        "stopping_rules": {"minimum_effective_independent_evidence_count": 2},
        "cost_proportionality": {"budget_tier": "standard"},
        "cas_ref": sha("1"),
        "runtime_event_ref": sha("2"),
    }


def _evidence_line(*, strand: str = "data") -> dict[str, object]:
    return {
        "schema_version": EVIDENCE_LINE_SCHEMA_VERSION,
        "line_id": f"line-{strand}",
        "portfolio_id": "portfolio-rec-1",
        "portfolio_strand_id": "data-method-literature",
        "claim_id": "rec_1",
        "evidence_strand": strand,
        "source_lineage": {
            "source_id": "production-msme-panel",
            "source_ref": sha("7"),
            "lineage_refs": [sha("8")],
            "rights_ref": sha("9"),
        },
        "method_id": "causal.difference_in_differences",
        "method_assumptions": [
            "parallel trends holds after bank and oblast controls",
            "no anticipatory treatment in pre-period placebo window",
        ],
        "specification_id": "did.att.baseline.v1",
        "producer_identity": {
            "component": "polisyos.foundry.methods.causal",
            "version": "2026.05.17+wave16",
            "owner": "team-science-quality",
        },
        "execution_context": {
            "run_id": "run-policy-design-1",
            "job_id": "job-evidence-line-1",
            "tenant_id": "tenant-prod",
            "trace_id": "trace-evidence-line-1",
            "executed_at": "2026-05-17T08:30:00+00:00",
        },
        "evidence_ref": sha("a"),
        "runtime_event_ref": sha("b"),
    }


def test_evidence_line_record_binds_to_predeclared_portfolio_design() -> None:
    validated = validate_evidence_line_record(
        _evidence_line(),
        portfolio_designs=[_portfolio_design()],
        producer_execution_started_at="2026-05-17T09:00:00+00:00",
    )

    assert validated["schema_version"] == EVIDENCE_LINE_SCHEMA_VERSION
    assert validated["line_id"] == "line-data"
    assert validated["portfolio_id"] == "portfolio-rec-1"
    assert validated["claim_ids"] == ["rec_1"]
    assert validated["portfolio_strand_id"] == "data-method-literature"


def test_evidence_line_json_schema_names_required_combination_surfaces() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["properties"]["schema_version"]["const"] == EVIDENCE_LINE_SCHEMA_VERSION
    assert set(schema["properties"]["evidence_strand"]["enum"]) == set(
        SUPPORTED_EVIDENCE_LINE_STRANDS
    )
    assert set(schema["required"]) >= {
        "line_id",
        "portfolio_id",
        "claim_id",
        "evidence_strand",
        "source_lineage",
        "method_id",
        "method_assumptions",
        "specification_id",
        "producer_identity",
        "execution_context",
    }


@pytest.mark.parametrize("strand", SUPPORTED_EVIDENCE_LINE_STRANDS)
def test_evidence_line_record_supports_policy_design_evidence_strands(
    strand: str,
) -> None:
    validated = validate_evidence_line_record(
        _evidence_line(strand=strand),
        portfolio_designs=[_portfolio_design()],
        producer_execution_started_at="2026-05-17T09:00:00+00:00",
    )

    assert validated["evidence_strand"] == strand


@pytest.mark.parametrize(
    ("field", "expected_code"),
    [
        ("source_lineage", "policy_design_evidence_line_source_lineage_missing"),
        ("method_assumptions", "policy_design_evidence_line_method_assumptions_missing"),
        ("specification_id", "policy_design_evidence_line_specification_id_missing"),
        ("producer_identity", "policy_design_evidence_line_producer_identity_missing"),
    ],
)
def test_evidence_line_record_rejects_missing_required_combination_surface(
    field: str,
    expected_code: str,
) -> None:
    line = _evidence_line()
    line.pop(field)

    with pytest.raises(EvidenceLineError, match=expected_code):
        validate_evidence_line_record(
            line,
            portfolio_designs=[_portfolio_design()],
            producer_execution_started_at="2026-05-17T09:00:00+00:00",
        )


def test_evidence_line_record_rejects_unknown_strand() -> None:
    line = _evidence_line(strand="friendly")

    with pytest.raises(
        EvidenceLineError,
        match="policy_design_evidence_line_strand_invalid",
    ):
        validate_evidence_line_record(
            line,
            portfolio_designs=[_portfolio_design()],
            producer_execution_started_at="2026-05-17T09:00:00+00:00",
        )


def test_evidence_line_record_rejects_unbound_portfolio_design() -> None:
    line = _evidence_line()
    line["portfolio_id"] = "portfolio-other"

    with pytest.raises(
        EvidenceLineError,
        match="policy_design_evidence_line_portfolio_binding_missing",
    ):
        validate_evidence_line_record(
            line,
            portfolio_designs=[_portfolio_design()],
            producer_execution_started_at="2026-05-17T09:00:00+00:00",
        )


def test_evidence_line_record_rejects_unbound_portfolio_strand() -> None:
    line = deepcopy(_evidence_line())
    line["portfolio_strand_id"] = "monitoring-only"

    with pytest.raises(
        EvidenceLineError,
        match="policy_design_evidence_line_portfolio_strand_binding_missing",
    ):
        validate_evidence_line_record(
            line,
            portfolio_designs=[_portfolio_design()],
            producer_execution_started_at="2026-05-17T09:00:00+00:00",
        )
