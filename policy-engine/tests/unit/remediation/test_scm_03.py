"""SCM-03 witnesses for active query planning and stochastic-law fidelity."""

from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.causal import gcm_query as gcm_query_module
from polisyos.foundry.methods.catalog.causal.gcm_query import GCMQuery
from polisyos.foundry.methods.catalog.causal.protocols import SCMQueryData
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
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
        source=MechanismSource.DEFAULT,
    )


def _scm(
    *,
    nodes: list[str],
    edges: list[tuple[str, str]],
    mechanisms: list[NodeMechanism],
) -> StructuralCausalModelSpec:
    """Build a synthetic, explicitly declared SCM for the public query entrypoint."""
    return StructuralCausalModelSpec(
        graph=_graph(*edges, nodes=nodes),
        mechanisms=mechanisms,
        fitted=True,
        fit_method="manual",
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


def test_manual_query_revalidates_partial_graph_and_normalizes_known_orientation() -> None:
    """Unresolved marks refuse; equivalent known direction keeps its actual effect."""
    mechanisms = [
        _linear("Y", intercept=5.0),
        _linear("X", parents=["Y"], coefficients={"Y": 2.0}),
    ]
    query = CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="Y",
        treatment_value=2.0,
        outcome_variable="X",
        n_samples=8,
    )
    reverse = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.TAIL)],
    )
    forward = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="Y", dst="X")],
    )
    unresolved = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="Y", dst="X", mark_src=EdgeMark.CIRCLE)],
    )
    for graph in (reverse, forward):
        before = graph.model_dump(mode="json")
        scm = StructuralCausalModelSpec(graph=graph, mechanisms=mechanisms, fit_method="manual")
        assert _run(scm, query)["query_result"].result_mean == pytest.approx(4.0)
        assert graph.model_dump(mode="json") == before
    scm = StructuralCausalModelSpec(graph=unresolved, mechanisms=mechanisms, fit_method="manual")
    with pytest.raises(ValueError, match=r"partial|projection|profile|orientation"):
        _run(scm, query)


def test_manual_query_rejects_repeated_mechanism_parent() -> None:
    """A repeated parent would otherwise multiply its declared effect twice."""
    scm = _scm(
        nodes=["X", "Y"],
        edges=[("X", "Y")],
        mechanisms=[
            _linear("X"),
            _linear("Y", parents=["X", "X"], coefficients={"X": 1.0}),
        ],
    )
    with pytest.raises(ValueError, match="mechanism parents do not match"):
        _run(scm, _interventional_query(treatment_value=2.0))


def test_manual_static_query_refuses_temporal_and_unavailable_latent_mechanisms() -> None:
    """A static sampler must not ignore time or invent projected latent laws."""
    temporal = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y", lag=1)],
    )
    confounded = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW)],
    )
    mechanisms = [_linear("X"), _linear("Y", parents=["X"], coefficients={"X": 1.0})]
    for graph, reason in ((temporal, "temporal"), (confounded, "latent mechanisms")):
        scm = StructuralCausalModelSpec(graph=graph, mechanisms=mechanisms, fit_method="manual")
        with pytest.raises(ValueError, match=reason):
            _run(scm, _interventional_query(treatment_value=2.0))


def test_manual_query_rejects_cycle_and_stale_or_forged_disposition() -> None:
    """The query rechecks the source even if a caller retained a stale typed instance."""
    from polisyos.ir.analytics.causal_graph import (
        GraphProjectionStatus,
        graph_projection_disposition,
    )

    with pytest.raises(ValueError, match="DAG must be acyclic"):
        _graph(("X", "Y"), ("Y", "X"), nodes=["X", "Y"])

    graph = _graph(("X", "Y"), nodes=["X", "Y"])
    forged_cycle = graph.model_copy(
        update={"edges": [CausalEdge(src="X", dst="Y"), CausalEdge(src="Y", dst="X")]}
    )
    with pytest.raises(ValueError, match="DAG must be acyclic"):
        StructuralCausalModelSpec(
            graph=forged_cycle,
            mechanisms=[
                _linear("X", parents=["Y"], coefficients={"Y": 1.0}),
                _linear("Y", parents=["X"], coefficients={"X": 1.0}),
            ],
            fit_method="manual",
        )
    disposition = graph_projection_disposition(graph, graph, status=GraphProjectionStatus.IDENTITY)
    valid = StructuralCausalModelSpec(
        graph=graph,
        source_graph=graph,
        graph_projection=disposition,
        mechanisms=[_linear("X"), _linear("Y", parents=["X"], coefficients={"X": 1.0})],
        fit_method="manual",
    )
    assert _run(valid, _interventional_query(treatment_value=2.0))["query_result"].result_mean == 2
    stale_source = graph.model_copy(update={"metadata": {"revision": "different"}})
    forged_disposition = disposition.model_copy(update={"source_graph_sha256": "0" * 64})
    for changed, reason in (
        (
            valid.model_copy(update={"source_graph": stale_source}),
            "does not bind the current source graph",
        ),
        (
            valid.model_copy(update={"graph_projection": forged_disposition}),
            "canonical GraphProjectionDisposition validation failed",
        ),
    ):
        with pytest.raises(ValueError, match=reason):
            _run(changed, _interventional_query(treatment_value=2.0))


@pytest.mark.parametrize("condition", [{"Y": 4.0}, {"B": 1.0}, {"B": 1.0, "C": 2.0}])
def test_gaussian_posterior_replicas_do_not_depend_on_graph_storage_order(
    condition: dict[str, float],
) -> None:
    """The same joint posterior and seed map to the same named replicas."""
    first, reordered = _b224_reordered_active_models()
    query = CausalQuery(
        query_type=QueryType.COUNTERFACTUAL,
        treatment_variable="X",
        treatment_value=2.0,
        outcome_variable="Y",
        condition=condition,
        n_samples=512,
    )
    left = _run(first, query, seed=31)["query_result"].result_distribution
    right = _run(reordered, query, seed=31)["query_result"].result_distribution
    np.testing.assert_allclose(left, right, rtol=1e-12, atol=1e-12)


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


def test_active_and_explicit_full_trace_preserve_output_with_actual_call_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Twenty unrelated roots are sampled only for an explicit full trace."""
    extras = [f"Q{index:02d}" for index in range(20)]
    scm = _scm(
        nodes=["X", "Y", *extras],
        edges=[("X", "Y")],
        mechanisms=[
            _linear("X", intercept=99.0),
            _linear("Y", parents=["X"], intercept=1.0, coefficients={"X": 3.0}),
            *[_linear(name, noise_std=1.0) for name in extras],
        ],
    )
    query = _interventional_query(treatment_value=2.0, n_samples=10)
    graph_before = scm.graph.model_dump(mode="json")
    original = gcm_query_module._sample_node_value
    count = 0

    def observed_sampler(**kwargs: object) -> float:
        nonlocal count
        count += 1
        return original(**kwargs)

    monkeypatch.setattr(gcm_query_module, "_sample_node_value", observed_sampler)
    active_rng, full_rng, expected_rng = (np.random.default_rng(7) for _ in range(3))
    expected_rng.integers(0, 2**63, size=4, dtype=np.uint64)
    active, active_nodes = gcm_query_module._simulate_samples(
        scm_spec=scm, query=query, n_samples=10, rng=active_rng, warnings=[]
    )
    assert count == 10 and sum(len(values) for values in active_nodes.values()) == 20
    count = 0
    full, full_nodes = gcm_query_module._simulate_samples(
        scm_spec=scm,
        query=query,
        n_samples=10,
        rng=full_rng,
        warnings=[],
        include_all_nodes=True,
    )
    assert count == 210 and sum(len(values) for values in full_nodes.values()) == 220
    np.testing.assert_array_equal(active, full)
    np.testing.assert_array_equal(active, np.full(10, 7.0))
    expected_next = expected_rng.integers(0, 2**63)
    assert active_rng.integers(0, 2**63) == expected_next
    assert full_rng.integers(0, 2**63) == expected_next
    assert scm.graph.model_dump(mode="json") == graph_before


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


def _b224_reordered_active_models() -> tuple[StructuralCausalModelSpec, StructuralCausalModelSpec]:
    """Build one same-DAG profile whose independent active siblings swap order."""
    mechanisms = [
        _linear("R", noise_std=1.0),
        _linear("B", parents=["R"], coefficients={"R": 0.5}, noise_std=0.8),
        _linear("C", parents=["R"], coefficients={"R": -0.25}, noise_std=1.2),
        _linear("X", intercept=91.0, noise_std=8.0),
        _linear(
            "Y",
            parents=["B", "C", "X"],
            intercept=1.0,
            coefficients={"B": 2.0, "C": -3.0, "X": 1.0},
            noise_std=0.2,
        ),
    ]
    common_edges = [("B", "Y"), ("C", "Y"), ("X", "Y")]
    first = _scm(
        nodes=["R", "B", "C", "X", "Y"],
        edges=[("R", "B"), ("R", "C"), *common_edges],
        mechanisms=mechanisms,
    )
    reversed_siblings = _scm(
        nodes=["R", "B", "C", "X", "Y"],
        edges=[("R", "C"), ("R", "B"), *common_edges],
        mechanisms=mechanisms,
    )
    return first, reversed_siblings


def test_scm03_b224_reordered_active_ancestors_keep_per_node_draws() -> None:
    """Reordering real active siblings cannot remap their seeded random streams."""
    first, reversed_siblings = _b224_reordered_active_models()
    first_order = gcm_query_module._topological_order(first)
    reversed_order = gcm_query_module._topological_order(reversed_siblings)
    assert first_order.index("B") < first_order.index("C")
    assert reversed_order.index("C") < reversed_order.index("B")

    query = _interventional_query(treatment_value=2.0, n_samples=64)
    first_result = _run(first, query, seed=31)["query_result"].result_distribution
    reordered_result = _run(reversed_siblings, query, seed=31)["query_result"].result_distribution

    assert first_result == reordered_result


def test_explicit_generator_consumes_one_fixed_entropy_token() -> None:
    """Node ordering does not change either outcomes or the caller's RNG position."""
    first, reordered = _b224_reordered_active_models()
    query = _interventional_query(treatment_value=2.0, n_samples=64)
    first_rng, second_rng, expected_rng = (np.random.default_rng(31) for _ in range(3))
    expected_rng.integers(0, 2**63, size=4, dtype=np.uint64)
    first_result = GCMQuery.pure_step(
        SCMQueryData(scm_spec=first, query=query),
        {"__rng__": first_rng, "enable_dowhy_comparison": False},
    )["query_result"]
    second_result = GCMQuery.pure_step(
        SCMQueryData(scm_spec=reordered, query=query),
        {"__rng__": second_rng, "enable_dowhy_comparison": False},
    )["query_result"]
    assert first_result.result_distribution == second_result.result_distribution
    expected_next = expected_rng.integers(0, 2**63)
    assert first_rng.integers(0, 2**63) == expected_next
    assert second_rng.integers(0, 2**63) == expected_next
    assert second_rng.bit_generator.state == first_rng.bit_generator.state


def test_scm03_b224_reordered_draws_detect_shared_rng_mutant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A marker-preserving shared-RNG mutant makes the reordered witness diverge."""
    first, reversed_siblings = _b224_reordered_active_models()
    query = _interventional_query(treatment_value=2.0, n_samples=64)

    def run_with_shared_rng(model: StructuralCausalModelSpec) -> list[float]:
        shared_rng = np.random.default_rng(31)
        monkeypatch.setattr(
            gcm_query_module._LogicalStreamFactory,
            "generator",
            lambda _factory, *, namespace, label: shared_rng,
        )
        return _run(model, query, seed=31)["query_result"].result_distribution

    first_mutant = run_with_shared_rng(first)
    reordered_mutant = run_with_shared_rng(reversed_siblings)

    assert first_mutant != reordered_mutant


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


def test_truncated_normal_uses_one_law_parse_and_independent_tail_moments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A far-tail intervention follows its density, rather than clipped noise."""
    import math

    from scipy.integrate import quad

    scm = _scm(
        nodes=["X", "Y"],
        edges=[("X", "Y")],
        mechanisms=[_linear("X"), _linear("Y", parents=["X"], coefficients={"X": 1.0})],
    )
    query = _soft_query(
        InterventionSpec(type=InterventionType.STOCHASTIC, distribution="truncnorm(0,1,8,9)"),
        n_samples=2048,
    )
    original = gcm_query_module._resolve_stochastic_distribution
    calls = []

    def count_law(value: str):
        calls.append(value)
        return original(value)

    monkeypatch.setattr(gcm_query_module, "_resolve_stochastic_distribution", count_law)
    first = np.asarray(_run(scm, query, seed=23)["query_result"].result_distribution)
    assert calls == ["truncnorm(0,1,8,9)"]
    calls.clear()
    second = np.asarray(_run(scm, query, seed=23)["query_result"].result_distribution)
    assert calls == ["truncnorm(0,1,8,9)"]
    np.testing.assert_array_equal(first, second)
    assert np.all((first > 8.0) & (first < 9.0))

    density = lambda value: math.exp(-0.5 * (value * value - 64.0))  # noqa: E731
    normalizer = quad(density, 8.0, 9.0)[0]
    mean = quad(lambda value: value * density(value), 8.0, 9.0)[0] / normalizer
    variance = quad(lambda value: (value - mean) ** 2 * density(value), 8.0, 9.0)[0] / normalizer
    fourth = quad(lambda value: (value - mean) ** 4 * density(value), 8.0, 9.0)[0] / normalizer
    assert np.mean(first) == pytest.approx(mean, abs=6.0 * math.sqrt(variance / len(first)))
    assert np.var(first) == pytest.approx(
        variance, abs=6.0 * math.sqrt((fourth - variance**2) / len(first))
    )
    degenerate = _run(
        scm,
        _soft_query(
            InterventionSpec(type=InterventionType.STOCHASTIC, distribution="truncnorm(0,1,8,8)"),
            n_samples=32,
        ),
        seed=23,
    )["query_result"].result_distribution
    clipped = _run(
        scm,
        _soft_query(
            InterventionSpec(type=InterventionType.TRUNCATED, bounds=(8.0, 9.0)), n_samples=32
        ),
        seed=23,
    )["query_result"].result_distribution
    assert degenerate == [8.0] * 32
    assert clipped == [8.0] * 32
