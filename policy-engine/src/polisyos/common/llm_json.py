"""JSON extraction for LLM responses that wrap strict JSON in provider text."""

from __future__ import annotations

import json
from collections.abc import Mapping

__all__ = ["extract_llm_json", "extract_llm_json_object"]


def extract_llm_json(raw_response: str) -> object:
    """Return the first JSON payload embedded in an LLM response.

    The gateway may return provider-visible reasoning or Markdown fences around
    an otherwise strict JSON object even when ``response_format`` asks for JSON.
    This helper keeps the raw response intact for provenance and parses only a
    syntactically valid JSON value from it.

    Raises:
        json.JSONDecodeError: If no valid JSON payload is present.
    """

    text = str(raw_response).strip()
    if not text:
        raise json.JSONDecodeError("empty LLM response", raw_response, 0)
    try:
        return json.loads(text)
    except json.JSONDecodeError as first_error:
        fenced = _fenced_json_payloads(text)
        for payload in fenced:
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                continue
        decoder = json.JSONDecoder()
        for index, char in enumerate(text):
            if char not in "{[":
                continue
            try:
                value, _end = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            return value
        raise first_error


def extract_llm_json_object(raw_response: str) -> Mapping[str, object]:
    """Return an embedded JSON object from an LLM response."""

    value = extract_llm_json(raw_response)
    if not isinstance(value, Mapping):
        raise json.JSONDecodeError("LLM JSON payload is not an object", raw_response, 0)
    return value


def _fenced_json_payloads(text: str) -> tuple[str, ...]:
    payloads: list[str] = []
    parts = text.split("```")
    for index in range(1, len(parts), 2):
        block = parts[index].strip()
        if block.startswith("json"):
            block = block[4:].strip()
        payloads.append(block)
    return tuple(payloads)
