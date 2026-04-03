"""Prompt templates for 2-pass LLM-based extraction from Ukrainian legal provisions."""

from __future__ import annotations

import json

SPO_PROMPT_VERSION = "lex_spo_v2"

# Pass 1: Extraction
SPO_EXTRACT_SYSTEM_PROMPT = """\
You are an expert in legal analysis of Ukrainian legislation (НПА).
Extract structured legal statements from one provision.

Output valid JSON only:
{"statements": [<statement>, ...]}

Each statement must include fields:
- subject_en, subject_uk, predicate, object_en, object_uk, fact_text, confidence, norm_type
- action_raw, action_canon
- norm_type_raw, norm_type_canon
- condition_text_uk, exception_text_uk, procedure_text_uk
- source_quote_uk, source_quote_start, source_quote_end
- thresholds (array of objects: metric, operator, value_decimal, value_text, unit, applies_to)

CANONICAL VOCABULARIES (use ONLY these values for action_canon and norm_type_canon):

action_canon MUST be one of:
requires, prohibits, grants, delegates, sets_threshold, applies_to, defines, revokes,
enters_into_force, amends, repeals, approves, excludes, establishes, regulates,
must_comply_with, must_not_exceed, is_funded_by, is_composed_of, limits, sanctions

norm_type_canon MUST be one of:
obligation, prohibition, permission, definition, procedure, exception, sanction,
delegation, amendment, repeal, entry_into_force

Rules:
1) Preserve Ukrainian legal wording in *_uk fields.
2) predicate and action_canon MUST use values from the canonical vocabulary above.
3) norm_type_canon MUST use values from the canonical vocabulary above.
4) If conditions/exceptions/procedure are missing, return empty string fields.
5) source_quote_uk should be the shortest verbatim quote supporting the statement.
6) Maximum 5 statements.
"""

# Batched extraction: multiple provisions in one request.
SPO_EXTRACT_BATCH_SYSTEM_PROMPT = """\
You are an expert in legal analysis of Ukrainian legislation (НПА).
Extract structured legal statements for multiple provisions in one pass.

Output valid JSON only:
{"items":[{"id":"<input_id>","statements":[<statement>, ...]}, ...]}

Rules:
1) Return exactly one output item for each input id.
2) Preserve input ids exactly as provided.
3) Follow the same statement schema as single-provision extraction.
4) Maximum 5 statements per item.
"""

# Pass 2: Verify + normalize
SPO_VERIFY_SYSTEM_PROMPT = """\
You verify and normalize extracted legal statements against the same source provision.

Input contains:
- source provision text
- extracted JSON from pass 1

Tasks:
1) Remove unsupported statements.
2) Correct wrong roles/objects/conditions/thresholds.
3) Canonicalize action_canon and norm_type_canon using strict vocabularies.
4) Ensure each retained statement has source_quote_uk and quote offsets.
5) Return low_confidence=true if statement quality remains uncertain.

Output valid JSON only:
{
  "statements": [...],
  "low_confidence": <true|false>,
  "low_confidence_reasons": ["..."],
  "verify_report": {
    "input_count": <int>,
    "output_count": <int>,
    "dropped_count": <int>
  }
}
"""


def build_spo_extract_user_prompt(
    *,
    provision_text: str,
    doc_title: str,
    doc_type: str,
    publisher: str,
    date_acc: str,
    provision_citation: str,
) -> str:
    """Build user prompt for extraction pass."""
    return (
        f"DOCUMENT: {doc_title}\n"
        f"Type: {doc_type} | Publisher: {publisher} | Date: {date_acc}\n"
        f"PROVISION ({provision_citation}):\n"
        f"{provision_text}"
    )


def build_spo_extract_batch_user_prompt(
    *,
    items: list[dict[str, str]],
) -> str:
    """Build user prompt for batched extraction pass."""
    payload = json.dumps(items, ensure_ascii=False)
    return (
        "Extract SPO statements for each input item.\n"
        "Return JSON with top-level key 'items' and the same ids.\n"
        "INPUT_ITEMS_JSON:\n"
        f"{payload}"
    )


def build_spo_verify_user_prompt(
    *,
    provision_text: str,
    extracted_json: str,
    provision_citation: str,
) -> str:
    """Build user prompt for verify+normalize pass."""
    return (
        f"PROVISION ({provision_citation}):\n"
        f"{provision_text}\n\n"
        "EXTRACTED_JSON_PASS1:\n"
        f"{extracted_json}"
    )


# Backward compatibility for older call-sites.
def build_spo_user_prompt(
    *,
    provision_text: str,
    doc_title: str,
    doc_type: str,
    publisher: str,
    date_acc: str,
    provision_citation: str,
) -> str:
    """Build spo user prompt."""
    return build_spo_extract_user_prompt(
        provision_text=provision_text,
        doc_title=doc_title,
        doc_type=doc_type,
        publisher=publisher,
        date_acc=date_acc,
        provision_citation=provision_citation,
    )


# -----------------------------------------------------------------------
# Light extraction: compact 7-field schema with closed vocabulary
# -----------------------------------------------------------------------

SPO_LIGHT_PROMPT_VERSION = "lex_spo_light_v1"

_LIGHT_ACTIONS = (
    "requires|prohibits|grants|delegates|sets_threshold|defines|establishes|"
    "approves|amends|repeals|enters_into_force|excludes|regulates|limits|"
    "applies_to|sanctions"
)
_LIGHT_NORM_TYPES = (
    "obligation|prohibition|permission|definition|procedure|exception|"
    "sanction|delegation|amendment|repeal|entry_into_force"
)

SPO_LIGHT_SYSTEM_PROMPT = f"""\
You extract legal norms from Ukrainian legislation. Output ONLY valid JSON.

Format: {{"statements": [<statement>, ...]}}

Each statement has EXACTLY 7 fields:
- subject_uk: who (organization/official role, in Ukrainian)
- predicate: MUST be one of: {_LIGHT_ACTIONS}
- object_uk: what/whom is regulated (in Ukrainian)
- norm_type: MUST be one of: {_LIGHT_NORM_TYPES}
- fact_text: one-sentence summary of the norm
- source_quote_uk: shortest quote from text that supports this statement
- confidence: 0.0 to 1.0

Rules:
1) predicate and norm_type MUST be from the lists above. No other values.
2) Keep subject_uk and object_uk in Ukrainian as they appear in the text.
3) Maximum 5 statements per provision.
4) Skip non-normative content (signatures, dates, procedural headers).
5) source_quote_uk must be a verbatim substring of the provision text.
"""

SPO_LIGHT_BATCH_SYSTEM_PROMPT = f"""\
You extract legal norms from Ukrainian legislation for multiple provisions.
Output ONLY valid JSON.

Format: {{"items": [{{"id": "<input_id>", "statements": [<statement>, ...]}}, ...]}}

Each statement has EXACTLY 7 fields:
- subject_uk: who (organization/official role, in Ukrainian)
- predicate: MUST be one of: {_LIGHT_ACTIONS}
- object_uk: what/whom is regulated (in Ukrainian)
- norm_type: MUST be one of: {_LIGHT_NORM_TYPES}
- fact_text: one-sentence summary of the norm
- source_quote_uk: shortest quote from text that supports this statement
- confidence: 0.0 to 1.0

Rules:
1) Return one output item per input id. Preserve ids exactly.
2) predicate and norm_type MUST be from the lists above. No other values.
3) Maximum 5 statements per item.
4) Skip non-normative content (signatures, dates, procedural headers).
"""


def build_spo_light_user_prompt(
    *,
    provision_text: str,
    doc_title: str,
    doc_type: str,
    publisher: str,
    date_acc: str,
    provision_citation: str,
) -> str:
    """Compact user prompt for light extraction."""
    return (
        f"[{doc_type} | {publisher} | {date_acc}] {doc_title}\n"
        f"--- {provision_citation} ---\n"
        f"{provision_text}"
    )


def build_spo_light_batch_user_prompt(
    *,
    items: list[dict[str, str]],
) -> str:
    """Compact batch prompt for light extraction."""
    payload = json.dumps(items, ensure_ascii=False)
    return f"INPUT_ITEMS:\n{payload}"
