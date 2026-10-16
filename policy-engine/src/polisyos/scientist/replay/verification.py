"""Replay verification artifacts and registry for promotion gating."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts import (
    ArtifactStore,
    CoreArtifactOwnerProfile,
    artifact_ref_for_manifest,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
    validate_owned_core_model_json_artifact,
)
from polisyos.core.artifacts.manifest import ArtifactManifest, ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.scientist.methods.autotune.models import default_search_registry_root
from polisyos.scientist.replay.deterministic import (
    CompletenessLevel,
    _measure_replayable_audit_bundle_admission,
)

if TYPE_CHECKING:
    from polisyos.scientist.policy_design.output import (
        ReplayableAuditBundle,
        _ReplayableAuditBasisAdmission,
    )

REPLAY_VERIFICATION_REPORT_SCHEMA_NAME = "polisyos.scientist.replay.ReplayVerificationReport"
REPLAY_VERIFICATION_REPORT_SCHEMA_VERSION = "1.0"

_REPLAY_VERIFICATION_REPORT_OWNER_PROFILE = CoreArtifactOwnerProfile(
    kind="scientist.replay_verification_report",
    media_type="application/json",
    schema_variants=(
        SchemaInfo(
            name=REPLAY_VERIFICATION_REPORT_SCHEMA_NAME,
            version=REPLAY_VERIFICATION_REPORT_SCHEMA_VERSION,
        ),
    ),
    payload_schema_version_by_manifest=(
        (
            (REPLAY_VERIFICATION_REPORT_SCHEMA_NAME, REPLAY_VERIFICATION_REPORT_SCHEMA_VERSION),
            REPLAY_VERIFICATION_REPORT_SCHEMA_VERSION,
        ),
    ),
)


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


@dataclass(frozen=True)
class _ReplayBundleRunContext:
    """Hold one loaded replay bundle and its shared selected-basis admission result."""

    bundle: ReplayableAuditBundle
    manifest: ArtifactManifest
    admission: _ReplayableAuditBasisAdmission


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
    store: ArtifactStore,
    *,
    run_id: str,
    replay_bundle_ref: ArtifactRef,
) -> ReplayVerificationReport:
    """Build replay verification report."""
    report, _ = _recompute_replay_context(
        store,
        run_id=run_id,
        replay_bundle_ref=replay_bundle_ref,
    )
    return report


def persist_replay_verification_report(
    store: ArtifactStore,
    payload: ReplayVerificationReport,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist replay verification report helper."""
    if payload.schema_version != REPLAY_VERIFICATION_REPORT_SCHEMA_VERSION:
        raise ValueError("replay_verification_report_schema_version_unsupported")
    measured, expected_inputs = _recompute_replay_context(
        store,
        run_id=payload.run_id,
        replay_bundle_ref=payload.replay_bundle_ref,
    )
    _require_same_recomputed_outcome(payload, measured)
    persisted_inputs = _report_inputs_for_write(expected_inputs, inputs)
    return _write_replay_verification_report(store, payload, persisted_inputs)


def _write_replay_verification_report(
    store: ArtifactStore,
    payload: ReplayVerificationReport,
    inputs: list[InputRef],
) -> ArtifactRef:
    """Persist a verifier-produced report with its exact selected replay edge."""
    return store.put_json(
        payload,
        PutOptions(
            kind="scientist.replay_verification_report",
            media_type="application/json",
            schema=SchemaInfo(
                name=REPLAY_VERIFICATION_REPORT_SCHEMA_NAME,
                version=payload.schema_version,
            ),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def load_replay_verification_report(
    store: ArtifactStore,
    ref: ArtifactRef,
    *,
    expected_run_id: str | None = None,
    expected_replay_bundle_ref: ArtifactRef | None = None,
    expected_candidate_ref: ArtifactRef | None = None,
    expected_evaluation_ref: ArtifactRef | None = None,
) -> ReplayVerificationReport:
    """Load an owner report, optionally bound to and rechecked against a live replay context.

    Without expected context, this preserves the historical candidate-reading path. Protected
    protected consumers provide run, replay, candidate, and evaluation context; that path rejects
    profileless history and recomputes the report outcome from the exact selected replay bundle.
    """
    has_context = any(
        value is not None
        for value in (
            expected_run_id,
            expected_replay_bundle_ref,
            expected_candidate_ref,
            expected_evaluation_ref,
        )
    )
    if has_context and any(
        value is None
        for value in (
            expected_run_id,
            expected_replay_bundle_ref,
            expected_candidate_ref,
            expected_evaluation_ref,
        )
    ):
        raise ValueError("replay_verification_context_incomplete")
    if (
        expected_run_id is not None
        and expected_replay_bundle_ref is not None
        and expected_candidate_ref is not None
        and expected_evaluation_ref is not None
    ):
        _require_nonblank_run_id(expected_run_id)
        _require_selected_manifest_ref(
            store,
            ref,
            kind="scientist.replay_verification_report",
            role="replay_verification_report",
        )
    report = validate_owned_core_model_json_artifact(
        ReplayVerificationReport,
        store,
        ref,
        expected_owner=_REPLAY_VERIFICATION_REPORT_OWNER_PROFILE,
    ).value
    if not has_context:
        return report
    return _load_report_for_context(
        store,
        ref,
        report,
        expected_run_id=expected_run_id,
        expected_replay_bundle_ref=expected_replay_bundle_ref,
        expected_candidate_ref=expected_candidate_ref,
        expected_evaluation_ref=expected_evaluation_ref,
    )


def _load_report_for_context(
    store: ArtifactStore,
    report_ref: ArtifactRef,
    report: ReplayVerificationReport,
    *,
    expected_run_id: str | None,
    expected_replay_bundle_ref: ArtifactRef | None,
    expected_candidate_ref: ArtifactRef | None,
    expected_evaluation_ref: ArtifactRef | None,
) -> ReplayVerificationReport:
    """Recompute a selected report against its caller's current replay basis."""
    if any(
        value is None
        for value in (
            expected_run_id,
            expected_replay_bundle_ref,
            expected_candidate_ref,
            expected_evaluation_ref,
        )
    ):
        raise ValueError("replay_verification_context_incomplete")
    assert expected_run_id is not None
    assert expected_replay_bundle_ref is not None
    assert expected_candidate_ref is not None
    assert expected_evaluation_ref is not None
    _require_nonblank_run_id(expected_run_id)
    _require_selected_manifest_ref(
        store,
        expected_replay_bundle_ref,
        kind="scientist.replayable_audit_bundle",
        role="replay_bundle",
    )
    run_context = _require_replay_bundle_run_context(
        store,
        expected_replay_bundle_ref,
        expected_run_id=expected_run_id,
    )
    _require_current_replay_subject(
        bundle=run_context.bundle,
        expected_candidate_ref=expected_candidate_ref,
        expected_evaluation_ref=expected_evaluation_ref,
        store=store,
    )
    if report.run_id != expected_run_id:
        raise ValueError("replay_verification_report_run_id_mismatch")
    if artifact_ref_identity_key(report.replay_bundle_ref) != artifact_ref_identity_key(
        expected_replay_bundle_ref
    ):
        raise ValueError("replay_verification_report_replay_bundle_ref_stale_or_mismatched")

    report_manifest = store.get_manifest(report_ref)
    measured, expected_inputs = _recompute_replay_context(
        store,
        run_id=expected_run_id,
        replay_bundle_ref=expected_replay_bundle_ref,
        expected_candidate_ref=expected_candidate_ref,
        expected_evaluation_ref=expected_evaluation_ref,
        run_context=run_context,
    )
    _require_same_recomputed_outcome(report, measured)
    _report_inputs_for_write(expected_inputs, report_manifest.inputs)
    return report


def _require_replay_bundle_run_context(
    store: ArtifactStore,
    replay_bundle_ref: ArtifactRef,
    *,
    expected_run_id: str,
) -> _ReplayBundleRunContext:
    """Require a selected replay bundle whose persisted owner body matches its run."""
    _require_nonblank_run_id(expected_run_id)
    from polisyos.scientist.policy_design.output import _admit_replayable_audit_bundle_basis

    admission = _admit_replayable_audit_bundle_basis(store, replay_bundle_ref)
    if admission.root.error_code is not None:
        raise ValueError(admission.root.error_code)
    manifest = admission.root.manifest
    bundle = admission.bundle
    if manifest is None or bundle is None:
        raise ValueError("replay_bundle_basis_not_established")
    if bundle.schema_version != "1.0":
        raise ValueError("replay_bundle_payload_schema_version_unsupported")
    if bundle.run_id != expected_run_id:
        raise ValueError("replay_bundle_run_id_mismatch")
    if admission.duplicate_input_roles:
        role = admission.duplicate_input_roles[0]
        raise ValueError(f"replay_verification_{role}_input_duplicate")
    if admission.input_mismatch_roles:
        role = admission.input_mismatch_roles[0]
        raise ValueError(f"replay_bundle_{role}_input_mismatch")
    unselected_roles = [item.role for item in admission.references if item.selected_profile_missing]
    if unselected_roles:
        role = unselected_roles[0]
        raise ValueError(f"replay_bundle_{role}_selected_profile_required")
    return _ReplayBundleRunContext(bundle=bundle, manifest=manifest, admission=admission)


def _recompute_replay_context(
    store: ArtifactStore,
    *,
    run_id: str,
    replay_bundle_ref: ArtifactRef,
    expected_candidate_ref: ArtifactRef | None = None,
    expected_evaluation_ref: ArtifactRef | None = None,
    run_context: _ReplayBundleRunContext | None = None,
) -> tuple[ReplayVerificationReport, list[InputRef]]:
    """Resolve the full selected replay context, verify it, and project report lineage."""
    if run_context is None:
        run_context = _require_replay_bundle_run_context(
            store,
            replay_bundle_ref,
            expected_run_id=run_id,
        )
    bundle = run_context.bundle
    has_expected_subject = expected_candidate_ref is not None or expected_evaluation_ref is not None
    if has_expected_subject:
        _require_current_replay_subject(
            store=store,
            bundle=bundle,
            expected_candidate_ref=expected_candidate_ref,
            expected_evaluation_ref=expected_evaluation_ref,
        )

    report_inputs = _report_context_inputs(replay_bundle_ref, run_context.manifest)
    measurement = _measure_replayable_audit_bundle_admission(
        store,
        replay_bundle_ref,
        bundle,
        run_context.admission,
    )
    report = ReplayVerificationReport(
        run_id=run_id,
        replay_bundle_ref=replay_bundle_ref,
        verification_mode=measurement.verification_mode,
        completeness_level=measurement.completeness.level.value,
        passed=measurement.passed,
        overall_similarity=measurement.overall_similarity,
        reason_codes=list(measurement.reason_codes),
        details=dict(measurement.details),
    )
    return report, report_inputs


def _require_current_replay_subject(
    *,
    store: ArtifactStore,
    bundle: ReplayableAuditBundle,
    expected_candidate_ref: ArtifactRef | None,
    expected_evaluation_ref: ArtifactRef | None,
) -> None:
    """Bind caller-current candidate/evaluation views to the resolved replay bundle body."""
    if expected_candidate_ref is None or expected_evaluation_ref is None:
        raise ValueError("replay_verification_context_incomplete")
    if bundle.candidate_ref is None or bundle.evaluation_ref is None:
        raise ValueError("replay_verification_subject_context_missing")
    for role, expected, nested in (
        ("candidate", expected_candidate_ref, bundle.candidate_ref),
        ("evaluation", expected_evaluation_ref, bundle.evaluation_ref),
    ):
        if expected.manifest_profile_sha256 is None or nested.manifest_profile_sha256 is None:
            raise ValueError(f"replay_verification_{role}_selected_profile_required")
        if artifact_ref_identity_key(expected) != artifact_ref_identity_key(nested):
            raise ValueError(f"replay_verification_{role}_context_mismatch")
        _require_selected_manifest_ref(
            store,
            expected,
            kind=expected.kind,
            role=f"replay_{role}",
        )


def _report_context_inputs(
    replay_bundle_ref: ArtifactRef,
    replay_bundle_manifest: ArtifactManifest,
) -> list[InputRef]:
    """Carry every direct replay-context edge into the selected verifier report."""
    inputs = [
        input_ref_from_artifact_ref(replay_bundle_ref, role="replay_bundle"),
        *replay_bundle_manifest.inputs,
    ]
    _input_refs_by_role(inputs)
    return inputs


def _input_refs_by_role(inputs: list[InputRef]) -> dict[str, InputRef]:
    """Index lineage edges by role and reject repeated role bindings."""
    by_role: dict[str, InputRef] = {}
    for item in inputs:
        if item.role in by_role:
            raise ValueError(f"replay_verification_{item.role}_input_duplicate")
        by_role[item.role] = item
    return by_role


def _require_selected_manifest_ref(
    store: ArtifactStore,
    ref: ArtifactRef,
    *,
    kind: str,
    role: str,
) -> ArtifactManifest:
    """Resolve a full selected view and reject profileless or substituted references."""
    if ref.kind != kind or ref.media_type != "application/json":
        raise ValueError(f"{role}_kind_or_media_type_mismatch")
    if ref.manifest_profile_sha256 is None:
        raise ValueError(f"{role}_selected_profile_required")
    manifest = store.get_manifest(ref)
    if artifact_ref_identity_key(artifact_ref_for_manifest(manifest)) != artifact_ref_identity_key(
        ref
    ):
        raise ValueError(f"{role}_selected_manifest_mismatch")
    return manifest


def _require_nonblank_run_id(run_id: str) -> None:
    """Reject blank run context while preserving exact nonblank identifiers."""
    if not run_id.strip():
        raise ValueError("replay_verification_run_id_blank")


def _require_same_recomputed_outcome(
    supplied: ReplayVerificationReport,
    measured: ReplayVerificationReport,
) -> None:
    """Reject any persisted decision fields that differ from the actual verifier output."""
    if (
        supplied.schema_version != measured.schema_version
        or supplied.run_id != measured.run_id
        or artifact_ref_identity_key(supplied.replay_bundle_ref)
        != artifact_ref_identity_key(measured.replay_bundle_ref)
        or supplied.verification_mode != measured.verification_mode
        or supplied.completeness_level != measured.completeness_level
        or supplied.passed != measured.passed
        or supplied.overall_similarity != measured.overall_similarity
        or supplied.reason_codes != measured.reason_codes
        or supplied.details != measured.details
    ):
        raise ValueError("replay_verification_report_not_recomputed")


def _report_inputs_for_write(
    expected_inputs: list[InputRef],
    supplied_inputs: list[InputRef] | None,
) -> list[InputRef]:
    """Require a report lineage projection to exactly match the resolved replay context."""
    if supplied_inputs is None:
        return list(expected_inputs)
    supplied_by_role = _input_refs_by_role(supplied_inputs)
    expected_by_role = _input_refs_by_role(expected_inputs)
    for role in sorted(set(supplied_by_role) | set(expected_by_role)):
        if supplied_by_role.get(role) != expected_by_role.get(role):
            raise ValueError(f"replay_verification_report_{role}_input_mismatch")
    return list(supplied_inputs)


def verify_and_persist_replay_bundle(
    store: ArtifactStore,
    *,
    run_id: str,
    replay_bundle_ref: ArtifactRef,
    candidate_ref: ArtifactRef | None = None,
    evaluation_ref: ArtifactRef | None = None,
    registry: ReplayRegistry | None = None,
) -> ArtifactRef:
    """Verify and persist replay bundle helper."""
    report, inputs = _recompute_replay_context(
        store,
        run_id=run_id,
        replay_bundle_ref=replay_bundle_ref,
        expected_candidate_ref=candidate_ref,
        expected_evaluation_ref=evaluation_ref,
    )
    ref = _write_replay_verification_report(store, report, inputs)
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
    "REPLAY_VERIFICATION_REPORT_SCHEMA_VERSION",
    "ReplayRegistry",
    "ReplayRegistryEntry",
    "ReplayRegistrySnapshot",
    "ReplayVerificationReport",
    "build_replay_verification_report",
    "load_replay_verification_report",
    "persist_replay_verification_report",
    "verify_and_persist_replay_bundle",
]
