"""Effective mode ledger and serious-closeout policy helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from polisyos.core.contracts.control import (
    POLICY_AUTHORITY_PROFILES,
    POLICY_AUTHORITY_TO_FALLBACK_PROFILE,
    POLICY_AUTHORITY_TO_VALIDATION_PROFILE,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

EFFECTIVE_MODE_FIELDS = (
    "execution_profile",
    "validation_profile",
    "fallback_policy",
    "canary_kind",
    "matrix_lane_id",
    "provider_mode",
    "llm_simulation_mode",
    "fixture_identity",
    "mock_fallback_allowed",
    "mock_fallback_used",
    "data_mode",
    "state_store_backend",
    "local_control_waiver",
    "scorecard_warn_policy",
    "evidence_overlay_mode",
    "signed_exception_ref",
    "quarantine_status",
)

SERIOUS_EXECUTION_PROFILES = frozenset(
    (*POLICY_AUTHORITY_PROFILES, "serious")
)
SERIOUS_CANARY_KINDS = frozenset(
    {
        "deterministic_closeout",
        "governed",
        "governed_runtime",
        "production",
        "production_live",
        "research",
        "research_runtime",
        "serious_runtime",
    }
)

_NONE_VALUES = frozenset({"", "disabled", "false", "n/a", "none", "null", "off", "no"})
_NON_PRODUCTION_TOKENS = ("dev", "development", "fixture", "local", "mock", "smoke", "test")
_SERIOUS_LANE_TOKENS = ("closeout", "governed", "production", "research", "serious")
_SIMULATED_PROVIDER_TOKENS = ("fallback", "fixture", "mock", "offline", "simulat", "stub")
_SIMULATION_ENABLED_VALUES = frozenset(
    {"enabled", "fixture", "mock", "on", "simulated", "simulation", "true", "yes"}
)
_NON_PRODUCTION_DATA_TOKENS = (
    "dev",
    "fixture",
    "generated",
    "mock",
    "sample",
    "synthetic",
    "test",
)
_NON_SERIOUS_STATE_TOKENS = ("fixture", "in_memory", "local", "memory", "sqlite")
_WARN_ACCEPTED_VALUES = frozenset(
    {
        "accept_warn",
        "allow_warn",
        "warn_allowed",
        "warn_accepted",
        "warn_as_pass",
        "warning_allowed",
        "warnings_allowed",
    }
)
_OVERLAY_BLOCKED_TOKENS = ("bundle", "fixture", "generated", "overlay", "projection")
_QUARANTINE_BLOCKED_VALUES = frozenset(
    {"blocked", "legacy_quarantined", "quarantined", "required"}
)
_MOCK_ALLOWED_VALUES = frozenset({"allowed", "enabled", "true", "used", "yes"})

_FLAT_ALIASES: dict[str, tuple[str, ...]] = {
    "execution_profile": ("execution_profile",),
    "validation_profile": ("validation_profile", "governance_profile"),
    "fallback_policy": ("fallback_policy", "fallback_profile"),
    "canary_kind": ("canary_kind",),
    "matrix_lane_id": ("matrix_lane_id", "lane_id"),
    "provider_mode": ("provider_mode",),
    "llm_simulation_mode": ("llm_simulation_mode", "model_simulation_mode"),
    "fixture_identity": ("fixture_identity",),
    "mock_fallback_allowed": ("mock_fallback_allowed",),
    "mock_fallback_used": ("mock_fallback_used",),
    "data_mode": ("data_mode",),
    "state_store_backend": ("state_store_backend",),
    "local_control_waiver": ("local_control_waiver",),
    "scorecard_warn_policy": ("scorecard_warn_policy",),
    "evidence_overlay_mode": ("evidence_overlay_mode",),
    "signed_exception_ref": ("signed_exception_ref",),
    "quarantine_status": ("quarantine_status",),
}


@dataclass(frozen=True, slots=True)
class EffectiveModeLedger:
    """Requested and effective runtime modes for a run or canary lane."""

    requested_execution_profile: object | None = None
    effective_execution_profile: object | None = None
    requested_validation_profile: object | None = None
    effective_validation_profile: object | None = None
    requested_fallback_policy: object | None = None
    effective_fallback_policy: object | None = None
    requested_canary_kind: object | None = None
    effective_canary_kind: object | None = None
    requested_matrix_lane_id: object | None = None
    effective_matrix_lane_id: object | None = None
    requested_provider_mode: object | None = None
    effective_provider_mode: object | None = None
    requested_llm_simulation_mode: object | None = None
    effective_llm_simulation_mode: object | None = None
    requested_fixture_identity: object | None = None
    effective_fixture_identity: object | None = None
    requested_mock_fallback_allowed: object | None = None
    effective_mock_fallback_allowed: object | None = None
    requested_mock_fallback_used: object | None = None
    effective_mock_fallback_used: object | None = None
    requested_data_mode: object | None = None
    effective_data_mode: object | None = None
    requested_state_store_backend: object | None = None
    effective_state_store_backend: object | None = None
    requested_local_control_waiver: object | None = None
    effective_local_control_waiver: object | None = None
    requested_scorecard_warn_policy: object | None = None
    effective_scorecard_warn_policy: object | None = None
    requested_evidence_overlay_mode: object | None = None
    effective_evidence_overlay_mode: object | None = None
    requested_signed_exception_ref: object | None = None
    effective_signed_exception_ref: object | None = None
    requested_quarantine_status: object | None = None
    effective_quarantine_status: object | None = None
    mode_ledger_id: str | None = None
    run_id: str | None = None
    job_id: str | None = None

    @classmethod
    def from_requested_effective(
        cls,
        *,
        requested: Mapping[str, object],
        effective: Mapping[str, object],
        mode_ledger_id: str | None = None,
        run_id: str | None = None,
        job_id: str | None = None,
    ) -> EffectiveModeLedger:
        """Build a ledger from explicit requested/effective dimension maps."""

        values: dict[str, object | None] = {
            "mode_ledger_id": mode_ledger_id,
            "run_id": run_id,
            "job_id": job_id,
        }
        for field in EFFECTIVE_MODE_FIELDS:
            values[f"requested_{field}"] = requested.get(field)
            values[f"effective_{field}"] = effective.get(field)
        return cls(**values)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> EffectiveModeLedger:
        """Build a ledger from the runtime contract payload shape."""

        requested: dict[str, object] = {}
        effective: dict[str, object] = {}
        for field in EFFECTIVE_MODE_FIELDS:
            requested[field] = _read_mode_value(payload, field, prefix="requested")
            effective[field] = _read_mode_value(payload, field, prefix="effective")
        return cls.from_requested_effective(
            requested=requested,
            effective=effective,
            mode_ledger_id=_optional_text(payload.get("mode_ledger_id")),
            run_id=_optional_text(payload.get("run_id")),
            job_id=_optional_text(payload.get("job_id")),
        )

    def requested_values(self) -> dict[str, object | None]:
        """Return requested dimension values in canonical field order."""

        return {
            field: getattr(self, f"requested_{field}") for field in EFFECTIVE_MODE_FIELDS
        }

    def effective_values(self) -> dict[str, object | None]:
        """Return effective dimension values in canonical field order."""

        return {
            field: getattr(self, f"effective_{field}") for field in EFFECTIVE_MODE_FIELDS
        }

    def mismatched_fields(self) -> tuple[str, ...]:
        """Return fields whose requested and effective values differ."""

        return tuple(
            field
            for field in EFFECTIVE_MODE_FIELDS
            if _canonical_value(getattr(self, f"requested_{field}"))
            != _canonical_value(getattr(self, f"effective_{field}"))
        )


class ModePolicyError(ValueError):
    """Raised when an effective-mode ledger cannot satisfy serious closeout."""

    def __init__(
        self,
        *,
        code: str,
        explanation: str,
        ledger: EffectiveModeLedger,
    ) -> None:
        super().__init__(explanation)
        self.code = code
        self.explanation = explanation
        self.ledger = ledger


ModePolicyViolation = ModePolicyError


def assert_serious_mode_allowed(ledger: EffectiveModeLedger) -> None:
    """Raise when a ledger is incompatible with serious closeout."""

    code = mode_policy_failure_code(ledger)
    if code is not None:
        raise ModePolicyError(
            code=code,
            explanation=explain_mode_mismatch(ledger),
            ledger=ledger,
        )


def mode_policy_failure_code(ledger: EffectiveModeLedger) -> str | None:
    """Return the first fail-closed mode policy code, if any."""

    if not _requires_serious_policy(ledger):
        return None

    if _profile_or_lane_mismatch(ledger):
        return "mode_profile_mismatch"
    if _validation_profile_mismatch(ledger):
        return "mode_validation_profile_mismatch"
    if _fallback_policy_mismatch(ledger):
        return "mode_fallback_policy_mismatch"
    if _fixture_overlay_quarantined(ledger):
        return "mode_fixture_overlay_quarantined"
    if _meaningful_ref(ledger.effective_fixture_identity):
        return "mode_fixture_identity_not_allowed"
    if _simulated_provider_used(ledger):
        return "mode_simulated_provider_not_allowed"
    if _truthy_mode(ledger.effective_mock_fallback_used):
        return "mode_mock_fallback_used"
    if _truthy_mode(ledger.effective_mock_fallback_allowed):
        return "mode_mock_fallback_allowed"
    if _contains_any(ledger.effective_data_mode, _NON_PRODUCTION_DATA_TOKENS):
        return "mode_non_production_data"
    if _contains_any(ledger.effective_state_store_backend, _NON_SERIOUS_STATE_TOKENS):
        return "mode_state_store_backend_not_allowed"
    if _meaningful_ref(ledger.effective_local_control_waiver):
        return "mode_local_control_waiver_not_allowed"
    if _norm(ledger.effective_scorecard_warn_policy) in _WARN_ACCEPTED_VALUES:
        return "mode_warn_policy_not_allowed"
    if _evidence_overlay_enabled(ledger.effective_evidence_overlay_mode):
        return "mode_evidence_overlay_not_allowed"
    if _norm(ledger.effective_quarantine_status) in _QUARANTINE_BLOCKED_VALUES:
        return "mode_quarantine_not_allowed"
    if ledger.mismatched_fields():
        return "mode_requested_effective_mismatch"
    return None


def explain_mode_mismatch(ledger: EffectiveModeLedger) -> str:
    """Explain the serious-closeout mode policy decision for operators."""

    code = mode_policy_failure_code(ledger)
    if code is None:
        return "effective_mode_policy_passed: ledger permits serious closeout"

    fields = _explanation_fields(code, ledger)
    details = "; ".join(
        f"{field} requested={_display(getattr(ledger, f'requested_{field}'))} "
        f"effective={_display(getattr(ledger, f'effective_{field}'))}"
        for field in fields
    )
    if not details:
        details = "no field details available"
    return f"{code}: effective mode ledger blocks serious closeout because {details}"


def _read_mode_value(
    payload: Mapping[str, object],
    field: str,
    *,
    prefix: str,
) -> object | None:
    prefixed_key = f"{prefix}_{field}"
    if prefixed_key in payload:
        return payload[prefixed_key]
    if field == "matrix_lane_id":
        alias = f"{prefix}_lane_id"
        if alias in payload:
            return payload[alias]
    if field == "llm_simulation_mode":
        alias = f"{prefix}_model_simulation_mode"
        if alias in payload:
            return payload[alias]

    for alias in _FLAT_ALIASES[field]:
        if alias in payload:
            return payload[alias]
    return None


def _requires_serious_policy(ledger: EffectiveModeLedger) -> bool:
    profile_values = (
        ledger.requested_execution_profile,
        ledger.effective_execution_profile,
    )
    if any(_norm(value) in SERIOUS_EXECUTION_PROFILES for value in profile_values):
        return True

    canary_values = (ledger.requested_canary_kind, ledger.effective_canary_kind)
    if any(_norm(value) in SERIOUS_CANARY_KINDS for value in canary_values):
        return True

    lane_values = (ledger.requested_matrix_lane_id, ledger.effective_matrix_lane_id)
    return any(
        _contains_any(value, _SERIOUS_LANE_TOKENS)
        and not _contains_any(value, ("non_production", "nonprod", "dev", "smoke"))
        for value in lane_values
    )


def _profile_or_lane_mismatch(ledger: EffectiveModeLedger) -> bool:
    requested_profile = _norm(ledger.requested_execution_profile)
    effective_profile = _norm(ledger.effective_execution_profile)
    if requested_profile != effective_profile:
        return True
    if effective_profile not in SERIOUS_EXECUTION_PROFILES:
        return True

    requested_canary = _norm(ledger.requested_canary_kind)
    effective_canary = _norm(ledger.effective_canary_kind)
    if requested_canary != effective_canary:
        return True
    if _contains_any(effective_canary, _NON_PRODUCTION_TOKENS):
        return True

    return _contains_any(ledger.effective_matrix_lane_id, _NON_PRODUCTION_TOKENS)


def _validation_profile_mismatch(ledger: EffectiveModeLedger) -> bool:
    effective_profile = _norm(ledger.effective_execution_profile)
    expected = POLICY_AUTHORITY_TO_VALIDATION_PROFILE.get(effective_profile)  # type: ignore[arg-type]
    if expected is None:
        return True

    requested_validation = _norm(ledger.requested_validation_profile)
    effective_validation = _norm(ledger.effective_validation_profile)
    return requested_validation != expected or effective_validation != expected


def _fallback_policy_mismatch(ledger: EffectiveModeLedger) -> bool:
    effective_profile = _norm(ledger.effective_execution_profile)
    expected = POLICY_AUTHORITY_TO_FALLBACK_PROFILE.get(effective_profile)  # type: ignore[arg-type]
    if expected is None:
        return True

    requested_fallback = _norm(ledger.requested_fallback_policy)
    effective_fallback = _norm(ledger.effective_fallback_policy)
    return requested_fallback != expected or effective_fallback != expected


def _fixture_overlay_quarantined(ledger: EffectiveModeLedger) -> bool:
    return _norm(ledger.effective_quarantine_status) in _QUARANTINE_BLOCKED_VALUES and (
        _meaningful_ref(ledger.effective_fixture_identity)
        or _evidence_overlay_enabled(ledger.effective_evidence_overlay_mode)
    )


def _simulated_provider_used(ledger: EffectiveModeLedger) -> bool:
    return _contains_any(ledger.effective_provider_mode, _SIMULATED_PROVIDER_TOKENS) or (
        _norm(ledger.effective_llm_simulation_mode) in _SIMULATION_ENABLED_VALUES
    )


def _evidence_overlay_enabled(value: object | None) -> bool:
    normalized = _norm(value)
    if normalized is None or normalized in _NONE_VALUES:
        return False
    return _contains_any(normalized, _OVERLAY_BLOCKED_TOKENS)


def _truthy_mode(value: object | None) -> bool:
    if isinstance(value, bool):
        return value
    normalized = _norm(value)
    if normalized is None or normalized in _NONE_VALUES:
        return False
    return normalized in _MOCK_ALLOWED_VALUES


def _meaningful_ref(value: object | None) -> bool:
    if value is None or value is False:
        return False
    normalized = _norm(value)
    return normalized is not None and normalized not in _NONE_VALUES


def _contains_any(value: object | None, tokens: tuple[str, ...]) -> bool:
    normalized = _norm(value)
    if normalized is None:
        return False
    return any(token in normalized for token in tokens)


def _canonical_value(value: object | None) -> str | None:
    normalized = _norm(value)
    if normalized in _NONE_VALUES:
        return None
    return normalized


def _norm(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value).strip()
    if not text:
        return ""
    return text.casefold().replace("-", "_").replace(" ", "_")


def _optional_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _display(value: object | None) -> str:
    return "<none>" if value is None else repr(value)


def _explanation_fields(code: str, ledger: EffectiveModeLedger) -> tuple[str, ...]:
    if code == "mode_profile_mismatch":
        return ("execution_profile", "canary_kind", "matrix_lane_id")
    if code == "mode_validation_profile_mismatch":
        return ("execution_profile", "validation_profile")
    if code == "mode_fallback_policy_mismatch":
        return ("execution_profile", "fallback_policy")
    if code == "mode_fixture_overlay_quarantined":
        return ("fixture_identity", "evidence_overlay_mode", "quarantine_status")
    if code == "mode_fixture_identity_not_allowed":
        return ("fixture_identity",)
    if code == "mode_simulated_provider_not_allowed":
        return ("provider_mode", "llm_simulation_mode")
    if code in {"mode_mock_fallback_allowed", "mode_mock_fallback_used"}:
        return ("mock_fallback_allowed", "mock_fallback_used")
    if code == "mode_non_production_data":
        return ("data_mode",)
    if code == "mode_state_store_backend_not_allowed":
        return ("state_store_backend",)
    if code == "mode_local_control_waiver_not_allowed":
        return ("local_control_waiver", "signed_exception_ref")
    if code == "mode_warn_policy_not_allowed":
        return ("scorecard_warn_policy",)
    if code == "mode_evidence_overlay_not_allowed":
        return ("evidence_overlay_mode",)
    if code == "mode_quarantine_not_allowed":
        return ("quarantine_status",)
    mismatched = ledger.mismatched_fields()
    return mismatched or EFFECTIVE_MODE_FIELDS


__all__ = [
    "EFFECTIVE_MODE_FIELDS",
    "SERIOUS_CANARY_KINDS",
    "SERIOUS_EXECUTION_PROFILES",
    "EffectiveModeLedger",
    "ModePolicyError",
    "ModePolicyViolation",
    "assert_serious_mode_allowed",
    "explain_mode_mismatch",
    "mode_policy_failure_code",
]
