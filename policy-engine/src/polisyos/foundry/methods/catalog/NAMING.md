# Foundry V2 Naming Spec

## Канонический идентификатор

Foundry V2 использует naming contract:

`domain.family.variant@semver`

Где:

- `domain` — верхний предметный namespace: `causal`, `econometrics`, `optimization`, `simulation`, `survey`, `distributional`, `forecasting`, `validation`, `sensitivity`, `bayesian`, `spatial` и т.д.
- `family` — устойчивое семейство методов внутри домена.
- `variant` — конкретный estimator/runtime variant.
- `semver` — версия ABI.

На уровне `MethodSignature` это означает:

- `namespace == "<domain>.<family>"`
- `name == "<variant>"`
- `family == "<domain>.<family>"`
- `variant == "<variant>"`

## Примеры

- `optimization.linear.resource_lp@1.0.0`
- `econometrics.panel.fixed_effects@1.0.0`
- `simulation.compartmental.seir@1.0.0`
- `bayesian.sampling.nuts@1.0.0`
- `spatial.accessibility.two_step_fca@1.0.0`

## Правила

- Не используй aggregate names вроде `panel_data`, `time_series`, `difference_in_differences`, если внутри скрываются разные ABI-семейства.
- Не дублируй семейство в variant имени.
- Не используй legacy aliases как канонический FQN.
- Не кодируй backend в FQN, если это не меняет ABI family.

## Когда повышать версию

- `major`: меняется ABI, slot surface, canonical semantics или contract fields.
- `minor`: расширяется совместимый diagnostics/output metadata.
- `patch`: внутренние багфиксы и стабильные улучшения без изменения ABI.
