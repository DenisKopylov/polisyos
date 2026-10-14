# Quality Validation Integration Guide

Originally written 2026-01-31; refreshed against the current source at repository pin
`bafca83bff9ff49eef1466bc491a8420b5cd1dbb`. The named source and test files were inspected, not
executed, for this documentation update. For current checks and scoring defaults, see
[Data Quality Validation](README_Quality_System.md).

## Report-to-Governance Path

`DataQualityValidator.validate(fetch_result, schema, ...)` returns a `DataQualityReport`. A caller
that owns a governance `PassContext` can provide it in `ctx.state["data_quality_report"]` before
`QualityGatePass.validate` runs. The pass prefers that report, attaches Fabric quality evidence,
and derives the existing `QualityIndicators` format. If no report is present, it follows the
existing evidence-bundle and classic-indicator path. This is a caller-composed bridge; the source
does not establish an automatic report-producing step for every connector workflow.

The bridge is implemented in:

- `src/polisyos/scientist/governance/passes/quality_gate_pass.py`
- `src/polisyos/fabric/quality/quality.py` (`QualityIndicators.from_quality_report`)
- `src/polisyos/fabric/connectors/quality/evidence.py`

For a Bronze report, the pass emits a blocker under the `strict` profile and a warning otherwise.
Freshness and error-severity violation handling have separate profile-dependent rules in the
consumer; Bronze tier alone does not summarize every gate outcome.

## Connector-Side Use

```text
from polisyos.fabric.connectors.quality import DataQualityValidator

validator = DataQualityValidator(
    freshness_policies=freshness_policies,
    quality_weights=quality_weights,
    sampling_threshold=100_000,
)
report = validator.validate(fetch_result, schema)
```

The optional configuration above maps to the current `DataQualityValidator` constructor. The
expected-row-count coverage helper is not wired through its generic validation path; see the
[current limits](README_Quality_System.md#sampling-and-coverage-limits).

To serialize report evidence, call `report.to_evidence()`. This gives the caller a payload to
attach or persist; it does not itself persist a CAS artifact or route the report into governance.

## Focused Coverage

The validator source is covered by `tests/unit/fabric/connectors/test_quality_system.py`.
`QualityGatePass` has its own tests under `tests/unit/scientist/governance/passes/`. These sources
were inspected but not run for this documentation update. To run the connector-focused test from
`policy-engine/`:

```bash
uv run pytest tests/unit/fabric/connectors/test_quality_system.py -q
```
