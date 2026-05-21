from __future__ import annotations

import importlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tools.ops_runners.runtime import canary_matrix

REPO_ROOT = Path(__file__).resolve().parents[3]
LEDGER_MODULE_PATH = (
    REPO_ROOT / "tools" / "ops_runners" / "runtime" / "provider_quality_ledger.py"
)


def _ledger_module():
    if not LEDGER_MODULE_PATH.is_file():
        pytest.fail("Phase 5.8 requires tools/ops_runners/runtime/provider_quality_ledger.py")
    return importlib.import_module("tools.ops_runners.runtime.provider_quality_ledger")


def _write_lane_bundle(
    root: Path,
    *,
    lane_id: str,
    provider: str,
    model_id: str,
    model_fingerprint: str,
    lane_kind: str,
    scenario_pack_id: str = "public_golden_pack",
    schema_valid: bool = True,
    selected_variant_quality: float = 0.91,
) -> Path:
    bundle_dir = root / lane_id
    quality_dir = bundle_dir / "quality_evidence"
    quality_dir.mkdir(parents=True)
    (bundle_dir / "bundle.json").write_text(
        json.dumps(
            {
                "schema_version": "policyos.canary_evidence.v1",
                "canary_kind": "production",
                "command": {"matrix_lane_id": lane_id},
                "files": {
                    "quality_evidence": {
                        "provider_model_quality_observations": (
                            "quality_evidence/provider_model_quality_observations.json"
                        )
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (quality_dir / "provider_model_quality_observations.json").write_text(
        json.dumps(
            {
                "observations": [
                    {
                        "observation_id": f"obs-{lane_id}",
                        "lane_id": lane_id,
                        "lane_kind": lane_kind,
                        "provider": provider,
                        "model_id": model_id,
                        "model_fingerprint": model_fingerprint,
                        "scenario_pack_id": scenario_pack_id,
                        "scenario_id": "scenario-public-1",
                        "observed_at": datetime(2026, 5, 13, tzinfo=UTC).isoformat(),
                        "schema_valid": schema_valid,
                        "healing_count": 0 if schema_valid else 1,
                        "json_valid": schema_valid,
                        "tool_call_valid": True,
                        "grounding_valid": schema_valid,
                        "citation_faithfulness_valid": schema_valid,
                        "disagreement_detected": not schema_valid,
                        "latency_ms": 123.0,
                        "cost_usd": 0.0,
                        "context_pressure": 0.42,
                        "provider_error_code": None if schema_valid else "schema_error",
                        "selected_variant_quality": selected_variant_quality,
                        "quarantined": lane_kind == "quarantined_live",
                        "raw_evidence": {
                            "api_key": "sk-never-leak",
                            "hidden_answer": "HIDDEN_HOLDOUT_ANSWER",
                            "safe_counter": 1,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return bundle_dir


def _write_confounded_live_bundle(root: Path) -> Path:
    lane_id = (
        "profile-production__provider-live_gonka_proxy__data-canonical_production"
        "__scenario-public_golden__ui-api_only"
    )
    bundle_dir = root / lane_id
    quality_dir = bundle_dir / "quality_evidence"
    quality_dir.mkdir(parents=True)
    (bundle_dir / "bundle.json").write_text(
        json.dumps(
            {
                "schema_version": "policyos.canary_evidence.v1",
                "canary_kind": "production",
                "created_at": "2026-05-13T12:00:00+00:00",
                "command": {
                    "matrix_lane_id": lane_id,
                    "scenario_pack_id": "public_golden_pack",
                },
            }
        ),
        encoding="utf-8",
    )
    (bundle_dir / "job.json").write_text(
        json.dumps(
            {
                "run_id": "R_confounded",
                "progress": {
                    "details": {
                        "llm_model_variants": [
                            {
                                "model_variant_id": "qwen-live-confounded",
                                "provider": "gonka_proxy",
                                "model": "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
                                "model_fingerprint": "qwen-live-fp",
                                "status": "failed",
                                "failure_code": "provider_timeout",
                                "provider_error_code": "provider_timeout",
                                "schema_healing_count": 1,
                                "json_valid": False,
                                "grounding_valid": False,
                                "citation_faithfulness_valid": False,
                                "selected_variant_quality": 0.20,
                            }
                        ]
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (quality_dir / "quality_scorecard.json").write_text(
        json.dumps(
            {
                "quality_status": "fail",
                "quality_gates": [
                    {
                        "name": "scenario_contract_propagation_graph_connected",
                        "phase": "evidence_spine",
                        "status": "fail",
                        "code": "evidence_spine_contract_dropped",
                    },
                    {
                        "name": "semantic_binding_ledger_passed",
                        "phase": "semantic_binding",
                        "status": "fail",
                        "code": "semantic_claim_axes_missing",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (quality_dir / "policy_design_case.json").write_text(
        json.dumps({"status": "pass", "records": [], "record_families": []}),
        encoding="utf-8",
    )
    return bundle_dir


def _write_controlled_lane_bundle(
    root: Path,
    *,
    lane_id: str,
    provider: str,
    model_id: str,
    model_fingerprint: str,
    request_fingerprint_prefix: str,
    first_sample_schema_valid: bool = True,
) -> Path:
    bundle_dir = root / lane_id
    quality_dir = bundle_dir / "quality_evidence"
    quality_dir.mkdir(parents=True)
    (bundle_dir / "bundle.json").write_text(
        json.dumps(
            {
                "schema_version": "policyos.canary_evidence.v1",
                "canary_kind": "production",
                "command": {"matrix_lane_id": lane_id},
                "files": {
                    "quality_evidence": {
                        "provider_model_quality_observations": (
                            "quality_evidence/provider_model_quality_observations.json"
                        )
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    observations: list[dict[str, object]] = []
    refs = {
        "data_ref": "sha256:" + "d" * 64,
        "norm_ref": "sha256:" + "e" * 64,
        "method_ref": "sha256:" + "f" * 64,
        "claim_ref": "sha256:" + "c" * 64,
    }
    for index in range(3):
        schema_valid = first_sample_schema_valid or index > 0
        observed_refs = refs if schema_valid else {**refs, "data_ref": "sha256:" + "0" * 64}
        observations.append(
            {
                "observation_id": f"obs-{lane_id}-{index}",
                "lane_id": lane_id,
                "lane_kind": "quarantined_live",
                "provider": provider,
                "model_id": model_id,
                "model_fingerprint": model_fingerprint,
                "scenario_pack_id": "provider_controlled_grounding_pack_v1",
                "scenario_id": "provider_controlled_grounding_task_v1",
                "observed_at": datetime(2026, 5, 13, tzinfo=UTC).isoformat(),
                "schema_valid": schema_valid,
                "healing_count": 0 if schema_valid else 1,
                "json_valid": schema_valid,
                "tool_call_valid": True,
                "grounding_valid": schema_valid,
                "citation_faithfulness_valid": schema_valid,
                "disagreement_detected": False,
                "refusal_detected": not schema_valid,
                "degradation_behavior": None if schema_valid else "fallback_plain_json",
                "request_fingerprint": (
                    f"sha256:{request_fingerprint_prefix}-controlled-{index}"
                ),
                "latency_ms": 100.0 + index,
                "cost_usd": 0.001,
                "context_pressure": 0.25,
                "provider_error_code": None,
                "selected_variant_quality": 0.92 if schema_valid else 0.55,
                "quarantined": True,
                "raw_evidence": {
                    "controlled_grounding_task": refs,
                    "observed_grounding_refs": observed_refs,
                    "api_key": "sk-never-leak",
                    "request_fingerprint": (
                        f"sha256:{request_fingerprint_prefix}-controlled-{index}"
                    ),
                },
            }
        )
    (quality_dir / "provider_model_quality_observations.json").write_text(
        json.dumps({"observations": observations}),
        encoding="utf-8",
    )
    return bundle_dir


def test_provider_quality_ledger_cli_builds_from_simulated_and_quarantined_lanes(
    tmp_path: Path,
) -> None:
    provider_quality_ledger = _ledger_module()
    input_root = tmp_path / "bundles"
    output = tmp_path / "provider-model-quality-ledger.json"
    _write_lane_bundle(
        input_root,
        lane_id="profile-dev__provider-simulated__data-fixture__scenario-public_golden__ui-api_only",
        provider="simulated",
        model_id="policyos-sim-v1",
        model_fingerprint="fixture-fp",
        lane_kind="simulated",
    )
    _write_lane_bundle(
        input_root,
        lane_id=(
            "profile-production__provider-live_gonka_proxy__data-canonical_production"
            "__scenario-public_golden__ui-api_only"
        ),
        provider="gonka_proxy",
        model_id="Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
        model_fingerprint="qwen-fp",
        lane_kind="quarantined_live",
    )

    assert (
        provider_quality_ledger.main(
            [
                "--input-root",
                str(input_root),
                "--output",
                str(output),
                "--generated-at",
                "2026-05-13T12:00:00+00:00",
                "--default-production-model",
                "simulated:policyos-sim-v1:fixture-fp:policy_drafting",
                "--hidden-answer-token",
                "HIDDEN_HOLDOUT_ANSWER",
            ]
        )
        == 0
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    rendered = json.dumps(payload, sort_keys=True)

    assert payload["schema_version"] == "policyos.provider_model_quality_ledger.v1"
    assert payload["provider_model_quality_ledger_ref"].startswith("sha256:")
    assert payload["summary"]["simulated_observations"] == 1
    assert payload["summary"]["quarantined_live_observations"] == 1
    assert payload["default_model_reviews"][0]["action"] == "approve"
    assert {
        tuple(entry["evidence_lane_kinds"]) for entry in payload["entries"]
    } == {("simulated",), ("quarantined_live",)}
    assert "sk-never-leak" not in rendered
    assert "HIDDEN_HOLDOUT_ANSWER" not in rendered


def test_provider_quality_ledger_keeps_live_provider_metrics_optional_in_ci(
    tmp_path: Path,
) -> None:
    provider_quality_ledger = _ledger_module()
    input_root = tmp_path / "bundles"
    output = tmp_path / "provider-model-quality-ledger.json"
    _write_lane_bundle(
        input_root,
        lane_id="profile-dev__provider-simulated__data-fixture__scenario-public_golden__ui-api_only",
        provider="simulated",
        model_id="policyos-sim-v1",
        model_fingerprint="fixture-fp",
        lane_kind="simulated",
    )

    assert (
        provider_quality_ledger.main(
            [
                "--input-root",
                str(input_root),
                "--output",
                str(output),
                "--generated-at",
                "2026-05-13T12:00:00+00:00",
            ]
        )
        == 0
    )

    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["summary"]["simulated_observations"] == 1
    assert payload["summary"]["quarantined_live_observations"] == 0
    assert payload["summary"]["status"] == "pass"
    assert payload["default_model_reviews"] == []


def test_provider_quality_ledger_marks_live_samples_system_confounded(
    tmp_path: Path,
) -> None:
    provider_quality_ledger = _ledger_module()
    input_root = tmp_path / "bundles"
    output = tmp_path / "provider-model-quality-ledger.json"
    _write_confounded_live_bundle(input_root)

    assert (
        provider_quality_ledger.main(
            [
                "--input-root",
                str(input_root),
                "--output",
                str(output),
                "--generated-at",
                "2026-05-13T12:00:00+00:00",
                "--default-production-model",
                (
                    "gonka_proxy:Qwen/Qwen3-235B-A22B-Instruct-2507-FP8:"
                    "qwen-live-fp:policy_drafting"
                ),
            ]
        )
        == 0
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    entry = payload["entries"][0]
    review = payload["default_model_reviews"][0]
    evidence_sample = entry["sanitized_evidence_samples"][0]

    assert payload["summary"]["status"] == "warn"
    assert payload["summary"]["system_confounded_observations"] == 1
    assert entry["metrics"]["system_confounded_sample_count"] == 1
    assert entry["metrics"]["decision_sample_count"] == 0
    assert entry["drift_action"] == "require_review"
    assert "system_confounded_samples_excluded" in entry["drift_reasons"]
    assert review["action"] == "require_review"
    assert evidence_sample["system_confounded"] is True
    assert evidence_sample["confounding_signal"] == "upstream_evidence_spine_incomplete"
    assert any(
        "evidence_spine_contract_dropped" in ref
        for ref in evidence_sample["upstream_spine_blocker_refs"]
    )
    assert review["action"] != "demote"


def test_provider_quality_ledger_cli_writes_controlled_qwen_kimi_comparison(
    tmp_path: Path,
) -> None:
    provider_quality_ledger = _ledger_module()
    input_root = tmp_path / "bundles"
    output = tmp_path / "provider-model-quality-ledger.json"
    comparison_output = tmp_path / "controlled-provider-comparison.json"
    _write_controlled_lane_bundle(
        input_root,
        lane_id="controlled-qwen",
        provider="gonka_proxy",
        model_id="Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
        model_fingerprint="qwen-controlled-fp",
        request_fingerprint_prefix="qwen",
    )
    _write_controlled_lane_bundle(
        input_root,
        lane_id="controlled-kimi",
        provider="gonka_proxy",
        model_id="moonshotai/Kimi-K2.6",
        model_fingerprint="kimi-controlled-fp",
        request_fingerprint_prefix="kimi",
        first_sample_schema_valid=False,
    )

    assert (
        provider_quality_ledger.main(
            [
                "--input-root",
                str(input_root),
                "--output",
                str(output),
                "--generated-at",
                "2026-05-13T12:00:00+00:00",
                "--controlled-grounding-comparison-output",
                str(comparison_output),
                "--candidate-model",
                "gonka_proxy:Qwen/Qwen3-235B-A22B-Instruct-2507-FP8:qwen-controlled-fp",
                "--candidate-model",
                "gonka_proxy:moonshotai/Kimi-K2.6:kimi-controlled-fp",
                "--default-controlled-model",
                "gonka_proxy:Qwen/Qwen3-235B-A22B-Instruct-2507-FP8:qwen-controlled-fp:policy_drafting",
                "--hidden-answer-token",
                "sk-never-leak",
            ]
        )
        == 0
    )

    comparison = json.loads(comparison_output.read_text(encoding="utf-8"))
    rendered = json.dumps(comparison, sort_keys=True)
    rows = {row["model_id"]: row for row in comparison["rows"]}

    assert comparison["schema_version"] == (
        "policyos.provider_controlled_grounding_comparison.v1"
    )
    assert comparison["summary"]["status"] == "pass"
    assert comparison["default_model_gate"]["action"] == "approve"
    assert rows["Qwen/Qwen3-235B-A22B-Instruct-2507-FP8"]["sample_count"] == 3
    assert rows["moonshotai/Kimi-K2.6"]["sample_count"] == 3
    assert rows["moonshotai/Kimi-K2.6"]["schema_failure_rate"] == 0.333333
    assert rows["moonshotai/Kimi-K2.6"]["grounding_failure_rate"] == 0.333333
    assert rows["Qwen/Qwen3-235B-A22B-Instruct-2507-FP8"]["request_fingerprints"] == [
        "sha256:qwen-controlled-0",
        "sha256:qwen-controlled-1",
        "sha256:qwen-controlled-2",
    ]
    assert "sk-never-leak" not in rendered


def test_provider_quality_contract_is_listed_in_canary_matrix_and_docs() -> None:
    provider_quality_ledger = _ledger_module()
    doc = REPO_ROOT / "docs/reference/runtime/provider-model-quality.md"

    assert provider_quality_ledger.SCHEMA_VERSION == "policyos.provider_model_quality_ledger.v1"
    assert "quality_evidence/provider_model_quality_ledger.json" in (
        canary_matrix.COMMON_EVIDENCE_FILES
    )
    text = doc.read_text(encoding="utf-8")
    assert "policyos.provider_model_quality_ledger.v1" in text
    assert "`provider_model_quality_ledger_ref`" in text
    assert "quarantined live" in text
