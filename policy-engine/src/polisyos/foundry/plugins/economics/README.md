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

The observable mapping is explicit:

| Profile axis | Native baseline kernel | Economics plugin |
| --- | --- | --- |
| State and return ABI | `GlobalState`, PatchMap plus progressed key | `EconomicState`, replacement state |
| Tax base and debit | `reported_income`, debit `income` | marginal brackets over `income`, debit `wealth` |
| Budget | equal and opposite `government.balance` patch | no government counteraccount |
| Target/population | active mask intersected with target mask | active mask; no native target-mask argument |
| Labor | per-call threshold resampling, uniform firm, employer IDs/counts | finding/separation transitions, wage shock, hours; no firms/employer IDs |
| Clock/units | supplied wage/income amounts for each kernel call | supplied income amount for each call; wage floor is `minimum_wage * 2000`; interest separately uses `/ 12` |
| Seed progression | fiscal key unchanged; labor returns third split key | supplied key drives three labor draws; omitted key uses domain clock |
| Execution clock | executor advances its global step | composite advances its global step; this profile retains the domain step |

This records actual supplied units and per-call laws. It does not admit an
unprovided calendar conversion or calibration. Matched flat-tax, uniform-transfer
and zero-job fixtures compare the declared overlapping observables; their full
states and distinct accounting/seed fields are still checked separately.
Progressive tax, means testing and positive-threshold versus zero-finding labor
provide deliberate unequal regimes. No model is retired or substituted.

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
use coefficient 0. The existing [numeric domain](../../../../../docs/reference/foundry/numeric-guardrails.md)
excludes negative values from classical Gini. Its single active-population
admission refuses negative or nonfinite resources before hard, soft or proxy
Gini is published, including JIT and executor scans. Inactive invalid padding
is excluded. Signed resource simulation laws are unchanged; callers must omit
Gini or use the distributional report API's existing unavailable (`None`)
metric. This numeric refusal does not admit economic evidence or policy authority.
Top/bottom shares and other aggregate equations retain their separate contracts.

Current-population Gini readers (objectives, critic observations, rewards,
training metrics, counterfactual analysis and the population simulation method)
measure current resources through the same exact owner. They do not treat a
valid old scalar as admission of a changed population. The plugin wealth plot
also admits current wealth before publishing a Gini title.

`DistributionAwareExecutor` intentionally exports its scheduled distribution
snapshot: `last_update_step` records the pre-transition refresh and
`update_frequency` controls later refreshes. These metrics, compact snapshots
and plotted history describe their captured population; they are not claims
about the current population after an intervening transition. The current
readers above recompute instead of modifying this dated snapshot contract.

The fiscal/labor distinction is the LA-004 model-profile criterion. Its finite
state/units/clock/base/seed/accounting witnesses do not depend on an unspecified
welfare preference. They preserve both executors and their state contracts.

Finite fixture checks:

```bash
PYTHONPATH=src:tools:. python -m pytest \
  tests/unit/foundry/agent_sim/test_gini_science.py \
  tests/unit/foundry/plugins/test_economic_profiles.py
```

These synthetic witnesses establish the declared equations and runtime paths.
They do not admit a real economic dataset, calibration, policy objective or
local production execution history.
