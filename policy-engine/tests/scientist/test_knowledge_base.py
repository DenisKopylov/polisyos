from __future__ import annotations

from datetime import UTC, datetime

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.agent.knowledge_base import CriticKnowledgeBase
from polisyos.scientist.agent.protocols import (
    CritiqueCategory,
    CritiqueIssue,
    CritiqueReport,
    CritiqueSeverity,
    ProblemFrame,
)


class _FakeMetrics:
    def __init__(self) -> None:
        self.gc_removed: list[int] = []
        self.pattern_sizes: list[int] = []

    def record_knowledge_base_gc_removed(self, removed: int) -> None:
        self.gc_removed.append(removed)

    def set_failure_pattern_index_size(self, size: int) -> None:
        self.pattern_sizes.append(size)


def _problem_frame(domain: str = "fiscal") -> ProblemFrame:
    return ProblemFrame(
        frame_id="pf_kb_1",
        domain=domain,
        problem_statement="Reduce poverty with strict budget",
        constraints=("Budget <= 1000",),
        goals=("reduce poverty",),
    )


def test_knowledge_base_record_search_and_persist(tmp_path) -> None:
    cas = FileSystemCAS(tmp_path)
    kb = CriticKnowledgeBase(cas, persist_threshold=100)

    report = CritiqueReport(
        report_id="rep_1",
        ir_ref="sha256:" + ("a" * 64),
        problem_frame_ref="pf_kb_1",
        verdict="REJECT",
        issues=[
            CritiqueIssue(
                issue_id="EMPTY_TARGET",
                category=CritiqueCategory.FEASIBILITY,
                severity=CritiqueSeverity.BLOCKER,
                message="Target population is empty",
                location="policy_spec.interventions[0].target",
                suggestion="Broaden selector",
            )
        ],
    )

    kb.record_critique(report, _problem_frame())
    assert kb.pattern_count == 1

    matches = kb.search_patterns(
        domain="fiscal",
        error_code="EMPTY_TARGET",
        category="feasibility",
        location="policy_spec.interventions[9].target",
        message="Target population is empty",
    )
    assert matches
    assert matches[0][0].occurrence_count == 1

    artifact_id = kb.persist()
    assert artifact_id.startswith("sha256:")

    loaded = CriticKnowledgeBase.load_or_create(cas, artifact_id)
    assert loaded.pattern_count == 1


def test_knowledge_base_prompt_context_uses_threshold(tmp_path) -> None:
    cas = FileSystemCAS(tmp_path)
    kb = CriticKnowledgeBase(cas, persist_threshold=100)

    for _ in range(3):
        report = CritiqueReport(
            report_id="rep",
            ir_ref="sha256:" + ("b" * 64),
            problem_frame_ref="pf_kb_1",
            verdict="NEEDS_REVISION",
            issues=[
                CritiqueIssue(
                    issue_id="BUDGET_EXCEEDED",
                    category=CritiqueCategory.FEASIBILITY,
                    severity=CritiqueSeverity.WARNING,
                    message="Estimated spend exceeds budget",
                    location="policy_spec.interventions[0].params.amount",
                    suggestion="Lower amount",
                )
            ],
            created_at=datetime.now(UTC),
        )
        kb.record_critique(report, _problem_frame())

    context = kb.to_prompt_context(domain="fiscal", min_occurrence=3)
    assert "KNOWN PITFALLS" in context
    assert "BUDGET_EXCEEDED" in context


def test_knowledge_base_accepts_injected_metrics(
    monkeypatch,
    tmp_path,
) -> None:
    cas = FileSystemCAS(tmp_path)
    metrics = _FakeMetrics()
    monkeypatch.setattr(
        "polisyos.scientist.agent.knowledge_base._default_metrics",
        lambda: (_ for _ in ()).throw(AssertionError("global metrics should not be used")),
    )
    kb = CriticKnowledgeBase(cas, metrics=metrics, persist_threshold=100)

    report = CritiqueReport(
        report_id="rep_injected",
        ir_ref="sha256:" + ("c" * 64),
        problem_frame_ref="pf_kb_1",
        verdict="REJECT",
        issues=[
            CritiqueIssue(
                issue_id="TARGET_MISSING",
                category=CritiqueCategory.FEASIBILITY,
                severity=CritiqueSeverity.BLOCKER,
                message="Target is missing",
                location="policy_spec.interventions[0].target",
                suggestion="Provide target",
            )
        ],
    )

    kb.record_critique(report, _problem_frame())
    kb.persist()
    removed = kb.garbage_collect()

    assert metrics.pattern_sizes[-1] == 1
    assert removed == 0
    assert metrics.gc_removed == []
