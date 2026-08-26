"""Focused verified-input tests for the Ukraine D4 Scientist bridge."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from polisyos.data_forge.domains.ukraine.builders.calibration import build_d4_stage
from polisyos.data_forge.domains.ukraine.manifests import (
    ArtifactRecord,
    BuildRunManifest,
    write_manifest,
)
from polisyos.data_forge.domains.ukraine.models import StageId, build_default_pipeline_config
from polisyos.data_forge.read_api.ukraine import UkraineStageArtifactVerificationError
from polisyos.scientist.governance.blueprint_release import run_verified_ukraine_d4_governance


def _write_completed_stage_manifest(
    config,
    *,
    stage_id: StageId,
    outputs: list[ArtifactRecord],
) -> None:
    write_manifest(
        config.build_root.manifests_dir / f"build_run_{stage_id.value}.json",
        BuildRunManifest(
            run_id=f"{stage_id.value}-fixture",
            stage_id=stage_id,
            status="completed",
            started_at="2026-08-26T10:00:00+00:00",
            finished_at="2026-08-26T10:01:00+00:00",
            outputs=outputs,
        ),
    )


def _verified_bridge_fixture(tmp_path):
    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    d0_dir = config.build_root.runtime_dir / "d0_p0"
    d2_dir = config.build_root.calibration_dir / "d2"
    d3_dir = config.build_root.calibration_dir / "d3"
    for directory in (d0_dir, d2_dir, d3_dir):
        directory.mkdir(parents=True, exist_ok=True)

    cohort_path = d0_dir / "identity_resolution_cohort_v1.json"
    cohort_path.write_text(
        json.dumps(
            {
                "schema_version": "policyos.data_forge.ukraine.identity_resolution_cohort.v1",
                "rows": [
                    {"cohort": "spending", "raw_identity": "s1", "resolved": True},
                    {"cohort": "spending", "raw_identity": "s2", "resolved": True},
                    {"cohort": "procurement", "raw_identity": "p1", "resolved": True},
                    {"cohort": "procurement", "raw_identity": "p2", "resolved": True},
                ],
            }
        ),
        encoding="utf-8",
    )
    _write_completed_stage_manifest(
        config,
        stage_id=StageId.D0_P0,
        outputs=[ArtifactRecord.from_path(cohort_path)],
    )

    periods = ["2023-01-01", "2024-01-01", "2025-01-01"]
    families = [
        "budget_flows",
        "procurement_flows",
        "macro_state",
        "trade_exposure",
        "public_service_domain_flows",
        "labor_market",
        "distress_enforcement",
    ]
    rows = [
        {
            "family": family,
            "period_start": period,
            "observed_value": 10.0 + index,
            "trust_weight": 0.99,
            "coverage_estimate": 0.99,
            "measurement_bias_flag": False,
            "source_id": f"source_{family}",
            "source_version": "v1",
            "identification_mode": "point_identified",
            "source_confidence_tier": "validated",
            "proxy_source_id": None,
            "regime_id": "regime_a",
            "entity_id": f"entity::{family}",
        }
        for family in families
        for index, period in enumerate(periods)
    ]
    observation_path = d2_dir / "observation_panel_monthly.parquet"
    pd.DataFrame(rows).to_parquet(observation_path, index=False)
    splits_path = d2_dir / "calibration_splits.json"
    splits_path.write_text(
        json.dumps(
            {
                "train_pre_2024": {"start": "2023-01-01", "end": "2023-12-31"},
                "validation_2024": {"start": "2024-01-01", "end": "2024-12-31"},
                "test_2025": {"start": "2025-01-01", "end": "2025-12-31"},
            }
        ),
        encoding="utf-8",
    )
    _write_completed_stage_manifest(
        config,
        stage_id=StageId.D2,
        outputs=[ArtifactRecord.from_path(observation_path), ArtifactRecord.from_path(splits_path)],
    )

    household_path = d3_dir / "calibrated_household_cells.parquet"
    pd.DataFrame(
        {
            "cell_id": ["cell::1", "cell::1", "cell::1"],
            "region_code": ["01", "01", "01"],
            "period_id": ["2023-01", "2024-01", "2025-01"],
            "household_income_mean": [100.0, 110.0, 120.0],
            "trust_weight": [0.99, 0.99, 0.99],
            "measurement_bias_flag": [False, False, False],
        }
    ).to_parquet(household_path, index=False)
    labor_path = d3_dir / "labor_validation_panel.parquet"
    pd.DataFrame(
        {
            "micro_employment_rate": [0.5, 0.6, 0.7, 0.8],
            "admin_employment_rate_proxy": [0.5, 0.6, 0.7, 0.8],
            "micro_sample_weight": [1.0, 1.0, 1.0, 1.0],
            "macro_labor_signal": [0.5, 0.6, 0.7, 0.8],
        }
    ).to_parquet(labor_path, index=False)
    _write_completed_stage_manifest(
        config,
        stage_id=StageId.D3,
        outputs=[ArtifactRecord.from_path(household_path), ArtifactRecord.from_path(labor_path)],
    )

    d4_result = build_d4_stage(config)
    d4_manifest_path = config.build_root.manifests_dir / "build_run_d4.json"
    _write_completed_stage_manifest(
        config,
        stage_id=StageId.D4,
        outputs=list(d4_result.outputs.values()),
    )
    return config, d4_manifest_path, observation_path


def test_verified_ukraine_d4_bridge_requires_recomputable_d0_coverage_evidence(tmp_path) -> None:
    """A completed D0 manifest without row evidence cannot make D4 governance run."""

    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    result = build_d4_stage(config)
    d4_manifest_path = config.build_root.manifests_dir / "build_run_d4.json"
    write_manifest(
        d4_manifest_path,
        BuildRunManifest(
            run_id="d4-producer",
            stage_id=StageId.D4,
            status="completed",
            started_at="2026-08-26T10:00:00+00:00",
            finished_at="2026-08-26T10:01:00+00:00",
            outputs=list(result.outputs.values()),
        ),
    )
    write_manifest(
        config.build_root.manifests_dir / "build_run_d0_p0.json",
        BuildRunManifest(
            run_id="d0-without-coverage-cohort",
            stage_id=StageId.D0_P0,
            status="completed",
            started_at="2026-08-26T10:00:00+00:00",
            finished_at="2026-08-26T10:01:00+00:00",
        ),
    )

    with pytest.raises(
        UkraineStageArtifactVerificationError,
        match="required stage outputs are missing: identity_resolution_cohort_v1.json",
    ):
        run_verified_ukraine_d4_governance(
            build_root=config.build_root.root,
            d4_manifest_path=d4_manifest_path,
            cas_root=config.build_root.resolved_cas_root,
        )


def test_verified_ukraine_d4_bridge_runs_scientist_validation_and_persists_receipts(
    tmp_path,
) -> None:
    """Verified stage artifacts reach the real Scientist calibration-validation runner."""

    config, d4_manifest_path, _ = _verified_bridge_fixture(tmp_path)

    result = run_verified_ukraine_d4_governance(
        build_root=config.build_root.root,
        d4_manifest_path=d4_manifest_path,
        cas_root=config.build_root.resolved_cas_root,
    )

    assert result.bundle_ref.kind == "scientist.calibration_validation_bundle"
    assert result.bundle.status == "completed"
    assert result.bundle.governance_verdict == "needs_revision"
    assert set(result.bundle.metadata["producer_receipt_refs"]) == {"d0_p0", "d2", "d3", "d4"}
    assert (
        result.bundle.metadata["producer_receipt_authority_purpose"] == "producer_artifact_receipt"
    )


def test_verified_ukraine_d4_bridge_rejects_content_drift_before_governance(tmp_path) -> None:
    """A mutated D2 output cannot create a Scientist governance artifact."""

    config, d4_manifest_path, observation_path = _verified_bridge_fixture(tmp_path)
    pd.DataFrame({"tampered": [1]}).to_parquet(observation_path, index=False)

    with pytest.raises(UkraineStageArtifactVerificationError, match="content hash mismatch"):
        run_verified_ukraine_d4_governance(
            build_root=config.build_root.root,
            d4_manifest_path=d4_manifest_path,
            cas_root=config.build_root.resolved_cas_root,
        )
