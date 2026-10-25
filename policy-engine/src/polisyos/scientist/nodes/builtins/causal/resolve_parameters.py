"""Public causal resolve parameters module API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from polisyos.core.artifacts import (
    ArtifactRef,
    input_ref_from_artifact_ref,
    profile_bound_ref,
)
from polisyos.core.artifacts import (
    ensure_ir_artifact_store as _ensure_ir_artifact_store,
)
from polisyos.core.components import (
    Capability,
    ComponentId,
    ComponentKind,
    ComponentMetadata,
)
from polisyos.data_forge.read_api.academic import (
    ParameterSelector,
    RetainedSKGSourceBinding,
    SKGQuery,
    retained_skg_source_binding,
)
from polisyos.foundry.methods.catalog.causal.parameter_transfer import ParameterTransfer
from polisyos.foundry.methods.catalog.causal.protocols import ParameterTransferData
from polisyos.ir.analytics.causal_graph import load_causal_graph_model
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.cross_graph import (
    CrossGraphEvidenceProfile,
    load_cross_graph_evidence_profile,
)
from polisyos.ir.analytics.parameters import (
    ContextAdaptiveParameterBundleV11,
    ContextAdaptiveParameterBundleV12,
    ParameterApplicability,
    load_context_adaptive_parameter_bundle,
    persist_context_adaptive_parameter_bundle_v1_2,
)
from polisyos.ir.registry.refs import CausalGraphModelRef, CrossGraphEvidenceProfileRef
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF,
    ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import (
    NodeError,
    NodeEvent,
    NodeOutcome,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.skg_snapshot import (
    SNAPSHOT_INPUT_KEY,
    RetainedSKGSnapshotError,
    _require_retained_skg_writer_store,
    prepare_or_validate_retained_skg_read,
    retain_prepared_skg_read,
    retained_skg_snapshot_directory,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state

if TYPE_CHECKING:
    from polisyos.data_forge.read_api.academic import PreparedSKGRead

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_resolve_parameters@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Resolve Parameters",
    description="Resolve context-adaptive simulation parameters from SKG.",
    tags=["builtin", "causal", "parameters"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "params.target_context",
        "params.required_parameters",
        "params.domain",
        "params.skg_db_path",
        "params.skg_index_dir",
        "params.phase15_runtime_backend",
        "params.phase15_runtime_draws",
        "params.phase15_runtime_seed",
        f"inputs.{SNAPSHOT_INPUT_KEY}",
        "params.causal_graph_ref",
        f"artifacts_index.{ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF}",
        f"artifacts_index.{ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF}",
        f"artifacts_index.{ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF}",
    ],
    state_writes=[
        f"artifacts_index.{ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF}",
        "params.literature_priors",
        "params.parameter_uncertainty_multipliers",
        "params.phase15_runtime_backend_used",
        "params.phase15_runtime_parameter_intervals",
        "params.phase15_runtime_ready",
    ],
    produces=[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF],
)


class _InvalidCausalGraphReference(ValueError):
    """Identify a supplied graph selector that is malformed or stale."""


class _InvalidCrossGraphEvidenceProfileReference(ValueError):
    """Identify a supplied cross-graph profile selector that cannot be resolved."""


_RESOLVE_PARAMETERS_LOAD_ERRORS = (
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    ValidationError,
)


@dataclass(frozen=True)
class ResolveParametersNode:
    """Resolve context-adaptive parameters from SKG and graph evidence.

    Converts workflow state into ``ContextAdaptiveParameterBundle`` plus runtime
    uncertainty payloads that Foundry simulation can consume directly.
    """

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def prepare_cache_input(
        self,
        ctx: ExecutionContext,
        state: ExperimentState,
    ) -> PreparedSKGRead | None:
        """Bind cache lookup to the selected SKG source database."""
        try:
            graph_ref = _resolve_causal_graph_ref(state)
            _cross_graph_profile, _cross_graph_profile_ref = _resolve_cross_graph_profile(
                ctx, state
            )
        except (
            _InvalidCausalGraphReference,
            _InvalidCrossGraphEvidenceProfileReference,
        ):
            # Cache preparation is a probe; execute() turns the supplied bad
            # selector into a typed failure instead of conflating it with absence.
            return None
        if (
            _resolve_target_context(state) is None
            or not _resolve_required_parameters(state)
            or graph_ref is None
        ):
            return None
        db_path_raw = state.params.get("skg_db_path")
        if not isinstance(db_path_raw, str) or not db_path_raw.strip():
            return None
        db_path = Path(db_path_raw)
        index_dir_raw = state.params.get("skg_index_dir")
        index_dir = Path(str(index_dir_raw)) if index_dir_raw else db_path.parent
        return SKGQuery.prepare_read(db_path=db_path, index_dir=index_dir)

    def validate_cache_hit(
        self,
        ctx: ExecutionContext,
        state: ExperimentState,
        cached_outcome: NodeOutcome,
    ) -> bool:
        """Re-run request, graph, and cross-graph bindings before cache replay."""
        bundle_ref = cached_outcome.state.artifacts_index.get(
            ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF
        )
        if bundle_ref is None:
            return False
        selected_source_ref = state.inputs.get(SNAPSHOT_INPUT_KEY)
        if SNAPSHOT_INPUT_KEY in state.inputs and not isinstance(selected_source_ref, ArtifactRef):
            return False
        try:
            graph_ref = _resolve_causal_graph_ref(state)
            _cross_graph_profile, cross_graph_profile_ref = _resolve_cross_graph_profile(ctx, state)
        except (
            _InvalidCausalGraphReference,
            _InvalidCrossGraphEvidenceProfileReference,
        ):
            return False
        return _bundle_matches_request(
            ctx,
            bundle_ref,
            target_context=_resolve_target_context(state),
            simulation_domain=str(state.params.get("domain", "unknown")),
            required_parameters=_resolve_required_parameters(state),
            graph_ref=graph_ref,
            cross_graph_profile_ref=cross_graph_profile_ref,
            prepared_read=ctx.prepared_skg_read,
            selected_source_ref=selected_source_ref,
        )

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        existing_bundle_ref = state.artifacts_index.get(
            ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF
        )

        target_context = _resolve_target_context(state)
        required_parameters = _resolve_required_parameters(state)
        simulation_domain = str(state.params.get("domain", "unknown"))
        try:
            graph_ref = _resolve_causal_graph_ref(state)
        except _InvalidCausalGraphReference as exc:
            return _invalid_causal_graph_reference(state, exc)
        if graph_ref is not None:
            try:
                graph_ref = profile_bound_ref(ctx.store, graph_ref)
            except _RESOLVE_PARAMETERS_LOAD_ERRORS as exc:
                return _invalid_causal_graph_reference(state, exc)
        try:
            cross_graph_profile, cross_graph_profile_ref = _resolve_cross_graph_profile(ctx, state)
        except _InvalidCrossGraphEvidenceProfileReference as exc:
            return _invalid_cross_graph_profile_reference(state, exc)

        # A source-unbound bundle can only be reused when this invocation has
        # no current SKG source to consume. Once an owner-prepared or
        # configured source is present, recompute because this bundle does not
        # persist the selector-read binding.
        skg_path_raw = state.params.get("skg_db_path")
        has_current_skg_source = isinstance(skg_path_raw, str) and bool(skg_path_raw.strip())
        if (
            existing_bundle_ref is not None
            and ctx.prepared_skg_read is None
            and not has_current_skg_source
            and SNAPSHOT_INPUT_KEY not in state.inputs
            and _bundle_matches_request(
                ctx,
                existing_bundle_ref,
                target_context=target_context,
                simulation_domain=simulation_domain,
                required_parameters=required_parameters,
                graph_ref=graph_ref,
                cross_graph_profile_ref=cross_graph_profile_ref,
            )
        ):
            return NodeOutcome(status="ok", state=state)

        if target_context is None:
            return _skip(
                state,
                "Missing params.target_context; parameter resolution skipped.",
            )

        if not required_parameters:
            return _skip(
                state,
                "Missing params.required_parameters; parameter resolution skipped.",
            )

        if graph_ref is None:
            return _skip(
                state,
                "No causal graph reference available; parameter resolution skipped.",
            )

        try:
            causal_graph = load_causal_graph_model(_ensure_ir_artifact_store(ctx.store), graph_ref)
        except _RESOLVE_PARAMETERS_LOAD_ERRORS:
            return _skip(
                state,
                "Failed to load causal graph artifact; parameter resolution skipped.",
            )

        has_selected_snapshot = SNAPSHOT_INPUT_KEY in state.inputs
        selected_snapshot_ref = state.inputs.get(SNAPSHOT_INPUT_KEY)
        if has_selected_snapshot and not isinstance(selected_snapshot_ref, ArtifactRef):
            raise RetainedSKGSnapshotError("retained_skg_descriptor_ref_required")
        db_path_raw = state.params.get("skg_db_path")
        if not isinstance(db_path_raw, str) or not db_path_raw.strip():
            if has_selected_snapshot:
                raise RetainedSKGSnapshotError("retained_skg_selected_path_required")
            return _skip(
                state,
                "Missing params.skg_db_path; parameter resolution skipped.",
            )
        db_path = Path(db_path_raw)
        if not db_path.exists() and not has_selected_snapshot:
            return _skip(
                state,
                f"SKG database '{db_path}' is unavailable; parameter resolution skipped.",
            )
        index_dir_raw = state.params.get("skg_index_dir")
        index_dir = Path(str(index_dir_raw)) if index_dir_raw else db_path.parent

        parameters: dict[str, Any] = {}
        applicability: dict[str, ParameterApplicability] = {}
        unsupported: list[str] = []
        prepared_read = ctx.prepared_skg_read
        owns_prepared_read = False
        source_binding: RetainedSKGSourceBinding | None = None
        if has_selected_snapshot:
            assert isinstance(selected_snapshot_ref, ArtifactRef)
            prepared_read = prepare_or_validate_retained_skg_read(
                ctx.store,
                selected_snapshot_ref,
                directory=retained_skg_snapshot_directory(ctx.run.trace_path),
                index_dir=index_dir,
                expected_path=db_path,
                prepared_read=prepared_read,
            )
            owns_prepared_read = ctx.prepared_skg_read is None
        elif prepared_read is None:
            prepared_read = SKGQuery.prepare_read(db_path=db_path, index_dir=index_dir)
            owns_prepared_read = True
        elif not prepared_read.matches_path(db_path):
            return _skip(state, "Prepared SKG source path does not match this selector request.")
        skg_query = prepared_read.query
        try:
            selector = ParameterSelector(skg_query)
            for parameter_name in required_parameters:
                parameter, appl = selector.select_for_context(
                    parameter_name=parameter_name,
                    target_context=target_context,
                    causal_graph=causal_graph,
                    cross_graph_profile=cross_graph_profile,
                )
                applicability[parameter_name] = appl
                if parameter is None:
                    unsupported.append(parameter_name)
                    continue
                parameters[parameter_name] = parameter

            skg_version_id = skg_query.latest_skg_version_id()
            if skg_version_id is None:
                raise RetainedSKGSnapshotError("retained_skg_source_version_missing")
            if (
                not prepared_read.source_generation_matches()
                or skg_query.skg_snapshot_ref(version_id=skg_version_id)
                != prepared_read.source_snapshot_ref
            ):
                raise RetainedSKGSnapshotError("retained_skg_prepared_source_changed_during_read")
            if selected_snapshot_ref is None:
                retained_store = _require_retained_skg_writer_store(ctx.store)
                retained_ref = retain_prepared_skg_read(retained_store, prepared_read)
            else:
                # Replay keeps its selected descriptor; its source path is the
                # original logical path, unlike this worker materialization.
                retained_ref = selected_snapshot_ref
            source_binding = retained_skg_source_binding(ctx.store, retained_ref)
            if (
                source_binding.source_sha256 != prepared_read.source_snapshot_sha256
                or source_binding.source_binding_schema_version
                != prepared_read.source_binding_schema_version
                or source_binding.query_version != prepared_read.query_version
                or source_binding.source_version_id != skg_version_id
                or (
                    selected_snapshot_ref is None
                    and source_binding.source_reference != prepared_read.source_snapshot_ref
                )
                or (
                    selected_snapshot_ref is not None
                    and source_binding.descriptor_ref != selected_snapshot_ref
                )
                or not prepared_read.source_generation_matches()
            ):
                raise RetainedSKGSnapshotError("retained_skg_prepared_source_mismatch")
        finally:
            if owns_prepared_read:
                prepared_read.close()

        if source_binding is None:
            raise RetainedSKGSnapshotError("retained_skg_source_bundle_join_missing")
        bundle = ContextAdaptiveParameterBundleV12(
            target_context=target_context,
            simulation_domain=simulation_domain,
            parameters=parameters,
            applicability=applicability,
            unsupported_parameters=unsupported,
            skg_snapshot_ref=source_binding.source_reference,
            skg_version_id=skg_version_id,
            selection_timestamp=datetime.now(UTC).replace(microsecond=0).isoformat(),
            selected_cross_graph_profile_ref=cross_graph_profile_ref,
            selected_skg_source=source_binding,
        )

        core_input_refs = [
            input_ref_from_artifact_ref(
                ArtifactRef.model_validate(graph_ref.model_dump(mode="json")),
                role="causal_graph",
            )
        ]
        if cross_graph_profile_ref is not None:
            core_input_refs.append(
                input_ref_from_artifact_ref(
                    ArtifactRef.model_validate(cross_graph_profile_ref.model_dump(mode="json")),
                    role="cross_graph_evidence_profile",
                )
            )
        core_input_refs.append(
            input_ref_from_artifact_ref(
                source_binding.descriptor_ref,
                role="skg_source_snapshot",
            )
        )
        input_refs = core_input_refs
        ir_bundle_ref = persist_context_adaptive_parameter_bundle_v1_2(
            _ensure_ir_artifact_store(ctx.store),
            bundle,
            inputs=input_refs,
        )
        bundle_ref = ArtifactRef.model_validate(ir_bundle_ref.model_dump(mode="json"))
        bridge_payload = ParameterTransfer.pure_step(
            ParameterTransferData(parameter_bundle=bundle),
            params={
                "runtime_backend": state.params.get("phase15_runtime_backend", "auto"),
                "runtime_draws": state.params.get("phase15_runtime_draws", 256),
                "runtime_seed": state.params.get("phase15_runtime_seed", 0),
            },
        )

        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        new_state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF] = bundle_ref
        new_state.params["literature_priors"] = bridge_payload.get("literature_priors", {})
        new_state.params["parameter_uncertainty_multipliers"] = bridge_payload.get(
            "uncertainty_multipliers",
            {},
        )
        new_state.params["phase15_runtime_backend_used"] = bridge_payload.get(
            "runtime_backend_used",
            "numpy",
        )
        new_state.params["phase15_runtime_parameter_intervals"] = bridge_payload.get(
            "runtime_parameter_intervals",
            {},
        )
        new_state.params["phase15_runtime_ready"] = bool(bridge_payload.get("runtime_ready", False))

        events = []
        if unsupported:
            events.append(
                NodeEvent(
                    level="warn",
                    code="PARAMS_WITHOUT_EVIDENCE",
                    message=(
                        "Parameters without applicable literature support: "
                        + ", ".join(sorted(unsupported))
                    ),
                )
            )
        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[bundle_ref, source_binding.descriptor_ref],
            events=events,
        )


def _resolve_target_context(state: ExperimentState) -> ContextProfile | None:
    payload = state.params.get("target_context")
    if payload is None:
        return None
    try:
        return ContextProfile.model_validate(payload)
    except _RESOLVE_PARAMETERS_LOAD_ERRORS:
        return None


def _resolve_required_parameters(state: ExperimentState) -> list[str]:
    raw = state.params.get("required_parameters")
    if not isinstance(raw, list):
        return []
    values = [str(item).strip() for item in raw if str(item).strip()]
    return sorted(set(values))


def _bundle_matches_request(
    ctx: ExecutionContext,
    bundle_ref: Any,
    *,
    target_context: ContextProfile | None,
    simulation_domain: str,
    required_parameters: list[str],
    graph_ref: CausalGraphModelRef | None,
    cross_graph_profile_ref: CrossGraphEvidenceProfileRef | None,
    prepared_read: PreparedSKGRead | None = None,
    selected_source_ref: ArtifactRef | None = None,
) -> bool:
    """Check bundle custody and exact graph/profile/source bindings for this request."""
    if selected_source_ref is not None and not isinstance(selected_source_ref, ArtifactRef):
        return False
    store = _ensure_ir_artifact_store(ctx.store)
    try:
        bundle = load_context_adaptive_parameter_bundle(store, bundle_ref)
        manifest = store.get_manifest(bundle_ref)
    except _RESOLVE_PARAMETERS_LOAD_ERRORS:
        return False

    if (
        manifest.kind != "ir.context_adaptive_parameter_bundle"
        or manifest.artifact_schema is None
        or manifest.artifact_schema.name != "ir.context_adaptive_parameter_bundle"
        or manifest.artifact_schema.version not in {"1.0", "1.1", "1.2"}
    ):
        return False

    source_scoped_request = prepared_read is not None or selected_source_ref is not None
    if source_scoped_request:
        if manifest.artifact_schema.version != "1.2" or not isinstance(
            bundle, ContextAdaptiveParameterBundleV12
        ):
            return False
        source_binding = bundle.selected_skg_source
        if bundle.skg_version_id != source_binding.source_version_id:
            return False
        if selected_source_ref is not None and selected_source_ref != source_binding.descriptor_ref:
            return False
        if prepared_read is not None:
            if (
                source_binding.source_sha256 != prepared_read.source_snapshot_sha256
                or source_binding.source_binding_schema_version
                != prepared_read.source_binding_schema_version
                or source_binding.query_version != prepared_read.query_version
                or prepared_read.query.latest_skg_version_id() != source_binding.source_version_id
                or not prepared_read.source_generation_matches()
            ):
                return False
            if (
                selected_source_ref is None
                and source_binding.source_reference != prepared_read.source_snapshot_ref
            ):
                return False

    # A selected source is part of the cache request even when this is a
    # historical replay without the context, graph, or parameter selectors.
    # Validate its exact v1.2 binding before preserving the no-request path.
    if (
        target_context is None
        and not required_parameters
        and graph_ref is None
        and cross_graph_profile_ref is None
    ):
        return True

    if target_context is None or not required_parameters or graph_ref is None:
        return False
    if not source_scoped_request and (
        manifest.artifact_schema.version not in {"1.1", "1.2"}
        or not isinstance(bundle, ContextAdaptiveParameterBundleV11)
    ):
        # Historical source-unbound bundles remain readable when no current source is selected.
        return False
    if bundle.target_context != target_context:
        return False
    if bundle.simulation_domain != simulation_domain:
        return False

    covered_parameters = set(bundle.parameters) | set(bundle.unsupported_parameters)
    if not set(required_parameters).issubset(covered_parameters):
        return False

    try:
        selected_graph_ref = profile_bound_ref(ctx.store, graph_ref)
    except _RESOLVE_PARAMETERS_LOAD_ERRORS:
        return False
    graph_inputs = [entry for entry in manifest.inputs if entry.role == "causal_graph"]
    selected_profile_ref = None
    if cross_graph_profile_ref is not None:
        try:
            selected_profile_ref = profile_bound_ref(ctx.store, cross_graph_profile_ref)
        except _RESOLVE_PARAMETERS_LOAD_ERRORS:
            return False
    if not isinstance(bundle, ContextAdaptiveParameterBundleV11):
        return False
    if bundle.selected_cross_graph_profile_ref != selected_profile_ref:
        return False
    profile_inputs = [
        entry for entry in manifest.inputs if entry.role == "cross_graph_evidence_profile"
    ]
    profile_matches = (
        not profile_inputs
        if selected_profile_ref is None
        else len(profile_inputs) == 1
        and str(profile_inputs[0].artifact_id) == str(selected_profile_ref.artifact_id)
        and profile_inputs[0].manifest_profile_sha256
        == selected_profile_ref.manifest_profile_sha256
    )
    return (
        len(graph_inputs) == 1
        and str(graph_inputs[0].artifact_id) == str(selected_graph_ref.artifact_id)
        and graph_inputs[0].manifest_profile_sha256 == selected_graph_ref.manifest_profile_sha256
        and profile_matches
    )


def _resolve_causal_graph_ref(state: ExperimentState) -> CausalGraphModelRef | None:
    if ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF in state.artifacts_index:
        raw = state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF]
        source = "artifacts_index"
    elif "causal_graph_ref" in state.params:
        raw = state.params["causal_graph_ref"]
        source = "params.causal_graph_ref"
    else:
        return None
    if raw is None:
        raise _InvalidCausalGraphReference(f"supplied {source} is explicitly null")

    if isinstance(raw, ArtifactRef):
        payload = raw.model_dump(mode="json")
    else:
        payload = raw
    try:
        return CausalGraphModelRef.model_validate(payload)
    except _RESOLVE_PARAMETERS_LOAD_ERRORS as exc:
        raise _InvalidCausalGraphReference("supplied causal graph reference is malformed") from exc


def _resolve_cross_graph_profile(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> tuple[CrossGraphEvidenceProfile | None, CrossGraphEvidenceProfileRef | None]:
    if ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF not in state.artifacts_index:
        return None, None
    raw = state.artifacts_index[ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF]
    if raw is None:
        raise _InvalidCrossGraphEvidenceProfileReference(
            "supplied cross-graph evidence profile reference is explicitly null"
        )
    try:
        if hasattr(raw, "model_dump"):
            payload = raw.model_dump(mode="json")
        else:
            payload = raw
        ref = CrossGraphEvidenceProfileRef.model_validate(payload)
        store = _ensure_ir_artifact_store(ctx.store)
        selected_ref = profile_bound_ref(ctx.store, ref)
        manifest = store.get_manifest(selected_ref)
        if (
            manifest.artifact_schema is None
            or manifest.artifact_schema.name != "ir.cross_graph_evidence_profile"
            or manifest.artifact_schema.version != "2.1"
        ):
            raise ValueError("cross-graph evidence profile artifact schema is incompatible")
        profile = load_cross_graph_evidence_profile(store, selected_ref)
        if profile.schema_version != "2.1":
            raise ValueError("cross-graph evidence profile payload schema is incompatible")
        return profile, selected_ref
    except _RESOLVE_PARAMETERS_LOAD_ERRORS as exc:
        raise _InvalidCrossGraphEvidenceProfileReference(
            "supplied cross-graph evidence profile reference is malformed, stale, or unloadable"
        ) from exc


def _invalid_causal_graph_reference(
    state: ExperimentState,
    exc: Exception,
) -> NodeOutcome:
    return NodeOutcome(
        status="fail",
        state=state,
        error=NodeError(
            code=node_errors.ERROR_INVALID_STATE,
            message=f"Invalid supplied causal graph reference: {exc}",
            details={"input": "causal_graph_ref"},
        ),
    )


def _invalid_cross_graph_profile_reference(
    state: ExperimentState,
    exc: Exception,
) -> NodeOutcome:
    return NodeOutcome(
        status="fail",
        state=state,
        error=NodeError(
            code=node_errors.ERROR_INVALID_STATE,
            message=f"Invalid supplied cross-graph evidence profile reference: {exc}",
            details={"input": ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF},
        ),
    )


def _skip(state: ExperimentState, message: str) -> NodeOutcome:
    return NodeOutcome(
        status="skip",
        state=state,
        events=[NodeEvent(level="warn", message=message)],
    )


__all__ = ["ResolveParametersNode"]
