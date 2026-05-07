from __future__ import annotations

from polisyos.foundry.methods.catalog import ensure_all_methods_registered
from polisyos.foundry.methods.catalog.snapshot import build_method_catalog_snapshot
from polisyos.scientist.agent.prompts import get_formalizer_prompt


def test_formalizer_prompt_includes_capability_ranked_catalog_summary() -> None:
    ensure_all_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_formalizer_prompt")

    prompt = get_formalizer_prompt(snapshot.model_dump(mode="json"))

    assert "recommended_families" in prompt
    assert "runnable_method_count" in prompt
    assert "mechanism.runtime" in prompt
