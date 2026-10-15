# Foundry V2 Naming Spec

## Canonical identifier

Foundry V2 uses this naming contract:

`domain.family.variant@semver`

Where:

- `domain` is the top-level subject namespace: `causal`, `econometrics`, `optimization`, `simulation`, `survey`, `distributional`, `forecasting`, `validation`, `sensitivity`, `bayesian`, `spatial`, and others.
- `family` is a stable method family within a domain.
- `variant` is a specific estimator/runtime variant.
- `semver` is the ABI version.

At the `MethodSignature` level, this means:

- `namespace == "<domain>.<family>"`
- `name == "<variant>"`
- `family == "<domain>.<family>"`
- `variant == "<variant>"`

## Examples

- `optimization.linear.resource_lp@1.0.0`
- `econometrics.panel.fixed_effects@1.0.0`
- `simulation.compartmental.seir@1.0.0`
- `bayesian.sampling.nuts@1.0.0`
- `spatial.accessibility.two_step_fca@1.0.0`

## Rules

- Do not use aggregate names such as `panel_data`, `time_series`, or `difference_in_differences` when they hide different ABI families.
- Do not repeat the family name in the variant name.
- Do not use legacy aliases as the canonical FQN.
- Do not encode the backend in the FQN unless it changes the ABI family.

## When to increment the version

- `major`: the ABI, slot surface, canonical semantics, or contract fields change.
- `minor`: compatible diagnostics/output metadata is extended.
- `patch`: internal bug fixes and stable improvements that do not change the ABI.
