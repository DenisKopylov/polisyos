"""Tests for Phase 2.5 data transformation pipeline."""
from __future__ import annotations

import pandas as pd
import pytest

try:
    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st

    HYPOTHESIS_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    HYPOTHESIS_AVAILABLE = False

from polisyos.fabric.connectors.contracts import (
    Additivity,
    DataSchema,
    FieldSpec,
    SchemaType,
    SchemaVersion,
    TimeGranularity,
)
from polisyos.fabric.connectors.transform import (
    CompletenessRule,
    TemporalType,
    TransformContext,
    TransformError,
    TransformPipeline,
)


@pytest.fixture
def sample_schema_daily() -> DataSchema:
    return DataSchema(
        schema_id="test.daily",
        version=SchemaVersion(1, 0, 0),
        fields=(
            FieldSpec(name="date", data_type=SchemaType.DATETIME),
            FieldSpec(name="store_id", data_type=SchemaType.STRING),
            FieldSpec(
                name="inventory",
                data_type=SchemaType.FLOAT64,
                additivity=Additivity.SEMI_ADDITIVE,
            ),
            FieldSpec(name="sales", data_type=SchemaType.FLOAT64),
        ),
        primary_key=("date",),
        time_dimension="date",
        time_granularity=TimeGranularity.DAILY,
    )


def test_builder_pattern_chaining() -> None:
    pipeline = (
        TransformPipeline().normalize(field_mappings={"A": "a"}).impute_missing(strategy="linear")
    )

    assert len(pipeline._stages) == 2
    assert pipeline._stages[1].dependencies == [pipeline._stages[0].name]


def test_topological_sort_stable_for_independent_nodes() -> None:
    pipeline = TransformPipeline(auto_chain=False)

    pipeline.normalize(field_mappings={"A": "a"})
    pipeline.impute_missing(strategy="linear")
    pipeline.validate(rules=[CompletenessRule("a")])

    compiled = pipeline.compile()
    assert compiled.execution_order == [
        pipeline._stages[0].name,
        pipeline._stages[1].name,
        pipeline._stages[2].name,
    ]


def test_cycle_detection() -> None:
    pipeline = TransformPipeline()
    pipeline.normalize(field_mappings={"A": "a"})
    pipeline.impute_missing(strategy="linear")

    # Inject cycle (A -> B and B -> A)
    pipeline._graph.add_edge(pipeline._stages[1].name, pipeline._stages[0].name)

    with pytest.raises(TransformError, match="contains cycles"):
        pipeline.compile()


def test_lineage_tree() -> None:
    data = pd.DataFrame({"A": [1, 2, 3], "B": [1.0, None, 3.0]})
    pipeline = (
        TransformPipeline()
        .normalize(field_mappings={"A": "a"})
        .impute_missing(strategy="linear")
        .validate(rules=[CompletenessRule("a")])
    )

    result = pipeline.apply(data, TransformContext())

    assert result.lineage.stage_name == "pipeline"
    assert len(result.lineage.parent_lineages) == 3


def test_warning_propagation_from_apply() -> None:
    data = pd.DataFrame({"value": [1.0, None, None, None, 5.0]})
    pipeline = TransformPipeline().impute_missing(
        strategy="linear",
        max_missing_pct=0.2,
    )
    result = pipeline.apply(data, TransformContext())
    assert any("missing" in warning for warning in result.warnings)


def test_stock_sum_over_time_corrected(sample_schema_daily: DataSchema) -> None:
    data = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=31, freq="D"),
            "inventory": [1000] * 31,
            "sales": [10] * 31,
        }
    )

    pipeline = TransformPipeline().aggregate(
        by=[pd.Grouper(key="date", freq="MS")],
        aggregations={"inventory": "sum", "sales": "sum"},
        temporal_context={"inventory": TemporalType.STOCK, "sales": TemporalType.FLOW},
    )

    result = pipeline.apply(data, TransformContext(source_schema=sample_schema_daily))

    # Inventory should NOT be summed across time
    inv = result.data["inventory"].iloc[0]
    assert inv == 1000
    assert any("inventory" in warning for warning in result.warnings)


def test_stock_sum_across_entities_allowed(sample_schema_daily: DataSchema) -> None:
    data = pd.DataFrame(
        {
            "date": ["2024-01-01"] * 2 + ["2024-01-02"] * 2,
            "store_id": ["A", "B", "A", "B"],
            "inventory": [100, 200, 150, 250],
            "sales": [1, 2, 3, 4],
        }
    )

    pipeline = TransformPipeline().aggregate(
        by=["date"],
        aggregations={"inventory": "sum"},
        temporal_context={"inventory": TemporalType.STOCK},
    )

    result = pipeline.apply(data, TransformContext(source_schema=sample_schema_daily))
    # Sum across entities (stores) for the same date is allowed
    assert result.data["inventory"].iloc[0] == 300


def test_non_additive_sum_corrected() -> None:
    schema = DataSchema(
        schema_id="test.nonadd",
        version=SchemaVersion(1, 0, 0),
        fields=(
            FieldSpec(
                name="date",
                data_type=SchemaType.DATETIME,
            ),
            FieldSpec(
                name="price_index",
                data_type=SchemaType.FLOAT64,
                additivity=Additivity.NON_ADDITIVE,
            ),
        ),
        primary_key=("date",),
        time_dimension="date",
        time_granularity=TimeGranularity.DAILY,
    )

    data = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=5, freq="D"),
            "price_index": [1.0, 1.1, 1.2, 1.1, 1.0],
        }
    )

    pipeline = TransformPipeline().aggregate(
        by=["date"],
        aggregations={"price_index": "sum"},
    )

    result = pipeline.apply(data, TransformContext(source_schema=schema))
    assert any("non-additive" in warning for warning in result.warnings)


if HYPOTHESIS_AVAILABLE:

    @settings(
        max_examples=150,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    @given(
        data=st.data(),
        n_rows=st.integers(min_value=10, max_value=200),
    )
    def test_aggregation_never_increases_row_count(data: st.DataObject, n_rows: int) -> None:
        groups = data.draw(
            st.lists(
                st.integers(min_value=0, max_value=10),
                min_size=n_rows,
                max_size=n_rows,
            )
        )
        values = data.draw(
            st.lists(
                st.floats(
                    min_value=-1e6,
                    max_value=1e6,
                    allow_nan=False,
                    allow_infinity=False,
                ),
                min_size=n_rows,
                max_size=n_rows,
            )
        )

        df = pd.DataFrame({"group": groups, "value": values})

        pipeline = TransformPipeline().aggregate(
            by=["group"],
            aggregations={"value": "sum"},
        )

        result = pipeline.apply(df, TransformContext())
        assert len(result.data) <= n_rows
else:

    def test_aggregation_never_increases_row_count() -> None:  # pragma: no cover
        pytest.skip("hypothesis not installed")
