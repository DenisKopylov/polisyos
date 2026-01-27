"""
Hash-locked metric binding for Scientist agent.

The MetricBinding is what the Scientist agent holds after resolving
an input query. It provides a tamper-evident reference that ensures
its contract definition has not changed since the binding was created.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .contract import DataContract


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
        contract_hash = hashlib.sha256(contract_bytes).hexdigest()[:16]

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
