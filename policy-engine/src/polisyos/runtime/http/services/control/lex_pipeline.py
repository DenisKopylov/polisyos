"""Lex pipeline control-plane endpoint behavior."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from polisyos.common.logger import get_logger
from polisyos.core.contracts.control import (
    LexGraphStatsResponse,
    LexPipelineStatusResponse,
    LexSearchRequest,
    LexSearchResponse,
    LexTriggerRequest,
    LexTriggerResponse,
)

from .._control_contracts import _build_api_meta

if TYPE_CHECKING:
    from polisyos.runtime.http.execution_policy import RuntimePrincipal

    from ..control_plane_store import ControlJobRecord

logger = get_logger(__name__)


class LexPipelineMixin:
    """Lex batch-pipeline endpoints for the control-plane service."""

    def trigger_lex_pipeline(
        self,
        request: LexTriggerRequest,
        *,
        request_id: str | None = None,
        principal: RuntimePrincipal | None = None,
    ) -> LexTriggerResponse:
        """Queue a Lex batch pipeline job and reject empty stage selections."""
        pipeline_id = f"lex_{uuid.uuid4().hex[:12]}"
        job_id = uuid.uuid4().hex
        output_dir = Path(request.output_dir)
        policy = self._resolve_execution_policy(
            requested_profile=request.execution_profile,
            policy_flags=request.policy_flags,
            principal=principal,
        )

        stages: set[str] = set()
        sc = request.stages
        if sc.parse:
            stages.add("parse")
        if sc.structure:
            stages.add("structure")
        if sc.spo:
            stages.add("spo")
        if sc.graph:
            stages.add("graph")
        if sc.embed:
            stages.add("embed")

        if not stages:
            return LexTriggerResponse(
                meta=_build_api_meta(request_id),
                status="rejected",
                pipeline_id=pipeline_id,
                job_id=job_id,
                effective_execution_profile=policy.effective_profile,
                message="No stages selected.",
            )

        self._enqueue_job(
            job_id=job_id,
            job_kind="lex_pipeline",
            run_id=None,
            pipeline_id=pipeline_id,
            payload={
                "pipeline_id": pipeline_id,
                "cards_path": request.cards_path,
                "texts_path": request.texts_path,
                "output_dir": str(output_dir),
                "stages": sorted(stages),
                "status_filter": list(request.status_filter or []),
                "llm_model": request.llm_model,
                "resume": request.resume,
            },
            policy=policy,
            request_id=request_id,
        )

        return LexTriggerResponse(
            meta=_build_api_meta(request_id),
            status="accepted",
            pipeline_id=pipeline_id,
            job_id=job_id,
            effective_execution_profile=policy.effective_profile,
            message=f"Pipeline {pipeline_id} launched with stages: {', '.join(sorted(stages))}",
        )

    def _run_lex_pipeline_job(
        self,
        *,
        job: ControlJobRecord,
        payload: dict[str, Any],
        capability_manifest_ref: str,
    ) -> None:
        import asyncio

        from polisyos.data_forge.read_api.legal import BatchConfig, run_batch_pipeline

        output_dir = Path(str(payload["output_dir"]))
        progress = {
            "output_dir": str(output_dir),
            "state": "running",
            "stages": list(payload.get("stages") or []),
        }
        self._control_store.update_progress_state(
            job_id=job.job_id,
            state="running",
            progress=progress,
        )
        config = BatchConfig(
            cards_path=Path(str(payload["cards_path"])),
            texts_path=Path(str(payload["texts_path"])),
            output_dir=output_dir,
            llm_model=str(payload.get("llm_model") or ""),
            stages=frozenset(str(item) for item in (payload.get("stages") or [])),
            resume=bool(payload.get("resume")),
            status_filter=(
                frozenset(str(item) for item in (payload.get("status_filter") or []))
                if payload.get("status_filter")
                else None
            ),
        )
        try:
            asyncio.run(run_batch_pipeline(config))
        except Exception:
            raise
        final_progress = self._collect_lex_progress(
            output_dir=output_dir,
            state="completed",
            existing=progress,
        )
        self._control_store.complete_job(
            job_id=job.job_id,
            pipeline_id=job.pipeline_id,
            capability_manifest_ref=capability_manifest_ref,
            progress=final_progress,
        )
        self._emit_runtime_diagnostic_event(
            job_id=job.job_id,
            run_id=job.run_id,
            execution_profile=job.effective_execution_profile,
            phase="lex_pipeline",
            event_type="polisyos.runtime.diagnostic.phase_transition.v1",
            state_before="running",
            state_after="completed",
            payload=payload,
            event_payload={
                "job_kind": job.kind,
                "pipeline_id": job.pipeline_id,
                "progress_event_authority": "progress_reference_only",
            },
            artifact_refs=[capability_manifest_ref],
        )

    def get_lex_pipeline_status(
        self,
        pipeline_id: str,
        *,
        request_id: str | None = None,
    ) -> LexPipelineStatusResponse:
        """Return durable Lex pipeline state merged with file-backed progress summaries."""
        record = self._control_store.get_job_by_pipeline(pipeline_id)
        if record is None:
            return LexPipelineStatusResponse(
                meta=_build_api_meta(request_id),
                pipeline_id=pipeline_id,
                state="failed",
                error_message="Pipeline not found.",
            )

        info = dict(record.progress)
        output_dir_raw = str(info.get("output_dir") or "").strip()
        output_dir = Path(output_dir_raw) if output_dir_raw else None
        merged_progress = self._collect_lex_progress(
            output_dir=output_dir,
            state=record.state,
            existing=info,
        )
        if merged_progress != info:
            self._control_store.upsert_progress(job_id=record.job_id, progress=merged_progress)
            info = merged_progress
        progress_summary = dict(info.get("progress_summary") or {})

        return LexPipelineStatusResponse(
            meta=_build_api_meta(request_id),
            pipeline_id=pipeline_id,
            state=record.state,
            progress_summary=progress_summary,
            error_message=record.error_message,
        )

    def get_lex_graph_stats(
        self,
        output_dir_str: str,
        *,
        request_id: str | None = None,
    ) -> LexGraphStatsResponse:
        """Inspect a Lex DuckDB graph database and return aggregate/top-k statistics."""
        import duckdb

        db_path = Path(output_dir_str) / "lex_knowledge_graph.duckdb"

        if not db_path.exists():
            return LexGraphStatsResponse(
                meta=_build_api_meta(request_id),
                db_exists=False,
            )

        try:
            con = duckdb.connect(str(db_path), read_only=True)
            entity_row = con.execute("SELECT COUNT(*) FROM lex_entities").fetchone()
            fact_row = con.execute("SELECT COUNT(*) FROM lex_facts").fetchone()
            provision_row = con.execute("SELECT COUNT(*) FROM lex_provisions").fetchone()
            if entity_row is None or fact_row is None or provision_row is None:
                raise RuntimeError("lex graph count query returned no rows")
            entities = entity_row[0]
            facts = fact_row[0]
            provisions = provision_row[0]

            top_preds = [
                {"predicate": r[0], "count": r[1]}
                for r in con.execute(
                    "SELECT predicate, COUNT(*) AS cnt FROM lex_facts "
                    "GROUP BY predicate ORDER BY cnt DESC LIMIT 10"
                ).fetchall()
            ]

            top_types = [
                {"entity_type": r[0], "count": r[1]}
                for r in con.execute(
                    "SELECT entity_type, COUNT(*) AS cnt FROM lex_entities "
                    "GROUP BY entity_type ORDER BY cnt DESC LIMIT 10"
                ).fetchall()
            ]

            con.close()

            return LexGraphStatsResponse(
                meta=_build_api_meta(request_id),
                total_entities=entities,
                total_facts=facts,
                total_provisions=provisions,
                top_predicates=top_preds,
                top_entity_types=top_types,
                db_exists=True,
            )
        except (duckdb.Error, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Failed to read lex graph stats: %s", exc)
            return LexGraphStatsResponse(
                meta=_build_api_meta(request_id),
                db_exists=False,
            )

    def search_lex_graph(
        self,
        request: LexSearchRequest,
        *,
        request_id: str | None = None,
    ) -> LexSearchResponse:
        """Run a Lex text search against the generated knowledge graph and return ranked facts."""
        from polisyos.core.contracts.control import LexSearchResultItem

        db_path = Path(request.output_dir) / "lex_knowledge_graph.duckdb"

        if not db_path.exists():
            return LexSearchResponse(
                meta=_build_api_meta(request_id),
                query=request.query,
                results=[],
                total=0,
            )

        try:
            from polisyos.data_forge.read_api.legal import search_legal_knowledge_graph

            raw_results = search_legal_knowledge_graph(
                output_dir=request.output_dir,
                query=request.query,
                top_k=request.top_k,
            )

            items = [
                LexSearchResultItem(
                    fact_id=r.fact_id,
                    subject_name=r.subject_name,
                    predicate=r.predicate,
                    object_name=r.object_name,
                    fact_text=r.fact_text,
                    confidence=r.confidence,
                    norm_type=r.norm_type,
                    action_canon=r.action_canon,
                    norm_type_canon=r.norm_type_canon,
                    condition_text_uk=r.condition_text_uk,
                    exception_text_uk=r.exception_text_uk,
                    procedure_text_uk=r.procedure_text_uk,
                    thresholds_json=r.thresholds_json,
                    source_quote_uk=r.source_quote_uk,
                    doc_name=r.doc_name,
                    doc_reestr_code=r.doc_reestr_code,
                    provision_citation=r.provision_citation,
                )
                for r in raw_results
            ]

            return LexSearchResponse(
                meta=_build_api_meta(request_id),
                query=request.query,
                results=items,
                total=len(items),
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Lex graph search failed: %s", exc)
            return LexSearchResponse(
                meta=_build_api_meta(request_id),
                query=request.query,
                results=[],
                total=0,
            )
