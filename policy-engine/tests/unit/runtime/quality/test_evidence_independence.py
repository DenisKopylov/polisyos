from __future__ import annotations

# ruff: noqa: S101
import hashlib

from polisyos.runtime.quality.evidence_independence import build_evidence_independence_map
from polisyos.runtime.quality.evidence_portfolio import (
    EVIDENCE_PORTFOLIO_DESIGN_SCHEMA_VERSION,
)


def _sha(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode("utf-8")).hexdigest()


def _design() -> dict[str, object]:
    strand = {
        "strand_id": "data-strand",
        "claim_id": "claim-a",
        "authority_level": "research",
        "candidate_data_source_families": ["administrative-register"],
        "candidate_method_families": ["causal-estimation"],
        "defensible_specification_space": {"estimand": "ATT"},
        "inclusion_rules": ["Use the registered source."],
        "exclusion_rules": ["Exclude non-source fixtures."],
        "disconfirming_lines": ["negative-control"],
        "synthesis_rules": {"strategy": "compare"},
        "stopping_rules": {"minimum_effective_count": 1},
        "cost_proportionality": {"budget": "small"},
    }
    return {
        "schema_version": EVIDENCE_PORTFOLIO_DESIGN_SCHEMA_VERSION,
        "portfolio_id": "portfolio-independent-1",
        "claim_ids": ["claim-a"],
        "predeclared": True,
        "declared_at": "2026-10-10T08:00:00+00:00",
        "authority_level": "research",
        "strands": [strand],
        "candidate_data_source_families": ["administrative-register"],
        "candidate_method_families": ["causal-estimation"],
        "inclusion_rules": ["Use the registered source."],
        "exclusion_rules": ["Exclude non-source fixtures."],
        "disconfirming_lines": ["negative-control"],
        "synthesis_rules": {"strategy": "compare"},
        "stopping_rules": {"minimum_effective_count": 1},
        "cost_proportionality": {"budget": "small"},
    }


def _line(line_id: str, specification_id: str) -> dict[str, object]:
    return {
        "schema_version": "policyos.runtime.policy_design_case.evidence_line.v1",
        "line_id": line_id,
        "portfolio_id": "portfolio-independent-1",
        "portfolio_strand_id": "data-strand",
        "claim_id": "claim-a",
        "evidence_strand": "data",
        "source_lineage": {
            "source_id": "administrative-register-v1",
            "source_ref": _sha("source"),
            "lineage_refs": [_sha("lineage")],
            "corpus_id": "registered-corpus",
            "corpus_ancestry": ["national-register"],
        },
        "corpus_ancestry": ["national-register"],
        "author_pool": ["analysis-team"],
        "institution_pool": ["policy-lab"],
        "preprocessing_pipeline_id": "normalize-v1",
        "method_id": "causal.did.primary",
        "method_assumptions": ["parallel-trends"],
        "identification_strategy_id": "did-att-v1",
        "shared_failure_modes": ["linkage-bias"],
        "specification_id": specification_id,
        "producer_identity": {
            "component": "polisyos.foundry.methods.causal",
            "version": "test-v1",
            "owner": "runtime-quality-tests",
        },
        "execution_context": {
            "run_id": "run-independent",
            "job_id": f"job-{line_id}",
            "tenant_id": "tenant-test",
            "trace_id": f"trace-{line_id}",
            "executed_at": "2026-10-10T08:30:00+00:00",
        },
        "evidence_ref": _sha(f"evidence-{line_id}"),
        "runtime_event_ref": _sha(f"event-{line_id}"),
    }


def test_duplicate_source_mass_is_collapsed_independent_of_input_order() -> None:
    lines = [_line("line-a", "spec-a"), _line("line-b", "spec-b")]
    designs = [_design()]

    assert len({line["specification_id"] for line in lines}) == 2
    assert len({line["evidence_ref"] for line in lines}) == 2
    assert len({line["runtime_event_ref"] for line in lines}) == 2

    forward = build_evidence_independence_map(
        lines,
        portfolio_designs=designs,
        map_id="map-order-check",
        producer_execution_started_at="2026-10-10T09:00:00+00:00",
    )
    reverse = build_evidence_independence_map(
        list(reversed(lines)),
        portfolio_designs=designs,
        map_id="map-order-check",
        producer_execution_started_at="2026-10-10T09:00:00+00:00",
    )

    assert forward["raw_evidence_line_count"] == 2
    assert forward["effective_independent_evidence_count"] == 1
    assert reverse["raw_evidence_line_count"] == 2
    assert reverse["effective_independent_evidence_count"] == 1
    assert forward["portfolio_ids"] == reverse["portfolio_ids"] == ["portfolio-independent-1"]
    assert forward["claim_ids"] == reverse["claim_ids"] == ["claim-a"]
    assert forward["effective_mass_report"] == reverse["effective_mass_report"]

    forward_clusters = forward["collapse_clusters"]
    reverse_clusters = reverse["collapse_clusters"]
    assert len(forward_clusters) == len(reverse_clusters) == 1

    def semantic_cluster(cluster: dict[str, object]) -> tuple[object, ...]:
        reason_rows = tuple(
            sorted(
                (
                    reason["dimension"],
                    reason["reason_code"],
                    reason["value"],
                    tuple(sorted(reason["line_ids"])),
                    reason["collapse_policy"],
                )
                for reason in cluster["collapse_reasons"]
            )
        )
        return (
            tuple(sorted(cluster["line_ids"])),
            cluster["raw_line_count"],
            cluster["effective_line_count"],
            cluster["collapse_dimensions"],
            reason_rows,
        )

    forward_cluster = forward_clusters[0]
    reverse_cluster = reverse_clusters[0]
    assert semantic_cluster(forward_cluster) == semantic_cluster(reverse_cluster)
    for cluster in (forward_cluster, reverse_cluster):
        assert set(cluster["line_ids"]) == {"line-a", "line-b"}
        assert cluster["raw_line_count"] == 2
        assert cluster["effective_line_count"] == 1
        # The representative is a member pointer, not an independent-mass input.
        assert cluster["representative_line_id"] in cluster["line_ids"]

    dimensions = forward_cluster["collapse_dimensions"]
    assert dimensions["method_cluster_id"] == "causal.did.primary"
    source_lineage = lines[0]["source_lineage"]
    source_lineage_parts = [
        source_lineage["source_id"],
        source_lineage["source_ref"],
        *source_lineage["lineage_refs"],
    ]
    encoded_lineage_parts = dimensions["source_lineage_cluster_id"].split("|")
    assert len(encoded_lineage_parts) == len(set(encoded_lineage_parts))
    assert set(encoded_lineage_parts) == set(source_lineage_parts)
