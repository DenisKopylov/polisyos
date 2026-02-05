# Components (Component Model v1)

Единый слой identity/discovery/compliance для расширений PolisyOS.

## ComponentId

Формат: `namespace.name@semver`

```python
from polisyos.core.components import ComponentId

cid = ComponentId.parse("fiscal.taxation.flat_tax@1.2.3")
print(cid.base_id)     # fiscal.taxation.flat_tax
print(cid.namespace)   # fiscal.taxation
print(cid.name)        # flat_tax
print(cid.version)     # 1.2.3
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

## Discovery & Registry

```python
from polisyos.core.components import ComponentRegistry, discover_components

report = discover_components()
registry = ComponentRegistry()
for component in report.components:
    registry.register(component)
```

## Особенности

- **Identity**: Уникальная идентификация через ComponentId
- **Discovery**: Автоматическое обнаружение компонентов
- **Compliance**: Проверка совместимости через abi_targets
- **Metadata**: Богатые метаданные (domains, jurisdictions, capabilities)
