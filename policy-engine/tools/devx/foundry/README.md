# Foundry DevX (`tools/devx/foundry`)

## Purpose

`tools/devx/foundry` is the public tooling surface for Foundry ABI maintenance: generating `.pyi` stubs and updating the signature baseline after approved breaking or non-breaking API changes.

## Where to Start

- Stub generation: `tools/devx/foundry/generate_stubs.py`.
- Signature baseline refresh: `tools/devx/foundry/update_signature_baseline.py`.
- Written outputs:
  `src/polisyos/foundry/methods/{base,registry,composer}.pyi` and
  `src/polisyos/foundry/methods/components/composer.pyi` and
  `src/polisyos/foundry/methods/selection/registry.pyi`.

- Baseline artifact:
  `tests/_golden/foundry/signature_baseline.json`.

## Public Entrypoints

| Entrypoint                                                            | Purpose                                                     |
| --------------------------------------------------------------------- | ----------------------------------------------------------- |
| `uv run --extra lint polisyos-tools foundry generate-stubs [--check | --dry-run] [--output-root PATH]`            | Regenerate public method stubs for the Foundry facade.      |
| `uv run polisyos-tools foundry update-signature-baseline [--dry-run]` | Recompute stable digests and update the signature baseline. |

## Depends On / Depended On By

- **Depends on:** `polisyos.foundry.methods.*`, `mypy.stubgen`, Ruff, registry
  snapshotting in `MethodRegistry`, and the baseline fixture under `tests/unit/foundry`.

- **Depended on by:** Foundry public-surface reviews, signature compatibility
  tests, release closeout, and manual ABI-drift investigations.

## Common Commands

The generator renders the complete `OUTPUT_MAP` before writing or comparing.
The existing owner derives facade names from each actual canonical owner's explicit
`__all__`, emitting explicit self-alias reexports rather than wildcard
imports or a second curated symbol list. It then organizes imports with Ruff,
formats each stub, and requires the full canonical Ruff policy before any
output is written. Every Ruff stdin call uses the actual canonical `.pyi`
logical filename, explicit product `ruff.toml` (which extends
`ruff.generated.toml`) and `--no-cache`. No policy suppression/configuration
change is made. Missing tools/configuration or missing/invalid owner
export declarations are ERROR before output publication.

Both existing mypy and Ruff are in the retained `lint` profile and frozen lock.
The family now declares the two Ruff config files as native probe inputs.
Each stubgen launcher wait is bounded at 120 seconds and each Ruff wait at 30
seconds; OSError/TimeoutExpired surfaces as backend ERROR before publication.
These conservative budgets are grounded in retained native/static measurements.
They do not establish standalone owner-import or descendant-process quiescence;
use the retained external supervisor for whole-case/process-group qualification.

Generation keeps two real stubgen calls per render and four outputs; the Ruff
normalization/check subprocesses are additional measured work. Existing runtime
freshness PASS proves its own producer/profile version; it does not imply that
older adopted bytes passed canonical Ruff. Source/staged/type/property checks
remain separate evidence.

`--dry-run` invokes stubgen and validates generated syntax but performs no byte
comparison; it is not a freshness receipt. `--check` regenerates into temporary
scratch and compares every declared output byte-for-byte without writing output
files. Missing or unreadable outputs are ERROR, drift is FAIL, and a complete
identical comparison is PASS. `--output-root PATH` writes product-relative output
paths beneath a staged root; with `--check`, it compares that staged tree.

```bash
uv run --extra lint polisyos-tools foundry generate-stubs --check
uv run --extra lint polisyos-tools foundry generate-stubs --output-root LOCAL/foundry-stubs-stage
uv run --extra lint polisyos-tools foundry generate-stubs --check --output-root LOCAL/foundry-stubs-stage
```

These commands are source-backed interfaces, not execution receipts for a future
candidate. Keep Python, lockfile, mypy/stubgen and the actual source tree pinned
when generating and comparing. The canonical composer output comes from
`components.composer`; the compatibility `composer.pyi` stays a canonical-owner
reexport. `architecture/generated_artifacts.toml` registers all five outputs as
one generated-committed family using this owner for checking and staged probing.

Each invocation prints its explicit read measurement, selected modules/output
paths and the named boundaries it cannot decide. Stubgen's transitive imports
and subprocess source reads are not observed by that explicit reader. Equality
covers the declared map, not unlisted stubs or semantic type correctness. Run the
real type/import consumers after generation; no snapshot grants runtime or
scientific authority.

## Test And Verification

| Command                                                                                                                        | What it verifies                                                         | Status         |
| ------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------ | -------------- |
| `uv run pytest -q tests/unit/foundry/contracts/test_signature_compat.py tests/repo_quality/tools/test_phase4_consolidation.py` | Signature-drift contract and zoned-tooling compatibility.                | `conceptual`   |
| `uv run polisyos-tools list --by-zone`                                                                                         | The Foundry tooling category is correctly registered in the unified CLI. | `smoke-tested` |

## Reference Docs

- [Foundry README](../../../src/polisyos/foundry/README.md)
- [Public Surface Reference](../../../docs/reference/public-surface.md)
- [Tool Reference](../../../docs/reference/tools.md)
- [Causal Engine Explanation](../../../docs/explanation/causal-engine.md)

## Current State

- Stub generation covers `polisyos.foundry.methods.base`, `registry`,
  `composer`, and the canonical `components.composer`; the map is the enumerated
  source of truth for both checking and staging.

- The signature baseline is stored in test fixtures for deliberate ABI
  review and to prevent silent drift.

- The canonical surface is `polisyos-tools foundry ...`; product-root
  `scripts/` were retired during the Repository SOTA closeout.

- Last updated: 2026-10-28

## Canonical provider closure

The generated family includes canonical `selection.registry` as well as the
compatibility registry facade. Python type checkers resolve `selection/registry.pyi`
ahead of its `.py`; updating the source reexport cannot repair a stale provider
stub. All physical `.pyi` files below `src/polisyos/foundry/methods` must belong to
the same complete `OUTPUT_MAP`. The defining staged-owner test recomputes this
physical file-type denominator before generation, then type-checks all staged
provider/facade outputs together. Its client also accesses every runtime `__all__`
export and consumes canonical registry entries, snapshots, lifecycle and audit
contracts. This is an extension of the existing owner, not a second stub generator.
