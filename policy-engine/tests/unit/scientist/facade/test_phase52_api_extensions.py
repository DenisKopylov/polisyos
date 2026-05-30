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
    import importlib.util

    import polisyos.scientist.evidence.sources as evidence_sources
    import polisyos.scientist.publishing as publishing

    assert evidence_sources.EvidenceSourcesConfig.__name__ == "EvidenceSourcesConfig"
    assert importlib.util.find_spec("polisyos.scientist.evidence_sources") is None
    assert importlib.util.find_spec("polisyos.scientist.publisher") is None
    assert publishing.DecisionGradeExport.__name__ == "DecisionGradeExport"
