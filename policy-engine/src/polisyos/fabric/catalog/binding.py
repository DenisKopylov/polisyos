"""
Hash-locked metric binding for Scientist agent.

The MetricBinding is what the Scientist agent holds after resolving
an input query. It provides a tamper-evident reference that ensures
its contract definition has not changed since the binding was created.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.canon import truncated_hash
from polisyos.fabric.connectors.contracts.registry import SchemaRegistry
from polisyos.fabric.connectors.contracts.schema import (
    DataSchema,
    SchemaType,
    SchemaVersion,
    normalize_unit_id,
)

if TYPE_CHECKING:
    from .contract import DataContract
    from .contract import DataType as ContractDataType


@dataclass(frozen=True, slots=True)
class MetricBinding:
    """
    Bound reference to a metric that Scientist must use.

    The Scientist agent cannot request metrics by arbitrary name --
    only by holding a validated MetricBinding. This prevents:

    1. Hallucination of metric names
    2. Silent contract drift (hash changes if contract changes)
    3. Type mismatches (dtype/unit are locked in)

    Attributes:
        metric_id: Canonical metric identifier
        unit: Unit of measurement (locked)
        dtype: Data type string (locked)
        dimensions: Tuple of dimension columns (immutable)
        pii_tier: Privacy tier (for access control)
        contract_hash: SHA-256 hash of the full contract (truncated)
    """

    metric_id: str
    unit: str | None
    dtype: str
    dimensions: tuple[str, ...]
    pii_tier: str
    contract_hash: str

    @classmethod
    def from_contract(cls, contract: "DataContract") -> "MetricBinding":
        """
        Create binding from a validated contract.

        The hash is computed from the full contract JSON to detect
        any changes to the contract definition.
        """

        contract_bytes = contract.model_dump_json(
            indent=None,
            exclude_none=False,
        ).encode("utf-8")

        # SHA-256 truncated to 16 hex chars (64 bits) for compactness.
        contract_hash = truncated_hash(contract_bytes, length=16)

        return cls(
            metric_id=contract.metric_id,
            unit=contract.unit,
            dtype=contract.dtype.value,
            dimensions=tuple(contract.dimensions),
            pii_tier=contract.pii_tier.value,
            contract_hash=contract_hash,
        )

    def __str__(self) -> str:
        """Compact string representation for logging/display."""

        return f"{self.metric_id}@{self.contract_hash}"

    def __repr__(self) -> str:
        """Full representation for debugging."""

        return (
            "MetricBinding("
            f"metric_id={self.metric_id!r}, "
            f"dtype={self.dtype!r}, "
            f"unit={self.unit!r}, "
            f"hash={self.contract_hash!r})"
        )

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""

        return {
            "metric_id": self.metric_id,
            "unit": self.unit,
            "dtype": self.dtype,
            "dimensions": list(self.dimensions),
            "pii_tier": self.pii_tier,
            "contract_hash": self.contract_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MetricBinding":
        """Deserialize from dictionary."""

        return cls(
            metric_id=data["metric_id"],
            unit=data.get("unit"),
            dtype=data["dtype"],
            dimensions=tuple(data.get("dimensions", [])),
            pii_tier=data.get("pii_tier", "none"),
            contract_hash=data["contract_hash"],
        )


def _map_contract_dtype(dtype: "ContractDataType") -> SchemaType:
    mapping = {
        "int": SchemaType.INT64,
        "float": SchemaType.FLOAT64,
        "string": SchemaType.STRING,
        "boolean": SchemaType.BOOLEAN,
        "datetime": SchemaType.DATETIME,
        "array": SchemaType.ARRAY,
        "json": SchemaType.JSON,
    }
    return mapping[dtype.value]


class DataContractSchemaBinding(BaseModel):
    """
    Binds a DataContract (metric-level) to its parent DataSchema (dataset-level).

    This allows:
    1. Validating that a contract's dtype matches schema field type
    2. Resolving effective unit/semantic information from the schema
    3. Tracing metric provenance to source dataset
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract: "DataContract"
    schema_id: str
    schema_version: str
    field_name: str = Field(min_length=1)
    schema_content_hash: str

    schema_type: str
    effective_unit_id: str | None = None
    effective_semantic_type: str | None = None

    @classmethod
    def bind(
        cls,
        contract: "DataContract",
        schema: DataSchema,
        field_name: str,
    ) -> "DataContractSchemaBinding":
        field = schema.get_field(field_name)
        if field is None:
            raise ValueError(
                f"Field '{field_name}' not found in schema '{schema.schema_id}'"
            )

        contract_type = _map_contract_dtype(contract.dtype)
        schema_type = field.data_type

        if not (
            contract_type.is_compatible_with(schema_type)
            or schema_type.is_compatible_with(contract_type)
        ):
            raise ValueError(
                f"Contract dtype {contract.dtype.value} incompatible with schema field "
                f"{field.name}:{schema_type.value}"
            )

        contract_unit = (
            normalize_unit_id(contract.unit) if contract.unit else None
        )
        schema_unit = field.unit.unit_id if field.unit else None
        if contract_unit and schema_unit and contract_unit != schema_unit:
            raise ValueError(
                f"Unit mismatch for field '{field.name}': contract={contract.unit} "
                f"schema={schema_unit}"
            )

        effective_unit = schema_unit or contract_unit
        effective_semantic = (
            field.semantic_type.value if field.semantic_type else None
        )

        return cls(
            contract=contract,
            schema_id=schema.schema_id,
            schema_version=str(schema.version),
            field_name=field.name,
            schema_content_hash=schema.content_hash,
            schema_type=schema_type.value,
            effective_unit_id=effective_unit,
            effective_semantic_type=effective_semantic,
        )

    @classmethod
    def bind_from_registry(
        cls,
        contract: "DataContract",
        registry: SchemaRegistry,
        schema_id: str,
        schema_version: str,
        field_name: str,
    ) -> "DataContractSchemaBinding":
        schema = registry.get(schema_id, SchemaVersion.parse(schema_version))
        return cls.bind(contract, schema, field_name)
