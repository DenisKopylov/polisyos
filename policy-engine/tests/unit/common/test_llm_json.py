from __future__ import annotations

import json

import pytest

from polisyos.common.serialization import extract_llm_json, extract_llm_json_object


def test_extract_llm_json_object_accepts_think_prefixed_json() -> None:
    payload = {"status": "ok", "nested": {"value": 4}}
    raw = "<think>reasoning with {non-json braces}</think>" + json.dumps(payload)

    assert dict(extract_llm_json_object(raw)) == payload


def test_extract_llm_json_object_accepts_fenced_json() -> None:
    assert dict(extract_llm_json_object('```json\n{"status":"ok"}\n```')) == {
        "status": "ok"
    }


def test_extract_llm_json_object_rejects_invalid_response() -> None:
    with pytest.raises(json.JSONDecodeError):
        extract_llm_json_object("no JSON object exists")


def test_extract_llm_json_object_rejects_non_object() -> None:
    with pytest.raises(json.JSONDecodeError, match="not an object"):
        extract_llm_json_object("[1, 2, 3]")


def test_extract_llm_json_keeps_generic_array_contract() -> None:
    assert extract_llm_json("reasoning [1, 2, 3]") == [1, 2, 3]


def test_json_extraction_uses_the_canonical_serialization_owner() -> None:
    from polisyos.common import serialization

    assert serialization.extract_llm_json('candidate ```json\n[1, 2]\n```') == [1, 2]
    assert dict(serialization.extract_llm_json_object('candidate {"valid": true}')) == {
        "valid": True
    }
    with pytest.raises(json.JSONDecodeError):
        serialization.extract_llm_json_object("invalid candidate")
