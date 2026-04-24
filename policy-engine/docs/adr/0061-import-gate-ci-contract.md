# ADR-0061: Import gate as CI contract (lint_foundry.py --strict on every PR)

## Status

Proposed

## Date

2026-02-28

## Context

The foundry layer must remain a pure computational core with no upward
dependencies on scientist, fabric, or lex. Previous violations were caught only
during manual review, sometimes after merging. An automated enforcement
mechanism is needed to guarantee that foundry modules never import from
higher-level layers and that the layered architecture stays intact as the
codebase grows.

## Decision

1. Run `tools/lint/lint_foundry.py --strict` as a required CI check on every
   pull request targeting `main`.
2. The linter statically analyses import statements in `polisyos.foundry` and
   fails if any import resolves to `polisyos.scientist`, `polisyos.fabric`,
   `polisyos.lex`, or `polisyos.datasets`.
3. The `import_policy.toml` file serves as the source of truth for allowed
   cross-layer dependencies and is version-controlled alongside source code.
4. Exceptions require an explicit entry in `import_policy.toml` with a
   justification comment and an associated ADR reference.

## Consequences

### Positive

- Automated enforcement catches import violations before merge, eliminating
  reliance on reviewer vigilance.

- The `import_policy.toml` file provides a single auditable manifest of all
  cross-layer dependency exceptions.

### Negative

- False positives from dynamic imports or re-exports may require allowlist
  entries that add maintenance overhead.

- Developers working on cross-cutting features may experience friction when
  the linter rejects seemingly reasonable imports, requiring architectural
  discussion before proceeding.
