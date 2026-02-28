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
    # Bulk norm_type synonyms from corpus analysis (Feb 2026).
    "fine": "sanction",
    "punishment": "sanction",
    "liability": "sanction",
    "responsibility": "sanction",
    "amnesty": "exception",
    "invalidation": "repeal",
    "void": "repeal",
    "scope": "definition",
    "composition": "definition",
    "structure": "definition",
    "location": "definition",
    "purpose": "definition",
    "classification": "definition",
    "designation": "definition",
    "ratification": "procedure",
    "appointment": "delegation",
    "subordination": "delegation",
    "replacement": "amendment",
    "revision": "amendment",
    "modification": "amendment",
    "exclusion_from_list": "exception",
    "restoration": "amendment",
    "enactment": "entry_into_force",
    "зобов_язання": "obligation",
    "заборона": "prohibition",
    "дозвіл": "permission",
    "визначення": "definition",
    "штраф": "sanction",
    "покарання": "sanction",
    "делегування": "delegation",
    "зміна": "amendment",
    "скасування": "repeal",
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
    "sanctions",
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
    # --- Bulk OOV mappings from corpus analysis (Feb 2026) ---
    # defines / definitions
    "is_defined_as": "defines",
    "are_defined_as": "defines",
    "is_determined_by": "defines",
    "is_designated_as": "defines",
    "determine": "defines",
    "determines": "defines",
    "означає": "defines",
    "визначається": "defines",
    "визначаються": "defines",
    "визначає": "defines",
    "є": "defines",
    # repeals / invalidation
    "recognizes_as_invalid": "repeals",
    "recognize_as_invalid": "repeals",
    "recognizes_as_invalid": "repeals",
    "declares_void": "repeals",
    "has_decision_invalidated": "repeals",
    # sanctions / fines / punishment
    "imposes_fine": "sanctions",
    "impose_fine": "sanctions",
    "imposes_fine": "sanctions",
    "shall_be_fined": "sanctions",
    "is_punishable_by": "sanctions",
    "imposes_punishment": "sanctions",
    "is_subject_to_punishment": "sanctions",
    "subject_to_fine": "sanctions",
    "bears_responsibility_for": "sanctions",
    "bears_responsibility": "sanctions",
    "bear_responsibility": "sanctions",
    "bears_personal_responsibility": "sanctions",
    "shall_be_released_from_punishment": "sanctions",
    # applies_to / scope
    "are_subject_to": "applies_to",
    "subject_to": "applies_to",
    "include": "applies_to",
    "contains": "applies_to",
    "is_located_at": "applies_to",
    "is_located_in": "applies_to",
    "located_in": "applies_to",
    "is_part_of": "applies_to",
    "belongs_to_category": "applies_to",
    "is_based_on": "applies_to",
    "is_governed_by": "applies_to",
    "is_conducted_by": "applies_to",
    "is_conducted_according_to": "applies_to",
    "is_conducted_in_accordance_with": "applies_to",
    "consists_of": "is_composed_of",
    "is": "applies_to",
    "can_be": "applies_to",
    "can_be_made_in_form_of": "applies_to",
    "has_purpose": "applies_to",
    "is_ensured_by": "applies_to",
    "depends_on": "applies_to",
    "results_in": "applies_to",
    "covers": "applies_to",
    "participates_in": "applies_to",
    "participates_in_development": "applies_to",
    "складають": "applies_to",
    "розглядаються": "applies_to",
    "розглядає": "applies_to",
    "розглядають_спори_про": "applies_to",
    "містить": "applies_to",
    "становить": "sets_threshold",
    "включає": "applies_to",
    # grants / permissions / rights
    "have_right_to": "grants",
    "is_entitled_to": "grants",
    "has_right_to_demand": "grants",
    "has_right_to_obtain_information": "grants",
    "has_right_to_claim_compensation": "grants",
    "has_power_to": "grants",
    "has_authority_to": "grants",
    "allows": "grants",
    "are_entitled_to": "grants",
    "are_eligible_for_amnesty": "grants",
    "має_право": "grants",
    "має_право_на_одержання_патенту": "grants",
    "звільняються_від_усіх_податків_і_мит_особистих_і_майнових_державних_районних_і_муніципальних": "grants",
    "звільняє_від_податків_і_зборів": "grants",
    # prohibits
    "is_prohibited": "prohibits",
    "is_prohibited_from": "prohibits",
    "are_prohibited_from": "prohibits",
    "забороняється": "prohibits",
    "не_застосовуються": "excludes",
    "суперечать": "prohibits",
    "суперечить": "prohibits",
    "не_визнається_порушенням_прав": "excludes",
    # enters_into_force
    "introduce_into_force": "enters_into_force",
    "adopted": "enters_into_force",
    "approved": "approves",
    # approves / adoption
    "adopts_resolution": "approves",
    "adopts_decision": "approves",
    "adopts": "approves",
    "ratifies": "approves",
    "ratifies_agreement": "approves",
    "approves_list": "approves",
    "shall_approve": "approves",
    "затверджує": "approves",
    # delegates / appointments
    "appoints": "delegates",
    "is_appointed_by": "delegates",
    "is_assigned_to": "delegates",
    "is_subordinate_to": "delegates",
    "is_subordinated_to": "delegates",
    "issues_order": "delegates",
    "decides": "delegates",
    # requires / obligations
    "develops": "requires",
    "shall_ensure": "requires",
    "must_ensure": "requires",
    "ensures": "requires",
    "must_submit": "requires",
    "must_provide": "requires",
    "must_notify": "requires",
    "must_include": "requires",
    "must_have": "requires",
    "must_be": "requires",
    "must_be_equipped_with": "requires",
    "must_contain": "requires",
    "must_know": "requires",
    "must_maintain": "requires",
    "must_display": "requires",
    "must_be_at_least": "sets_threshold",
    "shall_develop": "requires",
    "shall_produce": "requires",
    "shall_submit": "requires",
    "shall_submit_proposals": "requires",
    "shall_conduct": "requires",
    "shall_cooperate": "requires",
    "shall_define": "defines",
    "shall_promote": "requires",
    "shall_take_measures": "requires",
    "shall_supply": "requires",
    "submit_proposals": "requires",
    "submits_proposal": "requires",
    "submits_proposals": "requires",
    "provide_information": "requires",
    "is_responsible_for": "requires",
    "are_responsible_for": "requires",
    "responsible_for": "requires",
    "conducts_control": "requires",
    "exercises_control": "requires",
    "conduct": "requires",
    "develop": "requires",
    "produces": "requires",
    "produced_by": "requires",
    "creates": "establishes",
    "shall_be_developed_by": "requires",
    "здійснюється": "requires",
    "повідомляє": "requires",
    "повідомляє_заявника": "requires",
    "видається": "requires",
    "вказує": "requires",
    # amends
    "replace_text": "amends",
    "replace_word": "amends",
    "replace": "amends",
    "replace_with": "amends",
    "replaces_text": "amends",
    "amends_text": "amends",
    "amends_regulation": "amends",
    "is_amended": "amends",
    "is_amended_by_addition": "amends",
    "shall_be_amended": "amends",
    "is_replaced_with": "amends",
    "enacts_amendment": "amends",
    "amended": "amends",
    "замінити": "amends",
    "замінити_слова": "amends",
    "замінюються": "amends",
    "вносить_зміни_до": "amends",
    "змінюється": "amends",
    "викладається_в_новій_редакції": "amends",
    "викладено_в_новій_редакції": "amends",
    "викладена_в_новій_редакції": "amends",
    # excludes
    "exclude": "excludes",
    "excludes_text": "excludes",
    "exclude_text": "excludes",
    "excluded_from_amnesty": "excludes",
    "is_excluded_from": "excludes",
    "is_exempt_from_land_tax": "excludes",
    "виключити": "excludes",
    "виключається": "excludes",
    "вважається_відкликаною": "excludes",
    # is_funded_by
    "is_financed_from": "is_funded_by",
    "allocate_funds": "is_funded_by",
    # is_composed_of / structure
    "develops_and_produces": "is_composed_of",
    "has_judge_count": "sets_threshold",
    "has_hunting_quota": "sets_threshold",
    "has_hunting_quota_for": "sets_threshold",
    "has_production_volume": "sets_threshold",
    "has_primary_task": "defines",
    # restoring / renaming
    "restores_name": "amends",
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
    # Sanctions / fines / punishment (check early — "fine" can appear in "define")
    if any(key in token for key in ("fine", "punish", "responsib", "штраф")):
        return "sanctions"
    if any(key in token for key in ("inconsistent", "contradict", "prohibit", "forbid", "must_not", "cannot",
                                     "заборон", "суперечи")):
        return "prohibits"
    if any(key in token for key in ("approve", "adopt", "ratif", "затверд")):
        return "approves"
    if any(key in token for key in ("amend", "replace", "замін", "виклад", "зміню")):
        return "amends"
    if any(key in token for key in ("repeal", "supersed", "invalid", "void", "втрат")):
        return "repeals"
    if any(key in token for key in ("delegate", "assign", "appoint", "subordinat", "призначи")):
        return "delegates"
    if any(key in token for key in ("grant", "allocat", "compensat", "provide", "right_to", "entitled",
                                     "eligible", "право", "звільн")):
        return "grants"
    if any(key in token for key in ("finance", "fund", "фінанс")):
        return "is_funded_by"
    if any(key in token for key in ("threshold", "limit", "cap", "taxable", "percent", "rate", "reduce",
                                     "quota", "volume", "count", "становить")):
        return "sets_threshold"
    if any(key in token for key in ("enter_into_force", "start_from", "effective_from", "introduce_into",
                                     "набира")):
        return "enters_into_force"
    if any(key in token for key in ("establish", "create", "constitute", "створ")):
        return "establishes"
    if any(key in token for key in ("define", "describe", "term", "визнач", "означа")):
        return "defines"
    if any(key in token for key in ("exclud", "exempt", "виключ", "не_застосов")):
        return "excludes"
    if any(key in token for key in ("apply", "use", "seal", "conduct", "located", "part_of",
                                     "subject_to", "consist", "belong", "contain", "cover",
                                     "розгляд", "містить", "включа", "складаю")):
        return "applies_to"
    if any(key in token for key in ("submit", "cooperate", "act_based_on", "store_and_use", "pay",
                                     "ensure", "must_", "shall_", "develop", "produc", "notify",
                                     "maintain", "must_know", "display", "control", "здійсню", "повідомл",
                                     "забезпеч")):
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
