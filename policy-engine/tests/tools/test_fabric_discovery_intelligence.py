from __future__ import annotations

from tools.quality.validation import fabric_discovery_intelligence


def test_discovery_intelligence_report_is_phase9_ready() -> None:
    report = fabric_discovery_intelligence.build_report()

    assert report["schema_version"] == fabric_discovery_intelligence.REPORT_SCHEMA_VERSION
    assert report["source_contract_count"] == report["catalog_entry_count"]
    assert report["embedding_model"] == "hashing-bow-dataset-v1"
    assert report["llm_calls"] == 0
    assert fabric_discovery_intelligence.validate_report(report) == []
    assert report["stale_invalidation"]["stale_filtered_by_default"] is True
    assert report["stale_invalidation"]["stale_allowed_only_when_explicit"] is True
    assert report["stale_invalidation"]["refresh_invalidates_source_contract_change"] is True
    assert report["eval"]["meets_thresholds"] is True
    assert report["entity_resolution"]["probabilistic_store"] is True
    assert report["entity_resolution"]["explainable_matches"] is True
    assert report["entity_resolution"]["reversible_candidates"] is True
    assert report["entity_resolution"]["accepted_override_requires_merge_governance"] is True
    assert report["entity_resolution"]["accepted_override_has_provenance"] is True
    assert report["entity_resolution"]["override_audit_index"] is True
    assert report["graph_reasoning"]["origin_trace"] is True


def test_discovery_intelligence_check_main_passes_without_llm_calls() -> None:
    assert fabric_discovery_intelligence.main(["--check"]) == 0


def test_discovery_intelligence_validator_rejects_gaps() -> None:
    report = fabric_discovery_intelligence.build_report()
    report["llm_calls"] = 1
    report["eval"]["meets_thresholds"] = False
    report["graph_reasoning"]["origin_trace"] = False
    report["entity_resolution"]["accepted_override_requires_merge_governance"] = False

    errors = fabric_discovery_intelligence.validate_report(report)

    assert "Phase 9 validator must not call LLMs" in errors
    assert "dataset discovery eval thresholds failed" in errors
    assert "missing graph reasoning helper: origin_trace" in errors
    assert "entity overrides can accept without merge governance" in errors
