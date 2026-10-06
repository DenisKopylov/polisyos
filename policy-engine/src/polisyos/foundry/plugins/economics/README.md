# Economics profiles

The domain plugin uses `EconomicState`. Native fiscal and labor execution uses
`polisyos.foundry.contracts.state.GlobalState` and emits a PatchMap consumed by
`polisyos.foundry.execute.executor.apply_patch_map`. These profiles share some
equations under explicit conversions; their identically named mechanisms do
not make them interchangeable.

| Quantity or law | Native execution | Economics plugin |
| --- | --- | --- |
| Tax base | `reported_income`, per execution step | `income`, using configured brackets and policy multiplier |
| Household tax debit | `agents.income` delta | `agents.wealth` debit; income unchanged |
| Government counteraccount | `government_balance` receives tax or pays subsidy | No government balance field |
| Subsidy/transfer | Rate times individual income, with active and target masks | Mean-income transfer plus unemployment benefit, optionally means tested |
| Labor | Resample employment and firm assignment; income is firm wage offer times skill | Job-finding/separation transitions, stochastic wage growth, minimum wage times 2000 and hours |
| Employment accounting | Employer IDs and firm labor counts in complete patches | Employment and hours in the returned economic state; no firm assignments |
| Randomness | Fiscal key unchanged; labor returns the third split key | Labor uses three draws from the supplied key, returns a state; absent key defaults to time step |

The units are those of the supplied fixture. The plugin's annualizing factor
2000 does not establish the native step's duration. A flat tax fixture with the
same one-period income base can match the numerical tax debit after an explicit
stock/flow account conversion. A uniform-income, non-means-tested transfer with
zero unemployment benefit can match a subsidy debit. Neither fixture supplies
the plugin's missing government counteraccount or proves whole-state/model
equivalence. Targeting the plugin fixture requires explicitly restricting its
active mask; its mechanism API has no native target-mask argument.

`baselines.normalized_income_budget_loss` preserves the historical
`GlobalState` normalized income/budget formula; the two `policy_loss_fn`
compatibility paths resolve to this same function. Nonnegative income whose
mean absolute value is at least 1 has income score -1 at any positive scale.
This is a named historical score, not a new welfare objective. `EconomicState`
wealth cannot be supplied as GlobalState income without a declared conversion.
Production optimizer callers and external serialized configurations require
their own admission before removing the compatibility paths.

The exact Gini owner is `agent_sim.distributions.compute_gini_hard`, consumed by
`EconomicState.update_aggregates`, the registered Gini objective and native
GlobalState distribution wiring. Native agent-sim `compute_aggregates` and
`PureExecutor` delegate to the same owner and exclude inactive padding from the
population. Its defining pairwise ratio is invariant to
positive changes in resource units. Empty and all-zero nonnegative populations
use coefficient 0. Nonconstant signed zero-total populations return NaN and are
outside this economic profile; negative wealth fails `EconomicState.validate`,
and the Gini objective preserves NaN. This is a numeric limitation, not an
authority-grade admission gate for arbitrary signed income. Approximate soft
and proxy statistics, top/bottom shares and other aggregate equations retain
their separate contracts.

Finite fixture checks:

```bash
PYTHONPATH=src:tools:. python -m pytest \
  tests/unit/foundry/agent_sim/test_gini_science.py \
  tests/unit/foundry/plugins/test_economic_profiles.py
```

These synthetic witnesses establish the declared equations and runtime paths.
They do not admit a real economic dataset, calibration, policy objective or
local production execution history.
