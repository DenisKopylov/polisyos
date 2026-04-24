from __future__ import annotations

from argparse import Namespace
from unittest.mock import MagicMock

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components._cli_scientist import _cmd_scientist_burn_in
from polisyos.scientist.search.cold_start import BurnInConfig, run_burn_in
from polisyos.scientist.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.search.funnel.types import (
    CheapSignalVector,
    FunnelStage,
    FunnelStageResult,
    TypedFailureCard,
    UncertaintyEnvelope,
)
from polisyos.scientist.search.lessons import LessonRegistry
from polisyos.scientist.search.stages import CorrelationTracker


def _make_stage_result(
    *,
    level: int,
    name: str,
    is_promising: bool,
    cheap_signal: CheapSignalVector | None = None,
    failure_cards: list[TypedFailureCard] | None = None,
) -> FunnelStageResult:
    return FunnelStageResult(
        policy_candidate={},
        objective_value=0.1 if is_promising else 0.9,
        is_promising=is_promising,
        stage_name=name,
        uncertainty_envelope=UncertaintyEnvelope.deterministic(),
        cheap_signal=cheap_signal,
        failure_cards=list(failure_cards or []),
        fidelity_level=level,
    )


def _stage(level: int, name: str, side_effect) -> FunnelStage:
    stage = MagicMock(spec=FunnelStage)
    stage.fidelity_level = level
    stage.stage_name = name
    stage.estimated_cost_usd = 0.0
    stage.evaluate.side_effect = side_effect
    return stage


def test_run_burn_in_bypasses_cheap_rejection_but_seeds_lessons(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    tracker = CorrelationTracker()
    lesson_registry = LessonRegistry(root=tmp_path / "registry" / "lessons", store=store)

    l0 = _stage(
        0,
        "L0",
        lambda candidate, context: _make_stage_result(level=0, name="L0", is_promising=True),
    )
    l1 = _stage(
        1,
        "L1",
        lambda candidate, context: (
            _make_stage_result(
                level=1,
                name="L1",
                is_promising=not candidate.get("bad", False),
                cheap_signal=CheapSignalVector(structural_validity=0.2)
                if candidate.get("bad", False)
                else CheapSignalVector(structural_validity=1.0, causal_identifiability=0.8),
                failure_cards=(
                    [
                        TypedFailureCard(
                            judge_name="L1",
                            failure_type="canonical_failure",
                            severity="warning",
                            description="Known bad candidate pattern.",
                        )
                    ]
                    if candidate.get("bad", False)
                    else []
                ),
            )
        ),
    )
    l2 = _stage(
        2,
        "L2",
        lambda candidate, context: _make_stage_result(
            level=2,
            name="L2",
            is_promising=True,
            cheap_signal=CheapSignalVector(
                structural_validity=1.0,
                causal_identifiability=0.8,
                expected_value_proxy=0.8,
            ),
        ),
    )
    l4 = _stage(
        4,
        "L4",
        lambda candidate, context: _make_stage_result(level=4, name="L4", is_promising=True),
    )

    orchestrator = FunnelOrchestrator(
        [l0, l1, l2, l4],
        correlation_tracker=tracker,
        lesson_registry=lesson_registry,
    )

    report = run_burn_in(
        orchestrator=orchestrator,
        config=BurnInConfig(
            run_id="burn-in-1",
            regular_candidates=[
                {"semantic": {"interventions": [{"type": "tax"}], "objectives": [{"name": "gdp"}]}}
            ],
            dumb_candidates=[
                {
                    "bad": True,
                    "semantic": {
                        "interventions": [{"type": "bad"}],
                        "objectives": [{"name": "gdp"}],
                    },
                }
            ],
        ),
        correlation_tracker=tracker,
        lesson_registry=lesson_registry,
        store=store,
    )

    assert report.actual_level4_candidates == 1
    assert report.cohort_sizes["calibration"] == 1
    assert report.lesson_card_refs
    assert lesson_registry.top_patterns(limit=5)
    assert l4.evaluate.call_count == 1


def test_burn_in_cli_happy_path_and_invalid_config(tmp_path) -> None:
    config_path = tmp_path / "burn_in.json"
    output_path = tmp_path / "burn_in_report.json"
    config_path.write_text(
        """
        {
          "run_id": "cli-burn-in",
          "regular_candidates": [
            {
              "semantic": {
                "interventions": [{"type": "tax_reform", "parameters": {"rate": 0.2}}],
                "objectives": [{"name": "gdp"}]
              },
              "expected_stage4": {
                "simulation_results": {"gdp_change": 0.3, "gov_balance": -0.05},
                "feedback": {"verdict": "APPROVE"}
              }
            }
          ],
          "dumb_candidates": []
        }
        """.strip(),
        encoding="utf-8",
    )

    code = _cmd_scientist_burn_in(
        Namespace(
            config=str(config_path),
            output=str(output_path),
            format="json",
            cas_root=str(tmp_path / ".polisyos"),
        )
    )
    assert code == 0
    assert output_path.exists()

    bad_config = tmp_path / "burn_in_bad.json"
    bad_config.write_text('{"regular_candidates": "oops"}', encoding="utf-8")
    bad_code = _cmd_scientist_burn_in(
        Namespace(
            config=str(bad_config),
            output=None,
            format="json",
            cas_root=str(tmp_path / ".polisyos"),
        )
    )
    assert bad_code == 2
