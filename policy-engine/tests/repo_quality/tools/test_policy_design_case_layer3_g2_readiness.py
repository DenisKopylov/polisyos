from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
G2_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g2_causal_forecast.v1"

EXPECTED_ARTIFACT_PATHS = {
    "architecture/policy_design_case/layer3_g2_adapter_admission_registry.json",
    "architecture/policy_design_case/layer3_g2_l2_skg_search_ledgers.json",
    "architecture/policy_design_case/layer3_g2_l2_skg_query_traces.json",
    "architecture/policy_design_case/layer3_g2_l2_skg_index_coverage.json",
    "architecture/policy_design_case/layer3_g2_search_recall_freshness.json",
    "architecture/policy_design_case/layer3_g2_foundry_method_registry_coverage.json",
    "architecture/policy_design_case/layer3_g2_foundry_method_registry_search.json",
    "architecture/policy_design_case/layer3_g2_method_requirement_bindings.json",
    "architecture/policy_design_case/layer3_g2_method_validity_transport.json",
    "architecture/policy_design_case/layer3_g2_semantic_spine_bindings.json",
    "architecture/policy_design_case/layer3_g2_concept_alignment_records.json",
    "architecture/policy_design_case/layer3_g2_s10_prerequisite_bindings.json",
    "architecture/policy_design_case/layer3_g2_forecast_support_bindings.json",
    "architecture/policy_design_case/layer3_g2_grounded_forecast_handoffs.json",
    "architecture/policy_design_case/layer3_g2_observable_calibration_report.json",
    "architecture/policy_design_case/layer3_g2_transport_limit_declarations.json",
    "architecture/policy_design_case/layer3_g2_authority_envelopes.json",
    "architecture/policy_design_case/layer3_g2_conformance_report.json",
    "architecture/policy_design_case/layer3_g2_w12d_consumer_gate.json",
    "architecture/policy_design_case/layer3_g2_causal_forecast_audit_surface.json",
    "architecture/policy_design_case/layer3_g2_health_metric_delta.toml",
    "architecture/policy_design_case/layer3_g2_adapter_contract_registry.toml",
    "architecture/policy_design_case/layer3_g2_readiness_manifest.json",
}

EXPECTED_MANIFEST_KEYS = {
    "schema_version",
    "rule_version",
    "g1_dependency_status",
    "g2_l2_skg_coverage_status",
    "g2_search_ledger_count",
    "g2_skg_query_trace_count",
    "g2_foundry_method_registry_coverage_status",
    "g2_method_requirement_binding_count",
    "g2_method_validity_report_status",
    "g2_semantic_spine_binding_count",
    "g2_s10_prerequisite_binding_status",
    "g2_forecast_support_binding_count",
    "g2_w12d_consumer_gate_status",
    "g2_search_engineering_quality_status",
    "g2_conformance_status",
    "g2_health_metric_ids",
}

REQUIRED_WRITE_PATHS = {
    "architecture/policy_design_case/layer3_g2_method_requirement_bindings.json",
    "architecture/policy_design_case/layer3_g2_semantic_spine_bindings.json",
    "architecture/policy_design_case/layer3_g2_w12d_consumer_gate.json",
    "architecture/policy_design_case/layer3_g2_health_metric_delta.toml",
    "architecture/policy_design_case/layer3_g2_adapter_contract_registry.toml",
    "architecture/policy_design_case/layer3_g2_readiness_manifest.json",
}


def _validator() -> Any:
    return import_module("tools.quality.validation.check_policy_design_case_layer3_g2_readiness")


def test_layer3_g2_readiness_passes_only_for_persisted_runtime_bundle() -> None:
    validation = _validator().validate_layer3_g2_readiness(REPO_ROOT)

    assert validation["status"] == "pass"
    assert validation["summary"]["schema_version"] == G2_SCHEMA_VERSION
    assert validation["summary"]["g1_dependency_status"] == "pass"
    assert validation["summary"]["g2_l2_skg_coverage_status"] == "pass"
    assert validation["summary"]["g2_foundry_method_registry_coverage_status"] == "pass"
    assert validation["summary"]["g2_method_requirement_binding_count"] >= 1
    assert validation["summary"]["g2_semantic_spine_binding_count"] >= 1
    assert validation["summary"]["g2_s10_prerequisite_binding_status"] in {
        "pass",
        "domain_ceiling_not_required",
    }
    assert validation["summary"]["g2_w12d_consumer_gate_status"] == "pass"
    assert validation["summary"]["g2_conformance_status"] == "pass"
    assert validation["summary"]["g2_manifest_runtime_drift_key_count"] == 0
    assert validation["issues"] == []


def test_layer3_g2_readiness_declares_complete_expected_artifact_set() -> None:
    validator = _validator()

    expected_paths = {path.as_posix() for path in validator.EXPECTED_ARTIFACT_PATHS}

    assert expected_paths >= EXPECTED_ARTIFACT_PATHS


def test_layer3_g2_readiness_requires_persisted_artifacts(monkeypatch: Any) -> None:
    validator = _validator()
    missing_path = Path(
        "architecture/policy_design_case/layer3_g2_missing_method_requirement_bindings.json"
    )
    monkeypatch.setattr(validator, "EXPECTED_ARTIFACT_PATHS", (missing_path,))

    validation = validator.validate_layer3_g2_readiness(REPO_ROOT)

    assert validation["status"] == "fail"
    assert validation["artifacts"]["missing_persisted_artifact_paths"] == [
        missing_path.as_posix()
    ]
    assert "layer3_g2_persisted_artifact_missing" in {
        issue["code"] for issue in validation["issues"]
    }


def test_layer3_g2_readiness_manifest_contains_selected_runtime_drift_keys() -> None:
    validation = _validator().validate_layer3_g2_readiness(REPO_ROOT)

    assert set(validation["summary"]) >= EXPECTED_MANIFEST_KEYS
    assert validation["summary"]["schema_version"] == G2_SCHEMA_VERSION
    assert validation["summary"]["g2_manifest_runtime_drift_key_count"] == 0


def test_layer3_g2_write_path_includes_binding_consumer_toml_and_manifest_records(
    monkeypatch: Any,
) -> None:
    validator = _validator()
    expected_paths = tuple(Path(path) for path in sorted(EXPECTED_ARTIFACT_PATHS))
    monkeypatch.setattr(validator, "EXPECTED_ARTIFACT_PATHS", expected_paths)
    monkeypatch.setattr(
        validator,
        "_write_artifacts",
        lambda _repo_root, _bundle: [path.as_posix() for path in expected_paths],
    )

    validation = validator.validate_layer3_g2_readiness(REPO_ROOT, write=True)

    written_paths = set(validation["artifacts"]["written_artifact_paths"])

    assert validation["write"] is True
    assert written_paths >= REQUIRED_WRITE_PATHS
    assert written_paths <= {path.as_posix() for path in validator.EXPECTED_ARTIFACT_PATHS}


def test_layer3_g2_readiness_fails_when_write_path_omits_binding_or_consumer_records(
    monkeypatch: Any,
) -> None:
    validator = _validator()
    expected_paths = tuple(Path(path) for path in sorted(EXPECTED_ARTIFACT_PATHS))
    omitted = Path("architecture/policy_design_case/layer3_g2_w12d_consumer_gate.json")
    monkeypatch.setattr(validator, "EXPECTED_ARTIFACT_PATHS", expected_paths)
    monkeypatch.setattr(
        validator,
        "_write_artifacts",
        lambda _repo_root, _bundle: [
            path.as_posix() for path in expected_paths if path != omitted
        ],
    )

    validation = validator.validate_layer3_g2_readiness(REPO_ROOT, write=True)

    assert validation["status"] == "fail"
    assert "layer3_g2_persisted_artifact_missing" in {
        issue["code"] for issue in validation["issues"]
    }
    assert omitted.as_posix() not in validation["artifacts"]["written_artifact_paths"]


def test_layer3_g2_readiness_reports_method_semantic_and_w12d_issue_codes() -> None:
    issue_codes = set(_validator().ALL_ISSUE_CODES)

    assert {
        "layer3_g2_method_requirement_missing",
        "layer3_g2_method_validity_missing",
        "layer3_g2_semantic_binding_spine_missing",
        "layer3_g2_s10_consumer_bridge_missing",
        "layer3_g2_w12d_not_routed_closeout",
        "layer3_g2_w12d_domain_ceiling_gate_missing",
    } <= issue_codes


def test_layer3_g2_readiness_fails_when_conformance_report_fails(
    monkeypatch: Any,
) -> None:
    validator = _validator()
    runtime_g2 = validator.g2
    bundle = runtime_g2.build_layer3_g2_bundle(REPO_ROOT)
    bad_bundle = bundle.model_copy(
        update={
            "conformance_report": runtime_g2.Layer3G2ConformanceReport(
                record_id="layer3-g2-conformance-report",
                status="fail",
                issue_codes=("layer3_g2_forecast_support_missing",),
            )
        }
    )
    monkeypatch.setattr(runtime_g2, "build_layer3_g2_bundle", lambda _repo_root: bad_bundle)

    validation = validator.validate_layer3_g2_readiness(REPO_ROOT)

    assert validation["status"] == "fail"
    assert validation["summary"]["g2_conformance_status"] == "fail"
    assert "layer3_g2_forecast_support_missing" in {
        issue["code"] for issue in validation["issues"]
    }


@pytest.mark.parametrize(
    ("constant_name", "fixture_text", "expected_code"),
    [
        (
            "GENERATED_ARTIFACTS_TOML_PATH",
            "[generated_artifacts]\nversion = 1\n",
            "layer3_g2_generated_artifacts_family_missing",
        ),
        (
            "REFERENCE_INDEX_PATH",
            "# Reference\n\nNo G2 reference entry here.\n",
            "layer3_g2_reference_index_missing",
        ),
        (
            "PUBLIC_SURFACE_PATH",
            "# Public Surface\n\nNo G2 public forecast tier visibility here.\n",
            "layer3_g2_public_surface_visibility_missing",
        ),
        (
            "ADAPTER_CONTRACT_REGISTRY_PATH",
            "",
            "layer3_g2_adapter_contract_registry_missing",
        ),
    ],
)
def test_layer3_g2_readiness_fails_when_surface_sync_marker_is_missing(
    monkeypatch: Any,
    tmp_path: Path,
    constant_name: str,
    fixture_text: str,
    expected_code: str,
) -> None:
    validator = _validator()
    fixture_path = tmp_path / f"{constant_name}.fixture"
    if fixture_text:
        fixture_path.write_text(fixture_text, encoding="utf-8")
    monkeypatch.setattr(validator, constant_name, fixture_path)

    validation = validator.validate_layer3_g2_readiness(REPO_ROOT)

    assert validation["status"] == "fail"
    assert expected_code in {issue["code"] for issue in validation["issues"]}


def test_layer3_g2_readiness_fails_when_inventory_surface_registration_is_missing(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    validator = _validator()
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text('{"artifacts": []}\n', encoding="utf-8")
    monkeypatch.setattr(validator, "INVENTORY_PATH", inventory_path)

    validation = validator.validate_layer3_g2_readiness(REPO_ROOT)

    assert validation["status"] == "fail"
    assert "layer3_g2_inventory_surface_missing" in {
        issue["code"] for issue in validation["issues"]
    }
