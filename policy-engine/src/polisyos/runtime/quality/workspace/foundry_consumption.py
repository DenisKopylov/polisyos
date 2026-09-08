"""Foundry method-output consumption and Phase-2 constraint ingestion."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import fields
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts import ArtifactRef as CoreArtifactRef
from polisyos.core.artifacts.manifest import InputRef, ProducerInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.pdc import (
    ArtifactRef,
    AuthorityBoundary,
    ConstraintStoreEntry,
    ConstraintStoreSnapshot,
    EvidenceBasis,
    MethodOutputConsumptionRecord,
    OperationClass,
)
from polisyos.runtime.quality.data_forge_binding import verify_recorded_panel_method_input

if TYPE_CHECKING:
    from polisyos.core.artifacts.manifest import ArtifactManifest
    from polisyos.runtime.quality.data_forge_binding import RecordedPanelMethodInput
    from polisyos.scientist.orchestration.engine import ExperimentState

FOUNDRY_CONSUMPTION_RULE_VERSION = "policyos.gy.phase2.foundry.v2"
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
    input_binding_receipt_ref: ArtifactRef
    method_replay_verified: Literal[True]
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

    def __init__(self, *, store: FileSystemCAS | None = None) -> None:
        self._store = store
        self._verified_consumptions: dict[int, tuple[FoundryConsumptionResult, bytes]] = {}

    def consume_from_state(
        self,
        *,
        workspace_id: str,
        operation_invocation_id: str,
        operation_class: OperationClass,
        state: object,
        measurement_root_ref: object,
        binding_receipt_ref: CoreArtifactRef | None = None,
        constraint_store_ref: str | None = None,
    ) -> FoundryConsumptionResult:
        """Build a consumption proof from real ``RunCausalEvaluationNode`` outputs."""

        from polisyos.foundry.data_plane import materialize_method_contract
        from polisyos.foundry.methods import MethodRegistry
        from polisyos.ir.analytics.causal import CausalEffectReport, EstimationStatus

        from .scientist_node_adapters import (
            _pdc_binding_ref,
            _read_binding,
            _validated_node_state,
        )

        store = self._store
        if store is None or binding_receipt_ref is None:
            raise ValueError("foundry_recorded_binding_and_store_required")
        try:
            state = _validated_node_state(state)
            bound = verify_recorded_panel_method_input(
                store=store,
                binding_receipt_ref=binding_receipt_ref,
            )
            root = CoreArtifactRef.model_validate(measurement_root_ref)
            if root != bound.observational_data_ref or state.observational_data_ref != root:
                raise ValueError("foundry_recorded_root_binding_mismatch")
            method_fqn = state.causal_method_fqn or state.params.get("causal_method_fqn")
            if not isinstance(method_fqn, str) or not method_fqn:
                raise ValueError("foundry_method_identity_missing")
            signature = MethodRegistry.get_instance().get(method_fqn).signature
            if (
                signature.fqn != bound.receipt.method_fqn
                or signature.stable_digest() != bound.receipt.method_signature_digest
            ):
                raise ValueError("foundry_method_binding_mismatch")
            typed_input = materialize_method_contract(
                contract_target=bound.contract_target,
                contract_payload=bound.contract_payload,
            )
            result_binding, result_raw, result_manifest = _read_binding(
                store,
                state.artifacts_index[ARTIFACT_CAUSAL_METHOD_RESULT_REF],
                "method_result",
            )
            evidence_binding, evidence_raw, evidence_manifest = _read_binding(
                store,
                state.artifacts_index[ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF],
                "method_evidence",
            )
            root_binding, _, root_manifest = _read_binding(store, root, "recorded_observations")
            if root_manifest.artifact_schema is None:
                raise ValueError("foundry_recorded_root_schema_missing")
            receipt_binding, _, _ = _read_binding(
                store, binding_receipt_ref, "recorded_input_binding"
            )
            if (
                result_manifest.kind != f"scientist.method_result.{signature.namespace}"
                or result_manifest.artifact_schema
                != SchemaInfo(
                    name="polisyos.scientist.MethodResult",
                    version="0.1.0",
                )
                or evidence_manifest.kind != "scientist.method_evidence"
                or evidence_manifest.artifact_schema
                != SchemaInfo(
                    name="polisyos.scientist.MethodExecutionEvidence",
                    version="0.1.0",
                )
                or evidence_manifest.inputs
                != [
                    InputRef(
                        artifact_id=result_binding.artifact_ref.artifact_id,
                        role="method_result",
                    )
                ]
            ):
                raise ValueError("foundry_method_artifact_identity_mismatch")
            output = from_canonical_bytes(result_raw)
            report = CausalEffectReport.model_validate(output["report"])
            if report.status != EstimationStatus.SUCCESS:
                raise ValueError("foundry_method_report_not_successful")
            input_refs = _verified_method_input_refs(store, result_manifest, state, bound)
            params = dict(
                state.causal_method_params or state.params.get("causal_method_params") or {}
            )
            seed = int(state.params.get("random_seed", 0) or 0)
            _verify_method_replay(
                store=store,
                method_fqn=signature.fqn,
                typed_input=typed_input,
                params=params,
                seed=seed,
                input_refs=input_refs,
                result_raw=result_raw,
                evidence_raw=evidence_raw,
                result_manifest=result_manifest,
                evidence_manifest=evidence_manifest,
            )
        except Exception as exc:
            raise ValueError(f"foundry_consumption_unverified:{exc}") from exc
        result_ref = _pdc_binding_ref(
            result_binding,
            "FoundryMethodResult",
            "polisyos.scientist.MethodResult@0.1.0",
        )
        evidence_ref = _pdc_binding_ref(
            evidence_binding,
            "FoundryMethodEvidence",
            "polisyos.scientist.MethodExecutionEvidence@0.1.0",
        )
        measurement_ref = _pdc_binding_ref(
            root_binding,
            "MeasurementRoot",
            f"{root_manifest.artifact_schema.name}@{root_manifest.artifact_schema.version}",
        )
        binding_ref = _pdc_binding_ref(
            receipt_binding, "RecordedPanelMethodBinding", bound.receipt.schema_version
        )
        record = MethodOutputConsumptionRecord(
            consumption_id=f"consume-{_slug(operation_invocation_id)}",
            workspace_id=workspace_id,
            operation_invocation_id=operation_invocation_id,
            operation_class=operation_class,
            consumed_method_output_refs=[result_ref],
            consumed_method_evidence_refs=[evidence_ref],
            dag_consumed_method_outputs_count=1,
            measurement_root_refs=[measurement_ref],
            constraint_store_ref=constraint_store_ref,
        )
        may_not_use_for = [
            "design_decision_authority",
            "production_recommendation",
            "publication_authority",
            "causal_identification",
            "execution_cost_authority",
        ]
        known_limits = [
            "Phase 2 caps Foundry consumption at descriptive authority.",
            "Recorded fields: " + ", ".join(bound.receipt.measured_fields) + ".",
            "Declared assumptions: " + ", ".join(bound.receipt.assumed_fields) + ".",
            "Method replay establishes computation, not operational EvalSafety admission.",
            "Elapsed timings remain historical observations, not recomputed facts; "
            "only their cost arithmetic is rederived. They confer no execution-cost authority.",
        ]
        authority = AuthorityBoundary(
            boundary_id=f"authority-{_slug(workspace_id)}-foundry",
            authoritative_for=[f"{operation_class.value.lower()}:{workspace_id}"],
            may_not_use_for=may_not_use_for,
            source_authority="deterministic_producer",
            posture="governed",
            rule_version_refs=[FOUNDRY_CONSUMPTION_RULE_VERSION],
            evidence_kind="measurement",
            decision_grade="descriptive_only",
            evidence_basis=EvidenceBasis(
                producer_roots=[measurement_ref],
                method_refs=[result_ref.artifact_id],
                calibration_refs=[],
                counterexamples_closed=[],
            ),
            known_limits=known_limits,
        )
        consumption = FoundryConsumptionResult(
            record=record,
            authority_boundary=authority,
            input_provenance="measurement_rooted",
            input_binding_receipt_ref=binding_ref,
            method_replay_verified=True,
        )
        self._verified_consumptions[id(consumption)] = (
            consumption,
            _consumption_bytes(consumption),
        )
        return consumption

    def _require_verified_consumption(
        self,
        *,
        store: FileSystemCAS,
        consumption: FoundryConsumptionResult,
    ) -> bytes:
        verified = self._verified_consumptions.get(id(consumption))
        if (
            store is not self._store
            or verified is None
            or verified[0] is not consumption
            or verified[1] != _consumption_bytes(consumption)
        ):
            raise ValueError("foundry_consumption_verification_required")
        return verified[1]

    def persist_consumption(
        self,
        *,
        store: FileSystemCAS,
        consumption: FoundryConsumptionResult,
    ) -> ArtifactRef:
        """Persist a consumed-method proof to CAS and return its GY artifact ref."""

        verified = from_canonical_bytes(
            self._require_verified_consumption(store=store, consumption=consumption)
        )
        payload = {"schema_version": FOUNDRY_CONSUMPTION_RULE_VERSION, **verified}
        core_ref = store.put_json(
            payload,
            PutOptions(
                kind="gy.method_output_consumption",
                media_type="application/json",
                schema=SchemaInfo(
                    name="policyos.gy.phase2.MethodOutputConsumptionRecord",
                    version="2.0",
                ),
                producer=ProducerInfo(
                    component="polisyos.runtime.quality.workspace.foundry_consumption.FoundryMethodOutputConsumer",
                    version=FOUNDRY_CONSUMPTION_RULE_VERSION,
                ),
                inputs=[
                    InputRef(artifact_id=ref["artifact_id"], role=role)
                    for role, refs in (
                        ("method_result", verified["record"]["consumed_method_output_refs"]),
                        ("method_evidence", verified["record"]["consumed_method_evidence_refs"]),
                        ("measurement_root", verified["record"]["measurement_root_refs"]),
                        ("input_binding", [verified["input_binding_receipt_ref"]]),
                    )
                    for ref in refs
                ],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        from .scientist_node_adapters import _pdc_binding_ref, _read_binding

        binding, _, _ = _read_binding(store, core_ref, "method_consumption")
        return _pdc_binding_ref(
            binding,
            "MethodOutputConsumptionRecord",
            "policyos.gy.phase2.MethodOutputConsumptionRecord.v2",
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
            if entry.status == "block"
            and entry.cell_ref in {"phase2.obligation", "phase2.method_requirement"}
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
        record.constraint_id for record in snapshot.constraint_records if record.status == "block"
    ]
    limiting = [
        record.constraint_id for record in snapshot.constraint_records if record.status == "limit"
    ]
    warning = [
        record.constraint_id for record in snapshot.constraint_records if record.status == "warn"
    ]
    return ConstraintStoreDecision(
        blocks_promotion=bool(blocking),
        downgrades_authority=bool(limiting or warning),
        blocking_constraint_ids=blocking,
        limiting_constraint_ids=limiting,
        warning_constraint_ids=warning,
    )


def _verified_method_input_refs(
    store: FileSystemCAS,
    manifest: ArtifactManifest,
    state: ExperimentState,
    bound: RecordedPanelMethodInput,
) -> dict[str, CoreArtifactRef]:
    from polisyos.foundry.data_plane import materialize_method_contract

    from .scientist_node_adapters import _read_binding, _reference_closure

    inputs: dict[str, CoreArtifactRef] = {}
    for item in manifest.inputs:
        if not item.role or not item.role.startswith("input:"):
            raise ValueError("foundry_method_input_lineage_invalid")
        slot = item.role.removeprefix("input:")
        if not slot or slot in inputs:
            raise ValueError("foundry_method_input_lineage_duplicate")
        parent = store.get_manifest(item.artifact_id)
        ref = CoreArtifactRef(
            artifact_id=item.artifact_id,
            kind=parent.kind,
            media_type=parent.media_type,
        )
        _reference_closure(store, ref, item.role)
        inputs[slot] = ref

    selected_key = "ukraine_selected_foundry_method_contract_ref"
    if selected_key in state.inputs:
        selected = state.inputs[selected_key]
        if inputs.get("ukraine_selected_method_contract") != selected:
            raise ValueError("foundry_selected_contract_lineage_mismatch")
        _, raw, _ = _read_binding(store, selected, "selected_method_contract")
        selected_input = materialize_method_contract(
            contract_target=bound.contract_target,
            contract_payload=from_canonical_bytes(raw),
        )
        if selected_input.model_dump(mode="json") != bound.contract_payload:
            raise ValueError("foundry_selected_contract_content_mismatch")
    if "ukraine_foundry_method_input_bundle_ref" in state.inputs or (
        "ukraine_foundry_intake_receipt_ref" in state.artifacts_index
    ):
        # Recorded-row custody is not the staged Ukraine intake's authority.
        # Its current owner has no independent persisted-bundle verification API.
        raise ValueError("foundry_staged_intake_owner_verification_unavailable")
    return inputs


def _verify_method_replay(
    *,
    store: FileSystemCAS,
    method_fqn: str,
    typed_input: object,
    params: dict[str, Any],
    seed: int,
    input_refs: dict[str, CoreArtifactRef],
    result_raw: bytes,
    evidence_raw: bytes,
    result_manifest: ArtifactManifest,
    evidence_manifest: ArtifactManifest,
) -> None:
    from polisyos.scientist.compute import MethodBackend

    from .scientist_node_adapters import _read_binding

    replay_parent = store.root / "_recompute"
    replay_parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="foundry-method-", dir=replay_parent) as directory:
        replay_store = FileSystemCAS(Path(directory))
        execution = MethodBackend().run(
            cas_root=replay_store.root,
            method_fqn=method_fqn,
            method_version=None,
            input_state=typed_input,
            method_params=params,
            seed=seed,
            input_refs=input_refs,
        )
        for name, ref, expected_raw, expected_manifest in (
            ("result", execution.exec_artifacts.result_ref, result_raw, result_manifest),
            ("evidence", execution.exec_artifacts.evidence_ref, evidence_raw, evidence_manifest),
        ):
            _, actual_raw, actual_manifest = _read_binding(replay_store, ref, f"replay_{name}")
            if actual_manifest.byte_size != len(actual_raw) or expected_manifest.byte_size != len(
                expected_raw
            ):
                raise ValueError(f"foundry_method_{name}_manifest_size_mismatch")
            actual_semantic = (
                _method_evidence_semantics(actual_raw) if name == "evidence" else actual_raw
            )
            expected_semantic = (
                _method_evidence_semantics(expected_raw) if name == "evidence" else expected_raw
            )
            if actual_semantic != expected_semantic:
                raise ValueError(f"foundry_method_{name}_replay_mismatch")
            manifests = []
            for manifest, semantic in (
                (actual_manifest, actual_semantic),
                (expected_manifest, expected_semantic),
            ):
                projection = manifest.model_dump(
                    mode="json",
                    by_alias=True,
                    exclude={"created_at"},
                )
                if name == "evidence":
                    # This is comparison only: both original CAS identities were checked above.
                    # Keep all other manifest fields, including optional integrity metadata.
                    digest = hashlib.sha256(semantic).hexdigest()
                    projection["artifact_id"] = "sha256:" + digest
                    projection["integrity"]["sha256"] = digest
                    projection["byte_size"] = len(semantic)
                manifests.append(projection)
            if manifests[0] != manifests[1]:
                raise ValueError(f"foundry_method_{name}_manifest_mismatch")


def _consumption_bytes(consumption: FoundryConsumptionResult) -> bytes:
    return to_canonical_bytes(
        consumption.model_dump(mode="json"),
        CanonSpec(forbid_floats=False),
    )


def _method_evidence_semantics(raw: bytes) -> bytes:
    """Check cost arithmetic and exclude only typed elapsed observations from replay."""
    from polisyos.foundry.methods.backends.dispatch import _estimate_cost_usd
    from polisyos.foundry.methods.backends.protocol import MethodTiming
    from polisyos.foundry.methods.base import ComputeBackend

    payload = from_canonical_bytes(raw)
    cost = payload["artifacts"]["cost_attribution"]
    timings = {}
    for field in fields(MethodTiming):
        value = cost[field.name]
        if value is None and field.default is None:
            timings[field.name] = None
        elif type(value) in (int, float) and math.isfinite(value) and value >= 0:
            timings[field.name] = value
        else:
            raise ValueError("foundry_method_timing_observation_invalid")
    expected_cost = _estimate_cost_usd(
        backend=ComputeBackend(cost["backend"]),
        timing=MethodTiming(**timings),
    )
    reported_cost = cost["estimated_cost_usd"]
    if type(reported_cost) not in (int, float) or reported_cost != expected_cost:
        raise ValueError("foundry_method_cost_attribution_mismatch")
    for field in fields(MethodTiming):
        del cost[field.name]
    del cost["estimated_cost_usd"]
    return to_canonical_bytes(payload, CanonSpec(forbid_floats=False))


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
