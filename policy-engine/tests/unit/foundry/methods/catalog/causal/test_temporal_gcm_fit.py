"""Finite temporal observations through the real native SCM fit and reader."""

from __future__ import annotations

import copy
import logging

import numpy as np
import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.methods.catalog.causal.gcm_fit import (
    HybridSCMFit,
    persist_temporal_scm_fit,
    temporal_fit_data_from_observations,
    validate_persisted_gcm_spec,
)
from polisyos.foundry.methods.catalog.causal.gcm_query import GCMQuery
from polisyos.foundry.methods.catalog.causal.protocols import SCMFitData, SCMQueryData
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    GraphType,
    expand_temporal_graph,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.structural_causal_model import (
    StructuralCausalModelSpec,
    load_structural_causal_model_spec,
    persist_structural_causal_model_spec,
)
from polisyos.ir.registry.refs import ArtifactRefModel, CausalGraphModelRef
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.compute.runner import run_job
from polisyos.scientist.nodes.builtins.causal.run_causal_queries import RunCausalQueriesNode
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


def _input(store: FileSystemCAS, payload: dict[str, object]) -> ArtifactRefModel:
    ref = store.put_json(
        payload,
        PutOptions(
            kind="tests.temporal_observations",
            media_type="application/json",
            schema=SchemaInfo(name="tests.temporal_observations", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return ArtifactRefModel.from_selected_write(ref.model_dump(mode="json"))


def _scenario(store: FileSystemCAS) -> tuple[CausalGraphModelRef, dict[str, object]]:
    ir_store = ensure_ir_artifact_store(store)
    compact = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y", lag=1), CausalEdge(src="Y", dst="X", lag=1)],
        metadata={"graph_basis": "synthetic"},
    )
    compact_ref = persist_causal_graph_model(ir_store, compact, return_selected_profile=True)
    expanded = expand_temporal_graph(
        ir_store,
        compact_ref,
        query_coordinates=[("X", 3), ("Y", 3)],
        start_step=0,
        end_step=3,
        boundary_coordinates=[("X", 0), ("Y", 0)],
        lag_unit="year",
        time_unit="year",
    )
    expanded_ref = persist_causal_graph_model(ir_store, expanded, return_selected_profile=True)
    rows = []
    for index in range(6):
        x, y = index + 0.25, 2.0 * index + 0.5
        for step in range(4):
            rows.extend(
                [
                    {"trajectory_id": str(index), "variable": "X", "step": step, "value": x},
                    {"trajectory_id": str(index), "variable": "Y", "step": step, "value": y},
                ]
            )
            x, y = 2.0 * y, 3.0 * x
    return expanded_ref, {
        "schema_version": "1.0",
        "source_graph_ref": compact_ref.model_dump(mode="json"),
        "time_unit": "year",
        "rows": list(reversed(rows)),
    }


def test_temporal_rows_fit_and_fresh_scm_query_preserve_selected_inputs(tmp_path) -> None:
    """A real CAS corpus is aligned, fitted, reopened and queried with its source bound."""
    store = FileSystemCAS(tmp_path / "cas")
    ir_store = ensure_ir_artifact_store(store)
    graph_ref, observations = _scenario(store)
    data_ref = _input(store, observations)
    data = temporal_fit_data_from_observations(
        ir_store, expanded_graph_ref=graph_ref, observations_ref=data_ref
    )
    assert data.data.shape == (6, 8)
    binding = data.graph.metadata["temporal_observation_binding"]
    assert binding["observations_ref"] == data_ref.model_dump(mode="json")
    assert binding["expanded_graph_ref"] == graph_ref.model_dump(mode="json")
    assert data.data[0, 0] == pytest.approx(0.25)
    assert binding["trajectory_ids"] == [str(i) for i in range(6)]
    fit_input_ref = store.put_json(
        data.model_dump(mode="json"),
        PutOptions(
            kind="tests.scm_fit_data",
            media_type="application/json",
            schema=SchemaInfo(name="tests.SCMFitData", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    MethodRegistry.get_instance().register(HybridSCMFit, override=True)
    job = run_job(
        JobSpec(
            job_kind="method",
            method_fqn=HybridSCMFit.signature.fqn,
            method_params={"fit_backend": "native_hybrid"},
            input_refs={"scm_fit_data": fit_input_ref},
            seed=7,
        ),
        cas_root=store.root,
        method_state=data,
    )
    assert not job.issues, job.issues
    assert job.method_result_ref is not None
    fit = StructuralCausalModelSpec.model_validate(
        from_canonical_bytes(store.get_bytes(job.method_result_ref))["scm_spec"]
    )
    bound_ref = CausalGraphModelRef.from_selected_write(data.metadata["temporal_bound_graph_ref"])
    scm_ref = persist_temporal_scm_fit(ir_store, fit_data=data, scm_spec=fit)
    fresh_store = ensure_ir_artifact_store(FileSystemCAS(store.root))
    restored = load_structural_causal_model_spec(fresh_store, scm_ref)
    manifest = fresh_store.get_manifest(dict(scm_ref))
    assert any(
        str(item.artifact_id) == str(bound_ref.artifact_id)
        and item.manifest_profile_sha256 == bound_ref.manifest_profile_sha256
        for item in manifest.inputs
    )
    assert restored.source_graph.metadata["temporal_observation_binding"] == binding
    validate_persisted_gcm_spec(restored, FileSystemCAS(store.root), scm_ref=scm_ref)
    coordinates = {
        (e["variable"], e["step"]): e["node"]
        for e in restored.graph.metadata["temporal_expansion"]["coordinates"]
    }
    query = {
        "query_type": "interventional",
        "treatment_variable": coordinates[("X", 2)],
        "treatment_value": 2.0,
        "outcome_variable": coordinates[("Y", 3)],
        "n_samples": 32,
    }
    result = GCMQuery.pure_step(
        SCMQueryData(
            scm_spec=restored,
            query=query,
        ),
        {"__seed__": 7, "enable_dowhy_comparison": False},
    )["query_result"]
    assert result.result_mean == pytest.approx(6.0, abs=1e-10)

    bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=bundle, run_id="temporal-query")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("temporal-query"))

    def state(ref: object) -> ExperimentState:
        return ExperimentState(
            run_id="temporal-query",
            params={
                "random_seed": 7,
                "structural_causal_model_ref": ref.model_dump(mode="json"),
                "causal_query": query,
            },
        )

    accepted = RunCausalQueriesNode().execute(ctx, state(scm_ref))
    assert accepted.status == "ok", accepted.error

    # Same SCM bytes under a selected profile without its graph lineage are not
    # interchangeable with the selected input-bearing manifest.
    unlinked = persist_structural_causal_model_spec(ir_store, fit)
    assert str(unlinked.artifact_id) == str(scm_ref.artifact_id)
    assert unlinked.manifest_profile_sha256 != scm_ref.manifest_profile_sha256
    with pytest.raises(ValueError, match="selected bound graph lineage"):
        validate_persisted_gcm_spec(restored, FileSystemCAS(store.root), scm_ref=unlinked)
    rejected = RunCausalQueriesNode().execute(ctx, state(unlinked))
    assert rejected.status == "fail"
    assert "selected bound graph lineage" in str(rejected.error)


def test_temporal_same_graph_bytes_with_missing_manifest_inputs_are_refused(tmp_path) -> None:
    """An identical payload cannot substitute for the admitted selected profile."""
    store = FileSystemCAS(tmp_path / "cas")
    ir_store = ensure_ir_artifact_store(store)
    graph_ref, observations = _scenario(store)
    data = temporal_fit_data_from_observations(
        ir_store, expanded_graph_ref=graph_ref, observations_ref=_input(store, observations)
    )
    expected = CausalGraphModelRef.from_selected_write(data.metadata["temporal_bound_graph_ref"])
    foreign = persist_causal_graph_model(ir_store, data.graph, return_selected_profile=True)
    assert str(foreign.artifact_id) == str(expected.artifact_id)
    assert foreign.manifest_profile_sha256 != expected.manifest_profile_sha256
    data.metadata["temporal_bound_graph_ref"] = foreign.model_dump(mode="json")
    fit = HybridSCMFit.pure_step(data, {"fit_backend": "native_hybrid"})["scm_spec"]
    with pytest.raises(ValueError, match="invalid selected source binding"):
        persist_temporal_scm_fit(ir_store, fit_data=data, scm_spec=fit)


@pytest.mark.parametrize("mutation", ["unit", "source", "duplicate", "boundary", "shift"])
def test_temporal_rows_reject_incompatible_source_unit_and_coordinates(tmp_path, mutation) -> None:
    """Source, unit, initial history and unique times are actual admission inputs."""
    store = FileSystemCAS(tmp_path / mutation)
    ir_store = ensure_ir_artifact_store(store)
    graph_ref, original = _scenario(store)
    payload = copy.deepcopy(original)
    rows = payload["rows"]
    if mutation == "unit":
        payload["time_unit"] = "day"
    elif mutation == "source":
        foreign = CausalGraphModel(graph_type=GraphType.DAG, nodes=["Z"], edges=[])
        payload["source_graph_ref"] = persist_causal_graph_model(
            ir_store, foreign, return_selected_profile=True
        ).model_dump(mode="json")
    elif mutation == "duplicate":
        rows.append(copy.deepcopy(rows[0]))
    elif mutation == "boundary":
        rows[:] = [row for row in rows if not (row["trajectory_id"] == "0" and row["step"] == 0)]
    else:
        for row in rows:
            if row["trajectory_id"] == "0":
                row["step"] += 1
    with pytest.raises(ValueError, match=r"time units|different source|duplicate|missing"):
        temporal_fit_data_from_observations(
            ir_store, expanded_graph_ref=graph_ref, observations_ref=_input(store, payload)
        )


def test_duplicate_graph_edges_preserve_one_logical_parent_and_one_effect() -> None:
    """Repeated evidence-bearing edge rows do not duplicate the OLS regressor."""
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y"), CausalEdge(src="X", dst="Y")],
    )
    x = np.arange(1.0, 6.0)
    data = SCMFitData(data=np.column_stack([x, 1 + 2 * x]), column_names=["X", "Y"], graph=graph)
    fit = HybridSCMFit.pure_step(data, {"fit_backend": "native_hybrid"})["scm_spec"]
    assert len(fit.graph.edges) == 2
    mechanism = next(item for item in fit.mechanisms if item.variable == "Y")
    assert mechanism.parents == ["X"]
    assert mechanism.family_params["coefficients"]["X"] == pytest.approx(2.0)
    query = SCMQueryData(
        scm_spec=fit,
        query={
            "query_type": "interventional",
            "treatment_variable": "X",
            "treatment_value": 3.0,
            "outcome_variable": "Y",
            "n_samples": 8,
        },
    )
    result = GCMQuery.pure_step(query, {"enable_dowhy_comparison": False})["query_result"]
    assert result.result_mean == pytest.approx(7.0)
