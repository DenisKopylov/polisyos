# Architecture Package Contracts

Phase 5.8 makes `architecture/packages/*.toml` the primary package architecture
source of truth. Existing aggregate contracts stay in place as generated or
mirrored legacy views until their gates switch to package-contract generation.

Each aggregate package in `architecture/packages/boundaries.toml` or
`architecture/public_surface/contract.toml` must have exactly one primary contract file
here. The report-only validator treats missing primary files and aggregate
mirror drift as contract errors, while the gates themselves remain report-only
until the Wave 6 fail-closed conversion plan is accepted.

When adding a package:

1. Add exactly one primary package contract under this directory.
2. Mirror or generate aggregate entries in the legacy TOML files named by the
   package contract.
3. Declare owner, layout status, boundaries, public surface, tests,
   SLO/runbook expectations, allowed name collisions, exceptions, sunsets, and
   extension host status in that one contract.
4. Keep every new gate in `architecture/gates/report_only.toml` until it has an
   owner, evidence, and an accepted fail-closed conversion plan.
