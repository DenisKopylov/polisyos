# ruff: noqa: S101

from __future__ import annotations

from datetime import UTC, datetime

from polisyos.runtime.quality.closeout_reader import (
    CLOSEOUT_INTEGRATION_SCHEMA_VERSION,
    CLOSEOUT_READER_SCHEMA_VERSION,
    CloseoutModuleReaderSpec,
    build_can_i_closeout_verdict,
    build_closeout_reader_skeleton,
)
from polisyos.runtime.quality.rule_evolution import build_rule_evolution_registry
from polisyos.runtime.quality.status_deficits import (
    build_status_envelope,
    status_envelope_payload,
)
from polisyos.scientist.cross_graph.conflict import ConflictSeverity, EvidenceConflict
from polisyos.scientist.cross_graph.conflict_materializer import (
    build_conflict_materialization_closeout_record,
    validate_conflict_backstop_coverage,
)


def test_reader_skeleton_emits_incomplete_closeout_only_verdict() -> None:
    verdict = build_closeout_reader_skeleton(
        run_id="run-w1d",
        module_records={
            "closeout_compatibility": {
                "schema_version": "policyos.runtime.can_i_closeout_compatibility.v1",
                "status": "pass",
                "producer_reader_matrix": [],
                "issues": [],
            }
        },
    )

    assert verdict["schema_version"] == CLOSEOUT_READER_SCHEMA_VERSION
    assert verdict["status"] == "incomplete"
    assert verdict["can_closeout"] is False
    assert verdict["capability_reality_state"] == "implemented_but_not_orchestrated"
    assert verdict["authority_envelope"]["authoritative_for"] == ["closeout_verdict"]
    assert set(verdict["authority_envelope"]["may_not_use_for"]) >= {
        "claim_authority",
        "dashboard_projection",
        "domain_evidence",
        "public_export",
    }

    issue_codes = {issue["code"] for issue in verdict["issues"]}
    assert "closeout_module_reader_stubbed" in issue_codes
    assert "closeout_module_evidence_missing" in issue_codes
    assert {
        row["module_id"]: row["status"] for row in verdict["module_reader_results"]
    }["closeout_compatibility"] == "pass"


def test_projection_readiness_packaging_and_public_export_cannot_satisfy_closeout() -> None:
    verdict = build_closeout_reader_skeleton(
        run_id="run-projection-only",
        module_records={
            "closeout_compatibility": {
                "schema_version": "policyos.runtime.can_i_closeout_compatibility.v1",
                "status": "pass",
                "producer_reader_matrix": [],
                "issues": [],
            }
        },
        substitute_records=[
            {
                "surface": "dashboard",
                "status": "ready",
                "authority_role": "projection_only",
                "provenance_kind": "runtime_projection",
                "may_not_be_used_for": ["runtime_closeout_authority"],
            },
            {
                "surface": "readiness",
                "status": "pass",
                "authority_role": "readiness_input",
            },
            {
                "surface": "bundle",
                "status": "pass",
                "authority_role": "packaging_only",
                "provenance_kind": "bundle_packaged",
            },
            {
                "surface": "public_export",
                "status": "publishable",
                "authority_role": "projection_only",
                "provenance_kind": "runtime_projection",
            },
        ],
    )

    assert verdict["can_closeout"] is False
    assert verdict["status"] == "blocked"
    rejection_codes = {row["code"] for row in verdict["substitution_rejections"]}
    assert rejection_codes >= {
        "closeout_dashboard_projection_not_authority",
        "closeout_packaging_not_authority",
        "closeout_public_export_not_authority",
        "closeout_readiness_not_closeout_evidence",
    }
    assert {
        issue["code"] for issue in verdict["issues"] if issue["severity"] == "fail"
    } >= rejection_codes


def test_projection_only_module_record_is_negative_closeout_evidence() -> None:
    verdict = build_closeout_reader_skeleton(
        run_id="run-projection-module",
        module_records={
            "closeout_compatibility": {
                "schema_version": "policyos.runtime.can_i_closeout_compatibility.v1",
                "status": "pass",
                "producer_reader_matrix": [],
                "issues": [],
            },
            "semantic_binding": {
                "status": "pass",
                "authority_role": "projection_only",
                "provenance_kind": "runtime_projection",
                "may_not_use_for": ["runtime_closeout_authority"],
            },
        },
    )

    semantic_binding = {
        row["module_id"]: row for row in verdict["module_reader_results"]
    }["semantic_binding"]
    assert semantic_binding["status"] == "fail"
    assert semantic_binding["issue_codes"] == ["closeout_projection_only_not_authority"]
    assert "closeout_projection_only_not_authority" in {
        issue["code"] for issue in verdict["issues"]
    }


def test_rule_evolution_revalidation_state_is_closeout_consumed() -> None:
    old_registry = build_rule_evolution_registry(
        registry_id="rule-registry-2026-05",
        version="2026.05",
        effective_at="2026-05-22T00:00:00+00:00",
        rule_refs=[
            {
                "requirement_id": "req.credit_support",
                "logic": {"predicate": "liquidity_gap", "threshold": 0.2},
                "taxonomy_refs": ["taxonomy.policy_obligation.v1"],
                "authority_purpose": "admissibility",
            }
        ],
        taxonomy_refs=[
            {
                "taxonomy_id": "taxonomy.policy_obligation",
                "version": "2026.05",
                "ref": "sha256:" + "a" * 64,
            }
        ],
        evidence_ref="sha256:" + "b" * 64,
        runtime_event_ref="event://rule-evolution/2026-05",
    )
    changed_registry = build_rule_evolution_registry(
        registry_id="rule-registry-2026-07",
        version="2026.07",
        effective_at="2026-07-01T00:00:00+00:00",
        previous_registry=old_registry,
        rule_refs=[
            {
                "requirement_id": "req.credit_support.v2",
                "logic": {"predicate": "liquidity_gap", "threshold": 0.35},
                "taxonomy_refs": ["taxonomy.policy_obligation.v1"],
                "authority_purpose": "admissibility",
            }
        ],
        taxonomy_refs=old_registry["taxonomy_refs"],
        alias_remaps=[
            {
                "from_requirement_id": "req.credit_support",
                "to_requirement_id": "req.credit_support.v2",
            }
        ],
        evidence_ref="sha256:" + "c" * 64,
        runtime_event_ref="event://rule-evolution/2026-07",
    )

    verdict = build_closeout_reader_skeleton(
        run_id="run-rule-evolution",
        module_records={
            "closeout_compatibility": {
                "schema_version": "policyos.runtime.can_i_closeout_compatibility.v1",
                "status": "pass",
                "producer_reader_matrix": [],
                "issues": [],
            },
            "rule_evolution": changed_registry,
        },
    )

    rule_evolution = {
        row["module_id"]: row for row in verdict["module_reader_results"]
    }["rule_evolution"]
    assert rule_evolution["status"] == "fail"
    assert rule_evolution["source_status"] == "blocked"
    assert "rule_alias_semantic_change_detected" in (
        rule_evolution["issues"][0]["child_issue_codes"]
    )


def test_cost_degradation_telemetry_is_observable_not_required_closeout_blocker() -> None:
    verdict = build_closeout_reader_skeleton(
        run_id="run-cost-observe",
        module_readers=(
            CloseoutModuleReaderSpec(
                module_id="closeout_compatibility",
                reader_contract="polisyos.runtime.quality.closeout_compatibility",
                owner="team-quality-closeout",
                stubbed=False,
            ),
            CloseoutModuleReaderSpec(
                module_id="cost_degradation_telemetry",
                reader_contract="polisyos.runtime.quality.cost_degradation",
                owner="team-runtime-quality",
                required=False,
                stubbed=False,
                next_wave_target="W2.C",
            ),
        ),
        module_records={
            "closeout_compatibility": {
                "schema_version": "policyos.runtime.can_i_closeout_compatibility.v1",
                "status": "pass",
                "producer_reader_matrix": [],
                "issues": [],
            },
            "cost_degradation_telemetry": {
                "schema_version": "policyos.runtime.cost_degradation_telemetry.v1",
                "status": "observe",
                "authority_role": "diagnostic_only",
                "provenance_kind": "runtime_emitted",
                "may_not_use_for": ["evidence_quality_downgrade"],
            },
        },
    )

    cost_row = {
        row["module_id"]: row for row in verdict["module_reader_results"]
    }["cost_degradation_telemetry"]

    assert verdict["status"] == "closed"
    assert verdict["can_closeout"] is True
    assert cost_row["status"] == "observe"
    assert cost_row["blocking"] is False
    assert "closeout_module_evidence_failed" not in {
        issue["code"] for issue in verdict["issues"]
    }


def test_w4_closeout_integration_closes_with_real_records_and_preserves_deficits() -> None:
    module_records = _w4_passing_module_records()
    module_records["deficit_crosswalk"] = {
        **status_envelope_payload(
            build_status_envelope(
                local_statuses=[],
                deficits=[
                    _deficit_record(
                        deficit_id="deficit-scholar-accepted",
                        disposition="accepted_deficit",
                    ),
                    _deficit_record(
                        deficit_id="deficit-source-limited",
                        disposition="publish_with_limitation",
                    ),
                ],
                now=datetime(2026, 5, 23, tzinfo=UTC),
            )
        ),
        "status": "pass",
        "authority_role": "runtime_reader",
        "provenance_kind": "runtime_emitted",
        "producer": "polisyos.runtime.quality.status_deficits",
    }

    verdict = build_can_i_closeout_verdict(
        run_id="run-w4d",
        module_records=module_records,
        readiness_record={"surface": "readiness", "status": "pass"},
        scorecard_record={
            "surface": "scorecard",
            "quality_status": "pass",
            "quality_gates": [],
            "blocking_quality_failures": [],
        },
    )

    assert verdict["schema_version"] == CLOSEOUT_INTEGRATION_SCHEMA_VERSION
    assert verdict["status"] == "closed_with_limitations"
    assert verdict["verdict"] == "can_closeout_with_limitations"
    assert verdict["can_closeout"] is True
    assert verdict["closeout_effect"] == "limited_closeout"
    assert verdict["blockers"] == []
    assert verdict["summary"]["accepted_deficit_count"] == 1
    assert verdict["summary"]["limitation_count"] == 1
    assert {
        item["deficit_id"]: item["source_module_id"]
        for item in verdict["accepted_deficits"]
    } == {"deficit-scholar-accepted": "deficit_crosswalk"}
    assert {
        item["deficit_id"]: item["source_module_id"] for item in verdict["limitations"]
    } == {"deficit-source-limited": "deficit_crosswalk"}
    assert {row["surface"] for row in verdict["observed_surfaces"]} >= {
        "readiness",
        "scorecard",
    }


def test_w4_closeout_preserves_upstream_blocker_when_readiness_and_scorecard_pass() -> None:
    module_records = _w4_passing_module_records()
    module_records["semantic_binding"] = _w4_record(
        "policyos.runtime.semantic_binding.v1",
        status="fail",
        producer="polisyos.runtime.quality.semantic_binding",
        issues=[
            {
                "code": "semantic_binding_claim_missing",
                "severity": "fail",
                "message": "Major claim lacks semantic closure.",
                "producer": "polisyos.runtime.quality.semantic_binding",
                "claim_id": "claim-msme-1",
            }
        ],
    )

    verdict = build_can_i_closeout_verdict(
        run_id="run-w4d-semantic-fail",
        module_records=module_records,
        readiness_record={"surface": "readiness", "status": "pass"},
        scorecard_record={
            "surface": "scorecard",
            "quality_status": "pass",
            "quality_gates": [],
            "blocking_quality_failures": [],
        },
    )

    assert verdict["status"] == "blocked"
    assert verdict["can_closeout"] is False
    assert {blocker["upstream_issue_code"] for blocker in verdict["blockers"]} == {
        "semantic_binding_claim_missing"
    }
    blocker = verdict["blockers"][0]
    assert blocker["source_module_id"] == "semantic_binding"
    assert blocker["source_reader_contract"] == "polisyos.runtime.quality.semantic_binding"
    assert blocker["source_producer"] == "polisyos.runtime.quality.semantic_binding"
    assert blocker["claim_id"] == "claim-msme-1"
    assert {
        row["surface"]: row["closeout_authority_effect"]
        for row in verdict["observed_surfaces"]
    } == {"readiness": "observed_only", "scorecard": "observed_only"}


def test_w8e_missing_conflict_materialization_record_blocks_closeout() -> None:
    module_records = _w4_passing_module_records()
    detector_conflict = EvidenceConflict(
        need_id="legal_applicability_need:credit_guarantee",
        dimension="legal_vs_academic",
        conflicting_sources=["legal", "academic"],
        severity=ConflictSeverity.HIGH,
        description="Legal prohibits what academic evidence supports.",
    )
    module_records["conflict_materialization"] = (
        build_conflict_materialization_closeout_record(
            {
                "conflict_records": [],
                "claim_registry": {"claims": []},
                "portfolio_index": {"conflict_records": []},
                "issues": list(
                    validate_conflict_backstop_coverage(
                        [detector_conflict],
                        conflict_records=[],
                    )
                ),
                "detector_conflicts": [
                    {
                        "need_id": detector_conflict.need_id,
                        "dimension": detector_conflict.dimension,
                    }
                ],
            }
        )
    )

    verdict = build_can_i_closeout_verdict(
        run_id="run-w8e-conflict-missing",
        module_records=module_records,
    )

    assert verdict["status"] == "blocked"
    assert verdict["can_closeout"] is False
    assert {
        blocker["upstream_issue_code"] for blocker in verdict["blockers"]
    } >= {"policy_design_conflict_materialization_missing"}
    conflict_reader = {
        row["module_id"]: row for row in verdict["module_reader_results"]
    }["conflict_materialization"]
    assert conflict_reader["status"] == "fail"


def test_w4_closeout_missing_real_reader_is_integration_blocker_not_stub() -> None:
    module_records = _w4_passing_module_records()
    module_records.pop("source_truth")

    verdict = build_can_i_closeout_verdict(
        run_id="run-w4d-missing-source-truth",
        module_records=module_records,
    )

    assert verdict["status"] == "incomplete"
    assert verdict["can_closeout"] is False
    issue_codes = {issue["code"] for issue in verdict["issues"]}
    assert "closeout_module_evidence_missing" in issue_codes
    assert "closeout_module_reader_stubbed" not in issue_codes
    source_truth = {
        row["module_id"]: row for row in verdict["module_reader_results"]
    }["source_truth"]
    assert source_truth["stubbed"] is False
    assert source_truth["status"] == "missing"


def _w4_passing_module_records() -> dict[str, dict[str, object]]:
    return {
        "i4_policy_design_case_graph": _w4_record(
            "policyos.runtime.policy_design_case.wave4_i4_graph.v1"
        ),
        "portfolio_effective_support": _w4_record(
            "policyos.runtime.policy_design_case.portfolio_effective_support.v1"
        ),
        "lifecycle_reissue": _w4_record(
            "policyos.runtime.policy_design_case.lifecycle_reissue_report.v1"
        ),
        "projection_consumer_contract": _w4_record(
            "policyos.runtime.policy_design_case.projection_contract_fixture.v1"
        ),
        "formal_invariants": _w4_record("policyos.runtime.formal_invariants.v1"),
        "source_truth": _w4_record("policyos.runtime.source_truth.v1"),
        "conflict_materialization": build_conflict_materialization_closeout_record(
            {
                "conflict_records": [],
                "claim_registry": {"claims": []},
                "portfolio_index": {"conflict_records": []},
                "issues": [],
                "detector_conflicts": [],
            }
        ),
        "attestation": _w4_record("policyos.runtime.attestation.v1"),
        "closeout_compatibility": _w4_record(
            "policyos.runtime.can_i_closeout_compatibility.v1"
        ),
        "semantic_binding": _w4_record("policyos.runtime.semantic_binding.v1"),
        "claim_registry": _w4_record("policyos.runtime.claim_registry.v1"),
        "pdc_record_family_status": _w4_record(
            "policyos.policy_design_case.record_family_coverage.v1"
        ),
        "projection_publication_state": _w4_record(
            "policyos.runtime.policy_design_case.projection_publication_state.v1"
        ),
        "complexity_self_fmea": _w4_record(
            "policyos.runtime.run_cost_proportionality.v1"
        ),
        "audit_verifier_ingestion": _w4_record("policyos.runtime.audit_verifier.v1"),
    }


def _w4_record(
    schema_version: str,
    *,
    status: str = "pass",
    producer: str = "polisyos.runtime.quality.fixture",
    issues: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": schema_version,
        "status": status,
        "authority_role": "runtime_reader",
        "provenance_kind": "runtime_emitted",
        "producer": producer,
        "runtime_event_ref": "event://w4d/test",
        "cas_ref": "sha256:" + "c" * 64,
        "issues": issues or [],
    }


def _deficit_record(*, deficit_id: str, disposition: str) -> dict[str, object]:
    return {
        "deficit_id": deficit_id,
        "deficit_family": "evidence_scope",
        "deficit_code": f"evidence_scope_{disposition}",
        "claim_ids": ["claim-msme-1"],
        "authority_level": "governed",
        "audience_scope": "public",
        "disposition": disposition,
        "support_cap": "weak",
        "readiness_cap": "external_briefing",
        "max_audience": "public_with_limitation",
        "owner": "team-policy-semantics",
        "expires_at": "2026-06-01T00:00:00+00:00",
        "runtime_event_ref": "event://status-deficit/w4d",
        "evidence_ref": "sha256:" + "d" * 64,
        "public_limitation_note": "Publish only with the recorded limitation.",
        "review_refs": ["review://status-deficit/w4d"],
    }
