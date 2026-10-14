# Data Quality Validation

Supplemental implementation notes. The canonical published summary is the
[Fabric Quality reference](../reference/fabric/quality.md), which carries the
current source pin and validation limits.

This page describes the current Fabric connector quality validator. The dated Phase 2.6 design
specification is historical; its original three-component weights are not the current defaults.

Source behavior was inspected at repository pin `bafca83bff9ff49eef1466bc491a8420b5cd1dbb` in
`src/polisyos/fabric/connectors/quality/validator.py`,
`src/polisyos/core/evaluation/scoring.py`, and
`src/polisyos/fabric/connectors/quality/completeness.py`. The cited test source was inspected, not
executed, for this documentation update.

## Quick Start

```text
from polisyos.fabric.connectors.quality import DataQualityValidator

validator = DataQualityValidator()
report = validator.validate(fetch_result, schema)

if report.needs_attention:
    print(report.summary())
```

## What It Checks

- Freshness: cache age and data age against the inferred or configured schedule.
- Completeness: nulls, required fields, and time-series gaps.
- Consistency: bounds, allowed values, regular expressions, and data types.
- Profile and anomaly scores: calculated for every call to `validate`.
- Drift: calculated when `baseline_data` is supplied.
- Quality-contract results: calculated when `quality_contract` is supplied.

## Scoring

`QualityScorer.__init__` starts with these seven weights:

| Component | Default weight |
| --- | ---: |
| Freshness | 0.25 |
| Completeness | 0.30 |
| Consistency | 0.25 |
| Profile | 0.08 |
| Anomaly | 0.06 |
| Drift | 0.04 |
| Contract | 0.02 |

The defaults sum to 1.0. `WeightedScorer` normalizes configured weights and renormalizes over the
components that have scores. Thus drift and contract do not contribute when their corresponding
inputs are absent; they are not silently scored as zero. The generic validator always supplies
profile and anomaly scores, supplies drift only with `baseline_data`, and supplies contract only
with `quality_contract`.

Tier thresholds are Platinum >= 0.95, Gold >= 0.85, Silver >= 0.70, and Bronze < 0.70. A hard
completeness or consistency failure, or a blocking contract rule, caps the final score at 0.69.

## Sampling and Coverage Limits

The validator samples large datasets for some checks. Time-series gap detection uses the full
time series, and consistency checks can use full data for categorical and pattern checks.

`CompletenessAnalyzer.analyze` accepts `expected_row_count`, but
`DataQualityValidator._check_completeness` always passes `expected_row_count=None`. The generic
`validate(fetch_result, schema, ...)` path therefore does not currently wire an expected-total
coverage check, even when an expected count exists elsewhere.

## Evidence and Governance Bridge

`DataQualityReport.to_evidence()` produces the report's evidence payload. The existing governance
consumer is `QualityGatePass` in `src/polisyos/scientist/governance/passes/quality_gate_pass.py`;
when `ctx.state["data_quality_report"]` is present it consumes that report, attaches Fabric
quality evidence, and derives `QualityIndicators`. Otherwise it uses the existing evidence-bundle
path. This consumer does not imply that every connector workflow automatically constructs or
attaches a report.

Core validator coverage is in `tests/unit/fabric/connectors/test_quality_system.py`. That test
source was inspected but not run during this documentation update.
