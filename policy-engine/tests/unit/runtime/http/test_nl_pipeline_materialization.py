from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.execution_plan import MethodCatalogSnapshot, MethodCatalogSnapshotRef
from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver
from polisyos.runtime.http.services.control import ControlPlaneService
from polisyos.runtime.http.services.control.generation_cycle import (
    compile_and_run_recursive_generation_cycle,
)
from polisyos.runtime.http.services.control.nl_pipeline import (
    NaturalLanguagePipelineRefusalError,
    NaturalLanguageRunMixin,
    _build_scientist_context_params,
    _preflight_design_problem_model,
    _production_materialization_failure,
    build_design_problem_from_nl_request,
)
from polisyos.runtime.http.services.control.nl_pipeline_testing import (
    NLContractTestingAuthorityStamp,
)
from polisyos.runtime.http.services.control_registry_providers import ControlRegistryProviders
from polisyos.runtime.quality.assurance_case import PolicyDesignCaseAuthorityError
from polisyos.runtime.quality.authority_reconciliation import reconcile_authority_ref
from polisyos.runtime.quality.design_problem import DesignProblem, DesignProblemAuthorityError
from polisyos.runtime.quality.generation_cycle import (
    CandidateGroundingObservation,
    GenerationCycleController,
    PendingN8ValuePort,
    PromotionPortObservation,
    SimulationPortObservation,
)
from polisyos.runtime.quality.recursive_generation_cycle import (
    RecursiveCycleBudget,
    RecursiveGenerationCycleController,
)
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMResponse, GatewayToolCall
from polisyos.scientist.orchestration.llm.simulated_gateway import SimulatedGatewayLLMClient
from polisyos.scientist.validation.policy_grounding import build_policy_grounding_matrix_report
from tools.ops_runners.runtime.canary_evidence import assemble_canary_evidence

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_production_nl_pipeline_refuses_empty_model_set_before_work() -> None:
    with pytest.raises(NaturalLanguagePipelineRefusalError) as exc_info:
        NaturalLanguageRunMixin()._execute_nl_pipeline(
            run_id="R_no_model",
            nl_request="Design a policy.",
            context={},
            domain_hint=None,
            data_source=None,
            max_iterations=1,
            llm_models=[],
            max_parallel_models=1,
            run_budget_usd=None,
            per_model_budget_usd=None,
            checkpoint_policy="strict",
            execution_plan_ref=None,
            execution_plan_payload=None,
            stop_criteria_payload=None,
            governance_constraints_payload=None,
            expected_outputs_payload=None,
        )

    assert exc_info.value.code == "llm_model_unconfigured"


def test_production_nl_pipeline_never_injects_contract_agents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = NaturalLanguageRunMixin()

    def _capture_router(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["contract_testing_agent_factory"] is None
        return {"run_id": kwargs["run_id"]}

    monkeypatch.setattr(mixin, "_execute_nl_pipeline_impl", _capture_router)
    result = mixin._execute_nl_pipeline(
        run_id="R_production_router",
        nl_request="Design a policy.",
        context={},
        domain_hint=None,
        data_source=None,
        max_iterations=1,
        llm_models=["configured-model"],
        max_parallel_models=1,
        run_budget_usd=None,
        per_model_budget_usd=None,
        checkpoint_policy="strict",
        execution_plan_ref=None,
        execution_plan_payload=None,
        stop_criteria_payload=None,
        governance_constraints_payload=None,
        expected_outputs_payload=None,
    )

    assert result["nl_authority"]["authority_scope"] == "production"
    assert result["nl_authority"]["production_promotable"] is True


def test_contract_testing_nl_stamp_cannot_be_promotable() -> None:
    with pytest.raises(ValueError):
        NLContractTestingAuthorityStamp(production_promotable=True)  # type: ignore[arg-type]


class _FakeMetric:
    def model_dump(self, mode: str = "json") -> dict[str, Any]:
        return {"metric": "macro.gdp", "value": 1.0}


class _FakeRetrievalService:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def resolve(self, request: Any) -> Any:
        return SimpleNamespace(
            fetch_plans=[{"id": "plan-1"}],
            telemetry={
                "lane_used": "fastlane",
                "metadata_docs_fetched": 1,
                "local_index_size_bytes": 10,
                "local_index_docs_total": 1,
                "candidates_filtered": 0,
                "phases": [],
            },
            mode="hybrid",
        )

    def execute_fetch_plans(
        self,
        plans: list[dict[str, Any]],
        persist_payload: bool = False,
        allow_fallback: bool = True,
    ) -> Any:
        return SimpleNamespace(
            previews=[SimpleNamespace(preview=SimpleNamespace(coverage_ok=True))],
            fallback_triggered_count=0,
            promoted_count=1,
            data_context=SimpleNamespace(
                metrics=[_FakeMetric()],
                metadata_docs_fetched=1,
                index_docs_total=1,
                index_size_bytes=10,
            ),
        )


class _ExternalFetchBlockedRetrievalService(_FakeRetrievalService):
    execute_called = False

    def execute_fetch_plans(
        self,
        plans: list[dict[str, Any]],
        persist_payload: bool = False,
        allow_fallback: bool = True,
    ) -> Any:
        type(self).execute_called = True
        raise TimeoutError("external provider fetch must not run for production-data canary")


class _EmptyRegistry:
    def query_entries(self, *args: Any, **kwargs: Any) -> list[Any]:
        return []

    def get(self, profile_id: str) -> None:
        return None

    def list_all(self) -> list[Any]:
        return []

    def list_by_family(self, connector_family: str) -> list[Any]:
        return []


def _registry_providers() -> ControlRegistryProviders:
    registry = _EmptyRegistry()
    return ControlRegistryProviders(
        connectors=registry,
        source_profiles=registry,
        binding_profiles=registry,
        model_profiles=registry,
    )


def _normative_context() -> dict[str, Any]:
    return {
        "tenant_id": "tenant-intent",
        "cell_id": "cell-intent",
        "jurisdiction": "UA",
        "target_population": "wartime MSMEs",
        "policy_time": "2026-05-15",
        "data_time": "2024-2026",
        "policy_problem": "Wartime MSMEs face liquidity constraints.",
        "desired_outcome": "msme survival",
        "proposed_intervention": "targeted credit support",
        "requester_preferred_conclusion": None,
        "requested_authority_level": "research",
        "target_context": {
            "context_id": "UA_WARTIME_MSME_2026",
            "countries": ["UA"],
            "publication_year": 2026,
        },
        "policy_domain": "wartime_msme_support",
        "as_of": "2026-05-12",
        "lex_candidate_norms": [
            {
                "norm_id": "norm.ua.credit_eligibility",
                "artifact_id": "sha256:" + "5" * 64,
                "fact_class": "credit_eligibility_rule",
                "jurisdiction": "UA",
                "policy_domain": "wartime_msme_support",
                "effective_from": "2024-01-01",
                "effective_to": "",
                "source_authority": "Verkhovna Rada",
                "authority_level": "statute",
                "relevance_rationale": "Defines wartime MSME credit eligibility.",
            }
        ],
        "policy_recommendations": [
            {
                "claim_id": "rec_1",
                "major": True,
                "text": "Target wartime credit support to eligible MSMEs.",
                "norm_refs": ["norm.ua.credit_eligibility"],
            }
        ],
    }


def _intent_context(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "tenant_id": "tenant-intent",
        "cell_id": "cell-intent",
        "jurisdiction": "UA",
        "target_population": "wartime MSMEs",
        "policy_time": "2026-05-15",
        "data_time": "2024-2026",
        "policy_problem": "Wartime MSMEs face liquidity constraints.",
        "desired_outcome": "msme survival",
        "proposed_intervention": "targeted credit support",
        "requester_preferred_conclusion": None,
        "requested_authority_level": "research",
    }
    payload.update(overrides)
    return payload


class _DeterministicSpanSupportClient:
    def __init__(self, *, decision: str = "entails", confidence: float = 0.93) -> None:
        self.decision = decision
        self.confidence = confidence
        self.calls: list[dict[str, Any]] = []

    async def generate(
        self,
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        temperature: float | None = None,
        seed: int | None = None,
    ) -> Any:
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
                "temperature": temperature,
                "seed": seed,
            }
        )
        return SimpleNamespace(
            content="",
            model="deterministic-span-support",
            provider="test-gateway",
            request_id="span-support-request",
            tool_calls=[
                SimpleNamespace(
                    id="call-span-support",
                    name="layer3_gy_record_span_support_judgment",
                    arguments={
                        "decision": self.decision,
                        "confidence": self.confidence,
                        "rationale": "deterministic test judgment",
                    },
                )
            ],
        )


class _FakeDesignProblemGateway:
    def __init__(self, *, models: list[str], arguments: dict[str, Any]) -> None:
        self.models = models
        self.arguments = arguments
        self.generate_calls: list[dict[str, Any]] = []

    async def list_model_ids(self, *, timeout: float | None = None) -> list[str]:
        return list(self.models)

    async def generate(self, **kwargs: Any) -> GatewayLLMResponse:
        self.generate_calls.append(kwargs)
        return GatewayLLMResponse(
            content="",
            model="Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
            provider="gateway",
            tool_calls=[
                GatewayToolCall(
                    id="call-design-problem",
                    name="emit_design_problem",
                    arguments=self.arguments,
                )
            ],
        )


class _PlainLanguageGenerationPort:
    async def __call__(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
    ) -> SimpleNamespace:
        del cycle_index
        candidate_id = f"candidate_{problem.design_problem_id}"
        candidate = SimpleNamespace(
            candidate_id=candidate_id,
            atom=SimpleNamespace(
                intervention_id=f"intervention_{problem.design_problem_id}",
                content_hash="sha256:" + "4" * 64,
                status="candidate_unverified",
                world_model_record_ref="world_model_record_plain_language_lane0",
                target_world_slots=(problem.outcome_of_interest.target_variable,),
            ),
            diversity_key=("plain", "language", "lane0", "candidate"),
            status="candidate_unverified",
        )
        return SimpleNamespace(
            status="generated",
            candidates=(candidate,),
            surrogate_rankings=(
                SimpleNamespace(
                    candidate_id=candidate_id,
                    score=0.2,
                    voi_estimate=0.1,
                    trust_level="search_guiding",
                    promotion_allowed=False,
                ),
            ),
            grounding_dispositions=(),
        )


class _PlainLanguageGroundingPort:
    def __call__(
        self,
        *,
        candidate: Any,
        **kwargs: Any,
    ) -> CandidateGroundingObservation:
        del kwargs
        return CandidateGroundingObservation(
            candidate_id=str(candidate.candidate_id),
            status="grounding_gap",
            grounding_score=0.2,
            issue_codes=("plain_language_lane0_grounding_gap",),
            current_valid=False,
        )


class _PlainLanguageSimulationPort:
    def __call__(self, *, candidate: Any, **kwargs: Any) -> SimulationPortObservation:
        del kwargs
        return SimulationPortObservation(
            candidate_id=str(candidate.candidate_id),
            status="simulation_pending_n5",
            authority_blockers=("plain_language_lane0_n5_pending",),
        )


class _PlainLanguagePromotionPort:
    def __call__(self, **kwargs: Any) -> PromotionPortObservation:
        del kwargs
        return PromotionPortObservation()


def _plain_language_leaf_cycle_factory(
    node_ref: str,
    problem: DesignProblem,
) -> GenerationCycleController:
    del node_ref, problem
    return GenerationCycleController(
        generation_port=_PlainLanguageGenerationPort(),
        grounding_port=_PlainLanguageGroundingPort(),
        simulation_port=_PlainLanguageSimulationPort(),
        value_port=PendingN8ValuePort(),
        promotion_port=_PlainLanguagePromotionPort(),
        repo_root=REPO_ROOT,
    )


def _design_problem_tool_args(*, constraint_source: str = "UAH 10b budget cap") -> dict[str, Any]:
    return {
        "design_problem_id": "design_problem_ua_msme_credit",
        "problem_statement": "Design a wartime MSME credit guarantee for Ukraine.",
        "domain": "social",
        "nl_provenance": {
            "raw_request": (
                "Design a wartime MSME credit guarantee for Ukraine within the stated "
                "UAH 10b budget cap."
            ),
            "source_surface": "runtime.control.nl_request",
            "source_context": {"run_id": "run-design-problem"},
        },
        "authority_profile": {
            "requester_authority": "research",
            "requested_authority_level": "research",
            "mandate": "Cabinet research mandate.",
        },
        "jurisdiction_time": {
            "region": "UA",
            "valid_time": "2026-05-15",
            "as_of": "2026-05-12",
            "policy_time": "2026-05-15",
            "data_time": "2024-2026",
            "time_semantics": {"frequency": "Q", "start_date": "2024-01-01", "step_count": 8},
        },
        "objectives": [
            {
                "objective_id": "increase_msme_survival",
                "description": "Increase MSME survival.",
                "metric_id": "msme_survival_rate",
                "direction": "maximize",
            }
        ],
        "constraints": [
            {
                "constraint_id": "budget_cap",
                "description": f"Respect {constraint_source}.",
                "hard": True,
                "admissibility_basis": "request_text",
                "source_text": constraint_source,
            }
        ],
        "stakeholders": [
            {"stakeholder_id": "wartime_msmes", "name": "wartime MSMEs", "role": "beneficiary"}
        ],
        "outcome_of_interest": {
            "target_variable": "firm_survival",
            "metric_id": "msme_survival_rate",
            "estimand": "P(firm_survival | do(credit_access))",
            "direction": "maximize",
        },
        "candidate_lever_space": {
            "allowed_operator_kinds": ["credit_guarantee"],
            "candidate_levers": [
                {
                    "lever_id": "credit_access_guarantee",
                    "operator_kind": "credit_guarantee",
                    "instrument": "credit guarantee",
                    "target_slot": "credit_access",
                }
            ],
        },
        "evidence_acquisition_needs": {
            "needs": [
                {
                    "need_id": "credit_panel",
                    "question": "Measure credit access and firm survival.",
                    "required_for": "outcome_of_interest",
                    "status": "required",
                    "source_hint": "measurement_root",
                }
            ]
        },
    }


@pytest.mark.asyncio
async def test_design_problem_front_door_uses_gateway_tool_calling_and_preflight() -> None:
    gateway = _FakeDesignProblemGateway(
        models=["Qwen/Qwen3-235B-A22B-Instruct-2507-FP8", "MiniMaxAI/MiniMax-M2.7"],
        arguments=_design_problem_tool_args(),
    )
    span_support = _DeterministicSpanSupportClient()

    problem = await build_design_problem_from_nl_request(
        nl_request=(
            "Design a wartime MSME credit guarantee for Ukraine within the stated "
            "UAH 10b budget cap."
        ),
        context=_intent_context(as_of="2026-05-12"),
        model_name="Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
        gateway_client=gateway,
        span_support_client=span_support,
    )

    assert problem.design_problem_id == "design_problem_ua_msme_credit"
    assert problem.authority_profile.requested_authority_level == "research"
    assert problem.jurisdiction_time.region == "UA"
    assert problem.outcome_of_interest.target_variable == "firm_survival"
    assert problem.candidate_lever_space.candidate_levers[0].operator_kind == "credit_guarantee"
    assert problem.evidence_acquisition_needs.needs[0].status == "required"
    assert gateway.generate_calls
    assert gateway.generate_calls[0]["tools"][0]["function"]["name"] == "emit_design_problem"
    assert gateway.generate_calls[0]["tool_choice"]["function"]["name"] == "emit_design_problem"
    tool_schema = gateway.generate_calls[0]["tools"][0]["function"]["parameters"]
    assert "$defs" not in tool_schema
    assert "$ref" not in json.dumps(tool_schema)
    assert span_support.calls


@pytest.mark.asyncio
async def test_plain_language_front_door_calls_real_design_problem_compiler() -> None:
    raw_request = (
        "Design a wartime MSME credit guarantee for Ukraine within the stated "
        "UAH 10b budget cap."
    )
    gateway = _FakeDesignProblemGateway(
        models=["Qwen/Qwen3-235B-A22B-Instruct-2507-FP8"],
        arguments=_design_problem_tool_args(),
    )
    result = await compile_and_run_recursive_generation_cycle(
        raw_request=raw_request,
        context=_intent_context(as_of="2026-05-12"),
        model_name="Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
        compiler_gateway=gateway,
        span_support_client=_DeterministicSpanSupportClient(),
        controller=RecursiveGenerationCycleController.for_contract_testing(
            cycle_controller_factory=_plain_language_leaf_cycle_factory,
            repo_root=REPO_ROOT,
        ),
        budget_state=BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
        ),
        recursive_budget=RecursiveCycleBudget(
            max_depth=0,
            max_nodes=1,
            min_cycles_per_leaf=1,
            max_cycles_per_leaf=2,
        ),
    )

    assert result.design_problem.nl_provenance.raw_request == raw_request
    assert result.recursive_run.root_design_problem_ref == result.design_problem_ref
    assert result.recursive_run.observed_max_depth == 0
    assert gateway.generate_calls


@pytest.mark.asyncio
async def test_design_problem_front_door_rejects_unsupported_model_profile() -> None:
    gateway = _FakeDesignProblemGateway(
        models=["Qwen/Qwen3-235B-A22B-Instruct-2507-FP8", "MiniMaxAI/MiniMax-M2.7"],
        arguments=_design_problem_tool_args(),
    )

    with pytest.raises(DesignProblemAuthorityError, match="model_profile_unsupported"):
        await build_design_problem_from_nl_request(
            nl_request="Design a credit guarantee.",
            context=_intent_context(),
            model_name="gpt-5-mini",
            gateway_client=gateway,
        )


@pytest.mark.asyncio
async def test_design_problem_preflight_uses_offline_simulated_model_catalog() -> None:
    client = SimulatedGatewayLLMClient(
        model="simulated-qwen",
        supported_model_ids=["simulated-qwen"],
    )

    await _preflight_design_problem_model(client=client, model_name="simulated-qwen")
    with pytest.raises(DesignProblemAuthorityError, match="model_profile_unsupported"):
        await _preflight_design_problem_model(client=client, model_name="gpt-5-mini")


@pytest.mark.asyncio
async def test_design_problem_front_door_rejects_hallucinated_constraint() -> None:
    gateway = _FakeDesignProblemGateway(
        models=["Qwen/Qwen3-235B-A22B-Instruct-2507-FP8"],
        arguments=_design_problem_tool_args(constraint_source="unstated WTO compatibility"),
    )

    with pytest.raises(DesignProblemAuthorityError, match="invented_admissibility"):
        await build_design_problem_from_nl_request(
            nl_request="Design a wartime MSME credit guarantee for Ukraine.",
            context=_intent_context(),
            model_name="Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
            gateway_client=gateway,
            span_support_client=_DeterministicSpanSupportClient(),
        )


@pytest.mark.asyncio
async def test_design_problem_front_door_rejects_word_sharing_without_entailment() -> None:
    gateway = _FakeDesignProblemGateway(
        models=["Qwen/Qwen3-235B-A22B-Instruct-2507-FP8"],
        arguments=_design_problem_tool_args(constraint_source="budget"),
    )
    neutral_support = _DeterministicSpanSupportClient(decision="neutral", confidence=0.96)

    with pytest.raises(DesignProblemAuthorityError, match="admissibility_unverified"):
        await build_design_problem_from_nl_request(
            nl_request=(
                "Assess credit guarantees for MSMEs and discuss budget tradeoffs. "
                "Do not set a fiscal cap."
            ),
            context=_intent_context(),
            model_name="Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
            gateway_client=gateway,
            span_support_client=neutral_support,
        )
    assert neutral_support.calls


@pytest.mark.asyncio
async def test_design_problem_front_door_accepts_supported_paraphrase() -> None:
    gateway = _FakeDesignProblemGateway(
        models=["Qwen/Qwen3-235B-A22B-Instruct-2507-FP8"],
        arguments=_design_problem_tool_args(constraint_source="below ten billion hryvnia"),
    )
    span_support = _DeterministicSpanSupportClient(decision="entails", confidence=0.91)

    problem = await build_design_problem_from_nl_request(
        nl_request=(
            "Assess credit guarantees for MSMEs. Keep fiscal exposure below ten "
            "billion hryvnia."
        ),
        context=_intent_context(),
        model_name="Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
        gateway_client=gateway,
        span_support_client=span_support,
    )

    assert problem.constraints[0].source_text == "below ten billion hryvnia"
    assert span_support.calls


@pytest.mark.asyncio
async def test_design_problem_front_door_fails_closed_without_entailment_verifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import polisyos.scientist.validation.citation_faithfulness as cf

    monkeypatch.setattr(cf, "_create_default_span_support_client", lambda: None)
    gateway = _FakeDesignProblemGateway(
        models=["Qwen/Qwen3-235B-A22B-Instruct-2507-FP8"],
        arguments=_design_problem_tool_args(),
    )

    with pytest.raises(DesignProblemAuthorityError, match="entailment_verifier_unavailable"):
        await build_design_problem_from_nl_request(
            nl_request=(
                "Design a wartime MSME credit guarantee for Ukraine within the stated "
                "UAH 10b budget cap."
            ),
            context=_intent_context(),
            model_name="Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
            gateway_client=gateway,
        )


_PHASE_24_REQUIRED_RUNTIME_REFS = {
    "normative_evidence": "normative_applicability_report_ref",
    "fabric_retrieval_trace": "fabric_retrieval_trace_ref",
    "foundry_method_report": "foundry_method_report_ref",
    "policy_grounding_matrix": "policy_grounding_matrix_ref",
    "conflict_check": "conflict_check_ref",
    "causal_statistical_validity": "causal_statistical_validity_report_ref",
}


def _write_phase_24_production_data_root(tmp_path: Path) -> Path:
    production_data_root = tmp_path / "production_data"
    datasets_dir = production_data_root / "datasets_full_20990101"
    curated_dir = production_data_root / "canonical/local_data_20990101/policy_engine_data/curated"
    datasets_dir.mkdir(parents=True)
    curated_dir.mkdir(parents=True)
    (datasets_dir / "dataset_catalog.duckdb").touch()
    (datasets_dir / "panel.csv").write_text(
        "\n".join(
            [
                "entity_id,period,geography,population,msme_survival_rate,macro.gdp,wartime_credit_support,label_quality",
                "ua-msme-1,2026-01-31,UKR,wartime_msme,0.84,1.0,1,audited",
                "ua-msme-2,2026-02-28,UKR,wartime_msme,0.88,1.1,0,audited",
                "ua-msme-3,2026-03-31,UKR,wartime_msme,0.81,1.2,1,audited",
            ]
        ),
        encoding="utf-8",
    )
    (datasets_dir / "data_dictionary.json").write_text(
        json.dumps(
            {
                "columns": {
                    "entity_id": {"description": "Entity id", "role": "entity_id"},
                    "period": {"description": "Period", "role": "time"},
                    "geography": {"description": "Country", "role": "geography"},
                    "population": {"description": "Population", "role": "population"},
                    "msme_survival_rate": {
                        "description": "MSME survival rate",
                        "metric_id": "msme_survival_rate",
                        "unit": "rate",
                    },
                    "macro.gdp": {
                        "description": "GDP value used by fake runtime data need extractor",
                        "metric_id": "macro.gdp",
                        "unit": "index",
                    },
                    "wartime_credit_support": {
                        "description": "Credit support treatment",
                        "metric_id": "wartime_credit_support",
                        "unit": "binary",
                    },
                    "label_quality": {"description": "Label quality", "role": "label_quality"},
                },
                "entity_id_columns": ["entity_id"],
                "time_columns": ["period"],
                "geography_columns": ["geography"],
                "population_columns": ["population"],
                "updated_at": "2026-05-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    (production_data_root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "generated_at": "2026-05-01T00:00:00Z",
                "bundles": {
                    "datasets": {
                        "version_id": "datasets_full_20990101",
                        "readiness": "ready",
                        "path": "datasets_full_20990101",
                        "catalog_db_path": "datasets_full_20990101/dataset_catalog.duckdb",
                        "dataset_path": "datasets_full_20990101/panel.csv",
                        "data_dictionary_path": "datasets_full_20990101/data_dictionary.json",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return production_data_root


def _forbid_real_gateway_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _blocked_gateway_constructor(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError(
            "POLISYOS_LLM_SIMULATION_MODE tests must not construct real gateway clients"
        )

    monkeypatch.setattr(
        "polisyos.scientist.orchestration.llm.factory.GatewayLLMClient",
        _blocked_gateway_constructor,
    )
    monkeypatch.setattr(
        "polisyos.scientist.orchestration.llm.factory.FallbackRouter",
        _blocked_gateway_constructor,
    )


def test_production_materialization_failure_requires_quality_ref_for_serious_profile() -> None:
    failure = _production_materialization_failure(
        execution_profile="research",
        data_source=None,
        selected_variant={
            "model": "simulated-qwen",
            "auto_data_source_refs": {
                "data_snapshot_ref": "sha256:" + "1" * 64,
                "input_bindings_ref": "sha256:" + "2" * 64,
                "registry_bundle_ref": "sha256:" + "3" * 64,
                "quality_report_ref": "sha256:" + "4" * 64,
            },
        },
    )

    assert failure is not None
    assert failure["code"] == "production_data_quality_missing"
    assert failure["layer"] == "fabric_materialization"
    assert failure["phase"] == "production_data_quality"
    assert failure["retryable"] is False
    assert "production_data_quality_report_ref" in failure["message"]


def test_production_materialization_failure_is_not_required_for_dev_profile() -> None:
    assert (
        _production_materialization_failure(
            execution_profile="dev",
            data_source=None,
            selected_variant={"auto_data_source_refs": {}},
        )
        is None
    )


def test_nl_pipeline_only_auto_attaches_default_production_data_for_serious_profiles(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    production_data_root = tmp_path / "production_data"
    datasets_dir = production_data_root / "datasets_full_phase3full_20260327_183054"
    datasets_dir.mkdir(parents=True)
    (datasets_dir / "dataset_catalog.duckdb").touch()
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("POLISYOS_PRODUCTION_DATA_ROOT", raising=False)

    dev_params = _build_scientist_context_params(
        {},
        domain_hint=None,
        execution_profile="dev",
    )
    research_params = _build_scientist_context_params(
        {},
        domain_hint=None,
        execution_profile="research",
    )

    assert "production_data_root" not in dev_params
    assert research_params["production_data_root"] == "production_data"
    assert research_params["datasets_db_path"] == (
        "production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb"
    )


def test_nl_pipeline_fails_unknown_serious_metric_before_workflow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _forbidden_run_experiment(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("unknown metrics must fail before scientist workflow execution")

    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _forbidden_run_experiment)
    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="research",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control-unknown-metric.sqlite3"),
            postgres_dsn=None,
        ),
        registry_providers=_registry_providers(),
    )
    job_id = "job_unknown_metric"
    service._control_store.create_job(
        job_id=job_id,
        kind="natural_language_run",
        run_id="R_nl_unknown_metric",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="research",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )

    try:
        with pytest.raises(RuntimeError) as exc_info:
            service._execute_nl_pipeline_for_contract_testing(
                run_id="R_nl_unknown_metric",
                nl_request="Evaluate a serious MSME policy.",
                context=_intent_context(
                    desired_outcome="msme_survivl_rate",
                    query_outcome="msme_survivl_rate",
                ),
                domain_hint="Ukraine wartime MSME support policy",
                data_source=None,
                max_iterations=1,
                llm_models=[],
                max_parallel_models=1,
                run_budget_usd=None,
                per_model_budget_usd=None,
                checkpoint_policy="strict",
                execution_plan_ref=None,
                execution_plan_payload=None,
                stop_criteria_payload={},
                governance_constraints_payload=[],
                expected_outputs_payload=[],
                control_job_id=job_id,
                execution_profile="research",
            )
        record = service._control_store.get_job(job_id)
    finally:
        service.close()

    assert "unknown_production_metric" in str(exc_info.value)
    assert "msme_survival_rate" in str(exc_info.value)
    assert record is not None
    assert record.progress["phase"] == "metric_taxonomy_failed"
    assert record.progress["failure"]["code"] == "unknown_production_metric"


def test_nl_pipeline_records_metric_taxonomy_evidence_for_canonicalized_aliases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}

    def _capture_state(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        return {"run_id": payload["run_id"], "reports_index": {}}

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    _forbid_real_gateway_network(monkeypatch)
    monkeypatch.setattr("polisyos.fabric.retrieval.RetrievalService", _FakeRetrievalService)
    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _capture_state)
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.ensure_all_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.build_method_catalog_snapshot",
        lambda *, run_id=None: MethodCatalogSnapshot(
            snapshot_id=f"test-catalog-{run_id or 'run'}",
            run_id=run_id,
        ),
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.persist_method_catalog_snapshot",
        lambda _store, _snapshot: MethodCatalogSnapshotRef(artifact_id="sha256:" + "9" * 64),
    )
    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="research",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control-metric-taxonomy.sqlite3"),
            postgres_dsn=None,
        ),
        registry_providers=_registry_providers(),
    )

    try:
        service._execute_nl_pipeline(
            run_id="R_nl_metric_taxonomy",
            nl_request="Evaluate a serious MSME policy with an aliased outcome.",
            context=_intent_context(
                desired_outcome="msme_credit_volume",
                query_outcome="msme_credit_volume",
            ),
            domain_hint="Ukraine wartime MSME support policy",
            data_source=None,
            max_iterations=1,
            llm_models=["simulated-qwen"],
            max_parallel_models=1,
            run_budget_usd=None,
            per_model_budget_usd=None,
            checkpoint_policy="strict",
            execution_plan_ref=None,
            execution_plan_payload=None,
            stop_criteria_payload={},
            governance_constraints_payload=[],
            expected_outputs_payload=[],
            execution_profile="research",
            allow_mock_fallback=False,
        )
    finally:
        service.close()

    params = captured["payload"]["params"]
    evidence = params["metric_taxonomy_evidence"]
    assert params["query_outcome"] == "msme_loan_volume"
    assert evidence["taxonomy_version"]
    assert evidence["metric_count"] > 0
    assert evidence["canonicalizer"] == "production_metric_taxonomy.v1"
    assert evidence["fingerprint"].startswith("sha256:")
    assert params["metric_taxonomy_diagnostics"] == [
        {
            "path": "context.query_outcome",
            "raw": "msme_credit_volume",
            "normalized": "msme_loan_volume",
            "canonical_metric_id": "msme_loan_volume",
            "canonicalizer": "production_metric_taxonomy.v1",
            "taxonomy_version": evidence["taxonomy_version"],
            "reason": "alias",
        }
    ]


def test_nl_pipeline_derives_production_data_paths_from_root_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    production_data_root = tmp_path / "production_data"
    datasets_dir = production_data_root / "datasets_full_20990101"
    datasets_dir.mkdir(parents=True)
    (datasets_dir / "catalog.duckdb").touch()

    lex_dir = production_data_root / "lex" / "lex-20990101"
    (lex_dir / "finalize").mkdir(parents=True)
    (lex_dir / "finalize" / "legal.duckdb").touch()

    academic_dir = production_data_root / "academic_runtime_20990101"
    academic_component_dir = academic_dir / "academic"
    (academic_component_dir / "graph").mkdir(parents=True)
    (academic_component_dir / "graph" / "scholar.duckdb").touch()
    (academic_component_dir / "benchmark_suite.json").write_text("{}", encoding="utf-8")
    (academic_component_dir / "benchmark_report.json").write_text("{}", encoding="utf-8")
    (academic_component_dir / "runtime_demand_backlog.jsonl").touch()

    ukraine_root = production_data_root / "ukraine_sim_20990101"
    ukraine_bundles = ukraine_root / "production_bundle" / "bundles"
    for bundle in (
        "runtime_bundle_v9",
        "intervention_bundle_v9",
        "calibration_bundle_v9",
        "method_contract_bundle_v9",
    ):
        (ukraine_bundles / bundle).mkdir(parents=True)

    manifest = {
        "schema_version": "1.0",
        "bundles": {
            "datasets": {
                "version_id": "datasets_full_20990101",
                "path": "datasets_full_20990101",
                "catalog_db_path": "datasets_full_20990101/catalog.duckdb",
            },
            "lex": {
                "version_id": "lex-20990101",
                "path": "lex/lex-20990101",
                "legal_kg_db_path": "lex/lex-20990101/finalize/legal.duckdb",
            },
            "academic": {
                "version_id": "academic_runtime_20990101",
                "path": "academic_runtime_20990101",
                "component_path": "academic_runtime_20990101/academic",
                "academic_db_path": "academic_runtime_20990101/academic/graph/scholar.duckdb",
                "benchmark_suite_path": "academic_runtime_20990101/academic/benchmark_suite.json",
                "benchmark_report_path": "academic_runtime_20990101/academic/benchmark_report.json",
                "demand_backlog_path": (
                    "academic_runtime_20990101/academic/runtime_demand_backlog.jsonl"
                ),
            },
            "ukraine_simulation": {
                "version_id": "ukraine_sim_20990101",
                "path": "ukraine_sim_20990101",
                "runtime_bundle_dir": (
                    "ukraine_sim_20990101/production_bundle/bundles/runtime_bundle_v9"
                ),
                "intervention_bundle_dir": (
                    "ukraine_sim_20990101/production_bundle/bundles/intervention_bundle_v9"
                ),
                "calibration_bundle_dir": (
                    "ukraine_sim_20990101/production_bundle/bundles/calibration_bundle_v9"
                ),
                "method_contract_bundle_dir": (
                    "ukraine_sim_20990101/production_bundle/bundles/method_contract_bundle_v9"
                ),
            },
        },
    }
    (production_data_root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("POLISYOS_PRODUCTION_DATA_ROOT", raising=False)

    params = _build_scientist_context_params(
        {},
        domain_hint=None,
        execution_profile="research",
    )

    assert params["datasets_snapshot_dir"] == "production_data/datasets_full_20990101"
    assert params["datasets_db_path"] == "production_data/datasets_full_20990101/catalog.duckdb"
    assert params["legal_kg_db_path"] == "production_data/lex/lex-20990101/finalize/legal.duckdb"
    assert params["academic_db_path"] == (
        "production_data/academic_runtime_20990101/academic/graph/scholar.duckdb"
    )
    assert params["ukraine_runtime_bundle_dir"] == (
        "production_data/ukraine_sim_20990101/production_bundle/bundles/runtime_bundle_v9"
    )
    evidence_context = params["production_data_evidence_context"]
    assert evidence_context["manifest_sha256"].startswith("sha256:")
    assert evidence_context["bundles"]["datasets"]["version_id"] == "datasets_full_20990101"
    assert evidence_context["bundles"]["lex"]["version_id"] == "lex-20990101"


def test_nl_pipeline_materializes_data_snapshot_without_data_source(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}

    def _capture_state(payload: dict[str, Any], **kwargs: Any) -> None:
        captured["payload"] = payload
        captured["kwargs"] = kwargs

    monkeypatch.setattr("polisyos.fabric.retrieval.RetrievalService", _FakeRetrievalService)
    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _capture_state)
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.ensure_all_methods_registered",
        lambda: None,
    )

    def _build_test_catalog_snapshot(*, run_id: str | None = None) -> MethodCatalogSnapshot:
        return MethodCatalogSnapshot(snapshot_id=f"test-catalog-{run_id or 'run'}", run_id=run_id)

    def _persist_test_catalog_snapshot(
        _store: object,
        _snapshot: MethodCatalogSnapshot,
    ) -> MethodCatalogSnapshotRef:
        return MethodCatalogSnapshotRef(artifact_id="sha256:" + "1" * 64)

    monkeypatch.setattr(
        "polisyos.foundry.methods.build_method_catalog_snapshot",
        _build_test_catalog_snapshot,
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.persist_method_catalog_snapshot",
        _persist_test_catalog_snapshot,
    )
    from polisyos.common import async_tools

    real_run_coro_sync = async_tools.run_coro_sync

    def _run_coro_sync_with_load_budget(coro, *, timeout_seconds=None):
        timeout = 120.0 if timeout_seconds is None else timeout_seconds
        return real_run_coro_sync(coro, timeout_seconds=timeout)

    monkeypatch.setattr(async_tools, "run_coro_sync", _run_coro_sync_with_load_budget)
    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="dev",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control.sqlite3"),
            postgres_dsn=None,
        ),
        registry_providers=_registry_providers(),
    )

    try:
        result = service._execute_nl_pipeline_for_contract_testing(
            run_id="R_nl_materialize",
            nl_request="test request",
            context=_intent_context(requested_authority_level="dev"),
            domain_hint="fiscal",
            data_source=None,
            max_iterations=1,
            llm_models=[],
            max_parallel_models=1,
            run_budget_usd=None,
            per_model_budget_usd=None,
            checkpoint_policy="strict",
            execution_plan_ref=None,
            execution_plan_payload=None,
            stop_criteria_payload={},
            governance_constraints_payload=[],
            expected_outputs_payload=[],
        )
    finally:
        service.close()

    payload = captured["payload"]
    assert result["contract_testing_authority"] == {
        "authority_scope": "contract_testing",
        "production_promotable": False,
        "non_promotable_reason": "nl_mock_agents_contract_testing_only",
    }
    assert captured["kwargs"]["store"] is service._artifact_store
    inputs = payload["inputs"]
    assert "data_snapshot_ref" in inputs
    assert "input_bindings_ref" in inputs
    assert "registry_bundle_ref" in inputs


def test_nl_pipeline_can_run_simulated_llm_without_mock_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}

    def _capture_state(payload: dict[str, Any], **kwargs: Any) -> None:
        captured["payload"] = payload
        captured["kwargs"] = kwargs

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    _forbid_real_gateway_network(monkeypatch)
    monkeypatch.setattr("polisyos.fabric.retrieval.RetrievalService", _FakeRetrievalService)
    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _capture_state)
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.ensure_all_methods_registered",
        lambda: None,
    )

    def _build_test_catalog_snapshot(*, run_id: str | None = None) -> MethodCatalogSnapshot:
        return MethodCatalogSnapshot(snapshot_id=f"test-catalog-{run_id or 'run'}", run_id=run_id)

    def _persist_test_catalog_snapshot(
        _store: object,
        _snapshot: MethodCatalogSnapshot,
    ) -> MethodCatalogSnapshotRef:
        return MethodCatalogSnapshotRef(artifact_id="sha256:" + "2" * 64)

    monkeypatch.setattr(
        "polisyos.foundry.methods.build_method_catalog_snapshot",
        _build_test_catalog_snapshot,
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.persist_method_catalog_snapshot",
        _persist_test_catalog_snapshot,
    )
    from polisyos.common import async_tools

    real_run_coro_sync = async_tools.run_coro_sync

    def _run_coro_sync_with_load_budget(coro, *, timeout_seconds=None):
        timeout = 120.0 if timeout_seconds is None else timeout_seconds
        return real_run_coro_sync(coro, timeout_seconds=timeout)

    monkeypatch.setattr(async_tools, "run_coro_sync", _run_coro_sync_with_load_budget)
    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="dev",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control-progress.sqlite3"),
            postgres_dsn=None,
        ),
        registry_providers=_registry_providers(),
    )

    try:
        service._execute_nl_pipeline(
            run_id="R_nl_simulated_llm",
            nl_request="Розроби оптимальну політику підтримки МСП України у воєнний час.",
            context=_intent_context(requested_authority_level="dev"),
            domain_hint="Ukraine wartime MSME support policy",
            data_source=None,
            max_iterations=1,
            llm_models=["simulated-qwen"],
            max_parallel_models=1,
            run_budget_usd=None,
            per_model_budget_usd=None,
            checkpoint_policy="strict",
            execution_plan_ref=None,
            execution_plan_payload=None,
            stop_criteria_payload={},
            governance_constraints_payload=[],
            expected_outputs_payload=[],
            allow_mock_fallback=False,
        )
    finally:
        service.close()

    payload = captured["payload"]
    assert captured["kwargs"]["store"] is service._artifact_store
    params = payload["params"]
    variants = params["llm_model_variants"]

    assert params["llm_model"] == "simulated-qwen"
    assert variants[0]["status"] == "completed"
    assert variants[0]["provider"] == "gateway"
    assert variants[0]["verdict"] == "APPROVE"
    assert variants[0]["critic"]["issue_count"] == variants[0]["issue_count"]
    assert params["critic"]["issue_count"] == variants[0]["issue_count"]
    assert isinstance(variants[0]["critic"]["issues"], list)
    assert variants[0]["prompt_tokens"] > 0
    performance = params["run_performance_summary"]
    assert performance["schema_version"] == "1.0"
    assert performance["variants"]["completed"] == 1
    assert performance["llm"]["total_tokens"] == variants[0]["total_tokens"]
    assert performance["steps_by_action"]["create_problem_frame"]["count"] == 1
    assert performance["phase_budgets"]
    assert any(row["phase"] == "llm.total" for row in performance["phase_budgets"])
    assert "budget_summary" in performance
    assert "fallback_mock" not in variants[0].get("status", "")
    assert "data_snapshot_ref" in payload["inputs"]
    assert "input_bindings_ref" in payload["inputs"]


def test_serious_nl_pipeline_persists_normative_applicability_report_ref(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}

    def _capture_state(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        return {"run_id": payload["run_id"], "reports_index": {}}

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    _forbid_real_gateway_network(monkeypatch)
    monkeypatch.setattr("polisyos.fabric.retrieval.RetrievalService", _FakeRetrievalService)
    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _capture_state)
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.ensure_all_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.build_method_catalog_snapshot",
        lambda *, run_id=None: MethodCatalogSnapshot(
            snapshot_id=f"test-catalog-{run_id or 'run'}",
            run_id=run_id,
        ),
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.persist_method_catalog_snapshot",
        lambda _store, _snapshot: MethodCatalogSnapshotRef(artifact_id="sha256:" + "6" * 64),
    )

    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="research",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control-normative.sqlite3"),
            postgres_dsn=None,
        ),
        registry_providers=_registry_providers(),
    )
    job_id = "job_nl_normative"
    service._control_store.create_job(
        job_id=job_id,
        kind="natural_language_run",
        run_id="R_nl_normative",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="research",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )

    persisted_report: dict[str, Any] = {}
    try:
        service._execute_nl_pipeline(
            run_id="R_nl_normative",
            nl_request="Evaluate Ukraine MSME wartime support with legal constraints.",
            context=_normative_context(),
            domain_hint="Ukraine wartime MSME support policy",
            data_source=None,
            max_iterations=1,
            llm_models=["simulated-qwen"],
            max_parallel_models=1,
            run_budget_usd=None,
            per_model_budget_usd=None,
            checkpoint_policy="strict",
            execution_plan_ref=None,
            execution_plan_payload=None,
            stop_criteria_payload={},
            governance_constraints_payload=[],
            expected_outputs_payload=[],
            control_job_id=job_id,
            execution_profile="research",
            allow_mock_fallback=False,
            provider_preflight_payload={"status": "skipped", "reason": "simulation_mode"},
        )
        record = service._control_store.get_job(job_id)
        payload = captured["payload"]
        report_ref = payload["params"]["normative_applicability_report_ref"]
        persisted_report = from_canonical_bytes(
            service._artifact_store.get_bytes(ArtifactID(report_ref))
        )
    finally:
        service.close()

    payload = captured["payload"]
    params = payload["params"]
    report_ref = params["normative_applicability_report_ref"]

    assert report_ref.startswith("sha256:")
    assert params["runtime_quality_refs"]["normative_applicability_report_ref"] == report_ref
    assert params["runtime_quality_evidence"]["normative_evidence"]["status"] == "pass"
    assert payload["reports_index"]["normative_applicability_report_ref"]["artifact_id"] == (
        report_ref
    )
    assert persisted_report["status"] == "pass"
    assert persisted_report["applied_norms"][0]["norm_id"] == "norm.ua.credit_eligibility"
    assert record is not None
    assert record.progress["details"]["normative_applicability_report_ref"] == report_ref
    assert (
        record.progress["details"]["runtime_quality_evidence"]["normative_evidence"]["status"]
        == "pass"
    )


def test_serious_nl_pipeline_conflict_check_uses_active_corpus_constraints(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}

    def _capture_state(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        return {"run_id": payload["run_id"], "reports_index": {}}

    context = _normative_context()
    context["active_corpus_constraints"] = [
        {
            "constraint_id": "no_uncapped_subsidy",
            "constraint_type": "direct_prohibition",
            "norm_ref": "norm.ua.credit_eligibility",
            "prohibited_actions": ["Temporary targeted tax relief for verified high-need MSMEs."],
            "severity": "critical",
        }
    ]

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    _forbid_real_gateway_network(monkeypatch)
    monkeypatch.setattr("polisyos.fabric.retrieval.RetrievalService", _FakeRetrievalService)
    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _capture_state)
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.ensure_all_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.build_method_catalog_snapshot",
        lambda *, run_id=None: MethodCatalogSnapshot(
            snapshot_id=f"test-catalog-{run_id or 'run'}",
            run_id=run_id,
        ),
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.persist_method_catalog_snapshot",
        lambda _store, _snapshot: MethodCatalogSnapshotRef(artifact_id="sha256:" + "6" * 64),
    )

    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="research",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control-conflict-active-corpus.sqlite3"),
            postgres_dsn=None,
        ),
        registry_providers=_registry_providers(),
    )
    job_id = "job_nl_active_corpus_conflict"
    service._control_store.create_job(
        job_id=job_id,
        kind="natural_language_run",
        run_id="R_nl_active_corpus_conflict",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="research",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )

    try:
        result = service._execute_nl_pipeline(
            run_id="R_nl_active_corpus_conflict",
            nl_request="Evaluate Ukraine MSME wartime support with legal constraints.",
            context=context,
            domain_hint="Ukraine wartime MSME support policy",
            data_source=None,
            max_iterations=1,
            llm_models=["simulated-qwen"],
            max_parallel_models=1,
            run_budget_usd=None,
            per_model_budget_usd=None,
            checkpoint_policy="strict",
            execution_plan_ref=None,
            execution_plan_payload=None,
            stop_criteria_payload={},
            governance_constraints_payload=[],
            expected_outputs_payload=[],
            control_job_id=job_id,
            execution_profile="research",
            allow_mock_fallback=False,
            provider_preflight_payload={"status": "skipped", "reason": "simulation_mode"},
        )
        record = service._control_store.get_job(job_id)
        conflict_ref = result["conflict_check_ref"]
        conflict_report = from_canonical_bytes(
            service._artifact_store.get_bytes(ArtifactID(conflict_ref))
        )
    finally:
        service.close()

    conflict = conflict_report["conflicts"][0]
    assert conflict_report["status"] == "fail"
    assert conflict["code"] == "direct_prohibition_conflict"
    assert conflict["constraint_id"] == "no_uncapped_subsidy"
    assert conflict["norm_refs"] == ["norm.ua.credit_eligibility"]
    assert captured["payload"]["params"]["runtime_quality_refs"][
        "normative_applicability_report_ref"
    ]
    assert record is not None
    assert record.progress["details"]["runtime_quality_refs"]["conflict_check_ref"] == conflict_ref
    assert (
        record.progress["details"]["runtime_quality_evidence"]["conflict_check"]["status"] == "fail"
    )


@pytest.mark.parametrize("execution_profile", ["research", "governed", "production"])
def test_serious_nl_pipeline_phase_24_persists_runtime_quality_refs_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    execution_profile: str,
) -> None:
    captured: dict[str, Any] = {}

    def _capture_state(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        return {"run_id": payload["run_id"], "reports_index": {}}

    production_data_root = _write_phase_24_production_data_root(tmp_path)
    context = {
        **_normative_context(),
        "production_data_root": str(production_data_root),
        "query_outcome": "msme_survival_rate",
        "query_treatment": "wartime_credit_support",
        "requirements": ["use_production_data_materialization"],
        "tenant_id": "tenant-phase-24",
        "cell_id": "cell-phase-24",
    }

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    _forbid_real_gateway_network(monkeypatch)
    monkeypatch.setattr("polisyos.fabric.retrieval.RetrievalService", _FakeRetrievalService)
    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _capture_state)
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.ensure_all_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.build_method_catalog_snapshot",
        lambda *, run_id=None: MethodCatalogSnapshot(
            snapshot_id=f"test-catalog-{run_id or 'run'}",
            run_id=run_id,
        ),
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.persist_method_catalog_snapshot",
        lambda _store, _snapshot: MethodCatalogSnapshotRef(artifact_id="sha256:" + "7" * 64),
    )

    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile=execution_profile,
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / f"control-phase-24-{execution_profile}.sqlite3"),
            postgres_dsn=None,
        ),
        registry_providers=_registry_providers(),
    )
    job_id = f"job_phase_24_{execution_profile}"
    run_id = f"R_nl_phase_24_{execution_profile}"
    service._control_store.create_job(
        job_id=job_id,
        kind="natural_language_run",
        run_id=run_id,
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile=execution_profile,
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )

    try:
        result = service._execute_nl_pipeline(
            run_id=run_id,
            nl_request="Evaluate Ukraine MSME wartime support with production data.",
            context=context,
            domain_hint="Ukraine wartime MSME support policy",
            data_source=None,
            max_iterations=1,
            llm_models=["simulated-qwen"],
            max_parallel_models=1,
            run_budget_usd=None,
            per_model_budget_usd=None,
            checkpoint_policy="strict",
            execution_plan_ref=None,
            execution_plan_payload=None,
            stop_criteria_payload={"require_data_snapshot_or_bindings": True},
            governance_constraints_payload=[],
            expected_outputs_payload=[],
            control_job_id=job_id,
            execution_profile=execution_profile,
            allow_mock_fallback=False,
            provider_preflight_payload={"status": "skipped", "reason": "simulation_mode"},
        )
        record = service._control_store.get_job(job_id)
        params = captured["payload"]["params"]
        details = record.progress["details"] if record is not None else {}

        for report_key, ref_key in _PHASE_24_REQUIRED_RUNTIME_REFS.items():
            ref = result[ref_key]
            assert ref.startswith("sha256:")
            assert params["runtime_quality_refs"][ref_key] == ref
            assert details["runtime_quality_refs"][ref_key] == ref

            report = from_canonical_bytes(service._artifact_store.get_bytes(ArtifactID(ref)))
            evidence = params["runtime_quality_evidence"][report_key]
            progress_evidence = details["runtime_quality_evidence"][report_key]
            assert evidence[ref_key] == ref
            assert progress_evidence[ref_key] == ref
            assert evidence["authority_envelope_ref"].startswith("sha256:")
            assert evidence["runtime_event_ref"].startswith("sha256:")

            envelope = from_canonical_bytes(
                service._artifact_store.get_bytes(ArtifactID(evidence["authority_envelope_ref"]))
            )
            manifest = service._artifact_store.get_manifest(ArtifactID(ref))
            assert envelope["authority_role"] == "producer_authority"
            assert envelope["provenance_kind"] == "runtime_emitted"
            assert envelope["artifact_ref"] == ref
            assert envelope["cas_ref"] == ref
            assert envelope["run_id"] == run_id
            assert envelope["job_id"] == job_id
            assert manifest.authority is not None
            assert manifest.authority.authority_envelope_ref == evidence["authority_envelope_ref"]
            assert manifest.authority.diagnostic_event_ref == evidence["runtime_event_ref"]
            assert manifest.authority.payload_sha256 == manifest.integrity.sha256
            reconciliation = reconcile_authority_ref(
                artifact_store=service._artifact_store,
                event_log=service._diagnostic_event_log,
                cas_ref=ref,
                expected_tenant_id="tenant-phase-24",
                expected_cell_id="cell-phase-24",
                expected_run_id=run_id,
                expected_job_id=job_id,
            )
            assert reconciliation.status == "pass"
            assert report["status"] in {"pass", "fail", "warn", "blocked"}

        assert record is not None
        assert details["runtime_quality_projection"]["authority_role"] == "projection_only"
        assert details["runtime_quality_projection"]["surface"] == "runtime.progress"
        assert details["diagnostic_event_log_ref"].startswith("sha256:")
        event_refs = {
            event["runtime_cas_ref"]
            for event in details["diagnostic_events"]
            if event.get("runtime_cas_ref")
        }
        assert {result[key] for key in _PHASE_24_REQUIRED_RUNTIME_REFS.values()} <= event_refs
        event_ref_keys = [
            event["ref_key"] for event in details["diagnostic_events"] if event.get("ref_key")
        ]
        assert len(event_ref_keys) == len(set(event_ref_keys))

        closure_identity_fields = (
            "closure_sha256",
            "run_id",
            "job_id",
            "tenant_id",
            "cell_id",
            "policy_intent_ref",
            "time_context_ref",
            "production_data_manifest_ref",
            "legal_snapshot_ref",
            "method_plan_ref",
            "provider_mode_ref",
            "effective_mode_ref",
            "degradation_ledger_ref",
        )
        closure_identities = set()
        for report_key in _PHASE_24_REQUIRED_RUNTIME_REFS:
            envelope = params["runtime_quality_evidence"][report_key]["authority_envelope"]
            closure = envelope["same_input_closure"]
            closure_identities.add(
                tuple(closure.get(field) for field in closure_identity_fields)
            )
        assert len(closure_identities) == 1
    finally:
        service.close()


def test_serious_nl_pipeline_materializes_policy_intent_before_scientist_workflow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}

    def _capture_state(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        return {"run_id": payload["run_id"], "reports_index": {}}

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    _forbid_real_gateway_network(monkeypatch)
    monkeypatch.setattr("polisyos.fabric.retrieval.RetrievalService", _FakeRetrievalService)
    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _capture_state)
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.ensure_all_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.build_method_catalog_snapshot",
        lambda *, run_id=None: MethodCatalogSnapshot(
            snapshot_id=f"test-catalog-{run_id or 'run'}",
            run_id=run_id,
        ),
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.persist_method_catalog_snapshot",
        lambda _store, _snapshot: MethodCatalogSnapshotRef(artifact_id="sha256:" + "7" * 64),
    )

    context = {
        **_normative_context(),
        "tenant_id": "tenant-intent",
        "cell_id": "cell-intent",
        "jurisdiction": "UA",
        "target_population": "wartime MSMEs",
        "policy_time": "2026-05-15",
        "data_time": "2024-2026",
        "policy_problem": "Wartime MSMEs face liquidity constraints.",
        "desired_outcome": "msme survival",
        "proposed_intervention": "targeted credit support",
        "requester_preferred_conclusion": "expand credit support",
        "requested_authority_level": "research",
        "query_outcome": "msme_survival_rate",
        "query_treatment": "wartime_credit_support",
    }
    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="research",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control-policy-intent.sqlite3"),
            postgres_dsn=None,
        ),
        registry_providers=_registry_providers(),
    )

    try:
        result = service._execute_nl_pipeline(
            run_id="R_policy_intent_materialized",
            nl_request="Evaluate Ukraine MSME wartime credit support.",
            context=context,
            domain_hint="Ukraine wartime MSME support policy",
            data_source=None,
            max_iterations=1,
            llm_models=["simulated-qwen"],
            max_parallel_models=1,
            run_budget_usd=None,
            per_model_budget_usd=None,
            checkpoint_policy="strict",
            execution_plan_ref=None,
            execution_plan_payload=None,
            stop_criteria_payload={},
            governance_constraints_payload=[],
            expected_outputs_payload=[],
            execution_profile="research",
            allow_mock_fallback=False,
            provider_preflight_payload={"status": "skipped", "reason": "simulation_mode"},
        )
        intent_ref = result["policy_intent_envelope_ref"]
        capability_ledger_ref = result["policy_design_capability_ledger_ref"]
        concept_spine_ref = result["concept_spine_ref"]
        jurisdiction_spine_ref = result["jurisdiction_spine_ref"]
        policy_design_case_ref = result["policy_design_case_ref"]
        intent_payload = from_canonical_bytes(
            service._artifact_store.get_bytes(ArtifactID(intent_ref))
        )
        capability_ledger_payload = from_canonical_bytes(
            service._artifact_store.get_bytes(ArtifactID(capability_ledger_ref))
        )
        policy_design_case_payload = from_canonical_bytes(
            service._artifact_store.get_bytes(ArtifactID(policy_design_case_ref))
        )
    finally:
        service.close()

    params = captured["payload"]["params"]
    runtime_evidence = params["runtime_quality_evidence"]

    assert intent_ref.startswith("sha256:")
    assert params["policy_intent_envelope_ref"] == intent_ref
    assert params["policy_intent_ref"] == intent_ref
    assert params["context"]["policy_intent_ref"] == intent_ref
    assert params["runtime_quality_refs"]["policy_intent_envelope_ref"] == intent_ref
    assert params["runtime_quality_refs"]["policy_design_capability_ledger_ref"] == (
        capability_ledger_ref
    )
    assert params["runtime_quality_refs"]["concept_spine_ref"] == concept_spine_ref
    assert params["runtime_quality_refs"]["jurisdiction_spine_ref"] == jurisdiction_spine_ref
    assert params["runtime_quality_refs"]["policy_design_case_ref"] == policy_design_case_ref
    assert intent_payload["requester_preferred_conclusion"] == "expand credit support"
    assert intent_payload["challenge_depth_policy"]["depth"] == "heightened"
    assert capability_ledger_payload["literature_evidence_required"] is True
    assert capability_ledger_payload["ledger_ref"] == (
        "policy-design-capability-ledger:R_policy_intent_materialized"
    )
    assert {duty["capability"] for duty in capability_ledger_payload["duties"]} == {
        "lex",
        "fabric",
        "scholar",
        "foundry",
        "scientist",
        "compiler",
        "review",
        "publication",
        "audit",
    }
    assert policy_design_case_payload["intent_envelope"]["intent_id"] == (
        "intent-R_policy_intent_materialized"
    )
    assert policy_design_case_payload["capability_ledger"]["ledger_ref"] == (
        capability_ledger_payload["ledger_ref"]
    )
    assert policy_design_case_payload["nodes"][0]["node_type"] == "concept_spine"
    assert policy_design_case_payload["jurisdiction_spine"]["jurisdiction_spine_ref"] == (
        jurisdiction_spine_ref
    )
    assert runtime_evidence["policy_intent_envelope"]["runtime_event_ref"].startswith("sha256:")
    assert runtime_evidence["policy_design_capability_ledger"][
        "runtime_event_ref"
    ].startswith("sha256:")
    assert runtime_evidence["policy_design_case"]["runtime_event_ref"].startswith("sha256:")
    for report_key, evidence in runtime_evidence.items():
        if report_key == "policy_intent_envelope":
            continue
        envelope = evidence.get("authority_envelope")
        if isinstance(envelope, dict):
            assert envelope["same_input_closure"]["policy_intent_ref"] == intent_ref


def test_serious_nl_pipeline_blocks_missing_jurisdiction_before_scientist_workflow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}

    def _capture_state(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        return {"run_id": payload["run_id"], "reports_index": {}}

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    _forbid_real_gateway_network(monkeypatch)
    monkeypatch.setattr("polisyos.fabric.retrieval.RetrievalService", _FakeRetrievalService)
    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _capture_state)
    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="research",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control-policy-intent-missing.sqlite3"),
            postgres_dsn=None,
        ),
        registry_providers=_registry_providers(),
    )
    context = {
        "tenant_id": "tenant-intent",
        "cell_id": "cell-intent",
        "target_population": "wartime MSMEs",
        "policy_time": "2026-05-15",
        "data_time": "2024-2026",
        "policy_problem": "Wartime MSMEs face liquidity constraints.",
        "desired_outcome": "msme survival",
        "proposed_intervention": "targeted credit support",
        "requester_preferred_conclusion": None,
        "requested_authority_level": "research",
    }

    try:
        with pytest.raises(
            PolicyDesignCaseAuthorityError,
            match="policy_intent_jurisdiction_missing",
        ):
            service._execute_nl_pipeline(
                run_id="R_policy_intent_missing_jurisdiction",
                nl_request="Evaluate Ukraine MSME wartime credit support.",
                context=context,
                domain_hint="Ukraine wartime MSME support policy",
                data_source=None,
                max_iterations=1,
                llm_models=["simulated-qwen"],
                max_parallel_models=1,
                run_budget_usd=None,
                per_model_budget_usd=None,
                checkpoint_policy="strict",
                execution_plan_ref=None,
                execution_plan_payload=None,
                stop_criteria_payload={},
                governance_constraints_payload=[],
                expected_outputs_payload=[],
                execution_profile="research",
                allow_mock_fallback=False,
                provider_preflight_payload={"status": "skipped", "reason": "simulation_mode"},
            )
    finally:
        service.close()

    assert "payload" not in captured


def test_canary_evidence_writes_normative_evidence_from_runtime_output(
    tmp_path: Path,
) -> None:
    normative_evidence = {
        "status": "pass",
        "target_context": {
            "jurisdiction": "UA",
            "policy_domain": "wartime_msme_support",
            "as_of": "2026-05-12",
        },
        "legal_corpus_snapshot": {
            "snapshot_ref": "sha256:" + "6" * 64,
            "store_kind": "runtime_lex_candidate_norms",
            "candidate_norm_count": 1,
        },
        "query_terms": [
            "wartime_msme_support",
            "UA",
            "Target wartime credit support to eligible MSMEs.",
        ],
        "candidate_norms": [_normative_context()["lex_candidate_norms"][0]],
        "applied_norms": [_normative_context()["lex_candidate_norms"][0]],
        "recommendation_coverage": [
            {
                "claim_id": "rec_1",
                "major": True,
                "norm_refs": ["norm.ua.credit_eligibility"],
            }
        ],
        "issues": [],
    }

    output = assemble_canary_evidence(
        output_root=tmp_path,
        canary_kind="production",
        job_payload={
            "job_id": "job-runtime-normative",
            "run_id": "R_runtime_normative",
            "state": "completed",
            "progress": {
                "details": {
                    "normative_applicability_report_ref": "sha256:" + "5" * 64,
                    "runtime_quality_evidence": {
                        "normative_evidence": normative_evidence,
                    },
                }
            },
        },
        provider_preflight={"status": "passed"},
        quality_evidence={
            "fabric_retrieval_trace": {"status": "pass"},
            "foundry_method_report": {"status": "pass"},
            "policy_grounding_matrix": {"status": "pass"},
            "conflict_check": {"status": "pass"},
        },
    )

    evidence_path = output / "quality_evidence" / "normative_evidence.json"
    persisted = json.loads(evidence_path.read_text(encoding="utf-8"))

    assert evidence_path.exists()
    assert persisted["status"] == "pass"
    assert persisted["applied_norms"][0]["norm_id"] == "norm.ua.credit_eligibility"


def test_production_data_canary_materializes_local_lane_without_external_fetch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}
    production_data_root = tmp_path / "production_data"
    datasets_dir = production_data_root / "datasets_full_20990101"
    curated_dir = production_data_root / "canonical/local_data_20990101/policy_engine_data/curated"
    datasets_dir.mkdir(parents=True)
    curated_dir.mkdir(parents=True)
    (datasets_dir / "dataset_catalog.duckdb").touch()
    (datasets_dir / "panel.csv").write_text(
        "\n".join(
            [
                "entity_id,period,geography,population,msme_survival_rate,macro.gdp,us.macro.gdp_nominal,wartime_credit_support,label_quality",
                "ua-msme-1,2026-01-31,UKR,wartime_msme,0.84,1.0,1000,1,audited",
                "ua-msme-2,2026-02-28,UKR,wartime_msme,0.88,1.1,1100,0,audited",
                "ua-msme-3,2026-03-31,UKR,wartime_msme,0.81,1.2,1200,1,audited",
            ]
        ),
        encoding="utf-8",
    )
    (datasets_dir / "data_dictionary.json").write_text(
        json.dumps(
            {
                "columns": {
                    "entity_id": {"description": "Entity id", "role": "entity_id"},
                    "period": {"description": "Period", "role": "time"},
                    "geography": {"description": "Country", "role": "geography"},
                    "population": {"description": "Population", "role": "population"},
                    "msme_survival_rate": {
                        "description": "MSME survival rate",
                        "metric_id": "msme_survival_rate",
                        "unit": "rate",
                    },
                    "macro.gdp": {
                        "description": "GDP value used by fake runtime data need extractor",
                        "metric_id": "macro.gdp",
                        "unit": "index",
                    },
                    "us.macro.gdp_nominal": {
                        "description": "Nominal GDP used by fake runtime data need extractor",
                        "metric_id": "us.macro.gdp_nominal",
                        "unit": "usd",
                    },
                    "wartime_credit_support": {
                        "description": "Credit support treatment",
                        "metric_id": "wartime_credit_support",
                        "unit": "binary",
                    },
                    "label_quality": {"description": "Label quality", "role": "label_quality"},
                },
                "entity_id_columns": ["entity_id"],
                "time_columns": ["period"],
                "geography_columns": ["geography"],
                "population_columns": ["population"],
                "updated_at": "2026-05-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "1.0",
        "generated_at": "2026-05-01T00:00:00Z",
        "bundles": {
            "curated": {
                "role": "fabric_curated_catalog",
                "version_id": "local_data_20990101",
                "readiness": "ready",
                "path": "canonical/local_data_20990101/policy_engine_data/curated",
                "required_files": [
                    "data_contracts.json",
                    "source_bindings.json",
                    "source_contracts_v2.json",
                ],
            },
            "datasets": {
                "version_id": "datasets_full_20990101",
                "readiness": "ready",
                "path": "datasets_full_20990101",
                "catalog_db_path": "datasets_full_20990101/dataset_catalog.duckdb",
                "dataset_path": "datasets_full_20990101/panel.csv",
                "data_dictionary_path": "datasets_full_20990101/data_dictionary.json",
            }
        },
    }
    (production_data_root / "manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    (curated_dir / "data_contracts.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "contracts": [
                    {
                        "contract_id": "contract.production_msme_panel",
                        "dataset_identity": "dataset:prod-msme-panel:202605",
                        "source_family": "production_msme_panel",
                        "source_contract_ref": "source-contract:production_msme_panel:v1",
                        "source_rights": "public_sector_reuse",
                        "dictionary_ref": "dictionary:prod-msme-panel:v1",
                        "schema_ref": "schema:prod-msme-panel:v1",
                        "field_refs": [
                            "field:prod-msme-panel.entity_id",
                            "field:prod-msme-panel.msme_survival_rate",
                            "field:prod-msme-panel.wartime_credit_support",
                        ],
                        "unit_refs": ["unit:rate", "unit:binary"],
                        "geography_refs": ["UA"],
                        "time_coverage_refs": ["2024-2026"],
                        "quality_refs": ["quality:prod-msme-panel:v1"],
                        "missingness_refs": ["missingness:prod-msme-panel:v1"],
                        "lineage_refs": ["lineage:prod-msme-panel:v1"],
                        "transformation_refs": ["transform:prod-msme-panel:v1"],
                        "derived_feature_bindings": ["feature:msme_survival_rate"],
                        "freshness_ref": "freshness:prod-msme-panel:2026-05-01",
                        "recency_ref": "freshness:prod-msme-panel:2026-05-01",
                        "quality_assertion_refs": ["quality-assertion:prod-msme-panel:v1"],
                        "construct_validity_refs": ["construct:msme_survival_rate:v1"],
                        "outlier_refs": ["outliers:prod-msme-panel:v1"],
                        "claim_bindability_refs": ["claim-bindability:prod-msme-panel:v1"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (curated_dir / "source_bindings.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "bindings": [
                    {
                        "binding_id": "binding.production_msme_panel",
                        "contract_id": "contract.production_msme_panel",
                        "scenario_source_family": "production_msme_panel",
                        "connector_id": "production.msme_panel",
                        "dataset_id": "wartime_msme_panel",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (curated_dir / "source_contracts_v2.json").write_text(
        json.dumps(
            {
                "schema_version": "fabric.source_contract.v2",
                "contracts": {
                    "source-contract:production_msme_panel:v1": {
                        "id": "source-contract:production_msme_panel:v1",
                        "version": "1.1.0",
                        "status": "active",
                        "content_hash": "sha256:" + "c" * 64,
                        "contract": {
                            "id": "source-contract:production_msme_panel:v1",
                            "version": "1.1.0",
                            "status": "active",
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    scenario_evidence_contract = {
        "schema_version": "policyos.scenario_evidence_contract.v1",
        "contract_id": "scenario-evidence-contract:ukraine_msme_wartime_credit_support:v1",
        "scenario_id": "ukraine_msme_wartime_credit_support",
        "requirements": [
            {
                "requirement_id": (
                    "scenario:ukraine_msme_wartime_credit_support:data:"
                    "production_msme_panel"
                ),
                "domain": "data",
                "expected_family": "production_msme_panel",
                "required_facets": [
                    "source_rights",
                    "dictionary_ref",
                    "schema_ref",
                    "field_refs",
                    "unit_refs",
                    "geography_refs",
                    "time_coverage_refs",
                    "quality_refs",
                    "missingness_refs",
                    "lineage_refs",
                    "transformation_refs",
                    "derived_feature_bindings",
                ],
                "claim_scope": ["major_recommendations"],
            }
        ],
    }

    def _capture_state(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        return {"run_id": payload["run_id"], "reports_index": {}}

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    _forbid_real_gateway_network(monkeypatch)
    _ExternalFetchBlockedRetrievalService.execute_called = False
    monkeypatch.setattr(
        "polisyos.fabric.retrieval.RetrievalService",
        _ExternalFetchBlockedRetrievalService,
    )
    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _capture_state)
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.ensure_all_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.build_method_catalog_snapshot",
        lambda *, run_id=None: MethodCatalogSnapshot(
            snapshot_id=f"test-catalog-{run_id or 'run'}",
            run_id=run_id,
        ),
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.persist_method_catalog_snapshot",
        lambda _store, _snapshot: MethodCatalogSnapshotRef(artifact_id="sha256:" + "8" * 64),
    )

    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="research",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control-production-data.sqlite3"),
            postgres_dsn=None,
        ),
        registry_providers=_registry_providers(),
    )
    job_id = "job_production_data_lane"
    service._control_store.create_job(
        job_id=job_id,
        kind="natural_language_run",
        run_id="R_nl_production_data_lane",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="research",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )

    try:
        service._execute_nl_pipeline(
            run_id="R_nl_production_data_lane",
            nl_request="Evaluate Ukraine MSME wartime support with production data.",
            context=_intent_context(
                production_data_root=str(production_data_root),
                query_outcome="msme_survival_rate",
                query_treatment="wartime_credit_support",
                requirements=["use_production_data_materialization"],
                scenario_evidence_contract=scenario_evidence_contract,
                scenario_evidence_contract_id=scenario_evidence_contract["contract_id"],
            ),
            domain_hint="Ukraine wartime MSME support policy",
            data_source=None,
            max_iterations=1,
            llm_models=["simulated-qwen"],
            max_parallel_models=1,
            run_budget_usd=None,
            per_model_budget_usd=None,
            checkpoint_policy="strict",
            execution_plan_ref=None,
            execution_plan_payload=None,
            stop_criteria_payload={"require_data_snapshot_or_bindings": True},
            governance_constraints_payload=[],
            expected_outputs_payload=[],
            control_job_id=job_id,
            allow_mock_fallback=False,
            provider_preflight_payload={"status": "skipped", "reason": "simulation_mode"},
        )
        record = service._control_store.get_job(job_id)
        production_quality_ref = captured["payload"]["params"]["auto_data_source_refs"][
            "production_data_quality_report_ref"
        ]
        privacy_compliance_ref = captured["payload"]["params"]["runtime_quality_refs"][
            "privacy_compliance_report_ref"
        ]
        production_quality_report = from_canonical_bytes(
            service._artifact_store.get_bytes(ArtifactID(production_quality_ref))
        )
        privacy_compliance_report = from_canonical_bytes(
            service._artifact_store.get_bytes(ArtifactID(privacy_compliance_ref))
        )
    finally:
        service.close()

    assert _ExternalFetchBlockedRetrievalService.execute_called is False
    payload = captured["payload"]
    inputs = payload["inputs"]
    assert "data_snapshot_ref" in inputs
    assert "input_bindings_ref" in inputs
    assert "registry_bundle_ref" in inputs
    variant = payload["params"]["llm_model_variants"][0]
    refs = variant["auto_data_source_refs"]
    assert refs["quality_report_ref"].startswith("sha256:")
    assert refs["production_data_quality_report_ref"].startswith("sha256:")
    assert variant["retrieval_context"]["production_data_evidence_context"]["root"] == str(
        production_data_root
    )
    production_quality_ref = refs["production_data_quality_report_ref"]
    assert production_quality_report["status"] in {"pass", "warn", "fail"}
    assert production_quality_report["claim_diagnostics"]
    assert production_quality_report["source_bundle_versions"] == {
        "curated": "local_data_20990101",
        "datasets": "datasets_full_20990101",
    }
    assert production_quality_report["data_snapshot_ref"] == refs["data_snapshot_ref"]
    assert payload["params"]["production_data_quality_report_ref"] == production_quality_ref
    assert payload["params"]["runtime_quality_refs"]["production_data_quality_report_ref"] == (
        production_quality_ref
    )
    assert payload["params"]["privacy_compliance_report_ref"] == privacy_compliance_ref
    assert payload["params"]["runtime_quality_refs"]["privacy_compliance_report_ref"] == (
        privacy_compliance_ref
    )
    assert payload["reports_index"]["privacy_compliance_report_ref"]["artifact_id"] == (
        privacy_compliance_ref
    )
    assert privacy_compliance_report["status"] == "pass"
    assert privacy_compliance_report["summary"]["production_data_source_count"] >= 1
    assert privacy_compliance_report["summary"]["public_artifact_family_count"] >= 1
    assert payload["reports_index"]["production_data_quality_report_ref"]["artifact_id"] == (
        production_quality_ref
    )
    fabric_trace = variant["retrieval_context"]["production_data_evidence_context"][
        "fabric_retrieval_trace"
    ]
    assert fabric_trace["scenario_evidence_contract_id"] == scenario_evidence_contract[
        "contract_id"
    ]
    assert fabric_trace["selected_contract_binding"]["status"] == "satisfied"
    assert fabric_trace["selected_contract_binding"]["expected_family"] == (
        "production_msme_panel"
    )
    assert fabric_trace["selected_contract_bindings"][0]["candidate_ref"] == (
        "production_data:curated:production_msme_panel:contract.production_msme_panel"
    )
    assert fabric_trace["selected_sources"][0]["selection_status"] == (
        "claim_admissible_contract_selected"
    )
    assert fabric_trace["selected_sources"][0]["authority_surface"] == (
        "claim_admissible_contract"
    )
    assert fabric_trace["fabric_spine_bindings"]["consumed_requirement_ids"] == [
        "scenario:ukraine_msme_wartime_credit_support:data:production_msme_panel"
    ]
    assert fabric_trace["fabric_spine_bindings"]["selected_contract_binding_refs"] == [
        "production_data:curated:production_msme_panel:contract.production_msme_panel"
    ]
    assert fabric_trace["source_family_blockers"] == []
    assert variant["retrieval_context"]["production_data_evidence_context"][
        "fabric_spine_bindings"
    ]["selected_contract_binding_refs"] == [
        "production_data:curated:production_msme_panel:contract.production_msme_panel"
    ]
    assert variant["retrieval_context"]["fabric_spine_bindings"][
        "consumed_requirement_ids"
    ] == [
        "scenario:ukraine_msme_wartime_credit_support:data:production_msme_panel"
    ]
    assert variant["retrieval_context"]["production_data_evidence_context"][
        "scenario_binding_findings"
    ][0]["status"] == "satisfied"
    assert record is not None
    progress_variant = record.progress["variants"]["simulated_qwen_1"]
    assert progress_variant["production_data_evidence_context"]["root"] == str(production_data_root)
    assert progress_variant["production_data_evidence_context"]["manifest_sha256"]
    assert any(
        item.get("production_data_quality_report_ref") == production_quality_ref
        for item in progress_variant["production_data_evidence_context"]["timeline"]
    )
    assert any(
        item.get("production_data_quality_report_ref") == production_quality_ref
        for item in progress_variant["production_data_evidence_context"]["lineage"]
    )


def test_serious_nl_pipeline_persists_foundry_method_report_from_final_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}

    def _capture_state(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        captured["payload"] = payload
        store = kwargs["store"]
        method_result_ref = store.put_json(
            {
                "report": {
                    "method": "difference_in_differences",
                    "status": "success",
                    "estimand": "ATT",
                    "point_estimate": 0.04,
                    "standard_error": 0.01,
                    "confidence_interval": [0.01, 0.07],
                    "confidence_level": 0.95,
                    "inference_method": "bootstrap",
                    "assumptions": {
                        "parallel_trends": "pass",
                        "stable_composition": "pass",
                    },
                    "sample_size": 240,
                    "n_treated": 120,
                    "n_control": 120,
                    "diagnostics": [
                        {"test_name": "parallel_trends", "passed": True},
                        {
                            "test_name": "missingness_rate",
                            "passed": True,
                            "details": {"missing_rate": 0.02},
                        },
                    ],
                    "metadata": {
                        "sensitivity": {"status": "pass", "robustness": "moderate"},
                        "min_required_sample_size": 30,
                    },
                }
            },
            ArtifactWriteOptions(
                kind="scientist.method_result.causal",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.scientist.MethodResult", version="0.1.0"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        method_surface_refs: dict[str, str] = {}
        method_surface_inputs: list[InputRef] = []
        surface_ref_keys = {
            "identification": "identification_ref",
            "transportability": "transportability_ref",
            "partial_identification": "partial_identification_ref",
            "recoverability": "recoverability_ref",
            "causal_ensemble": "causal_ensemble_ref",
            "falsification": "falsification_ref",
            "certificate_proof": "proof_bundle_ref",
        }
        for surface_name, ref_key in surface_ref_keys.items():
            surface_ref = store.put_json(
                {
                    "surface": surface_name,
                    "status": "pass",
                    "method_result_ref": str(method_result_ref.artifact_id),
                },
                ArtifactWriteOptions(
                    kind=f"foundry.method_validity.{surface_name}",
                    media_type="application/json",
                    schema=SchemaInfo(
                        name="polisyos.foundry.MethodValiditySurface",
                        version="1.0",
                    ),
                    inputs=[
                        InputRef(
                            artifact_id=method_result_ref.artifact_id,
                            role="method_result",
                        )
                    ],
                ),
                canon_spec=CanonSpec(forbid_floats=False),
            )
            method_surface_refs[ref_key] = str(surface_ref.artifact_id)
            method_surface_inputs.append(
                InputRef(
                    artifact_id=surface_ref.artifact_id,
                    role=f"validity_surface:{surface_name}",
                )
            )
        method_evidence_ref = store.put_json(
            {
                "method_fqn": "causal.inference.difference_in_differences@1.0.0",
                "backend": "numpy",
                "result_ref": str(method_result_ref.artifact_id),
                **method_surface_refs,
            },
            ArtifactWriteOptions(
                kind="scientist.method_evidence",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.MethodExecutionEvidence",
                    version="0.1.0",
                ),
                inputs=[
                    InputRef(
                        artifact_id=method_result_ref.artifact_id,
                        role="method_result",
                    ),
                    *method_surface_inputs,
                ],
            ),
        )
        return {
            "run_id": payload["run_id"],
            "inputs": payload["inputs"],
            "params": payload["params"],
            "artifacts_index": {
                "causal_method_result_ref": method_result_ref.model_dump(mode="json"),
                "causal_method_evidence_ref": method_evidence_ref.model_dump(mode="json"),
            },
            "reports_index": {},
        }

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    _forbid_real_gateway_network(monkeypatch)
    monkeypatch.setattr("polisyos.fabric.retrieval.RetrievalService", _FakeRetrievalService)
    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _capture_state)
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.ensure_all_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.build_method_catalog_snapshot",
        lambda *, run_id=None: MethodCatalogSnapshot(
            snapshot_id=f"test-catalog-{run_id or 'run'}",
            run_id=run_id,
        ),
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.persist_method_catalog_snapshot",
        lambda _store, _snapshot: MethodCatalogSnapshotRef(artifact_id="sha256:" + "9" * 64),
    )

    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="research",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control-method-report.sqlite3"),
            postgres_dsn=None,
        ),
        registry_providers=_registry_providers(),
    )
    job_id = "job_foundry_method_report"
    service._control_store.create_job(
        job_id=job_id,
        kind="natural_language_run",
        run_id="R_nl_method_report",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="research",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )

    try:
        result = service._execute_nl_pipeline(
            run_id="R_nl_method_report",
            nl_request="Evaluate Ukraine MSME support using causal evidence.",
            context=_intent_context(),
            domain_hint="Ukraine wartime MSME support policy",
            data_source=None,
            max_iterations=1,
            llm_models=["simulated-qwen"],
            max_parallel_models=1,
            run_budget_usd=None,
            per_model_budget_usd=None,
            checkpoint_policy="strict",
            execution_plan_ref=None,
            execution_plan_payload=None,
            stop_criteria_payload={},
            governance_constraints_payload=[],
            expected_outputs_payload=[],
            control_job_id=job_id,
            execution_profile="research",
            allow_mock_fallback=False,
            provider_preflight_payload={"status": "skipped", "reason": "simulation_mode"},
        )
        record = service._control_store.get_job(job_id)
        report_ref = result["foundry_method_report_ref"]
        grounding_ref = result["policy_grounding_matrix_ref"]
        conflict_ref = result["conflict_check_ref"]
        report = from_canonical_bytes(service._artifact_store.get_bytes(ArtifactID(report_ref)))
        grounding_report = from_canonical_bytes(
            service._artifact_store.get_bytes(ArtifactID(grounding_ref))
        )
        conflict_report = from_canonical_bytes(
            service._artifact_store.get_bytes(ArtifactID(conflict_ref))
        )
    finally:
        service.close()

    auto_refs = captured["payload"]["params"]["auto_data_source_refs"]
    selected = report["selected_methods"][0]
    assert report_ref.startswith("sha256:")
    assert report["status"] == "pass"
    assert report["foundry_input_refs"]["data_snapshot_ref"] == auto_refs["data_snapshot_ref"]
    assert report["foundry_input_refs"]["input_bindings_ref"] == auto_refs["input_bindings_ref"]
    assert selected["input_refs"]["data_snapshot_ref"] == auto_refs["data_snapshot_ref"]
    assert selected["input_refs"]["input_bindings_ref"] == auto_refs["input_bindings_ref"]
    assert selected["method_id"] == "causal.inference.difference_in_differences@1.0.0"
    assert grounding_ref.startswith("sha256:")
    assert conflict_ref.startswith("sha256:")
    assert grounding_report["schema_version"] == "policyos.scientist.policy_grounding_matrix.v1"
    assert grounding_report["claim_extraction"]["extraction_status"] in {
        "pass",
        "review_required",
    }
    assert conflict_report["schema_version"] == "policyos.lex.policy_conflict_check.v1"
    assert record is not None
    assert record.progress["foundry_method_report_ref"] == report_ref
    assert record.progress["policy_grounding_matrix_ref"] == grounding_ref
    assert record.progress["conflict_check_ref"] == conflict_ref
    assert (
        record.progress["variants"]["simulated_qwen_1"]["foundry_method_report_ref"] == report_ref
    )


def test_nl_pipeline_passes_resolved_curated_dir_to_llm_data_need_extractor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}
    curated_dir = tmp_path / "production_data" / "canonical" / "curated"
    curated_dir.mkdir(parents=True)

    class _CapturingDataNeedExtractor:
        def __init__(self, *args: Any, curated_dir: Path, **kwargs: Any) -> None:
            del args, kwargs
            captured["curated_dir"] = curated_dir

        async def extract_data_needs(self, _problem_frame: object) -> list[Any]:
            return []

    def _capture_state(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        return {"run_id": payload["run_id"], "reports_index": {}}

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    monkeypatch.setenv("POLISYOS_CURATED_DIR", str(curated_dir))
    _forbid_real_gateway_network(monkeypatch)
    monkeypatch.setattr(
        "polisyos.scientist.agent.data_need_extractor.LLMDataNeedExtractorAgent",
        _CapturingDataNeedExtractor,
    )
    monkeypatch.setattr("polisyos.fabric.retrieval.RetrievalService", _FakeRetrievalService)
    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _capture_state)
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.ensure_all_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.build_method_catalog_snapshot",
        lambda *, run_id=None: MethodCatalogSnapshot(
            snapshot_id=f"test-catalog-{run_id or 'run'}",
            run_id=run_id,
        ),
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.persist_method_catalog_snapshot",
        lambda _store, _snapshot: MethodCatalogSnapshotRef(artifact_id="sha256:" + "7" * 64),
    )

    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="dev",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control-gateway-failed.sqlite3"),
            postgres_dsn=None,
        ),
        registry_providers=_registry_providers(),
    )

    try:
        service._execute_nl_pipeline(
            run_id="R_nl_curated_dir",
            nl_request="Evaluate an MSME policy.",
            context=_intent_context(requested_authority_level="dev"),
            domain_hint="Ukraine wartime MSME support policy",
            data_source=None,
            max_iterations=1,
            llm_models=["simulated-qwen"],
            max_parallel_models=1,
            run_budget_usd=None,
            per_model_budget_usd=None,
            checkpoint_policy="strict",
            execution_plan_ref=None,
            execution_plan_payload=None,
            stop_criteria_payload={},
            governance_constraints_payload=[],
            expected_outputs_payload=[],
            allow_mock_fallback=False,
        )
    finally:
        service.close()

    assert captured["curated_dir"] == curated_dir
    assert captured["kwargs"]["store"] is service._artifact_store


def test_nl_pipeline_simulated_multimodel_honors_run_budget_guard_without_network(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}

    def _capture_state(payload: dict[str, Any], **kwargs: Any) -> None:
        captured["payload"] = payload
        captured["kwargs"] = kwargs

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    _forbid_real_gateway_network(monkeypatch)
    monkeypatch.setattr("polisyos.fabric.retrieval.RetrievalService", _FakeRetrievalService)
    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _capture_state)
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.ensure_all_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.build_method_catalog_snapshot",
        lambda *, run_id=None: MethodCatalogSnapshot(
            snapshot_id=f"test-catalog-{run_id or 'run'}",
            run_id=run_id,
        ),
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.persist_method_catalog_snapshot",
        lambda _store, _snapshot: MethodCatalogSnapshotRef(artifact_id="sha256:" + "3" * 64),
    )
    from polisyos.common import async_tools

    real_run_coro_sync = async_tools.run_coro_sync

    def _run_coro_sync_with_load_budget(coro, *, timeout_seconds=None):
        timeout = 120.0 if timeout_seconds is None else timeout_seconds
        return real_run_coro_sync(coro, timeout_seconds=timeout)

    monkeypatch.setattr(async_tools, "run_coro_sync", _run_coro_sync_with_load_budget)
    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        registry_providers=_registry_providers(),
    )

    try:
        service._execute_nl_pipeline(
            run_id="R_nl_simulated_multimodel_budget",
            nl_request="Compare deterministic simulated model variants for MSME support.",
            context=_intent_context(requested_authority_level="dev"),
            domain_hint="Ukraine wartime MSME support policy",
            data_source=None,
            max_iterations=1,
            llm_models=["simulated-qwen", "simulated-llama"],
            max_parallel_models=1,
            run_budget_usd=0.0,
            per_model_budget_usd=None,
            checkpoint_policy="strict",
            execution_plan_ref=None,
            execution_plan_payload=None,
            stop_criteria_payload={},
            governance_constraints_payload=[],
            expected_outputs_payload=[],
            allow_mock_fallback=False,
        )
    finally:
        service.close()

    payload = captured["payload"]
    assert captured["kwargs"]["store"] is service._artifact_store
    params = payload["params"]
    variants = params["llm_model_variants"]

    assert params["llm_models"] == ["simulated-qwen", "simulated-llama"]
    assert params["llm_selected_variant_id"] == variants[0]["model_variant_id"]
    assert variants[0]["status"] == "completed"
    assert variants[0]["prompt_tokens"] > 0
    assert variants[0]["completion_tokens"] > 0
    assert variants[0]["cost_usd"] == 0.0
    assert variants[1]["status"] == "skipped_budget_guard"
    assert variants[1]["notes"] == ["run_budget_guard_prevented_start"]
    assert params["run_budget_usd"] == 0.0
    assert params["run_cost_usd"] == 0.0


def test_policy_grounding_fails_unadjudicated_material_model_disagreement() -> None:
    report = build_policy_grounding_matrix_report(
        claims=[
            {
                "claim_id": "rec_credit",
                "claim_family": "recommendation",
                "major": True,
                "text": "Target wartime credit support to eligible MSMEs.",
                "policy_action": "targeted_credit_support",
                "norm_refs": ["norm.ua.credit_eligibility"],
            }
        ],
        model_variants=[
            {
                "model_variant_id": "simulated_qwen_1",
                "model": "simulated-qwen",
                "trinity_bundle_ref": "sha256:" + "a" * 64,
                "final_policy_claims_ref": "sha256:" + "b" * 64,
                "claims": [
                    {
                        "claim_id": "rec_credit",
                        "claim_family": "recommendation",
                        "major": True,
                        "text": "Target wartime credit support to eligible MSMEs.",
                        "policy_action": "targeted_credit_support",
                    }
                ],
            },
            {
                "model_variant_id": "simulated_llama_2",
                "model": "simulated-llama",
                "trinity_bundle_ref": "sha256:" + "c" * 64,
                "final_policy_claims_ref": "sha256:" + "d" * 64,
                "claims": [
                    {
                        "claim_id": "rec_grant",
                        "claim_family": "recommendation",
                        "major": True,
                        "text": "Launch universal emergency grants for all MSMEs.",
                        "policy_action": "universal_emergency_grants",
                    }
                ],
            },
        ],
        normative_evidence={
            "status": "pass",
            "applied_norms": [{"norm_id": "norm.ua.credit_eligibility"}],
        },
    )

    issue = next(
        item for item in report["issues"] if item["code"] == "multi_model_policy_disagreement"
    )
    assert report["status"] == "fail"
    assert issue["variant_refs"] == [
        {
            "model_variant_id": "simulated_qwen_1",
            "model": "simulated-qwen",
            "trinity_bundle_ref": "sha256:" + "a" * 64,
            "final_policy_claims_ref": "sha256:" + "b" * 64,
        },
        {
            "model_variant_id": "simulated_llama_2",
            "model": "simulated-llama",
            "trinity_bundle_ref": "sha256:" + "c" * 64,
            "final_policy_claims_ref": "sha256:" + "d" * 64,
        },
    ]
    assert issue["next_action"]


def test_nl_pipeline_persists_multimodel_adjudication_and_keeps_unsupported_claim_blocking(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}

    def _capture_state(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        return {"run_id": payload["run_id"], "reports_index": {}}

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    _forbid_real_gateway_network(monkeypatch)
    monkeypatch.setattr("polisyos.fabric.retrieval.RetrievalService", _FakeRetrievalService)
    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _capture_state)
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.ensure_all_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.build_method_catalog_snapshot",
        lambda *, run_id=None: MethodCatalogSnapshot(
            snapshot_id=f"test-catalog-{run_id or 'run'}",
            run_id=run_id,
        ),
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.persist_method_catalog_snapshot",
        lambda _store, _snapshot: MethodCatalogSnapshotRef(artifact_id="sha256:" + "a" * 64),
    )

    from polisyos.scientist.agent.drafter_clients import LLMDrafterAgent

    original_draft_policy = LLMDrafterAgent.draft_policy

    async def _draft_with_material_disagreement(
        self: LLMDrafterAgent,
        problem_frame: object,
        *,
        data_context: dict[str, Any] | None = None,
        hints: list[str] | None = None,
        prior_drafts: list[Any] | None = None,
    ) -> Any:
        draft = await original_draft_policy(
            self,
            problem_frame,
            data_context=data_context,
            hints=hints,
            prior_drafts=prior_drafts,
        )
        model_name = str(getattr(getattr(self, "_llm", None), "_model_name", ""))
        if "llama" in model_name:
            supports = [
                {
                    "claim_id": "rec_universal_grants",
                    "claim_family": "recommendation",
                    "major": True,
                    "text": "Launch universal emergency grants for all MSMEs.",
                    "policy_action": "universal_emergency_grants",
                    "norm_refs": ["norm.ua.credit_eligibility"],
                }
            ]
        else:
            supports = [
                {
                    "claim_id": "rec_targeted_credit",
                    "claim_family": "recommendation",
                    "major": True,
                    "text": "Target wartime credit support to eligible MSMEs.",
                    "policy_action": "targeted_credit_support",
                    "norm_refs": ["norm.ua.credit_eligibility"],
                },
                {
                    "claim_id": "causal_unsupported_blanket",
                    "claim_family": "causal",
                    "major": True,
                    "text": "The selected package will cause immediate MSME survival gains.",
                },
            ]
        return replace(draft, claim_supports=supports)

    monkeypatch.setattr(LLMDrafterAgent, "draft_policy", _draft_with_material_disagreement)

    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="research",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control-adjudication.sqlite3"),
            postgres_dsn=None,
        ),
        registry_providers=_registry_providers(),
    )

    try:
        result = service._execute_nl_pipeline(
            run_id="R_nl_multimodel_adjudication",
            nl_request="Evaluate materially different MSME support recommendations.",
            context=_normative_context(),
            domain_hint="Ukraine wartime MSME support policy",
            data_source=None,
            max_iterations=1,
            llm_models=["simulated-qwen", "simulated-llama"],
            max_parallel_models=1,
            run_budget_usd=None,
            per_model_budget_usd=None,
            checkpoint_policy="strict",
            execution_plan_ref=None,
            execution_plan_payload=None,
            stop_criteria_payload={},
            governance_constraints_payload=[],
            expected_outputs_payload=[],
            execution_profile="research",
            allow_mock_fallback=False,
            provider_preflight_payload={"status": "skipped", "reason": "simulation_mode"},
        )
        adjudication_ref = result["llm_model_adjudication_ref"]
        grounding_ref = result["policy_grounding_matrix_ref"]
        citation_ref = result["citation_faithfulness_report_ref"]
        source_ref = result["source_quality_report_ref"]
        adjudication = from_canonical_bytes(
            service._artifact_store.get_bytes(ArtifactID(adjudication_ref))
        )
        grounding_report = from_canonical_bytes(
            service._artifact_store.get_bytes(ArtifactID(grounding_ref))
        )
        citation_report = from_canonical_bytes(
            service._artifact_store.get_bytes(ArtifactID(citation_ref))
        )
        source_report = from_canonical_bytes(
            service._artifact_store.get_bytes(ArtifactID(source_ref))
        )
    finally:
        service.close()

    params = captured["payload"]["params"]
    selected_variant = next(
        item for item in params["llm_model_variants"] if item.get("selected_for_workflow")
    )
    disagreement = adjudication["disagreements"][0]

    assert params["llm_model_adjudication_ref"] == adjudication_ref
    assert params["runtime_quality_refs"]["citation_faithfulness_report_ref"] == citation_ref
    assert params["runtime_quality_refs"]["source_quality_report_ref"] == source_ref
    assert adjudication["schema_version"] == "policyos.scientist.llm_model_adjudication.v1"
    assert adjudication["decision"]["code"] == "llm_model_variant_adjudication"
    assert adjudication["decision"]["selected_variant_id"] == params["llm_selected_variant_id"]
    assert disagreement["code"] == "multi_model_policy_disagreement"
    assert disagreement["variant_refs"][0]["final_policy_claims_ref"].startswith("sha256:")
    assert disagreement["variant_refs"][1]["trinity_bundle_ref"].startswith("sha256:")
    assert disagreement["next_action"]
    assert selected_variant["selection_rationale"]
    assert "norm.ua.credit_eligibility" in selected_variant["selection_evidence_refs"]
    assert selected_variant["llm_model_adjudication_ref"] == adjudication_ref

    issue_codes = {issue["code"] for issue in grounding_report["issues"]}
    assert citation_report["schema_version"] == "policyos.scientist.citation_faithfulness.v1"
    assert citation_report["live_llm_judging_enabled"] is False
    assert source_report["schema_version"] == "policyos.scientist.source_quality_report.v1"
    assert source_report["score_calibration"] == "advisory"
    assert grounding_report["citation_faithfulness"]["status"] == citation_report["status"]
    assert grounding_report["source_quality"]["status"] == source_report["status"]
    assert grounding_report["adjudication_decision"]["artifact_ref"] == adjudication_ref
    assert "multi_model_policy_disagreement" not in issue_codes
    assert "claim_family_missing_required_grounding" in issue_codes
    assert grounding_report["status"] == "fail"


def test_nl_pipeline_promotes_serious_causal_context_into_scientist_params(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}

    def _capture_state(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        return {"run_id": payload["run_id"], "reports_index": {}}

    closed_models: list[str] = []

    async def _record_simulated_close(client: object) -> None:
        closed_models.append(str(client.model))

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    _forbid_real_gateway_network(monkeypatch)
    monkeypatch.setattr(
        "polisyos.scientist.orchestration.llm.simulated_gateway.SimulatedGatewayLLMClient.aclose",
        _record_simulated_close,
    )
    monkeypatch.setattr("polisyos.fabric.retrieval.RetrievalService", _FakeRetrievalService)
    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _capture_state)
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.ensure_all_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.build_method_catalog_snapshot",
        lambda *, run_id=None: MethodCatalogSnapshot(
            snapshot_id=f"test-catalog-{run_id or 'run'}",
            run_id=run_id,
        ),
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.persist_method_catalog_snapshot",
        lambda _store, _snapshot: MethodCatalogSnapshotRef(artifact_id="sha256:" + "6" * 64),
    )

    production_data_root = tmp_path / "production_data"
    datasets_dir = production_data_root / "datasets_full_phase3full_20260327_183054"
    datasets_dir.mkdir(parents=True)
    datasets_db = datasets_dir / "dataset_catalog.duckdb"
    datasets_db.touch()
    lex_bundle_dir = production_data_root / "lex" / "lex-amendment-only-optimized-20260501-v3"
    legal_db = lex_bundle_dir / "finalize" / "lex_knowledge_graph.duckdb"
    legal_db.parent.mkdir(parents=True)
    legal_db.touch()
    academic_dir = production_data_root / "policyos_academic_runtime_slim_20260411T112032Z"
    academic_component = academic_dir / "academic"
    academic_db = academic_component / "graph" / "scholar_knowledge.duckdb"
    academic_db.parent.mkdir(parents=True)
    academic_db.touch()
    benchmark_suite = academic_component / "benchmark_suite.json"
    benchmark_report = academic_component / "benchmark_report.json"
    academic_backlog = academic_component / "runtime_demand_backlog.jsonl"
    benchmark_suite.write_text("{}", encoding="utf-8")
    benchmark_report.write_text("{}", encoding="utf-8")
    academic_backlog.write_text("", encoding="utf-8")
    ukraine_bundles = (
        production_data_root
        / "ukraine_agent_simulation_baseline_20260410"
        / "production_bundle"
        / "bundles"
    )
    for bundle_name in (
        "runtime_bundle_v1",
        "intervention_bundle_v1",
        "calibration_bundle_v1",
        "method_contract_bundle_v1",
    ):
        (ukraine_bundles / bundle_name).mkdir(parents=True)

    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        registry_providers=_registry_providers(),
    )

    try:
        service._execute_nl_pipeline(
            run_id="R_nl_serious_context",
            nl_request="Evaluate a wartime MSME credit-guarantee policy for Ukraine.",
            context=_intent_context(
                source_context={
                    "context_id": "EU_COVID_SME_SUPPORT_2020",
                    "context_label": "EU COVID SME support evidence",
                    "countries": ["DE", "PL"],
                    "publication_year": 2020,
                    "time_period": "2020-2021",
                },
                target_context={
                    "context_id": "UA_WARTIME_MSME_2026",
                    "context_label": "Ukraine wartime MSME support",
                    "countries": ["UA"],
                    "publication_year": 2026,
                    "time_period": "2026",
                    "post_conflict": True,
                },
                query_treatment="credit_guarantee",
                query_outcome="msme_survival_rate",
                production_data_root=str(production_data_root),
            ),
            domain_hint="Ukraine wartime MSME support policy",
            data_source=None,
            max_iterations=1,
            llm_models=["simulated-qwen"],
            max_parallel_models=1,
            run_budget_usd=None,
            per_model_budget_usd=None,
            checkpoint_policy="strict",
            execution_plan_ref=None,
            execution_plan_payload=None,
            stop_criteria_payload={},
            governance_constraints_payload=[],
            expected_outputs_payload=[],
            execution_profile="research",
            allow_mock_fallback=False,
        )
    finally:
        service.close()

    params = captured["payload"]["params"]
    assert captured["payload"]["execution_profile"] == "research"
    assert params["source_context"]["context_id"] == "EU_COVID_SME_SUPPORT_2020"
    assert params["target_context"]["context_id"] == "UA_WARTIME_MSME_2026"
    assert params["query_treatment"] == "credit_guarantee"
    assert params["query_outcome"] == "msme_survival_rate"
    assert params["transport_required"] is True
    assert params["cross_graph_evidence_config"]["enabled"] is True
    assert params["cross_graph_evidence_config"]["policy_domain"] == (
        "Ukraine wartime MSME support policy"
    )
    assert params["cross_graph_evidence_config"]["country_code"] == "UA"
    assert params["production_data_root"] == str(production_data_root)
    assert params["datasets_db_path"] == str(datasets_db)
    assert params["dataset_registry_db_path"] == str(datasets_db)
    assert params["lex_bundle_dir"] == str(lex_bundle_dir)
    assert params["legal_db_path"] == str(legal_db)
    assert params["legal_kg_db_path"] == str(legal_db)
    assert params["academic_db_path"] == str(academic_db)
    assert params["skg_db_path"] == str(academic_db)
    assert params["academic_index_dir"] == str(academic_component)
    assert params["skg_index_dir"] == str(academic_component)
    assert params["benchmark_suite_path"] == str(benchmark_suite)
    assert params["benchmark_report_path"] == str(benchmark_report)
    assert params["academic_demand_backlog_path"] == str(academic_backlog)
    assert params["ukraine_runtime_bundle_dir"] == str(ukraine_bundles / "runtime_bundle_v1")
    assert closed_models == ["simulated-qwen", "simulated-qwen"]


def test_nl_pipeline_reports_gateway_failure_when_mock_fallback_is_disallowed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class _FailingLLMClient:
        closed = False

        async def list_model_ids(self, *, timeout: float | None = None) -> list[str]:
            return ["broken-gateway-model"]

        async def generate(self, *args: object, **kwargs: object) -> GatewayLLMResponse:
            tools = kwargs.get("tools")
            if isinstance(tools, list):
                for tool in tools:
                    if not isinstance(tool, dict):
                        continue
                    function = tool.get("function")
                    if isinstance(function, dict) and function.get("name") == "emit_design_problem":
                        arguments = _design_problem_tool_args()
                        arguments["constraints"] = []
                        return GatewayLLMResponse(
                            content="",
                            model="broken-gateway-model",
                            provider="test-gateway",
                            tool_calls=[
                                GatewayToolCall(
                                    id="call-design-problem",
                                    name="emit_design_problem",
                                    arguments=arguments,
                                )
                            ],
                        )
            raise RuntimeError("gateway temporarily unavailable")

        async def aclose(self) -> None:
            self.closed = True

    client = _FailingLLMClient()
    monkeypatch.setattr(
        "polisyos.runtime.http.services.control.nl_pipeline.create_traced_gateway_client",
        lambda **_kwargs: client,
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.ensure_all_methods_registered",
        lambda: None,
    )

    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        registry_providers=_registry_providers(),
    )
    job_id = "job_nl_gateway_failed"
    service._control_store.create_job(
        job_id=job_id,
        kind="natural_language_run",
        run_id="R_nl_gateway_failed",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="research",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )

    try:
        with pytest.raises(RuntimeError) as exc_info:
            service._execute_nl_pipeline(
                run_id="R_nl_gateway_failed",
                nl_request="Evaluate an MSME policy.",
                context=_intent_context(),
                domain_hint="Ukraine wartime MSME support policy",
                data_source=None,
                max_iterations=1,
                llm_models=["broken-gateway-model"],
                max_parallel_models=1,
                run_budget_usd=None,
                per_model_budget_usd=None,
                checkpoint_policy="strict",
                execution_plan_ref=None,
                execution_plan_payload=None,
                stop_criteria_payload={},
                governance_constraints_payload=[],
                expected_outputs_payload=[],
                control_job_id=job_id,
                allow_mock_fallback=False,
            )
        record = service._control_store.get_job(job_id)
    finally:
        service.close()

    message = str(exc_info.value)
    assert "no_model_variant_completed" in message
    assert "broken-gateway-model" in message
    assert "gateway temporarily unavailable" in message
    assert client.closed is True
    assert record is not None
    assert record.progress["phase"] == "model_variants_failed"
    assert record.progress["state"] == "failed"
    assert record.progress["failure"]["code"] == "no_model_variant_completed"
    assert record.progress["failure"]["layer"] == "llm_gateway"
    assert record.progress["failure"]["retryable"] is True


def test_nl_pipeline_surfaces_formalizer_schema_healing_in_variant_telemetry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}

    def _capture_state(payload: dict[str, Any], **kwargs: Any) -> None:
        captured["payload"] = payload
        captured["kwargs"] = kwargs

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    _forbid_real_gateway_network(monkeypatch)
    monkeypatch.setattr("polisyos.fabric.retrieval.RetrievalService", _FakeRetrievalService)
    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _capture_state)
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.ensure_all_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.build_method_catalog_snapshot",
        lambda *, run_id=None: MethodCatalogSnapshot(
            snapshot_id=f"test-catalog-{run_id or 'run'}",
            run_id=run_id,
        ),
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.persist_method_catalog_snapshot",
        lambda _store, _snapshot: MethodCatalogSnapshotRef(artifact_id="sha256:" + "6" * 64),
    )

    from polisyos.ir.trinity import TrinityBundle
    from polisyos.scientist.agent.formalizer import LLMFormalizerAgent

    original_formalize = LLMFormalizerAgent.formalize

    async def _formalize_with_healing_note(self, draft, *, schema_version="1.0"):
        bundle = await original_formalize(self, draft, schema_version=schema_version)
        payload = bundle.model_dump(mode="python")
        payload["model_spec"]["notes"] = ["schema_healed:model_spec.fidelity_level:medium->hybrid"]
        return TrinityBundle.model_validate(payload)

    monkeypatch.setattr(LLMFormalizerAgent, "formalize", _formalize_with_healing_note)

    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        registry_providers=_registry_providers(),
    )

    try:
        service._execute_nl_pipeline(
            run_id="R_nl_schema_healing",
            nl_request="Evaluate an MSME policy with a simulated model.",
            context=_intent_context(requested_authority_level="dev"),
            domain_hint="Ukraine wartime MSME support policy",
            data_source=None,
            max_iterations=1,
            llm_models=["simulated-qwen"],
            max_parallel_models=1,
            run_budget_usd=None,
            per_model_budget_usd=None,
            checkpoint_policy="strict",
            execution_plan_ref=None,
            execution_plan_payload=None,
            stop_criteria_payload={},
            governance_constraints_payload=[],
            expected_outputs_payload=[],
            allow_mock_fallback=False,
        )
    finally:
        service.close()

    variant = captured["payload"]["params"]["llm_model_variants"][0]
    assert variant["schema_healing"] == ["schema_healed:model_spec.fidelity_level:medium->hybrid"]
    assert variant["schema_healing_count"] == 1


def test_nl_pipeline_promotes_formalizer_structured_schema_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    _forbid_real_gateway_network(monkeypatch)
    monkeypatch.setattr("polisyos.fabric.retrieval.RetrievalService", _FakeRetrievalService)
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.ensure_all_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.build_method_catalog_snapshot",
        lambda *, run_id=None: MethodCatalogSnapshot(
            snapshot_id=f"test-catalog-{run_id or 'run'}",
            run_id=run_id,
        ),
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.persist_method_catalog_snapshot",
        lambda _store, _snapshot: MethodCatalogSnapshotRef(artifact_id="sha256:" + "6" * 64),
    )

    from polisyos.scientist.agent.formalizer import (
        FormalizerSchemaValidationError,
        LLMFormalizerAgent,
    )

    async def _formalize_with_strict_schema_failure(
        self: LLMFormalizerAgent,
        draft: object,
        *,
        schema_version: str = "1.0",
    ) -> None:
        del self, schema_version
        raise FormalizerSchemaValidationError(
            "LLM formalizer output required schema healing in strict mode.",
            phase="schema_healing",
            field_errors=[
                {
                    "path": "model_spec.fidelity_level",
                    "raw": "medium",
                    "normalized": "hybrid",
                    "note": "schema_healed:model_spec.fidelity_level:medium->hybrid",
                }
            ],
            draft_id=str(getattr(draft, "draft_id", "")),
        )

    monkeypatch.setattr(LLMFormalizerAgent, "formalize", _formalize_with_strict_schema_failure)

    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        registry_providers=_registry_providers(),
    )
    job_id = "job_nl_formalizer_schema_failed"
    service._control_store.create_job(
        job_id=job_id,
        kind="natural_language_run",
        run_id="R_nl_formalizer_schema_failed",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="research",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )

    try:
        with pytest.raises(RuntimeError) as exc_info:
            service._execute_nl_pipeline(
                run_id="R_nl_formalizer_schema_failed",
                nl_request="Evaluate an MSME policy with a simulated model.",
                context=_intent_context(),
                domain_hint="Ukraine wartime MSME support policy",
                data_source=None,
                max_iterations=1,
                llm_models=["simulated-qwen"],
                max_parallel_models=1,
                run_budget_usd=None,
                per_model_budget_usd=None,
                checkpoint_policy="strict",
                execution_plan_ref=None,
                execution_plan_payload=None,
                stop_criteria_payload={},
                governance_constraints_payload=[],
                expected_outputs_payload=[],
                control_job_id=job_id,
                allow_mock_fallback=False,
            )
        record = service._control_store.get_job(job_id)
    finally:
        service.close()

    assert "llm_formalizer_schema_validation_failed" in str(exc_info.value)
    assert record is not None
    assert record.progress["phase"] == "model_variants_failed"
    failure = record.progress["failure"]
    assert failure["code"] == "llm_formalizer_schema_validation_failed"
    assert failure["layer"] == "llm_formalizer"
    assert failure["phase"] == "schema_healing"
    variant_failure = failure["variants"][0]["failure"]
    assert variant_failure["field_errors"][0]["path"] == "model_spec.fidelity_level"


def test_nl_pipeline_propagates_scientist_workflow_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _failing_run_experiment(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        store = kwargs["store"]
        report_ref = store.put_json(
            {
                "schema_version": "1.0",
                "workflow_id": "scientist_causal_full",
                "run_id": payload["run_id"],
                "status": "fail",
                "nodes": [],
            },
            ArtifactWriteOptions(
                kind="scientist.workflow_report",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.orchestration.engine.WorkflowReport",
                    version="1.0",
                ),
            ),
        )
        return {
            "run_id": payload["run_id"],
            "reports_index": {"workflow_report": report_ref.model_dump(mode="json")},
        }

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    _forbid_real_gateway_network(monkeypatch)
    monkeypatch.setattr("polisyos.fabric.retrieval.RetrievalService", _FakeRetrievalService)
    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _failing_run_experiment)
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.ensure_all_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.build_method_catalog_snapshot",
        lambda *, run_id=None: MethodCatalogSnapshot(
            snapshot_id=f"test-catalog-{run_id or 'run'}",
            run_id=run_id,
        ),
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.persist_method_catalog_snapshot",
        lambda _store, _snapshot: MethodCatalogSnapshotRef(artifact_id="sha256:" + "2" * 64),
    )

    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        registry_providers=_registry_providers(),
    )

    try:
        with pytest.raises(RuntimeError, match="scientist_workflow_failed:fail"):
            service._execute_nl_pipeline(
                run_id="R_nl_scientist_fail",
                nl_request="Розроби оптимальну політику підтримки МСП України у воєнний час.",
                context=_intent_context(requested_authority_level="dev"),
                domain_hint="Ukraine wartime MSME support policy",
                data_source=None,
                max_iterations=1,
                llm_models=["simulated-qwen"],
                max_parallel_models=1,
                run_budget_usd=None,
                per_model_budget_usd=None,
                checkpoint_policy="strict",
                execution_plan_ref=None,
                execution_plan_payload=None,
                stop_criteria_payload={},
                governance_constraints_payload=[],
                expected_outputs_payload=[],
                allow_mock_fallback=False,
            )
    finally:
        service.close()


def test_nl_pipeline_updates_control_job_progress(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}

    def _capture_state(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        return {"run_id": payload["run_id"], "reports_index": {}}

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    _forbid_real_gateway_network(monkeypatch)
    monkeypatch.setattr("polisyos.fabric.retrieval.RetrievalService", _FakeRetrievalService)
    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _capture_state)
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.ensure_all_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.build_method_catalog_snapshot",
        lambda *, run_id=None: MethodCatalogSnapshot(
            snapshot_id=f"test-catalog-{run_id or 'run'}",
            run_id=run_id,
        ),
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.persist_method_catalog_snapshot",
        lambda _store, _snapshot: MethodCatalogSnapshotRef(artifact_id="sha256:" + "4" * 64),
    )

    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="dev",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control-progress.sqlite3"),
            postgres_dsn=None,
        ),
        registry_providers=_registry_providers(),
    )
    job_id = "job_nl_progress"
    service._control_store.create_job(
        job_id=job_id,
        kind="natural_language_run",
        run_id="R_nl_progress",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )

    try:
        service._execute_nl_pipeline(
            run_id="R_nl_progress",
            nl_request="Compare deterministic simulated model variants for MSME support.",
            context=_intent_context(requested_authority_level="dev"),
            domain_hint="Ukraine wartime MSME support policy",
            data_source=None,
            max_iterations=1,
            llm_models=["simulated-qwen"],
            max_parallel_models=1,
            run_budget_usd=None,
            per_model_budget_usd=None,
            checkpoint_policy="strict",
            execution_plan_ref=None,
            execution_plan_payload=None,
            stop_criteria_payload={},
            governance_constraints_payload=[],
            expected_outputs_payload=[],
            control_job_id=job_id,
            allow_mock_fallback=False,
            provider_preflight_payload={"status": "skipped", "reason": "simulation_mode"},
        )
        record = service._control_store.get_job(job_id)
    finally:
        service.close()

    assert record is not None
    assert record.progress["phase"] == "scientist_workflow_completed"
    assert record.progress["run_id"] == "R_nl_progress"
    assert record.progress["steps_completed"] > 0
    assert record.progress["last_step"]["action"] == "run_experiment"
    assert record.progress["variants"]["simulated_qwen_1"]["status"] == "completed"
    assert record.progress["variants"]["simulated_qwen_1"]["auto_data_source_refs"][
        "data_snapshot_ref"
    ].startswith("sha256:")
    assert record.progress["provider_preflight"] == {
        "status": "skipped",
        "reason": "simulation_mode",
    }


def test_nl_pipeline_bridges_scientist_trace_events_to_control_progress(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _capture_state(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        store = kwargs["store"]
        trace_path = store.root / "runs" / payload["run_id"] / "trace.jsonl"
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        events = [
            {
                "ts": "2026-05-12T09:00:00+00:00",
                "run_id": payload["run_id"],
                "phase": "scientist.node.formalize_problem",
                "event": "NODE_STARTED",
                "refs": {"inputs": [], "outputs": []},
                "metrics": {},
                "warnings": [],
                "errors": [],
            },
            {
                "ts": "2026-05-12T09:00:01+00:00",
                "run_id": payload["run_id"],
                "phase": "scientist.node.formalize_problem",
                "event": "NODE_OK",
                "refs": {
                    "inputs": [],
                    "outputs": [
                        {
                            "artifact_id": "sha256:" + "c" * 64,
                            "kind": "scientist.formalized_problem",
                            "media_type": "application/json",
                        }
                    ],
                },
                "metrics": {"duration_ms": 12},
                "warnings": [],
                "errors": [],
            },
        ]
        trace_path.write_text(
            "".join(json.dumps(event) + "\n" for event in events),
            encoding="utf-8",
        )
        return {"run_id": payload["run_id"], "reports_index": {}}

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    monkeypatch.setenv("POLISYOS_SCIENTIST_PROGRESS_POLL_S", "0.01")
    _forbid_real_gateway_network(monkeypatch)
    monkeypatch.setattr("polisyos.fabric.retrieval.RetrievalService", _FakeRetrievalService)
    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _capture_state)
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.ensure_all_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.build_method_catalog_snapshot",
        lambda *, run_id=None: MethodCatalogSnapshot(
            snapshot_id=f"test-catalog-{run_id or 'run'}",
            run_id=run_id,
        ),
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.persist_method_catalog_snapshot",
        lambda _store, _snapshot: MethodCatalogSnapshotRef(artifact_id="sha256:" + "4" * 64),
    )

    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="dev",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control-scientist-progress.sqlite3"),
            postgres_dsn=None,
        ),
        registry_providers=_registry_providers(),
    )
    job_id = "job_scientist_progress"
    service._control_store.create_job(
        job_id=job_id,
        kind="natural_language_run",
        run_id="R_nl_scientist_progress",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )

    try:
        service._execute_nl_pipeline(
            run_id="R_nl_scientist_progress",
            nl_request="Compare deterministic simulated model variants for MSME support.",
            context=_intent_context(requested_authority_level="dev"),
            domain_hint="Ukraine wartime MSME support policy",
            data_source=None,
            max_iterations=1,
            llm_models=["simulated-qwen"],
            max_parallel_models=1,
            run_budget_usd=None,
            per_model_budget_usd=None,
            checkpoint_policy="strict",
            execution_plan_ref=None,
            execution_plan_payload=None,
            stop_criteria_payload={},
            governance_constraints_payload=[],
            expected_outputs_payload=[],
            control_job_id=job_id,
            allow_mock_fallback=False,
            provider_preflight_payload={"status": "skipped", "reason": "simulation_mode"},
        )
        record = service._control_store.get_job(job_id)
    finally:
        service.close()

    assert record is not None
    scientist_progress = record.progress["scientist_workflow"]
    assert scientist_progress["event_count"] == 2
    assert scientist_progress["current_node_alias"] == "formalize_problem"
    assert scientist_progress["latest_event"]["event"] == "NODE_OK"
    assert scientist_progress["latest_artifact_refs"] == [
        {
            "direction": "outputs",
            "artifact_id": "sha256:" + "c" * 64,
            "kind": "scientist.formalized_problem",
            "media_type": "application/json",
        }
    ]


def test_nl_pipeline_marks_progress_failed_when_scientist_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _raising_run_experiment(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("foundry execution aborted")

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    _forbid_real_gateway_network(monkeypatch)
    monkeypatch.setattr("polisyos.fabric.retrieval.RetrievalService", _FakeRetrievalService)
    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _raising_run_experiment)
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.ensure_all_methods_registered",
        lambda: None,
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.build_method_catalog_snapshot",
        lambda *, run_id=None: MethodCatalogSnapshot(
            snapshot_id=f"test-catalog-{run_id or 'run'}",
            run_id=run_id,
        ),
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.persist_method_catalog_snapshot",
        lambda _store, _snapshot: MethodCatalogSnapshotRef(artifact_id="sha256:" + "5" * 64),
    )

    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="dev",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control-progress-fail.sqlite3"),
            postgres_dsn=None,
        ),
        registry_providers=_registry_providers(),
    )
    job_id = "job_nl_progress_failed"
    service._control_store.create_job(
        job_id=job_id,
        kind="natural_language_run",
        run_id="R_nl_progress_failed",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )

    try:
        with pytest.raises(RuntimeError, match="foundry execution aborted"):
            service._execute_nl_pipeline(
                run_id="R_nl_progress_failed",
                nl_request="Compare deterministic simulated model variants for MSME support.",
                context=_intent_context(requested_authority_level="dev"),
                domain_hint="Ukraine wartime MSME support policy",
                data_source=None,
                max_iterations=1,
                llm_models=["simulated-qwen"],
                max_parallel_models=1,
                run_budget_usd=None,
                per_model_budget_usd=None,
                checkpoint_policy="strict",
                execution_plan_ref=None,
                execution_plan_payload=None,
                stop_criteria_payload={},
                governance_constraints_payload=[],
                expected_outputs_payload=[],
                control_job_id=job_id,
                allow_mock_fallback=False,
            )
        record = service._control_store.get_job(job_id)
    finally:
        service.close()

    assert record is not None
    assert record.progress["phase"] == "scientist_workflow_failed"
    assert record.progress["state"] == "failed"
    assert record.progress["last_step"]["status"] == "failed"
    assert record.progress["last_step"]["details"]["error_type"] == "RuntimeError"
