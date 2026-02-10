from __future__ import annotations

from typing import List

from .base import ValidatorPass, PassContext, ComplianceIssue, IssueSeverity


def _extract_mechanisms(registry_bundle: object | None) -> dict:
    if registry_bundle is None:
        return {}

    if isinstance(registry_bundle, dict):
        mechanism_registry = registry_bundle.get("mechanism_registry")
        if isinstance(mechanism_registry, dict):
            mechanisms = mechanism_registry.get("mechanisms")
            if isinstance(mechanisms, dict):
                return mechanisms
        if isinstance(registry_bundle.get("mechanisms"), dict):
            return registry_bundle.get("mechanisms", {})
        return {}

    mechanism_registry = getattr(registry_bundle, "mechanism_registry", None)
    if mechanism_registry is None:
        return {}
    mechanisms = getattr(mechanism_registry, "mechanisms", None)
    return mechanisms if isinstance(mechanisms, dict) else {}


class SafetyPass(ValidatorPass):
    """
    Validates mechanism types and intervention safety.

    Extracted from flow_nodes.py validate_ir_node.
    """

    @property
    def pass_id(self) -> str:
        return "safety"

    @property
    def estimated_cost_ms(self) -> int:
        return 25

    @property
    def requires_data(self) -> bool:
        return True

    def validate(self, ctx: PassContext) -> List[ComplianceIssue]:
        issues: List[ComplianceIssue] = []
        ir = ctx.ir

        if ir is None:
            return issues

        registry_bundle = ctx.registry_bundle
        if registry_bundle is None:
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["registry_bundle"],
                    message="Registry bundle not available for safety validation",
                    severity=IssueSeverity.WARNING,
                    code="REGISTRY_UNAVAILABLE",
                )
            )
            return issues

        known_mechanisms = _extract_mechanisms(registry_bundle)

        for idx, intervention in enumerate(ir.policy_spec.interventions):
            if intervention.kind not in known_mechanisms:
                suggestion = None
                if known_mechanisms:
                    suggestion = f"Valid mechanisms: {', '.join(sorted(known_mechanisms.keys()))}"
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=["policy_spec", "interventions", idx, "kind"],
                        message=f"Unknown mechanism type '{intervention.kind}'",
                        severity=IssueSeverity.BLOCKER,
                        code="UNKNOWN_MECHANISM",
                        input_value=intervention.kind,
                        suggestion=suggestion,
                    )
                )

        return issues
