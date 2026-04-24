"""Public autotune execution plan module API."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from polisyos.core.canon import CanonSpec, fingerprint
from polisyos.core.contracts.execution_plan import (
    ExecutionPlan,
    MethodCatalogSnapshot,
    MethodDagEdge,
    MethodDagNode,
    PreflightReport,
)
from polisyos.foundry.methods import MethodRegistry
from polisyos.foundry.methods.base import parse_fqn
from polisyos.foundry.methods.exceptions import FoundryMethodError, MethodNotFoundError
from polisyos.foundry.methods.selection import (
    suggest_adapter_methods,
    suggest_plan_node_alternatives,
)
from polisyos.scientist.governance.report import GovernanceReport

from .models import (
    BenchmarkedEvaluator,
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSuite,
    MetricDirection,
    MutationArtifact,
    PromotionPolicy,
    SearchLoopSpec,
    load_model_artifact,
    read_split_manifest,
)
from .registry import ChampionRegistry
from .runtime import PydanticMutationCodec

EXECUTION_PLAN_LOOP_ID = "execution_plan"

if TYPE_CHECKING:
    from collections.abc import Callable


_EXECUTION_PLAN_MODEL_ERRORS = (TypeError, ValueError, ValidationError)
_EXECUTION_PLAN_METHOD_LOOKUP_ERRORS = (
    AttributeError,
    FoundryMethodError,
    MethodNotFoundError,
    RuntimeError,
    TypeError,
    ValueError,
)


def _resolve_registry(
    registry: MethodRegistry | None,
    registry_provider: Callable[[], MethodRegistry] | None,
) -> MethodRegistry:
    if registry is not None:
        return registry
    return (registry_provider or MethodRegistry.get_instance)()


def _clone_runtime_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clone_runtime_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clone_runtime_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_clone_runtime_payload(item) for item in value)
    if isinstance(value, set):
        return {_clone_runtime_payload(item) for item in value}
    return value


def _clone_method_dag_node(node: MethodDagNode) -> MethodDagNode:
    return node.model_copy(
        update={
            "params": _clone_runtime_payload(node.params),
            "depends_on": list(node.depends_on),
            "reads_slots": list(node.reads_slots),
            "writes_slots": list(node.writes_slots),
            "incompatibilities": list(node.incompatibilities),
            "deprecations": list(node.deprecations),
            "notes": list(node.notes),
        }
    )


class ExecutionPlanSearchMode(str, Enum):
    """Execution plan search mode public type."""

    PARAMS_ONLY = "params_only"
    TOPOLOGY_STEP = "topology_step"


class TopologyMutationKind(str, Enum):
    """Topology mutation kind public type."""

    SWAP_METHOD = "swap_method"
    INSERT_ADAPTER = "insert_adapter"
    DROP_OPTIONAL_NODE = "drop_optional_node"


class TopologyMutation(BaseModel):
    """Topology mutation public type."""

    model_config = ConfigDict(extra="forbid")

    kind: TopologyMutationKind
    node_id: str = Field(..., min_length=1)
    upstream_node_id: str | None = None
    replacement_method_fqn: str | None = None
    adapter_method_fqn: str | None = None


class ExecutionPlanSearchConfig(MutationArtifact):
    """Execution plan search config data model."""

    model_config = ConfigDict(extra="forbid")

    loop_id: str = EXECUTION_PLAN_LOOP_ID
    mode: ExecutionPlanSearchMode = ExecutionPlanSearchMode.PARAMS_ONLY
    method_dag: list[MethodDagNode] = Field(default_factory=list)
    method_edges: list[MethodDagEdge] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    fixed_method_dag_hash: str | None = None
    topology_mutation: TopologyMutation | None = None

    @model_validator(mode="after")
    def _validate_mode_constraints(self) -> ExecutionPlanSearchConfig:
        dag_hash = self.method_dag_hash
        if self.mode == ExecutionPlanSearchMode.PARAMS_ONLY:
            if self.topology_mutation is not None:
                raise ValueError("params_only mode cannot carry topology_mutation")
            if self.fixed_method_dag_hash is not None and self.fixed_method_dag_hash != dag_hash:
                raise ValueError("params_only mode must preserve fixed_method_dag_hash")
        elif self.topology_mutation is None:
            raise ValueError("topology_step mode requires exactly one topology_mutation")
        return self

    @property
    def method_dag_hash(self) -> str:
        return fingerprint(
            {
                "method_dag": [node.model_dump(mode="json") for node in self.method_dag],
                "method_edges": [edge.model_dump(mode="json") for edge in self.method_edges],
            },
            canon_spec=CanonSpec(forbid_floats=False),
        )

    def apply_to_execution_plan(self, base_plan: ExecutionPlan) -> ExecutionPlan:
        return base_plan.model_copy(
            update={
                "method_dag": list(self.method_dag),
                "method_edges": list(self.method_edges),
                "params": dict(self.params),
            }
        )

    def with_topology_mutation(
        self,
        mutation: TopologyMutation,
        *,
        registry: MethodRegistry | None = None,
        registry_provider: Callable[[], MethodRegistry] | None = None,
    ) -> ExecutionPlanSearchConfig:
        reg = _resolve_registry(registry, registry_provider)
        nodes = [_clone_method_dag_node(node) for node in self.method_dag]
        node_by_id = {node.node_id: node for node in nodes}
        target = node_by_id.get(mutation.node_id)
        if target is None:
            raise ValueError(f"unknown node_id for topology mutation: {mutation.node_id}")

        if mutation.kind is TopologyMutationKind.SWAP_METHOD:
            replacement = str(mutation.replacement_method_fqn or "").strip()
            if not replacement:
                raise ValueError("swap_method mutations require replacement_method_fqn")
            target.method_fqn = replacement
            try:
                _, _, version = parse_fqn(replacement)
            except ValueError:
                target.method_version = None
            else:
                target.method_version = version
            target.backend = _backend_for_method(reg, replacement)
        elif mutation.kind is TopologyMutationKind.INSERT_ADAPTER:
            adapter_fqn = str(mutation.adapter_method_fqn or "").strip()
            if not adapter_fqn:
                raise ValueError("insert_adapter mutations require adapter_method_fqn")
            upstream_node_id = str(mutation.upstream_node_id or "").strip()
            if not upstream_node_id:
                upstream_node_id = target.depends_on[0] if len(target.depends_on) == 1 else ""
            if not upstream_node_id or upstream_node_id not in set(target.depends_on):
                raise ValueError(
                    "insert_adapter mutations require upstream_node_id to identify the broken edge"
                )
            adapter_node_id = _unique_adapter_node_id(
                nodes, upstream_node_id=upstream_node_id, target_node_id=target.node_id
            )
            adapter_node = MethodDagNode(
                node_id=adapter_node_id,
                method_fqn=adapter_fqn,
                method_version=_version_from_fqn(adapter_fqn),
                backend=_backend_for_method(reg, adapter_fqn),
                depends_on=[upstream_node_id],
                reads_slots=list(_input_slot_names(reg, adapter_fqn)),
                writes_slots=list(_output_slot_names(reg, adapter_fqn)),
                notes=[f"inserted_adapter_for:{target.node_id}"],
            )
            target.depends_on = [
                adapter_node_id if dep_id == upstream_node_id else dep_id
                for dep_id in target.depends_on
            ]
            nodes.append(adapter_node)
        elif mutation.kind is TopologyMutationKind.DROP_OPTIONAL_NODE:
            downstream = [node for node in nodes if target.node_id in set(node.depends_on or [])]
            for consumer in downstream:
                consumer.depends_on = [
                    dep_id for dep_id in consumer.depends_on if dep_id != target.node_id
                ]
                for dep_id in target.depends_on:
                    if dep_id not in consumer.depends_on:
                        consumer.depends_on.append(dep_id)
            nodes = [node for node in nodes if node.node_id != target.node_id]
        else:
            raise ValueError(f"unsupported topology mutation kind: {mutation.kind}")

        return ExecutionPlanSearchConfig(
            mode=ExecutionPlanSearchMode.TOPOLOGY_STEP,
            method_dag=nodes,
            method_edges=_edges_from_nodes(nodes),
            params=dict(self.params),
            fixed_method_dag_hash=self.fixed_method_dag_hash or self.method_dag_hash,
            topology_mutation=mutation,
            notes=[*self.notes, _mutation_note(mutation)],
        )


def build_baseline_execution_plan_config(
    context: dict[str, Any] | None = None,
) -> ExecutionPlanSearchConfig:
    """Build baseline execution plan config."""
    baseline_plan = None if context is None else context.get("baseline_execution_plan")
    if isinstance(baseline_plan, ExecutionPlan):
        return ExecutionPlanSearchConfig(
            method_dag=list(baseline_plan.method_dag),
            method_edges=list(baseline_plan.method_edges),
            params=dict(baseline_plan.params),
            fixed_method_dag_hash=fingerprint(
                {
                    "method_dag": [
                        node.model_dump(mode="json") for node in baseline_plan.method_dag
                    ],
                    "method_edges": [
                        edge.model_dump(mode="json") for edge in baseline_plan.method_edges
                    ],
                },
                canon_spec=CanonSpec(forbid_floats=False),
            ),
        )
    return ExecutionPlanSearchConfig()


def suggest_execution_plan_topology_mutations(
    config: ExecutionPlanSearchConfig,
    *,
    preflight_report: PreflightReport,
    catalog: MethodCatalogSnapshot,
    limit: int = 8,
    registry: MethodRegistry | None = None,
    registry_provider: Callable[[], MethodRegistry] | None = None,
) -> list[TopologyMutation]:
    """Suggest execution plan topology mutations helper."""
    reg = _resolve_registry(registry, registry_provider)
    mutations: list[TopologyMutation] = []
    seen: set[tuple[str, str, str, str]] = set()
    node_by_id = {node.node_id: node for node in config.method_dag}
    catalog_entries = {entry.fqn: entry for entry in catalog.entries}

    for diagnostic in preflight_report.diagnostics:
        node_id = _diagnostic_node_id(diagnostic)
        if not node_id:
            continue
        node = node_by_id.get(node_id)
        if node is None:
            continue

        alternative_rows = diagnostic.data.get("alternative_methods") or []
        for row in alternative_rows:
            replacement = str(row.get("fqn") or "").strip()
            if not replacement or replacement == node.method_fqn:
                continue
            mutation = TopologyMutation(
                kind=TopologyMutationKind.SWAP_METHOD,
                node_id=node.node_id,
                replacement_method_fqn=replacement,
            )
            _append_unique_mutation(mutations, seen, mutation)

        if diagnostic.code == "slot_linker.not_linkable":
            src_node_id = str(diagnostic.data.get("src_node_id") or "").strip()
            adapter_rows = diagnostic.data.get("adapter_methods") or []
            for row in adapter_rows:
                adapter_fqn = str(row.get("fqn") or "").strip()
                if not adapter_fqn:
                    continue
                mutation = TopologyMutation(
                    kind=TopologyMutationKind.INSERT_ADAPTER,
                    node_id=node.node_id,
                    upstream_node_id=src_node_id or None,
                    adapter_method_fqn=adapter_fqn,
                )
                _append_unique_mutation(mutations, seen, mutation)

            if not adapter_rows and src_node_id:
                source_node = node_by_id.get(src_node_id)
                if source_node is not None:
                    adapter_candidates = suggest_adapter_methods(
                        catalog,
                        source_fqn=source_node.method_fqn,
                        target_fqn=node.method_fqn,
                        limit=3,
                        registry=reg,
                        exclude_fqns=(node.method_fqn,),
                    )
                    for entry in adapter_candidates:
                        mutation = TopologyMutation(
                            kind=TopologyMutationKind.INSERT_ADAPTER,
                            node_id=node.node_id,
                            upstream_node_id=src_node_id,
                            adapter_method_fqn=entry.fqn,
                        )
                        _append_unique_mutation(mutations, seen, mutation)

        if diagnostic.code in {
            "method_catalog.method_missing",
            "method_catalog.method_unavailable",
        } and _is_optional_leaf_node(node, config.method_dag):
            mutation = TopologyMutation(
                kind=TopologyMutationKind.DROP_OPTIONAL_NODE,
                node_id=node.node_id,
            )
            _append_unique_mutation(mutations, seen, mutation)

        if (
            diagnostic.code == "method_catalog.causal_capability_unavailable"
            and catalog_entries.get(node.method_fqn) is not None
        ):
            alternatives = suggest_plan_node_alternatives(
                catalog,
                node=node,
                plan_nodes=config.method_dag,
                target_entry=catalog_entries.get(node.method_fqn),
                limit=3,
                registry=reg,
            )
            for entry in alternatives:
                mutation = TopologyMutation(
                    kind=TopologyMutationKind.SWAP_METHOD,
                    node_id=node.node_id,
                    replacement_method_fqn=entry.fqn,
                )
                _append_unique_mutation(mutations, seen, mutation)

        if len(mutations) >= max(1, int(limit)):
            break

    return mutations[: max(1, int(limit))]


class CapabilityAwareExecutionPlanCandidateGenerator:
    """Capability aware execution plan candidate generator implementation."""

    def generate(
        self,
        history: list[Any],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        generation_context = build_execution_plan_generation_context(
            history=history,
            current_best=current_best,
            context=context,
        )
        config = generation_context.get("execution_plan_search_config")
        catalog = generation_context.get("catalog_snapshot")
        preflight = generation_context.get("preflight_report")
        mutations = generation_context.get("execution_plan_topology_mutations") or []
        if not isinstance(config, ExecutionPlanSearchConfig):
            return build_baseline_execution_plan_config(context).model_dump(mode="json")
        if catalog is None or preflight is None:
            return config.model_dump(mode="json")

        attempted = {
            _mutation_identity(_coerce_candidate_mutation(item))
            for item in history
            if _coerce_candidate_mutation(item) is not None
        }
        for mutation in mutations:
            identity = _mutation_identity(mutation)
            if identity in attempted:
                continue
            return config.with_topology_mutation(mutation).model_dump(mode="json")
        return config.model_dump(mode="json")


def build_execution_plan_generation_context(
    *,
    history: list[Any],
    current_best: dict[str, Any] | None,
    context: dict[str, Any],
    limit: int = 8,
) -> dict[str, Any]:
    """Build execution plan generation context."""
    generation_context: dict[str, Any] = {}
    config = _current_execution_plan_config(
        history=history,
        current_best=current_best,
        context=context,
    )
    if config is None:
        config = _baseline_config_from_context(context)
    catalog = _coerce_catalog_snapshot(
        _latest_stage_b_value(history, "catalog_snapshot")
        or _latest_stage_b_value(history, "method_catalog_snapshot")
        or context.get("catalog_snapshot")
        or context.get("method_catalog_snapshot")
    )
    preflight = _coerce_preflight(
        _latest_stage_b_value(history, "preflight_report") or context.get("preflight_report")
    )
    mutations: list[TopologyMutation] = []
    if catalog is not None and preflight.diagnostics:
        mutations = suggest_execution_plan_topology_mutations(
            config,
            preflight_report=preflight,
            catalog=catalog,
            limit=limit,
        )
    generation_context.update(
        {
            "execution_plan_search_config": config,
            "baseline_execution_plan_config": config,
            "catalog_snapshot": catalog,
            "preflight_report": preflight,
            "execution_plan_topology_mutations": mutations,
            "execution_plan_topology_mutation_payload": [
                mutation.model_dump(mode="json") for mutation in mutations
            ],
            "execution_plan_topology_mutation_count": len(mutations),
        }
    )
    return generation_context


def default_execution_plan_policy() -> PromotionPolicy:
    """Default execution plan policy helper."""
    return PromotionPolicy(
        loop_id=EXECUTION_PLAN_LOOP_ID,
        primary_metric="composite_score",
        direction=MetricDirection.MAXIMIZE,
        compare_split=BenchmarkSplit.HOLDOUT,
        min_improvement=0.0,
        min_sample_count=1,
        required_guardrails=[
            "no_new_blockers",
            "governance_not_degraded",
            "compatibility_ok",
        ],
    )


def _coerce_catalog_snapshot(raw: Any) -> MethodCatalogSnapshot | None:
    if isinstance(raw, MethodCatalogSnapshot):
        return raw
    if isinstance(raw, dict):
        return MethodCatalogSnapshot.model_validate(raw)
    return None


def _baseline_config_from_context(context: dict[str, Any]) -> ExecutionPlanSearchConfig:
    baseline_cfg = context.get("baseline_execution_plan_config")
    if isinstance(baseline_cfg, ExecutionPlanSearchConfig):
        return baseline_cfg
    if isinstance(baseline_cfg, dict):
        return ExecutionPlanSearchConfig.model_validate(baseline_cfg)
    return build_baseline_execution_plan_config(context)


def _current_execution_plan_config(
    *,
    history: list[Any],
    current_best: dict[str, Any] | None,
    context: dict[str, Any],
) -> ExecutionPlanSearchConfig | None:
    for candidate in (
        current_best,
        _latest_stage_b_value(history, "candidate_payload"),
        _latest_history_candidate(history),
        context.get("execution_plan_search_config"),
        context.get("baseline_execution_plan_config"),
    ):
        config = _coerce_candidate_config(candidate)
        if config is not None:
            return config
    return None


def _coerce_candidate_config(raw: Any) -> ExecutionPlanSearchConfig | None:
    if isinstance(raw, ExecutionPlanSearchConfig):
        return raw
    if isinstance(raw, dict):
        try:
            return ExecutionPlanSearchConfig.model_validate(raw)
        except _EXECUTION_PLAN_MODEL_ERRORS:
            return None
    return None


def _latest_history_candidate(history: list[Any]) -> Any | None:
    for item in reversed(history):
        candidate = getattr(item, "candidate", None)
        if candidate is not None:
            return candidate
    return None


def _latest_stage_b_value(history: list[Any], key: str) -> Any | None:
    for item in reversed(history):
        stage_b_result = getattr(item, "stage_b_result", None)
        if isinstance(stage_b_result, dict) and stage_b_result.get(key) is not None:
            return stage_b_result.get(key)
    return None


def _diagnostic_node_id(diagnostic: Any) -> str | None:
    path = getattr(diagnostic, "path", None)
    if isinstance(path, list) and len(path) >= 2 and path[0] == "method_dag":
        token = str(path[1]).strip()
        return token or None
    return None


def _is_optional_leaf_node(node: MethodDagNode, plan_nodes: list[MethodDagNode]) -> bool:
    downstream = any(node.node_id in set(item.depends_on or []) for item in plan_nodes)
    if downstream:
        return False
    note_tokens = [token.lower() for token in [*node.notes, *node.deprecations] if token]
    return any("optional" in token for token in note_tokens)


def _append_unique_mutation(
    mutations: list[TopologyMutation],
    seen: set[tuple[str, str, str, str]],
    mutation: TopologyMutation,
) -> None:
    identity = _mutation_identity(mutation)
    if identity in seen:
        return
    seen.add(identity)
    mutations.append(mutation)


def _mutation_identity(mutation: TopologyMutation | None) -> tuple[str, str, str, str] | None:
    if mutation is None:
        return None
    return (
        mutation.kind.value,
        mutation.node_id,
        str(mutation.upstream_node_id or ""),
        str(mutation.replacement_method_fqn or mutation.adapter_method_fqn or ""),
    )


def _coerce_candidate_mutation(history_item: Any) -> TopologyMutation | None:
    candidate = getattr(history_item, "candidate", history_item)
    if isinstance(candidate, ExecutionPlanSearchConfig):
        return candidate.topology_mutation
    if isinstance(candidate, dict):
        mutation = candidate.get("topology_mutation")
        if mutation is None:
            return None
        return TopologyMutation.model_validate(mutation)
    return None


def _unique_adapter_node_id(
    nodes: list[MethodDagNode],
    *,
    upstream_node_id: str,
    target_node_id: str,
) -> str:
    base = f"{upstream_node_id}_to_{target_node_id}_adapter"
    existing = {node.node_id for node in nodes}
    if base not in existing:
        return base
    suffix = 2
    while f"{base}_{suffix}" in existing:
        suffix += 1
    return f"{base}_{suffix}"


def _version_from_fqn(fqn: str) -> str | None:
    try:
        _, _, version = parse_fqn(fqn)
    except ValueError:
        return None
    return version


def _backend_for_method(registry: MethodRegistry, fqn: str) -> str | None:
    try:
        return registry.get(fqn).signature.execution_backend.value
    except _EXECUTION_PLAN_METHOD_LOOKUP_ERRORS:
        return None


def _input_slot_names(registry: MethodRegistry, fqn: str) -> tuple[str, ...]:
    try:
        signature = registry.get(fqn).signature
    except _EXECUTION_PLAN_METHOD_LOOKUP_ERRORS:
        return ()
    return tuple(sorted(signature.input_slot_names))


def _output_slot_names(registry: MethodRegistry, fqn: str) -> tuple[str, ...]:
    try:
        signature = registry.get(fqn).signature
    except _EXECUTION_PLAN_METHOD_LOOKUP_ERRORS:
        return ()
    return tuple(sorted(signature.output_slot_names))


def _edges_from_nodes(nodes: list[MethodDagNode]) -> list[MethodDagEdge]:
    edges: list[MethodDagEdge] = []
    for node in nodes:
        for dep_id in node.depends_on:
            edges.append(MethodDagEdge(src=dep_id, dst=node.node_id, relation="depends_on"))
    edges.sort(key=lambda edge: (edge.src, edge.dst, edge.relation))
    return edges


def _mutation_note(mutation: TopologyMutation) -> str:
    if mutation.kind is TopologyMutationKind.SWAP_METHOD:
        return f"swap:{mutation.node_id}->{mutation.replacement_method_fqn}"
    if mutation.kind is TopologyMutationKind.INSERT_ADAPTER:
        return (
            f"adapter:{mutation.upstream_node_id or 'auto'}->{mutation.node_id}"
            f":{mutation.adapter_method_fqn}"
        )
    return f"drop_optional:{mutation.node_id}"


class ExecutionPlanBenchmarkEvaluator(BenchmarkedEvaluator):
    """Execution plan benchmark evaluator public type."""

    def __init__(
        self,
        *,
        store: Any | None = None,
        registry: ChampionRegistry | None = None,
    ) -> None:
        self._store = store
        self._registry = registry

    def evaluate(self, candidate_ref, suite_ref, context: dict[str, Any]) -> BenchmarkEvaluation:
        store = context.get("store") or self._store
        if store is None:
            raise ValueError("ExecutionPlanBenchmarkEvaluator requires a CAS store")
        suite = load_model_artifact(store, suite_ref, BenchmarkSuite)
        config = load_model_artifact(store, candidate_ref, ExecutionPlanSearchConfig)
        if suite.dataset_path is None or suite.split_manifest_path is None:
            raise ValueError(
                "Execution plan benchmark suite requires dataset_path and split_manifest_path"
            )
        runner = context.get("execution_plan_runner")
        if not callable(runner):
            raise ValueError("context['execution_plan_runner'] must be callable")
        rows = _read_jsonl(Path(suite.dataset_path))
        split_manifest = read_split_manifest(Path(suite.split_manifest_path))
        champion_governance = self._champion_governance_score(
            candidate_ref=candidate_ref,
            suite=suite,
            rows=rows,
            runner=runner,
            split_manifest=split_manifest,
            context=context,
        )
        selection_cases = _run_execution_plan_cases(
            config=config,
            rows=[
                row
                for row in rows
                if split_manifest.split_for(str(row["case_id"])) == BenchmarkSplit.SELECTION
            ],
            runner=runner,
            context=context,
        )
        holdout_cases = _run_execution_plan_cases(
            config=config,
            rows=[
                row
                for row in rows
                if split_manifest.split_for(str(row["case_id"])) == BenchmarkSplit.HOLDOUT
            ],
            runner=runner,
            context=context,
        )
        selection_metrics = _execution_plan_metrics(selection_cases)
        holdout_metrics = _execution_plan_metrics(holdout_cases)
        guardrails = {
            "no_new_blockers": float(holdout_metrics.get("blocker_free_rate", 0.0)) >= 1.0,
            "governance_not_degraded": float(holdout_metrics.get("governance_score", 0.0))
            >= champion_governance,
            "compatibility_ok": float(holdout_metrics.get("compatibility_rate", 0.0)) >= 1.0,
        }
        return BenchmarkEvaluation(
            loop_id=EXECUTION_PLAN_LOOP_ID,
            suite_id=suite.suite_id,
            suite_version=suite.suite_version,
            candidate_ref=candidate_ref,
            selection_metrics=selection_metrics,
            holdout_metrics=holdout_metrics,
            sample_counts={
                BenchmarkSplit.SELECTION.value: int(selection_metrics.get("sample_count", 0.0)),
                BenchmarkSplit.HOLDOUT.value: int(holdout_metrics.get("sample_count", 0.0)),
            },
            guardrails=guardrails,
            promotable=all(guardrails.values()),
        )

    def _champion_governance_score(
        self,
        *,
        candidate_ref,
        suite: BenchmarkSuite,
        rows: list[dict[str, Any]],
        runner: Any,
        split_manifest,
        context: dict[str, Any],
    ) -> float:
        registry = context.get("registry") or self._registry
        store = context.get("store") or self._store
        if registry is None or store is None:
            return 0.0
        champion = registry.get(EXECUTION_PLAN_LOOP_ID)
        if champion is None or champion.candidate_ref.artifact_id == candidate_ref.artifact_id:
            return 0.0
        cfg = load_model_artifact(store, champion.candidate_ref, ExecutionPlanSearchConfig)
        metrics = _execution_plan_metrics(
            _run_execution_plan_cases(
                config=cfg,
                rows=[
                    row
                    for row in rows
                    if split_manifest.split_for(str(row["case_id"])) == BenchmarkSplit.HOLDOUT
                ],
                runner=runner,
                context=context,
            )
        )
        return float(metrics.get("governance_score", 0.0))


def execution_plan_search_loop_spec(
    *,
    candidate_generator: Any | None = None,
    store: Any | None = None,
    registry: ChampionRegistry | None = None,
) -> SearchLoopSpec:
    """Execution plan search loop spec helper."""
    return SearchLoopSpec(
        loop_id=EXECUTION_PLAN_LOOP_ID,
        mutation_codec=PydanticMutationCodec(ExecutionPlanSearchConfig),
        candidate_generator=candidate_generator or CapabilityAwareExecutionPlanCandidateGenerator(),
        benchmark_evaluator=ExecutionPlanBenchmarkEvaluator(store=store, registry=registry),
        promotion_policy=default_execution_plan_policy(),
        runtime_loader=None,
    )


def _run_execution_plan_cases(
    *,
    config: ExecutionPlanSearchConfig,
    rows: list[dict[str, Any]],
    runner: Any,
    context: dict[str, Any],
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for row in rows:
        result = runner(row, config, context)
        if not isinstance(result, dict):
            raise TypeError("execution_plan_runner must return dict-like case results")
        cases.append(result)
    return cases


def _execution_plan_metrics(cases: list[dict[str, Any]]) -> dict[str, float]:
    if not cases:
        return {
            "sample_count": 0.0,
            "composite_score": 0.0,
            "preflight_pass_rate": 0.0,
            "governance_score": 0.0,
            "backtest_score": 0.0,
            "cross_graph_coverage": 0.0,
            "run_cost_score": 0.0,
            "blocker_free_rate": 0.0,
            "compatibility_rate": 0.0,
        }
    preflight_ready = []
    blocker_free = []
    governance_scores = []
    backtest_scores = []
    cross_graph_scores = []
    cost_scores = []
    compatibility_scores = []
    for case in cases:
        preflight = _coerce_preflight(case.get("preflight_report"))
        governance = _coerce_governance(case.get("governance_report"))
        backtest = _backtest_score(case.get("backtest_summary") or {})
        cross_graph = _cross_graph_score(case.get("cross_graph_summary") or {})
        cost = _run_cost_score(case.get("run_stats") or {})
        compatibility_ok = 1.0 if bool(case.get("compatibility_ok", True)) else 0.0
        preflight_ready.append(1.0 if preflight.ready_to_run else 0.0)
        blocker_free.append(1.0 if not _has_blocking_diagnostics(preflight) else 0.0)
        governance_scores.append(_governance_score(governance))
        backtest_scores.append(backtest)
        cross_graph_scores.append(cross_graph)
        cost_scores.append(cost)
        compatibility_scores.append(compatibility_ok)
    composite = (
        _avg(preflight_ready) * 0.20
        + _avg(governance_scores) * 0.20
        + _avg(backtest_scores) * 0.25
        + _avg(cross_graph_scores) * 0.20
        + _avg(cost_scores) * 0.15
    )
    return {
        "sample_count": float(len(cases)),
        "composite_score": composite,
        "preflight_pass_rate": _avg(preflight_ready),
        "governance_score": _avg(governance_scores),
        "backtest_score": _avg(backtest_scores),
        "cross_graph_coverage": _avg(cross_graph_scores),
        "run_cost_score": _avg(cost_scores),
        "blocker_free_rate": _avg(blocker_free),
        "compatibility_rate": _avg(compatibility_scores),
    }


def _coerce_preflight(raw: Any) -> PreflightReport:
    if isinstance(raw, PreflightReport):
        return raw
    if isinstance(raw, dict):
        return PreflightReport.model_validate(raw)
    return PreflightReport(ready_to_run=False, diagnostics=[], notes=["missing_preflight_report"])


def _coerce_governance(raw: Any) -> GovernanceReport:
    if isinstance(raw, GovernanceReport):
        return raw
    if isinstance(raw, dict):
        return GovernanceReport.model_validate(raw)
    return GovernanceReport(verdict="reject", issues=[{"message": "missing_governance_report"}])


def _has_blocking_diagnostics(report: PreflightReport) -> bool:
    return any(diag.severity in {"error", "blocker"} for diag in report.diagnostics)


def _governance_score(report: GovernanceReport) -> float:
    return {
        "approve": 1.0,
        "needs_revision": 0.5,
        "human_gate": 0.0,
        "reject": 0.0,
    }.get(report.verdict, 0.0)


def _backtest_score(summary: dict[str, Any]) -> float:
    if "score" in summary:
        return max(0.0, min(1.0, float(summary["score"])))
    rmse = float(summary.get("rmse", 1.0) or 1.0)
    coverage = float(summary.get("coverage_probability", summary.get("coverage", 0.0)) or 0.0)
    return max(0.0, min(1.0, (1.0 / (1.0 + rmse)) * 0.6 + coverage * 0.4))


def _cross_graph_score(summary: dict[str, Any]) -> float:
    if "score" in summary:
        return max(0.0, min(1.0, float(summary["score"])))
    candidates = [
        summary.get("causal_supported_ratio"),
        summary.get("parameter_supported_ratio"),
        summary.get("scholar_query_coverage_ratio"),
        summary.get("coverage"),
    ]
    values = [float(value) for value in candidates if value is not None]
    return _avg(values)


def _run_cost_score(stats: dict[str, Any]) -> float:
    if "score" in stats:
        return max(0.0, min(1.0, float(stats["score"])))
    usd = float(stats.get("cost_usd", 0.0) or 0.0)
    runtime_seconds = float(stats.get("runtime_seconds", 0.0) or 0.0)
    return max(0.0, min(1.0, 1.0 / (1.0 + usd + (runtime_seconds / 60.0))))


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


__all__ = [
    "EXECUTION_PLAN_LOOP_ID",
    "CapabilityAwareExecutionPlanCandidateGenerator",
    "ExecutionPlanBenchmarkEvaluator",
    "ExecutionPlanSearchConfig",
    "ExecutionPlanSearchMode",
    "TopologyMutation",
    "TopologyMutationKind",
    "build_baseline_execution_plan_config",
    "build_execution_plan_generation_context",
    "default_execution_plan_policy",
    "execution_plan_search_loop_spec",
    "suggest_execution_plan_topology_mutations",
]
