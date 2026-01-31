# Integration Guide - Phase 2.6 Quality System

Date: 2026-01-31

## 1) QualityIndicators Integration

File: `src/polisyos/fabric/quality.py`

Use the classmethod:

- `QualityIndicators.from_quality_report(report)`

This converts DataQualityReport to the existing indicator format for governance usage.

## 2) QualityGatePass Integration

File: `src/polisyos/scientist/governance/passes/quality_gate_pass.py`

Behavior:
- If `ctx.state["data_quality_report"]` exists, use it directly
- Otherwise fall back to evidence bundle and classic QualityIndicators

Bronze tier handling:
- STRICT profile -> BLOCKER
- MVP/FAST -> WARNING

## 3) Connector Workflow Usage

Typical flow:

```
from polisyos.fabric.connectors.quality import DataQualityValidator

validator = DataQualityValidator()
report = validator.validate(fetch_result, schema)

ctx.state["data_quality_report"] = report
```

Optionally attach evidence:

```
evidence_payload = report.to_evidence()
# store payload in EvidenceBundle notes or external CAS
```

## 4) Configuration

- `freshness_policies` can override default schedules
- `quality_weights` can adjust scoring emphasis
- `sampling_threshold` controls sampling cutover

## 5) Testing

Run the new tests:

```
pytest tests/fabric/connectors/test_quality_system.py -q
```

Note: governance integration tests are skipped when optional dependencies
(e.g. opentelemetry) are not installed.
