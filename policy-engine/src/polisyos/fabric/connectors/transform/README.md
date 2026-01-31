# Data Transformation Pipeline (Phase 2.5)

This module implements a composable, DAG-based transformation pipeline with
lazy evaluation, full lineage tracking, and stock/flow-safe aggregation.

## Quick Start

```python
from polisyos.fabric.connectors.transform import (
    TransformPipeline,
    TransformContext,
    TemporalType,
    CompletenessRule,
)

pipeline = (
    TransformPipeline()
    .normalize(field_mappings={"GDP": "gdp_usd"})
    .harmonize_codes("country", "ISO_3166_ALPHA3")
    .aggregate(
        by=["country", "year"],
        aggregations={"gdp_usd": "sum"},
        temporal_context={"gdp_usd": TemporalType.FLOW},
    )
    .impute_missing(strategy="linear")
    .validate(rules=[CompletenessRule("gdp_usd", threshold=0.95)])
)

result = pipeline.apply(data, TransformContext())
print(result.lineage.to_dict())
print(result.warnings)
```

## Stock/Flow + Additivity

Aggregation respects both temporal semantics and additivity:

- **Additive**: sum across time and entities (flows)
- **Semi-additive**: sum across entities, NOT time (stocks)
- **Non-additive**: never sum (rates, indices)

Additivity can be specified on `FieldSpec.additivity` or passed to the
`AggregationTransform` via `additivity_context`.

## DAG Branching

Builder methods create a linear chain by default, but the engine supports
branching and joining:

```python
pipeline = TransformPipeline()

pipeline.normalize(field_mappings={"A": "a"})

left_tail = pipeline.branch(lambda p: p.impute_missing(fields=["a"]))
right_tail = pipeline.branch(lambda p: p.aggregate(by=["a"], aggregations={"a": "sum"}))

pipeline.join(
    transform=SomeCustomTransform(),
    depends_on=left_tail + right_tail,
)
```

## Copy Policy

Set `TransformContext.metadata["copy_policy"]` to control memory behavior:

- `copy`: always copy (safe)
- `cow`: copy-on-write (if pandas COW enabled)
- `inplace_if_safe`: mutate in place when possible

## Testing

Run the test suite:

```bash
pytest tests/fabric/connectors/test_transform_pipeline.py -v
```
