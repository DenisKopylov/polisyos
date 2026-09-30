from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import replace
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import Any

import duckdb
import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import ComponentId
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.core.security.tenant_context import tenant_scope
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
    ContextAdaptiveParameterBundle,
    load_context_adaptive_parameter_bundle,
    persist_context_adaptive_parameter_bundle,
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
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF,
    ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
    ARTIFACT_LITERATURE_PRIOR_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
    INPUT_TRINITY_BUNDLE_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.idempotency import (
    NodeCacheEntry,
    NodeResultCache,
    compute_idempotency_key,
)
from polisyos.scientist.orchestration.engine.protocol import NodeEvent, NodeOutcome
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
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


def _set_unrelated_value(path: Path, value: int) -> None:
    connection = duckdb.connect(str(path))
    try:
        connection.execute("UPDATE unrelated_rows SET value = ?", [value])
    finally:
        connection.close()


def _build_run_context(store: FileSystemCAS, run_id: str) -> tuple[ExecutionContext, NodeRegistry]:
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        registry_bundle = build_default_registry_bundle(store)
        run = RunContext.start(
            store=store,
            registry_bundle=registry_bundle.bundle_ref,
            run_id=run_id,
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
        bundle = load_context_adaptive_parameter_bundle(store, bundle_ref)
    return float(bundle.parameters["fiscal_multiplier"].value)


def _execute_workflow(
    context: ExecutionContext,
    registry: NodeRegistry,
    workflow: WorkflowSpec,
    state: ExperimentState,
):
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        return WorkflowExecutor(context, registry).execute(workflow, state)


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
            ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: artifact_ref_factory(
                kind="ir.causal_graph_model"
            )
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
    candidate = SimpleNamespace(
        as_search_payload=lambda: {"candidate_id": "candidate-prepared-read"},
        trinity_bundle=object(),
        candidate_id="candidate-prepared-read",
        candidate_hash=lambda: "candidate-hash",
    )
    state = minimal_state.model_copy(deep=True)
    observed: list[object | None] = []

    def capture_prepared_read(
        ctx: ExecutionContext,
        _state: ExperimentState,
        *,
        candidate_payload: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, object]:
        del candidate_payload, context
        observed.append(ctx.prepared_skg_read)
        return {"status": "ok", "feasible": True, "objective_value": 1.0}

    def run_search(_adapter, _candidate, **kwargs):
        kwargs["stage_b_evaluator"](_candidate.as_search_payload(), {})
        return SimpleNamespace(model_dump=lambda mode="json": {"status": "ok"})

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
        lambda fallback, _search_result: fallback,
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


def test_workflow_executor_binds_source_transaction_and_emits_hit_receipt(tmp_path: Path) -> None:
    """The source-byte binding admits exact hits and rejects changed database bytes."""
    db_path = tmp_path / "skg.duckdb"
    _seed_skg(db_path)
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", "cell-a")
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        graph_ref = persist_causal_graph_model(
            store,
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
    workflow = _workflow()

    ctx_first, registry_first = _build_run_context(store, initial_state.run_id)
    first = _execute_workflow(ctx_first, registry_first, workflow, initial_state)
    first_value = _resolved_value(store, first.state)
    assert first.report.status == "ok"
    assert first_value == 1.4
    cache_store_event = next(
        event
        for event in _trace_events(ctx_first)
        if event.get("event") == "NODE_CACHE_STORE"
    )
    cache_entry_ref = ArtifactRef.model_validate(cache_store_event["refs"]["outputs"][0])
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        cache_entry = NodeCacheEntry.model_validate(
            from_canonical_bytes(store.get_bytes(cache_entry_ref.artifact_id))
        )
    assert cache_entry.outcome_payload is not None
    cached_events = [
        NodeEvent.model_validate(event)
        for event in cache_entry.outcome_payload.get("events", [])
    ]
    origin_events = [
        event
        for event in cached_events
        if event.code == "skg.prepared_connection_query"
    ]
    assert len(origin_events) == 1
    origin_attrs = origin_events[0].attrs
    assert origin_attrs["read_evidence_scope"] == "bound_connection_query_execution_only"
    assert origin_attrs["output_dependency"] == "not_established"
    query_fingerprints = json.loads(
        origin_attrs["connection_query_fingerprints_json"]
    )
    assert query_fingerprints

    ctx_hit, registry_hit = _build_run_context(store, initial_state.run_id)
    hit_trace_start = _trace_event_count(ctx_hit)
    hit = _execute_workflow(ctx_hit, registry_hit, workflow, initial_state)

    assert hit.report.status == "ok"
    assert _resolved_value(store, hit.state) == first_value
    hit_events = [
        event
        for event in _trace_events(ctx_hit, start_line=hit_trace_start)
        if event.get("event") == "NODE_CACHE_HIT"
    ]
    assert len(hit_events) == 1
    receipt_refs = [
        ref
        for ref in hit.report.nodes[0].artifacts
        if ref.kind == "scientist.skg_cache_read_receipt"
    ]
    assert len(receipt_refs) == 1
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        receipt = PreparedSKGReadReceipt.model_validate_json(
            store.get_bytes(receipt_refs[0].artifact_id)
        )
    assert receipt.authority_band == "candidate"
    assert receipt.source_snapshot_authenticity == "not_established"
    assert receipt.schema_version == "scientist.skg_cache_read_receipt.v3"
    assert receipt.read_evidence_scope == "bound_connection_query_execution_only"
    assert receipt.output_dependency == "not_established"
    assert receipt.current_source_snapshot_sha256 == receipt.original_source_snapshot_sha256
    assert receipt.source_binding_schema_version == "academic.skg_source_binding.v2"
    assert receipt.time_semantics == "read_transaction_opened_at"
    assert receipt.current_prepared_at >= receipt.original_prepared_at
    assert any(
        ref.kind == "ir.context_adaptive_parameter_bundle"
        for ref in receipt.original_output_refs
    )

    foreign_store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-b", "cell-a")
    with (
        tenant_scope(None, tenant_id="tenant-b", cell_id="cell-a"),
        pytest.raises(ArtifactOwnershipError),
    ):
        foreign_store.get_bytes(receipt_refs[0].artifact_id)

    _set_unrelated_value(db_path, 2)
    ctx_unrelated, registry_unrelated = _build_run_context(store, initial_state.run_id)
    unrelated_trace_start = _trace_event_count(ctx_unrelated)
    unrelated = _execute_workflow(
        ctx_unrelated,
        registry_unrelated,
        workflow,
        initial_state,
    )

    assert unrelated.report.status == "ok"
    assert _resolved_value(store, unrelated.state) == first_value
    unrelated_events = _trace_events(ctx_unrelated, start_line=unrelated_trace_start)
    assert not any(event.get("event") == "NODE_CACHE_HIT" for event in unrelated_events)
    assert sum(event.get("event") == "NODE_CACHE_STORE" for event in unrelated_events) == 1

    _set_skg_value(db_path, 2.6)
    ctx_changed, registry_changed = _build_run_context(store, initial_state.run_id)
    changed_trace_start = _trace_event_count(ctx_changed)
    changed = _execute_workflow(ctx_changed, registry_changed, workflow, unrelated.state)

    assert changed.report.status == "ok"
    assert _resolved_value(store, changed.state) == 2.6
    changed_events = _trace_events(ctx_changed, start_line=changed_trace_start)
    assert not any(event.get("event") == "NODE_CACHE_HIT" for event in changed_events)
    assert sum(event.get("event") == "NODE_CACHE_STORE" for event in changed_events) == 1


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
            store,
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

    first_context, first_registry = _build_run_context(store, state.run_id)
    first = _execute_workflow(first_context, first_registry, _workflow(), state)
    assert first.report.status == "ok"
    assert observed == [1]
    store_event = next(
        event
        for event in _trace_events(first_context)
        if event.get("event") == "NODE_CACHE_STORE"
    )
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

    hit_context, hit_registry = _build_run_context(store, state.run_id)
    hit = _execute_workflow(hit_context, hit_registry, _workflow(), state)
    assert hit.report.status == "ok"
    assert observed == [1]
    receipt_refs = [
        ref
        for ref in hit.report.nodes[0].artifacts
        if ref.kind == "scientist.skg_cache_read_receipt"
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
            store,
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
    context, registry = _build_run_context(store, state.run_id)

    with pytest.raises(duckdb.CatalogException):
        _execute_workflow(context, registry, _workflow(), state)

    assert len(prepared_reads) == 1
    assert close_calls == prepared_reads
    assert prepared_reads[0]._closed is True


def test_timed_prepared_read_bypasses_shared_handle_until_worker_finishes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A timed call skips a stale unbound cache row and uses its own read lifetime."""
    from polisyos.scientist.orchestration.engine import retry as retry_module

    db_path = tmp_path / "skg-timeout-lifetime.duckdb"
    _seed_skg(db_path)
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", "cell-a")
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        graph_ref = persist_causal_graph_model(
            store,
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
    context, registry = _build_run_context(store, state.run_id)
    warmup = _execute_workflow(context, registry, _workflow(), state)
    assert warmup.report.status == "ok"
    assert _resolved_value(store, warmup.state) == 1.4

    warmup_store_event = next(
        event
        for event in _trace_events(context)
        if event.get("event") == "NODE_CACHE_STORE"
    )
    source_bound_entry_ref = ArtifactRef.model_validate(
        warmup_store_event["refs"]["outputs"][0]
    )
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        source_bound_entry = NodeCacheEntry.model_validate(
            from_canonical_bytes(store.get_bytes(source_bound_entry_ref.artifact_id))
        )
        prior_cache = NodeResultCache(store, run_id=state.run_id)
        assert prior_cache.load_entry(source_bound_entry_ref)
        prior_outcome = prior_cache.get(source_bound_entry.idempotency_key)
        assert prior_outcome is not None
        unbound_key = compute_idempotency_key(
            spec=ResolveParametersNode().spec,
            state=state,
            bind_params={},
        )
        assert unbound_key != source_bound_entry.idempotency_key
        unbound_entry_ref = prior_cache.put(
            unbound_key,
            node_id=_RESOLVE_NODE_ID,
            outcome=prior_outcome,
        )
        stale_outcome = prior_cache.get(unbound_key)
        assert stale_outcome is not None
        assert _resolved_value(store, stale_outcome.state) == 1.4
    context.run.emit(
        "scientist.node.resolve",
        "NODE_CACHE_STORE",
        outputs=[unbound_entry_ref],
    )

    # A cache key that omits source bytes would now return the old 1.4 result.
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

    monkeypatch.setattr(retry_module, "_can_use_forked_timeout_worker", lambda: False)
    monkeypatch.setattr(SKGQuery, "prepare_read", staticmethod(track_prepare))
    monkeypatch.setattr(PreparedSKGRead, "close", track_close)
    monkeypatch.setattr(ResolveParametersNode, "prepare_cache_input", track_cache_prepare)
    monkeypatch.setattr(ResolveParametersNode, "validate_cache_hit", track_cache_validation)
    monkeypatch.setattr(ResolveParametersNode, "execute", delayed_execute)
    monkeypatch.setattr(ParameterSelector, "select_for_context", track_selected_source)

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
        assert not any(event.get("event") in {"NODE_CACHE_HIT", "NODE_CACHE_STORE"} for event in events)
        assert cache_validation_calls == []
        assert not finished.is_set()
    finally:
        release.set()

    assert finished.wait(timeout=8)
    assert selected_source_values == [2.6], (
        f"source selection did not complete; context={worker_context_facts!r}; "
        f"prepared_read_count={len(prepared_reads)}; "
        f"worker_errors={[(type(exc).__module__, type(exc).__qualname__, str(exc)) for exc in worker_errors]!r}"
    )
    assert len(worker_outcomes) + len(worker_errors) == 1
    if worker_outcomes:
        assert len(worker_outcomes) == 1
        assert _resolved_value(store, worker_outcomes[0].state) == 2.6
    else:
        assert type(worker_errors[0]) is ValueError
        assert str(worker_errors[0]) == (
            "artifact ref payload must include artifact_id, kind, media_type"
        )
    assert len(prepared_reads) == 1
    assert close_calls == prepared_reads
    assert prepared_reads[0]._closed is True


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
            store,
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
    context, registry = _build_run_context(store, state.run_id)
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
        store,
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


def test_build_literature_prior_recomputes_existing_output_from_changed_prepared_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An old prior ref cannot bypass a newly prepared source read."""
    db_path = tmp_path / "literature-prior-source.duckdb"
    _seed_skg(db_path)
    store = FileSystemCAS(tmp_path / "literature-prior-cas")
    old_ref = persist_literature_causal_prior(
        store,
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
    store = FileSystemCAS(tmp_path / "resolved-parameters-cas").for_tenant(
        "tenant-a", "cell-a"
    )
    target_context = {
        "context_id": "us-2025",
        "countries": ["US"],
        "publication_year": 2025,
    }
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        graph_ref = persist_causal_graph_model(
            store,
            CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[]),
        )
        old_bundle_ref = persist_context_adaptive_parameter_bundle(
            store,
            ContextAdaptiveParameterBundle(
                target_context=ContextProfile.model_validate(target_context),
                simulation_domain="fiscal",
            ),
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
    context, _ = _build_run_context(store, state.run_id)

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
        current_ref = outcome.state.artifacts_index[
            ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF
        ]
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
    trinity_ref = store.put_json(
        _trinity_bundle(),
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="ir.trinity_bundle", version="1.0"),
        ),
    )
    old_ref = persist_cross_graph_evidence_profile(
        store,
        CrossGraphEvidenceProfile(
            summary=CrossGraphEvidenceSummary(status="ok", total_needs=0),
            notes=["legacy-source-unbound"],
        ),
    )
    state = ExperimentState(
        run_id="R_existing_cross_graph_profile",
        inputs={INPUT_TRINITY_BUNDLE_REF: trinity_ref},
        artifacts_index={ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF: old_ref},
        params={
            "cross_graph_evidence_config": {
                "enabled": True,
                "academic_db_path": str(db_path),
            }
        },
    )
    context, _ = _build_run_context(store, state.run_id)
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
        profile = load_cross_graph_evidence_profile(store, current_ref)
        assert profile.notes == [f"prepared-source-value:{expected_value}"]
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
        store,
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

    workflow = _workflow()
    ctx_first, registry_first = _build_run_context(store, initial_state.run_id)
    first = WorkflowExecutor(ctx_first, registry_first).execute(workflow, initial_state)
    assert _resolved_value(store, first.state) == 1.4

    _set_skg_value(db_path, 3.1)
    ctx_second, registry_second = _build_run_context(store, initial_state.run_id)
    second_trace_start = _trace_event_count(ctx_second)
    second = WorkflowExecutor(ctx_second, registry_second).execute(workflow, initial_state)

    assert second.report.status == "ok"
    assert _resolved_value(store, second.state) == 3.1
    assert not any(
        event.get("event") == "NODE_CACHE_HIT"
        for event in _trace_events(ctx_second, start_line=second_trace_start)
    )
