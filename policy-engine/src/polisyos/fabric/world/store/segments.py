"""Write and index world fact segments that bridge emission and materialization."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.fabric.evidence.fact_writer import write_fact_segment
from polisyos.fabric.io.atomic import append_text_locked, atomic_write_text, file_lock
from polisyos.fabric._adapters.observability import FABRIC_TRACE_NAMES
from polisyos.fabric.data_plane.temporal import parse_datetime_utc
from polisyos.fabric.world.providers import resolve_world_observability
from polisyos.ir.loading.fact_log import Fact, FactProvenance, FactSegmentManifest
from polisyos.ir.kernel.base import ID_PATTERN

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.core.observability import MetricsRegistry, PolicyOSTracer

from .errors import WorldSegmentError

logger = get_logger(__name__)

SEGMENTS_INDEX_NAME = "_segments.jsonl"
SEGMENTS_INDEX_LOCK_NAME = "_segments.lock"

_ID_RE = re.compile(ID_PATTERN)
_WORLD_MUTATION_NOTE_PREFIX = "world_mutation.v1:"


class WorldMutationKind(str, Enum):
    """Append-only mutation semantics for world fact emission."""

    ASSERTION = "assertion"
    CORRECTION = "correction"
    REVOCATION = "revocation"
    BRANCH_ASSERTION = "branch_assertion"
    SCENARIO_ASSERTION = "scenario_assertion"


class WorldObservedState(str, Enum):
    """Whether a branch/fact represents observed or simulated state."""

    OBSERVED = "observed"
    SIMULATED = "simulated"


@dataclass(frozen=True)
class WorldSegmentGCReport:
    """Outcome of world segment retention and garbage collection."""

    retained_segment_ids: tuple[str, ...]
    deleted_segment_ids: tuple[str, ...]
    dry_run: bool = False


@dataclass(frozen=True)
class WorldFactMutationMetadata:
    """Machine-readable mutation envelope embedded into fact provenance notes."""

    mutation_kind: WorldMutationKind = WorldMutationKind.ASSERTION
    corrects_fact_ref: str | None = None
    revokes_fact_ref: str | None = None
    reason: str | None = None
    source_evidence_refs: tuple[str, ...] = ()
    lineage_ref: str | None = None
    actor: str | None = None
    branch_name: str | None = None
    scenario_ref: str | None = None
    observed_state: WorldObservedState = WorldObservedState.OBSERVED

    def __post_init__(self) -> None:
        kind = _coerce_mutation_kind(self.mutation_kind)
        state = _coerce_observed_state(self.observed_state)
        object.__setattr__(self, "mutation_kind", kind)
        object.__setattr__(self, "observed_state", state)
        object.__setattr__(
            self,
            "source_evidence_refs",
            tuple(str(ref).strip() for ref in self.source_evidence_refs if str(ref).strip()),
        )
        _validate_world_mutation_metadata(self)

    def to_payload(self) -> dict[str, Any]:
        """Serialize to a stable note payload."""

        payload: dict[str, Any] = {
            "mutation_kind": self.mutation_kind.value,
            "observed_state": self.observed_state.value,
        }
        for key, value in (
            ("corrects_fact_ref", self.corrects_fact_ref),
            ("revokes_fact_ref", self.revokes_fact_ref),
            ("reason", self.reason),
            ("lineage_ref", self.lineage_ref),
            ("actor", self.actor),
            ("branch_name", self.branch_name),
            ("scenario_ref", self.scenario_ref),
        ):
            if value:
                payload[key] = value
        if self.source_evidence_refs:
            payload["source_evidence_refs"] = list(self.source_evidence_refs)
        return payload

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> WorldFactMutationMetadata:
        """Load one mutation envelope from a provenance note payload."""

        return cls(
            mutation_kind=_coerce_mutation_kind(str(payload.get("mutation_kind", "assertion"))),
            corrects_fact_ref=_optional_text(payload.get("corrects_fact_ref")),
            revokes_fact_ref=_optional_text(payload.get("revokes_fact_ref")),
            reason=_optional_text(payload.get("reason")),
            source_evidence_refs=tuple(
                str(ref).strip()
                for ref in payload.get("source_evidence_refs", ())
                if str(ref).strip()
            ),
            lineage_ref=_optional_text(payload.get("lineage_ref")),
            actor=_optional_text(payload.get("actor")),
            branch_name=_optional_text(payload.get("branch_name")),
            scenario_ref=_optional_text(payload.get("scenario_ref")),
            observed_state=_coerce_observed_state(str(payload.get("observed_state", "observed"))),
        )


def build_world_mutation_metadata(
    *,
    mutation_kind: WorldMutationKind | str = WorldMutationKind.ASSERTION,
    corrects_fact_ref: str | None = None,
    revokes_fact_ref: str | None = None,
    reason: str | None = None,
    source_evidence_refs: Iterable[str] = (),
    lineage_ref: str | None = None,
    actor: str | None = None,
    branch_name: str | None = None,
    scenario_ref: str | None = None,
    observed_state: WorldObservedState | str = WorldObservedState.OBSERVED,
) -> WorldFactMutationMetadata:
    """Validate and build append-only mutation metadata for a world fact."""

    return WorldFactMutationMetadata(
        mutation_kind=_coerce_mutation_kind(mutation_kind),
        corrects_fact_ref=_optional_text(corrects_fact_ref),
        revokes_fact_ref=_optional_text(revokes_fact_ref),
        reason=_optional_text(reason),
        source_evidence_refs=tuple(source_evidence_refs),
        lineage_ref=_optional_text(lineage_ref),
        actor=_optional_text(actor),
        branch_name=_optional_text(branch_name),
        scenario_ref=_optional_text(scenario_ref),
        observed_state=_coerce_observed_state(observed_state),
    )


def provenance_with_world_mutation(
    provenance: FactProvenance,
    mutation: WorldFactMutationMetadata,
) -> FactProvenance:
    """Return provenance carrying one stable, parseable world mutation note."""

    note = _world_mutation_note(mutation)
    if note in provenance.notes:
        return provenance
    return provenance.model_copy(update={"notes": [*provenance.notes, note]})


def parse_world_mutation_notes(
    provenance: FactProvenance,
) -> tuple[WorldFactMutationMetadata, ...]:
    """Extract mutation envelopes from fact provenance notes."""

    mutations: list[WorldFactMutationMetadata] = []
    for note in provenance.notes:
        if not note.startswith(_WORLD_MUTATION_NOTE_PREFIX):
            continue
        raw = note.removeprefix(_WORLD_MUTATION_NOTE_PREFIX)
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise WorldSegmentError("world mutation provenance note must be a JSON object")
        mutations.append(WorldFactMutationMetadata.from_payload(payload))
    return tuple(mutations)


def annotate_world_fact_mutation(
    fact: Fact,
    mutation: WorldFactMutationMetadata,
) -> Fact:
    """Attach mutation metadata to an already-built fact without altering its value fields."""

    provenance = provenance_with_world_mutation(fact.provenance, mutation)
    return fact.model_copy(update={"provenance": provenance})


def _world_mutation_note(mutation: WorldFactMutationMetadata) -> str:
    payload = json.dumps(mutation.to_payload(), sort_keys=True, separators=(",", ":"))
    return f"{_WORLD_MUTATION_NOTE_PREFIX}{payload}"


def _coerce_mutation_kind(value: WorldMutationKind | str) -> WorldMutationKind:
    if isinstance(value, WorldMutationKind):
        return value
    try:
        return WorldMutationKind(str(value).strip())
    except ValueError as exc:
        known = ", ".join(kind.value for kind in WorldMutationKind)
        raise WorldSegmentError(f"unsupported world mutation kind {value!r}; expected {known}") from exc


def _coerce_observed_state(value: WorldObservedState | str) -> WorldObservedState:
    if isinstance(value, WorldObservedState):
        return value
    try:
        return WorldObservedState(str(value).strip())
    except ValueError as exc:
        known = ", ".join(state.value for state in WorldObservedState)
        raise WorldSegmentError(f"unsupported world observed state {value!r}; expected {known}") from exc


def _validate_world_mutation_metadata(mutation: WorldFactMutationMetadata) -> None:
    kind = mutation.mutation_kind
    if kind == WorldMutationKind.CORRECTION:
        _require_mutation_fields(
            mutation,
            "correction",
            ("corrects_fact_ref", "reason", "source_evidence_refs", "lineage_ref", "actor"),
        )
    elif kind == WorldMutationKind.REVOCATION:
        _require_mutation_fields(
            mutation,
            "revocation",
            ("revokes_fact_ref", "reason", "source_evidence_refs", "actor"),
        )
    elif kind == WorldMutationKind.BRANCH_ASSERTION and not mutation.branch_name:
        raise WorldSegmentError("branch_assertion world mutations require branch_name")
    elif kind == WorldMutationKind.SCENARIO_ASSERTION:
        _require_mutation_fields(
            mutation,
            "scenario_assertion",
            ("branch_name", "scenario_ref", "reason", "lineage_ref", "actor"),
        )
        if mutation.observed_state != WorldObservedState.SIMULATED:
            raise WorldSegmentError("scenario_assertion world mutations must be simulated")


def _require_mutation_fields(
    mutation: WorldFactMutationMetadata,
    label: str,
    fields: tuple[str, ...],
) -> None:
    missing: list[str] = []
    for field_name in fields:
        value = getattr(mutation, field_name)
        if value is None or value == () or value == "":
            missing.append(field_name)
    if missing:
        raise WorldSegmentError(f"{label} world mutations require: {', '.join(missing)}")


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _segment_manifest_sidecar_path(manifest: FactSegmentManifest) -> Path:
    segment_path = Path(manifest.path)
    return segment_path.with_name(f"{segment_path.stem}_manifest.json")


def _write_world_fact_index(
    fact_log_root: Path,
    manifests: Iterable[FactSegmentManifest],
) -> list[FactSegmentManifest]:
    manifest_list = list(manifests)
    index_path = fact_log_root / "world" / SEGMENTS_INDEX_NAME
    lock_path = fact_log_root / "world" / SEGMENTS_INDEX_LOCK_NAME
    payload = "".join(manifest.model_dump_json() + "\n" for manifest in manifest_list)
    with file_lock(lock_path):
        atomic_write_text(index_path, payload)
    return manifest_list


def _normalize_segment_name(segment_name: str) -> str:
    value = segment_name.strip().lower()
    value = re.sub(r"[^a-z0-9_.-]+", "_", value)
    value = value.strip("_-. ")
    if not value:
        value = "segment"
    if not re.match(r"^[a-z]", value):
        value = f"seg_{value}"
    if _ID_RE.fullmatch(value) is None:
        value = re.sub(r"[^a-z0-9_.-]+", "_", value)
        if not value or _ID_RE.fullmatch(value) is None:
            value = "segment"
    return value


def _dedup_facts(facts: Iterable[Fact]) -> list[Fact]:
    seen: set[str] = set()
    deduped: list[Fact] = []
    for fact in facts:
        if fact.fact_id in seen:
            continue
        seen.add(fact.fact_id)
        deduped.append(fact)
    return deduped


def write_world_fact_segment(
    facts: list[Fact],
    *,
    fact_log_root: Path,
    segment_name: str,
) -> FactSegmentManifest:
    """Write one deduplicated world fact segment under the fact-log `world/` lane."""
    try:
        segment_dir = fact_log_root / "world"
        normalized = _normalize_segment_name(segment_name)
        deduped = _dedup_facts(facts)
        return write_fact_segment(
            deduped,
            segment_dir=segment_dir,
            segment_name=normalized,
        )
    except Exception as exc:  # pragma: no cover - defensive
        raise WorldSegmentError(f"failed to write world fact segment: {exc}") from exc


def append_world_segment_index(
    manifest: FactSegmentManifest,
    *,
    fact_log_root: Path,
    tracer: PolicyOSTracer | None = None,
    metrics: MetricsRegistry | None = None,
) -> None:
    """Append a segment manifest to the world fact-log index consumed by materializers."""
    resolved = resolve_world_observability(tracer=tracer, metrics=metrics)
    try:
        with resolved.tracer.start_as_current_span(
            FABRIC_TRACE_NAMES["segment_append"],
            attributes={
                "world.segment_id": manifest.segment_id,
                "world.row_count": manifest.row_count,
            },
        ):
            index_path = fact_log_root / "world" / SEGMENTS_INDEX_NAME
            lock_path = fact_log_root / "world" / SEGMENTS_INDEX_LOCK_NAME
            append_text_locked(
                index_path,
                manifest.model_dump_json() + "\n",
                lock_path=lock_path,
            )
            if getattr(resolved.metrics, "set_fabric_segment_count", None):
                try:
                    manifests = load_world_fact_manifests(fact_log_root)
                except Exception:
                    manifests = []
                tenant_id = ""
                if isinstance(manifest.stats, dict):
                    tenant_id = str(manifest.stats.get("tenant_id", "") or "").strip()
                if tenant_id:
                    count = sum(
                        1
                        for item in manifests
                        if isinstance(item.stats, dict)
                        and str(item.stats.get("tenant_id", "") or "").strip() == tenant_id
                    )
                    resolved.metrics.set_fabric_segment_count(float(count), tenant_id=tenant_id)
                else:
                    resolved.metrics.set_fabric_segment_count(float(len(manifests)))
    except Exception as exc:  # pragma: no cover - defensive
        raise WorldSegmentError(f"failed to append world segment index: {exc}") from exc


def load_world_fact_manifests(fact_log_root: Path) -> list[FactSegmentManifest]:
    """Load world fact manifests."""
    index_path = fact_log_root / "world" / SEGMENTS_INDEX_NAME
    if not index_path.exists():
        return []
    manifests: list[FactSegmentManifest] = []
    lock_path = fact_log_root / "world" / SEGMENTS_INDEX_LOCK_NAME
    with file_lock(lock_path), index_path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                manifests.append(FactSegmentManifest.model_validate_json(raw))
            except Exception as exc:
                logger.error(
                    "Invalid world fact manifest index entry",
                    index_path=str(index_path),
                    line_number=line_number,
                    error=str(exc),
                )
                raise WorldSegmentError(
                    f"invalid world segment index entry at {index_path}:{line_number}: {exc}"
                ) from exc
    return manifests


def vacuum_world_segment_index(fact_log_root: Path) -> list[FactSegmentManifest]:
    """Rewrite the segment index so it only references unique, existing segments."""

    manifests = load_world_fact_manifests(fact_log_root)
    deduped: dict[str, FactSegmentManifest] = {}
    for manifest in manifests:
        if not Path(manifest.path).exists():
            logger.warning(
                "Dropping missing world segment from index during vacuum",
                segment_id=manifest.segment_id,
                path=manifest.path,
            )
            continue
        deduped[manifest.segment_id] = manifest
    return _write_world_fact_index(fact_log_root, deduped.values())


def gc_world_segments(
    fact_log_root: Path,
    *,
    applied_segment_ids: Iterable[str] = (),
    retain_latest: int = 0,
    retain_since: str | None = None,
    retain_segment_ids: Iterable[str] = (),
    dry_run: bool = False,
) -> WorldSegmentGCReport:
    """Delete expired applied segments while preserving retained or unapplied ones."""

    manifests = load_world_fact_manifests(fact_log_root)
    applied_ids = {str(segment_id) for segment_id in applied_segment_ids}
    explicit_retain = {str(segment_id) for segment_id in retain_segment_ids}
    keep_since_dt = (
        parse_datetime_utc(retain_since, what="retain_since") if retain_since is not None else None
    )

    retained: list[FactSegmentManifest] = []
    deleted_ids: list[str] = []
    latest_ids = {manifest.segment_id for manifest in manifests[-max(retain_latest, 0) :]}

    for manifest in manifests:
        keep = False
        if manifest.segment_id not in applied_ids:
            keep = True
        if manifest.segment_id in explicit_retain or manifest.segment_id in latest_ids:
            keep = True
        if keep_since_dt is not None:
            if manifest.time_end is None:
                keep = True
            else:
                try:
                    keep = (
                        parse_datetime_utc(manifest.time_end, what="world segment time_end")
                        >= keep_since_dt
                    ) or keep
                except Exception:
                    keep = True

        if keep:
            retained.append(manifest)
            continue

        deleted_ids.append(manifest.segment_id)
        if dry_run:
            continue
        for path in (Path(manifest.path), _segment_manifest_sidecar_path(manifest)):
            try:
                if path.exists():
                    path.unlink()
            except OSError as exc:
                logger.warning(
                    "Failed to delete world segment artifact during GC",
                    segment_id=manifest.segment_id,
                    path=str(path),
                    error=str(exc),
                )
                retained.append(manifest)
                deleted_ids.pop()
                break

    if not dry_run:
        retained = _write_world_fact_index(fact_log_root, retained)

    return WorldSegmentGCReport(
        retained_segment_ids=tuple(manifest.segment_id for manifest in retained),
        deleted_segment_ids=tuple(deleted_ids),
        dry_run=dry_run,
    )


def persist_fact_segment_manifest(
    manifest: FactSegmentManifest,
    store: ArtifactStore,
) -> ArtifactRef:
    """Persist a segment manifest artifact so downstream stages can reference the batch."""
    ref = store.put_json(
        manifest.model_dump(),
        opts=ArtifactWriteOptions(
            kind="ir.fact_segment_manifest",
            media_type="application/json",
            schema=SchemaInfo(name="ir.fact_segment_manifest", version="1.0"),
        ),
    )
    return ArtifactRef.model_validate(ref.model_dump())


__all__ = [
    "SEGMENTS_INDEX_LOCK_NAME",
    "SEGMENTS_INDEX_NAME",
    "WorldFactMutationMetadata",
    "WorldMutationKind",
    "WorldObservedState",
    "WorldSegmentGCReport",
    "annotate_world_fact_mutation",
    "append_world_segment_index",
    "build_world_mutation_metadata",
    "gc_world_segments",
    "load_world_fact_manifests",
    "parse_world_mutation_notes",
    "persist_fact_segment_manifest",
    "provenance_with_world_mutation",
    "vacuum_world_segment_index",
    "write_world_fact_segment",
]
