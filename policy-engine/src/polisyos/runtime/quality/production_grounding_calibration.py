"""Persist and replay exact-request source discovery with an honest CG2 refusal.

This implements the source-discovery half of production calibration. Publication
adjudication does not determine a CG1 proposal/reference relation. The scientific
acceptance slot is deliberately empty until relation gold, an accepted adjudicator
and an outcome-sensitive calibration rule are supplied by their proper owners.
No number of retained rows or publication labels can populate that slot here.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from polisyos.core import artifacts
from polisyos.data_forge.read_api import academic
from polisyos.runtime.quality import grounding_bind

if TYPE_CHECKING:
    from pathlib import Path

_KIND = "runtime.production_grounding_source_resolution"
_VERSION = "1.0"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class SourceGroundingRequest(_StrictModel):
    """Exact N7 request and current runtime context, without inferred treatment."""

    requirement_ref: str = Field(min_length=1)
    claim_ref: str | None
    compiled_requirement: dict[str, JsonValue]
    design_problem: dict[str, JsonValue] | None
    world_snapshot: dict[str, JsonValue] | None


class RelationAcceptanceSlot(_StrictModel):
    """Empty scientific acceptance decision, distinct from edge publishability."""

    purpose: Literal["cg1_proposal_reference_relation"] = "cg1_proposal_reference_relation"
    status: Literal["not_established"] = "not_established"
    relation_gold_context: None = None
    accepted_relation_adjudicator: None = None
    outcome_sensitive_calibration_rule: None = None


class UnverifiedSourceGroundingRefusal(_StrictModel):
    """Current-context refusal that does not copy candidate source facts or grades."""

    purpose: Literal["unverified_source_capture_refusal"] = "unverified_source_capture_refusal"
    request: SourceGroundingRequest
    submitted_artifact_ref: str
    submitted_content_hash: str
    verification_status: Literal["not_established"] = "not_established"
    refusal_reasons: tuple[str, ...]
    n7_disposition: Literal["no_acquired_grounding"] = "no_acquired_grounding"
    n8_admission: Literal["blocked"] = "blocked"


class ProductionGroundingSourceResolution(_StrictModel):
    """Replayable source feasibility result; never a calibration authority token."""

    schema_version: Literal["policyos.runtime.production_grounding_source_resolution.v1"] = (
        "policyos.runtime.production_grounding_source_resolution.v1"
    )
    purpose: Literal["exact_request_source_discovery_and_refusal"] = (
        "exact_request_source_discovery_and_refusal"
    )
    request: SourceGroundingRequest
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_population: academic.SourceReferencePopulation | None
    target_variable: str | None
    estimand: str | None
    candidate_operator: None = None
    reference_epoch: None = None
    relation_acceptance: RelationAcceptanceSlot = Field(default_factory=RelationAcceptanceSlot)
    cg2_owner_ledger_id: str
    cg2_owner_source_id: str
    cg2_status: Literal["cold_start"] = "cold_start"
    admitted_relation_observation_count: Literal[0] = 0
    refusal_reasons: tuple[str, ...]
    n7_disposition: Literal["no_acquired_grounding"] = "no_acquired_grounding"
    n8_admission: Literal["blocked"] = "blocked"
    production_value_eligible: Literal[False] = False


def _bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _target(request: SourceGroundingRequest) -> tuple[str | None, str | None]:
    problem = request.design_problem
    outcome = problem.get("outcome_of_interest") if problem is not None else None
    if not isinstance(outcome, dict):
        return None, None
    target, estimand = outcome.get("target_variable"), outcome.get("estimand")
    return (
        target if isinstance(target, str) and target else None,
        estimand if isinstance(estimand, str) and estimand else None,
    )


class ProductionCG2CalibrationSource:
    """Produce/replay source discovery; keep the unimplemented truth mapping empty.

    The owner supplies snapshot and request separately from candidate CAS bytes.
    This does not produce the planned positive production-calibration corpus:
    its relation acceptance decision has not been established.
    """

    def __init__(
        self,
        *,
        source: academic.SourceSnapshot | None,
        store: artifacts.FileSystemCAS,
        scratch: Path,
    ) -> None:
        self._source = source
        self._store = store
        self._scratch = scratch

    def _recompute(self, request: SourceGroundingRequest) -> ProductionGroundingSourceResolution:
        request = SourceGroundingRequest.model_validate_json(request.model_dump_json())
        target, estimand = _target(request)
        reasons = [
            "relation_gold_context_not_established",
            "accepted_relation_adjudicator_not_established",
            "outcome_sensitive_calibration_rule_not_established",
            "candidate_operator_not_established",
            "reference_epoch_not_established",
        ]
        if target is None or estimand is None:
            reasons.append("exact_outcome_request_not_established")
        if request.world_snapshot is None:
            reasons.append("current_world_context_not_established")
        population = None
        if self._source is None:
            reasons.append("source_snapshot_unavailable")
        else:
            population = academic.read_source_reference_population(
                source=self._source, target_variable=target, scratch=self._scratch
            )
            reasons.extend(population.refusal_reasons)
            if population.status != "refused" and not population.literal_target_row_indices:
                reasons.append("literal_target_reference_absent_semantic_coverage_unestablished")
        # Reuse the production owner, without populating it from counts or caller labels.
        owned = grounding_bind._owned_calibration_store(
            "unknown", source="production", calibration_min_samples=20
        )
        return ProductionGroundingSourceResolution(
            request=request,
            request_sha256=hashlib.sha256(_bytes(request.model_dump(mode="json"))).hexdigest(),
            source_population=population,
            target_variable=target,
            estimand=estimand,
            cg2_owner_ledger_id=owned.ledger.ledger_id,
            cg2_owner_source_id=owned.ledger.source_id,
            refusal_reasons=tuple(reasons),
        )

    def produce(self, request: SourceGroundingRequest) -> artifacts.ArtifactRef:
        """Persist the complete current request/source projection and refusal."""
        result = self._recompute(request)
        return self._store.put_bytes(
            _bytes(result.model_dump(mode="json")),
            artifacts.ArtifactWriteOptions(
                kind=_KIND,
                media_type="application/json",
                schema=artifacts.SchemaInfo(name=_KIND, version=_VERSION),
                producer=artifacts.ProducerInfo(component=__name__, version=_VERSION),
            ),
        )

    def replay(
        self, *, ref: artifacts.ArtifactRef, request: SourceGroundingRequest
    ) -> ProductionGroundingSourceResolution:
        """Recompute source and exact request before returning any audit projection."""
        manifest = self._store.get_manifest(ref.artifact_id)
        if (
            manifest.kind != _KIND
            or manifest.artifact_schema is None
            or (manifest.artifact_schema.name, manifest.artifact_schema.version)
            != (_KIND, _VERSION)
        ):
            raise ValueError("production_grounding_source_schema_mismatch")
        persisted = ProductionGroundingSourceResolution.model_validate_json(
            self._store.get_bytes(ref.artifact_id)
        )
        current = self._recompute(request)
        if _bytes(persisted.model_dump(mode="json")) != _bytes(current.model_dump(mode="json")):
            raise ValueError("production_grounding_source_replay_mismatch")
        return current
