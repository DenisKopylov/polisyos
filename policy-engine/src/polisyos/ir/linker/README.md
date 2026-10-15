# Linker (`polisyos.ir.linker`)

`polisyos.ir.linker` connects `TrinityBundle` to the registry surface and turns
a declarative policy payload into a `LinkedTrinityBundle` with binding diagnostics,
canonical digests, and a typed issue report. This is the final contract stage
before compilation/execution in `foundry` and governance preflight in `scientist`.

## Role in the system

- **Depends on:** `polisyos.ir.trinity`, `polisyos.ir.kernel`, `polisyos.ir.governance`
- **Used by:** `polisyos.core.compiler`, `polisyos.foundry`, `polisyos.scientist`
- The linker turns static IR contracts into runtime-ready bindings without executing the mechanisms themselves.

## Key concepts

- **Linked bundle** — `LinkedTrinityBundle` retains the source bundle, bindings, and digests.
- **Typed diagnostics** — `LinkReport` and `LinkIssue` distinguish errors, warnings, and informational notes.
- **Registry validation** — the linker checks mechanism IDs, parameters, slots, metrics, constraints, and selector fields.
- **Canonical digests** — the report includes registry and bundle hashes when canonicalization is possible.
- **Applicability refs** — the helper in `types.py` validates actor/concept/jurisdiction references.

## Public API

| Type/Function                                | Description                                                             |
| -------------------------------------------- | ----------------------------------------------------------------------- |
| `link_trinity()`                             | Main function for linking a Trinity bundle against registries           |
| `LinkedIntervention`                         | Normalized linked view of one intervention                              |
| `TrinityBindings`                            | Aggregated bindings for slots, parameters, and mechanisms               |
| `LinkedTrinityBundle`                        | Result object for downstream compilation/runtime use                    |
| `LinkIssue`, `LinkIssueCode`, `LinkSeverity` | Typed issue protocol                                                    |
| `LinkReport`                                 | Summary of the validation outcome and digests                           |
| `validate_norm_applicability_refs()`         | Validate norm applicability references outside the main linker pipeline |

Full reference: [docs/reference/ir/](../../../../docs/reference/ir/index.md)

## Current state

- Last updated: 2026-04-03
- Files: 9 Python files
- Exports: 9 public names in `__init__.py`
- Delta status: linker code is stable; this README reflects the current registry/observation-aware Trinity surface
