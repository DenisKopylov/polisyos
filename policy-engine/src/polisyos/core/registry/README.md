# Registry — registries и bundle artifacts

`core.registry` объединяет:
- in-memory registry primitives (`BaseRegistry`, `GenericRegistry`)
- сборку/загрузку CAS bundle (`core.registry_bundle`) для детерминированного runtime

## Состав

```text
registry/
├── base.py                    # BaseRegistry + duplicate lifecycle hooks
├── generic.py                 # GenericRegistry + secondary indices + snapshots
├── builder.py                 # build_registry_bundle(), build_default_registry_bundle()
├── builder_from_fragments.py  # compose из component IR fragments
└── loader.py                  # load_registry_bundle*() + materialized content
```

## Основные сценарии

1. Базовый bundle из default IR:
   `build_default_registry_bundle(store)`
2. Bundle из компонентов:
   `build_registry_bundle_from_components(...)` -> bundle ref + compose report (`core.registry_compose_report`)
3. Загрузка в runtime:
   `load_registry_bundle_content(store, ref)` -> typed registries

## Что входит в bundle

Обязательные реестры:
- `slot`, `merge`, `mechanism`, `constraint`

Опциональные:
- `selector_field`, `metric`, `units`, `trust`, `predicate`, `privacy`

## Интеграции

- `components`: source of `ComponentKind.IR_FRAGMENT`
- `artifacts`: CAS storage и typed refs
- `ir`: default registries + compose models
- `governance`/`foundry`/`scientist`/`runtime`: потребители runtime registries

## Публичный API

- primitives: `BaseRegistry`, `DuplicateDecision`, `GenericRegistry`, `GenericRegistrySnapshot`
- builders: `build_registry_bundle`, `build_default_registry_bundle`, `build_registry_bundle_from_components`, `FragmentPrecedencePolicy`
- loaders: `load_registry_bundle`, `load_registry_bundle_payload`, `load_registry_bundle_content`, `RegistryBundleContent`
