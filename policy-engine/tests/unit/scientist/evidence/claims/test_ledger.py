from __future__ import annotations

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
