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

import pytest

from polisyos.core import artifacts
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.acquisition_evaluation import (
    CandidateAcquisitionEvaluationBasis,
    CandidateAcquisitionEvaluationDecision,
    issue_candidate_acquisition_evaluation_basis,
    issue_candidate_acquisition_evaluation_decision,
    persist_acquisition_evaluation_artifact,
    read_acquisition_evaluation_artifact,
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
        assert basis.reason_codes == prepared.reason_codes
        assert basis.limitations == limitations
        assert not basis.observed_admission and not basis.publication_authority
        encoded = exact_n5_content_bytes(prepared.effective_values)
        assert bytes.fromhex(basis.effective_native_values_hex) == encoded
        assert basis.effective_values_sha256 == "sha256:" + hashlib.sha256(encoded).hexdigest()
        assert basis.content_hash == exact_n5_content_hash(
            basis.model_dump(mode="json", exclude={"content_hash"})
        )

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
            decision = issue_candidate_acquisition_evaluation_decision(**decision_inputs)
            assert issue_candidate_acquisition_evaluation_decision(**decision_inputs) == decision
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
