"""Pure candidate-authority firewall helpers shared below runtime."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

CANDIDATE_AUTHORITY_SLOTS: tuple[str, ...] = (
    "legal_authority",
    "data_authority",
    "method_authority",
    "participation_authority",
    "closeout_authority",
    "projection_authority",
    "claim_authority",
    "obligation_authority",
)

_CANDIDATE_REF_PREFIXES = (
    "hypothesis-candidate:",
    "candidate://hypothesis/",
    "runtime.hypothesis_ledger:",
)
_ADMITTED_STATES = {"admitted_to_claim", "admitted_to_obligation"}


def candidate_firewall_issues_for_payload(
    payload: Mapping[str, Any] | None,
    *,
    hypothesis_ledger: Mapping[str, Any] | None = None,
    authority_slots: Sequence[str] = CANDIDATE_AUTHORITY_SLOTS,
    surface: str,
) -> list[dict[str, Any]]:
    """Return typed issues for candidate refs in authority-bearing payload slots."""

    if not isinstance(payload, Mapping):
        return []
    candidate_refs = candidate_refs_from_payload(payload)
    if not candidate_refs:
        return []
    ledger = (
        hypothesis_ledger
        if isinstance(hypothesis_ledger, Mapping)
        else _embedded_ledger(payload)
    )
    if not isinstance(ledger, Mapping):
        return [
            _issue(
                code="candidate_firewall_hypothesis_ledger_missing",
                surface=surface,
                candidate_ref=ref,
                candidate_id=ref,
                authority_slot=",".join(_slot_tuple(authority_slots)),
                message=(
                    "Candidate refs cannot be read in authority slots without "
                    "a hypothesis ledger."
                ),
            )
            for ref in candidate_refs
        ]
    entries = _entries_by_ref(ledger)
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
        state = str(entry.get("admission_state") or entry.get("state") or "")
        for slot in _slot_tuple(authority_slots):
            issue = _entry_issue(entry, state=state, authority_slot=slot, surface=surface, ref=ref)
            if issue is not None:
                issues.append(issue)
    return _dedupe_issues(issues)


def candidate_refs_from_payload(value: object) -> tuple[str, ...]:
    """Find candidate refs in nested payloads."""

    refs: list[str] = []
    _collect_candidate_refs(value, refs)
    return tuple(dict.fromkeys(refs))


def _entry_issue(
    entry: Mapping[str, Any],
    *,
    state: str,
    authority_slot: str,
    surface: str,
    ref: str,
) -> dict[str, Any] | None:
    if state == "candidate_unverified":
        return _entry_block(
            "candidate_firewall_candidate_unverified",
            entry,
            authority_slot=authority_slot,
            surface=surface,
            ref=ref,
            message="Unverified hypothesis candidates cannot satisfy authority slots.",
        )
    if state == "rejected_speculation":
        return _entry_block(
            "candidate_firewall_rejected_speculation",
            entry,
            authority_slot=authority_slot,
            surface=surface,
            ref=ref,
            message="Rejected speculation cannot satisfy authority slots.",
        )
    if authority_slot in {"blocker_authority", "closeout_blocker"}:
        return (
            None
            if state == "typed_blocker"
            else _state_mismatch(entry, authority_slot, surface, ref)
        )
    if authority_slot in {"limitation_authority", "public_limitation"}:
        return (
            None
            if state == "limitation"
            else _state_mismatch(entry, authority_slot, surface, ref)
        )
    if authority_slot == "claim_authority" and state != "admitted_to_claim":
        return _state_mismatch(entry, authority_slot, surface, ref)
    if authority_slot == "obligation_authority" and state != "admitted_to_obligation":
        return _state_mismatch(entry, authority_slot, surface, ref)
    if authority_slot in CANDIDATE_AUTHORITY_SLOTS and state not in _ADMITTED_STATES:
        return _state_mismatch(entry, authority_slot, surface, ref)
    if state in _ADMITTED_STATES and not _has_validation(entry):
        return _entry_block(
            "candidate_firewall_validation_missing",
            entry,
            authority_slot=authority_slot,
            surface=surface,
            ref=ref,
            message="Admitted candidate lacks producer or reader validation refs.",
        )
    return None


def _entry_block(
    code: str,
    entry: Mapping[str, Any],
    *,
    authority_slot: str,
    surface: str,
    ref: str,
    message: str,
) -> dict[str, Any]:
    return _issue(
        code=code,
        surface=surface,
        candidate_ref=ref,
        candidate_id=str(entry.get("candidate_id") or entry.get("entry_id") or ref),
        authority_slot=authority_slot,
        message=message,
    )


def _state_mismatch(
    entry: Mapping[str, Any],
    authority_slot: str,
    surface: str,
    ref: str,
) -> dict[str, Any]:
    state = str(entry.get("admission_state") or entry.get("state") or "unknown")
    return _entry_block(
        "candidate_firewall_admission_state_mismatch",
        entry,
        authority_slot=authority_slot,
        surface=surface,
        ref=ref,
        message=f"Candidate state {state!r} cannot satisfy {authority_slot!r}.",
    )


def _issue(
    *,
    code: str,
    surface: str,
    candidate_ref: str,
    candidate_id: str,
    authority_slot: str,
    message: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "surface": surface,
        "candidate_ref": candidate_ref,
        "candidate_id": candidate_id,
        "authority_slot": authority_slot,
        "message": message,
        "severity": "fail",
        "authority_effect": "blocked_candidate_authority",
    }


def _collect_candidate_refs(value: object, refs: list[str]) -> None:
    if isinstance(value, str):
        if any(value.startswith(prefix) for prefix in _CANDIDATE_REF_PREFIXES):
            refs.append(value)
        return
    if isinstance(value, Mapping):
        for nested in value.values():
            _collect_candidate_refs(nested, refs)
        return
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        for nested in value:
            _collect_candidate_refs(nested, refs)


def _embedded_ledger(payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
    ledger = payload.get("hypothesis_ledger")
    return ledger if isinstance(ledger, Mapping) else None


def _entries_by_ref(ledger: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    raw_entries = ledger.get("entries")
    if not isinstance(raw_entries, Sequence):
        return {}
    entries: dict[str, Mapping[str, Any]] = {}
    for raw in raw_entries:
        if not isinstance(raw, Mapping):
            continue
        refs = [
            raw.get("candidate_ref"),
            raw.get("ref"),
            raw.get("entry_ref"),
            raw.get("candidate_id"),
        ]
        for ref in refs:
            if isinstance(ref, str) and ref:
                entries[ref] = raw
    return entries


def _has_validation(entry: Mapping[str, Any]) -> bool:
    refs = entry.get("validation_refs")
    return (
        isinstance(refs, Sequence)
        and not isinstance(refs, (str, bytes, bytearray))
        and bool(refs)
    )


def _slot_tuple(slots: Sequence[str]) -> tuple[str, ...]:
    return tuple(str(slot) for slot in slots if str(slot))


def _dedupe_issues(issues: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for issue in issues:
        key = (
            str(issue.get("code") or ""),
            str(issue.get("candidate_ref") or ""),
            str(issue.get("authority_slot") or ""),
        )
        deduped.setdefault(key, dict(issue))
    return list(deduped.values())
