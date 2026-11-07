from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import signal
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import Any

import duckdb
import pytest
from _helpers.run_lifecycle import (
    assert_one_resumed_terminal_lifecycle,
    start_or_resume_run,
)

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts import input_ref_from_artifact_ref, profile_bound_ref
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.tenant_context import (
    get_current_access_scope_or_none,
    reset_current_access_scope,
    set_current_access_scope,
    tenant_scope,
)
from polisyos.data_forge.domains.academic.knowledge.skg_query import (
    PreparedSKGRead,
    PreparedSKGReadReceipt,
    SKGQuery,
)
from polisyos.data_forge.read_api.academic import ParameterSelector
from polisyos.ir.analytics.causal_graph import (
    CausalGraphModel,
    GraphType,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.cross_graph import (
    CrossGraphEvidenceProfile,
    CrossGraphEvidenceSummary,
    load_cross_graph_evidence_profile,
    persist_cross_graph_evidence_profile,
)
from polisyos.ir.analytics.literature import (
    LiteratureCausalPrior,
    persist_literature_causal_prior,
)
from polisyos.ir.analytics.parameters import (
    ContextAdaptiveParameterBundleV11,
    ContextAdaptiveParameterBundleV12,
    load_context_adaptive_parameter_bundle,
    persist_context_adaptive_parameter_bundle_v1_1,
)
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ConstraintSpec, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.nodes.builtins.causal.build_literature_prior import (
    BuildLiteraturePriorNode,
)
from polisyos.scientist.nodes.builtins.causal.resolve_parameters import ResolveParametersNode
from polisyos.scientist.nodes.builtins.causal.resolve_transport import RunTransportabilityNode
from polisyos.scientist.nodes.builtins.planning.compile_cross_graph_evidence import (
    CompileCrossGraphEvidenceNode,
)
from polisyos.scientist.nodes.builtins.planning.run_discovery_blueprint_runtime import (
    RunDiscoveryBlueprintRuntimeNode,
)
from polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search import (
    HierarchicalPolicySearchAdapter,
    RunHierarchicalPolicySearchNode,
    _persist_trinity_bundle,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF,
    ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
    ARTIFACT_LITERATURE_PRIOR_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
    INPUT_TRINITY_BUNDLE_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import (
    WorkflowExecutionResult,
    WorkflowExecutor,
    WorkflowReport,
)
from polisyos.scientist.orchestration.engine.idempotency import (
    NodeCacheEntry,
    NodeResultCache,
)
from polisyos.scientist.orchestration.engine.protocol import NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.skg_snapshot import (
    SNAPSHOT_INPUT_KEY,
    load_retained_skg_snapshot,
    retain_prepared_skg_read,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema
from tests.unit.scientist.nodes import conftest as _node_fixtures

# Re-export the unit owner fixtures locally; their conftest scope excludes this integration tree.
cas_store = _node_fixtures.cas_store
registry_bundle_ref = _node_fixtures.registry_bundle_ref
execution_context = _node_fixtures.execution_context
minimal_state = _node_fixtures.minimal_state
artifact_ref_factory = _node_fixtures.artifact_ref_factory


_RESOLVE_NODE_ID = "scientist.node_resolve_parameters@1.0.0"


def _seed_skg(path: Path) -> None:
    connection = duckdb.connect(str(path))
    try:
        connection.execute("CREATE TABLE ac_skg_versions(version_id INTEGER)")
        connection.execute("INSERT INTO ac_skg_versions VALUES (7)")
        connection.execute(
            """
            CREATE TABLE ac_skg_simulation_parameters (
                numeric_id VARCHAR,
                openalex_id VARCHAR,
                canonical_name VARCHAR,
                estimate_type VARCHAR,
                point_estimate DOUBLE,
                estimate_sign VARCHAR,
                unit VARCHAR,
                evidence_strength VARCHAR,
                confidence_interval_json VARCHAR,
                std_error DOUBLE,
                source_layer VARCHAR,
                uncertainty_source VARCHAR,
                quality_flags_json VARCHAR,
                linked_claim_ids_json VARCHAR,
                linked_edges_json VARCHAR,
                context_json VARCHAR
            )
            """
        )
        connection.execute(
            """
            INSERT INTO ac_skg_simulation_parameters VALUES
                ('p1', 'W1', 'fiscal_multiplier', 'point', 1.4, 'positive',
                 'ratio', 'rct', '[1.1, 1.7]', NULL, 'simulation_ready',
                 'confidence_interval', '[]', '[]', '[]', ?)
            """,
            [json.dumps({"context_id": "us-2025", "countries": ["US"], "publication_year": 2025})],
        )
        connection.execute("CREATE TABLE unrelated_rows (value INTEGER)")
        connection.execute("INSERT INTO unrelated_rows VALUES (1)")
    finally:
        connection.close()


def _set_skg_value(path: Path, value: float) -> None:
    connection = duckdb.connect(str(path))
    try:
        connection.execute(
            "UPDATE ac_skg_simulation_parameters SET point_estimate = ?",
            [value],
        )
    finally:
        connection.close()


def _file_sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _set_unrelated_value(path: Path, value: int) -> None:
    connection = duckdb.connect(str(path))
    try:
        connection.execute("UPDATE unrelated_rows SET value = ?", [value])
    finally:
        connection.close()


@contextmanager
def _access_scope_context(access_scope: AccessScope | None) -> Iterator[None]:
    """Install one exact typed caller scope for lifecycle admission."""
    token = set_current_access_scope(access_scope)
    try:
        yield
    finally:
        reset_current_access_scope(token)


def _build_run_context(
    store: FileSystemCAS,
    run_id: str,
    *,
    tenant_id: str | None = None,
    cell_id: str | None = None,
    resume_from: ExecutionContext | None = None,
    selected_registry_profile: bool = False,
) -> tuple[ExecutionContext, NodeRegistry]:
    owner_scope = get_current_access_scope_or_none()
    if owner_scope is None and tenant_id is not None:
        owner_scope = AccessScope.for_service(
            tenant_id=tenant_id,
            cell_id=cell_id,
            spiffe_id="spiffe://polisyos.test/svc/skg-prepared-read-cache",
        )
    with (
        tenant_scope(None, tenant_id=tenant_id or "tenant-a", cell_id=cell_id),
        _access_scope_context(owner_scope),
    ):
        registry_bundle = (
            build_default_registry_bundle(
                store, return_selected_profile=selected_registry_profile
            ).bundle_ref
            if resume_from is None
            else None
        )
        run = start_or_resume_run(
            store,
            run_id=run_id,
            registry_bundle=registry_bundle,
            resume_from=None if resume_from is None else resume_from.run,
            tenant_id=tenant_id,
            cell_id=cell_id,
            access_scope=owner_scope,
        )
    context = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("skg_prepared_read_integration"),
    )
    registry = NodeRegistry()
    registry.register(ResolveParametersNode())
    return context, registry


def _workflow(*, timeout_s: float | None = None) -> WorkflowSpec:
    return WorkflowSpec(
        workflow_id="skg_prepared_read_cache",
        nodes=[
            NodeInvocation(
                alias="resolve",
                node_id=ComponentId.parse(_RESOLVE_NODE_ID),
                timeout_s=timeout_s,
            )
        ],
    )


def _trace_event_count(context: ExecutionContext) -> int:
    assert context.run.trace_path is not None
    return len(context.run.trace_path.read_text(encoding="utf-8").splitlines())


def _trace_events(
    context: ExecutionContext,
    *,
    start_line: int = 0,
) -> list[dict[str, object]]:
    assert context.run.trace_path is not None
    return [
        json.loads(line)
        for line in context.run.trace_path.read_text(encoding="utf-8").splitlines()[start_line:]
        if line.strip()
    ]


def _resolved_value(store: FileSystemCAS, state: ExperimentState) -> float:
    bundle_ref = state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        bundle = load_context_adaptive_parameter_bundle(
            _ensure_ir_artifact_store(store), bundle_ref
        )
    return float(bundle.parameters["fiscal_multiplier"].value)


def _execute_workflow(
    context: ExecutionContext,
    registry: NodeRegistry,
    workflow: WorkflowSpec,
    state: ExperimentState,
):
    with (
        tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"),
        _access_scope_context(context.run.access_scope),
    ):
        return WorkflowExecutor(context, registry).execute(workflow, state)


def _seed_input_bundle(context: ExecutionContext, state: ExperimentState) -> ExperimentState:
    """Produce a genuine initial ref that later declared nodes can restore without deletion."""
    with (
        tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"),
        _access_scope_context(context.run.access_scope),
    ):
        produced = ResolveParametersNode().execute(context, state)
    assert produced.status == "ok"
    initial = state.model_copy(deep=True)
    initial.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF] = (
        produced.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
    )
    return initial


def _async_skg_fixture(
    tmp_path: Path, run_id: str
) -> tuple[Path, FileSystemCAS, ExecutionContext, NodeRegistry, ExperimentState]:
    """Create one real scoped native source and owner for async consumer controls."""
    source = tmp_path / "async-source.duckdb"
    _seed_skg(source)
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", "cell-a")
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        graph_ref = persist_causal_graph_model(
            _ensure_ir_artifact_store(store),
            CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[]),
        )
    initial = ExperimentState(
        run_id=run_id,
        artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref},
        params={
            "target_context": {"context_id": "us-2025", "countries": ["US"]},
            "required_parameters": ["fiscal_multiplier"],
            "domain": "fiscal",
            "skg_db_path": str(source),
            "phase15_runtime_backend": "numpy",
        },
    )
    context, registry = _build_run_context(
        store,
        initial.run_id,
        tenant_id="tenant-a",
        cell_id="cell-a",
        selected_registry_profile=True,
    )
    return source, store, context, registry, initial


async def _execute_async_workflow(
    context: ExecutionContext,
    registry: NodeRegistry,
    workflow: WorkflowSpec,
    state: ExperimentState,
) -> WorkflowExecutionResult:
    from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor

    with (
        tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"),
        _access_scope_context(context.run.access_scope),
    ):
        return await AsyncWorkflowExecutor(context, registry, max_parallelism=1).execute(
            workflow, state
        )


class _SkgTransitionNode:
    """Mutate only owned fixture databases and restore the declared original bundle input."""

    def __init__(
        self,
        name: str,
        initial_bundle: ArtifactRef,
        updates: tuple[tuple[str, float | int, bool], ...] = (),
    ) -> None:
        self.name = name
        self.bundle_payload = initial_bundle.model_dump(mode="json")
        self.updates = updates

    @property
    def spec(self) -> NodeSpec:
        return NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse(f"test.skg_transition_{self.name}@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="SKG fixture transition",
                description="Declared transition between actual cold and warm invocations",
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=["params.study_source_inventory"],
            state_writes=[
                f"artifacts_index.{ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF}",
                "params.study_source_inventory",
            ],
        )

    def execute(self, _context: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        for source_path, value, unrelated in self.updates:
            path = Path(source_path)
            if unrelated:
                _set_unrelated_value(path, int(value))
            else:
                _set_skg_value(path, float(value))
            inventory = state.params.get("study_source_inventory")
            if isinstance(inventory, dict):
                for item in inventory.values():
                    if item["path"] == source_path:
                        item["sha256"] = _file_sha256(path)
        state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF] = (
            ArtifactRef.model_validate(self.bundle_payload)
        )
        return NodeOutcome(status="ok", state=state)


def _planned_skg_workflow(
    registry: NodeRegistry,
    initial: ExperimentState,
    phases: list[tuple[str, tuple[tuple[str, float | int, bool], ...]]],
) -> WorkflowSpec:
    """Declare every invocation before execution; no resumed full-DAG dispatch is inferred."""
    bundle_ref = ArtifactRef.model_validate(
        initial.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF].model_dump(
            mode="json"
        )
    )
    nodes = [NodeInvocation(alias="cold", node_id=_RESOLVE_NODE_ID)]
    previous = "cold"
    for name, updates in phases:
        transition = _SkgTransitionNode(name, bundle_ref, updates)
        registry.register(transition)
        transition_alias = f"prepare_{name}"
        nodes.extend(
            [
                NodeInvocation(
                    alias=transition_alias,
                    node_id=transition.spec.metadata.component_id,
                    depends_on=[previous],
                ),
                NodeInvocation(alias=name, node_id=_RESOLVE_NODE_ID, depends_on=[transition_alias]),
            ]
        )
        previous = name
    return WorkflowSpec(workflow_id="planned_skg_invocations", nodes=nodes)


def _phase_events(context: ExecutionContext, alias: str) -> list[dict[str, object]]:
    return [
        event for event in _trace_events(context) if event.get("phase") == f"scientist.node.{alias}"
    ]


def _phase_bundle_ref(report: WorkflowReport, alias: str) -> ArtifactRef:
    record = next(node for node in report.nodes if node.alias == alias)
    assert record.status == "ok", record.model_dump_json()
    return next(
        ref for ref in record.artifacts if ref.kind == "ir.context_adaptive_parameter_bundle"
    )


def _phase_value(store: FileSystemCAS, report: WorkflowReport, alias: str) -> float:
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        bundle = load_context_adaptive_parameter_bundle(
            _ensure_ir_artifact_store(store), _phase_bundle_ref(report, alias)
        )
    return float(bundle.parameters["fiscal_multiplier"].value)


def _trinity_bundle() -> TrinityBundle:
    return TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="skg_source_mutation",
            domain="social",
            hard_constraints=[
                ConstraintSpec(constraint_id="budget_cap", value=1, slot_id="budget")
            ],
        ),
        policy_spec=PolicySpec(policy_id="skg_source_mutation_policy"),
        model_spec=ModelSpec(
            model_id="skg_source_mutation_model",
            data_snapshot_ref="sha256:" + ("0" * 64),
        ),
    )


@pytest.mark.parametrize(
    ("node_type", "params"),
    [
        (BuildLiteraturePriorNode, {"skg_db_path": "/owner/skg.duckdb"}),
        (ResolveParametersNode, {"skg_db_path": "/owner/skg.duckdb"}),
        (RunTransportabilityNode, {"skg_db_path": "/owner/skg.duckdb"}),
        (
            CompileCrossGraphEvidenceNode,
            {"cross_graph_evidence_config": {"academic_db_path": "/owner/skg.duckdb"}},
        ),
        (
            RunDiscoveryBlueprintRuntimeNode,
            {"evidence_sources": {"academic_db_path": "/owner/skg.duckdb"}},
        ),
        (RunHierarchicalPolicySearchNode, {"skg_db_path": "/owner/skg.duckdb"}),
    ],
)
def test_each_skg_node_owner_prepares_the_selected_source(
    node_type: type[Any],
    params: dict[str, object],
    artifact_ref_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared_read = object()
    observed: list[tuple[str, str]] = []

    def prepare_read(*, db_path: Path, index_dir: Path) -> object:
        observed.append((str(db_path), str(index_dir)))
        return prepared_read

    monkeypatch.setattr(SKGQuery, "prepare_read", staticmethod(prepare_read))
    state_params = {
        **params,
        "causal_variables": ["fiscal_multiplier"],
        "target_context": {"context_id": "us-2025", "countries": ["US"]},
        "required_parameters": ["fiscal_multiplier"],
    }
    state = ExperimentState(
        run_id="R_owner_prepare",
        inputs={INPUT_TRINITY_BUNDLE_REF: artifact_ref_factory(kind="ir.trinity_bundle")},
        artifacts_index={
            ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: artifact_ref_factory(kind="ir.causal_graph_model")
        },
        params=state_params,
    )
    result = node_type().prepare_cache_input(SimpleNamespace(), state)

    assert result is prepared_read
    assert observed == [("/owner/skg.duckdb", "/owner")]


def test_hierarchical_candidate_callback_keeps_executor_prepared_read(
    execution_context,
    minimal_state,
    artifact_ref_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The direct nested ResolveParameters call receives the exact outer prepared owner read."""
    prepared_read = object()
    context = replace(execution_context, prepared_skg_read=prepared_read)
    candidate = PolicyCandidateSchema.from_trinity_bundle(
        _trinity_bundle(), candidate_id="candidate-prepared-read"
    )
    state = minimal_state.model_copy(deep=True)
    observed: list[object | None] = []
    selected_stores: list[object] = []

    def capture_prepared_read(
        ctx: ExecutionContext,
        _state: ExperimentState,
        *,
        candidate_payload: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, object]:
        typed_payload = {
            key: value for key, value in candidate_payload.items() if key != "candidate_hash"
        }
        assert PolicyCandidateSchema.model_validate(typed_payload) == candidate
        del context
        observed.append(ctx.prepared_skg_read)
        return {"status": "ok", "feasible": True, "objective_value": 1.0}

    def run_search(_adapter, _candidate, **kwargs):
        assert kwargs["source_store"] is context.store
        kwargs["stage_b_evaluator"](_candidate.as_search_payload(), {})
        return SimpleNamespace(model_dump=lambda mode="json": {"status": "ok"})

    def select_champion(_search_result, *, source_store):
        assert source_store is context.store
        selected_stores.append(source_store)
        return candidate

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search._evaluate_candidate_payload",
        capture_prepared_read,
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search._resolve_search_candidate",
        lambda _ctx, _state: candidate,
    )
    monkeypatch.setattr(
        HierarchicalPolicySearchAdapter,
        "run_search",
        run_search,
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search._select_champion_candidate",
        select_champion,
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search._persist_trinity_bundle",
        lambda *_args, **_kwargs: artifact_ref_factory(kind="ir.trinity_bundle"),
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search._persist_frontier_report",
        lambda *_args, **_kwargs: None,
    )

    outcome = RunHierarchicalPolicySearchNode().execute(context, state)

    assert outcome.status == "ok"
    assert observed == [prepared_read]
    assert selected_stores == [context.store]


def test_workflow_executor_binds_source_transaction_and_emits_hit_receipt(tmp_path: Path) -> None:
    """The source-byte binding admits exact hits and rejects changed database bytes."""
    db_path = tmp_path / "skg.duckdb"
    _seed_skg(db_path)
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", "cell-a")
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        graph_ref = persist_causal_graph_model(
            _ensure_ir_artifact_store(store),
            CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[]),
        )
    initial_state = ExperimentState(
        run_id="R_skg_prepared_read_cache",
        artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref},
        params={
            "target_context": {
                "context_id": "us-2025",
                "countries": ["US"],
                "publication_year": 2025,
            },
            "required_parameters": ["fiscal_multiplier"],
            "domain": "fiscal",
            "skg_db_path": str(db_path),
        },
    )
    ctx_first, registry_first = _build_run_context(
        store,
        initial_state.run_id,
        selected_registry_profile=True,
        tenant_id="tenant-a",
        cell_id="cell-a",
    )
    initial_state = _seed_input_bundle(ctx_first, initial_state)
    workflow = _planned_skg_workflow(
        registry_first,
        initial_state,
        [
            ("warm", ()),
            ("unrelated", ((str(db_path), 2, True),)),
            ("changed", ((str(db_path), 2.6, False),)),
        ],
    )
    changed = _execute_workflow(ctx_first, registry_first, workflow, initial_state)
    assert changed.report.status == "ok"
    first_events = _phase_events(ctx_first, "cold")
    first_value = _phase_value(store, changed.report, "cold")
    assert first_value == 1.4
    bundle_ref = _phase_bundle_ref(changed.report, "cold")
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        first_bundle = load_context_adaptive_parameter_bundle(
            _ensure_ir_artifact_store(store), bundle_ref
        )
        assert isinstance(first_bundle, ContextAdaptiveParameterBundleV12)
        source_ref = first_bundle.selected_skg_source.descriptor_ref
        source_snapshot = load_retained_skg_snapshot(store, source_ref)
        source_manifest = store.get_manifest(source_ref)
        cold_store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", "cell-a")
        cold_bundle = load_context_adaptive_parameter_bundle(
            _ensure_ir_artifact_store(cold_store), bundle_ref
        )
    assert source_snapshot.source_version_id == first_bundle.skg_version_id == 7
    assert source_snapshot.version_identity_kind == "content_digest"
    assert source_snapshot.source_sha256 == first_bundle.selected_skg_source.source_sha256
    assert first_bundle.selected_skg_source.source_reference == source_snapshot.source_reference
    assert source_manifest.artifact_schema is not None
    assert source_manifest.artifact_schema.version == "1.1"
    assert isinstance(cold_bundle, ContextAdaptiveParameterBundleV12)
    assert cold_bundle.selected_skg_source == first_bundle.selected_skg_source
    assert any(
        item.role == "skg_source_snapshot"
        and str(item.artifact_id) == str(source_ref.artifact_id)
        and item.manifest_profile_sha256 == source_ref.manifest_profile_sha256
        for item in store.get_manifest(bundle_ref).inputs
    )
    cache_store_event = next(
        event for event in first_events if event.get("event") == "NODE_CACHE_STORE"
    )
    cache_entry_ref = ArtifactRef.model_validate(cache_store_event["refs"]["outputs"][0])
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        cache_entry = NodeCacheEntry.model_validate(
            from_canonical_bytes(store.get_bytes(cache_entry_ref.artifact_id))
        )
    assert cache_entry.outcome_payload is not None
    cached_events = [
        NodeEvent.model_validate(event) for event in cache_entry.outcome_payload.get("events", [])
    ]
    origin_events = [
        event for event in cached_events if event.code == "skg.prepared_connection_query"
    ]
    assert len(origin_events) == 1
    origin_attrs = origin_events[0].attrs
    assert origin_attrs["read_evidence_scope"] == "bound_connection_query_execution_only"
    assert origin_attrs["output_dependency"] == "not_established"
    query_fingerprints = json.loads(origin_attrs["connection_query_fingerprints_json"])
    assert query_fingerprints

    hit_events = [
        event
        for event in _phase_events(ctx_first, "warm")
        if event.get("event") == "NODE_CACHE_HIT"
    ]
    assert len(hit_events) == 1
    assert _phase_value(store, changed.report, "warm") == first_value
    hit_record = next(node for node in changed.report.nodes if node.alias == "warm")
    receipt_refs = [
        ref for ref in hit_record.artifacts if ref.kind == "scientist.skg_cache_read_receipt"
    ]
    assert len(receipt_refs) == 1
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        receipt = PreparedSKGReadReceipt.model_validate_json(
            store.get_bytes(receipt_refs[0].artifact_id)
        )
    assert receipt.cache_key == cache_entry.idempotency_key
    assert receipt.authority_band == "candidate"
    assert receipt.source_snapshot_authenticity == "not_established"
    assert receipt.schema_version == "scientist.skg_cache_read_receipt.v3"
    assert receipt.query_version == "skg-query-read.v3"
    assert receipt.read_evidence_scope == "bound_connection_query_execution_only"
    assert receipt.output_dependency == "not_established"
    assert receipt.current_source_snapshot_sha256 == receipt.original_source_snapshot_sha256
    assert receipt.source_binding_schema_version == "academic.skg_source_binding.v2"
    assert receipt.time_semantics == "read_transaction_opened_at"
    assert receipt.current_prepared_at >= receipt.original_prepared_at
    assert any(
        ref.kind == "ir.context_adaptive_parameter_bundle" for ref in receipt.original_output_refs
    )

    foreign_store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-b", "cell-a")
    with (
        tenant_scope(None, tenant_id="tenant-b", cell_id="cell-a"),
        pytest.raises(ArtifactOwnershipError),
    ):
        foreign_store.get_bytes(receipt_refs[0].artifact_id)

    unrelated_events = _phase_events(ctx_first, "unrelated")
    assert _phase_value(store, changed.report, "unrelated") == first_value
    assert not any(event.get("event") == "NODE_CACHE_HIT" for event in unrelated_events)
    assert sum(event.get("event") == "NODE_CACHE_STORE" for event in unrelated_events) == 1
    assert _resolved_value(store, changed.state) == 2.6
    changed_events = _phase_events(ctx_first, "changed")
    assert not any(event.get("event") == "NODE_CACHE_HIT" for event in changed_events)
    assert sum(event.get("event") == "NODE_CACHE_STORE" for event in changed_events) == 1
    assert_one_resumed_terminal_lifecycle(ctx_first.run, expected_resumes=0)


def test_executor_reuses_selected_skg_a_when_unconsumed_study_source_b_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Changing another inventoried DB preserves A's real cache hit and state."""
    source_dir = tmp_path / "study-sources"
    source_dir.mkdir()
    selected_a = source_dir / "selected-a.duckdb"
    other_b = source_dir / "other-b.duckdb"
    _seed_skg(selected_a)
    _seed_skg(other_b)
    _set_skg_value(other_b, 3.5)
    initial_inventory = {
        "selected_a": {"path": str(selected_a), "sha256": _file_sha256(selected_a)},
        "other_b": {"path": str(other_b), "sha256": _file_sha256(other_b)},
    }
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", "cell-a")
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        graph_ref = persist_causal_graph_model(
            _ensure_ir_artifact_store(store),
            CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[]),
        )
    state = ExperimentState(
        run_id="R_skg_unconsumed_inventory_source_b",
        artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref},
        params={
            "target_context": {
                "context_id": "us-2025",
                "countries": ["US"],
                "publication_year": 2025,
            },
            "required_parameters": ["fiscal_multiplier"],
            "domain": "fiscal",
            "skg_db_path": str(selected_a),
            "skg_index_dir": str(source_dir),
            # This generic state payload is a test-only inventory of study inputs.
            "study_source_inventory": initial_inventory,
        },
    )
    first_context, first_registry = _build_run_context(
        store,
        state.run_id,
        selected_registry_profile=True,
        tenant_id="tenant-a",
        cell_id="cell-a",
    )
    state = _seed_input_bundle(first_context, state)
    workflow = _planned_skg_workflow(
        first_registry,
        state,
        [("after_b", ((str(other_b), 4.5, False),)), ("after_a", ((str(selected_a), 2.6, False),))],
    )
    executions: list[tuple[Path, float]] = []
    bindings: list[dict[str, str]] = []
    validated_inventories: list[dict[str, Any]] = []
    original_validate = ResolveParametersNode.validate_cache_hit
    original_execute = ResolveParametersNode.execute
    original_binding = PreparedSKGRead.cache_binding

    def record_real_resolve(
        node: ResolveParametersNode,
        context: ExecutionContext,
        current_state: ExperimentState,
    ) -> NodeOutcome:
        assert context.prepared_skg_read is not None
        prepared_path = context.prepared_skg_read.db_path
        outcome = original_execute(node, context, current_state)
        assert outcome.status == "ok"
        executions.append((prepared_path, _resolved_value(store, outcome.state)))
        return outcome

    def record_real_binding(
        prepared: PreparedSKGRead,
        *,
        selector_version: str,
    ) -> dict[str, str]:
        binding = original_binding(prepared, selector_version=selector_version)
        bindings.append(binding)
        return binding

    def record_real_validate(node, context, current_state, cached_outcome):
        validated_inventories.append(
            current_state.model_dump(mode="python")["params"]["study_source_inventory"]
        )
        return original_validate(node, context, current_state, cached_outcome)

    monkeypatch.setattr(ResolveParametersNode, "execute", record_real_resolve)
    monkeypatch.setattr(ResolveParametersNode, "validate_cache_hit", record_real_validate)
    monkeypatch.setattr(PreparedSKGRead, "cache_binding", record_real_binding)
    result = _execute_workflow(first_context, first_registry, workflow, state)
    assert result.report.status == "ok", result.report.model_dump_json(indent=2)
    assert _phase_value(store, result.report, "cold") == 1.4
    assert _phase_value(store, result.report, "after_b") == 1.4
    assert _phase_value(store, result.report, "after_a") == 2.6
    assert executions == [(selected_a, 1.4), (selected_a, 2.6)]
    b_events = _phase_events(first_context, "after_b")
    assert [event.get("event") for event in b_events].count("NODE_CACHE_HIT") == 1
    assert not any(event.get("event") == "NODE_CACHE_STORE" for event in b_events)
    a_events = _phase_events(first_context, "after_a")
    assert not any(event.get("event") == "NODE_CACHE_HIT" for event in a_events)
    assert sum(event.get("event") == "NODE_CACHE_STORE" for event in a_events) == 1
    old_b_digest = initial_inventory["other_b"]["sha256"]
    new_b_digest = _file_sha256(other_b)
    assert new_b_digest != old_b_digest
    with duckdb.connect(str(other_b), read_only=True) as connection:
        assert connection.execute(
            "SELECT point_estimate FROM ac_skg_simulation_parameters "
            "WHERE canonical_name = 'fiscal_multiplier'"
        ).fetchone() == (4.5,)
    old_a_digest = initial_inventory["selected_a"]["sha256"]
    new_a_digest = _file_sha256(selected_a)
    assert new_a_digest != old_a_digest
    assert len(validated_inventories) == 1
    assert validated_inventories[0]["other_b"]["sha256"] == new_b_digest
    assert validated_inventories[0]["selected_a"]["sha256"] == old_a_digest
    assert result.state.params["study_source_inventory"]["selected_a"]["sha256"] == new_a_digest
    assert result.state.params["study_source_inventory"]["other_b"]["sha256"] == new_b_digest
    assert len(bindings) == 3
    assert all(
        binding["source_snapshot_ref"].startswith(f"duckdb://{selected_a}") for binding in bindings
    )
    assert [binding["source_snapshot_sha256"] for binding in bindings] == [
        old_a_digest,
        old_a_digest,
        new_a_digest,
    ]
    cold_store_event = next(
        event
        for event in _phase_events(first_context, "cold")
        if event.get("event") == "NODE_CACHE_STORE"
    )
    cold_ref = ArtifactRef.model_validate(cold_store_event["refs"]["outputs"][0])
    cold_entry = NodeCacheEntry.model_validate(from_canonical_bytes(store.get_bytes(cold_ref)))
    hit_record = next(node for node in result.report.nodes if node.alias == "after_b")
    hit_ref = next(
        ref for ref in hit_record.artifacts if ref.kind == "scientist.skg_cache_read_receipt"
    )
    receipt = PreparedSKGReadReceipt.model_validate_json(store.get_bytes(hit_ref))
    assert receipt.cache_key == cold_entry.idempotency_key
    assert_one_resumed_terminal_lifecycle(first_context.run, expected_resumes=0)


def test_workflow_executor_scopes_constant_query_as_execution_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A constant SELECT proves connection execution, not SKG row use or output dependence."""
    db_path = tmp_path / "skg-constant-query.duckdb"
    _seed_skg(db_path)
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", "cell-a")
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        graph_ref = persist_causal_graph_model(
            _ensure_ir_artifact_store(store),
            CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[]),
        )
    state = ExperimentState(
        run_id="R_skg_constant_query_scope",
        artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref},
        params={
            "target_context": {"context_id": "us-2025", "countries": ["US"]},
            "required_parameters": ["fiscal_multiplier"],
            "domain": "fiscal",
            "skg_db_path": str(db_path),
        },
    )
    observed: list[int] = []

    def execute_constant_query(_self, ctx, current_state):
        assert ctx.prepared_skg_read is not None
        value = ctx.prepared_skg_read.query._con.execute("SELECT 1").fetchone()[0]
        observed.append(int(value))
        return NodeOutcome(status="ok", state=current_state)

    monkeypatch.setattr(ResolveParametersNode, "execute", execute_constant_query)
    monkeypatch.setattr(ResolveParametersNode, "validate_cache_hit", lambda *_args: True)

    first_context, first_registry = _build_run_context(
        store, state.run_id, selected_registry_profile=True, tenant_id="tenant-a", cell_id="cell-a"
    )
    workflow = WorkflowSpec(
        workflow_id="constant_query_cold_warm",
        nodes=[
            NodeInvocation(alias="cold", node_id=_RESOLVE_NODE_ID),
            NodeInvocation(alias="warm", node_id=_RESOLVE_NODE_ID, depends_on=["cold"]),
        ],
    )
    hit = _execute_workflow(first_context, first_registry, workflow, state)
    assert hit.report.status == "ok"
    assert observed == [1]
    first_events = _phase_events(first_context, "cold")
    store_event = next(event for event in first_events if event.get("event") == "NODE_CACHE_STORE")
    cache_entry_ref = ArtifactRef.model_validate(store_event["refs"]["outputs"][0])
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        cache_entry = NodeCacheEntry.model_validate(
            from_canonical_bytes(store.get_bytes(cache_entry_ref.artifact_id))
        )
    assert cache_entry.outcome_payload is not None
    origin = next(
        NodeEvent.model_validate(event)
        for event in cache_entry.outcome_payload.get("events", [])
        if event.get("code") == "skg.prepared_connection_query"
    )
    assert origin.attrs["connection_query_fingerprints_json"] == json.dumps(
        [hashlib.sha256(b"SELECT 1").hexdigest()], separators=(",", ":")
    )
    assert origin.attrs["read_evidence_scope"] == "bound_connection_query_execution_only"
    assert origin.attrs["output_dependency"] == "not_established"

    assert_one_resumed_terminal_lifecycle(first_context.run, expected_resumes=0)
    hit_record = next(node for node in hit.report.nodes if node.alias == "warm")
    assert any(
        event.get("event") == "NODE_CACHE_HIT" for event in _phase_events(first_context, "warm")
    )
    receipt_refs = [
        ref for ref in hit_record.artifacts if ref.kind == "scientist.skg_cache_read_receipt"
    ]
    assert len(receipt_refs) == 1
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        receipt = PreparedSKGReadReceipt.model_validate_json(
            store.get_bytes(receipt_refs[0].artifact_id)
        )
    assert receipt.read_evidence_scope == "bound_connection_query_execution_only"
    assert receipt.output_dependency == "not_established"


def test_workflow_executor_closes_prepared_reader_when_duckdb_error_escapes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The node resource owner closes its read transaction on an uncaught DuckDB error."""
    db_path = tmp_path / "skg-error-cleanup.duckdb"
    _seed_skg(db_path)
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", "cell-a")
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        graph_ref = persist_causal_graph_model(
            _ensure_ir_artifact_store(store),
            CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[]),
        )
    state = ExperimentState(
        run_id="R_skg_error_cleanup",
        artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref},
        params={
            "target_context": {"context_id": "us-2025", "countries": ["US"]},
            "required_parameters": ["fiscal_multiplier"],
            "domain": "fiscal",
            "skg_db_path": str(db_path),
        },
    )
    prepared_reads: list[PreparedSKGRead] = []
    close_calls: list[PreparedSKGRead] = []
    original_prepare = SKGQuery.prepare_read
    original_close = PreparedSKGRead.close

    def track_prepare(*, db_path: Path, index_dir: Path) -> PreparedSKGRead:
        prepared = original_prepare(db_path=db_path, index_dir=index_dir)
        prepared_reads.append(prepared)
        return prepared

    def track_close(prepared: PreparedSKGRead) -> None:
        close_calls.append(prepared)
        original_close(prepared)

    def execute_missing_relation(_self, ctx, _state):
        assert ctx.prepared_skg_read is not None
        ctx.prepared_skg_read.query._con.execute("SELECT * FROM __b61_missing_relation")
        raise AssertionError("DuckDB missing-relation query unexpectedly succeeded")

    monkeypatch.setattr(SKGQuery, "prepare_read", staticmethod(track_prepare))
    monkeypatch.setattr(PreparedSKGRead, "close", track_close)
    monkeypatch.setattr(ResolveParametersNode, "execute", execute_missing_relation)
    context, registry = _build_run_context(
        store, state.run_id, tenant_id="tenant-a", cell_id="cell-a"
    )

    with pytest.raises(duckdb.CatalogException):
        _execute_workflow(context, registry, _workflow(), state)

    assert len(prepared_reads) == 1
    assert close_calls == prepared_reads
    assert prepared_reads[0]._closed is True


@pytest.mark.asyncio
async def test_async_live_skg_rebinds_source_before_reusing_cached_prior(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_testsuite_property: Callable[[str, object], None],
) -> None:
    """Actual async cache reuse cannot turn an old source result into a current prior."""
    from polisyos.scientist.orchestration.engine import async_executor as async_module
    from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
    from polisyos.scientist.orchestration.engine.idempotency import compute_idempotency_key

    source = tmp_path / "async-live-skg.duckdb"
    _seed_skg(source)
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", "cell-a")
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        graph_ref = persist_causal_graph_model(
            _ensure_ir_artifact_store(store),
            CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[]),
        )
    initial = ExperimentState(
        run_id="R_async_live_skg_current_source",
        artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref},
        params={
            "target_context": {"context_id": "us-2025", "countries": ["US"]},
            "required_parameters": ["fiscal_multiplier"],
            "domain": "fiscal",
            "skg_db_path": str(source),
            "phase15_runtime_backend": "numpy",
        },
    )
    context, registry = _build_run_context(
        store,
        initial.run_id,
        tenant_id="tenant-a",
        cell_id="cell-a",
        selected_registry_profile=True,
    )
    initial = _seed_input_bundle(context, initial)
    workflow = _planned_skg_workflow(
        registry,
        initial,
        [("changed", ((str(source), 9.75, False),))],
    )
    key_observations: list[dict[str, str]] = []

    def observe_actual_key(**kwargs: Any) -> str:
        actual = compute_idempotency_key(**kwargs)
        if str(kwargs["spec"].metadata.component_id) == _RESOLVE_NODE_ID:
            unbound = dict(kwargs.get("bind_params") or {})
            unbound.pop("prepared_skg_read", None)
            declared = compute_idempotency_key(**{**kwargs, "bind_params": unbound})
            key_observations.append({"cache_key": actual, "declared_only_key": declared})
        return actual

    monkeypatch.setattr(async_module, "compute_idempotency_key", observe_actual_key)
    with (
        tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"),
        _access_scope_context(context.run.access_scope),
    ):
        result = await AsyncWorkflowExecutor(context, registry, max_parallelism=1).execute(
            workflow, initial
        )
        assert result.report.status == "ok", result.report.model_dump_json(indent=2)
        cold_event = next(
            event
            for event in _phase_events(context, "cold")
            if event.get("event") == "NODE_CACHE_STORE"
        )
        entry_ref = ArtifactRef.model_validate(cold_event["refs"]["outputs"][0])
        entry = NodeCacheEntry.model_validate(from_canonical_bytes(store.get_bytes(entry_ref)))
        old_ref = _phase_bundle_ref(result.report, "cold")
        current_ref = _phase_bundle_ref(result.report, "changed")
        old_bundle = load_context_adaptive_parameter_bundle(
            _ensure_ir_artifact_store(store), old_ref
        )
        current_bundle = load_context_adaptive_parameter_bundle(
            _ensure_ir_artifact_store(store), current_ref
        )
    with duckdb.connect(str(source), read_only=True) as connection:
        row = connection.execute(
            "SELECT point_estimate FROM ac_skg_simulation_parameters "
            "WHERE canonical_name = 'fiscal_multiplier'"
        ).fetchone()
    assert row == (9.75,)
    changed_events = _phase_events(context, "changed")
    observation = {
        "cold_entry_ref": entry_ref.model_dump(mode="json"),
        "cold_cache_key": entry.idempotency_key,
        "actual_key_observations": key_observations,
        "old_bundle_ref": old_ref.model_dump(mode="json"),
        "current_bundle_ref": current_ref.model_dump(mode="json"),
        "old_value": old_bundle.parameters["fiscal_multiplier"].value,
        "current_value": current_bundle.parameters["fiscal_multiplier"].value,
        "independent_live_value": row[0],
        "live_source_sha256": _file_sha256(source),
        "changed_cache_hits": sum(
            event.get("event") == "NODE_CACHE_HIT" for event in changed_events
        ),
        "authority": "Synthetic mechanism fixture; no empirical or institutional source authority",
    }
    record_testsuite_property(
        "async_live_skg_source_controls", json.dumps(observation, sort_keys=True)
    )
    assert len(key_observations) == 2
    assert key_observations[0]["declared_only_key"] == key_observations[1]["declared_only_key"]
    assert key_observations[0]["cache_key"] == entry.idempotency_key
    assert key_observations[1]["cache_key"] != entry.idempotency_key
    assert old_bundle.parameters["fiscal_multiplier"].value == 1.4
    assert current_bundle.parameters["fiscal_multiplier"].value == 9.75
    assert not any(event.get("event") == "NODE_CACHE_HIT" for event in changed_events)


@pytest.mark.asyncio
@pytest.mark.parametrize("selected_snapshot", [False, True], ids=["live", "retained"])
async def test_async_same_source_hit_persists_fresh_receipt_and_origin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    selected_snapshot: bool,
) -> None:
    """Actual async reuse retains its source lineage and a current candidate read receipt."""
    source, store, context, registry, initial = _async_skg_fixture(
        tmp_path, f"R_async_warm_skg_{selected_snapshot}"
    )
    initial = _seed_input_bundle(context, initial)
    selected_ref = None
    if selected_snapshot:
        prepared = SKGQuery.prepare_read(db_path=source, index_dir=tmp_path)
        try:
            with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
                selected_ref = retain_prepared_skg_read(store, prepared)
        finally:
            prepared.close()
        initial.inputs[SNAPSHOT_INPUT_KEY] = selected_ref
    if selected_snapshot:
        _set_skg_value(source, 9.75)
    workflow = _planned_skg_workflow(registry, initial, [("warm", ())])
    readers: list[PreparedSKGRead] = []
    closes: list[PreparedSKGRead] = []
    binding_connections: list[tuple[PreparedSKGRead, int]] = []
    producer_connections: list[tuple[PreparedSKGRead, int]] = []
    validator_connections: list[tuple[PreparedSKGRead, int]] = []
    original_prepare = SKGQuery.prepare_read
    original_close = PreparedSKGRead.close
    original_binding = PreparedSKGRead.cache_binding
    original_execute = ResolveParametersNode.execute
    original_validate = ResolveParametersNode.validate_cache_hit

    def track_prepare(*, db_path: Path, index_dir: Path) -> PreparedSKGRead:
        reader = original_prepare(db_path=db_path, index_dir=index_dir)
        readers.append(reader)
        return reader

    def track_close(reader: PreparedSKGRead) -> None:
        closes.append(reader)
        original_close(reader)

    def track_binding(reader: PreparedSKGRead, **kwargs: Any):
        binding_connections.append((reader, id(reader.query._confidence_connection())))
        return original_binding(reader, **kwargs)

    def track_execute(self, ctx, state):
        reader = ctx.prepared_skg_read
        assert isinstance(reader, PreparedSKGRead)
        producer_connections.append((reader, id(reader.query._confidence_connection())))
        return original_execute(self, ctx, state)

    def track_validate(self, ctx, state, outcome):
        reader = ctx.prepared_skg_read
        assert isinstance(reader, PreparedSKGRead)
        validator_connections.append((reader, id(reader.query._confidence_connection())))
        return original_validate(self, ctx, state, outcome)

    monkeypatch.setattr(SKGQuery, "prepare_read", staticmethod(track_prepare))
    monkeypatch.setattr(PreparedSKGRead, "close", track_close)
    monkeypatch.setattr(PreparedSKGRead, "cache_binding", track_binding)
    monkeypatch.setattr(ResolveParametersNode, "execute", track_execute)
    monkeypatch.setattr(ResolveParametersNode, "validate_cache_hit", track_validate)
    result = await _execute_async_workflow(context, registry, workflow, initial)
    assert result.report.status == "ok", result.report.model_dump_json(indent=2)
    assert _phase_value(store, result.report, "cold") == 1.4
    assert _phase_value(store, result.report, "warm") == 1.4
    assert (
        sum(event.get("event") == "NODE_CACHE_HIT" for event in _phase_events(context, "warm")) == 1
    )
    assert len(readers) == 2
    assert closes == readers
    assert all(reader._closed is True for reader in readers)
    assert producer_connections == [binding_connections[0]]
    assert validator_connections == [binding_connections[1]]
    assert [reader for reader, _connection in binding_connections] == readers
    warm_record = next(record for record in result.report.nodes if record.alias == "warm")
    receipt_refs = [
        ref for ref in warm_record.artifacts if ref.kind == "scientist.skg_cache_read_receipt"
    ]
    assert len(receipt_refs) == 1
    cold_event = next(
        event
        for event in _phase_events(context, "cold")
        if event.get("event") == "NODE_CACHE_STORE"
    )
    entry_ref = ArtifactRef.model_validate(cold_event["refs"]["outputs"][0])
    fresh = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", "cell-a")
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        fresh_cache = NodeResultCache(fresh, run_id=initial.run_id)
        assert fresh_cache.load_entry(entry_ref)
        entry = NodeCacheEntry.model_validate(from_canonical_bytes(fresh.get_bytes(entry_ref)))
        cached = fresh_cache.get(entry.idempotency_key)
        assert cached is not None
        origins = [
            event for event in cached.events if event.code == "skg.prepared_connection_query"
        ]
        assert len(origins) == 1
        origin = origins[0].attrs
        retained_ref = ArtifactRef.model_validate_json(origin["retained_snapshot_ref_json"])
        retained = load_retained_skg_snapshot(fresh, retained_ref)
        receipt = PreparedSKGReadReceipt.model_validate_json(fresh.get_bytes(receipt_refs[0]))
        warm_bundle = load_context_adaptive_parameter_bundle(
            _ensure_ir_artifact_store(fresh), _phase_bundle_ref(result.report, "warm")
        )
    assert receipt.run_id == initial.run_id
    assert receipt.node_id == _RESOLVE_NODE_ID
    assert receipt.cache_key == entry.idempotency_key
    assert receipt.current_source_snapshot_sha256 == receipt.original_source_snapshot_sha256
    assert receipt.current_source_snapshot_sha256 == origin["source_snapshot_sha256"]
    assert receipt.current_source_snapshot_sha256 == retained.source_sha256
    assert receipt.current_source_snapshot_ref == receipt.original_source_snapshot_ref
    assert receipt.current_prepared_at >= receipt.original_prepared_at
    assert receipt.authority_band == "candidate"
    assert receipt.source_snapshot_authenticity == "not_established"
    assert receipt.read_evidence_scope == "bound_connection_query_execution_only"
    assert receipt.output_dependency == "not_established"
    assert receipt.time_semantics == "read_transaction_opened_at"
    assert _phase_bundle_ref(result.report, "cold") in receipt.original_output_refs
    assert receipt_refs[0] not in receipt.original_output_refs
    assert origin["authority_band"] == "candidate"
    assert origin["read_evidence_scope"] == "bound_connection_query_execution_only"
    assert origin["output_dependency"] == "not_established"
    assert json.loads(origin["connection_query_fingerprints_json"])
    assert isinstance(warm_bundle, ContextAdaptiveParameterBundleV12)
    assert warm_bundle.selected_skg_source.descriptor_ref == retained_ref
    if selected_ref is not None:
        assert retained_ref == selected_ref
        assert result.state.inputs[SNAPSHOT_INPUT_KEY] == selected_ref
        assert _file_sha256(source) != retained.source_sha256
        with duckdb.connect(str(source), read_only=True) as connection:
            assert connection.execute(
                "SELECT point_estimate FROM ac_skg_simulation_parameters"
            ).fetchone() == (9.75,)
    else:
        assert _file_sha256(source) == retained.source_sha256
    assert_one_resumed_terminal_lifecycle(context.run, expected_resumes=0)


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["removed_key", "missing_origin", "wrong_origin"])
async def test_async_cache_origin_guard_recomputes_without_stale_or_unbound_hit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    """A real cache entry needs origin reconciliation after the independent matcher passes."""
    from polisyos.scientist.orchestration.engine import async_executor as async_module

    source, store, context, registry, initial = _async_skg_fixture(
        tmp_path, f"R_async_origin_{fault}"
    )
    initial = _seed_input_bundle(context, initial)
    updates = ((str(source), 9.75, False),) if fault == "removed_key" else ()
    workflow = _planned_skg_workflow(registry, initial, [("after_fault", updates)])
    original_key = async_module.compute_idempotency_key
    original_attach = async_module._attach_prepared_read_success
    original_execute = ResolveParametersNode.execute
    executions: list[PreparedSKGRead] = []
    attachments = 0

    def track_execute(self, ctx, state):
        assert isinstance(ctx.prepared_skg_read, PreparedSKGRead)
        executions.append(ctx.prepared_skg_read)
        return original_execute(self, ctx, state)

    def remove_prepared_key(**kwargs: Any) -> str:
        bind_params = dict(kwargs.get("bind_params") or {})
        bind_params.pop("prepared_skg_read", None)
        return original_key(**{**kwargs, "bind_params": bind_params})

    def corrupt_first_origin(**kwargs: Any) -> None:
        nonlocal attachments
        original_attach(**kwargs)
        attachments += 1
        if attachments != 1:
            return
        outcome = kwargs["outcome"]
        if fault == "missing_origin":
            outcome.events[:] = [
                event for event in outcome.events if event.code != "skg.prepared_connection_query"
            ]
        elif fault == "wrong_origin":
            outcome.events[:] = [
                event.model_copy(
                    update={"attrs": {**event.attrs, "source_snapshot_sha256": "f" * 64}}
                )
                if event.code == "skg.prepared_connection_query"
                else event
                for event in outcome.events
            ]

    monkeypatch.setattr(ResolveParametersNode, "execute", track_execute)
    if fault == "removed_key":
        monkeypatch.setattr(async_module, "compute_idempotency_key", remove_prepared_key)
        monkeypatch.setattr(ResolveParametersNode, "validate_cache_hit", lambda *_args: True)
    else:
        monkeypatch.setattr(async_module, "_attach_prepared_read_success", corrupt_first_origin)
    result = await _execute_async_workflow(context, registry, workflow, initial)
    assert result.report.status == "ok", result.report.model_dump_json(indent=2)
    assert _phase_value(store, result.report, "cold") == 1.4
    expected = 9.75 if fault == "removed_key" else 1.4
    assert _phase_value(store, result.report, "after_fault") == expected
    assert len(executions) == 2
    events = _phase_events(context, "after_fault")
    assert not any(event.get("event") == "NODE_CACHE_HIT" for event in events)
    assert any(
        event.get("event") == "NODE_CACHE_BYPASS"
        and event.get("metrics", {}).get("reason_code") == 5
        for event in events
    )
    cold_event = next(
        event
        for event in _phase_events(context, "cold")
        if event.get("event") == "NODE_CACHE_STORE"
    )
    entry_ref = ArtifactRef.model_validate(cold_event["refs"]["outputs"][0])
    fresh = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", "cell-a")
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        entry = NodeCacheEntry.model_validate(from_canonical_bytes(fresh.get_bytes(entry_ref)))
        fresh_cache = NodeResultCache(fresh, run_id=initial.run_id)
        assert fresh_cache.load_entry(entry_ref)
        cold_outcome = fresh_cache.get(entry.idempotency_key)
        assert cold_outcome is not None
        assert _resolved_value(fresh, cold_outcome.state) == 1.4
        origins = [
            event for event in cold_outcome.events if event.code == "skg.prepared_connection_query"
        ]
    if fault == "missing_origin":
        assert origins == []
    elif fault == "wrong_origin":
        assert len(origins) == 1
        assert origins[0].attrs["source_snapshot_sha256"] == "f" * 64
    else:
        assert len(origins) == 1
        assert origins[0].attrs["source_snapshot_sha256"] != _file_sha256(source)
    assert_one_resumed_terminal_lifecycle(context.run, expected_resumes=0)


@pytest.mark.asyncio
async def test_async_cancelled_preparation_closes_late_real_reader_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cancelled await does not strand the real reader returned by a late preparation."""
    _source, _store, context, registry, initial = _async_skg_fixture(
        tmp_path, "R_async_late_preparation"
    )
    entered, release, returning, closed = Event(), Event(), Event(), Event()
    readers: list[PreparedSKGRead] = []
    close_facts: list[tuple[PreparedSKGRead, bool]] = []
    original_prepare = ResolveParametersNode.prepare_cache_input
    original_close = PreparedSKGRead.close

    def delayed_prepare(self, ctx, state):
        reader = original_prepare(self, ctx, state)
        assert isinstance(reader, PreparedSKGRead)
        readers.append(reader)
        entered.set()
        try:
            assert release.wait(8), "test did not release the physical preparation"
            return reader
        finally:
            returning.set()

    def track_close(reader: PreparedSKGRead) -> None:
        close_facts.append((reader, returning.is_set()))
        original_close(reader)
        closed.set()

    monkeypatch.setattr(ResolveParametersNode, "prepare_cache_input", delayed_prepare)
    monkeypatch.setattr(PreparedSKGRead, "close", track_close)
    task = asyncio.create_task(_execute_async_workflow(context, registry, _workflow(), initial))
    try:
        assert await asyncio.to_thread(entered.wait, 6)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=3)
        assert len(readers) == 1
        assert readers[0]._closed is False
        assert close_facts == []
        assert not returning.is_set()
    finally:
        release.set()
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    assert await asyncio.to_thread(closed.wait, 6)
    assert close_facts == [(readers[0], True)]
    assert readers[0]._closed is True
    assert ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF not in initial.artifacts_index
    assert not any(
        event.get("event") in {"NODE_CACHE_HIT", "NODE_CACHE_STORE"}
        for event in _trace_events(context)
    )
    context.run.suspend_for_resume()


@pytest.mark.asyncio
@pytest.mark.parametrize("physical_user", ["producer", "validator"])
async def test_async_cancelled_physical_user_keeps_real_reader_until_return(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    physical_user: str,
) -> None:
    """A running producer or validator owns the native reader beyond coroutine cancellation."""
    _source, _store, context, registry, initial = _async_skg_fixture(
        tmp_path, f"R_async_reader_pin_{physical_user}"
    )
    workflow = _workflow()
    if physical_user == "validator":
        initial = _seed_input_bundle(context, initial)
        workflow = _planned_skg_workflow(registry, initial, [("warm", ())])
    entered, release, physical_done, closed = Event(), Event(), Event(), Event()
    held: list[PreparedSKGRead] = []
    close_facts: list[tuple[PreparedSKGRead, bool]] = []
    observed_values: list[float] = []
    errors: list[BaseException] = []
    original_close = PreparedSKGRead.close
    original_call = (
        ResolveParametersNode.execute
        if physical_user == "producer"
        else ResolveParametersNode.validate_cache_hit
    )

    def hold_actual_call(self, ctx, state, *args):
        reader = ctx.prepared_skg_read
        assert isinstance(reader, PreparedSKGRead)
        held.append(reader)
        entered.set()
        try:
            assert release.wait(8), "test did not release the physical reader user"
            assert reader._closed is False
            observed_values.append(
                float(reader.query.query_parameters("fiscal_multiplier")[0].parameter.value)
            )
            return original_call(self, ctx, state, *args)
        except BaseException as exc:
            errors.append(exc)
            raise
        finally:
            physical_done.set()

    def track_close(reader: PreparedSKGRead) -> None:
        close_facts.append((reader, physical_done.is_set()))
        original_close(reader)
        if held and reader is held[0]:
            closed.set()

    method = "execute" if physical_user == "producer" else "validate_cache_hit"
    monkeypatch.setattr(ResolveParametersNode, method, hold_actual_call)
    monkeypatch.setattr(PreparedSKGRead, "close", track_close)
    task = asyncio.create_task(_execute_async_workflow(context, registry, workflow, initial))
    try:
        assert await asyncio.to_thread(entered.wait, 6)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=3)
        assert len(held) == 1
        assert held[0]._closed is False
        assert not physical_done.is_set()
        assert not any(reader is held[0] for reader, _done in close_facts)
    finally:
        release.set()
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    assert await asyncio.to_thread(closed.wait, 6)
    assert observed_values == [1.4]
    assert [(reader, done) for reader, done in close_facts if reader is held[0]] == [
        (held[0], True)
    ]
    assert held[0]._closed is True
    if physical_user == "producer":
        from polisyos.scientist.orchestration.engine.retry import _AttemptWriteDeniedError

        assert len(errors) == 1
        assert isinstance(errors[0], _AttemptWriteDeniedError)
        assert ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF not in initial.artifacts_index
    else:
        assert errors == []
        cold_ref = next(
            ArtifactRef.model_validate(event["refs"]["outputs"][0])
            for event in _phase_events(context, "cold")
            if event.get("event") == "NODE_CACHE_STORE"
        )
        with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
            assert (
                FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", "cell-a").verify(cold_ref).ok
            )
        assert not any(
            event.get("event") in {"NODE_CACHE_HIT", "NODE_CACHE_STORE"}
            for event in _phase_events(context, "warm")
        )
    context.run.suspend_for_resume()


@pytest.mark.asyncio
@pytest.mark.parametrize(("timeout_s", "reason_code"), [(None, 5), (30.0, 7)])
async def test_async_preparer_protocol_keeps_ordinary_async_producer_available(
    tmp_path: Path, timeout_s: float | None, reason_code: int
) -> None:
    """An async producer without a physical-reader lifetime uses ordinary uncached execution."""
    _source, _store, context, registry, initial = _async_skg_fixture(
        tmp_path, f"R_async_preparer_protocol_{reason_code}"
    )

    class AsyncPreparedNode:
        def __init__(self) -> None:
            self.calls = 0
            self.preparations = 0

        @property
        def spec(self) -> NodeSpec:
            return NodeSpec(
                metadata=ComponentMetadata(
                    component_id=ComponentId.parse("test.async_prepared_consumer@1.0.0"),
                    kind=ComponentKind.SCIENTIST_NODE,
                    abi_targets={"world_abi": "1.x"},
                    display_name="Async prepared-protocol fixture",
                    description="Actual ordinary async execution without borrowed reader ownership",
                    capabilities=Capability.SCIENTIST_NODE,
                ),
                state_reads=["params"],
                state_writes=["params.async_producer_result"],
            )

        def prepare_cache_input(self, _ctx, _state) -> PreparedSKGRead:
            self.preparations += 1
            raise AssertionError("a detached coroutine cannot borrow the physical reader")

        def execute(self, _ctx, _state) -> NodeOutcome:
            raise AssertionError("the ordinary async producer must be selected")

        async def execute_async(self, ctx, state) -> NodeOutcome:
            self.calls += 1
            assert ctx.prepared_skg_read is None
            await asyncio.sleep(0)
            state.params["async_producer_result"] = 4
            return NodeOutcome(status="ok", state=state)

    node = AsyncPreparedNode()
    registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="async_preparer_protocol",
        nodes=[
            NodeInvocation(
                alias="async_consumer",
                node_id=node.spec.metadata.component_id,
                timeout_s=timeout_s,
            )
        ],
    )
    result = await _execute_async_workflow(context, registry, workflow, initial)
    assert result.report.status == "ok", result.report.model_dump_json(indent=2)
    assert result.state.params["async_producer_result"] == 4
    assert node.calls == 1
    assert node.preparations == 0
    events = _phase_events(context, "async_consumer")
    bypasses = [event for event in events if event.get("event") == "NODE_CACHE_BYPASS"]
    assert len(bypasses) == 1
    assert bypasses[0]["metrics"]["reason_code"] == reason_code
    assert not any(event.get("event") in {"NODE_CACHE_HIT", "NODE_CACHE_STORE"} for event in events)
    assert_one_resumed_terminal_lifecycle(context.run, expected_resumes=0)


def test_timed_executor_thread_fallback_bypasses_shared_read_until_worker_finishes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A late thread fallback read cannot persist after its timeout expires."""
    from polisyos.scientist.orchestration.engine import retry as retry_module

    db_path = tmp_path / "skg-timeout-lifetime.duckdb"
    _seed_skg(db_path)
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", "cell-a")
    underlying_store_write_calls: list[tuple[str, ArtifactRef | None]] = []
    for method_name in sorted(retry_module._STORE_WRITE_METHODS):
        original_store_write = getattr(store, method_name)

        def track_store_write(
            *args,
            _method_name=method_name,
            _original_store_write=original_store_write,
            return_selected_profile: bool = False,
            **kwargs,
        ):
            if _method_name in {"put_bytes", "put_json"}:
                kwargs["return_selected_profile"] = return_selected_profile
            call_index = len(underlying_store_write_calls)
            underlying_store_write_calls.append((_method_name, None))
            result = _original_store_write(*args, **kwargs)
            if isinstance(result, ArtifactRef):
                underlying_store_write_calls[call_index] = (_method_name, result)
            return result

        monkeypatch.setattr(store, method_name, track_store_write)
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        graph_ref = persist_causal_graph_model(
            _ensure_ir_artifact_store(store),
            CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[]),
        )
    state = ExperimentState(
        run_id="R_skg_timeout_lifetime",
        artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref},
        params={
            "target_context": {"context_id": "us-2025", "countries": ["US"]},
            "required_parameters": ["fiscal_multiplier"],
            "domain": "fiscal",
            "skg_db_path": str(db_path),
        },
    )
    warmup_input = state.model_copy(update={"run_id": f"{state.run_id}_warmup"})
    warmup_context, warmup_registry = _build_run_context(
        store,
        warmup_input.run_id,
        selected_registry_profile=True,
        tenant_id="tenant-a",
        cell_id="cell-a",
    )
    writes_before_warmup = tuple(underlying_store_write_calls)
    warmup = _execute_workflow(warmup_context, warmup_registry, _workflow(), warmup_input)
    warmup_report, warmup_state = warmup.report, warmup.state
    warmup_events = _trace_events(warmup_context)
    warmup_write_delta = tuple(underlying_store_write_calls)[len(writes_before_warmup) :]
    assert warmup_report.status == "ok"
    assert _resolved_value(store, warmup_state) == 1.4

    warmup_store_event = next(
        event for event in warmup_events if event.get("event") == "NODE_CACHE_STORE"
    )
    source_bound_entry_ref = ArtifactRef.model_validate(warmup_store_event["refs"]["outputs"][0])
    warmup_bundle_ref = ArtifactRef.model_validate(
        warmup_state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
    )
    assert any(method == "put_bytes" for method, _ref in warmup_write_delta)
    assert any(
        method == "put_bytes" and written_ref == source_bound_entry_ref
        for method, written_ref in warmup_write_delta
    )
    assert any(
        method == "put_bytes" and written_ref == warmup_bundle_ref
        for method, written_ref in warmup_write_delta
    )
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        source_bound_entry = NodeCacheEntry.model_validate(
            from_canonical_bytes(store.get_bytes(source_bound_entry_ref.artifact_id))
        )
        prior_cache = NodeResultCache(store, run_id=warmup_input.run_id)
        assert prior_cache.load_entry(source_bound_entry_ref)
        prior_outcome = prior_cache.get(source_bound_entry.idempotency_key)
        assert prior_outcome is not None
        assert _resolved_value(store, prior_outcome.state) == 1.4
    assert_one_resumed_terminal_lifecycle(warmup_context.run, expected_resumes=0)
    # Same-run stale/unbound-key faults are exercised by the planned alias controls.
    # This is a new logical timed invocation; its initially absent output must remain absent.
    context, registry = _build_run_context(
        store,
        state.run_id,
        selected_registry_profile=True,
        tenant_id="tenant-a",
        cell_id="cell-a",
    )
    assert ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF not in state.artifacts_index
    _set_skg_value(db_path, 2.6)
    trace_start = _trace_event_count(context)
    started = Event()
    release = Event()
    finished = Event()
    worker_outcomes: list[NodeOutcome] = []
    worker_errors: list[BaseException] = []
    selected_source_values: list[float] = []
    worker_context_facts: list[dict[str, object]] = []
    observed_shared: list[object | None] = []
    prepared_reads: list[PreparedSKGRead] = []
    close_calls: list[PreparedSKGRead] = []
    prepare_cache_calls: list[bool] = []
    cache_validation_calls: list[bool] = []
    original_execute = ResolveParametersNode.execute
    original_validate = ResolveParametersNode.validate_cache_hit
    original_select = ParameterSelector.select_for_context
    original_prepare = SKGQuery.prepare_read
    original_close = PreparedSKGRead.close
    original_prepare_cache = ResolveParametersNode.prepare_cache_input

    def track_prepare(*, db_path: Path, index_dir: Path) -> PreparedSKGRead:
        prepared = original_prepare(db_path=db_path, index_dir=index_dir)
        prepared_reads.append(prepared)
        return prepared

    def track_close(prepared: PreparedSKGRead) -> None:
        close_calls.append(prepared)
        original_close(prepared)

    def track_cache_prepare(self, ctx, current_state):
        prepare_cache_calls.append(True)
        return original_prepare_cache(self, ctx, current_state)

    def delayed_execute(_self, ctx, current_state):
        observed_shared.append(ctx.prepared_skg_read)
        worker_context_facts.append(
            {
                "context_type": type(ctx).__qualname__,
                "has_prepared_skg_read": hasattr(ctx, "prepared_skg_read"),
                "prepared_skg_read": ctx.prepared_skg_read,
            }
        )
        started.set()
        release.wait(timeout=6)
        try:
            outcome = original_execute(_self, ctx, current_state)
            worker_outcomes.append(outcome)
            return outcome
        except BaseException as exc:
            worker_errors.append(exc)
            raise
        finally:
            finished.set()

    def track_cache_validation(self, ctx, current_state, cached_outcome):
        cache_validation_calls.append(True)
        return original_validate(self, ctx, current_state, cached_outcome)

    def track_selected_source(self, *args, **kwargs):
        selected, applicability = original_select(self, *args, **kwargs)
        if selected is not None:
            selected_source_values.append(float(selected.value))
        return selected, applicability

    monkeypatch.setattr(retry_module, "mp", SimpleNamespace(get_all_start_methods=lambda: []))
    monkeypatch.setattr(retry_module, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(SKGQuery, "prepare_read", staticmethod(track_prepare))
    monkeypatch.setattr(PreparedSKGRead, "close", track_close)
    monkeypatch.setattr(ResolveParametersNode, "prepare_cache_input", track_cache_prepare)
    monkeypatch.setattr(ResolveParametersNode, "validate_cache_hit", track_cache_validation)
    monkeypatch.setattr(ResolveParametersNode, "execute", delayed_execute)
    monkeypatch.setattr(ParameterSelector, "select_for_context", track_selected_source)

    store_writes_at_timeout: tuple[tuple[str, ArtifactRef | None], ...] | None = None
    try:
        result = _execute_workflow(context, registry, _workflow(timeout_s=1.0), state)
        assert started.is_set()
        assert result.report.nodes[0].status == "fail"
        assert ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF not in result.state.artifacts_index
        assert observed_shared == [None]
        assert prepare_cache_calls == []
        events = _trace_events(context, start_line=trace_start)
        bypasses = [event for event in events if event.get("event") == "NODE_CACHE_BYPASS"]
        assert len(bypasses) == 1
        assert bypasses[0]["metrics"]["reason_code"] == 7
        assert not any(
            event.get("event") in {"NODE_CACHE_HIT", "NODE_CACHE_STORE"} for event in events
        )
        assert cache_validation_calls == []
        assert not finished.is_set()
        store_writes_at_timeout = tuple(underlying_store_write_calls)
    finally:
        release.set()

    assert finished.wait(timeout=8)
    assert selected_source_values == [2.6], (
        f"source selection did not complete; context={worker_context_facts!r}; "
        f"prepared_read_count={len(prepared_reads)}; "
        f"worker_errors={[(type(exc).__module__, type(exc).__qualname__, str(exc)) for exc in worker_errors]!r}"
    )
    assert len(worker_outcomes) + len(worker_errors) == 1
    assert worker_outcomes == []
    assert len(worker_errors) == 1
    assert type(worker_errors[0]) is retry_module._AttemptWriteDeniedError
    assert worker_errors[0].code == "attempt_write_revoked"
    assert worker_errors[0].reason_code == "attempt_write_revoked"
    assert store_writes_at_timeout is not None
    assert tuple(underlying_store_write_calls) == store_writes_at_timeout
    assert len(prepared_reads) == 1
    assert close_calls == prepared_reads
    assert prepared_reads[0]._closed is True
    assert_one_resumed_terminal_lifecycle(context.run, expected_resumes=0)


@pytest.mark.skipif(
    sys.platform != "darwin", reason="requires the native Darwin spawn timeout route"
)
def test_darwin_spawn_timeout_recomputes_changed_skg_and_persists_profile_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A canonical spawn worker reads current SKG bytes and publishes a typed bundle."""
    from polisyos.scientist.orchestration.engine import retry as retry_module
    from polisyos.scientist.orchestration.engine.errors import NodeTimeoutError

    allowed_cleanup_exitcodes = {0, -signal.SIGTERM}

    db_path = tmp_path / "skg-spawn-source.duckdb"
    _seed_skg(db_path)
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", "cell-a")
    owner_scope = AccessScope.for_service(
        tenant_id="tenant-a",
        cell_id="cell-a",
        spiffe_id="spiffe://polisyos.test/cell/cell-a/svc/skg-prepared-read-cache",
    )
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        graph_ref = persist_causal_graph_model(
            _ensure_ir_artifact_store(store),
            CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[]),
        )
        profile_ref = persist_cross_graph_evidence_profile(
            _ensure_ir_artifact_store(store),
            CrossGraphEvidenceProfile(
                summary=CrossGraphEvidenceSummary(status="ok", total_needs=0),
                notes=["spawn-worker-profile"],
            ),
        )
    state = ExperimentState(
        run_id="R_skg_spawn_timeout_lifetime",
        artifacts_index={
            ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref,
            ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF: profile_ref,
        },
        params={
            "target_context": {"context_id": "us-2025", "countries": ["US"]},
            "required_parameters": ["fiscal_multiplier"],
            "domain": "fiscal",
            "skg_db_path": str(db_path),
        },
    )
    warmup_input = state.model_copy(update={"run_id": f"{state.run_id}_warmup"})
    with _access_scope_context(owner_scope):
        warmup_context, warmup_registry = _build_run_context(
            store,
            warmup_input.run_id,
            tenant_id="tenant-a",
            cell_id="cell-a",
            selected_registry_profile=True,
        )
    warmup = _execute_workflow(warmup_context, warmup_registry, _workflow(), warmup_input)
    assert warmup.report.status == "ok"
    assert _resolved_value(store, warmup.state) == 1.4
    warmup_store_event = next(
        event for event in _trace_events(warmup_context) if event.get("event") == "NODE_CACHE_STORE"
    )
    source_bound_entry_ref = ArtifactRef.model_validate(warmup_store_event["refs"]["outputs"][0])
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        source_bound_entry = NodeCacheEntry.model_validate(
            from_canonical_bytes(store.get_bytes(source_bound_entry_ref))
        )
        prior_cache = NodeResultCache(store, run_id=warmup_input.run_id)
        assert prior_cache.load_entry(source_bound_entry_ref)
        prior_outcome = prior_cache.get(source_bound_entry.idempotency_key)
        assert prior_outcome is not None
        assert _resolved_value(store, prior_outcome.state) == 1.4
    assert_one_resumed_terminal_lifecycle(warmup_context.run, expected_resumes=0)

    # Owner admission is tested on a genuine paused owner before any node effects.
    # It does not grant replay permission for the completed warmup workflow.
    probe_run_id = f"{state.run_id}_owner_probe"
    with _access_scope_context(owner_scope):
        probe_context, _ = _build_run_context(
            store,
            probe_run_id,
            tenant_id="tenant-a",
            cell_id="cell-a",
            selected_registry_profile=True,
        )
    probe_context.run.suspend_for_resume()
    assert probe_context.run.trace_path is not None
    owner_trace = probe_context.run.trace_path
    trace_before_rejected_resume = owner_trace.read_bytes()
    with (
        _access_scope_context(owner_scope),
        pytest.raises(ValueError, match="run_resume_owner_inputs_mismatch"),
    ):
        _build_run_context(
            store, probe_run_id, tenant_id="tenant-b", cell_id="cell-a", resume_from=probe_context
        )
    assert owner_trace.read_bytes() == trace_before_rejected_resume
    changed_scope = AccessScope.for_service(
        tenant_id="tenant-a",
        cell_id="cell-a",
        spiffe_id="spiffe://polisyos.test/cell/cell-a/svc/other-service",
    )
    with (
        _access_scope_context(changed_scope),
        pytest.raises(ValueError, match="run_resume_owner_inputs_mismatch"),
    ):
        _build_run_context(
            store, probe_run_id, tenant_id="tenant-a", cell_id="cell-a", resume_from=probe_context
        )
    assert owner_trace.read_bytes() == trace_before_rejected_resume
    with _access_scope_context(owner_scope):
        probe_context, _ = _build_run_context(
            store, probe_run_id, tenant_id="tenant-a", cell_id="cell-a", resume_from=probe_context
        )
        probe_context.run.finalize()
    assert_one_resumed_terminal_lifecycle(probe_context.run, expected_resumes=1)

    # Cache-key/origin attacks remain in the same-run planned alias controls above.
    # The native worker is a new logical invocation with a real, initially empty result inlet.
    with _access_scope_context(owner_scope):
        context, registry = _build_run_context(
            store,
            state.run_id,
            tenant_id="tenant-a",
            cell_id="cell-a",
            selected_registry_profile=True,
        )
    assert ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF not in state.artifacts_index
    # Preserve the 1s negative result separately; this positive run tests the same
    # native spawn consumer with an explicit, larger test-only observation budget.
    _set_skg_value(db_path, 2.6)
    selected_read = SKGQuery.prepare_read(db_path=db_path, index_dir=tmp_path)
    try:
        with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
            selected_snapshot_ref = retain_prepared_skg_read(store, selected_read)
    finally:
        selected_read.close()
    assert selected_snapshot_ref.manifest_profile_sha256 is not None
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        selected_snapshot = load_retained_skg_snapshot(store, selected_snapshot_ref)
    replay_state = state.model_copy(update={"inputs": {SNAPSHOT_INPUT_KEY: selected_snapshot_ref}})
    _set_skg_value(db_path, 9.75)
    live_read = SKGQuery.prepare_read(db_path=db_path, index_dir=tmp_path)
    try:
        assert live_read.query.query_parameters("fiscal_multiplier")[0].parameter.value == 9.75
    finally:
        live_read.close()
    trace_start = _trace_event_count(context)
    worker_closes: list[dict[str, object]] = []
    original_close_worker = retry_module._close_worker_process

    def observe_worker_close(process) -> None:
        facts = {
            "pid": process.pid,
            "alive_before_close": process.is_alive(),
            "exitcode_before_close": process.exitcode,
        }
        original_close_worker(process)
        facts["closed_after"] = process._closed
        worker_closes.append(facts)

    monkeypatch.setattr(retry_module, "_close_worker_process", observe_worker_close)
    result = _execute_workflow(context, registry, _workflow(timeout_s=30.0), replay_state)

    assert result.report.nodes[0].status == "ok"
    assert _resolved_value(store, result.state) == 2.6
    assert result.state.inputs[SNAPSHOT_INPUT_KEY] == selected_snapshot_ref
    events = _trace_events(context, start_line=trace_start)
    bypasses = [event for event in events if event.get("event") == "NODE_CACHE_BYPASS"]
    assert len(bypasses) == 1
    assert bypasses[0]["metrics"]["reason_code"] == 7
    assert not any(event.get("event") in {"NODE_CACHE_HIT", "NODE_CACHE_STORE"} for event in events)
    assert len(worker_closes) == 1
    assert worker_closes[0]["pid"] not in {None, os.getpid()}
    assert worker_closes[0]["alive_before_close"] is False
    assert worker_closes[0]["exitcode_before_close"] in allowed_cleanup_exitcodes
    assert worker_closes[0]["closed_after"] is True

    assert context.run.trace_path is not None
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        bundle_ref = result.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
        bundle = load_context_adaptive_parameter_bundle(
            _ensure_ir_artifact_store(store), bundle_ref
        )
        bundle_manifest = store.get_manifest(bundle_ref)
        selected_graph_ref = profile_bound_ref(_ensure_ir_artifact_store(store), graph_ref)
        selected_profile_ref = profile_bound_ref(_ensure_ir_artifact_store(store), profile_ref)
        assert isinstance(bundle, ContextAdaptiveParameterBundleV12)
        assert bundle.schema_version == "1.2"
        assert bundle.parameters["fiscal_multiplier"].value == 2.6
        assert bundle.skg_version_id == 7
        assert bundle.selected_skg_source.descriptor_ref == selected_snapshot_ref
        assert bundle.selected_skg_source.source_sha256 == selected_snapshot.source_sha256
        assert bundle.selected_skg_source.source_version_id == selected_snapshot.source_version_id
        assert bundle.skg_snapshot_ref == selected_snapshot.source_reference
        assert bundle.selected_cross_graph_profile_ref == selected_profile_ref
        assert load_cross_graph_evidence_profile(
            _ensure_ir_artifact_store(store), selected_profile_ref
        ).notes == ["spawn-worker-profile"]
        assert bundle_manifest.artifact_schema is not None
        assert bundle_manifest.artifact_schema.name == "ir.context_adaptive_parameter_bundle"
        assert bundle_manifest.artifact_schema.version == "1.2"
        expected_inputs = [
            input_ref_from_artifact_ref(selected_graph_ref, role="causal_graph"),
            input_ref_from_artifact_ref(
                selected_profile_ref,
                role="cross_graph_evidence_profile",
            ),
            input_ref_from_artifact_ref(
                selected_snapshot_ref,
                role="skg_source_snapshot",
            ),
        ]
        assert bundle_manifest.inputs == expected_inputs
        inputs_by_role = {item.role: item for item in bundle_manifest.inputs}
        assert str(inputs_by_role["causal_graph"].artifact_id) == str(
            selected_graph_ref.artifact_id
        )
        assert (
            inputs_by_role["causal_graph"].manifest_profile_sha256
            == selected_graph_ref.manifest_profile_sha256
        )
        assert str(inputs_by_role["cross_graph_evidence_profile"].artifact_id) == str(
            selected_profile_ref.artifact_id
        )
        assert (
            inputs_by_role["cross_graph_evidence_profile"].manifest_profile_sha256
            == selected_profile_ref.manifest_profile_sha256
        )
        assert str(inputs_by_role["skg_source_snapshot"].artifact_id) == str(
            selected_snapshot_ref.artifact_id
        )
        assert (
            inputs_by_role["skg_source_snapshot"].manifest_profile_sha256
            == selected_snapshot_ref.manifest_profile_sha256
        )

    race_run_id = "R_skg_spawn_snapshot_race"
    with _access_scope_context(owner_scope):
        race_context, race_registry = _build_run_context(
            store,
            race_run_id,
            tenant_id="tenant-a",
            cell_id="cell-a",
        )
    assert race_context.run.run_manifest.run_id == race_run_id
    race_state = replay_state.model_copy(update={"run_id": race_run_id})
    assert race_context.run.trace_path is not None
    race_materialization = (
        race_context.run.trace_path.parent
        / "skg-snapshots"
        / f"{selected_snapshot.source_sha256}.duckdb"
    )
    replacement_path = tmp_path / "skg-spawn-replacement.duckdb"
    _seed_skg(replacement_path)
    _set_skg_value(replacement_path, 4.4)
    spawn_context = retry_module.mp.get_context("spawn")
    real_mp = retry_module.mp
    mutations: list[tuple[str, str]] = []
    raced_processes: list[Any] = []

    class MutatingStartProcess:
        """Change only the bound local copy immediately before its real child starts."""

        def __init__(self, process) -> None:
            self._process = process

        def start(self) -> None:
            assert race_materialization.is_file()
            before = _file_sha256(race_materialization)
            assert before == selected_snapshot.source_sha256
            os.replace(replacement_path, race_materialization)
            after = _file_sha256(race_materialization)
            mutations.append((before, after))
            self._process.start()

        def __getattr__(self, name: str) -> Any:
            return getattr(self._process, name)

    def process_factory(*args, **kwargs):
        process = spawn_context.Process(*args, **kwargs)
        if kwargs.get("target") is retry_module._typed_node_timeout_worker:
            process = MutatingStartProcess(process)
            raced_processes.append(process)
        return process

    class DynamicOnlySpawnContextProxy:
        def __getattr__(self, name: str) -> Any:
            if name == "Process":
                return process_factory
            return getattr(spawn_context, name)

    with pytest.raises(NodeTimeoutError) as dynamic_only_refusal:
        retry_module._process_factory(DynamicOnlySpawnContextProxy())
    assert dynamic_only_refusal.value.code == "node.timeout_worker_unsupported"
    assert (
        dynamic_only_refusal.value.details["reason"]
        == "process_context_process_factory_unavailable"
    )

    class SpawnContextProxy:
        Process: Any

        def __init__(self) -> None:
            self.Process = process_factory

        def __getattr__(self, name: str) -> Any:
            return getattr(spawn_context, name)

    context_proxy = SpawnContextProxy()
    monkeypatch.setattr(
        retry_module,
        "mp",
        SimpleNamespace(
            get_all_start_methods=real_mp.get_all_start_methods,
            get_context=lambda _method: context_proxy,
        ),
    )
    race_worker_closes: list[dict[str, object]] = []

    def observe_race_worker_close(process) -> None:
        facts = {
            "pid": process.pid,
            "exitcode_before_close": process.exitcode,
            "alive_before_close": process.is_alive(),
        }
        original_close_worker(process)
        facts["closed_after"] = process._closed
        race_worker_closes.append(facts)

    monkeypatch.setattr(retry_module, "_close_worker_process", observe_race_worker_close)
    race_result = _execute_workflow(
        race_context,
        race_registry,
        _workflow(timeout_s=30.0),
        race_state,
    )
    assert len(mutations) == 1
    before, after = mutations[0]
    assert before == selected_snapshot.source_sha256
    assert after != selected_snapshot.source_sha256
    assert race_result.report.nodes[0].status == "fail"
    race_error = race_result.report.nodes[0].error
    assert race_error is not None
    assert race_error.code == "node.retry_exhausted"
    assert race_error.message == "Node resolve: all 0 retries exhausted"
    assert race_result.state.inputs[SNAPSHOT_INPUT_KEY] == selected_snapshot_ref
    assert ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF not in race_result.state.artifacts_index
    dead_letter_events = [
        event for event in _trace_events(race_context) if event.get("event") == "NODE_DEAD_LETTER"
    ]
    assert len(dead_letter_events) == 1
    assert dead_letter_events[0]["metrics"]["attempts"] == 1
    dead_letter_refs = dead_letter_events[0]["refs"]["outputs"]
    assert len(dead_letter_refs) == 1
    dead_letter_ref = ArtifactRef.model_validate(dead_letter_refs[0])
    assert dead_letter_ref.kind == "scientist.dead_letter"
    from polisyos.scientist.replay import load_dead_letter

    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        dead_letter = load_dead_letter(store, dead_letter_ref.artifact_id)
    assert dead_letter.artifact_ref.artifact_id == dead_letter_ref.artifact_id
    assert dead_letter.artifact_ref.kind == "scientist.dead_letter"
    assert dead_letter.run_id == race_context.run.run_manifest.run_id
    assert dead_letter.alias == "resolve"
    assert dead_letter.node_id == _RESOLVE_NODE_ID
    assert dead_letter.attempts == 1
    assert (
        "RetainedSKGSnapshotError: retained_skg_materialization_digest" in dead_letter.error_message
    )
    assert len(raced_processes) == 1
    assert len(race_worker_closes) == 1
    assert race_worker_closes[0]["pid"] not in {None, os.getpid()}
    assert race_worker_closes[0]["exitcode_before_close"] in allowed_cleanup_exitcodes
    assert race_worker_closes[0]["alive_before_close"] is False
    assert race_worker_closes[0]["closed_after"] is True
    assert _file_sha256(race_materialization) == after
    assert_one_resumed_terminal_lifecycle(context.run, expected_resumes=0)


def test_spawn_timeout_refuses_live_prepared_read_before_child_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The spawn wire rejects a live DuckDB handle before creating a child process."""
    from polisyos.scientist.orchestration.engine import retry as retry_module
    from polisyos.scientist.orchestration.engine.errors import NodeTimeoutError

    db_path = tmp_path / "skg-spawn-owned-read.duckdb"
    _seed_skg(db_path)
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", "cell-a")
    run_id = "R_skg_spawn_owned_read"
    owner_scope = AccessScope.for_service(
        tenant_id="tenant-a",
        cell_id="cell-a",
        spiffe_id="spiffe://polisyos.test/cell/cell-a/svc/skg-prepared-read-cache",
    )
    with _access_scope_context(owner_scope):
        context, _registry = _build_run_context(
            store,
            run_id,
            tenant_id="tenant-a",
            cell_id="cell-a",
        )
    assert context.run.tenant_id == "tenant-a"
    assert context.run.cell_id == "cell-a"
    assert context.run.access_scope == owner_scope
    prepared_read = SKGQuery.prepare_read(db_path=db_path, index_dir=tmp_path)
    context = replace(context, prepared_skg_read=prepared_read)
    spawn_context = retry_module.mp.get_context("spawn")

    process_constructions: list[object] = []

    def process_factory(*args, **kwargs):
        process_constructions.append((args, kwargs))
        return spawn_context.Process(*args, **kwargs)

    context_probe = SimpleNamespace(
        Process=process_factory,
        Value=spawn_context.Value,
    )
    monkeypatch.setattr(retry_module, "_timeout_worker_start_method", lambda: "spawn")
    monkeypatch.setattr(
        retry_module,
        "mp",
        SimpleNamespace(get_context=lambda _method: context_probe),
    )
    try:
        with (
            tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"),
            pytest.raises(NodeTimeoutError) as caught,
        ):
            retry_module.execute_with_retry_sync(
                ResolveParametersNode(),
                context,
                ExperimentState(run_id=run_id),
                retry_policy=retry_module.RetryPolicy(),
                timeout_s=5.0,
                alias="resolve",
                dispatch_params={},
            )
        assert caught.value.code == "node.timeout_worker_unsupported"
        assert caught.value.details["reason"] == "timeout_worker_optional_context_port_unsupported"
        assert process_constructions == []
    finally:
        prepared_read.close()
    assert prepared_read._closed is True


def test_duckdb_cache_preparation_failure_bypasses_cache_and_runs_node(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A DuckDB failure in preparation bypasses caching before normal node execution."""
    db_path = tmp_path / "skg-with-unselected-failure.duckdb"
    _seed_skg(db_path)
    with duckdb.connect(str(db_path)) as writer:
        writer.execute(
            "CREATE VIEW ac_unselected_failure AS "
            "SELECT error('unselected academic view was evaluated') AS value"
        )
    prepared_read = SKGQuery.prepare_read(db_path=db_path, index_dir=tmp_path)
    try:
        selected = prepared_read.query.query_parameters("fiscal_multiplier")
        assert selected[0].parameter.value == 1.4
    finally:
        prepared_read.close()

    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", "cell-a")
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        graph_ref = persist_causal_graph_model(
            _ensure_ir_artifact_store(store),
            CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[]),
        )
    state = ExperimentState(
        run_id="R_prepared_read_duckdb_bypass",
        artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref},
        params={
            "target_context": {
                "context_id": "us-2025",
                "countries": ["US"],
                "publication_year": 2025,
            },
            "required_parameters": ["fiscal_multiplier"],
            "domain": "fiscal",
            "skg_db_path": str(db_path),
        },
    )

    def fail_during_preparation(_self, _context, _state):
        connection = duckdb.connect(str(db_path), read_only=True)
        try:
            connection.execute("SELECT * FROM ac_unselected_failure").fetchall()
        finally:
            connection.close()

    monkeypatch.setattr(ResolveParametersNode, "prepare_cache_input", fail_during_preparation)
    context, registry = _build_run_context(
        store, state.run_id, tenant_id="tenant-a", cell_id="cell-a"
    )
    result = _execute_workflow(context, registry, _workflow(), state)

    assert result.report.status == "ok"
    assert _resolved_value(store, result.state) == 1.4
    events = _trace_events(context)
    bypasses = [event for event in events if event.get("event") == "NODE_CACHE_BYPASS"]
    assert len(bypasses) == 1
    assert bypasses[0]["metrics"]["reason_code"] == 5
    assert not any(event.get("event") == "NODE_CACHE_STORE" for event in events)


def test_workflow_executor_bypasses_cache_if_source_generation_changes_during_miss(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mid-invocation source generation change cannot produce a cache entry."""
    from polisyos.scientist.orchestration.engine import executor as executor_module
    from polisyos.scientist.orchestration.engine.idempotency import (
        compute_idempotency_key as real_compute_idempotency_key,
    )

    db_path = tmp_path / "skg-between-key-and-query.duckdb"
    _seed_skg(db_path)
    store = FileSystemCAS(tmp_path / "cas")
    graph_ref = persist_causal_graph_model(
        _ensure_ir_artifact_store(store),
        CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[]),
    )
    initial_state = ExperimentState(
        run_id="R_skg_between_key_and_query",
        artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref},
        params={
            "target_context": {
                "context_id": "us-2025",
                "countries": ["US"],
                "publication_year": 2025,
            },
            "required_parameters": ["fiscal_multiplier"],
            "domain": "fiscal",
            "skg_db_path": str(db_path),
        },
    )

    def compute_then_change_generation(**kwargs: Any) -> str:
        key = real_compute_idempotency_key(**kwargs)
        before = db_path.stat()
        os.utime(db_path, ns=(before.st_atime_ns, before.st_mtime_ns + 2_000_000_000))
        return key

    monkeypatch.setattr(
        executor_module,
        "compute_idempotency_key",
        compute_then_change_generation,
    )
    context, registry = _build_run_context(store, initial_state.run_id)
    result = WorkflowExecutor(context, registry).execute(_workflow(), initial_state)

    assert result.report.status == "ok"
    assert _resolved_value(store, result.state) == 1.4
    events = _trace_events(context)
    assert any(
        event.get("event") == "NODE_CACHE_BYPASS"
        and event.get("metrics", {}).get("reason_code") == 5
        for event in events
    )
    assert not any(event.get("event") == "NODE_CACHE_STORE" for event in events)


def test_workflow_executor_rebinds_changed_live_source_during_cache_miss(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A live same-path replacement is read fresh and never stored under the old key."""
    from polisyos.scientist.orchestration.engine import executor as executor_module
    from polisyos.scientist.orchestration.engine.idempotency import (
        compute_idempotency_key as real_compute_idempotency_key,
    )

    db_path = tmp_path / "skg-between-key-and-query.duckdb"
    _seed_skg(db_path)
    store = FileSystemCAS(tmp_path / "cas")
    graph_ref = persist_causal_graph_model(
        _ensure_ir_artifact_store(store),
        CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[]),
    )
    initial_state = ExperimentState(
        run_id="R_skg_between_key_and_query_rebind",
        artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref},
        params={
            "target_context": {
                "context_id": "us-2025",
                "countries": ["US"],
                "publication_year": 2025,
            },
            "required_parameters": ["fiscal_multiplier"],
            "domain": "fiscal",
            "skg_db_path": str(db_path),
        },
    )

    def compute_then_replace_selected_row(**kwargs: Any) -> str:
        key = real_compute_idempotency_key(**kwargs)
        replacement = tmp_path / "skg-between-key-and-query-replacement.duckdb"
        _seed_skg(replacement)
        _set_skg_value(replacement, 2.6)
        os.replace(replacement, db_path)
        return key

    monkeypatch.setattr(
        executor_module,
        "compute_idempotency_key",
        compute_then_replace_selected_row,
    )
    context, registry = _build_run_context(store, initial_state.run_id)
    result = WorkflowExecutor(context, registry).execute(_workflow(), initial_state)

    assert result.report.status == "ok"
    assert _resolved_value(store, result.state) == 2.6
    bundle_ref = result.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
    bundle = load_context_adaptive_parameter_bundle(_ensure_ir_artifact_store(store), bundle_ref)
    assert bundle.selected_skg_source is not None
    assert bundle.selected_skg_source.source_sha256 == _file_sha256(db_path)
    events = _trace_events(context)
    assert any(
        event.get("event") == "NODE_CACHE_BYPASS"
        and event.get("metrics", {}).get("reason_code") == 5
        for event in events
    )
    assert not any(event.get("event") == "NODE_CACHE_STORE" for event in events)


def test_build_literature_prior_recomputes_existing_output_from_changed_prepared_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An old prior ref cannot bypass a newly prepared source read."""
    db_path = tmp_path / "literature-prior-source.duckdb"
    _seed_skg(db_path)
    store = FileSystemCAS(tmp_path / "literature-prior-cas")
    old_ref = persist_literature_causal_prior(
        _ensure_ir_artifact_store(store),
        LiteratureCausalPrior(metadata={"legacy_source": "unbound"}),
    )
    state = ExperimentState(
        run_id="R_existing_literature_prior",
        artifacts_index={ARTIFACT_LITERATURE_PRIOR_REF: old_ref},
        params={
            "causal_variables": ["fiscal_multiplier"],
            "skg_db_path": str(db_path),
            "environment_audit_enabled": False,
        },
    )
    context, _ = _build_run_context(store, state.run_id)
    consumed_values: list[float] = []

    def rebuild_from_prepared_source(_request, params, *, prepared_read):
        del params
        candidates = prepared_read.query.query_parameters("fiscal_multiplier")
        value = float(candidates[0].parameter.value)
        consumed_values.append(value)
        prior = LiteratureCausalPrior(metadata={"selected_parameter_value": value})
        graph = CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["fiscal_multiplier"],
            edges=[],
        )
        return {
            "literature_prior": prior,
            "literature_prior_graph": graph,
            "warnings": [],
        }

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.build_literature_prior.BuildLiteraturePrior.pure_step",
        rebuild_from_prepared_source,
    )

    for expected_value in (1.4, 2.6):
        if expected_value != 1.4:
            _set_skg_value(db_path, expected_value)
        prepared_read = SKGQuery.prepare_read(db_path=db_path, index_dir=tmp_path)
        try:
            prepared_context = replace(context, prepared_skg_read=prepared_read)
            outcome = BuildLiteraturePriorNode().execute(prepared_context, state)
        finally:
            prepared_read.close()
        assert outcome.status == "ok"
        current_ref = outcome.state.artifacts_index[ARTIFACT_LITERATURE_PRIOR_REF]
        assert current_ref != old_ref
        state = outcome.state
        old_ref = current_ref

    assert consumed_values == [1.4, 2.6]


def test_resolve_parameters_recomputes_existing_bundle_from_changed_prepared_source(
    tmp_path: Path,
) -> None:
    """A persisted parameter bundle cannot bypass the current owner-prepared read."""
    db_path = tmp_path / "resolved-parameters-source.duckdb"
    _seed_skg(db_path)
    store = FileSystemCAS(tmp_path / "resolved-parameters-cas").for_tenant("tenant-a", "cell-a")
    target_context = {
        "context_id": "us-2025",
        "countries": ["US"],
        "publication_year": 2025,
    }
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        graph_ref = persist_causal_graph_model(
            _ensure_ir_artifact_store(store),
            CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[]),
        )
        graph_ref = profile_bound_ref(_ensure_ir_artifact_store(store), graph_ref)
        old_bundle_ref = persist_context_adaptive_parameter_bundle_v1_1(
            _ensure_ir_artifact_store(store),
            ContextAdaptiveParameterBundleV11(
                target_context=ContextProfile.model_validate(target_context),
                simulation_domain="fiscal",
                selected_cross_graph_profile_ref=None,
            ),
            inputs=[
                input_ref_from_artifact_ref(
                    ArtifactRef.model_validate(graph_ref.model_dump(mode="json")),
                    role="causal_graph",
                )
            ],
        )
    state = ExperimentState(
        run_id="R_existing_resolved_parameters",
        artifacts_index={
            ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref,
            ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF: old_bundle_ref,
        },
        params={
            "target_context": target_context,
            "required_parameters": ["fiscal_multiplier"],
            "domain": "fiscal",
            "skg_db_path": str(db_path),
        },
    )
    context, _ = _build_run_context(store, state.run_id, tenant_id="tenant-a", cell_id="cell-a")

    for expected_value in (1.4, 2.6):
        if expected_value != 1.4:
            _set_skg_value(db_path, expected_value)
        prepared_read = SKGQuery.prepare_read(db_path=db_path, index_dir=tmp_path)
        try:
            prepared_context = replace(context, prepared_skg_read=prepared_read)
            with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
                outcome = ResolveParametersNode().execute(prepared_context, state)
        finally:
            prepared_read.close()
        assert outcome.status == "ok"
        current_ref = outcome.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
        assert current_ref != old_bundle_ref
        assert _resolved_value(store, outcome.state) == expected_value
        state = outcome.state
        old_bundle_ref = current_ref


def test_cross_graph_recomputes_existing_profile_from_changed_prepared_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An existing profile is recompiled against the current prepared academic read."""
    db_path = tmp_path / "cross-graph-source.duckdb"
    _seed_skg(db_path)
    store = FileSystemCAS(tmp_path / "cross-graph-cas")
    run_id = "R_existing_cross_graph_profile"
    seed_state = ExperimentState(run_id=run_id)
    context, _ = _build_run_context(store, run_id)
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        trinity_ref = _persist_trinity_bundle(context, _trinity_bundle(), state=seed_state)
        trinity_manifest = store.get_manifest(trinity_ref)
        assert trinity_manifest.kind == TrinityBundle.ARTIFACT_KIND
        assert trinity_manifest.media_type == TrinityBundle.ARTIFACT_MEDIA_TYPE
        assert trinity_manifest.artifact_schema == SchemaInfo(
            name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
            version=TrinityBundle.ARTIFACT_SCHEMA_VERSION,
        )
        old_ref = persist_cross_graph_evidence_profile(
            _ensure_ir_artifact_store(store),
            CrossGraphEvidenceProfile(
                summary=CrossGraphEvidenceSummary(status="ok", total_needs=0),
                notes=["legacy-source-unbound"],
            ),
        )
    state = ExperimentState(
        run_id=run_id,
        inputs={INPUT_TRINITY_BUNDLE_REF: trinity_ref},
        artifacts_index={ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF: old_ref},
        params={
            "cross_graph_evidence_config": {
                "enabled": True,
                "academic_db_path": str(db_path),
            }
        },
    )
    consumed_values: list[float] = []

    def compile_from_prepared_source(_self, _bundle, *, prepared_skg_read=None, **_kwargs):
        assert prepared_skg_read is not None
        candidates = prepared_skg_read.query.query_parameters("fiscal_multiplier")
        value = float(candidates[0].parameter.value)
        consumed_values.append(value)
        return CrossGraphEvidenceProfile(
            summary=CrossGraphEvidenceSummary(status="ok", total_needs=0),
            notes=[f"prepared-source-value:{value}"],
        )

    monkeypatch.setattr(
        "polisyos.scientist.cross_graph.compiler.CrossGraphEvidenceCompiler.compile",
        compile_from_prepared_source,
    )

    for expected_value in (1.4, 2.6):
        if expected_value != 1.4:
            _set_skg_value(db_path, expected_value)
        prepared_read = CompileCrossGraphEvidenceNode().prepare_cache_input(context, state)
        assert prepared_read is not None
        try:
            prepared_context = replace(context, prepared_skg_read=prepared_read)
            outcome = CompileCrossGraphEvidenceNode().execute(prepared_context, state)
        finally:
            prepared_read.close()
        assert outcome.status == "ok"
        current_ref = outcome.state.artifacts_index[ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF]
        assert current_ref != old_ref
        profile = load_cross_graph_evidence_profile(_ensure_ir_artifact_store(store), current_ref)
        assert profile.notes == [f"prepared-source-value:{expected_value}"]
        profile_manifest = store.get_manifest(current_ref)
        assert any(
            source.role == "trinity_bundle"
            and str(source.artifact_id) == str(trinity_ref.artifact_id)
            for source in profile_manifest.inputs
        )
        state = outcome.state
        old_ref = current_ref

    assert consumed_values == [1.4, 2.6]


def test_removed_cache_key_binding_is_stopped_by_origin_read_set_check(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Removing the key binding while retaining origin markers cannot serve stale output."""
    from polisyos.scientist.orchestration.engine import executor as executor_module
    from polisyos.scientist.orchestration.engine.idempotency import (
        compute_idempotency_key as real_compute_idempotency_key,
    )

    db_path = tmp_path / "skg.duckdb"
    _seed_skg(db_path)
    store = FileSystemCAS(tmp_path / "cas")
    graph_ref = persist_causal_graph_model(
        _ensure_ir_artifact_store(store),
        CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[]),
    )
    initial_state = ExperimentState(
        run_id="R_skg_removed_read_binding",
        artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref},
        params={
            "target_context": {
                "context_id": "us-2025",
                "countries": ["US"],
                "publication_year": 2025,
            },
            "required_parameters": ["fiscal_multiplier"],
            "domain": "fiscal",
            "skg_db_path": str(db_path),
        },
    )

    def original_binding_free_key(**kwargs):
        params = {
            key: value
            for key, value in dict(kwargs.get("bind_params") or {}).items()
            if key != "prepared_skg_read"
        }
        return real_compute_idempotency_key(**{**kwargs, "bind_params": params})

    monkeypatch.setattr(executor_module, "compute_idempotency_key", original_binding_free_key)
    # Remove the independent request-matcher shield as well, so this control
    # reaches the original read-set reconciliation rather than an earlier refusal.
    monkeypatch.setattr(ResolveParametersNode, "validate_cache_hit", lambda *_args: True)

    ctx_first, registry_first = _build_run_context(
        store, initial_state.run_id, selected_registry_profile=True
    )
    initial_state = _seed_input_bundle(ctx_first, initial_state)
    workflow = _planned_skg_workflow(
        registry_first,
        initial_state,
        [("changed", ((str(db_path), 3.1, False),))],
    )
    second = _execute_workflow(ctx_first, registry_first, workflow, initial_state)
    cold_events = _phase_events(ctx_first, "cold")
    cache_store_event = next(
        event for event in cold_events if event.get("event") == "NODE_CACHE_STORE"
    )
    cache_entry_ref = ArtifactRef.model_validate(cache_store_event["refs"]["outputs"][0])
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        cache_entry = NodeCacheEntry.model_validate(
            from_canonical_bytes(store.get_bytes(cache_entry_ref.artifact_id))
        )
        first_cache = NodeResultCache(store, run_id=initial_state.run_id)
        assert first_cache.load_entry(cache_entry_ref)
        first_outcome = first_cache.get(cache_entry.idempotency_key)
    assert first_outcome is not None
    assert _resolved_value(store, first_outcome.state) == 1.4

    assert second.report.status == "ok", second.report.model_dump_json(indent=2)
    second_value = _resolved_value(store, second.state)
    assert second_value == 3.1
    second_events = _phase_events(ctx_first, "changed")
    second_cache_hits = [event for event in second_events if event.get("event") == "NODE_CACHE_HIT"]
    assert not second_cache_hits
    assert any(
        event.get("event") == "NODE_CACHE_BYPASS"
        and event.get("metrics", {}).get("reason_code") == 5
        for event in second_events
    )
    assert_one_resumed_terminal_lifecycle(ctx_first.run, expected_resumes=0)

    observation_root = os.environ.get("E02_B_PROPERTY_REMOVAL_OBSERVATION")
    if observation_root:
        observation_dir = Path(observation_root)
        observation_dir.mkdir(parents=True, exist_ok=True)
        observation = {
            "observation_schema": "e02.prepared_b.removal_observation.v1",
            "case_id": "b61-same-path-source-replacement",
            "first_persisted_cache_value": _resolved_value(store, first_outcome.state),
            "value_after_same_path_source_replacement": second_value,
            "cache_hits_after_replacement": len(second_cache_hits),
            "resumed_workflow_status": second.report.status,
            "replacement_readset_guard_completed": True,
            "terminal_lifecycle_completed": True,
        }
        (observation_dir / "b61-same-path-source-replacement.json").write_text(
            json.dumps(observation, sort_keys=True) + "\n", encoding="utf-8"
        )
