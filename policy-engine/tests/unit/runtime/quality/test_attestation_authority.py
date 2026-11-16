"""Protected attestation intake must not promote producer declarations."""

from __future__ import annotations

import pytest

from polisyos.runtime.quality.attestation import (
    DIAGNOSTIC_ATTESTATION_SCHEMA_VERSION,
    AttestationRecord,
    build_diagnostic_attestation_record,
    build_verified_attestation_record,
    evaluate_trust_boundary_attestation,
    load_trust_boundary_registry,
)


def test_declared_verification_markers_cannot_appoint_a_production_verifier() -> None:
    registry = load_trust_boundary_registry()
    boundary = registry.require("runtime_worker")
    record = build_verified_attestation_record(
        boundary_id=boundary.boundary_id,
        material_refs={
            key: f"unresolved://material/{key}" for key in boundary.expected_material_kinds
        },
        product_refs={
            key: f"unresolved://product/{key}" for key in boundary.expected_product_kinds
        },
        registry=registry,
    )
    assert record.consumer_verification == "verified"
    assert record.tamper_check_status == "pass"
    assert record.isolation_status == "isolated"
    assert record.signature_ref
    result = evaluate_trust_boundary_attestation(
        boundary_id=boundary.boundary_id, attestations=[record], registry=registry
    )
    assert not result.production_closeout_satisfied
    assert result.status == "not_established"
    assert result.diagnostic_readable


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("consumer_verification", "verified"),
        ("tamper_check_status", "pass"),
        ("isolation_status", "isolated"),
        ("signature_ref", "signature://forged"),
    ],
)
def test_new_diagnostic_format_rejects_verification_claims(field: str, value: str) -> None:
    record = build_diagnostic_attestation_record(boundary_id="runtime_worker")
    assert record.schema_version == DIAGNOSTIC_ATTESTATION_SCHEMA_VERSION
    body = record.model_dump(mode="python")
    body[field] = value
    with pytest.raises(ValueError, match="diagnostic_attestation_cannot_claim_verification"):
        AttestationRecord.model_validate(body)


@pytest.mark.parametrize("kind", ["dev", "research", "governed", "production", "staging"])
def test_fresh_and_legacy_declarations_cannot_pass_serious_scorecard_gates(kind: str) -> None:
    from polisyos.runtime.quality import scorecard

    registry = load_trust_boundary_registry()
    records = [
        build_verified_attestation_record(
            boundary_id=boundary.boundary_id,
            material_refs={key: f"declared://{key}" for key in boundary.expected_material_kinds},
            product_refs={key: f"declared://{key}" for key in boundary.expected_product_kinds},
            registry=registry,
        ).model_dump(mode="json")
        for boundary in registry.boundaries.values()
    ]
    records.extend(
        build_diagnostic_attestation_record(boundary_id=boundary.boundary_id).model_dump(
            mode="json"
        )
        for boundary in registry.boundaries.values()
    )
    gates = scorecard._attestation_gates(
        canary_kind=kind,
        job_payload={"progress": {"details": {"trust_boundary_attestations": records}}},
        run_payload=None,
    )
    if kind in scorecard.SERIOUS_CANARY_KINDS:
        assert {gate["phase"] for gate in gates} == set(registry.boundaries)
        assert all(gate["status"] == "fail" and gate["blocking"] for gate in gates)
        assert all(gate["code"] == "attestation_verifier_not_appointed" for gate in gates)
    else:
        assert gates == []


def test_removing_unappointed_denial_is_detected_with_markers_unchanged(monkeypatch) -> None:
    """The exact assertion goes red if the protected result is promoted again."""
    from dataclasses import replace

    from polisyos.runtime.quality import attestation as owner

    real_result = owner._result

    def removed_denial(*args, **kwargs):
        result = real_result(*args, **kwargs)
        if result.status == "not_established":
            return replace(result, status="verified", production_closeout_satisfied=True)
        return result

    with monkeypatch.context() as removal:
        removal.setattr(owner, "_result", removed_denial)
        with pytest.raises(AssertionError):
            test_declared_verification_markers_cannot_appoint_a_production_verifier()
    test_declared_verification_markers_cannot_appoint_a_production_verifier()


@pytest.mark.parametrize(
    "change", ["wrong_subject", "wrong_issuer", "tampered", "empty", "duplicate"]
)
def test_unappointed_intake_rejects_adversarial_declared_records(change: str) -> None:
    registry = load_trust_boundary_registry()
    boundary = registry.require("runtime_worker")
    record = build_verified_attestation_record(
        boundary_id=boundary.boundary_id,
        material_refs={
            key: f"unresolved://material/{key}" for key in boundary.expected_material_kinds
        },
        product_refs={
            key: f"unresolved://product/{key}" for key in boundary.expected_product_kinds
        },
        registry=registry,
    )
    if change == "wrong_subject":
        record.environment_identity.tenant_id = "other-tenant"
    elif change == "wrong_issuer":
        record.producer_identity.component = "caller.appointed.issuer"
    elif change == "tampered":
        record.observed_materials[0].ref = "unresolved://changed-bytes"
    elif change == "empty":
        record.expected_materials = record.observed_materials = []
        record.expected_products = record.observed_products = []
    else:
        record.expected_materials.append(record.expected_materials[0])
        record.observed_materials.append(record.observed_materials[0])
    result = evaluate_trust_boundary_attestation(
        boundary_id=boundary.boundary_id, attestations=[record], registry=registry
    )
    assert not result.production_closeout_satisfied
