# Data Quality and Freshness System

Phase 2.6 Quality System for Fabric connectors.

## Quick Start

```text
from polisyos.fabric.connectors.quality import DataQualityValidator

validator = DataQualityValidator()
report = validator.validate(fetch_result, schema)

if report.needs_attention:
    print(report.summary())
```

## What It Checks

- Freshness: cache age vs data age, schedule aware
- Completeness: nulls, missing fields, time gaps
- Consistency: bounds, allowed values, regex patterns, data types

## Scoring

Weighted score:

- freshness 0.3
- completeness 0.4
- consistency 0.3

Tier thresholds:

- Platinum >= 0.95
- Gold >= 0.85
- Silver >= 0.70
- Bronze < 0.70

## Sampling

Sampling is applied for large datasets. Time gap detection and categorical
checks use full data to avoid sampling blind spots.

## Evidence

`DataQualityReport.to_evidence()` returns a stable dictionary payload that
can be attached to EvidenceBundle notes or stored in CAS.

## Files

- `src/polisyos/fabric/connectors/quality/`
- `tests/unit/fabric/connectors/test_quality_system.py`
