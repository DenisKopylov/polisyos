"""
Tests for the Data Contract catalog system.

Covers:
- Contract validation and serialization
- MetricBinding hash integrity
- MetricSearcher disambiguation logic
- DataContractRegistry loading and validation
- Bootstrap tool type mapping
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from polisyos.fabric.catalog.binding import MetricBinding
from polisyos.fabric.catalog.contract import (
    DataContract,
    DataContractCollection,
    DataType,
    Granularity,
    PIITier,
)
from polisyos.fabric.catalog.registry import (
    ContractHashMismatchError,
    ContractNotFoundError,
    DataContractRegistry,
)
from polisyos.fabric.catalog.search import MetricSearcher


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_contracts() -> list[DataContract]:
    """Create a set of sample contracts for testing."""
    return [
        DataContract(
            metric_id="us.macro.gdp_nominal",
            display_name="Nominal GDP",
            description="Gross Domestic Product in current USD",
            dtype=DataType.FLOAT,
            unit="billion_usd",
            granularity=Granularity.QUARTERLY,
            source_system="simulation.duckdb",
            source_table="macro_history",
            source_column="gdp",
            pii_tier=PIITier.NONE,
            aliases=["gdp", "gross domestic product", "nominal gdp"],
            tags=["macro", "economy"],
        ),
        DataContract(
            metric_id="us.macro.gdp_real",
            display_name="Real GDP",
            description="Gross Domestic Product adjusted for inflation",
            dtype=DataType.FLOAT,
            unit="billion_usd_2020",
            granularity=Granularity.QUARTERLY,
            source_system="simulation.duckdb",
            source_table="macro_history",
            source_column="gdp_real",
            pii_tier=PIITier.NONE,
            aliases=["real gdp", "gdp constant"],
            tags=["macro", "economy"],
        ),
        DataContract(
            metric_id="us.macro.unemployment_rate",
            display_name="Unemployment Rate",
            description="Percentage of labor force without employment",
            dtype=DataType.FLOAT,
            unit="ratio",
            granularity=Granularity.MONTHLY,
            valid_range=(0.0, 1.0),
            source_system="simulation.duckdb",
            source_table="macro_history",
            source_column="unemployment_rate",
            pii_tier=PIITier.NONE,
            aliases=["unemployment", "jobless rate"],
            tags=["macro", "labor"],
        ),
        DataContract(
            metric_id="agent.income.salary",
            display_name="Agent Salary",
            description="Individual agent salary",
            dtype=DataType.FLOAT,
            unit="usd",
            granularity=Granularity.AGENT,
            source_system="simulation.duckdb",
            source_table="agents_snapshot",
            source_column="income",
            pii_tier=PIITier.LOW,
            aliases=["salary", "wage", "income"],
            tags=["agent", "income"],
        ),
        DataContract(
            metric_id="deprecated.old_metric",
            display_name="Old Metric (Deprecated)",
            description="This metric is deprecated",
            dtype=DataType.FLOAT,
            source_system="legacy.duckdb",
            pii_tier=PIITier.NONE,
            deprecated=True,
            superseded_by="us.macro.gdp_nominal",
        ),
    ]


@pytest.fixture
def contracts_file(sample_contracts: list[DataContract], tmp_path: Path) -> Path:
    """Create a temporary contracts JSON file."""
    collection = DataContractCollection(
        schema_version="1.0",
        contracts=sample_contracts,
    )

    contracts_path = tmp_path / "data_contracts.json"
    contracts_path.write_text(collection.model_dump_json(indent=2))

    return tmp_path


# =============================================================================
# Contract Validation Tests
# =============================================================================


class TestDataContract:
    """Tests for DataContract model validation."""

    def test_valid_contract_creation(self) -> None:
        """Test creating a valid contract."""
        contract = DataContract(
            metric_id="test.metric.value",
            display_name="Test Metric",
            description="A test metric for validation",
            dtype=DataType.FLOAT,
            source_system="test.duckdb",
        )

        assert contract.metric_id == "test.metric.value"
        assert contract.dtype == DataType.FLOAT
        assert contract.pii_tier == PIITier.NONE

    def test_invalid_metric_id_rejected(self) -> None:
        """Test that invalid metric_ids are rejected."""
        with pytest.raises(ValueError, match="pattern"):
            DataContract(
                metric_id="Invalid-ID",
                display_name="Test",
                description="Test",
                dtype=DataType.INT,
                source_system="test.duckdb",
            )

    def test_aliases_normalized_to_lowercase(self) -> None:
        """Test that aliases are normalized to lowercase."""
        contract = DataContract(
            metric_id="test.metric",
            display_name="Test",
            description="Test",
            dtype=DataType.STRING,
            source_system="test.duckdb",
            aliases=["GDP", "Gross Product", "  padded  "],
        )

        assert contract.aliases == ["gdp", "gross product", "padded"]

    def test_valid_range_validation(self) -> None:
        """Test that valid_range min <= max."""
        with pytest.raises(ValueError, match="min.*max"):
            DataContract(
                metric_id="test.metric",
                display_name="Test",
                description="Test",
                dtype=DataType.FLOAT,
                source_system="test.duckdb",
                valid_range=(100.0, 0.0),
            )

    def test_contract_immutability(self) -> None:
        """Test that contracts are frozen (immutable)."""
        contract = DataContract(
            metric_id="test.metric",
            display_name="Test",
            description="Test",
            dtype=DataType.INT,
            source_system="test.duckdb",
        )

        with pytest.raises(Exception):
            contract.metric_id = "changed"


class TestDataContractCollection:
    """Tests for DataContractCollection validation."""

    def test_duplicate_metric_ids_rejected(self, sample_contracts: list[DataContract]) -> None:
        """Test that duplicate metric_ids are rejected."""
        duplicate = DataContract(
            metric_id=sample_contracts[0].metric_id,
            display_name="Duplicate",
            description="Duplicate metric",
            dtype=DataType.INT,
            source_system="test.duckdb",
        )

        with pytest.raises(ValueError, match="Duplicate"):
            DataContractCollection(contracts=sample_contracts + [duplicate])


# =============================================================================
# Binding Tests
# =============================================================================


class TestMetricBinding:
    """Tests for MetricBinding hash integrity."""

    def test_binding_from_contract(self, sample_contracts: list[DataContract]) -> None:
        """Test creating a binding from a contract."""
        contract = sample_contracts[0]
        binding = MetricBinding.from_contract(contract)

        assert binding.metric_id == contract.metric_id
        assert binding.dtype == contract.dtype.value
        assert binding.unit == contract.unit
        assert len(binding.contract_hash) == 16

    def test_binding_hash_changes_with_contract(self) -> None:
        """Test that changing a contract changes the binding hash."""
        contract_v1 = DataContract(
            metric_id="test.metric",
            display_name="Test V1",
            description="Version 1",
            dtype=DataType.FLOAT,
            source_system="test.duckdb",
        )

        contract_v2 = DataContract(
            metric_id="test.metric",
            display_name="Test V2",
            description="Version 2",
            dtype=DataType.FLOAT,
            source_system="test.duckdb",
        )

        binding_v1 = MetricBinding.from_contract(contract_v1)
        binding_v2 = MetricBinding.from_contract(contract_v2)

        assert binding_v1.contract_hash != binding_v2.contract_hash

    def test_binding_hash_stable_for_same_contract(self, sample_contracts: list[DataContract]) -> None:
        """Test that the same contract always produces the same hash."""
        contract = sample_contracts[0]

        binding1 = MetricBinding.from_contract(contract)
        binding2 = MetricBinding.from_contract(contract)

        assert binding1.contract_hash == binding2.contract_hash

    def test_binding_is_immutable(self, sample_contracts: list[DataContract]) -> None:
        """Test that bindings are frozen."""
        binding = MetricBinding.from_contract(sample_contracts[0])

        with pytest.raises(Exception):
            binding.metric_id = "changed"

    def test_binding_serialization(self, sample_contracts: list[DataContract]) -> None:
        """Test binding to/from dict serialization."""
        binding = MetricBinding.from_contract(sample_contracts[0])

        data = binding.to_dict()
        restored = MetricBinding.from_dict(data)

        assert restored == binding


# =============================================================================
# Registry Tests
# =============================================================================


class TestDataContractRegistry:
    """Tests for DataContractRegistry loading and validation."""

    def test_registry_loads_contracts(self, contracts_file: Path) -> None:
        """Test that registry loads contracts from file."""
        registry = DataContractRegistry(contracts_file)

        assert len(registry) == 5
        assert "us.macro.gdp_nominal" in registry

    def test_registry_get_contract(self, contracts_file: Path) -> None:
        """Test getting a contract by ID."""
        registry = DataContractRegistry(contracts_file)

        contract = registry.get("us.macro.gdp_nominal")
        assert contract.display_name == "Nominal GDP"

    def test_registry_get_missing_raises(self, contracts_file: Path) -> None:
        """Test that getting a missing contract raises."""
        registry = DataContractRegistry(contracts_file)

        with pytest.raises(ContractNotFoundError):
            registry.get("nonexistent.metric")

    def test_registry_validate_binding_success(self, contracts_file: Path) -> None:
        """Test validating a binding that matches."""
        registry = DataContractRegistry(contracts_file)

        binding = registry.get_binding("us.macro.gdp_nominal")
        contract = registry.validate_binding(binding)

        assert contract.metric_id == binding.metric_id

    def test_registry_validate_binding_mismatch(self, contracts_file: Path) -> None:
        """Test that changed contracts fail validation."""
        registry = DataContractRegistry(contracts_file)
        binding = registry.get_binding("us.macro.gdp_nominal")

        contracts_path = contracts_file / "data_contracts.json"
        data = json.loads(contracts_path.read_text())
        data["contracts"][0]["description"] = "CHANGED DESCRIPTION"
        contracts_path.write_text(json.dumps(data))

        registry2 = DataContractRegistry(contracts_file)

        with pytest.raises(ContractHashMismatchError):
            registry2.validate_binding(binding)

    def test_registry_missing_file_warning(self, tmp_path: Path) -> None:
        """Test that missing contracts file produces warning, not error."""
        registry = DataContractRegistry(tmp_path)

        assert len(registry) == 0


# =============================================================================
# Search Tests
# =============================================================================


class TestMetricSearcher:
    """Tests for MetricSearcher disambiguation logic."""

    def test_exact_alias_match(self, sample_contracts: list[DataContract]) -> None:
        """Test that exact alias match returns confidence 1.0."""
        searcher = MetricSearcher(sample_contracts)

        response = searcher.search("gdp")

        assert not response.needs_disambiguation
        assert response.best_match is not None
        assert response.best_match.confidence == 1.0

    def test_ambiguous_query_needs_disambiguation(
        self, sample_contracts: list[DataContract]
    ) -> None:
        """Test that ambiguous queries flag disambiguation."""
        searcher = MetricSearcher(sample_contracts, threshold=0.7)

        response = searcher.search("gdp real nominal")

        assert response.needs_disambiguation
        assert len(response.results) >= 2

    def test_ambiguous_query_uses_best_alias_per_metric(
        self, sample_contracts: list[DataContract]
    ) -> None:
        """Weak aliases encountered first should not suppress stronger matches later."""
        searcher = MetricSearcher(sample_contracts, threshold=0.7)
        searcher._alias_index = {
            "gdp": ["us.macro.gdp_nominal"],
            "us.macro.gdp_real": ["us.macro.gdp_real"],
            "nominal gdp": ["us.macro.gdp_nominal"],
            "real gdp": ["us.macro.gdp_real"],
        }

        response = searcher.search("gdp real nominal")

        assert response.needs_disambiguation
        confidences = {result.binding.metric_id: result.confidence for result in response.results}
        assert confidences["us.macro.gdp_nominal"] > 0.8
        assert confidences["us.macro.gdp_real"] > 0.6

    def test_no_results_needs_disambiguation(self, sample_contracts: list[DataContract]) -> None:
        """Test that no results flags disambiguation."""
        searcher = MetricSearcher(sample_contracts)

        response = searcher.search("nonexistent_metric_xyz")

        assert response.needs_disambiguation
        assert len(response.results) == 0

    def test_fuzzy_match_unemployment(self, sample_contracts: list[DataContract]) -> None:
        """Test fuzzy matching finds unemployment."""
        searcher = MetricSearcher(sample_contracts)

        response = searcher.search("unemployment")

        assert not response.needs_disambiguation
        assert response.best_match is not None
        assert response.best_match.binding.metric_id == "us.macro.unemployment_rate"

    def test_resolve_convenience_method(self, sample_contracts: list[DataContract]) -> None:
        """Test the resolve() convenience method."""
        searcher = MetricSearcher(sample_contracts)

        binding = searcher.resolve("unemployment")

        assert binding.metric_id == "us.macro.unemployment_rate"

    def test_resolve_ambiguous_raises(self, sample_contracts: list[DataContract]) -> None:
        """Test that resolve() raises on ambiguous queries."""
        searcher = MetricSearcher(sample_contracts, threshold=0.99)

        with pytest.raises(ValueError, match="Ambiguous"):
            searcher.resolve("product")

    def test_deprecated_result_present(self, sample_contracts: list[DataContract]) -> None:
        """Test that deprecated metrics are flagged in results."""
        searcher = MetricSearcher(sample_contracts)

        response = searcher.search("old_metric")

        assert len(response.results) > 0
        deprecated_result = [result for result in response.results if result.is_deprecated]
        assert len(deprecated_result) > 0


# =============================================================================
# Type Mapping Tests (for Bootstrap Tool)
# =============================================================================


class TestDuckDBTypeMapping:
    """Tests for DuckDB type mapping in bootstrap tool."""

    @pytest.mark.parametrize(
        "duckdb_type,expected",
        [
            ("INTEGER", "int"),
            ("BIGINT", "int"),
            ("INT8", "int"),
            ("FLOAT", "float"),
            ("DOUBLE", "float"),
            ("DECIMAL(10,2)", "float"),
            ("BOOLEAN", "boolean"),
            ("BOOL", "boolean"),
            ("VARCHAR", "string"),
            ("VARCHAR(255)", "string"),
            ("TEXT", "string"),
            ("TIMESTAMP", "datetime"),
            ("DATE", "datetime"),
            ("INTEGER[]", "array"),
            ("VARCHAR[]", "array"),
            ("JSON", "json"),
            ("STRUCT(a INT, b VARCHAR)", "json"),
            ("UNKNOWN_TYPE", "string"),
        ],
    )
    def test_type_mapping(self, duckdb_type: str, expected: str) -> None:
        """Test DuckDB type to DataType mapping."""
        import re

        duckdb_type_map = {
            "INTEGER": "int",
            "BIGINT": "int",
            "INT8": "int",
            "INT": "int",
            "FLOAT": "float",
            "DOUBLE": "float",
            "DECIMAL": "float",
            "BOOLEAN": "boolean",
            "BOOL": "boolean",
            "VARCHAR": "string",
            "TEXT": "string",
            "STRING": "string",
            "TIMESTAMP": "datetime",
            "DATE": "datetime",
            "TIME": "datetime",
            "JSON": "json",
            "STRUCT": "json",
        }

        dtype_upper = duckdb_type.upper()
        if dtype_upper.endswith("[]"):
            result = "array"
        else:
            base_type = re.split(r"[(\[]", dtype_upper)[0].strip()
            result = duckdb_type_map.get(base_type, "string")

        assert result == expected


# =============================================================================
# Integration Tests
# =============================================================================


class TestCatalogIntegration:
    """Integration tests for the full catalog workflow."""

    def test_full_workflow(self, contracts_file: Path) -> None:
        """Test the full workflow: load -> search -> bind -> validate."""
        registry = DataContractRegistry(contracts_file)

        searcher = MetricSearcher(list(registry))

        response = searcher.search("gdp")
        assert not response.needs_disambiguation

        binding = response.best_match.binding

        contract = registry.validate_binding(binding)
        assert contract.metric_id == binding.metric_id

    def test_scientist_cannot_use_arbitrary_name(self, contracts_file: Path) -> None:
        """Test that arbitrary metric names must go through search."""
        registry = DataContractRegistry(contracts_file)

        with pytest.raises(ContractNotFoundError):
            registry.get("invented.metric.name")

        searcher = MetricSearcher(list(registry))
        response = searcher.search("gdp")

        assert response.best_match is not None
