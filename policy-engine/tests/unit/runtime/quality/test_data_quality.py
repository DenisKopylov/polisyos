from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polisyos.runtime.quality.data_quality import (
    build_production_data_quality_report,
    normalize_production_data_quality_report,
)
from polisyos.runtime.quality.scorecard import (
    build_quality_scorecard,
    normalize_quality_evidence,
)


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _production_root(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    root = tmp_path / "production_data"
    bundle_dir = root / "datasets" / "msme_panel_v1"
    bundle_dir.mkdir(parents=True)
    _write_csv(
        bundle_dir / "panel.csv",
        [
            {
                "entity_id": "ua-msme-1",
                "period": "2026-01-31",
                "geography": "UA",
                "population": "wartime_msme",
                "msme_survival_rate": "0.84",
                "wartime_credit_support": "1",
                "label_quality": "audited",
            },
            {
                "entity_id": "ua-msme-2",
                "period": "2026-02-28",
                "geography": "UA",
                "population": "wartime_msme",
                "msme_survival_rate": "0.88",
                "wartime_credit_support": "0",
                "label_quality": "audited",
            },
            {
                "entity_id": "ua-msme-3",
                "period": "2026-03-31",
                "geography": "UA",
                "population": "wartime_msme",
                "msme_survival_rate": "0.81",
                "wartime_credit_support": "1",
                "label_quality": "audited",
            },
        ],
    )
    (bundle_dir / "data_dictionary.json").write_text(
        json.dumps(
            {
                "columns": {
                    "entity_id": {"description": "Firm identifier", "role": "entity_id"},
                    "period": {"description": "Observation month", "role": "time"},
                    "geography": {"description": "ISO country code", "role": "geography"},
                    "population": {"description": "Target population", "role": "population"},
                    "msme_survival_rate": {
                        "description": "Share of MSMEs still active",
                        "metric_id": "msme_survival_rate",
                        "unit": "rate",
                        "construct": "msme_survival",
                    },
                    "wartime_credit_support": {
                        "description": "Credit support exposure",
                        "metric_id": "wartime_credit_support",
                        "unit": "binary",
                    },
                    "label_quality": {"description": "Audit status", "role": "label_quality"},
                },
                "entity_id_columns": ["entity_id"],
                "time_columns": ["period"],
                "geography_columns": ["geography"],
                "population_columns": ["population"],
                "expected_schema": [
                    "entity_id",
                    "period",
                    "geography",
                    "population",
                    "msme_survival_rate",
                    "wartime_credit_support",
                    "label_quality",
                ],
                "coverage": {
                    "geographies": ["UA"],
                    "period_start": "2026-01-31",
                    "period_end": "2026-03-31",
                    "populations": ["wartime_msme"],
                },
                "updated_at": "2026-05-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "1.0",
        "generated_at": "2026-05-01T00:00:00Z",
        "bundles": {
            "datasets": {
                "role": "dataset_catalog_snapshot",
                "version_id": "msme_panel_v1",
                "readiness": "ready",
                "path": "datasets/msme_panel_v1",
                "dataset_path": "datasets/msme_panel_v1/panel.csv",
                "data_dictionary_path": "datasets/msme_panel_v1/data_dictionary.json",
                "required_files": ["panel.csv", "data_dictionary.json"],
            }
        },
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    evidence_context = {
        "root": str(root),
        "manifest_path": str(root / "manifest.json"),
        "manifest_sha256": _sha("m"),
        "bundles": manifest["bundles"],
    }
    return root, evidence_context


def _materialization_refs(**overrides: str) -> dict[str, str]:
    refs = {
        "data_snapshot_ref": _sha("1"),
        "input_bindings_ref": _sha("2"),
        "registry_bundle_ref": _sha("3"),
        "quality_report_ref": _sha("4"),
        "fabric_retrieval_trace_ref": _sha("5"),
    }
    refs.update(overrides)
    return refs


def test_build_production_data_quality_report_names_refs_counts_and_diagnostics(
    tmp_path: Path,
) -> None:
    root, evidence_context = _production_root(tmp_path)

    report = build_production_data_quality_report(
        production_data_root=root,
        evidence_context=evidence_context,
        materialization_refs=_materialization_refs(),
        data_needs=[
            {
                "metric": "msme_survival_rate",
                "geography": "UA",
                "unit": "rate",
                "population": "wartime_msme",
            }
        ],
        claims=[
            {
                "claim_id": "rec_1",
                "claim_family": "recommendation",
                "major": True,
                "data_refs": ["msme_survival_rate"],
            }
        ],
        now=datetime(2026, 5, 13, tzinfo=UTC),
    )

    assert report["schema_version"] == "policyos.runtime.production_data_quality.v1"
    assert report["status"] == "pass"
    assert report["source_bundle_versions"] == {"datasets": "msme_panel_v1"}
    assert report["manifest_checksum"] == _sha("m")
    assert report["data_snapshot_ref"] == _sha("1")
    assert report["input_bindings_ref"] == _sha("2")
    assert report["registry_bundle_ref"] == _sha("3")
    assert report["row_counts"]["datasets"] == 3
    assert report["entity_counts"]["datasets"] == 3
    assert set(report["diagnostics"]) == {
        "schema_drift",
        "missingness",
        "outliers",
        "duplicate_entity_collisions",
        "unit_drift",
        "temporal_leakage",
        "cohort_leakage",
        "label_quality",
        "construct_validity",
        "coverage",
        "recency_ttl",
        "data_dictionary",
    }
    assert report["claim_diagnostics"] == [
        {
            "claim_id": "rec_1",
            "major": True,
            "status": "pass",
            "diagnostics": [],
            "data_refs": ["msme_survival_rate"],
        }
    ]


def test_report_fails_fixture_like_or_missing_production_evidence(tmp_path: Path) -> None:
    root, evidence_context = _production_root(tmp_path)

    report = build_production_data_quality_report(
        production_data_root=root,
        evidence_context=evidence_context,
        materialization_refs=_materialization_refs(data_snapshot_ref="fixture://snapshot"),
        data_needs=[{"metric": "unknown_metric", "geography": "UA"}],
        now=datetime(2026, 5, 13, tzinfo=UTC),
    )

    assert report["status"] == "fail"
    assert "production_data_quality_missing" in {issue["code"] for issue in report["issues"]}
    assert report["diagnostics"]["construct_validity"]["status"] == "fail"


def test_major_data_backed_failure_requires_degrade_reason_for_approval(
    tmp_path: Path,
) -> None:
    root, evidence_context = _production_root(tmp_path)
    bundle_dir = root / "datasets" / "msme_panel_v1"
    _write_csv(
        bundle_dir / "panel.csv",
        [
            {
                "entity_id": "ua-msme-1",
                "period": "2026-01-31",
                "geography": "UA",
                "population": "wartime_msme",
                "msme_survival_rate": "",
                "wartime_credit_support": "1",
                "label_quality": "audited",
            },
            {
                "entity_id": "ua-msme-2",
                "period": "2026-02-28",
                "geography": "UA",
                "population": "wartime_msme",
                "msme_survival_rate": "",
                "wartime_credit_support": "0",
                "label_quality": "audited",
            },
        ],
    )
    report = build_production_data_quality_report(
        production_data_root=root,
        evidence_context=evidence_context,
        materialization_refs=_materialization_refs(production_data_quality_report_ref=_sha("6")),
        data_needs=[{"metric": "msme_survival_rate", "geography": "UA"}],
        claims=[
            {
                "claim_id": "rec_1",
                "claim_family": "recommendation",
                "major": True,
                "data_refs": ["msme_survival_rate"],
            }
        ],
        now=datetime(2026, 5, 13, tzinfo=UTC),
    )
    degraded = normalize_production_data_quality_report(
        {
            **report,
            "degrade_reason": (
                "Known March reporting lag; recommendation is limited to exploratory "
                "screening pending the next administrative extract."
            ),
        }
    )

    assert report["status"] == "fail"
    assert any(
        issue["code"] == "major_recommendation_data_quality_degrade_reason_missing"
        for issue in report["issues"]
    )
    assert degraded["status"] == "warn"
    assert degraded["degrade_reason"]


def test_scorecard_blocks_failing_production_data_quality_report() -> None:
    job_payload = {
        "job_id": "job-quality",
        "run_id": "R_quality",
        "state": "completed",
        "progress": {
            "details": {
                "data_snapshot_ref": _sha("1"),
                "input_bindings_ref": _sha("2"),
                "registry_bundle_ref": _sha("3"),
                "quality_report_ref": _sha("4"),
                "production_data_quality_report_ref": _sha("5"),
                "normative_applicability_report_ref": _sha("6"),
                "fabric_retrieval_trace_ref": _sha("7"),
                "foundry_method_report_ref": _sha("8"),
                "policy_grounding_matrix_ref": _sha("9"),
                "conflict_check_ref": _sha("a"),
                "llm_model_variants": [
                    {
                        "model_variant_id": "qwen_1",
                        "model": "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
                        "provider": "gateway",
                        "status": "completed",
                        "prompt_tokens": 120,
                        "completion_tokens": 32,
                        "total_tokens": 152,
                        "cost_usd": 0.0001,
                    }
                ],
                "run_performance_summary": {"status": "pass"},
            }
        },
    }
    quality_evidence = normalize_quality_evidence(
        {
            "production_data_quality": {
                "status": "fail",
                "issues": [
                    {
                        "code": "major_recommendation_data_quality_failed",
                        "phase": "production_data_quality",
                        "next_action": "Provide a degrade reason or refresh production data.",
                    }
                ],
            },
            "normative_evidence": {"status": "pass"},
            "fabric_retrieval_trace": {"status": "pass"},
            "foundry_method_report": {"status": "pass"},
            "policy_grounding_matrix": {"status": "pass"},
            "conflict_check": {"status": "pass"},
        },
        canary_kind="production",
    )

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload=job_payload,
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    gate = next(
        item
        for item in scorecard["quality_gates"]
        if item["name"] == "production_data_quality_present"
    )
    assert gate["status"] == "fail"
    assert scorecard["approval_state"] == "quality_failed"
    assert (
        "major_recommendation_data_quality_failed" in scorecard["approval_eligibility"]["reasons"]
    )
