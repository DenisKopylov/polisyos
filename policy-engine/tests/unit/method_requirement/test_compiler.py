from __future__ import annotations

import json

from polisyos.method_requirement import (
    MethodIdentificationClass,
    MethodUncertaintyClass,
    compile_method_validity_requirements,
    method_validity_requirement_audit_surface,
    write_method_validity_requirement_artifact,
)


def _claim(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "claim_id": "claim_msme_credit_access",
        "run_id": "run_w7c",
        "claim_type": "causal",
        "claim_family": "distributional",
        "claim_use": "decision_support",
        "text": (
            "The MSME credit guarantee improves credit access for underserved firms "
            "without unacceptable regional exclusion."
        ),
        "facet_refs": ["facet_credit_access", "facet_underserved_firms"],
        "obligation_refs": ["obl_method_validity", "obl_distributional_equity"],
        "concept_spine_refs": ["concept.credit_access", "concept.underserved_msme"],
        "authority_profile_refs": ["authority.fiscal_delegated"],
        "baseline_refs": ["baseline_status_quo"],
        "alternative_refs": ["alt_direct_grants"],
        "method_need_preconditions": [
            {
                "precondition_id": "need_causal",
                "claim_id": "claim_msme_credit_access",
                "claim_type": "causal",
                "method_need": "causal_identification",
                "reason": "Causal claims require identification.",
                "facet_refs": ["facet_credit_access"],
                "obligation_refs": ["obl_method_validity"],
            },
            {
                "precondition_id": "need_distributional",
                "claim_id": "claim_msme_credit_access",
                "claim_type": "distributional",
                "method_need": "distributional_decomposition",
                "reason": "Distributional claims require subgroup decomposition.",
                "facet_refs": ["facet_underserved_firms"],
                "obligation_refs": ["obl_distributional_equity"],
            },
        ],
        "metadata": {"strategic_response": "take_up_sensitivity"},
    }
    payload.update(overrides)
    return payload


def test_compiler_emits_typed_method_validity_requirement_per_claim(tmp_path) -> None:
    artifact = compile_method_validity_requirements(
        run_id="run_w7c",
        claims=[_claim()],
        requirement_graph_ref="artifact://policy-design-case/run_w7c/obligation-graph",
    )

    assert artifact.capability_reality_label == "implemented"
    assert artifact.runtime_event_ref == "event://method-requirement/run_w7c"
    assert artifact.requirement_graph_ref == (
        "artifact://policy-design-case/run_w7c/obligation-graph"
    )
    assert len(artifact.requirements) == 1

    spec = artifact.requirements[0]
    assert spec.claim_id == "claim_msme_credit_access"
    assert spec.identification_class is MethodIdentificationClass.POINT
    assert spec.transportability_requirement == "target_population_limits"
    assert spec.uncertainty_class is MethodUncertaintyClass.INTERVAL
    assert spec.fairness_decomposition_need == "subgroup"
    assert spec.strategic_response_sensitivity == "sensitivity"
    assert spec.simulation_dgp_requirements.required is False
    assert spec.method_expectations == [
        "causal_effect_estimation",
        "distributional_evidence",
        "sensitivity_or_transportability_diagnostic",
    ]
    assert [need.assumption_id for need in spec.assumption_validation_needs] == [
        "identification_assumptions",
        "overlap_or_support",
        "missingness_process",
        "subgroup_support",
        "strategic_response_model",
    ]
    assert spec.requires_ir_analytics is True
    assert spec.requires_runtime_assumption_gates is True
    assert spec.requires_uncertainty_envelope is True
    assert spec.requires_limitation_refs is True

    artifact_path = write_method_validity_requirement_artifact(artifact, tmp_path)
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    audit = method_validity_requirement_audit_surface(payload)

    assert payload["requirements"][0]["requirement_id"] == spec.requirement_id
    assert audit["surface"] == "method_requirement.audit_surface"
    assert audit["summary"]["requirement_count"] == 1
    assert audit["authority_boundary"]["may_not_use_for"] == [
        "legal_authority",
        "source_family_satisfaction",
        "academic_support_strength",
        "participation_representativeness",
        "closeout_pass",
    ]


def test_negative_certificate_claim_compiles_to_blocking_ir_requirement() -> None:
    artifact = compile_method_validity_requirements(
        run_id="run_w7c_negative",
        claims=[
            _claim(
                claim_id="claim_no_identification",
                support_status="refuted",
                claim_type="causal",
                claim_family="causal",
                method_need_preconditions=[
                    {
                        "precondition_id": "need_negative",
                        "claim_id": "claim_no_identification",
                        "claim_type": "causal",
                        "method_need": "negative_certificate",
                        "reason": "The claim must preserve non-identification.",
                    }
                ],
            )
        ],
    )

    spec = artifact.requirements[0]
    assert spec.identification_class is MethodIdentificationClass.NEGATIVE_CERTIFICATE
    assert spec.method_expectations == ["negative_certificate"]
    assert spec.requires_negative_certificate is True
    assert spec.requires_method_output is False
