"""Tests for TrialDeduplicator."""

from __future__ import annotations

from polisyos.scientist.methods.autotune.dedup import TrialDeduplicator, TrialFingerprint
from polisyos.scientist.methods.autotune.models import MutationArtifact


def _candidate(loop_id: str = "loop1", **extra: str) -> MutationArtifact:
    return MutationArtifact(loop_id=loop_id, **extra)


class TestTrialDeduplicator:
    def test_unique_candidates(self):
        dedup = TrialDeduplicator()
        c1 = _candidate("loop1")
        c2 = _candidate("loop2")
        dedup.register(c1, "loop")
        assert dedup.is_duplicate(c1, "loop") is True
        assert dedup.is_duplicate(c2, "loop") is False

    def test_duplicate_detected(self):
        dedup = TrialDeduplicator()
        c = _candidate("loop1")
        assert dedup.is_duplicate(c, "loop") is False
        dedup.register(c, "loop")
        assert dedup.is_duplicate(c, "loop") is True

    def test_deterministic_fingerprint(self):
        dedup = TrialDeduplicator()
        c = _candidate("loop1")
        fp1 = dedup.fingerprint(c)
        fp2 = dedup.fingerprint(c)
        assert fp1 == fp2

    def test_different_loop_ids(self):
        dedup = TrialDeduplicator()
        c = _candidate("loop1")
        dedup.register(c, "loop_a")
        assert dedup.is_duplicate(c, "loop_a") is True
        assert dedup.is_duplicate(c, "loop_b") is False

    def test_dict_candidate(self):
        dedup = TrialDeduplicator()
        c = {"loop_id": "loop1", "artifact_version": "1.0", "search_space_version": "1.0"}
        dedup.register(c, "loop")
        assert dedup.is_duplicate(c, "loop") is True

    def test_count(self):
        dedup = TrialDeduplicator()
        dedup.register(_candidate("a"), "loop")
        dedup.register(_candidate("b"), "loop")
        assert dedup.count("loop") == 2

    def test_reset(self):
        dedup = TrialDeduplicator()
        dedup.register(_candidate("a"), "loop")
        dedup.reset("loop")
        assert dedup.count("loop") == 0

    def test_register_returns_fingerprint(self):
        dedup = TrialDeduplicator()
        fp = dedup.register(_candidate("a"), "loop")
        assert isinstance(fp, TrialFingerprint)
        assert fp.loop_id == "loop"
        assert len(fp.digest) == 16
