# Foundry V2 Migration Note

Foundry V2 завершает breaking cleanup старого method surface.

## Что удалено

- `bootstrap_registry` больше не существует ни в `polisyos.foundry.methods`, ни в `polisyos.foundry.methods.discovery`.
- Удалены deep shim-модули вида `polisyos.foundry.methods.<domain>.<module>`.
- Удалён deprecated shim `polisyos.foundry.methods.catalog.causal.scm`.
- Aggregate-wrapper FQN больше не регистрируются как first-class methods.

## Что использовать вместо этого

- Для bootstrap/runtime: `polisyos.core.components.bootstrap.build_components_index(...)` и `polisyos.foundry.methods.components.bridge.bootstrap_method_registry_from_components(...)`.
- Для публичного flat API:
  - `from polisyos.foundry.methods.causal import SyntheticControlMethod`
  - `from polisyos.foundry.methods.optimization import ResourceLP`
  - `from polisyos.foundry.methods.econometrics import PanelData`
- Для канонических модулей: `polisyos.foundry.methods.catalog.<domain>.<module>`.

## Типовые миграции

- `polisyos.foundry.methods.causal.protocols`
  -> `polisyos.foundry.methods.catalog.causal.protocols`
- `polisyos.foundry.methods.optimization.lp`
  -> `polisyos.foundry.methods.optimization`
- `polisyos.foundry.methods.econometrics.panel`
  -> `polisyos.foundry.methods.econometrics`
- `bootstrap_registry(...)`
  -> `build_components_index(...)` + `bootstrap_method_registry_from_components(...)`

## Новый инвариант

Каталог `methods/catalog/*` является единственным источником истины для:

- canonical FQN;
- registration;
- capability matrix;
- migration/authoring guidance.

Phase 1A удаляет пустые package-placeholders
`methods/{bayesian,causal,dependence,econometrics,microsim,ml,network,optimization,spatial}/`.
Flat domain API теперь реализован однофайловыми façade-модулями
`methods/<domain>.py`; они не являются packages, поэтому deep legacy imports
ниже `methods.<domain>` остаются неимпортируемыми.
