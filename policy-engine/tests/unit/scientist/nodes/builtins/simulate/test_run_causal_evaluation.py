"""Gap-coverage tests for RunCausalEvaluationNode."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.foundry.methods.causal import PanelObservationalData
from polisyos.pdc import ArtifactRef as EvaluationArtifactRef
from polisyos.runtime.quality.evaluation_safety import (
    EvalSafetyAdmissionChallenge,
    EvalSafetyConsumerAdmissionReceipt,
    EvaluationExecutionContext,
    EvaluationInputProvenance,
    evaluation_execution_context_hash,
)
from polisyos.scientist.evidence.claims.validators import CLAIM_SPINE_FLAG
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation import (
    RunCausalEvaluationNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF,
    ARTIFACT_CLAIMS_REF,
)


def test_base_context_records_claim_owner_limitation_on_success(
    execution_context,
    minimal_state,
) -> None:
    t0 = 6
    donor_1 = np.arange(10.0, 20.0)
    donor_2 = np.arange(8.0, 18.0)
    treated = donor_1.copy()
    treated[t0:] += 4.0
    data = PanelObservationalData(
        outcome=np.vstack([treated, donor_1, donor_2]),
        treatment=np.array([1, 0, 0]),
        time_treatment=t0,
    )
    data_ref = execution_context.store.put_json(
        data.model_dump(mode="json"),
        PutOptions(
            kind="ir.observational_data",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.ObservationalData", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    state = minimal_state.model_copy(
        update={
            "observational_data_ref": data_ref,
            "causal_method_fqn": "causal.inference.synthetic_control@1.0.0",
            "params": {"random_seed": 42, CLAIM_SPINE_FLAG: True},
        }
    )

    outcome = RunCausalEvaluationNode().execute(execution_context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.details["blocker_codes"] == [
        "polisyos.eval_safety.execution_context_missing@1.0.0"
    ]
    assert "claim_ledger_status" not in outcome.state.params
    assert "claim_ledger_limitation_code" not in outcome.state.params
    assert ARTIFACT_CLAIMS_REF not in outcome.state.artifacts_index
    assert ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF not in outcome.state.artifacts_index
    assert ARTIFACT_CAUSAL_REPORT_REF not in outcome.state.artifacts_index


def test_skip_when_no_observational_data_ref(execution_context, minimal_state):
    """No observational_data_ref on state -> skip."""
    state = minimal_state.model_copy(update={"params": {}})
    assert state.observational_data_ref is None
    outcome = RunCausalEvaluationNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert any("observational_data_ref" in e.message.lower() for e in outcome.events)
    assert outcome.skip_blocker is not None
    assert outcome.skip_blocker.missing_input == "observational_data_ref"
    assert outcome.skip_blocker.blocker_code == "gy_phase2_blocked_input_producer_missing"


def test_promotion_state_injection_cannot_bypass_eval_safety(
    execution_context,
    minimal_state,
) -> None:
    """Absent, favorable, and forged promotion state leave admission unchanged."""
    data = PanelObservationalData(
        outcome=np.array([[1.0, 2.0], [1.5, 2.5]]),
        treatment=np.array([1, 0]),
        time_treatment=1,
    )
    data_ref = execution_context.store.put_json(
        data.model_dump(mode="json"),
        PutOptions(
            kind="ir.observational_data",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.ObservationalData", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    evaluation_input_ref = EvaluationArtifactRef(
        artifact_id=str(data_ref.artifact_id),
        artifact_type="observational_data",
        content_hash=str(data_ref.artifact_id),
        schema_ref="polisyos.ir.ObservationalData@1.0",
        uri="runtime://scientist/causal-observational-input",
        version="1.0.0",
    )
    certificate_ref = EvaluationArtifactRef(
        artifact_id="polisyos.test.eval_safety_certificate",
        artifact_type="eval_safety_certificate",
        content_hash="sha256:" + "c" * 64,
        schema_ref="policyos.runtime.eval_safety.certificate.v1",
        uri="runtime://eval-safety/certificate",
        version="1.0.0",
    )
    revision_head_ref = EvaluationArtifactRef(
        artifact_id="polisyos.test.eval_safety_revision_head",
        artifact_type="eval_safety_certificate_revision",
        content_hash="sha256:" + "d" * 64,
        schema_ref="policyos.runtime.eval_safety.certificate_revision.v1",
        uri="runtime://eval-safety/revision-head",
        version="1.0.0",
    )
    node = RunCausalEvaluationNode()
    safety_context = EvaluationExecutionContext(
        intake_ref=EvaluationArtifactRef(
            artifact_id="polisyos.test.causal_evaluation_intake",
            artifact_type="evaluation_attempt_intake",
            content_hash="sha256:" + "a" * 64,
            schema_ref="policyos.runtime.eval_safety.intake.v1",
            uri="runtime://eval-safety/causal-intake",
            version="1.0.0",
        ),
        evaluator_owner_id=node.spec.metadata.component_id,
        design_problem_ref="sha256:" + "1" * 64,
        evaluation_mode="field_pilot",
        candidate_ref=EvaluationArtifactRef(
            artifact_id="polisyos.test.causal_candidate",
            artifact_type="candidate",
            content_hash="sha256:" + "2" * 64,
            schema_ref="policyos.runtime.candidate.v1",
            uri="runtime://candidate/causal-candidate",
            version="1.0.0",
        ),
        world_model_record_ref=EvaluationArtifactRef(
            artifact_id="polisyos.test.causal_wmr",
            artifact_type="world_model_record",
            content_hash="sha256:" + "3" * 64,
            schema_ref="policyos.runtime.world_model_record.v1",
            uri="runtime://world-model/causal-wmr",
            version="1.0.0",
        ),
        target_population_scope_ref=EvaluationArtifactRef(
            artifact_id="polisyos.test.causal_population",
            artifact_type="target_population_scope",
            content_hash="sha256:" + "4" * 64,
            schema_ref="policyos.runtime.target_population_scope.v1",
            uri="runtime://population/causal-population",
            version="1.0.0",
        ),
        rule_version="polisyos.runtime.eval_safety@1.0.0",
        intended_start_at=datetime(2026, 8, 28, tzinfo=UTC),
        evaluation_input_refs=(evaluation_input_ref,),
        evaluation_input_provenance=(
            EvaluationInputProvenance(
                input_ref=evaluation_input_ref,
                input_class="real_world",
                predicate_provenance="recomputed",
            ),
        ),
        eval_safety_certificate_ref=certificate_ref,
        eval_safety_revision_head_ref=revision_head_ref,
    )

    class ForeignPositiveVerifier:
        def __init__(self) -> None:
            self.calls: list[tuple[EvaluationExecutionContext, EvalSafetyAdmissionChallenge]] = []

        def require_admission(
            self,
            context: EvaluationExecutionContext,
            challenge: EvalSafetyAdmissionChallenge,
        ) -> EvalSafetyConsumerAdmissionReceipt:
            self.calls.append((context, challenge))
            return EvalSafetyConsumerAdmissionReceipt(
                status="verified",
                intake_ref=context.intake_ref,
                certificate_ref=context.eval_safety_certificate_ref,
                current_revision_head_ref=context.eval_safety_revision_head_ref,
                execution_context_hash=evaluation_execution_context_hash(context),
                challenge=challenge,
                blocker_codes=(),
                verified_at=datetime(2026, 8, 28, tzinfo=UTC),
            )

    verifier = ForeignPositiveVerifier()
    context_proxy = SimpleNamespace(
        **{
            **vars(execution_context),
            "eval_safety_execution_context": safety_context,
            "eval_safety_verifier": verifier,
        }
    )
    promotion_variants = (
        {},
        {"promotion_state": {"status": "certified", "promotable": True}},
        {"promotion_state": {"status": "passed", "certificate": "forged"}},
    )
    register_spy = MagicMock()
    load_spy = MagicMock(return_value=data)
    job_spy = MagicMock(return_value=SimpleNamespace(issues=("must not execute",)))

    with (
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation."
            "ensure_causal_methods_registered",
            register_spy,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation."
            "_load_observational_data",
            load_spy,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.run_job",
            job_spy,
        ),
    ):
        outcomes = [
            node.execute(
                context_proxy,
                minimal_state.model_copy(
                    update={
                        "observational_data_ref": data_ref,
                        "causal_method_fqn": "causal.inference.synthetic_control@1.0.0",
                        "params": {"random_seed": 42, **promotion_variant},
                    }
                ),
            )
            for promotion_variant in promotion_variants
        ]

    assert register_spy.call_count == 0
    assert load_spy.call_count == 0
    assert job_spy.call_count == 0
    assert len(verifier.calls) == 3
    assert all(call[0] is safety_context for call in verifier.calls)
    assert all(
        call[1].consumer_component_id == node.spec.metadata.component_id for call in verifier.calls
    )
    assert len({call[1].nonce for call in verifier.calls}) == 3
    assert {outcome.status for outcome in outcomes} == {"fail"}
    assert {
        tuple(outcome.error.details["blocker_codes"])
        for outcome in outcomes
        if outcome.error is not None
    } == {("polisyos.eval_safety.consumer_admission_blocked@1.0.0",)}


@pytest.mark.parametrize(
    "mutation",
    ["actual_input_changed", "same_bytes_wrong_identity", "consumer_asserted"],
)
def test_actual_input_or_untrusted_provenance_blocks_before_causal_work(
    execution_context,
    minimal_state,
    mutation: str,
) -> None:
    """Actual-input identity and provenance are recomputed before verifier work."""
    data = PanelObservationalData(
        outcome=np.array([[1.0, 2.0], [1.5, 2.5]]),
        treatment=np.array([1, 0]),
        time_treatment=1,
    )
    data_ref = execution_context.store.put_json(
        data.model_dump(mode="json"),
        PutOptions(
            kind="ir.observational_data",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.ObservationalData", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    actual_ref = EvaluationArtifactRef(
        artifact_id=str(data_ref.artifact_id),
        artifact_type="observational_data",
        content_hash=str(data_ref.artifact_id),
        schema_ref="polisyos.ir.ObservationalData@1.0",
        uri="runtime://scientist/causal-observational-input",
        version="1.0.0",
    )
    context_ref = (
        actual_ref.model_copy(update={"artifact_id": "polisyos.test.same-bytes-wrong-identity"})
        if mutation == "same_bytes_wrong_identity"
        else actual_ref
    )
    predicate_provenance = "consumer_asserted" if mutation == "consumer_asserted" else "recomputed"
    node = RunCausalEvaluationNode()
    safety_context = EvaluationExecutionContext(
        intake_ref=EvaluationArtifactRef(
            artifact_id="polisyos.test.causal-mutation-intake",
            artifact_type="evaluation_attempt_intake",
            content_hash="sha256:" + "1" * 64,
            schema_ref="policyos.runtime.eval_safety.intake.v1",
            uri="runtime://eval-safety/causal-mutation-intake",
            version="1.0.0",
        ),
        evaluator_owner_id=node.spec.metadata.component_id,
        design_problem_ref="sha256:" + "2" * 64,
        evaluation_mode="field_pilot",
        candidate_ref=EvaluationArtifactRef(
            artifact_id="polisyos.test.causal-mutation-candidate",
            artifact_type="candidate",
            content_hash="sha256:" + "3" * 64,
            schema_ref="policyos.runtime.candidate.v1",
            uri="runtime://candidate/causal-mutation-candidate",
            version="1.0.0",
        ),
        world_model_record_ref=EvaluationArtifactRef(
            artifact_id="polisyos.test.causal-mutation-wmr",
            artifact_type="world_model_record",
            content_hash="sha256:" + "4" * 64,
            schema_ref="polisyos.runtime.world_model_record@1.0",
            uri="runtime://world-model/causal-mutation-wmr",
            version="1.0.0",
        ),
        target_population_scope_ref=EvaluationArtifactRef(
            artifact_id="polisyos.test.causal-mutation-population",
            artifact_type="target_population_scope",
            content_hash="sha256:" + "5" * 64,
            schema_ref="polisyos.runtime.target_population_scope@1.0",
            uri="runtime://population/causal-mutation-population",
            version="1.0.0",
        ),
        rule_version="polisyos.runtime.eval_safety@1.0.0",
        intended_start_at=datetime(2026, 8, 28, tzinfo=UTC),
        evaluation_input_refs=(context_ref,),
        evaluation_input_provenance=(
            EvaluationInputProvenance(
                input_ref=context_ref,
                input_class="real_world",
                predicate_provenance=predicate_provenance,
            ),
        ),
        eval_safety_certificate_ref=None,
        eval_safety_revision_head_ref=None,
    )

    verifier = MagicMock()
    context_proxy = SimpleNamespace(
        **{
            **vars(execution_context),
            "eval_safety_execution_context": safety_context,
            "eval_safety_verifier": verifier,
        }
    )
    changed_data = PanelObservationalData(
        outcome=np.array([[9.0, 8.0], [7.0, 6.0]]),
        treatment=np.array([0, 1]),
        time_treatment=1,
    )
    changed_ref = execution_context.store.put_json(
        changed_data.model_dump(mode="json"),
        PutOptions(
            kind="ir.observational_data",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.ObservationalData", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    state = minimal_state.model_copy(
        update={
            "observational_data_ref": changed_ref
            if mutation == "actual_input_changed"
            else data_ref,
            "causal_method_fqn": "causal.inference.synthetic_control@1.0.0",
            "params": {"random_seed": 42},
        }
    )
    register_spy = MagicMock()
    load_spy = MagicMock()
    job_spy = MagicMock()

    with (
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation."
            "ensure_causal_methods_registered",
            register_spy,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation."
            "_load_observational_data",
            load_spy,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.run_job",
            job_spy,
        ),
    ):
        outcome = node.execute(context_proxy, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.details["blocker_codes"] == [
        "polisyos.eval_safety.execution_context_binding_mismatch@1.0.0"
    ]
    assert verifier.call_count == 0
    assert register_spy.call_count == 0
    assert load_spy.call_count == 0
    assert job_spy.call_count == 0


def test_fail_when_observational_data_cannot_be_loaded(
    execution_context, minimal_state, artifact_ref_factory
):
    """observational_data_ref points to invalid artifact -> fail with ERROR_MISSING_INPUT."""
    ref = artifact_ref_factory(kind="ir.observational_data", data={"garbage": True})
    state = minimal_state.model_copy(
        update={
            "observational_data_ref": ref,
            "params": {
                "causal_method_fqn": "causal.inference.synthetic_control",
            },
        },
    )
    outcome = RunCausalEvaluationNode().execute(execution_context, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_MISSING_INPUT


def test_skip_with_no_method_fqn_defaults(execution_context, minimal_state):
    """When no method FQN and no observational data, should skip gracefully."""
    state = minimal_state.model_copy(
        update={
            "params": {},
            "causal_method_fqn": None,
        },
    )
    outcome = RunCausalEvaluationNode().execute(execution_context, state)
    assert outcome.status == "skip"


def test_fail_when_method_job_has_issues(execution_context, minimal_state, artifact_ref_factory):
    """When run_job returns issues, node returns fail with ERROR_FOUNDRY_EXECUTE_FAILED."""
    from unittest.mock import MagicMock, patch

    ref = artifact_ref_factory(kind="ir.observational_data", data={"dummy": 1})
    state = minimal_state.model_copy(
        update={
            "observational_data_ref": ref,
            "params": {
                "causal_method_fqn": "causal.inference.synthetic_control",
            },
        },
    )

    mock_job_result = MagicMock()
    mock_job_result.issues = ["convergence failure", "insufficient data"]
    mock_data = MagicMock()

    with (
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation._load_observational_data",
            return_value=mock_data,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.ensure_causal_methods_registered",
        ),
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.run_job",
            return_value=mock_job_result,
        ),
    ):
        outcome = RunCausalEvaluationNode().execute(execution_context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_FOUNDRY_EXECUTE_FAILED
    assert "Causal method job failed" in outcome.error.message


def test_method_job_carries_selected_contract_bundle_and_intake_lineage(
    execution_context,
    minimal_state,
    artifact_ref_factory,
):
    selected_ref = artifact_ref_factory(
        kind="foundry.ukraine_method_input",
        data={"outcome": [[1, 2], [2, 3]]},
    )
    bundle_ref = artifact_ref_factory(
        kind="foundry.ukraine_method_input_bundle",
        data={"contracts": {}},
    )
    intake_ref = artifact_ref_factory(
        kind="foundry.ukraine_intake_receipt",
        data={"validated_contracts": {}},
    )
    state = minimal_state.model_copy(
        update={
            "observational_data_ref": selected_ref,
            "causal_method_fqn": "causal.inference.did.standard@1.0.0",
            "inputs": {
                "ukraine_selected_foundry_method_contract_ref": selected_ref,
                "ukraine_foundry_method_input_bundle_ref": bundle_ref,
            },
            "artifacts_index": {"ukraine_foundry_intake_receipt_ref": intake_ref},
        }
    )
    captured_specs = []
    mock_job_result = MagicMock()
    mock_job_result.issues = ["stop after inspecting lineage"]

    def _capture(spec, **kwargs):
        del kwargs
        captured_specs.append(spec)
        return mock_job_result

    with (
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation._load_observational_data",
            return_value=MagicMock(),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.ensure_causal_methods_registered",
        ),
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.run_job",
            side_effect=_capture,
        ),
    ):
        outcome = RunCausalEvaluationNode().execute(execution_context, state)

    assert outcome.status == "fail"
    assert len(captured_specs) == 1
    assert captured_specs[0].input_refs == {
        "ukraine_selected_method_contract": selected_ref,
        "ukraine_method_input_bundle": bundle_ref,
        "ukraine_intake_receipt": intake_ref,
    }


def test_fail_when_method_output_missing_report(
    execution_context, minimal_state, artifact_ref_factory
):
    """When run_job returns no issues but output has no report, node returns fail."""
    from unittest.mock import MagicMock, patch

    ref = artifact_ref_factory(kind="ir.observational_data", data={"dummy": 1})
    state = minimal_state.model_copy(
        update={
            "observational_data_ref": ref,
            "params": {
                "causal_method_fqn": "causal.inference.synthetic_control",
            },
        },
    )

    mock_job_result = MagicMock()
    mock_job_result.issues = []
    mock_job_result.final_state = {"no_report_key": True}
    mock_data = MagicMock()

    with (
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation._load_observational_data",
            return_value=mock_data,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.ensure_causal_methods_registered",
        ),
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.run_job",
            return_value=mock_job_result,
        ),
    ):
        outcome = RunCausalEvaluationNode().execute(execution_context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_FOUNDRY_EXECUTE_FAILED
    assert "missing report" in outcome.error.message


def test_assertion_in_observational_data_load_is_not_swallowed(
    execution_context, minimal_state, artifact_ref_factory
):
    ref = artifact_ref_factory(kind="ir.observational_data", data={"dummy": 1})
    state = minimal_state.model_copy(
        update={
            "observational_data_ref": ref,
            "params": {
                "causal_method_fqn": "causal.inference.synthetic_control",
            },
        },
    )

    with (
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.ensure_causal_methods_registered",
        ),
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation._load_observational_data",
            side_effect=AssertionError("observational invariant"),
        ),
    ):
        with pytest.raises(AssertionError, match="observational invariant"):
            RunCausalEvaluationNode().execute(execution_context, state)


def test_fail_when_method_output_report_is_invalid(
    execution_context, minimal_state, artifact_ref_factory
):
    ref = artifact_ref_factory(kind="ir.observational_data", data={"dummy": 1})
    state = minimal_state.model_copy(
        update={
            "observational_data_ref": ref,
            "params": {
                "causal_method_fqn": "causal.inference.synthetic_control",
            },
        },
    )

    mock_job_result = MagicMock()
    mock_job_result.issues = []
    mock_job_result.final_state = {"report": {"broken": True}}
    mock_job_result.method_result_ref = None
    mock_job_result.method_evidence_ref = None
    mock_data = MagicMock()

    with (
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation._load_observational_data",
            return_value=mock_data,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.ensure_causal_methods_registered",
        ),
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.run_job",
            return_value=mock_job_result,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.CausalEffectReport.model_validate",
            side_effect=ValueError("bad report"),
        ),
    ):
        outcome = RunCausalEvaluationNode().execute(execution_context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_FOUNDRY_EXECUTE_FAILED
    assert "report is invalid" in outcome.error.message
