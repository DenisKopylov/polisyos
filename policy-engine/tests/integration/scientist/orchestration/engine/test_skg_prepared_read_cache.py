from __future__ import annotations

import hashlib
import json
import logging
import os
import signal
import sys
from dataclasses import replace
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import Any

import duckdb
import pytest
from _helpers.run_lifecycle import (
    assert_one_resumed_terminal_lifecycle,
    interrupt_and_suspend_before_finalize,
    start_or_resume_run,
)

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts import input_ref_from_artifact_ref, profile_bound_ref
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import ComponentId
from polisyos.core.registry import build_default_registry_bundle
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
    ContextAdaptiveParameterBundleV11,
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
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF,
    ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
    ARTIFACT_LITERATURE_PRIOR_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
    INPUT_TRINITY_BUNDLE_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor, WorkflowReport
from polisyos.scientist.orchestration.engine.idempotency import (
    NodeCacheEntry,
    NodeResultCache,
    compute_idempotency_key,
)
from polisyos.scientist.orchestration.engine.protocol import NodeEvent, NodeOutcome
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


def _build_run_context(
    store: FileSystemCAS,
    run_id: str,
    *,
    tenant_id: str | None = None,
    cell_id: str | None = None,
    resume_from: ExecutionContext | None = None,
    selected_registry_profile: bool = False,
) -> tuple[ExecutionContext, NodeRegistry]:
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
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
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        return WorkflowExecutor(context, registry).execute(workflow, state)


def _workflow_result_from_events(
    context: ExecutionContext, events: list[dict[str, Any]]
) -> tuple[WorkflowReport, ExperimentState]:
    """Read the actual persisted workflow outputs before an interrupted terminal boundary."""
    refs = [
        ArtifactRef.model_validate(raw_ref)
        for event in events
        if event.get("event") == "RUN_OUTPUT_ADDED"
        for raw_ref in event.get("refs", {}).get("outputs", [])
    ]
    report_ref = next(ref for ref in reversed(refs) if ref.kind == "scientist.workflow_report")
    state_ref = next(ref for ref in reversed(refs) if ref.kind == "scientist.experiment_state")
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        report = WorkflowReport.model_validate(
            from_canonical_bytes(context.store.get_bytes(report_ref.artifact_id))
        )
        state = ExperimentState.model_validate(
            from_canonical_bytes(context.store.get_bytes(state_ref.artifact_id))
        )
    return report, state


def _execute_workflow_and_suspend(
    context: ExecutionContext,
    registry: NodeRegistry,
    workflow: WorkflowSpec,
    state: ExperimentState,
    *,
    expected_resumes: int,
) -> tuple[WorkflowReport, ExperimentState, list[dict[str, object]]]:
    """Run real consumers, retain their CAS outputs, and pause before terminal publication."""
    start_line = _trace_event_count(context)
    interrupt_and_suspend_before_finalize(
        context.run,
        lambda: _execute_workflow(context, registry, workflow, state),
        expected_resumes=expected_resumes,
    )
    events = _trace_events(context, start_line=start_line)
    report, result_state = _workflow_result_from_events(context, events)
    return report, result_state, events


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
    workflow = _workflow()

    ctx_first, registry_first = _build_run_context(
        store, initial_state.run_id, selected_registry_profile=True
    )
    first_report, first_state, first_events = _execute_workflow_and_suspend(
        ctx_first, registry_first, workflow, initial_state, expected_resumes=0
    )
    first_value = _resolved_value(store, first_state)
    assert first_report.status == "ok"
    assert first_value == 1.4
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

    ctx_hit, registry_hit = _build_run_context(store, initial_state.run_id, resume_from=ctx_first)
    hit_report, hit_state, hit_events = _execute_workflow_and_suspend(
        ctx_hit, registry_hit, workflow, initial_state, expected_resumes=1
    )

    assert hit_report.status == "ok"
    assert _resolved_value(store, hit_state) == first_value
    hit_events = [event for event in hit_events if event.get("event") == "NODE_CACHE_HIT"]
    assert len(hit_events) == 1
    receipt_refs = [
        ref
        for ref in hit_report.nodes[0].artifacts
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

    _set_unrelated_value(db_path, 2)
    ctx_unrelated, registry_unrelated = _build_run_context(
        store, initial_state.run_id, resume_from=ctx_hit
    )
    unrelated_report, unrelated_state, unrelated_events = _execute_workflow_and_suspend(
        ctx_unrelated,
        registry_unrelated,
        workflow,
        initial_state,
        expected_resumes=2,
    )

    assert unrelated_report.status == "ok"
    assert _resolved_value(store, unrelated_state) == first_value
    assert not any(event.get("event") == "NODE_CACHE_HIT" for event in unrelated_events)
    assert sum(event.get("event") == "NODE_CACHE_STORE" for event in unrelated_events) == 1

    _set_skg_value(db_path, 2.6)
    ctx_changed, registry_changed = _build_run_context(
        store, initial_state.run_id, resume_from=ctx_unrelated
    )
    changed_trace_start = _trace_event_count(ctx_changed)
    changed = _execute_workflow(ctx_changed, registry_changed, workflow, unrelated_state)

    assert changed.report.status == "ok"
    assert _resolved_value(store, changed.state) == 2.6
    changed_events = _trace_events(ctx_changed, start_line=changed_trace_start)
    assert not any(event.get("event") == "NODE_CACHE_HIT" for event in changed_events)
    assert sum(event.get("event") == "NODE_CACHE_STORE" for event in changed_events) == 1
    assert_one_resumed_terminal_lifecycle(ctx_changed.run, expected_resumes=3)


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
        store, state.run_id, selected_registry_profile=True
    )
    first_report, _first_state, first_events = _execute_workflow_and_suspend(
        first_context, first_registry, _workflow(), state, expected_resumes=0
    )
    assert first_report.status == "ok"
    assert observed == [1]
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

    hit_context, hit_registry = _build_run_context(store, state.run_id, resume_from=first_context)
    hit = _execute_workflow(hit_context, hit_registry, _workflow(), state)
    assert hit.report.status == "ok"
    assert observed == [1]
    assert_one_resumed_terminal_lifecycle(hit_context.run)
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
    context, registry = _build_run_context(store, state.run_id)

    with pytest.raises(duckdb.CatalogException):
        _execute_workflow(context, registry, _workflow(), state)

    assert len(prepared_reads) == 1
    assert close_calls == prepared_reads
    assert prepared_reads[0]._closed is True


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
    context, registry = _build_run_context(store, state.run_id, selected_registry_profile=True)
    writes_before_warmup = tuple(underlying_store_write_calls)
    warmup_report, warmup_state, warmup_events = _execute_workflow_and_suspend(
        context, registry, _workflow(), state, expected_resumes=0
    )
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
    context, registry = _build_run_context(store, state.run_id, resume_from=context)
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
    assert_one_resumed_terminal_lifecycle(context.run)


@pytest.mark.skipif(
    sys.platform != "darwin", reason="requires the native Darwin spawn timeout route"
)
def test_darwin_spawn_timeout_recomputes_changed_skg_and_persists_profile_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A canonical spawn worker reads current SKG bytes and publishes a typed bundle."""
    from polisyos.scientist.orchestration.engine import retry as retry_module

    allowed_cleanup_exitcodes = {0, -signal.SIGTERM}

    db_path = tmp_path / "skg-spawn-source.duckdb"
    _seed_skg(db_path)
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", "cell-a")
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
    context, registry = _build_run_context(
        store,
        state.run_id,
        tenant_id="tenant-a",
        cell_id="cell-a",
        selected_registry_profile=True,
    )
    warmup_report, warmup_state, warmup_events = _execute_workflow_and_suspend(
        context, registry, _workflow(), state, expected_resumes=0
    )
    assert warmup_report.status == "ok"
    assert _resolved_value(store, warmup_state) == 1.4

    warmup_store_event = next(
        event for event in warmup_events if event.get("event") == "NODE_CACHE_STORE"
    )
    source_bound_entry_ref = ArtifactRef.model_validate(warmup_store_event["refs"]["outputs"][0])
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
    context, registry = _build_run_context(store, state.run_id, resume_from=context)
    context.run.emit(
        "scientist.node.resolve",
        "NODE_CACHE_STORE",
        outputs=[unbound_entry_ref],
    )

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
        assert isinstance(bundle, ContextAdaptiveParameterBundleV11)
        assert bundle.schema_version == "1.1"
        assert bundle.parameters["fiscal_multiplier"].value == 2.6
        assert bundle.skg_version_id == 7
        selected_materialization = (
            context.run.trace_path.parent
            / "skg-snapshots"
            / f"{selected_snapshot.source_sha256}.duckdb"
        )
        assert bundle.skg_snapshot_ref == f"duckdb://{selected_materialization.resolve()}#v7"
        assert bundle.selected_cross_graph_profile_ref == selected_profile_ref
        assert load_cross_graph_evidence_profile(
            _ensure_ir_artifact_store(store), selected_profile_ref
        ).notes == ["spawn-worker-profile"]
        assert bundle_manifest.artifact_schema is not None
        assert bundle_manifest.artifact_schema.name == "ir.context_adaptive_parameter_bundle"
        assert bundle_manifest.artifact_schema.version == "1.1"
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

    class SpawnContextProxy:
        def __getattr__(self, name: str) -> Any:
            if name == "Process":
                return process_factory
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
    assert_one_resumed_terminal_lifecycle(context.run)


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
    context, _registry = _build_run_context(store, run_id)
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
    trinity_ref = store.put_json(
        _trinity_bundle(),
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="ir.trinity_bundle", version="1.0"),
        ),
    )
    old_ref = persist_cross_graph_evidence_profile(
        _ensure_ir_artifact_store(store),
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
        profile = load_cross_graph_evidence_profile(_ensure_ir_artifact_store(store), current_ref)
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

    workflow = _workflow()
    ctx_first, registry_first = _build_run_context(
        store, initial_state.run_id, selected_registry_profile=True
    )
    cold_events = interrupt_and_suspend_before_finalize(
        ctx_first.run,
        lambda: _execute_workflow(ctx_first, registry_first, workflow, initial_state),
    )
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

    _set_skg_value(db_path, 3.1)
    ctx_second, registry_second = _build_run_context(
        store, initial_state.run_id, resume_from=ctx_first
    )
    second_trace_start = _trace_event_count(ctx_second)
    second = WorkflowExecutor(ctx_second, registry_second).execute(workflow, initial_state)

    assert second.report.status == "ok"
    assert _resolved_value(store, second.state) == 3.1
    assert not any(
        event.get("event") == "NODE_CACHE_HIT"
        for event in _trace_events(ctx_second, start_line=second_trace_start)
    )
    assert_one_resumed_terminal_lifecycle(ctx_second.run)
