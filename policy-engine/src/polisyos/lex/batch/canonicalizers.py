"""Canonicalizers for Lex batch SPO extraction.

This module keeps strict canonical vocabularies for actions and deontic types,
while preserving original raw values for auditability.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from polisyos.lex.knowledge.types import ThresholdAtom

_CORE_NORM_TYPES = {
    "obligation",
    "prohibition",
    "permission",
    "definition",
    "procedure",
    "exception",
    "sanction",
    "delegation",
    "amendment",
    "repeal",
    "entry_into_force",
}

_NORM_TYPE_SYNONYMS: dict[str, str] = {
    "obligation": "obligation",
    "required": "obligation",
    "must": "obligation",
    "requirement": "obligation",
    "prohibition": "prohibition",
    "forbidden": "prohibition",
    "must_not": "prohibition",
    "permission": "permission",
    "right": "permission",
    "allowed": "permission",
    "definition": "definition",
    "term": "definition",
    "procedure": "procedure",
    "procedural": "procedure",
    "exception": "exception",
    "exemption": "exception",
    "exclusion": "exception",
    "sanction": "sanction",
    "penalty": "sanction",
    "delegation": "delegation",
    "delegates_to": "delegation",
    "amendment": "amendment",
    "amends": "amendment",
    "repeal": "repeal",
    "supersedes": "repeal",
    "entry_into_force": "entry_into_force",
    "enters_into_force": "entry_into_force",
    # Common verify-pass labels from legal extraction.
    "directive": "obligation",
    "binding": "obligation",
    "usage_rule": "procedure",
    "regulation": "procedure",
    "establishment": "procedure",
    "distribution_rule": "procedure",
    "statement_of_fact": "definition",
    "declarative": "definition",
    "inclusion": "definition",
    "regulatory_act": "procedure",
    "compensation": "sanction",
    "transfer": "delegation",
    "temporal_reference": "entry_into_force",
    "settlement": "procedure",
    "постановляє": "obligation",
    # New labels observed in smoke runs.
    "imperative": "obligation",
    "allocation_rule": "procedure",
    "presidential_decree": "procedure",
    "entitlement": "permission",
    "scope_of_application": "procedure",
    "approval": "procedure",
    "temporal_rule": "entry_into_force",
    "prohibitive": "prohibition",
    "allocation": "procedure",
}

_CORE_ACTIONS = {
    "requires",
    "prohibits",
    "grants",
    "delegates",
    "sets_threshold",
    "applies_to",
    "defines",
    "revokes",
    "enters_into_force",
    "amends",
    "repeals",
    "approves",
    "excludes",
    "establishes",
    "regulates",
    "must_comply_with",
    "must_not_exceed",
    "is_funded_by",
    "is_composed_of",
    "limits",
}

_ACTION_SYNONYMS: dict[str, str] = {
    "requires": "requires",
    "require": "requires",
    "must_comply_with": "must_comply_with",
    "prohibits": "prohibits",
    "forbids": "prohibits",
    "must_not": "prohibits",
    "grants": "grants",
    "has_right_to": "grants",
    "delegates_to": "delegates",
    "delegates": "delegates",
    "sets_threshold": "sets_threshold",
    "must_not_exceed": "must_not_exceed",
    "applies_to": "applies_to",
    "is_subject_to": "applies_to",
    "defines": "defines",
    "is_defined_by": "defines",
    "revokes": "revokes",
    "must_be_revoked_or_reduced": "revokes",
    "enters_into_force": "enters_into_force",
    "amends": "amends",
    "supersedes": "repeals",
    "repeals": "repeals",
    "approves": "approves",
    "excludes": "excludes",
    "does_not_apply_to": "excludes",
    "establishes": "establishes",
    "is_established_by": "establishes",
    "regulates": "regulates",
    "is_regulated_by": "regulates",
    "is_funded_by": "is_funded_by",
    "is_composed_of": "is_composed_of",
    "are_composed_of": "is_composed_of",
    "limits": "limits",
    "includes": "applies_to",
    # Common verify-pass labels from legal extraction.
    "adopt_proposal": "approves",
    "adopts_proposal": "approves",
    "approve_repayment_schedule": "approves",
    "grant_deferral": "grants",
    "grants_deferral": "grants",
    "repay_loan": "requires",
    "ensure_accounting_and_control": "requires",
    "define_repayment_schedule": "sets_threshold",
    "be_allocated_for_purchase": "applies_to",
    "used_to_seal_signatures": "applies_to",
    "cannot_be_established_or_changed": "prohibits",
    "authorize_transfer": "delegates",
    "owe_debt": "applies_to",
    "seal": "applies_to",
    "amend": "amends",
    "establish": "establishes",
    "compensate": "grants",
    "transfer": "delegates",
    "enter_into_force": "enters_into_force",
    "finance_via": "is_funded_by",
    "submit": "requires",
    "submit_draft": "requires",
    "create": "establishes",
    "designate": "delegates",
    "resolve_issues": "requires",
    "start_from": "enters_into_force",
    "establish_fee": "establishes",
    "pay_fee": "requires",
    "reduce_taxable_base": "sets_threshold",
    "reduce_taxable_profit": "sets_threshold",
    "exceed_authority": "prohibits",
    "contradict_law": "prohibits",
    "suspend_operation": "prohibits",
    "is_inconsistent_with": "prohibits",
    "allocate_to_settlement": "grants",
    "owe": "applies_to",
    "прийняти_пропозицію": "approves",
    "наділити_управлінням": "delegates",
    # New labels observed in smoke runs.
    "declared_inconsistent": "prohibits",
    "inconsistent_with": "prohibits",
    "finance": "is_funded_by",
    "apply_to": "applies_to",
    "allocate": "grants",
    "is_conducted": "applies_to",
    "cooperate_with": "requires",
    "submit_by": "requires",
    "store_and_use": "requires",
    "approve": "approves",
    "submit_proposal": "requires",
    "act_based_on": "requires",
    "approve_proposal": "approves",
    "assign_to": "delegates",
}

_PERCENT_RE = re.compile(r"(?P<value>\d+(?:[\.,]\d+)?)\s*%")
_YEAR_RE = re.compile(r"(?P<value>\d+)\s*(?:рок(?:и|ів|у)?|years?)", re.IGNORECASE)


def _normalize_token(raw: str) -> str:
    # Keep Unicode word chars (including Cyrillic), collapse separators to "_".
    return re.sub(r"[^\w]+", "_", raw.strip().lower(), flags=re.UNICODE).strip("_")


def _heuristic_norm_type(token: str) -> str | None:
    """Map unseen norm labels by lexical cues."""
    if any(key in token for key in ("prohibit", "forbid", "ban", "must_not", "cannot")):
        return "prohibition"
    if any(key in token for key in ("permission", "right", "entitlement", "allowed")):
        return "permission"
    if any(key in token for key in ("exception", "exempt", "exclusion")):
        return "exception"
    if any(key in token for key in ("sanction", "penalty", "fine")):
        return "sanction"
    if any(key in token for key in ("delegat", "assign", "transfer")):
        return "delegation"
    if "amend" in token:
        return "amendment"
    if any(key in token for key in ("repeal", "supersed")):
        return "repeal"
    if any(key in token for key in ("entry", "force", "temporal", "start")):
        return "entry_into_force"
    if any(key in token for key in ("definition", "declar", "statement", "inclusion", "term")):
        return "definition"
    if any(key in token for key in ("procedure", "regulation", "rule", "act", "decree", "approval", "scope")):
        return "procedure"
    if any(key in token for key in ("obligation", "directive", "binding", "imperative", "must", "require")):
        return "obligation"
    return None


def _heuristic_action(token: str) -> str | None:
    """Map unseen action labels by lexical cues."""
    if any(key in token for key in ("inconsistent", "contradict", "prohibit", "forbid", "must_not", "cannot")):
        return "prohibits"
    if any(key in token for key in ("approve", "adopt")):
        return "approves"
    if "amend" in token:
        return "amends"
    if any(key in token for key in ("repeal", "supersed")):
        return "repeals"
    if any(key in token for key in ("delegate", "assign", "authorize_transfer", "transfer_to")):
        return "delegates"
    if any(key in token for key in ("grant", "allocate", "compensat", "provide")):
        return "grants"
    if any(key in token for key in ("finance", "fund")):
        return "is_funded_by"
    if any(key in token for key in ("threshold", "limit", "cap", "taxable", "percent", "rate", "reduce")):
        return "sets_threshold"
    if any(key in token for key in ("enter_into_force", "start_from", "effective_from")):
        return "enters_into_force"
    if any(key in token for key in ("establish", "create", "constitute")):
        return "establishes"
    if any(key in token for key in ("define", "describe", "term")):
        return "defines"
    if any(key in token for key in ("apply", "use", "seal", "conduct")):
        return "applies_to"
    if any(key in token for key in ("submit", "cooperate", "act_based_on", "store_and_use", "pay")):
        return "requires"
    return None


def canonicalize_norm_type(raw: str) -> tuple[str, bool]:
    """Return canonical norm type and whether value was out-of-vocabulary."""
    token = _normalize_token(raw)
    if token in _CORE_NORM_TYPES:
        return token, False
    if token in _NORM_TYPE_SYNONYMS:
        return _NORM_TYPE_SYNONYMS[token], False
    heuristic = _heuristic_norm_type(token)
    if heuristic is not None:
        return heuristic, False
    # Conservative fallback for unknown values.
    return "obligation", True


def canonicalize_action(raw: str) -> tuple[str, bool]:
    """Return canonical action and whether value was out-of-vocabulary."""
    token = _normalize_token(raw)
    if token in _CORE_ACTIONS:
        return token, False
    if token in _ACTION_SYNONYMS:
        return _ACTION_SYNONYMS[token], False
    heuristic = _heuristic_action(token)
    if heuristic is not None:
        return heuristic, False
    return "requires", True


def _decimal_text(value: str) -> str | None:
    normalized = value.replace(",", ".")
    try:
        decimal_value = Decimal(normalized)
    except InvalidOperation:
        return None
    return format(decimal_value.normalize(), "f")


def extract_thresholds_from_text(text: str, *, applies_to: str = "") -> list[ThresholdAtom]:
    """Extract simple thresholds (percentages + durations) from text."""
    thresholds: list[ThresholdAtom] = []
    if not text.strip():
        return thresholds

    for match in _PERCENT_RE.finditer(text):
        value_raw = match.group("value")
        value_decimal = _decimal_text(value_raw)
        thresholds.append(
            ThresholdAtom(
                metric="percent",
                operator="lte",
                value_decimal=value_decimal,
                value_text=value_raw,
                unit="percent",
                applies_to=applies_to or None,
            )
        )

    for match in _YEAR_RE.finditer(text):
        value_raw = match.group("value")
        value_decimal = _decimal_text(value_raw)
        thresholds.append(
            ThresholdAtom(
                metric="duration",
                operator="gte",
                value_decimal=value_decimal,
                value_text=value_raw,
                unit="year",
                applies_to=applies_to or None,
            )
        )

    return thresholds
