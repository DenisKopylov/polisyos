"""Rule-based pre-classifier for Ukrainian legal provisions.

Classifies provisions into three categories before LLM extraction:
- skip: non-normative content (signatures, dates, short fragments)
- auto: simple patterns extractable without LLM (approval, repeal, entry-into-force)
- llm: requires full LLM extraction
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Skip patterns: signatures, short text, non-normative headers
# ---------------------------------------------------------------------------

_SKIP_PATTERNS: list[re.Pattern[str]] = [
    # Signatures / officials at the end of documents
    re.compile(
        r"^(?:Прем.єр[\s-]?[Мм]іністр|Міністр\s|Голова\s|Секретар\s|Президент\s|Директор\s)"
        r".*$",
        re.IGNORECASE,
    ),
    re.compile(r"^\s*Виконавець\s*[:\-].*$", re.IGNORECASE),
    # Index lines like "Інд. 49" or numbering artifacts
    re.compile(r"^(?:Інд\.\s?\d|_{3,}|[=]{3,}|\*{3,})", re.IGNORECASE),
    # Purely procedural headers with no normative content
    re.compile(r"^(?:ЗМІСТ|ПЕРЕЛІК СКОРОЧЕНЬ|СПИСОК|Примітка)\s*$", re.IGNORECASE),
    re.compile(r"^\s*ДОДАТ(?:ОК|КИ)\b", re.IGNORECASE),
    re.compile(r"^\s*СКЛАД\b", re.IGNORECASE),
    re.compile(r"^\s*СХЕМА\b", re.IGNORECASE),
    re.compile(r"^\s*ЗАЯВКА\b", re.IGNORECASE),
    # Just a date or number reference
    re.compile(r"^\d{1,2}\s+(?:січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня)\s+\d{4}\s*(?:року|р\.?)?\s*$", re.IGNORECASE),
]

_MIN_TEXT_LENGTH = 40  # provisions shorter than this are skipped

# ---------------------------------------------------------------------------
# Auto-extract patterns: simple one-statement provisions
# ---------------------------------------------------------------------------

_AUTO_APPROVE = re.compile(
    r"(?:затвердити|схвалити|ухвалити|прийняти)\s+(.{10,200})",
    re.IGNORECASE,
)

_AUTO_REPEAL = re.compile(
    r"визнати\s+(?:таки(?:м|ми)\s*,?\s*що\s*втратил(?:и|а|о)\s+чинність|"
    r"такими\s*що\s*втратили\s+чинність)\s*(.{0,300})",
    re.IGNORECASE,
)

_AUTO_ENTRY_INTO_FORCE = re.compile(
    r"(?:набирає|набуває)\s+чинності?\s*(.{0,200})",
    re.IGNORECASE,
)

_AUTO_AMEND = re.compile(
    r"(?:внести\s+(?:такі\s+)?зміни|викласти\s+в\s+(?:такій\s+)?(?:новій\s+)?редакції)",
    re.IGNORECASE,
)

_AUTO_DELEGATE = re.compile(
    r"(?:доручити|покласти\s+на|уповноважити)\s+(.{10,200}?)\s+(?:забезпечити|контроль|виконання|здійснення|підготовку|розроб)",
    re.IGNORECASE,
)

_AUTO_DEFINE = re.compile(
    r"(?:під\s+терміном|у\s+цьому\s+(?:Законі|Кодексі|Порядку|Положенні).*?терміни\s+вживаються|"
    r"для\s+цілей\s+цього.*?терміни)",
    re.IGNORECASE,
)

_AUTO_BUDGET = re.compile(
    r"(?:передбачити\s+(?:у|в)\s+(?:бюджет|кошторис|видатках)|виділити\s+кошт|"
    r"здійснити\s+фінансування|фінансувати\s+за\s+рахунок)\s*(.{0,200})",
    re.IGNORECASE,
)

_AUTO_REGISTER = re.compile(
    r"(?:зареєструвати|опублікувати|оприлюднити)\s+(?:в|у|на)\s+(.{5,200})",
    re.IGNORECASE,
)

_AUTO_CONTROL = re.compile(
    r"контроль\s+(?:за\s+виконанням|покласти\s+на)\s*(.{5,200})",
    re.IGNORECASE,
)
_AUTO_APPROVAL_BUNDLE_ITEM = re.compile(
    r"^\s*(?:\d+[.)]|[а-яіїєґ]\))\s+(?P<object>.{10,260}?)(?:\s*\((?:додат(?:ок|ки))\s*(?:N|№)?\s*[\w\-]+\))\.?\s*$",
    re.IGNORECASE,
)
_AUTO_IMPERATIVE_ITEM = re.compile(
    r"^\s*(?:[-\u2013\u2014\u2022]|\d+[.)]|[а-яіїєґ]\))\s*(?P<lemma>з['’`ʼ]?ясувати|надіслати|опитати|"
    r"виконувати|забезпечувати|сплатити|провести|подати|повідомити|зареєструвати|оприлюднити|"
    r"забезпечити|підготувати|розробити|здійснити)\b(?P<object>.{0,260})",
    re.IGNORECASE,
)
_AUTO_APPLICANT_HEADER = re.compile(r"заявник\s+зобов['’`ʼ]язується", re.IGNORECASE)
_AUTO_TABLE_THRESHOLD = re.compile(
    r"^\s*(?P<label>[^*\n]{3,90}?)\s*\*\s*(?P<value>\d+(?:[.,]\d+)?)\s*$",
    re.IGNORECASE,
)
_TITLE_APPROVAL_RE = re.compile(r"(затвердження|затвердити|схвалення|схвалити)", re.IGNORECASE)
_TITLE_AMEND_RE = re.compile(r"(внесення змін|доповнень|внести зміни|зміни до)", re.IGNORECASE)
_BUNDLE_OBJECT_RE = re.compile(
    r"\b(положення|правила|порядок|інструкц(?:ія|ії)|перелік|вимоги|форма|схема|зміни|доповнення)\b",
    re.IGNORECASE,
)
_ROLE_WORDS = (
    "міністр",
    "заступник",
    "начальник",
    "директор",
    "голова",
    "секретар",
    "спеціаліст",
    "управління",
    "відділу",
    "кабінету",
    "міненерго",
    "мінфіну",
    "мінекономіки",
)
_UPPERCASE_TOKEN_RE = re.compile(r"\b[А-ЯІЇЄҐ]{2,}\b")
_DECORATIVE_SEPARATOR_RE = re.compile(r"^[\s*._\-–—=|/\\()]+$")
_TABLE_SCAFFOLD_KEEP_CUES_RE = re.compile(
    r"\b(повин|має|зобов|заборон|дозвол|мінімаль|максималь|оклад|грн|відсот|кг|см|мм|дата)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ClassificationResult:
    """Result of rule-based provision classification."""

    action: str  # "skip" | "auto" | "llm"
    auto_statements: list[dict[str, str]] = field(default_factory=list)
    skip_reason: str = ""


def _compact_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _looks_like_composition_member(text: str) -> bool:
    compact = _compact_spaces(text)
    lower = compact.lower()
    if not compact.startswith(("-", "–", "—", "•")):
        return False
    if re.search(r"\b(виконувати|забезпечувати|сплатити|з['’`ʼ]?ясувати|надіслати|опитати)\b", lower):
        return False
    role_hits = sum(1 for word in _ROLE_WORDS if word in lower)
    uppercase_hits = len(_UPPERCASE_TOKEN_RE.findall(compact))
    if role_hits < 1 or re.search(r"\d", compact):
        return False
    if uppercase_hits >= 1:
        return True
    return len(compact.split()) <= 12


def _looks_like_blank_form_field(text: str) -> bool:
    compact = _compact_spaces(text)
    lower = compact.lower()
    if lower.startswith(("керівнику ", "органу з сертифікації ", "заявка ")):
        return True
    if compact.count("_") >= 8:
        return True
    return ("найменування" in lower or "адреса" in lower or "назва" in lower) and "_" in compact


def _looks_like_table_scaffold(text: str) -> bool:
    compact = _compact_spaces(text)
    if not compact:
        return True
    if _DECORATIVE_SEPARATOR_RE.fullmatch(compact):
        return True

    stars = compact.count("*")
    if stars < 3:
        return False

    letters = sum(ch.isalpha() for ch in compact)
    digits = sum(ch.isdigit() for ch in compact)
    if letters <= 6 and digits <= 2:
        return True

    if compact.startswith("*") and compact.endswith("*"):
        cells = [cell.strip(" *|-:") for cell in re.split(r"\*+|\|+| {2,}", compact) if cell.strip(" *|-:")]
        if len(cells) <= 1:
            return True
        if len(cells) >= 2 and all(len(cell) <= 3 for cell in cells):
            return True

    return compact.startswith("*") and digits == 0 and not _TABLE_SCAFFOLD_KEEP_CUES_RE.search(compact)


def classify_provision(text: str, citation: str = "", doc_title: str = "") -> ClassificationResult:
    """Classify a provision for skip/auto/llm processing.

    Returns a ClassificationResult with:
    - action="skip" for non-normative content
    - action="auto" with pre-built statements for trivial extractable patterns
    - action="llm" for everything else
    """
    stripped = text.strip()
    compact = _compact_spaces(stripped)
    title_lower = (doc_title or "").lower()
    short_allow = bool(_AUTO_IMPERATIVE_ITEM.search(stripped) or _AUTO_TABLE_THRESHOLD.match(compact))

    # --- Skip checks ---
    if len(stripped) < _MIN_TEXT_LENGTH and not short_allow:
        return ClassificationResult(action="skip", skip_reason="too_short")

    # Check if text is just whitespace/punctuation after stripping
    if not re.search(r"[а-яА-ЯіїєґІЇЄҐa-zA-Z]", stripped):
        return ClassificationResult(action="skip", skip_reason="no_text_content")

    if _looks_like_blank_form_field(stripped):
        return ClassificationResult(action="skip", skip_reason="blank_form_field")

    if _looks_like_table_scaffold(stripped):
        return ClassificationResult(action="skip", skip_reason="table_scaffold")

    if _looks_like_composition_member(stripped):
        return ClassificationResult(action="skip", skip_reason="composition_member")

    for pattern in _SKIP_PATTERNS:
        if pattern.search(stripped):
            return ClassificationResult(action="skip", skip_reason="pattern_match")

    # --- Auto-extract checks ---
    m = _AUTO_APPROVAL_BUNDLE_ITEM.match(compact)
    if m and _BUNDLE_OBJECT_RE.search(m.group("object") or ""):
        obj = (m.group("object") or "").strip().rstrip(".")
        if _TITLE_APPROVAL_RE.search(title_lower):
            return ClassificationResult(
                action="auto",
                auto_statements=[{
                    "subject_uk": "орган, що прийняв акт",
                    "predicate": "approves",
                    "object_uk": obj,
                    "norm_type": "procedure",
                    "fact_text": f"Затверджено додаток: {obj}",
                    "source_quote_uk": compact[:240],
                    "confidence": "0.92",
                }],
            )
        if _TITLE_AMEND_RE.search(title_lower):
            return ClassificationResult(
                action="auto",
                auto_statements=[{
                    "subject_uk": "орган, що прийняв акт",
                    "predicate": "amends",
                    "object_uk": obj,
                    "norm_type": "amendment",
                    "fact_text": f"Внесено зміни/доповнення: {obj}",
                    "source_quote_uk": compact[:240],
                    "confidence": "0.90",
                }],
            )

    m = _AUTO_IMPERATIVE_ITEM.match(stripped)
    if m:
        lemma = (m.group("lemma") or "").strip()
        obj = (m.group("object") or "").strip(" .;:")
        subject = "заявник" if any(key in (title_lower + " " + compact.lower()) for key in ("заявка", "сертифікац", "заявник")) else "адресат акта"
        fact_text = f"Необхідно {lemma}"
        if obj:
            fact_text += f" {obj}"
        return ClassificationResult(
            action="auto",
            auto_statements=[{
                "subject_uk": subject,
                "predicate": "requires",
                "object_uk": obj or lemma,
                "norm_type": "obligation",
                "fact_text": fact_text,
                "source_quote_uk": compact[:240],
                "confidence": "0.88",
            }],
        )

    if _AUTO_APPLICANT_HEADER.search(stripped):
        return ClassificationResult(
            action="auto",
            auto_statements=[{
                "subject_uk": "заявник",
                "predicate": "requires",
                "object_uk": "виконувати умови сертифікації",
                "norm_type": "obligation",
                "fact_text": "Заявник зобов'язується виконувати умови сертифікації",
                "source_quote_uk": compact[:240],
                "confidence": "0.87",
            }],
        )

    m = _AUTO_TABLE_THRESHOLD.match(compact)
    if m:
        label = (m.group("label") or "").strip(" -:")
        value = (m.group("value") or "").strip()
        if label and value:
            return ClassificationResult(
                action="auto",
                auto_statements=[{
                    "subject_uk": "цей акт",
                    "predicate": "sets_threshold",
                    "object_uk": label,
                    "norm_type": "procedure",
                    "fact_text": f"Встановлено значення {value} для {label}",
                    "source_quote_uk": compact[:240],
                    "confidence": "0.9",
                }],
            )

    m = _AUTO_APPROVE.search(stripped)
    if m and len(stripped) < 500:
        obj = m.group(1).strip().rstrip(".")
        return ClassificationResult(
            action="auto",
            auto_statements=[{
                "subject_uk": "орган, що прийняв акт",
                "predicate": "approves",
                "object_uk": obj,
                "norm_type": "procedure",
                "fact_text": f"Затверджено: {obj}",
                "source_quote_uk": stripped[:200],
                "confidence": "0.9",
            }],
        )

    m = _AUTO_REPEAL.search(stripped)
    if m and len(stripped) < 500:
        obj = m.group(1).strip().rstrip(".") or "перелічені акти"
        return ClassificationResult(
            action="auto",
            auto_statements=[{
                "subject_uk": "орган, що прийняв акт",
                "predicate": "repeals",
                "object_uk": obj,
                "norm_type": "repeal",
                "fact_text": f"Визнано такими, що втратили чинність: {obj}",
                "source_quote_uk": stripped[:200],
                "confidence": "0.9",
            }],
        )

    m = _AUTO_ENTRY_INTO_FORCE.search(stripped)
    if m and len(stripped) < 300:
        detail = m.group(1).strip().rstrip(".") or ""
        fact = "Акт набирає чинності"
        if detail:
            fact += f" {detail}"
        return ClassificationResult(
            action="auto",
            auto_statements=[{
                "subject_uk": "цей акт",
                "predicate": "enters_into_force",
                "object_uk": detail or "з дня опублікування",
                "norm_type": "entry_into_force",
                "fact_text": fact,
                "source_quote_uk": stripped[:200],
                "confidence": "0.9",
            }],
        )

    m = _AUTO_AMEND.search(stripped)
    if m and len(stripped) < 300:
        return ClassificationResult(
            action="auto",
            auto_statements=[{
                "subject_uk": "орган, що прийняв акт",
                "predicate": "amends",
                "object_uk": "зазначений акт",
                "norm_type": "amendment",
                "fact_text": "Внесено зміни до акту",
                "source_quote_uk": stripped[:200],
                "confidence": "0.85",
            }],
        )

    m = _AUTO_DELEGATE.search(stripped)
    if m and len(stripped) < 500:
        obj = m.group(1).strip().rstrip(".")
        return ClassificationResult(
            action="auto",
            auto_statements=[{
                "subject_uk": "орган, що прийняв акт",
                "predicate": "delegates",
                "object_uk": obj,
                "norm_type": "delegation",
                "fact_text": f"Доручено: {obj}",
                "source_quote_uk": stripped[:200],
                "confidence": "0.85",
            }],
        )

    m = _AUTO_DEFINE.search(stripped)
    if m and len(stripped) < 500:
        return ClassificationResult(
            action="auto",
            auto_statements=[{
                "subject_uk": "цей акт",
                "predicate": "defines",
                "object_uk": "терміни та визначення",
                "norm_type": "definition",
                "fact_text": "Визначено терміни, що вживаються в акті",
                "source_quote_uk": stripped[:200],
                "confidence": "0.87",
            }],
        )

    m = _AUTO_BUDGET.search(stripped)
    if m and len(stripped) < 500:
        detail = (m.group(1) or "").strip().rstrip(".") if m.lastindex else ""
        obj = detail or "фінансування заходів"
        return ClassificationResult(
            action="auto",
            auto_statements=[{
                "subject_uk": "орган, що прийняв акт",
                "predicate": "is_funded_by",
                "object_uk": obj,
                "norm_type": "procedure",
                "fact_text": f"Передбачено фінансування: {obj}",
                "source_quote_uk": stripped[:200],
                "confidence": "0.84",
            }],
        )

    m = _AUTO_REGISTER.search(stripped)
    if m and len(stripped) < 400:
        obj = m.group(1).strip().rstrip(".")
        return ClassificationResult(
            action="auto",
            auto_statements=[{
                "subject_uk": "орган, що прийняв акт",
                "predicate": "requires",
                "object_uk": obj,
                "norm_type": "procedure",
                "fact_text": f"Зареєструвати/опублікувати в: {obj}",
                "source_quote_uk": stripped[:200],
                "confidence": "0.88",
            }],
        )

    m = _AUTO_CONTROL.search(stripped)
    if m and len(stripped) < 400:
        obj = m.group(1).strip().rstrip(".")
        return ClassificationResult(
            action="auto",
            auto_statements=[{
                "subject_uk": "орган, що прийняв акт",
                "predicate": "delegates",
                "object_uk": obj,
                "norm_type": "delegation",
                "fact_text": f"Контроль покладено на: {obj}",
                "source_quote_uk": stripped[:200],
                "confidence": "0.86",
            }],
        )

    # --- Default: LLM ---
    return ClassificationResult(action="llm")
