"""Policy Design Case projection semantics for user-facing surfaces."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from polisyos.core import contracts
from polisyos.runtime.quality.assurance_case import validate_policy_design_case_profile
from polisyos.runtime.quality.candidate_firewall import (
    CandidateFirewallError,
    assert_no_candidate_authority_laundering,
)
from polisyos.runtime.quality.contestability import (
    PolicyDesignContestabilityError,
    verified_recourse_pointer_for_publication,
)

POLICY_DESIGN_CASE_PROJECTION_SCHEMA_VERSION = (
    contracts.POLICY_DESIGN_CASE_PROJECTION_SCHEMA_VERSION
)
PROJECTION_STATES = (
    "draft",
    "projection_only",
    "redacted",
    "stale",
    "contested",
    "blocked",
    "publishable",
)
_PRIMARY_STATE_ORDER = (
    "blocked",
    "contested",
    "stale",
    "draft",
    "redacted",
    "publishable",
    "projection_only",
)
_SOURCE_AUTHORITY_ROLES_THAT_MINT_AUTHORITY = frozenset(
    {
        "approval_input",
        "producer_authority",
        "readiness_input",
        "runtime_blocker",
        "scorecard_input",
    }
)
_ALLOWED_FINAL_ARTIFACT_SOURCE_ROLES = frozenset(
    {
        "",
        "diagnostic_only",
        "final_decision_artifact",
        "not_authoritative",
        "packaging_only",
        "projection",
        "projection_only",
    }
)
_MAY_NOT_BE_USED_FOR = (
    "approval_authority",
    "claim_authority",
    "provider_credential_validation",
    "runtime_closeout_authority",
    "scorecard_authority",
    "tenant_identity_resolution",
)
_MAY_BE_USED_FOR = (
    "api_display",
    "dashboard_display",
    "external_explanation",
    "operator_triage",
    "public_audit",
)
_LEGACY_PROJECTION_POLICY = "reads_policy_design_case_only"
_RUNTIME_GRAPH_PROJECTION_POLICY = "reads_runtime_policy_design_case_graph"
_S9_CONSUMER_CONTRACT_REF = (
    "policyos.runtime.policy_design_case.projection_contract_verification.v1"
)
_S10_CONSUMER_CONTRACT_REF = (
    "policyos.runtime.policy_design_case.s10_forecast_projection_verification.v1"
)
_S11_CONSUMER_CONTRACT_REF = (
    "policyos.runtime.policy_design_case.s11_predictive_projection_verification.v1"
)
_S12_CONSUMER_CONTRACT_REF = (
    "policyos.runtime.policy_design_case.s12_resource_projection_verification.v1"
)
_S9_REQUIRED_MAY_NOT_USE_FOR = frozenset(
    {
        "claim_authority",
        "scorecard_authority",
        "runtime_closeout_authority",
    }
)
_S9_AUTHORITY_BOUNDARY_REQUIRED_MAY_NOT_USE_FOR = frozenset(
    {
        "claim_authority",
        "scorecard_authority",
        "runtime_closeout_authority",
        "production_recommendation",
    }
)
_S10_REQUIRED_MAY_NOT_USE_FOR = frozenset(
    {
        "production_recommendation",
        "production_claim_authority",
        "publication_authority",
        "claim_authority",
        "closeout_authority",
        "s11_calibration",
    }
)
_S10_FORBIDDEN_AUTHORITY_USES = frozenset(
    {
        "approval_authority",
        "claim_authority",
        "closeout_authority",
        "publication_authority",
        "production_claim_authority",
        "production_recommendation",
        "recommendation_authority",
        "runtime_closeout_authority",
        "scorecard_authority",
    }
)
_S11_REQUIRED_MAY_NOT_USE_FOR = frozenset(
    {
        "production_recommendation",
        "production_claim_authority",
        "publication_authority",
        "claim_authority",
        "runtime_closeout_authority",
    }
)
_S11_FORBIDDEN_AUTHORITY_USES = frozenset(
    {
        "approval_authority",
        "claim_authority",
        "closeout_authority",
        "publication_authority",
        "production_claim_authority",
        "production_recommendation",
        "recommendation_authority",
        "runtime_closeout_authority",
        "scorecard_authority",
    }
)
_S12_REQUIRED_MAY_NOT_USE_FOR = frozenset(
    {
        "production_authority",
        "production_recommendation",
        "rollout_authority",
        "publication_authority",
        "claim_authority",
        "closeout_authority",
        "approval_authority",
        "scorecard_authority",
        "preference_learning_authority",
        "mdp_bandit_optimizer_authority",
        "budget_interchangeability",
        "mission_or_value_self_authorization",
        "floor_relaxation",
        "s13_envelope_shrink",
        "s13_accountability_closure",
        "s14_universality",
    }
)
_S12_FORBIDDEN_AUTHORITY_USES = frozenset(
    {
        "approval_authority",
        "claim_authority",
        "closeout_authority",
        "publication_authority",
        "production_authority",
        "production_claim_authority",
        "production_recommendation",
        "recommendation_authority",
        "runtime_closeout_authority",
        "scorecard_authority",
        "s13_accountability_closure",
        "s13_envelope_shrink",
        "s14_universality",
    }
)
_S12_SCALAR_ALLOCATION_KEYS = frozenset(
    {
        "allocation_score",
        "hidden_scalar_score",
        "numeric_voi_score",
        "selected_policy_score",
        "voi_score",
    }
)
_ALLOWED_PROJECTION_POLICIES = frozenset(
    {_LEGACY_PROJECTION_POLICY, _RUNTIME_GRAPH_PROJECTION_POLICY}
)
_RUNTIME_GRAPH_PROJECTION_CONSUMED_FIELDS = (
    "policy_design_case_profile",
    "claim_graph",
    "warrant_structures",
    "obligation_refs",
    "producer_binding_refs",
    "baseline_refs",
    "alternative_refs",
    "conflict_refs",
    "effective_independence_refs",
    "closeout_refs",
    "closeout_verdict",
    "contested_records",
    "deficit_register",
    "claim_registry_ref",
    "semantic_binding_refs",
    "graph_ref",
    "runtime_event_ref",
    "schema_version",
    "projection_source_policy",
)


class PolicyDesignCaseProjectionError(ValueError):
    """Fail-closed projection-boundary violation."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


def build_policy_design_case_projection_semantics(
    *,
    policy_design_case: Mapping[str, Any],
    surface: str,
    source_payload: Mapping[str, Any] | None = None,
    source_ref: str | None = None,
    generated_at: datetime | None = None,
    audience: contracts.PolicyDesignCaseAudience | str | None = None,
    closeout_verdict: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build projection labels that read, but cannot create, case authority."""

    validated_case = validate_policy_design_case_profile(policy_design_case)
    source = dict(source_payload or {})
    try:
        assert_no_candidate_authority_laundering(
            source,
            hypothesis_ledger=source.get("hypothesis_ledger")
            if isinstance(source.get("hypothesis_ledger"), Mapping)
            else None,
            authority_slots=("projection_authority",),
            surface=surface,
        )
    except CandidateFirewallError as exc:
        raise PolicyDesignCaseProjectionError(exc.code, str(exc)) from exc
    _assert_source_is_projection_safe(source)
    audience_value = _audience(audience, surface=surface)
    recourse_pointer, recourse_gap = _recourse_projection(
        policy_design_case=validated_case,
        source_payload=source,
    )
    raw_closeout = (
        closeout_verdict
        or _mapping(source.get("closeout_verdict"))
        or _mapping(validated_case.get("closeout_verdict"))
    )
    closeout_truth = _closeout_truth(
        raw_closeout,
        contested=_is_contested(validated_case) or _is_contested(source),
        recourse_gap=recourse_gap,
    )
    projection_gaps = _projection_gaps(
        closeout_truth=closeout_truth,
        closeout_verdict=raw_closeout,
        source_payload=source,
        recourse_gap=recourse_gap,
        audience=audience_value,
    )
    omission_manifest = _omission_manifest(
        closeout_verdict=raw_closeout,
        source_payload=source,
        audience=audience_value,
    )
    participation_surface = _participation_surface(
        source_payload=source,
        policy_design_case=validated_case,
        audience=audience_value,
    )
    projection_gaps = _dedupe_gaps(
        [*projection_gaps, *participation_surface["projection_gaps"]]
    )
    contested_records = _contested_records(
        source_payload=source,
        policy_design_case=validated_case,
        audience=audience_value,
        recourse_pointer=recourse_pointer,
    )
    if participation_surface["contested_records"]:
        contested_records = [
            *contested_records,
            *participation_surface["contested_records"],
        ]
    deficit_register = [
        *_deficit_register(source, validated_case),
        *participation_surface["deficit_register"],
    ]
    invariant_summary = _invariant_summary(source, validated_case)
    states = _projection_states(
        validated_case,
        source_payload=source,
        surface=surface,
        forced_blocked=bool(recourse_gap or closeout_truth.get("blocker_codes")),
    )
    primary_state = _primary_state(states)
    authority_chain = _mapping(validated_case.get("authority_chain"))
    resolved_source_ref = (
        _text(source_ref)
        or _text(source.get("source_ref"))
        or _text(authority_chain.get("cas_ref"))
    )
    projection = {
        "schema_version": POLICY_DESIGN_CASE_PROJECTION_SCHEMA_VERSION,
        "generated_at": _utc(generated_at).isoformat(),
        "surface": _text(surface) or "unknown_projection_surface",
        "audience": audience_value.value,
        "primary_state": primary_state,
        "states": list(states),
        "labels": [
            {
                "state": state,
                "label": _state_label(state),
                "authority_role": "projection_only",
                "source_authority": "policy_design_case",
            }
            for state in states
        ],
        "authority_role": "projection_only",
        "projection_policy": _LEGACY_PROJECTION_POLICY,
        "authoritative_for": [],
        "closeout_truth": closeout_truth,
        "projection_gaps": projection_gaps,
        "omission_manifest": omission_manifest,
        "contested_records": contested_records,
        "recourse_pointer": recourse_pointer,
        "deficit_register": deficit_register,
        "participation_requirements": participation_surface["rows"],
        "invariant_summary": invariant_summary,
        "evidence_class": "redacted_derived" if "redacted" in states else "diagnostic_supporting",
        "provenance_kind": "runtime_projection",
        "redacted": "redacted" in states,
        "redaction_summary": _redaction_summary(source, audience_value),
        "policy_design_case_id": _text(validated_case.get("case_id")),
        "run_id": _text(validated_case.get("run_id")),
        "source_ref": resolved_source_ref,
        "source_ref_fingerprint": _fingerprint(resolved_source_ref)
        if resolved_source_ref
        else None,
        "audit_refs": _audit_refs(source, validated_case, authority_chain),
        "source_authority_refs": _source_authority_refs(authority_chain),
        "source_state": {
            "policy_design_case_status": _text(validated_case.get("status")),
            "artifact_publishability": _text(source.get("publishability")),
            "public_export_status": _nested_text(
                source,
                ("decision_context", "public_export_status"),
            ),
        },
        "may_be_used_for": list(_MAY_BE_USED_FOR),
        "may_not_be_used_for": list(_MAY_NOT_BE_USED_FOR),
        "capability_reality_state": "implemented",
        "contract_verification_status": _text(source.get("contract_verification_status"))
        or "not_verified",
        "contract_verification_refs": _text_list(source.get("contract_verification_refs")),
    }
    return assert_policy_design_projection_not_authority(projection)


def build_policy_design_case_projection_from_runtime_graph(
    *,
    runtime_pdc_graph: Mapping[str, Any] | object,
    surface: str,
    generated_at: datetime | None = None,
    audience: contracts.PolicyDesignCaseAudience | str | None = None,
) -> dict[str, Any]:
    """Build a projection whose source payload is derived from the W8.A graph."""

    from polisyos.pdc import (
        RuntimePolicyDesignCase,
        runtime_policy_design_case_projection_source,
    )

    graph = RuntimePolicyDesignCase.model_validate(runtime_pdc_graph)
    if graph.policy_design_case_profile is None:
        raise PolicyDesignCaseProjectionError(
            "runtime_pdc_graph_policy_design_case_missing",
            "Projection-from-graph requires the graph's validated Policy Design Case profile.",
        )
    source_payload = runtime_policy_design_case_projection_source(graph)
    projection = build_policy_design_case_projection_semantics(
        policy_design_case=graph.policy_design_case_profile,
        surface=surface,
        source_payload=source_payload,
        source_ref=graph.graph_ref,
        generated_at=generated_at,
        audience=audience,
        closeout_verdict=graph.closeout_verdict or {},
    )
    projection["source_state"] = {
        **dict(projection.get("source_state") or {}),
        "runtime_pdc_graph_ref": graph.graph_ref,
        "runtime_pdc_graph_schema_version": graph.schema_version,
        "runtime_pdc_graph_projection_policy": graph.projection_source_policy,
        "runtime_pdc_graph_consumed_fields": list(
            _RUNTIME_GRAPH_PROJECTION_CONSUMED_FIELDS
        ),
    }
    projection["source_authority_refs"] = {
        **dict(projection.get("source_authority_refs") or {}),
        "runtime_pdc_graph_ref": graph.graph_ref,
        "runtime_pdc_graph_event_ref": graph.runtime_event_ref,
    }
    projection["projection_policy"] = _RUNTIME_GRAPH_PROJECTION_POLICY
    return assert_policy_design_projection_not_authority(projection)


def assert_policy_design_projection_not_authority(
    projection: Mapping[str, Any],
) -> dict[str, Any]:
    """Raise if a Policy Design Case projection is shaped like authority."""

    authority_role = _text(projection.get("authority_role")).casefold()
    if authority_role != "projection_only":
        raise PolicyDesignCaseProjectionError(
            "policy_design_projection_mints_authority",
            "Policy Design Case projections must be projection_only.",
        )
    policy = _text(projection.get("projection_policy"))
    if policy not in _ALLOWED_PROJECTION_POLICIES:
        raise PolicyDesignCaseProjectionError(
            "policy_design_projection_policy_invalid",
            "Policy Design Case projections must read a case or runtime PDC graph "
            "without issuing authority.",
        )
    for label in _sequence(projection.get("labels")):
        if not isinstance(label, Mapping):
            continue
        label_role = _text(label.get("authority_role")).casefold()
        if label_role != "projection_only":
            raise PolicyDesignCaseProjectionError(
                "policy_design_projection_label_mints_authority",
                "Projection labels cannot carry authority-bearing roles.",
            )
    may_not = {_text(item) for item in _sequence(projection.get("may_not_be_used_for"))}
    if not {"claim_authority", "scorecard_authority", "runtime_closeout_authority"} <= may_not:
        raise PolicyDesignCaseProjectionError(
            "policy_design_projection_limits_missing",
            "Projection must forbid claim, scorecard, and runtime closeout authority use.",
        )
    if _sequence(projection.get("authoritative_for")):
        raise PolicyDesignCaseProjectionError(
            "policy_design_projection_authoritative_for_nonempty",
            "Policy Design Case projections cannot fill authority slots.",
        )
    try:
        typed = contracts.PolicyDesignCaseProjection.model_validate(projection)
    except ValidationError as exc:
        raise PolicyDesignCaseProjectionError(
            "policy_design_projection_contract_invalid",
            str(exc),
        ) from exc
    return typed.model_dump(mode="json", exclude_none=True)


def _projection_states(
    case: Mapping[str, Any],
    *,
    source_payload: Mapping[str, Any],
    surface: str,
    forced_blocked: bool = False,
) -> tuple[str, ...]:
    states: set[str] = {"projection_only"}
    surface_name = _text(surface).casefold()
    if (
        surface_name in {"public_export", "public-export"}
        or surface_name.startswith("public_")
        or _is_redacted(source_payload)
    ):
        states.add("redacted")
    if _is_draft(source_payload):
        states.add("draft")
    if forced_blocked or _is_blocked(case) or _is_blocked(source_payload):
        states.add("blocked")
    if _is_contested(case) or _is_contested(source_payload):
        states.add("contested")
    if _is_stale(case) or _is_stale(source_payload):
        states.add("stale")
    if _is_publishable(source_payload) and not states & {"blocked", "contested", "stale", "draft"}:
        states.add("publishable")
    return tuple(state for state in PROJECTION_STATES if state in states)


def _assert_source_is_projection_safe(source: Mapping[str, Any]) -> None:
    role = _text(source.get("authority_role")).casefold()
    if role in _SOURCE_AUTHORITY_ROLES_THAT_MINT_AUTHORITY:
        raise PolicyDesignCaseProjectionError(
            "policy_design_projection_source_mints_authority",
            (
                "Projection source must not claim producer, scorecard, readiness, "
                "or approval authority."
            ),
        )
    if role not in _ALLOWED_FINAL_ARTIFACT_SOURCE_ROLES:
        raise PolicyDesignCaseProjectionError(
            "policy_design_projection_source_authority_role_invalid",
            f"Unsupported projection source authority_role={role!r}.",
        )
    _assert_capability_binding_results_projection_safe(source)


def _assert_capability_binding_results_projection_safe(
    source: Mapping[str, Any],
) -> None:
    for binding in _capability_binding_rows(source):
        authority_role = _text(binding.get("authority_role")).casefold()
        authoritative_for = {
            _text(item) for item in _sequence(binding.get("authoritative_for"))
        }
        if authority_role == "projection_only" and (
            bool(binding.get("satisfies_claim_evidence"))
            or bool(authoritative_for)
        ):
            raise PolicyDesignCaseProjectionError(
                "capability_binding_projection_laundering",
                (
                    "Projection-only capability binding results cannot satisfy "
                    "claim evidence or fill authoritative_for slots."
                ),
            )


def _capability_binding_rows(source: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for key in ("capability_binding_results", "capability_bindings"):
        value = source.get(key)
        if isinstance(value, Mapping):
            rows.extend(row for row in value.values() if isinstance(row, Mapping))
        elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
            rows.extend(row for row in value if isinstance(row, Mapping))
    return tuple(rows)


def build_policy_design_case_projection_contract_fixture(
    *,
    policy_design_case: Mapping[str, Any],
    closeout_verdict: Mapping[str, Any],
    source_payload: Mapping[str, Any] | None = None,
    audiences: Sequence[contracts.PolicyDesignCaseAudience | str] = (
        contracts.PolicyDesignCaseAudience.PUBLIC,
        contracts.PolicyDesignCaseAudience.REVIEWER,
        contracts.PolicyDesignCaseAudience.EXPERT,
        contracts.PolicyDesignCaseAudience.MACHINE,
    ),
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build multi-audience consumer-contract fixtures over one projection truth."""

    projections: dict[str, dict[str, Any]] = {}
    for audience in audiences:
        audience_value = _audience(audience, surface="")
        projections[audience_value.value] = build_policy_design_case_projection_semantics(
            policy_design_case=policy_design_case,
            surface=f"{audience_value.value}_projection",
            source_payload=source_payload,
            closeout_verdict=closeout_verdict,
            audience=audience_value,
            generated_at=generated_at,
        )
    expected_closeout_truth = _closeout_truth(
        closeout_verdict,
        contested=any(
            bool(projection.get("contested_records")) for projection in projections.values()
        ),
        recourse_gap=None,
    )
    expected_contested_record_ids = sorted(
        {
            _text(record.get("contested_record_id"))
            for projection in projections.values()
            for record in _sequence(projection.get("contested_records"))
            if isinstance(record, Mapping)
        }
    )
    verification = verify_policy_design_case_projection_consumer_contract(
        projections=projections,
        expected_closeout_truth=expected_closeout_truth,
        expected_contested_record_ids=expected_contested_record_ids,
    )
    status_by_audience = {
        _text(row.get("audience")): _text(row.get("status"))
        for row in _sequence(verification.get("consumer_contracts"))
        if isinstance(row, Mapping)
    }
    for audience, projection in list(projections.items()):
        projections[audience] = {
            **projection,
            "contract_verification_status": status_by_audience.get(audience) or "fail",
            "contract_verification_refs": [
                "policyos.runtime.policy_design_case.projection_contract_verification.v1"
            ],
        }
    return {
        "schema_version": "policyos.runtime.policy_design_case.projection_contract_fixture.v1",
        "status": verification["status"],
        "expected_closeout_truth": expected_closeout_truth,
        "expected_contested_record_ids": expected_contested_record_ids,
        "projections": projections,
        "consumer_contracts": verification["consumer_contracts"],
        "issues": verification["issues"],
    }


def verify_policy_design_case_projection_consumer_contract(
    *,
    projections: Mapping[str, Mapping[str, Any]],
    expected_closeout_truth: Mapping[str, Any],
    expected_contested_record_ids: Sequence[str] = (),
    runtime_pdc_graph: Mapping[str, Any] | object | None = None,
) -> dict[str, Any]:
    """Verify that audience projections preserve closeout and contested truth."""

    expected_truth = contracts.PolicyDesignCaseCloseoutTruth.model_validate(expected_closeout_truth)
    expected_blocker_codes = set(expected_truth.blocker_codes)
    expected_omission_codes = set(expected_truth.omission_codes)
    expected_contested_ids = {
        _text(value) for value in expected_contested_record_ids if _text(value)
    }
    graph = None
    graph_fields: set[str] = set()
    if runtime_pdc_graph is not None:
        from polisyos.pdc import RuntimePolicyDesignCase

        graph = RuntimePolicyDesignCase.model_validate(runtime_pdc_graph)
        graph_fields = set(RuntimePolicyDesignCase.model_fields)
    issues: list[dict[str, Any]] = []
    consumer_contracts: list[dict[str, Any]] = []
    for audience, projection in projections.items():
        audience_issues: list[dict[str, Any]] = []
        try:
            typed = contracts.PolicyDesignCaseProjection.model_validate(projection)
        except ValidationError as exc:
            audience_issues.append(
                _contract_issue(
                    "policy_design_projection_contract_invalid",
                    audience=audience,
                    message=str(exc),
                )
            )
            typed = None
        if typed is not None:
            if (
                typed.closeout_truth.status != expected_truth.status
                or typed.closeout_truth.verdict != expected_truth.verdict
                or typed.closeout_truth.can_closeout != expected_truth.can_closeout
            ):
                audience_issues.append(
                    _contract_issue(
                        "policy_design_projection_changes_closeout_truth",
                        audience=audience,
                        message="Audience projection changed closeout status, verdict, or closure.",
                    )
                )
            if not expected_blocker_codes <= set(typed.closeout_truth.blocker_codes):
                audience_issues.append(
                    _contract_issue(
                        "policy_design_projection_hides_closeout_blockers",
                        audience=audience,
                        message="Audience projection omitted closeout blocker codes.",
                    )
                )
            if not expected_omission_codes <= set(typed.closeout_truth.omission_codes):
                audience_issues.append(
                    _contract_issue(
                        "policy_design_projection_hides_closeout_omissions",
                        audience=audience,
                        message="Audience projection omitted closeout omission codes.",
                    )
                )
            omission_codes = {row.omission_code for row in typed.omission_manifest}
            if expected_omission_codes and not expected_omission_codes <= omission_codes:
                audience_issues.append(
                    _contract_issue(
                        "policy_design_projection_hides_omission_manifest",
                        audience=audience,
                        message="Audience projection omitted required omission manifest rows.",
                    )
                )
            contested_ids = {record.contested_record_id for record in typed.contested_records}
            if not expected_contested_ids <= contested_ids:
                audience_issues.append(
                    _contract_issue(
                        "policy_design_projection_hides_contested_state",
                        audience=audience,
                        message=(
                            "Audience projection omitted contested records visible in the case."
                        ),
                    )
                )
            if typed.audience is contracts.PolicyDesignCaseAudience.MACHINE and not (
                typed.source_ref or typed.source_authority_refs or typed.audit_refs
            ):
                audience_issues.append(
                    _contract_issue(
                        "policy_design_projection_machine_refs_missing",
                        audience=audience,
                        message=(
                            "Machine projection must preserve reconstructable source, "
                            "authority, or audit refs."
                        ),
                        )
                    )
            if graph is not None:
                source_state = dict(typed.source_state)
                consumed_fields = {
                    _text(value)
                    for value in _sequence(
                        source_state.get("runtime_pdc_graph_consumed_fields")
                    )
                    if _text(value)
                }
                if typed.projection_policy != _RUNTIME_GRAPH_PROJECTION_POLICY:
                    audience_issues.append(
                        _contract_issue(
                            "policy_design_projection_not_graph_backed",
                            audience=audience,
                            message=(
                                "Projection consumer contract requires the W8.A "
                                "RuntimePolicyDesignCase graph source policy."
                            ),
                        )
                    )
                if typed.source_ref != graph.graph_ref or source_state.get(
                    "runtime_pdc_graph_ref"
                ) != graph.graph_ref:
                    audience_issues.append(
                        _contract_issue(
                            "policy_design_projection_runtime_graph_ref_mismatch",
                            audience=audience,
                            message=(
                                "Projection source_ref/source_state must point at the "
                                "RuntimePolicyDesignCase graph ref."
                            ),
                        )
                    )
                if not consumed_fields:
                    audience_issues.append(
                        _contract_issue(
                            "policy_design_projection_graph_consumed_fields_missing",
                            audience=audience,
                            message=(
                                "Graph-backed projections must declare the graph fields "
                                "they consumed."
                            ),
                        )
                    )
                invalid_fields = sorted(consumed_fields - graph_fields)
                if invalid_fields:
                    audience_issues.append(
                        _contract_issue(
                            "policy_design_projection_reads_field_absent_from_runtime_graph",
                            audience=audience,
                            message=(
                                "Projection declared graph fields absent from the W8.A "
                                f"schema: {', '.join(invalid_fields)}."
                            ),
                        )
                    )
        issues.extend(audience_issues)
        consumer_contracts.append(
            {
                "consumer": _text(audience),
                "audience": _text(audience),
                "status": "fail" if audience_issues else "pass",
                "issue_codes": [issue["code"] for issue in audience_issues],
                "verified_fields": [
                    "closeout_truth",
                    "blockers",
                    "limitations",
                    "omissions",
                    "contested_records",
                ]
                + (
                    [
                        "runtime_pdc_graph_ref",
                        "runtime_pdc_graph_consumed_fields",
                    ]
                    if graph is not None
                    else []
                ),
            }
        )
    return {
        "schema_version": "policyos.runtime.policy_design_case.projection_contract_verification.v1",
        "status": "fail" if issues else "pass",
        "consumer_contracts": consumer_contracts,
        "issues": issues,
    }


def verify_s9_projection_faithfulness_for_pdc_consumer_contract(
    *,
    projections: Mapping[str, Mapping[str, Any]],
    expected_closeout_truth: Mapping[str, Any],
    expected_contested_record_ids: Sequence[str] = (),
    expected_deficit_codes: Sequence[str] = (),
    expected_source_revision_ref: str | None = None,
) -> dict[str, Any]:
    """Verify S9 faithfulness while reusing the PDC projection consumer contract."""

    adapted_projections: dict[str, dict[str, Any]] = {}
    s9_records: dict[str, dict[str, Any]] = {}
    for audience, projection in projections.items():
        projection_payload = _mapping_from_record(projection)
        faithfulness = _s9_faithfulness_record(projection_payload)
        s9_records[audience] = faithfulness
        adapted_projections[audience] = _s9_consumer_projection(
            projection_payload,
            faithfulness=faithfulness,
            audience=audience,
        )

    base = verify_policy_design_case_projection_consumer_contract(
        projections=adapted_projections,
        expected_closeout_truth=expected_closeout_truth,
        expected_contested_record_ids=expected_contested_record_ids,
    )
    issues = [dict(issue) for issue in _sequence(base.get("issues")) if isinstance(issue, Mapping)]
    for audience, projection in projections.items():
        projection_payload = _mapping_from_record(projection)
        faithfulness = s9_records[audience]
        issues.extend(
            _s9_projection_issues(
                audience=audience,
                projection=projection_payload,
                faithfulness=faithfulness,
                expected_deficit_codes=expected_deficit_codes,
                expected_source_revision_ref=expected_source_revision_ref,
            )
        )

    issue_codes = _unique_texts(issue.get("code") for issue in issues)
    first_record = next(iter(s9_records.values()), {})
    return {
        "schema_version": "policyos.runtime.policy_design_case.s9_projection_verification.v1",
        "status": "fail" if issues else "pass",
        "consumer_contract_ref": _S9_CONSUMER_CONTRACT_REF,
        "consumer_contracts": list(base.get("consumer_contracts", [])),
        "projection_contract_verification": base,
        "s9_projection_faithfulness": first_record,
        "issue_codes": issue_codes,
        "issues": issues,
    }


def verify_s10_forecast_projection_consumer_contract(
    *,
    projections: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Verify S10 forecast-support projections without minting recommendation authority."""

    issues: list[dict[str, Any]] = []
    consumer_contracts: list[dict[str, Any]] = []
    s10_records: dict[str, dict[str, Any]] = {}
    for audience, projection in projections.items():
        projection_payload = _mapping_from_record(projection)
        s10_record = _s10_forecast_projection_record(projection_payload)
        s10_records[audience] = s10_record
        audience_issues = _s10_projection_issues(
            audience=audience,
            projection=projection_payload,
            s10_record=s10_record,
        )
        issues.extend(audience_issues)
        consumer_contracts.append(
            {
                "consumer": _text(audience),
                "audience": _text(audience),
                "status": "fail" if audience_issues else "pass",
                "issue_codes": [issue["code"] for issue in audience_issues],
                "verified_fields": [
                    "forecast_tier",
                    "forecast_support_ref",
                    "forecast_calibration_record_ref",
                    "design_graph_ref",
                    "prediction_context_ref",
                    "source_contract_ref",
                    "method_validity_ref",
                    "credible_evaluation_evidence_ref",
                    "uncertainty_interval_refs",
                    "welfare_comparison",
                    "authority_boundary",
                ],
            }
        )
    issue_codes = _unique_texts(issue.get("code") for issue in issues)
    first_record = next(iter(s10_records.values()), {})
    return {
        "schema_version": _S10_CONSUMER_CONTRACT_REF,
        "status": "fail" if issues else "pass",
        "consumer_contract_ref": _S10_CONSUMER_CONTRACT_REF,
        "consumer_contracts": consumer_contracts,
        "s10_forecast_projection": first_record,
        "issue_codes": issue_codes,
        "issues": issues,
    }


def verify_s11_predictive_projection_consumer_contract(
    *,
    projections: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Verify S11 predictive posture projections without authority promotion."""

    issues: list[dict[str, Any]] = []
    consumer_contracts: list[dict[str, Any]] = []
    s11_records: dict[str, dict[str, Any]] = {}
    public_projection: dict[str, Any] = {}
    for audience, projection in projections.items():
        projection_payload = _mapping_from_record(projection)
        s11_record = _s11_predictive_projection_record(projection_payload)
        s11_records[audience] = s11_record
        audience_issues = _s11_projection_issues(
            audience=audience,
            projection=projection_payload,
            s11_record=s11_record,
        )
        issues.extend(audience_issues)
        if _audience(
            projection_payload.get("audience") or audience,
            surface="s11_predictive_projection",
        ) is contracts.PolicyDesignCaseAudience.PUBLIC:
            public_projection = _s11_public_projection(projection_payload, s11_record)
        consumer_contracts.append(
            {
                "consumer": _text(audience),
                "audience": _text(audience),
                "status": "fail" if audience_issues else "pass",
                "issue_codes": [issue["code"] for issue in audience_issues],
                "verified_fields": [
                    "s11_predictive_posture_ref",
                    "predictive_axis_upgrade_refs",
                    "predictive_axis_rows",
                    "per_axis_predictive_calibration_status",
                    "proof_carrying_analytics_ref",
                    "ir_analytics_bridge_ref",
                    "residual_limitation_refs",
                    "weakest_boundary_reason",
                    "authority_boundary",
                ],
            }
        )
    issue_codes = _unique_texts(issue.get("code") for issue in issues)
    first_record = next(iter(s11_records.values()), {})
    return {
        "schema_version": _S11_CONSUMER_CONTRACT_REF,
        "status": "fail" if issues else "pass",
        "consumer_contract_ref": _S11_CONSUMER_CONTRACT_REF,
        "consumer_contracts": consumer_contracts,
        "s11_predictive_projection": first_record,
        "public_projection": public_projection,
        "issue_codes": issue_codes,
        "issues": issues,
    }


def verify_s12_resource_projection_consumer_contract(
    *,
    projections: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Verify S12 resource-economics projections without allocation authority."""

    issues: list[dict[str, Any]] = []
    consumer_contracts: list[dict[str, Any]] = []
    s12_records: dict[str, dict[str, Any]] = {}
    public_projection: dict[str, Any] = {}
    for audience, projection in projections.items():
        projection_payload = _mapping_from_record(projection)
        s12_record = _s12_resource_projection_record(projection_payload)
        s12_records[audience] = s12_record
        audience_issues = _s12_projection_issues(
            audience=audience,
            projection=projection_payload,
            s12_record=s12_record,
        )
        issues.extend(audience_issues)
        if _audience(
            projection_payload.get("audience") or audience,
            surface="s12_resource_projection",
        ) is contracts.PolicyDesignCaseAudience.PUBLIC:
            public_projection = _s12_public_projection(projection_payload, s12_record)
        consumer_contracts.append(
            {
                "consumer": _text(audience),
                "audience": _text(audience),
                "status": "fail" if audience_issues else "pass",
                "issue_codes": [issue["code"] for issue in audience_issues],
                "verified_fields": [
                    "resource_allocation_policy_ref",
                    "explore_exploit_posture",
                    "explore_exploit_dial_ref",
                    "voi_allocation_refs",
                    "typed_budget_refs",
                    "pareto_archive_ref",
                    "envelope_growth_ledger_ref",
                    "growth_thermometer_ref",
                    "override_rate_trend",
                    "reuse_rate_trend",
                    "residual_limitation_refs",
                    "authority_boundary",
                ],
            }
        )
    issue_codes = _unique_texts(issue.get("code") for issue in issues)
    first_record = next(iter(s12_records.values()), {})
    return {
        "schema_version": _S12_CONSUMER_CONTRACT_REF,
        "status": "fail" if issues else "pass",
        "consumer_contract_ref": _S12_CONSUMER_CONTRACT_REF,
        "consumer_contracts": consumer_contracts,
        "s12_resource_projection": first_record,
        "public_projection": public_projection,
        "issue_codes": issue_codes,
        "issues": issues,
    }


def _s10_forecast_projection_record(projection: Mapping[str, Any]) -> dict[str, Any]:
    if not (
        _text(projection.get("forecast_support_ref"))
        or _text(projection.get("forecast_tier"))
        or _text(projection.get("forecast_calibration_record_ref"))
    ):
        return {}
    authority_boundary = _mapping(
        projection.get("authority_boundary")
        or projection.get("forecast_authority_boundary")
    )
    calibration_status = _s10_calibration_status(projection)
    return {
        "forecast_support_ref": _text(projection.get("forecast_support_ref")),
        "forecast_tier": _text(projection.get("forecast_tier")),
        "forecast_authority_disposition_reason": _text(
            projection.get("forecast_authority_disposition_reason")
        ),
        "forecast_support_label": _text(projection.get("forecast_support_label")),
        "forecast_calibration_record_ref": _text(
            projection.get("forecast_calibration_record_ref")
        ),
        "observable_subset_calibration_status": calibration_status,
        "design_graph_ref": _text(projection.get("design_graph_ref")),
        "prediction_context_ref": _text(projection.get("prediction_context_ref")),
        "policy_context_ref": _text(projection.get("policy_context_ref")),
        "source_contract_ref": _text(projection.get("source_contract_ref")),
        "method_validity_ref": _text(projection.get("method_validity_ref")),
        "credible_evaluation_evidence_ref": _text(
            projection.get("credible_evaluation_evidence_ref")
        ),
        "uncertainty_interval_refs": _text_list(
            projection.get("uncertainty_interval_refs")
        ),
        "s5_forecast_support_ref": _text(projection.get("s5_forecast_support_ref")),
        "s6_firewall_status_refs": _text_list(projection.get("s6_firewall_status_refs")),
        "s8_value_choice_provenance_ref": _text(
            projection.get("s8_value_choice_provenance_ref")
        ),
        "s8_value_tradeoff_disclosure_ref": _text(
            projection.get("s8_value_tradeoff_disclosure_ref")
        ),
        "welfare_comparison_ref": _text(projection.get("welfare_comparison_ref")),
        "welfare_comparison": _mapping(projection.get("welfare_comparison")),
        "authority_boundary": authority_boundary,
        "may_not_be_used_for": _unique_texts(
            [
                *_text_list(projection.get("may_not_be_used_for")),
                *_text_list(projection.get("may_not_use_for")),
            ]
        ),
        "rule_version_ref": _text(projection.get("rule_version_ref")),
    }


def _s11_predictive_projection_record(projection: Mapping[str, Any]) -> dict[str, Any]:
    if not (
        _text(projection.get("s11_predictive_posture_ref"))
        or _text(projection.get("predictive_knowledge_ref"))
        or _sequence(projection.get("predictive_axis_rows"))
    ):
        return {}
    authority_boundary = _mapping(
        projection.get("authority_boundary")
        or projection.get("predictive_authority_boundary")
    )
    return {
        "s11_predictive_posture_ref": _text(
            projection.get("s11_predictive_posture_ref")
            or projection.get("predictive_knowledge_ref")
        ),
        "effective_predictive_posture": _text(
            projection.get("effective_predictive_posture")
            or projection.get("predictive_authority_status")
        ),
        "predictive_axis_upgrade_refs": _text_list(
            projection.get("predictive_axis_upgrade_refs")
            or projection.get("axis_upgrade_refs")
        ),
        "predictive_axis_rows": [
            _mapping(row)
            for row in _sequence(projection.get("predictive_axis_rows"))
            if isinstance(row, Mapping)
        ],
        "per_axis_predictive_calibration_status": _text(
            projection.get("per_axis_predictive_calibration_status")
        ),
        "per_axis_predictive_calibration_threshold_ref": _text(
            projection.get("per_axis_predictive_calibration_threshold_ref")
        ),
        "proof_carrying_analytics_ref": _text(
            projection.get("proof_carrying_analytics_ref")
        ),
        "ir_analytics_bridge_ref": _text(projection.get("ir_analytics_bridge_ref")),
        "residual_limitation_refs": _text_list(
            projection.get("residual_limitation_refs")
        ),
        "weakest_boundary_reason": _text(projection.get("weakest_boundary_reason")),
        "s11_public_limitation": _text(projection.get("s11_public_limitation")),
        "authority_boundary": authority_boundary,
        "may_not_be_used_for": _unique_texts(
            [
                *_text_list(projection.get("may_not_be_used_for")),
                *_text_list(projection.get("may_not_use_for")),
                *_text_list(authority_boundary.get("may_not_use_for")),
            ]
        ),
        "authority_role": _text(projection.get("authority_role")) or "projection_only",
        "rule_version_ref": _text(projection.get("rule_version_ref")),
    }


def _s11_projection_issues(
    *,
    audience: str,
    projection: Mapping[str, Any],
    s11_record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if not s11_record:
        return [
            _contract_issue(
                "s11_predictive_projection_missing",
                audience=audience,
                message="S11 predictive posture projection fields are missing.",
            )
        ]
    issues: list[dict[str, Any]] = []
    audience_value = _audience(
        projection.get("audience") or audience,
        surface="s11_predictive_projection",
    )
    if audience_value is contracts.PolicyDesignCaseAudience.PUBLIC:
        if not _text(s11_record.get("s11_public_limitation")):
            issues.append(
                _contract_issue(
                    "s11_public_limitation_missing",
                    audience=audience,
                    message="PUBLIC S11 projection requires a high-level limitation.",
                )
            )
    else:
        required_fields = {
            "s11_predictive_posture_ref": "S11 posture ref",
            "predictive_axis_rows": "predictive axis rows",
            "per_axis_predictive_calibration_status": "calibration status",
            "per_axis_predictive_calibration_threshold_ref": "calibration threshold ref",
            "proof_carrying_analytics_ref": "proof-carrying analytics ref",
            "ir_analytics_bridge_ref": "IR analytics bridge ref",
            "residual_limitation_refs": "residual limitation refs",
            "weakest_boundary_reason": "weakest boundary reason",
        }
        for field_name, label in required_fields.items():
            value = s11_record.get(field_name)
            if not value:
                issues.append(
                    _contract_issue(
                        "s11_predictive_projection_missing_audit_field",
                        audience=audience,
                        message=f"{label} missing from S11 projection.",
                    )
                )
    if _s11_prediction_authority_laundered(projection, s11_record):
        issues.append(
            _contract_issue(
                "s11_predictive_authority_laundering",
                audience=audience,
                message=(
                    "S11 predictive posture projection crossed into recommendation "
                    "or claim authority."
                ),
            )
        )
    return _dedupe_contract_issues(issues)


def _s11_prediction_authority_laundered(
    projection: Mapping[str, Any],
    s11_record: Mapping[str, Any],
) -> bool:
    role = _text(projection.get("authority_role")).casefold()
    if role not in {"", "projection_only"}:
        return True
    boundary = _mapping(s11_record.get("authority_boundary"))
    authoritative_for = {
        *_text_list(projection.get("authoritative_for")),
        *_text_list(boundary.get("authoritative_for")),
    }
    if authoritative_for & _S11_FORBIDDEN_AUTHORITY_USES:
        return True
    may_not = {
        *_text_list(s11_record.get("may_not_be_used_for")),
        *_text_list(boundary.get("may_not_use_for")),
    }
    return not may_not >= _S11_REQUIRED_MAY_NOT_USE_FOR


def _s11_public_projection(
    projection: Mapping[str, Any],
    s11_record: Mapping[str, Any],
) -> dict[str, Any]:
    may_not = _unique_texts(
        [
            *_text_list(s11_record.get("may_not_be_used_for")),
            *_S11_REQUIRED_MAY_NOT_USE_FOR,
        ]
    )
    return {
        "authority_role": "projection_only",
        "effective_predictive_posture": _text(
            s11_record.get("effective_predictive_posture")
        ),
        "s11_public_limitation": _text(
            projection.get("s11_public_limitation")
            or s11_record.get("s11_public_limitation")
        ),
        "may_not_be_used_for": may_not,
    }


def _s12_resource_projection_record(projection: Mapping[str, Any]) -> dict[str, Any]:
    if not (
        _text(projection.get("resource_allocation_policy_ref"))
        or _text(projection.get("s12_resource_posture_ref"))
        or _text(projection.get("explore_exploit_posture"))
    ):
        return {}
    authority_boundary = _mapping(
        projection.get("resource_authority_boundary")
        or projection.get("authority_boundary")
    )
    return {
        "s12_resource_posture_ref": _text(projection.get("s12_resource_posture_ref")),
        "resource_allocation_policy_ref": _text(
            projection.get("resource_allocation_policy_ref")
            or projection.get("s12_resource_posture_ref")
        ),
        "explore_exploit_posture": _text(projection.get("explore_exploit_posture")),
        "explore_exploit_dial_ref": _text(projection.get("explore_exploit_dial_ref")),
        "delegation_contract_ref": _text(projection.get("delegation_contract_ref")),
        "voi_allocation_refs": _text_list(projection.get("voi_allocation_refs")),
        "voi_site_count": _int(projection.get("voi_site_count")),
        "typed_budget_refs": _text_list(projection.get("typed_budget_refs")),
        "pareto_archive_ref": _text(projection.get("pareto_archive_ref")),
        "envelope_growth_ledger_ref": _text(
            projection.get("envelope_growth_ledger_ref")
        ),
        "growth_thermometer_ref": _text(projection.get("growth_thermometer_ref")),
        "override_rate_trend": _text(projection.get("override_rate_trend")),
        "reuse_rate_trend": _text(projection.get("reuse_rate_trend")),
        "held_out_status": _text(projection.get("held_out_status")),
        "resource_allocation_disposition": _text(
            projection.get("resource_allocation_disposition")
        ),
        "residual_limitation_refs": _text_list(
            projection.get("residual_limitation_refs")
        ),
        "s12_public_growth_limitation": _text(
            projection.get("s12_public_growth_limitation")
        ),
        "authority_boundary": authority_boundary,
        "may_not_be_used_for": _unique_texts(
            [
                *_text_list(projection.get("may_not_be_used_for")),
                *_text_list(projection.get("may_not_use_for")),
                *_text_list(authority_boundary.get("may_not_use_for")),
            ]
        ),
        "authority_role": _text(projection.get("authority_role")) or "projection_only",
        "rule_version_ref": _text(projection.get("rule_version_ref")),
    }


def _s12_projection_issues(
    *,
    audience: str,
    projection: Mapping[str, Any],
    s12_record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if not s12_record:
        return [
            _contract_issue(
                "s12_resource_projection_missing",
                audience=audience,
                message="S12 resource posture projection fields are missing.",
            )
        ]
    issues: list[dict[str, Any]] = []
    audience_value = _audience(
        projection.get("audience") or audience,
        surface="s12_resource_projection",
    )
    if audience_value is contracts.PolicyDesignCaseAudience.PUBLIC:
        if not _text(s12_record.get("s12_public_growth_limitation")):
            issues.append(
                _contract_issue(
                    "s12_public_growth_limitation_missing",
                    audience=audience,
                    message="PUBLIC S12 projection requires a high-level growth limitation.",
                )
            )
    else:
        required_fields = {
            "resource_allocation_policy_ref": "resource allocation policy ref",
            "explore_exploit_posture": "explore/exploit posture",
            "voi_allocation_refs": "VOI allocation refs",
            "typed_budget_refs": "typed budget refs",
            "pareto_archive_ref": "Pareto archive ref",
            "envelope_growth_ledger_ref": "envelope growth ledger ref",
            "growth_thermometer_ref": "growth thermometer ref",
            "override_rate_trend": "override trend",
            "reuse_rate_trend": "reuse trend",
        }
        for field_name, label in required_fields.items():
            if not s12_record.get(field_name):
                issues.append(
                    _contract_issue(
                        "s12_resource_projection_missing_audit_field",
                        audience=audience,
                        message=f"{label} missing from S12 projection.",
                    )
                )
        if _int(s12_record.get("voi_site_count")) < 3:
            issues.append(
                _contract_issue(
                    "s12_resource_projection_missing_audit_field",
                    audience=audience,
                    message="S12 projection requires VOI refs across at least three sites.",
                )
            )
        if len(_text_list(s12_record.get("typed_budget_refs"))) < 5:
            issues.append(
                _contract_issue(
                    "s12_resource_projection_missing_audit_field",
                    audience=audience,
                    message="S12 projection requires all typed budget refs.",
                )
            )
    if _s12_allocation_authority_laundered(projection, s12_record):
        issues.append(
            _contract_issue(
                "s12_allocation_as_recommendation_authority",
                audience=audience,
                message=(
                    "S12 resource allocation projection crossed into recommendation "
                    "or production authority."
                ),
            )
        )
    if _s12_growth_without_delta_surfaced(projection):
        issues.append(
            _contract_issue(
                "s12_growth_without_envelope_delta_surfaced_as_growth",
                audience=audience,
                message="S12 growth cannot be surfaced as mechanism growth without envelope delta.",
            )
        )
    if _s12_explore_exploit_self_set(s12_record):
        issues.append(
            _contract_issue(
                "s12_explore_exploit_self_set",
                audience=audience,
                message="S12 explore/exploit posture requires an S7 delegation dial ref.",
            )
        )
    if _S12_SCALAR_ALLOCATION_KEYS & set(projection):
        issues.append(
            _contract_issue(
                "s12_hidden_pareto_allocation_scalar",
                audience=audience,
                message=(
                    "S12 allocation projection cannot hide the Pareto frontier "
                    "behind a scalar."
                ),
            )
        )
    return _dedupe_contract_issues(issues)


def _s12_allocation_authority_laundered(
    projection: Mapping[str, Any],
    s12_record: Mapping[str, Any],
) -> bool:
    role = _text(projection.get("authority_role")).casefold()
    if role not in {"", "projection_only"}:
        return True
    if _text(projection.get("allocation_recommendation_text")) or _text(
        projection.get("production_recommendation_text")
    ):
        return True
    boundary = _mapping(s12_record.get("authority_boundary"))
    authoritative_for = {
        *_text_list(projection.get("authoritative_for")),
        *_text_list(boundary.get("authoritative_for")),
    }
    if authoritative_for & _S12_FORBIDDEN_AUTHORITY_USES:
        return True
    may_not = {
        *_text_list(s12_record.get("may_not_be_used_for")),
        *_text_list(boundary.get("may_not_use_for")),
    }
    return not may_not >= _S12_REQUIRED_MAY_NOT_USE_FOR


def _s12_growth_without_delta_surfaced(projection: Mapping[str, Any]) -> bool:
    if _int(projection.get("growth_without_envelope_delta_count")) <= 0:
        return False
    disposition = _text(projection.get("growth_counting_disposition"))
    return disposition in {"", "counted_mechanism_growth"}


def _s12_explore_exploit_self_set(s12_record: Mapping[str, Any]) -> bool:
    posture = _text(s12_record.get("explore_exploit_posture"))
    if posture in {"", "blocked"}:
        return False
    return not _text(s12_record.get("explore_exploit_dial_ref"))


def _s12_public_projection(
    projection: Mapping[str, Any],
    s12_record: Mapping[str, Any],
) -> dict[str, Any]:
    may_not = _unique_texts(
        [
            *_text_list(s12_record.get("may_not_be_used_for")),
            *_S12_REQUIRED_MAY_NOT_USE_FOR,
        ]
    )
    return {
        "authority_role": "projection_only",
        "explore_exploit_posture": _text(s12_record.get("explore_exploit_posture")),
        "override_rate_trend": _text(s12_record.get("override_rate_trend")),
        "reuse_rate_trend": _text(s12_record.get("reuse_rate_trend")),
        "s12_public_growth_limitation": _text(
            projection.get("s12_public_growth_limitation")
            or s12_record.get("s12_public_growth_limitation")
        ),
        "may_not_be_used_for": may_not,
    }


def _s10_projection_issues(
    *,
    audience: str,
    projection: Mapping[str, Any],
    s10_record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if not s10_record:
        return [
            _contract_issue(
                "s10_forecast_projection_missing",
                audience=audience,
                message="S10 forecast-support projection fields are missing.",
            )
        ]
    issues: list[dict[str, Any]] = []
    tier = _text(s10_record.get("forecast_tier"))
    if not (
        _text(s10_record.get("design_graph_ref"))
        and _text(s10_record.get("prediction_context_ref"))
    ):
        issues.append(
            _contract_issue(
                "s10_missing_design_graph_or_prediction_context",
                audience=audience,
                message="S10 projection must preserve design graph and prediction context refs.",
            )
        )
    if tier == "simulation_only_advisory" and bool(
        projection.get("evidence_authority_claimed")
    ):
        issues.append(
            _contract_issue(
                "s10_simulation_only_laundered_as_evidence",
                audience=audience,
                message="Simulation-only forecasts cannot be rendered as evidence authority.",
            )
        )
    if tier == "equilibrium_contested_blocked" and not _text_list(
        s10_record.get("uncertainty_interval_refs")
    ):
        issues.append(
            _contract_issue(
                "s10_equilibrium_contested_single_forecast",
                audience=audience,
                message="Equilibrium-contested forecasts cannot be projected as a single forecast.",
            )
        )
    calibration_status = _text(s10_record.get("observable_subset_calibration_status"))
    if tier == "observable_calibrated" and (
        not _text(s10_record.get("forecast_calibration_record_ref"))
        or calibration_status != "pass"
    ):
        issues.append(
            _contract_issue(
                "s10_uncalibrated_observable_promotion",
                audience=audience,
                message="Observable calibrated tier requires a passing calibration record.",
            )
        )
    if (
        _text(projection.get("observed_outcome_ref"))
        or _text(projection.get("outcome_observation_ref"))
        or (tier == "observable_calibrated" and calibration_status == "pass")
    ) and not _text(s10_record.get("credible_evaluation_evidence_ref")):
        issues.append(
            _contract_issue(
                "s10_observed_outcome_without_credible_evaluation",
                audience=audience,
                message="Observed outcome support requires credible evaluation evidence refs.",
            )
        )
    if tier == "observable_calibrated" and not (
        _text(s10_record.get("source_contract_ref"))
        and _text(s10_record.get("method_validity_ref"))
    ):
        issues.append(
            _contract_issue(
                "s10_validated_model_missing_source_or_method_validity",
                audience=audience,
                message=(
                    "Validated local forecast projection requires source and "
                    "method-validity refs."
                ),
            )
        )
    welfare = _mapping(s10_record.get("welfare_comparison"))
    if (welfare or _text(s10_record.get("welfare_comparison_ref"))) and not (
        (
            _text(s10_record.get("s8_value_choice_provenance_ref"))
            and _text(s10_record.get("s8_value_tradeoff_disclosure_ref"))
        )
        or (
            _text(welfare.get("s8_value_choice_provenance_ref"))
            and _text(welfare.get("s8_value_tradeoff_disclosure_ref"))
        )
    ):
        issues.append(
            _contract_issue(
                "s10_missing_value_provenance",
                audience=audience,
                message="S10 welfare comparison must preserve S8 value provenance refs.",
            )
        )
    if tier in {
        "observable_calibrated",
        "transported_limited",
        "historical_prior_context",
    } and not _text_list(s10_record.get("uncertainty_interval_refs")):
        issues.append(
            _contract_issue(
                "s10_hidden_uncertainty_interval",
                audience=audience,
                message="S10 forecast projections must expose uncertainty interval refs.",
            )
        )
    if _s10_scalar_welfare_hides_tradeoff(s10_record):
        issues.append(
            _contract_issue(
                "s10_scalar_welfare_hides_pareto_tradeoff",
                audience=audience,
                message="Scalar welfare summaries require Pareto/tradeoff disclosure refs.",
            )
        )
    if _s10_prediction_authority_laundered(projection, s10_record):
        issues.append(
            _contract_issue(
                "s10_prediction_authority_laundering",
                audience=audience,
                message=(
                    "S10 projection crossed from forecast support into "
                    "recommendation authority."
                ),
            )
        )
    return _dedupe_contract_issues(issues)


def _s10_calibration_status(projection: Mapping[str, Any]) -> str:
    return _text(
        projection.get("observable_subset_calibration_status")
        or projection.get("calibration_status")
        or projection.get("forecast_calibration_status")
    )


def _s10_scalar_welfare_hides_tradeoff(s10_record: Mapping[str, Any]) -> bool:
    welfare = _mapping(s10_record.get("welfare_comparison"))
    if not bool(welfare.get("scalar_summary_allowed")):
        return False
    has_frontier = bool(
        _text(welfare.get("pareto_frontier_ref"))
        or _text(welfare.get("frontier_ref"))
        or _sequence(welfare.get("pareto_frontier"))
        or _sequence(welfare.get("frontier"))
    )
    has_rejected_nondominated = bool(
        _text_list(welfare.get("rejected_nondominated_alternative_refs"))
    )
    has_value_refs = bool(
        _text(welfare.get("s8_value_choice_provenance_ref"))
        and _text(welfare.get("s8_value_tradeoff_disclosure_ref"))
    )
    return not (has_frontier and (has_rejected_nondominated or has_value_refs))


def _s10_prediction_authority_laundered(
    projection: Mapping[str, Any],
    s10_record: Mapping[str, Any],
) -> bool:
    role = _text(projection.get("authority_role")).casefold()
    if role not in {"", "projection_only"}:
        return True
    boundary = _mapping(s10_record.get("authority_boundary"))
    authoritative_for = {
        *_text_list(projection.get("authoritative_for")),
        *_text_list(boundary.get("authoritative_for")),
    }
    if authoritative_for & _S10_FORBIDDEN_AUTHORITY_USES:
        return True
    may_not = {
        *_text_list(s10_record.get("may_not_be_used_for")),
        *_text_list(boundary.get("may_not_use_for")),
    }
    return not may_not >= _S10_REQUIRED_MAY_NOT_USE_FOR


def _s9_consumer_projection(
    projection: Mapping[str, Any],
    *,
    faithfulness: Mapping[str, Any],
    audience: str,
) -> dict[str, Any]:
    audience_value = _audience(projection.get("audience") or audience, surface="s9_projection")
    closeout_truth = _s9_closeout_truth(_mapping(projection.get("closeout_truth")))
    source_revision_ref = _text(
        projection.get("source_revision_ref") or faithfulness.get("source_revision_ref")
    )
    canonical_ref = _text(
        projection.get("canonical_design_record_ref")
        or faithfulness.get("canonical_design_record_ref")
    )
    faithfulness_ref = _text(faithfulness.get("faithfulness_ref"))
    source_ref = canonical_ref or _text(projection.get("source_ref"))
    audit_refs = _unique_texts(
        [
            *_text_list(projection.get("audit_refs")),
            faithfulness_ref,
            _text(faithfulness.get("render_ref")),
            _text(faithfulness.get("request_ref")),
            canonical_ref,
        ]
    )
    return {
        "schema_version": POLICY_DESIGN_CASE_PROJECTION_SCHEMA_VERSION,
        "generated_at": _utc(None).isoformat(),
        "surface": "s9_projection_faithfulness",
        "audience": audience_value.value,
        "policy_design_case_id": _text(projection.get("policy_design_case_id")),
        "run_id": _text(projection.get("run_id")),
        "source_ref": source_ref,
        "source_ref_fingerprint": _fingerprint(source_ref) if source_ref else None,
        "primary_state": "blocked"
        if closeout_truth.get("blocker_codes")
        else "projection_only",
        "states": [
            "projection_only",
            *(["blocked"] if closeout_truth.get("blocker_codes") else []),
        ],
        "labels": [
            {
                "state": "projection_only",
                "label": "Projection only",
                "authority_role": "projection_only",
                "source_authority": "canonical_design_record",
            }
        ],
        "closeout_truth": closeout_truth,
        "projection_gaps": [
            _normalize_gap(raw, audience=audience_value)
            for raw in _sequence(projection.get("projection_gaps"))
            if isinstance(raw, Mapping)
        ],
        "omission_manifest": [
            _normalize_omission(raw, audience=audience_value)
            for raw in _sequence(projection.get("omission_manifest"))
            if isinstance(raw, Mapping)
        ],
        "contested_records": _contested_records(
            source_payload=projection,
            policy_design_case={},
            audience=audience_value,
            recourse_pointer=None,
        ),
        "recourse_pointer": None,
        "deficit_register": _s9_deficit_register(projection),
        "participation_requirements": [],
        "invariant_summary": {},
        "authority_role": "projection_only",
        "projection_policy": _LEGACY_PROJECTION_POLICY,
        "authoritative_for": [],
        "evidence_class": _text(projection.get("evidence_class")) or "redacted_derived",
        "provenance_kind": "runtime_projection",
        "redacted": audience_value is contracts.PolicyDesignCaseAudience.PUBLIC,
        "redaction_summary": _redaction_summary(projection, audience_value),
        "audit_refs": audit_refs,
        "source_authority_refs": {
            "canonical_design_record_ref": canonical_ref,
            "s9_faithfulness_ref": faithfulness_ref,
        },
        "source_state": {
            "projection_policy": _text(projection.get("projection_policy"))
            or "reads_canonical_design_record",
            "source_revision_ref": source_revision_ref,
            "canonical_design_record_ref": canonical_ref,
            "canonical_design_record_digest": _text(
                projection.get("canonical_design_record_digest")
                or faithfulness.get("canonical_design_record_digest")
            ),
        },
        "may_be_used_for": list(_MAY_BE_USED_FOR),
        "may_not_be_used_for": _unique_texts(
            [
                *_text_list(projection.get("may_not_be_used_for")),
                *_text_list(projection.get("may_not_use_for")),
                *list(_S9_REQUIRED_MAY_NOT_USE_FOR),
                "production_recommendation",
            ]
        ),
        "capability_reality_state": "implemented",
        "contract_verification_status": "not_verified",
        "contract_verification_refs": [_S9_CONSUMER_CONTRACT_REF],
    }


def _s9_closeout_truth(closeout_truth: Mapping[str, Any]) -> dict[str, Any]:
    blocker_codes = _text_list(closeout_truth.get("blocker_codes"))
    blockers = [
        {
            "code": code,
            "severity": "fail",
            "message": code,
        }
        for code in blocker_codes
    ]
    for raw in _sequence(closeout_truth.get("blockers")):
        if isinstance(raw, Mapping):
            code = _text(raw.get("code") or raw.get("issue_code"))
            if code:
                blockers.append(
                    {
                        "code": code,
                        "severity": _text(raw.get("severity")) or "fail",
                        "message": _text(raw.get("message")) or code,
                        "module_id": _text(raw.get("module_id")),
                        "owner": _text(raw.get("owner")),
                        "evidence_ref": _text(raw.get("evidence_ref")),
                        "next_action": _text(raw.get("next_action")),
                    }
                )
    return {
        "status": _text(closeout_truth.get("status")) or "not_provided",
        "verdict": _text(closeout_truth.get("verdict")) or "cannot_closeout",
        "can_closeout": bool(closeout_truth.get("can_closeout")),
        "blocker_codes": blocker_codes,
        "limitation_codes": _text_list(closeout_truth.get("limitation_codes")),
        "omission_codes": _text_list(closeout_truth.get("omission_codes")),
        "contested_state": _text(closeout_truth.get("contested_state"))
        or "not_contested",
        "blockers": blockers,
    }


def _s9_deficit_register(projection: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in _deficit_register(projection, {}):
        rows.append(
            {
                **row,
                "deficit_family": _text(row.get("deficit_family"))
                or "projection_faithfulness",
                "disposition": _text(row.get("disposition")) or "requires_review",
            }
        )
    return rows


def _s9_projection_issues(
    *,
    audience: str,
    projection: Mapping[str, Any],
    faithfulness: Mapping[str, Any],
    expected_deficit_codes: Sequence[str],
    expected_source_revision_ref: str | None,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for code in _s9_faithfulness_issue_codes(faithfulness):
        issues.append(
            _contract_issue(
                code,
                audience=audience,
                message=f"S9 projection faithfulness failed: {code}.",
            )
        )
    if _text(faithfulness.get("faithfulness_status")) != "pass" and not issues:
        issues.append(
            _contract_issue(
                "s9_projection_faithfulness_failed",
                audience=audience,
                message="S9 projection faithfulness status is not pass.",
            )
        )
    if _text(faithfulness.get("tradeoff_direction_status")) == "inverted":
        issues.append(
            _contract_issue(
                "s9_tradeoff_inversion",
                audience=audience,
                message="S9 projection inverted a value-tradeoff direction.",
            )
        )
    if _text(faithfulness.get("shadow_approval_status")) == "rendered_as_approved":
        issues.append(
            _contract_issue(
                "s9_shadow_candidate_rendered_as_approved",
                audience=audience,
                message="S9 projection rendered a shadow candidate as approved.",
            )
        )
    if _text_list(faithfulness.get("added_claim_refs")):
        issues.append(
            _contract_issue(
                "s9_projection_added_claim",
                audience=audience,
                message="S9 projection added claim refs absent from the canonical record.",
            )
        )
    hidden_blockers = _text_list(faithfulness.get("hidden_blocker_refs"))
    if hidden_blockers and not _sequence(projection.get("omission_manifest")):
        issues.append(
            _contract_issue(
                "s9_redaction_hides_blocker",
                audience=audience,
                message="S9 projection hid blocker refs without an omission manifest.",
            )
        )
    issues.extend(
        _s9_authority_issues(
            audience=audience,
            projection=projection,
            faithfulness=faithfulness,
        )
    )
    issues.extend(
        _s9_revision_issues(
            audience=audience,
            projection=projection,
            faithfulness=faithfulness,
            expected_source_revision_ref=expected_source_revision_ref,
        )
    )
    actual_deficit_codes = {
        _text(row.get("deficit_code") or row.get("code"))
        for row in _sequence(projection.get("deficit_register"))
        if isinstance(row, Mapping)
    }
    missing_deficit_codes = sorted(
        {_text(code) for code in expected_deficit_codes if _text(code)}
        - actual_deficit_codes
    )
    for code in missing_deficit_codes:
        issues.append(
            _contract_issue(
                "s9_projection_hides_deficit_record",
                audience=audience,
                message=f"S9 projection omitted deficit code {code}.",
            )
        )
    return _dedupe_contract_issues(issues)


def _s9_authority_issues(
    *,
    audience: str,
    projection: Mapping[str, Any],
    faithfulness: Mapping[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if _text(projection.get("authority_role")).casefold() not in {"", "projection_only"}:
        issues.append(
            _contract_issue(
                "s9_projection_mints_authority",
                audience=audience,
                message="S9 projection authority_role must remain projection_only.",
            )
        )
    if _sequence(projection.get("authoritative_for")):
        issues.append(
            _contract_issue(
                "s9_projection_mints_authority",
                audience=audience,
                message="S9 projection cannot satisfy authoritative_for slots.",
            )
        )
    may_not = {
        *_text_list(projection.get("may_not_be_used_for")),
        *_text_list(projection.get("may_not_use_for")),
    }
    boundary = _mapping(faithfulness.get("authority_boundary"))
    boundary_may_not = set(_text_list(boundary.get("may_not_use_for")))
    boundary_authoritative_for = set(_text_list(boundary.get("authoritative_for")))
    if not may_not >= _S9_REQUIRED_MAY_NOT_USE_FOR:
        issues.append(
            _contract_issue(
                "s9_projection_mints_authority",
                audience=audience,
                message="S9 projection omitted claim/scorecard/closeout use limits.",
            )
        )
    if not boundary_may_not >= _S9_AUTHORITY_BOUNDARY_REQUIRED_MAY_NOT_USE_FOR:
        issues.append(
            _contract_issue(
                "s9_projection_mints_authority",
                audience=audience,
                message="S9 faithfulness authority boundary omitted forbidden uses.",
            )
        )
    forbidden_authoritative_for = boundary_authoritative_for & {
        "claim_authority",
        "scorecard_authority",
        "runtime_closeout_authority",
        "approval_authority",
        "publication_authority",
    }
    if forbidden_authoritative_for:
        issues.append(
            _contract_issue(
                "s9_projection_mints_authority",
                audience=audience,
                message="S9 faithfulness boundary tried to fill authority slots.",
            )
        )
    return issues


def _s9_revision_issues(
    *,
    audience: str,
    projection: Mapping[str, Any],
    faithfulness: Mapping[str, Any],
    expected_source_revision_ref: str | None,
) -> list[dict[str, Any]]:
    expected = _text(expected_source_revision_ref)
    if not expected:
        return []
    actual = _text(
        projection.get("source_revision_ref") or faithfulness.get("source_revision_ref")
    )
    if actual == expected:
        return []
    has_reissue_route = any(
        _text(projection.get(key) or faithfulness.get(key))
        for key in ("reissue_ref", "reopen_ref")
    ) or bool(projection.get("s9_reissue_required"))
    if has_reissue_route:
        return []
    return [
        _contract_issue(
            "s9_projection_source_revision_mismatch",
            audience=audience,
            message="S9 projection source revision changed without reissue/reopen route.",
        )
    ]


def _s9_faithfulness_issue_codes(faithfulness: Mapping[str, Any]) -> list[str]:
    codes = _text_list(faithfulness.get("issue_codes"))
    if _text(faithfulness.get("faithfulness_status")) != "pass" and not codes:
        codes.append("s9_projection_faithfulness_failed")
    return codes


def _s9_faithfulness_record(projection: Mapping[str, Any]) -> dict[str, Any]:
    record = projection.get("s9_projection_faithfulness") or projection.get(
        "projection_faithfulness"
    )
    if record is None and "faithfulness_status" in projection:
        record = projection
    return _mapping_from_record(record)


def _mapping_from_record(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        if isinstance(dumped, Mapping):
            return dict(dumped)
    return {}


def _dedupe_contract_issues(issues: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for issue in issues:
        key = (_text(issue.get("audience")), _text(issue.get("code")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(issue))
    return deduped


def _source_authority_refs(authority_chain: Mapping[str, Any]) -> dict[str, str]:
    refs: dict[str, str] = {}
    for key in (
        "cas_ref",
        "runtime_event_ref",
        "same_input_closure_ref",
        "effective_mode_ref",
        "schema_compatibility_ref",
    ):
        value = _text(authority_chain.get(key))
        if value:
            out_key = "policy_design_case_ref" if key == "cas_ref" else key
            refs[out_key] = value
    return refs


def _audience(
    value: contracts.PolicyDesignCaseAudience | str | None,
    *,
    surface: str,
) -> contracts.PolicyDesignCaseAudience:
    if isinstance(value, contracts.PolicyDesignCaseAudience):
        return value
    text = _text(value).casefold()
    if text:
        try:
            return contracts.PolicyDesignCaseAudience(text)
        except ValueError:
            return contracts.PolicyDesignCaseAudience.MACHINE
    surface_name = _text(surface).casefold().replace("-", "_")
    if "public" in surface_name:
        return contracts.PolicyDesignCaseAudience.PUBLIC
    if "reviewer" in surface_name:
        return contracts.PolicyDesignCaseAudience.REVIEWER
    if "expert" in surface_name:
        return contracts.PolicyDesignCaseAudience.EXPERT
    return contracts.PolicyDesignCaseAudience.MACHINE


def _closeout_truth(
    closeout: Mapping[str, Any],
    *,
    contested: bool,
    recourse_gap: Mapping[str, Any] | None,
) -> dict[str, Any]:
    blockers = _closeout_blockers(closeout)
    if recourse_gap is not None:
        blockers.append(
            {
                "code": _text(recourse_gap.get("gap_code")),
                "severity": _text(recourse_gap.get("severity")) or "fail",
                "message": _text(recourse_gap.get("message")),
                "module_id": "contestability",
                "owner": _text(recourse_gap.get("owner")),
                "evidence_ref": _text(recourse_gap.get("evidence_ref")),
                "next_action": _text(recourse_gap.get("next_action")),
            }
        )
    blocker_codes = _unique_texts(blocker.get("code") for blocker in blockers)
    closeout_limitations = _closeout_limitations(closeout)
    limitation_codes = _unique_texts(
        [
            *_issue_codes(closeout, severities={"warning", "limited", "limitation"}),
            *(row["code"] for row in closeout_limitations),
        ]
    )
    omission_codes = _issue_codes(
        closeout,
        severities={"incomplete", "missing", "omission", "omitted"},
    )
    status = _text(closeout.get("status")) or ("blocked" if blockers else "not_provided")
    can_closeout = bool(closeout.get("can_closeout")) if closeout else False
    if blockers:
        status = "blocked"
        can_closeout = False
    return {
        "status": status,
        "verdict": _text(closeout.get("verdict"))
        or ("can_closeout" if can_closeout else "cannot_closeout"),
        "can_closeout": can_closeout,
        "blocker_codes": blocker_codes,
        "limitation_codes": limitation_codes,
        "omission_codes": omission_codes,
        "contested_state": "contested" if contested else "not_contested",
        "blockers": blockers,
    }


def _closeout_blockers(closeout: Mapping[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for issue in _sequence(closeout.get("issues")):
        if not isinstance(issue, Mapping):
            continue
        severity = _text(issue.get("severity")).casefold()
        code = _text(issue.get("code") or issue.get("issue_code"))
        if severity not in {"fail", "error", "critical", "blocked", "hard_block"}:
            continue
        if not code:
            continue
        blockers.append(
            {
                "code": code,
                "severity": severity or "fail",
                "message": _text(issue.get("message")) or code,
                "module_id": _text(issue.get("module_id")),
                "owner": _text(issue.get("owner")),
                "evidence_ref": _text(issue.get("evidence_ref")),
                "next_action": _text(issue.get("next_action")),
            }
        )
    for key in ("blockers", "blocking_findings"):
        for blocker in _sequence(closeout.get(key)):
            if not isinstance(blocker, Mapping):
                continue
            code = _text(blocker.get("code") or blocker.get("issue_code"))
            if code:
                blockers.append(
                    {
                        "code": code,
                        "severity": _text(blocker.get("severity")) or "fail",
                        "message": _text(blocker.get("message")) or code,
                        "module_id": _text(blocker.get("module_id")),
                        "owner": _text(blocker.get("owner")),
                        "evidence_ref": _text(blocker.get("evidence_ref")),
                        "next_action": _text(blocker.get("next_action")),
                    }
                )
    return blockers


def _issue_codes(closeout: Mapping[str, Any], *, severities: set[str]) -> list[str]:
    codes: list[str] = []
    for issue in _sequence(closeout.get("issues")):
        if not isinstance(issue, Mapping):
            continue
        severity = _text(issue.get("severity")).casefold()
        code = _text(issue.get("code") or issue.get("issue_code"))
        if code and severity in severities and code not in codes:
            codes.append(code)
    return codes


def _closeout_issues(
    closeout: Mapping[str, Any],
    *,
    severities: set[str],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for issue in _sequence(closeout.get("issues")):
        if not isinstance(issue, Mapping):
            continue
        severity = _text(issue.get("severity")).casefold()
        code = _text(issue.get("code") or issue.get("issue_code"))
        if code and severity in severities:
            issues.append(dict(issue))
    return issues


def _recourse_projection(
    *,
    policy_design_case: Mapping[str, Any],
    source_payload: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    try:
        pointer = verified_recourse_pointer_for_publication(
            policy_design_case=policy_design_case,
            projection_payload=source_payload,
        )
    except PolicyDesignContestabilityError as exc:
        return None, _gap(
            gap_code=exc.code,
            gap_family="contestability",
            severity="fail",
            message=str(exc.message),
            source="runtime.quality.contestability",
            owner="team-policyos-runtime",
            next_action=(
                "Attach a deterministic or governed verified-reachable recourse pointer "
                "before high-stakes contested production publication."
            ),
            publication_effect="publication_blocked",
            closeout_effect="closeout_blocked",
        )
    if pointer is None:
        return None, None
    return dict(pointer), None


def _projection_gaps(
    *,
    closeout_truth: Mapping[str, Any],
    closeout_verdict: Mapping[str, Any],
    source_payload: Mapping[str, Any],
    recourse_gap: Mapping[str, Any] | None,
    audience: contracts.PolicyDesignCaseAudience,
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    if recourse_gap is not None:
        gaps.append(dict(recourse_gap))
    for blocker in _sequence(closeout_truth.get("blockers")):
        if not isinstance(blocker, Mapping):
            continue
        gaps.append(
            _gap(
                gap_code=_text(blocker.get("code")) or "closeout_blocker",
                gap_family="closeout",
                severity=_text(blocker.get("severity")) or "fail",
                message=_text(blocker.get("message")) or "Closeout blocker is present.",
                source=_text(blocker.get("module_id")) or "closeout_reader",
                owner=_text(blocker.get("owner")),
                evidence_ref=_text(blocker.get("evidence_ref")),
                next_action=_text(blocker.get("next_action")),
                publication_effect="publication_blocked",
                closeout_effect="closeout_blocked",
            )
        )
    for issue in _closeout_issues(
        closeout_verdict,
        severities={"limited", "limitation", "warning"},
    ):
        gaps.append(
            _gap(
                gap_code=_text(issue.get("code") or issue.get("issue_code"))
                or "closeout_limitation",
                gap_family="limitation",
                severity=_text(issue.get("severity")) or "limitation",
                message=_text(issue.get("message")) or "Closeout limitation is present.",
                source=_text(issue.get("module_id")) or "closeout_reader",
                owner=_text(issue.get("owner")),
                evidence_ref=_text(issue.get("evidence_ref")),
                next_action=_text(issue.get("next_action")),
                claim_ids=_text_list(issue.get("claim_ids") or issue.get("claim_refs")),
                publication_effect="publish_with_limitation",
                closeout_effect="limited_closeout",
            )
        )
    for limitation in _closeout_limitations(closeout_verdict):
        gaps.append(
            _gap(
                gap_code=limitation["code"],
                gap_family="limitation",
                severity="limitation",
                message=limitation["message"],
                source=limitation["source"],
                owner=limitation["owner"],
                evidence_ref=limitation["evidence_ref"],
                claim_ids=limitation["claim_ids"],
                publication_effect="publish_with_limitation",
                closeout_effect="limited_closeout",
            )
        )
    for issue in _closeout_issues(
        closeout_verdict,
        severities={"incomplete", "missing", "omission", "omitted"},
    ):
        gaps.append(
            _gap(
                gap_code=_text(issue.get("code") or issue.get("issue_code"))
                or "closeout_omission",
                gap_family="omission",
                severity=_text(issue.get("severity")) or "omission",
                message=_text(issue.get("message")) or "Closeout omission is present.",
                source=_text(issue.get("module_id")) or "closeout_reader",
                owner=_text(issue.get("owner")),
                evidence_ref=_text(issue.get("evidence_ref")),
                next_action=_text(issue.get("next_action")),
                claim_ids=_text_list(issue.get("claim_ids") or issue.get("claim_refs")),
                publication_effect="omission_manifest_required",
                closeout_effect="limited_closeout",
            )
        )
    for raw_gap in _sequence(source_payload.get("projection_gaps")):
        if isinstance(raw_gap, Mapping):
            gaps.append(_normalize_gap(raw_gap, audience=audience))
    return _dedupe_gaps(gaps)


def _closeout_limitations(closeout: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for limitation in _sequence(closeout.get("limitations")):
        if not isinstance(limitation, Mapping):
            continue
        code = _text(
            limitation.get("limitation_id")
            or limitation.get("deficit_id")
            or limitation.get("code")
        )
        if not code:
            continue
        claim_ids = _text_list(limitation.get("claim_ids") or limitation.get("claim_refs"))
        claim_id = _text(limitation.get("claim_id"))
        if claim_id and claim_id not in claim_ids:
            claim_ids.append(claim_id)
        rows.append(
            {
                "code": code,
                "message": _text(limitation.get("message")) or code,
                "owner": _text(limitation.get("owner")),
                "evidence_ref": _text(limitation.get("evidence_ref")),
                "claim_ids": claim_ids,
                "source": _text(limitation.get("source_module_id"))
                or _text(limitation.get("module_id"))
                or "closeout_reader",
            }
        )
    return rows


def _gap(
    *,
    gap_code: str,
    gap_family: str,
    severity: str,
    message: str,
    source: str | None = None,
    owner: str | None = None,
    evidence_ref: str | None = None,
    next_action: str | None = None,
    claim_ids: Sequence[str] = (),
    publication_effect: str = "unaffected",
    closeout_effect: str = "limited_closeout",
) -> dict[str, Any]:
    code = _text(gap_code) or "policy_design_projection_gap"
    return {
        "gap_id": f"gap:{code}",
        "gap_code": code,
        "gap_family": _text(gap_family) or "projection",
        "severity": _text(severity) or "warning",
        "message": _text(message) or code,
        "audience_visibility": [audience.value for audience in contracts.PolicyDesignCaseAudience],
        "claim_ids": list(claim_ids),
        "source": _text(source),
        "owner": _text(owner),
        "evidence_ref": _text(evidence_ref),
        "next_action": _text(next_action),
        "publication_effect": publication_effect,
        "closeout_effect": closeout_effect,
    }


def _normalize_gap(
    raw_gap: Mapping[str, Any],
    *,
    audience: contracts.PolicyDesignCaseAudience,
) -> dict[str, Any]:
    visibility = _audience_visibility(
        raw_gap.get("audience_visibility") or raw_gap.get("audiences")
    )
    if not visibility:
        visibility = (audience,)
    code = _text(raw_gap.get("gap_code") or raw_gap.get("code")) or "projection_gap"
    return {
        "gap_id": _text(raw_gap.get("gap_id")) or f"gap:{code}",
        "gap_code": code,
        "gap_family": _text(raw_gap.get("gap_family") or raw_gap.get("family")) or "projection",
        "severity": _text(raw_gap.get("severity")) or "warning",
        "message": _text(raw_gap.get("message")) or code,
        "audience_visibility": [item.value for item in visibility],
        "claim_ids": _text_list(raw_gap.get("claim_ids") or raw_gap.get("claim_refs")),
        "source": _text(raw_gap.get("source")),
        "owner": _text(raw_gap.get("owner")),
        "evidence_ref": _text(raw_gap.get("evidence_ref")),
        "next_action": _text(raw_gap.get("next_action")),
        "publication_effect": _text(raw_gap.get("publication_effect")) or "unaffected",
        "closeout_effect": _text(raw_gap.get("closeout_effect")) or "limited_closeout",
    }


def _dedupe_gaps(gaps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for gap in gaps:
        key = (_text(gap.get("gap_code")), _text(gap.get("gap_family")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(gap))
    return deduped


def _omission_manifest(
    *,
    closeout_verdict: Mapping[str, Any],
    source_payload: Mapping[str, Any],
    audience: contracts.PolicyDesignCaseAudience,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for issue in _closeout_issues(
        closeout_verdict,
        severities={"incomplete", "missing", "omission", "omitted"},
    ):
        rows.append(_normalize_omission(issue, audience=audience))
    for raw in (
        *_sequence(source_payload.get("omission_manifest")),
        *_sequence(source_payload.get("omissions")),
    ):
        if isinstance(raw, Mapping):
            rows.append(_normalize_omission(raw, audience=audience))
    return _dedupe_omissions(rows)


def _normalize_omission(
    raw: Mapping[str, Any],
    *,
    audience: contracts.PolicyDesignCaseAudience,
) -> dict[str, Any]:
    visibility = _audience_visibility(raw.get("audience_visibility") or raw.get("audiences"))
    if not visibility:
        visibility = (audience,)
    code = _text(raw.get("omission_code") or raw.get("code") or raw.get("issue_code"))
    if not code:
        code = "projection_omission"
    return {
        "omission_id": _text(raw.get("omission_id")) or f"omission:{code}",
        "omission_code": code,
        "omission_family": _text(raw.get("omission_family") or raw.get("family"))
        or "projection",
        "reason": _text(raw.get("reason") or raw.get("message")) or code,
        "audience_visibility": [item.value for item in visibility],
        "claim_ids": _text_list(raw.get("claim_ids") or raw.get("claim_refs")),
        "source": _text(raw.get("source") or raw.get("module_id")),
        "owner": _text(raw.get("owner")),
        "evidence_ref": _text(raw.get("evidence_ref")),
        "manifest_ref": _text(raw.get("manifest_ref")),
        "publication_effect": _text(raw.get("publication_effect"))
        or "omission_manifest_required",
        "closeout_effect": _text(raw.get("closeout_effect")) or "limited_closeout",
    }


def _dedupe_omissions(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for row in rows:
        key = (_text(row.get("omission_code")), tuple(_text_list(row.get("claim_ids"))))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(row))
    return deduped


def _contested_records(
    *,
    source_payload: Mapping[str, Any],
    policy_design_case: Mapping[str, Any],
    audience: contracts.PolicyDesignCaseAudience,
    recourse_pointer: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for raw in (
        *_sequence(policy_design_case.get("contested_records")),
        *_sequence(source_payload.get("contested_records")),
    ):
        if not isinstance(raw, Mapping):
            continue
        visibility = _audience_visibility(raw.get("audience_visibility") or raw.get("audiences"))
        if visibility and audience not in visibility:
            continue
        record = {
            "contested_record_id": _text(raw.get("contested_record_id") or raw.get("id")),
            "case_ref": _text(raw.get("case_ref"))
            or _text(policy_design_case.get("case_id"))
            or "policy_design_case",
            "claim_refs": _text_list(raw.get("claim_refs") or raw.get("claim_ids")),
            "audience_visibility": [item.value for item in visibility]
            or [item.value for item in contracts.PolicyDesignCaseAudience],
            "contestability_status": _text(raw.get("contestability_status") or raw.get("status"))
            or "contested",
            "grounds": _text_list(raw.get("grounds")),
            "standing_or_actor_ref": _text(raw.get("standing_or_actor_ref")),
            "counterevidence_refs": _text_list(raw.get("counterevidence_refs")),
            "source_truth_conflict_refs": _text_list(raw.get("source_truth_conflict_refs")),
            "authority_profile": _text(raw.get("authority_profile"))
            or _text(policy_design_case.get("effective_execution_profile"))
            or "unknown",
            "publication_effect": _text(raw.get("publication_effect"))
            or "review_before_publication",
            "reopening_trigger_refs": _text_list(raw.get("reopening_trigger_refs")),
            "lifecycle_event_refs": _text_list(raw.get("lifecycle_event_refs")),
            "recourse_pointer": raw.get("recourse_pointer")
            if isinstance(raw.get("recourse_pointer"), Mapping)
            else None,
            "recourse_outcome_refs": _text_list(raw.get("recourse_outcome_refs")),
            "ingestion_event_refs": _text_list(raw.get("ingestion_event_refs")),
            "public_projection_effect": _text(raw.get("public_projection_effect"))
            or "show_contested_state",
        }
        if record["recourse_pointer"] is None and recourse_pointer is not None:
            record["recourse_pointer"] = dict(recourse_pointer)
        if record["contested_record_id"]:
            records.append(record)
    return records


def _deficit_register(
    source_payload: Mapping[str, Any],
    policy_design_case: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in (
        *_sequence(policy_design_case.get("deficit_register")),
        *_sequence(source_payload.get("deficit_register")),
        *_sequence(source_payload.get("deficits")),
    ):
        if not isinstance(raw, Mapping):
            continue
        rows.append(
            {
                "deficit_id": _text(raw.get("deficit_id") or raw.get("id")),
                "deficit_family": _text(raw.get("deficit_family") or raw.get("family")),
                "deficit_code": _text(raw.get("deficit_code") or raw.get("code")),
                "claim_ids": _text_list(raw.get("claim_ids") or raw.get("claim_refs")),
                "authority_level": _text(raw.get("authority_level")) or "unknown",
                "audience_scope": _text(raw.get("audience_scope")) or "machine",
                "disposition": _text(raw.get("disposition") or raw.get("decision")),
                "owner": _text(raw.get("owner")) or "team-policyos-runtime",
                "ttl_expires_at": raw.get("ttl_expires_at") or raw.get("expires_at"),
                "runtime_event_ref": _text(raw.get("runtime_event_ref"))
                or "event://policy-design-case/deficit",
                "evidence_ref": _text(raw.get("evidence_ref")) or "policy_design_case:deficit",
                "support_cap": _text(raw.get("support_cap")),
                "readiness_cap": _text(raw.get("readiness_cap")),
                "max_audience": _text(raw.get("max_audience")),
                "public_limitation_note": _text(raw.get("public_limitation_note")),
                "review_refs": _text_list(raw.get("review_refs")),
            }
        )
    return rows


def _participation_surface(
    *,
    source_payload: Mapping[str, Any],
    policy_design_case: Mapping[str, Any],
    audience: contracts.PolicyDesignCaseAudience,
) -> dict[str, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    deficits: list[dict[str, Any]] = []
    contested_records: list[dict[str, Any]] = []
    for evaluation in _participation_evaluations(source_payload, policy_design_case):
        row_records = _sequence(evaluation.get("public_projection_rows"))
        if not row_records:
            row_records = (evaluation,)
        for raw_row in row_records:
            if not isinstance(raw_row, Mapping):
                continue
            row = _normalize_participation_row(
                raw_row,
                evaluation=evaluation,
                audience=audience,
            )
            rows.append(row)
            code = row.get("blocker_code") or row.get("downgrade_reason")
            if code:
                status = _text(evaluation.get("status"))
                gaps.append(
                    _gap(
                        gap_code=_text(code),
                        gap_family="participation",
                        severity="fail" if status in {"blocked", "missing"} else "limitation",
                        message=(
                            "Participation provenance cannot support the requested "
                            f"{row['claim_use_requested']} claim use; allowed use is "
                            f"{row['claim_use_allowed']}."
                        ),
                        source="participation_requirement",
                        owner="team-participation",
                        evidence_ref=_text(row.get("evidence_ref")),
                        next_action=(
                            "Acquire scope-matched participation provenance or publish "
                            "only the downgraded claim use with a visible limitation."
                        ),
                        claim_ids=[_text(row.get("claim_id"))],
                        publication_effect="publish_with_limitation"
                        if status == "downgraded"
                        else "publication_blocked_for_affected_claim",
                        closeout_effect=_text(evaluation.get("case_closeout_effect"))
                        or "limited_closeout",
                    )
                )
        for raw_deficit in _sequence(evaluation.get("deficit_records")):
            if isinstance(raw_deficit, Mapping):
                deficits.append(_normalize_participation_deficit(raw_deficit))
        for raw_contested in _sequence(evaluation.get("contested_records")):
            if isinstance(raw_contested, Mapping):
                contested_records.append(dict(raw_contested))
    return {
        "rows": _dedupe_participation_rows(rows),
        "projection_gaps": _dedupe_gaps(gaps),
        "deficit_register": deficits,
        "contested_records": contested_records,
    }


def _participation_evaluations(
    source_payload: Mapping[str, Any],
    policy_design_case: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for owner in (policy_design_case, source_payload):
        for key in (
            "participation_requirement_evaluations",
            "participation_evaluations",
            "participation_requirements",
        ):
            for item in _sequence(owner.get(key)):
                if isinstance(item, Mapping):
                    rows.append(item)
    return rows


def _normalize_participation_row(
    raw_row: Mapping[str, Any],
    *,
    evaluation: Mapping[str, Any],
    audience: contracts.PolicyDesignCaseAudience,
) -> dict[str, Any]:
    visibility = _audience_visibility(
        raw_row.get("audience_visibility") or raw_row.get("audiences")
    )
    if not visibility:
        visibility = tuple(contracts.PolicyDesignCaseAudience)
    requirement_id = _text(raw_row.get("requirement_id") or evaluation.get("requirement_id"))
    claim_id = _text(raw_row.get("claim_id") or evaluation.get("claim_id"))
    return {
        "requirement_id": requirement_id or "participation_requirement",
        "claim_id": claim_id or "claim",
        "participation_ref": _text(
            raw_row.get("participation_ref") or evaluation.get("participation_ref")
        ),
        "claim_use_requested": _text(
            raw_row.get("claim_use_requested") or evaluation.get("claim_use_requested")
        )
        or "context-only",
        "claim_use_allowed": _text(
            raw_row.get("claim_use_allowed") or evaluation.get("claim_use_allowed")
        )
        or "context-only",
        "source_kind": _text(raw_row.get("source_kind")) or "unknown",
        "consultation_mode": _text(raw_row.get("consultation_mode")),
        "provenance_class": _text(raw_row.get("provenance_class")) or "unknown",
        "representativeness_class": _text(raw_row.get("representativeness_class"))
        or "unknown",
        "public_projection_effect": _text(raw_row.get("public_projection_effect"))
        or _text(evaluation.get("case_closeout_effect"))
        or "show_participation_status",
        "downgrade_reason": _text(
            raw_row.get("downgrade_reason") or evaluation.get("downgrade_reason")
        ),
        "blocker_code": _text(raw_row.get("blocker_code") or evaluation.get("blocker_code")),
        "limitations": _text_list(raw_row.get("limitations")),
        "privacy_constraints": _text_list(raw_row.get("privacy_constraints")),
        "raw_materials_redacted": True,
        "evidence_ref": _text(raw_row.get("evidence_ref")),
        "audience_visibility": [item.value for item in visibility if audience in visibility]
        or [audience.value],
    }


def _normalize_participation_deficit(raw: Mapping[str, Any]) -> dict[str, Any]:
    code = _text(raw.get("deficit_code") or raw.get("code")) or "participation_deficit"
    return {
        "deficit_id": _text(raw.get("deficit_id") or raw.get("id")) or f"deficit:{code}",
        "deficit_family": "participation",
        "deficit_code": code,
        "claim_ids": _text_list(raw.get("claim_ids") or raw.get("claim_refs")),
        "authority_level": _text(raw.get("authority_level")) or "unknown",
        "audience_scope": _text(raw.get("audience_scope")) or "public",
        "disposition": _text(raw.get("disposition") or raw.get("decision"))
        or "publish_with_limitation",
        "owner": _text(raw.get("owner")) or "team-participation",
        "ttl_expires_at": raw.get("ttl_expires_at") or raw.get("expires_at"),
        "runtime_event_ref": _text(raw.get("runtime_event_ref"))
        or "event://participation_requirement/deficit",
        "evidence_ref": _text(raw.get("evidence_ref")) or "participation_requirement:deficit",
        "support_cap": _text(raw.get("support_cap")),
        "readiness_cap": _text(raw.get("readiness_cap")),
        "max_audience": _text(raw.get("max_audience")),
        "public_limitation_note": _text(raw.get("public_limitation_note")),
        "review_refs": _text_list(raw.get("review_refs")),
    }


def _dedupe_participation_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (_text(row.get("requirement_id")), _text(row.get("claim_id")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(row))
    return deduped


def _invariant_summary(
    source_payload: Mapping[str, Any],
    policy_design_case: Mapping[str, Any],
) -> dict[str, Any]:
    raw = _mapping(source_payload.get("invariant_summary")) or _mapping(
        policy_design_case.get("invariant_summary")
    )
    if not raw:
        return {
            "status": "not_provided",
            "passing_count": 0,
            "failing_count": 0,
            "blocker_codes": [],
            "evidence_refs": [],
            "details": {},
        }
    return {
        "status": _text(raw.get("status")) or "not_provided",
        "passing_count": _int(raw.get("passing_count")),
        "failing_count": _int(raw.get("failing_count")),
        "blocker_codes": _text_list(raw.get("blocker_codes")),
        "evidence_refs": _text_list(raw.get("evidence_refs")),
        "details": _mapping(raw.get("details")),
    }


def _redaction_summary(
    source_payload: Mapping[str, Any],
    audience: contracts.PolicyDesignCaseAudience,
) -> dict[str, Any]:
    summary = _mapping(source_payload.get("redaction_summary"))
    if audience == contracts.PolicyDesignCaseAudience.PUBLIC:
        return {
            **summary,
            "audience": audience.value,
            "redacted_for_public": True,
            "redaction_policy": "policy_design_case.public_projection.v1",
        }
    return {
        **summary,
        "audience": audience.value,
        "redacted_for_public": False,
    }


def _audit_refs(
    source_payload: Mapping[str, Any],
    policy_design_case: Mapping[str, Any],
    authority_chain: Mapping[str, Any],
) -> list[str]:
    refs: list[str] = []
    for key in (
        "audit_refs",
        "audit_ref",
        "external_audit_refs",
        "public_audit_refs",
        "verification_refs",
    ):
        value = source_payload.get(key)
        if isinstance(value, str):
            refs.append(value)
        else:
            refs.extend(_text_list(value))
    refs.extend(_text_list(policy_design_case.get("audit_refs")))
    for key in ("runtime_event_ref", "same_input_closure_ref", "schema_compatibility_ref"):
        value = _text(authority_chain.get(key))
        if value:
            refs.append(value)
    return _unique_texts(refs)


def _contract_issue(code: str, *, audience: str, message: str) -> dict[str, Any]:
    return {
        "code": code,
        "audience": audience,
        "message": message,
        "owner": "team-policyos-runtime",
        "next_action": "Expose the same closeout truth, blockers, omissions, and contested state.",
    }


def _primary_state(states: Sequence[str]) -> str:
    state_set = set(states)
    for state in _PRIMARY_STATE_ORDER:
        if state in state_set:
            return state
    return "projection_only"


def _state_label(state: str) -> str:
    if state == "projection_only":
        return "projection only"
    return state.replace("_", " ")


def _is_publishable(payload: Mapping[str, Any]) -> bool:
    publishability = _text(payload.get("publishability")).casefold()
    export_status = _nested_text(payload, ("decision_context", "public_export_status")).casefold()
    return publishability == "publishable" or export_status == "publishable"


def _is_draft(payload: Mapping[str, Any]) -> bool:
    kind = _text(payload.get("artifact_kind")).casefold()
    publishability = _text(payload.get("publishability")).casefold()
    export_status = _nested_text(payload, ("decision_context", "public_export_status")).casefold()
    return (
        kind == "draft_decision_packet"
        or publishability in {"draft", "not_publishable"}
        or export_status in {"draft", "draft_projection"}
    )


def _is_redacted(payload: Mapping[str, Any]) -> bool:
    return (
        _text(payload.get("evidence_class")).casefold() == "redacted_derived"
        or _text(payload.get("public_export_classification")).casefold()
        == "public_redacted_projection"
        or isinstance(payload.get("redaction_summary"), Mapping)
    )


def _is_blocked(payload: Mapping[str, Any]) -> bool:
    status_values = [
        _text(payload.get("status")),
        _text(payload.get("quality_status")),
        _text(payload.get("approval_state")),
        _text(payload.get("publishability")),
        _nested_text(payload, ("decision_context", "public_export_status")),
    ]
    if any(
        value.casefold() in {"blocked", "fail", "failed", "quality_failed"}
        for value in status_values
    ):
        return True
    for key in (
        "blockers",
        "blocking_quality_failures",
        "compiler_issues",
        "source_truth_conflicts",
    ):
        if _sequence(payload.get(key)):
            return True
    return False


def _is_contested(payload: Mapping[str, Any]) -> bool:
    status_values = [
        _text(payload.get("contestability_status")),
        _text(payload.get("challenge_status")),
        _text(payload.get("dispute_status")),
        _text(payload.get("status")),
    ]
    if any(value.casefold() in {"contested", "conflict", "disputed"} for value in status_values):
        return True
    for key in (
        "source_truth_conflicts",
        "counter_evidence",
        "counter_evidence_nodes",
        "rebuttals",
    ):
        if _sequence(payload.get(key)):
            return True
    return any(
        isinstance(node, Mapping)
        and _text(node.get("status")).casefold() in {"contested", "conflict", "disputed"}
        for node in _sequence(payload.get("nodes"))
    )


def _is_stale(payload: Mapping[str, Any]) -> bool:
    status_values = [
        _text(payload.get("freshness_status")),
        _text(payload.get("decision_validity_status")),
        _text(payload.get("schema_compatibility_status")),
        _text(payload.get("status")),
    ]
    return any("stale" in value.casefold() for value in status_values)


def _audience_visibility(value: object) -> tuple[contracts.PolicyDesignCaseAudience, ...]:
    audiences: list[contracts.PolicyDesignCaseAudience] = []
    for item in _sequence(value):
        text = _text(item).casefold()
        try:
            audience = contracts.PolicyDesignCaseAudience(text)
        except ValueError:
            continue
        if audience not in audiences:
            audiences.append(audience)
    return tuple(audiences)


def _text_list(value: object) -> list[str]:
    return _unique_texts(_sequence(value))


def _unique_texts(values: Iterable[object]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = _text(value)
        if text and text not in result:
            result.append(text)
    return result


def _int(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _nested_text(payload: Mapping[str, Any], path: Sequence[str]) -> str:
    value: Any = payload
    for key in path:
        if not isinstance(value, Mapping):
            return ""
        value = value.get(key)
    return _text(value)


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: object) -> Sequence[object]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return ()


def _text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC).replace(microsecond=0)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC, microsecond=0)
    return value.astimezone(UTC).replace(microsecond=0)


def _fingerprint(value: object) -> str:
    return "sha256:" + hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


__all__ = [
    "POLICY_DESIGN_CASE_PROJECTION_SCHEMA_VERSION",
    "PROJECTION_STATES",
    "PolicyDesignCaseProjectionError",
    "assert_policy_design_projection_not_authority",
    "build_policy_design_case_projection_from_runtime_graph",
    "build_policy_design_case_projection_semantics",
    "verify_s9_projection_faithfulness_for_pdc_consumer_contract",
    "verify_s10_forecast_projection_consumer_contract",
    "verify_s11_predictive_projection_consumer_contract",
    "verify_s12_resource_projection_consumer_contract",
]
