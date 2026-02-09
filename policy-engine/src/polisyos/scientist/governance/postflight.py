from __future__ import annotations

from typing import Optional, Tuple

from polisyos.ir.gate import GateDecision, GateVerdict

from .preflight import preflight_checks
from .profiles import ValidationProfile


def postflight_checks(
    state: dict,
    profile: Optional[ValidationProfile] = None,
) -> Tuple[dict, Optional[GateDecision]]:
    """
    Post-flight governance using the validation pipeline.

    Returns:
        tuple: (updated_state, gate_decision)
            - gate_decision: None if checks pass, GateDecision if blockers found
    """

    profile = profile or ValidationProfile.mvp()
    updated_state, gate_request = preflight_checks(state, profile)

    if gate_request:
        reason_codes = _extract_reason_codes(updated_state.get("validation_blockers") or [])
        decision = GateDecision(
            request_id=gate_request.request_id,
            run_id=gate_request.run_id,
            verdict=GateVerdict.REJECT,
            approver_id="governance.preflight",
            reason_codes=reason_codes,
            comment=gate_request.reason,
        )
        return updated_state, decision

    return updated_state, None


def _extract_reason_codes(issues: list[dict]) -> list[str]:
    codes: list[str] = []
    for issue in issues:
        code = issue.get("code") or issue.get("error_type")
        if code:
            codes.append(str(code))
    return sorted(set(codes))
