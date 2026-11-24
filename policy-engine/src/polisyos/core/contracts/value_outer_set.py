"""Canonical set-valued value contracts for policy-design runtime gates."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from typing import Annotated, Any, ClassVar, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    WithJsonSchema,
    computed_field,
    field_validator,
    model_validator,
)

ValueOuterSetRepresentation = Literal[
    "interval_box",
    "polytope_support_functions",
    "scenario_set",
    "unknown",
]
ValueOuterSetIdentificationStatus = Literal["point", "partial", "proxy", "blocked"]
ValueOuterSetAssumptionStatus = Literal[
    "declared",
    "externally_supported",
    "stress_tested",
    "violated",
    "out_of_scope",
]
ValueOuterSetRepresentationStatus = Literal["certified", "search_only", "unknown"]
ValueOuterSetComparison = Literal["dominates", "incomparable", "unknown"]
ValuePromotionDecisionGrade = Literal["blocked", "low", "medium", "high"]
ValuePromotionDecisionReason = Literal[
    "eligible",
    "historical_numerical_profile",
    "representation_not_certified",
    "assumption_violated",
    "identification_blocked",
    "data_trust_zero",
    "data_trust_below_l5_min_coverage",
    "data_trust_below_promotion_floor",
]

_EXACT_NUMERICAL_PROFILE = "policyos.value_outer_set.numeric.v2"
_HISTORICAL_READ_CONTEXT = object()


def _float_tuple_close(
    actual: tuple[float, ...],
    expected: tuple[float, ...],
    *,
    atol: float = 1e-9,
) -> bool:
    if len(actual) != len(expected):
        return False
    return all(
        abs(float(left) - float(right)) <= atol
        for left, right in zip(actual, expected, strict=True)
    )


def _coerce_interval_values(value: Any) -> tuple[float, ...]:
    if value is None:
        items: tuple[Any, ...] = ()
    elif isinstance(value, tuple):
        items = value
    elif isinstance(value, list):
        items = tuple(value)
    else:
        items = (value,)
    values = tuple(float(item) for item in items)
    if any(not math.isfinite(item) for item in values):
        raise ValueError("value_outer_set_bounds_non_finite")
    return values


def _derive_interval_widths(
    lower: tuple[float, ...],
    upper: tuple[float, ...],
    *,
    historical: bool = False,
) -> tuple[float, ...]:
    if historical:
        return tuple(max(0.0, round(hi - lo, 12)) for lo, hi in zip(lower, upper, strict=True))
    widths = tuple(hi - lo for lo, hi in zip(lower, upper, strict=True))
    if any(not math.isfinite(width) for width in widths):
        raise ValueError("value_outer_set_width_non_finite")
    return widths


class DataTrust(BaseModel):
    """L5 trust-tier content used by value promotion and substrate registration."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    tier: str = Field(min_length=1)
    trust_cap: float = Field(ge=0.0, le=1.0)
    trust_multiplier: float = Field(ge=0.0, le=1.0)
    min_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    max_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    promotion_floor: float | None = Field(default=None, ge=0.0, le=1.0)
    authority_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_coverage_range(self) -> DataTrust:
        if (
            self.min_coverage is not None
            and self.max_coverage is not None
            and self.min_coverage > self.max_coverage
        ):
            raise ValueError("min_coverage must be <= max_coverage")
        return self

    @property
    def effective_score(self) -> float:
        """Return the content-derived promotion score capped by L5 trust numbers."""

        return min(self.trust_cap, self.trust_multiplier)

    @property
    def resolved_promotion_floor(self) -> float:
        """Return the L5-derived promotion floor for this trust content."""

        if self.promotion_floor is not None:
            return self.promotion_floor
        if self.min_coverage is not None and self.min_coverage > 0.0:
            return self.min_coverage
        return 0.0


class ValuePromotionDecision(BaseModel):
    """Content-bound decision for whether a value set can mint promotion value."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    promotable: bool
    capped_decision_grade: ValuePromotionDecisionGrade
    reasons: tuple[ValuePromotionDecisionReason, ...]
    representation_status: ValueOuterSetRepresentationStatus
    identification_status: ValueOuterSetIdentificationStatus
    data_trust_tier: str
    trust_cap: float = Field(ge=0.0, le=1.0)
    trust_multiplier: float = Field(ge=0.0, le=1.0)
    trust_score: float = Field(ge=0.0, le=1.0)
    trust_floor: float = Field(ge=0.0, le=1.0)
    min_coverage: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_reasons(self) -> ValuePromotionDecision:
        if self.promotable and self.capped_decision_grade == "blocked":
            raise ValueError("promotable decision cannot use blocked grade")
        if not self.promotable and self.reasons == ("eligible",):
            raise ValueError("non-promotable decision requires blocking reasons")
        return self


class ValueOuterSet(BaseModel):
    """Canonical typed carrier for set-valued value over policy-design worlds.

    Optional statistical endpoints preserve an estimator's reported uncertainty
    separately from the identification set. They are descriptive evidence only:
    identification, comparison, and promotion continue to use ``lower`` and
    ``upper``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    CURRENT_NUMERICAL_PROFILE: ClassVar[Literal["policyos.value_outer_set.numeric.v2"]] = (
        _EXACT_NUMERICAL_PROFILE
    )

    representation: ValueOuterSetRepresentation
    lower: tuple[float, ...] = Field(default_factory=tuple)
    upper: tuple[float, ...] = Field(default_factory=tuple)
    statistical_lower: tuple[float, ...] | None = Field(
        default=None,
        description=(
            "Source-reported statistical interval lower endpoints, separate from "
            "identification bounds and not used to authorize promotion."
        ),
    )
    statistical_upper: tuple[float, ...] | None = Field(
        default=None,
        description=(
            "Source-reported statistical interval upper endpoints, separate from "
            "identification bounds and not used to authorize promotion."
        ),
    )
    coordinates: tuple[str, ...] = Field(default_factory=tuple)
    identification_status: ValueOuterSetIdentificationStatus
    assumptions: tuple[str, ...] = Field(default_factory=tuple)
    assumption_status: ValueOuterSetAssumptionStatus
    calibration_scope: dict[str, str] = Field(default_factory=dict)
    data_trust: DataTrust
    world_model_record_ref: str = Field(min_length=1)
    epoch: str = Field(min_length=1)
    representation_status: ValueOuterSetRepresentationStatus
    solver_time_budget_ms: int | None = Field(default=None, ge=0)
    # An absent field is the original, unversioned historical wire. Only the
    # historical reader may construct that profile; live values use v2.
    numerical_profile: Annotated[
        Literal["policyos.value_outer_set.numeric.v2"] | None,
        WithJsonSchema({"const": _EXACT_NUMERICAL_PROFILE, "type": "string"}),
    ] = Field(
        default_factory=lambda: None,
        exclude_if=lambda value: value is None,
    )

    _POINT_WIDTH_TOLERANCE: ClassVar[float] = 1e-9
    _PROXY_WIDTH_TOLERANCE: ClassVar[float] = 1e-9
    _STATUS_BY_L5_MODE: ClassVar[dict[str, ValueOuterSetIdentificationStatus]] = {
        "point_identified": "point",
        "point": "point",
        "partially_identified": "partial",
        "partial_identified": "partial",
        "partial": "partial",
        "proxy_identified": "proxy",
        "proxy": "proxy",
        "unidentified": "blocked",
        "blocked": "blocked",
        "unknown": "blocked",
    }

    @field_validator("lower", "upper", "coordinates", "assumptions", mode="before")
    @classmethod
    def _coerce_tuple(cls, value: Any, info: ValidationInfo) -> tuple[Any, ...]:
        if value is None:
            return ()
        if isinstance(value, tuple):
            items = value
        elif isinstance(value, list):
            items = tuple(value)
        else:
            items = (value,)
        if info.field_name in {"lower", "upper"}:
            return _coerce_interval_values(items)
        return tuple(str(item) for item in items)

    @field_validator("statistical_lower", "statistical_upper", mode="before")
    @classmethod
    def _coerce_optional_statistical_interval(
        cls,
        value: Any,
    ) -> tuple[float, ...] | None:
        if value is None:
            return None
        return _coerce_interval_values(value)

    @field_validator("assumptions")
    @classmethod
    def _sort_assumptions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(value))

    @model_validator(mode="before")
    @classmethod
    def _accept_only_derived_width(cls, data: Any, info: ValidationInfo) -> Any:
        if not isinstance(data, Mapping):
            return data
        if "width" in data:
            raise ValueError("value_outer_set_width_supplied_not_derived")
        if "numerical_profile" not in data:
            return {**data, "numerical_profile": _EXACT_NUMERICAL_PROFILE}
        if data["numerical_profile"] is None and info.context is not _HISTORICAL_READ_CONTEXT:
            raise ValueError("value_outer_set_historical_profile_read_only")
        return data

    @classmethod
    def from_persisted_payload(
        cls,
        payload: Mapping[str, Any] | str | bytes | bytearray,
        *,
        expected_numerical_profile: Literal["historical", "policyos.value_outer_set.numeric.v2"]
        | None = None,
    ) -> ValueOuterSet:
        """Verify and load a persisted value set through the canonical boundary.

        Persisted serializers include the derived ``width`` as an integrity
        checksum. This boundary verifies that checksum exactly, discards it,
        and returns the model constructed through the ordinary derivation path.
        Live callers remain unable to supply ``width`` to normal validation.
        An enclosing artifact owner can bind the expected profile to its selected
        manifest. Without that binding an unversioned wire is historical only.
        """

        decoded: Any = payload
        if isinstance(decoded, (bytes, bytearray)):
            decoded = bytes(decoded).decode("utf-8")
        if isinstance(decoded, str):
            decoded = json.loads(decoded)
        if not isinstance(decoded, Mapping):
            raise ValueError("value_outer_set_persisted_payload_not_mapping")
        historical = "numerical_profile" not in decoded
        if not historical and decoded["numerical_profile"] != _EXACT_NUMERICAL_PROFILE:
            raise ValueError("value_outer_set_numerical_profile_invalid")
        actual_profile = "historical" if historical else _EXACT_NUMERICAL_PROFILE
        if expected_numerical_profile is not None and actual_profile != expected_numerical_profile:
            raise ValueError("value_outer_set_numerical_profile_mismatch")
        if "width" not in decoded:
            raise ValueError("value_outer_set_persisted_width_missing")

        persisted_width_raw = decoded["width"]
        if not isinstance(persisted_width_raw, (list, tuple)):
            raise ValueError("value_outer_set_width_tampered")
        persisted_width_items = tuple(persisted_width_raw)
        if historical:
            # Keep the original width wire's coercion for historical replay.
            try:
                if any(isinstance(value, bool) for value in persisted_width_items):
                    raise ValueError
                persisted_width = tuple(float(value) for value in persisted_width_items)
                if any(not math.isfinite(value) for value in persisted_width):
                    raise ValueError
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("value_outer_set_width_tampered") from exc
        else:
            # Compare the original JSON numbers. Casting an integer first would
            # silently round values outside binary64's exact integer range.
            if any(type(value) not in (int, float) for value in persisted_width_items):
                raise ValueError("value_outer_set_width_tampered")
            persisted_width = persisted_width_items

        try:
            persisted_lower = _coerce_interval_values(decoded.get("lower"))
            persisted_upper = _coerce_interval_values(decoded.get("upper"))
            expected_width = _derive_interval_widths(
                persisted_lower,
                persisted_upper,
                historical=historical,
            )
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("value_outer_set_persisted_bounds_invalid") from exc
        if persisted_width != expected_width:
            raise ValueError("value_outer_set_width_tampered")

        model_payload = dict(decoded)
        model_payload.pop("width")
        if historical:
            model_payload["numerical_profile"] = None
        return cls.model_validate(
            model_payload,
            context=_HISTORICAL_READ_CONTEXT if historical else None,
        )

    @classmethod
    def from_historical_fields(cls, payload: Mapping[str, Any]) -> ValueOuterSet:
        """Read the old fields inside an independently verified historical wire.

        Some historical enclosing schemas omitted the computed width. Their
        owner must verify the enclosing artifact; this method cannot verify a
        width checksum that the historical schema did not serialize.
        """
        if not isinstance(payload, Mapping):
            raise ValueError("value_outer_set_historical_fields_not_mapping")
        if "width" in payload or "numerical_profile" in payload:
            raise ValueError("value_outer_set_historical_fields_unexpected_profile")
        return cls.model_validate(
            {**payload, "numerical_profile": None},
            context=_HISTORICAL_READ_CONTEXT,
        )

    @classmethod
    def identification_status_for_l5_mode(
        cls,
        identification_mode: str,
    ) -> ValueOuterSetIdentificationStatus:
        """Map an L5 identification mode to the generic value-set status."""

        mode = identification_mode.strip().lower()
        try:
            return cls._STATUS_BY_L5_MODE[mode]
        except KeyError as exc:
            raise ValueError(f"l5_identification_mode_unresolved:{identification_mode}") from exc

    @classmethod
    def interval_box(
        cls,
        *,
        coordinates: tuple[str, ...],
        lower: tuple[float, ...],
        upper: tuple[float, ...],
        statistical_lower: tuple[float, ...] | None = None,
        statistical_upper: tuple[float, ...] | None = None,
        identification_mode: str,
        assumptions: tuple[str, ...],
        assumption_status: ValueOuterSetAssumptionStatus,
        calibration_scope: dict[str, str],
        data_trust: DataTrust,
        world_model_record_ref: str,
        epoch: str,
        representation_status: ValueOuterSetRepresentationStatus,
    ) -> ValueOuterSet:
        """Build an implemented interval-box value set from an L5 mode."""

        return cls(
            representation="interval_box",
            coordinates=coordinates,
            lower=lower,
            upper=upper,
            statistical_lower=statistical_lower,
            statistical_upper=statistical_upper,
            identification_status=cls.identification_status_for_l5_mode(identification_mode),
            assumptions=assumptions,
            assumption_status=assumption_status,
            calibration_scope=calibration_scope,
            data_trust=data_trust,
            world_model_record_ref=world_model_record_ref,
            epoch=epoch,
            representation_status=representation_status,
        )

    @model_validator(mode="after")
    def _validate_outer_set(self) -> ValueOuterSet:
        if self.representation != "interval_box":
            if (
                self.lower
                or self.upper
                or self.statistical_lower is not None
                or self.statistical_upper is not None
                or self.coordinates
            ):
                raise ValueError("non_interval_representation_payload_unimplemented")
            return self
        if not self.lower or not self.upper or not self.coordinates:
            raise ValueError("interval_box requires lower, upper, and coordinates")
        if len(self.lower) != len(self.upper) or len(self.lower) != len(self.coordinates):
            raise ValueError("interval_box lower, upper, and coordinates must align")
        if any(lo > hi for lo, hi in zip(self.lower, self.upper, strict=True)):
            raise ValueError("interval_box lower must be <= upper for every coordinate")
        if (self.statistical_lower is None) != (self.statistical_upper is None):
            raise ValueError("statistical_bounds_must_be_supplied_together")
        if self.statistical_lower is not None and self.statistical_upper is not None:
            if len(self.statistical_lower) != len(self.coordinates) or len(
                self.statistical_upper
            ) != len(self.coordinates):
                raise ValueError("statistical_bounds_must_align_with_coordinates")
            if any(
                lo > hi
                for lo, hi in zip(
                    self.statistical_lower,
                    self.statistical_upper,
                    strict=True,
                )
            ):
                raise ValueError("statistical_interval_lower_must_be_lte_upper")
        widths = self.width
        point_is_nonzero = (
            any(width > self._POINT_WIDTH_TOLERANCE for width in widths)
            if self.numerical_profile is None
            else any(lo != hi for lo, hi in zip(self.lower, self.upper, strict=True))
        )
        if self.identification_status == "point" and point_is_nonzero:
            raise ValueError("point_identified_requires_tight_interval")
        proxy_has_width = any(
            width > (self._PROXY_WIDTH_TOLERANCE if self.numerical_profile is None else 0.0)
            for width in widths
        )
        if self.identification_status == "proxy" and not proxy_has_width:
            raise ValueError("bounded_identification_requires_nonzero_interval")
        return self

    @computed_field(return_type=tuple[float, ...])
    @property
    def width(self) -> tuple[float, ...]:
        """Return derived interval widths per coordinate."""

        return _derive_interval_widths(
            self.lower,
            self.upper,
            historical=self.numerical_profile is None,
        )

    def promotion_decision(self) -> ValuePromotionDecision:
        """Return the single content-bound promotion decision for this value set.

        GY-N8/GY-N9 are the future production value-minting consumers. Until those
        tasks land, this decision object is the only live promotability API and is
        exercised by the substrate contract validator.
        """

        trust_score = self.data_trust.effective_score
        trust_floor = self.data_trust.resolved_promotion_floor
        reasons: list[ValuePromotionDecisionReason] = []
        if self.numerical_profile is None:
            reasons.append("historical_numerical_profile")
        if self.representation_status != "certified":
            reasons.append("representation_not_certified")
        if self.assumption_status == "violated":
            reasons.append("assumption_violated")
        if self.identification_status == "blocked":
            reasons.append("identification_blocked")
        if trust_score <= 0.0:
            reasons.append("data_trust_zero")
        if (
            self.data_trust.min_coverage is not None
            and self.data_trust.trust_cap < self.data_trust.min_coverage
        ):
            reasons.append("data_trust_below_l5_min_coverage")
        if trust_score < trust_floor:
            reasons.append("data_trust_below_promotion_floor")

        if reasons:
            return ValuePromotionDecision(
                promotable=False,
                capped_decision_grade="blocked",
                reasons=tuple(dict.fromkeys(reasons)),
                data_trust_tier=self.data_trust.tier,
                trust_cap=self.data_trust.trust_cap,
                trust_multiplier=self.data_trust.trust_multiplier,
                trust_score=trust_score,
                trust_floor=trust_floor,
                representation_status=self.representation_status,
                identification_status=self.identification_status,
                min_coverage=self.data_trust.min_coverage,
            )

        return ValuePromotionDecision(
            promotable=True,
            capped_decision_grade=self._promotion_grade(trust_score, trust_floor),
            reasons=("eligible",),
            data_trust_tier=self.data_trust.tier,
            trust_cap=self.data_trust.trust_cap,
            trust_multiplier=self.data_trust.trust_multiplier,
            trust_score=trust_score,
            trust_floor=trust_floor,
            representation_status=self.representation_status,
            identification_status=self.identification_status,
            min_coverage=self.data_trust.min_coverage,
        )

    @staticmethod
    def _promotion_grade(trust_score: float, trust_floor: float) -> ValuePromotionDecisionGrade:
        usable_span = max(1.0 - trust_floor, 1e-12)
        normalized = max(0.0, min((trust_score - trust_floor) / usable_span, 1.0))
        if normalized >= 0.8:
            return "high"
        if normalized >= 0.5:
            return "medium"
        return "low"

    def compare(
        self,
        other: ValueOuterSet,
        *,
        timeout_ms: int | None = None,
        force_timeout: bool = False,
    ) -> ValueOuterSetComparison:
        """Compare interval boxes with a conservative marginal fallback."""

        if force_timeout or timeout_ms == 0:
            return "unknown"
        if self.representation != "interval_box" or other.representation != "interval_box":
            return "unknown"
        if self.coordinates != other.coordinates:
            return "unknown"
        if len(self.lower) != len(other.lower):
            return "unknown"
        if all(lo >= hi for lo, hi in zip(self.lower, other.upper, strict=True)) and any(
            lo > hi for lo, hi in zip(self.lower, other.upper, strict=True)
        ):
            return "dominates"
        return "incomparable"

    def canonical_payload(self) -> dict[str, Any]:
        """Return a stable JSON-compatible payload for content addressing."""

        def canonical_float(value: float) -> str:
            if self.numerical_profile is None:
                return f"{value:.12g}"
            # 17 significant digits preserve every distinct finite float.
            # Both signed zeroes compare equal and therefore share an identity.
            return "0" if value == 0.0 else f"{value:.17g}"

        payload = {
            "representation": self.representation,
            "lower": [canonical_float(value) for value in self.lower],
            "upper": [canonical_float(value) for value in self.upper],
            "coordinates": list(self.coordinates),
            "identification_status": self.identification_status,
            "assumptions": list(self.assumptions),
            "assumption_status": self.assumption_status,
            "calibration_scope": self.calibration_scope,
            "data_trust": self.data_trust.model_dump(mode="json"),
            "world_model_record_ref": self.world_model_record_ref,
            "width": [canonical_float(value) for value in self.width],
            "epoch": self.epoch,
            "representation_status": self.representation_status,
        }
        if self.numerical_profile is not None:
            payload["numerical_profile"] = self.numerical_profile
        if self.statistical_lower is not None and self.statistical_upper is not None:
            payload["statistical_lower"] = [
                canonical_float(value) for value in self.statistical_lower
            ]
            payload["statistical_upper"] = [
                canonical_float(value) for value in self.statistical_upper
            ]
        return payload

    def __hash__(self) -> int:
        payload = json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        value = int.from_bytes(digest[:8], byteorder="big", signed=False)
        return value if value < 2**63 else value - 2**64

    def tree_flatten(self) -> tuple[tuple[()], tuple[str]]:
        """Expose this Pydantic model as static metadata in JAX pytrees."""

        payload = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        return (), (payload,)

    @classmethod
    def tree_unflatten(cls, aux_data: tuple[str], children: tuple[()]) -> ValueOuterSet:
        """Rebuild a static JAX pytree node."""

        _ = children
        return cls.from_persisted_payload(aux_data[0])


try:  # pragma: no cover - optional when JAX is unavailable in doc tooling.
    import jax.tree_util as _jax_tree_util

    _jax_tree_util.register_pytree_node_class(ValueOuterSet)
except Exception:  # pragma: no cover
    _jax_tree_util = None


__all__ = [
    "DataTrust",
    "ValueOuterSet",
    "ValueOuterSetAssumptionStatus",
    "ValueOuterSetComparison",
    "ValueOuterSetIdentificationStatus",
    "ValueOuterSetRepresentation",
    "ValueOuterSetRepresentationStatus",
    "ValuePromotionDecision",
    "ValuePromotionDecisionGrade",
    "ValuePromotionDecisionReason",
]
