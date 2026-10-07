"""No-backend warm admission keeps rejection reasons and the admitted corpus.

Synthetic declared rows exercise the search owner intake contract. They appoint
neither a source issuer nor a production law, and assert no fitted GP property.
"""

import copy
import json

import pytest

from polisyos.scientist.methods.search.strategies.bayesian import (
    BayesianConfig,
    BayesianOptimizer,
)
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import ParameterBounds
from tests.unit.scientist.methods.search.strategies._continuation_fixture import rows


@pytest.mark.parametrize("invalid", [float("nan"), 10**400, True], ids=["nan", "overflow", "bool"])
def test_warm_admission_preserves_each_explicit_rejection_reason(invalid):
    space = SearchSpace([ParameterBounds("x")])
    basis = {
        "profile": "synthetic_scalar_gp.v1",
        "search_space_fingerprint": space.sobol_space_fingerprint(),
        "context_fingerprint": "synthetic/warm-admission-reports.v1",
        "metric": "cost",
        "unit": "fixture_cost",
        "direction": "minimize",
    }
    strategy = BayesianOptimizer(space, BayesianConfig(seed=31), numerical_basis=basis)
    admitted = rows(space, 1)[0]
    admitted.candidate_id = "warm-admitted"
    admitted.metadata["warm_start_compatibility"] = {
        "search_space_fingerprint": basis["search_space_fingerprint"],
        "input_transform_fingerprint": "Normalize[0,1]",
        "outcome_transform_fingerprint": "Standardize[m=1]",
        "noise_model_fingerprint": "GaussianLikelihood[inferred]",
        "objective_fingerprint": "scalar_score[minimize]",
        "context_fingerprint": basis["context_fingerprint"],
    }
    rejected = []
    for identity in ("invalid", "unbound", "coordinate", "basis"):
        row = copy.deepcopy(admitted)
        row.candidate_id = identity
        rejected.append(row)
    rejected[0].scalar_score = invalid
    rejected[1].provenance_ref = None
    rejected[2].params_normalized = (0.75,)
    rejected[3].metadata["warm_start_compatibility"]["context_fingerprint"] = "foreign/context"
    strategy.warm_start([admitted, *rejected])
    assert strategy.last_warm_start_report == [
        {"candidate_id": "invalid", "reason": "invalid_outcome"},
        {"candidate_id": "unbound", "reason": "missing_origin"},
        {"candidate_id": "coordinate", "reason": "physical_coordinate_mismatch"},
        {"candidate_id": "basis", "reason": "numerical_basis_mismatch"},
    ]
    assert [row.candidate_id for row in strategy._effective_training_corpus([])] == [
        "warm-admitted"
    ]
    assert strategy._model is None and strategy._fitted_train_X is None
    print(
        json.dumps(
            {
                "cell": "warm-admission-explicit-rejections",
                "rejected": strategy.last_warm_start_report,
                "admitted": [row.candidate_id for row in strategy._warm_evals],
                "fitting_occurred": False,
            }
        )
    )
