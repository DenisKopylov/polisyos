from __future__ import annotations

import json

import pytest

from polisyos.ir.observation import IdentificationMode
from polisyos.method_requirement import (
    MethodIdentificationClass,
    MethodUncertaintyClass,
    compile_method_validity_requirements,
    method_validity_requirement_audit_surface,
    write_method_validity_requirement_artifact,
)
from polisyos.scientist.policy_design.claim_decomposition import (
    ClaimDecompositionCompiler,
    ClaimDecompositionFacet,
    ClaimDecompositionInput,
    ClaimDecompositionObligation,
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


def test_unrecognized_claim_metadata_cannot_launder_method_semantics() -> None:
    baseline = compile_method_validity_requirements(
        run_id="run_w7c_metadata_baseline",
        claims=[_claim()],
    ).requirements[0]
    with_untrusted_metadata = compile_method_validity_requirements(
        run_id="run_w7c_metadata_control",
        claims=[
            _claim(
                metadata={
                    "strategic_response": "take_up_sensitivity",
                    "audit_note": "partial_identification point bounds causal",
                    "grammar_limitation_records": [
                        {
                            "code": "candidate_scope_unknown",
                            "details": {"review_text": "bounds-only is not established"},
                        }
                    ],
                }
            )
        ],
    ).requirements[0]
    assert with_untrusted_metadata.identification_class is baseline.identification_class
    assert with_untrusted_metadata.method_expectations == baseline.method_expectations
    assert (
        with_untrusted_metadata.assumption_validation_needs == baseline.assumption_validation_needs
    )

    typed_claim = _claim()
    typed_claim["method_need_preconditions"][0]["metadata"] = {
        "explicit_identification_mode_facets": [
            {
                "facet_ref": "facet_credit_access",
                "identification_mode": IdentificationMode.BOUNDS_ONLY.value,
                "source_class": "deterministic_compiler",
            }
        ]
    }
    with_typed_mode = compile_method_validity_requirements(
        run_id="run_w7c_typed_mode",
        claims=[typed_claim],
    ).requirements[0]
    assert with_typed_mode.identification_class is MethodIdentificationClass.BOUNDS
    assert IdentificationMode.BOUNDS_ONLY.value in with_typed_mode.method_expectations


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


@pytest.mark.parametrize(
    ("mode", "expected_class"),
    [
        (IdentificationMode.POINT_IDENTIFIED, MethodIdentificationClass.POINT),
        (IdentificationMode.PARTIALLY_IDENTIFIED, MethodIdentificationClass.PARTIAL),
        (IdentificationMode.BOUNDS_ONLY, MethodIdentificationClass.BOUNDS),
        (IdentificationMode.PROXY_IDENTIFIED, MethodIdentificationClass.POINT),
        (IdentificationMode.INTERFERENCE_AWARE, MethodIdentificationClass.POINT),
        (IdentificationMode.SEQUENTIAL, MethodIdentificationClass.POINT),
    ],
)
def test_linked_identification_mode_reaches_method_requirement_with_provenance(
    mode: IdentificationMode,
    expected_class: MethodIdentificationClass,
) -> None:
    decomposition = ClaimDecompositionCompiler().compile(
        ClaimDecompositionInput(
            run_id=f"run_w6d_{mode.value}",
            intent="Assess a causal policy effect under the declared method mode.",
            facets=[
                ClaimDecompositionFacet(
                    facet_id="facet_effect",
                    facet_type="outcome_channel",
                    value="causal effect",
                ),
                ClaimDecompositionFacet(
                    facet_id="facet_method",
                    facet_type="method_need",
                    value=mode.value,
                ),
            ],
            obligations=[
                ClaimDecompositionObligation(
                    obligation_id="obligation_effect",
                    family="causal_effect",
                    description="Assess the intervention effect.",
                    facet_refs=["facet_effect", "facet_method"],
                )
            ],
        )
    )

    artifact = compile_method_validity_requirements(
        run_id=decomposition.run_id,
        claims=decomposition.claims,
    )

    causal_claims = [claim for claim in decomposition.claims if claim.claim_type.value == "causal"]
    assert len(causal_claims) == 2
    for causal_claim in causal_claims:
        requirement = next(
            row for row in artifact.requirements if row.claim_id == causal_claim.claim_id
        )
        assert requirement.identification_class is expected_class
        assert requirement.source_precondition_refs
        assert mode.value in requirement.method_expectations
        assert requirement.metadata["explicit_identification_mode_facets"] == [
            {
                "facet_ref": "facet_method",
                "identification_mode": mode.value,
                "identification_mode_origin": "declared_constraint",
                "source_class": "deterministic_compiler",
            }
        ]


def test_unlinked_method_context_does_not_supply_causal_mode() -> None:
    decomposition = ClaimDecompositionCompiler().compile(
        ClaimDecompositionInput(
            run_id="run_w6d_unlinked_mode",
            intent="Assess a causal policy effect.",
            facets=[
                ClaimDecompositionFacet(
                    facet_id="facet_effect",
                    facet_type="outcome_channel",
                    value="causal effect",
                ),
                ClaimDecompositionFacet(
                    facet_id="facet_method_context",
                    facet_type="method_need",
                    value=IdentificationMode.BOUNDS_ONLY.value,
                ),
            ],
            obligations=[
                ClaimDecompositionObligation(
                    obligation_id="obligation_effect",
                    family="causal_effect",
                    description="Assess the intervention effect.",
                    facet_refs=["facet_effect"],
                )
            ],
        )
    )
    artifact = compile_method_validity_requirements(
        run_id=decomposition.run_id,
        claims=decomposition.claims,
    )

    causal_claim = next(
        claim
        for claim in decomposition.claims
        if claim.claim_type.value == "causal" and claim.obligation_refs
    )
    requirement = next(
        row for row in artifact.requirements if row.claim_id == causal_claim.claim_id
    )
    assert requirement.identification_class is MethodIdentificationClass.POINT
    assert requirement.metadata["explicit_identification_mode_facets"] == []


def test_unknown_grammar_mode_origin_survives_requirement_audit_as_limitation() -> None:
    ledger = ClaimDecompositionCompiler().compile(
        ClaimDecompositionInput(
            run_id="run_w7c_unknown_method_origin",
            intent="Assess a causal effect with a historical method facet.",
            facets=[
                ClaimDecompositionFacet(
                    facet_id="facet_effect",
                    facet_type="outcome_channel",
                    value="causal effect",
                    metadata={"case_id": "historical_case"},
                ),
                ClaimDecompositionFacet(
                    facet_id="facet_method",
                    facet_type="method_need",
                    value=IdentificationMode.BOUNDS_ONLY.value,
                    metadata={
                        "case_id": "historical_case",
                        "derivation_rule_ref": "policyos.policy_grammar.facet_derivation.v1:method_need",
                        "identification_mode_origin": "not_established",
                    },
                ),
            ],
            obligations=[
                ClaimDecompositionObligation(
                    obligation_id="obligation_effect",
                    family="causal_effect",
                    description="Assess the causal effect.",
                    facet_refs=["facet_effect", "facet_method"],
                )
            ],
        )
    )
    artifact = compile_method_validity_requirements(
        run_id=ledger.run_id,
        claims=ledger.claims,
    )
    causal_claims = [claim for claim in ledger.claims if claim.claim_type.value == "causal"]
    requirements = [
        row
        for row in artifact.requirements
        if row.claim_id in {claim.claim_id for claim in causal_claims}
    ]

    assert len(requirements) == 2
    for requirement in requirements:
        assert requirement.metadata["explicit_identification_mode_facets"] == []
        assert IdentificationMode.BOUNDS_ONLY.value not in requirement.method_expectations
        assert requirement.metadata["identification_class_semantics"] == (
            "required_method_capability_not_identification_evidence"
        )
        assert requirement.metadata["identification_mode_limitations"] == [
            {
                "code": "identification_mode_origin_not_established",
                "facet_ref": "facet_method",
                "identification_mode": IdentificationMode.BOUNDS_ONLY.value,
                "origin": "not_established",
                "derivation_rule_ref": "policyos.policy_grammar.facet_derivation.v1:method_need",
            }
        ]
        context = next(
            row
            for row in requirement.metadata["source_facet_contexts"]
            if row["facet_ref"] == "facet_method"
        )
        assert context["value"] == IdentificationMode.BOUNDS_ONLY.value
        assert context["metadata"]["identification_mode_origin"] == "not_established"

    audit = method_validity_requirement_audit_surface(artifact)
    assert all(
        requirement["metadata"]["identification_mode_limitations"][0]["origin"] == "not_established"
        for requirement in audit["requirements"]
        if requirement["claim_id"] in {claim.claim_id for claim in causal_claims}
    )


def test_grammar_default_rule_cannot_erase_a_supplied_explicit_mode_binding() -> None:
    claim = _claim()
    claim["facet_refs"] = ["facet_credit_access"]
    claim["metadata"] = {
        "source_facet_contexts": [
            {
                "facet_ref": "facet_credit_access",
                "facet_type": "method_need",
                "value": IdentificationMode.POINT_IDENTIFIED.value,
                "source_class": "deterministic_compiler",
                "metadata": {
                    "case_id": "default_case",
                    "derivation_rule_ref": (
                        "policyos.policy_grammar.facet_derivation.v1:method_need:default_point.v1"
                    ),
                    "identification_mode_origin": "default_point",
                },
            }
        ]
    }
    claim["method_need_preconditions"] = [
        {
            **claim["method_need_preconditions"][0],
            "facet_refs": ["facet_credit_access"],
            "metadata": {
                "explicit_identification_mode_facets": [
                    {
                        "facet_ref": "facet_credit_access",
                        "identification_mode": IdentificationMode.POINT_IDENTIFIED.value,
                        "identification_mode_origin": "default_point",
                        "derivation_rule_ref": (
                            "policyos.policy_grammar.facet_derivation.v1:method_need:default_point.v1"
                        ),
                        "source_class": "deterministic_compiler",
                    }
                ]
            },
        }
    ]

    with pytest.raises(
        ValueError,
        match="method_requirement_identification_mode_binding_not_explicit",
    ):
        compile_method_validity_requirements(
            run_id="run_w7c_default_binding_control", claims=[claim]
        )


@pytest.mark.parametrize(
    ("left_mode", "right_mode"),
    [
        (IdentificationMode.BOUNDS_ONLY, IdentificationMode.PARTIALLY_IDENTIFIED),
        (IdentificationMode.POINT_IDENTIFIED, IdentificationMode.SEQUENTIAL),
        (IdentificationMode.PROXY_IDENTIFIED, IdentificationMode.INTERFERENCE_AWARE),
    ],
)
def test_distinct_linked_identification_modes_refuse_per_claim(
    left_mode: IdentificationMode,
    right_mode: IdentificationMode,
) -> None:
    decomposition = ClaimDecompositionCompiler().compile(
        ClaimDecompositionInput(
            run_id=f"run_w6d_conflicting_modes_{left_mode.value}_{right_mode.value}",
            intent="Assess a causal policy effect.",
            facets=[
                ClaimDecompositionFacet(
                    facet_id="facet_effect",
                    facet_type="outcome_channel",
                    value="causal effect",
                ),
                ClaimDecompositionFacet(
                    facet_id="facet_mode_left",
                    facet_type="method_need",
                    value=left_mode.value,
                ),
                ClaimDecompositionFacet(
                    facet_id="facet_mode_right",
                    facet_type="method_need",
                    value=right_mode.value,
                ),
            ],
            obligations=[
                ClaimDecompositionObligation(
                    obligation_id="obligation_effect",
                    family="causal_effect",
                    description="Assess the intervention effect.",
                    facet_refs=["facet_effect", "facet_mode_left", "facet_mode_right"],
                )
            ],
        )
    )

    with pytest.raises(
        ValueError,
        match="method_requirement_explicit_identification_modes_conflict",
    ):
        compile_method_validity_requirements(
            run_id=decomposition.run_id,
            claims=decomposition.claims,
        )


def test_repeated_linked_identification_mode_preserves_each_facet_without_conflict() -> None:
    decomposition = ClaimDecompositionCompiler().compile(
        ClaimDecompositionInput(
            run_id="run_w6d_repeated_mode",
            intent="Assess a causal effect with repeated partial-mode references.",
            facets=[
                ClaimDecompositionFacet(
                    facet_id="facet_effect",
                    facet_type="outcome_channel",
                    value="causal effect",
                ),
                ClaimDecompositionFacet(
                    facet_id="facet_partial_a",
                    facet_type="method_need",
                    value=IdentificationMode.PARTIALLY_IDENTIFIED.value,
                ),
                ClaimDecompositionFacet(
                    facet_id="facet_partial_b",
                    facet_type="method_need",
                    value=IdentificationMode.PARTIALLY_IDENTIFIED.value,
                ),
            ],
            obligations=[
                ClaimDecompositionObligation(
                    obligation_id="obligation_effect",
                    family="causal_effect",
                    description="Assess the intervention effect.",
                    facet_refs=["facet_effect", "facet_partial_a", "facet_partial_b"],
                )
            ],
        )
    )
    artifact = compile_method_validity_requirements(
        run_id=decomposition.run_id,
        claims=decomposition.claims,
    )
    causal_claims = [claim for claim in decomposition.claims if claim.claim_type.value == "causal"]
    assert len(causal_claims) == 2

    for claim in causal_claims:
        requirement = next(row for row in artifact.requirements if row.claim_id == claim.claim_id)
        assert requirement.identification_class is MethodIdentificationClass.PARTIAL
        assert (
            requirement.method_expectations.count(IdentificationMode.PARTIALLY_IDENTIFIED.value)
            == 1
        )
        assert {
            row["facet_ref"] for row in requirement.metadata["explicit_identification_mode_facets"]
        } == {"facet_partial_a", "facet_partial_b"}


def test_distinct_modes_on_separate_components_do_not_conflict_globally() -> None:
    decomposition = ClaimDecompositionCompiler().compile(
        ClaimDecompositionInput(
            run_id="run_w6d_distinct_component_modes",
            intent="Assess employment and inflation effects using their respective methods.",
            facets=[
                ClaimDecompositionFacet(
                    facet_id="facet_employment",
                    facet_type="outcome_channel",
                    value="employment causal effect",
                    metadata={"component_id": "employment"},
                ),
                ClaimDecompositionFacet(
                    facet_id="facet_employment_mode",
                    facet_type="method_need",
                    value=IdentificationMode.POINT_IDENTIFIED.value,
                    metadata={"component_id": "employment"},
                ),
                ClaimDecompositionFacet(
                    facet_id="facet_inflation",
                    facet_type="outcome_channel",
                    value="inflation causal effect",
                    metadata={"component_id": "inflation"},
                ),
                ClaimDecompositionFacet(
                    facet_id="facet_inflation_mode",
                    facet_type="method_need",
                    value=IdentificationMode.SEQUENTIAL.value,
                    metadata={"component_id": "inflation"},
                ),
            ],
            obligations=[
                ClaimDecompositionObligation(
                    obligation_id="obligation_employment",
                    family="causal_effect",
                    description="Assess the employment effect.",
                    facet_refs=["facet_employment", "facet_employment_mode"],
                ),
                ClaimDecompositionObligation(
                    obligation_id="obligation_inflation",
                    family="causal_effect",
                    description="Assess the inflation effect.",
                    facet_refs=["facet_inflation", "facet_inflation_mode"],
                ),
            ],
        )
    )
    artifact = compile_method_validity_requirements(
        run_id=decomposition.run_id,
        claims=decomposition.claims,
    )

    causal_claims = [claim for claim in decomposition.claims if claim.claim_type.value == "causal"]
    assert len(causal_claims) == 4
    for claim in causal_claims:
        mode = (
            IdentificationMode.POINT_IDENTIFIED
            if "facet_employment_mode" in claim.facet_refs
            else IdentificationMode.SEQUENTIAL
        )
        requirement = next(row for row in artifact.requirements if row.claim_id == claim.claim_id)
        assert mode.value in requirement.method_expectations
        assert [
            row["identification_mode"]
            for row in requirement.metadata["explicit_identification_mode_facets"]
        ] == [mode.value]
