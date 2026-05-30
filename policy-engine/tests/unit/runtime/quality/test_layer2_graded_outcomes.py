from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from polisyos.runtime.quality.graded_outcomes import (
    S1_GRADED_OUTCOME_SCHEMA_VERSION,
    GradedOutcomeEvidenceInput,
    GradedOutcomeInputError,
    compose_graded_outcome,
    graded_outcome_closeout_record,
)

from polisyos.runtime.quality.closeout_reader import build_can_i_closeout_verdict
from polisyos.runtime.quality.projection_semantics import (
    build_policy_design_case_projection_contract_fixture,
)
from tests._helpers.policy_design_case_projection import policy_design_case

REPO_ROOT = Path(__file__).resolve().parents[4]
CORPUS_CASES = REPO_ROOT / "tests" / "fixtures" / "universal-corpus" / "cases"
NOW = datetime(2026, 5, 30, tzinfo=UTC)


def _cases() -> list[dict[str, object]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(CORPUS_CASES.glob("*.json"))
    ]


def _case_id(case: dict[str, object]) -> str:
    return str(case.get("case_id") or case.get("id"))


def _label(case: dict[str, object]) -> str:
    adjudication = case.get("expert_adjudication")
    assert isinstance(adjudication, dict)
    return str(adjudication.get("case_label") or "")


def _input_for(case: dict[str, object], *, authority_level: str) -> GradedOutcomeEvidenceInput:
    case_id = _case_id(case)
    return GradedOutcomeEvidenceInput(
        schema_version=S1_GRADED_OUTCOME_SCHEMA_VERSION,
        case_id=case_id,
        claim_id=f"claim:{case_id}:main",
        authority_level=authority_level,
        requested_outcome="publish_with_limitation",
        evidence_profile="partial_or_proxy",
        proxy_evidence_refs=(f"corpus://{case_id}/proxy-evidence",),
        partial_evidence_refs=(f"corpus://{case_id}/partial-support",),
        limitation_reason_codes=("expert_limitation_required",),
        mandatory_gate_state="none",
        owner="team-evaluation",
        decision_owner_ref=f"review://layer2-s1/{case_id}/governed-owner",
        authority_profile_ref=f"authority_profile.{authority_level}",
        review_refs=(f"review://layer2-s1/{case_id}/limitation",),
        ttl_expires_at="2026-06-30T00:00:00Z",
        public_limitation_note=(
            "This governed output is publishable only with explicit limitation."
        ),
        rule_version_ref="policyos.layer2.s1.graded_outcomes.v1",
    )


def _w4_record(
    schema_version: str,
    *,
    status: str = "pass",
    issues: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": schema_version,
        "status": status,
        "authority_role": "runtime_reader",
        "provenance_kind": "runtime_emitted",
        "producer": "test.layer2_s1",
        "runtime_event_ref": "event://layer2-s1/test",
        "cas_ref": "sha256:" + "a" * 64,
        "issues": list(issues or []),
    }


def _passing_w4_records() -> dict[str, dict[str, object]]:
    return {
        "i4_policy_design_case_graph": _w4_record(
            "policyos.runtime.policy_design_case.wave4_i4_graph.v1"
        ),
        "portfolio_effective_support": _w4_record(
            "policyos.runtime.policy_design_case.portfolio_effective_support.v1"
        ),
        "lifecycle_reissue": _w4_record(
            "policyos.runtime.policy_design_case.lifecycle_reissue_report.v1"
        ),
        "projection_consumer_contract": _w4_record(
            "policyos.runtime.policy_design_case.projection_contract_fixture.v1"
        ),
        "formal_invariants": _w4_record("policyos.runtime.formal_invariants.v1"),
        "source_truth": _w4_record("policyos.runtime.source_truth.v1"),
        "conflict_materialization": _w4_record(
            "policyos.runtime.policy_design_case.conflict_materialization_closeout.v1"
        ),
        "attestation": _w4_record("policyos.runtime.attestation.v1"),
        "closeout_compatibility": _w4_record(
            "policyos.runtime.can_i_closeout_compatibility.v1"
        ),
        "semantic_binding": _w4_record("policyos.runtime.semantic_binding.v1"),
        "claim_registry": _w4_record("policyos.runtime.claim_registry.v1"),
        "pdc_record_family_status": _w4_record(
            "policyos.policy_design_case.record_family_coverage.v1"
        ),
        "projection_publication_state": _w4_record(
            "policyos.runtime.policy_design_case.projection_publication_state.v1"
        ),
        "run_cost_gate": _w4_record("policyos.runtime.run_cost_gate.v1"),
        "complexity_self_fmea": _w4_record(
            "policyos.runtime.run_cost_proportionality.v1"
        ),
        "audit_verifier_ingestion": _w4_record("policyos.runtime.audit_verifier.v1"),
        "prompt_tool_repair_fmea": _w4_record(
            "policyos.runtime.prompt_tool_repair_fmea.v1"
        ),
    }


def test_governed_limitation_required_cases_route_to_publish_with_limitation() -> None:
    limitation_cases = [case for case in _cases() if _label(case) == "limitation_required"]

    assert len(limitation_cases) == 9

    decisions = [
        compose_graded_outcome(_input_for(case, authority_level="governed"))
        for case in limitation_cases
    ]

    assert {decision.outcome for decision in decisions} == {"publish_with_limitation"}
    assert all(decision.closeout_effect == "limited_closeout" for decision in decisions)
    assert all(decision.blockers == () for decision in decisions)
    assert all(len(decision.deficit_records) == 1 for decision in decisions)
    assert {
        row["disposition"]
        for decision in decisions
        for row in decision.deficit_records
    } == {"publish_with_limitation"}
    assert {
        row["authority_level"]
        for decision in decisions
        for row in decision.deficit_records
    } == {"governed"}


def test_research_limitation_routes_but_forbids_publication_authority() -> None:
    limitation_case = next(case for case in _cases() if _label(case) == "limitation_required")

    decision = compose_graded_outcome(_input_for(limitation_case, authority_level="research"))

    assert decision.outcome == "publish_with_limitation"
    assert decision.closeout_effect == "limited_closeout"
    assert "publication_authority_without_closeout" in decision.authority_boundary[
        "may_not_use_for"
    ]
    assert "production_closeout_authority" in decision.authority_boundary["may_not_use_for"]
    assert decision.deficit_records[0]["authority_level"] == "research"


def test_governed_limitation_requires_decision_owner_before_closeout_change() -> None:
    limitation_case = next(case for case in _cases() if _label(case) == "limitation_required")

    with pytest.raises(
        GradedOutcomeInputError,
        match="publish_with_limitation requires decision_owner_ref and review_refs",
    ):
        compose_graded_outcome(
            _input_for(limitation_case, authority_level="governed").model_copy(
                update={"decision_owner_ref": None, "review_refs": ()}
            )
        )


def test_production_strictness_blocks_all_corpus_cases_under_proxy_evidence() -> None:
    decisions = [
        compose_graded_outcome(_input_for(case, authority_level="production"))
        for case in _cases()
    ]

    assert len(decisions) == 13
    assert {decision.outcome for decision in decisions} == {"typed_blocker"}
    assert {decision.closeout_effect for decision in decisions} == {"closeout_blocked"}
    assert all(decision.limitations == () for decision in decisions)
    assert all(decision.blockers for decision in decisions)
    assert {
        blocker["code"]
        for decision in decisions
        for blocker in decision.blockers
    } == {"graded_outcome_production_proxy_block"}


def test_fabricated_limitation_without_proxy_or_partial_evidence_is_rejected() -> None:
    with pytest.raises(
        GradedOutcomeInputError,
        match="publish_with_limitation requires proxy or partial evidence refs",
    ):
        compose_graded_outcome(
            GradedOutcomeEvidenceInput(
                schema_version=S1_GRADED_OUTCOME_SCHEMA_VERSION,
                case_id="fabricated-limitation",
                claim_id="claim:fabricated",
                authority_level="governed",
                requested_outcome="publish_with_limitation",
                evidence_profile="partial_or_proxy",
                proxy_evidence_refs=(),
                partial_evidence_refs=(),
                limitation_reason_codes=("unsupported_limitation",),
                mandatory_gate_state="none",
                owner="team-evaluation",
                decision_owner_ref="review://layer2-s1/fabricated/governed-owner",
                authority_profile_ref="authority_profile.governed",
                review_refs=("review://layer2-s1/fabricated/limitation",),
                ttl_expires_at="2026-06-30T00:00:00Z",
                public_limitation_note="Unsupported limitation.",
                rule_version_ref="policyos.layer2.s1.graded_outcomes.v1",
            )
        )


def test_non_overridable_gate_dominates_limitation_request() -> None:
    decision = compose_graded_outcome(
        _input_for(_cases()[0], authority_level="governed").model_copy(
            update={"mandatory_gate_state": "non_overridable"}
        )
    )

    assert decision.outcome == "typed_blocker"
    assert decision.closeout_effect == "closeout_blocked"
    assert decision.limitations == ()
    assert decision.blockers[0]["code"] == "graded_outcome_non_overridable_gate"


def test_governed_limitation_persists_to_closeout_downgrade() -> None:
    decision = compose_graded_outcome(_input_for(_cases()[0], authority_level="governed"))
    closeout_record = graded_outcome_closeout_record(
        [decision],
        generated_at=NOW,
    )

    module_records = _passing_w4_records()
    module_records["deficit_crosswalk"] = closeout_record
    verdict = build_can_i_closeout_verdict(
        run_id="run-layer2-s1",
        module_records=module_records,
    )

    assert closeout_record["schema_version"] == "policyos.runtime.status_envelope.v1"
    assert closeout_record["status"] == "pass"
    assert closeout_record["authority_role"] == "runtime_reader"
    assert closeout_record["producer"] == "polisyos.runtime.quality.graded_outcomes"
    assert verdict["status"] == "closed_with_limitations"
    assert verdict["verdict"] == "can_closeout_with_limitations"
    assert verdict["summary"]["limitation_count"] == 1
    assert verdict["limitations"][0]["deficit_id"].startswith("limitation:")


def test_limitation_does_not_override_existing_closeout_blocker() -> None:
    decision = compose_graded_outcome(_input_for(_cases()[0], authority_level="governed"))
    closeout_record = graded_outcome_closeout_record([decision], generated_at=NOW)
    module_records = _passing_w4_records()
    module_records["deficit_crosswalk"] = closeout_record
    module_records["semantic_binding"] = _w4_record(
        "policyos.runtime.semantic_binding.v1",
        status="fail",
        issues=[
            {
                "code": "semantic_binding_claim_missing",
                "severity": "fail",
                "message": "Major claim lacks semantic closure.",
                "producer": "test.semantic_binding",
                "claim_id": "claim:blocked",
            }
        ],
    )

    verdict = build_can_i_closeout_verdict(
        run_id="run-layer2-s1",
        module_records=module_records,
    )

    assert verdict["status"] == "blocked"
    assert verdict["can_closeout"] is False
    assert verdict["summary"]["limitation_count"] == 1
    assert "semantic_binding_claim_missing" in {
        blocker["upstream_issue_code"] for blocker in verdict["blockers"]
    }


def test_public_reviewer_and_expert_projections_surface_closeout_limitation() -> None:
    decision = compose_graded_outcome(_input_for(_cases()[0], authority_level="governed"))
    closeout_record = graded_outcome_closeout_record([decision], generated_at=NOW)
    module_records = _passing_w4_records()
    module_records["deficit_crosswalk"] = closeout_record
    verdict = build_can_i_closeout_verdict(
        run_id="run-layer2-s1",
        module_records=module_records,
    )

    fixture = build_policy_design_case_projection_contract_fixture(
        policy_design_case=policy_design_case(),
        closeout_verdict=verdict,
        audiences=("public", "reviewer", "expert"),
        generated_at=NOW,
    )

    assert fixture["status"] == "pass"
    for audience in ("public", "reviewer", "expert"):
        projection = fixture["projections"][audience]
        assert projection["closeout_truth"]["status"] == "closed_with_limitations"
        assert projection["closeout_truth"]["limitation_codes"]
        assert any(
            gap["publication_effect"] == "publish_with_limitation"
            for gap in projection["projection_gaps"]
        )
