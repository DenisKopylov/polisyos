"""Bounded policy translator worker and deterministic compliance pass."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.engine.budget import BudgetState
from polisyos.scientist.llm.budget_enforcer import LLMBudgetEnforcer
from polisyos.scientist.llm.factory import create_traced_gateway_client
from polisyos.scientist.policy_design.output import (
    ChampionPolicyDossier,
    ConstraintSatisfactionReport,
    ImplementationPlan,
    PolicyBrief,
    PolicyRiskNote,
    RecommendedAction,
    SubgroupImpactReport,
    TradeoffRow,
    UncertaintyReport,
    persist_policy_brief,
)
from polisyos.scientist.policy_design.prompts import (
    build_policy_translator_user_payload,
    get_policy_translator_prompt,
)
from polisyos.scientist.search.readiness import DecisionReadinessContract


class PolicyTranslatorConfig(BaseModel):
    """Policy translator config data model."""
    model_config = ConfigDict(extra="forbid")

    model_name: str = "gpt-5.4"
    provider_hint: str | None = None
    max_tokens: int = Field(default=1800, ge=256, le=4000)
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    budget_keys: list[str] = Field(
        default_factory=lambda: ["policy_translator", "policy_briefing"]
    )
    fallback_on_error: bool = True


class TranslatorInputBundle(BaseModel):
    """Translator input bundle data model."""
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    dossier: ChampionPolicyDossier
    readiness_contract: DecisionReadinessContract
    constraint_report: ConstraintSatisfactionReport
    subgroup_report: SubgroupImpactReport
    uncertainty_report: UncertaintyReport
    implementation_plan: ImplementationPlan | None = None
    budget_state: BudgetState | None = None
    run_id: str = Field(default="policy_translator", min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TranslatorComplianceFinding(BaseModel):
    """Translator compliance finding public type."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: str = Field(default="blocker", min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TranslatorComplianceResult(BaseModel):
    """Translator compliance result data model."""
    model_config = ConfigDict(extra="forbid")

    passed: bool
    findings: list[TranslatorComplianceFinding] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeterministicPolicyTranslator:
    """Structured fallback translator that never invents facts."""

    def translate(self, bundle: TranslatorInputBundle) -> PolicyBrief:
        subgroup_harms = [entry.label for entry in bundle.subgroup_report.harmed_subgroups]
        tradeoffs = [
            TradeoffRow(
                axis=name,
                champion_value=f"{value:.4f}",
                rationale=f"Technical objective {name} is {value:.4f} in the dossier.",
            )
            for name, value in sorted(bundle.dossier.objective_summary.items())
        ]
        uncertainty_highlights = [
            f"{name}: {value:.3f}"
            for name, value in sorted(bundle.uncertainty_report.uncertainties.items())
        ]
        risks = [
            PolicyRiskNote(
                title="Subgroup harm",
                severity="warning",
                description=f"Potential negative effect on subgroup '{label}'.",
                impacted_groups=[label],
            )
            for label in subgroup_harms
        ]
        risks.extend(
            PolicyRiskNote(
                title="Surfaced assumption",
                severity="warning",
                description=text,
                surfaced_assumptions=[text],
            )
            for text in bundle.readiness_contract.assumptions_must_be_surfaced[:5]
        )
        for source_name, source_status in sorted(
            (bundle.readiness_contract.metadata.get("cross_graph_source_statuses") or {}).items()
        ):
            if source_status == "available":
                continue
            risks.append(
                PolicyRiskNote(
                    title="Evidence channel unavailable",
                    severity="warning",
                    description=(
                        f"Cross-graph evidence source '{source_name}' is unavailable ({source_status})."
                    ),
                )
            )
        if bundle.readiness_contract.metadata.get("prior_knowledge_status") not in {None, "ok"}:
            risks.append(
                PolicyRiskNote(
                    title="Academic support unavailable",
                    severity="warning",
                    description=(
                        "Academic prior support is unavailable or degraded, which limits readiness depth."
                    ),
                )
            )
        hard_constraint_notes = [
            entry.constraint_name
            for entry in bundle.constraint_report.constraints
            if entry.status in {"near_binding", "violated"}
        ]
        recommended_actions = list(bundle.dossier.recommended_actions)
        if not recommended_actions and bundle.implementation_plan is not None:
            recommended_actions = list(bundle.implementation_plan.recommended_actions)
        if not recommended_actions:
            recommended_actions = [
                RecommendedAction(
                    title="Review rollout safeguards",
                    description="Confirm monitoring and rollback triggers before deployment.",
                    priority="high",
                )
            ]
        return PolicyBrief(
            title=f"Policy brief for {bundle.dossier.candidate_id}",
            audience="decision_maker",
            executive_summary=bundle.dossier.executive_summary,
            readiness_level=bundle.readiness_contract.readiness_level.value,
            surfaced_assumptions=list(bundle.readiness_contract.assumptions_must_be_surfaced),
            uncertainty_highlights=uncertainty_highlights,
            subgroup_harms=subgroup_harms,
            hard_constraint_notes=hard_constraint_notes,
            tradeoffs=tradeoffs,
            risks=risks,
            recommended_actions=recommended_actions,
            metadata={"translator_mode": "deterministic"},
        )


class PolicyTranslatorWorker:
    """Gateway-backed translator with deterministic fallback."""

    def __init__(
        self,
        config: PolicyTranslatorConfig | None = None,
        *,
        fallback: DeterministicPolicyTranslator | None = None,
    ) -> None:
        self._config = config or PolicyTranslatorConfig()
        self._fallback = fallback or DeterministicPolicyTranslator()

    async def translate_async(self, bundle: TranslatorInputBundle) -> PolicyBrief:
        client = create_traced_gateway_client(
            model_name=self._config.model_name,
            provider_hint=self._config.provider_hint,
            run_id=bundle.run_id,
        )
        if client is None:
            return self._fallback.translate(bundle)

        llm_client: Any = client
        if bundle.budget_state is not None:
            llm_client = LLMBudgetEnforcer(
                client=client,
                budget_state=bundle.budget_state,
                budget_keys=list(self._config.budget_keys),
                model_name=self._config.model_name,
                run_id=bundle.run_id,
            )

        payload = {
            "dossier": bundle.dossier.model_dump(mode="json"),
            "readiness_contract": bundle.readiness_contract.model_dump(mode="json"),
            "constraint_report": bundle.constraint_report.model_dump(mode="json"),
            "subgroup_report": bundle.subgroup_report.model_dump(mode="json"),
            "uncertainty_report": bundle.uncertainty_report.model_dump(mode="json"),
            "implementation_plan": (
                bundle.implementation_plan.model_dump(mode="json")
                if bundle.implementation_plan is not None
                else None
            ),
        }
        try:
            response = await llm_client.generate(
                system=get_policy_translator_prompt(),
                user=build_policy_translator_user_payload(payload),
                response_format={"type": "json_object"},
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
                _run_id=bundle.run_id,
            )
            raw = getattr(response, "content", response)
            return PolicyBrief.model_validate(_parse_json_object(raw))
        except Exception:
            if not self._config.fallback_on_error:
                raise
            return self._fallback.translate(bundle)

    def translate(self, bundle: TranslatorInputBundle) -> PolicyBrief:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.translate_async(bundle))
        return self._fallback.translate(bundle)

    async def translate_and_persist_async(
        self,
        store: FileSystemCAS,
        bundle: TranslatorInputBundle,
        *,
        inputs: list[InputRef] | None = None,
    ) -> tuple[PolicyBrief, ArtifactRef]:
        brief = await self.translate_async(bundle)
        ref = persist_policy_brief(store, brief, inputs=inputs)
        return brief, ref

    def translate_and_persist(
        self,
        store: FileSystemCAS,
        bundle: TranslatorInputBundle,
        *,
        inputs: list[InputRef] | None = None,
    ) -> tuple[PolicyBrief, ArtifactRef]:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.translate_and_persist_async(store, bundle, inputs=inputs))
        brief = self._fallback.translate(bundle)
        ref = persist_policy_brief(store, brief, inputs=inputs)
        return brief, ref


class TranslatorCompliancePass:
    """Deterministic anti-spin validation for translated briefs."""

    def evaluate(
        self,
        brief: PolicyBrief,
        *,
        dossier: ChampionPolicyDossier,
        readiness_contract: DecisionReadinessContract,
        constraint_report: ConstraintSatisfactionReport,
        subgroup_report: SubgroupImpactReport,
        uncertainty_report: UncertaintyReport,
    ) -> TranslatorComplianceResult:
        findings: list[TranslatorComplianceFinding] = []

        if brief.readiness_level != readiness_contract.readiness_level.value:
            findings.append(
                TranslatorComplianceFinding(
                    code="readiness_overstated",
                    message=(
                        "Policy brief readiness level does not match DecisionReadinessContract."
                    ),
                    metadata={
                        "expected": readiness_contract.readiness_level.value,
                        "observed": brief.readiness_level,
                    },
                )
            )

        missing_assumptions = [
            item
            for item in readiness_contract.assumptions_must_be_surfaced
            if _normalize_text(item)
            not in {_normalize_text(value) for value in brief.surfaced_assumptions}
        ]
        if missing_assumptions:
            findings.append(
                TranslatorComplianceFinding(
                    code="assumptions_omitted",
                    message="Brief omitted surfaced assumptions required by readiness contract.",
                    metadata={"missing": missing_assumptions},
                )
            )

        missing_uncertainty_types = [
            uncertainty_type
            for uncertainty_type in uncertainty_report.uncertainties
            if uncertainty_type
            not in " ".join(brief.uncertainty_highlights).lower()
        ]
        if missing_uncertainty_types:
            findings.append(
                TranslatorComplianceFinding(
                    code="uncertainty_collapsed",
                    message="Brief collapsed or omitted typed uncertainty categories.",
                    metadata={"missing_uncertainty_types": missing_uncertainty_types},
                )
            )

        harmed_labels = {entry.label for entry in subgroup_report.harmed_subgroups}
        described_harms = {
            _normalize_text(item) for item in brief.subgroup_harms
        } | {
            _normalize_text(risk.description) for risk in brief.risks
        }
        missing_harms = [
            label
            for label in harmed_labels
            if _normalize_text(label) not in described_harms
        ]
        if missing_harms:
            findings.append(
                TranslatorComplianceFinding(
                    code="negative_harm_omitted",
                    message="Brief omitted known negative subgroup harms.",
                    metadata={"missing_harms": missing_harms},
                )
            )

        binding_constraints = [
            entry.constraint_name
            for entry in constraint_report.constraints
            if entry.status in {"near_binding", "violated"}
        ]
        noted_constraints = {_normalize_text(item) for item in brief.hard_constraint_notes}
        missing_constraints = [
            name for name in binding_constraints if _normalize_text(name) not in noted_constraints
        ]
        if missing_constraints:
            findings.append(
                TranslatorComplianceFinding(
                    code="binding_constraints_omitted",
                    message="Brief omitted binding or near-binding hard constraints.",
                    metadata={"missing_constraints": missing_constraints},
                )
            )

        if _normalize_text(dossier.executive_summary) not in _normalize_text(
            brief.executive_summary
        ) and _normalize_text(brief.executive_summary) not in _normalize_text(
            dossier.executive_summary
        ):
            findings.append(
                TranslatorComplianceFinding(
                    code="dossier_summary_drift",
                    message="Brief executive summary drifted materially from technical dossier.",
                )
            )

        return TranslatorComplianceResult(
            passed=not findings,
            findings=findings,
            metadata={
                "risk_count": len(brief.risks),
                "tradeoff_count": len(brief.tradeoffs),
            },
        )


def _parse_json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    text = str(raw).strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValidationError.from_exception_data(
            "PolicyBrief",
            [{"loc": ("root",), "msg": "Expected JSON object", "type": "value_error"}],
        )
    return payload


def _normalize_text(value: str) -> str:
    return " ".join(str(value).strip().lower().split())


__all__ = [
    "DeterministicPolicyTranslator",
    "PolicyBrief",
    "PolicyRiskNote",
    "PolicyTranslatorConfig",
    "PolicyTranslatorWorker",
    "RecommendedAction",
    "TradeoffRow",
    "TranslatorComplianceFinding",
    "TranslatorCompliancePass",
    "TranslatorComplianceResult",
    "TranslatorInputBundle",
]
