# Freeze Policy v2 (P1 Import Policy v2 aligned)

## Purpose

The freeze policy records the current state of architectural debt and prohibits its growth until the end of P1. `Import Policy v2` applies to imports.

## Rules

1. The number of package cycles must not increase.
2. The number of import violations must not increase.
3. Unmanaged import violations (`import_violations_count > 0`) are prohibited under P1 Import Policy v2.
4. New exceptions are allowed only when these fields are populated:

   - `id`
   - `owner`
   - `reason`
   - `expires`

5. `expires` must be no more than 90 days after the PR review date.
6. Expired exceptions are prohibited.
7. New changes must not use deep imports into other packages' internal/private modules.
8. All active import exceptions must be listed in `architecture/imports/exceptions.md` and linked to the P1 backlog.

## Enforcement

- Metrics are collected by `tools/quality/lint/collect_arch_metrics.py`.
- `tools/quality/lint/compare_baseline.py` compares the baseline with the current state.
- CI workflow: `/.github/workflows/arch-freeze.yml`.
- Blocking mode is enabled for `pull_request`.
- The deep-import freeze (`ARCH004/ARCH006`) is checked against the baseline/current diff in `import_gate.txt`.

## Exception Policy

- Exception registry: `architecture/imports/exceptions.md`.
- Technical source of truth: `architecture/imports/exceptions.toml`.
- Each exception must have an owner and an expiry date.
- Expired or invalid exceptions block merge.
