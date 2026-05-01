from __future__ import annotations

import json
from pathlib import Path

from polisyos.fabric.catalog import (
    DatasetDiscoveryBenchmarkPack,
    SemanticDatasetCatalog,
)
from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
from tools.quality.validation.fabric_source_contracts import build_source_contracts


def _catalog() -> SemanticDatasetCatalog:
    return SemanticDatasetCatalog(
        build_source_contracts(),
        profiles=tuple(SourceProfileRegistry.get_instance().list_all()),
    )


def test_dataset_semantic_search_returns_contract_profile_quality_and_access_evidence() -> None:
    catalog = _catalog()

    plan = catalog.resolve("world bank development indicators gdp macro data")

    assert plan.best_candidate is not None
    candidate = plan.best_candidate
    assert candidate.source_contract_id == "worldbank.wdi.generic"
    assert candidate.evidence.source_contract_id == candidate.source_contract_id
    assert candidate.evidence.profile_id == "worldbank_wdi"
    assert candidate.evidence.profile_status == "resolved"
    assert candidate.evidence.quality_contract_ref.startswith("fabric.quality.")
    assert candidate.evidence.access_classification == "public"
    assert candidate.evidence.source_trust_tier == "institutional"
    assert candidate.evidence.vector_metadata.embedding_model == "hashing-bow-dataset-v1"
    assert candidate.evidence.supporting_tokens
    assert plan.plan_steps[0]["llm_calls"] == 0


def test_stale_dataset_vectors_are_not_used_silently() -> None:
    catalog = _catalog()
    source_contract_id = "worldbank.wdi.generic"

    catalog.mark_stale(source_contract_id, "source_contract_snapshot_changed")
    stale_report = catalog.staleness_report()
    assert stale_report.has_stale_entries
    assert source_contract_id in stale_report.stale_entry_ids

    plan = catalog.resolve("world bank development indicators gdp macro data")
    assert all(candidate.source_contract_id != source_contract_id for candidate in plan.candidates)
    assert plan.plan_steps[2]["status"] == "filtered"

    stale_allowed = catalog.resolve(
        "world bank development indicators gdp macro data",
        allow_stale=True,
    )
    assert stale_allowed.best_candidate is not None
    assert stale_allowed.best_candidate.source_contract_id == source_contract_id
    assert stale_allowed.best_candidate.evidence.vector_metadata.stale is True


def test_refresh_invalidates_source_contract_and_profile_changes() -> None:
    contracts = list(build_source_contracts())
    profiles = tuple(SourceProfileRegistry.get_instance().list_all())
    catalog = SemanticDatasetCatalog(contracts, profiles=profiles)
    before = catalog.get_entry("stream.jsonl.generic")
    assert before is not None

    updated_contracts = [
        contract.model_copy(update={"version": "1.1.1"})
        if contract.id == "stream.jsonl.generic"
        else contract
        for contract in contracts
    ]
    changed = catalog.refresh(updated_contracts, profiles=profiles)
    after = catalog.get_entry("stream.jsonl.generic")

    assert "stream.jsonl.generic" in changed
    assert after is not None
    assert before.vector_metadata.fingerprint != after.vector_metadata.fingerprint


def test_nl_to_dataset_resolution_is_ranked_and_explainable() -> None:
    catalog = _catalog()

    plan = catalog.resolve("jsonl event stream messages replay", max_candidates=4)

    assert plan.best_candidate is not None
    assert plan.best_candidate.source_contract_id == "stream.jsonl.generic"
    assert [candidate.rank for candidate in plan.candidates] == list(
        range(1, len(plan.candidates) + 1)
    )
    assert plan.best_candidate.score >= plan.candidates[-1].score
    assert plan.best_candidate.evidence.score_breakdown["combined"] == plan.best_candidate.score
    assert plan.route in {"semantic", "hybrid", "lexical_exact", "lexical_fallback"}


def test_dataset_discovery_eval_pack_tracks_relevance_and_false_positive_budget() -> None:
    payload = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "fabric_discovery_eval.json")
        .read_text("utf-8")
    )
    benchmark = DatasetDiscoveryBenchmarkPack.from_mapping(payload)
    catalog = _catalog()

    report = catalog.evaluate_benchmark(benchmark)

    assert report.passed
    assert benchmark.meets_thresholds(report)
    assert report.false_positive_failures == 0
