from __future__ import annotations

import pytest
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.claims.models import (
    ClaimLedger,
    ClaimPublishability,
    ClaimRecord,
    ClaimSupportStatus,
    ClaimType,
)
from polisyos.scientist.search.readiness import DecisionReadiness
from pydantic import ValidationError


def _ref(suffix: str = "1") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + suffix * 64,
        kind="scientist.test_evidence",
        media_type="application/json",
    )


def test_claim_record_accepts_supported_publishable_claim() -> None:
    claim = ClaimRecord(
        claim_id="claim_1",
        run_id="run_1",
        claim_type=ClaimType.CAUSAL,
        text="The policy increases the target outcome.",
        support_status=ClaimSupportStatus.SUPPORTED,
        publishability=ClaimPublishability.PUBLISHABLE,
        readiness_level=DecisionReadiness.ANALYST_ADVISORY,
        evidence_refs=[_ref()],
        source_attribution=["causal_effect_report"],
    )

    assert claim.schema_version == "1.0"
    assert claim.readiness_level is DecisionReadiness.ANALYST_ADVISORY


def test_publishable_legal_claim_requires_evidence() -> None:
    with pytest.raises(ValidationError, match="evidence_refs"):
        ClaimRecord(
            claim_id="claim_legal",
            run_id="run_1",
            claim_type=ClaimType.LEGAL,
            text="The intervention has statutory authority.",
            support_status=ClaimSupportStatus.SUPPORTED,
            publishability=ClaimPublishability.PUBLISHABLE,
            readiness_level=DecisionReadiness.EXTERNAL_BRIEFING,
        )


def test_claim_with_unresolved_counterevidence_cannot_be_publishable() -> None:
    with pytest.raises(ValidationError, match="counterevidence"):
        ClaimRecord(
            claim_id="claim_contested",
            run_id="run_1",
            claim_type=ClaimType.FACTUAL,
            text="The metric improved.",
            support_status=ClaimSupportStatus.SUPPORTED,
            publishability=ClaimPublishability.PUBLISHABLE,
            readiness_level=DecisionReadiness.ANALYST_ADVISORY,
            evidence_refs=[_ref("1")],
            counterevidence_refs=[_ref("2")],
        )


def test_claim_ledger_rejects_duplicate_claim_ids() -> None:
    claim = ClaimRecord(
        claim_id="claim_dup",
        run_id="run_1",
        claim_type=ClaimType.FACTUAL,
        text="Metric exists.",
        support_status=ClaimSupportStatus.SUPPORTED,
        publishability=ClaimPublishability.INTERNAL_ONLY,
        readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
        evidence_refs=[_ref()],
    )

    with pytest.raises(ValidationError, match="unique"):
        ClaimLedger(run_id="run_1", claims=[claim, claim])
