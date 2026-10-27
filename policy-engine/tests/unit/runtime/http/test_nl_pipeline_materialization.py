from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

import pytest

from polisyos.core.artifacts import (
    AUTHORITY_ENVELOPE_ARTIFACT_KIND,
    artifact_manifest_profile_sha256,
    read_core_json_artifact,
)
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.core.contracts.execution_plan import MethodCatalogSnapshot, MethodCatalogSnapshotRef
from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver
from polisyos.runtime.http.services.control import ControlPlaneService
from polisyos.runtime.http.services.control.nl_pipeline import (
    _DESIGN_PROBLEM_COMPILER_OUTPUT_POLICY,
    NaturalLanguagePipelineRefusalError,
    NaturalLanguageRunMixin,
    _build_scientist_context_params,
    _preflight_design_problem_model,
    _production_materialization_failure,
    _resolve_selected_materialization_ref,
    _runtime_quality_candidate_inputs_match,
    _runtime_quality_closure_reference_values,
    _runtime_quality_semantic_binding_reference,
    _RuntimeQualityPublicationCandidate,
    build_design_problem_from_nl_request,
    design_problem_compiler_source_semantics_invariant,
    design_problem_provider_constraint_schema,
)
from polisyos.runtime.http.services.control.nl_pipeline_testing import (
    NLContractTestingAuthorityStamp,
)
from polisyos.runtime.http.services.control_registry_providers import ControlRegistryProviders
from polisyos.runtime.quality.assurance_case import PolicyDesignCaseAuthorityError
from polisyos.runtime.quality.authority_reconciliation import reconcile_authority_ref
from polisyos.runtime.quality.design_problem import DesignProblem, DesignProblemAuthorityError
from polisyos.runtime.quality.diagnostic_events import DIAGNOSTIC_EVENT_ARTIFACT_KIND
from polisyos.runtime.quality.scorecard import _phase_barrier_gates
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMResponse, GatewayToolCall
from polisyos.scientist.orchestration.llm.simulated_gateway import SimulatedGatewayLLMClient
from polisyos.scientist.validation.policy_grounding import build_policy_grounding_matrix_report
from tests._helpers.runtime_http import _DeterministicSpanSupportClient
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

    def resolve(self, request: Any, *, run_profile: Any = None) -> Any:
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


def _trinity_bundle_artifact_ids(store: Any) -> set[str]:
    return {
        str(ref)
        for ref in store.iter_artifact_ids()
        if store.get_manifest(ref).kind == "ir.trinity_bundle"
    }


def _prepare_running_scoped_control_job(
    store: Any,
    *,
    job_id: str,
    run_id: str,
    effective_profile: str,
    context: dict[str, Any],
    include_execution_scope: bool = True,
) -> Any:
    """Create and lease one control job with explicit fixture-owned scope."""

    creation_event_payload: dict[str, Any] = {
        "job_id": job_id,
        "run_id": run_id,
        "job_kind": "natural_language_run",
        "pipeline_id": None,
        "payload_ref": None,
        "submitted_by": "tester",
        "requested_execution_profile": effective_profile,
        "effective_execution_profile": effective_profile,
        "policy_flags": {},
        "capability_manifest_ref": None,
    }
    if include_execution_scope:
        tenant_id = context.get("tenant_id")
        cell_id = context.get("cell_id")
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise AssertionError("scoped fixture requires explicit tenant_id")
        if not isinstance(cell_id, str) or not cell_id.strip():
            raise AssertionError("scoped fixture requires explicit cell_id")
        creation_event_payload["execution_scope"] = {
            "schema_version": "polisyos.runtime.control_execution_scope.v1",
            "status": "established",
            "tenant_id": tenant_id,
            "cell_id": cell_id,
            "actor_subject": "tester",
            "actor_authenticated": True,
            "actor_roles": ["analyst"],
        }
    store.create_job(
        job_id=job_id,
        kind="natural_language_run",
        run_id=run_id,
        pipeline_id=None,
        requested_execution_profile=effective_profile,
        effective_execution_profile=effective_profile,
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
        creation_event_payload=creation_event_payload,
    )
    worker_id = f"nl-test-worker:{job_id}"
    leased = store.lease_next_job(worker_id=worker_id, lease_seconds=60)
    if leased is None or leased.job_id != job_id:
        raise AssertionError("scoped fixture job was not leased")
    return store.job_execution_fence(
        job_id=job_id,
        worker_id=worker_id,
        attempt=leased.attempt,
    )


def _run_nl_pipeline_with_live_admission(
    service: ControlPlaneService,
    pipeline: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run a direct NL pipeline test through the real scoped-job fixture."""

    run_id = kwargs.get("run_id")
    context = kwargs.get("context")
    if not isinstance(run_id, str) or not run_id.strip():
        raise AssertionError("NL pipeline fixture requires an explicit run_id")
    if not isinstance(context, dict):
        raise AssertionError("NL pipeline fixture requires an explicit context")
    if kwargs.get("control_job_id") is not None:
        raise AssertionError("NL pipeline fixture owns control_job_id")
    execution_profile = kwargs.get("execution_profile") or getattr(
        getattr(service, "_policy_resolver", None),
        "default_profile",
        None,
    )
    if not isinstance(execution_profile, str) or not execution_profile.strip():
        raise AssertionError("NL pipeline fixture requires an explicit effective profile")
    job_id = f"job_test_{run_id}"
    execution_fence = _prepare_running_scoped_control_job(
        service._control_store,
        job_id=job_id,
        run_id=run_id,
        effective_profile=execution_profile,
        context=context,
    )
    kwargs["control_job_id"] = job_id
    kwargs["execution_profile"] = execution_profile
    with execution_fence:
        return pipeline(**kwargs)


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


def _design_problem_tool_args(*, constraint_source: str = "UAH 10b budget cap") -> dict[str, Any]:
    return {
        "schema_version": "policyos.runtime.design_problem.v3",
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
    assert problem.schema_version == "policyos.runtime.design_problem.v3"
    assert problem.authority_profile.requested_authority_level == "research"
    assert problem.jurisdiction_time.region == "UA"
    assert problem.outcome_of_interest.target_variable == "firm_survival"
    assert problem.candidate_lever_space.candidate_levers[0].operator_kind == "credit_guarantee"
    assert problem.evidence_acquisition_needs.needs[0].status == "required"
    assert gateway.generate_calls
    assert gateway.generate_calls[0]["tools"][0]["function"]["name"] == "emit_design_problem"
    assert gateway.generate_calls[0]["tool_choice"]["function"]["name"] == "emit_design_problem"
    assert gateway.generate_calls[0]["max_tokens"] == 8192
    tool_schema = gateway.generate_calls[0]["tools"][0]["function"]["parameters"]
    assert tool_schema["properties"]["schema_version"] == {
        "const": "policyos.runtime.design_problem.v3",
        "type": "string",
    }
    assert "schema_version" in tool_schema["required"]
    assert "$defs" not in tool_schema
    assert "$ref" not in json.dumps(tool_schema)
    time_object = tool_schema["properties"]["jurisdiction_time"]["properties"]["time_semantics"][
        "anyOf"
    ][0]
    assert time_object["anyOf"] == [
        {
            "required": ["step_count"],
            "properties": {"step_count": {"type": "integer", "minimum": 1}},
        },
        {
            "required": ["end_date"],
            "properties": {"end_date": {"type": "string", "minLength": 1}},
        },
    ]


@pytest.mark.asyncio
async def test_design_problem_front_door_binds_provider_events_to_nl_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from polisyos.runtime.http.services.control import nl_pipeline
    from polisyos.scientist.orchestration.engine.budget import BudgetState
    from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware

    gateway = _FakeDesignProblemGateway(
        models=["Qwen/Qwen3-235B-A22B-Instruct-2507-FP8"],
        arguments=_design_problem_tool_args(),
    )
    middleware = BudgetMiddleware(
        BudgetState(),
        ledger=FileBudgetLedger(tmp_path / "llm-ledger.json"),
    )
    span_support = _DeterministicSpanSupportClient()
    captured: dict[str, object] = {}

    def _build_client(**kwargs: object) -> _FakeDesignProblemGateway:
        captured.update(kwargs)
        return gateway

    monkeypatch.setattr(nl_pipeline, "create_traced_gateway_client", _build_client)
    problem = await nl_pipeline.build_design_problem_from_nl_request(
        nl_request=(
            "Design a wartime MSME credit guarantee for Ukraine within the stated "
            "UAH 10b budget cap."
        ),
        context=_intent_context(as_of="2026-05-12"),
        model_name="Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
        run_id="run-design-problem",
        producer_settlement_store=middleware,
        span_support_client=span_support,
    )

    assert problem.design_problem_id == "design_problem_ua_msme_credit"
    assert captured["run_id"] == "run-design-problem"
    assert captured["producer_settlement_store"] is middleware
    assert captured["producer_budget_key"] == "nl-run:run-design-problem"
    assert span_support.calls


@pytest.mark.asyncio
async def test_design_problem_front_door_accepts_current_qualified_outcome() -> None:
    """The current NL owner emits and parses the versioned qualified grammar."""

    arguments = _design_problem_tool_args()
    arguments["schema_version"] = "policyos.runtime.design_problem.v3"
    arguments["outcome_of_interest"]["target_variable"] = "government.balance"
    gateway = _FakeDesignProblemGateway(
        models=["Qwen/Qwen3-235B-A22B-Instruct-2507-FP8"],
        arguments=arguments,
    )
    problem = await build_design_problem_from_nl_request(
        nl_request=(
            "Design a wartime MSME credit guarantee within the stated UAH 10b budget cap; "
            "measure Ukraine's government cash balance."
        ),
        context=_intent_context(as_of="2026-05-12"),
        model_name="Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
        gateway_client=gateway,
        span_support_client=_DeterministicSpanSupportClient(),
    )

    assert problem.schema_version == "policyos.runtime.design_problem.v3"
    assert problem.outcome_of_interest.target_variable == "government.balance"
    tool_schema = gateway.generate_calls[0]["tools"][0]["function"]["parameters"]
    assert tool_schema["properties"]["schema_version"] == {
        "const": "policyos.runtime.design_problem.v3",
        "type": "string",
    }


@pytest.mark.asyncio
async def test_design_problem_front_door_rejects_explicit_legacy_schema_version() -> None:
    """The current compiler cannot relabel an explicit legacy provider payload."""

    gateway = _FakeDesignProblemGateway(
        models=["Qwen/Qwen3-235B-A22B-Instruct-2507-FP8"],
        arguments={
            **_design_problem_tool_args(),
            "schema_version": "policyos.runtime.design_problem.v1",
        },
    )

    with pytest.raises(DesignProblemAuthorityError) as exc_info:
        await build_design_problem_from_nl_request(
            nl_request=(
                "Design a wartime MSME credit guarantee for Ukraine within the stated "
                "UAH 10b budget cap."
            ),
            context=_intent_context(),
            model_name="Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
            gateway_client=gateway,
            span_support_client=_DeterministicSpanSupportClient(),
        )

    assert exc_info.value.code == "design_problem_compiler_schema_version_mismatch"


@pytest.mark.asyncio
async def test_design_problem_front_door_rejects_missing_current_schema_version() -> None:
    """A fresh compiler cannot infer the current schema from a missing field."""

    arguments = _design_problem_tool_args()
    arguments.pop("schema_version")
    gateway = _FakeDesignProblemGateway(
        models=["Qwen/Qwen3-235B-A22B-Instruct-2507-FP8"],
        arguments=arguments,
    )

    with pytest.raises(DesignProblemAuthorityError) as exc_info:
        await build_design_problem_from_nl_request(
            nl_request=(
                "Design a wartime MSME credit guarantee for Ukraine within the stated "
                "UAH 10b budget cap."
            ),
            context=_intent_context(),
            model_name="Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
            gateway_client=gateway,
            span_support_client=_DeterministicSpanSupportClient(),
        )

    assert exc_info.value.code == "design_problem_compiler_schema_version_mismatch"


@pytest.mark.asyncio
async def test_design_problem_prompt_exposes_non_empty_collection_contract() -> None:
    """Make the producer state strict collection invariants before model output."""

    required_collections = {
        "objectives",
        "stakeholders",
        "candidate_lever_space.allowed_operator_kinds",
        "candidate_lever_space.candidate_levers",
    }

    class _PromptBoundGateway(_FakeDesignProblemGateway):
        async def generate(self, **kwargs: Any) -> GatewayLLMResponse:
            self.generate_calls.append(kwargs)
            user_payload = json.loads(str(kwargs.get("user") or "{}"))
            required_semantics = user_payload.get("required_semantics") or {}
            observed = set(required_semantics.get("non_empty_collections") or [])
            arguments = _design_problem_tool_args()
            if observed != required_collections:
                arguments["stakeholders"] = []
            return GatewayLLMResponse(
                content="",
                model="moonshotai/Kimi-K2.6",
                provider="test-gateway",
                tool_calls=[
                    GatewayToolCall(
                        id="call-prompt-bound-design-problem",
                        name="emit_design_problem",
                        arguments=arguments,
                    )
                ],
            )

    gateway = _PromptBoundGateway(
        models=["moonshotai/Kimi-K2.6"],
        arguments={},
    )

    problem = await build_design_problem_from_nl_request(
        nl_request=(
            "Design a wartime MSME credit guarantee for Ukraine within the stated "
            "UAH 10b budget cap."
        ),
        context=_intent_context(as_of="2026-05-12"),
        model_name="moonshotai/Kimi-K2.6",
        gateway_client=gateway,
        span_support_client=_DeterministicSpanSupportClient(),
    )

    assert problem.stakeholders
    assert problem.objectives
    assert problem.candidate_lever_space.candidate_levers
    assert design_problem_compiler_source_semantics_invariant() in str(
        gateway.generate_calls[0]["system"]
    )


def test_design_problem_output_budget_is_derived_from_characterization() -> None:
    """The compiler ceiling is typed, evidence-bound, and not a silent default."""

    policy = _DESIGN_PROBLEM_COMPILER_OUTPUT_POLICY

    assert policy.observed_max_completion_tokens == 5628
    assert policy.max_tokens == 8192
    assert policy.headroom_tokens == 2564
    assert policy.max_tokens == 1 << (policy.observed_max_completion_tokens - 1).bit_length()
    assert "2026-07-14-gy-n10-stage-4" in policy.evidence_ref
    with pytest.raises(ValueError, match="output_budget_not_next_power_of_two"):
        type(policy)(
            observed_max_completion_tokens=policy.observed_max_completion_tokens,
            max_tokens=9000,
            headroom_tokens=3677,
            evidence_ref=policy.evidence_ref,
        )


def test_design_problem_provider_constraint_exposes_existing_time_rule() -> None:
    """The request schema mirrors strict time completeness without changing its gate owner."""

    from polisyos.ir.kernel.time_semantics import TimeSemantics

    canonical_before = json.dumps(
        DesignProblem.model_json_schema(),
        sort_keys=True,
        separators=(",", ":"),
    )
    provider_schema = design_problem_provider_constraint_schema()
    canonical_after = json.dumps(
        DesignProblem.model_json_schema(),
        sort_keys=True,
        separators=(",", ":"),
    )
    time_union = provider_schema["properties"]["jurisdiction_time"]["properties"]["time_semantics"][
        "anyOf"
    ]
    time_schema = next(item for item in time_union if item.get("type") == "object")

    assert canonical_after == canonical_before
    assert {item.get("type") for item in time_union} == {"object", "null"}
    assert time_schema["anyOf"] == [
        {
            "required": ["step_count"],
            "properties": {
                "step_count": {"type": "integer", "minimum": 1},
            },
        },
        {
            "required": ["end_date"],
            "properties": {
                "end_date": {"type": "string", "minLength": 1},
            },
        },
    ]
    TimeSemantics.model_validate(
        {
            "frequency": "Q",
            "start_date": "2026-07-14",
            "step_count": 1,
        }
    )
    TimeSemantics.model_validate(
        {
            "frequency": "Q",
            "start_date": "2026-07-14",
            "end_date": "2027-07-14",
        }
    )
    with pytest.raises(ValueError, match="step_count or end_date must be provided"):
        TimeSemantics.model_validate(
            {
                "frequency": "Q",
                "start_date": "2026-07-14",
                "step_count": None,
                "end_date": None,
            }
        )


def test_design_problem_provider_schema_matches_versioned_slot_grammar() -> None:
    """The current provider contract emits v3 while saved v1/v2 use their own schema."""

    from jsonschema import Draft202012Validator

    schema = design_problem_provider_constraint_schema()
    validator = Draft202012Validator(schema)
    cases = (
        (None, "credit_access", False),
        ("policyos.runtime.design_problem.v1", "government.balance", False),
        ("policyos.runtime.design_problem.v1", "credit_access", False),
        ("policyos.runtime.design_problem.v2", "government.balance", False),
        ("policyos.runtime.design_problem.v2", "credit_access", False),
        ("policyos.runtime.design_problem.v3", "government.balance", True),
        ("policyos.runtime.design_problem.v3", "credit_access", True),
        ("policyos.runtime.design_problem.legacy-import", "credit_access", False),
        ("policyos.runtime.design_problem.legacy-import", "government.balance", False),
    )
    for schema_version, target_slot, expected in cases:
        payload = _design_problem_tool_args()
        if schema_version is None:
            payload.pop("schema_version", None)
        else:
            payload["schema_version"] = schema_version
        payload["candidate_lever_space"]["candidate_levers"][0]["target_slot"] = target_slot
        assert validator.is_valid(payload) is expected, (
            schema_version,
            target_slot,
        )


@pytest.mark.asyncio
async def test_design_problem_front_door_types_provider_output_truncation() -> None:
    """A provider-declared completion ceiling is not a generic JSON/schema failure."""

    class _TruncatedGateway(_FakeDesignProblemGateway):
        async def generate(self, **kwargs: Any) -> GatewayLLMResponse:
            self.generate_calls.append(kwargs)
            return GatewayLLMResponse(
                content="",
                model="moonshotai/Kimi-K2.6",
                provider="test-gateway",
                raw={"choices": [{"finish_reason": "length"}]},
                tool_calls=[
                    GatewayToolCall(
                        id="call-truncated-design-problem",
                        name="emit_design_problem",
                        arguments={},
                        error_envelope={
                            "reason": "tool_call_arguments_parse_error",
                            "details": {"arguments_preview": '{"objectives":'},
                        },
                    )
                ],
            )

    gateway = _TruncatedGateway(
        models=["moonshotai/Kimi-K2.6"],
        arguments={},
    )

    with pytest.raises(DesignProblemAuthorityError) as exc_info:
        await build_design_problem_from_nl_request(
            nl_request="Design a credit guarantee for wartime MSMEs.",
            context=_intent_context(),
            model_name="moonshotai/Kimi-K2.6",
            gateway_client=gateway,
            span_support_client=_DeterministicSpanSupportClient(),
        )

    assert exc_info.value.code == "design_problem_output_truncated"


@pytest.mark.asyncio
async def test_design_problem_front_door_keeps_nontruncated_malformed_output_strict() -> None:
    """Malformed tool arguments do not acquire truncation semantics by shape alone."""

    class _MalformedGateway(_FakeDesignProblemGateway):
        async def generate(self, **kwargs: Any) -> GatewayLLMResponse:
            self.generate_calls.append(kwargs)
            return GatewayLLMResponse(
                content="",
                model="MiniMaxAI/MiniMax-M2.7",
                provider="test-gateway",
                raw={"choices": [{"finish_reason": "tool_calls"}]},
                tool_calls=[
                    GatewayToolCall(
                        id="call-malformed-design-problem",
                        name="emit_design_problem",
                        arguments={},
                        error_envelope={
                            "reason": "tool_call_arguments_parse_error",
                            "details": {"arguments_preview": "<think>reasoning"},
                        },
                    )
                ],
            )

    gateway = _MalformedGateway(
        models=["MiniMaxAI/MiniMax-M2.7"],
        arguments={},
    )

    with pytest.raises(DesignProblemAuthorityError) as exc_info:
        await build_design_problem_from_nl_request(
            nl_request="Design a credit guarantee for wartime MSMEs.",
            context=_intent_context(),
            model_name="MiniMaxAI/MiniMax-M2.7",
            gateway_client=gateway,
            span_support_client=_DeterministicSpanSupportClient(),
        )

    assert exc_info.value.code == "design_problem_validation_failed"


@pytest.mark.asyncio
async def test_plain_language_front_door_calls_real_design_problem_compiler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compile plain language, then return typed N4 limitation without recursive authority."""

    from polisyos.runtime.http.services.control import generation_cycle as generation_cycle_service
    from polisyos.runtime.http.services.control.generation_cycle import (
        N4CandidateProposalExecution,
    )
    from polisyos.runtime.quality.design_generation import (
        DesignGenerationOrganRun,
        GenerationDiversityReport,
        GenerationUnderAResult,
        ModelProfilePreflight,
    )
    from polisyos.runtime.quality.generation_cycle import gy_content_hash
    from polisyos.runtime.quality.promotion_sequence import PromotionRuntime
    from polisyos.runtime.quality.recursive_generation_cycle import RecursiveCycleBudget
    from tests.unit.runtime.quality.test_generation_cycle import REPO_ROOT, _budget

    raw_request = (
        "Design a wartime MSME credit guarantee for Ukraine within the stated UAH 10b budget cap."
    )
    model_id = "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8"
    gateway = _FakeDesignProblemGateway(
        models=[model_id],
        arguments=_design_problem_tool_args(),
    )
    span_support = _DeterministicSpanSupportClient()
    n4_inputs: list[tuple[DesignProblem, str, Path | None]] = []

    async def terminal_n4(
        problem: DesignProblem,
        *,
        model_id: str,
        repo_root: Path | None = None,
        **_: Any,
    ) -> DesignGenerationOrganRun:
        n4_inputs.append((problem, model_id, repo_root))
        return DesignGenerationOrganRun(
            result=GenerationUnderAResult(
                status="generation_unavailable",
                design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
                model_id=model_id,
                preflight=ModelProfilePreflight(
                    status="gateway_unavailable",
                    model_id=model_id,
                    supported_model_ids=(model_id,),
                    reason="candidate_front_door_fixture_terminal",
                ),
                diversity_report=GenerationDiversityReport(
                    min_required=1,
                    candidate_count=0,
                    unique_diversity_key_count=0,
                ),
            )
        )

    def recursive_path_is_forbidden(**_: Any) -> object:
        raise AssertionError("candidate_only_front_door_entered_recursive_controller")

    monkeypatch.setattr(
        "polisyos.runtime.quality.design_generation.generate_design_candidate_proposal_under_a",
        terminal_n4,
    )
    monkeypatch.setattr(
        generation_cycle_service,
        "build_default_recursive_generation_cycle_controller",
        recursive_path_is_forbidden,
    )

    compiled = await generation_cycle_service.compile_and_run_recursive_generation_cycle(
        raw_request=raw_request,
        context=_intent_context(as_of="2026-05-12"),
        model_name=model_id,
        execution_intent="candidate_only",
        compiler_gateway=gateway,
        span_support_client=span_support,
        budget_state=_budget(),
        recursive_budget=RecursiveCycleBudget(
            max_depth=0,
            max_nodes=1,
            min_cycles_per_leaf=1,
            max_cycles_per_leaf=1,
        ),
        promotion_runtime=PromotionRuntime(store=FileSystemCAS(tmp_path / "promotion-cas")),
        eval_safety_verifier=object(),  # type: ignore[arg-type]
        root_evaluation_context=None,
        repo_root=REPO_ROOT,
    )

    assert isinstance(compiled, N4CandidateProposalExecution)
    assert compiled.design_problem.nl_provenance.raw_request == raw_request
    assert compiled.target_world_scope_status == "not_established"
    assert compiled.target_world_model_record_ref is None
    assert len(n4_inputs) == 1
    problem, n4_model_id, n4_repo_root = n4_inputs[0]
    assert problem == compiled.design_problem
    assert problem.outcome_of_interest.target_variable == "firm_survival"
    assert n4_model_id == model_id
    assert n4_repo_root == REPO_ROOT
    assert isinstance(compiled.proposal, DesignGenerationOrganRun)
    assert compiled.proposal.result.status == "generation_unavailable"
    assert compiled.proposal.result.candidates == ()
    assert gateway.generate_calls
    assert gateway.generate_calls[0]["tools"][0]["function"]["name"] == "emit_design_problem"
    assert span_support.calls


@pytest.mark.asyncio
async def test_plain_language_front_door_compiles_hashed_qualified_v3_problem() -> None:
    raw_request = (
        "Design a wartime MSME credit guarantee for Ukraine within the stated UAH 10b budget cap, "
        "and assess Ukraine's government cash balance."
    )

    def government_balance_payload() -> dict[str, Any]:
        payload = _design_problem_tool_args()
        payload["problem_statement"] = (
            "Improve Ukraine's government cash balance using grounded evidence."
        )
        payload["nl_provenance"]["raw_request"] = raw_request
        payload["objectives"][0].update(
            {
                "objective_id": "government_balance",
                "description": "Improve government cash balance.",
                "metric_id": "government_balance",
            }
        )
        payload["outcome_of_interest"].update(
            {
                "target_variable": "government.balance",
                "metric_id": "government_balance",
                "estimand": "Government cash balance for Ukraine.",
            }
        )
        for lever in payload["candidate_lever_space"]["candidate_levers"]:
            lever["target_slot"] = "government.balance"
        return payload

    gateway = _FakeDesignProblemGateway(
        models=["Qwen/Qwen3-235B-A22B-Instruct-2507-FP8"],
        arguments=government_balance_payload(),
    )
    runtime_context = _intent_context(as_of="2026-05-12")
    problem = await build_design_problem_from_nl_request(
        nl_request=raw_request,
        context=runtime_context,
        model_name="Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
        gateway_client=gateway,
        span_support_client=_DeterministicSpanSupportClient(),
    )

    assert problem.nl_provenance.raw_request == raw_request
    assert problem.schema_version == "policyos.runtime.design_problem.v3"
    assert problem.outcome_of_interest.target_variable == "government.balance"
    from polisyos.pdc import gy_content_hash

    design_problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    assert design_problem_ref.startswith("sha256:")
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
            "Assess credit guarantees for MSMEs. Keep fiscal exposure below ten billion hryvnia."
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


def test_selected_materialization_ref_resolves_exact_core_view_and_parent_edge(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts.manifest import ProducerInfo, input_ref_from_artifact_ref

    store = FileSystemCAS(tmp_path / "cas")
    producer = ProducerInfo(component="polisyos.tests.materialization", version="1.0")
    child_options = ArtifactWriteOptions(
        kind="fabric.retrieval_summary",
        media_type="application/json",
        schema=SchemaInfo(name="polisyos.fabric.RetrievalSummary", version="1.0"),
        producer=producer,
    )
    child_payload = {"assessment_status": "not_assessed", "source": "fixture"}
    selected_child = store.put_json(
        child_payload,
        child_options,
        CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    sibling_view = store.put_json(
        child_payload,
        child_options,
        CanonSpec(forbid_floats=False, ensure_ascii=True),
        return_selected_profile=True,
    )
    assert sibling_view.artifact_id == selected_child.artifact_id
    assert sibling_view.manifest_profile_sha256 != selected_child.manifest_profile_sha256

    parent_ref = store.put_json(
        {"quality_report_ref": selected_child.model_dump(mode="json")},
        ArtifactWriteOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
            producer=producer,
            inputs=[input_ref_from_artifact_ref(selected_child, role="quality_report")],
        ),
        CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    parent_manifest = store.get_manifest(parent_ref)
    selected_by_id = {str(selected_child.artifact_id): [selected_child]}
    parent_roles = frozenset({"quality_report", "quality_report_ref"})

    assert (
        _resolve_selected_materialization_ref(
            store,
            selected_child,
            selected_by_id,
            kind="fabric.retrieval_summary",
            parent_manifest=parent_manifest,
            parent_roles=parent_roles,
        )
        == selected_child
    )
    assert (
        _resolve_selected_materialization_ref(
            store,
            selected_child,
            {},
            kind="fabric.retrieval_summary",
            parent_manifest=parent_manifest,
            parent_roles=parent_roles,
        )
        == selected_child
    )
    profileless_child = selected_child.model_copy(update={"manifest_profile_sha256": None})
    assert (
        _resolve_selected_materialization_ref(
            store,
            profileless_child,
            {},
            kind="fabric.retrieval_summary",
            parent_manifest=parent_manifest,
            parent_roles=parent_roles,
        )
        == selected_child
    )
    with pytest.raises(
        RuntimeError,
        match="auto_materialization_selected_ref_not_established",
    ):
        _resolve_selected_materialization_ref(
            store,
            profileless_child,
            {str(selected_child.artifact_id): [sibling_view]},
            kind="fabric.retrieval_summary",
            parent_manifest=parent_manifest,
            parent_roles=parent_roles,
        )

    invalid_views = (
        selected_child.model_copy(update={"manifest_profile_sha256": "sha256:" + "f" * 64}),
        selected_child.model_copy(update={"kind": "foreign.retrieval_summary"}),
        selected_child.model_copy(update={"media_type": "text/plain"}),
    )
    for invalid_view in invalid_views:
        with pytest.raises(
            RuntimeError,
            match="auto_materialization_selected_ref_not_established",
        ):
            _resolve_selected_materialization_ref(
                store,
                invalid_view,
                selected_by_id,
                kind="fabric.retrieval_summary",
            )

    with pytest.raises(
        RuntimeError,
        match="auto_materialization_quality_ref_lineage_not_established",
    ):
        _resolve_selected_materialization_ref(
            store,
            sibling_view,
            {},
            kind="fabric.retrieval_summary",
            parent_manifest=parent_manifest,
            parent_roles=parent_roles,
        )

    parent_input = parent_manifest.inputs[0]
    wrong_parent_manifests = (
        parent_manifest.model_copy(update={"inputs": []}),
        parent_manifest.model_copy(
            update={
                "inputs": [parent_input.model_copy(update={"artifact_id": "sha256:" + "9" * 64})]
            }
        ),
        parent_manifest.model_copy(
            update={"inputs": [parent_input.model_copy(update={"role": "other"})]}
        ),
    )
    for wrong_parent_manifest in wrong_parent_manifests:
        with pytest.raises(
            RuntimeError,
            match="auto_materialization_quality_ref_lineage_not_established",
        ):
            _resolve_selected_materialization_ref(
                store,
                selected_child,
                {},
                kind="fabric.retrieval_summary",
                parent_manifest=wrong_parent_manifest,
                parent_roles=parent_roles,
            )

    missing_ref = selected_child.model_copy(
        update={
            "artifact_id": "sha256:" + "e" * 64,
            "manifest_profile_sha256": "sha256:" + "d" * 64,
        }
    )
    with pytest.raises(
        RuntimeError,
        match="auto_materialization_selected_ref_not_established",
    ):
        _resolve_selected_materialization_ref(
            store,
            missing_ref,
            {},
            kind="fabric.retrieval_summary",
        )

    with pytest.raises(
        RuntimeError,
        match="auto_materialization_selected_ref_not_established",
    ):
        _resolve_selected_materialization_ref(
            store,
            {
                "artifact_id": str(selected_child.artifact_id),
                "kind": "fabric.retrieval_summary",
                "media_type": "application/json",
                "manifest_profile_sha256": "malformed-profile",
            },
            selected_by_id,
            kind="fabric.retrieval_summary",
        )


def test_materialization_input_basis_ignores_later_outputs_but_detects_source_view_change() -> None:
    from polisyos.runtime.http.services.control.nl_pipeline import (
        _reconcile_materialization_input_basis,
    )

    source_input = InputRef(
        artifact_id="sha256:" + "1" * 64,
        role="data_ref",
        manifest_profile_sha256="sha256:" + "a" * 64,
    )
    output_id = "sha256:" + "2" * 64
    initial_basis = _reconcile_materialization_input_basis(
        [source_input],
        currently_published_refs=frozenset(),
        existing_basis=None,
    )

    retry_inputs = [
        source_input,
        InputRef(
            artifact_id=output_id,
            role="production_data_quality_report",
            manifest_profile_sha256="sha256:" + "b" * 64,
        ),
    ]
    assert (
        _reconcile_materialization_input_basis(
            retry_inputs,
            currently_published_refs=frozenset({output_id}),
            existing_basis=initial_basis,
        )
        == initial_basis
    )

    changed_source_view = source_input.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "c" * 64}
    )
    with pytest.raises(RuntimeError, match="auto_materialization_input_basis_changed"):
        _reconcile_materialization_input_basis(
            [changed_source_view, retry_inputs[1]],
            currently_published_refs=frozenset({output_id}),
            existing_basis=initial_basis,
        )


def test_materialization_input_basis_keeps_frozen_generated_lineage_across_reissue() -> None:
    from polisyos.runtime.http.services.control.nl_pipeline import (
        _reconcile_materialization_input_basis,
    )

    source_input = InputRef(
        artifact_id="sha256:" + "1" * 64,
        role="production_data_payload",
        manifest_profile_sha256="sha256:" + "a" * 64,
    )
    frozen_report = InputRef(
        artifact_id="sha256:" + "2" * 64,
        role="production_data_quality_report",
        manifest_profile_sha256="sha256:" + "b" * 64,
    )
    superseding_report = InputRef(
        artifact_id="sha256:" + "3" * 64,
        role="production_data_quality_report",
        manifest_profile_sha256="sha256:" + "c" * 64,
    )
    initial_refs = frozenset({str(frozen_report.artifact_id)})
    initial_basis = _reconcile_materialization_input_basis(
        [source_input, frozen_report],
        currently_published_refs=initial_refs,
        existing_basis=None,
    )

    assert (
        _reconcile_materialization_input_basis(
            [source_input],
            currently_published_refs=frozenset(
                {*initial_refs, str(superseding_report.artifact_id)}
            ),
            existing_basis=initial_basis,
            current_reissuable_report_refs=frozenset(
                {(str(superseding_report.artifact_id), "production_data_quality_report")}
            ),
        )
        == initial_basis
    )

    changed_source = source_input.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "d" * 64}
    )
    with pytest.raises(RuntimeError, match="auto_materialization_input_basis_changed"):
        _reconcile_materialization_input_basis(
            [changed_source],
            currently_published_refs=frozenset(
                {*initial_refs, str(superseding_report.artifact_id)}
            ),
            existing_basis=initial_basis,
            current_reissuable_report_refs=frozenset(
                {(str(superseding_report.artifact_id), "production_data_quality_report")}
            ),
        )

    changed_source_ref = source_input.model_copy(update={"artifact_id": "sha256:" + "4" * 64})
    with pytest.raises(RuntimeError, match="auto_materialization_input_basis_changed"):
        _reconcile_materialization_input_basis(
            [changed_source_ref],
            currently_published_refs=frozenset(
                {*initial_refs, str(superseding_report.artifact_id)}
            ),
            existing_basis=initial_basis,
            current_reissuable_report_refs=frozenset(
                {(str(superseding_report.artifact_id), "production_data_quality_report")}
            ),
        )


def test_materialization_input_basis_restores_only_verified_report_edges() -> None:
    from polisyos.runtime.http.services.control.nl_pipeline import (
        _restore_frozen_materialization_report_inputs,
    )

    source = InputRef(
        artifact_id="sha256:" + "1" * 64,
        role="production_data_payload",
        manifest_profile_sha256="sha256:" + "a" * 64,
    )
    predecessor = InputRef(
        artifact_id="sha256:" + "2" * 64,
        role="production_data_quality_report",
        manifest_profile_sha256="sha256:" + "b" * 64,
    )
    frozen_inputs = (source, predecessor)
    basis = (frozen_inputs, frozenset({str(predecessor.artifact_id)}))
    verified_predecessor = frozenset(
        {
            (
                str(predecessor.artifact_id),
                predecessor.role,
                predecessor.manifest_profile_sha256,
            )
        }
    )
    report_roles = frozenset({"production_data_quality_report", "fabric_retrieval_trace"})

    restored, recovered_ids = _restore_frozen_materialization_report_inputs(
        [source],
        existing_basis=basis,
        persisted_output_inputs=frozen_inputs,
        reissuable_report_roles=report_roles,
        verified_reissuable_report_refs=verified_predecessor,
    )
    assert restored == frozen_inputs
    assert recovered_ids == frozenset({str(predecessor.artifact_id)})

    with pytest.raises(RuntimeError, match="auto_materialization_input_basis_changed"):
        _restore_frozen_materialization_report_inputs(
            [source],
            existing_basis=basis,
            persisted_output_inputs=(
                source,
                predecessor.model_copy(update={"manifest_profile_sha256": "sha256:" + "c" * 64}),
            ),
            reissuable_report_roles=report_roles,
            verified_reissuable_report_refs=verified_predecessor,
        )

    with pytest.raises(RuntimeError, match="auto_materialization_input_basis_changed"):
        _restore_frozen_materialization_report_inputs(
            [predecessor],
            existing_basis=basis,
            persisted_output_inputs=frozen_inputs,
            reissuable_report_roles=report_roles,
            verified_reissuable_report_refs=verified_predecessor,
        )

    with pytest.raises(RuntimeError, match="auto_materialization_input_basis_changed"):
        _restore_frozen_materialization_report_inputs(
            [source],
            existing_basis=basis,
            persisted_output_inputs=frozen_inputs,
            reissuable_report_roles=report_roles,
            verified_reissuable_report_refs=frozenset(),
        )


def test_materialization_recovery_requires_current_cas_owner_admission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.http.services.control.nl_pipeline import (
        _reconcile_materialization_input_basis,
        _restore_frozen_materialization_report_inputs,
        _runtime_quality_report_cas_publication_is_admitted,
        _runtime_quality_report_materialization_input_is_verified,
    )
    from polisyos.runtime.quality import authority as authority_module
    from tests.unit.runtime.quality.test_runtime_quality_report_owner_contract import (
        _persist_report,
    )

    report_key = "fabric_retrieval_trace"
    ref_key = "fabric_retrieval_trace_ref"
    store, result, report, envelope = _persist_report(
        tmp_path,
        report_key=report_key,
        run_suffix="materialization-recovery",
        payload={
            "schema_version": "1.0",
            "status": "pass",
            "claims": [{"claim_id": "reissuable-predecessor"}],
        },
    )
    selected_ref = result.cas_ref
    predecessor_id = str(selected_ref.artifact_id)
    assert selected_ref.manifest_profile_sha256 is not None

    source_ref = store.put_json(
        {"source": "same frozen materialization"},
        ArtifactWriteOptions(kind="fabric.production_data_payload", media_type="application/json"),
        return_selected_profile=True,
    )
    assert source_ref.manifest_profile_sha256 is not None
    source_input = InputRef(
        artifact_id=source_ref.artifact_id,
        role="production_data_payload",
        manifest_profile_sha256=source_ref.manifest_profile_sha256,
    )
    predecessor_input = InputRef(
        artifact_id=selected_ref.artifact_id,
        role=ref_key.removesuffix("_ref"),
        manifest_profile_sha256=selected_ref.manifest_profile_sha256,
    )
    output_ref = store.put_json(
        {"output": "previously materialized"},
        ArtifactWriteOptions(
            kind="runtime.test.materialization_output",
            media_type="application/json",
            inputs=[source_input, predecessor_input],
        ),
        return_selected_profile=True,
    )
    frozen_inputs = tuple(store.get_manifest(output_ref).inputs)
    assert frozen_inputs == (source_input, predecessor_input)
    basis = (
        frozen_inputs,
        frozenset({str(source_ref.artifact_id), predecessor_id}),
    )
    role_set = frozenset({"fabric_retrieval_trace", "production_data_quality_report"})

    def is_verified(
        item: InputRef,
        *,
        ref: ArtifactRef = selected_ref,
        report_view: Mapping[str, Any] = report,
        selected_envelope: Mapping[str, Any] | None = envelope,
        selected_report_key: str = report_key,
        selected_ref_key: str = ref_key,
    ) -> bool:
        runtime_refs: dict[str, object] = {selected_ref_key: str(ref.artifact_id)}
        artifact_refs: dict[str, object] = {selected_ref_key: ref}

        def verify_current(
            candidate_report_key: str,
            candidate_ref_key: str,
            expected_ref: str,
        ) -> bool:
            if (
                candidate_report_key != selected_report_key
                or candidate_ref_key != selected_ref_key
                or expected_ref != str(ref.artifact_id)
            ):
                return False
            return _runtime_quality_report_cas_publication_is_admitted(
                artifact_store=store,
                selected_ref=ref,
                runtime_ref=expected_ref,
                report_key=candidate_report_key,
                ref_key=candidate_ref_key,
                report=report_view,
                envelope=selected_envelope,
            )

        return _runtime_quality_report_materialization_input_is_verified(
            item,
            output_report_key="production_data_quality_report",
            reissuable_report_roles=role_set,
            runtime_quality_refs=runtime_refs,
            runtime_quality_artifact_refs=artifact_refs,
            current_publication_verifier=verify_current,
        )

    def restore(
        *,
        current_inputs: tuple[InputRef, ...] = (source_input,),
        item: InputRef = predecessor_input,
        ref: ArtifactRef = selected_ref,
        report_view: Mapping[str, Any] = report,
        selected_envelope: Mapping[str, Any] | None = envelope,
    ) -> tuple[tuple[InputRef, ...], frozenset[str]]:
        verified_refs = (
            frozenset({(str(item.artifact_id), item.role, item.manifest_profile_sha256)})
            if is_verified(
                item,
                ref=ref,
                report_view=report_view,
                selected_envelope=selected_envelope,
            )
            else frozenset()
        )
        return _restore_frozen_materialization_report_inputs(
            current_inputs,
            existing_basis=basis,
            persisted_output_inputs=frozen_inputs,
            reissuable_report_roles=role_set,
            verified_reissuable_report_refs=verified_refs,
        )

    restored, recovered_ids = restore()
    assert restored == frozen_inputs
    assert recovered_ids == frozenset({predecessor_id})
    assert (
        _reconcile_materialization_input_basis(
            restored,
            currently_published_refs=basis[1] - recovered_ids,
            existing_basis=basis,
        )
        == basis
    )

    wrong_owner_ref = selected_ref.model_copy(update={"kind": "runtime.unowned_report"})
    wrong_profile_ref = selected_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "0" * 64}
    )
    wrong_profile_input = predecessor_input.model_copy(
        update={"manifest_profile_sha256": wrong_profile_ref.manifest_profile_sha256}
    )
    invalid_envelope = {**envelope, "authority_role": "candidate"}
    assert not is_verified(predecessor_input, ref=wrong_owner_ref)
    assert not is_verified(wrong_profile_input, ref=wrong_profile_ref)
    assert not is_verified(predecessor_input, selected_envelope=invalid_envelope)
    assert not _runtime_quality_report_cas_publication_is_admitted(
        artifact_store=store,
        selected_ref=wrong_owner_ref,
        runtime_ref=predecessor_id,
        report_key=report_key,
        ref_key=ref_key,
        report=report,
        envelope=envelope,
    )

    for item, ref, selected_envelope in (
        (predecessor_input, wrong_owner_ref, envelope),
        (wrong_profile_input, wrong_profile_ref, envelope),
        (predecessor_input, selected_ref, invalid_envelope),
    ):
        with pytest.raises(RuntimeError, match="auto_materialization_input_basis_changed"):
            restore(item=item, ref=ref, selected_envelope=selected_envelope)

    with pytest.raises(RuntimeError, match="auto_materialization_input_basis_changed"):
        restore(current_inputs=())

    changed_source = source_input.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "f" * 64}
    )
    with pytest.raises(RuntimeError, match="auto_materialization_input_basis_changed"):
        restore(current_inputs=(changed_source,))

    # Keep owner markers, payloads, and refs fixed while removing the authority gate.
    # Invalid evidence would then be admitted, proving the negative is gate-sensitive.
    with monkeypatch.context() as bypass:
        bypass.setattr(
            authority_module,
            "runtime_quality_report_cas_admission_issues",
            lambda **_kwargs: [],
        )
        bypassed_inputs, bypassed_ids = restore(selected_envelope=invalid_envelope)
        assert bypassed_inputs == frozen_inputs
        assert bypassed_ids == frozenset({predecessor_id})


def test_historical_materialization_report_input_rebuilds_owner_from_exact_cas_profile(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts.manifest import ArtifactTenantContextInfo
    from polisyos.runtime.http.services.control.nl_pipeline import (
        _runtime_quality_historical_report_materialization_input_is_verified,
        _runtime_quality_report_materialization_input_is_verified,
    )
    from polisyos.runtime.quality.report_registry import runtime_quality_report_owner_contract
    from tests.unit.runtime.quality.test_runtime_quality_report_owner_contract import (
        _persist_report,
    )

    report_key = "fabric_retrieval_trace"
    ref_key = "fabric_retrieval_trace_ref"
    store, result, _report, _envelope = _persist_report(
        tmp_path,
        report_key=report_key,
        run_suffix="historical-materialization",
        payload={"schema_version": "1.0", "status": "pass", "claims": []},
    )
    selected_ref = result.cas_ref
    predecessor = InputRef(
        artifact_id=selected_ref.artifact_id,
        role="fabric_retrieval_trace",
        manifest_profile_sha256=selected_ref.manifest_profile_sha256,
    )
    owner = ArtifactTenantContextInfo(tenant_id="tenant-1", cell_id="cell-a")
    contract = runtime_quality_report_owner_contract(report_key, ref_key)
    assert contract is not None

    def current_owner_context_matches(basis: Any) -> bool:
        envelope = basis.authority_envelope
        closure = envelope.get("same_input_closure")
        return (
            envelope.get("run_id") == "run-owner-historical-materialization"
            and envelope.get("job_id") == "job-owner-historical-materialization"
            and envelope.get("tenant_id") == "tenant-1"
            and envelope.get("cell_id") == "cell-a"
            and envelope.get("requested_execution_profile") == "production"
            and envelope.get("effective_execution_profile") == "production"
            and envelope.get("phase") == contract.phase
            and isinstance(closure, dict)
            and closure.get("run_id") == "run-owner-historical-materialization"
            and closure.get("job_id") == "job-owner-historical-materialization"
            and closure.get("tenant_id") == "tenant-1"
            and closure.get("cell_id") == "cell-a"
        )

    def verify(basis: Any) -> bool:
        return current_owner_context_matches(basis)

    args = {
        "report_key": report_key,
        "ref_key": ref_key,
        "artifact_store": store,
        "tenant_context": owner,
        "current_publication_verifier": verify,
    }
    assert _runtime_quality_historical_report_materialization_input_is_verified(predecessor, **args)
    assert not _runtime_quality_historical_report_materialization_input_is_verified(
        predecessor.model_copy(update={"manifest_profile_sha256": "sha256:" + "0" * 64}), **args
    )
    assert not _runtime_quality_historical_report_materialization_input_is_verified(
        predecessor.model_copy(update={"role": "production_data_quality_report"}), **args
    )
    assert not _runtime_quality_historical_report_materialization_input_is_verified(
        predecessor,
        **{
            **args,
            "tenant_context": ArtifactTenantContextInfo(
                tenant_id="tenant-other", cell_id="cell-other"
            ),
        },
    )
    assert not _runtime_quality_historical_report_materialization_input_is_verified(
        predecessor, **{**args, "current_publication_verifier": lambda _basis: False}
    )

    current_output_ref = store.put_json(
        {"status": "new output"},
        ArtifactWriteOptions(
            kind=contract.artifact_kind,
            media_type=contract.media_type,
            tenant_context=owner,
        ),
        return_selected_profile=True,
    )
    assert current_output_ref.artifact_id != selected_ref.artifact_id
    current_refs = {ref_key: str(current_output_ref.artifact_id)}
    current_artifacts = {ref_key: current_output_ref}

    def verify_historical_edge(
        candidate_report_key: str, candidate_ref_key: str, candidate: InputRef
    ) -> bool:
        return (
            candidate_report_key == report_key
            and candidate_ref_key == ref_key
            and _runtime_quality_historical_report_materialization_input_is_verified(
                candidate, **args
            )
        )

    assert _runtime_quality_report_materialization_input_is_verified(
        predecessor,
        output_report_key=report_key,
        reissuable_report_roles=frozenset({"fabric_retrieval_trace"}),
        runtime_quality_refs=current_refs,
        runtime_quality_artifact_refs=current_artifacts,
        current_publication_verifier=lambda *_args: False,
        historical_publication_verifier=verify_historical_edge,
    )
    assert not _runtime_quality_report_materialization_input_is_verified(
        predecessor,
        output_report_key=report_key,
        reissuable_report_roles=frozenset({"fabric_retrieval_trace"}),
        runtime_quality_refs={ref_key: str(selected_ref.artifact_id)},
        runtime_quality_artifact_refs={ref_key: selected_ref},
        current_publication_verifier=lambda *_args: False,
        historical_publication_verifier=verify_historical_edge,
    )


def test_nl_child_json_writer_binds_admitted_tenant_and_refuses_foreign_input(
    tmp_path: Path,
) -> None:
    import asyncio

    from polisyos.core.artifacts import (
        ArtifactOwnershipError,
        ensure_async_artifact_store,
        input_ref_from_artifact_ref,
    )
    from polisyos.core.artifacts.backends.config import (
        with_ambient_ownership_enforcement_if_supported,
    )
    from polisyos.core.artifacts.manifest import ArtifactTenantContextInfo
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.services.control.nl_pipeline import _put_nl_tenant_owned_json

    store = with_ambient_ownership_enforcement_if_supported(FileSystemCAS(tmp_path / "cas"))
    owner = ArtifactTenantContextInfo(tenant_id="tenant-owner", cell_id="cell-owner")
    foreign = ArtifactTenantContextInfo(tenant_id="tenant-foreign", cell_id="cell-foreign")
    with tenant_scope(None, tenant_id=owner.tenant_id, cell_id=owner.cell_id):
        owner_ref = store.put_json(
            {"source": "owner"},
            ArtifactWriteOptions(
                kind="runtime.nl.test_input", media_type="application/json", tenant_context=owner
            ),
            return_selected_profile=True,
        )
    with tenant_scope(None, tenant_id=foreign.tenant_id, cell_id=foreign.cell_id):
        foreign_ref = store.put_json(
            {"source": "foreign"},
            ArtifactWriteOptions(
                kind="runtime.nl.test_input", media_type="application/json", tenant_context=foreign
            ),
            return_selected_profile=True,
        )
    async_store = ensure_async_artifact_store(store)

    def write(payload: object, input_ref: InputRef, context: ArtifactTenantContextInfo) -> Any:
        return asyncio.run(
            _put_nl_tenant_owned_json(
                async_store,
                payload,
                ArtifactWriteOptions(
                    kind="runtime.nl.test_child", media_type="application/json", inputs=[input_ref]
                ),
                tenant_context=context,
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )
        )

    owner_input = input_ref_from_artifact_ref(owner_ref, role="source")
    selected = write({"result": "same-owner"}, owner_input, owner)
    with tenant_scope(None, tenant_id=owner.tenant_id, cell_id=owner.cell_id):
        selected_manifest = store.get_manifest(selected)
    assert selected_manifest.tenant_context == owner
    assert selected_manifest.inputs == [owner_input]
    assert selected.manifest_profile_sha256 is not None

    foreign_input = input_ref_from_artifact_ref(foreign_ref, role="source")
    with pytest.raises(ArtifactOwnershipError):
        write({"result": "cross-owner"}, foreign_input, owner)
    with pytest.raises(RuntimeError, match="nl_child_artifact_tenant_context_mismatch"):
        asyncio.run(
            _put_nl_tenant_owned_json(
                async_store,
                {"result": "conflicting-context"},
                ArtifactWriteOptions(
                    kind="runtime.nl.test_child",
                    media_type="application/json",
                    tenant_context=foreign,
                ),
                tenant_context=owner,
                canon_spec=CanonSpec(forbid_floats=False),
            )
        )


def test_runtime_quality_replay_candidate_requires_exact_typed_input_edges() -> None:
    first = InputRef(
        artifact_id="sha256:" + "1" * 64,
        role="production_data_quality_report",
        manifest_profile_sha256="sha256:" + "a" * 64,
    )
    second = InputRef(
        artifact_id="sha256:" + "2" * 64,
        role="data_snapshot",
        manifest_profile_sha256="sha256:" + "b" * 64,
    )
    ids = (str(first.artifact_id), str(second.artifact_id))
    assert _runtime_quality_candidate_inputs_match(
        manifest_inputs=(first, second),
        envelope_input_refs=ids,
        closure_input_refs=ids,
        expected_inputs=(first, second),
    )

    mutations = (
        first.model_copy(update={"role": "normative_applicability_report"}),
        first.model_copy(update={"manifest_profile_sha256": "sha256:" + "c" * 64}),
    )
    for changed in mutations:
        assert not _runtime_quality_candidate_inputs_match(
            manifest_inputs=(changed, second),
            envelope_input_refs=ids,
            closure_input_refs=ids,
            expected_inputs=(first, second),
        )
    assert not _runtime_quality_candidate_inputs_match(
        manifest_inputs=(second, first),
        envelope_input_refs=ids,
        closure_input_refs=ids,
        expected_inputs=(first, second),
    )
    assert not _runtime_quality_candidate_inputs_match(
        manifest_inputs=(first, second),
        envelope_input_refs=ids,
        closure_input_refs=(ids[1], ids[0]),
        expected_inputs=(first, second),
    )


def test_runtime_quality_reentry_reconciles_only_verified_later_report_inputs() -> None:
    from polisyos.runtime.http.services.control.nl_pipeline import (
        _reconcile_runtime_quality_report_reentry_inputs,
    )

    original_inputs = tuple(
        InputRef(
            artifact_id="sha256:" + str(index) * 64,
            role=f"source_{index}",
            manifest_profile_sha256="sha256:" + chr(96 + index) * 64,
        )
        for index in range(1, 7)
    )
    later_report = InputRef(
        artifact_id="sha256:" + "7" * 64,
        role="production_data_quality_report",
        manifest_profile_sha256="sha256:" + "7" * 64,
    )

    assert (
        _reconcile_runtime_quality_report_reentry_inputs(
            (*original_inputs, later_report),
            original_inputs,
            (later_report,),
        )
        == original_inputs
    )

    unverified_fabric_ref = InputRef(
        artifact_id="sha256:" + "8" * 64,
        role="fabric.evidence_bundle",
        manifest_profile_sha256="sha256:" + "8" * 64,
    )
    with pytest.raises(RuntimeError, match="runtime_quality_publication_reuse_inputs_mismatch"):
        _reconcile_runtime_quality_report_reentry_inputs(
            (*original_inputs, later_report, unverified_fabric_ref),
            original_inputs,
            (later_report,),
        )

    changed_original = original_inputs[0].model_copy(
        update={"manifest_profile_sha256": "sha256:" + "f" * 64}
    )
    with pytest.raises(RuntimeError, match="runtime_quality_publication_reuse_inputs_mismatch"):
        _reconcile_runtime_quality_report_reentry_inputs(
            (changed_original, *original_inputs[1:], later_report),
            original_inputs,
            (later_report,),
        )


def test_runtime_quality_reentry_ref_can_be_resolved_without_runtime_cache() -> None:
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.runtime.http.services.control.nl_pipeline import (
        _runtime_quality_reuse_ref_matches_selected,
    )

    selected = ArtifactRef.model_validate(
        {
            "artifact_id": "sha256:" + "a" * 64,
            "manifest_profile_sha256": "sha256:" + "b" * 64,
            "kind": "fabric.retrieval_trace",
            "media_type": "application/json",
        }
    )
    selected_id = str(selected.artifact_id)
    assert _runtime_quality_reuse_ref_matches_selected(selected, selected_id, None, None)
    assert not _runtime_quality_reuse_ref_matches_selected(
        selected,
        selected_id,
        "sha256:" + "c" * 64,
        None,
    )
    changed_profile = selected.model_copy(update={"manifest_profile_sha256": "sha256:" + "d" * 64})
    assert not _runtime_quality_reuse_ref_matches_selected(
        selected,
        selected_id,
        None,
        changed_profile,
    )


def test_runtime_quality_reentry_rejects_candidate_closure_refs_without_typed_inputs() -> None:
    candidate = _RuntimeQualityPublicationCandidate(
        "2026-10-19T00:00:00+00:00",
        "2026-10-19",
        "sha256:" + "1" * 64,
        "sha256:" + "2" * 64,
        None,
        None,
    )
    current = {
        "policy_intent_envelope_ref": candidate.policy_intent_ref,
        # A report output with the old closure key cannot replace the typed source edge.
        "production_data_quality_report_ref": "sha256:" + "9" * 64,
        "normative_applicability_report_ref": "sha256:" + "3" * 64,
    }
    with pytest.raises(
        NaturalLanguagePipelineRefusalError,
        match="runtime_quality_same_input_identity_not_established",
    ):
        _runtime_quality_closure_reference_values(
            current,
            candidate=candidate,
            output_artifact_id="sha256:" + "f" * 64,
            ref_key="decision_artifact_quality_report_ref",
        )


def test_runtime_quality_closure_refs_bind_typed_sources_and_leave_legal_snapshot_unbound() -> None:
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.runtime.http.services.control.nl_pipeline import (
        _runtime_quality_candidate_inputs_match,
        _runtime_quality_closure_reference_values,
    )

    policy_ref = "sha256:" + "1" * 64
    production_payload_ref = "sha256:" + "2" * 64
    report_projection_ref = "sha256:" + "8" * 64
    normative_report_ref = "sha256:" + "3" * 64
    values = {
        "policy_intent_envelope_ref": policy_ref,
        # These current outputs are projections. Neither is a source closure input.
        "production_data_quality_report_ref": report_projection_ref,
        "normative_applicability_report_ref": normative_report_ref,
    }
    candidate = _RuntimeQualityPublicationCandidate(
        "2026-10-19T00:00:00+00:00",
        "2026-10-19",
        policy_ref,
        production_payload_ref,
        None,
        None,
    )
    source_input = InputRef.model_validate(
        {
            "artifact_id": production_payload_ref,
            "role": "production_data_payload",
            "manifest_profile_sha256": "sha256:" + "b" * 64,
        }
    )
    typed_inputs = [
        InputRef.model_validate(
            {
                "artifact_id": policy_ref,
                "role": "policy_intent_envelope",
                "manifest_profile_sha256": "sha256:" + "a" * 64,
            }
        ),
        source_input,
    ]
    refs = {
        "policy_intent_envelope_ref": ArtifactRef.model_validate(
            {
                "artifact_id": policy_ref,
                "manifest_profile_sha256": "sha256:" + "a" * 64,
                "kind": "runtime.policy_intent_envelope",
                "media_type": "application/json",
            }
        ),
        "production_data_quality_report_ref": ArtifactRef.model_validate(
            {
                "artifact_id": report_projection_ref,
                "manifest_profile_sha256": "sha256:" + "c" * 64,
                "kind": "runtime.production_data_quality_report",
                "media_type": "application/json",
            }
        ),
        "normative_applicability_report_ref": ArtifactRef.model_validate(
            {
                "artifact_id": normative_report_ref,
                "manifest_profile_sha256": "sha256:" + "d" * 64,
                "kind": "lex.normative_applicability_report",
                "media_type": "application/json",
            }
        ),
    }
    verified: list[tuple[str, str]] = []

    def verify_owner(ref_key: str, artifact_id: str) -> bool:
        verified.append((ref_key, artifact_id))
        return refs.get(ref_key) is not None and str(refs[ref_key].artifact_id) == artifact_id

    closure = _runtime_quality_closure_reference_values(
        values,
        candidate=candidate,
        output_artifact_id="sha256:" + "f" * 64,
        ref_key="decision_artifact_quality_report_ref",
        current_inputs=typed_inputs,
        current_artifact_refs=refs,
        current_report_verifier=verify_owner,
    )
    assert closure == {
        "policy_intent_ref": policy_ref,
        "production_data_manifest_ref": production_payload_ref,
        "legal_snapshot_ref": None,
    }
    assert closure["production_data_manifest_ref"] != values["production_data_quality_report_ref"]
    assert closure["legal_snapshot_ref"] is None
    assert set(verified) == {("policy_intent_envelope_ref", policy_ref)}

    unrelated_source = source_input.model_copy(update={"artifact_id": "sha256:" + "e" * 64})
    with pytest.raises(
        NaturalLanguagePipelineRefusalError,
        match="runtime_quality_same_input_identity_not_established",
    ):
        _runtime_quality_closure_reference_values(
            values,
            candidate=candidate,
            output_artifact_id="sha256:" + "f" * 64,
            ref_key="decision_artifact_quality_report_ref",
            current_inputs=[typed_inputs[0], unrelated_source],
            current_artifact_refs=refs,
            current_report_verifier=verify_owner,
        )

    with pytest.raises(
        NaturalLanguagePipelineRefusalError,
        match="runtime_quality_same_input_identity_not_established",
    ):
        _runtime_quality_closure_reference_values(
            values,
            candidate=candidate,
            output_artifact_id="sha256:" + "f" * 64,
            ref_key="decision_artifact_quality_report_ref",
            current_inputs=[*typed_inputs, source_input],
            current_artifact_refs=refs,
            current_report_verifier=verify_owner,
        )

    changed_source_profile = source_input.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "e" * 64}
    )
    source_id = str(source_input.artifact_id)
    assert not _runtime_quality_candidate_inputs_match(
        manifest_inputs=[source_input],
        envelope_input_refs=[source_id],
        closure_input_refs=[source_id],
        expected_inputs=[changed_source_profile],
    )

    legacy_legal_candidate = candidate._replace(legal_snapshot_ref=normative_report_ref)
    with pytest.raises(
        NaturalLanguagePipelineRefusalError,
        match="runtime_quality_same_input_identity_not_established",
    ):
        _runtime_quality_closure_reference_values(
            values,
            candidate=legacy_legal_candidate,
            output_artifact_id="sha256:" + "f" * 64,
            ref_key="decision_artifact_quality_report_ref",
            current_inputs=typed_inputs,
            current_artifact_refs=refs,
            current_report_verifier=verify_owner,
        )

    semantic_ref = "sha256:" + "4" * 64
    semantic_candidate = candidate._replace(semantic_binding_ref=semantic_ref)
    semantic_selected_ref = ArtifactRef.model_validate(
        {
            "artifact_id": semantic_ref,
            "manifest_profile_sha256": "sha256:" + "d" * 64,
            "kind": "runtime.semantic_binding_ledger",
            "media_type": "application/json",
        }
    )
    refs["semantic_binding_ledger_ref"] = semantic_selected_ref
    from polisyos.runtime.http.services.control.nl_pipeline import (
        _runtime_quality_semantic_binding_reference,
    )

    with pytest.raises(
        NaturalLanguagePipelineRefusalError,
        match="runtime_quality_same_input_identity_not_established",
    ):
        _runtime_quality_semantic_binding_reference(
            report_payload={},
            explicit_ref=None,
            runtime_quality_refs={"semantic_binding_ledger_ref": semantic_ref},
            candidate=semantic_candidate,
            output_artifact_id="sha256:" + "f" * 64,
            ref_key="decision_artifact_quality_report_ref",
            current_inputs=(),
            current_artifact_refs=refs,
            current_report_verifier=verify_owner,
        )

    with pytest.raises(
        NaturalLanguagePipelineRefusalError,
        match="runtime_quality_same_input_identity_not_established",
    ):
        _runtime_quality_closure_reference_values(
            values,
            candidate=candidate,
            output_artifact_id="sha256:" + "f" * 64,
            ref_key="decision_artifact_quality_report_ref",
            current_inputs=(),
            current_artifact_refs=refs,
            current_report_verifier=lambda _ref_key, _artifact_id: False,
        )


def test_runtime_quality_replay_closure_pointer_families_refuse_rebinding() -> None:
    candidate = _RuntimeQualityPublicationCandidate(
        "2026-10-19T00:00:00+00:00",
        "2026-10-19",
        "sha256:" + "1" * 64,
        "sha256:" + "2" * 64,
        None,
        "sha256:" + "4" * 64,
    )
    output_id = "sha256:" + "f" * 64
    production_output_projection = "sha256:" + "9" * 64
    current = {
        "policy_intent_envelope_ref": candidate.policy_intent_ref,
        "production_data_quality_report_ref": production_output_projection,
        "production_data_payload_ref": candidate.production_data_manifest_ref,
        "normative_applicability_report_ref": "sha256:" + "3" * 64,
    }
    expected = {
        "policy_intent_ref": candidate.policy_intent_ref,
        "production_data_manifest_ref": candidate.production_data_manifest_ref,
        "legal_snapshot_ref": None,
    }
    typed_inputs = [
        InputRef.model_validate(
            {
                "artifact_id": current["policy_intent_envelope_ref"],
                "role": "policy_intent_envelope",
                "manifest_profile_sha256": "sha256:" + "1" * 64,
            }
        ),
        InputRef.model_validate(
            {
                "artifact_id": current["production_data_payload_ref"],
                "role": "production_data_payload",
                "manifest_profile_sha256": "sha256:" + "2" * 64,
            }
        ),
    ]
    assert (
        _runtime_quality_closure_reference_values(
            {},
            candidate=candidate,
            output_artifact_id=output_id,
            ref_key="decision_artifact_quality_report_ref",
            current_inputs=typed_inputs,
        )
        == expected
    )

    with pytest.raises(
        NaturalLanguagePipelineRefusalError,
        match="runtime_quality_same_input_identity_not_established",
    ):
        _runtime_quality_closure_reference_values(
            current,
            candidate=candidate,
            output_artifact_id=output_id,
            ref_key="decision_artifact_quality_report_ref",
            current_inputs=typed_inputs,
            current_artifact_refs={},
        )

    # A report output projection and an unavailable legal snapshot cannot fill source closure.
    assert (
        _runtime_quality_closure_reference_values(
            {
                "production_data_quality_report_ref": production_output_projection,
                "normative_applicability_report_ref": "not-an-artifact-reference",
            },
            candidate=candidate,
            output_artifact_id=output_id,
            ref_key="decision_artifact_quality_report_ref",
            current_inputs=typed_inputs,
        )
        == expected
    )

    for current_key in (
        "policy_intent_envelope_ref",
        "production_data_payload_ref",
    ):
        rebound = dict(current)
        rebound[current_key] = "sha256:" + "e" * 64
        with pytest.raises(
            NaturalLanguagePipelineRefusalError,
            match="runtime_quality_same_input_identity_not_established",
        ):
            _runtime_quality_closure_reference_values(
                rebound,
                candidate=candidate,
                output_artifact_id=output_id,
                ref_key="decision_artifact_quality_report_ref",
                current_inputs=typed_inputs,
            )

        self_republication = {**current, current_key: output_id}
        with pytest.raises(
            NaturalLanguagePipelineRefusalError,
            match="runtime_quality_same_input_identity_not_established",
        ):
            _runtime_quality_closure_reference_values(
                self_republication,
                candidate=candidate,
                output_artifact_id=output_id,
                ref_key=current_key,
                current_inputs=typed_inputs,
            )

    for malformed in ("", None, [], {"artifact_id": output_id}):
        with pytest.raises(
            NaturalLanguagePipelineRefusalError,
            match="runtime_quality_identity_reference_invalid",
        ):
            _runtime_quality_closure_reference_values(
                {"production_data_payload_ref": malformed},
                candidate=candidate,
                output_artifact_id=output_id,
                ref_key="decision_artifact_quality_report_ref",
                current_inputs=typed_inputs,
            )
    with pytest.raises(NaturalLanguagePipelineRefusalError):
        _runtime_quality_closure_reference_values(
            {},
            candidate=candidate,
            output_artifact_id=output_id,
            ref_key="decision_artifact_quality_report_ref",
            current_inputs=[],
        )


def test_runtime_quality_replay_semantic_binding_refuses_rebound_sources(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts.manifest import ProducerInfo
    from polisyos.runtime.quality.report_registry import (
        runtime_quality_report_owner_contract,
        runtime_quality_report_owner_marker,
    )
    from polisyos.runtime.quality.semantic_binding import build_semantic_binding_ledger

    ref_key = "semantic_binding_ledger_ref"
    owner = runtime_quality_report_owner_contract("semantic_binding_ledger", ref_key)
    assert owner is not None
    marker = runtime_quality_report_owner_marker("semantic_binding_ledger", ref_key)
    assert marker is not None

    ledger_payload = build_semantic_binding_ledger(
        policy_intent={"intent_id": "policy-intent-1"},
        runtime_refs={"policy_intent_ref": "sha256:" + "1" * 64},
    )
    semantic_identity = str(ledger_payload["semantic_binding_ref"])
    store = FileSystemCAS(tmp_path / "cas")
    writer_payload = {**ledger_payload, "runtime_authority_payload": marker}
    selected_ref = store.put_json(
        writer_payload,
        ArtifactWriteOptions(
            kind=owner.artifact_kind,
            media_type=owner.media_type,
            schema=SchemaInfo(name=owner.schema_name, version=owner.schema_version),
            producer=ProducerInfo(
                component=owner.producer_component,
                version=owner.producer_version,
            ),
        ),
        CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    selected_id = str(selected_ref.artifact_id)
    assert selected_id != semantic_identity
    semantic_input = InputRef(
        artifact_id=selected_ref.artifact_id,
        role="semantic_binding_ledger",
        manifest_profile_sha256=selected_ref.manifest_profile_sha256,
    )
    selected_refs = {ref_key: selected_ref}
    current_refs = {ref_key: selected_id}
    candidate = _RuntimeQualityPublicationCandidate(
        "2026-10-19T00:00:00+00:00",
        "2026-10-19",
        None,
        None,
        None,
        semantic_identity,
    )
    output_id = "sha256:" + "f" * 64

    def resolve(**overrides: Any) -> str | None:
        kwargs: dict[str, Any] = {
            "report_payload": {},
            "explicit_ref": None,
            "runtime_quality_refs": current_refs,
            "candidate": candidate,
            "output_artifact_id": output_id,
            "ref_key": "decision_artifact_quality_report_ref",
            "current_inputs": [semantic_input],
            "current_artifact_refs": selected_refs,
            "artifact_store": store,
        }
        kwargs.update(overrides)
        refs = kwargs["runtime_quality_refs"]
        kwargs["current_report_verifier"] = lambda current_key, expected_id: (
            current_key == ref_key and refs.get(current_key) == expected_id
        )
        return _runtime_quality_semantic_binding_reference(**kwargs)

    assert resolve() == semantic_identity
    assert resolve(explicit_ref=semantic_identity) == semantic_identity
    assert resolve(report_payload={"semantic_binding_ref": semantic_identity}) == semantic_identity

    # Typed inputs resolve the same semantic content identity through their CAS edge.
    assert resolve(runtime_quality_refs={}, current_artifact_refs={}) == semantic_identity

    # The semantic ledger may bind its own content identity before its CAS output exists.
    assert (
        resolve(
            report_payload=ledger_payload,
            runtime_quality_refs={},
            candidate=candidate,
            ref_key=ref_key,
            current_inputs=[],
            current_artifact_refs={},
        )
        == semantic_identity
    )

    with pytest.raises(
        NaturalLanguagePipelineRefusalError,
        match="runtime_quality_same_input_identity_not_established",
    ):
        resolve(
            report_payload={"semantic_binding_ref": semantic_identity},
            runtime_quality_refs={},
            candidate=None,
            ref_key="decision_artifact_quality_report_ref",
            current_inputs=[],
            current_artifact_refs={},
        )

    for invalid_sources in (
        {"explicit_ref": "sha256:" + "5" * 64},
        {"report_payload": {"semantic_binding_ref": "sha256:" + "5" * 64}},
    ):
        with pytest.raises(
            NaturalLanguagePipelineRefusalError,
            match="runtime_quality_same_input_identity_not_established",
        ):
            resolve(**invalid_sources)

    with pytest.raises(
        NaturalLanguagePipelineRefusalError,
        match="runtime_quality_same_input_identity_not_established",
    ):
        resolve(runtime_quality_refs={ref_key: selected_id}, current_artifact_refs={})

    wrong_profile_ref = selected_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "9" * 64}
    )
    with pytest.raises(
        NaturalLanguagePipelineRefusalError,
        match="runtime_quality_same_input_identity_not_established",
    ):
        resolve(current_artifact_refs={ref_key: wrong_profile_ref})

    with pytest.raises(
        NaturalLanguagePipelineRefusalError,
        match="runtime_quality_same_input_identity_not_established",
    ):
        resolve(candidate=candidate._replace(semantic_binding_ref="sha256:" + "5" * 64))

    tampered_ledger = {**ledger_payload, "semantic_binding_ref": "sha256:" + "5" * 64}
    with pytest.raises(
        NaturalLanguagePipelineRefusalError,
        match="runtime_quality_same_input_identity_not_established",
    ):
        resolve(
            report_payload=tampered_ledger,
            runtime_quality_refs={},
            candidate=None,
            ref_key=ref_key,
            current_inputs=[],
            current_artifact_refs={},
        )

    malformed_owner_marker = {**ledger_payload, "runtime_authority_payload": None}
    with pytest.raises(
        NaturalLanguagePipelineRefusalError,
        match="runtime_quality_same_input_identity_not_established",
    ):
        resolve(
            report_payload=malformed_owner_marker,
            runtime_quality_refs={},
            candidate=None,
            ref_key=ref_key,
            current_inputs=[],
            current_artifact_refs={},
        )

    with pytest.raises(
        NaturalLanguagePipelineRefusalError,
        match="runtime_quality_identity_reference_invalid",
    ):
        resolve(explicit_ref="not-an-artifact-reference")

    assert (
        resolve(
            report_payload={},
            runtime_quality_refs={},
            candidate=None,
            ref_key="decision_artifact_quality_report_ref",
            current_inputs=[],
            current_artifact_refs={},
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
    execution_fence = _prepare_running_scoped_control_job(
        service._control_store,
        job_id=job_id,
        run_id="R_nl_unknown_metric",
        effective_profile="research",
        context=_intent_context(
            desired_outcome="msme_survivl_rate", query_outcome="msme_survivl_rate"
        ),
    )

    try:
        with pytest.raises(RuntimeError) as exc_info, execution_fence:
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
        _run_nl_pipeline_with_live_admission(
            service,
            service._execute_nl_pipeline,
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
    from polisyos.runtime.quality.epoch_certificate_issuance import DecisionPacketEpochIssuanceOwner

    store = FileSystemCAS(tmp_path / "cas")
    issuance_owner = DecisionPacketEpochIssuanceOwner.for_store(store=store)
    service = ControlPlaneService(
        artifact_store=store,
        epoch_certificate_issuance_owner=issuance_owner,
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

    from polisyos.core.contracts.fabric import DataSnapshot
    from polisyos.runtime.http.services.control import nl_pipeline as nl_pipeline_module

    production_quality_writes: list[str] = []
    original_authority_writer = nl_pipeline_module.write_runtime_authority_artifact

    def _track_authority_write(
        store_arg: object,
        event_log: object,
        payload: object,
        opts: Any,
        **fields: Any,
    ):
        if opts.kind == "runtime.production_data_quality_report":
            production_quality_writes.append(opts.kind)
        return original_authority_writer(store_arg, event_log, payload, opts, **fields)

    monkeypatch.setattr(
        nl_pipeline_module,
        "write_runtime_authority_artifact",
        _track_authority_write,
    )

    def _run_contract_pipeline(run_id: str) -> dict[str, Any]:
        return _run_nl_pipeline_with_live_admission(
            service,
            service._execute_nl_pipeline_for_contract_testing,
            run_id=run_id,
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

    tampered_snapshots: list[str] = []
    baseline_quality_write_count = 0
    try:
        result = _run_contract_pipeline("R_nl_materialize")
        assert production_quality_writes
        positive_payload = captured["payload"]

        original_put_json = store.put_json
        tamper_snapshot = True

        def _put_json_with_wrong_nested_profile(
            obj: object,
            opts: Any,
            canon_spec: CanonSpec | None = None,
            *,
            return_selected_profile: bool = False,
        ):
            if tamper_snapshot and opts.kind == "fabric.data_snapshot":
                assert isinstance(obj, DataSnapshot)
                assert obj.quality_report_ref is not None
                tampered_snapshots.append(str(obj.quality_report_ref.artifact_id))
                invalid_ref = obj.quality_report_ref.model_copy(
                    update={
                        "manifest_profile_sha256": "sha256:" + "f" * 64,
                    }
                )
                obj = obj.model_copy(update={"quality_report_ref": invalid_ref})
            return original_put_json(
                obj,
                opts,
                canon_spec,
                return_selected_profile=return_selected_profile,
            )

        monkeypatch.setattr(store, "put_json", _put_json_with_wrong_nested_profile)
        baseline_quality_write_count = len(production_quality_writes)
        _run_contract_pipeline("R_nl_materialize_wrong_nested_profile")
    finally:
        service.close()

    assert tampered_snapshots
    assert len(production_quality_writes) == baseline_quality_write_count, {
        "baseline": baseline_quality_write_count,
        "after": len(production_quality_writes),
    }
    negative_payload = captured["payload"]
    negative_variant = negative_payload["params"]["llm_model_variants"][0]
    assert (
        "auto_materialization_failed:DataSnapshot selected nested reference profile differs from its parent: quality_report_ref"
        in (negative_variant["notes"])
    )
    assert any(
        step["action"] == "materialize_data_artifacts" and step["status"] == "warn"
        for step in negative_variant["steps"]
    )

    payload = positive_payload
    assert result["contract_testing_authority"] == {
        "authority_scope": "contract_testing",
        "production_promotable": False,
        "non_promotable_reason": "nl_mock_agents_contract_testing_only",
    }
    assert captured["kwargs"]["store"] is service._artifact_store
    assert captured["kwargs"]["epoch_certificate_issuance_owner"] is issuance_owner
    assert "epoch_certificate_issuance_owner" not in payload
    inputs = payload["inputs"]
    assert "data_snapshot_ref" in inputs
    assert "input_bindings_ref" in inputs
    assert "registry_bundle_ref" in inputs
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.contracts.fabric import RetrievalSummary

    snapshot_ref = ArtifactRef.model_validate(inputs["data_snapshot_ref"])
    assert snapshot_ref.manifest_profile_sha256 is not None
    snapshot = DataSnapshot.model_validate(
        from_canonical_bytes(store.get_bytes(snapshot_ref.artifact_id))
    )
    assert snapshot.quality_report_ref is not None
    assert snapshot.quality_report_ref.kind == RetrievalSummary.ARTIFACT_KIND
    assert snapshot.quality_report_ref.manifest_profile_sha256 is not None
    summary_payload = from_canonical_bytes(store.get_bytes(snapshot.quality_report_ref.artifact_id))
    summary = RetrievalSummary.model_validate(summary_payload)
    assert summary.assessment_status == "not_assessed"
    assert summary.source == "retrieval_service"
    assert summary.source_refs
    assert summary.source_refs[0].kind == "fabric.retrieval_payload"
    assert summary.source_refs[0].manifest_profile_sha256 is not None
    assert store.get_manifest(snapshot.quality_report_ref).kind == RetrievalSummary.ARTIFACT_KIND
    snapshot_manifest = store.get_manifest(snapshot_ref)
    assert any(
        item.role in {"quality_report", "quality_report_ref"}
        and item.artifact_id == snapshot.quality_report_ref.artifact_id
        and item.manifest_profile_sha256 == snapshot.quality_report_ref.manifest_profile_sha256
        for item in snapshot_manifest.inputs
    )


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
    from polisyos.scientist.orchestration.engine.budget import BudgetState
    from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware

    llm_ledger_path = tmp_path / "llm-cost-ledger.json"
    llm_store = BudgetMiddleware(
        BudgetState(),
        ledger=FileBudgetLedger(llm_ledger_path),
    )
    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        llm_producer_settlement_store=llm_store,
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
        _run_nl_pipeline_with_live_admission(
            service,
            service._execute_nl_pipeline,
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
    persisted_events = FileBudgetLedger(llm_ledger_path).snapshot().producer_settlements
    assert len(persisted_events) >= 2
    assert all(event.key == "nl-run:R_nl_simulated_llm" for event in persisted_events.values())
    assert all(event.status == "committed" for event in persisted_events.values())
    assert all(event.cost_origin == "reported" for event in persisted_events.values())
    assert all(event.amount == Decimal("0") for event in persisted_events.values())


@pytest.mark.parametrize(
    "change_as_of_on_retry", [False, True], ids=["stable-intent", "changed-as-of"]
)
def test_serious_nl_pipeline_persists_normative_applicability_report_ref(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    change_as_of_on_retry: bool,
) -> None:
    captured: dict[str, Any] = {}
    authority_write_attempts: list[dict[str, Any]] = []
    persisted_time_candidates: list[tuple[str, Any | None]] = []
    publication_time_selections: list[tuple[str | None, str | None, Any | None]] = []
    mutable_as_of = {"value": "2026-05-12"}

    class _MutableAsOf(str):
        def __new__(cls, state: dict[str, str]) -> _MutableAsOf:
            instance = super().__new__(cls, state["value"])
            instance._state = state
            return instance

        def __str__(self) -> str:
            return self._state["value"]

        def strip(self, chars: str | None = None) -> str:
            return self._state["value"].strip(chars)

        def __deepcopy__(self, memo: dict[int, Any]) -> _MutableAsOf:
            return self

    from polisyos.runtime.http.services.control.nl_pipeline import (
        _persisted_runtime_quality_publication_times as original_persisted_times,
    )
    from polisyos.runtime.http.services.control.nl_pipeline import (
        _runtime_quality_publication_times as original_publication_times,
    )
    from polisyos.runtime.http.services.control.nl_pipeline import (
        write_runtime_authority_artifact as original_authority_writer,
    )

    def _capture_persisted_times(
        store: Any,
        *,
        output_artifact_id: str,
        artifact_kind: str,
        expected_inputs: list[InputRef],
    ) -> Any | None:
        result = original_persisted_times(
            store,
            output_artifact_id=output_artifact_id,
            artifact_kind=artifact_kind,
            expected_inputs=expected_inputs,
        )
        if artifact_kind == "runtime.production_data_quality_report":
            persisted_time_candidates.append((artifact_kind, result))
        return result

    def _capture_publication_times(
        published_times: Mapping[str, tuple[str, str]],
        *,
        identity_key: str,
        requested_as_of_time: str | None,
        persisted_times: _RuntimeQualityPublicationCandidate | None,
        now: datetime,
    ) -> tuple[str, str]:
        persisted_kind = next(
            (
                kind
                for kind, candidate in reversed(persisted_time_candidates)
                if candidate is persisted_times
            ),
            None,
        )
        publication_time_selections.append((persisted_kind, requested_as_of_time, persisted_times))
        return original_publication_times(
            published_times,
            identity_key=identity_key,
            requested_as_of_time=requested_as_of_time,
            persisted_times=persisted_times,
            now=now,
        )

    def _capture_authority_write(
        store: Any,
        event_log: Any,
        payload: Any,
        opts: Any,
        **authority_fields: Any,
    ) -> Any:
        attempt = {
            "kind": opts.kind,
            "attempt_observed_at": datetime.now(UTC).isoformat(),
            "output_id": "sha256:"
            + hashlib.sha256(
                to_canonical_bytes(payload, CanonSpec(forbid_floats=False))
            ).hexdigest(),
            "input_refs": [
                {
                    "artifact_id": str(item.artifact_id),
                    "role": item.role,
                    "manifest_profile_sha256": item.manifest_profile_sha256,
                }
                for item in opts.inputs
            ],
            "payload": payload if opts.kind == "runtime.production_data_quality_report" else None,
            "opts": opts if opts.kind == "runtime.production_data_quality_report" else None,
            "authority_fields": (
                dict(authority_fields)
                if opts.kind == "runtime.production_data_quality_report"
                else None
            ),
            "generated_at_argument": authority_fields.get("generated_at"),
            "as_of_time_argument": authority_fields.get("as_of_time"),
        }
        authority_write_attempts.append(attempt)
        result = original_authority_writer(
            store,
            event_log,
            payload,
            opts,
            **authority_fields,
        )
        attempt["output_id"] = str(result.cas_ref.artifact_id)
        attempt["publication_generated_at"] = result.identity_context.generated_at
        attempt["publication_as_of_time"] = result.identity_context.as_of_time
        if opts.kind == "runtime.production_data_quality_report":
            attempt["writer_result"] = result
        if (
            change_as_of_on_retry
            and opts.kind == "runtime.production_data_quality_report"
            and sum(
                1
                for item in authority_write_attempts
                if item["kind"] == "runtime.production_data_quality_report"
            )
            == 1
        ):
            mutable_as_of["value"] = "2026-05-13"
        return result

    monkeypatch.setattr(
        "polisyos.runtime.http.services.control.nl_pipeline.write_runtime_authority_artifact",
        _capture_authority_write,
    )
    monkeypatch.setattr(
        "polisyos.runtime.http.services.control.nl_pipeline._persisted_runtime_quality_publication_times",
        _capture_persisted_times,
    )
    monkeypatch.setattr(
        "polisyos.runtime.http.services.control.nl_pipeline._runtime_quality_publication_times",
        _capture_publication_times,
    )

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
    persisted_report: dict[str, Any] = {}
    persisted_quality_envelope: Any | None = None
    production_quality_input_ids: set[str] = set()
    normative_context = _normative_context()
    if change_as_of_on_retry:
        normative_context["as_of"] = _MutableAsOf(mutable_as_of)
    execution_fence = _prepare_running_scoped_control_job(
        service._control_store,
        job_id=job_id,
        run_id="R_nl_normative",
        effective_profile="research",
        context=normative_context,
    )
    pipeline_error: Exception | None = None
    try:
        try:
            with execution_fence:
                service._execute_nl_pipeline(
                    run_id="R_nl_normative",
                    nl_request="Evaluate Ukraine MSME wartime support with legal constraints.",
                    context=normative_context,
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
        except Exception as exc:
            if not change_as_of_on_retry:
                raise
            pipeline_error = exc

        if not change_as_of_on_retry:
            record = service._control_store.get_job(job_id)
            payload = captured["payload"]
            report_ref = payload["params"]["normative_applicability_report_ref"]
            persisted_report = from_canonical_bytes(
                service._artifact_store.get_bytes(ArtifactID(report_ref))
            )
            from polisyos.core.artifacts.canonical_profile import read_core_manifest_profile
            from polisyos.core.artifacts.manifest import ArtifactRef
            from polisyos.core.contracts.fabric import DataSnapshot

            production_quality_ref = ArtifactRef.model_validate(
                payload["params"]["runtime_quality_evidence"]["production_data_quality"][
                    "runtime_quality_artifact_refs"
                ]["production_data_quality_report_ref"]
            )
            selected_snapshot_ref = ArtifactRef.model_validate(
                payload["inputs"]["data_snapshot_ref"]
            )
            selected_snapshot_manifest, _ = read_core_manifest_profile(
                service._artifact_store,
                selected_snapshot_ref,
            )
            selected_snapshot = DataSnapshot.model_validate(
                from_canonical_bytes(
                    service._artifact_store.get_bytes(selected_snapshot_ref.artifact_id)
                )
            )
            production_quality_manifest, _ = read_core_manifest_profile(
                service._artifact_store,
                production_quality_ref,
            )
            assert production_quality_manifest.authority is not None
            from polisyos.runtime.quality.authority import EvidenceAuthorityEnvelope

            persisted_quality_envelope = EvidenceAuthorityEnvelope.model_validate(
                from_canonical_bytes(
                    service._artifact_store.get_bytes(
                        ArtifactID(production_quality_manifest.authority.authority_envelope_ref)
                    )
                )
            )
            normative_manifest = service._artifact_store.get_manifest(ArtifactID(report_ref))
            production_quality_input_ids = {
                str(item.artifact_id) for item in production_quality_manifest.inputs
            }

            quality_attempt = next(
                item
                for item in reversed(authority_write_attempts)
                if item["kind"] == "runtime.production_data_quality_report"
                and item.get("writer_result") is not None
            )
            quality_payload = quality_attempt["payload"]
            quality_opts = quality_attempt["opts"]
            quality_fields = quality_attempt["authority_fields"]
            exact_replay = original_authority_writer(
                service._artifact_store,
                service._diagnostic_event_log,
                quality_payload,
                quality_opts,
                **quality_fields,
            )
            assert exact_replay.cas_ref == quality_attempt["writer_result"].cas_ref

            foreign_job_fields = dict(quality_fields)
            foreign_job_fields["job_id"] = "job_foreign_context"
            closure = dict(foreign_job_fields["same_input_closure"])
            closure["job_id"] = "job_foreign_context"
            foreign_job_fields["same_input_closure"] = closure
            with pytest.raises(ValueError, match="authority identity mismatch"):
                original_authority_writer(
                    service._artifact_store,
                    service._diagnostic_event_log,
                    quality_payload,
                    quality_opts,
                    **foreign_job_fields,
                )

            changed_profile_fields = dict(quality_fields)
            changed_profile_fields["effective_execution_profile"] = "production"
            changed_profile_fields["effective_mode_ref"] = "runtime-mode:production"
            changed_profile_closure = dict(quality_fields["same_input_closure"])
            changed_profile_closure["effective_mode_ref"] = "runtime-mode:production"
            changed_profile_fields["same_input_closure"] = changed_profile_closure
            with pytest.raises(ValueError, match="authority identity mismatch"):
                original_authority_writer(
                    service._artifact_store,
                    service._diagnostic_event_log,
                    quality_payload,
                    quality_opts,
                    **changed_profile_fields,
                )

            assert quality_opts.inputs
            input_variants = (
                quality_opts.inputs[0].model_copy(
                    update={"role": quality_opts.inputs[0].role + ".rebound"}
                ),
                quality_opts.inputs[0].model_copy(
                    update={"manifest_profile_sha256": "sha256:" + "d" * 64}
                ),
            )
            for changed_input in input_variants:
                changed_opts = replace(
                    quality_opts,
                    inputs=[changed_input, *quality_opts.inputs[1:]],
                )
                with pytest.raises(ValueError, match="authority identity mismatch"):
                    original_authority_writer(
                        service._artifact_store,
                        service._diagnostic_event_log,
                        quality_payload,
                        changed_opts,
                        **quality_fields,
                    )

            envelope_id = str(quality_attempt["writer_result"].authority_envelope_ref.artifact_id)
            original_get_bytes = service._artifact_store.get_bytes

            def _forged_persisted_envelope(ref: object) -> bytes:
                payload_bytes = original_get_bytes(ref)
                ref_value = getattr(ref, "artifact_id", ref)
                if str(ref_value) != envelope_id:
                    return payload_bytes
                forged = from_canonical_bytes(payload_bytes)
                forged_closure = dict(forged["same_input_closure"])
                forged_closure["policy_intent_ref"] = "sha256:" + "e" * 64
                forged["same_input_closure"] = forged_closure
                return to_canonical_bytes(forged, CanonSpec(forbid_floats=False))

            monkeypatch.setattr(service._artifact_store, "get_bytes", _forged_persisted_envelope)
            with pytest.raises(ValueError, match="authority identity mismatch"):
                original_authority_writer(
                    service._artifact_store,
                    service._diagnostic_event_log,
                    quality_payload,
                    quality_opts,
                    **quality_fields,
                )
            monkeypatch.setattr(service._artifact_store, "get_bytes", original_get_bytes)
    finally:
        service.close()

    if change_as_of_on_retry:
        production_quality_attempts = [
            attempt
            for attempt in authority_write_attempts
            if attempt["kind"] == "runtime.production_data_quality_report"
        ]
        assert pipeline_error is not None, [
            (
                item.get("as_of_time_argument"),
                item.get("output_id"),
                item.get("generated_at_argument"),
                item.get("publication_generated_at"),
            )
            for item in production_quality_attempts
        ]
        assert isinstance(pipeline_error, ValueError)
        assert str(pipeline_error) == "existing authority identity mismatch"
        assert len(production_quality_attempts) >= 2, repr(pipeline_error)
        first_quality_attempt, changed_as_of_attempt = production_quality_attempts[:2]
        assert first_quality_attempt["input_refs"] == changed_as_of_attempt["input_refs"]
        assert first_quality_attempt["output_id"] == changed_as_of_attempt["output_id"]
        assert first_quality_attempt["as_of_time_argument"] == "2026-05-12"
        assert changed_as_of_attempt["as_of_time_argument"] == "2026-05-13"
        assert first_quality_attempt["publication_as_of_time"] == "2026-05-12"
        assert persisted_time_candidates[0] == ("runtime.production_data_quality_report", None)
        quality_candidates = [
            candidate
            for kind, candidate in persisted_time_candidates
            if kind == "runtime.production_data_quality_report" and candidate is not None
        ]
        assert any(
            kind == "runtime.production_data_quality_report"
            and requested == "2026-05-13"
            and any(candidate is quality_candidate for quality_candidate in quality_candidates)
            and candidate.as_of_time == "2026-05-12"
            for kind, requested, candidate in publication_time_selections
        )
        assert "publication_generated_at" not in changed_as_of_attempt
        assert "publication_as_of_time" not in changed_as_of_attempt
        assert (
            changed_as_of_attempt["attempt_observed_at"]
            != (first_quality_attempt["attempt_observed_at"])
        )
        return

    payload = captured["payload"]
    params = payload["params"]
    report_ref = params["normative_applicability_report_ref"]
    production_quality_ref = ArtifactRef.model_validate(
        params["runtime_quality_evidence"]["production_data_quality"][
            "runtime_quality_artifact_refs"
        ]["production_data_quality_report_ref"]
    )

    assert report_ref.startswith("sha256:")
    assert params["runtime_quality_refs"]["normative_applicability_report_ref"] == report_ref
    normative_evidence = params["runtime_quality_evidence"]["normative_evidence"]
    assert normative_evidence["status"] == "fail"
    assert normative_evidence["candidate_norm_refs"] == ["norm.ua.credit_eligibility"]
    assert normative_evidence["applied_norms"] == []
    assert "legal_source_relation_verification_not_established" in normative_evidence["issue_codes"]
    assert payload["reports_index"]["normative_applicability_report_ref"]["artifact_id"] == (
        report_ref
    )
    assert persisted_report["status"] == "fail"
    assert persisted_report["candidate_norm_refs"] == ["norm.ua.credit_eligibility"]
    assert persisted_report["applied_norms"] == []
    assert "legal_source_relation_verification_not_established" in persisted_report["issue_codes"]
    normative_edges = list(normative_manifest.inputs)
    assert normative_edges
    assert all(edge.manifest_profile_sha256 is not None for edge in normative_edges)
    from polisyos.core.contracts import (
        data_snapshot_reference_fields,
        data_snapshot_reference_input_roles,
    )

    for field_name in data_snapshot_reference_fields():
        nested_ref = getattr(selected_snapshot, field_name)
        if nested_ref is None:
            continue
        parent_edges = [
            edge
            for edge in selected_snapshot_manifest.inputs
            if edge.role in data_snapshot_reference_input_roles(field_name)
            and edge.artifact_id == nested_ref.artifact_id
        ]
        assert len(parent_edges) == 1
        assert parent_edges[0].manifest_profile_sha256 == nested_ref.manifest_profile_sha256
        report_edges = [
            edge
            for edge in normative_edges
            if edge.role == field_name and edge.artifact_id == nested_ref.artifact_id
        ]
        assert len(report_edges) == 1
        assert report_edges[0].manifest_profile_sha256 == nested_ref.manifest_profile_sha256
    assert str(production_quality_ref.artifact_id) not in production_quality_input_ids
    assert str(selected_snapshot_ref.artifact_id) in production_quality_input_ids
    production_quality_attempts = [
        attempt
        for attempt in authority_write_attempts
        if attempt["kind"] == "runtime.production_data_quality_report"
    ]
    assert len(production_quality_attempts) >= 2
    first_quality_attempt = production_quality_attempts[0]
    assert persisted_quality_envelope is not None
    assert persisted_quality_envelope.artifact_ref == str(production_quality_ref.artifact_id)
    assert persisted_quality_envelope.cas_ref == str(production_quality_ref.artifact_id)
    assert persisted_quality_envelope.artifact_kind == production_quality_ref.kind
    assert (
        persisted_quality_envelope.generated_at == first_quality_attempt["publication_generated_at"]
    )
    assert persisted_quality_envelope.as_of_time == first_quality_attempt["publication_as_of_time"]
    persisted_candidate = next(
        candidate
        for _artifact_kind, candidate in persisted_time_candidates
        if candidate is not None
        and candidate.generated_at == persisted_quality_envelope.generated_at
        and candidate.as_of_time == persisted_quality_envelope.as_of_time
    )
    assert (
        persisted_candidate.policy_intent_ref
        == persisted_quality_envelope.same_input_closure.policy_intent_ref
    )
    assert (
        persisted_candidate.production_data_manifest_ref
        == persisted_quality_envelope.same_input_closure.production_data_manifest_ref
    )
    assert (
        persisted_candidate.legal_snapshot_ref
        == persisted_quality_envelope.same_input_closure.legal_snapshot_ref
    )
    assert (
        persisted_candidate.semantic_binding_ref == persisted_quality_envelope.semantic_binding_ref
    )
    assert any(
        candidate is not None
        and candidate.generated_at == first_quality_attempt["publication_generated_at"]
        and candidate.as_of_time == first_quality_attempt["publication_as_of_time"]
        for _artifact_kind, candidate in persisted_time_candidates
    )
    for retry_attempt in production_quality_attempts[1:]:
        assert retry_attempt["input_refs"] == first_quality_attempt["input_refs"]
        assert retry_attempt["output_id"] == first_quality_attempt["output_id"]
        assert (
            retry_attempt["publication_generated_at"]
            == (first_quality_attempt["publication_generated_at"])
        )
        assert (
            retry_attempt["publication_as_of_time"]
            == (first_quality_attempt["publication_as_of_time"])
        )
        assert retry_attempt["attempt_observed_at"] != first_quality_attempt["attempt_observed_at"]
    assert all(
        item["artifact_id"] != attempt["output_id"]
        for attempt in production_quality_attempts
        for item in attempt["input_refs"]
    )
    assert record is not None
    assert record.progress["details"]["normative_applicability_report_ref"] == report_ref
    persisted_progress_evidence = record.progress["details"]["runtime_quality_evidence"][
        "normative_evidence"
    ]
    assert persisted_progress_evidence["status"] == "fail"
    assert persisted_progress_evidence["applied_norms"] == []
    assert (
        "legal_source_relation_verification_not_established"
        in persisted_progress_evidence["issue_codes"]
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
    execution_fence = _prepare_running_scoped_control_job(
        service._control_store,
        job_id=job_id,
        run_id="R_nl_active_corpus_conflict",
        effective_profile="research",
        context=context,
    )

    try:
        with execution_fence:
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
    execution_fence = _prepare_running_scoped_control_job(
        service._control_store,
        job_id=job_id,
        run_id=run_id,
        effective_profile=execution_profile,
        context=context,
    )

    try:
        with execution_fence:
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

        fresh_store = FileSystemCAS(tmp_path / "cas")
        for report_key, ref_key in _PHASE_24_REQUIRED_RUNTIME_REFS.items():
            ref = result[ref_key]
            assert ref.startswith("sha256:")
            assert params["runtime_quality_refs"][ref_key] == ref
            assert details["runtime_quality_refs"][ref_key] == ref

            evidence = params["runtime_quality_evidence"][report_key]
            progress_evidence = details["runtime_quality_evidence"][report_key]
            assert evidence[ref_key] == ref
            assert progress_evidence[ref_key] == ref
            assert evidence["authority_envelope_ref"].startswith("sha256:")
            assert evidence["runtime_event_ref"].startswith("sha256:")

            selected_report_ref = ArtifactRef.model_validate(
                evidence["runtime_quality_artifact_refs"][ref_key]
            )
            assert str(selected_report_ref.artifact_id) == ref
            assert selected_report_ref.manifest_profile_sha256 is not None
            report_manifest = fresh_store.get_manifest(selected_report_ref)
            assert (
                artifact_manifest_profile_sha256(report_manifest)
                == selected_report_ref.manifest_profile_sha256
            )
            report = from_canonical_bytes(fresh_store.get_bytes(selected_report_ref))

            assert report_manifest.authority is not None
            authority_links = report_manifest.authority
            assert authority_links.authority_envelope_ref == evidence["authority_envelope_ref"]
            assert authority_links.diagnostic_event_ref == evidence["runtime_event_ref"]
            assert authority_links.authority_envelope_manifest_profile_sha256 is not None
            assert authority_links.diagnostic_event_manifest_profile_sha256 is not None
            assert (
                authority_links.diagnostic_event_manifest_profile_sha256
                == evidence["runtime_event_manifest_profile_sha256"]
            )
            envelope_ref = ArtifactRef(
                artifact_id=ArtifactID(authority_links.authority_envelope_ref),
                kind=AUTHORITY_ENVELOPE_ARTIFACT_KIND,
                media_type="application/json",
                manifest_profile_sha256=(
                    authority_links.authority_envelope_manifest_profile_sha256
                ),
            )
            event_ref = ArtifactRef(
                artifact_id=ArtifactID(authority_links.diagnostic_event_ref),
                kind=DIAGNOSTIC_EVENT_ARTIFACT_KIND,
                media_type="application/json",
                manifest_profile_sha256=(authority_links.diagnostic_event_manifest_profile_sha256),
            )
            envelope_manifest = fresh_store.get_manifest(envelope_ref)
            event_manifest = fresh_store.get_manifest(event_ref)
            assert (
                artifact_manifest_profile_sha256(envelope_manifest)
                == envelope_ref.manifest_profile_sha256
            )
            assert (
                artifact_manifest_profile_sha256(event_manifest)
                == event_ref.manifest_profile_sha256
            )
            assert envelope_manifest.inputs == report_manifest.inputs
            assert event_manifest.inputs == report_manifest.inputs
            for input_ref in report_manifest.inputs:
                if input_ref.manifest_profile_sha256 is not None:
                    input_manifest = fresh_store.get_manifest_by_profile(
                        input_ref.artifact_id,
                        input_ref.manifest_profile_sha256,
                    )
                    assert (
                        artifact_manifest_profile_sha256(input_manifest)
                        == input_ref.manifest_profile_sha256
                    )

            envelope = from_canonical_bytes(fresh_store.get_bytes(envelope_ref))
            event_payload = from_canonical_bytes(fresh_store.get_bytes(event_ref))
            if report_key == "production_data_quality":
                production_payload_edges = [
                    item
                    for item in report_manifest.inputs
                    if item.role == "production_data_payload"
                ]
                assert len(production_payload_edges) == 1
                production_payload_edge = production_payload_edges[0]
                snapshot_ref = ArtifactRef.model_validate(
                    captured["payload"]["inputs"]["data_snapshot_ref"]
                )
                snapshot_manifest = fresh_store.get_manifest(snapshot_ref)
                parent_edges = [
                    item
                    for item in snapshot_manifest.inputs
                    if item.role == "production_data_payload"
                    and item.artifact_id == production_payload_edge.artifact_id
                ]
                assert len(parent_edges) == 1
                assert (
                    parent_edges[0].manifest_profile_sha256
                    == production_payload_edge.manifest_profile_sha256
                )
                payload_ref = ArtifactRef(
                    artifact_id=production_payload_edge.artifact_id,
                    kind="fabric.production_data_payload",
                    media_type="application/json",
                    manifest_profile_sha256=(production_payload_edge.manifest_profile_sha256),
                )
                payload_manifest = fresh_store.get_manifest_by_profile(
                    payload_ref.artifact_id,
                    payload_ref.manifest_profile_sha256,
                )
                assert payload_manifest.kind == "fabric.production_data_payload"
                assert payload_manifest.artifact_schema is not None
                assert payload_manifest.artifact_schema.name == (
                    "polisyos.fabric.ProductionDataPayload"
                )
                assert payload_manifest.artifact_schema.version == "1.0"
                payload_source = read_core_json_artifact(fresh_store, payload_ref).value
                production_context = payload_source["production_data_evidence_context"]
                manifest_sha256 = production_context["manifest_sha256"]
                assert isinstance(manifest_sha256, str)
                assert len(manifest_sha256) == 71 and manifest_sha256.startswith("sha256:")
                assert all(character in "0123456789abcdef" for character in manifest_sha256[7:])
                assert envelope["same_input_closure"]["production_data_manifest_ref"] == str(
                    production_payload_edge.artifact_id
                )
                assert envelope["same_input_closure"]["production_data_manifest_ref"] != ref
                assert envelope["same_input_closure"]["legal_snapshot_ref"] is None
            input_ids = [str(item.artifact_id) for item in report_manifest.inputs]
            assert envelope["input_refs"] == input_ids
            assert event_payload["input_refs"] == input_ids
            assert report_manifest.same_input_closure is not None
            assert envelope["same_input_closure"]["closure_sha256"] == (
                report_manifest.same_input_closure.closure_sha256
            )
            assert envelope["same_input_closure"]["evidence_input_refs"] == input_ids
            assert event_manifest.same_input_closure == report_manifest.same_input_closure
            assert envelope_manifest.same_input_closure == report_manifest.same_input_closure
            assert envelope["authority_role"] == "producer_authority"
            assert envelope["provenance_kind"] == "runtime_emitted"
            assert envelope["artifact_kind"] == report_manifest.kind
            assert envelope["governance"]["classification"] == "runtime_quality_evidence"
            assert envelope["governance"]["authority_boundary"] == "runtime_control_plane"
            assert envelope["artifact_ref"] == ref
            assert envelope["cas_ref"] == ref
            assert envelope["run_id"] == run_id
            assert envelope["job_id"] == job_id
            assert authority_links.payload_sha256 == report_manifest.integrity.sha256
            normalized_status = str(report.get("status") or "").strip().casefold()
            expected_validation_status = (
                "pass"
                if normalized_status in {"pass", "passed", "ok", "match", "complete"}
                else "blocked"
                if normalized_status in {"blocked", "block"}
                else "not_applicable"
                if normalized_status in {"not_applicable", "n/a", "na", "skipped"}
                else "fail"
            )
            assert envelope["validation_status"] == expected_validation_status
            assert envelope["blocking_status"] == (
                "non_blocking" if expected_validation_status == "pass" else "blocking"
            )
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
            closure_identities.add(tuple(closure.get(field) for field in closure_identity_fields))
        assert len(closure_identities) == 1
    finally:
        service.close()


@pytest.mark.parametrize(
    ("source_fault", "expected_error"),
    [
        (
            "selected_child_kind_conflicts_with_parent_role",
            "auto_materialization_production_data_payload_kind_mismatch",
        ),
        (
            "present_malformed_manifest_digest",
            "auto_materialization_production_manifest_digest_not_established",
        ),
    ],
    ids=[
        "wrong-selected-child-kind-under-production-payload-role",
        "present-malformed-production-manifest-digest",
    ],
)
def test_phase_24_materialization_rejects_unverified_production_payload_basis(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    source_fault: str,
    expected_error: str,
) -> None:
    from polisyos.runtime.http.services.control import nl_pipeline as nl_pipeline_module

    selected_refs: dict[str, ArtifactRef] = {}

    def _capture_state(payload: dict[str, Any], **_: Any) -> dict[str, Any]:
        return {"run_id": payload["run_id"], "reports_index": {}}

    if source_fault == "present_malformed_manifest_digest":
        original_evidence_context = nl_pipeline_module._production_data_evidence_context

        def _evidence_context_with_malformed_digest(*args: Any, **kwargs: Any) -> Any:
            evidence_context = original_evidence_context(*args, **kwargs)
            if evidence_context is None:
                return None
            return {**evidence_context, "manifest_sha256": "sha256:" + "g" * 64}

        monkeypatch.setattr(
            nl_pipeline_module,
            "_production_data_evidence_context",
            _evidence_context_with_malformed_digest,
        )

    original_put_json = FileSystemCAS.put_json

    def _put_json_with_source_fault(
        store: FileSystemCAS,
        obj: object,
        opts: ArtifactWriteOptions,
        canon_spec: CanonSpec | None = None,
        *,
        return_selected_profile: bool = False,
    ) -> Any:
        selected_options = opts
        if (
            source_fault == "selected_child_kind_conflicts_with_parent_role"
            and opts.kind == "fabric.production_data_payload"
        ):
            selected_options = replace(
                opts,
                kind="fabric.retrieval_summary",
                schema=SchemaInfo(name="polisyos.fabric.RetrievalSummary", version="1.0"),
            )
        selected_ref = original_put_json(
            store,
            obj,
            selected_options,
            canon_spec=canon_spec,
            return_selected_profile=return_selected_profile,
        )
        if opts.kind == "fabric.production_data_payload":
            selected_refs["production_payload"] = selected_ref
        elif opts.kind == "fabric.data_snapshot":
            selected_refs["data_snapshot"] = selected_ref
        return selected_ref

    monkeypatch.setattr(FileSystemCAS, "put_json", _put_json_with_source_fault)
    production_data_root = _write_phase_24_production_data_root(tmp_path)
    context = {
        **_normative_context(),
        "production_data_root": str(production_data_root),
        "query_outcome": "msme_survival_rate",
        "query_treatment": "wartime_credit_support",
        "requirements": ["use_production_data_materialization"],
        "tenant_id": "tenant-phase-24-source-negative",
        "cell_id": "cell-phase-24-source-negative",
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
            default_profile="research",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control-phase-24-source-negative.sqlite3"),
            postgres_dsn=None,
        ),
        registry_providers=_registry_providers(),
    )
    run_id = f"R_nl_phase_24_source_negative_{source_fault}"
    try:
        with pytest.raises(RuntimeError, match=expected_error):
            _run_nl_pipeline_with_live_admission(
                service,
                service._execute_nl_pipeline,
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
                provider_preflight_payload={"status": "skipped", "reason": "simulation_mode"},
            )
    finally:
        service.close()

    payload_ref = selected_refs["production_payload"]
    snapshot_ref = selected_refs["data_snapshot"]
    assert payload_ref.manifest_profile_sha256 is not None
    assert snapshot_ref.manifest_profile_sha256 is not None
    fresh_store = FileSystemCAS(tmp_path / "cas")
    payload_manifest = fresh_store.get_manifest(payload_ref)
    snapshot_manifest = fresh_store.get_manifest(snapshot_ref)
    assert snapshot_manifest.kind == "fabric.data_snapshot"
    assert snapshot_manifest.artifact_schema is not None
    assert snapshot_manifest.artifact_schema.name == "polisyos.core.DataSnapshot"
    assert snapshot_manifest.artifact_schema.version == "0.2.0"
    assert fresh_store.verify(payload_ref).ok
    assert fresh_store.verify(snapshot_ref).ok
    assert artifact_manifest_profile_sha256(payload_manifest) == (
        payload_ref.manifest_profile_sha256
    )
    assert artifact_manifest_profile_sha256(snapshot_manifest) == (
        snapshot_ref.manifest_profile_sha256
    )
    parent_edges = [
        item
        for item in snapshot_manifest.inputs
        if item.role == "production_data_payload" and item.artifact_id == payload_ref.artifact_id
    ]
    assert len(parent_edges) == 1
    assert parent_edges[0].manifest_profile_sha256 == payload_ref.manifest_profile_sha256
    snapshot_payload = read_core_json_artifact(fresh_store, snapshot_ref).value
    assert ArtifactRef.model_validate(snapshot_payload["data_ref"]) == payload_ref

    payload = read_core_json_artifact(fresh_store, payload_ref).value
    evidence_context = payload["production_data_evidence_context"]
    if source_fault == "selected_child_kind_conflicts_with_parent_role":
        assert payload_manifest.kind == "fabric.retrieval_summary"
        assert payload_manifest.artifact_schema is not None
        assert payload_manifest.artifact_schema.name == "polisyos.fabric.RetrievalSummary"
        assert payload_manifest.artifact_schema.version == "1.0"
        assert evidence_context["manifest_sha256"].startswith("sha256:")
    else:
        assert payload_manifest.kind == "fabric.production_data_payload"
        assert payload_manifest.artifact_schema is not None
        assert payload_manifest.artifact_schema.name == "polisyos.fabric.ProductionDataPayload"
        assert payload_manifest.artifact_schema.version == "1.0"
        assert evidence_context["manifest_sha256"] == "sha256:" + "g" * 64
        assert evidence_context["manifest_sha256"]


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
        result = _run_nl_pipeline_with_live_admission(
            service,
            service._execute_nl_pipeline,
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
    assert (
        policy_design_case_payload["capability_ledger"]["ledger_ref"]
        == (capability_ledger_payload["ledger_ref"])
    )
    assert policy_design_case_payload["nodes"][0]["node_type"] == "concept_spine"
    assert policy_design_case_payload["jurisdiction_spine"]["jurisdiction_spine_ref"] == (
        jurisdiction_spine_ref
    )
    assert runtime_evidence["policy_intent_envelope"]["runtime_event_ref"].startswith("sha256:")
    assert runtime_evidence["policy_design_capability_ledger"]["runtime_event_ref"].startswith(
        "sha256:"
    )
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
            _run_nl_pipeline_with_live_admission(
                service,
                service._execute_nl_pipeline,
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


@pytest.mark.usefixtures("canary_diagnostic_output_root")
def test_canary_evidence_keeps_unverified_runtime_norms_candidate_only(
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
    assert persisted["status"] == "fail"
    assert persisted["candidate_norm_refs"] == ["norm.ua.credit_eligibility"]
    assert persisted["applied_norms"] == []
    assert "legal_source_relation_verification_not_established" in persisted["issue_codes"]


def test_production_data_canary_materializes_local_lane_without_external_fetch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from copy import deepcopy

    from polisyos.runtime.quality.scorecard import build_quality_scorecard

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
            },
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
                    "scenario:ukraine_msme_wartime_credit_support:data:production_msme_panel"
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
    execution_fence = _prepare_running_scoped_control_job(
        service._control_store,
        job_id=job_id,
        run_id="R_nl_production_data_lane",
        effective_profile="research",
        context=_intent_context(
            production_data_root=str(production_data_root),
            query_outcome="msme_survival_rate",
            query_treatment="wartime_credit_support",
            requirements=["use_production_data_materialization"],
            scenario_evidence_contract=scenario_evidence_contract,
            scenario_evidence_contract_id=scenario_evidence_contract["contract_id"],
        ),
    )

    try:
        with execution_fence:
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
        fresh_response = service.get_job_status(
            job_id,
            request_id="scorecard-owner-witness",
        )
        fresh_job_payload = fresh_response.model_dump(mode="json")
        assert fresh_job_payload["execution_status"] == "completed"
        fresh_details = fresh_job_payload["progress"]["details"]
        fresh_runtime_quality_refs = fresh_details["runtime_quality_refs"]
        fresh_quality_evidence = fresh_details["runtime_quality_evidence"]
        fabric_report = fresh_quality_evidence["fabric_retrieval_trace"]
        selected_fabric_ref = ArtifactRef.model_validate(
            fresh_job_payload["runtime_quality_artifact_refs"]["fabric_retrieval_trace_ref"]
        )
        assert selected_fabric_ref.kind == "fabric.retrieval_trace"
        assert selected_fabric_ref.media_type == "application/json"
        assert selected_fabric_ref.manifest_profile_sha256 is not None
        assert (
            str(selected_fabric_ref.artifact_id)
            == fresh_runtime_quality_refs["fabric_retrieval_trace_ref"]
        )
        assert fabric_report["runtime_quality_artifact_refs"]["fabric_retrieval_trace_ref"] == (
            selected_fabric_ref.model_dump(mode="json")
        )
        publication = fabric_report["runtime_quality_publication_basis"]["publication"]
        assert publication["artifact_ref"] == selected_fabric_ref.model_dump(mode="json")
        assert publication["runtime_event_ref"] == fabric_report["runtime_event_ref"]
        assert publication["authority_envelope_ref"] == fabric_report["authority_envelope_ref"]
        assert publication["authority_envelope"] == fabric_report["authority_envelope"]
        assert publication["manifest_ref"] == fabric_report["manifest_ref"]
        assert publication["payload_sha256"] == fabric_report["payload_sha256"]

        fresh_store = FileSystemCAS(tmp_path / "cas")
        assert fresh_store.verify(selected_fabric_ref).ok
        selected_manifest = fresh_store.get_manifest(selected_fabric_ref)
        assert (
            artifact_manifest_profile_sha256(selected_manifest)
            == selected_fabric_ref.manifest_profile_sha256
        )
        assert selected_manifest.authority is not None
        assert (
            selected_manifest.authority.authority_envelope_ref
            == fabric_report["authority_envelope_ref"]
        )
        assert (
            selected_manifest.authority.diagnostic_event_ref == fabric_report["runtime_event_ref"]
        )
        assert selected_manifest.authority.authority_envelope_manifest_profile_sha256
        assert (
            selected_manifest.authority.diagnostic_event_manifest_profile_sha256
            == fabric_report["runtime_event_manifest_profile_sha256"]
        )

        def _build_fresh_scorecard(
            evidence: dict[str, Any],
        ) -> dict[str, Any]:
            return build_quality_scorecard(
                canary_kind="research",
                job_id=job_id,
                run_id=fresh_job_payload["run_id"],
                execution_status=fresh_job_payload["execution_status"],
                job_payload=fresh_job_payload,
                run_payload=None,
                provider_preflight={"status": "skipped", "reason": "simulation_mode"},
                quality_evidence=evidence,
                artifact_store=fresh_store,
            )

        fabric_gate_ref = "quality_evidence/fabric_retrieval_trace.json"

        def _fabric_gate_codes(scorecard: dict[str, Any]) -> set[str]:
            return {
                str(gate["code"])
                for gate in scorecard["quality_gates"]
                if gate.get("evidence_ref") == fabric_gate_ref
            }

        positive_scorecard = _build_fresh_scorecard(fresh_quality_evidence)
        positive_fabric_gate_codes = _fabric_gate_codes(positive_scorecard)
        assert "hds_borrowed_authority_envelope" not in positive_fabric_gate_codes
        assert (
            "runtime_quality_report_publication_basis_not_established"
            not in positive_fabric_gate_codes
        )

        wrong_owner_evidence = deepcopy(fresh_quality_evidence)
        wrong_owner_report = wrong_owner_evidence["fabric_retrieval_trace"]
        assert (
            wrong_owner_report["runtime_quality_artifact_refs"]
            == (fabric_report["runtime_quality_artifact_refs"])
        )
        assert (
            wrong_owner_report["runtime_authority_payload"]
            == (fabric_report["runtime_authority_payload"])
        )
        assert (
            wrong_owner_report["runtime_quality_publication_basis"]
            == (fabric_report["runtime_quality_publication_basis"])
        )
        wrong_owner_report["authority_envelope"]["artifact_kind"] = (
            "runtime.production_data_quality_report"
        )
        wrong_owner_scorecard = _build_fresh_scorecard(wrong_owner_evidence)
        wrong_owner_gate = next(
            gate
            for gate in wrong_owner_scorecard["quality_gates"]
            if gate.get("evidence_ref") == fabric_gate_ref
            and gate.get("code") == "hds_borrowed_authority_envelope"
        )
        assert wrong_owner_gate["status"] == "fail"
        assert wrong_owner_gate["blocking"] is True

        basisless_evidence = deepcopy(fresh_quality_evidence)
        basisless_report = basisless_evidence["fabric_retrieval_trace"]
        assert (
            basisless_report["runtime_quality_artifact_refs"]
            == (fabric_report["runtime_quality_artifact_refs"])
        )
        assert (
            basisless_report["runtime_authority_payload"]
            == (fabric_report["runtime_authority_payload"])
        )
        del basisless_report["runtime_quality_publication_basis"]
        basisless_scorecard = _build_fresh_scorecard(basisless_evidence)
        basisless_gate = next(
            gate
            for gate in basisless_scorecard["quality_gates"]
            if gate.get("evidence_ref") == fabric_gate_ref
            and gate.get("code") == "runtime_quality_report_publication_basis_not_established"
        )
        assert basisless_gate["status"] == "fail"
        assert basisless_gate["blocking"] is True
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
    assert (
        fabric_trace["scenario_evidence_contract_id"] == scenario_evidence_contract["contract_id"]
    )
    assert fabric_trace["selected_contract_binding"]["status"] == "satisfied"
    assert fabric_trace["selected_contract_binding"]["expected_family"] == ("production_msme_panel")
    assert fabric_trace["selected_contract_bindings"][0]["candidate_ref"] == (
        "production_data:curated:production_msme_panel:contract.production_msme_panel"
    )
    assert fabric_trace["selected_sources"][0]["selection_status"] == (
        "claim_admissible_contract_selected"
    )
    assert fabric_trace["selected_sources"][0]["authority_surface"] == ("claim_admissible_contract")
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
    assert variant["retrieval_context"]["fabric_spine_bindings"]["consumed_requirement_ids"] == [
        "scenario:ukraine_msme_wartime_credit_support:data:production_msme_panel"
    ]
    assert (
        variant["retrieval_context"]["production_data_evidence_context"][
            "scenario_binding_findings"
        ][0]["status"]
        == "satisfied"
    )
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
    execution_fence = _prepare_running_scoped_control_job(
        service._control_store,
        job_id=job_id,
        run_id="R_nl_method_report",
        effective_profile="research",
        context=_intent_context(),
    )

    try:
        with execution_fence:
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
        _run_nl_pipeline_with_live_admission(
            service,
            service._execute_nl_pipeline,
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
        _run_nl_pipeline_with_live_admission(
            service,
            service._execute_nl_pipeline,
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
        result = _run_nl_pipeline_with_live_admission(
            service,
            service._execute_nl_pipeline,
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
        _run_nl_pipeline_with_live_admission(
            service,
            service._execute_nl_pipeline,
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
    execution_fence = _prepare_running_scoped_control_job(
        service._control_store,
        job_id=job_id,
        run_id="R_nl_gateway_failed",
        effective_profile="research",
        context=_intent_context(),
    )

    try:
        with pytest.raises(RuntimeError) as exc_info, execution_fence:
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
                execution_profile="research",
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
        _run_nl_pipeline_with_live_admission(
            service,
            service._execute_nl_pipeline,
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
    execution_fence = _prepare_running_scoped_control_job(
        service._control_store,
        job_id=job_id,
        run_id="R_nl_formalizer_schema_failed",
        effective_profile="research",
        context=_intent_context(),
    )

    try:
        with pytest.raises(RuntimeError) as exc_info, execution_fence:
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
                execution_profile="research",
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
            _run_nl_pipeline_with_live_admission(
                service,
                service._execute_nl_pipeline,
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
    execution_fence = _prepare_running_scoped_control_job(
        service._control_store,
        job_id=job_id,
        run_id="R_nl_progress",
        effective_profile="dev",
        context=_intent_context(requested_authority_level="dev"),
    )
    progress_write_errors: list[Exception] = []
    original_update_progress = service._control_store.update_progress_state

    def _track_progress_write(**kwargs: Any) -> None:
        try:
            original_update_progress(**kwargs)
        except Exception as exc:
            progress_write_errors.append(exc)
            raise

    monkeypatch.setattr(
        service._control_store,
        "update_progress_state",
        _track_progress_write,
    )

    try:
        with execution_fence:
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
            admission = service._control_store.current_execution_job_admission()
            record = service._control_store.get_job(job_id)
            assert record is not None
            policy_intent_ref = record.progress["runtime_quality_refs"][
                "policy_intent_envelope_ref"
            ]
            policy_intent = from_canonical_bytes(
                service._artifact_store.get_bytes(ArtifactID(policy_intent_ref))
            )
            ledger_event = next(
                event
                for event in record.progress["diagnostic_events"]
                if event.get("report_key") == "policy_design_capability_ledger"
            )
            authority_envelope = from_canonical_bytes(
                service._artifact_store.get_bytes(
                    ArtifactID(ledger_event["authority_envelope_ref"])
                )
            )
    finally:
        service.close()

    assert record is not None
    assert not progress_write_errors, [str(error) for error in progress_write_errors]
    assert record.progress["phase"] == "scientist_workflow_completed"
    assert record.progress["run_id"] == "R_nl_progress"
    assert record.progress["steps_completed"] > 0
    assert record.progress["last_step"]["action"] == "run_experiment"
    assert record.progress["variants"]["simulated_qwen_1"]["status"] == "completed"
    selected_auto_refs = record.progress["variants"]["simulated_qwen_1"]["auto_data_source_refs"]
    assert selected_auto_refs["data_snapshot_ref"].startswith("sha256:")
    assert selected_auto_refs["input_bindings_ref"].startswith("sha256:")
    assert selected_auto_refs["registry_bundle_ref"].startswith("sha256:")
    from polisyos.core.artifacts.manifest import ArtifactRef

    selected_snapshot_ref = ArtifactRef.model_validate(
        captured["payload"]["inputs"]["data_snapshot_ref"]
    )
    assert str(selected_snapshot_ref.artifact_id) == selected_auto_refs["data_snapshot_ref"]
    assert selected_snapshot_ref.manifest_profile_sha256 is not None
    assert record.progress["provider_preflight"] == {
        "status": "skipped",
        "reason": "simulation_mode",
    }
    assert admission.scope.status == "established"
    assert admission.scope.tenant_id == "tenant-intent"
    assert admission.scope.cell_id == "cell-intent"
    owner_binding = record.progress["execution_owner_binding"]
    assert owner_binding == {
        "job_id": job_id,
        "run_id": "R_nl_progress",
        "tenant_id": "tenant-intent",
        "cell_id": "cell-intent",
        "requested_execution_profile": "dev",
        "effective_execution_profile": "dev",
        "attempt": 1,
        "lease_owner": f"nl-test-worker:{job_id}",
    }
    assert record.progress["runtime_diagnostic_event_status"] == "persisted"
    assert record.progress["diagnostic_event_scope_status"] == "established"
    run_intent_binding = record.progress["run_intent_binding"]
    assert run_intent_binding["policy_intent_ref"] == policy_intent_ref
    assert run_intent_binding["time_context_ref"] is None
    assert run_intent_binding["same_input_closure_ref"] is None
    assert policy_intent["run_id"] == "R_nl_progress"
    assert policy_intent["job_id"] == job_id
    assert policy_intent["tenant_id"] == "tenant-intent"
    closure = authority_envelope["same_input_closure"]
    assert closure["status"] == "not_closed"
    assert closure["policy_intent_ref"] == policy_intent_ref
    assert closure["run_id"] == "R_nl_progress"
    assert closure["job_id"] == job_id
    assert closure["tenant_id"] == "tenant-intent"
    assert closure["cell_id"] == "cell-intent"
    assert closure["time_context_ref"] is None
    assert closure["closure_sha256"] is None
    gates = _phase_barrier_gates(
        canary_kind="research",
        run_id=record.run_id,
        quality_evidence={},
        job_payload={
            "job_id": record.job_id,
            "run_id": record.run_id,
            "requested_execution_profile": str(record.requested_execution_profile),
            "effective_execution_profile": str(record.effective_execution_profile),
            "progress": record.progress,
        },
        run_payload=None,
    )
    gate_status = {gate["name"]: gate for gate in gates}
    assert gate_status["serious_phase_barrier_owner_scope"]["status"] == "fail"
    assert gate_status["serious_phase_barrier_owner_scope"]["code"] == (
        "phase_barrier_owner_scope_not_established"
    )
    assert gate_status["serious_phase_barrier_intent_binding"]["code"] == (
        "run_intent_binding_incomplete"
    )
    assert "phase_barrier_missing" in {gate["code"] for gate in gates}


@pytest.mark.parametrize(
    ("binding_mismatch", "call_run_id", "call_profile", "call_tenant_id"),
    [
        ("stale_lease", "R_nl_owner_binding", "research", "tenant-intent"),
        ("wrong_run", "R_nl_foreign_run", "research", "tenant-intent"),
        ("wrong_profile", "R_nl_owner_binding", "dev", "tenant-intent"),
        ("wrong_scope", "R_nl_owner_binding", "research", "tenant-foreign"),
    ],
)
def test_nl_pipeline_refuses_stale_or_mismatched_execution_owner(
    binding_mismatch: str,
    call_run_id: str,
    call_profile: str,
    call_tenant_id: str,
    tmp_path: Path,
) -> None:
    """A live job must match the NL call's complete scope and owner identity."""

    cas_root = tmp_path / "cas"
    service = ControlPlaneService(
        cas_root=cas_root,
        core_runs_root=tmp_path / "runs",
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="research",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control-owner-binding.sqlite3"),
            postgres_dsn=None,
        ),
        registry_providers=_registry_providers(),
    )
    job_id = "job_nl_owner_binding"
    execution_fence = _prepare_running_scoped_control_job(
        service._control_store,
        job_id=job_id,
        run_id="R_nl_owner_binding",
        effective_profile="research",
        context=_intent_context(),
    )
    refusal: NaturalLanguagePipelineRefusalError | None = None
    record = None
    baseline_trinity_refs = _trinity_bundle_artifact_ids(service._artifact_store)
    try:
        with execution_fence:
            if binding_mismatch == "stale_lease":
                service._control_store.complete_job(
                    job_id=job_id,
                    progress={"phase": "completed"},
                )
            with pytest.raises(NaturalLanguagePipelineRefusalError) as exc_info:
                service._execute_nl_pipeline(
                    run_id=call_run_id,
                    nl_request="Compare policy variants under the current admitted scope.",
                    context=_intent_context(tenant_id=call_tenant_id),
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
                    execution_profile=call_profile,
                )
            refusal = exc_info.value
            record = service._control_store.get_job(job_id)
    finally:
        service.close()

    assert refusal is not None
    assert refusal.code == "control_job_execution_scope_not_established"
    assert record is not None
    if binding_mismatch == "stale_lease":
        assert record.state == "completed"
        assert record.progress.get("execution_owner_binding") == {
            "attempt": 1,
            "cell_id": "cell-intent",
            "effective_execution_profile": "research",
            "job_id": job_id,
            "lease_owner": f"nl-test-worker:{job_id}",
            "requested_execution_profile": "research",
            "run_id": "R_nl_owner_binding",
            "tenant_id": "tenant-intent",
        }
    else:
        assert record.state == "running"
        assert record.progress.get("execution_owner_binding") is None
    assert record.progress.get("runtime_quality_refs") is None
    assert _trinity_bundle_artifact_ids(FileSystemCAS(cas_root)) == baseline_trinity_refs


def test_nl_pipeline_refuses_legacy_job_without_admitted_execution_scope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    _forbid_real_gateway_network(monkeypatch)
    cas_root = tmp_path / "cas"
    service = ControlPlaneService(
        cas_root=cas_root,
        core_runs_root=tmp_path / "runs",
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="dev",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control-unscoped.sqlite3"),
            postgres_dsn=None,
        ),
        registry_providers=_registry_providers(),
    )
    job_id = "job_nl_unscoped"
    execution_fence = _prepare_running_scoped_control_job(
        service._control_store,
        job_id=job_id,
        run_id="R_nl_unscoped",
        effective_profile="dev",
        context=_intent_context(requested_authority_level="dev"),
        include_execution_scope=False,
    )
    baseline_trinity_refs = _trinity_bundle_artifact_ids(service._artifact_store)
    try:
        with execution_fence:
            with pytest.raises(NaturalLanguagePipelineRefusalError) as exc_info:
                service._execute_nl_pipeline(
                    run_id="R_nl_unscoped",
                    nl_request="Compare simulated policy variants for MSME support.",
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
                    execution_profile="dev",
                )
            record = service._control_store.get_job(job_id)
    finally:
        service.close()

    assert exc_info.value.code == "control_job_execution_scope_not_established"
    assert record is not None
    assert record.progress.get("execution_owner_binding") is None
    assert record.progress.get("runtime_quality_refs") is None
    assert _trinity_bundle_artifact_ids(FileSystemCAS(cas_root)) == baseline_trinity_refs


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
    execution_fence = _prepare_running_scoped_control_job(
        service._control_store,
        job_id=job_id,
        run_id="R_nl_scientist_progress",
        effective_profile="dev",
        context=_intent_context(requested_authority_level="dev"),
    )

    try:
        with execution_fence:
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
    execution_fence = _prepare_running_scoped_control_job(
        service._control_store,
        job_id=job_id,
        run_id="R_nl_progress_failed",
        effective_profile="dev",
        context=_intent_context(requested_authority_level="dev"),
    )

    try:
        with pytest.raises(RuntimeError, match="foundry execution aborted"), execution_fence:
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


def test_selected_final_claims_refusal_report_blocks_grounding() -> None:
    from polisyos.runtime.http.services.control.nl_pipeline import (
        _selected_final_claims_refusal_report,
    )
    from polisyos.scientist.validation.policy_grounding import (
        build_policy_grounding_matrix_report,
    )

    citation = _selected_final_claims_refusal_report(
        refusal_code="nl_final_policy_claims_selected_unreadable"
    )
    assert citation["status"] == "fail"
    assert citation["blocking_issue_count"] == 1
    assert citation["claims"] == []
    assert citation["issues"][0]["code"] == "selected_final_policy_claims_unavailable"
    grounding = build_policy_grounding_matrix_report(
        claims=[],
        citation_faithfulness_report=citation,
        enforce_claim_support_semantics=True,
    )
    assert grounding["status"] == "fail"
    assert grounding["citation_faithfulness"]["status"] == "fail"


def test_empty_selected_final_claims_payload_is_not_absence() -> None:
    import pytest

    from polisyos.common.canonical_profile import CanonicalProfileRefusalError
    from polisyos.runtime.http.services.control.nl_pipeline import (
        _require_final_claims_report_shape,
    )
    from polisyos.scientist.validation.policy_grounding import (
        build_policy_grounding_matrix_report,
    )

    with pytest.raises(CanonicalProfileRefusalError) as refusal:
        _require_final_claims_report_shape(
            {},
            refusal_code="nl_final_policy_claims_selected_payload_invalid",
        )
    assert refusal.value.code == "nl_final_policy_claims_selected_payload_invalid"
    with pytest.raises(CanonicalProfileRefusalError) as malformed_claims:
        _require_final_claims_report_shape(
            {"claims": [None]},
            refusal_code="nl_final_policy_claims_selected_payload_invalid",
        )
    assert malformed_claims.value.code == "nl_final_policy_claims_selected_payload_invalid"
    with pytest.raises(CanonicalProfileRefusalError) as malformed_inline:
        _require_final_claims_report_shape(
            "not-an-object",
            refusal_code="nl_final_policy_claims_inline_payload_invalid",
        )
    assert malformed_inline.value.code == "nl_final_policy_claims_inline_payload_invalid"

    valid_empty_failed_report = {
        "schema_version": "policyos.scientist.final_policy_claims.v1",
        "extraction_status": "fail",
        "human_review_required": False,
        "claims": [],
        "major_claims": [],
        "issues": [{"code": "policy_claim_extraction_failed", "severity": "fail"}],
    }
    selected_report = _require_final_claims_report_shape(
        valid_empty_failed_report,
        refusal_code="nl_final_policy_claims_selected_payload_invalid",
    )
    assert selected_report == valid_empty_failed_report

    # The typed empty artifact is retained for the real quality consumer, which
    # refuses it as unusable policy evidence instead of treating it as absence.
    grounding = build_policy_grounding_matrix_report(
        claims=[],
        claim_extraction_report=selected_report,
        enforce_claim_support_semantics=True,
    )
    assert grounding["status"] == "fail"
    assert "policy_claim_extraction_failed" in {issue["code"] for issue in grounding["issues"]}
    assert "no_policy_claims" in {issue["code"] for issue in grounding["issues"]}


@pytest.mark.parametrize(
    ("selected_fault", "expected_refusal"),
    [
        ("malformed_payload", "nl_final_policy_claims_selected_payload_invalid"),
        ("missing_blob", "nl_final_policy_claims_selected_unreadable"),
        ("integrity_mismatch", "nl_final_policy_claims_selected_unreadable"),
        ("profile_mismatch", "nl_final_policy_claims_selected_unreadable"),
        ("inline_conflict", "nl_final_policy_claims_selected_inline_mismatch"),
        ("backend_outage", None),
    ],
)
def test_nl_pipeline_selected_final_claims_faults_block_inline_fallback_or_propagate_outage(
    selected_fault: str,
    expected_refusal: str | None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Item-local faults refuse evidence; shared CAS outage escapes without result writes."""
    from polisyos.runtime.http.errors import RuntimeDependencyUnavailableError

    captured: dict[str, Any] = {}
    selected_cas: dict[str, Any] = {}

    def _capture_state(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        return {"run_id": payload["run_id"], "reports_index": {}}

    original_put_json = FileSystemCAS.put_json
    original_get_bytes = FileSystemCAS.get_bytes

    def _persist_selected_fault(
        self: FileSystemCAS,
        obj: object,
        opts: ArtifactWriteOptions,
        canon_spec: CanonSpec | None = None,
        *,
        return_selected_profile: bool = False,
    ) -> Any:
        if selected_cas.get("read_attempted"):
            selected_cas.setdefault("post_read_put_kinds", []).append(opts.kind)
        inline_ref = original_put_json(
            self,
            obj,
            opts,
            canon_spec=canon_spec,
            return_selected_profile=return_selected_profile,
        )
        if opts.kind != "scientist.final_policy_claims":
            return inline_ref
        assert isinstance(obj, dict)
        selected_cas["store"] = self
        selected_cas["inline"] = dict(obj)
        if selected_fault == "malformed_payload":
            malformed = {**dict(obj), "claims": [None]}
            selected_ref = original_put_json(
                self,
                malformed,
                opts,
                canon_spec=canon_spec,
                return_selected_profile=return_selected_profile,
            )
            selected_cas["payload"] = malformed
        elif selected_fault == "profile_mismatch":
            selected_ref = inline_ref.model_copy(
                update={"manifest_profile_sha256": "sha256:" + "0" * 64}
            )
            selected_cas["payload"] = dict(obj)
        elif selected_fault == "inline_conflict":
            stored_report = dict(obj)
            assert stored_report.get("claims")
            inline_claims = [dict(claim) for claim in obj.get("claims", [])]
            inline_claims[0]["text"] = "The inline projection conflicts with the selected report."
            obj["claims"] = inline_claims
            selected_cas["inline"] = dict(obj)
            selected_cas["payload"] = stored_report
            selected_ref = inline_ref
        else:
            selected_ref = inline_ref
            selected_cas["payload"] = dict(obj)
        selected_cas["ref"] = selected_ref
        if selected_fault in {"missing_blob", "integrity_mismatch"}:
            blob_path, _ = self._paths(ArtifactID(str(selected_ref.artifact_id)))
            selected_cas["blob_path"] = blob_path
            if selected_fault == "missing_blob":
                backup_path = blob_path.with_name(blob_path.name + ".selected-missing-backup")
                assert not backup_path.exists()
                selected_cas["blob_backup_path"] = backup_path
            else:
                selected_cas["original_blob"] = blob_path.read_bytes()
        return selected_ref

    def _get_selected_fault(
        self: FileSystemCAS,
        artifact_id: ArtifactID | str,
    ) -> bytes:
        selected_ref = selected_cas.get("ref")
        requested_artifact_id = getattr(artifact_id, "artifact_id", artifact_id)
        requested_profile = getattr(artifact_id, "manifest_profile_sha256", None)
        selected_profile = getattr(selected_ref, "manifest_profile_sha256", None)
        if (
            selected_ref is not None
            and str(requested_artifact_id) == str(selected_ref.artifact_id)
            and (requested_profile is None or requested_profile == selected_profile)
        ):
            selected_cas["read_attempted"] = True
            if selected_fault == "backend_outage":
                raise OSError("injected whole-CAS outage")
            blob_path = selected_cas.get("blob_path")
            if selected_fault == "missing_blob" and isinstance(blob_path, Path):
                blob_path.replace(selected_cas["blob_backup_path"])
            elif selected_fault == "integrity_mismatch" and isinstance(blob_path, Path):
                blob_path.write_bytes(b"corrupted isolated selected final-claims fixture")
        try:
            return original_get_bytes(self, artifact_id)
        except (OSError, ValueError) as exc:
            if selected_cas.get("read_attempted"):
                selected_cas["selected_read_exception"] = type(exc).__name__
                if selected_fault == "missing_blob":
                    selected_cas["missing_blob_observed"] = not selected_cas["blob_path"].exists()
            raise
        finally:
            if selected_fault == "missing_blob":
                backup_path = selected_cas.get("blob_backup_path")
                blob_path = selected_cas.get("blob_path")
                if (
                    isinstance(backup_path, Path)
                    and isinstance(blob_path, Path)
                    and backup_path.exists()
                ):
                    backup_path.replace(blob_path)
            elif selected_fault == "integrity_mismatch":
                blob_path = selected_cas.get("blob_path")
                original_blob = selected_cas.get("original_blob")
                if isinstance(blob_path, Path) and isinstance(original_blob, bytes):
                    blob_path.write_bytes(original_blob)

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
        lambda _store, _snapshot: MethodCatalogSnapshotRef(artifact_id="sha256:" + "e" * 64),
    )
    monkeypatch.setattr(FileSystemCAS, "put_json", _persist_selected_fault)
    monkeypatch.setattr(FileSystemCAS, "get_bytes", _get_selected_fault)

    service = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="research",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control-nl-selected-claims.sqlite3"),
            postgres_dsn=None,
        ),
        registry_providers=_registry_providers(),
    )
    result: dict[str, Any] | None = None
    citation: dict[str, Any] | None = None
    grounding: dict[str, Any] | None = None
    selected_payload: dict[str, Any] | None = None
    outage: RuntimeDependencyUnavailableError | None = None
    try:
        kwargs = {
            "run_id": f"R_nl_selected_claims_{selected_fault}_with_inline",
            "nl_request": "Evaluate Ukraine MSME support and retain the selected evidence basis.",
            "context": _normative_context(),
            "domain_hint": "Ukraine wartime MSME support policy",
            "data_source": None,
            "max_iterations": 1,
            "llm_models": ["simulated-qwen"],
            "max_parallel_models": 1,
            "run_budget_usd": None,
            "per_model_budget_usd": None,
            "checkpoint_policy": "strict",
            "execution_plan_ref": None,
            "execution_plan_payload": None,
            "stop_criteria_payload": {},
            "governance_constraints_payload": [],
            "expected_outputs_payload": [],
            "execution_profile": "research",
            "allow_mock_fallback": False,
            "provider_preflight_payload": {"status": "skipped", "reason": "simulation_mode"},
        }
        if selected_fault == "backend_outage":
            with pytest.raises(RuntimeDependencyUnavailableError) as exc_info:
                _run_nl_pipeline_with_live_admission(
                    service, service._execute_nl_pipeline, **kwargs
                )
            outage = exc_info.value
        else:
            result = _run_nl_pipeline_with_live_admission(
                service, service._execute_nl_pipeline, **kwargs
            )
            citation = from_canonical_bytes(
                service._artifact_store.get_bytes(
                    ArtifactID(result["citation_faithfulness_report_ref"])
                )
            )
            grounding = from_canonical_bytes(
                service._artifact_store.get_bytes(ArtifactID(result["policy_grounding_matrix_ref"]))
            )
            if selected_fault in {"malformed_payload", "profile_mismatch", "inline_conflict"}:
                selected_payload = from_canonical_bytes(
                    original_get_bytes(
                        selected_cas["store"],
                        ArtifactID(str(selected_cas["ref"].artifact_id)),
                    )
                )
    finally:
        service.close()
        backup_path = selected_cas.get("blob_backup_path")
        blob_path = selected_cas.get("blob_path")
        if isinstance(backup_path, Path) and isinstance(blob_path, Path) and backup_path.exists():
            backup_path.replace(blob_path)
        original_blob = selected_cas.get("original_blob")
        if isinstance(original_blob, bytes) and isinstance(blob_path, Path):
            blob_path.write_bytes(original_blob)

    if selected_fault == "backend_outage":
        assert outage is not None
        assert outage.code == "content_addressed_storage_unavailable"
        assert outage.dependency == "content_addressed_storage"
        assert outage.retry_state == "retryable"
        assert selected_cas["read_attempted"]
        assert selected_cas.get("post_read_put_kinds", []) == []
        assert selected_cas["inline"]["claims"]
        return

    params = captured["payload"]["params"]
    selected_variant = next(
        item for item in params["llm_model_variants"] if item.get("selected_for_workflow")
    )
    assert selected_variant["final_policy_claims_ref"] == str(selected_cas["ref"].artifact_id)
    assert selected_variant["final_policy_claims"] == selected_cas["inline"]
    assert selected_variant["final_policy_claims"]["claims"]
    if selected_fault != "profile_mismatch":
        assert selected_cas["read_attempted"]

    assert expected_refusal is not None
    assert result is not None
    assert citation is not None
    assert grounding is not None

    if selected_fault == "malformed_payload":
        assert selected_payload == selected_cas["payload"]
        assert selected_payload["claims"] == [None]
        assert selected_variant["final_policy_claims"] != selected_payload
    elif selected_fault == "missing_blob":
        assert selected_cas["selected_read_exception"] == "FileNotFoundError"
        assert selected_payload is None
        assert selected_cas["missing_blob_observed"]
        assert selected_cas["blob_path"].is_file()
    elif selected_fault == "integrity_mismatch":
        assert selected_cas["selected_read_exception"] == "ArtifactIntegrityError"
        assert selected_payload is None
    elif selected_fault == "profile_mismatch":
        assert selected_payload == selected_cas["inline"]
        assert selected_cas["ref"].manifest_profile_sha256 == "sha256:" + "0" * 64
    else:
        assert selected_payload == selected_cas["payload"]
        assert selected_payload != selected_variant["final_policy_claims"]
    assert citation["status"] == "fail"
    assert citation["blocking_issue_count"] == 1
    assert citation["issues"][0]["code"] == "selected_final_policy_claims_unavailable"
    assert expected_refusal in citation["issues"][0]["message"]
    assert grounding["citation_faithfulness"]["status"] == "fail"


def test_runtime_dependency_outage_persists_typed_failure_through_control_job_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persist a shared-CAS outage via the normal launch, worker, store, and status read."""
    import uuid

    from tests._helpers.control_worker import (
        dispatch_one_control_job,
        stop_embedded_control_worker,
    )
    from tests._helpers.runtime_http import build_runtime_api_env, close_runtime_api_env

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    _forbid_real_gateway_network(monkeypatch)
    env = build_runtime_api_env(tmp_path, include_test_client=True)
    app = env["app"]
    client = env["client"]
    service = app.state._control_service
    store = service._control_store
    try:
        stop_embedded_control_worker(service)
        launch_response = client.post(
            "/api/v1/control/runs/nl",
            headers={"Idempotency-Key": uuid.uuid4().hex},
            json={
                "request": "Analyze a small-business liquidity support policy.",
                "llm_model": "simulated-qwen",
                "max_iterations": 1,
            },
        )
        assert launch_response.status_code == 200, launch_response.text
        job_id = str(launch_response.json()["job_id"])
        queued = store.get_job(job_id)
        assert queued is not None
        assert queued.state == "pending"
        assert queued.attempt == 0
        assert queued.payload_ref is not None

        def _raise_whole_cas_outage(
            self: FileSystemCAS,
            artifact_id: ArtifactID | str,
        ) -> bytes:
            del self, artifact_id
            raise OSError("injected whole-CAS worker outage")

        monkeypatch.setattr(FileSystemCAS, "get_bytes", _raise_whole_cas_outage)
        dispatched = dispatch_one_control_job(
            store=store,
            handler=service._process_control_job,
            expected_job_id=job_id,
        )
        assert dispatched == job_id

        failed = store.get_job(job_id)
        assert failed is not None
        assert failed.state == "failed"
        assert failed.attempt == 1
        assert failed.finished_at is not None
        failure = failed.progress["failure"]
        assert failure["code"] == "content_addressed_storage_unavailable"
        assert failure["layer"] == "content_addressed_storage"
        assert failure["phase"] == "job_execution"
        assert failure["retryable"] is True
        assert failure["run_id"] == failed.run_id
        assert failure["job_id"] == job_id
        dead_letter = next(item for item in store.list_dead_letter_jobs() if item.job_id == job_id)
        assert dead_letter.attempt == 1

        status_response = client.get(f"/api/v1/control/jobs/{job_id}")
        assert status_response.status_code == 200, status_response.text
        served = status_response.json()
        assert served["state"] == "failed"
        assert served["failure"]["code"] == "content_addressed_storage_unavailable"
        assert served["failure"]["layer"] == "content_addressed_storage"
        assert served["failure"]["retryable"] is True
    finally:
        close_runtime_api_env(env)


def test_final_claims_variant_selector_is_producer_owned_and_profile_exact(
    tmp_path: Path,
) -> None:
    from polisyos.common.canonical_profile import CanonicalProfileRefusalError
    from polisyos.core.artifacts.manifest import ProducerInfo
    from polisyos.runtime.http.services.control.nl_pipeline import (
        _resolve_selected_materialization_ref,
        _selected_final_policy_claims_ref_for_variant,
        _validate_producer_selected_ref_membership,
    )

    store = FileSystemCAS(tmp_path / "cas")
    opts = ArtifactWriteOptions(
        kind="scientist.final_policy_claims",
        media_type="application/json",
        schema=SchemaInfo(name="polisyos.scientist.FinalPolicyClaims", version="1.0"),
        producer=ProducerInfo(component="polisyos.tests.selected_claims", version="1.0"),
    )
    payload = {
        "schema_version": "policyos.scientist.final_policy_claims.v1",
        "extraction_status": "pass",
        "human_review_required": False,
        "claims": [{"claim_id": "same", "text": "same payload"}],
    }
    canonical_view = store.put_json(
        payload,
        opts,
        CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    ascii_view = store.put_json(
        payload,
        opts,
        CanonSpec(forbid_floats=False, ensure_ascii=True),
        return_selected_profile=True,
    )
    assert canonical_view.artifact_id == ascii_view.artifact_id
    assert canonical_view.manifest_profile_sha256 != ascii_view.manifest_profile_sha256
    variant_views = {
        "variant_a": canonical_view,
        "variant_b": ascii_view,
    }
    candidates = {str(canonical_view.artifact_id): [canonical_view, ascii_view]}
    legacy_resolver_calls: list[object] = []

    def _legacy_resolver(value: object) -> ArtifactRef:
        legacy_resolver_calls.append(value)
        return _resolve_selected_materialization_ref(
            store,
            value,
            candidates,
            kind="scientist.final_policy_claims",
        )

    variant_a = {
        "model_variant_id": "variant_a",
        "final_policy_claims_ref": str(canonical_view.artifact_id),
        "final_policy_claims_selected_ref": canonical_view.model_dump(mode="json"),
    }
    assert (
        _selected_final_policy_claims_ref_for_variant(
            variant_a,
            producer_selected_refs=variant_views,
            resolve_legacy_ref=_legacy_resolver,
        )
        == canonical_view
    )

    typed_only = {
        "model_variant_id": "variant_a",
        "final_policy_claims_selected_ref": canonical_view.model_dump(mode="json"),
    }
    assert (
        _selected_final_policy_claims_ref_for_variant(
            typed_only,
            producer_selected_refs=variant_views,
            resolve_legacy_ref=_legacy_resolver,
        )
        == canonical_view
    )
    legacy_only = {
        "model_variant_id": "variant_b",
        "final_policy_claims_ref": str(ascii_view.artifact_id),
    }
    assert (
        _selected_final_policy_claims_ref_for_variant(
            legacy_only,
            producer_selected_refs=variant_views,
            resolve_legacy_ref=_legacy_resolver,
        )
        == ascii_view
    )
    _validate_producer_selected_ref_membership(
        [variant_a, legacy_only],
        variant_views,
        refusal_code="nl_final_policy_claims_ref_invalid",
    )
    for inconsistent_variants in (
        [{"model_variant_id": "unowned_variant"}],
        [variant_a, {**variant_a}],
    ):
        with pytest.raises(CanonicalProfileRefusalError):
            _validate_producer_selected_ref_membership(
                inconsistent_variants,
                variant_views,
                refusal_code="nl_final_policy_claims_ref_invalid",
            )
    for malformed_projection in (
        {"model_variant_id": "variant_a"},
        {"model_variant_id": "variant_a", "final_policy_claims_ref": ""},
        {"model_variant_id": "variant_a", "final_policy_claims_ref": []},
        {"model_variant_id": "variant_a", "final_policy_claims_ref": None},
        {"model_variant_id": "variant_a", "final_policy_claims_selected_ref": None},
    ):
        with pytest.raises(CanonicalProfileRefusalError):
            _selected_final_policy_claims_ref_for_variant(
                malformed_projection,
                producer_selected_refs=variant_views,
                resolve_legacy_ref=_legacy_resolver,
            )

    wrong_owner_legacy_only = {
        "model_variant_id": "unowned_variant",
        "final_policy_claims_ref": str(canonical_view.artifact_id),
    }
    with pytest.raises(CanonicalProfileRefusalError):
        _selected_final_policy_claims_ref_for_variant(
            wrong_owner_legacy_only,
            producer_selected_refs=variant_views,
            resolve_legacy_ref=_legacy_resolver,
        )

    wrong_sibling = {
        **variant_a,
        "final_policy_claims_selected_ref": ascii_view.model_dump(mode="json"),
    }
    malformed_selector = {
        **variant_a,
        "final_policy_claims_selected_ref": {
            **canonical_view.model_dump(mode="json"),
            "manifest_profile_sha256": "sha256:malformed",
        },
    }
    removed_selector = {
        "model_variant_id": "variant_a",
        "final_policy_claims_ref": str(canonical_view.artifact_id),
    }
    self_attested_selector = {
        **variant_a,
        "model_variant_id": "legacy_unowned",
    }
    for adversarial in (
        wrong_sibling,
        malformed_selector,
        self_attested_selector,
    ):
        with pytest.raises(CanonicalProfileRefusalError):
            _selected_final_policy_claims_ref_for_variant(
                adversarial,
                producer_selected_refs=variant_views,
                resolve_legacy_ref=_legacy_resolver,
            )

    assert legacy_resolver_calls == []

    legacy_ambiguous = {
        "model_variant_id": "legacy_variant",
        "final_policy_claims_ref": str(canonical_view.artifact_id),
    }
    with pytest.raises(CanonicalProfileRefusalError):
        _selected_final_policy_claims_ref_for_variant(
            legacy_ambiguous,
            producer_selected_refs={},
            resolve_legacy_ref=_legacy_resolver,
        )
    assert legacy_resolver_calls == [str(canonical_view.artifact_id)]

    calls_before_selected_map_ref = list(legacy_resolver_calls)
    assert (
        _selected_final_policy_claims_ref_for_variant(
            removed_selector,
            producer_selected_refs=variant_views,
            resolve_legacy_ref=_legacy_resolver,
        )
        == canonical_view
    )
    assert legacy_resolver_calls == calls_before_selected_map_ref

    unique_candidates = {str(canonical_view.artifact_id): [canonical_view]}
    unique_legacy_ref = _selected_final_policy_claims_ref_for_variant(
        legacy_ambiguous,
        producer_selected_refs={},
        resolve_legacy_ref=lambda value: _resolve_selected_materialization_ref(
            store,
            value,
            unique_candidates,
            kind="scientist.final_policy_claims",
        ),
    )
    assert unique_legacy_ref == canonical_view
    assert (
        _selected_final_policy_claims_ref_for_variant(
            {"model_variant_id": "legacy_inline_only"},
            producer_selected_refs={},
            resolve_legacy_ref=_legacy_resolver,
        )
        is None
    )


def test_nl_pipeline_carries_same_payload_variant_profiles_into_selected_citation_consumer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Keep map-owned CAS edges after legacy projection removal."""
    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.core.artifacts.backends.config import (
        with_ambient_ownership_enforcement_if_supported,
    )
    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.core.artifacts.manifest import (
        ArtifactRef,
        ArtifactTenantContextInfo,
        ProducerInfo,
    )
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.ir.trinity import TrinityBundle
    from polisyos.ir.trinity.loaders import load_trinity_bundle_artifact
    from polisyos.scientist.agent.protocols import DraftResult

    captured: dict[str, Any] = {}
    trinity_write_count = 0

    def _capture_state(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        return {"run_id": payload["run_id"], "reports_index": {}}

    from polisyos.scientist.agent.drafter_clients import LLMDrafterAgent
    from polisyos.scientist.agent.formalizer import build_final_policy_claims_report

    async def _same_draft(
        self: LLMDrafterAgent,
        problem_frame: object,
        *,
        data_context: dict[str, Any] | None = None,
        hints: list[str] | None = None,
        prior_drafts: list[Any] | None = None,
    ) -> DraftResult:
        del self, problem_frame, data_context, hints, prior_drafts
        return DraftResult(
            draft_id="r4_shared_variant_draft",
            problem_frame_ref="sha256:" + "1" * 64,
            narrative="Target wartime credit support to eligible MSMEs.",
            rationale="Shared deterministic test draft.",
            claim_supports=[
                {
                    "claim_id": "r4_shared_claim",
                    "claim_family": "recommendation",
                    "major": True,
                    "text": "Target wartime credit support to eligible MSMEs.",
                    "policy_action": "targeted_credit_support",
                    "norm_refs": ["norm.ua.credit_eligibility"],
                }
            ],
        )

    def _stable_final_claims_report(
        *,
        draft: DraftResult,
        trinity_bundle: object = None,
    ) -> dict[str, Any]:
        report = build_final_policy_claims_report(draft=draft, trinity_bundle=trinity_bundle)
        report["created_at"] = "2026-01-01T00:00:00+00:00"
        return report

    original_put_bytes = FileSystemCAS.put_bytes

    def _write_distinct_trinity_views(
        self: FileSystemCAS,
        data: bytes,
        opts: ArtifactWriteOptions,
        *,
        return_selected_profile: bool = False,
    ) -> Any:
        nonlocal trinity_write_count
        if opts.kind == "ir.trinity_bundle":
            trinity_write_count += 1
            opts = replace(
                opts,
                producer=ProducerInfo(
                    component="polisyos.tests.nl_variant_lineage",
                    version=f"profile-{trinity_write_count}",
                ),
            )
        return original_put_bytes(
            self,
            data,
            opts,
            return_selected_profile=return_selected_profile,
        )

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    _forbid_real_gateway_network(monkeypatch)
    monkeypatch.setattr("polisyos.fabric.retrieval.RetrievalService", _FakeRetrievalService)
    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _capture_state)
    monkeypatch.setattr(LLMDrafterAgent, "draft_policy", _same_draft)
    monkeypatch.setattr(
        "polisyos.scientist.agent.formalizer.build_final_policy_claims_report",
        _stable_final_claims_report,
    )
    monkeypatch.setattr(FileSystemCAS, "put_bytes", _write_distinct_trinity_views)
    import asyncio

    original_gather = asyncio.gather

    async def _drop_legacy_claim_projections(*awaitables: Any, **kwargs: Any) -> Any:
        variants = await original_gather(*awaitables, **kwargs)
        for variant in variants:
            if isinstance(variant, BaseException):
                raise variant
            if not isinstance(variant, dict):
                raise TypeError("variant result must be a mapping")
            variant.pop("final_policy_claims_ref", None)
            variant.pop("trinity_bundle_ref", None)
        return variants

    async def _cancelled_variant() -> dict[str, Any]:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(_drop_legacy_claim_projections(_cancelled_variant(), return_exceptions=True))

    monkeypatch.setattr(asyncio, "gather", _drop_legacy_claim_projections)
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
    cas_root = tmp_path / "cas"
    ambient_store = with_ambient_ownership_enforcement_if_supported(FileSystemCAS(cas_root))
    service = ControlPlaneService(
        cas_root=cas_root,
        core_runs_root=tmp_path / "runs",
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="research",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control-nl-variant-profiles.sqlite3"),
            postgres_dsn=None,
        ),
        artifact_store=ambient_store,
        registry_providers=_registry_providers(),
    )

    def _owner_manifest(ref: Any) -> Any:
        fresh_owner_store = FileSystemCAS(service._artifact_store.root).for_tenant(
            "tenant-intent",
            "cell-intent",
        )
        with tenant_scope(None, tenant_id="tenant-intent", cell_id="cell-intent"):
            return fresh_owner_store.get_manifest(ref)

    def _owner_bytes(ref: Any) -> bytes:
        fresh_owner_store = FileSystemCAS(service._artifact_store.root).for_tenant(
            "tenant-intent",
            "cell-intent",
        )
        with tenant_scope(None, tenant_id="tenant-intent", cell_id="cell-intent"):
            return fresh_owner_store.get_bytes(ref)

    expected_owner = ArtifactTenantContextInfo(tenant_id="tenant-intent", cell_id="cell-intent")
    try:
        result = _run_nl_pipeline_with_live_admission(
            service,
            service._execute_nl_pipeline,
            run_id="R_nl_selected_claims_variant_profiles",
            nl_request="Compare two deterministic variants with the same policy claims.",
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
        payload = captured["payload"]
        assert captured["kwargs"]["store"] is service._artifact_store
        variants = payload["params"]["llm_model_variants"]
        assert len(variants) == 2
        assert trinity_write_count == len(variants)
        owner_artifact_specs = (
            ("execution_plan_ref", "scientist.execution_plan"),
            ("method_catalog_snapshot_ref", "foundry.method_catalog_snapshot"),
            ("preflight_report_ref", "scientist.preflight_report"),
            ("evaluator_report_ref", "scientist.evaluator_report"),
            ("iteration_state_ref", "scientist.iteration_state"),
            ("reproducibility_manifest_ref", "scientist.reproducibility_manifest"),
        )
        for variant in variants:
            for ref_key, expected_kind in owner_artifact_specs:
                ref_value = variant.get(ref_key)
                assert isinstance(ref_value, str) and ref_value
                owned_ref = ArtifactRef(
                    artifact_id=ref_value,
                    kind=expected_kind,
                    media_type="application/json",
                )
                owner_manifest = _owner_manifest(owned_ref)
                assert owner_manifest.kind == expected_kind
                assert owner_manifest.tenant_context == expected_owner
                assert artifact_manifest_profile_sha256(owner_manifest) is not None
        selected_variant_id = payload["params"]["llm_selected_variant_id"]
        selected_variant = next(
            variant for variant in variants if variant["model_variant_id"] == selected_variant_id
        )
        quality_evidence = payload["params"]["runtime_quality_evidence"]["production_data_quality"]
        quality_ref_key = "production_data_quality_report_ref"
        quality_ref = ArtifactRef.model_validate(
            quality_evidence["runtime_quality_artifact_refs"][quality_ref_key]
        )
        quality_manifest = _owner_manifest(quality_ref)
        assert not any(item.role == "production_data_payload" for item in quality_manifest.inputs)
        assert (
            quality_evidence["authority_envelope"]["same_input_closure"][
                "production_data_manifest_ref"
            ]
            is None
        )
        selected_ref = ArtifactRef.model_validate(
            selected_variant["final_policy_claims_selected_ref"]
        )
        sibling = next(variant for variant in variants if variant is not selected_variant)
        sibling_ref = ArtifactRef.model_validate(sibling["final_policy_claims_selected_ref"])
        assert selected_ref.artifact_id == sibling_ref.artifact_id
        assert selected_ref.manifest_profile_sha256 is not None
        assert sibling_ref.manifest_profile_sha256 is not None
        assert selected_ref.manifest_profile_sha256 != sibling_ref.manifest_profile_sha256
        selected_trinity_ref = ArtifactRef.model_validate(
            selected_variant["trinity_bundle_selected_ref"]
        )
        sibling_trinity_ref = ArtifactRef.model_validate(sibling["trinity_bundle_selected_ref"])
        if selected_trinity_ref.artifact_id == sibling_trinity_ref.artifact_id:
            assert selected_trinity_ref.manifest_profile_sha256 is not None
            assert sibling_trinity_ref.manifest_profile_sha256 is not None
            assert (
                selected_trinity_ref.manifest_profile_sha256
                != sibling_trinity_ref.manifest_profile_sha256
            )
        for variant in variants:
            assert "final_policy_claims_ref" not in variant
            assert "trinity_bundle_ref" not in variant
        assert selected_variant["final_policy_claims"] == sibling["final_policy_claims"]

        for variant in variants:
            variant_claims_ref = ArtifactRef.model_validate(
                variant["final_policy_claims_selected_ref"]
            )
            variant_trinity_ref = ArtifactRef.model_validate(variant["trinity_bundle_selected_ref"])
            variant_manifest = _owner_manifest(variant_trinity_ref)
            assert variant_manifest.tenant_context == expected_owner
            claims_manifest = _owner_manifest(variant_claims_ref)
            claims_edges = {item.role: item for item in claims_manifest.inputs}
            assert claims_manifest.tenant_context == expected_owner
            assert claims_edges["trinity_bundle"].artifact_id == variant_trinity_ref.artifact_id
            assert (
                claims_edges["trinity_bundle"].manifest_profile_sha256
                == variant_trinity_ref.manifest_profile_sha256
            )
            fresh_owner_store = FileSystemCAS(service._artifact_store.root).for_tenant(
                "tenant-intent",
                "cell-intent",
            )
            with tenant_scope(None, tenant_id="tenant-intent", cell_id="cell-intent"):
                fresh_bundle = load_trinity_bundle_artifact(
                    ensure_ir_artifact_store(fresh_owner_store),
                    variant_trinity_ref,
                )
            assert isinstance(fresh_bundle, TrinityBundle)
            ledger_ref = ArtifactID(variant["prompt_tool_ledger_ref"])
            ledger_manifest = _owner_manifest(ledger_ref)
            assert ledger_manifest.tenant_context == expected_owner
            ledger_inputs = {item.role: item for item in ledger_manifest.inputs}
            for ref_key, role, expected_kind in (
                ("execution_plan_ref", "variant_execution_plan", "scientist.execution_plan"),
                (
                    "method_catalog_snapshot_ref",
                    "variant_method_catalog_snapshot",
                    "foundry.method_catalog_snapshot",
                ),
                ("preflight_report_ref", "variant_preflight_report", "scientist.preflight_report"),
                ("evaluator_report_ref", "variant_evaluator_report", "scientist.evaluator_report"),
            ):
                source_ref = ArtifactRef(
                    artifact_id=variant[ref_key],
                    kind=expected_kind,
                    media_type="application/json",
                )
                source_manifest = _owner_manifest(source_ref)
                ledger_edge = ledger_inputs[role]
                assert ledger_edge.artifact_id == source_manifest.artifact_id
                assert ledger_edge.manifest_profile_sha256 == artifact_manifest_profile_sha256(
                    source_manifest
                )
            for role, selected_view in (
                ("variant_final_policy_claims", variant_claims_ref),
                ("variant_trinity_bundle", variant_trinity_ref),
            ):
                assert role in ledger_inputs
                assert ledger_inputs[role].artifact_id == selected_view.artifact_id
                assert (
                    ledger_inputs[role].manifest_profile_sha256
                    == selected_view.manifest_profile_sha256
                )
            ledger_payload = variant["prompt_tool_ledger"]
            assert ledger_payload["model_variant_id"] == variant["model_variant_id"]
            ledger_step = ledger_payload["steps"][0]
            assert str(variant_claims_ref.artifact_id) in ledger_step["output_refs"]
            assert str(variant_trinity_ref.artifact_id) in ledger_step["output_refs"]
            assert all(isinstance(ref, str) for ref in ledger_step["output_refs"])
            assert all(
                isinstance(handoff["handoff_ref"], str)
                for handoff in ledger_step["authority_handoff_refs"]
            )
            adjudication_ref = ArtifactID(variant["llm_model_adjudication_ref"])
            assert _owner_manifest(adjudication_ref).tenant_context == expected_owner

        citation_ref = ArtifactID(selected_variant["citation_faithfulness_report_ref"])
        citation_manifest = _owner_manifest(citation_ref)
        citation_inputs = {item.role: item for item in citation_manifest.inputs}
        assert citation_manifest.tenant_context == expected_owner
        assert citation_inputs["final_policy_claims"].artifact_id == selected_ref.artifact_id
        assert (
            citation_inputs["final_policy_claims"].manifest_profile_sha256
            == selected_ref.manifest_profile_sha256
        )
        source_quality_ref = ArtifactID(selected_variant["source_quality_report_ref"])
        assert _owner_manifest(source_quality_ref).tenant_context == expected_owner

        from polisyos.core.artifacts import ArtifactOwnershipError

        foreign_store = FileSystemCAS(service._artifact_store.root).for_tenant(
            "tenant-outsider", "cell-outsider"
        )
        with (
            tenant_scope(None, tenant_id="tenant-outsider", cell_id="cell-outsider"),
            pytest.raises(ArtifactOwnershipError),
        ):
            read_core_json_artifact(foreign_store, selected_ref)

        sibling_ledger_ref = ArtifactID(sibling["prompt_tool_ledger_ref"])
        sibling_ledger = _owner_manifest(sibling_ledger_ref)
        sibling_claims_edge = next(
            item for item in sibling_ledger.inputs if item.role == "variant_final_policy_claims"
        )
        assert sibling_claims_edge.artifact_id == selected_ref.artifact_id
        assert sibling_claims_edge.manifest_profile_sha256 == sibling_ref.manifest_profile_sha256
        assert sibling_claims_edge.manifest_profile_sha256 != selected_ref.manifest_profile_sha256

        indexed_ref = ArtifactRef.model_validate(payload["artifacts_index"]["final_policy_claims"])
        assert indexed_ref == selected_ref
        citation_ref = result["citation_faithfulness_report_ref"]
        citation_manifest = _owner_manifest(ArtifactID(citation_ref))
        citation_inputs = [
            item for item in citation_manifest.inputs if item.role == "final_policy_claims"
        ]
        assert len(citation_inputs) == 1
        assert citation_inputs[0].artifact_id == selected_ref.artifact_id
        assert citation_inputs[0].manifest_profile_sha256 == selected_ref.manifest_profile_sha256

        grounding_payload = from_canonical_bytes(
            _owner_bytes(ArtifactID(result["policy_grounding_matrix_ref"]))
        )
        selected_grounding_variant = next(
            variant
            for variant in grounding_payload["model_variants"]
            if variant["model_variant_id"] == selected_variant_id
        )
        assert (
            ArtifactRef.model_validate(
                selected_grounding_variant["final_policy_claims_selected_ref"]
            )
            == selected_ref
        )
    finally:
        service.close()
