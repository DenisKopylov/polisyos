"""Unit profile recovery over real CAS inventory, events and pointer files.

The historical verifier is an explicit unit adapter. It reads actual selected
CAS bytes and manifest scope, then returns an opaque model_construct fixture
of the requested exact record type. Those fixtures are not valid lifecycle
receipts or authority evidence. Full history, live action/lease, N4 and N5
verification remain outside this inventory-and-pointer unit boundary.
"""

from __future__ import annotations

import errno
from contextlib import closing
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from polisyos.core import artifacts
from polisyos.runtime.http.services.control.artifacts import write_runtime_authority_artifact
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.acquisition_world_growth import (
    AcquisitionWorldGrowthBridge,
    CandidateAcquisitionWorldCheckpoint,
    CandidateAcquisitionWorldIntent,
)
from polisyos.runtime.quality.authority_reconciliation import AuthorityReconciliationError
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.runtime.quality.generation_cycle import CandidateSourceReentryReceipt
from tests.unit.runtime.quality.test_authority_reconciliation import _runtime_context

_PRODUCER = artifacts.ProducerInfo(
    component="polisyos.runtime.acquisition_world_growth", version="1.0"
)


@dataclass(frozen=True)
class _OwnerSpec:
    name: str
    kind: str
    schema: str
    version: str
    record_type: type[BaseModel]


_SPECS = (
    _OwnerSpec(
        "intent",
        "runtime_quality.acquisition_candidate_world_intent",
        "polisyos.runtime.CandidateAcquisitionWorldIntent",
        "1.2",
        CandidateAcquisitionWorldIntent,
    ),
    _OwnerSpec(
        "checkpoint",
        "runtime_quality.acquisition_candidate_world_checkpoint",
        "polisyos.runtime.CandidateAcquisitionWorldCheckpoint",
        "1.1",
        CandidateAcquisitionWorldCheckpoint,
    ),
    _OwnerSpec(
        "reentry",
        "runtime_quality.candidate_source_reentry_receipt",
        "polisyos.runtime.CandidateSourceReentryReceipt",
        "1.0",
        CandidateSourceReentryReceipt,
    ),
)


@pytest.fixture(params=_SPECS, ids=lambda spec: spec.name)
def recovery_case(request: pytest.FixtureRequest, tmp_path: Path) -> Any:
    """Emit real authority-profile/event metadata around a clearly unit-owned body."""
    spec = request.param
    with closing(
        ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "events.sqlite3")
    ) as control:
        store = artifacts.FileSystemCAS(tmp_path / "cas")
        events = RuntimeDiagnosticEventLog(store=control, artifact_store=store)
        action_ref = store.put_json(
            {"unit_candidate_action_parent": True, "publication_authority": False},
            artifacts.ArtifactWriteOptions(
                kind="runtime_quality.acquisition_candidate_action_receipt",
                media_type="application/json",
            ),
            return_selected_profile=True,
        )
        payload = {
            "unit_profile_fixture": spec.name,
            "authority_purpose": "unit_inventory_recovery_only",
            "publication_authority": False,
        }
        context = _runtime_context(str(action_ref.artifact_id))
        context.update(
            evidence_id="unit-profile-recovery-" + spec.name,
            reader_contract=spec.kind + ".unit_fixture_reader",
            phase="unit_profile_recovery",
            event_id="evt_unit_profile_recovery_" + spec.name,
        )
        result = write_runtime_authority_artifact(
            store,
            events,
            payload,
            artifacts.ArtifactWriteOptions(
                kind=spec.kind,
                media_type="application/json",
                schema=artifacts.SchemaInfo(name=spec.schema, version=spec.version),
                producer=_PRODUCER,
                governance=artifacts.ArtifactGovernanceInfo(classification="internal"),
                inputs=[artifacts.input_ref_from_artifact_ref(action_ref, role="unit_parent")],
            ),
            **context,
        )
        manifest = store.get_manifest(result.cas_ref)
        assert manifest.authority is not None
        assert result.cas_ref.manifest_profile_sha256 is not None
        rows = events.list_events(event_id=context["event_id"], limit=2)
        assert len(rows) == 1
        assert tuple(rows[0].event.artifact_refs) == (str(result.cas_ref.artifact_id),)
        bridge = AcquisitionWorldGrowthBridge.__new__(AcquisitionWorldGrowthBridge)
        bridge.artifact_store = store
        yield SimpleNamespace(
            spec=spec,
            store=store,
            bridge=bridge,
            ref=result.cas_ref,
            body=store.get_bytes(result.cas_ref),
            manifest=manifest,
            event_artifact_ref=rows[0].event.artifact_refs[0],
            action_ref=action_ref,
            pointer=tmp_path / "selected-owner-view.json",
            opaque=spec.record_type.model_construct(),
            seen=[],
        )


def _verify_unit_view(case: SimpleNamespace, ref: artifacts.ArtifactRef) -> BaseModel:
    """Read real selected content/scope before returning the opaque typed fixture."""
    case.seen.append(ref)
    assert ref.manifest_profile_sha256 is not None
    manifest = case.store.get_manifest(ref)
    assert case.store.verify(ref).ok
    if ref.artifact_id != case.ref.artifact_id or case.store.get_bytes(ref) != case.body:
        raise ValueError("unit_selected_payload_mismatch")
    if manifest.same_input_closure != case.manifest.same_input_closure:
        raise ValueError("unit_selected_owner_scope_mismatch")
    return case.opaque


def _recover(case: SimpleNamespace, *, artifact_ref: str | None = None, verify: Any = None) -> Any:
    return case.bridge._recover_unique_candidate_owner_view(
        artifact_ref=artifact_ref or case.event_artifact_ref,
        kind=case.spec.kind,
        schema=case.spec.schema,
        version=case.spec.version,
        record_type=case.spec.record_type,
        verify=verify or (lambda ref: _verify_unit_view(case, ref)),
    )


def _alternate(case: SimpleNamespace, **updates: Any) -> artifacts.ArtifactRef:
    """Add a real same-blob manifest view; copied metadata is adversarial, not proof."""
    manifest = case.manifest
    options = artifacts.ArtifactWriteOptions(
        kind=manifest.kind,
        media_type=manifest.media_type,
        schema=manifest.artifact_schema,
        producer=manifest.producer,
        env=manifest.env,
        inputs=list(manifest.inputs),
        canon=manifest.canon,
        governance=manifest.governance,
        tenant_context=manifest.tenant_context,
        same_input_closure=manifest.same_input_closure,
        authority=manifest.authority,
        warnings=list(manifest.warnings),
    )
    ref = case.store.put_bytes(case.body, replace(options, **updates), return_selected_profile=True)
    assert ref.artifact_id == case.ref.artifact_id
    assert ref.manifest_profile_sha256 != case.ref.manifest_profile_sha256
    return ref


def _eligible_views(case: SimpleNamespace) -> tuple[artifacts.ArtifactRef, ...]:
    inventory = case.store.inventory_snapshot(artifact_id=case.ref.artifact_id)
    assert inventory.verdict == "pass", inventory
    by_profile = {}
    for entry in inventory.entries:
        manifest = entry.manifest
        if (
            manifest.kind == case.spec.kind
            and manifest.media_type == "application/json"
            and manifest.artifact_schema == case.manifest.artifact_schema
            and manifest.producer == _PRODUCER
            and manifest.authority is not None
        ):
            ref = artifacts.artifact_ref_for_manifest(manifest)
            by_profile[ref.manifest_profile_sha256] = ref
    return tuple(by_profile.values())


def test_unique_selected_profile_recovers_from_exact_event_id_without_a_pointer(
    recovery_case: SimpleNamespace,
) -> None:
    """Recovery performs no pointer write and ignores ineligible same-blob views."""
    case = recovery_case
    for updates in (
        {"kind": "unit.foreign-kind"},
        {"schema": artifacts.SchemaInfo(name=case.spec.schema, version="foreign")},
        {"producer": artifacts.ProducerInfo(component="unit.foreign-producer", version="1.0")},
        {"producer": artifacts.ProducerInfo(component=_PRODUCER.component, version="foreign")},
        {"authority": None},
    ):
        _alternate(case, **updates)
    before = case.store.inventory_snapshot(artifact_id=case.ref.artifact_id)
    assert before.verdict == "pass"
    assert not case.pointer.exists()
    selected, opaque = _recover(case)
    assert selected == case.ref and opaque is case.opaque
    assert {ref.manifest_profile_sha256 for ref in case.seen} == {case.ref.manifest_profile_sha256}
    assert all(str(ref.artifact_id) == case.event_artifact_ref for ref in case.seen)
    assert not case.pointer.exists()
    assert case.store.inventory_snapshot(artifact_id=case.ref.artifact_id) == before
    # The real caller-owned pointer primitive retains this exact selected view.
    case.bridge._write_candidate_world_pointer(
        case.pointer, candidate_action_ref=case.action_ref, selected_ref=selected
    )
    assert (
        case.bridge._read_candidate_world_pointer(
            case.pointer, candidate_action_ref=case.action_ref, expected_kind=case.spec.kind
        )
        == selected
    )
    assert case.store.inventory_snapshot(artifact_id=case.ref.artifact_id) == before


def test_eligible_foreign_profile_is_not_silently_removed_from_the_denominator(
    recovery_case: SimpleNamespace,
) -> None:
    """A competing owner-scope failure cannot leave the original looking unique."""
    case = recovery_case
    assert _recover(case)[0] == case.ref
    foreign_scope = case.manifest.same_input_closure.model_copy(
        update={"job_id": "unit-foreign-job"}
    )
    _alternate(case, same_input_closure=foreign_scope)
    assert len(_eligible_views(case)) == 2
    with pytest.raises(ValueError, match="unit_selected_owner_scope_mismatch"):
        _recover(case)
    assert not case.pointer.exists()


@pytest.mark.parametrize("missing", ["wrong_event_id", "absent_blob_id", "missing_blob_bytes"])
def test_missing_event_selected_content_never_falls_back_to_another_view(
    recovery_case: SimpleNamespace, missing: str
) -> None:
    """The exact event blob ID remains load-bearing even when a valid view exists."""
    case = recovery_case
    assert _recover(case)[0] == case.ref
    case.seen.clear()
    event_ref = case.event_artifact_ref
    expected = "candidate_source_reentry_profile_not_unique"
    if missing == "wrong_event_id":
        event_ref = str(case.action_ref.artifact_id)
    elif missing == "absent_blob_id":
        event_ref = "sha256:" + "0" * 64
    else:
        blob, _manifest = case.store._paths(case.ref.artifact_id)
        blob.unlink()
        expected = "candidate_source_reentry_profile_inventory_unverified"
    with pytest.raises(ValueError, match=expected):
        _recover(case, artifact_ref=event_ref)
    assert case.seen == []
    assert not case.pointer.exists()


def test_two_accepted_eligible_profiles_refuse_recovery(recovery_case: SimpleNamespace) -> None:
    """Neither default selection nor iteration order resolves a real profile ambiguity."""
    case = recovery_case
    assert _recover(case)[0] == case.ref
    _alternate(case, warnings=[artifacts.WarningRecord(code="unit.alternate", msg="unit profile")])
    profiles = _eligible_views(case)
    assert len(profiles) == 2
    assert all(type(_verify_unit_view(case, ref)) is case.spec.record_type for ref in profiles)
    with pytest.raises(ValueError, match="candidate_source_reentry_profile_not_unique"):
        _recover(case)
    assert not case.pointer.exists()


@pytest.mark.parametrize("denial", ["reconciliation", "permission", "wrapped_permission", "io"])
def test_one_denied_eligible_view_cannot_make_the_other_view_unique(
    recovery_case: SimpleNamespace, denial: str
) -> None:
    """Preserve operational refusal instead of treating an unread view as invalid."""
    case = recovery_case
    _alternate(case, warnings=[artifacts.WarningRecord(code="unit.other", msg="unit profile")])
    profiles = _eligible_views(case)
    assert len(profiles) == 2
    assert all(type(_verify_unit_view(case, ref)) is case.spec.record_type for ref in profiles)
    denied_profile = profiles[0].manifest_profile_sha256
    if denial == "reconciliation":
        failure = AuthorityReconciliationError(
            "authority_payload_mismatch",
            "unit callback denied selected payload read",
            details={"error_kind": "permission_denied"},
        )
    elif denial in {"permission", "wrapped_permission"}:
        failure = PermissionError(errno.EACCES, "unit callback denied selected payload read")
    else:
        failure = OSError(errno.EIO, "unit callback selected payload I/O failure")

    def verify_with_one_denied(ref: artifacts.ArtifactRef) -> BaseModel:
        if ref.manifest_profile_sha256 == denied_profile:
            if denial == "wrapped_permission":
                raise ValueError("unit wrapped read refusal") from failure
            raise failure
        return _verify_unit_view(case, ref)

    with pytest.raises(type(failure)) as refused:
        _recover(case, verify=verify_with_one_denied)
    assert refused.value is failure
    assert not case.pointer.exists()


def test_callback_must_return_the_exact_record_type(recovery_case: SimpleNamespace) -> None:
    """A success-shaped mapping or sibling opaque model cannot select a profile."""
    case = recovery_case
    assert _recover(case)[0] == case.ref
    sibling = next(
        spec.record_type for spec in _SPECS if spec.record_type is not case.spec.record_type
    )
    for returned in ({"selected": True}, sibling.model_construct()):
        with pytest.raises(ValueError, match="candidate_source_reentry_profile_result_untyped"):
            _recover(case, verify=lambda _ref, value=returned: value)
    assert not case.pointer.exists()


def test_backend_without_inventory_cannot_recover_from_a_default(
    recovery_case: SimpleNamespace,
) -> None:
    """A real store behind a reduced capability surface gets no default-read fallback."""
    case = recovery_case
    assert _recover(case)[0] == case.ref
    case.bridge.artifact_store = SimpleNamespace(get_manifest=case.store.get_manifest)
    with pytest.raises(ValueError, match="candidate_source_reentry_profile_inventory_unavailable"):
        _recover(case)
    assert not case.pointer.exists()
