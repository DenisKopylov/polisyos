# Components (Component Model v1)

`polisyos.core.components` задает единый слой identity/discovery/compliance для расширений.

## ComponentId

Формат: `seg(.seg)+@semver`

- `seg`: `[a-z][a-z0-9_]*`
- SemVer 2.0.0 (включая pre-release/build)

```python
from polisyos.core.components import ComponentId

cid = ComponentId.parse("fiscal.taxation.flat_tax@1.2.3")
print(cid.base_id)     # fiscal.taxation.flat_tax
print(cid.namespace)   # fiscal.taxation
print(cid.name)        # flat_tax
print(cid.version)     # 1.2.3
```

## Metadata

```python
from polisyos.core.components import (
    Capability,
    ComponentKind,
    ComponentMetadata,
    ComponentId,
)

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
from polisyos.core.components import (
    ComponentRegistry,
    ComponentEntry,
    discover_components,
)

report = discover_components()
registry = ComponentRegistry()
for row in report.components:
    registry.register(ComponentEntry(metadata=row.metadata, component=row.component, source=row.source))
```
