from __future__ import annotations

from typing import Literal

import pytest

from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.scientist.methods.search.judge_stack import (
    JudgeInputBundle,
    JudgeName,
    JudgeStack,
)
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    persist_policy_candidate_schema,
)
from polisyos.scientist.replay.verification import (
    REPLAY_VERIFICATION_REPORT_SCHEMA_NAME,
    ReplayVerificationReport,
    load_replay_verification_report,
    verify_and_persist_replay_bundle,
)
from tests.unit.scientist.replay.test_verification_owner_admission import (
    _foreign_schema_report_ref,
    _persist_replay_bundle,
)
from tests.unit.scientist.search.test_phase_b_policy_runtime import _candidate


def _replay_inputs(
    store: FileSystemCAS,
) -> tuple[PolicyCandidateSchema, ArtifactRef, ArtifactRef, ArtifactRef, ArtifactRef]:
    candidate = _candidate()
    candidate_ref = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    evaluation_ref = store.put_json(
        {"candidate_id": candidate_ref.artifact_id, "score": 1.0},
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            schema=SchemaInfo(name="tests.PolicyEvaluationVector", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    replay_ref = _persist_replay_bundle(
        store,
        run_id="run-judge-replay-owner",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
    )
    verification_ref = verify_and_persist_replay_bundle(
        store,
        run_id="run-judge-replay-owner",
        replay_bundle_ref=replay_ref,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
    )
    return candidate, candidate_ref, evaluation_ref, replay_ref, verification_ref


def _constructed_complete_report(replay_ref: ArtifactRef) -> ReplayVerificationReport:
    return ReplayVerificationReport(
        run_id="run-judge-replay-owner",
        replay_bundle_ref=replay_ref,
        verification_mode="semantic_diff",
        completeness_level="complete",
        passed=True,
        overall_similarity=1.0,
    )


def _judge_input(
    *,
    candidate: PolicyCandidateSchema,
    candidate_ref: ArtifactRef,
    evaluation_ref: ArtifactRef,
    replay_ref: ArtifactRef,
    verification_ref: ArtifactRef | None,
    report: ReplayVerificationReport | None,
    claim_mode: Literal["proof_only", "bounds", "estimation"] = "estimation",
) -> JudgeInputBundle:
    return JudgeInputBundle(
        candidate=candidate,
        replay_bundle_ref=replay_ref,
        replay_verification_ref=verification_ref,
        replay_verification_report=report,
        claim_mode=claim_mode,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        state={"audit_lineage_complete": True, "checkpoints": ["checkpoint-1"]},
        run_id="run-judge-replay-owner",
    )


def _persist_report_variant(
    store: FileSystemCAS,
    verification_ref: ArtifactRef,
    *,
    changes: dict[str, object],
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    source_manifest = store.get_manifest(verification_ref)
    source_report = load_replay_verification_report(store, verification_ref)
    report = source_report.model_copy(update=changes)
    return store.put_json(
        report,
        PutOptions(
            kind="scientist.replay_verification_report",
            media_type="application/json",
            schema=SchemaInfo(
                name=REPLAY_VERIFICATION_REPORT_SCHEMA_NAME,
                version="1.0",
            ),
            inputs=list(source_manifest.inputs) if inputs is None else inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def test_judge_resolves_foreign_selected_profile_even_with_complete_report_object(store) -> None:
    candidate, candidate_ref, evaluation_ref, replay_ref, verification_ref = _replay_inputs(store)
    foreign_ref = _foreign_schema_report_ref(store, verification_ref)
    complete_but_unbound = _constructed_complete_report(replay_ref)
    bundle = _judge_input(
        candidate=candidate,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        replay_ref=replay_ref,
        verification_ref=foreign_ref,
        report=complete_but_unbound,
    )

    with pytest.raises(ValueError):
        JudgeStack(store=store).evaluate(
            bundle,
            active_judges={JudgeName.REPRODUCIBILITY},
        )


def test_judge_uses_selected_artifact_when_optional_report_object_disagrees(store) -> None:
    candidate, candidate_ref, evaluation_ref, replay_ref, verification_ref = _replay_inputs(store)
    contradictory_object = ReplayVerificationReport(
        run_id="run-judge-replay-owner",
        replay_bundle_ref=replay_ref,
        verification_mode="artifact_snapshot",
        completeness_level="incomplete",
        passed=False,
        overall_similarity=0.0,
        reason_codes=["untrusted_in_memory_value"],
    )
    bundle = _judge_input(
        candidate=candidate,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        replay_ref=replay_ref,
        verification_ref=verification_ref,
        report=contradictory_object,
    )

    verdict = JudgeStack(store=store).evaluate(
        bundle,
        active_judges={JudgeName.REPRODUCIBILITY},
    )
    reproducibility = verdict.per_judge[JudgeName.REPRODUCIBILITY.value]

    assert reproducibility.metrics["replay_match"] == 1.0
    assert reproducibility.metrics["replay_complete"] == 1.0
    assert not any(card.failure_type == "replay_incomplete" for card in verdict.blocking_failures)
    assert any(
        card.failure_type == "replay_verification_unmeasured" for card in verdict.blocking_failures
    )


def test_judge_rejects_selected_report_from_another_run(store) -> None:
    candidate, candidate_ref, evaluation_ref, replay_ref, verification_ref = _replay_inputs(store)
    foreign_run_ref = _persist_report_variant(
        store,
        verification_ref,
        changes={"run_id": "another-run"},
    )
    bundle = _judge_input(
        candidate=candidate,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        replay_ref=replay_ref,
        verification_ref=foreign_run_ref,
        report=None,
    )

    with pytest.raises(ValueError, match="run"):
        JudgeStack(store=store).evaluate(
            bundle,
            active_judges={JudgeName.REPRODUCIBILITY},
        )

    whitespace_variant = bundle.model_copy(update={"run_id": f"{bundle.run_id} "})
    with pytest.raises(ValueError, match="run"):
        JudgeStack(store=store).evaluate(
            whitespace_variant,
            active_judges={JudgeName.REPRODUCIBILITY},
        )


def test_judge_rejects_same_artifact_with_a_foreign_replay_profile(store) -> None:
    candidate, candidate_ref, evaluation_ref, replay_ref, verification_ref = _replay_inputs(store)
    foreign_replay_ref = replay_ref.model_copy(
        update={"manifest_profile_sha256": f"sha256:{'f' * 64}"}
    )
    foreign_replay_edge = input_ref_from_artifact_ref(
        foreign_replay_ref,
        role="replay_bundle",
    )
    source_inputs = list(store.get_manifest(verification_ref).inputs)
    foreign_inputs = [
        foreign_replay_edge if item.role == "replay_bundle" else item for item in source_inputs
    ]
    foreign_ref = _persist_report_variant(
        store,
        verification_ref,
        changes={"replay_bundle_ref": foreign_replay_ref},
        inputs=foreign_inputs,
    )
    assert foreign_replay_ref.artifact_id == replay_ref.artifact_id
    assert foreign_replay_ref.manifest_profile_sha256 != replay_ref.manifest_profile_sha256
    bundle = _judge_input(
        candidate=candidate,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        replay_ref=replay_ref,
        verification_ref=foreign_ref,
        report=None,
    )

    with pytest.raises(ValueError, match="replay"):
        JudgeStack(store=store).evaluate(
            bundle,
            active_judges={JudgeName.REPRODUCIBILITY},
        )


def test_judge_rejects_report_without_selected_replay_input_edge(store) -> None:
    candidate, candidate_ref, evaluation_ref, replay_ref, verification_ref = _replay_inputs(store)
    source_inputs = list(store.get_manifest(verification_ref).inputs)
    no_replay_edge = [item for item in source_inputs if item.role != "replay_bundle"]
    unbound_ref = _persist_report_variant(
        store,
        verification_ref,
        changes={},
        inputs=no_replay_edge,
    )
    bundle = _judge_input(
        candidate=candidate,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        replay_ref=replay_ref,
        verification_ref=unbound_ref,
        report=None,
    )

    with pytest.raises(ValueError, match="input"):
        JudgeStack(store=store).evaluate(
            bundle,
            active_judges={JudgeName.REPRODUCIBILITY},
        )


def test_judge_recomputes_report_outcome_instead_of_trusting_selected_payload(store) -> None:
    candidate, candidate_ref, evaluation_ref, replay_ref, verification_ref = _replay_inputs(store)
    report = load_replay_verification_report(store, verification_ref)
    forged_ref = _persist_report_variant(
        store,
        verification_ref,
        changes={
            "overall_similarity": 1.0 if report.overall_similarity != 1.0 else 0.0,
            "passed": not report.passed,
        },
    )
    bundle = _judge_input(
        candidate=candidate,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        replay_ref=replay_ref,
        verification_ref=forged_ref,
        report=None,
    )

    with pytest.raises(ValueError, match="recomputed"):
        JudgeStack(store=store).evaluate(
            bundle,
            active_judges={JudgeName.REPRODUCIBILITY},
        )


def test_judge_does_not_emit_replay_metric_without_current_candidate_and_evaluation_refs(
    store,
) -> None:
    candidate, candidate_ref, evaluation_ref, replay_ref, verification_ref = _replay_inputs(store)
    bundle = _judge_input(
        candidate=candidate,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        replay_ref=replay_ref,
        verification_ref=verification_ref,
        report=None,
    ).model_copy(update={"candidate_ref": None, "evaluation_ref": None})

    verdict = JudgeStack(store=store).evaluate(
        bundle,
        active_judges={JudgeName.REPRODUCIBILITY},
    )
    reproducibility = verdict.per_judge[JudgeName.REPRODUCIBILITY.value]

    assert "replay_match" not in reproducibility.metrics
    assert "replay_complete" not in reproducibility.metrics
    assert any(
        card.failure_type == "replay_verification_context_incomplete"
        for card in verdict.blocking_failures
    )


@pytest.mark.parametrize("context_role", ["candidate", "evaluation"])
def test_judge_rejects_same_id_current_context_with_foreign_profile(
    store, context_role: str
) -> None:
    candidate, candidate_ref, evaluation_ref, replay_ref, verification_ref = _replay_inputs(store)
    source_ref = candidate_ref if context_role == "candidate" else evaluation_ref
    foreign_ref = store.put_bytes(
        store.get_bytes(source_ref),
        PutOptions(
            kind=source_ref.kind,
            media_type=source_ref.media_type,
            schema=SchemaInfo(name=f"tests.Foreign{context_role.title()}", version="9.9"),
        ),
        return_selected_profile=True,
    )
    assert foreign_ref.artifact_id == source_ref.artifact_id
    assert foreign_ref.manifest_profile_sha256 != source_ref.manifest_profile_sha256
    bundle = _judge_input(
        candidate=candidate,
        candidate_ref=foreign_ref if context_role == "candidate" else candidate_ref,
        evaluation_ref=foreign_ref if context_role == "evaluation" else evaluation_ref,
        replay_ref=replay_ref,
        verification_ref=verification_ref,
        report=None,
    )

    with pytest.raises(ValueError, match=context_role):
        JudgeStack(store=store).evaluate(
            bundle,
            active_judges={JudgeName.REPRODUCIBILITY},
        )


@pytest.mark.parametrize(
    ("claim_mode", "requires_missing_blocker"),
    [("estimation", True), ("proof_only", False)],
)
def test_model_only_replay_report_cannot_supply_replay_metric(
    store,
    claim_mode: Literal["proof_only", "bounds", "estimation"],
    requires_missing_blocker: bool,
) -> None:
    candidate, candidate_ref, evaluation_ref, replay_ref, _verification_ref = _replay_inputs(store)
    bundle = _judge_input(
        candidate=candidate,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        replay_ref=replay_ref,
        verification_ref=None,
        report=_constructed_complete_report(replay_ref),
        claim_mode=claim_mode,
    )

    verdict = JudgeStack().evaluate(
        bundle,
        active_judges={JudgeName.REPRODUCIBILITY},
    )
    reproducibility = verdict.per_judge[JudgeName.REPRODUCIBILITY.value]

    assert "replay_match" not in reproducibility.metrics
    has_missing_blocker = any(
        card.failure_type == "replay_verification_missing" for card in verdict.blocking_failures
    )
    assert has_missing_blocker is requires_missing_blocker
