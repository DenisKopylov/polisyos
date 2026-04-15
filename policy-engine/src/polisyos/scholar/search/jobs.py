"""Background/resumable deep-research jobs with CAS checkpoints and progress events."""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from polisyos.core.artifacts.async_store import ensure_async_artifact_store
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, ProducerInfo, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.scholar.search.models import (
    QueryGraph,
    ResearchBrief,
    ResearchJobCheckpoint,
    ResearchJobStatus,
    ResearchProgressEvent,
    SearchBudgetControls,
    SearchConstraints,
    WebEvidenceBundle,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.scholar.search.service import ScholarDeepSearchService


@dataclass
class _JobRecord:
    status: ResearchJobStatus
    task: asyncio.Task[WebEvidenceBundle] | None = None


def _resolve_status_index_path(store: ArtifactStore, status_root: Path | None) -> Path:
    if status_root is not None:
        base_root = status_root
    else:
        root_value = getattr(store, "root", None)
        if isinstance(root_value, Path):
            base_root = root_value
        elif isinstance(root_value, str):
            base_root = Path(root_value)
        else:
            base_root = Path.cwd() / ".polisyos" / "scholar_jobs"
    return base_root / "scholar_web_jobs" / "status_index.json"


class DeepResearchJobManager:
    """Manage background deep-search jobs and checkpoint snapshots."""

    def __init__(
        self,
        *,
        service: ScholarDeepSearchService,
        cas: ArtifactStore,
        status_root: Path | None = None,
    ) -> None:
        self._service = service
        self._cas = cas
        self._async_cas = ensure_async_artifact_store(cas)
        self._jobs: dict[str, _JobRecord] = {}
        self._status_index_path = _resolve_status_index_path(cas, status_root)
        self._load_status_index()

    def submit(
        self,
        *,
        question: str | None = None,
        brief: ResearchBrief | None = None,
        query_graph: QueryGraph | None = None,
        claim_texts: list[str] | None = None,
        constraints: SearchConstraints | None = None,
        budgets: SearchBudgetControls | None = None,
    ) -> str:
        """Start one background deep-search job and return its job ID."""
        job_id = f"research.{uuid.uuid4().hex[:24]}"
        status = ResearchJobStatus(job_id=job_id, status="pending")
        record = _JobRecord(status=status)
        self._jobs[job_id] = record
        self._persist_status_index()
        record.task = asyncio.create_task(
            self._run_job(
                job_id=job_id,
                question=question,
                brief=brief,
                query_graph=query_graph,
                claim_texts=claim_texts,
                constraints=constraints,
                budgets=budgets,
                resume_bundle=None,
            )
        )
        return str(job_id)

    async def resume(self, *, checkpoint_artifact_id: str) -> str:
        """Resume a failed/partial job from a CAS checkpoint artifact."""
        payload = from_canonical_bytes(
            await self._async_cas.get_bytes(ArtifactID.model_validate(checkpoint_artifact_id))
        )
        checkpoint = ResearchJobCheckpoint.model_validate(payload)
        job_id = str(checkpoint.job_id)
        self._jobs[job_id] = _JobRecord(
            status=ResearchJobStatus(
                job_id=job_id,
                status="pending",
                checkpoint_artifact_id=checkpoint_artifact_id,
                latest_event=checkpoint.progress_events[-1]
                if checkpoint.progress_events
                else None,
                result_bundle=checkpoint.bundle,
                error=checkpoint.error,
            )
        )
        self._persist_status_index()
        self._jobs[job_id].task = asyncio.create_task(
            self._run_job(
                job_id=job_id,
                question=checkpoint.brief.question,
                brief=checkpoint.brief,
                query_graph=checkpoint.query_graph,
                claim_texts=[item.claim_text for item in checkpoint.bundle.claim_supports]
                or [checkpoint.brief.question],
                constraints=checkpoint.constraints,
                budgets=checkpoint.budgets,
                resume_bundle=checkpoint.bundle,
            )
        )
        return job_id

    def get_status(self, job_id: str) -> ResearchJobStatus:
        """Return current status and latest checkpoint metadata for one job."""
        if job_id not in self._jobs:
            raise KeyError(job_id)
        return self._jobs[job_id].status

    def get_snapshot(self, job_id: str) -> WebEvidenceBundle | None:
        """Return the latest partial/completed bundle for a job without awaiting a live task."""
        status = self.get_status(job_id)
        if status.result_bundle is not None:
            return status.result_bundle
        checkpoint_artifact_id = status.checkpoint_artifact_id
        if not checkpoint_artifact_id:
            return None
        payload = from_canonical_bytes(
            self._cas.get_bytes(ArtifactID.model_validate(checkpoint_artifact_id))
        )
        checkpoint = ResearchJobCheckpoint.model_validate(payload)
        return checkpoint.bundle

    async def wait(self, job_id: str) -> ResearchJobStatus:
        """Await job completion and return the latest status snapshot."""
        if job_id not in self._jobs:
            raise KeyError(job_id)
        record = self._jobs[job_id]
        if record.task is not None:
            await record.task
        return record.status

    async def _run_job(
        self,
        *,
        job_id: str,
        question: str | None,
        brief: ResearchBrief | None,
        query_graph: QueryGraph | None,
        claim_texts: list[str] | None,
        constraints: SearchConstraints | None,
        budgets: SearchBudgetControls | None,
        resume_bundle: WebEvidenceBundle | None,
    ) -> WebEvidenceBundle:
        record = self._jobs[job_id]
        record.status = record.status.model_copy(update={"status": "running"})
        self._persist_status_index()

        brief_for_checkpoint = brief or ResearchBrief(question=question or "research")
        graph_for_checkpoint = query_graph or QueryGraph(brief=brief_for_checkpoint)
        bundle_for_checkpoint = resume_bundle or WebEvidenceBundle(
            bundle_id=job_id,
            brief=brief_for_checkpoint,
            query_graph=graph_for_checkpoint,
            partial=True,
        )
        progress_events: list[ResearchProgressEvent] = []

        async def _on_progress(
            event: ResearchProgressEvent,
            bundle: WebEvidenceBundle,
        ) -> None:
            nonlocal brief_for_checkpoint, graph_for_checkpoint, bundle_for_checkpoint
            patched_event = event.model_copy(update={"job_id": job_id})
            progress_events.append(patched_event)
            brief_for_checkpoint = bundle.brief
            graph_for_checkpoint = bundle.query_graph
            bundle_for_checkpoint = bundle
            checkpoint_ref = await self._persist_checkpoint_async(
                ResearchJobCheckpoint(
                    job_id=job_id,
                    status="running",
                    brief=brief_for_checkpoint,
                    query_graph=graph_for_checkpoint,
                    constraints=constraints,
                    budgets=budgets,
                    bundle=bundle_for_checkpoint,
                    progress_events=progress_events,
                )
            )
            record.status = ResearchJobStatus(
                job_id=job_id,
                status="running",
                checkpoint_artifact_id=str(checkpoint_ref.artifact_id),
                latest_event=patched_event.model_copy(
                    update={"checkpoint_artifact_id": str(checkpoint_ref.artifact_id)}
                ),
                result_bundle=bundle_for_checkpoint,
                updated_at=patched_event.created_at,
            )
            self._persist_status_index()

        try:
            bundle = await self._service.deep_search(
                question=question,
                brief=brief,
                query_graph=query_graph,
                claim_texts=claim_texts,
                constraints=constraints,
                budgets=budgets,
                progress_callback=_on_progress,
                resume_bundle=resume_bundle,
            )
            checkpoint_ref = await self._persist_checkpoint_async(
                ResearchJobCheckpoint(
                    job_id=job_id,
                    status="completed",
                    brief=bundle.brief,
                    query_graph=bundle.query_graph,
                    constraints=constraints,
                    budgets=budgets,
                    bundle=bundle,
                    progress_events=progress_events,
                )
            )
            record.status = ResearchJobStatus(
                job_id=job_id,
                status="completed",
                checkpoint_artifact_id=str(checkpoint_ref.artifact_id),
                latest_event=progress_events[-1] if progress_events else None,
                result_bundle=bundle,
                updated_at=bundle.created_at,
            )
            self._persist_status_index()
            return bundle
        except Exception as exc:
            checkpoint_ref = await self._persist_checkpoint_async(
                ResearchJobCheckpoint(
                    job_id=job_id,
                    status="failed",
                    brief=brief_for_checkpoint,
                    query_graph=graph_for_checkpoint,
                    constraints=constraints,
                    budgets=budgets,
                    bundle=bundle_for_checkpoint,
                    progress_events=progress_events,
                    error=str(exc),
                )
            )
            record.status = ResearchJobStatus(
                job_id=job_id,
                status="failed",
                checkpoint_artifact_id=str(checkpoint_ref.artifact_id),
                latest_event=progress_events[-1] if progress_events else None,
                result_bundle=bundle_for_checkpoint,
                error=str(exc),
                updated_at=datetime.now(UTC),
            )
            self._persist_status_index()
            return bundle_for_checkpoint

    async def _persist_checkpoint_async(self, checkpoint: ResearchJobCheckpoint) -> ArtifactRef:
        return await self._async_cas.put_json(
            checkpoint.model_dump(mode="json", exclude_none=True),
            ArtifactWriteOptions(
                kind="scholar.web_research_checkpoint",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.scholar.web_research_checkpoint", version="1.0"),
                producer=ProducerInfo(component="polisyos.scholar.search.jobs", version="1.0.0"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )

    def _load_status_index(self) -> None:
        if not self._status_index_path.exists():
            return
        try:
            payload = json.loads(self._status_index_path.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(payload, dict):
            return
        for job_id, item in payload.items():
            if not isinstance(job_id, str) or not isinstance(item, dict):
                continue
            try:
                status = ResearchJobStatus.model_validate(item)
            except (TypeError, ValueError):
                continue
            self._jobs[job_id] = _JobRecord(status=status)

    def _persist_status_index(self) -> None:
        self._status_index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            job_id: record.status.model_dump(mode="json", exclude_none=True)
            for job_id, record in sorted(self._jobs.items())
        }
        tmp = self._status_index_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        tmp.replace(self._status_index_path)


__all__ = ["DeepResearchJobManager"]
