"""Phase 3 schema and semantic correctness coverage for Fabric."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import ClassVar

import pandas as pd
import pytest

try:
    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st

    HYPOTHESIS_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    HYPOTHESIS_AVAILABLE = False

from polisyos.fabric.connectors.base import (
    BaseConnector,
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    FetchResult,
    HealthStatus,
)
from polisyos.fabric.connectors.contracts import (
    ChangeType,
    ConnectorSchemaContract,
    ContractRegistry,
    DataSchema,
    FieldSpec,
    MigrationStatus,
    SchemaApprovalMetadata,
    SchemaEvolution,
    SchemaRiskLevel,
    SchemaType,
    SchemaVersion,
    SemanticType,
    coerce_dataframe_to_schema,
    evaluate_contract_governance,
    infer_schema,
    make_field_id,
    make_schema_id,
    validate_dataframe_against_schema,
)
from polisyos.fabric.connectors.contracts.validation_middleware import (
    ContractValidatingProxy,
    SchemaValidationMode,
)
from polisyos.fabric.connectors.quality.consistency import ConsistencyChecker
from polisyos.fabric.connectors.transform import (
    NormalizationTransform,
    TransformContext,
    TransformError,
)
from polisyos.fabric.connectors.transform.validator import RangeRule
from polisyos.fabric.connectors.types import CoercionError, SchemaError, safe_cast
from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    DataVersion,
    QualityTier,
    TrustLevel,
    VersionStrategy,
    capabilities_from_flags,
)


def _version() -> DataVersion:
    now = datetime.now(UTC)
    return DataVersion(
        strategy=VersionStrategy.CONTENT_HASH,
        value="sha256:" + "1" * 64,
        timestamp=now,
        content_hash="sha256:" + "1" * 64,
    )


def test_source_schema_id_helper_preserves_unicode_without_unsafe_segments() -> None:
    schema_id = make_schema_id("world-bank.wdi", "GDP/Україна 2024")

    assert schema_id.startswith("world_bank.wdi.gdp")
    assert ".." not in schema_id
    assert "/" not in schema_id
    assert "u0443" in schema_id


def test_field_ids_are_stable_and_unique() -> None:
    schema_id = make_schema_id("worldbank", "wdi", "generic")
    value_field_id = make_field_id(schema_id, "value")
    schema = DataSchema(
        schema_id=schema_id,
        version=SchemaVersion(1, 0, 0),
        fields=(
            FieldSpec(
                name="country",
                field_id=make_field_id(schema_id, "country"),
                data_type=SchemaType.STRING,
            ),
            FieldSpec(name="value", field_id=value_field_id, data_type=SchemaType.FLOAT64),
        ),
    )

    assert schema.field_ids() == [make_field_id(schema_id, "country"), value_field_id]
    assert schema.get_field_by_id(value_field_id).name == "value"

    with pytest.raises(ValueError, match="Duplicate field ids"):
        DataSchema(
            schema_id=schema_id,
            version=SchemaVersion(1, 0, 0),
            fields=(
                FieldSpec(name="a", field_id=value_field_id, data_type=SchemaType.STRING),
                FieldSpec(name="b", field_id=value_field_id, data_type=SchemaType.STRING),
            ),
        )


def test_stable_field_id_rename_is_breaking_and_gets_replayable_migration() -> None:
    field_id = "schema.sample.value"
    old = DataSchema(
        schema_id="schema.sample",
        version=SchemaVersion(1, 0, 0),
        fields=(FieldSpec(name="value", field_id=field_id, data_type=SchemaType.FLOAT64),),
    )
    new = DataSchema(
        schema_id="schema.sample",
        version=SchemaVersion(2, 0, 0),
        fields=(FieldSpec(name="amount", field_id=field_id, data_type=SchemaType.FLOAT64),),
    )

    evolution = SchemaEvolution()
    report = evolution.compare(old, new)
    plan = evolution.build_migration_plan(old, new, "world_facts")

    assert not report.is_compatible
    assert any(change.change_type == ChangeType.FIELD_RENAMED for change in report.changes)
    assert plan.evidence_id
    assert any(operation.action == "rename_column" for operation in plan.operations)
    assert not plan.safe_to_apply


def test_field_id_change_on_same_name_is_breaking_drift() -> None:
    old = DataSchema(
        schema_id="schema.sample",
        version=SchemaVersion(1, 0, 0),
        fields=(
            FieldSpec(name="value", field_id="schema.sample.value", data_type=SchemaType.FLOAT64),
        ),
    )
    new = DataSchema(
        schema_id="schema.sample",
        version=SchemaVersion(2, 0, 0),
        fields=(
            FieldSpec(
                name="value", field_id="schema.sample.other_value", data_type=SchemaType.FLOAT64
            ),
        ),
    )

    report = SchemaEvolution().compare(old, new)

    assert any(change.change_type == ChangeType.FIELD_ID_CHANGED for change in report.changes)
    assert not report.is_compatible


def test_compatible_changes_generate_migration_evidence() -> None:
    old = DataSchema(
        schema_id="schema.sample",
        version=SchemaVersion(1, 0, 0),
        fields=(FieldSpec(name="value", data_type=SchemaType.INT32, nullable=False),),
    )
    new = DataSchema(
        schema_id="schema.sample",
        version=SchemaVersion(1, 1, 0),
        fields=(
            FieldSpec(name="value", data_type=SchemaType.INT64, nullable=True),
            FieldSpec(name="source", data_type=SchemaType.STRING, nullable=True),
        ),
    )

    plan = SchemaEvolution().build_migration_plan(old, new, "world_facts")

    assert plan.safe_to_apply
    assert plan.source_content_hash == old.content_hash
    assert plan.target_content_hash == new.content_hash
    assert plan.sql_statements
    assert any(operation.action == "add_column" for operation in plan.operations)


def test_incompatible_semantic_change_requires_governance_metadata() -> None:
    old_schema = DataSchema(
        schema_id="schema.sample",
        version=SchemaVersion(1, 0, 0),
        fields=(
            FieldSpec(name="value", data_type=SchemaType.FLOAT64, semantic_type=SemanticType.RATIO),
        ),
    )
    new_schema = DataSchema(
        schema_id="schema.sample",
        version=SchemaVersion(2, 0, 0),
        fields=(
            FieldSpec(
                name="value", data_type=SchemaType.FLOAT64, semantic_type=SemanticType.PERCENTAGE
            ),
        ),
    )
    old = ConnectorSchemaContract(
        contract_id="schema.sample.contract",
        connector_id="schema.sample",
        dataset_id="sample",
        schema=old_schema,
    )
    new = ConnectorSchemaContract(
        contract_id=old.contract_id,
        connector_id=old.connector_id,
        dataset_id=old.dataset_id,
        schema=new_schema,
    )

    evaluation = evaluate_contract_governance(old, new)

    assert any(
        change.change_type == ChangeType.SEMANTIC_TYPE_CHANGED
        for change in evaluation.report.changes
    )
    assert (
        "owner is required for breaking schema changes"
        in evaluation.missing_governance_requirements
    )
    assert (
        "reviewer is required for breaking schema changes"
        in evaluation.missing_governance_requirements
    )
    assert (
        "migration_note is required for breaking schema changes"
        in evaluation.missing_governance_requirements
    )


def test_semantic_value_validation_blocks_ratio_drift() -> None:
    schema = DataSchema(
        schema_id="schema.sample",
        version=SchemaVersion(1, 0, 0),
        fields=(
            FieldSpec(name="share", data_type=SchemaType.FLOAT64, semantic_type=SemanticType.RATIO),
        ),
    )

    errors = validate_dataframe_against_schema(pd.DataFrame({"share": [0.2, 1.5]}), schema)

    assert any("semantic ratio max" in error for error in errors)


def test_schema_model_rejects_non_numeric_numeric_semantics() -> None:
    with pytest.raises(ValueError, match="requires a numeric data_type"):
        FieldSpec(
            name="share",
            data_type=SchemaType.STRING,
            semantic_type=SemanticType.RATIO,
        )


def test_locale_decimal_and_unicode_column_normalization_are_stable() -> None:
    schema = infer_schema(pd.DataFrame({"Регіон": ["Київ"], "Value €": ["1.000,50"]}))
    assert schema.field_names()[0].startswith("u0440")

    contract = DataSchema(
        schema_id="schema.sample",
        version=SchemaVersion(1, 0, 0),
        fields=(FieldSpec(name="amount", data_type=SchemaType.DECIMAL),),
    )
    result = coerce_dataframe_to_schema(
        pd.DataFrame({"amount": ["1.000,50", "2,50e2"]}),
        contract,
    )

    assert result.errors == ()
    assert result.dataframe["amount"].tolist() == [Decimal("1000.50"), Decimal("250")]


def test_unit_conversion_lineage_is_explicit_and_replayable() -> None:
    transform = NormalizationTransform(unit_conversions={"distance": ("km", "m")})
    result, lineage, _warnings = transform.apply(
        pd.DataFrame({"distance": [Decimal("1.5"), None]}),
        TransformContext(),
    )

    assert result["distance"].iloc[0] == Decimal("1500")
    evidence = lineage.parameters["unit_conversions"]["distance"]
    assert evidence == {
        "from_unit": "km",
        "to_unit": "m",
        "multiplier": "1000",
        "offset": "0",
        "requires_rate": False,
    }


def test_range_rule_rejects_non_finite_values() -> None:
    rule = RangeRule("score", min_value=0.0, max_value=1.0)
    violations = rule.validate(pd.DataFrame({"score": [0.5, float("inf")]}), TransformContext())

    assert any("non-finite" in violation for violation in violations)


def test_numeric_coercion_rejects_non_finite_trust_boundary_values() -> None:
    with pytest.raises(CoercionError):
        safe_cast(float("inf"), "float64")
    with pytest.raises(CoercionError):
        safe_cast(Decimal("NaN"), "decimal")
    with pytest.raises(CoercionError):
        safe_cast(float("nan"), "boolean")


def test_dataframe_coercion_reports_non_finite_values_without_silent_scoring() -> None:
    schema = DataSchema(
        schema_id="schema.sample",
        version=SchemaVersion(1, 0, 0),
        fields=(FieldSpec(name="value", data_type=SchemaType.FLOAT64),),
    )

    result = coerce_dataframe_to_schema(pd.DataFrame({"value": [1.0, float("inf")]}), schema)

    assert any("non-finite values during coercion" in error for error in result.errors)
    assert result.dataframe["value"].isna().iloc[1]


def test_consistency_checker_covers_all_numeric_schema_types_for_non_finite_values() -> None:
    schema = DataSchema(
        schema_id="schema.sample",
        version=SchemaVersion(1, 0, 0),
        fields=(FieldSpec(name="value", data_type=SchemaType.UINT64),),
    )

    result = ConsistencyChecker().check_consistency(
        pd.DataFrame({"value": [1, float("inf")]}),
        schema,
    )

    assert any(
        "non-finite values in numeric field" in violation.message for violation in result.violations
    )


def test_unit_conversion_rejects_non_finite_values() -> None:
    transform = NormalizationTransform(unit_conversions={"distance": ("km", "m")})

    with pytest.raises(TransformError, match="non-finite"):
        transform.apply(pd.DataFrame({"distance": [float("inf")]}), TransformContext())


class _DriftConnector(BaseConnector[pd.DataFrame]):
    connector_id: ClassVar[str] = "schema.sample"
    capabilities: ClassVar[ConnectorCapability] = ConnectorCapability.FULL_FETCH
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id="sample",
        version="1.0.0",
        namespace="schema",
        source_name="Sample",
        source_organization="Tests",
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.SILVER,
        capabilities=capabilities_from_flags(ConnectorCapability.FULL_FETCH),
    )

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        return self._create_handle(config)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        return None

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        return HealthStatus(healthy=True, message="ok")

    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[pd.DataFrame]:
        return FetchResult(
            data=pd.DataFrame({"share": [1.25]}),
            row_count=1,
            schema_id="schema.sample",
            schema_version="1.0.0",
            version=_version(),
            fetched_at=datetime.now(UTC),
            completeness=1.0,
            quality_tier=QualityTier.SILVER,
        )


def test_contract_proxy_blocks_semantic_drift_before_world_facts_change() -> None:
    registry = ContractRegistry()
    registry.register(
        ConnectorSchemaContract(
            contract_id="schema.sample.contract",
            connector_id="schema.sample",
            dataset_id="sample",
            schema=DataSchema(
                schema_id="schema.sample",
                version=SchemaVersion(1, 0, 0),
                fields=(
                    FieldSpec(
                        name="share",
                        data_type=SchemaType.FLOAT64,
                        semantic_type=SemanticType.RATIO,
                    ),
                ),
            ),
        )
    )
    proxy = ContractValidatingProxy(
        _DriftConnector(),
        registry,
        mode=SchemaValidationMode.STRICT,
    )

    async def _exercise() -> None:
        handle = await proxy.connect(ConnectionConfig(url="http://example.com"))
        await proxy.fetch(handle, FetchRequest(dataset_id="sample"))

    with pytest.raises(SchemaError):
        asyncio.run(_exercise())


def test_breaking_semantic_change_with_governance_can_be_registered() -> None:
    registry = ContractRegistry()
    base = ConnectorSchemaContract(
        contract_id="schema.sample.contract",
        connector_id="schema.sample",
        dataset_id="sample",
        schema=DataSchema(
            schema_id="schema.sample",
            version=SchemaVersion(1, 0, 0),
            fields=(
                FieldSpec(
                    name="value", data_type=SchemaType.FLOAT64, semantic_type=SemanticType.RATIO
                ),
            ),
        ),
    )
    registry.register(base)
    approval = SchemaApprovalMetadata(
        owner="fabric-owner",
        reviewer="fabric-reviewer",
        risk_level=SchemaRiskLevel.HIGH,
        migration_status=MigrationStatus.PLANNED,
        downstream_impact_summary="world facts and materialized projections",
        migration_note="Backfill ratio values to percentage values before release.",
        adr_refs=("ADR-0053",),
        approved_major_bump=True,
    )

    report = registry.register(
        ConnectorSchemaContract(
            contract_id=base.contract_id,
            connector_id=base.connector_id,
            dataset_id=base.dataset_id,
            schema=DataSchema(
                schema_id="schema.sample",
                version=SchemaVersion(2, 0, 0),
                fields=(
                    FieldSpec(
                        name="value",
                        data_type=SchemaType.FLOAT64,
                        semantic_type=SemanticType.PERCENTAGE,
                    ),
                ),
            ),
            approval=approval,
        ),
        allow_breaking=True,
    )

    assert report is not None
    assert any(change.change_type == ChangeType.SEMANTIC_TYPE_CHANGED for change in report.changes)


if HYPOTHESIS_AVAILABLE:

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    @given(
        old_max=st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        new_max=st.floats(
            min_value=1001.0, max_value=2000.0, allow_nan=False, allow_infinity=False
        ),
    )
    def test_property_bounds_relaxation_is_compatible(old_max: float, new_max: float) -> None:
        old = DataSchema(
            schema_id="schema.sample",
            version=SchemaVersion(1, 0, 0),
            fields=(FieldSpec(name="value", data_type=SchemaType.FLOAT64, bounds=(0.0, old_max)),),
        )
        new = DataSchema(
            schema_id="schema.sample",
            version=SchemaVersion(1, 1, 0),
            fields=(FieldSpec(name="value", data_type=SchemaType.FLOAT64, bounds=(0.0, new_max)),),
        )

        report = SchemaEvolution().compare(old, new)

        assert report.is_compatible
        assert any(change.change_type == ChangeType.BOUNDS_RELAXED for change in report.changes)

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    @given(
        values=st.sets(
            st.text(
                alphabet=st.characters(
                    whitelist_categories=("Ll", "Lu", "Nd"),
                    min_codepoint=48,
                    max_codepoint=122,
                ),
                min_size=1,
                max_size=8,
            ),
            min_size=1,
            max_size=8,
        )
    )
    def test_property_allowed_values_restriction_is_breaking(values: set[str]) -> None:
        source_values = frozenset(values | {"__kept__"})
        target_values = frozenset({"__kept__"})
        old = DataSchema(
            schema_id="schema.sample",
            version=SchemaVersion(1, 0, 0),
            fields=(
                FieldSpec(
                    name="status",
                    data_type=SchemaType.CATEGORY,
                    allowed_values=source_values,
                ),
            ),
        )
        new = DataSchema(
            schema_id="schema.sample",
            version=SchemaVersion(2, 0, 0),
            fields=(
                FieldSpec(
                    name="status",
                    data_type=SchemaType.CATEGORY,
                    allowed_values=target_values,
                ),
            ),
        )

        report = SchemaEvolution().compare(old, new)

        assert not report.is_compatible
        assert any(
            change.change_type == ChangeType.ALLOWED_VALUES_RESTRICTED for change in report.changes
        )
else:

    def test_property_bounds_relaxation_is_compatible() -> None:  # pragma: no cover
        pytest.skip("hypothesis not installed")

    def test_property_allowed_values_restriction_is_breaking() -> None:  # pragma: no cover
        pytest.skip("hypothesis not installed")
