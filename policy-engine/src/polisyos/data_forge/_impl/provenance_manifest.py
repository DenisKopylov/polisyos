"""Closeout-grade provenance manifests for Data Forge snapshots."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from polisyos.data_forge.kernel._base import DataForgeModel

DATA_FORGE_PROVENANCE_MANIFEST_FILE = "data_forge_provenance_manifest.json"
DATA_FORGE_PROVENANCE_MANIFEST_SCHEMA_VERSION = (
    "policyos.data_forge.snapshot_provenance_manifest.v1"
)
_PASS_STATUSES = {"pass", "passed", "ok", "success"}


class SnapshotQualityGate(DataForgeModel):
    """Quality gate evidence attached to an official Data Forge snapshot."""

    name: str = Field(min_length=1)
    status: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)


class TransformLineageStep(DataForgeModel):
    """One transform step that contributed to a snapshot data hash."""

    step_id: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    input_refs: tuple[str, ...] = Field(default_factory=tuple)
    output_refs: tuple[str, ...] = Field(default_factory=tuple)
    code_ref: str | None = Field(default=None, min_length=1)
    config_ref: str | None = Field(default=None, min_length=1)


class SnapshotClaimRequirementBinding(DataForgeModel):
    """Claim requirement that an official snapshot can satisfy."""

    claim_id: str = Field(min_length=1)
    requirement_id: str = Field(min_length=1)
    requirement_kind: str = Field(min_length=1)
    authority_level: str = Field(min_length=1)
    time_role: str = Field(min_length=1)
    supported_by: tuple[str, ...] = Field(default_factory=tuple)
    lifecycle_dependency_refs: tuple[str, ...] = Field(default_factory=tuple)


class SnapshotProvenanceLedgerEntry(DataForgeModel):
    """Durable lineage ledger row for one role/corpus inside a snapshot."""

    role: str = Field(min_length=1)
    corpus_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    snapshot_ref: str = Field(min_length=1)
    release_id: str = Field(min_length=1)
    release_manifest_ref: str = Field(min_length=1)
    manifest_ref: str = Field(min_length=1)
    data_hash: str = Field(min_length=1)
    merkle_root: str = Field(min_length=1)
    creation_time: str = Field(min_length=1)
    lineage_refs: tuple[str, ...] = Field(min_length=1)
    quality_gates: tuple[SnapshotQualityGate, ...] = Field(min_length=1)
    builder_revision: str = Field(min_length=1)
    transform_lineage: tuple[TransformLineageStep, ...] = Field(min_length=1)
    claim_requirement_bindings: tuple[SnapshotClaimRequirementBinding, ...] = (
        Field(default_factory=tuple)
    )
    runtime_event_ref: str | None = Field(default=None, min_length=1)
    read_api_surface: str | None = Field(default=None, min_length=1)
    read_api_identity: str | None = Field(default=None, min_length=1)

    def quality_gates_pass(self) -> bool:
        """Return whether every attached quality gate has a passing status."""

        return all(gate.status.casefold() in _PASS_STATUSES for gate in self.quality_gates)


class OfficialSnapshotAnswer(DataForgeModel):
    """Typed answer for closeout's claim-to-official-snapshot query."""

    status: Literal["satisfied", "blocked", "not_found"]
    claim_id: str = Field(min_length=1)
    requirement_id: str | None = Field(default=None, min_length=1)
    role: str | None = Field(default=None, min_length=1)
    corpus_id: str | None = Field(default=None, min_length=1)
    snapshot_id: str | None = Field(default=None, min_length=1)
    snapshot_ref: str | None = Field(default=None, min_length=1)
    data_hash: str | None = Field(default=None, min_length=1)
    creation_time: str | None = Field(default=None, min_length=1)
    lineage_refs: tuple[str, ...] = Field(default_factory=tuple)
    quality_gates: tuple[SnapshotQualityGate, ...] = Field(default_factory=tuple)
    builder_revision: str | None = Field(default=None, min_length=1)
    transform_lineage: tuple[TransformLineageStep, ...] = Field(default_factory=tuple)
    supported_by: tuple[str, ...] = Field(default_factory=tuple)
    lifecycle_dependency_refs: tuple[str, ...] = Field(default_factory=tuple)
    reason: str | None = Field(default=None, min_length=1)


class SnapshotProvenanceManifest(DataForgeModel):
    """Durable provenance ledger written with each Data Forge snapshot transaction."""

    schema_version: str = DATA_FORGE_PROVENANCE_MANIFEST_SCHEMA_VERSION
    snapshot_id: str = Field(min_length=1)
    release_id: str = Field(min_length=1)
    generated_at: str = Field(min_length=1)
    entries: tuple[SnapshotProvenanceLedgerEntry, ...] = Field(min_length=1)

    def official_snapshot_for_claim(
        self,
        *,
        claim_id: str,
        requirement_id: str | None = None,
    ) -> OfficialSnapshotAnswer:
        """Return the official snapshot row satisfying a claim requirement, if any."""

        for entry in self.entries:
            for binding in entry.claim_requirement_bindings:
                if binding.claim_id != claim_id:
                    continue
                if requirement_id is not None and binding.requirement_id != requirement_id:
                    continue
                return _answer_from_entry(
                    entry=entry,
                    binding=binding,
                    status="satisfied" if entry.quality_gates_pass() else "blocked",
                    reason=None if entry.quality_gates_pass() else "quality_gate_failed",
                )
        return OfficialSnapshotAnswer(
            status="not_found",
            claim_id=claim_id,
            requirement_id=requirement_id,
            reason="claim_requirement_binding_missing",
        )


def build_snapshot_provenance_manifest(
    *,
    snapshot_id: str,
    release_id: str,
    generated_at: str,
    bindings: Sequence[Mapping[str, Any]],
) -> SnapshotProvenanceManifest:
    """Build a provenance manifest from normalized snapshot binding rows."""

    return SnapshotProvenanceManifest(
        snapshot_id=snapshot_id,
        release_id=release_id,
        generated_at=generated_at,
        entries=tuple(_entry_from_binding(binding) for binding in bindings),
    )


def write_snapshot_provenance_manifest(
    snapshot_root: str | Path,
    *,
    snapshot_id: str,
    release_id: str,
    generated_at: str,
    bindings: Sequence[Mapping[str, Any]],
) -> Path:
    """Persist the Data Forge snapshot provenance manifest beside the snapshot."""

    manifest = build_snapshot_provenance_manifest(
        snapshot_id=snapshot_id,
        release_id=release_id,
        generated_at=generated_at,
        bindings=bindings,
    )
    out_path = Path(snapshot_root) / DATA_FORGE_PROVENANCE_MANIFEST_FILE
    out_path.write_text(
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path


def load_snapshot_provenance_manifest(path: str | Path) -> SnapshotProvenanceManifest:
    """Load a Data Forge snapshot provenance manifest from disk."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return SnapshotProvenanceManifest.model_validate(payload)


def official_snapshot_answer_from_binding(
    binding: Mapping[str, Any],
    *,
    claim_id: str,
    requirement_id: str | None = None,
    blocked_reason: str | None = None,
) -> OfficialSnapshotAnswer | None:
    """Return a typed answer from one runtime snapshot-binding row."""

    for row in _claim_requirement_rows(binding):
        row_claim_id = _clean_text(row.get("claim_id"))
        row_requirement_id = _clean_text(row.get("requirement_id"))
        if row_claim_id != claim_id:
            continue
        if requirement_id is not None and row_requirement_id != requirement_id:
            continue
        return OfficialSnapshotAnswer(
            status="blocked" if blocked_reason else "satisfied",
            claim_id=claim_id,
            requirement_id=requirement_id or row_requirement_id,
            role=_clean_text(binding.get("role")),
            corpus_id=_clean_text(binding.get("corpus_id")),
            snapshot_id=_clean_text(binding.get("snapshot_id")),
            snapshot_ref=_clean_text(binding.get("snapshot_ref")),
            data_hash=_clean_text(binding.get("data_hash")),
            creation_time=_clean_text(binding.get("creation_time")),
            lineage_refs=tuple(_string_refs(binding.get("lineage_refs"))),
            quality_gates=tuple(_quality_gates(binding.get("quality_gates"))),
            builder_revision=_clean_text(binding.get("builder_revision")),
            transform_lineage=tuple(
                _transform_lineage(binding.get("transform_lineage"))
            ),
            supported_by=tuple(_string_refs(row.get("supported_by"))),
            lifecycle_dependency_refs=tuple(
                _string_refs(row.get("lifecycle_dependency_refs"))
            ),
            reason=blocked_reason,
        )
    return None


def _entry_from_binding(binding: Mapping[str, Any]) -> SnapshotProvenanceLedgerEntry:
    return SnapshotProvenanceLedgerEntry(
        role=_required_text(binding, "role"),
        corpus_id=_required_text(binding, "corpus_id"),
        snapshot_id=_required_text(binding, "snapshot_id"),
        snapshot_ref=_required_text(binding, "snapshot_ref"),
        release_id=_required_text(binding, "release_id"),
        release_manifest_ref=_required_text(binding, "release_manifest_ref"),
        manifest_ref=_required_text(binding, "manifest_ref"),
        data_hash=_required_text(binding, "data_hash"),
        merkle_root=_required_text(binding, "merkle_root"),
        creation_time=_required_text(binding, "creation_time"),
        lineage_refs=tuple(_string_refs(binding.get("lineage_refs"))),
        quality_gates=tuple(_quality_gates(binding.get("quality_gates"))),
        builder_revision=_required_text(binding, "builder_revision"),
        transform_lineage=tuple(_transform_lineage(binding.get("transform_lineage"))),
        claim_requirement_bindings=tuple(
            _claim_requirement_binding(row) for row in _claim_requirement_rows(binding)
        ),
        runtime_event_ref=_clean_text(binding.get("runtime_event_ref")),
        read_api_surface=_clean_text(binding.get("read_api_surface")),
        read_api_identity=_clean_text(binding.get("read_api_identity")),
    )


def _answer_from_entry(
    *,
    entry: SnapshotProvenanceLedgerEntry,
    binding: SnapshotClaimRequirementBinding,
    status: Literal["satisfied", "blocked"],
    reason: str | None,
) -> OfficialSnapshotAnswer:
    return OfficialSnapshotAnswer(
        status=status,
        claim_id=binding.claim_id,
        requirement_id=binding.requirement_id,
        role=entry.role,
        corpus_id=entry.corpus_id,
        snapshot_id=entry.snapshot_id,
        snapshot_ref=entry.snapshot_ref,
        data_hash=entry.data_hash,
        creation_time=entry.creation_time,
        lineage_refs=entry.lineage_refs,
        quality_gates=entry.quality_gates,
        builder_revision=entry.builder_revision,
        transform_lineage=entry.transform_lineage,
        supported_by=binding.supported_by,
        lifecycle_dependency_refs=binding.lifecycle_dependency_refs,
        reason=reason,
    )


def _quality_gates(value: object) -> list[SnapshotQualityGate]:
    gates: list[SnapshotQualityGate] = []
    for item in _list_value(value):
        if isinstance(item, Mapping):
            gates.append(
                SnapshotQualityGate(
                    name=_required_text(item, "name"),
                    status=_required_text(item, "status"),
                    artifact_id=_required_text(
                        item,
                        "artifact_id",
                        fallback_fields=("artifact_ref", "quality_gate_ref"),
                    ),
                )
            )
        elif isinstance(item, str):
            gates.append(
                SnapshotQualityGate(name="quality_gate", status="pass", artifact_id=item)
            )
    return gates


def _transform_lineage(value: object) -> list[TransformLineageStep]:
    steps: list[TransformLineageStep] = []
    for index, item in enumerate(_list_value(value), start=1):
        if not isinstance(item, Mapping):
            continue
        steps.append(
            TransformLineageStep(
                step_id=_clean_text(item.get("step_id")) or f"transform_step_{index}",
                operation=_required_text(item, "operation"),
                input_refs=tuple(_string_refs(item.get("input_refs"))),
                output_refs=tuple(_string_refs(item.get("output_refs"))),
                code_ref=_clean_text(item.get("code_ref")),
                config_ref=_clean_text(item.get("config_ref")),
            )
        )
    return steps


def _claim_requirement_rows(value: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = value.get("claim_requirement_bindings") or value.get("claim_requirements")
    return [item for item in _list_value(raw) if isinstance(item, Mapping)]


def _claim_requirement_binding(
    row: Mapping[str, Any],
) -> SnapshotClaimRequirementBinding:
    return SnapshotClaimRequirementBinding(
        claim_id=_required_text(row, "claim_id"),
        requirement_id=_required_text(row, "requirement_id"),
        requirement_kind=_required_text(row, "requirement_kind"),
        authority_level=_required_text(row, "authority_level"),
        time_role=_required_text(row, "time_role"),
        supported_by=tuple(_string_refs(row.get("supported_by"))),
        lifecycle_dependency_refs=tuple(
            _string_refs(row.get("lifecycle_dependency_refs"))
        ),
    )


def _required_text(
    row: Mapping[str, Any],
    field: str,
    *,
    fallback_fields: tuple[str, ...] = (),
) -> str:
    for candidate in (field, *fallback_fields):
        value = _clean_text(row.get(candidate))
        if value:
            return value
    raise ValueError(f"missing required Data Forge provenance field: {field}")


def _string_refs(value: object) -> list[str]:
    if isinstance(value, str):
        ref = _clean_text(value)
        return [ref] if ref else []
    refs: list[str] = []
    for item in _list_value(value):
        if isinstance(item, str):
            ref = _clean_text(item)
        elif isinstance(item, Mapping):
            ref = _clean_text(
                item.get("artifact_id")
                or item.get("artifact_ref")
                or item.get("ref")
                or item.get("uri")
            )
        else:
            ref = None
        if ref:
            refs.append(ref)
    return refs


def _list_value(value: object) -> list[object]:
    if not isinstance(value, list | tuple):
        return []
    return list(value)


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or any(char in text for char in "\r\n\t"):
        return None
    return text


__all__ = [
    "DATA_FORGE_PROVENANCE_MANIFEST_FILE",
    "DATA_FORGE_PROVENANCE_MANIFEST_SCHEMA_VERSION",
    "OfficialSnapshotAnswer",
    "SnapshotClaimRequirementBinding",
    "SnapshotProvenanceLedgerEntry",
    "SnapshotProvenanceManifest",
    "SnapshotQualityGate",
    "TransformLineageStep",
    "build_snapshot_provenance_manifest",
    "load_snapshot_provenance_manifest",
    "official_snapshot_answer_from_binding",
    "write_snapshot_provenance_manifest",
]
