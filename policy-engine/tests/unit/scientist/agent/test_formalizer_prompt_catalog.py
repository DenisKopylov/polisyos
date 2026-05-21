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
    assert "Only agents.* targets are executable" in prompt
    assert "FULL METHOD CATALOG SNAPSHOT" not in prompt
    assert "TRINITYBUNDLE SCHEMA" not in prompt


def test_formalizer_prompt_lists_executable_metric_registry_ids() -> None:
    prompt = get_formalizer_prompt()

    assert "AVAILABLE METRICS" in prompt
    assert "avg_income" in prompt
    assert "sme_survival_rate" in prompt
    assert "employment_retention_rate" in prompt
    assert 'never\n   prefix them with "params."' in prompt


def test_formalizer_prompt_stays_bounded_with_full_catalog_snapshot() -> None:
    ensure_all_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_formalizer_prompt_size")

    prompt = get_formalizer_prompt(snapshot.model_dump(mode="json"))

    assert len(prompt) < 80_000
