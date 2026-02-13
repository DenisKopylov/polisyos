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
from pathlib import Path
from typing import Any

from polisyos.core.contracts.control import (
    BindingProfileInfo,
    BindingProfilesListResponse,
    CacheEntryInfo,
    CacheStatusResponse,
    ConnectorInfo,
    ConnectorsListResponse,
    DataSourceBinding,
    IngestRequest,
    IngestResponse,
    ModelProfileInfo,
    ModelProfilesListResponse,
    NaturalLanguageRunRequest,
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


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class ControlPlaneService:
    """Orchestrates control-plane operations (run launch, data ingestion)."""

    def __init__(self, *, cas_root: Path, core_runs_root: Path) -> None:
        self._cas_root = cas_root
        self._core_runs_root = core_runs_root
        self._task_runner = TaskRunner(max_workers=2)

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
    ) -> None:
        """Run agent circuit synchronously (called from thread pool)."""
        from polisyos.common.async_tools import run_coro_sync

        async def _agent_pipeline() -> None:
            from polisyos.core.artifacts.store import FileSystemCAS
            from polisyos.core.canon import content_hash
            from polisyos.scientist.agent.critic import LLMCriticAgent, MockCriticAgent
            from polisyos.scientist.agent.drafter_clients import LLMDrafterAgent, MockDrafterAgent
            from polisyos.scientist.agent.formalizer import LLMFormalizerAgent, MockFormalizerAgent
            from polisyos.scientist.agent.pi import LLMPIAgent, MockPIAgent

            store = FileSystemCAS(Path(".polisyos"))
            models_to_run = _dedupe_models(list(llm_models))

            def _store_bundle(bundle: Any) -> str:
                bundle_bytes = json.dumps(
                    bundle.model_dump(mode="json"),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
                bundle_hash = content_hash(bundle_bytes)
                store.put_bytes(bundle_bytes, expected_hash=bundle_hash)
                return f"sha256:{bundle_hash}"

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
                    drafter = MockDrafterAgent()
                    formalizer = MockFormalizerAgent()
                    critic = MockCriticAgent()
                else:
                    pi = LLMPIAgent(llm_client=llm_client, model_name=model_name)
                    drafter = LLMDrafterAgent(llm_client=llm_client, model_name=model_name)
                    formalizer = LLMFormalizerAgent(llm_client=llm_client, model_name=model_name)
                    critic = LLMCriticAgent(llm_client=llm_client, model_name=model_name)

                steps: list[dict[str, Any]] = []

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
                    draft = await _capture_step(
                        agent="drafter",
                        action="draft_policy",
                        coro=drafter.draft_policy(problem_frame),
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
                        if critique.verdict == "APPROVE":
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

            state_payload = {
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
                    "context": context,
                },
            }

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

        manifest = ConnectorManifestSpec(
            datasets=datasets,
            cache_policy=request.cache_policy if request.cache_policy != "default" else None,
        )

        # Resolve connection profile → ConnectionConfig
        connection_config = None
        if request.connection_profile:
            from polisyos.fabric.connectors.profiles import SourceProfileRegistry
            from polisyos.fabric.connectors.profiles.resolver import resolve_connection_config

            profile_reg = SourceProfileRegistry.get_instance()
            profile = profile_reg.get(request.connection_profile)
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


__all__ = ["ControlPlaneService"]
