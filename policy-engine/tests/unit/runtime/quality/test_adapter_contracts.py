from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from polisyos.core.contracts.capability_discovery import CapabilityDiscoveryRequest
from polisyos.core.contracts.search import SearchRequest
from polisyos.runtime.quality.adapter_contracts import (
    AdapterSurfacePayload,
    VerifiedAdapterAdmission,
    VerifiedAdapterAdmissionProducer,
    load_adapter_contract_registry,
)
from polisyos.runtime.quality.capability_discovery import (
    AdapterCapabilityDiscoveryProvider,
    AdapterCapabilityOwnerReceipt,
    CapabilityProviderSearchResult,
)
from tests.unit.runtime.quality.adapter_registry_test_support import (
    NEW_ADAPTER_ID,
    mutated_registry,
)

_FIELD_FAMILIES = (
    "runtime_refs",
    "final_claims",
    "source_data_context",
    "legal_context",
    "foundry_method_context",
    "scorecard_identity_and_gates",
    "approval_readiness_public_status",
    "mode_and_fallback_records",
)


def _source_payload(surface: str) -> AdapterSurfacePayload:
    fields = {
        "status": "pass",
        "provenance": "runtime_emitted",
        "owner": "team-runtime-quality",
        "schema": "policyos.policy_design_case.layer3_g3_analytics_search.v1",
        "rule_version": "policyos.layer3.g3.analytics_search.v1",
        "lineage": "layer3_g3_deterministic_first_case",
        "tenant": "policy-design-case",
        "time_context": "runtime_snapshot",
        "jurisdiction": "UA",
        "source_family": "ir_analytics",
        "method_expectation": "proof_carrying_analytics",
        "claim_sets": ["g3_default_claim"],
        "rights": "internal_audit_projection",
        "freshness": "current_snapshot",
        "contamination": "none_known",
        "authority_boundary": {
            "authoritative_for": ["g3_projection_audit"],
            "may_not_use_for": ["claim_authority", "publication_authority"],
            "source_authority": "deterministic_producer",
            "posture": "shadow",
            "rule_version_refs": ["policyos.layer3.g3.analytics_search.v1"],
        },
    }
    return AdapterSurfacePayload(
        surface=surface,
        field_families={family: dict(fields) for family in _FIELD_FAMILIES},
    )


def _admitted_discovery(
    registry_path: Path,
    *,
    observed_at: datetime,
) -> tuple[VerifiedAdapterAdmission, CapabilityProviderSearchResult]:
    registry = load_adapter_contract_registry(registry_path)
    contract = registry.adapter_paths[NEW_ADAPTER_ID]
    admission = VerifiedAdapterAdmissionProducer().admit(
        contract=contract,
        before=_source_payload(contract.source_surface),
        registry=registry,
        observed_at=observed_at,
    )
    provider = AdapterCapabilityDiscoveryProvider(admissions=(admission,))
    result = provider.search(
        CapabilityDiscoveryRequest(
            search=SearchRequest(
                request_id="adapter-registry-byte-probe",
                query_text="proof audit projection",
                construct_refs=("construct:proof-carrying-analytics",),
                intent="verify source bytes remain bound through verified discovery",
                required_layers=("L3",),
                authority_purpose=admission.capability_purpose,
                allowed_modes=("exact", "lexical"),
                budget={"top_k": 1},
                rule_version="policyos.dx0.adapter-registry-bytes.v1",
            ),
            resource_kinds=(admission.resource_kind,),
            audience="REVIEWER",
        )
    )
    return admission, result


def test_real_admission_and_discovery_bind_exact_registry_bytes(tmp_path: Path) -> None:
    """A real declaration is producer-verified before its bytes reach discovery."""

    registry_path = mutated_registry(tmp_path / "adapter-registry.toml")
    original_bytes = registry_path.read_bytes()
    observed_at = datetime(2026, 10, 10, 12, tzinfo=UTC)

    original_admission, original_result = _admitted_discovery(
        registry_path,
        observed_at=observed_at,
    )
    expected_original_digest = "sha256:" + hashlib.sha256(original_bytes).hexdigest()
    assert original_admission.evidence.contract_registry_digest == expected_original_digest
    assert original_admission.evidence.semantic_preservation_status == "pass"
    assert original_admission.currentness.state == "current"
    assert original_result.rows
    assert isinstance(original_result.owner_receipt, AdapterCapabilityOwnerReceipt)
    assert (
        original_result.owner_receipt.admission_snapshot_digest
        == original_result.ledger.corpus_snapshot_hash
    )
    assert "adapter_admission_as_execution_authority" in original_result.rows[0].may_not_use_for

    changed_bytes = original_bytes + b"\n# byte-identity probe\n"
    registry_path.write_bytes(changed_bytes)
    changed_admission, changed_result = _admitted_discovery(
        registry_path,
        observed_at=observed_at,
    )

    expected_changed_digest = "sha256:" + hashlib.sha256(changed_bytes).hexdigest()
    assert changed_admission.evidence.contract_registry_digest == expected_changed_digest
    assert changed_admission.capability_ref == original_admission.capability_ref
    assert changed_result.rows[0].capability_ref == original_result.rows[0].capability_ref
    assert changed_result.owner_receipt.admission_snapshot_digest != (
        original_result.owner_receipt.admission_snapshot_digest
    )
    assert changed_result.ledger.corpus_snapshot_hash != original_result.ledger.corpus_snapshot_hash
