"""Candidate issuance over real source preparation and CAS/event owners.

Action/intent parents and the subject scope are explicit component fixtures.
They do not establish protected execution, a selected proposal, an N5 result,
or permission to retain an evaluation. The actual source preparation below
produces the retained not-established reason; no diagnostic is manufactured.
"""

from __future__ import annotations

import hashlib
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core import artifacts
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.acquisition_evaluation import (
    CANDIDATE_N5_CLOSURE_RESIDUALS_V2,
    CandidateAcquisitionEvaluationBasis,
    CandidateAcquisitionEvaluationBasisV2,
    CandidateAcquisitionEvaluationDecision,
    CandidateAcquisitionEvaluationDecisionV2,
    GenericModelInputEvaluationBasisV1,
    GenericModelInputSelectedEvaluation,
    _candidate_evaluation_role_event_id,
    basis_exact_values_equal,
    issue_candidate_acquisition_evaluation_basis,
    issue_candidate_acquisition_evaluation_decision,
    issue_generic_model_input_evaluation_decision,
    persist_acquisition_evaluation_artifact,
    read_acquisition_evaluation_artifact,
    read_candidate_acquisition_evaluation_basis_artifact,
    read_candidate_acquisition_evaluation_decision_artifact,
    reconcile_generic_model_input_evaluation_completion,
)
from polisyos.runtime.quality.candidate_source_basis import prepare_candidate_source_basis_values
from polisyos.runtime.quality.cycle_substrate import cycle_job_design_problem_ref
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.runtime.quality.joint_simulation_horizon import prepare_joint_simulation_configuration
from polisyos.runtime.quality.n5_execution_basis import (
    exact_n5_content_bytes,
    exact_n5_content_hash,
)
from tests.unit.runtime.quality.test_candidate_acquisition_world import (
    CELL_ID,
    TENANT_ID,
    TRANSACTION_TIME,
    _candidate_world_case,
)
from tests.unit.runtime.quality.test_candidate_source_basis import _files, _inputs


def test_generic_basis_component_roundtrips_selected_cas_and_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A synthetic, explicitly unavailable basis has an exact durable reader."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.runtime.quality import model_input_successor_selection
    from polisyos.runtime.quality.acquisition_route_loop import VerifiedModelInputRoutingOrigin

    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        store = FileSystemCAS(tmp_path / "generic-cas")

        def component_ref(kind: str, label: str = "default") -> artifacts.ArtifactRef:
            return store.put_json(
                {"component_fixture": kind, "label": label, "source_authority": "not_established"},
                artifacts.ArtifactWriteOptions(kind=kind, media_type="application/json"),
                return_selected_profile=True,
            )

        input_ref = component_ref("runtime.quality.generic_cycle_simulation_n5_input")
        selection_ref = component_ref("runtime.quality.model_input_successor_selection")
        state_ref = component_ref("foundry.state_snapshot")
        content = exact_n5_content_bytes({"component_only": True})
        payload = {
            "schema_version": "GenericModelInputEvaluationBasis@1.0",
            "authority_purpose": "candidate_evaluation_retention_only",
            "comparison_profile": "generic_program_graph_declared_numerical_v1",
            "basis_role": "blocked",
            "tenant_id": TENANT_ID,
            "cell_id": CELL_ID,
            "run_id": "generic-component-run",
            "source_job_id": "generic-source-job",
            "action_job_id": "generic-action-job",
            "route_id": "sha256:" + "1" * 64,
            "design_problem_ref": "sha256:" + "2" * 64,
            "design_problem_basis_ref": "sha256:" + "3" * 64,
            "candidate_id": "generic-component-candidate",
            "input_ref": input_ref.model_dump(mode="json"),
            "semantic_successor_ref": selection_ref.model_dump(mode="json"),
            "bound_state_snapshot_ref": state_ref.model_dump(mode="json"),
            "evaluation": None,
            "prospective_basis_ref": None,
            "comparison_decision_ref": None,
            "predicate_provenance": "not_established",
            "reason_codes": ["component_source_not_established"],
            "limitations": ["synthetic_component_only"],
            "closure_residuals": list(CANDIDATE_N5_CLOSURE_RESIDUALS_V2),
            "observed_admission": False,
            "publication_authority": False,
            "numerical_intent_hex": content.hex(),
            "numerical_intent_sha256": "sha256:" + hashlib.sha256(content).hexdigest(),
        }
        record = GenericModelInputEvaluationBasisV1.model_validate(
            {**payload, "content_hash": exact_n5_content_hash(payload)}
        )
        with closing(
            ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "generic-control.sqlite3")
        ) as control:
            events = RuntimeDiagnosticEventLog(store=control, artifact_store=store)
            ref = persist_acquisition_evaluation_artifact(
                store=store, event_log=events, record=record
            )

            def read(selected: artifacts.ArtifactRef) -> GenericModelInputEvaluationBasisV1:
                result = read_acquisition_evaluation_artifact(
                    store=store,
                    event_log=events,
                    ref=selected,
                    record_type=GenericModelInputEvaluationBasisV1,
                )
                assert type(result) is GenericModelInputEvaluationBasisV1
                return result

            assert read(ref) == record
            foreign = ref.model_copy(update={"manifest_profile_sha256": "sha256:" + "0" * 64})
            with pytest.raises((FileNotFoundError, OSError, ValueError)):
                read(foreign)
            with pytest.raises(ValueError, match="artifact_owner_mismatch"):
                read_acquisition_evaluation_artifact(
                    store=store,
                    event_log=events,
                    ref=ref,
                    record_type=CandidateAcquisitionEvaluationBasis,
                )
            blob = store._member_path(ref.artifact_id, "blob", None)
            held = blob.with_name(blob.name + ".temporarily-unavailable")
            blob.rename(held)
            try:
                with pytest.raises((FileNotFoundError, OSError, ValueError)):
                    read(ref)
            finally:
                held.rename(blob)
            assert read(ref) == record

            # The selection and origin below are explicitly component fixtures;
            # the selected basis and event are real. These negatives never admit
            # a fake V5 as an initial frontier.
            blocked_ref = component_ref("runtime.quality.generic_cycle_simulation_n5_execution")
            compiled_ref = component_ref("runtime.compiled_recursive_generation_cycle")
            routing_ref = component_ref("runtime.quality.model_input_routing_report")
            use_ref = component_ref("runtime.quality.model_input_routing_use_decision")
            selection = SimpleNamespace(
                tenant_id=TENANT_ID,
                cell_id=CELL_ID,
                run_id=payload["run_id"],
                source_job_id=payload["source_job_id"],
                action_job_id=payload["action_job_id"],
                route_id=payload["route_id"],
                blocked_execution_ref=blocked_ref,
                routing_report_ref=routing_ref,
                compiled_ref=compiled_ref,
                routing_use_decision_ref=use_ref,
            )
            origin = VerifiedModelInputRoutingOrigin(
                tenant_id=TENANT_ID,
                cell_id=CELL_ID,
                run_id=payload["run_id"],
                source_job_id=payload["source_job_id"],
                source_payload_ref="component-only",
                capability_manifest_ref="component-only",
                compiled_ref=compiled_ref,
                terminal_event_id="component-only",
                generation_run=object(),
                source_cycle=SimpleNamespace(
                    design_problem_ref=payload["design_problem_ref"],
                    selected_candidate_ref=payload["candidate_id"],
                ),
                design_problem_basis=object(),
                n5_execution_ref=blocked_ref,
                n5_expectation=SimpleNamespace(
                    design_problem_ref=payload["design_problem_basis_ref"], input_ref=input_ref
                ),
                selected_basis=object(),
                routing_report_ref=routing_ref,
                routing_report=object(),
            )
            monkeypatch.setattr(
                model_input_successor_selection,
                "read_model_input_successor_selection",
                lambda *_args: selection,
            )
            initial = {
                "store": store,
                "event_log": events,
                "origin": origin,
                "prior_origin": None,
                "controller": object(),
                "semantic_successor_ref": selection_ref,
                "current_basis_ref": ref,
                "prior_basis_ref": None,
                "prior_evaluation": None,
                "decision_kind": "initial",
                "comparison_result": None,
                "reason_codes": (),
                "expected_frontier_revision": 0,
                "expected_frontier_ref": None,
                "generated_at": TRANSACTION_TIME.isoformat(),
            }
            with pytest.raises(ValueError, match="initial_decision_invalid"):
                issue_generic_model_input_evaluation_decision(**initial)
            prospective_payload = {
                **payload,
                "basis_role": "prospective",
                "predicate_provenance": "recomputed",
                "reason_codes": [],
            }
            prospective = GenericModelInputEvaluationBasisV1.model_validate(
                {**prospective_payload, "content_hash": exact_n5_content_hash(prospective_payload)}
            )
            prospective_ref = persist_acquisition_evaluation_artifact(
                store=store, event_log=events, record=prospective
            )
            with pytest.raises(ValueError, match="initial_decision_invalid"):
                issue_generic_model_input_evaluation_decision(
                    **{**initial, "current_basis_ref": prospective_ref}
                )
            selection.action_job_id = "foreign-action"
            with pytest.raises(ValueError, match="decision_current_basis_mismatch"):
                issue_generic_model_input_evaluation_decision(**initial)
            selection.action_job_id = payload["action_job_id"]

            second_selection = component_ref(
                "runtime.quality.model_input_successor_selection", "incomplete-v5"
            )
            incomplete_evaluation = GenericModelInputSelectedEvaluation(
                input_ref=input_ref,
                execution_ref=component_ref(
                    "runtime.quality.generic_cycle_simulation_n5_execution", "incomplete-v5"
                ),
                result_ref=component_ref("polisyos.runtime.joint_simulation_result"),
                semantic_successor_ref=second_selection,
                action_job_id=payload["action_job_id"],
            )
            incomplete_payload = {
                **payload,
                "basis_role": "evaluated",
                "semantic_successor_ref": second_selection.model_dump(mode="json"),
                "evaluation": incomplete_evaluation.model_dump(mode="json"),
                "predicate_provenance": "recomputed",
                "reason_codes": [],
            }
            incomplete = GenericModelInputEvaluationBasisV1.model_validate(
                {**incomplete_payload, "content_hash": exact_n5_content_hash(incomplete_payload)}
            )
            incomplete_ref = persist_acquisition_evaluation_artifact(
                store=store, event_log=events, record=incomplete
            )
            comparison_ref = component_ref("runtime_quality.acquisition_evaluation_decision")
            unpaired_payload = {
                **incomplete_payload,
                "prospective_basis_ref": prospective_ref.model_dump(mode="json"),
            }
            with pytest.raises(ValueError, match="basis_comparison_link_invalid"):
                GenericModelInputEvaluationBasisV1.model_validate(
                    {**unpaired_payload, "content_hash": exact_n5_content_hash(unpaired_payload)}
                )
            with pytest.raises(ValueError, match="completion_not_established"):
                reconcile_generic_model_input_evaluation_completion(
                    store=store,
                    event_log=events,
                    origin=origin,
                    prior_origin=None,
                    controller=object(),
                    comparison_decision_ref=comparison_ref,
                    evaluated_basis_ref=incomplete_ref,
                )
            ready_shape = {
                **initial,
                "semantic_successor_ref": second_selection,
                "current_basis_ref": incomplete_ref,
            }
            for invalid in (
                {"prior_basis_ref": ref},
                {"expected_frontier_revision": 1, "expected_frontier_ref": "sha256:" + "4" * 64},
            ):
                with pytest.raises(ValueError, match="initial_decision_invalid"):
                    issue_generic_model_input_evaluation_decision(**{**ready_shape, **invalid})
            # Even a shape-valid synthetic V5 cannot pass the native source owner.
            with pytest.raises((OSError, RuntimeError, TypeError, ValueError)):
                issue_generic_model_input_evaluation_decision(**ready_shape)


def test_candidate_issuers_preserve_actual_source_ne_through_selected_cas_and_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Actual preparation failure remains NE; hashes and selected views stay binding."""
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        case = _candidate_world_case(tmp_path, monkeypatch)
        inputs = _inputs(case)
        prepared = prepare_candidate_source_basis_values(
            store=case.store, problem=case.problem, inputs=inputs
        )
        assert prepared.predicate_provenance == "not_established"
        assert prepared.reason_codes == ("acquisition_world_skg_consumed_values_not_established",)
        limitations = tuple(
            dict.fromkeys(
                (
                    *case.source_case.source.limitations,
                    *inputs.configured_profile.limitations,
                    *case.base.record.limitations.admissibility_blockers,
                )
            )
        )

        def component_parent(kind: str, name: str) -> artifacts.ArtifactRef:
            return case.store.put_json(
                {"component_fixture": name, "protected_execution_not_established": True},
                artifacts.ArtifactWriteOptions(kind=kind, media_type="application/json"),
                return_selected_profile=True,
            )

        action = component_parent("runtime_quality.acquisition_candidate_action_receipt", "action")
        intent = component_parent("runtime_quality.acquisition_candidate_world_intent", "intent")
        source = case.source_case.source
        problem_ref = cycle_job_design_problem_ref(case.problem)
        scope = {
            "tenant_id": TENANT_ID,
            "cell_id": CELL_ID,
            "run_id": source.run_id,
            "source_job_id": source.job_id,
            "action_job_id": "issuance-component-action",
            "action_generation": 1,
            "route_id": str(case.source_case.source_ref.artifact_id),
            "design_problem_ref": problem_ref,
            "design_problem_basis_ref": problem_ref,
            "candidate_id": case.source_case.candidate_digest,
            "source_candidate_content_hash": case.source_case.candidate_digest,
            "candidate_action_ref": action,
            "candidate_world_intent_ref": intent,
            "candidate_source_ref": case.source_case.source_ref,
        }
        basis_inputs = {
            **scope,
            "preparation_inputs": inputs,
            "prepared_n5_configuration": prepare_joint_simulation_configuration(),
            "basis_role": "prospective",
            "values": prepared.effective_values,
            "predicate_provenance": prepared.predicate_provenance,
            "reason_codes": prepared.reason_codes,
            "limitations": limitations,
        }
        before = _files(case.store.root)
        basis = issue_candidate_acquisition_evaluation_basis(**basis_inputs)
        assert issue_candidate_acquisition_evaluation_basis(**basis_inputs) == basis
        assert _files(case.store.root) == before
        assert basis.predicate_provenance == "not_established"
        assert "reuse_occurrence_ref" not in basis.model_dump(mode="json")
        assert basis.reason_codes == prepared.reason_codes
        assert basis.limitations == limitations
        assert not basis.observed_admission and not basis.publication_authority
        encoded = exact_n5_content_bytes(prepared.effective_values)
        assert bytes.fromhex(basis.effective_native_values_hex) == encoded
        assert basis.effective_values_sha256 == "sha256:" + hashlib.sha256(encoded).hexdigest()
        assert basis.content_hash == exact_n5_content_hash(
            basis.model_dump(mode="json", exclude={"content_hash"})
        )
        v2 = issue_candidate_acquisition_evaluation_basis(**basis_inputs, basis_version="2.0")
        assert type(v2) is CandidateAcquisitionEvaluationBasisV2
        assert v2.comparison_profile == "candidate_source_declared_numerical_basis_v2"
        assert v2.closure_residuals == CANDIDATE_N5_CLOSURE_RESIDUALS_V2
        assert not v2.observed_admission and not v2.publication_authority
        assert not basis_exact_values_equal(basis, v2)
        altered = v2.model_dump(mode="json")
        altered["closure_residuals"] = []
        altered["content_hash"] = exact_n5_content_hash(
            {name: value for name, value in altered.items() if name != "content_hash"}
        )
        with pytest.raises(ValueError, match="closure_residuals_mismatch"):
            CandidateAcquisitionEvaluationBasisV2.model_validate(altered)

        with closing(
            ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
        ) as control:
            events = RuntimeDiagnosticEventLog(store=control, artifact_store=case.store)
            basis_ref = persist_acquisition_evaluation_artifact(
                store=case.store, event_log=events, record=basis
            )
            assert (
                read_acquisition_evaluation_artifact(
                    store=case.store,
                    event_log=events,
                    ref=basis_ref,
                    record_type=CandidateAcquisitionEvaluationBasis,
                )
                == basis
            )
            v2_action = component_parent(
                "runtime_quality.acquisition_candidate_action_receipt", "v2-action"
            )
            v2_scoped_basis = issue_candidate_acquisition_evaluation_basis(
                **{**basis_inputs, "candidate_action_ref": v2_action}, basis_version="2.0"
            )
            v2_ref = persist_acquisition_evaluation_artifact(
                store=case.store, event_log=events, record=v2_scoped_basis
            )
            assert (
                read_candidate_acquisition_evaluation_basis_artifact(
                    store=case.store, event_log=events, ref=v2_ref
                )
                == v2_scoped_basis
            )
            with pytest.raises(ValueError, match="artifact_owner_mismatch"):
                read_acquisition_evaluation_artifact(
                    store=case.store,
                    event_log=events,
                    ref=v2_ref,
                    record_type=CandidateAcquisitionEvaluationBasis,
                )
            decision_inputs = {
                **scope,
                "compiled_ref": str(case.source_case.binding.compiler_report_ref.artifact_id),
                "current_basis_ref": basis_ref,
                "prior_basis_ref": None,
                "prior_evaluation": None,
                "comparison_result": "not_established",
                "predicate_provenance": "not_established",
                "reason_codes": prepared.reason_codes,
                "expected_frontier_revision": 0,
                "expected_frontier_ref": None,
                "generated_at": TRANSACTION_TIME.isoformat(),
            }
            decision_v2 = issue_candidate_acquisition_evaluation_decision(
                **{
                    **decision_inputs,
                    "candidate_action_ref": v2_action,
                    "current_basis_ref": v2_ref,
                },
                decision_version="2.0",
            )
            assert type(decision_v2) is CandidateAcquisitionEvaluationDecisionV2
            assert decision_v2.comparison_rule == "candidate-source-declared-numerical-basis.v2"
            decision_v2_ref = persist_acquisition_evaluation_artifact(
                store=case.store, event_log=events, record=decision_v2
            )
            assert (
                read_candidate_acquisition_evaluation_decision_artifact(
                    store=case.store, event_log=events, ref=decision_v2_ref
                )
                == decision_v2
            )
            decision = issue_candidate_acquisition_evaluation_decision(**decision_inputs)
            assert issue_candidate_acquisition_evaluation_decision(**decision_inputs) == decision
            assert "reuse_occurrence_ref" not in decision.model_dump(mode="json")
            assert decision.reason_codes == prepared.reason_codes
            assert decision.generated_at == TRANSACTION_TIME.isoformat()
            assert not decision.observed_admission and not decision.publication_authority
            selected = persist_acquisition_evaluation_artifact(
                store=case.store, event_log=events, record=decision
            )
            assert (
                read_acquisition_evaluation_artifact(
                    store=case.store,
                    event_log=events,
                    ref=selected,
                    record_type=CandidateAcquisitionEvaluationDecision,
                )
                == decision
            )

            # A repeated reuse names a new action occurrence without claiming
            # that the physical source action or its budget happened again.
            # Both basis and decision events must remain independently readable.
            occurrences = [
                component_parent("runtime_quality.candidate_experiment_reuse_occurrence", name)
                for name in ("reuse-a", "reuse-b")
            ]
            legacy_basis_event = _candidate_evaluation_role_event_id(action, "prospective_basis")
            assert legacy_basis_event == (
                "evt_candidate_evaluation_prospective_basis_"
                + hashlib.sha256(exact_n5_content_bytes(action)).hexdigest()
            )
            reuse_events: list[str] = []
            for generation, occurrence_ref in enumerate(occurrences, start=2):
                reuse_basis = issue_candidate_acquisition_evaluation_basis(
                    **{
                        **basis_inputs,
                        "action_job_id": f"reuse-{generation}",
                        "action_generation": generation,
                        "reuse_occurrence_ref": occurrence_ref,
                    }
                )
                assert reuse_basis.candidate_action_ref == action
                reuse_basis_ref = persist_acquisition_evaluation_artifact(
                    store=case.store, event_log=events, record=reuse_basis
                )
                assert (
                    read_acquisition_evaluation_artifact(
                        store=case.store,
                        event_log=events,
                        ref=reuse_basis_ref,
                        record_type=CandidateAcquisitionEvaluationBasis,
                    )
                    == reuse_basis
                )
                reuse_decision = issue_candidate_acquisition_evaluation_decision(
                    **{
                        **decision_inputs,
                        "action_job_id": f"reuse-{generation}",
                        "action_generation": generation,
                        "current_basis_ref": reuse_basis_ref,
                        "reuse_occurrence_ref": occurrence_ref,
                    }
                )
                reuse_decision_ref = persist_acquisition_evaluation_artifact(
                    store=case.store, event_log=events, record=reuse_decision
                )
                assert (
                    read_acquisition_evaluation_artifact(
                        store=case.store,
                        event_log=events,
                        ref=reuse_decision_ref,
                        record_type=CandidateAcquisitionEvaluationDecision,
                    )
                    == reuse_decision
                )
                reuse_events.append(
                    _candidate_evaluation_role_event_id(
                        action, "prospective_basis", reuse_occurrence_ref=occurrence_ref
                    )
                )
            assert len({legacy_basis_event, *reuse_events}) == 3
            occurrence_manifest = case.store.get_manifest(occurrences[0])
            sibling_occurrence = case.store.put_bytes(
                case.store.get_bytes(occurrences[0]),
                artifacts.ArtifactWriteOptions(
                    kind=occurrences[0].kind,
                    media_type=occurrences[0].media_type,
                    schema=occurrence_manifest.artifact_schema,
                    canon=occurrence_manifest.canon,
                    inputs=occurrence_manifest.inputs,
                    governance=occurrence_manifest.governance,
                    tenant_context=occurrence_manifest.tenant_context,
                    producer=artifacts.ProducerInfo(
                        component="test.foreign-occurrence", version="1"
                    ),
                ),
                return_selected_profile=True,
            )
            assert sibling_occurrence.artifact_id == occurrences[0].artifact_id
            assert (
                sibling_occurrence.manifest_profile_sha256 != occurrences[0].manifest_profile_sha256
            )
            assert (
                _candidate_evaluation_role_event_id(
                    action, "prospective_basis", reuse_occurrence_ref=sibling_occurrence
                )
                != reuse_events[0]
            )
            with pytest.raises(
                ValueError, match="candidate_evaluation_basis_reuse_occurrence_invalid"
            ):
                issue_candidate_acquisition_evaluation_basis(
                    **{
                        **basis_inputs,
                        "reuse_occurrence_ref": occurrences[0].model_copy(
                            update={"manifest_profile_sha256": None}
                        ),
                    }
                )

            # Incomplete prior selection cannot be relabeled as a successful
            # comparison; issuer defaults never invent a reason or a frontier.
            with pytest.raises(ValueError, match="candidate_evaluation_decision_prior_missing"):
                issue_candidate_acquisition_evaluation_decision(
                    **{
                        **decision_inputs,
                        "comparison_result": "different",
                        "predicate_provenance": "recomputed",
                        "reason_codes": (),
                    }
                )
            with pytest.raises(
                ValueError, match="candidate_evaluation_decision_selected_ref_invalid"
            ):
                issue_candidate_acquisition_evaluation_decision(
                    **{
                        **decision_inputs,
                        "current_basis_ref": basis_ref.model_copy(
                            update={"manifest_profile_sha256": None}
                        ),
                    }
                )

        with pytest.raises(ValueError, match="candidate_evaluation_basis_predicate_mismatch"):
            issue_candidate_acquisition_evaluation_basis(**{**basis_inputs, "reason_codes": ()})
        with pytest.raises(ValueError, match="candidate_evaluation_actual_outcome_incomplete"):
            issue_candidate_acquisition_evaluation_basis(
                **{**basis_inputs, "basis_role": "evaluated"}
            )
        with pytest.raises(ValueError, match="candidate_evaluation_issuance_reasons_invalid"):
            issue_candidate_acquisition_evaluation_basis(**{**basis_inputs, "reason_codes": ("",)})

        manifest = case.store.get_manifest(case.source_case.source_ref)
        sibling = case.store.put_bytes(
            case.store.get_bytes(case.source_case.source_ref),
            artifacts.ArtifactWriteOptions(
                kind=case.source_case.source_ref.kind,
                media_type=case.source_case.source_ref.media_type,
                schema=manifest.artifact_schema,
                canon=manifest.canon,
                inputs=manifest.inputs,
                governance=manifest.governance,
                tenant_context=manifest.tenant_context,
                producer=artifacts.ProducerInfo(component="test.foreign-source-view", version="1"),
            ),
            return_selected_profile=True,
        )
        assert sibling.artifact_id == case.source_case.source_ref.artifact_id
        assert (
            sibling.manifest_profile_sha256 != case.source_case.source_ref.manifest_profile_sha256
        )
        with pytest.raises(ValueError, match="candidate_evaluation_basis_source_mismatch"):
            issue_candidate_acquisition_evaluation_basis(
                **{**basis_inputs, "candidate_source_ref": sibling}
            )

        corrupt = basis.model_dump(mode="json")
        corrupt["effective_native_values_hex"] = exact_n5_content_bytes({"changed": True}).hex()
        with pytest.raises(ValueError, match="candidate_evaluation_basis_values_hash_mismatch"):
            CandidateAcquisitionEvaluationBasis.model_validate(corrupt)


@pytest.mark.parametrize(
    ("field", "changed", "expected_error"),
    [
        ("world_model_record_content_hash", "sha256:" + "b" * 64, "wmr_mismatch"),
        ("atom_ids", ("foreign-atom",), "atom_binding_mismatch"),
        ("selected_outcomes", ("foreign-outcome",), "selected_outcomes_binding_mismatch"),
    ],
)
def test_selected_result_bindings_reject_constructed_or_mutated_values(
    field, changed, expected_error
) -> None:
    """The reused semantic validator still checks actual values, not a read marker."""
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleError,
        _validate_loaded_joint_simulation_result,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationResult

    # Only refusal is tested here. This deliberately incomplete construction
    # cannot stand in for the canonical CAS/receipt read exercised by the owner.
    values = {
        "uncertainty_kind": "K_sim",
        "state_consumption": None,
        "world_model_record_content_hash": "sha256:" + "a" * 64,
        "atom_ids": ("selected-atom",),
        "selected_outcomes": ("selected-outcome",),
    }
    for result in (
        JointSimulationResult.model_construct(**{**values, field: changed}),
        JointSimulationResult.model_construct(**values).model_copy(update={field: changed}),
    ):
        with pytest.raises(GenerationCycleError, match=expected_error):
            _validate_loaded_joint_simulation_result(
                result,
                expected_world_model_record_content_hash=values["world_model_record_content_hash"],
                expected_atom_ids=values["atom_ids"],
                expected_selected_outcomes=values["selected_outcomes"],
            )
