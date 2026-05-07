# Component Operability Bundles

Owner: `team-ops`
Phase: `repository-best-in-class-phase-4.9`

Phase 1.6 selected component-first operability organization. This directory is
the physical draft tree for that decision: each component has stable links for
SLO coverage or an explicit exception, alert-to-runbook routing, dashboard
mapping, runtime-contract references, and retention policy references.

The machine-readable index is [index.toml](index.toml). Existing type-cut
observability files under `ops/observability/**` remain valid aliases while
Wave 6 converts report-only checks into gates.

## Bundle Shape

Each component bundle keeps the same draft shape:

```text
ops/components/<component>/
  README.md
  slo.yaml
  alerts.yml
  dashboard.json
  runbooks.md
  runtime-contract.toml
  retention-policy.toml
```

`slo.yaml` is either a measurable SLO definition or an explicit exception with
`status: exception`, `exception_reason`, and `exception_expires`.

