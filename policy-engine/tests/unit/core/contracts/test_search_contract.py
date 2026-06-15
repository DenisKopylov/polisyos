from __future__ import annotations

import pytest

from polisyos.core.contracts.search import (
    SEARCH_CONTRACT_SCHEMA_VERSION,
    SearchCandidate,
    SearchLedger,
    SearchRequest,
)


def test_search_contract_requires_executable_replay_and_corpus_snapshot() -> None:
    request = SearchRequest(
        request_id="search-request:g1:credit_access",
        query_text="credit access",
        construct_refs=("construct:credit_access",),
        intent="source_grounding",
        required_layers=("L1",),
        authority_purpose="layer3_g1_construct_grounding_audit",
        allowed_modes=("exact", "lexical"),
        budget={"top_k": 8},
        rule_version="policyos.layer3.g1.substrate_grounding_search.v1",
    )
    candidate = SearchCandidate(
        candidate_ref="dcat-metric-binding://credit_access/dataset/distribution",
        source_layer="L1",
        match_mode="exact",
        score=1.0,
        evidence_refs=("duckdb://dataset_catalog.duckdb#ds_metric_bindings",),
        authority_boundary={"authoritative_for": [], "may_not_use_for": ["claim_authority"]},
        may_not_use_for=("claim_authority",),
    )
    ledger = SearchLedger(
        request_ref=request.request_id,
        query_plan={
            "query_text": request.query_text,
            "query_hash": "sha256:" + "1" * 64,
            "query_expansion_trace_refs": ["concept-alias://credit_access"],
        },
        corpus_ref="duckdb://production_data/dataset_catalog.duckdb#ds_metric_bindings",
        corpus_path="production_data/dataset_catalog.duckdb",
        corpus_snapshot_hash="sha256:" + "2" * 64,
        corpus_kind="canonical",
        configured_store_path="production_data/dataset_catalog.duckdb",
        indexes_used=("duckdb://production_data/dataset_catalog.duckdb#ds_metric_bindings",),
        index_version_refs=("duckdb://production_data/dataset_catalog.duckdb#v1",),
        index_freshness={"status": "pass", "checked_at": "2026-06-12T00:00:00Z"},
        candidates=(candidate,),
        rejected_candidates=(),
        no_hit_frontier=(),
        incompleteness={"status": "complete"},
        replay_key="search-replay:g1:credit_access",
        replay_command=(
            "uv run python tools/quality/validation/check_policy_design_case_layer3_g1_readiness.py "
            "--repo-root . --write"
        ),
        replay_expected_output_hash="sha256:" + "3" * 64,
    )

    assert ledger.schema_version == SEARCH_CONTRACT_SCHEMA_VERSION
    assert ledger.corpus_kind == "canonical"
    assert ledger.candidates[0].match_mode == "exact"


def test_search_ledger_rejects_decorative_replay_key() -> None:
    payload = {
        "request_ref": "search-request:g1:decorative",
        "query_plan": {"query_text": "decorative"},
        "corpus_ref": "duckdb://production_data/dataset_catalog.duckdb",
        "corpus_path": "production_data/dataset_catalog.duckdb",
        "corpus_snapshot_hash": "sha256:" + "4" * 64,
        "corpus_kind": "canonical",
        "indexes_used": ("duckdb://production_data/dataset_catalog.duckdb",),
        "index_version_refs": ("duckdb://production_data/dataset_catalog.duckdb#v1",),
        "candidates": (),
        "rejected_candidates": (),
        "no_hit_frontier": (),
        "incompleteness": {"status": "complete"},
        "replay_key": "decorative-only",
        "replay_command": "",
        "replay_expected_output_hash": "sha256:" + "5" * 64,
    }

    with pytest.raises(ValueError, match="replay_command"):
        SearchLedger.model_validate(payload)
