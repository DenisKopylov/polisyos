"""Formalizer agents: draft -> canonical Trinity artifacts."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from polisyos.core.canon import truncated_hash
from polisyos.ir.governance.policy_spec import InterventionSpec as TrinityInterventionSpec
from polisyos.ir.governance.policy_spec import ParameterSpec, PolicySpec
from polisyos.ir.governance.problem_frame import (
    ConstraintType,
    ObjectiveSpec,
    ProblemDomain,
)
from polisyos.ir.governance.problem_frame import (
    ProblemFrame as TrinityProblemFrame,
)
from polisyos.ir.model_spec import (
    AgentConfig,
    AssumptionSpec,
    AssumptionType,
    EnvironmentConfig,
    ModelSpec,
)
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.agent.prompts import get_formalizer_prompt
from polisyos.scientist.agent.protocols import DraftResult, FormalizerAgent
from polisyos.scientist.llm import TracedLLMClient

ZERO_ARTIFACT_REF = f"sha256:{'0' * 64}"
_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _normalize_id(raw: str, *, prefix: str) -> str:
    value = re.sub(r"[^a-z0-9_]+", "_", raw.lower()).strip("_")
    value = re.sub(r"_+", "_", value)
    if not value:
        value = prefix
    if not value[0].isalpha():
        value = f"{prefix}_{value}"
    if _ID_RE.fullmatch(value):
        return value
    digest = truncated_hash(raw, length=10)
    return f"{prefix}_{digest}"


def _infer_domain(text: str) -> ProblemDomain:
    lowered = text.lower()
    if any(token in lowered for token in {"tax", "income", "poverty", "gdp", "budget"}):
        return ProblemDomain.FISCAL
    if any(token in lowered for token in {"health", "hospital", "medical"}):
        return ProblemDomain.HEALTHCARE
    if any(token in lowered for token in {"school", "education", "student"}):
        return ProblemDomain.EDUCATION
    return ProblemDomain.CUSTOM


def _default_target() -> dict[str, Any]:
    return {
        "kind": "predicate",
        "field": "id",
        "operator": "==",
        "value": "all",
    }


def _default_schedule() -> dict[str, Any]:
    return {"start_step": 0, "duration_steps": 12}


def _draft_interventions_to_policy_spec(
    draft: DraftResult,
    *,
    policy_id: str,
    schema_version: str,
) -> PolicySpec:
    interventions: list[TrinityInterventionSpec] = []
    params_specs: list[ParameterSpec] = []

    if draft.interventions:
        raw_items = draft.interventions
    else:
        raw_items = [
            {
                "kind": "tax_subsidy",
                "target": _default_target(),
                "schedule": _default_schedule(),
                "params": {"rate": "0.1"},
            }
        ]

    for idx, raw_item in enumerate(raw_items):
        item = dict(raw_item)
        intervention_id = _normalize_id(
            str(item.get("intervention_id") or item.get("name") or f"intervention_{idx + 1}"),
            prefix="intervention",
        )
        kind = _normalize_id(
            str(item.get("kind") or item.get("mechanism_type") or "tax_subsidy"),
            prefix="mechanism",
        )
        params = item.get("params") or item.get("parameters") or {"rate": "0.1"}
        if not isinstance(params, dict):
            params = {"value": str(params)}

        intervention = TrinityInterventionSpec.model_validate(
            {
                "intervention_id": intervention_id,
                "kind": kind,
                "target": item.get("target") or _default_target(),
                "schedule": item.get("schedule") or _default_schedule(),
                "params": params,
                "notes": [str(item.get("description", "")).strip()] if item.get("description") else [],
            }
        )
        interventions.append(intervention)

        for param_key, param_value in intervention.params.items():
            param_id = _normalize_id(f"{intervention_id}_{param_key}", prefix="param")
            params_specs.append(
                ParameterSpec(
                    param_id=param_id,
                    intervention_id=intervention_id,
                    param_path=str(param_key),
                    default_value=param_value,
                )
            )

    return PolicySpec(
        schema_version=schema_version,
        policy_id=policy_id,
        interventions=interventions,
        parameters=params_specs,
        labels=["scientist", "trinity"],
        description=draft.rationale or None,
    )


def _build_trinity_bundle_from_draft(draft: DraftResult, *, schema_version: str) -> TrinityBundle:
    digest = truncated_hash(draft.draft_id, length=10)
    problem_id = _normalize_id(draft.problem_frame_ref or f"problem_{digest}", prefix="problem")
    policy_id = _normalize_id(f"policy_{digest}", prefix="policy")
    model_id = _normalize_id(f"model_{digest}", prefix="model")

    objectives = [
        ObjectiveSpec(
            objective_id="objective_primary",
            metric_id="avg_income",
            direction="maximize",
        )
    ]

    problem_frame = TrinityProblemFrame(
        schema_version=schema_version,
        problem_id=problem_id,
        domain=_infer_domain(draft.narrative),
        objectives=objectives,
        hard_constraints=[],
        soft_constraints=[],
        narrative=draft.narrative,
        labels=["scientist", "trinity"],
    )

    policy_spec = _draft_interventions_to_policy_spec(
        draft,
        policy_id=policy_id,
        schema_version=schema_version,
    )

    assumptions: list[AssumptionSpec] = []
    if draft.rationale:
        assumptions.append(
            AssumptionSpec(
                assumption_id="assumption_rationale",
                assumption_type=AssumptionType.STRUCTURAL,
                description=draft.rationale[:500],
            )
        )

    model_spec = ModelSpec(
        schema_version=schema_version,
        model_id=model_id,
        data_snapshot_ref=ZERO_ARTIFACT_REF,
        agent_config=AgentConfig(total_agents=1000, max_agents=1000),
        assumptions=assumptions,
        environment_config=EnvironmentConfig(random_seed=42, stochastic=True),
        labels=["scientist", "trinity"],
    )

    return TrinityBundle(
        schema_version=schema_version,
        problem_frame=problem_frame,
        policy_spec=policy_spec,
        model_spec=model_spec,
    )


def _to_trinity(ir: Any, *, schema_version: str = "1.0") -> TrinityBundle:
    if isinstance(ir, TrinityBundle):
        if ir.schema_version == schema_version:
            return ir
        return ir.model_copy(update={"schema_version": schema_version})

    raise TypeError(f"Unsupported IR type for Trinity conversion: {type(ir)}")


class MockFormalizerAgent:
    """Mock implementation of FormalizerAgent for tests and fallback paths."""

    def __init__(self) -> None:
        self._formalization_count: int = 0
        self._repair_count: int = 0

    async def formalize(
        self,
        draft: DraftResult,
        *,
        schema_version: str = "1.0",
    ) -> TrinityBundle:
        if not draft.draft_id:
            raise ValueError("Draft must have a valid draft_id")

        self._formalization_count += 1
        return _build_trinity_bundle_from_draft(draft, schema_version=schema_version)

    async def repair_ir(
        self,
        ir: TrinityBundle,
        errors: list[str],
        *,
        hint: str | None = None,
    ) -> TrinityBundle:
        self._repair_count += 1

        bundle = _to_trinity(ir)
        bundle_data = bundle.model_dump(mode="python")

        lowered_errors = " ".join(error.lower() for error in errors)
        if "intervention" in lowered_errors and not bundle_data["policy_spec"]["interventions"]:
            bundle_data["policy_spec"]["interventions"] = [
                {
                    "intervention_id": "intervention_repair",
                    "kind": "tax_subsidy",
                    "target": _default_target(),
                    "schedule": _default_schedule(),
                    "params": {"rate": "0.1"},
                }
            ]
        if "data_snapshot_ref" in lowered_errors or not bundle_data["model_spec"].get(
            "data_snapshot_ref"
        ):
            bundle_data["model_spec"]["data_snapshot_ref"] = ZERO_ARTIFACT_REF
        if hint:
            notes = list(bundle_data["policy_spec"].get("notes") or [])
            notes.append(f"repair_hint: {hint}")
            bundle_data["policy_spec"]["notes"] = notes

        repaired = TrinityBundle.model_validate(bundle_data)
        return repaired

    async def validate_structure(
        self,
        ir: TrinityBundle,
    ) -> tuple[bool, list[str]]:
        errors: list[str] = []

        try:
            bundle = _to_trinity(ir)
            if not bundle.problem_frame.problem_id:
                errors.append("Missing problem_frame.problem_id")
            if not bundle.policy_spec.interventions:
                errors.append("No interventions defined")
            if not bundle.model_spec.data_snapshot_ref:
                errors.append("Missing model_spec.data_snapshot_ref")
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
    """LLM-powered Formalizer; Trinity-first."""

    MAX_RETRIES = 2

    def __init__(
        self,
        llm_client: Any,
        model_name: str | None = None,
        *,
        method_catalog_snapshot: dict[str, Any] | None = None,
    ) -> None:
        if llm_client is not None and not isinstance(llm_client, TracedLLMClient):
            self._llm = TracedLLMClient(llm_client, model_name=model_name)
        else:
            self._llm = llm_client
        self._fallback = MockFormalizerAgent()
        self._method_catalog_snapshot = dict(method_catalog_snapshot or {})

    def set_method_catalog_snapshot(self, payload: dict[str, Any] | None) -> None:
        self._method_catalog_snapshot = dict(payload or {})

    async def formalize(
        self,
        draft: DraftResult,
        *,
        schema_version: str = "1.0",
    ) -> TrinityBundle:
        prompt = get_formalizer_prompt(method_catalog_snapshot=self._method_catalog_snapshot)

        user_message = f"""
DRAFT TO FORMALIZE:
{draft.narrative}

PROPOSED INTERVENTIONS:
{json.dumps(draft.interventions, indent=2)}

RATIONALE:
{draft.rationale}

Generate a valid TrinityBundle v{schema_version} JSON.
"""

        last_error: str | None = None
        for attempt in range(self.MAX_RETRIES + 1):
            attempt_message = user_message
            if last_error and attempt > 0:
                attempt_message += (
                    f"\n\nPREVIOUS ERROR (attempt {attempt}):\n{last_error}\n"
                    "Please fix and try again."
                )

            try:
                response = await self._llm.generate(
                    system=prompt,
                    user=attempt_message,
                    response_format={"type": "json_object"},
                )
            except Exception as exc:
                last_error = f"LLM call failed: {exc}"
                continue

            content = response.content if hasattr(response, "content") else str(response)
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            try:
                data = json.loads(content)
                bundle = TrinityBundle.model_validate(data)
                if schema_version and bundle.schema_version != schema_version:
                    bundle = bundle.model_copy(update={"schema_version": schema_version})
                return bundle
            except (json.JSONDecodeError, ValidationError, ValueError, TypeError) as exc:
                last_error = str(exc)

        # Fallback to deterministic formalizer if LLM output is unusable.
        return await self._fallback.formalize(
            draft,
            schema_version=schema_version,
        )

    async def repair_ir(
        self,
        ir: TrinityBundle,
        errors: list[str],
        *,
        hint: str | None = None,
    ) -> TrinityBundle:
        return await self._fallback.repair_ir(
            ir,
            errors,
            hint=hint,
        )

    async def validate_structure(
        self,
        ir: TrinityBundle,
    ) -> tuple[bool, list[str]]:
        return await self._fallback.validate_structure(ir)


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
