"""Control Plane service — bridges HTTP layer to scientist/fabric."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from polisyos.core.contracts.control import (
    BindingProfileInfo,
    BindingProfilesListResponse,
    CacheEntryInfo,
    CacheStatusResponse,
    CapabilityFeatureInfo,
    CapabilityManifestResponse,
    ConnectorInfo,
    ConnectorsListResponse,
    DataCatalogSearchResponse,
    DataDiscoverRequest,
    DataDiscoverResponse,
    DataNeed,
    DataPreviewRequest,
    DataPreviewResponse,
    DataResolveRequest,
    DataResolveResponse,
    DataSourceBinding,
    IngestRequest,
    IngestResponse,
    IndexStatsResponse,
    ModelProfileInfo,
    ModelProfilesListResponse,
    NaturalLanguageRunRequest,
    PromotionCandidatesResponse,
    PromotionDecisionRequest,
    PromotionDecisionResponse,
    RunLaunchResponse,
    SourceProfileInfo,
    SourceProfilesListResponse,
    WorkflowRunRequest,
)
from polisyos.core.contracts.runtime import ApiMeta
from polisyos.scientist.llm.factory import create_traced_gateway_client

from .task_runner import TaskRunner

logger = logging.getLogger(__name__)


def _build_api_meta(request_id: str | None = None) -> ApiMeta:
    return ApiMeta(request_id=request_id or uuid.uuid4().hex)


# ---------------------------------------------------------------------------
# Helpers to convert string refs → ArtifactRef
# ---------------------------------------------------------------------------

def _make_artifact_ref(ref_str: str, *, kind: str, media_type: str = "application/json"):
    """Lazily import ArtifactRef and ArtifactID to avoid heavy startup cost."""
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.artifacts.ids import ArtifactID

    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(ref_str),
        kind=kind,
        media_type=media_type,
    )


_DATA_SOURCE_KEYS = {
    "data_snapshot_ref": "fabric.data_snapshot",
    "input_bindings_ref": "foundry.input_bindings",
    "data_view_request_ref": "fabric.data_view_request",
}

_OPTIONAL_INPUT_KEYS = {
    "trinity_bundle_ref": "ir.trinity_bundle",
    "policy_spec_ref": "ir.policy_spec",
    "model_spec_ref": "ir.model_spec",
    "research_intent_ref": "scholar.research_intent",
    "knowledge_bundle_ref": "scholar.knowledge_bundle",
    "norm_pack_ref": "lex.norm_pack",
    "calibration_report_ref": "foundry.calibration_report",
}


def _resolve_data_source(binding: DataSourceBinding) -> tuple[str, str]:
    """Return (state_key, ref_string) for the provided data source."""
    for field_name, kind in _DATA_SOURCE_KEYS.items():
        value = getattr(binding, field_name, None)
        if value:
            return field_name, value
    raise ValueError(
        "At least one data source must be provided: "
        "data_snapshot_ref, input_bindings_ref, or data_view_request_ref"
    )


def _as_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_multimodel_enabled() -> bool:
    return _as_bool(
        os.getenv("POLISYOS_LLM_MULTIMODEL_ENABLED"),
        default=True,
    )


def _is_required_preflight_enabled() -> bool:
    return _as_bool(os.getenv("POLISYOS_REQUIRED_PREFLIGHT_ENABLED"), default=True)


def _is_auto_materialization_enabled() -> bool:
    return _as_bool(os.getenv("POLISYOS_AUTO_MATERIALIZATION_ENABLED"), default=True)


def _is_unified_dag_enabled() -> bool:
    return _as_bool(os.getenv("POLISYOS_UNIFIED_DAG_ENABLED"), default=True)


def _normalize_model_variant_id(model_name: str, index: int) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", model_name.strip().lower()).strip("_")
    if not base:
        base = "model"
    return f"{base}_{index + 1}"


def _dedupe_models(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _now_ms() -> int:
    return int(time.time() * 1000)


def _resolve_curated_dir() -> Path:
    candidates = (
        Path("data/curated"),
        Path("policy-engine/data/curated"),
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _sum_call_events(events: list[dict[str, Any]]) -> dict[str, float]:
    prompt_tokens = 0.0
    completion_tokens = 0.0
    latency_ms = 0.0
    cost_usd = 0.0
    for event in events:
        prompt_tokens += float(event.get("prompt_tokens") or 0)
        completion_tokens += float(event.get("completion_tokens") or 0)
        latency_ms += float(event.get("latency_ms") or 0)
        cost_usd += float(event.get("cost_usd") or 0.0)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "latency_ms": latency_ms,
        "cost_usd": cost_usd,
    }


def _delta_usage(
    before: dict[str, float],
    after: dict[str, float],
) -> tuple[int, int, int, float]:
    prompt = max(0, int(after["prompt_tokens"] - before["prompt_tokens"]))
    completion = max(0, int(after["completion_tokens"] - before["completion_tokens"]))
    latency = max(0, int(after["latency_ms"] - before["latency_ms"]))
    cost = max(0.0, float(after["cost_usd"] - before["cost_usd"]))
    return prompt, completion, latency, cost


def _canonicalize_numeric_payload(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {
            key: _canonicalize_numeric_payload(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_canonicalize_numeric_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_canonicalize_numeric_payload(item) for item in value]
    return value


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class ControlPlaneService:
    """Orchestrates control-plane operations (run launch, data ingestion)."""

    def __init__(self, *, cas_root: Path, core_runs_root: Path) -> None:
        from polisyos.fabric.retrieval import RetrievalService

        self._cas_root = cas_root
        self._core_runs_root = core_runs_root
        self._task_runner = TaskRunner(max_workers=2)
        self._retrieval = RetrievalService(
            curated_dir=_resolve_curated_dir(),
            cas_root=cas_root,
        )

    # ---- Workflow launch ---------------------------------------------------

    def launch_workflow_run(
        self,
        request: WorkflowRunRequest,
        *,
        request_id: str | None = None,
    ) -> RunLaunchResponse:
        from polisyos.core.run.context import new_run_id

        run_id = new_run_id()

        # Build inputs dict
        inputs: dict[str, Any] = {}

        # Data source (required)
        ds_key, ds_value = _resolve_data_source(request.data_source)
        inputs[ds_key] = _make_artifact_ref(ds_value, kind=_DATA_SOURCE_KEYS[ds_key])

        # Optional refs
        for field_name, kind in _OPTIONAL_INPUT_KEYS.items():
            value = getattr(request, field_name, None)
            if value:
                inputs[field_name] = _make_artifact_ref(value, kind=kind)

        state_payload: dict[str, Any] = {
            "run_id": run_id,
            "inputs": inputs,
            "params": dict(request.params),
        }

        task_id = uuid.uuid4().hex
        self._task_runner.submit(
            task_id,
            run_id,
            self._execute_workflow,
            state_payload,
            request.checkpoint_policy,
        )

        return RunLaunchResponse(
            meta=_build_api_meta(request_id),
            status="accepted",
            run_id=run_id,
            message=f"Workflow run {run_id} accepted and executing in background.",
        )

    @staticmethod
    def _execute_workflow(
        state_payload: dict[str, Any],
        checkpoint_policy: str,
    ) -> None:
        from polisyos.scientist.api import run_experiment

        run_experiment(state_payload)

    # ---- NL launch (agent circuit) ----------------------------------------

    async def launch_nl_run(
        self,
        request: NaturalLanguageRunRequest,
        *,
        request_id: str | None = None,
    ) -> RunLaunchResponse:
        from polisyos.core.run.context import new_run_id

        run_id = new_run_id()
        requested_models = _dedupe_models(list(request.llm_models or []))
        if request.llm_model and request.llm_model not in requested_models:
            requested_models.insert(0, request.llm_model)
        if not _is_multimodel_enabled() and len(requested_models) > 1:
            requested_models = requested_models[:1]

        task_id = uuid.uuid4().hex
        self._task_runner.submit(
            task_id,
            run_id,
            self._execute_nl_pipeline,
            run_id,
            request.request,
            request.context,
            request.domain_hint,
            request.data_source,
            request.max_iterations,
            requested_models,
            request.max_parallel_models,
            request.run_budget_usd,
            request.per_model_budget_usd,
            request.checkpoint_policy,
            request.execution_plan_ref,
            request.execution_plan,
            request.stop_criteria,
            request.governance_constraints,
            request.expected_outputs,
        )

        models_label = ", ".join(requested_models) if requested_models else "mock agents"
        if len(requested_models) > 1:
            mode_label = (
                f"{len(requested_models)} model variants "
                f"(parallel={max(1, min(request.max_parallel_models, len(requested_models)))})"
            )
        elif requested_models:
            mode_label = "single model"
        else:
            mode_label = "mock mode"

        return RunLaunchResponse(
            meta=_build_api_meta(request_id),
            status="accepted",
            run_id=run_id,
            message=(
                f"Natural-language run {run_id} accepted. "
                f"Agent circuit will execute in {mode_label}: {models_label}."
            ),
        )

    @staticmethod
    def _execute_nl_pipeline(
        run_id: str,
        nl_request: str,
        context: dict[str, Any],
        domain_hint: str | None,
        data_source: DataSourceBinding | None,
        max_iterations: int,
        llm_models: list[str],
        max_parallel_models: int,
        run_budget_usd: float | None,
        per_model_budget_usd: float | None,
        checkpoint_policy: str,
        execution_plan_ref: str | None,
        execution_plan_payload: dict[str, Any] | None,
        stop_criteria_payload: dict[str, Any] | None,
        governance_constraints_payload: list[dict[str, Any]] | None,
        expected_outputs_payload: list[dict[str, Any]] | None,
    ) -> None:
        """Run agent circuit synchronously (called from thread pool)."""
        from polisyos.common.async_tools import run_coro_sync

        async def _agent_pipeline() -> None:
            from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
            from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
            from polisyos.core.canon import CanonSpec
            from polisyos.core.contracts.execution_plan import (
                ExecutionPlan,
                ExecutionPlanRef,
                IterationState,
                MethodCatalogSnapshot,
                MethodCatalogSnapshotRef,
                PreflightReportRef,
            )
            from polisyos.core.contracts.fabric import DataSnapshot
            from polisyos.core.contracts.foundry import (
                FoundryInputBindings,
                StateSnapshot,
                StateSnapshotRef,
            )
            from polisyos.core.registry import build_default_registry_bundle
            from polisyos.foundry.methods import (
                build_method_catalog_snapshot,
                persist_method_catalog_snapshot,
            )
            from polisyos.foundry.methods.catalog.causal import ensure_causal_methods_registered
            from polisyos.scientist.agent.critic import LLMCriticAgent, MockCriticAgent
            from polisyos.scientist.agent.data_need_extractor import (
                LLMDataNeedExtractorAgent,
                MockDataNeedExtractorAgent,
            )
            from polisyos.scientist.agent.drafter_clients import LLMDrafterAgent, MockDrafterAgent
            from polisyos.scientist.agent.formalizer import LLMFormalizerAgent, MockFormalizerAgent
            from polisyos.scientist.agent.pi import LLMPIAgent, MockPIAgent
            from polisyos.scientist.engine.iteration_state_machine import transition
            from polisyos.fabric.retrieval import RetrievalService
            from polisyos.scientist.llm_cycle import (
                build_default_execution_plan,
                build_reproducibility_manifest,
                evaluate_iteration,
                persist_evaluator_report,
                persist_execution_plan,
                persist_iteration_state,
                persist_preflight_report,
                persist_reproducibility_manifest,
                preflight_execution_plan,
            )

            store = FileSystemCAS(Path(".polisyos"))
            models_to_run = _dedupe_models(list(llm_models))
            method_catalog_snapshot_cache: dict[str, Any] = {
                "snapshot": None,
                "ref": None,
            }
            registry_bundle_ref_cache: ArtifactRef | None = None
            catalog_lock = asyncio.Lock()

            def _artifact_ref_from_sha(sha: str, *, kind: str) -> ArtifactRef:
                return _make_artifact_ref(sha, kind=kind)

            def _ensure_registry_bundle_ref() -> ArtifactRef:
                nonlocal registry_bundle_ref_cache
                if registry_bundle_ref_cache is None:
                    bundle = build_default_registry_bundle(store)
                    registry_bundle_ref_cache = bundle.bundle_ref
                return registry_bundle_ref_cache

            async def _ensure_catalog_snapshot() -> tuple[MethodCatalogSnapshot, str]:
                async with catalog_lock:
                    cached_snapshot = method_catalog_snapshot_cache.get("snapshot")
                    cached_ref = method_catalog_snapshot_cache.get("ref")
                    if isinstance(cached_snapshot, MethodCatalogSnapshot) and isinstance(cached_ref, str):
                        return cached_snapshot, cached_ref
                    ensure_causal_methods_registered()
                    snapshot = build_method_catalog_snapshot(run_id=run_id)
                    snapshot_ref = persist_method_catalog_snapshot(store, snapshot)
                    snapshot_ref_str = str(snapshot_ref.artifact_id)
                    method_catalog_snapshot_cache["snapshot"] = snapshot
                    method_catalog_snapshot_cache["ref"] = snapshot_ref_str
                    return snapshot, snapshot_ref_str

            def _materialize_retrieval_artifacts(
                *,
                variant_id: str,
                data_context_payload: dict[str, Any],
                retrieval_telemetry: dict[str, Any],
            ) -> dict[str, str]:
                payload_ref = store.put_json(
                    {
                        "model_variant_id": variant_id,
                        "data_context": data_context_payload,
                        "retrieval_telemetry": retrieval_telemetry,
                    },
                    PutOptions(
                        kind="fabric.retrieval_payload",
                        media_type="application/json",
                        schema=SchemaInfo(name="polisyos.fabric.RetrievalPayload", version="1.0"),
                    ),
                    canon_spec=CanonSpec(forbid_floats=False),
                )
                quality_ref = store.put_json(
                    {
                        "source": "retrieval_service",
                        "mode": str(retrieval_telemetry.get("mode") or "hybrid"),
                        "coverage_ok": True,
                        "warnings": list(retrieval_telemetry.get("warnings") or []),
                    },
                    PutOptions(
                        kind="fabric.quality_report",
                        media_type="application/json",
                        schema=SchemaInfo(name="polisyos.fabric.DataQualityReport", version="1.0"),
                    ),
                    canon_spec=CanonSpec(forbid_floats=False),
                )
                snapshot = DataSnapshot(
                    data_ref=payload_ref,
                    quality_report_ref=quality_ref,
                    stats={
                        "metric_count": len(data_context_payload.get("metrics") or []),
                        "metadata_docs_fetched": int(
                            data_context_payload.get("metadata_docs_fetched") or 0
                        ),
                    },
                    notes=[
                        "source:runtime_nl_retrieval",
                        f"model_variant_id:{variant_id}",
                    ],
                )
                snapshot_ref = store.put_json(
                    snapshot,
                    PutOptions(
                        kind="fabric.data_snapshot",
                        media_type="application/json",
                        schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
                        inputs=[
                            InputRef(artifact_id=payload_ref.artifact_id, role="retrieval_payload"),
                        ],
                    ),
                    canon_spec=CanonSpec(forbid_floats=False),
                )
                registry_ref = _ensure_registry_bundle_ref()
                try:
                    from polisyos.foundry.data_plane import build_input_bindings

                    bindings_result = build_input_bindings(
                        store,
                        data_snapshot_ref=_artifact_ref_from_sha(
                            str(snapshot_ref.artifact_id),
                            kind="fabric.data_snapshot",
                        ),
                        registry_bundle_ref=registry_ref,
                        rules=None,
                        notes=["runtime_nl_auto_materialization"],
                    )
                    return {
                        "data_snapshot_ref": str(snapshot_ref.artifact_id),
                        "input_bindings_ref": str(bindings_result.input_bindings_ref.artifact_id),
                        "registry_bundle_ref": str(registry_ref.artifact_id),
                        "input_binding_report_ref": str(
                            bindings_result.input_binding_report_ref.artifact_id
                        ),
                    }
                except ModuleNotFoundError:
                    # Keep pipeline runnable in lightweight environments without JAX.
                    fallback_state_ref = store.put_json(
                        {"source": "runtime_nl_auto_materialization", "jax": "missing"},
                        PutOptions(
                            kind="foundry.state_payload",
                            media_type="application/json",
                            schema=SchemaInfo(name="polisyos.foundry.StatePayload", version="0.1.0"),
                        ),
                        canon_spec=CanonSpec(forbid_floats=False),
                    )
                    fallback_snapshot = StateSnapshot(
                        state_ref=fallback_state_ref,
                        step=0,
                        notes=["fallback_state_snapshot_without_jax"],
                    )
                    fallback_snapshot_ref = store.put_json(
                        fallback_snapshot,
                        PutOptions(
                            kind="foundry.state_snapshot",
                            media_type="application/json",
                            schema=SchemaInfo(name="polisyos.core.StateSnapshot", version="1.0"),
                        ),
                        canon_spec=CanonSpec(forbid_floats=False),
                    )
                    fallback_bindings = FoundryInputBindings(
                        data_snapshot_ref=_artifact_ref_from_sha(
                            str(snapshot_ref.artifact_id),
                            kind="fabric.data_snapshot",
                        ),
                        registry_bundle_ref=registry_ref,
                        rules=[],
                        bound_state_snapshot_ref=StateSnapshotRef(
                            artifact_id=fallback_snapshot_ref.artifact_id
                        ),
                        notes=["fallback_bindings_without_jax"],
                    )
                    fallback_bindings_ref = store.put_json(
                        fallback_bindings,
                        PutOptions(
                            kind="foundry.input_bindings",
                            media_type="application/json",
                            schema=SchemaInfo(name="polisyos.core.FoundryInputBindings", version="1.0"),
                            inputs=[
                                InputRef(artifact_id=snapshot_ref.artifact_id, role="data_snapshot"),
                                InputRef(artifact_id=fallback_snapshot_ref.artifact_id, role="bound_state"),
                            ],
                        ),
                        canon_spec=CanonSpec(forbid_floats=False),
                    )
                    fallback_report_ref = store.put_json(
                        {
                            "ok": False,
                            "warnings": ["jax_not_available"],
                            "applied_rules": [],
                            "errors": [],
                        },
                        PutOptions(
                            kind="foundry.input_binding_report",
                            media_type="application/json",
                            schema=SchemaInfo(
                                name="polisyos.foundry.FoundryInputBindingReport",
                                version="1.0",
                            ),
                            inputs=[
                                InputRef(
                                    artifact_id=fallback_bindings_ref.artifact_id,
                                    role="input_bindings",
                                )
                            ],
                        ),
                        canon_spec=CanonSpec(forbid_floats=False),
                    )
                    return {
                        "data_snapshot_ref": str(snapshot_ref.artifact_id),
                        "input_bindings_ref": str(fallback_bindings_ref.artifact_id),
                        "registry_bundle_ref": str(registry_ref.artifact_id),
                        "input_binding_report_ref": str(fallback_report_ref.artifact_id),
                    }

            def _store_bundle(bundle: Any) -> str:
                ref = store.put_json(
                    bundle,
                    PutOptions(
                        kind="ir.trinity_bundle",
                        media_type="application/json",
                        schema=SchemaInfo(
                            name="polisyos.ir.TrinityBundle",
                            version=str(getattr(bundle, "schema_version", "1.0")),
                        ),
                    ),
                    canon_spec=CanonSpec(forbid_floats=False),
                )
                return str(ref.artifact_id)

            async def _run_variant(model_name: str | None, variant_index: int) -> dict[str, Any]:
                variant_started_at = _now_ms()
                variant_started_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
                call_events: list[dict[str, Any]] = []
                variant_label = model_name or "mock"
                variant_id = _normalize_model_variant_id(variant_label, variant_index)
                notes: list[str] = []
                llm_client = None
                provider = "mock"

                if model_name:
                    llm_client = create_traced_gateway_client(
                        model_name=model_name,
                        run_id=run_id,
                        model_variant_id=variant_id,
                        call_observer=call_events.append,
                    )
                    if llm_client is None:
                        notes.append("gateway_not_configured_fallback_to_mock")
                    else:
                        provider = "gateway"

                if llm_client is None:
                    pi = MockPIAgent()
                    data_need_extractor = MockDataNeedExtractorAgent()
                    drafter = MockDrafterAgent()
                    formalizer = MockFormalizerAgent()
                    critic = MockCriticAgent()
                else:
                    pi = LLMPIAgent(llm_client=llm_client, model_name=model_name)
                    data_need_extractor = LLMDataNeedExtractorAgent(
                        llm_client=llm_client,
                        model_name=model_name,
                    )
                    drafter = LLMDrafterAgent(llm_client=llm_client, model_name=model_name)
                    formalizer = LLMFormalizerAgent(llm_client=llm_client, model_name=model_name)
                    critic = LLMCriticAgent(llm_client=llm_client, model_name=model_name)

                retrieval = RetrievalService(
                    curated_dir=_resolve_curated_dir(),
                    cas_root=Path(".polisyos"),
                )

                steps: list[dict[str, Any]] = []
                retrieval_telemetry: dict[str, Any] = {}
                retrieval_mode = "hybrid"
                retrieval_lane_used = "none"
                retrieval_metadata_docs_fetched = 0
                retrieval_index_size_bytes = 0
                retrieval_index_docs_total = 0
                retrieval_candidates_filtered = 0
                retrieval_candidates_promoted = 0
                retrieval_phase_durations: dict[str, int] = {}
                data_context_payload: dict[str, Any] = {}
                auto_data_source_refs: dict[str, str] = {}
                retrieval_context_payload: dict[str, Any] = {
                    "data_needs": [],
                    "fetch_plans": [],
                    "promotion_candidates": [],
                    "auto_data_source_refs": {},
                }
                execution_plan_ref_str = execution_plan_ref
                method_catalog_snapshot_ref_str: str | None = None
                preflight_report_ref_str: str | None = None
                evaluator_report_ref_str: str | None = None
                iteration_state_ref_str: str | None = None
                reproducibility_manifest_ref_str: str | None = None
                preflight_ready = True
                preflight_diagnostics: list[dict[str, Any]] = []
                evaluator_payload: dict[str, Any] = {}

                async def _capture_step(
                    *,
                    agent: str,
                    action: str,
                    coro: Any,
                    summary: str | None = None,
                    status: str = "ok",
                    details: dict[str, Any] | None = None,
                ) -> Any:
                    before = _sum_call_events(call_events)
                    started = _now_ms()
                    result = await coro
                    after = _sum_call_events(call_events)
                    finished = _now_ms()
                    prompt_tokens, completion_tokens, llm_latency_ms, delta_cost = _delta_usage(
                        before,
                        after,
                    )
                    total_tokens = prompt_tokens + completion_tokens
                    step_latency = max(0, finished - started)
                    steps.append(
                        {
                            "attempt": 1,
                            "agent": agent,
                            "action": action,
                            "status": status,
                            "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                            "summary": summary,
                            "model": model_name,
                            "provider": provider,
                            "model_variant_id": variant_id,
                            "latency_ms": llm_latency_ms or step_latency,
                            "cost_usd": round(delta_cost, 8),
                            "token_usage": {
                                "prompt_tokens": prompt_tokens,
                                "completion_tokens": completion_tokens,
                                "total_tokens": total_tokens,
                            },
                            "details": details or {},
                        }
                    )
                    return result

                def _append_step(
                    *,
                    agent: str,
                    action: str,
                    summary: str | None = None,
                    status: str = "ok",
                    details: dict[str, Any] | None = None,
                ) -> None:
                    steps.append(
                        {
                            "attempt": 1,
                            "agent": agent,
                            "action": action,
                            "status": status,
                            "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                            "summary": summary,
                            "model": model_name,
                            "provider": provider,
                            "model_variant_id": variant_id,
                            "latency_ms": 0,
                            "cost_usd": 0.0,
                            "token_usage": {
                                "prompt_tokens": 0,
                                "completion_tokens": 0,
                                "total_tokens": 0,
                            },
                            "details": details or {},
                        }
                    )

                try:
                    problem_frame = await _capture_step(
                        agent="pi_agent",
                        action="create_problem_frame",
                        coro=pi.create_problem_frame(
                            nl_request,
                            domain_hint=domain_hint or "custom",
                        ),
                        summary="Problem frame created",
                    )
                    await pi.hold_problem_frame(problem_frame)
                    data_need_specs = await _capture_step(
                        agent="data_need_extractor",
                        action="extract_data_need",
                        coro=data_need_extractor.extract_data_needs(problem_frame),
                        summary="Data needs extracted from problem frame",
                    )
                    data_needs = [
                        DataNeed(
                            metric=spec.metric,
                            geography=spec.geography,
                            time_start=spec.time_start,
                            time_end=spec.time_end,
                            granularity=spec.granularity,
                            quality_min=spec.quality_min,
                            purpose=spec.purpose,
                        )
                        for spec in data_need_specs
                        if spec.metric
                    ]
                    if not data_needs:
                        notes.append("no_data_needs_extracted")
                    retrieval_context_payload["data_needs"] = [
                        item.model_dump(mode="json") for item in data_needs
                    ]

                    # 1) Build ExecutionPlan first and persist as the first cycle artifact.
                    if execution_plan_payload:
                        try:
                            execution_plan_data = dict(execution_plan_payload)
                            execution_plan_data["run_id"] = run_id
                            execution_plan_data["iteration"] = 1
                            if isinstance(stop_criteria_payload, dict):
                                execution_plan_data["stop_criteria"] = dict(stop_criteria_payload)
                            if isinstance(governance_constraints_payload, list):
                                execution_plan_data["governance_constraints"] = list(
                                    governance_constraints_payload
                                )
                            if isinstance(expected_outputs_payload, list):
                                execution_plan_data["expected_outputs"] = list(
                                    expected_outputs_payload
                                )
                            execution_plan = ExecutionPlan.model_validate(execution_plan_data)
                        except Exception:
                            execution_plan = build_default_execution_plan(
                                run_id=run_id,
                                data_needs=data_needs,
                                method_dag=[],
                                params={"context": context},
                                max_iterations=max_iterations,
                                run_budget_usd=run_budget_usd,
                                per_model_budget_usd=per_model_budget_usd,
                                governance_constraints=governance_constraints_payload,
                                expected_outputs=expected_outputs_payload,
                            )
                    else:
                        execution_plan = build_default_execution_plan(
                            run_id=run_id,
                            data_needs=data_needs,
                            method_dag=[],
                            params={"context": context},
                            max_iterations=max_iterations,
                            run_budget_usd=run_budget_usd,
                            per_model_budget_usd=per_model_budget_usd,
                            governance_constraints=governance_constraints_payload,
                            expected_outputs=expected_outputs_payload,
                        )

                    if not execution_plan_ref_str:
                        execution_plan_ref_obj = persist_execution_plan(store, execution_plan)
                        execution_plan_ref_str = str(execution_plan_ref_obj.artifact_id)
                    _append_step(
                        agent="planner",
                        action="build_execution_plan",
                        summary="ExecutionPlan persisted",
                        details={
                            "execution_plan_ref": execution_plan_ref_str,
                            "data_needs": len(execution_plan.data_needs),
                            "method_dag_nodes": len(execution_plan.method_dag),
                        },
                    )

                    # 2) Build and cache live method catalog snapshot for this run.
                    catalog_snapshot, method_catalog_snapshot_ref_str = await _ensure_catalog_snapshot()
                    if hasattr(formalizer, "set_method_catalog_snapshot"):
                        try:
                            formalizer.set_method_catalog_snapshot(
                                catalog_snapshot.model_dump(mode="json")
                            )
                        except Exception:
                            notes.append("formalizer_catalog_injection_failed")

                    # 3) Mandatory preflight before execution.
                    preflight_report = preflight_execution_plan(execution_plan, catalog_snapshot)
                    preflight_report.plan_ref = ExecutionPlanRef(artifact_id=execution_plan_ref_str)
                    preflight_report.catalog_snapshot_ref = MethodCatalogSnapshotRef(
                        artifact_id=method_catalog_snapshot_ref_str
                    )
                    preflight_report_ref = persist_preflight_report(
                        store,
                        preflight_report,
                        inputs=[
                            InputRef(
                                artifact_id=_artifact_ref_from_sha(
                                    execution_plan_ref_str,
                                    kind="scientist.execution_plan",
                                ).artifact_id,
                                role="execution_plan",
                            ),
                            InputRef(
                                artifact_id=_artifact_ref_from_sha(
                                    method_catalog_snapshot_ref_str,
                                    kind="foundry.method_catalog_snapshot",
                                ).artifact_id,
                                role="method_catalog_snapshot",
                            ),
                        ],
                    )
                    preflight_report_ref_str = str(preflight_report_ref.artifact_id)
                    preflight_ready = bool(preflight_report.ready_to_run)
                    preflight_diagnostics = [
                        item.model_dump(mode="json") for item in preflight_report.diagnostics
                    ]
                    _append_step(
                        agent="preflight",
                        action="validate_execution_plan",
                        summary="Preflight completed",
                        status="ok" if preflight_ready else "warn",
                        details={
                            "ready_to_run": preflight_ready,
                            "diagnostics_count": len(preflight_diagnostics),
                            "preflight_report_ref": preflight_report_ref_str,
                        },
                    )

                    iteration_state = IterationState(
                        run_id=run_id,
                        iteration=1,
                        lifecycle_state="plan_created",
                        plan_ref=ExecutionPlanRef(artifact_id=execution_plan_ref_str),
                        preflight_report_ref=PreflightReportRef(
                            artifact_id=preflight_report_ref_str
                        ),
                    )
                    iteration_state = transition(
                        iteration_state,
                        "start_preflight",
                        notes=["preflight_started"],
                    )
                    if preflight_ready:
                        iteration_state = transition(
                            iteration_state,
                            "preflight_ready",
                            notes=["ready_to_run"],
                        )
                    else:
                        iteration_state = transition(
                            iteration_state,
                            "preflight_failed",
                            notes=["replanning_required"],
                        )
                        # Lightweight replanning strategy: keep data_needs, clear method DAG.
                        execution_plan = execution_plan.model_copy(
                            update={
                                "method_dag": [],
                                "method_edges": [],
                                "notes": list(execution_plan.notes)
                                + ["replanned_after_preflight_diagnostics"],
                            }
                        )
                        execution_plan_ref_obj = persist_execution_plan(store, execution_plan)
                        execution_plan_ref_str = str(execution_plan_ref_obj.artifact_id)
                        preflight_report = preflight_execution_plan(execution_plan, catalog_snapshot)
                        preflight_report.plan_ref = ExecutionPlanRef(
                            artifact_id=execution_plan_ref_str
                        )
                        preflight_report.catalog_snapshot_ref = MethodCatalogSnapshotRef(
                            artifact_id=method_catalog_snapshot_ref_str
                        )
                        preflight_report_ref = persist_preflight_report(store, preflight_report)
                        preflight_report_ref_str = str(preflight_report_ref.artifact_id)
                        preflight_ready = bool(preflight_report.ready_to_run)
                        preflight_diagnostics = [
                            item.model_dump(mode="json") for item in preflight_report.diagnostics
                        ]
                        _append_step(
                            agent="preflight",
                            action="replan_after_diagnostics",
                            summary="ExecutionPlan replanned after preflight diagnostics",
                            status="warn",
                            details={
                                "ready_to_run": preflight_ready,
                                "diagnostics_count": len(preflight_diagnostics),
                            },
                        )
                        if preflight_ready:
                            iteration_state = transition(
                                iteration_state,
                                "replan",
                                notes=["replan_completed"],
                            )
                            iteration_state = transition(
                                iteration_state,
                                "start_preflight",
                                notes=["preflight_rerun"],
                            )
                            iteration_state = transition(
                                iteration_state,
                                "preflight_ready",
                                notes=["ready_after_replan"],
                            )
                        else:
                            notes.append("preflight_failed_after_replan")

                    iteration_state_ref = persist_iteration_state(store, iteration_state)
                    iteration_state_ref_str = str(iteration_state_ref.artifact_id)

                    resolve_request = DataResolveRequest(
                        data_needs=data_needs or [DataNeed(metric="generic.policy.context")],
                        mode="hybrid",
                        allow_explore_fallback=True,
                    )
                    resolve_outcome = await _capture_step(
                        agent="source_resolver",
                        action="resolve_fast_lane",
                        coro=asyncio.to_thread(retrieval.resolve, resolve_request),
                        summary="Resolved data needs into fetch plans",
                        details={"data_needs": len(data_needs)},
                    )
                    retrieval_telemetry = dict(resolve_outcome.telemetry)
                    retrieval_mode = str(resolve_outcome.mode)
                    retrieval_lane_used = str(
                        retrieval_telemetry.get("lane_used")
                        or retrieval_telemetry.get("lane")
                        or "none"
                    )
                    retrieval_metadata_docs_fetched = int(
                        retrieval_telemetry.get("metadata_docs_fetched") or 0
                    )
                    retrieval_index_size_bytes = int(
                        retrieval_telemetry.get("local_index_size_bytes") or 0
                    )
                    retrieval_index_docs_total = int(
                        retrieval_telemetry.get("local_index_docs_total") or 0
                    )
                    retrieval_candidates_filtered = int(
                        retrieval_telemetry.get("candidates_filtered") or 0
                    )
                    phase_rows = retrieval_telemetry.get("phases") or []
                    if isinstance(phase_rows, list):
                        for phase in phase_rows:
                            if not isinstance(phase, dict):
                                continue
                            phase_name = str(phase.get("phase") or "unknown")
                            retrieval_phase_durations[phase_name] = int(
                                phase.get("duration_ms") or 0
                            )
                            if phase_name == "discover_explore_lane":
                                _append_step(
                                    agent="source_resolver",
                                    action="discover_explore_lane",
                                    summary="ExploreLane discovery executed",
                                    details={
                                        "docs_fetched": int(phase.get("docs_fetched") or 0),
                                        "candidates_total": int(
                                            phase.get("candidates_total") or 0
                                        ),
                                        "candidates_selected": int(
                                            phase.get("candidates_selected") or 0
                                        ),
                                    },
                                )

                    execute_outcome = None
                    if resolve_outcome.fetch_plans:
                        promotion_ids_before = {
                            item.promotion_id for item in retrieval.list_promotion_candidates()
                        }
                        execute_outcome = await _capture_step(
                            agent="executor",
                            action="fetch_execute",
                            coro=asyncio.to_thread(
                                retrieval.execute_fetch_plans,
                                list(resolve_outcome.fetch_plans),
                                persist_payload=False,
                                allow_fallback=True,
                            ),
                            summary="Executed fetch plans",
                            details={"fetch_plans": len(resolve_outcome.fetch_plans)},
                        )
                        preview_rejected = sum(
                            1
                            for item in execute_outcome.previews
                            if not bool(item.preview.coverage_ok)
                        )
                        _append_step(
                            agent="executor",
                            action="preview_gate",
                            summary="Preview gate completed",
                            status="warn" if preview_rejected > 0 else "ok",
                            details={
                                "plans_total": len(execute_outcome.previews),
                                "coverage_rejected": preview_rejected,
                                "fallback_triggered": execute_outcome.fallback_triggered_count,
                            },
                        )
                        retrieval_candidates_promoted = int(execute_outcome.promoted_count)
                        promotion_candidates = [
                            item.model_dump(mode="json")
                            for item in retrieval.list_promotion_candidates()
                            if item.promotion_id not in promotion_ids_before
                        ]
                        _append_step(
                            agent="promotion_lane",
                            action="promotion_signal_emit",
                            summary="Promotion signals emitted",
                            details={"candidates_promoted": retrieval_candidates_promoted},
                        )
                        data_context_payload = {
                            "metrics": [
                                metric.model_dump(mode="json")
                                for metric in execute_outcome.data_context.metrics
                            ],
                            "metadata_docs_fetched": execute_outcome.data_context.metadata_docs_fetched,
                            "index_docs_total": execute_outcome.data_context.index_docs_total,
                            "index_size_bytes": execute_outcome.data_context.index_size_bytes,
                        }
                        retrieval_context_payload["fetch_plans"] = [
                            item.model_dump(mode="json")
                            for item in resolve_outcome.fetch_plans
                        ]
                        retrieval_context_payload["promotion_candidates"] = promotion_candidates
                    else:
                        _append_step(
                            agent="executor",
                            action="fetch_execute",
                            summary="No fetch plans resolved",
                            status="warn",
                            details={"fetch_plans": 0},
                            )

                    if _is_auto_materialization_enabled():
                        try:
                            auto_data_source_refs = _materialize_retrieval_artifacts(
                                variant_id=variant_id,
                                data_context_payload=data_context_payload or {"metrics": []},
                                retrieval_telemetry=retrieval_telemetry,
                            )
                            _append_step(
                                agent="executor",
                                action="materialize_data_artifacts",
                                summary="Retrieval materialized into DataSnapshot/InputBindings",
                                details={
                                    "data_snapshot_ref": auto_data_source_refs.get(
                                        "data_snapshot_ref"
                                    ),
                                    "input_bindings_ref": auto_data_source_refs.get(
                                        "input_bindings_ref"
                                    ),
                                },
                            )
                            retrieval_context_payload["auto_data_source_refs"] = dict(
                                auto_data_source_refs
                            )
                        except Exception as exc:
                            notes.append(f"auto_materialization_failed:{exc}")
                            _append_step(
                                agent="executor",
                                action="materialize_data_artifacts",
                                summary="Retrieval materialization failed",
                                status="warn",
                                details={"error": str(exc)},
                            )

                    draft = await _capture_step(
                        agent="drafter",
                        action="draft_policy",
                        coro=drafter.draft_policy(
                            problem_frame,
                            data_context=data_context_payload or None,
                        ),
                        summary="Draft generated",
                    )
                    trinity_bundle = await _capture_step(
                        agent="formalizer",
                        action="formalize",
                        coro=formalizer.formalize(draft),
                        summary="Trinity bundle formalized",
                    )

                    verdict = "NEEDS_REVISION"
                    issue_count = 0
                    if preflight_ready:
                        try:
                            iteration_state = transition(
                                iteration_state,
                                "start_execute",
                                notes=["execution_started"],
                            )
                            iteration_state = transition(
                                iteration_state,
                                "execute_done",
                                notes=["execution_phase_complete"],
                            )
                        except Exception:
                            notes.append("iteration_state_execute_transition_failed")
                    for iteration in range(max_iterations):
                        critique = await _capture_step(
                            agent="critic",
                            action="critique",
                            coro=critic.critique(trinity_bundle, problem_frame),
                            summary=f"Critique iteration {iteration + 1}",
                            details={"iteration": iteration + 1},
                        )
                        verdict = critique.verdict
                        issue_count = len(critique.issues)

                        usage_snapshot = _sum_call_events(call_events)
                        budget_remaining_ratio = None
                        if per_model_budget_usd is not None and float(per_model_budget_usd) > 0:
                            budget_remaining_ratio = max(
                                0.0,
                                (float(per_model_budget_usd) - float(usage_snapshot["cost_usd"]))
                                / float(per_model_budget_usd),
                            )
                        retrieval_quality = (
                            1.0
                            if retrieval_candidates_filtered == 0
                            else max(
                                0.0,
                                1.0
                                - (
                                    float(retrieval_candidates_filtered)
                                    / float(
                                        max(
                                            1,
                                            retrieval_candidates_filtered + len(data_context_payload.get("metrics", [])),
                                        )
                                    )
                                ),
                            )
                        )
                        evaluator_report = evaluate_iteration(
                            issue_count=issue_count,
                            verdict=critique.verdict,
                            retrieval_quality=retrieval_quality,
                            budget_remaining_ratio=budget_remaining_ratio,
                        )
                        evaluator_report_ref = persist_evaluator_report(
                            store,
                            evaluator_report,
                        )
                        evaluator_report_ref_str = str(evaluator_report_ref.artifact_id)
                        evaluator_payload = evaluator_report.model_dump(mode="json")
                        _append_step(
                            agent="evaluator",
                            action="score_iteration",
                            summary=f"Evaluator verdict: {evaluator_report.verdict}",
                            status="ok" if evaluator_report.verdict == "APPROVE" else "warn",
                            details={
                                "iteration": iteration + 1,
                                "verdict": evaluator_report.verdict,
                                "scores": evaluator_payload.get("scores"),
                                "evaluator_report_ref": evaluator_report_ref_str,
                            },
                        )
                        try:
                            if evaluator_report.verdict == "APPROVE":
                                iteration_state = transition(
                                    iteration_state,
                                    "approve",
                                    verdict=evaluator_report.verdict,
                                    stop_reason="approved",
                                    notes=["approved_by_evaluator"],
                                )
                            elif evaluator_report.verdict == "STOP_BUDGET":
                                iteration_state = transition(
                                    iteration_state,
                                    "stop_budget",
                                    verdict=evaluator_report.verdict,
                                    stop_reason="budget_exhausted",
                                    notes=["stopped_by_budget_guard"],
                                )
                            else:
                                iteration_state = transition(
                                    iteration_state,
                                    "replan",
                                    verdict=evaluator_report.verdict,
                                    notes=[f"replanning_due_to:{evaluator_report.verdict}"],
                                )
                        except Exception:
                            notes.append("iteration_state_evaluator_transition_failed")

                        if evaluator_report.verdict == "APPROVE":
                            verdict = "APPROVE"
                            break
                        if evaluator_report.verdict == "STOP_BUDGET":
                            verdict = "STOP_BUDGET"
                            notes.append("evaluator_stop_budget")
                            break
                        if iteration < max_iterations - 1:
                            draft = await _capture_step(
                                agent="drafter",
                                action="refine_draft",
                                coro=drafter.refine_draft(draft, critique),
                                summary="Draft refined",
                                status="warn",
                                details={"iteration": iteration + 1},
                            )
                            trinity_bundle = await _capture_step(
                                agent="formalizer",
                                action="formalize",
                                coro=formalizer.formalize(draft),
                                summary="Trinity bundle re-formalized",
                                status="warn",
                                details={"iteration": iteration + 1},
                            )
                            if preflight_ready:
                                try:
                                    iteration_state = transition(
                                        iteration_state,
                                        "start_preflight",
                                        notes=["iteration_replan_preflight_start"],
                                    )
                                    iteration_state = transition(
                                        iteration_state,
                                        "preflight_ready",
                                        notes=["iteration_replan_preflight_ready"],
                                    )
                                    iteration_state = transition(
                                        iteration_state,
                                        "start_execute",
                                        notes=["iteration_reexecution_start"],
                                    )
                                    iteration_state = transition(
                                        iteration_state,
                                        "execute_done",
                                        notes=["iteration_reexecution_done"],
                                    )
                                except Exception:
                                    notes.append("iteration_state_replan_transition_failed")
                    iteration_state_ref = persist_iteration_state(store, iteration_state)
                    iteration_state_ref_str = str(iteration_state_ref.artifact_id)
                except Exception as exc:  # pragma: no cover - defensive pipeline hardening
                    logger.exception("NL variant failed for model '%s': %s", model_name, exc)
                    return {
                        "model_variant_id": variant_id,
                        "model": model_name,
                        "provider": provider,
                        "status": "failed",
                        "verdict": "ERROR",
                        "issue_count": 0,
                        "prompt_tokens": int(_sum_call_events(call_events)["prompt_tokens"]),
                        "completion_tokens": int(_sum_call_events(call_events)["completion_tokens"]),
                        "total_tokens": int(
                            _sum_call_events(call_events)["prompt_tokens"]
                            + _sum_call_events(call_events)["completion_tokens"]
                        ),
                        "latency_ms": max(0, _now_ms() - variant_started_at),
                        "cost_usd": round(_sum_call_events(call_events)["cost_usd"], 8),
                        "started_at": variant_started_iso,
                        "finished_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                        "steps": steps,
                        "notes": notes + [f"variant_error:{exc}"],
                        "retrieval_mode": retrieval_mode,
                        "retrieval_lane_used": retrieval_lane_used,
                        "metadata_docs_fetched": retrieval_metadata_docs_fetched,
                        "local_index_size_bytes": retrieval_index_size_bytes,
                        "local_index_docs_total": retrieval_index_docs_total,
                        "candidates_filtered": retrieval_candidates_filtered,
                        "candidates_promoted": retrieval_candidates_promoted,
                        "retrieval_phase_durations": retrieval_phase_durations,
                        "retrieval_telemetry": retrieval_telemetry,
                        "execution_plan_ref": execution_plan_ref_str,
                        "method_catalog_snapshot_ref": method_catalog_snapshot_ref_str,
                        "preflight_report_ref": preflight_report_ref_str,
                        "preflight_ready": preflight_ready,
                        "preflight_diagnostics": preflight_diagnostics,
                        "evaluator_report_ref": evaluator_report_ref_str,
                        "evaluator": evaluator_payload,
                        "iteration_state_ref": iteration_state_ref_str,
                        "auto_data_source_refs": auto_data_source_refs,
                        "reproducibility_manifest_ref": reproducibility_manifest_ref_str,
                        "retrieval_context": retrieval_context_payload,
                        "_bundle": None,
                    }

                usage = _sum_call_events(call_events)
                variant_cost = round(float(usage["cost_usd"]), 8)
                status = "completed"
                if per_model_budget_usd is not None and variant_cost > float(per_model_budget_usd):
                    status = "budget_exceeded"
                    notes.append("per_model_budget_exceeded")
                if llm_client is None and model_name:
                    status = "fallback_mock"

                trinity_ref_str = _store_bundle(trinity_bundle)
                try:
                    repro_manifest = build_reproducibility_manifest(
                        run_id=run_id,
                        iteration=1,
                        seed=int(context.get("random_seed", 0) or 0),
                        plan=execution_plan,
                        registry_bundle_ref=auto_data_source_refs.get("registry_bundle_ref"),
                        method_catalog_snapshot_ref=method_catalog_snapshot_ref_str,
                        data_snapshot_ref=auto_data_source_refs.get("data_snapshot_ref"),
                        input_bindings_ref=auto_data_source_refs.get("input_bindings_ref"),
                    )
                    repro_manifest_ref = persist_reproducibility_manifest(store, repro_manifest)
                    reproducibility_manifest_ref_str = str(repro_manifest_ref.artifact_id)
                except Exception as exc:
                    notes.append(f"reproducibility_manifest_failed:{exc}")
                return {
                    "model_variant_id": variant_id,
                    "model": model_name,
                    "provider": provider,
                    "status": status,
                    "verdict": verdict,
                    "issue_count": int(issue_count),
                    "prompt_tokens": int(usage["prompt_tokens"]),
                    "completion_tokens": int(usage["completion_tokens"]),
                    "total_tokens": int(usage["prompt_tokens"] + usage["completion_tokens"]),
                    "latency_ms": max(0, _now_ms() - variant_started_at),
                    "cost_usd": variant_cost,
                    "trinity_bundle_ref": trinity_ref_str,
                    "started_at": variant_started_iso,
                    "finished_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                    "steps": steps,
                    "notes": notes,
                    "retrieval_mode": retrieval_mode,
                    "retrieval_lane_used": retrieval_lane_used,
                    "metadata_docs_fetched": retrieval_metadata_docs_fetched,
                    "local_index_size_bytes": retrieval_index_size_bytes,
                    "local_index_docs_total": retrieval_index_docs_total,
                    "candidates_filtered": retrieval_candidates_filtered,
                    "candidates_promoted": retrieval_candidates_promoted,
                    "retrieval_phase_durations": retrieval_phase_durations,
                    "retrieval_telemetry": retrieval_telemetry,
                    "execution_plan_ref": execution_plan_ref_str,
                    "method_catalog_snapshot_ref": method_catalog_snapshot_ref_str,
                    "preflight_report_ref": preflight_report_ref_str,
                    "preflight_ready": preflight_ready,
                    "preflight_diagnostics": preflight_diagnostics,
                    "evaluator_report_ref": evaluator_report_ref_str,
                    "evaluator": evaluator_payload,
                    "iteration_state_ref": iteration_state_ref_str,
                    "auto_data_source_refs": auto_data_source_refs,
                    "reproducibility_manifest_ref": reproducibility_manifest_ref_str,
                    "retrieval_context": retrieval_context_payload,
                    "_bundle": trinity_bundle,
                }

            variants: list[dict[str, Any]] = []
            if not models_to_run:
                variants.append(await _run_variant(None, 0))
            else:
                run_budget_spent = 0.0
                run_budget_stop = False
                sem = asyncio.Semaphore(max(1, min(max_parallel_models, len(models_to_run))))
                budget_lock = asyncio.Lock()

                async def _run_with_limits(idx: int, model_name: str) -> dict[str, Any]:
                    nonlocal run_budget_spent, run_budget_stop
                    async with sem:
                        async with budget_lock:
                            if run_budget_stop:
                                return {
                                    "model_variant_id": _normalize_model_variant_id(model_name, idx),
                                    "model": model_name,
                                    "provider": "gateway",
                                    "status": "skipped_budget_guard",
                                    "verdict": None,
                                    "issue_count": 0,
                                    "prompt_tokens": 0,
                                    "completion_tokens": 0,
                                    "total_tokens": 0,
                                    "latency_ms": 0,
                                    "cost_usd": 0.0,
                                    "started_at": None,
                                    "finished_at": None,
                                    "steps": [],
                                    "notes": ["run_budget_guard_prevented_start"],
                                    "_bundle": None,
                                }
                        variant = await _run_variant(model_name, idx)
                        async with budget_lock:
                            run_budget_spent += float(variant.get("cost_usd") or 0.0)
                            if run_budget_usd is not None and run_budget_spent >= float(run_budget_usd):
                                run_budget_stop = True
                        return variant

                tasks = [
                    asyncio.create_task(_run_with_limits(index, model_name))
                    for index, model_name in enumerate(models_to_run)
                ]
                variants = await asyncio.gather(*tasks)

            selected_variant: dict[str, Any] | None = None
            approved_candidates = [
                item
                for item in variants
                if item.get("_bundle") is not None and str(item.get("verdict", "")).upper() == "APPROVE"
            ]
            if approved_candidates:
                selected_variant = approved_candidates[0]
            if selected_variant is None:
                non_failed = [
                    item
                    for item in variants
                    if item.get("_bundle") is not None and item.get("status") not in {"failed"}
                ]
                if non_failed:
                    selected_variant = non_failed[0]
            if selected_variant is None:
                # Last-resort fallback guarantees a runnable workflow payload.
                selected_variant = await _run_variant(None, len(variants))
                variants.append(selected_variant)
            selected_variant["selected_for_workflow"] = True

            selected_ref = selected_variant.get("trinity_bundle_ref")
            if not isinstance(selected_ref, str):
                selected_bundle = selected_variant.get("_bundle")
                if selected_bundle is None:
                    raise RuntimeError("No valid model variant produced a Trinity bundle")
                selected_ref = _store_bundle(selected_bundle)
                selected_variant["trinity_bundle_ref"] = selected_ref

            # 8. Build state and run workflow
            inputs: dict[str, Any] = {
                "trinity_bundle_ref": _make_artifact_ref(
                    selected_ref, kind="ir.trinity_bundle"
                ),
            }

            # Add data source if provided
            if data_source:
                ds_key, ds_value = _resolve_data_source(data_source)
                inputs[ds_key] = _make_artifact_ref(
                    ds_value, kind=_DATA_SOURCE_KEYS[ds_key]
                )
            else:
                auto_refs = selected_variant.get("auto_data_source_refs")
                if isinstance(auto_refs, dict):
                    snapshot_ref = auto_refs.get("data_snapshot_ref")
                    bindings_ref = auto_refs.get("input_bindings_ref")
                    registry_ref = auto_refs.get("registry_bundle_ref")
                    if isinstance(snapshot_ref, str) and snapshot_ref:
                        inputs["data_snapshot_ref"] = _make_artifact_ref(
                            snapshot_ref,
                            kind=_DATA_SOURCE_KEYS["data_snapshot_ref"],
                        )
                    if isinstance(bindings_ref, str) and bindings_ref:
                        inputs["input_bindings_ref"] = _make_artifact_ref(
                            bindings_ref,
                            kind=_DATA_SOURCE_KEYS["input_bindings_ref"],
                        )
                    if isinstance(registry_ref, str) and registry_ref:
                        inputs["registry_bundle_ref"] = _make_artifact_ref(
                            registry_ref,
                            kind="core.registry_bundle",
                        )

            state_payload = _canonicalize_numeric_payload(
                {
                    "run_id": run_id,
                    "inputs": inputs,
                    "params": {
                        "nl_request": nl_request,
                        "agent_circuit": True,
                        "llm_model": selected_variant.get("model"),
                        "llm_models": [item.get("model") for item in variants if item.get("model")],
                        "llm_selected_variant_id": selected_variant.get("model_variant_id"),
                        "llm_prompt_tokens": int(selected_variant.get("prompt_tokens") or 0),
                        "llm_completion_tokens": int(selected_variant.get("completion_tokens") or 0),
                        "llm_cost_usd": float(selected_variant.get("cost_usd") or 0.0),
                        "run_cost_usd": round(
                            sum(float(item.get("cost_usd") or 0.0) for item in variants),
                            8,
                        ),
                        "llm_model_variants": [
                            {
                                key: value
                                for key, value in item.items()
                                if not key.startswith("_")
                            }
                            for item in variants
                        ],
                        "llm_multimodel_enabled": _is_multimodel_enabled(),
                        "run_budget_usd": run_budget_usd,
                        "per_model_budget_usd": per_model_budget_usd,
                        "max_parallel_models": max_parallel_models,
                        "checkpoint_policy": checkpoint_policy,
                        "unified_dag_enabled": _is_unified_dag_enabled(),
                        "required_preflight_enabled": _is_required_preflight_enabled(),
                        "auto_materialization_enabled": _is_auto_materialization_enabled(),
                        "retrieval_mode": selected_variant.get("retrieval_mode"),
                        "retrieval_lane_used": selected_variant.get("retrieval_lane_used"),
                        "retrieval_metadata_docs_fetched": int(
                            selected_variant.get("metadata_docs_fetched") or 0
                        ),
                        "retrieval_local_index_size_bytes": int(
                            selected_variant.get("local_index_size_bytes") or 0
                        ),
                        "retrieval_local_index_docs_total": int(
                            selected_variant.get("local_index_docs_total") or 0
                        ),
                        "retrieval_candidates_filtered": int(
                            selected_variant.get("candidates_filtered") or 0
                        ),
                        "retrieval_candidates_promoted": int(
                            selected_variant.get("candidates_promoted") or 0
                        ),
                        "retrieval_phase_durations": dict(
                            selected_variant.get("retrieval_phase_durations") or {}
                        ),
                        "retrieval_telemetry": selected_variant.get("retrieval_telemetry") or {},
                        "execution_plan_ref": selected_variant.get("execution_plan_ref"),
                        "method_catalog_snapshot_ref": selected_variant.get(
                            "method_catalog_snapshot_ref"
                        ),
                        "preflight_report_ref": selected_variant.get("preflight_report_ref"),
                        "preflight_ready": bool(selected_variant.get("preflight_ready")),
                        "preflight_diagnostics": list(
                            selected_variant.get("preflight_diagnostics") or []
                        ),
                        "evaluator_report_ref": selected_variant.get("evaluator_report_ref"),
                        "evaluator": dict(selected_variant.get("evaluator") or {}),
                        "iteration_state_ref": selected_variant.get("iteration_state_ref"),
                        "reproducibility_manifest_ref": selected_variant.get(
                            "reproducibility_manifest_ref"
                        ),
                        "stop_criteria": dict(stop_criteria_payload or {}),
                        "governance_constraints": list(governance_constraints_payload or []),
                        "expected_outputs": list(expected_outputs_payload or []),
                        "context": context,
                        "retrieval_context": dict(selected_variant.get("retrieval_context") or {}),
                    },
                }
            )
            execution_plan_ref_value = selected_variant.get("execution_plan_ref")
            if isinstance(execution_plan_ref_value, str) and execution_plan_ref_value:
                state_payload["execution_plan_ref"] = _make_artifact_ref(
                    execution_plan_ref_value,
                    kind="scientist.execution_plan",
                )
            method_catalog_ref_value = selected_variant.get("method_catalog_snapshot_ref")
            if isinstance(method_catalog_ref_value, str) and method_catalog_ref_value:
                state_payload["method_catalog_snapshot_ref"] = _make_artifact_ref(
                    method_catalog_ref_value,
                    kind="foundry.method_catalog_snapshot",
                )
            preflight_ref_value = selected_variant.get("preflight_report_ref")
            if isinstance(preflight_ref_value, str) and preflight_ref_value:
                state_payload["preflight_report_ref"] = _make_artifact_ref(
                    preflight_ref_value,
                    kind="scientist.preflight_report",
                )
            evaluator_ref_value = selected_variant.get("evaluator_report_ref")
            if isinstance(evaluator_ref_value, str) and evaluator_ref_value:
                state_payload["evaluator_report_ref"] = _make_artifact_ref(
                    evaluator_ref_value,
                    kind="scientist.evaluator_report",
                )
            iteration_ref_value = selected_variant.get("iteration_state_ref")
            if isinstance(iteration_ref_value, str) and iteration_ref_value:
                state_payload["iteration_state_ref"] = _make_artifact_ref(
                    iteration_ref_value,
                    kind="scientist.iteration_state",
                )
            repro_ref_value = selected_variant.get("reproducibility_manifest_ref")
            if isinstance(repro_ref_value, str) and repro_ref_value:
                state_payload["reproducibility_manifest_ref"] = _make_artifact_ref(
                    repro_ref_value,
                    kind="scientist.reproducibility_manifest",
                )

            from polisyos.scientist.api import run_experiment
            run_experiment(state_payload)

        run_coro_sync(_agent_pipeline())

    # ---- Data ingestion ---------------------------------------------------

    def run_data_ingestion(
        self,
        request: IngestRequest,
        *,
        request_id: str | None = None,
    ) -> IngestResponse:
        from polisyos.fabric.ingestion import ConnectorManifestSpec, DatasetFetchSpec

        datasets = [
            DatasetFetchSpec(
                connector_id=ds.connector_id,
                dataset_id=ds.dataset_id,
                filters=ds.filters,
                date_start=ds.date_start,
                date_end=ds.date_end,
            )
            for ds in request.datasets
        ]
        if request.fetch_plans:
            datasets.extend(
                DatasetFetchSpec(
                    connector_id=plan.connector_id,
                    dataset_id=plan.dataset_id,
                    filters=plan.filters,
                    date_start=plan.date_start,
                    date_end=plan.date_end,
                )
                for plan in request.fetch_plans
            )

        manifest = ConnectorManifestSpec(
            datasets=datasets,
            cache_policy=request.cache_policy if request.cache_policy != "default" else None,
        )

        # Resolve connection profile → ConnectionConfig
        connection_config = None
        connection_profile_id = request.connection_profile
        if not connection_profile_id:
            profile_ids = {plan.profile_id for plan in request.fetch_plans if plan.profile_id}
            if len(profile_ids) == 1:
                connection_profile_id = next(iter(profile_ids))
            elif len(profile_ids) > 1:
                logger.warning(
                    "Multiple profile_ids in fetch_plans; using connector defaults. "
                    "Provide connection_profile for deterministic credentials."
                )

        if connection_profile_id:
            from polisyos.fabric.connectors.profiles import SourceProfileRegistry
            from polisyos.fabric.connectors.profiles.resolver import resolve_connection_config

            profile_reg = SourceProfileRegistry.get_instance()
            profile = profile_reg.get(connection_profile_id)
            if profile:
                connection_config = resolve_connection_config(profile)

        mode = request.execution_mode
        record_ref: str | None = None
        try:
            # Record/replay takes priority over execution mode dispatch
            if request.replay_ref:
                from polisyos.fabric.data_plane.modes import run_replay_mode

                result = run_replay_mode(
                    connector_manifest=manifest,
                    source=request.source,
                    license_name=request.license_name,
                    cas_root=self._cas_root,
                    replay_ref=request.replay_ref,
                    connection_config=connection_config,
                    produce_snapshot=request.produce_data_snapshot,
                )
            elif request.record_mode:
                from polisyos.fabric.data_plane.modes import run_record_mode

                result, record_ref = run_record_mode(
                    connector_manifest=manifest,
                    source=request.source,
                    license_name=request.license_name,
                    cas_root=self._cas_root,
                    connection_config=connection_config,
                    produce_snapshot=request.produce_data_snapshot,
                )
            elif mode == "streaming_windowed":
                from polisyos.fabric.data_plane.modes import run_streaming_windowed

                result = run_streaming_windowed(
                    connector_manifest=manifest,
                    source=request.source,
                    license_name=request.license_name,
                    cas_root=self._cas_root,
                    connection_config=connection_config,
                    produce_snapshot=request.produce_data_snapshot,
                )
            elif mode == "batch_incremental":
                from polisyos.fabric.data_plane.modes import run_batch_incremental

                result = run_batch_incremental(
                    connector_manifest=manifest,
                    source=request.source,
                    license_name=request.license_name,
                    cas_root=self._cas_root,
                    connection_config=connection_config,
                    produce_snapshot=request.produce_data_snapshot,
                )
            else:
                from polisyos.fabric.data_plane.orchestrator import run_orchestrated_ingestion

                result = run_orchestrated_ingestion(
                    connector_manifest=manifest,
                    source=request.source,
                    license_name=request.license_name,
                    cas_root=self._cas_root,
                    connection_config=connection_config,
                    produce_snapshot=request.produce_data_snapshot,
                )

            # Post-ingestion: produce input bindings if requested
            input_bindings_ref: str | None = None
            if request.produce_input_bindings and request.binding_profile_id:
                input_bindings_ref = self._produce_input_bindings(
                    binding_profile_id=request.binding_profile_id,
                    data_snapshot_ref=(
                        str(result.data_snapshot_ref.artifact_id.hex)
                        if result.data_snapshot_ref
                        else None
                    ),
                )

            return IngestResponse(
                meta=_build_api_meta(request_id),
                status="completed",
                evidence_bundle_ref=(
                    str(result.evidence_bundle_ref.artifact_id.hex)
                    if result.evidence_bundle_ref
                    else None
                ),
                data_snapshot_ref=(
                    str(result.data_snapshot_ref.artifact_id.hex)
                    if result.data_snapshot_ref
                    else None
                ),
                datasets_fetched=result.datasets_fetched,
                message=f"Successfully ingested {result.datasets_fetched} dataset(s).",
                warnings=result.warnings,
                cursor_ref=result.cursor_ref,
                mode_effective=mode,
                record_ref=record_ref,
                input_bindings_ref=input_bindings_ref,
            )
        except Exception as exc:
            logger.exception("Data ingestion failed: %s", exc)
            return IngestResponse(
                meta=_build_api_meta(request_id),
                status="failed",
                datasets_fetched=0,
                message=f"Ingestion failed: {exc}",
                mode_effective=mode,
            )

    def data_resolve(
        self,
        request: DataResolveRequest,
        *,
        request_id: str | None = None,
    ) -> DataResolveResponse:
        result = self._retrieval.resolve(request)
        return DataResolveResponse(
            meta=_build_api_meta(request_id),
            mode=result.mode,
            fetch_plans=result.fetch_plans,
            candidates=result.candidates,
            warnings=result.warnings,
        )

    def data_discover(
        self,
        request: DataDiscoverRequest,
        *,
        request_id: str | None = None,
    ) -> DataDiscoverResponse:
        result = self._retrieval.discover(
            data_needs=request.data_needs,
            max_sources_per_query=request.max_sources_per_query,
            max_discovery_calls_per_source=request.max_discovery_calls_per_source,
            max_candidates_total=request.max_candidates_total,
            time_budget_ms=request.time_budget_ms,
            cost_budget_usd=request.cost_budget_usd,
        )
        return DataDiscoverResponse(
            meta=_build_api_meta(request_id),
            candidates=result.candidates,
            docs_fetched_total=result.docs_fetched_total,
            index_stats=self._retrieval.get_index_stats(),
            warnings=result.warnings,
        )

    def data_preview(
        self,
        request: DataPreviewRequest,
        *,
        request_id: str | None = None,
    ) -> DataPreviewResponse:
        result = self._retrieval.preview(
            request.fetch_plan,
            allow_fallback=request.allow_fallback,
        )
        return DataPreviewResponse(
            meta=_build_api_meta(request_id),
            preview=result.preview,
        )

    def search_data_catalog(
        self,
        *,
        metric_query: str,
        geography: str | None = None,
        limit: int = 25,
        request_id: str | None = None,
    ) -> DataCatalogSearchResponse:
        matches = self._retrieval.search_catalog(
            metric_query=metric_query,
            geography=geography,
            limit=limit,
        )
        return DataCatalogSearchResponse(
            meta=_build_api_meta(request_id),
            query=metric_query,
            matches=matches,
            total_matches=len(matches),
        )

    def get_data_index_stats(self, *, request_id: str | None = None) -> IndexStatsResponse:
        return IndexStatsResponse(
            meta=_build_api_meta(request_id),
            stats=self._retrieval.get_index_stats(),
        )

    def list_promotion_candidates(
        self,
        *,
        request_id: str | None = None,
    ) -> PromotionCandidatesResponse:
        return PromotionCandidatesResponse(
            meta=_build_api_meta(request_id),
            candidates=self._retrieval.list_promotion_candidates(),
        )

    def approve_promotion_candidate(
        self,
        promotion_id: str,
        request: PromotionDecisionRequest,
        *,
        request_id: str | None = None,
    ) -> PromotionDecisionResponse:
        updated = self._retrieval.approve_promotion(promotion_id, reason=request.reason)
        status = "approved" if updated else "rejected"
        return PromotionDecisionResponse(
            meta=_build_api_meta(request_id),
            promotion_id=promotion_id,
            status=status,
            message=(
                "Promotion candidate approved and source bindings updated."
                if updated
                else "Promotion candidate not found."
            ),
            binding_updated=updated,
        )

    def reject_promotion_candidate(
        self,
        promotion_id: str,
        request: PromotionDecisionRequest,
        *,
        request_id: str | None = None,
    ) -> PromotionDecisionResponse:
        updated = self._retrieval.reject_promotion(promotion_id, reason=request.reason)
        return PromotionDecisionResponse(
            meta=_build_api_meta(request_id),
            promotion_id=promotion_id,
            status="rejected",
            message=(
                "Promotion candidate rejected."
                if updated
                else "Promotion candidate not found."
            ),
            binding_updated=False,
        )

    def _produce_input_bindings(
        self,
        *,
        binding_profile_id: str,
        data_snapshot_ref: str | None,
    ) -> str | None:
        """Resolve binding profile and persist rules as a CAS artifact."""
        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.fabric.connectors.bindings import BindingProfileRegistry
        from polisyos.fabric.connectors.bindings.resolver import persist_binding_rules_artifact

        registry = BindingProfileRegistry.get_instance()
        profile = registry.get(binding_profile_id)
        if profile is None:
            logger.warning("Binding profile '%s' not found", binding_profile_id)
            return None

        store = FileSystemCAS(self._cas_root)
        ref = persist_binding_rules_artifact(
            store, profile, data_snapshot_ref=data_snapshot_ref,
        )
        return str(ref.artifact_id.hex)

    # ---- Connectors listing -----------------------------------------------

    def list_connectors(self, *, request_id: str | None = None) -> ConnectorsListResponse:
        from polisyos.fabric.connectors.profiles import SourceProfileRegistry
        from polisyos.fabric.connectors.registry import ConnectorRegistry

        registry = ConnectorRegistry.get_instance()
        profile_reg = SourceProfileRegistry.get_instance()
        infos: list[ConnectorInfo] = []

        for entry in registry.query_entries():
            meta = entry.metadata
            family_profiles = profile_reg.list_by_family(meta.namespace)
            infos.append(
                ConnectorInfo(
                    connector_id=meta.fully_qualified_id,
                    namespace=meta.namespace,
                    version=meta.version,
                    known_datasets=sorted(entry.known_datasets),
                    loaded=entry.loaded,
                    last_health_check=entry.last_health_check,
                    available_profiles=[p.profile_id for p in family_profiles],
                )
            )

        return ConnectorsListResponse(
            meta=_build_api_meta(request_id),
            connectors=infos,
        )

    # ---- Source profiles --------------------------------------------------

    def list_source_profiles(
        self, *, request_id: str | None = None
    ) -> SourceProfilesListResponse:
        from polisyos.fabric.connectors.profiles import SourceProfileRegistry
        from polisyos.fabric.connectors.registry import ConnectorRegistry

        profile_reg = SourceProfileRegistry.get_instance()
        connector_reg = ConnectorRegistry.get_instance()

        # Determine which connector families are registered
        registered_families: set[str] = set()
        for entry in connector_reg.query_entries():
            registered_families.add(entry.metadata.namespace)

        profiles = profile_reg.list_all()
        infos = [
            SourceProfileInfo(
                profile_id=p.profile_id,
                display_name=p.display_name,
                description=p.description,
                connector_family=p.connector_family,
                base_url=p.base_url,
                auth_policy=p.auth_policy,
                tags=p.tags,
                source_organization=p.source_organization,
                estimated_datasets=p.estimated_datasets,
                connector_available=(p.connector_family in registered_families),
            )
            for p in profiles
        ]

        return SourceProfilesListResponse(
            meta=_build_api_meta(request_id),
            profiles=infos,
        )

    # ---- LLM model profiles -----------------------------------------------

    def list_model_profiles(
        self, *, request_id: str | None = None
    ) -> ModelProfilesListResponse:
        from polisyos.scientist.llm.profiles import ModelProfileRegistry

        profile_reg = ModelProfileRegistry.get_instance()
        profiles = profile_reg.list_all()
        infos = [
            ModelProfileInfo(
                profile_id=p.profile_id,
                display_name=p.display_name,
                description=p.description,
                provider=p.provider,
                model_id=p.model_id,
                base_url=p.base_url,
                tags=p.tags,
                capabilities=p.capabilities,
                input_cost_per_mtoken_usd=p.input_cost_per_mtoken_usd,
                output_cost_per_mtoken_usd=p.output_cost_per_mtoken_usd,
                enabled=p.enabled,
            )
            for p in profiles
        ]
        return ModelProfilesListResponse(
            meta=_build_api_meta(request_id),
            profiles=infos,
        )

    # ---- Binding profiles -------------------------------------------------

    def list_binding_profiles(
        self, *, request_id: str | None = None
    ) -> BindingProfilesListResponse:
        from polisyos.fabric.connectors.bindings import BindingProfileRegistry

        registry = BindingProfileRegistry.get_instance()
        profiles = registry.list_all()
        infos = [
            BindingProfileInfo(
                profile_id=p.profile_id,
                display_name=p.display_name,
                description=p.description,
                schema_family=p.schema_family,
                strategy=p.strategy,
                rule_count=len(p.rules),
                expected_columns=p.expected_columns,
                tags=p.tags,
            )
            for p in profiles
        ]
        return BindingProfilesListResponse(
            meta=_build_api_meta(request_id),
            profiles=infos,
        )

    # ---- Cache status -----------------------------------------------------

    def get_cache_status(self, *, request_id: str | None = None) -> CacheStatusResponse:
        # CacheStore uses SQLite; for now return a basic response
        # Production version should query ConnectorCacheStore
        return CacheStatusResponse(
            meta=_build_api_meta(request_id),
            total_entries=0,
            total_size_bytes=0,
            entries=[],
        )

    # ---- Capabilities -----------------------------------------------------

    def get_capabilities(
        self, *, request_id: str | None = None
    ) -> CapabilityManifestResponse:
        features = [
            CapabilityFeatureInfo(
                key="workflow_runs",
                label="Workflow runs",
                description="Launch workflow-backed runs from explicit artifact bindings.",
                category="runs",
                enabled=True,
            ),
            CapabilityFeatureInfo(
                key="natural_language_runs",
                label="Natural-language runs",
                description="Use the agent circuit to transform NL requests into executable policy runs.",
                category="runs",
                enabled=True,
            ),
            CapabilityFeatureInfo(
                key="multimodel_nl",
                label="Multi-model NL execution",
                description="Evaluate multiple LLM variants for a single NL request.",
                category="runs",
                enabled=_is_multimodel_enabled(),
            ),
            CapabilityFeatureInfo(
                key="required_preflight",
                label="Required preflight",
                description="Run execution-plan preflight diagnostics before execution.",
                category="governance",
                enabled=_is_required_preflight_enabled(),
            ),
            CapabilityFeatureInfo(
                key="evaluator_reports",
                label="Evaluator reports",
                description="Persist evaluator verdicts, scores, and replanning hints.",
                category="governance",
                enabled=True,
            ),
            CapabilityFeatureInfo(
                key="reproducibility_manifests",
                label="Reproducibility manifests",
                description="Expose replay, hash, and determinism metadata for completed runs.",
                category="governance",
                enabled=True,
            ),
            CapabilityFeatureInfo(
                key="transport_summary",
                label="Transport summary",
                description="Expose transportability summaries on governance and decision surfaces.",
                category="governance",
                enabled=True,
            ),
            CapabilityFeatureInfo(
                key="promotion_lane",
                label="Promotion lane",
                description="Review and approve ExploreLane candidates into reusable bindings.",
                category="evidence",
                enabled=True,
            ),
            CapabilityFeatureInfo(
                key="auto_materialization",
                label="Auto materialization",
                description="Materialize retrieval results into snapshots or bindings during NL execution.",
                category="evidence",
                enabled=_is_auto_materialization_enabled(),
            ),
            CapabilityFeatureInfo(
                key="binding_profiles",
                label="Binding profiles",
                description="List reusable binding-profile strategies for structured inputs.",
                category="evidence",
                enabled=True,
            ),
            CapabilityFeatureInfo(
                key="source_profiles",
                label="Source profiles",
                description="List curated connector/source profiles for ingestion and retrieval.",
                category="evidence",
                enabled=True,
            ),
            CapabilityFeatureInfo(
                key="lex_pipeline",
                label="Lex knowledge pipeline",
                description="Trigger, inspect, and search the legal knowledge graph pipeline.",
                category="knowledge",
                enabled=True,
            ),
            CapabilityFeatureInfo(
                key="unified_dag",
                label="Unified DAG",
                description="Expose unified method DAG execution in NL and workflow paths.",
                category="runtime",
                enabled=_is_unified_dag_enabled(),
            ),
            CapabilityFeatureInfo(
                key="security_admin_layer",
                label="Security / admin layer",
                description="Dedicated tenant/authz/audit admin surfaces.",
                category="platform",
                enabled=False,
                stage="deferred",
            ),
        ]

        return CapabilityManifestResponse(
            meta=_build_api_meta(request_id),
            workspaces=[
                "command_center",
                "scenario_composer",
                "runs_decisions",
                "evidence_fabric",
                "lex_knowledge",
                "platform_health",
            ],
            features=features,
            constraints={
                "max_parallel_models": 16,
                "max_nl_iterations": 10,
                "artifact_preview_max_bytes": 2_000_000,
                "task_runner": "in_process_thread_pool",
                "default_locale": "en",
                "supported_locales": ["en", "uk"],
            },
        )

    # ---- Lex Knowledge Graph -----------------------------------------------

    def trigger_lex_pipeline(
        self,
        request: "LexTriggerRequest",
        *,
        request_id: str | None = None,
    ) -> "LexTriggerResponse":
        from polisyos.core.contracts.control import LexTriggerResponse

        pipeline_id = f"lex_{uuid.uuid4().hex[:12]}"
        output_dir = Path(request.output_dir)

        # Build stage set from config
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
                message="No stages selected.",
            )

        # Store pipeline metadata for status tracking
        if not hasattr(self, "_lex_pipelines"):
            self._lex_pipelines: dict[str, dict[str, Any]] = {}

        self._lex_pipelines[pipeline_id] = {
            "output_dir": str(output_dir),
            "state": "running",
            "error": None,
        }

        def _run_lex_batch() -> None:
            import asyncio

            from polisyos.lex.batch.config import BatchConfig
            from polisyos.lex.batch.pipeline import run_batch_pipeline

            try:
                config = BatchConfig(
                    cards_path=Path(request.cards_path),
                    texts_path=Path(request.texts_path),
                    output_dir=output_dir,
                    llm_model=request.llm_model,
                    stages=frozenset(stages),
                    resume=request.resume,
                    status_filter=(
                        frozenset(request.status_filter)
                        if request.status_filter
                        else None
                    ),
                )
                asyncio.run(run_batch_pipeline(config))
                self._lex_pipelines[pipeline_id]["state"] = "completed"
            except Exception as exc:
                logger.exception("Lex pipeline %s failed: %s", pipeline_id, exc)
                self._lex_pipelines[pipeline_id]["state"] = "failed"
                self._lex_pipelines[pipeline_id]["error"] = str(exc)[:500]

        self._task_runner.submit(pipeline_id, pipeline_id, _run_lex_batch)

        return LexTriggerResponse(
            meta=_build_api_meta(request_id),
            status="accepted",
            pipeline_id=pipeline_id,
            message=f"Pipeline {pipeline_id} launched with stages: {', '.join(sorted(stages))}",
        )

    def get_lex_pipeline_status(
        self,
        pipeline_id: str,
        *,
        request_id: str | None = None,
    ) -> "LexPipelineStatusResponse":
        from polisyos.core.contracts.control import LexPipelineStatusResponse

        pipelines = getattr(self, "_lex_pipelines", {})
        info = pipelines.get(pipeline_id)

        if info is None:
            return LexPipelineStatusResponse(
                meta=_build_api_meta(request_id),
                pipeline_id=pipeline_id,
                state="failed",
                error_message="Pipeline not found.",
            )

        # Try to read progress summary from output_dir
        progress_summary: dict[str, int] = {}
        try:
            from polisyos.lex.batch.progress import ProgressTracker

            output_dir = Path(info["output_dir"])
            progress_path = output_dir / "progress.jsonl"
            if progress_path.exists():
                tracker = ProgressTracker(progress_path)
                progress_summary = tracker.summary()
        except Exception:
            pass

        return LexPipelineStatusResponse(
            meta=_build_api_meta(request_id),
            pipeline_id=pipeline_id,
            state=info.get("state", "pending"),
            progress_summary=progress_summary,
            error_message=info.get("error"),
        )

    def get_lex_graph_stats(
        self,
        output_dir_str: str,
        *,
        request_id: str | None = None,
    ) -> "LexGraphStatsResponse":
        import duckdb

        from polisyos.core.contracts.control import LexGraphStatsResponse

        db_path = Path(output_dir_str) / "lex_knowledge_graph.duckdb"

        if not db_path.exists():
            return LexGraphStatsResponse(
                meta=_build_api_meta(request_id),
                db_exists=False,
            )

        try:
            con = duckdb.connect(str(db_path), read_only=True)
            entities = con.execute("SELECT COUNT(*) FROM lex_entities").fetchone()[0]
            facts = con.execute("SELECT COUNT(*) FROM lex_facts").fetchone()[0]
            provisions = con.execute("SELECT COUNT(*) FROM lex_provisions").fetchone()[0]

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
        except Exception as exc:
            logger.warning("Failed to read lex graph stats: %s", exc)
            return LexGraphStatsResponse(
                meta=_build_api_meta(request_id),
                db_exists=False,
            )

    def search_lex_graph(
        self,
        request: "LexSearchRequest",
        *,
        request_id: str | None = None,
    ) -> "LexSearchResponse":
        from polisyos.core.contracts.control import (
            LexSearchResponse,
            LexSearchResultItem,
        )

        db_path = Path(request.output_dir) / "lex_knowledge_graph.duckdb"

        if not db_path.exists():
            return LexSearchResponse(
                meta=_build_api_meta(request_id),
                query=request.query,
                results=[],
                total=0,
            )

        try:
            from polisyos.lex.knowledge.store import LegalKnowledgeStore

            store = LegalKnowledgeStore(
                db_path=db_path,
                index_dir=Path(request.output_dir),
            )
            try:
                raw_results = store.text_search_facts(
                    request.query,
                    top_k=request.top_k,
                )
            finally:
                store.close()

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
        except Exception as exc:
            logger.warning("Lex graph search failed: %s", exc)
            return LexSearchResponse(
                meta=_build_api_meta(request_id),
                query=request.query,
                results=[],
                total=0,
            )


__all__ = ["ControlPlaneService"]
