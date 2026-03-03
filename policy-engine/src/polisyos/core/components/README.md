# Components — component model и bootstrap

`core.components` — единая модель расширений PolisyOS: идентификаторы, metadata/capabilities, discovery, реестр компонентов и bootstrap runtime-реестров.

## Состав

```text
components/
├── ids.py          # SemVer/SemverRange/ComponentId
├── metadata.py     # ComponentKind/ComponentMetadata/ComponentDep
├── capabilities.py # Capability flags
├── protocols.py    # Component / ComponentFactory / ComponentProvider protocols
├── discovery.py    # entry-point + dev-scan discovery
├── registry.py     # multi-version ComponentRegistry
├── compliance.py   # metadata/runtime compliance checks
├── bootstrap.py    # bootstrap domain registries from one component index
├── cli*.py         # CLI facade + subcommands (components/registry/audit/replay/...)
└── __init__.py
```

## Identity и metadata

- `ComponentId`: формат `namespace.name@semver`
- `ComponentKind`: `ir_fragment`, `foundry_method`, `fabric_connector`, `scholar_extractor`, `lex_*`, `scientist_node`, `norm_pack_provider`
- `Capability`: type- и cross-cutting возможности (`CAS_READ`, `FOUNDRY_EXECUTE`, `LEX_EVALUATE`, ...)

## Discovery

`discover_components()` собирает компоненты из:
- entry-point групп `polisyos.ir_fragments`, `polisyos.foundry_methods`, `polisyos.fabric_connectors`, `polisyos.lex_*`, `polisyos.scholar_extractors`, `polisyos.scientist_nodes`, `polisyos.norm_pack_providers`;
- dev-scan (по умолчанию включен, обычно `.../packs`).

`polisyos.components` (legacy group) поддерживается отдельно через `include_legacy_group=True`.

Политики:
- duplicate policy (`warn/error/ignore`)
- precedence (`dev_scan_wins_over_entry_points`)

## ComponentRegistry

`ComponentRegistry` хранит несколько версий и поддерживает:
- `register`, `get`, `list`, `list_all`
- `resolve` (`EXACT`, `LATEST`, `LATEST_COMPATIBLE`)
- `query` по `kind/domain/jurisdiction/capabilities/tags`

## Bootstrap runtime-реестров

Типовой поток:

```python
from polisyos.core.components import build_components_index, bootstrap_plugin_registries

components_index, discovery_report = build_components_index()
bootstrap_report = bootstrap_plugin_registries(components_index)
```

`bootstrap_plugin_registries()` инициализирует домены:
- connectors (`fabric`)
- methods (`foundry`)
- evaluators/providers (`lex`)
- extractors (`fabric`/`scholar`/`lex`)
- nodes (`scientist`)

## Где используется

- `packs/`: декларация компонентных metadata
- `registry/`: сборка IR bundle из `ComponentKind.IR_FRAGMENT`
- `fabric`/`foundry`/`lex`/`scientist`/`scholar`: runtime discovery и bootstrap
