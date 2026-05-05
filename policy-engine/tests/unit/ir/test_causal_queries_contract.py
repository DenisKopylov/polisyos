from __future__ import annotations

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal_queries import (
    CausalQuery,
    CausalQueryResult,
    InterventionSpec,
    InterventionType,
    QueryType,
    load_causal_query_result,
    persist_causal_query_result,
)
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintySource,
)
from polisyos.ir.refs import CausalQueryResultRef


def test_intervention_spec_accepts_supported_variants() -> None:
    atomic = InterventionSpec(type=InterventionType.ATOMIC, value=1.0)
    shifted = InterventionSpec(type=InterventionType.SHIFTED, shift=0.1)
    truncated = InterventionSpec(type=InterventionType.TRUNCATED, bounds=(0.0, 1.0))
    stochastic = InterventionSpec(
        type=InterventionType.STOCHASTIC,
        distribution="truncnorm(0.1,0.05,0,0.2)",
    )

    assert atomic.value == 1.0
    assert shifted.shift == 0.1
    assert truncated.bounds == (0.0, 1.0)
    assert stochastic.distribution == "truncnorm(0.1,0.05,0,0.2)"


def test_intervention_spec_rejects_invalid_bounds_or_shift() -> None:
    with pytest.raises(ValueError, match="bounds are required"):
        InterventionSpec(type=InterventionType.TRUNCATED)
    with pytest.raises(ValueError, match="lower cannot exceed upper"):
        InterventionSpec(type=InterventionType.TRUNCATED, bounds=(1.0, 0.0))
    with pytest.raises(ValueError, match="shift is required"):
        InterventionSpec(type=InterventionType.SHIFTED)


def test_causal_query_validates_counterfactual_and_atomic_requirements() -> None:
    with pytest.raises(ValueError, match="counterfactual queries require non-empty condition"):
        CausalQuery(
            query_type=QueryType.COUNTERFACTUAL,
            treatment_variable="X",
            treatment_value=1.0,
            outcome_variable="Y",
            condition={},
        )

    with pytest.raises(ValueError, match="treatment_value is required for atomic interventions"):
        CausalQuery(
            query_type=QueryType.INTERVENTIONAL,
            treatment_variable="X",
            outcome_variable="Y",
        )

    with pytest.raises(ValueError, match="soft_intervention queries require intervention_spec"):
        CausalQuery(
            query_type=QueryType.SOFT_INTERVENTION,
            treatment_variable="X",
            outcome_variable="Y",
            treatment_value=0.1,
        )


def test_causal_query_result_to_uncertainty_envelope_is_phase11_compatible() -> None:
    query = CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="X",
        treatment_value=1.0,
        outcome_variable="Y",
        n_samples=200,
    )
    result = CausalQueryResult(
        query=query,
        result_mean=0.8,
        result_std=0.2,
        result_ci=(0.4, 1.2),
        result_distribution=[0.6, 0.9, 0.7],
        computation_time_seconds=0.01,
    )
    envelope = result.to_uncertainty_envelope()

    assert envelope.source is UncertaintySource.CAUSAL
    assert envelope.propagation_method is PropagationMethod.MONTE_CARLO
    assert envelope.interval_semantics is IntervalSemantics.CONFIDENCE_INTERVAL
    assert envelope.distribution_family is DistributionFamily.BOOTSTRAP
    assert envelope.sample_size == 200
    assert envelope.gate_eligible is True


def test_causal_query_result_artifact_roundtrip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    query = CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="X",
        treatment_value=1.0,
        outcome_variable="Y",
        n_samples=128,
    )
    result = CausalQueryResult(
        query=query,
        result_mean=1.0,
        result_std=0.1,
        result_ci=(0.8, 1.2),
        result_distribution=[0.9, 1.1, 1.0],
        computation_time_seconds=0.1,
    )

    ref = persist_causal_query_result(store, result)
    loaded = load_causal_query_result(store, ref)

    assert isinstance(ref, CausalQueryResultRef)
    assert ref.kind == "ir.causal_query_result"
    assert loaded == result
