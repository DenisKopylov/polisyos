from __future__ import annotations

# ruff: noqa: S101
from datetime import UTC, datetime

import pytest

from polisyos.runtime.quality.claim_argument import (
    validate_claim_argument_case_surfaces,
)
from polisyos.runtime.quality.explanation_reliability import (
    build_berl_warrant_reliability_record,
)
from tests._helpers.hds_quality import sha


@pytest.mark.parametrize(
    "reliability_flag",
    [
        "explanation_reliability_affects_reviewer_trust",
        "explanation_trust_affects_acceptance",
        "explanation_reliability_affects_user_facing_confidence",
    ],
)
def test_warrant_requires_berl_refs_when_reliability_affects_trust_surface(
    reliability_flag: str,
) -> None:
    case = _claim_argument_case()
    warrant = dict(case["warrants"][0])
    warrant[reliability_flag] = True
    warrant["berl_reliability_refs"] = []
    case["warrants"] = [warrant]

    result = validate_claim_argument_case_surfaces(case)

    assert result.status == "fail"
    assert {issue.code for issue in result.issues} >= {"policy_design_warrant_berl_refs_missing"}


def test_warrant_reliability_record_blocks_failed_berl_thresholds(tmp_path) -> None:
    case = _claim_argument_case()
    warrant = dict(case["warrants"][0])
    warrant["explanation_trust_affects_acceptance"] = True
    warrant["berl_reliability_refs"] = ["berl-reliability-rec-1"]
    case["warrants"] = [warrant]
    store, record = _selected_bundle_record(
        tmp_path,
        reliability_id="berl-reliability-rec-1",
        bundle_payload=_berl_bundle(upper_bound=0.08),
        thresholds={"max_p95_infidelity_upper_bound": 0.02},
    )
    case["warrant_reliability_records"] = [record]

    result = validate_claim_argument_case_surfaces(case, artifact_store=store)

    assert result.status == "fail"
    assert {issue.code for issue in result.issues} >= {
        "policy_design_warrant_berl_threshold_failed"
    }
    normalized = result.major_claims[0]["warrant_reliability_records"][0]
    assert normalized["candidate_diagnostics"]["source"] == "selected_cas_bundle"
    assert normalized["candidate_diagnostics"]["threshold_decision"]["status"] == "fail"


def test_warrant_reliability_ref_must_resolve_to_a_record() -> None:
    case = _claim_argument_case()
    warrant = dict(case["warrants"][0])
    warrant["explanation_trust_affects_acceptance"] = True
    warrant["berl_reliability_refs"] = ["missing-berl-reliability-rec"]
    case["warrants"] = [warrant]

    result = validate_claim_argument_case_surfaces(case)

    assert result.status == "fail"
    assert {issue.code for issue in result.issues} >= {
        "policy_design_warrant_berl_reliability_record_missing"
    }


def test_warrant_reliability_record_must_carry_bundle_thresholds_bounds_and_infidelity() -> None:
    case = _claim_argument_case()
    warrant = dict(case["warrants"][0])
    warrant["explanation_trust_affects_acceptance"] = True
    warrant["berl_reliability_refs"] = ["berl-reliability-empty"]
    case["warrants"] = [warrant]
    case["warrant_reliability_records"] = [
        {
            "reliability_id": "berl-reliability-empty",
            "claim_id": "rec_1",
            "warrant_id": "warrant-rec-1",
        }
    ]

    result = validate_claim_argument_case_surfaces(case)

    assert result.status == "fail"
    assert {issue.code for issue in result.issues} >= {
        "policy_design_warrant_berl_bundle_ref_missing",
        "policy_design_warrant_berl_validation_thresholds_missing",
        "policy_design_warrant_berl_empirical_bounds_missing",
        "policy_design_warrant_berl_local_infidelity_missing",
    }
    normalized = result.major_claims[0]["warrant_reliability_records"][0]
    assert normalized["threshold_decision"]["status"] == "fail"
    assert normalized["threshold_decision"]["violations"] == [
        "policy_design_warrant_berl_bundle_ref_missing"
    ]


def test_berl_warrant_reliability_record_can_be_built_without_argument_refs() -> None:
    record = build_berl_warrant_reliability_record(
        reliability_id="berl-reliability-rec-1",
        claim_id="rec_1",
        explanation_bundle_ref=sha("bundle"),
        evidence_ref=sha("evidence"),
        validation_thresholds={"max_p95_infidelity_upper_bound": 0.1},
        explanation_bundle=_berl_bundle(upper_bound=0.03),
    )

    assert record["reliability_id"] == "berl-reliability-rec-1"
    assert record["claim_id"] == "rec_1"
    assert "warrant_id" not in record
    assert record["schema_version"].endswith(".v2")
    assert record["threshold_decision"]["status"] == "fail"
    assert record["candidate_diagnostics"]["threshold_decision"]["status"] == "pass"
    assert record["subject_context_resolution"]["predicate_class"] == "not_established"
    assert record["candidate_diagnostics"]["empirical_bounds"]
    assert record["candidate_diagnostics"]["local_infidelity_diagnostics"]


@pytest.mark.parametrize(
    ("profile", "expected_violation"),
    [
        ("conditional_observational", "conditional_feature_law_unverified"),
        ("future_profile", "feature_dependence_profile_unsupported"),
        (
            {"profile": "conditional_observational"},
            "method_feature_dependence_profile_malformed",
        ),
    ],
)
def test_warrant_reliability_refuses_unadmitted_feature_dependence_profiles(
    tmp_path,
    profile: object,
    expected_violation: str,
) -> None:
    case = _claim_argument_case()
    warrant = dict(case["warrants"][0])
    warrant["explanation_trust_affects_acceptance"] = True
    warrant["berl_reliability_refs"] = ["berl-reliability-conditional"]
    case["warrants"] = [warrant]
    bundle = _berl_bundle(upper_bound=0.03)
    if isinstance(profile, dict):
        # Keep the top-level typed field valid while exercising malformed method
        # assumptions preserved in raw selected CAS bytes.
        bundle["methods"][0]["assumptions"] = {"feature_removal": profile}
    else:
        bundle["assumptions"]["feature_dependence_policy"]["primary"] = profile
        bundle["methods"][0]["assumptions"] = {"feature_removal": profile}
    bundle["audit"]["artifact_refs"] = ["cas://self-attested/conditional-law-verified"]
    store, record = _selected_bundle_record(
        tmp_path,
        reliability_id="berl-reliability-conditional",
        bundle_payload=bundle,
        thresholds={"max_p95_infidelity_upper_bound": 0.1},
        raw_payload=True,
        inline_bundle_payload=_berl_bundle(upper_bound=0.03),
    )
    case["warrant_reliability_records"] = [record]

    result = validate_claim_argument_case_surfaces(case, artifact_store=store)

    assert result.status == "fail"
    assert any(expected_violation in issue.message for issue in result.issues)
    normalized = result.major_claims[0]["warrant_reliability_records"][0]
    assert normalized["candidate_diagnostics"]["source"] == "selected_cas_bundle"
    assert (
        expected_violation
        in normalized["candidate_diagnostics"]["threshold_decision"]["violations"]
    )


def test_warrant_reliability_refuses_malformed_selected_primary_profile_bytes_without_inline_rescue(
    tmp_path,
) -> None:
    from polisyos.berl.contracts.explanation_bundle import (
        EXPLANATION_BUNDLE_SCHEMA_VERSION,
    )
    from polisyos.berl.contracts.schema import explanation_bundle_schema_id
    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.ir.registry.refs import ExplanationBundleRef

    case = _claim_argument_case()
    warrant = dict(case["warrants"][0])
    warrant["explanation_trust_affects_acceptance"] = True
    warrant["berl_reliability_refs"] = ["berl-reliability-primary-malformed"]
    case["warrants"] = [warrant]
    bundle = _berl_bundle(upper_bound=0.03)
    bundle["assumptions"]["feature_dependence_policy"]["primary"] = {
        "profile": "conditional_observational"
    }
    bundle["methods"][0]["assumptions"] = {"feature_removal": "marginal_interventional"}
    store, record = _selected_bundle_record(
        tmp_path,
        reliability_id="berl-reliability-primary-malformed",
        bundle_payload=bundle,
        thresholds={"max_p95_infidelity_upper_bound": 0.1},
        raw_payload=True,
        inline_bundle_payload=_berl_bundle(upper_bound=0.03),
    )
    case["warrant_reliability_records"] = [record]
    selected_ref = ExplanationBundleRef.model_validate_json(record["explanation_bundle_ref"])
    selected_manifest = ensure_ir_artifact_store(store).get_manifest(selected_ref)
    assert selected_ref.manifest_profile_sha256 is not None
    assert selected_manifest.kind == "scientist.explanation_bundle"
    assert selected_manifest.media_type == "application/json"
    assert selected_manifest.artifact_schema.name == explanation_bundle_schema_id()
    assert selected_manifest.artifact_schema.version == EXPLANATION_BUNDLE_SCHEMA_VERSION

    result = validate_claim_argument_case_surfaces(case, artifact_store=store)

    assert result.status == "fail"
    assert any(
        issue.code == "policy_design_warrant_berl_bundle_unresolved" for issue in result.issues
    )
    normalized = result.major_claims[0]["warrant_reliability_records"][0]
    assert normalized["threshold_decision"]["status"] == "fail"
    assert normalized["threshold_decision"]["violations"] == [
        "policy_design_warrant_berl_bundle_unresolved"
    ]
    assert "candidate_diagnostics" not in normalized


def _selected_bundle_record(
    tmp_path,
    *,
    reliability_id: str,
    bundle_payload: dict[str, object],
    thresholds: dict[str, float],
    raw_payload: bool = False,
    inline_bundle_payload: dict[str, object] | None = None,
):
    from polisyos.berl.contracts.explanation_bundle import (
        EXPLANATION_BUNDLE_SCHEMA_VERSION,
        ExplanationBundle,
    )
    from polisyos.berl.contracts.schema import explanation_bundle_schema_id
    from polisyos.berl.persistence import persist_explanation_bundle
    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.canon import CanonSpec
    from polisyos.ir.artifacts import put_json_artifact
    from polisyos.ir.registry.refs import ExplanationBundleRef

    writer = FileSystemCAS(tmp_path / reliability_id)
    if raw_payload:
        persisted_payload = dict(bundle_payload)
        persisted_payload.setdefault("schema_version", EXPLANATION_BUNDLE_SCHEMA_VERSION)
        written_ref = put_json_artifact(
            ensure_ir_artifact_store(writer),
            persisted_payload,
            kind="scientist.explanation_bundle",
            schema_name=explanation_bundle_schema_id(),
            schema_version=EXPLANATION_BUNDLE_SCHEMA_VERSION,
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        reference = ExplanationBundleRef.model_validate(written_ref)
    else:
        reference = persist_explanation_bundle(
            writer, ExplanationBundle.model_validate(bundle_payload)
        )

    # Reopen the immutable bytes through a separate reader instance; callers must resolve
    # the selected view rather than relying on a producer object or inline payload.
    reader = FileSystemCAS(writer.root)
    record = {
        "reliability_id": reliability_id,
        "claim_id": "rec_1",
        "warrant_id": "warrant-rec-1",
        "evidence_ref": sha("9"),
        "explanation_bundle_ref": reference.model_dump_json(),
        "validation_thresholds": thresholds,
        "explanation_bundle": dict(inline_bundle_payload or bundle_payload),
    }
    return reader, record


def _claim_argument_case() -> dict[str, object]:
    return {
        "effective_execution_profile": "production",
        "final_major_claims": [
            {
                "claim_id": "rec_1",
                "assurance_node_id": "claim-node-rec-1",
                "claim_ref": sha("a"),
                "major": True,
                "argument_refs": ["arg-rec-1"],
                "warrant_refs": ["warrant-rec-1"],
                "rebuttal_refs": ["rebuttal-rec-1"],
                "counter_evidence_refs": ["counter-evidence-rec-1"],
                "assurance_deficit_refs": ["deficit-assessment-rec-1"],
                "requester_capture_challenge_refs": ["requester-capture-rec-1"],
                "blocker_refs": [],
            }
        ],
        "arguments": [
            {
                "argument_id": "arg-rec-1",
                "claim_id": "rec_1",
                "strategy": "triangulated_policy_design_case",
                "evidence_refs": [sha("1"), sha("2")],
            }
        ],
        "warrants": [
            {
                "warrant_id": "warrant-rec-1",
                "claim_id": "rec_1",
                "warrant_text": "Runtime evidence supports the claim.",
                "assumptions": ["parallel trends remains plausible"],
                "applicability_limits": ["No extrapolation outside observed support"],
                "requires_explanation_reliability": False,
                "berl_reliability_refs": [],
            }
        ],
        "rebuttals": [
            {
                "rebuttal_id": "rebuttal-rec-1",
                "claim_id": "rec_1",
                "counter_evidence_refs": ["counter-evidence-rec-1"],
                "resolution": "counter-evidence assessed and bounded",
            }
        ],
        "counter_evidence": [
            {
                "counter_evidence_id": "counter-evidence-rec-1",
                "claim_id": "rec_1",
                "visibility": "reviewer_visible",
                "status": "assessed",
                "assessment_result": "bounded",
                "evidence_ref": sha("3"),
                "runtime_event_ref": sha("4"),
            }
        ],
        "assurance_deficits": [
            {
                "deficit_id": "deficit-assessment-rec-1",
                "claim_id": "rec_1",
                "deficit_kind": "no_unresolved_assurance_deficit",
                "status": "none",
                "evidence_ref": sha("5"),
                "runtime_event_ref": sha("6"),
            }
        ],
        "requester_capture_challenges": [
            {
                "challenge_id": "requester-capture-rec-1",
                "claim_id": "rec_1",
                "challenge_result": "passed",
                "requester_preferred_conclusion": "expand credit support",
                "independent_analysis_conclusion": (
                    "targeted credit support is conditionally justified"
                ),
                "independent_alternative_analyses": [
                    {
                        "alternative_id": "baseline-no-action",
                        "conclusion": ("no action has lower fiscal risk but worse survival impact"),
                        "evidence_refs": [sha("1")],
                    },
                    {
                        "alternative_id": "untargeted-subsidy",
                        "conclusion": ("untargeted subsidy is rejected on distributional grounds"),
                        "evidence_refs": [sha("2")],
                    },
                ],
                "scientist_output_refs": {
                    "policy_design_adversary_refs": [sha("3")],
                    "policy_design_critic_refs": [sha("4")],
                    "policy_design_objective_refs": [sha("5")],
                    "policy_design_search_refs": [sha("6")],
                    "backtesting_adversarial_refs": [sha("7")],
                },
                "adversarial_output_refs": [
                    sha("3"),
                    sha("4"),
                    sha("5"),
                    sha("6"),
                    sha("7"),
                ],
                "evidence_ref": sha("7"),
                "runtime_event_ref": sha("8"),
            }
        ],
        "nodes": [
            {
                "node_type": "claim",
                "node_id": "claim-node-rec-1",
                "claim_id": "rec_1",
                "claim_ref": sha("a"),
                "cas_ref": sha("a"),
                "runtime_event_ref": sha("e"),
                "runtime_authority_envelope": {
                    "authority_role": "producer_authority",
                    "provenance_kind": "runtime_emitted",
                },
            }
        ],
    }


def _berl_bundle(*, upper_bound: float) -> dict[str, object]:
    return {
        "bundle_id": "berl-bundle-1",
        "created_at": datetime(2026, 5, 18, tzinfo=UTC).isoformat(),
        "faithfulness_claim": "bounded",
        "display_policy": "limited",
        "model": {
            "model_id": "policy_model",
            "model_hash": sha("m"),
            "model_class": "gradient_boosted_trees",
            "training_data_hash": sha("d"),
        },
        "prediction": {
            "prediction_id": "prediction-1",
            "row_id": "case-1",
            "output_name": "claim_acceptance",
            "output_scale": "probability",
            "raw_score": 0.72,
            "display_score": 0.72,
            "decision_threshold": 0.65,
        },
        "feature_context": {
            "feature_values_ref": sha("f"),
            "feature_schema_version": "2026-05",
            "constraints_ref": sha("c"),
        },
        "assumptions": {
            "perturbation_distribution": {
                "name": "conditional_empirical_local",
                "radius": 0.2,
                "categorical_policy": "observed_support_only",
                "continuous_policy": "local_empirical_resampling",
                "support_constraints": sha("c"),
            },
            "feature_dependence_policy": {
                "primary": "marginal_interventional",
                "alternatives_tested": ["marginal_interventional"],
                "causal_claim_made": False,
            },
            "background_data": {
                "dataset_ref": sha("b"),
                "n": 120,
                "sampling_policy": "fixed_fixture_sample",
            },
        },
        "redundancy": {"clusters": []},
        "methods": [
            {
                "method_id": "kernel_shap",
                "library": "berl-fixture",
                "library_version": "1.0.0",
                "params": {"coalition_samples": 64},
                "assumptions": {"feature_removal": "marginal_interventional"},
                "attributions": [{"feature": "employment_rate", "value": 0.18}],
                "infidelity": {
                    "point_estimate": 0.01,
                    "upper_bound": upper_bound,
                    "confidence": 0.95,
                    "n_eval_perturbations": 64,
                    "residual_cap": 1.0,
                    "bound_type": "empirical_bernstein_heldout",
                    "evaluation_split": "heldout",
                },
            }
        ],
        "disagreement": {
            "methods_compared": ["kernel_shap"],
            "top_k": 1,
            "top_k_jaccard_median": 1.0,
            "kendall_tau_median": 1.0,
            "sign_conflict_features": [],
            "flags": [],
        },
        "validity": {
            "support_check": {
                "ood_rate_eval_perturbations": 0.01,
                "constraint_violation_rate": 0.0,
            },
            "use_restrictions": ["Local to declared perturbation support."],
        },
        "audit": {
            "code_version": "berl-fixture@sha256:code",
            "random_seeds": [7],
            "artifact_refs": [sha("r")],
        },
    }


def test_warrant_reliability_keeps_selected_cas_candidate_but_blocks_unresolved_subject_context(
    tmp_path,
) -> None:
    import hashlib
    import json

    from polisyos.berl.contracts.explanation_bundle import ExplanationBundle
    from polisyos.berl.contracts.schema import explanation_bundle_schema_id
    from polisyos.berl.persistence import persist_explanation_bundle
    from polisyos.core.artifacts import SchemaInfo, ensure_ir_artifact_store
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.core.canon import CanonSpec
    from polisyos.ir.registry.refs import ExplanationBundleRef
    from polisyos.runtime.quality.explanation_reliability import (
        evaluate_warrant_berl_reliability,
    )

    store = FileSystemCAS(tmp_path / "cas")
    bundle = ExplanationBundle.model_validate(_berl_bundle(upper_bound=0.03))
    reference = persist_explanation_bundle(store, bundle)
    expected_subject = {
        "prediction_id": bundle.prediction.prediction_id,
        "model_hash": bundle.model.model_hash,
        "feature_schema_version": bundle.feature_context.feature_schema_version,
    }
    record = build_berl_warrant_reliability_record(
        reliability_id="berl-cas-record",
        claim_id="claim-cas",
        warrant_id="warrant-cas",
        explanation_bundle_ref=reference.model_dump_json(),
        validation_thresholds={"max_p95_infidelity_upper_bound": 0.1},
        explanation_bundle=bundle.model_dump(mode="json"),
        expected_explanation_subject=expected_subject,
    )

    def evaluate(selected_record, *, selected_store=store):
        return evaluate_warrant_berl_reliability(
            {"warrant_reliability_records": [selected_record]},
            {
                "claim_id": "claim-cas",
                "warrant_id": "warrant-cas",
                "berl_reliability_refs": ["berl-cas-record"],
            },
            claim_id="claim-cas",
            artifact_store=selected_store,
        )

    positive = evaluate(record)
    assert any(
        issue.code == "policy_design_warrant_berl_subject_context_not_established"
        for issue in positive.issues
    )
    assert positive.records[0]["threshold_decision"]["status"] == "fail"
    assert (
        "policy_design_warrant_berl_subject_context_not_established"
        in positive.records[0]["threshold_decision"]["violations"]
    )
    assert positive.records[0]["candidate_diagnostics"]["threshold_decision"]["status"] == "pass"
    assert positive.records[0]["subject_context_resolution"]["status"] == "not_established"
    assert (
        positive.records[0]["subject_context_resolution"]["gate_predicate"][
            "claim_run_model_prediction_relation"
        ]
        == "not_established"
    )

    resolution = positive.records[0]["subject_context_resolution"]
    assert resolution["candidate_assertions"]["status"] == "matched"
    assert resolution["claim_warrant_linkage"]["status"] == "matched"
    assert resolution["claim_warrant_linkage"]["record_id_in_warrant_refs"] is True
    assert resolution["selected_ref"]

    no_assertion_record = dict(record)
    no_assertion_record.pop("expected_explanation_subject")
    no_assertion_result = evaluate(no_assertion_record)
    assert (
        no_assertion_result.records[0]["subject_context_resolution"]["candidate_assertions"][
            "status"
        ]
        == "absent"
    )
    assert no_assertion_result.records[0]["threshold_decision"]["status"] == "fail"

    malformed_assertion = dict(
        record,
        expected_explanation_subject={**expected_subject, "model_hash": ""},
    )
    malformed_result = evaluate(malformed_assertion)
    assert (
        malformed_result.records[0]["subject_context_resolution"]["candidate_assertions"]["status"]
        == "malformed"
    )
    assert malformed_result.records[0]["threshold_decision"]["status"] == "fail"

    wrong_warrant = dict(record, warrant_id="different-warrant")
    wrong_warrant_result = evaluate(wrong_warrant)
    assert any(
        issue.code == "policy_design_warrant_berl_subject_context_link_mismatch"
        for issue in wrong_warrant_result.issues
    )

    forged_resolution = dict(
        record,
        subject_context_resolution={"status": "independently_reconciled", "source": "caller"},
    )
    forged_result = evaluate(forged_resolution)
    assert forged_result.records[0]["threshold_decision"]["status"] == "fail"
    assert forged_result.records[0]["subject_context_resolution"]["status"] == "not_established"

    wrong_claim = dict(record, claim_id="different-claim")
    wrong_claim_result = evaluate(wrong_claim)
    assert any(
        issue.code == "policy_design_warrant_berl_subject_context_link_mismatch"
        for issue in wrong_claim_result.issues
    )
    assert wrong_claim_result.records[0]["threshold_decision"]["status"] == "fail"

    conflicting_warrant = {
        "claim_id": "claim-cas",
        "warrant_id": "warrant-cas",
        "berl_reliability_refs": ["berl-cas-record"],
        "expected_explanation_subject": {**expected_subject, "prediction_id": "other-prediction"},
    }
    conflict_result = evaluate_warrant_berl_reliability(
        {"warrant_reliability_records": [record]},
        conflicting_warrant,
        claim_id="claim-cas",
        artifact_store=store,
    )
    assert conflict_result.records[0]["subject_context_resolution"]["status"] == "contested"
    assert conflict_result.records[0]["threshold_decision"]["status"] == "fail"
    assert any(
        issue.code == "policy_design_warrant_berl_bundle_subject_mismatch"
        for issue in conflict_result.issues
    )

    missing_ref_record = {
        key: value for key, value in record.items() if key != "explanation_bundle_ref"
    }
    missing_ref = evaluate(missing_ref_record)
    assert any(
        issue.code == "policy_design_warrant_berl_bundle_ref_missing"
        for issue in missing_ref.issues
    )
    assert missing_ref.records[0]["threshold_decision"]["status"] == "fail"

    no_store = evaluate(record, selected_store=None)
    assert any(
        issue.code == "policy_design_warrant_berl_bundle_store_unavailable"
        for issue in no_store.issues
    )
    assert no_store.records[0]["threshold_decision"]["status"] == "fail"

    class ProviderReadFailureStore:
        def __init__(self, backing_store, failed_operation: str) -> None:
            self.backing_store = backing_store
            self.failed_operation = failed_operation

        def _raise_if_selected(self, operation: str) -> None:
            if self.failed_operation == operation:
                raise RuntimeError("provider response must not become evidence")

        def get_manifest(self, selector):
            self._raise_if_selected("manifest")
            return self.backing_store.get_manifest(selector)

        def get_manifest_bytes(self, selector):
            self._raise_if_selected("manifest_bytes")
            return self.backing_store.get_manifest_bytes(selector)

        def get_bytes(self, selector):
            self._raise_if_selected("payload_bytes")
            return self.backing_store.get_bytes(selector)

    for failed_operation in ("manifest", "manifest_bytes", "payload_bytes"):
        failed_read = evaluate(
            record,
            selected_store=ProviderReadFailureStore(
                ensure_ir_artifact_store(store), failed_operation
            ),
        )
        store_read_issue = next(
            issue
            for issue in failed_read.issues
            if issue.code == "policy_design_warrant_berl_bundle_store_read_unavailable"
        )
        assert store_read_issue.message == (
            "The selected BERL store read failed; object absence is not established."
        )
        assert "provider response" not in store_read_issue.message
        assert failed_read.records[0]["threshold_decision"]["status"] == "fail"
        assert "attributions" not in failed_read.records[0]

    invalid_store = evaluate(record, selected_store=object())
    assert any(
        issue.code == "policy_design_warrant_berl_bundle_unresolved"
        for issue in invalid_store.issues
    )
    assert invalid_store.records[0]["threshold_decision"]["status"] == "fail"

    malformed = dict(record, explanation_bundle_ref="{bad-json")
    malformed_result = evaluate(malformed)
    assert any(
        issue.code == "policy_design_warrant_berl_bundle_ref_invalid"
        for issue in malformed_result.issues
    )
    assert malformed_result.records[0]["threshold_decision"]["status"] == "fail"

    ref_payload = reference.model_dump(mode="json")
    wrong_kind = dict(
        record,
        explanation_bundle_ref=json.dumps({**ref_payload, "kind": "scientist.other"}),
    )
    wrong_media = dict(
        record,
        explanation_bundle_ref=json.dumps({**ref_payload, "media_type": "text/plain"}),
    )
    for selected in (wrong_kind, wrong_media):
        selected_result = evaluate(selected)
        assert any(
            issue.code == "policy_design_warrant_berl_bundle_ref_invalid"
            for issue in selected_result.issues
        )
        assert selected_result.records[0]["threshold_decision"]["status"] == "fail"

    wrong_profile_payload = {
        **ref_payload,
        "manifest_profile_sha256": "sha256:" + "0" * 64,
    }
    wrong_profile = dict(record, explanation_bundle_ref=json.dumps(wrong_profile_payload))
    wrong_profile_result = evaluate(wrong_profile)
    assert any(
        issue.code == "policy_design_warrant_berl_bundle_unresolved"
        for issue in wrong_profile_result.issues
    )
    assert wrong_profile_result.records[0]["threshold_decision"]["status"] == "fail"

    unresolved_id = "sha256:" + hashlib.sha256(b"unresolved-berl-bundle").hexdigest()
    unresolved_payload = {**ref_payload, "artifact_id": unresolved_id}
    unresolved = dict(record, explanation_bundle_ref=json.dumps(unresolved_payload))
    assert any(
        issue.code == "policy_design_warrant_berl_bundle_unresolved"
        for issue in evaluate(unresolved).issues
    )

    wrong_schema_artifact = store.put_json(
        bundle.model_dump(mode="json", round_trip=True),
        PutOptions(
            kind="scientist.explanation_bundle",
            media_type="application/json",
            schema=SchemaInfo(name=explanation_bundle_schema_id(), version="0.9.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    wrong_schema_ref = ExplanationBundleRef.model_validate(
        ArtifactRef.model_validate(wrong_schema_artifact).model_dump(mode="python")
    )
    wrong_schema = dict(record, explanation_bundle_ref=wrong_schema_ref.model_dump_json())
    wrong_schema_result = evaluate(wrong_schema)
    assert any(
        issue.code == "policy_design_warrant_berl_bundle_unresolved"
        for issue in wrong_schema_result.issues
    )
    assert wrong_schema_result.records[0]["threshold_decision"]["status"] == "fail"

    wrong_subject = dict(record)
    wrong_subject["expected_explanation_subject"] = {
        **expected_subject,
        "prediction_id": "different-prediction",
    }
    assert any(
        issue.code == "policy_design_warrant_berl_bundle_subject_mismatch"
        for issue in evaluate(wrong_subject).issues
    )
