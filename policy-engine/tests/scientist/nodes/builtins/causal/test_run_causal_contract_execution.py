from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.observation.causal_execution import load_causal_execution_bundle
from polisyos.ir.refs import CausalExecutionBundleRef
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.causal.run_causal_contract_execution import (
    RunCausalContractExecutionNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_BOUNDS_BUNDLE_REF,
    ARTIFACT_CAUSAL_EXECUTION_BUNDLE_REF,
    ARTIFACT_DYNAMIC_TREATMENT_REGIME_REF,
)


def _build_ctx(tmp_path, *, run_id: str) -> ExecutionContext:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id=run_id)
    return ExecutionContext(store=store, run=run, logger=logging.getLogger(f"test.{run_id}"))


def test_run_causal_contract_execution_node_persists_aggregate_and_primary_refs(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_c4b")
    state = ExperimentState(
        run_id="R_c4b",
        artifacts_index={},
        params={
            "bounds_estimation_tasks": [
                {
                    "task_id": "bounds_task",
                    "bounds_input": {
                        "outcome": [0.1, 0.2, 0.8, 0.9],
                        "treatment": [0.0, 0.0, 1.0, 1.0],
                        "instrument": [0.0, 1.0, 0.0, 1.0],
                    },
                    "bundle": {
                        "channels": [
                            {
                                "family": "household_distribution",
                                "bound_strategy": "iv_bounds",
                                "fallback_reason": "synthetic",
                            }
                        ]
                    },
                }
            ],
            "temporal_dtr_tasks": [
                {
                    "task_id": "temporal_task",
                    "sequence_id": "ua_seq",
                    "dynamic_intervention_id": "ua_dyn",
                    "steps": [
                        {"effective_date": "2022-01", "intervention_id": "launch"},
                        {"effective_date": "2022-06", "intervention_id": "expand"},
                        {"effective_date": "2023-01", "intervention_id": "taper"},
                    ],
                    "n_units": 24,
                    "params": {"n_bootstrap": 20},
                }
            ],
        },
    )

    outcome = RunCausalContractExecutionNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert ARTIFACT_CAUSAL_EXECUTION_BUNDLE_REF in outcome.state.artifacts_index
    assert ARTIFACT_BOUNDS_BUNDLE_REF in outcome.state.artifacts_index
    assert ARTIFACT_DYNAMIC_TREATMENT_REGIME_REF in outcome.state.artifacts_index

    bundle_ref = outcome.state.artifacts_index[ARTIFACT_CAUSAL_EXECUTION_BUNDLE_REF]
    bundle = load_causal_execution_bundle(
        ctx.store,
        CausalExecutionBundleRef.model_validate(bundle_ref.model_dump(mode="json")),
    )
    assert len(bundle.bounds_results) == 1
    assert len(bundle.temporal_results) == 1
    assert bundle.bounds_results[0].status == "ok"
    assert bundle.temporal_results[0].status == "ok"
    assert isinstance(
        outcome.state.artifacts_index[ARTIFACT_CAUSAL_EXECUTION_BUNDLE_REF], ArtifactRef
    )


def test_run_causal_contract_execution_task_assertion_is_not_swallowed(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_c4b_assert")
    state = ExperimentState(
        run_id="R_c4b_assert",
        params={"bounds_estimation_tasks": [{"task_id": "bounds_task"}]},
    )

    with patch(
        "polisyos.scientist.nodes.builtins.causal.run_causal_contract_execution.BoundsEstimationTask.model_validate",
        side_effect=AssertionError("task validator invariant"),
    ):
        with pytest.raises(AssertionError, match="task validator invariant"):
            RunCausalContractExecutionNode().execute(ctx, state)
