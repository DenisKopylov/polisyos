"""Internal welfare types implementation helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from pydantic import ValidationError

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.foundry.calibration.report import CalibrationCoordinateProjection
from polisyos.foundry.uncertainty import extract_std as _extract_typed_std
from polisyos.ir.analytics import DependenceStructure, UncertaintyEnvelope, WelfareMethod
from polisyos.ir.artifacts import get_json_artifact
from polisyos.ir.registry.refs import (
    ArtifactRefModel,
    DependenceStructureRef,
    GEUncertaintyBundleRef,
    UncertaintyEnvelopeRef,
    WelfareSampleBundleRef,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_SIMULATION_RESULT_REF,
    ARTIFACT_WELFARE_BUNDLE_REF,
    INPUT_CALIBRATION_REPORT_REF,
    INPUT_DATA_SNAPSHOT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeSpec

_WELFARE_LOAD_ERRORS = (OSError, RuntimeError, TypeError, ValueError, ValidationError)

_WELFARE_VALIDATION_ERRORS = (TypeError, ValueError, ValidationError)

_ERROR_WELFARE_MODEL_CLASS_MISMATCH = "ERROR_WELFARE_MODEL_CLASS_MISMATCH"

_ERROR_WELFARE_DIMENSION_MISMATCH = "ERROR_WELFARE_DIMENSION_MISMATCH"

_ERROR_GE_OPERATOR_SINGULAR = "ERROR_GE_OPERATOR_SINGULAR"

_ERROR_GE_UNCERTAINTY_REF_KIND = "ERROR_GE_UNCERTAINTY_REF_KIND"

_ERROR_DEPENDENCE_SPEC_INVALID = "ERROR_DEPENDENCE_SPEC_INVALID"

_ERROR_INTERVAL_SEMANTICS_INVALID = "ERROR_INTERVAL_SEMANTICS_INVALID"

_ERROR_MONTE_CARLO_NOT_CONVERGED = "ERROR_MONTE_CARLO_NOT_CONVERGED"

_ERROR_WELFARE_OUTPUT_NONFINITE = "ERROR_WELFARE_OUTPUT_NONFINITE"

_ERROR_WELFARE_UNCERTAINTY_SCALE_INVALID = "ERROR_WELFARE_UNCERTAINTY_SCALE_INVALID"

_ERROR_WELFARE_GLOBAL_EVALUATION_FAILURE = "ERROR_WELFARE_GLOBAL_EVALUATION_FAILURE"

_ERROR_WELFARE_EVALUATION_SCOPE_UNKNOWN = "ERROR_WELFARE_EVALUATION_SCOPE_UNKNOWN"

_ERROR_CHANNEL_DECOMPOSITION_CONFIG_INVALID = "ERROR_CHANNEL_DECOMPOSITION_CONFIG_INVALID"

_ERROR_CHANNEL_DECOMPOSITION_BUILD_FAILED = "ERROR_CHANNEL_DECOMPOSITION_BUILD_FAILED"

_WELFARE_MC_MAX_EXECUTION_ATTEMPTS = 2

_EXPLICIT_WELFARE_RESPONSE_KEYS = frozenset(("pe_response", "metric_order", "weights"))

_EXPLICIT_GE_UNCERTAINTY_KEYS = frozenset(
    (
        "ge_uncertainty_ref",
        "ge_matrix",
        "ge_lower_matrix",
        "ge_upper_matrix",
        "ge_technical_coefficients",
        "ge_lower_technical_coefficients",
        "ge_upper_technical_coefficients",
        "ge_model_ref",
        "ge_entry_map",
    )
)

_DEFAULT_CONDITION_THRESHOLD = 1e12

_DEFAULT_MAX_VERTEX_ENUMERATION = 10

_CALIBRATION_COORDINATE_PROJECTION_VERSION = "1.0"

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_propagate_welfare@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Propagate Welfare",
    description="Aggregate PE and GE uncertainty into a typed welfare bundle.",
    tags=["builtin", "simulate", "welfare"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        f"artifacts_index.{ARTIFACT_SIMULATION_RESULT_REF}",
        f"inputs.{INPUT_DATA_SNAPSHOT_REF}",
        f"inputs.{INPUT_CALIBRATION_REPORT_REF}",
        "params.welfare_config",
        "params.welfare_channel_decomposition",
        "params.welfare_weights",
        "params.welfare_social_weight_manifest",
        "params.welfare_social_weight_ref",
        "params.welfare_metric_order",
        "params.welfare_pe_response",
        "params.welfare_pe_sensitivity",
        "params.welfare_ge_matrix",
        "params.welfare_ge_lower_matrix",
        "params.welfare_ge_upper_matrix",
        "params.welfare_ge_technical_coefficients",
        "params.welfare_ge_lower_technical_coefficients",
        "params.welfare_ge_upper_technical_coefficients",
        "params.welfare_ge_entry_map",
        "params.welfare_ge_model_ref",
        "params.welfare_ge_uncertainty_ref",
        "params.welfare_dependence_structure_ref",
        "params.social_weight_manifest",
        "params.social_weight_ref",
        "params.propagation_config",
    ],
    state_writes=[
        f"artifacts_index.{ARTIFACT_SIMULATION_RESULT_REF}",
        f"artifacts_index.{ARTIFACT_WELFARE_BUNDLE_REF}",
    ],
    produces=[ARTIFACT_SIMULATION_RESULT_REF, ARTIFACT_WELFARE_BUNDLE_REF],
)


@dataclass(frozen=True)
class _ResolvedGEContext:
    source_kind: Literal["none", "multiplier", "technical_coefficients"]
    point_multiplier: np.ndarray | None
    source_matrix: np.ndarray | None
    lower_multiplier: np.ndarray | None
    upper_multiplier: np.ndarray | None
    ge_model_ref: ArtifactRefModel | None
    ge_uncertainty_ref: GEUncertaintyBundleRef | None
    ge_entry_map: dict[str, tuple[int, int]]
    diagnostics: dict[str, Any]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class _ResolvedDependenceContext:
    ref: DependenceStructureRef | None
    structure: DependenceStructure | None
    correlation_matrix: np.ndarray | None
    parameter_order: tuple[str, ...]
    strategy: str
    warnings: tuple[str, ...]
    diagnostics: dict[str, Any]


@dataclass(frozen=True)
class _ResolvedWelfareContext:
    welfare_measure: str
    model_class: str
    ge_multiplier_semantics: str
    labels: tuple[str, ...]
    base_response: np.ndarray
    weights: np.ndarray
    weights_ref: ArtifactRefModel | None
    social_weight_ref: ArtifactRefModel | None
    policy_ref: ArtifactRefModel | None
    baseline_ref: ArtifactRefModel | None
    pe_model_ref: ArtifactRefModel | None
    dependence_structure_ref: DependenceStructureRef | None
    dependence_context: _ResolvedDependenceContext
    pe_sensitivity: dict[str, dict[str, float]]
    ge_context: _ResolvedGEContext
    warnings: tuple[str, ...]
    diagnostics: dict[str, Any]


@dataclass(frozen=True)
class _EnvelopeCollection:
    envelopes: dict[str, UncertaintyEnvelope]
    refs: dict[str, UncertaintyEnvelopeRef]
    calibration_source: _CalibrationCovarianceSource | None = None


@dataclass(frozen=True)
class _EnvelopeOrigin:
    artifact_key: tuple[str, str] | None
    source_role: str


@dataclass(frozen=True)
class _CalibrationCovarianceSource:
    report_ref: ArtifactRefModel
    report_schema_version: str
    projection_status: str
    field_order: tuple[str, ...]
    projection_present: bool
    coordinate_projection: CalibrationCoordinateProjection | None
    coordinate_order: tuple[str, ...]
    coordinate_covariance: tuple[tuple[float, ...], ...]
    issue_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class _CalibrationCoordinateSampler:
    coordinate_order: tuple[str, ...]
    calibration_fields: tuple[str, ...]
    extra_fields: tuple[str, ...]
    projection_matrix: np.ndarray
    coordinate_covariance: np.ndarray
    joint_covariance: np.ndarray
    calibration_indices: tuple[int, ...]
    extra_indices: tuple[int, ...]
    projection_pseudoinverse: np.ndarray | None
    extra_stds: tuple[float, ...]


@dataclass(frozen=True)
class _EmpiricalRowSampler:
    param_names: tuple[str, ...]
    samples_by_name: Mapping[str, tuple[float, ...]]
    probabilities: tuple[float, ...]
    dependence_note: dict[str, Any]


@dataclass(frozen=True)
class _CalibrationCoordinateLaw:
    coordinate_order: tuple[str, ...]
    calibration_fields: tuple[str, ...]
    projection_matrix: np.ndarray
    coordinate_covariance: np.ndarray


@dataclass(frozen=True)
class _CovarianceResolution:
    matrix: np.ndarray | None
    dependence_applied: bool
    note: dict[str, Any]
    limitation_code: str | None = None
    coordinate_law: _CalibrationCoordinateLaw | None = None


@dataclass(frozen=True)
class _PropagationOutcome:
    credible_interval: tuple[float, float] | None
    method_used: WelfareMethod
    result_map: dict[str, Any]
    method_config_ref: ArtifactRefModel | None
    report_ref: ArtifactRefModel | None
    sample_bundle_ref: WelfareSampleBundleRef | None
    diagnostics: dict[str, Any]


class _WelfareNodeFailure(Exception):
    def __init__(self, error: NodeError) -> None:
        super().__init__(error.message)
        self.error = error


def _load_artifact_json(ctx: ExecutionContext, ref: ArtifactRef | ArtifactRefModel) -> Any:
    """Load JSON from the exact manifest view named by a typed artifact reference."""
    return get_json_artifact(_ensure_ir_artifact_store(ctx.store), ref)


def _input_ref(ref: ArtifactRef | ArtifactRefModel, *, role: str) -> InputRef:
    """Build one producer lineage edge without discarding its selected manifest view."""
    return InputRef(
        artifact_id=ref.artifact_id,
        role=role,
        manifest_profile_sha256=ref.manifest_profile_sha256,
    )


def _input_envelope_refs(
    refs: Mapping[str, UncertaintyEnvelopeRef],
) -> tuple[InputRef, ...]:
    """Bind each selected uncertainty envelope to its semantic parameter name."""
    return tuple(
        _input_ref(ref, role=f"input_envelope.{name}") for name, ref in sorted(refs.items())
    )


def _persist_json_payload(
    ctx: ExecutionContext,
    *,
    payload: Mapping[str, Any],
    kind: str,
    schema_name: str,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    schema_version = payload.get("schema_version", "1.0")
    if not isinstance(schema_version, str) or not schema_version.strip():
        raise ValueError("persisted welfare payload must declare a non-empty schema_version")
    ref = ctx.store.put_json(
        dict(payload),
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version=schema_version),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ArtifactRefModel.model_validate(ref.model_dump())


def _extract_std(env: UncertaintyEnvelope) -> float:
    try:
        return _extract_typed_std(env)
    except (OverflowError, TypeError, ValueError) as exc:
        param_name = env.metadata.get("param_name")
        raise _fail_error(
            _ERROR_WELFARE_UNCERTAINTY_SCALE_INVALID,
            "Welfare input uncertainty does not declare a usable scale",
            details={
                "param_name": param_name if isinstance(param_name, str) else "unknown",
                "reason": str(exc),
            },
        ) from exc


def _mul_interval(
    a_lower: float, a_upper: float, b_lower: float, b_upper: float
) -> tuple[float, float]:
    candidates = (
        a_lower * b_lower,
        a_lower * b_upper,
        a_upper * b_lower,
        a_upper * b_upper,
    )
    return min(candidates), max(candidates)


def _matvec_interval(
    matrix_lower: np.ndarray,
    matrix_upper: np.ndarray,
    vector_lower: np.ndarray,
    vector_upper: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    rows, cols = matrix_lower.shape
    out_lower = np.zeros(rows, dtype=np.float64)
    out_upper = np.zeros(rows, dtype=np.float64)
    for row_idx in range(rows):
        total_lower = 0.0
        total_upper = 0.0
        for col_idx in range(cols):
            item_lower, item_upper = _mul_interval(
                float(matrix_lower[row_idx, col_idx]),
                float(matrix_upper[row_idx, col_idx]),
                float(vector_lower[col_idx]),
                float(vector_upper[col_idx]),
            )
            total_lower += item_lower
            total_upper += item_upper
        out_lower[row_idx] = total_lower
        out_upper[row_idx] = total_upper
    return out_lower, out_upper


def _dot_interval(weights: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> tuple[float, float]:
    total_lower = 0.0
    total_upper = 0.0
    for weight, lo, hi in zip(weights, lower, upper, strict=True):
        contrib_lower, contrib_upper = _mul_interval(
            float(weight),
            float(weight),
            float(lo),
            float(hi),
        )
        total_lower += contrib_lower
        total_upper += contrib_upper
    return total_lower, total_upper


def _fail_error(
    code: str,
    message: str,
    *,
    details: Mapping[str, Any] | None = None,
) -> _WelfareNodeFailure:
    return _WelfareNodeFailure(NodeError(code=code, message=message, details=dict(details or {})))
