"""Replay actual historical evidence without restamping its authority epoch."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.runtime.quality.promotion_sequence import (
    N9PromotionEvidenceBridgeRecord,
    _EffectiveIndependenceProducerRecord,
    _persist_model,
)


def test_actual_v2_evidence_bridge_retains_its_exact_producer_bytes(tmp_path: Path) -> None:
    wrapper = json.loads(
        (Path(__file__).parent / "fixtures" / "n9_evidence_bridge_v2.json").read_bytes()
    )
    assert wrapper["synthetic"] is True
    raw = wrapper["body_utf8"].encode()
    assert hashlib.sha256(raw).hexdigest() == wrapper["body_sha256"]
    body = json.loads(raw)
    record = N9PromotionEvidenceBridgeRecord.model_validate(body)
    assert record.model_dump(mode="json", exclude_none=True) == body
    _, _, observed = _persist_model(
        store=FileSystemCAS(tmp_path / "cas"),
        value=record,
        kind="polisyos.gy.n9_promotion_evidence_bridge",
    )
    assert observed == raw
    for field, value in (
        ("synthetic", True),
        ("source_disposition", "established"),
        ("source_limitation_code", "effective_independence_established"),
    ):
        with pytest.raises(ValueError, match="historical_evidence_bridge_cannot_be_restamped"):
            N9PromotionEvidenceBridgeRecord.model_validate({**body, field: value})


def test_actual_v1_independence_source_retains_its_exact_producer_bytes(tmp_path: Path) -> None:
    wrapper = json.loads(
        (Path(__file__).parent / "fixtures" / "n9_independence_source_v1.json").read_bytes()
    )
    assert wrapper["synthetic"] is True
    raw = wrapper["body_utf8"].encode()
    assert hashlib.sha256(raw).hexdigest() == wrapper["body_sha256"]
    body = json.loads(raw)
    record = _EffectiveIndependenceProducerRecord.model_validate(body)
    assert record.model_dump(mode="json", exclude_none=True) == body
    _, _, observed = _persist_model(
        store=FileSystemCAS(tmp_path / "cas"),
        value=record,
        kind="polisyos.gy.n9_effective_independence_producer_record",
    )
    assert observed == raw
    with pytest.raises(ValueError, match="historical_evidence_source_cannot_be_restamped"):
        _EffectiveIndependenceProducerRecord.model_validate({**body, "synthetic": True})
