from __future__ import annotations

import polisyos.scientist.search as search_mod
from polisyos.scientist.nodes.builtins import decide as decide_mod


def test_scientist_public_surface_does_not_export_legacy_shortcuts() -> None:
    assert not hasattr(search_mod, "LegacySearchServiceAdapter")
    assert not hasattr(search_mod, "SearchController")
    assert not hasattr(search_mod, "SearchConfig")
    assert "RunPolicyFunnelLevel5Node" not in getattr(decide_mod, "__all__", [])
    assert "RunPolicyPromotionNode" not in getattr(decide_mod, "__all__", [])
