# IR (`polisyos.ir`)

## Purpose

`polisyos.ir` задает канонический контрактный слой PolicyOS для policy
authoring, schema-backed reflection, registry-aware linking, observation-driven
readiness bundles и аналитических результатов. Корневой пакет работает как lazy
facade для наиболее частых import-path'ов и как локальная точка навигации по
IR-подсистеме.

Важно: корневой facade не зеркалит весь код `src/polisyos/ir/**`. Например,
`TrinityBundle` живет в [`trinity`](./trinity/README.md), а linker entrypoint-ы
живут в [`linker`](./linker/README.md).

## Where to Start

- [`__init__.py`](./__init__.py) — стабильный lazy facade и поддерживаемый root import surface.
- [`api.py`](./api.py) — public-surface manifest и shared lazy-facade helpers.
- [`loaders`](./loaders/__init__.py) — loader package, включая `load_policy()`.
- [`schemas`](./schemas/__init__.py) — reflection API, который питает generated reference pages.
- [`trinity/README.md`](./trinity/README.md) — канонический payload `ProblemFrame + PolicySpec + ModelSpec`.
- [`governance/README.md`](./governance/README.md) — authoring surface для `ProblemFrame` и `PolicySpec`.
- [`observation/README.md`](./observation/README.md) — measurement, readiness и execution bundles.
- [`analytics/README.md`](./analytics/README.md) — causal, transportability, HTE, uncertainty и frontier result contracts.
- Соседние пакеты, полезные для навигации: [`kernel/README.md`](./kernel/README.md), [`migrations/README.md`](./migrations/README.md), [`linker/README.md`](./linker/README.md), [`artifacts/README.md`](./artifacts/README.md), [`world/README.md`](./world/README.md).

## Public API

| Entrypoint                                                                | Use when                                                                     | Defined in                                               |
| ------------------------------------------------------------------------- | ---------------------------------------------------------------------------- | -------------------------------------------------------- |
| `polisyos.ir.load_policy()`                                               | Нужно загрузить canonical policy payload из `dict` / JSON / YAML / bytes     | [`loaders`](./loaders/__init__.py)                       |
| `polisyos.ir.ProblemFrame`, `PolicySpec`, `ModelSpec`                     | Нужны базовые Trinity contracts с root import path                           | [`__init__.py`](./__init__.py)                           |
| `polisyos.ir.get_ir_schema_catalog()`, `list_ir_types()`, `get_ir_type()` | Нужен reflection/catalog API для local discovery и generated docs            | [`schemas`](./schemas/__init__.py)                       |
| `polisyos.ir.ObservationRecord`, `ObservationPanel`                       | Нужен базовый observation surface для record/panel payloads                  | [`observation/contracts.py`](./observation/contracts.py) |
| `polisyos.ir.CausalReadinessBundle`, `CausalExecutionBundle`              | Нужны readiness/execution bundles для downstream foundry/scientist execution | [`observation`](./observation/README.md)                 |
| `polisyos.ir.CausalEffectReport`, `TransportabilityResult`, `HTEResult`   | Нужны canonical analytics result models                                      | [`analytics`](./analytics/README.md)                     |
| `polisyos.ir.trinity.TrinityBundle`                                       | Нужен сам canonical Trinity container                                        | [`trinity/__init__.py`](./trinity/__init__.py)           |
| `polisyos.ir.linker.link_trinity()`                                       | Нужно связать Trinity payload с registry surface до compile/runtime          | [`linker/README.md`](./linker/README.md)                 |

## Internal Layout

- [`api.py`](./api.py) and [`__init__.py`](./__init__.py) own the stable lazy
  facade and public-surface helper metadata.
- [`_internal/`](./_internal/) is private implementation code. Do not import it
  from other packages.
- [`_lazy_facade/`](./_lazy_facade/) and
  [`public_surface/`](./public_surface/) are compatibility wrappers that
  re-export from `api.py` while the facade cleanup sunsets.
- [`schemas/`](./schemas/__init__.py), [`loaders/`](./loaders/__init__.py),
  [`trinity/`](./trinity/README.md), [`governance/`](./governance/README.md),
  [`observation/`](./observation/README.md), and
  [`analytics/`](./analytics/README.md) are the main public-adjacent contract
  owners.
- Citation/reference compatibility is centralized under
  [`references/`](./references/__init__.py).

## Extension Points

- IR is not a plugin host in `architecture/extension_points.toml`; it is the
  shared schema and contract layer consumed by extension hosts in Foundry,
  Scientist, Fabric, Lex, Runtime, and Data Forge.
- New schema-backed public IR types should follow
  [Add a schema-backed IR type](../../../docs/how-to/add-schema-backed-ir-type.md)
  and update the schema catalog/reference generation checks.

## Depends on / depended on by

- Depends on: [`kernel`](./kernel/README.md), [`trinity`](./trinity/README.md), [`governance`](./governance/README.md), [`analytics`](./analytics/README.md), [`observation`](./observation/README.md), [`artifacts`](./artifacts/README.md), [`linker`](./linker/README.md), [`migrations`](./migrations/README.md).
- Depended on by: `polisyos.foundry`, `polisyos.scientist`, `polisyos.fabric`, `polisyos.lex`, `polisyos.core`, plus docs/tooling that render IR schema and public-surface catalogs.

## Common commands

Run from the repository root (`policy-engine/`).

Smoke-tested on `2026-05-05`.

```bash
uv run python -c "from polisyos.ir import ProblemFrame, load_policy, list_ir_types; print(ProblemFrame.__name__, callable(load_policy), len(list_ir_types(section='governance', public_only=True)))"
```

## Tests

Run from the repository root (`policy-engine/`).

Conceptual in this README refresh; run these targeted checks before landing IR
changes.

```bash
uv run pytest tests/unit/ir/test_public_surface.py tests/unit/ir/test_schema_catalog.py tests/unit/ir/test_trinity_loaders.py tests/unit/ir/test_interoperability_bridges.py -q
uv run python tools/quality/diagnostics/generate_ir_reference_catalog.py --check
uv run --extra ml polisyos-tools diagnostics gen-schema --check
```

Package-local ownership is documented in
[tests/unit/ir/README.md](../../../tests/unit/ir/README.md) and high-complexity
analytics coverage is documented in
[tests/unit/ir/analytics/README.md](../../../tests/unit/ir/analytics/README.md).

## Operability Links

- [IR component SLO](../../../ops/components/ir/slo.yaml)
- [IR component runbooks](../../../ops/components/ir/runbooks.md)
- [IR schema catalog](../../../docs/reference/ir/schema-catalog.md)
- [Schema management how-to](../../../docs/how-to/manage-schemas.md)
- [Broken contract generation runbook](../../../docs/runbooks/broken-contract-generation.md)

## Known Shims/Deprecations

- Active IR facade-cleanup shims are registered in
  [architecture/shims.toml](../../../architecture/shims.toml) with owner
  `team-ir` and sunset `2026-12-31`.
- Current wrapper-only import paths include `polisyos.ir.public_surface`,
  `polisyos.ir._lazy_facade`, `polisyos.ir.citations`,
  `polisyos.ir.refs`, and `polisyos.ir.schema_catalog`.
- The high-complexity `ir/analytics/strategic.py` budget is tracked in
  [architecture/module_size_budget.toml](../../../architecture/module_size_budget.toml)
  with owner `team-ir` and sunset `2026-12-31`.

## Reference docs

- [IR reference index](../../../docs/reference/ir/index.md)
- [IR public surface](../../../docs/reference/ir/public-surface.md)
- [IR schema catalog](../../../docs/reference/ir/schema-catalog.md)
- [IR compiler pipeline](../../../docs/reference/ir/compiler-pipeline.md)
- [IR interoperability](../../../docs/reference/ir/interoperability.md)
- [IR governance](../../../docs/reference/ir/governance.md)
- [IR analytics](../../../docs/reference/ir/analytics.md)
- [IR observation](../../../docs/reference/ir/observation.md)
- [Shared schemas reference](../../../docs/reference/schemas.md)
- [Shared public surface reference](../../../docs/reference/public-surface.md)
- [TRINITY contract](../../../docs/contracts/TRINITY.md)
- [Merge semantics contract](../../../docs/contracts/MERGE_SEMANTICS.md)

- Last updated: 2026-05-06
