"""Tests for cross-graph evidence gatherer protocols."""

from __future__ import annotations

from unittest.mock import MagicMock

from polisyos.scientist.cross_graph.protocols import (
    GathererResult,
)


class _StubGatherer:
    @property
    def dimension(self) -> str:
        return "test"

    def assess(self, need, *, concepts, context):
        return GathererResult(
            status="ok",
            confidence=0.8,
            diagnostics=[],
            provenance_refs=[],
            metadata={},
        )


class TestGathererResult:
    def test_creation(self):
        r = GathererResult(
            status="supported",
            confidence=0.9,
            diagnostics=[],
            provenance_refs=["ref1"],
            metadata={"key": "val"},
        )
        assert r.status == "supported"
        assert r.confidence == 0.9
        assert r.provenance_refs == ["ref1"]


class TestEvidenceGathererProtocol:
    def test_stub_satisfies_protocol(self):
        g = _StubGatherer()
        assert g.dimension == "test"
        need = MagicMock()
        result = g.assess(need, concepts=[], context={})
        assert isinstance(result, GathererResult)
        assert result.confidence == 0.8
