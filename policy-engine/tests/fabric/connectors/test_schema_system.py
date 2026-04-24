"""Tests for the Data Schema & Contract System."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest

try:  # optional dependency
    import jax.numpy as jnp
except Exception:  # pragma: no cover
    jnp = None

from polisyos.fabric.connectors.contracts import (
    ChangeType,
    CoercionResult,
    DataSchema,
    FieldSpec,
    FileBackedSchemaRegistry,
    GeoGranularity,
    InferenceConfig,
    InferenceResult,
    MigrationPlan,
    MigrationStatus,
    SchemaApprovalMetadata,
    SchemaEvolution,
    SchemaHints,
    SchemaInference,
    SchemaNotFoundError,
    SchemaRegistry,
    SchemaRiskLevel,
    SchemaType,
    SchemaVersion,
    SchemaVersionConflictError,
    SemanticType,
    TimeGranularity,
    coerce_dataframe_to_schema,
    infer_schema,
    validate_dataframe_against_schema,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_schema() -> DataSchema:
    """Create a sample schema for testing."""
    return DataSchema(
        schema_id="test.sample.data",
        version=SchemaVersion(1, 0, 0),
        fields=(
            FieldSpec(
                name="id",
                data_type=SchemaType.INT64,
                nullable=False,
                semantic_type=SemanticType.IDENTIFIER,
            ),
            FieldSpec(
                name="country_code",
                data_type=SchemaType.STRING,
                nullable=False,
                semantic_type=SemanticType.GEOSPATIAL,
            ),
            FieldSpec(
                name="year",
                data_type=SchemaType.INT32,
                nullable=False,
                semantic_type=SemanticType.TEMPORAL,
            ),
            FieldSpec(
                name="gdp_usd",
                data_type=SchemaType.FLOAT64,
                nullable=True,
                unit="usd",
                semantic_type=SemanticType.CURRENCY,
                bounds=(0.0, None),
            ),
            FieldSpec(
                name="unemployment_rate",
                data_type=SchemaType.FLOAT64,
                nullable=True,
                unit="ratio",
                semantic_type=SemanticType.RATIO,
                bounds=(0.0, 1.0),
            ),
            FieldSpec(
                name="region",
                data_type=SchemaType.CATEGORY,
                nullable=False,
                allowed_values=frozenset({"NA", "EU", "APAC", "LATAM"}),
            ),
        ),
        primary_key=("id",),
        time_dimension="year",
        time_granularity=TimeGranularity.ANNUAL,
        geo_dimension="country_code",
        geo_granularity=GeoGranularity.COUNTRY,
    )


@pytest.fixture
def sample_dataframe() -> pd.DataFrame:
    """Create a sample DataFrame for inference testing."""
    return pd.DataFrame(
        {
            "country_code": ["US", "DE", "JP", "BR", "UA"],
            "year": [2023, 2023, 2023, 2023, 2023],
            "gdp_usd": [25000.0, 4200.0, 4900.0, 2100.0, 160.0],
            "unemployment_rate": [0.037, 0.029, 0.026, 0.079, 0.089],
            "population": [331000000, 83000000, 125000000, 215000000, 41000000],
            "category": ["developed", "developed", "developed", "emerging", "emerging"],
        }
    )


# =============================================================================
# Type Mapping Tests
# =============================================================================


class TestSchemaTypeMapping:
    """Tests for SchemaType cross-platform mapping."""

    def test_int32_to_duckdb(self) -> None:
        """Verify INT32 maps to INTEGER in DuckDB."""
        assert SchemaType.INT32.to_duckdb_type() == "INTEGER"

    @pytest.mark.skipif(jnp is None, reason="JAX not installed")
    def test_int32_to_jax(self) -> None:
        """Verify INT32 maps to jnp.int32 in JAX."""
        assert SchemaType.INT32.to_jax_dtype() == jnp.int32

    def test_int32_to_pandas(self) -> None:
        """Verify INT32 maps to nullable Int32 in Pandas."""
        assert SchemaType.INT32.to_pandas_dtype() == "Int32"

    @pytest.mark.skipif(jnp is None, reason="JAX not installed")
    def test_float64_mappings(self) -> None:
        """Verify FLOAT64 maps correctly across platforms."""
        assert SchemaType.FLOAT64.to_duckdb_type() == "DOUBLE"
        assert SchemaType.FLOAT64.to_jax_dtype() == jnp.float64
        assert SchemaType.FLOAT64.to_pandas_dtype() == "Float64"

    def test_string_no_jax_dtype(self) -> None:
        """Verify STRING returns None for JAX (cannot cross boundary)."""
        assert SchemaType.STRING.to_jax_dtype() is None

    def test_category_to_duckdb(self) -> None:
        """Verify CATEGORY maps to VARCHAR in DuckDB."""
        assert SchemaType.CATEGORY.to_duckdb_type() == "VARCHAR"

    def test_datetime_mappings(self) -> None:
        """Verify DATETIME maps correctly."""
        assert SchemaType.DATETIME.to_duckdb_type() == "TIMESTAMP"
        assert SchemaType.DATETIME.to_pandas_dtype() == "datetime64[ns]"
        assert SchemaType.DATETIME.to_jax_dtype() is None

    def test_timestamp_tz_mappings(self) -> None:
        """Verify TIMESTAMP_TZ maps correctly."""
        assert SchemaType.TIMESTAMP_TZ.to_duckdb_type() == "TIMESTAMPTZ"
        assert SchemaType.TIMESTAMP_TZ.to_pandas_dtype() == "datetime64[ns, UTC]"

    def test_is_numeric(self) -> None:
        """Verify is_numeric correctly identifies numeric types."""
        assert SchemaType.INT32.is_numeric()
        assert SchemaType.FLOAT64.is_numeric()
        assert SchemaType.BOOLEAN.is_numeric()
        assert not SchemaType.STRING.is_numeric()
        assert not SchemaType.DATETIME.is_numeric()

    def test_is_temporal(self) -> None:
        """Verify is_temporal correctly identifies temporal types."""
        assert SchemaType.DATE.is_temporal()
        assert SchemaType.DATETIME.is_temporal()
        assert SchemaType.TIMESTAMP_TZ.is_temporal()
        assert SchemaType.DURATION.is_temporal()
        assert not SchemaType.STRING.is_temporal()
        assert not SchemaType.INT32.is_temporal()


class TestTypeCompatibility:
    """Tests for type compatibility and coercion."""

    def test_int32_compatible_with_int64(self) -> None:
        """INT32 can be widened to INT64."""
        assert SchemaType.INT32.is_compatible_with(SchemaType.INT64)

    def test_int64_not_compatible_with_int32(self) -> None:
        """INT64 cannot be narrowed to INT32."""
        assert not SchemaType.INT64.is_compatible_with(SchemaType.INT32)

    def test_float32_compatible_with_float64(self) -> None:
        """FLOAT32 can be widened to FLOAT64."""
        assert SchemaType.FLOAT32.is_compatible_with(SchemaType.FLOAT64)

    def test_int_compatible_with_float(self) -> None:
        """Integers can be widened to floats."""
        assert SchemaType.INT32.is_compatible_with(SchemaType.FLOAT64)
        assert SchemaType.INT64.is_compatible_with(SchemaType.FLOAT64)

    def test_date_compatible_with_datetime(self) -> None:
        """DATE can be widened to DATETIME."""
        assert SchemaType.DATE.is_compatible_with(SchemaType.DATETIME)

    def test_same_type_compatible(self) -> None:
        """Same types are always compatible."""
        for dt in SchemaType:
            assert dt.is_compatible_with(dt)


# =============================================================================
# Schema Tests
# =============================================================================


class TestSchemaVersion:
    """Tests for schema version handling."""

    def test_version_parse(self) -> None:
        """Test parsing version strings."""
        v = SchemaVersion.parse("1.2.3")
        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 3

    def test_version_parse_minor(self) -> None:
        v = SchemaVersion.parse("2.4")
        assert str(v) == "2.4.0"

    def test_version_str(self) -> None:
        """Test version string representation."""
        v = SchemaVersion(1, 2, 3)
        assert str(v) == "1.2.3"

    def test_version_comparison(self) -> None:
        """Test version comparison."""
        v1 = SchemaVersion(1, 0, 0)
        v2 = SchemaVersion(1, 1, 0)
        v3 = SchemaVersion(2, 0, 0)

        assert v1 < v2 < v3
        assert v1 <= v2
        assert not v3 < v1

    def test_version_compatibility(self) -> None:
        """Test backward compatibility check."""
        v1 = SchemaVersion(1, 0, 0)
        v1_1 = SchemaVersion(1, 1, 0)
        v2 = SchemaVersion(2, 0, 0)

        assert v1.is_compatible_with(v1_1)
        assert v1_1.is_compatible_with(v1)
        assert not v1.is_compatible_with(v2)

    def test_version_bump(self) -> None:
        """Test version bumping."""
        v = SchemaVersion(1, 2, 3)

        assert v.bump_major() == SchemaVersion(2, 0, 0)
        assert v.bump_minor() == SchemaVersion(1, 3, 0)
        assert v.bump_patch() == SchemaVersion(1, 2, 4)


class TestFieldSpec:
    """Tests for field specifications."""

    def test_field_creation(self) -> None:
        """Test creating a valid field spec."""
        field = FieldSpec(
            name="gdp_usd",
            data_type=SchemaType.FLOAT64,
            unit="usd",
            semantic_type=SemanticType.CURRENCY,
        )
        assert field.name == "gdp_usd"
        assert field.data_type == SchemaType.FLOAT64
        assert field.unit is not None
        assert field.unit.unit_id == "usd"

    def test_field_name_validation(self) -> None:
        """Test that invalid field names are rejected."""
        with pytest.raises(ValueError):
            FieldSpec(name="Invalid Name", data_type=SchemaType.STRING)

        with pytest.raises(ValueError):
            FieldSpec(name="123_invalid", data_type=SchemaType.STRING)

    def test_bounds_validation(self) -> None:
        """Test that invalid bounds are rejected."""
        with pytest.raises(ValueError, match="min.*max"):
            FieldSpec(
                name="test",
                data_type=SchemaType.FLOAT64,
                bounds=(100.0, 0.0),
            )

        for bad_bound in (float("nan"), float("inf"), float("-inf")):
            with pytest.raises(ValueError, match="finite"):
                FieldSpec(
                    name="test",
                    data_type=SchemaType.FLOAT64,
                    bounds=(0.0, bad_bound),
                )

        with pytest.raises(ValueError, match="exactly two"):
            FieldSpec(
                name="test",
                data_type=SchemaType.FLOAT64,
                bounds=(0.0, 1.0, 2.0),
            )

    def test_field_compatibility(self) -> None:
        """Test field compatibility checking."""
        field1 = FieldSpec(
            name="value",
            data_type=SchemaType.INT32,
            semantic_type=SemanticType.COUNT,
        )
        field2 = FieldSpec(
            name="value",
            data_type=SchemaType.INT64,
            semantic_type=SemanticType.COUNT,
        )
        field3 = FieldSpec(
            name="value",
            data_type=SchemaType.STRING,
            semantic_type=SemanticType.NAME,
        )

        assert field1.is_compatible_with(field2)
        assert not field1.is_compatible_with(field3)

    def test_array_requires_element_type(self) -> None:
        """Test that ARRAY fields require element_type."""
        with pytest.raises(ValueError, match="element_type"):
            FieldSpec(name="items", data_type=SchemaType.ARRAY)

    def test_duckdb_column_def(self) -> None:
        """Test DuckDB column definition generation."""
        field = FieldSpec(
            name="id",
            data_type=SchemaType.INT64,
            nullable=False,
        )
        assert field.to_duckdb_column_def() == "id BIGINT NOT NULL"


class TestDataSchema:
    """Tests for DataSchema model."""

    def test_schema_creation(self, sample_schema: DataSchema) -> None:
        """Test creating a valid schema."""
        assert sample_schema.schema_id == "test.sample.data"
        assert len(sample_schema.fields) == 6
        assert sample_schema.primary_key == ("id",)

    def test_get_field(self, sample_schema: DataSchema) -> None:
        """Test getting field by name."""
        field = sample_schema.get_field("gdp_usd")
        assert field is not None
        assert field.data_type == SchemaType.FLOAT64

        assert sample_schema.get_field("nonexistent") is None

    def test_field_names(self, sample_schema: DataSchema) -> None:
        """Test getting field names."""
        names = sample_schema.field_names()
        assert names == [
            "id",
            "country_code",
            "year",
            "gdp_usd",
            "unemployment_rate",
            "region",
        ]

    def test_numeric_fields(self, sample_schema: DataSchema) -> None:
        """Test getting numeric fields only."""
        numeric = sample_schema.numeric_fields()
        numeric_names = [f.name for f in numeric]
        assert "id" in numeric_names
        assert "gdp_usd" in numeric_names
        assert "country_code" not in numeric_names
        assert "region" not in numeric_names

    @pytest.mark.skipif(jnp is None, reason="JAX not installed")
    def test_to_jax_dtypes(self, sample_schema: DataSchema) -> None:
        """Test converting schema to JAX dtypes."""
        jax_dtypes = sample_schema.to_jax_dtypes()

        assert jax_dtypes["id"] == jnp.int64
        assert jax_dtypes["gdp_usd"] == jnp.float64
        assert "country_code" not in jax_dtypes
        assert "region" not in jax_dtypes

    def test_jax_excluded_fields(self, sample_schema: DataSchema) -> None:
        """Test getting fields that cannot cross to JAX."""
        excluded = sample_schema.jax_excluded_fields()
        assert "country_code" in excluded
        assert "region" in excluded
        assert "id" not in excluded

    def test_to_duckdb_schema(self, sample_schema: DataSchema) -> None:
        """Test generating DuckDB schema."""
        sql = sample_schema.to_duckdb_schema()
        assert "id BIGINT NOT NULL" in sql
        assert "country_code VARCHAR NOT NULL" in sql
        assert "PRIMARY KEY (id)" in sql

    def test_to_duckdb_create_table(self, sample_schema: DataSchema) -> None:
        """Test generating DuckDB CREATE TABLE."""
        sql = sample_schema.to_duckdb_create_table("my_table")
        assert sql.startswith("CREATE TABLE my_table")

    def test_content_hash_deterministic(self, sample_schema: DataSchema) -> None:
        """Test that content hash is deterministic."""
        hash1 = sample_schema.content_hash
        hash2 = sample_schema.content_hash
        assert hash1 == hash2
        assert hash1.startswith("sha256:")

    def test_content_hash_changes_with_schema(self) -> None:
        """Test that different schemas produce different hashes."""
        schema1 = DataSchema(
            schema_id="test.a",
            version=SchemaVersion(1, 0, 0),
            fields=(FieldSpec(name="a", data_type=SchemaType.INT32),),
        )
        schema2 = DataSchema(
            schema_id="test.b",
            version=SchemaVersion(2, 0, 0),
            fields=(FieldSpec(name="a", data_type=SchemaType.INT64),),
        )

        assert schema1.content_hash != schema2.content_hash

    def test_content_hash_ignores_identity(self) -> None:
        """Ensure content hash ignores schema_id/version when content is identical."""
        schema1 = DataSchema(
            schema_id="test.a",
            version=SchemaVersion(1, 0, 0),
            fields=(FieldSpec(name="a", data_type=SchemaType.INT32),),
        )
        schema2 = DataSchema(
            schema_id="test.b",
            version=SchemaVersion(2, 1, 0),
            fields=(FieldSpec(name="a", data_type=SchemaType.INT32),),
        )

        assert schema1.content_hash == schema2.content_hash

    def test_select_fields(self, sample_schema: DataSchema) -> None:
        """Test selecting a subset of fields."""
        selected = sample_schema.select_fields(["id", "gdp_usd", "year"])

        assert len(selected.fields) == 3
        assert selected.primary_key == ("id",)
        assert selected.time_dimension == "year"
        assert selected.geo_dimension is None

    def test_add_field(self, sample_schema: DataSchema) -> None:
        """Test adding a new field."""
        new_field = FieldSpec(
            name="inflation_rate",
            data_type=SchemaType.FLOAT64,
            unit="ratio",
        )
        updated = sample_schema.add_field(new_field)

        assert len(updated.fields) == 7
        assert updated.get_field("inflation_rate") is not None
        assert updated.version == SchemaVersion(1, 1, 0)

    def test_duplicate_field_names_rejected(self) -> None:
        """Test that duplicate field names are rejected."""
        with pytest.raises(ValueError, match="Duplicate"):
            DataSchema(
                schema_id="test.dup",
                version=SchemaVersion(1, 0, 0),
                fields=(
                    FieldSpec(name="a", data_type=SchemaType.INT32),
                    FieldSpec(name="a", data_type=SchemaType.INT64),
                ),
            )

    def test_invalid_schema_ids_rejected(self) -> None:
        for schema_id in ("test.", "test..bad", "test._bad", "test_.bad"):
            with pytest.raises(ValueError):
                DataSchema(
                    schema_id=schema_id,
                    version=SchemaVersion(1, 0, 0),
                    fields=(FieldSpec(name="a", data_type=SchemaType.INT32),),
                )

    def test_invalid_pk_reference_rejected(self) -> None:
        """Test that invalid primary key references are rejected."""
        with pytest.raises(ValueError, match="not found"):
            DataSchema(
                schema_id="test.pk",
                version=SchemaVersion(1, 0, 0),
                fields=(FieldSpec(name="a", data_type=SchemaType.INT32),),
                primary_key=("nonexistent",),
            )


# =============================================================================
# Schema Inference Tests
# =============================================================================


class TestSchemaInference:
    """Tests for schema inference."""

    def test_infer_from_sample(self, sample_dataframe: pd.DataFrame) -> None:
        """Test basic schema inference."""
        inference = SchemaInference()
        result = inference.infer_from_sample(sample_dataframe, schema_id="test.inferred")

        assert isinstance(result, InferenceResult)
        assert result.schema.schema_id == "test.inferred"
        assert len(result.schema.fields) == 6

    def test_infer_integer_types(self) -> None:
        """Test integer type inference."""
        df = pd.DataFrame(
            {
                "small_int": [1, 2, 3, 4, 5],
                "big_int": [1000000000, 2000000000, 3000000000, 4000000000, 5000000000],
            }
        )

        schema = infer_schema(df)

        small_field = schema.get_field("small_int")
        big_field = schema.get_field("big_int")

        assert small_field.data_type.is_numeric()
        assert big_field.data_type.is_numeric()

    def test_infer_float_type_default(self) -> None:
        """Test float type inference defaults to FLOAT32."""
        df = pd.DataFrame({"value": [1.5, 2.5, 3.5]})
        schema = infer_schema(df)

        field = schema.get_field("value")
        assert field.data_type == SchemaType.FLOAT32

    def test_infer_float_type_override(self) -> None:
        config = InferenceConfig(prefer_float32=False)
        schema = infer_schema(pd.DataFrame({"value": [1.5, 2.5]}), config=config)
        field = schema.get_field("value")
        assert field.data_type == SchemaType.FLOAT64

    def test_infer_category_type(self) -> None:
        """Test category type inference for low-cardinality strings."""
        df = pd.DataFrame({"status": ["active", "inactive", "pending"] * 100})

        schema = infer_schema(df)
        field = schema.get_field("status")

        assert field.data_type == SchemaType.CATEGORY
        assert field.allowed_values == frozenset({"active", "inactive", "pending"})

    def test_infer_datetime_from_pattern(self) -> None:
        """Test datetime inference from string patterns."""
        df = pd.DataFrame({"date_col": ["2023-01-01", "2023-02-01", "2023-03-01"]})

        schema = infer_schema(df)
        field = schema.get_field("date_col")

        assert field.data_type in (SchemaType.DATETIME, SchemaType.DATE)

    def test_infer_unit_from_name(self, sample_dataframe: pd.DataFrame) -> None:
        """Test unit inference from column names."""
        schema = infer_schema(sample_dataframe)

        gdp_field = schema.get_field("gdp_usd")
        assert gdp_field.unit is not None
        assert gdp_field.unit.unit_id == "usd"

    def test_infer_semantic_type(self, sample_dataframe: pd.DataFrame) -> None:
        """Test semantic type inference."""
        schema = infer_schema(sample_dataframe)

        pop_field = schema.get_field("population")
        assert pop_field.semantic_type == SemanticType.POPULATION

    def test_infer_semantic_type_respects_ratio_and_identifier_ordering(self) -> None:
        schema = infer_schema(
            pd.DataFrame(
                {
                    "share": [0.0, 0.5, 1.0],
                    "year": [2020, 2021, 2022],
                    "postal_code": [10101, 10102, 10103],
                    "record_id": [1, 2, 3],
                }
            )
        )

        assert schema.get_field("share").semantic_type == SemanticType.RATIO
        assert schema.get_field("year").semantic_type == SemanticType.TEMPORAL
        assert schema.get_field("postal_code").semantic_type == SemanticType.CODE
        assert schema.get_field("record_id").semantic_type == SemanticType.IDENTIFIER

    def test_infer_numeric_bounds_ignore_non_finite_values(self) -> None:
        schema = infer_schema(pd.DataFrame({"value": [1.0, float("inf"), 2.0]}))
        field = schema.get_field("value")
        assert field.bounds == (1.0, 2.0)

    def test_infer_time_dimension(self, sample_dataframe: pd.DataFrame) -> None:
        """Test time dimension detection."""
        schema = infer_schema(sample_dataframe)

        assert schema.time_dimension == "year"
        assert schema.time_granularity == TimeGranularity.ANNUAL

    def test_infer_geo_dimension(self, sample_dataframe: pd.DataFrame) -> None:
        """Test geo dimension detection."""
        schema = infer_schema(sample_dataframe)

        assert schema.geo_dimension is not None

    def test_infer_with_hints(self, sample_dataframe: pd.DataFrame) -> None:
        """Test inference with user-provided hints."""
        hints = SchemaHints(
            field_types={"year": SchemaType.INT16},
            primary_key=("country_code", "year"),
            time_dimension="year",
        )

        schema = infer_schema(sample_dataframe, hints=hints)

        year_field = schema.get_field("year")
        assert year_field.data_type == SchemaType.INT16
        assert schema.primary_key == ("country_code", "year")

    def test_infer_handles_nulls(self) -> None:
        """Test that inference handles null values correctly."""
        df = pd.DataFrame({"sparse": [1, None, 3, None, 5], "dense": [1, 2, 3, 4, 5]})

        result = SchemaInference().infer_from_sample(df)

        sparse_field = result.schema.get_field("sparse")
        dense_field = result.schema.get_field("dense")

        assert sparse_field.expected_completeness < 1.0
        assert not sparse_field.nullable
        assert not dense_field.nullable
        assert any("rare nulls" in w for w in result.warnings)

    def test_column_name_normalization(self) -> None:
        """Test that column names are normalized to snake_case."""
        df = pd.DataFrame(
            {
                "GDP Growth Rate": [1.0, 2.0],
                "countryCode": ["US", "DE"],
                "UNEMPLOYMENT_RATE": [0.05, 0.03],
            }
        )

        schema = infer_schema(df)
        field_names = schema.field_names()

        assert "gdp_growth_rate" in field_names
        assert "country_code" in field_names
        assert "unemployment_rate" in field_names


# =============================================================================
# Schema Evolution Tests
# =============================================================================


class TestSchemaEvolution:
    """Tests for schema evolution and compatibility."""

    @pytest.fixture
    def evolution(self) -> SchemaEvolution:
        return SchemaEvolution()

    def test_detect_field_added(self, evolution: SchemaEvolution) -> None:
        """Test detecting added fields."""
        old = DataSchema(
            schema_id="test",
            version=SchemaVersion(1, 0, 0),
            fields=(FieldSpec(name="a", data_type=SchemaType.INT32),),
        )
        new = DataSchema(
            schema_id="test",
            version=SchemaVersion(1, 1, 0),
            fields=(
                FieldSpec(name="a", data_type=SchemaType.INT32),
                FieldSpec(name="b", data_type=SchemaType.STRING),
            ),
        )

        report = evolution.compare(old, new)

        assert report.is_compatible
        assert report.recommended_version_bump == "minor"
        assert any(c.change_type == ChangeType.FIELD_ADDED for c in report.changes)

    def test_detect_field_removed(self, evolution: SchemaEvolution) -> None:
        """Test detecting removed fields (breaking change)."""
        old = DataSchema(
            schema_id="test",
            version=SchemaVersion(1, 0, 0),
            fields=(
                FieldSpec(name="a", data_type=SchemaType.INT32),
                FieldSpec(name="b", data_type=SchemaType.STRING),
            ),
        )
        new = DataSchema(
            schema_id="test",
            version=SchemaVersion(2, 0, 0),
            fields=(FieldSpec(name="a", data_type=SchemaType.INT32),),
        )

        report = evolution.compare(old, new)

        assert not report.is_compatible
        assert report.recommended_version_bump == "major"
        assert len(report.breaking_changes) == 1

    def test_detect_type_widened(self, evolution: SchemaEvolution) -> None:
        """Test detecting type widening (non-breaking)."""
        old = DataSchema(
            schema_id="test",
            version=SchemaVersion(1, 0, 0),
            fields=(FieldSpec(name="a", data_type=SchemaType.INT32),),
        )
        new = DataSchema(
            schema_id="test",
            version=SchemaVersion(1, 1, 0),
            fields=(FieldSpec(name="a", data_type=SchemaType.INT64),),
        )

        report = evolution.compare(old, new)

        assert report.is_compatible
        assert report.recommended_version_bump == "minor"
        assert any(c.change_type == ChangeType.TYPE_WIDENED for c in report.changes)

    def test_detect_type_narrowed(self, evolution: SchemaEvolution) -> None:
        """Test detecting type narrowing (breaking)."""
        old = DataSchema(
            schema_id="test",
            version=SchemaVersion(1, 0, 0),
            fields=(FieldSpec(name="a", data_type=SchemaType.INT64),),
        )
        new = DataSchema(
            schema_id="test",
            version=SchemaVersion(2, 0, 0),
            fields=(FieldSpec(name="a", data_type=SchemaType.INT32),),
        )

        report = evolution.compare(old, new)

        assert not report.is_compatible
        assert any(c.change_type == ChangeType.TYPE_NARROWED for c in report.changes)

    def test_detect_nullable_change(self, evolution: SchemaEvolution) -> None:
        """Test detecting nullability changes."""
        old = DataSchema(
            schema_id="test",
            version=SchemaVersion(1, 0, 0),
            fields=(FieldSpec(name="a", data_type=SchemaType.INT32, nullable=False),),
        )
        new = DataSchema(
            schema_id="test",
            version=SchemaVersion(1, 1, 0),
            fields=(FieldSpec(name="a", data_type=SchemaType.INT32, nullable=True),),
        )

        report = evolution.compare(old, new)

        assert report.is_compatible
        assert any(c.change_type == ChangeType.FIELD_MADE_NULLABLE for c in report.changes)

    def test_mixed_bounds_emit_relaxed_and_tightened_changes(
        self, evolution: SchemaEvolution
    ) -> None:
        old = DataSchema(
            schema_id="test",
            version=SchemaVersion(1, 0, 0),
            fields=(FieldSpec(name="value", data_type=SchemaType.FLOAT64, bounds=(0, 10)),),
        )
        new = DataSchema(
            schema_id="test",
            version=SchemaVersion(2, 0, 0),
            fields=(FieldSpec(name="value", data_type=SchemaType.FLOAT64, bounds=(-5, 5)),),
        )

        report = evolution.compare(old, new)
        change_types = {change.change_type for change in report.changes}

        assert ChangeType.BOUNDS_RELAXED in change_types
        assert ChangeType.BOUNDS_TIGHTENED in change_types
        assert not report.is_compatible

    def test_allowed_values_empty_set_is_constraint(self, evolution: SchemaEvolution) -> None:
        empty = FieldSpec(
            name="status",
            data_type=SchemaType.CATEGORY,
            allowed_values=frozenset(),
        )
        with_value = FieldSpec(
            name="status",
            data_type=SchemaType.CATEGORY,
            allowed_values=frozenset({"active"}),
        )

        assert empty.widen_to(with_value).allowed_values == frozenset({"active"})
        assert empty.widen_to(empty).allowed_values == frozenset()

        schema = DataSchema(
            schema_id="test",
            version=SchemaVersion(1, 0, 0),
            fields=(empty,),
        )
        assert validate_dataframe_against_schema(
            pd.DataFrame({"status": ["active"]}),
            schema,
        )

        old = DataSchema(
            schema_id="test",
            version=SchemaVersion(1, 0, 0),
            fields=(empty,),
        )
        new = DataSchema(
            schema_id="test",
            version=SchemaVersion(1, 1, 0),
            fields=(with_value,),
        )
        report = evolution.compare(old, new)
        assert any(
            change.change_type == ChangeType.ALLOWED_VALUES_EXPANDED for change in report.changes
        )

    def test_precision_removal_is_relaxation(self, evolution: SchemaEvolution) -> None:
        old = DataSchema(
            schema_id="test",
            version=SchemaVersion(1, 0, 0),
            fields=(FieldSpec(name="value", data_type=SchemaType.FLOAT64, precision=10),),
        )
        new = DataSchema(
            schema_id="test",
            version=SchemaVersion(1, 1, 0),
            fields=(FieldSpec(name="value", data_type=SchemaType.FLOAT64),),
        )

        report = evolution.compare(old, new)
        assert report.is_compatible
        assert any(change.change_type == ChangeType.PRECISION_WIDENED for change in report.changes)

    def test_generate_migration_sql(self, evolution: SchemaEvolution) -> None:
        """Test SQL migration generation."""
        old = DataSchema(
            schema_id="test",
            version=SchemaVersion(1, 0, 0),
            fields=(FieldSpec(name="a", data_type=SchemaType.INT32),),
        )
        new = DataSchema(
            schema_id="test",
            version=SchemaVersion(1, 1, 0),
            fields=(
                FieldSpec(name="a", data_type=SchemaType.INT32),
                FieldSpec(name="b", data_type=SchemaType.STRING, nullable=True),
            ),
        )

        sql = evolution.generate_migration_sql(old, new, "my_table")

        assert len(sql) == 1
        assert "ADD COLUMN" in sql[0]
        assert "VARCHAR" in sql[0]

    def test_build_migration_plan_marks_destructive_changes_unsafe(
        self,
        evolution: SchemaEvolution,
    ) -> None:
        old = DataSchema(
            schema_id="test",
            version=SchemaVersion(1, 0, 0),
            fields=(
                FieldSpec(name="a", data_type=SchemaType.INT32),
                FieldSpec(name="b", data_type=SchemaType.STRING),
            ),
        )
        new = DataSchema(
            schema_id="test",
            version=SchemaVersion(2, 0, 0),
            fields=(FieldSpec(name="a", data_type=SchemaType.INT32),),
        )

        plan = evolution.build_migration_plan(old, new, "my_table")

        assert isinstance(plan, MigrationPlan)
        assert plan.safe_to_apply is False
        assert any(operation.action == "drop_column" for operation in plan.operations)


# =============================================================================
# Schema Registry Tests
# =============================================================================


class TestSchemaRegistry:
    """Tests for schema registry."""

    def test_register_and_get(self, sample_schema: DataSchema) -> None:
        """Test basic register and get operations."""
        registry = SchemaRegistry()

        reg = registry.register(sample_schema)

        assert reg.content_hash == sample_schema.content_hash
        assert registry.get(sample_schema.schema_id) == sample_schema

    def test_get_specific_version(self) -> None:
        """Test getting a specific schema version."""
        registry = SchemaRegistry()

        v1 = DataSchema(
            schema_id="test",
            version=SchemaVersion(1, 0, 0),
            fields=(FieldSpec(name="a", data_type=SchemaType.INT32),),
        )
        v2 = DataSchema(
            schema_id="test",
            version=SchemaVersion(2, 0, 0),
            fields=(
                FieldSpec(name="a", data_type=SchemaType.INT32),
                FieldSpec(name="b", data_type=SchemaType.STRING),
            ),
        )

        registry.register(v1)
        registry.register(v2)

        assert registry.get("test", SchemaVersion(1, 0, 0)) == v1
        assert registry.get("test", SchemaVersion(2, 0, 0)) == v2
        assert registry.get("test") == v2

    def test_version_conflict(self, sample_schema: DataSchema) -> None:
        """Test that version conflicts are detected."""
        registry = SchemaRegistry()
        registry.register(sample_schema)

        modified = DataSchema(
            schema_id=sample_schema.schema_id,
            version=sample_schema.version,
            fields=(FieldSpec(name="different", data_type=SchemaType.STRING),),
        )

        with pytest.raises(SchemaVersionConflictError):
            registry.register(modified)

    def test_not_found(self) -> None:
        """Test SchemaNotFoundError."""
        registry = SchemaRegistry()

        with pytest.raises(SchemaNotFoundError):
            registry.get("nonexistent")

    def test_list_schemas(self, sample_schema: DataSchema) -> None:
        """Test listing schemas."""
        registry = SchemaRegistry()
        registry.register(sample_schema)

        schemas = registry.list_schemas()
        assert sample_schema.schema_id in schemas

    def test_list_versions(self) -> None:
        """Test listing schema versions."""
        registry = SchemaRegistry()

        for i in range(3):
            schema = DataSchema(
                schema_id="test",
                version=SchemaVersion(1, i, 0),
                fields=(FieldSpec(name="a", data_type=SchemaType.INT32),),
            )
            registry.register(schema)

        versions = registry.list_versions("test")
        assert len(versions) == 3
        assert versions == sorted(versions)

    def test_compare_versions(self) -> None:
        """Test comparing schema versions via registry."""
        registry = SchemaRegistry()

        v1 = DataSchema(
            schema_id="test",
            version=SchemaVersion(1, 0, 0),
            fields=(FieldSpec(name="a", data_type=SchemaType.INT32),),
        )
        v2 = DataSchema(
            schema_id="test",
            version=SchemaVersion(1, 1, 0),
            fields=(
                FieldSpec(name="a", data_type=SchemaType.INT32),
                FieldSpec(name="b", data_type=SchemaType.STRING),
            ),
        )

        registry.register(v1)
        registry.register(v2)

        report = registry.compare_versions(
            "test",
            SchemaVersion(1, 0, 0),
            SchemaVersion(1, 1, 0),
        )

        assert report.is_compatible


class TestFileBackedSchemaRegistry:
    """Tests for file-backed registry."""

    def test_persistence(self, sample_schema: DataSchema) -> None:
        """Test that schemas persist across registry instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            approval = SchemaApprovalMetadata(
                owner="fabric-owner",
                reviewer="fabric-reviewer",
                risk_level=SchemaRiskLevel.HIGH,
                migration_status=MigrationStatus.PLANNED,
                downstream_impact_summary="world.claims, quality_reports",
                migration_note="Add backfill for downstream views.",
                adr_refs=("ADR-0053",),
                approved_major_bump=True,
            )

            registry1 = FileBackedSchemaRegistry(base_dir)
            registry1.register(sample_schema, approval=approval)

            registry2 = FileBackedSchemaRegistry(base_dir)
            loaded = registry2.get(sample_schema.schema_id)
            registration = registry2.get_registration(sample_schema.schema_id)

            assert loaded.schema_id == sample_schema.schema_id
            assert loaded.content_hash == sample_schema.content_hash
            assert registration.approval.owner == "fabric-owner"
            assert registration.approval.adr_refs == ("ADR-0053",)

    def test_unregister(self, sample_schema: DataSchema) -> None:
        """Test unregistering removes files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)

            registry = FileBackedSchemaRegistry(base_dir)
            registry.register(sample_schema)

            schema_dir = base_dir / sample_schema.schema_id.replace(".", "_")
            assert schema_dir.exists()

            registry.unregister(sample_schema.schema_id)

            assert not schema_dir.exists()

    def test_startup_removes_orphan_tmp_files(self, sample_schema: DataSchema) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            orphan = base_dir / ".schema.tmp"
            orphan.write_text("{not-json", encoding="utf-8")

            registry = FileBackedSchemaRegistry(base_dir)
            registry.register(sample_schema)

            assert not orphan.exists()
            assert registry.get(sample_schema.schema_id).content_hash == sample_schema.content_hash


# =============================================================================
# Validation & Coercion Tests
# =============================================================================


class TestDataFrameValidation:
    """Tests for DataFrame validation against schemas."""

    def test_valid_dataframe(self, sample_schema: DataSchema) -> None:
        """Test validating a conforming DataFrame."""
        df = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "country_code": ["US", "DE", "JP"],
                "year": [2023, 2023, 2023],
                "gdp_usd": [25000.0, 4200.0, 4900.0],
                "unemployment_rate": [0.037, 0.029, 0.026],
                "region": ["NA", "EU", "APAC"],
            }
        )

        errors = validate_dataframe_against_schema(df, sample_schema)
        assert errors == []

    def test_missing_column(self, sample_schema: DataSchema) -> None:
        """Test detecting missing columns."""
        df = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "country_code": ["US", "DE", "JP"],
            }
        )

        errors = validate_dataframe_against_schema(df, sample_schema)
        assert any("Missing" in e for e in errors)

    def test_null_in_non_nullable(self, sample_schema: DataSchema) -> None:
        """Test detecting nulls in non-nullable fields."""
        df = pd.DataFrame(
            {
                "id": [1, None, 3],
                "country_code": ["US", "DE", "JP"],
                "year": [2023, 2023, 2023],
                "gdp_usd": [25000.0, 4200.0, 4900.0],
                "unemployment_rate": [0.037, 0.029, 0.026],
                "region": ["NA", "EU", "APAC"],
            }
        )

        errors = validate_dataframe_against_schema(df, sample_schema)
        assert any("null" in e.lower() for e in errors)

    def test_value_out_of_bounds(self, sample_schema: DataSchema) -> None:
        """Test detecting values outside bounds."""
        df = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "country_code": ["US", "DE", "JP"],
                "year": [2023, 2023, 2023],
                "gdp_usd": [-1000.0, 4200.0, 4900.0],
                "unemployment_rate": [0.037, 0.029, 1.5],
                "region": ["NA", "EU", "APAC"],
            }
        )

        errors = validate_dataframe_against_schema(df, sample_schema)
        assert len(errors) >= 2

    def test_invalid_category_value(self, sample_schema: DataSchema) -> None:
        """Test detecting invalid category values."""
        df = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "country_code": ["US", "DE", "JP"],
                "year": [2023, 2023, 2023],
                "gdp_usd": [25000.0, 4200.0, 4900.0],
                "unemployment_rate": [0.037, 0.029, 0.026],
                "region": ["NA", "INVALID", "APAC"],
            }
        )

        errors = validate_dataframe_against_schema(df, sample_schema)
        assert any("invalid" in e.lower() for e in errors)


class TestDataFrameCoercion:
    """Tests for coercion to schema types."""

    def test_coerce_basic(self, sample_schema: DataSchema) -> None:
        df = pd.DataFrame(
            {
                "ID": ["1", "2", "3"],
                "country_code": ["US", "DE", "JP"],
                "year": ["2023", "2023", "2023"],
                "gdp_usd": ["25000.0", "4200.0", "4900.0"],
                "unemployment_rate": ["0.037", "0.029", "0.026"],
                "region": ["NA", "EU", "APAC"],
            }
        )

        result = coerce_dataframe_to_schema(df, sample_schema, normalize_columns=True)
        assert isinstance(result, CoercionResult)
        assert "id" in result.dataframe.columns
        assert result.dataframe["id"].dtype.name.startswith("Int")
