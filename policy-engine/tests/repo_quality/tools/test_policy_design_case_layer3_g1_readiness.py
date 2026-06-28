from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = REPO_ROOT / "tests/fixtures/layer3/g1"
EXPECTED_HEALTH_METRICS = {
    "envelope-expansion-rate",
    "adapter-semantic-loss",
    "governance-throughput",
    "demand-pull-vs-abstention",
    "search-recall@known-seeds+index-staleness",
}
EXPECTED_MAY_NOT_USE_FOR = {
    "claim_authority",
    "causal_effect",
    "policy_recommendation",
    "publishability",
    "adapter_promotion",
    "useful_design_credit",
    "production_authority",
    "search_hit_as_authority",
}


def _g1() -> Any:
    return import_module("polisyos.runtime.quality.proving_ground.substrate_grounding_search")


def _validator() -> Any:
    return import_module("tools.quality.validation.check_policy_design_case_layer3_g1_readiness")


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _dump(payload: Any) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump(mode="json")
    return dict(payload)


def _issue_codes(report: Any) -> set[str]:
    payload = _dump(report)
    return {str(issue["code"]) for issue in payload.get("issues", [])}


def _assert_fixture_fails(name: str) -> Any:
    fixture = _fixture(name)
    expected_codes = set(fixture["expected_issue_codes"])
    assert expected_codes, f"{name} must declare expected issue codes"

    report = _g1().validate_layer3_g1_bundle(REPO_ROOT, fixture["payload"])

    assert _dump(report)["status"] == "fail"
    assert expected_codes <= _issue_codes(report)
    return report


def test_layer3_g1_readiness_passes_with_persisted_runtime_bundle() -> None:
    validation = _validator().validate_layer3_g1_readiness(REPO_ROOT)

    assert validation["status"] == "pass"
    assert validation["summary"]["schema_version"].endswith("layer3_g1_substrate_grounding.v1")
    assert validation["summary"]["g0_v2_dependency_status"] == "pass"
    assert validation["summary"]["g1_substrate_search_ledger_count"] >= 1
    assert validation["summary"]["source_contract_snapshot_count"] >= validation["summary"][
        "grounded_or_uncertain_construct_count"
    ]
    assert validation["summary"]["useful_design_credit_count"] == 0
    assert validation["summary"]["production_claim_authority_count"] == 0


def test_layer3_g1_readiness_requires_persisted_artifacts(monkeypatch: Any) -> None:
    validator = _validator()
    missing_path = Path("architecture/policy_design_case/layer3_g1_missing_probe.json")
    monkeypatch.setattr(validator, "EXPECTED_ARTIFACT_PATHS", (missing_path,))

    validation = validator.validate_layer3_g1_readiness(REPO_ROOT)

    assert validation["status"] == "fail"
    assert validation["artifacts"]["missing_persisted_artifact_paths"] == [
        missing_path.as_posix()
    ]
    assert "layer3_g1_persisted_artifact_missing" in {
        issue["code"] for issue in validation["issues"]
    }


def test_layer3_g1_validator_fails_manifest_runtime_drift() -> None:
    _assert_fixture_fails("manifest_runtime_drift.json")


def test_layer3_g1_validator_detects_persisted_manifest_count_drift(
    tmp_path: Path,
) -> None:
    validator = _validator()
    bundle = _g1().build_layer3_g1_bundle(REPO_ROOT)
    manifest_path = tmp_path / validator.READINESS_MANIFEST_PATH
    manifest_path.parent.mkdir(parents=True)
    persisted = bundle.readiness_manifest.model_dump(mode="json")
    persisted["counts"]["g1_substrate_search_ledger_count"] += 1
    manifest_path.write_text(json.dumps(persisted), encoding="utf-8")

    issues = validator._validate_manifest_runtime_drift(tmp_path, bundle)

    assert "layer3_g1_manifest_runtime_drift" in {
        issue["code"] for issue in issues
    }


def test_layer3_g1_surface_registered_for_expert_and_machine() -> None:
    validation = _validator().validate_layer3_g1_readiness(REPO_ROOT)

    assert validation["status"] == "pass"
    assert validation["summary"]["surface_id"] == "layer3_g1_substrate_grounding_audit_surface"
    assert set(validation["summary"]["surface_audiences"]) == {"EXPERT", "MACHINE"}
    assert set(validation["summary"]["surface_out_of_scope_audiences"]) == {
        "PUBLIC",
        "REVIEWER",
    }


def test_layer3_g1_validator_blocks_claim_authority_or_useful_design_leak() -> None:
    payload = {
        "schema_version": "policyos.policy_design_case.layer3_g1_substrate_grounding.v1",
        "rule_version": "policyos.layer3.g1.substrate_grounding_search.v1",
        "readiness_manifest": {
            "grounding_closure_outcome": "grounded_or_uncertain",
            "counts": {
                "production_claim_authority_count": 1,
                "useful_design_credit_count": 1,
            },
        },
        "grounded_source_contracts": {
            "bindings": [
                {
                    "binding_id": "g1-binding:authority-leak",
                    "construct_ref": "firm_survival",
                    "grounding_status": "grounded_binding",
                    "authoritative_for": ["claim_authority"],
                    "may_not_use_for": sorted(EXPECTED_MAY_NOT_USE_FOR - {"claim_authority"}),
                }
            ]
        },
    }

    report = _g1().validate_layer3_g1_bundle(REPO_ROOT, payload)

    assert _dump(report)["status"] == "fail"
    assert {
        "layer3_g1_claim_authority_leak",
        "layer3_g1_useful_design_credit_leak",
    } <= _issue_codes(report)


def test_layer3_g1_validator_requires_g0_v2_dependency_artifacts() -> None:
    _assert_fixture_fails("stale_or_missing_g0_v2_dependency_artifact.json")


def test_layer3_g1_validator_fails_search_ledger_authority_leak() -> None:
    payload = {
        "schema_version": "policyos.policy_design_case.layer3_g1_substrate_grounding.v1",
        "rule_version": "policyos.layer3.g1.substrate_grounding_search.v1",
        "search_ledgers": [
            {
                "ledger_id": "g1-ledger:authority-leak",
                "event_type": "selected_candidate",
                "request_ref": "g1-request:firm-survival",
                "searched_index_refs": [
                    "duckdb://production_data/datasets_full_phase3full_20260327_183054/"
                    "dataset_catalog.duckdb#ds_metric_bindings"
                ],
                "replay_key": "g1-ledger:authority-leak:replay",
                "authoritative_for": ["layer3_g1_construct_grounding_audit"],
                "may_not_use_for": sorted(EXPECTED_MAY_NOT_USE_FOR),
            }
        ],
    }

    report = _g1().validate_layer3_g1_bundle(REPO_ROOT, payload)

    assert _dump(report)["status"] == "fail"
    assert "layer3_g1_search_ledger_authority_boundary_leak" in _issue_codes(report)


def test_layer3_g1_validator_blocks_domain_ceiling_on_recall_or_freshness_failure() -> None:
    recall_report = _assert_fixture_fails("search_recall_seed_miss_domain_ceiling.json")
    stale_report = _assert_fixture_fails("stale_index_domain_ceiling.json")

    assert "layer3_g1_search_recall_seed_miss_blocks_domain_ceiling" in _issue_codes(
        recall_report
    )
    assert "layer3_g1_stale_index_blocks_domain_ceiling" in _issue_codes(stale_report)


def test_layer3_g1_validator_blocks_hardcoded_fallback_closure() -> None:
    _assert_fixture_fails("hardcoded_construct_fallback_used_for_closure.json")


def test_layer3_g1_validator_blocks_hardcoded_fallback_not_deleted() -> None:
    _assert_fixture_fails("hardcoded_fallback_not_deleted.json")


def test_layer3_g1_validator_requires_free_growth_and_mechanism_generality() -> None:
    single_shape_report = _assert_fixture_fails("mechanism_generality_single_request.json")
    free_growth_report = _g1().build_g1_free_growth_report(REPO_ROOT)

    assert "layer3_g1_mechanism_generality_single_request" in _issue_codes(
        single_shape_report
    )
    assert _dump(free_growth_report)["status"] == "pass"
    assert _dump(free_growth_report)["free_growth_fixture_count"] == 0


def test_layer3_g1_validator_requires_l1_l5_l6_index_coverage() -> None:
    _assert_fixture_fails("l1_l5_l6_index_coverage_missing.json")


def test_layer3_g1_validator_rejects_capability_index_as_l1_search() -> None:
    _assert_fixture_fails("capability_index_used_as_l1_search.json")


def test_layer3_g1_validator_rejects_unjustified_l1_surrogate() -> None:
    _assert_fixture_fails("unjustified_l1_surrogate.json")


def test_layer3_g1_validator_requires_all_five_health_metric_deltas() -> None:
    recorded_metric_ids = {"envelope-expansion-rate", "adapter-semantic-loss"}
    assert EXPECTED_HEALTH_METRICS - recorded_metric_ids
    payload = {
        "schema_version": "policyos.policy_design_case.layer3_g1_substrate_grounding.v1",
        "rule_version": "policyos.layer3.g1.substrate_grounding_search.v1",
        "health_metric_delta": {
            "metric_ids": sorted(recorded_metric_ids)
        },
    }

    report = _g1().validate_layer3_g1_bundle(REPO_ROOT, payload)

    assert _dump(report)["status"] == "fail"
    assert "layer3_g1_surface_unsynced" in _issue_codes(report)


def test_layer3_g1_validator_requires_search_engineering_quality() -> None:
    _assert_fixture_fails("search_engineering_quality_unindexed_scan.json")
