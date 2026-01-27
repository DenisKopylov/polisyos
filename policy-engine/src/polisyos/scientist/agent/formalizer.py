"""
Mock Formalizer Agent.

Implements the FormalizerAgent protocol with deterministic IR outputs for tests.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from polisyos.ir.surface import PolicySurfaceIR
from polisyos.scientist.agent.prompts import get_formalizer_prompt
from polisyos.scientist.agent.protocols import DraftResult, FormalizerAgent

if TYPE_CHECKING:
    pass


class MockFormalizerAgent:
    """Mock implementation of FormalizerAgent for testing."""

    def __init__(self) -> None:
        self._formalization_count: int = 0
        self._repair_count: int = 0

    async def formalize(
        self,
        draft: DraftResult,
        *,
        schema_version: str = "2.0",
    ) -> "PolicySurfaceIR":
        from polisyos.ir.surface import PolicySurfaceIR

        if not draft.draft_id:
            raise ValueError("Draft must have a valid draft_id")

        self._formalization_count += 1

        base_hash = hashlib.sha256(draft.draft_id.encode()).hexdigest()[:8]

        intervention_kind = "tax_subsidy"
        narrative_lower = draft.narrative.lower()
        if "tax" in narrative_lower and "subsidy" not in narrative_lower:
            intervention_kind = "income_tax"
        elif any(word in narrative_lower for word in ["ubi", "basic income", "transfer"]):
            intervention_kind = "direct_transfer"

        ir_data: dict[str, Any] = {
            "schema_version": schema_version,
            "semantic": {
                "context_snapshot_ref": f"sha256:{'0' * 64}",
                "time_semantics": {
                    "frequency": "M",
                    "start_date": "2024-01-01",
                    "step_count": 12,
                },
                "objectives": [
                    {
                        "objective_id": f"obj_{base_hash}",
                        "metric_id": "avg_income",
                        "direction": "maximize",
                        "weight": "1.0",
                    }
                ],
                "interventions": self._build_interventions(draft, intervention_kind, base_hash),
                "constraints": [
                    {
                        "constraint_id": "min_balance",
                        "value": {"amount": "-5000", "currency": "USD"},
                    }
                ],
            },
            "advisory": {
                "entities": [
                    {
                        "entity_id": "target_group",
                        "entity_type": "agent",
                        "name": {"en": "Target population", "ua": "Target population"},
                    }
                ],
                "labels": ["mock_generated"],
                "narrative": draft.rationale or "Auto-generated from draft",
            },
        }

        return PolicySurfaceIR(**ir_data)

    def _build_interventions(
        self,
        draft: DraftResult,
        intervention_kind: str,
        base_hash: str,
    ) -> list[dict[str, Any]]:
        interventions: list[dict[str, Any]] = []

        if draft.interventions:
            for i, intervention in enumerate(draft.interventions):
                interventions.append(
                    {
                        "intervention_id": f"interv_{base_hash}_{i}",
                        "kind": intervention.get("kind", intervention_kind),
                        "target": intervention.get(
                            "target",
                            {
                                "kind": "predicate",
                                "field": "income",
                                "operator": "<",
                                "value": "1000",
                            },
                        ),
                        "schedule": intervention.get(
                            "schedule",
                            {"start_step": 0, "duration_steps": 12},
                        ),
                        "params": intervention.get("params", {"rate": "0.15"}),
                    }
                )
        else:
            interventions.append(
                {
                    "intervention_id": f"interv_{base_hash}_0",
                    "kind": intervention_kind,
                    "target": {
                        "kind": "predicate",
                        "field": "income",
                        "operator": "<",
                        "value": "1000",
                    },
                    "schedule": {"start_step": 0, "duration_steps": 12},
                    "params": {"rate": "0.15"},
                }
            )

        return interventions

    async def repair_ir(
        self,
        ir: "PolicySurfaceIR",
        errors: list[str],
        *,
        hint: str | None = None,
    ) -> "PolicySurfaceIR":
        from polisyos.ir.surface import PolicySurfaceIR

        self._repair_count += 1

        ir_dict = ir.model_dump()

        for error in errors:
            error_lower = error.lower()
            if "context_snapshot_ref" in error_lower:
                ir_dict["semantic"]["context_snapshot_ref"] = f"sha256:{'0' * 64}"
            if "time_semantics" in error_lower:
                ir_dict["semantic"]["time_semantics"] = {
                    "frequency": "M",
                    "start_date": "2024-01-01",
                    "step_count": 12,
                }
            if "intervention" in error_lower and not ir_dict["semantic"].get("interventions"):
                ir_dict["semantic"]["interventions"] = [
                    {
                        "intervention_id": "default_repair",
                        "kind": "tax_subsidy",
                        "target": {
                            "kind": "predicate",
                            "field": "id",
                            "operator": "==",
                            "value": "all",
                        },
                        "schedule": {"start_step": 0, "duration_steps": 12},
                        "params": {"rate": "0.1"},
                    }
                ]

        return PolicySurfaceIR(**ir_dict)

    async def validate_structure(
        self,
        ir: "PolicySurfaceIR",
    ) -> tuple[bool, list[str]]:
        errors: list[str] = []

        try:
            if not ir.schema_version:
                errors.append("Missing schema_version")
            if not ir.semantic:
                errors.append("Missing semantic section")
                return False, errors

            semantic = ir.semantic
            if hasattr(semantic, "context_snapshot_ref") and not semantic.context_snapshot_ref:
                errors.append("Missing context_snapshot_ref")

            if hasattr(semantic, "interventions"):
                if not semantic.interventions:
                    errors.append("No interventions defined")
                else:
                    for i, intervention in enumerate(semantic.interventions):
                        if not getattr(intervention, "intervention_id", None):
                            errors.append(f"Intervention {i} missing intervention_id")
        except Exception as exc:
            errors.append(f"Validation error: {exc}")

        return len(errors) == 0, errors

    @property
    def formalization_count(self) -> int:
        return self._formalization_count

    @property
    def repair_count(self) -> int:
        return self._repair_count

    def reset(self) -> None:
        self._formalization_count = 0
        self._repair_count = 0


class LLMFormalizerAgent:
    """
    LLM-powered Formalizer agent.

    Converts DraftResult to PolicySurfaceIR with validation.
    """

    MAX_RETRIES = 2

    def __init__(self, llm_client: Any) -> None:
        self._llm = llm_client

    async def formalize(
        self,
        draft: DraftResult,
        *,
        schema_version: str = "2.0",
    ) -> PolicySurfaceIR:
        """Convert a natural language draft to PolicySurfaceIR."""
        prompt = get_formalizer_prompt()

        user_message = f"""
DRAFT TO FORMALIZE:
{draft.narrative}

PROPOSED INTERVENTIONS:
{json.dumps(draft.interventions, indent=2)}

RATIONALE:
{draft.rationale}

Generate a valid PolicySurfaceIR v{schema_version} JSON.
"""

        last_error: str | None = None
        for attempt in range(self.MAX_RETRIES + 1):
            if last_error and attempt > 0:
                user_message += (
                    f"\n\nPREVIOUS ERROR (attempt {attempt}):\n{last_error}\n"
                    "Please fix and try again."
                )

            response = await self._llm.generate(
                system=prompt,
                user=user_message,
                response_format={"type": "json_object"},
            )

            content = response.content if hasattr(response, "content") else str(response)
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            try:
                data = json.loads(content)
                return PolicySurfaceIR(**data)
            except json.JSONDecodeError as exc:
                last_error = f"JSON parse error: {exc}"
            except ValidationError as exc:
                last_error = f"Schema validation error: {exc.errors()[:3]}"

        raise ValueError(
            f"Formalization failed after {self.MAX_RETRIES + 1} attempts: {last_error}"
        )

    async def repair_ir(
        self,
        ir: PolicySurfaceIR,
        errors: list[str],
        *,
        hint: str | None = None,
    ) -> PolicySurfaceIR:
        """Repair an invalid IR based on validation errors."""
        prompt = get_formalizer_prompt()

        ir_json = ir.model_dump_json(indent=2)
        errors_text = "\n".join(f"- {error}" for error in errors)

        user_message = f"""
INVALID IR TO REPAIR:
{ir_json}

ERRORS TO FIX:
{errors_text}
"""
        if hint:
            user_message += f"\nHINT: {hint}"

        user_message += "\n\nGenerate the CORRECTED PolicySurfaceIR JSON."

        response = await self._llm.generate(
            system=prompt,
            user=user_message,
            response_format={"type": "json_object"},
        )

        content = response.content if hasattr(response, "content") else str(response)
        data = json.loads(content)
        return PolicySurfaceIR(**data)

    async def validate_structure(
        self,
        ir: PolicySurfaceIR,
    ) -> tuple[bool, list[str]]:
        """Validate IR structure without full semantic check."""
        errors: list[str] = []

        if not ir.semantic.interventions:
            errors.append("No interventions defined")

        for i, intervention in enumerate(ir.semantic.interventions):
            if not intervention.intervention_id:
                errors.append(f"Intervention {i}: missing intervention_id")
            if not intervention.kind:
                errors.append(f"Intervention {i}: missing mechanism kind")
            if not intervention.target:
                errors.append(f"Intervention {i}: missing target selector")

        return (len(errors) == 0, errors)


def create_mock_draft(
    *,
    draft_id: str | None = None,
    problem_frame_ref: str = "pf_mock",
    narrative: str = "Mock policy to reduce poverty through targeted subsidies",
    interventions: list[dict[str, Any]] | None = None,
) -> DraftResult:
    import uuid

    return DraftResult(
        draft_id=draft_id or f"draft_{uuid.uuid4().hex[:8]}",
        problem_frame_ref=problem_frame_ref,
        narrative=narrative,
        interventions=interventions or [],
        rationale="Mock rationale for testing",
        confidence=0.85,
        created_at=datetime.utcnow(),
    )


def _verify_protocol() -> None:
    agent = MockFormalizerAgent()
    if not isinstance(agent, FormalizerAgent):
        raise TypeError("MockFormalizerAgent does not implement FormalizerAgent protocol")


_verify_protocol()
