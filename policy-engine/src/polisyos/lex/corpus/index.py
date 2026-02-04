from __future__ import annotations

from typing import Literal

from pydantic import BeforeValidator, ConfigDict, Field, model_validator
from typing_extensions import Annotated

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.ir.kernel.base import ARTIFACT_ID_PATTERN, ID_PATTERN, KernelModel, reject_floats_deep
from polisyos.lex.errors import LexIndexError

PROVISION_INDEX_KIND = "lex.corpus.provision_index"
VERSION_INDEX_KIND = "lex.corpus.version_index"
DOC_SOURCE_PROPS_KIND = "lex.corpus.doc_source_props"

_PROVISION_INDEX_SCHEMA = SchemaInfo(name="polisyos.lex.corpus.ProvisionIndex", version="1.0")
_VERSION_INDEX_SCHEMA = SchemaInfo(name="polisyos.lex.corpus.VersionIndex", version="1.0")
_DOC_SOURCE_PROPS_SCHEMA = SchemaInfo(name="polisyos.lex.corpus.DocSourceProps", version="1.0")


class ProvisionEntryV1(KernelModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provision_key: str
    fragment_id: str = Field(..., pattern=ID_PATTERN)
    citation_label: str
    parent_provision_key: str | None = None
    anchor_path: str
    offset_start: int = Field(..., ge=0)
    offset_end: int = Field(..., ge=0)
    kind: Literal["article", "part", "point", "subpoint", "paragraph"]
    number: str | None = None
    props: Annotated[
        dict[str, str | int | bool],
        BeforeValidator(reject_floats_deep),
    ] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_offsets(self) -> "ProvisionEntryV1":
        if self.offset_end <= self.offset_start:
            raise ValueError("offset_end must be > offset_start")
        return self


class ProvisionIndexV1(KernelModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    doc_source_id: str = Field(..., pattern=ID_PATTERN)
    doc_version_id: str = Field(..., pattern=ID_PATTERN)
    doc_meta_artifact_id: str = Field(..., pattern=ARTIFACT_ID_PATTERN)
    structure_algorithm_id: str
    range_semantics: Literal["python_slice"] = "python_slice"
    provisions: list[ProvisionEntryV1] = Field(default_factory=list)
    stats: Annotated[dict[str, int], BeforeValidator(reject_floats_deep)] = Field(
        default_factory=dict
    )
    quality_issues: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class VersionEntryV1(KernelModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_version_id: str = Field(..., pattern=ID_PATTERN)
    doc_meta_artifact_id: str = Field(..., pattern=ARTIFACT_ID_PATTERN)
    published_at: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    confidence: str
    quality_issues: list[str] = Field(default_factory=list)


class VersionIndexV1(KernelModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    doc_source_id: str = Field(..., pattern=ID_PATTERN)
    selection_policy_id: str
    versions: list[VersionEntryV1] = Field(default_factory=list)
    quality_issues: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class DocSourcePropsV1(KernelModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    doc_source_id: str = Field(..., pattern=ID_PATTERN)
    version_index_ref: str = Field(..., pattern=ARTIFACT_ID_PATTERN)
    updated_at_iso: str
    notes: list[str] = Field(default_factory=list)


def _load_json_artifact(cas: FileSystemCAS, artifact_id: str) -> dict:
    try:
        aid = ArtifactID.model_validate(artifact_id)
        payload = from_canonical_bytes(cas.get_bytes(aid))
    except Exception as exc:  # pragma: no cover - defensive
        raise LexIndexError(f"failed to read artifact {artifact_id}: {exc}") from exc
    if not isinstance(payload, dict):
        raise LexIndexError(f"artifact {artifact_id} payload must be a JSON object")
    return payload


def persist_provision_index(cas: FileSystemCAS, payload: ProvisionIndexV1) -> str:
    try:
        ref = cas.put_json(
            payload.model_dump(mode="python"),
            opts=PutOptions(
                kind=PROVISION_INDEX_KIND,
                media_type="application/json",
                schema=_PROVISION_INDEX_SCHEMA,
            ),
        )
        return str(ref.artifact_id)
    except Exception as exc:  # pragma: no cover - defensive
        raise LexIndexError(f"failed to persist provision index: {exc}") from exc


def persist_version_index(cas: FileSystemCAS, payload: VersionIndexV1) -> str:
    try:
        ref = cas.put_json(
            payload.model_dump(mode="python"),
            opts=PutOptions(
                kind=VERSION_INDEX_KIND,
                media_type="application/json",
                schema=_VERSION_INDEX_SCHEMA,
            ),
        )
        return str(ref.artifact_id)
    except Exception as exc:  # pragma: no cover - defensive
        raise LexIndexError(f"failed to persist version index: {exc}") from exc


def persist_doc_source_props(cas: FileSystemCAS, payload: DocSourcePropsV1) -> str:
    try:
        ref = cas.put_json(
            payload.model_dump(mode="python"),
            opts=PutOptions(
                kind=DOC_SOURCE_PROPS_KIND,
                media_type="application/json",
                schema=_DOC_SOURCE_PROPS_SCHEMA,
            ),
        )
        return str(ref.artifact_id)
    except Exception as exc:  # pragma: no cover - defensive
        raise LexIndexError(f"failed to persist doc source props: {exc}") from exc


def load_provision_index(cas: FileSystemCAS, artifact_id: str) -> ProvisionIndexV1:
    try:
        payload = _load_json_artifact(cas, artifact_id)
        return ProvisionIndexV1.model_validate(payload)
    except LexIndexError:
        raise
    except Exception as exc:
        raise LexIndexError(f"failed to parse provision index {artifact_id}: {exc}") from exc


def load_version_index(cas: FileSystemCAS, artifact_id: str) -> VersionIndexV1:
    try:
        payload = _load_json_artifact(cas, artifact_id)
        return VersionIndexV1.model_validate(payload)
    except LexIndexError:
        raise
    except Exception as exc:
        raise LexIndexError(f"failed to parse version index {artifact_id}: {exc}") from exc


def load_doc_source_props(cas: FileSystemCAS, artifact_id: str) -> DocSourcePropsV1:
    try:
        payload = _load_json_artifact(cas, artifact_id)
        return DocSourcePropsV1.model_validate(payload)
    except LexIndexError:
        raise
    except Exception as exc:
        raise LexIndexError(f"failed to parse doc source props {artifact_id}: {exc}") from exc


__all__ = [
    "DOC_SOURCE_PROPS_KIND",
    "PROVISION_INDEX_KIND",
    "VERSION_INDEX_KIND",
    "DocSourcePropsV1",
    "ProvisionEntryV1",
    "ProvisionIndexV1",
    "VersionEntryV1",
    "VersionIndexV1",
    "load_doc_source_props",
    "load_provision_index",
    "load_version_index",
    "persist_doc_source_props",
    "persist_provision_index",
    "persist_version_index",
]
