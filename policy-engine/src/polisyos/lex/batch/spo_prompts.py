"""Prompt templates for 2-pass LLM-based extraction from Ukrainian legal provisions."""

from __future__ import annotations

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

Rules:
1) Preserve Ukrainian legal wording in *_uk fields.
2) Keep predicate/action concise and machine-friendly (snake_case).
3) If conditions/exceptions/procedure are missing, return empty string fields.
4) source_quote_uk should be the shortest quote supporting the statement.
5) Maximum 5 statements.
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
    return build_spo_extract_user_prompt(
        provision_text=provision_text,
        doc_title=doc_title,
        doc_type=doc_type,
        publisher=publisher,
        date_acc=date_acc,
        provision_citation=provision_citation,
    )
