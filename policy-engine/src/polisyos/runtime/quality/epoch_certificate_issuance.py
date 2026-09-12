"""Bind actual decision-packet emission to independently admitted epoch inputs.

The canonical node records its full invocation; this owner derives its immutable
recipe and binds actual successful emission. The configured input resolver owns
admission of native epoch coordinates and the complete code/tool/environment
closure for that exact invocation. A plan, method label or caller DTO does not
establish that property.
The default resolver returns a nonreceipt. This module records execution and
checks exact source bytes; it does not invent a recipe language or execute reissue.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core import artifacts, canon, contracts, security
from polisyos.runtime.quality.epoch_validity_cascade import (
    DerivationRecipeBinding,
    EpochCertificateBinding,
    EpochDependencyDenominatorReceipt,
    EpochDependencyEdge,
    EpochDependencyGraph,
    bind_certificate_to_epoch,
    epoch_dependency_outer_denominator_ref,
)
from polisyos.runtime.quality.semantic_epoch import (
    EpochScopeHistory,
    SemanticEpochHistoryRepository,
    SemanticEpochManifest,
)
from polisyos.scientist import (
    DECISION_PACKET_INVOCATION_KIND,
    CanonicalDecisionPacketInvocation,
    CompletedDecisionPacketExecution,
    DecisionPacketInvocationRecord,
    EpochCertificateIssuanceNonReceipt,
    PersistedEpochCertificateIssuancePreparation,
    decision_packet_invocation_input_refs,
    require_canonical_decision_packet_execution,
    require_canonical_decision_packet_invocation,
)

ArtifactRef = artifacts.ArtifactRef
DecisionDependencyKind = contracts.DecisionDependencyKind
DecisionDependencyRef = contracts.DecisionDependencyRef
DecisionTriggerSpec = contracts.DecisionTriggerSpec
DecisionTriggerType = contracts.DecisionTriggerType
DecisionValidityEnvelope = contracts.DecisionValidityEnvelope
_PRODUCER = (
    "polisyos.scientist.nodes.builtins.decide.decision_packet.builder."
    "BuildDecisionPacketNode.execute"
)
_BASIS_KIND = "scientist.epoch_certificate_issuance_basis"
_RECEIPT_KIND = "scientist.epoch_certificate_issuance"
_CANON = canon.CanonSpec()
_DIGEST = r"^sha256:[0-9a-f]{64}$"
_Model = TypeVar("_Model", bound=BaseModel)


def _raw_hash(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _identity(ref: ArtifactRef) -> tuple[str, str, str]:
    return str(ref.artifact_id), ref.kind, ref.media_type


def _canonical_refs(refs: tuple[ArtifactRef, ...]) -> tuple[ArtifactRef, ...]:
    by_identity = {_identity(ref): ref for ref in refs}
    return tuple(by_identity[key] for key in sorted(by_identity))


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EpochCertificateIssuanceInputs(_StrictModel):
    """Native epoch and semantic source inputs from the privileged verifier.

    Admission must reconcile the exact native epoch, source certificates and
    profiles with this producer/run. An optional upstream recipe remains source
    evidence; this owner computes the actual invocation recipe independently.
    Artifact kinds never establish source admission or applicability.
    """

    run_id: str = Field(min_length=1)
    canonical_producer_ref: Literal[
        "polisyos.scientist.nodes.builtins.decide.decision_packet.builder."
        "BuildDecisionPacketNode.execute"
    ]
    epoch_manifest_ref: ArtifactRef
    recipe: DerivationRecipeBinding | None = None
    input_certificate_refs: tuple[ArtifactRef, ...] = Field(min_length=1)
    native_coordinate_refs: tuple[str, ...] = Field(min_length=1)
    rule_schema_profile_refs: tuple[str, ...] = Field(min_length=1)
    requested_query_context_ref: str = Field(pattern=_DIGEST)
    authority_purpose: Literal["decision_validity_epoch_transition"]
    admission_evidence_ref: ArtifactRef
    verifier_provenance_ref: ArtifactRef


class AdmittedDecisionPacketExecutionClosure(_StrictModel):
    """Exact result of the configured complete execution-source admission owner.

    The resolver must reconcile its admitted source denominator with this exact
    invocation, including code, tools and an independently admitted environment.
    It must return its owned admitted statement on readback. Neither the literal
    predicate label nor CAS presence establishes those premises. Native Foundry
    reconstruction/cutoff refusals retain their original purpose and cannot be
    relabelled as a positive closure here.
    """

    invocation_ref: ArtifactRef
    invocation_content_hash: str = Field(pattern=_DIGEST)
    epoch_manifest_ref: ArtifactRef
    authority_purpose: Literal["decision_validity_epoch_transition"]
    requested_query_context_ref: str = Field(pattern=_DIGEST)
    input_certificate_refs: tuple[ArtifactRef, ...] = Field(min_length=1)
    code_source_refs: tuple[ArtifactRef, ...] = Field(min_length=1)
    tool_source_refs: tuple[ArtifactRef, ...]
    environment_manifest_ref: ArtifactRef
    environment_profile_ref: ArtifactRef
    admission_evidence_ref: ArtifactRef
    verifier_provenance_ref: ArtifactRef
    predicate_class: Literal["independently_reconciled"] = "independently_reconciled"


class _InvocationRecipe(_StrictModel):
    """Canonical producer invocation binding, with no recipe execution API."""

    canonical_producer_ref: Literal[
        "polisyos.scientist.nodes.builtins.decide.decision_packet.builder."
        "BuildDecisionPacketNode.execute"
    ] = _PRODUCER
    invocation_ref: ArtifactRef
    admitted_closure: AdmittedDecisionPacketExecutionClosure
    input_certificate_refs: tuple[ArtifactRef, ...]


class EpochCertificateIssuanceInputResolver(Protocol):
    """Independently reconcile native inputs and the complete execution closure.

    A production implementation must verify source admission, exact producer/run
    applicability, the complete input-certificate denominator and profile/native
    coordinate semantics. Returning content-shaped fields is insufficient. No
    implementation is selected by this module or by HTTP/state parameters.
    """

    verifier_provenance_ref: ArtifactRef | None

    def resolve_verified_inputs(
        self,
        *,
        run_id: str,
        canonical_producer_ref: str,
        invocation_input_refs: tuple[ArtifactRef, ...],
    ) -> EpochCertificateIssuanceInputs | EpochCertificateIssuanceNonReceipt:
        """Return independently admitted inputs or a typed refusal."""
        ...

    def resolve_admitted_execution_closure(
        self,
        *,
        invocation_ref: ArtifactRef,
        invocation_content_hash: str,
    ) -> AdmittedDecisionPacketExecutionClosure | EpochCertificateIssuanceNonReceipt:
        """Resolve and independently read back the owned admitted complete closure."""
        ...


class NoEpochCertificateIssuanceInputResolver:
    """Preserve absence until native inputs and admitted execution sources are configured."""

    verifier_provenance_ref: ArtifactRef | None = None

    def resolve_verified_inputs(
        self,
        *,
        run_id: str,
        canonical_producer_ref: str,
        invocation_input_refs: tuple[ArtifactRef, ...],
    ) -> EpochCertificateIssuanceNonReceipt:
        """Decline without reading or fabricating any source artifact."""

        del run_id, canonical_producer_ref, invocation_input_refs
        return EpochCertificateIssuanceNonReceipt()

    def resolve_admitted_execution_closure(
        self,
        *,
        invocation_ref: ArtifactRef,
        invocation_content_hash: str,
    ) -> EpochCertificateIssuanceNonReceipt:
        """Preserve absence of an independently admitted environment/code/tool closure."""

        del invocation_ref, invocation_content_hash
        return EpochCertificateIssuanceNonReceipt(
            code="epoch_certificate_execution_closure_not_established"
        )


class _IssuanceBasis(_StrictModel):
    inputs: EpochCertificateIssuanceInputs
    invocation_input_refs: tuple[ArtifactRef, ...]
    invocation_ref: ArtifactRef
    execution_closure: AdmittedDecisionPacketExecutionClosure
    execution_recipe: DerivationRecipeBinding
    complete_input_certificate_refs: tuple[ArtifactRef, ...]
    epoch_history_snapshot_ref: ArtifactRef
    epoch_history_snapshot_content_hash: str = Field(pattern=_DIGEST)


class _IssuanceReceipt(_StrictModel):
    preparation: PersistedEpochCertificateIssuancePreparation
    epoch_manifest_ref: ArtifactRef
    binding: EpochCertificateBinding


class PersistedEpochCertificateIssuance(_IssuanceReceipt):
    """Exact admitted emission record and existing certificate binding."""

    issuance_receipt_ref: ArtifactRef


class DecisionPacketEpochIssuanceOwner:
    """Prepare exact inputs, finalize actual emission, and enumerate admitted rows."""

    def __init__(
        self,
        *,
        store: artifacts.ArtifactStore,
        root: Path,
        history: SemanticEpochHistoryRepository | None = None,
        input_resolver: EpochCertificateIssuanceInputResolver | None = None,
    ) -> None:
        self.store = store
        self._root = Path(root)
        self._history = history
        self._input_resolver = input_resolver or NoEpochCertificateIssuanceInputResolver()

    def _scope_root(self) -> Path:
        scope = security.get_current_access_scope_or_none()
        tenant_id = (
            scope.tenant_id if scope is not None else security.get_current_tenant_id_or_none()
        )
        if tenant_id is None:
            return self._root
        cell_id = scope.cell_id if scope is not None else security.get_current_cell_id()
        namespace = hashlib.sha256(
            canon.to_canonical_bytes({"tenant_id": tenant_id, "cell_id": cell_id}, _CANON)
        ).hexdigest()
        return self._root / "tenant-scopes" / namespace

    @property
    def _index(self) -> Path:
        return self._scope_root() / "epoch-certificate-issuances.jsonl"

    @classmethod
    def for_store(
        cls,
        *,
        store: artifacts.ArtifactStore,
        history: SemanticEpochHistoryRepository | None = None,
        input_resolver: EpochCertificateIssuanceInputResolver | None = None,
    ) -> DecisionPacketEpochIssuanceOwner:
        """Compose the shared durable owner at the canonical artifact-store root."""

        root = getattr(store, "root", None)
        if not isinstance(root, (str, Path)):
            raise ValueError("epoch_certificate_issuance_owner_root_unresolved")
        return cls(
            store=store,
            root=Path(root) / "epoch-certificate-issuance",
            history=history,
            input_resolver=input_resolver,
        )

    def _read_exact(self, ref: ArtifactRef) -> bytes:
        try:
            raw = self.store.get_bytes(ref.artifact_id)
            manifest = self.store.get_manifest(ref.artifact_id)
            if (
                not self.store.verify(ref.artifact_id).ok
                or _raw_hash(raw) != str(ref.artifact_id)
                or ArtifactRef(
                    artifact_id=manifest.artifact_id,
                    kind=manifest.kind,
                    media_type=manifest.media_type,
                )
                != ref
            ):
                raise ValueError("exact evidence mismatch")
            return raw
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            raise ValueError("epoch_certificate_issuance_evidence_unresolved") from exc

    def _read_model(self, ref: ArtifactRef, model: type[_Model], kind: str) -> _Model:
        raw = self._read_exact(ref)
        manifest = self.store.get_manifest(ref.artifact_id)
        if (
            ref.kind != kind
            or ref.media_type != "application/json"
            or manifest.artifact_schema != artifacts.SchemaInfo(name=kind, version="1.0")
            or manifest.canon != artifacts.CanonInfo.from_spec(_CANON)
        ):
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        value = model.model_validate(canon.from_canonical_bytes(raw))
        if canon.to_canonical_bytes(value.model_dump(mode="json"), _CANON) != raw:
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        return value

    def _persist(
        self, value: BaseModel, kind: str, *, input_refs: tuple[ArtifactRef, ...]
    ) -> ArtifactRef:
        raw = canon.to_canonical_bytes(value.model_dump(mode="json"), _CANON)
        ref = self.store.put_bytes(
            raw,
            artifacts.ArtifactWriteOptions(
                kind=kind,
                media_type="application/json",
                schema=artifacts.SchemaInfo(name=kind, version="1.0"),
                canon=artifacts.CanonInfo.from_spec(_CANON),
                inputs=[
                    artifacts.InputRef(artifact_id=ref.artifact_id, role=f"source[{index}]")
                    for index, ref in enumerate(_canonical_refs(input_refs))
                ],
            ),
        )
        if self._read_model(ref, type(value), kind) != value:
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        return ref

    def _read_epoch(self, ref: ArtifactRef) -> SemanticEpochManifest:
        raw = self._read_exact(ref)
        if (
            ref.kind != "epoch.semantic_manifest"
            or ref.media_type != "application/vnd.polisyos.epoch+json"
        ):
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        records = contracts.chronology._split_framed_records(raw)
        if len(records) != 1:
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        epoch = SemanticEpochManifest.model_validate(canon.from_canonical_bytes(records[0]))
        if contracts.chronology._frame_record(contracts.epoch.canonical_epoch_bytes(epoch)) != raw:
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        return epoch

    def _read_basis(
        self, preparation: PersistedEpochCertificateIssuancePreparation
    ) -> _IssuanceBasis:
        basis = self._read_model(preparation.issuance_basis_ref, _IssuanceBasis, _BASIS_KIND)
        if preparation.issuance_basis_content_hash != str(
            preparation.issuance_basis_ref.artifact_id
        ):
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        self._validate_basis(basis)
        return basis

    def _read_issuance_history(
        self, *, ref: ArtifactRef, content_hash: str, epoch: SemanticEpochManifest
    ) -> EpochScopeHistory:
        raw = self._read_exact(ref)
        if (
            ref.kind != "epoch.scope_history"
            or ref.media_type != "application/vnd.polisyos.epoch+json"
            or _raw_hash(raw) != content_hash
        ):
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        records = contracts.chronology._split_framed_records(raw)
        if len(records) != 1:
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        statement = canon.from_canonical_bytes(records[0])
        if (
            not isinstance(statement, dict)
            or statement.get("schema_version") != "polisyos.epoch.scope-history.v1"
            or contracts.chronology._frame_record(contracts.epoch.canonical_epoch_bytes(statement))
            != raw
        ):
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        values = dict(statement)
        values.pop("schema_version")
        history = EpochScopeHistory.model_validate(
            {
                **values,
                "history_snapshot_ref": ref,
                "history_snapshot_content_hash": content_hash,
                "predicate_class": "recomputed",
            }
        )
        if set(values) != {"scope", "authority_purpose", "entries", "head_refs"}:
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        rows = tuple(row for row in history.entries if row.epoch_ref == epoch.epoch_ref)
        if (
            history.scope != epoch.scope_identity
            or history.authority_purpose != epoch.authority_purpose
            or history.head_refs != (epoch.epoch_ref,)
            or len(rows) != 1
            or rows[0].manifest_content_hash != epoch.manifest_content_hash
            or self._read_epoch(rows[0].manifest_ref) != epoch
        ):
            raise ValueError("epoch_certificate_issuance_epoch_not_current")
        return history

    def _read_invocation(self, ref: ArtifactRef, *, run_id: str) -> DecisionPacketInvocationRecord:
        record = self._read_model(
            ref, DecisionPacketInvocationRecord, DECISION_PACKET_INVOCATION_KIND
        )
        values = []
        for part_ref, kind in (
            (record.state_ref, "scientist.decision_packet_invoked_state"),
            (record.run_manifest_ref, "scientist.decision_packet_invoked_run"),
            (record.node_spec_ref, "scientist.decision_packet_invoked_spec"),
        ):
            raw = self._read_exact(part_ref)
            value = canon.from_canonical_bytes(raw)
            manifest = self.store.get_manifest(part_ref.artifact_id)
            profile = canon.CanonSpec(forbid_floats=False)
            if (
                part_ref.kind != kind
                or part_ref.media_type != "application/json"
                or manifest.artifact_schema != artifacts.SchemaInfo(name=kind, version="1.0")
                or manifest.canon != artifacts.CanonInfo.from_spec(profile)
                or canon.to_canonical_bytes(value, profile) != raw
            ):
                raise ValueError("epoch_certificate_issuance_evidence_unresolved")
            values.append(value)
        if values[0].get("run_id") != run_id or values[1].get("run_id") != run_id:
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        if decision_packet_invocation_input_refs(*values) != record.input_refs:
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        self._read_exact(record.implementation_ref)
        self._read_exact(record.loaded_code_ref)
        for source in record.input_refs:
            self._read_exact(source)
        return record

    def _complete_recipe_inputs(
        self,
        *,
        record: DecisionPacketInvocationRecord,
        closure: AdmittedDecisionPacketExecutionClosure,
    ) -> tuple[ArtifactRef, ...]:
        if (
            closure.invocation_content_hash != str(closure.invocation_ref.artifact_id)
            or closure.input_certificate_refs != _canonical_refs(closure.input_certificate_refs)
            or not {_identity(ref) for ref in record.input_refs}.issubset(
                _identity(ref) for ref in closure.input_certificate_refs
            )
            or record.implementation_ref not in closure.code_source_refs
            or record.loaded_code_ref not in closure.code_source_refs
        ):
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        refs = _canonical_refs(
            (
                *closure.input_certificate_refs,
                *closure.code_source_refs,
                *closure.tool_source_refs,
                closure.environment_manifest_ref,
                closure.environment_profile_ref,
                closure.admission_evidence_ref,
                closure.verifier_provenance_ref,
                record.state_ref,
                record.run_manifest_ref,
                record.node_spec_ref,
            )
        )
        for ref in refs:
            self._read_exact(ref)
        return refs

    def _validate_basis(self, basis: _IssuanceBasis) -> None:
        inputs = basis.inputs
        if (
            inputs.canonical_producer_ref != _PRODUCER
            or basis.invocation_input_refs != _canonical_refs(basis.invocation_input_refs)
            or inputs.input_certificate_refs != basis.invocation_input_refs
        ):
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        for ref in (
            *inputs.input_certificate_refs,
            inputs.admission_evidence_ref,
            inputs.verifier_provenance_ref,
        ):
            self._read_exact(ref)
        if inputs.recipe is not None and (
            _raw_hash(self._read_exact(inputs.recipe.recipe_ref))
            != inputs.recipe.recipe_content_hash
        ):
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        record = self._read_invocation(basis.invocation_ref, run_id=inputs.run_id)
        closure = basis.execution_closure
        if (
            closure.epoch_manifest_ref != inputs.epoch_manifest_ref
            or closure.authority_purpose != inputs.authority_purpose
            or closure.requested_query_context_ref != inputs.requested_query_context_ref
        ):
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        complete_refs = self._complete_recipe_inputs(record=record, closure=closure)
        expected_recipe = _InvocationRecipe(
            invocation_ref=basis.invocation_ref,
            admitted_closure=closure,
            input_certificate_refs=complete_refs,
        )
        recipe = self._read_model(
            basis.execution_recipe.recipe_ref,
            _InvocationRecipe,
            "scientist.decision_packet_invocation_recipe",
        )
        if (
            record.input_refs != basis.invocation_input_refs
            or closure.invocation_ref != basis.invocation_ref
            or complete_refs != basis.complete_input_certificate_refs
            or recipe != expected_recipe
            or basis.execution_recipe.recipe_content_hash
            != str(basis.execution_recipe.recipe_ref.artifact_id)
            or basis.execution_recipe.recipe_schema_profile_ref
            != _raw_hash(b"scientist.decision_packet_invocation_recipe.v1")
            or basis.execution_recipe.input_roles
            != tuple(f"execution.source[{i}]" for i in range(len(complete_refs)))
        ):
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        epoch = self._read_epoch(inputs.epoch_manifest_ref)
        if (
            epoch.authority_purpose != inputs.authority_purpose
            or epoch.requested_query_context_ref != inputs.requested_query_context_ref
        ):
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        history = self._read_issuance_history(
            ref=basis.epoch_history_snapshot_ref,
            content_hash=basis.epoch_history_snapshot_content_hash,
            epoch=epoch,
        )
        if not any(row.manifest_ref == inputs.epoch_manifest_ref for row in history.entries):
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")

    def prepare(
        self,
        *,
        run_id: str,
        invocation_input_refs: tuple[ArtifactRef, ...],
        invocation: CanonicalDecisionPacketInvocation | None = None,
    ) -> PersistedEpochCertificateIssuancePreparation | EpochCertificateIssuanceNonReceipt:
        """Resolve admitted source inputs before any epoch dependency is emitted."""

        if self._input_resolver.verifier_provenance_ref is None:
            return EpochCertificateIssuanceNonReceipt()
        refs = _canonical_refs(invocation_input_refs)
        record = None
        if invocation is not None:
            require_canonical_decision_packet_invocation(invocation)
            record = self._read_invocation(invocation.invocation_ref, run_id=run_id)
            if not {_identity(ref) for ref in refs}.issubset(
                _identity(ref) for ref in record.input_refs
            ):
                raise ValueError("epoch_certificate_issuance_evidence_unresolved")
            refs = record.input_refs
        resolved = self._input_resolver.resolve_verified_inputs(
            run_id=run_id, canonical_producer_ref=_PRODUCER, invocation_input_refs=refs
        )
        if isinstance(resolved, EpochCertificateIssuanceNonReceipt):
            return resolved
        if type(resolved) is not EpochCertificateIssuanceInputs:
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        inputs = EpochCertificateIssuanceInputs.model_validate(resolved.model_dump(mode="json"))
        if (
            inputs.run_id != run_id
            or inputs.canonical_producer_ref != _PRODUCER
            or self._input_resolver.verifier_provenance_ref is None
            or inputs.verifier_provenance_ref != self._input_resolver.verifier_provenance_ref
            or inputs.input_certificate_refs != refs
        ):
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        if (
            inputs.recipe is not None
            and _raw_hash(self._read_exact(inputs.recipe.recipe_ref))
            != inputs.recipe.recipe_content_hash
        ):
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        if self._history is None:
            return EpochCertificateIssuanceNonReceipt(
                code="epoch_certificate_epoch_owner_not_established"
            )
        epoch = self._read_epoch(inputs.epoch_manifest_ref)
        history = self._history.resolve_scope_history(
            scope=epoch.scope_identity, authority_purpose=inputs.authority_purpose
        )
        if (
            self._read_issuance_history(
                ref=history.history_snapshot_ref,
                content_hash=history.history_snapshot_content_hash,
                epoch=epoch,
            )
            != history
        ):
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        if invocation is None or record is None:
            return EpochCertificateIssuanceNonReceipt(
                code="epoch_certificate_canonical_invocation_not_established"
            )
        resolve_closure = getattr(self._input_resolver, "resolve_admitted_execution_closure", None)
        if not callable(resolve_closure):
            return EpochCertificateIssuanceNonReceipt(
                code="epoch_certificate_execution_closure_not_established"
            )
        closure = resolve_closure(
            invocation_ref=invocation.invocation_ref,
            invocation_content_hash=str(invocation.invocation_ref.artifact_id),
        )
        if isinstance(closure, EpochCertificateIssuanceNonReceipt):
            return closure
        if type(closure) is not AdmittedDecisionPacketExecutionClosure:
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        if (
            closure.invocation_ref != invocation.invocation_ref
            or closure.epoch_manifest_ref != inputs.epoch_manifest_ref
            or closure.authority_purpose != inputs.authority_purpose
            or closure.requested_query_context_ref != inputs.requested_query_context_ref
            or closure.verifier_provenance_ref != self._input_resolver.verifier_provenance_ref
            or resolve_closure(
                invocation_ref=invocation.invocation_ref,
                invocation_content_hash=str(invocation.invocation_ref.artifact_id),
            )
            != closure
        ):
            raise ValueError("epoch_certificate_execution_closure_admission_unresolved")
        complete_refs = self._complete_recipe_inputs(record=record, closure=closure)
        recipe_value = _InvocationRecipe(
            invocation_ref=invocation.invocation_ref,
            admitted_closure=closure,
            input_certificate_refs=complete_refs,
        )
        recipe_ref = self._persist(
            recipe_value,
            "scientist.decision_packet_invocation_recipe",
            input_refs=(*complete_refs, invocation.invocation_ref),
        )
        recipe = DerivationRecipeBinding(
            recipe_ref=recipe_ref,
            recipe_content_hash=str(recipe_ref.artifact_id),
            recipe_schema_profile_ref=_raw_hash(b"scientist.decision_packet_invocation_recipe.v1"),
            input_roles=tuple(f"execution.source[{i}]" for i in range(len(complete_refs))),
        )
        basis = _IssuanceBasis(
            inputs=inputs,
            invocation_input_refs=refs,
            invocation_ref=invocation.invocation_ref,
            execution_closure=closure,
            execution_recipe=recipe,
            complete_input_certificate_refs=complete_refs,
            epoch_history_snapshot_ref=history.history_snapshot_ref,
            epoch_history_snapshot_content_hash=history.history_snapshot_content_hash,
        )
        self._validate_basis(basis)
        ref = self._persist(
            basis,
            _BASIS_KIND,
            input_refs=(
                *refs,
                inputs.epoch_manifest_ref,
                *((inputs.recipe.recipe_ref,) if inputs.recipe is not None else ()),
                recipe_ref,
                invocation.invocation_ref,
                *complete_refs,
                inputs.admission_evidence_ref,
                inputs.verifier_provenance_ref,
                history.history_snapshot_ref,
            ),
        )
        preparation = PersistedEpochCertificateIssuancePreparation(
            issuance_basis_ref=ref, issuance_basis_content_hash=str(ref.artifact_id)
        )
        self._read_basis(preparation)
        return preparation

    def bind_envelope(
        self,
        *,
        preparation: PersistedEpochCertificateIssuancePreparation,
        envelope: DecisionValidityEnvelope,
    ) -> DecisionValidityEnvelope:
        """Bind the immutable issuance basis through the existing semantic-epoch kind."""

        basis = self._read_basis(preparation)
        ref = preparation.issuance_basis_ref
        key = "semantic_epoch:" + str(ref.artifact_id)
        dependency = DecisionDependencyRef(
            key=key,
            kind=DecisionDependencyKind.SEMANTIC_EPOCH,
            artifact_id=str(ref.artifact_id),
            label="epoch_certificate_issuance_basis",
        )
        values = envelope.model_dump(mode="json")
        values["data_basis"]["dependencies"].append(dependency.model_dump(mode="json"))
        values["data_basis"]["summary"]["epoch_certificate_issuance"] = {
            "status": "prepared",
            "issuance_basis_ref": ref.model_dump(mode="json"),
            "input_certificate_refs": [
                item.model_dump(mode="json") for item in basis.complete_input_certificate_refs
            ],
        }
        values["watched_triggers"].append(
            DecisionTriggerSpec(
                trigger_type=DecisionTriggerType.HISTORICAL_SEMANTIC_REVISION, dependency_keys=[key]
            ).model_dump(mode="json")
        )
        return DecisionValidityEnvelope.model_validate(values)

    def _read_packet_binding(
        self,
        *,
        packet_ref: ArtifactRef,
        preparation: PersistedEpochCertificateIssuancePreparation,
        basis: _IssuanceBasis,
    ) -> EpochCertificateBinding:
        packet_raw = self._read_exact(packet_ref)
        if packet_ref.kind != "scientist.decision_packet":
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        packet = canon.from_canonical_bytes(packet_raw)
        envelope = DecisionValidityEnvelope.model_validate(packet["decision_validity_envelope"])
        dependency_id = str(preparation.issuance_basis_ref.artifact_id)
        selected = tuple(
            row
            for row in envelope.data_basis.dependencies
            if row.kind is DecisionDependencyKind.SEMANTIC_EPOCH
            and row.artifact_id == dependency_id
        )
        if (
            packet.get("run_id") != basis.inputs.run_id
            or len(selected) != 1
            or selected[0].key != "semantic_epoch:" + dependency_id
        ):
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        input_ids = {
            str(row.artifact_id) for row in self.store.get_manifest(packet_ref.artifact_id).inputs
        }
        if not {str(ref.artifact_id) for ref in basis.complete_input_certificate_refs}.issubset(
            input_ids
        ):
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        epoch = self._read_epoch(basis.inputs.epoch_manifest_ref)
        return bind_certificate_to_epoch(
            certificate_ref=packet_ref,
            certificate_content_hash=_raw_hash(packet_raw),
            epoch=epoch,
            input_certificate_refs=basis.complete_input_certificate_refs,
            recipe=basis.execution_recipe,
            canonical_producer_ref=_PRODUCER,
            authority_purpose=basis.inputs.authority_purpose,
            native_coordinate_refs=basis.inputs.native_coordinate_refs,
            rule_schema_profile_refs=basis.inputs.rule_schema_profile_refs,
        )

    def finalize(self, *, execution: CompletedDecisionPacketExecution) -> ArtifactRef:
        """Admit an emission only with the canonical node's internal completion ticket."""

        require_canonical_decision_packet_execution(execution)
        basis = self._read_basis(execution.preparation)
        binding = self._read_packet_binding(
            packet_ref=execution.decision_packet_ref,
            preparation=execution.preparation,
            basis=basis,
        )
        receipt = _IssuanceReceipt(
            preparation=execution.preparation,
            epoch_manifest_ref=basis.inputs.epoch_manifest_ref,
            binding=binding,
        )
        ref = self._persist(
            receipt,
            _RECEIPT_KIND,
            input_refs=(
                execution.preparation.issuance_basis_ref,
                execution.decision_packet_ref,
                basis.inputs.epoch_manifest_ref,
            ),
        )
        root = self._scope_root()
        root.mkdir(parents=True, exist_ok=True)
        with (root / "epoch-certificate-issuances.lock").open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            existing = self._index_refs()
            if ref not in existing:
                with self._index.open("ab") as output:
                    output.write(
                        canon.to_canonical_bytes(ref.model_dump(mode="json"), _CANON) + b"\n"
                    )
                    output.flush()
                    os.fsync(output.fileno())
        return self._read_issuance(ref).issuance_receipt_ref

    def _index_refs(self) -> tuple[ArtifactRef, ...]:
        if not self._index.exists():
            return ()
        try:
            refs = tuple(
                ArtifactRef.model_validate(json.loads(line))
                for line in self._index.read_bytes().splitlines()
            )
            if len({_identity(ref) for ref in refs}) != len(refs):
                raise ValueError("duplicate owner row")
            return refs
        except (OSError, TypeError, ValueError) as exc:
            raise ValueError("epoch_certificate_issuance_owner_unresolved") from exc

    def _read_issuance(self, ref: ArtifactRef) -> PersistedEpochCertificateIssuance:
        receipt = self._read_model(ref, _IssuanceReceipt, _RECEIPT_KIND)
        basis = self._read_basis(receipt.preparation)
        expected = self._read_packet_binding(
            packet_ref=receipt.binding.certificate_ref,
            preparation=receipt.preparation,
            basis=basis,
        )
        if (
            expected != receipt.binding
            or receipt.epoch_manifest_ref != basis.inputs.epoch_manifest_ref
        ):
            raise ValueError("epoch_certificate_issuance_evidence_unresolved")
        return PersistedEpochCertificateIssuance(**receipt.model_dump(), issuance_receipt_ref=ref)

    def enumerate_registered_issuances(self) -> tuple[PersistedEpochCertificateIssuance, ...]:
        """Read the complete owner-admitted index; CAS membership alone admits nothing."""

        root = self._scope_root()
        if not root.exists():
            return ()
        with (root / "epoch-certificate-issuances.lock").open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_SH)
            return tuple(
                self._read_issuance(ref) for ref in sorted(self._index_refs(), key=_identity)
            )

    def resolve_complete_epoch_dependencies(
        self, *, previous_epoch_ref: str, authority_purpose: str
    ) -> EpochDependencyDenominatorReceipt:
        """Derive old-epoch dependencies without confusing issuance and transition queries."""

        rows = tuple(
            row
            for row in self.enumerate_registered_issuances()
            if row.binding.epoch_ref == previous_epoch_ref
            and row.binding.authority_purpose == authority_purpose
        )
        if not rows:
            raise ValueError("dependency_denominator_unresolved")
        bindings = tuple(
            sorted((row.binding for row in rows), key=lambda row: _identity(row.certificate_ref))
        )
        edge_map = {}
        for row in rows:
            edge = EpochDependencyEdge(
                source_ref=row.epoch_manifest_ref,
                target_ref=row.preparation.issuance_basis_ref,
                relation="invalidates_issuance_basis",
                authority_purpose=authority_purpose,
            )
            edge_map[(_identity(edge.source_ref), _identity(edge.target_ref))] = edge
        edges = tuple(edge_map[key] for key in sorted(edge_map))
        graph_raw = canon.to_canonical_bytes(
            {"edges": [edge.model_dump(mode="json") for edge in edges]}, _CANON
        )
        graph = EpochDependencyGraph(
            edges=edges,
            denominator_ref=_raw_hash(b"polisyos.epoch.dependency-graph.v1\0" + graph_raw),
        )
        return EpochDependencyDenominatorReceipt(
            denominator_ref=epoch_dependency_outer_denominator_ref(
                certificate_bindings=bindings, dependency_graph=graph
            ),
            certificate_bindings=bindings,
            dependency_graph=graph,
            target_refs=_canonical_refs(tuple(row.preparation.issuance_basis_ref for row in rows)),
            predicate_class="independently_reconciled",
        )
