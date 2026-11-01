# Migrations (`polisyos.ir.migrations`)

## Purpose

`polisyos.ir.migrations` handles versioned migrations for the canonical policy
IR payload only. The package is intentionally narrow: it supports schema lineage
for Trinity-era `policy_ir` but does not attempt to revive legacy
non-Trinity surface.

## Where to Start

- [`__init__.py`](./__init__.py) — public migration entry points, version parsing, and guarded major-bump behavior.
- [`policy_ir.py`](./policy_ir.py) — current policy IR version, schema rule, and legacy identity helper.
- [`trinity_migration.py`](./trinity_migration.py) — Trinity-specific helper routines.
- [`schema_registry.py`](./schema_registry.py) — compatibility tables and schema rules.
- [`base.py`](./base.py) — generic migration registry / negotiation primitives.
- For the payload shape, see [`../trinity/README.md`](../trinity/README.md); for root loaders, see [`../README.md`](../README.md).

## Callback registration identity

IR registration fingerprints supported callback code, defaults and captured
values once, before changing the registry. Only a genuinely empty closure cell
receives the empty-cell marker. Unsupported captured values raise the existing
`MigrationCompatibilityError`; they cannot silently collide with another
capture or replace a registered edge. Supported identical registrations remain
idempotent, and conflicting descriptors or cycles refuse.

This is the identity of a registration snapshot, not proof of immutable Python
behavior. Captured semantic dictionaries remain live and can change later;
callers claiming reproducible conversion need an explicit immutable/versioned
semantic configuration and implementation/environment binding. The registry does
not freeze or rehash every callback at invocation. Harmless mutable observer
lists remain supported. No global, file or external-dependency drift detection
or exhaustive historical-plugin compatibility is implied.

Common and IR still use the same linear traversal with distinct copy, stamping,
error and no-op profiles. Data Forge's instance-owned branching graph registry
retains its separate shortest-path contract. Conversion, direct-read
compatibility and actual DTO admission remain separate outcomes.

## Public entrypoints

| Entrypoint                                                               | Use when                                                          | Defined in                                                |
| ------------------------------------------------------------------------ | ----------------------------------------------------------------- | --------------------------------------------------------- |
| `polisyos.ir.migrations.IR_ARTIFACT`                                     | Get the canonical artifact family name for the migration registry | [`__init__.py`](./__init__.py)                            |
| `polisyos.ir.migrations.IR_CURRENT_VERSION`                              | Find the currently supported policy IR version                    | [`__init__.py`](./__init__.py)                            |
| `polisyos.ir.migrations.parse_version()`                                 | Parse a `MAJOR.MINOR` version string                              | [`__init__.py`](./__init__.py)                            |
| `polisyos.ir.migrations.is_major_bump()`                                 | Determine whether a guarded major transition is required          | [`__init__.py`](./__init__.py)                            |
| `polisyos.ir.migrations.migrate_policy_ir()`                             | Run a canonical payload through the supported migration chain     | [`__init__.py`](./__init__.py)                            |
| `polisyos.ir.migrations.can_read_schema()`, `negotiate_schema_version()` | Use compatibility checks for producers/consumers                  | [`base.py`](./base.py) via [`__init__.py`](./__init__.py) |

## Depends on / depended on by

- Depends on: [`../trinity/README.md`](../trinity/README.md), migration registry primitives in [`base.py`](./base.py), schema rules in [`schema_registry.py`](./schema_registry.py).
- Depended on by: `polisyos.ir.loading.loaders`, `polisyos.ir.loading.schema_catalog`, runtime ingestion paths, contract tests and compatibility checks.

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
