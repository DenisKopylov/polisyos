"""Public slsa attestation module API."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.run.manifest import RunManifest

from .models import (
    BuildDefinition,
    BuilderInfo,
    BuildMetadata,
    DigestSet,
    InTotoStatement,
    ResourceDescriptor,
    RunDetails,
    SLSAProvenancePredicate,
    Subject,
)


class SLSAAttestationBuilder:
    """Build in-toto/SLSA provenance statements from CAS + run manifest."""

    def __init__(self, cas: FileSystemCAS) -> None:
        self._cas = cas

    def build_attestation(
        self,
        *,
        decision_packet_id: ArtifactID,
        run_manifest: RunManifest,
        input_artifact_ids: list[ArtifactID],
        internal_parameters: dict[str, Any] | None = None,
        external_parameters: dict[str, Any] | None = None,
        finished_at: datetime | None = None,
    ) -> InTotoStatement:
        finished = finished_at or run_manifest.finished_at or datetime.now(timezone.utc)

        subject = Subject(
            name=f"cas://sha256:{decision_packet_id.hex}",
            digest=DigestSet(sha256=decision_packet_id.hex),
        )

        dependencies: list[ResourceDescriptor] = []
        for aid in sorted(input_artifact_ids, key=lambda item: item.hex):
            manifest = self._cas.get_manifest(aid)
            dependencies.append(
                ResourceDescriptor(
                    uri=f"cas://sha256:{aid.hex}",
                    digest=DigestSet(sha256=aid.hex),
                    name=manifest.kind,
                    annotations={
                        "media_type": manifest.media_type,
                        "byte_size": str(manifest.byte_size),
                    },
                )
            )

        ext: dict[str, Any] = {
            "run_id": run_manifest.run_id,
            "tenant_id": run_manifest.tenant_id,
            "cell_id": run_manifest.cell_id,
        }
        if external_parameters:
            ext.update(external_parameters)

        internal: dict[str, Any] = {
            "run_status": run_manifest.status,
            "error_count": len(run_manifest.errors),
        }
        if internal_parameters:
            internal.update(internal_parameters)

        return InTotoStatement(
            subject=[subject],
            predicate=SLSAProvenancePredicate(
                buildDefinition=BuildDefinition(
                    external_parameters=ext,
                    internal_parameters=internal,
                    resolved_dependencies=dependencies,
                ),
                runDetails=RunDetails(
                    builder=BuilderInfo(version={"polisyos": "3.0"}),
                    metadata=BuildMetadata(
                        invocation_id=run_manifest.run_id,
                        started_on=run_manifest.started_at,
                        finished_on=finished,
                    ),
                ),
            ),
        )
