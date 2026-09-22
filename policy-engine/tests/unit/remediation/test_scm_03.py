"""SCM-03 witnesses for active query planning and stochastic-law fidelity."""

from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.causal import gcm_query as gcm_query_module
from polisyos.foundry.methods.catalog.causal.gcm_query import GCMQuery
from polisyos.foundry.methods.catalog.causal.protocols import SCMQueryData
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.causal_queries import (
    CausalQuery,
    InterventionSpec,
    InterventionType,
    QueryType,
)
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    MechanismSource,
    NodeMechanism,
    StructuralCausalModelSpec,
)


def _graph(*edges: tuple[str, str], nodes: list[str]) -> CausalGraphModel:
    """Build a small static DAG fixture for one SCM-03 witness."""
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=nodes,
        edges=[CausalEdge(src=src, dst=dst) for src, dst in edges],
    )


def _linear(
    variable: str,
    *,
    parents: list[str] | None = None,
    intercept: float = 0.0,
    coefficients: dict[str, float] | None = None,
    noise_std: float = 0.0,
) -> NodeMechanism:
    """Build a deterministic linear mechanism with explicit parameters."""
    return NodeMechanism(
        variable=variable,
        parents=parents or [],
        family=MechanismFamily.LINEAR,
        family_params={
            "intercept": intercept,
            "coefficients": coefficients or {},
            "noise_std": noise_std,
        },
        source=MechanismSource.DATA_FITTED,
    )


def _scm(
    *,
    nodes: list[str],
    edges: list[tuple[str, str]],
    mechanisms: list[NodeMechanism],
) -> StructuralCausalModelSpec:
    """Build a fitted SCM fixture accepted by the public query entrypoint."""
    return StructuralCausalModelSpec(
        graph=_graph(*edges, nodes=nodes),
        mechanisms=mechanisms,
        fitted=True,
        fit_method="gcm",
    )


def _run(
    scm_spec: StructuralCausalModelSpec,
    query: CausalQuery,
    *,
    seed: int = 17,
) -> dict[str, object]:
    """Run the real GCM query seam with external comparison disabled."""
    return GCMQuery.pure_step(
        SCMQueryData(scm_spec=scm_spec, query=query),
        params={"__seed__": seed, "enable_dowhy_comparison": False},
    )


def _interventional_query(
    *,
    treatment_value: float,
    n_samples: int = 64,
    intervention_spec: InterventionSpec | None = None,
) -> CausalQuery:
    """Build an atomic or explicitly stochastic interventional request."""
    return CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="X",
        treatment_value=treatment_value,
        outcome_variable="Y",
        intervention_spec=intervention_spec,
        n_samples=n_samples,
    )


def _soft_query(
    intervention_spec: InterventionSpec,
    *,
    n_samples: int = 64,
) -> CausalQuery:
    """Build a non-atomic treatment request for the sampling witnesses."""
    return CausalQuery(
        query_type=QueryType.SOFT_INTERVENTION,
        treatment_variable="X",
        outcome_variable="Y",
        intervention_spec=intervention_spec,
        n_samples=n_samples,
    )


def test_scm03_b224_perfect_do_skips_broken_natural_treatment_sampler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A perfect do(X=2) must not evaluate X's broken natural mechanism."""
    scm = _scm(
        nodes=["X", "Y"],
        edges=[("X", "Y")],
        mechanisms=[
            _linear("X", intercept=99.0),
            _linear("Y", parents=["X"], intercept=1.0, coefficients={"X": 3.0}),
        ],
    )
    original_sampler = gcm_query_module._sample_node_value

    def fail_for_treatment(**kwargs: object) -> float:
        mechanism = kwargs["mechanism"]
        if isinstance(mechanism, NodeMechanism) and mechanism.variable == "X":
            raise AssertionError("perfect do evaluated the replaced natural X mechanism")
        return original_sampler(**kwargs)

    monkeypatch.setattr(gcm_query_module, "_sample_node_value", fail_for_treatment)

    output = _run(scm, _interventional_query(treatment_value=2.0))

    assert output["query_result"].result_mean == pytest.approx(7.0)
    assert output["query_result"].result_distribution == pytest.approx([7.0] * 64)


def test_scm03_b224_active_plan_prunes_irrelevant_root_but_keeps_factual_ancestors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An irrelevant root is pruned while U->Z remains factual input to Y."""
    scm = _scm(
        nodes=["Q", "U", "Z", "X", "Y"],
        edges=[("U", "Z"), ("Z", "Y"), ("X", "Y")],
        mechanisms=[
            _linear("Q", intercept=123.0),
            _linear("U", intercept=5.0),
            _linear("Z", parents=["U"], coefficients={"U": 1.0}),
            _linear("X", intercept=91.0),
            _linear("Y", parents=["X", "Z"], coefficients={"X": 1.0, "Z": 1.0}),
        ],
    )
    original_sampler = gcm_query_module._sample_node_value

    def fail_for_irrelevant_root(**kwargs: object) -> float:
        mechanism = kwargs["mechanism"]
        if isinstance(mechanism, NodeMechanism) and mechanism.variable == "Q":
            raise AssertionError("active query plan sampled irrelevant root Q")
        return original_sampler(**kwargs)

    monkeypatch.setattr(gcm_query_module, "_sample_node_value", fail_for_irrelevant_root)

    output = _run(scm, _interventional_query(treatment_value=2.0))

    assert output["query_result"].result_mean == pytest.approx(7.0)
    assert output["query_result"].result_distribution == pytest.approx([7.0] * 64)


def test_scm03_b224_pruning_preserves_logical_draws_for_relevant_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Adding a noisy irrelevant root must not shift relevant seeded draws."""
    def make_scm(*, include_irrelevant_root: bool) -> StructuralCausalModelSpec:
        nodes = ["U", "Z", "X", "Y"]
        mechanisms = [
            _linear("U", noise_std=1.0),
            _linear("Z", parents=["U"], coefficients={"U": 1.0}, noise_std=0.75),
            _linear("X", intercept=91.0, noise_std=8.0),
            _linear(
                "Y",
                parents=["X", "Z"],
                coefficients={"X": 1.0, "Z": 1.0},
                noise_std=0.5,
            ),
        ]
        edges = [("U", "Z"), ("Z", "Y"), ("X", "Y")]
        if include_irrelevant_root:
            nodes.insert(0, "Q")
            mechanisms.insert(0, _linear("Q", intercept=13.0, noise_std=100.0))
        return _scm(nodes=nodes, edges=edges, mechanisms=mechanisms)

    original_sampler = gcm_query_module._sample_node_value

    def run_with_recording(
        scm: StructuralCausalModelSpec,
    ) -> tuple[dict[str, object], dict[str, list[float]]]:
        calls: dict[str, list[float]] = {node: [] for node in ("U", "Z", "Y")}

        def record_relevant_draws(**kwargs: object) -> float:
            value = original_sampler(**kwargs)
            mechanism = kwargs["mechanism"]
            if isinstance(mechanism, NodeMechanism) and mechanism.variable in calls:
                calls[mechanism.variable].append(value)
            return value

        monkeypatch.setattr(gcm_query_module, "_sample_node_value", record_relevant_draws)
        return _run(scm, _interventional_query(treatment_value=2.0, n_samples=32)), calls

    without_irrelevant, draws_without = run_with_recording(make_scm(include_irrelevant_root=False))
    with_irrelevant, draws_with = run_with_recording(make_scm(include_irrelevant_root=True))

    assert draws_with == draws_without
    assert with_irrelevant["query_result"].result_distribution == pytest.approx(
        without_irrelevant["query_result"].result_distribution
    )


def test_scm03_b224_shift_intervention_retains_natural_dependency() -> None:
    """A shift is applied to natural X=5, so X+2 remains 7 rather than atomic 2."""
    scm = _scm(
        nodes=["X", "Y"],
        edges=[("X", "Y")],
        mechanisms=[
            _linear("X", intercept=5.0),
            _linear("Y", parents=["X"], coefficients={"X": 1.0}),
        ],
    )

    output = _run(scm, _soft_query(InterventionSpec(type=InterventionType.SHIFTED, shift=2.0)))

    assert output["query_result"].result_mean == pytest.approx(7.0)
    assert output["query_result"].result_distribution == pytest.approx([7.0] * 64)


def test_scm03_b225_malformed_stochastic_law_does_not_fallback_to_atomic_do() -> None:
    """A malformed stochastic law must fail explicitly even with value=7 present."""
    scm = _scm(
        nodes=["X", "Y"],
        edges=[("X", "Y")],
        mechanisms=[
            _linear("X"),
            _linear("Y", parents=["X"], coefficients={"X": 1.0}),
        ],
    )
    malformed = InterventionSpec(
        type=InterventionType.STOCHASTIC,
        distribution="typo(0,1)",
    )

    with pytest.raises(ValueError, match="stochastic intervention"):
        _run(
            scm,
            _interventional_query(
                treatment_value=7.0,
                intervention_spec=malformed,
            ),
        )


@pytest.mark.parametrize("distribution", ["uniform(2,,3)", "normal(0,0)"])
def test_scm03_b225_invalid_stochastic_parameters_fail_closed(distribution: str) -> None:
    """Empty arguments and zero normal scale cannot become valid laws."""
    scm = _scm(
        nodes=["X", "Y"],
        edges=[("X", "Y")],
        mechanisms=[
            _linear("X"),
            _linear("Y", parents=["X"], coefficients={"X": 1.0}),
        ],
    )

    with pytest.raises(ValueError, match="stochastic intervention"):
        _run(
            scm,
            _soft_query(
                InterventionSpec(
                    type=InterventionType.STOCHASTIC,
                    distribution=distribution,
                )
            ),
        )


def test_scm03_b225_truncnorm_tail_stays_continuous_inside_bounds() -> None:
    """A tail truncnorm must produce interior conditional draws, not boundary atoms."""
    scm = _scm(
        nodes=["X", "Y"],
        edges=[("X", "Y")],
        mechanisms=[
            _linear("X"),
            _linear("Y", parents=["X"], coefficients={"X": 1.0}),
        ],
    )
    output = _run(
        scm,
        _soft_query(
            InterventionSpec(
                type=InterventionType.STOCHASTIC,
                distribution="truncnorm(0,1,8,9)",
            ),
            n_samples=64,
        ),
        seed=23,
    )

    values = np.asarray(output["query_result"].result_distribution, dtype=float)
    assert np.all((values > 8.0) & (values < 9.0))
    assert np.unique(values).size > 1


def test_scm03_b225_uniform_seed_is_reproducible_and_preserves_support() -> None:
    """Uniform(2,3) is a deterministic seeded positive control for stochastic planning."""
    scm = _scm(
        nodes=["X", "Y"],
        edges=[("X", "Y")],
        mechanisms=[
            _linear("X"),
            _linear("Y", parents=["X"], coefficients={"X": 1.0}),
        ],
    )
    query = _soft_query(
        InterventionSpec(
            type=InterventionType.STOCHASTIC,
            distribution="uniform(2,3)",
        ),
        n_samples=64,
    )

    first = _run(scm, query, seed=41)
    second = _run(scm, query, seed=41)
    first_values = np.asarray(first["query_result"].result_distribution, dtype=float)
    second_values = np.asarray(second["query_result"].result_distribution, dtype=float)

    assert np.array_equal(first_values, second_values)
    assert np.all((first_values >= 2.0) & (first_values < 3.0))
    assert np.unique(first_values).size > 1
