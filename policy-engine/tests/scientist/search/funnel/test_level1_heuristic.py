"""Tests for Level 1 Cheap Heuristic (A.3)."""

from __future__ import annotations

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.search.funnel.level1_heuristic import (
    Level1CheapHeuristic,
    _candidate_structure_hash,
)
from polisyos.scientist.search.funnel.types import FunnelStageResult
from polisyos.scientist.search.lessons import LessonCard, LessonKind, LessonRegistry
from polisyos.scientist.search.transfer_context import TransferContext


def _make_candidate(**overrides):
    base = {
        "semantic": {
            "interventions": [
                {
                    "type": "tax_reform",
                    "parameters": {"income_tax_rate": 0.25},
                },
            ],
            "objectives": [
                {"name": "gdp_growth", "variable": "gdp"},
            ],
        },
    }
    base.update(overrides)
    return base


class TestLevel1CheapHeuristic:
    def setup_method(self):
        self.stage = Level1CheapHeuristic()

    def test_stage_metadata(self):
        assert self.stage.stage_name == "funnel_L1_heuristic"
        assert self.stage.fidelity_level == 1

    def test_valid_candidate_advances(self):
        result = self.stage.evaluate(_make_candidate(), {})
        assert result.is_promising is True
        assert result.cheap_signal is not None
        assert result.cheap_signal.routing_decision() in ("advance", "fast_track")

    def test_cheap_signal_vector_populated(self):
        result = self.stage.evaluate(_make_candidate(), {})
        sig = result.cheap_signal
        assert sig is not None
        assert 0.0 <= sig.structural_validity <= 1.0
        assert 0.0 <= sig.feasibility <= 1.0

    def test_high_conflict_rejects(self):
        """Candidate with forbidden combination should have high policy_conflict."""
        candidate = _make_candidate(
            semantic={
                "interventions": [
                    {"type": "carbon_tax", "parameters": {}},
                    {"type": "fossil_subsidy", "parameters": {}},
                ],
                "objectives": [{"name": "gdp"}],
            },
        )
        result = self.stage.evaluate(candidate, {})
        assert result.cheap_signal is not None
        assert result.cheap_signal.policy_conflict >= 0.8

    def test_failure_cache_affects_value_proxy(self):
        candidate = _make_candidate()
        shash = _candidate_structure_hash(candidate)

        # Stage with high failure rate for this structure.
        stage = Level1CheapHeuristic(
            failure_pattern_cache={shash: 0.95},
        )
        result = stage.evaluate(candidate, {})
        assert result.cheap_signal is not None
        assert result.cheap_signal.expected_value_proxy < 0.1

    def test_failure_cache_emits_warning(self):
        candidate = _make_candidate()
        shash = _candidate_structure_hash(candidate)
        stage = Level1CheapHeuristic(failure_pattern_cache={shash: 0.95})
        result = stage.evaluate(candidate, {})
        assert any(
            fc.failure_type == "historic_failure_pattern"
            for fc in result.failure_cards
        )

    def test_domain_prior_provider_integration(self):
        def mock_priors(cand):
            return {
                "causal_identifiability": 0.9,
                "transportability_risk": 0.1,
            }

        stage = Level1CheapHeuristic(domain_prior_provider=mock_priors)
        result = stage.evaluate(_make_candidate(), {})
        assert result.cheap_signal is not None
        assert result.cheap_signal.causal_identifiability == 0.9
        assert result.cheap_signal.transportability_risk == 0.1

    def test_domain_prior_provider_failure_graceful(self):
        def failing_priors(cand):
            raise RuntimeError("boom")

        stage = Level1CheapHeuristic(domain_prior_provider=failing_priors)
        result = stage.evaluate(_make_candidate(), {})
        # Should not crash; falls back to defaults.
        assert result.is_promising is True

    def test_info_gain_lower_for_duplicates(self):
        candidate = _make_candidate()
        shash = _candidate_structure_hash(candidate)
        stage = Level1CheapHeuristic(evaluated_hashes={shash})
        result = stage.evaluate(candidate, {})
        assert result.cheap_signal is not None
        assert result.cheap_signal.expected_information_gain < 0.5

    def test_record_evaluated_updates_hashes(self):
        candidate = _make_candidate()
        self.stage.record_evaluated(candidate)
        shash = _candidate_structure_hash(candidate)
        assert shash in self.stage._evaluated_hashes

    def test_lesson_registry_integration_lowers_value_proxy(self, tmp_path):
        store = FileSystemCAS(tmp_path / ".polisyos")
        registry = LessonRegistry(root=tmp_path / "registry" / "lessons", store=store)
        registry.record(
            LessonCard(
                kind=LessonKind.FAILURE,
                summary="Tax reform plus GDP objective usually fails transport screening.",
                failure_type="transport_failure",
                stage_name="funnel_L1_heuristic",
                fidelity_level=1,
                candidate_hash="pattern",
                source_run_id="run-1",
                tags=["tax_reform", "gdp_growth"],
            )
        )

        result = self.stage.evaluate(_make_candidate(), {"lesson_registry": registry})
        assert result.cheap_signal is not None
        assert result.cheap_signal.expected_value_proxy < 0.5
        assert any(card.failure_type == "lesson_registry_match" for card in result.failure_cards)

    def test_transferred_lessons_apply_softer_penalty_than_local(self, tmp_path):
        store = FileSystemCAS(tmp_path / ".polisyos")
        registry = LessonRegistry(root=tmp_path / "registry" / "lessons", store=store)
        source = TransferContext(
            task_family="policy",
            domain="fiscal",
            run_id="run-source",
            tenant_hash="tenant-a",
        )
        registry.record_local(
            LessonCard(
                kind=LessonKind.FAILURE,
                summary="Transferred anti-pattern for tax reform plus GDP objective.",
                failure_type="transport_failure",
                stage_name="funnel_L1_heuristic",
                fidelity_level=1,
                candidate_hash="pattern",
                source_run_id="run-source",
                tags=["tax_reform", "gdp_growth"],
            ),
            context=source,
        )

        local_context = {"lesson_registry": registry, "domain": "fiscal", "tenant_hash": "tenant-a"}
        transferred_context = {
            "lesson_registry": registry,
            "domain": "labor",
            "tenant_hash": "tenant-a",
        }

        local_result = self.stage.evaluate(_make_candidate(), local_context)
        transferred_result = self.stage.evaluate(_make_candidate(), transferred_context)

        assert local_result.cheap_signal is not None
        assert transferred_result.cheap_signal is not None
        assert (
            transferred_result.cheap_signal.expected_value_proxy
            > local_result.cheap_signal.expected_value_proxy
        )

    def test_inherits_l0_structural_validity(self):
        """If L0 result is in context, structural_validity reflects it."""
        l0_pass = FunnelStageResult(
            policy_candidate={},
            objective_value=0.0,
            is_promising=True,
            stage_name="funnel_L0_static",
        )
        result = self.stage.evaluate(
            _make_candidate(),
            {"_funnel_L0_result": l0_pass},
        )
        assert result.cheap_signal.structural_validity == 1.0

    def test_evaluation_speed(self):
        """L1 should complete in < 100ms."""
        result = self.stage.evaluate(_make_candidate(), {})
        assert result.duration_seconds < 0.1


class TestCandidateStructureHash:
    def test_same_structure_same_hash(self):
        c1 = _make_candidate()
        c2 = _make_candidate()
        assert _candidate_structure_hash(c1) == _candidate_structure_hash(c2)

    def test_different_structure_different_hash(self):
        c1 = _make_candidate()
        c2 = _make_candidate(
            semantic={
                "interventions": [{"type": "subsidy", "parameters": {}}],
                "objectives": [{"name": "employment"}],
            },
        )
        assert _candidate_structure_hash(c1) != _candidate_structure_hash(c2)

    def test_parameter_values_ignored(self):
        """Hash depends on structure, not parameter values."""
        c1 = _make_candidate()
        c2 = _make_candidate()
        c2["semantic"]["interventions"][0]["parameters"]["income_tax_rate"] = 0.5
        assert _candidate_structure_hash(c1) == _candidate_structure_hash(c2)
