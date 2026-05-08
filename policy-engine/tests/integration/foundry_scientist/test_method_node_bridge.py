from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from _helpers.artifacts import put_json_artifact
from _helpers.scientist_runtime import build_execution_context
from polisyos.core.canon import from_canonical_bytes
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.causal import PanelObservationalData, ensure_causal_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation import (
    RunCausalEvaluationNode,
)
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_CAUSAL_REPORT_REF
from polisyos.scientist.orchestration.engine.state import ExperimentState

pytestmark = pytest.mark.integration

TESTS_ROOT = Path(__file__).resolve().parents[2]
METHOD_FQN = "causal.inference.synthetic_control@1.0.0"


@pytest.fixture(autouse=True)
def _reset_foundry_method_singletons():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodDispatcher.reset_instance()
    MethodRegistry.reset_instance()


def test_foundry_method_registry_entry_executes_through_scientist_node(store) -> None:
    golden = json.loads((TESTS_ROOT / "_golden" / "foundry" / "signature_baseline.json").read_text())
    assert golden["schema_version"] == "1.0"

    ensure_causal_methods_registered()
    assert MethodRegistry.get_instance().get(METHOD_FQN) is not None

    t0 = 6
    donor_1 = np.array([10, 11, 12, 13, 14, 15, 16, 17, 18, 19], dtype=float)
    donor_2 = np.array([9, 10, 11, 12, 13, 14, 15, 16, 17, 18], dtype=float)
    treated = donor_1.copy()
    treated[t0:] += 3.0
    data = PanelObservationalData(
        outcome=np.vstack([treated, donor_1, donor_2]),
        treatment=np.array([1, 0, 0]),
        time_treatment=t0,
    )
    data_ref = put_json_artifact(
        store,
        data.model_dump(mode="json"),
        kind="ir.observational_data",
        schema_version="1.0",
    )
    ctx, _registry_bundle_ref = build_execution_context(store, run_id="R_phase5_2_causal_bridge")
    state = ExperimentState(
        run_id="R_phase5_2_causal_bridge",
        observational_data_ref=data_ref,
        causal_method_fqn=METHOD_FQN,
        params={"random_seed": 42},
    )

    outcome = RunCausalEvaluationNode().execute(ctx, state)

    assert outcome.status == "ok"
    report_ref = outcome.state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF]
    report = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))
    assert report["status"] == "success"
    assert report["method"] == "synthetic_control"
    assert report["sample_size"] == data.outcome.size
