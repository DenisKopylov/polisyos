"""Non-producing verification of appointed claim-evaluation evidence.

Deployment supplies public-key appointments. This module never signs an
observation, appoints an evaluator, or treats a candidate's labels as evidence.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts, canon
from polisyos.ir.analytics import (
    AdmittedClaimAdjudicationBatch,
    ClaimAdjudicationInputBatch,
    ClaimAdjudicationResult,
)

from .claim_adjudication_policy import (
    ClaimAdjudicationRules,
    aggregate_claim_rows,
    claim_guardrails,
    claim_metrics,
    claim_policy_publishable,
    claim_promotion_policy,
    metric_is_improved,
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class ClaimEvaluatorAppointment(_Strict):
    """Deployment-trusted public key and corpus scope; no self-appointment path."""

    evaluator_id: str = Field(min_length=1)
    key_id: str = Field(min_length=1)
    public_key_hex: str = Field(pattern=r"^[0-9a-f]{64}$")
    producer_id: str = Field(min_length=1)
    benchmark_refs: tuple[str, ...] = Field(min_length=1)
    valid_from: datetime
    valid_until: datetime

    @model_validator(mode="after")
    def _separation(self) -> ClaimEvaluatorAppointment:
        if self.evaluator_id == self.producer_id:
            raise ValueError("claim_adjudication_evaluator_is_producer")
        if (
            self.valid_from.tzinfo is None
            or self.valid_until.tzinfo is None
            or self.valid_from >= self.valid_until
        ):
            raise ValueError("claim_adjudication_appointment_interval_invalid")
        return self


class _Receipt(_Strict):
    schema_version: Literal["claim-independent-evaluation.v1"]
    purpose: Literal["benchmark", "execution"]
    evaluator_id: str
    key_id: str
    producer_id: str
    candidate_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    evaluation_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    benchmark_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    observations_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    champion_pointer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_input_ref: str | None = None
    issued_at: datetime
    expires_at: datetime


class _SignedReceipt(_Strict):
    payload: _Receipt
    signature_hex: str = Field(pattern=r"^[0-9a-f]{128}$")


class _GoldCase(_Strict):
    item_id: str = Field(min_length=1)
    split: Literal["selection", "holdout"]
    publish_to_graph: Literal["yes", "no"]
    source_basis: Literal["fulltext", "abstract_only"]
    design_family: str


class _Corpus(_Strict):
    suite_id: str
    suite_version: str
    cases: tuple[_GoldCase, ...] = Field(min_length=1)


class _PredictionCase(_Strict):
    item_id: str
    predictions: tuple[ClaimAdjudicationResult | None, ...]
    costs: tuple[float, ...]


class _BenchmarkObservations(_Strict):
    candidate_ref: str
    cases: tuple[_PredictionCase, ...]
    incumbent_candidate_ref: str | None = None
    incumbent_cases: tuple[_PredictionCase, ...] = ()


class _RunObservations(_Strict):
    raw_input_ref: str
    candidate_ref: str
    cases: tuple[_PredictionCase, ...]


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode()


def _pointer_hash(pointer: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(pointer)).hexdigest()


class _PromotionBasis(_Strict):
    schema_version: Literal["claim-promotion-basis.v1"]
    transition: Literal["genesis", "successor"]
    current_pointer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    previous_pointer: dict[str, Any] | None

    @model_validator(mode="after")
    def _explicit_predecessor(self) -> _PromotionBasis:
        if (self.transition == "genesis") != (self.previous_pointer is None):
            raise ValueError("claim_adjudication_promotion_basis_inconsistent")
        return self


def read_claim_promotion_predecessor(
    registry_root: Path,
    current_pointer: dict[str, Any],
) -> dict[str, Any] | None:
    """Resolve the registry-owned transition basis independently of evaluator claims.

    A legacy mutable pointer without this checkpoint does not establish genesis.
    The registry directory is deployment-owned state, never candidate receipt data.
    """
    path = registry_root / "claim_adjudication" / "promotion_basis.json"
    if not path.exists():
        raise ValueError("claim_adjudication_promotion_basis_missing")
    basis = _PromotionBasis.model_validate_json(path.read_bytes())
    if basis.current_pointer_sha256 != _pointer_hash(current_pointer):
        raise ValueError("claim_adjudication_promotion_basis_pointer_mismatch")
    if basis.previous_pointer is not None:
        predecessor = basis.previous_pointer
        policy = claim_promotion_policy()
        if predecessor.get("loop_id") != "claim_adjudication" or predecessor.get("metadata") != {
            "promoted_by_policy": policy,
            "compare_split": policy["compare_split"],
        }:
            raise ValueError("claim_adjudication_predecessor_policy_unverified")
    return basis.previous_pointer


class ClaimAdjudicationVerifier:
    """Resolve, authenticate and replay claim authority at both consumer intakes."""

    def __init__(
        self,
        *,
        store: artifacts.FileSystemCAS,
        registry_root: Path,
        appointments: tuple[ClaimEvaluatorAppointment, ...] = (),
    ) -> None:
        self._store = store
        self._registry_root = Path(registry_root)
        self._appointments = tuple(
            ClaimEvaluatorAppointment.model_validate(a.model_dump()) for a in appointments
        )
        identities = [(a.evaluator_id, a.key_id) for a in self._appointments]
        if len(set(identities)) != len(identities):
            raise ValueError("claim_adjudication_duplicate_evaluator_appointment")

    def _load(self, ref: str) -> object:
        return canon.from_canonical_bytes(self._store.get_bytes(artifacts.ArtifactID(ref)))

    def _authenticate(self, receipt_ref: str, *, purpose: str) -> _Receipt:
        if not self._appointments:
            raise ValueError("claim_adjudication_evaluator_appointment_missing")
        signed = _SignedReceipt.model_validate(self._load(receipt_ref))
        receipt = signed.payload
        matches = [
            a
            for a in self._appointments
            if (a.evaluator_id, a.key_id) == (receipt.evaluator_id, receipt.key_id)
        ]
        if len(matches) != 1:
            raise ValueError("claim_adjudication_evaluator_not_appointed")
        appointment = matches[0]
        if receipt.producer_id != appointment.producer_id:
            raise ValueError("claim_adjudication_receipt_producer_mismatch")
        if receipt.purpose != purpose or receipt.benchmark_ref not in appointment.benchmark_refs:
            raise ValueError("claim_adjudication_receipt_purpose_or_corpus_mismatch")
        now = datetime.now(UTC)
        if (
            receipt.issued_at.tzinfo is None
            or receipt.expires_at.tzinfo is None
            or not appointment.valid_from <= receipt.issued_at <= now < receipt.expires_at
            or receipt.expires_at > appointment.valid_until
        ):
            raise ValueError("claim_adjudication_evaluator_receipt_stale")
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(appointment.public_key_hex)).verify(
                bytes.fromhex(signed.signature_hex),
                b"polisyos.claim-independent-evaluation.v1\0"
                + _canonical(receipt.model_dump(mode="json")),
            )
        except (InvalidSignature, ValueError) as exc:
            raise ValueError("claim_adjudication_evaluator_signature_invalid") from exc
        return receipt

    def _candidate(self, ref: str) -> tuple[dict[str, Any], ClaimAdjudicationRules]:
        manifest = self._store.get_manifest(artifacts.ArtifactID(ref))
        if manifest.kind != "scientist.autotune.claim_adjudication.candidate":
            raise ValueError("claim_adjudication_candidate_kind_mismatch")
        candidate = self._load(ref)
        if not isinstance(candidate, dict) or candidate.get("loop_id") != "claim_adjudication":
            raise ValueError("claim_adjudication_candidate_loop_mismatch")
        rules = ClaimAdjudicationRules.model_validate(
            {
                k: v
                for k, v in candidate.items()
                if k
                not in {
                    "loop_id",
                    "artifact_version",
                    "search_space_version",
                    "notes",
                    "prompt_variants",
                }
            }
        )
        return candidate, rules

    @staticmethod
    def _metrics(
        corpus: _Corpus,
        cases: tuple[_PredictionCase, ...],
        rules: ClaimAdjudicationRules,
    ) -> dict[str, dict[str, float]]:
        expected = [row.item_id for row in corpus.cases]
        if len(set(expected)) != len(expected) or [row.item_id for row in cases] != expected:
            raise ValueError("claim_adjudication_observation_denominator_mismatch")
        items = []
        invalid = 0
        cost = 0.0
        for gold, observed in zip(corpus.cases, cases, strict=True):
            if len(observed.predictions) != rules.passes or len(observed.costs) != rules.passes:
                raise ValueError("claim_adjudication_observation_pass_denominator_mismatch")
            if any(value < 0 for value in observed.costs):
                raise ValueError("claim_adjudication_observation_cost_invalid")
            passes = [p for p in observed.predictions if p is not None]
            invalid += len(observed.predictions) - len(passes)
            cost += sum(observed.costs)
            if passes:
                if any(p.claim_id != gold.item_id for p in passes):
                    raise ValueError("claim_adjudication_observation_identity_mismatch")
                items.append(
                    {
                        "item_id": gold.item_id,
                        "gold": gold.model_dump(),
                        "prediction": aggregate_claim_rows(passes, rules),
                    }
                )
        return {
            split: claim_metrics(
                [
                    item
                    for item in items
                    if next(row.split for row in corpus.cases if row.item_id == item["item_id"])
                    == split
                ],
                total_cost=cost,
                invalid_count=invalid,
            )
            for split in ("selection", "holdout")
        }

    def replay_champion(self, evaluation_receipt_ref: str) -> dict[str, Any]:
        """Authenticate observations and replay metrics, policy and current champion."""
        receipt = self._authenticate(evaluation_receipt_ref, purpose="benchmark")
        if receipt.raw_input_ref is not None:
            raise ValueError("claim_adjudication_benchmark_has_execution_input")
        pointer_path = self._registry_root / "claim_adjudication" / "champion.json"
        if not pointer_path.exists():
            raise ValueError("claim_adjudication_champion_missing")
        pointer = json.loads(pointer_path.read_text())
        predecessor = read_claim_promotion_predecessor(self._registry_root, pointer)
        if _pointer_hash(pointer) != receipt.champion_pointer_sha256:
            raise ValueError("claim_adjudication_champion_replay_mismatch")
        if (
            pointer.get("loop_id") != "claim_adjudication"
            or pointer.get("candidate_ref", {}).get("artifact_id") != receipt.candidate_ref
            or pointer.get("evaluation_ref", {}).get("artifact_id") != receipt.evaluation_ref
        ):
            raise ValueError("claim_adjudication_champion_binding_mismatch")
        candidate, rules = self._candidate(receipt.candidate_ref)
        corpus = _Corpus.model_validate(self._load(receipt.benchmark_ref))
        observations = _BenchmarkObservations.model_validate(self._load(receipt.observations_ref))
        if observations.candidate_ref != receipt.candidate_ref:
            raise ValueError("claim_adjudication_observation_candidate_mismatch")
        metrics = self._metrics(corpus, observations.cases, rules)
        incumbent_metrics = None
        expected_incumbent = predecessor["candidate_ref"]["artifact_id"] if predecessor else None
        if observations.incumbent_candidate_ref != expected_incumbent:
            raise ValueError("claim_adjudication_observation_incumbent_binding_mismatch")
        if observations.incumbent_candidate_ref is not None:
            _, incumbent_rules = self._candidate(observations.incumbent_candidate_ref)
            incumbent_metrics = self._metrics(corpus, observations.incumbent_cases, incumbent_rules)
            if predecessor is None or predecessor.get("metrics") != incumbent_metrics["holdout"]:
                raise ValueError("claim_adjudication_incumbent_metric_recomputation_mismatch")
        elif observations.incumbent_cases:
            raise ValueError("claim_adjudication_incumbent_binding_missing")
        guardrails = claim_guardrails(
            metrics["holdout"],
            incumbent_metrics["holdout"]["fulltext_strong_design_recall"]
            if incumbent_metrics
            else 0.0,
        )
        evaluation = self._load(receipt.evaluation_ref)
        expected = {
            "loop_id": "claim_adjudication",
            "candidate_ref": pointer["candidate_ref"],
            "suite_id": corpus.suite_id,
            "suite_version": corpus.suite_version,
            "selection_metrics": metrics["selection"],
            "holdout_metrics": metrics["holdout"],
            "sample_counts": {k: int(v["sample_count"]) for k, v in metrics.items()},
            "guardrails": guardrails,
            "promotable": all(guardrails.values()),
        }
        if not isinstance(evaluation, dict) or any(
            evaluation.get(k) != v for k, v in expected.items()
        ):
            raise ValueError("claim_adjudication_evaluation_recomputation_mismatch")
        policy = claim_promotion_policy()
        if (
            not all(guardrails.values())
            or metrics["holdout"]["sample_count"] < policy["min_sample_count"]
        ):
            raise ValueError("claim_adjudication_recomputed_promotion_rejected")
        if incumbent_metrics is not None and not metric_is_improved(
            current=incumbent_metrics["holdout"][policy["primary_metric"]],
            new=metrics["holdout"][policy["primary_metric"]],
            direction=policy["direction"],
            min_improvement=policy["min_improvement"],
        ):
            raise ValueError("claim_adjudication_recomputed_promotion_not_improved")
        if (
            pointer.get("metrics") != metrics["holdout"]
            or pointer.get("suite_version") != corpus.suite_version
            or pointer.get("search_space_version") != candidate.get("search_space_version")
            or pointer.get("metadata")
            != {"promoted_by_policy": policy, "compare_split": policy["compare_split"]}
        ):
            raise ValueError("claim_adjudication_champion_policy_replay_mismatch")
        return pointer

    def verify_batch(
        self,
        batch: AdmittedClaimAdjudicationBatch,
        *,
        evaluation_receipt_ref: str,
        execution_receipt_ref: str,
    ) -> None:
        """Recompute the entire batch from independent run observations before emission."""
        pointer = self.replay_champion(evaluation_receipt_ref)
        benchmark = self._authenticate(evaluation_receipt_ref, purpose="benchmark")
        execution = self._authenticate(execution_receipt_ref, purpose="execution")
        if (
            any(
                getattr(execution, k) != getattr(benchmark, k)
                for k in (
                    "candidate_ref",
                    "evaluation_ref",
                    "benchmark_ref",
                    "champion_pointer_sha256",
                )
            )
            or execution.raw_input_ref != batch.raw_input_ref
        ):
            raise ValueError("claim_adjudication_execution_receipt_binding_mismatch")
        if (
            batch.candidate_ref != benchmark.candidate_ref
            or batch.evaluation_ref != benchmark.evaluation_ref
            or batch.champion_pointer_sha256 != _pointer_hash(pointer)
        ):
            raise ValueError("claim_adjudication_batch_champion_mismatch")
        raw = ClaimAdjudicationInputBatch.model_validate(self._load(batch.raw_input_ref))
        observed = _RunObservations.model_validate(self._load(execution.observations_ref))
        if (
            observed.raw_input_ref != batch.raw_input_ref
            or observed.candidate_ref != batch.candidate_ref
            or [row.item_id for row in observed.cases] != [row.claim_id for row in raw.items]
        ):
            raise ValueError("claim_adjudication_execution_denominator_mismatch")
        _, rules = self._candidate(batch.candidate_ref)
        results = []
        for item, row in zip(raw.items, observed.cases, strict=True):
            if len(row.predictions) != rules.passes or len(row.costs) != rules.passes:
                raise ValueError("claim_adjudication_execution_pass_denominator_mismatch")
            passes = []
            for prediction in row.predictions:
                if prediction is None:
                    raise ValueError("claim_adjudication_execution_observation_missing")
                if (
                    prediction.claim_id != item.claim_id
                    or prediction.openalex_id != item.openalex_id
                    or prediction.cause_variable != item.cause_variable
                    or prediction.effect_variable != item.effect_variable
                    or prediction.source_basis != item.source_basis
                ):
                    raise ValueError("claim_adjudication_execution_identity_mismatch")
                passes.append(
                    prediction.model_copy(
                        update={
                            "publishable_edge": claim_policy_publishable(item, prediction, rules),
                            "intra_paper_contradiction": item.intra_paper_contradiction,
                        }
                    )
                )
            aggregate = aggregate_claim_rows(passes, rules)
            results.append(
                aggregate.model_copy(
                    update={
                        "publishable_edge": claim_policy_publishable(item, aggregate, rules),
                        "intra_paper_contradiction": item.intra_paper_contradiction,
                    }
                )
            )
        expected = AdmittedClaimAdjudicationBatch(
            raw_input_ref=batch.raw_input_ref,
            candidate_ref=batch.candidate_ref,
            evaluation_ref=batch.evaluation_ref,
            champion_pointer_sha256=batch.champion_pointer_sha256,
            input_claim_ids=[item.claim_id for item in raw.items],
            results=results,
        )
        if batch.model_dump(mode="json") != expected.model_dump(mode="json"):
            raise ValueError("claim_adjudication_batch_observation_replay_mismatch")
