"""Configured graph/NumPy execution persists actual nonstationary calibration pairs."""

from __future__ import annotations

import copy
from typing import Any

import numpy as np
import pytest

from polisyos.calibration import load_continuous_evaluation
from polisyos.core.artifacts import ArtifactRef, ArtifactWriteOptions
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.foundry import (
    ExecPlan,
    LoweredIR,
    LoweredIRRef,
    ProgramGraph,
    ProgramGraphRef,
    ProgramNode,
)
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.api import _build_standard_derived_refs
from polisyos.foundry.execute.executor import execute_program_graph
from polisyos.foundry.methods.backends.circuit_breaker import CircuitBreakerRegistry
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.econometrics.advanced import NonstationaryGARCHEstimator
from polisyos.foundry.methods.catalog.econometrics.protocols import PanelData
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
)


@pytest.fixture(autouse=True)
def _reset_runtimes():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    CircuitBreakerRegistry.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    CircuitBreakerRegistry.reset_instance()


def _panel() -> PanelData:
    rng = np.random.default_rng(20261006)
    return PanelData(
        dependent=rng.normal(scale=0.25, size=140),
        exog=np.zeros((140, 1)),
        entity_ids=np.repeat(np.arange(2), 70),
        time_ids=np.tile(np.arange(70), 2),
        feature_names=["constant"],
        metadata={"target_id": "synthetic-return", "unit": "return", "group_labels": ["g", "g"]},
    )


def _params() -> dict[str, Any]:
    return {
        "max_breaks": 0,
        "break_detection_method": "none",
        "min_segment_length": 12,
        "holdout_periods": 50,
        "nominal_coverage": 0.95,
        "diagnostic_levels": (0.95,),
        "variance_feature_names": (),
        "run_policy_benchmark": True,
    }


def _assert_fresh_source_and_pairs(store: FileSystemCAS, ref: ArtifactRef) -> None:
    fresh = FileSystemCAS(store.root)
    report = load_continuous_evaluation(fresh, ref)
    artifact = from_canonical_bytes(fresh.get_bytes(ref))
    pairs = from_canonical_bytes(fresh.get_bytes(ArtifactRef.model_validate(artifact["pairs_ref"])))
    binding = artifact["source_binding"]
    source = from_canonical_bytes(
        fresh.get_bytes(ArtifactRef.model_validate(binding["source_data_ref"]))
    )
    rows = binding["evaluated_rows"]
    assert len(rows) == len(pairs["y_true"]) == 100
    for outcome, row in zip(pairs["y_true"], rows, strict=True):
        index = row["source_row_index"]
        assert outcome == source["dependent"][index]
        assert row["entity_id"] == source["entity_ids"][index]
        assert row["observation_time_id"] == source["time_ids"][index]
        assert row["training_end_time_id"] < row["observation_time_id"]
        assert row["forecast_horizon"] == row["observation_time_id"] - row["training_end_time_id"]
    # The oracle reads fresh source rows and persisted interval endpoints, not
    # the producer's report, covered-array, or results accumulation loop.
    hits = sum(
        lo <= source["dependent"][row["source_row_index"]] <= hi
        for row, (lo, hi) in zip(rows, pairs["intervals"][0], strict=True)
    )
    counts = report.metadata["interval_coverage"]
    assert tuple(counts[key] for key in ("requested", "eligible", "observed")) == (100, 100, 100)
    assert report.curves["interval_coverage"][0].mean_observed == hits / 100
    assert report.metrics.ece == pytest.approx(abs(hits / 100 - 0.95))
    assert artifact["gate_eligible"] is False
    assert report.to_truthfulness_receipt().diagnostics["gate_eligible"] is False
    assert binding["source_authority_basis"] == "not_established"


def test_real_dispatch_reopens_all_three_summary_call_sites(tmp_path) -> None:
    pytest.importorskip("arch")
    store = FileSystemCAS(tmp_path / "cas")
    data = _panel()
    before = data.model_dump(mode="json")
    params = {**_params(), "artifact_store": store}
    result = MethodDispatcher(enable_runtime_selection=False).dispatch(
        method_class=NonstationaryGARCHEstimator,
        signature=NonstationaryGARCHEstimator.signature,
        state=data,
        params=params,
        seed=37,
    )
    refs = result.artifacts["artifact_refs"]
    assert any(role.startswith("calibration.segment.") for role in refs)
    assert "calibration.overall" in refs
    assert "calibration.scenario.pooled_stationary_garch" in refs
    for raw_ref in refs.values():
        _assert_fresh_source_and_pairs(store, ArtifactRef.model_validate(raw_ref))
    assert (
        result.output["result"].diagnostics["calibration"]["diagnostics_ref"]
        == refs["calibration.overall"]
    )
    assert data.model_dump(mode="json") == before
    assert params["artifact_store"] is store
    assert "artifact_store" not in result.output["result"].model_dump_json()


class _PanelGraphState(dict):
    """Synthetic native execution fixture, not a production input-binding claim."""

    def __init__(self, data: PanelData):
        super().__init__(data.model_dump(mode="python"))
        base = GlobalState.empty(n_agents=1, n_firms=1)
        self.agents = base.agents
        self.firms = base.firms


def test_native_graph_returns_refs_from_its_configured_cas(tmp_path) -> None:
    pytest.importorskip("arch")
    store = FileSystemCAS(tmp_path / "configured-cas")
    MethodRegistry.get_instance().register(NonstationaryGARCHEstimator)
    ir_ref = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="ir.trinity_bundle",
        media_type="application/json",
    )
    lowered = store.put_json(
        LoweredIR(ir_ref=ir_ref, mechanisms=[], constraints=[]),
        ArtifactWriteOptions(kind="foundry.lowered_ir", media_type="application/json"),
    )
    client_params = {**_params(), "artifact_store": "untrusted-client-store"}
    node = ProgramNode(
        node_id="calibration",
        node_kind="method",
        method_fqn=NonstationaryGARCHEstimator.signature.fqn,
        method_params=client_params,
    )
    graph = ProgramGraph(
        ir_ref=ir_ref,
        lowered_ir_ref=LoweredIRRef(artifact_id=lowered.artifact_id),
        nodes=[node],
        entrypoints=[node.node_id],
    )
    graph_ref = store.put_json(
        graph,
        ArtifactWriteOptions(kind="foundry.program_graph", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    plan = ExecPlan(
        program_ref=ProgramGraphRef(artifact_id=graph_ref.artifact_id), order=[node.node_id]
    )
    plan_ref = store.put_json(
        plan, ArtifactWriteOptions(kind="foundry.exec_plan", media_type="application/json")
    )
    state = _PanelGraphState(_panel())
    before = copy.deepcopy(dict(state))
    artifacts = execute_program_graph(
        store,
        program_ref=graph_ref,
        exec_plan_ref=plan_ref,
        base_state=state,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        seed=43,
    )
    assert artifacts.is_degraded is False
    assert any(role == "calibration:calibration.overall" for role, _ in artifacts.derived_artifacts)
    for role, ref in artifacts.derived_artifacts:
        assert role.startswith("calibration:calibration.")
        _assert_fresh_source_and_pairs(store, ref)
    public_refs = _build_standard_derived_refs(artifacts)
    assert {
        (item.role, item.ref.artifact_id) for item in public_refs if ":calibration." in item.role
    } == {(role, ref.artifact_id) for role, ref in artifacts.derived_artifacts}
    stored_graph = from_canonical_bytes(store.get_bytes(graph_ref))
    assert stored_graph["nodes"][0]["method_params"]["artifact_store"] == "untrusted-client-store"
    assert client_params["artifact_store"] == "untrusted-client-store"
    for name in ("dependent", "exog", "entity_ids", "time_ids"):
        np.testing.assert_array_equal(state[name], before[name])
    assert "artifact_store" not in state
    assert from_canonical_bytes(store.get_bytes(artifacts.state_delta_ref))["ops"] == []


def test_method_without_store_remains_descriptive_and_has_no_persisted_refs() -> None:
    pytest.importorskip("arch")
    result = MethodDispatcher(enable_runtime_selection=False).dispatch(
        method_class=NonstationaryGARCHEstimator,
        signature=NonstationaryGARCHEstimator.signature,
        state=_panel(),
        params={**_params(), "run_policy_benchmark": False},
        seed=37,
    )
    calibration = result.output["result"].diagnostics["calibration"]
    assert calibration["diagnostics_ref"] is None
    assert calibration["persistence_status"] == "store_missing"
    assert calibration["gate_eligible"] is False
    assert result.artifacts["artifact_refs"] == {}
