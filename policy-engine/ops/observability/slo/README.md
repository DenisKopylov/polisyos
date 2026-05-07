# SLO Definitions

Service-level objectives live here as code. Any SLO change should be reviewed
with the owning team and linked to an ADR or explicit release-governance note.

Each SLO file should declare:

- service
- owner
- objective name
- SLI expression
- threshold
- window
- alert policy
- rollback or triage runbook

Phase 1.6 records package-level SLO coverage expectations in
`architecture/component_observability.toml`. Public-stable components need a
real SLO file or an explicit owner-approved exception before the operability
gate moves to fail-closed enforcement.

Phase 4.9 adds component-first bundle drafts under `ops/components/<component>/`.
When both paths exist, the `ops/components/<component>/slo.yaml` file is the
bundle-local draft and `ops/observability/slo/<component>.yaml` remains the
type-cut alias for existing dashboards, rules, and docs.
