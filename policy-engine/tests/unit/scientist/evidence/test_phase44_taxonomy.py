from __future__ import annotations

import importlib
from datetime import date

from polisyos.scientist.evidence.compatibility import (
    SCIENTIST_EVIDENCE_SHIMS,
    shim_metadata_for,
    validate_scientist_evidence_shims,
)


def test_phase44_shim_metadata_is_complete_and_current() -> None:
    assert validate_scientist_evidence_shims(today=date(2026, 5, 5)) == []
    assert {shim.legacy_module for shim in SCIENTIST_EVIDENCE_SHIMS} == {
        "polisyos.scientist.claims",
        "polisyos.scientist.evidence_sources",
        "polisyos.scientist.feedback_utils",
        "polisyos.scientist.provenance",
        "polisyos.scientist.replay_backend",
    }
    assert shim_metadata_for("polisyos.scientist.claims").canonical_module == (
        "polisyos.scientist.evidence.claims"
    )


def test_legacy_pair_shims_point_to_canonical_hubs() -> None:
    pairs = [
        (
            "polisyos.scientist.feedback_utils",
            "polisyos.scientist.feedback.utils",
            "_as_float",
        ),
        (
            "polisyos.scientist.replay_backend",
            "polisyos.scientist.replay.backend",
            "ReplayBackendResult",
        ),
        (
            "polisyos.scientist.evidence_sources",
            "polisyos.scientist.evidence.sources",
            "EvidenceSourcesConfig",
        ),
    ]
    for legacy_name, canonical_name, symbol in pairs:
        legacy = importlib.import_module(legacy_name)
        canonical = importlib.import_module(canonical_name)
        assert getattr(legacy, symbol) is getattr(canonical, symbol)
        assert legacy.__canonical_module__ == canonical_name
        assert legacy.__sunset_date__ == "2026-11-30"


def test_claim_and_provenance_deep_shims_preserve_public_symbols() -> None:
    pairs = [
        (
            "polisyos.scientist.claims.models",
            "polisyos.scientist.evidence.claims.models",
            "ClaimLedger",
        ),
        (
            "polisyos.scientist.claims.ledger",
            "polisyos.scientist.evidence.claims.ledger",
            "persist_claim_ledger",
        ),
        (
            "polisyos.scientist.provenance.run_dag",
            "polisyos.scientist.evidence.provenance.run_dag",
            "RunProvenanceDAG",
        ),
        (
            "polisyos.scientist.provenance.prov_json",
            "polisyos.scientist.evidence.provenance.prov_json",
            "to_prov_json",
        ),
    ]
    for legacy_name, canonical_name, symbol in pairs:
        legacy = importlib.import_module(legacy_name)
        canonical = importlib.import_module(canonical_name)
        assert getattr(legacy, symbol) is getattr(canonical, symbol)
        assert legacy.__canonical_module__ == canonical_name
        assert legacy.__sunset_date__ == "2026-11-30"
