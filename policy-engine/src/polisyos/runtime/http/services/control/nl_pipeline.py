"""Natural-language run lifecycle for the runtime control-plane service."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from polisyos.common.async_tools import run_blocking_async
from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.control import (
    DataNeed,
    DataResolveRequest,
    DataSourceBinding,
)
from polisyos.runtime.http.services.control.artifacts import (
    _make_artifact_ref,
    _resolve_curated_dir,
    _typed_artifact_ref,
)
from polisyos.runtime.http.services.control.response_shapes import (
    _build_scientist_v2_shadow_comparison,
    _canonicalize_numeric_payload,
    _delta_usage,
    _sum_call_events,
)
from polisyos.scientist.orchestration.llm.factory import create_traced_gateway_client

from .._control_contracts import (
    _DATA_SOURCE_KEYS,
    _dedupe_models,
    _is_auto_materialization_enabled,
    _is_multimodel_enabled,
    _is_required_preflight_enabled,
    _is_scientist_reflexion_enabled,
    _is_scientist_shadow_mode,
    _is_scientist_swarm_enabled,
    _is_scientist_v2_enabled,
    _is_scientist_web_search_enabled,
    _is_unified_dag_enabled,
    _MethodCatalogSnapshotAware,
    _normalize_model_variant_id,
    _now_ms,
    _resolve_data_source,
)

logger = get_logger(__name__)

class NaturalLanguageRunMixin:
    """Natural-language runtime path split out of ControlPlaneService."""

    def _execute_nl_pipeline(
        self,
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
        control_job_id: str | None = None,
        execution_profile: str | None = None,
        capability_manifest_ref: str | None = None,
        allow_mock_fallback: bool = True,
        capability_manifest_updater: Any | None = None,
    ) -> dict[str, Any]:
        """Run agent circuit synchronously for a durable control-plane job."""
        from polisyos.common.async_tools import run_coro_sync

        async def _agent_pipeline() -> dict[str, Any]:
            from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
            from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
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
            from polisyos.fabric.retrieval import RetrievalService
            from polisyos.foundry.methods import (
                build_method_catalog_snapshot,
                persist_method_catalog_snapshot,
            )
            from polisyos.foundry.methods.catalog import (
                ensure_all_methods_registered as ensure_causal_methods_registered,
            )
            from polisyos.scientist.agent.critic import LLMCriticAgent, MockCriticAgent
            from polisyos.scientist.agent.data_need_extractor import (
                LLMDataNeedExtractorAgent,
                MockDataNeedExtractorAgent,
            )
            from polisyos.scientist.agent.drafter_clients import LLMDrafterAgent, MockDrafterAgent
            from polisyos.scientist.agent.formalizer import LLMFormalizerAgent, MockFormalizerAgent
            from polisyos.scientist.agent.pi import LLMPIAgent, MockPIAgent
            from polisyos.scientist.orchestration.engine.iteration_state_machine import transition
            from polisyos.scientist.orchestration.llm.cycle import (
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

            store = self._artifact_store
            async_store = self._async_artifact_store
            models_to_run = _dedupe_models(list(llm_models))
            current_capability_manifest_ref = capability_manifest_ref
            if not models_to_run and not allow_mock_fallback:
                raise RuntimeError("mock_fallback_disallowed")
            method_catalog_snapshot_cache: dict[str, Any] = {
                "snapshot": None,
                "ref": None,
            }
            registry_bundle_ref_cache: ArtifactRef | None = None
            catalog_lock = asyncio.Lock()

            def _artifact_ref_from_sha(sha: str, *, kind: str) -> ArtifactRef:
                return _make_artifact_ref(sha, kind=kind)

            async def _ensure_registry_bundle_ref() -> ArtifactRef:
                nonlocal registry_bundle_ref_cache
                if registry_bundle_ref_cache is None:
                    bundle = await run_blocking_async(build_default_registry_bundle, store)
                    registry_bundle_ref = bundle.bundle_ref
                    if registry_bundle_ref is None:
                        raise RuntimeError(
                            "default registry bundle did not produce an artifact reference"
                        )
                    registry_bundle_ref_cache = registry_bundle_ref
                if registry_bundle_ref_cache is None:
                    raise RuntimeError("default registry bundle ref cache was not populated")
                return registry_bundle_ref_cache

            async def _ensure_catalog_snapshot() -> tuple[MethodCatalogSnapshot, str]:
                async with catalog_lock:
                    cached_snapshot = method_catalog_snapshot_cache.get("snapshot")
                    cached_ref = method_catalog_snapshot_cache.get("ref")
                    if isinstance(cached_snapshot, MethodCatalogSnapshot) and isinstance(
                        cached_ref, str
                    ):
                        return cached_snapshot, cached_ref
                    ensure_causal_methods_registered()
                    snapshot = build_method_catalog_snapshot(run_id=run_id)
                    snapshot_ref = await run_blocking_async(
                        persist_method_catalog_snapshot,
                        store,
                        snapshot,
                    )
                    snapshot_ref_str = str(snapshot_ref.artifact_id)
                    method_catalog_snapshot_cache["snapshot"] = snapshot
                    method_catalog_snapshot_cache["ref"] = snapshot_ref_str
                    return snapshot, snapshot_ref_str

            async def _materialize_retrieval_artifacts(
                *,
                variant_id: str,
                data_context_payload: dict[str, Any],
                retrieval_telemetry: dict[str, Any],
            ) -> dict[str, str]:
                payload_ref = await async_store.put_json(
                    {
                        "model_variant_id": variant_id,
                        "data_context": data_context_payload,
                        "retrieval_telemetry": retrieval_telemetry,
                    },
                    ArtifactWriteOptions(
                        kind="fabric.retrieval_payload",
                        media_type="application/json",
                        schema=SchemaInfo(name="polisyos.fabric.RetrievalPayload", version="1.0"),
                    ),
                    canon_spec=CanonSpec(forbid_floats=False),
                )
                quality_ref = await async_store.put_json(
                    {
                        "source": "retrieval_service",
                        "mode": str(retrieval_telemetry.get("mode") or "hybrid"),
                        "coverage_ok": True,
                        "warnings": list(retrieval_telemetry.get("warnings") or []),
                    },
                    ArtifactWriteOptions(
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
                snapshot_ref = await async_store.put_json(
                    snapshot,
                    ArtifactWriteOptions(
                        kind="fabric.data_snapshot",
                        media_type="application/json",
                        schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
                        inputs=[
                            InputRef(artifact_id=payload_ref.artifact_id, role="retrieval_payload"),
                        ],
                    ),
                    canon_spec=CanonSpec(forbid_floats=False),
                )
                registry_ref = await _ensure_registry_bundle_ref()
                try:
                    from polisyos.foundry.data_plane import build_input_bindings

                    bindings_result = await run_blocking_async(
                        build_input_bindings,
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
                    fallback_state_ref = await async_store.put_json(
                        {"source": "runtime_nl_auto_materialization", "jax": "missing"},
                        ArtifactWriteOptions(
                            kind="foundry.state_payload",
                            media_type="application/json",
                            schema=SchemaInfo(
                                name="polisyos.foundry.StatePayload", version="0.1.0"
                            ),
                        ),
                        canon_spec=CanonSpec(forbid_floats=False),
                    )
                    fallback_snapshot = StateSnapshot(
                        schema_version="2.0",
                        state_ref=fallback_state_ref,
                        step=0,
                        notes=["fallback_state_snapshot_without_jax"],
                    )
                    fallback_snapshot_ref = await async_store.put_json(
                        fallback_snapshot,
                        ArtifactWriteOptions(
                            kind="foundry.state_snapshot",
                            media_type="application/json",
                            schema=SchemaInfo(name="polisyos.core.StateSnapshot", version="1.0"),
                        ),
                        canon_spec=CanonSpec(forbid_floats=False),
                    )
                    fallback_bindings = FoundryInputBindings(
                        schema_version="1.0",
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
                    fallback_bindings_ref = await async_store.put_json(
                        fallback_bindings,
                        ArtifactWriteOptions(
                            kind="foundry.input_bindings",
                            media_type="application/json",
                            schema=SchemaInfo(
                                name="polisyos.core.FoundryInputBindings", version="1.0"
                            ),
                            inputs=[
                                InputRef(
                                    artifact_id=snapshot_ref.artifact_id, role="data_snapshot"
                                ),
                                InputRef(
                                    artifact_id=fallback_snapshot_ref.artifact_id,
                                    role="bound_state",
                                ),
                            ],
                        ),
                        canon_spec=CanonSpec(forbid_floats=False),
                    )
                    fallback_report_ref = await async_store.put_json(
                        {
                            "ok": False,
                            "warnings": ["jax_not_available"],
                            "applied_rules": [],
                            "errors": [],
                        },
                        ArtifactWriteOptions(
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

            async def _store_bundle(bundle: Any) -> str:
                ref = await async_store.put_json(
                    bundle,
                    ArtifactWriteOptions(
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
                nonlocal current_capability_manifest_ref
                variant_started_at = _now_ms()
                variant_started_iso = datetime.now(UTC).replace(microsecond=0).isoformat()
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
                        tracer=self._tracer,
                        metrics=self._metrics,
                    )
                    if llm_client is None:
                        if not allow_mock_fallback:
                            raise RuntimeError("mock_fallback_disallowed")
                        notes.append("gateway_not_configured_fallback_to_mock")
                        if callable(capability_manifest_updater):
                            current_capability_manifest_ref = capability_manifest_updater(
                                ["gateway_not_configured_fallback_to_mock"]
                            )
                    else:
                        provider = "gateway"
                elif not allow_mock_fallback:
                    raise RuntimeError("mock_fallback_disallowed")

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
                    cas_root=Path(".polisyos/cas"),
                    providers=self._build_retrieval_providers(),
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
                fabric_result = None
                fabric_shadow_result = None
                fabric_shadow_task = None
                fabric_shadow_comparison = None

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
                            "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat(),
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
                            "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat(),
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
                        except (TypeError, ValueError) as exc:
                            logger.debug(
                                "Falling back to default execution plan for run %s: %s",
                                run_id,
                                exc,
                            )
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
                        execution_plan_ref_obj = await run_blocking_async(
                            persist_execution_plan,
                            store,
                            execution_plan,
                        )
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
                    (
                        catalog_snapshot,
                        method_catalog_snapshot_ref_str,
                    ) = await _ensure_catalog_snapshot()
                    snapshot_injector = cast(
                        "_MethodCatalogSnapshotAware | None",
                        formalizer if hasattr(formalizer, "set_method_catalog_snapshot") else None,
                    )
                    if snapshot_injector is not None:
                        try:
                            snapshot_injector.set_method_catalog_snapshot(
                                catalog_snapshot.model_dump(mode="json")
                            )
                        except (AttributeError, TypeError, ValueError) as exc:
                            logger.debug(
                                "Failed to inject method catalog snapshot for run %s: %s",
                                run_id,
                                exc,
                            )
                            notes.append("formalizer_catalog_injection_failed")

                    # 3) Mandatory preflight before execution.
                    preflight_report = preflight_execution_plan(execution_plan, catalog_snapshot)
                    preflight_report.plan_ref = _typed_artifact_ref(
                        execution_plan_ref_str,
                        kind="scientist.execution_plan",
                        ref_type=ExecutionPlanRef,
                    )
                    preflight_report.catalog_snapshot_ref = _typed_artifact_ref(
                        method_catalog_snapshot_ref_str,
                        kind="foundry.method_catalog_snapshot",
                        ref_type=MethodCatalogSnapshotRef,
                    )
                    preflight_report_ref = await run_blocking_async(
                        persist_preflight_report,
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
                        schema_version="1.0",
                        run_id=run_id,
                        iteration=1,
                        lifecycle_state="plan_created",
                        plan_ref=_typed_artifact_ref(
                            execution_plan_ref_str,
                            kind="scientist.execution_plan",
                            ref_type=ExecutionPlanRef,
                        ),
                        preflight_report_ref=_typed_artifact_ref(
                            preflight_report_ref_str,
                            kind="scientist.preflight_report",
                            ref_type=PreflightReportRef,
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
                                "notes": [
                                    *list(execution_plan.notes),
                                    "replanned_after_preflight_diagnostics",
                                ],
                            }
                        )
                        execution_plan_ref_obj = await run_blocking_async(
                            persist_execution_plan,
                            store,
                            execution_plan,
                        )
                        execution_plan_ref_str = str(execution_plan_ref_obj.artifact_id)
                        preflight_report = preflight_execution_plan(
                            execution_plan, catalog_snapshot
                        )
                        preflight_report.plan_ref = _typed_artifact_ref(
                            execution_plan_ref_str,
                            kind="scientist.execution_plan",
                            ref_type=ExecutionPlanRef,
                        )
                        preflight_report.catalog_snapshot_ref = _typed_artifact_ref(
                            method_catalog_snapshot_ref_str,
                            kind="foundry.method_catalog_snapshot",
                            ref_type=MethodCatalogSnapshotRef,
                        )
                        preflight_report_ref = await run_blocking_async(
                            persist_preflight_report,
                            store,
                            preflight_report,
                        )
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

                    iteration_state_ref = await run_blocking_async(
                        persist_iteration_state,
                        store,
                        iteration_state,
                    )
                    iteration_state_ref_str = str(iteration_state_ref.artifact_id)

                    resolve_request = DataResolveRequest(
                        data_needs=data_needs or [DataNeed(metric="generic.policy.context")],
                        mode="hybrid",
                        allow_explore_fallback=True,
                    )
                    resolve_outcome = await _capture_step(
                        agent="source_resolver",
                        action="resolve_fast_lane",
                        coro=run_blocking_async(retrieval.resolve, resolve_request),
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
                                        "candidates_total": int(phase.get("candidates_total") or 0),
                                        "candidates_selected": int(
                                            phase.get("candidates_selected") or 0
                                        ),
                                    },
                                )

                    execute_outcome = None
                    if resolve_outcome.fetch_plans:

                        def _promotion_candidate_payload(item: Any) -> dict[str, Any]:
                            if hasattr(item, "model_dump"):
                                return dict(item.model_dump(mode="json"))
                            if isinstance(item, dict):
                                return dict(item)
                            return {
                                "promotion_id": getattr(item, "promotion_id", None),
                                "candidate": repr(item),
                            }

                        def _promotion_candidate_id(item: Any) -> str | None:
                            if isinstance(item, dict):
                                value = item.get("promotion_id")
                            else:
                                value = getattr(item, "promotion_id", None)
                            return str(value) if value else None

                        list_promotion_candidates = getattr(
                            retrieval,
                            "list_promotion_candidates",
                            None,
                        )
                        promotion_candidates_before = (
                            list(raw_candidates_before)
                            if callable(list_promotion_candidates)
                            and isinstance(
                                (raw_candidates_before := list_promotion_candidates()),
                                list | tuple | set,
                            )
                            else []
                        )
                        promotion_ids_before = {
                            promotion_id
                            for item in promotion_candidates_before
                            if (promotion_id := _promotion_candidate_id(item)) is not None
                        }
                        execute_outcome = await _capture_step(
                            agent="executor",
                            action="fetch_execute",
                            coro=run_blocking_async(
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
                        promotion_candidates_after = (
                            list(raw_candidates_after)
                            if callable(list_promotion_candidates)
                            and isinstance(
                                (raw_candidates_after := list_promotion_candidates()),
                                list | tuple | set,
                            )
                            else []
                        )
                        promotion_candidates = [
                            _promotion_candidate_payload(item)
                            for item in promotion_candidates_after
                            if (promotion_id := _promotion_candidate_id(item)) is not None
                            and promotion_id not in promotion_ids_before
                        ]
                        _append_step(
                            agent="promotion_lane",
                            action="promotion_signal_emit",
                            summary="Promotion signals emitted",
                            details={"candidates_promoted": retrieval_candidates_promoted},
                        )

                        def _json_payload(item: Any) -> dict[str, Any]:
                            if hasattr(item, "model_dump"):
                                return dict(item.model_dump(mode="json"))
                            if isinstance(item, dict):
                                return dict(item)
                            return dict(vars(item))

                        data_context_payload = {
                            "metrics": [
                                metric.model_dump(mode="json")
                                for metric in execute_outcome.data_context.metrics
                            ],
                            "metadata_docs_fetched": (
                                execute_outcome.data_context.metadata_docs_fetched
                            ),
                            "index_docs_total": execute_outcome.data_context.index_docs_total,
                            "index_size_bytes": execute_outcome.data_context.index_size_bytes,
                        }
                        retrieval_context_payload["fetch_plans"] = [
                            _json_payload(item) for item in resolve_outcome.fetch_plans
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
                            auto_data_source_refs = await _materialize_retrieval_artifacts(
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
                        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
                            notes.append(f"auto_materialization_failed:{exc}")
                            _append_step(
                                agent="executor",
                                action="materialize_data_artifacts",
                                summary="Retrieval materialization failed",
                                status="warn",
                                details={"error": str(exc)},
                            )

                    fabric_flags_active = _is_scientist_v2_enabled() or _is_scientist_shadow_mode()
                    if fabric_flags_active:
                        from polisyos.scientist.agent.fabric import (
                            ScientistAgentFabric,
                            ScientistAgentFabricConfig,
                            ScientistAgentFabricRequest,
                        )

                        fabric = ScientistAgentFabric(config=ScientistAgentFabricConfig.from_env())
                        fabric_request = ScientistAgentFabricRequest(
                            run_id=run_id,
                            variant_id=variant_id,
                            model_name=model_name,
                            llm_client=llm_client,
                            problem_frame=problem_frame,
                            data_context=dict(data_context_payload or {}),
                            drafter=drafter,
                            formalizer=formalizer,
                            critic=critic,
                            artifact_store=store,
                            max_iterations=max_iterations,
                        )
                        if fabric.config.shadow_mode:
                            fabric_shadow_task = asyncio.create_task(fabric.run(fabric_request))
                        elif fabric.config.enabled:
                            fabric_result = await _capture_step(
                                agent="scientist_v2",
                                action="fabric_run",
                                coro=fabric.run(fabric_request),
                                summary="Scientist v2 orchestration completed",
                            )

                    verdict = "NEEDS_REVISION"
                    issue_count = 0
                    if fabric_result is not None:
                        draft = fabric_result.draft
                        trinity_bundle = fabric_result.trinity_bundle
                        verdict = fabric_result.critique.verdict
                        issue_count = len(fabric_result.critique.issues)
                        evaluator_payload = dict(fabric_result.metrics or {})
                        _append_step(
                            agent="scientist_v2",
                            action="fabric_summary",
                            summary="Scientist v2 result accepted",
                            details={
                                "result": dict(fabric_result.result or {}),
                                "traces": dict(fabric_result.traces or {}),
                                "metrics": dict(fabric_result.metrics or {}),
                            },
                        )
                    else:
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
                            except ValueError as exc:
                                logger.debug(
                                    "Iteration state execute transition failed for run %s: %s",
                                    run_id,
                                    exc,
                                )
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
                                    (
                                        float(per_model_budget_usd)
                                        - float(usage_snapshot["cost_usd"])
                                    )
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
                                                retrieval_candidates_filtered
                                                + len(data_context_payload.get("metrics", [])),
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
                            evaluator_report_ref = await run_blocking_async(
                                persist_evaluator_report,
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
                            except ValueError as exc:
                                logger.debug(
                                    "Iteration state evaluator transition failed for run %s: %s",
                                    run_id,
                                    exc,
                                )
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
                                    except ValueError as exc:
                                        logger.debug(
                                            "Iteration replan transition failed for run %s: %s",
                                            run_id,
                                            exc,
                                        )
                                        notes.append("iteration_state_replan_transition_failed")

                    if fabric_shadow_task is not None:
                        try:
                            fabric_shadow_result = await fabric_shadow_task
                            fabric_shadow_comparison = _build_scientist_v2_shadow_comparison(
                                legacy_status="completed",
                                legacy_verdict=verdict,
                                legacy_issue_count=int(issue_count),
                                legacy_cost_usd=float(_sum_call_events(call_events)["cost_usd"]),
                                legacy_prompt_tokens=int(
                                    _sum_call_events(call_events)["prompt_tokens"]
                                ),
                                legacy_completion_tokens=int(
                                    _sum_call_events(call_events)["completion_tokens"]
                                ),
                                shadow_result=fabric_shadow_result,
                            )
                            _append_step(
                                agent="scientist_v2",
                                action="shadow_run",
                                summary="Scientist v2 shadow run completed",
                                details={
                                    "result": dict(fabric_shadow_result.result or {}),
                                    "traces": dict(fabric_shadow_result.traces or {}),
                                    "metrics": dict(fabric_shadow_result.metrics or {}),
                                    "comparison": dict(fabric_shadow_comparison or {}),
                                },
                            )
                        except Exception as exc:
                            notes.append(f"scientist_v2_shadow_failed:{exc}")
                            _append_step(
                                agent="scientist_v2",
                                action="shadow_run",
                                summary="Scientist v2 shadow run failed",
                                status="warn",
                                details={"error": str(exc)},
                            )
                    iteration_state_ref = await run_blocking_async(
                        persist_iteration_state,
                        store,
                        iteration_state,
                    )
                    iteration_state_ref_str = str(iteration_state_ref.artifact_id)
                except (
                    AttributeError,
                    LookupError,
                    RuntimeError,
                    TypeError,
                    ValueError,
                ) as exc:  # pragma: no cover - defensive pipeline hardening
                    logger.exception("NL variant failed for model '%s': %s", model_name, exc)
                    return {
                        "model_variant_id": variant_id,
                        "model": model_name,
                        "provider": provider,
                        "status": "failed",
                        "verdict": "ERROR",
                        "issue_count": 0,
                        "prompt_tokens": int(_sum_call_events(call_events)["prompt_tokens"]),
                        "completion_tokens": int(
                            _sum_call_events(call_events)["completion_tokens"]
                        ),
                        "total_tokens": int(
                            _sum_call_events(call_events)["prompt_tokens"]
                            + _sum_call_events(call_events)["completion_tokens"]
                        ),
                        "latency_ms": max(0, _now_ms() - variant_started_at),
                        "cost_usd": round(_sum_call_events(call_events)["cost_usd"], 8),
                        "cost_reconciliation_delta_usd": round(
                            _sum_call_events(call_events)["cost_delta_usd"],
                            8,
                        ),
                        "started_at": variant_started_iso,
                        "finished_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
                        "steps": steps,
                        "notes": [*notes, f"variant_error:{exc}"],
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
                        "scientist_v2": (
                            {
                                "result": dict(fabric_result.result or {}),
                                "traces": dict(fabric_result.traces or {}),
                                "metrics": dict(fabric_result.metrics or {}),
                            }
                            if fabric_result is not None
                            else None
                        ),
                        "scientist_v2_shadow": (
                            {
                                "result": dict(fabric_shadow_result.result or {}),
                                "traces": dict(fabric_shadow_result.traces or {}),
                                "metrics": dict(fabric_shadow_result.metrics or {}),
                                "comparison": dict(fabric_shadow_comparison or {}),
                            }
                            if fabric_shadow_result is not None
                            else None
                        ),
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

                trinity_ref_str = await _store_bundle(trinity_bundle)
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
                    repro_manifest_ref = await run_blocking_async(
                        persist_reproducibility_manifest,
                        store,
                        repro_manifest,
                    )
                    reproducibility_manifest_ref_str = str(repro_manifest_ref.artifact_id)
                except (OSError, RuntimeError, TypeError, ValueError) as exc:
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
                        "cost_reconciliation_delta_usd": round(
                            float(usage["cost_delta_usd"]),
                            8,
                        ),
                        "trinity_bundle_ref": trinity_ref_str,
                        "started_at": variant_started_iso,
                        "finished_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
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
                        "scientist_v2": (
                            {
                                "result": dict(fabric_result.result or {}),
                                "traces": dict(fabric_result.traces or {}),
                                "metrics": dict(fabric_result.metrics or {}),
                            }
                            if fabric_result is not None
                            else None
                        ),
                        "scientist_v2_shadow": (
                            {
                                "result": dict(fabric_shadow_result.result or {}),
                                "traces": dict(fabric_shadow_result.traces or {}),
                                "metrics": dict(fabric_shadow_result.metrics or {}),
                                "comparison": dict(fabric_shadow_comparison or {}),
                            }
                            if fabric_shadow_result is not None
                            else None
                        ),
                        "_bundle": trinity_bundle,
                    }

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
                    "cost_reconciliation_delta_usd": round(
                        float(usage["cost_delta_usd"]),
                        8,
                    ),
                    "trinity_bundle_ref": trinity_ref_str,
                    "started_at": variant_started_iso,
                    "finished_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
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
                    "scientist_v2": (
                        {
                            "result": dict(fabric_result.result or {}),
                            "traces": dict(fabric_result.traces or {}),
                            "metrics": dict(fabric_result.metrics or {}),
                        }
                        if fabric_result is not None
                        else None
                    ),
                    "scientist_v2_shadow": (
                        {
                            "result": dict(fabric_shadow_result.result or {}),
                            "traces": dict(fabric_shadow_result.traces or {}),
                            "metrics": dict(fabric_shadow_result.metrics or {}),
                            "comparison": dict(fabric_shadow_comparison or {}),
                        }
                        if fabric_shadow_result is not None
                        else None
                    ),
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
                                    "model_variant_id": _normalize_model_variant_id(
                                        model_name, idx
                                    ),
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
                            if run_budget_usd is not None and run_budget_spent >= float(
                                run_budget_usd
                            ):
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
                if item.get("_bundle") is not None
                and str(item.get("verdict", "")).upper() == "APPROVE"
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
                if not allow_mock_fallback:
                    raise RuntimeError("mock_fallback_disallowed")
                # Last-resort fallback only runs when policy allows it.
                selected_variant = await _run_variant(None, len(variants))
                variants.append(selected_variant)
            selected_variant["selected_for_workflow"] = True

            selected_ref = selected_variant.get("trinity_bundle_ref")
            if not isinstance(selected_ref, str):
                selected_bundle = selected_variant.get("_bundle")
                if selected_bundle is None:
                    raise RuntimeError("No valid model variant produced a Trinity bundle")
                selected_ref = await _store_bundle(selected_bundle)
                selected_variant["trinity_bundle_ref"] = selected_ref

            # 8. Build state and run workflow
            inputs: dict[str, Any] = {
                "trinity_bundle_ref": _make_artifact_ref(selected_ref, kind="ir.trinity_bundle"),
            }

            # Add data source if provided
            if data_source:
                ds_key, ds_value = _resolve_data_source(data_source)
                inputs[ds_key] = _make_artifact_ref(ds_value, kind=_DATA_SOURCE_KEYS[ds_key])
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
                    "control_job_id": control_job_id,
                    "execution_profile": execution_profile,
                    "params": {
                        "nl_request": nl_request,
                        "agent_circuit": True,
                        "llm_model": selected_variant.get("model"),
                        "llm_models": [item.get("model") for item in variants if item.get("model")],
                        "llm_selected_variant_id": selected_variant.get("model_variant_id"),
                        "llm_prompt_tokens": int(selected_variant.get("prompt_tokens") or 0),
                        "llm_completion_tokens": int(
                            selected_variant.get("completion_tokens") or 0
                        ),
                        "llm_cost_usd": float(selected_variant.get("cost_usd") or 0.0),
                        "llm_cost_reconciliation_delta_usd": float(
                            selected_variant.get("cost_reconciliation_delta_usd") or 0.0
                        ),
                        "run_cost_usd": round(
                            sum(float(item.get("cost_usd") or 0.0) for item in variants),
                            8,
                        ),
                        "llm_model_variants": [
                            {key: value for key, value in item.items() if not key.startswith("_")}
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
                        "scientist_v2_enabled": _is_scientist_v2_enabled(),
                        "scientist_v2_shadow_mode": _is_scientist_shadow_mode(),
                        "scientist_web_search_enabled": _is_scientist_web_search_enabled(),
                        "scientist_swarm_enabled": _is_scientist_swarm_enabled(),
                        "scientist_reflexion_enabled": _is_scientist_reflexion_enabled(),
                        "scientist_v2": dict(selected_variant.get("scientist_v2") or {}),
                        "scientist_v2_shadow": dict(
                            selected_variant.get("scientist_v2_shadow") or {}
                        ),
                    },
                }
            )
            if isinstance(current_capability_manifest_ref, str) and current_capability_manifest_ref:
                state_payload["capability_manifest_ref"] = _make_artifact_ref(
                    current_capability_manifest_ref,
                    kind="runtime.capability_manifest",
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
            return {
                "run_id": run_id,
                "capability_manifest_ref": current_capability_manifest_ref,
            }

        result: dict[str, Any] = run_coro_sync(_agent_pipeline())
        return result


__all__ = ["NaturalLanguageRunMixin"]
