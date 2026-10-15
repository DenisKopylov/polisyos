# Manage Schema Snapshots

Related reference: [Schemas](../reference/schemas.md). Related explanation: [IR Design](../explanation/ir-design.md).

> This page is for engineers changing public IR/runtime contracts who need to
> preserve ABI discipline instead of simply "regenerating JSON."

Freshness: 2026-10-14.

Source snapshot: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`; read-only inspection of
`tools/quality/diagnostics/gen_schema.py`,
`tools/quality/diagnostics/generate_ir_reference_catalog.py`,
`tools/ops_runners/runtime/export_runtime_openapi.py`,
`src/polisyos/ir/migrations/base.py`, and
`docs/adr/0104-ir-canonical-cas-policy.md`; generators and checks were not run.
This supersedes the previous 2026-04-17 freshness marker and is not a generation receipt.

## Inputs

- a change to a public Pydantic model, Enum, or runtime DTO;
- an assessment of whether the change is additive, breaking, or accidental
  drift;
- readiness to update docs/reference and the generated client when the runtime
  surface changes.

## Outputs

- ABI snapshots and runtime OpenAPI that match the code;
- a documented compatibility story;
- an IR schema catalog and reference pages that match the actual surface.

## Commands

```bash
uv run --extra ml polisyos-tools diagnostics gen-schema --check
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py
cd apps/runtime-dashboard && corepack pnpm run generate:api
```

The repository currently has two important schema surfaces:

- ABI snapshots in `schemas/snapshots/**`, generated through
  `tools/quality/diagnostics/gen_schema.py`;
- the runtime OpenAPI snapshot `schemas/runtime_api_v1.openapi.json`, exported
  through `tools/ops_runners/runtime/export_runtime_openapi.py`.

The top-level `schemas/` directory contains only committed data artifacts. The
ABI registry and Python helpers are imported from `polisyos.schemas.*`.

## 1. When to update snapshots

Run the schema workflow when you:

- change a public Pydantic model or Enum that belongs to the ABI registry;
- add a new IR/Fabric contract;
- change the Runtime API request/response surface;
- change the generated runtime client.

If an internal helper change does not affect the public contract shape, a
snapshot update is usually unnecessary.

## 2. Check ABI drift without writing files

Basic local check:

```bash
uv run --extra ml polisyos-tools diagnostics gen-schema --check
```

If a snapshot does not match the code, the script exits with an error and lists
the out-of-date files.

To check a subset of models:

```bash
uv run --extra ml polisyos-tools diagnostics gen-schema --check --models claim p0 ir
```

## 3. Regenerate ABI snapshots

When the change is intentional:

```bash
uv run --extra ml polisyos-tools diagnostics gen-schema
```

The generator updates:

- `schemas/snapshots/<module>/*.schema.json`
- `_manifest.json` for the corresponding snapshot bundle
- `docs/reference/ir/schema-catalog.md`
- `docs/reference/schemas.md`

As a rule, review the semantic intent of the change as well as the JSON diff. A
snapshot update without a clear contract story is usually a warning sign.

## 4. Check the runtime OpenAPI snapshot

The runtime contract is maintained separately:

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json
```

If you changed HTTP routes or DTOs, you will usually also need to update the
generated client after exporting the snapshot:

```bash
corepack pnpm --dir packages/runtime-api-client run generate -- --openapi schemas/runtime_api_v1.openapi.json
```

## 5. Classify drift

It is useful to distinguish three cases:

- additive drift: a new field/model was added with a compatible history;
- breaking drift: a field was removed, renamed, or changed to another type;
- accidental drift: the code changed without an intentional contract decision.

The first case is usually acceptable with an appropriate report/ADR. The second
requires an explicit compatibility decision. The third should be caught and
reverted promptly.

## 6. Make a compatibility decision before updating snapshots

Before accepting schema drift, ask the same question that release review will
ask:

```python
from polisyos.ir.migrations import negotiate_schema_version

decision = negotiate_schema_version(
    "article_extraction_result",
    producer_version="1.0",
    consumer_version="1.5",
)
assert decision.can_read
```

The IR registry uses four modes:

- `FULL`: direct reading is promised in both directions within the declared
  compatibility line.
- `BACKWARD`: a new consumer can read an old producer payload.
- `FORWARD`: an old consumer can read a declared new producer payload.
- `NONE`: direct reading is not promised; a migration edge or refusal is
  required.

Classify changes as follows:

- additive optional fields are usually `BACKWARD` if the old payload is valid
  for the new reader without silent loss of defaults;

- field removal and rename are not compatible by themselves; they require an
  explicit dual-read alias or migration;

- canonical defaults must be recorded in the compatibility rule if a reader
  fills in or normalizes an absent field;

- an unknown canonical `_type` is not a compatibility escape hatch and fails
  closed under ADR-0104.

## 7. What to review in a PR

When reviewing a schema-related PR, check:

- whether the reason for the contract change is clear;
- whether ABI snapshots and OpenAPI/client artifacts were updated when the
  runtime surface changed;
- whether unrelated snapshot bundles were left untouched;
- whether docs/reference pages match the new contract shape;
- whether a compatibility rule or ADR covers producer/consumer mismatch.

## 8. Minimum checks before merge

```bash
uv run --extra ml polisyos-tools diagnostics gen-schema --check
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py
uv run --extra docs python -m mkdocs build --strict
uv run --extra docs python tools/quality/validation/check_docstring_quality.py --repo-root . --allowlist tools/quality/validation/docstring_quality_allowlist.txt
```

## Rollback

If the drift was accidental:

1. Revert the snapshot/OpenAPI/client diff.
2. Rerun the `--check` commands.
3. Confirm that the code matches the committed baseline again without manually
   editing generated files.

## Troubleshooting

- If it is unclear which model caused drift, start with `gen_schema.py --check`
  and narrow the check to the affected models.
- If the runtime client differs from OpenAPI, first export the committed OpenAPI
  snapshot, then regenerate the client.
- If a change appears breaking and the compatible path is unclear, define an
  explicit compatibility rule or ADR instead of creating only a new snapshot.

## Next steps

- For the current snapshot catalog, see the [Schemas reference](../reference/schemas.md).
- For the complete generated inventory of IR types and fields, see the [IR
  Schema Catalog](../reference/ir/schema-catalog.md).
- For runtime contract tooling, see `tools/ops_runners/runtime/README.md`.
- For ABI tooling, see `tools/quality/diagnostics/README.md`.
