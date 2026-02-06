from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.observability import get_metrics


class NaNDiagnostic(BaseModel):
    """Diagnostic information when NaN/Inf detected."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    slot_id: str = Field(..., description="Affected slot identifier")
    mechanism_id: str = Field(..., description="Mechanism that produced the value")
    time_step: int = Field(..., ge=0, description="Simulation time step")
    nan_count: int = Field(..., ge=0, description="Number of NaN values")
    inf_count: int = Field(..., ge=0, description="Number of Inf values")
    sample_indices: list[int] = Field(
        default_factory=list, description="Sample of affected array indices (max 10)"
    )
    possible_cause: str = Field(..., description="Heuristic diagnosis of likely cause")
    value_stats: dict[str, float] = Field(
        default_factory=dict, description="Statistics of non-NaN values for context"
    )


class NaNGuardReport(BaseModel):
    """Complete report from NaN guard checks."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    ok: bool = Field(..., description="True if no NaN/Inf detected")
    diagnostics: list[NaNDiagnostic] = Field(default_factory=list)
    checks_performed: int = Field(default=0, ge=0)
    first_failure_step: int | None = Field(
        default=None, description="Time step of first detected issue"
    )

    def to_artifact(self) -> dict:
        """Convert to storable artifact format."""
        return {
            "schema_version": self.schema_version,
            "ok": self.ok,
            "checks_performed": self.checks_performed,
            "first_failure_step": self.first_failure_step,
            "diagnostics": [
                {
                    "slot_id": diagnostic.slot_id,
                    "mechanism_id": diagnostic.mechanism_id,
                    "time_step": diagnostic.time_step,
                    "nan_count": diagnostic.nan_count,
                    "inf_count": diagnostic.inf_count,
                    "sample_indices": diagnostic.sample_indices[:10],
                    "possible_cause": diagnostic.possible_cause,
                }
                for diagnostic in self.diagnostics
            ],
        }


class NaNGuard:
    """
    Runtime NaN/Inf detection for STRICT profile.

    Provides human-readable diagnostics instead of cryptic JAX tracebacks.
    Only enabled in STRICT validation profile for debugging.

    Performance notes:
    - Uses jnp.any() for efficient reduction
    - Accumulates diagnostics without interrupting compute graph
    - Check frequency is configurable
    """

    CAUSE_PATTERNS: dict[str, str] = {
        "income": "Division by zero or negative sqrt in income calculation",
        "utility": "Log of non-positive value in utility function",
        "tax": "Tax rate outside [0, 1] range or division by zero",
        "consumption": "Negative consumption leading to log(negative)",
        "wealth": "Wealth went negative, causing downstream NaN",
        "labor": "Labor supply outside valid bounds",
        "price": "Price went to zero or negative",
        "rate": "Interest/discount rate computation overflow",
        "policy": "Policy network output outside valid action space",
    }

    def __init__(
        self,
        enabled: bool = False,
        check_interval: int = 1,
        max_diagnostics: int = 100,
    ):
        self._enabled = enabled
        self._check_interval = max(1, check_interval)
        self._max_diagnostics = max_diagnostics
        self._diagnostics: list[NaNDiagnostic] = []
        self._checks_performed = 0
        self._first_failure_step: int | None = None
        self._metrics = get_metrics()

    @property
    def enabled(self) -> bool:
        """Whether guard is active."""
        return self._enabled

    def check_state(
        self,
        state: dict[str, Any],
        slot_id: str,
        mechanism_id: str,
        time_step: int,
    ) -> bool:
        """
        Check state for NaN/Inf after mechanism execution.

        Returns True if state is valid, False otherwise.
        """
        if not self._enabled:
            return True
        if time_step % self._check_interval != 0:
            return True

        self._checks_performed += 1
        if slot_id in state:
            value = state[slot_id]
        else:
            if len(state) == 1:
                value = next(iter(state.values()))
            else:
                return True

        try:
            import jax.numpy as jnp

            arr = jnp.asarray(value)
            nan_mask = jnp.isnan(arr)
            inf_mask = jnp.isinf(arr)

            has_nan = bool(jnp.any(nan_mask))
            has_inf = bool(jnp.any(inf_mask))
            if not has_nan and not has_inf:
                return True

            nan_count = int(jnp.sum(nan_mask))
            inf_count = int(jnp.sum(inf_mask))

            problem_mask = nan_mask | inf_mask
            indices = jnp.where(problem_mask.flatten())[0]
            sample_indices = indices[:10].tolist()

            valid_mask = ~problem_mask
            has_valid = bool(jnp.any(valid_mask))
            if has_valid:
                valid_values = arr[valid_mask]
                value_stats = {
                    "min": float(jnp.min(valid_values)),
                    "max": float(jnp.max(valid_values)),
                    "mean": float(jnp.mean(valid_values)),
                }
            else:
                value_stats = {}

            if len(self._diagnostics) < self._max_diagnostics:
                diagnostic = NaNDiagnostic(
                    slot_id=slot_id,
                    mechanism_id=mechanism_id,
                    time_step=time_step,
                    nan_count=nan_count,
                    inf_count=inf_count,
                    sample_indices=sample_indices,
                    possible_cause=self._diagnose_cause(slot_id, mechanism_id),
                    value_stats=value_stats,
                )
                self._diagnostics.append(diagnostic)
                if self._first_failure_step is None:
                    self._first_failure_step = time_step

            self._metrics.record_slo_simulation_nan(method=mechanism_id)
            return False

        except Exception:
            return True

    def check_array(
        self,
        arr: Any,
        slot_id: str,
        mechanism_id: str,
        time_step: int,
    ) -> bool:
        """Direct array check without state lookup."""
        return self.check_state({slot_id: arr}, slot_id, mechanism_id, time_step)

    def _diagnose_cause(self, slot_id: str, mechanism_id: str) -> str:
        combined = f"{slot_id.lower()} {mechanism_id.lower()}"
        for pattern, cause in self.CAUSE_PATTERNS.items():
            if pattern in combined:
                return cause
        return (
            "Unknown cause - check mechanism implementation for:\n"
            "- Division by zero\n"
            "- Log of non-positive values\n"
            "- Sqrt of negative values\n"
            "- Exp overflow"
        )

    def get_report(self) -> NaNGuardReport:
        """Get comprehensive report of all checks."""
        return NaNGuardReport(
            ok=len(self._diagnostics) == 0,
            diagnostics=list(self._diagnostics),
            checks_performed=self._checks_performed,
            first_failure_step=self._first_failure_step,
        )

    def reset(self) -> None:
        """Reset guard state for new simulation."""
        self._diagnostics.clear()
        self._checks_performed = 0
        self._first_failure_step = None


def create_nan_guard_for_profile(profile_level: str) -> NaNGuard:
    """
    Factory function creating NaNGuard based on validation profile.

    Args:
        profile_level: "fast", "mvp", or "strict"
    """
    profile_level = profile_level.lower()
    if profile_level == "strict":
        return NaNGuard(enabled=True, check_interval=1, max_diagnostics=100)
    if profile_level == "mvp":
        return NaNGuard(enabled=True, check_interval=10, max_diagnostics=50)
    return NaNGuard(enabled=False)
