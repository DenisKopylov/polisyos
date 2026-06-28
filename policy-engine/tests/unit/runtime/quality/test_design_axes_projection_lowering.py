from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from pydantic import ValidationError

import polisyos.runtime.quality as runtime_quality

CASE_ID = "ua-msme-affordable-loans-2022"
S9_SCHEMA_VERSION = "policyos.policy_design_case.layer2_s9_projection_lowering.v1"
S9_RULE_VERSION_REF = "policyos.layer2.s9.projection_lowering.v1"
S9_FLOOR_ID = "s9_projection_faithfulness"
SOURCE_DESIGN_RECORD_REF = "pdc://layer2/s2/ua-msme/design-record-v0"
SOURCE_DESIGN_RECORD_DIGEST = "sha256:" + "2" * 64
CANONICAL_REF = "pdc://layer2/s9/ua-msme/canonical-design-record"
CANONICAL_DIGEST = "sha256:" + "9" * 64
SOURCE_REVISION_REF = "git://policyos/layer2/s9/red-first"
REQUEST_REF = "pdc://layer2/s9/ua-msme/projection-request/public"
RENDER_REF = "pdc://layer2/s9/ua-msme/projection-render/public"
FAITHFULNESS_REF = "pdc://layer2/s9/ua-msme/faithfulness/public"
LIMITATION_REF = "pdc://layer2/s6/ua-msme/measurability-limitation"
BLOCKER_REF = "pdc://layer2/s6/ua-msme/strategic-response-blocker"
VALUE_TRADEOFF_REF = "pdc://layer2/s8/ua-msme/value-tradeoff-disclosure"


def _s9(name: str) -> Any:
    return getattr(runtime_quality, name)


def _as_mapping(record: object) -> Mapping[str, Any]:
    if hasattr(record, "model_dump"):
        return record.model_dump(mode="json")  # type: ignore[no-any-return]
    if isinstance(record, Mapping):
        return record
    raise TypeError(f"Expected mapping-like record, got {type(record)!r}")


def _authority_boundary(
    *,
    authoritative_for: list[str] | None = None,
    posture: str = "shadow",
) -> dict[str, object]:
    return {
        "authoritative_for": authoritative_for or ["projection_faithfulness"],
        "may_not_use_for": [
            "production_recommendation",
            "production_claim_authority",
            "rollout_authority",
            "publication_authority",
            "claim_authority",
            "approval_authority",
            "runtime_closeout_authority",
            "scorecard_authority",
            "s10_forecast_support",
            "s11_calibration",
            "s12_envelope_growth",
            "s13_accountability_closure",
            "s14_universality",
        ],
        "source_authority": "deterministic_producer",
        "posture": posture,
        "rule_version_refs": [S9_RULE_VERSION_REF],
    }


def _canonical_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": S9_SCHEMA_VERSION,
        "record_id": "layer2.s9.canonical-design-record.ua-msme",
        "record_ref": CANONICAL_REF,
        "source_design_record_ref": SOURCE_DESIGN_RECORD_REF,
        "source_design_record_digest": SOURCE_DESIGN_RECORD_DIGEST,
        "source_revision_ref": SOURCE_REVISION_REF,
        "canonical_design_record_revision_ref": (
            "pdc://layer2/s9/ua-msme/canonical-design-record/revision/001"
        ),
        "recursive_design_graph_refs": ["pdc://layer2/s5/ua-msme/recursive-design-graph"],
        "claim_bound_evidence_portfolio_refs": ["claim-portfolio://ua-msme/evidence-bound"],
        "pareto_tradeoff_value_choice_refs": [VALUE_TRADEOFF_REF],
        "axis_position_refs": ["pdc://layer2/s2/ua-msme/axis/value-choice"],
        "firewall_status_refs": [BLOCKER_REF],
        "certified_envelope_ref": "pdc://layer2/s2/ua-msme/envelope/shadow",
        "search_ledger_refs": ["pdc://layer2/s2/ua-msme/search-ledger"],
        "counterexample_refinement_refs": [
            "pdc://layer2/s2/ua-msme/counterexample/001",
            "pdc://layer2/s2/ua-msme/refinement/001",
        ],
        "assurance_case_refs": ["pdc://layer2/s9/ua-msme/assurance/projection"],
        "limitation_refs": [LIMITATION_REF],
        "abstention_refs": ["pdc://layer2/s2/ua-msme/abstention/budget-gap"],
        "lowering_artifact_refs": ["pdc://layer2/s9/ua-msme/lowering/machine-contract"],
        "projection_audiences": ["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"],
        "projection_status": "shadow",
        "authority_boundary": _authority_boundary(
            authoritative_for=["canonical_design_record_maturity"]
        ),
        "rule_version_ref": S9_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _projection_request_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "request_id": "layer2.s9.request.public",
        "request_ref": REQUEST_REF,
        "source_design_record_ref": SOURCE_DESIGN_RECORD_REF,
        "source_design_record_digest": SOURCE_DESIGN_RECORD_DIGEST,
        "canonical_design_record_ref": CANONICAL_REF,
        "canonical_design_record_digest": CANONICAL_DIGEST,
        "operation": "projection",
        "audience": "PUBLIC",
        "aspect": "tradeoff_brief",
        "depth": "design_candidate",
        "redaction": "public_redacted",
        "format": "public_brief",
        "revision_policy": "same_revision",
        "source_revision_ref": SOURCE_REVISION_REF,
        "reissue_ref": None,
        "requested_field_refs": [
            LIMITATION_REF,
            BLOCKER_REF,
            VALUE_TRADEOFF_REF,
        ],
        "authority_boundary": _authority_boundary(authoritative_for=["projection_request"]),
        "rule_version_ref": S9_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _omission_manifest_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "omitted_field_ref": LIMITATION_REF,
        "audience": "PUBLIC",
        "reason": "public_redaction_summary",
        "source_ref": CANONICAL_REF,
        "publication_effect": "limitation_disclosed_not_removed",
    }
    row.update(overrides)
    return row


def _render_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "render_id": "layer2.s9.render.public",
        "render_ref": RENDER_REF,
        "request_ref": REQUEST_REF,
        "canonical_design_record_ref": CANONICAL_REF,
        "canonical_design_record_digest": CANONICAL_DIGEST,
        "source_revision_ref": SOURCE_REVISION_REF,
        "audience": "PUBLIC",
        "aspect": "tradeoff_brief",
        "depth": "design_candidate",
        "redaction": "public_redacted",
        "format": "public_brief",
        "rendered_claim_refs": [
            "claim://ua-msme/shadow-design",
            LIMITATION_REF,
            VALUE_TRADEOFF_REF,
        ],
        "omission_manifest": [_omission_manifest_row()],
        "authority_boundary": _authority_boundary(authoritative_for=["projection_render"]),
        "may_not_use_for": _authority_boundary()["may_not_use_for"],
        "rule_version_ref": S9_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _faithfulness_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "faithfulness_id": "layer2.s9.faithfulness.public",
        "faithfulness_ref": FAITHFULNESS_REF,
        "render_ref": RENDER_REF,
        "request_ref": REQUEST_REF,
        "canonical_design_record_ref": CANONICAL_REF,
        "canonical_design_record_digest": CANONICAL_DIGEST,
        "source_revision_ref": SOURCE_REVISION_REF,
        "faithfulness_status": "pass",
        "issue_codes": [],
        "added_claim_refs": [],
        "hidden_blocker_refs": [],
        "hidden_limitation_refs": [],
        "tradeoff_direction_status": "preserved",
        "shadow_approval_status": "not_approved",
        "consumer_contract_ref": (
            "policyos.runtime.policy_design_case.projection_contract_verification.v1"
        ),
        "authority_boundary": _authority_boundary(
            authoritative_for=["projection_faithfulness"]
        ),
        "rule_version_ref": S9_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _lowering_request_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "request_id": "layer2.s9.lowering.legal-diff",
        "request_ref": "pdc://layer2/s9/ua-msme/lowering-request/legal-diff",
        "canonical_design_record_ref": CANONICAL_REF,
        "canonical_design_record_digest": CANONICAL_DIGEST,
        "source_design_record_ref": SOURCE_DESIGN_RECORD_REF,
        "source_revision_ref": SOURCE_REVISION_REF,
        "lowering_kind": "legal_diff",
        "requested_depth": "legal_budget_procedure",
        "grounding_refs": [],
        "post_closeout_state": "open_shadow_case",
        "authority_boundary": _authority_boundary(authoritative_for=["lowering_request"]),
        "rule_version_ref": S9_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _lowering_gate_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "gate_id": "layer2.s9.lowering-gate.machine-contract",
        "gate_ref": "pdc://layer2/s9/ua-msme/lowering-gate/machine-contract",
        "request_ref": "pdc://layer2/s9/ua-msme/lowering-request/machine-contract",
        "canonical_design_record_ref": CANONICAL_REF,
        "source_revision_ref": SOURCE_REVISION_REF,
        "status": "lowering_allowed_existing_scope",
        "missing_grounding_refs": [],
        "inspected_grounding_refs": ["pdc://layer2/s9/ua-msme/grounding/machine-contract"],
        "may_not_use_for": _authority_boundary()["may_not_use_for"],
        "authority_boundary": _authority_boundary(authoritative_for=["lowering_gate"]),
        "rule_version_ref": S9_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _issue_codes(record: object) -> set[str]:
    mapping = _as_mapping(record)
    return {str(code) for code in mapping.get("issue_codes", [])}


def test_s9_projection_contracts_are_strict_replayable_and_exported() -> None:
    required_exports = {
        "LAYER2_S9_PROJECTION_LOWERING_SCHEMA_VERSION": S9_SCHEMA_VERSION,
        "LAYER2_S9_PROJECTION_LOWERING_RULE_VERSION": S9_RULE_VERSION_REF,
        "S9_PROJECTION_FLOOR_ID": S9_FLOOR_ID,
    }
    for name, expected in required_exports.items():
        assert _s9(name) == expected

    for name in [
        "CanonicalDesignRecord",
        "ProjectionAlgebraRequest",
        "ProjectionRenderRecord",
        "ProjectionFaithfulnessRecord",
        "LoweringRequestRecord",
        "LoweringAuthorityGateRecord",
        "LoweringArtifactRecord",
        "LoweringAppendReceipt",
        "DesignRecordMaturityReport",
        "ProjectionLoweringIntegrityReport",
    ]:
        model = _s9(name)
        assert model.model_config.get("extra") == "forbid", name

    request = _s9("ProjectionAlgebraRequest").model_validate(_projection_request_payload())
    render = _s9("ProjectionRenderRecord").model_validate(_render_payload())
    faithfulness = _s9("ProjectionFaithfulnessRecord").model_validate(
        _faithfulness_payload()
    )

    assert request.request_ref == render.request_ref == faithfulness.request_ref
    assert render.canonical_design_record_digest == CANONICAL_DIGEST
    assert faithfulness.authority_boundary.posture == "shadow"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _s9("ProjectionAlgebraRequest").model_validate(
            {
                **request.model_dump(mode="json"),
                "hidden_authority_upgrade": "approval",
            }
        )


def test_canonical_design_record_contains_graph_evidence_assurance_limitations_and_lowering_refs() -> None:
    record = _s9("CanonicalDesignRecord").model_validate(_canonical_payload())

    assert record.source_design_record_ref == SOURCE_DESIGN_RECORD_REF
    assert record.source_revision_ref == SOURCE_REVISION_REF
    assert record.recursive_design_graph_refs
    assert record.claim_bound_evidence_portfolio_refs
    assert record.pareto_tradeoff_value_choice_refs == [VALUE_TRADEOFF_REF]
    assert record.assurance_case_refs
    assert record.limitation_refs == [LIMITATION_REF]
    assert record.lowering_artifact_refs
    assert record.projection_status == "shadow"
    assert "production_recommendation" in record.authority_boundary.may_not_use_for

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _s9("CanonicalDesignRecord").model_validate(
            {
                **record.model_dump(mode="json"),
                "public_brief_text": "projection text is not canonical truth",
            }
        )


def test_projection_grammar_request_covers_audience_aspect_depth_redaction_format_revision() -> None:
    request = _s9("ProjectionAlgebraRequest").model_validate(
        _projection_request_payload(
            audience="MACHINE",
            aspect="machine_contract",
            depth="design_candidate",
            redaction="machine_full",
            format="json",
            revision_policy="same_revision",
        )
    )

    assert request.operation == "projection"
    assert request.audience == "MACHINE"
    assert request.aspect == "machine_contract"
    assert request.depth == "design_candidate"
    assert request.redaction == "machine_full"
    assert request.format == "json"
    assert request.revision_policy == "same_revision"
    assert request.source_revision_ref == SOURCE_REVISION_REF

    with pytest.raises(ValidationError, match=r"PUBLIC.*machine_full|machine_full.*PUBLIC"):
        _s9("ProjectionAlgebraRequest").model_validate(
            _projection_request_payload(audience="PUBLIC", redaction="machine_full")
        )


def test_public_projection_missing_load_bearing_limitation_fails_faithfulness() -> None:
    canonical = _s9("CanonicalDesignRecord").model_validate(_canonical_payload())
    request = _s9("ProjectionAlgebraRequest").model_validate(_projection_request_payload())
    render = _s9("ProjectionRenderRecord").model_validate(
        _render_payload(rendered_claim_refs=["claim://ua-msme/shadow-design"], omission_manifest=[])
    )

    faithfulness = _s9("verify_projection_faithfulness")(
        canonical_design_record=canonical,
        projection_request=request,
        projection_render=render,
    )

    assert _as_mapping(faithfulness)["faithfulness_status"] == "fail"
    assert "s9_public_projection_missing_limitation" in _issue_codes(faithfulness)
    assert LIMITATION_REF in _as_mapping(faithfulness)["hidden_limitation_refs"]


def test_prose_adding_claim_absent_from_design_record_is_rejected() -> None:
    canonical = _s9("CanonicalDesignRecord").model_validate(_canonical_payload())
    request = _s9("ProjectionAlgebraRequest").model_validate(_projection_request_payload())
    render = _s9("ProjectionRenderRecord").model_validate(
        _render_payload(
            rendered_claim_refs=[
                "claim://ua-msme/shadow-design",
                LIMITATION_REF,
                "claim://ua-msme/new-public-benefit-claim",
            ]
        )
    )

    faithfulness = _s9("verify_projection_faithfulness")(
        canonical_design_record=canonical,
        projection_request=request,
        projection_render=render,
    )

    assert _as_mapping(faithfulness)["faithfulness_status"] == "fail"
    assert "s9_projection_added_claim" in _issue_codes(faithfulness)
    assert "claim://ua-msme/new-public-benefit-claim" in _as_mapping(faithfulness)[
        "added_claim_refs"
    ]


def test_tradeoff_inversion_fails_faithfulness() -> None:
    canonical = _s9("CanonicalDesignRecord").model_validate(_canonical_payload())
    request = _s9("ProjectionAlgebraRequest").model_validate(_projection_request_payload())
    render = _s9("ProjectionRenderRecord").model_validate(
        _render_payload(
            rendered_claim_refs=[
                "claim://ua-msme/shadow-design",
                LIMITATION_REF,
                VALUE_TRADEOFF_REF,
                "tradeoff://ua-msme/inverted-fiscal-burden",
            ]
        )
    )

    faithfulness = _s9("verify_projection_faithfulness")(
        canonical_design_record=canonical,
        projection_request=request,
        projection_render=render,
    )

    assert _as_mapping(faithfulness)["faithfulness_status"] == "fail"
    assert "s9_tradeoff_inversion" in _issue_codes(faithfulness)
    assert _as_mapping(faithfulness)["tradeoff_direction_status"] == "inverted"


def test_shadow_candidate_cannot_render_as_approved() -> None:
    canonical = _s9("CanonicalDesignRecord").model_validate(_canonical_payload())
    request = _s9("ProjectionAlgebraRequest").model_validate(_projection_request_payload())
    render = _s9("ProjectionRenderRecord").model_validate(
        _render_payload(rendered_claim_refs=["claim://ua-msme/approved-shadow-candidate"])
    )

    faithfulness = _s9("verify_projection_faithfulness")(
        canonical_design_record=canonical,
        projection_request=request,
        projection_render=render,
    )

    assert _as_mapping(faithfulness)["faithfulness_status"] == "fail"
    assert "s9_shadow_candidate_rendered_as_approved" in _issue_codes(faithfulness)
    assert _as_mapping(faithfulness)["shadow_approval_status"] == "rendered_as_approved"


def test_legal_lowering_without_grounding_is_blocked_while_public_projection_passes() -> None:
    canonical = _s9("CanonicalDesignRecord").model_validate(_canonical_payload())
    request = _s9("ProjectionAlgebraRequest").model_validate(_projection_request_payload())
    render = _s9("ProjectionRenderRecord").model_validate(_render_payload())
    projection_faithfulness = _s9("verify_projection_faithfulness")(
        canonical_design_record=canonical,
        projection_request=request,
        projection_render=render,
    )
    lowering_request = _s9("LoweringRequestRecord").model_validate(
        _lowering_request_payload()
    )

    gate = _s9("gate_lowering_request")(
        canonical_design_record=canonical,
        lowering_request=lowering_request,
    )

    assert _as_mapping(projection_faithfulness)["faithfulness_status"] == "pass"
    assert _as_mapping(gate)["status"] == "lowering_blocked_missing_grounding"
    assert "legal://ua-msme/grounding" in _as_mapping(gate)["missing_grounding_refs"]
    assert "production_recommendation" in _as_mapping(gate)["may_not_use_for"]


def test_allowed_lowering_persists_verified_append_receipt() -> None:
    lowering_request = _s9("LoweringRequestRecord").model_validate(
        _lowering_request_payload(
            request_id="layer2.s9.lowering.machine-contract",
            request_ref="pdc://layer2/s9/ua-msme/lowering-request/machine-contract",
            lowering_kind="machine_contract",
            requested_depth="design_candidate",
            grounding_refs=["pdc://layer2/s9/ua-msme/grounding/machine-contract"],
        )
    )
    gate = _s9("LoweringAuthorityGateRecord").model_validate(_lowering_gate_payload())

    append = _s9("append_verified_lowering_artifact")(
        lowering_request=lowering_request,
        gate_record=gate,
        artifact_ref="pdc://layer2/s9/ua-msme/lowering-artifact/machine-contract",
        verification_ref="pdc://layer2/s9/ua-msme/lowering-verification/machine-contract",
    )
    append_mapping = _as_mapping(append)

    assert append_mapping["artifact"]["lowering_kind"] == "machine_contract"
    assert append_mapping["append_receipt"]["verification_status"] == "verified"
    assert append_mapping["append_receipt"]["source_revision_ref"] == SOURCE_REVISION_REF
    assert append_mapping["append_receipt"]["replay_refs"]


def test_machine_projection_preserves_refs_authority_boundary_and_omission_manifest() -> None:
    request = _s9("ProjectionAlgebraRequest").model_validate(
        _projection_request_payload(
            audience="MACHINE",
            aspect="machine_contract",
            redaction="machine_full",
            format="json",
        )
    )
    render = _s9("ProjectionRenderRecord").model_validate(
        _render_payload(
            audience="MACHINE",
            aspect="machine_contract",
            redaction="machine_full",
            format="json",
        )
    )

    assert render.canonical_design_record_ref == request.canonical_design_record_ref
    assert render.source_revision_ref == request.source_revision_ref
    assert render.omission_manifest
    assert "runtime_closeout_authority" in render.authority_boundary.may_not_use_for


def test_post_closeout_lowering_requires_reissue_or_reopen() -> None:
    canonical = _s9("CanonicalDesignRecord").model_validate(_canonical_payload())
    lowering_request = _s9("LoweringRequestRecord").model_validate(
        _lowering_request_payload(
            post_closeout_state="closed",
            source_revision_ref="git://policyos/layer2/s9/new-source-revision",
        )
    )

    gate = _s9("gate_lowering_request")(
        canonical_design_record=canonical,
        lowering_request=lowering_request,
    )

    assert _as_mapping(gate)["status"] == "lowering_blocked_requires_reissue"
    assert "reissue_required" in _as_mapping(gate)["action_route"]


def test_projection_cannot_mint_claim_scorecard_or_closeout_authority() -> None:
    canonical = _s9("CanonicalDesignRecord").model_validate(_canonical_payload())
    request = _s9("ProjectionAlgebraRequest").model_validate(_projection_request_payload())
    render = _s9("ProjectionRenderRecord").model_validate(
        _render_payload(
            authority_boundary=_authority_boundary(
                authoritative_for=["claim_authority"],
                posture="governed",
            ),
            may_not_use_for=["production_recommendation"],
        )
    )

    faithfulness = _s9("verify_projection_faithfulness")(
        canonical_design_record=canonical,
        projection_request=request,
        projection_render=render,
    )

    assert _as_mapping(faithfulness)["faithfulness_status"] == "fail"
    assert "s9_projection_mints_authority" in _issue_codes(faithfulness)


def test_s9_integrity_report_records_false_clear_counts() -> None:
    pass_record = _s9("ProjectionFaithfulnessRecord").model_validate(_faithfulness_payload())
    failed_record = _s9("ProjectionFaithfulnessRecord").model_validate(
        _faithfulness_payload(
            faithfulness_id="layer2.s9.faithfulness.public.failed",
            faithfulness_ref="pdc://layer2/s9/ua-msme/faithfulness/public/failed",
            faithfulness_status="fail",
            issue_codes=["s9_projection_added_claim"],
            added_claim_refs=["claim://ua-msme/new-public-benefit-claim"],
        )
    )

    report = _s9("s9_projection_lowering_integrity")(
        projection_faithfulness_records=[pass_record, failed_record],
        lowering_gate_records=[
            _s9("LoweringAuthorityGateRecord").model_validate(_lowering_gate_payload())
        ],
        negative_control_results={
            "added_prose_claim": {"expected_false_clear": False, "actual_clear": False},
            "tradeoff_inversion": {"expected_false_clear": False, "actual_clear": False},
        },
    )
    report_mapping = _as_mapping(report)

    assert report_mapping["floor_id"] == S9_FLOOR_ID
    assert report_mapping["projection_faithfulness_denominator"] == 2
    assert report_mapping["false_clear_counts"]["added_prose_claim"] == 0
    assert report_mapping["false_clear_counts"]["tradeoff_inversion"] == 0
    assert report_mapping["issue_counts"]["s9_projection_added_claim"] == 1
