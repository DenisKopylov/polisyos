"""Bounded policy translator worker and deterministic compliance pass."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.common.serialization import extract_llm_json_object
from polisyos.core.artifacts import ArtifactStore, ArtifactWriteOptions
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.search.readiness import DecisionReadinessContract
from polisyos.scientist.orchestration.engine.budget import BudgetState
from polisyos.scientist.orchestration.llm._translator_materialization import (
    TRANSLATOR_INPUT_KIND,
    TRANSLATOR_ROLES,
    TranslatorMaterialization,
    translator_materialization_scope,
)
from polisyos.scientist.orchestration.llm.budget_enforcer import LLMBudgetEnforcer
from polisyos.scientist.orchestration.llm.factory import create_traced_gateway_client
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


class PolicyTranslatorConfig(BaseModel):
    """LLM budget and fallback settings for translating policy dossiers into delivery-ready text."""

    model_config = ConfigDict(extra="forbid")

    model_name: str = "gpt-5.4"
    provider_hint: str | None = None
    max_tokens: int = Field(default=1800, ge=256, le=4000)
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    budget_keys: list[str] = Field(default_factory=lambda: ["policy_translator", "policy_briefing"])
    fallback_on_error: bool = True


class TranslatorInputBundle(BaseModel):
    """Joined evidence pack handed to the translator and its compliance checks."""

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


def _translator_payload(bundle: TranslatorInputBundle) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for role in TRANSLATOR_ROLES:
        value = getattr(bundle, role)
        payload[role] = value.model_dump(mode="json") if value is not None else None
    return payload


def materialize_translator_inputs(
    store: ArtifactStore, bundle: TranslatorInputBundle
) -> TranslatorMaterialization:
    """Persist the actual finite translator inputs as selected CAS views.

    Args:
        store: The CAS owner that writes and later reads each selected view.
        bundle: The exact candidate input to the translator.

    Returns:
        A materialization for an optional scoped reuse attempt. It confers no
        current permission or authority: the cache checks the actual call and
        a current authorizer independently admits the selected evidence.
    """
    payload = _translator_payload(bundle)
    role_refs: list[tuple[str, ArtifactRef | None]] = []
    for role in TRANSLATOR_ROLES:
        value = payload[role]
        if value is None:
            if role != "implementation_plan":
                raise ValueError("translator_required_input_missing")
            role_refs.append((role, None))
            continue
        content = json.dumps(
            {"role": role, "value": value},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        ref = store.put_bytes(
            content,
            ArtifactWriteOptions(kind=TRANSLATOR_INPUT_KIND, media_type="application/json"),
            return_selected_profile=True,
        )
        role_refs.append((role, ref))
    return TranslatorMaterialization(store=store, role_refs=tuple(role_refs))


class TranslatorComplianceFinding(BaseModel):
    """Translator compliance finding public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: str = Field(default="blocker", min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TranslatorComplianceResult(BaseModel):
    """Outcome of translator compliance checks over the generated policy brief or bundle."""

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

    async def translate_async(
        self,
        bundle: TranslatorInputBundle,
        *,
        materialization: TranslatorMaterialization | None = None,
    ) -> PolicyBrief:
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

        payload = _translator_payload(bundle)
        try:
            with translator_materialization_scope(materialization):
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

    def translate(
        self,
        bundle: TranslatorInputBundle,
        *,
        materialization: TranslatorMaterialization | None = None,
    ) -> PolicyBrief:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.translate_async(bundle, materialization=materialization))
        return self._fallback.translate(bundle)

    async def translate_and_persist_async(
        self,
        store: FileSystemCAS,
        bundle: TranslatorInputBundle,
        *,
        inputs: list[InputRef] | None = None,
        materialization: TranslatorMaterialization | None = None,
    ) -> tuple[PolicyBrief, ArtifactRef]:
        brief = await self.translate_async(bundle, materialization=materialization)
        ref = persist_policy_brief(store, brief, inputs=inputs)
        return brief, ref

    def translate_and_persist(
        self,
        store: FileSystemCAS,
        bundle: TranslatorInputBundle,
        *,
        inputs: list[InputRef] | None = None,
        materialization: TranslatorMaterialization | None = None,
    ) -> tuple[PolicyBrief, ArtifactRef]:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.translate_and_persist_async(
                    store, bundle, inputs=inputs, materialization=materialization
                )
            )
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
            if uncertainty_type not in " ".join(brief.uncertainty_highlights).lower()
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
        described_harms = {_normalize_text(item) for item in brief.subgroup_harms} | {
            _normalize_text(risk.description) for risk in brief.risks
        }
        missing_harms = [
            label for label in harmed_labels if _normalize_text(label) not in described_harms
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
    return dict(extract_llm_json_object(str(raw)))


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
    "TranslatorMaterialization",
    "materialize_translator_inputs",
]
