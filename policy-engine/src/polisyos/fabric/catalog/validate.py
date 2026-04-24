"""Contract validation utilities for the data catalog."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from .contract import DataContractCollection


class ContractValidationError(ValueError):
    """Raised when contract files fail validation."""


def load_contract_collection(path: Path) -> DataContractCollection:
    """
    Load and validate a DataContractCollection from JSON.

    Args:
        path: Path to the data_contracts.json file

    Raises:
        FileNotFoundError: If the file does not exist
        ContractValidationError: If JSON or schema validation fails
    """

    if not path.exists():
        raise FileNotFoundError(f"Contracts file not found: {path}")

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContractValidationError(f"Failed to read contracts file: {exc}") from exc

    try:
        return DataContractCollection.model_validate_json(raw)
    except ValidationError as exc:
        raise ContractValidationError(f"Invalid contracts file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ContractValidationError(f"Invalid JSON in contracts file: {exc}") from exc
