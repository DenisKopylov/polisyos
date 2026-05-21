from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from polisyos.runtime.quality.attestation import (
    AttestationViolation,
    REQUIRED_TRUST_BOUNDARY_IDS,
    TrustBoundaryRegistryError,
    build_required_production_attestations,
    deserialize_attestation_record,
    evaluate_trust_boundary_attestation,
    iter_required_production_attestation_boundaries,
    load_trust_boundary_registry,
    serialize_attestation_record,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
REGISTRY_PATH = REPO_ROOT / "architecture/production_quality/trust_boundaries.toml"

REQUIRED_BOUNDARIES = {
    "runtime_worker",
    "cas_writer",
    "bundle_assembler",
    "scorecard_builder",
    "readiness_aggregator",
    "approval_packet_builder",
    "dashboard_projection",
    "public_export_renderer",
    "provider_model_gateway",
    "external_data_connector",
    "legal_kg_connector",
    "prompt_tool_parser_executor",
}


def _material(key: str, ref: str) -> dict[str, str]:
    return {
        "key": key,
        "ref": ref,
        "sha256": "a" * 64,
    }


def _valid_attestation_payload() -> dict[str, object]:
    return {
        "schema_version": "polisyos.runtime.attestation.v1",
        "attestation_id": "att-runtime-worker-1",
        "trust_boundary_id": "runtime_worker",
        "generated_at": "2026-05-15T08:30:00+00:00",
        "expected_materials": [_material("run_request", "cas://sha256/" + "1" * 64)],
        "observed_materials": [_material("run_request", "cas://sha256/" + "1" * 64)],
        "expected_products": [_material("runtime_quality_refs", "cas://sha256/" + "2" * 64)],
        "observed_products": [_material("runtime_quality_refs", "cas://sha256/" + "2" * 64)],
        "functionary": {
            "functionary_id": "runtime-worker@prod-cell-a",
            "role": "runtime_worker",
            "service_account": "runtime-worker",
        },
        "producer_identity": {
            "component": "polisyos.runtime.worker",
            "version": "2026.05.15+hds-phase19",
            "owner": "team-runtime",
        },
        "environment_identity": {
            "environment_id": "prod-cell-a",
            "execution_profile": "production",
            "tenant_id": "tenant-1",
            "cell_id": "cell-a",
            "runner_id": "worker-1",
        },
        "isolation_status": "isolated",
        "service_generated": True,
        "consumer_verification": "verified",
        "tamper_check_status": "pass",
        "signature_ref": "signature://runtime-worker",
        "evidence_ref": "quality_evidence/attestation_records.json#/runtime_worker",
    }


def test_attestation_record_round_trips_and_captures_required_contract_fields() -> None:
    record = deserialize_attestation_record(_valid_attestation_payload())

    assert record.expected_materials[0].key == "run_request"
    assert record.observed_materials[0].ref == "cas://sha256/" + "1" * 64
    assert record.expected_products[0].key == "runtime_quality_refs"
    assert record.observed_products[0].ref == "cas://sha256/" + "2" * 64
    assert record.functionary.role == "runtime_worker"
    assert record.producer_identity.component == "polisyos.runtime.worker"
    assert record.environment_identity.environment_id == "prod-cell-a"
    assert record.isolation_status == "isolated"
    assert record.service_generated is True
    assert record.consumer_verification == "verified"
    assert record.tamper_check_status == "pass"

    assert deserialize_attestation_record(serialize_attestation_record(record)) == record


def test_trust_boundary_registry_classifies_phase_1_9_boundaries() -> None:
    registry = load_trust_boundary_registry(REGISTRY_PATH)

    assert REQUIRED_TRUST_BOUNDARY_IDS == REQUIRED_BOUNDARIES
    assert set(registry.boundaries) == REQUIRED_BOUNDARIES
    for boundary_id in REQUIRED_BOUNDARIES:
        boundary = registry.require(boundary_id)
        assert boundary.functionary
        assert boundary.producer_owner
        assert boundary.consumer
        assert boundary.classification
        assert boundary.scorecard_gate_name
        assert boundary.failure_code


def test_all_required_trust_boundaries_are_production_closeout_requirements() -> None:
    registry = load_trust_boundary_registry(REGISTRY_PATH)

    required_boundary_ids = {
        boundary.boundary_id
        for boundary in iter_required_production_attestation_boundaries(registry)
    }
    generated = build_required_production_attestations(registry=registry)

    assert required_boundary_ids == REQUIRED_BOUNDARIES
    assert {record.trust_boundary_id for record in generated} == REQUIRED_BOUNDARIES


def test_trust_boundary_registry_rejects_missing_required_boundary(tmp_path) -> None:
    registry = tmp_path / "trust_boundaries.toml"
    registry.write_text(
        "\n".join(
            [
                "[[trust_boundaries]]",
                'boundary_id = "runtime_worker"',
                'name = "Runtime worker"',
                'classification = "runtime_authority"',
                'functionary = "runtime_worker"',
                'producer_owner = "team-runtime"',
                'consumer = "runtime.scorecard"',
                "requires_attestation = true",
                "production_closeout_required = true",
                "diagnostic_readable_without_attestation = true",
                "isolation_required = true",
                "service_generated_required = true",
                'expected_material_kinds = ["run_request"]',
                'expected_product_kinds = ["runtime_quality_refs"]',
                'scorecard_gate_name = "runtime_worker_attestation_verified"',
                'scorecard_stage = "ops"',
                'failure_code = "attestation_missing"',
                'next_action = "Persist attestation."',
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(TrustBoundaryRegistryError, match="missing required trust boundaries"):
        load_trust_boundary_registry(registry)


def test_required_boundary_without_attestation_is_diagnostic_readable_only() -> None:
    registry = load_trust_boundary_registry(REGISTRY_PATH)

    result = evaluate_trust_boundary_attestation(
        boundary_id="runtime_worker",
        attestations=[],
        registry=registry,
    )

    assert result.status == "missing"
    assert result.diagnostic_readable is True
    assert result.production_closeout_satisfied is False
    assert result.failure_code == "attestation_missing"

    with pytest.raises(AttestationViolation, match="attestation_missing"):
        result.assert_production_closeout_satisfied()


def test_verified_attestation_satisfies_required_production_boundary() -> None:
    registry = load_trust_boundary_registry(REGISTRY_PATH)
    record = deserialize_attestation_record(_valid_attestation_payload())

    result = evaluate_trust_boundary_attestation(
        boundary_id="runtime_worker",
        attestations=[record],
        registry=registry,
    )

    assert result.status == "verified"
    assert result.diagnostic_readable is True
    assert result.production_closeout_satisfied is True
    result.assert_production_closeout_satisfied()


def test_tampered_attestation_blocks_production_closeout() -> None:
    registry = load_trust_boundary_registry(REGISTRY_PATH)
    payload = deepcopy(_valid_attestation_payload())
    payload["tamper_check_status"] = "fail"
    record = deserialize_attestation_record(payload)

    result = evaluate_trust_boundary_attestation(
        boundary_id="runtime_worker",
        attestations=[record],
        registry=registry,
    )

    assert result.status == "tamper_check_failed"
    assert result.diagnostic_readable is True
    assert result.production_closeout_satisfied is False


def test_attestation_without_evidence_or_signature_blocks_production_closeout() -> None:
    registry = load_trust_boundary_registry(REGISTRY_PATH)
    payload = deepcopy(_valid_attestation_payload())
    payload.pop("evidence_ref")
    payload.pop("signature_ref")
    record = deserialize_attestation_record(payload)

    result = evaluate_trust_boundary_attestation(
        boundary_id="runtime_worker",
        attestations=[record],
        registry=registry,
    )

    assert result.status == "evidence_ref_missing"
    assert result.production_closeout_satisfied is False
    assert result.failure_code == "attestation_evidence_ref_missing"


def test_synthetic_attestation_refs_block_production_closeout() -> None:
    registry = load_trust_boundary_registry(REGISTRY_PATH)
    generated = build_required_production_attestations(
        material_refs={},
        product_refs={},
        registry=registry,
    )
    runtime_worker = next(
        record for record in generated if record.trust_boundary_id == "runtime_worker"
    )

    result = evaluate_trust_boundary_attestation(
        boundary_id="runtime_worker",
        attestations=[runtime_worker],
        registry=registry,
    )

    assert result.status == "synthetic_material_ref"
    assert result.production_closeout_satisfied is False
