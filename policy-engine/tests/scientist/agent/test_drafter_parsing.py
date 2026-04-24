"""Tests for polisyos.scientist.agent._drafter_parsing — LLM response parsing."""

from __future__ import annotations

import json

import pytest

from polisyos.scientist.agent._drafter_parsing import _DrafterParsingMixin
from polisyos.scientist.agent.drafter_models import (
    FindingCategory,
    FindingSeverity,
)
from polisyos.scientist.agent.protocols import DraftResult

# ---------------------------------------------------------------------------
# Test harness — instantiate the mixin standalone
# ---------------------------------------------------------------------------


class _ParsingHarness(_DrafterParsingMixin):
    pass


@pytest.fixture
def parser():
    return _ParsingHarness()


def _make_draft(**overrides) -> DraftResult:
    defaults = dict(
        draft_id="d1",
        problem_frame_ref="pf1",
        narrative="Some policy narrative",
        interventions=[],
        rationale="reason",
        confidence=0.7,
    )
    defaults.update(overrides)
    return DraftResult(**defaults)


# ---------------------------------------------------------------------------
# _parse_critique_payload
# ---------------------------------------------------------------------------


class TestParseCritiquePayload:
    def test_valid_json_string(self, parser):
        payload = {
            "findings": [
                {
                    "category": "parameter_error",
                    "severity": "high",
                    "description": "Rate out of range",
                    "suggested_fix": "Clamp rate",
                }
            ],
            "confidence_adjustment": -0.05,
        }
        findings, adj, ok, code = parser._parse_critique_payload(
            json.dumps(payload),
            pass_name="pass2",
        )
        assert ok is True
        assert len(findings) == 1
        assert findings[0].finding_id == "pass2_0"
        assert findings[0].category == FindingCategory.PARAMETER_ERROR
        assert findings[0].severity == FindingSeverity.HIGH
        assert findings[0].description == "Rate out of range"
        assert adj == -0.05

    def test_multiple_findings(self, parser):
        payload = {
            "findings": [
                {"category": "other", "severity": "low", "description": "Minor issue"},
                {"category": "side_effect", "severity": "critical", "description": "Severe"},
            ],
        }
        findings, adj, ok, code = parser._parse_critique_payload(
            json.dumps(payload),
            pass_name="p",
        )
        assert ok is True
        assert len(findings) == 2
        assert findings[0].finding_id == "p_0"
        assert findings[1].finding_id == "p_1"
        assert findings[1].severity == FindingSeverity.CRITICAL

    def test_empty_findings(self, parser):
        payload = {"findings": []}
        findings, adj, ok, code = parser._parse_critique_payload(
            json.dumps(payload),
            pass_name="p",
        )
        assert ok is True
        assert findings == []
        assert adj is None

    def test_invalid_json(self, parser):
        findings, adj, ok, code = parser._parse_critique_payload(
            "not json at all",
            pass_name="p",
        )
        assert ok is False
        assert findings == []
        assert adj is None
        assert code is None

    def test_verification_code_extracted(self, parser):
        payload = {
            "findings": [],
            "verification_code": "assert x > 0",
        }
        findings, adj, ok, code = parser._parse_critique_payload(
            json.dumps(payload),
            pass_name="p",
        )
        assert ok is True
        assert code == "assert x > 0"

    def test_empty_verification_code_is_none(self, parser):
        payload = {"findings": [], "verification_code": "  "}
        _, _, _, code = parser._parse_critique_payload(
            json.dumps(payload),
            pass_name="p",
        )
        assert code is None

    def test_fallback_json_loads_then_validate(self, parser):
        payload = {"findings": [{"description": "issue"}]}
        raw = json.dumps(payload)
        findings, adj, ok, code = parser._parse_critique_payload(raw, pass_name="p")
        assert ok is True
        assert len(findings) == 1
        assert findings[0].category == FindingCategory.OTHER
        assert findings[0].severity == FindingSeverity.MEDIUM


# ---------------------------------------------------------------------------
# _parse_findings (wrapper)
# ---------------------------------------------------------------------------


class TestParseFindings:
    def test_delegates_to_critique_payload(self, parser):
        payload = {
            "findings": [{"description": "x", "category": "other", "severity": "low"}],
            "confidence_adjustment": -0.01,
        }
        findings, adj, ok = parser._parse_findings(json.dumps(payload), pass_name="test")
        assert ok is True
        assert len(findings) == 1
        assert adj == -0.01


# ---------------------------------------------------------------------------
# _parse_consolidated_draft
# ---------------------------------------------------------------------------


class TestParseConsolidatedDraft:
    def test_valid_consolidation(self, parser):
        original = _make_draft()
        payload = {
            "narrative": "Updated narrative",
            "interventions": [{"name": "new"}],
            "rationale": "better reason",
            "confidence": 0.95,
            "alternatives_considered": ["alt1"],
        }
        result, ok = parser._parse_consolidated_draft(
            raw_response=json.dumps(payload),
            original=original,
        )
        assert ok is True
        assert result.narrative == "Updated narrative"
        assert result.interventions == [{"name": "new"}]
        assert result.rationale == "better reason"
        assert result.confidence == 0.95
        assert result.alternatives_considered == ["alt1"]
        assert result.draft_id == "d1_mp"

    def test_null_fields_use_original(self, parser):
        original = _make_draft(narrative="original nar", rationale="orig rat")
        payload = {"narrative": "", "rationale": ""}
        result, ok = parser._parse_consolidated_draft(
            raw_response=json.dumps(payload),
            original=original,
        )
        assert ok is True
        assert result.narrative == "original nar"
        assert result.rationale == "orig rat"

    def test_null_confidence_uses_original(self, parser):
        original = _make_draft(confidence=0.6)
        payload = {"narrative": "n"}
        result, ok = parser._parse_consolidated_draft(
            raw_response=json.dumps(payload),
            original=original,
        )
        assert result.confidence == 0.6

    def test_invalid_json_returns_original(self, parser):
        original = _make_draft()
        result, ok = parser._parse_consolidated_draft(
            raw_response="not json",
            original=original,
        )
        assert ok is False
        assert result is original

    def test_preserves_domain_references(self, parser):
        original = _make_draft(domain_references=["ref1", "ref2"])
        payload = {"narrative": "new"}
        result, ok = parser._parse_consolidated_draft(
            raw_response=json.dumps(payload),
            original=original,
        )
        assert result.domain_references == ["ref1", "ref2"]


# ---------------------------------------------------------------------------
# _parse_category / _parse_severity
# ---------------------------------------------------------------------------


class TestParseCategory:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("parameter_error", FindingCategory.PARAMETER_ERROR),
            ("PARAMETER_ERROR", FindingCategory.PARAMETER_ERROR),
            ("  side_effect  ", FindingCategory.SIDE_EFFECT),
            ("other", FindingCategory.OTHER),
            ("unknown_value", FindingCategory.OTHER),
            ("", FindingCategory.OTHER),
        ],
    )
    def test_parse(self, parser, raw, expected):
        assert parser._parse_category(raw) == expected


class TestParseSeverity:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("low", FindingSeverity.LOW),
            ("HIGH", FindingSeverity.HIGH),
            ("  critical  ", FindingSeverity.CRITICAL),
            ("medium", FindingSeverity.MEDIUM),
            ("unknown", FindingSeverity.MEDIUM),
            ("", FindingSeverity.MEDIUM),
        ],
    )
    def test_parse(self, parser, raw, expected):
        assert parser._parse_severity(raw) == expected
