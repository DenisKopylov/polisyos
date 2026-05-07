"""Replay verification artifacts and registry for promotion gating."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.runtime.replay import (
    CompletenessLevel,
    measure_replayable_audit_bundle,
)
from polisyos.scientist.methods.autotune.models import default_search_registry_root

REPLAY_VERIFICATION_REPORT_SCHEMA_NAME = "polisyos.scientist.replay.ReplayVerificationReport"


class ReplayVerificationReport(BaseModel):
    """Measured replay verdict for a replayable audit bundle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    run_id: str = Field(min_length=1)
    replay_bundle_ref: ArtifactRef
    verification_mode: str = Field(min_length=1)
    completeness_level: str = Field(min_length=1)
    passed: bool
    overall_similarity: float = Field(ge=0.0, le=1.0)
    reason_codes: list[str] = Field(default_factory=list)
    details: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_complete(self) -> bool:
        return self.completeness_level == CompletenessLevel.COMPLETE.value


class ReplayRegistryEntry(BaseModel):
    """Replay verification binding for one promoted artifact set."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    candidate_ref: ArtifactRef
    evaluation_ref: ArtifactRef
    replay_bundle_ref: ArtifactRef
    replay_verification_ref: ArtifactRef
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReplayRegistrySnapshot(BaseModel):
    """Serializable snapshot of replay verification bindings."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    entries: list[ReplayRegistryEntry] = Field(default_factory=list)


class ReplayRegistry:
    """Optional runtime registry for replay evidence bindings."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = (root or default_search_registry_root() / "replay_registry").resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        *,
        run_id: str,
        candidate_ref: ArtifactRef,
        evaluation_ref: ArtifactRef,
        replay_bundle_ref: ArtifactRef,
        replay_verification_ref: ArtifactRef,
    ) -> None:
        snapshot = self._load_snapshot()
        entry = ReplayRegistryEntry(
            run_id=run_id,
            candidate_ref=candidate_ref,
            evaluation_ref=evaluation_ref,
            replay_bundle_ref=replay_bundle_ref,
            replay_verification_ref=replay_verification_ref,
        )
        deduped = [
            item
            for item in snapshot.entries
            if not (
                item.run_id == entry.run_id
                and item.candidate_ref == entry.candidate_ref
                and item.evaluation_ref == entry.evaluation_ref
            )
        ]
        deduped.append(entry)
        snapshot = snapshot.model_copy(
            update={
                "updated_at": datetime.now(UTC),
                "entries": deduped,
            }
        )
        self._write_snapshot(snapshot)

    def latest(
        self,
        *,
        run_id: str,
        candidate_ref: ArtifactRef,
        evaluation_ref: ArtifactRef,
    ) -> ReplayRegistryEntry | None:
        snapshot = self._load_snapshot()
        matches = [
            item
            for item in snapshot.entries
            if item.run_id == run_id
            and item.candidate_ref == candidate_ref
            and item.evaluation_ref == evaluation_ref
        ]
        matches.sort(key=lambda item: item.created_at.timestamp(), reverse=True)
        return matches[0] if matches else None

    def _snapshot_path(self) -> Path:
        return self._root / "replay_registry.json"

    def _load_snapshot(self) -> ReplayRegistrySnapshot:
        path = self._snapshot_path()
        if not path.exists():
            return ReplayRegistrySnapshot()
        return ReplayRegistrySnapshot.model_validate_json(path.read_text(encoding="utf-8"))

    def _write_snapshot(self, snapshot: ReplayRegistrySnapshot) -> None:
        path = self._snapshot_path()
        payload = snapshot.model_dump_json(indent=2)
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
        ) as tmp:
            tmp.write(payload)
            temp_path = Path(tmp.name)
        temp_path.replace(path)


def build_replay_verification_report(
    store: FileSystemCAS,
    *,
    run_id: str,
    replay_bundle_ref: ArtifactRef,
) -> ReplayVerificationReport:
    """Build replay verification report."""
    measurement = measure_replayable_audit_bundle(store, replay_bundle_ref)
    return ReplayVerificationReport(
        run_id=run_id,
        replay_bundle_ref=replay_bundle_ref,
        verification_mode=measurement.verification_mode,
        completeness_level=measurement.completeness.level.value,
        passed=measurement.passed,
        overall_similarity=measurement.overall_similarity,
        reason_codes=list(measurement.reason_codes),
        details=dict(measurement.details),
    )


def persist_replay_verification_report(
    store: FileSystemCAS,
    payload: ReplayVerificationReport,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist replay verification report helper."""
    return store.put_json(
        payload,
        PutOptions(
            kind="scientist.replay_verification_report",
            media_type="application/json",
            schema=SchemaInfo(
                name=REPLAY_VERIFICATION_REPORT_SCHEMA_NAME,
                version=payload.schema_version,
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_replay_verification_report(
    store: FileSystemCAS,
    ref: ArtifactRef,
) -> ReplayVerificationReport:
    """Load replay verification report."""
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return ReplayVerificationReport.model_validate(payload)


def verify_and_persist_replay_bundle(
    store: FileSystemCAS,
    *,
    run_id: str,
    replay_bundle_ref: ArtifactRef,
    candidate_ref: ArtifactRef | None = None,
    evaluation_ref: ArtifactRef | None = None,
    registry: ReplayRegistry | None = None,
) -> ArtifactRef:
    """Verify and persist replay bundle helper."""
    report = build_replay_verification_report(
        store,
        run_id=run_id,
        replay_bundle_ref=replay_bundle_ref,
    )
    inputs = [InputRef(artifact_id=replay_bundle_ref.artifact_id, role="replay_bundle")]
    if candidate_ref is not None:
        inputs.append(InputRef(artifact_id=candidate_ref.artifact_id, role="candidate"))
    if evaluation_ref is not None:
        inputs.append(InputRef(artifact_id=evaluation_ref.artifact_id, role="evaluation"))
    ref = persist_replay_verification_report(store, report, inputs=inputs)
    if registry is not None and candidate_ref is not None and evaluation_ref is not None:
        registry.record(
            run_id=run_id,
            candidate_ref=candidate_ref,
            evaluation_ref=evaluation_ref,
            replay_bundle_ref=replay_bundle_ref,
            replay_verification_ref=ref,
        )
    return ref


__all__ = [
    "REPLAY_VERIFICATION_REPORT_SCHEMA_NAME",
    "ReplayRegistry",
    "ReplayRegistryEntry",
    "ReplayRegistrySnapshot",
    "ReplayVerificationReport",
    "build_replay_verification_report",
    "load_replay_verification_report",
    "persist_replay_verification_report",
    "verify_and_persist_replay_bundle",
]
