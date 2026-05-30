"""Shadow-compatible unified snapshot finalization helpers."""

from __future__ import annotations

import json
import logging
import pathlib
from dataclasses import dataclass
from datetime import UTC, datetime

from polisyos.data_forge.kernel.io import sha256_bytes, sha256_file
from polisyos.data_forge.kernel.snapshot.merkle import merkle_root
from polisyos.data_forge import (
    DATA_FORGE_PROVENANCE_MANIFEST_FILE,
    write_snapshot_provenance_manifest,
)

DEFAULT_PIPELINES = ("datasets", "academic", "lex")
DATA_FORGE_SNAPSHOT_BINDING_FILE = "data_forge_snapshot_binding.json"
DATA_FORGE_SNAPSHOT_BINDING_SCHEMA_VERSION = (
    "policyos.runtime.data_forge_snapshot_binding.v1"
)
PIPELINE_BINDING_SURFACES = {
    "academic": ("academic", "academic"),
    "catalog": ("catalog", "catalog"),
    "datasets": ("catalog", "catalog"),
    "legal": ("legal", "legal"),
    "lex": ("legal", "legal"),
    "domain": ("domain", "ukraine"),
    "ukraine": ("domain", "ukraine"),
}
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _SnapshotArtifactRef:
    uri: str
    sha256: str


def finalize_snapshot(
    snapshot_root: str | pathlib.Path,
    *,
    update_latest_symlink: bool = True,
    pipelines: tuple[str, ...] = DEFAULT_PIPELINES,
) -> pathlib.Path:
    """Create a legacy-compatible `snapshot_manifest.json` from publish manifests."""
    root = pathlib.Path(snapshot_root)
    pipeline_manifests: dict[str, dict[str, object]] = {}
    artifacts: list[dict[str, str]] = []

    for pipeline in pipelines:
        manifest_path = root / pipeline / "publish" / "manifest.json"
        manifest = _read_optional_json(manifest_path)
        pipeline_manifests[pipeline] = manifest
        pipeline_root = root / pipeline
        for item in _list_value(manifest.get("artifacts")):
            if not isinstance(item, dict):
                continue
            artifact_path = _resolve_artifact_path(pipeline_root, str(item.get("path") or ""))
            if artifact_path.exists():
                artifacts.append(
                    {
                        "pipeline": pipeline,
                        "path": str(artifact_path),
                        "sha256": str(item.get("sha256") or sha256_file(artifact_path)),
                    }
                )

    generated_at = datetime.now(UTC).isoformat()
    payload: dict[str, object] = {
        "kind": "snapshot",
        "snapshot_root": str(root),
        "generated_at": generated_at,
        "pipelines": pipeline_manifests,
        "artifacts": artifacts,
    }

    out_path = root / "snapshot_manifest.json"
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_snapshot_binding(
        root=root,
        generated_at=generated_at,
        snapshot_manifest_path=out_path,
        pipeline_manifests=pipeline_manifests,
        artifacts=artifacts,
        pipelines=pipelines,
    )

    if update_latest_symlink:
        _update_latest_symlink(root)

    return out_path


def write_snapshot_binding(
    snapshot_root: str | pathlib.Path,
    *,
    pipelines: tuple[str, ...] = DEFAULT_PIPELINES,
) -> pathlib.Path:
    """Write the closeout-grade Data Forge snapshot binding for an existing snapshot."""
    root = pathlib.Path(snapshot_root)
    snapshot_manifest_path = root / "snapshot_manifest.json"
    generated_at = datetime.now(UTC).isoformat()
    manifest = _read_optional_json(snapshot_manifest_path)
    raw_pipeline_manifests = manifest.get("pipelines")
    pipeline_manifests = (
        {
            str(key): value
            for key, value in raw_pipeline_manifests.items()
            if isinstance(value, dict)
        }
        if isinstance(raw_pipeline_manifests, dict)
        else {}
    )
    raw_artifacts = manifest.get("artifacts")
    artifacts = [
        {str(key): str(value) for key, value in item.items()}
        for item in _list_value(raw_artifacts)
        if isinstance(item, dict)
    ]
    return _write_snapshot_binding(
        root=root,
        generated_at=generated_at,
        snapshot_manifest_path=snapshot_manifest_path,
        pipeline_manifests=pipeline_manifests,
        artifacts=artifacts,
        pipelines=pipelines,
    )


def _write_snapshot_binding(
    *,
    root: pathlib.Path,
    generated_at: str,
    snapshot_manifest_path: pathlib.Path,
    pipeline_manifests: dict[str, dict[str, object]],
    artifacts: list[dict[str, str]],
    pipelines: tuple[str, ...],
) -> pathlib.Path:
    snapshot_id = root.name
    release_id = f"data-forge-release-{snapshot_id}"
    release_manifest_ref = _cas_ref(snapshot_manifest_path)
    bindings: list[dict[str, object]] = []

    for pipeline in pipelines:
        manifest = pipeline_manifests.get(pipeline, {})
        if not manifest:
            continue
        role_surface = PIPELINE_BINDING_SURFACES.get(pipeline)
        if role_surface is None:
            continue
        role, surface = role_surface
        pipeline_artifacts = [
            artifact for artifact in artifacts if artifact.get("pipeline") == pipeline
        ]
        artifact_refs = tuple(
            _SnapshotArtifactRef(
                uri=_artifact_uri(
                    pipeline=pipeline,
                    path=str(artifact.get("path") or ""),
                    snapshot_id=snapshot_id,
                ),
                sha256=str(artifact.get("sha256") or ""),
            )
            for artifact in pipeline_artifacts
            if artifact.get("sha256")
        )
        merkle_hash = merkle_root(artifact_refs)
        data_hash = sha256_bytes(
            "\n".join(sorted(ref.sha256 for ref in artifact_refs)).encode("utf-8")
        )
        snapshot_ref = f"cas://sha256/{merkle_hash}"
        runtime_event_ref = f"event://data-forge/{snapshot_id}/{role}/release"
        manifest_path = root / pipeline / "publish" / "manifest.json"
        manifest_ref = _cas_ref(manifest_path)
        claim_bindings = _claim_requirement_bindings(
            manifest=manifest,
            snapshot_ref=snapshot_ref,
            runtime_event_ref=runtime_event_ref,
        )
        published_at = str(manifest.get("published_at") or generated_at)
        extra = _mapping_value(manifest.get("extra"))
        artifact_ids = [f"cas://sha256/{ref.sha256}" for ref in artifact_refs]
        data_hash_ref = f"sha256:{data_hash}"
        manifest_lineage_refs = _lineage_refs(
            manifest=manifest,
            extra=extra,
            release_manifest_ref=release_manifest_ref,
            manifest_ref=manifest_ref,
            artifact_ids=artifact_ids,
        )
        builder_revision = str(
            extra.get("builder_revision")
            or manifest.get("builder_revision")
            or "polisyos.data_forge.snapshot.finalize.v1"
        )
        creation_time = str(
            extra.get("creation_time")
            or manifest.get("creation_time")
            or manifest.get("created_at")
            or published_at
        )
        quality_gates = _quality_gates(
            role=role,
            manifest=manifest,
            manifest_ref=manifest_ref,
            pipeline_root=root / pipeline,
        )
        transform_lineage = _transform_lineage(
            manifest=manifest,
            extra=extra,
            pipeline=pipeline,
            artifact_ids=artifact_ids,
            snapshot_ref=snapshot_ref,
            data_hash_ref=data_hash_ref,
            builder_revision=builder_revision,
            manifest_ref=manifest_ref,
        )
        bindings.append(
            {
                "role": role,
                "corpus_id": str(
                    extra.get("corpus_id")
                    or manifest.get("corpus_id")
                    or f"polisyos.data_forge.{role}"
                ),
                "snapshot_id": snapshot_id,
                "snapshot_ref": snapshot_ref,
                "release_id": release_id,
                "release_manifest_ref": release_manifest_ref,
                "manifest_ref": manifest_ref,
                "manifest_artifact_id": manifest_ref,
                "artifact_ids": artifact_ids,
                "merkle_root": merkle_hash,
                "data_hash": data_hash_ref,
                "read_api_surface": surface,
                "read_api_module": f"polisyos.data_forge.read_api.{surface}",
                "read_api_identity": f"{surface}@{snapshot_id}",
                "runtime_event_ref": runtime_event_ref,
                "published_at": published_at,
                "creation_time": creation_time,
                "freshness_ttl_seconds": 60 * 60 * 24 * 90,
                "lineage_refs": manifest_lineage_refs,
                "quality_gates": quality_gates,
                "builder_revision": builder_revision,
                "transform_lineage": transform_lineage,
                "prov": {
                    "entity": f"data-forge:{snapshot_id}:{role}",
                    "activity": f"data-forge:{pipeline}:publish",
                    "agent": "team-data-forge",
                    "generated_at": published_at,
                },
                "openlineage": {
                    "namespace": "polisyos.data_forge",
                    "job": {"name": f"{pipeline}.publish"},
                    "run": {"runId": f"{snapshot_id}:{pipeline}"},
                    "inputs": [],
                    "outputs": [
                        {
                            "name": f"{snapshot_id}:{pipeline}",
                            "facets": {
                                "dataHash": {"sha256": data_hash},
                                "merkleRoot": {"sha256": merkle_hash},
                            },
                        }
                    ],
                },
                "claim_requirement_bindings": claim_bindings,
            }
        )

    provenance_manifest_path = write_snapshot_provenance_manifest(
        root,
        snapshot_id=snapshot_id,
        release_id=release_id,
        generated_at=generated_at,
        bindings=bindings,
    )
    provenance_manifest_ref = _cas_ref(provenance_manifest_path)
    for binding in bindings:
        binding["provenance_manifest_ref"] = provenance_manifest_ref

    payload: dict[str, object] = {
        "schema_version": DATA_FORGE_SNAPSHOT_BINDING_SCHEMA_VERSION,
        "snapshot_id": snapshot_id,
        "release_id": release_id,
        "release_manifest_ref": release_manifest_ref,
        "provenance_manifest_ref": provenance_manifest_ref,
        "generated_at": generated_at,
        "bindings": bindings,
    }
    out_path = root / DATA_FORGE_SNAPSHOT_BINDING_FILE
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path


def _read_optional_json(path: pathlib.Path) -> dict[str, object]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return {str(key): value for key, value in payload.items()}


def _resolve_artifact_path(pipeline_root: pathlib.Path, raw_path: str) -> pathlib.Path:
    path = pathlib.Path(raw_path)
    if path.is_absolute():
        return path
    return pipeline_root / path


def _list_value(value: object) -> list[object]:
    if not isinstance(value, list):
        return []
    return value


def _mapping_value(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _string_refs(value: object) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    refs: list[str] = []
    for item in _list_value(value):
        if isinstance(item, str) and item:
            refs.append(item)
        elif isinstance(item, dict):
            ref = item.get("artifact_id") or item.get("artifact_ref") or item.get("ref")
            if ref:
                refs.append(str(ref))
    return refs


def _lineage_refs(
    *,
    manifest: dict[str, object],
    extra: dict[str, object],
    release_manifest_ref: str,
    manifest_ref: str,
    artifact_ids: list[str],
) -> list[str]:
    explicit = _string_refs(extra.get("lineage_refs") or manifest.get("lineage_refs"))
    if explicit:
        return explicit
    return [
        ref
        for ref in (release_manifest_ref, manifest_ref, *artifact_ids)
        if ref
    ]


def _transform_lineage(
    *,
    manifest: dict[str, object],
    extra: dict[str, object],
    pipeline: str,
    artifact_ids: list[str],
    snapshot_ref: str,
    data_hash_ref: str,
    builder_revision: str,
    manifest_ref: str,
) -> list[dict[str, object]]:
    raw = extra.get("transform_lineage") or manifest.get("transform_lineage")
    rows: list[dict[str, object]] = []
    for item in _list_value(raw):
        if not isinstance(item, dict):
            continue
        row = {str(key): value for key, value in item.items()}
        row.setdefault("step_id", f"{pipeline}.publish")
        row.setdefault("operation", "publish_snapshot")
        row.setdefault("input_refs", artifact_ids)
        row.setdefault("output_refs", [snapshot_ref, data_hash_ref])
        row.setdefault("code_ref", builder_revision)
        row.setdefault("config_ref", manifest_ref)
        rows.append(row)
    if rows:
        return rows
    return [
        {
            "step_id": f"{pipeline}.publish",
            "operation": "publish_snapshot",
            "input_refs": artifact_ids,
            "output_refs": [snapshot_ref, data_hash_ref],
            "code_ref": builder_revision,
            "config_ref": manifest_ref,
        }
    ]


def _cas_ref(path: pathlib.Path) -> str:
    if path.exists():
        return f"cas://sha256/{sha256_file(path)}"
    return ""


def _artifact_uri(*, pipeline: str, path: str, snapshot_id: str) -> str:
    name = pathlib.Path(path).name or "artifact"
    safe_name = "".join(
        char if char.isalnum() or char in "._/-" else "_" for char in name.lower()
    )
    return f"polisyos://data-forge/{pipeline}/{safe_name}@{snapshot_id}"


def _quality_gates(
    *,
    role: str,
    manifest: dict[str, object],
    manifest_ref: str,
    pipeline_root: pathlib.Path,
) -> list[dict[str, object]]:
    gates = [
        {
            "name": f"{role}_publish_manifest_present",
            "status": "pass",
            "artifact_id": manifest_ref,
        }
    ]
    qc_report = str(manifest.get("qc_report") or "")
    if qc_report:
        qc_path = pathlib.Path(qc_report)
        if not qc_path.is_absolute():
            qc_path = pipeline_root / qc_path
        qc_ref = _cas_ref(qc_path)
        gates.append(
            {
                "name": f"{role}_publish_quality",
                "status": "pass" if qc_ref else "fail",
                "artifact_id": qc_ref or manifest_ref,
            }
        )
    return gates


def _claim_requirement_bindings(
    *,
    manifest: dict[str, object],
    snapshot_ref: str,
    runtime_event_ref: str,
) -> list[dict[str, object]]:
    extra = manifest.get("extra")
    raw_rows: object = None
    if isinstance(extra, dict):
        raw_rows = extra.get("claim_requirement_bindings") or extra.get(
            "claim_requirements"
        )
    rows: list[dict[str, object]] = []
    for raw_row in _list_value(raw_rows):
        if not isinstance(raw_row, dict):
            continue
        row = {str(key): value for key, value in raw_row.items()}
        row.setdefault("authority_level", "closeout")
        row.setdefault("time_role", "publication_time")
        row.setdefault("supported_by", [snapshot_ref])
        row.setdefault("lifecycle_dependency_refs", [runtime_event_ref])
        rows.append(row)
    return rows


def _update_latest_symlink(root: pathlib.Path) -> None:
    latest = root.parent / "policyos_snapshot_latest"
    try:
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(root.name)
    except OSError as exc:
        logger.warning("Failed to update latest symlink: %s", exc)


__all__ = [
    "DATA_FORGE_PROVENANCE_MANIFEST_FILE",
    "DATA_FORGE_SNAPSHOT_BINDING_FILE",
    "DEFAULT_PIPELINES",
    "PIPELINE_BINDING_SURFACES",
    "finalize_snapshot",
    "write_snapshot_binding",
]
