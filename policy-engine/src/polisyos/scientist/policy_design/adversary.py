"""Bounded scenario adversary for policy robustness evaluation."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.scientist.autotune.models import BenchmarkSplitManifest
from polisyos.scientist.backtesting.adversarial import AdversarialGenerator
from polisyos.scientist.doe.designs import (
    AdversarialPlan,
    AdversarialStrategy,
    ParameterSpec as DOEParameterSpec,
    ScenarioSweep,
)
from polisyos.scientist.doe.stress_report import StressTestReport
from polisyos.scientist.engine.budget import BudgetState
from polisyos.scientist.llm.budget_enforcer import LLMBudgetEnforcer
from polisyos.scientist.llm.factory import create_traced_gateway_client
from polisyos.scientist.policy_design.prompts import (
    build_policy_adversary_user_payload,
    get_policy_adversary_prompt,
)
from polisyos.scientist.search.adversarial import run_stress_test
from polisyos.scientist.search.objective import CompositeObjective


class ScenarioAttackSurface(BaseModel):
    """Scenario attack surface public type."""
    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1)
    parameter_specs: list[DOEParameterSpec] = Field(default_factory=list)
    base_metrics: dict[str, list[float]] = Field(default_factory=dict)
    benchmark_split_manifest: BenchmarkSplitManifest | None = None
    vulnerability_threshold: float | None = None
    notes: list[str] = Field(default_factory=list)


class AdversarialScenarioProposal(BaseModel):
    """Adversarial scenario proposal public type."""
    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(min_length=1)
    scenario_type: str = Field(min_length=1)
    target_split: str = Field(default="both", pattern="^(selection_only|hidden_holdout_only|both)$")
    parameter_name: str | None = None
    intensity: float = Field(default=0.2, ge=0.0, le=1.0)
    rationale: str = Field(default="", max_length=500)


class AdversarialScenarioBundle(BaseModel):
    """Scenario pack describing the adversarial probes prepared for a policy candidate."""
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    candidate_id: str = Field(min_length=1)
    scenarios: list[AdversarialScenarioProposal] = Field(default_factory=list)
    fallback_used: bool = False
    scenario_sweep: ScenarioSweep = Field(default_factory=ScenarioSweep)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScenarioAdversaryConfig(BaseModel):
    """Budget, sampling, and fallback controls for the LLM-assisted policy adversary."""
    model_config = ConfigDict(extra="forbid")

    model_name: str = "gpt-5.4"
    provider_hint: str | None = None
    max_tokens: int = Field(default=1200, ge=256, le=4000)
    max_calls: int = Field(default=1, ge=1, le=5)
    max_scenarios: int = Field(default=5, ge=1, le=20)
    collect_top_k: int = Field(default=5, ge=1, le=20)
    budget_keys: list[str] = Field(default_factory=lambda: ["policy_adversary"])
    strategy: AdversarialStrategy = AdversarialStrategy.SEARCH_LOOP
    fallback_on_error: bool = True


class AdversaryExecutionResult(BaseModel):
    """Result bundle returned after scenario proposal, DOE compilation, and stress execution."""
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    scenario_bundle: AdversarialScenarioBundle
    compiled_plan: AdversarialPlan
    stress_test_report: StressTestReport
    stress_test_report_ref: ArtifactRef | None = None
    adversary_bundle_ref: ArtifactRef | None = None


class ScenarioAdversaryWorker:
    """LLM-assisted scenario proposer with deterministic execution."""

    def __init__(self, config: ScenarioAdversaryConfig | None = None) -> None:
        self._config = config or ScenarioAdversaryConfig()

    async def propose_async(
        self,
        surface: ScenarioAttackSurface,
        *,
        run_id: str = "policy_adversary",
        budget_state: BudgetState | None = None,
    ) -> AdversarialScenarioBundle:
        client = create_traced_gateway_client(
            model_name=self._config.model_name,
            provider_hint=self._config.provider_hint,
            run_id=run_id,
        )
        if client is None:
            return self._fallback_bundle(surface)

        llm_client: Any = client
        if budget_state is not None:
            llm_client = LLMBudgetEnforcer(
                client=client,
                budget_state=budget_state,
                budget_keys=list(self._config.budget_keys),
                model_name=self._config.model_name,
                run_id=run_id,
            )
        try:
            response = await llm_client.generate(
                system=get_policy_adversary_prompt(),
                user=build_policy_adversary_user_payload(
                    {
                        "candidate_id": surface.candidate_id,
                        "parameter_specs": [
                            item.model_dump(mode="json")
                            for item in surface.parameter_specs[: self._config.max_scenarios]
                        ],
                        "split_manifest": (
                            surface.benchmark_split_manifest.model_dump(mode="json")
                            if surface.benchmark_split_manifest is not None
                            else None
                        ),
                    }
                ),
                response_format={"type": "json_object"},
                max_tokens=self._config.max_tokens,
                temperature=0.1,
                _run_id=run_id,
            )
            payload = _parse_json_object(getattr(response, "content", response))
            proposals = [
                AdversarialScenarioProposal.model_validate(item)
                for item in payload.get("scenarios", [])[: self._config.max_scenarios]
                if isinstance(item, dict)
            ]
            if not proposals:
                return self._fallback_bundle(surface)
            return self._build_bundle(surface, proposals, fallback_used=False)
        except Exception:
            if not self._config.fallback_on_error:
                raise
            return self._fallback_bundle(surface)

    def propose(
        self,
        surface: ScenarioAttackSurface,
        *,
        run_id: str = "policy_adversary",
        budget_state: BudgetState | None = None,
    ) -> AdversarialScenarioBundle:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.propose_async(surface, run_id=run_id, budget_state=budget_state)
            )
        return self._fallback_bundle(surface)

    def compile_plan(
        self,
        surface: ScenarioAttackSurface,
        bundle: AdversarialScenarioBundle,
    ) -> AdversarialPlan:
        referenced_parameters = {
            proposal.parameter_name
            for proposal in bundle.scenarios
            if proposal.parameter_name is not None
        }
        parameter_specs = [
            spec
            for spec in surface.parameter_specs
            if not referenced_parameters or spec.name in referenced_parameters
        ]
        if not parameter_specs:
            parameter_specs = list(surface.parameter_specs)
        return AdversarialPlan(
            parameter_specs=parameter_specs[: max(1, self._config.max_scenarios)],
            strategy=self._config.strategy,
            vulnerability_threshold=surface.vulnerability_threshold,
            collect_top_k=self._config.collect_top_k,
            max_iterations=max(10, len(parameter_specs) * 8),
        )

    def execute(
        self,
        *,
        surface: ScenarioAttackSurface,
        base_objective: CompositeObjective,
        stage_b_evaluator: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
        candidate_generator: object | None = None,
        context: dict[str, Any] | None = None,
        cas: FileSystemCAS | None = None,
        run_id: str = "policy_adversary",
        budget_state: BudgetState | None = None,
        decision_packet_ref: str | None = None,
    ) -> AdversaryExecutionResult:
        bundle = self.propose(surface, run_id=run_id, budget_state=budget_state)
        plan = self.compile_plan(surface, bundle)
        stress_report = run_stress_test(
            adversarial_plan=plan,
            base_objective=base_objective,
            stage_b_evaluator=stage_b_evaluator,
            candidate_generator=candidate_generator,
            context=context,
            cas=cas,
            decision_packet_ref=decision_packet_ref,
        )
        bundle_ref = None
        if cas is not None:
            bundle_ref = persist_adversarial_scenario_bundle(
                cas,
                bundle,
                inputs=[InputRef(artifact_id=decision_packet_ref, role="decision_packet")]
                if decision_packet_ref
                else None,
            )
        report_ref = None
        if stress_report.cas_artifact_id is not None:
            report_ref = ArtifactRef(
                artifact_id=stress_report.cas_artifact_id,
                kind="scientist.stress_test_report",
                media_type="application/json",
            )
        return AdversaryExecutionResult(
            scenario_bundle=bundle,
            compiled_plan=plan,
            stress_test_report=stress_report,
            stress_test_report_ref=report_ref,
            adversary_bundle_ref=bundle_ref,
        )

    def _fallback_bundle(self, surface: ScenarioAttackSurface) -> AdversarialScenarioBundle:
        proposals: list[AdversarialScenarioProposal] = []
        scenario_types = [
            "shift",
            "noise",
            "outlier",
            "missing",
            "targeting_fragility",
        ]
        for index, spec in enumerate(surface.parameter_specs[: self._config.max_scenarios]):
            scenario_type = scenario_types[index % len(scenario_types)]
            target_split = "both"
            if surface.benchmark_split_manifest is not None and index % 2 == 1:
                target_split = "hidden_holdout_only"
            proposals.append(
                AdversarialScenarioProposal(
                    scenario_id=f"adv_{scenario_type}_{index + 1}",
                    scenario_type=scenario_type,
                    target_split=target_split,
                    parameter_name=spec.name,
                    intensity=0.2 + (0.1 * (index % 3)),
                    rationale=f"Fallback {scenario_type} stress on parameter '{spec.name}'.",
                )
            )
        return self._build_bundle(surface, proposals, fallback_used=True)

    def _build_bundle(
        self,
        surface: ScenarioAttackSurface,
        proposals: list[AdversarialScenarioProposal],
        *,
        fallback_used: bool,
    ) -> AdversarialScenarioBundle:
        generator = AdversarialGenerator(seed=42)
        preview_scenarios: list[dict[str, Any]] = []
        if surface.base_metrics:
            for proposal in proposals[:3]:
                if proposal.scenario_type == "shift":
                    scenario = generator.generate_shift(
                        surface.base_metrics,
                        scenario_id=proposal.scenario_id,
                        shift_fraction=proposal.intensity,
                    )
                elif proposal.scenario_type == "noise":
                    scenario = generator.generate_noise(
                        surface.base_metrics,
                        scenario_id=proposal.scenario_id,
                        noise_scale=proposal.intensity,
                    )
                elif proposal.scenario_type == "outlier":
                    scenario = generator.generate_outliers(
                        surface.base_metrics,
                        scenario_id=proposal.scenario_id,
                        outlier_fraction=max(0.05, proposal.intensity / 2.0),
                    )
                else:
                    scenario = generator.generate_missing(
                        surface.base_metrics,
                        scenario_id=proposal.scenario_id,
                        missing_fraction=max(0.05, proposal.intensity / 2.0),
                    )
                preview_scenarios.append(
                    {
                        "scenario_id": scenario.scenario_id,
                        "perturbation_type": scenario.perturbation_type,
                        "perturbation_magnitude": scenario.perturbation_magnitude,
                    }
                )
        sweep = ScenarioSweep(
            scenarios=[
                {
                    "scenario_id": proposal.scenario_id,
                    "scenario_type": proposal.scenario_type,
                    "target_split": proposal.target_split,
                    "parameter_name": proposal.parameter_name,
                    "intensity": proposal.intensity,
                }
                for proposal in proposals
            ]
        )
        return AdversarialScenarioBundle(
            candidate_id=surface.candidate_id,
            scenarios=proposals,
            fallback_used=fallback_used,
            scenario_sweep=sweep,
            metadata={"preview_scenarios": preview_scenarios},
        )


def persist_adversarial_scenario_bundle(
    store: FileSystemCAS,
    bundle: AdversarialScenarioBundle,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist the adversarial scenario bundle so robustness probes can be replayed later."""
    return store.put_json(
        bundle,
        PutOptions(
            kind="scientist.policy_adversary_bundle",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.policy_design.AdversarialScenarioBundle",
                version=bundle.schema_version,
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_adversarial_scenario_bundle(
    store: FileSystemCAS,
    ref: ArtifactRef,
) -> AdversarialScenarioBundle:
    """Load adversarial scenario bundle."""
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return AdversarialScenarioBundle.model_validate(payload)


def _parse_json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    payload = json.loads(str(raw).strip())
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object from adversary worker")
    return payload


__all__ = [
    "AdversarialScenarioBundle",
    "AdversarialScenarioProposal",
    "AdversaryExecutionResult",
    "ScenarioAdversaryConfig",
    "ScenarioAdversaryWorker",
    "ScenarioAttackSurface",
    "load_adversarial_scenario_bundle",
    "persist_adversarial_scenario_bundle",
]
