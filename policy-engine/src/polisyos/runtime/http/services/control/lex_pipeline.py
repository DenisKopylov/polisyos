"""Lex pipeline control-plane endpoint behavior."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from polisyos.common.logger import get_logger
from polisyos.core.contracts.control import (
    LexGraphStatsResponse,
    LexPipelineStatusResponse,
    LexSearchRequest,
    LexTriggerRequest,
    LexTriggerResponse,
)

from .._control_contracts import _build_api_meta
from .lex_search_profile import (
    LexSearchProfileAvailableResponse,
    LexSearchProfileRefusedResponse,
    LexSearchProfileResponse,
    selected_legal_fact_query_intent,
)
from .lex_search_projection import LexSearchResponse, LexSearchResultItem

if TYPE_CHECKING:
    from polisyos.lex.knowledge.store import LegalQueryProfile
    from polisyos.runtime.http.container import LegalQueryEncoderProvider
    from polisyos.runtime.http.execution_policy import RuntimePrincipal

    from ..control_plane_store import ControlJobExecutionScope, ControlJobRecord

logger = get_logger(__name__)


def _legal_query_profiles_from_request(
    request: LexSearchRequest,
) -> tuple[LegalQueryProfile, ...]:
    """Convert exact request snapshots to immutable Legal owner profiles."""
    from polisyos.lex.knowledge.store import LegalQueryProfile, LegalQueryProfileError

    intent = request.query_generation_intent
    if intent is None:
        raise LegalQueryProfileError("query_profile_unavailable")
    if not intent:
        raise LegalQueryProfileError("query_profile_malformed")

    profiles: list[LegalQueryProfile] = []
    for item in intent:
        try:
            inventory = json.loads(item.inventory_json)
            canonical_inventory = json.dumps(
                inventory,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise LegalQueryProfileError("query_profile_malformed") from exc
        if (
            not isinstance(inventory, dict)
            or canonical_inventory != item.inventory_json
            or not isinstance(inventory.get("basis"), dict)
            or inventory["basis"].get("basis_kind") != item.basis_kind
        ):
            raise LegalQueryProfileError("query_profile_malformed")
        profiles.append(
            LegalQueryProfile(
                basis_kind=item.basis_kind,
                generation_id=item.generation_id,
                inventory_bytes=canonical_inventory.encode("utf-8"),
            )
        )
    return tuple(profiles)


class LexPipelineMixin:
    """Lex batch-pipeline endpoints for the control-plane service."""

    def bind_legal_query_encoder_provider(
        self,
        provider: LegalQueryEncoderProvider | None,
    ) -> None:
        """Bind the runtime-composed Legal encoder owner, if one is configured."""
        from polisyos.runtime.http.container import LegalQueryEncoderProvider

        if provider is not None and type(provider) is not LegalQueryEncoderProvider:
            raise TypeError("legal_query_encoder_provider_invalid")
        self._legal_query_encoder_provider = provider

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
        execution_scope: ControlJobExecutionScope,
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
            execution_scope=execution_scope,
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

    def get_lex_search_profile(
        self,
        output_dir: str,
        *,
        request_id: str | None = None,
    ) -> LexSearchProfileResponse:
        """Return the selected fact-generation snapshot for a search request."""
        from polisyos.lex.knowledge.store import LegalQueryProfileError

        try:
            intent = selected_legal_fact_query_intent(output_dir)
        except LegalQueryProfileError as exc:
            return LexSearchProfileRefusedResponse(
                meta=_build_api_meta(request_id),
                status="refused",
                output_dir=output_dir,
                refusal_code=exc.code,
            )

        return LexSearchProfileAvailableResponse(
            meta=_build_api_meta(request_id),
            status="available",
            output_dir=output_dir,
            query_generation_intent=intent,
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
        """Search Lex facts, preserving text fallback and typed vector refusal."""
        db_path = Path(request.output_dir) / "lex_knowledge_graph.duckdb"

        from polisyos.lex.knowledge.store import LegalQueryProfileError

        profile_error: LegalQueryProfileError | None = None
        try:
            query_profile = _legal_query_profiles_from_request(request)
        except LegalQueryProfileError as exc:
            query_profile = None
            profile_error = exc

        if not db_path.exists():
            return LexSearchResponse(
                meta=_build_api_meta(request_id),
                query=request.query,
                results=[],
                total=0,
                search_mode="text",
                vector_refusal_code=profile_error.code
                if profile_error is not None
                else "selected_generation_unavailable"
                if query_profile is not None
                else None,
            )

        try:
            import duckdb

            from polisyos.lex import LegalKnowledgeGraph

            query_encoder: object | None = None
            provider_error: LegalQueryProfileError | None = None
            provider = getattr(self, "_legal_query_encoder_provider", None)
            if profile_error is None and provider is not None:
                from polisyos.runtime.http.container import (
                    LegalQueryEncoderProvider,
                    LegalQueryEncoderProviderError,
                )

                if type(provider) is not LegalQueryEncoderProvider:
                    provider_error = LegalQueryProfileError("query_encoder_provider_invalid")
                else:
                    try:
                        query_encoder = provider.resolve_encoder()
                    except LegalQueryEncoderProviderError as exc:
                        provider_error = LegalQueryProfileError(exc.code)

            graph = LegalKnowledgeGraph(
                db_path=db_path,
                index_dir=Path(request.output_dir),
                query_encoder=query_encoder,
                query_profile=query_profile,
            )
            try:
                if profile_error is None and provider_error is None:
                    raw_results = graph.hybrid_search(
                        request.query,
                        top_k=request.top_k,
                        trust_tier=None,
                        include_candidates=False,
                    )
                    refusal_code = (
                        graph.query_profile_error.code
                        if graph.query_profile_error is not None
                        else None
                    )
                    search_mode = "vector" if refusal_code is None else "text"
                else:
                    raw_results = graph.text_search(
                        request.query,
                        top_k=request.top_k,
                        trust_tier=None,
                        include_candidates=False,
                    )
                    refusal_code = (
                        profile_error.code if profile_error is not None else provider_error.code
                    )
                    search_mode = "text"
            finally:
                graph.close()

            items = [
                LexSearchResultItem.model_validate(result.model_dump(mode="python"))
                for result in raw_results
            ]

            return LexSearchResponse(
                meta=_build_api_meta(request_id),
                query=request.query,
                results=items,
                total=len(items),
                search_mode=search_mode,
                vector_refusal_code=refusal_code,
            )
        except (
            duckdb.Error,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as exc:
            logger.warning("Lex graph search failed: %s", exc)
            return LexSearchResponse(
                meta=_build_api_meta(request_id),
                query=request.query,
                results=[],
                total=0,
                search_mode="text",
                vector_refusal_code="lex_search_failed",
            )
