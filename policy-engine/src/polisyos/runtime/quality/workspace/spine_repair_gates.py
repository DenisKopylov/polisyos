"""GY Phase-2 repair gates for legacy spine rot before authority promotion."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from polisyos.pdc import ApplicabilityResult, OperationClass, SearchBlockerRecord


class LexBoundsGateResult(BaseModel):
    """Applicability verdict and frontier provenance for lex bound search."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    applicability: ApplicabilityResult
    blocker: SearchBlockerRecord | None = None
    frontier_payload: dict[str, Any]


class GovernanceTailVerification(BaseModel):
    """Verdict after normative arbitration and judge-stack re-validation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    applicability: ApplicabilityResult
    blocker: SearchBlockerRecord | None = None


class LexBoundsApplicabilityGate:
    """GY facade over the search-domain explicit-bounds repair."""

    def evaluate(
        self,
        *,
        workspace_id: str,
        invocation_id: str,
        lower: float | None,
        upper: float | None,
    ) -> LexBoundsGateResult:
        """Return a typed blocker or a bounded frontier payload."""

        from polisyos.scientist.policy_design import search as policy_search

        domain_result = policy_search.derive_phase2_parameter_bounds(
            workspace_id=workspace_id,
            invocation_id=invocation_id,
            default=0.0,
            lower=lower,
            upper=upper,
        )
        applicability = ApplicabilityResult(
            result_id=domain_result.applicability.result_id,
            invocation_id=invocation_id,
            status=domain_result.applicability.status,
            checked_preconditions=domain_result.applicability.checked_preconditions,
            failed_preconditions=domain_result.applicability.failed_preconditions,
            type_errors=[],
            repair_options=domain_result.applicability.repair_options,
        )
        blocker = None
        if domain_result.blocker is not None:
            blocker = SearchBlockerRecord(
                blocker_id=domain_result.blocker.blocker_id,
                workspace_id=workspace_id,
                operation_class=OperationClass.REFINE,
                blocked_port=domain_result.blocker.blocked_port,
                missing_input=domain_result.blocker.missing_input,
                reason=domain_result.blocker.reason,
                frontier_snapshot_ref=domain_result.blocker.frontier_snapshot_ref,
                applicability_result_ref=applicability.result_id,
                repair_options=applicability.repair_options,
                producer_missing_label=domain_result.blocker.producer_missing_label,
            )
        return LexBoundsGateResult(
            applicability=applicability,
            blocker=blocker,
            frontier_payload=domain_result.frontier_payload,
        )


class BlockedInputProducer:
    """Emit honest blockers for causal/data ports that no producer has supplied."""

    def produce(
        self,
        *,
        workspace_id: str,
        invocation_id: str,
        state_facts: dict[str, Any],
        required_inputs: list[str],
    ) -> list[SearchBlockerRecord]:
        """Return one blocker per missing required causal/data input."""

        blockers: list[SearchBlockerRecord] = []
        for input_name in required_inputs:
            if _present(state_facts.get(input_name)):
                continue
            blockers.append(
                SearchBlockerRecord(
                    blocker_id=f"blocker-{_slug(input_name)}",
                    workspace_id=workspace_id,
                    operation_class=OperationClass.REFINE,
                    blocked_port=input_name,
                    missing_input=input_name,
                    reason=f"Required Phase-2 input '{input_name}' has no producer output.",
                    applicability_result_ref=f"applicability-{_slug(invocation_id)}",
                    repair_options=[
                        {
                            "operation_class": OperationClass.ACQUIRE.value,
                            "reason": f"Produce {input_name} before causal/governance execution.",
                        }
                    ],
                    producer_missing_label="producer_missing",
                )
            )
        return blockers


class GovernanceTailVerifier:
    """Re-validate normative arbitration plus judge stack before authority movement."""

    def verify(
        self,
        *,
        workspace_id: str,
        invocation_id: str,
        normative_result: dict[str, Any],
        judge_verdict: dict[str, Any],
    ) -> GovernanceTailVerification:
        """Return repair-required unless the governance tail is promotable."""

        from polisyos.scientist.api import verify_phase2_governance_tail

        domain_tail = verify_phase2_governance_tail(
            workspace_id=workspace_id,
            invocation_id=invocation_id,
            normative_result=normative_result,
            judge_verdict=judge_verdict,
        )
        applicability = ApplicabilityResult(
            result_id=domain_tail.applicability.result_id,
            invocation_id=domain_tail.applicability.invocation_id,
            status=domain_tail.applicability.status,
            checked_preconditions=domain_tail.applicability.checked_preconditions,
            failed_preconditions=domain_tail.applicability.failed_preconditions,
            type_errors=[],
            repair_options=domain_tail.applicability.repair_options,
        )
        blocker = None
        if domain_tail.blocker is not None:
            blocker = SearchBlockerRecord(
                blocker_id=domain_tail.blocker.blocker_id,
                workspace_id=domain_tail.blocker.workspace_id,
                operation_class=OperationClass.VERIFY,
                blocked_port=domain_tail.blocker.blocked_port,
                missing_input=domain_tail.blocker.missing_input,
                reason=domain_tail.blocker.reason,
                applicability_result_ref=domain_tail.blocker.applicability_result_ref,
                repair_options=domain_tail.blocker.repair_options,
                producer_missing_label=domain_tail.blocker.producer_missing_label,
                severity=domain_tail.blocker.severity,  # type: ignore[arg-type]
            )
        return GovernanceTailVerification(applicability=applicability, blocker=blocker)


def _present(value: object) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def _slug(value: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "-" for char in value)
    compact = "-".join(part for part in normalized.split("-") if part)
    return compact or "item"


__all__ = [
    "BlockedInputProducer",
    "GovernanceTailVerification",
    "GovernanceTailVerifier",
    "LexBoundsApplicabilityGate",
    "LexBoundsGateResult",
]
