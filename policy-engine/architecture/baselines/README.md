# Architecture Baselines

This directory is the canonical home for architecture freeze baselines such as
deep import graphs, public-surface snapshots, topology inventories, and
generated artifact drift baselines.

Existing root-level baseline files should move here only after the guardrails
and docs that read them are updated.

Tracked migration:

- `architecture/deep_import_baseline.json` ->
  `architecture/baselines/deep_import_baseline.json`, registered as
  `architecture-deep-import-baseline-to-baselines` in
  `architecture/migration_shims.toml`.
