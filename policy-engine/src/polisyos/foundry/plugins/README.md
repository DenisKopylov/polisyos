# Plugins (`polisyos.foundry.plugins`)

`polisyos.foundry.plugins` is the legacy domain-plugin layer on top of
`polisyos.foundry.agent_sim`: it packages mechanisms, rewards, objectives,
observations, and composite orchestration into reusable simulation domains.

- Last updated: 2026-05-06
- Sunset status: compatibility surface. New Foundry method extensions must use
  `polisyos.foundry.extensions` and the `polisyos.foundry_methods` entry-point
  group; `polisyos.plugins` remains only for existing domain-simulation plugins.

## Purpose

Use plugins when you want to assemble higher-level domain simulations rather
than operate directly on the low-level agent-sim runtime. This package owns the
legacy domain-plugin contract, discovery/registration path, composite execution, and the
`PolisySimulator` orchestration facade.

Do not use this package to publish Foundry methods. Method authors should
follow `src/polisyos/foundry/methods/AUTHORING.md` and the installable example
under `examples/extensions/foundry_method/`.

## Where to Start

- [core.py](core.py) for `DomainPlugin`, `PluginRegistry`, metadata, and domain
  config contracts.

- [discovery.py](discovery.py) for built-in and entry-point plugin discovery.
- [api.py](api.py) for `PolisySimulator`, simulation config, and high-level run
  / train / visualize flows.

- [composite.py](composite.py) for cross-domain state and executor wiring.
- [economics/plugin.py](economics/plugin.py) for the built-in reference plugin.
- [cli.py](cli.py) for local list/run/train/analyze command entrypoints.

## Public Entrypoints

| Entrypoint                | Description                                          |
| ------------------------- | ---------------------------------------------------- |
| `DomainPlugin`            | Base contract for a pluggable domain.                |
| `PluginRegistry`          | Registry for loaded plugins and metadata.            |
| `discover_plugins()`      | Finds built-in and entry-point plugins.              |
| `auto_register_plugins()` | Registers built-in plugins into a registry.          |
| `create_simple_plugin()`  | Helper for lightweight plugin scaffolding.           |
| `CompositeState`          | Combined state across multiple domains.              |
| `CompositeExecutor`       | Cross-domain executor for composite runs.            |
| `PolisySimulator`         | High-level run/train/orchestration facade.           |
| `SimulationConfig`        | Top-level configuration for multi-domain simulation. |

## Depends On / Depended On By

- Depends on: `polisyos.foundry.agent_sim`, `polisyos.foundry.contracts`, JAX,
  and built-in domain plugins such as `economics`.

- Depended on by: local plugin CLI workflows, plugin-system tests, and
  domain-specific simulation scenarios built on top of `PolisySimulator`.

## Common Commands

Smoke-tested on 2026-04-17:

```bash
uv run python -m polisyos.foundry.plugins.cli list --verbose

uv run python - <<'PY'
from polisyos.foundry.plugins import DomainConfig, PolisySimulator

sim = PolisySimulator(auto_discover=True)
sim.add_domain("economics", DomainConfig(n_agents=16))
result = sim.run(n_steps=2, seed=0)
print(result.n_steps)
print(int(result.final_state.time_step))
PY
```

## Test / Verification Commands

```bash
uv run pytest tests/unit/foundry/plugins/test_plugin_system.py -q
```

## Reference Docs

- [../agent_sim/README.md](../agent_sim/README.md)
- [docs/reference/foundry/agent-sim.md](../../../../docs/reference/foundry/agent-sim.md)
- [docs/reference/foundry/index.md](../../../../docs/reference/foundry/index.md)
- [../README.md](../README.md)
