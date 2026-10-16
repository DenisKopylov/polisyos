from __future__ import annotations

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    persist_benchmark_evaluation,
)
from polisyos.scientist.methods.search.adversarial import (
    PlatformMetaEvaluationReport,
    persist_platform_meta_evaluation_report,
)
from polisyos.scientist.methods.search.benchmark_registry import BenchmarkRegistry
from polisyos.scientist.methods.search.calibration_report import (
    build_calibration_report,
    persist_funnel_calibration_report,
)
from polisyos.scientist.methods.search.promotion_evidence import (
    PromotionEvidenceBundle,
    _PolicyRuntimeSelectionSourceBasis,
    load_promotion_evidence_bundle,
    persist_promotion_evidence_bundle,
)
from polisyos.scientist.policy_design.output import (
    ReplayableAuditBundle,
    persist_replayable_audit_bundle,
)
from polisyos.scientist.replay.verification import verify_and_persist_replay_bundle


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
        return_selected_profile=True,
    )
    evaluation_ref = store.put_json(
        {"score": 1},
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            schema=SchemaInfo(name="evaluation", version="1.0"),
            inputs=[input_ref_from_artifact_ref(candidate_ref, role="candidate")],
        ),
        return_selected_profile=True,
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
        inputs=[input_ref_from_artifact_ref(candidate_ref, role="candidate")],
        return_selected_profile=True,
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
        return_selected_profile=True,
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
            "replay_bundle_ref": replay_ref,
            "governance_report_ref": governance_ref,
        },
        source_basis_by_role={
            "selection_evaluation_ref": _PolicyRuntimeSelectionSourceBasis(
                expected_evaluation=BenchmarkEvaluation(
                    loop_id="loop-a",
                    suite_id="policy_selection",
                    candidate_ref=candidate_ref,
                    selection_metrics={"score": 0.9},
                    holdout_metrics={"score": 0.9},
                    sample_counts={BenchmarkSplit.SELECTION.value: 10},
                    promotable=True,
                    runtime_split_type=BenchmarkSplit.SELECTION,
                )
            ),
        },
    )


@pytest.mark.parametrize("edge_profile", ["missing", "foreign"])
def test_promotion_evidence_requires_exact_selected_candidate_evaluation_edge(
    tmp_path,
    edge_profile: str,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref = store.put_json(
        {"candidate_id": "selected-candidate"},
        PutOptions(
            kind="scientist.policy_candidate_schema",
            media_type="application/json",
            schema=SchemaInfo(name="candidate", version="1.0"),
        ),
        return_selected_profile=True,
    )
    if edge_profile == "foreign":
        edge_candidate_ref = store.put_bytes(
            store.get_bytes(candidate_ref),
            PutOptions(
                kind=candidate_ref.kind,
                media_type=candidate_ref.media_type,
                schema=SchemaInfo(name="tests.ForeignCandidate", version="9.9"),
            ),
            return_selected_profile=True,
        )
        assert edge_candidate_ref.artifact_id == candidate_ref.artifact_id
        assert edge_candidate_ref.manifest_profile_sha256 != candidate_ref.manifest_profile_sha256
        candidate_edge = input_ref_from_artifact_ref(
            edge_candidate_ref,
            role="candidate",
        )
    else:
        candidate_edge = InputRef(artifact_id=candidate_ref.artifact_id, role="candidate")
    evaluation_ref = store.put_json(
        {"score": 1},
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            inputs=[candidate_edge],
        ),
        return_selected_profile=True,
    )
    bundle = PromotionEvidenceBundle(
        run_id="run-selected-edge",
        produced_by_run_id="run-selected-edge",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
    )

    with pytest.raises(ValueError, match="manifest source edges are incomplete"):
        bundle.assert_runtime_compatible(run_id="run-selected-edge", store=store)


def test_promotion_evidence_does_not_promote_profileless_candidate_history(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref = store.put_json(
        {"candidate_id": "profileless-candidate"},
        PutOptions(kind="scientist.policy_candidate_schema", media_type="application/json"),
    )
    evaluation_ref = store.put_json(
        {"score": 1},
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            inputs=[InputRef(artifact_id=candidate_ref.artifact_id, role="candidate")],
        ),
    )
    assert candidate_ref.manifest_profile_sha256 is None
    assert evaluation_ref.manifest_profile_sha256 is None
    bundle = PromotionEvidenceBundle(
        run_id="run-profileless-history",
        produced_by_run_id="run-profileless-history",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
    )

    with pytest.raises(ValueError, match="candidate_ref requires a selected manifest profile"):
        bundle.assert_runtime_compatible(
            run_id="run-profileless-history",
            store=store,
        )


@pytest.mark.parametrize(
    ("field_name", "expected_role"),
    [
        ("candidate_ref", "candidate_ref"),
        ("evaluation_ref", "evaluation_ref"),
        ("selection_evaluation_ref", "selection_evaluation_ref"),
        ("hidden_holdout_evaluation_ref", "hidden_holdout_evaluation_ref"),
        ("rotating_challenge_evaluation_refs", "rotating_challenge_evaluation_refs"),
        ("adversarial_meta_evaluation_ref", "adversarial_meta_evaluation_ref"),
        ("replay_bundle_ref", "replay_bundle_ref"),
        ("replay_verification_ref", "replay_verification_ref"),
        ("calibration_report_ref", "calibration_report_ref"),
        ("governance_report_ref", "governance_report_ref"),
        ("stress_test_report_ref", "stress_test_report_ref"),
    ],
)
def test_promotion_evidence_requires_selected_profile_for_each_admitted_ref(
    tmp_path,
    field_name: str,
    expected_role: str,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    selected_candidate_ref = store.put_json(
        {"candidate_id": "selected-candidate"},
        PutOptions(
            kind="scientist.policy_candidate_schema",
            media_type="application/json",
            schema=SchemaInfo(name="candidate", version="1.0"),
        ),
        return_selected_profile=True,
    )
    profileless_ref = store.put_json(
        {"candidate_id": "profileless-evidence"},
        PutOptions(kind="tests.profileless_evidence", media_type="application/json"),
    )
    assert profileless_ref.manifest_profile_sha256 is None

    ref_value = (
        [profileless_ref] if field_name == "rotating_challenge_evaluation_refs" else profileless_ref
    )
    bundle_values = {
        "run_id": "run-selected-profile-required",
        "produced_by_run_id": "run-selected-profile-required",
        "candidate_ref": selected_candidate_ref,
    }
    if field_name != "candidate_ref":
        bundle_values[field_name] = ref_value
    else:
        bundle_values["candidate_ref"] = profileless_ref
    bundle = PromotionEvidenceBundle(**bundle_values)

    with pytest.raises(
        ValueError,
        match=f"{expected_role} requires a selected manifest profile",
    ):
        bundle.assert_runtime_compatible(
            run_id="run-selected-profile-required",
            store=store,
        )


@pytest.mark.parametrize("context_role", ["candidate", "evaluation"])
def test_promotion_evidence_rejects_report_edges_with_foreign_selected_context(
    tmp_path,
    context_role: str,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref = store.put_json(
        {"candidate_id": "candidate-context"},
        PutOptions(kind="scientist.policy_candidate_schema", media_type="application/json"),
        return_selected_profile=True,
    )
    evaluation_ref = store.put_json(
        {"score": 0.7},
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            inputs=[input_ref_from_artifact_ref(candidate_ref, role="candidate")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    replay_ref = persist_replayable_audit_bundle(
        store,
        ReplayableAuditBundle(
            run_id="run-context-edges",
            candidate_ref=candidate_ref,
            evaluation_ref=evaluation_ref,
        ),
    )
    verification_ref = verify_and_persist_replay_bundle(
        store,
        run_id="run-context-edges",
        replay_bundle_ref=replay_ref,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
    )
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
    from polisyos.scientist.replay.verification import load_replay_verification_report

    source_report = load_replay_verification_report(store, verification_ref)
    source_inputs = list(store.get_manifest(verification_ref).inputs)
    foreign_edge = input_ref_from_artifact_ref(foreign_ref, role=context_role)
    foreign_inputs = [foreign_edge if item.role == context_role else item for item in source_inputs]
    forged_report_ref = store.put_json(
        source_report,
        PutOptions(
            kind="scientist.replay_verification_report",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.replay.ReplayVerificationReport",
                version="1.0",
            ),
            inputs=foreign_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    bundle = PromotionEvidenceBundle(
        run_id="run-context-edges",
        produced_by_run_id="run-context-edges",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        replay_bundle_ref=replay_ref,
        replay_verification_ref=forged_report_ref,
    )

    with pytest.raises(ValueError, match=context_role):
        bundle.assert_runtime_compatible(run_id="run-context-edges", store=store)


def test_promotion_evidence_requires_nested_bundle_candidate_and_evaluation_context(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref = store.put_json(
        {"candidate_id": "current-candidate"},
        PutOptions(kind="scientist.policy_candidate_schema", media_type="application/json"),
        return_selected_profile=True,
    )
    evaluation_ref = store.put_json(
        {"score": 1},
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            inputs=[input_ref_from_artifact_ref(candidate_ref, role="candidate")],
        ),
        return_selected_profile=True,
    )
    replay_ref = persist_replayable_audit_bundle(
        store,
        ReplayableAuditBundle(run_id="run-missing-nested-context"),
    )
    verification_ref = verify_and_persist_replay_bundle(
        store,
        run_id="run-missing-nested-context",
        replay_bundle_ref=replay_ref,
    )
    bundle = PromotionEvidenceBundle(
        run_id="run-missing-nested-context",
        produced_by_run_id="run-missing-nested-context",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        replay_bundle_ref=replay_ref,
        replay_verification_ref=verification_ref,
    )

    with pytest.raises(ValueError, match="subject_context_missing"):
        bundle.assert_runtime_compatible(run_id="run-missing-nested-context", store=store)


def test_promotion_evidence_rejects_duplicate_candidate_context_edge(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref = store.put_json(
        {"candidate_id": "duplicate-context"},
        PutOptions(kind="scientist.policy_candidate_schema", media_type="application/json"),
        return_selected_profile=True,
    )
    evaluation_ref = store.put_json(
        {"score": 1},
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            inputs=[input_ref_from_artifact_ref(candidate_ref, role="candidate")],
        ),
        return_selected_profile=True,
    )
    replay_ref = persist_replayable_audit_bundle(
        store,
        ReplayableAuditBundle(
            run_id="run-duplicate-context",
            candidate_ref=candidate_ref,
            evaluation_ref=evaluation_ref,
        ),
    )
    verification_ref = verify_and_persist_replay_bundle(
        store,
        run_id="run-duplicate-context",
        replay_bundle_ref=replay_ref,
    )
    from polisyos.scientist.replay.verification import load_replay_verification_report

    source_report = load_replay_verification_report(store, verification_ref)
    source_inputs = list(store.get_manifest(verification_ref).inputs)
    duplicate_candidate_edge = input_ref_from_artifact_ref(candidate_ref, role="candidate")
    forged_report_ref = store.put_json(
        source_report,
        PutOptions(
            kind="scientist.replay_verification_report",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.replay.ReplayVerificationReport",
                version="1.0",
            ),
            inputs=[*source_inputs, duplicate_candidate_edge],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    bundle = PromotionEvidenceBundle(
        run_id="run-duplicate-context",
        produced_by_run_id="run-duplicate-context",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        replay_bundle_ref=replay_ref,
        replay_verification_ref=forged_report_ref,
    )

    with pytest.raises(ValueError, match="candidate.*input|context.*input"):
        bundle.assert_runtime_compatible(run_id="run-duplicate-context", store=store)


def test_promotion_evidence_binds_replay_report_to_exact_run_context(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    candidate_ref = store.put_json(
        {"candidate_id": "cand-context"},
        PutOptions(kind="scientist.policy_candidate_schema", media_type="application/json"),
        return_selected_profile=True,
    )
    evaluation_ref = store.put_json(
        {"score": 1},
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            inputs=[input_ref_from_artifact_ref(candidate_ref, role="candidate")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    replay_ref = persist_replayable_audit_bundle(
        store,
        ReplayableAuditBundle(
            run_id="run-current",
            candidate_ref=candidate_ref,
            evaluation_ref=evaluation_ref,
        ),
    )
    foreign_replay_ref = persist_replayable_audit_bundle(
        store,
        ReplayableAuditBundle(
            run_id="run-foreign",
            candidate_ref=candidate_ref,
            evaluation_ref=evaluation_ref,
        ),
    )
    foreign_report_ref = verify_and_persist_replay_bundle(
        store,
        run_id="run-foreign",
        replay_bundle_ref=foreign_replay_ref,
    )
    bundle = PromotionEvidenceBundle(
        run_id="run-current",
        produced_by_run_id="run-current",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        replay_bundle_ref=replay_ref,
        replay_verification_ref=foreign_report_ref,
    )

    with pytest.raises(ValueError, match="run"):
        bundle.assert_runtime_compatible(run_id="run-current", store=store)

    missing_context = bundle.model_copy(update={"replay_bundle_ref": None})
    with pytest.raises(ValueError, match="context"):
        missing_context.assert_runtime_compatible(run_id="run-current", store=store)


def test_promotion_evidence_writer_selects_and_binds_subject_profiles(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref = store.put_json(
        {"candidate_id": "selected-pbe-candidate"},
        PutOptions(kind="scientist.policy_candidate_schema", media_type="application/json"),
        return_selected_profile=True,
    )
    evaluation_ref = store.put_json(
        {"score": 0.8},
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            inputs=[input_ref_from_artifact_ref(candidate_ref, role="candidate")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    bundle = PromotionEvidenceBundle(
        run_id="run-selected-pbe",
        produced_by_run_id="run-selected-pbe",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
    )

    ref = persist_promotion_evidence_bundle(store, bundle)

    assert ref.manifest_profile_sha256 is not None
    manifest = store.get_manifest(ref)
    by_role = {item.role: item for item in manifest.inputs}
    assert by_role["candidate"] == input_ref_from_artifact_ref(candidate_ref, role="candidate")
    assert by_role["evaluation"] == input_ref_from_artifact_ref(evaluation_ref, role="evaluation")
    assert load_promotion_evidence_bundle(store, ref) == bundle


def test_promotion_evidence_writer_rejects_subject_profile_conflict(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref = store.put_json(
        {"candidate_id": "selected-pbe-candidate"},
        PutOptions(kind="scientist.policy_candidate_schema", media_type="application/json"),
        return_selected_profile=True,
    )
    foreign_candidate_ref = store.put_bytes(
        store.get_bytes(candidate_ref),
        PutOptions(
            kind=candidate_ref.kind,
            media_type=candidate_ref.media_type,
            schema=SchemaInfo(name="tests.ForeignPbeCandidate", version="9.9"),
        ),
        return_selected_profile=True,
    )
    assert foreign_candidate_ref.artifact_id == candidate_ref.artifact_id
    assert foreign_candidate_ref.manifest_profile_sha256 != candidate_ref.manifest_profile_sha256
    bundle = PromotionEvidenceBundle(
        run_id="run-selected-pbe-conflict",
        produced_by_run_id="run-selected-pbe-conflict",
        candidate_ref=candidate_ref,
    )

    with pytest.raises(ValueError, match="candidate.*profile|candidate.*input"):
        persist_promotion_evidence_bundle(
            store,
            bundle,
            inputs=[input_ref_from_artifact_ref(foreign_candidate_ref, role="candidate")],
        )


def test_protected_promotion_requires_a_trusted_benchmark_source_basis(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    candidate_ref = store.put_json(
        {"candidate_id": "cand-1"},
        PutOptions(
            kind="scientist.policy_candidate_schema",
            media_type="application/json",
            schema=SchemaInfo(name="candidate", version="1.0"),
        ),
        return_selected_profile=True,
    )
    selection_ref = persist_benchmark_evaluation(
        store,
        BenchmarkEvaluation(
            loop_id="loop-a",
            suite_id="policy_selection",
            candidate_ref=candidate_ref,
            selection_metrics={"score": 0.9},
            holdout_metrics={"score": 0.9},
            sample_counts={BenchmarkSplit.SELECTION.value: 100},
            promotable=True,
            runtime_split_type=BenchmarkSplit.SELECTION,
        ),
        inputs=[input_ref_from_artifact_ref(candidate_ref, role="candidate")],
        return_selected_profile=True,
    )
    bundle = PromotionEvidenceBundle(
        run_id="run-a",
        produced_by_run_id="run-a",
        candidate_ref=candidate_ref,
        selection_evaluation_ref=selection_ref,
    )

    with pytest.raises(ValueError, match="source basis"):
        bundle.assert_runtime_compatible(
            run_id="run-a",
            store=store,
            expected_loop_id="loop-a",
        )


def test_registry_backed_hidden_holdout_without_source_basis_is_refused(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    candidate_ref = store.put_json(
        {"candidate_id": "cand-1"},
        PutOptions(
            kind="scientist.policy_candidate_schema",
            media_type="application/json",
            schema=SchemaInfo(name="candidate", version="1.0"),
        ),
        return_selected_profile=True,
    )
    selection = BenchmarkEvaluation(
        loop_id="loop-a",
        suite_id="policy_selection",
        candidate_ref=candidate_ref,
        selection_metrics={"score": 0.9},
        holdout_metrics={"score": 0.9},
        sample_counts={BenchmarkSplit.SELECTION.value: 10},
        promotable=True,
        runtime_split_type=BenchmarkSplit.SELECTION,
    )
    selection_ref = persist_benchmark_evaluation(
        store,
        selection,
        inputs=[input_ref_from_artifact_ref(candidate_ref, role="candidate")],
        return_selected_profile=True,
    )
    hidden_evaluation = BenchmarkEvaluation(
        loop_id="loop-a",
        suite_id="policy_hidden_holdout",
        candidate_ref=candidate_ref,
        selection_metrics={"score": 0.9},
        holdout_metrics={"score": 0.88},
        sample_counts={BenchmarkSplit.HIDDEN_HOLDOUT.value: 8},
        promotable=True,
        runtime_split_type=BenchmarkSplit.HIDDEN_HOLDOUT,
    )
    hidden_ref = persist_benchmark_evaluation(
        store,
        hidden_evaluation,
        inputs=[input_ref_from_artifact_ref(candidate_ref, role="candidate")],
        return_selected_profile=True,
    )
    registry = BenchmarkRegistry(tmp_path / "search_registry" / "benchmarks")
    registry.record_evaluation(hidden_evaluation, hidden_ref, run_id="run-a")
    assert registry.get(
        BenchmarkSplit.HIDDEN_HOLDOUT.value,
        run_id="run-a",
        loop_id="loop-a",
    ) == [hidden_ref]
    bundle = PromotionEvidenceBundle(
        run_id="run-a",
        produced_by_run_id="run-a",
        candidate_ref=candidate_ref,
        selection_evaluation_ref=selection_ref,
        hidden_holdout_evaluation_ref=hidden_ref,
    )

    with pytest.raises(ValueError, match="hidden_holdout_evaluation_ref source basis is required"):
        bundle.assert_runtime_compatible(
            run_id="run-a",
            store=store,
            expected_loop_id="loop-a",
            source_basis_by_role={
                "selection_evaluation_ref": _PolicyRuntimeSelectionSourceBasis(
                    expected_evaluation=selection
                )
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
        return_selected_profile=True,
    )
    evaluation_ref = store.put_json(
        {"score": 1},
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            schema=SchemaInfo(name="evaluation", version="1.0"),
            inputs=[input_ref_from_artifact_ref(candidate_ref, role="candidate")],
        ),
        return_selected_profile=True,
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
        inputs=[input_ref_from_artifact_ref(candidate_ref, role="candidate")],
        return_selected_profile=True,
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
        return_selected_profile=True,
    )

    bundle = PromotionEvidenceBundle(
        run_id="run-a",
        produced_by_run_id="run-a",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        selection_evaluation_ref=selection_ref,
        adversarial_meta_evaluation_ref=meta_ref,
        replay_bundle_ref=replay_ref,
        replay_verification_ref=replay_verification_ref,
        governance_report_ref=governance_ref,
    )

    with pytest.raises(ValueError, match="stale"):
        bundle.assert_runtime_compatible(
            run_id="run-a",
            store=store,
            expected_loop_id="loop-a",
            source_basis_by_role={
                "selection_evaluation_ref": _PolicyRuntimeSelectionSourceBasis(
                    expected_evaluation=BenchmarkEvaluation(
                        loop_id="loop-a",
                        suite_id="policy_selection",
                        candidate_ref=candidate_ref,
                        selection_metrics={"score": 0.9},
                        holdout_metrics={"score": 0.9},
                        sample_counts={BenchmarkSplit.SELECTION.value: 10},
                        promotable=True,
                        runtime_split_type=BenchmarkSplit.SELECTION,
                    )
                ),
            },
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
        return_selected_profile=True,
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
        inputs=[input_ref_from_artifact_ref(candidate_ref, role="candidate")],
        return_selected_profile=True,
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
        inputs=[input_ref_from_artifact_ref(candidate_ref, role="candidate")],
        return_selected_profile=True,
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
