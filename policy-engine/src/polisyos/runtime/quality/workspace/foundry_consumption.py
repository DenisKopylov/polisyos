"""Foundry method-output consumption and Phase-2 constraint ingestion."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.pdc import (
    ArtifactRef,
    AuthorityBoundary,
    ConstraintStoreEntry,
    ConstraintStoreSnapshot,
    EvidenceBasis,
    MethodOutputConsumptionRecord,
    OperationClass,
)

FOUNDRY_CONSUMPTION_RULE_VERSION = "policyos.gy.phase2.foundry.v1"
ARTIFACT_CAUSAL_METHOD_RESULT_REF = "causal_method_result_ref"
ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF = "causal_method_evidence_ref"
_ALLOWED_CONSTRAINT_SOURCES = frozenset(
    {"obligation", "participation_requirement", "method_requirement"}
)


class FoundryConsumptionResult(BaseModel):
    """Bridge output proving GY consumed a real Foundry method artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    record: MethodOutputConsumptionRecord
    authority_boundary: AuthorityBoundary
    input_provenance: Literal["measurement_rooted", "synthetic_probe"]
    open_production_findings: list[str] = Field(default_factory=list)


class ConstraintStoreDecision(BaseModel):
    """Phase-2 consumer decision derived from a ConstraintStoreSnapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    blocks_promotion: bool
    downgrades_authority: bool
    blocking_constraint_ids: list[str]
    limiting_constraint_ids: list[str]
    warning_constraint_ids: list[str]


class FoundryMethodOutputConsumer:
    """Consume Foundry method outputs from Scientist state into GY authority facts."""

    def consume_from_state(
        self,
        *,
        workspace_id: str,
        operation_invocation_id: str,
        operation_class: OperationClass,
        state: object,
        measurement_root_ref: object,
        constraint_store_ref: str | None = None,
    ) -> FoundryConsumptionResult:
        """Build a consumption proof from real ``RunCausalEvaluationNode`` outputs."""

        artifacts_index = getattr(state, "artifacts_index", {}) or {}
        method_result = artifacts_index.get(ARTIFACT_CAUSAL_METHOD_RESULT_REF)
        method_evidence = artifacts_index.get(ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF)
        if method_result is None or method_evidence is None:
            raise ValueError("Foundry method output and evidence refs are required")
        result_ref = _pdc_ref_from_core(
            method_result,
            artifact_type="FoundryMethodResult",
            schema_ref="polisyos.foundry.methods.result.v1",
        )
        evidence_ref = _pdc_ref_from_core(
            method_evidence,
            artifact_type="FoundryMethodEvidence",
            schema_ref="polisyos.foundry.methods.evidence.v1",
        )
        input_provenance = _input_provenance(measurement_root_ref)
        synthetic_probe = input_provenance == "synthetic_probe"
        measurement_ref = _pdc_ref_from_core(
            measurement_root_ref,
            artifact_type=(
                "SyntheticObservationInput" if synthetic_probe else "MeasurementRoot"
            ),
            schema_ref=(
                "policyos.gy.phase2.synthetic_observational_data.v1"
                if synthetic_probe
                else "polisyos.ir.observational_data.v1"
            ),
        )
        record = MethodOutputConsumptionRecord(
            consumption_id=f"consume-{_slug(operation_invocation_id)}",
            workspace_id=workspace_id,
            operation_invocation_id=operation_invocation_id,
            operation_class=operation_class,
            consumed_method_output_refs=[result_ref],
            consumed_method_evidence_refs=[evidence_ref],
            dag_consumed_method_outputs_count=1,
            measurement_root_refs=[] if synthetic_probe else [measurement_ref],
            constraint_store_ref=constraint_store_ref,
        )
        may_not_use_for = [
            "design_decision_authority",
            "production_recommendation",
            "publication_authority",
        ]
        known_limits = ["Phase 2 caps Foundry consumption at descriptive authority."]
        open_production_findings: list[str] = []
        if synthetic_probe:
            may_not_use_for.append("measurement_rooted_authority")
            known_limits.append(
                "F10 open: loop-generated synthetic panel is a probe input, not "
                "catalog-measurement-rooted evidence."
            )
            open_production_findings.append("F10")
        authority = AuthorityBoundary(
            boundary_id=f"authority-{_slug(workspace_id)}-foundry",
            authoritative_for=[f"{operation_class.value.lower()}:{workspace_id}"],
            may_not_use_for=may_not_use_for,
            source_authority="deterministic_producer",
            posture="governed",
            rule_version_refs=[FOUNDRY_CONSUMPTION_RULE_VERSION],
            evidence_kind="simulation" if synthetic_probe else "measurement",
            decision_grade="descriptive_only",
            evidence_basis=EvidenceBasis(
                producer_roots=[measurement_ref],
                method_refs=[result_ref.artifact_id],
                calibration_refs=[],
                counterexamples_closed=[],
            ),
            known_limits=known_limits,
        )
        return FoundryConsumptionResult(
            record=record,
            authority_boundary=authority,
            input_provenance=input_provenance,
            open_production_findings=open_production_findings,
        )

    def persist_consumption(
        self,
        *,
        store: FileSystemCAS,
        consumption: FoundryConsumptionResult,
    ) -> ArtifactRef:
        """Persist a consumed-method proof to CAS and return its GY artifact ref."""

        payload = {
            "schema_version": FOUNDRY_CONSUMPTION_RULE_VERSION,
            "record": consumption.record.model_dump(mode="json"),
            "authority_boundary": consumption.authority_boundary.model_dump(mode="json"),
            "input_provenance": consumption.input_provenance,
            "open_production_findings": list(consumption.open_production_findings),
        }
        core_ref = store.put_json(
            payload,
            PutOptions(
                kind="gy.method_output_consumption",
                media_type="application/json",
                schema=SchemaInfo(
                    name="policyos.gy.phase2.MethodOutputConsumptionRecord",
                    version="1.0",
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        return ArtifactRef.from_payload(
            artifact_id=str(core_ref.artifact_id),
            artifact_type="MethodOutputConsumptionRecord",
            payload=payload,
            schema_ref="policyos.gy.phase2.MethodOutputConsumptionRecord.v1",
            uri=f"cas://{core_ref.artifact_id}",
            version="phase2.v1",
        )


class ConstraintStoreIngestor:
    """Convert governed requirement artifacts into existing ConstraintStore records."""

    def ingest(
        self,
        *,
        snapshot_id: str,
        grammar_expansion_ref: str,
        artifacts: list[dict[str, Any]],
    ) -> ConstraintStoreSnapshot:
        """Reject free text and ingest only governed obligation/requirement artifacts."""

        entries: list[ConstraintStoreEntry] = []
        for artifact in artifacts:
            source_kind = str(artifact.get("source_kind") or "")
            source_ref = str(artifact.get("artifact_ref") or "")
            if source_kind not in _ALLOWED_CONSTRAINT_SOURCES or not source_ref:
                raise ValueError("Phase-2 constraints require a governed artifact source")
            status = str(artifact.get("status") or "")
            constraint_id = f"phase2.{source_kind}.{_source_slug(source_ref)}"
            entries.append(
                ConstraintStoreEntry(
                    constraint_id=constraint_id,
                    cell_ref=f"phase2.{source_kind}",
                    status=status,
                    source_ref=source_ref,
                    consumer_ref=str(artifact.get("consumer_ref") or "VERIFY"),
                    refinement_route=_route_for_status(status),
                    evidence_refs=[source_ref],
                    reason=str(artifact.get("reason") or "governed Phase-2 constraint"),
                    rule_version_ref=FOUNDRY_CONSUMPTION_RULE_VERSION,
                )
            )
        hard_ids = [entry.constraint_id for entry in entries if entry.status == "block"]
        governance_gap_ids = [
            entry.constraint_id
            for entry in entries
            if entry.status == "block" and entry.cell_ref
            in {"phase2.obligation", "phase2.method_requirement"}
        ]
        return ConstraintStoreSnapshot(
            snapshot_id=snapshot_id,
            snapshot_ref=f"pdc://phase2/{snapshot_id}",
            grammar_expansion_ref=grammar_expansion_ref,
            constraint_ids=[entry.constraint_id for entry in entries],
            hard_constraint_ids=hard_ids,
            governance_owned_gap_ids=governance_gap_ids,
            constraint_records=entries,
        )


def evaluate_constraint_store_for_phase2(
    snapshot: ConstraintStoreSnapshot,
) -> ConstraintStoreDecision:
    """Consume an existing ConstraintStoreSnapshot for Phase-2 promotion gating."""

    blocking = [
        record.constraint_id
        for record in snapshot.constraint_records
        if record.status == "block"
    ]
    limiting = [
        record.constraint_id
        for record in snapshot.constraint_records
        if record.status == "limit"
    ]
    warning = [
        record.constraint_id
        for record in snapshot.constraint_records
        if record.status == "warn"
    ]
    return ConstraintStoreDecision(
        blocks_promotion=bool(blocking),
        downgrades_authority=bool(limiting or warning),
        blocking_constraint_ids=blocking,
        limiting_constraint_ids=limiting,
        warning_constraint_ids=warning,
    )


def _pdc_ref_from_core(value: object, *, artifact_type: str, schema_ref: str) -> ArtifactRef:
    artifact_id = str(getattr(value, "artifact_id", value))
    payload = {
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "schema_ref": schema_ref,
    }
    return ArtifactRef.from_payload(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        payload=payload,
        schema_ref=schema_ref,
        uri=f"cas://{artifact_id}",
        version="v1",
    )


def _input_provenance(value: object) -> Literal["measurement_rooted", "synthetic_probe"]:
    if not _is_typed_artifact_ref(value):
        raise ValueError(
            "Foundry measurement_root_ref requires a typed measurement ArtifactRef; "
            "untyped roots cannot be stamped as measurement."
        )
    kind = str(getattr(value, "kind", "") or "").lower()
    if "synthetic" in kind or kind.startswith("gy.synthetic"):
        return "synthetic_probe"
    if _is_measurement_root_kind(kind):
        return "measurement_rooted"
    raise ValueError(
        "Foundry measurement_root_ref requires a typed measurement ArtifactRef; "
        f"unsupported kind={kind or '<missing>'}."
    )


def _is_typed_artifact_ref(value: object) -> bool:
    return hasattr(value, "artifact_id") and hasattr(value, "kind")


def _is_measurement_root_kind(kind: str) -> bool:
    return kind in {
        "ir.observational_data",
        "policyos.gy.measurement_root_payload",
    } or "measurement" in kind


def _route_for_status(status: str) -> str:
    if status == "block":
        return "block_candidate"
    if status == "limit":
        return "human_decision"
    if status == "warn":
        return "reframe"
    if status == "pass":
        return "none"
    raise ValueError(f"Unsupported constraint status: {status}")


def _source_slug(source_ref: str) -> str:
    tail = source_ref.rsplit("/", maxsplit=1)[-1]
    tail = tail.rsplit(":", maxsplit=1)[-1]
    return _slug(tail)


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return normalized or "item"


__all__ = [
    "ConstraintStoreDecision",
    "ConstraintStoreIngestor",
    "FoundryConsumptionResult",
    "FoundryMethodOutputConsumer",
    "evaluate_constraint_store_for_phase2",
]
