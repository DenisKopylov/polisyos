from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime

import duckdb
import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.causal_graph import (
    CausalGraphModel,
    GraphType,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.parameters import load_context_adaptive_parameter_bundle
from polisyos.scientist.nodes.builtins.causal.resolve_parameters import ResolveParametersNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.idempotency import compute_idempotency_key
from polisyos.scientist.orchestration.engine.state import ExperimentState


def _build_ctx(tmp_path, *, run_id: str) -> ExecutionContext:
    store = FileSystemCAS(tmp_path / "cas")
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id=run_id)
    return ExecutionContext(store=store, run=run, logger=logging.getLogger(f"test.{run_id}"))


def _seed_skg(db_path) -> None:
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            CREATE TABLE ac_skg_parameters (
                param_id VARCHAR,
                canonical_name VARCHAR,
                openalex_id VARCHAR,
                parameter_json VARCHAR,
                context_json VARCHAR
            )
            """
        )
        con.execute("CREATE TABLE ac_skg_versions (version_id INTEGER)")
        con.execute("INSERT INTO ac_skg_versions VALUES (12)")
        con.executemany(
            "INSERT INTO ac_skg_parameters VALUES (?, ?, ?, ?, ?)",
            [
                (
                    "p_cee",
                    "fiscal_multiplier",
                    "W_CEE",
                    json.dumps(
                        {
                            "name": "fiscal_multiplier",
                            "value": 1.35,
                            "parameter_type": "quantitative",
                            "evidence_strength": "observational",
                        }
                    ),
                    json.dumps(
                        {
                            "context_id": "PL",
                            "income_level": "lower_middle",
                            "institutional_quality": 0.45,
                            "post_communist": True,
                        }
                    ),
                ),
                (
                    "p_far",
                    "fiscal_multiplier",
                    "W_FAR",
                    json.dumps(
                        {
                            "name": "fiscal_multiplier",
                            "value": 2.1,
                            "parameter_type": "quantitative",
                            "evidence_strength": "theoretical",
                        }
                    ),
                    json.dumps(
                        {
                            "context_id": "US",
                            "income_level": "high",
                            "institutional_quality": 0.9,
                            "post_communist": False,
                        }
                    ),
                ),
            ],
        )
    finally:
        con.close()


def test_resolve_parameters_node_persists_bundle_and_bridge_payload(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_phase15_resolve")
    db_path = tmp_path / "skg.duckdb"
    _seed_skg(db_path)
    graph_ref = persist_causal_graph_model(
        ctx.store,
        CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["fiscal_multiplier"],
            edges=[],
        ),
    )
    state = ExperimentState(
        run_id="R_phase15_resolve",
        artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref},
        params={
            "target_context": {
                "context_id": "UA",
                "income_level": "lower_middle",
                "institutional_quality": 0.4,
                "post_communist": True,
            },
            "required_parameters": ["fiscal_multiplier", "missing_parameter"],
            "skg_db_path": str(db_path),
            "skg_index_dir": str(tmp_path / "idx"),
            "domain": "fiscal",
        },
    )

    outcome = ResolveParametersNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF in outcome.state.artifacts_index
    bundle_ref = outcome.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
    bundle = load_context_adaptive_parameter_bundle(ctx.store, bundle_ref)

    # E2E scenario from phase DoD: UA should select CEE-like estimate.
    assert bundle.parameters["fiscal_multiplier"].value == 1.35
    assert "missing_parameter" in bundle.unsupported_parameters
    assert (
        outcome.state.params["literature_priors"]["fiscal_multiplier"]["__intercept__"]["mean"]
        == 1.35
    )
    assert "fiscal_multiplier" in outcome.state.params["parameter_uncertainty_multipliers"]
    assert outcome.state.params["phase15_runtime_ready"] is True
    assert outcome.state.params["phase15_runtime_backend_used"] in {"jax", "numpy", "numpyro"}
    assert (
        outcome.state.params["phase15_runtime_parameter_intervals"]["fiscal_multiplier"]["ci_low"]
        < outcome.state.params["phase15_runtime_parameter_intervals"]["fiscal_multiplier"][
            "ci_high"
        ]
    )
    assert any(event.code == "PARAMS_WITHOUT_EVIDENCE" for event in outcome.events)


def test_existing_bundle_is_revalidated_for_changed_request(tmp_path) -> None:
    """A bundle ref is a reuse candidate, not proof for a changed request."""
    ctx = _build_ctx(tmp_path, run_id="R_phase15_changed_request")
    db_path = tmp_path / "skg.duckdb"
    _seed_skg(db_path)
    graph_ref = persist_causal_graph_model(
        ctx.store,
        CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[]),
    )
    state = ExperimentState(
        run_id="R_phase15_changed_request",
        artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref},
        params={
            "target_context": {
                "context_id": "UA",
                "income_level": "lower_middle",
                "institutional_quality": 0.4,
                "post_communist": True,
            },
            "required_parameters": ["fiscal_multiplier"],
            "skg_db_path": str(db_path),
            "skg_index_dir": str(tmp_path / "idx"),
            "domain": "fiscal",
        },
    )

    first = ResolveParametersNode().execute(ctx, state)
    assert first.status == "ok"
    first_ref = first.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]

    changed = first.state.model_copy(deep=True)
    changed.params["target_context"] = {
        "context_id": "US",
        "income_level": "high",
        "institutional_quality": 0.9,
        "post_communist": False,
    }

    second = ResolveParametersNode().execute(ctx, changed)
    assert second.status == "ok"
    second_ref = second.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
    assert second_ref != first_ref

    second_bundle = load_context_adaptive_parameter_bundle(ctx.store, second_ref)
    assert second_bundle.target_context == ContextProfile(
        context_id="US",
        income_level="high",
        institutional_quality=0.9,
        post_communist=False,
    )
    assert second_bundle.simulation_domain == "fiscal"


def test_matching_bundle_reuses_without_reinvoking_selector(tmp_path, monkeypatch) -> None:
    """A valid request-bound bundle replays when no current SKG source is requested."""
    ctx = _build_ctx(tmp_path, run_id="R_phase15_reuse")
    db_path = tmp_path / "skg.duckdb"
    _seed_skg(db_path)
    graph_ref = persist_causal_graph_model(
        ctx.store,
        CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[]),
    )
    state = ExperimentState(
        run_id="R_phase15_reuse",
        artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref},
        params={
            "target_context": {
                "context_id": "UA",
                "income_level": "lower_middle",
                "institutional_quality": 0.4,
                "post_communist": True,
            },
            "required_parameters": ["fiscal_multiplier"],
            "skg_db_path": str(db_path),
            "skg_index_dir": str(tmp_path / "idx"),
            "domain": "fiscal",
        },
    )

    node = ResolveParametersNode()
    first = node.execute(ctx, state)
    assert first.status == "ok"
    first_ref = first.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]

    def fail_if_selected(*args, **kwargs):
        del args, kwargs
        raise AssertionError("ParameterSelector must not run for a matching CAS bundle")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_parameters.ParameterSelector",
        fail_if_selected,
    )
    replay_state = first.state.model_copy(deep=True)
    replay_state.params.pop("skg_db_path")
    replay_state.params.pop("skg_index_dir")
    first_cas_ref = ArtifactRef.model_validate(first_ref.model_dump(mode="json"))
    assert FileSystemCAS(ctx.store.root).verify(first_cas_ref).ok
    replay = node.execute(ctx, replay_state)

    assert replay.status == "ok"
    assert replay.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF] == first_ref


def test_current_skg_source_reselects_unbound_bundle_and_refuses_missing_source(
    tmp_path, monkeypatch
) -> None:
    """Current reads cannot inherit a v1 bundle's absent selector-read binding."""
    from polisyos.scientist.nodes.builtins.causal import resolve_parameters

    ctx = _build_ctx(tmp_path, run_id="R_phase15_current_source")
    db_path = tmp_path / "skg.duckdb"
    _seed_skg(db_path)
    graph_ref = persist_causal_graph_model(
        ctx.store, CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[])
    )
    state = ExperimentState(
        run_id="R_phase15_current_source",
        artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref},
        params={
            "target_context": {
                "context_id": "UA",
                "income_level": "lower_middle",
                "institutional_quality": 0.4,
                "post_communist": True,
            },
            "required_parameters": ["fiscal_multiplier"],
            "skg_db_path": str(db_path),
            "skg_index_dir": str(tmp_path / "idx"),
            "domain": "fiscal",
        },
    )
    node = ResolveParametersNode()
    first_before = datetime.now(UTC).replace(microsecond=0)
    first = node.execute(ctx, state)
    first_after = datetime.now(UTC)
    assert first.status == "ok"
    first_ref = first.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
    first_bundle = load_context_adaptive_parameter_bundle(ctx.store, first_ref)
    selected = []
    original_select = resolve_parameters.ParameterSelector.select_for_context

    def observe_select(self, **kwargs):
        selected.append(kwargs)
        return original_select(self, **kwargs)

    monkeypatch.setattr(resolve_parameters.ParameterSelector, "select_for_context", observe_select)
    # Source253 explicitly generates a fresh second-resolution selection time.
    # Separate calls across that boundary; identity equality is not the oracle.
    time.sleep(1.05)
    second_before = datetime.now(UTC).replace(microsecond=0)
    second = node.execute(ctx, first.state.model_copy(deep=True))
    second_after = datetime.now(UTC)
    assert second.status == "ok"
    assert len(selected) == 1
    assert selected[0]["parameter_name"] == "fiscal_multiplier"
    assert selected[0]["target_context"] == first_bundle.target_context
    second_ref = second.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
    second_bundle = load_context_adaptive_parameter_bundle(ctx.store, second_ref)
    assert first_bundle.model_dump(exclude={"selection_timestamp"}) == second_bundle.model_dump(
        exclude={"selection_timestamp"}
    )
    first_time = datetime.fromisoformat(first_bundle.selection_timestamp)
    second_time = datetime.fromisoformat(second_bundle.selection_timestamp)
    assert first_time.tzinfo == second_time.tzinfo == UTC
    assert first_before <= first_time <= first_after
    assert second_before <= second_time <= second_after
    assert second_time > first_time
    assert second_ref.artifact_id != first_ref.artifact_id
    reopened = FileSystemCAS(ctx.store.root)
    for ref in (first_ref, second_ref):
        cas_ref = ArtifactRef.model_validate(ref.model_dump(mode="json"))
        assert reopened.verify(cas_ref).ok
        manifest = reopened.get_manifest(cas_ref)
        assert manifest.kind == "ir.context_adaptive_parameter_bundle"
        assert manifest.artifact_schema.name == "ir.context_adaptive_parameter_bundle"
        assert manifest.artifact_schema.version == "1.0"
        assert [(edge.role, str(edge.artifact_id)) for edge in manifest.inputs] == [
            ("causal_graph", str(graph_ref.artifact_id))
        ]
    missing = first.state.model_copy(deep=True)
    missing.params["skg_db_path"] = str(tmp_path / "missing.duckdb")
    refused = node.execute(ctx, missing)
    assert refused.status == "skip"
    assert len(selected) == 1
    assert reopened.verify(ArtifactRef.model_validate(first_ref.model_dump(mode="json"))).ok


def test_changed_domain_invalidates_bundle_and_idempotency_key(tmp_path) -> None:
    """Domain participates in both bundle reuse and node idempotency identity."""
    ctx = _build_ctx(tmp_path, run_id="R_phase15_domain")
    db_path = tmp_path / "skg.duckdb"
    _seed_skg(db_path)
    graph_ref = persist_causal_graph_model(
        ctx.store,
        CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[]),
    )
    state = ExperimentState(
        run_id="R_phase15_domain",
        artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref},
        params={
            "target_context": {
                "context_id": "UA",
                "income_level": "lower_middle",
                "institutional_quality": 0.4,
                "post_communist": True,
            },
            "required_parameters": ["fiscal_multiplier"],
            "skg_db_path": str(db_path),
            "skg_index_dir": str(tmp_path / "idx"),
            "domain": "fiscal",
        },
    )

    node = ResolveParametersNode()
    first = node.execute(ctx, state)
    assert first.status == "ok"
    first_ref = first.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]

    changed = first.state.model_copy(deep=True)
    changed.params["domain"] = "monetary"
    assert compute_idempotency_key(node.spec, first.state) != compute_idempotency_key(
        node.spec, changed
    )

    second = node.execute(ctx, changed)
    assert second.status == "ok"
    second_ref = second.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
    assert second_ref != first_ref
    second_bundle = load_context_adaptive_parameter_bundle(ctx.store, second_ref)
    assert second_bundle.simulation_domain == "monetary"


def test_resolve_parameters_node_skips_on_missing_inputs(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_phase15_resolve_skip")
    state = ExperimentState(run_id="R_phase15_resolve_skip", params={})

    outcome = ResolveParametersNode().execute(ctx, state)

    assert outcome.status == "skip"
    assert outcome.events
    assert outcome.events[0].level == "warn"


def _native_bundle_request(tmp_path, *, run_id):
    ctx = _build_ctx(tmp_path, run_id=run_id)
    db_path = tmp_path / "skg.duckdb"
    _seed_skg(db_path)
    graph = CausalGraphModel(graph_type=GraphType.DAG, nodes=["fiscal_multiplier"], edges=[])
    graph_ref = persist_causal_graph_model(ctx.store, graph)
    state = ExperimentState(
        run_id=run_id,
        artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref},
        params={
            "target_context": {"context_id": "UA", "income_level": "lower_middle"},
            "required_parameters": ["fiscal_multiplier"],
            "skg_db_path": str(db_path),
            "skg_index_dir": str(tmp_path / "idx"),
            "domain": "fiscal",
        },
    )
    node = ResolveParametersNode()
    first = node.execute(ctx, state)
    assert first.status == "ok"
    return ctx, node, first, graph, graph_ref, db_path


@pytest.mark.parametrize("change", ["graph", "required_parameters"])
def test_native_bundle_reuse_checks_graph_and_required_parameters(tmp_path, monkeypatch, change):
    from polisyos.scientist.nodes.builtins.causal import resolve_parameters

    ctx, node, first, _, graph_ref, db_path = _native_bundle_request(
        tmp_path, run_id=f"R_b60_{change}"
    )
    old_ref = first.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
    old_cas_ref = ArtifactRef.model_validate(old_ref.model_dump(mode="json"))
    reopened = FileSystemCAS(ctx.store.root)
    assert reopened.verify(old_cas_ref).ok
    old_bytes = reopened.get_bytes(old_cas_ref)
    selected = []
    select = resolve_parameters.ParameterSelector.select_for_context

    def observe_select(self, **kwargs):
        selected.append(kwargs["parameter_name"])
        return select(self, **kwargs)

    monkeypatch.setattr(resolve_parameters.ParameterSelector, "select_for_context", observe_select)
    same = first.state.model_copy(deep=True)
    same.params.pop("skg_db_path")
    same.params.pop("skg_index_dir")
    assert node.validate_cache_hit(ctx, same, first)
    reused = node.execute(ctx, same)
    assert reused.status == "ok" and selected == []
    assert reused.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF] == old_ref

    changed = same.model_copy(deep=True)
    if change == "graph":
        graph_ref = persist_causal_graph_model(
            ctx.store,
            CausalGraphModel(
                graph_type=GraphType.DAG, nodes=["fiscal_multiplier", "changed_node"], edges=[]
            ),
        )
        changed.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF] = graph_ref
    else:
        changed.params["required_parameters"] = ["fiscal_multiplier", "missing_parameter"]
    assert not node.validate_cache_hit(ctx, changed, first)
    assert node.execute(ctx, changed).status == "skip"
    assert selected == []
    # The v1 producer intentionally writes a fresh second-resolution selection time.
    time.sleep(1.05)
    changed.params["skg_db_path"] = str(db_path)
    changed.params["skg_index_dir"] = str(tmp_path / "idx")
    refreshed = node.execute(ctx, changed)
    assert refreshed.status == "ok"
    assert selected == changed.params["required_parameters"]
    new_ref = refreshed.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
    assert new_ref.artifact_id != old_ref.artifact_id
    new_cas_ref = ArtifactRef.model_validate(new_ref.model_dump(mode="json"))
    assert reopened.verify(new_cas_ref).ok
    new_bundle = load_context_adaptive_parameter_bundle(reopened, new_ref)
    assert set(changed.params["required_parameters"]) <= (
        set(new_bundle.parameters) | set(new_bundle.unsupported_parameters)
    )
    assert [
        (edge.role, str(edge.artifact_id)) for edge in reopened.get_manifest(new_cas_ref).inputs
    ] == [("causal_graph", str(graph_ref.artifact_id))]
    assert node.validate_cache_hit(ctx, changed, refreshed)
    assert reopened.get_bytes(old_cas_ref) == old_bytes and reopened.verify(old_cas_ref).ok


def test_native_unavailable_bundle_ref_does_not_authorize_ok(tmp_path):
    ctx, node, first, graph, _, _ = _native_bundle_request(tmp_path, run_id="R_b60_unavailable")
    old_ref = first.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
    old_cas_ref = ArtifactRef.model_validate(old_ref.model_dump(mode="json"))
    assert ctx.store.verify(old_cas_ref).ok
    consumer = _build_ctx(tmp_path / "fresh_consumer", run_id=first.state.run_id)
    graph_ref = persist_causal_graph_model(consumer.store, graph)
    request = first.state.model_copy(deep=True)
    request.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF] = graph_ref
    request.params.pop("skg_db_path")
    request.params.pop("skg_index_dir")
    before = request.model_dump(mode="json")
    with pytest.raises(FileNotFoundError):
        consumer.store.get_bytes(old_cas_ref)
    assert not node.validate_cache_hit(consumer, request, first)
    refused = node.execute(consumer, request)
    assert refused.status == "skip" and refused.state.model_dump(mode="json") == before
    with pytest.raises(FileNotFoundError):
        consumer.store.get_bytes(old_cas_ref)
    assert ctx.store.verify(old_cas_ref).ok
