# Migrations (`polisyos.ir.migrations`)

## Purpose

`polisyos.ir.migrations` отвечает за versioned migration только канонического
policy IR payload. Пакет intentionally узкий: он поддерживает schema lineage
для Trinity-era `policy_ir`, но не пытается автоматически оживлять legacy
non-Trinity surface.

## Where to Start

- [`__init__.py`](./__init__.py) — public migration entrypoints, version parsing и guarded major-bump behavior.
- [`policy_ir.py`](./policy_ir.py) — current policy IR version и registered identity migration.
- [`trinity_migration.py`](./trinity_migration.py) — Trinity-specific helper routines.
- [`schema_registry.py`](./schema_registry.py) — compatibility tables и schema rules.
- [`base.py`](./base.py) — generic migration registry / negotiation primitives.
- Для payload shape откройте [`../trinity/README.md`](../trinity/README.md), для root loaders — [`../README.md`](../README.md).

## Public entrypoints

| Entrypoint                                                               | Use when                                                         | Defined in                                                |
| ------------------------------------------------------------------------ | ---------------------------------------------------------------- | --------------------------------------------------------- |
| `polisyos.ir.migrations.IR_ARTIFACT`                                     | Нужно canonical artifact family name для migration registry      | [`__init__.py`](./__init__.py)                            |
| `polisyos.ir.migrations.IR_CURRENT_VERSION`                              | Нужно узнать текущую поддерживаемую policy IR version            | [`__init__.py`](./__init__.py)                            |
| `polisyos.ir.migrations.parse_version()`                                 | Нужно распарсить `MAJOR.MINOR` version string                    | [`__init__.py`](./__init__.py)                            |
| `polisyos.ir.migrations.is_major_bump()`                                 | Нужно определить, требуется ли guarded major transition          | [`__init__.py`](./__init__.py)                            |
| `polisyos.ir.migrations.migrate_policy_ir()`                             | Нужно прогнать canonical payload через supported migration chain | [`__init__.py`](./__init__.py)                            |
| `polisyos.ir.migrations.can_read_schema()`, `negotiate_schema_version()` | Нужны compatibility checks для producers/consumers               | [`base.py`](./base.py) via [`__init__.py`](./__init__.py) |

## Depends on / depended on by

- Depends on: [`../trinity/README.md`](../trinity/README.md), migration registry primitives in [`base.py`](./base.py), schema rules in [`schema_registry.py`](./schema_registry.py).
- Depended on by: `polisyos.ir.loaders`, `polisyos.ir.schema_catalog`, runtime ingestion paths, contract tests and compatibility checks.

## Common commands

Run from the repository root (`policy-engine/`).

Smoke-tested on `2026-04-17`.

```bash
uv run python -c "from polisyos.ir.migrations import IR_CURRENT_VERSION, parse_version, migrate_policy_ir; print(IR_CURRENT_VERSION, parse_version(IR_CURRENT_VERSION), callable(migrate_policy_ir))"
```

## Test/verification commands

Run from the repository root (`policy-engine/`).

Conceptual in this README refresh; run this suite before landing migration or
compatibility changes.

```bash
uv run pytest tests/contract/test_ir_migrations.py tests/contract/test_trinity_migration.py -q
```

## Reference docs

- [IR schema catalog](../../../../docs/reference/ir/schema-catalog.md)
- [Shared schemas reference](../../../../docs/reference/schemas.md)
- [TRINITY contract](../../../../docs/contracts/TRINITY.md)
- [IR root README](../README.md)
- [Trinity README](../trinity/README.md)

## Last updated

`2026-04-17`
