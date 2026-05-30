# ruff: noqa: S101

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from polisyos.runtime.quality.adapter_contracts import (
    AdapterSurfacePayload,
    adapter_surface_payload_from_envelope,
    load_adapter_contract_registry,
    validate_adapter_preservation,
)
from polisyos.runtime.quality.source_truth import (
    detect_source_truth_conflict,
    load_source_truth_lattice,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
LATTICE_PATH = REPO_ROOT / "architecture/production_quality/source_truth_lattice.toml"

MINIMUM_FIELD_FAMILIES = {
    "runtime_refs",
    "final_claims",
    "source_data_context",
    "legal_context",
    "foundry_method_context",
    "scorecard_identity_and_gates",
    "approval_readiness_public_status",
    "mode_and_fallback_records",
}
REQUIRED_ADAPTER_PATHS = {
    "runtime_to_cas",
    "runtime_to_progress",
    "progress_to_api",
    "runtime_to_canary_bundle",
    "bundle_to_scorecard",
    "scorecard_to_readiness",
    "readiness_to_approval",
    "api_to_dashboard",
    "public_export",
}
REQUIRED_SEMANTIC_FIELDS = {
    "status",
    "provenance",
    "owner",
    "schema",
    "lineage",
    "tenant",
    "time_context",
    "jurisdiction",
    "source_family",
    "method_expectation",
    "claim_sets",
}
CHAIN_PRESERVED_FIELD_CASES = (
    ("runtime_to_progress", "runtime", "runtime.progress", "final_claims", "claim_sets"),
    (
        "runtime_to_canary_bundle",
        "runtime",
        "runtime.canary_bundle",
        "source_data_context",
        "source_family",
    ),
    (
        "bundle_to_scorecard",
        "runtime.canary_bundle",
        "runtime.scorecard",
        "foundry_method_context",
        "method_expectation",
    ),
    (
        "bundle_to_scorecard",
        "runtime.canary_bundle",
        "runtime.scorecard",
        "legal_context",
        "norm_refs",
    ),
    (
        "scorecard_to_readiness",
        "runtime.scorecard",
        "runtime.readiness",
        "scorecard_identity_and_gates",
        "scorecard_identity",
    ),
    (
        "scorecard_to_readiness",
        "runtime.scorecard",
        "runtime.readiness",
        "approval_readiness_public_status",
        "approval_state",
    ),
)


def _authority_payload() -> dict[str, object]:
    return {
        "status": "pass",
        "provenance": {"producer": "polisyos.runtime.evidence"},
        "owner": "team-runtime-quality",
        "schema": {"name": "runtime_quality.policy_grounding_matrix", "version": "1"},
        "lineage": {"input_refs": ["sha256:1"], "output_ref": "sha256:2"},
        "tenant": {"tenant_id": "tenant-001", "cell_id": "cell-a"},
        "time_context": {"as_of": "2026-05-15", "coverage": ["2024", "2026"]},
        "jurisdiction": {"code": "UA", "filters": ["wartime_msme_support"]},
        "source_family": {"families": ["production_msme_panel"]},
        "method_expectation": {"families": ["causal_effect_estimation"]},
        "claim_sets": {"claim_ids": ["rec_1"], "claim_refs": ["sha256:claim"]},
        "norm_refs": {"norm_ids": ["norm.ua.credit_eligibility"]},
        "scorecard_identity": {
            "scorecard_ref": "sha256:scorecard",
            "scorecard_digest": "sha256:scorecard-digest",
        },
        "approval_state": {"state": "approval_ready", "eligible": True},
    }


def test_source_truth_lattice_declares_minimum_authority_field_families() -> None:
    lattice = load_source_truth_lattice(LATTICE_PATH)

    assert set(lattice.field_families) >= MINIMUM_FIELD_FAMILIES
    runtime_refs = lattice.field_families["runtime_refs"]
    assert runtime_refs.authoritative_producer == "runtime.cas"
    assert "runtime.progress" in runtime_refs.allowed_projection_surfaces
    assert "runtime.canary_bundle" in runtime_refs.allowed_package_surfaces
    assert runtime_refs.conflict_failure_code == "hds_runtime_ref_authority_conflict"
    assert {
        "field_family",
        "authoritative_producer",
        "authoritative_surface",
        "losing_surface",
        "lost_fields",
        "failure_code",
        "owner",
        "next_diagnostic_command",
    } <= set(runtime_refs.losing_authority_record_required_fields)


def test_losing_authority_records_use_family_failure_code_and_required_format() -> None:
    lattice = load_source_truth_lattice(LATTICE_PATH)

    record = lattice.losing_authority_record(
        field_family="scorecard_identity_and_gates",
        authoritative_surface="runtime.scorecard",
        losing_surface="runtime.readiness",
        lost_fields=["gate_statuses"],
        authoritative_ref="sha256:scorecard",
        losing_ref="sha256:readiness-projection",
        details={"reason": "readiness attempted to upgrade a failed gate"},
    )

    family = lattice.field_families["scorecard_identity_and_gates"]
    assert record["failure_code"] == family.conflict_failure_code
    for field in family.losing_authority_record_required_fields:
        assert field in record
    assert record["field_family"] == "scorecard_identity_and_gates"
    assert record["lost_fields"] == ["gate_statuses"]


def test_adapter_contract_registry_contains_required_edges_and_semantic_requirements() -> None:
    registry = load_adapter_contract_registry(LATTICE_PATH)

    assert set(registry.adapter_paths) >= REQUIRED_ADAPTER_PATHS
    for path_name in REQUIRED_ADAPTER_PATHS:
        contract = registry.adapter_paths[path_name]
        assert contract.blocker_code == "hds_adapter_semantic_loss"
        assert set(contract.required_semantic_fields) >= REQUIRED_SEMANTIC_FIELDS
        assert set(contract.field_families) >= MINIMUM_FIELD_FAMILIES


@pytest.mark.parametrize("field_name", sorted(REQUIRED_SEMANTIC_FIELDS))
def test_authority_semantic_fields_cannot_be_dropped_without_blocker(
    field_name: str,
) -> None:
    registry = load_adapter_contract_registry(LATTICE_PATH)
    before = AdapterSurfacePayload(
        surface="runtime",
        field_families={"final_claims": _authority_payload()},
    )
    dropped_payload = deepcopy(_authority_payload())
    dropped_payload.pop(field_name)
    after = AdapterSurfacePayload(
        surface="runtime.cas",
        field_families={"final_claims": dropped_payload},
    )

    report = validate_adapter_preservation(
        adapter_path="runtime_to_cas",
        before=before,
        after=after,
        registry=registry,
    )

    assert report.status == "blocked"
    assert report.blockers
    assert any(
        blocker.code == "hds_adapter_semantic_loss"
        and blocker.field_family == "final_claims"
        and field_name in blocker.lost_fields
        for blocker in report.blockers
    )


def test_adapter_checks_block_missing_field_family_payloads() -> None:
    registry = load_adapter_contract_registry(LATTICE_PATH)
    before = AdapterSurfacePayload(
        surface="runtime",
        field_families={"legal_context": _authority_payload()},
    )
    after = AdapterSurfacePayload(surface="runtime.cas", field_families={})

    report = validate_adapter_preservation(
        adapter_path="runtime_to_cas",
        before=before,
        after=after,
        registry=registry,
    )

    assert report.status == "blocked"
    assert any(
        blocker.code == "hds_adapter_semantic_loss"
        and blocker.field_family == "legal_context"
        and set(blocker.lost_fields) >= REQUIRED_SEMANTIC_FIELDS
        for blocker in report.blockers
    )


def test_typed_source_truth_envelope_reads_adapter_surface_payloads() -> None:
    surface = adapter_surface_payload_from_envelope(
        {
            "schema_version": "policyos.runtime.quality.source_truth_surface.v1",
            "source_truth": {
                "surface": "runtime.progress",
                "field_families": {
                    "final_claims": _authority_payload(),
                },
            },
            "nested": {
                "field_families": {
                    "final_claims": {"claim_sets": {"claim_ids": ["spoofed"]}},
                }
            },
        },
        expected_surface="runtime.progress",
    )

    assert surface.surface == "runtime.progress"
    assert surface.payload_for("final_claims")["claim_sets"] == {
        "claim_ids": ["rec_1"],
        "claim_refs": ["sha256:claim"],
    }


@pytest.mark.parametrize(
    ("adapter_path", "source_surface", "target_surface", "field_family", "field_name"),
    CHAIN_PRESERVED_FIELD_CASES,
)
def test_authority_semantic_values_cannot_change_across_runtime_chain_without_blocker(
    adapter_path: str,
    source_surface: str,
    target_surface: str,
    field_family: str,
    field_name: str,
) -> None:
    registry = load_adapter_contract_registry(LATTICE_PATH)
    before_payload = _authority_payload()
    after_payload = deepcopy(before_payload)
    assert after_payload[field_name] != {"changed": True}
    after_payload[field_name] = {"changed": True}

    report = validate_adapter_preservation(
        adapter_path=adapter_path,
        before=AdapterSurfacePayload(
            surface=source_surface,
            field_families={field_family: before_payload},
        ),
        after=AdapterSurfacePayload(
            surface=target_surface,
            field_families={field_family: after_payload},
        ),
        registry=registry,
    )

    assert report.status == "blocked"
    assert any(
        blocker.code == "hds_adapter_semantic_loss"
        and blocker.field_family == field_family
        and field_name in blocker.lost_fields
        and blocker.losing_authority_record["failure_code"].startswith("hds_")
        for blocker in report.blockers
    )


@pytest.mark.parametrize(
    "case",
    [
        {"name": "runtime job state and progress state", "field_family": "approval_readiness_public_status", "authoritative_source": "runtime.job_state", "authoritative_surface": "runtime", "authoritative_values": {"state": "completed", "runtime_event_ref": "evt:job"}, "conflicting_source": "runtime.progress", "conflicting_surface": "runtime.progress", "conflicting_values": {"state": "failed", "runtime_event_ref": "evt:progress"}, "fields": ("state",), "downstream_impact": "approval and public export would read a terminal pass state"},
        {"name": "runtime CAS ref and bundled report embedded ref", "field_family": "runtime_refs", "authoritative_source": "runtime.cas", "authoritative_surface": "runtime.cas", "authoritative_values": {"production_data_quality_report_ref": "sha256:" + "1" * 64, "cas_ref": "sha256:" + "1" * 64, "runtime_event_ref": "evt:cas"}, "conflicting_source": "runtime.canary_bundle", "conflicting_surface": "runtime.canary_bundle", "conflicting_values": {"production_data_quality_report_ref": "sha256:" + "2" * 64, "cas_ref": "sha256:" + "2" * 64}, "fields": ("production_data_quality_report_ref",), "downstream_impact": "scorecard would trust a bundled report with a different CAS ref"},
        {"name": "selected variant and scorecard refs", "field_family": "final_claims", "authoritative_source": "runtime.selected_variant", "authoritative_surface": "runtime", "authoritative_values": {"selected_variant_id": "qwen", "final_policy_claims_ref": "sha256:" + "3" * 64}, "conflicting_source": "runtime.scorecard", "conflicting_surface": "runtime.scorecard", "conflicting_values": {"selected_variant_id": "kimi", "final_policy_claims_ref": "sha256:" + "4" * 64}, "fields": ("selected_variant_id", "final_policy_claims_ref"), "downstream_impact": "scorecard would close out claims from a losing model variant"},
        {"name": "bundle scorecard and runtime scorecard", "field_family": "scorecard_identity_and_gates", "authoritative_source": "runtime.scorecard", "authoritative_surface": "runtime.scorecard", "authoritative_values": {"quality_scorecard_ref": "sha256:" + "5" * 64, "quality_status": "fail"}, "conflicting_source": "runtime.canary_bundle", "conflicting_surface": "runtime.canary_bundle", "conflicting_values": {"quality_scorecard_ref": "quality_evidence/quality_scorecard.json", "quality_status": "pass"}, "fields": ("quality_scorecard_ref", "quality_status"), "downstream_impact": "canary matrix would accept a packaged scorecard over runtime authority"},
        {"name": "API projection and readiness result", "field_family": "approval_readiness_public_status", "authoritative_source": "runtime.readiness", "authoritative_surface": "runtime.readiness", "authoritative_values": {"readiness": "blocked", "approval_state": "quality_failed"}, "conflicting_source": "runtime.api", "conflicting_surface": "runtime.api", "conflicting_values": {"readiness": "pass", "approval_state": "approval_ready"}, "fields": ("readiness", "approval_state"), "downstream_impact": "API would publish an approval-ready projection over readiness"},
        {"name": "dashboard approval projection and persisted approval packet", "field_family": "approval_readiness_public_status", "authoritative_source": "runtime.approval_packet", "authoritative_surface": "runtime.approval", "authoritative_values": {"approval_packet_ref": "sha256:" + "6" * 64, "decision": "blocked"}, "conflicting_source": "runtime.dashboard", "conflicting_surface": "runtime.dashboard", "conflicting_values": {"approval_packet_ref": "sha256:" + "7" * 64, "decision": "approved"}, "fields": ("approval_packet_ref", "decision"), "downstream_impact": "dashboard would show approval over the persisted packet"},
    ],
    ids=lambda case: case["name"],
)
def test_phase36_reader_conflicts_emit_complete_source_truth_records(
    case: dict[str, object],
) -> None:
    conflict = detect_source_truth_conflict(
        field_family=str(case["field_family"]),
        authoritative_source=str(case["authoritative_source"]),
        authoritative_surface=str(case["authoritative_surface"]),
        authoritative_values=case["authoritative_values"],  # type: ignore[arg-type]
        conflicting_source=str(case["conflicting_source"]),
        conflicting_surface=str(case["conflicting_surface"]),
        conflicting_values=case["conflicting_values"],  # type: ignore[arg-type]
        fields=case["fields"],  # type: ignore[arg-type]
        downstream_impact=str(case["downstream_impact"]),
    )

    assert conflict is not None
    assert conflict["authoritative_source"] == case["authoritative_source"]
    assert conflict["conflicting_source"] == case["conflicting_source"]
    assert conflict["field_family"] == case["field_family"]
    assert conflict["failure_code"].startswith("hds_")
    assert conflict["owner"]
    assert conflict["downstream_impact"] == case["downstream_impact"]
    assert conflict["next_diagnostic_command"].startswith("uv run pytest")
    assert isinstance(conflict["runtime_event_refs"], list)
    assert isinstance(conflict["cas_refs"], list)
    assert conflict["losing_authority_record"]["failure_code"] == conflict["failure_code"]
    assert conflict["losing_authority_record"]["field_family"] == case["field_family"]
    assert set(conflict["lost_fields"]) == set(case["fields"])  # type: ignore[arg-type]


def test_phase36_matching_reader_values_do_not_emit_conflicts() -> None:
    conflict = detect_source_truth_conflict(
        field_family="scorecard_identity_and_gates",
        authoritative_source="runtime.scorecard",
        authoritative_surface="runtime.scorecard",
        authoritative_values={
            "quality_scorecard_ref": "sha256:" + "8" * 64,
            "quality_status": "pass",
        },
        conflicting_source="runtime.readiness",
        conflicting_surface="runtime.readiness",
        conflicting_values={
            "quality_scorecard_ref": "sha256:" + "8" * 64,
            "quality_status": "pass",
        },
        fields=("quality_scorecard_ref", "quality_status"),
        downstream_impact="readiness can safely project the scorecard decision",
    )

    assert conflict is None
