"""Consumer-side firewall between candidates and authority-bearing read slots."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from polisyos.runtime.quality.authority import authority_purpose_blockers
from polisyos.runtime.quality.hypothesis_ledger import (
    CANDIDATE_AUTHORITY_SLOTS,
    HYPOTHESIS_LEDGER_REPORT_KEY,
    HypothesisLedger,
    HypothesisLedgerEntry,
    HypothesisLedgerInput,
    deserialize_hypothesis_ledger,
)

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
    "CandidateFirewallError",
    "assert_no_candidate_authority_laundering",
    "candidate_firewall_issues_for_payload",
    "candidate_refs_from_payload",
]
