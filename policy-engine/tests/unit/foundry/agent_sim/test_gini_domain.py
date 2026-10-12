"""Active-population admission for classical Gini at real runtime consumers."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.foundry.agent_sim.distributions import (
    GiniPopulationProfile,
    active_gini_population_supported,
    compute_gini_hard,
    compute_gini_proxy,
    compute_gini_soft,
)
from polisyos.foundry.agent_sim.executor import PureExecutor
from polisyos.foundry.agent_sim.state import GlobalState as AgentSimState
from polisyos.foundry.agent_sim.state import compute_aggregates
from polisyos.foundry.agent_sim.wiring.executors import _compute_distribution_state
from polisyos.foundry.analysis.distributional import (
    build_distributional_report,
    build_income_quintile_breakdown,
)
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.plugins.composite import (
    CompositeExecutor,
    CompositeState,
    CompositeStateConfig,
    CrossDomainInteraction,
)
from polisyos.foundry.plugins.core import DomainConfig, PluginRegistry
from polisyos.foundry.plugins.economics import EconomicsPlugin, EconomicState


@pytest.mark.parametrize(
    "selector",
    [
        pytest.param(None, id="falsey-none"),
        pytest.param("false", id="truthy-string"),
    ],
)
def test_jit_training_config_rejects_malformed_track_selector(selector: object) -> None:
    """A present malformed bool cannot become the default wealth-only path."""

    from polisyos.foundry.agent_sim.jit_training import JITTrainingConfig

    with pytest.raises(TypeError, match="track_active_wealth must be a bool"):
        JITTrainingConfig(track_active_wealth=selector)


def test_jit_training_config_preserves_valid_selector_and_profile_contract() -> None:
    """Exact booleans retain legacy behavior and selected-profile requirements."""

    from polisyos.foundry.agent_sim.jit_training import JITTrainingConfig

    profile = GiniPopulationProfile.ECONOMICS_ACTIVE_WEALTH_INCOME_V1
    assert JITTrainingConfig(track_active_wealth=False).track_active_wealth is False
    assert JITTrainingConfig(track_active_wealth=True).track_active_wealth is True
    with pytest.raises(ValueError, match="requires track_active_wealth=True"):
        JITTrainingConfig(track_active_wealth=False, gini_population_profile=profile)
    selected = JITTrainingConfig(track_active_wealth=True, gini_population_profile=profile)
    assert selected.gini_population_profile is profile


@pytest.mark.parametrize(
    "entrypoint",
    ["train_actor_critic_jit", "train_actor_critic_with_artifact"],
)
@pytest.mark.parametrize(
    "selector,profile",
    [
        pytest.param(
            None,
            GiniPopulationProfile.ECONOMICS_ACTIVE_WEALTH_INCOME_V1,
            id="falsey-with-selected-profile",
        ),
        pytest.param("false", None, id="truthy-string-without-profile"),
    ],
)
def test_exported_training_entrypoints_reject_malformed_selector_before_setup(
    entrypoint: str,
    selector: object,
    profile: GiniPopulationProfile | None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject malformed selectors before trainer, logger, fingerprint, or artifact work."""

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.foundry import agent_sim
    from polisyos.foundry.agent_sim import jit_training as jit_training_module
    from polisyos.foundry.agent_sim import training as training_module
    from polisyos.foundry.agent_sim.training import TrainingConfig
    from polisyos.foundry.runtime.fingerprint import EnvironmentFingerprint

    calls: list[str] = []

    def unexpected(name: str) -> Callable[..., None]:
        def fail(*args: object, **kwargs: object) -> None:
            del args, kwargs
            calls.append(name)
            raise AssertionError(f"{name} ran before selector admission")

        return fail

    monkeypatch.setattr(jit_training_module, "create_jit_trainer", unexpected("trainer"))
    monkeypatch.setattr(training_module, "get_logger", unexpected("logger"))
    monkeypatch.setattr(
        EnvironmentFingerprint, "capture", staticmethod(unexpected("fingerprint"))
    )
    monkeypatch.setattr(training_module.jax.random, "PRNGKey", unexpected("prng"))

    config = TrainingConfig(gini_population_profile=profile)
    function = getattr(agent_sim, entrypoint)
    kwargs = {
        "make_executor": unexpected("executor"),
        "track_active_wealth": selector,
    }
    cas = None
    if entrypoint == "train_actor_critic_with_artifact":
        cas = FileSystemCAS(tmp_path / "malformed-selector-artifacts")
        kwargs.update(run_id="malformed-selector", cas=cas)
    else:
        kwargs["rng_key"] = object()

    with pytest.raises(TypeError, match="track_active_wealth must be a bool"):
        function(None, None, config, **kwargs)

    assert calls == []
    if cas is not None:
        assert not list(cas.root.rglob("*.blob"))
        assert not list(cas.root.rglob("*.manifest.json"))


@pytest.mark.parametrize(
    "selector,profile,expected",
    [
        pytest.param(False, None, False, id="legacy-disabled"),
        pytest.param(True, None, True, id="legacy-enabled"),
        pytest.param(
            False,
            GiniPopulationProfile.ECONOMICS_ACTIVE_WEALTH_INCOME_V1,
            True,
            id="profile-auto-enables-monitor",
        ),
        pytest.param(
            True,
            GiniPopulationProfile.ECONOMICS_ACTIVE_WEALTH_INCOME_V1,
            True,
            id="profile-explicitly-enabled",
        ),
    ],
)
def test_jit_training_entrypoint_preserves_valid_selector_semantics(
    selector: bool,
    profile: GiniPopulationProfile | None,
    expected: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The wrapper auto-enables only for a selected profile and retains bool inputs."""

    from polisyos.foundry import agent_sim
    from polisyos.foundry.agent_sim import jit_training as jit_training_module
    from polisyos.foundry.agent_sim.jit_training import JITTrainingConfig
    from polisyos.foundry.agent_sim.training import TrainingConfig

    captured: list[JITTrainingConfig] = []

    def factory(
        _actor: object,
        _make_executor: object,
        _initial_state: object,
        config: JITTrainingConfig,
    ) -> Callable[[object], tuple[object, dict[str, object]]]:
        captured.append(config)

        def run(_rng_key: object) -> tuple[object, dict[str, object]]:
            metrics: dict[str, object] = {}
            if config.track_active_wealth:
                metrics["active_wealth_validation"] = (
                    jit_training_module._ActiveWealthTrajectoryValidation(
                        initial_state_checked=True,
                        episodes_checked=int(config.n_episodes),
                        transitions_checked=int(config.n_episodes)
                        * int(config.steps_per_episode),
                        active_wealth_supported=True,
                    )
                )
            return object(), metrics

        return run

    monkeypatch.setattr(jit_training_module, "create_jit_trainer", factory)
    config = TrainingConfig(
        n_episodes=1,
        steps_per_episode=1,
        gini_population_profile=profile,
    )
    policy, metrics = agent_sim.train_actor_critic_jit(
        None,
        None,
        config,
        make_executor=lambda _actor: None,
        rng_key=object(),
        track_active_wealth=selector,
    )

    assert policy is not None
    assert metrics == {}
    assert len(captured) == 1
    assert captured[0].track_active_wealth is expected
    assert captured[0].gini_population_profile is profile


@pytest.mark.parametrize(
    "wealth,income,active,expected",
    [
        ([0.0, 10.0], [0.0, 20.0], [True, True], True),
        ([0.0, -1.0], [0.0, float("nan")], [True, False], True),
        ([0.0, 1.0], [0.0, -1.0], [True, True], False),
        ([0.0, 1.0], [0.0, float("nan")], [True, True], False),
        ([float("inf"), 1.0], [0.0, 1.0], [True, True], False),
    ],
)
def test_shared_gini_population_predicate_covers_all_active_resources(
    wealth, income, active, expected
) -> None:
    """Selected profile checks both resource vectors and ignores inactive padding."""

    supported = active_gini_population_supported(
        jnp.asarray(active, dtype=jnp.bool_),
        jnp.asarray(wealth, dtype=jnp.float32),
        jnp.asarray(income, dtype=jnp.float32),
    )
    assert bool(supported) is expected


def test_shared_gini_population_predicate_fails_closed_on_unsupported_array_schema() -> None:
    """Malformed masks and resources cannot be broadcast into a valid profile."""

    assert not bool(
        active_gini_population_supported(
            jnp.asarray([True, False]),
            jnp.asarray([1.0]),
            jnp.asarray([2.0, 3.0]),
        )
    )
    assert not bool(
        active_gini_population_supported(
            jnp.asarray([1, 0]),
            jnp.asarray([1.0, 2.0]),
            jnp.asarray([2.0, 3.0]),
        )
    )
    assert not bool(
        active_gini_population_supported(
            jnp.asarray([True, False]),
            jnp.asarray([1.0 + 2.0j, 2.0 + 3.0j]),
            jnp.asarray([2.0, 3.0]),
        )
    )
    assert not bool(
        active_gini_population_supported(
            jnp.asarray([True]),
            ["not-a-numeric-resource"],
            jnp.asarray([2.0]),
        )
    )


@pytest.mark.parametrize("function", [compute_gini_hard, compute_gini_soft, compute_gini_proxy])
@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
@pytest.mark.parametrize(
    "values", [[-2.0, 1.0], [-1.0, 2.0], [-1.0, 1.0], [np.nan, 1.0], [np.inf, 1.0]]
)
def test_classical_gini_refuses_invalid_active_population(function, compiled, values) -> None:
    evaluate = jax.jit(function) if compiled else function
    with pytest.raises(
        (RuntimeError, ValueError), match="classical Gini requires finite nonnegative active values"
    ):
        jax.block_until_ready(evaluate(jnp.asarray(values), jnp.ones(2, dtype=jnp.bool_)))


@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
def test_admission_excludes_inactive_invalid_padding_and_preserves_exact_law(compiled) -> None:
    evaluate = jax.jit(compute_gini_hard) if compiled else compute_gini_hard
    with jax.enable_x64(True):
        for scale in (0.0, 1e-300, 1e-12, 1.0, 1e300):
            values = jnp.asarray([scale, -np.inf, 2 * scale, np.nan, 3 * scale])
            mask = jnp.asarray([True, False, True, False, True])
            result = evaluate(values, mask)
            assert result.dtype == jnp.float64
            assert float(result) == pytest.approx(0 if scale == 0 else 2 / 9, abs=1e-14)
        assert float(evaluate(jnp.asarray([np.nan, -np.inf]), jnp.zeros(2, dtype=bool))) == 0


@pytest.mark.parametrize("values", [[-2.0, 1.0], [-1.0, 2.0]])
@pytest.mark.parametrize(
    "consumer", ["aggregate", "executor", "native-distribution", "plugin-income", "plugin-wealth"]
)
def test_invalid_metric_is_refused_before_actual_consumer_publication(values, consumer) -> None:
    if consumer in {"aggregate", "executor"}:
        state = AgentSimState.empty(n_agents=2, seed=7)
        state = state.replace(agents=state.agents.replace(wealth=jnp.asarray(values)))
        if consumer == "aggregate":
            evaluate = lambda: jax.jit(lambda a: compute_aggregates(a, compute_gini=True))(
                state.agents
            )
        else:
            evaluate = lambda: PureExecutor([], aggregate_every=1, compute_gini=True).run(state, 2)
        # Signed resource simulation remains possible when Gini is not requested.
        unmeasured, _ = PureExecutor([], aggregate_every=1, compute_gini=False).run(state, 2)
        np.testing.assert_array_equal(unmeasured.agents.wealth, values)
    elif consumer == "native-distribution":
        state = GlobalState.empty(n_agents=2, n_firms=1)
        state = state.replace(agents=state.agents.replace(income=jnp.asarray(values)))
        evaluate = lambda: jax.jit(lambda s: _compute_distribution_state(s, n_quantiles=2))(state)
    else:
        state = EconomicState.empty(n_agents=2, seed=7)
        slot = "income" if consumer == "plugin-income" else "wealth"
        state = state.replace(agents=state.agents.replace(**{slot: jnp.asarray(values)}))
        objective = EconomicsPlugin().get_objectives()["gini"]
        # The genuine aggregate refresh must refuse before the objective sees a scalar.
        evaluate = lambda: objective.evaluate(jax.jit(EconomicState.update_aggregates)(state))
    with pytest.raises(
        (RuntimeError, ValueError), match="classical Gini requires finite nonnegative active values"
    ):
        jax.block_until_ready(evaluate())


@pytest.mark.parametrize("values", [[-2.0, 1.0], [-1.0, 2.0]])
def test_distributional_report_api_preserves_existing_typed_unavailable_metric(values) -> None:
    population = np.tile(np.asarray(values), 5)
    breakdown = build_income_quintile_breakdown(population, population)
    report = build_distributional_report(
        [breakdown], incomes_before=population, incomes_after=population
    )
    assert report.overall_gini_before is None
    assert report.overall_gini_after is None
    assert report.metadata["negative_values_present"] is True


@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
@pytest.mark.parametrize("values", [[-2.0, 1.0], [-1.0, 2.0]])
def test_registered_objective_refuses_current_signed_population_despite_valid_cached_metric(
    compiled, values
) -> None:
    state = EconomicState.empty(n_agents=2, seed=7)
    state = state.replace(agents=state.agents.replace(wealth=jnp.asarray(values)))
    assert np.isfinite(float(state.distributions.gini_wealth))
    evaluate = EconomicsPlugin().get_objectives()["gini"].evaluate
    if compiled:
        evaluate = jax.jit(evaluate)
    with pytest.raises(
        (RuntimeError, ValueError), match="classical Gini requires finite nonnegative"
    ):
        jax.block_until_ready(evaluate(state))


def test_composite_interaction_current_population_is_admitted_at_registered_objective() -> None:
    registry = PluginRegistry()
    registry.clear()
    plugin = EconomicsPlugin()
    registry.register(plugin)
    state = EconomicState.empty(n_agents=12, seed=7)
    state = state.replace(agents=state.agents.replace(wealth=jnp.asarray([2.0, 1.0] * 6)))
    interaction = CrossDomainInteraction(
        source_domain="economics",
        target_domain="economics",
        source_field="agents.wealth",
        target_field="agents.wealth",
        transform=lambda values: values * jnp.asarray([-1.0, 1.0] * 6),
    )
    config = CompositeStateConfig(
        domains={"economics": DomainConfig(n_agents=12, enabled_mechanisms=("taxation",))},
        interactions=[interaction],
    )
    composite = CompositeState(
        domain_states={"economics": state}, time_step=jnp.asarray(0), config=config
    )
    after = CompositeExecutor(["economics"], registry).step(composite, jax.random.PRNGKey(3))
    current = after.get_domain("economics")
    np.testing.assert_array_equal(current.agents.wealth, [-2.0, 1.0] * 6)
    assert np.isfinite(float(current.distributions.gini_wealth))
    with pytest.raises(
        (RuntimeError, ValueError), match="classical Gini requires finite nonnegative"
    ):
        jax.block_until_ready(plugin.get_objectives()["gini"].evaluate(current))
