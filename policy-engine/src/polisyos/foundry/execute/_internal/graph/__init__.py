"""Program-graph orchestrator — execute_program_graph and direct helpers."""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
import math
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, TypedDict, TypeVar

import jax
import jax.numpy as jnp
import numpy as np
from pydantic import TypeAdapter, ValidationError

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import artifact_ref_for_manifest
from polisyos.core.artifacts.environment import (
    EnvironmentManifest,
    EnvironmentManifestRef,
    capture_environment,
)
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.ir_adapter import matches_artifact_store_protocol
from polisyos.core.artifacts.manifest import (
    ArtifactManifest,
    ArtifactRef,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.protocol import (
    ArtifactStore,
    CoreJSONArtifactBoundedMemberReader,
    CoreJSONArtifactStore,
)
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.foundry import (
    METHOD_METRIC_BINDING_LIMIT,
    ConstraintReport,
    ConstraintReportRef,
    ExecPlan,
    ExecPlanRef,
    LoweredIR,
    MethodArtifactOutputPayload,
    MethodArtifactOutputRef,
    MethodExecutionArtifact,
    MethodExecutionBackendAttempt,
    MethodExecutionBundle,
    MethodExecutionBundleRef,
    MethodExecutionDispatchRecord,
    MethodExecutionInputRole,
    MethodExecutionInputSlot,
    MethodExecutionOccurrence,
    MethodExecutionOutputSlot,
    MethodExecutionParameterValue,
    MethodExecutionReturnedSlot,
    MethodMetricBinding,
    MethodMetricBindingSet,
    MethodMetricBindingSetRef,
    MethodMetricInputCapturePayload,
    MethodMetricInputCaptureRef,
    MethodMetricInputCaptureSlot,
    MethodOutputPayload,
    MethodOutputRef,
    Metrics,
    PatchOp,
    ProgramGraph,
    ProgramGraphRef,
    ProgramNode,
    RestrictedMethodCallWitness,
    StateDelta,
    StateSnapshotRef,
)
from polisyos.foundry.agent_sim.agents import AdaptiveAgentMechanism
from polisyos.foundry.compile.randomization import (
    TREASURY_SALTS_PROFILE,
    TreasuryPlan,
    build_treasury_plan,
)
from polisyos.foundry.execute._internal.models import (
    ExecuteArtifacts,
    ExecutionStrictness,
    FailureCard,
    FailureKind,
    FailureSeverity,
    MethodExecutionCapture,
    artifact_id,
    artifact_input_ref,
    get_state_path,
    load_model,
    load_payload,
    put_tensor,
)
from polisyos.foundry.execute._internal.ops import (
    apply_ops_to_state,
    coerce_number,
    evaluate_selector,
)
from polisyos.foundry.execute._internal.patching import apply_patch_map
from polisyos.foundry.execute._internal.snapshots import put_state_snapshot
from polisyos.foundry.execute.patch_vm import merge_patch_records
from polisyos.foundry.methods.backends.circuit_breaker import BackendCircuitOpenError
from polisyos.foundry.methods.backends.dispatch import BackendNotAvailableError
from polisyos.foundry.methods.catalog.mechanism.runtime_registry import (
    create_mechanism_from_spec,
)
from polisyos.foundry.methods.exceptions import (
    BackendAdaptationError,
    ContractViolationError,
    FoundryExecutionError,
    MethodExecutionAbortError,
    ObservationBindingError,
    ProgramNodeValidationError,
    SelectorEvaluationError,
    ShapeMismatchError,
    StatePathTraversalError,
)
from polisyos.foundry.welfare.bounds import (
    load_observed_range_bundle,
    persist_welfare_bound_report,
    safe_compute_mechanism_welfare_bound_report,
)
from polisyos.ir.governance.schedule import ScheduleSpec, schedule_range
from polisyos.ir.governance.selector_expr import SelectorExpr
from polisyos.ir.kernel import (
    METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID,
    ConstraintRegistry,
    MechanismTypeRegistry,
    MergeRuleKind,
    MergeRuleRegistry,
    MethodMetricSourceUnit,
    SelectorFieldRegistry,
    SlotRegistry,
    SlotScope,
    registered_method_metric_semantics_match,
)

logger = logging.getLogger(__name__)

__all__ = [
    "execute_program_graph",
]

_SELECTOR_ADAPTER = TypeAdapter(SelectorExpr)
_MAX_FAILURE_CARDS = 256
_CLASSIFIED_EXECUTOR_FAILURES = (
    BackendAdaptationError,
    BackendCircuitOpenError,
    BackendNotAvailableError,
    ContractViolationError,
    FloatingPointError,
    FoundryExecutionError,
    ImportError,
    ModuleNotFoundError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValidationError,
    ValueError,
)


class _MethodExecutionIdentity(TypedDict, total=False):
    """Method identity fields retain the source's declared value domains."""

    method_fqn: str
    method_version: str | None
    method_abi_digest: str | None
    method_abi_digest_algorithm: Literal["blake2b"] | None
    method_build_digest: str | None
    method_build_digest_scope: Literal["class_source_only", "unavailable"] | None
    limitation: str | None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _execution_treasury(
    store: CoreJSONArtifactStore,
    program_ref: ArtifactRef | ArtifactID | str,
    exec_plan_ref: ArtifactRef | ArtifactID | str,
    program: ProgramGraph,
    plan: ExecPlan,
) -> TreasuryPlan | None:
    """Admit the explicit salt law only through its selected CAS input lineage."""
    profiles = [note for note in plan.notes if note.startswith("randomization:")]
    if not profiles:
        return None
    if profiles != [TREASURY_SALTS_PROFILE]:
        raise ValueError("unsupported_randomization_profile")
    if plan.program_ref.artifact_id != artifact_id(program_ref):
        raise ValueError("treasury_exec_program_mismatch")
    manifest = store.get_manifest(_artifact_selector(exec_plan_ref))
    if manifest.kind != "foundry.exec_plan":
        raise ValueError("treasury_exec_manifest_kind")

    def one_input(inputs: Any, role: str) -> Any:
        edges = [item for item in inputs if item.role == role]
        if len(edges) != 1:
            raise ValueError(f"treasury_requires_one_{role}_input")
        return edges[0]

    program_edge = one_input(manifest.inputs, "program_graph")
    if program_edge.artifact_id != artifact_id(program_ref):
        raise ValueError("treasury_program_input_mismatch")
    requested_profile = getattr(program_ref, "manifest_profile_sha256", None)
    if requested_profile is not None and requested_profile != program_edge.manifest_profile_sha256:
        raise ValueError("treasury_program_profile_mismatch")
    bound_program_ref = ArtifactRef(
        artifact_id=program_edge.artifact_id,
        manifest_profile_sha256=program_edge.manifest_profile_sha256,
        kind=ProgramGraph.ARTIFACT_KIND,
        media_type=ProgramGraph.ARTIFACT_MEDIA_TYPE,
    )
    program_manifest = store.get_manifest(bound_program_ref)
    if program_manifest.kind != "foundry.program_graph":
        raise ValueError("treasury_program_manifest_kind")
    # Reading the selected input also verifies its content bytes and ownership.
    load_model(store, bound_program_ref, ProgramGraph)
    lowered_edge = one_input(program_manifest.inputs, "lowered_ir")
    if (
        program.lowered_ir_ref is None
        or lowered_edge.artifact_id != program.lowered_ir_ref.artifact_id
    ):
        raise ValueError("treasury_lowered_ir_input_mismatch")

    edge = one_input(manifest.inputs, "treasury_plan")
    ref = ArtifactRef(
        artifact_id=edge.artifact_id,
        manifest_profile_sha256=edge.manifest_profile_sha256,
        kind="foundry.treasury_plan",
        media_type="application/json",
    )
    treasury_manifest = store.get_manifest(ref)
    if treasury_manifest.kind != ref.kind or treasury_manifest.artifact_schema != SchemaInfo(
        name="polisyos.foundry.TreasuryPlan", version="1.0"
    ):
        raise ValueError("treasury_manifest_schema_or_kind")
    treasury_program_edge = one_input(treasury_manifest.inputs, "program_graph")
    if treasury_program_edge != program_edge:
        raise ValueError("treasury_source_program_mismatch")
    treasury = load_model(store, ref, TreasuryPlan)
    expected = build_treasury_plan(program, root_seed=plan.random_seed or 0)
    if (
        treasury.schema_version != "1.0"
        or treasury.root_seed != expected.root_seed
        or treasury.node_salts != expected.node_salts
        or treasury.stream_salts != expected.stream_salts
    ):
        raise ValueError("treasury_seed_or_salts_mismatch")
    return treasury


def _artifact_selector(ref: ArtifactRef | ArtifactID | str) -> ArtifactRef | ArtifactID:
    """Normalize a string selector to the generic CAS protocol's typed ID."""
    return ArtifactID.model_validate(ref) if isinstance(ref, str) else ref


def _selected_typed_ref(
    store: ArtifactStore,
    ref: ArtifactRef | ArtifactID | str,
    ref_type: type[_RefT],
) -> _RefT:
    """Resolve and type the exact current manifest profile for one source ref."""
    manifest = store.get_manifest(_artifact_selector(ref))
    if isinstance(ref, ArtifactRef):
        if manifest.artifact_id != ref.artifact_id or manifest.kind != ref.kind:
            raise ValueError("method_execution_source_ref_identity_mismatch")
        if manifest.media_type != ref.media_type:
            raise ValueError("method_execution_source_ref_media_type_mismatch")
    profile = artifact_ref_for_manifest(manifest)
    if isinstance(ref, ArtifactRef) and (
        ref.manifest_profile_sha256 is not None
        and ref.manifest_profile_sha256 != profile.manifest_profile_sha256
    ):
        raise ValueError("method_execution_source_profile_mismatch")
    return ref_type.model_validate(profile.model_dump(mode="python"))


def _one_manifest_input(manifest: Any, role: str) -> Any:
    edges = [item for item in manifest.inputs if item.role == role]
    if len(edges) != 1:
        raise ValueError(f"method_execution_manifest_requires_one_{role}_edge")
    return edges[0]


def _edge_matches_ref(edge: Any, ref: ArtifactRef) -> bool:
    return (
        edge.artifact_id == ref.artifact_id
        and edge.manifest_profile_sha256 == ref.manifest_profile_sha256
    )


def _binding_ref_from_exec_plan_manifest(
    store: ArtifactStore,
    exec_plan_ref: ArtifactRef | ArtifactID | str,
) -> MethodMetricBindingSetRef | None:
    manifest = store.get_manifest(_artifact_selector(exec_plan_ref))
    edges = [item for item in manifest.inputs if item.role == "method_metric_bindings"]
    if not edges:
        return None
    if len(edges) != 1:
        raise ValueError("method_metric_exec_plan_has_duplicate_binding_edges")
    edge = edges[0]
    ref = MethodMetricBindingSetRef(
        artifact_id=edge.artifact_id,
        manifest_profile_sha256=edge.manifest_profile_sha256,
    )
    # The exact profile is carried by the ExecPlan edge; the bounded Core read below
    # validates the binding-set kind, media, and full manifest before decoding its payload.
    return ref


_METHOD_METRIC_BINDING_PAYLOAD_LIMIT_BYTES = 1024 * 1024
_METHOD_METRIC_BINDING_MANIFEST_LIMIT_BYTES = 64 * 1024
_METHOD_METRIC_BINDING_JSON_ELEMENT_LIMIT = 32_768
_METHOD_METRIC_BINDING_JSON_DEPTH_LIMIT = 16


class _BoundedCoreJSONArtifactStore(
    CoreJSONArtifactStore,
    CoreJSONArtifactBoundedMemberReader,
    Protocol,
):
    """Store needed only when execution admits a bounded method-metric binding read."""


def _require_bounded_core_json_store(store: CoreJSONArtifactStore) -> _BoundedCoreJSONArtifactStore:
    """Narrow the optional bounded reader at the method-metric read use site."""
    if not matches_artifact_store_protocol(store, _BoundedCoreJSONArtifactStore):
        raise CanonicalProfileRefusalError("canon_profile_bounded_stream_unavailable")
    return store


def _read_method_metric_binding_set_bounded(
    store: CoreJSONArtifactBoundedMemberReader,
    binding_set_ref: MethodMetricBindingSetRef,
) -> tuple[ArtifactManifest, MethodMetricBindingSet]:
    """Read a selected binding set under Core bounds before Pydantic materialization."""
    from polisyos.core.artifacts import (
        CoreJsonReadLimits,
        read_core_json_artifact_bounded,
        validate_core_model_bounded_read,
    )

    selected_ref = ArtifactRef.model_validate(binding_set_ref.model_dump(mode="python"))
    bounded_read = read_core_json_artifact_bounded(
        store,
        selected_ref,
        limits=CoreJsonReadLimits(
            max_bytes=_METHOD_METRIC_BINDING_PAYLOAD_LIMIT_BYTES,
            max_depth=_METHOD_METRIC_BINDING_JSON_DEPTH_LIMIT,
            max_elements=_METHOD_METRIC_BINDING_JSON_ELEMENT_LIMIT,
            max_manifest_bytes=_METHOD_METRIC_BINDING_MANIFEST_LIMIT_BYTES,
        ),
    )
    decoded_payload = bounded_read.profile_read.value
    if type(decoded_payload) is dict:
        raw_bindings = decoded_payload.get("bindings")
        if type(raw_bindings) is list and len(raw_bindings) > METHOD_METRIC_BINDING_LIMIT:
            raise ValueError("method_metric_binding_inventory_exceeds_capture_limit")
    binding_set = validate_core_model_bounded_read(MethodMetricBindingSet, bounded_read)
    if len(binding_set.bindings) > METHOD_METRIC_BINDING_LIMIT:
        raise ValueError("method_metric_binding_inventory_exceeds_capture_limit")
    return bounded_read.manifest, binding_set


def _validate_method_metric_plan_binding(
    store: _BoundedCoreJSONArtifactStore,
    *,
    plan_ref: ExecPlanRef,
    graph_ref: ProgramGraphRef,
    binding_set_ref: MethodMetricBindingSetRef,
) -> MethodMetricBindingSet:
    """Reconcile selected-profile lineage under bounded binding-payload admission."""

    plan_manifest = store.get_manifest(plan_ref)
    if plan_manifest.kind != ExecPlan.ARTIFACT_KIND or plan_manifest.artifact_schema != SchemaInfo(
        name=ExecPlan.ARTIFACT_SCHEMA_NAME, version=ExecPlan.ARTIFACT_SCHEMA_VERSION
    ):
        raise ValueError("method_metric_exec_plan_schema_or_kind_mismatch")
    binding_edge = _one_manifest_input(plan_manifest, "method_metric_bindings")
    graph_edge = _one_manifest_input(plan_manifest, "program_graph")
    if not _edge_matches_ref(binding_edge, binding_set_ref):
        raise ValueError("method_metric_exec_plan_binding_edge_mismatch")
    if not _edge_matches_ref(graph_edge, graph_ref):
        raise ValueError("method_metric_exec_plan_program_graph_edge_mismatch")

    binding_manifest, binding_set = _read_method_metric_binding_set_bounded(
        store,
        binding_set_ref,
    )
    if (
        binding_manifest.kind != MethodMetricBindingSet.ARTIFACT_KIND
        or binding_manifest.artifact_schema
        != SchemaInfo(
            name=MethodMetricBindingSet.ARTIFACT_SCHEMA_NAME,
            version=MethodMetricBindingSet.ARTIFACT_SCHEMA_VERSION,
        )
    ):
        raise ValueError("method_metric_binding_set_schema_or_profile_mismatch")
    if binding_set.program_graph_ref != graph_ref:
        raise ValueError("method_metric_binding_set_program_graph_payload_mismatch")
    if not _edge_matches_ref(_one_manifest_input(binding_manifest, "program_graph"), graph_ref):
        raise ValueError("method_metric_binding_set_program_graph_edge_mismatch")
    for role, ref in (
        ("policy", binding_set.policy_ref),
        ("registry_bundle", binding_set.registry_bundle_ref),
        ("metric_registry", binding_set.metric_registry_ref),
        ("units_registry", binding_set.units_registry_ref),
    ):
        exact_ref = _selected_typed_ref(store, ref, ArtifactRef)
        if not _edge_matches_ref(_one_manifest_input(binding_manifest, role), exact_ref):
            raise ValueError(f"method_metric_binding_set_{role}_edge_mismatch")
    return binding_set


def new_method_execution_capture(
    store: CoreJSONArtifactStore,
    *,
    program_ref: ArtifactRef | ArtifactID | str,
    exec_plan_ref: ArtifactRef | ArtifactID | str,
) -> MethodExecutionCapture | None:
    """Create a graph metric capture only when the selected ExecPlan binds metrics.

    The method-metric binding is admitted through the exact ExecPlan manifest edge;
    the legacy ExecPlan payload remains unchanged.
    """
    binding_set_ref = _binding_ref_from_exec_plan_manifest(store, exec_plan_ref)
    if binding_set_ref is None:
        return None
    plan_ref = _selected_typed_ref(store, exec_plan_ref, ExecPlanRef)
    graph_ref = _selected_typed_ref(store, program_ref, ProgramGraphRef)
    bounded_store = _require_bounded_core_json_store(store)
    binding_set = _validate_method_metric_plan_binding(
        bounded_store,
        plan_ref=plan_ref,
        graph_ref=graph_ref,
        binding_set_ref=binding_set_ref,
    )
    return MethodExecutionCapture(
        program_graph_ref=graph_ref,
        exec_plan_ref=plan_ref,
        method_metric_binding_set_ref=binding_set_ref,
        method_metric_bindings=tuple(binding_set.bindings),
    )


def _resolve_planned_method_identities(
    order: list[str], node_map: dict[str, Any]
) -> tuple[dict[str, type[Any]], dict[str, _MethodExecutionIdentity]]:
    """Load exact planned method classes and retain honest source identity limits."""
    from polisyos.foundry.methods.registry import MethodRegistry

    registry = MethodRegistry.get_instance()
    classes: dict[str, type[Any]] = {}
    identities: dict[str, _MethodExecutionIdentity] = {}
    for node_id in dict.fromkeys(order):
        node = node_map.get(node_id)
        if node is None or node.node_kind != "method" or not node.method_fqn:
            continue
        identity: _MethodExecutionIdentity = {
            "method_fqn": node.method_fqn,
            "method_version": node.method_version,
            "method_abi_digest": None,
            "method_abi_digest_algorithm": None,
            "method_build_digest": None,
            "method_build_digest_scope": "unavailable",
            "limitation": "method_identity_unavailable",
        }
        try:
            method_class = registry.get(node.method_fqn)
            signature = method_class.signature
            if signature.fqn != node.method_fqn:
                raise ValueError("loaded_method_fqn_differs_from_selected_fqn")
            if node.method_version is not None and signature.version != node.method_version:
                raise ValueError("loaded_method_version_differs_from_selected_version")
            if (
                len(signature.input_slots) > 32
                or len(signature.output_slots) > _MAX_METHOD_RETURNED_SLOTS
                or len(signature.parameters) > _MAX_METHOD_PARAMETER_COUNT
                or any(len(slot.name) > 256 for slot in signature.input_slots)
                or any(len(slot.name) > 256 for slot in signature.output_slots)
                or any(len(parameter.name) > 256 for parameter in signature.parameters)
            ):
                raise ValueError("loaded_method_signature_inventory_exceeds_capture_limit")
            identity.update(
                {
                    "method_version": signature.version,
                    "method_abi_digest": signature.abi_digest(),
                    "method_abi_digest_algorithm": "blake2b",
                    "limitation": None,
                }
            )
            classes[node_id] = method_class
            try:
                source = inspect.getsource(method_class).encode("utf-8")
            except (OSError, TypeError, UnicodeError):
                identity["method_build_digest_scope"] = "unavailable"
                identity["limitation"] = "method_class_source_unavailable"
            else:
                identity["method_build_digest"] = "sha256:" + hashlib.sha256(source).hexdigest()
                identity["method_build_digest_scope"] = "class_source_only"
        except Exception as exc:
            identity["limitation"] = f"method_identity_unavailable:{type(exc).__name__}"
        identities[node_id] = identity
    return classes, identities


def _method_occurrence_id(invocation_id: str, plan_index: int, node_id: str) -> str:
    """Identify one plan position without collapsing repeated node invocations."""
    return f"{invocation_id}:{plan_index}:{node_id}"


_UNSUPPORTED_BOUNDED_JSON = object()


def _bounded_json_value(
    value: Any,
    *,
    max_bytes: int,
    max_elements: int = 256,
    max_depth: int = 8,
) -> Any:
    """Normalize a small JSON value while bounding cardinality before traversal."""
    budget = [0, 0]
    active: set[int] = set()

    def visit(item: Any, depth: int) -> Any:
        if depth > max_depth:
            return _UNSUPPORTED_BOUNDED_JSON
        budget[0] += 1
        if budget[0] > max_elements:
            return _UNSUPPORTED_BOUNDED_JSON
        if item is None or type(item) is bool:
            return item
        if type(item) is int:
            if item.bit_length() > 4096:
                return _UNSUPPORTED_BOUNDED_JSON
            budget[1] += max(1, (item.bit_length() + 7) // 8)
            return item if budget[1] <= max_bytes else _UNSUPPORTED_BOUNDED_JSON
        if type(item) is float:
            if not math.isfinite(item):
                return _UNSUPPORTED_BOUNDED_JSON
            budget[1] += 8
            return item if budget[1] <= max_bytes else _UNSUPPORTED_BOUNDED_JSON
        if type(item) is str:
            if len(item) > max_bytes - budget[1]:
                return _UNSUPPORTED_BOUNDED_JSON
            size = len(item.encode("utf-8"))
            if size > max_bytes - budget[1]:
                return _UNSUPPORTED_BOUNDED_JSON
            budget[1] += size
            return item
        if type(item) in {list, tuple}:
            if len(item) > max_elements - budget[0]:
                return _UNSUPPORTED_BOUNDED_JSON
            identity = id(item)
            if identity in active:
                return _UNSUPPORTED_BOUNDED_JSON
            active.add(identity)
            list_values: list[Any] = []
            for child in item:
                value = visit(child, depth + 1)
                if value is _UNSUPPORTED_BOUNDED_JSON:
                    active.remove(identity)
                    return _UNSUPPORTED_BOUNDED_JSON
                list_values.append(value)
            active.remove(identity)
            return list_values
        from pydantic import BaseModel

        if isinstance(item, BaseModel):
            identity = id(item)
            if identity in active:
                return _UNSUPPORTED_BOUNDED_JSON
            try:
                model_values = object.__getattribute__(item, "__dict__")
            except (AttributeError, TypeError):
                return _UNSUPPORTED_BOUNDED_JSON
            if type(model_values) is not dict:
                return _UNSUPPORTED_BOUNDED_JSON
            active.add(identity)
            result = visit(model_values, depth + 1)
            active.remove(identity)
            return result
        if type(item) is dict:
            if len(item) > max_elements - budget[0]:
                return _UNSUPPORTED_BOUNDED_JSON
            identity = id(item)
            if identity in active:
                return _UNSUPPORTED_BOUNDED_JSON
            keys = tuple(item.keys())
            if any(
                type(key) is not str or not key or len(key) > max_bytes - budget[1] for key in keys
            ):
                return _UNSUPPORTED_BOUNDED_JSON
            active.add(identity)
            values: dict[str, Any] = {}
            for key in sorted(keys):
                key_bytes = len(key.encode("utf-8"))
                if key_bytes > max_bytes - budget[1]:
                    active.remove(identity)
                    return _UNSUPPORTED_BOUNDED_JSON
                budget[1] += key_bytes
                child = visit(item[key], depth + 1)
                if child is _UNSUPPORTED_BOUNDED_JSON:
                    active.remove(identity)
                    return _UNSUPPORTED_BOUNDED_JSON
                values[key] = child
            active.remove(identity)
            return values
        return _UNSUPPORTED_BOUNDED_JSON

    return visit(value, 0)


def _captured_parameter_value(
    name: str,
    *,
    source: Literal[
        "requested",
        "signature_default",
        "signature_default_unresolved",
        "requested_unresolved",
    ],
    value: Any,
) -> MethodExecutionParameterValue:
    """Freeze a bounded JSON parameter value or state why its codec is unknown."""
    frozen_value = _bounded_json_value(
        value,
        max_bytes=_MAX_METHOD_PARAMETER_VALUE_BYTES,
        max_elements=128,
        max_depth=8,
    )
    if frozen_value is _UNSUPPORTED_BOUNDED_JSON:
        return MethodExecutionParameterValue(
            name=name[:256] or "__unmodeled_parameter__",
            source=source,
            status="unsupported_codec",
            limitation="method_parameter_value_not_bounded_json",
        )
    try:
        encoded = json.dumps(
            frozen_value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError, OverflowError, RecursionError):
        return MethodExecutionParameterValue(
            name=name[:256] or "__unmodeled_parameter__",
            source=source,
            status="unsupported_codec",
            limitation="method_parameter_value_not_bounded_json",
        )
    if len(encoded.encode("utf-8")) > _MAX_METHOD_PARAMETER_VALUE_BYTES:
        return MethodExecutionParameterValue(
            name=name[:256] or "__unmodeled_parameter__",
            source=source,
            status="unsupported_codec",
            limitation="method_parameter_value_exceeds_capture_limit",
        )
    return MethodExecutionParameterValue(
        name=name,
        source=source,
        status="captured",
        value=frozen_value,
        value_sha256=hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
    )


def _method_parameter_values(
    node: Any | None,
    method_class: type[Any] | None,
) -> tuple[tuple[MethodExecutionParameterValue, ...], str | None, int | None, int | None]:
    """Capture requested params and exact signature defaults used by the runner."""
    if node is None or method_class is None:
        return (), "loaded_method_signature_unavailable", None, _MAX_METHOD_PARAMETER_COUNT
    requested = node.method_params if isinstance(node.method_params, Mapping) else {}
    signature = method_class.signature
    signature_params = signature.parameters
    observed_count = max(len(requested), len(signature_params))
    if (
        len(requested) > _MAX_METHOD_PARAMETER_COUNT
        or len(signature_params) > _MAX_METHOD_PARAMETER_COUNT
    ):
        return (
            (),
            "method_parameter_inventory_exceeds_capture_limit",
            observed_count,
            _MAX_METHOD_PARAMETER_COUNT,
        )
    parameter_specs = {item.name: item for item in signature_params}
    values: list[MethodExecutionParameterValue] = []
    names = sorted(set(requested) | set(parameter_specs))
    if len(names) > _MAX_METHOD_PARAMETER_COUNT:
        return (
            (),
            "method_parameter_inventory_exceeds_capture_limit",
            len(names),
            _MAX_METHOD_PARAMETER_COUNT,
        )
    for raw_name in names:
        if type(raw_name) is not str or not raw_name or len(raw_name) > 256:
            return (
                (),
                "method_parameter_name_inventory_not_established",
                len(names),
                _MAX_METHOD_PARAMETER_COUNT,
            )
        name = raw_name
        if name in requested:
            source: Literal[
                "requested",
                "signature_default",
                "signature_default_unresolved",
                "requested_unresolved",
            ] = "requested" if name in parameter_specs else "requested_unresolved"
            values.append(_captured_parameter_value(name, source=source, value=requested[name]))
            continue
        parameter = parameter_specs[name]
        values.append(
            _captured_parameter_value(
                name,
                source="signature_default",
                value=parameter.default,
            )
        )
    if any(value.status != "captured" for value in values):
        return (
            tuple(values),
            "method_effective_parameter_values_not_established",
            len(names),
            _MAX_METHOD_PARAMETER_COUNT,
        )
    return tuple(values), None, len(values), _MAX_METHOD_PARAMETER_COUNT


_MAX_METHOD_PRESTATE_HASH_BYTES = 4 * 1024 * 1024
_MAX_METHOD_METRIC_INPUT_CAPTURE_BYTES = 4 * 1024 * 1024
_MAX_METHOD_CAPTURE_ARRAY_ELEMENTS = 1_000_000
_MAX_METHOD_EXECUTION_OCCURRENCES = 128
_MAX_METHOD_RETURNED_SLOTS = METHOD_METRIC_BINDING_LIMIT
_MAX_METHOD_ARTIFACTS = 32
_MAX_METHOD_CAPTURE_BUNDLE_BYTES = 16 * 1024 * 1024
_MAX_METHOD_PARAMETER_COUNT = 32
_MAX_METHOD_PARAMETER_VALUE_BYTES = 1024
_MAX_METHOD_CAPTURE_SIDECAR_BYTES = 4 * 1024 * 1024
_MAX_METHOD_OUTPUT_PAYLOAD_BYTES = 64 * 1024
_MAX_METHOD_ARTIFACT_PAYLOAD_BYTES = 64 * 1024
_MAX_METHOD_ARTIFACT_PAYLOAD_ELEMENTS = 1024
_MAX_METHOD_CAPTURE_LIMITATIONS = 32
_MAX_METHOD_CAPTURE_MANIFEST_EDGES = 9000
_MAX_METHOD_CAPTURE_SIDECAR_REFS = 8192
_MAX_METHOD_CAPTURE_INPUT_BYTES = 32 * 1024 * 1024
_METHOD_PRESTATE_IDENTITY_ALGORITHM = "policyos.method_dispatch_input_map.sha256.v1"
_METHOD_PRESTATE_IDENTITY_DOMAIN = b"policyos.method_dispatch_input_map.sha256.v1\0"
_RefT = TypeVar("_RefT", bound=ArtifactRef)


def _materialize_exact_method_input_state(
    state: Any,
    *,
    node: ProgramNode,
    method_class: type[Any],
    slot_registry: SlotRegistry,
) -> Any:
    """Materialize declared method inputs only when graph IDs match ABI slot IDs.

    The graph has no separate positional input-port binding. A method-specific
    mapping is therefore emitted only for the exact identity join between
    ``ProgramNode.inputs`` and the loaded method ABI. Ambiguous or partial
    joins preserve the existing ambient state and will be recorded as
    unestablished by the dispatch capture.
    """
    signature_input_slots = method_class.signature.input_slots
    if len(signature_input_slots) > 32:
        return state
    signature_input_ids = {slot.name for slot in signature_input_slots}
    graph_input_ids = tuple(node.inputs)
    if (
        not signature_input_ids
        or not graph_input_ids
        or len(graph_input_ids) != len(signature_input_ids)
        or set(graph_input_ids) != signature_input_ids
        or len(set(graph_input_ids)) != len(graph_input_ids)
    ):
        return state

    materialized: dict[str, Any] = {}
    try:
        for slot_id in graph_input_ids:
            graph_slot = slot_registry.slots.get(slot_id)
            state_path = graph_slot.state_path if graph_slot is not None else None
            value = state
            for segment in (state_path or slot_id).split("."):
                if isinstance(value, Mapping) and segment in value:
                    value = value[segment]
                elif hasattr(value, segment):
                    value = getattr(value, segment)
                else:
                    raise KeyError(segment)
            materialized[slot_id] = value
    except (AttributeError, KeyError, IndexError, TypeError, ValueError):
        return state
    return materialized


def _bounded_array_metadata(value: Any) -> tuple[tuple[int, ...], np.dtype[Any], int, int] | None:
    """Read array metadata and enforce dimensions before any device transfer."""
    if not isinstance(value, (np.ndarray, np.generic, jax.Array)):
        return None
    shape = getattr(value, "shape", None)
    dtype = getattr(value, "dtype", None)
    if not isinstance(shape, tuple) or len(shape) > 4 or dtype is None:
        return None
    try:
        if any(type(size) is not int for size in shape):
            return None
        dims = tuple(shape)
        resolved_dtype = np.dtype(dtype)
        if (
            len(dims) > 4
            or any(size < 0 for size in dims)
            or resolved_dtype.hasobject
            or resolved_dtype.kind not in {"i", "u", "f", "b"}
        ):
            return None
        count = math.prod(dims) if dims else 1
        byte_count = count * resolved_dtype.itemsize
        if (
            count > _MAX_METHOD_CAPTURE_ARRAY_ELEMENTS
            or byte_count > _MAX_METHOD_PRESTATE_HASH_BYTES
        ):
            return None
        return dims, resolved_dtype, count, byte_count
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None


def _bounded_array_value(value: Any, *, max_bytes: int) -> np.ndarray | None:
    """Copy one supported NumPy/JAX value only after metadata and byte preflight."""
    metadata = _bounded_array_metadata(value)
    if metadata is None:
        return None
    shape, dtype, _count, byte_count = metadata
    if byte_count > max_bytes:
        return None
    try:
        array = np.asarray(jax.device_get(value))
        if array.shape != shape or array.dtype != dtype or array.dtype.hasobject:
            return None
        if array.nbytes != byte_count:
            return None
        copied = np.array(array, copy=True, order="C")
        if copied.dtype.kind == "f" and not np.isfinite(copied).all():
            return None
        return copied
    except (TypeError, ValueError, OverflowError, RuntimeError, RecursionError):
        return None


def _bounded_method_input_arrays(
    state: Any,
    *,
    slot_ids: tuple[str, ...],
    require_vectors: bool,
    max_bytes: int = _MAX_METHOD_METRIC_INPUT_CAPTURE_BYTES,
) -> dict[str, np.ndarray] | None:
    """Preflight a flat method input map before transferring or copying arrays."""
    if (
        not isinstance(state, Mapping)
        or len(slot_ids) == 0
        or len(slot_ids) > 32
        or len(set(slot_ids)) != len(slot_ids)
        or any(type(slot_id) is not str or not slot_id for slot_id in slot_ids)
        or len(state) != len(slot_ids)
        or set(state) != set(slot_ids)
    ):
        return None
    metadata_by_slot: dict[str, tuple[tuple[int, ...], np.dtype[Any], int, int]] = {}
    total_bytes = 0
    total_elements = 0
    for slot_id in slot_ids:
        metadata = _bounded_array_metadata(state[slot_id])
        if metadata is None:
            return None
        shape, _dtype, count, byte_count = metadata
        if require_vectors and (len(shape) != 1 or count == 0):
            return None
        total_bytes += byte_count
        total_elements += count
        if (
            total_bytes > min(max_bytes, _MAX_METHOD_METRIC_INPUT_CAPTURE_BYTES)
            or total_elements > _MAX_METHOD_CAPTURE_ARRAY_ELEMENTS
        ):
            return None
        metadata_by_slot[slot_id] = metadata
    arrays: dict[str, np.ndarray] = {}
    for slot_id in sorted(slot_ids):
        value = _bounded_array_value(
            state[slot_id],
            max_bytes=metadata_by_slot[slot_id][3],
        )
        if value is None:
            return None
        arrays[slot_id] = value
    return arrays


def _array_identity_bytes(value: np.ndarray) -> memoryview | None:
    """Expose bounded C-order numeric bytes without an avoidable array copy."""
    metadata = _bounded_array_metadata(value)
    if metadata is None:
        return None
    if value.dtype.kind == "f" and not np.isfinite(value).all():
        return None
    try:
        array = value if value.flags.c_contiguous else np.ascontiguousarray(value)
        return memoryview(array).cast("B")
    except (TypeError, ValueError, BufferError):
        return None


def _method_dispatch_input_identity(arrays: Mapping[str, np.ndarray]) -> str:
    """Hash the exact flat method input mapping with a replayable domain-separated rule."""
    digest = hashlib.sha256()
    digest.update(_METHOD_PRESTATE_IDENTITY_DOMAIN)
    for slot_id in sorted(arrays):
        value = arrays[slot_id]
        raw = _array_identity_bytes(value)
        if raw is None:
            raise ValueError("method_dispatch_input_identity_not_bounded")
        slot_bytes = slot_id.encode("utf-8")
        dtype_bytes = value.dtype.str.encode("ascii")
        shape_bytes = json.dumps(value.shape, separators=(",", ":")).encode("ascii")
        for part in (slot_bytes, dtype_bytes, shape_bytes):
            digest.update(len(part).to_bytes(8, "big"))
            digest.update(part)
        digest.update(len(raw).to_bytes(8, "big"))
        digest.update(raw)
    return digest.hexdigest()


def _bounded_value_identity(value: Any) -> tuple[str, tuple[int, ...], str] | None:
    """Return a bounded array identity without coercing lists or unknown values."""
    if isinstance(value, np.ndarray):
        array = value
        if _bounded_array_metadata(array) is None:
            return None
    else:
        array = _bounded_array_value(value, max_bytes=_MAX_METHOD_PRESTATE_HASH_BYTES)
        if array is None:
            return None
    raw = _array_identity_bytes(array)
    if raw is None:
        return None
    digest = hashlib.sha256()
    digest.update(array.dtype.str.encode("ascii"))
    digest.update(json.dumps(array.shape, separators=(",", ":")).encode("ascii"))
    digest.update(raw)
    return digest.hexdigest(), tuple(int(size) for size in array.shape), array.dtype.str


def _method_input_slot_values(
    state: Any,
    method_class: type[Any],
    *,
    input_arrays: dict[str, np.ndarray] | None,
) -> tuple[MethodExecutionInputSlot, ...]:
    """Record exact input identities only from the preflighted actual dispatch map."""
    signature_slots = method_class.signature.input_slots
    if len(signature_slots) > 32:
        return ()
    values: list[MethodExecutionInputSlot] = []
    for slot in sorted(signature_slots, key=lambda item: item.name):
        if input_arrays is None or slot.name not in input_arrays:
            values.append(
                MethodExecutionInputSlot(
                    slot_id=slot.name,
                    status="not_established",
                    limitation="method_input_slot_map_not_bounded_or_not_exact",
                )
            )
            continue
        value = input_arrays[slot.name]
        identity = _bounded_value_identity(value)
        if identity is None:
            values.append(
                MethodExecutionInputSlot(
                    slot_id=slot.name,
                    status="not_established",
                    runtime_type=f"{type(value).__module__}.{type(value).__qualname__}",
                    limitation="method_input_slot_content_identity_unavailable_or_over_bound",
                )
            )
            continue
        value_sha256, shape, dtype = identity
        values.append(
            MethodExecutionInputSlot(
                slot_id=slot.name,
                status="captured",
                value_sha256=value_sha256,
                runtime_type=f"{type(value).__module__}.{type(value).__qualname__}",
                runtime_shape=shape,
                runtime_dtype=dtype,
            )
        )
    return tuple(values)


def _capture_method_metric_dispatch_inputs(
    store: CoreJSONArtifactStore,
    *,
    capture: MethodExecutionCapture,
    occurrence_id: str,
    invocation_id: str,
    node_id: str,
    step: int,
    state: Any,
    input_arrays: dict[str, np.ndarray] | None,
    method_class: type[Any],
    binding: MethodMetricBinding | None,
    prestate_identity: str | None,
    source_state_ref: ArtifactRef | None,
) -> tuple[
    tuple[MethodExecutionInputSlot, ...],
    tuple[MethodExecutionInputRole, ...],
    MethodMetricInputCaptureRef | None,
    Literal["captured", "not_established", "not_required"],
    str | None,
    StateSnapshotRef | None,
]:
    """Persist one bounded current-input snapshot and its registered-law metadata."""
    is_registered_ex_ante = (
        binding is not None
        and binding.availability == "available"
        and binding.law_id == METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID
        and registered_method_metric_semantics_match(binding.law_id, binding.semantics)
    )
    if not is_registered_ex_ante or binding is None or binding.semantics is None:
        return (
            _method_input_slot_values(state, method_class, input_arrays=input_arrays),
            (),
            None,
            "not_required",
            None,
            None,
        )

    expected_input_slots = tuple(sorted(slot.name for slot in method_class.signature.input_slots))
    if expected_input_slots != ("baseline", "scenario"):
        return (
            _method_input_slot_values(state, method_class, input_arrays=input_arrays),
            (),
            None,
            "not_established",
            "method_metric_registered_input_set_mismatch",
            None,
        )
    arrays = input_arrays
    if arrays is None or set(arrays) != set(expected_input_slots):
        return (
            _method_input_slot_values(state, method_class, input_arrays=input_arrays),
            (),
            None,
            "not_established",
            "method_metric_required_input_unavailable_or_over_bound",
            None,
        )
    actual_identity = _method_dispatch_input_identity(arrays)
    if prestate_identity is None or prestate_identity != actual_identity:
        return (
            _method_input_slot_values(arrays, method_class, input_arrays=arrays),
            (),
            None,
            "not_established",
            "method_prestate_identity_not_reconciled",
            None,
        )

    signature_slots = {slot.name: slot for slot in method_class.signature.input_slots}
    captured_slots: list[MethodMetricInputCaptureSlot] = []
    input_slot_rows: list[MethodExecutionInputSlot] = []
    for slot_id in expected_input_slots:
        array = arrays[slot_id]
        value_sha256, shape, dtype = _bounded_value_identity(array) or (None, None, None)
        if value_sha256 is None or shape is None or dtype is None:
            return (
                _method_input_slot_values(arrays, method_class, input_arrays=arrays),
                (),
                None,
                "not_established",
                "method_metric_required_input_identity_unavailable",
                None,
            )
        slot = signature_slots[slot_id]
        source_unit = MethodMetricSourceUnit(
            dimension=slot.unit.dimension,
            symbol=slot.unit.symbol,
            scale=float(slot.unit.scale),
        )
        captured_slots.append(
            MethodMetricInputCaptureSlot(
                slot_id=slot_id,
                dtype=dtype,
                shape=shape,
                value_sha256=value_sha256,
                unit=source_unit,
            )
        )
        input_slot_rows.append(
            MethodExecutionInputSlot(
                slot_id=slot_id,
                status="captured",
                value_sha256=value_sha256,
                runtime_type=f"{type(state[slot_id]).__module__}.{type(state[slot_id]).__qualname__}",
                runtime_shape=shape,
                runtime_dtype=dtype,
            )
        )
    captured_by_id = {item.slot_id: item for item in captured_slots}
    role_values = tuple(
        MethodExecutionInputRole(
            role_id=role.role_id,
            slot_id=role.method_input_slot_id,
            value_sha256=captured_by_id[role.method_input_slot_id].value_sha256,
        )
        for role in binding.semantics.input_roles
    )

    snapshot_inputs = (
        [artifact_input_ref(source_state_ref, role="dispatch_origin_state")]
        if source_state_ref is not None
        and source_state_ref.kind == "foundry.state_snapshot"
        and source_state_ref.manifest_profile_sha256 is not None
        else []
    )
    try:
        persisted_snapshot_ref = put_state_snapshot(
            store,
            state=arrays,
            step=step,
            inputs=snapshot_inputs,
            return_selected_profile=True,
        )
        selected_prestate_ref = _selected_typed_ref(
            store,
            persisted_snapshot_ref,
            StateSnapshotRef,
        )
        payload = MethodMetricInputCapturePayload(
            program_graph_ref=capture.program_graph_ref,
            exec_plan_ref=capture.exec_plan_ref,
            method_metric_binding_set_ref=capture.method_metric_binding_set_ref,
            occurrence_id=occurrence_id,
            invocation_id=invocation_id,
            node_id=node_id,
            prestate_identity_algorithm=_METHOD_PRESTATE_IDENTITY_ALGORITHM,
            prestate_identity_sha256=actual_identity,
            pre_dispatch_state_ref=selected_prestate_ref,
            slots=tuple(captured_slots),
        )
        payload_bytes = json.dumps(
            payload.model_dump(mode="json"),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(payload_bytes) > 65536:
            raise ValueError("method_metric_input_capture_metadata_exceeds_byte_limit")
        ref = store.put_json(
            payload,
            PutOptions(
                kind=MethodMetricInputCapturePayload.ARTIFACT_KIND,
                media_type=MethodMetricInputCapturePayload.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=MethodMetricInputCapturePayload.ARTIFACT_SCHEMA_NAME,
                    version=MethodMetricInputCapturePayload.ARTIFACT_SCHEMA_VERSION,
                ),
                inputs=[
                    artifact_input_ref(capture.program_graph_ref, role="program_graph"),
                    artifact_input_ref(capture.exec_plan_ref, role="exec_plan"),
                    artifact_input_ref(
                        capture.method_metric_binding_set_ref,
                        role="method_metric_binding_set",
                    ),
                    artifact_input_ref(selected_prestate_ref, role="pre_dispatch_state"),
                ],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        selected_capture_ref = _selected_typed_ref(store, ref, MethodMetricInputCaptureRef)
    except Exception as exc:
        return (
            tuple(input_slot_rows),
            role_values,
            None,
            "not_established",
            f"method_metric_input_capture_persistence_failed:{type(exc).__name__}",
            None,
        )
    return (
        tuple(input_slot_rows),
        role_values,
        selected_capture_ref,
        "captured",
        None,
        selected_prestate_ref,
    )


def _bounded_method_prestate_identity(state: Any) -> str | None:
    """Hash a flat, bounded method input mapping before recording its provenance."""
    if not isinstance(state, Mapping) or len(state) == 0 or len(state) > 32:
        return None
    slot_ids = tuple(sorted(state))
    if any(type(slot_id) is not str for slot_id in slot_ids):
        return None
    arrays = _bounded_method_input_arrays(state, slot_ids=slot_ids, require_vectors=False)
    return None if arrays is None else _method_dispatch_input_identity(arrays)


def _method_key_words(step_key: jax.Array) -> tuple[int, ...]:
    """Return the bounded exact integer words of the dispatched JAX key."""
    try:
        words = np.asarray(jax.random.key_data(step_key)).reshape(-1)
        return tuple(int(word) for word in words)
    except (AttributeError, TypeError, ValueError, OverflowError, RuntimeError):
        return ()


def _dispatch_record_with_updates(
    planned: MethodExecutionDispatchRecord,
    **updates: Any,
) -> MethodExecutionDispatchRecord:
    """Validate a terminal dispatch record while retaining planned facts."""
    payload = planned.model_dump(mode="python")
    payload.update(updates)
    return MethodExecutionDispatchRecord.model_validate(payload)


def _successful_method_dispatch_record(
    planned: MethodExecutionDispatchRecord,
    *,
    started_at: datetime,
    started_counter: float,
    method_seed: int,
    key_words: tuple[int, ...],
    root_seed: int,
    step: int,
    prestate_identity: str | None,
    input_state_ref: StateSnapshotRef | None,
    source_state_ref: ArtifactRef | None,
    method_class: type[Any],
    method_result: Any,
    input_slot_values: tuple[MethodExecutionInputSlot, ...],
    input_role_values: tuple[MethodExecutionInputRole, ...],
    metric_input_capture_ref: MethodMetricInputCaptureRef | None,
    metric_input_capture_status: Literal["captured", "not_established", "not_required"],
    metric_input_capture_limitation: str | None,
) -> MethodExecutionDispatchRecord:
    """Reconcile graph seed, runner identity, timing, and dispatcher trace."""
    completed_at = datetime.now(UTC)
    reproducibility = method_result.reproducibility
    artifacts = method_result.artifacts if isinstance(method_result.artifacts, Mapping) else {}
    raw_trace = artifacts.get("dispatch_trace")
    trace = raw_trace if isinstance(raw_trace, Mapping) else {}
    requested_backend = trace.get("requested_backend")
    selected_backend = trace.get("selected_backend")
    raw_attempts = trace.get("attempts")
    attempts: list[MethodExecutionBackendAttempt] = []
    trace_valid = (
        isinstance(requested_backend, str)
        and isinstance(selected_backend, str)
        and isinstance(raw_attempts, list)
        and 0 < len(raw_attempts) <= 32
    )
    if trace_valid and isinstance(raw_attempts, list):
        for attempt in raw_attempts:
            if (
                not isinstance(attempt, Mapping)
                or not isinstance(attempt.get("backend"), str)
                or not isinstance(attempt.get("outcome"), str)
            ):
                trace_valid = False
                attempts = []
                break
            attempts.append(
                MethodExecutionBackendAttempt(
                    backend=attempt["backend"],
                    outcome=attempt["outcome"],
                )
            )
        if trace_valid:
            terminal_attempt = attempts[-1]
            trace_valid = (
                terminal_attempt.outcome == "success"
                and terminal_attempt.backend == selected_backend
            )
    if not trace_valid:
        requested_backend = planned.requested_backend
        selected_backend = None
        attempts = []
    actual_backend = getattr(reproducibility.backend, "value", None)
    backend_status = (
        "not_established"
        if not trace_valid or not isinstance(actual_backend, str)
        else "reconciled"
        if actual_backend == selected_backend
        else "mismatch"
    )
    runner_seed = reproducibility.seed
    seed_status: Literal["reconciled", "mismatch", "not_established", "not_started"] = (
        "not_established"
        if runner_seed is None
        else "reconciled"
        if int(runner_seed) == method_seed
        else "mismatch"
    )
    fallback_status: Literal["fell_back", "not_fell_back", "not_established", "not_started"]
    if not trace_valid:
        fallback_status = "not_established"
    elif any(attempt.outcome != "success" for attempt in attempts[:-1]):
        fallback_status = "fell_back"
    else:
        fallback_status = "not_fell_back"
    has_selected_prestate = (
        prestate_identity is not None
        and input_state_ref is not None
        and input_state_ref.manifest_profile_sha256 is not None
    )
    input_status = "captured" if has_selected_prestate else "not_established"
    input_limitation = (
        None
        if has_selected_prestate
        else "method_prestate_selected_snapshot_or_content_identity_unavailable"
    )
    actual_prestate_ref = (
        StateSnapshotRef.model_validate(input_state_ref.model_dump(mode="python"))
        if has_selected_prestate and input_state_ref is not None
        else None
    )
    source_ref = None
    if (
        source_state_ref is not None
        and source_state_ref.kind == "foundry.state_snapshot"
        and source_state_ref.manifest_profile_sha256 is not None
    ):
        source_ref = StateSnapshotRef.model_validate(source_state_ref.model_dump(mode="python"))
    timing = method_result.timing
    return _dispatch_record_with_updates(
        planned,
        outcome="succeeded",
        started_at=started_at,
        completed_at=completed_at,
        dispatch_elapsed_ms=max((time.perf_counter() - started_counter) * 1000.0, 0.0),
        runner_wall_time_ms=float(timing.wall_time_ms),
        runner_cpu_time_ms=(None if timing.cpu_time_ms is None else float(timing.cpu_time_ms)),
        runner_compile_time_ms=(
            None if timing.compile_time_ms is None else float(timing.compile_time_ms)
        ),
        input_state_ref=actual_prestate_ref,
        input_state_relation=(
            "current_visible_state" if has_selected_prestate else "not_established"
        ),
        input_state_identity_algorithm=(
            _METHOD_PRESTATE_IDENTITY_ALGORITHM if has_selected_prestate else None
        ),
        input_state_identity_sha256=prestate_identity if has_selected_prestate else None,
        input_state_source_ref=source_ref,
        input_state_status=input_status,
        input_state_limitation=input_limitation,
        input_slot_values=input_slot_values,
        input_role_values=input_role_values,
        method_metric_input_capture_ref=metric_input_capture_ref,
        method_metric_input_capture_status=metric_input_capture_status,
        method_metric_input_capture_limitation=metric_input_capture_limitation,
        signature_output_slot_ids=planned.signature_output_slot_ids,
        root_seed=root_seed,
        step=step,
        method_key_words=key_words,
        method_seed=method_seed,
        reproducibility_seed=None if runner_seed is None else int(runner_seed),
        seed_status=seed_status,
        rng_state_status="runner_rng_state_not_retained",
        requested_backend=(requested_backend if isinstance(requested_backend, str) else None),
        selected_backend=(selected_backend if isinstance(selected_backend, str) else None),
        actual_backend=actual_backend if isinstance(actual_backend, str) else None,
        backend_selection_reason=(
            trace.get("selection_reason")
            if isinstance(trace.get("selection_reason"), str)
            else None
        ),
        backend_identity_status=backend_status,
        backend_attempts=tuple(attempts),
        backend_trace_status="captured" if trace_valid else "not_established",
        fallback_status=fallback_status,
    )


def _failed_method_dispatch_record(
    planned: MethodExecutionDispatchRecord,
    *,
    started_at: datetime,
    started_counter: float,
    method_seed: int | None,
    key_words: tuple[int, ...],
    root_seed: int,
    step: int,
    prestate_identity: str | None,
    input_state_ref: StateSnapshotRef | None,
    source_state_ref: ArtifactRef | None,
    method_class: type[Any],
    error: Exception,
    input_slot_values: tuple[MethodExecutionInputSlot, ...],
    input_role_values: tuple[MethodExecutionInputRole, ...],
    metric_input_capture_ref: MethodMetricInputCaptureRef | None,
    metric_input_capture_status: Literal["captured", "not_established", "not_required"],
    metric_input_capture_limitation: str | None,
) -> MethodExecutionDispatchRecord:
    """Record a failed invocation without inventing dispatcher observations."""
    completed_at = datetime.now(UTC)
    has_selected_prestate = (
        prestate_identity is not None
        and input_state_ref is not None
        and input_state_ref.manifest_profile_sha256 is not None
    )
    input_status = "captured" if has_selected_prestate else "not_established"
    input_limitation = (
        None
        if has_selected_prestate
        else "method_prestate_selected_snapshot_or_content_identity_unavailable"
    )
    actual_prestate_ref = (
        StateSnapshotRef.model_validate(input_state_ref.model_dump(mode="python"))
        if has_selected_prestate and input_state_ref is not None
        else None
    )
    source_ref = None
    if (
        source_state_ref is not None
        and source_state_ref.kind == "foundry.state_snapshot"
        and source_state_ref.manifest_profile_sha256 is not None
    ):
        source_ref = StateSnapshotRef.model_validate(source_state_ref.model_dump(mode="python"))
    message = str(error).encode("utf-8", errors="replace")
    return _dispatch_record_with_updates(
        planned,
        outcome="failed",
        started_at=started_at,
        completed_at=completed_at,
        dispatch_elapsed_ms=max((time.perf_counter() - started_counter) * 1000.0, 0.0),
        input_state_ref=actual_prestate_ref,
        input_state_relation=(
            "current_visible_state" if has_selected_prestate else "not_established"
        ),
        input_state_identity_algorithm=(
            _METHOD_PRESTATE_IDENTITY_ALGORITHM if has_selected_prestate else None
        ),
        input_state_identity_sha256=prestate_identity if has_selected_prestate else None,
        input_state_source_ref=source_ref,
        input_state_status=input_status,
        input_state_limitation=input_limitation,
        input_slot_values=input_slot_values,
        input_role_values=input_role_values,
        method_metric_input_capture_ref=metric_input_capture_ref,
        method_metric_input_capture_status=metric_input_capture_status,
        method_metric_input_capture_limitation=metric_input_capture_limitation,
        signature_output_slot_ids=planned.signature_output_slot_ids,
        root_seed=root_seed,
        step=step,
        method_key_words=key_words,
        method_seed=method_seed,
        seed_status="not_established",
        rng_state_status="runner_rng_state_not_retained",
        backend_identity_status="not_established",
        backend_trace_status="not_established",
        fallback_status="not_established",
        failure_type=f"{type(error).__module__}.{type(error).__qualname__}",
        failure_message_sha256=hashlib.sha256(message).hexdigest(),
        limitations=tuple(
            dict.fromkeys((*planned.limitations, "dispatcher_failure_trace_not_emitted"))
        ),
    )


def _declared_method_slot_type_name(slot: Any | None) -> str | None:
    """Encode a declared slot type with its stable ABI enum identity."""
    if slot is None:
        return None
    return slot.slot_type.name


def _planned_returned_slots(
    method_class: type[Any] | None,
) -> list[MethodExecutionReturnedSlot]:
    """Inventory ABI outputs only when the full declaration fits the cap."""
    if method_class is None:
        return []
    declared = method_class.signature.output_slots
    if len(declared) > _MAX_METHOD_RETURNED_SLOTS:
        return []
    return [
        MethodExecutionReturnedSlot(
            slot_id=slot.name,
            declared_by_signature=True,
            declared_slot_type=_declared_method_slot_type_name(slot),
            declared_shape=tuple(str(dimension)[:128] for dimension in slot.shape[:4]),
            returned="not_returned",
            runtime_shape_status="not_returned",
            codec_status="not_returned",
            retention_status="not_emitted",
            limitation="method_invocation_not_completed",
        )
        for slot in sorted(declared, key=lambda item: item.name)
    ]


def _planned_method_dispatch(
    *,
    node: Any | None,
    method_class: type[Any] | None,
    method_identity: _MethodExecutionIdentity,
    metric_input_capture_required: bool,
) -> MethodExecutionDispatchRecord:
    """Create a terminally honest not-run record before a graph invocation."""
    parameter_values, parameter_limitation, parameter_count, parameter_limit = (
        _method_parameter_values(node, method_class)
    )
    requested_backend = None
    signature_input_slot_ids: tuple[str, ...] = ()
    signature_output_slot_ids: tuple[str, ...] = ()
    signature_parameter_names: tuple[str, ...] = ()
    signature_input_count: int | None = None
    signature_output_count: int | None = None
    signature_parameter_count: int | None = None
    raw_graph_inputs = getattr(node, "inputs", ()) or ()
    graph_input_count = len(raw_graph_inputs)
    graph_input_ids = tuple(raw_graph_inputs) if graph_input_count <= 32 else ()
    if method_class is not None:
        signature = method_class.signature
        requested_backend = signature.backend.value
        signature_input_count = len(signature.input_slots)
        signature_output_count = len(signature.output_slots)
        signature_parameter_count = len(signature.parameters)
        if signature_input_count <= 32:
            signature_input_slot_ids = tuple(sorted(item.name for item in signature.input_slots))
        if signature_output_count <= _MAX_METHOD_RETURNED_SLOTS:
            signature_output_slot_ids = tuple(sorted(item.name for item in signature.output_slots))
        if signature_parameter_count <= _MAX_METHOD_PARAMETER_COUNT:
            signature_parameter_names = tuple(sorted(item.name for item in signature.parameters))
    elif node is not None and node.node_kind == "method":
        requested_backend = None
    limitations = []
    if parameter_limitation:
        limitations.append(parameter_limitation)
    if graph_input_count > 32:
        limitations.append("graph_input_inventory_exceeds_capture_limit")
    if signature_input_count is not None and signature_input_count > 32:
        limitations.append("method_signature_input_inventory_exceeds_capture_limit")
    if signature_output_count is not None and signature_output_count > _MAX_METHOD_RETURNED_SLOTS:
        limitations.append("method_signature_output_inventory_exceeds_capture_limit")
    if (
        signature_parameter_count is not None
        and signature_parameter_count > _MAX_METHOD_PARAMETER_COUNT
    ):
        limitations.append("method_signature_parameter_inventory_exceeds_capture_limit")
    identity_limitation = method_identity.get("limitation")
    if identity_limitation:
        limitations.append(identity_limitation)
    return MethodExecutionDispatchRecord(
        outcome="not_run",
        method_metric_input_capture_status=(
            "not_started" if metric_input_capture_required else "not_required"
        ),
        input_state_status="not_started",
        graph_input_ids=graph_input_ids,
        graph_input_inventory_observed_count=graph_input_count,
        graph_input_inventory_limit=32,
        signature_input_slot_ids=signature_input_slot_ids,
        signature_output_slot_ids=signature_output_slot_ids,
        signature_parameter_names=signature_parameter_names,
        signature_input_inventory_observed_count=signature_input_count,
        signature_input_inventory_limit=32,
        signature_output_inventory_observed_count=signature_output_count,
        signature_output_inventory_limit=_MAX_METHOD_RETURNED_SLOTS,
        signature_parameter_inventory_observed_count=signature_parameter_count,
        signature_parameter_inventory_limit=_MAX_METHOD_PARAMETER_COUNT,
        parameter_values=parameter_values,
        parameter_resolution_status=("not_established" if parameter_limitation else "captured"),
        parameter_resolution_limitation=parameter_limitation,
        parameter_inventory_observed_count=parameter_count,
        parameter_inventory_limit=parameter_limit,
        seed_status="not_started",
        rng_state_status="not_started",
        requested_backend=requested_backend,
        backend_identity_status="not_started",
        backend_trace_status="not_started",
        fallback_status="not_started",
        limitations=tuple(dict.fromkeys(limitations)),
    )


def _planned_method_occurrence(
    *,
    occurrence_id: str,
    invocation_id: str,
    plan_index: int,
    node: Any | None,
    node_id: str,
    method_identity: _MethodExecutionIdentity | None,
    method_class: type[Any] | None,
    selected_slot_ids: tuple[str, ...],
    metric_input_capture_required: bool,
) -> MethodExecutionOccurrence:
    """Predeclare a plan position before execution, including unresolved nodes."""
    node_kind = node.node_kind if node is not None else "unknown"
    if node_kind not in {"method", "mechanism", "op"}:
        node_kind = "unknown"
    method_fqn = (method_identity or {}).get("method_fqn") if node_kind == "method" else None
    if node_kind == "method" and method_fqn is None and node is not None:
        method_fqn = node.method_fqn
    identity = method_identity or {}
    limitations = []
    identity_limitation = identity.get("limitation")
    if node_kind == "method" and identity_limitation:
        limitations.append(identity_limitation)
    slots = [
        MethodExecutionOutputSlot(
            slot_id=slot_id,
            status="not_emitted",
            limitation="method_invocation_not_completed",
        )
        for slot_id in (selected_slot_ids if node_kind == "method" else ())
    ]
    dispatch = (
        _planned_method_dispatch(
            node=node,
            method_class=method_class,
            method_identity=identity,
            metric_input_capture_required=metric_input_capture_required,
        )
        if node_kind == "method"
        else None
    )
    returned_slots = _planned_returned_slots(method_class) if node_kind == "method" else []
    declared_output_count = (
        None
        if node_kind != "method" or method_class is None
        else len(method_class.signature.output_slots)
    )
    returned_inventory_status = (
        "not_established"
        if declared_output_count is not None and declared_output_count > _MAX_METHOD_RETURNED_SLOTS
        else "not_started"
    )
    return MethodExecutionOccurrence(
        occurrence_id=occurrence_id,
        invocation_id=invocation_id,
        plan_index=plan_index,
        node_id=node_id,
        node_kind=node_kind,
        status="planned",
        method_fqn=method_fqn,
        method_version=identity.get("method_version"),
        method_abi_digest=identity.get("method_abi_digest"),
        method_abi_digest_algorithm=identity.get("method_abi_digest_algorithm"),
        method_build_digest=identity.get("method_build_digest"),
        method_build_digest_scope=identity.get("method_build_digest_scope"),
        output_slots=slots,
        returned_slots=returned_slots,
        returned_slot_inventory_status=returned_inventory_status,
        returned_slot_inventory_limitation=(
            "method_signature_output_inventory_exceeds_capture_limit"
            if returned_inventory_status == "not_established"
            else None
        ),
        returned_slot_inventory_observed_count=declared_output_count,
        returned_slot_inventory_limit=(
            _MAX_METHOD_RETURNED_SLOTS if node_kind == "method" else None
        ),
        dispatch=dispatch,
        limitations=tuple(limitations),
    )


def _runtime_slot_shape(
    value: Any,
) -> tuple[tuple[int, ...] | None, Literal["captured", "not_established"]]:
    """Read runtime shape metadata without converting or copying output arrays."""
    shape = getattr(value, "shape", None)
    if shape is not None:
        try:
            if not isinstance(shape, tuple) or len(shape) > 4:
                return None, "not_established"
            if any(type(dimension) is not int for dimension in shape):
                return None, "not_established"
            dims = tuple(shape)
            if (
                all(dimension >= 0 for dimension in dims)
                and math.prod(dims) <= _MAX_METHOD_CAPTURE_ARRAY_ELEMENTS
            ):
                return dims, "captured"
        except (AttributeError, TypeError, ValueError, OverflowError):
            return None, "not_established"
    if isinstance(value, (int, float, bool, str, bytes, type(None), np.generic)):
        return (), "captured"
    if type(value) in {list, tuple}:
        inspected = 0

        def walk(item: Any, depth: int = 0) -> tuple[int, ...] | None:
            nonlocal inspected
            if inspected >= 4096 or depth > 32:
                return None
            inspected += 1
            if type(item) not in {list, tuple}:
                return ()
            child_count = len(item)
            if child_count > min(_MAX_METHOD_RETURNED_SLOTS, 4096 - inspected):
                return None
            child_shapes: list[tuple[int, ...]] = []
            for index in range(child_count):
                if inspected >= 4096:
                    return None
                child_shape = walk(item[index], depth + 1)
                if child_shape is None:
                    return None
                child_shapes.append(child_shape)
            if child_shapes and any(shape != child_shapes[0] for shape in child_shapes[1:]):
                return None
            return (child_count,) + (child_shapes[0] if child_shapes else ())

        resolved = walk(value)
        return (resolved, "captured") if resolved is not None else (None, "not_established")
    return None, "not_established"


def _runtime_slot_codec_status(
    value: Any,
) -> Literal["json_scalar_supported", "unsupported_codec", "not_attempted"]:
    """Classify JSON scalar codec support without materializing array-like values."""
    if isinstance(value, (str, bool, int)) or value is None:
        return "json_scalar_supported"
    if isinstance(value, float):
        return "json_scalar_supported" if math.isfinite(value) else "unsupported_codec"
    if isinstance(value, np.generic):
        if value.dtype.kind in "iufb":
            if value.dtype.kind == "f" and not math.isfinite(float(value)):
                return "unsupported_codec"
            return "json_scalar_supported"
        return "unsupported_codec"
    if isinstance(value, (list, tuple, dict)) or (
        getattr(value, "shape", None) is not None and getattr(value, "dtype", None) is not None
    ):
        return "not_attempted"
    return "unsupported_codec"


def _returned_slot_inventory_row(
    *,
    slot_id: str,
    value: Any,
    declared_slot: Any | None,
    selected_output: MethodExecutionOutputSlot | None,
) -> MethodExecutionReturnedSlot:
    """Describe one returned value without retaining non-selected method outputs."""
    codec_status = _runtime_slot_codec_status(value)
    runtime_shape, shape_status = _runtime_slot_shape(value)
    runtime_type = f"{type(value).__module__}.{type(value).__qualname__}"[:512]
    dtype = getattr(value, "dtype", None)
    if selected_output is not None and selected_output.status == "captured":
        retention_status = "selected_metric_output"
        limitation = None
        codec_status = "json_scalar_supported"
    elif codec_status == "unsupported_codec":
        retention_status = "unsupported_codec"
        limitation = (
            selected_output.limitation
            if selected_output is not None
            else "returned_method_output_codec_unsupported"
        )
    else:
        retention_status = "not_retained"
        limitation = (
            selected_output.limitation
            if selected_output is not None
            else "unselected_method_output_not_retained"
        )
    return MethodExecutionReturnedSlot(
        slot_id=slot_id,
        declared_by_signature=declared_slot is not None,
        declared_slot_type=_declared_method_slot_type_name(declared_slot),
        declared_shape=(
            None
            if declared_slot is None
            else tuple(str(dimension)[:128] for dimension in declared_slot.shape[:4])
        ),
        returned="returned",
        runtime_type=runtime_type,
        runtime_shape=runtime_shape,
        runtime_shape_status=shape_status,
        runtime_dtype=None if dtype is None else str(dtype)[:128],
        codec_status=codec_status,
        retention_status=retention_status,
        limitation=limitation,
    )


def _capture_method_outputs(
    store: CoreJSONArtifactStore,
    *,
    capture: MethodExecutionCapture,
    occurrence: MethodExecutionOccurrence,
    method_class: type[Any],
    method_result: Any,
    method_identity: _MethodExecutionIdentity,
    bindings: dict[tuple[str, str], MethodMetricBinding],
) -> tuple[
    list[MethodExecutionOutputSlot],
    list[MethodExecutionReturnedSlot],
    Literal["captured", "not_established"],
    str | None,
    int | None,
    int | None,
]:
    """Capture bounded selected scalars and inventory all returned ABI slots."""
    from polisyos.core.artifacts import validate_core_model_json_artifact

    selected = [
        binding
        for (node_id, _slot_id), binding in bindings.items()
        if node_id == occurrence.node_id
    ]
    if len(selected) > _MAX_METHOD_RETURNED_SLOTS:
        raise ValueError("method_metric_selected_output_inventory_exceeds_capture_limit")
    selected_by_slot = {binding.output_slot_id: binding for binding in selected}
    declared_slots = method_class.signature.output_slots
    declared_slot_count = len(declared_slots)
    result_slots = getattr(method_result, "slot_outputs", None)
    if type(result_slots) is not dict:
        limitation = "method_result_slot_inventory_not_established"
        unavailable = [
            MethodExecutionOutputSlot(
                slot_id=slot_id,
                status="unavailable",
                limitation=limitation,
            )
            for slot_id in sorted(selected_by_slot)
        ]
        return unavailable, [], "not_established", limitation, None, _MAX_METHOD_RETURNED_SLOTS

    returned_slot_count = len(result_slots)
    if (
        declared_slot_count > _MAX_METHOD_RETURNED_SLOTS
        or returned_slot_count > _MAX_METHOD_RETURNED_SLOTS
        or declared_slot_count + returned_slot_count > _MAX_METHOD_RETURNED_SLOTS
    ):
        limitation = "method_result_returned_slot_inventory_exceeds_capture_limit"
        unavailable = [
            MethodExecutionOutputSlot(
                slot_id=slot_id,
                status="unavailable",
                limitation=limitation,
            )
            for slot_id in sorted(selected_by_slot)
        ]
        return (
            unavailable,
            [],
            "not_established",
            limitation,
            returned_slot_count + declared_slot_count,
            _MAX_METHOD_RETURNED_SLOTS,
        )

    returned_ids = tuple(result_slots.keys())
    if any(
        type(slot_id) is not str or not slot_id or len(slot_id) > 256 for slot_id in returned_ids
    ):
        limitation = "method_result_returned_slot_identity_not_bounded"
        unavailable = [
            MethodExecutionOutputSlot(
                slot_id=slot_id,
                status="unavailable",
                limitation=limitation,
            )
            for slot_id in sorted(selected_by_slot)
        ]
        return (
            unavailable,
            [],
            "not_established",
            limitation,
            returned_slot_count + declared_slot_count,
            _MAX_METHOD_RETURNED_SLOTS,
        )
    declared_by_slot = {slot.name: slot for slot in declared_slots}
    all_slot_ids = set(declared_by_slot) | set(returned_ids)
    if len(all_slot_ids) > _MAX_METHOD_RETURNED_SLOTS:
        limitation = "method_result_returned_slot_inventory_exceeds_capture_limit"
        unavailable = [
            MethodExecutionOutputSlot(
                slot_id=slot_id,
                status="unavailable",
                limitation=limitation,
            )
            for slot_id in sorted(selected_by_slot)
        ]
        return (
            unavailable,
            [],
            "not_established",
            limitation,
            len(all_slot_ids),
            _MAX_METHOD_RETURNED_SLOTS,
        )

    selected_outputs: dict[str, MethodExecutionOutputSlot] = {}
    for slot_id in sorted(selected_by_slot):
        binding = selected_by_slot[slot_id]
        if (
            method_identity.get("method_fqn") != binding.method_fqn
            or method_identity.get("method_version") != binding.method_version
            or method_identity.get("method_abi_digest") != binding.method_abi_digest
            or method_identity.get("method_abi_digest_algorithm")
            != binding.method_abi_digest_algorithm
            or method_identity.get("method_build_digest") != binding.method_build_digest
        ):
            selected_outputs[slot_id] = MethodExecutionOutputSlot(
                slot_id=slot_id,
                status="unavailable",
                limitation="compiled_method_abi_identity_mismatch",
            )
            continue
        if slot_id not in result_slots:
            selected_outputs[slot_id] = MethodExecutionOutputSlot(
                slot_id=slot_id,
                status="not_emitted",
                limitation="declared_method_slot_not_emitted",
            )
            continue
        selected_value = result_slots[slot_id]
        path_error = False
        for segment in binding.output_value_path:
            if isinstance(selected_value, Mapping) and segment in selected_value:
                selected_value = selected_value[segment]
            else:
                path_error = True
                break
        if path_error:
            selected_outputs[slot_id] = MethodExecutionOutputSlot(
                slot_id=slot_id,
                status="unavailable",
                limitation="bound_method_output_value_path_not_found",
            )
            continue
        if isinstance(selected_value, bool):
            scalar = None
        elif isinstance(selected_value, int):
            scalar = selected_value if selected_value.bit_length() <= 4096 else None
        elif isinstance(selected_value, float):
            scalar = selected_value
        elif isinstance(selected_value, np.generic) and selected_value.dtype.kind in "iuf":
            scalar = selected_value.item()
        elif getattr(selected_value, "shape", None) == ():
            metadata = _bounded_array_metadata(selected_value)
            array = (
                _bounded_array_value(selected_value, max_bytes=metadata[3])
                if metadata is not None and metadata[2] == 1
                else None
            )
            scalar = (
                array.item()
                if array is not None and array.shape == () and array.dtype.kind in "iuf"
                else None
            )
        else:
            scalar = None
        if scalar is None or isinstance(scalar, bool):
            selected_outputs[slot_id] = MethodExecutionOutputSlot(
                slot_id=slot_id,
                status="unavailable",
                limitation="output_not_finite_numeric_scalar",
            )
            continue
        finite = (isinstance(scalar, int) and scalar.bit_length() <= 4096) or (
            isinstance(scalar, float) and math.isfinite(scalar)
        )
        if not finite:
            selected_outputs[slot_id] = MethodExecutionOutputSlot(
                slot_id=slot_id,
                status="unavailable",
                limitation="output_not_finite_numeric_scalar",
            )
            continue
        payload = MethodOutputPayload(
            occurrence_id=occurrence.occurrence_id,
            invocation_id=occurrence.invocation_id,
            node_id=occurrence.node_id,
            slot_id=slot_id,
            value_path=binding.output_value_path,
            value=scalar,
        )
        try:
            payload_bytes = json.dumps(
                payload.model_dump(mode="json"),
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            if len(payload_bytes) > _MAX_METHOD_OUTPUT_PAYLOAD_BYTES:
                raise ValueError("method_output_payload_exceeds_byte_limit")
            if capture.sidecar_refs_used >= _MAX_METHOD_CAPTURE_SIDECAR_REFS:
                raise ValueError("method_output_sidecar_ref_limit_exceeded")
            if len(payload_bytes) > _MAX_METHOD_CAPTURE_SIDECAR_BYTES - capture.sidecar_bytes_used:
                raise ValueError("method_output_sidecar_byte_limit_exceeded")
            output_ref = store.put_json(
                payload,
                PutOptions(
                    kind=MethodOutputPayload.ARTIFACT_KIND,
                    media_type="application/json",
                    schema=SchemaInfo(
                        name=MethodOutputPayload.ARTIFACT_SCHEMA_NAME,
                        version=MethodOutputPayload.ARTIFACT_SCHEMA_VERSION,
                    ),
                    inputs=[
                        artifact_input_ref(capture.program_graph_ref, role="program_graph"),
                        artifact_input_ref(capture.exec_plan_ref, role="exec_plan"),
                        artifact_input_ref(
                            capture.method_metric_binding_set_ref,
                            role="method_metric_binding_set",
                        ),
                    ],
                ),
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )
            selected_output_ref = _selected_typed_ref(store, output_ref, MethodOutputRef)
            validate_core_model_json_artifact(MethodOutputPayload, store, selected_output_ref)
        except Exception as exc:
            selected_outputs[slot_id] = MethodExecutionOutputSlot(
                slot_id=slot_id,
                status="unavailable",
                limitation=f"method_output_capture_failed:{type(exc).__name__}"[:512],
            )
            continue
        capture.sidecar_refs_used += 1
        capture.sidecar_bytes_used += len(payload_bytes)
        selected_outputs[slot_id] = MethodExecutionOutputSlot(
            slot_id=slot_id,
            status="captured",
            output_ref=selected_output_ref,
        )

    inventory: list[MethodExecutionReturnedSlot] = []
    for slot_id in sorted(all_slot_ids):
        declared_slot = declared_by_slot.get(slot_id)
        if slot_id not in result_slots:
            inventory.append(
                MethodExecutionReturnedSlot(
                    slot_id=slot_id,
                    declared_by_signature=declared_slot is not None,
                    declared_slot_type=_declared_method_slot_type_name(declared_slot),
                    declared_shape=(
                        None
                        if declared_slot is None
                        else tuple(str(dimension)[:128] for dimension in declared_slot.shape[:4])
                    ),
                    returned="not_returned",
                    runtime_shape_status="not_returned",
                    codec_status="not_returned",
                    retention_status="not_emitted",
                    limitation="declared_method_slot_not_emitted",
                )
            )
        else:
            inventory.append(
                _returned_slot_inventory_row(
                    slot_id=slot_id,
                    value=result_slots[slot_id],
                    declared_slot=declared_slot,
                    selected_output=selected_outputs.get(slot_id),
                )
            )
    return (
        list(selected_outputs.values()),
        inventory,
        "captured",
        None,
        len(inventory),
        _MAX_METHOD_RETURNED_SLOTS,
    )


def _capture_method_artifacts(
    store: CoreJSONArtifactStore,
    *,
    capture: MethodExecutionCapture,
    occurrence: MethodExecutionOccurrence,
    method_result: Any,
) -> tuple[
    list[MethodExecutionArtifact],
    Literal["captured", "not_established"],
    str | None,
    int | None,
    int | None,
]:
    """Persist only bounded JSON sidecars and inventory every exact artifact key."""
    from pydantic import BaseModel

    from polisyos.core.artifacts import validate_core_model_json_artifact

    artifacts = getattr(method_result, "artifacts", None)
    if type(artifacts) is not dict:
        return (
            [],
            "not_established",
            "method_artifact_inventory_not_mapping",
            None,
            _MAX_METHOD_ARTIFACTS,
        )
    observed_count = len(artifacts)
    if observed_count > _MAX_METHOD_ARTIFACTS:
        return (
            [],
            "not_established",
            "method_artifact_inventory_exceeds_capture_limit",
            observed_count,
            _MAX_METHOD_ARTIFACTS,
        )
    keys = tuple(artifacts.keys())
    if any(type(key) is not str or not key.strip() or len(key) > 256 for key in keys):
        return (
            [],
            "not_established",
            "method_artifact_key_inventory_not_bounded",
            observed_count,
            _MAX_METHOD_ARTIFACTS,
        )
    if len(set(keys)) != len(keys):
        return (
            [],
            "not_established",
            "method_artifact_key_inventory_not_unique",
            observed_count,
            _MAX_METHOD_ARTIFACTS,
        )

    captured: list[MethodExecutionArtifact] = []
    for artifact_key in sorted(keys):
        raw_payload = artifacts[artifact_key]
        if type(raw_payload) is not dict and not isinstance(raw_payload, BaseModel):
            captured.append(
                MethodExecutionArtifact(
                    artifact_key=artifact_key,
                    status="unavailable",
                    limitation="method_artifact_payload_not_bounded_json_object",
                )
            )
            continue
        normalized = _bounded_json_value(
            raw_payload,
            max_bytes=_MAX_METHOD_ARTIFACT_PAYLOAD_BYTES,
            max_elements=_MAX_METHOD_ARTIFACT_PAYLOAD_ELEMENTS,
            max_depth=8,
        )
        if normalized is _UNSUPPORTED_BOUNDED_JSON or type(normalized) is not dict:
            captured.append(
                MethodExecutionArtifact(
                    artifact_key=artifact_key,
                    status="unavailable",
                    limitation="method_artifact_payload_exceeds_capture_limit_or_codec_unsupported",
                )
            )
            continue
        try:
            payload = MethodArtifactOutputPayload(
                occurrence_id=occurrence.occurrence_id,
                invocation_id=occurrence.invocation_id,
                node_id=occurrence.node_id,
                artifact_key=artifact_key,
                payload=normalized,
            )
            encoded = json.dumps(
                payload.model_dump(mode="json"),
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            if len(encoded) > _MAX_METHOD_ARTIFACT_PAYLOAD_BYTES:
                raise ValueError("method_artifact_payload_exceeds_byte_limit")
            if capture.sidecar_refs_used >= _MAX_METHOD_CAPTURE_SIDECAR_REFS:
                raise ValueError("method_artifact_sidecar_ref_limit_exceeded")
            if len(encoded) > _MAX_METHOD_CAPTURE_SIDECAR_BYTES - capture.sidecar_bytes_used:
                raise ValueError("method_artifact_sidecar_byte_limit_exceeded")
            ref = store.put_json(
                payload,
                PutOptions(
                    kind=MethodArtifactOutputPayload.ARTIFACT_KIND,
                    media_type=MethodArtifactOutputPayload.ARTIFACT_MEDIA_TYPE,
                    schema=SchemaInfo(
                        name=MethodArtifactOutputPayload.ARTIFACT_SCHEMA_NAME,
                        version=MethodArtifactOutputPayload.ARTIFACT_SCHEMA_VERSION,
                    ),
                    inputs=[
                        artifact_input_ref(capture.program_graph_ref, role="program_graph"),
                        artifact_input_ref(capture.exec_plan_ref, role="exec_plan"),
                        artifact_input_ref(
                            capture.method_metric_binding_set_ref,
                            role="method_metric_binding_set",
                        ),
                    ],
                ),
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )
            selected_ref = _selected_typed_ref(store, ref, MethodArtifactOutputRef)
            validate_core_model_json_artifact(MethodArtifactOutputPayload, store, selected_ref)
        except Exception as exc:
            captured.append(
                MethodExecutionArtifact(
                    artifact_key=artifact_key,
                    status="unavailable",
                    limitation=f"method_artifact_capture_failed:{type(exc).__name__}"[:512],
                )
            )
            continue
        capture.sidecar_refs_used += 1
        capture.sidecar_bytes_used += len(encoded)
        captured.append(
            MethodExecutionArtifact(
                artifact_key=artifact_key,
                status="captured",
                artifact_ref=selected_ref,
            )
        )
    return captured, "captured", None, observed_count, _MAX_METHOD_ARTIFACTS


def _replace_capture_occurrence(
    capture: MethodExecutionCapture | None,
    occurrence_id: str,
    *,
    status: Literal["succeeded", "failed", "skipped"],
    output_slots: list[MethodExecutionOutputSlot] | None = None,
    returned_slots: list[MethodExecutionReturnedSlot] | None = None,
    returned_slot_inventory_status: Literal["captured", "not_established", "not_started"]
    | None = None,
    returned_slot_inventory_limitation: str | None = None,
    returned_slot_inventory_observed_count: int | None = None,
    returned_slot_inventory_limit: int | None = None,
    artifact_inventory_status: Literal["captured", "not_established", "not_started"] | None = None,
    artifact_inventory_limitation: str | None = None,
    artifact_inventory_observed_count: int | None = None,
    artifact_inventory_limit: int | None = None,
    dispatch: MethodExecutionDispatchRecord | None = None,
    artifacts: list[MethodExecutionArtifact] | None = None,
    restricted_call_witness: RestrictedMethodCallWitness | None = None,
) -> None:
    """Finish one predeclared occurrence without losing its actual identity."""
    if capture is None:
        return
    for occurrence in capture.occurrences:
        if occurrence.occurrence_id != occurrence_id:
            continue
        capture.replace_occurrence(
            occurrence.model_copy(
                update={
                    "status": status,
                    "output_slots": output_slots
                    if output_slots is not None
                    else occurrence.output_slots,
                    "returned_slots": returned_slots
                    if returned_slots is not None
                    else occurrence.returned_slots,
                    "returned_slot_inventory_status": (
                        returned_slot_inventory_status
                        if returned_slot_inventory_status is not None
                        else occurrence.returned_slot_inventory_status
                    ),
                    "returned_slot_inventory_limitation": (
                        returned_slot_inventory_limitation
                        if returned_slot_inventory_status is not None
                        else occurrence.returned_slot_inventory_limitation
                    ),
                    "returned_slot_inventory_observed_count": (
                        returned_slot_inventory_observed_count
                        if returned_slot_inventory_status is not None
                        else occurrence.returned_slot_inventory_observed_count
                    ),
                    "returned_slot_inventory_limit": (
                        returned_slot_inventory_limit
                        if returned_slot_inventory_status is not None
                        else occurrence.returned_slot_inventory_limit
                    ),
                    "artifact_inventory_status": (
                        artifact_inventory_status
                        if artifact_inventory_status is not None
                        else occurrence.artifact_inventory_status
                    ),
                    "artifact_inventory_limitation": (
                        artifact_inventory_limitation
                        if artifact_inventory_status is not None
                        else occurrence.artifact_inventory_limitation
                    ),
                    "artifact_inventory_observed_count": (
                        artifact_inventory_observed_count
                        if artifact_inventory_status is not None
                        else occurrence.artifact_inventory_observed_count
                    ),
                    "artifact_inventory_limit": (
                        artifact_inventory_limit
                        if artifact_inventory_status is not None
                        else occurrence.artifact_inventory_limit
                    ),
                    "dispatch": dispatch if dispatch is not None else occurrence.dispatch,
                    "artifacts": artifacts if artifacts is not None else occurrence.artifacts,
                    "restricted_call_witness": (
                        restricted_call_witness
                        if restricted_call_witness is not None
                        else occurrence.restricted_call_witness
                    ),
                }
            )
        )
        return
    raise ValueError("method_execution_occurrence_not_predeclared")


def _mark_unfinished_capture_occurrences_skipped(
    capture: MethodExecutionCapture | None,
    *,
    invocation_id: str,
    after_plan_index: int,
) -> None:
    """Close all unstarted plan positions when strict execution aborts."""
    if capture is None:
        return
    for occurrence in tuple(capture.occurrences):
        if (
            occurrence.invocation_id == invocation_id
            and occurrence.plan_index > after_plan_index
            and occurrence.status == "planned"
        ):
            capture.replace_occurrence(
                occurrence.model_copy(
                    update={
                        "status": "skipped",
                        "limitations": (
                            *occurrence.limitations,
                            "execution_aborted_before_occurrence",
                        ),
                    }
                )
            )


def persist_method_execution_capture(
    store: ArtifactStore,
    capture: MethodExecutionCapture,
) -> MethodExecutionBundleRef:
    """Persist a terminal bundle with the complete occurrence and output edge set."""
    if capture.method_execution_bundle_ref is not None:
        return capture.method_execution_bundle_ref
    if len(capture.occurrences) > _MAX_METHOD_EXECUTION_OCCURRENCES:
        raise ValueError("method_execution_occurrence_inventory_exceeds_capture_limit")
    if (
        capture.sidecar_refs_used > _MAX_METHOD_CAPTURE_SIDECAR_REFS
        or capture.sidecar_bytes_used > _MAX_METHOD_CAPTURE_SIDECAR_BYTES
        or len(capture.limitations) > _MAX_METHOD_CAPTURE_LIMITATIONS
    ):
        raise ValueError("method_execution_capture_resource_limit_exceeded")
    manifest_edge_count = 3 + int(capture.environment_manifest_ref is not None)
    for occurrence in capture.occurrences:
        manifest_edge_count += sum(
            output.output_ref is not None for output in occurrence.output_slots
        )
        manifest_edge_count += sum(
            artifact.artifact_ref is not None for artifact in occurrence.artifacts
        )
        manifest_edge_count += int(
            occurrence.dispatch is not None and occurrence.dispatch.input_state_ref is not None
        )
        manifest_edge_count += int(
            occurrence.dispatch is not None
            and occurrence.dispatch.input_state_source_ref is not None
        )
        manifest_edge_count += int(
            occurrence.dispatch is not None
            and occurrence.dispatch.method_metric_input_capture_ref is not None
        )
        if manifest_edge_count > _MAX_METHOD_CAPTURE_MANIFEST_EDGES:
            raise ValueError("method_execution_bundle_manifest_edge_limit_exceeded")
    occurrences = []
    inputs = [
        artifact_input_ref(capture.program_graph_ref, role="program_graph"),
        artifact_input_ref(capture.exec_plan_ref, role="exec_plan"),
        artifact_input_ref(
            capture.method_metric_binding_set_ref,
            role="method_metric_binding_set",
        ),
    ]
    if capture.environment_manifest_ref is not None:
        inputs.append(
            artifact_input_ref(capture.environment_manifest_ref, role="environment_manifest")
        )
    for occurrence in capture.occurrences:
        terminal = occurrence
        if occurrence.status == "planned":
            terminal = occurrence.model_copy(
                update={
                    "status": "skipped",
                    "limitations": (
                        *occurrence.limitations,
                        "execution_ended_before_occurrence",
                    ),
                }
            )
        occurrences.append(terminal)
        for output in terminal.output_slots:
            if output.output_ref is not None:
                inputs.append(
                    artifact_input_ref(
                        output.output_ref,
                        role=f"method_output:{terminal.occurrence_id}:{output.slot_id}",
                    )
                )
        for artifact in terminal.artifacts:
            if artifact.artifact_ref is not None:
                inputs.append(
                    artifact_input_ref(
                        artifact.artifact_ref,
                        role=f"method_artifact:{terminal.occurrence_id}:{artifact.artifact_key}",
                    )
                )
        if terminal.dispatch is not None and terminal.dispatch.input_state_ref is not None:
            inputs.append(
                artifact_input_ref(
                    terminal.dispatch.input_state_ref,
                    role=f"method_prestate:{terminal.occurrence_id}",
                )
            )
        if terminal.dispatch is not None and terminal.dispatch.input_state_source_ref is not None:
            inputs.append(
                artifact_input_ref(
                    terminal.dispatch.input_state_source_ref,
                    role=f"method_prestate_source:{terminal.occurrence_id}",
                )
            )
        if (
            terminal.dispatch is not None
            and terminal.dispatch.method_metric_input_capture_ref is not None
        ):
            inputs.append(
                artifact_input_ref(
                    terminal.dispatch.method_metric_input_capture_ref,
                    role=f"method_metric_input_capture:{terminal.occurrence_id}",
                )
            )
    bundle = MethodExecutionBundle(
        schema_version=(
            "1.2" if any(row.restricted_call_witness is not None for row in occurrences) else "1.1"
        ),
        program_graph_ref=capture.program_graph_ref,
        exec_plan_ref=capture.exec_plan_ref,
        method_metric_binding_set_ref=capture.method_metric_binding_set_ref,
        environment_manifest_ref=capture.environment_manifest_ref,
        occurrences=occurrences,
        limitations=tuple(dict.fromkeys(capture.limitations)),
    )
    if len(inputs) > _MAX_METHOD_CAPTURE_MANIFEST_EDGES:
        raise ValueError("method_execution_bundle_manifest_edge_limit_exceeded")
    bundle_bytes = json.dumps(
        bundle.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(bundle_bytes) > _MAX_METHOD_CAPTURE_BUNDLE_BYTES:
        raise ValueError("method_execution_bundle_byte_limit_exceeded")
    ref = store.put_json(
        bundle,
        PutOptions(
            kind=MethodExecutionBundle.ARTIFACT_KIND,
            media_type=MethodExecutionBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=MethodExecutionBundle.ARTIFACT_SCHEMA_NAME,
                version=bundle.schema_version,
            ),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    bundle_ref = _selected_typed_ref(
        store,
        ref,
        MethodExecutionBundleRef,
    )
    capture.method_execution_bundle_ref = bundle_ref
    return bundle_ref


def _abort_method_capture_limit(
    store: CoreJSONArtifactStore,
    capture: MethodExecutionCapture,
    *,
    reason: str,
) -> None:
    """Stop before graph execution when its complete capture exceeds declared limits."""
    if (
        reason not in capture.limitations
        and len(capture.limitations) < _MAX_METHOD_CAPTURE_LIMITATIONS
    ):
        capture.limitations.append(reason)
    card = FailureCard(
        node_id="method_metric_capture",
        method_fqn="polisyos.foundry.method_metric_capture",
        severity=FailureSeverity.FATAL,
        failure_kind=FailureKind.CONTRACT,
        error_type="MethodCaptureLimitError",
        error_message=reason,
        traceback_hash=hashlib.sha256(reason.encode("utf-8")).hexdigest(),
        timestamp=time.time(),
        retry_eligible=False,
        details={"capture_status": "not_established", "limitation": reason},
    )
    error = MethodExecutionAbortError(card)
    error.method_execution_bundle_ref = persist_method_execution_capture(store, capture)
    raise error


def _treasury_node_key(root_key: jax.Array, treasury: TreasuryPlan, node_id: str) -> jax.Array:
    """Version one folds low then high 32-bit words of the stream and node salts."""
    key = root_key
    for salt in (treasury.stream_salts["default"], treasury.node_salts[node_id]):
        key = jax.random.fold_in(key, salt & 0xFFFFFFFF)
        key = jax.random.fold_in(key, salt >> 32)
    return key


def execute_program_graph(
    store: CoreJSONArtifactStore,
    *,
    program_ref: ArtifactRef | ArtifactID | str,
    exec_plan_ref: ArtifactRef | ArtifactID | str,
    base_state: Any,
    mechanism_registry: MechanismTypeRegistry,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
    selector_field_registry: SelectorFieldRegistry | None = None,
    constraint_registry: ConstraintRegistry | None = None,
    step: int = 0,
    seed: int | None = None,
    base_ref: StateSnapshotRef | None = None,
    project_root: str | None = None,
    capture_env: bool = False,
    parameter_overrides: dict[str, dict[str, Any]] | None = None,
    parameter_override_bundle_ref: ArtifactRef | None = None,
    observed_range_bundle_ref: ArtifactRef | None = None,
    welfare_bound_mode: str = "ex_ante",
    persist_welfare_bound_reports: bool = True,
    execution_input_basis_ref: ArtifactRef | None = None,
    return_selected_profile: bool = False,
    method_execution_capture: MethodExecutionCapture | None = None,
    method_input_state_source_ref: ArtifactRef | None = None,
    finalize_method_execution_capture: bool = True,
    strictness: ExecutionStrictness = ExecutionStrictness.FAIL_CLOSED,
) -> ExecuteArtifacts:
    """Execute program graph."""
    start_time = time.perf_counter()
    program_graph = load_model(store, program_ref, ProgramGraph)
    exec_plan = load_model(store, exec_plan_ref, ExecPlan)
    treasury = _execution_treasury(store, program_ref, exec_plan_ref, program_graph, exec_plan)
    order = exec_plan.order or [node.node_id for node in program_graph.nodes]
    node_map = {node.node_id: node for node in program_graph.nodes}
    if len(node_map) != len(program_graph.nodes):
        raise ValueError("duplicate_program_graph_node_id")
    metric_bindings: dict[tuple[str, str], MethodMetricBinding] = {}
    selected_slot_ids_by_node: dict[str, tuple[str, ...]] = {}
    metric_input_capture_required_by_node: dict[str, bool] = {}
    capture = method_execution_capture
    binding_set_ref = _binding_ref_from_exec_plan_manifest(store, exec_plan_ref)
    if binding_set_ref is not None:
        plan_ref = _selected_typed_ref(store, exec_plan_ref, ExecPlanRef)
        graph_ref = _selected_typed_ref(store, program_ref, ProgramGraphRef)
        if capture is not None and capture.method_metric_bindings is not None:
            if (
                capture.program_graph_ref != graph_ref
                or capture.exec_plan_ref != plan_ref
                or capture.method_metric_binding_set_ref != binding_set_ref
            ):
                raise ValueError("method_execution_capture_source_tuple_mismatch")
            binding_rows = capture.method_metric_bindings
        else:
            bounded_store = _require_bounded_core_json_store(store)
            binding_set = _validate_method_metric_plan_binding(
                bounded_store,
                plan_ref=plan_ref,
                graph_ref=graph_ref,
                binding_set_ref=binding_set_ref,
            )
            binding_rows = tuple(binding_set.bindings)
        if capture is None:
            capture = MethodExecutionCapture(
                program_graph_ref=graph_ref,
                exec_plan_ref=plan_ref,
                method_metric_binding_set_ref=binding_set_ref,
                method_metric_bindings=binding_rows,
            )
        elif (
            capture.program_graph_ref != graph_ref
            or capture.exec_plan_ref != plan_ref
            or capture.method_metric_binding_set_ref != binding_set_ref
        ):
            raise ValueError("method_execution_capture_source_tuple_mismatch")
        if capture.method_metric_bindings is None:
            capture.method_metric_bindings = binding_rows
        if len(binding_rows) > METHOD_METRIC_BINDING_LIMIT:
            _abort_method_capture_limit(
                store,
                capture,
                reason="method_metric_binding_inventory_exceeds_capture_limit",
            )
        metric_bindings = {
            (binding.node_id, binding.output_slot_id): binding for binding in binding_rows
        }
        for binding in binding_rows:
            metric_input_capture_required_by_node[binding.node_id] = (
                metric_input_capture_required_by_node.get(binding.node_id, False)
                or (
                    binding.availability == "available"
                    and binding.law_id == METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID
                    and registered_method_metric_semantics_match(binding.law_id, binding.semantics)
                )
            )
        selected_slots: dict[str, set[str]] = {}
        for binding in binding_rows:
            selected_slots.setdefault(binding.node_id, set()).add(binding.output_slot_id)
        selected_slot_ids_by_node = {
            node_id: tuple(sorted(slot_ids)) for node_id, slot_ids in selected_slots.items()
        }
    elif capture is not None:
        raise ValueError("method_execution_capture_requires_compiled_binding_set")
    if capture is not None:
        if (
            len(order) > _MAX_METHOD_EXECUTION_OCCURRENCES
            or len(capture.occurrences) + len(order) > _MAX_METHOD_EXECUTION_OCCURRENCES
            or capture.invocation_count >= _MAX_METHOD_EXECUTION_OCCURRENCES
        ):
            _abort_method_capture_limit(
                store,
                capture,
                reason="method_execution_occurrence_inventory_exceeds_capture_limit",
            )
        if any(type(node_id) is not str or not node_id or len(node_id) > 256 for node_id in order):
            _abort_method_capture_limit(
                store,
                capture,
                reason="method_execution_node_identity_exceeds_capture_limit",
            )
    selected_profile = return_selected_profile or capture is not None
    current_invocation_id: str | None = None
    invocation_occurrence_ids: dict[int, str] = {}
    if capture is not None:
        method_classes, method_identities = _resolve_planned_method_identities(order, node_map)
        current_invocation_id = capture.begin_invocation()
        for plan_index, node_id in enumerate(order):
            node = node_map.get(node_id)
            occurrence_id = _method_occurrence_id(current_invocation_id, plan_index, node_id)
            invocation_occurrence_ids[plan_index] = occurrence_id
            capture.occurrences.append(
                _planned_method_occurrence(
                    occurrence_id=occurrence_id,
                    invocation_id=current_invocation_id,
                    plan_index=plan_index,
                    node=node,
                    node_id=node_id,
                    method_identity=method_identities.get(node_id),
                    method_class=method_classes.get(node_id),
                    selected_slot_ids=selected_slot_ids_by_node.get(node_id, ()),
                    metric_input_capture_required=(
                        metric_input_capture_required_by_node.get(node_id, False)
                    ),
                )
            )
    else:
        method_classes, method_identities = {}, {}
    effective_seed = (
        seed if seed is not None else ((exec_plan.random_seed or 0) if treasury is not None else 0)
    )
    env_manifest_ref: EnvironmentManifestRef | None = None
    env_fingerprint: str | None = None
    should_capture_environment = capture_env or (
        capture is not None and capture.environment_manifest_ref is None
    )
    if should_capture_environment:
        loaded_method_identities = [
            method_identities[node_id] for node_id in order if node_id in method_identities
        ]
        env_manifest = capture_environment(
            project_root=project_root,
            include_git=True,
            include_dependencies=True,
            custom_metadata={
                "seed": effective_seed,
                "seed_source": "explicit_override"
                if seed is not None
                else ("exec_plan" if treasury is not None else "legacy_default"),
                "randomization_profile": TREASURY_SALTS_PROFILE
                if treasury is not None
                else "legacy",
                "exec_plan_id": str(artifact_id(exec_plan_ref)),
                "loaded_method_identities": loaded_method_identities,
                "environment_fingerprint_excludes_loaded_method_identity": True,
                "environment_identity_scope": "loaded_method_class_source_only",
            },
        )
        env_manifest_ref = _persist_environment_manifest(
            store,
            env_manifest,
            exec_plan_ref,
            return_selected_profile=selected_profile,
        )
        env_fingerprint = env_manifest.fingerprint
        if capture is not None:
            capture.environment_manifest_ref = env_manifest_ref
            for limitation in (
                "environment_fingerprint_excludes_loaded_method_identity",
                "environment_manifest_captured_before_method_dispatch",
            ):
                if limitation not in capture.limitations:
                    capture.limitations.append(limitation)
        _log_environment_captured(env_manifest)

    if program_graph.lowered_ir_ref is None:
        raise ValueError("program_graph_missing_lowered_ir_ref")
    lowered_ir = load_model(store, program_graph.lowered_ir_ref, LoweredIR)
    observed_ranges = None
    if persist_welfare_bound_reports and welfare_bound_mode != "off":
        observed_ranges = (
            load_observed_range_bundle(store, observed_range_bundle_ref)
            if observed_range_bundle_ref is not None
            else None
        )

    incoming_dependencies = _incoming_dependencies(program_graph)
    mask_barrier_targets = _mask_barrier_targets(program_graph)

    n_agents = getattr(base_state.agents, "size", None)
    if n_agents is None:
        n_agents = int(base_state.agents.income.shape[0])
    n_firms = getattr(base_state.firms, "size", None)
    if n_firms is None:
        n_firms = int(base_state.firms.capital.shape[0])

    key = jax.random.PRNGKey(effective_seed)
    root_key = key
    tax_rate_value = _resolve_income_tax_rate(
        program_graph,
        store,
        step,
        parameter_overrides=parameter_overrides,
    )
    visible_state = base_state
    patch_records: dict[str, list[dict[str, Any]]] = {}
    ops: list[PatchOp] = []
    applied_nodes = 0
    skipped_nodes = 0
    failure_cards: list[FailureCard] = []
    failure_cards_dropped = 0
    provenance: dict[str, list[str]] = {}
    derived_artifacts: list[tuple[str, ArtifactRef]] = []
    touched_slots: set[str] = set()
    executed_mutating_nodes: set[str] = set()
    op_nodes = 0
    checked_constraints = 0
    masks: dict[str, tuple[jnp.ndarray, SlotScope]] = {}
    constraint_report = ConstraintReport(
        schema_version="1.0",
        ok=True,
        hard_fail=False,
        constraint_mode=lowered_ir.constraint_mode,
        total_constraints=0,
        violations=[],
        penalty_total=None,
        notes=[],
    )

    def _flush_pending_records() -> None:
        nonlocal patch_records, visible_state
        if not patch_records:
            return
        touched_slots.update(patch_records.keys())
        base_values = {
            slot_id: get_state_path(visible_state, slot_spec.state_path)
            for slot_id in patch_records
            for slot_spec in [slot_registry.slots.get(slot_id)]
            if slot_spec is not None and slot_spec.state_path
        }
        merged_ops = merge_patch_records(
            store,
            patch_records,
            base_values=base_values,
            slot_registry=slot_registry,
            merge_registry=merge_registry,
        )
        visible_state = apply_ops_to_state(
            store,
            base_state=visible_state,
            ops=merged_ops,
            slot_registry=slot_registry,
            merge_registry=merge_registry,
        )
        patch_records = {}

    def _persist_welfare_report(node: Any, report: Any) -> None:
        if report is None or not persist_welfare_bound_reports:
            return
        report_inputs = [
            artifact_input_ref(exec_plan_ref, role="exec_plan"),
        ]
        if base_ref is not None:
            report_inputs.append(input_ref_from_artifact_ref(base_ref, role="base_state_snapshot"))
        if node.params_ref is not None:
            report_inputs.append(
                input_ref_from_artifact_ref(node.params_ref, role="mechanism_params")
            )
        if parameter_override_bundle_ref is not None:
            report_inputs.append(
                input_ref_from_artifact_ref(
                    parameter_override_bundle_ref,
                    role="parameter_override_bundle",
                )
            )
        if observed_range_bundle_ref is not None:
            report_inputs.append(
                input_ref_from_artifact_ref(observed_range_bundle_ref, role="observed_range_bundle")
            )
        report_ref = persist_welfare_bound_report(store, report, inputs=report_inputs)
        derived_artifacts.append((f"welfare_bound_report:{node.node_id}", report_ref))

    for plan_index, node_id in enumerate(order):
        occurrence_id = invocation_occurrence_ids.get(plan_index)
        node = node_map.get(node_id)
        if node is None:
            card = _build_failure_card(
                ProgramNodeValidationError(
                    f"ExecPlan referenced unknown node '{node_id}'",
                    node_id=node_id,
                    code="unknown_exec_plan_node",
                ),
                node_id=node_id,
                slot_context=(),
            )
            failure_cards_dropped += _append_failure_card(failure_cards, card)
            if capture is not None and occurrence_id is not None:
                _replace_capture_occurrence(capture, occurrence_id, status="failed")
            if _should_abort(card, strictness):
                abort_error = MethodExecutionAbortError(card)
                _mark_unfinished_capture_occurrences_skipped(
                    capture,
                    invocation_id=current_invocation_id or "",
                    after_plan_index=plan_index,
                )
                if capture is not None:
                    abort_error.method_execution_bundle_ref = persist_method_execution_capture(
                        store,
                        capture,
                    )
                raise abort_error
            skipped_nodes += 1
            continue
        occurrence_status: Literal["succeeded", "failed", "skipped"] = "succeeded"
        occurrence_output_slots: list[MethodExecutionOutputSlot] | None = None
        occurrence_returned_slots: list[MethodExecutionReturnedSlot] | None = None
        occurrence_inventory_status: (
            Literal["captured", "not_established", "not_started"] | None
        ) = None
        occurrence_inventory_limitation: str | None = None
        occurrence_inventory_observed_count: int | None = None
        occurrence_inventory_limit: int | None = None
        occurrence_dispatch: MethodExecutionDispatchRecord | None = None
        occurrence_artifacts: list[MethodExecutionArtifact] | None = None
        occurrence_restricted_call_witness: RestrictedMethodCallWitness | None = None
        occurrence_artifact_inventory_status: (
            Literal["captured", "not_established", "not_started"] | None
        ) = None
        occurrence_artifact_inventory_limitation: str | None = None
        occurrence_artifact_inventory_observed_count: int | None = None
        occurrence_artifact_inventory_limit: int | None = None
        abort_error: MethodExecutionAbortError | None = None
        abort_cause: Exception | None = None
        try:
            barrier_target = mask_barrier_targets.get(node_id, node_id)
            node_key = (
                _treasury_node_key(root_key, treasury, node_id) if treasury is not None else key
            )
            if patch_records and _depends_on_executed_mutation(
                barrier_target,
                incoming_dependencies=incoming_dependencies,
                executed_mutating_nodes=executed_mutating_nodes,
            ):
                _flush_pending_records()
            if node.node_kind == "op":
                op_nodes += 1
                if node.op is None:
                    raise ProgramNodeValidationError(
                        f"Program op node '{node_id}' is missing op payload",
                        node_id=node_id,
                        op_kind=None,
                        code="missing_program_op",
                    )
                if node.op.op_kind == "make_mask":
                    selector_payload = node.op.params.get("selector") or {}
                    target = _parse_selector_payload(selector_payload, node=node)
                    mask, scope = evaluate_selector(
                        target,
                        visible_state,
                        selector_field_registry=selector_field_registry,
                    )
                    masks[node.node_id] = (mask, scope)
                    continue
                if node.op.op_kind == "apply_mechanism":
                    key, patch_map, payload, welfare_report = _execute_mechanism_like_node(
                        store,
                        node=node,
                        visible_state=visible_state,
                        selector_field_registry=selector_field_registry,
                        masks=masks,
                        step=step,
                        key=node_key,
                        n_agents=n_agents,
                        n_firms=n_firms,
                        mechanism_registry=mechanism_registry,
                        parameter_overrides=parameter_overrides,
                        observed_ranges=observed_ranges,
                        slot_registry=slot_registry,
                        merge_registry=merge_registry,
                        tax_rate_value=tax_rate_value,
                        welfare_bound_mode=welfare_bound_mode,
                    )
                    if patch_map is None:
                        skipped_nodes += 1
                        occurrence_status = "skipped"
                        continue
                    _append_patch_map_records(
                        patch_records,
                        node=node,
                        payload=payload,
                        patch_map=patch_map,
                    )
                    _persist_welfare_report(node, welfare_report)
                    applied_nodes += 1
                    executed_mutating_nodes.add(node_id)
                    continue
                if node.op.op_kind == "merge_state":
                    _flush_pending_records()
                    continue
                if node.op.op_kind == "check_constraints":
                    ids = node.op.params.get("constraint_ids") or []
                    if constraint_registry is not None:
                        from polisyos.foundry.validation.constraints_engine import (
                            check_constraints as evaluate_lowered_constraints,
                        )

                        constraint_ids = [item for item in ids if isinstance(item, str)]
                        lowered_constraints = [
                            item
                            for item in lowered_ir.constraints
                            if item.constraint_id in constraint_ids
                        ]
                        checked_constraints += len(lowered_constraints)
                        constraint_report = evaluate_lowered_constraints(
                            constraints=lowered_constraints,
                            slot_registry=slot_registry,
                            state=visible_state,
                        )
                    continue
                raise ProgramNodeValidationError(
                    f"Unsupported program op '{node.op.op_kind}'",
                    node_id=node_id,
                    op_kind=node.op.op_kind,
                    code="unsupported_program_op",
                )
            if node.node_kind == "mechanism":
                key, patch_map, payload, welfare_report = _execute_mechanism_like_node(
                    store,
                    node=node,
                    visible_state=visible_state,
                    selector_field_registry=selector_field_registry,
                    masks=masks,
                    step=step,
                    key=node_key,
                    n_agents=n_agents,
                    n_firms=n_firms,
                    mechanism_registry=mechanism_registry,
                    parameter_overrides=parameter_overrides,
                    observed_ranges=observed_ranges,
                    slot_registry=slot_registry,
                    merge_registry=merge_registry,
                    tax_rate_value=tax_rate_value,
                    welfare_bound_mode=welfare_bound_mode,
                )
                if patch_map is None:
                    skipped_nodes += 1
                    occurrence_status = "skipped"
                    continue
                _append_patch_map_records(
                    patch_records,
                    node=node,
                    payload=payload,
                    patch_map=patch_map,
                )
                _persist_welfare_report(node, welfare_report)
                applied_nodes += 1
                executed_mutating_nodes.add(node_id)
                continue
            if node.node_kind == "method":
                method_fqn = node.method_fqn
                if not method_fqn:
                    raise ProgramNodeValidationError(
                        f"Method node '{node_id}' is missing method_fqn",
                        node_id=node_id,
                        code="missing_method_fqn",
                    )
                from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
                from polisyos.foundry.methods.registry import MethodRegistry

                registry = MethodRegistry.get_instance()
                method_class = method_classes.get(node_id) or registry.get(
                    method_fqn,
                    version=node.method_version,
                )
                signature = method_class.signature
                dispatcher = MethodDispatcher.get_instance()
                key, step_key = jax.random.split(node_key)
                method_dispatch_state = _materialize_exact_method_input_state(
                    visible_state,
                    node=node,
                    method_class=method_class,
                    slot_registry=slot_registry,
                )
                planned_occurrence = (
                    next(
                        item
                        for item in capture.occurrences
                        if capture is not None and item.occurrence_id == occurrence_id
                    )
                    if capture is not None and occurrence_id is not None
                    else None
                )
                planned_dispatch = (
                    planned_occurrence.dispatch if planned_occurrence is not None else None
                )
                method_started_at = datetime.now(UTC)
                method_started_counter = time.perf_counter()
                method_seed = _seed_from_key(step_key)
                key_words = _method_key_words(step_key)
                signature_input_ids = (
                    tuple(sorted(slot.name for slot in signature.input_slots))
                    if len(signature.input_slots) <= 32
                    else ()
                )
                remaining_input_bytes = (
                    max(_MAX_METHOD_CAPTURE_INPUT_BYTES - capture.input_capture_bytes_used, 0)
                    if capture is not None
                    else 0
                )
                prestate_arrays = (
                    _bounded_method_input_arrays(
                        method_dispatch_state,
                        slot_ids=signature_input_ids,
                        require_vectors=False,
                        max_bytes=min(_MAX_METHOD_PRESTATE_HASH_BYTES, remaining_input_bytes),
                    )
                    if planned_dispatch is not None and signature_input_ids
                    else None
                )
                prestate_byte_count = (
                    0
                    if prestate_arrays is None
                    else sum(array.nbytes for array in prestate_arrays.values())
                )
                if capture is not None and prestate_arrays is not None:
                    capture.input_capture_bytes_used += prestate_byte_count
                prestate_identity = (
                    _method_dispatch_input_identity(prestate_arrays)
                    if prestate_arrays is not None
                    else None
                )
                selected_bindings = [
                    binding
                    for (bound_node_id, _slot_id), binding in metric_bindings.items()
                    if bound_node_id == node_id
                ]
                input_law_bindings = [
                    binding
                    for binding in selected_bindings
                    if binding.availability == "available"
                    and binding.law_id == METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID
                    and registered_method_metric_semantics_match(
                        binding.law_id,
                        binding.semantics,
                    )
                ]
                if len(input_law_bindings) > 1:
                    raise ValueError("method_metric_multiple_input_laws_for_node_dispatch")
                selected_binding = input_law_bindings[0] if input_law_bindings else None
                if capture is not None and occurrence_id is not None:
                    (
                        dispatch_input_slot_values,
                        dispatch_input_role_values,
                        metric_input_capture_ref,
                        metric_input_capture_status,
                        metric_input_capture_limitation,
                        dispatch_prestate_ref,
                    ) = _capture_method_metric_dispatch_inputs(
                        store,
                        capture=capture,
                        occurrence_id=occurrence_id,
                        invocation_id=current_invocation_id or "",
                        node_id=node_id,
                        step=step,
                        state=method_dispatch_state,
                        input_arrays=prestate_arrays,
                        method_class=method_class,
                        binding=selected_binding,
                        prestate_identity=prestate_identity,
                        source_state_ref=(method_input_state_source_ref or base_ref),
                    )
                else:
                    dispatch_input_slot_values = ()
                    dispatch_input_role_values = ()
                    metric_input_capture_ref = None
                    metric_input_capture_status = "not_required"
                    metric_input_capture_limitation = None
                    dispatch_prestate_ref = None
                try:
                    method_result = dispatcher.dispatch(
                        method_class=method_class,
                        signature=signature,
                        state=method_dispatch_state,
                        params=node.method_params,
                        seed=method_seed,
                    )
                except Exception as dispatch_error:
                    if planned_dispatch is not None:
                        occurrence_dispatch = _failed_method_dispatch_record(
                            planned_dispatch,
                            started_at=method_started_at,
                            started_counter=method_started_counter,
                            method_seed=method_seed,
                            key_words=key_words,
                            root_seed=effective_seed,
                            step=step,
                            prestate_identity=prestate_identity,
                            input_state_ref=dispatch_prestate_ref,
                            source_state_ref=(method_input_state_source_ref or base_ref),
                            method_class=method_class,
                            error=dispatch_error,
                            input_slot_values=dispatch_input_slot_values,
                            input_role_values=dispatch_input_role_values,
                            metric_input_capture_ref=metric_input_capture_ref,
                            metric_input_capture_status=metric_input_capture_status,
                            metric_input_capture_limitation=metric_input_capture_limitation,
                        )
                    raise
                if capture is not None and occurrence_id is not None:
                    occurrence = planned_occurrence
                    if occurrence is None or planned_dispatch is None:
                        raise ValueError("method_execution_occurrence_not_predeclared")
                    identity = method_identities.get(node_id, {})
                    occurrence_dispatch = _successful_method_dispatch_record(
                        planned_dispatch,
                        started_at=method_started_at,
                        started_counter=method_started_counter,
                        method_seed=method_seed,
                        key_words=key_words,
                        root_seed=effective_seed,
                        step=step,
                        prestate_identity=prestate_identity,
                        input_state_ref=dispatch_prestate_ref,
                        source_state_ref=(method_input_state_source_ref or base_ref),
                        method_class=method_class,
                        method_result=method_result,
                        input_slot_values=dispatch_input_slot_values,
                        input_role_values=dispatch_input_role_values,
                        metric_input_capture_ref=metric_input_capture_ref,
                        metric_input_capture_status=metric_input_capture_status,
                        metric_input_capture_limitation=metric_input_capture_limitation,
                    )
                    if signature.fqn == "policy.evaluation.ex_ante_simulation@1.0.0":
                        from polisyos.foundry.methods.catalog.policy.restricted_executable_profile import (
                            bind_occurrence_call_witness,
                        )

                        occurrence_restricted_call_witness = bind_occurrence_call_witness(
                            evidence=getattr(method_result, "restricted_invocation", None),
                            occurrence=occurrence,
                            input_capture_ref=metric_input_capture_ref,
                            input_capture_status=metric_input_capture_status,
                        )
                    (
                        occurrence_output_slots,
                        occurrence_returned_slots,
                        occurrence_inventory_status,
                        occurrence_inventory_limitation,
                        occurrence_inventory_observed_count,
                        occurrence_inventory_limit,
                    ) = _capture_method_outputs(
                        store,
                        capture=capture,
                        occurrence=occurrence,
                        method_class=method_class,
                        method_result=method_result,
                        method_identity=identity,
                        bindings=metric_bindings,
                    )
                    (
                        occurrence_artifacts,
                        occurrence_artifact_inventory_status,
                        occurrence_artifact_inventory_limitation,
                        occurrence_artifact_inventory_observed_count,
                        occurrence_artifact_inventory_limit,
                    ) = _capture_method_artifacts(
                        store,
                        capture=capture,
                        occurrence=occurrence,
                        method_result=method_result,
                    )
                _append_method_patch_records(
                    patch_records,
                    provenance,
                    node=node,
                    output_payload=method_result.output,
                )
                applied_nodes += 1
                executed_mutating_nodes.add(node_id)
                continue
            raise ProgramNodeValidationError(
                f"Unsupported node kind '{node.node_kind}'",
                node_id=node_id,
                code="unsupported_node_kind",
            )
        except _CLASSIFIED_EXECUTOR_FAILURES as exc:
            card = _build_failure_card(
                exc,
                node=node,
                slot_context=tuple(node.inputs) + tuple(node.outputs),
            )
            failure_cards_dropped += _append_failure_card(failure_cards, card)
            logger.warning(
                "Program node '%s' failed [%s/%s]: %s",
                node_id,
                card.severity.value,
                card.failure_kind.value,
                card.error_message,
            )
            if _should_abort(card, strictness):
                occurrence_status = "failed"
                abort_error = MethodExecutionAbortError(card)
                abort_cause = exc
            else:
                occurrence_status = "failed"
                skipped_nodes += 1
        finally:
            if capture is not None and occurrence_id is not None:
                _replace_capture_occurrence(
                    capture,
                    occurrence_id,
                    status=occurrence_status,
                    output_slots=occurrence_output_slots,
                    returned_slots=occurrence_returned_slots,
                    returned_slot_inventory_status=occurrence_inventory_status,
                    returned_slot_inventory_limitation=occurrence_inventory_limitation,
                    returned_slot_inventory_observed_count=occurrence_inventory_observed_count,
                    returned_slot_inventory_limit=occurrence_inventory_limit,
                    artifact_inventory_status=occurrence_artifact_inventory_status,
                    artifact_inventory_limitation=occurrence_artifact_inventory_limitation,
                    artifact_inventory_observed_count=occurrence_artifact_inventory_observed_count,
                    artifact_inventory_limit=occurrence_artifact_inventory_limit,
                    dispatch=occurrence_dispatch,
                    artifacts=occurrence_artifacts,
                    restricted_call_witness=occurrence_restricted_call_witness,
                )
        if abort_error is not None:
            _mark_unfinished_capture_occurrences_skipped(
                capture,
                invocation_id=current_invocation_id or "",
                after_plan_index=plan_index,
            )
            if capture is not None:
                abort_error.method_execution_bundle_ref = persist_method_execution_capture(
                    store,
                    capture,
                )
            raise abort_error from abort_cause

    if patch_records:
        _flush_pending_records()

    ops = _build_state_delta_ops(
        store,
        base_state=base_state,
        final_state=visible_state,
        touched_slots=touched_slots,
        slot_registry=slot_registry,
        merge_registry=merge_registry,
    )

    latency_ms = int((time.perf_counter() - start_time) * 1000)

    inputs = [
        artifact_input_ref(program_ref, role="program_graph"),
        artifact_input_ref(exec_plan_ref, role="exec_plan"),
    ]
    if program_graph.lowered_ir_ref is not None:
        inputs.append(input_ref_from_artifact_ref(program_graph.lowered_ir_ref, role="lowered_ir"))
    if parameter_override_bundle_ref is not None:
        inputs.append(
            input_ref_from_artifact_ref(
                parameter_override_bundle_ref,
                role="parameter_override_bundle",
            )
        )
    if execution_input_basis_ref is not None:
        inputs.append(
            input_ref_from_artifact_ref(execution_input_basis_ref, role="execution_input_basis")
        )
    for op in ops:
        if op.value_ref is not None:
            inputs.append(input_ref_from_artifact_ref(op.value_ref, role="patch_value"))

    state_delta = StateDelta(base_ref=base_ref, ops=ops)
    state_delta_ref = store.put_json(
        state_delta,
        PutOptions(
            kind=StateDelta.ARTIFACT_KIND,
            media_type=StateDelta.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=StateDelta.ARTIFACT_SCHEMA_NAME,
                version=StateDelta.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=inputs,
        ),
        return_selected_profile=selected_profile,
    )

    metrics = Metrics(
        values={
            "applied_nodes": int(applied_nodes),
            "skipped_nodes": int(skipped_nodes),
            "op_nodes": int(op_nodes),
            "checked_constraints": int(checked_constraints),
            "patch_ops": len(ops),
            "step": int(step),
            "step_latency_ms": latency_ms,
            "constraint_hard_fail": int(constraint_report.hard_fail),
            "failure_cards_recorded": len(failure_cards),
            "failure_cards_dropped": int(failure_cards_dropped),
        }
    )
    metrics_ref = store.put_json(
        metrics,
        PutOptions(
            kind=Metrics.ARTIFACT_KIND,
            media_type=Metrics.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=Metrics.ARTIFACT_SCHEMA_NAME,
                version=Metrics.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=selected_profile,
    )

    constraint_report_ref = None
    if constraint_registry is not None or lowered_ir.constraints:
        cref = store.put_json(
            constraint_report,
            PutOptions(
                kind="foundry.constraint_report",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.core.ConstraintReport", version="1.0"),
                inputs=inputs,
            ),
            return_selected_profile=selected_profile,
        )
        constraint_report_ref = ConstraintReportRef.model_validate(cref.model_dump(mode="python"))

    frozen_provenance = {k: tuple(v) for k, v in provenance.items()}
    degradation_cards = tuple(
        card for card in failure_cards if card.severity != FailureSeverity.FATAL
    )
    method_execution_bundle_ref = (
        persist_method_execution_capture(store, capture)
        if capture is not None and finalize_method_execution_capture
        else None
    )
    return ExecuteArtifacts(
        state_delta_ref=state_delta_ref,
        metrics_ref=metrics_ref,
        derived_artifacts=tuple(derived_artifacts),
        constraint_report_ref=constraint_report_ref,
        constraint_hard_fail=constraint_report.hard_fail,
        environment_ref=env_manifest_ref,
        method_metric_binding_set_ref=(
            capture.method_metric_binding_set_ref if capture is not None else None
        ),
        method_execution_bundle_ref=method_execution_bundle_ref,
        environment_fingerprint=env_fingerprint,
        failure_cards=tuple(failure_cards),
        degradation_cards=degradation_cards,
        is_degraded=len(failure_cards) > 0,
        provenance=frozen_provenance,
    )


# ---------------------------------------------------------------------------
# Failure classification
# ---------------------------------------------------------------------------


def _classify_failure(exc: Exception) -> FailureSeverity:
    """Classify an exception into a failure severity level."""
    if isinstance(
        exc,
        (
            TypeError,
            ValueError,
            ShapeMismatchError,
            ContractViolationError,
            FoundryExecutionError,
            StatePathTraversalError,
            SelectorEvaluationError,
            ObservationBindingError,
        ),
    ):
        return FailureSeverity.FATAL
    if isinstance(exc, (ModuleNotFoundError, ImportError, TimeoutError)):
        return FailureSeverity.RECOVERABLE
    if isinstance(exc, FloatingPointError):
        return FailureSeverity.DEGRADED
    return FailureSeverity.FATAL


def _classify_failure_kind(exc: Exception) -> FailureKind:
    if isinstance(exc, (ContractViolationError, ShapeMismatchError)):
        return FailureKind.CONTRACT
    if isinstance(exc, StatePathTraversalError):
        return FailureKind.PATH
    if isinstance(exc, SelectorEvaluationError):
        return FailureKind.SELECTOR
    if isinstance(exc, ObservationBindingError):
        return FailureKind.ROUTING
    if type(exc).__name__ == "LifecycleTransitionError":
        return FailureKind.LIFECYCLE
    if isinstance(exc, BackendAdaptationError):
        return FailureKind.BACKEND
    if isinstance(exc, (FloatingPointError, RuntimeWarning)):
        return FailureKind.NUMERICAL
    if isinstance(exc, (ModuleNotFoundError, ImportError, TimeoutError)):
        return FailureKind.DEPENDENCY
    if isinstance(exc, (ProgramNodeValidationError, TypeError, ValueError, FoundryExecutionError)):
        return FailureKind.VALIDATION
    return FailureKind.INTERNAL


def _node_target_fqn(node: Any | None, *, node_id: str | None = None) -> str:
    if node is None:
        return f"executor.graph.{node_id or 'unknown'}@runtime"
    if getattr(node, "method_fqn", None):
        return str(node.method_fqn)
    if getattr(node, "mechanism_type", None):
        return f"mechanism.{node.mechanism_type}@runtime"
    if getattr(node, "op", None) is not None:
        return f"executor.op.{node.op.op_kind}@runtime"
    return f"executor.node.{getattr(node, 'node_id', node_id or 'unknown')}@runtime"


def _build_failure_card(
    exc: Exception,
    *,
    node: Any | None = None,
    node_id: str | None = None,
    slot_context: tuple[str, ...] = (),
) -> FailureCard:
    details = dict(getattr(exc, "details", {}) or {})
    resolved_node_id = (
        getattr(exc, "node_id", None) or getattr(node, "node_id", None) or node_id or "unknown"
    )
    resolved_method_fqn = getattr(exc, "method_fqn", None) or _node_target_fqn(
        node, node_id=resolved_node_id
    )
    resolved_mechanism_type = getattr(exc, "mechanism_type", None) or getattr(
        node, "mechanism_type", None
    )
    resolved_op_kind = getattr(exc, "op_kind", None) or (
        getattr(node.op, "op_kind", None)
        if node is not None and getattr(node, "op", None)
        else None
    )
    resolved_slot_context = tuple(slot_context)
    slot_id = getattr(exc, "slot_id", None)
    if slot_id is not None and slot_id not in resolved_slot_context:
        resolved_slot_context = resolved_slot_context + (str(slot_id),)
    if resolved_slot_context:
        details.setdefault("slot_context", list(resolved_slot_context))
    return FailureCard(
        node_id=str(resolved_node_id),
        method_fqn=str(resolved_method_fqn),
        severity=_classify_failure(exc),
        failure_kind=_classify_failure_kind(exc),
        error_type=type(exc).__name__,
        error_message=str(exc),
        traceback_hash=_hash_traceback(exc),
        timestamp=time.time(),
        retry_eligible=_classify_failure(exc) == FailureSeverity.RECOVERABLE,
        suggested_fallback="retry"
        if _classify_failure(exc) == FailureSeverity.RECOVERABLE
        else None,
        mechanism_type=resolved_mechanism_type,
        op_kind=resolved_op_kind,
        slot_context=resolved_slot_context,
        details=details,
    )


def _should_abort(card: FailureCard, strictness: ExecutionStrictness) -> bool:
    if strictness == ExecutionStrictness.FAIL_CLOSED:
        return True
    if strictness == ExecutionStrictness.DEGRADED:
        return card.severity == FailureSeverity.FATAL
    return False


def _parse_selector_payload(selector_payload: Any, *, node: Any) -> SelectorExpr:
    try:
        return _SELECTOR_ADAPTER.validate_python(selector_payload)
    except (TypeError, ValueError, ValidationError) as exc:
        raise SelectorEvaluationError(
            None,
            f"invalid selector payload for node '{node.node_id}': {exc}",
            value=selector_payload,
        ) from exc


def _append_patch_map_records(
    patch_records: dict[str, list[dict[str, Any]]],
    *,
    node: Any,
    payload: dict[str, Any],
    patch_map: Any,
) -> None:
    if not isinstance(patch_map, dict):
        raise ContractViolationError(
            _node_target_fqn(node),
            "postcondition",
            "patch map must be a dict[str, list[dict]]",
        )
    expected_slots = {str(slot_id) for slot_id in getattr(node, "outputs", [])}
    unexpected_slots = set(map(str, patch_map.keys())) - expected_slots if expected_slots else set()
    if unexpected_slots:
        raise ContractViolationError(
            _node_target_fqn(node),
            "postcondition",
            f"unexpected patch outputs: {sorted(unexpected_slots)}",
        )
    for slot_id, patches in patch_map.items():
        patch_list = patches if isinstance(patches, list) else [patches]
        for patch in patch_list:
            if not isinstance(patch, dict):
                raise ContractViolationError(
                    _node_target_fqn(node),
                    "postcondition",
                    f"patch for slot '{slot_id}' must be a dict",
                )
            record = {
                "node_id": node.node_id,
                "priority": payload.get("priority"),
            }
            record.update(patch)
            patch_records.setdefault(str(slot_id), []).append(record)


def _append_method_patch_records(
    patch_records: dict[str, list[dict[str, Any]]],
    provenance: dict[str, list[str]],
    *,
    node: Any,
    output_payload: Any,
) -> None:
    method_fqn = str(node.method_fqn)
    if not isinstance(output_payload, dict):
        raise ContractViolationError(method_fqn, "postcondition", "method output must be a dict")
    patch_payload = output_payload.get("patch_records")
    if patch_payload is None:
        if getattr(node, "outputs", None):
            raise ContractViolationError(
                method_fqn,
                "postcondition",
                "declared outputs require patch_records in method output",
            )
        return
    if not isinstance(patch_payload, dict):
        raise ContractViolationError(
            method_fqn,
            "postcondition",
            "patch_records must be a dict[str, list[dict]]",
        )
    expected_slots = {str(slot_id) for slot_id in getattr(node, "outputs", [])}
    unexpected_slots = (
        set(map(str, patch_payload.keys())) - expected_slots if expected_slots else set()
    )
    if unexpected_slots:
        raise ContractViolationError(
            method_fqn,
            "postcondition",
            f"unexpected patch outputs: {sorted(unexpected_slots)}",
        )
    for slot_id, patches in patch_payload.items():
        if not isinstance(patches, list):
            raise ContractViolationError(
                method_fqn,
                "postcondition",
                f"patch_records['{slot_id}'] must be a list of patch dicts",
            )
        for patch in patches:
            if not isinstance(patch, dict):
                raise ContractViolationError(
                    method_fqn,
                    "postcondition",
                    f"patch for slot '{slot_id}' must be a dict",
                )
            materialized_patch = dict(patch)
            materialized_patch.setdefault("node_id", node.node_id)
            patch_records.setdefault(str(slot_id), []).append(materialized_patch)
            provenance.setdefault(str(slot_id), []).append(method_fqn)


def _hash_traceback(exc: Exception) -> str:
    """Produce a short hash of the traceback for deduplication."""
    import hashlib
    import traceback as tb_mod

    tb_str = "".join(tb_mod.format_exception(type(exc), exc, exc.__traceback__))
    return hashlib.sha256(tb_str.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _incoming_dependencies(program_graph: ProgramGraph) -> dict[str, tuple[str, ...]]:
    incoming: dict[str, list[str]] = {}
    for edge in program_graph.edges:
        incoming.setdefault(edge.dst, []).append(edge.src)
    return {node_id: tuple(sorted(srcs)) for node_id, srcs in incoming.items()}


def _mask_barrier_targets(program_graph: ProgramGraph) -> dict[str, str]:
    targets: dict[str, str] = {}
    for node in program_graph.nodes:
        if node.op is None or node.op.op_kind not in {
            "apply_mechanism",
            "apply_method",
        }:
            continue
        mask_id = node.op.params.get("mask_id")
        if isinstance(mask_id, str):
            targets[mask_id] = node.node_id
    return targets


def _depends_on_executed_mutation(
    node_id: str,
    *,
    incoming_dependencies: dict[str, tuple[str, ...]],
    executed_mutating_nodes: set[str],
) -> bool:
    return any(
        dependency in executed_mutating_nodes
        for dependency in incoming_dependencies.get(node_id, ())
    )


def _append_failure_card(failure_cards: list[FailureCard], card: FailureCard) -> int:
    if len(failure_cards) < _MAX_FAILURE_CARDS:
        failure_cards.append(card)
        return 0
    return 1


def _seed_from_key(key: jax.Array) -> int:
    key_words = np.asarray(jax.random.key_data(key), dtype=np.uint32).reshape(-1)
    acc = 0
    for word in key_words:
        acc = (acc * 1664525 + int(word) + 1013904223) % (2**31 - 1)
    return int(acc or 1)


def _execute_mechanism_like_node(
    store: CoreJSONArtifactStore,
    *,
    node: Any,
    visible_state: Any,
    selector_field_registry: SelectorFieldRegistry | None,
    masks: dict[str, tuple[jnp.ndarray, SlotScope]],
    step: int,
    key: jax.Array,
    n_agents: int,
    n_firms: int,
    mechanism_registry: MechanismTypeRegistry,
    parameter_overrides: dict[str, dict[str, Any]] | None,
    observed_ranges: Any | None,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
    tax_rate_value: jnp.ndarray | None,
    welfare_bound_mode: str,
) -> tuple[jax.Array, dict[str, Any] | None, dict[str, Any], Any | None]:
    if node.params_ref is None:
        raise ProgramNodeValidationError(
            f"Node '{node.node_id}' is missing params_ref",
            node_id=node.node_id,
            mechanism_type=node.mechanism_type,
            op_kind=getattr(node.op, "op_kind", None),
            code="missing_params_ref",
        )
    payload = _load_node_payload(
        store,
        node=node,
        parameter_overrides=parameter_overrides,
    )
    schedule = ScheduleSpec.model_validate(payload.get("schedule", {}))
    start, end = schedule_range(schedule)
    if step < start or step > end:
        return key, None, payload, None

    mechanism_type = node.mechanism_type or payload.get("mechanism_id")
    if not isinstance(mechanism_type, str) or not mechanism_type.strip():
        raise ProgramNodeValidationError(
            f"Node '{node.node_id}' is missing mechanism_type",
            node_id=node.node_id,
            code="missing_mechanism_type",
        )
    mechanism_spec = mechanism_registry.mechanisms.get(mechanism_type)

    mask_info: tuple[jnp.ndarray, SlotScope] | None = None
    if node.node_kind == "op" and node.op is not None and node.op.op_kind == "apply_mechanism":
        mask_id = node.op.params.get("mask_id")
        if isinstance(mask_id, str):
            mask_info = masks.get(mask_id)
            if mask_info is None:
                raise ProgramNodeValidationError(
                    f"Node '{node.node_id}' referenced unresolved mask '{mask_id}'",
                    node_id=node.node_id,
                    mechanism_type=mechanism_type,
                    op_kind=node.op.op_kind,
                    code="missing_mask_dependency",
                )
        if mask_info is None:
            selector_payload = payload.get("selector") or payload.get("target")
            if selector_payload is None:
                raise ProgramNodeValidationError(
                    f"Node '{node.node_id}' is missing selector payload",
                    node_id=node.node_id,
                    mechanism_type=mechanism_type,
                    op_kind=node.op.op_kind,
                    code="missing_selector_payload",
                )
            target = _parse_selector_payload(selector_payload, node=node)
            mask_info = evaluate_selector(
                target, visible_state, selector_field_registry=selector_field_registry
            )

    params = payload.get("params", {})
    mechanism = create_mechanism_from_spec(
        mechanism_type,
        params,
        n_agents=n_agents,
        n_firms=n_firms,
        mechanism_spec=mechanism_spec,
        selected_fidelity=payload.get("selected_fidelity"),
    )
    if (
        tax_rate_value is not None
        and isinstance(mechanism, AdaptiveAgentMechanism)
        and (
            "global.tax_rate" in mechanism.observation_space
            or "policy.tax_rate" in mechanism.observation_space
        )
    ):
        mechanism = mechanism.with_runtime_overrides(tax_rate_value=tax_rate_value)

    key, step_key = jax.random.split(key)
    target_mask = None
    if mask_info is not None:
        mask, mask_scope = mask_info
        if mask_scope in {SlotScope.PER_AGENT, SlotScope.PER_FIRM}:
            target_mask = mask
    patch_map, key = mechanism.emit_patches(visible_state, step_key, target_mask=target_mask)
    if patch_map is None:
        raise ContractViolationError(
            _node_target_fqn(node),
            "postcondition",
            f"mechanism '{mechanism_type}' did not emit patches",
        )
    welfare_report = None
    state_after_error: str | None = None
    if welfare_bound_mode != "off":
        state_after = None
        if welfare_bound_mode in {"ex_post", "both"}:
            try:
                state_after = apply_patch_map(
                    visible_state,
                    patch_map,
                    slot_registry=slot_registry,
                    merge_registry=merge_registry,
                    default_node_id=node.node_id,
                    priority=payload.get("priority"),
                )
            except Exception as exc:  # pragma: no cover - defensive envelope
                state_after_error = f"{type(exc).__name__}: {exc}"
        welfare_report = safe_compute_mechanism_welfare_bound_report(
            mechanism_type,
            mechanism,
            visible_state,
            observed_ranges,
            state_after=state_after,
            node_id=node.node_id,
            target_mask=target_mask,
            mode=welfare_bound_mode,
        )
    if welfare_report is not None and state_after_error is not None:
        welfare_report = welfare_report.model_copy(
            update={
                "status": "warning",
                "notes": [
                    *welfare_report.notes,
                    f"state_after_reconstruction_failed:{state_after_error}",
                ],
            }
        )
    return key, patch_map, payload, welfare_report


def _build_state_delta_ops(
    store: CoreJSONArtifactStore,
    *,
    base_state: Any,
    final_state: Any,
    touched_slots: set[str],
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
) -> list[PatchOp]:
    ops: list[PatchOp] = []
    for slot_id in sorted(touched_slots):
        slot_spec = slot_registry.slots.get(slot_id)
        if slot_spec is None or not slot_spec.state_path:
            raise ValueError(f"Slot '{slot_id}' missing state_path for execution")
        rule = merge_registry.rules.get(slot_spec.merge_rule.rule_id)
        if rule is None:
            raise ValueError(f"Unknown merge rule '{slot_spec.merge_rule.rule_id}' for '{slot_id}'")
        base_value = get_state_path(base_state, slot_spec.state_path)
        final_value = get_state_path(final_state, slot_spec.state_path)
        if rule.kind == MergeRuleKind.SUM:
            payload = jnp.asarray(final_value) - jnp.asarray(base_value)
            op_kind = "add"
        else:
            payload = jnp.asarray(final_value)
            op_kind = "set"
        value_ref = put_tensor(store, payload)
        ops.append(
            PatchOp(
                slot_id=slot_id,
                op=op_kind,
                value_ref=value_ref,
                notes=[f"merge:{rule.kind.value}", "source:visible_state_diff"],
            )
        )
    return ops


def _persist_environment_manifest(
    store: CoreJSONArtifactStore,
    manifest: EnvironmentManifest,
    exec_plan_ref: ArtifactRef | ArtifactID | str,
    *,
    return_selected_profile: bool = False,
) -> EnvironmentManifestRef:
    artifact_ref = store.put_json(
        manifest,
        PutOptions(
            kind="foundry.environment_manifest",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.core.artifacts.environment.EnvironmentManifest",
                version="1.0",
            ),
            inputs=[artifact_input_ref(exec_plan_ref, role="exec_plan")],
        ),
        return_selected_profile=return_selected_profile,
    )
    return EnvironmentManifestRef.model_validate(artifact_ref.model_dump(mode="python"))


def _log_environment_captured(manifest: EnvironmentManifest) -> None:
    from polisyos.common.logger import get_logger

    log = get_logger(__name__)
    log.info(
        "Environment captured",
        fingerprint=manifest.fingerprint,
        cpu_arch=manifest.cpu.architecture,
        jax_version=manifest.jax.jax_version,
        cuda_version=manifest.gpu.cuda_version,
        python_version=manifest.python.version,
        git_commit=manifest.git.commit_short if manifest.git else None,
    )


def _resolve_income_tax_rate(
    program_graph: ProgramGraph,
    store: CoreJSONArtifactStore,
    step: int,
    parameter_overrides: dict[str, dict[str, Any]] | None = None,
) -> jnp.ndarray | None:
    for node in program_graph.nodes:
        if node.mechanism_type != "income_tax" or node.params_ref is None:
            continue
        payload = _load_node_payload(
            store,
            node=node,
            parameter_overrides=parameter_overrides,
        )
        schedule = ScheduleSpec.model_validate(payload.get("schedule", {}))
        start, end = schedule_range(schedule)
        if step < start or step > end:
            continue
        params = payload.get("params", {})
        numeric = coerce_number(params.get("rate"))
        if numeric is None:
            continue
        return jnp.array(float(numeric), dtype=jnp.float32)
    return None


def _load_node_payload(
    store: CoreJSONArtifactStore,
    *,
    node: Any,
    parameter_overrides: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    payload = load_payload(store, node.params_ref)
    if not isinstance(payload, dict):
        raise ProgramNodeValidationError(
            f"Node '{node.node_id}' params payload must be a dict",
            node_id=node.node_id,
            mechanism_type=getattr(node, "mechanism_type", None),
            op_kind=getattr(node.op, "op_kind", None) if getattr(node, "op", None) else None,
            code="invalid_node_payload",
        )
    if not parameter_overrides:
        return payload
    node_overrides = parameter_overrides.get(str(node.node_id))
    if not isinstance(node_overrides, dict) or not node_overrides:
        return payload
    merged_payload = dict(payload)
    params = payload.get("params")
    merged_payload["params"] = {
        **(params if isinstance(params, dict) else {}),
        **node_overrides,
    }
    return merged_payload
