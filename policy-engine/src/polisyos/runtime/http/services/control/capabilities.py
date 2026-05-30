"""Control-plane capability manifest surface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.core.contracts.control import (
    CapabilityFeatureInfo,
    CapabilityManifestResponse,
    PolicyFlags,
)
from polisyos.foundry.methods.catalog.causal.capabilities import (
    build_causal_capability_contract,
    project_capability_features,
)
from polisyos.runtime.http.services.control.production_data import (
    production_data_evidence_context,
)

from .._control_contracts import (
    _build_api_meta,
    _is_auto_materialization_enabled,
    _is_multimodel_enabled,
    _is_required_preflight_enabled,
    _is_scientist_reflexion_enabled,
    _is_scientist_shadow_mode,
    _is_scientist_swarm_enabled,
    _is_scientist_v2_enabled,
    _is_scientist_web_search_enabled,
    _is_unified_dag_enabled,
)

if TYPE_CHECKING:
    from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver


class CapabilityManifestMixin:
    """Capability-manifest endpoint behavior for the control-plane service."""

    _policy_resolver: RuntimeExecutionPolicyResolver

    def get_capabilities(self, *, request_id: str | None = None) -> CapabilityManifestResponse:
        """Return the control-plane capability manifest, execution profiles, and feature gates."""
        causal_contract = build_causal_capability_contract()
        production_data_context = production_data_evidence_context(None, allow_default=True)
        resolved_policy = self._policy_resolver.resolve(
            requested_profile=None,
            policy_flags=PolicyFlags(),
            principal=None,
        )
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
                description=(
                    "Use the agent circuit to transform NL requests into executable policy runs."
                ),
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
                key="scientist_v2",
                label="Scientist v2 runtime",
                description=(
                    "Unified v2 facade for web grounding, swarm, and Reflexion orchestration."
                ),
                category="runs",
                enabled=_is_scientist_v2_enabled(),
            ),
            CapabilityFeatureInfo(
                key="scientist_shadow_mode",
                label="Scientist shadow mode",
                description=(
                    "Run v2 in shadow alongside the legacy Scientist path "
                    "and keep legacy as return-path."
                ),
                category="runs",
                enabled=_is_scientist_shadow_mode(),
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
                description=(
                    "Expose transportability summaries on governance and decision surfaces."
                ),
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
                description=(
                    "Materialize retrieval results into snapshots or bindings during NL execution."
                ),
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
                key="scientist_web_search",
                label="Scientist web search",
                description=(
                    "Enable first-class Scholar web search and citation grounding "
                    "in the Scientist runtime."
                ),
                category="evidence",
                enabled=_is_scientist_web_search_enabled(),
            ),
            CapabilityFeatureInfo(
                key="scientist_swarm",
                label="Scientist swarm runtime",
                description=(
                    "Enable supervisor-worker swarm orchestration for research "
                    "and evaluation facets."
                ),
                category="runtime",
                enabled=_is_scientist_swarm_enabled(),
            ),
            CapabilityFeatureInfo(
                key="scientist_reflexion",
                label="Scientist Reflexion",
                description=(
                    "Enable evaluator-optimizer retries with persistent memory "
                    "in the Scientist runtime."
                ),
                category="runtime",
                enabled=_is_scientist_reflexion_enabled(),
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
            CapabilityFeatureInfo(
                key="durable_control_plane",
                label="Durable control plane",
                description="Use leased workers, durable state, and outbox-backed control events.",
                category="platform",
                enabled=bool(resolved_policy.fallback_rules.get("durable_control_required")),
            ),
            CapabilityFeatureInfo(
                key="control_plane_local_waiver",
                label="Local control-plane waiver",
                description=(
                    "Explicit research-only waiver allowing non-durable "
                    "local control infrastructure."
                ),
                category="platform",
                enabled=bool(
                    resolved_policy.fallback_rules.get("local_control_plane_waiver_active")
                ),
                stage="planned"
                if not resolved_policy.fallback_rules.get("local_control_plane_waiver_active")
                else "active",
            ),
        ]
        for feature in project_capability_features(causal_contract):
            features.append(CapabilityFeatureInfo.model_validate(feature))

        return CapabilityManifestResponse(
            meta=_build_api_meta(request_id),
            default_execution_profile=self._policy_resolver.default_profile,
            supported_execution_profiles=list(self._policy_resolver.supported_profiles()),
            worker_backend=self._policy_resolver.worker_backend,
            state_store_backend=self._policy_resolver.state_store_backend,
            security_posture=dict(resolved_policy.security_posture),
            fallback_rules=dict(resolved_policy.fallback_rules),
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
                "task_runner": "durable_control_worker",
                "default_locale": "en",
                "supported_locales": ["en", "uk"],
                "durable_control_profiles": ["research", "governed", "production"],
                "local_control_plane_waiver_active": bool(
                    resolved_policy.fallback_rules.get("local_control_plane_waiver_active")
                ),
                "causal_runtime": causal_contract.model_dump(mode="json"),
                **(
                    {"production_data": production_data_context}
                    if production_data_context is not None
                    else {}
                ),
            },
        )
