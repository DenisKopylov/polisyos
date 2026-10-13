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
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from polisyos.core import artifacts
from polisyos.ir.analytics import (
    AdmittedClaimAdjudicationBatch,
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


class _ClaimAdjudicationModelRefusalError(ValueError):
    """Carry a stable domain refusal code through Pydantic validation."""

    code: str

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _claim_adjudication_refusal_from_validation_error(
    exc: ValidationError,
) -> _ClaimAdjudicationModelRefusalError | None:
    """Return only a sole, explicitly typed domain refusal from Pydantic errors."""
    errors = exc.errors(include_url=False)
    if len(errors) != 1:
        return None
    context = errors[0].get("ctx")
    refusal = context.get("error") if isinstance(context, dict) else None
    return refusal if isinstance(refusal, _ClaimAdjudicationModelRefusalError) else None


class ClaimEvaluatorAppointment(_Strict):
    """Deployment-trusted public key and corpus scope; no self-appointment path."""

    evaluator_id: str = Field(min_length=1)
    key_id: str = Field(min_length=1)
    public_key_hex: str = Field(pattern=r"^[0-9a-f]{64}$")
    producer_id: str = Field(min_length=1)
    benchmark_refs: tuple[artifacts.ArtifactRef, ...] = Field(min_length=1)
    valid_from: datetime
    valid_until: datetime

    @model_validator(mode="after")
    def _separation(self) -> ClaimEvaluatorAppointment:
        if self.evaluator_id == self.producer_id:
            raise ValueError("claim_adjudication_evaluator_is_producer")
        if any(ref.manifest_profile_sha256 is None for ref in self.benchmark_refs):
            raise ValueError("claim_adjudication_appointment_benchmark_profile_missing")
        identities = {artifacts.artifact_ref_identity_key(ref) for ref in self.benchmark_refs}
        if len(identities) != len(self.benchmark_refs):
            raise ValueError("claim_adjudication_duplicate_appointment_benchmark_ref")
        if (
            self.valid_from.tzinfo is None
            or self.valid_until.tzinfo is None
            or self.valid_from >= self.valid_until
        ):
            raise ValueError("claim_adjudication_appointment_interval_invalid")
        return self


class _Receipt(_Strict):
    """Versioned evaluator statement over every selected CAS view it consumed."""

    schema_version: Literal["claim-independent-evaluation.v2"]
    purpose: Literal["benchmark", "execution"]
    evaluator_id: str
    key_id: str
    producer_id: str
    candidate_ref: artifacts.ArtifactRef
    evaluation_ref: artifacts.ArtifactRef
    benchmark_ref: artifacts.ArtifactRef
    observations_ref: artifacts.ArtifactRef
    benchmark_suite_ref: artifacts.ArtifactRef | None = None
    champion_pointer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_input_ref: artifacts.ArtifactRef | None = None
    issued_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def _selected_views(self) -> _Receipt:
        refs = [self.candidate_ref, self.evaluation_ref, self.benchmark_ref, self.observations_ref]
        if self.benchmark_suite_ref is not None:
            refs.append(self.benchmark_suite_ref)
        if self.raw_input_ref is not None:
            refs.append(self.raw_input_ref)
        if any(ref.manifest_profile_sha256 is None for ref in refs):
            raise ValueError("claim_adjudication_receipt_selected_profile_missing")
        if (self.purpose == "execution") != (self.raw_input_ref is not None):
            raise ValueError("claim_adjudication_receipt_raw_input_purpose_mismatch")
        return self


class _SignedReceipt(_Strict):
    payload: dict[str, Any]
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
    candidate_ref: artifacts.ArtifactRef
    cases: tuple[_PredictionCase, ...]
    benchmark_suite_ref: artifacts.ArtifactRef | None = None
    incumbent_candidate_ref: artifacts.ArtifactRef | None = None
    incumbent_cases: tuple[_PredictionCase, ...] = ()

    @model_validator(mode="after")
    def _selected_views(self) -> _BenchmarkObservations:
        refs = [self.candidate_ref]
        if self.benchmark_suite_ref is not None:
            refs.append(self.benchmark_suite_ref)
        if self.incumbent_candidate_ref is not None:
            refs.append(self.incumbent_candidate_ref)
        if any(ref.manifest_profile_sha256 is None for ref in refs):
            raise ValueError("claim_adjudication_observation_selected_profile_missing")
        return self


class _RunObservations(_Strict):
    raw_input_ref: artifacts.ArtifactRef
    candidate_ref: artifacts.ArtifactRef
    cases: tuple[_PredictionCase, ...]
    benchmark_suite_ref: artifacts.ArtifactRef | None = None

    @model_validator(mode="after")
    def _selected_views(self) -> _RunObservations:
        refs = [self.raw_input_ref, self.candidate_ref]
        if self.benchmark_suite_ref is not None:
            refs.append(self.benchmark_suite_ref)
        if any(ref.manifest_profile_sha256 is None for ref in refs):
            raise ValueError("claim_adjudication_observation_selected_profile_missing")
        return self


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode()


def _pointer_hash(pointer: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(pointer)).hexdigest()


def require_selected_artifact_ref(
    ref: artifacts.ArtifactRef, *, field: str
) -> artifacts.ArtifactRef:
    """Refuse an authority input whose selected manifest view is unknown."""
    if ref.manifest_profile_sha256 is None:
        raise ValueError(f"claim_adjudication_selected_profile_missing:{field}")
    return ref


def same_selected_artifact_ref(left: artifacts.ArtifactRef, right: artifacts.ArtifactRef) -> bool:
    """Compare the complete artifact identity, including its selected profile."""
    require_selected_artifact_ref(left, field="left")
    require_selected_artifact_ref(right, field="right")
    return artifacts.artifact_ref_identity_key(left) == artifacts.artifact_ref_identity_key(right)


def selected_artifact_ref_for_input(
    store: artifacts.FileSystemCAS,
    item: artifacts.InputRef,
) -> artifacts.ArtifactRef:
    """Resolve a manifest edge only by its declared selected profile."""
    profile = item.manifest_profile_sha256
    if profile is None:
        raise ValueError("claim_adjudication_lineage_profile_missing")
    manifest = store.get_manifest_by_profile(item.artifact_id, profile)
    ref = artifacts.artifact_ref_for_manifest(manifest)
    if ref.manifest_profile_sha256 != profile or ref.artifact_id != item.artifact_id:
        raise ValueError("claim_adjudication_lineage_profile_mismatch")
    return ref


def _selected_role_ref(
    store: artifacts.FileSystemCAS,
    inputs: tuple[artifacts.InputRef, ...] | list[artifacts.InputRef],
    role: str,
) -> artifacts.ArtifactRef:
    matches = [item for item in inputs if item.role == role]
    if len(matches) != 1:
        raise ValueError(f"claim_adjudication_lineage_role_invalid:{role}")
    return selected_artifact_ref_for_input(store, matches[0])


class _PromotionBasis(_Strict):
    schema_version: Literal["claim-promotion-basis.v1"]
    transition: Literal["genesis", "successor"]
    current_pointer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    previous_pointer: dict[str, Any] | None

    @model_validator(mode="after")
    def _explicit_predecessor(self) -> _PromotionBasis:
        if (self.transition == "genesis") != (self.previous_pointer is None):
            raise _ClaimAdjudicationModelRefusalError(
                "claim_adjudication_promotion_basis_inconsistent"
            )
        return self


class _ClaimChampionEnvelope(_Strict):
    schema_version: Literal["claim-champion-envelope.v1"]
    pointer: dict[str, Any]
    promotion_basis: _PromotionBasis

    @model_validator(mode="after")
    def _pointer_is_claim_transition(self) -> _ClaimChampionEnvelope:
        if self.pointer.get("loop_id") != "claim_adjudication":
            raise _ClaimAdjudicationModelRefusalError(
                "claim_adjudication_champion_envelope_pointer_invalid"
            )
        if self.promotion_basis.current_pointer_sha256 != _pointer_hash(self.pointer):
            raise _ClaimAdjudicationModelRefusalError(
                "claim_adjudication_promotion_basis_pointer_mismatch"
            )
        return self


def _validate_predecessor(
    basis: _PromotionBasis,
    *,
    store: artifacts.FileSystemCAS | None = None,
) -> dict[str, Any] | None:
    if basis.previous_pointer is None:
        return None
    predecessor = basis.previous_pointer
    policy = claim_promotion_policy()
    metadata = predecessor.get("metadata")
    expected_metadata_keys = {
        "promoted_by_policy",
        "compare_split",
        "suite_id",
        "suite_ref",
    }
    if (
        predecessor.get("loop_id") != "claim_adjudication"
        or not isinstance(metadata, dict)
        or set(metadata) != expected_metadata_keys
        or metadata.get("promoted_by_policy") != policy
        or metadata.get("compare_split") != policy["compare_split"]
        or not isinstance(metadata.get("suite_id"), str)
        or not metadata["suite_id"].strip()
    ):
        raise ValueError("claim_adjudication_predecessor_policy_unverified")
    try:
        suite_ref = artifacts.ArtifactRef.model_validate(metadata["suite_ref"])
    except (TypeError, ValueError) as exc:
        raise ValueError("claim_adjudication_predecessor_policy_unverified") from exc
    if (
        suite_ref.kind != "scientist.autotune.claim_adjudication.suite"
        or suite_ref.media_type != "application/json"
    ):
        raise ValueError("claim_adjudication_predecessor_policy_unverified")
    if store is None:
        # Registry.get is a history/diagnostic surface. It may preserve an old
        # profileless predecessor, but that value cannot enter protected use.
        return predecessor

    try:
        from polisyos.core.artifacts import load_core_json_artifact

        candidate_ref = require_selected_artifact_ref(
            artifacts.ArtifactRef.model_validate(predecessor.get("candidate_ref")),
            field="predecessor_candidate",
        )
        evaluation_ref = require_selected_artifact_ref(
            artifacts.ArtifactRef.model_validate(predecessor.get("evaluation_ref")),
            field="predecessor_evaluation",
        )
        suite_ref = require_selected_artifact_ref(suite_ref, field="predecessor_benchmark_suite")

        def selected_manifest(ref: artifacts.ArtifactRef) -> artifacts.ArtifactManifest:
            manifest = store.get_manifest_by_profile(ref.artifact_id, ref.manifest_profile_sha256)
            resolved_ref = artifacts.artifact_ref_for_manifest(manifest)
            if not same_selected_artifact_ref(resolved_ref, ref):
                raise ValueError("claim_adjudication_predecessor_selected_ref_mismatch")
            return manifest

        candidate_manifest = selected_manifest(candidate_ref)
        evaluation_manifest = selected_manifest(evaluation_ref)
        suite_manifest = selected_manifest(suite_ref)
        if (
            suite_manifest.kind != "scientist.autotune.claim_adjudication.suite"
            or suite_manifest.media_type != "application/json"
            or suite_manifest.producer is None
            or str(suite_manifest.producer.component)
            != "polisyos.scientist.methods.autotune.benchmark_suite"
            or suite_manifest.artifact_schema is None
            or suite_manifest.artifact_schema.name
            != "polisyos.scientist.methods.autotune.BenchmarkSuite"
        ):
            raise ValueError("claim_adjudication_predecessor_suite_provenance_mismatch")
        if (
            candidate_manifest.kind != "scientist.autotune.claim_adjudication.candidate"
            or candidate_manifest.media_type != "application/json"
            or candidate_manifest.producer is None
            or str(candidate_manifest.producer.component)
            != "polisyos.scientist.methods.autotune.mutation_artifact"
            or candidate_manifest.artifact_schema is None
            or not candidate_manifest.artifact_schema.name.startswith(
                "polisyos.scientist.methods.autotune."
            )
        ):
            raise ValueError("claim_adjudication_predecessor_candidate_provenance_mismatch")
        if (
            evaluation_manifest.kind != "scientist.autotune.claim_adjudication.evaluation"
            or evaluation_manifest.media_type != "application/json"
            or evaluation_manifest.producer is None
            or str(evaluation_manifest.producer.component)
            != "polisyos.scientist.methods.autotune.benchmark_evaluator"
            or evaluation_manifest.artifact_schema is None
            or evaluation_manifest.artifact_schema.name
            != "polisyos.scientist.methods.autotune.BenchmarkEvaluation"
        ):
            raise ValueError("claim_adjudication_predecessor_evaluation_provenance_mismatch")

        candidate_payload = load_core_json_artifact(store, candidate_ref)
        evaluation_payload = load_core_json_artifact(store, evaluation_ref)
        suite_payload = load_core_json_artifact(store, suite_ref)
        if (
            not isinstance(candidate_payload, dict)
            or candidate_payload.get("loop_id") != "claim_adjudication"
            or not isinstance(candidate_payload.get("artifact_version"), str)
            or candidate_manifest.artifact_schema.version
            != candidate_payload.get("artifact_version")
            or predecessor.get("search_space_version")
            != candidate_payload.get("search_space_version")
        ):
            raise ValueError("claim_adjudication_predecessor_candidate_payload_mismatch")
        reserved_candidate_fields = {
            "loop_id",
            "artifact_version",
            "search_space_version",
            "notes",
            "prompt_variants",
        }
        ClaimAdjudicationRules.model_validate(
            {
                key: value
                for key, value in candidate_payload.items()
                if key not in reserved_candidate_fields
            }
        )
        if (
            not isinstance(suite_payload, dict)
            or suite_payload.get("suite_id") != metadata["suite_id"]
            or suite_payload.get("suite_version") != predecessor.get("suite_version")
            or suite_manifest.artifact_schema.version != predecessor.get("suite_version")
        ):
            raise ValueError("claim_adjudication_predecessor_suite_payload_mismatch")
        if (
            not isinstance(evaluation_payload, dict)
            or evaluation_payload.get("loop_id") != "claim_adjudication"
            or evaluation_payload.get("suite_id") != metadata["suite_id"]
            or evaluation_payload.get("suite_version") != predecessor.get("suite_version")
            or evaluation_manifest.artifact_schema.version != predecessor.get("suite_version")
        ):
            raise ValueError("claim_adjudication_predecessor_evaluation_payload_mismatch")
        evaluation_candidate_ref = artifacts.ArtifactRef.model_validate(
            evaluation_payload.get("candidate_ref")
        )
        if not same_selected_artifact_ref(evaluation_candidate_ref, candidate_ref):
            raise ValueError("claim_adjudication_predecessor_evaluation_candidate_mismatch")
        expected_metrics = evaluation_payload.get(f"{policy['compare_split']}_metrics")
        if not isinstance(expected_metrics, dict) or predecessor.get("metrics") != expected_metrics:
            raise ValueError("claim_adjudication_predecessor_metrics_mismatch")
        candidate_suite_ref = _selected_role_ref(
            store, candidate_manifest.inputs, "benchmark_suite"
        )
        evaluation_suite_ref = _selected_role_ref(
            store, evaluation_manifest.inputs, "benchmark_suite"
        )
        evaluation_candidate_edge = _selected_role_ref(
            store, evaluation_manifest.inputs, "candidate"
        )
        if (
            not same_selected_artifact_ref(candidate_suite_ref, suite_ref)
            or not same_selected_artifact_ref(evaluation_suite_ref, suite_ref)
            or not same_selected_artifact_ref(evaluation_candidate_edge, candidate_ref)
        ):
            raise ValueError("claim_adjudication_predecessor_manifest_lineage_mismatch")
    except Exception as exc:
        raise ValueError("claim_adjudication_predecessor_source_unverified") from exc
    return predecessor


def _read_claim_champion_document(
    registry_root: Path,
) -> tuple[dict[str, Any] | None, _PromotionBasis | None]:
    path = registry_root / "claim_adjudication" / "champion.json"
    if not path.exists():
        return None, None
    document = json.loads(path.read_bytes())
    if (
        isinstance(document, dict)
        and document.get("schema_version") == "claim-champion-envelope.v1"
    ):
        try:
            envelope = _ClaimChampionEnvelope.model_validate(document)
        except ValidationError as exc:
            refusal = _claim_adjudication_refusal_from_validation_error(exc)
            if refusal is not None:
                raise refusal from exc
            raise
        return envelope.pointer, envelope.promotion_basis
    if not isinstance(document, dict):
        raise ValueError("claim_adjudication_champion_pointer_invalid")
    return document, None


def read_claim_promotion_predecessor(
    registry_root: Path,
    current_pointer: dict[str, Any],
    *,
    store: artifacts.FileSystemCAS | None = None,
) -> dict[str, Any] | None:
    """Read one predecessor as history or resolve it for protected use."""
    stored_pointer, embedded_basis = _read_claim_champion_document(registry_root)
    if embedded_basis is not None:
        if stored_pointer != current_pointer:
            raise ValueError("claim_adjudication_promotion_basis_pointer_mismatch")
        basis = embedded_basis
    else:
        path = registry_root / "claim_adjudication" / "promotion_basis.json"
        if not path.exists():
            raise ValueError("claim_adjudication_promotion_basis_missing")
        try:
            basis = _PromotionBasis.model_validate_json(path.read_bytes())
        except ValidationError as exc:
            refusal = _claim_adjudication_refusal_from_validation_error(exc)
            if refusal is not None:
                raise refusal from exc
            raise
        if basis.current_pointer_sha256 != _pointer_hash(current_pointer):
            raise ValueError("claim_adjudication_promotion_basis_pointer_mismatch")
    return _validate_predecessor(basis, store=store)


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

    def _load(self, ref: artifacts.ArtifactRef) -> object:
        from polisyos.core.artifacts import load_core_json_artifact

        require_selected_artifact_ref(ref, field="load")
        return load_core_json_artifact(self._store, ref)

    def _authenticate(self, receipt_ref: artifacts.ArtifactRef, *, purpose: str) -> _Receipt:
        require_selected_artifact_ref(receipt_ref, field="receipt")
        if not self._appointments:
            raise ValueError("claim_adjudication_evaluator_appointment_missing")
        signed = _SignedReceipt.model_validate(self._load(receipt_ref))
        if signed.payload.get("schema_version") == "claim-independent-evaluation.v1":
            raise ValueError("claim_adjudication_legacy_v1_receipt_profileless_refused")
        receipt = _Receipt.model_validate(signed.payload)
        matches = [
            appointment
            for appointment in self._appointments
            if (appointment.evaluator_id, appointment.key_id)
            == (receipt.evaluator_id, receipt.key_id)
        ]
        if len(matches) != 1:
            raise ValueError("claim_adjudication_evaluator_not_appointed")
        appointment = matches[0]
        if receipt.producer_id != appointment.producer_id:
            raise ValueError("claim_adjudication_receipt_producer_mismatch")
        if receipt.purpose != purpose or not any(
            same_selected_artifact_ref(receipt.benchmark_ref, ref)
            for ref in appointment.benchmark_refs
        ):
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
                b"polisyos.claim-independent-evaluation.v2\0"
                + _canonical(receipt.model_dump(mode="json")),
            )
        except (InvalidSignature, ValueError) as exc:
            raise ValueError("claim_adjudication_evaluator_signature_invalid") from exc
        return receipt

    def _candidate(
        self, ref: artifacts.ArtifactRef
    ) -> tuple[dict[str, Any], ClaimAdjudicationRules]:
        require_selected_artifact_ref(ref, field="candidate")
        manifest = self._store.get_manifest_by_profile(ref.artifact_id, ref.manifest_profile_sha256)
        resolved = artifacts.artifact_ref_for_manifest(manifest)
        if not same_selected_artifact_ref(resolved, ref):
            raise ValueError("claim_adjudication_candidate_profile_mismatch")
        if (
            manifest.kind != "scientist.autotune.claim_adjudication.candidate"
            or manifest.producer is None
            or str(manifest.producer.component)
            != "polisyos.scientist.methods.autotune.mutation_artifact"
        ):
            raise ValueError("claim_adjudication_candidate_provenance_mismatch")
        candidate = self._load(ref)
        if not isinstance(candidate, dict) or candidate.get("loop_id") != "claim_adjudication":
            raise ValueError("claim_adjudication_candidate_loop_mismatch")
        rules = ClaimAdjudicationRules.model_validate(
            {
                key: value
                for key, value in candidate.items()
                if key
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

    def replay_champion(
        self, evaluation_receipt_ref: artifacts.ArtifactRef | str
    ) -> dict[str, Any]:
        """Replay only a receipt bound to the exact selected suite and candidate views."""
        if not isinstance(evaluation_receipt_ref, artifacts.ArtifactRef):
            raise ValueError("claim_adjudication_selected_profile_required:evaluation_receipt")
        require_selected_artifact_ref(evaluation_receipt_ref, field="evaluation_receipt")
        receipt = self._authenticate(evaluation_receipt_ref, purpose="benchmark")
        if receipt.raw_input_ref is not None:
            raise ValueError("claim_adjudication_benchmark_has_execution_input")
        if receipt.benchmark_suite_ref is None:
            raise ValueError("claim_adjudication_selected_profile_required:benchmark_suite")
        suite_ref = require_selected_artifact_ref(
            receipt.benchmark_suite_ref, field="benchmark_suite"
        )
        pointer_path = self._registry_root / "claim_adjudication" / "champion.json"
        if not pointer_path.exists():
            raise ValueError("claim_adjudication_champion_missing")
        document = json.loads(pointer_path.read_text(encoding="utf-8"))
        if (
            isinstance(document, dict)
            and document.get("schema_version") == "claim-champion-envelope.v1"
        ):
            pointer = document.get("pointer")
        else:
            pointer = document
        if not isinstance(pointer, dict):
            raise ValueError("claim_adjudication_champion_pointer_invalid")
        predecessor = read_claim_promotion_predecessor(
            self._registry_root, pointer, store=self._store
        )
        if _pointer_hash(pointer) != receipt.champion_pointer_sha256:
            raise ValueError("claim_adjudication_champion_replay_mismatch")
        try:
            pointer_candidate = artifacts.ArtifactRef.model_validate(pointer.get("candidate_ref"))
            pointer_evaluation = artifacts.ArtifactRef.model_validate(pointer.get("evaluation_ref"))
            metadata = pointer.get("metadata")
            if not isinstance(metadata, dict):
                raise ValueError("claim_adjudication_champion_selected_ref_invalid")
            pointer_suite = artifacts.ArtifactRef.model_validate(metadata.get("suite_ref"))
        except Exception as exc:
            raise ValueError("claim_adjudication_champion_selected_ref_invalid") from exc
        require_selected_artifact_ref(pointer_candidate, field="champion_candidate")
        require_selected_artifact_ref(pointer_evaluation, field="champion_evaluation")
        require_selected_artifact_ref(pointer_suite, field="champion_benchmark_suite")
        if (
            pointer.get("loop_id") != "claim_adjudication"
            or not same_selected_artifact_ref(pointer_candidate, receipt.candidate_ref)
            or not same_selected_artifact_ref(pointer_evaluation, receipt.evaluation_ref)
            or not same_selected_artifact_ref(pointer_suite, suite_ref)
        ):
            raise ValueError("claim_adjudication_champion_binding_mismatch")

        candidate_manifest = self._store.get_manifest_by_profile(
            receipt.candidate_ref.artifact_id,
            receipt.candidate_ref.manifest_profile_sha256,
        )
        evaluation_manifest = self._store.get_manifest_by_profile(
            receipt.evaluation_ref.artifact_id,
            receipt.evaluation_ref.manifest_profile_sha256,
        )
        suite_manifest = self._store.get_manifest_by_profile(
            suite_ref.artifact_id, suite_ref.manifest_profile_sha256
        )
        if (
            suite_manifest.kind != "scientist.autotune.claim_adjudication.suite"
            or suite_manifest.media_type != "application/json"
            or suite_manifest.producer is None
            or str(suite_manifest.producer.component)
            != "polisyos.scientist.methods.autotune.benchmark_suite"
            or suite_manifest.artifact_schema is None
            or suite_manifest.artifact_schema.name
            != "polisyos.scientist.methods.autotune.BenchmarkSuite"
        ):
            raise ValueError("claim_adjudication_benchmark_suite_profile_mismatch")
        candidate_suite = _selected_role_ref(
            self._store, candidate_manifest.inputs, "benchmark_suite"
        )
        evaluation_suite = _selected_role_ref(
            self._store, evaluation_manifest.inputs, "benchmark_suite"
        )
        evaluation_candidate = _selected_role_ref(
            self._store, evaluation_manifest.inputs, "candidate"
        )
        if (
            evaluation_manifest.kind != "scientist.autotune.claim_adjudication.evaluation"
            or evaluation_manifest.producer is None
            or str(evaluation_manifest.producer.component)
            != "polisyos.scientist.methods.autotune.benchmark_evaluator"
            or evaluation_manifest.artifact_schema is None
            or evaluation_manifest.artifact_schema.name
            != "polisyos.scientist.methods.autotune.BenchmarkEvaluation"
            or evaluation_manifest.artifact_schema.version != suite_manifest.artifact_schema.version
            or not same_selected_artifact_ref(candidate_suite, suite_ref)
            or not same_selected_artifact_ref(evaluation_suite, suite_ref)
            or not same_selected_artifact_ref(evaluation_candidate, receipt.candidate_ref)
        ):
            raise ValueError("claim_adjudication_benchmark_suite_lineage_mismatch")
        if (
            not same_selected_artifact_ref(candidate_suite, suite_ref)
            or not same_selected_artifact_ref(evaluation_suite, suite_ref)
            or not same_selected_artifact_ref(evaluation_candidate, receipt.candidate_ref)
        ):
            raise ValueError("claim_adjudication_benchmark_suite_lineage_mismatch")

        candidate, rules = self._candidate(receipt.candidate_ref)
        corpus = _Corpus.model_validate(self._load(receipt.benchmark_ref))
        suite_payload = self._load(suite_ref)
        if (
            not isinstance(suite_payload, dict)
            or suite_payload.get("suite_id") != corpus.suite_id
            or suite_payload.get("suite_version") != corpus.suite_version
            or suite_manifest.artifact_schema.version != corpus.suite_version
            or metadata.get("suite_id") != corpus.suite_id
        ):
            raise ValueError("claim_adjudication_benchmark_suite_payload_mismatch")
        observations = _BenchmarkObservations.model_validate(self._load(receipt.observations_ref))
        if (
            not same_selected_artifact_ref(observations.candidate_ref, receipt.candidate_ref)
            or observations.benchmark_suite_ref is None
            or not same_selected_artifact_ref(observations.benchmark_suite_ref, suite_ref)
        ):
            raise ValueError("claim_adjudication_observation_candidate_or_suite_mismatch")
        metrics = self._metrics(corpus, observations.cases, rules)
        incumbent_metrics = None
        expected_incumbent = (
            artifacts.ArtifactRef.model_validate(predecessor["candidate_ref"])
            if predecessor is not None
            else None
        )
        if expected_incumbent is not None:
            require_selected_artifact_ref(expected_incumbent, field="predecessor_candidate")
        if (observations.incumbent_candidate_ref is None) != (expected_incumbent is None) or (
            observations.incumbent_candidate_ref is not None
            and expected_incumbent is not None
            and not same_selected_artifact_ref(
                observations.incumbent_candidate_ref, expected_incumbent
            )
        ):
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
        if not isinstance(evaluation, dict):
            raise ValueError("claim_adjudication_evaluation_recomputation_mismatch")
        try:
            evaluation_candidate_ref = artifacts.ArtifactRef.model_validate(
                evaluation.get("candidate_ref")
            )
        except Exception as exc:
            raise ValueError("claim_adjudication_evaluation_candidate_profile_missing") from exc
        if not same_selected_artifact_ref(evaluation_candidate_ref, receipt.candidate_ref):
            raise ValueError("claim_adjudication_evaluation_candidate_profile_mismatch")
        expected = {
            "loop_id": "claim_adjudication",
            "candidate_ref": pointer["candidate_ref"],
            "suite_id": corpus.suite_id,
            "suite_version": corpus.suite_version,
            "selection_metrics": metrics["selection"],
            "holdout_metrics": metrics["holdout"],
            "sample_counts": {key: int(value["sample_count"]) for key, value in metrics.items()},
            "guardrails": guardrails,
            "promotable": all(guardrails.values()),
        }
        if any(evaluation.get(key) != value for key, value in expected.items()):
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
        expected_metadata = {
            "promoted_by_policy": policy,
            "compare_split": policy["compare_split"],
            "suite_id": corpus.suite_id,
            "suite_ref": suite_ref.model_dump(mode="json"),
        }
        if (
            pointer.get("metrics") != metrics["holdout"]
            or pointer.get("suite_version") != corpus.suite_version
            or pointer.get("search_space_version") != candidate.get("search_space_version")
            or metadata != expected_metadata
        ):
            raise ValueError("claim_adjudication_champion_policy_replay_mismatch")
        return pointer

    def verify_batch(
        self,
        batch: AdmittedClaimAdjudicationBatch,
        *,
        evaluation_receipt_ref: artifacts.ArtifactRef | str,
        execution_receipt_ref: artifacts.ArtifactRef | str,
        raw_input_ref: artifacts.ArtifactRef | None = None,
        candidate_ref: artifacts.ArtifactRef | None = None,
        evaluation_ref: artifacts.ArtifactRef | None = None,
        benchmark_suite_ref: artifacts.ArtifactRef | None = None,
    ) -> None:
        """Recompute a result only from every exact selected source view."""
        required_refs = (
            ("raw_input", raw_input_ref),
            ("candidate", candidate_ref),
            ("evaluation", evaluation_ref),
            ("benchmark_suite", benchmark_suite_ref),
            ("evaluation_receipt", evaluation_receipt_ref),
            ("execution_receipt", execution_receipt_ref),
        )
        for field, ref in required_refs:
            if not isinstance(ref, artifacts.ArtifactRef):
                raise ValueError(f"claim_adjudication_selected_profile_required:{field}")
            require_selected_artifact_ref(ref, field=field)
        raw_input_ref = require_selected_artifact_ref(raw_input_ref, field="raw_input")
        candidate_ref = require_selected_artifact_ref(candidate_ref, field="candidate")
        evaluation_ref = require_selected_artifact_ref(evaluation_ref, field="evaluation")
        benchmark_suite_ref = require_selected_artifact_ref(
            benchmark_suite_ref, field="benchmark_suite"
        )
        evaluation_receipt_ref = require_selected_artifact_ref(
            evaluation_receipt_ref, field="evaluation_receipt"
        )
        execution_receipt_ref = require_selected_artifact_ref(
            execution_receipt_ref, field="execution_receipt"
        )
        pointer = self.replay_champion(evaluation_receipt_ref)
        benchmark = self._authenticate(evaluation_receipt_ref, purpose="benchmark")
        execution = self._authenticate(execution_receipt_ref, purpose="execution")
        if execution.raw_input_ref is None:
            raise ValueError("claim_adjudication_execution_raw_input_missing")
        if (
            benchmark.benchmark_suite_ref is None
            or execution.benchmark_suite_ref is None
            or not same_selected_artifact_ref(benchmark.benchmark_suite_ref, benchmark_suite_ref)
            or not same_selected_artifact_ref(execution.benchmark_suite_ref, benchmark_suite_ref)
            or any(
                not same_selected_artifact_ref(getattr(execution, key), getattr(benchmark, key))
                for key in ("candidate_ref", "evaluation_ref", "benchmark_ref")
            )
            or execution.champion_pointer_sha256 != benchmark.champion_pointer_sha256
            or not same_selected_artifact_ref(execution.raw_input_ref, raw_input_ref)
            or not same_selected_artifact_ref(benchmark.candidate_ref, candidate_ref)
            or not same_selected_artifact_ref(benchmark.evaluation_ref, evaluation_ref)
            or batch.raw_input_ref != str(raw_input_ref.artifact_id)
            or batch.candidate_ref != str(candidate_ref.artifact_id)
            or batch.evaluation_ref != str(evaluation_ref.artifact_id)
            or batch.champion_pointer_sha256 != _pointer_hash(pointer)
        ):
            raise ValueError("claim_adjudication_execution_receipt_binding_mismatch")
        from polisyos.data_forge.domains.academic.batch.claim_adjudicator import (
            _validate_input_batch,
        )

        raw = _validate_input_batch(self._store, raw_input_ref)
        observed = _RunObservations.model_validate(self._load(execution.observations_ref))
        if (
            not same_selected_artifact_ref(observed.raw_input_ref, raw_input_ref)
            or not same_selected_artifact_ref(observed.candidate_ref, candidate_ref)
            or observed.benchmark_suite_ref is None
            or not same_selected_artifact_ref(observed.benchmark_suite_ref, benchmark_suite_ref)
            or [row.item_id for row in observed.cases] != [row.claim_id for row in raw.items]
        ):
            raise ValueError("claim_adjudication_execution_denominator_or_suite_mismatch")
        _, rules = self._candidate(candidate_ref)
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
