"""Red-first semantic tests for the DS11 trust-claim posture contract."""

from __future__ import annotations

import importlib

import pytest

from polisyos.runtime.quality.claim_registry import normalize_runtime_claim_registry


def _posture_api(name: str):
    """Load one required C01 semantic API or fail with the guarded behavior."""
    try:
        module = importlib.import_module("polisyos.scientist.evidence.claims.posture")
    except ModuleNotFoundError:
        pytest.fail(f"C01 posture module is absent; required semantic API: {name}")
    api = getattr(module, name, None)
    if not callable(api):
        pytest.fail(f"C01 posture module lacks required semantic API: {name}")
    return api


def test_blocked_vetoes_planned_and_supported() -> None:
    """Catch a composer mutation that lets a blocked arm lose its veto."""
    compose = _posture_api("compose_effective_state")

    assert compose(("supported", "planned", "blocked")) == "blocked"


def test_candidate_or_planned_never_composes_to_supported() -> None:
    """Catch a composer mutation that treats candidate or planned as support."""
    compose = _posture_api("compose_effective_state")

    assert compose(("candidate", "supported")) == "blocked"
    assert compose(("planned", "supported")) == "planned"


def test_grounded_performance_requires_governed_evidence_and_prerequisite() -> None:
    """Catch admission of a performance row without governed prerequisite evidence."""
    evaluate = _posture_api("evaluate_grounded_performance")

    assert (
        evaluate(
            {
                "subject": "grounded_performance",
                "governed_evidence": (),
                "prerequisite_establishment": "not_established",
            }
        )
        == "blocked"
    )


def test_posture_artifact_cannot_enter_runtime_claim_registry() -> None:
    """Catch a bridge mutation that lets posture metadata discharge claim-local evidence."""
    build_register = _posture_api("build_posture_register")
    posture_payload = {
        "schema_version": "policyos.trust.claim_posture_register.v1",
        "claims": [
            {
                "claim_id": "final-runtime-claim",
                "effective_state": "supported",
                "source_digest": "sha256:posture-source",
                "limitation_refs": ["cas:posture-limitation"],
                "evidence_refs": ["cas:posture-evidence"],
            }
        ],
    }
    posture_artifact = build_register(posture_payload)
    assert posture_artifact.__class__.__name__ == "ClaimPostureRegisterV1"
    assert posture_artifact.schema_version == "policyos.trust.claim_posture_register.v1"
    with pytest.raises(ValueError, match=r"(?i)extra|unexpected"):
        build_register({**posture_payload, "unexpected": "must not survive strict admission"})
    model_dump = getattr(posture_artifact, "model_dump", None)
    if not callable(model_dump):
        pytest.fail("ClaimPostureRegisterV1 must serialize its posture artifact")
    registry = normalize_runtime_claim_registry(
        model_dump(mode="json"),
        claims=[{"claim_id": "final-runtime-claim", "major": True}],
    )

    assert registry["status"] == "fail"
    assert {
        issue["code"] for issue in registry["issues"]
    } >= {"runtime_claim_registry_scenario_requirement_refs_missing"}
    assert any(
        issue["code"] == "runtime_claim_registry_data_refs_missing"
        for issue in registry["issues"]
    )
