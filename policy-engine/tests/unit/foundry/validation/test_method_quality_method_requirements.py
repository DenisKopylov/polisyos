from __future__ import annotations

from polisyos.foundry.validation.method_quality import build_foundry_method_report
from polisyos.method_requirement import MethodValidityRequirementSpec


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _requirement() -> MethodValidityRequirementSpec:
    return MethodValidityRequirementSpec(
        requirement_id="method-req-claim-effect",
        run_id="run_w7c",
        claim_id="claim_effect",
        identification_class="point",
        method_expectations=["causal_effect_estimation"],
        required_method_families=["causal_effect_estimation"],
        transportability_requirement="target_population_limits",
        uncertainty_class="interval",
        assumption_validation_needs=[
            {"assumption_id": "parallel_trends"},
            {"assumption_id": "overlap_or_support"},
        ],
        facet_refs=["facet_outcome"],
        obligation_refs=["obl_method"],
    )


def _selected_method(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "method_id": "causal.did.runtime",
        "method_family": "causal_effect_estimation",
        "method_expectations": ["causal_effect_estimation"],
        "truthfulness_status": "runtime_consistent",
        "input_refs": {"data_snapshot_ref": _sha("1"), "input_bindings_ref": _sha("2")},
        "assumptions": {"parallel_trends": "pass", "overlap_or_support": "pass"},
        "runtime_assumption_gates": [
            {
                "gate_ref": "gate://parallel-trends",
                "assumption": "parallel_trends",
                "status": "pass",
            },
            {
                "gate_ref": "gate://overlap",
                "assumption": "overlap_or_support",
                "status": "pass",
            },
        ],
        "identification_requirements": {"estimand": "ATT", "requirements": ["parallel_trends"]},
        "uncertainty": {"status": "pass", "interval": [0.01, 0.07]},
        "uncertainty_refs": {"uncertainty_envelope_ref": _sha("3")},
        "missingness": {"status": "pass", "missing_rate": 0.01},
        "sensitivity": {"status": "pass", "robustness": "moderate"},
        "transportability_limits": {"target_population": "wartime_msmes"},
        "specification_space": {"primary": "two_way_fixed_effects"},
        "method_result_refs": {"method_result_ref": _sha("4")},
        "limitation_refs": {"method_limitation_ref": _sha("5")},
        "validity_surfaces": {
            "identification": {"status": "present", "ref": _sha("a")},
            "transportability": {"status": "present", "ref": _sha("b")},
            "partial_identification": {"status": "present", "ref": _sha("c")},
            "recoverability": {"status": "present", "ref": _sha("d")},
            "causal_ensemble": {"status": "present", "ref": _sha("e")},
            "falsification": {"status": "present", "ref": _sha("f")},
            "certificate_proof": {"status": "present", "ref": _sha("0")},
        },
    }
    payload.update(overrides)
    return payload


def test_method_quality_report_consumes_requirements_and_marks_selected_method() -> None:
    report = build_foundry_method_report(
        selected_methods=[_selected_method()],
        method_requirements=[_requirement()],
        canary_kind="production",
    )

    assert report["status"] == "pass"
    assert report["method_requirement_statuses"] == {
        "method-req-claim-effect": "satisfied"
    }
    assert report["selected_methods"][0]["method_requirement_refs"] == [
        "method-req-claim-effect"
    ]
    assert report["summary"]["method_requirement_statuses"] == {
        "method-req-claim-effect": "satisfied"
    }


def test_method_quality_report_rejects_method_without_requirement_assumption_gate() -> None:
    report = build_foundry_method_report(
        selected_methods=[
            _selected_method(
                assumptions={"parallel_trends": "pass"},
                runtime_assumption_gates=[
                    {
                        "gate_ref": "gate://parallel-trends",
                        "assumption": "parallel_trends",
                        "status": "pass",
                    }
                ],
            )
        ],
        method_requirements=[_requirement()],
        canary_kind="production",
    )

    assert report["status"] == "fail"
    assert report["selected_methods"] == []
    assert report["rejected_methods"][0]["reason_code"] == (
        "runtime_assumption_validation_missing"
    )
    assert "method_requirement_no_selected_method" in {
        issue["code"] for issue in report["issues"]
    }
