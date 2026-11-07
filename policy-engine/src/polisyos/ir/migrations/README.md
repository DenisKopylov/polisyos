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

## Provided release composition (REQ-MIG-05-04)

This record declares the finite exercised Python registration/import set below.
It preserves the public registration APIs; it does not declare unlisted external
callbacks unsupported or claim they do not exist.

| Owner/entry | Version, registration and consumer boundary |
| --- | --- |
| `ir.migrations` and `policy_ir` | Policy IR baseline `1.0`; import installs schema compatibility declarations from `policy_ir.py` and `schema_registry.py`. A schema rule is not a conversion callback. `migrate_policy_ir` and the loader/Trinity helpers retain the [helper matrix](../../../../tools/ops_runners/migrations/README.md). |
| `ir.migrations.register_migration` / `base.register_migration` | Explicit caller-supplied edges in the IR registry; supported descriptor equality, conflict, cycle, empty-cell and unsupported-capture outcomes are exercised. Importing the facade is not permission to reinterpret legacy non-Trinity payloads. |
| `common.migrations.register_migration` | Neutral Common profile with its own replacement, copy, stamping and error ABI; shared traversal does not erase those differences. |
| Common legacy adapter / Fabric explicit registration / CLI per-call edge | The dataset `0.9 -> 1.0` composition and two import orders are enumerated in [Common adapter support](../../common/migrations/README.md). |
| `data_forge.kernel.schemas.migrations.SchemaMigrationRegistry` | Explicit instance-owned `SchemaMigrationPlan` registrations use three-component versions and deterministic shortest-path traversal. This graph is not silently replaced by the Common/IR linear profile. |

The finite callback/configuration corpus is
[test_mig_05.py](../../../../tests/unit/remediation/test_mig_05.py): actual manifest
and Trinity helpers, supported scalar/mapping captures, genuine empty cells,
unsupported opaque captures, a changed semantic dictionary, an immutable tuple
configuration plus mutable observer, Common/IR no-op/copy/stamp/error profiles,
and instance-owned Data Forge branching/direct-read controls. It checks actual
conversion separately from read compatibility and strict DTO admission. The
registration fingerprint does not bind arbitrary library/global/file state: the
changed dictionary intentionally changes the result without re-registration.
Its profile is non-reproducible across that change. Reproducible callers must
supply immutable/versioned semantic configuration and identify implementation and
environment; an observer list alone does not require blanket freezing or rehashing.

The source-qualified historical sample referenced by this record is the Runtime
protocol-4 fixture in [Replay support](../../scientist/replay/README.md), not an
exhaustive repository or historical-corpus inventory. Current writer and synthetic
dataset/Trinity vectors remain separately identified. No
external migration callbacks, original historical dataset/Policy IR payloads or
their semantic configuration/implementation/environment bindings were supplied for
this record. Their compatibility is `not_established`, not zero or universally
refused. A concrete external compatibility claim needs that callback/import path,
versioned configuration, input bytes/hash and expected consumer result; this does
not block the independently qualified unsupported-versus-empty fix or normal use
of the registration APIs. Source/native qualification does not establish the shared
noneditable installed I06-E composition. Operator windows remain those in the
[migration contract](../../../../ops/migrations/migration-contracts.toml); no adapter
retirement is approved by this record.

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
