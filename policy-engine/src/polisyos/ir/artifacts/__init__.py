"""Public ir artifacts package API."""
from .contracts import (
    ArtifactID,
    ArtifactStore,
    CanonInfo,
    InputRef,
    PutOptions,
    SchemaInfo,
    StorePutOptions,
    normalize_artifact_ref,
    normalize_input_refs,
    to_store_put_options,
)
from .io import get_json_artifact, normalize_input_sequence, put_json_artifact

__all__ = [
    "ArtifactID",
    "ArtifactStore",
    "CanonInfo",
    "InputRef",
    "PutOptions",
    "SchemaInfo",
    "StorePutOptions",
    "get_json_artifact",
    "normalize_artifact_ref",
    "normalize_input_refs",
    "normalize_input_sequence",
    "put_json_artifact",
    "to_store_put_options",
]
