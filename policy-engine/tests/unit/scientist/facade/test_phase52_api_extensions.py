from __future__ import annotations

import polisyos.scientist as scientist
from polisyos.scientist.extensions import (
    SCIENTIST_GOVERNANCE_PASSES_ENTRY_POINT_GROUP,
    SCIENTIST_NODES_ENTRY_POINT_GROUP,
)


def test_phase52_facade_exports_extension_entrypoints() -> None:
    assert SCIENTIST_GOVERNANCE_PASSES_ENTRY_POINT_GROUP == "polisyos.scientist_governance_passes"
    assert SCIENTIST_NODES_ENTRY_POINT_GROUP == "polisyos.scientist_nodes"
    assert callable(scientist.load_governance_passes)
    assert callable(scientist.build_governance_pipeline)
    assert callable(scientist.discover_scientist_nodes)


def test_phase52_publishing_and_module_shims_have_sunsets() -> None:
    import polisyos.scientist.evidence_sources as evidence_sources
    import polisyos.scientist.publisher as publisher
    import polisyos.scientist.publishing as publishing

    assert evidence_sources.__canonical_module__ == "polisyos.scientist.evidence.sources"
    assert evidence_sources.__sunset_date__ == "2026-11-30"
    assert publisher.__canonical_module__ == "polisyos.scientist.publishing"
    assert publisher.__shim_sunset_date__ == "2026-12-31"
    assert publisher.DecisionGradeExport is publishing.DecisionGradeExport
