"""Tests for provenance tracking in executor."""
from __future__ import annotations

from polisyos.foundry._executor_models import ExecuteArtifacts, FailureCard


class TestProvenanceFields:
    """Verify ExecuteArtifacts carries provenance data."""

    def test_provenance_default_empty(self):
        """ExecuteArtifacts should have empty provenance by default."""
        from unittest.mock import MagicMock

        arts = ExecuteArtifacts(
            state_delta_ref=MagicMock(),
            metrics_ref=MagicMock(),
        )
        assert arts.provenance == {}
        assert arts.failure_cards == ()
        assert arts.is_degraded is False

    def test_provenance_accepts_dict(self):
        from unittest.mock import MagicMock

        prov = {"agents.income": ("ns.tax@1.0", "ns.transfer@1.0")}
        arts = ExecuteArtifacts(
            state_delta_ref=MagicMock(),
            metrics_ref=MagicMock(),
            provenance=prov,
        )
        assert arts.provenance["agents.income"] == ("ns.tax@1.0", "ns.transfer@1.0")

    def test_provenance_multi_writer_same_slot(self):
        from unittest.mock import MagicMock

        prov = {"slot_a": ("method_1@1.0", "method_2@1.0")}
        arts = ExecuteArtifacts(
            state_delta_ref=MagicMock(),
            metrics_ref=MagicMock(),
            provenance=prov,
        )
        assert len(arts.provenance["slot_a"]) == 2
        assert "method_1@1.0" in arts.provenance["slot_a"]
        assert "method_2@1.0" in arts.provenance["slot_a"]
