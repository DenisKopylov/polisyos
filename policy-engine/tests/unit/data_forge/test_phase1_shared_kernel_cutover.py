from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

import polisyos.data_forge.kernel.io as kernel_io
import polisyos.data_forge.kernel.pipeline.manifests as kernel_manifest
import polisyos.data_forge.kernel.quality as kernel_quality
import polisyos.data_forge.kernel.runtime as kernel_runtime
import pytest
from polisyos.data_forge.kernel.pipeline.config import (
    EnvSecretBackend,
    MappingSecretBackend,
    SecretRef,
)
from polisyos.data_forge.kernel.snapshot import (
    AtomicCommitResult,
    CommitPlan,
    RetentionPolicy,
    SnapshotCoordinate,
    SnapshotResolver,
    SnapshotTransaction,
    commit_staged_path,
    merkle_root,
)
from polisyos.data_forge.kernel.snapshot import (
    finalize_snapshot as kernel_finalize_snapshot,
)
from polisyos.data_forge.kernel.snapshot.cli import finalize_snapshot as cli_finalize_snapshot
from polisyos.data_forge.kernel.testing import (
    compare_file_sha256,
    compare_json_files,
)


def test_kernel_manifest_writers_accept_legacy_shapes(tmp_path: Path) -> None:
    payload_path = tmp_path / "payload.jsonl"
    payload_path.write_text('{"id": 1}\n', encoding="utf-8")

    legacy_stage_path = kernel_manifest.write_stage_manifest(
        manifest_path=tmp_path / "legacy" / "stage.json",
        stage="normalize",
        status="ok",
        metrics={"rows": 1},
        artifacts=[payload_path],
        started_at="2026-05-01T00:00:00+00:00",
        finished_at="2026-05-01T00:00:01+00:00",
    )
    kernel_stage_path = kernel_manifest.write_stage_manifest(
        manifest_path=tmp_path / "kernel" / "stage.json",
        stage="normalize",
        status="ok",
        metrics={"rows": 1},
        artifacts=(payload_path,),
        started_at="2026-05-01T00:00:00+00:00",
        finished_at="2026-05-01T00:00:01+00:00",
    )

    assert json.loads(legacy_stage_path.read_text(encoding="utf-8")) == json.loads(
        kernel_stage_path.read_text(encoding="utf-8")
    )

    empty_stage_path = kernel_manifest.write_stage_manifest(
        manifest_path=tmp_path / "legacy" / "empty_stage.json",
        stage="empty",
        status="ok",
        artifacts=None,
    )
    empty_publish_path = kernel_manifest.write_publish_manifest(
        manifest_path=tmp_path / "legacy" / "empty_publish.json",
        pipeline="datasets",
        artifacts=None,
    )
    assert json.loads(empty_stage_path.read_text(encoding="utf-8"))["artifacts"] == []
    assert json.loads(empty_publish_path.read_text(encoding="utf-8"))["artifacts"] == []


def test_manifest_writers_match_legacy_reference_shapes(tmp_path: Path) -> None:
    payload_path = tmp_path / "payload.jsonl"
    payload_path.write_text('{"id": 1}\n', encoding="utf-8")

    raw_path = kernel_manifest.write_raw_manifest(
        manifest_path=tmp_path / "raw.json",
        source="fixture",
        endpoint="file://fixture",
        payload_path=payload_path,
        count=1,
        filters={"country": "UA"},
        parser_version="legacy",
        fetched_at="2026-05-01T00:00:00+00:00",
    )
    assert json.loads(raw_path.read_text(encoding="utf-8")) == _legacy_raw_manifest_payload(
        source="fixture",
        endpoint="file://fixture",
        payload_path=payload_path,
        count=1,
        filters={"country": "UA"},
        parser_version="legacy",
        fetched_at="2026-05-01T00:00:00+00:00",
    )

    stage_path = kernel_manifest.write_stage_manifest(
        manifest_path=tmp_path / "stage.json",
        stage="normalize",
        status="ok",
        metrics={"rows": 1},
        artifacts=[payload_path],
        started_at="2026-05-01T00:00:01+00:00",
        finished_at="2026-05-01T00:00:02+00:00",
    )
    assert json.loads(stage_path.read_text(encoding="utf-8")) == _legacy_stage_manifest_payload(
        stage="normalize",
        status="ok",
        metrics={"rows": 1},
        artifacts=[payload_path],
        started_at="2026-05-01T00:00:01+00:00",
        finished_at="2026-05-01T00:00:02+00:00",
    )

    publish_path = kernel_manifest.write_publish_manifest(
        manifest_path=tmp_path / "publish.json",
        pipeline="datasets",
        artifacts=[payload_path],
        qc_report_path=tmp_path / "qc.json",
        extra={"ready": True},
    )
    publish_payload = json.loads(publish_path.read_text(encoding="utf-8"))
    published_at = publish_payload.pop("published_at")
    assert published_at.endswith("+00:00")
    assert publish_payload == _legacy_publish_manifest_payload(
        pipeline="datasets",
        artifacts=[payload_path],
        qc_report_path=tmp_path / "qc.json",
        extra={"ready": True},
    )


def test_kernel_io_qc_thermal_and_phase0_contracts_remain_compatible(
    tmp_path: Path,
) -> None:
    assert kernel_io.sha256_file is kernel_io.sha256_file
    assert kernel_io.sha256_jsonl is kernel_io.sha256_jsonl
    assert kernel_io.ensure_dirs is kernel_io.ensure_dirs
    assert kernel_io.snapshot_component_dir is kernel_io.snapshot_component_dir
    assert kernel_quality.QCCheck is kernel_quality.QCCheck
    assert kernel_quality.QCReport is kernel_quality.QCReport
    assert kernel_quality.evaluate_phase0_quality is kernel_quality.evaluate_phase0_quality
    assert kernel_runtime.ThermalProfile is not None
    assert kernel_runtime.resolve_profile("missing").name == "default"

    artifact = tmp_path / "artifact.jsonl"
    artifact.write_text('{"ok": true}\n', encoding="utf-8")
    assert kernel_io.sha256_jsonl(artifact) == kernel_io.sha256_file(artifact)

    component_dir = kernel_io.snapshot_component_dir(tmp_path / "snapshot", "academic")
    extra_dir = tmp_path / "snapshot" / "extra"
    kernel_io.ensure_dirs(extra_dir)
    assert component_dir.is_dir()
    assert extra_dir.is_dir()

    report = kernel_quality.QCReport(scope="datasets")
    report.checks.append(
        kernel_quality.QCCheck(name="row_count", passed=True, value=1, threshold=1)
    )
    assert report.to_dict() == {
        "scope": "datasets",
        "passed": True,
        "metrics": {},
        "checks": [
            {
                "name": "row_count",
                "passed": True,
                "group": "",
                "severity": "critical",
                "value": 1,
                "threshold": 1,
                "message": "",
                "status": "passed",
            }
        ],
    }

    failed_report = kernel_quality.QCReport(
        scope="datasets",
        checks=[kernel_quality.QCCheck(name="row_count", passed=False)],
    )
    with pytest.raises(RuntimeError, match="row_count"):
        kernel_quality.evaluate_fail_fast(failed_report, fail_fast=True)

    phase0_report = kernel_quality.evaluate_phase0_quality(
        article_count=50,
        claims_count=200,
        parameters_count=100,
        canonical_claim_variable_pct=80.0,
        alignment_seed_parity_pct=100.0,
    )
    assert phase0_report.passed is True


def test_snapshot_cli_finalize_is_data_forge_kernel_owned(tmp_path: Path) -> None:
    assert cli_finalize_snapshot is kernel_finalize_snapshot

    snapshot_root = tmp_path / "snapshot"
    artifact = snapshot_root / "datasets" / "data.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text('{"ok": true}\n', encoding="utf-8")
    kernel_manifest.write_publish_manifest(
        manifest_path=snapshot_root / "datasets" / "publish" / "manifest.json",
        pipeline="datasets",
        artifacts=[artifact],
        published_at="2026-05-01T00:00:00+00:00",
    )

    manifest_path = cli_finalize_snapshot(snapshot_root, update_latest_symlink=False)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert payload["kind"] == "snapshot"
    assert payload["artifacts"] == [
        {
            "pipeline": "datasets",
            "path": str(artifact),
            "sha256": kernel_io.sha256_file(artifact),
        }
    ]


def test_snapshot_finalize_matches_legacy_reference_payload(tmp_path: Path) -> None:
    snapshot_root = tmp_path / "snapshot"
    artifacts: list[Path] = []
    for pipeline in ("datasets", "academic", "lex"):
        artifact = snapshot_root / pipeline / f"{pipeline}.json"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(json.dumps({"pipeline": pipeline}), encoding="utf-8")
        artifacts.append(artifact)
        kernel_manifest.write_publish_manifest(
            manifest_path=snapshot_root / pipeline / "publish" / "manifest.json",
            pipeline=pipeline,
            artifacts=[artifact],
            qc_report_path=snapshot_root / pipeline / "qc_report.json",
            extra={"pipeline": pipeline},
        )

    manifest_path = cli_finalize_snapshot(snapshot_root, update_latest_symlink=False)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    generated_at = payload.pop("generated_at")
    assert generated_at.endswith("+00:00")
    assert payload == _legacy_snapshot_payload(snapshot_root, artifacts)


def test_config_secrets_and_atomic_commit_contracts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret_ref = SecretRef(name="API_TOKEN")
    assert secret_ref.resolve(MappingSecretBackend({"API_TOKEN": "from-map"})) == "from-map"

    monkeypatch.setenv("DF_API_TOKEN", "from-env")
    assert secret_ref.resolve(EnvSecretBackend(prefix="DF_")) == "from-env"

    json_path = kernel_io.atomic_write_json(tmp_path / "manifest.json", {"ok": True})
    assert json.loads(json_path.read_text(encoding="utf-8")) == {"ok": True}

    staged = tmp_path / "staged.txt"
    staged.write_text("ready", encoding="utf-8")
    final = tmp_path / "final.txt"
    result = commit_staged_path(CommitPlan(staging_path=str(staged), final_path=str(final)))

    assert isinstance(result, AtomicCommitResult)
    assert result.final_path == str(final)
    assert result.artifact_count == 0
    assert final.read_text(encoding="utf-8") == "ready"


def test_snapshot_transaction_merkle_time_travel_and_retention_contracts() -> None:
    artifact = _artifact_ref("polisyos://academic/skg@snap-1", "a" * 64)
    transaction = SnapshotTransaction(
        snapshot_id="snap-1",
        asset_group="academic",
        artifacts=(artifact,),
    ).commit()
    assert transaction.merkle_root == merkle_root((artifact,))

    resolver = SnapshotResolver()
    resolver.add(artifact)
    assert (
        resolver.resolve(SnapshotCoordinate(uri="polisyos://academic/skg", snapshot_id="snap-1"))
        == artifact
    )

    retention = RetentionPolicy(retention_class=artifact.retention_class, keep_days=30)
    assert retention.delete_on_expiry is True


def test_differential_harness_supports_file_and_json_comparisons(tmp_path: Path) -> None:
    expected = tmp_path / "expected.json"
    observed = tmp_path / "observed.json"
    expected.write_text('{"generated_at": "old", "ok": true}\n', encoding="utf-8")
    observed.write_text('{"generated_at": "new", "ok": true}\n', encoding="utf-8")

    json_comparison = compare_json_files(
        expected,
        observed,
        ignored_top_level_keys=("generated_at",),
        name="manifest",
    )
    assert json_comparison.passed is True
    assert json_comparison.expected_sha256 == json_comparison.observed_sha256

    expected_bytes = tmp_path / "expected.txt"
    observed_bytes = tmp_path / "observed.txt"
    expected_bytes.write_text("same\n", encoding="utf-8")
    observed_bytes.write_text("same\n", encoding="utf-8")
    file_comparison = compare_file_sha256(expected_bytes, observed_bytes, name="artifact")
    assert file_comparison.passed is True
    assert file_comparison.expected_sha256 == file_comparison.observed_sha256


def test_phase1_architecture_manifests_no_longer_track_removed_shims() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    package_boundaries = tomllib.loads(
        (repo_root / "architecture" / "package_boundaries.toml").read_text(encoding="utf-8")
    )
    packages = {item["module"]: item for item in package_boundaries["package"]}

    assert "polisyos.batch_common" not in packages
    assert "polisyos.batch_snapshot" not in packages

    migration_shims = tomllib.loads(
        (repo_root / "architecture" / "shims.toml").read_text(encoding="utf-8")
    )
    shim_ids = {item["id"] for item in migration_shims["shim"]}
    assert "polisyos-batch-common-to-data-forge-kernel" not in shim_ids
    assert "polisyos-batch-snapshot-to-data-forge-kernel-snapshot" not in shim_ids


def test_data_forge_kernel_does_not_import_legacy_batch_modules() -> None:
    kernel_root = Path(__file__).resolve().parents[3] / "src" / "polisyos" / "data_forge" / "kernel"
    legacy_needles = ("polisyos.batch_common", "polisyos.batch_snapshot")

    offenders = []
    for module_path in sorted(kernel_root.rglob("*.py")):
        text = module_path.read_text(encoding="utf-8")
        if any(needle in text for needle in legacy_needles):
            offenders.append(str(module_path.relative_to(kernel_root)))

    assert offenders == []


def _legacy_raw_manifest_payload(
    *,
    source: str,
    endpoint: str,
    payload_path: Path,
    count: int,
    filters: dict[str, object],
    parser_version: str,
    fetched_at: str,
) -> dict[str, object]:
    return {
        "kind": "raw",
        "source": source,
        "endpoint": endpoint,
        "fetched_at": fetched_at,
        "count": int(count),
        "payload": str(payload_path),
        "sha256": kernel_io.sha256_file(payload_path),
        "filters": filters,
        "parser_version": parser_version,
    }


def _legacy_stage_manifest_payload(
    *,
    stage: str,
    status: str,
    metrics: dict[str, object],
    artifacts: list[Path],
    started_at: str,
    finished_at: str,
) -> dict[str, object]:
    return {
        "kind": "stage",
        "stage": stage,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "metrics": metrics,
        "artifacts": [_legacy_artifact_ref(path) for path in artifacts],
    }


def _legacy_publish_manifest_payload(
    *,
    pipeline: str,
    artifacts: list[Path],
    qc_report_path: Path,
    extra: dict[str, object],
) -> dict[str, object]:
    return {
        "kind": "publish",
        "pipeline": pipeline,
        "artifacts": [_legacy_artifact_ref(path) for path in artifacts],
        "qc_report": str(qc_report_path),
        "extra": extra,
    }


def _legacy_snapshot_payload(snapshot_root: Path, artifacts: list[Path]) -> dict[str, object]:
    pipeline_manifests: dict[str, Any] = {}
    snapshot_artifacts: list[dict[str, str]] = []
    artifacts_by_pipeline = {path.parent.name: path for path in artifacts}
    for pipeline in ("datasets", "academic", "lex"):
        manifest_path = snapshot_root / pipeline / "publish" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        pipeline_manifests[pipeline] = manifest
        artifact = artifacts_by_pipeline[pipeline]
        snapshot_artifacts.append(
            {
                "pipeline": pipeline,
                "path": str(artifact),
                "sha256": kernel_io.sha256_file(artifact),
            }
        )

    return {
        "kind": "snapshot",
        "snapshot_root": str(snapshot_root),
        "pipelines": pipeline_manifests,
        "artifacts": snapshot_artifacts,
    }


def _legacy_artifact_ref(path: Path) -> dict[str, str]:
    return {"path": str(path), "sha256": kernel_io.sha256_file(path) if path.exists() else ""}


def _artifact_ref(uri: str, sha256: str):
    from polisyos.data_forge.kernel.artifacts import (
        ArtifactRef,
        PIILevel,
        ProducerVersion,
        RetentionClass,
    )

    return ArtifactRef(
        uri=uri,
        sha256=sha256,
        producer="tests.unit.data_forge.phase1",
        producer_version=ProducerVersion(code_version="0.1.0", lockfile_hash="c" * 64),
        trace_id="1" * 32,
        span_id="2" * 16,
        config_hash="d" * 64,
        owner="team-data-forge",
        license="test-fixture",
        regeneration_command="uv run pytest tests/unit/data_forge/test_phase1_shared_kernel_cutover.py",
        pii_level=PIILevel.NONE,
        retention_class=RetentionClass.HOT,
        freshness_sla_seconds=3600,
        schema_id="test.schema",
        schema_version="1.0.0",
    )
