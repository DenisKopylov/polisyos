# Components (Component Model Skeleton)

Минимальный ABI для идентичности и discovery компонентов. Этот пакет — подготовка к E3, без интеграции существующих подсистем.

## ComponentId

Формат: `namespace.name@semver`

- `namespace` и `name`:
  - lowercase `[a-z][a-z0-9_]*`
  - разделитель — точка между namespace и name
- `semver`:
  - минимум `MAJOR.MINOR.PATCH`
  - допускаются pre-release/build metadata

```python
from polisyos.core.components import ComponentId

cid = ComponentId.parse("polisyos.fabric@1.2.0")
print(cid.namespace, cid.name, cid.version)
```

## ComponentMetadata

```python
from polisyos.core.components import ComponentMetadata, Capability, ComponentId

metadata = ComponentMetadata(
    component_id=ComponentId.parse("polisyos.lex@0.1.0"),
    display_name="Lex Stub",
    domains=["legal"],
    jurisdictions=["US-CA"],
    tags=["compliance"],
    capabilities=Capability.LEX_EVALUATE,
)
```

## Registry & Discovery

```python
from polisyos.core.components import ComponentRegistry, ConflictPolicy

registry = ComponentRegistry()
registry.register(metadata, policy=ConflictPolicy.PREFER_HIGHEST_SEMVER)

lex_components = registry.query(capabilities=Capability.LEX_EVALUATE)
```

Entry point group: `polisyos.components`.

Discovery helpers:

```python
from polisyos.core.components import discover_entry_points

components = discover_entry_points()
```
