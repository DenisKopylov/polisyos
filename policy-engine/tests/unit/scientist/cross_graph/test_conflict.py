"""Tests for evidence conflict detection and resolution."""

from __future__ import annotations

from unittest.mock import MagicMock

from polisyos.scientist.cross_graph.conflict import (
    ConflictDetector,
    ConflictSeverity,
    EvidenceConflict,
    ResolutionStrategy,
)


def _need(need_id: str = "n1") -> MagicMock:
    n = MagicMock()
    n.need_id = need_id
    return n


class TestConflictDetector:
    def test_legal_vs_academic_conflict(self):
        detector = ConflictDetector()
        conflicts = detector.detect(
            _need(),
            {"legal": {"status": "prohibited"}, "academic": {"status": "supported"}},
        )
        assert len(conflicts) == 1
        assert conflicts[0].severity == ConflictSeverity.HIGH

    def test_dataset_vs_academic_conflict(self):
        detector = ConflictDetector()
        conflicts = detector.detect(
            _need(),
            {"dataset": {"status": "missing"}, "academic": {"status": "supported"}},
        )
        assert len(conflicts) == 1
        assert conflicts[0].severity == ConflictSeverity.MEDIUM

    def test_no_conflict(self):
        detector = ConflictDetector()
        conflicts = detector.detect(
            _need(),
            {"legal": {"status": "allowed"}, "academic": {"status": "supported"}},
        )
        assert len(conflicts) == 0

    def test_multiple_conflicts(self):
        detector = ConflictDetector()
        conflicts = detector.detect(
            _need(),
            {
                "legal": {"status": "prohibited"},
                "academic": {"status": "supported"},
                "dataset": {"status": "missing"},
            },
        )
        assert len(conflicts) == 2


class TestConflictResolution:
    def test_escalate_critical(self):
        detector = ConflictDetector()
        conflict = EvidenceConflict(
            need_id="n1",
            dimension="test",
            conflicting_sources=["a", "b"],
            severity=ConflictSeverity.CRITICAL,
            description="test",
        )
        resolution = detector.resolve(conflict)
        assert resolution.strategy == ResolutionStrategy.ESCALATE
        assert resolution.confidence_penalty > 0

    def test_custom_strategy(self):
        detector = ConflictDetector()
        conflict = EvidenceConflict(
            need_id="n1",
            dimension="test",
            conflicting_sources=["a"],
            severity=ConflictSeverity.LOW,
            description="test",
        )
        resolution = detector.resolve(conflict, strategy=ResolutionStrategy.MARK_MIXED)
        assert resolution.strategy == ResolutionStrategy.MARK_MIXED
