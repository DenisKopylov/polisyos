"""Tests for polisyos.scientist.agent._drafter_formatting — serialization & constitution."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from polisyos.scientist.agent._drafter_formatting import _DrafterFormattingMixin
from polisyos.scientist.agent.drafter_models import (
    FindingCategory,
    FindingSeverity,
    MultiPassConfig,
    PassFinding,
)
from polisyos.scientist.agent.protocols import DraftResult, ProblemFrame

# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------


class _FormattingHarness(_DrafterFormattingMixin):
    def __init__(
        self,
        *,
        config: MultiPassConfig | None = None,
        constitution_gen=None,
        knowledge_base=None,
        norm_pack=None,
        model_spec=None,
    ):
        self._config = config or MultiPassConfig()
        self._constitution_gen = constitution_gen or MagicMock()
        self._knowledge_base = knowledge_base
        self._constitution_norm_pack = norm_pack
        self._constitution_model_spec = model_spec


@pytest.fixture
def harness():
    return _FormattingHarness()


def _make_frame(**overrides) -> ProblemFrame:
    defaults = dict(
        frame_id="f1",
        domain="education",
        problem_statement="How to improve literacy?",
        actors=("government", "schools"),
        goals=("increase reading scores",),
        constraints=("budget <= 1M",),
        success_criteria={"reading_score": ">0.8"},
    )
    defaults.update(overrides)
    return ProblemFrame(**defaults)


def _make_draft(**overrides) -> DraftResult:
    defaults = dict(
        draft_id="d1",
        problem_frame_ref="pf1",
        narrative="A policy to improve literacy",
        interventions=[{"name": "reading_program", "params": {"rate": 0.5}}],
        rationale="Based on evidence",
        confidence=0.8,
        alternatives_considered=["alt1"],
    )
    defaults.update(overrides)
    return DraftResult(**defaults)


# ---------------------------------------------------------------------------
# _summarize_problem_frame
# ---------------------------------------------------------------------------


class TestSummarizeProblemFrame:
    def test_contains_key_fields(self, harness):
        frame = _make_frame()
        summary = harness._summarize_problem_frame(frame)
        assert "education" in summary
        assert "How to improve literacy?" in summary
        assert "increase reading scores" in summary
        assert "government" in summary

    def test_success_criteria_as_json(self, harness):
        frame = _make_frame(success_criteria={"metric": 42})
        summary = harness._summarize_problem_frame(frame)
        assert '"metric": 42' in summary


# ---------------------------------------------------------------------------
# _serialize_draft
# ---------------------------------------------------------------------------


class TestSerializeDraft:
    def test_valid_json(self, harness):
        draft = _make_draft()
        serialized = harness._serialize_draft(draft)
        parsed = json.loads(serialized)
        assert parsed["narrative"] == "A policy to improve literacy"
        assert parsed["confidence"] == 0.8
        assert len(parsed["interventions"]) == 1

    def test_ensure_ascii(self, harness):
        draft = _make_draft(narrative="Полiтика")
        serialized = harness._serialize_draft(draft)
        assert "\\u" in serialized  # non-ASCII escaped


# ---------------------------------------------------------------------------
# _format_constraints
# ---------------------------------------------------------------------------


class TestFormatConstraints:
    def test_empty(self, harness):
        frame = _make_frame(constraints=())
        assert harness._format_constraints(frame) == "No explicit constraints provided."

    def test_numbered_list(self, harness):
        frame = _make_frame(constraints=("budget <= 1M", "time <= 1 year", "no layoffs"))
        result = harness._format_constraints(frame)
        assert "1. budget <= 1M" in result
        assert "2. time <= 1 year" in result
        assert "3. no layoffs" in result


# ---------------------------------------------------------------------------
# _format_findings
# ---------------------------------------------------------------------------


class TestFormatFindings:
    def test_empty(self, harness):
        result = harness._format_findings([])
        assert "No issues found" in result

    def test_single_finding(self, harness):
        finding = PassFinding(
            finding_id="f1",
            category=FindingCategory.PARAMETER_ERROR,
            severity=FindingSeverity.HIGH,
            description="Rate out of range",
            suggested_fix="Clamp to [0,1]",
        )
        result = harness._format_findings([finding])
        assert "[HIGH]" in result
        assert "parameter_error" in result
        assert "Rate out of range" in result
        assert "Fix: Clamp to [0,1]" in result

    def test_anchor_shown(self, harness):
        finding = PassFinding(
            finding_id="f1",
            category=FindingCategory.OTHER,
            severity=FindingSeverity.LOW,
            description="issue",
            anchor="intervention:0",
        )
        result = harness._format_findings([finding])
        assert "(anchor: intervention:0)" in result

    def test_anchor_none_not_shown(self, harness):
        finding = PassFinding(
            finding_id="f1",
            category=FindingCategory.OTHER,
            severity=FindingSeverity.LOW,
            description="issue",
            anchor="none",
        )
        result = harness._format_findings([finding])
        assert "anchor" not in result


# ---------------------------------------------------------------------------
# _build_constitution
# ---------------------------------------------------------------------------


class TestBuildConstitution:
    def test_disabled(self):
        config = MultiPassConfig(constitution_enabled=False)
        h = _FormattingHarness(config=config)
        assert h._build_constitution(_make_frame()) is None

    def test_enabled_calls_generator(self):
        gen = MagicMock()
        gen.generate.return_value = MagicMock()
        h = _FormattingHarness(constitution_gen=gen)
        result = h._build_constitution(_make_frame())
        assert result is gen.generate.return_value
        gen.generate.assert_called_once()

    def test_exception_returns_none(self):
        gen = MagicMock()
        gen.generate.side_effect = RuntimeError("boom")
        h = _FormattingHarness(constitution_gen=gen)
        result = h._build_constitution(_make_frame())
        assert result is None

    def test_assertion_is_not_swallowed(self):
        gen = MagicMock()
        gen.generate.side_effect = AssertionError("constitution invariant failed")
        h = _FormattingHarness(constitution_gen=gen)
        with pytest.raises(AssertionError, match="constitution invariant failed"):
            h._build_constitution(_make_frame())

    def test_pitfalls_from_knowledge_base(self):
        kb = MagicMock()
        kb.get_top_patterns.return_value = ["p1", "p2"]
        gen = MagicMock()
        gen.generate.return_value = MagicMock()
        h = _FormattingHarness(constitution_gen=gen, knowledge_base=kb)
        h._build_constitution(_make_frame())
        gen.generate.assert_called_once()
        call_kwargs = gen.generate.call_args[1]
        assert call_kwargs["known_pitfalls"] == ["p1", "p2"]


# ---------------------------------------------------------------------------
# _inject_constitution_context
# ---------------------------------------------------------------------------


class TestInjectConstitutionContext:
    def test_updates_context(self):
        h = _FormattingHarness()
        frame = _make_frame(context={"existing": "value"})
        constitution = MagicMock()
        constitution.to_system_prompt.return_value = "rules here"
        constitution.compute_hash.return_value = "abc123"

        result = h._inject_constitution_context(frame, constitution=constitution)
        assert result.context["policy_constitution"] == "rules here"
        assert result.context["policy_constitution_hash"] == "abc123"
        assert result.context["existing"] == "value"

    def test_non_dict_context_returns_original(self):
        h = _FormattingHarness()
        # context is empty dict — technically still a dict, but let's test with non-dict
        frame_no_ctx = ProblemFrame(
            frame_id="f1",
            domain="d",
            problem_statement="p",
        )
        # context defaults to {} (a dict), so inject should work
        constitution = MagicMock()
        constitution.to_system_prompt.return_value = "r"
        constitution.compute_hash.return_value = "h"
        result = h._inject_constitution_context(frame_no_ctx, constitution=constitution)
        assert result.context.get("policy_constitution") == "r"
