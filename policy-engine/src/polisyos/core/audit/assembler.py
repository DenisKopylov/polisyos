"""Audit package assembler -- bundles audit artifacts into signed packages."""

from __future__ import annotations

from polisyos.core.audit._assembler_archive import (
    build_index,
    compute_file_checksums,
    create_deterministic_tarball,
    normalize_archive_path,
    write_checksums,
    write_json,
)
from polisyos.core.audit._assembler_core import AuditPackageAssembler
from polisyos.core.audit._assembler_errors import (
    AuditAssemblyError,
    IncompleteAuditError,
    IncompleteRunError,
    RunNotFoundError,
    UnsignedArtifactError,
)
from polisyos.core.audit._assembler_provenance import (
    build_merged_provenance,
    collect_public_keys,
    collect_signatures,
)
from polisyos.core.audit._assembler_slsa import (
    attach_sbom,
    build_slsa_bundle,
    extract_sbom_metadata,
    find_decision_packet_id,
)

__all__ = [
    "AuditAssemblyError",
    "AuditPackageAssembler",
    "IncompleteAuditError",
    "IncompleteRunError",
    "RunNotFoundError",
    "UnsignedArtifactError",
    "attach_sbom",
    "build_index",
    "build_merged_provenance",
    "build_slsa_bundle",
    "collect_public_keys",
    "collect_signatures",
    "compute_file_checksums",
    "create_deterministic_tarball",
    "extract_sbom_metadata",
    "find_decision_packet_id",
    "normalize_archive_path",
    "write_checksums",
    "write_json",
]
