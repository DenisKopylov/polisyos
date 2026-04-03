"""Public fabric config module API."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

NORMALIZATION_RULES = [
    {"pattern": r"\s+", "repl": "_"},
    {"pattern": r"[^a-zA-Z0-9_]", "repl": ""},
    {"pattern": r"_+", "repl": "_"},
]

RECONCILIATION_RULES = {
    "paid_tax": {"debit": "from_id", "credit": "to_id"},
    "transfer": {"debit": "from_id", "credit": "to_id"},
}

DEFAULT_RECONCILIATION_TOLERANCE = 1e-6


@dataclass
class CatalogConfig:
    """
    Configuration for the Data Contract catalog.

    Attributes:
        contracts_file: Filename for data contracts JSON
        search_threshold: Minimum confidence for auto-resolution (0.0-1.0)
        max_search_results: Maximum results from metric search
        strict_validation: If True, raise on invalid contracts
        allow_deprecated: If True, allow access to deprecated metrics
    """

    contracts_file: str = "data_contracts.json"
    search_threshold: float = 0.7
    max_search_results: int = 5
    strict_validation: bool = True
    allow_deprecated: bool = True


@dataclass
class FabricConfig:
    """
    Master configuration for the Fabric module.
    """

    curated_dir: Path = field(default_factory=lambda: Path("data/curated"))
    staging_dir: Path = field(default_factory=lambda: Path("data/staging"))
    raw_dir: Path = field(default_factory=lambda: Path("data/raw"))
    catalog: CatalogConfig = field(default_factory=CatalogConfig)

    def __post_init__(self) -> None:
        """Ensure paths are Path objects."""

        self.curated_dir = Path(self.curated_dir)
        self.staging_dir = Path(self.staging_dir)
        self.raw_dir = Path(self.raw_dir)
