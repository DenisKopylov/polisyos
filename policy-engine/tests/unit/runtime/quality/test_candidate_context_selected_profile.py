"""Context persistence forwards the actual writer-selected manifest view."""

from __future__ import annotations

from contextlib import closing
from dataclasses import replace
from pathlib import Path

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    ProducerInfo,
    PutOptions,
    artifact_manifest_profile_sha256,
    load_core_json_artifact,
)
from polisyos.core.canon import CanonSpec
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.cycle_substrate import (
    _CONTEXT_JOB_CANON,
    CycleSubstrateContextArtifactOwner,
    CycleSubstrateContextOwnerError,
    _context_job_write_options,
    cycle_job_design_problem_ref,
)
from tests.unit.runtime.http.test_cycle_substrate_job_execution_binding import (
    _create_execution_scoped_job,
)
from tests.unit.runtime.quality.test_cycle_substrate import (
    _authenticated_tenant_scope,
    _cycle_context,
    _design_problem,
    _registry,
    _world_record,
)

TENANT_ID = "e7db6c57-e11d-4c29-881e-c54172dd08ef"
CELL_ID = "17f51f84-04fa-4c8b-8fcb-0a3f49cd976d"


def test_context_selected_profile_comes_from_writer_and_exact_manifest_is_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A live job reopens the selected context and refuses manifest fallback."""
    problem = _design_problem()
    registry = _registry("education")
    world = _world_record(
        "education",
        registry,
        region_or_jurisdiction="UA",
        policy_slot_ids=("education.teaching_method",),
    )
    context = _cycle_context(
        design_problem_ref=cycle_job_design_problem_ref(problem),
        registry=registry,
        world_model_record=world,
    )
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=True, ownership_requires_scope=True)
    with closing(
        ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control-plane.sqlite3")
    ) as control:
        leased = _create_execution_scoped_job(
            control,
            job_id="job-selected-context",
            run_id="run-selected-context",
            tenant_id=TENANT_ID,
            cell_id=CELL_ID,
            actor_subject="selected-context-test-actor",
        )
        assert leased.lease_owner
        owner = CycleSubstrateContextArtifactOwner(store=store, control_store=control)
        verified_owner = CycleSubstrateContextArtifactOwner(
            store=store,
            control_store=control,
            context_admission_verifier=lambda _ref, _context: True,
        )
        writes: list[tuple[bool, ArtifactRef]] = []
        real_put_json = store.put_json

        def observe_real_write(
            obj: object,
            opts: PutOptions,
            canon_spec: CanonSpec | None = None,
            *,
            return_selected_profile: bool = False,
        ) -> ArtifactRef:
            written = real_put_json(
                obj, opts, canon_spec=canon_spec, return_selected_profile=return_selected_profile
            )
            writes.append((return_selected_profile, written))
            return written

        with (
            _authenticated_tenant_scope(tenant_id=TENANT_ID, cell_id=CELL_ID),
            control.job_execution_fence(
                job_id=leased.job_id, worker_id=leased.lease_owner, attempt=leased.attempt
            ),
        ):
            with monkeypatch.context() as observed:
                observed.setattr(store, "put_json", observe_real_write)
                selected = owner.persist_for_current_job(
                    context, problem=problem, return_selected_profile=True
                )
                assert len(writes) == 1
                assert writes[0][0] is True
                assert selected is writes[0][1]
                legacy = owner.persist_for_current_job(context, problem=problem)
                assert len(writes) == 2
                assert writes[1][0] is False
                assert legacy is writes[1][1]
                verified_selected = verified_owner.persist_for_current_job(context, problem=problem)
                assert len(writes) == 3
                assert writes[2][0] is True
                assert verified_selected is writes[2][1]
            assert selected.manifest_profile_sha256
            assert legacy.artifact_id == selected.artifact_id
            assert verified_selected == selected

            # The real CAS writes the selected view, but a defective delegate
            # can suppress or corrupt its return. The owning writer must not
            # silently forward that result to a selected-profile caller.
            for fault in ("missing_profile", "wrong_kind", "wrong_media", "untyped"):

                def corrupt_selected_write(
                    obj: object,
                    opts: PutOptions,
                    canon_spec: CanonSpec | None = None,
                    *,
                    return_selected_profile: bool = False,
                    _fault: str = fault,
                ) -> ArtifactRef | None:
                    written = real_put_json(
                        obj,
                        opts,
                        canon_spec=canon_spec,
                        return_selected_profile=return_selected_profile,
                    )
                    assert return_selected_profile and written.manifest_profile_sha256
                    assert store.verify(written).ok
                    if _fault == "untyped":
                        return None
                    updates = {
                        "missing_profile": {"manifest_profile_sha256": None},
                        "wrong_kind": {"kind": "runtime.quality.foreign_context"},
                        "wrong_media": {"media_type": "text/plain"},
                    }
                    return written.model_copy(update=updates[_fault])

                with monkeypatch.context() as defective:
                    defective.setattr(store, "put_json", corrupt_selected_write)
                    with pytest.raises(
                        CycleSubstrateContextOwnerError,
                        match="cycle_substrate_context_writer_profile_not_established",
                    ):
                        owner.persist_for_current_job(
                            context, problem=problem, return_selected_profile=True
                        )
                    # A verifier-backed owner also asks the writer for the
                    # selected profile when the public option is omitted.
                    with pytest.raises(
                        CycleSubstrateContextOwnerError,
                        match="cycle_substrate_context_writer_profile_not_established",
                    ):
                        verified_owner.persist_for_current_job(context, problem=problem)
            manifest = store.get_manifest_by_profile(
                selected.artifact_id, selected.manifest_profile_sha256
            )
            assert artifact_manifest_profile_sha256(manifest) == selected.manifest_profile_sha256
            reader = FileSystemCAS.open_existing_read_only(store.root)
            read_owner = CycleSubstrateContextArtifactOwner(store=reader, control_store=control)
            resolved = read_owner.resolve_for_current_job(selected, problem=problem)
            assert resolved.context == context
            assert resolved.problem == problem
            assert (resolved.job_id, resolved.run_id) == (leased.job_id, leased.run_id)
            assert (resolved.tenant_id, resolved.cell_id) == (TENANT_ID, CELL_ID)
            assert resolved.profile_admission_status == "not_established"
            assert resolved.s8_status == "blocked"
            assert read_owner.resolve_for_current_job(legacy, problem=problem) == resolved

            # Same body under an actually written sibling profile is not
            # the manifest selected by the context writer above.
            sibling = store.put_json(
                load_core_json_artifact(store, selected),
                replace(
                    _context_job_write_options(resolved),
                    producer=ProducerInfo(component="test.unrelated-context-writer", version="1"),
                ),
                canon_spec=_CONTEXT_JOB_CANON,
                return_selected_profile=True,
            )
            assert sibling.artifact_id == selected.artifact_id
            assert sibling.manifest_profile_sha256 != selected.manifest_profile_sha256
            substituted_manifest = store.get_manifest_bytes(sibling)
            selected_path = store._manifest_path_for_ref(
                selected.artifact_id, selected.manifest_profile_sha256
            )
            held_path = selected_path.with_name(selected_path.name + ".held")
            assert not held_path.exists()
            selected_path.rename(held_path)
            try:
                with pytest.raises(
                    CycleSubstrateContextOwnerError,
                    match="cycle_substrate_context_job_cas_integrity_failed",
                ):
                    read_owner.resolve_for_current_job(selected, problem=problem)
                selected_path.write_bytes(substituted_manifest)
                with pytest.raises(
                    CycleSubstrateContextOwnerError,
                    match="cycle_substrate_context_job_cas_integrity_failed",
                ):
                    read_owner.resolve_for_current_job(selected, problem=problem)
            finally:
                if selected_path.exists():
                    selected_path.unlink()
                held_path.rename(selected_path)
            assert read_owner.resolve_for_current_job(selected, problem=problem) == resolved
