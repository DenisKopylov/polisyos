"""Capability reality debt algebra for Policy Design Case readiness."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Any

CAPABILITY_RATCHET_SCHEMA_VERSION = "policyos.runtime.policy_design_case.capability_ratchet.v1"
CAPABILITY_RATCHET_CONTRACT_ID = "policy_design_case.capability_ratchet.v1"
CAPABILITY_RATCHET_TOOL_NAME = "runtime.quality.capability-ratchet"

IMPLEMENTED_STATE = "implemented"
REALITY_STATES = (
    IMPLEMENTED_STATE,
    "surface_out_of_scope",
    "contract_only",
    "consumer_missing",
    "surface_missing",
    "producer_missing",
    "artifact_missing",
    "bridge_missing",
    "implemented_but_not_orchestrated",
    "verification_missing",
    "semantic_test_missing",
)
MISSING_REALITY_STATES = tuple(state for state in REALITY_STATES if state != IMPLEMENTED_STATE)
REALITY_STATE_BASE_POINTS: Mapping[str, float] = {
    IMPLEMENTED_STATE: 0.0,
    "surface_out_of_scope": 0.0,
    "contract_only": 2.0,
    "consumer_missing": 2.0,
    "surface_missing": 2.0,
    "producer_missing": 3.0,
    "artifact_missing": 3.0,
    "bridge_missing": 4.0,
    "implemented_but_not_orchestrated": 4.0,
    "verification_missing": 5.0,
    "semantic_test_missing": 5.0,
}

PURPOSE_MULTIPLIERS: Mapping[str, float] = {
    "internal_helper": 0.5,
    "diagnostic_only": 0.75,
    "public_surface": 1.0,
    "lifecycle_trigger": 1.25,
    "evidence_producer": 1.5,
    "closeout_input": 1.75,
    "authority_gate": 2.0,
}

SERIOUS_PROFILES = frozenset({"research", "governed", "production"})
AUTHORITY_WEIGHTED_PURPOSES = frozenset(
    {"public_surface", "lifecycle_trigger", "evidence_producer", "closeout_input", "authority_gate"}
)
AUTHORITY_OR_CLOSEOUT_PURPOSES = frozenset({"authority_gate", "closeout_input"})
AUTHORITY_CHAIN_BLOCKER_STATES = frozenset(
    {
        "producer_missing",
        "artifact_missing",
        "bridge_missing",
        "verification_missing",
        "semantic_test_missing",
    }
)
CHAIN_FIELDS: tuple[tuple[str, str], ...] = (
    ("typed_contract_ref", "contract_only"),
    ("producer_ref", "contract_only"),
    ("artifact_ref", "artifact_missing"),
    ("bridge_ref", "bridge_missing"),
    ("consumer_ref", "consumer_missing"),
    ("verification_ref", "verification_missing"),
    ("surface_ref", "surface_missing"),
    ("semantic_test_ref", "semantic_test_missing"),
)
TRACEABILITY_FIELDS = (
    "research_refs",
    "decision_refs",
    "no_adr_required",
    "reuse_classification",
    "rejected_reuse_evidence",
    "rollout_refs",
)

BURN_DOWN_SIGNALS: Mapping[str, Mapping[str, str]] = {
    IMPLEMENTED_STATE: {
        "required_evidence": "none",
        "closure_move": "Preserve the evidence chain and prevent regression.",
    },
    "surface_out_of_scope": {
        "required_evidence": "surface_out_of_scope",
        "closure_move": "Keep owner, rationale, review date, and inspection path current.",
    },
    "contract_only": {
        "required_evidence": "producer_ref",
        "closure_move": "Add a real producer for the typed contract/artifact.",
    },
    "producer_missing": {
        "required_evidence": "producer_ref",
        "closure_move": "Deploy a producer that emits the expected event or artifact.",
    },
    "artifact_missing": {
        "required_evidence": "artifact_ref",
        "closure_move": "Persist a queryable and replayable runtime artifact or event.",
    },
    "bridge_missing": {
        "required_evidence": "bridge_ref",
        "closure_move": "Connect producer output to the runtime consumer path.",
    },
    "implemented_but_not_orchestrated": {
        "required_evidence": "bridge_ref",
        "closure_move": "Wire the locally working component into orchestration.",
    },
    "consumer_missing": {
        "required_evidence": "consumer_ref",
        "closure_move": "Add a downstream reader that acts on the artifact.",
    },
    "verification_missing": {
        "required_evidence": "verification_ref",
        "closure_move": "Add an automated end-to-end proof of the capability chain.",
    },
    "surface_missing": {
        "required_evidence": "surface_ref",
        "closure_move": "Expose an API, dashboard, audit, export, or valid out-of-scope surface.",
    },
    "semantic_test_missing": {
        "required_evidence": "semantic_test_ref",
        "closure_move": "Add content-level adequacy or authority-semantics tests.",
    },
}


def evaluate_capability_claim(
    claim: Mapping[str, Any],
    *,
    validation_profile: str | None = None,
    as_of: str | date | datetime | None = None,
    chain_cluster_premium: float = 0.0,
) -> dict[str, Any]:
    """Evaluate one capability claim against the C36 debt algebra.

    Args:
        claim: Capability claim row with reality state, purpose, ownership, and
            optional evidence-chain refs.
        validation_profile: Default validation profile when the claim does not
            declare one.
        as_of: Date used for expiry checks.
        chain_cluster_premium: Premium added by report aggregation when several
            debts sit in the same producer-consumer chain.

    Returns:
        A normalized claim row with debt points, severity, blockers, and issues.
    """

    row = dict(claim)
    issues: list[dict[str, Any]] = []
    capability_id = _required_text(row.get("capability_id"), "capability_id", issues)
    reported_state = _normalized_label(row.get("reality_state") or row.get("state"))
    inferred_state = infer_capability_reality_state(row)
    reality_state = reported_state or inferred_state
    if reality_state not in REALITY_STATE_BASE_POINTS:
        issues.append(
            _issue(
                "capability_reality_state_invalid",
                "reality_state",
                f"Unsupported capability reality state: {reality_state or '<missing>'}",
            )
        )
        reality_state = "contract_only"

    if reality_state == IMPLEMENTED_STATE and inferred_state != IMPLEMENTED_STATE:
        issues.append(
            _issue(
                "capability_implemented_chain_incomplete",
                "reality_state",
                "A capability cannot be implemented while a chain link is missing.",
                inferred_reality_state=inferred_state,
            )
        )
        reality_state = inferred_state

    purpose = _normalized_label(row.get("purpose")) or "internal_helper"
    if purpose not in PURPOSE_MULTIPLIERS:
        issues.append(
            _issue(
                "capability_purpose_invalid",
                "purpose",
                f"Unsupported capability purpose: {purpose}",
            )
        )
        purpose = "internal_helper"

    if reality_state == "surface_out_of_scope" and not _valid_surface_out_of_scope(row):
        issues.append(
            _issue(
                "surface_out_of_scope_governance_missing",
                "surface_out_of_scope",
                (
                    "surface_out_of_scope requires rationale, owner, review_date, "
                    "and inspection_path."
                ),
            )
        )
        reality_state = "surface_missing"

    profile = _normalized_label(row.get("validation_profile") or validation_profile) or "dev"
    serious_profile = profile in SERIOUS_PROFILES or bool(row.get("serious_profile"))
    owner = _text(row.get("owner"))
    expiry = _text(row.get("expiry") or row.get("review_date"))
    expired = _is_expired(expiry, as_of=as_of)
    ownerless_or_expired = reality_state != IMPLEMENTED_STATE and (
        not owner or expired
    )
    ownerless_or_expired_premium = 1.0 if ownerless_or_expired else 0.0
    serious_profile_premium = (
        1.0
        if serious_profile
        and reality_state not in {IMPLEMENTED_STATE, "surface_out_of_scope"}
        else 0.0
    )
    sole_authority_path = bool(
        row.get("sole_authority_path")
        or row.get("sole_path")
        or row.get("sole_inspection_path")
    )
    sole_path_premium = (
        1.0
        if sole_authority_path
        and reality_state not in {IMPLEMENTED_STATE, "surface_out_of_scope"}
        else 0.0
    )
    mitigation_credit = _mitigation_credit(row, reality_state=reality_state)
    base_points = REALITY_STATE_BASE_POINTS[reality_state]
    purpose_multiplier = PURPOSE_MULTIPLIERS[purpose]
    local_points = max(
        0.0,
        base_points * purpose_multiplier
        + serious_profile_premium
        + sole_path_premium
        + ownerless_or_expired_premium
        + chain_cluster_premium
        - mitigation_credit,
    )
    severity = severity_for_points(local_points)
    blocker_reasons = _blocker_reasons(
        reality_state=reality_state,
        purpose=purpose,
        serious_profile=serious_profile,
        sole_authority_path=sole_authority_path,
        promised_audiences=_sequence_of_text(row.get("promised_audiences")),
    )
    graduation_allowed = reality_state in {IMPLEMENTED_STATE, "surface_out_of_scope"}
    readiness_effect = "blocked" if blocker_reasons else (
        "ready" if severity in {"none", "low", "medium"} else "conditional"
    )
    if reality_state != IMPLEMENTED_STATE and not owner:
        issues.append(
            _issue(
                "capability_debt_owner_missing",
                "owner",
                "Open capability debt must have an owner.",
            )
        )
    if reality_state != IMPLEMENTED_STATE and not _text(row.get("hold_reason")):
        issues.append(
            _issue(
                "capability_debt_hold_reason_missing",
                "hold_reason",
                "Open capability debt must explain the hold reason.",
            )
        )
    if reality_state != IMPLEMENTED_STATE and not _text(row.get("next_wave_target")):
        issues.append(
            _issue(
                "capability_debt_next_wave_target_missing",
                "next_wave_target",
                "Open capability debt must name the next wave or phase target.",
            )
        )

    return {
        "capability_id": capability_id,
        "capability_name": _text(row.get("capability_name") or row.get("title")),
        "reported_reality_state": reported_state or reality_state,
        "reality_state": reality_state,
        "purpose": purpose,
        "authority_scope": _text(row.get("authority_scope")) or purpose,
        "validation_profile": profile,
        "chain_id": _text(row.get("chain_id")),
        "owner": owner,
        "expiry": expiry,
        "hold_reason": _text(row.get("hold_reason")),
        "next_wave_target": _text(row.get("next_wave_target")),
        "base_points": base_points,
        "purpose_multiplier": purpose_multiplier,
        "serious_profile_premium": serious_profile_premium,
        "sole_path_premium": sole_path_premium,
        "ownerless_or_expired_premium": ownerless_or_expired_premium,
        "chain_cluster_premium": chain_cluster_premium,
        "mitigation_credit": mitigation_credit,
        "local_points": round(local_points, 3),
        "local_severity": severity,
        "authority_weighted": _authority_weighted(row, purpose=purpose),
        "release_blocker": bool(blocker_reasons),
        "blocker_reasons": blocker_reasons,
        "graduation_allowed": graduation_allowed,
        "readiness_effect": readiness_effect,
        "burn_down_signal": dict(BURN_DOWN_SIGNALS[reality_state]),
        "evidence_refs": _evidence_refs(row),
        "traceability": _traceability(row),
        "surface_out_of_scope": _surface_out_of_scope(row),
        "issues": issues,
    }


def infer_capability_reality_state(claim: Mapping[str, Any]) -> str:
    """Infer the first missing capability-chain state from evidence refs."""

    if _normalized_label(claim.get("reality_state") or claim.get("state")) not in {
        "",
        IMPLEMENTED_STATE,
    }:
        return str(_normalized_label(claim.get("reality_state") or claim.get("state")))

    if _valid_surface_out_of_scope(claim):
        surface_ref_present = True
    else:
        surface_ref_present = _has_text(claim.get("surface_ref"))

    for field, missing_state in CHAIN_FIELDS:
        if field == "surface_ref":
            if surface_ref_present:
                continue
            return missing_state
        if not _has_text(claim.get(field)):
            return missing_state
    return IMPLEMENTED_STATE


def build_capability_reality_report(
    claims: Iterable[Mapping[str, Any]],
    *,
    validation_profile: str = "production",
    generated_at: str = "2026-05-22T00:00:00Z",
    as_of: str | date | datetime | None = None,
) -> dict[str, Any]:
    """Build the capability reality report used by W1.A and later waves."""

    claim_rows = [dict(claim) for claim in claims]
    base_records = [
        evaluate_capability_claim(
            claim,
            validation_profile=validation_profile,
            as_of=as_of,
        )
        for claim in claim_rows
    ]
    cluster_premiums, chain_clusters = _cluster_premiums(base_records)
    records = [
        (
            evaluate_capability_claim(
                claim,
                validation_profile=validation_profile,
                as_of=as_of,
                chain_cluster_premium=cluster_premiums.get(_text(claim.get("capability_id")), 0.0),
            )
            if cluster_premiums.get(_text(claim.get("capability_id")), 0.0)
            else record
        )
        for claim, record in zip(claim_rows, base_records, strict=True)
    ]
    state_counts = Counter(record["reality_state"] for record in records)
    for state in REALITY_STATES:
        state_counts.setdefault(state, 0)
    blocker_records = [record for record in records if record["release_blocker"]]
    authority_weighted_debt = round(
        sum(
            float(record["local_points"])
            for record in records
            if record.get("authority_weighted")
        ),
        3,
    )
    max_severity = max(
        (str(record["local_severity"]) for record in records),
        key=_severity_rank,
        default="none",
    )
    report_issues = [
        issue
        for record in records
        for issue in _sequence_of_mappings(record.get("issues"))
    ]
    readiness = _readiness(
        records=records,
        authority_weighted_debt=authority_weighted_debt,
        max_severity=max_severity,
        blocker_records=blocker_records,
        chain_clusters=chain_clusters,
    )
    return {
        "schema_version": CAPABILITY_RATCHET_SCHEMA_VERSION,
        "contract_id": CAPABILITY_RATCHET_CONTRACT_ID,
        "tool": CAPABILITY_RATCHET_TOOL_NAME,
        "generated_at": generated_at,
        "validation_profile": validation_profile,
        "ratchet_integrity_status": "fail" if report_issues else "pass",
        "summary": {
            "capability_claims_total": len(records),
            "implemented": state_counts[IMPLEMENTED_STATE],
            "open_debt_count": sum(
                1
                for record in records
                if record["reality_state"] not in {IMPLEMENTED_STATE, "surface_out_of_scope"}
            ),
            "release_blocker_count": len(blocker_records),
            "chain_cluster_count": len(chain_clusters),
            "authority_weighted_debt": authority_weighted_debt,
            "max_severity": max_severity,
            "state_counts": dict(sorted(state_counts.items())),
        },
        "readiness": readiness,
        "debt_algebra": {
            "base_points": dict(REALITY_STATE_BASE_POINTS),
            "purpose_multipliers": dict(PURPOSE_MULTIPLIERS),
            "local_points_formula": (
                "base_state_points * purpose_factor + serious_profile_premium "
                "+ sole_path_premium + ownerless_or_expired_premium "
                "+ chain_cluster_premium - mitigation_credit"
            ),
            "severity_bands": {
                "none": "0",
                "low": ">0 and <2",
                "medium": "2 through 4",
                "high": ">4 through 7",
                "critical": ">7",
            },
        },
        "ratchet_templates": ratchet_templates(),
        "chain_clusters": chain_clusters,
        "blockers": blocker_records,
        "issues": report_issues,
        "capability_claims": records,
    }


def ratchet_templates() -> dict[str, dict[str, str]]:
    """Return burn-down templates keyed by reality state."""

    return {
        state: {
            "state": state,
            "base_points": str(REALITY_STATE_BASE_POINTS[state]),
            "required_evidence": BURN_DOWN_SIGNALS[state]["required_evidence"],
            "closure_move": BURN_DOWN_SIGNALS[state]["closure_move"],
        }
        for state in REALITY_STATES
    }


def severity_for_points(points: float) -> str:
    """Map local debt points to the C36 severity band."""

    if points <= 0:
        return "none"
    if points < 2:
        return "low"
    if points <= 4:
        return "medium"
    if points <= 7:
        return "high"
    return "critical"


def _cluster_premiums(
    records: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    records_by_chain: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        chain_id = _text(record.get("chain_id"))
        if not chain_id:
            continue
        if record.get("reality_state") == IMPLEMENTED_STATE:
            continue
        records_by_chain[chain_id].append(record)

    premiums: dict[str, float] = {}
    clusters: list[dict[str, Any]] = []
    for chain_id, chain_records in sorted(records_by_chain.items()):
        medium_plus = [
            record
            for record in chain_records
            if _severity_rank(str(record.get("local_severity"))) >= _severity_rank("medium")
        ]
        high_plus = [
            record
            for record in chain_records
            if _severity_rank(str(record.get("local_severity"))) >= _severity_rank("high")
        ]
        premium = 0.0
        reason = ""
        if len(high_plus) >= 2:
            premium = 2.0
            reason = "two_high_or_worse_in_chain"
        elif len(medium_plus) >= 3:
            premium = 1.0
            reason = "three_medium_or_worse_in_chain"
        if not premium:
            continue
        for record in chain_records:
            capability_id = _text(record.get("capability_id"))
            if capability_id:
                premiums[capability_id] = premium
        clusters.append(
            {
                "chain_id": chain_id,
                "reason": reason,
                "premium": premium,
                "capability_ids": [
                    str(record.get("capability_id")) for record in chain_records
                ],
            }
        )
    return premiums, clusters


def _readiness(
    *,
    records: Sequence[Mapping[str, Any]],
    authority_weighted_debt: float,
    max_severity: str,
    blocker_records: Sequence[Mapping[str, Any]],
    chain_clusters: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    owned_and_expiring = all(
        bool(_text(record.get("owner"))) and bool(_text(record.get("expiry")))
        for record in records
        if record.get("reality_state") != IMPLEMENTED_STATE
    )
    high_records = [
        record
        for record in records
        if str(record.get("local_severity")) == "high"
    ]
    high_outside_authority_closeout = [
        record
        for record in high_records
        if record.get("purpose") not in AUTHORITY_OR_CLOSEOUT_PURPOSES
    ]

    if blocker_records or authority_weighted_debt > 30:
        band = "red"
        decision = "blocked"
    elif chain_clusters or 20 <= authority_weighted_debt <= 30:
        band = "orange"
        decision = "not_ready"
    elif (
        (
            len(high_records) == 1
            and len(high_outside_authority_closeout) == 1
        )
        or 12 <= authority_weighted_debt < 20
    ) and owned_and_expiring:
        band = "yellow"
        decision = "conditional"
    elif _severity_rank(max_severity) <= _severity_rank("medium") and authority_weighted_debt < 12:
        band = "green"
        decision = "ready"
    else:
        band = "orange"
        decision = "not_ready"
    return {
        "band": band,
        "decision": decision,
        "authority_weighted_debt": authority_weighted_debt,
        "max_severity": max_severity,
        "release_blocker_count": len(blocker_records),
        "chain_cluster_count": len(chain_clusters),
    }


def _blocker_reasons(
    *,
    reality_state: str,
    purpose: str,
    serious_profile: bool,
    sole_authority_path: bool,
    promised_audiences: Sequence[str],
) -> list[str]:
    reasons: list[str] = []
    if (
        serious_profile
        and reality_state in AUTHORITY_CHAIN_BLOCKER_STATES
        and purpose in AUTHORITY_OR_CLOSEOUT_PURPOSES
    ):
        reasons.append("serious_authority_or_closeout_chain_missing")
    if reality_state == "surface_missing" and (promised_audiences or purpose == "public_surface"):
        reasons.append("promised_external_surface_missing")
    return reasons


def _evidence_refs(row: Mapping[str, Any]) -> dict[str, str]:
    return {
        field: _text(row.get(field))
        for field, _state in CHAIN_FIELDS
        if _text(row.get(field))
    }


def _traceability(row: Mapping[str, Any]) -> dict[str, Any]:
    rollout_refs = row.get("rollout_refs")
    traceability: dict[str, Any] = {
        "research_refs": list(_sequence_of_text(row.get("research_refs"))),
        "decision_refs": list(_sequence_of_text(row.get("decision_refs"))),
        "no_adr_required": _text(row.get("no_adr_required")),
        "reuse_classification": _normalized_label(row.get("reuse_classification")),
        "rejected_reuse_evidence": list(
            _sequence_of_text(row.get("rejected_reuse_evidence"))
        ),
        "rollout_refs": dict(rollout_refs) if isinstance(rollout_refs, Mapping) else {},
    }
    return {
        key: value
        for key, value in traceability.items()
        if key in TRACEABILITY_FIELDS and value not in ("", [], {})
    }


def _authority_weighted(row: Mapping[str, Any], *, purpose: str) -> bool:
    if "authority_weighted" in row:
        return bool(row.get("authority_weighted"))
    return purpose in AUTHORITY_WEIGHTED_PURPOSES


def _mitigation_credit(row: Mapping[str, Any], *, reality_state: str) -> float:
    if reality_state in {IMPLEMENTED_STATE, "surface_out_of_scope"}:
        return 0.0
    refs = _sequence_of_text(row.get("mitigation_refs"))
    if refs and bool(row.get("mitigation_enforced")):
        return 1.0
    return 0.0


def _valid_surface_out_of_scope(row: Mapping[str, Any]) -> bool:
    details = _surface_out_of_scope(row)
    return all(
        _text(details.get(field))
        for field in ("rationale", "owner", "review_date", "inspection_path")
    )


def _surface_out_of_scope(row: Mapping[str, Any]) -> Mapping[str, Any]:
    details = row.get("surface_out_of_scope")
    if isinstance(details, Mapping):
        return details
    return {
        "rationale": row.get("surface_out_of_scope_rationale"),
        "owner": row.get("surface_out_of_scope_owner") or row.get("owner"),
        "review_date": row.get("surface_out_of_scope_review_date") or row.get("review_date"),
        "inspection_path": row.get("inspection_path"),
    }


def _is_expired(expiry: str, *, as_of: str | date | datetime | None) -> bool:
    if not expiry:
        return False
    try:
        expiry_date = date.fromisoformat(expiry[:10])
    except ValueError:
        return True
    current = _date_from_as_of(as_of)
    return expiry_date < current


def _date_from_as_of(value: str | date | datetime | None) -> date:
    if value is None:
        return datetime.now(tz=UTC).date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _required_text(value: object, field: str, issues: list[dict[str, Any]]) -> str:
    text = _text(value)
    if not text:
        issues.append(
            _issue(
                "capability_claim_field_missing",
                field,
                f"{field} is required.",
            )
        )
    return text


def _issue(
    code: str,
    field: str,
    message: str,
    **details: object,
) -> dict[str, object]:
    return {
        "code": code,
        "field": field,
        "message": message,
        **details,
    }


def _severity_rank(severity: str) -> int:
    return {
        "none": 0,
        "low": 1,
        "medium": 2,
        "high": 3,
        "critical": 4,
    }.get(severity, -1)


def _normalized_label(value: object) -> str:
    return _text(value).strip().lower().replace("-", "_").replace(" ", "_")


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _has_text(value: object) -> bool:
    return bool(_text(value))


def _sequence_of_text(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, Sequence):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def _sequence_of_mappings(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))
