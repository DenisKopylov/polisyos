"""
Data Contract Registry -- loads, caches, and validates metric contracts.

This registry coexists with ManifestRegistry:
- ManifestRegistry: dataset-level (file granularity)
- DataContractRegistry: metric-level (column granularity)
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from pydantic import ValidationError

from polisyos.common.logger import logger
from polisyos.core.errors import ErrorCategory, PolicyOSError
from polisyos.core.registry.generic import GenericRegistry

from .binding import MetricBinding
from .contract import DataContract, DataContractCollection


class ContractNotFoundError(PolicyOSError):
    """Raised when a metric contract is not found."""

    default_stage = "fabric.catalog"
    default_category = ErrorCategory.VALIDATION


class ContractHashMismatchError(PolicyOSError):
    """Raised when a binding's hash doesn't match the current contract."""

    default_stage = "fabric.catalog"
    default_category = ErrorCategory.VALIDATION


class DataContractRegistry:
    """
    Registry for metric-level data contracts.

    Loads contracts from JSON file and provides:
    - Fast lookup by metric_id
    - Binding validation (hash check)
    - Iteration over all contracts
    """

    DEFAULT_FILENAME = "data_contracts.json"

    def __init__(
        self,
        curated_dir: Path,
        filename: str = DEFAULT_FILENAME,
        strict: bool = True,
    ) -> None:
        """
        Initialize the registry.

        Args:
            curated_dir: Directory containing data_contracts.json
            filename: Contract collection filename
            strict: If True, raise on invalid contracts; if False, skip them
        """

        self.curated_dir = curated_dir
        self.contracts_path = curated_dir / filename
        self._strict = strict

        self._contracts = GenericRegistry[str, DataContract](
            key_fn=lambda contract: contract.metric_id
        )
        self._bindings_cache: dict[str, MetricBinding] = {}
        self._collection: DataContractCollection | None = None

        self._load_contracts()

    def _load_contracts(self) -> None:
        """Load contracts from JSON file."""

        if not self.contracts_path.exists():
            logger.warning(
                f"No data contracts file found at {self.contracts_path}. "
                "Run `python tools/diagnostics/scan_fabric.py` to generate draft contracts."
            )
            return

        try:
            raw = self.contracts_path.read_text(encoding="utf-8")
            self._collection = DataContractCollection.model_validate_json(raw)
        except ValidationError as exc:
            if self._strict:
                raise ValueError(
                    f"Invalid data contracts file {self.contracts_path}: {exc}"
                ) from exc
            logger.error(f"Invalid contracts file, skipping: {exc}")
            return
        except json.JSONDecodeError as exc:
            if self._strict:
                raise ValueError(f"Invalid JSON in {self.contracts_path}: {exc}") from exc
            logger.error(f"Invalid JSON in contracts file: {exc}")
            return

        for contract in self._collection.contracts:
            self._contracts.register(contract, override=True)

        logger.info(f"Loaded {self._contracts.count} data contracts from {self.contracts_path}")

    def get(self, metric_id: str) -> DataContract:
        """
        Get a contract by metric_id.

        Args:
            metric_id: The canonical metric identifier

        Returns:
            The DataContract

        Raises:
            ContractNotFoundError: If metric_id not found
        """

        contract = self._contracts.get(metric_id)
        if contract is None:
            raise ContractNotFoundError(
                f"No contract found for metric_id '{metric_id}'. "
                f"Available: {self.list_all()[:5]}..."
            )
        return contract

    def get_binding(self, metric_id: str) -> MetricBinding:
        """
        Get a MetricBinding for the given metric_id.

        Bindings are cached for performance.
        """

        if metric_id not in self._bindings_cache:
            contract = self.get(metric_id)
            self._bindings_cache[metric_id] = MetricBinding.from_contract(contract)
        return self._bindings_cache[metric_id]

    def validate_binding(self, binding: MetricBinding) -> DataContract:
        """
        Validate that a binding's hash matches the current contract.

        This catches "contract drift" -- when a contract was changed
        after the Scientist received its binding.

        Args:
            binding: The MetricBinding to validate

        Returns:
            The current DataContract if valid

        Raises:
            ContractNotFoundError: If metric not found
            ContractHashMismatchError: If hash doesn't match
        """

        contract = self.get(binding.metric_id)
        current_binding = MetricBinding.from_contract(contract)

        if current_binding.contract_hash != binding.contract_hash:
            raise ContractHashMismatchError(
                f"Contract for '{binding.metric_id}' has changed. "
                f"Binding hash: {binding.contract_hash}, "
                f"Current hash: {current_binding.contract_hash}. "
                "Re-resolve the metric to get an updated binding."
            )

        return contract

    def list_all(self) -> list[str]:
        """Return all metric_ids in the registry."""

        return self._contracts.keys()

    def __contains__(self, metric_id: str) -> bool:
        """Check if a metric_id exists in the registry."""

        return self._contracts.get(metric_id) is not None

    def __len__(self) -> int:
        """Return number of contracts in the registry."""

        return self._contracts.count

    def __iter__(self) -> Iterator[DataContract]:
        """Iterate over all contracts."""

        return iter(self._contracts.values())

    @property
    def schema_version(self) -> str | None:
        """Return the schema version of the contract collection."""

        return self._collection.schema_version if self._collection else None
