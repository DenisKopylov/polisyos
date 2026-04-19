"""Persistent critic knowledge base backed by `FailurePatternIndex`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from polisyos.common.logger import get_logger
from polisyos.core.observability import MetricsRegistry, get_metrics
from polisyos.scientist.agent.failure_index import (
    FailurePatternIndex,
    build_failure_signature,
    normalize_location,
    normalize_message,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.scientist.agent.failure_card import FailureCard
    from polisyos.scientist.agent.protocols import CritiqueReport, ProblemFrame

logger = get_logger(__name__)


def _default_metrics() -> MetricsRegistry:
    return get_metrics()


@dataclass(frozen=True, slots=True)
class KnowledgePattern:
    """Prompt-friendly projection of recurring failure patterns."""

    signature_id: str
    error_code: str
    category: str
    summary: str
    remediation: str
    occurrence_count: int


class CriticKnowledgeBase:
    """Cross-run failure memory for Critic and Drafter shift-left guidance."""

    INDEX_METADATA_KEY = "critic_knowledge_base_ref"

    def __init__(
        self,
        cas: FileSystemCAS,
        *,
        index: FailurePatternIndex | None = None,
        metrics: MetricsRegistry | None = None,
        max_patterns: int = 100,
        gc_max_age_days: int = 30,
        persist_threshold: int = 5,
    ) -> None:
        self._cas = cas
        self._index = index or FailurePatternIndex()
        self._metrics = metrics if metrics is not None else _default_metrics()
        self._max_patterns = max(10, max_patterns)
        self._gc_max_age_days = max(1, gc_max_age_days)
        self._persist_threshold = max(1, persist_threshold)
        self._unsaved_updates = 0
        self._last_artifact_id: str | None = None

    @classmethod
    def load_or_create(
        cls,
        cas: FileSystemCAS,
        artifact_id: str | None,
        **kwargs: Any,
    ) -> CriticKnowledgeBase:
        index = FailurePatternIndex.load_or_create(cas, artifact_id)
        kb = cls(cas, index=index, **kwargs)
        kb._last_artifact_id = artifact_id
        return kb

    def record_critique(self, report: CritiqueReport, problem_frame: ProblemFrame) -> None:
        if report.verdict == "APPROVE":
            return

        domain = str(getattr(problem_frame, "domain", "general") or "general")

        for issue in report.issues:
            if issue.severity.value not in {"warning", "blocker"}:
                continue
            signature_id = build_failure_signature(
                error_code=issue.issue_id,
                category=issue.category.value,
                location=issue.location,
                message=issue.message,
                source_step="critic",
                domain=domain,
            )
            self._index.add_failure(
                signature_id=signature_id,
                error_code=issue.issue_id,
                category=issue.category.value,
                domain=domain,
                source_step="critic",
                normalized_location=normalize_location(issue.location),
                normalized_message=normalize_message(issue.message),
                remediation_advice=issue.suggestion,
                card_ref=report.ir_ref,
            )
        self._mark_dirty()

    def record_failure_card(self, card: FailureCard, *, domain: str) -> None:
        field_path = ""
        if card.violations and card.violations[0].field_path:
            field_path = card.violations[0].field_path
        signature_id = build_failure_signature(
            error_code=card.error_code,
            category=card.source_step.value,
            location=field_path,
            message=card.violation_summary,
            source_step=card.source_step.value,
            domain=domain,
        )
        self._index.add_failure(
            signature_id=signature_id,
            error_code=card.error_code,
            category=card.source_step.value,
            domain=domain,
            source_step=card.source_step.value,
            normalized_location=normalize_location(field_path),
            normalized_message=normalize_message(card.violation_summary),
            remediation_advice=card.remediation_advice,
            card_ref=card.content_hash,
        )
        self._mark_dirty()

    def search_patterns(
        self,
        *,
        domain: str,
        error_code: str = "",
        category: str = "",
        location: str = "",
        message: str = "",
        top_k: int = 5,
        min_occurrence: int = 1,
    ) -> list[tuple[KnowledgePattern, float]]:
        matches = self._index.search(
            domain=domain,
            error_code=error_code,
            category=category,
            location=location,
            message=message,
            top_k=top_k,
            min_occurrence=min_occurrence,
        )
        result: list[tuple[KnowledgePattern, float]] = []
        for entry, score in matches:
            result.append(
                (
                    KnowledgePattern(
                        signature_id=entry.signature_id,
                        error_code=entry.error_code,
                        category=entry.category,
                        summary=entry.normalized_message,
                        remediation=entry.remediation_advice,
                        occurrence_count=entry.occurrence_count,
                    ),
                    score,
                )
            )
        return result

    def get_top_patterns(self, n: int = 10) -> list[KnowledgePattern]:
        patterns: list[KnowledgePattern] = []
        for entry in self._index.top_patterns(n):
            patterns.append(
                KnowledgePattern(
                    signature_id=entry.signature_id,
                    error_code=entry.error_code,
                    category=entry.category,
                    summary=entry.normalized_message,
                    remediation=entry.remediation_advice,
                    occurrence_count=entry.occurrence_count,
                )
            )
        return patterns

    def to_prompt_context(
        self,
        *,
        domain: str,
        max_patterns: int = 3,
        min_occurrence: int = 3,
    ) -> str:
        matches = self.search_patterns(
            domain=domain,
            top_k=max_patterns,
            min_occurrence=min_occurrence,
        )
        if not matches:
            return ""

        lines = [
            "## KNOWN PITFALLS (DO NOT REPEAT)",
            "Use the following recurring failures as negative constraints:",
            "",
        ]
        for idx, (pattern, score) in enumerate(matches, start=1):
            lines.append(
                f"{idx}. [{pattern.error_code}] seen {pattern.occurrence_count}x"
                f" (similarity={score:.2f})"
            )
            lines.append(f"   - Failure: {pattern.summary[:180]}")
            if pattern.remediation:
                lines.append(f"   - Fix: {pattern.remediation[:180]}")
        return "\n".join(lines)

    def garbage_collect(self) -> int:
        removed = int(self._index.garbage_collect(max_age_days=self._gc_max_age_days))
        if len(self._index.entries) > self._max_patterns:
            before = len(self._index.entries)
            self._index.entries = self._index.top_patterns(self._max_patterns)
            removed += max(0, before - len(self._index.entries))
        if removed > 0:
            self.persist()
            self._metrics.record_knowledge_base_gc_removed(removed)
            logger.info("CriticKnowledgeBase GC removed %s stale entries", removed)
        return removed

    def persist(self) -> str:
        artifact_id = str(self._index.persist(self._cas))
        self._last_artifact_id = artifact_id
        self._unsaved_updates = 0
        self._metrics.set_failure_pattern_index_size(self.pattern_count)
        return artifact_id

    def _mark_dirty(self) -> None:
        self._unsaved_updates += 1
        if self._unsaved_updates >= self._persist_threshold:
            self.persist()

    @property
    def pattern_count(self) -> int:
        return len(self._index.entries)

    @property
    def last_artifact_id(self) -> str | None:
        return self._last_artifact_id


__all__ = [
    "CriticKnowledgeBase",
    "KnowledgePattern",
]
