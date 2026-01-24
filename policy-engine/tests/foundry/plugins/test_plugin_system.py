import jax
import jax.numpy as jnp
import pytest

from polisyos.foundry.plugins.api import PolisySimulator
from polisyos.foundry.plugins.composite import (
    CompositeExecutor,
    CompositeState,
    CompositeStateConfig,
)
from polisyos.foundry.plugins.core import (
    DomainConfig,
    PluginCapability,
    PluginRegistry,
)
from polisyos.foundry.plugins.discovery import auto_register_plugins
from polisyos.foundry.plugins.economics import EconomicsPlugin


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
