# CI Operations

`ops/ci/` stores CI support material that is not directly executed by GitHub.

- `templates/workflows/`: inactive product workflow templates retained for
  comparison and rollback while root `.github/workflows/` remains the active
  GitHub Actions control plane.
- `templates/github/`: inactive copies of product-local GitHub templates.
