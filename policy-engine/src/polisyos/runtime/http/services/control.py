"""Control Plane service — bridges HTTP layer to scientist/fabric."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from polisyos.core.contracts.control import (
    CacheEntryInfo,
    CacheStatusResponse,
    ConnectorInfo,
    ConnectorsListResponse,
    DataSourceBinding,
    IngestRequest,
    IngestResponse,
    NaturalLanguageRunRequest,
    RunLaunchResponse,
    WorkflowRunRequest,
)
from polisyos.core.contracts.runtime import ApiMeta

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
            request.llm_model,
            request.checkpoint_policy,
        )

        return RunLaunchResponse(
            meta=_build_api_meta(request_id),
            status="accepted",
            run_id=run_id,
            message=(
                f"Natural-language run {run_id} accepted. "
                f"Agent circuit will execute with "
                f"{'LLM=' + request.llm_model if request.llm_model else 'mock agents'}."
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
        llm_model: str | None,
        checkpoint_policy: str,
    ) -> None:
        """Run agent circuit synchronously (called from thread pool)."""
        from polisyos.common.async_tools import run_coro_sync

        async def _agent_pipeline() -> None:
            # 1. Create PI agent
            if llm_model:
                from polisyos.scientist.agent.pi import MockPIAgent
                pi = MockPIAgent()  # TODO: LLMPIAgent when available
            else:
                from polisyos.scientist.agent.pi import MockPIAgent
                pi = MockPIAgent()

            # 2. Decompose task → get ProblemFrame
            problem_frame = await pi.create_problem_frame(
                nl_request,
                domain_hint=domain_hint or "custom",
            )
            await pi.hold_problem_frame(problem_frame)

            # 3. Create Drafter
            if llm_model:
                from polisyos.scientist.agent.drafter_clients import LLMDrafterAgent
                from polisyos.scientist.llm import TracedLLMClient
                llm_client = TracedLLMClient(model=llm_model)
                drafter = LLMDrafterAgent(llm_client=llm_client)
            else:
                from polisyos.scientist.agent.drafter_clients import MockDrafterAgent
                drafter = MockDrafterAgent()

            # 4. Draft policy
            draft = await drafter.draft_policy(problem_frame)

            # 5. Formalize → TrinityBundle
            if llm_model:
                from polisyos.scientist.agent.formalizer import LLMFormalizerAgent
                formalizer = LLMFormalizerAgent(llm_client=TracedLLMClient(model=llm_model))
            else:
                from polisyos.scientist.agent.formalizer import MockFormalizerAgent
                formalizer = MockFormalizerAgent()

            trinity_bundle = await formalizer.formalize(draft)

            # 6. Critic review loop
            if llm_model:
                from polisyos.scientist.agent.critic import LLMCriticAgent
                critic = LLMCriticAgent(llm_client=TracedLLMClient(model=llm_model))
            else:
                from polisyos.scientist.agent.critic import MockCriticAgent
                critic = MockCriticAgent()

            for iteration in range(max_iterations):
                critique = await critic.critique(trinity_bundle, problem_frame)
                if critique.verdict == "APPROVE":
                    break
                if iteration < max_iterations - 1:
                    hint = await critic.generate_hint(critique.issues)
                    draft = await drafter.refine_draft(draft, critique)
                    trinity_bundle = await formalizer.formalize(draft)

            # 7. Store TrinityBundle and build ExperimentState
            from polisyos.core.artifacts.store import FileSystemCAS
            from polisyos.core.canon import content_hash

            store = FileSystemCAS(Path(".polisyos"))

            # Serialize and store trinity bundle
            import json
            bundle_bytes = json.dumps(
                trinity_bundle.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            bundle_hash = content_hash(bundle_bytes)
            store.put_bytes(bundle_bytes, expected_hash=bundle_hash)

            trinity_ref_str = f"sha256:{bundle_hash}"

            # 8. Build state and run workflow
            inputs: dict[str, Any] = {
                "trinity_bundle_ref": _make_artifact_ref(
                    trinity_ref_str, kind="ir.trinity_bundle"
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
                    "llm_model": llm_model,
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
        from polisyos.fabric.ingestion import (
            ConnectorManifestSpec,
            DatasetFetchSpec,
            run_connectors_ingestion,
        )

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

        try:
            evidence_ref = run_connectors_ingestion(
                connector_manifest=manifest,
                source=request.source,
                license_name=request.license_name,
                cas_root=self._cas_root,
            )
            return IngestResponse(
                meta=_build_api_meta(request_id),
                status="completed",
                evidence_bundle_ref=(
                    str(evidence_ref.artifact_id.hex) if evidence_ref else None
                ),
                datasets_fetched=len(datasets),
                message=f"Successfully ingested {len(datasets)} dataset(s).",
            )
        except Exception as exc:
            logger.exception("Data ingestion failed: %s", exc)
            return IngestResponse(
                meta=_build_api_meta(request_id),
                status="failed",
                datasets_fetched=0,
                message=f"Ingestion failed: {exc}",
            )

    # ---- Connectors listing -----------------------------------------------

    def list_connectors(self, *, request_id: str | None = None) -> ConnectorsListResponse:
        from polisyos.fabric.connectors.registry import ConnectorRegistry

        registry = ConnectorRegistry.get_instance()
        infos: list[ConnectorInfo] = []

        for entry in registry.query_entries():
            meta = entry.metadata
            infos.append(
                ConnectorInfo(
                    connector_id=meta.fully_qualified_id,
                    namespace=meta.namespace,
                    version=meta.version,
                    known_datasets=sorted(entry.known_datasets),
                    loaded=entry.loaded,
                    last_health_check=entry.last_health_check,
                )
            )

        return ConnectorsListResponse(
            meta=_build_api_meta(request_id),
            connectors=infos,
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
