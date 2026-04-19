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
- [`loaders.py`](./loaders.py) — root-level loaders, включая `load_policy()`.
- [`schema_catalog.py`](./schema_catalog.py) — reflection API, который питает generated reference pages.
- [`trinity/README.md`](./trinity/README.md) — канонический payload `ProblemFrame + PolicySpec + ModelSpec`.
- [`governance/README.md`](./governance/README.md) — authoring surface для `ProblemFrame` и `PolicySpec`.
- [`observation/README.md`](./observation/README.md) — measurement, readiness и execution bundles.
- [`analytics/README.md`](./analytics/README.md) — causal, transportability, HTE, uncertainty и frontier result contracts.
- Соседние пакеты, полезные для навигации: [`kernel/README.md`](./kernel/README.md), [`migrations/README.md`](./migrations/README.md), [`linker/README.md`](./linker/README.md), [`artifacts/README.md`](./artifacts/README.md), [`world/README.md`](./world/README.md).

## Public entrypoints

| Entrypoint | Use when | Defined in |
|---|---|---|
| `polisyos.ir.load_policy()` | Нужно загрузить canonical policy payload из `dict` / JSON / YAML / bytes | [`loaders.py`](./loaders.py) |
| `polisyos.ir.ProblemFrame`, `PolicySpec`, `ModelSpec` | Нужны базовые Trinity contracts с root import path | [`__init__.py`](./__init__.py) |
| `polisyos.ir.get_ir_schema_catalog()`, `list_ir_types()`, `get_ir_type()` | Нужен reflection/catalog API для local discovery и generated docs | [`schema_catalog.py`](./schema_catalog.py) |
| `polisyos.ir.ObservationRecord`, `ObservationPanel` | Нужен базовый observation surface для record/panel payloads | [`observation/contracts.py`](./observation/contracts.py) |
| `polisyos.ir.CausalReadinessBundle`, `CausalExecutionBundle` | Нужны readiness/execution bundles для downstream foundry/scientist execution | [`observation`](./observation/README.md) |
| `polisyos.ir.CausalEffectReport`, `TransportabilityResult`, `HTEResult` | Нужны canonical analytics result models | [`analytics`](./analytics/README.md) |
| `polisyos.ir.trinity.TrinityBundle` | Нужен сам canonical Trinity container | [`trinity/__init__.py`](./trinity/__init__.py) |
| `polisyos.ir.linker.link_trinity()` | Нужно связать Trinity payload с registry surface до compile/runtime | [`linker/README.md`](./linker/README.md) |

## Depends on / depended on by

- Depends on: [`kernel`](./kernel/README.md), [`trinity`](./trinity/README.md), [`governance`](./governance/README.md), [`analytics`](./analytics/README.md), [`observation`](./observation/README.md), [`artifacts`](./artifacts/README.md), [`linker`](./linker/README.md), [`migrations`](./migrations/README.md).
- Depended on by: `polisyos.foundry`, `polisyos.scientist`, `polisyos.fabric`, `polisyos.lex`, `polisyos.core`, plus docs/tooling that render IR schema and public-surface catalogs.

## Common commands

Run from the repository root (`policy-engine/`).

Smoke-tested on `2026-04-17`.

```bash
uv run python -c "from polisyos.ir import ProblemFrame, load_policy, list_ir_types; print(ProblemFrame.__name__, callable(load_policy), len(list_ir_types(section='governance', public_only=True)))"
```

## Test/verification commands

Run from the repository root (`policy-engine/`).

Conceptual in this README refresh; run these targeted checks before landing IR
changes.

```bash
uv run pytest tests/ir/test_public_surface.py tests/ir/test_schema_catalog.py tests/ir/test_trinity_loaders.py tests/ir/test_interoperability_bridges.py -q
uv run python tools/diagnostics/generate_ir_reference_catalog.py --check
uv run --extra ml polisyos-tools diagnostics gen-schema --check
```

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

- Last updated: 2026-04-17
