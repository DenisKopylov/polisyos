"""Cryptographic test evidence only; never a production evaluator or appointment."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from polisyos.core.artifacts import (
    ArtifactWriteOptions,
    FileSystemCAS,
    InputRef,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.data_forge.domains.academic.batch.claim_adjudication_verifier import (
    ClaimAdjudicationVerifier,
    ClaimEvaluatorAppointment,
)
from polisyos.ir.analytics.literature import AdmittedClaimAdjudicationBatch, ClaimAdjudicationResult
from polisyos.scientist.methods.autotune import (
    BenchmarkEvaluation,
    ChampionRegistry,
    persist_benchmark_evaluation,
    persist_mutation_artifact,
)
from polisyos.scientist.methods.autotune.claim_adjudication import (
    ClaimAdjudicationSearchConfig,
    default_claim_adjudication_promotion_policy,
)


def canonical(payload):
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def put(store, value):
    return store.put_json(
        value,
        ArtifactWriteOptions(kind="test.claim-evidence", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def signed_receipt(store, payload, key):
    signature = key.sign(b"polisyos.claim-independent-evaluation.v1\0" + canonical(payload))
    return put(store, {"payload": payload, "signature_hex": signature.hex()})


def evidence_fixture(
    store: FileSystemCAS,
    registry: ChampionRegistry,
    registry_root,
    raw_ref,
    *,
    positive: bool = True,
    declared_metric_error: bool = False,
    benchmark_gold_positive: bool = True,
    benchmark_prediction_positive: bool = True,
    candidate_note: str = "",
):
    """Create independent fixture signatures over complete benchmark and run inputs."""
    candidate_ref = persist_mutation_artifact(
        store, ClaimAdjudicationSearchConfig(passes=1, notes=[candidate_note])
    )
    prediction = ClaimAdjudicationResult(
        claim_id="benchmark-1",
        openalex_id="W-gold",
        cause_variable="cause",
        effect_variable="effect",
        paper_asserts_causality_score=0.95,
        claim_type="causal_assertion",
        design_family="rct",
        causal_credibility="strong",
        risk_of_bias="low",
        support_status="supported",
        claim_validity_score=0.95,
        adjudication_confidence=0.95,
        publishable_edge=benchmark_prediction_positive,
        adjudication_notes="candidate assessment",
    )
    corpus = {
        "suite_id": "claim_gold",
        "suite_version": "1.0",
        "cases": [
            {
                "item_id": "benchmark-1",
                "split": "holdout",
                "publish_to_graph": "yes" if benchmark_gold_positive else "no",
                "source_basis": "fulltext",
                "design_family": "rct",
            }
        ],
    }
    corpus_ref = put(store, corpus)
    observations = {
        "candidate_ref": str(candidate_ref.artifact_id),
        "cases": [
            {
                "item_id": "benchmark-1",
                "predictions": [prediction.model_dump(mode="json")],
                "costs": [0.0],
            }
        ],
    }
    observations_ref = put(store, observations)
    # Expected arithmetic is specified independently for one correct positive observation.
    empty = {
        "sample_count": 0.0,
        "precision_publishable": 0.0,
        "f1_publishable": 0.0,
        "brier_score": 1.0,
        "cost_per_correct": 0.0,
        "abstract_only_publishable_fp_rate": 0.0,
        "schema_valid_json_rate": 0.0,
        "fulltext_strong_design_recall": 0.0,
    }
    positive_metrics = {
        "sample_count": 1.0,
        "precision_publishable": 0.0
        if benchmark_prediction_positive and not benchmark_gold_positive
        else 1.0,
        "f1_publishable": 0.0
        if benchmark_prediction_positive and not benchmark_gold_positive
        else 1.0,
        "brier_score": (0.95 - float(benchmark_gold_positive)) ** 2,
        "cost_per_correct": 0.0,
        "abstract_only_publishable_fp_rate": 0.0,
        "schema_valid_json_rate": 1.0,
        "fulltext_strong_design_recall": 1.0,
    }
    policy = default_claim_adjudication_promotion_policy()
    evaluation = BenchmarkEvaluation(
        loop_id="claim_adjudication",
        suite_id="claim_gold",
        suite_version="1.0",
        candidate_ref=candidate_ref,
        selection_metrics=empty,
        holdout_metrics=positive_metrics,
        sample_counts={"selection": 0, "holdout": 1},
        guardrails=dict.fromkeys(policy.required_guardrails, True),
        promotable=True,
    )
    if declared_metric_error:
        evaluation.holdout_metrics["sample_count"] = 100.0
    evaluation_ref = persist_benchmark_evaluation(store, evaluation)
    decision = registry.consider_promotion(
        "claim_adjudication", candidate_ref, evaluation_ref, policy
    )
    assert decision.promoted
    pointer = registry.get("claim_adjudication")
    pointer_hash = hashlib.sha256(canonical(pointer.model_dump(mode="json"))).hexdigest()
    key = Ed25519PrivateKey.generate()
    base = {
        "schema_version": "claim-independent-evaluation.v1",
        "purpose": "benchmark",
        "evaluator_id": "independent-fixture-evaluator",
        "key_id": "evaluator-fixture-key",
        "producer_id": "candidate-fixture-producer",
        "candidate_ref": str(candidate_ref.artifact_id),
        "evaluation_ref": str(evaluation_ref.artifact_id),
        "benchmark_ref": str(corpus_ref.artifact_id),
        "observations_ref": str(observations_ref.artifact_id),
        "champion_pointer_sha256": pointer_hash,
        "raw_input_ref": None,
        "issued_at": "2020-01-01T00:00:00Z",
        "expires_at": "2100-01-01T00:00:00Z",
    }
    # Pydantic's JSON mode uses +00:00 for datetimes. Freeze those exact signed bytes.
    base["issued_at"] = "2020-01-01T00:00:00Z"
    base["expires_at"] = "2100-01-01T00:00:00Z"
    evaluation_receipt = signed_receipt(store, base, key)
    raw = from_canonical_bytes(store.get_bytes(raw_ref.artifact_id))
    predictions = []
    expected_results = []
    for item in raw["items"]:
        row = ClaimAdjudicationResult.model_validate(
            {
                **prediction.model_dump(),
                "claim_id": item["claim_id"],
                "openalex_id": item["openalex_id"],
                "cause_variable": item["cause_variable"],
                "effect_variable": item["effect_variable"],
                "source_basis": item["source_basis"],
                "publishable_edge": False,
                "support_status": "supported" if positive else "counterevidence",
            }
        )
        predictions.append(
            {
                "item_id": item["claim_id"],
                "predictions": [row.model_dump(mode="json")],
                "costs": [0.0],
            }
        )
        expected_results.append(
            row.model_copy(
                update={
                    "publishable_edge": positive
                    and item["source_basis"] == "fulltext"
                    and not item["intra_paper_contradiction"],
                    "claim_type_confidence": 1.0,
                    "design_family_confidence": 1.0,
                    "direction_confidence": 1.0,
                    "intra_paper_contradiction": item["intra_paper_contradiction"],
                }
            )
        )
    run_observations = {
        "candidate_ref": str(candidate_ref.artifact_id),
        "raw_input_ref": str(raw_ref.artifact_id),
        "cases": predictions,
    }
    run_observations_ref = put(store, run_observations)
    run_payload = {
        **base,
        "purpose": "execution",
        "observations_ref": str(run_observations_ref.artifact_id),
        "raw_input_ref": str(raw_ref.artifact_id),
    }
    execution_receipt = signed_receipt(store, run_payload, key)
    appointment = ClaimEvaluatorAppointment(
        evaluator_id=base["evaluator_id"],
        key_id=base["key_id"],
        public_key_hex=key.public_key().public_bytes_raw().hex(),
        producer_id=base["producer_id"],
        benchmark_refs=(str(corpus_ref.artifact_id),),
        valid_from=datetime(2019, 1, 1, tzinfo=UTC),
        valid_until=datetime(2101, 1, 1, tzinfo=UTC),
    )
    verifier = ClaimAdjudicationVerifier(
        store=store, registry_root=registry_root, appointments=(appointment,)
    )
    batch = AdmittedClaimAdjudicationBatch(
        raw_input_ref=str(raw_ref.artifact_id),
        candidate_ref=str(candidate_ref.artifact_id),
        evaluation_ref=str(evaluation_ref.artifact_id),
        champion_pointer_sha256=pointer_hash,
        input_claim_ids=[item["claim_id"] for item in raw["items"]],
        results=expected_results,
    )
    return SimpleNamespace(
        store=store,
        registry=registry,
        verifier=verifier,
        key=key,
        appointment=appointment,
        benchmark_payload=base,
        execution_payload=run_payload,
        evaluation_receipt_ref=evaluation_receipt,
        execution_receipt_ref=execution_receipt,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        raw_ref=raw_ref,
        observations=observations,
        run_observations=run_observations,
        batch=batch,
        client_payload=predictions[0]["predictions"][0],
    )


def persist_batch(fixture, batch=None):
    batch = batch or fixture.batch
    return fixture.store.put_json(
        batch,
        ArtifactWriteOptions(
            kind="scientist.claim_adjudication.admitted_batch",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.ir.analytics.literature.AdmittedClaimAdjudicationBatch",
                version="1.0",
            ),
            producer=ProducerInfo(
                component="polisyos.scientist.methods.autotune.claim_adjudication_runtime",
                version="1.0",
            ),
            inputs=[
                InputRef(artifact_id=ref.artifact_id, role=role)
                for role, ref in (
                    ("raw_input", fixture.raw_ref),
                    ("candidate", fixture.candidate_ref),
                    ("evaluation", fixture.evaluation_ref),
                    ("evaluation_receipt", fixture.evaluation_receipt_ref),
                    ("execution_receipt", fixture.execution_receipt_ref),
                )
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def tamper_pointer(registry_root, loop_id, pointer):
    """Simulate hostile local pointer bytes; ordinary claim transitions refuse this."""
    path = registry_root / loop_id / "champion.json"
    path.write_text(pointer.model_dump_json())
