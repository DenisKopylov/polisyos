"""One owner-replayed same-input identity for the SQL-backed ex-ante Debug path.

This private slice establishes input identity only. It is not a source-currentness,
scientific, legal, or publication authorization, and is not a generic method owner.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, NoReturn, cast, get_args, get_origin

from polisyos.core.artifacts import ArtifactRef, InputRef, artifact_ref_identity_key
from polisyos.core.security import AccessScope, get_current_access_scope_or_none
from polisyos.runtime.quality.authority import (
    _VERIFIED_CLOSURE_KEY,
    AuthorityEnvelopeError,
    ClosureCasIdentity,
    ClosureMemberContract,
    ClosureOwnerValueIdentity,
    SameInputClosure,
    SameInputClosureContract,
    VerifiedSameInputClosure,
    _same_input_closure_projection_sha256,
)

if TYPE_CHECKING:
    from pydantic import BaseModel

    from polisyos.core.artifacts import ArtifactManifest
    from polisyos.runtime.http.services.control import ControlPlaneService
    from polisyos.scientist.compute import MethodMetricSourceReadBudget as _ProjectionReadBudget

EXECUTION_INPUT_IDENTITY_PURPOSE: Literal["execution_input_identity_only"] = (
    "execution_input_identity_only"
)
_OWNER_ID = "polisyos.runtime.quality.owned_execution_identity"
_LAW = "restricted-exante-sql-source@1.0"


@dataclass(frozen=True, slots=True)
class _ReplayedIdentity:
    """One in-process, freshly rebuilt owner result; never persisted as a grant."""

    closure: SameInputClosure
    contract: SameInputClosureContract


def _fail(reason: str) -> NoReturn:
    raise AuthorityEnvelopeError("same_input_closure_" + reason)


def _scope_identity(scope: AccessScope) -> tuple[object, ...]:
    """Snapshot all access-scope fields that can distinguish the live principal."""
    return (
        scope.tenant_id,
        scope.cell_id,
        scope.principal_type,
        scope.user_sub,
        tuple(sorted(str(role.value) for role in scope.roles)),
        str(scope.max_pii_tier.value),
        scope.mfa_verified,
        scope.spiffe_id,
        scope.delegation_jti,
        scope.jwt_jti,
    )


def _manifest_member(
    *, name: str, role: str, ref: ArtifactRef, manifest: ArtifactManifest
) -> ClosureCasIdentity:
    """Retain exact observed metadata; absence is not an invented producer."""
    schema = manifest.artifact_schema
    producer = manifest.producer
    return ClosureCasIdentity(
        name=name,
        role=role,
        artifact_ref=ref,
        schema_name=None if schema is None else schema.name,
        schema_version=None if schema is None else schema.version,
        producer_component=None if producer is None else str(producer.component),
        producer_version=None if producer is None else producer.version,
    )


def _edge_text(edge: InputRef) -> str:
    """Preserve this owner's ordered role-qualified selected edge without guessing."""
    return json.dumps(edge.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


class _RestrictedExecutionIdentityOwner:
    """Concrete Runtime replayer; caller callbacks cannot replace this owner.

    A token holds the installed control service and the lookup key, but no claimed
    member list. Every use re-enters current request scope, completed owner
    selection, restricted dispatch verifier, bounded source and selected bytes.
    """

    __slots__ = (
        "_aggregate_read_budget",
        "_control",
        "_run_id",
        "_scope",
        "_sealed",
        "_simulation_key",
    )

    def __init__(
        self,
        *,
        control: ControlPlaneService,
        run_id: str,
        simulation_ref: ArtifactRef,
        aggregate_read_budget: _ProjectionReadBudget,
    ) -> None:
        from polisyos.runtime.http.services.control import ControlPlaneService
        from polisyos.scientist.compute import (
            MethodMetricSourceReadBudget as _ProjectionReadBudget,
        )

        scope = get_current_access_scope_or_none()
        if (
            type(control) is not ControlPlaneService
            or type(aggregate_read_budget) is not _ProjectionReadBudget
            or aggregate_read_budget.parent is not None
            or type(scope) is not AccessScope
            or not scope.tenant_id
            or not scope.cell_id
            or not (scope.user_sub or scope.spiffe_id)
            or type(run_id) is not str
            or not run_id
            or not isinstance(simulation_ref, ArtifactRef)
            or simulation_ref.manifest_profile_sha256 is None
        ):
            _fail("debug_owner_or_access_scope_not_established")
        object.__setattr__(self, "_aggregate_read_budget", aggregate_read_budget)
        object.__setattr__(self, "_control", control)
        object.__setattr__(self, "_run_id", run_id)
        object.__setattr__(self, "_scope", _scope_identity(scope))
        object.__setattr__(self, "_simulation_key", artifact_ref_identity_key(simulation_ref))
        object.__setattr__(self, "_sealed", True)

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, "_sealed", False):
            raise AttributeError("restricted_execution_identity_owner_is_immutable")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        raise AttributeError("restricted_execution_identity_owner_is_immutable")

    def replay(self) -> _ReplayedIdentity:
        """Re-enter the actual completed source and build its complete owned basis."""
        from polisyos.core.contracts import (
            GraphMethodExecutionSelection,
            MethodExecutionBundle,
            ProgramGraph,
            SimulationResultRef,
            StateSnapshot,
        )
        from polisyos.foundry.execute import (
            admit_execution_source_bounded,
            execution_input_basis_sources,
        )
        from polisyos.runtime.http.resilience import _require_runtime_ambient_ownership
        from polisyos.runtime.http.services.debug_registered_sql import (
            _is_supported_restricted_graph,
            _reconcile_selected_sql_inputs,
        )
        from polisyos.scientist.compute import (
            MAX_METHOD_METRIC_SOURCE_BYTES,
        )
        from polisyos.scientist.compute import (
            BoundedMethodMetricSourceReader as _BoundedExecutionSourceReader,
        )
        from polisyos.scientist.compute import (
            MethodMetricSourceReadBudget as _ProjectionReadBudget,
        )
        from polisyos.scientist.compute import (
            VerifiedRestrictedExAnteCall as _VerifiedRestrictedExAnteCall,
        )
        from polisyos.scientist.compute import (
            read_bounded_method_metric_artifact as _read_bounded_method_metric_artifact,
        )
        from polisyos.scientist.compute import (
            selected_method_metric_ref as _selected_ref,
        )

        control = self._control
        scope = get_current_access_scope_or_none()
        if type(scope) is not AccessScope or _scope_identity(scope) != self._scope:
            _fail("debug_current_access_scope_changed")
        store = control._artifact_store
        _require_runtime_ambient_ownership(store)
        selection = control.get_method_execution_selection(
            run_id=self._run_id,
            tenant_id=scope.tenant_id,
            cell_id=scope.cell_id,
            aggregate_read_budget=self._aggregate_read_budget,
        )
        if (
            type(selection) is not GraphMethodExecutionSelection
            or selection.simulation_result_ref is None
            or artifact_ref_identity_key(selection.simulation_result_ref) != self._simulation_key
            or selection.source_candidate_ref is None
            or selection.method_execution_bundle_ref is None
        ):
            _fail("debug_completed_owner_selection_not_established")

        calls: list[Any] = []
        score = control.read_current_completed_ex_ante_candidate_score(
            run_id=self._run_id,
            tenant_id=scope.tenant_id,
            cell_id=scope.cell_id,
            require_restricted_exante_call_witness=True,
            restricted_exante_call_collector=calls,
            aggregate_read_budget=self._aggregate_read_budget,
        )
        if (
            score.status != "selected"
            or len(calls) != 1
            or type(calls[0]) is not _VerifiedRestrictedExAnteCall
        ):
            _fail("debug_actual_restricted_invocation_not_established")
        call = calls[0]
        budget = _ProjectionReadBudget(parent=self._aggregate_read_budget)
        reader = _BoundedExecutionSourceReader(cast("Any", store), budget)
        sim_ref = SimulationResultRef.model_validate(
            selection.simulation_result_ref.model_dump(mode="python")
        )
        source_bytes_before = budget.observed_execution_source_bytes
        admitted = admit_execution_source_bounded(store, sim_ref, reader=reader)
        basis = admitted.basis
        if (
            admitted.mode != "single_step_basis"
            or basis is None
            or admitted.basis_ref is None
            or admitted.basis_manifest is None
            or admitted.basis_inventory is None
            or basis.registered_sql_admission_ref is None
            or basis.candidate_ref != selection.source_candidate_ref
            or type(admitted.source_read_bytes) is not int
            or admitted.source_read_bytes
            != budget.observed_execution_source_bytes - source_bytes_before
        ):
            _fail("debug_source_basis_not_established")
        _, graph, _, _ = reader.read_typed_model(ProgramGraph, basis.program_graph_ref)
        _, bundle, _, _ = reader.read_typed_model(
            MethodExecutionBundle, selection.method_execution_bundle_ref
        )
        if (
            len(bundle.occurrences) != 1
            or bundle.occurrences[0] != call.occurrence
            or not _is_supported_restricted_graph(graph, method_node_id=call.occurrence.node_id)
            or call.occurrence.dispatch is None
            or call.occurrence.dispatch.input_state_source_ref is None
            or artifact_ref_identity_key(call.occurrence.dispatch.input_state_source_ref)
            != artifact_ref_identity_key(basis.base_state_snapshot_ref)
        ):
            _fail("debug_restricted_graph_or_source_state_mismatch")
        _reconcile_selected_sql_inputs(store, basis=basis, call=call, budget=budget)
        _, state, _, _ = reader.read_typed_model(StateSnapshot, basis.bound_state_snapshot_ref)
        state_blob_key = artifact_ref_identity_key(state.state_ref)

        from polisyos.core.artifacts import SchemaInfo, input_ref_from_artifact_ref
        from polisyos.core.contracts import (
            DataSnapshotOwnerBound,
            ExecPlan,
            ExecutionPlan,
            ExecutionPlanRef,
            FabricBridgeDataSnapshotLineage,
            FoundryExecutionInputBasis,
            FoundryInputBindings,
            LoweredIR,
            MethodMetricBindingSet,
            RegisteredSQLAdmissionBinding,
            RegisteredSQLUseContract,
            WarningsBundle,
            data_snapshot_manifest_inputs_match,
        )
        from polisyos.foundry.compile import (
            TreasuryPlan,
            build_treasury_plan,
            execution_plan_input_refs,
            program_graph_input_refs,
        )
        from polisyos.ir import LinkReport
        from polisyos.ir.kernel import (
            ConstraintRegistry,
            MechanismTypeRegistry,
            MergeRuleRegistry,
            MetricRegistry,
            SelectorFieldRegistry,
            SlotRegistry,
            UnitsRegistry,
        )
        from polisyos.ir.trinity import TrinityBundle
        from polisyos.scientist.adapters import (
            RegisteredSQLCapture,
            RegisteredSQLViewContract,
            registered_sql_capture_input_refs,
        )
        from polisyos.scientist.policy_design import PolicyCandidateSchema

        snapshot_manifest, snapshot, _, _ = reader.read_typed_model(
            DataSnapshotOwnerBound, basis.data_snapshot_ref
        )
        _, bindings, _, _ = reader.read_typed_model(FoundryInputBindings, basis.input_bindings_ref)
        _, sql_binding, _, _ = reader.read_typed_model(
            RegisteredSQLAdmissionBinding, basis.registered_sql_admission_ref
        )
        capture_manifest, capture, _, _ = reader.read_typed_model(
            RegisteredSQLCapture, sql_binding.materialization.producer_capture_ref
        )
        _, view, _, _ = reader.read_typed_model(RegisteredSQLViewContract, capture.view_ref)
        if (
            not isinstance(snapshot.source_lineage, FabricBridgeDataSnapshotLineage)
            or snapshot.data_schema_ref is None
            or snapshot.quality_report_ref is None
            or artifact_ref_identity_key(capture.request_ref)
            != artifact_ref_identity_key(snapshot.source_lineage.data_view_request_ref)
            or artifact_ref_identity_key(capture.request_ref)
            != artifact_ref_identity_key(sql_binding.materialization.request_ref)
            or capture_manifest.inputs
            != registered_sql_capture_input_refs(
                snapshot, basis.data_snapshot_ref, sql_binding.materialization.registration
            )
            or capture.connector_id != view.connector_id
            or capture.config_fingerprint != view.config_fingerprint
            or capture.statement != view.statement
            or capture.parameters != view.parameters
            or capture.page_size != view.page_size
            or artifact_ref_identity_key(capture.snapshot_ref)
            != artifact_ref_identity_key(basis.data_snapshot_ref)
            or artifact_ref_identity_key(capture.payload_ref)
            != artifact_ref_identity_key(snapshot.data_ref)
            or artifact_ref_identity_key(capture.schema_ref)
            != artifact_ref_identity_key(snapshot.data_schema_ref)
            or artifact_ref_identity_key(capture.quality_ref)
            != artifact_ref_identity_key(snapshot.quality_report_ref)
            or artifact_ref_identity_key(capture.view_ref)
            != artifact_ref_identity_key(
                sql_binding.materialization.registration.effective_view_contract_ref
            )
            or artifact_ref_identity_key(capture.use_ref)
            != artifact_ref_identity_key(sql_binding.materialization.registration.use_contract_ref)
        ):
            _fail("debug_sql_capture_selected_inputs_mismatch")
        if not data_snapshot_manifest_inputs_match(
            snapshot,
            snapshot_manifest.inputs,
            schema_version=(
                None
                if snapshot_manifest.artifact_schema is None
                else snapshot_manifest.artifact_schema.version
            ),
        ):
            _fail("debug_snapshot_owner_edges_mismatch")

        # The restricted profile reuses the registry producer's real seven
        # typed owners. Optional families without a typed replay refuse here.
        registry_models: dict[str, tuple[str, type[BaseModel]]] = {
            "slot_registry": ("ir.slot_registry", SlotRegistry),
            "merge_registry": ("ir.merge_rule_registry", MergeRuleRegistry),
            "constraint_registry": ("ir.constraint_registry", ConstraintRegistry),
            "mechanism_registry": ("ir.mechanism_registry", MechanismTypeRegistry),
            "selector_field_registry": ("ir.selector_field_registry", SelectorFieldRegistry),
            "metric_registry": ("ir.metric_registry", MetricRegistry),
            "units_registry": ("ir.units_registry", UnitsRegistry),
        }
        registry_values = basis.binding_registry_members.model_dump(mode="python")
        registry_refs = {
            name: ArtifactRef.model_validate(value)
            for name, value in registry_values.items()
            if value is not None
        }
        if set(registry_refs) - set(registry_models):
            _fail("debug_registry_family_not_supported")
        required_registries = {
            "slot_registry",
            "merge_registry",
            "constraint_registry",
            "mechanism_registry",
        }
        if not required_registries.issubset(registry_refs):
            _fail("debug_required_registry_missing")
        registry_validated: set[tuple[str, str, str, str | None]] = set()

        def validate_registry_source(
            source_role: str, source_ref: ArtifactRef, manifest: ArtifactManifest
        ) -> None:
            if source_role.endswith("_registry_bundle"):
                expected = sorted(
                    (name, str(ref.artifact_id), ref.manifest_profile_sha256)
                    for name, ref in registry_refs.items()
                )
                actual = sorted(
                    (edge.role, str(edge.artifact_id), edge.manifest_profile_sha256)
                    for edge in manifest.inputs
                )
                if (
                    source_ref.kind != "core.registry_bundle"
                    or source_ref.media_type != "application/json"
                    or manifest.artifact_schema is not None
                    or actual != expected
                ):
                    _fail("debug_registry_bundle_contract_mismatch")
                return
            if "_registry_member." not in source_role:
                return
            member = source_role.partition("_registry_member.")[2]
            contract = registry_models.get(member)
            ref = registry_refs.get(member)
            if contract is None or ref is None:
                _fail("debug_registry_member_contract_missing")
            kind, model = contract
            key = artifact_ref_identity_key(source_ref)
            schema = manifest.artifact_schema
            version_field = model.model_fields["schema_version"]
            annotation = version_field.annotation
            supported = (
                set(get_args(annotation))
                if get_origin(annotation) is Literal
                else {version_field.default}
            )
            if (
                key != artifact_ref_identity_key(ref)
                or source_ref.kind != kind
                or source_ref.media_type != "application/json"
                or schema is None
                or schema.name != f"polisyos.ir.kernel.{model.__name__}"
                or schema.version not in supported
                or manifest.inputs
            ):
                _fail("debug_registry_member_schema_mismatch")
            if key not in registry_validated:
                typed_manifest, value, _, _ = reader.read_typed_model(model, source_ref)
                if (
                    typed_manifest != manifest
                    or "schema_version" not in value.model_fields_set
                    or SchemaInfo(name=schema.name, version=getattr(value, "schema_version", ""))
                    != schema
                ):
                    _fail("debug_registry_member_payload_mismatch")
                registry_validated.add(key)

        # Each supported kind maps to its actual installed typed owner and
        # exact accepted schema. Kinds outside this bounded SQL execution
        # profile refuse instead of being admitted as generic JSON.
        typed_contracts: dict[str, tuple[type[BaseModel], str, set[str]]] = {
            "foundry.execution_input_basis": (
                FoundryExecutionInputBasis,
                "polisyos.core.FoundryExecutionInputBasis",
                {"1.1"},
            ),
            "foundry.exec_plan": (ExecPlan, "polisyos.core.ExecPlan", {"0.2.0"}),
            "foundry.program_graph": (ProgramGraph, "polisyos.core.ProgramGraph", {"0.2.0"}),
            "ir.trinity_bundle": (TrinityBundle, "polisyos.ir.TrinityBundle", {"1.0"}),
            "scientist.policy_design.candidate": (
                PolicyCandidateSchema,
                PolicyCandidateSchema.ARTIFACT_SCHEMA_NAME,
                {PolicyCandidateSchema.ARTIFACT_SCHEMA_VERSION},
            ),
            "fabric.data_snapshot": (
                DataSnapshotOwnerBound,
                "polisyos.core.DataSnapshot",
                {"0.3.0"},
            ),
            "foundry.input_bindings": (
                FoundryInputBindings,
                "polisyos.core.FoundryInputBindings",
                {"1.1"},
            ),
            "foundry.state_snapshot": (StateSnapshot, "polisyos.core.StateSnapshot", {"2.2.0"}),
            "foundry.lowered_ir": (LoweredIR, "polisyos.foundry.LoweredIR", {"0.2.0"}),
            "foundry.treasury_plan": (TreasuryPlan, "polisyos.foundry.TreasuryPlan", {"1.0"}),
            "foundry.method_metric_binding_set": (
                MethodMetricBindingSet,
                MethodMetricBindingSet.ARTIFACT_SCHEMA_NAME,
                {MethodMetricBindingSet.ARTIFACT_SCHEMA_VERSION},
            ),
            "scientist.execution_plan": (ExecutionPlan, "polisyos.core.ExecutionPlan", {"1.0"}),
            "compiler.link_report": (LinkReport, "polisyos.ir.LinkReport", {"1.0"}),
            "fabric.registered_sql_admission_binding": (
                RegisteredSQLAdmissionBinding,
                RegisteredSQLAdmissionBinding.ARTIFACT_SCHEMA_NAME,
                {RegisteredSQLAdmissionBinding.ARTIFACT_SCHEMA_VERSION},
            ),
            "fabric.registered_sql_view": (
                RegisteredSQLViewContract,
                RegisteredSQLViewContract.ARTIFACT_SCHEMA_NAME,
                {RegisteredSQLViewContract.ARTIFACT_SCHEMA_VERSION},
            ),
            "fabric.registered_sql_use": (
                RegisteredSQLUseContract,
                RegisteredSQLUseContract.ARTIFACT_SCHEMA_NAME,
                {RegisteredSQLUseContract.ARTIFACT_SCHEMA_VERSION},
            ),
            "fabric.registered_sql_capture": (
                RegisteredSQLCapture,
                RegisteredSQLCapture.ARTIFACT_SCHEMA_NAME,
                {RegisteredSQLCapture.ARTIFACT_SCHEMA_VERSION},
            ),
            "fabric.warnings": (WarningsBundle, "polisyos.core.WarningsBundle", {"1.0"}),
        }
        simple_contracts = {
            "ir.data_view_request": ("polisyos.ir.DataViewRequest", "1.0"),
            "fabric.tabular_payload": ("polisyos.fabric.TabularPayload", "1.0"),
            "fabric.data_schema": ("polisyos.fabric.DataSchema", "1.1"),
            "fabric.quality_report": ("polisyos.fabric.DataQualityReport", "1.1"),
        }
        typed_validated: set[tuple[str, str, str, str | None]] = set()
        members: list[ClosureCasIdentity | ClosureOwnerValueIdentity] = []
        observed_edges: list[InputRef] = []
        json_verified = set(budget.payload_refs)
        checked_simple: set[tuple[str, str, str, str | None]] = set()

        def record_selected(
            edge: InputRef, selected_ref: ArtifactRef, manifest: ArtifactManifest
        ) -> None:
            if selected_ref.manifest_profile_sha256 is None:
                _fail("debug_source_selected_profile_missing")
            key = artifact_ref_identity_key(selected_ref)
            if selected_ref.media_type == "application/json":
                typed = typed_contracts.get(selected_ref.kind)
                simple_schema = simple_contracts.get(selected_ref.kind)
                registry_kind = selected_ref.kind == "core.registry_bundle" or any(
                    selected_ref.kind == item[0] for item in registry_models.values()
                )
                if not registry_kind and typed is None and simple_schema is None:
                    _fail("debug_source_kind_not_supported")
                schema = manifest.artifact_schema
                if typed is not None:
                    model, schema_name, versions = typed
                    if (
                        schema is None
                        or schema.name != schema_name
                        or schema.version not in versions
                    ):
                        _fail("debug_source_schema_mismatch")
                    if key not in typed_validated:
                        checked_manifest, value, _, _ = reader.read_typed_model(model, selected_ref)
                        if checked_manifest != manifest:
                            _fail("debug_source_typed_manifest_mismatch")
                        versioned_kinds = {
                            "foundry.execution_input_basis",
                            "foundry.program_graph",
                            "ir.trinity_bundle",
                            "scientist.policy_design.candidate",
                            "foundry.input_bindings",
                            "foundry.state_snapshot",
                            "foundry.lowered_ir",
                            "foundry.treasury_plan",
                            "foundry.method_metric_binding_set",
                            "scientist.execution_plan",
                            "compiler.link_report",
                            "fabric.registered_sql_admission_binding",
                            "fabric.registered_sql_view",
                            "fabric.registered_sql_use",
                            "fabric.registered_sql_capture",
                        }
                        payload_version = {
                            "foundry.program_graph": "0.2",
                            "foundry.lowered_ir": "0.2",
                            "foundry.state_snapshot": "2.2",
                        }.get(selected_ref.kind, schema.version)
                        if selected_ref.kind in versioned_kinds and (
                            "schema_version" not in value.model_fields_set
                            or getattr(value, "schema_version", None) != payload_version
                        ):
                            _fail("debug_source_payload_schema_version_mismatch")
                        if selected_ref.kind == "foundry.state_snapshot" and (
                            not isinstance(value, StateSnapshot)
                            or value.schema_version != "2.2"
                            or StateSnapshot.SCHEMA_MANIFEST_VERSION_BY_PAYLOAD_VERSION.get(
                                value.schema_version
                            )
                            != schema.version
                        ):
                            _fail("debug_state_snapshot_schema_mismatch")
                        typed_validated.add(key)
                if simple_schema is not None and (
                    schema != SchemaInfo(name=simple_schema[0], version=simple_schema[1])
                ):
                    _fail("debug_source_schema_mismatch")
                if key in json_verified:
                    if budget.manifests.get(key) != manifest:
                        _fail("debug_source_manifest_changed_during_read")
                else:
                    result = _read_bounded_method_metric_artifact(
                        cast("Any", store),
                        ref=_selected_ref(selected_ref, kind=selected_ref.kind),
                        max_bytes=MAX_METHOD_METRIC_SOURCE_BYTES,
                        read_budget=budget,
                    )
                    if result.manifest != manifest:
                        _fail("debug_source_manifest_changed_during_read")
                    if selected_ref.kind in {"fabric.data_schema", "fabric.quality_report"}:
                        value = result.value
                        required = (
                            {"schema_id", "schema_version", "sql_columns"}
                            if selected_ref.kind == "fabric.data_schema"
                            else {
                                "dataset_id",
                                "schema_id",
                                "score",
                                "tier",
                                "grade",
                                "freshness_status",
                                "violations",
                                "validated_at",
                                "row_count",
                                "quality_flags",
                            }
                        )
                        if not isinstance(value, dict) or set(value) != required:
                            _fail("debug_source_payload_shape_mismatch")
                        if selected_ref.kind == "fabric.data_schema" and value.get(
                            "sql_columns"
                        ) != [
                            {"name": name, "dtype": dtype}
                            for name, dtype in zip(capture.columns, capture.dtypes, strict=True)
                        ]:
                            _fail("debug_sql_capture_columns_mismatch")
                        checked_simple.add(key)
                    json_verified.add(key)
                if (
                    selected_ref.kind in {"fabric.data_schema", "fabric.quality_report"}
                    and key not in checked_simple
                ):
                    _fail("debug_source_payload_shape_not_established")
            elif selected_ref.kind == "foundry.state_blob" and key == state_blob_key:
                # The selected typed StateSnapshot edge and full actual NPZ
                # bytes were independently reconciled immediately above.
                pass
            else:
                _fail("debug_source_binary_not_established")
            observed_edges.append(edge)
            members.append(
                _manifest_member(
                    name=f"input.{len(members):04d}",
                    role=edge.role,
                    ref=selected_ref,
                    manifest=manifest,
                )
            )

        basis_edge = InputRef(
            artifact_id=admitted.basis_ref.artifact_id,
            role="basis.execution_input_basis",
            manifest_profile_sha256=admitted.basis_ref.manifest_profile_sha256,
        )
        record_selected(basis_edge, admitted.basis_ref, admitted.basis_manifest)

        def validate_parent(
            role: str,
            manifest: ArtifactManifest,
            children: list[tuple[InputRef, ArtifactRef, ArtifactManifest]],
        ) -> None:
            if role.endswith("_registry_bundle") or "_registry_member." in role:
                return
            source_kinds = {
                "exec_plan": "foundry.exec_plan",
                "program_graph": "foundry.program_graph",
                "trinity_bundle": "ir.trinity_bundle",
                "candidate": "scientist.policy_design.candidate",
                "candidate_data_snapshot": "fabric.data_snapshot",
                "actual_data_snapshot": "fabric.data_snapshot",
                "input_bindings": "foundry.input_bindings",
                "bound_state_snapshot": "foundry.state_snapshot",
                "base_state_snapshot": "foundry.state_snapshot",
                "registered_sql_admission": "fabric.registered_sql_admission_binding",
            }
            if manifest.kind != source_kinds.get(role):
                _fail("debug_source_role_kind_mismatch")
            snapshot_kinds = {
                "data_view_request_ref": "ir.data_view_request",
                "data_ref": "fabric.tabular_payload",
                "data_schema_ref": "fabric.data_schema",
                "quality_report_ref": "fabric.quality_report",
                "warnings_ref": "fabric.warnings",
            }
            parent_kinds = {
                "exec_plan": {
                    "program_graph": "foundry.program_graph",
                    "treasury_plan": "foundry.treasury_plan",
                    "method_metric_bindings": "foundry.method_metric_binding_set",
                },
                "program_graph": {
                    "ir": "ir.trinity_bundle",
                    "registry_bundle": "core.registry_bundle",
                    "link_report": "compiler.link_report",
                    "lowered_ir": "foundry.lowered_ir",
                    "execution_plan_source": "scientist.execution_plan",
                },
                "trinity_bundle": {"policy_candidate": "scientist.policy_design.candidate"},
                "candidate": {
                    "world_model_data_snapshot": "fabric.data_snapshot",
                    "world_model_registry": "core.registry_bundle",
                },
                "candidate_data_snapshot": snapshot_kinds,
                "actual_data_snapshot": snapshot_kinds,
                "input_bindings": {
                    "input.data_snapshot_ref": "fabric.data_snapshot",
                    "input.registry_bundle_ref": "core.registry_bundle",
                    "artifact.bound_state_snapshot_ref": "foundry.state_snapshot",
                    "input.registered_sql_admission_ref": "fabric.registered_sql_admission_binding",
                    "input.quality_report_ref": "fabric.quality_report",
                },
                "bound_state_snapshot": {
                    "input.data_snapshot_ref": "fabric.data_snapshot",
                    "input.registry_bundle_ref": "core.registry_bundle",
                    "state_blob": "foundry.state_blob",
                },
                "base_state_snapshot": {
                    "input.data_snapshot_ref": "fabric.data_snapshot",
                    "input.registry_bundle_ref": "core.registry_bundle",
                    "state_blob": "foundry.state_blob",
                },
                "registered_sql_admission": {
                    "source.snapshot": "fabric.data_snapshot",
                    "source.view": "fabric.registered_sql_view",
                    "source.use": "fabric.registered_sql_use",
                    "source.capture": "fabric.registered_sql_capture",
                    **{f"snapshot.{key}": value for key, value in snapshot_kinds.items()},
                },
            }
            expected_kinds = parent_kinds.get(role, {})
            for edge, child_ref, _ in children[1:]:
                edge_role = edge.role.removeprefix(f"basis.edge.{role}.")
                if child_ref.kind != expected_kinds.get(edge_role):
                    _fail("debug_source_edge_role_kind_mismatch")
            actual = manifest.inputs
            expected: list[InputRef] | None = None
            if role == "exec_plan":
                by_role = {
                    edge.role.removeprefix("basis.edge.exec_plan."): (ref, child_manifest)
                    for edge, ref, child_manifest in children[1:]
                }
                try:
                    treasury_ref, treasury_manifest = by_role["treasury_plan"]
                    binding_ref, binding_manifest = by_role["method_metric_bindings"]
                except KeyError:
                    _fail("debug_exec_plan_input_roles_mismatch")
                if artifact_ref_identity_key(binding_ref) != artifact_ref_identity_key(
                    selection.method_metric_binding_set_ref
                ):
                    _fail("debug_exec_plan_binding_selection_mismatch")
                _, plan, _, _ = reader.read_typed_model(ExecPlan, basis.exec_plan_ref)
                _, treasury, _, _ = reader.read_typed_model(TreasuryPlan, treasury_ref)
                if treasury != build_treasury_plan(
                    graph, root_seed=plan.random_seed or 0
                ) or treasury_manifest.inputs != [
                    input_ref_from_artifact_ref(basis.program_graph_ref, role="program_graph")
                ]:
                    _fail("debug_exec_plan_treasury_replay_mismatch")
                _, metric_set, _, _ = reader.read_typed_model(MethodMetricBindingSet, binding_ref)
                if (
                    artifact_ref_identity_key(metric_set.program_graph_ref)
                    != artifact_ref_identity_key(basis.program_graph_ref)
                    or artifact_ref_identity_key(metric_set.policy_ref)
                    != artifact_ref_identity_key(basis.trinity_bundle_ref)
                    or artifact_ref_identity_key(metric_set.registry_bundle_ref)
                    != artifact_ref_identity_key(basis.compile_registry_ref)
                    or basis.compile_registry_members.metric_registry is None
                    or basis.compile_registry_members.units_registry is None
                    or artifact_ref_identity_key(metric_set.metric_registry_ref)
                    != artifact_ref_identity_key(basis.compile_registry_members.metric_registry)
                    or artifact_ref_identity_key(metric_set.units_registry_ref)
                    != artifact_ref_identity_key(basis.compile_registry_members.units_registry)
                    or binding_manifest.inputs
                    != [
                        input_ref_from_artifact_ref(
                            metric_set.program_graph_ref, role="program_graph"
                        ),
                        input_ref_from_artifact_ref(metric_set.policy_ref, role="policy"),
                        input_ref_from_artifact_ref(
                            metric_set.registry_bundle_ref, role="registry_bundle"
                        ),
                        input_ref_from_artifact_ref(
                            metric_set.metric_registry_ref, role="metric_registry"
                        ),
                        input_ref_from_artifact_ref(
                            metric_set.units_registry_ref, role="units_registry"
                        ),
                    ]
                ):
                    _fail("debug_exec_plan_metric_binding_mismatch")
                expected = execution_plan_input_refs(
                    program_graph_ref=basis.program_graph_ref,
                    treasury_plan_ref=treasury_ref,
                    method_metric_binding_set_ref=selection.method_metric_binding_set_ref,
                )
            elif role == "program_graph":
                # Derive the exact closure and order from the same compiler owner.
                by_role = {
                    edge.role.removeprefix("basis.edge.program_graph."): ref
                    for edge, ref, _ in children[1:]
                }
                if (
                    "link_report" not in by_role
                    or "execution_plan_source" not in by_role
                    or by_role["link_report"].kind != "compiler.link_report"
                    or by_role["execution_plan_source"].kind != "scientist.execution_plan"
                ):
                    _fail("debug_program_graph_input_kind_mismatch")
                expected = program_graph_input_refs(
                    policy_ref=basis.trinity_bundle_ref,
                    registry_bundle_ref=basis.compile_registry_ref,
                    link_report_ref=by_role["link_report"],
                    lowered_ir_ref=graph.lowered_ir_ref,
                    params_refs={},
                    method_execution_plan_ref=ExecutionPlanRef.model_validate(
                        by_role["execution_plan_source"].model_dump(mode="python")
                    ),
                )
            elif role == "trinity_bundle":
                expected = [
                    input_ref_from_artifact_ref(basis.candidate_ref, role="policy_candidate")
                ]
            elif role == "candidate":
                expected = [
                    input_ref_from_artifact_ref(
                        basis.candidate_data_snapshot_ref, role="world_model_data_snapshot"
                    ),
                    input_ref_from_artifact_ref(
                        basis.candidate_registry_bundle_ref, role="world_model_registry"
                    ),
                ]
            elif role in {"candidate_data_snapshot", "actual_data_snapshot"}:
                if manifest != snapshot_manifest:
                    _fail("debug_snapshot_selected_manifest_mismatch")
                return
            elif role == "input_bindings":
                expected = [
                    input_ref_from_artifact_ref(
                        basis.data_snapshot_ref, role="input.data_snapshot_ref"
                    ),
                    input_ref_from_artifact_ref(
                        basis.binding_registry_ref, role="input.registry_bundle_ref"
                    ),
                    input_ref_from_artifact_ref(
                        basis.bound_state_snapshot_ref, role="artifact.bound_state_snapshot_ref"
                    ),
                    input_ref_from_artifact_ref(
                        basis.registered_sql_admission_ref,
                        role="input.registered_sql_admission_ref",
                    ),
                ]
                if bindings.quality_report_ref is not None:
                    expected.append(
                        input_ref_from_artifact_ref(
                            bindings.quality_report_ref, role="input.quality_report_ref"
                        )
                    )
            elif role in {"bound_state_snapshot", "base_state_snapshot"}:
                expected = state.lineage_inputs
            elif role == "registered_sql_admission":
                expected = registered_sql_capture_input_refs(
                    snapshot, basis.data_snapshot_ref, sql_binding.materialization.registration
                )
                expected.append(
                    input_ref_from_artifact_ref(
                        sql_binding.materialization.producer_capture_ref, role="source.capture"
                    )
                )
            else:
                _fail("debug_source_role_not_supported")
            if expected is None or actual != expected:
                _fail("debug_source_parent_edges_mismatch")

        # This is the Foundry source owner's ordered enumeration, not a list
        # supplied by the reporting caller. Resolve every direct selected edge.
        for source_role, source_ref in execution_input_basis_sources(basis):
            source_manifest, _ = reader.read_selected_manifest(source_ref)
            validate_registry_source(source_role, source_ref, source_manifest)
            source_edge = InputRef(
                artifact_id=source_ref.artifact_id,
                role=f"basis.source.{source_role}",
                manifest_profile_sha256=source_ref.manifest_profile_sha256,
            )
            rows = [(source_edge, source_ref, source_manifest)]
            for edge in source_manifest.inputs:
                child_ref, child_manifest, _ = reader.read_edge_manifest(source_ref, edge)
                rows.append(
                    (
                        InputRef(
                            artifact_id=edge.artifact_id,
                            role=f"basis.edge.{source_role}.{edge.role}",
                            manifest_profile_sha256=edge.manifest_profile_sha256,
                        ),
                        child_ref,
                        child_manifest,
                    )
                )
            validate_parent(source_role, source_manifest, rows)
            for edge, selected_ref, manifest in rows:
                record_selected(edge, selected_ref, manifest)
        if tuple(observed_edges) != (basis_edge, *admitted.basis_inventory):
            _fail("debug_source_inventory_or_order_mismatch")
        if admitted.basis_manifest.inputs != list(admitted.basis_inventory):
            _fail("debug_source_producer_inventory_order_mismatch")

        witness = call.witness
        inputs = call.input_values
        if tuple(item.slot_id for item in inputs) != ("baseline", "scenario"):
            _fail("debug_actual_input_order_not_established")
        # Capture identities, not array contents, and never include output refs,
        # receipt time, or the random closure locator in the input projection.
        members.append(
            ClosureOwnerValueIdentity(
                name="restricted_execution",
                role="method.execution_input_identity",
                owner=_OWNER_ID,
                rule_version=_LAW,
                value={
                    "profile_id": witness.profile_id,
                    "profile_revision_sha256": witness.profile_revision_sha256,
                    "method_abi_digest": witness.method_abi_digest,
                    "method_callable_sha256": witness.method_callable_sha256,
                    "runner_callable_sha256": witness.runner_callable_sha256,
                    "backend_runtime_fingerprint": witness.backend_runtime_fingerprint,
                    "state_reads": list(witness.state_reads),
                    "parameter_reads": list(witness.parameter_reads),
                    "parameter_origin": witness.parameter_origin,
                    "poverty_line": None,
                    "inputs": [
                        {
                            "slot_id": item.slot_id,
                            "dtype": item.dtype,
                            "shape": list(item.shape),
                            "value_sha256": item.value_sha256,
                        }
                        for item in inputs
                    ],
                },
            )
        )
        contract = SameInputClosureContract(
            owner=_OWNER_ID,
            purpose=EXECUTION_INPUT_IDENTITY_PURPOSE,
            rule_version=_LAW,
            members=tuple(
                ClosureMemberContract(
                    name=member.name,
                    role=member.role,
                    identity_domain=member.identity_domain,
                    required=True,
                )
                for member in members
            ),
        )
        refs = tuple(_edge_text(edge) for edge in observed_edges)
        closure = SameInputClosure(
            schema_version="2.0",
            closure_id=f"{selection.job_id}:restricted-exante-inputs",
            status="closed",
            run_id=self._run_id,
            job_id=selection.job_id,
            tenant_id=scope.tenant_id,
            cell_id=scope.cell_id,
            members=tuple(members),
            evidence_input_refs=refs,
        )
        digest = _same_input_closure_projection_sha256(
            closure=closure, contract=contract, resolved_members=members, observed_refs=refs
        )
        closure = closure.model_copy(update={"closure_sha256": digest})
        if (
            control.get_method_execution_selection(
                run_id=self._run_id,
                tenant_id=scope.tenant_id,
                cell_id=scope.cell_id,
                aggregate_read_budget=self._aggregate_read_budget,
            )
            != selection
            or get_current_access_scope_or_none() != scope
        ):
            _fail("debug_selection_or_scope_changed_during_replay")
        return _ReplayedIdentity(closure=closure, contract=contract)


def issue_debug_execution_input_identity(
    *,
    control: ControlPlaneService,
    run_id: str,
    simulation_ref: ArtifactRef,
    aggregate_read_budget: _ProjectionReadBudget,
) -> tuple[SameInputClosure, VerifiedSameInputClosure]:
    """Issue the private Debug-use identity only after replaying the actual owner."""
    owner = _RestrictedExecutionIdentityOwner(
        control=control,
        run_id=run_id,
        simulation_ref=simulation_ref,
        aggregate_read_budget=aggregate_read_budget,
    )
    replayed = owner.replay()
    closure = replayed.closure
    verified = VerifiedSameInputClosure(
        _VERIFIED_CLOSURE_KEY,
        closure,
        closure.identity_tuple(),
        replayed.contract,
        owner,  # type: ignore[arg-type]
    )
    return closure, verified


def assert_debug_execution_input_identity(
    closure: SameInputClosure, verified: VerifiedSameInputClosure
) -> None:
    """Require current replay for this fixed input-identity purpose only."""
    if (
        type(verified) is not VerifiedSameInputClosure
        or verified._contract.purpose != EXECUTION_INPUT_IDENTITY_PURPOSE
        or type(verified._resolver) is not _RestrictedExecutionIdentityOwner
        or not verified._revalidate(closure)
    ):
        _fail("debug_execution_identity_not_established")
