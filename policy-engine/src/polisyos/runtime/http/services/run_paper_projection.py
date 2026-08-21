"""Resolve verified terminal run manifests into replayable paper packets."""

from __future__ import annotations

import hmac
from typing import TYPE_CHECKING, Protocol

from polisyos.runtime.http.services.adapters.core_run import (
    BOUND_RUN_MANIFEST_SCHEMA_VERSION,
    load_bound_terminal_manifest,
)
from polisyos.runtime.http.services.export_replay import (
    build_export_replay_address,
    hash_export_projection,
)
from polisyos.runtime.http.services.run_paper_contracts import (
    RUN_PAPER_PROJECTION_RULE_VERSION,
    AvailableRunPaperStageTrace,
    RunPaperArtifactLink,
    RunPaperPacket,
    RunPaperReplayConflictError,
    RunPaperReplayPins,
    RunPaperReplayQuery,
    RunPaperRun,
    RunPaperSourceBinding,
    RunPaperSourceError,
    RunPaperStageTraceResolution,
    UnavailableRunPaperCase,
    UnavailableRunPaperStageTrace,
    build_run_paper_semantic_projection,
)

if TYPE_CHECKING:
    from polisyos.core import artifacts
    from polisyos.runtime.http.services.run_index import IndexedRunRecord


class _RunIndex(Protocol):
    def get_run(self, run_id: str) -> IndexedRunRecord: ...


class RunPaperProjectionService:
    """Build run paper only from a tenant-bound, verified terminal manifest."""

    def __init__(
        self,
        *,
        store: artifacts.ArtifactStore,
        run_index: _RunIndex,
        tenant_id: str,
    ) -> None:
        self._store = store
        self._run_index = run_index
        self._tenant_id = tenant_id

    def get(
        self,
        run_id: str,
        *,
        replay_query: RunPaperReplayQuery | None = None,
    ) -> RunPaperPacket:
        """Return the current packet or the exact packet named by complete pins."""

        try:
            run = self._run_index.get_run(run_id)
            packet = self._project(run)
        except KeyError:
            raise
        except (TypeError, ValueError) as exc:
            if isinstance(exc, RunPaperReplayConflictError | RunPaperSourceError):
                raise
            raise RunPaperSourceError(str(exc)) from exc
        self._check_replay_query(replay_query or RunPaperReplayQuery(), packet.replay_pins)
        return packet

    def resolve(self, run_id: str) -> RunPaperStageTraceResolution | None:
        """Resolve the narrow Cycle Board link, returning no value on any source gap."""

        try:
            packet = self.get(run_id)
        except (KeyError, RunPaperSourceError):
            return None
        if not isinstance(packet.stage_trace, AvailableRunPaperStageTrace):
            return None
        pins = packet.replay_pins
        return RunPaperStageTraceResolution(
            href=packet.report_href,
            manifest_artifact_id=pins.manifest_artifact_id,
            manifest_schema_version=pins.manifest_schema_version,
            paper_projection_rule_version=pins.paper_projection_rule_version,
            paper_projection_hash=pins.paper_projection_hash,
        )

    def _project(self, run: IndexedRunRecord) -> RunPaperPacket:
        if run.details.tenant_id != self._tenant_id:
            raise RunPaperSourceError("run paper tenant binding mismatch")
        if run.summary.run_terminality.value != "terminal":
            raise RunPaperSourceError("run paper requires producer-owned terminality")
        manifest_ref = run.details.manifest_ref
        if manifest_ref is None:
            raise RunPaperSourceError("terminal run carries no manifest reference")
        manifest = load_bound_terminal_manifest(
            store=self._store,
            manifest_ref=manifest_ref,
            run_id=run.run_id,
            tenant_id=run.details.tenant_id,
            cell_id=run.details.cell_id,
        )
        if manifest.tenant_id is None:
            raise RunPaperSourceError("verified run manifest is not tenant-bound")

        paper_run = RunPaperRun(
            run_id=manifest.run_id,
            status=manifest.status,
            run_terminality=run.summary.run_terminality,
            started_at=manifest.started_at,
            finished_at=manifest.finished_at,
            duration_ms=run.summary.duration_ms,
            tenant_id=manifest.tenant_id,
            cell_id=manifest.cell_id,
        )
        if manifest.trace_ref is None:
            stage_trace = UnavailableRunPaperStageTrace()
        elif self._is_verified_ref(manifest.trace_ref):
            stage_trace = AvailableRunPaperStageTrace(trace_ref=manifest.trace_ref)
        else:
            stage_trace = UnavailableRunPaperStageTrace(
                availability="invalid_source",
                reason="run manifest trace reference failed content verification",
            )
        artifact_links = tuple(
            RunPaperArtifactLink(
                artifact_ref=artifact_ref,
                href=f"/api/v1/artifacts/{artifact_ref.artifact_id}",
            )
            for artifact_ref in manifest.outputs
            if self._is_verified_ref(artifact_ref)
        )
        source = RunPaperSourceBinding(
            manifest_ref=manifest_ref,
            producer=manifest.producer,
            environment=manifest.env,
            registry_bundle=manifest.registry_bundle,
        )
        case_record = UnavailableRunPaperCase()
        semantic_projection = build_run_paper_semantic_projection(
            run=paper_run,
            case_record=case_record,
            stage_trace=stage_trace,
            artifact_links=artifact_links,
            source=source,
        )
        projection_hash = hash_export_projection(semantic_projection)
        pins = RunPaperReplayPins(
            manifest_artifact_id=str(manifest_ref.artifact_id),
            manifest_schema_version=BOUND_RUN_MANIFEST_SCHEMA_VERSION,
            paper_projection_rule_version=RUN_PAPER_PROJECTION_RULE_VERSION,
            paper_projection_hash=projection_hash,
        )
        stable_address = f"/api/v1/runs/{run.run_id}/paper"
        pin_values = pins.model_dump(mode="json")
        replay_address = build_export_replay_address(stable_address, pin_values)
        report_stable_address = f"/runs/{run.run_id}/report"
        report_href = (
            f"{build_export_replay_address(report_stable_address, pin_values)}"
            "#stage-trace"
        )
        return RunPaperPacket(
            run=paper_run,
            case_record=case_record,
            stage_trace=stage_trace,
            artifact_links=artifact_links,
            source=source,
            replay_pins=pins,
            projection_hash=projection_hash,
            stable_address=stable_address,
            replay_address=replay_address,
            report_href=report_href,
        )

    def _is_verified_ref(self, artifact_ref: object) -> bool:
        artifact_id = getattr(artifact_ref, "artifact_id", None)
        if artifact_id is None:
            return False
        try:
            verification = self._store.verify(artifact_id)
            if not verification.ok:
                return False
            sidecar = self._store.get_manifest(artifact_id)
        except (OSError, TypeError, ValueError):
            return False
        return (
            sidecar.kind == getattr(artifact_ref, "kind", None)
            and sidecar.media_type == getattr(artifact_ref, "media_type", None)
        )

    @staticmethod
    def _check_replay_query(
        query: RunPaperReplayQuery,
        actual: RunPaperReplayPins,
    ) -> None:
        requested = query.model_dump(mode="json")
        supplied = {key: value for key, value in requested.items() if value is not None}
        if not supplied:
            return
        if len(supplied) != len(RunPaperReplayQuery.model_fields):
            raise RunPaperReplayConflictError(
                "run paper replay requires exactly the complete four-pin tuple"
            )
        actual_values = actual.model_dump(mode="json")
        mismatched = [
            key
            for key, expected in supplied.items()
            if not hmac.compare_digest(str(expected), str(actual_values[key]))
        ]
        if mismatched:
            raise RunPaperReplayConflictError(
                "run paper replay pins do not match the resolved projection: "
                + ", ".join(sorted(mismatched))
            )


__all__ = ["RunPaperProjectionService", "build_run_paper_semantic_projection"]
