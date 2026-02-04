from __future__ import annotations

from .api import (
    build_legal_structure,
    build_version_index,
    ingest_legal_doc_bytes,
    resolve_active_version,
)
from .errors import (
    LexError,
    LexIndexError,
    LexIngestError,
    LexNotReadyError,
    LexStructureError,
    LexValidationError,
    LexVersioningError,
)
from .types import (
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

__all__ = [
    "ActiveVersionResult",
    "ActiveVersionStrategy",
    "LegalDocSource",
    "LexError",
    "LexIndexError",
    "LexIngestError",
    "LexIngestOptions",
    "LexIngestResult",
    "LexNotReadyError",
    "LexStructureError",
    "LexStructureOptions",
    "LexStructureResult",
    "LexValidationError",
    "LexVersionIndexOptions",
    "LexVersionIndexResult",
    "LexVersioningError",
    "WorldEventRefLike",
    "build_legal_structure",
    "build_version_index",
    "ingest_legal_doc_bytes",
    "resolve_active_version",
]
