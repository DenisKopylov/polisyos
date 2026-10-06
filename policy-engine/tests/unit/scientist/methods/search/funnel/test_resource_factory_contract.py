"""The ordinary serialized state cannot carry a runtime resource owner object."""

import logging
from decimal import Decimal

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    PolicyRuntimeEvaluationSafetyError,
)
from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
    PolicyBudgetExecutionContext,
    RunPolicyBlueprintRuntimeNode,
)
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema


def test_ordinary_experiment_state_rejects_resource_owner_in_json_params(tmp_path):
    owner = BudgetMiddleware(
        BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal(5))}),
        ledger=FileBudgetLedger(tmp_path / "budget.json"),
    )
    with pytest.raises(ValidationError):
        ExperimentState(run_id="run-1", params={"_resource_budget_middleware": owner})
    assert FileBudgetLedger(tmp_path / "budget.json").load().spent == {}


def test_ordinary_experiment_state_absent_owner_preserves_legacy_json_params():
    state = ExperimentState(run_id="run-1", params={"scientific_profile": "fixture"})
    assert state.params == {"scientific_profile": "fixture"}


@pytest.mark.parametrize("configured", [False, True])
def test_ordinary_blueprint_actual_backend_refuses_missing_admission_without_debit(
    tmp_path, configured
):
    """Resource context is not an evaluation admission or physical cost input.

    The actual backend runs its owner check. A positive downstream funnel run
    needs the appointed evaluation context/certificate/verifier input; that
    input is deliberately not replaced by a fixture bool or backend stub.
    """
    path = tmp_path / "ledger.json"
    owner = BudgetMiddleware(
        BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal(5))}),
        ledger=FileBudgetLedger(path),
    )
    store = FileSystemCAS(tmp_path / "artifacts")
    registry = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry, run_id="ordinary-node")
    args = {"store": store, "run": run, "logger": logging.getLogger("ordinary-node")}
    ctx = (
        PolicyBudgetExecutionContext(**args, budget_middleware=owner)
        if configured
        else ExecutionContext(**args)
    )
    candidate = PolicyCandidateSchema.from_trinity_bundle(
        TrinityBundle(
            problem_frame=ProblemFrame(problem_id="ordinary_problem", domain=ProblemDomain.FISCAL),
            policy_spec=PolicySpec(policy_id="ordinary_policy"),
            model_spec=ModelSpec(model_id="ordinary_model", data_snapshot_ref="sha256:" + "1" * 64),
        ),
        candidate_id="ordinary_candidate",
    )
    state = ExperimentState(
        run_id="ordinary-node",
        params={"policy_mode": True, "policy_candidate_schema": candidate.model_dump(mode="json")},
    )
    before = FileBudgetLedger(path).snapshot()
    with pytest.raises(PolicyRuntimeEvaluationSafetyError) as error:
        RunPolicyBlueprintRuntimeNode().execute(ctx, state)
    assert error.value.blocker_codes == ("polisyos.eval_safety.execution_context_missing@1.0.0",)
    assert FileBudgetLedger(path).snapshot() == before
    assert before.state.spent == {} and before.spend_receipts == {}
    assert "_funnel_outcome" not in state.params
    if configured:
        assert ctx.budget_middleware is owner
