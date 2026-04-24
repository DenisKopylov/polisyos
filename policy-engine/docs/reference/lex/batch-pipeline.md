# Lex Batch Pipeline

Related explanation: [Lex Pipeline](../../explanation/lex-pipeline.md).

Owner: `@lex-owners`
Source of truth: `src/polisyos/lex/batch/**`, `src/polisyos/lex/batch/config.py`, and `tests/lex/batch/**`

The Lex batch pipeline converts raw legal documents into grounded facts,
reference edges, amendment records, and temporal envelopes. Phase 2 extends
this layer with deterministic amendment extraction, hallucination screening,
and status-aware temporal resolution for UA legislation.

## Key Stages

| Stage                    | Purpose                                                        | Primary API                                     |
| ------------------------ | -------------------------------------------------------------- | ----------------------------------------------- |
| Deterministic extraction | Extract SPO-style legal facts from provision text              | `lex.batch.pipeline`, `lex.batch.spo_extractor` |
| Quality filtering        | Reject synthetic or low-signal entity spans                    | `lex.batch.quality_filters`                     |
| Hallucination screening  | Detect ungrounded articles, numbers, and norm-type mismatches  | `lex.batch.hallucination_detector`              |
| Amendment extraction     | Identify replace/add/remove/repeal amendment patterns          | `lex.batch.amendment_detector`                  |
| Temporal resolution      | Infer `current`, `historical`, `suspended`, or `future` status | `lex.batch.temporal_resolver`                   |
| QC metrics               | Summarize amendment coverage and blocking rates                | `lex.batch.amendment_metrics`                   |

## Operational Notes

- The quality filters are intentionally Ukrainian-specific because the
  deterministic pattern library is optimized for UA statutes and regulations.

- Temporal resolution merges publication metadata, status strings, and inline
  effective-date text before assigning a document or fact temporal state.

- Amendment metrics distinguish row-level extraction coverage from
  single-target document resolution rates.

## Reference

::: polisyos.lex.batch.amendment_detector

::: polisyos.lex.batch.hallucination_detector

::: polisyos.lex.batch.quality_filters

::: polisyos.lex.batch.temporal_resolver

::: polisyos.lex.batch.amendment_metrics
