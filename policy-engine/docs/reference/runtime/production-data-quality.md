# Production Data Quality Reports

Freshness: 2026-05-13.
Owner: `team-data-forge`, `team-runtime`
Source: Phase 5.1 of `docs/plans/active/POLICYOS_BEST_IN_CLASS_PRODUCTION_QUALITY_REMEDIATION_PLAN.md`

Serious data-backed runs emit a runtime-owned
`production_data_quality_report_ref`. The report is built from the materialized
production data evidence used by the run, not from a fixture-only test payload.
It does not change Foundry method behavior in Phase 5.1; it adds diagnostics and
approval gates around the data backing the recommendation.

## Runtime Surfaces

| Surface | Field |
| --- | --- |
| Materialization refs | `auto_data_source_refs.production_data_quality_report_ref` |
| Runtime quality refs | `runtime_quality_refs.production_data_quality_report_ref` |
| Report index | `reports_index.production_data_quality_report_ref` |
| Quality evidence bundle | `quality_evidence/production_data_quality.json` |
| Scorecard evidence refs | `evidence_refs.production_data_quality_report_ref` |
| Production data context | `production_data_evidence_context.timeline[]` and `production_data_evidence_context.lineage[]` |

The report also names:

- source bundle versions;
- production manifest path and checksum;
- `data_snapshot_ref`;
- `input_bindings_ref`;
- `registry_bundle_ref`;
- legacy Fabric `quality_report_ref`;
- row counts and entity counts by source bundle;
- diagnostics and claim-level data-quality attachment.

## Diagnostics

Each report contains these diagnostic groups:

| Diagnostic | Purpose |
| --- | --- |
| `schema_drift` | Expected columns, required files, manifest/bundle shape, and fixture-like evidence. |
| `missingness` | Column and metric missing-rate checks. |
| `outliers` | Numeric outlier-ratio checks. |
| `duplicate_entity_collisions` | Duplicate entity/time observations. |
| `unit_drift` | Data-need unit expectations against dictionary units. |
| `temporal_leakage` | Observations after the run as-of timestamp. |
| `cohort_leakage` | Holdout, test, future, or post-treatment cohorts in production materialization. |
| `label_quality` | Label audit markers and label-quality metadata. |
| `construct_validity` | Requested metrics and claim data refs against observed columns and dictionary metrics. |
| `coverage` | Geography, time, and population coverage. |
| `recency_ttl` | Bundle `updated_at` or `generated_at` age against TTL. |
| `data_dictionary` | Dictionary presence and required column metadata completeness. |

## Approval Behavior

Missing or fixture-like production evidence in `research`, `governed`, or
`production` profiles fails closed with `production_data_quality_missing`.

If diagnostics fail for a major data-backed recommendation, the scorecard blocks
production approval. A signed or otherwise explicit degrade reason can downgrade
the data-quality failure to a warning, but serious profiles still require
override handling before approval.

## Operator Checklist

1. Confirm `production_data_quality_report_ref` exists in run params, job
   progress, and the report index.
2. Open the report and verify the manifest checksum and source bundle versions
   match the intended production snapshot.
3. Inspect `issues[]`; failures with `affects_major_recommendation=true` are
   approval blockers unless a degrade reason is attached.
4. Check `claim_diagnostics[]` to see which major claims are affected.
5. Use `production_data_evidence_context.lineage[]` and
   `production_data_evidence_context.timeline[]` to connect the report back to
   the materialized snapshot, input bindings, registry bundle, and Fabric trace.
