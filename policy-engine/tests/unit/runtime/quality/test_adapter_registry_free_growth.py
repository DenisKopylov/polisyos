"""Behavioral coverage for verified post-G0 adapter-registry growth."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from polisyos.runtime.quality.adapter_contracts import (
    AdapterContractError,
    AdapterSurfacePayload,
    VerifiedAdapterAdmission,
    build_verified_adapter_admission,
    load_adapter_contract_registry,
)
from polisyos.runtime.quality.proving_ground.proof_carrying_analytics_search import (
    build_g3_adapter_contract_registry_status,
)
from tests.unit.runtime.quality.adapter_registry_test_support import (
    NEW_ADAPTER_ID,
    REPO_ROOT,
    mutated_registry,
)


def test_post_g0_registry_admits_new_contract_from_data_only_mutation(tmp_path: Path) -> None:
    """A verified row grows admission without adding its identity to Python source."""

    bare_path = mutated_registry(tmp_path / "bare.toml", include_capability=False)
    bare = build_g3_adapter_contract_registry_status(repo_root=REPO_ROOT, path=bare_path)

    assert bare.status == "fail"
    assert "layer3_g3_adapter_capability_admission_missing" in bare.issue_codes
    assert all(record.get("adapter_id") != NEW_ADAPTER_ID for record in bare.adapter_admission_records)

    verified_path = mutated_registry(tmp_path / "verified.toml", include_capability=True)
    verified = build_g3_adapter_contract_registry_status(
        repo_root=REPO_ROOT,
        path=verified_path,
    )
    admission = next(
        VerifiedAdapterAdmission.model_validate_json(json.dumps(record))
        for record in verified.adapter_admission_records
        if record.get("adapter_id") == NEW_ADAPTER_ID
    )

    assert verified.status == "pass"
    assert verified.adapter_contract_path_count == 7
    assert admission.admission_state == "admitted"
    assert admission.admitted is True
    assert admission.evidence.semantic_preservation_status == "pass"
    assert admission.evidence.checked_field_families
    assert admission.currentness.state == "current"
    assert admission.passport.adapter_id == NEW_ADAPTER_ID
    assert admission.passport.operation_id == "layer3.g3.project_proof_audit_candidate"
    assert admission.passport.operation_kind == "semantic_identity_projection"
    assert admission.passport.consumes_ports == ("layer3.g3.proof_record",)
    assert admission.passport.produces_ports == ("layer3.g3.audit_surface",)

    registry = load_adapter_contract_registry(verified_path)
    with pytest.raises(AdapterContractError) as semantic_loss:
        build_verified_adapter_admission(
            adapter_path=NEW_ADAPTER_ID,
            before=AdapterSurfacePayload(
                surface="layer3.g3.proof_record",
                field_families={"runtime_refs": {"status": "pass"}},
            ),
            after=AdapterSurfacePayload(
                surface="layer3.g3.audit_surface",
                field_families={"runtime_refs": {"status": "fail"}},
            ),
            registry=registry,
        )
    assert semantic_loss.value.code == "hds_adapter_semantic_preservation_failed"

    stale_path = mutated_registry(
        tmp_path / "stale.toml",
        valid_until="2026-08-31T00:00:00+00:00",
    )
    stale = build_g3_adapter_contract_registry_status(repo_root=REPO_ROOT, path=stale_path)
    assert stale.status == "fail"
    assert "layer3_g3_adapter_currentness_invalid" in stale.issue_codes
    assert all(
        record.get("adapter_id") != NEW_ADAPTER_ID
        for record in stale.adapter_admission_records
    )
