# Foundry DevX (`tools/devx/foundry`)

## Purpose

`tools/devx/foundry` is the public tooling surface for Foundry ABI maintenance: generating `.pyi` stubs and updating the signature baseline after approved breaking or non-breaking API changes.

## Where to Start

- Stub generation: `tools/devx/foundry/generate_stubs.py`.
- Signature baseline refresh: `tools/devx/foundry/update_signature_baseline.py`.
- Written outputs:
  `src/polisyos/foundry/methods/{base,registry,composer}.pyi`.

- Baseline artifact:
  `tests/_golden/foundry/signature_baseline.json`.

## Public Entrypoints

| Entrypoint                                                            | Purpose                                                     |
| --------------------------------------------------------------------- | ----------------------------------------------------------- |
| `uv run polisyos-tools foundry generate-stubs [--dry-run]`            | Regenerate public method stubs for the Foundry facade.      |
| `uv run polisyos-tools foundry update-signature-baseline [--dry-run]` | Recompute stable digests and update the signature baseline. |

## Depends On / Depended On By

- **Depends on:** `polisyos.foundry.methods.*`, `mypy.stubgen`, registry
  snapshotting in `MethodRegistry`, and the baseline fixture under `tests/unit/foundry`.

- **Depended on by:** Foundry public-surface reviews, signature compatibility
  tests, release closeout, and manual ABI-drift investigations.

## Common Commands

The commands below were smoke-tested on `2026-04-17` unless explicitly marked as `conceptual`.

| Command                                                             | Purpose                                                                | Status                                                                                                         |
| ------------------------------------------------------------------- | ---------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `uv run polisyos-tools foundry generate-stubs --dry-run`            | Check stub generation without writing `.pyi` files.                    | `smoke-tested` (the command starts, but the current environment configuration does not execute `mypy.stubgen`) |
| `uv run polisyos-tools foundry update-signature-baseline --dry-run` | Check the signature diff without rewriting the baseline fixture.       | `smoke-tested` (currently fails on a `RegistrySnapshot`/`.items()` mismatch)                                   |
| `uv run polisyos-tools foundry generate-stubs`                      | Write the regenerated `.pyi` stubs to `src/polisyos/foundry/methods/`. | `conceptual` (modifies checked-in artifacts)                                                                   |
| `uv run polisyos-tools foundry update-signature-baseline`           | Update `tests/_golden/foundry/signature_baseline.json`.                | `conceptual` (modifies a checked-in artifact)                                                                  |

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

- Stub generation currently covers `polisyos.foundry.methods.base`,
  `registry`, and `composer`.

- The signature baseline is stored in test fixtures for deliberate ABI
  review and to prevent silent drift.

- The canonical surface is `polisyos-tools foundry ...`; product-root
  `scripts/` were retired during the Repository SOTA closeout.

- Last updated: 2026-04-17
