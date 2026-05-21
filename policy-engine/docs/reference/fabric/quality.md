# Fabric Quality

Related explanation: [Data Fabric](../../explanation/data-fabric.md).

Freshness: 2026-04-27.
Owner: `@fabric-owners`
Source plan: `docs/plans/active/FABRIC_AUDIT_REMEDIATION_PLAN.md`, D1-L2 section in `docs/plans/active/DOCUMENTATION_SOTA_PLAN.md`
Source of truth: `src/polisyos/fabric/quality/quality.py`, `src/polisyos/fabric/quality/fitness_report.py`, `src/polisyos/fabric/connectors/quality/**`, `tests/unit/fabric/test_quality_indicators.py`, `tests/unit/fabric/connectors/test_quality_{system,statistics}.py`
Best-in-class inventory: [best-in-class-inventory.md](best-in-class-inventory.md)

Fabric currently exposes two quality layers that are both active in code.

## Metric-Level Quality Indicators

| Surface                               | Current behavior                                                                                   |
| ------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `QualityIndicators`                   | Stores missingness, staleness, coverage, row count, schema drift, and outlier ratio for one metric |
| `QualityThresholds`                   | Provides `fast`, `mvp`, and `strict` threshold sets for scoring                                    |
| `QualityLevel`                        | Ordered levels: `excellent`, `good`, `acceptable`, `poor`, `unusable`                              |
| `compute_quality_indicators()`        | Computes indicators from a dataframe and records a quality score metric                            |
| `compute_quality_from_duckdb()`       | Computes the same indicators from one DuckDB table after validating the table identifier           |
| `DataFitnessReport` / `MetricFitness` | Aggregates metric-level results into a run-level pass/fail summary                                 |

`tests/unit/fabric/test_quality_indicators.py` is the executable source for:

- missingness, coverage, staleness, and outlier calculations;
- rejection of non-finite values;
- clamping future timestamps to zero staleness;
- schema-drift penalty behavior;
- safe DuckDB table-name enforcement;
- `DataFitnessReport.from_dict()` diagnostics and counter preservation.

## Dataset-Level Validation Stack

| Component           | Module                                                      | Current role                                                                                                            |
| ------------------- | ----------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Freshness           | `connectors.quality.freshness`                              | TTL/schedule-based freshness status with clock-skew tolerance                                                           |
| Completeness        | `connectors.quality.completeness`                           | Required-field completeness and time-gap detection                                                                      |
| Consistency         | `connectors.quality.consistency`                            | Bounds, categorical, and non-finite validation                                                                          |
| Profiling           | `connectors.quality.statistics.profile_dataframe()`         | Dataset/column profile generation                                                                                       |
| Anomaly detection   | `connectors.quality.statistics.detect_anomalies()`          | Statistical anomaly findings                                                                                            |
| Drift detection     | `connectors.quality.statistics.detect_drift()`              | Numeric and categorical drift tests against a baseline                                                                  |
| Contract rules      | `connectors.quality.statistics.evaluate_quality_contract()` | Inline YAML or file-backed quality contracts                                                                            |
| Aggregate validator | `connectors.quality.validator.DataQualityValidator`         | Produces `DataQualityReport` with scores, tier, grade, component breakdown, and optional drift/anomaly/contract results |

`DataQualityValidator` currently weights the aggregate score across freshness,
completeness, consistency, profile, anomaly, drift, and contract sub-scores.
Its default tier mapping is:

| Score threshold | Tier       |
| --------------- | ---------- |
| `>= 0.95`       | `platinum` |
| `>= 0.85`       | `gold`     |
| `>= 0.70`       | `silver`   |
| `< 0.70`        | `bronze`   |

`tests/unit/fabric/connectors/test_quality_system.py` and
`tests/unit/fabric/connectors/test_quality_statistics.py` cover:

- freshness-policy inference and injected metrics;
- completeness gap detection on time dimensions;
- consistency violations for bounds, categories, and non-finite numerics;
- dataset profiles, anomaly findings, drift findings, and quality trend deltas;
- inline YAML quality contracts that can fail validation.

## Evidence And Downstream Use

| Surface                           | Current evidence                                                                                                                                                               |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `DataQualityReport.to_evidence()` | Builds a content-hashed evidence payload with score, tier, freshness, completeness, consistency, anomaly, drift, and contract-failure counts                                   |
| `build_fabric_quality_governance_evidence()` | Normalizes a quality report into `fabric.quality.evidence.v1` for Scientist governance state, including quality indicators and contract status                                  |
| `DataFitnessReport`               | Generates ASCII or Markdown summaries for governance/logging/UI paths                                                                                                          |
| Orchestrated ingestion            | `tests/unit/fabric/data_plane/test_orchestrator.py` shows `run_orchestrated_ingestion(..., produce_snapshot=True)` persisting `fabric.quality_report` before `fabric.data_snapshot` |
| Scientist quality gate            | `tests/unit/fabric/test_observability_governance_quality_phase4.py` checks that strict validation profiles receive `fabric_quality_evidence` and dataset-indexed quality evidence    |

## Safety And Boundary Rules

| Rule                                        | Current implementation evidence                                                                    |
| ------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Non-finite quality inputs are rejected      | `QualityIndicators` and validator helpers raise on `NaN`/`inf` inputs                              |
| Future timestamps are tolerated but clamped | Both freshness and quality indicator paths clamp future times instead of producing negative ages   |
| Unsafe DuckDB identifiers are rejected      | `compute_quality_from_duckdb()` validates table identifiers before querying                        |
| Quality metrics may be injected             | Quality and freshness code paths accept injected metrics instead of requiring global metric lookup |

## Validation Anchors

```bash
uv run pytest tests/unit/fabric/test_quality_indicators.py -q
uv run pytest tests/unit/fabric/connectors/test_quality_system.py -q
uv run pytest tests/unit/fabric/connectors/test_quality_statistics.py -q
uv run pytest tests/unit/fabric/test_observability_governance_quality_phase4.py -q
uv run pytest tests/unit/fabric/data_plane/test_orchestrator.py -q
```

## API Reference

::: polisyos.fabric.quality.quality

::: polisyos.fabric.quality.fitness_report

::: polisyos.fabric.connectors.quality.validator

::: polisyos.fabric.connectors.quality.report

::: polisyos.fabric.connectors.quality.evidence
