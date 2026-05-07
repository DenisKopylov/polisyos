# Architecture Baselines

This directory is the canonical home for architecture freeze baselines such as
deep import graphs, public-surface snapshots, topology inventories, and
generated artifact drift baselines.

Existing root-level baseline files should move here only after the guardrails
and docs that read them are updated. Repository SOTA Phase 5 removed stale
planned migration entries from `architecture/shims.toml`; future
baseline relocations need a fresh wrapper or reader update plus closeout
evidence.

`repository_best_in_class_phase0_4/` stores the report-only verification
inventory used by the Repository Best-In-Class remediation plan: source/test
mirror baselines, fixture/data layout, property coverage, benchmark topology,
and pytest root/conftest layering.
