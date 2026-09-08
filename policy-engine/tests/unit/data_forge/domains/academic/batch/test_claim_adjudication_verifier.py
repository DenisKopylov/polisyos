"""Real signature, CAS, recomputation and consumer-boundary adjudication controls."""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.data_forge.domains.academic.batch.claim_adjudication_verifier import (
    ClaimAdjudicationVerifier,
    ClaimEvaluatorAppointment,
)
from polisyos.data_forge.domains.academic.batch.claim_adjudicator import (
    materialize_claim_adjudication_result,
)
from polisyos.scientist.methods.autotune import ChampionRegistry
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


@pytest.mark.asyncio
@pytest.mark.parametrize("positive", [True, False])
async def test_signed_observations_drive_runtime_and_direct_materialization(tmp_path, positive):
    config, f = setup_evidence(tmp_path, positive=positive)
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
        payload = {**f.benchmark_payload, "observations_ref": str(observation_ref.artifact_id)}
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
    assert first.verifier.replay_champion(str(first.evaluation_receipt_ref.artifact_id))
    successor = evidence_fixture(
        store,
        registry,
        registry_root,
        raw_ref,
        benchmark_gold_positive=False,
        benchmark_prediction_positive=False,
        candidate_note="better",
    )
    with pytest.raises(ValueError, match="observation_incumbent_binding_mismatch"):
        successor.verifier.replay_champion(str(successor.evaluation_receipt_ref.artifact_id))
    observations = {
        **successor.observations,
        "incumbent_candidate_ref": str(first.candidate_ref.artifact_id),
        "incumbent_cases": first.observations["cases"],
    }
    ref = put(store, observations)
    receipt = signed_receipt(
        store,
        {**successor.benchmark_payload, "observations_ref": str(ref.artifact_id)},
        successor.key,
    )
    assert successor.verifier.replay_champion(str(receipt.artifact_id))


def test_legacy_pointer_has_no_inferred_genesis_and_manual_replacement_is_refused(tmp_path):
    _, f = setup_evidence(tmp_path)
    basis_path = tmp_path / "registry" / "claim_adjudication" / "promotion_basis.json"
    original = basis_path.read_bytes()
    # Retain the historical bytes in this isolated fixture while making them unavailable.
    basis_path.rename(basis_path.with_suffix(".legacy"))
    with pytest.raises(ValueError, match="promotion_basis_missing"):
        f.verifier.replay_champion(str(f.evaluation_receipt_ref.artifact_id))
    from polisyos.scientist.methods.autotune.claim_adjudication import (
        default_claim_adjudication_promotion_policy,
    )

    with pytest.raises(ValueError, match="promotion_basis_missing"):
        f.registry.consider_promotion(
            "claim_adjudication",
            f.candidate_ref,
            f.evaluation_ref,
            default_claim_adjudication_promotion_policy(),
        )
    basis_path.write_bytes(original)
    pointer = f.registry.get("claim_adjudication")
    with pytest.raises(ValueError, match="manual_pointer_transition_unverified"):
        f.registry.write_pointer("claim_adjudication", pointer)
    # Ordinary lexical alias bypasses the convenience guard but cannot move the
    # independently retained basis. The verifier itself must detect that change.
    changed = pointer.model_copy(update={"metrics": {"precision_publishable": 0.2}})
    f.registry.write_pointer("claim_adjudication/.", changed)
    with pytest.raises(ValueError, match="promotion_basis_pointer_mismatch"):
        f.verifier.replay_champion(str(f.evaluation_receipt_ref.artifact_id))


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
    basis_path = tmp_path / "registry" / "claim_adjudication" / "promotion_basis.json"
    before = basis_path.read_bytes()
    original_pointer = f.registry.get("claim_adjudication")
    candidate = persist_mutation_artifact(
        f.store, ClaimAdjudicationSearchConfig(passes=1, notes=["weaker"])
    )
    payload = from_canonical_bytes(f.store.get_bytes(f.evaluation_ref.artifact_id))
    payload["candidate_ref"] = candidate.model_dump(mode="json")
    payload["holdout_metrics"]["precision_publishable"] = 0.5
    evaluation = persist_benchmark_evaluation(f.store, BenchmarkEvaluation.model_validate(payload))
    policy = default_claim_adjudication_promotion_policy()
    decision = f.registry.consider_promotion(
        "claim_adjudication",
        candidate,
        evaluation,
        policy.model_copy(update={"direction": MetricDirection.MINIMIZE}),
    )
    assert not decision.promoted
    assert f.registry.get("claim_adjudication") == original_pointer
    assert basis_path.read_bytes() == before
    assert f.verifier.replay_champion(str(f.evaluation_receipt_ref.artifact_id))
