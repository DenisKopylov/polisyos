from __future__ import annotations

import importlib
import importlib.util
from datetime import date

import pytest

from polisyos.scientist.evidence.compatibility import (
    SCIENTIST_EVIDENCE_SHIMS,
    shim_metadata_for,
    validate_scientist_evidence_shims,
)


def _find_spec(module_name: str) -> object | None:
    try:
        return importlib.util.find_spec(module_name)
    except ModuleNotFoundError:
        return None


def test_phase44_shim_metadata_is_complete_and_current() -> None:
    assert validate_scientist_evidence_shims(today=date(2026, 5, 5)) == []
    assert SCIENTIST_EVIDENCE_SHIMS == ()
    with pytest.raises(KeyError):
        shim_metadata_for("polisyos.scientist.claims")


def test_removed_single_file_shims_no_longer_import() -> None:
    pairs = [
        "polisyos.scientist.feedback_utils",
        "polisyos.scientist.replay_backend",
        "polisyos.scientist.evidence_sources",
        "polisyos.scientist.provenance",
        "polisyos.scientist.provenance.run_dag",
        "polisyos.scientist.provenance.prov_json",
        "polisyos.scientist.claims",
        "polisyos.scientist.claims.ledger",
        "polisyos.scientist.claims.models",
    ]
    for legacy_name in pairs:
        assert _find_spec(legacy_name) is None
