from __future__ import annotations

import json

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.agent.failure_card import (
    FailureCard,
    FailureSource,
)
from polisyos.scientist.agent.persistent_memory import (
    PersistentMemoryStore,
    problem_signature,
    tool_error_pattern_tag,
)
from polisyos.scientist.agent.reflexion import (
    ReflexionConfig,
    ReflexionDecision,
    ReflexionOrchestrator,
)
from polisyos.scientist.agent.reflexion_evaluator import RubricReflexionEvaluator


class _FakeArtifactStore:
    def __init__(self) -> None:
        self._payloads: dict[str, bytes] = {}
        self._counter = 0

    def put_json(self, data, options=None):
        del options
        self._counter += 1
        artifact_id = f"sha256:{self._counter:064d}"
        self._payloads[artifact_id] = json.dumps(data, default=str).encode()
        return ArtifactRef(
            artifact_id=artifact_id,
            kind="test",
            media_type="application/json",
        )

    def get_bytes(self, artifact_id):
        return self._payloads[str(artifact_id)]


def test_store_and_recall_reflexion_memory_by_problem_and_error_pattern() -> None:
    memory = PersistentMemoryStore(_FakeArtifactStore())
    memory.store_reflexion_memory(
        problem_statement="Design a transport subsidy policy",
        reflection="Use tighter tool args and cite transport ministry sources.",
        trajectory_summary="Attempt 1 failed with invalid tool args.",
        source_run_id="run-1",
        error_code="SCHEMA_VALIDATION_ERROR",
        tool_error_patterns=["scholar_web_search:invalid_arguments"],
    )

    recalled = memory.recall_reflexion_memories(
        problem_statement="Design a transport subsidy policy",
        error_code="SCHEMA_VALIDATION_ERROR",
        tool_error_patterns=["scholar_web_search:invalid_arguments"],
    )

    assert len(recalled) == 1
    assert "Use tighter tool args" in recalled[0].content
    assert f"problem:{problem_signature('Design a transport subsidy policy')}" in recalled[0].tags
    assert tool_error_pattern_tag("scholar_web_search:invalid_arguments") in recalled[0].tags


def test_reflexion_orchestrator_injects_prior_reflections_and_stores_retry_outcome() -> None:
    memory = PersistentMemoryStore(_FakeArtifactStore())
    memory.store_reflexion_memory(
        problem_statement="Design a carbon tax policy",
        reflection="When schema validation fails, regenerate only the malformed field and reuse known-good sections.",
        trajectory_summary="Previous run repeated the same malformed JSON shape twice.",
        source_run_id="run-old",
        error_code="SCHEMA_VALIDATION_ERROR",
        tool_error_patterns=["formalizer:invalid_arguments"],
    )
    orchestrator = ReflexionOrchestrator(
        ReflexionConfig(memory_recall_limit=3),
        persistent_memory=memory,
        evaluator=RubricReflexionEvaluator(),
    )
    card = FailureCard.generate(
        source_step=FailureSource.VALIDATOR_SCHEMA,
        error_code="SCHEMA_VALIDATION_ERROR",
        violation_summary="Formalizer emitted malformed JSON",
        remediation_advice="Fix malformed JSON",
        run_id="run-new",
        technical_details={
            "tool_name": "formalizer",
            "error_type": "invalid_arguments",
        },
    )

    retry_context = orchestrator.prepare_retry_context(
        card,
        {
            "user_request": "Design a carbon tax policy",
            "failure_history": [],
        },
    )

    assert "prior_reflections" in retry_context
    assert "reuse known-good sections" in retry_context["prior_reflections"]
    assert retry_context["problem_signature"] == problem_signature(
        "Design a carbon tax policy"
    )

    scorecard = orchestrator.evaluate_candidate(
        objective="Design a carbon tax policy",
        output_text="A carbon tax proposal with legal and fiscal reasoning.",
        output_data={"answer": "ok"},
        expected_output_schema={"type": "object", "required": ["answer"]},
    )
    orchestrator.record_retry_outcome(
        card,
        ReflexionDecision.RETURN_TO_FORMALIZER,
        success=False,
        evaluation=scorecard,
        problem_statement="Design a carbon tax policy",
        trajectory_summary="Attempt 2 still failed schema validation.",
        tool_error_patterns=["formalizer:invalid_arguments"],
    )

    memories = memory.recall_reflexion_memories(
        problem_statement="Design a carbon tax policy",
        error_code="SCHEMA_VALIDATION_ERROR",
        tool_error_patterns=["formalizer:invalid_arguments"],
        max_results=10,
    )
    assert len(memories) >= 2
    assert any("Attempt 2 still failed schema validation" in entry.content for entry in memories)
