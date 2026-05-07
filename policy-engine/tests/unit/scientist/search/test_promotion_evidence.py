from __future__ import annotations

import pytest
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    persist_benchmark_evaluation,
)
from polisyos.scientist.policy_design.output import (
    ReplayableAuditBundle,
    persist_replayable_audit_bundle,
)
from polisyos.scientist.replay.verification import verify_and_persist_replay_bundle
from polisyos.scientist.methods.search.adversarial import (
    PlatformMetaEvaluationReport,
    persist_platform_meta_evaluation_report,
)
from polisyos.scientist.methods.search.calibration_report import (
    build_calibration_report,
    persist_funnel_calibration_report,
)
from polisyos.scientist.methods.search.promotion_evidence import PromotionEvidenceBundle


def _ref(seed: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(f"sha256:{seed * 64}"),
        kind="scientist.test",
        media_type="application/json",
    )


def test_promotion_evidence_bundle_requires_real_holdout_and_meta_refs() -> None:
    bundle = PromotionEvidenceBundle(
        run_id="run-a",
        produced_by_run_id="run-a",
        candidate_ref=_ref("1"),
        evaluation_ref=_ref("2"),
        selection_evaluation_ref=_ref("3"),
        replay_bundle_ref=_ref("4"),
        governance_report_ref=_ref("5"),
    )

    missing = bundle.missing_required_refs()

    assert "hidden_holdout_evaluation_ref" in missing
    assert "adversarial_meta_evaluation_ref" in missing


def test_promotion_evidence_bundle_requires_replay_and_governance_refs() -> None:
    bundle = PromotionEvidenceBundle(
        run_id="run-a",
        produced_by_run_id="run-a",
        candidate_ref=_ref("1"),
        selection_evaluation_ref=_ref("2"),
        hidden_holdout_evaluation_ref=_ref("3"),
        adversarial_meta_evaluation_ref=_ref("4"),
    )

    missing = bundle.missing_required_refs()

    assert "replay_bundle_ref" in missing
    assert "governance_report_ref" in missing


def test_promotion_evidence_bundle_must_match_current_run() -> None:
    bundle = PromotionEvidenceBundle(
        run_id="run-a",
        produced_by_run_id="run-a",
        candidate_ref=_ref("1"),
    )

    try:
        bundle.assert_compatible_with_run("run-b")
    except ValueError as exc:
        assert "current run" in str(exc)
    else:  # pragma: no cover - explicit assertion for clarity
        raise AssertionError("expected run compatibility validation to fail")


def test_promotion_evidence_bundle_validates_runtime_lineage(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    candidate_ref = store.put_json(
        {"candidate_id": "cand-1"},
        PutOptions(
            kind="scientist.policy_candidate_schema",
            media_type="application/json",
            schema=SchemaInfo(name="candidate", version="1.0"),
        ),
    )
    evaluation_ref = store.put_json(
        {"score": 1},
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            schema=SchemaInfo(name="evaluation", version="1.0"),
            inputs=[InputRef(artifact_id=candidate_ref.artifact_id, role="candidate")],
        ),
    )
    selection_ref = persist_benchmark_evaluation(
        store,
        BenchmarkEvaluation(
            loop_id="loop-a",
            suite_id="policy_selection",
            candidate_ref=candidate_ref,
            selection_metrics={"score": 0.9},
            holdout_metrics={"score": 0.9},
            sample_counts={BenchmarkSplit.SELECTION.value: 10},
            promotable=True,
            runtime_split_type=BenchmarkSplit.SELECTION,
        ),
        inputs=[InputRef(artifact_id=candidate_ref.artifact_id, role="candidate")],
    )
    hidden_ref = persist_benchmark_evaluation(
        store,
        BenchmarkEvaluation(
            loop_id="loop-a",
            suite_id="policy_hidden_holdout",
            candidate_ref=candidate_ref,
            selection_metrics={"score": 0.9},
            holdout_metrics={"score": 0.88},
            sample_counts={BenchmarkSplit.HIDDEN_HOLDOUT.value: 8},
            promotable=True,
            runtime_split_type=BenchmarkSplit.HIDDEN_HOLDOUT,
        ),
        inputs=[InputRef(artifact_id=candidate_ref.artifact_id, role="candidate")],
    )
    replay_ref = persist_replayable_audit_bundle(
        store,
        ReplayableAuditBundle(
            run_id="run-a",
            candidate_ref=candidate_ref,
            evaluation_ref=evaluation_ref,
        ),
    )
    governance_ref = store.put_json(
        {"verdict": "approve"},
        PutOptions(
            kind="scientist.governance_report",
            media_type="application/json",
            schema=SchemaInfo(name="gov", version="1.0"),
        ),
    )
    calibration_ref = persist_funnel_calibration_report(store, build_calibration_report())
    meta_ref = persist_platform_meta_evaluation_report(
        store,
        PlatformMetaEvaluationReport(
            source_refs={"selection_evaluation_ref": selection_ref},
            metadata={"run_id": "run-a"},
        ),
    )
    replay_verification_ref = verify_and_persist_replay_bundle(
        store,
        run_id="run-a",
        replay_bundle_ref=replay_ref,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
    )

    bundle = PromotionEvidenceBundle(
        run_id="run-a",
        produced_by_run_id="run-a",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        selection_evaluation_ref=selection_ref,
        hidden_holdout_evaluation_ref=hidden_ref,
        adversarial_meta_evaluation_ref=meta_ref,
        replay_bundle_ref=replay_ref,
        replay_verification_ref=replay_verification_ref,
        calibration_report_ref=calibration_ref,
        governance_report_ref=governance_ref,
    )

    bundle.assert_runtime_compatible(
        run_id="run-a",
        store=store,
        expected_loop_id="loop-a",
        expected_refs={
            "candidate_ref": candidate_ref,
            "selection_evaluation_ref": selection_ref,
            "hidden_holdout_evaluation_ref": hidden_ref,
            "replay_bundle_ref": replay_ref,
            "governance_report_ref": governance_ref,
        },
    )


def test_promotion_evidence_bundle_rejects_stale_replay_verification_ref(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    candidate_ref = store.put_json(
        {"candidate_id": "cand-1"},
        PutOptions(
            kind="scientist.policy_candidate_schema",
            media_type="application/json",
            schema=SchemaInfo(name="candidate", version="1.0"),
        ),
    )
    evaluation_ref = store.put_json(
        {"score": 1},
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            schema=SchemaInfo(name="evaluation", version="1.0"),
            inputs=[InputRef(artifact_id=candidate_ref.artifact_id, role="candidate")],
        ),
    )
    replay_ref = persist_replayable_audit_bundle(
        store,
        ReplayableAuditBundle(
            run_id="run-a",
            candidate_ref=candidate_ref,
            evaluation_ref=evaluation_ref,
        ),
    )
    stale_ref = persist_replayable_audit_bundle(
        store,
        ReplayableAuditBundle(
            run_id="run-a",
            candidate_ref=candidate_ref,
            evaluation_ref=evaluation_ref,
            trace_notes=["stale"],
        ),
    )
    replay_verification_ref = verify_and_persist_replay_bundle(
        store,
        run_id="run-a",
        replay_bundle_ref=stale_ref,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
    )
    selection_ref = persist_benchmark_evaluation(
        store,
        BenchmarkEvaluation(
            loop_id="loop-a",
            suite_id="policy_selection",
            candidate_ref=candidate_ref,
            selection_metrics={"score": 0.9},
            holdout_metrics={"score": 0.9},
            sample_counts={BenchmarkSplit.SELECTION.value: 10},
            promotable=True,
            runtime_split_type=BenchmarkSplit.SELECTION,
        ),
        inputs=[InputRef(artifact_id=candidate_ref.artifact_id, role="candidate")],
    )
    hidden_ref = persist_benchmark_evaluation(
        store,
        BenchmarkEvaluation(
            loop_id="loop-a",
            suite_id="policy_hidden",
            candidate_ref=candidate_ref,
            selection_metrics={"score": 0.9},
            holdout_metrics={"score": 0.88},
            sample_counts={BenchmarkSplit.HIDDEN_HOLDOUT.value: 8},
            promotable=True,
            runtime_split_type=BenchmarkSplit.HIDDEN_HOLDOUT,
        ),
        inputs=[InputRef(artifact_id=candidate_ref.artifact_id, role="candidate")],
    )
    meta_ref = persist_platform_meta_evaluation_report(
        store,
        PlatformMetaEvaluationReport(
            source_refs={"selection_evaluation_ref": selection_ref},
            metadata={"run_id": "run-a"},
        ),
    )
    governance_ref = store.put_json(
        {"verdict": "approve"},
        PutOptions(
            kind="scientist.governance_report",
            media_type="application/json",
            schema=SchemaInfo(name="gov", version="1.0"),
        ),
    )

    bundle = PromotionEvidenceBundle(
        run_id="run-a",
        produced_by_run_id="run-a",
        candidate_ref=candidate_ref,
        selection_evaluation_ref=selection_ref,
        hidden_holdout_evaluation_ref=hidden_ref,
        adversarial_meta_evaluation_ref=meta_ref,
        replay_bundle_ref=replay_ref,
        replay_verification_ref=replay_verification_ref,
        governance_report_ref=governance_ref,
    )

    with pytest.raises(ValueError, match="stale"):
        bundle.assert_runtime_compatible(
            run_id="run-a",
            store=store,
        )


def test_promotion_evidence_bundle_rejects_stale_selection_ref(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    candidate_ref = store.put_json(
        {"candidate_id": "cand-1"},
        PutOptions(
            kind="scientist.policy_candidate_schema",
            media_type="application/json",
            schema=SchemaInfo(name="candidate", version="1.0"),
        ),
    )
    selection_ref = persist_benchmark_evaluation(
        store,
        BenchmarkEvaluation(
            loop_id="loop-a",
            suite_id="policy_selection",
            candidate_ref=candidate_ref,
            selection_metrics={"score": 0.9},
            holdout_metrics={"score": 0.9},
            sample_counts={BenchmarkSplit.SELECTION.value: 10},
            promotable=True,
            runtime_split_type=BenchmarkSplit.SELECTION,
        ),
        inputs=[InputRef(artifact_id=candidate_ref.artifact_id, role="candidate")],
    )
    other_ref = persist_benchmark_evaluation(
        store,
        BenchmarkEvaluation(
            loop_id="loop-a",
            suite_id="policy_selection",
            candidate_ref=candidate_ref,
            selection_metrics={"score": 0.7},
            holdout_metrics={"score": 0.7},
            sample_counts={BenchmarkSplit.SELECTION.value: 10},
            promotable=False,
            runtime_split_type=BenchmarkSplit.SELECTION,
        ),
        inputs=[InputRef(artifact_id=candidate_ref.artifact_id, role="candidate")],
    )

    bundle = PromotionEvidenceBundle(
        run_id="run-a",
        produced_by_run_id="run-a",
        candidate_ref=candidate_ref,
        selection_evaluation_ref=selection_ref,
        hidden_holdout_evaluation_ref=selection_ref,
        adversarial_meta_evaluation_ref=selection_ref,
        replay_bundle_ref=selection_ref,
        governance_report_ref=selection_ref,
    )

    with pytest.raises(ValueError, match="stale"):
        bundle.assert_runtime_compatible(
            run_id="run-a",
            store=store,
            expected_loop_id="loop-a",
            expected_refs={"selection_evaluation_ref": other_ref},
        )
