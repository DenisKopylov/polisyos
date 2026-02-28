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
    # Index lines like "Інд. 49" or numbering artifacts
    re.compile(r"^(?:Інд\.\s?\d|_{3,}|[=]{3,}|\*{3,})", re.IGNORECASE),
    # Purely procedural headers with no normative content
    re.compile(r"^(?:ЗМІСТ|ПЕРЕЛІК СКОРОЧЕНЬ|ДОДАТ(?:ОК|КИ)|СПИСОК|Примітка)\s*$", re.IGNORECASE),
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


@dataclass(frozen=True)
class ClassificationResult:
    """Result of rule-based provision classification."""

    action: str  # "skip" | "auto" | "llm"
    auto_statements: list[dict[str, str]] = field(default_factory=list)
    skip_reason: str = ""


def classify_provision(text: str, citation: str = "") -> ClassificationResult:
    """Classify a provision for skip/auto/llm processing.

    Returns a ClassificationResult with:
    - action="skip" for non-normative content
    - action="auto" with pre-built statements for trivial extractable patterns
    - action="llm" for everything else
    """
    stripped = text.strip()

    # --- Skip checks ---
    if len(stripped) < _MIN_TEXT_LENGTH:
        return ClassificationResult(action="skip", skip_reason="too_short")

    # Check if text is just whitespace/punctuation after stripping
    if not re.search(r"[а-яА-ЯіїєґІЇЄҐa-zA-Z]", stripped):
        return ClassificationResult(action="skip", skip_reason="no_text_content")

    for pattern in _SKIP_PATTERNS:
        if pattern.search(stripped):
            return ClassificationResult(action="skip", skip_reason="pattern_match")

    # --- Auto-extract checks ---
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
