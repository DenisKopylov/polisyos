from __future__ import annotations

import numpy as np
import pytest
from _helpers.artifacts import put_json_artifact
from _helpers.scientist_runtime import build_execution_context

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.causal import PanelObservationalData, ensure_causal_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.pdc import OperationClass
from polisyos.runtime.quality.workspace.foundry_consumption import FoundryMethodOutputConsumer
from polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation import (
    RunCausalEvaluationNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF,
    ARTIFACT_CAUSAL_METHOD_RESULT_REF,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _reset_foundry_method_singletons():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodDispatcher.reset_instance()
    MethodRegistry.reset_instance()


def test_phase2_estimate_consumes_real_foundry_method_output_with_measurement_authority(store) -> None:
    method_fqn = "causal.inference.synthetic_control@1.0.0"
    ensure_causal_methods_registered()
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
    ctx, _registry_bundle_ref = build_execution_context(store, run_id="R_gy_phase2_foundry")
    state = ExperimentState(
        run_id="R_gy_phase2_foundry",
        observational_data_ref=data_ref,
        causal_method_fqn=method_fqn,
        params={"random_seed": 42},
    )

    outcome = RunCausalEvaluationNode().execute(ctx, state)
    assert outcome.status == "ok"

    consumed = FoundryMethodOutputConsumer().consume_from_state(
        workspace_id="ws-phase2-foundry",
        operation_invocation_id="invoke-estimate",
        operation_class=OperationClass.ESTIMATE,
        state=outcome.state,
        measurement_root_ref=data_ref,
        constraint_store_ref="constraint-store-phase2",
    )

    assert consumed.record.dag_consumed_method_outputs_count > 0
    assert consumed.record.consumed_method_output_refs[0].artifact_id == str(
        outcome.state.artifacts_index[ARTIFACT_CAUSAL_METHOD_RESULT_REF].artifact_id
    )
    assert consumed.record.consumed_method_evidence_refs[0].artifact_id == str(
        outcome.state.artifacts_index[ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF].artifact_id
    )
    assert consumed.authority_boundary.evidence_kind == "measurement"
    assert consumed.authority_boundary.decision_grade == "descriptive_only"

    persisted_ref = FoundryMethodOutputConsumer().persist_consumption(
        store=store,
        consumption=consumed,
    )

    assert persisted_ref.artifact_type == "MethodOutputConsumptionRecord"
    assert persisted_ref.uri.startswith("cas://")


def test_foundry_consumer_rejects_untyped_synthetic_string_as_measurement_root(store) -> None:
    method_fqn = "causal.inference.synthetic_control@1.0.0"
    ensure_causal_methods_registered()
    data = PanelObservationalData(
        outcome=np.array(
            [
                [10, 11, 12, 13, 14, 18, 19, 20],
                [10, 11, 12, 13, 14, 15, 16, 17],
                [9, 10, 11, 12, 13, 14, 15, 16],
            ],
            dtype=float,
        ),
        treatment=np.array([1, 0, 0]),
        time_treatment=5,
    )
    data_ref = put_json_artifact(
        store,
        data.model_dump(mode="json"),
        kind="ir.observational_data",
        schema_version="1.0",
    )
    ctx, _registry_bundle_ref = build_execution_context(store, run_id="R_gy_phase2_foundry_string")
    state = ExperimentState(
        run_id="R_gy_phase2_foundry_string",
        observational_data_ref=data_ref,
        causal_method_fqn=method_fqn,
        params={"random_seed": 42},
    )
    outcome = RunCausalEvaluationNode().execute(ctx, state)
    assert outcome.status == "ok"

    with pytest.raises(ValueError, match="typed measurement ArtifactRef"):
        FoundryMethodOutputConsumer().consume_from_state(
            workspace_id="ws-phase2-foundry",
            operation_invocation_id="invoke-estimate-string",
            operation_class=OperationClass.ESTIMATE,
            state=outcome.state,
            measurement_root_ref="direct_synthetic_string",
            constraint_store_ref=None,
        )
