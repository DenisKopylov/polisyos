from __future__ import annotations

from polisyos.method_requirement import MethodValidityRequirementSpec
from polisyos.runtime.quality.ir_analytics_bridge import build_ir_analytics_claim_bridge


def _requirement(**overrides: object) -> MethodValidityRequirementSpec:
    payload: dict[str, object] = {
        "requirement_id": "method-req-bounds",
        "run_id": "run_w7c",
        "claim_id": "claim_bounds",
        "identification_class": "bounds",
        "method_expectations": ["partial_identification"],
        "required_method_families": ["partial_identification"],
        "transportability_requirement": "target_population_limits",
        "uncertainty_class": "bounds",
        "assumption_validation_needs": [{"assumption_id": "monotonicity_bounds"}],
        "facet_refs": ["facet_outcome"],
        "obligation_refs": ["obl_method"],
    }
    payload.update(overrides)
    return MethodValidityRequirementSpec.model_validate(payload)


def test_ir_bridge_consumes_bounds_requirement_and_requires_uncertainty_refs() -> None:
    bridge = build_ir_analytics_claim_bridge(
        claim_bindings=[
            {
                "claim_id": "claim_bounds",
                "analytics_ref": "ir.analytics.bounds.msme",
                "method_output_refs": ["ir.method.bounds.ate"],
                "ir_certificate_refs": ["ir.certificate.bounds.msme"],
                "proof_status": "bounded",
            }
        ],
        method_requirements=[_requirement()],
        run_id="run_w7c",
    )

    assert bridge["status"] == "fail"
    assert bridge["claim_bindings"][0]["method_requirement_refs"] == ["method-req-bounds"]
    assert "ir_analytics_method_requirement_uncertainty_missing" in {
        issue["code"] for issue in bridge["issues"]
    }
    assert bridge["rejected_methods"] == [
        {
            "claim_id": "claim_bounds",
            "method_output_refs": ["ir.method.bounds.ate"],
            "method_requirement_ref": "method-req-bounds",
            "reason_code": "ir_requirement_uncertainty_missing",
            "reason": (
                "Method requirement method-req-bounds requires uncertainty or bounds "
                "refs for claim claim_bounds."
            ),
        }
    ]


def test_ir_bridge_satisfies_negative_certificate_requirement_without_method_output() -> None:
    bridge = build_ir_analytics_claim_bridge(
        claim_bindings=[
            {
                "claim_id": "claim_non_identified",
                "analytics_ref": "ir.analytics.non_id.msme",
                "negative_certificate_refs": ["ir.negative.hedge.msme"],
                "proof_status": "not_identified",
            }
        ],
        method_requirements=[
            _requirement(
                requirement_id="method-req-negative",
                claim_id="claim_non_identified",
                identification_class="negative_certificate",
                method_expectations=["negative_certificate"],
                required_method_families=["negative_certificate"],
                uncertainty_class="none",
            )
        ],
        run_id="run_w7c_negative",
    )

    assert bridge["status"] == "fail"
    assert bridge["summary"]["method_requirement_binding_count"] == 1
    assert bridge["claim_bindings"][0]["method_requirement_refs"] == ["method-req-negative"]
    assert not any(
        issue["code"] == "ir_analytics_method_requirement_method_output_missing"
        for issue in bridge["issues"]
    )
    assert {
        issue["code"] for issue in bridge["issues"]
    } == {"runtime_claim_registry_ir_analytics_blocked"}
