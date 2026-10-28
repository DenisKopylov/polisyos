"""Execute compiled Foundry plans from bound runtime state snapshots.

`execute()` is the public runtime entrypoint paired with
`polisyos.foundry.compile.api.compile`. It resolves
`FoundryInputBindingsRef -> StateSnapshotRef`, replays the persisted
`ExecPlan` deterministically with the requested seed, and writes
`foundry.simulation_result` plus runtime-derived artifacts back to CAS.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, Protocol, TypeVar, cast

import numpy as np
from pydantic import BaseModel

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import (
    RegistryBundlePayload,
    artifact_manifest_profile_sha256,
    ensure_ir_artifact_store,
    resolve_manifest_by_profile,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts import (
    require_return_selected_profile_writer as _require_return_selected_profile_writer,
)
from polisyos.core.artifacts.manifest import (
    ArtifactManifest,
    ArtifactRef,
    InputRef,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.protocol import ArtifactStore, CoreJSONArtifactStore
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts import DataSnapshot, data_snapshot_owner_input_requirements
from polisyos.core.contracts.decision_validity import RegisteredSQLAdmissionBinding
from polisyos.core.contracts.foundry import (
    DerivedArtifact,
    EquilibriumMultiplicityReport,
    EquilibriumMultiplicityReportRef,
    ExecPlan,
    ExecuteRequest,
    ExecuteResult,
    FeedbackConfig,
    FeedbackConvergenceCertificate,
    FeedbackConvergenceCertificateRef,
    FeedbackFixedPointCandidate,
    FeedbackIterationRecord,
    FeedbackJacobianDiagnostics,
    FeedbackJacobianDiagnosticsRef,
    FeedbackResultRef,
    FeedbackSolveResult,
    FeedbackStateSnapshot,
    FeedbackTrace,
    FeedbackTraceRef,
    FoundryExecConfig,
    FoundryExecutionInputBasis,
    FoundryExecutionInputBasisRef,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    Metrics,
    MetricsRef,
    ParameterOverrideBundle,
    ParameterOverrideBundleRef,
    ProgramGraph,
    SimulationResult,
    SimulationResultRef,
    StateDelta,
    StateSnapshotRef,
    WelfareBoundReportRef,
)
from polisyos.core.contracts.uncertainty import UncertaintyEnvelopeRef
from polisyos.core.registry import (
    RegistryBundleContent,
    load_registry_bundle_content,
    load_registry_bundle_payload,
)
from polisyos.foundry._artifact_capabilities import resolve_core_json_profile_store
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.data_plane import (
    extract_feedback_diagnostics,
    extract_feedback_state,
    inject_feedback_state,
    load_input_bindings,
)
from polisyos.foundry.execute._internal.posture import (
    ResolvedExecutionPosture,
    resolve_execution_posture,
)
from polisyos.foundry.execute.executor import (
    ExecuteArtifacts,
    MethodExecutionCapture,
    apply_state_delta,
    apply_state_delta_and_snapshot,
    execute_program_graph,
    load_state_snapshot,
    new_method_execution_capture,
    persist_method_execution_capture,
    put_state_snapshot,
)
from polisyos.foundry.feedback import (
    AlternativeSolution,
    MapEvaluation,
    PreparedFeedbackConfig,
    SolveOutcome,
    discover_equilibria,
    prepare_feedback_config,
    snapshot_from_vector,
    solve_fixed_point,
)
from polisyos.foundry.methods.catalog.mechanism.runtime_registry import (
    MissingRuntimeMechanismSupportError,
)
from polisyos.foundry.methods.exceptions import MethodExecutionAbortError
from polisyos.ir import TrinityBundle
from polisyos.ir.trinity import load_trinity_bundle_artifact

_ModelT = TypeVar("_ModelT", bound=BaseModel)


@dataclass(frozen=True)
class _ResolvedStateSource:
    """Internal bundle describing where the execution base state came from."""

    state_snapshot_ref: StateSnapshotRef
    notes: tuple[str, ...]
    input_refs: tuple[InputRef, ...]


@dataclass(frozen=True)
class _FeedbackExecutionEvaluation:
    """Internal one-shot execution result used by the outer feedback solver."""

    map_evaluation: MapEvaluation
    final_state: GlobalState


ExecutionSourceMode = Literal["legacy_profileless", "single_step_basis", "feedback_uncomposed"]


@dataclass(frozen=True)
class ExecutionSourceAdmission:
    """Source mode and exact owner artifacts recomputed from the selected CAS view.

    The frozen dataclass and tuple inventory prevent top-level reassignment. The
    contained Pydantic models retain their existing mutability contract.
    """

    mode: ExecutionSourceMode
    simulation_result_ref: SimulationResultRef
    simulation_result: SimulationResult
    simulation_manifest: ArtifactManifest
    basis_ref: FoundryExecutionInputBasisRef | None = None
    basis: FoundryExecutionInputBasis | None = None
    basis_manifest: ArtifactManifest | None = None
    basis_inventory: tuple[InputRef, ...] | None = None
    source_read_bytes: int | None = None


class ExecutionSourceAdmissionRefusal(ValueError):
    """A source-admission refusal carrying the unchanged owner reason string."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class ExecutionSourceBoundedReadRefusal(ExecutionSourceAdmissionRefusal):
    """A source admission stopped because its shared byte budget was exhausted."""

    def __init__(
        self,
        reason: str,
        *,
        observed_bytes: int,
        limit_bytes: int,
    ) -> None:
        if type(observed_bytes) is not int or observed_bytes < 0:
            raise ValueError("execution_source_bounded_read_observed_bytes_invalid")
        if type(limit_bytes) is not int or limit_bytes < 0:
            raise ValueError("execution_source_bounded_read_limit_bytes_invalid")
        self.observed_bytes = observed_bytes
        self.limit_bytes = limit_bytes
        super().__init__(reason)


class BoundedExecutionSourceReader(Protocol):
    """Read source artifacts through a shared, aggregate-bounded Core reader.

    Every method must resolve the exact selected profile, verify the selected
    manifest and payload integrity, and charge all bytes actually read to the
    same server-owned budget. ``read_typed_model`` must use the normal strict
    Core schema/profile validation path. A budget refusal must raise
    ``ExecutionSourceBoundedReadRefusal``; this protocol has no unbounded
    fallback.
    """

    def read_selected_manifest(self, ref: ArtifactRef) -> tuple[ArtifactManifest, int]:
        """Read and verify one exact selected-profile artifact view."""
        ...

    def read_edge_manifest(
        self,
        parent_ref: ArtifactRef,
        edge: InputRef,
    ) -> tuple[ArtifactRef, ArtifactManifest, int]:
        """Resolve one exact edge while preserving its selected direct parent."""
        ...

    def read_typed_model(
        self,
        model: type[BaseModel],
        ref: ArtifactRef,
    ) -> tuple[ArtifactManifest, BaseModel, int, int]:
        """Read a strict Core model and report observed manifest/payload bytes."""
        ...


@dataclass
class _BoundedExecutionSourceReadSession:
    """Track actual reads while reusing one caller-owned bounded reader."""

    reader: BoundedExecutionSourceReader
    observed_bytes: int = 0

    def add(self, count: int) -> None:
        if type(count) is not int or count < 0:
            raise TypeError("execution_source_reader_observed_bytes_invalid")
        self.observed_bytes += count

    def selected_manifest(self, ref: ArtifactRef) -> ArtifactManifest:
        manifest, observed_bytes = self.reader.read_selected_manifest(ref)
        self.add(observed_bytes)
        _require_selected_manifest_identity(manifest, ref)
        return manifest

    def edge_ref_and_manifest(
        self,
        parent_ref: ArtifactRef,
        edge: InputRef,
    ) -> tuple[ArtifactRef, ArtifactManifest]:
        """Resolve one edge with its selected parent context intact."""
        ref, manifest, observed_bytes = self.reader.read_edge_manifest(parent_ref, edge)
        self.add(observed_bytes)
        if (
            edge.manifest_profile_sha256 is None
            or ref.artifact_id != edge.artifact_id
            or ref.manifest_profile_sha256 != edge.manifest_profile_sha256
            or manifest.artifact_id != ref.artifact_id
            or manifest.kind != ref.kind
            or manifest.media_type != ref.media_type
            or artifact_manifest_profile_sha256(manifest) != edge.manifest_profile_sha256
        ):
            raise ValueError("execution_source_edge_profile_identity_mismatch")
        return ref, manifest

    def typed_model(self, model: type[_ModelT], ref: ArtifactRef) -> _ModelT:
        manifest, value, manifest_bytes, payload_bytes = self.reader.read_typed_model(model, ref)
        self.add(manifest_bytes)
        self.add(payload_bytes)
        _require_selected_manifest_identity(manifest, ref)
        if not isinstance(value, model):
            raise TypeError("execution_source_reader_typed_model_contract_mismatch")
        return cast("_ModelT", value)


def _method_execution_abort_result(
    store: ArtifactStore,
    *,
    capture: MethodExecutionCapture | None,
    error: MethodExecutionAbortError,
    notes: list[str] | None = None,
) -> ExecuteResult:
    """Surface a strict graph failure and its persisted capture without success aliasing."""
    bundle_ref = getattr(error, "method_execution_bundle_ref", None)
    if bundle_ref is None and capture is not None:
        bundle_ref = capture.method_execution_bundle_ref
    derived_refs = _persisted_method_metric_capture_refs(store, capture)
    return ExecuteResult(
        schema_version="1.1" if bundle_ref is not None else "1.0",
        ok=False,
        simulation_result_ref=None,
        method_execution_bundle_ref=bundle_ref,
        derived_refs=derived_refs,
        notes=[
            *(notes or []),
            "method_execution_aborted",
            f"method_execution_failure_type:{type(error).__module__}.{type(error).__qualname__}",
        ],
    )


def _require_selected_manifest_identity(manifest: ArtifactManifest, ref: ArtifactRef) -> None:
    """Require a returned manifest to match a complete selected artifact ref."""
    if (
        ref.manifest_profile_sha256 is None
        or manifest.artifact_id != ref.artifact_id
        or manifest.kind != ref.kind
        or manifest.media_type != ref.media_type
        or artifact_manifest_profile_sha256(manifest) != ref.manifest_profile_sha256
    ):
        raise ValueError("execution_source_manifest_selected_identity_mismatch")


def _read_typed_model(
    model: type[_ModelT],
    store: ArtifactStore,
    ref: ArtifactRef,
    *,
    read_session: _BoundedExecutionSourceReadSession | None,
) -> _ModelT:
    """Read with Core's owner validator or the required bounded Core facade."""
    if read_session is None:
        return validate_core_model_json_artifact(model, store, ref)
    return read_session.typed_model(model, ref)


def _read_registry_bundle_payload(
    store: ArtifactStore,
    ref: ArtifactRef,
    *,
    read_session: _BoundedExecutionSourceReadSession | None,
) -> RegistryBundlePayload:
    """Keep the legacy loader while bounding the selected projection reader."""
    if read_session is None:
        return load_registry_bundle_payload(store, ref)
    return read_session.typed_model(RegistryBundlePayload, ref)


def _selected_manifest(
    store: ArtifactStore,
    ref: ArtifactRef,
    *,
    read_session: _BoundedExecutionSourceReadSession | None = None,
) -> ArtifactManifest:
    """Resolve one exact selected manifest and verify its payload bytes."""
    if ref.manifest_profile_sha256 is None:
        raise ValueError("execution_source_selected_profile_missing")
    if read_session is not None:
        return read_session.selected_manifest(ref)
    manifest = resolve_manifest_by_profile(store, ref.artifact_id, ref.manifest_profile_sha256)
    if manifest.kind != ref.kind or manifest.media_type != ref.media_type:
        raise ValueError("execution_source_manifest_contract_mismatch")
    if not store.verify(ref).ok:
        raise ValueError("execution_source_manifest_integrity_failure")
    return manifest


def _selected_ref_from_edge(
    store: ArtifactStore,
    parent_ref: ArtifactRef,
    role: str,
    *,
    expected_kind: str | None = None,
    read_session: _BoundedExecutionSourceReadSession | None = None,
) -> ArtifactRef:
    """Resolve a unique content-bound parent edge without falling back to the default view."""
    parent_manifest = _selected_manifest(store, parent_ref, read_session=read_session)
    edges = [edge for edge in parent_manifest.inputs if edge.role == role]
    if len(edges) != 1:
        raise ValueError(f"execution_source_requires_one_edge:{role}")
    edge = edges[0]
    if edge.manifest_profile_sha256 is None:
        raise ValueError(f"execution_source_edge_profile_missing:{role}")
    if read_session is None:
        manifest = resolve_manifest_by_profile(
            store, edge.artifact_id, edge.manifest_profile_sha256
        )
        ref = ArtifactRef(
            artifact_id=manifest.artifact_id,
            kind=manifest.kind,
            media_type=manifest.media_type,
            manifest_profile_sha256=edge.manifest_profile_sha256,
        )
    else:
        ref, manifest = read_session.edge_ref_and_manifest(parent_ref, edge)
    if expected_kind is not None and manifest.kind != expected_kind:
        raise ValueError(f"execution_source_edge_kind_mismatch:{role}")
    if read_session is None:
        _selected_manifest(store, ref)
    return ref


def _execution_source_inventory(
    store: ArtifactStore,
    sources: list[tuple[str, ArtifactRef]],
    *,
    read_session: _BoundedExecutionSourceReadSession | None = None,
) -> list[InputRef]:
    """Inventory exact selected source manifests and each complete direct edge set."""
    inventory: list[InputRef] = []
    for source_role, source_ref in sources:
        manifest = _selected_manifest(store, source_ref, read_session=read_session)
        inventory.append(
            input_ref_from_artifact_ref(source_ref, role=f"basis.source.{source_role}")
        )
        for edge in manifest.inputs:
            if edge.manifest_profile_sha256 is None:
                raise ValueError(f"execution_source_edge_profile_missing:{source_role}.{edge.role}")
            if read_session is None:
                resolve_manifest_by_profile(store, edge.artifact_id, edge.manifest_profile_sha256)
            else:
                read_session.edge_ref_and_manifest(source_ref, edge)
            inventory.append(
                InputRef(
                    artifact_id=edge.artifact_id,
                    role=f"basis.edge.{source_role}.{edge.role}",
                    manifest_profile_sha256=edge.manifest_profile_sha256,
                )
            )
    return inventory


def _execution_input_basis_sources(
    basis: FoundryExecutionInputBasis,
) -> list[tuple[str, ArtifactRef]]:
    """Enumerate the source refs owned by a Foundry execution-input basis."""
    sources: list[tuple[str, ArtifactRef]] = [
        ("exec_plan", basis.exec_plan_ref),
        ("program_graph", basis.program_graph_ref),
        ("trinity_bundle", basis.trinity_bundle_ref),
        ("candidate", basis.candidate_ref),
        ("candidate_data_snapshot", basis.candidate_data_snapshot_ref),
        ("candidate_registry_bundle", basis.candidate_registry_bundle_ref),
        ("input_bindings", basis.input_bindings_ref),
        ("actual_data_snapshot", basis.data_snapshot_ref),
        ("bound_state_snapshot", basis.bound_state_snapshot_ref),
        ("base_state_snapshot", basis.base_state_snapshot_ref),
        ("binding_registry_bundle", basis.binding_registry_ref),
        ("compile_registry_bundle", basis.compile_registry_ref),
        ("runtime_registry_bundle", basis.runtime_registry_ref),
    ]
    for role, payload in (
        ("binding", basis.binding_registry_members),
        ("compile", basis.compile_registry_members),
        ("runtime", basis.runtime_registry_members),
    ):
        for member_role, member_ref in payload.model_dump(mode="python").items():
            if member_ref is not None:
                sources.append(
                    (
                        f"{role}_registry_member.{member_role}",
                        ArtifactRef.model_validate(member_ref),
                    )
                )
    if basis.registered_sql_admission_ref is not None:
        sources.append(("registered_sql_admission", basis.registered_sql_admission_ref))
    if basis.parameter_override_bundle_ref is not None:
        sources.append(("parameter_override_bundle", basis.parameter_override_bundle_ref))
    if basis.observed_range_bundle_ref is not None:
        sources.append(("observed_range_bundle", basis.observed_range_bundle_ref))
    if basis.request.feedback_config_ref is not None:
        sources.append(("feedback_config", basis.request.feedback_config_ref))
    return sources


def _execution_input_basis_inventory(
    store: ArtifactStore,
    basis: FoundryExecutionInputBasis,
    *,
    read_session: _BoundedExecutionSourceReadSession | None = None,
) -> list[InputRef]:
    """Recompute the exact basis inventory through the executor's source reader."""
    return _execution_source_inventory(
        store,
        _execution_input_basis_sources(basis),
        read_session=read_session,
    )


def _execution_input_inventory_key(
    items: list[InputRef],
) -> list[tuple[str, str, str | None]]:
    return sorted(
        (str(item.artifact_id), item.role, item.manifest_profile_sha256) for item in items
    )


def _execution_ref_key(
    ref: ArtifactRef | UncertaintyEnvelopeRef,
) -> tuple[str, str, str, str | None]:
    return (
        str(ref.artifact_id),
        ref.kind,
        ref.media_type,
        ref.manifest_profile_sha256,
    )


def _require_execution_edge_ref(
    store: ArtifactStore,
    parent_ref: ArtifactRef,
    role: str,
    expected_ref: ArtifactRef | UncertaintyEnvelopeRef,
    *,
    expected_kind: str,
    read_session: _BoundedExecutionSourceReadSession | None = None,
) -> ArtifactRef:
    """Resolve one exact selected parent edge and compare its complete child identity."""
    selected_ref = _selected_ref_from_edge(
        store,
        parent_ref,
        role,
        expected_kind=expected_kind,
        read_session=read_session,
    )
    if _execution_ref_key(selected_ref) != _execution_ref_key(expected_ref):
        raise ValueError(f"execution_source_edge_payload_disagrees:{role}")
    return selected_ref


def _verify_execution_data_snapshot_edges(
    store: ArtifactStore,
    ref: ArtifactRef,
    snapshot: DataSnapshot,
    *,
    read_session: _BoundedExecutionSourceReadSession | None = None,
) -> None:
    """Reconcile the selected DataSnapshot fields with their exact CAS edges."""
    manifest = _selected_manifest(store, ref, read_session=read_session)
    for role, raw_ref in (
        ("data_ref", snapshot.data_ref),
        ("uncertainty_envelope_ref", snapshot.uncertainty_envelope_ref),
    ):
        edges = [edge for edge in manifest.inputs if edge.role == role]
        if raw_ref is None:
            if edges:
                raise ValueError(f"execution_source_data_snapshot_unexpected_edge:{role}")
            continue
        if len(edges) != 1 or edges[0].manifest_profile_sha256 is None:
            raise ValueError(f"execution_source_data_snapshot_requires_selected_edge:{role}")
        _require_execution_edge_ref(
            store,
            ref,
            role,
            raw_ref,
            expected_kind=raw_ref.kind,
            read_session=read_session,
        )


def _simulation_result_manifest(
    store: ArtifactStore,
    ref: SimulationResultRef,
    *,
    read_session: _BoundedExecutionSourceReadSession | None,
) -> ArtifactManifest:
    """Read the selected result manifest, isolating legacy profileless access."""
    if read_session is not None:
        if ref.manifest_profile_sha256 is None:
            raise ValueError("execution_source_selected_profile_missing")
        return read_session.selected_manifest(ref)
    if ref.manifest_profile_sha256 is None:
        manifest = store.get_manifest(ref)
        if not store.verify(ref).ok:
            raise ValueError("execution_source_manifest_integrity_failure")
        return manifest
    return _selected_manifest(store, ref)


def _admit_execution_source(
    store: ArtifactStore,
    simulation_result_ref: SimulationResultRef,
    *,
    read_session: _BoundedExecutionSourceReadSession | None = None,
) -> ExecutionSourceAdmission:
    """Admit a result's explicit source mode and, when selected, its exact basis.

    The reference field alone does not select replay behavior. Only an exact
    single-step basis whose owner request, source-result edges, and complete CAS
    source inventory agree can select profiled replay. Legacy and feedback modes
    remain distinct, explicit outcomes.
    """
    simulation_manifest = _simulation_result_manifest(
        store,
        simulation_result_ref,
        read_session=read_session,
    )
    if simulation_manifest.kind != SimulationResult.ARTIFACT_KIND:
        raise ValueError("execution_source_simulation_result_kind_mismatch")
    simulation_result = _read_typed_model(
        SimulationResult,
        store,
        simulation_result_ref,
        read_session=read_session,
    )
    roles = [item.role for item in simulation_manifest.inputs]
    if len(roles) != len(set(roles)):
        raise ValueError("execution_source_simulation_result_duplicate_input_role")
    basis_edges = [
        item for item in simulation_manifest.inputs if item.role == "execution_input_basis"
    ]

    if (
        simulation_result.schema_version == SimulationResult.LEGACY_ARTIFACT_SCHEMA_VERSION
        and simulation_result.execution_source_status == "not_recorded"
        and simulation_result.execution_input_basis_ref is None
    ):
        if basis_edges:
            raise ValueError("execution_source_legacy_result_has_basis_edge")
        return ExecutionSourceAdmission(
            mode="legacy_profileless",
            simulation_result_ref=simulation_result_ref,
            simulation_result=simulation_result,
            simulation_manifest=simulation_manifest,
            source_read_bytes=(read_session.observed_bytes if read_session is not None else None),
        )

    if simulation_result_ref.manifest_profile_sha256 is None:
        raise ValueError("execution_source_selected_profile_missing")

    if (
        simulation_result.schema_version == SimulationResult.ARTIFACT_SCHEMA_VERSION
        and simulation_result.execution_source_status == "feedback_uncomposed"
        and simulation_result.execution_input_basis_ref is None
        and simulation_result.feedback_result_ref is not None
    ):
        if basis_edges:
            raise ValueError("execution_source_feedback_result_has_basis_edge")
        feedback_ref = simulation_result.feedback_result_ref
        if feedback_ref.manifest_profile_sha256 is None:
            raise ValueError("execution_source_feedback_result_profile_missing")
        _require_execution_edge_ref(
            store,
            simulation_result_ref,
            "artifact.feedback_result_ref",
            feedback_ref,
            expected_kind="foundry.feedback_result",
            read_session=read_session,
        )
        _read_typed_model(FeedbackSolveResult, store, feedback_ref, read_session=read_session)
        feedback_config_ref = _selected_ref_from_edge(
            store,
            simulation_result_ref,
            "input.feedback_config_ref",
            expected_kind=FeedbackConfig.ARTIFACT_KIND,
            read_session=read_session,
        )
        feedback_config = _read_typed_model(
            FeedbackConfig, store, feedback_config_ref, read_session=read_session
        )
        if feedback_config.mode != "fixed_point":
            raise ValueError("execution_source_feedback_config_does_not_match_refusal_mode")
        return ExecutionSourceAdmission(
            mode="feedback_uncomposed",
            simulation_result_ref=simulation_result_ref,
            simulation_result=simulation_result,
            simulation_manifest=simulation_manifest,
            source_read_bytes=(read_session.observed_bytes if read_session is not None else None),
        )

    if (
        simulation_result.schema_version != SimulationResult.ARTIFACT_SCHEMA_VERSION
        or simulation_result.execution_source_status != "single_step_basis"
        or simulation_result.execution_input_basis_ref is None
        or simulation_result.feedback_result_ref is not None
    ):
        raise ValueError("execution_source_status_has_no_admitted_mode")

    basis_ref = simulation_result.execution_input_basis_ref
    if basis_ref.manifest_profile_sha256 is None:
        raise ValueError("execution_source_basis_selected_profile_missing")
    if len(basis_edges) != 1:
        raise ValueError("execution_source_requires_one_execution_input_basis_edge")
    basis_edge = basis_edges[0]
    if (
        basis_edge.artifact_id != basis_ref.artifact_id
        or basis_edge.manifest_profile_sha256 != basis_ref.manifest_profile_sha256
    ):
        raise ValueError("execution_source_basis_ref_differs_from_exact_result_edge")
    basis_manifest = _selected_manifest(store, basis_ref, read_session=read_session)
    basis_schema = basis_manifest.artifact_schema
    if (
        basis_schema is None
        or basis_schema.name != FoundryExecutionInputBasis.ARTIFACT_SCHEMA_NAME
        or basis_schema.version not in FoundryExecutionInputBasis.ARTIFACT_SCHEMA_VERSIONS
    ):
        raise ValueError("execution_source_basis_schema_mismatch")
    basis = _read_typed_model(
        FoundryExecutionInputBasis,
        store,
        basis_ref,
        read_session=read_session,
    )
    if basis.schema_version != basis_schema.version:
        raise ValueError("execution_source_basis_schema_mismatch")

    fields_set = basis.request_fields_set
    if fields_set != tuple(sorted(set(fields_set))) or set(fields_set) - set(
        ExecuteRequest.model_fields
    ):
        raise ValueError("execution_source_basis_request_fields_set_invalid")
    if (
        basis.request.return_selected_profile is not True
        or "return_selected_profile" not in fields_set
    ):
        raise ValueError("execution_source_basis_request_did_not_explicitly_select_profiles")
    config_fields_set = basis.request_exec_config_fields_set
    if config_fields_set != tuple(sorted(set(config_fields_set))) or set(config_fields_set) - set(
        FoundryExecConfig.model_fields
    ):
        raise ValueError("execution_source_basis_exec_config_fields_set_invalid")

    if (
        _execution_ref_key(basis.exec_plan_ref)
        != _execution_ref_key(simulation_result.exec_plan_ref)
        or _execution_ref_key(basis.request.exec_plan_ref)
        != _execution_ref_key(basis.exec_plan_ref)
        or _execution_ref_key(basis.request.input_bindings_ref)
        != _execution_ref_key(basis.input_bindings_ref)
        or basis.request.registry_bundle_ref is None
        or _execution_ref_key(basis.request.registry_bundle_ref)
        != _execution_ref_key(basis.runtime_registry_ref)
        or (basis.request.parameter_override_bundle_ref is None)
        != (basis.parameter_override_bundle_ref is None)
        or (
            basis.request.parameter_override_bundle_ref is not None
            and basis.parameter_override_bundle_ref is not None
            and _execution_ref_key(basis.request.parameter_override_bundle_ref)
            != _execution_ref_key(basis.parameter_override_bundle_ref)
        )
        or (basis.request.observed_range_bundle_ref is None)
        != (basis.observed_range_bundle_ref is None)
        or (
            basis.request.observed_range_bundle_ref is not None
            and basis.observed_range_bundle_ref is not None
            and _execution_ref_key(basis.request.observed_range_bundle_ref)
            != _execution_ref_key(basis.observed_range_bundle_ref)
        )
    ):
        raise ValueError("execution_source_basis_request_refs_disagree")

    source_plan_ref = _selected_ref_from_edge(
        store,
        simulation_result_ref,
        "exec_plan",
        expected_kind=ExecPlan.ARTIFACT_KIND,
        read_session=read_session,
    )
    source_bindings_ref = _selected_ref_from_edge(
        store,
        simulation_result_ref,
        "input.input_bindings_ref",
        expected_kind="foundry.input_bindings",
        read_session=read_session,
    )
    if _execution_ref_key(source_plan_ref) != _execution_ref_key(
        basis.exec_plan_ref
    ) or _execution_ref_key(source_bindings_ref) != _execution_ref_key(
        basis.request.input_bindings_ref
    ):
        raise ValueError("execution_source_basis_request_does_not_match_result_inputs")

    override_edges = [
        item for item in simulation_manifest.inputs if item.role == "parameter_override_bundle"
    ]
    if basis.request.parameter_override_bundle_ref is None:
        if override_edges:
            raise ValueError("execution_source_unrequested_parameter_override_edge")
    else:
        if len(override_edges) != 1:
            raise ValueError("execution_source_requires_one_parameter_override_edge")
        source_override_ref = _selected_ref_from_edge(
            store,
            simulation_result_ref,
            "parameter_override_bundle",
            expected_kind=ParameterOverrideBundle.ARTIFACT_KIND,
            read_session=read_session,
        )
        if _execution_ref_key(source_override_ref) != _execution_ref_key(
            basis.request.parameter_override_bundle_ref
        ):
            raise ValueError("execution_source_basis_override_differs_from_result_input")

    exec_plan = _read_typed_model(ExecPlan, store, basis.exec_plan_ref, read_session=read_session)
    if _execution_ref_key(exec_plan.program_ref) != _execution_ref_key(basis.program_graph_ref):
        raise ValueError("execution_source_basis_graph_differs_from_exec_plan")
    _require_execution_edge_ref(
        store,
        basis.exec_plan_ref,
        "program_graph",
        basis.program_graph_ref,
        expected_kind=ProgramGraph.ARTIFACT_KIND,
        read_session=read_session,
    )
    graph = _read_typed_model(
        ProgramGraph, store, basis.program_graph_ref, read_session=read_session
    )
    if _execution_ref_key(graph.ir_ref) != _execution_ref_key(basis.trinity_bundle_ref):
        raise ValueError("execution_source_basis_trinity_differs_from_program_graph")
    _require_execution_edge_ref(
        store,
        basis.program_graph_ref,
        "ir",
        basis.trinity_bundle_ref,
        expected_kind=basis.trinity_bundle_ref.kind,
        read_session=read_session,
    )
    _require_execution_edge_ref(
        store,
        basis.program_graph_ref,
        "registry_bundle",
        basis.compile_registry_ref,
        expected_kind="core.registry_bundle",
        read_session=read_session,
    )

    _require_execution_edge_ref(
        store,
        basis.trinity_bundle_ref,
        "policy_candidate",
        basis.candidate_ref,
        expected_kind="scientist.policy_design.candidate",
        read_session=read_session,
    )

    bindings = _read_typed_model(
        FoundryInputBindings,
        store,
        basis.input_bindings_ref,
        read_session=read_session,
    )
    if bindings.bound_state_snapshot_ref is None or (
        _execution_ref_key(bindings.data_snapshot_ref)
        != _execution_ref_key(basis.data_snapshot_ref)
        or _execution_ref_key(bindings.bound_state_snapshot_ref)
        != _execution_ref_key(basis.bound_state_snapshot_ref)
        or _execution_ref_key(bindings.registry_bundle_ref)
        != _execution_ref_key(basis.binding_registry_ref)
        or _execution_ref_key(basis.base_state_snapshot_ref)
        != _execution_ref_key(bindings.bound_state_snapshot_ref)
    ):
        raise ValueError("execution_source_basis_bindings_disagree")
    source_binding: RegisteredSQLAdmissionBinding | None = None
    binding_manifest = _selected_manifest(
        store, basis.input_bindings_ref, read_session=read_session
    )
    transport_edges = [
        edge
        for edge in binding_manifest.inputs
        if edge.role == "input.registered_sql_admission_ref"
    ]
    if (basis.registered_sql_admission_ref is None) != (
        bindings.registered_sql_admission_ref is None
    ):
        raise ValueError("execution_source_registered_sql_binding_disagrees")
    if basis.registered_sql_admission_ref is None:
        if transport_edges:
            raise ValueError("execution_source_unrequested_registered_sql_edge")
    else:
        source_ref = basis.registered_sql_admission_ref
        if bindings.registered_sql_admission_ref is None or _execution_ref_key(
            source_ref
        ) != _execution_ref_key(bindings.registered_sql_admission_ref):
            raise ValueError("execution_source_registered_sql_binding_disagrees")
        _require_execution_edge_ref(
            store,
            basis.input_bindings_ref,
            "input.registered_sql_admission_ref",
            source_ref,
            expected_kind=RegisteredSQLAdmissionBinding.ARTIFACT_KIND,
            read_session=read_session,
        )
        source_binding = _read_typed_model(
            RegisteredSQLAdmissionBinding, store, source_ref, read_session=read_session
        )
        if _execution_ref_key(source_binding.materialization.snapshot_ref) != _execution_ref_key(
            basis.data_snapshot_ref
        ):
            raise ValueError("execution_source_registered_sql_snapshot_disagrees")
        _require_execution_edge_ref(
            store,
            source_ref,
            "source.snapshot",
            basis.data_snapshot_ref,
            expected_kind=DataSnapshot.ARTIFACT_KIND,
            read_session=read_session,
        )
    _require_execution_edge_ref(
        store,
        basis.input_bindings_ref,
        "input.data_snapshot_ref",
        basis.data_snapshot_ref,
        expected_kind=DataSnapshot.ARTIFACT_KIND,
        read_session=read_session,
    )
    _require_execution_edge_ref(
        store,
        basis.input_bindings_ref,
        "input.registry_bundle_ref",
        basis.binding_registry_ref,
        expected_kind="core.registry_bundle",
        read_session=read_session,
    )
    _require_execution_edge_ref(
        store,
        basis.input_bindings_ref,
        "artifact.bound_state_snapshot_ref",
        basis.bound_state_snapshot_ref,
        expected_kind="foundry.state_snapshot",
        read_session=read_session,
    )
    _require_execution_edge_ref(
        store,
        simulation_result_ref,
        "input.data_snapshot_ref",
        bindings.data_snapshot_ref,
        expected_kind=DataSnapshot.ARTIFACT_KIND,
        read_session=read_session,
    )
    _require_execution_edge_ref(
        store,
        simulation_result_ref,
        "input.bound_state_snapshot_ref",
        bindings.bound_state_snapshot_ref,
        expected_kind="foundry.state_snapshot",
        read_session=read_session,
    )
    for registry_ref, declared_members in (
        (basis.binding_registry_ref, basis.binding_registry_members),
        (basis.compile_registry_ref, basis.compile_registry_members),
        (basis.runtime_registry_ref, basis.runtime_registry_members),
    ):
        if (
            _read_registry_bundle_payload(
                store,
                registry_ref,
                read_session=read_session,
            )
            != declared_members
        ):
            raise ValueError("execution_source_basis_registry_members_disagree")

    if basis.request.feedback_config_ref is not None:
        feedback_config = _read_typed_model(
            FeedbackConfig,
            store,
            basis.request.feedback_config_ref,
            read_session=read_session,
        )
        if feedback_config.mode != "off":
            raise ValueError("execution_source_feedback_basis_uncomposed")

    configured = FoundryExecConfig.model_construct(
        _fields_set=set(basis.request_exec_config_fields_set),
        **basis.request.exec_config.model_dump(mode="python"),
    )
    posture = resolve_execution_posture(exec_plan, configured)
    effective_posture = {
        "effective_seed": posture.seed,
        "effective_seed_source": posture.seed_source,
        "effective_mode": posture.mode,
        "effective_max_steps": posture.max_steps,
        "effective_determinism_tier": posture.determinism_tier,
        "effective_nan_guard_enabled": posture.nan_guard_enabled,
        "effective_jit": posture.jit,
        "effective_capture_env": posture.capture_env,
    }
    if any(getattr(basis, key) != value for key, value in effective_posture.items()):
        raise ValueError("execution_source_basis_effective_posture_does_not_recompute")

    if basis.data_snapshot_ref.manifest_profile_sha256 is None:
        raise ValueError("execution_source_data_snapshot_profile_missing")
    data_snapshot = _read_typed_model(
        DataSnapshot,
        store,
        basis.data_snapshot_ref,
        read_session=read_session,
    )
    _verify_execution_data_snapshot_edges(
        store,
        basis.data_snapshot_ref,
        data_snapshot,
        read_session=read_session,
    )
    if data_snapshot.data_ref.manifest_profile_sha256 is None:
        raise ValueError("execution_source_data_snapshot_state_profile_missing")

    if basis.registered_sql_admission_ref is not None:
        source_ref = basis.registered_sql_admission_ref
        if source_binding is None:
            raise ValueError("execution_source_registered_sql_binding_missing")
        registration = source_binding.materialization.registration
        expected_source_edges = [
            (basis.data_snapshot_ref, "source.snapshot"),
            (registration.effective_view_contract_ref, "source.view"),
            (registration.use_contract_ref, "source.use"),
            *(
                (ref, "snapshot." + role)
                for ref, role in data_snapshot_owner_input_requirements(data_snapshot)
            ),
            (source_binding.materialization.producer_capture_ref, "source.capture"),
        ]
        source_manifest = _selected_manifest(store, source_ref, read_session=read_session)
        expected_inputs = [
            input_ref_from_artifact_ref(ref, role=role) for ref, role in expected_source_edges
        ]
        if Counter(_execution_input_inventory_key(source_manifest.inputs)) != Counter(
            _execution_input_inventory_key(expected_inputs)
        ):
            raise ValueError("execution_source_registered_sql_edges_disagree")
        for expected_ref, role in expected_source_edges:
            _require_execution_edge_ref(
                store,
                source_ref,
                role,
                expected_ref,
                expected_kind=expected_ref.kind,
                read_session=read_session,
            )

    if basis.parameter_override_bundle_ref is None:
        expected_overrides = None
    else:
        override_payload = _read_typed_model(
            ParameterOverrideBundle,
            store,
            basis.parameter_override_bundle_ref,
            read_session=read_session,
        )
        expected_overrides = {
            str(node_id): dict(values)
            for node_id, values in override_payload.overrides.items()
            if isinstance(values, dict)
        }
    if basis.parameter_overrides != expected_overrides:
        raise ValueError("execution_source_basis_parameter_overrides_disagree")

    metrics_ref = simulation_result.metrics_ref
    if metrics_ref is None:
        raise ValueError("execution_source_result_missing:metrics")
    for role, output_ref in (
        ("metrics", simulation_result.metrics_ref),
        ("state_snapshot", simulation_result.state_snapshot_ref),
    ):
        if output_ref is None:
            raise ValueError(f"execution_source_result_missing:{role}")
        _require_execution_edge_ref(
            store,
            simulation_result_ref,
            role,
            output_ref,
            expected_kind=output_ref.kind,
            read_session=read_session,
        )
    state_delta_ref = _selected_ref_from_edge(
        store,
        simulation_result_ref,
        "state_delta",
        expected_kind=StateDelta.ARTIFACT_KIND,
        read_session=read_session,
    )
    state_delta = _read_typed_model(StateDelta, store, state_delta_ref, read_session=read_session)
    if state_delta.base_ref is None or _execution_ref_key(
        state_delta.base_ref
    ) != _execution_ref_key(basis.base_state_snapshot_ref):
        raise ValueError("execution_source_state_delta_base_differs_from_basis")
    for parent_ref in (metrics_ref, state_delta_ref):
        _require_execution_edge_ref(
            store,
            parent_ref,
            "execution_input_basis",
            basis_ref,
            expected_kind=FoundryExecutionInputBasis.ARTIFACT_KIND,
            read_session=read_session,
        )
    metrics = _read_typed_model(Metrics, store, metrics_ref, read_session=read_session)
    if metrics.values.get("step") != basis.effective_step:
        raise ValueError("execution_source_metrics_step_differs_from_basis")

    expected_inventory = _execution_input_basis_inventory(store, basis, read_session=read_session)
    if _execution_input_inventory_key(basis_manifest.inputs) != _execution_input_inventory_key(
        expected_inventory
    ):
        raise ValueError("execution_source_basis_manifest_does_not_bind_complete_source_graph")
    return ExecutionSourceAdmission(
        mode="single_step_basis",
        simulation_result_ref=simulation_result_ref,
        simulation_result=simulation_result,
        simulation_manifest=simulation_manifest,
        basis_ref=basis_ref,
        basis=basis,
        basis_manifest=basis_manifest,
        basis_inventory=tuple(expected_inventory),
        source_read_bytes=(read_session.observed_bytes if read_session is not None else None),
    )


def admit_execution_source(
    store: ArtifactStore,
    simulation_result_ref: SimulationResultRef,
) -> ExecutionSourceAdmission:
    """Recompute the selected execution-source mode and its complete CAS basis.

    Refusal text is the existing owner reason string; the subtype only adds a
    typed facade boundary. Only a single-step basis carries an inventory.
    """
    try:
        return _admit_execution_source(store, simulation_result_ref)
    except ExecutionSourceAdmissionRefusal:
        raise
    except ValueError as exc:
        # Only plain owner reason strings become admission refusals. Preserve
        # typed storage and payload-validation errors as their original classes.
        if type(exc) is not ValueError:
            raise
        raise ExecutionSourceAdmissionRefusal(str(exc)) from exc


def admit_execution_source_bounded(
    store: ArtifactStore,
    simulation_result_ref: SimulationResultRef,
    *,
    reader: BoundedExecutionSourceReader,
) -> ExecutionSourceAdmission:
    """Recompute source admission through one required aggregate-bounded reader.

    Unlike the compatibility entry point, this method requires a fully selected
    SimulationResult profile and routes every manifest, edge, and typed payload
    read through the supplied Core reader. The same source-basis predicate and
    refusal reasons are used by both entry points; this method has no
    profileless or unbounded fallback.

    Args:
        store: The configured artifact store. It is not used as a fallback
            reader; the supplied reader owns all source bytes and budget checks.
        simulation_result_ref: The exact selected-profile SimulationResult.
        reader: A server-owned reader that charges every actual read against a
            shared aggregate byte budget.

    Returns:
        The recomputed source admission, including aggregate observed read bytes.

    Raises:
        ExecutionSourceAdmissionRefusal: If the selected result does not pass
            the existing source admission predicate.
        ExecutionSourceBoundedReadRefusal: If aggregate reader budget is spent.
    """
    if simulation_result_ref.manifest_profile_sha256 is None:
        raise ExecutionSourceAdmissionRefusal("execution_source_selected_profile_missing")
    read_session = _BoundedExecutionSourceReadSession(reader=reader)
    try:
        return _admit_execution_source(
            store,
            simulation_result_ref,
            read_session=read_session,
        )
    except ExecutionSourceAdmissionRefusal:
        raise
    except ValueError as exc:
        if type(exc) is not ValueError:
            raise
        raise ExecutionSourceAdmissionRefusal(str(exc)) from exc


def _build_execution_input_basis(
    store: CoreJSONArtifactStore,
    *,
    request: ExecuteRequest,
    resolved_state: _ResolvedStateSource,
    exec_plan: ExecPlan,
    posture: ResolvedExecutionPosture,
    current_step: int,
    parameter_overrides: dict[str, dict[str, object]] | None,
) -> FoundryExecutionInputBasisRef:
    """Persist a selected source basis from the same objects used by the executor."""
    bindings = load_input_bindings(store, request.input_bindings_ref)
    graph_ref = exec_plan.program_ref
    graph = _load_model(store, graph_ref, ProgramGraph)
    trinity_ref = graph.ir_ref
    trinity = load_trinity_bundle_artifact(ensure_ir_artifact_store(store), trinity_ref)
    candidate_ref = _selected_ref_from_edge(
        store,
        trinity_ref,
        "policy_candidate",
        expected_kind="scientist.policy_design.candidate",
    )
    candidate_data_snapshot_ref = _selected_ref_from_edge(
        store,
        candidate_ref,
        "world_model_data_snapshot",
        expected_kind="fabric.data_snapshot",
    )
    candidate_registry_bundle_ref = _selected_ref_from_edge(
        store,
        candidate_ref,
        "world_model_registry",
        expected_kind="core.registry_bundle",
    )
    compile_registry_ref = _selected_ref_from_edge(
        store, graph_ref, "registry_bundle", expected_kind="core.registry_bundle"
    )
    if not isinstance(trinity, TrinityBundle):
        raise TypeError("execution_source_trinity_contract_invalid")
    if str(trinity.model_spec.registry_bundle_ref) != str(
        candidate_registry_bundle_ref.artifact_id
    ):
        raise ValueError("execution_source_candidate_registry_edge_disagrees_with_trinity")
    binding_registry_ref = bindings.registry_bundle_ref
    runtime_registry_ref = request.registry_bundle_ref
    if runtime_registry_ref is None:
        raise ValueError("registry_bundle_ref is required for selected execution basis")
    source_refs: list[tuple[str, ArtifactRef]] = [
        ("exec_plan", request.exec_plan_ref),
        ("program_graph", graph_ref),
        ("trinity_bundle", trinity_ref),
        ("candidate", candidate_ref),
        ("candidate_data_snapshot", candidate_data_snapshot_ref),
        ("candidate_registry_bundle", candidate_registry_bundle_ref),
        ("input_bindings", request.input_bindings_ref),
        ("actual_data_snapshot", bindings.data_snapshot_ref),
        ("bound_state_snapshot", bindings.bound_state_snapshot_ref),
        ("base_state_snapshot", resolved_state.state_snapshot_ref),
        ("binding_registry_bundle", binding_registry_ref),
        ("compile_registry_bundle", compile_registry_ref),
        ("runtime_registry_bundle", runtime_registry_ref),
    ]
    if bindings.registered_sql_admission_ref is not None:
        source_refs.append(("registered_sql_admission", bindings.registered_sql_admission_ref))
    registry_payloads: dict[str, RegistryBundlePayload] = {}
    for role, ref in (
        ("binding", binding_registry_ref),
        ("compile", compile_registry_ref),
        ("runtime", runtime_registry_ref),
    ):
        payload = load_registry_bundle_payload(store, ref)
        registry_payloads[role] = payload
        for member_role, member_ref in payload.model_dump(mode="python").items():
            if member_ref is not None:
                typed_ref = ArtifactRef.model_validate(member_ref)
                source_refs.append((f"{role}_registry_member.{member_role}", typed_ref))
    if request.parameter_override_bundle_ref is not None:
        source_refs.append(("parameter_override_bundle", request.parameter_override_bundle_ref))
    if request.observed_range_bundle_ref is not None:
        source_refs.append(("observed_range_bundle", request.observed_range_bundle_ref))
    if request.feedback_config_ref is not None:
        source_refs.append(("feedback_config", request.feedback_config_ref))
    inventory = _execution_source_inventory(store, source_refs)
    basis = FoundryExecutionInputBasis(
        schema_version="1.1" if bindings.registered_sql_admission_ref is not None else "1.0",
        registered_sql_admission_ref=bindings.registered_sql_admission_ref,
        request=request,
        request_fields_set=tuple(sorted(request.model_fields_set)),
        request_exec_config_fields_set=tuple(sorted(request.exec_config.model_fields_set)),
        exec_plan_ref=request.exec_plan_ref,
        program_graph_ref=graph_ref,
        trinity_bundle_ref=trinity_ref,
        candidate_ref=candidate_ref,
        candidate_data_snapshot_ref=candidate_data_snapshot_ref,
        candidate_registry_bundle_ref=candidate_registry_bundle_ref,
        input_bindings_ref=request.input_bindings_ref,
        data_snapshot_ref=bindings.data_snapshot_ref,
        bound_state_snapshot_ref=bindings.bound_state_snapshot_ref,
        binding_registry_ref=binding_registry_ref,
        compile_registry_ref=compile_registry_ref,
        runtime_registry_ref=runtime_registry_ref,
        binding_registry_members=registry_payloads["binding"],
        compile_registry_members=registry_payloads["compile"],
        runtime_registry_members=registry_payloads["runtime"],
        base_state_snapshot_ref=resolved_state.state_snapshot_ref,
        parameter_override_bundle_ref=request.parameter_override_bundle_ref,
        observed_range_bundle_ref=request.observed_range_bundle_ref,
        parameter_overrides=parameter_overrides,
        effective_step=current_step,
        effective_seed=posture.seed,
        effective_seed_source=posture.seed_source,
        effective_mode=posture.mode,
        effective_max_steps=posture.max_steps,
        effective_determinism_tier=posture.determinism_tier,
        effective_nan_guard_enabled=posture.nan_guard_enabled,
        effective_jit=posture.jit,
        effective_capture_env=posture.capture_env,
    )
    payload_ref = store.put_json(
        basis,
        PutOptions(
            kind=FoundryExecutionInputBasis.ARTIFACT_KIND,
            media_type=FoundryExecutionInputBasis.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=FoundryExecutionInputBasis.ARTIFACT_SCHEMA_NAME,
                version=basis.schema_version,
            ),
            inputs=inventory,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return FoundryExecutionInputBasisRef.model_validate(payload_ref.model_dump(mode="python"))


def execute(store: ArtifactStore, request: ExecuteRequest) -> ExecuteResult:
    """Execute a compiled Foundry plan from a bound state snapshot.

    `request.input_bindings_ref` is treated as the canonical boundary object
    between Fabric data ingestion and Foundry runtime state. Execution reads
    the bound `StateSnapshotRef`, applies the `ExecPlan`, persists metrics,
    state-delta, optional constraint/environment artifacts, and finally writes
    a `SimulationResult` whose `state_snapshot_ref` points to the updated
    post-step snapshot.

    Deterministic replay is expected when the same `exec_plan_ref`,
    `input_bindings_ref`, `registry_bundle_ref`, parameter overrides, and
    `exec_config.seed` are reused against identical CAS content. Runtime
    unsupported-mechanism errors are returned as `ExecuteResult(ok=False, ...)`
    envelopes; malformed requests and missing registry references raise.

    Args:
        store: CAS containing the `ExecPlan`, registry bundle, input bindings,
            and parameter override artifacts, and receiving runtime outputs.
        request: Execution contract referencing the compiled plan, bound
            input snapshot, registry bundle, and runtime configuration.

    Returns:
        `ExecuteResult` with `simulation_result_ref` and derived artifact refs
        on success, or `ok=False` plus notes such as
        `missing_runtime_mechanism_support:*` or
        `hard_constraint_violation` when execution is rejected.

    Raises:
        ValueError: If `registry_bundle_ref` is missing or the request points
            to unreadable or invalid artifacts.

    Example:
        ```python
        from polisyos.core.contracts.foundry import ExecuteRequest
        from polisyos.foundry import execute

        result = execute(
            store,
            ExecuteRequest(
                exec_plan_ref=compile_result.exec_plan_ref,
                input_bindings_ref=input_bindings_ref,
                registry_bundle_ref=registry_bundle_ref,
            ),
        )
        if result.ok:
            simulation_ref = result.simulation_result_ref
        ```
    """

    core_json_store = resolve_core_json_profile_store(store)
    if core_json_store is None:
        raise CanonicalProfileRefusalError("canon_profile_raw_manifest_unavailable")
    store = core_json_store
    resolved_state = _resolve_state_snapshot(store, request)
    state_snapshot_ref = resolved_state.state_snapshot_ref
    registry_bundle_ref = request.registry_bundle_ref
    if registry_bundle_ref is None:
        raise ValueError("registry_bundle_ref is required for execute()")

    registry_content = load_registry_bundle_content(store, registry_bundle_ref)
    base_state = load_state_snapshot(store, snapshot_ref=state_snapshot_ref)

    exec_plan = _load_model(store, request.exec_plan_ref, ExecPlan)
    method_execution_capture = new_method_execution_capture(
        store,
        program_ref=exec_plan.program_ref,
        exec_plan_ref=request.exec_plan_ref,
    )
    if method_execution_capture is not None:
        request = request.model_copy(
            update={
                "exec_plan_ref": method_execution_capture.exec_plan_ref,
                "return_selected_profile": True,
            }
        )
    posture = resolve_execution_posture(exec_plan, request.exec_config)
    current_step = int(getattr(base_state, "step", 0))
    execution_notes = [*resolved_state.notes, *posture.notes]
    if posture.max_steps is not None and current_step >= posture.max_steps:
        return ExecuteResult(
            ok=False,
            simulation_result_ref=None,
            derived_refs=[],
            notes=[
                *execution_notes,
                f"max_steps_reached:{current_step}>={posture.max_steps}",
            ],
        )
    parameter_overrides: dict[str, dict[str, object]] | None = None
    parameter_override_inputs: list[InputRef] = []
    if request.parameter_override_bundle_ref is not None:
        bundle = _load_model(
            store,
            request.parameter_override_bundle_ref,
            ParameterOverrideBundle,
        )
        parameter_overrides = {
            str(node_id): dict(values)
            for node_id, values in bundle.overrides.items()
            if isinstance(values, dict)
        }
        parameter_override_inputs.append(
            input_ref_from_artifact_ref(
                request.parameter_override_bundle_ref,
                role="parameter_override_bundle",
            )
        )
    execution_input_basis_ref: FoundryExecutionInputBasisRef | None = None
    if request.return_selected_profile:
        _require_return_selected_profile_writer(store, "put_json")
    if request.feedback_config_ref is not None:
        feedback_config = _load_model(store, request.feedback_config_ref, FeedbackConfig)
        if feedback_config.mode == "fixed_point":
            return _execute_with_feedback(
                store,
                request=request,
                resolved_state=resolved_state,
                registry_content=registry_content,
                base_state=base_state,
                exec_plan=exec_plan,
                posture=posture,
                current_step=current_step,
                execution_notes=execution_notes,
                parameter_overrides=parameter_overrides,
                parameter_override_inputs=parameter_override_inputs,
                feedback_config=feedback_config,
                method_execution_capture=method_execution_capture,
            )
    if request.return_selected_profile:
        execution_input_basis_ref = _build_execution_input_basis(
            store,
            request=request,
            resolved_state=resolved_state,
            exec_plan=exec_plan,
            posture=posture,
            current_step=current_step,
            parameter_overrides=parameter_overrides,
        )
    try:
        exec_artifacts = execute_program_graph(
            store,
            program_ref=exec_plan.program_ref,
            exec_plan_ref=request.exec_plan_ref,
            base_state=base_state,
            mechanism_registry=registry_content.mechanism_registry,
            slot_registry=registry_content.slot_registry,
            merge_registry=registry_content.merge_registry,
            selector_field_registry=registry_content.selector_field_registry,
            constraint_registry=registry_content.constraint_registry,
            step=current_step,
            seed=posture.seed,
            base_ref=state_snapshot_ref,
            capture_env=posture.capture_env,
            parameter_overrides=parameter_overrides,
            parameter_override_bundle_ref=request.parameter_override_bundle_ref,
            observed_range_bundle_ref=request.observed_range_bundle_ref,
            welfare_bound_mode=request.welfare_bound_mode,
            execution_input_basis_ref=execution_input_basis_ref,
            return_selected_profile=request.return_selected_profile,
            method_execution_capture=method_execution_capture,
            finalize_method_execution_capture=True,
        )
    except MethodExecutionAbortError as exc:
        return _method_execution_abort_result(
            store,
            capture=method_execution_capture,
            error=exc,
        )
    except MissingRuntimeMechanismSupportError as exc:
        failed_refs: list[DerivedArtifact] = []
        bundle_ref = None
        if method_execution_capture is not None:
            bundle_ref = persist_method_execution_capture(store, method_execution_capture)
            failed_refs = [
                DerivedArtifact(
                    role="method_metric_binding_set",
                    ref=method_execution_capture.method_metric_binding_set_ref,
                ),
                DerivedArtifact(role="method_execution_bundle", ref=bundle_ref),
            ]
        return ExecuteResult(
            schema_version="1.1" if bundle_ref is not None else "1.0",
            ok=False,
            simulation_result_ref=None,
            method_execution_bundle_ref=bundle_ref,
            derived_refs=failed_refs,
            notes=[
                f"missing_runtime_mechanism_support:{exc.mech_type}",
                str(exc),
            ],
        )

    derived_refs = _build_standard_derived_refs(exec_artifacts)
    welfare_bound_failure_notes = _evaluate_welfare_bound_requirement(
        store,
        request=request,
        derived_refs=derived_refs,
    )

    if exec_artifacts.constraint_hard_fail:
        return ExecuteResult(
            ok=False,
            simulation_result_ref=None,
            derived_refs=derived_refs,
            notes=[*execution_notes, "hard_constraint_violation"],
        )
    if welfare_bound_failure_notes:
        return ExecuteResult(
            ok=False,
            simulation_result_ref=None,
            derived_refs=derived_refs,
            notes=[*execution_notes, *welfare_bound_failure_notes],
        )

    _, applied = apply_state_delta_and_snapshot(
        store,
        base_state=base_state,
        state_delta_ref=exec_artifacts.state_delta_ref,
        slot_registry=registry_content.slot_registry,
        merge_registry=registry_content.merge_registry,
        step=current_step,
        base_ref=state_snapshot_ref,
        return_selected_profile=request.return_selected_profile,
    )

    sim_result = SimulationResult(
        schema_version=(
            SimulationResult.ARTIFACT_SCHEMA_VERSION
            if execution_input_basis_ref is not None
            else SimulationResult.LEGACY_ARTIFACT_SCHEMA_VERSION
        ),
        exec_plan_ref=request.exec_plan_ref,
        metrics_ref=(
            MetricsRef.model_validate(exec_artifacts.metrics_ref.model_dump(mode="python"))
            if request.return_selected_profile
            else MetricsRef(artifact_id=exec_artifacts.metrics_ref.artifact_id)
        ),
        state_snapshot_ref=(
            StateSnapshotRef.model_validate(applied.state_snapshot_ref.model_dump(mode="python"))
            if request.return_selected_profile
            else StateSnapshotRef(artifact_id=applied.state_snapshot_ref.artifact_id)
        ),
        execution_input_basis_ref=execution_input_basis_ref,
        execution_source_status=(
            "single_step_basis" if execution_input_basis_ref is not None else "not_recorded"
        ),
        environment_ref=exec_artifacts.environment_ref,
        environment_fingerprint=(
            exec_artifacts.environment_fingerprint or posture.current_environment_fingerprint
        ),
        welfare_bound_refs=_extract_welfare_bound_refs(derived_refs),
        notes=list(execution_notes),
    )
    sim_inputs = [
        input_ref_from_artifact_ref(request.exec_plan_ref, role="exec_plan"),
        input_ref_from_artifact_ref(exec_artifacts.metrics_ref, role="metrics"),
        input_ref_from_artifact_ref(exec_artifacts.state_delta_ref, role="state_delta"),
        input_ref_from_artifact_ref(applied.state_snapshot_ref, role="state_snapshot"),
    ]
    sim_inputs.extend(resolved_state.input_refs)
    sim_inputs.extend(parameter_override_inputs)
    if exec_artifacts.method_execution_bundle_ref is not None:
        sim_inputs.append(
            input_ref_from_artifact_ref(
                exec_artifacts.method_execution_bundle_ref,
                role="method_execution",
            )
        )
    if execution_input_basis_ref is not None:
        sim_inputs.append(
            input_ref_from_artifact_ref(execution_input_basis_ref, role="execution_input_basis")
        )
    sim_result_ref = store.put_json(
        sim_result.to_artifact_payload(),
        PutOptions(
            kind=SimulationResult.ARTIFACT_KIND,
            media_type=SimulationResult.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=SimulationResult.ARTIFACT_SCHEMA_NAME,
                version=sim_result.schema_version,
            ),
            inputs=sim_inputs,
        ),
        return_selected_profile=request.return_selected_profile,
    )

    return ExecuteResult(
        schema_version=("1.1" if exec_artifacts.method_execution_bundle_ref is not None else "1.0"),
        ok=True,
        simulation_result_ref=(
            SimulationResultRef.model_validate(sim_result_ref.model_dump(mode="python"))
            if request.return_selected_profile
            else SimulationResultRef(artifact_id=sim_result_ref.artifact_id)
        ),
        method_execution_bundle_ref=exec_artifacts.method_execution_bundle_ref,
        derived_refs=derived_refs,
        notes=execution_notes,
    )


def _resolve_state_snapshot(
    store: CoreJSONArtifactStore, request: ExecuteRequest
) -> _ResolvedStateSource:
    """Load and validate the bound snapshot referenced by `request`."""
    bindings_ref = FoundryInputBindingsRef.model_validate(request.input_bindings_ref.model_dump())
    bindings = load_input_bindings(store, bindings_ref)
    _ensure_readable(store, bindings.data_snapshot_ref)
    _ensure_readable(store, bindings.bound_state_snapshot_ref)
    return _ResolvedStateSource(
        state_snapshot_ref=bindings.bound_state_snapshot_ref,
        notes=("state_source:input_bindings_ref",),
        input_refs=(
            input_ref_from_artifact_ref(bindings_ref, role="input.input_bindings_ref"),
            input_ref_from_artifact_ref(bindings.data_snapshot_ref, role="input.data_snapshot_ref"),
            input_ref_from_artifact_ref(
                bindings.bound_state_snapshot_ref,
                role="input.bound_state_snapshot_ref",
            ),
        ),
    )


def _ensure_readable(store: ArtifactStore, ref: ArtifactRef) -> None:
    """Raise if `ref` does not resolve to a readable CAS manifest."""
    store.get_manifest(ref)


def _load_model[ModelT: BaseModel](
    store: CoreJSONArtifactStore,
    ref: ArtifactRef,
    model_cls: type[ModelT],
) -> ModelT:
    """Deserialize a CAS JSON artifact into the requested Pydantic model."""
    from polisyos.core.artifacts import validate_core_model_json_artifact

    return validate_core_model_json_artifact(model_cls, store, ref)


def _execute_with_feedback(
    store: CoreJSONArtifactStore,
    *,
    request: ExecuteRequest,
    resolved_state: _ResolvedStateSource,
    registry_content: RegistryBundleContent,
    base_state: GlobalState,
    exec_plan: ExecPlan,
    posture: ResolvedExecutionPosture,
    current_step: int,
    execution_notes: list[str],
    parameter_overrides: dict[str, dict[str, object]] | None,
    parameter_override_inputs: list[InputRef],
    feedback_config: FeedbackConfig,
    method_execution_capture: MethodExecutionCapture | None = None,
) -> ExecuteResult:
    initial_feedback_state = _build_initial_feedback_state(base_state, feedback_config)
    prepared = prepare_feedback_config(
        feedback_config,
        initial_state=initial_feedback_state,
    )

    def evaluate_feedback_map(values: np.ndarray) -> MapEvaluation:
        snapshot = snapshot_from_vector(prepared, np.asarray(values, dtype=float))
        injected_state, feedback_overrides = inject_feedback_state(
            base_state,
            config=feedback_config,
            snapshot=snapshot,
        )
        merged_overrides = _merge_parameter_overrides(parameter_overrides, feedback_overrides)
        evaluation = _run_feedback_iteration(
            store,
            exec_plan=exec_plan,
            request=request,
            registry_content=registry_content,
            posture=posture,
            current_step=current_step,
            base_state=injected_state,
            parameter_overrides=merged_overrides,
            feedback_config=feedback_config,
            method_execution_capture=method_execution_capture,
            method_input_state_source_ref=resolved_state.state_snapshot_ref,
        )
        return evaluation.map_evaluation

    try:
        outcome = solve_fixed_point(
            prepared=prepared,
            evaluate_map=evaluate_feedback_map,
        )
    except MethodExecutionAbortError as exc:
        return _method_execution_abort_result(
            store,
            capture=method_execution_capture,
            error=exc,
            notes=["feedback_mode:fixed_point"],
        )
    except MissingRuntimeMechanismSupportError as exc:
        return ExecuteResult(
            ok=False,
            simulation_result_ref=None,
            derived_refs=_persisted_method_metric_capture_refs(
                store,
                method_execution_capture,
            ),
            notes=[
                *execution_notes,
                "feedback_mode:fixed_point",
                f"missing_runtime_mechanism_support:{exc.mech_type}",
                str(exc),
            ],
        )
    except RuntimeError as exc:
        return ExecuteResult(
            ok=False,
            simulation_result_ref=None,
            derived_refs=_persisted_method_metric_capture_refs(
                store,
                method_execution_capture,
            ),
            notes=[
                *execution_notes,
                "feedback_mode:fixed_point",
                f"feedback_solve_failed:{exc}",
            ],
        )
    solved_feedback_state = snapshot_from_vector(
        prepared,
        np.asarray(outcome.solution, dtype=float),
        notes=[
            "fixed_point_solution" if outcome.converged else "fixed_point_candidate",
            outcome.status,
        ],
    )
    feedback_trace_ref = _persist_feedback_trace(
        store,
        outcome=outcome,
        request=request,
    )
    feedback_jacobian_ref = _persist_feedback_jacobian(
        store,
        outcome=outcome,
        request=request,
        trace_ref=feedback_trace_ref,
    )
    feedback_certificate_ref = _persist_feedback_convergence_certificate(
        store,
        outcome=outcome,
        request=request,
        prepared=prepared,
        trace_ref=feedback_trace_ref,
        jacobian_ref=feedback_jacobian_ref,
    )
    feedback_artifacts = [
        DerivedArtifact(role="feedback_trace", ref=feedback_trace_ref),
        DerivedArtifact(role="feedback_convergence_certificate", ref=feedback_certificate_ref),
    ]
    if feedback_jacobian_ref is not None:
        feedback_artifacts.append(
            DerivedArtifact(role="feedback_jacobian_diagnostics", ref=feedback_jacobian_ref)
        )
    multiplicity_report_ref: EquilibriumMultiplicityReportRef | None = None
    multiplicity_notes: list[str] = []
    if (
        feedback_config.solver.detect_multiplicity
        or feedback_config.solver.multiplicity_mode != "off"
    ):
        try:
            report = discover_equilibria(
                prepared=prepared,
                evaluate_map=evaluate_feedback_map,
                base_outcome=outcome,
                runtime_refs=[
                    str(feedback_trace_ref.artifact_id),
                    str(feedback_certificate_ref.artifact_id),
                    *(
                        [str(feedback_jacobian_ref.artifact_id)]
                        if feedback_jacobian_ref is not None
                        else []
                    ),
                ],
            )
            multiplicity_report_ref = _persist_equilibrium_multiplicity_report(
                store,
                request=request,
                report=report,
                trace_ref=feedback_trace_ref,
                jacobian_ref=feedback_jacobian_ref,
                convergence_certificate_ref=feedback_certificate_ref,
            )
            feedback_artifacts.append(
                DerivedArtifact(
                    role="equilibrium_multiplicity_report",
                    ref=multiplicity_report_ref,
                )
            )
            multiplicity_notes.append("feedback_multiplicity_report:created")
        except RuntimeError as exc:
            multiplicity_notes.append(f"feedback_multiplicity_report_failed:{exc}")

    if not outcome.converged:
        feedback_result_ref = _persist_feedback_result(
            store,
            request=request,
            prepared=prepared,
            exec_artifacts=None,
            initial_feedback_state=initial_feedback_state,
            final_feedback_state=solved_feedback_state,
            final_feedback_diagnostics=outcome.final_diagnostics,
            final_override_bundle_ref=None,
            trace_ref=feedback_trace_ref,
            jacobian_ref=feedback_jacobian_ref,
            convergence_certificate_ref=feedback_certificate_ref,
            multiplicity_report_ref=multiplicity_report_ref,
            status=outcome.status,
            converged=False,
            failure_reason=outcome.failure_reason,
            alternative_solutions=outcome.alternative_solutions,
            notes=[
                "feedback_mode:fixed_point",
                f"feedback_status:{outcome.status}",
                *multiplicity_notes,
            ],
        )
        return ExecuteResult(
            ok=False,
            simulation_result_ref=None,
            derived_refs=[
                *_persisted_method_metric_capture_refs(store, method_execution_capture),
                *feedback_artifacts,
                DerivedArtifact(role="feedback_result", ref=feedback_result_ref),
            ],
            notes=[
                *execution_notes,
                "feedback_mode:fixed_point",
                f"feedback_status:{outcome.status}",
                *multiplicity_notes,
                *([f"feedback_failure:{outcome.failure_reason}"] if outcome.failure_reason else []),
            ],
        )

    final_injected_state, final_feedback_overrides = inject_feedback_state(
        base_state,
        config=feedback_config,
        snapshot=solved_feedback_state,
    )
    merged_final_overrides = _merge_parameter_overrides(
        parameter_overrides,
        final_feedback_overrides,
    )
    final_override_bundle_ref = _persist_parameter_override_bundle(
        store,
        request=request,
        merged_overrides=merged_final_overrides,
        feedback_notes=feedback_config.notes,
    )

    feedback_base_inputs = [
        input_ref_from_artifact_ref(
            resolved_state.state_snapshot_ref,
            role="input.bound_state_snapshot_ref",
        )
    ]
    if request.feedback_config_ref is not None:
        feedback_base_inputs.append(
            input_ref_from_artifact_ref(
                request.feedback_config_ref,
                role="input.feedback_config_ref",
            )
        )
    if final_override_bundle_ref is not None:
        feedback_base_inputs.append(
            input_ref_from_artifact_ref(
                final_override_bundle_ref,
                role="feedback.parameter_override_bundle",
            )
        )
    feedback_base_state_ref = put_state_snapshot(
        store,
        state=final_injected_state,
        step=current_step,
        inputs=feedback_base_inputs,
        return_selected_profile=request.return_selected_profile,
    )
    feedback_base_state_snapshot_ref = (
        StateSnapshotRef.model_validate(feedback_base_state_ref.model_dump(mode="python"))
        if request.return_selected_profile
        else StateSnapshotRef(artifact_id=feedback_base_state_ref.artifact_id)
    )

    try:
        exec_artifacts = execute_program_graph(
            store,
            program_ref=exec_plan.program_ref,
            exec_plan_ref=request.exec_plan_ref,
            base_state=final_injected_state,
            mechanism_registry=registry_content.mechanism_registry,
            slot_registry=registry_content.slot_registry,
            merge_registry=registry_content.merge_registry,
            selector_field_registry=registry_content.selector_field_registry,
            constraint_registry=registry_content.constraint_registry,
            step=current_step,
            seed=posture.seed,
            base_ref=feedback_base_state_snapshot_ref,
            capture_env=posture.capture_env,
            parameter_overrides=merged_final_overrides,
            parameter_override_bundle_ref=final_override_bundle_ref
            if final_override_bundle_ref is not None
            else request.parameter_override_bundle_ref,
            observed_range_bundle_ref=request.observed_range_bundle_ref,
            welfare_bound_mode=request.welfare_bound_mode,
            return_selected_profile=request.return_selected_profile,
            method_execution_capture=method_execution_capture,
            finalize_method_execution_capture=True,
        )
    except MethodExecutionAbortError as exc:
        return _method_execution_abort_result(
            store,
            capture=method_execution_capture,
            error=exc,
            notes=["feedback_mode:fixed_point"],
        )
    except MissingRuntimeMechanismSupportError as exc:
        feedback_result_ref = _persist_feedback_result(
            store,
            request=request,
            prepared=prepared,
            exec_artifacts=None,
            initial_feedback_state=initial_feedback_state,
            final_feedback_state=solved_feedback_state,
            final_feedback_diagnostics={
                **outcome.final_diagnostics,
                "final_execution_failed": 1,
            },
            final_override_bundle_ref=final_override_bundle_ref,
            trace_ref=feedback_trace_ref,
            jacobian_ref=feedback_jacobian_ref,
            convergence_certificate_ref=feedback_certificate_ref,
            multiplicity_report_ref=multiplicity_report_ref,
            status="failed",
            converged=False,
            failure_reason=str(exc),
            alternative_solutions=outcome.alternative_solutions,
            notes=[
                "feedback_mode:fixed_point",
                "feedback_status:failed",
                *multiplicity_notes,
                f"missing_runtime_mechanism_support:{exc.mech_type}",
            ],
        )
        return ExecuteResult(
            ok=False,
            simulation_result_ref=None,
            derived_refs=[
                *_persisted_method_metric_capture_refs(store, method_execution_capture),
                *feedback_artifacts,
                DerivedArtifact(role="feedback_result", ref=feedback_result_ref),
            ],
            notes=[
                *execution_notes,
                "feedback_mode:fixed_point",
                "feedback_status:failed",
                *multiplicity_notes,
                f"missing_runtime_mechanism_support:{exc.mech_type}",
                str(exc),
            ],
        )

    derived_refs = _build_standard_derived_refs(exec_artifacts)
    welfare_bound_failure_notes = _evaluate_welfare_bound_requirement(
        store,
        request=request,
        derived_refs=derived_refs,
    )
    final_state, applied = apply_state_delta_and_snapshot(
        store,
        base_state=final_injected_state,
        state_delta_ref=exec_artifacts.state_delta_ref,
        slot_registry=registry_content.slot_registry,
        merge_registry=registry_content.merge_registry,
        step=current_step,
        base_ref=feedback_base_state_snapshot_ref,
        return_selected_profile=request.return_selected_profile,
    )
    final_metrics = _load_model(store, exec_artifacts.metrics_ref, Metrics)
    final_feedback_observed = extract_feedback_state(
        final_state,
        config=feedback_config,
        metrics=final_metrics.values,
    )
    final_feedback_diagnostics = extract_feedback_diagnostics(
        final_state,
        config=feedback_config,
        metrics=final_metrics.values,
    )
    if exec_artifacts.constraint_hard_fail:
        final_feedback_diagnostics["constraint_hard_fail"] = 1.0

    feedback_result_ref = _persist_feedback_result(
        store,
        request=request,
        prepared=prepared,
        exec_artifacts=exec_artifacts,
        initial_feedback_state=initial_feedback_state,
        final_feedback_state=final_feedback_observed,
        final_feedback_diagnostics=final_feedback_diagnostics,
        final_override_bundle_ref=final_override_bundle_ref,
        trace_ref=feedback_trace_ref,
        jacobian_ref=feedback_jacobian_ref,
        convergence_certificate_ref=feedback_certificate_ref,
        multiplicity_report_ref=multiplicity_report_ref,
        status=outcome.status,
        converged=outcome.converged,
        failure_reason=outcome.failure_reason,
        alternative_solutions=outcome.alternative_solutions,
        notes=[
            "feedback_mode:fixed_point",
            f"feedback_converged:{int(outcome.converged)}",
            f"feedback_status:{outcome.status}",
            *multiplicity_notes,
        ],
    )
    derived_refs.extend(
        [
            *feedback_artifacts,
            DerivedArtifact(role="feedback_result", ref=feedback_result_ref),
        ]
    )

    if welfare_bound_failure_notes:
        return ExecuteResult(
            ok=False,
            simulation_result_ref=None,
            derived_refs=derived_refs,
            notes=[
                *execution_notes,
                "feedback_mode:fixed_point",
                *welfare_bound_failure_notes,
            ],
        )

    feedback_notes = [
        *execution_notes,
        "feedback_mode:fixed_point",
        f"feedback_iterations:{len(outcome.trace)}",
        f"feedback_status:{outcome.status}",
        *multiplicity_notes,
    ]
    sim_result = SimulationResult(
        schema_version=(
            SimulationResult.ARTIFACT_SCHEMA_VERSION
            if request.return_selected_profile
            else SimulationResult.LEGACY_ARTIFACT_SCHEMA_VERSION
        ),
        exec_plan_ref=request.exec_plan_ref,
        metrics_ref=(
            MetricsRef.model_validate(exec_artifacts.metrics_ref.model_dump(mode="python"))
            if request.return_selected_profile
            else MetricsRef(artifact_id=exec_artifacts.metrics_ref.artifact_id)
        ),
        state_snapshot_ref=(
            StateSnapshotRef.model_validate(applied.state_snapshot_ref.model_dump(mode="python"))
            if request.return_selected_profile
            else StateSnapshotRef(artifact_id=applied.state_snapshot_ref.artifact_id)
        ),
        execution_input_basis_ref=None,
        execution_source_status=(
            "feedback_uncomposed" if request.return_selected_profile else "not_recorded"
        ),
        environment_ref=exec_artifacts.environment_ref,
        environment_fingerprint=(
            exec_artifacts.environment_fingerprint or posture.current_environment_fingerprint
        ),
        feedback_result_ref=feedback_result_ref,
        welfare_bound_refs=_extract_welfare_bound_refs(derived_refs),
        notes=feedback_notes,
    )
    sim_inputs = [
        input_ref_from_artifact_ref(request.exec_plan_ref, role="exec_plan"),
        input_ref_from_artifact_ref(exec_artifacts.metrics_ref, role="metrics"),
        input_ref_from_artifact_ref(exec_artifacts.state_delta_ref, role="state_delta"),
        input_ref_from_artifact_ref(applied.state_snapshot_ref, role="state_snapshot"),
        input_ref_from_artifact_ref(
            feedback_base_state_snapshot_ref,
            role="input.feedback_base_state_snapshot_ref",
        ),
        input_ref_from_artifact_ref(feedback_result_ref, role="artifact.feedback_result_ref"),
        input_ref_from_artifact_ref(
            feedback_certificate_ref,
            role="artifact.feedback_convergence_certificate_ref",
        ),
    ]
    sim_inputs.extend(resolved_state.input_refs)
    sim_inputs.extend(parameter_override_inputs)
    if exec_artifacts.method_execution_bundle_ref is not None:
        sim_inputs.append(
            input_ref_from_artifact_ref(
                exec_artifacts.method_execution_bundle_ref,
                role="method_execution",
            )
        )
    if request.feedback_config_ref is not None:
        sim_inputs.append(
            input_ref_from_artifact_ref(
                request.feedback_config_ref,
                role="input.feedback_config_ref",
            )
        )
    if final_override_bundle_ref is not None:
        sim_inputs.append(
            input_ref_from_artifact_ref(
                final_override_bundle_ref,
                role="feedback.parameter_override_bundle",
            )
        )
    sim_result_ref = store.put_json(
        sim_result.to_artifact_payload(),
        PutOptions(
            kind=SimulationResult.ARTIFACT_KIND,
            media_type=SimulationResult.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=SimulationResult.ARTIFACT_SCHEMA_NAME,
                version=sim_result.schema_version,
            ),
            inputs=sim_inputs,
        ),
        return_selected_profile=request.return_selected_profile,
    )

    if exec_artifacts.constraint_hard_fail:
        return ExecuteResult(
            ok=False,
            simulation_result_ref=None,
            derived_refs=derived_refs,
            notes=[*feedback_notes, "hard_constraint_violation"],
        )

    return ExecuteResult(
        schema_version=("1.1" if exec_artifacts.method_execution_bundle_ref is not None else "1.0"),
        ok=True,
        simulation_result_ref=(
            SimulationResultRef.model_validate(sim_result_ref.model_dump(mode="python"))
            if request.return_selected_profile
            else SimulationResultRef(artifact_id=sim_result_ref.artifact_id)
        ),
        method_execution_bundle_ref=exec_artifacts.method_execution_bundle_ref,
        derived_refs=derived_refs,
        notes=feedback_notes,
    )


def _persisted_method_metric_capture_refs(
    store: ArtifactStore,
    capture: MethodExecutionCapture | None,
) -> list[DerivedArtifact]:
    """Persist refs-only graph evidence after a feedback failure with actual invocations."""
    if capture is None or capture.invocation_count == 0:
        return []
    bundle_ref = persist_method_execution_capture(store, capture)
    return [
        DerivedArtifact(
            role="method_metric_binding_set",
            ref=capture.method_metric_binding_set_ref,
        ),
        DerivedArtifact(role="method_execution_bundle", ref=bundle_ref),
    ]


def _run_feedback_iteration(
    store: CoreJSONArtifactStore,
    *,
    exec_plan: ExecPlan,
    request: ExecuteRequest,
    registry_content: RegistryBundleContent,
    posture: ResolvedExecutionPosture,
    current_step: int,
    base_state: GlobalState,
    parameter_overrides: dict[str, dict[str, object]] | None,
    feedback_config: FeedbackConfig,
    method_execution_capture: MethodExecutionCapture | None = None,
    method_input_state_source_ref: ArtifactRef | None = None,
) -> _FeedbackExecutionEvaluation:
    exec_artifacts = execute_program_graph(
        store,
        program_ref=exec_plan.program_ref,
        exec_plan_ref=request.exec_plan_ref,
        base_state=base_state,
        mechanism_registry=registry_content.mechanism_registry,
        slot_registry=registry_content.slot_registry,
        merge_registry=registry_content.merge_registry,
        selector_field_registry=registry_content.selector_field_registry,
        constraint_registry=registry_content.constraint_registry,
        step=current_step,
        seed=posture.seed,
        base_ref=None,
        capture_env=False,
        parameter_overrides=parameter_overrides,
        parameter_override_bundle_ref=request.parameter_override_bundle_ref,
        observed_range_bundle_ref=request.observed_range_bundle_ref,
        welfare_bound_mode="off",
        return_selected_profile=method_execution_capture is not None,
        method_execution_capture=method_execution_capture,
        method_input_state_source_ref=method_input_state_source_ref,
        finalize_method_execution_capture=False,
    )
    final_state = apply_state_delta(
        store,
        base_state=base_state,
        state_delta_ref=exec_artifacts.state_delta_ref,
        slot_registry=registry_content.slot_registry,
        merge_registry=registry_content.merge_registry,
    )
    metrics = _load_model(store, exec_artifacts.metrics_ref, Metrics)
    diagnostics = extract_feedback_diagnostics(
        final_state,
        config=feedback_config,
        metrics=metrics.values,
    )
    feedback_state = extract_feedback_state(
        final_state,
        config=feedback_config,
        metrics=metrics.values,
    )
    if exec_artifacts.constraint_hard_fail:
        diagnostics["constraint_hard_fail"] = 1.0
    budget_gap = None
    if feedback_config.solver.budget_diagnostic_id is not None:
        raw_budget_gap = diagnostics.get(feedback_config.solver.budget_diagnostic_id)
        if raw_budget_gap is not None:
            budget_gap = float(raw_budget_gap)
    noise_sd = None
    if diagnostics.get("noise_sd") is not None:
        noise_sd = float(diagnostics["noise_sd"])
    return _FeedbackExecutionEvaluation(
        map_evaluation=MapEvaluation(
            map_value=np.asarray(feedback_state.values, dtype=float),
            diagnostics=diagnostics,
            budget_gap=budget_gap,
            noise_sd=noise_sd,
        ),
        final_state=final_state,
    )


def _build_initial_feedback_state(
    base_state: GlobalState,
    feedback_config: FeedbackConfig,
) -> FeedbackStateSnapshot:
    values: list[float] = []
    for variable in feedback_config.variables:
        if variable.initial_value is not None:
            values.append(float(variable.initial_value))
            continue
        if variable.source_kind != "state_path":
            raise ValueError(
                f"Feedback variable '{variable.variable_id}' requires initial_value when "
                "source_kind is not 'state_path'"
            )
        single_config = FeedbackConfig(
            schema_version="1.0",
            mode="fixed_point",
            variables=[variable],
            solver=feedback_config.solver,
            notes=feedback_config.notes,
        )
        extracted = extract_feedback_state(base_state, config=single_config, metrics={})
        values.append(float(extracted.values[0]))
    return FeedbackStateSnapshot(
        variable_ids=[variable.variable_id for variable in feedback_config.variables],
        values=values,
        scales=[
            float(variable.scale) if variable.scale is not None else 1.0
            for variable in feedback_config.variables
        ],
        lower_bounds=[variable.lower_bound for variable in feedback_config.variables],
        upper_bounds=[variable.upper_bound for variable in feedback_config.variables],
        weights=[float(variable.weight) for variable in feedback_config.variables],
        notes=["initial_feedback_state"],
    )


def _merge_parameter_overrides(
    base: dict[str, dict[str, object]] | None,
    extra: dict[str, dict[str, object]] | None,
) -> dict[str, dict[str, object]] | None:
    if not base and not extra:
        return None
    merged: dict[str, dict[str, object]] = {
        str(node_id): dict(values) for node_id, values in (base or {}).items()
    }
    for node_id, values in (extra or {}).items():
        merged.setdefault(str(node_id), {}).update(dict(values))
    return merged


def _persist_parameter_override_bundle(
    store: ArtifactStore,
    *,
    request: ExecuteRequest,
    merged_overrides: dict[str, dict[str, object]] | None,
    feedback_notes: list[str],
) -> ParameterOverrideBundleRef | None:
    if not merged_overrides:
        return request.parameter_override_bundle_ref
    payload = ParameterOverrideBundle(
        schema_version="1.0",
        overrides=merged_overrides,
        sources={str(node_id): ["feedback_solver"] for node_id in merged_overrides},
        notes=["merged_for_feedback_mode", *feedback_notes],
    )
    ref = store.put_json(
        payload,
        PutOptions(
            kind=ParameterOverrideBundle.ARTIFACT_KIND,
            media_type=ParameterOverrideBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=ParameterOverrideBundle.ARTIFACT_SCHEMA_NAME,
                version=ParameterOverrideBundle.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=(
                [
                    input_ref_from_artifact_ref(
                        request.parameter_override_bundle_ref,
                        role="input.original_parameter_override_bundle_ref",
                    )
                ]
                if request.parameter_override_bundle_ref is not None
                else []
            )
            + (
                [
                    input_ref_from_artifact_ref(
                        request.feedback_config_ref,
                        role="input.feedback_config_ref",
                    )
                ]
                if request.feedback_config_ref is not None
                else []
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ParameterOverrideBundleRef(artifact_id=ref.artifact_id)


def _build_standard_derived_refs(
    exec_artifacts: ExecuteArtifacts,
) -> list[DerivedArtifact]:
    derived_refs = [
        DerivedArtifact(role="metrics", ref=exec_artifacts.metrics_ref),
        DerivedArtifact(role="state_delta", ref=exec_artifacts.state_delta_ref),
    ]
    if exec_artifacts.constraint_report_ref is not None:
        derived_refs.append(
            DerivedArtifact(role="constraint_report", ref=exec_artifacts.constraint_report_ref)
        )
    if exec_artifacts.environment_ref is not None:
        derived_refs.append(
            DerivedArtifact(role="environment_manifest", ref=exec_artifacts.environment_ref)
        )
    if exec_artifacts.method_metric_binding_set_ref is not None:
        derived_refs.append(
            DerivedArtifact(
                role="method_metric_binding_set",
                ref=exec_artifacts.method_metric_binding_set_ref,
            )
        )
    if exec_artifacts.method_execution_bundle_ref is not None:
        derived_refs.append(
            DerivedArtifact(
                role="method_execution_bundle",
                ref=exec_artifacts.method_execution_bundle_ref,
            )
        )
    derived_refs.extend(
        DerivedArtifact(role=role, ref=ref) for role, ref in exec_artifacts.derived_artifacts
    )
    return derived_refs


def _extract_welfare_bound_refs(
    derived_refs: list[DerivedArtifact],
) -> dict[str, WelfareBoundReportRef] | None:
    refs: dict[str, WelfareBoundReportRef] = {}
    prefix = "welfare_bound_report:"
    for item in derived_refs:
        if not item.role.startswith(prefix):
            continue
        node_id = item.role[len(prefix) :].strip()
        if not node_id:
            continue
        refs[node_id] = WelfareBoundReportRef.model_validate(item.ref.model_dump())
    return refs or None


def _evaluate_welfare_bound_requirement(
    store: ArtifactStore,
    *,
    request: ExecuteRequest,
    derived_refs: list[DerivedArtifact],
) -> list[str]:
    from polisyos.core.artifacts import load_core_json_artifact

    if not request.welfare_bound_required:
        return []
    if request.welfare_bound_mode not in {"ex_ante", "ex_post", "both"}:
        return [f"invalid_welfare_bound_mode:{request.welfare_bound_mode}"]
    report_refs = [
        item.ref for item in derived_refs if item.role.startswith("welfare_bound_report:")
    ]
    if not report_refs:
        return ["missing_required_welfare_bound_reports"]

    failures: list[str] = []
    for ref in report_refs:
        payload = load_core_json_artifact(store, ref)
        status = str(payload.get("status", "")).strip().lower()
        if status == "ok":
            continue
        node_id = str(payload.get("node_id") or "unknown")
        mechanism_type = str(payload.get("mechanism_type") or "unknown")
        failures.append(f"required_welfare_bound_failed:{mechanism_type}:{node_id}:{status}")
    return failures


def _persist_feedback_trace(
    store: ArtifactStore,
    *,
    outcome: SolveOutcome,
    request: ExecuteRequest,
) -> FeedbackTraceRef:
    trace = FeedbackTrace(
        schema_version="1.0",
        records=[
            FeedbackIterationRecord(
                stage_alpha=float(record.stage_alpha),
                iteration=int(record.iteration),
                residual_norm=float(record.residual_norm),
                step_norm=float(record.step_norm),
                damping=float(record.damping),
                method=record.method,
                accepted=bool(record.accepted),
                iterate=np.asarray(record.iterate, dtype=float).tolist(),
                residual=np.asarray(record.residual, dtype=float).tolist(),
                diagnostics=_sanitize_diagnostics(record.diagnostics),
                notes=list(record.notes),
            )
            for record in outcome.trace
        ],
        notes=["feedback_mode:fixed_point"],
    )
    ref = store.put_json(
        trace,
        PutOptions(
            kind="foundry.feedback_trace",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.FeedbackTrace", version="1.0"),
            inputs=[
                input_ref_from_artifact_ref(request.exec_plan_ref, role="exec_plan"),
            ]
            + (
                [
                    input_ref_from_artifact_ref(
                        request.feedback_config_ref,
                        role="input.feedback_config_ref",
                    )
                ]
                if request.feedback_config_ref is not None
                else []
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return FeedbackTraceRef(artifact_id=ref.artifact_id)


def _persist_feedback_jacobian(
    store: ArtifactStore,
    *,
    outcome: SolveOutcome,
    request: ExecuteRequest,
    trace_ref: FeedbackTraceRef,
) -> FeedbackJacobianDiagnosticsRef | None:
    if outcome.jacobian is None:
        return None
    diagnostics = FeedbackJacobianDiagnostics(
        schema_version="1.0",
        dimension=int(outcome.jacobian.matrix.shape[0]),
        jacobian=np.asarray(outcome.jacobian.matrix, dtype=float).tolist(),
        spectral_radius=outcome.jacobian.spectral_radius,
        operator_norm_inf=outcome.jacobian.operator_norm_inf,
        condition_number=outcome.jacobian.condition_number,
        smallest_singular_value_i_minus_j=(outcome.jacobian.smallest_singular_value_i_minus_j),
        near_fold=outcome.jacobian.near_fold,
        near_flip=outcome.jacobian.near_flip,
        near_loss_of_stability=outcome.jacobian.near_loss_of_stability,
        near_bifurcation=outcome.jacobian.near_bifurcation,
        notes=list(outcome.jacobian.notes),
    )
    ref = store.put_json(
        diagnostics,
        PutOptions(
            kind="foundry.feedback_jacobian_diagnostics",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.FeedbackJacobianDiagnostics", version="1.0"),
            inputs=[
                input_ref_from_artifact_ref(trace_ref, role="artifact.feedback_trace_ref"),
            ]
            + (
                [
                    input_ref_from_artifact_ref(
                        request.feedback_config_ref,
                        role="input.feedback_config_ref",
                    )
                ]
                if request.feedback_config_ref is not None
                else []
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return FeedbackJacobianDiagnosticsRef(artifact_id=ref.artifact_id)


def _feedback_convergence_status(
    status: str,
) -> Literal[
    "converged",
    "max_iter_exceeded",
    "restarts_exhausted",
    "diverged",
    "oscillating",
    "stagnated",
    "failed",
]:
    """Retain only the existing convergence status vocabulary."""
    if status == "converged":
        return "converged"
    if status == "max_iter_exceeded":
        return "max_iter_exceeded"
    if status == "restarts_exhausted":
        return "restarts_exhausted"
    if status == "diverged":
        return "diverged"
    if status == "oscillating":
        return "oscillating"
    if status == "stagnated":
        return "stagnated"
    if status == "failed":
        return "failed"
    return "failed"


def _persist_feedback_convergence_certificate(
    store: ArtifactStore,
    *,
    outcome: SolveOutcome,
    request: ExecuteRequest,
    prepared: PreparedFeedbackConfig,
    trace_ref: FeedbackTraceRef,
    jacobian_ref: FeedbackJacobianDiagnosticsRef | None,
) -> FeedbackConvergenceCertificateRef:
    final_record = outcome.trace[-1] if outcome.trace else None
    diagnostics = _sanitize_diagnostics(outcome.final_diagnostics)
    status = _feedback_convergence_status(outcome.status)
    certificate = FeedbackConvergenceCertificate(
        schema_version="1.0",
        status=status,
        converged=bool(outcome.converged),
        final_stage_alpha=float(final_record.stage_alpha) if final_record is not None else None,
        final_iteration=int(final_record.iteration) if final_record is not None else None,
        final_residual_norm=(
            None if outcome.final_residual_norm is None else float(outcome.final_residual_norm)
        ),
        final_step_norm=None if outcome.final_step_norm is None else float(outcome.final_step_norm),
        budget_gap=None if outcome.final_budget_gap is None else float(outcome.final_budget_gap),
        budget_tolerance=prepared.config.solver.budget_tolerance,
        multiple_fixed_points=bool(outcome.alternative_solutions)
        or bool(diagnostics.get("multiple_fixed_points", False)),
        oscillation_detected=bool(diagnostics.get("oscillation_detected", False)),
        divergence_detected=bool(diagnostics.get("divergence_detected", False)),
        stagnation_detected=bool(diagnostics.get("stagnation_detected", False)),
        near_bifurcation=bool(diagnostics.get("near_bifurcation", False)),
        notes=(
            ["feedback_mode:fixed_point"]
            + ([f"failure_reason:{outcome.failure_reason}"] if outcome.failure_reason else [])
        ),
    )
    inputs = [
        input_ref_from_artifact_ref(request.exec_plan_ref, role="exec_plan"),
        input_ref_from_artifact_ref(trace_ref, role="artifact.feedback_trace_ref"),
    ]
    if request.feedback_config_ref is not None:
        inputs.append(
            input_ref_from_artifact_ref(
                request.feedback_config_ref,
                role="input.feedback_config_ref",
            )
        )
    if jacobian_ref is not None:
        inputs.append(
            input_ref_from_artifact_ref(
                jacobian_ref,
                role="artifact.feedback_jacobian_diagnostics_ref",
            )
        )
    ref = store.put_json(
        certificate,
        PutOptions(
            kind="foundry.feedback_convergence_certificate",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.core.FeedbackConvergenceCertificate",
                version="1.0",
            ),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return FeedbackConvergenceCertificateRef(artifact_id=ref.artifact_id)


def _persist_equilibrium_multiplicity_report(
    store: ArtifactStore,
    *,
    request: ExecuteRequest,
    report: EquilibriumMultiplicityReport,
    trace_ref: FeedbackTraceRef,
    jacobian_ref: FeedbackJacobianDiagnosticsRef | None,
    convergence_certificate_ref: FeedbackConvergenceCertificateRef,
) -> EquilibriumMultiplicityReportRef:
    inputs = [
        input_ref_from_artifact_ref(request.exec_plan_ref, role="exec_plan"),
        input_ref_from_artifact_ref(trace_ref, role="artifact.feedback_trace_ref"),
        input_ref_from_artifact_ref(
            convergence_certificate_ref,
            role="artifact.feedback_convergence_certificate_ref",
        ),
    ]
    if request.feedback_config_ref is not None:
        inputs.append(
            input_ref_from_artifact_ref(
                request.feedback_config_ref,
                role="input.feedback_config_ref",
            )
        )
    if jacobian_ref is not None:
        inputs.append(
            input_ref_from_artifact_ref(
                jacobian_ref,
                role="artifact.feedback_jacobian_diagnostics_ref",
            )
        )
    ref = store.put_json(
        report,
        PutOptions(
            kind="foundry.equilibrium_multiplicity_report",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.core.EquilibriumMultiplicityReport",
                version="1.0",
            ),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return EquilibriumMultiplicityReportRef(artifact_id=ref.artifact_id)


def _persist_feedback_result(
    store: ArtifactStore,
    *,
    request: ExecuteRequest,
    prepared: PreparedFeedbackConfig,
    exec_artifacts: ExecuteArtifacts | None,
    initial_feedback_state: FeedbackStateSnapshot,
    final_feedback_state: FeedbackStateSnapshot,
    final_feedback_diagnostics: Mapping[str, object],
    final_override_bundle_ref: ParameterOverrideBundleRef | None,
    trace_ref: FeedbackTraceRef,
    jacobian_ref: FeedbackJacobianDiagnosticsRef | None,
    convergence_certificate_ref: FeedbackConvergenceCertificateRef | None,
    multiplicity_report_ref: EquilibriumMultiplicityReportRef | None,
    status: str,
    converged: bool,
    failure_reason: str | None,
    alternative_solutions: tuple[AlternativeSolution, ...],
    notes: list[str],
) -> FeedbackResultRef:
    result = FeedbackSolveResult(
        schema_version="1.0",
        status=status,
        converged=converged,
        initial_state=initial_feedback_state,
        final_state=final_feedback_state,
        trace_ref=trace_ref,
        jacobian_diagnostics_ref=jacobian_ref,
        convergence_certificate_ref=convergence_certificate_ref,
        final_parameter_override_bundle_ref=final_override_bundle_ref,
        multiplicity_report_ref=multiplicity_report_ref,
        alternative_fixed_points=[
            FeedbackFixedPointCandidate(
                state=snapshot_from_vector(
                    prepared,
                    np.asarray(candidate.solution, dtype=float),
                    notes=list(candidate.notes),
                ),
                residual_norm=(
                    None if candidate.residual_norm is None else float(candidate.residual_norm)
                ),
                diagnostics=_sanitize_diagnostics(candidate.diagnostics),
                notes=list(candidate.notes),
            )
            for candidate in alternative_solutions
        ],
        failure_reason=failure_reason,
        final_diagnostics=_sanitize_diagnostics(final_feedback_diagnostics),
        notes=notes,
    )
    inputs = [
        input_ref_from_artifact_ref(request.exec_plan_ref, role="exec_plan"),
        input_ref_from_artifact_ref(trace_ref, role="artifact.feedback_trace_ref"),
    ]
    if exec_artifacts is not None:
        inputs.append(input_ref_from_artifact_ref(exec_artifacts.metrics_ref, role="metrics"))
    if request.feedback_config_ref is not None:
        inputs.append(
            input_ref_from_artifact_ref(
                request.feedback_config_ref,
                role="input.feedback_config_ref",
            )
        )
    if jacobian_ref is not None:
        inputs.append(
            input_ref_from_artifact_ref(
                jacobian_ref,
                role="artifact.feedback_jacobian_diagnostics_ref",
            )
        )
    if convergence_certificate_ref is not None:
        inputs.append(
            input_ref_from_artifact_ref(
                convergence_certificate_ref,
                role="artifact.feedback_convergence_certificate_ref",
            )
        )
    if final_override_bundle_ref is not None:
        inputs.append(
            input_ref_from_artifact_ref(
                final_override_bundle_ref,
                role="feedback.parameter_override_bundle",
            )
        )
    if multiplicity_report_ref is not None:
        inputs.append(
            input_ref_from_artifact_ref(
                multiplicity_report_ref,
                role="artifact.equilibrium_multiplicity_report_ref",
            )
        )
    ref = store.put_json(
        result,
        PutOptions(
            kind="foundry.feedback_result",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.FeedbackSolveResult", version="1.0"),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=request.return_selected_profile,
    )
    if request.return_selected_profile:
        return FeedbackResultRef.model_validate(ref.model_dump(mode="python"))
    return FeedbackResultRef(artifact_id=ref.artifact_id)


def _sanitize_diagnostics(values: Mapping[str, object]) -> dict[str, object]:
    sanitized: dict[str, object] = {}
    for key, value in values.items():
        sanitized[key] = _sanitize_value(value)
    return sanitized


def _sanitize_value(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, (np.floating, float)):
        return float(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.ndarray):
        return [_sanitize_value(item) for item in value.tolist()]
    if isinstance(value, dict):
        return {str(key): _sanitize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_value(item) for item in value]
    return str(value)
