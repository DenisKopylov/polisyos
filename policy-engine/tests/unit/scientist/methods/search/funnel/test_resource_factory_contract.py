"""The ordinary serialized state cannot carry a runtime resource owner object."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.engine.state import ExperimentState


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
