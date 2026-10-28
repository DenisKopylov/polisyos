from __future__ import annotations

import hashlib
import json
import pickle
from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from polisyos.data_forge.domains.ukraine.manifests import (
    ArtifactRecord,
    BuildRunManifest,
    NormalizedArtifactManifest,
    PartAGateCollectionContext,
    PartAGateExecutionReceipt,
    PartAGateManifest,
    PytestCasePhaseReport,
    ValidationFinding,
    load_manifest,
    write_manifest,
)
from polisyos.data_forge.domains.ukraine.models import (
    StageConfig,
    StageId,
    build_default_pipeline_config,
)
from polisyos.data_forge.domains.ukraine.orchestrator import (
    UkraineDataOrchestrator,
)
from polisyos.data_forge.domains.ukraine.server import OpsCompositionRequiredError
from tools.ops_runners.ukraine_data.server_bootstrap import (
    build_orchestrator as build_ops_orchestrator,
)


def _synthetic_c7_collection_context() -> PartAGateCollectionContext:
    """Build collection context for unit stubs, not actual C7 execution proof."""

    return PartAGateCollectionContext(
        profile="policyos.ukraine.c7.collection.v1",
        plugin_autoload="disabled",
        pluggy_version="synthetic-unit-fixture",
        ambient_controls="sanitized",
        hook_capture="before_collection_modifyitems",
        pytest_arguments=[
            "-q",
            "-ra",
            "--import-mode=importlib",
            "--strict-markers",
            "-o",
            "addopts=",
            "-p",
            "tools.quality.testing.pytest_workload_receipt",
            "tests/integration/test_c7_synthetic_full_pipeline.py",
        ],
        approved_pytest_addopts=[],
        repo_plugin_source_digests={
            "code:tools/quality/testing/pytest_workload_receipt.py": "sha256:" + "4" * 64
        },
        keyword_expression="",
        mark_expression="",
        collect_only=False,
        deselected_node_ids=[],
        ignored_paths=[],
    )


def _passing_part_a_gate() -> PartAGateManifest:
    """Build a unit-only synthetic gate fixture, not actual C7 execution evidence."""

    node_id = "tests/integration/test_c7_synthetic_full_pipeline.py::test_case"
    receipt = PartAGateExecutionReceipt(
        schema_version="policyos.ukraine.part_a_gate_execution.v2",
        attempt_id="c" * 32,
        test_path="tests/integration/test_c7_synthetic_full_pipeline.py",
        source_sha256="sha256:" + "0" * 64,
        pytest_version="9.0.0",
        config_path="pytest.ini",
        config_sha256="sha256:" + "1" * 64,
        collection_context=_synthetic_c7_collection_context(),
        node_ids=[node_id],
        phase_reports=[
            PytestCasePhaseReport(node_id=node_id, when=phase, outcome="passed", reason=None)
            for phase in ("setup", "call", "teardown")
        ],
        pytest_exit_status=0,
        workload_receipt_sha256="sha256:" + "2" * 64,
        phases_receipt_sha256="sha256:" + "3" * 64,
    )
    return PartAGateManifest(status="passed", passed=True, execution_receipt=receipt)


def test_stage_id_str_enum_preserves_python_and_pydantic_contract() -> None:
    for stage_id in StageId:
        assert str(stage_id) == f"StageId.{stage_id.name}"
        assert format(stage_id) == str(stage_id)
        assert format(stage_id, ">24") == format(f"StageId.{stage_id.name}", ">24")
        assert repr(stage_id) == f"<StageId.{stage_id.name}: {stage_id.value!r}>"
        assert stage_id.value == str(stage_id.value) == stage_id
        assert json.dumps(stage_id) == json.dumps(stage_id.value)
        assert StageConfig(stage_id=stage_id).stage_id is stage_id

    schema = StageConfig.model_json_schema()
    assert schema["$defs"]["StageId"] == {
        "description": "Stable stage identifiers used by the Ukraine data orchestrator.",
        "enum": [
            "bootstrap_server",
            "validate_part_a",
            "d0_p0",
            "d1",
            "d2",
            "d3",
            "d4",
            "d5",
            "demography_source_inventory",
            "full",
            "release",
        ],
        "title": "StageId",
        "type": "string",
    }
    assert schema["properties"]["stage_id"] == {"$ref": "#/$defs/StageId"}
    assert schema["properties"]["required_previous_stages"]["items"] == {"$ref": "#/$defs/StageId"}

    legacy_d3_pickle = bytes.fromhex(
        "80059543000000000000008c2a706f6c6973796f732e646174615f666f7267652e"
        "646f6d61696e732e756b7261696e652e6d6f64656c73948c0753746167654964"
        "9493948c02643394859452942e"
    )
    assert pickle.dumps(StageId.D3) == legacy_d3_pickle


def test_domain_orchestrator_requires_explicit_workspace_root(tmp_path: Path) -> None:
    """Domain composition never infers a repository from its source location."""

    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    implicit = UkraineDataOrchestrator(config)
    explicit_root = tmp_path / "checkout"
    explicit = UkraineDataOrchestrator(config, workspace_root=explicit_root)

    assert implicit.workspace_root is None
    assert explicit.workspace_root == explicit_root


def test_bootstrap_server_writes_expected_outputs(tmp_path: Path) -> None:
    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    config.server.require_server_for_build = False
    config.server.storage_root = tmp_path / "server-root"
    config.server.workdir = tmp_path / "repo"
    orchestrator = build_ops_orchestrator(config, tmp_path / "checkout")

    summary = orchestrator.bootstrap_server(write_capabilities=True)

    assert summary.status == "completed"
    output_paths = {Path(output.path) for output in summary.manifest.outputs}
    assert config.server.env_path in output_paths
    assert orchestrator.bootstrap_script_path() in output_paths
    assert config.build_root.capability_manifest_path in output_paths


def test_domain_bootstrap_requires_ops_renderer(tmp_path: Path) -> None:
    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    config.server.require_server_for_build = False
    orchestrator = UkraineDataOrchestrator(config)

    with pytest.raises(OpsCompositionRequiredError, match="Ops-owned"):
        orchestrator.write_bootstrap_script()


def test_build_stage_blocks_when_part_a_gate_is_missing(tmp_path: Path) -> None:
    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    config.server.require_server_for_build = False
    orchestrator = UkraineDataOrchestrator(config)

    summary = orchestrator.build_stage(StageId.D0_P0)

    assert summary.status == "blocked_by_part_a_gate"
    assert "part_a_gate_manifest.json" in summary.manifest.errors[0]


def test_validate_stage_outputs_reports_missing_artifact(tmp_path: Path) -> None:
    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    config.server.require_server_for_build = False
    orchestrator = UkraineDataOrchestrator(config)
    orchestrator.ensure_layout()
    write_manifest(
        config.build_root.part_a_gate_manifest_path,
        _passing_part_a_gate(),
    )
    long_component = f"missing_{'x' * 190}"
    missing_path = tmp_path / long_component / "does_not_exist.json"
    assert len(str(missing_path)) > 255
    stage_manifest = BuildRunManifest(
        run_id="d0_test",
        stage_id=StageId.D0_P0,
        status="completed",
        started_at="2026-04-05T00:00:00Z",
        finished_at="2026-04-05T00:00:00Z",
        outputs=[{"path": str(missing_path), "sha256": "", "size_bytes": 0}],
    )
    write_manifest(orchestrator.stage_manifest_path(StageId.D0_P0), stage_manifest)

    summary = orchestrator.validate_stage_outputs(StageId.D0_P0)

    assert summary.status == "failed"
    finding = summary.manifest.findings[0]
    assert finding.code == "missing_output"
    message_limit = ValidationFinding.model_json_schema()["properties"]["message"]["maxLength"]
    assert isinstance(message_limit, int)
    assert len(finding.message) <= message_limit
    assert finding.message.startswith("expected output missing:")
    assert finding.message.endswith("does_not_exist.json")
    # The display message is bounded; the source record retains the complete path.
    assert summary.manifest.inputs[0].path == str(missing_path)
    # Supplied DTO values remain strict; only explicit producer paths project.
    with pytest.raises(ValidationError):
        ValidationFinding(
            severity="error",
            code="missing_output",
            message="x" * (message_limit + 1),
        )


def _seed_explicit_period_d3_inputs(tmp_path: Path) -> UkraineDataOrchestrator:
    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    config.server.require_server_for_build = False
    orchestrator = UkraineDataOrchestrator(config)
    orchestrator.ensure_layout()
    write_manifest(
        config.build_root.part_a_gate_manifest_path,
        _passing_part_a_gate(),
    )
    write_manifest(
        orchestrator.stage_manifest_path(StageId.D2),
        BuildRunManifest(
            run_id="d2_explicit_period_fixture",
            stage_id=StageId.D2,
            status="completed",
            started_at="2026-04-05T00:00:00Z",
            finished_at="2026-04-05T00:00:00Z",
        ),
    )
    frames = {
        "household_microdata": pd.DataFrame(
            {
                "household_id": ["hh::1", "hh::2"],
                "cell_id": [
                    "cell::01::household_distribution",
                    "cell::02::household_distribution",
                ],
                "period_id": ["2025-12", "2025-12"],
                "income": [1000.0, 800.0],
                "weight": [1.0, 1.0],
                "market_income": [900.0, 700.0],
                "region_code": ["01", "02"],
            }
        ),
        "labor_force_microdata": pd.DataFrame(
            {
                "household_id": ["lfs::1", "lfs::2", "lfs::3", "lfs::4"],
                "cell_id": [
                    "cell::01::labor_market",
                    "cell::01::labor_market",
                    "cell::02::labor_market",
                    "cell::02::labor_market",
                ],
                "period_id": ["2025-12"] * 4,
                "participation_rate": [0.9, 0.8, 0.6, 0.5],
                "weight": [1.0] * 4,
                "employment_flag": [0.8, 0.7, 0.4, 0.5],
                "informal_employment_flag": [0.1] * 4,
                "region_code": ["01", "01", "02", "02"],
            }
        ),
        "pfu_debt": pd.DataFrame(
            {"agent_id": ["agent::1"], "period_id": ["2025-12"], "debt_amount": [10.0]}
        ),
        "wage_arrears": pd.DataFrame(
            {"agent_id": ["agent::1"], "period_id": ["2025-12"], "arrears_amount": [5.0]}
        ),
        "distress_events": pd.DataFrame(
            {
                "agent_id": ["agent::1"],
                "period_id": ["2025-12"],
                "months_to_event": [12],
                "event_flag": [1],
            }
        ),
        "employment_service": pd.DataFrame(
            {
                "agent_id": ["agent::a", "agent::b"],
                "region_code": ["01", "02"],
                "period_id": ["2025-12", "2025-12"],
                "employment_count": [80.0, 45.0],
                "vacancies": [10.0, 6.0],
            }
        ),
        "macro_nbu_derzhstat": pd.DataFrame(
            {
                "metric_id": ["employment_index", "employment_index"],
                "observed_value": [0.82, 0.48],
                "region_code": ["01", "02"],
                "period_id": ["2025-12", "2025-12"],
            }
        ),
    }
    declared_inputs = set(config.stages[StageId.D3.value].required_sources)
    for source_id, frame in frames.items():
        source = config.sources[source_id]
        path = config.build_root.normalized_dir / source_id / source.normalized_artifact
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path, index=False)
        if source_id in declared_inputs:
            write_manifest(
                config.build_root.manifests_dir / source_id / source.manifest_name,
                NormalizedArtifactManifest(
                    source_id=source_id,
                    stage_id=StageId.D3,
                    status="completed",
                    normalized_artifact=ArtifactRecord.from_path(path, row_count=len(frame)),
                    schema_version="1.0",
                ),
            )
    return orchestrator


def test_d3_registry_route_preserves_explicit_period_outputs(tmp_path: Path) -> None:
    orchestrator = _seed_explicit_period_d3_inputs(tmp_path)
    config = orchestrator.config
    before = {
        p.relative_to(config.build_root.root)
        for p in config.build_root.root.rglob("*")
        if p.is_file()
    }

    summary = orchestrator.build_stage(StageId.D3)
    persisted = load_manifest(orchestrator.stage_manifest_path(StageId.D3), BuildRunManifest)
    assert isinstance(persisted, BuildRunManifest)
    assert persisted.model_dump(mode="json") == summary.manifest.model_dump(mode="json")

    assert summary.status == persisted.status == "completed"
    assert persisted.stage_id is StageId.D3
    assert persisted.errors == []
    assert persisted.findings == []
    assert persisted.warnings == [
        "logistics_mobility_displacement:Exploratory optional D3 connector.",
        "land_cadastre:Exploratory optional land-use proxy connector.",
        "optional source skipped: logistics_mobility_displacement",
        "optional source skipped: land_cadastre",
    ]
    outputs = {Path(record.path).name: record for record in persisted.outputs}
    assert len(outputs) == len(persisted.outputs)
    assert set(outputs) == set(config.stages[StageId.D3.value].output_artifacts)
    assert len(persisted.inputs) == 5
    assert len({record.path for record in persisted.inputs}) == 5
    assert {Path(record.path).parent.name for record in persisted.inputs} == {
        "household_microdata",
        "labor_force_microdata",
        "pfu_debt",
        "wage_arrears",
        "distress_events",
    }
    assert persisted.metrics == {
        "distress_rows": 1,
        "household_rows": 2,
        "labor_bias_validated": False,
        "labor_rows": 4,
        "labor_validation_overlap_rows": 2,
    }
    # These logical-content digests were measured from the same fixture at the
    # pre-split execution base. The separate receipt records 10/10 byte parity.
    expected_semantic_sha256 = {
        "calibrated_household_cells.parquet": "d0aca476693e1180fd4f81fa182e4208377c13f78f59cbe351929e6c2602dc04",
        "corrected_firm_panels.parquet": "ef2964cd876a0660ca411165f33f5c5c14f174a142a5e2f8f58e67b97d3109a9",
        "household_candidate_panel.parquet": "a5a74bc544e1a26f72ca1b90a1fef402fda0567a2d3ab4eb2163db05d2e94ab1",
        "labor_bias_validation.json": "abeabf94970543d130eaa952d69b433dd542f1e09ed8583a252b979390431d11",
        "labor_market_corrected_panel.parquet": "6132b2c3be315159799cf16d58055a37ca04a55e92a8c2b583fcd1114787fa86",
        "labor_validation_panel.parquet": "eb4e0bed773648d3ed767e7381600e7d7d60285dc5202ed84d85c39e64d8af11",
        "land_cadastre_skipped_source_manifest.json": "ba7a21b5c5dc8eb86c9131670ffde7708cb008ebb856db185afc12604c0828ff",
        "lesson_registry_seed_v1.json": "abac2bf425cedf8f37409f008985c2d3991e7106bb5e906a45d6fb527611189b",
        "logistics_mobility_displacement_skipped_source_manifest.json": "37b086cd3493c6980db977fd700c8c7a35dad26e35ee1facaf31f32a380bd95c",
        "microsim_survey_contract_v1.json": "dbdfae5bc4fda952c95cff1e069dd7fede732fc91987ba4adacccba2b658c3bd",
        "survival_hazard_estimates.parquet": "8ddb27b4eeba11e0c7dc985933359155a85fa9fb9c84d69059935ca7060df12c",
    }
    assert set(outputs) == set(expected_semantic_sha256) | {"household_candidate_basis.json"}
    for record in persisted.outputs:
        path = Path(record.path)
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record.sha256
        assert path.stat().st_size == record.size_bytes
        if path.name in expected_semantic_sha256:
            if path.suffix == ".parquet":
                semantic = (
                    pd.read_parquet(path)
                    .to_json(orient="split", date_format="iso", double_precision=12)
                    .encode()
                )
            else:
                semantic = json.dumps(
                    json.loads(path.read_text(encoding="utf-8")),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            assert hashlib.sha256(semantic).hexdigest() == expected_semantic_sha256[path.name], (
                path.name
            )

    candidate_panel = pd.read_parquet(outputs["household_candidate_panel.parquet"].path)
    assert list(candidate_panel.columns) == [
        "family",
        "metric_id",
        "region_code",
        "quarter_id",
        "period_start",
        "period_end",
        "time_grain",
        "observed_value",
        "unit",
        "source_snapshot_id",
        "source_record_hashes",
        "contributor_count",
        "population_coverage",
        "custody",
        "currentness",
    ]
    assert candidate_panel.empty
    candidate_basis = json.loads(
        Path(outputs["household_candidate_basis.json"].path).read_text(encoding="utf-8")
    )
    assert candidate_basis["status"] == "incomplete"
    assert candidate_basis["source_row_count"] == 2
    assert candidate_basis["source_record_hashes"] == []
    assert (
        candidate_basis["panel_artifact"]["path"]
        == outputs["household_candidate_panel.parquet"].path
    )
    assert candidate_basis["panel_artifact"]["row_count"] == 0
    assert (
        candidate_basis["panel_artifact"]["sha256"]
        == outputs["household_candidate_panel.parquet"].sha256
    )

    after = {
        p.relative_to(config.build_root.root)
        for p in config.build_root.root.rglob("*")
        if p.is_file()
    }
    created = {path.as_posix() for path in after - before}
    assert created == {
        "calibration/d3/calibrated_household_cells.parquet",
        "calibration/d3/corrected_firm_panels.parquet",
        "calibration/d3/labor_bias_validation.json",
        "calibration/d3/labor_market_corrected_panel.parquet",
        "calibration/d3/labor_validation_panel.parquet",
        "calibration/d3/lesson_registry_seed_v1.json",
        "calibration/d3/microsim_survey_contract_v1.json",
        "calibration/d3/survival_hazard_estimates.parquet",
        "calibration/d3/household_candidate_panel.parquet",
        "calibration/d3/household_candidate_basis.json",
        "manifests/build_run_d3.json",
        "manifests/land_cadastre/skipped_source_manifest.json",
        "manifests/land_cadastre_skipped_source_manifest.json",
        "manifests/logistics_mobility_displacement/skipped_source_manifest.json",
        "manifests/logistics_mobility_displacement_skipped_source_manifest.json",
        "manifests/metrics.prom",
        "manifests/resource_usage.jsonl",
        "manifests/stage_metrics.json",
    }
    labor_report = json.loads(
        Path(outputs["labor_bias_validation.json"].path).read_text(encoding="utf-8")
    )
    assert labor_report["family"] == "labor_market"
    assert labor_report["overlap_rows"] >= 1


def test_d4_registry_route_keeps_governance_handoff_purpose_limited(tmp_path: Path) -> None:
    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    config.server.require_server_for_build = False
    orchestrator = UkraineDataOrchestrator(config)
    orchestrator.ensure_layout()
    write_manifest(
        config.build_root.part_a_gate_manifest_path,
        _passing_part_a_gate(),
    )
    write_manifest(
        orchestrator.stage_manifest_path(StageId.D3),
        BuildRunManifest(
            run_id="d3_completed_fixture",
            stage_id=StageId.D3,
            status="completed",
            started_at="2026-04-05T00:00:00Z",
            finished_at="2026-04-05T00:00:00Z",
        ),
    )

    summary = orchestrator.build_stage(StageId.D4)

    assert summary.status == "completed"
    assert {Path(record.path).name for record in summary.manifest.outputs} == {
        "d4_governance_request.json"
    }
    request = json.loads(Path(summary.manifest.outputs[0].path).read_text(encoding="utf-8"))
    assert request["authority_purpose"] == "producer_governance_handoff"
    assert "governance_admissibility" in request["may_not_use_for"]
    assert "governance_verdict" not in request
    assert "coverage_threshold" not in request
    assert "waived_signoff_families" not in request


@pytest.mark.parametrize(
    "failure_kind", ["permission", "reader", "reader_restart", "mapper", "mapper_after_first"]
)
def test_d2_failure_receipt_preserves_actual_reader_or_mapper_reason(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_kind: str,
) -> None:
    """The stage's persisted error distinguishes denial, reader and mapper failures."""
    import pyarrow.parquet as parquet

    from polisyos.data_forge.domains.ukraine.builders import sources
    from polisyos.data_forge.domains.ukraine.models import SourceConfig
    from polisyos.ir.observation.contracts import EntityScope, ObservationFamily

    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    source = SourceConfig(
        source_id="reader_failure",
        display_name="reader failure",
        stage_id=StageId.D1,
        normalized_artifact="frame.parquet",
        required_columns=["agent_id", "period_id", "income"],
        metric_columns=["income"],
        observation_family=ObservationFamily.MACRO_STATE,
        entity_scope=EntityScope.AGENT,
    )
    config = config.model_copy(update={"sources": {source.source_id: source}})
    orchestrator = UkraineDataOrchestrator(config)
    orchestrator.ensure_layout()
    path = config.build_root.normalized_dir / source.source_id / source.normalized_artifact
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"agent_id": ["a"], "period_id": ["2024-02"], "income": [1.0]}).to_parquet(path)
    reads: list[Path] = []

    def forbidden_read(path: Path, **_kwargs: object) -> pd.DataFrame:
        reads.append(path)
        raise AssertionError("full reader must not be called")

    monkeypatch.setattr(sources, "_read_parquet_frame", forbidden_read)
    if failure_kind in {"permission", "reader"}:

        def fail_read(_path: Path) -> object:
            if failure_kind == "permission":
                raise PermissionError("controlled source permission denied")
            raise OSError("controlled reader decoder error")

        monkeypatch.setattr(parquet, "ParquetFile", fail_read)
    elif failure_kind == "reader_restart":
        original_reader = parquet.ParquetFile
        calls: list[Path] = []

        class FailAfterFirstBatch:
            def __init__(self, reader: object) -> None:
                self.reader = reader

            def iter_batches(self, **kwargs: object):
                batches = iter(self.reader.iter_batches(**kwargs))
                yield next(batches)
                raise OSError("controlled first reader error")

        def fail_restart(path: Path) -> object:
            calls.append(path)
            if len(calls) == 1:
                return FailAfterFirstBatch(original_reader(path))
            raise OSError("controlled retry reader error")

        monkeypatch.setattr(parquet, "ParquetFile", fail_restart)
    else:
        original_mapper = sources._observation_metric_frames_from_frame

        def fail_mapper(*args: object, **kwargs: object):
            if failure_kind == "mapper_after_first":
                yield next(iter(original_mapper(*args, **kwargs)))
            raise OSError("controlled mapper error")

        monkeypatch.setattr(sources, "_observation_metric_frames_from_frame", fail_mapper)

    summary = orchestrator._run_stage_with_tracking(StageId.D2, inputs=[])
    assert summary.status == "failed"
    receipt = load_manifest(orchestrator.stage_manifest_path(StageId.D2), BuildRunManifest)
    error = " ".join(receipt.errors)
    assert reads == []
    if failure_kind == "permission":
        assert "controlled source permission denied" in error
        assert "observation_full_read_budget_not_established" not in error
    elif failure_kind in {"mapper", "mapper_after_first"}:
        assert "controlled mapper error" in error
        assert "observation_full_read_budget_not_established" not in error
    elif failure_kind == "reader_restart":
        assert "controlled first reader error" in error
        assert "controlled retry reader error" in error
    else:
        assert "controlled reader decoder error" in error
        assert "observation_full_read_budget_not_established" in error
    partial = receipt.metrics["partial_observation_stage"]
    assert partial["status"] == "incomplete"
    has_partial = failure_kind in {"mapper_after_first", "reader_restart"}
    assert partial["confirmed_shard_count"] == (1 if has_partial else 0)
    assert partial["confirmed_monthly_rows"] == (1 if has_partial else 0)
    if has_partial:
        assert len(partial["confirmed_shard_paths"]) == 1
        assert Path(partial["confirmed_shard_paths"][0]).is_file()
