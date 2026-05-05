from __future__ import annotations

from polisyos.scientist.agent.reflexion_evaluator import (
    ReflexionEvaluatorConfig,
    ReflexionReplayCase,
    ReflexionTrajectoryStep,
    RubricReflexionEvaluator,
    evaluate_reflexion_replay_cases,
)


def test_rubric_reflexion_evaluator_passes_grounded_structured_answer() -> None:
    evaluator = RubricReflexionEvaluator(
        ReflexionEvaluatorConfig(
            required_citation_count=1,
            min_quality_score=0.2,
            min_grounding_score=0.5,
            min_schema_score=0.8,
            min_overall_score=0.5,
        )
    )

    scorecard = evaluator.evaluate_candidate(
        objective="Assess fiscal and legal impact of a clean-energy subsidy",
        output_text=(
            "## Finding\n"
            "Clean-energy subsidies can improve investment while requiring legal "
            "compliance checks and budget caps. Source: https://example.org/report"
        ),
        output_data={"answer": "ok"},
        citations=[
            {
                "url": "https://example.org/report",
                "snippet": "Budget and compliance constraints are material.",
                "source_id": "src-1",
            }
        ],
        tool_results=[
            {
                "tool_name": "scholar_web_search",
                "arguments": {"query": "clean energy subsidy budget"},
                "result": {"results": []},
            }
        ],
        expected_output_schema={
            "type": "object",
            "required": ["answer"],
        },
    )

    assert scorecard.passed is True
    assert scorecard.grounding_score >= 0.5
    assert scorecard.schema_score == 1.0
    assert scorecard.retry_advice == ""


def test_rubric_reflexion_evaluator_flags_low_grounding_schema_and_tool_errors() -> None:
    evaluator = RubricReflexionEvaluator(
        ReflexionEvaluatorConfig(
            required_citation_count=1,
            min_quality_score=0.3,
            min_grounding_score=0.5,
            min_schema_score=0.8,
            min_overall_score=0.6,
        )
    )

    scorecard = evaluator.evaluate_candidate(
        objective="Explain policy tradeoffs",
        output_text="done",
        output_data={"wrong": True},
        citations=[],
        tool_results=[
            {
                "tool_name": "scholar_fetch_open",
                "arguments": {"url": "https://example.org"},
                "error": "timeout after 10s",
                "error_type": "timeout",
            }
        ],
        expected_output_schema={
            "type": "object",
            "required": ["answer"],
        },
    )

    assert scorecard.passed is False
    assert "grounding_below_threshold:0.000" in scorecard.blocking_issues
    assert "scholar_fetch_open:timeout" in scorecard.blocking_issues
    assert "Do not repeat these failed tool/error patterns" in scorecard.retry_advice


def test_evaluator_should_stop_on_pass_or_score_plateau() -> None:
    evaluator = RubricReflexionEvaluator(
        ReflexionEvaluatorConfig(min_overall_score=0.6, min_improvement_delta=0.05)
    )
    poor = evaluator.evaluate_candidate(
        objective="policy question",
        output_text="policy answer",
    )
    almost_same = evaluator.evaluate_candidate(
        objective="policy question",
        output_text="policy answer",
    )
    stop, reason = evaluator.should_stop(almost_same, poor)
    assert stop is True
    assert reason == "score_plateau"


def test_evaluate_reflexion_replay_cases_reports_improvement_and_repeated_errors() -> None:
    evaluator = RubricReflexionEvaluator(
        ReflexionEvaluatorConfig(min_overall_score=0.6, min_improvement_delta=0.01)
    )
    replay = evaluate_reflexion_replay_cases(
        [
            ReflexionReplayCase(
                case_id="case-improves",
                objective="Explain policy with citations",
                steps=[
                    ReflexionTrajectoryStep(
                        iteration=1,
                        output_text="done",
                        tool_results=[
                            {
                                "tool_name": "scholar_web_search",
                                "arguments": {},
                                "error": "invalid args",
                                "error_type": "invalid_arguments",
                            }
                        ],
                    ),
                    ReflexionTrajectoryStep(
                        iteration=2,
                        output_text=(
                            "Policy answer with cited evidence https://example.org/report"
                        ),
                        citations=[
                            {
                                "url": "https://example.org/report",
                                "snippet": "Evidence snippet",
                            }
                        ],
                    ),
                ],
            ),
            ReflexionReplayCase(
                case_id="case-repeats-error",
                objective="Explain policy",
                steps=[
                    ReflexionTrajectoryStep(
                        iteration=1,
                        output_text="done",
                        tool_results=[
                            {
                                "tool_name": "scholar_fetch_open",
                                "arguments": {},
                                "error": "timeout",
                                "error_type": "timeout",
                            }
                        ],
                    ),
                    ReflexionTrajectoryStep(
                        iteration=2,
                        output_text="done",
                        tool_results=[
                            {
                                "tool_name": "scholar_fetch_open",
                                "arguments": {},
                                "error": "timeout",
                                "error_type": "timeout",
                            }
                        ],
                    ),
                ],
                expected_success=False,
            ),
        ],
        evaluator=evaluator,
    )

    assert replay.sample_count == 2
    assert replay.improvement_rate >= 0.5
    assert replay.repeated_error_rate == 0.5
    assert replay.avg_best_score >= replay.avg_first_score
