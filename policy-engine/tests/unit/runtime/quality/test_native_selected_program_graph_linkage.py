"""Supplemental Native V2 compiler-linkage checks without claiming owner history."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError


def _unverified_candidate_ref(kind: str, label: str):
    """Build a typed candidate pointer for the compiler-law component test only."""
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.pdc import gy_content_hash

    return ArtifactRef(
        artifact_id=gy_content_hash({"candidate_ref": label}),
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256=gy_content_hash({"candidate_manifest": label}),
    )


def test_native_linkage_reuses_selected_compiler_law_and_preserves_v1_wire(
    tmp_path: Path,
) -> None:
    """V2 adds candidate context identity while V1 and the actual linker stay stable.

    The Native references below are explicitly unverified component pointers. This
    test covers the V2 payload/compiler boundary, not Native action history replay.
    """
    from polisyos.core.artifacts import PutOptions, WarningRecord
    from polisyos.core.registry import load_registry_bundle_content
    from polisyos.runtime.quality import design_generation as n4
    from polisyos.runtime.quality.cycle_substrate import (
        cycle_job_design_problem_ref,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleN5PairedProgramGraphRequestProfileV5,
        GenericCycleN5RequestProfileV1,
    )
    from polisyos.runtime.quality.world_model_record import world_model_artifact_views
    from tests.unit.runtime.quality.test_cycle_substrate import _cycle_context
    from tests.unit.runtime.quality.test_generic_simulation_admission_program_graph import (
        _linkage_problem,
        _with_hash,
        compiled_selection,
    )

    case = compiled_selection.__wrapped__(tmp_path)
    problem = _linkage_problem().model_copy(update={"domain": case.world.policy_domain})
    context = _cycle_context(
        domain=problem.domain,
        registry=case.profile.context_inputs.substrate_registry,
        world_model_record=case.world,
        design_problem_ref=cycle_job_design_problem_ref(problem),
    )
    registry_ref = world_model_artifact_views(case.world).registry_bundle_ref
    assert registry_ref is not None
    registry_content = load_registry_bundle_content(case.store, registry_ref)

    profile_ref = _unverified_candidate_ref(
        "runtime.quality.generic_cycle_simulation_profile", "native-linkage-profile"
    )
    legacy = n4.N4SelectedProgramGraphLinkageV1.from_selected_owner(
        profile_ref=profile_ref,
        profile=case.profile,
        registry_bundle_ref=registry_ref,
    )
    legacy_payload = legacy.model_dump(mode="json")
    assert legacy.schema_version == "policyos.runtime.n4_selected_program_graph_linkage.v1"
    assert set(legacy_payload) == {
        "schema_version",
        "authority_purpose",
        "profile_ref",
        "profile_content_hash",
        "profile_selection_ref",
        "compile_report_ref",
        "registry_bundle_ref",
        "content_hash",
    }

    paired_profile_fields = case.profile.n5.model_dump(mode="python")
    paired_profile_fields["schema_version"] = "policyos.runtime.generic_cycle_n5_request_profile.v5"
    paired_n5 = GenericCycleN5PairedProgramGraphRequestProfileV5.model_validate(
        paired_profile_fields
    )
    paired_profile = _with_hash(case.profile.model_copy(update={"n5": paired_n5}))
    paired_linkage = n4.N4SelectedProgramGraphLinkageV1.from_selected_owner(
        profile_ref=_unverified_candidate_ref(
            "runtime.quality.generic_cycle_simulation_profile", "native-linkage-paired-profile"
        ),
        profile=paired_profile,
        registry_bundle_ref=registry_ref,
    )
    assert type(paired_profile.n5) is GenericCycleN5PairedProgramGraphRequestProfileV5
    assert paired_linkage.profile_content_hash == paired_profile.content_hash
    assert paired_linkage.compile_report_ref == case.profile.n5.compile_report_ref
    assert paired_linkage.registry_bundle_ref == registry_ref

    unsupported_n5 = GenericCycleN5RequestProfileV1(
        budget_ref=case.profile.n5.budget_ref,
        horizon=case.profile.n5.horizon,
        baseline_state=case.profile.n5.baseline_state,
    )
    unsupported_profile = _with_hash(
        case.profile.model_copy(
            update={
                "n5": unsupported_n5,
                "selected_ncm_ref": _unverified_candidate_ref("ir.ncm_spec", "unsupported-ncm"),
            }
        )
    )
    with pytest.raises(ValueError, match="n4_selected_program_graph_profile_untyped"):
        n4.N4SelectedProgramGraphLinkageV1.from_selected_owner(
            profile_ref=_unverified_candidate_ref(
                "runtime.quality.generic_cycle_simulation_profile",
                "native-linkage-unsupported-profile",
            ),
            profile=unsupported_profile,
            registry_bundle_ref=registry_ref,
        )

    v2_payload = legacy.model_dump(mode="json", exclude={"content_hash"})
    v2_payload.update(
        {
            "schema_version": "policyos.runtime.n4_selected_program_graph_linkage.v2",
            "profile_selection_ref": cycle_job_profile_selection_ref(problem),
            "original_profile_selection_ref": case.profile.profile_selection_ref,
            "context_job_ref": _unverified_candidate_ref(
                "runtime.quality.cycle_substrate_context_job", "native-context"
            ).model_dump(mode="json"),
            "context_content_hash": context.content_hash,
            "native_world_checkpoint_ref": _unverified_candidate_ref(
                "runtime_quality.acquisition_candidate_world_checkpoint", "native-checkpoint"
            ).model_dump(mode="json"),
            "original_generic_input_ref": _unverified_candidate_ref(
                "runtime.quality.generic_cycle_simulation_n5_input", "original-generic-input"
            ).model_dump(mode="json"),
        }
    )
    linkage = n4.N4SelectedProgramGraphLinkageV2.model_validate(
        {**v2_payload, "content_hash": n4.gy_content_hash(v2_payload)}
    )
    assert linkage.profile_ref == legacy.profile_ref
    assert linkage.profile_content_hash == case.profile.content_hash
    assert linkage.original_profile_selection_ref == case.profile.profile_selection_ref
    assert linkage.profile_selection_ref == cycle_job_profile_selection_ref(problem)
    assert linkage.authority_purpose == "candidate_linkage_only"

    adapter = TypeAdapter(n4.N4SelectedProgramGraphLinkage)
    for selected in (legacy, linkage):
        wire = adapter.dump_json(selected)
        reopened = adapter.validate_json(wire)
        assert type(reopened) is type(selected)
        assert reopened.model_dump(mode="json") == selected.model_dump(mode="json")

    linkage_context = n4.N4SelectedProgramGraphLinkContext(
        linkage=linkage, registry_content=registry_content
    )
    registries = n4._selected_program_graph_link_registries(
        linkage_context,
        design_problem=problem,
        context=context,
        bundle=case.trinity,
    )
    assert registries is not None
    intervention = case.trinity.policy_spec.interventions[0]
    linked = n4._link_selected_program_graph_intervention(
        bundle=case.trinity,
        intervention=intervention,
        linkage_context=linkage_context,
        registries=registries,
        required_do_slots=("agents.income",),
    )
    assert linked.reads_slots == ["agents.income"]
    assert linked.writes_slots == ["agents.income", "government.balance"]

    foreign_context = _cycle_context(
        domain=problem.domain,
        lever_id="foreign_native_context",
        registry=case.profile.context_inputs.substrate_registry,
        world_model_record=case.world,
        design_problem_ref=cycle_job_design_problem_ref(problem),
    )
    with pytest.raises(
        n4.DesignGenerationError,
        match="n4_native_selected_program_graph_context_mismatch",
    ):
        n4._selected_program_graph_link_registries(
            linkage_context,
            design_problem=problem,
            context=foreign_context,
            bundle=case.trinity,
        )

    manifest = case.store.get_manifest(registry_ref)
    foreign_registry_ref = case.store.put_bytes(
        case.store.get_bytes(registry_ref),
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            canon=manifest.canon,
            inputs=manifest.inputs,
            warnings=[
                WarningRecord(code="fixture.foreign_registry_view", msg="Distinct selected view.")
            ],
        ),
        return_selected_profile=True,
    )
    foreign_registry_content = load_registry_bundle_content(case.store, foreign_registry_ref)
    with pytest.raises(ValueError, match="n4_selected_program_graph_registry_ref_mismatch"):
        n4.N4SelectedProgramGraphLinkContext(
            linkage=linkage, registry_content=foreign_registry_content
        )

    with pytest.raises(ValidationError):
        n4.N4SelectedProgramGraphLinkageV2.model_validate(
            {
                key: value
                for key, value in linkage.model_dump(mode="json").items()
                if key != "registry_bundle_ref"
            }
        )

    with pytest.raises(
        n4.DesignGenerationError,
        match="n4_selected_program_graph_candidate_link_refused",
    ):
        n4._link_selected_program_graph_intervention(
            bundle=case.trinity,
            intervention=intervention,
            linkage_context=linkage_context,
            registries=registries,
            required_do_slots=("government.tax_rate",),
        )


def test_native_acquired_context_binding_uses_constructor_upstream_callback(
    tmp_path: Path,
) -> None:
    """Bind a candidate Native pair only under its real SQLite acquisition lease.

    The handoff and its references are explicitly unverified component inputs.
    This test exercises private callback identity and temporary binding only; it
    does not claim checkpoint replay, acquisition permission, or N5 execution.
    """
    from polisyos.runtime.http.services.control_plane_store import (
        ControlPlaneStore,
    )
    from polisyos.runtime.quality.acquisition_world_growth import (
        _acquired_world_context_binding,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
        cycle_job_design_problem_ref,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.generation_cycle import GenerationCycleController
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleNativeWorldContextHandoffV1,
        GenericCycleSimulationAdmissionOwner,
    )
    from tests.unit.runtime.http.test_control_plane_store import (
        _job_creation_event,
        _job_execution_scope,
        _make_store,
        _prepared_candidate_action_head,
    )
    from tests.unit.runtime.quality.test_cycle_substrate import _cycle_context
    from tests.unit.runtime.quality.test_generic_simulation_admission_program_graph import (
        _linkage_problem,
        compiled_selection,
    )

    case = compiled_selection.__wrapped__(tmp_path)
    problem = _linkage_problem().model_copy(update={"domain": case.world.policy_domain})
    context = _cycle_context(
        domain=problem.domain,
        registry=case.profile.context_inputs.substrate_registry,
        world_model_record=case.world,
        design_problem_ref=cycle_job_design_problem_ref(problem),
    )

    control_store: ControlPlaneStore = _make_store(tmp_path / "control")
    publication = _prepared_candidate_action_head(job_id="native-context-binding-action")
    execution_scope = {
        **_job_execution_scope(),
        "tenant_id": publication.tenant_id,
        "cell_id": publication.cell_id,
    }
    creation_event = {
        **_job_creation_event(execution_scope=execution_scope),
        "job_id": publication.job_id,
        "run_id": publication.run_id,
        "job_kind": "acquisition",
        "payload_ref": publication.payload_ref,
        "submitted_by": "denis",
        "policy_flags": {},
        "capability_manifest_ref": None,
    }
    job = control_store.create_job(
        job_id=publication.job_id,
        kind="acquisition",
        run_id=publication.run_id,
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=publication.payload_ref,
        submitted_by="denis",
        creation_event_payload=creation_event,
        prepared_acquisition_action_head=publication,
    )
    worker_id = "native-context-binding-worker"
    leased = control_store.lease_next_job(worker_id=worker_id, lease_seconds=30)
    assert leased is not None and leased.job_id == job.job_id

    profile_ref = _unverified_candidate_ref(
        "runtime.quality.generic_cycle_simulation_profile", "native-binding-profile"
    )
    handoff = GenericCycleNativeWorldContextHandoffV1(
        context=context,
        context_job_ref=_unverified_candidate_ref(
            "runtime.quality.cycle_substrate_context_job", "native-binding-context"
        ),
        profile=case.profile,
        profile_ref=profile_ref,
        native_world_checkpoint_ref=_unverified_candidate_ref(
            "runtime_quality.acquisition_candidate_world_checkpoint",
            "native-binding-checkpoint",
        ),
        original_generic_input_ref=_unverified_candidate_ref(
            "runtime.quality.generic_cycle_simulation_n5_input",
            "native-binding-original-input",
        ),
        current_profile_selection_ref=cycle_job_profile_selection_ref(problem),
        source_job_id=publication.source_job_id,
        job_id=publication.job_id,
        run_id=publication.run_id,
        tenant_id=publication.tenant_id,
        cell_id=publication.cell_id,
    )
    generic_owner = GenericCycleSimulationAdmissionOwner(profiles=(case.profile,), store=case.store)
    context_owner = CycleSubstrateContextArtifactOwner(
        store=case.store, control_store=control_store
    )

    def upstream_currentness() -> bool:
        return False

    controller = GenerationCycleController(
        repo_root=tmp_path,
        model_id="native-context-binding-fixture",
        authority_scope="contract_testing",
        artifact_store=case.store,
        cycle_substrate_context=context,
        generic_cycle_simulation_admission_owner=generic_owner,
        generic_cycle_simulation_handoff=handoff,
        generic_cycle_simulation_currentness_resolver=upstream_currentness,
    )
    assert controller._generic_cycle_simulation_upstream_currentness_resolver is (
        upstream_currentness
    )
    assert controller._generic_cycle_simulation_currentness_resolver is not upstream_currentness
    assert upstream_currentness() is False

    try:
        with control_store.job_execution_fence(
            job_id=leased.job_id,
            worker_id=worker_id,
            attempt=leased.attempt,
        ):
            admission = control_store.current_execution_job_admission()
            assert admission.job.kind == "acquisition"
            assert admission.job.run_id == handoff.run_id
            assert admission.job.job_id == handoff.job_id
            assert admission.scope.status == "established"
            assert (admission.scope.tenant_id, admission.scope.cell_id) == (
                handoff.tenant_id,
                handoff.cell_id,
            )
            original_binding = controller._candidate_source_reentry_context_binding
            with _acquired_world_context_binding(
                controller=controller,
                context_owner=context_owner,
                handoff=handoff,
                currentness_resolver=upstream_currentness,
                control_store=control_store,
            ):
                assert controller._candidate_source_reentry_context_binding == (
                    context_owner,
                    handoff,
                )
            assert controller._candidate_source_reentry_context_binding == original_binding

            def other_currentness() -> bool:
                return False

            with (
                pytest.raises(
                    ValueError,
                    match="acquisition_candidate_context_owner_binding_mismatch",
                ),
                _acquired_world_context_binding(
                    controller=controller,
                    context_owner=context_owner,
                    handoff=handoff,
                    currentness_resolver=other_currentness,
                    control_store=control_store,
                ),
            ):
                pytest.fail("a distinct callback identity must not bind the Native pair")
            assert controller._candidate_source_reentry_context_binding == original_binding
    finally:
        control_store.close()


def test_native_source_write_refuses_candidate_linkage_without_history_owner(
    tmp_path: Path,
) -> None:
    """Source persistence refuses typed Native pointers without actual history replay."""
    from dataclasses import replace

    from polisyos.core import canon
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.quality import design_generation as n4
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
        cycle_job_design_problem_ref,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.design_problem import (
        DESIGN_PROBLEM_V3_SCHEMA_VERSION,
        DesignProblem,
    )
    from polisyos.runtime.quality.generation_source import (
        SOURCE_KIND,
        GenerationSourceRepository,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationAdmissionOwner,
    )
    from polisyos.runtime.quality.world_model_record import world_model_artifact_views
    from tests.unit.runtime.http.test_control_plane_store import (
        _job_creation_event,
        _job_execution_scope,
        _make_store,
        _prepared_candidate_action_head,
    )
    from tests.unit.runtime.quality.test_generic_simulation_admission_program_graph import (
        _linkage_problem,
        _with_hash,
        compiled_selection,
    )

    case = compiled_selection.__wrapped__(tmp_path)
    base_problem = _linkage_problem()
    world_as_of_valid_time = case.world.fabric_world_ref.as_of_valid_time
    assert isinstance(world_as_of_valid_time, str)
    problem_payload = base_problem.model_dump(mode="json")
    problem_payload.update(
        {
            "schema_version": DESIGN_PROBLEM_V3_SCHEMA_VERSION,
            "domain": case.world.policy_domain,
            "jurisdiction_time": {
                **problem_payload["jurisdiction_time"],
                "region": case.world.region_or_jurisdiction,
                "valid_time": case.world.valid_time_scope,
                "as_of": world_as_of_valid_time,
                "policy_time": case.world.valid_time_scope,
                "data_time": world_as_of_valid_time,
            },
            "outcome_of_interest": {
                **problem_payload["outcome_of_interest"],
                "target_variable": "government.balance",
            },
            "candidate_lever_space": {
                **problem_payload["candidate_lever_space"],
                "candidate_levers": [
                    {**lever, "target_slot": "agents.income"}
                    for lever in problem_payload["candidate_lever_space"]["candidate_levers"]
                ],
            },
        }
    )
    problem = DesignProblem.model_validate(problem_payload)
    problem_ref = cycle_job_design_problem_ref(problem)
    profile_selection_ref = cycle_job_profile_selection_ref(problem)
    profile = _with_hash(
        case.profile.model_copy(update={"profile_selection_ref": profile_selection_ref})
    )
    profile_owner = GenericCycleSimulationAdmissionOwner(profiles=(profile,), store=case.store)
    context = profile_owner.context_for_profile(profile, problem)

    control_store = _make_store(tmp_path / "source-control")
    publication = _prepared_candidate_action_head(job_id="native-source-without-history")
    execution_scope = {
        **_job_execution_scope(),
        "tenant_id": publication.tenant_id,
        "cell_id": publication.cell_id,
    }
    creation_event = {
        **_job_creation_event(execution_scope=execution_scope),
        "job_id": publication.job_id,
        "run_id": publication.run_id,
        "job_kind": "acquisition",
        "payload_ref": publication.payload_ref,
        "submitted_by": "denis",
        "policy_flags": {},
        "capability_manifest_ref": None,
    }
    control_store.create_job(
        job_id=publication.job_id,
        kind="acquisition",
        run_id=publication.run_id,
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=publication.payload_ref,
        submitted_by="denis",
        creation_event_payload=creation_event,
        prepared_acquisition_action_head=publication,
    )
    worker_id = "native-source-without-history-worker"
    leased = control_store.lease_next_job(worker_id=worker_id, lease_seconds=30)
    assert leased is not None and leased.job_id == publication.job_id

    try:
        with control_store.job_execution_fence(
            job_id=leased.job_id,
            worker_id=worker_id,
            attempt=leased.attempt,
        ):
            admission = control_store.current_execution_job_admission()
            assert admission.job.kind == "acquisition"
            assert admission.scope.status == "established"
            with tenant_scope(
                None,
                tenant_id=admission.scope.tenant_id,
                cell_id=admission.scope.cell_id,
            ):
                profile_options = profile_owner._profile_write_options(
                    profile=profile,
                    job_id=admission.job.job_id,
                    run_id=admission.job.run_id,
                    tenant_id=admission.scope.tenant_id,
                    cell_id=admission.scope.cell_id,
                )
                profile_ref = case.store.put_json(
                    profile.model_dump(mode="json"),
                    profile_options,
                    canon_spec=canon.CanonSpec(forbid_floats=False),
                    return_selected_profile=True,
                )
                context_ref = CycleSubstrateContextArtifactOwner(
                    store=case.store,
                    control_store=control_store,
                ).persist_for_current_job(
                    context,
                    problem=problem,
                    return_selected_profile=True,
                )
                profile_bytes = case.store.get_bytes(profile_ref)
                registry_ref = world_model_artifact_views(case.world).registry_bundle_ref
                assert registry_ref is not None
                legacy = n4.N4SelectedProgramGraphLinkageV1.from_selected_owner(
                    profile_ref=profile_ref,
                    profile=profile,
                    registry_bundle_ref=registry_ref,
                )
                linkage_payload = legacy.model_dump(mode="json", exclude={"content_hash"})
                linkage_payload.update(
                    {
                        "schema_version": "policyos.runtime.n4_selected_program_graph_linkage.v2",
                        "profile_selection_ref": profile_selection_ref,
                        "original_profile_selection_ref": profile.profile_selection_ref,
                        "context_job_ref": context_ref.model_dump(mode="json"),
                        "context_content_hash": context.content_hash,
                        "native_world_checkpoint_ref": _unverified_candidate_ref(
                            "runtime_quality.acquisition_candidate_world_checkpoint",
                            "missing-history-checkpoint",
                        ).model_dump(mode="json"),
                        "original_generic_input_ref": _unverified_candidate_ref(
                            "runtime.quality.generic_cycle_simulation_n5_input",
                            "missing-history-original-input",
                        ).model_dump(mode="json"),
                    }
                )
                linkage = n4.N4SelectedProgramGraphLinkageV2.model_validate(
                    {
                        **linkage_payload,
                        "content_hash": n4.gy_content_hash(linkage_payload),
                    }
                )
                result = n4.GenerationUnderAResult(
                    status="generation_unavailable",
                    design_problem_ref=problem_ref,
                    model_id="native-source-missing-history",
                    preflight=n4.ModelProfilePreflight(
                        status="gateway_unavailable", model_id="native-source-missing-history"
                    ),
                    diversity_report=n4.GenerationDiversityReport(
                        min_required=1,
                        candidate_count=0,
                        unique_diversity_key_count=0,
                    ),
                )
                ordinary_organ = replace(
                    result.as_organ_run(trinity_bundle=case.trinity),
                    cycle_substrate_context=context,
                    selected_program_graph_linkage=legacy,
                )
                repository = GenerationSourceRepository(case.store)
                ordinary_source_ref = repository.persist_ref(
                    run_id="native-source-missing-history-run",
                    cycle_index=0,
                    problem=problem,
                    organ=ordinary_organ,
                    execution_scope="contract_testing",
                    job_id=admission.job.job_id,
                    expected_run_id=admission.job.run_id,
                    tenant_id=admission.scope.tenant_id,
                    cell_id=admission.scope.cell_id,
                    context_job_ref=context_ref,
                    profile_ref=profile_ref,
                )
                ordinary_source = repository.load(
                    ordinary_source_ref,
                    run_id="native-source-missing-history-run",
                    expected_run_id=admission.job.run_id,
                    expected_job_id=admission.job.job_id,
                    expected_tenant_id=admission.scope.tenant_id,
                    expected_cell_id=admission.scope.cell_id,
                    context_job_ref=context_ref,
                    profile_ref=profile_ref,
                )
                assert ordinary_source.selected_program_graph_linkage == legacy
                source_inventory = case.store.manifest_inventory_snapshot(kind=SOURCE_KIND).entries
                organ = replace(
                    ordinary_organ,
                    selected_program_graph_linkage=linkage,
                )
                with pytest.raises(
                    ValueError,
                    match="generation_source_selected_program_graph_replay_failed",
                ) as refused:
                    repository.persist_ref(
                        run_id="native-source-missing-history-run",
                        cycle_index=0,
                        problem=problem,
                        organ=organ,
                        execution_scope="contract_testing",
                        job_id=admission.job.job_id,
                        expected_run_id=admission.job.run_id,
                        tenant_id=admission.scope.tenant_id,
                        cell_id=admission.scope.cell_id,
                        context_job_ref=context_ref,
                        profile_ref=profile_ref,
                    )
                assert (
                    str(refused.value.__cause__)
                    == "generation_source_native_history_owner_unavailable"
                )
                assert case.store.manifest_inventory_snapshot(kind=SOURCE_KIND).entries == (
                    source_inventory
                )
                assert case.store.get_bytes(profile_ref) == profile_bytes
    finally:
        control_store.close()
