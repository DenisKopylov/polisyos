from __future__ import annotations

# ruff: noqa: S101
import hashlib

import pytest

from polisyos.runtime.quality.evidence_line import EvidenceLineError, validate_evidence_line_record
from polisyos.runtime.quality.evidence_portfolio import (
    EVIDENCE_PORTFOLIO_DESIGN_SCHEMA_VERSION,
)


def _sha(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode("utf-8")).hexdigest()


def _portfolio() -> dict[str, object]:
    strand = {
        "strand_id": "data-strand",
        "claim_id": "claim-a",
        "authority_level": "research",
        "candidate_data_source_families": ["registered-source"],
        "candidate_method_families": ["causal-estimation"],
        "defensible_specification_space": {"estimand": "ATT"},
        "inclusion_rules": ["Include registered observations."],
        "exclusion_rules": ["Exclude unsupported sources."],
        "disconfirming_lines": ["negative-control"],
        "synthesis_rules": {"strategy": "triangulate"},
        "stopping_rules": {"minimum_effective_count": 1},
        "cost_proportionality": {"budget": "small"},
    }
    return {
        "schema_version": EVIDENCE_PORTFOLIO_DESIGN_SCHEMA_VERSION,
        "portfolio_id": "portfolio-line-1",
        "claim_ids": ["claim-a"],
        "predeclared": True,
        "declared_at": "2026-10-10T08:00:00+00:00",
        "authority_level": "research",
        "strands": [strand],
        "candidate_data_source_families": ["registered-source"],
        "candidate_method_families": ["causal-estimation"],
        "inclusion_rules": ["Include registered observations."],
        "exclusion_rules": ["Exclude unsupported sources."],
        "disconfirming_lines": ["negative-control"],
        "synthesis_rules": {"strategy": "triangulate"},
        "stopping_rules": {"minimum_effective_count": 1},
        "cost_proportionality": {"budget": "small"},
    }


def _line() -> dict[str, object]:
    return {
        "schema_version": "policyos.runtime.policy_design_case.evidence_line.v1",
        "line_id": "line-a",
        "portfolio_id": "portfolio-line-1",
        "portfolio_strand_id": "data-strand",
        "claim_id": "claim-a",
        "evidence_strand": "data",
        "source_lineage": {"source_id": "registered-source", "source_ref": _sha("source")},
        "method_id": "causal.did.primary",
        "method_assumptions": ["parallel-trends"],
        "specification_id": "did-att-v1",
        "producer_identity": {
            "component": "polisyos.foundry.methods.causal",
            "version": "test-v1",
            "owner": "runtime-quality-tests",
        },
        "execution_context": {
            "run_id": "run-line-1",
            "job_id": "job-line-1",
            "tenant_id": "tenant-test",
            "trace_id": "trace-line-1",
            "executed_at": "2026-10-10T08:30:00+00:00",
        },
        "evidence_ref": _sha("evidence"),
        "runtime_event_ref": _sha("event"),
    }


def test_evidence_line_refuses_a_portfolio_declared_after_execution_started() -> None:
    design = _portfolio()
    line = _line()
    producer_started = "2026-10-10T07:59:59+00:00"

    with pytest.raises(EvidenceLineError) as raised:
        validate_evidence_line_record(
            line,
            portfolio_designs=[design],
            producer_execution_started_at=producer_started,
        )

    assert raised.value.code == "policy_design_portfolio_design_post_hoc"
    assert raised.value.field == "declared_at"

    admitted = validate_evidence_line_record(
        line,
        portfolio_designs=[design],
        producer_execution_started_at="2026-10-10T08:00:01+00:00",
    )
    assert admitted["line_id"] == "line-a"
    assert admitted["portfolio_id"] == "portfolio-line-1"
