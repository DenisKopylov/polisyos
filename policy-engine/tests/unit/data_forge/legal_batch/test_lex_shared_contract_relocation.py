"""Compatibility coverage for Data Forge-owned former Lex shared contracts."""

from __future__ import annotations

from polisyos.common.timestamps import latest_object_by_subject, parse_iso_date
from polisyos.data_forge.domains.legal.contracts import (
    ActiveVersionResult,
    ActiveVersionStrategy,
    LegalDocSource,
    LexIngestOptions,
    LexIngestResult,
    LexStructureOptions,
    LexStructureResult,
    LexVersionIndexOptions,
    LexVersionIndexResult,
    WorldEventRefLike,
)
from polisyos.data_forge.errors import (
    LexError,
    LexIndexError,
    LexIngestError,
    LexNotReadyError,
    LexStructureError,
    LexValidationError,
    LexVersioningError,
)
from polisyos.data_forge.kernel.artifacts import (
    load_doc_meta_artifact,
    load_json_artifact,
)
from polisyos.fabric.world import load_world_facts
from polisyos.lex import artifacts, common, errors, factlog, types


def test_lex_shared_contracts_are_data_forge_canonical_objects() -> None:
    """Keep legacy Lex imports as identity-preserving compatibility aliases."""
    assert common.parse_iso_date is parse_iso_date
    assert common.latest_object_by_subject is latest_object_by_subject
    assert artifacts.load_json_artifact is load_json_artifact
    assert artifacts.load_doc_meta_artifact is load_doc_meta_artifact
    assert factlog.load_world_facts is load_world_facts

    assert errors.LexError is LexError
    assert errors.LexIndexError is LexIndexError
    assert errors.LexIngestError is LexIngestError
    assert errors.LexNotReadyError is LexNotReadyError
    assert errors.LexStructureError is LexStructureError
    assert errors.LexValidationError is LexValidationError
    assert errors.LexVersioningError is LexVersioningError

    assert types.LegalDocSource is LegalDocSource
    assert types.LexIngestOptions is LexIngestOptions
    assert types.LexIngestResult is LexIngestResult
    assert types.LexStructureOptions is LexStructureOptions
    assert types.LexStructureResult is LexStructureResult
    assert types.LexVersionIndexOptions is LexVersionIndexOptions
    assert types.LexVersionIndexResult is LexVersionIndexResult
    assert types.WorldEventRefLike is WorldEventRefLike
    assert types.ActiveVersionStrategy is ActiveVersionStrategy
    assert types.ActiveVersionResult is ActiveVersionResult
