from __future__ import annotations

import numpy as np
import pytest

from polisyos.scientist.nodes.builtins.simulate.propagate_welfare import (
    WelfareSampleDomainError,
)
from polisyos.scientist.nodes.builtins.simulate.welfare_ge import (
    _invert_linear_operator,
    _invert_sampled_ge_operator,
)
from polisyos.scientist.nodes.builtins.simulate.welfare_types import _WelfareNodeFailure


def _sample_domain_error(message: str, *, predicate_id: str) -> WelfareSampleDomainError:
    return WelfareSampleDomainError(message, predicate_id=predicate_id)


def test_ge_inverse_is_correct_and_sampled_singularity_is_declared_domain() -> None:
    inverse, condition = _invert_linear_operator(
        np.asarray([[0.5]]),
        semantics="leontief_inverse",
        condition_threshold=10.0,
    )
    np.testing.assert_allclose(inverse, [[2.0]])
    assert condition == 1.0

    with pytest.raises(WelfareSampleDomainError) as failure:
        _invert_sampled_ge_operator(
            np.asarray([[1.0]]),
            condition_threshold=10.0,
            sample_domain_error_factory=_sample_domain_error,
        )

    assert failure.value.predicate_id == "welfare.ge_operator.condition_number_within_threshold"


def test_point_operator_ill_conditioning_fails_as_node_error() -> None:
    with pytest.raises(_WelfareNodeFailure) as failure:
        _invert_linear_operator(
            np.asarray([[1.0]]),
            semantics="leontief_inverse",
            condition_threshold=10.0,
        )

    assert failure.value.error.code == "ERROR_GE_OPERATOR_SINGULAR"
