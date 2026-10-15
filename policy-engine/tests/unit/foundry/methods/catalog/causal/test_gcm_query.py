from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import numpy as np
import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.foundry.methods.catalog.causal._dowhy_worker import _worker_directory
from polisyos.foundry.methods.catalog.causal.gcm_fit import (
    HybridSCMFit,
    validate_persisted_gcm_spec,
)
from polisyos.foundry.methods.catalog.causal.gcm_query import GCMQuery, _simulate_samples
from polisyos.foundry.methods.catalog.causal.protocols import SCMFitData, SCMQueryData
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.causal_queries import CausalQueryResult
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    MechanismSource,
    NodeMechanism,
    StructuralCausalModelSpec,
)
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.compute.runner import run_job


def _fit_data() -> SCMFitData:
    rng = np.random.default_rng(321)
    w = rng.normal(size=400)
    x = 0.2 + 0.8 * w + rng.normal(scale=0.15, size=400)
    y = 1.0 + 3.0 * x + w + rng.normal(scale=0.1, size=400)
    z = rng.normal(size=400)
    return SCMFitData(
        data=np.column_stack([w, x, y, z]),
        column_names=["W", "X", "Y", "Z"],
        graph=CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["W", "X", "Y", "Z"],
            edges=[
                CausalEdge(src="W", dst="X"),
                CausalEdge(src="W", dst="Y"),
                CausalEdge(src="X", dst="Y"),
            ],
        ),
        metadata={
            "sampling_unit": "iid_observation_row",
            "input_scope": "known_synthetic_dgp",
        },
    )


def _fit_selected_gcm(tmp_path: Path) -> StructuralCausalModelSpec:
    """Produce a real source-bound GCM artifact through the selected worker."""
    from polisyos.foundry import causal_worker_execution_context

    data = _fit_data()
    store = FileSystemCAS(tmp_path / "cas")
    source = store.put_json(
        data.model_dump(mode="json"),
        PutOptions(
            kind="tests.scm_fit_data",
            media_type="application/json",
            schema=SchemaInfo(name="tests.SCMFitData", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    configured_worker = os.environ.get("E02_TEST_DOWHY_WORKER_PYTHON")
    if configured_worker is None and sys.platform != "linux":
        pytest.skip(
            "source-bound GCM fitting requires the selected Linux/Python 3.12 DoWhy worker; "
            "set E02_TEST_DOWHY_WORKER_PYTHON for an explicit worker"
        )
    worker_python = (
        Path(configured_worker)
        if configured_worker is not None
        else _worker_directory() / ".venv/bin/python"
    )
    assert worker_python.is_file(), "Install the selected locked GCM worker before this test"
    MethodRegistry.get_instance().register(HybridSCMFit, override=True)
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("POLISYOS_DOWHY_WORKER_PYTHON", str(worker_python))
        with causal_worker_execution_context(store=store, source_ref=source):
            result = run_job(
                JobSpec(
                    job_kind="method",
                    method_fqn=HybridSCMFit.signature.fqn,
                    input_refs={"scm_fit_data": source},
                    seed=23,
                ),
                cas_root=tmp_path / "cas",
                method_state=data,
            )
    assert not result.issues, result.issues
    assert result.method_result_ref is not None
    payload = from_canonical_bytes(store.get_bytes(result.method_result_ref))
    scm_spec = StructuralCausalModelSpec.model_validate(payload["scm_spec"])
    assert payload["structural_causal_model_spec"] == payload["scm_spec"]
    assert scm_spec.schema_version == "1.2"
    assert scm_spec.fit_method == "gcm"
    assert scm_spec.source_graph == data.graph
    assert scm_spec.graph_projection is not None
    assert scm_spec.training_rows is not None
    assert scm_spec.fit_provenance is not None
    assert (
        scm_spec.training_rows.source_sha256 == hashlib.sha256(store.get_bytes(source)).hexdigest()
    )
    validate_persisted_gcm_spec(scm_spec, store)
    return scm_spec


@pytest.fixture(scope="module")
def fitted_scm(tmp_path_factory: pytest.TempPathFactory) -> StructuralCausalModelSpec:
    return _fit_selected_gcm(tmp_path_factory.mktemp("gcm-query"))


def _manual_scm(*, y_family: MechanismFamily = MechanismFamily.LINEAR) -> StructuralCausalModelSpec:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )
    return StructuralCausalModelSpec(
        graph=graph,
        mechanisms=[
            NodeMechanism(
                variable="X",
                parents=[],
                family=MechanismFamily.EMPIRICAL,
                family_params={"mean": 0.0, "std": 1.0},
                source=MechanismSource.DATA_FITTED,
            ),
            NodeMechanism(
                variable="Y",
                parents=["X"],
                family=y_family,
                family_params={
                    "intercept": 0.5,
                    "coefficients": {"X": 2.0},
                    "noise_std": 0.1,
                    "mean": 0.5,
                    "std": 0.2,
                },
                source=MechanismSource.DATA_FITTED,
            ),
        ],
        schema_version="1.0",
        fitted=False,
        fit_method="manual",
    )


def _run_query(scm_spec: StructuralCausalModelSpec, query: dict, *, seed: int = 123) -> dict:
    payload = SCMQueryData(scm_spec=scm_spec, query=query)
    return GCMQuery.pure_step(payload, params={"__seed__": seed})


def test_gcm_query_interventional_atomic(fitted_scm: StructuralCausalModelSpec) -> None:
    result = _run_query(
        fitted_scm,
        {
            "query_type": "interventional",
            "treatment_variable": "X",
            "treatment_value": 1.0,
            "outcome_variable": "Y",
            "n_samples": 2000,
        },
    )
    query_result = CausalQueryResult.model_validate(result["query_result"])
    assert query_result.result_mean == pytest.approx(4.0, abs=0.15)
    assert query_result.result_std > 0.0


def test_gcm_query_counterfactual_with_condition(fitted_scm: StructuralCausalModelSpec) -> None:
    result = _run_query(
        fitted_scm,
        {
            "query_type": "counterfactual",
            "treatment_variable": "X",
            "treatment_value": 0.0,
            "outcome_variable": "Y",
            "condition": {"W": 0.0, "X": 1.0, "Y": 4.0},
            "n_samples": 512,
        },
    )
    query_result = CausalQueryResult.model_validate(result["query_result"])
    assert query_result.result_mean == pytest.approx(1.0, abs=0.2)


def test_gcm_query_shifted_and_truncated_soft_interventions(
    fitted_scm: StructuralCausalModelSpec,
) -> None:
    shifted = _run_query(
        fitted_scm,
        {
            "query_type": "soft_intervention",
            "treatment_variable": "X",
            "outcome_variable": "Y",
            "n_samples": 1024,
            "intervention_spec": {"type": "shifted", "shift": 1.0},
        },
        seed=11,
    )
    truncated = _run_query(
        fitted_scm,
        {
            "query_type": "soft_intervention",
            "treatment_variable": "X",
            "outcome_variable": "Y",
            "n_samples": 1024,
            "intervention_spec": {"type": "truncated", "bounds": [-0.2, 0.2]},
        },
        seed=11,
    )

    shifted_result = CausalQueryResult.model_validate(shifted["query_result"])
    truncated_result = CausalQueryResult.model_validate(truncated["query_result"])
    assert shifted_result.result_mean > truncated_result.result_mean
    assert shifted_result.result_mean > 1.5


def test_gcm_query_rejects_malformed_stochastic_law(
    fitted_scm: StructuralCausalModelSpec,
) -> None:
    with pytest.raises(ValueError, match="stochastic intervention"):
        GCMQuery.pure_step(
            SCMQueryData(
                scm_spec=fitted_scm,
                query={
                    "query_type": "interventional",
                    "treatment_variable": "X",
                    "treatment_value": 1.5,
                    "outcome_variable": "Y",
                    "n_samples": 512,
                    "intervention_spec": {
                        "type": "stochastic",
                        "distribution": "broken(",
                    },
                },
            ),
            params={"__seed__": 33},
        )


def test_gcm_query_stochastic_truncnorm_tail_has_no_endpoint_atoms(
    fitted_scm: StructuralCausalModelSpec,
) -> None:
    result = _run_query(
        fitted_scm,
        {
            "query_type": "interventional",
            "treatment_variable": "X",
            "outcome_variable": "X",
            "n_samples": 512,
            "intervention_spec": {
                "type": "stochastic",
                "distribution": "truncnorm(0, 1, 8, 10)",
            },
        },
        seed=29,
    )
    query_result = CausalQueryResult.model_validate(result["query_result"])
    draws = np.asarray(query_result.result_distribution, dtype=float)
    assert draws.shape == (512,)
    assert np.all((draws > 8.0) & (draws < 10.0))
    assert np.unique(draws).size == len(draws)


def test_gcm_query_atomic_intervention_keeps_active_ancestor_and_prunes_sibling(
    fitted_scm: StructuralCausalModelSpec,
) -> None:
    result = _run_query(
        fitted_scm,
        {
            "query_type": "interventional",
            "treatment_variable": "X",
            "treatment_value": 2.0,
            "outcome_variable": "Y",
            "n_samples": 512,
        },
        seed=31,
    )
    query_result = CausalQueryResult.model_validate(result["query_result"])
    assert query_result.result_mean == pytest.approx(7.0, abs=0.15)

    _, active = _simulate_samples(
        scm_spec=fitted_scm,
        query=SCMQueryData(
            scm_spec=fitted_scm,
            query={
                "query_type": "interventional",
                "treatment_variable": "X",
                "treatment_value": 2.0,
                "outcome_variable": "Y",
                "n_samples": 32,
            },
        ).query,
        n_samples=32,
        rng=np.random.default_rng(31),
        warnings=[],
    )
    assert set(active) == {"W", "X", "Y"}
    _, full_trace = _simulate_samples(
        scm_spec=fitted_scm,
        query=SCMQueryData(
            scm_spec=fitted_scm,
            query={
                "query_type": "interventional",
                "treatment_variable": "X",
                "treatment_value": 2.0,
                "outcome_variable": "Y",
                "n_samples": 32,
            },
        ).query,
        n_samples=32,
        rng=np.random.default_rng(31),
        warnings=[],
        include_all_nodes=True,
    )
    assert set(full_trace) == {"W", "X", "Y", "Z"}


def test_gcm_query_surfaces_mechanism_fallback_warning() -> None:
    result = _run_query(
        _manual_scm(y_family=MechanismFamily.POST_NONLINEAR),
        {
            "query_type": "interventional",
            "treatment_variable": "X",
            "treatment_value": 1.0,
            "outcome_variable": "Y",
            "n_samples": 256,
        },
    )
    warnings = result.get("warnings", [])
    assert any("not fully supported" in str(item) for item in warnings)


def test_gcm_query_dowhy_parity_optional() -> None:
    pytest.importorskip("dowhy")

    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["Z", "X", "Y"],
        edges=[
            CausalEdge(src="Z", dst="X"),
            CausalEdge(src="Z", dst="Y"),
            CausalEdge(src="X", dst="Y"),
        ],
    )
    scm_spec = StructuralCausalModelSpec(
        graph=graph,
        mechanisms=[
            NodeMechanism(
                variable="Z",
                parents=[],
                family=MechanismFamily.EMPIRICAL,
                family_params={"mean": 0.0, "std": 1.0},
                source=MechanismSource.DATA_FITTED,
            ),
            NodeMechanism(
                variable="X",
                parents=["Z"],
                family=MechanismFamily.LINEAR,
                family_params={
                    "intercept": 0.0,
                    "coefficients": {"Z": 0.8},
                    "noise_std": 0.2,
                },
                source=MechanismSource.DATA_FITTED,
            ),
            NodeMechanism(
                variable="Y",
                parents=["X", "Z"],
                family=MechanismFamily.LINEAR,
                family_params={
                    "intercept": 0.0,
                    "coefficients": {"X": 1.2, "Z": 0.7},
                    "noise_std": 0.2,
                },
                source=MechanismSource.DATA_FITTED,
            ),
        ],
        schema_version="1.0",
        fitted=False,
        fit_method="manual",
    )

    treat = _run_query(
        scm_spec,
        {
            "query_type": "interventional",
            "treatment_variable": "X",
            "treatment_value": 1.0,
            "outcome_variable": "Y",
            "n_samples": 2000,
        },
        seed=77,
    )
    control = _run_query(
        scm_spec,
        {
            "query_type": "interventional",
            "treatment_variable": "X",
            "treatment_value": 0.0,
            "outcome_variable": "Y",
            "n_samples": 2000,
        },
        seed=77,
    )

    treat_res = CausalQueryResult.model_validate(treat["query_result"])
    control_res = CausalQueryResult.model_validate(control["query_result"])
    gcm_ate = treat_res.result_mean - control_res.result_mean
    dowhy_comparison = treat.get("dowhy_comparison")
    assert isinstance(dowhy_comparison, dict)
    assert abs(gcm_ate - float(dowhy_comparison["dowhy_ate"])) < 0.35
