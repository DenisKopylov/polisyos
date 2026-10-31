from __future__ import annotations

import polisyos.scientist.methods.search as search_mod
from polisyos.scientist.nodes.builtins import decide as decide_mod
from polisyos.scientist.nodes.builtins.decide.build_verified_policy_report import (
    BuildVerifiedPolicyReportCompositionNode,
    BuildVerifiedPolicyReportNode,
)


def test_scientist_public_surface_does_not_export_legacy_shortcuts() -> None:
    assert not hasattr(search_mod, "LegacySearchServiceAdapter")
    assert not hasattr(search_mod, "SearchController")
    assert not hasattr(search_mod, "SearchConfig")
    assert "RunPolicyFunnelLevel5Node" not in getattr(decide_mod, "__all__", [])
    assert "RunPolicyPromotionNode" not in getattr(decide_mod, "__all__", [])


def test_verified_policy_report_versions_resolve_through_decide_facade() -> None:
    assert "BuildVerifiedPolicyReportCompositionNode" in decide_mod.__all__
    assert "BuildVerifiedPolicyReportNode" in decide_mod.__all__
    assert (
        decide_mod.BuildVerifiedPolicyReportCompositionNode
        is BuildVerifiedPolicyReportCompositionNode
    )
    assert decide_mod.BuildVerifiedPolicyReportNode is BuildVerifiedPolicyReportNode
