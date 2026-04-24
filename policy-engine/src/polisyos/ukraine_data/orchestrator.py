"""Resumable orchestrator for the Ukraine Part B production build stack."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from polisyos.batch_common.paths import ensure_dirs
from polisyos.ukraine_data.adapters import (
    AgentIdentityResolver,
    SourceExecutionContext,
    build_default_adapter_registry,
)
from polisyos.ukraine_data.builders import STAGE_BUILDERS
from polisyos.ukraine_data.manifests import (
    ArtifactRecord,
    BuildRunManifest,
    NormalizedArtifactManifest,
    PartAGateManifest,
    SkippedSourceManifest,
    ValidationFinding,
    load_manifest,
    utc_now_iso,
    write_manifest,
)
from polisyos.ukraine_data.models import PipelineConfig, StageId, build_default_pipeline_config
from polisyos.ukraine_data.resources import (
    ResourceTracker,
    append_resource_usage,
    directory_size_gib,
    write_prometheus_metrics,
    write_stage_metrics,
)
from polisyos.ukraine_data.server import (
    assert_server_execution_allowed,
    build_bootstrap_script,
    probe_local_server_capabilities,
    run_part_a_gate,
)


class StageBlockedError(RuntimeError):
    """Raised when a requested stage is blocked by a missing prerequisite."""

    def __init__(self, status: str, message: str) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class StageRunSummary:
    """Compact summary returned by the public orchestration methods."""

    manifest: BuildRunManifest

    @property
    def status(self) -> str:
        return self.manifest.status


def load_pipeline_config(
    config_path: Path | None = None,
    *,
    root: Path | None = None,
) -> PipelineConfig:
    """Load pipeline configuration from JSON or build the default config."""

    if config_path is None:
        return build_default_pipeline_config(root=root)
    payload = PipelineConfig.model_validate_json(config_path.read_text(encoding="utf-8"))
    if root is not None:
        payload.build_root.root = root
    return payload


class UkraineDataOrchestrator:
    """Server-only, resumable orchestration facade for Part B stages."""

    def __init__(
        self,
        config: PipelineConfig | None = None,
        *,
        repo_root: Path | None = None,
        adapter_registry: dict[str, Any] | None = None,
    ) -> None:
        self.config = config or build_default_pipeline_config()
        self.repo_root = repo_root or Path(__file__).resolve().parents[3]
        self.adapter_registry = adapter_registry or build_default_adapter_registry()
        self.source_ctx = SourceExecutionContext(self.config.build_root)

    def ensure_layout(self) -> None:
        build_root = self.config.build_root
        ensure_dirs(
            build_root.root,
            build_root.raw_dir,
            build_root.normalized_dir,
            build_root.runtime_dir,
            build_root.calibration_dir,
            build_root.bundles_dir,
            build_root.manifests_dir,
            build_root.tmp_dir,
            build_root.logs_dir,
            build_root.resolved_cas_root,
        )

    def stage_manifest_path(self, stage_id: StageId) -> Path:
        return self.config.build_root.manifests_dir / f"build_run_{stage_id.value}.json"

    def bootstrap_script_path(self) -> Path:
        return self.config.build_root.logs_dir / "bootstrap_server.sh"

    def write_bootstrap_script(self) -> Path:
        self.ensure_layout()
        path = self.bootstrap_script_path()
        path.write_text(
            build_bootstrap_script(self.config.server, self.config.build_root),
            encoding="utf-8",
        )
        path.chmod(0o755)
        return path

    def write_server_capability_manifest(self) -> Path:
        self.ensure_layout()
        payload = probe_local_server_capabilities(self.config.server)
        return write_manifest(self.config.build_root.capability_manifest_path, payload)

    def _write_server_env_file(self) -> Path:
        self.ensure_layout()
        env_path = self.config.server.env_path
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text(
            "\n".join(
                [
                    f"export {self.config.server.server_marker_env}=1",
                    f"export POLISYOS_UKRAINE_DATA_ROOT={self.config.server.storage_root}",
                    f"export POLISYOS_CAS_ROOT={self.config.build_root.resolved_cas_root}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return env_path

    @staticmethod
    def _log(message: str) -> None:
        pass

    def _materialize_source_inputs(
        self, stage_id: StageId
    ) -> tuple[list[ArtifactRecord], list[str]]:
        stage = self.config.stages[stage_id.value]
        if not stage.required_sources:
            return [], []
        inputs: list[ArtifactRecord] = []
        warnings: list[str] = []
        edr_manifest_path = (
            self.config.build_root.manifests_dir
            / "edr_current"
            / self.config.sources["edr_current"].manifest_name
        )
        identity_resolver: AgentIdentityResolver | None = None
        if edr_manifest_path.exists():
            edr_manifest = load_manifest(edr_manifest_path, NormalizedArtifactManifest)
            edr_frame = pd.read_parquet(edr_manifest.normalized_artifact.path)
            identity_resolver = AgentIdentityResolver(edr_frame)
        ordered_sources = list(stage.required_sources)
        if stage_id == StageId.D0_P0 and "edr_current" in ordered_sources:
            ordered_sources = ["edr_current"] + [
                item for item in ordered_sources if item != "edr_current"
            ]

        for source_id in ordered_sources:
            source = self.config.sources[source_id]
            adapter = self.adapter_registry[source.adapter_id]
            manifest_dir = self.config.build_root.manifests_dir / source_id
            normalized_manifest_path = manifest_dir / source.manifest_name
            normalized_artifact_path = (
                self.config.build_root.normalized_dir / source_id / source.normalized_artifact
            )
            if normalized_manifest_path.exists() and normalized_artifact_path.exists():
                self._log(f"reusing normalized source {source_id} from {normalized_artifact_path}")
                normalized_manifest = load_manifest(
                    normalized_manifest_path, NormalizedArtifactManifest
                )
                inputs.append(normalized_manifest.normalized_artifact)
                if source_id == "edr_current":
                    identity_resolver = AgentIdentityResolver(
                        pd.read_parquet(normalized_artifact_path)
                    )
                continue

            self._log(f"fetching source {source_id}")
            snapshot = adapter.fetch(source, self.source_ctx)
            if isinstance(snapshot, SkippedSourceManifest):
                warnings.append(f"{source_id}:{snapshot.reason}")
                if source.required:
                    raise RuntimeError(
                        f"required source {source_id} was skipped: {snapshot.reason}"
                    )
                continue
            self._log(f"normalizing source {source_id}")
            normalized_manifest = adapter.normalize(
                source,
                snapshot,
                self.source_ctx,
                identity_resolver=identity_resolver,
            )
            findings = adapter.validate(source, normalized_manifest)
            error_findings = [finding for finding in findings if finding.severity == "error"]
            if error_findings:
                joined = "; ".join(finding.message for finding in error_findings)
                raise RuntimeError(f"source validation failed for {source_id}: {joined}")
            self._log(
                f"normalized source {source_id}: rows={normalized_manifest.normalized_artifact.row_count} "
                f"path={normalized_artifact_path}"
            )
            inputs.append(normalized_manifest.normalized_artifact)
            if source_id == "edr_current":
                identity_resolver = AgentIdentityResolver(pd.read_parquet(normalized_artifact_path))
        return inputs, warnings

    def _load_stage_manifest(self, stage_id: StageId) -> BuildRunManifest | None:
        path = self.stage_manifest_path(stage_id)
        if not path.exists():
            return None
        return load_manifest(path, BuildRunManifest)

    def _manifest_outputs_exist(self, manifest: BuildRunManifest) -> bool:
        for output in manifest.outputs:
            path = Path(output.path)
            if not path.exists():
                return False
        return True

    def _load_part_a_gate(self) -> PartAGateManifest | None:
        path = self.config.build_root.part_a_gate_manifest_path
        if not path.exists():
            return None
        return load_manifest(path, PartAGateManifest)

    def _ensure_part_a_gate(self) -> None:
        gate = self._load_part_a_gate()
        if gate is None:
            raise StageBlockedError(
                "blocked_by_part_a_gate",
                "Part B stage blocked because part_a_gate_manifest.json is missing.",
            )
        if not gate.passed:
            raise StageBlockedError(
                "blocked_by_part_a_gate",
                f"Part B stage blocked because Part A gate status is {gate.status}.",
            )

    def _ensure_previous_stage_manifests(self, stage_id: StageId) -> None:
        for previous in self.config.stages[stage_id.value].required_previous_stages:
            manifest = self._load_stage_manifest(previous)
            if manifest is None or manifest.status != "completed":
                raise StageBlockedError(
                    "blocked_by_previous_stage",
                    f"Stage {stage_id.value} requires completed stage {previous.value}.",
                )

    def _write_run_manifest(self, path: Path, manifest: BuildRunManifest) -> BuildRunManifest:
        write_manifest(path, manifest)
        append_resource_usage(
            self.config.build_root.resource_usage_path,
            {
                "timestamp": utc_now_iso(),
                "stage_id": manifest.stage_id.value,
                "status": manifest.status,
                "elapsed_s": manifest.elapsed_s,
                "peak_rss_gib": manifest.peak_rss_gib,
                "disk_used_gib": manifest.disk_used_gib,
            },
        )
        stage_metrics_payload = {}
        stage_metrics_path = self.config.build_root.stage_metrics_path
        if stage_metrics_path.exists():
            stage_metrics_payload = json.loads(stage_metrics_path.read_text(encoding="utf-8"))
        stage_metrics_payload[manifest.stage_id.value] = manifest.metrics
        write_stage_metrics(stage_metrics_path, stage_metrics_payload)
        write_prometheus_metrics(
            self.config.build_root.metrics_prom_path,
            {
                f'ukraine_data_stage_elapsed_seconds{{stage="{manifest.stage_id.value}"}}': manifest.elapsed_s,
                f'ukraine_data_stage_peak_rss_gib{{stage="{manifest.stage_id.value}"}}': manifest.peak_rss_gib,
                f'ukraine_data_stage_disk_used_gib{{stage="{manifest.stage_id.value}"}}': manifest.disk_used_gib,
            },
        )
        return manifest

    def _run_stage_with_tracking(
        self,
        stage_id: StageId,
        *,
        inputs: list[ArtifactRecord],
        warnings: list[str] | None = None,
        resume_from: str | None = None,
    ) -> StageRunSummary:
        stage_path = self.stage_manifest_path(stage_id)
        started_at = utc_now_iso()
        tracker = ResourceTracker(self.config.build_root.root)
        errors: list[str] = []
        findings: list[ValidationFinding] = []
        warnings_list = list(warnings or [])
        outputs: list[ArtifactRecord] = []
        metrics: dict[str, Any] = {}
        status = "completed"
        start = time.perf_counter()
        try:
            builder = STAGE_BUILDERS[stage_id]
            self._log(f"building stage {stage_id.value}")
            result = builder(self.config)
            outputs = list(result.outputs.values())
            findings = list(result.findings)
            warnings_list.extend(result.warnings)
            metrics = dict(result.metrics)
            if any(finding.severity == "error" for finding in findings):
                status = "failed"
        except Exception as exc:
            status = "failed"
            errors.append(str(exc))
        elapsed_s = time.perf_counter() - start
        budget = self.config.stages[stage_id.value].resource_budget.time_budget_s
        if budget is not None and elapsed_s > budget:
            warnings_list.append(
                f"runtime_budget_exceeded: elapsed_s={elapsed_s:.3f} budget_s={budget:.3f}"
            )
            metrics["runtime_budget_exceeded"] = True
            metrics["runtime_budget_s"] = budget
            metrics["runtime_budget_ratio"] = elapsed_s / budget if budget else None
        peak_rss_gib = tracker.peak_rss_gib
        disk_used_gib = directory_size_gib(self.config.build_root.root)
        manifest = BuildRunManifest(
            run_id=f"{stage_id.value}_{int(time.time())}",
            stage_id=stage_id,
            status=status,
            started_at=started_at,
            finished_at=utc_now_iso(),
            elapsed_s=elapsed_s,
            peak_rss_gib=peak_rss_gib,
            disk_used_gib=disk_used_gib,
            inputs=inputs,
            outputs=outputs,
            warnings=warnings_list,
            errors=errors,
            findings=findings,
            resume_from=resume_from,
            metrics=metrics,
        )
        self._log(
            f"stage {stage_id.value} finished with status={status} elapsed_s={elapsed_s:.2f} "
            f"outputs={len(outputs)} findings={len(findings)} errors={len(errors)}"
        )
        return StageRunSummary(self._write_run_manifest(stage_path, manifest))

    def bootstrap_server(self, *, write_capabilities: bool = True) -> StageRunSummary:
        assert_server_execution_allowed(self.config.server)
        self.ensure_layout()
        tracker = ResourceTracker(self.config.build_root.root)
        started_at = utc_now_iso()
        env_path = self._write_server_env_file()
        bootstrap_script = self.write_bootstrap_script()
        outputs = [
            ArtifactRecord.from_path(env_path),
            ArtifactRecord.from_path(bootstrap_script),
        ]
        if write_capabilities:
            capability_path = self.write_server_capability_manifest()
            outputs.append(ArtifactRecord.from_path(capability_path))
        manifest = BuildRunManifest(
            run_id=f"{StageId.BOOTSTRAP_SERVER.value}_{int(time.time())}",
            stage_id=StageId.BOOTSTRAP_SERVER,
            status="completed",
            started_at=started_at,
            finished_at=utc_now_iso(),
            elapsed_s=0.0,
            peak_rss_gib=tracker.peak_rss_gib,
            disk_used_gib=directory_size_gib(self.config.build_root.root),
            inputs=[],
            outputs=outputs,
            warnings=[],
            errors=[],
            findings=[],
            metrics={"write_capabilities": write_capabilities},
        )
        return StageRunSummary(
            self._write_run_manifest(self.stage_manifest_path(StageId.BOOTSTRAP_SERVER), manifest)
        )

    def validate_part_a(self) -> StageRunSummary:
        assert_server_execution_allowed(self.config.server)
        self.ensure_layout()
        tracker = ResourceTracker(self.config.build_root.root)
        started_at = utc_now_iso()
        gate = run_part_a_gate(self.config.server, self.repo_root)
        gate_path = write_manifest(self.config.build_root.part_a_gate_manifest_path, gate)
        manifest = BuildRunManifest(
            run_id=f"{StageId.VALIDATE_PART_A.value}_{int(time.time())}",
            stage_id=StageId.VALIDATE_PART_A,
            status=gate.status,
            started_at=started_at,
            finished_at=utc_now_iso(),
            elapsed_s=0.0,
            peak_rss_gib=tracker.peak_rss_gib,
            disk_used_gib=directory_size_gib(self.config.build_root.root),
            inputs=[],
            outputs=[ArtifactRecord.from_path(gate_path)],
            warnings=[],
            errors=[] if gate.passed else [f"part_a_gate_status={gate.status}"],
            findings=[],
            metrics={"passed": gate.passed, "skipped": gate.skipped, "notes": gate.notes},
        )
        return StageRunSummary(
            self._write_run_manifest(self.stage_manifest_path(StageId.VALIDATE_PART_A), manifest)
        )

    def build_stage(self, stage_id: StageId, *, resume: bool = False) -> StageRunSummary:
        if stage_id not in STAGE_BUILDERS:
            raise ValueError(f"unsupported build stage: {stage_id.value}")
        assert_server_execution_allowed(self.config.server)
        self.ensure_layout()
        existing = self._load_stage_manifest(stage_id)
        if (
            resume
            and existing is not None
            and existing.status == "completed"
            and self._manifest_outputs_exist(existing)
        ):
            return StageRunSummary(existing)
        try:
            self._ensure_part_a_gate()
            self._ensure_previous_stage_manifests(stage_id)
            inputs, source_warnings = self._materialize_source_inputs(stage_id)
            return self._run_stage_with_tracking(
                stage_id,
                inputs=inputs,
                warnings=source_warnings,
                resume_from=existing.run_id if existing is not None else None,
            )
        except StageBlockedError as exc:
            manifest = BuildRunManifest(
                run_id=f"{stage_id.value}_{int(time.time())}",
                stage_id=stage_id,
                status=exc.status,
                started_at=utc_now_iso(),
                finished_at=utc_now_iso(),
                elapsed_s=0.0,
                peak_rss_gib=0.0,
                disk_used_gib=directory_size_gib(self.config.build_root.root),
                inputs=[],
                outputs=[],
                warnings=[],
                errors=[str(exc)],
                findings=[],
                resume_from=existing.run_id if existing is not None else None,
                metrics={},
            )
            return StageRunSummary(
                self._write_run_manifest(self.stage_manifest_path(stage_id), manifest)
            )

    def build_full(self, *, resume: bool = False) -> list[StageRunSummary]:
        summaries: list[StageRunSummary] = []
        for stage_id in (StageId.D0_P0, StageId.D1, StageId.D2, StageId.D3, StageId.D4, StageId.D5):
            summary = self.build_stage(stage_id, resume=resume)
            summaries.append(summary)
            if summary.status != "completed":
                break
        return summaries

    def release(self, *, resume: bool = False) -> StageRunSummary:
        return self.build_stage(StageId.D5, resume=resume)

    def validate_stage_outputs(self, stage_id: StageId) -> StageRunSummary:
        manifest = self._load_stage_manifest(stage_id)
        if manifest is None:
            raise FileNotFoundError(f"missing build run manifest for stage {stage_id.value}")
        findings: list[ValidationFinding] = []
        for output in manifest.outputs:
            if not Path(output.path).exists():
                findings.append(
                    ValidationFinding(
                        severity="error",
                        code="missing_output",
                        message=f"expected output missing: {output.path}",
                    )
                )
        validation_manifest = BuildRunManifest(
            run_id=f"validate_{stage_id.value}_{int(time.time())}",
            stage_id=stage_id,
            status="completed" if not findings else "failed",
            started_at=utc_now_iso(),
            finished_at=utc_now_iso(),
            elapsed_s=0.0,
            peak_rss_gib=0.0,
            disk_used_gib=directory_size_gib(self.config.build_root.root),
            inputs=manifest.outputs,
            outputs=[],
            warnings=[],
            errors=[],
            findings=findings,
            metrics={"validated_stage": stage_id.value},
        )
        path = self.config.build_root.manifests_dir / f"validate_{stage_id.value}.json"
        return StageRunSummary(self._write_run_manifest(path, validation_manifest))


__all__ = [
    "StageBlockedError",
    "StageRunSummary",
    "UkraineDataOrchestrator",
    "load_pipeline_config",
]
