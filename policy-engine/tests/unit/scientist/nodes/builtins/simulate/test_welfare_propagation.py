from __future__ import annotations

from types import SimpleNamespace

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)
from polisyos.scientist.nodes.builtins.simulate.propagate_welfare import WelfareSampleDomainError
from polisyos.scientist.nodes.builtins.simulate.welfare_propagation import (
    _propagate_credible_interval,
    _resolve_requested_welfare_method,
)
from polisyos.scientist.nodes.builtins.simulate.welfare_types import _WelfareNodeFailure
from polisyos.scientist.orchestration.engine.state import ExperimentState


@pytest.mark.parametrize(
    ("params", "preferred", "expected"),
    [
        ({"credible_method": "mc", "method": "robust"}, "delta", "monte_carlo"),
        ({"method": "delta_method"}, "auto", "delta"),
        ({}, "robust", "robust_set"),
    ],
)
def test_requested_method_precedence_and_aliases_are_effective(
    params: dict[str, str], preferred: str, expected: str
) -> None:
    resolved = _resolve_requested_welfare_method(
        PropagationConfig(preferred_method=preferred), params
    )

    assert resolved == expected


@pytest.mark.parametrize("malformed", [None, " ", 42, ["delta"]])
def test_malformed_explicit_method_does_not_fall_back_to_valid_lower_priority_method(
    malformed,
) -> None:
    with pytest.raises(_WelfareNodeFailure) as failure:
        _resolve_requested_welfare_method(
            PropagationConfig(preferred_method="auto"),
            {"credible_method": malformed, "method": "delta"},
        )

    assert failure.value.error.code == "ERROR_INTERVAL_SEMANTICS_INVALID"


def test_unknown_configured_method_is_not_silently_selected_as_monte_carlo() -> None:
    with pytest.raises(_WelfareNodeFailure) as failure:
        _resolve_requested_welfare_method(
            PropagationConfig(preferred_method="future-method"),
            {},
        )

    assert failure.value.error.code == "ERROR_INTERVAL_SEMANTICS_INVALID"


def test_unknown_explicit_method_is_refused_before_consumer_dispatch(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    state = ExperimentState(
        run_id="R_welfare_unknown_method",
        params={"propagation_config": PropagationConfig(mc_n_samples=100).model_dump(mode="json")},
    )
    envelope = UncertaintyEnvelope(
        point_estimate=1.0,
        confidence_interval=(0.0, 2.0),
        distribution_family=DistributionFamily.UNIFORM,
        source=UncertaintySource.BOOTSTRAP,
        propagation_method=PropagationMethod.MONTE_CARLO,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
    )
    dependence_context = SimpleNamespace(
        correlation_matrix=None,
        parameter_order=(),
        strategy="independent_marginals",
    )

    with pytest.raises(_WelfareNodeFailure) as failure:
        _propagate_credible_interval(
            SimpleNamespace(store=store),
            state,
            welfare_params={"credible_method": "future-method", "method": "delta"},
            context=SimpleNamespace(
                dependence_context=dependence_context,
                dependence_structure_ref=None,
            ),
            simulation_fn=lambda **params: {
                "welfare": params["rate"],
                "welfare_pe": params["rate"],
                "welfare_ge": 0.0,
            },
            nominal_params={"rate": 1.0},
            input_envelopes={"rate": envelope},
            input_envelope_refs={},
            sample_domain_error_type=WelfareSampleDomainError,
            sample_param_draw=lambda *args, **kwargs: {"rate": 1.0},
        )

    assert failure.value.error.code == "ERROR_INTERVAL_SEMANTICS_INVALID"
