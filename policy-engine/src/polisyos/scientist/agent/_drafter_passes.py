"""Deterministic pass checks and code-verification augmentation.

These are mixed into ``MultiPassLLMDrafter`` via the
``_DrafterPassesMixin`` helper base class.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from polisyos.core.observability import get_tracer
from polisyos.scientist.agent.code_verifier import (
    DraftVariableExtractor,
    VerificationCodeExtractor,
    VerificationStatus,
)
from polisyos.scientist.agent.protocols import DraftResult, ProblemFrame

from .drafter_models import (
    FindingCategory,
    FindingSeverity,
    PassExecution,
    PassFinding,
)

if TYPE_CHECKING:
    from polisyos.scientist.agent.code_verifier import CodeVerificationSandbox
    from polisyos.scientist.agent.memory import ShortTermMemory

    from .drafter_models import MultiPassConfig

logger = logging.getLogger(__name__)

__all__ = ["_DrafterPassesMixin"]


class _DrafterPassesMixin:
    """Deterministic checks and code-verification augmentation."""

    # -- Provided by the orchestrator at runtime --
    _config: MultiPassConfig
    _code_verifier: CodeVerificationSandbox | None
    _memory: ShortTermMemory | None

    # ------------------------------------------------------------------
    # Deterministic checks (pass 1.5)
    # ------------------------------------------------------------------

    def _execute_deterministic_checks(self, draft: DraftResult) -> PassExecution:
        tracer = get_tracer()
        started = time.perf_counter()
        with tracer.start_as_current_span(
            "drafter.pass.deterministic_checks",
            attributes={
                "polisyos.drafter.pass_name": "deterministic_checks",
                "polisyos.drafter.pass_number": 1,
            },
        ):
            findings: list[PassFinding] = []
            findings.extend(self._check_parameter_ranges(draft))
            findings.extend(self._check_target_overlaps(draft))
            return PassExecution(
                pass_name="deterministic_checks",
                pass_number=1,
                executed=True,
                draft=draft,
                findings=findings,
                duration_ms=int((time.perf_counter() - started) * 1000),
            )

    def _check_parameter_ranges(self, draft: DraftResult) -> list[PassFinding]:
        findings: list[PassFinding] = []
        for idx, intervention in enumerate(draft.interventions):
            params = intervention.get("params")
            if params is None:
                params = intervention.get("parameters")
            if not isinstance(params, dict):
                continue
            for key, value in params.items():
                key_lower = str(key).lower()
                if "rate" not in key_lower:
                    continue
                try:
                    numeric = float(value)
                except (TypeError, ValueError):
                    findings.append(
                        PassFinding(
                            finding_id=f"det_rate_type_{idx}_{key}",
                            category=FindingCategory.PARAMETER_ERROR,
                            severity=FindingSeverity.MEDIUM,
                            description=f"Parameter `{key}` is non-numeric (`{value}`).",
                            suggested_fix=f"Set `{key}` to numeric value in [0, 1].",
                            anchor=f"intervention:{idx}",
                            source_pass="deterministic_checks",
                        )
                    )
                    continue
                if numeric < 0.0 or numeric > 1.0:
                    findings.append(
                        PassFinding(
                            finding_id=f"det_rate_range_{idx}_{key}",
                            category=FindingCategory.PARAMETER_ERROR,
                            severity=FindingSeverity.HIGH,
                            description=(
                                f"Parameter `{key}`={numeric} is out of allowed range [0, 1]."
                            ),
                            suggested_fix=f"Clamp `{key}` to [0, 1] or explain scaling.",
                            anchor=f"intervention:{idx}",
                            source_pass="deterministic_checks",
                        )
                    )
        return findings

    def _check_target_overlaps(self, draft: DraftResult) -> list[PassFinding]:
        findings: list[PassFinding] = []
        seen: dict[str, int] = {}
        for idx, intervention in enumerate(draft.interventions):
            target_population = intervention.get("target_population")
            if isinstance(target_population, str) and target_population.strip():
                key = target_population.strip().lower()
            else:
                target = intervention.get("target")
                key = json.dumps(target, sort_keys=True) if target else ""
            if not key:
                continue
            first_idx = seen.get(key)
            if first_idx is None:
                seen[key] = idx
                continue
            findings.append(
                PassFinding(
                    finding_id=f"det_target_overlap_{first_idx}_{idx}",
                    category=FindingCategory.TARGET_OVERLAP,
                    severity=FindingSeverity.MEDIUM,
                    description=(
                        f"Interventions {first_idx} and {idx} appear to target the same population."
                    ),
                    suggested_fix="Clarify targeting or merge conflicting interventions.",
                    anchor=f"intervention:{idx}",
                    source_pass="deterministic_checks",
                )
            )
        return findings

    # ------------------------------------------------------------------
    # Code-verification augmentation for pass 3
    # ------------------------------------------------------------------

    def _augment_pass3_with_code_verification(
        self,
        pass3: PassExecution,
        *,
        draft: DraftResult,
        problem_frame: ProblemFrame,
    ) -> PassExecution:
        if not pass3.executed:
            return pass3
        if self._code_verifier is None:
            return pass3

        verification_code = pass3.verification_code
        if not verification_code:
            verification_code = VerificationCodeExtractor.extract_from_llm_response(
                pass3.raw_llm_response
            )
        if not verification_code:
            return pass3

        tracer = get_tracer()
        with tracer.start_as_current_span(
            "drafter.pass.code_verification",
            attributes={
                "polisyos.drafter.pass_name": "code_verification",
                "polisyos.drafter.pass_number": 3,
            },
        ) as span:
            variables = DraftVariableExtractor.extract(draft, problem_frame)
            verification = self._code_verifier.execute(
                verification_code,
                variables=variables,
            )
            span.set_attribute(
                "polisyos.drafter.code_verification_status", verification.status.value
            )
            span.set_attribute("polisyos.drafter.code_verification_passed", verification.passed)
            span.set_attribute(
                "polisyos.drafter.code_verification_duration_ms",
                verification.execution_time_ms,
            )

        if verification.status in {VerificationStatus.PASSED, VerificationStatus.SKIPPED}:
            return pass3

        extra_findings: list[PassFinding] = []
        for idx, payload in enumerate(verification.to_findings()):
            extra_findings.append(
                PassFinding(
                    finding_id=f"code_verification_{idx}",
                    category=self._parse_category(payload.get("category", "other")),
                    severity=self._parse_severity(payload.get("severity", "high")),
                    description=str(payload.get("description", "Verification failed")),
                    suggested_fix=str(payload.get("suggested_fix", "")),
                    affected_intervention=(
                        str(payload.get("affected_intervention"))
                        if payload.get("affected_intervention")
                        else None
                    ),
                    anchor=str(payload.get("anchor", "verification:code")),
                    source_pass="code_verification",
                )
            )

        if self._memory is not None and extra_findings:
            self._memory.add_pass_findings(
                "code_verification",
                [finding.as_memory_dict() for finding in extra_findings],
            )

        merged_findings = list(pass3.findings) + extra_findings
        updated_adjustment = pass3.confidence_adjustment
        if extra_findings:
            updated_adjustment = (updated_adjustment or 0.0) - (0.03 * len(extra_findings))
        return replace(
            pass3,
            findings=merged_findings,
            confidence_adjustment=updated_adjustment,
        )
