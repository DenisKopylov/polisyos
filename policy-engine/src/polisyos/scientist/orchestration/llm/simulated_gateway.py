"""Deterministic OpenAI-compatible LLM simulator for fast integration runs."""

from __future__ import annotations

import json
import re

from polisyos.scientist.orchestration.llm.gateway_client import (
    GatewayLLMResponse,
    GatewayToolCall,
    GatewayUsage,
)

ZERO_ARTIFACT_REF = f"sha256:{'0' * 64}"
DEFAULT_SIMULATED_MODEL_IDS = (
    "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
    "MiniMaxAI/MiniMax-M2.7",
    "moonshotai/Kimi-K2.6",
)


class SimulatedGatewayLLMClient:
    """Contract-faithful LLM stand-in that exercises JSON parsing without network calls."""

    provider = "simulated_gateway"

    def __init__(
        self,
        *,
        model: str,
        provider_hint: str | None = None,
        supported_model_ids: tuple[str, ...] | list[str] | None = None,
    ) -> None:
        self.model = model
        self.provider_name = provider_hint or self.provider
        self.supported_model_ids = tuple(supported_model_ids or DEFAULT_SIMULATED_MODEL_IDS)
        self.calls: list[dict[str, object]] = []

    async def list_model_ids(self, *, timeout: float | None = None) -> list[str]:
        """Return the deterministic model catalog for offline gateway preflight."""

        del timeout
        return list(self.supported_model_ids)

    async def generate(
        self,
        *,
        system: str | None = None,
        user: str | None = None,
        messages: list[dict[str, object]] | None = None,
        response_format: dict[str, object] | None = None,
        tools: list[dict[str, object]] | None = None,
        tool_choice: str | dict[str, object] | None = None,
        **kwargs: object,
    ) -> GatewayLLMResponse:
        prompt = _prompt_text(system=system, user=user, messages=messages)
        tool_name = _selected_tool_name(tools=tools, tool_choice=tool_choice)
        if tool_name == "emit_design_problem":
            arguments = _design_problem_payload(prompt)
            self.calls.append(
                {
                    "response_kind": "design_problem_tool",
                    "response_format": response_format,
                    "kwargs": {
                        key: value for key, value in kwargs.items() if not key.startswith("_")
                    },
                    "tool_name": tool_name,
                }
            )
            return GatewayLLMResponse(
                content="",
                usage=GatewayUsage(
                    prompt_tokens=max(1, len(prompt) // 4),
                    completion_tokens=max(1, len(json.dumps(arguments)) // 4),
                    total_tokens=max(2, (len(prompt) + len(json.dumps(arguments))) // 4),
                    cost_usd=0.0,
                ),
                model=self.model,
                provider=self.provider_name,
                raw={"simulated": True, "response_kind": "design_problem_tool"},
                tool_calls=[
                    GatewayToolCall(
                        id="call-simulated-design-problem",
                        name="emit_design_problem",
                        arguments=arguments,
                    )
                ],
            )

        payload = _payload_for_prompt(prompt)
        content = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        prompt_tokens = max(1, len(prompt) // 4)
        completion_tokens = max(1, len(content) // 4)
        self.calls.append(
            {
                "response_kind": payload.get("_simulated_response_kind", "generic"),
                "response_format": response_format,
                "tool_choice": tool_choice,
                "kwargs": {key: value for key, value in kwargs.items() if not key.startswith("_")},
            }
        )
        payload.pop("_simulated_response_kind", None)
        return GatewayLLMResponse(
            content=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            usage=GatewayUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                cost_usd=0.0,
            ),
            model=self.model,
            provider=self.provider_name,
            raw={"simulated": True, "response_kind": self.calls[-1]["response_kind"]},
        )

    async def aclose(self) -> None:
        return None


def _selected_tool_name(
    *,
    tools: list[dict[str, object]] | None,
    tool_choice: str | dict[str, object] | None,
) -> str | None:
    if isinstance(tool_choice, dict):
        raw_function = tool_choice.get("function")
        if isinstance(raw_function, dict):
            raw_name = raw_function.get("name")
            if isinstance(raw_name, str) and raw_name.strip():
                return raw_name.strip()
    if tools:
        for tool in tools:
            raw_function = tool.get("function")
            if isinstance(raw_function, dict):
                raw_name = raw_function.get("name")
                if isinstance(raw_name, str) and raw_name.strip():
                    return raw_name.strip()
    return None


def _prompt_text(
    *,
    system: str | None,
    user: str | None,
    messages: list[dict[str, object]] | None,
) -> str:
    if messages:
        return "\n\n".join(str(item.get("content") or "") for item in messages)
    return "\n\n".join(part for part in (system or "", user or "") if part)


def _design_problem_payload(prompt: str) -> dict[str, object]:
    request, context = _extract_design_problem_request(prompt)
    jurisdiction = str(context.get("jurisdiction") or "UA")
    policy_time = str(context.get("policy_time") or context.get("as_of") or "2026-05-15")
    data_time = str(context.get("data_time") or "2024-2026")
    requested_outcome = str(context.get("desired_outcome") or "msme survival")
    return {
        "design_problem_id": "simulated_design_problem",
        "problem_statement": request,
        "domain": "social",
        "nl_provenance": {
            "raw_request": request,
            "source_surface": "runtime.control.nl_request",
            "source_context": {
                key: value
                for key, value in context.items()
                if key in {"run_id", "job_id", "tenant_id", "cell_id", "as_of"}
            },
        },
        "authority_profile": {
            "requester_authority": "research",
            "requested_authority_level": "research",
            "mandate": str(context.get("mandate") or "runtime captured requester intent"),
            "authority_refs": [],
        },
        "jurisdiction_time": {
            "region": jurisdiction,
            "valid_time": policy_time,
            "as_of": str(context.get("as_of") or policy_time),
            "policy_time": policy_time,
            "data_time": data_time,
            "time_semantics": {
                "frequency": "M",
                "start_date": policy_time,
                "step_count": 18,
                "end_date": None,
                "notes": ["simulated gateway deterministic design problem"],
            },
        },
        "objectives": [
            {
                "objective_id": "improve_policy_outcome",
                "description": f"Improve {requested_outcome}.",
                "metric_id": "policy_outcome_metric",
                "direction": "maximize",
            }
        ],
        "constraints": [],
        "stakeholders": [
            {
                "stakeholder_id": "target_population",
                "name": str(context.get("target_population") or "Target population"),
                "role": "beneficiary",
            },
            {
                "stakeholder_id": "policy_authority",
                "name": "Policy authority",
                "role": "requester",
            },
        ],
        "outcome_of_interest": {
            "target_variable": "policy_outcome",
            "metric_id": "policy_outcome_metric",
            "estimand": "Average treatment effect on the requested policy outcome.",
            "direction": "maximize",
        },
        "candidate_lever_space": {
            "allowed_operator_kinds": ["targeted_support"],
            "candidate_levers": [
                {
                    "lever_id": "targeted_support_lever",
                    "operator_kind": "targeted_support",
                    "instrument": str(
                        context.get("proposed_intervention") or "targeted policy support"
                    ),
                    "target_slot": "target_population",
                }
            ],
        },
        "evidence_acquisition_needs": {
            "needs": [
                {
                    "need_id": "outcome_measurement",
                    "question": "What evidence measures the requested outcome for the target population?",
                    "required_for": "outcome_of_interest",
                    "status": "required",
                    "source_hint": "runtime_context",
                    "artifact_ref": None,
                }
            ]
        },
    }


def _extract_design_problem_request(prompt: str) -> tuple[str, dict[str, object]]:
    json_start = prompt.find("{")
    if json_start < 0:
        return _extract_request(prompt), {}
    try:
        payload = json.loads(prompt[json_start:])
    except json.JSONDecodeError:
        return _extract_request(prompt), {}
    if not isinstance(payload, dict):
        return _extract_request(prompt), {}
    raw_request = payload.get("raw_request")
    context = payload.get("context")
    return (
        str(raw_request or _extract_request(prompt)),
        dict(context) if isinstance(context, dict) else {},
    )


def _payload_for_prompt(prompt: str) -> dict[str, object]:
    if "TRINITY BUNDLE TO REVIEW:" in prompt:
        return _critic_payload()
    if "DRAFT TO FORMALIZE:" in prompt:
        return _trinity_payload(prompt)
    if "DataNeedExtractor" in prompt or '"data_needs"' in prompt:
        return _data_needs_payload(prompt)
    if "Generate a draft JSON object" in prompt or "PROBLEM FRAME:" in prompt:
        return _draft_payload(prompt)
    if "USER REQUEST:" in prompt:
        return _pi_payload(prompt)
    return {
        "_simulated_response_kind": "generic",
        "status": "simulated",
        "message": "Deterministic simulated LLM response.",
    }


def _extract_request(prompt: str) -> str:
    match = re.search(r"USER REQUEST:\s*(.+?)(?:\n[A-Z_ ]+:|\Z)", prompt, flags=re.S)
    if not match:
        return "Design a resilient Ukrainian MSME support policy."
    return re.sub(r"\s+", " ", match.group(1)).strip()[:1200]


def _pi_payload(prompt: str) -> dict[str, object]:
    request = _extract_request(prompt)
    return {
        "_simulated_response_kind": "pi",
        "problem_frame": {
            "frame_id": "pf_wartime_msme_support",
            "domain": "economic",
            "problem_statement": request,
            "actors": [
                "cabinet_of_ministers",
                "ministry_of_economy",
                "tax_authority",
                "msmes",
                "banks",
                "local_governments",
            ],
            "goals": [
                "Increase survival and recovery capacity of Ukrainian MSMEs.",
                "Preserve employment under wartime and reconstruction uncertainty.",
                "Target support to high-need firms without open-ended fiscal exposure.",
            ],
            "constraints": [
                "Tight wartime fiscal space.",
                "Legal feasibility under Ukrainian normative acts must be checked.",
                "Eligibility and monitoring must be auditable and contestable.",
            ],
            "success_criteria": {
                "primary_metric": "msme_survival_24m",
                "secondary_metric": "employment_retention",
                "timeframe_months": 18,
            },
            "assumptions": [
                "Applicant-level microdata may be incomplete.",
                "Regional conflict and infrastructure shocks remain heterogeneous.",
            ],
        },
        "sub_tasks": [
            {
                "task_id": "task_msme_draft",
                "description": "Draft a wartime Ukrainian MSME support policy.",
                "target_agent": "drafter",
                "priority": "high",
                "dependencies": [],
                "expected_output": "DraftResult",
            },
            {
                "task_id": "task_msme_formalize",
                "description": "Formalize the draft into a TrinityBundle.",
                "target_agent": "formalizer",
                "priority": "high",
                "dependencies": ["task_msme_draft"],
                "expected_output": "TrinityBundle",
            },
            {
                "task_id": "task_msme_critique",
                "description": "Critique legal, fiscal, fairness and implementation readiness.",
                "target_agent": "critic",
                "priority": "medium",
                "dependencies": ["task_msme_formalize"],
                "expected_output": "CritiqueReport",
            },
        ],
    }


def _draft_payload(prompt: str) -> dict[str, object]:
    problem_frame_ref = _extract_json_field(prompt, "frame_id") or "pf_wartime_msme_support"
    return {
        "_simulated_response_kind": "draft",
        "draft_id": "draft_wartime_msme_integrated_support",
        "problem_frame_ref": problem_frame_ref,
        "narrative": (
            "A targeted wartime MSME resilience package combining bounded tax relief, "
            "recovery grant referrals, auditable eligibility scoring, and adaptive case "
            "management for displaced, veteran-owned, women-owned, export-oriented and "
            "energy-vulnerable firms."
        ),
        "interventions": [
            {
                "intervention_id": "targeted_tax_relief",
                "kind": "tax_subsidy",
                "description": "Temporary targeted tax relief for verified high-need MSMEs.",
                "target": {
                    "kind": "predicate",
                    "field": "id",
                    "operator": "==",
                    "value": "all",
                },
                "schedule": {"start_step": 0, "duration_steps": 18},
                "params": {"rate": "0.12"},
            },
            {
                "intervention_id": "adaptive_case_management",
                "kind": "adaptive_agent",
                "description": "Adaptive routing of firms into monitoring and support lanes.",
                "target": {
                    "kind": "predicate",
                    "field": "id",
                    "operator": "==",
                    "value": "all",
                },
                "schedule": {"start_step": 0, "duration_steps": 18},
                "params": {
                    "observation_space": [
                        "agents.income",
                        "agents.risk_aversion",
                        "agents.skill_level",
                    ],
                    "action_space": {
                        "type": "discrete",
                        "actions": ["monitor", "tax_relief", "grant_referral"],
                        "affects": ["agents.income"],
                        "n_categories": 3,
                    },
                    "utility": "maximize(msme_resilience) - fiscal_cost",
                    "learning_rate": "0.01",
                    "seed": 20260509,
                    "stochastic": True,
                },
            },
        ],
        "rationale": (
            "The simulated LLM proposes a fiscally bounded, auditable package that keeps "
            "the executable mechanism surface compatible with the Trinity linker."
        ),
        "domain_references": [
            "Ukraine MSME support law and wartime recovery programs",
            "Final Lex bundle where available",
        ],
        "alternatives_considered": [
            "untargeted tax holiday",
            "large universal grants",
            "credit-only support",
        ],
        "confidence": 0.82,
    }


def _data_needs_payload(prompt: str) -> dict[str, object]:
    geography = "UKR" if "Ukraine" in prompt or "Укра" in prompt else None
    return {
        "_simulated_response_kind": "data_needs",
        "data_needs": [
            {
                "metric": "us.macro.gdp_nominal",
                "geography": geography,
                "time_start": "2021",
                "time_end": "2026",
                "granularity": "annual",
                "quality_min": 0.6,
                "purpose": "macroeconomic_context_for_msme_policy",
            },
            {
                "metric": "agent.income.salary",
                "geography": geography,
                "time_start": "2021",
                "time_end": "2026",
                "granularity": "agent-level",
                "quality_min": 0.55,
                "purpose": "distributional_and_employment_effect_proxy",
            },
        ],
    }


def _trinity_payload(prompt: str) -> dict[str, object]:
    del prompt
    return {
        "_simulated_response_kind": "formalizer",
        "schema_version": "1.0",
        "problem_frame": {
            "schema_version": "1.0",
            "problem_id": "problem_wartime_msme_support",
            "domain": "fiscal",
            "objectives": [
                {
                    "objective_id": "objective_msme_survival",
                    "metric_id": "avg_income",
                    "direction": "maximize",
                    "weight": "1",
                },
                {
                    "objective_id": "objective_employment_retention",
                    "metric_id": "unemployment_rate",
                    "direction": "minimize",
                    "weight": "0.7",
                },
            ],
            "hard_constraints": [],
            "soft_constraints": [],
            "narrative": (
                "Optimize wartime support for Ukrainian MSMEs under fiscal and legal "
                "constraints."
            ),
            "labels": ["scientist", "trinity", "simulated_llm"],
        },
        "policy_spec": {
            "schema_version": "1.0",
            "policy_id": "policy_wartime_msme_resilience",
            "interventions": [
                {
                    "intervention_id": "targeted_tax_relief",
                    "kind": "tax_subsidy",
                    "target": {
                        "kind": "predicate",
                        "field": "id",
                        "operator": "==",
                        "value": "all",
                    },
                    "schedule": {"start_step": 0, "duration_steps": 18},
                    "params": {"rate": "0.12"},
                    "notes": ["bounded temporary tax relief"],
                },
                {
                    "intervention_id": "adaptive_case_management",
                    "kind": "adaptive_agent",
                    "target": {
                        "kind": "predicate",
                        "field": "id",
                        "operator": "==",
                        "value": "all",
                    },
                    "schedule": {"start_step": 0, "duration_steps": 18},
                    "params": {
                        "observation_space": [
                            "agents.income",
                            "agents.risk_aversion",
                            "agents.skill_level",
                        ],
                        "action_space": {
                            "type": "discrete",
                            "actions": ["monitor", "tax_relief", "grant_referral"],
                            "affects": ["agents.income"],
                            "n_categories": 3,
                        },
                        "utility": "maximize(msme_resilience) - fiscal_cost",
                        "learning_rate": "0.01",
                        "seed": 20260509,
                        "stochastic": True,
                    },
                    "notes": ["adaptive routing and monitoring"],
                },
            ],
            "parameters": [
                {
                    "param_id": "targeted_tax_relief_rate",
                    "intervention_id": "targeted_tax_relief",
                    "param_path": "rate",
                    "default_value": "0.12",
                    "min_value": "0",
                    "max_value": "0.3",
                },
                {
                    "param_id": "adaptive_case_management_learning_rate",
                    "intervention_id": "adaptive_case_management",
                    "param_path": "learning_rate",
                    "default_value": "0.01",
                    "min_value": "0",
                    "max_value": "0.1",
                },
            ],
            "labels": ["scientist", "trinity", "simulated_llm"],
            "description": "Simulated LLM Trinity bundle for fast end-to-end integration checks.",
        },
        "model_spec": {
            "schema_version": "1.0",
            "model_id": "model_wartime_msme_hybrid",
            "data_snapshot_ref": ZERO_ARTIFACT_REF,
            "agent_config": {
                "total_agents": 1000,
                "max_agents": 1000,
                "interaction_topology": "network",
            },
            "assumptions": [
                {
                    "assumption_id": "assumption_microdata_incomplete",
                    "assumption_type": "structural",
                    "description": (
                        "Applicant-level MSME treatment and outcome microdata may be "
                        "incomplete."
                    ),
                    "confidence": "0.7",
                    "sensitivity_flag": True,
                }
            ],
            "environment_config": {
                "random_seed": 20260509,
                "stochastic": True,
                "parallel_worlds": 1,
            },
            "fidelity_level": "hybrid",
            "labels": ["scientist", "trinity", "simulated_llm"],
        },
    }


def _critic_payload() -> dict[str, object]:
    return {
        "_simulated_response_kind": "critic",
        "report_id": "critique_simulated_wartime_msme",
        "verdict": "APPROVE",
        "issues": [
            {
                "issue_id": "simulated_lex_uncertainty",
                "category": "compliance",
                "severity": "info",
                "message": "Legal citations should be checked against the final Lex bundle.",
                "location": "policy_spec.interventions",
                "suggestion": "Keep direct NPA references in the decision packet when available.",
            }
        ],
        "alignment_score": 0.86,
        "completeness_score": 0.84,
        "overall_quality": 0.85,
        "reflexion_hint": "No blocking revision required in simulated LLM mode.",
    }


def _extract_json_field(text: str, field_name: str) -> str | None:
    match = re.search(rf'"{re.escape(field_name)}"\s*:\s*"([^"]+)"', text)
    return match.group(1) if match else None


__all__ = ["SimulatedGatewayLLMClient"]
