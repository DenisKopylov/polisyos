"""Native tracked Ukraine observations through selected CAS and Scientist readers."""

from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.data_forge.domains.ukraine.models import (
    SourceConfig,
    StageId,
    build_default_pipeline_config,
)
from polisyos.data_forge.domains.ukraine.orchestrator import UkraineDataOrchestrator
from polisyos.data_forge.read_api.ukraine import (
    UkraineStageArtifactVerificationError,
    load_verified_stage_artifacts,
    load_verified_stage_output_bytes,
)
from polisyos.ir.observation.contracts import EntityScope, ObservationFamily
from polisyos.scientist.governance import blueprint_release


def _native_sources(tmp_path: Path):
    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    frames = {}
    sources = {}
    for index, family in enumerate(ObservationFamily):
        source = SourceConfig(
            source_id=f"native_{family.value}",
            display_name=f"Native fixture {family.value}",
            stage_id=StageId.D1,
            normalized_artifact="observations.parquet",
            required_columns=["agent_id", "period_id", "amount"],
            metric_columns=["amount"],
            observation_family=family,
            entity_scope=EntityScope.AGENT,
        )
        sources[source.source_id] = source
        periods = ["2024-02", "2024-13", None, "2024"]
        if family is not ObservationFamily.MACRO_STATE:
            periods = ["2024-02"] * 4
        frame = pd.DataFrame(
            {
                "agent_id": [f"fixture::{index}::{row}" for row in range(4)],
                "cell_id": [f"cell::{index}::{row}" for row in range(4)],
                "region_code": ["01"] * 4,
                "sector_id": ["fixture"] * 4,
                "period_id": periods,
                "amount": [10.0, 20.0, 30.0, 40.0],
                "schema_regime_id": ["ukraine_schema_v1"] * 4,
                "regime_id": ["regime_a"] * 4,
            }
        )
        path = config.build_root.normalized_dir / source.source_id / source.normalized_artifact
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path, index=False)
        frames[source.source_id] = (path, frame)
    return config.model_copy(update={"sources": sources}), frames


def _capture_stage(orchestrator: UkraineDataOrchestrator):
    store = FileSystemCAS(orchestrator.config.build_root.resolved_cas_root)
    receipt = load_verified_stage_artifacts(
        orchestrator.stage_manifest_path(StageId.D2),
        store=store,
        allowed_root=orchestrator.config.build_root.root,
        expected_stage=StageId.D2.value,
        required_outputs=(
            "observation_panel_monthly.parquet",
            "observation_panel_annual.parquet",
            "calibration_bundle_manifest.json",
        ),
    )
    payload = load_verified_stage_output_bytes(store, receipt, "observation_panel_monthly.parquet")
    # A fresh CAS object consumes the selected receipt, not the live output file.
    fresh = FileSystemCAS(orchestrator.config.build_root.resolved_cas_root)
    assert payload == load_verified_stage_output_bytes(
        fresh, receipt, "observation_panel_monthly.parquet"
    )
    return fresh, receipt, pd.read_parquet(BytesIO(payload))


def test_tracked_d2_periods_reach_selected_cas_and_scientist(tmp_path: Path) -> None:
    config, source_frames = _native_sources(tmp_path)
    before = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, (path, _) in source_frames.items()
    }
    orchestrator = UkraineDataOrchestrator(config)
    summary = orchestrator._run_stage_with_tracking(StageId.D2, inputs=[])
    assert summary.status == "completed", summary.manifest.errors
    assert summary.manifest.findings == []
    _store, receipt, panel = _capture_stage(orchestrator)
    expected_count = 4 * len(config.sources)
    assert len(panel) == summary.manifest.metrics["n_monthly_records"] == expected_count
    assert panel["observation_id"].is_unique
    assert receipt.outputs["observation_panel_monthly.parquet"].size_bytes > 0
    assert all(
        hashlib.sha256(path.read_bytes()).hexdigest() == before[name]
        for name, (path, _) in source_frames.items()
    )

    macro = panel[panel["family"] == ObservationFamily.MACRO_STATE.value].copy()
    assert list(macro["observed_value"]) == [10.0, 20.0, 30.0, 40.0]
    assert list(macro["period_disposition"]) == ["valid", "invalid", "missing", "limited"]
    assert macro.iloc[0]["period_start"] == "2024-02-01"
    assert macro.iloc[0]["period_end"] == "2024-02-29"
    assert set(macro["schema_regime_id"]) == {"ukraine_schema_v1"}
    # Duplicate labels must retain positional date/value pairing in reconciliation.
    macro.index = [7, 7, 2, 2]
    original = macro.copy(deep=True)
    reconciled = blueprint_release._reconcile_ukraine_period_projection(macro)
    pd.testing.assert_frame_equal(macro, original)
    assert list(reconciled.index) == [7, 7, 2, 2]
    assert list(reconciled["observed_value"]) == [10.0, 20.0, 30.0, 40.0]
    assert set(reconciled["period_projection_provenance"]) == {"recomputed_from_period_id"}
    assert set(reconciled["schema_regime_id"]) == {"ukraine_schema_v1"}
    registry = blueprint_release.build_family_eligibility_registry(
        reconciled, coverage_threshold=0.95
    )
    assert registry.families[ObservationFamily.MACRO_STATE.value].exact_signoff_eligible is False

    for field, value in [("period_end", "2024-02-31"), ("period_projection_version", "unknown")]:
        altered = macro.reset_index(drop=True)
        altered.loc[0, field] = value
        with pytest.raises(UkraineStageArtifactVerificationError, match="period_projection"):
            blueprint_release._reconcile_ukraine_period_projection(altered)


def test_tracked_d2_failure_and_fresh_rerun_do_not_mix_shards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.data_forge.domains.ukraine import orchestrator as owner
    from polisyos.data_forge.domains.ukraine.builders import sources

    config, _source_frames = _native_sources(tmp_path)
    # Wall-clock seconds are neither an attempt identity nor a monotonic source.
    monkeypatch.setattr(owner.time, "time", lambda: 1700000000.0)
    orchestrator = UkraineDataOrchestrator(config)
    real_mapper = sources._observation_metric_frames_from_frame

    def fail_after_first_metric(*args, **kwargs):
        yield next(iter(real_mapper(*args, **kwargs)))
        raise OSError("controlled inter-metric failure")

    with monkeypatch.context() as controlled:
        controlled.setattr(
            sources, "_observation_metric_frames_from_frame", fail_after_first_metric
        )
        failed = orchestrator._run_stage_with_tracking(StageId.D2, inputs=[])
    assert failed.status == "failed"
    assert failed.manifest.outputs == []
    assert "controlled inter-metric failure" in " ".join(failed.manifest.errors)
    partial = failed.manifest.metrics["partial_observation_stage"]
    assert partial["confirmed_shard_count"] == 1
    assert partial["confirmed_monthly_rows"] == 4
    shard_paths = [Path(x) for x in partial["confirmed_shard_paths"]]
    assert sum(len(pd.read_parquet(path)) for path in shard_paths) == 4
    failure_bytes = orchestrator.stage_manifest_path(StageId.D2).read_bytes()
    failure_copy = config.build_root.manifests_dir / "failed_d2_attempt.json"
    failure_copy.write_bytes(failure_bytes)
    cas = FileSystemCAS(config.build_root.resolved_cas_root)
    before_ids = list(cas.iter_artifact_ids())
    with pytest.raises(UkraineStageArtifactVerificationError):
        load_verified_stage_artifacts(
            failure_copy,
            store=cas,
            allowed_root=config.build_root.root,
            expected_stage=StageId.D2.value,
            required_outputs=("observation_panel_monthly.parquet",),
        )
    assert list(cas.iter_artifact_ids()) == before_ids

    completed = orchestrator._run_stage_with_tracking(
        StageId.D2, inputs=[], resume_from=failed.manifest.run_id
    )
    assert completed.status == "completed", completed.manifest.errors
    assert completed.manifest.run_id != failed.manifest.run_id
    assert completed.manifest.resume_from == failed.manifest.run_id
    assert failure_copy.read_bytes() == failure_bytes
    _fresh, _receipt, panel = _capture_stage(orchestrator)
    assert len(panel) == 4 * len(config.sources)
    assert panel["observation_id"].is_unique
    assert completed.manifest.metrics["n_monthly_records"] == len(panel)
    assert not (config.build_root.tmp_dir / "d2_observation_shards").exists()
