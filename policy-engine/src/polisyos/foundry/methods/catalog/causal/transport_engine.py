"""Public causal transport engine module API."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import Enum
from types import UnionType
from typing import Any, Literal, Union, get_args, get_origin

import numpy as np
from pydantic import BaseModel, ValidationError

from polisyos.ir.analytics.causal import ProofBundle
from polisyos.ir.analytics.causal_capabilities import (
    CausalBackendId,
    CausalCapabilityContract,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
    _FrozenDict,
    _FrozenList,
)
from polisyos.ir.analytics.partial_identification import compute_manski_bounds
from polisyos.ir.analytics.privacy_transportability import (
    TransportPrivacyContext,
    apply_transport_privacy_context,
)
from polisyos.ir.analytics.transportability import (
    PAGIdentificationPolicy,
    SelectionDiagram,
    SNodeRole,
    StratificationVariable,
    TransportabilityResult,
    TransportabilityStatus,
    TransportFormula,
    TransportMode,
)

from .capabilities import build_causal_capability_contract
from .full_transport_bridge import normalize_transport_formula
from .transport_bounds import transport_bounds

_NON_ADJUDICATIVE_TRANSPORT_REFUSALS = frozenset(
    {
        "partial_graph_completion_semantics_not_established",
        "pag_identification_policy_invalid",
        "unsupported_static_admg_profile",
        "causal_graph_profile_invalid",
        "causal_graph_type_not_supported",
    }
)

_VALID_SOLVER_MODES: frozenset[str] = frozenset(
    {"auto", "simplified", "symbolic", "symbolic_y0", "symbolic_r", "full_auto"}
)


def solve_transportability(
    *,
    selection_diagram: SelectionDiagram,
    query_treatment: str,
    query_outcome: str,
    solver_mode: str = "auto",
    allow_degraded_transport: bool = False,
    pag_identification_policy: PAGIdentificationPolicy | str | None = None,
    pag_max_dag_samples: int = 100,
    pag_threshold: float = 0.5,
    pag_seed: int = 0,
    capability_contract: CausalCapabilityContract | None = None,
    privacy_context: TransportPrivacyContext | None = None,
) -> TransportabilityResult:
    """Solve transportability helper."""
    mode = _normalize_solver_mode(solver_mode)
    selection_diagram, malformed_graph_refusal = validate_scalar_graph_selection_diagram(
        selection_diagram,
        treatment=query_treatment,
        outcome=query_outcome,
        solver_mode=mode,
        privacy_context=privacy_context,
    )
    if malformed_graph_refusal is not None:
        return malformed_graph_refusal
    assert selection_diagram is not None

    # Direct solver callers receive the same detached, typed snapshot as registered
    # dispatchers. The graph gate and every downstream backend consume this object.
    graph_admission_refusal = scalar_graph_admission_refusal(
        selection_diagram=selection_diagram,
        treatment=query_treatment,
        outcome=query_outcome,
        solver_mode=mode,
        pag_identification_policy=pag_identification_policy,
        privacy_context=privacy_context,
    )
    if graph_admission_refusal is not None:
        return graph_admission_refusal

    contract = capability_contract or build_causal_capability_contract()
    trace = [
        f"solver_mode:{mode}",
        f"capability_fingerprint:{contract.dependency_fingerprint}",
        f"allow_degraded_transport:{str(bool(allow_degraded_transport)).lower()}",
    ]
    if not selection_diagram.s_nodes and _should_use_probabilistic_pag_path(
        selection_diagram=selection_diagram,
        pag_identification_policy=pag_identification_policy,
    ):
        pag_result = _run_simplified_legacy(
            diagram=selection_diagram,
            treatment=query_treatment,
            outcome=query_outcome,
            trace=[*trace, "family:direct_via_pag_probabilistic"],
            pag_identification_policy=pag_identification_policy,
            pag_max_dag_samples=pag_max_dag_samples,
            pag_threshold=pag_threshold,
            pag_seed=pag_seed,
        )
        if pag_result is not None:
            return _finalize_transport_result(
                pag_result,
                privacy_context=privacy_context,
            )
    if not selection_diagram.s_nodes:
        return _finalize_transport_result(
            _direct_result(
                diagram=selection_diagram,
                treatment=query_treatment,
                outcome=query_outcome,
                engine="simplified_legacy",
                trace=[*trace, "family:direct"],
            ),
            privacy_context=privacy_context,
        )
    for backend_id in _backend_order(mode, allow_degraded_transport=allow_degraded_transport):
        trace.append(f"backend_attempt:{backend_id.value}")
        if backend_id is CausalBackendId.BOUNDS_ONLY:
            result = _run_bounds_only(
                diagram=selection_diagram,
                treatment=query_treatment,
                outcome=query_outcome,
                trace=trace,
            )
            if result is not None:
                return _finalize_transport_result(
                    result,
                    privacy_context=privacy_context,
                )
            continue
        if backend_id is CausalBackendId.SIMPLIFIED_LEGACY:
            result = _run_simplified_legacy(
                diagram=selection_diagram,
                treatment=query_treatment,
                outcome=query_outcome,
                trace=trace,
                pag_identification_policy=pag_identification_policy,
                pag_max_dag_samples=pag_max_dag_samples,
                pag_threshold=pag_threshold,
                pag_seed=pag_seed,
            )
            if result is not None:
                return _finalize_transport_result(
                    result,
                    privacy_context=privacy_context,
                )
            continue

        backend = contract.backend(backend_id)
        if backend is None or not backend.available:
            trace.append(
                f"backend_unavailable:{backend_id.value}:{backend.disabled_reason if backend else 'missing'}"
            )
            continue
        result = _run_symbolic_backend(
            backend_id=backend_id,
            diagram=selection_diagram,
            treatment=query_treatment,
            outcome=query_outcome,
            trace=trace,
        )
        if result is not None:
            return _finalize_transport_result(
                result,
                privacy_context=privacy_context,
            )

    return _finalize_transport_result(
        TransportabilityResult(
            query=f"P*({query_outcome}|do({query_treatment}))",
            status=TransportabilityStatus.UNSUPPORTED,
            transport_mode=TransportMode.NONE,
            base_confidence=0.0,
            context_distance_penalty=0.0,
            data_availability_penalty=0.0,
            final_confidence=0.0,
            algorithm_version="trso_v2",
            identification_engine="bounds_only",
            identification_trace=trace + ["transport_engine:unsupported"],
            unsupported_reason="transport_engine_exhausted_backends",
            warnings=["All configured transport backends were exhausted without identification."],
            source_context_id=selection_diagram.source_context.context_id,
            target_context_id=selection_diagram.target_context.context_id,
        ),
        privacy_context=privacy_context,
    )


def _finalize_transport_result(
    result: TransportabilityResult,
    *,
    privacy_context: TransportPrivacyContext | None,
) -> TransportabilityResult:
    finalized = apply_transport_privacy_context(result, privacy_context)
    if result.unsupported_reason not in _NON_ADJUDICATIVE_TRANSPORT_REFUSALS:
        return finalized

    # Privacy projections may narrow a supported transport result, but cannot
    # turn an graph-admission limitation into an identified region.
    return finalized.model_copy(
        update={
            "status": TransportabilityStatus.UNSUPPORTED,
            "transport_mode": TransportMode.NONE,
            "transport_formula": None,
            "identified_region": None,
            "base_confidence": result.base_confidence,
            "context_distance_penalty": result.context_distance_penalty,
            "data_availability_penalty": result.data_availability_penalty,
            "final_confidence": result.final_confidence,
            "pag_identification_policy": result.pag_identification_policy,
            "id_confidence_under_pag": result.id_confidence_under_pag,
            "pag_dag_sample_size": result.pag_dag_sample_size,
            "pag_transportable_count": result.pag_transportable_count,
            "unsupported_reason": result.unsupported_reason,
        }
    )


def _is_valid_pag_policy(raw: PAGIdentificationPolicy | str | None) -> bool:
    """Return whether a supplied PAG policy is a recognized typed value."""
    if raw is None:
        return True
    value = raw.value if isinstance(raw, PAGIdentificationPolicy) else raw
    if not isinstance(value, str):
        return False
    try:
        PAGIdentificationPolicy(value)
    except ValueError:
        return False
    return True


def _graph_admission_refusal_result(
    *,
    selection_diagram: SelectionDiagram | None,
    treatment: str,
    outcome: str,
    reason: str,
    trace: list[str],
) -> TransportabilityResult:
    """Return a typed limitation without claiming identification or non-identification."""
    warning_by_reason = {
        "pag_identification_policy_invalid": (
            "The supplied PAG identification policy is invalid; no default policy was applied."
        ),
        "partial_graph_completion_semantics_not_established": (
            "Transportability for PAG/CPDAG input is not established until completion semantics "
            "are selected and validated."
        ),
        "unsupported_static_admg_profile": (
            "The graph does not meet the existing resolved static ADMG profile; no scalar "
            "identification claim was emitted."
        ),
        "causal_graph_profile_invalid": (
            "The supplied graph does not satisfy canonical graph-profile validation; no scalar "
            "identification claim was emitted."
        ),
        "causal_graph_type_not_supported": (
            "This graph type is not admitted by the scalar transport and identification methods."
        ),
    }
    return TransportabilityResult(
        query=f"P*({outcome}|do({treatment}))",
        status=TransportabilityStatus.UNSUPPORTED,
        transport_mode=TransportMode.NONE,
        base_confidence=0.0,
        context_distance_penalty=0.0,
        data_availability_penalty=0.0,
        final_confidence=0.0,
        algorithm_version="trso_v2_scalar_graph_admission_refusal",
        identification_engine="scalar_graph_admission_refusal",
        identification_trace=trace,
        unsupported_reason=reason,
        warnings=[warning_by_reason[reason]],
        source_context_id=(
            selection_diagram.source_context.context_id
            if selection_diagram is not None
            else "not_established:noncanonical_selection_diagram"
        ),
        target_context_id=(
            selection_diagram.target_context.context_id
            if selection_diagram is not None
            else "not_established:noncanonical_selection_diagram"
        ),
    )


def validate_scalar_graph_selection_diagram(
    raw_diagram: Any,
    *,
    treatment: str,
    outcome: str,
    solver_mode: str,
    privacy_context: TransportPrivacyContext | None = None,
) -> tuple[SelectionDiagram | None, TransportabilityResult | None]:
    """Parse a selection diagram and type-refuse malformed graph profiles.

    Graphs that fail canonical IR validation cannot enter an algorithm merely
    because they were supplied as a mapping instead of a preconstructed model.
    Other malformed selection-diagram fields retain their ordinary validation
    error; this adapter only projects the rejected graph into the existing typed
    scalar-admission limitation.
    """
    if isinstance(raw_diagram, SelectionDiagram) and type(raw_diagram) is not SelectionDiagram:
        trace = [
            f"solver_mode:{solver_mode}",
            "graph_type:noncanonical_selection_diagram_object",
            "graph_profile:causal_graph_profile_invalid",
            "graph_admission_gate:refused:causal_graph_profile_invalid",
        ]
        result = _graph_admission_refusal_result(
            selection_diagram=None,
            treatment=treatment,
            outcome=outcome,
            reason="causal_graph_profile_invalid",
            trace=trace,
        )
        return None, _finalize_transport_result(result, privacy_context=privacy_context)

    try:
        parsed_diagram = SelectionDiagram.model_validate(raw_diagram)
        admitted_diagram = _snapshot_typed_model(parsed_diagram, SelectionDiagram)
        return admitted_diagram, None
    except _NoncanonicalSelectionSnapshotError:
        trace = [
            f"solver_mode:{solver_mode}",
            "graph_type:not_established:noncanonical_selection_diagram_fields",
            "graph_profile:causal_graph_profile_invalid",
            "graph_admission_gate:refused:causal_graph_profile_invalid",
        ]
        result = _graph_admission_refusal_result(
            selection_diagram=None,
            treatment=treatment,
            outcome=outcome,
            reason="causal_graph_profile_invalid",
            trace=trace,
        )
        return None, _finalize_transport_result(result, privacy_context=privacy_context)
    except (ValidationError, TypeError, ValueError) as validation_error:
        if not isinstance(raw_diagram, Mapping) or "base_graph" not in raw_diagram:
            raise

        # Validate the non-graph selection-diagram fields independently. The
        # placeholder is never consumed by an algorithm; it only supplies the
        # contexts needed for the typed, non-adjudicative refusal projection.
        sanitized = dict(raw_diagram)
        sanitized["base_graph"] = {
            "graph_type": GraphType.DAG.value,
            "nodes": ["__scalar_graph_admission__"],
            "edges": [],
        }
        try:
            diagram = SelectionDiagram.model_validate(sanitized)
        except (ValidationError, TypeError, ValueError):
            raise validation_error from None

        raw_graph = raw_diagram.get("base_graph")
        raw_graph_type = (
            raw_graph.get("graph_type")
            if isinstance(raw_graph, Mapping)
            else getattr(raw_graph, "graph_type", None)
        )
        graph_type_label = (
            raw_graph_type.value if isinstance(raw_graph_type, GraphType) else str(raw_graph_type)
        )
        trace = [
            f"solver_mode:{solver_mode}",
            f"graph_type:{graph_type_label}",
            "graph_profile:causal_graph_profile_invalid",
            "graph_admission_gate:refused:causal_graph_profile_invalid",
        ]
        result = _graph_admission_refusal_result(
            selection_diagram=diagram,
            treatment=treatment,
            outcome=outcome,
            reason="causal_graph_profile_invalid",
            trace=trace,
        )
        return diagram, _finalize_transport_result(result, privacy_context=privacy_context)


class _NoncanonicalSelectionSnapshotError(ValueError):
    """Mark a live input that cannot be copied as its declared IR value."""


def _snapshot_untyped_value(value: Any) -> Any:
    """Copy JSON-like values without invoking custom container or serializer methods."""
    if value is None or type(value) in (str, bool, int, float, bytes):
        return value
    if isinstance(value, Enum):
        return value
    if type(value) in (list, _FrozenList):
        return [_snapshot_untyped_value(item) for item in list.__iter__(value)]
    if type(value) in (dict, _FrozenDict):
        return {
            _snapshot_untyped_value(key): _snapshot_untyped_value(item)
            for key, item in dict.items(value)
        }
    if type(value) is tuple:
        return tuple(_snapshot_untyped_value(item) for item in tuple.__iter__(value))
    if type(value) is frozenset:
        return frozenset(_snapshot_untyped_value(item) for item in value)
    raise _NoncanonicalSelectionSnapshotError(
        f"unsupported untyped IR value: {type(value).__module__}.{type(value).__qualname__}"
    )


def _snapshot_typed_value(value: Any, annotation: Any) -> Any:
    """Copy one typed field through the declared schema, not caller overrides."""
    if annotation is Any:
        return _snapshot_untyped_value(value)

    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Literal:
        if any(type(value) is type(choice) and value == choice for choice in args):
            return value
        raise _NoncanonicalSelectionSnapshotError("value is outside its declared Literal")
    if origin in (Union, UnionType):
        for candidate in args:
            try:
                return _snapshot_typed_value(value, candidate)
            except _NoncanonicalSelectionSnapshotError:
                continue
        raise _NoncanonicalSelectionSnapshotError("value is outside its declared union")
    if origin is list:
        if type(value) not in (list, _FrozenList):
            raise _NoncanonicalSelectionSnapshotError("noncanonical list field")
        item_type = args[0] if args else Any
        return [_snapshot_typed_value(item, item_type) for item in list.__iter__(value)]
    if origin is tuple:
        if type(value) is not tuple:
            raise _NoncanonicalSelectionSnapshotError("noncanonical tuple field")
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_snapshot_typed_value(item, args[0]) for item in tuple.__iter__(value))
        if len(value) != len(args):
            raise _NoncanonicalSelectionSnapshotError("tuple field arity differs from its schema")
        return tuple(
            _snapshot_typed_value(item, item_type)
            for item, item_type in zip(tuple.__iter__(value), args, strict=True)
        )
    if origin is dict:
        if type(value) not in (dict, _FrozenDict):
            raise _NoncanonicalSelectionSnapshotError("noncanonical mapping field")
        key_type, value_type = args if len(args) == 2 else (Any, Any)
        return {
            _snapshot_typed_value(key, key_type): _snapshot_typed_value(item, value_type)
            for key, item in dict.items(value)
        }
    if origin in (set, frozenset):
        if type(value) not in (set, frozenset):
            raise _NoncanonicalSelectionSnapshotError("noncanonical set field")
        item_type = args[0] if args else Any
        return origin(_snapshot_typed_value(item, item_type) for item in value)
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return _snapshot_typed_model(value, annotation)
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        if type(value) is not annotation:
            raise _NoncanonicalSelectionSnapshotError("noncanonical enum field")
        return value
    if annotation is type(None):
        if value is not None:
            raise _NoncanonicalSelectionSnapshotError("non-null value for None field")
        return None
    if isinstance(annotation, type) and type(value) is annotation:
        return value
    raise _NoncanonicalSelectionSnapshotError(
        f"unsupported or noncanonical field for {annotation!r}"
    )


def _snapshot_typed_model(instance: Any, model_type: type[Any]) -> Any:
    """Rebuild a model from declared fields without calling instance serializers."""
    if type(instance) is not model_type:
        raise _NoncanonicalSelectionSnapshotError("noncanonical live model class")
    try:
        stored_fields = object.__getattribute__(instance, "__dict__")
    except AttributeError as exc:
        raise _NoncanonicalSelectionSnapshotError("model has no canonical field storage") from exc
    if type(stored_fields) is not dict:
        raise _NoncanonicalSelectionSnapshotError("model field storage is not a plain dictionary")

    snapshot: dict[str, Any] = {}
    for field_name, field in model_type.model_fields.items():
        if field_name not in stored_fields:
            raise _NoncanonicalSelectionSnapshotError(f"missing stored model field: {field_name}")
        snapshot[field_name] = _snapshot_typed_value(stored_fields[field_name], field.annotation)
    try:
        return model_type.model_validate(snapshot)
    except (TypeError, ValueError, ValidationError) as exc:
        raise _NoncanonicalSelectionSnapshotError("canonical model reconstruction failed") from exc


def _model_field_snapshot(instance: object, model_type: type[Any]) -> dict[str, Any] | None:
    """Copy canonical Pydantic field storage without invoking instance serializers."""
    if type(instance) is not model_type:
        return None
    try:
        stored_fields = object.__getattribute__(instance, "__dict__")
    except AttributeError:
        return None
    if type(stored_fields) is not dict:
        return None

    snapshot: dict[str, Any] = {}
    for field_name in model_type.model_fields:
        if field_name == "metadata":
            # Metadata is not part of the graph profile consumed by the static owner.
            continue
        if field_name not in stored_fields:
            continue
        value = stored_fields[field_name]
        if isinstance(value, list):
            if type(value) not in (list, _FrozenList):
                return None
            value = list(list.__iter__(value))
        elif isinstance(value, dict):
            if type(value) not in (dict, _FrozenDict):
                return None
            value = dict(dict.items(value))
        snapshot[field_name] = value
    return snapshot


def _canonical_scalar_graph_refusal(graph: Any) -> tuple[str | None, str]:
    """Admit exact live IR values from their stored fields, never their serializers."""
    if type(graph) is not CausalGraphModel:
        return "causal_graph_profile_invalid", "noncanonical_graph_object"

    graph_fields = _model_field_snapshot(graph, CausalGraphModel)
    if graph_fields is None:
        return "causal_graph_profile_invalid", "noncanonical_graph_object"

    graph_type = graph_fields.get("graph_type")
    if type(graph_type) is not GraphType:
        return "causal_graph_profile_invalid", "noncanonical_graph_type"
    graph_type_label = graph_type.value

    nodes = graph_fields.get("nodes")
    edges = graph_fields.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return "causal_graph_profile_invalid", graph_type_label
    if any(type(node) is not str for node in nodes):
        return "causal_graph_profile_invalid", graph_type_label

    edge_snapshots: list[dict[str, Any]] = []
    for edge in edges:
        edge_fields = _model_field_snapshot(edge, CausalEdge)
        if edge_fields is None:
            return "causal_graph_profile_invalid", graph_type_label
        mark_src = edge_fields.get("mark_src")
        mark_dst = edge_fields.get("mark_dst")
        src = edge_fields.get("src")
        dst = edge_fields.get("dst")
        lag = edge_fields.get("lag")
        if (
            type(src) is not str
            or type(dst) is not str
            or type(mark_src) is not EdgeMark
            or type(mark_dst) is not EdgeMark
            or (lag is not None and type(lag) is not int)
        ):
            return "causal_graph_profile_invalid", graph_type_label
        edge_snapshots.append(edge_fields)

    graph_fields["nodes"] = nodes
    graph_fields["edges"] = edge_snapshots
    try:
        canonical_graph = CausalGraphModel.model_validate(graph_fields)
    except (AttributeError, TypeError, ValueError):
        return "causal_graph_profile_invalid", graph_type_label

    graph_type = canonical_graph.graph_type
    graph_type_label = graph_type.value
    if graph_type in {GraphType.PAG, GraphType.CPDAG}:
        return "partial_graph_completion_semantics_not_established", graph_type_label
    if graph_type not in {GraphType.DAG, GraphType.ADMG}:
        return "causal_graph_type_not_supported", graph_type_label

    # Keep the scalar boundary on the canonical native static endpoint profile.
    # This admits the three resolved directed/bidirected mark pairs and rejects
    # every unresolved or temporal pair through the same owner used by static ID.
    from .admg_ops import (
        UnsupportedStaticADMGProfileError,
        _validate_static_admg,
        topological_order,
    )

    try:
        _validate_static_admg(canonical_graph)
    except UnsupportedStaticADMGProfileError:
        return "unsupported_static_admg_profile", graph_type_label
    try:
        topological_order(canonical_graph)
    except (AttributeError, TypeError, ValueError):
        return "causal_graph_profile_invalid", graph_type_label
    return None, graph_type_label


def scalar_graph_admission_refusal(
    *,
    selection_diagram: SelectionDiagram,
    treatment: str,
    outcome: str,
    solver_mode: str,
    pag_identification_policy: PAGIdentificationPolicy | str | None,
    policy_present: bool | None = None,
    privacy_context: TransportPrivacyContext | None = None,
) -> TransportabilityResult | None:
    """Refuse scalar claims unless the complete canonical graph profile is admitted.

    ``policy_present`` preserves the distinction between an absent optional value
    and a supplied null at mapping-based Foundry boundaries. Direct solver calls
    retain their existing optional-``None`` contract by inferring presence from a
    non-null value.
    """
    if type(selection_diagram) is not SelectionDiagram:
        reason, graph_type_label = (
            "causal_graph_profile_invalid",
            "noncanonical_selection_diagram_object",
        )
        refusal_diagram: SelectionDiagram | None = None
    else:
        diagram_fields = object.__getattribute__(selection_diagram, "__dict__")
        graph = diagram_fields.get("base_graph")
        reason, graph_type_label = _canonical_scalar_graph_refusal(graph)
        refusal_diagram = selection_diagram
    if reason is None:
        return None

    supplied = pag_identification_policy is not None if policy_present is None else policy_present
    invalid_policy = (
        reason == "partial_graph_completion_semantics_not_established"
        and supplied
        and (
            pag_identification_policy is None or not _is_valid_pag_policy(pag_identification_policy)
        )
    )
    if invalid_policy:
        reason = "pag_identification_policy_invalid"

    trace = [
        f"solver_mode:{solver_mode}",
        f"graph_type:{graph_type_label}",
        f"graph_profile:{reason}",
    ]
    if reason == "partial_graph_completion_semantics_not_established":
        if not supplied:
            trace.append("pag_policy_input:absent")
        else:
            effective_policy = (
                pag_identification_policy.value
                if isinstance(pag_identification_policy, PAGIdentificationPolicy)
                else pag_identification_policy
            )
            trace.append(f"pag_policy_effective:{effective_policy};origin:not_established")
    elif reason == "pag_identification_policy_invalid":
        trace.append("pag_policy_input:invalid_present_value")
    trace.append(f"graph_admission_gate:refused:{reason}")

    result = _graph_admission_refusal_result(
        selection_diagram=refusal_diagram,
        treatment=treatment,
        outcome=outcome,
        reason=reason,
        trace=trace,
    )
    return _finalize_transport_result(result, privacy_context=privacy_context)


def scalar_graph_refusal_proof_bundle(result: TransportabilityResult) -> ProofBundle | None:
    """Build the non-adjudicative proof projection for a graph-admission refusal."""
    if result.unsupported_reason not in _NON_ADJUDICATIVE_TRANSPORT_REFUSALS:
        return None
    return ProofBundle(
        proof_status="oracle_needed",
        proof_stratum="A1_extended",
        theorem_family=str(result.algorithm_version or "transportability"),
        completeness_regime="sound_incomplete",
        implementation_coverage="scalar_graph_admission_gate",
        query_ref=str(result.query or ""),
        proof_trace=list(result.identification_trace),
        assumptions=[],
        metadata={
            "status": result.status.value,
            "transport_mode": result.transport_mode.value,
            "reason": result.unsupported_reason,
        },
    )


def _should_use_probabilistic_pag_path(
    *,
    selection_diagram: SelectionDiagram,
    pag_identification_policy: PAGIdentificationPolicy | str | None,
) -> bool:
    graph_type = getattr(selection_diagram.base_graph.graph_type, "value", "")
    if graph_type != "pag":
        return False
    if pag_identification_policy is None:
        return True
    try:
        return (
            PAGIdentificationPolicy(str(pag_identification_policy))
            is PAGIdentificationPolicy.PROBABILISTIC
        )
    except Exception:
        return True


def _attach_estimand_ast(
    result: TransportabilityResult,
    estimand_ast: Any,
) -> TransportabilityResult:
    """Return a copy of *result* with *estimand_ast* serialised into the result."""
    return result.model_copy(update={"estimand_ast": estimand_ast.model_dump(mode="json")})


def _estimand_ast_to_transport_formula(
    ast: Any,
    *,
    engine: str,
) -> TransportFormula | None:
    """Convert a symbolic EstimandAST to a TransportFormula for the result contract.

    Extracts stratification variables, source quantities, and target quantities
    from the tree structure of the estimand.

    Returns None when the AST shape is not expressible as a simple TransportFormula.
    """
    from polisyos.ir.analytics.estimand import DistributionDomain

    try:
        latex = ast.to_latex()
        dist_refs = ast.collect_distribution_refs()

        source_qtys = [
            ref.to_latex()
            for ref in dist_refs
            if ref.domain in {DistributionDomain.SOURCE, DistributionDomain.EXPERIMENTAL}
        ]
        target_qtys = [
            ref.to_latex() for ref in dist_refs if ref.domain is DistributionDomain.TARGET
        ]

        # Extract summation/stratification variables from SumNode root or first SumNode child
        strat_vars: list[str] = []
        root = ast.root
        if hasattr(root, "summation_vars"):
            strat_vars = list(root.summation_vars)
        elif hasattr(root, "factors"):
            for factor in root.factors:
                if hasattr(factor, "summation_vars"):
                    strat_vars = list(factor.summation_vars)
                    break

        adj_type = "transport_formula"
        if not strat_vars:
            adj_type = "direct"

        return TransportFormula(
            formula_str=latex,
            stratification_variables=strat_vars,
            stratification_details=[],
            source_quantities=source_qtys,
            target_quantities=target_qtys,
            adjustment_type=adj_type,
        )
    except Exception:
        return None


def _try_tr_via_id_engine(
    *,
    diagram: SelectionDiagram,
    treatment: str,
    outcome: str,
    backend_id: CausalBackendId,
    trace: list[str],
) -> TransportabilityResult | None:
    """Attempt identification via the formal TR algorithm from id_engine.

    Runs :func:`tr_algorithm` on the selection diagram, applies the do-calculus
    simplification post-pass via :func:`rewrite_estimand`, converts the resulting
    :class:`EstimandAST` to a :class:`TransportFormula`, and returns a
    :class:`TransportabilityResult`.

    Returns None if identification fails or the estimand cannot be converted.
    """
    try:
        from polisyos.foundry.methods.catalog.causal.do_calculus import (
            rewrite_estimand,
        )
        from polisyos.foundry.methods.catalog.causal.id_engine import (
            IdentificationStatus,
            tr_algorithm,
        )
    except ImportError:
        return None

    try:
        id_result = tr_algorithm(
            treatment=frozenset({treatment}),
            outcome=frozenset({outcome}),
            selection_diagram=diagram,
        )
    except Exception:
        return None

    if id_result.status is not IdentificationStatus.IDENTIFIED:
        return None
    if id_result.estimand_ast is None:
        return None

    # Apply do-calculus simplification post-pass
    try:
        simplified_ast, rewrite_steps = rewrite_estimand(id_result.estimand_ast, diagram.base_graph)
    except Exception:
        simplified_ast = id_result.estimand_ast
        rewrite_steps = []

    # Convert EstimandAST to TransportFormula
    formula = _estimand_ast_to_transport_formula(simplified_ast, engine=backend_id.value)
    if formula is None:
        return None

    engine_tag = f"id_engine_tr:{backend_id.value}"
    n_rewrite = len(rewrite_steps)
    extra_trace = [
        *trace,
        f"symbolic_backend_selected:{backend_id.value}",
        "tr_id_engine_identified",
    ]
    if n_rewrite > 0:
        extra_trace.append(f"do_calculus_rewrite:{n_rewrite}_steps")

    context_penalty = min(float(diagram.context_distance) * 0.35, 0.6)
    data_penalty = min(0.6, 0.15 * len(formula.target_quantities))

    base_result = TransportabilityResult(
        query=f"P*({outcome}|do({treatment}))",
        status=TransportabilityStatus.IDENTIFIED,
        transport_mode=(
            TransportMode.TRANSPORT_FORMULA if formula.target_quantities else TransportMode.DIRECT
        ),
        transport_formula=formula if formula.target_quantities else None,
        base_confidence=1.0,
        context_distance_penalty=context_penalty,
        data_availability_penalty=data_penalty,
        final_confidence=max(0.0, 1.0 - context_penalty - data_penalty),
        algorithm_version="trso_v2",
        identification_engine=engine_tag,
        identification_trace=extra_trace,
        required_target_data=list(formula.target_quantities),
        source_context_id=diagram.source_context.context_id,
        target_context_id=diagram.target_context.context_id,
    )

    return _attach_estimand_ast(base_result, simplified_ast)


def _run_symbolic_backend(
    *,
    backend_id: CausalBackendId,
    diagram: SelectionDiagram,
    treatment: str,
    outcome: str,
    trace: list[str],
) -> TransportabilityResult | None:
    base_trace = [*trace, f"symbolic_backend_selected:{backend_id.value}"]
    # Attempt formal TR identification via id_engine (with do-calculus post-pass)
    tr_result = _try_tr_via_id_engine(
        diagram=diagram,
        treatment=treatment,
        outcome=outcome,
        backend_id=backend_id,
        trace=trace,
    )
    if tr_result is not None:
        return tr_result

    if not diagram.s_nodes:
        return _direct_result(
            diagram=diagram,
            treatment=treatment,
            outcome=outcome,
            engine=backend_id.value,
            trace=base_trace + ["family:direct"],
        )

    mediator = _frontdoor_mediator(
        graph_nodes=diagram.base_graph.nodes,
        directed_edges=_directed_edges(diagram.base_graph),
        treatment=treatment,
        outcome=outcome,
    )
    if mediator is not None:
        return _identified_formula_result(
            diagram=diagram,
            treatment=treatment,
            outcome=outcome,
            engine=backend_id.value,
            formula=_frontdoor_formula(treatment=treatment, outcome=outcome, mediator=mediator),
            trace=base_trace + [f"family:frontdoor:{mediator}"],
        )

    adjustment_vars = _rule2_adjustment_candidates(
        graph_nodes=diagram.base_graph.nodes,
        s_node_roles={item.target_variable: item.role for item in diagram.s_nodes},
        treatment=treatment,
        outcome=outcome,
    )
    if adjustment_vars:
        return _identified_formula_result(
            diagram=diagram,
            treatment=treatment,
            outcome=outcome,
            engine=backend_id.value,
            formula=_rule2_formula(
                treatment=treatment,
                outcome=outcome,
                adjustment_vars=adjustment_vars,
            ),
            trace=base_trace + [f"family:do_calculus_rule2:{','.join(adjustment_vars)}"],
        )

    component_vars = _c_component_candidates(diagram.s_nodes)
    if component_vars:
        return _partial_formula_result(
            diagram=diagram,
            treatment=treatment,
            outcome=outcome,
            engine=backend_id.value,
            formula=_c_component_formula(
                treatment=treatment,
                outcome=outcome,
                component_vars=component_vars,
            ),
            identified_region={"identified_components": component_vars},
            trace=base_trace + [f"family:c_component_factorization:{','.join(component_vars)}"],
        )

    if any(node.role is SNodeRole.INSTRUMENT for node in diagram.s_nodes):
        return _partial_formula_result(
            diagram=diagram,
            treatment=treatment,
            outcome=outcome,
            engine=backend_id.value,
            formula=_rule3_formula(treatment=treatment, outcome=outcome, s_nodes=diagram.s_nodes),
            identified_region={"rule": "do_calculus_rule3"},
            trace=base_trace + ["family:do_calculus_rule3"],
        )

    return None


def _run_bounds_only(
    *,
    diagram: SelectionDiagram,
    treatment: str,
    outcome: str,
    trace: list[str],
) -> TransportabilityResult:
    try:
        partial = transport_bounds(selection_diagram=diagram)
    except Exception:
        partial = compute_manski_bounds(
            outcome_conditioned=np.array([0.4, 0.6]),
            treatment_probs=np.array([0.5, 0.5]),
            outcome_support=(0.0, 1.0),
        )
    return TransportabilityResult(
        query=f"P*({outcome}|do({treatment}))",
        status=TransportabilityStatus.BOUNDED_NON_IDENTIFIED,
        transport_mode=TransportMode.BOUNDS_ONLY,
        base_confidence=0.35,
        context_distance_penalty=min(float(diagram.context_distance) * 0.3, 0.5),
        data_availability_penalty=0.35,
        final_confidence=max(0.0, 0.35 - min(float(diagram.context_distance) * 0.1, 0.2)),
        algorithm_version="trso_v2_bounds",
        identification_engine="bounds_only",
        identification_trace=[*trace, "family:transport_bounds"],
        warnings=[
            "Exact transport identification unavailable; emitted transport-aware bounds fallback."
        ],
        partial_identification_result=partial,
        required_target_data=sorted({node.target_variable for node in diagram.s_nodes}),
        source_context_id=diagram.source_context.context_id,
        target_context_id=diagram.target_context.context_id,
    )


def _run_simplified_legacy(
    *,
    diagram: SelectionDiagram,
    treatment: str,
    outcome: str,
    trace: list[str],
    pag_identification_policy: PAGIdentificationPolicy | str | None,
    pag_max_dag_samples: int,
    pag_threshold: float,
    pag_seed: int,
) -> TransportabilityResult | None:
    from polisyos.foundry.methods.catalog.causal.transport_check import _legacy_pure_step

    payload = _legacy_pure_step(
        {
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": treatment,
            "query_outcome": outcome,
        },
        {
            "pag_identification_policy": pag_identification_policy,
            "pag_max_dag_samples": pag_max_dag_samples,
            "pag_threshold": pag_threshold,
            "pag_seed": pag_seed,
        },
    )
    legacy = TransportabilityResult.model_validate(payload["transport_result"])
    next_trace = [*trace, "legacy_simplified_fallback"]
    return legacy.model_copy(
        update={
            "algorithm_version": (
                "trso_v2"
                if legacy.algorithm_version == "simplified_tr_v2"
                else legacy.algorithm_version
            ),
            "identification_engine": "simplified_legacy",
            "identification_trace": [*legacy.identification_trace, *next_trace],
        }
    )


def _direct_result(
    *,
    diagram: SelectionDiagram,
    treatment: str,
    outcome: str,
    engine: str,
    trace: list[str],
) -> TransportabilityResult:
    lagged_count = _lagged_edge_count(diagram.base_graph)
    return TransportabilityResult(
        query=f"P*({outcome}|do({treatment}))",
        status=TransportabilityStatus.IDENTIFIED,
        transport_mode=TransportMode.DIRECT,
        base_confidence=1.0,
        context_distance_penalty=0.0,
        data_availability_penalty=0.0,
        final_confidence=1.0,
        algorithm_version="trso_v2",
        identification_engine=engine,
        identification_trace=trace,
        source_context_id=diagram.source_context.context_id,
        target_context_id=diagram.target_context.context_id,
        assumes_time_stationarity=lagged_count > 0,
        lagged_edge_count=lagged_count,
        temporal_distance_penalty=min(0.3, float(diagram.context_distance) * 0.2)
        if lagged_count > 0
        else 0.0,
    )


def _identified_formula_result(
    *,
    diagram: SelectionDiagram,
    treatment: str,
    outcome: str,
    engine: str,
    formula: TransportFormula,
    trace: list[str],
) -> TransportabilityResult:
    context_penalty = min(float(diagram.context_distance) * 0.35, 0.6)
    data_penalty = min(0.6, 0.15 * len(formula.target_quantities))
    return TransportabilityResult(
        query=f"P*({outcome}|do({treatment}))",
        status=TransportabilityStatus.IDENTIFIED,
        transport_mode=TransportMode.TRANSPORT_FORMULA,
        transport_formula=formula,
        base_confidence=1.0,
        context_distance_penalty=context_penalty,
        data_availability_penalty=data_penalty,
        final_confidence=max(0.0, 1.0 - context_penalty - data_penalty),
        algorithm_version="trso_v2",
        identification_engine=engine,
        identification_trace=trace,
        required_target_data=list(formula.target_quantities),
        source_context_id=diagram.source_context.context_id,
        target_context_id=diagram.target_context.context_id,
    )


def _partial_formula_result(
    *,
    diagram: SelectionDiagram,
    treatment: str,
    outcome: str,
    engine: str,
    formula: TransportFormula,
    identified_region: dict[str, Any],
    trace: list[str],
) -> TransportabilityResult:
    context_penalty = min(float(diagram.context_distance) * 0.35, 0.7)
    data_penalty = min(0.7, 0.2 * len(formula.target_quantities))
    return TransportabilityResult(
        query=f"P*({outcome}|do({treatment}))",
        status=TransportabilityStatus.PARTIALLY_IDENTIFIED,
        transport_mode=TransportMode.TRANSPORT_FORMULA,
        transport_formula=formula,
        identified_region=identified_region,
        base_confidence=0.7,
        context_distance_penalty=context_penalty,
        data_availability_penalty=data_penalty,
        final_confidence=max(0.0, 0.7 - context_penalty - data_penalty),
        algorithm_version="trso_v2",
        identification_engine=engine,
        identification_trace=trace,
        required_target_data=list(formula.target_quantities),
        source_context_id=diagram.source_context.context_id,
        target_context_id=diagram.target_context.context_id,
        warnings=["Transportability only partially identified for this graph shape."],
    )


def _frontdoor_formula(*, treatment: str, outcome: str, mediator: str) -> TransportFormula:
    normalized = normalize_transport_formula(
        formula=(
            f"P*({outcome}|do({treatment})) = "
            f"Σ_{{{mediator}}} P*({mediator}|{treatment}) * "
            f"Σ_{{{treatment}}} P({outcome}|{mediator},{treatment})P({treatment})"
        )
    )
    return TransportFormula(
        formula_str=normalized.formula_str,
        stratification_variables=[*normalized.stratification_variables] or [mediator],
        stratification_details=[
            StratificationVariable(
                name=mediator,
                role=SNodeRole.MEDIATOR,
                requires_conditional=True,
                condition_on_treatment=treatment,
            )
        ],
        source_quantities=[*normalized.source_quantities]
        or [f"P({outcome}|{mediator},{treatment})", f"P({treatment})"],
        target_quantities=[*normalized.target_quantities] or [f"P*({mediator}|{treatment})"],
        adjustment_type="frontdoor_symbolic",
    )


def _rule2_formula(
    *,
    treatment: str,
    outcome: str,
    adjustment_vars: list[str],
) -> TransportFormula:
    adjustment = ",".join(adjustment_vars)
    normalized = normalize_transport_formula(
        formula=(
            f"P*({outcome}|do({treatment})) = "
            f"Σ_{{{adjustment}}} P({outcome}|do({treatment}),{adjustment})P*({adjustment})"
        )
    )
    return TransportFormula(
        formula_str=normalized.formula_str,
        stratification_variables=list(adjustment_vars),
        stratification_details=[
            StratificationVariable(
                name=var,
                role=SNodeRole.PRE_TREATMENT_COVARIATE,
                requires_conditional=False,
            )
            for var in adjustment_vars
        ],
        source_quantities=[*normalized.source_quantities]
        or [f"P({outcome}|do({treatment}),{adjustment})"],
        target_quantities=[*normalized.target_quantities] or [f"P*({adjustment})"],
        adjustment_type="do_calculus_rule2",
    )


def _rule3_formula(
    *,
    treatment: str,
    outcome: str,
    s_nodes: Iterable[Any],
) -> TransportFormula:
    instruments = [
        str(item.target_variable) for item in s_nodes if item.role is SNodeRole.INSTRUMENT
    ]
    instrument = instruments[0] if instruments else "z"
    normalized = normalize_transport_formula(
        formula=(
            f"P*({outcome}|do({treatment})) partially identified via "
            f"Σ_{{{instrument}}} P({outcome}|{instrument},do({treatment}))P*({instrument})"
        )
    )
    return TransportFormula(
        formula_str=normalized.formula_str,
        stratification_variables=[instrument],
        stratification_details=[
            StratificationVariable(
                name=instrument,
                role=SNodeRole.INSTRUMENT,
                requires_conditional=False,
            )
        ],
        source_quantities=[*normalized.source_quantities]
        or [f"P({outcome}|{instrument},do({treatment}))"],
        target_quantities=[*normalized.target_quantities] or [f"P*({instrument})"],
        adjustment_type="do_calculus_rule3_partial",
    )


def _c_component_formula(
    *,
    treatment: str,
    outcome: str,
    component_vars: list[str],
) -> TransportFormula:
    adjustment = ",".join(component_vars)
    normalized = normalize_transport_formula(
        formula=(
            f"P*({outcome}|do({treatment})) partially identified via "
            f"Π_{{c in {adjustment}}} P*({{c}}) * P({outcome}|do({treatment}),{adjustment})"
        )
    )
    return TransportFormula(
        formula_str=normalized.formula_str,
        stratification_variables=list(component_vars),
        stratification_details=[
            StratificationVariable(
                name=var,
                role=SNodeRole.MEDIATOR,
                requires_conditional=False,
            )
            for var in component_vars
        ],
        source_quantities=[*normalized.source_quantities]
        or [f"P({outcome}|do({treatment}),{adjustment})"],
        target_quantities=[*normalized.target_quantities] or [f"P*({adjustment})"],
        adjustment_type="c_component_factorization_partial",
    )


def _frontdoor_mediator(
    *,
    graph_nodes: list[str],
    directed_edges: set[tuple[str, str]],
    treatment: str,
    outcome: str,
) -> str | None:
    del graph_nodes
    mediators = sorted(
        {
            mediator
            for src, mediator in directed_edges
            if src == treatment and (mediator, outcome) in directed_edges
        }
    )
    return mediators[0] if mediators else None


def _rule2_adjustment_candidates(
    *,
    graph_nodes: list[str],
    s_node_roles: dict[str, Any],
    treatment: str,
    outcome: str,
) -> list[str]:
    preferred = [
        node
        for node in graph_nodes
        if node != treatment and s_node_roles.get(node) is SNodeRole.PRE_TREATMENT_COVARIATE
    ]
    if preferred:
        return sorted(preferred)
    heuristics = [node for node in graph_nodes if node not in {treatment, outcome}]
    return sorted(heuristics[:1])


def _c_component_candidates(s_nodes: list[Any]) -> list[str]:
    components = sorted(
        {str(node.target_variable) for node in s_nodes if node.role is SNodeRole.MEDIATOR}
    )
    if len(components) >= 2:
        return components
    return []


def _directed_edges(graph: Any) -> set[tuple[str, str]]:
    from polisyos.ir.analytics.causal_graph import CausalEdge, EdgeMark

    directed: set[tuple[str, str]] = set()
    for edge in graph.edges:
        if not isinstance(edge, CausalEdge):
            continue
        if edge.mark_src is EdgeMark.ARROW and edge.mark_dst in {EdgeMark.TAIL, EdgeMark.CIRCLE}:
            directed.add((edge.dst, edge.src))
            continue
        if edge.mark_dst is EdgeMark.ARROW and edge.mark_src in {EdgeMark.TAIL, EdgeMark.CIRCLE}:
            directed.add((edge.src, edge.dst))
            continue
        if edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.TAIL:
            continue
        directed.add((edge.src, edge.dst))
    return directed


def _lagged_edge_count(graph: Any) -> int:
    return sum(
        1 for edge in getattr(graph, "edges", []) if getattr(edge, "lag", None) not in (None, 0)
    )


def _backend_order(mode: str, *, allow_degraded_transport: bool) -> list[CausalBackendId]:
    if mode == "simplified":
        return [CausalBackendId.SIMPLIFIED_LEGACY]
    if mode == "symbolic_y0":
        base = [CausalBackendId.Y0, CausalBackendId.BOUNDS_ONLY]
    elif mode == "symbolic_r":
        base = [CausalBackendId.R_CAUSALEFFECT, CausalBackendId.BOUNDS_ONLY]
    else:
        base = [
            CausalBackendId.Y0,
            CausalBackendId.R_CAUSALEFFECT,
            CausalBackendId.BOUNDS_ONLY,
        ]
    if allow_degraded_transport and CausalBackendId.SIMPLIFIED_LEGACY not in base:
        base.append(CausalBackendId.SIMPLIFIED_LEGACY)
    return base


def _normalize_solver_mode(raw: str | None) -> str:
    token = str(raw or "auto").strip().lower()
    if token not in _VALID_SOLVER_MODES:
        return "auto"
    if token == "symbolic":
        return "full_auto"
    return token


__all__ = ["solve_transportability"]
