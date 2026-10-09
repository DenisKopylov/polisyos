"""Versioned posterior functionals that do not overload an uncertainty envelope.

The v1.1 summary keeps named point functionals, equal-tail bounds, and the
source draw rows as separate values. It is candidate evidence only: the
existing ``UncertaintyEnvelope`` schema and its consumers retain their current
point-within-interval contract.
"""

from __future__ import annotations

import base64
import math
from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.artifacts import (
    ArtifactStore,
    InputRef,
    get_json_artifact,
    put_json_artifact,
)
from polisyos.ir.model_layer.canon import CanonSpec, content_hash, to_canonical_bytes
from polisyos.ir.registry.refs import ArtifactRefModel

POSTERIOR_SUMMARY_PROFILE_ID = "urn:policyos:ir:bayesian-posterior-summary-profile:1"
POSTERIOR_SUMMARY_PROFILE_VERSION = "1.1"
POSTERIOR_DRAWS_SCHEMA = "foundry.bayesian.draws.v1"


def _inverse_empirical_cdf(
    ordered_values: np.ndarray,
    cumulative_probabilities: np.ndarray,
    level: float,
    *,
    maximum_index: int,
) -> float:
    """Evaluate a left-continuous empirical inverse CDF over source draws."""
    index = min(
        int(np.searchsorted(cumulative_probabilities, level, side="left")),
        maximum_index,
    )
    return float(ordered_values[index])


class PosteriorPointRole(StrEnum):
    """Name the posterior point functional selected by a consumer."""

    POSTERIOR_MEAN = "posterior_mean"
    POSTERIOR_MEDIAN = "posterior_median"


class PosteriorSummaryRef(ArtifactRefModel):
    """Reference a v1.1 posterior summary artifact."""

    kind: Literal["ir.posterior_summary"] = "ir.posterior_summary"
    media_type: Literal["application/json"] = "application/json"


class PosteriorParameterSummary(BaseModel):
    """Retain one scalar parameter's exact draws and separate functionals."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_parameter: str = Field(min_length=1)
    source_coordinate: tuple[int, ...] = ()
    draws: tuple[float, ...] = Field(min_length=1)
    posterior_mean: float
    posterior_median: float
    equal_tail_interval: tuple[float, float]
    selected_point: float

    @model_validator(mode="after")
    def _validate_statistics(self) -> PosteriorParameterSummary:
        values = (
            *self.draws,
            self.posterior_mean,
            self.posterior_median,
            *self.equal_tail_interval,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("posterior summary values must be finite")
        if self.equal_tail_interval[0] > self.equal_tail_interval[1]:
            raise ValueError("posterior equal-tail interval must be ordered")
        if not math.isfinite(self.selected_point):
            raise ValueError("selected posterior point must be finite")
        return self


class PosteriorSummaryV11(BaseModel):
    """Store versioned posterior functionals without envelope coercion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.1"] = "1.1"
    profile_id: Literal["urn:policyos:ir:bayesian-posterior-summary-profile:1"] = (
        POSTERIOR_SUMMARY_PROFILE_ID
    )
    profile_version: Literal["1.1"] = POSTERIOR_SUMMARY_PROFILE_VERSION
    point_role: PosteriorPointRole
    credible_mass: float = Field(gt=0.0, lt=1.0)
    source_draws_ref: str = Field(min_length=1)
    source_draws_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_draws_payload: dict[str, Any]
    source_method_evidence_ref: ArtifactRefModel | None = None
    chain_count: int = Field(ge=1)
    draws_per_chain: int = Field(ge=1)
    draw_order: tuple[int, ...] = Field(min_length=1)
    parameter_order: tuple[str, ...] = Field(min_length=1)
    parameters: dict[str, PosteriorParameterSummary]
    source_weights: tuple[float, ...] | None = None
    weight_status: Literal["not_supplied_by_source"] = "not_supplied_by_source"
    unit_bindings: dict[str, str] = Field(default_factory=dict)
    unit_binding_status: Literal["not_established"] = "not_established"
    gate_eligible: Literal[False] = False

    @model_validator(mode="after")
    def _validate_summary_identity(self) -> PosteriorSummaryV11:
        draw_count = self.chain_count * self.draws_per_chain
        if (
            self.source_weights is not None
            or self.draw_order != tuple(range(draw_count))
            or self.parameter_order != tuple(self.parameters)
            or set(self.unit_bindings) - set(self.parameter_order)
            or any(len(item.draws) != draw_count for item in self.parameters.values())
        ):
            raise ValueError("posterior summary source axes or declarations are inconsistent")
        return self

    def joint_row_values(self, parameter_names: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        """Return exact source rows for named parameters in producer order.

        Args:
            parameter_names: Parameter names whose aligned source draw values are requested.

        Returns:
            The exact row-ordered joint values, with no independently declared join identifier.

        Raises:
            ValueError: If names are empty, duplicated, or absent from this source artifact.
        """
        if not parameter_names or len(set(parameter_names)) != len(parameter_names):
            raise ValueError("posterior joint row selection requires distinct parameter names")
        missing = set(parameter_names) - set(self.parameters)
        if missing:
            raise ValueError(
                f"posterior joint row selection has unknown parameters: {sorted(missing)}"
            )
        return tuple(
            tuple(self.parameters[name].draws[row] for name in parameter_names)
            for row in self.draw_order
        )


def summarize_posterior_draw_artifact(
    *,
    artifact_ref: str,
    artifact_payload: Mapping[str, Any],
    artifact_hash: str,
    credible_mass: float,
    point_role: PosteriorPointRole,
    source_method_evidence_ref: ArtifactRefModel | None = None,
) -> PosteriorSummaryV11:
    """Recompute separate functionals from one hash-bound Bayesian draw artifact.

    Args:
        artifact_ref: Native content-addressed producer reference.
        artifact_payload: ``foundry.bayesian.draws.v1`` payload from that producer.
        artifact_hash: Producer-declared digest, independently recomputed here.
        credible_mass: Equal-tail interval mass in ``(0, 1)``.
        point_role: Explicitly selected named point functional.
        source_method_evidence_ref: Persisted method evidence that carries the draw payload.

    Returns:
        A candidate-only v1.1 summary retaining source order and all scalarized draws.

    Raises:
        ValueError: If source identity, axis layout, bytes, statistics, or selected functional
            cannot be recomputed without loss.
    """
    if not 0.0 < credible_mass < 1.0:
        raise ValueError("credible_mass must be in (0, 1)")
    expected_hash = content_hash(
        to_canonical_bytes(artifact_payload, CanonSpec(forbid_floats=False)),
        prefix=True,
    )
    expected_ref = f"artifact://foundry/bayesian/posterior/{expected_hash}"
    if artifact_hash != expected_hash or artifact_ref != expected_ref:
        raise ValueError("posterior draw reference does not content-bind to its payload")
    if (
        artifact_payload.get("schema") != POSTERIOR_DRAWS_SCHEMA
        or artifact_payload.get("stage") != "posterior"
        or artifact_payload.get("draw_layout")
        != {
            "axis_order": ["chain", "draw", "parameter"],
            "array_order": "C",
            "dtype": "<f8",
            "canonicalization_version": POSTERIOR_DRAWS_SCHEMA,
        }
    ):
        raise ValueError("posterior draw payload has an unsupported schema or axis layout")
    if "weights" in artifact_payload or "sample_weights" in artifact_payload:
        raise ValueError(
            "posterior draw source reports weights unsupported by this unweighted v1.1 profile"
        )
    raw_parameters = artifact_payload.get("parameters")
    if not isinstance(raw_parameters, Mapping) or not raw_parameters:
        raise ValueError("posterior draw payload has no parameter arrays")

    parameter_arrays: dict[str, np.ndarray] = {}
    shared_axis: tuple[int, int] | None = None
    for parameter_name, raw in sorted(raw_parameters.items()):
        if (
            not isinstance(parameter_name, str)
            or not parameter_name.strip()
            or not isinstance(raw, Mapping)
        ):
            raise ValueError("posterior parameter entry is malformed")
        raw_shape = raw.get("shape")
        if (
            not isinstance(raw_shape, list)
            or len(raw_shape) < 2
            or any(
                not isinstance(dim, int) or isinstance(dim, bool) or dim < 1 for dim in raw_shape
            )
            or raw.get("dtype") != "<f8"
        ):
            raise ValueError("posterior parameter shape or dtype is unsupported")
        shape = tuple(raw_shape)
        chain_draw_axis = (shape[0], shape[1])
        if shared_axis is None:
            shared_axis = chain_draw_axis
        elif chain_draw_axis != shared_axis:
            raise ValueError("posterior parameters do not share chain/draw axes")
        encoded = raw.get("data_base64")
        if not isinstance(encoded, str):
            raise ValueError("posterior parameter bytes are missing")
        try:
            data = base64.b64decode(encoded, validate=True)
            array = np.frombuffer(data, dtype=np.dtype("<f8"))
        except (ValueError, TypeError) as exc:
            raise ValueError("posterior parameter bytes are invalid") from exc
        if array.size != math.prod(shape):
            raise ValueError("posterior parameter byte count does not match its declared shape")
        array = array.reshape(shape, order="C")
        if not np.all(np.isfinite(array)):
            raise ValueError("posterior parameter draws must be finite")
        parameter_arrays[parameter_name] = array

    if shared_axis is None:
        raise ValueError("posterior draw axes are missing")
    chain_count, draws_per_chain = shared_axis
    draw_count = chain_count * draws_per_chain
    parameter_summaries: dict[str, PosteriorParameterSummary] = {}
    for source_name, array in parameter_arrays.items():
        coordinates = tuple(np.ndindex(array.shape[2:])) if array.ndim > 2 else ((),)
        for coordinate in coordinates:
            key = (
                source_name
                if not coordinate
                else f"{source_name}[{','.join(map(str, coordinate))}]"
            )
            selector = (slice(None), slice(None), *coordinate)
            draws = tuple(float(value) for value in array[selector].reshape(-1, order="C"))
            mean = math.fsum(draws) / draw_count
            if not math.isfinite(mean):
                raise ValueError("posterior arithmetic mean is outside finite float64 range")
            ordered = np.sort(np.asarray(draws, dtype=np.float64), kind="stable")
            cumulative = np.arange(1, draw_count + 1, dtype=np.float64) / draw_count
            alpha = (1.0 - credible_mass) / 2.0

            median = _inverse_empirical_cdf(
                ordered,
                cumulative,
                0.5,
                maximum_index=draw_count - 1,
            )
            interval = (
                _inverse_empirical_cdf(
                    ordered,
                    cumulative,
                    alpha,
                    maximum_index=draw_count - 1,
                ),
                _inverse_empirical_cdf(
                    ordered,
                    cumulative,
                    1.0 - alpha,
                    maximum_index=draw_count - 1,
                ),
            )
            selected_point = mean if point_role is PosteriorPointRole.POSTERIOR_MEAN else median
            parameter_summaries[key] = PosteriorParameterSummary(
                source_parameter=source_name,
                source_coordinate=coordinate,
                draws=draws,
                posterior_mean=mean,
                posterior_median=median,
                equal_tail_interval=interval,
                selected_point=selected_point,
            )

    return PosteriorSummaryV11(
        point_role=point_role,
        credible_mass=credible_mass,
        source_draws_ref=artifact_ref,
        source_draws_hash=expected_hash,
        source_draws_payload=dict(artifact_payload),
        source_method_evidence_ref=source_method_evidence_ref,
        chain_count=chain_count,
        draws_per_chain=draws_per_chain,
        draw_order=tuple(range(draw_count)),
        parameter_order=tuple(parameter_summaries),
        parameters=parameter_summaries,
        source_weights=None,
        unit_bindings={},
        unit_binding_status="not_established",
        gate_eligible=False,
    )


def persist_posterior_summary(
    store: ArtifactStore,
    summary: PosteriorSummaryV11,
    *,
    source_method_evidence_ref: ArtifactRefModel,
) -> PosteriorSummaryRef:
    """Persist a candidate summary with its exact selected evidence view as lineage."""
    bound_summary = summary.model_copy(
        update={
            "source_method_evidence_ref": ArtifactRefModel.model_validate(
                source_method_evidence_ref.model_dump(mode="python")
            )
        }
    )
    ref = put_json_artifact(
        store,
        bound_summary.model_dump(mode="python", round_trip=True),
        kind="ir.posterior_summary",
        schema_name="ir.PosteriorSummaryV11",
        schema_version="1.1",
        inputs=[
            InputRef(
                artifact_id=source_method_evidence_ref.artifact_id,
                role="method_evidence",
                manifest_profile_sha256=source_method_evidence_ref.manifest_profile_sha256,
            )
        ],
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return PosteriorSummaryRef.model_validate(ref)


def load_posterior_summary(store: ArtifactStore, ref: PosteriorSummaryRef) -> PosteriorSummaryV11:
    """Load and recompute the v1.1 summary from its retained exact draw payload."""
    summary = PosteriorSummaryV11.model_validate(get_json_artifact(store, ref))
    recomputed = summarize_posterior_draw_artifact(
        artifact_ref=summary.source_draws_ref,
        artifact_payload=summary.source_draws_payload,
        artifact_hash=summary.source_draws_hash,
        credible_mass=summary.credible_mass,
        point_role=summary.point_role,
        source_method_evidence_ref=summary.source_method_evidence_ref,
    )
    if recomputed != summary:
        raise ValueError("persisted posterior summary does not match its source draw payload")
    return summary


__all__ = [
    "POSTERIOR_SUMMARY_PROFILE_ID",
    "POSTERIOR_SUMMARY_PROFILE_VERSION",
    "PosteriorParameterSummary",
    "PosteriorPointRole",
    "PosteriorSummaryRef",
    "PosteriorSummaryV11",
    "load_posterior_summary",
    "persist_posterior_summary",
    "summarize_posterior_draw_artifact",
]
