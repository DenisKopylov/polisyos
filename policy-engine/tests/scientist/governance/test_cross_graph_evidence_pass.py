from __future__ import annotations

from polisyos.core.governance.passes.base import IssueSeverity
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.ir.analytics.cross_graph import (
    CrossGraphDiagnostic,
    CrossGraphEvidenceProfile,
    CrossGraphEvidenceSummary,
    EvidenceSourceKind,
    EvidenceSourceState,
    EvidenceSourceStatus,
    EvidenceNeed,
    EvidenceNeedAssessment,
    EvidenceNeedType,
    EvidenceStatus,
    LegalStatus,
    ObservabilityStatus,
    TransportStatus,
)
from polisyos.ir.analytics.transportability import TransportMode
from polisyos.scientist.governance.passes.cross_graph_evidence_pass import (
    CrossGraphEvidencePass,
)


def _make_need(need_id: str = "need_1") -> EvidenceNeed:
    return EvidenceNeed(
        need_id=need_id,
        need_type=EvidenceNeedType.OBJECTIVE_METRIC,
    )


def _make_assessment(
    *,
    need_id: str = "need_1",
    legal_status: LegalStatus = LegalStatus.ALLOWED,
    observability_status: ObservabilityStatus = ObservabilityStatus.DIRECT,
    evidence_status: EvidenceStatus = EvidenceStatus.SUPPORTED,
    transport_status: TransportStatus = TransportStatus.IDENTIFIED,
    transport_mode: TransportMode = TransportMode.DIRECT,
    requires_expert_review: bool = False,
) -> EvidenceNeedAssessment:
    return EvidenceNeedAssessment(
        need=_make_need(need_id),
        legal_status=legal_status,
        observability_status=observability_status,
        evidence_status=evidence_status,
        transport_status=transport_status,
        transport_mode=transport_mode,
        requires_expert_review=requires_expert_review,
    )


def _make_profile(
    needs: list[EvidenceNeedAssessment] | None = None,
    diagnostics: list[CrossGraphDiagnostic] | None = None,
    source_statuses: dict[str, EvidenceSourceStatus] | None = None,
) -> CrossGraphEvidenceProfile:
    return CrossGraphEvidenceProfile(
        summary=CrossGraphEvidenceSummary(),
        needs=needs or [],
        diagnostics=diagnostics or [],
        source_statuses=source_statuses or {},
    )


class TestCrossGraphEvidencePass:
    def test_fast_profile_skips(self, pass_context_factory, fast_profile):
        ctx = pass_context_factory(
            state={"cross_graph_evidence_profile": _make_profile()},
            profile=fast_profile,
        )
        issues = CrossGraphEvidencePass().validate(ctx)
        assert issues == []

    def test_no_profile_not_expected_no_issues(self, pass_context_factory, strict_profile):
        ctx = pass_context_factory(
            state={},
            profile=strict_profile,
        )
        issues = CrossGraphEvidencePass().validate(ctx)
        assert issues == []

    def test_no_profile_expected_strict_blocker(self, pass_context_factory, strict_profile):
        ctx = pass_context_factory(
            state={"cross_graph_evidence_expected": True},
            profile=strict_profile,
        )
        issues = CrossGraphEvidencePass().validate(ctx)
        assert len(issues) == 1
        assert issues[0].code == "CROSS_GRAPH_PROFILE_MISSING"
        assert issues[0].severity is IssueSeverity.BLOCKER

    def test_no_profile_expected_mvp_warning(self, pass_context_factory, mvp_profile):
        ctx = pass_context_factory(
            state={"cross_graph_evidence_expected": True},
            profile=mvp_profile,
        )
        issues = CrossGraphEvidencePass().validate(ctx)
        assert len(issues) == 1
        assert issues[0].code == "CROSS_GRAPH_PROFILE_MISSING"
        assert issues[0].severity is IssueSeverity.WARNING

    def test_prohibited_legal_status(self, pass_context_factory, strict_profile):
        profile = _make_profile(
            needs=[_make_assessment(legal_status=LegalStatus.PROHIBITED)]
        )
        ctx = pass_context_factory(
            state={"cross_graph_evidence_profile": profile},
            profile=strict_profile,
        )
        issues = CrossGraphEvidencePass().validate(ctx)
        codes = {i.code for i in issues}
        assert "CROSS_GRAPH_LEGAL_PROHIBITED" in codes

    def test_unsupported_transport(self, pass_context_factory, strict_profile):
        profile = _make_profile(
            needs=[_make_assessment(transport_status=TransportStatus.UNSUPPORTED)]
        )
        ctx = pass_context_factory(
            state={"cross_graph_evidence_profile": profile},
            profile=strict_profile,
        )
        issues = CrossGraphEvidencePass().validate(ctx)
        codes = {i.code for i in issues}
        assert "CROSS_GRAPH_TRANSPORT_REVIEW_REQUIRED" in codes

    def test_missing_observability(self, pass_context_factory, strict_profile):
        profile = _make_profile(
            needs=[_make_assessment(observability_status=ObservabilityStatus.MISSING)]
        )
        ctx = pass_context_factory(
            state={"cross_graph_evidence_profile": profile},
            profile=strict_profile,
        )
        issues = CrossGraphEvidencePass().validate(ctx)
        codes = {i.code for i in issues}
        assert "CROSS_GRAPH_DATA_MISSING" in codes

    def test_unsupported_evidence(self, pass_context_factory, strict_profile):
        profile = _make_profile(
            needs=[_make_assessment(evidence_status=EvidenceStatus.UNSUPPORTED)]
        )
        ctx = pass_context_factory(
            state={"cross_graph_evidence_profile": profile},
            profile=strict_profile,
        )
        issues = CrossGraphEvidencePass().validate(ctx)
        codes = {i.code for i in issues}
        assert "CROSS_GRAPH_EVIDENCE_UNSUPPORTED" in codes

    def test_all_checks_passing(self, pass_context_factory, strict_profile):
        profile = _make_profile(
            needs=[_make_assessment()],
        )
        ctx = pass_context_factory(
            state={"cross_graph_evidence_profile": profile},
            profile=strict_profile,
        )
        issues = CrossGraphEvidencePass().validate(ctx)
        assert issues == []

    def test_degraded_profile_is_not_treated_as_missing(self, pass_context_factory, strict_profile):
        profile = _make_profile(
            needs=[_make_assessment(observability_status=ObservabilityStatus.UNKNOWN)],
            source_statuses={
                "datasets": EvidenceSourceStatus(
                    source=EvidenceSourceKind.DATASETS,
                    configured=False,
                    status=EvidenceSourceState.MISSING_CONFIG,
                )
            },
        )
        ctx = pass_context_factory(
            state={
                "cross_graph_evidence_expected": True,
                "cross_graph_evidence_profile": profile,
            },
            profile=strict_profile,
        )

        issues = CrossGraphEvidencePass().validate(ctx)

        codes = {issue.code for issue in issues}
        assert "CROSS_GRAPH_PROFILE_MISSING" not in codes
        assert "CROSS_GRAPH_SOURCE_UNAVAILABLE" in codes

    def test_source_unavailable_is_warning_outside_strict(self, pass_context_factory, mvp_profile):
        profile = _make_profile(
            needs=[_make_assessment(observability_status=ObservabilityStatus.UNKNOWN)],
            source_statuses={
                "datasets": EvidenceSourceStatus(
                    source=EvidenceSourceKind.DATASETS,
                    configured=False,
                    status=EvidenceSourceState.MISSING_CONFIG,
                )
            },
        )
        ctx = pass_context_factory(
            state={"cross_graph_evidence_profile": profile},
            profile=mvp_profile,
        )

        issues = CrossGraphEvidencePass().validate(ctx)

        issue = next(issue for issue in issues if issue.code == "CROSS_GRAPH_SOURCE_UNAVAILABLE")
        assert issue.severity is IssueSeverity.WARNING
