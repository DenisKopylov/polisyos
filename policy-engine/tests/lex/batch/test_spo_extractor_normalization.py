from __future__ import annotations

import json

import pytest

from polisyos.lex.batch.spo_extractor import (
    _choose_verify_statements,
    _extract_one_provision,
    _is_json_mode_invalid_request,
    _normalize_statements,
    _parse_json_object,
    _parse_spo_statements,
)
from polisyos.lex.batch.structurer import ProvisionSpan
from polisyos.lex.batch.xml_parser import NPACard, NPADocument
from polisyos.lex.knowledge.types import SPOCandidate


def test_normalization_prefers_canonical_fields_from_verify_pass() -> None:
    stmt = SPOCandidate(
        subject_en="cabinet_of_ministers",
        subject_uk="Кабінет Міністрів України",
        predicate="adopts_proposal",
        object_en="proposal",
        object_uk="пропозицію",
        fact_text="Cabinet adopts proposal.",
        confidence=0.95,
        norm_type="directive",
        action_raw="Прийняти пропозицію",
        action_canon="adopt_proposal",
        norm_type_raw="ПОСТАНОВЛЯЄ",
        norm_type_canon="directive",
        source_quote_uk="Прийняти пропозицію...",
        source_quote_start=10,
        source_quote_end=30,
    )

    normalized, reasons, stats = _normalize_statements([stmt])
    assert len(normalized) == 1
    assert normalized[0].action_canon == "approves"
    assert normalized[0].norm_type_canon == "obligation"
    assert stats["oov_action"] == 0
    assert stats["oov_norm_type"] == 0
    assert "oov_action" not in reasons
    assert "oov_norm_type" not in reasons


def test_normalization_falls_back_to_predicate_when_action_canon_oov() -> None:
    stmt = SPOCandidate(
        subject_en="cabinet_of_ministers",
        subject_uk="Кабінет Міністрів України",
        predicate="enters_into_force",
        object_en="regulation",
        object_uk="постанова",
        fact_text="Regulation enters into force.",
        confidence=0.9,
        norm_type="obligation",
        action_raw="набирає чинності",
        action_canon="totally_unknown_action",
        norm_type_raw="обов'язок",
        norm_type_canon="directive",
        source_quote_uk="набирає чинності",
        source_quote_start=0,
        source_quote_end=15,
    )

    normalized, reasons, stats = _normalize_statements([stmt])
    assert len(normalized) == 1
    assert normalized[0].action_canon == "enters_into_force"
    assert normalized[0].norm_type_canon == "obligation"
    assert stats["oov_action"] == 0
    assert "oov_action" not in reasons


def test_parse_json_object_from_mixed_text() -> None:
    raw = 'Answer:\n{"statements":[{"predicate":"requires"}]}\nDone.'
    parsed = _parse_json_object(raw)
    assert parsed is not None
    assert parsed["statements"][0]["predicate"] == "requires"


def test_parse_json_object_raw_decode_ignores_trailing_garbage() -> None:
    raw = '{"statements":[{"predicate":"requires"}]}} trailing junk'
    parsed = _parse_json_object(raw)
    assert parsed is not None
    assert parsed["statements"][0]["predicate"] == "requires"


def test_parse_spo_statements_maps_loose_schema_and_threshold_aliases() -> None:
    parsed = _parse_spo_statements(
        {
            "statements": [
                {
                    "subject": "Кабінет Міністрів України",
                    "object": "заборгованість",
                    "action_canon": "grant_deferral",
                    "norm_type_canon": "obligation",
                    "quote_start": 12,
                    "quote_end": 44,
                    "source_quote_uk": "Надати відстрочку повернення позички",
                    "thresholds": [
                        {
                            "type": "amount",
                            "comparator": "up_to",
                            "value_decimal": 295,
                            "unit": "non_taxable_minimums",
                        }
                    ],
                }
            ]
        }
    )

    assert len(parsed) == 1
    stmt = parsed[0]
    assert stmt.subject_uk == "Кабінет Міністрів України"
    assert stmt.object_uk == "заборгованість"
    assert stmt.source_quote_start == 12
    assert stmt.source_quote_end == 44
    assert len(stmt.thresholds) == 1
    assert stmt.thresholds[0].metric == "amount"
    assert stmt.thresholds[0].operator == "up_to"
    assert stmt.thresholds[0].value_decimal == "295"


def test_json_mode_invalid_request_detector() -> None:
    body = (
        '{"error":{"message":"Invalid request.","type":"invalid_request_error",'
        '"code":"invalid_request","param":null}}'
    )
    assert _is_json_mode_invalid_request(400, body) is True
    assert _is_json_mode_invalid_request(429, body) is False


def test_choose_verify_statements_accepts_loose_verify_schema() -> None:
    pass1_stmt = SPOCandidate(
        subject_en="cabinet_of_ministers",
        subject_uk="Кабінет Міністрів України",
        predicate="approves",
        object_en="proposal",
        object_uk="пропозицію",
        fact_text="Cabinet approves proposal.",
        confidence=0.9,
        norm_type="obligation",
        source_quote_uk="Схвалити пропозицію.",
        source_quote_start=0,
        source_quote_end=18,
    )

    verify_payload = {
        "statements": [
            {
                # Intentionally incompatible with SPOCandidate schema.
                "subject": "Кабінет Міністрів України",
                "object": "пропозицію",
                "action_canon": "approves",
            }
        ]
    }
    chosen, used_fallback = _choose_verify_statements(
        doc_id="doc1",
        provision_anchor="full/chunk:0001",
        statements_pass1=[pass1_stmt],
        data_verify=verify_payload,
    )

    assert len(chosen) == 1
    assert chosen[0].predicate == "approves"
    assert chosen[0].subject_uk == "Кабінет Міністрів України"
    assert used_fallback is False


class _DummyClient:
    def __init__(self) -> None:
        self.model_id = "dummy/model"
        self.calls = 0

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        response_format: dict[str, str] | None = None,
    ) -> dict:
        self.calls += 1
        payload = {
            "statements": [
                {
                    "subject_en": "cabinet_of_ministers",
                    "subject_uk": "Кабінет Міністрів України",
                    "predicate": "approves",
                    "object_en": "proposal",
                    "object_uk": "пропозицію",
                    "fact_text": "Кабінет Міністрів України схвалює пропозицію.",
                    "confidence": 0.9,
                    "norm_type": "obligation",
                    "source_quote_uk": "схвалює пропозицію",
                    "source_quote_start": 10,
                    "source_quote_end": 27,
                    "thresholds": [],
                }
            ]
        }
        return {
            "choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }


@pytest.mark.asyncio
async def test_extract_one_provision_code_verify_mode_skips_second_llm_pass() -> None:
    client = _DummyClient()
    card = NPACard(
        doc_id="doc1234567890abcd",
        reestr_code="rc1",
        date_acc="2001-01-01",
        reestr_date="2001-01-02",
        status="Чинний",
        doc_type="Наказ",
        name="Тестовий документ",
        publisher=("КМУ",),
        number="1",
        publication=(),
        keywords=(),
        reg_date="",
        reg_number="",
    )
    doc = NPADocument(card=card, text="Кабінет Міністрів України схвалює пропозицію.")
    provision = ProvisionSpan(
        kind="full_text",
        number="1",
        anchor_path="full/chunk:0001",
        citation_label="Повний текст, фрагмент 1",
        offset_start=0,
        offset_end=len(doc.text),
        text=doc.text,
    )

    result = await _extract_one_provision(
        client,
        doc,
        provision,
        verify_mode="code",
    )

    assert client.calls == 1
    assert result.extract_passes == 1
    assert result.pass2_latency_ms == 0
    assert result.token_count_prompt_verify == 0
    assert result.token_count_completion_verify == 0
    assert json.loads(result.verify_report_json)["mode"] == "code"
    assert len(result.statements) == 1
