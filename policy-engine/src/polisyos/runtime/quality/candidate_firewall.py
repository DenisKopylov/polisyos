"""Consumer-side firewall between candidates and authority-bearing read slots."""

from __future__ import annotations

import importlib
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from polisyos.runtime.quality.authority import authority_purpose_blockers
from polisyos.runtime.quality.hypothesis_ledger import (
    CANDIDATE_AUTHORITY_SLOTS,
    HYPOTHESIS_LEDGER_REPORT_KEY,
    HypothesisLedger,
    HypothesisLedgerEntry,
    HypothesisLedgerInput,
    deserialize_hypothesis_ledger,
)

AUTHORITY_CANDIDATE_FIREWALL_NAME = "candidate_positive_status_firewall"


class SpanSupportClient(Protocol):
    """Structural client protocol for injected span-support judges."""

    def generate(
        self,
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        temperature: float | None = None,
        seed: int | None = None,
    ) -> Awaitable[object]:
        """Return a bounded-agent style tool-calling response."""


class AuthorityCandidateInventoryRow(BaseModel):
    """One firewall-excluded candidate-positive status row."""

    model_config = ConfigDict(extra="forbid")

    producer_component: str = Field(..., min_length=1)
    source_artifact_ref: str = Field(..., min_length=1)
    field_path: str = Field(..., min_length=1)
    status_text: str = Field(..., min_length=1)
    candidate_positive_rule: str = Field(..., min_length=1)
    firewall_name: str = AUTHORITY_CANDIDATE_FIREWALL_NAME
    exclusion_reason: str = Field(..., min_length=1)
    resulting_boundary_ref: str = Field(..., min_length=1)
    false_exclusion_review: str = Field(..., min_length=1)
    reviewer: str | None = None
    reviewed_at: str | None = None

_CANDIDATE_REF_PREFIXES = (
    "hypothesis-candidate:",
    "candidate://hypothesis/",
    "runtime.hypothesis_ledger:",
)
_ADMITTED_STATES = frozenset({"admitted_to_claim", "admitted_to_obligation"})
_CLAIM_SLOTS = frozenset({"claim_authority"})
_OBLIGATION_SLOTS = frozenset({"obligation_authority"})
_LIMITATION_SLOTS = frozenset({"limitation_authority", "public_limitation"})
_BLOCKER_SLOTS = frozenset({"blocker_authority", "closeout_blocker"})
_PROTECTED_AUTHORITY_SLOTS = frozenset(
    {
        "legal_authority",
        "data_authority",
        "method_authority",
        "participation_authority",
        "closeout_authority",
        "projection_authority",
        "claim_authority",
        "obligation_authority",
    }
)


class CandidateFirewallError(ValueError):
    """Raised when candidate content attempts to satisfy authority."""

    def __init__(
        self,
        code: str,
        message: str | None = None,
        *,
        candidate_id: str | None = None,
        surface: str | None = None,
    ) -> None:
        self.code = code
        self.candidate_id = candidate_id
        self.surface = surface
        detail = message or code
        if candidate_id:
            detail = f"{detail} (candidate_id={candidate_id})"
        if surface:
            detail = f"{detail} (surface={surface})"
        super().__init__(f"{code}: {detail}")


def assert_no_candidate_authority_laundering(
    payload: Mapping[str, Any],
    *,
    hypothesis_ledger: HypothesisLedgerInput | None = None,
    authority_slots: Sequence[str] = CANDIDATE_AUTHORITY_SLOTS,
    surface: str,
) -> Mapping[str, Any]:
    """Raise when payload references a candidate that cannot fill authority slots."""

    issues = candidate_firewall_issues_for_payload(
        payload,
        hypothesis_ledger=hypothesis_ledger,
        authority_slots=authority_slots,
        surface=surface,
    )
    if issues:
        first = issues[0]
        raise CandidateFirewallError(
            str(first.get("code") or "candidate_firewall_blocked"),
            str(first.get("message") or "Candidate content cannot satisfy authority."),
            candidate_id=_text(first.get("candidate_id")),
            surface=surface,
        )
    return payload


def candidate_firewall_issues_for_payload(
    payload: Mapping[str, Any] | None,
    *,
    hypothesis_ledger: HypothesisLedgerInput | None = None,
    authority_slots: Sequence[str] = CANDIDATE_AUTHORITY_SLOTS,
    surface: str,
) -> list[dict[str, Any]]:
    """Return firewall issues for candidate refs found in one read payload."""

    if not isinstance(payload, Mapping):
        return []
    candidate_refs = candidate_refs_from_payload(payload)
    if not candidate_refs:
        return []
    ledger = _ledger_from_inputs(payload=payload, hypothesis_ledger=hypothesis_ledger)
    if ledger is None:
        return [
            _issue(
                code="candidate_firewall_hypothesis_ledger_missing",
                surface=surface,
                candidate_ref=ref,
                candidate_id=ref,
                authority_slot=",".join(_slot_tuple(authority_slots)),
                message=(
                    "Candidate refs cannot be read in authority slots without the "
                    "runtime hypothesis ledger."
                ),
            )
            for ref in candidate_refs
        ]
    entries = ledger.entries_by_ref()
    issues: list[dict[str, Any]] = []
    for ref in candidate_refs:
        entry = entries.get(ref)
        if entry is None:
            issues.append(
                _issue(
                    code="candidate_firewall_candidate_unknown",
                    surface=surface,
                    candidate_ref=ref,
                    candidate_id=ref,
                    authority_slot=",".join(_slot_tuple(authority_slots)),
                    message="Candidate ref is not present in the hypothesis ledger.",
                )
            )
            continue
        for slot in _slot_tuple(authority_slots):
            issue = _entry_issue(entry, authority_slot=slot, surface=surface, candidate_ref=ref)
            if issue is not None:
                issues.append(issue)
    return _dedupe_issues(issues)


def candidate_refs_from_payload(value: object) -> tuple[str, ...]:
    """Find candidate refs in nested payloads without treating ordinary text as authority."""

    refs: list[str] = []
    _collect_candidate_refs(value, refs)
    return tuple(dict.fromkeys(refs))


def build_authority_candidate_inventory_rows(
    firewall_rows: Sequence[Mapping[str, Any]],
    *,
    reviewer: str | None = None,
    reviewed_at: str | None = None,
) -> tuple[AuthorityCandidateInventoryRow, ...]:
    """Build row-level authority inventory from existing firewall exclusions."""

    return tuple(
        _authority_candidate_inventory_row(
            row,
            reviewer=reviewer,
            reviewed_at=reviewed_at,
        )
        for row in firewall_rows
    )


def assert_candidate_positive_firewall_boundary(
    row: AuthorityCandidateInventoryRow | Mapping[str, Any],
    *,
    surface: str,
    boundary_ref: str | None,
) -> None:
    """Reject candidate-positive authority promotion unless the firewall boundary exists."""

    inventory_row = (
        row
        if isinstance(row, AuthorityCandidateInventoryRow)
        else AuthorityCandidateInventoryRow.model_validate(row)
    )
    if boundary_ref != inventory_row.resulting_boundary_ref:
        raise CandidateFirewallError(
            "candidate_positive_firewall_boundary_missing",
            "Candidate-positive diagnostic status cannot promote without its firewall boundary.",
            candidate_id=inventory_row.resulting_boundary_ref,
            surface=surface,
        )


def assert_l2_claim_authority_span_grounded(
    payload: Mapping[str, Any],
    *,
    surface: str,
    grounding_resolver: Callable[[str], Mapping[str, Any] | None] | None = None,
    span_support_client: SpanSupportClient | None = None,
) -> Mapping[str, Any]:
    """Reject L2 claim-authority records without resolved validated span grounding."""

    issues = l2_claim_authority_grounding_issues_for_payload(
        payload,
        surface=surface,
        grounding_resolver=grounding_resolver,
        span_support_client=span_support_client,
    )
    if issues:
        first = issues[0]
        raise CandidateFirewallError(
            str(first.get("code") or "web_bundle_l2_authority_blocked"),
            str(first.get("message") or "Web bundle cannot satisfy L2 authority."),
            candidate_id=_text(first.get("source_ref")),
            surface=surface,
        )
    return payload


def web_bundle_l2_authority_issues_for_payload(
    payload: Mapping[str, Any] | None,
    *,
    surface: str,
) -> list[dict[str, Any]]:
    """Return issues for web bundles attempting to fill L2 claim authority."""

    return l2_claim_authority_grounding_issues_for_payload(payload, surface=surface)


def l2_claim_authority_grounding_issues_for_payload(
    payload: Mapping[str, Any] | None,
    *,
    surface: str,
    grounding_resolver: Callable[[str], Mapping[str, Any] | None] | None = None,
    span_support_client: SpanSupportClient | None = None,
) -> list[dict[str, Any]]:
    """Return issues for L2 claim authority without resolved span grounding."""

    if not isinstance(payload, Mapping):
        return []
    issues: list[dict[str, Any]] = []
    _collect_web_l2_authority_issues(
        payload,
        issues,
        surface=surface,
        in_claim_authority=False,
        grounding_resolver=grounding_resolver,
        span_support_client=span_support_client,
    )
    return _dedupe_web_issues(issues)


def _authority_candidate_inventory_row(
    row: Mapping[str, Any],
    *,
    reviewer: str | None,
    reviewed_at: str | None,
) -> AuthorityCandidateInventoryRow:
    producer_source = row.get("producer_source")
    if not isinstance(producer_source, Mapping):
        producer_source = {}
    producer_component = (
        _text(producer_source.get("producer_ref"))
        or _text(producer_source.get("producer_type"))
        or _text(row.get("artifact_family"))
        or "unknown_producer"
    )
    candidate_positive_rule = (
        _text(row.get("firewall_rule"))
        or _text(row.get("classification"))
        or "candidate_positive_status_firewall"
    )
    exclusion_reason = (
        _text(row.get("firewall_rule"))
        or _text(row.get("classification"))
        or "candidate_positive_excluded"
    )
    candidate_id = _text(row.get("candidate_positive_status_id")) or _stable_candidate_row_id(row)
    return AuthorityCandidateInventoryRow(
        producer_component=producer_component,
        source_artifact_ref=_text(row.get("artifact_path")) or "unknown_artifact",
        field_path=_candidate_positive_field_path(row),
        status_text=_text(row.get("value")) or "unknown_status",
        candidate_positive_rule=candidate_positive_rule,
        firewall_name=AUTHORITY_CANDIDATE_FIREWALL_NAME,
        exclusion_reason=exclusion_reason,
        resulting_boundary_ref=f"authority-boundary://candidate-positive-status/{candidate_id}",
        false_exclusion_review=_false_exclusion_review(row),
        reviewer=reviewer,
        reviewed_at=reviewed_at,
    )


_WEB_BUNDLE_SOURCE_KINDS = {
    "scholar.web_evidence_bundle",
    "web_evidence_bundle",
    "web_search_hit",
    "openalex_search_hit",
    "candidate_web_bundle",
}


def _collect_web_l2_authority_issues(
    value: object,
    issues: list[dict[str, Any]],
    *,
    surface: str,
    in_claim_authority: bool,
    grounding_resolver: Callable[[str], Mapping[str, Any] | None] | None,
    span_support_client: SpanSupportClient | None,
) -> None:
    if isinstance(value, Mapping):
        is_claim_authority = in_claim_authority
        for key in value:
            if str(key).strip().lower() in {"claim_authority", "l2_claim_authority"}:
                is_claim_authority = True
                break
        if is_claim_authority and _looks_like_l2_claim_authority_record(value):
            issue = _l2_claim_authority_grounding_issue(
                value,
                surface=surface,
                grounding_resolver=grounding_resolver,
                span_support_client=span_support_client,
            )
            if issue is not None:
                issues.append(issue)
        elif (
            is_claim_authority
            and _looks_like_web_authority_record(value)
            and not _has_validated_span_grounding(value)
        ):
            issues.append(
                {
                    "code": "web_bundle_l2_authority_blocked",
                    "severity": "fail",
                    "status": "fail",
                    "surface": surface,
                    "layer": "candidate_firewall",
                    "source_kind": _text(value.get("source_kind")),
                    "source_ref": _text(value.get("source_ref")),
                    "authority_slot": "claim_authority",
                    "message": (
                        "Web bundles and raw search hits are candidate_unverified until "
                        "a resolving, supporting span-grounding record validates them."
                    ),
                }
            )
        for key, item in value.items():
            key_is_claim = str(key).strip().lower() in {
                "claim_authority",
                "l2_claim_authority",
            }
            _collect_web_l2_authority_issues(
                item,
                issues,
                surface=surface,
                in_claim_authority=is_claim_authority or key_is_claim,
                grounding_resolver=grounding_resolver,
                span_support_client=span_support_client,
            )
        return
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray | str):
        for item in value:
            _collect_web_l2_authority_issues(
                item,
                issues,
                surface=surface,
                in_claim_authority=in_claim_authority,
                grounding_resolver=grounding_resolver,
                span_support_client=span_support_client,
            )


def _looks_like_l2_claim_authority_record(value: Mapping[str, Any]) -> bool:
    authority_tier = _text(value.get("authority_tier")) or ""
    if authority_tier == "design_tier_l2":
        return True
    if _text(value.get("span_grounding_status")) or _text(
        value.get("validated_span_grounding_ref")
    ):
        return True
    source_kind = _text(value.get("source_kind")) or ""
    source_ref = _text(value.get("source_ref")) or ""
    return source_kind == "openalex_span_grounded_claim" or source_ref.startswith(
        "openalex-span-grounding://"
    )


def _l2_claim_authority_grounding_issue(
    value: Mapping[str, Any],
    *,
    surface: str,
    grounding_resolver: Callable[[str], Mapping[str, Any] | None] | None,
    span_support_client: SpanSupportClient | None,
) -> dict[str, Any] | None:
    source_ref = _text(value.get("source_ref")) or ""
    grounding_ref = (
        _text(value.get("validated_span_grounding_ref"))
        or _text(value.get("grounding_ref"))
        or (source_ref if source_ref.startswith("openalex-span-grounding://") else "")
    )
    if _looks_like_web_authority_record(value) and not grounding_ref:
        return {
            "code": "web_bundle_l2_authority_blocked",
            "severity": "fail",
            "status": "fail",
            "surface": surface,
            "layer": "candidate_firewall",
            "source_kind": _text(value.get("source_kind")),
            "source_ref": _text(value.get("source_ref")),
            "authority_slot": "claim_authority",
            "message": (
                "Web bundles and raw search hits are candidate_unverified until "
                "a resolving, supporting span-grounding record validates them."
            ),
        }
    if not grounding_ref or grounding_resolver is None:
        return _l2_grounding_issue(
            code="l2_claim_authority_grounding_unresolved",
            value=value,
            surface=surface,
            grounding_ref=grounding_ref,
            message="L2 claim authority requires a resolver-backed span grounding record.",
        )
    resolved = grounding_resolver(grounding_ref)
    if resolved is None:
        return _l2_grounding_issue(
            code="l2_claim_authority_grounding_unresolved",
            value=value,
            surface=surface,
            grounding_ref=grounding_ref,
            message="L2 claim authority grounding ref did not resolve.",
        )
    if not _resolved_grounding_validates(
        grounding_ref,
        candidate=value,
        resolved=resolved,
        span_support_client=span_support_client,
    ):
        return _l2_grounding_issue(
            code="l2_claim_authority_grounding_unvalidated",
            value=value,
            surface=surface,
            grounding_ref=grounding_ref,
            message="Resolved L2 claim authority grounding is not validated supporting evidence.",
        )
    return None


def _resolved_grounding_validates(
    grounding_ref: str,
    *,
    candidate: Mapping[str, Any],
    resolved: Mapping[str, Any],
    span_support_client: SpanSupportClient | None,
) -> bool:
    resolved_ref = _text(resolved.get("grounding_ref")) or _text(resolved.get("source_ref"))
    if resolved_ref and resolved_ref != grounding_ref:
        return False
    candidate_claim_text = _text(candidate.get("claim_text") or candidate.get("text"))
    if not candidate_claim_text:
        return False
    candidate_claim_id = _text(candidate.get("claim_id") or candidate.get("id"))
    resolved_claim_id = _text(resolved.get("claim_id") or resolved.get("id"))
    if candidate_claim_id and resolved_claim_id and candidate_claim_id != resolved_claim_id:
        return False
    resolved_claim_text = _text(resolved.get("claim_text") or resolved.get("text"))
    if not resolved_claim_text:
        return False
    if _content_binding_text(candidate_claim_text) != _content_binding_text(resolved_claim_text):
        return False
    candidate_span_text = _text(
        candidate.get("span_text")
        or candidate.get("evidence_text")
        or candidate.get("source_span_text")
    )
    resolved_span_text = _text(
        resolved.get("span_text")
        or resolved.get("evidence_text")
        or resolved.get("source_span_text")
    )
    if candidate_span_text and resolved_span_text and candidate_span_text != resolved_span_text:
        return False
    if (
        _text(resolved.get("support_status") or resolved.get("span_grounding_status"))
        != "validated_supporting"
    ):
        return False
    if _text(resolved.get("authority_tier")) != "design_tier_l2":
        return False
    if not _text(resolved.get("source_content_sha256")):
        return False
    return _resolved_grounding_entails(
        grounding_ref,
        candidate=candidate,
        resolved=resolved,
        span_support_client=span_support_client,
    )


def _content_binding_text(value: object) -> str:
    return " ".join(_text(value).casefold().split())


def _resolved_grounding_entails(
    grounding_ref: str,
    *,
    candidate: Mapping[str, Any],
    resolved: Mapping[str, Any],
    span_support_client: SpanSupportClient | None,
) -> bool:
    claim_text = _text(candidate.get("claim_text") or candidate.get("text"))
    span_text = _text(
        resolved.get("span_text")
        or resolved.get("evidence_text")
        or resolved.get("source_span_text")
    )
    if not claim_text or not span_text:
        return False
    module = importlib.import_module("polisyos.scientist.validation.citation_faithfulness")
    entailment = module.evaluate_span_claim_entailment(
        claim={
            "claim_id": _text(candidate.get("claim_id") or candidate.get("id"))
            or _text(resolved.get("claim_id"))
            or grounding_ref,
            "claim_text": claim_text,
            "claim_family": (
                candidate.get("claim_family") or resolved.get("claim_family") or "causal"
            ),
            "cause_variable": candidate.get("cause")
            or candidate.get("cause_variable")
            or resolved.get("cause")
            or resolved.get("cause_variable"),
            "effect_variable": candidate.get("effect")
            or candidate.get("effect_variable")
            or resolved.get("effect")
            or resolved.get("effect_variable"),
            "direction": candidate.get("direction") or resolved.get("direction"),
            "data_refs": [resolved.get("openalex_id") or grounding_ref],
            "source_attribution": resolved.get("openalex_id") or grounding_ref,
            "method_refs": [resolved.get("design_family") or "source_bound_claim_span"],
            "identification_strategy": (
                resolved.get("identification_strategy")
                or resolved.get("design_family")
                or "source_bound_claim_span"
            ),
            "citation_refs": [grounding_ref],
        },
        evidence={
            "ref_id": grounding_ref,
            "source_id": resolved.get("openalex_id") or grounding_ref,
            "section": resolved.get("section") or "abstract",
            "text": span_text,
            "source_content_sha256": resolved.get("source_content_sha256"),
        },
        client=span_support_client,
    )
    labels = module.SPAN_ENTAILMENT_SUPPORT_LABELS
    return str(entailment.get("label") or "") in {str(label) for label in labels}


def _l2_grounding_issue(
    *,
    code: str,
    value: Mapping[str, Any],
    surface: str,
    grounding_ref: str,
    message: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "fail",
        "status": "fail",
        "surface": surface,
        "layer": "candidate_firewall",
        "source_kind": _text(value.get("source_kind")),
        "source_ref": _text(value.get("source_ref")),
        "grounding_ref": grounding_ref,
        "authority_slot": "claim_authority",
        "message": message,
    }


def _looks_like_web_authority_record(value: Mapping[str, Any]) -> bool:
    source_kind = _text(value.get("source_kind")) or _text(value.get("artifact_kind")) or ""
    source_ref = _text(value.get("source_ref")) or _text(value.get("bundle_ref")) or ""
    authority_tier = _text(value.get("authority_tier")) or ""
    return (
        source_kind in _WEB_BUNDLE_SOURCE_KINDS
        or source_ref.startswith("webkb.")
        or source_ref.startswith("scholar.web_evidence_bundle:")
        or (
            authority_tier == "design_tier_l2"
            and source_kind in {"web", "academic_search_result"}
        )
    )


def _has_validated_span_grounding(value: Mapping[str, Any]) -> bool:
    return (
        _text(value.get("span_grounding_status")) == "validated_supporting"
        and bool(_text(value.get("validated_span_grounding_ref")))
    )


def _dedupe_web_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for issue in issues:
        key = (
            str(issue.get("code")),
            str(issue.get("source_ref")),
            str(issue.get("authority_slot")),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(issue)
    return deduped


def _candidate_positive_field_path(row: Mapping[str, Any]) -> str:
    pointer = _text(row.get("json_pointer")) or "$"
    field = _text(row.get("field")) or "status"
    return f"{pointer}/{field}"


def _false_exclusion_review(row: Mapping[str, Any]) -> str:
    triage = row.get("false_exclusion_triage")
    if not isinstance(triage, Mapping):
        return "repair_ticket_required:triage_missing"
    risk = _text(triage.get("risk")) or "unknown_risk"
    note = _text(triage.get("note")) or "no_note"
    if triage.get("needs_human_review") is True:
        return f"repair_ticket_required:{risk}:{note}"
    return f"no_false_exclusion:{risk}"


def _stable_candidate_row_id(row: Mapping[str, Any]) -> str:
    import hashlib
    import json

    payload = json.dumps(row, sort_keys=True, default=str).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _entry_issue(
    entry: HypothesisLedgerEntry,
    *,
    authority_slot: str,
    surface: str,
    candidate_ref: str,
) -> dict[str, Any] | None:
    state = entry.admission_state
    if state == "candidate_unverified":
        return _entry_block(
            "candidate_firewall_candidate_unverified",
            entry,
            authority_slot=authority_slot,
            surface=surface,
            candidate_ref=candidate_ref,
            message="Unverified hypothesis candidates cannot satisfy authority slots.",
        )
    if state == "rejected_speculation":
        return _entry_block(
            "candidate_firewall_rejected_speculation",
            entry,
            authority_slot=authority_slot,
            surface=surface,
            candidate_ref=candidate_ref,
            message="Rejected speculation cannot satisfy authority slots.",
        )
    if authority_slot in _BLOCKER_SLOTS:
        return (
            None
            if state == "typed_blocker"
            else _state_mismatch(entry, authority_slot, surface, candidate_ref)
        )
    if authority_slot in _LIMITATION_SLOTS:
        return (
            None
            if state == "limitation"
            else _state_mismatch(entry, authority_slot, surface, candidate_ref)
        )
    if authority_slot in _CLAIM_SLOTS and state != "admitted_to_claim":
        return _state_mismatch(entry, authority_slot, surface, candidate_ref)
    if authority_slot in _OBLIGATION_SLOTS and state != "admitted_to_obligation":
        return _state_mismatch(entry, authority_slot, surface, candidate_ref)
    if authority_slot in _PROTECTED_AUTHORITY_SLOTS and state not in _ADMITTED_STATES:
        return _state_mismatch(entry, authority_slot, surface, candidate_ref)
    if not entry.has_admission_lineage:
        return _entry_block(
            "candidate_firewall_admission_lineage_missing",
            entry,
            authority_slot=authority_slot,
            surface=surface,
            candidate_ref=candidate_ref,
            message=(
                "Admitted candidate is missing prompt fingerprint, tool refs, "
                "or repair-decision lineage."
            ),
        )
    if not entry.validation_refs:
        return _entry_block(
            "candidate_firewall_validation_missing",
            entry,
            authority_slot=authority_slot,
            surface=surface,
            candidate_ref=candidate_ref,
            message="Admitted candidate lacks producer or reader validation refs.",
        )
    purpose_blockers = authority_purpose_blockers(
        entry.authority_envelope.model_dump(mode="json"),
        authority_slot,
    )
    if purpose_blockers:
        return _entry_block(
            purpose_blockers[0],
            entry,
            authority_slot=authority_slot,
            surface=surface,
            candidate_ref=candidate_ref,
            message=(
                "Candidate authority envelope does not authorize this purpose "
                "or explicitly forbids it."
            ),
        )
    return None


def _state_mismatch(
    entry: HypothesisLedgerEntry,
    authority_slot: str,
    surface: str,
    candidate_ref: str,
) -> dict[str, Any]:
    return _entry_block(
        "candidate_firewall_admission_state_mismatch",
        entry,
        authority_slot=authority_slot,
        surface=surface,
        candidate_ref=candidate_ref,
        message=(
            f"Candidate admission_state={entry.admission_state!r} cannot satisfy "
            f"{authority_slot!r}."
        ),
    )


def _entry_block(
    code: str,
    entry: HypothesisLedgerEntry,
    *,
    authority_slot: str,
    surface: str,
    candidate_ref: str,
    message: str,
) -> dict[str, Any]:
    return _issue(
        code=code,
        surface=surface,
        candidate_ref=candidate_ref,
        candidate_id=entry.candidate_id,
        authority_slot=authority_slot,
        message=message,
        admission_state=entry.admission_state,
        source_class=entry.source_class,
        next_action=(
            "Route candidate content through producer or reader validation and "
            "record admitted_to_claim/admitted_to_obligation lineage, or keep it "
            "as a typed blocker/limitation instead of authority."
        ),
    )


def _issue(
    *,
    code: str,
    surface: str,
    candidate_ref: str,
    candidate_id: str,
    authority_slot: str,
    message: str,
    admission_state: str | None = None,
    source_class: str | None = None,
    next_action: str | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "fail",
        "status": "fail",
        "surface": surface,
        "layer": "candidate_firewall",
        "phase": surface,
        "candidate_ref": candidate_ref,
        "candidate_id": candidate_id,
        "authority_slot": authority_slot,
        "admission_state": admission_state,
        "source_class": source_class,
        "message": message,
        "next_action": next_action
        or "Persist and validate the candidate through the hypothesis ledger firewall.",
    }


def _ledger_from_inputs(
    *,
    payload: Mapping[str, Any],
    hypothesis_ledger: HypothesisLedgerInput | None,
) -> HypothesisLedger | None:
    candidate = hypothesis_ledger
    if candidate is None:
        embedded = payload.get(HYPOTHESIS_LEDGER_REPORT_KEY)
        if isinstance(embedded, Mapping):
            candidate = embedded
    if candidate is None:
        return None
    return deserialize_hypothesis_ledger(candidate)


def _collect_candidate_refs(value: object, refs: list[str]) -> None:
    if isinstance(value, str):
        text = value.strip()
        if _looks_like_candidate_ref(text):
            refs.append(text)
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).casefold()
            if lowered == HYPOTHESIS_LEDGER_REPORT_KEY:
                continue
            if lowered in {
                "candidate_id",
                "candidate_ref",
                "hypothesis_candidate_id",
                "hypothesis_candidate_ref",
            }:
                for ref in _refs_from_value(item):
                    if _looks_like_candidate_ref(ref):
                        refs.append(ref)
                continue
            if lowered in {
                "candidate_refs",
                "hypothesis_candidate_refs",
                "claim_refs",
                "selected_norm_refs",
                "data_refs",
                "method_output_refs",
                "participation_refs",
                "projection_refs",
                "closeout_refs",
            }:
                for ref in _refs_from_value(item):
                    if _looks_like_candidate_ref(ref):
                        refs.append(ref)
                continue
            _collect_candidate_refs(item, refs)
        return
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        for item in value:
            _collect_candidate_refs(item, refs)


def _refs_from_value(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        values: Sequence[object] = (value,)
    elif isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        values = value
    else:
        values = (value,)
    refs: list[str] = []
    for item in values:
        text = _text(item)
        if text and text not in refs:
            refs.append(text)
    return tuple(refs)


def _looks_like_candidate_ref(value: str) -> bool:
    return any(value.startswith(prefix) for prefix in _CANDIDATE_REF_PREFIXES)


def _slot_tuple(values: Sequence[str]) -> tuple[str, ...]:
    slots = [text for value in values for text in (_text(value),) if text]
    return tuple(dict.fromkeys(slots))


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dedupe_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for issue in issues:
        key = (
            str(issue.get("code")),
            str(issue.get("candidate_id")),
            str(issue.get("authority_slot")),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(issue)
    return deduped


__all__ = [
    "AUTHORITY_CANDIDATE_FIREWALL_NAME",
    "AuthorityCandidateInventoryRow",
    "CandidateFirewallError",
    "assert_candidate_positive_firewall_boundary",
    "assert_l2_claim_authority_span_grounded",
    "assert_no_candidate_authority_laundering",
    "build_authority_candidate_inventory_rows",
    "candidate_firewall_issues_for_payload",
    "candidate_refs_from_payload",
    "web_bundle_l2_authority_issues_for_payload",
]
