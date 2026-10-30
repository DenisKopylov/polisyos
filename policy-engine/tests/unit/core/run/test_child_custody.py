"""Behavioral release controls through actual Core runs and generic CAS readers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from pydantic import BaseModel, ConfigDict

from polisyos.core.artifacts.child_release import (
    _CHILD_STAGING_TOKEN,
    ChildReleaseRecord,
    ChildReleaseUnavailableError,
    _ChildReleaseHead,
    _ChildReleaseLedger,
    _read_head,
    _verify_job_authorization,
    child_binding_digest,
    child_store_identity,
)
from polisyos.core.artifacts.manifest import ArtifactChildReleaseInfo, ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.child_custody import (
    ChildComputationBinding,
    ChildComputationCustody,
)
from polisyos.core.run.context import RunContext

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.core.artifacts.protocol import ArtifactReader


class _Projection(BaseModel):
    """A test-owned typed payload whose edge is intentionally not manifest-only."""

    model_config = ConfigDict(extra="forbid")
    selected: ArtifactRef


class _TypedResolver:
    def resolve(
        self, store: ArtifactReader, projection_ref: ArtifactRef
    ) -> tuple[ArtifactRef, ...]:
        manifest = store.get_manifest(projection_ref)
        if manifest.kind == "tests.child.value":
            return ()
        if manifest.kind != "tests.child.projection":
            raise ValueError("unsupported_test_schema")
        selected = _Projection.model_validate_json(store.get_bytes(projection_ref)).selected
        store.get_bytes(selected)
        return (selected,)


def _root(tmp_path: Path) -> tuple[RunContext, ChildComputationBinding]:
    store = FileSystemCAS(tmp_path / "served", ownership_enforced=False)
    registry = build_default_registry_bundle(store, return_selected_profile=True)
    root = RunContext.start(
        store, registry.bundle_ref, run_id="root", run_dir=store.root / "runs" / "root"
    )
    workflow = store.put_json(
        {},
        PutOptions(kind="tests.workflow", media_type="application/json"),
        return_selected_profile=True,
    )
    state = store.put_json(
        {},
        PutOptions(kind="tests.state", media_type="application/json"),
        return_selected_profile=True,
    )
    attempt_id = str(uuid4())
    basis = root._record_runtime_invocation_started(
        attempt_id=attempt_id,
        attempt_number=1,
        workflow_spec_ref=workflow,
        node_alias="parent",
        component_id="tests.parent",
        input_state_ref=state,
    )
    binding = ChildComputationBinding(
        root_run_id="root",
        control_job_id=None,
        parent_attempt_id=attempt_id,
        parent_basis_ref=basis,
        tenant_id=None,
        cell_id=None,
        policy_id="tests.local_builtin",
        policy_version="1",
        template_sha256="sha256:" + "1" * 64,
        admission_id="actual_test_engine_admission",
        child_invocation_id="parent-session",
        admission_generation=1,
        deadline=datetime.now(UTC) + timedelta(minutes=5),
    )
    return root, binding


def test_jobless_refuses_before_managed_scope_or_candidate_write(tmp_path: Path) -> None:
    root, binding = _root(tmp_path)
    assert binding.control_job_id is None
    staging_root = tmp_path / "private"
    release_root = root.store.root / "artifacts" / "ownership" / "child_releases"
    assert not staging_root.exists()
    assert not release_root.exists()
    with pytest.raises(ChildReleaseUnavailableError, match="jobless_child_computation_unsupported"):
        ChildComputationCustody(root, staging_root=staging_root, closure_resolver=_TypedResolver())
    assert not staging_root.exists()
    assert not release_root.exists()
    root.finalize()


def test_jobless_selected_release_head_cannot_grant_reader_admission(tmp_path: Path) -> None:
    root, binding = _root(tmp_path)
    ref = binding.parent_basis_ref
    record = ChildReleaseRecord(
        release_id="1" * 32,
        root_run_id=binding.root_run_id,
        tenant_id=None,
        cell_id=None,
        parent_attempt_id=binding.parent_attempt_id,
        parent_basis_ref=ref,
        projection_ref=ref,
        released_refs=(ref,),
        scope_bindings=(),
        binding_payloads={
            "scope": {
                "control_job_id": None,
                "admission_generation": 1,
                "deadline": binding.deadline.isoformat(),
            }
        },
        execution_outcome="completed",
        parent_effects={},
        parent_effects_sha256="sha256:" + "0" * 64,
    )
    head = _ChildReleaseHead(
        release_id="1" * 32,
        root_run_id=binding.root_run_id,
        served_store_identity="sha256:" + "0" * 64,
        status="released",
        release_ref=ref,
    )
    with pytest.raises(ChildReleaseUnavailableError, match="jobless_child_release_unsupported"):
        _verify_job_authorization(head, record)
    root.finalize()


def test_generic_reader_refuses_self_consistent_legacy_jobless_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A valid old jobless head/record cannot authorize generic selected reads."""
    root, binding = _root(tmp_path)
    served = root.store
    stage = FileSystemCAS(tmp_path / "legacy-private", ownership_enforced=False)
    payload = {
        "root_run_id": binding.root_run_id,
        "parent_attempt_id": binding.parent_attempt_id,
        "tenant_id": None,
        "cell_id": None,
        "control_job_id": None,
        "admission_generation": 1,
        "deadline": binding.deadline.isoformat(),
    }
    info = ArtifactChildReleaseInfo(
        release_id="d" * 32,
        scope_id="e" * 32,
        binding_sha256=child_binding_digest(payload),
        served_store_identity=child_store_identity(served.root),
        root_run_id=binding.root_run_id,
        child_run_id="legacy-child",
    )
    stage._configure_child_staging(info, token=_CHILD_STAGING_TOKEN)
    selected = stage.put_bytes(
        b"legacy candidate",
        PutOptions(kind="tests.child", media_type="text/plain", child_release=info),
        return_selected_profile=True,
    )
    assert stage.get_bytes(selected) == b"legacy candidate"
    record = ChildReleaseRecord(
        release_id=info.release_id,
        root_run_id=binding.root_run_id,
        tenant_id=None,
        cell_id=None,
        parent_attempt_id=binding.parent_attempt_id,
        parent_basis_ref=binding.parent_basis_ref,
        projection_ref=selected,
        released_refs=(selected,),
        scope_bindings=(info,),
        binding_payloads={info.scope_id: payload},
        execution_outcome="completed",
        parent_effects={},
        parent_effects_sha256=child_binding_digest({}),
    )
    release_ref = stage.put_json(
        record.model_dump(mode="json"),
        PutOptions(
            kind="core.child_computation_release",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ChildComputationReleaseRecord", version="1.0"),
            child_release=info,
        ),
        return_selected_profile=True,
    )
    ledger = _ChildReleaseLedger(served.root, info.release_id, binding.root_run_id)
    ledger.enroll(((selected, info), (release_ref, info)))
    served._publish_child_release_profiles(
        stage, (selected, release_ref), ledger, token=_CHILD_STAGING_TOKEN
    )
    ledger.commit(release_ref)
    fresh = FileSystemCAS(served.root, ownership_enforced=False)
    for read in (fresh.get_bytes, fresh.get_manifest):
        with pytest.raises(ChildReleaseUnavailableError, match="jobless_child_release_unsupported"):
            read(selected)
    # Removal control: keep the head, selected manifest, and release record intact.
    from polisyos.core.artifacts import child_release

    monkeypatch.setattr(child_release, "_verify_job_authorization", lambda head, record: None)
    assert fresh.get_bytes(selected) == b"legacy candidate"
    root.finalize()


def test_release_head_root_loss_is_typed_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _ = _root(tmp_path)
    ledger = _ChildReleaseLedger(root.store.root, "f" * 32, "root")

    def missing_root(self: object, *args: object, **kwargs: object) -> None:
        raise FileNotFoundError("owner root disappeared")

    with monkeypatch.context() as patch:
        patch.setattr(type(ledger.root), "resolve", missing_root)
        with pytest.raises(ChildReleaseUnavailableError, match="served_owner_unavailable"):
            _read_head(ledger.root, ledger.release_id)
    root.finalize()
