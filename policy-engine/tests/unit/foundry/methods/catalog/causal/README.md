# Causal Method Catalog Tests

Owner: `team-foundry`
Last updated: 2026-05-05

## Purpose

This subtree mirrors `src/polisyos/foundry/methods/catalog/causal/` and pins
causal method behavior, registration, diagnostics, and compatibility.

## Public API

Tests may import public catalog exports and package-private helpers only when
the helper is the behavior under characterization.

## Internal Layout

Flat `test_*.py` files are grouped by causal concept or method family. There
are no nested fixture packages in this directory.

## Extension Points

External causal method examples should be tested under `examples/extensions/`
or the broader Foundry extension tests, not in this builtin catalog mirror.

## Tests

Run from `policy-engine/`:

```bash
uv run pytest tests/unit/foundry/methods/catalog/causal -q
```

## Operability Links

- `src/polisyos/foundry/methods/catalog/causal/README.md`
- `src/polisyos/foundry/methods/catalog/causal/AUTHORING.md`

## Known Shims/Deprecations

Keep characterization tests for deprecated method IDs until the source shim is
removed.
