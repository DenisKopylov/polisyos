"""Selected-family context reads through the real CAS and historical context owner.

The source captures reuse the existing component N4/N5 declarations; those
parents are not a served Generic or NCM execution proof. The context artifact
itself is produced/read by its canonical owner. These tests establish the
consumer's family, selected-profile and historical-scope behavior only.
"""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from polisyos.core import artifacts
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality import acquisition_planner as planner
from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteClosureError
from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContextArtifactOwner
from polisyos.runtime.quality.generation_cycle import (
    SimulationPortObservation,
    _grounding_unavailable,
)
from tests.unit.runtime.quality import test_n7_pre_numerical_source_contract as source_fixtures
from tests.unit.runtime.quality.test_cycle_substrate import (
    _authenticated_tenant_scope,
    _cycle_context,
    _design_problem,
    _registry,
    _TestCurrentJobExecutionOwner,
    _world_record,
)


def _files(root):
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


@contextmanager
def _case(tmp_path, *, generic: bool = True, source_version: str | None = None):
    root = tmp_path / "cas"
    store = artifacts.FileSystemCAS(root)
    problem = _design_problem()
    basis = gy_content_hash(problem.model_dump(mode="json"))
    tenant, cell = "tenant-context-family", "cell-context-family"
    job_id, run_id = "job-context-family", "run-context-family"
    with _authenticated_tenant_scope(tenant_id=tenant, cell_id=cell):
        registry = _registry("education")
        context = _cycle_context(
            design_problem_ref=basis,
            registry=registry,
            world_model_record=_world_record(
                "education",
                registry,
                region_or_jurisdiction="UA",
                policy_slot_ids=("education.teaching_method",),
            ),
        )
        context_owner = CycleSubstrateContextArtifactOwner(
            store=store,
            control_store=_TestCurrentJobExecutionOwner(job_id, run_id),
        )
        context_id = context_owner.persist_for_current_job(context, problem=problem)
        context_ref = artifacts.artifact_ref_for_manifest(store.get_manifest(context_id))
        if generic:
            payload = source_fixtures._pre_numerical_payload(design_problem_ref=basis)
        else:
            payload = source_fixtures._legacy_source(
                source_version or source_fixtures._V1_SOURCE
            ).model_dump(mode="json")
            # Declare the fixture's actual basis before creating its source;
            # no existing source/compiled/profile artifact is modified.
            old_gap = planner.AcquisitionRequirementGap.model_validate(payload["source_gap"])
            availability = {
                key: value
                for key, value in old_gap.metadata["availability"].items()
                if key != "availability_content_hash"
            }
            gap = planner.l1_variable_availability_requirement_gap(
                candidate_id=payload["candidate_id"],
                candidate_content_hash=payload["candidate_content_hash"],
                design_problem_ref=basis,
                availability=availability,
                authority_level=old_gap.authority_level,
            )
            payload["source_gap"] = gap.model_dump(mode="json")
            payload["value_observation"]["candidate_n5_l1_routing"]["requirement_gap"] = (
                gap.model_dump(mode="json")
            )
            payload["design_problem_basis_ref"] = basis
            grounding = _grounding_unavailable(
                payload["candidate_id"],
                issue_codes=("cgf_disposition_missing",),
                candidate_content_hash=payload["candidate_content_hash"],
                design_problem_ref=basis,
                authority_level="research",
            )
            assert grounding.acquisition_requirement is not None
            payload["grounding_observation"] = grounding.model_dump(mode="json")
            payload["grounding_digest_payload"] = {
                "candidate_id": payload["candidate_id"],
                "issue_codes": ["cgf_disposition_missing"],
                "source": "grounding_unavailable",
            }
            payload["accompanying_requirement_gaps"] = [
                grounding.acquisition_requirement.model_dump(mode="json")
            ]
        payload.update(
            tenant_id=tenant,
            cell_id=cell,
            run_id=run_id,
            source_job_id=job_id,
            context_job_ref=context_ref,
        )
        if not generic:
            payload["value_observation"]["candidate_n5_l1_routing"]["context_job_ref"] = (
                context_ref.model_dump(mode="json")
            )
        source = planner._N7ConfiguredCandidatePortSource.model_validate(payload)
        source_ref = planner._n7_put_configured_candidate_port_source(store, source)
        simulation = SimulationPortObservation(
            candidate_id=source.candidate_id,
            status="simulation_blocked" if generic else "joint_simulated",
            simulation_result_ref=None if generic else source.n5_result_ref,
            cycle_substrate_context_job_ref=context_ref,
            generic_context_job_ref=context_ref if generic else None,
            generic_n4_source_ref=source.n4_source_ref if generic else None,
            generic_profile_ref=(
                source_fixtures._selected_ref(
                    "runtime.quality.generic_cycle_simulation_profile", "8", "2"
                )
                if generic
                else None
            ),
            generic_n5_input_ref=source.n5_input_ref if generic else None,
            generic_n5_execution_ref=source.n5_execution_ref if generic else None,
            generic_profile_selection_ref=basis if generic else None,
            candidate_simulation_n4_source_ref=None if generic else source.n4_source_ref,
            candidate_simulation_context_job_ref=None if generic else context_ref,
            candidate_simulation_n5_input_ref=None if generic else source.n5_input_ref,
            candidate_simulation_profile_config_ref=None if generic else basis,
            candidate_simulation_profile_selection_ref=None if generic else basis,
        )
        closure = SimpleNamespace(
            tenant_id=tenant,
            cell_id=cell,
            run_id=run_id,
            source_job_id=job_id,
            design_problem_basis=problem,
            generation_run=SimpleNamespace(run_id=source.source_generation_run_id),
            source_cycle=SimpleNamespace(
                simulation=simulation,
                cycle_index=source.cycle_index,
                selected_candidate_ref=source.candidate_id,
                selected_candidate_content_hash=source.candidate_content_hash,
                design_problem_basis_ref=basis,
                design_problem_ref=basis,
            ),
            native_derivation_leaf_scope=SimpleNamespace(configured_port_source_ref=source_ref),
        )
        bridge = object.__new__(AcquisitionWorldGrowthBridge)
        bridge.artifact_store = artifacts.FileSystemCAS.open_existing_read_only(root)
        yield SimpleNamespace(
            root=root,
            store=store,
            source=source,
            source_ref=source_ref,
            context_ref=context_ref,
            closure=closure,
            bridge=bridge,
        )


def test_generic_reentry_reads_its_selected_historical_context_without_writes(tmp_path):
    with _case(tmp_path) as case:
        before = _files(case.root)
        source, context, n4 = case.bridge._native_derivation_reentry_source_refs(case.closure)
        assert source == case.source
        assert context == case.context_ref
        assert n4 == case.source.n4_source_ref
        assert case.closure.source_cycle.simulation.candidate_simulation_context_job_ref is None
        assert _files(case.root) == before


@pytest.mark.parametrize("version", [source_fixtures._V1_SOURCE, source_fixtures._V2_SOURCE])
def test_ncm_legacy_reentry_keeps_its_own_selected_context(tmp_path, version):
    with _case(tmp_path, generic=False, source_version=version) as case:
        before = _files(case.root)
        source, context, n4 = case.bridge._native_derivation_reentry_source_refs(case.closure)
        assert source == case.source and context == case.context_ref
        assert n4 == case.source.n4_source_ref
        assert _files(case.root) == before


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ("absent", "native_derivation_reentry_selected_refs_missing"),
        ("mixed", "native_derivation_reentry_source_family_mixed"),
        ("context_profile", "native_derivation_reentry_selected_refs_mismatch"),
        ("n4_profile", "native_derivation_reentry_selected_refs_mismatch"),
        ("foreign_source", "native_derivation_reentry_source_mismatch"),
    ],
)
def test_reentry_context_refuses_missing_mixed_foreign_or_grafted_selection(tmp_path, change, code):
    with _case(tmp_path) as case:
        simulation = case.closure.source_cycle.simulation
        if change == "absent":
            simulation = simulation.model_copy(update={"generic_context_job_ref": None})
        elif change == "mixed":
            simulation = simulation.model_copy(
                update={"candidate_simulation_context_job_ref": case.context_ref}
            )
        elif change in {"context_profile", "n4_profile"}:
            field = (
                "generic_context_job_ref"
                if change == "context_profile"
                else "generic_n4_source_ref"
            )
            ref = getattr(simulation, field)
            simulation = simulation.model_copy(
                update={
                    field: ref.model_copy(update={"manifest_profile_sha256": "sha256:" + "0" * 64})
                }
            )
        else:
            case.closure.tenant_id = "foreign-tenant"
        case.closure.source_cycle.simulation = simulation
        before = _files(case.root)
        with pytest.raises(AcquisitionRouteClosureError) as refusal:
            case.bridge._native_derivation_reentry_source_refs(case.closure)
        assert refusal.value.code == code
        assert _files(case.root) == before


def test_coherent_context_profile_graft_does_not_replace_the_context_owner(tmp_path):
    with _case(tmp_path) as case:
        selected = case.store.get_manifest(case.context_ref)
        foreign = case.store.put_bytes(
            case.store.get_bytes(case.context_ref),
            artifacts.ArtifactWriteOptions(
                kind=case.context_ref.kind,
                media_type=case.context_ref.media_type,
                schema=selected.artifact_schema,
                producer=artifacts.ProducerInfo(
                    component="unrelated.context.fixture", version="1.0"
                ),
            ),
            return_selected_profile=True,
        )
        assert foreign.artifact_id == case.context_ref.artifact_id
        assert foreign.manifest_profile_sha256 != case.context_ref.manifest_profile_sha256
        source = planner._N7ConfiguredCandidatePortSource.model_validate(
            case.source.model_copy(update={"context_job_ref": foreign}).model_dump(mode="json")
        )
        source_ref = planner._n7_put_configured_candidate_port_source(case.store, source)
        case.closure.native_derivation_leaf_scope.configured_port_source_ref = source_ref
        case.closure.source_cycle.simulation = case.closure.source_cycle.simulation.model_copy(
            update={"generic_context_job_ref": foreign}
        )
        before = _files(case.root)
        with pytest.raises(AcquisitionRouteClosureError) as refusal:
            case.bridge._native_derivation_reentry_source_refs(case.closure)
        assert refusal.value.code == "native_derivation_reentry_source_not_established"
        assert _files(case.root) == before


def test_source_declaration_cannot_rebind_the_actual_context_job_owner(tmp_path):
    with _case(tmp_path) as case:
        foreign_job = "foreign-declared-source-job"
        source = planner._N7ConfiguredCandidatePortSource.model_validate(
            case.source.model_copy(update={"source_job_id": foreign_job}).model_dump(mode="json")
        )
        source_ref = planner._n7_put_configured_candidate_port_source(case.store, source)
        case.closure.source_job_id = foreign_job
        case.closure.native_derivation_leaf_scope.configured_port_source_ref = source_ref
        before = _files(case.root)
        with pytest.raises(AcquisitionRouteClosureError) as refusal:
            case.bridge._native_derivation_reentry_source_refs(case.closure)
        assert refusal.value.code == "native_derivation_reentry_source_not_established"
        assert _files(case.root) == before
