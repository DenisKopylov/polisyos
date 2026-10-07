# Historical normalized-income/budget baseline

`polisyos.foundry.plugins.economics.baselines.normalized_income_budget_loss`
owns the historical native `GlobalState` profile. Both
`polisyos.foundry.methods.loss.policy_loss_fn` and the corresponding internal
facade retain the identical callable. The relocation preserves the formula:

```text
-mean(income) / max(mean(abs(income)), 1)
+ 10 * (max(min_balance - government_balance, 0) / max(abs(min_balance), 1))**2
```

The default minimum balance is `-1000`. Inputs and calculation retain the
historical float32 profile. The population consists of every supplied income
entry; this baseline does not introduce an active-mask selection. Non-finite
inputs and non-finite computed losses produce positive infinity through the
existing public runtime numeric guard.

For nonnegative income whose mean is at least one, the income component is
`-1`, including after rescaling. Below that threshold it is linear in mean
income. Negative and mixed income retain the original sign and normalization.
These properties identify a preserved baseline; they do not specify a new
welfare or income-maximizing objective. The original LA035 acceptance concerns
equivalent relocation, supported callers, numeric guards, native state,
promised JIT/gradient behavior, and package import side effects. A new optimizer
or normative welfare choice is a separate change, not a prerequisite for this
unchanged profile. Historical receipts recording that prerequisite remain
historical evidence and do not define the current recommendation.

The original LA035 equivalent relocation is technically closed by the native
formula, population, guard, aliases, JIT/gradient, caller census and fresh-import
checks, with independent review. ROOT's current ledger decision and G's
acceptance remain separate. The 2026-10-06
`F/economics-continuation-20261006.json` receipt at Git ref `072d45a5` records the
prior hold literally; the 2026-10-07 COMMON supersedes its optimizer/normative
prerequisite for this unchanged relocation. A newly requested optimizer or
policy objective remains a future objective/version follow-up.

The maintained native aliases and numeric consumer tests use this exact
profile. A complete tracked source/configuration/FQN census accompanies the
handoff; dynamic external callers and production economic decisions are not
established by those synthetic checks. `EconomicState` GDP, wealth taxation,
and social-welfare objectives retain their different state and model contracts.
LA004 compares deliberately matched and divergent fiscal/labor regimes,
including state, units, timestep, tax base, budget, seeds and observable
outputs. It does not require a new Gini or welfare convention.

## Signed wealth at the Economics/PPO boundary

The built-in Economics training adapter invokes the native temporal actor,
then the registered plugin labor, taxation, transfer, and savings mechanisms.
With zero starting wealth, positive generated wages and zero transfers and
interest, the plugin's existing tax law can produce negative active wealth.
The producer and its RNG law remain unchanged.

Classical Gini has the existing finite, nonnegative active-population domain.
Requesting it through the plugin distribution refresh, the current metric
collector, or metric-enabled PPO raises the canonical domain error before a
coefficient or metric history is returned. A trajectory without a requested
Gini can retain signed wealth: an unused cached distribution may be eliminated
inside a JAX scan. That successful trajectory does not establish an admissible
Gini coefficient. Nonnegative active populations are admitted, and invalid
inactive padding is excluded. This bounded synthetic producer/consumer witness
does not assert that real training data are nonnegative or calibrated.
