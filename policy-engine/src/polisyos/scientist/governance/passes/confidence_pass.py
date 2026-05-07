"""Enforce uncertainty-envelope thresholds on simulation and causal outputs."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import SimulationResult
from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext, ValidatorPass
from polisyos.ir.analytics.uncertainty import load_uncertainty_envelope
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path
from polisyos.scientist.governance.accountability import resolve_governance_threshold


class ConfidencePass(ValidatorPass):
    """Reject over-wide confidence intervals and low gate-eligibility ratios.

    Expected state/artifacts: a `_store` handle plus either
    `artifacts_index.simulation_result_ref` with embedded uncertainty envelopes
    or a causal-envelope ref. Thresholds are read from
    `uncertainty_max_ci_width_ratio`, `uncertainty_max_ci_width_abs`, and
    `uncertainty_min_gate_eligible_ratio`.
    """

    @property
    def pass_id(self) -> str:
        return "confidence"

    @property
    def estimated_cost_ms(self) -> int:
        return 50

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        issues: list[ComplianceIssue] = []

        store = _resolve_store(ctx.state)
        if store is None:
            return issues

        envelope_refs: dict[str, Any] = {}

        sim_result_id = _resolve_simulation_result_id(ctx.state)
        if sim_result_id is None:
            causal_ref = _resolve_causal_envelope_ref(ctx.state)
            if causal_ref is None:
                return issues
            envelope_refs["causal_effect"] = causal_ref
        else:
            try:
                payload = from_canonical_bytes(store.get_bytes(sim_result_id))
                sim_result = SimulationResult.model_validate(payload)
            except (
                AttributeError,
                OSError,
                RuntimeError,
                TypeError,
                ValidationError,
                ValueError,
            ) as exc:
                emit_degraded_path(
                    component="governance.confidence_pass",
                    operation="load_simulation_result",
                    reason="artifact_load_failed",
                    exc=exc,
                    details={"simulation_result_id": str(sim_result_id)},
                )
                return [
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=["artifacts_index", "simulation_result_ref"],
                        message=f"Failed to load SimulationResult: {exc}",
                        severity=IssueSeverity.WARNING,
                        code="CONFIDENCE_SIM_RESULT_LOAD_FAILED",
                    )
                ]

            if sim_result.uncertainty_envelopes:
                for metric_id, ref in sim_result.uncertainty_envelopes.items():
                    envelope_refs[str(metric_id)] = ref
            causal_ref = _resolve_causal_envelope_ref(ctx.state)
            if causal_ref is not None:
                envelope_refs["causal_effect"] = causal_ref

        if not envelope_refs:
            return issues

        max_ci_ratio = resolve_governance_threshold(
            "uncertainty_max_ci_width_ratio",
            ctx.profile.thresholds,
        )
        max_ci_abs = resolve_governance_threshold(
            "uncertainty_max_ci_width_abs",
            ctx.profile.thresholds,
            fallback=float("inf"),
        )
        min_gate_ratio = resolve_governance_threshold(
            "uncertainty_min_gate_eligible_ratio",
            ctx.profile.thresholds,
        )

        n_total = 0
        n_gate_eligible = 0
        for metric_id, ref in envelope_refs.items():
            try:
                env = load_uncertainty_envelope(store, ref)
            except (
                AttributeError,
                OSError,
                RuntimeError,
                TypeError,
                ValidationError,
                ValueError,
            ) as exc:
                emit_degraded_path(
                    component="governance.confidence_pass",
                    operation="load_uncertainty_envelope",
                    reason="artifact_load_failed",
                    exc=exc,
                    details={"metric_id": str(metric_id)},
                )
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=["uncertainty_envelopes", str(metric_id)],
                        message=f"Failed to load uncertainty envelope for metric '{metric_id}'",
                        severity=IssueSeverity.WARNING,
                        code="CONFIDENCE_ENVELOPE_LOAD_FAILED",
                    )
                )
                continue

            n_total += 1
            if env.gate_eligible:
                n_gate_eligible += 1

            ci_width = float(env.confidence_interval[1] - env.confidence_interval[0])
            point_abs = abs(float(env.point_estimate))
            ci_ratio = ci_width / point_abs if point_abs > 1e-12 else float("inf")

            if ci_ratio > max_ci_ratio:
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=["uncertainty_envelopes", str(metric_id), "confidence_interval"],
                        message=(
                            f"Metric '{metric_id}' CI ratio {ci_ratio:.3f} exceeds "
                            f"threshold {max_ci_ratio:.3f}"
                        ),
                        severity=IssueSeverity.BLOCKER,
                        code="CONFIDENCE_CI_RATIO_EXCEEDED",
                        suggestion=f"Reduce uncertainty for metric '{metric_id}' inputs.",
                    )
                )

            if ci_width > max_ci_abs:
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=["uncertainty_envelopes", str(metric_id), "confidence_interval"],
                        message=(
                            f"Metric '{metric_id}' CI width {ci_width:.6g} exceeds "
                            f"threshold {max_ci_abs:.6g}"
                        ),
                        severity=IssueSeverity.BLOCKER,
                        code="CONFIDENCE_CI_ABS_EXCEEDED",
                        suggestion="Narrow input ranges or increase model fidelity.",
                    )
                )

        if n_total > 0:
            gate_ratio = n_gate_eligible / n_total
            if gate_ratio < min_gate_ratio:
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=["uncertainty_envelopes"],
                        message=(
                            f"Gate-eligible envelope ratio {gate_ratio:.3f} is below "
                            f"required minimum {min_gate_ratio:.3f}"
                        ),
                        severity=IssueSeverity.BLOCKER,
                        code="CONFIDENCE_GATE_ELIGIBILITY_LOW",
                        suggestion="Use statistical propagation or improve envelope quality.",
                    )
                )

        return issues


def _resolve_store(state: dict[str, Any]) -> FileSystemCAS | None:
    store = state.get("_store")
    return (
        store
        if store is not None and hasattr(store, "get_bytes") and hasattr(store, "put_json")
        else None
    )


def _resolve_simulation_result_id(state: dict[str, Any]) -> ArtifactID | None:
    artifacts_index = state.get("artifacts_index")
    if isinstance(artifacts_index, dict):
        ref = artifacts_index.get("simulation_result_ref")
        if ref is not None and hasattr(ref, "artifact_id"):
            return ref.artifact_id

    explicit = state.get("simulation_result_ref")
    if explicit is None:
        return None
    if isinstance(explicit, str):
        try:
            return ArtifactID.model_validate(explicit)
        except (TypeError, ValidationError, ValueError) as exc:
            emit_degraded_path(
                component="governance.confidence_pass",
                operation="resolve_simulation_result_id",
                reason="artifact_ref_parse_failed",
                exc=exc,
                details={"simulation_result_ref": explicit},
            )
            return None
    if hasattr(explicit, "artifact_id"):
        return explicit.artifact_id
    return None


def _resolve_causal_envelope_ref(state: dict[str, Any]) -> Any | None:
    artifacts_index = state.get("artifacts_index")
    if isinstance(artifacts_index, dict):
        ref = artifacts_index.get("causal_envelope_ref")
        if ref is not None and hasattr(ref, "artifact_id"):
            return ref
    explicit = state.get("causal_envelope_ref")
    if explicit is not None and hasattr(explicit, "artifact_id"):
        return explicit
    return None


__all__ = ["ConfidencePass"]
