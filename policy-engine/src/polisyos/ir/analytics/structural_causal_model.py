"""Describe serializable SCM graph-plus-mechanism contracts and persistence helpers."""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import ArtifactRefModel, StructuralCausalModelSpecRef

if TYPE_CHECKING:
    from polisyos.ir.analytics.causal_graph import CausalGraphModel
else:
    from polisyos.ir.analytics.causal_graph import CausalGraphModel


def _normalize_json_value(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _normalize_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_json_value(item) for item in value]
    return value


def _ensure_json_serializable(field_name: str, value: Any) -> Any:
    normalized = _normalize_json_value(value)
    try:
        json.dumps(normalized, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be JSON-serializable: {exc}") from exc
    return normalized


class MechanismFamily(str, Enum):
    """Allowed mechanism families for SCM node equations."""

    LINEAR = "linear"
    ADDITIVE_NOISE = "additive_noise"
    POST_NONLINEAR = "post_nonlinear"
    CLASSIFIER = "classifier"
    EMPIRICAL = "empirical"
    PARAMETRIC_PRIOR = "parametric_prior"


class MechanismSource(str, Enum):
    """Where a node mechanism was sourced from."""

    DATA_FITTED = "data_fitted"
    LITERATURE_PRIOR = "literature_prior"
    HYBRID = "hybrid"
    DEFAULT = "default"


def _payload_digest(value: Any) -> str:
    """Hash the finite JSON basis used by the selected worker protocol."""
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


class SCMTrainingRows(BaseModel):
    """Content-bound aligned observational rows retained for complete refits.

    Hash reconciliation checks content; the parent CAS resolver establishes
    source custody. Neither establishes the iid law or causal identification.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    rows: list[list[float]]
    columns: list[str]
    row_ids: list[str]
    source_ref: ArtifactRefModel
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    data_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    row_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    graph_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    graph_payload: dict[str, Any]
    fit_input: dict[str, Any]

    @model_validator(mode="after")
    def _validate_basis(self) -> SCMTrainingRows:
        data = np.asarray(self.rows, dtype=float)
        if data.ndim != 2 or len(data) < 2 or not np.isfinite(data).all():
            raise ValueError("training rows require a finite two-dimensional matrix")
        if data.shape[1] != len(self.columns) or len(set(self.columns)) != len(self.columns):
            raise ValueError("training columns must uniquely identify the matrix columns")
        expected_ids = [f"{self.source_ref.artifact_id}:{i}" for i in range(len(data))]
        if self.row_ids != expected_ids:
            raise ValueError("training row IDs must bind exact ordered source artifact rows")
        if self.data_sha256 != _payload_digest({"columns": self.columns, "rows": self.rows}):
            raise ValueError("training matrix content hash mismatch")
        if self.row_sha256 != _payload_digest(self.row_ids):
            raise ValueError("training row identity hash mismatch")
        if self.graph_sha256 != _payload_digest(self.graph_payload):
            raise ValueError("training graph content hash mismatch")
        if (
            self.fit_input.get("data") != self.rows
            or self.fit_input.get("column_names") != self.columns
        ):
            raise ValueError(
                "retained fit input must contain the exact training matrix and columns"
            )
        return self


class SCMFitProvenance(BaseModel):
    """Observed selected-worker identities for an actual GCM mechanism fit."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    profile: Literal["dowhy-014"] = "dowhy-014"
    fit_function: Literal["dowhy.gcm.fit"] = "dowhy.gcm.fit"
    python: str = Field(pattern=r"^3\.12\.\d+$")
    versions: dict[str, str]
    seed: int
    request_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    worker_code_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    worker_lock_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    worker_response: dict[str, Any]
    resample_indices: list[int] | None = None

    @model_validator(mode="after")
    def _validate_backend(self) -> SCMFitProvenance:
        if self.versions.get("dowhy") != "0.14":
            raise ValueError("GCM fit provenance requires the selected DoWhy 0.14 profile")
        return self


class NodeMechanism(BaseModel):
    """Structural equation metadata for one variable in an SCM."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    variable: str
    parents: list[str] = Field(default_factory=list)
    family: MechanismFamily
    family_params: dict[str, Any] = Field(default_factory=dict)
    noise_distribution: str = "empirical"
    source: MechanismSource = MechanismSource.DATA_FITTED
    literature_prior: dict[str, Any] | None = None
    sensitivity_to_latent: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="before")
    @classmethod
    def _normalize_payload(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        payload["family_params"] = _ensure_json_serializable(
            "family_params",
            payload.get("family_params", {}),
        )
        prior = payload.get("literature_prior")
        if prior is not None:
            payload["literature_prior"] = _ensure_json_serializable("literature_prior", prior)
        return payload

    @model_validator(mode="after")
    def _validate_json_only(self) -> NodeMechanism:
        _ensure_json_serializable("family_params", self.family_params)
        if self.literature_prior is not None:
            _ensure_json_serializable("literature_prior", self.literature_prior)
        return self


class StructuralCausalModelSpec(BaseModel):
    """Serializable structural causal model with graph and node mechanisms."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.1"
    graph: CausalGraphModel
    mechanisms: list[NodeMechanism] = Field(default_factory=list)
    fitted: bool = False
    fit_method: Literal["auto", "manual", "gcm", "hybrid", "native_hybrid"] | None = None
    fit_metrics: dict[str, float] = Field(default_factory=dict)
    mechanism_source_summary: dict[str, int] = Field(default_factory=dict)
    skg_snapshot_ref: str | None = None
    training_rows: SCMTrainingRows | None = None
    fit_provenance: SCMFitProvenance | None = None

    @model_validator(mode="after")
    def _validate_mechanisms_cover_graph(self) -> StructuralCausalModelSpec:
        mech_vars = {m.variable for m in self.mechanisms}
        graph_vars = set(self.graph.nodes)

        unknown_mechanisms = sorted(mech_vars - graph_vars)
        if unknown_mechanisms:
            raise ValueError(f"Mechanisms reference unknown variables: {unknown_mechanisms}")

        missing = graph_vars - mech_vars
        non_roots = {edge.dst for edge in self.graph.edges}
        missing_non_roots = sorted(missing & non_roots)
        if missing_non_roots:
            raise ValueError(f"Non-root nodes without mechanisms: {missing_non_roots}")

        roots = graph_vars - non_roots
        invalid_root_carriers = sorted(
            mechanism.variable
            for mechanism in self.mechanisms
            if mechanism.variable in roots
            and "observed_samples" in mechanism.family_params
            and mechanism.family is not MechanismFamily.EMPIRICAL
        )
        if invalid_root_carriers:
            raise ValueError(
                f"Observed root samples require an EMPIRICAL mechanism: {invalid_root_carriers}"
            )
        root_carriers = [
            mechanism
            for mechanism in self.mechanisms
            if mechanism.variable in roots
            and not mechanism.parents
            and "observed_samples" in mechanism.family_params
        ]
        if root_carriers:
            carrier_lengths: set[int] = set()
            carrier_sources: set[str] = set()
            carrier_alignments: set[str] = set()
            carrier_groups: set[str] = set()
            for mechanism in root_carriers:
                params = mechanism.family_params
                samples = params.get("observed_samples")
                if (
                    not isinstance(samples, list)
                    or not samples
                    or not all(
                        isinstance(value, (int, float)) and np.isfinite(value) for value in samples
                    )
                ):
                    raise ValueError(
                        f"Observed root samples for '{mechanism.variable}' must be a "
                        "non-empty finite list"
                    )
                source = params.get("observed_samples_source")
                alignment = params.get("observed_sample_alignment")
                group = params.get("joint_sample_group")
                if not all(
                    isinstance(value, str) and value.strip() for value in (source, alignment, group)
                ):
                    raise ValueError(
                        f"Observed root carrier '{mechanism.variable}' requires "
                        "source, alignment, and joint group"
                    )
                carrier_lengths.add(len(samples))
                carrier_sources.add(source)
                carrier_alignments.add(alignment)
                carrier_groups.add(group)
            if len(carrier_lengths) != 1:
                raise ValueError("Observed root samples must share one row count")
            if (
                len(carrier_sources) != 1
                or len(carrier_alignments) != 1
                or len(carrier_groups) != 1
            ):
                raise ValueError("Observed root carriers must share provenance and alignment")
        if self.schema_version == "1.1" and self.fit_method == "gcm":
            if self.training_rows is None or self.fit_provenance is None:
                raise ValueError(
                    "selected GCM fit requires training rows and observed worker provenance"
                )
        if self.training_rows is not None:
            rows = self.training_rows
            graph_payload = {
                "nodes": list(self.graph.nodes),
                "edges": [[edge.src, edge.dst] for edge in self.graph.edges],
            }
            if rows.graph_payload != graph_payload:
                raise ValueError("SCM graph differs from its bound training graph")
            indices = self.fit_provenance.resample_indices if self.fit_provenance else None
            if indices is not None and (
                len(indices) != len(rows.rows)
                or any(type(i) is not int or not 0 <= i < len(rows.rows) for i in indices)
            ):
                raise ValueError("bootstrap indices must resample the complete source row set")
            selected = indices if indices is not None else list(range(len(rows.rows)))
            selected_ids = [rows.row_ids[i] for i in selected]
            for mechanism in root_carriers:
                params = mechanism.family_params
                if params.get("observed_row_ids") != selected_ids:
                    raise ValueError(
                        "observed root rows do not share the bound source row identities"
                    )
                col = rows.columns.index(mechanism.variable)
                if params["observed_samples"] != [rows.rows[i][col] for i in selected]:
                    raise ValueError("observed root values differ from their source-bound rows")
        return self


def persist_structural_causal_model_spec(
    store: ArtifactStore,
    scm_spec: StructuralCausalModelSpec,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.structural_causal_model_spec",
    schema_version: str | None = None,
) -> StructuralCausalModelSpecRef:
    """Persist a structural causal model spec and return its typed artifact ref."""
    resolved_version = schema_version or scm_spec.schema_version
    if resolved_version != scm_spec.schema_version or resolved_version not in {"1.0", "1.1"}:
        raise ValueError("SCM payload and supported CAS schema versions must match")
    ref = put_json_artifact(
        store,
        scm_spec.model_dump(mode="json"),
        kind="ir.structural_causal_model_spec",
        schema_name=schema_name,
        schema_version=resolved_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return StructuralCausalModelSpecRef.model_validate(ref)


def load_structural_causal_model_spec(
    store: ArtifactStore,
    ref: StructuralCausalModelSpecRef,
) -> StructuralCausalModelSpec:
    """Load structural causal model spec."""
    payload = get_json_artifact(store, ref.artifact_id)
    manifest = store.get_manifest(ref.artifact_id)
    schema = getattr(manifest, "artifact_schema", None)
    if schema is None or schema.version not in {"1.0", "1.1"}:
        raise ValueError("SCM artifact requires a supported CAS schema manifest")
    if payload.get("schema_version", "1.0") != schema.version:
        raise ValueError("SCM payload and CAS schema versions differ")
    # Historical manifests without an explicit payload version remain 1.0.
    # The current constructor default must not upgrade their backend profile.
    return StructuralCausalModelSpec.model_validate(
        {**payload, "schema_version": payload.get("schema_version", "1.0")}
    )


__all__ = [
    "MechanismFamily",
    "MechanismSource",
    "NodeMechanism",
    "SCMFitProvenance",
    "SCMTrainingRows",
    "StructuralCausalModelSpec",
    "load_structural_causal_model_spec",
    "persist_structural_causal_model_spec",
]
