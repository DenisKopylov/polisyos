# Foundry V2 Authoring Guide

`methods/catalog` is the single source of truth for new Foundry methods.

## Where to create a new method

- Add implementations only under `polisyos.foundry.methods.catalog.<domain>`.
- Use the domain package's `__init__.py` for the public flat API.
- Do not add deep import paths under `polisyos.foundry.methods.<domain>.<module>` or restore shim modules.

## Required V2 method fields

- The FQN must follow the `domain.family.variant@semver` convention.
- `MethodSignature.family` must describe the stable family surface.
- `MethodSignature.variant` must describe the specific estimator/runtime variant.
- `MethodSignature.kind` must be one of `pure`, `mechanism`, or `simulation`.
- `MethodSignature.execution_backend` must describe the actual execution mechanism.
- `MethodSignature.data_modalities` must reflect the actual data type, not a marketing label.
- Every non-scalar slot must declare a `shape`.

## When a variant needs a separate method

Create a separate method variant when at least one of the following changes:

- input or output ABI;
- diagnostics or uncertainty surface;
- execution backend;
- assumptions;
- fallback behavior.

If only an internal heuristic changes while the ABI and diagnostics remain the same, use a parameter rather than a new method.

## Metadata and capability truth

- `required_deps` lists dependencies without which the method cannot honestly be declared runnable.
- Use `optional_deps` only for quality degradation, diagnostics, or convenience extras.
- Declare `determinism_tier`, `fallback_policy`, and `side_effect_profile` explicitly.
- Do not encode deprecation through tags on the canonical entry.

## Registration

- Add each new method to `_registry_boot.py` exactly once.
- Do not register aggregate wrappers as first-class entries.
- When extending a family with variants, register the variant methods themselves.

## Checks before merge

- Run the catalog snapshot and contract tests.
- Confirm that the method appears in the `schema_version=2.0` snapshot with accurate `runnable`, `dependency_posture`, and `capability_matrix` values.
- Confirm that scientist selection sees the family/variant and offers the method as a canonical alternative.
