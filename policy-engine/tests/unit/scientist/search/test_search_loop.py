"""
Verification tests for Phase 17: Search Loop + Two-Stage + Engine Abstraction.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from threading import Event, Thread
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel, field_serializer, model_serializer

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.execution_plan import ExecutionPlan, MethodDagNode
from polisyos.foundry.methods.catalog.snapshot import build_method_catalog_snapshot
from polisyos.scientist.methods.search.controller import (
    SearchBudgetProducerUnsupportedError,
    SearchConfig,
    SearchController,
    SearchIteration,
    SearchStatus,
    TracedLLMCandidateGenerator,
    _search_prompt_value,
)
from polisyos.scientist.methods.search.objective import (
    CompositeObjective,
    GDPGrowthObjective,
    ObjectivePresets,
    ObjectiveValue,
    OptimizationDirection,
)
from polisyos.scientist.methods.search.stages import CheapStage, ExpensiveStage
from polisyos.scientist.methods.search.stopping import (
    CompositeStoppingCriterion,
    CostBudgetStopping,
    ImprovementPlateau,
    MaxIterations,
    MaxWallTime,
)
from polisyos.scientist.orchestration.llm.cycle import preflight_execution_plan
from polisyos.scientist.orchestration.workflows.engine_simple import SimpleLoopEngine


def test_traced_prompt_refuses_lossy_json_serializer_output_before_provider() -> None:
    """JSON-mode normalization must not turn an invalid serializer value into null."""

    class LossyFieldSerializer(BaseModel):
        value: str

        @field_serializer("value", when_used="json")
        def serialize_value(self, value: str) -> Any:
            del value
            return {"nested": math.nan}

    class NonStringKeySerializer(BaseModel):
        value: str

        @field_serializer("value", when_used="json")
        def serialize_value(self, value: str) -> Any:
            del value
            return {1: "candidate"}

    sibling_serializer_calls: list[str] = []

    class SiblingCallbackSerializer(BaseModel):
        invalid: str
        later: str

        @field_serializer("invalid", when_used="json")
        def serialize_invalid(self, value: str) -> Any:
            del value
            return {"nested": math.nan}

        @field_serializer("later", when_used="json")
        def serialize_later(self, value: str) -> str:
            sibling_serializer_calls.append(value)
            return value

    class AnyPayload(BaseModel):
        value: Any

    class NeverCalledClient:
        def __init__(self) -> None:
            self.calls = 0

        async def generate(self, **_kwargs: Any) -> object:
            self.calls += 1
            pytest.fail("invalid prompt data must be refused before provider dispatch")

    client = NeverCalledClient()
    generator = TracedLLMCandidateGenerator(
        client=client,  # type: ignore[arg-type]
        system_prompt="Return one candidate object.",
    )

    for payload, expected_reason in (
        (
            LossyFieldSerializer(value="candidate"),
            "search_prompt_contains_nonfinite_number",
        ),
        (
            NonStringKeySerializer(value="candidate"),
            "search_prompt_contains_non_string_key",
        ),
        (
            SiblingCallbackSerializer(invalid="source", later="must-not-run"),
            "search_prompt_contains_nonfinite_number",
        ),
        (
            AnyPayload(value=LossyFieldSerializer(value="candidate")),
            "search_prompt_contains_nonfinite_number",
        ),
    ):
        with pytest.raises(SearchBudgetProducerUnsupportedError) as raised:
            generator.generate([], None, {"payload": payload})
        assert raised.value.reason_code == expected_reason

    assert client.calls == 0
    assert sibling_serializer_calls == []


def test_traced_prompt_guards_allowed_model_extras_before_provider() -> None:
    """Allowed extras and nested Any models cannot be normalized to null."""
    from types import SimpleNamespace

    from polisyos.runtime.quality.semantic_binding import CoverageBinding
    from polisyos.scientist.methods.search.controller import (
        _prompt_compiled_serializer,
        _prompt_to_python,
    )

    class NestedPromptValue(BaseModel):
        value: Any

    class PlainSerializedNestedPromptValue(BaseModel):
        value: str

        @model_serializer(mode="plain")
        def serialize_nonfinite_value(self) -> dict[str, Any]:
            del self.value
            return {"projected": math.nan}

    class WrapSerializedNestedPromptValue(BaseModel):
        value: str

        @model_serializer(mode="wrap")
        def serialize_nonfinite_value(self, handler: Any) -> dict[str, Any]:
            del self.value
            del handler
            return {"projected": math.nan}

    class PromptClient:
        _cache_reuse_owner = None

        def __init__(self) -> None:
            self.calls = 0
            self.user_prompts: list[str] = []

        async def generate(self, **kwargs: Any) -> object:
            self.calls += 1
            self.user_prompts.append(str(kwargs["user"]))
            return SimpleNamespace(content='{"candidate":"accepted"}')

    def binding(payload: Any) -> CoverageBinding:
        return CoverageBinding(
            source_ref="fixture-source",
            claim_ids=("claim-1",),
            status="covers",
            payload=payload,
        )

    from collections.abc import Iterable
    from enum import Enum

    consumed: list[float] = []

    def one_shot_values() -> Any:
        consumed.append(math.nan)
        yield math.nan

    one_shot = one_shot_values()

    class TypedOneShotPromptValue(BaseModel):
        values: Iterable[float]

    typed_one_shot = one_shot_values()

    class RecursivePromptEnum(Enum):
        HOLDER = {"nested": None}

    RecursivePromptEnum.HOLDER.value["nested"] = RecursivePromptEnum.HOLDER
    cycle: dict[str, Any] = {}
    cycle["self"] = cycle
    invalid_payloads = (
        math.nan,
        math.inf,
        NestedPromptValue(value=math.nan),
        {"child": NestedPromptValue(value=math.nan)},
        {"children": [NestedPromptValue(value=math.nan)]},
        RecursivePromptEnum.HOLDER,
        {"numbers": {math.nan}},
        {"numbers": frozenset({math.nan})},
        one_shot,
        TypedOneShotPromptValue(values=typed_one_shot),
        {"child": PlainSerializedNestedPromptValue(value="source")},
        {"child": WrapSerializedNestedPromptValue(value="source")},
        cycle,
        {1: "non-string key"},
    )
    rejecting_client = PromptClient()
    rejecting_generator = TracedLLMCandidateGenerator(
        client=rejecting_client,  # type: ignore[arg-type]
        system_prompt="Return one candidate object.",
    )
    for payload in invalid_payloads:
        with pytest.raises(SearchBudgetProducerUnsupportedError):
            rejecting_generator.generate([], None, {"binding": binding(payload)})
    assert rejecting_client.calls == 0
    assert consumed == []

    serializer = _prompt_compiled_serializer(CoverageBinding)
    omitted_bad_payload = binding({"safe": 0.5, "hidden": math.nan})
    assert _prompt_to_python(
        serializer,
        omitted_bad_payload,
        mode="json",
        include={"payload": {"safe"}},
    )["payload"] == {"safe": 0.5}
    assert _prompt_to_python(
        serializer,
        omitted_bad_payload,
        mode="json",
        exclude={"payload": {"hidden"}},
    )["payload"] == {"safe": 0.5}
    with pytest.raises(SearchBudgetProducerUnsupportedError):
        _prompt_to_python(
            serializer,
            omitted_bad_payload,
            mode="json",
            include={"payload": {"hidden"}},
        )
    assert (
        _prompt_to_python(
            serializer,
            binding(math.nan),
            mode="json",
            exclude={"payload"},
        )["source_ref"]
        == "fixture-source"
    )
    assert _prompt_to_python(
        serializer,
        binding({"numbers": {0.25}}),
        mode="json",
    )["payload"]["numbers"] == [0.25]

    from pydantic import Field, RootModel

    class AnyRootPromptValue(RootModel[Any]):
        pass

    class FloatRootPromptValue(RootModel[float]):
        pass

    root_invalid_payloads = (
        FloatRootPromptValue(root=math.nan),
        FloatRootPromptValue(root=math.inf),
        AnyRootPromptValue(root=math.nan),
        AnyRootPromptValue(root={"nested": math.nan}),
    )
    for payload in root_invalid_payloads:
        with pytest.raises(SearchBudgetProducerUnsupportedError) as raised:
            rejecting_generator.generate([], None, {"binding": binding(payload)})
        assert raised.value.reason_code == "search_prompt_contains_nonfinite_number"
    assert rejecting_client.calls == 0

    finite_root = AnyRootPromptValue(root={"safe": 0.5})
    root_accepting_client = PromptClient()
    root_accepting_generator = TracedLLMCandidateGenerator(
        client=root_accepting_client,  # type: ignore[arg-type]
        system_prompt="Return one candidate object.",
    )
    assert root_accepting_generator.generate(
        [],
        None,
        {"binding": binding(finite_root)},
    ) == {"candidate": "accepted"}
    assert root_accepting_client.calls == 1
    assert '"payload":{"safe":0.5}' in root_accepting_client.user_prompts[0]
    assert root_accepting_generator.generate(
        [],
        None,
        {"binding": binding(FloatRootPromptValue(root=0.5))},
    ) == {"candidate": "accepted"}
    assert root_accepting_client.calls == 2
    assert '"payload":0.5' in root_accepting_client.user_prompts[1]
    root_serializer = _prompt_compiled_serializer(AnyRootPromptValue)
    projected_root = AnyRootPromptValue(root={"safe": 0.5, "hidden": math.nan})
    assert _prompt_to_python(
        root_serializer,
        projected_root,
        mode="json",
        include={"safe"},
    ) == {"safe": 0.5}
    assert _prompt_to_python(
        root_serializer,
        projected_root,
        mode="json",
        exclude={"hidden"},
    ) == {"safe": 0.5}
    root_shared = NestedPromptValue(value=0.75)
    assert _prompt_to_python(
        root_serializer,
        AnyRootPromptValue(root={"left": root_shared, "right": root_shared}),
        mode="json",
    ) == {"left": {"value": 0.75}, "right": {"value": 0.75}}

    class TypedRootEnvelope(BaseModel):
        child: AnyRootPromptValue

    typed_root = TypedRootEnvelope(child=AnyRootPromptValue(root={"safe": 0.25}))
    assert root_accepting_generator.generate(
        [],
        None,
        {"binding": binding(typed_root)},
    ) == {"candidate": "accepted"}
    assert root_accepting_client.calls == 3
    assert '"payload":{"child":{"safe":0.25}}' in root_accepting_client.user_prompts[2]

    shared_root = AnyRootPromptValue(root={"safe": 0.75})
    assert _search_prompt_value(
        AnyRootPromptValue(root={"left": shared_root, "right": shared_root}),
    ) == {"left": {"safe": 0.75}, "right": {"safe": 0.75}}

    raw_mapping_cycle: dict[str, Any] = {}
    raw_mapping_cycle["self"] = raw_mapping_cycle
    with pytest.raises(SearchBudgetProducerUnsupportedError) as raised:
        _search_prompt_value(AnyRootPromptValue(root=raw_mapping_cycle))
    assert raised.value.reason_code == "search_prompt_contains_cycle"

    root_model_cycle = AnyRootPromptValue(root={})
    root_model_cycle.root["self"] = root_model_cycle
    with pytest.raises(SearchBudgetProducerUnsupportedError) as raised:
        _search_prompt_value(root_model_cycle)
    assert raised.value.reason_code == "search_prompt_model_serialization_failed"

    callback_iterator = iter([math.nan])

    class CallbackRootPromptValue(RootModel[Any]):
        @model_serializer(mode="plain")
        def consume_root(self) -> dict[str, Any]:
            return {"values": list(self.root)}

    callback_value = CallbackRootPromptValue(root=callback_iterator)
    with pytest.raises(SearchBudgetProducerUnsupportedError) as raised:
        rejecting_generator.generate([], None, {"binding": callback_value})
    assert raised.value.reason_code == "search_prompt_contains_nonfinite_number"
    assert list(callback_iterator) == []
    assert rejecting_client.calls == 0

    finite_callback_iterator = iter([0.25])
    assert root_accepting_generator.generate(
        [],
        None,
        {
            "binding": binding(
                CallbackRootPromptValue(root=finite_callback_iterator),
            ),
        },
    ) == {"candidate": "accepted"}
    assert list(finite_callback_iterator) == []
    assert root_accepting_client.calls == 4

    class ExcludeIfPromptValue(BaseModel):
        payload: Any = Field(
            exclude_if=lambda value: isinstance(value, float) and math.isnan(value)
        )

    assert (
        _prompt_to_python(
            _prompt_compiled_serializer(ExcludeIfPromptValue),
            ExcludeIfPromptValue(payload=math.nan),
            mode="json",
        )
        == {}
    )

    class TypedExtraBinding(CoverageBinding):
        __pydantic_extra__: dict[str, float]

    typed_serializer = _prompt_compiled_serializer(TypedExtraBinding)
    with pytest.raises(SearchBudgetProducerUnsupportedError):
        _prompt_to_python(
            typed_serializer,
            TypedExtraBinding(source_ref="fixture-source", measured=math.nan),
            mode="json",
        )
    assert (
        _prompt_to_python(
            typed_serializer,
            TypedExtraBinding(source_ref="fixture-source", measured=0.5),
            mode="json",
        )["measured"]
        == 0.5
    )

    accepting_client = PromptClient()
    accepting_generator = TracedLLMCandidateGenerator(
        client=accepting_client,  # type: ignore[arg-type]
        system_prompt="Return one candidate object.",
    )
    assert accepting_generator.generate(
        [],
        None,
        {"binding": binding({"items": [NestedPromptValue(value=0.5)]})},
    ) == {"candidate": "accepted"}
    assert accepting_client.calls == 1
    assert '"payload":{"items":[{"value":0.5}]}' in accepting_client.user_prompts[0]

    shared = NestedPromptValue(value=0.75)
    assert accepting_generator.generate(
        [],
        None,
        {"binding": binding({"left": shared, "right": shared})},
    ) == {"candidate": "accepted"}
    assert accepting_client.calls == 2
    assert (
        '"payload":{"left":{"value":0.75},"right":{"value":0.75}}'
        in (accepting_client.user_prompts[1])
    )


def test_prompt_field_guard_follows_effective_source_resolution_projection() -> None:
    """Excluded source context stays hidden unless an actual serializer emits it."""
    from types import SimpleNamespace

    from polisyos.runtime.quality.generation_source import GenerationSourceResolution

    class FakePromptClient:
        _cache_reuse_owner = None

        def __init__(self) -> None:
            self.calls = 0
            self.user_prompts: list[str] = []

        async def generate(self, **_kwargs: Any) -> object:
            self.calls += 1
            self.user_prompts.append(str(_kwargs["user"]))
            return SimpleNamespace(content='{"candidate":"accepted"}')

    cycle: dict[str, Any] = {}
    cycle["self"] = cycle
    hidden_values = (
        GenerationSourceResolution(
            status="resolved",
            code="source-resolution",
            context={"excluded_context_nan": math.nan},
        ),
        GenerationSourceResolution(
            status="resolved",
            code="source-resolution",
            context={"excluded_context_cycle": cycle},
        ),
    )
    client = FakePromptClient()
    generator = TracedLLMCandidateGenerator(
        client=client,  # type: ignore[arg-type]
        system_prompt="Return one search candidate as a non-empty JSON object.",
    )

    for hidden_value in hidden_values:
        assert generator.generate([], None, {"source": hidden_value}) == {"candidate": "accepted"}
    assert client.calls == 2
    assert all("excluded_context_" not in prompt for prompt in client.user_prompts)

    class ReemittingResolution(GenerationSourceResolution):
        @model_serializer(mode="plain")
        def serialize_with_context(self) -> dict[str, Any]:
            return {"status": self.status, "context": self.context}

    reemitted_values = (
        ReemittingResolution(
            status="resolved",
            code="source-resolution",
            context={"re-emitted": math.nan},
        ),
        ReemittingResolution(
            status="resolved",
            code="source-resolution",
            context={"re-emitted": cycle},
        ),
    )
    refusing_client = FakePromptClient()
    refusing_generator = TracedLLMCandidateGenerator(
        client=refusing_client,  # type: ignore[arg-type]
        system_prompt="Return one search candidate as a non-empty JSON object.",
    )

    for reemitted_value in reemitted_values:
        with pytest.raises(SearchBudgetProducerUnsupportedError) as raised:
            refusing_generator.generate([], None, {"source": reemitted_value})
        assert raised.value.reason_code in {
            "search_prompt_contains_nonfinite_number",
            "search_prompt_contains_cycle",
        }
    assert refusing_client.calls == 0


def test_prompt_projection_preserves_artifact_ref_and_datetime_json_contract() -> None:
    """The raw-output fence retains existing DTO and native datetime projections."""
    reference = ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex("a" * 64),
        kind="fixture",
        media_type="application/json",
    )
    created_at = datetime(2026, 10, 13, 12, 30, tzinfo=UTC)

    actual = _search_prompt_value({"reference": reference, "created_at": created_at})

    assert actual == {
        "reference": reference.model_dump(mode="json", exclude_none=False),
        "created_at": created_at.isoformat(),
    }


def test_traced_prompt_projects_owned_search_history_and_keeps_refusals() -> None:
    """The declared history row reaches JSON while foreign or malformed inputs refuse."""
    import json
    from types import SimpleNamespace

    class PromptClient:
        _cache_reuse_owner = None

        def __init__(self) -> None:
            self.calls = 0
            self.user_prompts: list[str] = []

        async def generate(self, **kwargs: Any) -> object:
            self.calls += 1
            self.user_prompts.append(str(kwargs["user"]))
            return SimpleNamespace(content='{"candidate":"accepted"}')

    client = PromptClient()
    generator = TracedLLMCandidateGenerator(
        client=client,  # type: ignore[arg-type]
        system_prompt="Return one search candidate as a non-empty JSON object.",
    )
    timestamp = datetime(2026, 10, 13, 12, 30, tzinfo=UTC)

    def row(
        *,
        objective_value: float = 1.0,
        candidate: dict[str, Any] | None = None,
        stage_b_result: dict[str, Any] | None = None,
        objective_details: list[Any] | None = None,
    ) -> SearchIteration:
        return SearchIteration(
            iteration=0,
            candidate=candidate or {"x": 1.0},
            objective_value=objective_value,
            objective_details=objective_details
            if objective_details is not None
            else [
                ObjectiveValue(
                    name="quadratic",
                    raw_value=1.0,
                    direction=OptimizationDirection.MINIMIZE,
                    weight=1.0,
                    is_satisfied=True,
                    threshold=None,
                )
            ],
            is_promising=True,
            stage_a_passed=True,
            stage_b_result=stage_b_result
            or {"simulation_results": {"x": 1.0}, "feedback": {"verdict": "APPROVE"}},
            duration_seconds=0.125,
            policy_evaluation=None,
            timestamp=timestamp,
            policy_evaluation_status="missing",
            policy_evaluation_error=None,
        )

    assert generator.generate([row()], None, {}) == {"candidate": "accepted"}
    prompt = client.user_prompts[0].partition("Search inputs JSON:\n")[2]
    emitted = json.loads(prompt)["history"][0]
    assert emitted == {
        "iteration": 0,
        "candidate": {"x": 1.0},
        "objective_value": 1.0,
        "objective_details": [
            {
                "name": "quadratic",
                "raw_value": 1.0,
                "direction": "minimize",
                "weight": 1.0,
                "is_satisfied": True,
                "threshold": None,
            }
        ],
        "is_promising": True,
        "stage_a_passed": True,
        "stage_b_result": {
            "simulation_results": {"x": 1.0},
            "feedback": {"verdict": "APPROVE"},
        },
        "duration_seconds": 0.125,
        "policy_evaluation": None,
        "timestamp": timestamp.isoformat(),
        "policy_evaluation_status": "missing",
        "policy_evaluation_error": None,
    }

    cycle: dict[str, Any] = {}
    cycle["self"] = cycle
    invalid_rows = (
        ([row(objective_value=math.nan)], "search_prompt_contains_nonfinite_number"),
        ([row(stage_b_result=cycle)], "search_prompt_contains_cycle"),
        (
            [row(candidate={"opaque": object()})],
            "search_prompt_contains_unsupported_value",
        ),
        (
            [row(objective_details=[object()])],
            "search_prompt_contains_unsupported_value",
        ),
        ([object()], "search_prompt_contains_unsupported_value"),
    )
    for history, reason_code in invalid_rows:
        with pytest.raises(SearchBudgetProducerUnsupportedError) as raised:
            generator.generate(history, None, {})
        assert raised.value.reason_code == reason_code
    assert client.calls == 1


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_candidate_generator():
    """Generator that produces candidates converging to x=0."""

    class QuadraticGenerator:
        def __init__(self):
            self._iteration = 0

        def generate(
            self,
            history: list[Any],
            current_best: dict[str, Any] | None,
            context: dict[str, Any],
        ) -> dict[str, Any]:
            if current_best:
                x = current_best.get("x", 1.0)
                x = x * 0.5
            else:
                x = 1.0

            self._iteration += 1
            return {"x": x, "semantic": {"interventions": []}}

    return QuadraticGenerator()


@pytest.fixture
def quadratic_objective():
    """Objective f(x) = x^2, minimum at x=0."""

    class QuadraticObjective:
        @property
        def name(self) -> str:
            return "quadratic"

        def evaluate(self, results: dict[str, Any]) -> Any:
            from polisyos.scientist.methods.search.objective import (
                ObjectiveValue,
                OptimizationDirection,
            )

            x = results.get("x", 0.0)
            return ObjectiveValue(
                name=self.name,
                raw_value=x**2,
                direction=OptimizationDirection.MINIMIZE,
            )

    return CompositeObjective([QuadraticObjective()])


# ─────────────────────────────────────────────────────────────────────────────
# Test: Optimization Flow
# ─────────────────────────────────────────────────────────────────────────────


class TestOptimizationFlow:
    """
    Test that search loop finds optimal solution for simple objective.

    Mock the ExpensiveStage with f(x) = x^2. Assert the search loop
    converges toward the minimum at x=0.
    """

    def test_generation_context_projects_missing_best_objective_as_absent(
        self,
        mock_candidate_generator,
        quadratic_objective,
    ) -> None:
        """A source-owned no-best sentinel becomes JSON absence at the producer boundary."""
        controller = SearchController(
            config=SearchConfig(
                stopping=MaxIterations(1),
                objective=quadratic_objective,
            ),
            candidate_generator=mock_candidate_generator,
            stage_a_evaluator=lambda _candidate, _context: (0.0, True),
            stage_b_evaluator=lambda _candidate, _context: {},
            metrics=MagicMock(),
        )

        context = controller._build_generation_context({}, iteration=0)

        assert controller._best_candidate is None
        assert math.isinf(controller._best_objective)
        assert context["search_state"]["current_best_candidate"] is None
        assert context["search_state"]["current_best_objective"] is None

        controller._best_candidate = {}
        controller._best_objective = math.inf
        malformed = controller._build_generation_context({}, iteration=1)
        assert math.isinf(malformed["search_state"]["current_best_objective"])
        with pytest.raises(SearchBudgetProducerUnsupportedError) as raised:
            _search_prompt_value(malformed)
        assert raised.value.reason_code == "search_prompt_contains_nonfinite_number"

        controller._best_candidate = None
        for malformed_objective in (math.nan, -math.inf):
            controller._best_objective = malformed_objective
            malformed_absence = controller._build_generation_context({}, iteration=2)
            projected_objective = malformed_absence["search_state"]["current_best_objective"]
            if math.isnan(malformed_objective):
                assert math.isnan(projected_objective)
            else:
                assert projected_objective == malformed_objective
            with pytest.raises(SearchBudgetProducerUnsupportedError) as raised:
                _search_prompt_value(malformed_absence)
            assert raised.value.reason_code == "search_prompt_contains_nonfinite_number"

        controller._best_candidate = {}
        controller._best_objective = 0.0
        populated = controller._build_generation_context({}, iteration=2)
        assert populated["search_state"]["current_best_candidate"] == {}
        assert populated["search_state"]["current_best_objective"] == 0.0

    def test_search_finds_quadratic_minimum(
        self,
        mock_candidate_generator,
        quadratic_objective,
    ):
        """Search should converge toward x=0 for f(x)=x^2."""

        def stage_a_evaluator(candidate, context):
            return 0.0, True

        def stage_b_evaluator(candidate, context):
            x = candidate.get("x", 1.0)
            return {
                "simulation_results": {"x": x, "objective_value": x**2},
                "feedback": {"verdict": "APPROVE"},
            }

        config = SearchConfig(
            stopping=MaxIterations(10),
            objective=quadratic_objective,
        )

        controller = SearchController(
            config=config,
            candidate_generator=mock_candidate_generator,
            stage_a_evaluator=stage_a_evaluator,
            stage_b_evaluator=stage_b_evaluator,
        )

        result = controller.run(
            initial_context={"user_request": "test"},
            initial_candidate={"x": 1.0, "semantic": {"interventions": []}},
        )

        assert result.best_candidate is not None
        assert result.best_candidate["x"] < 0.1
        assert result.best_objective < 0.01

    def test_search_respects_max_iterations(self, mock_candidate_generator, quadratic_objective):
        """Search must stop exactly at max_iterations."""

        def stage_a_evaluator(candidate, context):
            return 0.0, True

        def stage_b_evaluator(candidate, context):
            return {
                "simulation_results": {"x": 1.0},
                "feedback": {"verdict": "APPROVE"},
            }

        config = SearchConfig(
            stopping=MaxIterations(5),
            objective=quadratic_objective,
        )

        controller = SearchController(
            config=config,
            candidate_generator=mock_candidate_generator,
            stage_a_evaluator=stage_a_evaluator,
            stage_b_evaluator=stage_b_evaluator,
        )

        result = controller.run({"user_request": "test"})

        assert result.iterations_completed == 5
        assert "Maximum iterations" in result.stopping_reason

    def test_repeated_runs_are_fresh_and_returned_snapshots_stay_stable(
        self,
        quadratic_objective,
    ):
        """A controller run owns its state and returns a stable result snapshot."""

        class StaticGenerator:
            def generate(self, history, current_best, context):
                del history, current_best, context
                return {"x": 10.0, "semantic": {"interventions": []}}

        def stage_a(candidate, context):
            del candidate, context
            return 0.0, True

        def stage_b(candidate, context):
            del context
            return {
                "simulation_results": {"x": candidate["x"]},
                "feedback": {"verdict": "APPROVE"},
            }

        controller = SearchController(
            config=SearchConfig(
                stopping=MaxIterations(1),
                objective=quadratic_objective,
                initial_evaluations=[],
            ),
            candidate_generator=StaticGenerator(),
            stage_a_evaluator=stage_a,
            stage_b_evaluator=stage_b,
        )

        first_candidate = {"x": 1.0, "semantic": {"interventions": []}}
        first = controller.run({"request": "first"}, initial_candidate=first_candidate)
        first_candidate["x"] = 99.0

        second = controller.run(
            {"request": "second"},
            initial_candidate={"x": 2.0, "semantic": {"interventions": []}},
        )

        assert second.search_id != first.search_id
        assert second.stage_a_evaluations == 1
        assert second.stage_b_evaluations == 1
        assert len(second.history) == 1
        assert second.history[0].candidate["x"] == 2.0
        assert second.best_candidate is not None
        assert second.best_candidate["x"] == 2.0

        assert len(first.history) == 1
        assert first.history[0].candidate["x"] == 1.0
        assert first.best_candidate is not None
        assert first.best_candidate["x"] == 1.0
        assert first.stage_a_evaluations == 1
        assert first.stage_b_evaluations == 1

        sentinel = controller.run(
            {"request": "sentinel"},
            initial_candidate={
                "x": 3.0,
                "semantic": {"interventions": []},
                "__sentinel__": {"sentinel_id": "ctl-01"},
            },
        )
        assert sentinel.history == []
        assert sentinel.best_candidate is None
        assert sentinel.stage_a_evaluations == 1
        assert sentinel.stage_b_evaluations == 1
        assert sentinel.telemetry["sentinel_evaluations"] == 1

        warm_evaluation = {
            "candidate": {"x": 0.5, "semantic": {"interventions": []}},
            "objective_value": 0.5,
        }
        warm_controller = SearchController(
            config=SearchConfig(
                stopping=MaxIterations(2),
                objective=quadratic_objective,
                initial_evaluations=[warm_evaluation],
            ),
            candidate_generator=StaticGenerator(),
            stage_a_evaluator=stage_a,
            stage_b_evaluator=stage_b,
        )
        warm = warm_controller.run(
            {"request": "compatible-warm-start"},
            initial_candidate={"x": 4.0, "semantic": {"interventions": []}},
        )
        warm_evaluation["candidate"]["x"] = 8.0

        assert warm.history[0].iteration == -1
        assert warm.history[0].candidate["x"] == 0.5
        assert warm.telemetry["training_evaluations"] == 1
        assert warm.telemetry["history_size"] == 3
        assert warm.telemetry["new_evaluations"] == 2
        assert warm.telemetry["evaluation_count"] == 2
        assert warm.telemetry["scientific_evaluations"] == 2

    def test_cost_budget_snapshot_stops_after_owner_spend_and_is_reported(
        self,
        quadratic_objective,
    ):
        """The owner spend is shared by both stopping checks and the result report."""

        class StaticGenerator:
            def generate(self, history, current_best, context):
                del history, current_best, context
                return {"x": 1.0, "semantic": {"interventions": []}}

        context = {"cumulative_cost_usd": 0.0}

        def stage_b(candidate, stage_context):
            del candidate
            stage_context["cumulative_cost_usd"] += 1.0
            return {
                "simulation_results": {"x": 1.0},
                "feedback": {"verdict": "APPROVE"},
            }

        controller = SearchController(
            config=SearchConfig(
                stopping=CostBudgetStopping(max_cost_usd=1.0),
                objective=quadratic_objective,
            ),
            candidate_generator=StaticGenerator(),
            stage_a_evaluator=lambda candidate, stage_context: (0.0, True),
            stage_b_evaluator=stage_b,
        )

        result = controller.run(context)

        assert result.iterations_completed == 1
        assert result.stage_b_evaluations == 1
        assert result.telemetry["budget_available"] is True
        assert result.telemetry["budget_snapshot"] == {"cumulative_cost_usd": 1.0}
        assert result.telemetry["budget_spent"] == 1.0
        assert "Cost budget" in result.stopping_reason

    @pytest.mark.parametrize(
        ("wire_cost", "owner_limit", "expected_owner_status", "expected_stage_b"),
        [
            ("0.25", "0.50", "resolved", 1),
            ("0.25", "0.25", "resolved", 0),
            ("0", "0.50", "resolved", 1),
            ("true", "0.50", "unavailable", 0),
        ],
    )
    def test_durable_provider_owner_controls_search_stopping_and_result(
        self,
        tmp_path,
        quadratic_objective,
        wire_cost: str,
        owner_limit: str,
        expected_owner_status: str,
        expected_stage_b: int,
    ) -> None:
        """Wire real provider bytes through settlement, run scope, stopping, and result."""
        import json
        from decimal import Decimal

        from polisyos.core.llm.traced_client import TracedLLMClient
        from polisyos.scientist.orchestration.engine.budget import (
            BudgetLimit,
            BudgetState,
        )
        from polisyos.scientist.orchestration.engine.budget_ledger import (
            BudgetLedgerProducerRunBinding,
            FileBudgetLedger,
        )
        from polisyos.scientist.orchestration.engine.budget_middleware import (
            BudgetMiddleware,
        )
        from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient

        run_id = f"search-owner-{wire_cost}-{owner_limit}"
        budget_key = f"nl-run:{run_id}"
        binding = BudgetLedgerProducerRunBinding(
            run_id=run_id,
            tenant_id="tenant-search-test",
            cell_id="cell-search-test",
            profile_id="search-profile-test",
            control_job_id=f"control-{run_id}",
        )
        ledger_path = tmp_path / f"{run_id}.json"
        owner = BudgetMiddleware(
            BudgetState(
                limits={
                    budget_key: BudgetLimit(
                        key=budget_key,
                        max_usd=Decimal(owner_limit),
                    )
                }
            ),
            ledger=FileBudgetLedger(ledger_path),
        )

        response_json = json.dumps(
            {
                "model": "fixture-model",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '{"x":1.0,"semantic":{"interventions":[]}}',
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 2,
                    "completion_tokens": 1,
                    "total_cost_usd": json.loads(wire_cost),
                },
            }
        )

        class FakeResponse:
            status = 200
            headers: dict[str, str] = {}

            async def text(self) -> str:
                return response_json

        class FakeContext:
            async def __aenter__(self) -> FakeResponse:
                return FakeResponse()

            async def __aexit__(self, *_args: object) -> None:
                return None

        class FakeSession:
            closed = False

            def post(self, *_args: object, **_kwargs: object) -> FakeContext:
                return FakeContext()

            async def close(self) -> None:
                self.closed = True

        gateway = GatewayLLMClient(
            base_url="http://test.local",
            api_key="fixture-key",
            model="fixture-model",
            max_retries=0,
        )
        gateway._session = FakeSession()
        traced = TracedLLMClient(
            gateway,
            model_name="fixture-model",
            producer_settlement_store=owner,
            producer_budget_key=budget_key,
        )

        candidate_generator = TracedLLMCandidateGenerator(
            client=traced,
            system_prompt="Return one search candidate as a non-empty JSON object.",
        )

        stage_b_calls: list[dict[str, Any]] = []

        def stage_b(candidate, context):
            del context
            stage_b_calls.append(candidate)
            return {
                "simulation_results": {"x": 1.0},
                "feedback": {"verdict": "APPROVE"},
            }

        controller = SearchController(
            config=SearchConfig(
                stopping=CostBudgetStopping(max_cost_usd=0.3),
                objective=quadratic_objective,
                max_iterations_hard_limit=1,
                producer_settlement_store=owner,
                producer_run_binding=binding,
            ),
            candidate_generator=candidate_generator,
            stage_a_evaluator=lambda candidate, context: (0.0, True),
            stage_b_evaluator=stage_b,
        )
        result = controller.run({"cumulative_cost_usd": 1000.0})

        durable = FileBudgetLedger(ledger_path).snapshot()
        events = list(durable.producer_settlements.values())
        assert len(events) == 1
        assert events[0].run_binding == binding
        assert events[0].key == budget_key
        assert events[0].status == ("unknown" if wire_cost == "true" else "committed")
        assert len(stage_b_calls) == expected_stage_b
        owner_telemetry = result.telemetry["producer_budget_owner"]
        assert owner_telemetry["status"] == expected_owner_status
        if expected_owner_status == "resolved":
            assert owner_telemetry["event_status_counts"] == {"committed": 1}
            assert Decimal(owner_telemetry["spent"]) == (
                Decimal(0) if wire_cost == "0" else Decimal("0.25")
            )
            assert result.telemetry["budget_available"] is True
        else:
            assert owner_telemetry.get("event_status_counts") is None
            assert "valueerror" in owner_telemetry["reason_code"]
            assert result.telemetry["budget_available"] is False
            assert result.telemetry["budget_spent"] is None

    @pytest.mark.parametrize(
        ("wire_cost", "expected_owner_status", "expected_evaluations"),
        [("0.25", "resolved", 1), ("true", "unavailable", 0)],
    )
    def test_autotune_runner_binds_real_provider_call_to_durable_budget_owner(
        self,
        tmp_path,
        wire_cost: str,
        expected_owner_status: str,
        expected_evaluations: int,
    ) -> None:
        """The SearchLoopRunner caller carries its exact owner binding through replay."""
        import json
        from decimal import Decimal

        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.core.llm.traced_client import TracedLLMClient
        from polisyos.scientist.methods.autotune import (
            BenchmarkEvaluation,
            BenchmarkSplit,
            BenchmarkSuite,
            ChampionRegistry,
            MetricDirection,
            MutationArtifact,
            PromotionPolicy,
            SearchLoopRunner,
            SearchLoopSpec,
            persist_benchmark_suite,
        )
        from polisyos.scientist.methods.autotune.models import load_model_artifact
        from polisyos.scientist.methods.autotune.runtime import PydanticMutationCodec
        from polisyos.scientist.orchestration.engine.budget import (
            BudgetLimit,
            BudgetState,
        )
        from polisyos.scientist.orchestration.engine.budget_ledger import (
            BudgetLedgerProducerRunBinding,
            FileBudgetLedger,
        )
        from polisyos.scientist.orchestration.engine.budget_middleware import (
            BudgetMiddleware,
        )
        from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient

        run_id = f"autotune-owner-{wire_cost}"
        budget_key = f"nl-run:{run_id}"
        binding = BudgetLedgerProducerRunBinding(
            run_id=run_id,
            tenant_id="tenant-autotune-test",
            cell_id="cell-autotune-test",
            profile_id="autotune-profile-test",
            control_job_id=f"control-{run_id}",
        )
        ledger_path = tmp_path / f"{run_id}.json"
        owner = BudgetMiddleware(
            BudgetState(
                limits={
                    budget_key: BudgetLimit(
                        key=budget_key,
                        max_usd=Decimal("0.50"),
                    )
                }
            ),
            ledger=FileBudgetLedger(ledger_path),
        )
        response_json = json.dumps(
            {
                "model": "fixture-model",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '{"loop_id":"autotune_owner","value":1}',
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 2,
                    "completion_tokens": 1,
                    "total_cost_usd": json.loads(wire_cost),
                },
            }
        )

        class FakeResponse:
            status = 200
            headers: dict[str, str] = {}

            async def text(self) -> str:
                return response_json

        class FakeContext:
            async def __aenter__(self) -> FakeResponse:
                return FakeResponse()

            async def __aexit__(self, *_args: object) -> None:
                return None

        class FakeSession:
            closed = False

            def post(self, *_args: object, **_kwargs: object) -> FakeContext:
                return FakeContext()

            async def close(self) -> None:
                self.closed = True

        gateway = GatewayLLMClient(
            base_url="http://test.local",
            api_key="fixture-key",
            model="fixture-model",
            max_retries=0,
        )
        gateway._session = FakeSession()
        traced = TracedLLMClient(
            gateway,
            model_name="fixture-model",
            producer_settlement_store=owner,
            producer_budget_key=budget_key,
        )

        class SearchMutation(MutationArtifact):
            value: int

        candidate_generator = TracedLLMCandidateGenerator(
            client=traced,
            system_prompt="Return one autotune candidate as a non-empty JSON object.",
        )

        evaluations: list[BenchmarkEvaluation] = []

        class TypedEvaluator:
            def evaluate(self, candidate_ref, suite_ref, context):
                del suite_ref
                candidate = load_model_artifact(context["store"], candidate_ref, SearchMutation)
                evaluation = BenchmarkEvaluation(
                    loop_id="autotune_owner",
                    suite_id="autotune_owner_suite",
                    suite_version="1.0",
                    candidate_ref=candidate_ref,
                    selection_metrics={"score": float(candidate.value)},
                    holdout_metrics={"score": float(candidate.value)},
                    sample_counts={
                        BenchmarkSplit.SELECTION.value: 1,
                        BenchmarkSplit.HOLDOUT.value: 1,
                    },
                    guardrails={"score_present": True},
                    promotable=True,
                    runtime_split_type=BenchmarkSplit.HOLDOUT,
                )
                evaluations.append(evaluation)
                return evaluation

        store = FileSystemCAS(tmp_path / "cas")
        suite_ref = persist_benchmark_suite(
            store,
            BenchmarkSuite(suite_id="autotune_owner_suite", suite_version="1.0"),
        )
        spec = SearchLoopSpec(
            loop_id="autotune_owner",
            mutation_codec=PydanticMutationCodec(SearchMutation),
            candidate_generator=candidate_generator,
            benchmark_evaluator=TypedEvaluator(),
            promotion_policy=PromotionPolicy(
                loop_id="autotune_owner",
                primary_metric="score",
                direction=MetricDirection.MAXIMIZE,
                compare_split=BenchmarkSplit.HOLDOUT,
                min_sample_count=1,
                required_guardrails=["score_present"],
            ),
        )
        runner = SearchLoopRunner(
            store=store,
            registry=ChampionRegistry(root=tmp_path / "registry", store=store),
        )

        result = runner.run(
            spec,
            suite_ref=suite_ref,
            context={"run_id": run_id, "cumulative_cost_usd": 1000.0},
            max_iterations=1,
            producer_settlement_store=owner,
            producer_run_binding=binding,
        )

        durable = FileBudgetLedger(ledger_path).snapshot()
        events = list(durable.producer_settlements.values())
        assert len(events) == 1
        assert events[0].run_binding == binding
        assert events[0].key == budget_key
        assert events[0].status == ("unknown" if wire_cost == "true" else "committed")
        assert len(evaluations) == expected_evaluations
        owner_telemetry = result.telemetry["producer_budget_owner"]
        assert owner_telemetry["status"] == expected_owner_status
        assert owner_telemetry["run_binding"]["run_id"] == run_id
        if expected_owner_status == "resolved":
            assert owner_telemetry["event_status_counts"] == {"committed": 1}
            assert Decimal(owner_telemetry["spent"]) == Decimal("0.25")
            assert result.telemetry["budget_spent"] == 0.25
            assert result.history
        else:
            assert owner_telemetry.get("event_status_counts") is None
            assert "valueerror" in owner_telemetry["reason_code"]
            assert result.history == []

    def test_budgeted_search_refuses_unproven_generator_before_runner_callback(
        self,
        tmp_path,
    ) -> None:
        """An arbitrary callback is refused before SearchLoopRunner configures it."""
        from decimal import Decimal
        from types import SimpleNamespace

        from polisyos.scientist.methods.autotune.runtime import SearchLoopRunner
        from polisyos.scientist.orchestration.engine.budget import (
            BudgetLimit,
            BudgetState,
        )
        from polisyos.scientist.orchestration.engine.budget_ledger import (
            BudgetLedgerProducerRunBinding,
            FileBudgetLedger,
        )
        from polisyos.scientist.orchestration.engine.budget_middleware import (
            BudgetMiddleware,
        )

        run_id = "search-unproven-generator"
        budget_key = f"nl-run:{run_id}"
        owner = BudgetMiddleware(
            BudgetState(
                limits={
                    budget_key: BudgetLimit(
                        key=budget_key,
                        max_usd=Decimal("1.00"),
                    )
                }
            ),
            ledger=FileBudgetLedger(tmp_path / "unproven.json"),
        )
        binding = BudgetLedgerProducerRunBinding(
            run_id=run_id,
            tenant_id="tenant-search-test",
            cell_id="cell-search-test",
            profile_id="search-profile-test",
            control_job_id="control-search-unproven-generator",
        )

        class UnprovenGenerator:
            def __init__(self) -> None:
                self.context_calls = 0
                self.generation_calls = 0

            def set_search_run_context(self, _context: dict[str, Any]) -> None:
                self.context_calls += 1

            def generate(self, history, current_best, context):
                del history, current_best, context
                self.generation_calls += 1
                return {"x": 1.0}

        generator = UnprovenGenerator()
        runner = SearchLoopRunner.__new__(SearchLoopRunner)
        runner._store = object()
        runner._registry = object()
        spec = SimpleNamespace(loop_id="unproven", candidate_generator=generator)

        with pytest.raises(SearchBudgetProducerUnsupportedError) as raised:
            runner.run(
                spec,
                suite_ref=object(),
                producer_settlement_store=owner,
                producer_run_binding=binding,
            )

        assert raised.value.reason_code == "budgeted_search_requires_traced_candidate_generator"
        assert generator.context_calls == 0
        assert generator.generation_calls == 0

    def test_budgeted_search_rejects_traced_client_bound_to_another_owner(
        self,
        tmp_path,
        quadratic_objective,
    ) -> None:
        """A real traced client with a foreign owner cannot run under this owner claim."""
        from decimal import Decimal

        from polisyos.core.llm.traced_client import TracedLLMClient
        from polisyos.scientist.orchestration.engine.budget import (
            BudgetLimit,
            BudgetState,
        )
        from polisyos.scientist.orchestration.engine.budget_ledger import (
            BudgetLedgerProducerRunBinding,
            FileBudgetLedger,
        )
        from polisyos.scientist.orchestration.engine.budget_middleware import (
            BudgetMiddleware,
        )

        run_id = "search-owner-mismatch"
        budget_key = f"nl-run:{run_id}"
        binding = BudgetLedgerProducerRunBinding(
            run_id=run_id,
            tenant_id="tenant-search-test",
            cell_id="cell-search-test",
            profile_id="search-profile-test",
            control_job_id="control-search-owner-mismatch",
        )

        def make_owner(name: str) -> BudgetMiddleware:
            return BudgetMiddleware(
                BudgetState(
                    limits={
                        budget_key: BudgetLimit(
                            key=budget_key,
                            max_usd=Decimal("1.00"),
                        )
                    }
                ),
                ledger=FileBudgetLedger(tmp_path / f"{name}.json"),
            )

        selected_owner = make_owner("selected")
        foreign_owner = make_owner("foreign")

        class NeverProvider:
            async def generate(self, **_kwargs: Any) -> object:
                pytest.fail("owner mismatch must be rejected before provider dispatch")

        traced = TracedLLMClient(
            NeverProvider(),
            model_name="fixture-model",
            producer_settlement_store=foreign_owner,
            producer_budget_key=budget_key,
        )
        generator = TracedLLMCandidateGenerator(
            client=traced,
            system_prompt="Return a candidate object.",
        )

        with pytest.raises(SearchBudgetProducerUnsupportedError) as raised:
            SearchController(
                config=SearchConfig(
                    stopping=CostBudgetStopping(max_cost_usd=0.30),
                    objective=quadratic_objective,
                    producer_settlement_store=selected_owner,
                    producer_run_binding=binding,
                ),
                candidate_generator=generator,
                stage_a_evaluator=lambda candidate, context: (0.0, True),
                stage_b_evaluator=lambda candidate, context: {
                    "simulation_results": {"x": candidate["x"]},
                    "feedback": {"verdict": "APPROVE"},
                },
            )

        assert raised.value.reason_code == "selected_traced_client_owner_or_run_mismatch"

    def test_generation_with_missing_owner_event_readback_stops_before_stage_b(
        self,
        tmp_path,
        quadratic_objective,
    ) -> None:
        """A hidden first settlement cannot pass through the initial empty-event window."""
        import json
        from decimal import Decimal

        from polisyos.core.llm.traced_client import TracedLLMClient
        from polisyos.scientist.orchestration.engine.budget import (
            BudgetLimit,
            BudgetState,
        )
        from polisyos.scientist.orchestration.engine.budget_ledger import (
            BudgetLedgerProducerRunBinding,
            FileBudgetLedger,
        )
        from polisyos.scientist.orchestration.engine.budget_middleware import (
            BudgetMiddleware,
        )
        from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient

        run_id = "search-owner-hidden-first-event"
        budget_key = f"nl-run:{run_id}"
        binding = BudgetLedgerProducerRunBinding(
            run_id=run_id,
            tenant_id="tenant-search-test",
            cell_id="cell-search-test",
            profile_id="search-profile-test",
            control_job_id="control-search-owner-hidden-first-event",
        )
        ledger_path = tmp_path / "hidden-first-event.json"
        owner = BudgetMiddleware(
            BudgetState(
                limits={
                    budget_key: BudgetLimit(
                        key=budget_key,
                        max_usd=Decimal("1.00"),
                    )
                }
            ),
            ledger=FileBudgetLedger(ledger_path),
        )
        response_json = json.dumps(
            {
                "model": "fixture-model",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '{"x":1.0,"semantic":{"interventions":[]}}',
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_cost_usd": 0,
                },
            }
        )

        class FakeResponse:
            status = 200
            headers: dict[str, str] = {}

            async def text(self) -> str:
                return response_json

        class FakeContext:
            async def __aenter__(self) -> FakeResponse:
                return FakeResponse()

            async def __aexit__(self, *_args: object) -> None:
                return None

        class FakeSession:
            closed = False

            def post(self, *_args: object, **_kwargs: object) -> FakeContext:
                return FakeContext()

            async def close(self) -> None:
                self.closed = True

        gateway = GatewayLLMClient(
            base_url="http://test.local",
            api_key="fixture-key",
            model="fixture-model",
            max_retries=0,
        )
        gateway._session = FakeSession()
        traced = TracedLLMClient(
            gateway,
            model_name="fixture-model",
            producer_settlement_store=owner,
            producer_budget_key=budget_key,
        )
        stage_b_calls: list[dict[str, Any]] = []

        def stage_b(candidate: dict[str, Any], _context: dict[str, Any]) -> dict[str, Any]:
            stage_b_calls.append(candidate)
            return {
                "simulation_results": {"x": candidate["x"]},
                "feedback": {"verdict": "APPROVE"},
            }

        controller = SearchController(
            config=SearchConfig(
                stopping=CostBudgetStopping(max_cost_usd=1.00),
                objective=quadratic_objective,
                producer_settlement_store=owner,
                producer_run_binding=binding,
            ),
            candidate_generator=TracedLLMCandidateGenerator(
                client=traced,
                system_prompt="Return one search candidate as a non-empty JSON object.",
            ),
            stage_a_evaluator=lambda candidate, context: (0.0, True),
            stage_b_evaluator=stage_b,
        )
        owner.list_producer_events_for_run_safe = lambda _binding: ()

        result = controller.run({"cumulative_cost_usd": 999.0})

        durable = FileBudgetLedger(ledger_path).snapshot()
        events = list(durable.producer_settlements.values())
        assert len(events) == 1
        assert events[0].run_binding == binding
        assert events[0].key == budget_key and events[0].status == "committed"
        assert events[0].amount == Decimal(0)
        assert stage_b_calls == []
        assert result.iterations_completed == 0
        assert result.stage_b_evaluations == 0
        assert result.telemetry["producer_budget_owner"]["status"] == "unavailable"
        assert "valueerror" in result.telemetry["producer_budget_owner"]["reason_code"]

    def test_durable_spend_crosses_cost_threshold_after_two_traced_calls(
        self,
        tmp_path,
        quadratic_objective,
    ) -> None:
        """The actual durable owner spend, not caller context, stops later evaluation."""
        import json
        from dataclasses import fields
        from decimal import Decimal

        from polisyos.core.llm.traced_client import TracedLLMClient
        from polisyos.scientist.orchestration.engine.budget import (
            BudgetLimit,
            BudgetState,
        )
        from polisyos.scientist.orchestration.engine.budget_ledger import (
            BudgetLedgerProducerRunBinding,
            FileBudgetLedger,
        )
        from polisyos.scientist.orchestration.engine.budget_middleware import (
            BudgetMiddleware,
        )
        from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient

        run_id = "search-owner-crosses-threshold"
        budget_key = f"nl-run:{run_id}"
        binding = BudgetLedgerProducerRunBinding(
            run_id=run_id,
            tenant_id="tenant-search-test",
            cell_id="cell-search-test",
            profile_id="search-profile-test",
            control_job_id="control-search-owner-crosses-threshold",
        )
        ledger_path = tmp_path / "crosses-threshold.json"
        owner = BudgetMiddleware(
            BudgetState(
                limits={
                    budget_key: BudgetLimit(
                        key=budget_key,
                        max_usd=Decimal("1.00"),
                    )
                }
            ),
            ledger=FileBudgetLedger(ledger_path),
        )
        response_json = json.dumps(
            {
                "model": "fixture-model",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '{"x":1.0,"semantic":{"interventions":[]}}',
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 2,
                    "completion_tokens": 1,
                    "total_cost_usd": 0.25,
                },
            }
        )

        dispatch_records: list[SearchIteration] = []
        controller: SearchController | None = None

        class FakeResponse:
            status = 200
            headers: dict[str, str] = {}

            async def text(self) -> str:
                return response_json

        class FakeContext:
            async def __aenter__(self) -> FakeResponse:
                return FakeResponse()

            async def __aexit__(self, *_args: object) -> None:
                return None

        class FakeSession:
            closed = False

            def __init__(self) -> None:
                self.request_count = 0
                self.requests: list[dict[str, Any]] = []

            def post(self, *_args: object, **kwargs: object) -> FakeContext:
                self.request_count += 1
                self.requests.append(dict(kwargs))
                if self.request_count == 2:
                    assert controller is not None
                    dispatch_records.extend(controller._history)
                return FakeContext()

            async def close(self) -> None:
                self.closed = True

        gateway = GatewayLLMClient(
            base_url="http://test.local",
            api_key="fixture-key",
            model="fixture-model",
            max_retries=0,
        )
        session = FakeSession()
        gateway._session = session
        traced = TracedLLMClient(
            gateway,
            model_name="fixture-model",
            producer_settlement_store=owner,
            producer_budget_key=budget_key,
        )
        stage_b_calls: list[dict[str, Any]] = []
        stage_b_results: list[dict[str, Any]] = []

        def stage_b(candidate: dict[str, Any], _context: dict[str, Any]) -> dict[str, Any]:
            stage_b_calls.append(candidate)
            result = {
                "simulation_results": {"x": candidate["x"]},
                "feedback": {"verdict": "APPROVE"},
            }
            stage_b_results.append(result)
            return result

        controller = SearchController(
            config=SearchConfig(
                stopping=CostBudgetStopping(max_cost_usd=0.30),
                objective=quadratic_objective,
                max_iterations_hard_limit=4,
                producer_settlement_store=owner,
                producer_run_binding=binding,
            ),
            candidate_generator=TracedLLMCandidateGenerator(
                client=traced,
                system_prompt="Return one search candidate as a non-empty JSON object.",
            ),
            stage_a_evaluator=lambda candidate, context: (0.0, True),
            stage_b_evaluator=stage_b,
        )

        result = controller.run({"cumulative_cost_usd": 999.0})

        durable = FileBudgetLedger(ledger_path).snapshot()
        events = list(durable.producer_settlements.values())
        assert session.request_count == 2
        second_request = session.requests[1]["json"]
        second_user_prompt = next(
            message["content"]
            for message in second_request["messages"]
            if message["role"] == "user"
        )
        second_history = json.loads(second_user_prompt.partition("Search inputs JSON:\n")[2])[
            "history"
        ]
        assert len(second_history) == 1
        assert len(dispatch_records) == 1
        first_record = dispatch_records[0]
        assert result.history == [first_record]

        source_candidate = {"x": 1.0, "semantic": {"interventions": []}}
        source_stage_b_result = {
            "simulation_results": {"x": 1.0},
            "feedback": {"verdict": "APPROVE"},
        }
        expected_objective = ObjectiveValue(
            name="quadratic",
            raw_value=1.0,
            direction=OptimizationDirection.MINIMIZE,
            weight=1.0,
            is_satisfied=True,
            threshold=None,
        )
        assert first_record.iteration == 0
        assert first_record.candidate == source_candidate
        assert first_record.objective_value == expected_objective.raw_value
        assert first_record.objective_details == [expected_objective]
        assert first_record.is_promising is True
        assert first_record.stage_a_passed is True
        assert first_record.stage_b_result == source_stage_b_result == stage_b_results[0]
        assert first_record.duration_seconds >= 0.0
        assert first_record.policy_evaluation is None
        assert isinstance(first_record.timestamp, datetime)
        assert first_record.policy_evaluation_status == "missing"
        assert first_record.policy_evaluation_error is None

        expected_objective_detail = {
            "name": expected_objective.name,
            "raw_value": expected_objective.raw_value,
            "direction": expected_objective.direction.value,
            "weight": expected_objective.weight,
            "is_satisfied": expected_objective.is_satisfied,
            "threshold": expected_objective.threshold,
        }
        objective_fields = {field.name for field in fields(ObjectiveValue)}
        assert set(expected_objective_detail) == objective_fields
        expected_history_row = {
            "iteration": first_record.iteration,
            "candidate": source_candidate,
            "objective_value": expected_objective.raw_value,
            "objective_details": [expected_objective_detail],
            "is_promising": True,
            "stage_a_passed": True,
            "stage_b_result": source_stage_b_result,
            "duration_seconds": first_record.duration_seconds,
            "policy_evaluation": None,
            "timestamp": first_record.timestamp.isoformat(),
            "policy_evaluation_status": "missing",
            "policy_evaluation_error": None,
        }
        expected_history_fields = {field.name for field in fields(SearchIteration)}
        assert set(expected_history_row) == expected_history_fields
        assert set(second_history[0]) == expected_history_fields
        assert second_history[0]["objective_details"] == [expected_objective_detail]
        assert set(second_history[0]["objective_details"][0]) == objective_fields
        assert second_history[0] == expected_history_row
        assert len(events) == 2
        assert all(event.run_binding == binding for event in events)
        assert all(event.key == budget_key and event.status == "committed" for event in events)
        assert sum((event.amount or Decimal(0) for event in events), Decimal(0)) == Decimal("0.50")
        assert Decimal(result.telemetry["producer_budget_owner"]["spent"]) == Decimal("0.50")
        assert result.iterations_completed == 1
        assert result.stage_b_evaluations == 1
        assert len(stage_b_calls) == 1
        assert result.stopping_reason is not None
        assert "Cost budget" in result.stopping_reason

    def test_malformed_typed_evaluation_cannot_fall_back_to_legacy_objective(
        self,
        quadratic_objective,
    ):
        """A present invalid typed result remains blocked at the consumer boundary."""

        class StaticGenerator:
            def generate(self, history, current_best, context):
                del history, current_best, context
                return {"x": 1.0, "semantic": {"interventions": []}}

        controller = SearchController(
            config=SearchConfig(
                stopping=MaxIterations(1),
                objective=quadratic_objective,
            ),
            candidate_generator=StaticGenerator(),
            stage_a_evaluator=lambda candidate, context: (0.0, True),
            stage_b_evaluator=lambda candidate, context: {
                "simulation_results": {"x": -10.0},
                "feedback": {"verdict": "APPROVE"},
                "policy_evaluation": {"unexpected": "typed payload"},
            },
        )

        result = controller.run({"user_request": "malformed typed"})

        assert result.best_candidate is None
        assert result.history[0].objective_value == float("inf")
        assert result.history[0].policy_evaluation is None
        assert result.history[0].policy_evaluation_status == "invalid"
        assert result.history[0].policy_evaluation_error == "policy_evaluation_parse_failed"
        assert result.history[0].is_promising is False
        assert result.telemetry["policy_evaluation_errors"] == 1

    def test_valid_infeasible_typed_evaluation_remains_typed(self, quadratic_objective):
        """A valid blocking vector is not converted into the legacy scalar path."""
        from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector

        class StaticGenerator:
            def generate(self, history, current_best, context):
                del history, current_best, context
                return {"x": -10.0, "semantic": {"interventions": []}}

        controller = SearchController(
            config=SearchConfig(
                stopping=MaxIterations(1),
                objective=quadratic_objective,
            ),
            candidate_generator=StaticGenerator(),
            stage_a_evaluator=lambda candidate, context: (0.0, True),
            stage_b_evaluator=lambda candidate, context: {
                "simulation_results": {"x": -10.0},
                "feedback": {"verdict": "REJECT"},
                "policy_evaluation": PolicyEvaluationVector(
                    feasible=False,
                    blocking_reasons=["budget_constraint"],
                ),
            },
        )

        result = controller.run({"user_request": "infeasible typed"})

        evaluation = result.history[0].policy_evaluation
        assert evaluation is not None
        assert evaluation.feasible is False
        assert result.history[0].policy_evaluation_status == "valid"
        assert result.history[0].is_promising is False
        assert result.history[0].objective_value >= 1_000_000.0

    def test_concurrent_runs_are_rejected_as_non_reentrant(self, quadratic_objective):
        """One mutable controller rejects a second run while the first is active."""

        first_entered_stage_b = Event()
        release_first_stage_b = Event()

        class StaticGenerator:
            def generate(self, history, current_best, context):
                del history, current_best
                return {"x": context["run_id"], "semantic": {"interventions": []}}

        def stage_a(candidate, context):
            del candidate, context
            return 0.0, True

        def stage_b(candidate, context):
            del context
            if candidate["x"] == "first":
                first_entered_stage_b.set()
                release_first_stage_b.wait(timeout=2.0)
            return {
                "simulation_results": {"x": 1.0},
                "feedback": {"verdict": "APPROVE"},
            }

        controller = SearchController(
            config=SearchConfig(
                stopping=MaxIterations(1),
                objective=quadratic_objective,
            ),
            candidate_generator=StaticGenerator(),
            stage_a_evaluator=stage_a,
            stage_b_evaluator=stage_b,
        )
        outcomes: dict[str, Any] = {}
        errors: dict[str, Exception] = {}

        def invoke(label: str, run_id: str) -> None:
            try:
                outcomes[label] = controller.run(
                    {"run_id": run_id},
                    initial_candidate={
                        "x": run_id,
                        "semantic": {"interventions": []},
                    },
                )
            except Exception as exc:
                errors[label] = exc

        first_thread = Thread(target=invoke, args=("first", "first"))
        second_thread = Thread(target=invoke, args=("second", "second"))
        first_thread.start()
        assert first_entered_stage_b.wait(timeout=2.0)
        second_thread.start()
        second_thread.join(timeout=2.0)
        release_first_stage_b.set()
        first_thread.join(timeout=2.0)

        assert not first_thread.is_alive()
        assert not second_thread.is_alive()
        assert "first" in outcomes
        assert "second" not in outcomes
        second_error = errors.get("second")
        assert isinstance(second_error, RuntimeError)
        assert str(second_error) == "SearchController.run is not reentrant"

    def test_diversity_telemetry_is_scoped_to_each_run(self, quadratic_objective, monkeypatch):
        """Fresh runs reset diversity telemetry without a cross-run contract."""

        monkeypatch.setenv("POLISYOS_SEARCH_DIVERSITY_ENABLED", "true")

        class ContextGenerator:
            def generate(self, history, current_best, context):
                del history, current_best
                return {
                    "x": 1.0,
                    "semantic": {
                        "interventions": [{"mechanism_type": context["run_id"]}],
                    },
                }

        controller = SearchController(
            config=SearchConfig(
                stopping=MaxIterations(1),
                objective=quadratic_objective,
            ),
            candidate_generator=ContextGenerator(),
            stage_a_evaluator=lambda candidate, context: (0.0, True),
            stage_b_evaluator=lambda candidate, context: {
                "simulation_results": {"x": candidate["x"]},
                "feedback": {"verdict": "APPROVE"},
            },
        )

        first = controller.run({"run_id": "first-mechanism"})
        second = controller.run({"run_id": "second-mechanism"})

        assert first.telemetry["diversity_unique_mechanisms_total"] == 1
        assert second.telemetry["diversity_unique_mechanisms_total"] == 1
        assert second.telemetry["diversity_ratio"] == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Test: Stopping Criteria
# ─────────────────────────────────────────────────────────────────────────────


class TestStoppingCriteria:
    """Test stopping criteria behavior."""

    def test_max_iterations_stops_exactly(self):
        """MaxIterations(5) should stop after exactly 5 iterations."""
        criterion = MaxIterations(5)

        history = []
        for i in range(10):
            result = criterion.check(history, {"iteration": i})
            if result.should_stop:
                assert i == 5
                break
            history.append({"iteration": i, "objective_value": 1.0})
        else:
            pytest.fail("Should have stopped")

    def test_improvement_plateau_triggers(self):
        """ImprovementPlateau should trigger when no improvement."""
        criterion = ImprovementPlateau(patience=3, min_improvement=0.01)

        history = [
            {"objective_value": 1.0},
            {"objective_value": 1.0},
            {"objective_value": 1.0},
            {"objective_value": 1.0},
        ]

        result = criterion.check(history, {})
        assert result.should_stop
        assert "plateau" in result.reason.lower()

    def test_improvement_plateau_stops_after_zero_then_positive_loss(self):
        """A positive loss after a zero minimum is not infinite improvement."""
        criterion = ImprovementPlateau(patience=2, min_improvement=0.01)

        result = criterion.check(
            [
                {"objective_value": 0.0},
                {"objective_value": 1.0},
                {"objective_value": 1.0},
            ],
            {},
        )

        assert result.should_stop
        improvement = result.details["improvement"]
        assert math.isfinite(improvement)
        assert improvement == pytest.approx(-1.0)

    def test_improvement_plateau_preserves_negative_gain_after_zero(self):
        """A negative objective after zero remains a real improvement."""
        criterion = ImprovementPlateau(patience=2, min_improvement=0.01)

        result = criterion.check(
            [
                {"objective_value": 0.0},
                {"objective_value": -1.0},
                {"objective_value": -1.0},
            ],
            {},
        )

        assert not result.should_stop

    def test_improvement_plateau_keeps_real_progress_open(self):
        """A normal positive relative gain still prevents an early stop."""
        criterion = ImprovementPlateau(patience=2, min_improvement=0.01)

        result = criterion.check(
            [
                {"objective_value": 2.0},
                {"objective_value": 1.0},
                {"objective_value": 1.0},
            ],
            {},
        )

        assert not result.should_stop

    @pytest.mark.parametrize(
        "invalid_value",
        [
            pytest.param(math.inf, id="positive-infinity"),
            pytest.param(-math.inf, id="negative-infinity"),
            pytest.param(math.nan, id="nan"),
            pytest.param(None, id="null"),
            pytest.param("not-a-number", id="malformed-string"),
            pytest.param(True, id="boolean-is-not-a-metric"),
        ],
    )
    def test_improvement_plateau_refuses_nonfinite_or_malformed_window_values(self, invalid_value):
        criterion = ImprovementPlateau(patience=2, min_improvement=0.01)
        history = [{"objective_value": 1.0} for _ in range(4)]
        history[-1]["objective_value"] = invalid_value

        result = criterion.check(history, {})

        assert not result.should_stop

    def test_improvement_plateau_does_not_drop_a_missing_historical_observation(self):
        criterion = ImprovementPlateau(patience=2, min_improvement=0.01)
        history = [
            {},
            {"objective_value": 1.0},
            {"objective_value": 1.0},
            {"objective_value": 1.0},
        ]

        result = criterion.check(history, {})

        assert not result.should_stop

    def test_improvement_plateau_does_not_treat_malformed_history_row_as_absence(self):
        criterion = ImprovementPlateau(patience=2, min_improvement=0.01)
        history = [
            None,
            {"objective_value": 1.0},
            {"objective_value": 1.0},
            {"objective_value": 1.0},
        ]

        result = criterion.check(history, {})

        assert not result.should_stop

    def test_search_controller_preserves_best_through_nonfinite_plateau_history(
        self, quadratic_objective
    ):
        class SequenceGenerator:
            def __init__(self):
                self._values = iter((0.0, math.inf, math.inf, 0.0))

            def generate(self, history, current_best, context):
                del history, current_best, context
                return {"x": next(self._values)}

        controller = SearchController(
            config=SearchConfig(
                stopping=ImprovementPlateau(patience=2, min_improvement=0.01),
                objective=quadratic_objective,
                max_iterations_hard_limit=4,
            ),
            candidate_generator=SequenceGenerator(),
            stage_a_evaluator=lambda candidate, context: (0.0, True),
            stage_b_evaluator=lambda candidate, context: {
                "simulation_results": {"x": candidate["x"]},
                "feedback": {"verdict": "APPROVE"},
            },
        )

        result = controller.run(initial_context={})

        assert result.iterations_completed == 4
        assert result.best_candidate == {"x": 0.0}
        assert result.best_objective == 0.0
        assert math.isinf(result.history[1].objective_value)
        assert math.isinf(result.history[2].objective_value)
        assert result.stopping_reason is not None
        assert "Hard iteration limit" in result.stopping_reason

    def test_composite_stops_on_first_trigger(self):
        """Composite should stop when ANY criterion triggers."""
        composite = CompositeStoppingCriterion(
            [
                MaxIterations(10),
                MaxWallTime(0.001),
            ]
        )

        import time

        time.sleep(0.01)

        result = composite.check([{"objective_value": 1.0}], {})
        assert result.should_stop
        assert "wall_time" in result.details.get("triggered_by", "").lower()


# ─────────────────────────────────────────────────────────────────────────────
# Test: Two-Stage Filtering
# ─────────────────────────────────────────────────────────────────────────────


class TestTwoStageFiltering:
    """
    Test that Stage A filtering prevents Stage B execution.

    Critical: If CheapStage returns is_promising=False, ExpensiveStage
    should NEVER be called. This saves expensive simulation compute.
    """

    def test_stage_a_rejection_skips_stage_b(self, mock_candidate_generator, quadratic_objective):
        """ExpensiveStage should NOT be called if CheapStage rejects."""

        stage_b_called = [False]

        def stage_a_evaluator(candidate, context):
            return 1.0, False

        def stage_b_evaluator(candidate, context):
            stage_b_called[0] = True
            return {"simulation_results": {}, "feedback": {"verdict": "APPROVE"}}

        config = SearchConfig(
            stopping=MaxIterations(3),
            objective=quadratic_objective,
            enable_stage_a=True,
        )

        controller = SearchController(
            config=config,
            candidate_generator=mock_candidate_generator,
            stage_a_evaluator=stage_a_evaluator,
            stage_b_evaluator=stage_b_evaluator,
        )

        result = controller.run({"user_request": "test"})

        assert not stage_b_called[0], "Stage B was called despite Stage A rejection!"
        assert result.stage_a_evaluations == 3
        assert result.stage_b_evaluations == 0

    def test_stage_a_approval_runs_stage_b(self, mock_candidate_generator, quadratic_objective):
        """ExpensiveStage SHOULD be called if CheapStage approves."""

        stage_b_count = [0]

        def stage_a_evaluator(candidate, context):
            return 0.0, True

        def stage_b_evaluator(candidate, context):
            stage_b_count[0] += 1
            return {
                "simulation_results": {"x": 1.0},
                "feedback": {"verdict": "APPROVE"},
            }

        config = SearchConfig(
            stopping=MaxIterations(3),
            objective=quadratic_objective,
            enable_stage_a=True,
        )

        controller = SearchController(
            config=config,
            candidate_generator=mock_candidate_generator,
            stage_a_evaluator=stage_a_evaluator,
            stage_b_evaluator=stage_b_evaluator,
        )

        result = controller.run({"user_request": "test"})

        assert stage_b_count[0] == 3
        assert result.stage_b_evaluations == 3

    def test_cheap_stage_rejects_invalid_params(self):
        """CheapStage should reject policies with invalid parameters."""
        stage = CheapStage(threshold=0.5)

        bad_candidate = {
            "semantic": {
                "interventions": [{"mechanism": "income_tax", "parameters": {"rate": 1.5}}],
            },
        }

        result = stage.evaluate(bad_candidate, {})

        assert not result.is_promising
        assert result.objective_value >= 0.5


# ─────────────────────────────────────────────────────────────────────────────
# Test: Workflow Engine Abstraction
# ─────────────────────────────────────────────────────────────────────────────


class TestWorkflowEngineAbstraction:
    """Test that WorkflowEngine protocol is properly implemented."""

    def test_simple_engine_runs_to_completion(self):
        """SimpleLoopEngine should execute all nodes."""
        execution_log = []

        def node_a(state):
            execution_log.append("a")
            return {**state, "a_done": True}

        def node_b(state):
            execution_log.append("b")
            return {**state, "b_done": True}

        engine = SimpleLoopEngine(
            [
                ("node_a", node_a),
                ("node_b", node_b),
            ]
        )

        result = engine.run({"initial": True})

        assert execution_log == ["a", "b"]
        assert result["a_done"]
        assert result["b_done"]

    @pytest.mark.asyncio
    async def test_simple_engine_run_async_awaits_nodes_and_honors_terminal(self):
        """SimpleLoopEngine.run_async should keep owner loop semantics for async nodes."""

        execution_log = []

        async def node_a(state):
            execution_log.append("a")
            return {**state, "a_done": True}

        async def node_b(state):
            execution_log.append("b")
            return {**state, "b_done": True}

        async def node_c(state):
            execution_log.append("c")
            return {**state, "c_done": True}

        engine = SimpleLoopEngine(
            [
                ("node_a", node_a),
                ("node_b", node_b),
                ("node_c", node_c),
            ],
            terminal_node="node_b",
        )

        result = await engine.run_async({"initial": True})

        assert execution_log == ["a", "b"]
        assert result["a_done"]
        assert result["b_done"]
        assert "c_done" not in result

    def test_simple_engine_step_by_step(self):
        """SimpleLoopEngine.step() should execute one node at a time."""

        def node_a(state):
            return {**state, "step": 1}

        def node_b(state):
            return {**state, "step": 2}

        engine = SimpleLoopEngine(
            [
                ("node_a", node_a),
                ("node_b", node_b),
            ]
        )

        state = {"initial": True}

        state, done = engine.step(state)
        assert state["step"] == 1
        assert not done

        state, done = engine.step(state)
        assert state["step"] == 2
        assert done

    def test_engine_protocol_compliance(self):
        """Verify engines satisfy WorkflowEngine protocol."""
        from polisyos.scientist.orchestration.workflows.engine_base import (
            WorkflowEngine,
        )

        engine = SimpleLoopEngine([("test", lambda s: s)])

        assert hasattr(engine, "run")
        assert hasattr(engine, "step")
        assert hasattr(engine, "current_phase")
        assert hasattr(engine, "reset")

        assert isinstance(engine, WorkflowEngine)


# ─────────────────────────────────────────────────────────────────────────────
# Test: Objectives
# ─────────────────────────────────────────────────────────────────────────────


class TestObjectives:
    """Test objective evaluation."""

    def test_gdp_objective_maximizes(self):
        """GDP objective should maximize (negative normalized value)."""
        obj = GDPGrowthObjective(weight=1.0)

        result = obj.evaluate({"gdp_change": 0.05})

        assert result.raw_value == 0.05
        assert result.normalized_value == -0.05

    def test_composite_combines_correctly(self):
        """Composite objective should combine weighted normalized values."""
        objective = ObjectivePresets.balanced_growth()

        results = {
            "gdp_change": 0.03,
            "gov_balance": -100.0,
            "gini_coefficient": 0.35,
        }

        value = objective.evaluate(results)

        assert isinstance(value.raw_value, float)
        assert value.is_satisfied


@pytest.mark.parametrize(
    ("simulation_results", "expected_score", "limited"),
    [
        pytest.param({"gdp_change": 0.05}, -0.05, True, id="marker-absent"),
        pytest.param(
            {"gdp_change": 0.05, "budget_deficit_objective_usable": True},
            -0.05,
            True,
            id="stale-available-marker",
        ),
        pytest.param(
            {"gdp_change": 0.05, "budget_deficit": 0.02},
            -0.04,
            False,
            id="valid-alias-marker-absent",
        ),
        pytest.param(
            {
                "gdp_change": 0.05,
                "budget_deficit": 0.02,
                "budget_deficit_objective_usable": False,
            },
            -0.04,
            False,
            id="stale-unavailable-marker",
        ),
    ],
)
def test_expensive_stage_derives_fiscal_limitation_from_embedded_results(
    simulation_results: dict[str, Any], expected_score: float, limited: bool
) -> None:
    """The cold-start embedded producer cannot suppress source-derived limitation."""
    from polisyos.scientist.methods.search.cold_start import (
        _EmbeddedResultsWorkflowEngine,
    )

    feedback: dict[str, Any] = {"verdict": "APPROVE"}
    if not limited:
        feedback["objective_limitations"] = [
            "budget_deficit_unavailable_required_float_legacy_zero"
        ]
    candidate = {
        "expected_stage4": {
            "simulation_results": simulation_results,
            "feedback": feedback,
        }
    }
    result = ExpensiveStage(_EmbeddedResultsWorkflowEngine()).evaluate(candidate, {})

    assert result.objective_value == pytest.approx(expected_score)
    assert (
        "budget_deficit_unavailable_required_float_legacy_zero"
        in result.feedback.get("objective_limitations", [])
    ) is limited


# ─────────────────────────────────────────────────────────────────────────────
# Integration Test
# ─────────────────────────────────────────────────────────────────────────────


class TestIntegration:
    """Full integration tests for the search system."""

    def test_end_to_end_search_with_mock_workflow(self):
        """
        End-to-end test: SearchController -> CheapStage -> ExpensiveStage
        with mocked workflow engine.
        """
        mock_engine = MagicMock()
        mock_engine.run.return_value = {
            "simulation_results": {
                "gdp_change": 0.02,
                "gov_balance": 50.0,
                "gini_coefficient": 0.3,
            },
            "feedback": {"verdict": "APPROVE"},
        }

        cheap = CheapStage(threshold=0.5)
        expensive = ExpensiveStage(mock_engine)

        def stage_a_fn(candidate, context):
            result = cheap.evaluate(candidate, context)
            return result.objective_value, result.is_promising

        def stage_b_fn(candidate, context):
            result = expensive.evaluate(candidate, context)
            return {
                "simulation_results": result.simulation_results,
                "feedback": result.feedback,
            }

        class StaticGenerator:
            def generate(self, history, best, context):
                return {
                    "semantic": {
                        "interventions": [{"mechanism": "tax", "parameters": {"rate": 0.2}}],
                        "objectives": ["growth"],
                    },
                }

        config = SearchConfig(
            stopping=MaxIterations(2),
            objective=ObjectivePresets.balanced_growth(),
        )

        controller = SearchController(
            config=config,
            candidate_generator=StaticGenerator(),
            stage_a_evaluator=stage_a_fn,
            stage_b_evaluator=stage_b_fn,
        )

        result = controller.run({"user_request": "Optimize growth"})

        assert result.status == SearchStatus.STOPPED
        assert result.iterations_completed == 2
        assert result.best_candidate is not None
        assert mock_engine.run.call_count == 2


class TestGenerationContext:
    def test_search_controller_exposes_execution_plan_mutations_in_generation_context(
        self,
        quadratic_objective,
    ):
        snapshot = build_method_catalog_snapshot(run_id="R_search_context")
        baseline_plan = ExecutionPlan(
            plan_id="plan_search_context",
            method_dag=[
                MethodDagNode(
                    node_id="node_lp",
                    method_fqn="optimization.resource_lp@1.0.0",
                    notes=["optional_leaf"],
                )
            ],
        )
        preflight = preflight_execution_plan(baseline_plan, snapshot)

        class ContextCapturingGenerator:
            def __init__(self):
                self.contexts: list[dict[str, Any]] = []

            def generate(self, history, current_best, context):
                del history, current_best
                self.contexts.append(dict(context))
                return {"x": 1.0, "semantic": {"interventions": []}}

        generator = ContextCapturingGenerator()

        controller = SearchController(
            config=SearchConfig(stopping=MaxIterations(1), objective=quadratic_objective),
            candidate_generator=generator,
            stage_a_evaluator=lambda candidate, context: (0.0, True),
            stage_b_evaluator=lambda candidate, context: {
                "simulation_results": {"x": candidate.get("x", 1.0)},
                "feedback": {"verdict": "APPROVE"},
            },
        )

        controller.run(
            {
                "baseline_execution_plan": baseline_plan,
                "catalog_snapshot": snapshot,
                "preflight_report": preflight,
            }
        )

        assert generator.contexts
        first_context = generator.contexts[0]
        assert first_context["search_state"]["iteration"] == 0
        assert first_context["execution_plan_topology_mutation_count"] >= 1
        assert any(
            item["replacement_method_fqn"] == "optimization.linear.resource_lp@1.0.0"
            for item in first_context["execution_plan_topology_mutation_payload"]
            if item["kind"] == "swap_method"
        )

    def test_search_controller_refreshes_mutation_context_from_stage_b_feedback(
        self,
        quadratic_objective,
    ):
        snapshot = build_method_catalog_snapshot(run_id="R_search_context")
        baseline_plan = ExecutionPlan(
            plan_id="plan_search_feedback",
            method_dag=[
                MethodDagNode(
                    node_id="node_lp",
                    method_fqn="optimization.resource_lp@1.0.0",
                )
            ],
        )
        preflight = preflight_execution_plan(baseline_plan, snapshot)

        class ContextCapturingGenerator:
            def __init__(self):
                self.contexts: list[dict[str, Any]] = []

            def generate(self, history, current_best, context):
                del history, current_best
                self.contexts.append(dict(context))
                return {"x": 1.0, "semantic": {"interventions": []}}

        generator = ContextCapturingGenerator()

        controller = SearchController(
            config=SearchConfig(stopping=MaxIterations(2), objective=quadratic_objective),
            candidate_generator=generator,
            stage_a_evaluator=lambda candidate, context: (0.0, True),
            stage_b_evaluator=lambda candidate, context: {
                "simulation_results": {"x": candidate.get("x", 1.0)},
                "feedback": {"verdict": "APPROVE"},
                "preflight_report": preflight,
                "catalog_snapshot": snapshot,
            },
        )

        controller.run({"baseline_execution_plan": baseline_plan})

        assert len(generator.contexts) == 2
        assert "execution_plan_topology_mutation_payload" not in generator.contexts[0]
        assert generator.contexts[1]["execution_plan_topology_mutation_count"] >= 1
