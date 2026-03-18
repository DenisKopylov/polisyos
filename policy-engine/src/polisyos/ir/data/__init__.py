"""ir.data — Data Engine for the Perla-Barenboim causal engine.

Provides domain-aware data harmonization and reproducible dataset versioning.

Public API
----------
harmonizer
    DomainHarmonizer, HarmonizationReport, MissingVariableStrategy,
    ResolvedMapping, TypeMismatch, MissingVariableRecord

versioning
    DatasetVersion, version_dataset, compute_content_hash, compute_schema_hash
"""

from polisyos.ir.data.harmonizer import (
    DomainHarmonizer,
    HarmonizationReport,
    MissingVariableRecord,
    MissingVariableStrategy,
    ResolvedMapping,
    TypeMismatch,
)
from polisyos.ir.data.versioning import (
    DatasetVersion,
    compute_content_hash,
    compute_schema_hash,
    version_dataset,
)

__all__ = [
    # harmonizer
    "DomainHarmonizer",
    "HarmonizationReport",
    "MissingVariableRecord",
    "MissingVariableStrategy",
    "ResolvedMapping",
    "TypeMismatch",
    # versioning
    "DatasetVersion",
    "compute_content_hash",
    "compute_schema_hash",
    "version_dataset",
]
