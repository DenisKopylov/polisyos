"""Synthetic source custody controls; no protected admission is manufactured."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.runtime.quality import design_generation as n4
from polisyos.runtime.quality.generation_cycle import N4GenerationPort
from polisyos.runtime.quality.generation_source import (
    GenerationSourceRepository,
    _canonical_model_content_hash,
    _generation_source_read_result,
    _require_unavailable_candidate_credal_source,
)
from tests.unit.runtime.quality.test_design_generation import (
    REPO_ROOT,
    RecordedClientWithCatalog,
    _bundle,
    _intervention,
    _recording_with_successful_first_response,
    _test_design_problem,
)
from tools.quality.validation import check_layer3_gy_design_generation_contract as contract


def test_candidate_scenario_v4_is_additive_to_historical_v3() -> None:
    """Selected-view v5 adds to earlier wires without reinterpreting history."""

    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationExecutionV3,
        CandidateSimulationExecutionV4,
        CandidateSimulationExecutionV5,
        CandidateSimulationN5InputV3,
        CandidateSimulationN5InputV4,
        CandidateSimulationN5InputV5,
    )
    from polisyos.runtime.quality.generation_source import (
        N4CandidateScenarioSourceRecordV2,
    )

    assert CandidateSimulationN5InputV3.model_fields["schema_version"].default == (
        "policyos.runtime.candidate_simulation.n5_input.v3"
    )
    assert CandidateSimulationExecutionV3.model_fields["schema_version"].default == (
        "policyos.runtime.candidate_simulation.execution.v3"
    )
    assert CandidateSimulationN5InputV4.model_fields["schema_version"].default == (
        "policyos.runtime.candidate_simulation.n5_input.v4"
    )
    assert CandidateSimulationExecutionV4.model_fields["schema_version"].default == (
        "policyos.runtime.candidate_simulation.execution.v4"
    )
    assert CandidateSimulationN5InputV5.model_fields["schema_version"].default == (
        "policyos.runtime.candidate_simulation.n5_input.v5"
    )
    assert CandidateSimulationExecutionV5.model_fields["schema_version"].default == (
        "policyos.runtime.candidate_simulation.execution.v5"
    )
    assert N4CandidateScenarioSourceRecordV2.model_fields["schema_version"].default == (
        "policyos.runtime.quality.n4_candidate_scenario_source.v2"
    )
    assert CandidateSimulationN5InputV4.model_config["extra"] == "forbid"
    assert CandidateSimulationExecutionV4.model_config["extra"] == "forbid"
    assert CandidateSimulationN5InputV5.model_config["extra"] == "forbid"
    assert CandidateSimulationExecutionV5.model_config["extra"] == "forbid"
    assert {"n4_source_ref", "context_job_ref", "profile", "materialization"}.issubset(
        CandidateSimulationN5InputV4.model_fields
    )
    assert {
        "n4_source_ref",
        "context_job_ref",
        "model_declaration_ref",
        "ncm_ref",
        "materialization",
    }.issubset(CandidateSimulationN5InputV5.model_fields)


@pytest.mark.asyncio
async def test_default_n4_port_preserves_actual_organ_bundle(monkeypatch):
    """The real N4 port must not erase the producer's enclosing source object."""
    problem = _test_design_problem()
    intervention = _intervention("corr_synthetic_source").model_copy(
        update={"measurement_expectations": {"synthetic": True}}
    )
    result = n4.GenerationUnderAResult(
        status="generation_unavailable",
        design_problem_ref=n4.gy_content_hash(problem.model_dump(mode="json")),
        model_id="synthetic-c2",
        preflight=n4.ModelProfilePreflight(status="gateway_unavailable", model_id="synthetic-c2"),
        diversity_report=n4.GenerationDiversityReport(
            min_required=1, candidate_count=0, unique_diversity_key_count=0
        ),
    )
    organ = result.as_organ_run(trinity_bundle=_bundle([intervention]))
    incoming_context = object()  # Transport-only witness, never an admitted/persisted context.

    async def produce(_problem, **kwargs):
        assert _problem is problem
        assert kwargs["cycle_substrate_context"] is incoming_context
        return organ

    monkeypatch.setattr(n4, "generate_design_candidate_bundle_under_a", produce)
    port = N4GenerationPort(model_id="synthetic-c2", cycle_substrate_context=incoming_context)

    observed = await port(problem, cycle_index=0)

    assert observed is organ
    assert observed.trinity_bundle is organ.trinity_bundle


def test_n4_source_canonical_identity_reaches_terminal_consumer(tmp_path):
    """Producer/readback comparison retains capture, context, and result wire content."""
    from dataclasses import replace

    from polisyos.core.artifacts import artifact_manifest_profile_sha256
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContext,
        cycle_substrate_context_content_hash,
    )
    from polisyos.runtime.quality.generation_source import _source_content_hash
    from tests.unit.runtime.quality.test_cycle_substrate import _cycle_context

    problem = _test_design_problem()
    result = n4.GenerationUnderAResult(
        status="generation_unavailable",
        design_problem_ref=n4.gy_content_hash(problem.model_dump(mode="json")),
        model_id="synthetic-c2",
        preflight=n4.ModelProfilePreflight(status="gateway_unavailable", model_id="synthetic-c2"),
        diversity_report=n4.GenerationDiversityReport(
            min_required=1, candidate_count=0, unique_diversity_key_count=0
        ),
    )
    context = _cycle_context(design_problem_ref=gy_content_hash(problem.model_dump(mode="json")))
    organ = replace(result.as_organ_run(), cycle_substrate_context=context)
    repository = GenerationSourceRepository(FileSystemCAS(tmp_path / "cas"))
    ref = repository.persist_ref(
        run_id="generic-n4-wire-identity",
        cycle_index=0,
        problem=problem,
        organ=organ,
        execution_scope="contract_testing",
    )
    fresh = repository.load(ref, run_id="generic-n4-wire-identity")
    fresh_read = _generation_source_read_result(fresh)
    assert fresh_read is not None and fresh_read.value is fresh
    assert fresh_read.provenance.canon_read_status == "declared_bytes_conformant"
    assert fresh_read.provenance.source_materialization == "reader_materialized"
    assert fresh_read.provenance.producer_attestation_status == "not_established"
    assert fresh_read.provenance.selected_artifact_id == str(ref.artifact_id)
    actual_selected_profile = artifact_manifest_profile_sha256(repository.store.get_manifest(ref))
    assert ref.manifest_profile_sha256 is None
    assert fresh_read.provenance.selected_manifest_profile_sha256 == actual_selected_profile
    assert "_generation_source_read_provenance" not in fresh.model_dump(mode="python")
    assert fresh == type(fresh).model_validate(fresh.model_dump(mode="python"))
    with (
        patch.object(repository.store, "get_raw_manifest_bytes", return_value=b'{"canon":null}'),
        patch.object(
            repository.store,
            "verify",
            side_effect=AssertionError("typed verification preceded raw-profile parsing"),
        ) as verify,
    ):
        with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_invalid"):
            repository.load(ref, run_id="generic-n4-wire-identity")
        verify.assert_not_called()
    assert _canonical_model_content_hash(fresh.generation_result) == (
        _canonical_model_content_hash(result)
    )

    class WireEquivalentResult(n4.GenerationUnderAResult):
        pass

    same_wire_other_result_type = WireEquivalentResult.model_validate(
        result.model_dump(mode="json")
    )
    assert same_wire_other_result_type.model_dump(mode="json") == result.model_dump(mode="json")
    assert same_wire_other_result_type != result
    assert _canonical_model_content_hash(same_wire_other_result_type) == (
        _canonical_model_content_hash(result)
    )

    class WireEquivalentProblem(type(problem)):
        pass

    same_wire_other_problem_type = WireEquivalentProblem.model_validate(
        problem.model_dump(mode="json")
    )
    assert same_wire_other_problem_type.model_dump(mode="json") == problem.model_dump(mode="json")
    assert same_wire_other_problem_type != problem
    assert _canonical_model_content_hash(same_wire_other_problem_type) == (
        _canonical_model_content_hash(problem)
    )

    class WireEquivalentContext(CycleSubstrateContext):
        pass

    same_wire_other_context = WireEquivalentContext.model_validate(context.model_dump(mode="json"))
    assert same_wire_other_context != context
    _require_unavailable_candidate_credal_source(
        fresh, problem=same_wire_other_problem_type, context=same_wire_other_context
    )

    altered_result_payload = same_wire_other_result_type.model_dump(mode="python")
    altered_result_payload["design_problem_ref"] = "sha256:" + "f" * 64
    altered_result = WireEquivalentResult.model_validate(altered_result_payload)
    assert _canonical_model_content_hash(altered_result) != (_canonical_model_content_hash(result))

    problem_payload = problem.model_dump(mode="python")
    problem_payload["nl_provenance"]["source_context"] = {
        **(problem_payload["nl_provenance"].get("source_context") or {}),
        "captured_at": "2026-10-11T10:00:00+00:00",
    }
    captured_problem = type(problem).model_validate(problem_payload)
    assert gy_content_hash(problem.model_dump(mode="json")) == gy_content_hash(
        captured_problem.model_dump(mode="json")
    )
    assert _source_content_hash(problem.model_dump(mode="python")) != (
        _source_content_hash(captured_problem.model_dump(mode="python"))
    )
    assert _canonical_model_content_hash(captured_problem) != (
        _canonical_model_content_hash(problem)
    )
    with pytest.raises(
        ValueError, match="candidate_credal_source_attempt_source_not_terminal_or_absent"
    ):
        _require_unavailable_candidate_credal_source(
            fresh, problem=captured_problem, context=context
        )

    context = _cycle_context(design_problem_ref=gy_content_hash(problem.model_dump(mode="json")))
    context_payload = context.model_dump(mode="python", exclude={"content_hash"})
    context_payload["source_pack_content_hash"] = "sha256:" + "e" * 64
    context_payload["content_hash"] = cycle_substrate_context_content_hash(context_payload)
    changed_context = CycleSubstrateContext.model_validate(context_payload)
    assert _canonical_model_content_hash(changed_context) != (
        _canonical_model_content_hash(context)
    )
    with pytest.raises(
        ValueError, match="candidate_credal_source_attempt_source_not_terminal_or_absent"
    ):
        _require_unavailable_candidate_credal_source(
            fresh, problem=problem, context=changed_context
        )

    purpose_changed_context = changed_context.model_copy(
        update={"authority_purpose": "publication"}
    )
    assert _canonical_model_content_hash(purpose_changed_context) != (
        _canonical_model_content_hash(changed_context)
    )
    with pytest.raises(ValidationError):
        CycleSubstrateContext.model_validate(purpose_changed_context.model_dump(mode="python"))


@pytest.mark.asyncio
async def test_candidate_proposal_repository_replays_exact_tenant_binding(tmp_path):
    """N4 proposal persistence uses the supplied artifact store and checks its served scope."""
    recording = _recording_with_successful_first_response()
    model_id = str(recording["model_id"])
    problem = contract._design_problem(recording)
    problem = problem.model_copy(
        update={
            "nl_provenance": problem.nl_provenance.model_copy(
                update={
                    "source_context": {
                        **problem.nl_provenance.source_context,
                        "tenant_id": "tenant-a",
                        "cell_id": "cell-a",
                        "job_id": "job-n4-candidate",
                        "run_id": "run-n4-candidate",
                    }
                }
            )
        }
    )
    proposal = await n4.generate_design_candidate_proposal_under_a(
        problem,
        model_id=model_id,
        llm_client=RecordedClientWithCatalog(recording, model_ids=[model_id]),
        repo_root=REPO_ROOT,
    )
    repository = GenerationSourceRepository(FileSystemCAS(tmp_path / "tenant-cas"))

    proposal_ref = repository.persist_candidate_proposal(
        job_id="job-n4-candidate",
        run_id="run-n4-candidate",
        tenant_id="tenant-a",
        cell_id="cell-a",
        raw_request=problem.nl_provenance.raw_request,
        problem=problem,
        proposal=proposal,
    )
    assert proposal_ref.kind == "runtime.quality.n4_candidate_proposal"
    assert proposal_ref.media_type == "application/json"
    loaded = repository.load_candidate_proposal(
        proposal_ref,
        job_id="job-n4-candidate",
        run_id="run-n4-candidate",
        tenant_id="tenant-a",
        cell_id="cell-a",
        raw_request=problem.nl_provenance.raw_request,
    )

    loaded_read = _generation_source_read_result(loaded)
    assert loaded_read is not None and loaded_read.value is loaded
    assert loaded_read.provenance.canon_read_status == "declared_bytes_conformant"
    assert loaded_read.provenance.source_materialization == "reader_materialized"
    assert loaded_read.provenance.producer_attestation_status == "not_established"
    assert loaded_read.provenance.selected_artifact_id == str(proposal_ref.artifact_id)
    assert loaded == type(loaded).model_validate(loaded.model_dump(mode="python"))
    with (
        patch.object(repository.store, "get_raw_manifest_bytes", return_value=b'{"canon":null}'),
        patch.object(
            repository.store,
            "verify",
            side_effect=AssertionError("typed verification preceded raw-profile parsing"),
        ) as verify,
    ):
        with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_invalid"):
            repository.load_candidate_proposal(
                proposal_ref,
                job_id="job-n4-candidate",
                run_id="run-n4-candidate",
                tenant_id="tenant-a",
                cell_id="cell-a",
                raw_request=problem.nl_provenance.raw_request,
            )
        verify.assert_not_called()
    assert loaded.proposal == proposal
    assert loaded.execution_band == "candidate"
    assert loaded.limitation_code == "cycle_substrate_context_unavailable"

    from polisyos.core import canon
    from polisyos.runtime.quality.generation_source import (
        _SOURCE_CANON,
        N4CandidateProposalRecordV3,
        N4CandidateProposalSimulationDisposition,
        _n4_candidate_proposal_v3_write_options,
    )

    v3_body = repository.store.get_bytes(proposal_ref)
    assert type(loaded) is N4CandidateProposalRecordV3
    assert v3_body == canon.to_canonical_bytes(loaded, _SOURCE_CANON)
    proposal_manifest = repository.store.get_manifest(proposal_ref.artifact_id)
    assert proposal_manifest.tenant_context is not None
    assert proposal_manifest.tenant_context.tenant_id == "tenant-a"
    assert proposal_manifest.tenant_context.cell_id == "cell-a"
    assert proposal_manifest.same_input_closure is not None
    assert proposal_manifest.same_input_closure.status == "candidate_only"
    assert proposal_manifest.same_input_closure.run_id == "run-n4-candidate"
    assert proposal_manifest.same_input_closure.job_id == "job-n4-candidate"
    simulation_ref = repository.persist_candidate_proposal(
        job_id="job-n4-candidate",
        run_id="run-n4-candidate",
        tenant_id="tenant-a",
        cell_id="cell-a",
        raw_request=problem.nl_provenance.raw_request,
        problem=problem,
        proposal=proposal,
        simulation_disposition=N4CandidateProposalSimulationDisposition(),
    )
    simulation_record = repository.load_candidate_proposal_for_served_job(
        simulation_ref,
        job_id="job-n4-candidate",
        run_id="run-n4-candidate",
        tenant_id="tenant-a",
        cell_id="cell-a",
        raw_request=problem.nl_provenance.raw_request,
    )
    assert type(simulation_record) is N4CandidateProposalRecordV3
    assert repository.store.get_bytes(simulation_ref) == canon.to_canonical_bytes(
        simulation_record, _SOURCE_CANON
    )
    assert simulation_record.schema_version.endswith(".v3")
    assert simulation_record.simulation_disposition.execution_intent_band == (
        "simulate_only_attempt"
    )
    assert simulation_record.simulation_disposition.status == "simulation_unavailable"
    assert simulation_record.simulation_disposition.reason_code == (
        "cycle_substrate_context_not_established"
    )
    assert simulation_record.n5_status == simulation_record.s8_status == "not_run"
    simulation_read = _generation_source_read_result(simulation_record)
    assert simulation_read is not None and simulation_read.value is simulation_record
    assert simulation_read.provenance.canon_read_status == "declared_bytes_conformant"
    assert simulation_read.provenance.source_materialization == "reader_materialized"
    assert simulation_read.provenance.producer_attestation_status == "not_established"
    assert simulation_read.provenance.selected_artifact_id == str(simulation_ref.artifact_id)
    assert simulation_record == type(simulation_record).model_validate(
        simulation_record.model_dump(mode="python")
    )

    altered = simulation_record.model_dump(mode="python")
    altered["job_id"] = "job-other"
    forged_ref = repository.store.put_bytes(
        canon.to_canonical_bytes(altered, _SOURCE_CANON),
        _n4_candidate_proposal_v3_write_options(simulation_record),
    )
    with pytest.raises(ValueError, match="n4_candidate_proposal_content_hash_mismatch"):
        repository.load_candidate_proposal_for_served_job(
            forged_ref,
            job_id="job-n4-candidate",
            run_id="run-n4-candidate",
            tenant_id="tenant-a",
            cell_id="cell-a",
            raw_request=problem.nl_provenance.raw_request,
        )

    with pytest.raises(ValueError, match="tenant"):
        repository.load_candidate_proposal(
            proposal_ref,
            job_id="job-n4-candidate",
            run_id="run-n4-candidate",
            tenant_id="tenant-b",
            cell_id="cell-a",
            raw_request=problem.nl_provenance.raw_request,
        )


@pytest.mark.asyncio
async def test_candidate_proposal_writer_rejects_inner_scope_from_another_owner(tmp_path):
    """The current N4 writer binds inner DesignProblem scope to its outer owner."""
    from polisyos.pdc import gy_content_hash

    recording = _recording_with_successful_first_response()
    model_id = str(recording["model_id"])
    problem = contract._design_problem(recording)
    problem = problem.model_copy(
        update={
            "nl_provenance": problem.nl_provenance.model_copy(
                update={
                    "source_context": {
                        "tenant_id": "tenant-foreign",
                        "cell_id": "cell-a",
                        "job_id": "job-n4-candidate",
                        "run_id": "run-n4-candidate",
                    }
                }
            )
        }
    )
    proposal = await n4.generate_design_candidate_proposal_under_a(
        problem,
        model_id=model_id,
        llm_client=RecordedClientWithCatalog(recording, model_ids=[model_id]),
        repo_root=REPO_ROOT,
    )
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    proposal = proposal.model_copy(update={"design_problem_ref": problem_ref})
    repository = GenerationSourceRepository(FileSystemCAS(tmp_path / "tenant-cas"))

    with pytest.raises(ValueError, match="n4_candidate_proposal_tenant_scope_binding_mismatch"):
        repository.persist_candidate_proposal(
            job_id="job-n4-candidate",
            run_id="run-n4-candidate",
            tenant_id="tenant-a",
            cell_id="cell-a",
            raw_request=problem.nl_provenance.raw_request,
            problem=problem,
            proposal=proposal,
        )


@pytest.mark.asyncio
async def test_served_candidate_reader_reconciles_inner_scope_without_changing_v1_replay(
    tmp_path,
):
    """Historical v1 bytes decode, while served admission reconciles their inner owner IDs."""
    from polisyos.core import canon
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.generation_source import (
        _SOURCE_CANON,
        N4CandidateProposalRecord,
        _n4_candidate_proposal_write_options,
        _source_content_hash,
    )

    recording = _recording_with_successful_first_response()
    model_id = str(recording["model_id"])
    problem = contract._design_problem(recording)
    owner_context = {
        "tenant_id": "tenant-a",
        "cell_id": "cell-a",
        "job_id": "job-n4-candidate",
        "run_id": "run-n4-candidate",
    }
    problem = problem.model_copy(
        update={
            "nl_provenance": problem.nl_provenance.model_copy(
                update={"source_context": owner_context}
            )
        }
    )
    proposal = await n4.generate_design_candidate_proposal_under_a(
        problem,
        model_id=model_id,
        llm_client=RecordedClientWithCatalog(recording, model_ids=[model_id]),
        repo_root=REPO_ROOT,
    )
    repository = GenerationSourceRepository(FileSystemCAS(tmp_path / "tenant-cas"))
    valid_ref = repository.persist_candidate_proposal(
        job_id=owner_context["job_id"],
        run_id=owner_context["run_id"],
        tenant_id=owner_context["tenant_id"],
        cell_id=owner_context["cell_id"],
        raw_request=problem.nl_provenance.raw_request,
        problem=problem,
        proposal=proposal,
    )
    valid_record = repository.load_candidate_proposal(
        valid_ref,
        job_id=owner_context["job_id"],
        run_id=owner_context["run_id"],
        tenant_id=owner_context["tenant_id"],
        cell_id=owner_context["cell_id"],
        raw_request=problem.nl_provenance.raw_request,
    )

    foreign_problem = valid_record.problem.model_copy(
        update={
            "nl_provenance": valid_record.problem.nl_provenance.model_copy(
                update={
                    "source_context": {
                        **valid_record.problem.nl_provenance.source_context,
                        "tenant_id": "tenant-foreign",
                    }
                }
            )
        }
    )
    foreign_problem_ref = gy_content_hash(foreign_problem.model_dump(mode="json"))
    foreign_proposal = valid_record.proposal.model_copy(
        update={"design_problem_ref": foreign_problem_ref}
    )
    historical_payload = {
        name: value
        for name, value in valid_record.model_dump(mode="python", exclude={"content_hash"}).items()
        if name in N4CandidateProposalRecord.model_fields
    }
    historical_payload["schema_version"] = (
        "policyos.runtime.quality.n4_candidate_proposal_record.v1"
    )
    historical_payload["problem"] = foreign_problem
    historical_payload["proposal"] = foreign_proposal
    historical_payload["design_problem_ref"] = foreign_problem_ref
    historical_payload["content_hash"] = _source_content_hash(historical_payload)
    historical_record = N4CandidateProposalRecord.model_validate(historical_payload)
    historical_ref = repository.store.put_bytes(
        canon.to_canonical_bytes(historical_record, _SOURCE_CANON),
        _n4_candidate_proposal_write_options(),
    )

    decoded = repository.load_candidate_proposal(
        historical_ref,
        job_id=owner_context["job_id"],
        run_id=owner_context["run_id"],
        tenant_id=owner_context["tenant_id"],
        cell_id=owner_context["cell_id"],
        raw_request=problem.nl_provenance.raw_request,
    )
    assert decoded == historical_record
    decoded_read = _generation_source_read_result(decoded)
    assert decoded_read is not None and decoded_read.value is decoded
    assert decoded_read.provenance.canon_read_status == "declared_bytes_conformant"
    assert decoded_read.provenance.source_materialization == "reader_materialized"
    assert decoded_read.provenance.producer_attestation_status == "not_established"
    assert decoded_read.provenance.selected_artifact_id == str(historical_ref.artifact_id)
    assert decoded == historical_record
    assert decoded.schema_version == "policyos.runtime.quality.n4_candidate_proposal_record.v1"
    with pytest.raises(ValueError, match="n4_candidate_proposal_tenant_scope_binding_mismatch"):
        repository.load_candidate_proposal_for_served_job(
            historical_ref,
            job_id=owner_context["job_id"],
            run_id=owner_context["run_id"],
            tenant_id=owner_context["tenant_id"],
            cell_id=owner_context["cell_id"],
            raw_request=problem.nl_provenance.raw_request,
        )


def test_synthetic_cg2_contract_mechanism_remains_non_promotable(tmp_path):
    """Law-free structural mechanics may bind only in the synthetic contract lane."""
    from polisyos.runtime.quality.grounding_bind import (
        GroundingBindGate,
        resolve_grounding_decision_promotability,
        resolve_grounding_decision_promotability_for_contract_testing,
    )
    from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine
    from polisyos.runtime.quality.promotion_sequence import (
        _cg2_resolution_is_contract_lane_bind,
    )
    from tests.unit.runtime.quality.test_grounding_bind import (
        _assert_structural_contract_bind,
        _pure_synonym_probe,
        _reference,
    )

    # Explicitly test lever mechanics; this fixture asserts no legal correspondence.
    reference = _reference(include_legal_associations=False)
    engine = GroundingRelationEngine(reference)
    relation = engine.certificate_for(_pure_synonym_probe(engine), proposal_id="corr-synthetic")
    decision = GroundingBindGate.for_contract_testing(
        reference,
        calibration_seed_anchor=True,
    ).certificate_for(relation)
    mechanical = resolve_grounding_decision_promotability_for_contract_testing(decision, reference)
    actual = resolve_grounding_decision_promotability(decision, reference)

    # Retain the owner values before any assertion, including on a mechanical
    # refusal. The synthetic reason by itself does not establish a bind.
    import json

    diagnostic_path = tmp_path / "synthetic-cg2-owner-diagnostic.json"
    diagnostic_path.write_text(
        json.dumps(
            {
                "schema_version": "test.synthetic_cg2_owner_diagnostic.v1",
                "relation": relation.model_dump(mode="json"),
                "decision": decision.model_dump(mode="json"),
                "contract_resolution": mechanical.model_dump(mode="json"),
                "production_resolution": actual.model_dump(mode="json"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    _assert_structural_contract_bind(reference, engine, relation, decision)
    assert decision.synthetic is True
    assert mechanical.reason == "synthetic_input_cannot_grant_authority"
    assert not mechanical.promotable
    assert not actual.promotable
    assert _cg2_resolution_is_contract_lane_bind(mechanical), diagnostic_path
    assert not _cg2_resolution_is_contract_lane_bind(actual)
    for mutation in (
        {"owned_anchor_id": None},
        {"store_anchor_content_hash": None},
        {"store_anchor_content_hash": "sha256:" + "f" * 64},
        {"certificate_promotable_claim": True},
        {"promotable": True},
        {"authority_scope": "production"},
        {"store_authority_scope": "production"},
    ):
        assert not _cg2_resolution_is_contract_lane_bind(mechanical.model_copy(update=mutation)), (
            mutation
        )


def _load_recorded_n4_world(store_root, artifact_id, expected_record_hash):
    """Read one existing, selected WMR through the read-only CAS owner."""
    import hashlib

    from polisyos.core import artifacts
    from polisyos.runtime.quality.world_model_record import load_world_model_record

    store = artifacts.FileSystemCAS.open_existing_read_only(store_root)
    if not store.verify(artifact_id).ok:
        raise ValueError("recorded_n4_world_artifact_verify_failed")
    if "sha256:" + hashlib.sha256(store.get_bytes(artifact_id)).hexdigest() != artifact_id:
        raise ValueError("recorded_n4_world_artifact_hash_mismatch")
    world = load_world_model_record(store, artifact_id)
    if world.content_hash != expected_record_hash:
        raise ValueError("recorded_n4_world_logical_hash_mismatch")
    return store, world


def test_recorded_n4_world_reader_never_writes_selected_store(tmp_path):
    """A local owner-produced WMR is verified without creating or modifying its source CAS."""
    import hashlib

    from polisyos.core.artifacts import ArtifactReadOnlyUnavailableError
    from tests._helpers.world_model_record import _build_record

    store, built, _, _ = _build_record(tmp_path / "owner")
    artifact_id = str(built.record_ref.artifact_id)

    def inventory():
        return {
            path.relative_to(store.root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in store.root.rglob("*")
            if path.is_file()
        }

    before = inventory()
    reader, loaded = _load_recorded_n4_world(store.root, artifact_id, built.record.content_hash)
    assert loaded == built.record
    assert not hasattr(reader, "put_bytes")
    with pytest.raises(ValueError, match="recorded_n4_world_logical_hash_mismatch"):
        _load_recorded_n4_world(store.root, artifact_id, "sha256:" + "0" * 64)
    assert inventory() == before
    missing = tmp_path / "missing-owner"
    with pytest.raises(ArtifactReadOnlyUnavailableError, match="cas_root_missing_or_invalid"):
        _load_recorded_n4_world(missing, artifact_id, built.record.content_hash)
    assert not missing.exists()


class _SyntheticSourceFixtureCatalog:
    """Controlled model catalog input; never evidence of external availability."""

    def __init__(self, model_ids: tuple[str, ...]) -> None:
        self.model_ids = model_ids
        self.calls: list[float | None] = []

    async def list_model_ids(self, *, timeout: float | None = None) -> list[str]:
        self.calls.append(timeout)
        return list(self.model_ids)


def _synthetic_source_preflight(*, model_id: str, model_ids: tuple[str, ...]):
    """Exercise the canonical preflight over an explicitly local synthetic catalog."""
    import asyncio

    catalog = _SyntheticSourceFixtureCatalog(model_ids)
    preflight = asyncio.run(n4.preflight_model_profile(catalog, model_id=model_id))
    assert catalog.calls == [10.0]
    return preflight


def _assemble_synthetic_source_result(
    problem, *, model_id, preflight, candidates, dispositions, root, calls
):
    """Reuse every canonical result owner without upgrading synthetic evidence."""
    problem_ref = n4.gy_content_hash(problem.model_dump(mode="json"))
    if preflight.status != "supported":
        return n4._terminal_result(
            design_problem_ref=problem_ref,
            model_id=model_id,
            preflight=preflight,
            status="preflight_rejected",
            reason=preflight.reason,
            organ="preflight",
            min_diverse_candidates=1,
            llm_calls=calls,
        )
    diversity = n4.measure_generation_diversity(
        candidates, min_required=1, dispositions=dispositions
    )
    if not diversity.diverse_enough:
        return n4.GenerationUnderAResult(
            status="generation_unavailable",
            design_problem_ref=problem_ref,
            model_id=model_id,
            preflight=preflight,
            degraded_artifacts=(
                n4.DegradedGenerationArtifact(
                    reason="insufficient_diverse_model_generated_candidates",
                    organ="diversity",
                    details=diversity.model_dump(mode="json"),
                ),
            ),
            diversity_report=diversity,
            llm_calls=calls,
            firewall_evidence=n4.default_firewall_evidence(),
            strangle_receipts=n4.design_generation_strangle_receipts(root),
        )
    try:
        rankings = n4.rank_shadow_candidates_with_graph_causal_surrogate(
            candidates, design_problem=problem, repo_root=root
        )
    except n4.DesignGenerationError as exc:
        return n4._terminal_result(
            design_problem_ref=problem_ref,
            model_id=model_id,
            preflight=preflight,
            status="generation_unavailable",
            reason=str(exc),
            organ="surrogate",
            min_diverse_candidates=1,
            llm_calls=calls,
        )
    return n4.GenerationUnderAResult(
        status="generated",
        design_problem_ref=problem_ref,
        model_id=model_id,
        preflight=preflight,
        candidates=candidates,
        grounding_dispositions=dispositions,
        grounding_disposition_summary=n4._grounding_disposition_summary(dispositions),
        diversity_report=diversity,
        surrogate_rankings=rankings,
        llm_calls=calls,
        firewall_evidence=n4.default_firewall_evidence(),
        strangle_receipts=n4.design_generation_strangle_receipts(root),
    )


@pytest.fixture(scope="module")
def actual_n4_source():
    """Use the actual composed WMR/L6 owners and explicitly synthetic relation inputs."""
    import os
    from dataclasses import replace
    from decimal import Decimal
    from pathlib import Path
    from typing import Any

    from polisyos.core import artifacts
    from polisyos.runtime.quality.credal_reference import _component_versions, _reference_hash
    from polisyos.runtime.quality.cycle_substrate import build_cycle_substrate_context
    from polisyos.runtime.quality.grounding_relation import (
        GroundingRelationCertificate,
        GroundingRelationEngine,
    )
    from polisyos.runtime.quality.intervention_substrate import (
        load_l6_intervention_substrate,
        production_composed_world_model_record,
    )
    from polisyos.runtime.quality.substrate_registry import load_substrate_registry
    from polisyos.runtime.quality.world_model_record import world_model_artifact_views
    from tests.unit.runtime.quality.test_design_generation import _llm_call
    from tests.unit.runtime.quality.test_grounding_bind import _reference

    root = Path(__file__).resolve().parents[4]
    pin = tuple(
        os.environ.get(key) for key in ("CORR_C_WORLD_CAS", "CORR_C_WORLD_REF", "CORR_C_WORLD_HASH")
    )
    if any(value is not None for value in pin):
        assert all(pin), "A replay pin must declare its store, artifact and logical record hash."
        store, world = _load_recorded_n4_world(root / pin[0], pin[1], pin[2])
    else:
        world = production_composed_world_model_record(root)
        store = artifacts.FileSystemCAS(root / ".tmp/gy-s-composed-wmr-cas")
    registry_view_ref = world_model_artifact_views(world).substrate_registry_ref
    assert registry_view_ref is not None
    registry = load_substrate_registry(store, registry_view_ref)
    problem = _test_design_problem()
    problem = problem.model_copy(
        update={
            "runtime_hints": {
                **problem.runtime_hints,
                "synthetic": True,
                "synthetic_model_catalog": {
                    "source": "fixture_local_not_external_availability",
                    "model_ids": ["synthetic-c2"],
                },
            }
        }
    )
    problem_ref = n4.gy_content_hash(problem.model_dump(mode="json"))
    l6_root = os.environ.get("CORR_C_L6_SOURCE_ROOT")
    l6_hash = os.environ.get("CORR_C_L6_SOURCE_HASH")
    if l6_root is not None or l6_hash is not None:
        assert l6_root and l6_hash, (
            "An L6 replay pin requires both its source root and bundle hash."
        )
        l6 = load_l6_intervention_substrate(root, source_owner_root=Path(l6_root))
        assert l6.content_hash == l6_hash, "The selected L6 bundle differs from its replay pin."
    else:
        l6 = load_l6_intervention_substrate(root)
    context = build_cycle_substrate_context(
        design_problem_ref=problem_ref,
        domain=problem.domain,
        substrate_registry=registry,
        selected_registry_entry_hashes=tuple(
            item.entry_content_hash for item in world.substrate_registry_ref.resolved_entries
        ),
        world_model_record=world,
        intervention_substrate=l6,
        candidate_levers=(),
        transport_context=None,
        source_pack_content_hash=None,
        substrate_input_content_hash=None,
    )
    reference = _reference()
    edges = {}
    for key, edge in reference.essential_edges.items():
        changed = replace(edge, provenance={**edge.provenance, "synthetic": True})
        edges[key] = changed.with_content_hash()
    versions = _component_versions(edges, world_model_record=world)
    reference_hash = _reference_hash(
        component_versions=versions,
        edge_index=edges,
        as_of=reference.as_of,
        schema_version=reference.schema_version,
    )
    reference = replace(
        reference,
        essential_edges=edges,
        component_versions=versions,
        reference_hash=reference_hash,
        reference_epoch="kref:" + reference_hash.removeprefix("sha256:")[:16],
    )
    intervention = _intervention("corr_synthetic_source").model_copy(
        update={
            "measurement_expectations": {"synthetic": True},
            "params": {
                "rate": Decimal("0.08"),
                "target_world_slot": "global.tax_rate",
                "sign": "decrease",
                "outcome_slots": ["government.balance"],
                "effect_path": ["tax_relief_rate", "global.tax_rate", "government.balance"],
                "estimand": "average_treatment_effect",
            },
        }
    )
    bundle = _bundle([intervention])

    class _RecordingGroundingRelationEngine(GroundingRelationEngine):
        def __init__(self, selected_reference: Any) -> None:
            super().__init__(selected_reference)
            self.owner_certificates: list[GroundingRelationCertificate] = []

        def certificate_for(
            self,
            proposal: Any,
            *,
            proposal_id: str | None = None,
            include_adversarial_countercandidates: bool = True,
        ) -> GroundingRelationCertificate:
            certificate = super().certificate_for(
                proposal,
                proposal_id=proposal_id,
                include_adversarial_countercandidates=include_adversarial_countercandidates,
            )
            self.owner_certificates.append(certificate)
            return certificate

    relation_engine = _RecordingGroundingRelationEngine(reference)
    capture = n4._N4SourceCapture()
    candidates, dispositions = n4._content_bound_candidates(
        design_problem=problem,
        design_problem_ref=problem_ref,
        bundle=bundle,
        model_id="synthetic-c2",
        draft_path="model_generated",
        formalizer_path="model_generated",
        critic_path="model_generated",
        critique_verdict="synthetic-mechanical-control",
        calls=(_llm_call(),),
        repo_root=root,
        world_model_record_ref=world.world_model_record_id,
        reference=reference,
        relation_engine=relation_engine,
        cycle_substrate_context=context,
        source_capture=capture,
    )

    def _cg1_owner_report(certificate: GroundingRelationCertificate) -> dict[str, Any]:
        return {
            "proposal_id": certificate.proposal_id,
            "certificate_id": certificate.certificate_id,
            "content_hash": certificate.content_hash,
            "selected_relation": certificate.selected_relation,
            "solver_status": certificate.solver_status,
            "solver_backend": certificate.cross_modal_witnesses.get("solver"),
            "unsat_core_if_any": certificate.unsat_core_if_any,
            "candidate_atom_ids": certificate.candidate_atom_ids,
            "known_space_coverage": certificate.relation_set.get("known_space_coverage", {}),
            "candidate_results": certificate.relation_set.get("candidate_results", ()),
            "proposal_signature": certificate.proposal_signature,
            "candidate_signatures": certificate.atom_signature_or_bundle,
            "axis_witnesses": [item.model_dump(mode="json") for item in certificate.axis_witnesses],
            "critical_contradictions": certificate.critical_contradictions,
            "unresolved_axes": certificate.unresolved_axes,
        }

    def _candidate_failure_diagnostic() -> str:
        certificates_by_hash = {
            certificate.content_hash: certificate
            for certificate in relation_engine.owner_certificates
        }
        owner_reports = [
            {
                "disposition_cg1_hash": disposition.certificate_chain.cg1_content_hash,
                "certificate": _cg1_owner_report(
                    certificates_by_hash[disposition.certificate_chain.cg1_content_hash]
                )
                if disposition.certificate_chain.cg1_content_hash in certificates_by_hash
                else None,
            }
            for disposition in dispositions
        ]
        return (
            "actual N4 fixture expected the existing CG1 owner to identify a shadow candidate; "
            "this direct _content_bound_candidates call does not run N4 model-profile preflight; "
            f"owner_bound_cg1={owner_reports!r}; "
            f"typed_dispositions="
            f"{[item.model_dump(mode='json') for item in dispositions]!r}"
        )

    assert candidates, _candidate_failure_diagnostic()
    preflight = _synthetic_source_preflight(model_id="synthetic-c2", model_ids=("synthetic-c2",))
    result = _assemble_synthetic_source_result(
        problem,
        model_id="synthetic-c2",
        preflight=preflight,
        candidates=candidates,
        dispositions=dispositions,
        root=root,
        calls=(_llm_call(),),
    )
    assert result.status == "generated", result.model_dump(mode="json")
    return problem, n4.DesignGenerationOrganRun(
        result=result,
        trinity_bundle=bundle,
        cycle_substrate_context=context,
        credal_reference=capture.reference,
        candidate_sources=tuple(capture.candidates),
    )


def test_actual_source_result_owners_preserve_synthetic_candidate_boundary(actual_n4_source):
    """The complete result carries owner-derived ranks without acquiring authority."""
    problem, organ = actual_n4_source
    result = organ.result
    assert problem.runtime_hints["synthetic_model_catalog"] == {
        "source": "fixture_local_not_external_availability",
        "model_ids": ["synthetic-c2"],
    }
    assert result.preflight.status == "supported"
    assert result.preflight.live_model_ids == ("synthetic-c2",)
    assert result.diversity_report == n4.measure_generation_diversity(
        result.candidates, min_required=1, dispositions=result.grounding_dispositions
    )
    assert {row.candidate_id for row in result.surrogate_rankings} == {
        candidate.candidate_id for candidate in result.candidates
    }
    assert len(result.surrogate_rankings) == len(result.candidates)
    assert all(not row.promotion_allowed for row in result.surrogate_rankings)
    assert all(row.trust_level != "certified" for row in result.surrogate_rankings)
    assert all(candidate.status == "candidate_unverified" for candidate in result.candidates)
    assert result.firewall_evidence
    assert all(row.blocked_from_authority for row in result.firewall_evidence)
    assert n4.GenerationUnderAResult.model_validate(result.model_dump(mode="python")) == result


def test_actual_source_result_rejects_removed_canonical_ranking(actual_n4_source, monkeypatch):
    """Keeping generated markers cannot replace coverage from the actual ranker."""
    from pathlib import Path

    problem, organ = actual_n4_source
    result = organ.result
    monkeypatch.setattr(
        n4, "rank_shadow_candidates_with_graph_causal_surrogate", lambda *a, **k: ()
    )
    with pytest.raises(ValidationError, match="surrogate_ranking_coverage_incomplete"):
        _assemble_synthetic_source_result(
            problem,
            model_id=result.model_id,
            preflight=result.preflight,
            candidates=result.candidates,
            dispositions=result.grounding_dispositions,
            root=Path(__file__).resolve().parents[4],
            calls=result.llm_calls,
        )


def test_actual_source_result_refuses_absent_synthetic_catalog_model(actual_n4_source):
    """Real preflight refusal cannot be replaced by a supported-status constructor."""
    from pathlib import Path

    problem, organ = actual_n4_source
    preflight = _synthetic_source_preflight(model_id=organ.result.model_id, model_ids=())
    assert preflight.status == "unsupported"
    refused = _assemble_synthetic_source_result(
        problem,
        model_id=organ.result.model_id,
        preflight=preflight,
        candidates=organ.result.candidates,
        dispositions=organ.result.grounding_dispositions,
        root=Path(__file__).resolve().parents[4],
        calls=organ.result.llm_calls,
    )
    assert refused.status == "preflight_rejected"
    assert refused.candidates == refused.grounding_dispositions == ()
    assert refused.surrogate_rankings == ()
    assert refused.preflight is preflight
    assert refused.degraded_artifacts[0].organ == "preflight"


def _source_summary(organ, cycle=0):
    from polisyos.runtime.quality.generation_cycle import CandidateSummary

    candidate = organ.result.candidates[0]
    return CandidateSummary(
        candidate_id=candidate.candidate_id,
        content_hash=candidate.atom.content_hash,
        cycle_index=cycle,
        proxy_score=0.0,
        voi_estimate=0.0,
        grounding_status="grounding_failed",
        grounding_score=0.0,
        current_valid=False,
        front="research",
        high_proxy=False,
        low_grounding=True,
    )


def _produce_source_variant(problem, original, *, bundle=None, run_budget=None):
    """Run the actual N4 source emitter for changed data or an actual N6 budget handle."""
    from dataclasses import replace
    from pathlib import Path

    from tests.unit.runtime.quality.test_design_generation import _llm_call

    bundle = original.trinity_bundle if bundle is None else bundle
    capture = n4._N4SourceCapture()
    candidates, dispositions = n4._content_bound_candidates(
        design_problem=problem,
        design_problem_ref=original.result.design_problem_ref,
        bundle=bundle,
        model_id=original.result.model_id,
        draft_path="model_generated",
        formalizer_path="model_generated",
        critic_path="model_generated",
        critique_verdict="synthetic-mechanical-control",
        calls=(_llm_call(),),
        repo_root=Path(__file__).resolve().parents[4],
        world_model_record_ref=original.cycle_substrate_context.world_model_record.world_model_record_id,
        reference=original.credal_reference,
        cycle_substrate_context=original.cycle_substrate_context,
        grounding_run_budget=run_budget,
        source_capture=capture,
    )
    assert candidates, [(item.disposition, item.rejected_cause) for item in dispositions]
    result = _assemble_synthetic_source_result(
        problem,
        model_id=original.result.model_id,
        preflight=original.result.preflight,
        candidates=candidates,
        dispositions=dispositions,
        root=Path(__file__).resolve().parents[4],
        calls=(_llm_call(),),
    )
    assert result.status == "generated", result.model_dump(mode="json")
    return replace(
        original,
        result=result,
        trinity_bundle=bundle,
        credal_reference=capture.reference,
        candidate_sources=tuple(capture.candidates),
    )


def test_actual_source_roundtrip_and_repeat_identity(actual_n4_source, tmp_path):
    """The same exact owner source in two cycles is idempotent, not ambiguous."""
    from polisyos.core import artifacts
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    problem, organ = actual_n4_source
    repository = GenerationSourceRepository(artifacts.FileSystemCAS(tmp_path / "cas"))
    run_id = "generation_cycle_" + organ.result.design_problem_ref.removeprefix("sha256:")[:16]
    refs = tuple(
        repository.persist(run_id=run_id, cycle_index=i, problem=problem, organ=organ)
        for i in range(2)
    )
    for ref in refs:
        persisted = repository.load(ref, run_id=run_id)
        assert persisted.synthetic is True
        assert persisted.generation_result == organ.result
        assert persisted.trinity_bundle == organ.trinity_bundle
    resolved = repository.resolve(
        refs=refs, run_id=run_id, summary=_source_summary(organ), problem=problem
    )
    assert resolved.status == "resolved", resolved.code
    assert (
        resolved.context["effect_obligation_writer_input"].intervention_atom
        == organ.result.candidates[0].atom
    )
    identity = (
        organ.result.design_problem_ref,
        organ.result.candidates[0].candidate_id,
        organ.result.candidates[0].atom.content_hash,
    )
    receipt = repository.preservation_receipt(
        run_id=run_id, refs=refs, expected=(identity, identity)
    )
    assert receipt.status == "strangled", receipt.issues


def _stub_repeated_occurrence_repository(monkeypatch, problem):
    """Model replayed handoffs with one candidate identity at two source occurrences."""
    from types import SimpleNamespace

    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality import generation_source
    from polisyos.runtime.quality.generation_cycle import CandidateSummary
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    candidate_id = "candidate-repeated-across-cycles"
    atom_hash = "sha256:" + "1" * 64
    identity = (gy_content_hash(problem.model_dump(mode="json")), candidate_id, atom_hash)
    context = SimpleNamespace(world_model_record=object(), intervention_substrate=None)
    intervention = SimpleNamespace(intervention_id="intervention-repeated", params={})
    bundle = SimpleNamespace(
        policy_spec=SimpleNamespace(interventions=(intervention,)),
    )
    handoffs = {
        f"handoff-cycle-{cycle_index}": SimpleNamespace(
            cycle_index=cycle_index,
            identities=lambda: (identity,),
            source_identity_hash=lambda: "sha256:" + "2" * 64,
            candidate_sources=(
                SimpleNamespace(
                    candidate_id=candidate_id,
                    intervention_id="intervention-repeated",
                    grounding_decision_certificate=object(),
                ),
            ),
            generation_result=SimpleNamespace(
                candidates=(SimpleNamespace(candidate_id=candidate_id, atom=object()),),
            ),
            cycle_substrate_context=context,
            reference=lambda: None,
            trinity_bundle=bundle,
        )
        for cycle_index in (0, 1)
    }
    repository = GenerationSourceRepository(store=object())
    monkeypatch.setattr(repository, "load", lambda ref, *, run_id: handoffs[ref])
    monkeypatch.setattr(
        generation_source,
        "revalidate_cycle_substrate_context",
        lambda _context: context,
    )
    monkeypatch.setattr(n4, "_candidate_parameter_value", lambda *_args, **_kwargs: None)

    def summary(cycle_index):
        return CandidateSummary(
            candidate_id=candidate_id,
            content_hash=atom_hash,
            cycle_index=cycle_index,
            proxy_score=0.0,
            voi_estimate=0.0,
            grounding_status="grounding_failed",
            grounding_score=0.0,
            current_valid=False,
            front="research",
            high_proxy=False,
            low_grounding=True,
        )

    return repository, handoffs, summary


def test_repeated_source_occurrence_preserves_same_occurrence_control(monkeypatch):
    """A cycle-zero summary resolves to the cycle-zero source returned by replay."""
    problem = _test_design_problem()
    repository, handoffs, summary = _stub_repeated_occurrence_repository(monkeypatch, problem)

    resolved = repository.resolve(
        refs=tuple(handoffs),
        run_id="run-with-repeated-source",
        summary=summary(0),
        problem=problem,
    )

    assert resolved.status == "resolved", resolved.code
    assert resolved.source_ref == "handoff-cycle-0"
    assert handoffs[resolved.source_ref].cycle_index == 0


def test_repeated_candidate_resolves_requested_later_cycle_occurrence(monkeypatch):
    """The resolver selects cycle one when identity-equivalent sources occur at 0 and 1."""
    problem = _test_design_problem()
    repository, handoffs, summary = _stub_repeated_occurrence_repository(monkeypatch, problem)

    resolved = repository.resolve(
        refs=tuple(handoffs),
        run_id="run-with-repeated-source",
        summary=summary(1),
        problem=problem,
    )

    assert resolved.status == "resolved", resolved.code
    assert resolved.source_ref == "handoff-cycle-1"
    assert handoffs[resolved.source_ref].cycle_index == 1


def test_wrong_source_occurrence_cannot_satisfy_later_cycle_summary(monkeypatch):
    """A matching candidate from cycle zero cannot stand in for missing cycle one."""
    problem = _test_design_problem()
    repository, _handoffs, summary = _stub_repeated_occurrence_repository(monkeypatch, problem)

    resolved = repository.resolve(
        refs=("handoff-cycle-0",),
        run_id="run-with-repeated-source",
        summary=summary(1),
        problem=problem,
    )

    assert resolved.status == "not_established"
    assert resolved.code == "source_occurrence_missing"
    assert not resolved.context


def test_contract_scope_marks_each_persisted_capsule(tmp_path):
    """Explicit synthetic execution marks the new artifact even with unknown old inputs."""
    from polisyos.core import artifacts
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    problem = _test_design_problem()
    result = n4.GenerationUnderAResult(
        status="generation_unavailable",
        design_problem_ref=n4.gy_content_hash(problem.model_dump(mode="json")),
        model_id="synthetic-c2",
        preflight=n4.ModelProfilePreflight(status="gateway_unavailable", model_id="synthetic-c2"),
        diversity_report=n4.GenerationDiversityReport(
            min_required=1, candidate_count=0, unique_diversity_key_count=0
        ),
    )
    repository = GenerationSourceRepository(artifacts.FileSystemCAS(tmp_path / "cas"))
    ref = repository.persist(
        run_id="synthetic-scope",
        cycle_index=0,
        problem=problem,
        organ=result.as_organ_run(),
        execution_scope="contract_testing",
    )
    assert repository.load(ref, run_id="synthetic-scope").synthetic is True


def test_candidate_n4_source_roundtrips_only_under_its_job_scope(tmp_path):
    """The persisted N4 source view is bound to the served job and tenant scope."""
    from polisyos.core import artifacts
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    problem = _test_design_problem()
    result = n4.GenerationUnderAResult(
        status="generation_unavailable",
        design_problem_ref=n4.gy_content_hash(problem.model_dump(mode="json")),
        model_id="synthetic-scoped-source",
        preflight=n4.ModelProfilePreflight(
            status="gateway_unavailable", model_id="synthetic-scoped-source"
        ),
        diversity_report=n4.GenerationDiversityReport(
            min_required=1, candidate_count=0, unique_diversity_key_count=0
        ),
    )
    repository = GenerationSourceRepository(artifacts.FileSystemCAS(tmp_path / "cas"))
    ref = repository.persist_ref(
        run_id="scoped-run",
        cycle_index=0,
        problem=problem,
        organ=result.as_organ_run(),
        execution_scope="contract_testing",
        job_id="scoped-job",
        tenant_id="tenant-a",
        cell_id="cell-a",
    )

    restored = repository.load(
        ref,
        run_id="scoped-run",
        expected_job_id="scoped-job",
        expected_tenant_id="tenant-a",
        expected_cell_id="cell-a",
    )
    assert restored.generation_result == result
    for wrong_scope in (
        {
            "expected_job_id": "foreign-job",
            "expected_tenant_id": "tenant-a",
            "expected_cell_id": "cell-a",
        },
        {
            "expected_job_id": "scoped-job",
            "expected_tenant_id": "tenant-b",
            "expected_cell_id": "cell-a",
        },
        {
            "expected_job_id": "scoped-job",
            "expected_tenant_id": "tenant-a",
            "expected_cell_id": "cell-b",
        },
    ):
        with pytest.raises(ValueError, match="generation_source_owner_profile_mismatch"):
            repository.load(ref, run_id="scoped-run", **wrong_scope)


def test_source_replay_requires_actual_persistence_owner_profile(tmp_path):
    """Valid source bytes under another persistence profile cannot claim N4 custody."""
    from dataclasses import replace

    from polisyos.core import artifacts
    from polisyos.runtime.quality.generation_source import (
        GenerationSourceRepository,
        _source_write_options,
    )

    problem = _test_design_problem()
    result = n4.GenerationUnderAResult(
        status="generation_unavailable",
        design_problem_ref=n4.gy_content_hash(problem.model_dump(mode="json")),
        model_id="synthetic-owner-profile",
        preflight=n4.ModelProfilePreflight(
            status="gateway_unavailable", model_id="synthetic-owner-profile"
        ),
        diversity_report=n4.GenerationDiversityReport(
            min_required=1, candidate_count=0, unique_diversity_key_count=0
        ),
    )
    store = artifacts.FileSystemCAS(tmp_path / "original")
    repository = GenerationSourceRepository(store)
    ref = repository.persist(
        run_id="synthetic-owner-profile",
        cycle_index=0,
        problem=problem,
        organ=result.as_organ_run(),
        execution_scope="contract_testing",
    )
    manifest = store.get_manifest(ref)
    body = store.get_bytes(ref)
    assert store.verify(ref).ok
    assert repository.load(ref, run_id="synthetic-owner-profile").synthetic is True
    options = _source_write_options()
    variants = {
        "kind": {"kind": "runtime.synthetic_other_source"},
        "media": {"media_type": "application/octet-stream"},
        "schema_name": {
            "schema": manifest.artifact_schema.model_copy(update={"name": "synthetic.other.v1"})
        },
        "schema_version": {
            "schema": manifest.artifact_schema.model_copy(update={"version": "0.0"})
        },
        "producer": {
            "producer": manifest.producer.model_copy(update={"component": "synthetic.other"})
        },
        "producer_version": {"producer": manifest.producer.model_copy(update={"version": "0.0"})},
        "producer_absent": {"producer": None},
    }
    for label, mutation in variants.items():
        other = artifacts.FileSystemCAS(tmp_path / label)
        observed_ref = other.put_bytes(
            body,
            replace(options, **mutation),
            return_selected_profile=True,
        )
        assert str(observed_ref.artifact_id) == ref
        assert other.get_bytes(ref) == body
        assert other.verify(
            observed_ref
        ).ok  # Byte integrity alone is insufficient owner provenance.
        assert observed_ref.manifest_profile_sha256 == (
            artifacts.artifact_manifest_profile_sha256(other.get_manifest(observed_ref))
        )
        with pytest.raises(ValueError, match="generation_source_owner_profile_mismatch"):
            GenerationSourceRepository(other).load(observed_ref, run_id="synthetic-owner-profile")


def test_typed_source_reference_roundtrips_v1_bytes_without_changing_string_api(tmp_path):
    """The source owner retains its exact CAS view while v1 history stays unchanged."""
    import hashlib
    from dataclasses import replace

    from polisyos.core import canon
    from polisyos.core.artifacts import ArtifactWriteOptions, artifact_manifest_profile_sha256
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.artifacts.ownership import ArtifactOwnershipError
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.quality.generation_source import (
        _SOURCE_CANON,
        _source_write_options,
    )

    problem = _test_design_problem()
    result = n4.GenerationUnderAResult(
        status="generation_unavailable",
        design_problem_ref=n4.gy_content_hash(problem.model_dump(mode="json")),
        model_id="synthetic-typed-source-ref",
        preflight=n4.ModelProfilePreflight(
            status="gateway_unavailable", model_id="synthetic-typed-source-ref"
        ),
        diversity_report=n4.GenerationDiversityReport(
            min_required=1, candidate_count=0, unique_diversity_key_count=0
        ),
    )
    source = result.as_organ_run()
    seed_store = FileSystemCAS(tmp_path / "source-seed")
    seed_repository = GenerationSourceRepository(seed_store)
    seed_id = seed_repository.persist(
        run_id="synthetic-typed-source-ref",
        cycle_index=0,
        problem=problem,
        organ=source,
        execution_scope="contract_testing",
    )
    source_body = seed_store.get_bytes(seed_id)

    store = FileSystemCAS(tmp_path / "typed-source-cas").with_ambient_ownership_enforcement()
    repository = GenerationSourceRepository(store)

    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        wrong_default = store.put_bytes(
            source_body,
            ArtifactWriteOptions(
                kind="runtime.unrelated_source_view", media_type="application/json"
            ),
        )
        typed_ref = repository.persist_ref(
            run_id="synthetic-typed-source-ref",
            cycle_index=0,
            problem=problem,
            organ=source,
            execution_scope="contract_testing",
        )

        assert isinstance(typed_ref, ArtifactRef)
        assert typed_ref.artifact_id == wrong_default.artifact_id
        assert typed_ref.manifest_profile_sha256 != wrong_default.manifest_profile_sha256
        body = store.get_bytes(typed_ref)
        restored = repository.load(typed_ref, run_id="synthetic-typed-source-ref")
        n6_receipt = repository.preservation_receipt(
            run_id="synthetic-typed-source-ref",
            refs=(typed_ref,),
            expected=restored.identities(),
        )
        assert n6_receipt.status == "drift"
        assert "source_selected_view_not_retained_by_n6_id" in n6_receipt.issues
        assert n6_receipt.source_refs == (str(typed_ref.artifact_id),)
        source_options = _source_write_options()
        assert source_options.producer is not None
        wrong_options = replace(
            source_options,
            producer=source_options.producer.model_copy(update={"component": "synthetic.other"}),
        )
        wrong_store = FileSystemCAS(
            tmp_path / "typed-source-wrong-owner"
        ).with_ambient_ownership_enforcement()
        wrong_owner_ref = wrong_store.put_bytes(body, wrong_options, return_selected_profile=True)
        assert wrong_owner_ref.manifest_profile_sha256 == (
            artifact_manifest_profile_sha256(wrong_store.get_manifest(wrong_owner_ref))
        )
        with pytest.raises(ValueError, match="generation_source_owner_profile_mismatch"):
            GenerationSourceRepository(wrong_store).load(
                wrong_owner_ref, run_id="synthetic-typed-source-ref"
            )
        with pytest.raises(ValueError, match="canon_profile_absent"):
            repository.load(str(typed_ref.artifact_id), run_id="synthetic-typed-source-ref")

    with (
        tenant_scope(None, tenant_id="tenant-b", cell_id="cell-b"),
        pytest.raises(ArtifactOwnershipError),
    ):
        store.get_bytes(typed_ref)

    body_hash = "sha256:" + hashlib.sha256(body).hexdigest()
    assert body_hash == str(typed_ref.artifact_id)
    assert body == source_body
    assert body == canon.to_canonical_bytes(restored, _SOURCE_CANON)

    legacy_store = FileSystemCAS(tmp_path / "legacy-source-cas")
    legacy_repository = GenerationSourceRepository(legacy_store)
    legacy_ref = legacy_repository.persist(
        run_id="synthetic-typed-source-ref",
        cycle_index=0,
        problem=problem,
        organ=source,
        execution_scope="contract_testing",
    )
    assert isinstance(legacy_ref, str)
    assert legacy_repository.load(legacy_ref, run_id="synthetic-typed-source-ref") == restored

    default_view_store = FileSystemCAS(tmp_path / "default-view-source-cas")
    default_view_repository = GenerationSourceRepository(default_view_store)
    default_view_ref = default_view_repository.persist_ref(
        run_id="synthetic-typed-source-ref",
        cycle_index=0,
        problem=problem,
        organ=source,
        execution_scope="contract_testing",
    )
    assert default_view_ref.manifest_profile_sha256 is None
    assert default_view_store.get_manifest(default_view_ref).kind == (
        "runtime.generation_source_handoff"
    )
    assert (
        default_view_repository.load(default_view_ref, run_id="synthetic-typed-source-ref")
        == restored
    )


def test_candidate_owner_profile_preserves_warning_view_semantics(tmp_path):
    """An omitted warnings option means no warnings, not an unknown profile."""
    from dataclasses import replace

    from polisyos.core import artifacts
    from polisyos.runtime.quality.generation_source import (
        _has_n4_candidate_proposal_owner_profile,
        _has_source_owner_profile,
        _n4_candidate_proposal_write_options,
        _source_write_options,
    )

    store = artifacts.FileSystemCAS(tmp_path / "warning-profile")
    candidate_bytes = b"candidate-profile-probe"
    store.put_bytes(
        candidate_bytes,
        artifacts.ArtifactWriteOptions(
            kind="runtime.unrelated_profile_probe", media_type="application/octet-stream"
        ),
    )
    options = _n4_candidate_proposal_write_options()
    ref = store.put_bytes(candidate_bytes, options)
    assert ref.manifest_profile_sha256 is not None
    assert store.verify(ref).ok
    manifest = store.get_manifest(ref)
    assert manifest.warnings == []
    assert _has_n4_candidate_proposal_owner_profile(manifest)

    warned_ref = store.put_bytes(
        candidate_bytes,
        replace(
            options,
            warnings=[artifacts.WarningRecord(code="warning", msg="retained warning")],
        ),
    )
    assert warned_ref.manifest_profile_sha256 is not None
    assert store.verify(warned_ref).ok
    assert not _has_n4_candidate_proposal_owner_profile(store.get_manifest(warned_ref))

    source_bytes = b"source-handoff-profile-probe"
    store.put_bytes(
        source_bytes,
        artifacts.ArtifactWriteOptions(
            kind="runtime.unrelated_source_probe", media_type="application/octet-stream"
        ),
    )
    source_ref = store.put_bytes(source_bytes, _source_write_options())
    assert source_ref.manifest_profile_sha256 is not None
    assert store.verify(source_ref).ok
    assert _has_source_owner_profile(store.get_manifest(source_ref))


def test_tracked_owner_epochs_remain_exactly_readable():
    """Walk complete tracked owner records; historical nested CG2 gets no new defaults."""
    import copy
    import json
    from pathlib import Path

    from polisyos.runtime.quality.generation_cycle import GenerationCycleRun
    from polisyos.runtime.quality.promotion_sequence import (
        CanonicalPromotionReceipt,
        parse_canonical_promotion_history_receipt,
        validate_canonical_promotion_receipt,
    )
    from tests.unit.runtime.quality.historical_artifacts import historical_generation_cycle_v1

    root = Path(__file__).resolve().parents[4]
    models = {
        "policyos.runtime.generation_cycle_controller.v1": GenerationCycleRun,
    }
    historical_schemas = {"policyos.policy_design_case.layer3_gy.n9_promotion.v6"}
    tracked_schemas = models.keys() | historical_schemas
    documents = {
        "historical_layer3_gy_generation_cycle_contract.v1": historical_generation_cycle_v1(),
        "layer3_gy_promotion_contract.json": json.loads(
            (
                root / "architecture/policy_design_case/layer3_gy_promotion_contract.json"
            ).read_bytes()
        ),
    }
    recursive = {}

    def walk(value, path):
        if isinstance(value, dict):
            if value.get("schema_version") in tracked_schemas:
                recursive[path] = value
            for key, item in value.items():
                walk(item, (*path, key))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, (*path, str(index)))

    for name, value in documents.items():
        walk(value, (name,))
    iterative = {}
    pending = [((name,), value) for name, value in documents.items()]
    while pending:
        path, value = pending.pop()
        if isinstance(value, dict):
            if value.get("schema_version") in tracked_schemas:
                iterative[path] = value
            pending.extend(((*path, key), item) for key, item in value.items())
        elif isinstance(value, list):
            pending.extend(((*path, str(index)), item) for index, item in enumerate(value))
    assert recursive.keys() == iterative.keys()
    assert recursive
    assert {payload["schema_version"] for payload in recursive.values()} == tracked_schemas

    def leaves(value, prefix=()):
        found = {}
        if isinstance(value, dict) and value:
            for key, item in value.items():
                found.update(leaves(item, (*prefix, key)))
        elif isinstance(value, list) and value:
            for index, item in enumerate(value):
                found.update(leaves(item, (*prefix, str(index))))
        else:
            found[prefix] = value
        return found

    differences = []
    for path, payload in recursive.items():
        schema_version = payload["schema_version"]
        if schema_version in historical_schemas:
            historical = parse_canonical_promotion_history_receipt(payload)
            observed = historical.historical_projection()
            assert observed == payload
            value_outer_set = payload["owner_projection"]["value_receipt"]["value_outer_set"]
            typed_outer_set = historical.owner_projection.value_receipt.value_outer_set
            for field_name in ("statistical_lower", "statistical_upper"):
                if field_name not in value_outer_set:
                    assert field_name not in typed_outer_set.model_fields_set
                    assert (
                        field_name
                        not in observed["owner_projection"]["value_receipt"]["value_outer_set"]
                    )
            corrupted = copy.deepcopy(payload)
            corrupted["owner_projection"]["operation_invocation_id"] += ".tampered"
            with pytest.raises(ValidationError, match="n9_owner_projection_hash_mismatch"):
                parse_canonical_promotion_history_receipt(corrupted)
            with pytest.raises(ValidationError):
                CanonicalPromotionReceipt.model_validate(payload)
            assert validate_canonical_promotion_receipt(payload) == (
                {"code": "legacy_obligation_scope_v3_authority_not_admitted"},
            )
        else:
            observed = models[schema_version].model_validate(payload).model_dump(mode="json")
        old, new = leaves(payload), leaves(observed)
        for identity in sorted(old.keys() | new.keys()):
            if identity not in old or identity not in new or old[identity] != new[identity]:
                differences.append(
                    {
                        "record": path,
                        "path": identity,
                        "old_present": identity in old,
                        "new_present": identity in new,
                        "old": old.get(identity, "ABSENT"),
                        "new": new.get(identity, "ABSENT"),
                    }
                )
    assert not differences, json.dumps(differences, sort_keys=True)


@pytest.mark.asyncio
async def test_default_controller_custody_and_missing_protected_admission(
    actual_n4_source,
    tmp_path,
    monkeypatch,
):
    """The real default N4/N6 handoff survives before the real protected N9 refusal."""
    from collections import Counter
    from pathlib import Path

    from polisyos.core import artifacts
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.resilience import guard_runtime_cas
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        PendingN8ValuePort,
    )
    from polisyos.runtime.quality.open_world_risk import PromotionRuntime
    from tests.unit.runtime.quality.test_generation_cycle import (
        _budget,
        _canonical_loaded_deployment_identity,
    )

    problem, organ = actual_n4_source
    supplied_budgets = []
    actual_emissions = []

    async def produce(_problem, **kwargs):
        assert _problem == problem
        assert kwargs["cycle_substrate_context"] == organ.cycle_substrate_context
        supplied_budgets.append(kwargs["grounding_run_budget"])
        emitted = _produce_source_variant(problem, organ, run_budget=kwargs["grounding_run_budget"])
        actual_emissions.append(emitted)
        return emitted

    monkeypatch.setattr(n4, "generate_design_candidate_bundle_under_a", produce)
    owner_store = artifacts.FileSystemCAS(tmp_path / "runtime").with_ambient_ownership_enforcement()
    store = guard_runtime_cas(owner_store)
    with tenant_scope(None, tenant_id="tenant-source-a", cell_id="cell-source-a"):
        runtime = PromotionRuntime(store=store)
        controller = GenerationCycleController(
            model_id="synthetic-c2",
            repo_root=Path(__file__).resolve().parents[4],
            cycle_substrate_context=organ.cycle_substrate_context,
            promotion_runtime=runtime,
            value_port=PendingN8ValuePort(),
            authority_scope="contract_testing",
        )
        run = await controller.run(problem, budget_state=_budget(), min_cycles=1, max_cycles=1)
        assert run.synthetic is True
        assert run.source_preservation_receipt.synthetic is True
        assert run.source_preservation_receipt.status == "strangled", (
            run.source_preservation_receipt.issues
        )
        assert run.source_handoff_refs
        assert not run.promotion_port.certified_candidate_ids
        assert controller._promotion_port(
            admitted_batch=None,
            problem=problem,
            deployment_identity=_canonical_loaded_deployment_identity(),
        ).reason == ("epoch_validity_refused:pre_n9_admitted_batch_missing")
        assert supplied_budgets and supplied_budgets[0] is controller._grounding_run_budget
        for source in actual_emissions[0].candidate_sources:
            admission = source.grounding_decision_certificate.run_admission
            assert admission.run_id == run.run_id
            assert admission.charged_this_attempt == 0
        repository = controller._source_repository
        assert repository is not None
        assert repository.store is store
        retained_organ = actual_emissions[0]
        emitted_candidates = tuple(retained_organ.result.candidates)
        assert emitted_candidates
        summary_by_candidate_id = {row.candidate_id: row for row in run.candidate_summaries}
        emitted_candidate_ids = {candidate.candidate_id for candidate in emitted_candidates}
        assert emitted_candidate_ids <= summary_by_candidate_id.keys()
        assert all(
            summary_by_candidate_id[candidate.candidate_id].generation_channel == "n4_owner"
            and summary_by_candidate_id[candidate.candidate_id].content_hash
            == candidate.atom.content_hash
            for candidate in emitted_candidates
        )
        emitted_candidate = emitted_candidates[0]
        summary = summary_by_candidate_id[emitted_candidate.candidate_id]
        resolved = repository.resolve(
            refs=run.source_handoff_refs,
            run_id=run.run_id,
            summary=summary,
            problem=problem,
        )
        assert resolved.status == "resolved", resolved.code
        assert resolved.source_ref in run.source_handoff_refs
        initial_context = controller._promotion_source_context(summary, problem)
        assert (
            initial_context["world_model_record"]
            == organ.cycle_substrate_context.world_model_record
        )
        assert (
            initial_context["effect_obligation_writer_input"].intervention_atom
            == emitted_candidate.atom
        )
        stale_fixture_summary = _source_summary(organ)
        assert (stale_fixture_summary.candidate_id, stale_fixture_summary.content_hash) != (
            summary.candidate_id,
            summary.content_hash,
        )
        stale_fixture_resolution = repository.resolve(
            refs=run.source_handoff_refs,
            run_id=run.run_id,
            summary=stale_fixture_summary,
            problem=problem,
        )
        assert stale_fixture_resolution.status == "not_established"
        assert stale_fixture_resolution.code == "source_missing"
        before = controller._grounding_run_budget
        controller._restore_source_run(run)
        assert controller._grounding_run_budget is before
        assert tuple(controller._source_handoff_refs) == run.source_handoff_refs
        # Repeating the actual default N4 handoff is permitted without changing the problem.
        repeated_state = await controller._generate_node({"problem": problem, "cycle_index": 1})
        assert supplied_budgets[-1] is before
        repeated_organ = actual_emissions[-1]
        repeated_candidates = tuple(repeated_organ.result.candidates)
        assert repeated_candidates
        assert repeated_state["generation_result"] is repeated_organ.result
        repeated_grounded_state = controller._ground_node(repeated_state)
        repeated_summaries = tuple(repeated_grounded_state["candidate_summaries"])
        assert repeated_state["cycle_index"] == 1
        assert repeated_state["generation_channel"] == "n4_owner"
        repeated_candidates_by_id = {
            candidate.candidate_id: candidate for candidate in repeated_candidates
        }
        assert len(repeated_candidates_by_id) == len(repeated_candidates)
        emitted_occurrences = Counter(
            (
                candidate.candidate_id,
                candidate.atom.content_hash,
                repeated_state["cycle_index"],
                repeated_state["generation_channel"],
            )
            for candidate in repeated_candidates
        )
        summary_occurrences = Counter(
            (
                owner_summary.candidate_id,
                owner_summary.content_hash,
                owner_summary.cycle_index,
                owner_summary.generation_channel,
            )
            for owner_summary in repeated_summaries
        )
        assert summary_occurrences == emitted_occurrences
        receipt = controller._source_preservation_receipt()
        assert receipt.status == "strangled", receipt.issues
        for owner_summary in repeated_summaries:
            candidate = repeated_candidates_by_id[owner_summary.candidate_id]
            actual_context = controller._promotion_source_context(owner_summary, problem)
            assert (
                actual_context["world_model_record"]
                == repeated_organ.cycle_substrate_context.world_model_record
            )
            assert (
                actual_context["effect_obligation_writer_input"].intervention_atom == candidate.atom
            )
        prior_epoch = repository.resolve(
            refs=tuple(controller._source_handoff_selected_refs),
            run_id=run.run_id,
            summary=summary,
            problem=problem,
        )
        assert prior_epoch.status == "not_established"
        assert prior_epoch.code == "source_occurrence_missing"

    with tenant_scope(None, tenant_id="tenant-source-b", cell_id="cell-source-b"):
        refused = repository.resolve(
            refs=run.source_handoff_refs,
            run_id=run.run_id,
            summary=summary,
            problem=problem,
        )
        assert refused.status == "not_established"
        assert refused.code == "source_replay_failed"


@pytest.mark.asyncio
async def test_failed_source_handoff_cannot_supply_authority(tmp_path, monkeypatch):
    """A candidate survives a CAS write failure, while strict N6 and N9 refuse it."""
    from polisyos.core import artifacts
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        GenerationCycleError,
        GenerationSourcePreservationReceipt,
        PendingN8ValuePort,
        eligible_n9_source_for_run,
        validate_generation_cycle_run,
    )
    from polisyos.runtime.quality.open_world_risk import PromotionRuntime
    from tests.unit.runtime.quality.test_generation_cycle import (
        _budget,
        _StableShadowGrounding,
    )

    problem = _test_design_problem()
    result = n4.GenerationUnderAResult(
        status="generation_unavailable",
        design_problem_ref=n4.gy_content_hash(problem.model_dump(mode="json")),
        model_id="synthetic-c2",
        preflight=n4.ModelProfilePreflight(status="gateway_unavailable", model_id="synthetic-c2"),
        diversity_report=n4.GenerationDiversityReport(
            min_required=1, candidate_count=0, unique_diversity_key_count=0
        ),
    )
    organ = result.as_organ_run(trinity_bundle=_bundle([_intervention("custody_failure")]))

    async def produce(_problem, *, cycle_index):
        assert _problem == problem and cycle_index == 0
        return organ

    persist_ref_attempts: list[tuple[str, int]] = []

    def fail_persist_ref(self, **kwargs):
        persist_ref_attempts.append((kwargs["run_id"], kwargs["cycle_index"]))
        raise OSError("injected source-store write failure")

    class _StopAfterCandidate(GenerationCycleController):
        def decide_next_action(self, **kwargs):
            decision = super().decide_next_action(**kwargs)
            return decision.model_copy(
                update={"next_action": "stop", "reason": "source_failure_candidate_control"}
            )

    monkeypatch.setattr(GenerationSourceRepository, "persist_ref", fail_persist_ref)
    store = artifacts.FileSystemCAS(tmp_path / "runtime")
    controller = _StopAfterCandidate(
        generation_port=produce,
        grounding_port=_StableShadowGrounding(),
        promotion_runtime=PromotionRuntime(store=store),
        value_port=PendingN8ValuePort(),
        authority_scope="contract_testing",
    )
    run = await controller.run(problem, budget_state=_budget(), min_cycles=1, max_cycles=1)
    assert len(persist_ref_attempts) == 1
    assert persist_ref_attempts[0][0]
    assert persist_ref_attempts[0][1] == 0
    assert run.cycles and run.candidate_summaries
    assert run.terminal_status == "completed"
    assert run.source_preservation_receipt is not None
    assert run.source_preservation_receipt.status == "drift"
    assert "source_persistence_refused:OSError" in run.source_preservation_receipt.issues
    assert run.promotion_port.reason == (
        "generation_cycle_source_preservation_not_established:drift"
    )
    assert "generation_cycle_source_preservation_not_established" in {
        issue["code"] for issue in validate_generation_cycle_run(run)
    }
    with pytest.raises(
        GenerationCycleError, match="generation_cycle_source_preservation_not_established"
    ):
        eligible_n9_source_for_run(run)

    # A self-hashed receipt with its positive status marker restored still
    # fails if the producer's recorded replay issue remains.
    receipt_payload = run.source_preservation_receipt.model_dump(mode="json")
    receipt_payload["status"] = "strangled"
    receipt_payload["content_hash"] = n4.gy_content_hash(
        {key: value for key, value in receipt_payload.items() if key != "content_hash"}
    )
    inconsistent = GenerationSourcePreservationReceipt.model_validate(receipt_payload)
    marked_run = run.model_copy(update={"source_preservation_receipt": inconsistent})
    assert {
        issue["reason"]
        for issue in validate_generation_cycle_run(marked_run)
        if issue["code"] == "generation_cycle_source_preservation_not_established"
    } == {"receipt_incoherent"}
    with pytest.raises(GenerationCycleError, match="receipt_incoherent"):
        eligible_n9_source_for_run(marked_run)

    missing_receipt_run = run.model_copy(update={"source_preservation_receipt": None})
    with pytest.raises(GenerationCycleError, match="receipt_missing"):
        eligible_n9_source_for_run(missing_receipt_run)


def test_data_only_new_candidate_preserves_complete_source_identity(actual_n4_source, tmp_path):
    """New declared IDs and parameter data traverse unchanged producers and custody owners."""
    from decimal import Decimal

    from polisyos.core import artifacts
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.grounding_bind import GroundingRunBudget

    problem, original = actual_n4_source
    run_id = "generation_cycle_" + original.result.design_problem_ref.removeprefix("sha256:")[:16]
    budget = GroundingRunBudget.for_contract_testing(tmp_path / "budget", run_id=run_id)
    intervention = original.trinity_bundle.policy_spec.interventions[0]
    changed = intervention.model_copy(
        update={
            "intervention_id": "corr_data_only_new_candidate",
            "params": {**intervention.params, "rate": Decimal("0.09")},
        }
    )
    bundle = original.trinity_bundle.model_copy(
        update={
            "policy_spec": original.trinity_bundle.policy_spec.model_copy(
                update={"interventions": [changed]}
            )
        }
    )
    originals = (
        _produce_source_variant(problem, original, run_budget=budget),
        _produce_source_variant(problem, original, bundle=bundle, run_budget=budget),
    )
    expected = {
        (value.result.design_problem_ref, candidate.candidate_id, candidate.atom.content_hash)
        for value in originals
        for candidate in value.result.candidates
    }
    assert {item.candidate_id for item in originals[0].result.candidates} != {
        item.candidate_id for item in originals[1].result.candidates
    }
    repository = GenerationSourceRepository(artifacts.FileSystemCAS(tmp_path / "cas"))
    refs = tuple(
        repository.persist(run_id=run_id, cycle_index=i, problem=problem, organ=value)
        for i, value in enumerate(originals)
    )
    restored = {
        identity for ref in refs for identity in repository.load(ref, run_id=run_id).identities()
    }
    assert restored == expected
    for cycle_index, value in enumerate(originals):
        resolved = repository.resolve(
            refs=refs,
            run_id=run_id,
            summary=_source_summary(value, cycle=cycle_index),
            problem=problem,
        )
        assert resolved.status == "resolved", resolved.code
        assert resolved.context["effect_obligation_writer_input"].intervention_atom == (
            value.result.candidates[0].atom
        )
        assert not value.candidate_sources[0].grounding_decision_certificate.production_promotable
    receipt = repository.preservation_receipt(run_id=run_id, refs=refs, expected=tuple(expected))
    assert receipt.status == "strangled", receipt.issues
    assert receipt.synthetic is True


def test_actual_retained_source_drives_effect_writer_and_marks_bridge(actual_n4_source, tmp_path):
    """Real retained owners produce a refused EFFECT artifact with explicit ancestry."""
    import hashlib
    import json
    import os
    from pathlib import Path

    from polisyos.core import artifacts
    from polisyos.runtime.quality import promotion_sequence as promotion_sequence_module
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.promotion_sequence import (
        CanonicalPromotionInput,
        N9DesignProblemBinding,
        N9PromotionEvidenceBridgeRepository,
    )

    problem, organ = actual_n4_source
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    repository = GenerationSourceRepository(store)
    ref = repository.persist(
        run_id="synthetic-writer-control", cycle_index=0, problem=problem, organ=organ
    )
    resolved = repository.resolve(
        refs=(ref,),
        run_id="synthetic-writer-control",
        summary=_source_summary(organ),
        problem=problem,
    )
    assert resolved.status == "resolved", resolved.code
    context = resolved.context
    writer = context["effect_obligation_writer_input"]
    promotion_input = CanonicalPromotionInput(
        design_problem_binding=N9DesignProblemBinding.from_problem(problem),
        candidate_summary=_source_summary(organ),
        world_model_record=context["world_model_record"],
        grounding_decision_certificate=context["grounding_decision_certificate"],
        credal_reference=context["credal_reference"],
    )
    bridge_owner = N9PromotionEvidenceBridgeRepository(store=store)
    bridge_ref = bridge_owner.persist_effect_obligation(
        promotion_input=promotion_input,
        **{name: getattr(writer, name) for name in type(writer).model_fields},
    )
    raw = store.get_bytes(bridge_ref.artifact_id)
    bridge = json.loads(raw)
    source = json.loads(store.get_bytes(bridge["source_artifact_id"]))
    assert bridge_ref.manifest_profile_sha256 is not None
    bridge_selector = artifacts.ArtifactRef(
        artifact_id=artifacts.ArtifactID(bridge_ref.artifact_id),
        kind=promotion_sequence_module._PROMOTION_EVIDENCE_BRIDGE_KIND,
        media_type="application/vnd.polisyos.chronology+json",
        manifest_profile_sha256=bridge_ref.manifest_profile_sha256,
    )
    bridge_manifest = store.get_manifest(bridge_selector)
    assert len(bridge_manifest.inputs) == 1
    source_input = bridge_manifest.inputs[0]
    assert source_input.role == promotion_sequence_module._N9_EVIDENCE_SOURCE_INPUT_ROLE
    assert str(source_input.artifact_id) == bridge["source_artifact_id"]
    assert source_input.manifest_profile_sha256 is not None
    source_selector = artifacts.ArtifactRef(
        artifact_id=source_input.artifact_id,
        kind=promotion_sequence_module._EFFECT_OBLIGATION_SOURCE_KIND,
        media_type="application/vnd.polisyos.chronology+json",
        manifest_profile_sha256=source_input.manifest_profile_sha256,
    )
    assert store.verify(source_selector).ok
    assert source_input.role == promotion_sequence_module._N9_EVIDENCE_SOURCE_INPUT_ROLE
    assert source["synthetic"] is True
    assert any(
        edge["provenance"].get("synthetic") is True
        for edge in source["credal_reference"]["essential_edges"]
    )
    disposition = bridge_owner.resolve(
        bridge_ref=bridge_ref, promotion_input=promotion_input, evidence_kind="effect_obligation"
    )
    assert disposition.status == "refused", disposition
    assert disposition.limitation_code == "synthetic_evidence_cannot_grant_authority"
    assert bridge["source_limitation_code"] == "effect_atom_binding_shadow_only"

    # The selected bridge profile is load-bearing even though the body is unchanged.
    profileless_bridge = bridge_ref.model_copy(update={"manifest_profile_sha256": None})
    assert (
        bridge_owner.resolve(
            bridge_ref=profileless_bridge,
            promotion_input=promotion_input,
            evidence_kind="effect_obligation",
        ).status
        == "not_established"
    )

    # Same source body plus a forged lineage role does not pass the consumer.
    current = promotion_sequence_module
    bridge_record = current.N9PromotionEvidenceBridgeRecord.model_validate_json(raw)
    wrong_role_input = source_input.model_copy(update={"role": "unrelated_source"})
    forged_ref, _, _ = current._persist_model(
        store=store,
        value=bridge_record,
        kind=current._PROMOTION_EVIDENCE_BRIDGE_KIND,
        inputs=(wrong_role_input,),
        selected_profile=True,
    )
    forged_bridge = bridge_ref.model_copy(
        update={
            "artifact_id": str(forged_ref.artifact_id),
            "uri": f"cas://{forged_ref.artifact_id}",
            "content_hash": n4.gy_content_hash(bridge_record.model_dump(mode="json")),
            "manifest_profile_sha256": forged_ref.manifest_profile_sha256,
        }
    )
    assert (
        bridge_owner.resolve(
            bridge_ref=forged_bridge,
            promotion_input=promotion_input,
            evidence_kind="effect_obligation",
        ).status
        == "not_established"
    )

    # A same-ID alternate manifest profile with substituted inputs cannot be rebound.
    source_record = current._read_model(
        store=store,
        ref=source_selector,
        model=current._EffectObligationProducerRecord,
        kind=current._EFFECT_OBLIGATION_SOURCE_KIND,
    )
    alternate_source_profile, _, _ = current._persist_model(
        store=store,
        value=source_record,
        kind=current._EFFECT_OBLIGATION_SOURCE_KIND,
        inputs=(
            artifacts.InputRef(
                artifact_id=bridge_owner._verifier_provenance_ref.artifact_id,
                role="unowned_source_input",
            ),
        ),
        selected_profile=True,
    )
    assert alternate_source_profile.artifact_id == source_selector.artifact_id
    assert (
        alternate_source_profile.manifest_profile_sha256 != source_selector.manifest_profile_sha256
    )
    alternate_profile_input = artifacts.input_ref_from_artifact_ref(
        alternate_source_profile, role=current._N9_EVIDENCE_SOURCE_INPUT_ROLE
    )
    alternate_profile_bridge_ref, _, _ = current._persist_model(
        store=store,
        value=bridge_record,
        kind=current._PROMOTION_EVIDENCE_BRIDGE_KIND,
        inputs=(alternate_profile_input,),
        selected_profile=True,
    )
    alternate_profile_bridge = bridge_ref.model_copy(
        update={"manifest_profile_sha256": alternate_profile_bridge_ref.manifest_profile_sha256}
    )
    assert (
        bridge_owner.resolve(
            bridge_ref=alternate_profile_bridge,
            promotion_input=promotion_input,
            evidence_kind="effect_obligation",
        ).status
        == "not_established"
    )

    # A different valid source artifact also cannot be rebound under the original body.
    alternate_record = source_record.model_copy(
        update={"proposal_id": source_record.proposal_id + "-alternate"}
    )
    alternate_ref, _, _ = current._persist_model(
        store=store,
        value=alternate_record,
        kind=current._EFFECT_OBLIGATION_SOURCE_KIND,
        selected_profile=True,
    )
    alternate_input = artifacts.input_ref_from_artifact_ref(
        alternate_ref, role=current._N9_EVIDENCE_SOURCE_INPUT_ROLE
    )
    wrong_source_ref, _, _ = current._persist_model(
        store=store,
        value=bridge_record,
        kind=current._PROMOTION_EVIDENCE_BRIDGE_KIND,
        inputs=(alternate_input,),
        selected_profile=True,
    )
    wrong_source_bridge = bridge_ref.model_copy(
        update={
            "artifact_id": str(wrong_source_ref.artifact_id),
            "uri": f"cas://{wrong_source_ref.artifact_id}",
            "content_hash": n4.gy_content_hash(bridge_record.model_dump(mode="json")),
            "manifest_profile_sha256": wrong_source_ref.manifest_profile_sha256,
        }
    )
    assert (
        bridge_owner.resolve(
            bridge_ref=wrong_source_bridge,
            promotion_input=promotion_input,
            evidence_kind="effect_obligation",
        ).status
        == "not_established"
    )

    empty_lineage_ref, _, _ = current._persist_model(
        store=store,
        value=bridge_record,
        kind=current._PROMOTION_EVIDENCE_BRIDGE_KIND,
        inputs=(),
        selected_profile=True,
    )
    empty_lineage_bridge = bridge_ref.model_copy(
        update={
            "artifact_id": str(empty_lineage_ref.artifact_id),
            "uri": f"cas://{empty_lineage_ref.artifact_id}",
            "content_hash": n4.gy_content_hash(bridge_record.model_dump(mode="json")),
            "manifest_profile_sha256": empty_lineage_ref.manifest_profile_sha256,
        }
    )
    assert (
        bridge_owner.resolve(
            bridge_ref=empty_lineage_bridge,
            promotion_input=promotion_input,
            evidence_kind="effect_obligation",
        ).status
        == "not_established"
    )

    duplicate_lineage_ref, _, _ = current._persist_model(
        store=store,
        value=bridge_record,
        kind=current._PROMOTION_EVIDENCE_BRIDGE_KIND,
        inputs=(source_input, source_input),
        selected_profile=True,
    )
    duplicate_lineage_bridge = bridge_ref.model_copy(
        update={"manifest_profile_sha256": duplicate_lineage_ref.manifest_profile_sha256}
    )
    assert (
        bridge_owner.resolve(
            bridge_ref=duplicate_lineage_bridge,
            promotion_input=promotion_input,
            evidence_kind="effect_obligation",
        ).status
        == "not_established"
    )

    compatibility_path = os.environ.get("CORR_C2_LEGACY_EFFECT_BRIDGE_PATH")
    if compatibility_path and bridge["schema_version"].endswith(".v2"):
        path = Path(compatibility_path)
        assert not path.exists()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "synthetic": True,
                    "purpose": "exact historical owner emission compatibility",
                    "body_sha256": hashlib.sha256(raw).hexdigest(),
                    "body_utf8": raw.decode(),
                },
                sort_keys=True,
            )
            + "\n"
        )
    assert bridge.get("synthetic") is True


def test_current_effect_bridge_binds_actual_historical_emitter_epoch(
    actual_n4_source, tmp_path, monkeypatch
):
    """A new run of the pinned v1 emitter remains history under a claimed v2 bridge."""
    import hashlib
    import json
    import sys
    import types

    from polisyos.core import artifacts
    from polisyos.runtime.quality import promotion_sequence as current
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from tests.unit.runtime.quality.historical_artifacts import (
        PROMOTION_EMITTER_BASE_BLOB,
        historical_owner_bytes,
    )

    problem, organ = actual_n4_source
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    repository = GenerationSourceRepository(store)
    source_ref = repository.persist(
        run_id="synthetic-historical-writer", cycle_index=0, problem=problem, organ=organ
    )
    resolved = repository.resolve(
        refs=(source_ref,),
        run_id="synthetic-historical-writer",
        summary=_source_summary(organ),
        problem=problem,
    )
    assert resolved.status == "resolved", resolved.code
    context = resolved.context
    writer = context["effect_obligation_writer_input"]
    promotion_input = current.CanonicalPromotionInput(
        design_problem_binding=current.N9DesignProblemBinding.from_problem(problem),
        candidate_summary=_source_summary(organ),
        world_model_record=context["world_model_record"],
        grounding_decision_certificate=context["grounding_decision_certificate"],
        credal_reference=context["credal_reference"],
    )

    # Execute the entire pinned historical owner. No current receipt is restamped.
    name = "polisyos.runtime.quality._corr_historical_promotion_emitter"
    historical = types.ModuleType(name)
    historical.__package__ = "polisyos.runtime.quality"
    historical.__file__ = f"git:{PROMOTION_EMITTER_BASE_BLOB}"
    monkeypatch.setitem(sys.modules, name, historical)
    raw_module = historical_owner_bytes(PROMOTION_EMITTER_BASE_BLOB)
    exec(compile(raw_module, historical.__file__, "exec"), historical.__dict__)  # noqa: S102
    old_input = historical.CanonicalPromotionInput(
        design_problem_binding=historical.N9DesignProblemBinding.from_problem(problem),
        candidate_summary=_source_summary(organ),
        world_model_record=context["world_model_record"],
        grounding_decision_certificate=context["grounding_decision_certificate"],
        credal_reference=context["credal_reference"],
    )
    old_ref = historical.N9PromotionEvidenceBridgeRepository(store=store).persist_effect_obligation(
        promotion_input=old_input,
        **{name: getattr(writer, name) for name in type(writer).model_fields},
    )
    old_bridge = json.loads(store.get_bytes(old_ref.artifact_id))
    old_raw = store.get_bytes(old_bridge["source_artifact_id"])
    old_body = json.loads(old_raw)
    assert old_body["schema_version"] == (
        "policyos.policy_design_case.layer3_gy.n9_effect_obligation_source.v1"
    )
    old_manifest = store.get_manifest(artifacts.ArtifactID(old_bridge["source_artifact_id"]))
    assert old_manifest.canon is None
    parsed = current._read_model(
        store=store,
        ref=artifacts.ArtifactRef(
            artifact_id=artifacts.ArtifactID(old_bridge["source_artifact_id"]),
            kind=current._EFFECT_OBLIGATION_SOURCE_KIND,
            media_type="application/vnd.polisyos.chronology+json",
        ),
        model=current._EffectObligationProducerRecord,
        kind=current._EFFECT_OBLIGATION_SOURCE_KIND,
    )
    _, _, observed = current._persist_model(
        store=store,
        value=parsed,
        kind=current._EFFECT_OBLIGATION_SOURCE_KIND,
        selected_profile=False,
    )
    assert observed == old_raw
    (tmp_path / "historical_effect_v1.json").write_text(
        json.dumps(
            {
                "synthetic": True,
                "purpose": "new execution of the exact historical owner, not recovered history",
                "producer_git_blob": PROMOTION_EMITTER_BASE_BLOB,
                "body_sha256": hashlib.sha256(old_raw).hexdigest(),
                "body_utf8": old_raw.decode(),
            },
            sort_keys=True,
        )
    )
    owner = current.N9PromotionEvidenceBridgeRepository(store=store)
    live_ref = owner.persist_effect_obligation(
        promotion_input=promotion_input,
        **{name: getattr(writer, name) for name in type(writer).model_fields},
    )
    assert (
        owner.resolve(
            bridge_ref=live_ref, promotion_input=promotion_input, evidence_kind="effect_obligation"
        ).limitation_code
        == "synthetic_evidence_cannot_grant_authority"
    )
    live = current.N9PromotionEvidenceBridgeRecord.model_validate_json(
        store.get_bytes(live_ref.artifact_id)
    )
    misleading = live.model_copy(
        update={
            "source_artifact_id": old_bridge["source_artifact_id"],
            "source_semantic_hash": current._semantic_hash(
                current._EFFECT_OBLIGATION_SOURCE_KIND, parsed
            ),
        }
    )
    assert misleading.source_schema_ref == current._EFFECT_OBLIGATION_SOURCE_SCHEMA_VERSION
    changed_ref, _, _ = current._persist_model(
        store=store,
        value=misleading,
        kind=current._PROMOTION_EVIDENCE_BRIDGE_KIND,
        inputs=(),
        selected_profile=True,
    )
    reference = live_ref.model_copy(
        update={
            "artifact_id": str(changed_ref.artifact_id),
            "uri": f"cas://{changed_ref.artifact_id}",
            "content_hash": n4.gy_content_hash(misleading.model_dump(mode="json")),
            "manifest_profile_sha256": changed_ref.manifest_profile_sha256,
        }
    )
    errors, attempts, outcomes = [], [], []
    actual_reader = owner._resolve_effect_record

    def observed_reader(record, *, promotion_input):
        attempts.append(record.source_artifact_id)
        try:
            result = actual_reader(record, promotion_input=promotion_input)
            outcomes.append(result)
            return result
        except ValueError as exc:
            errors.append(str(exc))
            raise

    monkeypatch.setattr(owner, "_resolve_effect_record", observed_reader)
    refusal = owner.resolve(
        bridge_ref=reference, promotion_input=promotion_input, evidence_kind="effect_obligation"
    )
    packet = {
        "actual_source_schema": parsed.schema_version,
        "claimed_source_schema": misleading.source_schema_ref,
        "consumed_source_ids": attempts,
        "mechanical_reader_outcomes": outcomes,
        "reader_errors": errors,
        "outer_disposition": refusal.model_dump(mode="json"),
    }
    print(json.dumps(packet, sort_keys=True))
    assert attempts == [], refusal
    assert outcomes == []
    assert errors == []
    assert (
        store.get_manifest(
            artifacts.ArtifactRef(
                artifact_id=changed_ref.artifact_id,
                kind=current._PROMOTION_EVIDENCE_BRIDGE_KIND,
                media_type="application/vnd.polisyos.chronology+json",
                manifest_profile_sha256=changed_ref.manifest_profile_sha256,
            )
        ).inputs
        == []
    )
    assert refusal.status == "not_established"
    assert refusal.limitation_code == "effect_obligation_evidence_not_established"


def test_synthetic_independence_source_establishes_mechanics_but_never_authority(
    actual_n4_source,
    tmp_path,
    monkeypatch,
):
    """A real established source cannot launder an explicitly synthetic evidence line."""
    import json

    from polisyos.core import artifacts
    from polisyos.runtime.quality.promotion_sequence import (
        _PROMOTION_EVIDENCE_BRIDGE_KIND,
        CanonicalPromotionInput,
        N9DesignProblemBinding,
        N9PromotionEvidenceBridgeRecord,
        N9PromotionEvidenceBridgeRepository,
        _persist_model,
    )
    from tests.unit.runtime.quality.test_promotion_sequence import (
        _independence_line,
        _independence_portfolio_design,
    )

    problem, organ = actual_n4_source
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    owner = N9PromotionEvidenceBridgeRepository(store=store)
    promotion_input = CanonicalPromotionInput(
        design_problem_binding=N9DesignProblemBinding.from_problem(problem),
        candidate_summary=_source_summary(organ),
        world_model_record=organ.cycle_substrate_context.world_model_record,
        grounding_decision_certificate=organ.candidate_sources[0].grounding_decision_certificate,
        credal_reference=organ.credal_reference,
    )
    line = {
        **_independence_line("corr-synthetic-paper", primary_source="journal"),
        "synthetic": True,
    }
    portfolio = {**_independence_portfolio_design(), "synthetic": True}
    bridge_ref = owner.persist_effective_independence(
        promotion_input=promotion_input,
        evidence_lines=(line,),
        portfolio_designs=(portfolio,),
        graph_id="synthetic-corr-independence",
    )
    resolution = owner.resolve(
        bridge_ref=bridge_ref,
        promotion_input=promotion_input,
        evidence_kind="effective_independence",
    )
    assert resolution.status == "refused", resolution
    assert resolution.limitation_code == "synthetic_evidence_cannot_grant_authority"
    bridge = json.loads(store.get_bytes(bridge_ref.artifact_id))
    assert bridge["synthetic"] is True
    assert bridge["source_disposition"] == "established"
    assert bridge["disposition"] == "blocked"
    source = json.loads(store.get_bytes(bridge["source_artifact_id"]))
    assert bridge_ref.manifest_profile_sha256 is not None
    bridge_selector = artifacts.ArtifactRef(
        artifact_id=artifacts.ArtifactID(bridge_ref.artifact_id),
        kind=_PROMOTION_EVIDENCE_BRIDGE_KIND,
        media_type="application/vnd.polisyos.chronology+json",
        manifest_profile_sha256=bridge_ref.manifest_profile_sha256,
    )
    bridge_manifest = store.get_manifest(bridge_selector)
    assert len(bridge_manifest.inputs) == 1
    source_input = bridge_manifest.inputs[0]
    assert source_input.role == "n9_promotion_evidence_source"
    assert str(source_input.artifact_id) == bridge["source_artifact_id"]
    assert source_input.manifest_profile_sha256 is not None
    assert source["synthetic"] is True

    # A hostile synthetic control conceals the marker but keeps actual source,
    # current epoch, semantic outcomes and fully valid CAS/reference bindings.
    malicious = N9PromotionEvidenceBridgeRecord.model_validate(
        {
            **bridge,
            "synthetic": None,
            "disposition": "established",
            "limitation_code": bridge["source_limitation_code"],
        }
    )
    changed_ref, _semantic_hash, _raw = _persist_model(
        store=store,
        value=malicious,
        kind=_PROMOTION_EVIDENCE_BRIDGE_KIND,
        inputs=(source_input,),
        selected_profile=True,
    )
    rebound = bridge_ref.model_copy(
        update={
            "artifact_id": str(changed_ref.artifact_id),
            "uri": f"cas://{changed_ref.artifact_id}",
            "content_hash": n4.gy_content_hash(malicious.model_dump(mode="json")),
            "manifest_profile_sha256": changed_ref.manifest_profile_sha256,
        }
    )
    ancestry = []
    original_ancestry = owner._source_synthetic_provenance

    def observed_ancestry(source_ref, *, promotion_input):
        value = original_ancestry(source_ref, promotion_input=promotion_input)
        ancestry.append((source_ref, value))
        return value

    monkeypatch.setattr(owner, "_source_synthetic_provenance", observed_ancestry)
    concealed = owner.resolve(
        bridge_ref=rebound,
        promotion_input=promotion_input,
        evidence_kind="effective_independence",
    )
    assert len(ancestry) == 1
    observed_source_ref, observed_synthetic = ancestry[0]
    assert isinstance(observed_source_ref, artifacts.ArtifactRef)
    assert str(observed_source_ref.artifact_id) == bridge["source_artifact_id"]
    assert observed_source_ref.manifest_profile_sha256 == source_input.manifest_profile_sha256
    assert observed_synthetic is True
    assert concealed.status == "not_established"
    assert concealed.limitation_code == "effective_independence_evidence_not_established"
    other = promotion_input.model_copy(
        update={
            "candidate_summary": promotion_input.candidate_summary.model_copy(
                update={"candidate_id": "different-synthetic-candidate"}
            )
        }
    )
    mismatch = owner.resolve(
        bridge_ref=bridge_ref, promotion_input=other, evidence_kind="effective_independence"
    )
    assert mismatch.status == "not_established"


def test_effect_writer_json_projection_preserves_complete_cg1(actual_n4_source, tmp_path):
    """Use the writer's serializer only when the actual relation owner stays identical."""
    import json

    from polisyos.core import artifacts
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine

    problem, organ = actual_n4_source
    repository = GenerationSourceRepository(artifacts.FileSystemCAS(tmp_path / "cas"))
    ref = repository.persist(run_id="synthetic-json", cycle_index=0, problem=problem, organ=organ)
    result = repository.resolve(
        refs=(ref,), run_id="synthetic-json", summary=_source_summary(organ), problem=problem
    )
    writer = result.context["effect_obligation_writer_input"]
    original = organ.candidate_sources[0]
    projected = writer.model_dump(mode="json")["proposal"]
    engine = GroundingRelationEngine(organ.credal_reference)
    before = engine.certificate_for(original.proposal, proposal_id=original.proposal_id)
    after = engine.certificate_for(projected, proposal_id=original.proposal_id)
    assert before == after == original.grounding_relation_certificate
    # This is the actual existing writer intake, not a capsule codec approximation.
    assert json.loads(json.dumps(writer.proposal, sort_keys=True)) == projected


def test_candidate_custody_requires_actual_reference(actual_n4_source, tmp_path):
    """A complete-looking candidate without its original reference cannot be retained."""
    from dataclasses import replace

    from polisyos.core import artifacts
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    problem, organ = actual_n4_source
    repository = GenerationSourceRepository(artifacts.FileSystemCAS(tmp_path / "cas"))
    with pytest.raises(ValueError, match="generation_source_owner_input_missing"):
        repository.persist(
            run_id="synthetic-missing-reference",
            cycle_index=0,
            problem=problem,
            organ=replace(organ, credal_reference=None),
        )


def test_semantically_changed_writer_projection_refuses(actual_n4_source, tmp_path, monkeypatch):
    """A valid-looking JSON projection may not alter a decisive grounding axis."""
    from polisyos.core import artifacts
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine
    from polisyos.runtime.quality.promotion_sequence import _EffectObligationWriterInput

    problem, organ = actual_n4_source
    repository = GenerationSourceRepository(artifacts.FileSystemCAS(tmp_path / "cas"))
    ref = repository.persist(
        run_id="synthetic-projection", cycle_index=0, problem=problem, organ=organ
    )
    serializer = _EffectObligationWriterInput.model_dump
    changed_proposals = []

    def changed(self, *args, **kwargs):
        payload = serializer(self, *args, **kwargs)
        if kwargs.get("mode") == "json":
            payload["proposal"]["signature"]["sign"] = "increase"
            changed_proposals.append(payload["proposal"])
        return payload

    monkeypatch.setattr(_EffectObligationWriterInput, "model_dump", changed)
    observed = repository.resolve(
        refs=(ref,), run_id="synthetic-projection", summary=_source_summary(organ), problem=problem
    )
    assert changed_proposals, "the existing writer serializer was not consumed"
    original = organ.candidate_sources[0]
    engine = GroundingRelationEngine(organ.credal_reference)
    altered = engine.certificate_for(changed_proposals[0], proposal_id=original.proposal_id)
    assert altered != original.grounding_relation_certificate
    assert observed.status == "not_established"
    assert observed.code == "effect_writer_projection_grounding_mismatch"
    assert "effect_obligation_writer_input" not in observed.context


def test_conflicting_complete_source_for_same_triple_refuses(actual_n4_source, tmp_path):
    """Different actual source provenance cannot collapse into an idempotent candidate."""
    from dataclasses import replace

    from polisyos.core import artifacts
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    problem, organ = actual_n4_source
    candidate = organ.result.candidates[0]
    altered = candidate.model_copy(
        update={
            "provenance": candidate.provenance.model_copy(
                update={"raw_llm_responses": ("synthetic second occurrence: different raw input",)}
            )
        }
    )
    other = replace(organ, result=organ.result.model_copy(update={"candidates": (altered,)}))
    repository = GenerationSourceRepository(artifacts.FileSystemCAS(tmp_path / "cas"))
    refs = tuple(
        repository.persist(run_id="synthetic-conflict", cycle_index=0, problem=problem, organ=value)
        for value in (organ, other)
    )
    resolved = repository.resolve(
        refs=refs, run_id="synthetic-conflict", summary=_source_summary(organ), problem=problem
    )
    assert resolved.status == "not_established"
    assert resolved.code == "source_ambiguous"
    assert not resolved.context
    receipt = repository.preservation_receipt(
        run_id="synthetic-conflict",
        refs=refs,
        expected=(
            (organ.result.design_problem_ref, candidate.candidate_id, candidate.atom.content_hash),
        ),
    )
    assert receipt.status == "drift"
    assert "source_identity_conflict" in receipt.issues


def test_source_intake_recomputes_original_candidate_provenance(actual_n4_source, tmp_path):
    """A resealed capsule cannot replace the original parsed intervention with a summary."""
    from polisyos.core import artifacts, canon
    from polisyos.runtime.quality.generation_source import (
        _SOURCE_CANON,
        GenerationSourceRepository,
        _source_content_hash,
    )

    problem, organ = actual_n4_source
    repository = GenerationSourceRepository(artifacts.FileSystemCAS(tmp_path / "cas"))
    ref = repository.persist(run_id="synthetic-reseal", cycle_index=0, problem=problem, organ=organ)
    artifact = repository.load(ref, run_id="synthetic-reseal")
    payload = artifact.model_dump(mode="python", exclude={"content_hash"})
    payload["generation_result"]["candidates"][0]["provenance"]["parsed_candidate"] = {
        "synthetic": True,
        "summary": "the original typed intervention has been discarded",
    }
    payload["content_hash"] = _source_content_hash(payload)
    manifest = repository.store.get_manifest(ref)
    assert manifest.canon is not None
    changed_ref = repository.store.put_bytes(
        canon.to_canonical_bytes(payload, _SOURCE_CANON),
        artifacts.ArtifactWriteOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            producer=manifest.producer,
            canon=manifest.canon,
        ),
    )
    _, changed_profile = artifacts.read_core_manifest_profile(repository.store, changed_ref)
    assert changed_profile.status == "declared"
    assert repository.store.verify(changed_ref.artifact_id).ok
    with pytest.raises(ValueError, match="generation_source_original_candidate_mismatch"):
        repository.load(str(changed_ref.artifact_id), run_id="synthetic-reseal")


def test_n4_nonbinding_surface_retains_actual_cg3_authority_limitation():
    """The actual synthetic CG3 admission stays visible in N4's refusal-path output."""
    from polisyos.runtime.quality.grounding_admission import GroundingAdmissionEngine
    from tests.unit.runtime.quality.test_grounding_admission import (
        _cg2_novel,
        _novel_transfer_probe,
        _reference,
    )

    reference = _reference(include_mechanism=True)
    cg1, cg2 = _cg2_novel(reference, _novel_transfer_probe())
    cg3 = GroundingAdmissionEngine(reference).decide(cg2, cg1_certificate=cg1)
    assert cg3.synthetic is True
    assert not cg3.production_promotable
    observed = n4._non_binding_cause(cg1, cg2, cg3)
    assert observed["synthetic"] is True
    assert observed["authority_limitation"] == cg3.authority_limitation


def test_n4_candidate_scenario_source_locator_is_versioned_and_kind_bound():
    """The progress pointer keeps the scenario-source owner distinct from N4 v1/v2."""
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.runtime.quality.generation_source import (
        N4CandidateScenarioSourceLocator,
    )

    locator = N4CandidateScenarioSourceLocator(
        artifact_ref=ArtifactRef(
            artifact_id="sha256:" + "a" * 64,
            kind="runtime.quality.n4_candidate_scenario_source",
            media_type="application/json",
        )
    )
    assert locator.model_dump(mode="json") == {
        "schema_version": ("policyos.runtime.quality.n4_candidate_scenario_source_locator.v1"),
        "artifact_ref": {
            "artifact_id": "sha256:" + "a" * 64,
            "kind": "runtime.quality.n4_candidate_scenario_source",
            "media_type": "application/json",
        },
    }

    with pytest.raises(
        ValueError, match="n4_candidate_scenario_source_locator_owner_profile_mismatch"
    ):
        N4CandidateScenarioSourceLocator(
            artifact_ref=ArtifactRef(
                artifact_id="sha256:" + "a" * 64,
                kind="runtime.quality.n4_candidate_proposal",
                media_type="application/json",
            )
        )


def test_candidate_scenario_identity_separates_semantics_from_refreshed_baseline():
    """Stable identity keeps the same declared action while N5 state changes."""
    from types import SimpleNamespace

    from polisyos.runtime.quality.generation_source import (
        candidate_scenario_semantic_identity_hash,
    )

    class _Dump:
        def __init__(self, payload):
            self.payload = payload

        def __getattr__(self, name):
            try:
                return self.payload[name]
            except KeyError as exc:
                raise AttributeError(name) from exc

        def model_dump(self, *, mode="json", exclude=None):
            del mode
            result = dict(self.payload)
            for key in exclude or ():
                result.pop(key, None)
            return result

    def _source(*, baseline, amount=1, profile_selection_ref=None):
        intervention = _Dump(
            {
                "intervention_id": "tax-relief",
                "kind": "budget_allocation_multiplier",
                "params": {"multiplier": amount},
                "target": {"slot": "government.balance"},
                "schedule": {"period": "2026"},
            }
        )
        policy = _Dump(
            {
                "policy_id": "budget-policy",
                "problem_frame_ref": "sha256:" + "a" * 64,
                "interventions": [intervention.model_dump()],
                "parameters": [],
                "mechanism_bindings": [],
            }
        )
        policy.interventions = (intervention,)
        proposal = SimpleNamespace(
            trinity_bundle=SimpleNamespace(
                problem_frame=_Dump({"problem_id": "public-budget"}),
                policy_spec=policy,
                model_spec=_Dump({"model_id": "synthetic-candidate"}),
            )
        )
        profile = SimpleNamespace(
            profile_id="controlled-budget-profile",
            profile_selection_ref=(profile_selection_ref or "sha256:" + "b" * 64),
            rule=_Dump(
                {
                    "operator_kind": "budget_allocation_multiplier",
                    "parameter_id": "multiplier",
                    "target_world_slot": "government.balance",
                    "unit_id": "fraction",
                    "minimum": 0,
                    "maximum": 2,
                }
            ),
            n5=_Dump(
                {
                    "budget_ref": "candidate-budget-v1",
                    "horizon": {"steps": 1},
                    "baseline_state": {"government.balance": baseline},
                    "comparator_refs": [],
                    "seed": 13,
                    "replications": 1,
                }
            ),
        )
        candidate = SimpleNamespace(intervention_id="tax-relief")
        return proposal, candidate, profile

    stable_subject_ref = "sha256:" + "c" * 64
    before = _source(baseline=0)
    after = _source(baseline=7)
    before_hash = candidate_scenario_semantic_identity_hash(
        stable_subject_ref=stable_subject_ref,
        proposal=before[0],
        candidate=before[1],
        profile=before[2],
    )
    after_hash = candidate_scenario_semantic_identity_hash(
        stable_subject_ref=stable_subject_ref,
        proposal=after[0],
        candidate=after[1],
        profile=after[2],
    )
    changed_action = _source(baseline=7, amount=2)
    changed_selector = _source(
        baseline=7,
        profile_selection_ref="sha256:" + "d" * 64,
    )

    assert before_hash == after_hash
    assert before_hash != candidate_scenario_semantic_identity_hash(
        stable_subject_ref=stable_subject_ref,
        proposal=changed_action[0],
        candidate=changed_action[1],
        profile=changed_action[2],
    )
    assert before_hash != candidate_scenario_semantic_identity_hash(
        stable_subject_ref=stable_subject_ref,
        proposal=changed_selector[0],
        candidate=changed_selector[1],
        profile=changed_selector[2],
    )
    assert before_hash != candidate_scenario_semantic_identity_hash(
        stable_subject_ref="sha256:" + "e" * 64,
        proposal=before[0],
        candidate=before[1],
        profile=before[2],
    )


def test_n6_stop_projection_covers_canonical_terminal_denominator():
    """Every typed terminal has a deliberate stop, abstain, or non-stop projection."""

    from polisyos.pdc import SearchTerminalKind
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleError,
        _stop_projection_decision,
    )

    expected = {
        SearchTerminalKind.A_SPEC_GAP: "not_stop",
        SearchTerminalKind.TOOL_FAILURE: "not_stop",
        SearchTerminalKind.COMPOSITION_INVALID: "not_stop",
        SearchTerminalKind.RECURSIVE_BLOCKED: "not_stop",
        SearchTerminalKind.SEARCH_CEILING_REPAIR_REQUIRED: "stop",
        SearchTerminalKind.HUMAN_DECISION_REQUIRED: "not_stop",
        SearchTerminalKind.ACQUISITION_REQUIRED: "not_stop",
        SearchTerminalKind.BUDGET_EXHAUSTED: "stop",
        SearchTerminalKind.FRONTIER_STABLE: "stop",
        SearchTerminalKind.GROUNDED_ADMISSIBLE: "stop",
        SearchTerminalKind.GROUNDED_PARTIAL_ADMISSIBLE: "stop",
        SearchTerminalKind.GROUNDED_ABSTENTION: "abstain",
    }
    assert set(expected) == set(SearchTerminalKind)

    for terminal_kind, projection in expected.items():
        if projection == "not_stop":
            with pytest.raises(
                GenerationCycleError,
                match="unsupported_stop_terminal_projection",
            ):
                _stop_projection_decision(terminal_kind.value)
        else:
            assert _stop_projection_decision(terminal_kind.value) == projection

    with pytest.raises(GenerationCycleError, match="unsupported_stop_terminal_projection"):
        _stop_projection_decision("not_a_search_terminal_kind")


@pytest.mark.parametrize("schema_version", ["v3", "v4", "v5"])
@pytest.mark.parametrize("view_profile_token", ["a", "f"])
def test_candidate_simulation_execution_versions_roundtrip_selected_views(
    schema_version,
    view_profile_token,
    tmp_path,
    monkeypatch,
):
    """Execution replay uses the selected N5 input as profile owner (V3-V5)."""
    from types import SimpleNamespace

    from polisyos.core import canon
    from polisyos.core.artifacts import artifact_manifest_profile_sha256
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationContextHandoff,
        CandidateSimulationExecutionV3,
        CandidateSimulationExecutionV4,
        CandidateSimulationExecutionV5,
        CandidateSimulationN5InputV3,
        CandidateSimulationN5InputV4,
        CandidateSimulationN5InputV5,
    )
    from polisyos.runtime.quality.generation_cycle import SimulationPortObservation
    from polisyos.runtime.quality.generation_source import (
        GenerationSourceRepository,
        N4CandidateScenarioSourceRecordV2,
    )

    token = view_profile_token

    def ref(artifact_token, kind):
        return ArtifactRef(
            artifact_id="sha256:" + artifact_token * 64,
            kind=kind,
            media_type="application/json",
            manifest_profile_sha256="sha256:" + token * 64,
        )

    job_id = f"job-{schema_version}-execution"
    run_id = f"run-{schema_version}-execution"
    tenant_id = "tenant-execution-roundtrip"
    cell_id = "cell-execution-roundtrip"
    context_hash = "sha256:" + "8" * 64
    profile_hash = "sha256:" + "9" * 64
    world_hash = "sha256:" + "b" * 64
    input_ref = ref("1", "runtime.quality.candidate_simulation_n5_input")
    n4_kind = (
        "runtime.generation_source_handoff"
        if schema_version == "v3"
        else "runtime.quality.n4_candidate_scenario_source"
    )
    n4_ref = ref("2", n4_kind)
    context_ref = ref("3", "runtime.quality.cycle_substrate_context_job")
    declaration_ref = ref("4", "runtime.quality.candidate_simulation_model_declaration")
    # Both profile-token cases refer to the same NCM bytes/ArtifactID but select
    # different well-formed manifest-profile hashes.
    ncm_ref = ref("5", "ir.ncm_spec")
    result_ref = ref("6", "polisyos.runtime.joint_simulation_result")
    materialization = SimpleNamespace(
        context_hash=context_hash,
        world_model_record_hash=world_hash,
        derived_n5_atom=SimpleNamespace(
            content_hash="sha256:" + "c" * 64,
            intervention_id=f"n5-{schema_version}",
        ),
        problem_ref="sha256:" + "d" * 64,
    )
    profile = SimpleNamespace(
        profile_id=f"profile-{schema_version}",
        content_hash=profile_hash,
    )

    input_types = {
        "v3": CandidateSimulationN5InputV3,
        "v4": CandidateSimulationN5InputV4,
        "v5": CandidateSimulationN5InputV5,
    }
    execution_types = {
        "v3": CandidateSimulationExecutionV3,
        "v4": CandidateSimulationExecutionV4,
        "v5": CandidateSimulationExecutionV5,
    }
    input_fields = {
        "n4_source_ref": n4_ref,
        "context_job_ref": context_ref,
        "job_id": job_id,
        "run_id": run_id,
        "tenant_id": tenant_id,
        "cell_id": cell_id,
        "profile": profile,
        "profile_config_ref": (
            f"runtime-config:candidate-simulation/{profile.profile_id}@{profile.content_hash}"
        ),
        "materialization": materialization,
        "original_candidate_id": f"candidate-{schema_version}",
        "original_candidate_hash": "sha256:" + "e" * 64,
        "original_n4_atom_hash": "sha256:" + "e" * 64,
    }
    if schema_version == "v5":
        input_fields.update(
            {
                "model_declaration_ref": declaration_ref,
                "ncm_ref": ncm_ref,
            }
        )
    input_record = input_types[schema_version].model_construct(**input_fields)
    handoff = CandidateSimulationContextHandoff.model_construct(
        context=SimpleNamespace(content_hash=context_hash),
        context_job_ref=context_ref,
        profile=profile,
        profile_config_ref=input_record.profile_config_ref,
        job_id=job_id,
        run_id=run_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
        model_declaration_ref=(declaration_ref if schema_version == "v5" else None),
        ncm_ref=(ncm_ref if schema_version == "v5" else None),
    )
    simulation = SimulationPortObservation(
        candidate_id=input_record.original_candidate_id,
        status="joint_simulated",
        simulation_ref="sha256:" + "f" * 64,
        simulation_result_ref=result_ref,
        k_world_ref_before=world_hash,
        k_world_ref_after=world_hash,
    )
    repository = GenerationSourceRepository(
        FileSystemCAS(tmp_path / f"execution-{schema_version}-cas")
    )
    monkeypatch.setattr(
        repository,
        f"_load_candidate_simulation_input_{schema_version}",
        lambda _ref: input_record,
    )

    execution_ref = getattr(repository, f"persist_candidate_simulation_execution_{schema_version}")(
        input_ref=input_ref,
        simulation=simulation,
        handoff=handoff,
    )
    if schema_version in {"v4", "v5"}:
        selected_profile = artifact_manifest_profile_sha256(
            repository.store.get_manifest(execution_ref)
        )
        assert execution_ref.manifest_profile_sha256 == selected_profile
        assert execution_ref.manifest_profile_sha256 is not None
    payload = canon.from_canonical_bytes(repository.store.get_bytes(execution_ref))
    execution = execution_types[schema_version].model_validate(payload)

    assert execution.authority_purpose == "candidate_scenario_n5_only"
    assert execution.n5_input_ref == input_ref
    assert execution.n4_source_ref == n4_ref
    assert execution.context_job_ref == context_ref
    assert execution.n5_result_ref == result_ref
    assert execution.job_id == job_id
    assert execution.run_id == run_id
    assert execution.tenant_id == tenant_id
    assert execution.cell_id == cell_id
    expected_inputs = {
        ("n5_input", str(input_ref.artifact_id), input_ref.manifest_profile_sha256),
        ("n4_source", str(n4_ref.artifact_id), n4_ref.manifest_profile_sha256),
        (
            "cycle_substrate_context_job",
            str(context_ref.artifact_id),
            context_ref.manifest_profile_sha256,
        ),
    }
    if schema_version == "v5":
        assert execution.model_declaration_ref == declaration_ref
        assert execution.ncm_ref == ncm_ref
        expected_inputs.update(
            {
                (
                    "candidate_model_declaration",
                    str(declaration_ref.artifact_id),
                    declaration_ref.manifest_profile_sha256,
                ),
                (
                    "candidate_ncm_spec",
                    str(ncm_ref.artifact_id),
                    ncm_ref.manifest_profile_sha256,
                ),
            }
        )
    expected_inputs.add(
        ("n5_result", str(result_ref.artifact_id), result_ref.manifest_profile_sha256)
    )
    manifest = repository.store.get_manifest(execution_ref)
    assert {
        (item.role, str(item.artifact_id), item.manifest_profile_sha256) for item in manifest.inputs
    } == expected_inputs

    # A changed selected view with the same content-addressed NCM bytes must
    # be rejected while schema and purpose markers remain unchanged.
    tampered = dict(payload)
    tampered_source_ref = dict(tampered["n4_source_ref"])
    tampered_source_ref["manifest_profile_sha256"] = "sha256:" + "7" * 64
    tampered["n4_source_ref"] = tampered_source_ref
    with pytest.raises(
        ValueError,
        match="candidate_simulation_execution_content_hash_mismatch",
    ):
        execution_types[schema_version].model_validate(tampered)

    if schema_version in {"v4", "v5"}:
        from polisyos.runtime.quality import generation_cycle as generation_cycle_module

        source_candidate = SimpleNamespace(
            candidate_id=input_record.original_candidate_id,
            atom=SimpleNamespace(content_hash=input_record.original_candidate_hash),
        )
        source_v1 = SimpleNamespace(
            context_job_ref=context_ref,
            profile=profile,
            profile_config_ref=input_record.profile_config_ref,
            candidate=source_candidate,
        )
        if schema_version == "v4":
            monkeypatch.setattr(
                repository,
                "load_candidate_scenario_source_v1",
                lambda *_args, **_kwargs: source_v1,
            )
        else:
            source_v2 = N4CandidateScenarioSourceRecordV2.model_construct(
                source_record=source_v1,
                model_declaration_ref=declaration_ref,
                ncm_ref=ncm_ref,
            )
            monkeypatch.setattr(
                repository,
                "load_candidate_scenario_source_for_n5",
                lambda *_args, **_kwargs: source_v2,
            )
        monkeypatch.setattr(
            generation_cycle_module,
            "load_joint_simulation_result",
            lambda *_args, **_kwargs: SimpleNamespace(
                receipt=SimpleNamespace(payload_hash=execution.n5_result_content_hash)
            ),
        )
        resolver = getattr(repository, f"resolve_candidate_simulation_{schema_version}")
        replayed = resolver(
            ref=execution_ref,
            expected_run_id=run_id,
            expected_job_id=job_id,
            expected_tenant_id=tenant_id,
            expected_cell_id=cell_id,
        )
        assert replayed == execution
        from polisyos.core.artifacts.canonical_profile import read_core_json_artifact

        replayed_read = _generation_source_read_result(replayed)
        assert replayed_read is not None and replayed_read.value is replayed
        expected_profile_read = read_core_json_artifact(repository.store, execution_ref)
        assert replayed_read.provenance.canon_read_status == expected_profile_read.status
        assert replayed_read.read_trace == (replayed_read.provenance,)
        assert replayed_read.provenance.source_materialization == "reader_materialized"
        assert replayed_read.provenance.producer_attestation_status == "not_established"
        assert replayed_read.provenance.selected_artifact_id == str(execution_ref.artifact_id)
        assert (
            replayed_read.provenance.selected_manifest_profile_sha256
            == execution_ref.manifest_profile_sha256
        )

        # A valid source with a different profile body cannot join the selected
        # input merely because its execution/profile reference string is alike.
        source_v1.profile = SimpleNamespace(
            profile_id="foreign-profile",
            content_hash="sha256:" + "a" * 64,
        )
        with pytest.raises(
            ValueError,
            match=f"candidate_simulation_{schema_version}_n4_source_membership_mismatch",
        ):
            resolver(
                ref=execution_ref,
                expected_run_id=run_id,
                expected_job_id=job_id,
                expected_tenant_id=tenant_id,
                expected_cell_id=cell_id,
            )
        source_v1.profile = profile

        # The profile owner is the selected input. A foreign input/profile pair
        # must fail the execution-to-input join before result replay.
        foreign_profile = SimpleNamespace(
            profile_id="foreign-profile",
            content_hash="sha256:" + "a" * 64,
        )
        foreign_input = input_record.model_copy(
            update={
                "profile": foreign_profile,
                "profile_config_ref": (
                    f"runtime-config:candidate-simulation/{foreign_profile.profile_id}"
                    f"@{foreign_profile.content_hash}"
                ),
            }
        )
        monkeypatch.setattr(
            repository,
            f"_load_candidate_simulation_input_{schema_version}",
            lambda _ref: foreign_input,
        )
        with pytest.raises(
            ValueError,
            match=f"candidate_simulation_{schema_version}_execution_input_mismatch",
        ):
            resolver(
                ref=execution_ref,
                expected_run_id=run_id,
                expected_job_id=job_id,
                expected_tenant_id=tenant_id,
                expected_cell_id=cell_id,
            )

        # Restoring the selected source and input preserves replay of the exact
        # previously written execution, including its selected CAS views.
        monkeypatch.setattr(
            repository,
            f"_load_candidate_simulation_input_{schema_version}",
            lambda _ref: input_record,
        )
        assert (
            resolver(
                ref=execution_ref,
                expected_run_id=run_id,
                expected_job_id=job_id,
                expected_tenant_id=tenant_id,
                expected_cell_id=cell_id,
            )
            == execution
        )


def test_every_generation_source_json_reader_refuses_malformed_present_profile_before_verify(
    tmp_path,
) -> None:
    """Invoke every actual JSON reader and keep malformed-present distinct from history."""
    import inspect

    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.runtime.quality import generation_source

    repository = GenerationSourceRepository(FileSystemCAS(tmp_path / "reader-class-cas"))

    def selected_ref(method_name: str) -> ArtifactRef:
        if method_name == "load_candidate_proposal":
            kind = "runtime.quality.n4_candidate_proposal"
        elif method_name == "load_candidate_credal_source_attempt":
            kind = "runtime.quality.candidate_credal_source_attempt"
        elif method_name == "load":
            kind = "runtime.generation_source_handoff"
        elif "scenario_source" in method_name:
            kind = "runtime.quality.n4_candidate_scenario_source"
        elif "model_declaration" in method_name:
            kind = "runtime.quality.candidate_simulation_model_declaration"
        else:
            kind = "runtime.quality.candidate_simulation_n5_input"
        return ArtifactRef(
            artifact_id="sha256:" + "a" * 64,
            kind=kind,
            media_type="application/json",
        )

    def invoke_actual_reader(method_name: str, method: object) -> None:
        signature = inspect.signature(method)
        arguments: dict[str, object] = {}
        for parameter in signature.parameters.values():
            if parameter.default is not inspect.Parameter.empty:
                continue
            name = parameter.name
            if name == "ref":
                ref = selected_ref(method_name)
                arguments[name] = (
                    str(ref.artifact_id)
                    if parameter.annotation is str or parameter.annotation == "str"
                    else ref
                )
            elif name in {
                "run_id",
                "expected_run_id",
                "source_run_id",
                "job_id",
                "expected_job_id",
                "tenant_id",
                "expected_tenant_id",
                "cell_id",
                "expected_cell_id",
                "raw_request",
                "profile_id",
                "profile_selection_ref",
            }:
                arguments[name] = "reader-class-fixture"
            else:
                # The selected malformed profile must refuse before these values
                # can participate in model, lineage, or authority decisions.
                arguments[name] = object()

        raw_readers = []
        with (
            patch.object(
                repository.store,
                "get_raw_manifest_bytes",
                side_effect=lambda *_args, **_kwargs: (
                    raw_readers.append(method_name) or b'{"canon":null}'
                ),
            ),
            patch.object(
                repository.store,
                "get_manifest",
                side_effect=AssertionError("typed manifest read preceded profile refusal"),
            ) as typed_manifest,
            patch.object(
                repository.store,
                "verify",
                side_effect=AssertionError("CAS verification preceded profile refusal"),
            ) as verify,
            pytest.raises(CanonicalProfileRefusalError, match="canon_profile_invalid"),
        ):
            method(**arguments)
        assert raw_readers == [method_name]
        typed_manifest.assert_not_called()
        verify.assert_not_called()

    # Discover the actual direct Core JSON readers from the class source, then
    # invoke each method through its public repository API. The AST/source scan
    # only builds the denominator; malformed-present refusal is asserted after
    # running each method with a real repository and selected Core store.
    readers = [
        (name, getattr(repository, name))
        for name, method in inspect.getmembers(
            generation_source.GenerationSourceRepository, inspect.isfunction
        )
        if "read_core_json_artifact(" in inspect.getsource(method)
    ]
    assert readers
    for name, method in readers:
        invoke_actual_reader(name, method)


def test_scenario_source_dispatch_refuses_malformed_present_profile_before_manifest_lookup(
    tmp_path,
):
    """The schema dispatcher cannot collapse a malformed selected profile to absence."""
    from polisyos.core import artifacts

    repository = GenerationSourceRepository(FileSystemCAS(tmp_path / "scenario-cas"))
    ref = repository.store.put_bytes(
        b"{}",
        artifacts.ArtifactWriteOptions(
            kind="runtime.quality.n4_candidate_scenario_source",
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name="policyos.runtime.quality.n4_candidate_scenario_source.v1",
                version="1.0",
            ),
            producer=artifacts.ProducerInfo(component="test", version="1"),
        ),
    )
    with (
        patch.object(repository.store, "get_raw_manifest_bytes", return_value=b'{"canon":null}'),
        patch.object(
            repository.store,
            "get_manifest",
            side_effect=AssertionError("manifest schema dispatch preceded raw profile parsing"),
        ) as get_manifest,
        patch.object(
            repository.store,
            "verify",
            side_effect=AssertionError("typed verification preceded raw profile parsing"),
        ) as verify,
    ):
        with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_invalid"):
            repository.load_candidate_scenario_source_for_n5(
                ref,
                expected_run_id="run",
                expected_job_id="job",
                expected_tenant_id="tenant",
                expected_cell_id="cell",
            )
        get_manifest.assert_not_called()
        verify.assert_not_called()


def test_generation_source_read_provenance_keeps_artifact_ref_subtype_identity(tmp_path):
    """Accepted ref subtypes retain the exact selected CAS identity in provenance."""
    from pydantic import BaseModel

    from polisyos.core.artifacts import (
        ArtifactRef,
        CanonInfo,
        PutOptions,
        artifact_manifest_profile_sha256,
    )
    from polisyos.core.artifacts.canonical_profile import read_core_json_artifact
    from polisyos.core.canon import to_canonical_bytes
    from polisyos.runtime.quality.generation_source import _mark_canonical_profile_read

    store = FileSystemCAS(tmp_path / "ref-subtype-cas")
    ref = store.put_bytes(
        to_canonical_bytes({"value": 1}),
        PutOptions(
            kind="test.generation-source-ref-subtype",
            media_type="application/json",
            canon=CanonInfo(),
        ),
        return_selected_profile=True,
    )

    class ScopedArtifactRef(ArtifactRef):
        pass

    selected_ref = ScopedArtifactRef.model_validate(ref.model_dump(mode="json"))
    profiled = read_core_json_artifact(store, selected_ref)

    class Result(BaseModel):
        value: int

    marked = _mark_canonical_profile_read(Result(value=1), profiled, selected_ref)
    provenance = marked._generation_source_read_provenance
    expected_profile = artifact_manifest_profile_sha256(store.get_manifest(ref))
    assert ref.manifest_profile_sha256 == expected_profile
    assert provenance.selected_artifact_id == str(ref.artifact_id)
    assert provenance.selected_manifest_profile_sha256 == expected_profile


def test_candidate_model_declaration_writer_returns_selected_profile(tmp_path):
    """Current model declarations retain the exact Core view selected by their writer."""
    from polisyos.core.artifacts import FileSystemCAS, artifact_manifest_profile_sha256
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationSyntheticModelDeclarationV1,
    )
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    fields = {
        "profile_config_ref": "runtime-config:candidate-simulation/model@sha256:" + "1" * 64,
        "profile_content_hash": "sha256:" + "1" * 64,
        "profile_selection_ref": "sha256:" + "2" * 64,
        "target_world_slot": "target",
        "outcome_variable": "outcome",
        "target_unit_id": "target-unit",
        "outcome_unit_id": "outcome-unit",
        "target_baseline": 0.0,
        "outcome_baseline": 0.0,
        "outcome_per_target_unit": 0.5,
        "outcome_noise_stddev": 0.01,
        "assumption": "declared_candidate_scm_not_empirically_grounded",
    }
    draft = CandidateSimulationSyntheticModelDeclarationV1.model_construct(
        **fields,
        content_hash="sha256:" + "0" * 64,
    )
    declaration = CandidateSimulationSyntheticModelDeclarationV1.model_validate(
        {
            **fields,
            "content_hash": gy_content_hash(
                draft.model_dump(mode="json", exclude={"content_hash"})
            ),
        }
    )
    repository = GenerationSourceRepository(FileSystemCAS(tmp_path / "model-declaration-cas"))

    ref = repository.persist_candidate_model_declaration(
        declaration=declaration,
        job_id="job-model-declaration",
        run_id="run-model-declaration",
        tenant_id="tenant-model-declaration",
        cell_id="cell-model-declaration",
    )

    expected_profile = artifact_manifest_profile_sha256(repository.store.get_manifest(ref))
    assert ref.manifest_profile_sha256 == expected_profile
    assert ref.manifest_profile_sha256 is not None
