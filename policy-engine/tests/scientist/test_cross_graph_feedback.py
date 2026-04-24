from __future__ import annotations

from polisyos.ir.analytics.cross_graph import (
    CrossGraphEvidenceProfile,
    CrossGraphEvidenceSummary,
    EvidenceNeed,
    EvidenceNeedAssessment,
    EvidenceNeedType,
    EvidenceStatus,
    TransportStatus,
)
from polisyos.ir.analytics.transportability import TransportMode
from polisyos.scientist.cross_graph.feedback import (
    AcademicBenchmarkScenario,
    AcademicBenchmarkSuite,
    BenchmarkCausalEdge,
    BenchmarkScholarQuery,
    build_need_backlog,
    evaluate_benchmark_suite,
)


class _StubScholarGraph:
    def find_causal_evidence(self, cause, effect, *, min_trust=0.5, support_mode="hybrid"):  # type: ignore[no-untyped-def]
        del min_trust, support_mode
        if cause == "tax.policy" and effect == "employment.rate":
            return ["w1", "w2"]
        return []


def _profile() -> CrossGraphEvidenceProfile:
    return CrossGraphEvidenceProfile(
        summary=CrossGraphEvidenceSummary(status="warning", total_needs=2),
        needs=[
            EvidenceNeedAssessment(
                need=EvidenceNeed(
                    need_id="edge_need:tax",
                    need_type=EvidenceNeedType.CAUSAL_EDGE_NEED,
                    source_path="causal_graph.edges[0]",
                    cause="tax.policy",
                    effect="employment.rate",
                ),
                evidence_status=EvidenceStatus.UNSUPPORTED,
                transport_status=TransportStatus.UNSUPPORTED,
                transport_mode=TransportMode.NONE,
                confidence=0.1,
                blocking_reasons=["transport_status=unsupported"],
            ),
            EvidenceNeedAssessment(
                need=EvidenceNeed(
                    need_id="param_need:multiplier",
                    need_type=EvidenceNeedType.PARAMETER_NEED,
                    source_path="params.required_parameters[0]",
                    parameter_name="fiscal_multiplier",
                ),
                evidence_status=EvidenceStatus.MIXED,
                transport_status=TransportStatus.IDENTIFIED,
                transport_mode=TransportMode.TRANSPORT_FORMULA,
                confidence=0.62,
            ),
        ],
    )


def test_build_need_backlog_prioritizes_unsupported_and_transport_sensitive_needs() -> None:
    items = build_need_backlog(_profile())

    assert len(items) == 2
    assert items[0]["need_id"] == "edge_need:tax"
    assert items[0]["priority_weight"] > items[1]["priority_weight"]
    assert "tax.policy" in items[0]["terms"]
    assert "employment.rate" in items[0]["terms"]


def test_evaluate_benchmark_suite_scores_profile_and_scholar_coverage() -> None:
    suite = AcademicBenchmarkSuite(
        scenarios=[
            AcademicBenchmarkScenario(
                scenario_id="fiscal_employment",
                title="Fiscal employment scenario",
                causal_edges=[BenchmarkCausalEdge(cause="tax.policy", effect="employment.rate")],
                parameters=["fiscal_multiplier"],
                scholar_queries=[
                    BenchmarkScholarQuery(
                        cause="tax.policy",
                        effect="employment.rate",
                        min_results=2,
                    )
                ],
            )
        ]
    )

    report = evaluate_benchmark_suite(_profile(), suite, scholar_graph=_StubScholarGraph())

    assert report["summary"]["causal_needs_total"] == 1
    assert report["summary"]["causal_needs_supported"] == 0
    assert report["summary"]["parameter_needs_total"] == 1
    assert report["summary"]["parameter_needs_mixed"] == 1
    assert report["summary"]["governance_blockers_due_to_academic"] == 1
    assert report["summary"]["scholar_query_coverage_ratio"] == 1.0
