---
title: Data Forge Cutover Readiness
status: completed
owner: team-data-forge
created: 2026-05-02
last_verified: 2026-05-05
stability: final
---

# Data Forge Cutover Readiness

- Status: completed
- Owner: team-data-forge
- Completed: 2026-05-02
- Repository revision recorded for cutover work: `3f7af28e59e34e547026c89ed6038ffc2be7d543`
- Accepted Lex artifact root: `production_data/lex_current_20260501`

## Owner Sign-Off

The NPA processing queue is complete enough for Data Forge Legal cutover. The
owner accepted the full Lex artifacts under
`production_data/lex_current_20260501` as immutable replay evidence for Phase 0
and Phase 4. The benchmark report still records advisory/readiness failures for
reference-resolution and temporal-current-safety thresholds, but the owner
explicitly confirmed that these artifacts are sufficient for the cutover.

## Queue 2/3 Evidence

The accepted artifact root contains the completed final Lex processing outputs
from the Queue 2/3 run family:

- `amendment_only_summary.json`
- `logs/amendment_only.stdout`
- `logs/amendment_only_driver.log`
- `logs/final_stages.stdout`
- `finalize/lex_knowledge_graph.duckdb`
- `finalize/qc_report.json`
- `finalize/benchmark_report.json`
- `finalize/claim_exports/normative_claims.jsonl`
- `finalize/claim_exports/normative_claims_summary.json`

The amendment-only queue summary records:

- Mode: `amendment_only_parallel`
- Documents in metadata: `134849`
- Amendments: `156196`
- Amendments with target: `104543`
- Amendment documents: `48785`
- Amendment documents with target: `36997`
- Elapsed seconds: `8994.469`

## Artifact Inventory

The accepted local root is intentionally large and must be treated as immutable:

- Root size: approximately `20G`
- Lex graph: `finalize/lex_knowledge_graph.duckdb`
- Normative claims JSONL: `finalize/claim_exports/normative_claims.jsonl`
- QC report: `finalize/qc_report.json`
- Benchmark report: `finalize/benchmark_report.json`
- Claim summary: `finalize/claim_exports/normative_claims_summary.json`

Claim export summary:

- Status: `ok`
- Claims: `1604211`
- Documents: `74939`

## QC And Benchmark Evidence

QC report:

- Scope: `lex`
- Passed: `true`
- Entities: `357742`
- Facts: `1980256`
- Provisions: `6074716`
- High-confidence norms: `1443585`
- Amendments total: `156196`
- Normative-ready total: `1604211`
- Normative-ready share: `100.0%`
- Reference-resolution coverage: `98.28648052117573%`
- Hallucination blocking rate: `0.0%`

Benchmark report:

- Kind: `lex_benchmark`
- Generated at: `2026-05-01T08:01:43.916136+00:00`
- Search top-5 relevance: `100.0%`
- Constraint readiness: `100.0%`
- Cross-graph non-unknown rate: `100.0%`
- Amendment extraction readiness: `99.154%`
- Amendment target resolution: `76.71%`
- Hallucination blocking clean rate: `100.0%`
- Owner-accepted failed checks:
  `benchmark_reference_resolution_ready_pct`,
  `benchmark_temporal_current_safety_pct`

## Manifest, Schema, And Layout Contract

The cutover uses the Data Forge kernel manifest contracts as the canonical
manifest surface:

- Raw manifests: `schemas/manifests/data_forge_raw_manifest_v1.schema.json`
- Stage manifests: `schemas/manifests/data_forge_stage_manifest_v1.schema.json`
- Publish manifests: `schemas/manifests/data_forge_publish_manifest_v1.schema.json`
- Artifact references: `schemas/artifacts/data_forge_artifact_ref_v1.schema.json`
- Trace metadata:
  `schemas/artifacts/data_forge_artifact_trace_metadata_v1.schema.json`
- Domain artifacts:
  `schemas/artifacts/data_forge_domain_artifact_v1.schema.json`

The accepted Legal output layout is rooted at `finalize/` and preserves the
historical Lex output names for DuckDB graph, QC, benchmark, and claim-export
artifacts. Data Forge Legal shadow tests may either point at this immutable
root or use tiny CI fixtures that preserve the same relative paths.

## Clean, Resume, Cache, And Idempotency Notes

- The accepted root is read-only input evidence for cutover tests.
- Data Forge replay tests must not mutate `production_data/lex_current_20260501`.
- Cache and resume markers are compared through legal shadow fixtures and
  Data Forge batch compatibility contracts.
- Idempotency is preserved at the compatibility layer by keeping legacy CLI and
  job entrypoints forwarding to Data Forge-owned modules until shim sunset.

## Rollback Checkpoints

Rollback for code cutover is now version-control based for removed Data Forge
and old Lex offline shims:

- Legal batch rollback: restore retired Lex offline shim entrypoints from
  version control only if a temporary compatibility release is required.
- Shared-kernel rollback: restore removed compatibility packages from version
  control only if a temporary rollback release needs the old import paths.
- Academic/catalog rollback: restore removed compatibility packages from
  version control only if a temporary rollback release needs the old import
  paths.
- Shim deletion rollback: use
  `docs/migration/data_forge_shim_sunset_rollback.md`.

## Gate Result

Phase 0 is complete. The repository may proceed with the full Data Forge
physical cutover while preserving compatibility shims until their documented
sunset gates pass.
