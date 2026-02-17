# Registry — generic registries и CAS registry bundles

`core.registry` объединяет два слоя:

- in-memory thread-safe registries (`GenericRegistry`, `BaseRegistry`);
- сборку/загрузку registry bundles в CAS для runtime-переноса и воспроизводимости.

## Состав

```text
registry/
├── generic.py                 # GenericRegistry + secondary indices + snapshots
├── base.py                    # BaseRegistry + duplicate hooks + lifecycle hooks
├── builder.py                 # build_registry_bundle()/build_default_registry_bundle()
├── builder_from_fragments.py  # compose bundle из IR fragment components
├── loader.py                  # load_registry_bundle*() из CAS
└── __init__.py                # lazy exports
```

## Роль в системе

- Единый формат registry bundle (`core.registry_bundle`) как артефакт.
- Композиция registries из default IR + component fragments.
- Детерминированная загрузка registries из CAS для Foundry/Scientist/Runtime.

## Ключевые сценарии

1. Базовая сборка:
   `build_default_registry_bundle(store)` -> bundle artifact в CAS.
2. Сборка из компонентов:
   `build_registry_bundle_from_components(...)` с `ComponentRegistry`,
   precedence policy и compose report (`core.registry_compose_report`).
3. Загрузка:
   `load_registry_bundle_content(store, ref)` -> materialized registries
   (`slot`, `merge`, `mechanism`, `constraint`, и опциональные `metric/units/trust/...`).

## Связи с другими директориями

- `components/`: источник `ComponentKind.IR_FRAGMENT` для compose-сценария.
- `artifacts/`: CAS storage, typed refs и canonical payload чтение/запись.
- `ir/`: schema-models и default registries (`ir.kernel`, `ir.registry_fragments`).
- `governance/` и `foundry/`: потребители собранных registries на этапе validation/execute.

## Публичный API

- Registry primitives: `GenericRegistry`, `GenericRegistrySnapshot`, `BaseRegistry`, `DuplicateDecision`
- Bundle builders: `build_registry_bundle`, `build_default_registry_bundle`,
  `build_registry_bundle_from_components`, `FragmentPrecedencePolicy`
- Bundle loaders: `load_registry_bundle`, `load_registry_bundle_payload`,
  `load_registry_bundle_content`, `RegistryBundleContent`
