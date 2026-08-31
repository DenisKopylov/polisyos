"""Capability discovery through verified post-G0 adapter admission."""

from __future__ import annotations

import json
from pathlib import Path

from polisyos.core.contracts.capability_discovery import CapabilityDiscoveryRequest
from polisyos.core.contracts.search import SearchRequest
from polisyos.runtime.quality.adapter_contracts import VerifiedAdapterAdmission
from polisyos.runtime.quality.capability_discovery import (
    AdapterCapabilityDiscoveryProvider,
    AdapterCapabilityOwnerReceipt,
    CapabilityProviderSearchResult,
)
from polisyos.runtime.quality.proving_ground.proof_carrying_analytics_search import (
    build_g3_adapter_contract_registry_status,
)
from tests.unit.runtime.quality.adapter_registry_test_support import (
    NEW_ADAPTER_ID,
    REPO_ROOT,
    mutated_registry,
)


def test_admitted_adapter_emits_typed_capability_kind_purpose_passport_evidence_and_currentness(
    tmp_path: Path,
) -> None:
    """Discovery consumes verified artifacts, never admission flags or tuple membership."""

    registry_path = mutated_registry(tmp_path / "verified.toml")
    status = build_g3_adapter_contract_registry_status(
        repo_root=REPO_ROOT,
        path=registry_path,
    )
    admission = next(
        VerifiedAdapterAdmission.model_validate_json(json.dumps(record))
        for record in status.adapter_admission_records
        if record.get("adapter_id") == NEW_ADAPTER_ID
    )
    provider = AdapterCapabilityDiscoveryProvider(admissions=(admission,))

    result = provider.search(_request(authority_purpose=admission.capability_purpose))

    assert result.resource_kind == "method"
    assert result.rows[0].resource_kind == "method"
    assert result.rows[0].capability_ref == admission.capability_ref
    assert result.rows[0].content_digest == admission.passport.content_digest
    assert isinstance(result.owner_receipt, AdapterCapabilityOwnerReceipt)
    assert result.owner_receipt.capability_purposes == (admission.capability_purpose,)
    assert admission.passport_ref in result.owner_receipt.passport_refs
    assert admission.evidence_ref in result.owner_receipt.evidence_receipt_refs
    assert admission.currentness_ref in result.owner_receipt.currentness_receipt_refs
    assert result.owner_receipt.search_snapshot_digest == result.ledger.corpus_snapshot_hash
    assert admission.passport_ref in result.rows[0].provenance_refs
    assert admission.evidence_ref in result.rows[0].provenance_refs
    assert admission.currentness_ref == result.rows[0].freshness_ref
    assert "adapter_admission_as_execution_authority" in result.rows[0].may_not_use_for

    replayed = CapabilityProviderSearchResult.model_validate_json(result.model_dump_json())
    assert isinstance(replayed.owner_receipt, AdapterCapabilityOwnerReceipt)
    assert replayed == result

    wrong_purpose = provider.search(_request(authority_purpose="publish_capability"))

    assert wrong_purpose.rows == ()
    assert wrong_purpose.ledger.candidates == ()
    assert wrong_purpose.ledger.rejected_candidates[0].candidate_ref == admission.capability_ref
    assert wrong_purpose.ledger.rejected_candidates[0].limitation_refs == (
        "adapter_capability_purpose_mismatch",
    )


def _request(*, authority_purpose: str) -> CapabilityDiscoveryRequest:
    return CapabilityDiscoveryRequest(
        search=SearchRequest(
            request_id=f"adapter-discovery:{authority_purpose}",
            query_text="proof audit projection",
            construct_refs=("construct:proof-carrying-analytics",),
            intent="discover a verified adapter-produced method capability",
            required_layers=("L3",),
            authority_purpose=authority_purpose,
            allowed_modes=("exact", "lexical"),
            budget={"top_k": 5},
            rule_version="policyos.ds10.adapter-discovery-test.v1",
        ),
        resource_kinds=("method",),
        audience="REVIEWER",
    )
