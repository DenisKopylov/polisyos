# Core Tests

`tests/core` covers the shared `polisyos.core` substrate: artifacts, security,
components, contracts, trace/audit helpers, and the phase0 execution
primitives. The slice currently contains `69` `test_*.py` files.

## Purpose

- Keep the platform substrate stable for `ir`, `fabric`, `foundry`,
  `scientist`, and `runtime`.
- Catch regressions in security boundaries, component discovery, and registry
  contracts before they leak into higher layers.
- Preserve the phase0 CAS, canon, signing, run-context, and observability
  guarantees that many other slices reuse.

## Where To Start

- [`../../src/polisyos/core/README.md`](../../src/polisyos/core/README.md) for
  the code-side subsystem boundary.
- [`phase0/README.md`](phase0/README.md) for the deepest artifact/run/canon
  coverage.
- `security/`, `components/`, and `contracts/` when the change touches auth,
  package facades, or typed execution contracts.

## Public Entrypoints

- `tests/core/` root: `10` direct tests for cache, pipeline, registry, hashing,
  scoring, and discovery primitives.
- `tests/core/phase0/`: `23` tests for artifacts, canon, signing,
  observability, and run lifecycle.
- `tests/core/security/`: `20` tests for identity, authz, tenant, router, and
  related runtime guards.
- `tests/core/components/`: `4` tests for component discovery and legacy entry
  point compatibility.
- `tests/core/contracts/`: `2` tests for execution-plan and facade-level
  contract checks.

## Depends On / Depended On By

**Depends on**

- [`../../src/polisyos/core/README.md`](../../src/polisyos/core/README.md)
- `src/polisyos/core/security`, `src/polisyos/core/components`,
  `src/polisyos/core/contracts`
- `tests/conftest.py` and `tests/core/phase0/conftest.py`

**Depended on by**

- [`../contract/README.md`](../contract/README.md),
  [`../runtime/README.md`](../runtime/README.md),
  [`../foundry/README.md`](../foundry/README.md), and
  [`../scientist/README.md`](../scientist/README.md)
- The fast local loop described in [`../TESTING_POLICY.md`](../TESTING_POLICY.md)

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: full core slice
uv run pytest tests/core -q

# conceptual: focused slices
uv run pytest tests/core/security -q
uv run pytest tests/core/components -q
uv run pytest tests/core/contracts -q
uv run pytest tests/core/phase0 -q
```

## Test And Verification Commands

The collect-only commands below were smoke-checked on `2026-04-17`.

```bash
cd policy-engine
uv run pytest --collect-only tests/core -q
uv run pytest --collect-only tests/core/phase0 -q
```

## Reference Docs

- [`phase0/README.md`](phase0/README.md)
- [`../../src/polisyos/core/README.md`](../../src/polisyos/core/README.md)
- [`../TESTING_POLICY.md`](../TESTING_POLICY.md)
- [`../README.md`](../README.md)

## Last Updated

2026-04-17
