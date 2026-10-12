from decimal import Decimal

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.foundry.agent_sim.distributions import GiniPopulationProfile
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.plugins.api import PolisySimulator
from polisyos.foundry.plugins.composite import (
    CompositeExecutor,
    CompositeProfileRefusal,
    CompositeState,
    CompositeStateConfig,
)
from polisyos.foundry.plugins.core import (
    DomainConfig,
    PluginCapability,
    PluginRegistry,
)
from polisyos.foundry.plugins.discovery import auto_register_plugins
from polisyos.foundry.plugins.economics import EconomicsPlugin, EconomicState
from polisyos.foundry.plugins.training_adapter import (
    EconomicsTrainingAdapter,
    TrainingBridgeError,
    _native_to_composite,
)


class _WriteMalformedResource:
    """Write one malformed resource on active rows or inactive padding."""

    resource: str
    invalid_value: float
    write_active: bool

    def __init__(self, resource: str, invalid_value: float, write_active: bool) -> None:
        self.resource = resource
        self.invalid_value = invalid_value
        self.write_active = write_active

    @property
    def name(self) -> str:
        return "write_malformed_resource"

    def apply(self, state, **kwargs):
        del kwargs
        invalid_rows = state.agents.active if self.write_active else ~state.agents.active
        values = getattr(state.agents, self.resource)
        malformed = jnp.where(invalid_rows, self.invalid_value, values)
        return state.replace(agents=state.agents.replace(**{self.resource: malformed}))


class _UnownedProjectionAlias:
    """An alias whose projection field must not be read by the selected profile."""

    @property
    def agents(self):
        raise AttributeError("unowned projection alias must be rejected by type first")


class _UnownedNativeStateAlias:
    """A noncanonical native state whose fields must not be inspected."""

    @property
    def agents(self):
        raise AttributeError("unowned native state must be rejected by type first")


class _ReturnUnownedProjectionAlias:
    """Return an unsupported state shape from an Economics producer."""

    @property
    def name(self) -> str:
        return "return_unowned_projection_alias"

    def apply(self, state, **kwargs):
        del state, kwargs
        return _UnownedProjectionAlias()


class _ReturnMismatchedResourceShape:
    """Return canonical Economics state with a resource layout mismatch."""

    @property
    def name(self) -> str:
        return "return_mismatched_resource_shape"

    def apply(self, state, **kwargs):
        del kwargs
        agents = state.agents.replace(income=state.agents.income[:-1])
        return state.replace(agents=agents)


class _ChangeNonProfileLeafSchema:
    """Change one non-Gini leaf's dtype or shape at the producer boundary."""

    def __init__(self, change: str) -> None:
        self.change = change

    @property
    def name(self) -> str:
        return "change_non_profile_leaf_schema"

    def apply(self, state, **kwargs):
        del kwargs
        wage = state.agents.wage
        if self.change == "dtype":
            target_dtype = jnp.float32 if wage.dtype == jnp.float64 else jnp.float64
            wage = wage.astype(target_dtype)
        elif self.change == "shape":
            wage = wage[:-1]
        else:
            raise AssertionError(f"Unknown schema change: {self.change}")
        return state.replace(agents=state.agents.replace(wage=wage))


class _SetPopulationMetadata:
    """Return an Economics state with one declared population count value."""

    def __init__(self, field: str, value: int) -> None:
        self.field = field
        self.value = value

    @property
    def name(self) -> str:
        return "set_population_metadata"

    def apply(self, state, **kwargs):
        del kwargs
        return state.replace(**{self.field: self.value})


class _SetActiveIncome:
    """Set active income to one value for an ordered producer probe."""

    def __init__(self, value: float) -> None:
        self.value = value

    @property
    def name(self) -> str:
        return "set_active_income"

    def apply(self, state, **kwargs):
        del kwargs
        income = jnp.where(state.agents.active, self.value, state.agents.income)
        return state.replace(agents=state.agents.replace(income=income))


@pytest.fixture
def registry():
    reg = PluginRegistry()
    reg.clear()
    return reg


@pytest.fixture
def economics_plugin():
    return EconomicsPlugin()


class TestPluginRegistry:
    def test_register_plugin(self, registry, economics_plugin):
        registry.register(economics_plugin)
        assert "economics" in [p.name for p in registry.list_plugins()]

    def test_get_plugin(self, registry, economics_plugin):
        registry.register(economics_plugin)
        plugin = registry.get("economics")
        assert plugin.metadata.name == "economics"

    def test_duplicate_registration_fails(self, registry, economics_plugin):
        registry.register(economics_plugin)
        with pytest.raises(ValueError):
            registry.register(economics_plugin)

    def test_with_capability(self, registry, economics_plugin):
        registry.register(economics_plugin)
        plugins = registry.with_capability(PluginCapability.AGENTS)
        assert len(plugins) == 1


class TestEconomicsPlugin:
    def test_create_state(self, economics_plugin):
        config = DomainConfig(n_agents=100)
        state = economics_plugin.create_initial_state(config, jax.random.PRNGKey(0))

        assert state.n_agents == 100
        assert int(jnp.sum(state.agents.active)) == 100

    def test_get_mechanisms(self, economics_plugin):
        mechanisms = economics_plugin.get_mechanisms()
        assert len(mechanisms) > 0

        names = [m.name for m in mechanisms]
        assert "taxation" in names
        assert "labor_market" in names

    def test_get_objectives(self, economics_plugin):
        objectives = economics_plugin.get_objectives()

        assert "gdp" in objectives
        assert "gini" in objectives
        assert "social_welfare" in objectives


class TestCompositeState:
    def test_create_composite(self, registry, economics_plugin):
        registry.register(economics_plugin)

        config = CompositeStateConfig(
            domains={"economics": DomainConfig(n_agents=100)},
        )

        state = CompositeState.create(config, registry)
        assert "economics" in state.domain_states

    def test_update_domain(self, registry, economics_plugin):
        registry.register(economics_plugin)

        config = CompositeStateConfig(
            domains={"economics": DomainConfig(n_agents=100)},
        )
        state = CompositeState.create(config, registry)

        domain_state = state.get_domain("economics")
        new_agents = domain_state.agents.replace(wealth=domain_state.agents.wealth * 2)
        new_domain = domain_state.replace(agents=new_agents)

        new_state = state.update_domain("economics", new_domain)

        assert jnp.allclose(
            new_state.get_domain("economics").agents.wealth,
            state.get_domain("economics").agents.wealth * 2,
        )


class TestCompositeExecutor:
    def test_step(self, registry, economics_plugin):
        registry.register(economics_plugin)

        config = CompositeStateConfig(
            domains={"economics": DomainConfig(n_agents=100)},
        )
        state = CompositeState.create(config, registry)

        executor = CompositeExecutor(["economics"], registry)
        new_state = executor.step(state)

        assert int(new_state.time_step) == 1

    def test_run(self, registry, economics_plugin):
        registry.register(economics_plugin)

        config = CompositeStateConfig(
            domains={"economics": DomainConfig(n_agents=100)},
        )
        state = CompositeState.create(config, registry)

        executor = CompositeExecutor(["economics"], registry)
        final_state, trajectory = executor.run(state, n_steps=10)

        assert int(final_state.time_step) == 10
        assert len(trajectory) == 11

    @pytest.mark.parametrize(
        "resource,invalid_value",
        [("income", float("nan")), ("wealth", float("inf"))],
        ids=["active-income-nan", "active-wealth-overflow"],
    )
    @pytest.mark.parametrize(
        "write_active,expected_supported,expected_time",
        [(True, False, 0), (False, True, 1)],
        ids=["active-malformed-refuses", "inactive-padding-is-excluded"],
    )
    def test_selected_gini_profile_checks_produced_resources_before_aggregate(
        self,
        registry,
        economics_plugin,
        monkeypatch,
        resource,
        invalid_value,
        write_active,
        expected_supported,
        expected_time,
    ):
        """The source-owned gate stops before aggregation of invalid active output."""
        registry.register(economics_plugin)
        producer = _WriteMalformedResource(resource, invalid_value, write_active)
        monkeypatch.setattr(economics_plugin, "get_mechanisms", lambda: [producer])

        config = CompositeStateConfig(
            domains={"economics": DomainConfig(n_agents=10, max_agents=11)},
        )
        state = CompositeState.create(config, registry)
        executor = CompositeExecutor(
            ["economics"],
            registry,
            gini_population_profile=GiniPopulationProfile.ECONOMICS_ACTIVE_WEALTH_INCOME_V1,
        )

        after = executor.step(state, jax.random.PRNGKey(11))

        assert bool(after.gini_profile_supported) is expected_supported
        assert int(after.time_step) == expected_time
        observed = getattr(after.get_domain("economics").agents, resource)
        if write_active:
            assert jnp.isfinite(observed[0])
            assert observed[0] >= 0.0
        else:
            assert jnp.isclose(observed[10], invalid_value, equal_nan=True)

    @pytest.mark.parametrize(
        "field,configured_value",
        [("n_agents", 10), ("max_agents", 11)],
        ids=["configured-population-count", "configured-capacity"],
    )
    @pytest.mark.parametrize("carrier", ["jax-array", "numpy-scalar"])
    def test_selected_profile_accepts_jax_abstract_compatible_scalar_carrier(
        self,
        registry,
        economics_plugin,
        monkeypatch,
        field,
        configured_value,
        carrier,
    ):
        """Weak scalar carriers share the selected branch's actual JAX ABI."""
        registry.register(economics_plugin)
        monkeypatch.setattr(
            economics_plugin,
            "get_mechanisms",
            lambda: [_SetPopulationMetadata(field, configured_value)],
        )
        config = CompositeStateConfig(
            domains={"economics": DomainConfig(n_agents=10, max_agents=11)},
        )
        state = CompositeState.create(config, registry)
        domain = state.get_domain("economics")
        scalar = (
            jnp.asarray(configured_value, dtype=jax.typeof(configured_value).dtype)
            if carrier == "jax-array"
            else np.asarray(
                configured_value, dtype=jax.typeof(configured_value).dtype
            )[()]
        )
        state = state.update_domain(
            "economics",
            domain.replace(**{field: scalar}),
        )
        executor = CompositeExecutor(
            ["economics"],
            registry,
            gini_population_profile=GiniPopulationProfile.ECONOMICS_ACTIVE_WEALTH_INCOME_V1,
        )

        result = executor.step(state, jax.random.PRNGKey(16))

        assert bool(result.gini_profile_supported)
        assert int(result.time_step) == 1
        assert int(getattr(result.get_domain("economics"), field)) == configured_value

    @pytest.mark.parametrize(
        "unsupported_leaf",
        [Decimal("1.0"), complex(1.0, 0.0), 10**1000],
        ids=[
            "unabstractifiable-decimal",
            "complex-domain-value",
            "integer-abstract-overflow",
        ],
    )
    def test_selected_profile_refuses_unsupported_initial_dynamic_leaf(
        self,
        registry,
        economics_plugin,
        unsupported_leaf,
    ):
        """Unabstractifiable, overflowing, and complex leaves refuse before cond."""
        registry.register(economics_plugin)
        config = CompositeStateConfig(
            domains={"economics": DomainConfig(n_agents=10, max_agents=11)},
        )
        state = CompositeState.create(config, registry)
        domain = state.get_domain("economics")
        state = state.update_domain(
            "economics",
            domain.replace(
                agents=domain.agents.replace(wage=unsupported_leaf),
            ),
        )
        executor = CompositeExecutor(
            ["economics"],
            registry,
            gini_population_profile=GiniPopulationProfile.ECONOMICS_ACTIVE_WEALTH_INCOME_V1,
        )

        with pytest.raises(CompositeProfileRefusal) as refusal:
            executor.step(state, jax.random.PRNGKey(18))
        assert refusal.value.code == "composite_gini_profile_schema_unsupported"

    @pytest.mark.parametrize(
        "field,configured_value,producer_value",
        [("n_agents", 10, 11), ("max_agents", 11, 12)],
        ids=["count-change-refuses", "capacity-change-refuses"],
    )
    def test_selected_profile_preserves_configured_population_metadata(
        self,
        registry,
        economics_plugin,
        monkeypatch,
        field,
        configured_value,
        producer_value,
    ):
        """Abstract-compatible carrier changes cannot alter population geometry."""
        registry.register(economics_plugin)
        monkeypatch.setattr(
            economics_plugin,
            "get_mechanisms",
            lambda: [_SetPopulationMetadata(field, producer_value)],
        )
        config = CompositeStateConfig(
            domains={"economics": DomainConfig(n_agents=10, max_agents=11)},
        )
        state = CompositeState.create(config, registry)
        domain = state.get_domain("economics")
        state = state.update_domain(
            "economics",
            domain.replace(**{field: jnp.asarray(configured_value, dtype=jnp.int32)}),
        )
        executor = CompositeExecutor(
            ["economics"],
            registry,
            gini_population_profile=GiniPopulationProfile.ECONOMICS_ACTIVE_WEALTH_INCOME_V1,
        )

        result = executor.step(state, jax.random.PRNGKey(17))

        assert not bool(result.gini_profile_supported)
        assert int(result.time_step) == int(state.time_step)
        assert int(getattr(result.get_domain("economics"), field)) == configured_value
        with pytest.raises(CompositeProfileRefusal) as refusal:
            executor.run(state, n_steps=1, rng_key=jax.random.PRNGKey(17))
        assert refusal.value.code == "composite_gini_population_unsupported"

    @pytest.mark.parametrize(
        "field",
        ["n_agents", "max_agents"],
        ids=["population-count", "population-capacity"],
    )
    def test_selected_profile_refuses_unrepresentable_configured_population_metadata(
        self,
        registry,
        economics_plugin,
        field,
    ):
        """Configured integer geometry cannot wrap into a narrower state scalar."""
        registry.register(economics_plugin)
        config = CompositeStateConfig(
            domains={"economics": DomainConfig(n_agents=128, max_agents=128)},
        )
        state = CompositeState.create(config, registry)
        domain = state.get_domain("economics")
        state = state.update_domain(
            "economics",
            domain.replace(**{field: jnp.asarray(-128, dtype=jnp.int8)}),
        )
        executor = CompositeExecutor(
            ["economics"],
            registry,
            gini_population_profile=GiniPopulationProfile.ECONOMICS_ACTIVE_WEALTH_INCOME_V1,
        )

        result = executor.step(state, jax.random.PRNGKey(19))

        assert not bool(result.gini_profile_supported)
        assert int(result.time_step) == int(state.time_step)
        assert int(getattr(result.get_domain("economics"), field)) == -128
        with pytest.raises(CompositeProfileRefusal) as refusal:
            executor.run(state, n_steps=1, rng_key=jax.random.PRNGKey(19))
        assert refusal.value.code == "composite_gini_population_unsupported"

    def test_selected_gini_profile_rejects_initial_shape_before_tracing_gini(
        self,
        registry,
        economics_plugin,
        monkeypatch,
    ):
        """An invalid initial layout cannot enter the traced aggregate branch."""
        registry.register(economics_plugin)
        monkeypatch.setattr(
            EconomicState,
            "update_aggregates",
            lambda self: pytest.fail("unsupported initial layout reached Gini aggregation"),
        )
        config = CompositeStateConfig(
            domains={"economics": DomainConfig(n_agents=10, max_agents=11)},
        )
        state = CompositeState.create(config, registry)
        domain = state.get_domain("economics")
        malformed = domain.replace(
            agents=domain.agents.replace(income=domain.agents.income[:1]),
        )
        state = state.update_domain("economics", malformed)
        executor = CompositeExecutor(
            ["economics"],
            registry,
            gini_population_profile=GiniPopulationProfile.ECONOMICS_ACTIVE_WEALTH_INCOME_V1,
        )

        with pytest.raises(CompositeProfileRefusal) as refusal:
            executor.step(state, jax.random.PRNGKey(10))

        assert refusal.value.code == "composite_gini_profile_schema_unsupported"

    def test_selected_gini_profile_rejects_unowned_projection_type_before_gini(
        self,
        registry,
        economics_plugin,
    ):
        """Duck-typed state aliases cannot replace the selected projection owner."""
        registry.register(economics_plugin)
        config = CompositeStateConfig(
            domains={"economics": DomainConfig(n_agents=10, max_agents=11)},
        )
        state = CompositeState.create(config, registry)
        canonical_domain = state.get_domain("economics")
        alias = _UnownedProjectionAlias()
        aliased_state = state.update_domain("economics", alias)
        executor = CompositeExecutor(
            ["economics"],
            registry,
            gini_population_profile=GiniPopulationProfile.ECONOMICS_ACTIVE_WEALTH_INCOME_V1,
        )

        with pytest.raises(CompositeProfileRefusal) as refusal:
            executor.step(aliased_state, jax.random.PRNGKey(11))

        assert refusal.value.code == "composite_gini_profile_schema_unsupported"

    def test_selected_gini_profile_terminally_refuses_unowned_producer_type(
        self,
        registry,
        economics_plugin,
        monkeypatch,
    ):
        """A producer alias cannot raise from field access before typed refusal."""
        registry.register(economics_plugin)
        monkeypatch.setattr(
            economics_plugin,
            "get_mechanisms",
            lambda: [_ReturnUnownedProjectionAlias()],
        )
        config = CompositeStateConfig(
            domains={"economics": DomainConfig(n_agents=10, max_agents=11)},
        )
        state = CompositeState.create(config, registry)
        executor = CompositeExecutor(
            ["economics"],
            registry,
            gini_population_profile=GiniPopulationProfile.ECONOMICS_ACTIVE_WEALTH_INCOME_V1,
        )

        result = executor.step(state, jax.random.PRNGKey(12))

        assert not bool(result.gini_profile_supported)
        with pytest.raises(CompositeProfileRefusal) as refusal:
            executor.run(state, n_steps=1, rng_key=jax.random.PRNGKey(12))
        assert refusal.value.code == "composite_gini_population_unsupported"

    @pytest.mark.parametrize("change", ["dtype", "shape"], ids=["float-promotion", "shape-change"])
    def test_selected_gini_profile_refuses_any_nonprofile_leaf_schema_change(
        self,
        registry,
        economics_plugin,
        monkeypatch,
        change,
    ):
        """A non-Gini leaf cannot bypass the complete selected-state ABI gate."""
        with jax.enable_x64(True):
            registry.register(economics_plugin)
            monkeypatch.setattr(
                economics_plugin,
                "get_mechanisms",
                lambda: [_ChangeNonProfileLeafSchema(change)],
            )
            config = CompositeStateConfig(
                domains={"economics": DomainConfig(n_agents=10, max_agents=11)},
            )
            state = CompositeState.create(config, registry)
            initial_domain = state.get_domain("economics")
            assert jnp.all(initial_domain.agents.wealth >= 0.0)
            assert jnp.all(initial_domain.agents.income >= 0.0)
            executor = CompositeExecutor(
                ["economics"],
                registry,
                gini_population_profile=GiniPopulationProfile.ECONOMICS_ACTIVE_WEALTH_INCOME_V1,
            )

            result = executor.step(state, jax.random.PRNGKey(15))

            assert not bool(result.gini_profile_supported)
            observed = result.get_domain("economics")
            assert jnp.array_equal(observed.agents.wage, initial_domain.agents.wage)
            assert int(result.time_step) == int(state.time_step)
            with pytest.raises(CompositeProfileRefusal) as refusal:
                executor.run(state, n_steps=1, rng_key=jax.random.PRNGKey(15))
            assert refusal.value.code == "composite_gini_population_unsupported"

    def test_selected_gini_profile_rejects_produced_shape_before_tracing_gini(
        self,
        registry,
        economics_plugin,
        monkeypatch,
    ):
        """Static shape refusal precedes tracing either conditional's Gini branch."""
        registry.register(economics_plugin)
        monkeypatch.setattr(
            economics_plugin,
            "get_mechanisms",
            lambda: [_ReturnMismatchedResourceShape()],
        )
        config = CompositeStateConfig(
            domains={"economics": DomainConfig(n_agents=10, max_agents=11)},
        )
        state = CompositeState.create(config, registry)
        executor = CompositeExecutor(
            ["economics"],
            registry,
            gini_population_profile=GiniPopulationProfile.ECONOMICS_ACTIVE_WEALTH_INCOME_V1,
        )

        result = executor.step(state, jax.random.PRNGKey(13))

        assert not bool(result.gini_profile_supported)

    def test_selected_profile_terminally_stops_between_invalid_and_recovering_producers(
        self,
        registry,
        economics_plugin,
        monkeypatch,
    ):
        """A later valid producer cannot erase an invalid intermediate population."""
        registry.register(economics_plugin)
        monkeypatch.setattr(
            economics_plugin,
            "get_mechanisms",
            lambda: [_SetActiveIncome(float("nan")), _SetActiveIncome(1.0)],
        )
        config = CompositeStateConfig(
            domains={"economics": DomainConfig(n_agents=10, max_agents=11)},
        )
        state = CompositeState.create(config, registry)
        executor = CompositeExecutor(
            ["economics"],
            registry,
            gini_population_profile=GiniPopulationProfile.ECONOMICS_ACTIVE_WEALTH_INCOME_V1,
        )

        result = executor.step(state, jax.random.PRNGKey(14))

        assert not bool(result.gini_profile_supported)
        assert jnp.array_equal(
            result.get_domain("economics").agents.income,
            state.get_domain("economics").agents.income,
        )
        with pytest.raises(CompositeProfileRefusal) as refusal:
            executor.run(state, n_steps=1, rng_key=jax.random.PRNGKey(14))
        assert refusal.value.code == "composite_gini_population_unsupported"

    def test_native_projection_rejects_unowned_state_before_field_access(self):
        """The bridge refuses an unsupported native producer before Gini projection."""
        config = CompositeStateConfig(
            domains={"economics": DomainConfig(n_agents=1, max_agents=2)},
        )

        with pytest.raises(TrainingBridgeError) as refusal:
            _native_to_composite(
                _UnownedNativeStateAlias(),
                config=config,
                n_agents=1,
                max_agents=2,
                wage_growth_rate=0.02,
            )

        assert refusal.value.code == "training_native_state_schema_unsupported"

    def test_native_projection_rejects_mismatched_resources_before_gini(self):
        """Canonical native state with an invalid static layout cannot reach Gini."""
        native = GlobalState.empty(n_agents=1, max_agents=2, seed=0)
        malformed = native.replace(
            agents=native.agents.replace(income=native.agents.income[:1]),
        )
        config = CompositeStateConfig(
            domains={"economics": DomainConfig(n_agents=1, max_agents=2)},
        )

        with pytest.raises(TrainingBridgeError) as refusal:
            _native_to_composite(
                malformed,
                config=config,
                n_agents=1,
                max_agents=2,
                wage_growth_rate=0.02,
            )

        assert refusal.value.code == "training_native_state_schema_unsupported"

    def test_training_admission_rejects_noncanonical_composite_before_field_access(
        self,
        registry,
        economics_plugin,
    ):
        """Training admission cannot derive its profile from a proxy composite."""
        registry.register(economics_plugin)
        executor = CompositeExecutor(["economics"], registry)

        assessment = EconomicsTrainingAdapter.assess(
            object(),
            executor,
            require_supported_active_wealth=True,
        )

        assert assessment is not None
        assert assessment.code == "training_execution_adapter_missing"

    def test_selected_gini_profile_run_raises_before_attempting_later_steps(
        self,
        registry,
        economics_plugin,
        monkeypatch,
    ):
        """A later valid transition cannot hide the first unsupported producer output."""
        registry.register(economics_plugin)
        producer = _WriteMalformedResource("income", jnp.nan, True)
        monkeypatch.setattr(economics_plugin, "get_mechanisms", lambda: [producer])
        monkeypatch.setattr(EconomicState, "update_aggregates", lambda self: self)

        config = CompositeStateConfig(
            domains={"economics": DomainConfig(n_agents=10, max_agents=11)},
        )
        state = CompositeState.create(config, registry)
        executor = CompositeExecutor(
            ["economics"],
            registry,
            gini_population_profile=GiniPopulationProfile.ECONOMICS_ACTIVE_WEALTH_INCOME_V1,
        )

        with pytest.raises(CompositeProfileRefusal) as refusal:
            executor.run(state, n_steps=2, rng_key=jax.random.PRNGKey(11))

        assert refusal.value.code == "composite_gini_population_unsupported"


class TestPolisySimulator:
    def test_simple_simulation(self, registry, economics_plugin):
        registry.register(economics_plugin)

        sim = PolisySimulator(registry, auto_discover=False)
        sim.add_domain("economics", DomainConfig(n_agents=100))

        result = sim.run(n_steps=10)

        assert result.n_steps == 10
        assert result.final_state is not None

    def test_with_objective(self, registry, economics_plugin):
        registry.register(economics_plugin)

        sim = PolisySimulator(registry, auto_discover=False)
        sim.add_domain("economics", DomainConfig(n_agents=100))
        sim.set_objective("welfare", "economics", "social_welfare")

        result = sim.run(n_steps=10)

        assert "welfare" in result.objectives

    def test_set_policy(self, registry, economics_plugin):
        registry.register(economics_plugin)

        sim = PolisySimulator(registry, auto_discover=False)
        sim.add_domain("economics", DomainConfig(n_agents=100))
        sim.initialize()

        sim.set_policy("economics", {"tax_rate": 0.3})

        state = sim.get_state()
        domain_state = state.get_domain("economics")
        assert float(domain_state.policy.tax_rate) == pytest.approx(0.3)


class TestPluginDiscovery:
    def test_auto_register(self, registry):
        registered = auto_register_plugins(registry)
        assert "economics" in registered
