"""Fresh G provider-bound identification counterexamples; no invented verifier."""
from __future__ import annotations

import json

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.governance.passes.base import IssueSeverity, PassContext
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    EstimationStatus,
    load_causal_effect_report,
    persist_causal_effect_report,
    ProofBundle,
    persist_proof_bundle,
)
from polisyos.ir.analytics.uncertainty import (
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
)
from polisyos.scientist.governance.passes.confidence_pass import ConfidencePass
from polisyos.core.governance.profiles import ValidationProfile


CASES = {
    "missing": {},
    "absent_ref": {"identification_proof_ref": "sha256:" + "a" * 64},
    "self_stamped": {
        "proof_status": "identified",
        "predicate_provenance": "recomputed",
        "verifier_role": "system_verifier",
        "gate_eligible": True,
    },
    "wrong_source": {"identified": True, "source_sha": "b" * 40},
    "wrong_graph": {"identified": True, "graph_ref": "sha256:" + "c" * 64},
    "wrong_estimand": {"identified": True, "estimand": "E[Z|do(W=1)]"},
    "wrong_target": {"identified": True, "target_population": "other_population"},
}


def _report(metadata: dict[str, object]) -> CausalEffectReport:
    return CausalEffectReport(
        method=CausalMethod.DIFFERENCE_IN_DIFFERENCES,
        status=EstimationStatus.SUCCESS,
        estimand="E[Y(1)-Y(0)|target_population]",
        point_estimate=10.0,
        confidence_interval=(9.9, 10.1),
        confidence_level=0.95,
        inference_method="asymptotic",
        sample_size=100,
        n_treated=50,
        n_control=50,
        pre_periods=2,
        post_periods=2,
        metadata={
            "parallel_trends_identified": True,
            "gate_eligible": True,
            "identification_admission": metadata,
        },
    )


@pytest.mark.parametrize("case", CASES)
def test_unverified_identification_stays_nongating_at_persisted_consumer(
    tmp_path, case: str
) -> None:
    store_path = tmp_path / "cas"
    writer = FileSystemCAS(store_path)
    report_ref = persist_causal_effect_report(writer, _report(CASES[case]))
    # Reopen actual persisted bytes through fresh reader instances; keep SUCCESS,
    # numerical interval and self-attested estimator markers unchanged.
    reader = FileSystemCAS(store_path)
    reopened_report = load_causal_effect_report(reader, report_ref)
    assert reopened_report.status is EstimationStatus.SUCCESS
    assert reopened_report.confidence_interval == (9.9, 10.1)
    envelope = reopened_report.to_uncertainty_envelope()
    assert envelope is not None
    envelope_ref = persist_uncertainty_envelope(writer, envelope)
    fresh_reader = FileSystemCAS(store_path)
    persisted_envelope = load_uncertainty_envelope(fresh_reader, envelope_ref)
    ctx = PassContext(
        ir=None,
        state={"_store": fresh_reader, "artifacts_index": {"causal_envelope_ref": envelope_ref}},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id=f"identification-{case}",
    )
    issues = ConfidencePass().validate(ctx)
    blockers = [issue.code for issue in issues if issue.severity is IssueSeverity.BLOCKER]
    print(json.dumps({"case": case, "report_ref": str(report_ref.artifact_id),
                      "envelope_ref": str(envelope_ref.artifact_id),
                      "gate_eligible": persisted_envelope.gate_eligible,
                      "blockers": blockers}, sort_keys=True))
    assert persisted_envelope.gate_eligible is False, "unverified identification admitted"
    assert "CONFIDENCE_GATE_ELIGIBILITY_LOW" in blockers


def test_real_failure_candidate_control_is_blocked(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    candidate = _report({}).model_copy(update={"status": EstimationStatus.ASSUMPTION_FAILED})
    envelope = candidate.to_uncertainty_envelope()
    assert envelope is not None and envelope.gate_eligible is False
    ref = persist_uncertainty_envelope(store, envelope)
    ctx = PassContext(ir=None, state={"_store": store, "causal_envelope_ref": ref},
                      registry_bundle=None, profile=ValidationProfile.strict(), run_id="control")
    issues = ConfidencePass().validate(ctx)
    assert any(issue.code == "CONFIDENCE_GATE_ELIGIBILITY_LOW" for issue in issues)


@pytest.mark.parametrize("source_label", ["causal", "ensemble"])
def test_direct_causal_slot_cannot_gain_gate_authority_by_relabeling(tmp_path, source_label) -> None:
    from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope

    store = FileSystemCAS(tmp_path)
    payload = _report({"proof_status": "identified"}).to_uncertainty_envelope().model_dump(mode="json")
    payload["source"] = source_label
    payload["metadata"]["identification_verified"] = True
    # Raw emitted artifact intake, including a false enum declaration. Causal
    # consumer role remains unchanged; a source label cannot substitute a proof.
    envelope = UncertaintyEnvelope.model_validate(payload)
    ref = persist_uncertainty_envelope(store, envelope)
    ctx = PassContext(ir=None, state={"_store": FileSystemCAS(tmp_path),
                                     "artifacts_index": {"causal_envelope_ref": ref}},
                      registry_bundle=None, profile=ValidationProfile.strict(), run_id="direct")
    issues = ConfidencePass().validate(ctx)
    print(json.dumps({"source_label": source_label, "gate_eligible": envelope.gate_eligible,
                      "issues": [issue.code for issue in issues]}, sort_keys=True))
    assert any(issue.code == "CONFIDENCE_GATE_ELIGIBILITY_LOW" for issue in issues)


def test_causal_native_report_has_no_value_projection_authority() -> None:
    from polisyos.core.observability.determinism import DeterminismTier
    from polisyos.foundry.methods.backends.protocol import (
        MethodResult, MethodTiming, ReproducibilityInfo,
    )
    from polisyos.foundry.methods.base import ComputeBackend
    from polisyos.foundry.methods.catalog.causal.did import DifferenceInDifferences
    from polisyos.foundry.methods.components.consensus import EstimandSpec
    from polisyos.foundry.methods.components.value_evidence import (
        MethodValueRefusal, project_method_value_evidence,
    )

    native_report = _report({"proof_status": "identified"})
    result = MethodResult(output={"result": native_report}, slot_outputs={"result": native_report},
                          timing=MethodTiming(wall_time_ms=1),
                          reproducibility=ReproducibilityInfo(backend=ComputeBackend.NUMPY,
                              determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC, seed=17))
    estimand = EstimandSpec(query_id="identification-consumer", estimand_id="ATT", outcome="Y",
                           treatment_or_exposure="A", population="target_population", unit="Y",
                           target_role="causal")
    evidence = project_method_value_evidence(method_signature=DifferenceInDifferences.signature,
                                            method_result=result, estimand=estimand,
                                            selected_output_slot="result")
    assert isinstance(evidence, MethodValueRefusal)
    assert evidence.reason_code == "method_output_contract_unresolved"


def test_resolving_producer_created_proof_bundle_is_not_verifier_admission(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    proof = ProofBundle(proof_status="identified", proof_stratum="A0_trusted",
                        theorem_family="parallel_trends", completeness_regime="complete",
                        implementation_coverage="caller-declared",
                        graph_ref="sha256:" + "d" * 64,
                        query_ref="sha256:" + "e" * 64,
                        estimand_ast={"outcome": "Z", "treatment": "W"},
                        metadata={"source_sha": "f" * 40, "target_population": "other_population",
                                  "writer_role": "system_verifier"})
    proof_ref = persist_proof_bundle(store, proof)
    report = _report({"identification_proof_ref": str(proof_ref.artifact_id),
                      "proof_status": "identified", "verifier_role": "system_verifier"})
    report.identified_estimand = "E[Z|do(W=1)]"
    report.graph_ref = proof.graph_ref
    report_ref = persist_causal_effect_report(store, report)
    report = load_causal_effect_report(FileSystemCAS(tmp_path), report_ref)
    envelope = report.to_uncertainty_envelope()
    assert envelope is not None
    ref = persist_uncertainty_envelope(store, envelope)
    ctx = PassContext(ir=None, state={"_store": FileSystemCAS(tmp_path), "causal_envelope_ref": ref},
                      registry_bundle=None, profile=ValidationProfile.strict(), run_id="resolved-fake")
    issues = ConfidencePass().validate(ctx)
    print(json.dumps({"resolvable_producer_proof": str(proof_ref.artifact_id),
                      "gate_eligible": envelope.gate_eligible,
                      "issues": [issue.code for issue in issues]}, sort_keys=True))
    assert envelope.gate_eligible is False
    assert any(issue.code == "CONFIDENCE_GATE_ELIGIBILITY_LOW" for issue in issues)
