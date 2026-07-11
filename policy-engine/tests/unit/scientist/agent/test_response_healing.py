"""Tests for optional GonkaGate response-healing in JSON-only agent paths."""

from __future__ import annotations

import json

import jax
import pytest

from polisyos.foundry.agent_sim.agents import AdaptiveAgentMechanism
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.ir.kernel import (
    DEFAULT_CONSTRAINT_REGISTRY,
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_METRIC_REGISTRY,
    DEFAULT_SELECTOR_FIELD_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
    DEFAULT_UNITS_REGISTRY,
)
from polisyos.ir.linker import LinkSeverity, link_trinity
from polisyos.ir.registry.registry_fragments import RegistryBundle
from polisyos.scientist.agent.formalizer import (
    FormalizerSchemaValidationError,
    LLMFormalizerAgent,
    MockFormalizerAgent,
    build_final_policy_claims_report,
    create_mock_draft,
)
from polisyos.scientist.agent.pi import LLMPIAgent
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMResponse, GatewayUsage


def _default_registries() -> RegistryBundle:
    return RegistryBundle(
        mechanisms=DEFAULT_MECHANISM_REGISTRY,
        slots=DEFAULT_SLOT_REGISTRY,
        merge_rules=DEFAULT_MERGE_RULE_REGISTRY,
        selector_fields=DEFAULT_SELECTOR_FIELD_REGISTRY,
        units=DEFAULT_UNITS_REGISTRY,
        metrics=DEFAULT_METRIC_REGISTRY,
        constraints=DEFAULT_CONSTRAINT_REGISTRY,
    )


class _FakeJSONLLMClient:
    def __init__(self, payload: dict[str, object] | str) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    async def generate(self, **kwargs):
        self.calls.append(dict(kwargs))
        return GatewayLLMResponse(
            content=(self.payload if isinstance(self.payload, str) else json.dumps(self.payload)),
            usage=GatewayUsage(),
            raw={},
        )


class _FailingLLMClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def generate(self, **kwargs):
        self.calls.append(dict(kwargs))
        raise RuntimeError("provider unavailable")


@pytest.mark.asyncio
async def test_pi_agent_can_attach_response_healing_plugin():
    client = _FakeJSONLLMClient(
        {
            "problem_frame": {
                "frame_id": "pf_test",
                "domain": "economic",
                "problem_statement": "Reduce poverty",
                "actors": ["government"],
                "goals": ["Improve welfare"],
                "constraints": ["Budget cap"],
                "success_criteria": {"metric": "income"},
                "assumptions": ["Stable macro conditions"],
            }
        }
    )

    agent = LLMPIAgent(client, enable_response_healing=True)
    frame = await agent.create_problem_frame("Reduce poverty")

    assert frame.frame_id == "pf_test"
    assert client.calls[0]["plugins"] == [{"id": "response-healing"}]
    assert client.calls[0]["response_format"] == {"type": "json_object"}
    assert "tools" not in client.calls[0]


@pytest.mark.asyncio
async def test_pi_agent_parses_think_prefixed_problem_frame() -> None:
    payload = {
        "problem_frame": {
            "frame_id": "pf_think_prefixed",
            "domain": "education",
            "problem_statement": "Improve school completion.",
            "actors": ["students"],
            "goals": ["Increase completion"],
        }
    }
    client = _FakeJSONLLMClient("<think>frame reasoning</think>" + json.dumps(payload))

    frame = await LLMPIAgent(client).create_problem_frame("Improve school completion")

    assert frame.frame_id == "pf_think_prefixed"
    assert frame.domain == "education"


@pytest.mark.asyncio
async def test_pi_agent_parses_think_prefixed_subtasks() -> None:
    payload = {
        "sub_tasks": [
            {
                "task_id": "task_real",
                "description": "Draft a candidate intervention.",
                "target_agent": "DRAFTER",
                "priority": "high",
            }
        ]
    }
    client = _FakeJSONLLMClient("<think>task reasoning</think>" + json.dumps(payload))

    tasks = await LLMPIAgent(client).decompose_task("Improve school completion")

    assert [task.task_id for task in tasks] == ["task_real"]


@pytest.mark.asyncio
async def test_formalizer_agent_can_attach_response_healing_plugin():
    draft = create_mock_draft(draft_id="draft_test")
    bundle = await MockFormalizerAgent().formalize(draft)
    client = _FakeJSONLLMClient(bundle.model_dump(mode="json"))

    agent = LLMFormalizerAgent(client, enable_response_healing=True)
    formalized = await agent.formalize(draft)

    assert formalized.schema_version == bundle.schema_version
    assert client.calls[0]["plugins"] == [{"id": "response-healing"}]
    assert client.calls[0]["response_format"] == {"type": "json_object"}
    assert "tools" not in client.calls[0]


@pytest.mark.asyncio
async def test_llm_formalizer_parses_think_prefixed_bundle_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft = create_mock_draft(draft_id="draft_think_prefixed_formalizer")
    expected = await MockFormalizerAgent().formalize(draft)
    raw = "<think>formalizer reasoning</think>" + json.dumps(
        expected.model_dump(mode="json")
    )

    async def _unexpected_fallback(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("think-prefixed formalizer output entered mock fallback")

    monkeypatch.setattr(MockFormalizerAgent, "formalize", _unexpected_fallback)

    formalized = await LLMFormalizerAgent(_FakeJSONLLMClient(raw)).formalize(draft)

    assert formalized == expected


@pytest.mark.asyncio
async def test_formalizer_emits_structured_final_policy_claims_from_draft_supports():
    draft = create_mock_draft(draft_id="draft_structured_claims")
    draft.claim_supports = [
        {
            "claim_id": "major_rec",
            "claim_family": "policy_recommendation",
            "major": True,
            "claim": "Target wartime credit support to eligible MSMEs.",
            "data_refs": ["production-msme-panel"],
            "method_refs": ["causal.difference_in_differences"],
            "norm_refs": ["norm.ua.credit_eligibility"],
        },
        {
            "claim_id": "minor_note",
            "claim_family": "implementation",
            "major": "minor",
            "text": "Publish monitoring updates during rollout.",
            "no_grounding_rationale": "Implementation note; no new empirical claim.",
        },
    ]

    bundle = await MockFormalizerAgent().formalize(draft)
    report = build_final_policy_claims_report(draft=draft, trinity_bundle=bundle)

    assert report["schema_version"] == "policyos.scientist.final_policy_claims.v1"
    assert report["extraction_status"] == "pass"
    assert report["summary"]["major_claim_count"] == 1
    assert report["major_claims"][0]["claim_id"] == "major_rec"
    assert report["claims"][0]["claim_family"] == "recommendation"
    assert report["claims"][0]["major"] is True
    assert report["claims"][1]["claim_family"] == "implementation"
    assert report["claims"][1]["major"] is False
    assert (
        report["claims"][1]["grounding"]["no_grounding_rationale"]
        == "Implementation note; no new empirical claim."
    )


@pytest.mark.asyncio
async def test_llm_formalizer_heals_common_model_spec_enum_aliases():
    draft = create_mock_draft(draft_id="draft_model_spec_aliases")
    bundle = await MockFormalizerAgent().formalize(draft)
    payload = bundle.model_dump(mode="json")
    payload["model_spec"]["agent_config"]["interaction_topology"] = "well_mixed"
    payload["model_spec"]["fidelity_level"] = "medium"

    formalized = await LLMFormalizerAgent(_FakeJSONLLMClient(payload)).formalize(draft)

    assert formalized.model_spec.agent_config.interaction_topology == "random"
    assert formalized.model_spec.fidelity_level.value == "hybrid"
    assert (
        "schema_healed:model_spec.agent_config.interaction_topology:well_mixed->random"
        in formalized.model_spec.notes
    )
    assert "schema_healed:model_spec.fidelity_level:medium->hybrid" in formalized.model_spec.notes


@pytest.mark.asyncio
async def test_llm_formalizer_strict_mode_fails_on_schema_healing_aliases() -> None:
    draft = create_mock_draft(draft_id="draft_model_spec_aliases_strict")
    bundle = await MockFormalizerAgent().formalize(draft)
    payload = bundle.model_dump(mode="json")
    payload["model_spec"]["agent_config"]["interaction_topology"] = "well_mixed"
    payload["model_spec"]["fidelity_level"] = "medium"
    client = _FakeJSONLLMClient(payload)

    with pytest.raises(FormalizerSchemaValidationError) as exc_info:
        await LLMFormalizerAgent(
            client,
            schema_healing_mode="strict",
        ).formalize(draft)

    error = exc_info.value
    assert len(client.calls) == 1
    assert error.failure["code"] == "llm_formalizer_schema_validation_failed"
    assert error.failure["layer"] == "llm_formalizer"
    assert error.failure["phase"] == "schema_healing"
    assert error.failure["retryable"] is False
    assert "Fix the formalizer prompt/output schema" in error.failure["next_action"]
    assert error.field_errors == [
        {
            "path": "model_spec.agent_config.interaction_topology",
            "raw": "well_mixed",
            "normalized": "random",
            "note": "schema_healed:model_spec.agent_config.interaction_topology:well_mixed->random",
        },
        {
            "path": "model_spec.fidelity_level",
            "raw": "medium",
            "normalized": "hybrid",
            "note": "schema_healed:model_spec.fidelity_level:medium->hybrid",
        },
    ]


@pytest.mark.asyncio
async def test_llm_formalizer_canonicalizes_common_production_metric_aliases():
    draft = create_mock_draft(draft_id="draft_metric_aliases")
    bundle = await MockFormalizerAgent().formalize(draft)
    payload = bundle.model_dump(mode="json")
    payload["problem_frame"]["objectives"][0]["metric_id"] = "msme_credit_volume"

    formalized = await LLMFormalizerAgent(_FakeJSONLLMClient(payload)).formalize(draft)

    assert formalized.problem_frame.objectives[0].metric_id == "msme_loan_volume"
    assert (
        "schema_healed:problem_frame.objectives[0].metric_id:msme_credit_volume->msme_loan_volume"
    ) in formalized.problem_frame.notes


@pytest.mark.asyncio
async def test_formalizer_falls_back_when_gateway_fails(monkeypatch):
    monkeypatch.setenv("POLISYOS_FORMALIZER_LLM_TIMEOUT_S", "1")
    draft = create_mock_draft(draft_id="draft_gateway_down")
    client = _FailingLLMClient()

    bundle = await LLMFormalizerAgent(client).formalize(draft)

    assert len(client.calls) == LLMFormalizerAgent.MAX_RETRIES + 1
    assert client.calls[0]["timeout"] == 1.0
    assert bundle.schema_version
    assert bundle.policy_spec.interventions


@pytest.mark.asyncio
async def test_mock_formalizer_canonicalizes_float_params_for_trinity_contract():
    draft = create_mock_draft(
        draft_id="draft_float_params",
        interventions=[
            {
                "kind": "adaptive_agent",
                "params": {
                    "adjustment_trigger": "security_risk > 0.6",
                    "learning_rate": 0.01,
                    "policy_model": {"temperature": 0.25},
                    "action_space": {
                        "type": "discrete",
                        "actions": ["monitor", "support"],
                        "affects": ["agents.income"],
                        "bands": [0.1, 1],
                    },
                },
            }
        ],
    )

    bundle = await MockFormalizerAgent().formalize(draft)
    params = bundle.policy_spec.interventions[0].params

    assert "adjustment_trigger" not in params
    assert params["learning_rate"] == "0.01"
    assert params["policy_model"]["temperature"] == "0.25"
    assert params["action_space"]["bands"] == ["0.1", 1]


@pytest.mark.asyncio
async def test_mock_formalizer_deduplicates_normalized_intervention_ids():
    draft = create_mock_draft(
        draft_id="draft_duplicate_interventions",
        interventions=[
            {
                "intervention_id": "intervention",
                "kind": "grant",
                "params": {"amount": 100},
            },
            {
                "intervention_id": "Intervention",
                "kind": "credit",
                "params": {"guarantee_rate": "0.7"},
            },
        ],
    )

    bundle = await MockFormalizerAgent().formalize(draft)
    intervention_ids = [
        intervention.intervention_id for intervention in bundle.policy_spec.interventions
    ]
    parameter_intervention_ids = {
        parameter.intervention_id for parameter in bundle.policy_spec.parameters
    }

    assert len(intervention_ids) == len(set(intervention_ids))
    assert intervention_ids[0] == "intervention"
    assert intervention_ids[1].startswith("intervention_2_")
    assert parameter_intervention_ids == set(intervention_ids)


@pytest.mark.asyncio
async def test_formalizer_normalizes_generated_mechanism_params_for_trinity_linker():
    draft = create_mock_draft(
        draft_id="draft_generated_param_aliases",
        interventions=[
            {
                "intervention_id": "tax_relief",
                "kind": "tax_subsidy",
                "params": {
                    "tax_rate_reduction": 0.2,
                    "duration_years": 3,
                },
            },
            {
                "intervention_id": "wage_support",
                "kind": "tax_subsidy",
                "params": {
                    "subsidy_rate": "25%",
                    "monthly_cap_usd": 500,
                },
            },
            {
                "intervention_id": "risk_scoring",
                "kind": "adaptive_agent",
                "params": {
                    "risk_weight_energy": 0.4,
                    "min_score_for_support": 0.65,
                },
            },
        ],
    )

    bundle = await MockFormalizerAgent().formalize(draft)
    _, report = link_trinity(bundle, _default_registries())
    errors = [issue for issue in report.issues if issue.severity == LinkSeverity.ERROR]

    assert errors == []
    assert bundle.policy_spec.interventions[0].params["rate"] == "0.2"
    assert set(bundle.policy_spec.interventions[0].params) == {"rate"}
    assert bundle.policy_spec.interventions[1].params["rate"] == "0.25"
    assert set(bundle.policy_spec.interventions[1].params) == {"rate"}
    assert bundle.policy_spec.interventions[2].params["observation_space"]
    assert bundle.policy_spec.interventions[2].params["action_space"]
    assert bundle.policy_spec.interventions[2].params["utility"]


@pytest.mark.asyncio
async def test_formalizer_normalizes_adaptive_agent_params_for_runtime_execution():
    draft = create_mock_draft(
        draft_id="draft_adaptive_runtime_targets",
        interventions=[
            {
                "intervention_id": "adaptive_wartime_router",
                "kind": "adaptive_agent",
                "params": {
                    "observation_space": [
                        "agents.income",
                        "cells.distress_score",
                        "government.balance",
                    ],
                    "action_space": {
                        "type": "discrete",
                        "actions": ["no_support", "basic_support", "intensive_support"],
                        "affects": [
                            "agents.income",
                            "government.balance",
                            "policy.tax_rate",
                        ],
                    },
                    "utility": "maximize(msme_resilience) - fiscal_cost",
                },
            }
        ],
    )

    bundle = await MockFormalizerAgent().formalize(draft)
    params = bundle.policy_spec.interventions[0].params

    assert params["observation_space"] == ["agents.income"]
    assert params["action_space"]["affects"] == ["agents.income"]
    assert params["action_space"]["n_categories"] == 3
    assert params["utility"] == "crra"

    mechanism = AdaptiveAgentMechanism(**params, init_opt=False)
    state = GlobalState.empty(4, seed=20260509)
    patches, _ = mechanism.emit_patches(state, jax.random.PRNGKey(20260509))

    assert set(patches) == {"agents.income"}


@pytest.mark.asyncio
async def test_formalizer_maps_tax_relief_semantics_away_from_tax_collection():
    draft = create_mock_draft(
        draft_id="draft_tax_relief_semantics",
        interventions=[
            {
                "intervention_id": "adaptive_tax_relief",
                "kind": "income_tax",
                "description": "Reduce effective tax rate for qualifying MSMEs.",
                "params": {
                    "tax_relief_rate": "30%",
                },
            }
        ],
    )

    bundle = await MockFormalizerAgent().formalize(draft)
    intervention = bundle.policy_spec.interventions[0]

    assert intervention.kind == "tax_subsidy"
    assert intervention.params == {"rate": "0.3"}


@pytest.mark.asyncio
async def test_formalizer_adds_budget_constraint_for_high_rate_support():
    draft = create_mock_draft(
        draft_id="draft_budget_constraint",
        interventions=[
            {
                "intervention_id": "wartime_msme_grant",
                "kind": "tax_subsidy",
                "params": {"rate": "0.7"},
            }
        ],
    )

    bundle = await MockFormalizerAgent().formalize(draft)

    assert [constraint.constraint_id for constraint in bundle.problem_frame.soft_constraints] == [
        "wartime_budget_feasibility"
    ]


@pytest.mark.asyncio
async def test_formalizer_maps_generic_policy_support_mechanisms_to_linkable_contracts():
    draft = create_mock_draft(
        draft_id="draft_generic_support_mechanisms",
        interventions=[
            {
                "intervention_id": "grant_window",
                "kind": "direct_grant",
                "params": {
                    "grant_amount_min_uah": 50_000,
                    "grant_amount_max_uah": 200_000,
                },
            },
            {
                "intervention_id": "reimbursement_window",
                "kind": "custom_mechanism",
                "params": {
                    "reimbursement_rate": "0.7",
                    "max_reimbursement_uah": 1_000_000,
                },
            },
        ],
    )

    bundle = await MockFormalizerAgent().formalize(draft)
    _, report = link_trinity(bundle, _default_registries())
    errors = [issue for issue in report.issues if issue.severity == LinkSeverity.ERROR]

    assert errors == []
    assert [item.kind for item in bundle.policy_spec.interventions] == [
        "tax_subsidy",
        "tax_subsidy",
    ]
    assert bundle.policy_spec.interventions[0].params["rate"] == "0.1"
    assert bundle.policy_spec.interventions[1].params["rate"] == "0.7"
    assert set(bundle.policy_spec.interventions[0].params) == {"rate"}
    assert set(bundle.policy_spec.interventions[1].params) == {"rate"}


@pytest.mark.asyncio
async def test_formalizer_strips_non_runtime_tax_subsidy_params_before_execution():
    draft = create_mock_draft(
        draft_id="draft_runtime_strict_params",
        interventions=[
            {
                "intervention_id": "tax_exemption_window",
                "kind": "tax_subsidy",
                "params": {
                    "exemptions": ["imports", "critical_goods"],
                    "rate": "0.1",
                    "tax_rate": "0.0",
                    "valid_until": "2026-12-31",
                },
            }
        ],
    )

    bundle = await MockFormalizerAgent().formalize(draft)
    intervention = bundle.policy_spec.interventions[0]

    assert intervention.kind == "tax_subsidy"
    assert intervention.params == {"rate": "0.1"}


@pytest.mark.asyncio
async def test_llm_formalizer_drops_unresolved_and_non_numeric_tunable_parameters():
    draft = create_mock_draft(draft_id="draft_invalid_llm_parameter")
    bundle = await MockFormalizerAgent().formalize(draft)
    payload = bundle.model_dump(mode="json")
    payload["policy_spec"]["interventions"] = [
        {
            "intervention_id": "state_loan_guarantee",
            "kind": "adaptive_agent",
            "target": {
                "kind": "predicate",
                "field": "id",
                "operator": "==",
                "value": "all",
            },
            "schedule": {"start_step": 0, "duration_steps": 12},
            "params": {
                "observation_space": ["agents.income", "agents.skill_level"],
                "action_space": {
                    "type": "continuous",
                    "dim": 1,
                    "affects": ["agents.income"],
                },
                "utility": "crra",
                "weights_artifact": "ai_model_weights_v3",
            },
        }
    ]
    payload["policy_spec"]["parameters"] = [
        {
            "param_id": "guarantee_coverage_rate",
            "intervention_id": "state_loan_guarantee",
            "param_path": "params.utility",
            "default_value": "0.8",
            "min_value": "0.0",
            "max_value": "1.0",
        },
        {
            "param_id": "missing_rate",
            "intervention_id": "state_loan_guarantee",
            "param_path": "params.coverage_rate",
            "default_value": "0.8",
        },
        {
            "param_id": "learning_rate",
            "intervention_id": "state_loan_guarantee",
            "param_path": "params.learning_rate",
            "default_value": "0.05",
        },
    ]
    payload["policy_spec"]["interventions"][0]["params"]["learning_rate"] = "0.05"

    client = _FakeJSONLLMClient(payload)
    formalized = await LLMFormalizerAgent(client).formalize(draft)

    assert [param.param_id for param in formalized.policy_spec.parameters] == ["learning_rate"]
    assert formalized.policy_spec.parameters[0].param_path == "learning_rate"
    assert "weights_artifact" not in formalized.policy_spec.interventions[0].params
    assert any(
        note == "dropped_non_numeric_parameter_spec:guarantee_coverage_rate:utility"
        for note in formalized.policy_spec.notes
    )
    assert any(
        note == "dropped_unresolved_parameter_spec:missing_rate:params.coverage_rate"
        for note in formalized.policy_spec.notes
    )
    assert any(
        note == "dropped_invalid_runtime_artifact_ref:state_loan_guarantee:weights_artifact"
        for note in formalized.policy_spec.notes
    )
