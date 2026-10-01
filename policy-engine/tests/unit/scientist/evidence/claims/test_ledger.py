from __future__ import annotations

import pytest

from polisyos.core.artifacts import ArtifactWriteOptions
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.evidence.claims.ledger import (
    CLAIM_LEDGER_KIND,
    _load_claim_ledger,
    _persist_claim_ledger,
)
from polisyos.scientist.evidence.claims.models import (
    ClaimLedger,
    ClaimPublishability,
    ClaimRecord,
    ClaimSupportStatus,
    ClaimType,
)
from polisyos.scientist.methods.search.readiness import DecisionReadiness


def _ref(suffix: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + suffix * 64,
        kind="scientist.evidence",
        media_type="application/json",
    )


def test_claim_ledger_persists_and_loads_from_cas(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    evidence_ref = _ref("1")
    readiness_ref = _ref("2")
    ledger = ClaimLedger(
        run_id="run_ledger",
        claims=[
            ClaimRecord(
                claim_id="claim_1",
                run_id="run_ledger",
                claim_type=ClaimType.FACTUAL,
                text="The report exists.",
                support_status=ClaimSupportStatus.SUPPORTED,
                publishability=ClaimPublishability.INTERNAL_ONLY,
                readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
                evidence_refs=[evidence_ref],
            )
        ],
        decision_readiness_ref=readiness_ref,
        source_artifact_refs=[evidence_ref],
        created_by_node_id="test",
    )

    ref = _persist_claim_ledger(store, ledger)
    loaded = _load_claim_ledger(store, ref)
    manifest = store.get_manifest(ref.artifact_id)

    assert ref.kind == CLAIM_LEDGER_KIND
    assert loaded == ledger
    assert {item.role for item in manifest.inputs} == {
        "decision_readiness",
        "claim_source[0]",
    }


def test_claim_ledger_loader_rejects_removed_selected_manifest_view(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    evidence_ref = _ref("1")
    ledger = ClaimLedger(
        run_id="run_profiled_ledger",
        claims=[
            ClaimRecord(
                claim_id="claim_profiled",
                run_id="run_profiled_ledger",
                claim_type=ClaimType.FACTUAL,
                text="The selected manifest view is required.",
                support_status=ClaimSupportStatus.SUPPORTED,
                publishability=ClaimPublishability.INTERNAL_ONLY,
                readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
                evidence_refs=[evidence_ref],
            )
        ],
        source_artifact_refs=[evidence_ref],
        created_by_node_id="test",
    )
    default_ref = _persist_claim_ledger(store, ledger)
    raw = store.get_bytes(default_ref)
    default_manifest = store.get_manifest(default_ref)
    selected_ref = store.put_bytes(
        raw,
        ArtifactWriteOptions(
            kind=default_ref.kind,
            media_type=default_ref.media_type,
            schema=default_manifest.artifact_schema,
            canon=default_manifest.canon,
            inputs=[],
        ),
    )
    assert selected_ref.artifact_id == default_ref.artifact_id
    assert selected_ref.manifest_profile_sha256 != default_ref.manifest_profile_sha256
    assert _load_claim_ledger(store, selected_ref) == ledger

    absent_profile = next(
        f"sha256:{digit * 64}"
        for digit in "0123456789abcdef"
        if f"sha256:{digit * 64}" not in {
            default_ref.manifest_profile_sha256,
            selected_ref.manifest_profile_sha256,
        }
        and not store.has_manifest_view(
            selected_ref.artifact_id, f"sha256:{digit * 64}"
        )
    )
    assert not store.has_manifest_view(selected_ref.artifact_id, absent_profile)
    missing_view = selected_ref.model_copy(
        update={"manifest_profile_sha256": absent_profile}
    )
    with pytest.raises((KeyError, OSError, ValueError)):
        _load_claim_ledger(store, missing_view)
