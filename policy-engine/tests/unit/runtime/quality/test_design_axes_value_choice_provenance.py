from __future__ import annotations

import json
from copy import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

import polisyos.runtime.quality as runtime_quality

CASE_ID = "ua-msme-affordable-loans-2022"
RULE_VERSION_REF = "policyos.layer2.s8.value_choice.v1"
FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "fixtures/layer2/s8"
NOW = datetime(2026, 6, 1, tzinfo=UTC)


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def _s8(name: str) -> Any:
    return getattr(runtime_quality, name)


def _authority_boundary(
    *,
    authoritative_for: list[str],
    source_authority: str = "human_governance",
    posture: str = "governed",
) -> dict[str, object]:
    return {
        "authoritative_for": authoritative_for,
        "may_not_use_for": [
            "production_recommendation",
            "production_claim_authority",
            "publication_authority",
            "scalar_welfare_authority",
            "preference_learning_authority",
            "mandate_creation",
            "s9_projection_maturity",
            "s10_forecast_support",
            "s11_calibration",
            "s12_envelope_growth",
            "s13_accountability_closure",
            "s14_universality",
        ],
        "source_authority": source_authority,
        "posture": posture,
        "rule_version_refs": [RULE_VERSION_REF],
    }


def _authorized_schedule_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schedule_id": "layer2.s8.schedule.ua-msme.2026",
        "schedule_ref": "pdc://layer2/s8/ua-msme/value-schedule/authorized",
        "case_id": CASE_ID,
        "mandate_record_ref": "pdc://layer2/s6/ua-msme/mandate-legitimacy",
        "s6_mandate_firewall_disposition": "pass",
        "mandate_source_dispositions": ["grounded"],
        "principal_refs": ["principal://ua/ministry-of-economy"],
        "source_class": "authorized_governance_schedule",
        "review_status": "approved",
        "effective_at": NOW,
        "social_weight_provenance_refs": [
            "foundry://welfare/social-weight-provenance/public-budget-2026"
        ],
        "authority_boundary": _authority_boundary(
            authoritative_for=["authorized_value_schedule", "value_choice_provenance"]
        ),
        "may_not_use_for": [
            "production_recommendation",
            "scalar_welfare_authority",
            "preference_learning_authority",
        ],
        "rule_version_ref": RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _objective_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "record_id": "layer2.s8.objective-provenance.ua-msme",
        "record_ref": "pdc://layer2/s8/ua-msme/objective-provenance",
        "case_id": CASE_ID,
        "objective_refs": [
            "objective://credit_access",
            "objective://fiscal_burden_per_beneficiary",
        ],
        "objective_source_refs": ["pdc://layer2/s6/ua-msme/mandate-legitimacy"],
        "value_schedule_ref": "pdc://layer2/s8/ua-msme/value-schedule/authorized",
        "measurability_refs": ["pdc://layer2/s6/ua-msme/measurability-adequacy"],
        "proxy_value_loss_disclosures": [
            {
                "construct_ref": "construct://credit_access",
                "value_loss_disclosure_ref": "pdc://layer2/s6/ua-msme/value-loss",
            }
        ],
        "mandate_refs": ["pdc://layer2/s6/ua-msme/mandate-legitimacy"],
        "p20_firewall_status": "pass",
        "p22_firewall_status": "pass",
        "authority_boundary": _authority_boundary(
            authoritative_for=["objective_function_provenance"]
        ),
        "rule_version_ref": RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _pareto_archive_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "archive_id": "layer2.s8.pareto-archive.ua-msme",
        "archive_ref": "pdc://layer2/s8/ua-msme/pareto-archive",
        "case_id": CASE_ID,
        "frontier_refs": ["foundry://welfare/frontier/ua-msme"],
        "nondominated_alternative_ids": ["targeted_credit", "cash_transfer"],
        "rejected_nondominated_alternative_ids": ["cash_transfer"],
        "objective_refs": [
            "objective://credit_access",
            "objective://fiscal_burden_per_beneficiary",
        ],
        "value_schedule_ref": "pdc://layer2/s8/ua-msme/value-schedule/authorized",
        "ranking_mode": "ranked_with_authorized_values",
        "archive_status": "ranked_with_authorized_values",
        "scenario_value_schedule_refs": ["pdc://layer2/s8/ua-msme/value-schedule/shadow-scenario"],
        "claim_refs": ["claim://ua-msme/welfare-frontier"],
        "audit_refs": ["cas://audit/welfare-frontier/ua-msme"],
        "authority_boundary": _authority_boundary(authoritative_for=["pareto_archive"]),
        "may_not_use_for": ["value_choice_authority", "scalar_welfare_authority"],
        "rule_version_ref": RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _value_choice_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "record_id": "layer2.s8.value-choice.ua-msme",
        "record_ref": "pdc://layer2/s8/ua-msme/value-choice-provenance",
        "case_id": CASE_ID,
        "selected_alternative_ref": "alternative://targeted_credit",
        "objective_provenance_ref": "pdc://layer2/s8/ua-msme/objective-provenance",
        "value_schedule_ref": "pdc://layer2/s8/ua-msme/value-schedule/authorized",
        "pareto_archive_ref": "pdc://layer2/s8/ua-msme/pareto-archive",
        "social_weight_provenance_refs": [
            "foundry://welfare/social-weight-provenance/public-budget-2026"
        ],
        "mandate_refs": ["pdc://layer2/s6/ua-msme/mandate-legitimacy"],
        "delegation_refs": ["pdc://layer2/s7/ua-msme/value-authorization-request"],
        "value_authorization_decision_refs": ["pdc://layer2/s7/ua-msme/value-authorization-record"],
        "conflict_rows": [],
        "affected_group_rows": [
            {
                "group_ref": "group://low-income-msmes",
                "weight_ref": "swr://policy.welfare/ua-msme#low-income",
                "disclosure_ref": "pdc://layer2/s8/ua-msme/affected-groups",
            }
        ],
        "dissent_refs": ["dissent://ua-msme/sme-panel"],
        "blocking_rights_refs": ["rights://ua-msme/legal-equality"],
        "alternative_schedule_sensitivity_rows": [
            {
                "scenario_schedule_ref": "pdc://layer2/s8/ua-msme/value-schedule/scenario",
                "selected_alternative_ref": "alternative://cash_transfer",
                "status": "shadow_scenario_only",
            }
        ],
        "disposition": "authorized",
        "integrity_status": "pass",
        "replay_refs": [
            "pdc://layer2/s8/ua-msme/value-schedule/authorized",
            "pdc://layer2/s8/ua-msme/pareto-archive",
        ],
        "authority_boundary": _authority_boundary(authoritative_for=["value_choice_provenance"]),
        "rule_version_ref": RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def test_value_choice_provenance_record_is_strict_replayable_and_mandate_bounded() -> None:
    schedule_model = _s8("AuthorizedValueSchedule")
    record_model = _s8("ValueChoiceProvenanceRecord")

    assert schedule_model.model_config.get("extra") == "forbid"
    assert record_model.model_config.get("extra") == "forbid"

    schedule = schedule_model.model_validate(_authorized_schedule_payload())
    record = record_model.model_validate(_value_choice_payload())

    assert schedule.s6_mandate_firewall_disposition == "pass"
    assert schedule.mandate_record_ref in record.mandate_refs
    assert schedule.schedule_ref == record.value_schedule_ref
    assert record.disposition == "authorized"
    assert "production_recommendation" in record.authority_boundary.may_not_use_for
    assert set(record.replay_refs) >= {schedule.schedule_ref, record.pareto_archive_ref}

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        record_model.model_validate(
            {
                **record.model_dump(mode="json"),
                "hidden_scalar_welfare_score": 0.91,
            }
        )


def test_authorized_value_schedule_requires_s6_mandate_firewall_pass() -> None:
    schedule = _s8("build_authorized_value_schedule")(**_authorized_schedule_payload())

    assert schedule.s6_mandate_firewall_disposition == "pass"
    assert schedule.source_class == "authorized_governance_schedule"

    for disposition in (None, "limit", "block", "candidate_unverified"):
        with pytest.raises(_s8("P22MandateLegitimacyError"), match=r"P22|mandate"):
            _s8("build_authorized_value_schedule")(
                **_authorized_schedule_payload(
                    s6_mandate_firewall_disposition=disposition,
                )
            )


def test_pareto_archive_cannot_rank_without_authorized_value_schedule() -> None:
    archive = _s8("build_pareto_archive")(
        **_pareto_archive_payload(
            value_schedule_ref=None,
            ranking_mode="unranked_frontier_only",
            archive_status="frontier_only",
        )
    )

    assert archive.ranking_mode == "unranked_frontier_only"
    assert "value_choice_authority" in archive.may_not_use_for

    with pytest.raises(_s8("P20NormativeChoiceError"), match=r"P20|authorized"):
        _s8("build_pareto_archive")(
            **_pareto_archive_payload(
                value_schedule_ref=None,
                ranking_mode="ranked_with_authorized_values",
                archive_status="ranking_attempted",
            )
        )


def test_shadowless_name_cannot_mint_authority_while_resolver_is_absent() -> None:
    schedule = _s8("build_authorized_value_schedule")(
        **_authorized_schedule_payload(
            schedule_ref="pdc://layer2/s8/value-schedules/shadowless-2026",
        )
    )

    assert schedule.disposition == "authorized"
    assert "shadow" in schedule.schedule_ref
    with pytest.raises(_s8("P20NormativeChoiceError")) as exc_info:
        _s8("build_pareto_archive")(
            **_pareto_archive_payload(value_schedule_ref=schedule.schedule_ref)
        )

    assert exc_info.value.code == "p20_value_schedule_resolver_absent"


def test_shadow_kind_is_refused_under_sh4dow_q3_name() -> None:
    schedule = _s8("build_shadow_scenario_value_schedule")(
        schedule_ref="pdc://layer2/s8/value-schedules/sh4dow-q3",
        case_id=CASE_ID,
        principal_refs=["principal://ua/ministry-of-economy"],
        social_weight_provenance_refs=["swr://scenario/low-income-heavy"],
        scenario_label="renamed shadow schedule",
        rule_version_ref=RULE_VERSION_REF,
    )

    with pytest.raises(_s8("P20NormativeChoiceError")) as exc_info:
        _s8("build_pareto_archive")(
            **_pareto_archive_payload(value_schedule_ref=schedule.schedule_ref)
        )

    assert exc_info.value.code == "p20_value_schedule_resolver_absent"


def test_unresolvable_value_schedule_ref_fails_closed_with_specific_code() -> None:
    with pytest.raises(_s8("P20NormativeChoiceError")) as exc_info:
        _s8("build_pareto_archive")(
            **_pareto_archive_payload(
                value_schedule_ref="pdc://layer2/s8/value-schedules/not-owned",
            )
        )

    assert exc_info.value.code == "p20_value_schedule_resolver_absent"


def test_shadow_kind_is_refused_under_a_name_invented_at_test_time() -> None:
    generated_ref = f"pdc://layer2/s8/value-schedules/{uuid4().hex}"
    schedule = _s8("build_shadow_scenario_value_schedule")(
        schedule_ref=generated_ref,
        case_id=CASE_ID,
        principal_refs=["principal://ua/ministry-of-economy"],
        social_weight_provenance_refs=["swr://scenario/low-income-heavy"],
        scenario_label="runtime-renamed shadow schedule",
        rule_version_ref=RULE_VERSION_REF,
    )

    assert "shadow" not in schedule.schedule_ref
    assert "scenario" not in schedule.schedule_ref
    with pytest.raises(_s8("P20NormativeChoiceError")) as exc_info:
        _s8("build_pareto_archive")(
            **_pareto_archive_payload(value_schedule_ref=schedule.schedule_ref)
        )

    assert exc_info.value.code == "p20_value_schedule_resolver_absent"


def test_pareto_archive_model_cannot_bypass_ranked_admission_guard() -> None:
    with pytest.raises(ValidationError, match="p20_value_schedule_resolver_absent"):
        _s8("ParetoArchive")(
            **_pareto_archive_payload(
                value_schedule_ref="pdc://layer2/s8/value-schedules/direct-model-bypass",
            )
        )


@pytest.mark.parametrize(
    "minting_seam",
    ["model_copy", "model_construct", "copy", "construct", "__replace__", "copy_replace"],
)
def test_pareto_archive_unvalidated_minting_seams_revalidate(
    minting_seam: str,
) -> None:
    archive_model = _s8("ParetoArchive")
    unranked_payload = _pareto_archive_payload(
        value_schedule_ref=None,
        ranking_mode="unranked_frontier_only",
        archive_status="frontier_only",
    )
    unranked = archive_model(**unranked_payload)
    ranked_update = {
        "ranking_mode": "ranked_with_authorized_values",
        "value_schedule_ref": "pdc://layer2/s8/value-schedules/unvalidated-bypass",
    }

    if minting_seam == "model_copy":
        with pytest.raises(ValidationError, match="p20_value_schedule_resolver_absent"):
            unranked.model_copy(update=ranked_update)
    elif minting_seam == "model_construct":
        with pytest.raises(ValidationError, match="p20_value_schedule_resolver_absent"):
            archive_model.model_construct(**{**unranked_payload, **ranked_update})
    elif minting_seam == "copy":
        with pytest.raises(ValidationError, match="p20_value_schedule_resolver_absent"):
            unranked.copy(update=ranked_update)
    elif minting_seam == "construct":
        with pytest.raises(ValidationError, match="p20_value_schedule_resolver_absent"):
            archive_model.construct(**{**unranked_payload, **ranked_update})
    elif minting_seam == "__replace__":
        with pytest.raises(ValidationError, match="p20_value_schedule_resolver_absent"):
            unranked.__replace__(**ranked_update)
    else:
        with pytest.raises(ValidationError, match="p20_value_schedule_resolver_absent"):
            replace(unranked, **ranked_update)

    if minting_seam == "model_copy":
        safe_copy = unranked.model_copy()
    elif minting_seam == "model_construct":
        safe_copy = archive_model.model_construct(**unranked_payload)
    elif minting_seam == "copy":
        safe_copy = unranked.copy()
    elif minting_seam == "construct":
        safe_copy = archive_model.construct(**unranked_payload)
    elif minting_seam == "__replace__":
        safe_copy = unranked.__replace__()
    else:
        safe_copy = replace(unranked)
    assert safe_copy.ranking_mode == "unranked_frontier_only"


def test_p20_rejects_llm_or_corpus_derived_social_weights() -> None:
    probe = _fixture("llm_social_weight_probe.json")
    for social_weight_provenance in probe["social_weight_provenance_candidates"]:
        with pytest.raises(_s8("P20NormativeChoiceError"), match=r"P20|value|authority"):
            _s8("coerce_social_weight_provenance_for_s8")(
                social_weight_provenance,
                authority_required=True,
                rule_version_ref=RULE_VERSION_REF,
            )


def test_p22_rejects_absent_limit_block_or_candidate_unverified_mandate_source() -> None:
    probe = _fixture("blocked_mandate_value_choice_probe.json")

    for disposition in (None, "limit", "block"):
        with pytest.raises(_s8("P22MandateLegitimacyError"), match=r"P22|mandate"):
            _s8("build_authorized_value_schedule")(
                **_authorized_schedule_payload(
                    mandate_record_ref=probe["mandate_record_ref"],
                    s6_mandate_firewall_disposition=disposition,
                )
            )

    with pytest.raises(_s8("P22MandateLegitimacyError"), match="candidate_unverified"):
        _s8("build_authorized_value_schedule")(
            **_authorized_schedule_payload(
                s6_mandate_firewall_disposition="pass",
                mandate_source_dispositions=["candidate_unverified"],
            )
        )


def test_shadow_scenario_value_schedule_is_visible_but_not_authority() -> None:
    scenario = _s8("build_shadow_scenario_value_schedule")(
        schedule_ref="pdc://layer2/s8/ua-msme/value-schedule/shadow-scenario",
        case_id=CASE_ID,
        principal_refs=["principal://ua/ministry-of-economy"],
        social_weight_provenance_refs=["swr://scenario/low-income-heavy"],
        scenario_label="low-income-heavy sensitivity",
        rule_version_ref=RULE_VERSION_REF,
    )

    assert scenario.disposition == "shadow_scenario_only"
    assert "ranked_recommendation_authority" in scenario.may_not_use_for

    with pytest.raises(_s8("P20NormativeChoiceError")) as exc_info:
        _s8("build_pareto_archive")(
            **_pareto_archive_payload(
                value_schedule_ref=scenario.schedule_ref,
                ranking_mode="ranked_with_authorized_values",
            )
        )

    assert exc_info.value.code == "p20_value_schedule_resolver_absent"


def test_multi_principal_conflict_is_contested_not_silent_average() -> None:
    conflict_rows = [
        {
            "principal_ref": "principal://city/tenant-board",
            "schedule_ref": "pdc://layer2/s8/rent-cap/tenant-schedule",
            "incompatible_with": ["principal://city/landlord-board"],
            "conflict_reason": "tenant stability and owner exit risk cannot be averaged",
        },
        {
            "principal_ref": "principal://city/landlord-board",
            "schedule_ref": "pdc://layer2/s8/rent-cap/owner-schedule",
            "incompatible_with": ["principal://city/tenant-board"],
            "conflict_reason": "owner solvency priority conflicts with tenant schedule",
        },
    ]
    record = _s8("build_value_choice_provenance_record")(
        **_value_choice_payload(
            conflict_rows=conflict_rows,
            disposition="authorized",
        )
    )

    assert record.disposition == "contested_multi_principal"
    assert record.conflict_rows == conflict_rows
    assert "silent_average" not in json.dumps(record.model_dump(mode="json"))

    with pytest.raises(_s8("P20NormativeChoiceError"), match=r"affected|dissent|blocking"):
        _s8("build_value_choice_provenance_record")(
            **_value_choice_payload(
                conflict_rows=conflict_rows,
                affected_group_rows=[],
                dissent_refs=[],
                blocking_rights_refs=[],
                alternative_schedule_sensitivity_rows=[],
            )
        )


def test_s7_human_decision_refs_cannot_substitute_for_s8_value_authority() -> None:
    probe = _fixture("s7_human_decision_substitution_probe.json")

    with pytest.raises(_s8("P20NormativeChoiceError"), match=r"S7|value"):
        _s8("build_value_choice_provenance_record")(
            **_value_choice_payload(
                value_schedule_ref=None,
                delegation_refs=probe["delegation_refs"],
                value_authorization_decision_refs=probe["value_authorization_decision_refs"],
                disposition="authorized",
            )
        )


def test_s7_value_authorization_route_requires_governance_decision_class_and_five_rights() -> None:
    registry = runtime_quality.build_governance_decision_class_registry(
        case_id=CASE_ID,
        rule_version_ref="policyos.layer2.s7.delegation.v1",
    )
    matrix = runtime_quality.build_decision_rights_matrix(
        case_id=CASE_ID,
        governance_decision_classes=registry,
        rule_version_ref="policyos.layer2.s7.delegation.v1",
    )
    row = matrix.row_for_decision_class("value_authorization")

    assert row.required_role == "principal"
    assert row.default_interaction_mode == "request_driven"
    assert row.ai_first_allowed is False
    assert row.delegated_autonomous_allowed is False
    assert set(row.five_rights_dimensions) == {
        "right_decision",
        "right_person",
        "right_information",
        "right_format_channel",
        "right_time",
    }

    with pytest.raises(_s8("P26ResponsibilityIntegrityError"), match="value_authorization"):
        _s8("build_authorized_value_schedule")(
            **_authorized_schedule_payload(
                s7_decision_rights_matrix_ref=matrix.matrix_ref,
                s7_value_authorization_request_ref=(
                    "pdc://layer2/s7/ua-msme/human-decision-request/a_spec_gap"
                ),
                s7_value_authorization_record_ref=(
                    "pdc://layer2/s7/ua-msme/human-decision-record/a_spec_gap"
                ),
                s7_value_authorization_decision_class_id="a_spec_gap",
                s7_five_rights_passed=True,
            )
        )


def test_value_tradeoff_disclosure_has_audience_bounded_public_projection() -> None:
    public = _s8("project_value_tradeoff_disclosure")(
        value_choice_record=_value_choice_payload(disposition="advisory_only"),
        audience="PUBLIC",
        rule_version_ref=RULE_VERSION_REF,
    )
    machine = _s8("project_value_tradeoff_disclosure")(
        value_choice_record=_value_choice_payload(disposition="advisory_only"),
        audience="MACHINE",
        rule_version_ref=RULE_VERSION_REF,
    )

    public_payload = public.model_dump(mode="json")
    machine_payload = machine.model_dump(mode="json")
    assert public_payload["audience"] == "PUBLIC"
    assert public_payload["decision_tradeoff_summary"]
    assert "raw_social_weights" not in public_payload
    assert "value_schedule_details" not in public_payload
    assert machine_payload["audience"] == "MACHINE"
    assert machine_payload["value_schedule_ref"] == _value_choice_payload()["value_schedule_ref"]
    assert machine_payload["affected_group_rows"]
    assert machine_payload["authority_boundary"]["may_not_use_for"]


def test_value_choice_records_are_exported_from_runtime_quality() -> None:
    required_exports = {
        "LAYER2_S8_VALUE_CHOICE_SCHEMA_VERSION",
        "LAYER2_S8_VALUE_CHOICE_RULE_VERSION",
        "S8_VALUE_CHOICE_CELL_REF",
        "S8_VALUE_CHOICE_FLOOR_ID",
        "AuthorizedValueSchedule",
        "ObjectiveFunctionProvenanceRecord",
        "ParetoArchive",
        "ValueChoiceProvenanceRecord",
        "ValueTradeoffDisclosureRecord",
        "ValueChoiceIntegrityReport",
        "P20NormativeChoiceError",
        "P22MandateLegitimacyError",
        "build_authorized_value_schedule",
        "build_shadow_scenario_value_schedule",
        "build_objective_function_provenance",
        "build_pareto_archive",
        "build_value_choice_provenance_record",
        "project_value_tradeoff_disclosure",
        "s8_value_provenance_integrity",
    }

    missing = sorted(name for name in required_exports if not hasattr(runtime_quality, name))
    assert missing == []


def test_ranked_bundle_persistence_requires_owner_verification(tmp_path: Path) -> None:
    """Deleting persistence admission while keeping DTO markers must reopen this escape."""
    from polisyos.core import artifacts
    from polisyos.runtime.quality.design_axes import value_choice_provenance as s8

    store = artifacts.FileSystemCAS(tmp_path)
    with pytest.raises(s8.P20NormativeChoiceError):
        s8.persist_value_choice_provenance_bundle(
            {"pareto_archive": _pareto_archive_payload()}, store=store
        )


def _normative_harness(tmp_path: Path, *, fault: str = "") -> dict[str, Any]:
    from polisyos.core import artifacts
    from polisyos.runtime.quality.design_axes import value_choice_provenance as s8

    store = artifacts.FileSystemCAS(tmp_path)
    claimant_key, authorizer_key = artifacts.KeyPair.generate(), artifacts.KeyPair.generate()
    claimant = "claimant://research-owner"
    authorizer = "principal://ua/ministry-of-economy"
    if fault == "self_grading":
        authorizer_key, authorizer = claimant_key, claimant
    scope = "value-scope://credit-and-budget"
    mandate = "pdc://layer2/s6/ua-msme/mandate-legitimacy"

    def put(payload: object, kind: str, schema: str, key: Any, identity: str) -> str:
        ref = store.put_json(
            payload,
            artifacts.PutOptions(
                kind=kind,
                media_type="application/json",
                schema=artifacts.SchemaInfo(name=kind, version=schema),
            ),
        )
        store.sign_artifact(
            ref.artifact_id, artifacts.Ed25519Signer(key.private_key), signer_identity=identity
        )
        return str(ref.artifact_id)

    schedule = s8.build_authorized_value_schedule(
        **_authorized_schedule_payload(
            principal_refs=[authorizer],
            schedule_ref=f"pdc://value-schedule/{uuid4().hex}",
        )
    )
    if fault == "shadow":
        schedule = s8.build_shadow_scenario_value_schedule(
            schedule_ref=f"pdc://value-schedule/{uuid4().hex}",
            case_id=CASE_ID,
            principal_refs=[authorizer],
            social_weight_provenance_refs=["swr://scenario"],
            scenario_label="sensitivity",
            rule_version_ref=RULE_VERSION_REF,
        )
    schedule_ref = put(
        schedule.model_dump(mode="json"),
        s8.NORMATIVE_SCHEDULE_KIND,
        s8.LAYER2_S8_VALUE_CHOICE_SCHEMA_VERSION,
        claimant_key,
        claimant,
    )
    frontier = s8.build_pareto_archive(
        **_pareto_archive_payload(
            ranking_mode="unranked_frontier_only",
            archive_status="frontier_available",
            value_schedule_ref=None,
            rejected_nondominated_alternative_ids=[],
            **(
                {
                    "authority_boundary": _authority_boundary(
                        authoritative_for=["publication_authority", "outcome_prediction_authority"]
                    ),
                }
                if fault == "broader_frontier"
                else {}
            ),
        )
    )
    frontier_ref = put(
        frontier.model_dump(mode="json"),
        s8.NORMATIVE_FRONTIER_KIND,
        s8.LAYER2_S8_VALUE_CHOICE_SCHEMA_VERSION,
        claimant_key,
        claimant,
    )
    authorization = s8.NormativeAuthorizationRecord(
        authorizer_identity=authorizer,
        authority_purpose="legal_competence"
        if fault == "purpose"
        else "value_schedule_for_ranking",
        case_id="other-case" if fault == "case" else CASE_ID,
        scope_ref="other-scope" if fault == "scope" else scope,
        mandate_ref=mandate,
        decision_class_id="value_authorization",
        decision_role="legal_reviewer" if fault == "role" else "principal",
        source_schedule_ref="sha256:" + "f" * 64 if fault == "missing_schedule" else schedule_ref,
        frontier_ref=frontier_ref,
        selected_alternative_id="targeted_credit",
        effective_at=NOW - timedelta(days=1),
        expires_at=NOW + timedelta(days=-0.5 if fault == "stale" else 1),
        rule_version_ref=RULE_VERSION_REF,
    )
    authorization_ref = put(
        authorization.model_dump(mode="json"),
        s8.NORMATIVE_AUTHORIZATION_KIND,
        s8.NORMATIVE_AUTHORIZATION_SCHEMA_VERSION,
        authorizer_key,
        authorizer,
    )
    authorizer_trust = s8.NormativeAuthorityPrincipal(
        identity=authorizer,
        public_key_pem=authorizer_key.public_pem().decode(),
        decision_roles=("principal",),
        authority_purposes=("value_schedule_for_ranking",),
        case_ids=(CASE_ID,),
        scope_refs=(scope,),
        mandate_refs=(mandate,),
    )
    principals = [authorizer_trust]
    if fault != "self_grading":
        principals.append(
            s8.NormativeAuthorityPrincipal(
                identity=claimant, public_key_pem=claimant_key.public_pem().decode()
            )
        )
    trust = s8.NormativeAuthorityTrust(
        epoch="test-deployment-epoch", principals=() if fault == "empty" else tuple(principals)
    )
    owner = s8.NormativeValueScheduleOwner(store=store, trust=trust)
    if fault == "signature":
        signature = store.get_signature(authorization_ref)
        assert signature is not None
        signature.signature_hex = ("00" if signature.signature_hex[:2] != "00" else "01") + (
            signature.signature_hex[2:]
        )
        store.put_signature(authorization_ref, signature)
    return {
        "owner": owner,
        "store": store,
        "frontier": frontier,
        "kwargs": {
            "frontier_ref": frontier_ref,
            "authorization_ref": None if fault == "missing" else authorization_ref,
            "case_id": CASE_ID,
            "scope_ref": scope,
            "evaluated_at": NOW,
        },
    }


def test_separate_signed_authorization_produces_persists_resolves_and_projects(
    tmp_path: Path,
) -> None:
    harness = _normative_harness(tmp_path)
    owner = harness["owner"]
    result, bundle_ref = owner.recommend(**harness["kwargs"])

    assert result.ranked_recommendations == ("targeted_credit",), (
        result.decision_request.reason_codes if result.decision_request else None
    )
    assert result.authorization_status == "authorized"
    assert result.decision_request is None
    assert result.archive.normative_admission_ref
    assert (
        owner.resolve_archive(result.archive.normative_admission_ref, evaluated_at=NOW)
        == result.archive
    )
    assert owner.project(bundle_ref, evaluated_at=NOW) == result.model_dump(mode="json")


@pytest.mark.parametrize(
    ("fault", "reason"),
    [
        ("missing", "p20_normative_authorization_missing"),
        ("missing_schedule", "p20_value_schedule_ref_unresolvable"),
        ("empty", "p20_normative_authority_slot_empty"),
        ("self_grading", "p20_normative_self_grading"),
        ("role", "p20_normative_authority_scope_mismatch"),
        ("purpose", "p20_normative_authority_scope_mismatch"),
        ("scope", "p20_normative_authority_scope_mismatch"),
        ("case", "p20_normative_authority_scope_mismatch"),
        ("stale", "p20_normative_authorization_stale"),
        ("shadow", "p20_resolved_schedule_not_authorized"),
        ("signature", "p20_normative_signature_unverified"),
    ],
)
def test_invalid_authority_keeps_frontier_and_persists_typed_request(
    tmp_path: Path, fault: str, reason: str
) -> None:
    harness = _normative_harness(tmp_path, fault=fault)
    result, bundle_ref = harness["owner"].recommend(**harness["kwargs"])

    assert result.ranked_recommendations == ()
    assert result.authorization_status == "blocked"
    assert (
        result.archive.nondominated_alternative_ids
        == harness["frontier"].nondominated_alternative_ids
    )
    assert result.archive.frontier_refs == harness["frontier"].frontier_refs
    assert result.archive.claim_refs == harness["frontier"].claim_refs
    assert result.archive.authority_boundary.authoritative_for == ["candidate_value_disclosure"]
    assert result.decision_request.reason_codes == (reason,)
    assert harness["owner"].project(bundle_ref, evaluated_at=NOW)["decision_request"]


def test_ranked_persistence_and_projection_recheck_ttl_and_exact_selection(tmp_path: Path) -> None:
    from polisyos.runtime.quality.design_axes import value_choice_provenance as s8

    harness = _normative_harness(tmp_path)
    owner = harness["owner"]
    result, bundle_ref = owner.recommend(**harness["kwargs"])
    assert result.ranked_recommendations
    with pytest.raises(s8.P20NormativeChoiceError, match="stale"):
        owner.project(bundle_ref, evaluated_at=NOW + timedelta(days=2))
    payload = result.model_dump(mode="json")
    payload["archive"]["selected_alternative_ref"] = "cash_transfer"
    payload["ranked_recommendations"] = ["cash_transfer"]
    with pytest.raises(s8.P20NormativeChoiceError, match="content_mismatch"):
        s8.persist_value_choice_provenance_bundle(
            payload, store=harness["store"], owner=owner, evaluated_at=NOW
        )


def test_authorized_projection_cannot_grade_its_own_mapping() -> None:
    from polisyos.runtime.quality.design_axes import value_choice_provenance as s8

    with pytest.raises(s8.P20NormativeChoiceError, match="resolver_absent"):
        s8.project_value_tradeoff_disclosure(
            value_choice_record=_value_choice_payload(),
            audience="PUBLIC",
            rule_version_ref=RULE_VERSION_REF,
        )


@pytest.mark.parametrize("fault", ["", "role"])
def test_persisted_authorization_status_is_derived_from_the_verified_result(
    tmp_path: Path, fault: str
) -> None:
    from polisyos.runtime.quality.design_axes import value_choice_provenance as s8

    harness = _normative_harness(tmp_path, fault=fault)
    result, _ = harness["owner"].recommend(**harness["kwargs"])
    payload = result.model_dump(mode="json")
    payload["authorization_status"] = (
        "blocked" if result.authorization_status == "authorized" else "authorized"
    )
    with pytest.raises(s8.P20NormativeChoiceError, match="mismatch"):
        s8.persist_value_choice_provenance_bundle(
            payload,
            store=harness["store"],
            owner=harness["owner"],
            evaluated_at=NOW,
        )


def test_admission_cannot_replace_verified_claimant_with_an_asserted_identity(
    tmp_path: Path,
) -> None:
    from polisyos.core import artifacts, canon
    from polisyos.runtime.quality.design_axes import value_choice_provenance as s8

    harness = _normative_harness(tmp_path)
    owner, store = harness["owner"], harness["store"]
    admission_ref = owner.produce(**harness["kwargs"])
    payload = canon.from_canonical_bytes(store.get_bytes(admission_ref))
    payload["claimant_identity"] = "claimant://someone-else"
    manifest = store.get_manifest(admission_ref)
    forged = store.put_json(
        payload,
        artifacts.PutOptions(
            kind=manifest.kind,
            media_type="application/json",
            schema=manifest.artifact_schema,
        ),
    )
    with pytest.raises(s8.P20NormativeChoiceError, match="admission_content_mismatch"):
        owner.resolve_archive(str(forged.artifact_id), evaluated_at=NOW)


def test_nested_sibling_ranked_payload_must_use_the_same_owner(tmp_path: Path) -> None:
    from polisyos.runtime.quality.design_axes import value_choice_provenance as s8

    harness = _normative_harness(tmp_path)
    with pytest.raises(s8.P20NormativeChoiceError, match="unregistered_s8_emission"):
        s8.persist_value_choice_provenance_bundle(
            {"other_consumer": [{"payload": _pareto_archive_payload()}]},
            store=harness["store"],
        )


def test_trust_cannot_turn_one_key_into_two_independent_parties(tmp_path: Path) -> None:
    from polisyos.core import artifacts
    from polisyos.runtime.quality.design_axes import value_choice_provenance as s8

    key = artifacts.KeyPair.generate()
    trust = s8.NormativeAuthorityTrust(
        principals=tuple(
            s8.NormativeAuthorityPrincipal(
                identity=identity, public_key_pem=key.public_pem().decode()
            )
            for identity in ("claimant://original", "principal://alias")
        )
    )
    with pytest.raises(ValueError, match="alias a signing key"):
        s8.NormativeValueScheduleOwner(store=artifacts.FileSystemCAS(tmp_path), trust=trust)


def test_schedule_bytes_remain_bound_after_a_valid_signature(tmp_path: Path) -> None:
    from polisyos.core import artifacts, canon
    from polisyos.runtime.quality.design_axes import value_choice_provenance as s8

    harness = _normative_harness(tmp_path)
    store = harness["store"]
    authorization = canon.from_canonical_bytes(
        store.get_bytes(harness["kwargs"]["authorization_ref"])
    )
    ref = artifacts.ArtifactID.model_validate(authorization["source_schedule_ref"])
    blob_path, _ = store.get_paths(ref)
    blob_path.write_bytes(blob_path.read_bytes().replace(b'"approved"', b'"rejected"'))
    result, _ = harness["owner"].recommend(**harness["kwargs"])
    assert result.ranked_recommendations == ()
    assert result.decision_request.reason_codes == (s8.P20_VALUE_SCHEDULE_REF_UNRESOLVABLE_CODE,)


def test_selection_permission_sets_a_whole_authority_ceiling(tmp_path: Path) -> None:
    harness = _normative_harness(tmp_path, fault="broader_frontier")
    result, bundle_ref = harness["owner"].recommend(**harness["kwargs"])
    projected = harness["owner"].project(bundle_ref, evaluated_at=NOW)
    assert result.ranked_recommendations == ("targeted_credit",)
    assert projected["archive"]["authority_boundary"]["authoritative_for"] == [
        "value_schedule_for_ranking"
    ]
    assert projected["archive"]["nondominated_alternative_ids"] == (
        harness["frontier"].nondominated_alternative_ids
    )
    assert "publication_authority" in projected["archive"]["may_not_use_for"]
    assert "outcome_prediction_authority" in projected["archive"]["may_not_use_for"]


@pytest.mark.parametrize("audience", ["REVIEWER", "MACHINE"])
def test_permission_projection_never_grades_candidate_auxiliary_premises(
    tmp_path: Path, audience: str
) -> None:
    from polisyos.runtime.quality.design_axes import value_choice_provenance as s8

    harness = _normative_harness(tmp_path)
    result, _ = harness["owner"].recommend(**harness["kwargs"])
    archive = result.archive
    candidate = _value_choice_payload(
        normative_admission_ref=archive.normative_admission_ref,
        selected_alternative_ref=archive.selected_alternative_ref,
        value_schedule_ref=archive.value_schedule_ref,
        pareto_archive_ref=archive.archive_ref,
        integrity_status="pass",
        mandate_refs=["mandate://unverified"],
        delegation_refs=["delegation://unverified"],
        replay_refs=["replay://unverified"],
        authority_boundary=_authority_boundary(authoritative_for=["publication_authority"]),
    )
    projected = s8.project_value_tradeoff_disclosure(
        value_choice_record=candidate,
        audience=audience,
        rule_version_ref=RULE_VERSION_REF,
        owner=harness["owner"],
        evaluated_at=NOW,
    )
    status = projected.reviewer_status_fields or projected.machine_integrity_fields
    assert status["normative_authorization_status"] == "verified"
    assert status["candidate_material_status"] == "unverified_disclosure"
    assert all(
        status[field] == "not_established"
        for field in status
        if field.endswith("status")
        and field not in {"normative_authorization_status", "candidate_material_status"}
    )
    persisted = s8.persist_value_choice_provenance_bundle(
        projected.model_dump(mode="json"),
        store=harness["store"],
        owner=harness["owner"],
        evaluated_at=NOW,
    )
    assert harness["owner"].project(str(persisted["artifact_ref"]), evaluated_at=NOW) == (
        projected.model_dump(mode="json")
    )


@pytest.mark.parametrize("audience", ["REVIEWER", "MACHINE"])
def test_registered_advisory_disclosure_rejects_all_modified_assessment_fields(
    tmp_path: Path, audience: str
) -> None:
    from copy import deepcopy

    from polisyos.core import artifacts
    from polisyos.runtime.quality.design_axes import value_choice_provenance as s8

    store = artifacts.FileSystemCAS(tmp_path)
    payload = s8.project_value_tradeoff_disclosure(
        value_choice_record=_value_choice_payload(disposition="advisory_only"),
        audience=audience,
        rule_version_ref=RULE_VERSION_REF,
    ).model_dump(mode="json")
    assert s8.persist_value_choice_provenance_bundle(payload, store=store)["artifact_ref"]
    field = "reviewer_status_fields" if audience == "REVIEWER" else "machine_integrity_fields"
    # Complete assessment field set comes from the emitted contract, not a list of known probes.
    for name, original in payload[field].items():
        mutated = deepcopy(payload)
        mutated[field][name] = (
            {"authoritative_for": ["publication_authority"]}
            if isinstance(original, dict)
            else "pass"
        )
        with pytest.raises(s8.P20NormativeChoiceError, match="disclosure_authority_mismatch"):
            s8.persist_value_choice_provenance_bundle(mutated, store=store)
