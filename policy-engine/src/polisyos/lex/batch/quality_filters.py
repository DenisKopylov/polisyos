"""Shared quality filters for deterministic Lex extraction."""

from __future__ import annotations

import re

SYNTHETIC_SUBJECTS: frozenset[str] = frozenset(
    {
        "орган, що прийняв акт",
        "суб'єкт правовідносин",
        "адресат акта",
        "адресат норми",
        "цей акт",
    }
)

_MONTH_NAME_RE = re.compile(
    r"\b(січ(?:ень|ня)|лют(?:ий|ого)|берез(?:ень|ня)|квіт(?:ень|ня)|"
    r"трав(?:ень|ня)|черв(?:ень|ня)|лип(?:ень|ня)|серп(?:ень|ня)|"
    r"верес(?:ень|ня)|жовт(?:ень|ня)|листопад(?:а|і)?|груд(?:ень|ня))\b",
    re.IGNORECASE,
)
_DATE_NUMERIC_RE = re.compile(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b")
_YEAR_REF_RE = re.compile(r"\b(?:від|станом\s+на|на|у)\s+\d{4}\s+роц", re.IGNORECASE)
_THRESHOLD_CUE_RE = re.compile(
    r"\b("
    r"не\s+менш(?:е| як)|не\s+більш(?:е| як)|не\s+нижче|не\s+вище|"
    r"мінімальн(?:ий|а|е|і)|максимальн(?:ий|а|е|і)|"
    r"ставк(?:а|и)|тариф|оклад|поріг|ліміт|квот|розмір|"
    r"не\s+перевищує|становить|становлять|у\s+розмірі"
    r")\b",
    re.IGNORECASE,
)
_THRESHOLD_UNIT_CUE_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:%|грн|коп|кг|км|га|тонн(?:и)?|дн(?:ів|і)?|місяц(?:ів|і)?|рок(?:ів|и)?)\b",
    re.IGNORECASE,
)
_THRESHOLD_NOISE_RE = re.compile(
    r"\b("
    r"приклад|наприклад|у\s+графі|у\s+рядку|у\s+колонц|"
    r"довідково|зразок|примітк(?:а|и)|зареєстровано|від\s+\d{1,2}[./-]\d{1,2}[./-]\d{2,4}"
    r")\b",
    re.IGNORECASE,
)
_LOW_QUALITY_ENTITY_RE = re.compile(
    r"\b("
    r"доповнено|доповнити|виключено|виключити|замінити|замінено|"
    r"викласти\s+в\s+такій\s+редакції|внесення\s+змін|про\s+внесення\s+змін|"
    r"згідно\s+з|в\s+редакції|втратив(?:ла|ли)?\s+чинність|скасувати|"
    r"пункт(?:ом|у|а)?\s+\d|статт(?:і|ю|я)\s+\d"
    r")\b",
    re.IGNORECASE,
)
_SENTENCE_VERB_RE = re.compile(
    r"\b("
    r"є|було|були|бути|має|мають|повинен|повинна|повинні|"
    r"встановлюється|визначається|затверджується|підлягає|"
    r"дозволяється|забороняється|не\s+дозволяється|не\s+допускається|"
    r"прийняла|прийнято|ухвалено|визнати|визнається"
    r")\b",
    re.IGNORECASE,
)
_EXPLICIT_MODAL_RE = re.compile(
    r"\b("
    r"повинен|повинна|повинні|зобов['’`ʼ]?язан|"
    r"має\s+право|мають\s+право|"
    r"забороняється|заборонено|не\s+допускається|не\s+має\s+права|"
    r"підлягає|необхідно|слід"
    r")\b",
    re.IGNORECASE,
)


def compact_text(text: str) -> str:
    """Normalize whitespace before running rule-based quality heuristics."""

    return re.sub(r"\s+", " ", str(text or "")).strip()


def is_synthetic_subject(text: str) -> bool:
    """Return whether a subject is one of the synthetic Lex placeholders."""

    return compact_text(text).lower() in SYNTHETIC_SUBJECTS


def has_explicit_threshold_cue(text: str) -> bool:
    """Detect Ukrainian-specific wording that usually introduces thresholds."""

    compact = compact_text(text)
    if not compact:
        return False
    return bool(_THRESHOLD_CUE_RE.search(compact) or _THRESHOLD_UNIT_CUE_RE.search(compact))


def is_threshold_noise_context(text: str) -> bool:
    """Detect contexts where numeric mentions are likely metadata noise."""

    compact = compact_text(text)
    if not compact:
        return False
    return bool(_THRESHOLD_NOISE_RE.search(compact))


def is_calendar_year_token(value_text: str, *, surrounding_text: str = "") -> bool:
    """Return whether a numeric token is more likely a calendar year than a threshold."""

    compact = compact_text(surrounding_text)
    try:
        year_value = int(str(value_text or "").strip())
    except ValueError:
        return False
    if 1900 <= year_value <= 2200:
        return True
    if not compact:
        return False
    return bool(
        _MONTH_NAME_RE.search(compact)
        or _DATE_NUMERIC_RE.search(compact)
        or _YEAR_REF_RE.search(compact)
    )


def is_low_quality_entity_text(text: str) -> bool:
    """Heuristically reject low-signal entity spans from deterministic extraction.

    The regex cues in this module are intentionally Ukrainian-specific because
    the current deterministic legal pipeline is optimized for UA legislation.
    """

    compact = compact_text(text)
    if not compact:
        return True
    lower = compact.lower()
    if is_synthetic_subject(compact):
        return True
    if lower in {"не визначено", "невідомо", "n/a", "none"}:
        return True
    token_count = len(compact.split())
    if len(compact) > 160 or token_count > 14:
        return True
    if compact[:1].islower() and token_count > 6:
        return True
    if re.match(r"^(у|на|при|для|щодо|від|за)\b", lower) and token_count > 5:
        return True
    if compact[0] in {"(", "[", '"', "'", "«"} and len(compact) >= 12:
        return True
    if _LOW_QUALITY_ENTITY_RE.search(compact):
        return True
    if compact.endswith(".") and token_count > 8:
        return True
    if compact.count(",") >= 2 and token_count > 10:
        return True
    if compact.count(".") >= 2 and token_count > 10:
        return True
    return bool(_SENTENCE_VERB_RE.search(compact) and token_count > 8)


def has_explicit_modal_signal(text: str) -> bool:
    """Detect explicit obligation, permission, or prohibition markers."""

    return bool(_EXPLICIT_MODAL_RE.search(compact_text(text)))
