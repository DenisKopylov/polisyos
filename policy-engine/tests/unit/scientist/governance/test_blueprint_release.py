"""Focused verified-input tests for the Ukraine D4 Scientist bridge."""

from __future__ import annotations

import json
from pathlib import Path

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
from polisyos.scientist.governance import blueprint_release
from polisyos.scientist.governance.blueprint_release import (
    _household_distribution_observation_panel,
    _load_d4_governance_request,
    _recompute_identity_resolution_coverage,
    run_verified_ukraine_d4_governance,
)


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
                    {"cohort": "spending", "raw_identity": "s1"},
                    {"cohort": "spending", "raw_identity": "s2"},
                    {"cohort": "procurement", "raw_identity": "p1"},
                    {"cohort": "procurement", "raw_identity": "p2"},
                ],
            }
        ),
        encoding="utf-8",
    )
    registry_path = d0_dir / "agent_registry_runtime.parquet"
    pd.DataFrame(
        {
            "agent_id": ["agent::s1", "agent::s2", "agent::p1", "agent::p2"],
            "registration_code": ["s1", "s2", "p1", "p2"],
            "tax_id": [None, None, None, None],
            "edrpou": [None, None, None, None],
        }
    ).to_parquet(registry_path, index=False)
    _write_completed_stage_manifest(
        config,
        stage_id=StageId.D0_P0,
        outputs=[ArtifactRecord.from_path(cohort_path), ArtifactRecord.from_path(registry_path)],
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
        match=(
            "required stage outputs are missing: "
            "agent_registry_runtime.parquet,identity_resolution_cohort_v1.json"
        ),
    ):
        run_verified_ukraine_d4_governance(
            build_root=config.build_root.root,
            d4_manifest_path=d4_manifest_path,
            cas_root=config.build_root.resolved_cas_root,
        )


def test_verified_ukraine_d4_bridge_blocks_household_signoff_after_immutable_admission(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Producer household rows remain bounds-only after immutable admission."""

    config, d4_manifest_path, _ = _verified_bridge_fixture(tmp_path)
    load_verified_stage_artifacts = blueprint_release.load_verified_stage_artifacts

    def _admit_then_mutate_sources(*args, **kwargs):
        receipt = load_verified_stage_artifacts(*args, **kwargs)
        for output in receipt.outputs.values():
            Path(output.source_path).write_bytes(b"mutated after immutable admission")
        return receipt

    monkeypatch.setattr(
        blueprint_release,
        "load_verified_stage_artifacts",
        _admit_then_mutate_sources,
    )

    with pytest.raises(
        ValueError,
        match=r"families_not_exact_signoff_ready:.*household_distribution",
    ):
        run_verified_ukraine_d4_governance(
            build_root=config.build_root.root,
            d4_manifest_path=d4_manifest_path,
            cas_root=config.build_root.resolved_cas_root,
        )


def test_d4_identity_coverage_is_recomputed_from_registry_bytes(tmp_path) -> None:
    """Raw producer identities cannot declare their own resolution predicate."""

    cohort = json.dumps(
        {
            "schema_version": "policyos.data_forge.ukraine.identity_resolution_cohort.v1",
            "rows": [
                {"cohort": "spending", "raw_identity": "s1"},
                {"cohort": "spending", "raw_identity": "s2"},
                {"cohort": "procurement", "raw_identity": "p1"},
                {"cohort": "procurement", "raw_identity": "p2"},
            ],
        }
    ).encode()
    registry_path = tmp_path / "agent_registry_runtime.parquet"
    pd.DataFrame(
        {
            "agent_id": ["agent::s1", "agent::p1"],
            "registration_code": ["s1", "p1"],
            "tax_id": [None, None],
            "edrpou": [None, None],
        }
    ).to_parquet(registry_path, index=False)

    spending, procurement = _recompute_identity_resolution_coverage(
        cohort,
        registry_path.read_bytes(),
    )

    assert spending == pytest.approx(0.5)
    assert procurement == pytest.approx(0.5)


def test_d4_rejects_producer_resolved_flags() -> None:
    """Even all-true producer flags cannot enter the recomputed coverage gate."""

    cohort = json.dumps(
        {
            "schema_version": "policyos.data_forge.ukraine.identity_resolution_cohort.v1",
            "rows": [
                {"cohort": "spending", "raw_identity": "s1", "resolved": True},
                {"cohort": "procurement", "raw_identity": "p1", "resolved": True},
            ],
        }
    ).encode()

    with pytest.raises(UkraineStageArtifactVerificationError, match="resolved"):
        _recompute_identity_resolution_coverage(cohort, b"not-consulted")


def test_d4_waiver_flip_is_rejected_with_constant_receipt_hash(tmp_path) -> None:
    """A stable digest cannot authorize a producer-authored signoff waiver."""

    config, d4_manifest_path, _ = _verified_bridge_fixture(tmp_path)
    store = blueprint_release.FileSystemCAS(config.build_root.resolved_cas_root)
    receipt = blueprint_release.load_verified_stage_artifacts(
        d4_manifest_path,
        store=store,
        allowed_root=config.build_root.root,
        expected_stage="d4",
        required_outputs=("d4_governance_request.json",),
    )
    admitted_output = receipt.outputs["d4_governance_request.json"]
    fixed_receipt_hash = admitted_output.sha256
    admitted_bytes = blueprint_release.load_verified_stage_output_bytes(
        store,
        receipt,
        "d4_governance_request.json",
    )
    _load_d4_governance_request(admitted_bytes)
    request = json.loads(admitted_bytes)
    request["waived_signoff_families"] = ["household_distribution"]

    with pytest.raises(UkraineStageArtifactVerificationError, match="waived_signoff_families"):
        _load_d4_governance_request(json.dumps(request).encode())

    assert receipt.outputs["d4_governance_request.json"].sha256 == fixed_receipt_hash


def test_household_projection_carries_declared_unknown_instead_of_coverage() -> None:
    """Household synthesis cannot manufacture verifier-grade exact coverage."""

    panel = _household_distribution_observation_panel(
        pd.DataFrame(
            {
                "cell_id": ["cell::1"],
                "region_code": ["01"],
                "period_id": ["2025-01"],
                "household_income_mean": [100.0],
                "trust_weight": [1.0],
                "measurement_bias_flag": [False],
            }
        )
    )

    assert panel["coverage_estimate"].tolist() == [0.0]
    assert panel["measurement_bias_flag"].tolist() == [True]
    assert panel["identification_mode"].tolist() == ["bounds_only"]
    assert panel["source_confidence_tier"].tolist() == ["exploratory"]
    assert panel["proxy_source_id"].tolist() == ["calibrated_household_cells.parquet"]
    assert blueprint_release._UKRAINE_D4_COVERAGE_THRESHOLD == 0.95


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
