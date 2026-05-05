# Data Forge Legal Batch Pipeline

Related explanation: [Lex Pipeline](../../explanation/lex-pipeline.md).

Owner: `@data-forge-owners`
Source of truth: `src/polisyos/data_forge/domains/legal/batch/**`,
`src/polisyos/data_forge/domains/legal/corpus/**`, and
`tests/unit/data_forge/legal_batch/**`

The legal batch pipeline is now an offline Data Forge surface. It converts raw
legal documents into grounded facts, reference edges, amendment records,
temporal envelopes, QC reports, benchmark summaries, and publish artifacts.

Runtime Lex reads the published outputs through `polisyos.lex.knowledge` and
`polisyos.data_forge.read_api.legal`; it no longer owns batch preprocessing.

## Key Stages

| Stage                    | Purpose                                                        | Primary API                                               |
| ------------------------ | -------------------------------------------------------------- | --------------------------------------------------------- |
| Deterministic extraction | Extract SPO-style legal facts from provision text              | `data_forge.domains.legal.batch.pipeline`                 |
| Quality filtering        | Reject synthetic or low-signal entity spans                    | `data_forge.domains.legal.batch.quality_filters`          |
| Hallucination screening  | Detect ungrounded articles, numbers, and norm-type mismatches  | `data_forge.domains.legal.batch.hallucination_detector`   |
| Amendment extraction     | Identify replace/add/remove/repeal amendment patterns          | `data_forge.domains.legal.batch.amendment_detector`       |
| Temporal resolution      | Infer `current`, `historical`, `suspended`, or `future` status | `data_forge.domains.legal.batch.temporal_resolver`        |
| QC metrics               | Summarize amendment coverage and blocking rates                | `data_forge.domains.legal.batch.amendment_metrics`        |

## Operational Notes

- The quality filters are intentionally Ukrainian-specific because the
  deterministic pattern library is optimized for UA statutes and regulations.

- Temporal resolution merges publication metadata, status strings, and inline
  effective-date text before assigning a document or fact temporal state.

- Amendment metrics distinguish row-level extraction coverage from
  single-target document resolution rates.

## Reference

::: polisyos.data_forge.domains.legal.batch.amendment_detector

::: polisyos.data_forge.domains.legal.batch.hallucination_detector

::: polisyos.data_forge.domains.legal.batch.quality_filters

::: polisyos.data_forge.domains.legal.batch.temporal_resolver

::: polisyos.data_forge.domains.legal.batch.amendment_metrics
