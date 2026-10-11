from __future__ import annotations

import pickle

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.evidence.claims.models import (
    ClaimLedger,
    ClaimPublishability,
    ClaimRecord,
    ClaimSupportStatus,
    ClaimType,
)
from polisyos.scientist.evidence.decision_readiness import (
    DecisionReadiness as CanonicalDecisionReadiness,
)
from polisyos.scientist.methods.search import readiness as legacy_readiness
from polisyos.scientist.methods.search.readiness import DecisionReadiness


def _ref(suffix: str = "1") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + suffix * 64,
        kind="scientist.test_evidence",
        media_type="application/json",
    )


def test_decision_readiness_keeps_legacy_module_and_pickle_identity() -> None:
    legacy_payload = (
        b"cpolisyos.scientist.methods.search.readiness\n"
        b"DecisionReadiness\n"
        b"p0\n(Vresearch_artifact\np1\ntp2\nRp3\n."
    )
    assert DecisionReadiness is CanonicalDecisionReadiness
    assert DecisionReadiness.__module__ == "polisyos.scientist.methods.search.readiness"
    assert tuple(member.value for member in DecisionReadiness) == (
        "research_artifact",
        "analyst_advisory",
        "external_briefing",
        "simulation_ready",
        "recommendation_ready",
        "deployment_ready",
    )
    for member in DecisionReadiness:
        newly_written_payload = pickle.dumps(member)
        assert b"polisyos.scientist.methods.search.readiness" in newly_written_payload
        assert b"DecisionReadiness" in newly_written_payload
        assert pickle.loads(newly_written_payload) is member  # noqa: S301
    assert pickle.loads(legacy_payload) is DecisionReadiness.RESEARCH_ARTIFACT  # noqa: S301


def test_decision_readiness_pickle_requires_legacy_module_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy_payload = (
        b"cpolisyos.scientist.methods.search.readiness\n"
        b"DecisionReadiness\n"
        b"p0\n(Vresearch_artifact\np1\ntp2\nRp3\n."
    )
    monkeypatch.delattr(legacy_readiness, "DecisionReadiness")

    with pytest.raises(AttributeError):
        pickle.loads(legacy_payload)  # noqa: S301
    for member in CanonicalDecisionReadiness:
        with pytest.raises(pickle.PicklingError):
            pickle.dumps(member)


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
