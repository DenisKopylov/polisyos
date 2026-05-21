"""Artifact manifest lifecycle helpers for filesystem-backed CAS implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.common.serialization import fast_json_dumps_bytes

from .manifest import ArtifactManifest, IntegrityInfo

if TYPE_CHECKING:
    from pathlib import Path

    from ._atomic_write import AtomicFileWriter
    from .ids import ArtifactID
    from .write_contract import ArtifactWriteOptions


class ManifestLifecycle:
    """Build, serialize, and validate immutable artifact manifest sidecars."""

    def __init__(self, files: AtomicFileWriter) -> None:
        self._files = files

    @staticmethod
    def build(
        *,
        artifact_id: ArtifactID,
        data: bytes,
        sha: str,
        opts: ArtifactWriteOptions,
    ) -> ArtifactManifest:
        return ArtifactManifest.model_validate(
            {
                "artifact_id": artifact_id,
                "kind": opts.kind,
                "media_type": opts.media_type,
                "byte_size": len(data),
                "schema": opts.schema,
                "canon": opts.canon,
                "inputs": list(opts.inputs or []),
                "producer": opts.producer,
                "env": opts.env,
                "governance": getattr(opts, "governance", None),
                "tenant_context": getattr(opts, "tenant_context", None),
                "same_input_closure": getattr(opts, "same_input_closure", None),
                "authority": getattr(opts, "authority", None),
                "integrity": IntegrityInfo(sha256=sha),
            }
        )

    @staticmethod
    def to_bytes(manifest: ArtifactManifest) -> bytes:
        return fast_json_dumps_bytes(
            manifest.model_dump(mode="json", by_alias=True, exclude_none=True),
            sort_keys=True,
        )

    def write_once(self, path: Path, manifest: ArtifactManifest) -> bool:
        return self._files.write_once(path, self.to_bytes(manifest))

    @staticmethod
    def read(path: Path) -> ArtifactManifest:
        return ArtifactManifest.model_validate_json(path.read_text("utf-8"))


__all__ = ["ManifestLifecycle"]
