"""Tests for polisyos.scientist.agent.drafter_models — enums, dataclasses, config."""
from __future__ import annotations

import os
from dataclasses import FrozenInstanceError
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from polisyos.scientist.agent.drafter_models import (
    FindingCategory,
    FindingSeverity,
    MultiPassConfig,
    PassExecution,
    PassFinding,
    _ConsolidationPayload,
    _CritiquePayload,
    _SEVERITY_ORDER,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TestFindingSeverity:
    def test_all_values(self):
        assert {s.value for s in FindingSeverity} == {"low", "medium", "high", "critical"}

    def test_is_string_enum(self):
        assert isinstance(FindingSeverity.LOW, str)

    def test_severity_order_complete(self):
        for sev in FindingSeverity:
            assert sev in _SEVERITY_ORDER


class TestFindingCategory:
    def test_all_values(self):
        expected = {
            "side_effect", "missing_group", "budget_violation",
            "constraint_conflict", "parameter_error", "target_overlap",
            "equity_concern", "feasibility_issue", "other",
        }
        assert {c.value for c in FindingCategory} == expected

    def test_count(self):
        assert len(FindingCategory) == 9


# ---------------------------------------------------------------------------
# PassFinding (frozen dataclass)
# ---------------------------------------------------------------------------

class TestPassFinding:
    def _make(self, **overrides):
        defaults = dict(
            finding_id="f1",
            category=FindingCategory.OTHER,
            severity=FindingSeverity.MEDIUM,
            description="test finding",
        )
        defaults.update(overrides)
        return PassFinding(**defaults)

    def test_creation(self):
        f = self._make()
        assert f.finding_id == "f1"
        assert f.category == FindingCategory.OTHER
        assert f.severity == FindingSeverity.MEDIUM
        assert f.description == "test finding"

    def test_defaults(self):
        f = self._make()
        assert f.suggested_fix == ""
        assert f.affected_intervention is None
        assert f.anchor == "none"
        assert f.source_pass == ""

    def test_frozen(self):
        f = self._make()
        with pytest.raises(FrozenInstanceError):
            f.description = "changed"

    def test_as_memory_dict(self):
        f = self._make(
            suggested_fix="fix it",
            affected_intervention="intervention_0",
            anchor="intervention:0",
        )
        d = f.as_memory_dict()
        assert d["category"] == "other"
        assert d["severity"] == "medium"
        assert d["description"] == "test finding"
        assert d["suggested_fix"] == "fix it"
        assert d["affected_intervention"] == "intervention_0"
        assert d["anchor"] == "intervention:0"

    def test_as_memory_dict_none_intervention(self):
        f = self._make(affected_intervention=None)
        assert f.as_memory_dict()["affected_intervention"] == ""


# ---------------------------------------------------------------------------
# PassExecution
# ---------------------------------------------------------------------------

class TestPassExecution:
    def test_defaults(self):
        p = PassExecution(pass_name="p1", pass_number=1, executed=True)
        assert p.pass_name == "p1"
        assert p.draft is None
        assert p.skip_reason == ""
        assert p.findings == []
        assert p.cost_usd == 0.0
        assert p.parse_ok is True
        assert p.confidence_adjustment is None

    def test_mutable(self):
        p = PassExecution(pass_name="p1", pass_number=1, executed=True)
        p.pass_name = "changed"
        assert p.pass_name == "changed"


# ---------------------------------------------------------------------------
# MultiPassConfig
# ---------------------------------------------------------------------------

class TestMultiPassConfig:
    def test_defaults(self):
        c = MultiPassConfig()
        assert c.max_passes == 4
        assert c.early_exit_confidence == 0.90
        assert c.finding_severity_threshold == FindingSeverity.MEDIUM
        assert c.budget_limit_usd == 0.20
        assert c.max_extra_llm_calls == 3
        assert c.shadow_mode is False
        assert c.rag_enabled is False
        assert c.code_verification_enabled is False
        assert c.constitution_enabled is True

    def test_max_passes_validation_too_low(self):
        with pytest.raises(ValidationError):
            MultiPassConfig(max_passes=0)

    def test_max_passes_validation_too_high(self):
        with pytest.raises(ValidationError):
            MultiPassConfig(max_passes=5)

    def test_budget_limit_validation(self):
        with pytest.raises(ValidationError, match="budget_limit_usd must be >= 0.01"):
            MultiPassConfig(budget_limit_usd=0.005)

    def test_budget_limit_zero(self):
        with pytest.raises(ValidationError):
            MultiPassConfig(budget_limit_usd=0.0)

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            MultiPassConfig(unknown_field=True)

    def test_frozen(self):
        c = MultiPassConfig()
        with pytest.raises(ValidationError):
            c.max_passes = 2

    def test_from_env_defaults(self):
        with patch.dict(os.environ, {}, clear=False):
            c = MultiPassConfig.from_env()
            assert c.max_passes == 4
            assert c.budget_limit_usd == 0.20

    def test_from_env_custom(self):
        env = {
            "POLISYOS_DRAFTER_MAX_PASSES": "2",
            "POLISYOS_DRAFTER_BUDGET_LIMIT_USD": "0.50",
            "POLISYOS_DRAFTER_MAX_EXTRA_LLM_CALLS": "5",
            "POLISYOS_DRAFTER_CRITIQUE_MODEL": "claude-3-haiku",
        }
        with patch.dict(os.environ, env, clear=False):
            c = MultiPassConfig.from_env()
            assert c.max_passes == 2
            assert c.budget_limit_usd == 0.50
            assert c.max_extra_llm_calls == 5
            assert c.critique_model == "claude-3-haiku"

    def test_from_env_shadow_mode(self):
        with patch.dict(os.environ, {"POLISYOS_DRAFTER_MULTIPASS_MODE": "shadow"}, clear=False):
            c = MultiPassConfig.from_env()
            assert c.shadow_mode is True

    def test_from_env_rag(self):
        env = {
            "POLISYOS_RAG_ENABLED": "true",
            "POLISYOS_RAG_TOP_K": "5",
        }
        with patch.dict(os.environ, env, clear=False):
            c = MultiPassConfig.from_env()
            assert c.rag_enabled is True
            assert c.rag_top_k == 5

    def test_roundtrip(self):
        c = MultiPassConfig(max_passes=2, budget_limit_usd=0.10, critique_model="test")
        data = c.model_dump()
        c2 = MultiPassConfig(**data)
        assert c == c2


# ---------------------------------------------------------------------------
# Internal payload models
# ---------------------------------------------------------------------------

class TestCritiquePayload:
    def test_extra_fields_ignored(self):
        p = _CritiquePayload(findings=[], unknown_field="x")
        assert p.findings == []

    def test_defaults(self):
        p = _CritiquePayload()
        assert p.findings == []
        assert p.confidence_adjustment is None
        assert p.verification_code is None


class TestConsolidationPayload:
    def test_extra_fields_ignored(self):
        p = _ConsolidationPayload(narrative="n", extra="ignored")
        assert p.narrative == "n"

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            _ConsolidationPayload(confidence=1.5)
        with pytest.raises(ValidationError):
            _ConsolidationPayload(confidence=-0.1)

    def test_confidence_valid(self):
        p = _ConsolidationPayload(confidence=0.85)
        assert p.confidence == 0.85
