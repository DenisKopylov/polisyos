# Add Schema-Backed IR Type

> Add an IR contract so it appears in the schema catalog, enters ABI snapshots
> when appropriate, and stays aligned with the published reference pages.

Source snapshot: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb` (2026-10-14), checked by
reading `src/polisyos/schemas/abi_models.py`,
`tools/quality/diagnostics/gen_schema.py`, and
`tools/quality/diagnostics/generate_ir_reference_catalog.py`. Generators and
tests were not run; a specific type still needs its own visibility and ABI decision.

## Inputs

- the fully qualified name of the new model or enum;
- the IR section where the type belongs;
- a decision about whether it needs catalog visibility only or a full ABI
  snapshot.

## Output

- a new IR type under `src/polisyos/ir/**`;
- an entry in `src/polisyos/schemas/abi_models.py`, when needed;
- updated schema snapshots and the reference catalog.

## Commands

Regenerate snapshots and IR reference catalog:

```bash
cd policy-engine
uv run --extra ml polisyos-tools diagnostics gen-schema
```

Verification:

```bash
uv run python tools/quality/diagnostics/generate_ir_reference_catalog.py --check
uv run --extra ml polisyos-tools diagnostics gen-schema --check
uv run pytest -q tests/unit/ir/test_schema_catalog.py tests/unit/ir/test_public_surface.py
```

## 1. Add the type in the right IR section

Define the model or enum under the relevant IR package, for example:

- `src/polisyos/ir/governance/**`
- `src/polisyos/ir/analytics/**`
- `src/polisyos/ir/observation/**`
- `src/polisyos/ir/world/**`

For snapshot-backed Pydantic models, keep a stable default `schema_version`
field so the generator can lift the version into the schema metadata.

## 2. Decide how visible the type should be

Possible visibility levels:

- internal only: importable from its module, but not exported through facades;
- package facade: exported from a section facade such as `polisyos.ir.analytics`;
- root facade: exported from `polisyos.ir`;
- snapshot-only: not exported from a facade, but still tracked through
  `src/polisyos/schemas/abi_models.py`.

That visibility shows up in `IRPublicStatus` inside the generated schema catalog.

## 3. Register ABI-backed types in `src/polisyos/schemas/abi_models.py`

If the contract is ABI-visible, add an `ABIModelEntry` with:

- `abi_key`;
- `fqn`;
- `module="ir"`;
- `schema_file`;
- `priority`;
- optional compatibility metadata when needed.

Skip this step if the type should stay catalog-only and not become part of the
committed ABI snapshot set.

## 4. Regenerate snapshots and docs

Run:

```bash
uv run --extra ml polisyos-tools diagnostics gen-schema
```

This generator is the canonical path for both:

- `schemas/snapshots/**`;
- generated IR reference catalog pages such as
  `docs/reference/ir/schema-catalog.md`.

## 5. Verify the resulting surface

Use:

```bash
uv run python tools/quality/diagnostics/generate_ir_reference_catalog.py --check
uv run --extra ml polisyos-tools diagnostics gen-schema --check
uv run pytest -q tests/unit/ir/test_schema_catalog.py tests/unit/ir/test_public_surface.py
```

If the type is exported through a facade, also verify the relevant package
public-surface tests.

## Rollback

- remove the `ABIModelEntry` if the type should stay out of committed snapshots;
- remove facade exports if the type should remain internal;
- rerun the generators so the snapshot and reference catalog return to the last
  intended state.

## Troubleshooting

- `gen-schema --check` fails: the new type is ABI-visible but missing from
  snapshots or has unstable schema metadata;

- schema catalog docs do not mention the type: it may be internal-only, not
  importable, or the generator has not been rerun;

- facade tests fail: the type was exported through docs expectations but not
  through the actual package `__all__`.
