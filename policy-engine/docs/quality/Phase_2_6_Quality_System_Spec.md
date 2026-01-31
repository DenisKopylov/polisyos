# Phase 2.6 Quality System Specification

Date: 2026-01-31
Version: 1.0

## Executive Summary

This specification defines the Data Quality and Freshness system for the Fabric connector layer. The system validates FetchResult data against DataSchema expectations and produces a scored DataQualityReport that integrates with QualityIndicators and QualityGatePass.

Design principles:
- Integration over reinvention (build on existing QualityIndicators)
- Soft failures (warn and downgrade instead of crashing)
- Performance aware (sampling with check-aware exceptions)
- Evidence friendly (report can be serialized for audit)

## Architecture Overview

Flow:
1. FetchResult + DataSchema
2. DataQualityValidator
   - FreshnessChecker
   - CompletenessAnalyzer
   - ConsistencyChecker
   - QualityScorer
3. DataQualityReport
4. Integration with QualityIndicators and QualityGatePass

## Core Structures

- FreshnessStatus (level, cache age, data age, TTL, schedule)
- RuleViolation (rule_type, field_name, severity, message, expected, actual)
- CompletenessResult (score, violations, gaps_detected, hard_fail)
- ConsistencyResult (score, violations)
- DataQualityReport (score, tier, grade, violations, warnings)

## Freshness Checking

Key concepts:
- Cache age: time since fetch
- Data age: time since source update

Policies:
- Default policies for real-time, hourly, daily, weekly, monthly, quarterly, annual
- Custom policies per dataset or schedule
- Adaptive TTL uses update_interval when available (not data age)

Schedule inference:
- Metadata schedule and update_frequency hints when valid
- Dataset_id keywords
- Connector capability streaming
- Default to daily

## Completeness Analysis

Checks:
- Per-field null percentage vs expected_completeness
- Missing required fields (hard fail)
- Time series gap detection using schema time_dimension and time_granularity
- Optional coverage check when expected_row_count is known

Scoring:
- Base score from average completeness
- Penalties scale by gap size and severity
- Missing required fields force hard_fail and score 0

## Consistency Validation

Checks:
- Numeric bounds
- Categorical allowed values
- Regex patterns
- Data type mismatches

Scoring:
- Penalties based on proportion of invalid values
- Severity weighting based on invalid ratio

## Quality Scoring

Weighted aggregation:
- freshness 0.3
- completeness 0.4
- consistency 0.3

Tier thresholds:
- Platinum >= 0.95
- Gold >= 0.85
- Silver >= 0.70
- Bronze < 0.70

Hard fails cap score to Bronze.

## Validator Flow

1. Extract data into DataFrame
2. Sampling for large datasets
3. Freshness check
4. Completeness analysis (gap detection uses full time series)
5. Consistency checks (categorical/patterns use full data)
6. Score and grade
7. Build DataQualityReport and QualityIndicators

## Integration

- QualityIndicators.from_quality_report(report)
- QualityGatePass uses data_quality_report when present
- Evidence: DataQualityReport.to_evidence returns a stable dict payload

## Error Handling

- Errors in checks are caught and downgraded
- Validation returns a Bronze report on failure

## Performance

- Sampling threshold default: 100k rows
- Gap detection uses time column values from full data
- Categorical and pattern checks use full data to avoid sampling blind spots

## Testing

See tests/fabric/connectors/test_quality_system.py for core coverage.

## Future Enhancements

- Schema drift detection
- Cross-column constraints
- Outlier detection extensions
- EvidenceRef integration in core contracts
