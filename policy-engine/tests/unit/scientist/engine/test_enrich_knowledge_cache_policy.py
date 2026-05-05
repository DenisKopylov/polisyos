from __future__ import annotations

from polisyos.scientist.engine.executor import _CACHE_DISABLED_NODE_IDS


def test_enrich_knowledge_node_cache_is_disabled() -> None:
    assert "scientist.node_enrich_knowledge@1.1.0" in _CACHE_DISABLED_NODE_IDS
