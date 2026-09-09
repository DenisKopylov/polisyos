"""Foundry method-output consumption and Phase-2 constraint ingestion."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, fields
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core import artifacts as core_artifacts
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
from polisyos.policy_grammar import (
    PolicyGrammarConceptSpineRefs,  # noqa: TC001 - Pydantic resolves this public field at runtime.
    UniversalAuthorityProfile,  # noqa: TC001 - Pydantic resolves this public field at runtime.
)
from polisyos.runtime.quality.data_forge_binding import verify_recorded_panel_method_input
from polisyos.runtime.quality.design_problem import DesignProblem

if TYPE_CHECKING:
    from polisyos.core.artifacts.manifest import ArtifactManifest
    from polisyos.runtime.quality.data_forge_binding import RecordedPanelMethodInput
    from polisyos.scientist import ExperimentState

FOUNDRY_CONSUMPTION_RULE_VERSION = "policyos.gy.phase2.foundry.v3"
ARTIFACT_CAUSAL_METHOD_RESULT_REF = "causal_method_result_ref"
ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF = "causal_method_evidence_ref"
_ALLOWED_CONSTRAINT_SOURCES = frozenset(
    {"obligation", "participation_requirement", "method_requirement"}
)


class ConstraintStoreDecision(BaseModel):
    """Phase-2 consumer decision derived from a ConstraintStoreSnapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    blocks_promotion: bool
    downgrades_authority: bool
    blocking_constraint_ids: list[str]
    limiting_constraint_ids: list[str]
    warning_constraint_ids: list[str]


class FoundryConsumptionResult(BaseModel):
    """Bridge output proving GY consumed a real Foundry method artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    record: MethodOutputConsumptionRecord
    authority_boundary: AuthorityBoundary
    input_provenance: Literal["measurement_rooted", "synthetic_probe"]
    input_binding_receipt_ref: ArtifactRef
    method_replay_verified: Literal[True]
    constraint_admission_ref: ArtifactRef | None = None
    constraint_decision: ConstraintStoreDecision | None = None
    open_production_findings: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class StagedFoundryInputSource:
    """Explicit source coordinates for replay by the existing intake owner.

    Coordinates carry no completed-stage or measurement authority assertion.
    The source files must remain available for every current admission.
    """

    allowed_root: Path
    stage_manifests: tuple[tuple[str, Path], ...]


@dataclass(frozen=True)
class StagedFoundryInputBinding:
    """Existing BindFoundryInputsNode output offered for content re-verification.

    This is a transport object, not an attestation that a node ran. The complete
    source replay below establishes only the intake's stated content custody.
    """

    source: StagedFoundryInputSource
    state: ExperimentState


def _staged_source_paths(source: StagedFoundryInputSource | None) -> dict[str, Path]:
    """Validate transport coordinates before calling the existing source owner."""
    if not isinstance(source, StagedFoundryInputSource):
        raise ValueError("foundry_staged_intake_source_verification_missing")
    if not isinstance(source.allowed_root, Path) or not isinstance(source.stage_manifests, tuple):
        raise ValueError("foundry_staged_intake_source_coordinates_invalid")
    paths: dict[str, Path] = {}
    for row in source.stage_manifests:
        if (
            not isinstance(row, tuple)
            or len(row) != 2
            or not isinstance(row[0], str)
            or not row[0].strip()
            or not isinstance(row[1], Path)
        ):
            raise ValueError("foundry_staged_intake_source_coordinates_invalid")
        stage, path = row
        if stage in paths:
            raise ValueError("foundry_staged_intake_source_duplicate")
        paths[stage] = path
    return paths


def verify_staged_foundry_input_state(
    *,
    store: FileSystemCAS,
    state: ExperimentState,
    source: StagedFoundryInputSource | None,
    bound: RecordedPanelMethodInput,
) -> None:
    """Re-run the original intake owner and bind its complete emitted closure."""

    from polisyos.foundry.data_plane import load_ukraine_foundry_intake

    from .scientist_node_adapters import _read_binding, _validated_node_state

    state = _validated_node_state(state)
    paths = _staged_source_paths(source)
    if source is None:
        raise ValueError("foundry_staged_intake_source_verification_missing")
    # Fresh-CAS replay derives expected manifests independently of any supplied
    # stored manifest; reusing the supplied CAS could preserve poisoned ancestry.
    with TemporaryDirectory(prefix="gy-c3-staged-readback-") as temporary:
        replay_store = FileSystemCAS(Path(temporary) / "cas")
        replay = load_ukraine_foundry_intake(
            replay_store, stage_manifests=paths, allowed_root=source.allowed_root,
        )
        if set(paths) != set(replay.stage_receipt_refs):
            raise ValueError("foundry_staged_intake_source_scope_mismatch")
        expected_refs = {
            "ukraine_foundry_method_input_bundle_ref": replay.method_input_bundle_ref,
            "ukraine_foundry_intake_receipt_ref": replay.receipt_ref,
        }
        supplied_refs = {
            "ukraine_foundry_method_input_bundle_ref": core_artifacts.ArtifactRef.model_validate(
                state.inputs.get("ukraine_foundry_method_input_bundle_ref")
            ),
            "ukraine_foundry_intake_receipt_ref": core_artifacts.ArtifactRef.model_validate(
                state.artifacts_index.get("ukraine_foundry_intake_receipt_ref")
            ),
        }
        selected = core_artifacts.ArtifactRef.model_validate(
            state.inputs.get("ukraine_selected_foundry_method_contract_ref")
        )
        selected_keys = [
            key for key, ref in replay.method_contract_refs.items() if ref == selected
        ]
        if len(selected_keys) != 1:
            raise ValueError("foundry_staged_selected_contract_not_owner_emitted")
        selected_key = selected_keys[0]
        if (
            state.causal_method_fqn != bound.receipt.method_fqn
            or replay.method_contracts[selected_key].model_dump(mode="json")
            != bound.contract_payload
        ):
            raise ValueError("foundry_staged_recorded_input_content_mismatch")
        expected_refs["ukraine_selected_foundry_method_contract_ref"] = (
            replay.method_contract_refs[selected_key]
        )
        supplied_refs["ukraine_selected_foundry_method_contract_ref"] = selected
        if supplied_refs != expected_refs:
            raise ValueError("foundry_staged_intake_owner_content_mismatch")
        from .scientist_node_adapters import _reference_closure

        expected_closure = _reference_closure(replay_store, expected_refs, "owner_replay")
        actual_closure = _reference_closure(store, supplied_refs, "supplied")
        expected_by_id = {str(row.artifact_ref.artifact_id): row for row in expected_closure}
        actual_by_id = {str(row.artifact_ref.artifact_id): row for row in actual_closure}
        if set(actual_by_id) != set(expected_by_id):
            raise ValueError("foundry_staged_intake_complete_lineage_mismatch")
        for identity, expected_binding in expected_by_id.items():
            _, expected_raw, expected_manifest = _read_binding(
                replay_store, expected_binding.artifact_ref, "owner_replay:" + identity,
            )
            _, actual_raw, actual_manifest = _read_binding(
                store, actual_by_id[identity].artifact_ref, "supplied:" + identity,
            )
            # created_at is the CAS storage event, not the source stage time.
            # Source finished_at and every other content/manifest field stay bound.
            if (
                actual_raw != expected_raw
                or actual_manifest.model_dump(mode="json", exclude={"created_at"})
                != expected_manifest.model_dump(mode="json", exclude={"created_at"})
            ):
                raise ValueError("foundry_staged_intake_owner_content_mismatch:" + identity)



def install_verified_staged_foundry_inputs(
    *,
    store: FileSystemCAS,
    state: ExperimentState,
    binding: StagedFoundryInputBinding,
) -> ExperimentState:
    """Transport the actual input-binding output without inventing new outputs."""

    from .scientist_node_adapters import _validated_node_state

    if not isinstance(binding, StagedFoundryInputBinding):
        raise ValueError("foundry_staged_intake_binding_type_required")
    _staged_source_paths(binding.source)
    state = _validated_node_state(state)
    offered = _validated_node_state(binding.state)
    receipt = state.artifacts_index.get("foundry_input_binding_receipt_ref")
    if receipt is None:
        raise ValueError("foundry_recorded_binding_and_store_required")
    bound = verify_recorded_panel_method_input(store=store, binding_receipt_ref=receipt)
    if offered.causal_method_fqn != state.causal_method_fqn:
        raise ValueError("foundry_staged_selected_method_mismatch")
    result = state.model_copy(deep=True)
    for key in (
        "ukraine_foundry_method_input_bundle_ref",
        "ukraine_selected_foundry_method_contract_ref",
    ):
        if key not in offered.inputs:
            raise ValueError("foundry_staged_intake_input_missing:" + key)
        result.inputs[key] = core_artifacts.ArtifactRef.model_validate(offered.inputs[key])
    key = "ukraine_foundry_intake_receipt_ref"
    if key not in offered.artifacts_index:
        raise ValueError("foundry_staged_intake_input_missing:" + key)
    result.artifacts_index[key] = core_artifacts.ArtifactRef.model_validate(
        offered.artifacts_index[key]
    )
    # Preserve the independently verified recorded measurement root; the
    # selected staged DTO must have exactly the same substantive input payload.
    verify_staged_foundry_input_state(
        store=store, state=result, source=binding.source, bound=bound,
    )
    return result


class FoundryMethodOutputConsumer:
    """Consume Foundry method outputs from Scientist state into GY authority facts."""

    def __init__(
        self, *, store: FileSystemCAS | None = None,
        staged_input_source: StagedFoundryInputSource | None = None,
    ) -> None:
        self._store = store
        self._staged_input_source = staged_input_source
        self._verified_consumptions: dict[int, tuple[FoundryConsumptionResult, bytes]] = {}
        self._verified_source_bindings: dict[int, bytes] = {}
        self._verified_constraint_admissions: dict[
            int, tuple[ConstraintStoreIngestor, Phase2ConstraintAdmission, bytes]
        ] = {}

    def consume_from_state(
        self,
        *,
        workspace_id: str,
        operation_invocation_id: str,
        operation_class: OperationClass,
        state: object,
        measurement_root_ref: object,
        binding_receipt_ref: core_artifacts.ArtifactRef | None = None,
        constraint_store_ref: str | None = None,
        constraint_owner: ConstraintStoreIngestor | None = None,
        constraint_admission: Phase2ConstraintAdmission | None = None,
    ) -> FoundryConsumptionResult:
        """Build a consumption proof from real ``RunCausalEvaluationNode`` outputs."""

        from polisyos.foundry.data_plane import materialize_method_contract
        from polisyos.foundry.methods import MethodRegistry
        from polisyos.ir import CausalEffectReport, EstimationStatus

        from .scientist_node_adapters import (
            _pdc_binding_ref,
            _read_binding,
            _validated_node_state,
        )

        store = self._store
        constraint_ref = None
        constraint_decision = None
        if any(
            item is not None
            for item in (constraint_store_ref, constraint_owner, constraint_admission)
        ):
            if (
                constraint_store_ref is None
                or constraint_owner is None
                or constraint_admission is None
                or constraint_owner._store is not store
                or str(constraint_admission.artifact_ref.artifact_id) != constraint_store_ref
            ):
                raise ValueError("constraint_admission_and_owner_required")
            supplied_ref = core_artifacts.ArtifactRef.model_validate(
                constraint_admission.artifact_ref.model_dump(mode="json")
            )
            constraint_packet = from_canonical_bytes(
                constraint_owner.require(constraint_admission, workspace_id=workspace_id)
            )
            constraint_decision = ConstraintStoreDecision.model_validate(
                constraint_packet["decision"]
            )
            binding, _, manifest = _read_binding(store, supplied_ref, "constraint_store")
            constraint_ref = _pdc_binding_ref(
                binding,
                "ConstraintStore",
                f"{manifest.artifact_schema.name}@{manifest.artifact_schema.version}",
            )
        if store is None or binding_receipt_ref is None:
            raise ValueError("foundry_recorded_binding_and_store_required")
        try:
            state = _validated_node_state(state)
            bound = verify_recorded_panel_method_input(
                store=store,
                binding_receipt_ref=binding_receipt_ref,
            )
            root = core_artifacts.ArtifactRef.model_validate(measurement_root_ref)
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
            input_refs = _verified_method_input_refs(
                store, result_manifest, state, bound,
                staged_input_source=self._staged_input_source,
            )
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
        if constraint_decision is not None:
            known_limits.append(
                "Requirement preflight remains binding: "
                + ", ".join(constraint_decision.blocking_constraint_ids)
            )
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
            constraint_admission_ref=constraint_ref,
            constraint_decision=constraint_decision,
        )
        self._verified_consumptions[id(consumption)] = (
            consumption,
            _consumption_bytes(consumption),
        )
        self._verified_source_bindings[id(consumption)] = _constraint_bytes(
            {
                "bindings": [
                    item.model_dump(mode="json")
                    for item in (result_binding, evidence_binding, root_binding, receipt_binding)
                ]
            }
        )
        if constraint_owner is not None and constraint_admission is not None:
            reconciled = constraint_owner.reconcile_method(
                constraint_admission, method_owner=self, consumption=consumption
            )
            return self.bind_constraints(
                consumption=consumption, owner=constraint_owner, admission=reconciled
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
        # The receipt body and the custody it consumes are one sealed quantity.
        # A subsequent consumer may not re-interpret a rewritten source manifest.
        from .scientist_node_adapters import _read_binding

        bindings = self._verified_source_bindings.get(id(consumption))
        if bindings is None:
            raise ValueError("foundry_consumption_source_custody_required")
        for source in from_canonical_bytes(bindings)["bindings"]:
            current, _, _ = _read_binding(store, source["artifact_ref"], source["path"])
            if current.model_dump(mode="json") != source:
                raise ValueError("foundry_consumption_source_custody_changed")
        constraints = self._verified_constraint_admissions.get(id(consumption))
        if constraints is not None:
            owner, admission, expected = constraints
            workspace_id = from_canonical_bytes(verified[1])["record"]["workspace_id"]
            if owner.require(admission, workspace_id=workspace_id) != expected:
                raise ValueError("foundry_consumption_constraint_custody_changed")
        return verified[1]

    def bind_constraints(
        self,
        *,
        consumption: FoundryConsumptionResult,
        owner: ConstraintStoreIngestor,
        admission: Phase2ConstraintAdmission,
    ) -> FoundryConsumptionResult:
        """Bind a recomputed post-execution ceiling without executing the method again."""
        from .scientist_node_adapters import _pdc_binding_ref, _read_binding

        store = self._store
        if store is None or owner._store is not store:
            raise ValueError("constraint_admission_and_owner_required")
        original = self._require_verified_consumption(store=store, consumption=consumption)
        frozen = from_canonical_bytes(original)
        supplied_ref = core_artifacts.ArtifactRef.model_validate(
            admission.artifact_ref.model_dump(mode="json")
        )
        packet_bytes = owner.require(admission, workspace_id=frozen["record"]["workspace_id"])
        packet = from_canonical_bytes(packet_bytes)
        if packet["method_consumption_hash"] != "sha256:" + hashlib.sha256(original).hexdigest():
            raise ValueError("constraint_method_consumption_binding_mismatch")
        binding, _, manifest = _read_binding(store, supplied_ref, "constraint_store")
        if manifest.artifact_schema is None:
            raise ValueError("constraint_store_schema_missing")
        pdc_ref = _pdc_binding_ref(
            binding,
            "ConstraintStore",
            f"{manifest.artifact_schema.name}@{manifest.artifact_schema.version}",
        )
        frozen["record"]["constraint_store_ref"] = str(supplied_ref.artifact_id)
        frozen["constraint_admission_ref"] = pdc_ref.model_dump(mode="json")
        frozen["constraint_decision"] = packet["decision"]
        frozen["authority_boundary"]["known_limits"].append(
            "Post-execution requirement ceilings: "
            + ", ".join(
                [
                    *packet["decision"]["blocking_constraint_ids"],
                    *packet["decision"]["limiting_constraint_ids"],
                    *packet["decision"]["warning_constraint_ids"],
                ]
            )
        )
        result = FoundryConsumptionResult.model_validate(frozen)
        self._verified_consumptions[id(result)] = (result, _consumption_bytes(result))
        self._verified_source_bindings[id(result)] = self._verified_source_bindings[id(consumption)]
        self._verified_constraint_admissions[id(result)] = (owner, admission, packet_bytes)
        return result

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
                    version="3.0",
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
                        (
                            "constraint_store",
                            [verified["constraint_admission_ref"]]
                            if verified.get("constraint_admission_ref") is not None
                            else [],
                        ),
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
            "policyos.gy.phase2.MethodOutputConsumptionRecord.v3",
        )


class Phase2RequirementBasis(BaseModel):
    """Original compilation inputs; these confer no institutional evidence authority.

    The workspace owner supplies this context. A caller cannot submit precomputed
    requirement IDs, statuses or a candidate-selected subset of the population.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    authority_profile: UniversalAuthorityProfile
    concept_spine_refs: PolicyGrammarConceptSpineRefs
    source_refs: tuple[core_artifacts.ArtifactRef, ...] = ()


class Phase2ConstraintAdmission(BaseModel):
    """Readback handle; deserialization alone cannot recreate owner admission."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_ref: core_artifacts.ArtifactRef
    workspace_id: str
    design_problem_hash: str
    decision: ConstraintStoreDecision
    missing_basis: tuple[str, ...]


class ConstraintStoreIngestor:
    """Recompute requirement ceilings and persist their full scoped input population."""

    def __init__(self, *, store: FileSystemCAS | None = None) -> None:
        self._store = store
        self._admissions: dict[int, tuple[Phase2ConstraintAdmission, bytes, bytes]] = {}
        self._method_contexts: dict[
            bytes, tuple[FoundryMethodOutputConsumer, FoundryConsumptionResult, bytes]
        ] = {}

    def ingest(
        self,
        *,
        snapshot_id: str,
        grammar_expansion_ref: str,
        artifacts: list[dict[str, Any]],
    ) -> ConstraintStoreSnapshot:
        """Refuse the retired caller-status admission path, including an empty list."""
        raise ValueError("constraint_requirement_basis_required")

    def produce(
        self,
        *,
        workspace_id: str,
        design_problem: DesignProblem,
        basis: Phase2RequirementBasis | None = None,
    ) -> Phase2ConstraintAdmission:
        """Persist actual owner recomputation or an explicit missing-basis refusal."""
        from datetime import UTC, datetime

        problem = DesignProblem.model_validate(design_problem.model_dump(mode="json"))
        typed_basis = (
            Phase2RequirementBasis.model_validate(basis.model_dump(mode="json"))
            if basis is not None
            else None
        )
        original = _constraint_bytes(
            {
                "workspace_id": workspace_id,
                "design_problem": problem.model_dump(mode="json"),
                "basis": typed_basis.model_dump(mode="json") if typed_basis is not None else None,
                "generated_at": datetime.now(UTC).isoformat(),
            }
        )
        return self._admit(original)

    def reconcile_method(
        self,
        admission: Phase2ConstraintAdmission,
        *,
        method_owner: FoundryMethodOutputConsumer,
        consumption: FoundryConsumptionResult,
    ) -> Phase2ConstraintAdmission:
        """Reconcile the full requirement basis with a replay-verified real method result."""
        self.require(admission, workspace_id=admission.workspace_id)
        if self._store is None:
            raise ValueError("constraint_store_required")
        method_bytes = method_owner._require_verified_consumption(
            store=self._store, consumption=consumption
        )
        frozen = from_canonical_bytes(method_bytes)
        stored = self._admissions[id(admission)]
        request = from_canonical_bytes(stored[2])
        if frozen["record"]["workspace_id"] != request["workspace_id"]:
            raise ValueError("constraint_method_workspace_mismatch")
        request["method_consumption"] = frozen
        original = _constraint_bytes(request)
        self._method_contexts[original] = (method_owner, consumption, method_bytes)
        return self._admit(original)

    def _admit(self, original: bytes) -> Phase2ConstraintAdmission:
        request = from_canonical_bytes(original)
        workspace_id = request["workspace_id"]
        packet = self._current_packet(original)
        ref = self._persist("gy.constraint_store", packet, packet["parent_refs"])
        admission = Phase2ConstraintAdmission(
            artifact_ref=ref,
            workspace_id=workspace_id,
            design_problem_hash=packet["design_problem_hash"],
            decision=ConstraintStoreDecision.model_validate(packet["decision"]),
            missing_basis=tuple(packet["missing_basis"]),
        )
        self._admissions[id(admission)] = (
            admission,
            _constraint_bytes(admission.model_dump(mode="json")),
            original,
        )
        self.require(admission, workspace_id=workspace_id)
        return admission

    def require(
        self,
        admission: Phase2ConstraintAdmission,
        *,
        workspace_id: str,
    ) -> bytes:
        """Return immutable CAS bytes only after full current owner recomputation."""
        from .scientist_node_adapters import _read_binding

        stored = self._admissions.get(id(admission))
        if (
            self._store is None
            or stored is None
            or stored[0] is not admission
            or stored[1] != _constraint_bytes(admission.model_dump(mode="json"))
            or admission.workspace_id != workspace_id
        ):
            raise ValueError("constraint_admission_not_owner_verified")
        sealed = Phase2ConstraintAdmission.model_validate(from_canonical_bytes(stored[1]))
        _, raw, manifest = _read_binding(self._store, sealed.artifact_ref, "constraint_store")
        expected = self._current_packet(stored[2])
        if (
            raw != _constraint_bytes(expected)
            or manifest.kind != "gy.constraint_store"
            or manifest.artifact_schema != _constraint_schema("gy.constraint_store")
            or manifest.producer != _constraint_producer()
            or manifest.inputs != _constraint_inputs(expected["parent_refs"])
        ):
            raise ValueError("constraint_store_recomputation_mismatch")
        return raw

    def readback(self, admission: Phase2ConstraintAdmission, *, workspace_id: str) -> bytes:
        """Return the verified packet and exact frozen inputs for audit recomputation."""
        stored = self._admissions.get(id(admission))
        raw = self.require(admission, workspace_id=workspace_id)
        if stored is None or stored[0] is not admission:
            raise ValueError("constraint_admission_not_owner_verified")
        return _constraint_bytes(
            {
                "schema_version": "policyos.gy.phase2.ConstraintReadback.v1",
                "packet": from_canonical_bytes(raw),
                "request": from_canonical_bytes(stored[2]),
            }
        )

    def _current_packet(self, original: bytes) -> dict[str, Any]:
        try:
            return self._recompute(original)
        except (ValueError, OSError) as exc:
            # A supplied unreadable/invalid basis is unavailable, never a zero
            # denominator. Do not convert importer/programming failures to data.
            request = from_canonical_bytes(original)
            problem = DesignProblem.model_validate(request["design_problem"])
            problem_ref = self._persist(
                "gy.constraint_problem", problem.model_dump(mode="json"), []
            )
            missing = ["constraint_requirement_basis_unverified"]
            return {
                "schema_version": FOUNDRY_CONSUMPTION_RULE_VERSION,
                "workspace_id": request["workspace_id"],
                "design_problem_hash": "sha256:"
                + hashlib.sha256(_constraint_bytes(request["design_problem"])).hexdigest(),
                "generated_at": request["generated_at"],
                "evaluation_phase": "post_execution_reconciliation"
                if "method_consumption" in request
                else "requirement_preflight",
                "method_consumption_hash": None,
                "method_report_ref": None,
                "snapshot": None,
                "population": None,
                "missing_basis": missing,
                "failure": {"type": type(exc).__name__, "reason": str(exc)},
                "decision": _constraint_decision([], missing).model_dump(mode="json"),
                "parent_refs": [
                    {"artifact_id": str(problem_ref.artifact_id), "role": "design_problem"}
                ],
                "authority_boundary": {
                    "authoritative_for": ["requirement_preflight_refusal"],
                    "may_not_use_for": [
                        "legal_authority",
                        "participation_legitimacy",
                        "method_validity",
                        "production_decision",
                        "publication_authority",
                    ],
                },
            }

    def _persist(
        self,
        kind: str,
        payload: dict[str, Any],
        parents: list[dict[str, str]],
    ) -> core_artifacts.ArtifactRef:
        from .scientist_node_adapters import _read_binding

        if self._store is None:
            raise ValueError("constraint_store_required")
        # Freeze the complete parent-role/identity basis before any write. A
        # projection of equal data under different evidence must have new bytes,
        # so immutable CAS cannot silently reuse an earlier manifest's ancestry.
        frozen_parents = from_canonical_bytes(_constraint_bytes({"parents": parents}))["parents"]
        if kind != "gy.constraint_store":
            payload = {
                "schema_version": FOUNDRY_CONSUMPTION_RULE_VERSION,
                "constraint_projection": kind,
                "source_payload": payload,
                "parent_refs": frozen_parents,
            }
        elif payload["parent_refs"] != frozen_parents:
            raise ValueError("constraint_store_parent_basis_mismatch")
        expected = _constraint_bytes(payload)
        options = PutOptions(
            kind=kind,
            media_type="application/json",
            schema=_constraint_schema(kind),
            producer=_constraint_producer(),
            inputs=_constraint_inputs(frozen_parents),
        )
        ref = self._store.put_json(
            from_canonical_bytes(expected),
            options,
            canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
        )
        _, raw, manifest = _read_binding(self._store, ref, "constraint_emission")
        if (
            raw != expected
            or manifest.kind != kind
            or manifest.media_type != "application/json"
            or manifest.artifact_schema != _constraint_schema(kind)
            or manifest.producer != _constraint_producer()
            or manifest.inputs != _constraint_inputs(frozen_parents)
        ):
            raise ValueError("constraint_emission_readback_mismatch")
        return ref

    def _verified_method_outputs(
        self, original: bytes
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]], str | None]:
        """Read the complete method-result/evidence pairing from the private verified receipt."""
        from polisyos.core.artifacts.manifest import ArtifactManifest

        from .scientist_node_adapters import _read_binding

        request = from_canonical_bytes(original)
        if "method_consumption" not in request:
            return [], [], None
        context = self._method_contexts.get(original)
        if self._store is None or context is None:
            raise ValueError("constraint_method_owner_verification_required")
        method_owner, consumption, sealed = context
        if (
            method_owner._require_verified_consumption(store=self._store, consumption=consumption)
            != sealed
        ):
            raise ValueError("constraint_method_verified_payload_changed")
        body = from_canonical_bytes(sealed)
        if body != request["method_consumption"]:
            raise ValueError("constraint_method_verified_payload_changed")
        record = body["record"]

        def read(
            ref: dict[str, Any], role: str
        ) -> tuple[core_artifacts.ArtifactRef, bytes, ArtifactManifest]:
            manifest = ArtifactManifest.model_validate(self._store.get_manifest(ref["artifact_id"]))
            typed = core_artifacts.ArtifactRef(
                artifact_id=ref["artifact_id"], kind=manifest.kind, media_type=manifest.media_type
            )
            binding, raw, manifest = _read_binding(self._store, typed, role)
            if binding.content_hash != ref["content_hash"]:
                raise ValueError("constraint_method_ref_content_mismatch")
            return typed, raw, manifest

        receipt, _, _ = read(body["input_binding_receipt_ref"], "recorded_input_binding")
        bound = verify_recorded_panel_method_input(store=self._store, binding_receipt_ref=receipt)
        roots = record["measurement_root_refs"]
        if [item["artifact_id"] for item in roots] != [
            str(bound.observational_data_ref.artifact_id)
        ]:
            raise ValueError("constraint_method_recorded_source_mismatch")
        parents = []
        input_refs = {}
        for ref in roots:
            typed, _, _ = read(ref, "measurement_root")
            parents.append({"artifact_id": str(typed.artifact_id), "role": "measurement_root"})
            input_refs["observational_data_ref"] = str(typed.artifact_id)
        parents.append({"artifact_id": str(receipt.artifact_id), "role": "recorded_input_binding"})
        results = record["consumed_method_output_refs"]
        evidences = record["consumed_method_evidence_refs"]
        result_ids = [item["artifact_id"] for item in results]
        evidence_ids = [item["artifact_id"] for item in evidences]
        if (
            not results
            or len(results) != len(evidences)
            or len(set(result_ids)) != len(results)
            or len(set(evidence_ids)) != len(evidences)
            or record["dag_consumed_method_outputs_count"] != len(results)
        ):
            raise ValueError("constraint_method_output_population_mismatch")
        evidence_by_result = {}
        for ref in evidences:
            typed, raw, manifest = read(ref, "method_evidence")
            if (
                manifest.kind != "scientist.method_evidence"
                or manifest.artifact_schema
                != SchemaInfo(name="polisyos.scientist.MethodExecutionEvidence", version="0.1.0")
                or len(manifest.inputs) != 1
                or manifest.inputs[0].role != "method_result"
            ):
                raise ValueError("constraint_method_evidence_schema_or_lineage_mismatch")
            result_id = str(manifest.inputs[0].artifact_id)
            if result_id in evidence_by_result:
                raise ValueError("constraint_method_evidence_duplicate_result")
            evidence_by_result[result_id] = (typed, from_canonical_bytes(raw))
            parents.append({"artifact_id": str(typed.artifact_id), "role": "method_evidence"})
        if set(evidence_by_result) != set(result_ids):
            raise ValueError("constraint_method_evidence_population_mismatch")
        outputs = []
        for ref in results:
            typed, raw, manifest = read(ref, "method_result")
            if manifest.artifact_schema != SchemaInfo(
                name="polisyos.scientist.MethodResult", version="0.1.0"
            ):
                raise ValueError("constraint_method_result_schema_mismatch")
            evidence_ref, evidence = evidence_by_result[str(typed.artifact_id)]
            if evidence["method_fqn"] != bound.receipt.method_fqn:
                raise ValueError("constraint_method_execution_identity_mismatch")
            outputs.append(
                {
                    "method_result": from_canonical_bytes(raw),
                    "method_evidence": evidence,
                    "method_result_ref": str(typed.artifact_id),
                    "method_evidence_ref": str(evidence_ref.artifact_id),
                    "input_refs": input_refs,
                }
            )
            parents.append({"artifact_id": str(typed.artifact_id), "role": "method_result"})
        return outputs, parents, "sha256:" + hashlib.sha256(sealed).hexdigest()

    def _recompute(self, original: bytes) -> dict[str, Any]:
        from datetime import datetime

        from polisyos.foundry import (
            select_method_candidates_for_requirements,
        )
        from polisyos.foundry.validation.method_quality import (
            build_foundry_method_report_from_execution_outputs,
        )
        from polisyos.method_requirement import MethodValidityRequirementCompiler
        from polisyos.obligation_graph import compile_obligation_graph
        from polisyos.obligation_rules import (
            build_seed_obligation_rule_catalog,
            select_governed_rules,
        )
        from polisyos.participation_requirement import evaluate_participation_requirement
        from polisyos.policy_grammar import (
            PolicyGrammarCompiler,
            PolicyGrammarIntent,
            facet_snapshots_for_obligation_graph,
        )
        from polisyos.scientist.policy_design import (
            ClaimDecompositionFacet,
            ClaimDecompositionInput,
            ClaimDecompositionObligation,
            compile_claim_decomposition,
            compile_participation_requirements_from_claim_ledger,
        )

        from .scientist_node_adapters import _read_binding

        if self._store is None:
            raise ValueError("constraint_store_required")
        request = from_canonical_bytes(original)
        problem = DesignProblem.model_validate(request["design_problem"])
        workspace_id = request["workspace_id"]
        problem_hash = (
            "sha256:" + hashlib.sha256(_constraint_bytes(request["design_problem"])).hexdigest()
        )
        problem_ref = self._persist("gy.constraint_problem", request["design_problem"], [])
        parents = [{"artifact_id": str(problem_ref.artifact_id), "role": "design_problem"}]
        missing: list[str] = []
        entries: list[ConstraintStoreEntry] = []
        population: dict[str, list[str]] = {}
        raw_basis = request["basis"]
        outputs, method_parents, method_hash = self._verified_method_outputs(original)
        parents.extend(method_parents)
        method_report_ref = None
        method_report = None
        if method_hash is not None:
            # Even an unavailable original requirement basis cannot erase an actual
            # completed method. The real report remains a bounded computation readback.
            method_report = build_foundry_method_report_from_execution_outputs(
                method_outputs=outputs
            )
            method_report_core = self._persist(
                "gy.constraint_method_report", method_report, method_parents
            )
            method_report_ref = str(method_report_core.artifact_id)
            parents.append({"artifact_id": method_report_ref, "role": "method_report"})
        grammar_ref: str | None = None
        if raw_basis is None:
            missing.append("constraint_requirement_basis_missing")
        else:
            basis = Phase2RequirementBasis.model_validate(raw_basis)
            source_ids = [str(ref.artifact_id) for ref in basis.source_refs]
            if len(source_ids) != len(set(source_ids)):
                raise ValueError("constraint_source_identity_duplicate")
            for ref in basis.source_refs:
                _read_binding(self._store, ref, "constraint_source")
                parents.append({"artifact_id": str(ref.artifact_id), "role": "constraint_source"})
            basis_ref = self._persist("gy.constraint_basis", raw_basis, parents)
            parents.append({"artifact_id": str(basis_ref.artifact_id), "role": "requirement_basis"})
            # Resolving supplied sources proves byte custody, not institutional standing.
            # This proposal is compilation-only until a source owner admits that context.
            missing.append("constraint_source_authority_verification_missing")
            compiled = PolicyGrammarCompiler().compile(
                intent=PolicyGrammarIntent(
                    intent_id=problem.design_problem_id,
                    problem_frame=problem.to_ir_problem_frame(),
                ),
                authority_profile=basis.authority_profile,
                concept_spine_refs=basis.concept_spine_refs,
            )
            grammar = compiled.model_dump(mode="json")
            grammar_core = self._persist("gy.constraint_grammar", grammar, parents)
            grammar_ref = str(grammar_core.artifact_id)
            parents.append({"artifact_id": grammar_ref, "role": "grammar_compilation"})
            if compiled.status in {"blocked", "candidate_unverified"} or compiled.facets is None:
                missing.append("constraint_grammar_not_admitted")
            else:
                facets = facet_snapshots_for_obligation_graph(compiled)
                catalog = build_seed_obligation_rule_catalog()
                catalog_core = self._persist(
                    "gy.constraint_rule_catalog",
                    catalog.model_dump(mode="json"),
                    [],
                )
                parents.append(
                    {"artifact_id": str(catalog_core.artifact_id), "role": "rule_catalog"}
                )
                graph = compile_obligation_graph(
                    run_id=workspace_id,
                    facets=facets,
                    governed_rules=select_governed_rules(catalog),
                    generated_at=datetime.fromisoformat(request["generated_at"]),
                    intent_text=problem.problem_statement,
                )
                graph_core = self._persist(
                    "gy.constraint_obligation_graph", graph.model_dump(mode="json"), parents
                )
                graph_ref = str(graph_core.artifact_id)
                parents.append({"artifact_id": graph_ref, "role": "obligation_graph"})
                bundle_by_id = {item.bundle_id: item for item in graph.bundle_ledger}
                frontier_by_bundle = {item.bundle_id: item for item in graph.blocking_frontier}
                deferred_by_bundle = {item.bundle_id: item for item in graph.deferred_or_rejected}
                if (
                    len(bundle_by_id) != len(graph.bundle_ledger)
                    or len(frontier_by_bundle) != len(graph.blocking_frontier)
                    or len(deferred_by_bundle) != len(graph.deferred_or_rejected)
                    or set(frontier_by_bundle) & set(deferred_by_bundle)
                    or set(bundle_by_id) != set(frontier_by_bundle) | set(deferred_by_bundle)
                ):
                    raise ValueError("constraint_obligation_population_mismatch")
                population["obligation"] = sorted(bundle_by_id)
                for bundle_id, bundle in sorted(bundle_by_id.items()):
                    entries.append(
                        _constraint_entry(
                            source_kind="obligation",
                            identity=bundle_id,
                            status="block" if bundle_id in frontier_by_bundle else "warn",
                            source_ref=graph_ref,
                            reason=(
                                "Owner-derived frontier requirement needs domain evidence; "
                                if bundle_id in frontier_by_bundle
                                else "Owner-derived deferred/candidate obligation remains visible; "
                            )
                            + bundle.canonical_obligation_text,
                        )
                    )
                # The claim owner requires actual obligations. Never create one just
                # to turn an empty compiler input into a green requirement denominator.
                if not graph.blocking_frontier:
                    missing.append("constraint_claim_requirement_population_not_established")
                else:
                    claim_input = ClaimDecompositionInput(
                        run_id=workspace_id,
                        intent=problem.problem_statement,
                        facets=[
                            ClaimDecompositionFacet(
                                facet_id=row["facet_id"],
                                facet_type=row["facet_type"],
                                value=row["value"],
                                concept_spine_refs=list(row["metadata"]["concept_spine_refs"]),
                                authority_profile_refs=[compiled.authority_profile.profile_id],
                            )
                            for row in facets
                        ],
                        obligations=[
                            ClaimDecompositionObligation(
                                obligation_id=item.frontier_id,
                                family=item.bundle_key.family,
                                description=item.obligation_text,
                            )
                            for item in graph.blocking_frontier
                        ],
                        concept_spine_refs=list(basis.concept_spine_refs.canonical_concept_refs),
                        authority_profile_refs=[compiled.authority_profile.profile_id],
                    )
                    ledger = compile_claim_decomposition(claim_input)
                    ledger_core = self._persist(
                        "gy.constraint_claim_ledger", ledger.model_dump(mode="json"), parents
                    )
                    parents.append(
                        {"artifact_id": str(ledger_core.artifact_id), "role": "claim_ledger"}
                    )
                    claims = [claim.model_dump(mode="json") for claim in ledger.claims]
                    claim_ids = [claim.claim_id for claim in ledger.claims]
                    if len(claim_ids) != len(set(claim_ids)) or not claim_ids:
                        raise ValueError("constraint_claim_population_unestablished")
                    population["claim"] = sorted(claim_ids)
                    participation = compile_participation_requirements_from_claim_ledger(ledger)
                    p_ids = [spec.requirement_id for spec in participation.requirements]
                    if len(p_ids) != len(set(p_ids)):
                        raise ValueError("constraint_participation_population_duplicate")
                    population["participation_requirement"] = sorted(p_ids)
                    for spec in participation.requirements:
                        # Actual absent records are evaluated by the real owner. This
                        # API does not relabel supplied positive assertions as records.
                        evaluation = evaluate_participation_requirement(spec, [])
                        evidence = self._persist(
                            "gy.constraint_participation_evaluation",
                            {
                                "requirement": spec.model_dump(mode="json"),
                                "evaluation": evaluation.model_dump(mode="json"),
                            },
                            parents,
                        )
                        parents.append(
                            {
                                "artifact_id": str(evidence.artifact_id),
                                "role": "participation_evaluation",
                            }
                        )
                        if evaluation.status != "missing":
                            raise ValueError(
                                "constraint_participation_missing_evidence_not_refused"
                            )
                        entries.append(
                            _constraint_entry(
                                source_kind="participation_requirement",
                                identity=spec.requirement_id,
                                status="block",
                                source_ref=str(evidence.artifact_id),
                                reason=evaluation.blocker_code
                                or "participation_provenance_missing",
                            )
                        )
                    methods = MethodValidityRequirementCompiler().compile(
                        run_id=workspace_id,
                        claims=claims,
                        requirement_graph_ref=graph_ref,
                        generated_at=datetime.fromisoformat(request["generated_at"]),
                    )
                    m_ids = [spec.requirement_id for spec in methods.requirements]
                    if len(m_ids) != len(set(m_ids)):
                        raise ValueError("constraint_method_population_duplicate")
                    population["method_requirement"] = sorted(m_ids)
                    if not m_ids:
                        missing.append("constraint_method_requirement_population_not_established")
                    if method_hash is not None:
                        method_report = build_foundry_method_report_from_execution_outputs(
                            method_outputs=outputs,
                            method_requirements=methods.requirements,
                        )
                        report_core = self._persist(
                            "gy.constraint_method_report", method_report, parents
                        )
                        method_report_ref = str(report_core.artifact_id)
                        parents.append(
                            {"artifact_id": method_report_ref, "role": "method_requirement_report"}
                        )
                    selection = select_method_candidates_for_requirements(
                        candidate_methods=[]
                        if method_report is None
                        else method_report["selected_methods"],
                        method_requirements=methods.requirements,
                    )
                    statuses = selection["method_requirement_statuses"]
                    if set(statuses) != set(m_ids):
                        raise ValueError("constraint_method_evaluation_population_mismatch")
                    method_core = self._persist(
                        "gy.constraint_method_preflight", selection, parents
                    )
                    parents.append(
                        {"artifact_id": str(method_core.artifact_id), "role": "method_preflight"}
                    )
                    for spec in methods.requirements:
                        status = statuses[spec.requirement_id]
                        if status not in {"missing", "satisfied"} or (
                            method_hash is None and status != "missing"
                        ):
                            raise ValueError("constraint_method_selection_status_unsubstantiated")
                        # MethodExecutionEvidence owns reproducible computation only.
                        # Shape-compatible selection cannot silently widen that claim.
                        entries.append(
                            _constraint_entry(
                                source_kind="method_requirement",
                                identity=spec.requirement_id,
                                status="block" if status == "missing" else "limit",
                                source_ref=str(method_core.artifact_id),
                                reason=(
                                    "Actual method requirement selector found no supporting method."
                                    if status == "missing"
                                    else (
                                        "The selected replay-verified method establishes "
                                        "computation; "
                                        "independent method-validity evidence remains unverified."
                                    )
                                ),
                            )
                        )
        ids = [entry.constraint_id for entry in entries]
        if len(ids) != len(set(ids)):
            raise ValueError("constraint_identity_duplicate")
        # An absent basis has no fabricated grammar/obligation snapshot. The packet
        # and typed missing-basis decision still exist and are consumed by A.
        snapshot = None
        if grammar_ref is not None and "obligation" in population:
            snapshot_basis = {
                "snapshot_id": f"constraints-{_slug(workspace_id)}",
                "grammar_expansion_ref": grammar_ref,
                "constraint_ids": ids,
                "hard_constraint_ids": [
                    entry.constraint_id for entry in entries if entry.status == "block"
                ],
                "governance_owned_gap_ids": [
                    entry.constraint_id for entry in entries if entry.status == "block"
                ],
                "constraint_records": [entry.model_dump(mode="json") for entry in entries],
            }
            # The existing snapshot DTO references the persisted complete basis.
            # It is not a fabricated pdc:// address and does not hash its own ID.
            snapshot_core = self._persist("gy.constraint_snapshot_basis", snapshot_basis, parents)
            parents.append(
                {"artifact_id": str(snapshot_core.artifact_id), "role": "constraint_snapshot_basis"}
            )
            snapshot = ConstraintStoreSnapshot(
                snapshot_ref=str(snapshot_core.artifact_id), **snapshot_basis
            )
        decision = _constraint_decision(entries, missing)
        return {
            "schema_version": FOUNDRY_CONSUMPTION_RULE_VERSION,
            "workspace_id": workspace_id,
            "design_problem_hash": problem_hash,
            "generated_at": request["generated_at"],
            "evaluation_phase": "post_execution_reconciliation"
            if method_hash is not None
            else "requirement_preflight",
            "method_consumption_hash": method_hash,
            "method_report_ref": method_report_ref,
            "snapshot": snapshot.model_dump(mode="json") if snapshot is not None else None,
            "population": population if population else None,
            "missing_basis": missing,
            "decision": decision.model_dump(mode="json"),
            "parent_refs": parents,
            "authority_boundary": {
                "authoritative_for": ["requirement_preflight_refusal"],
                "may_not_use_for": [
                    "legal_authority",
                    "participation_legitimacy",
                    "method_validity",
                    "production_decision",
                    "publication_authority",
                ],
            },
        }


def _constraint_entry(
    *,
    source_kind: str,
    identity: str,
    status: str,
    source_ref: str,
    reason: str,
) -> ConstraintStoreEntry:
    return ConstraintStoreEntry(
        constraint_id=f"phase2.{source_kind}.{hashlib.sha256(identity.encode()).hexdigest()}",
        cell_ref=f"phase2.{source_kind}",
        status=status,
        source_ref=source_ref,
        consumer_ref="VERIFY",
        refinement_route=_route_for_status(status),
        evidence_refs=[source_ref],
        reason=reason,
        rule_version_ref=FOUNDRY_CONSUMPTION_RULE_VERSION,
    )


def _constraint_decision(
    entries: list[ConstraintStoreEntry],
    missing: list[str],
) -> ConstraintStoreDecision:
    blocking = [entry.constraint_id for entry in entries if entry.status == "block"]
    limiting = [entry.constraint_id for entry in entries if entry.status == "limit"]
    warning = [entry.constraint_id for entry in entries if entry.status == "warn"]
    return ConstraintStoreDecision(
        blocks_promotion=bool(blocking or missing),
        downgrades_authority=bool(limiting or warning or missing),
        blocking_constraint_ids=[*blocking, *missing],
        limiting_constraint_ids=limiting,
        warning_constraint_ids=warning,
    )


def evaluate_constraint_store_for_phase2(
    admission: Phase2ConstraintAdmission,
    *,
    owner: ConstraintStoreIngestor,
    workspace_id: str,
) -> ConstraintStoreDecision:
    """Consume the full actual owner recomputation, not caller statuses or a flag."""
    packet = from_canonical_bytes(owner.require(admission, workspace_id=workspace_id))
    return ConstraintStoreDecision.model_validate(packet["decision"])


def _constraint_bytes(payload: dict[str, Any]) -> bytes:
    return to_canonical_bytes(payload, CanonSpec(forbid_floats=False, exclude_none=False))


def _constraint_inputs(parents: list[dict[str, str]]) -> list[InputRef]:
    return [InputRef(artifact_id=ref["artifact_id"], role=ref["role"]) for ref in parents]


def _constraint_schema(kind: str) -> SchemaInfo:
    return SchemaInfo(name=f"policyos.{kind}", version="1.0")


def _constraint_producer() -> ProducerInfo:
    return ProducerInfo(
        component="polisyos.runtime.quality.workspace.foundry_consumption.ConstraintStoreIngestor",
        version=FOUNDRY_CONSUMPTION_RULE_VERSION,
    )


def _verified_method_input_refs(
    store: FileSystemCAS,
    manifest: ArtifactManifest,
    state: ExperimentState,
    bound: RecordedPanelMethodInput,
    *, staged_input_source: StagedFoundryInputSource | None = None,
) -> dict[str, core_artifacts.ArtifactRef]:
    from polisyos.foundry.data_plane import materialize_method_contract

    from .scientist_node_adapters import _read_binding, _reference_closure

    inputs: dict[str, core_artifacts.ArtifactRef] = {}
    for item in manifest.inputs:
        if not item.role or not item.role.startswith("input:"):
            raise ValueError("foundry_method_input_lineage_invalid")
        slot = item.role.removeprefix("input:")
        if not slot or slot in inputs:
            raise ValueError("foundry_method_input_lineage_duplicate")
        parent = store.get_manifest(item.artifact_id)
        ref = core_artifacts.ArtifactRef(
            artifact_id=item.artifact_id,
            kind=parent.kind,
            media_type=parent.media_type,
        )
        _reference_closure(store, ref, item.role)
        inputs[slot] = ref

    selected_key = "ukraine_selected_foundry_method_contract_ref"
    if selected_key in state.inputs:
        selected = core_artifacts.ArtifactRef.model_validate(state.inputs[selected_key])
        if inputs.get("ukraine_selected_method_contract") != selected:
            raise ValueError("foundry_selected_contract_lineage_mismatch")
        _, raw, _ = _read_binding(store, selected, "selected_method_contract")
        selected_input = materialize_method_contract(
            contract_target=bound.contract_target,
            contract_payload=from_canonical_bytes(raw),
        )
        if selected_input.model_dump(mode="json") != bound.contract_payload:
            raise ValueError("foundry_selected_contract_content_mismatch")
    staged_slots = {
        "ukraine_selected_method_contract": (state.inputs, selected_key),
        "ukraine_method_input_bundle": (state.inputs, "ukraine_foundry_method_input_bundle_ref"),
        "ukraine_intake_receipt": (state.artifacts_index, "ukraine_foundry_intake_receipt_ref"),
    }
    if (
        staged_input_source is not None
        or bool(inputs.keys() & staged_slots.keys())
        or any(key in mapping for mapping, key in staged_slots.values())
    ):
        verify_staged_foundry_input_state(
            store=store, state=state, source=staged_input_source, bound=bound,
        )
        for slot, (mapping, key) in staged_slots.items():
            if inputs.get(slot) != core_artifacts.ArtifactRef.model_validate(mapping[key]):
                raise ValueError("foundry_staged_intake_lineage_mismatch:" + slot)
    return inputs


def _verify_method_replay(
    *,
    store: FileSystemCAS,
    method_fqn: str,
    typed_input: object,
    params: dict[str, Any],
    seed: int,
    input_refs: dict[str, core_artifacts.ArtifactRef],
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
    from polisyos.foundry.methods import (
        ComputeBackend,
        MethodTiming,
        estimate_method_execution_cost_usd,
    )

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
    expected_cost = estimate_method_execution_cost_usd(
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
    "Phase2ConstraintAdmission",
    "Phase2RequirementBasis",
    "evaluate_constraint_store_for_phase2",
]
