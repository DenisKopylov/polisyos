from __future__ import annotations

import json
from pathlib import Path

from tools.quality.validation import production_quality_evidence_inventory as inventory

REPO_ROOT = Path(__file__).resolve().parents[3]


def _inventory() -> dict[str, object]:
    return inventory.build_inventory(REPO_ROOT)


def test_inventory_covers_phase01_acceptance_surfaces() -> None:
    payload = _inventory()

    assert payload["schema_version"] == inventory.SCHEMA_VERSION
    assert payload["phase"] == "0.1"
    assert payload["mode"] == "read_only_inventory"
    assert payload["status_model"]["allowed_statuses"] == list(inventory.STATUS_VALUES)

    reports = {
        str(row["id"]): row
        for row in payload["quality_reports"]
    }
    assert set(reports) >= {
        "lex.normative_evidence",
        "fabric.retrieval_trace",
        "foundry.method_report",
        "scientist.policy_grounding_matrix",
        "runtime.semantic_binding_ledger",
        "lex.policy_conflict_check",
        "runtime.performance_summary",
        "ir.metric_taxonomy",
        "llm.provider_preflight",
        "fabric.production_data_context",
        "core.cas_ownership_evidence",
    }

    for report in reports.values():
        assert report["status"] in inventory.STATUS_VALUES
        assert report["expected_ref"]
        assert report["owner_runtime_layer"]
        assert report["producer"]["name"]
        assert report["artifact_fields"]
        assert report["validators"]


def test_inventory_names_first_missing_producer_for_required_serious_refs() -> None:
    payload = _inventory()

    required_refs = {
        str(row["expected_ref"]): row
        for row in payload["serious_profile_required_refs"]
    }
    assert set(required_refs) >= {
        "provider_preflight.json",
        "performance.json",
        "production_data_evidence.json",
        "runtime_quality_ref#normative_applicability_report_ref",
        "runtime_quality_ref#fabric_retrieval_trace_ref",
        "runtime_quality_ref#foundry_method_report_ref",
        "runtime_quality_ref#policy_grounding_matrix_ref",
        "runtime_quality_ref#semantic_binding_ledger_ref",
        "runtime_quality_ref#conflict_check_ref",
        "runtime_quality_ref#provider_model_quality_ledger_ref",
        "quality_evidence/normative_evidence.json",
        "quality_evidence/fabric_retrieval_trace.json",
        "quality_evidence/foundry_method_report.json",
        "quality_evidence/policy_grounding_matrix.json",
        "quality_evidence/semantic_binding_ledger.json",
        "quality_evidence/conflict_check.json",
        "quality_evidence/provider_model_quality_ledger.json",
        "artifacts.json#data_snapshot_ref",
        "artifacts.json#input_bindings_ref",
        "artifacts.json#registry_bundle_ref",
        "artifacts.json#quality_report_ref",
        "artifacts.json#production_data_quality_report_ref",
        "bundle.json#metric_taxonomy",
        "cas_manifest#producer",
    }

    assert payload["summary"]["missing_or_input_required_producers"] == []
    for row in required_refs.values():
        assert "first_missing_producer" in row
        assert row["status"] == "runtime_emitted"
        assert row["first_missing_producer"] is None

    runtime_refs = {
        "runtime_quality_ref#normative_applicability_report_ref",
        "runtime_quality_ref#fabric_retrieval_trace_ref",
        "runtime_quality_ref#foundry_method_report_ref",
        "runtime_quality_ref#policy_grounding_matrix_ref",
        "runtime_quality_ref#semantic_binding_ledger_ref",
        "runtime_quality_ref#conflict_check_ref",
        "runtime_quality_ref#provider_model_quality_ledger_ref",
        "cas_manifest#producer",
    }
    for expected_ref in runtime_refs:
        row = required_refs[expected_ref]
        assert row["status"] == "runtime_emitted"
        assert row["producer"]


def test_inventory_maps_validators_to_runtime_layers_and_expected_refs() -> None:
    payload = _inventory()

    validators = {
        str(row["id"]): row
        for row in payload["validators"]
    }
    expected_layers = {
        "polisyos.lex.normpack.applicability_report.normalize_normative_applicability_report": (
            "lex",
            "quality_evidence/normative_evidence.json",
        ),
        "polisyos.fabric.catalog.source_selection_audit.normalize_fabric_retrieval_trace": (
            "fabric_retrieval",
            "quality_evidence/fabric_retrieval_trace.json",
        ),
        "polisyos.foundry.validation.method_quality.normalize_foundry_method_report": (
            "foundry_methods",
            "quality_evidence/foundry_method_report.json",
        ),
        "polisyos.scientist.validation.policy_grounding.normalize_policy_grounding_matrix": (
            "scientist_policy_artifacts",
            "quality_evidence/policy_grounding_matrix.json",
        ),
        "polisyos.runtime.quality.semantic_binding.evaluate_semantic_binding_ledger": (
            "semantic_binding",
            "quality_evidence/semantic_binding_ledger.json",
        ),
        "polisyos.lex.normpack.conflict_check.normalize_policy_conflict_check_report": (
            "normative_conflict",
            "quality_evidence/conflict_check.json",
        ),
        "polisyos.runtime.quality.scorecard.build_quality_scorecard": (
            "runtime_quality_scorecard",
            "quality_evidence/quality_scorecard.json",
        ),
    }

    for validator_id, (owner_layer, expected_ref) in expected_layers.items():
        assert validators[validator_id]["owner_runtime_layer"] == owner_layer
        assert validators[validator_id]["expected_ref"] == expected_ref

    fields = {
        str(row["field_path"]): row
        for row in payload["quality_artifact_fields"]
    }
    for field_path in (
        "QualityRef.status",
        "QualityRef.report_ref",
        "quality_scorecard.evidence_refs",
        "runtime.semantic_binding_ledger.semantic_binding_ref",
        "production_data_evidence.materialization_refs.quality_report_ref",
        "cas_manifest.producer",
    ):
        assert field_path in fields
        assert fields[field_path]["expected_ref"]


def test_dump_json_is_stable_and_checked_in_baseline_is_current() -> None:
    payload = _inventory()
    dumped = inventory.dump_json(payload)

    round_tripped = json.loads(dumped)
    assert round_tripped["schema_version"] == inventory.SCHEMA_VERSION
    assert round_tripped == payload
    assert "generated_at" not in dumped

    baseline = (
        REPO_ROOT
        / "architecture"
        / "baselines"
        / "production_quality"
        / "evidence_inventory.json"
    )
    assert baseline.read_text(encoding="utf-8") == dumped
    assert inventory.check_artifacts(repo_root=REPO_ROOT) == []


def test_cli_writes_json_output(tmp_path: Path) -> None:
    output = tmp_path / "evidence_inventory.json"

    assert inventory.main(["--json-output", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8")) == _inventory()
