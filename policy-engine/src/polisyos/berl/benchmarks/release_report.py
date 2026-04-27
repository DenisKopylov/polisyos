"""Text report helpers for BERL release gates."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from polisyos.berl.contracts.validation_rules import ExplanationValidationResult


def render_release_report(
    *,
    model_ids: Sequence[str],
    method_ids: Sequence[str],
    output_scale: str,
    perturbation_policy: str,
    validation: ExplanationValidationResult,
) -> str:
    """Render a compact release report block for explainability validation."""

    lines = [
        "Explanation disagreement report",
        f"- Models: {', '.join(model_ids)}",
        f"- Methods: {', '.join(method_ids)}",
        f"- Output scale: {output_scale}",
        f"- Local perturbation policy: {perturbation_policy}",
        f"- Faithfulness claim: {validation.faithfulness_claim}",
        f"- Display policy: {validation.display_policy}",
        f"- Violations: {', '.join(validation.violations) if validation.violations else 'none'}",
        f"- Warnings: {', '.join(validation.warnings) if validation.warnings else 'none'}",
    ]
    return "\n".join(lines)
