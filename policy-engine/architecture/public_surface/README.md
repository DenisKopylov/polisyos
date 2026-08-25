# Public Surface Snapshots

This directory stores generated public-surface inventories grouped by package.
`architecture/public_surface/contract.toml` defines the policy; generated JSON files
capture exported names and signatures for drift checks.

Data Forge must be included from its first implementation phase.

## Snapshot Rules

1. Policy lives in `architecture/public_surface/contract.toml`.
2. Generated inventories live in this directory and are refreshed by the
   existing architecture writer:

   ```text
   uv run python tools/devx/architecture/guardrails.py sync --skip-deep-import-baseline
   ```

3. `exports: []` is valid only while the corresponding package is explicitly
   marked as planned or pre-implementation. Once code exists, the package must
   either expose a stable facade or mark every internal module as unsupported.
4. Signature changes in public exports require review by the package owner and,
   when breaking, a SemVer decision under ADR-0118.
