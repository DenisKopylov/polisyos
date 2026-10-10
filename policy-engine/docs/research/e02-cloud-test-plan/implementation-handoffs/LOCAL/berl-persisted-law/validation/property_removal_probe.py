"""Isolated property-removal falsifier for the shared BERL law gate."""

from __future__ import annotations

import runpy
import sys

from polisyos.berl.contracts import validation_rules
from polisyos.runtime.quality.explanation_reliability import _validate_bundle_record
from polisyos.scientist.validation.phase5_preflight import build_phase5_validation_report


def main() -> None:
    # Remove only the shared semantic property in this fresh process. No product source
    # bytes are edited; both persisted consumers should admit the forged conditional row.
    validation_rules._feature_dependence_profile_violations = lambda _: ()

    phase5_test_support = runpy.run_path("tests/unit/scientist/validation/test_phase5_preflight.py")
    payload = phase5_test_support["_present_berl_payload"]()
    payload["assumptions"]["feature_dependence_policy"]["primary"] = "conditional_observational"
    payload["methods"][0]["method_id"] = "kernel_shap_conditional"
    payload["methods"][0]["assumptions"] = {"feature_removal": "conditional_observational"}
    payload["audit"]["artifact_refs"] = ["cas://self-attested/conditional-law-verified"]
    phase5_report = build_phase5_validation_report(
        phase5_test_support["_ctx"](),
        phase5_test_support["_state"](),
        artifact_payload=payload,
        artifact_kind="scientist.explanation_bundle",
    )
    phase5_explanation = next(
        component
        for component in phase5_report.phase5_components
        if component.name == "explanation"
    )
    _require(
        phase5_explanation.status == "pass",
        "Phase5 no longer admits the forged row when the shared property is removed",
    )
    _emit("Phase5 with shared law predicate removed: pass (property is discriminating)")

    reliability_test_support = runpy.run_path(
        "tests/unit/runtime/quality/test_berl_warrant_reliability.py"
    )
    bundle = reliability_test_support["_berl_bundle"](upper_bound=0.03)
    bundle["assumptions"]["feature_dependence_policy"]["primary"] = "conditional_observational"
    bundle["methods"][0]["method_id"] = "kernel_shap_conditional"
    bundle["methods"][0]["assumptions"] = {"feature_removal": "conditional_observational"}
    bundle["audit"]["artifact_refs"] = ["cas://self-attested/conditional-law-verified"]
    reliability_record, issues = _validate_bundle_record(
        bundle,
        thresholds={"max_p95_infidelity_upper_bound": 0.1},
        evidence_ref="sha256:evidence",
    )
    _require(
        reliability_record["threshold_decision"]["status"] == "pass",
        "warrant reliability no longer admits the forged row when the shared property is removed",
    )
    _require(issues == (), "warrant reliability emitted issues after property removal")
    _emit(
        "Warrant reliability with shared law predicate removed: pass (property is discriminating)"
    )


def _emit(value: object) -> None:
    sys.stdout.write(f"{value}\n")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
