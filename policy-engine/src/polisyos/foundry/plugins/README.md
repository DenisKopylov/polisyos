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
- [training_adapter.py](training_adapter.py) for the bounded Economics bridge to
  the native agent-sim trainer.

- [composite.py](composite.py) for cross-domain state and executor wiring.
- [economics/plugin.py](economics/plugin.py) for the built-in reference plugin.
- [economics/baselines.py](economics/baselines.py) for the retained
  `GlobalState` normalized-income/budget objective. Its legacy `policy_loss_fn`
  aliases remain compatibility entrypoints.
- [cli.py](cli.py) for local list/run/train/analyze command entrypoints.

## Economic Profiles And Compatibility

The execution kernels and the domain plugin implement distinct baseline
models. A shared class name or registry entry does not establish substitution
compatibility (E02 findings LA-003, LA-004 and LA-035).

| Contract | Execution baseline | Economics domain plugin |
| --- | --- | --- |
| State and output ABI | `foundry.contracts.state.GlobalState`; `emit_patches(state, key, target_mask=...)` returns a `PatchMap` and next key | `economics.state.EconomicState`; `apply(state, rng_key=...)` returns a state |
| Tax base and effect | `IncomeTax`: flat rate on `reported_income`; subtracts from `income`, credits `government.balance` | `TaxationMechanism`: progressive brackets on `income`, policy multiplier; subtracts from `wealth`, leaves `income` unchanged |
| Transfer and budget | `TaxSubsidy`: fraction of current income; credits income and debits government balance by the same total | `TransferMechanism`: policy/aggregate-income and unemployment inputs, optional wealth means test; credits wealth; state has no government-balance field |
| Labor law | Each call resamples employment at a fixed threshold and selects a firm uniformly; income is firm wage offer times skill | Finding/separation transitions depend on previous employment and skill; wage shocks, growth and a minimum wage floor determine income |
| Mask and firm accounting | Active and target masks preserve unselected households; active incumbents count towards firm labor counts | Domain mechanisms use their own active masks; no employer IDs, firm labor counts or `target_mask` ABI |
| Randomness | Fiscal keys are unchanged; labor splits into independent employment, firm and next keys | Labor accepts a key or derives one from `time_step`; `apply` does not return a progressed key |
| Time and units | Kernels do not advance `GlobalState.step`; currency and wage periods are not encoded in these state fields | Individual mechanisms do not advance `EconomicState.time_step`; wage floor uses `minimum_wage * 2000`, hours use `40`, and savings uses interest `/12`. These conventions do not establish a common timestep or currency |

The native execution consumer chain is a Trinity-compiled plan, the canonical
`foundry.execute.mechanisms` kernel, persisted `StateDelta`, and the Foundry
patch consumer and snapshot reader. The registered
`mechanism.runtime.*@1.0.0` adapter exposes separate diagnostic
`result.patches` JSON: its list deltas are not directly compatible with
`apply_patch_map`, and the program-graph method consumer expects top-level
`patch_records`. An adapter invocation is therefore not a consumed-state
witness; this bridge remains unestablished. The plugin consumer selects its
separate mechanisms through `EconomicsPlugin.get_mechanisms()` and domain
orchestration. `DomainPlugin` lifecycle/rewards/objectives/observations are
not the `FoundryMethod` ABI; changing an entry-point group requires an
explicit bridge, not a class rename.

`normalized_income_budget_loss` retains
`-mean(income) / max(mean(abs(income)), 1)` plus ten times the squared normalized
budget shortfall. For nonnegative income with mean at least one its income
term is constant `-1`, with zero local income gradient. It is an explicitly
named compatibility baseline, not an income-level maximizer or a substitute
for the `EconomicState` GDP/welfare objectives. Nonfinite income, balance or
budget threshold yields infinity through the native numerical guard.

The small native witnesses in `tests/unit/remediation/test_fry_03.py` exercise
registered adapter JSON effects and the incompatible-consumer negative,
active/target masks, independently expected
fiscal and labor accounting, compiled plan replay and persisted snapshot
readback. `test_eco_01.py` protects the distinct domain-plugin tax consumer and
analytic baseline derivatives. These synthetic fixtures do not establish
calibration, real-data applicability, production optimizer use, or retirement
compatibility. LA-004 and LA-035 retain the principal decision about profile,
objective and caller migration; no new economic law or authority is inferred.

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
