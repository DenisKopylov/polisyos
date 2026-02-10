# Components — Component Model v1

Единый слой identity, discovery, registry и compliance для расширений PolisyOS. Плагинная архитектура через Python entry points.

## Архитектура

```
components/
├── ids.py           # ComponentId, SemVer, SemverRange — идентификация и версионирование
├── metadata.py      # ComponentMetadata, ComponentKind, ComponentDep — метаданные
├── capabilities.py  # Capability flags — что компонент умеет
├── protocols.py     # Component, ComponentFactory, ComponentProvider, SupportsValidation
├── registry.py      # ComponentRegistry с conflict resolution policies
├── discovery.py     # discover_components() через entry points
├── bootstrap.py     # единый bootstrap runtime-реестров из ComponentRegistry
├── compliance.py    # validate_component_id(), validate_metadata(), HostAbi checks
└── cli.py           # CLI-интеграция
```

## ComponentId

Формат: `namespace.name@semver`

```python
from polisyos.core.components import ComponentId

cid = ComponentId.parse("fiscal.taxation.flat_tax@1.2.3")
cid.base_id    # "fiscal.taxation.flat_tax"
cid.namespace  # "fiscal.taxation"
cid.name       # "flat_tax"
cid.version    # SemVer(1, 2, 3)
```

## ComponentMetadata

```python
from polisyos.core.components import ComponentMetadata, ComponentKind, Capability

metadata = ComponentMetadata(
    component_id=ComponentId.parse("roads.extractor.speed@1.0.0"),
    kind=ComponentKind.SCHOLAR_EXTRACTOR,
    abi_targets={"world_abi": "1.x"},
    domains=["roads"],
    jurisdictions=["ua"],
    tags=["builtin"],
    capabilities=Capability.SCHOLAR_EXTRACTOR,
)
```

**ComponentKind:** определяет тип компонента (extractor, evaluator, foundry method, IR fragment и т.д.).
В P6 добавлен `fabric_connector`.

## Discovery через Entry Points

Автоматическое обнаружение компонентов через Python packaging entry points:

```python
from polisyos.core.components import discover_components, discover_entry_points

report = discover_components()  # все компоненты из всех групп
```

**Entry point groups:**
- `polisyos.components` — основная группа
- `polisyos.ir_fragments` — IR-фрагменты
- `polisyos.foundry_methods` — методы Foundry
- `polisyos.fabric_connectors` — коннекторы Fabric (Component model)
- `polisyos.lex_evaluators` / `polisyos.lex_extractors` — компоненты Lex
- `polisyos.norm_pack_providers` — провайдеры нормативных пакетов
- `polisyos.scholar_extractors` — extractors Scholar
- `polisyos.scientist_nodes` — ноды Scientist

## ComponentRegistry

Реестр с настраиваемым разрешением конфликтов:

```python
from polisyos.core.components import ComponentRegistry, ConflictPolicy

registry = ComponentRegistry()
registry.register(component)
found = registry.get("fiscal.taxation.flat_tax@1.2.3")
```

**Policies:** `ConflictPolicy`, `DuplicateComponentIdPolicy`, `ResolvePolicy`, `SourcePrecedencePolicy`, `DiscoveryPrecedencePolicy`.

## Compliance

Валидация компонентов перед регистрацией:

```python
from polisyos.core.components.compliance import validate_metadata, has_errors

issues = validate_metadata(metadata)
if has_errors(issues):
    raise ValueError(f"Invalid component: {issues}")
```

## Unified bootstrap

В P6 discovery и bootstrap runtime-реестров унифицированы:

```python
from polisyos.core.components import build_components_index, bootstrap_plugin_registries

components_index, discovery_report = build_components_index()
bootstrap_report = bootstrap_plugin_registries(components_index)
```

`bootstrap_plugin_registries(...)` использует один `ComponentRegistry` snapshot для:
- connectors,
- foundry methods,
- lex evaluators,
- scholar/lex extractors,
- norm pack providers,
- scientist nodes.

## Использование в системе

| Модуль | Что использует |
|--------|---------------|
| **Lex** | `ComponentRegistry`, `discover_components` для norm_pack providers, evaluators, extractors |
| **Fabric** | `ComponentRegistry` для extractor discovery |
| **Packs** | `ComponentId`, `ComponentKind`, `ComponentMetadata`, `Capability` — регистрация компонентов |
| **Scholar** | `ComponentMetadata` для extractor discovery |
