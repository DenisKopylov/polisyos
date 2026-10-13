"""Real signature, CAS, recomputation and consumer-boundary adjudication controls."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from polisyos.core.artifacts import (
    FileSystemCAS,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
)
from polisyos.core.canon import from_canonical_bytes
from polisyos.data_forge.domains.academic.batch.claim_adjudication_policy import (
    claim_promotion_policy,
)
from polisyos.data_forge.domains.academic.batch.claim_adjudication_verifier import (
    ClaimAdjudicationVerifier,
    ClaimEvaluatorAppointment,
    read_claim_promotion_predecessor,
)
from polisyos.data_forge.domains.academic.batch.claim_adjudicator import (
    materialize_claim_adjudication_result,
)
from polisyos.scientist.methods.autotune import (
    BenchmarkEvaluation,
    ChampionRegistry,
    persist_benchmark_evaluation,
    persist_mutation_artifact,
)
from polisyos.scientist.methods.autotune.claim_adjudication_runtime import ClaimAdjudicationRuntime
from tests.unit.scientist.methods.autotune.test_claim_adjudication_runtime import (
    _article,
    _FakeClient,
    _input_ref,
)

from ._claim_evidence import (
    evidence_fixture,
    persist_batch,
    put,
    selected_manifest_view,
    signed_receipt,
    tamper_pointer,
)


def setup_evidence(tmp_path, *, positive=True, declared_metric_error=False):
    store = FileSystemCAS(tmp_path / "cas")
    registry_root = tmp_path / "registry"
    registry = ChampionRegistry(root=registry_root, store=store)
    config, raw_ref = _input_ref(tmp_path, store)
    return config, evidence_fixture(
        store,
        registry,
        registry_root,
        raw_ref,
        positive=positive,
        declared_metric_error=declared_metric_error,
    )


def runtime(f):
    return ClaimAdjudicationRuntime(
        store=f.store,
        registry=f.registry,
        verifier=f.verifier,
        evaluation_receipt_ref=f.evaluation_receipt_ref,
        execution_receipt_ref=f.execution_receipt_ref,
    )


def _rewrite_current_claim_state_as_legacy_sidecar(registry_root) -> None:
    pointer_path = registry_root / "claim_adjudication" / "champion.json"
    document = json.loads(pointer_path.read_text(encoding="utf-8"))
    assert document["schema_version"] == "claim-champion-envelope.v1"
    (registry_root / "claim_adjudication" / "promotion_basis.json").write_text(
        json.dumps(
            document["promotion_basis"],
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    pointer_path.write_text(
        json.dumps(
            document["pointer"],
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ),
        encoding="utf-8",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("positive", [True, False])
async def test_signed_observations_drive_runtime_and_direct_materialization(tmp_path, positive):
    config, f = setup_evidence(tmp_path, positive=positive)
    pointer = f.registry.get("claim_adjudication")
    assert pointer is not None
    assert pointer.metadata["promoted_by_policy"] == claim_promotion_policy()
    assert "unit" not in pointer.metadata["promoted_by_policy"]
    replayed_pointer = f.verifier.replay_champion(f.evaluation_receipt_ref)
    assert replayed_pointer == pointer.model_dump(mode="json")
    outcome = await runtime(f).adjudicate(
        f.raw_ref, client=_FakeClient(f.client_payload), model="fixture"
    )
    assert outcome.status == "completed", outcome
    assert outcome.published_claims == int(positive)
    result = materialize_claim_adjudication_result(
        config, outcome.result_ref, store=f.store, verifier=f.verifier
    )
    assert result == {"claims": 1, "published": int(positive)}
    assert config.claim_adjudications_path.exists()


def test_claim_transition_envelope_reopens_with_its_embedded_basis(tmp_path) -> None:
    _, f = setup_evidence(tmp_path)
    state_path = tmp_path / "registry" / "claim_adjudication" / "champion.json"
    document = json.loads(state_path.read_text(encoding="utf-8"))
    pointer = f.registry.get("claim_adjudication")
    assert pointer is not None
    assert document["schema_version"] == "claim-champion-envelope.v1"
    assert document["pointer"] == pointer.model_dump(mode="json", exclude_none=True)
    from polisyos.data_forge.domains.academic.batch.claim_adjudication_verifier import (
        _pointer_hash,
    )

    assert document["promotion_basis"]["current_pointer_sha256"] == _pointer_hash(
        document["pointer"]
    )
    fresh = ChampionRegistry(root=tmp_path / "registry", store=f.store)
    assert fresh.get("claim_adjudication") == pointer
    assert (
        read_claim_promotion_predecessor(
            tmp_path / "registry", pointer.model_dump(mode="json", exclude_none=True)
        )
        is None
    )
    assert f.verifier.replay_champion(f.evaluation_receipt_ref)


@pytest.mark.asyncio
@pytest.mark.parametrize("entry", ["scientist", "data_forge"])
@pytest.mark.parametrize(
    "corruption", ["signature", "unappointed_signer", "missing_observation", "champion", "metric"]
)
async def test_self_issued_or_incoherent_evidence_is_refused_at_both_intakes(
    tmp_path, entry, corruption
):
    config, f = setup_evidence(tmp_path, declared_metric_error=corruption == "metric")
    if corruption == "signature":
        signed = from_canonical_bytes(f.store.get_bytes(f.evaluation_receipt_ref.artifact_id))
        signed["signature_hex"] = "0" * 128
        f.evaluation_receipt_ref = put(f.store, signed)
    elif corruption == "unappointed_signer":
        f.evaluation_receipt_ref = signed_receipt(
            f.store, f.benchmark_payload, Ed25519PrivateKey.generate()
        )
    elif corruption == "missing_observation":
        observation_ref = put(f.store, {**f.observations, "cases": []})
        payload = {
            **f.benchmark_payload,
            "observations_ref": observation_ref.model_dump(mode="json"),
        }
        f.evaluation_receipt_ref = signed_receipt(f.store, payload, f.key)
    elif corruption == "champion":
        pointer = f.registry.get("claim_adjudication")
        tamper_pointer(
            tmp_path / "registry",
            "claim_adjudication",
            pointer.model_copy(update={"metrics": {"precision_publishable": 0.123}}),
        )
    if entry == "scientist":
        client = _FakeClient(f.client_payload)
        outcome = await runtime(f).adjudicate(f.raw_ref, client=client, model="fixture")
        assert outcome.status == "blocked", outcome
        assert outcome.result_ref is None
        assert client.calls == 0
    else:
        with pytest.raises(ValueError, match="claim_adjudication"):
            materialize_claim_adjudication_result(
                config, persist_batch(f), store=f.store, verifier=f.verifier
            )
        assert not config.claim_adjudications_path.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("entry", ["scientist", "data_forge"])
async def test_empty_deployment_appointment_cannot_publish(tmp_path, entry):
    config, f = setup_evidence(tmp_path)
    f.verifier = ClaimAdjudicationVerifier(store=f.store, registry_root=tmp_path / "registry")
    if entry == "scientist":
        outcome = await runtime(f).adjudicate(
            f.raw_ref, client=_FakeClient(f.client_payload), model="fixture"
        )
        assert outcome.status == "blocked"
        assert outcome.blockers == ("claim_adjudication_evaluator_appointment_missing",)
    else:
        with pytest.raises(ValueError, match="appointment_missing"):
            materialize_claim_adjudication_result(
                config, persist_batch(f), store=f.store, verifier=f.verifier
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("entry", ["scientist", "data_forge"])
async def test_valid_champion_does_not_authorize_fabricated_run_result(tmp_path, entry):
    config, f = setup_evidence(tmp_path, positive=False)
    if entry == "scientist":
        payload = {**f.client_payload, "support_status": "supported"}
        outcome = await runtime(f).adjudicate(
            f.raw_ref, client=_FakeClient(payload), model="fixture"
        )
        assert outcome.status == "blocked", outcome
        assert outcome.result_ref is None
        assert "observation_replay_mismatch" in outcome.blockers[0]
    else:
        forged = f.batch.model_copy(
            update={"results": [f.batch.results[0].model_copy(update={"publishable_edge": True})]}
        )
        with pytest.raises(ValueError, match="observation_replay_mismatch"):
            materialize_claim_adjudication_result(
                config, persist_batch(f, forged), store=f.store, verifier=f.verifier
            )
        assert not config.claim_adjudications_path.exists()


def test_appointment_cannot_name_its_producer_as_evaluator(tmp_path):
    _, f = setup_evidence(tmp_path)
    appointment = f.appointment.model_dump()
    appointment["evaluator_id"] = appointment["producer_id"]
    with pytest.raises(ValueError, match="evaluator_is_producer"):
        ClaimEvaluatorAppointment.model_validate(appointment)


def test_graph_rejects_raw_or_unminted_verified_rows_before_writing(tmp_path):
    from polisyos.data_forge.domains.academic.batch.admitted_claim_adjudications import (
        VerifiedClaimAdjudicationRows,
    )
    from polisyos.data_forge.domains.academic.batch.graph_builder import build_graph

    for forged in (
        {"claim-1": {"publishable_edge": True}},
        object.__new__(VerifiedClaimAdjudicationRows),
    ):
        with pytest.raises(ValueError, match="capability"):
            build_graph(
                records=iter(()),
                db_path=tmp_path / "graph.duckdb",
                admitted_claim_adjudications=forged,
            )
        assert not (tmp_path / "graph.duckdb").exists()


def test_verified_rows_recheck_current_champion_at_graph_use(tmp_path):
    from polisyos.data_forge.domains.academic.batch.admitted_claim_adjudications import (
        load_verified_claim_adjudication_rows,
    )
    from polisyos.data_forge.domains.academic.batch.graph_builder import build_graph

    config, f = setup_evidence(tmp_path)
    ref = persist_batch(f)
    materialize_claim_adjudication_result(config, ref, store=f.store, verifier=f.verifier)
    rows = load_verified_claim_adjudication_rows(config, verifier=f.verifier, store=f.store)
    from polisyos.data_forge.domains.academic.batch.claim_adjudicator import _input_items

    subject = _input_items([_article()], retracted_ids=set())[0].model_dump(mode="json")
    assert rows.for_current_subject(subject)["publishable_edge"] is True
    detached = {"claim-1": rows.for_current_subject(subject)}
    detached["claim-1"]["publishable_edge"] = False
    with pytest.raises(ValueError, match="capability_required"):
        build_graph(
            records=iter(()),
            db_path=tmp_path / "graph.duckdb",
            admitted_claim_adjudications=detached,
        )
    pointer = f.registry.get("claim_adjudication")
    tamper_pointer(
        tmp_path / "registry", "claim_adjudication", pointer.model_copy(update={"metrics": {}})
    )
    with pytest.raises(ValueError, match="promotion_basis_pointer_mismatch"):
        build_graph(
            records=iter(()), db_path=tmp_path / "graph.duckdb", admitted_claim_adjudications=rows
        )
    assert not (tmp_path / "graph.duckdb").exists()


def test_retained_promotion_basis_requires_actual_incumbent_observations(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    registry_root = tmp_path / "registry"
    registry = ChampionRegistry(root=registry_root, store=store)
    _, raw_ref = _input_ref(tmp_path, store)
    first = evidence_fixture(
        store,
        registry,
        registry_root,
        raw_ref,
        benchmark_gold_positive=False,
        candidate_note="first",
    )
    assert first.verifier.replay_champion(first.evaluation_receipt_ref)
    successor = evidence_fixture(
        store,
        registry,
        registry_root,
        raw_ref,
        benchmark_gold_positive=False,
        benchmark_prediction_positive=False,
        candidate_note="better",
    )
    successor_pointer = successor.registry.get("claim_adjudication")
    assert successor_pointer is not None
    predecessor = read_claim_promotion_predecessor(
        tmp_path / "registry", successor_pointer.model_dump(mode="json"), store=store
    )
    assert predecessor is not None
    assert predecessor["metadata"]["promoted_by_policy"] == claim_promotion_policy()
    assert "unit" not in predecessor["metadata"]["promoted_by_policy"]
    with pytest.raises(ValueError, match="observation_incumbent_binding_mismatch"):
        successor.verifier.replay_champion(successor.evaluation_receipt_ref)
    observations = {
        **successor.observations,
        "incumbent_candidate_ref": first.candidate_ref.model_dump(mode="json"),
        "incumbent_cases": first.observations["cases"],
    }
    ref = put(store, observations)
    receipt = signed_receipt(
        store,
        {**successor.benchmark_payload, "observations_ref": ref.model_dump(mode="json")},
        successor.key,
    )
    assert successor.verifier.replay_champion(receipt)


@pytest.mark.parametrize(
    "mutation",
    [
        "profileless_suite_history",
        "unavailable_suite_profile",
        "alternate_suite_profile",
        "suite_payload_conflict",
        "candidate_suite_edge_mismatch",
        "evaluation_candidate_mismatch",
    ],
)
def test_protected_predecessor_requires_resolved_selected_source_chain(tmp_path, mutation):
    """Protected consumers resolve every immediate predecessor source through the CAS."""
    from polisyos.scientist.methods.autotune import BenchmarkSuite, persist_benchmark_suite
    from polisyos.scientist.methods.autotune.claim_adjudication import (
        ClaimAdjudicationSearchConfig,
        default_claim_adjudication_promotion_policy,
    )

    store = FileSystemCAS(tmp_path / "cas")
    registry_root = tmp_path / "registry"
    registry = ChampionRegistry(root=registry_root, store=store)
    _, raw_ref = _input_ref(tmp_path, store)
    first = evidence_fixture(
        store,
        registry,
        registry_root,
        raw_ref,
        benchmark_gold_positive=False,
        candidate_note="predecessor-source-first",
    )
    successor = evidence_fixture(
        store,
        registry,
        registry_root,
        raw_ref,
        benchmark_gold_positive=False,
        benchmark_prediction_positive=False,
        candidate_note="predecessor-source-successor",
    )
    state_path = registry_root / "claim_adjudication" / "champion.json"
    document = json.loads(state_path.read_text(encoding="utf-8"))
    predecessor = document["promotion_basis"]["previous_pointer"]
    selected_suite = predecessor["metadata"]["suite_ref"]

    if mutation == "profileless_suite_history":
        selected_suite["manifest_profile_sha256"] = None
    elif mutation == "unavailable_suite_profile":
        selected_suite["manifest_profile_sha256"] = "sha256:" + "0" * 64
    elif mutation == "alternate_suite_profile":
        alternate = selected_manifest_view(
            store,
            first.suite_ref,
            warning_code="tests.claim_adjudication.alternate-predecessor-suite",
        )
        predecessor["metadata"]["suite_ref"] = alternate.model_dump(mode="json")
    elif mutation == "suite_payload_conflict":
        conflicting_suite = persist_benchmark_suite(
            store,
            BenchmarkSuite(
                suite_id="different_claim_suite",
                suite_version="1.0",
                kind="claim_adjudication",
            ),
            return_selected_profile=True,
        )
        predecessor["metadata"]["suite_ref"] = conflicting_suite.model_dump(mode="json")
    elif mutation == "candidate_suite_edge_mismatch":
        # Keep payload and evaluation bindings valid while changing only the
        # candidate manifest's selected benchmark-suite edge.
        alternate_suite = selected_manifest_view(
            store,
            first.suite_ref,
            warning_code="tests.claim_adjudication.alternate-predecessor-suite-edge",
        )
        candidate_payload = ClaimAdjudicationSearchConfig.model_validate(
            load_core_json_artifact(store, first.candidate_ref)
        )
        alternate_candidate_ref = persist_mutation_artifact(
            store,
            candidate_payload,
            inputs=[input_ref_from_artifact_ref(alternate_suite, role="benchmark_suite")],
            return_selected_profile=True,
        )
        assert alternate_candidate_ref is not None
        assert alternate_candidate_ref.artifact_id == first.candidate_ref.artifact_id
        assert (
            alternate_candidate_ref.manifest_profile_sha256
            != first.candidate_ref.manifest_profile_sha256
        )
        assert store.get_bytes(alternate_candidate_ref) == store.get_bytes(first.candidate_ref)

        original_evaluation = BenchmarkEvaluation.model_validate(
            load_core_json_artifact(store, first.evaluation_ref)
        )
        alternate_evaluation_payload = {
            **original_evaluation.model_dump(mode="json"),
            "candidate_ref": alternate_candidate_ref.model_dump(mode="json"),
        }
        alternate_evaluation = BenchmarkEvaluation.model_validate(alternate_evaluation_payload)
        assert alternate_evaluation.model_dump(
            mode="json", exclude={"candidate_ref"}
        ) == original_evaluation.model_dump(mode="json", exclude={"candidate_ref"})
        alternate_evaluation_ref = persist_benchmark_evaluation(
            store,
            alternate_evaluation,
            inputs=[
                input_ref_from_artifact_ref(alternate_candidate_ref, role="candidate"),
                input_ref_from_artifact_ref(first.suite_ref, role="benchmark_suite"),
            ],
            return_selected_profile=True,
        )
        assert alternate_evaluation_ref is not None
        assert alternate_evaluation.candidate_ref == alternate_candidate_ref
        assert alternate_evaluation.suite_id == predecessor["metadata"]["suite_id"]
        assert alternate_evaluation.suite_version == predecessor["suite_version"]

        candidate_manifest = store.get_manifest(alternate_candidate_ref)
        original_candidate_manifest = store.get_manifest(first.candidate_ref)
        evaluation_manifest = store.get_manifest(alternate_evaluation_ref)
        original_evaluation_manifest = store.get_manifest(first.evaluation_ref)
        assert candidate_manifest.kind == original_candidate_manifest.kind
        assert candidate_manifest.media_type == original_candidate_manifest.media_type
        assert candidate_manifest.producer == original_candidate_manifest.producer
        assert candidate_manifest.artifact_schema == original_candidate_manifest.artifact_schema
        assert evaluation_manifest.kind == original_evaluation_manifest.kind
        assert evaluation_manifest.media_type == original_evaluation_manifest.media_type
        assert evaluation_manifest.producer == original_evaluation_manifest.producer
        assert evaluation_manifest.artifact_schema == original_evaluation_manifest.artifact_schema

        alternate_suite_edge = input_ref_from_artifact_ref(alternate_suite, role="benchmark_suite")
        predecessor_suite_edge = input_ref_from_artifact_ref(
            first.suite_ref, role="benchmark_suite"
        )
        alternate_candidate_edge = input_ref_from_artifact_ref(
            alternate_candidate_ref, role="candidate"
        )
        candidate_suite_edges = [
            item for item in candidate_manifest.inputs if item.role == "benchmark_suite"
        ]
        evaluation_suite_edges = [
            item for item in evaluation_manifest.inputs if item.role == "benchmark_suite"
        ]
        evaluation_candidate_edges = [
            item for item in evaluation_manifest.inputs if item.role == "candidate"
        ]
        assert candidate_suite_edges == [alternate_suite_edge]
        assert candidate_suite_edges != [predecessor_suite_edge]
        assert evaluation_suite_edges == [predecessor_suite_edge]
        assert evaluation_candidate_edges == [alternate_candidate_edge]
        assert (
            predecessor["metadata"]["suite_ref"]["manifest_profile_sha256"]
            == first.suite_ref.manifest_profile_sha256
        )
        predecessor["candidate_ref"] = alternate_candidate_ref.model_dump(mode="json")
        predecessor["evaluation_ref"] = alternate_evaluation_ref.model_dump(mode="json")
    elif mutation == "evaluation_candidate_mismatch":
        predecessor["evaluation_ref"] = successor.evaluation_ref.model_dump(mode="json")
    else:
        raise AssertionError(f"unknown predecessor mutation: {mutation}")

    state_path.write_text(
        json.dumps(document, sort_keys=True, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    mutated_bytes = state_path.read_bytes()
    current = registry.get("claim_adjudication")
    assert current is not None
    assert (
        read_claim_promotion_predecessor(registry_root, current.model_dump(mode="json")) is not None
    )
    with pytest.raises(ValueError, match="predecessor_source_unverified") as replay_error:
        successor.verifier.replay_champion(successor.evaluation_receipt_ref)
    if mutation == "candidate_suite_edge_mismatch":
        assert isinstance(replay_error.value.__cause__, ValueError)
        assert (
            str(replay_error.value.__cause__)
            == "claim_adjudication_predecessor_manifest_lineage_mismatch"
        )
    with pytest.raises(ValueError, match="predecessor_source_unverified") as promotion_error:
        registry.consider_promotion(
            "claim_adjudication",
            successor.candidate_ref,
            successor.evaluation_ref,
            default_claim_adjudication_promotion_policy(),
            suite_ref=successor.suite_ref,
        )
    if mutation == "candidate_suite_edge_mismatch":
        assert isinstance(promotion_error.value.__cause__, ValueError)
        assert (
            str(promotion_error.value.__cause__)
            == "claim_adjudication_predecessor_manifest_lineage_mismatch"
        )
    assert state_path.read_bytes() == mutated_bytes


def test_legacy_sidecar_preserves_typed_basis_refusal(tmp_path) -> None:
    claim_dir = tmp_path / "registry" / "claim_adjudication"
    claim_dir.mkdir(parents=True)
    pointer = {"loop_id": "claim_adjudication"}
    (claim_dir / "champion.json").write_text(json.dumps(pointer), encoding="utf-8")
    (claim_dir / "promotion_basis.json").write_text(
        json.dumps(
            {
                "schema_version": "claim-promotion-basis.v1",
                "transition": "genesis",
                "current_pointer_sha256": "a" * 64,
                "previous_pointer": {"loop_id": "claim_adjudication"},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=r"^claim_adjudication_promotion_basis_inconsistent$",
    ) as exc_info:
        read_claim_promotion_predecessor(tmp_path / "registry", pointer)

    assert str(exc_info.value) == "claim_adjudication_promotion_basis_inconsistent"


def test_legacy_pointer_has_no_inferred_genesis_and_manual_replacement_is_refused(tmp_path):
    _, f = setup_evidence(tmp_path)
    _rewrite_current_claim_state_as_legacy_sidecar(tmp_path / "registry")
    basis_path = tmp_path / "registry" / "claim_adjudication" / "promotion_basis.json"
    original = basis_path.read_bytes()
    # Retain the historical bytes in this isolated fixture while making them unavailable.
    basis_path.rename(basis_path.with_suffix(".legacy"))
    with pytest.raises(ValueError, match="promotion_basis_missing"):
        f.verifier.replay_champion(f.evaluation_receipt_ref)
    from polisyos.scientist.methods.autotune.claim_adjudication import (
        default_claim_adjudication_promotion_policy,
    )

    with pytest.raises(ValueError, match="promotion_basis_missing"):
        f.registry.consider_promotion(
            "claim_adjudication",
            f.candidate_ref,
            f.evaluation_ref,
            default_claim_adjudication_promotion_policy(),
            suite_ref=f.suite_ref,
        )
    basis_path.write_bytes(original)
    assert f.verifier.replay_champion(f.evaluation_receipt_ref)
    pointer = f.registry.get("claim_adjudication")
    with pytest.raises(ValueError, match="manual_pointer_transition_unverified"):
        f.registry.write_pointer("claim_adjudication", pointer)
    # Ordinary lexical alias bypasses the convenience guard but cannot move the
    # independently retained basis. The verifier itself must detect that change.
    changed = pointer.model_copy(update={"metrics": {"precision_publishable": 0.2}})
    f.registry.write_pointer("claim_adjudication/.", changed)
    with pytest.raises(ValueError, match=r"promotion_basis_(missing|pointer_mismatch)"):
        f.verifier.replay_champion(f.evaluation_receipt_ref)


@pytest.mark.parametrize(("boundary", "expected_returncode"), [("before", 81), ("after", 82)])
def test_claim_registry_process_exit_at_atomic_replace_keeps_old_or_new_state(
    tmp_path, boundary, expected_returncode
) -> None:
    _, f = setup_evidence(tmp_path)
    original_pointer = f.registry.get("claim_adjudication")
    assert original_pointer is not None
    from polisyos.scientist.methods.autotune.claim_adjudication import ClaimAdjudicationSearchConfig

    candidate_ref = persist_mutation_artifact(
        f.store,
        ClaimAdjudicationSearchConfig(passes=1, notes=["atomic-boundary-fixture"]),
        inputs=[input_ref_from_artifact_ref(f.suite_ref, role="benchmark_suite")],
        return_selected_profile=True,
    )
    original_evaluation = BenchmarkEvaluation.model_validate(
        from_canonical_bytes(f.store.get_bytes(f.evaluation_ref.artifact_id))
    )
    holdout = dict(original_evaluation.holdout_metrics)
    holdout["precision_publishable"] = holdout.get("precision_publishable", 0.0) + 0.25
    holdout["f1_publishable"] = holdout.get("f1_publishable", 0.0) + 0.25
    evaluation_ref = persist_benchmark_evaluation(
        f.store,
        original_evaluation.model_copy(
            update={"candidate_ref": candidate_ref, "holdout_metrics": holdout}
        ),
        inputs=[
            input_ref_from_artifact_ref(candidate_ref, role="candidate"),
            input_ref_from_artifact_ref(f.suite_ref, role="benchmark_suite"),
        ],
        return_selected_profile=True,
    )
    child = textwrap.dedent(
        """
        import json
        import os
        import sys
        from pathlib import Path
        from polisyos.core.artifacts.manifest import ArtifactRef
        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.scientist.methods.autotune import ChampionRegistry
        from polisyos.scientist.methods.autotune.claim_adjudication import default_claim_adjudication_promotion_policy

        root, cas_root = Path(sys.argv[1]), Path(sys.argv[2])
        candidate = ArtifactRef.model_validate(json.loads(sys.argv[3]))
        evaluation = ArtifactRef.model_validate(json.loads(sys.argv[4]))
        suite = ArtifactRef.model_validate(json.loads(sys.argv[5]))
        boundary = sys.argv[6]
        registry = ChampionRegistry(root=root, store=FileSystemCAS(cas_root))
        pointer_path = root / "claim_adjudication" / "champion.json"
        original_replace = os.replace

        def exit_at_replace(source, destination):
            if Path(destination) == pointer_path:
                if boundary == "before":
                    os._exit(81)
                original_replace(source, destination)
                os._exit(82)
            return original_replace(source, destination)

        os.replace = exit_at_replace
        registry.consider_promotion(
            "claim_adjudication",
            candidate,
            evaluation,
            default_claim_adjudication_promotion_policy(),
            suite_ref=suite,
        )
        raise SystemExit("requested atomic replacement boundary was not reached")
        """
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            child,
            str(tmp_path / "registry"),
            str(tmp_path / "cas"),
            json.dumps(candidate_ref.model_dump(mode="json")),
            json.dumps(evaluation_ref.model_dump(mode="json")),
            json.dumps(f.suite_ref.model_dump(mode="json")),
            boundary,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == expected_returncode, completed.stderr

    fresh = ChampionRegistry(root=tmp_path / "registry", store=f.store)
    current = fresh.get("claim_adjudication")
    assert current is not None
    if boundary == "before":
        assert current == original_pointer
        assert (
            read_claim_promotion_predecessor(
                tmp_path / "registry", current.model_dump(mode="json", exclude_none=True)
            )
            is None
        )
    else:
        assert current.candidate_ref == candidate_ref
        predecessor = read_claim_promotion_predecessor(
            tmp_path / "registry", current.model_dump(mode="json", exclude_none=True)
        )
        assert predecessor == original_pointer.model_dump(mode="json", exclude_none=True)


def test_claim_transition_rejects_alternate_policy_without_changing_basis(tmp_path):
    from polisyos.scientist.methods.autotune import (
        BenchmarkEvaluation,
        persist_benchmark_evaluation,
        persist_mutation_artifact,
    )
    from polisyos.scientist.methods.autotune.claim_adjudication import (
        ClaimAdjudicationSearchConfig,
        default_claim_adjudication_promotion_policy,
    )
    from polisyos.scientist.methods.autotune.models import MetricDirection

    _, f = setup_evidence(tmp_path)
    state_path = tmp_path / "registry" / "claim_adjudication" / "champion.json"
    before = state_path.read_bytes()
    original_pointer = f.registry.get("claim_adjudication")
    candidate = persist_mutation_artifact(
        f.store,
        ClaimAdjudicationSearchConfig(passes=1, notes=["weaker"]),
        inputs=[input_ref_from_artifact_ref(f.suite_ref, role="benchmark_suite")],
        return_selected_profile=True,
    )
    payload = from_canonical_bytes(f.store.get_bytes(f.evaluation_ref.artifact_id))
    payload["candidate_ref"] = candidate.model_dump(mode="json")
    payload["holdout_metrics"]["precision_publishable"] = 0.5
    evaluation = persist_benchmark_evaluation(
        f.store,
        BenchmarkEvaluation.model_validate(payload),
        inputs=[
            input_ref_from_artifact_ref(candidate, role="candidate"),
            input_ref_from_artifact_ref(f.suite_ref, role="benchmark_suite"),
        ],
        return_selected_profile=True,
    )
    policy = default_claim_adjudication_promotion_policy()
    decision = f.registry.consider_promotion(
        "claim_adjudication",
        candidate,
        evaluation,
        policy.model_copy(update={"direction": MetricDirection.MINIMIZE}),
        suite_ref=f.suite_ref,
    )
    assert not decision.promoted
    assert f.registry.get("claim_adjudication") == original_pointer
    assert state_path.read_bytes() == before
    assert f.verifier.replay_champion(f.evaluation_receipt_ref)


def test_same_id_alternate_candidate_profile_is_refused_by_full_claim_chain(tmp_path, monkeypatch):
    """The exact selected candidate view, not its artifact ID, binds signed observations."""
    _, fixture = setup_evidence(tmp_path)
    alternate = selected_manifest_view(
        fixture.store,
        fixture.candidate_ref,
        warning_code="tests.claim_adjudication.alternate-candidate-view",
    )
    assert alternate.artifact_id == fixture.candidate_ref.artifact_id
    assert alternate.manifest_profile_sha256 != fixture.candidate_ref.manifest_profile_sha256
    assert (
        fixture.store.get_manifest(alternate).producer
        == fixture.store.get_manifest(fixture.candidate_ref).producer
    )
    payload = {**fixture.benchmark_payload, "candidate_ref": alternate.model_dump(mode="json")}
    receipt_ref = signed_receipt(fixture.store, payload, fixture.key)
    with pytest.raises(
        ValueError, match=r"champion_binding_mismatch|observation_candidate_mismatch"
    ):
        fixture.verifier.replay_champion(receipt_ref)

    # Removal probe: with the same IDs accepted regardless of profile, all the
    # surrounding signature/pointer/observation markers remain and replay turns green.
    import polisyos.data_forge.domains.academic.batch.claim_adjudication_verifier as verifier_module

    monkeypatch.setattr(
        verifier_module,
        "same_selected_artifact_ref",
        lambda left, right: left.artifact_id == right.artifact_id,
    )
    assert fixture.verifier.replay_champion(receipt_ref)


def test_profileless_v1_signed_receipt_is_retained_as_history_but_refused(tmp_path):
    _, fixture = setup_evidence(tmp_path)
    legacy = {
        **fixture.benchmark_payload,
        "schema_version": "claim-independent-evaluation.v1",
        "candidate_ref": str(fixture.candidate_ref.artifact_id),
        "evaluation_ref": str(fixture.evaluation_ref.artifact_id),
        "benchmark_ref": str(fixture.appointment.benchmark_refs[0].artifact_id),
        "observations_ref": str(put(fixture.store, fixture.observations).artifact_id),
    }
    legacy.pop("raw_input_ref", None)
    legacy_ref = signed_receipt(fixture.store, legacy, fixture.key, version="v1")
    with pytest.raises(ValueError, match="legacy_v1_receipt_profileless_refused"):
        fixture.verifier.replay_champion(legacy_ref)


def test_id_only_replay_api_fails_with_typed_selected_profile_refusal(tmp_path):
    _, fixture = setup_evidence(tmp_path)
    with pytest.raises(ValueError, match="selected_profile_required:evaluation_receipt"):
        fixture.verifier.replay_champion(str(fixture.evaluation_receipt_ref.artifact_id))


def test_same_id_alternate_suite_profile_is_refused_by_complete_chain(tmp_path):
    _, fixture = setup_evidence(tmp_path)
    alternate = selected_manifest_view(
        fixture.store,
        fixture.suite_ref,
        warning_code="tests.claim_adjudication.alternate-suite-view",
    )
    assert alternate.artifact_id == fixture.suite_ref.artifact_id
    assert alternate.manifest_profile_sha256 != fixture.suite_ref.manifest_profile_sha256
    assert (
        fixture.store.get_manifest(alternate).producer
        == fixture.store.get_manifest(fixture.suite_ref).producer
    )
    payload = {
        **fixture.benchmark_payload,
        "benchmark_suite_ref": alternate.model_dump(mode="json"),
    }
    receipt_ref = signed_receipt(fixture.store, payload, fixture.key)
    with pytest.raises(ValueError, match=r"champion_binding_mismatch|suite_lineage_mismatch"):
        fixture.verifier.replay_champion(receipt_ref)
