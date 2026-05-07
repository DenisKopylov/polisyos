"""Shared persisted dependence primitive for Phase 1 consumers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import ConfigDict, Field

from polisyos.ir.kernel.base import KernelModel

if TYPE_CHECKING:
    from polisyos.ir.artifacts.contracts import ArtifactStore
    from polisyos.ir.artifacts.refs import InputRef
    from polisyos.ir.references import DependenceStructureRef


class DependenceStructure(KernelModel):
    """Canonical dependence artifact shared across econometrics, SAE, and spatial estimators."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    artifact_name: Literal["dependence_structure_v1.json"] = "dependence_structure_v1.json"
    regime: Literal["panel", "areal", "network_adjacent"]
    class_label: str
    calibrated: bool
    recommended_covariance: str
    metrics: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    source_method: str
    metadata: dict[str, Any] = Field(default_factory=dict)


def build_dependence_structure(
    *,
    regime: Literal["panel", "areal", "network_adjacent"],
    class_label: str,
    calibrated: bool,
    recommended_covariance: str,
    source_method: str,
    metrics: dict[str, float] | None = None,
    warnings: list[str] | None = None,
    blocking_reasons: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> DependenceStructure:
    """Build a dependence structure payload directly."""

    return DependenceStructure(
        regime=regime,
        class_label=str(class_label),
        calibrated=bool(calibrated),
        recommended_covariance=str(recommended_covariance),
        metrics=dict(metrics or {}),
        warnings=[str(item).strip() for item in warnings or () if str(item).strip()],
        blocking_reasons=[
            str(item).strip() for item in blocking_reasons or () if str(item).strip()
        ],
        source_method=str(source_method),
        metadata=dict(metadata or {}),
    )


def dependence_structure_from_econometrics(
    diagnostic: Any,
    *,
    source_method: str,
) -> DependenceStructure:
    """Normalize an econometrics dependence routing diagnostic into the shared primitive."""

    class_label = _enum_or_string(getattr(diagnostic, "class_label", None), default="inconclusive")
    recommended_covariance = _enum_or_string(
        getattr(diagnostic, "recommended_covariance", None),
        default="none",
    )
    estimator_status = _enum_or_string(
        getattr(diagnostic, "estimator_status", None), default="unsafe"
    )
    regime: Literal["panel", "areal", "network_adjacent"] = "panel"
    if class_label == "network_local":
        regime = "network_adjacent"
    elif class_label == "spatial_local":
        regime = "areal"

    evidence = dict(getattr(diagnostic, "evidence", {}) or {})
    tests = list(getattr(diagnostic, "tests", ()) or ())
    metrics: dict[str, float] = {}
    for key in ("factor_count", "alpha_hat"):
        value = getattr(diagnostic, key, None)
        if value is not None:
            metrics[key] = float(value)
    for key, value in evidence.items():
        if isinstance(value, bool):
            metrics[key] = 1.0 if value else 0.0
        elif isinstance(value, (int, float)):
            metrics[key] = float(value)
    warnings: list[str] = []
    blocking_reasons: list[str] = []
    calibrated = estimator_status in {"ok", "ok_conservative"}
    if estimator_status == "ok_conservative":
        warnings.append("dependence_requires_conservative_inference")
    elif estimator_status in {"reroute_required", "unsafe_for_default_inference"}:
        blocking_reasons.append(f"estimator_status:{estimator_status}")

    metadata = {
        "used_time_dummies": bool(getattr(diagnostic, "used_time_dummies", False)),
        "dependence_removed_by_time_effects": getattr(
            diagnostic, "dependence_removed_by_time_effects", None
        ),
        "shared_artifacts_ref": getattr(diagnostic, "shared_artifacts_ref", None),
        "tests": [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in tests
        ],
    }
    return build_dependence_structure(
        regime=regime,
        class_label=class_label,
        calibrated=calibrated,
        recommended_covariance=recommended_covariance,
        source_method=source_method,
        metrics=metrics,
        warnings=warnings,
        blocking_reasons=blocking_reasons,
        metadata=metadata,
    )


def dependence_structure_from_graph_diagnostic(
    diagnostic: Any,
    *,
    regime: Literal["areal", "network_adjacent"] = "areal",
    source_method: str,
) -> DependenceStructure:
    """Normalize graph-aware dependence diagnostics emitted by SAE/spatial lanes."""

    payload = (
        diagnostic.model_dump(mode="python")
        if hasattr(diagnostic, "model_dump")
        else dict(diagnostic)
    )
    decision = str(payload.get("decision", "fallback_independent") or "fallback_independent")
    identifiable = bool(payload.get("identifiable", False))
    class_label = str(payload.get("class_label", "inconclusive") or "inconclusive")
    selected_graph_id = payload.get("selected_graph_id")
    recommended_covariance = "network_hac" if regime == "network_adjacent" else "conley_spatial_hac"
    warnings: list[str] = []
    blocking_reasons: list[str] = []
    if not identifiable:
        blocking_reasons.append(f"decision:{decision}")
    elif decision != "identified":
        warnings.append(f"decision:{decision}")
    metrics: dict[str, float] = {}
    for key in (
        "moran_i",
        "geary_c",
        "moran_p_value",
        "geary_p_value",
        "pesaran_cd",
        "pesaran_cd_p_value",
        "lm_error",
        "lm_error_p_value",
        "lm_lag",
        "lm_lag_p_value",
        "profile_curvature",
        "information_eigen_min",
        "information_condition_number",
    ):
        value = payload.get(key)
        if value is not None:
            metrics[key] = float(value)
    return build_dependence_structure(
        regime=regime,
        class_label=class_label,
        calibrated=identifiable and decision == "identified",
        recommended_covariance=recommended_covariance,
        source_method=source_method,
        metrics=metrics,
        warnings=warnings,
        blocking_reasons=blocking_reasons,
        metadata={
            "selected_graph_id": selected_graph_id,
            "strength": payload.get("strength"),
            "fallback_reason": payload.get("fallback_reason"),
            "graph_diagnostics": payload.get("graph_diagnostics", ()),
        },
    )


def persist_dependence_structure(
    store: ArtifactStore,
    report: DependenceStructure,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.dependence_structure",
    schema_version: str = "1.0",
) -> DependenceStructureRef:
    """Persist a dependence structure artifact and return its typed ref."""

    from polisyos.ir.artifacts.io import put_json_artifact
    from polisyos.ir.canon import CanonSpec
    from polisyos.ir.references import DependenceStructureRef

    ref = put_json_artifact(
        store,
        report.model_dump(mode="json"),
        kind="ir.dependence_structure",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return DependenceStructureRef.model_validate(ref)


def load_dependence_structure(
    store: ArtifactStore,
    ref: DependenceStructureRef,
) -> DependenceStructure:
    """Load a persisted dependence structure."""

    from polisyos.ir.artifacts.io import get_json_artifact

    payload = get_json_artifact(store, ref.artifact_id)
    return DependenceStructure.model_validate(payload)


def _enum_or_string(value: Any, *, default: str) -> str:
    if value is None:
        return default
    resolved = getattr(value, "value", value)
    text = str(resolved).strip()
    return text or default


__all__ = [
    "DependenceStructure",
    "build_dependence_structure",
    "dependence_structure_from_econometrics",
    "dependence_structure_from_graph_diagnostic",
    "load_dependence_structure",
    "persist_dependence_structure",
]
