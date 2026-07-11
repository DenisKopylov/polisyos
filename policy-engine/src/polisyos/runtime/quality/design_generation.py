"""Shadow-only design generation under A using the existing LLM organs.

N4 is a proposer bridge, not an authority path. It calls the real Scientist
drafter/formalizer/critic organs, content-binds their Trinity output to N2
``InterventionAtomBinding`` candidates, and fails closed whenever generation
degrades to fixtures, unsupported models, untyped JSON, or unbound content.
"""

from __future__ import annotations

import ast
import asyncio
import importlib
import inspect
import json
import os
import re
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.common.llm_json import extract_llm_json
from polisyos.ir.analytics.interventions import (
    InterventionContext,
    NodeIntervention,
    QueryTarget,
    VariableAssignment,
    identification_plan_for_intervention,
)
from polisyos.ir.governance import InterventionSpec, ScheduleSpec
from polisyos.ir.linker import LinkedIntervention, link_trinity
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.credal_reference import CredalReference, build_credal_reference
from polisyos.runtime.quality.grounding_active_controller import (
    GroundingActionCertificate,
    GroundingActiveController,
    GroundingControllerCase,
)
from polisyos.runtime.quality.grounding_admission import (
    GroundingAdmissionCertificate,
    GroundingAdmissionEngine,
)
from polisyos.runtime.quality.grounding_bind import (
    GroundingBindGate,
    GroundingDecisionCertificate,
)
from polisyos.runtime.quality.grounding_disposition_vocab import GroundingDispositionKind
from polisyos.runtime.quality.grounding_phrasing_defense import (
    GroundingPhrasingDefenseEngine,
    GroundingProxyGapRisk,
    QuarantineHandoffRecord,
)
from polisyos.runtime.quality.grounding_relation import (
    GroundingRelationCertificate,
    GroundingRelationEngine,
    parse_n4_proposal,
)
from polisyos.runtime.quality.intervention_atom_binding import (
    InterventionAtomBinding,
    build_intervention_atom_binding,
    consume_intervention_atom_for_cycle,
    intervention_atom_target_selector_ref,
)
from polisyos.runtime.quality.intervention_substrate import (
    InterventionSubstrateError,
    intervention_generation_registry_bundle,
    load_l6_intervention_substrate,
    production_composed_world_model_record,
)
from polisyos.runtime.quality.world_model_record import resolve_intervention_atom_world_binding
from polisyos.scientist.agent.critic import create_critic_agent
from polisyos.scientist.agent.drafter_factory import create_drafter_agent
from polisyos.scientist.agent.drafter_models import MultiPassConfig
from polisyos.scientist.agent.formalizer import (
    LLMFormalizerAgent,
    trinity_bundle_formalizer_generator_path,
)

if TYPE_CHECKING:
    from polisyos.ir.trinity import TrinityBundle
    from polisyos.runtime.quality.design_problem import DesignProblem

DESIGN_GENERATION_SCHEMA_VERSION = "policyos.runtime.design_generation_under_a.v1"
DESIGN_GENERATION_CONTRACT_SCHEMA_VERSION = (
    "policyos.policy_design_case.layer3_gy.design_generation_contract.v1"
)
DESIGN_GENERATION_ARTIFACT_KIND = "runtime.quality.design_generation_under_a"
DESIGN_GENERATION_PRODUCER_REF = "polisyos.runtime.quality.design_generation"
SUPPORTED_GENERATION_MODEL_IDS: tuple[str, ...] = (
    "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
    "MiniMaxAI/MiniMax-M2.7",
    "moonshotai/Kimi-K2.6",
)
NOT_CERTIFICATE_KINDS: tuple[str, ...] = (
    "llm_explanation",
    "natural_language_rationale",
    "proxy_score",
    "surrogate_score",
    "unverified_simulation",
    "posterior_ci_without_coverage",
    "self_reported_causal_claim",
    "untyped_json",
    "degraded_mock_fallback",
    "unsupported_model",
)
_REAL_GENERATOR_PATH = "model_generated"
_DEGRADED_GENERATOR_PATH = "degraded_mock_fallback"
_SEARCH_SURROGATE_OWNERS = (
    "polisyos.foundry.methods.catalog.causal.ncm_engine.NCMEngineMethod",
    "polisyos.foundry.methods.catalog.causal.gcm_fit.HybridSCMFit",
    "polisyos.data_forge.domains.academic.knowledge.skg_query.SKGQuery",
    "polisyos.runtime.quality.intervention_substrate.load_l6_intervention_substrate",
)


GeneratorPath = Literal["model_generated", "degraded_mock_fallback"]
GenerationStatus = Literal["generated", "generation_unavailable", "preflight_rejected"]
PreflightStatus = Literal["supported", "unsupported", "gateway_unavailable"]
CandidateStatus = Literal["candidate_unverified"]
SurrogateTrustLevel = Literal[
    "proposal_only",
    "search_guiding",
    "calibrated_predictive",
    "certified",
]
AuthorityState = Literal[
    "candidate_unverified",
    "rejected_from_authority",
    "authority_requested",
    "promoted",
]
LeverSpaceSliceStatus = Literal["derived", "unavailable"]
LegacyLinkerDisposition = Literal["would_bind", "would_reject"]


class DesignGenerationError(ValueError):
    """Fail-closed design-generation error."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


class _StrictModel(BaseModel):
    """Strict immutable model for N4 runtime artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class LLMGenerationCall(_StrictModel):
    """Replay provenance for one model call consumed by the real organs."""

    call_index: int = Field(..., ge=0)
    role_hint: str | None = None
    status: Literal["success", "error"] = "success"
    model_id: str = Field(..., min_length=1)
    provider: str | None = None
    prompt_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    raw_llm_response: str = ""
    parsed_json: Any = None
    response_format: dict[str, Any] | None = None
    prompt_tokens: int = Field(0, ge=0)
    completion_tokens: int = Field(0, ge=0)
    total_tokens: int = Field(0, ge=0)
    wall_seconds: float = Field(0.0, ge=0.0)
    error_type: str | None = None
    error_message: str | None = None
    error_status: int | None = Field(None, ge=100, le=599)
    error_code: str | None = None
    retry_after_s: float | None = Field(None, ge=0.0)
    request_id: str | None = None
    cache_status: str | None = None
    cache_key: str | None = None


class ModelProfilePreflight(_StrictModel):
    """Model catalog preflight resolved against the gateway ``/models`` surface."""

    status: PreflightStatus
    model_id: str = Field(..., min_length=1)
    supported_model_ids: tuple[str, ...] = ()
    live_model_ids: tuple[str, ...] = ()
    reason: str = ""


class GenerationCandidateProvenance(_StrictModel):
    """Replayable provenance for one candidate atom."""

    model_id: str = Field(..., min_length=1)
    generator_path: GeneratorPath
    draft_generator_path: GeneratorPath
    formalizer_generator_path: GeneratorPath
    critic_generator_path: GeneratorPath
    prompt_hashes: tuple[str, ...]
    raw_llm_responses: tuple[str, ...]
    parsed_candidate: dict[str, Any]
    trinity_bundle_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")


class ShadowGeneratedCandidate(_StrictModel):
    """One N4 shadow candidate bound to an N2 atom."""

    candidate_id: str = Field(..., pattern=r"^candidate_[a-f0-9]{16}$")
    status: CandidateStatus = "candidate_unverified"
    generator_path: GeneratorPath
    atom: InterventionAtomBinding
    diversity_key: tuple[str, str, str, str]
    provenance: GenerationCandidateProvenance
    critique_verdict: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def _shadow_only(self) -> ShadowGeneratedCandidate:
        if self.status != "candidate_unverified":
            raise ValueError("generated_candidate_not_shadow")
        if self.generator_path != _REAL_GENERATOR_PATH:
            raise ValueError("generated_candidate_degraded")
        if self.atom.status != "candidate_unverified":
            raise ValueError("generated_atom_not_shadow")
        if self.atom.content_hash != self.provenance.content_hash:
            raise ValueError("candidate_atom_content_hash_mismatch")
        return self


class DegradedGenerationArtifact(_StrictModel):
    """Visible artifact for fixture fallback or unavailable generation."""

    generator_path: Literal["degraded_mock_fallback"] = _DEGRADED_GENERATOR_PATH
    reason: str = Field(..., min_length=1)
    organ: str = Field(..., min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)


class GenerationDiversityReport(_StrictModel):
    """Measured diversity over N2 atom features, not authored candidate counts."""

    min_required: int = Field(..., ge=1)
    candidate_count: int = Field(..., ge=0)
    unique_diversity_key_count: int = Field(..., ge=0)
    unique_operator_kinds: tuple[str, ...] = ()
    unique_target_selectors: tuple[str, ...] = ()
    unique_mechanisms: tuple[str, ...] = ()
    unique_parameterizations: tuple[str, ...] = ()
    diverse_enough: bool = False
    domain_mechanism_hardcode_detected: bool = False


class SurrogateRanking(_StrictModel):
    """Graph-causal search score that can prioritize but never certify in N4."""

    candidate_id: str = Field(..., min_length=1)
    trust_level: SurrogateTrustLevel
    score: float = Field(..., ge=0.0, le=1.0)
    voi_estimate: float = Field(..., ge=0.0)
    promotion_allowed: bool = False
    owner_refs: tuple[str, ...] = _SEARCH_SURROGATE_OWNERS
    feature_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _below_certified_cannot_promote(self) -> SurrogateRanking:
        if self.trust_level != "certified" and self.promotion_allowed:
            raise ValueError("surrogate_below_certified_promoted")
        return self


class FirewallEvidence(_StrictModel):
    """One non-certificate signal observed by the behavioral firewall."""

    evidence_kind: str = Field(..., min_length=1)
    authority_state: AuthorityState
    blocked_from_authority: bool
    reason: str = Field(..., min_length=1)


class LeverSpaceSliceEntry(_StrictModel):
    """One owner-derived lever row nudged into the generator prompt."""

    operator_kind: str = Field(..., min_length=1)
    aliases: tuple[str, ...] = ()
    target_world_slots: tuple[str, ...] = ()
    unit: str | None = None
    parameter_key: str | None = None
    parameter_bounds: dict[str, Any] = Field(default_factory=dict)
    sign_semantics: str | None = None
    expected_outcome_slots: tuple[str, ...] = ()
    effect_path: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


class LeverSpacePromptSlice(_StrictModel):
    """Hash-bound owner-derived prompt slice for N4 generation."""

    status: LeverSpaceSliceStatus
    content_hash: str | None = Field(None, pattern=r"^sha256:[0-9a-f]{64}$")
    entries: tuple[LeverSpaceSliceEntry, ...] = ()
    owner_refs: tuple[str, ...] = ()
    failure_reason: str | None = None
    non_constraining: bool = True

    @model_validator(mode="after")
    def _hash_status_consistent(self) -> LeverSpacePromptSlice:
        if self.status == "derived" and (not self.content_hash or not self.entries):
            raise ValueError("lever_space_prompt_slice_missing_hash_or_entries")
        if self.status == "unavailable" and self.entries:
            raise ValueError("unavailable_lever_space_slice_must_not_carry_entries")
        if not self.non_constraining:
            raise ValueError("lever_space_prompt_slice_must_be_non_constraining")
        return self


class GroundingCertificateChain(_StrictModel):
    """Certificate ids/hashes observed for one generated candidate."""

    cg1_certificate_id: str = Field(..., min_length=1)
    cg1_content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    cg2_certificate_id: str | None = None
    cg2_content_hash: str | None = Field(None, pattern=r"^sha256:[0-9a-f]{64}$")
    cg3_certificate_id: str | None = None
    cg3_content_hash: str | None = Field(None, pattern=r"^sha256:[0-9a-f]{64}$")
    cg4_proxy_gap_risk_id: str | None = None
    cg4_proxy_gap_content_hash: str | None = Field(None, pattern=r"^sha256:[0-9a-f]{64}$")
    cg4_quarantine_handoff_id: str | None = None
    cg4_quarantine_handoff_hash: str | None = Field(None, pattern=r"^sha256:[0-9a-f]{64}$")
    cg5_action_certificate_id: str | None = None
    cg5_action_content_hash: str | None = Field(None, pattern=r"^sha256:[0-9a-f]{64}$")
    cg5_ticket_id: str | None = None
    cg5_ticket_hash: str | None = Field(None, pattern=r"^sha256:[0-9a-f]{64}$")


class GroundingDispositionRecord(_StrictModel):
    """Full-denominator CGF disposition for one generated intervention candidate."""

    proposal_id: str = Field(..., min_length=1)
    candidate_id: str | None = Field(None, pattern=r"^candidate_[a-f0-9]{16}$")
    raw_candidate_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    disposition: GroundingDispositionKind
    status: CandidateStatus = "candidate_unverified"
    selected_relation: str = Field(..., min_length=1)
    identified_atom_id: str | None = None
    shadow_atom_content_hash: str | None = Field(None, pattern=r"^sha256:[0-9a-f]{64}$")
    cg2_decision: str | None = None
    cg2_reason: str | None = None
    cg3_decision: str | None = None
    cg3_reason: str | None = None
    rejected_cause: dict[str, Any] | None = None
    legacy_exact_match: LegacyLinkerDisposition
    legacy_linker_issues: tuple[dict[str, Any], ...] = ()
    certificate_chain: GroundingCertificateChain
    bridge_missing_records: tuple[dict[str, Any], ...] = ()

    @model_validator(mode="after")
    def _binding_requires_certificate_and_atom(self) -> GroundingDispositionRecord:
        if self.status != "candidate_unverified":
            raise ValueError("grounding_disposition_not_shadow")
        if self.disposition == "shadow_bound":
            if (
                not self.candidate_id
                or not self.shadow_atom_content_hash
                or not self.identified_atom_id
            ):
                raise ValueError("shadow_bound_disposition_missing_atom_or_certificate")
            if self.selected_relation not in {"exact", "certified-specialization"}:
                raise ValueError("shadow_bound_without_identifying_relation")
        if self.disposition != "shadow_bound" and (
            self.candidate_id or self.shadow_atom_content_hash
        ):
            raise ValueError("non_binding_disposition_carried_shadow_atom")
        return self


class GroundingDispositionSummary(_StrictModel):
    """Counted before/after payoff receipt for the recorded candidate set."""

    total_candidates: int = Field(..., ge=0)
    shadow_bound: int = Field(0, ge=0)
    novel_cg3: int = Field(0, ge=0)
    veto_false_analog: int = Field(0, ge=0)
    abstain_or_blocked: int = Field(0, ge=0)
    legacy_exact_match_would_bind: int = Field(0, ge=0)
    legacy_exact_match_would_reject: int = Field(0, ge=0)

    @model_validator(mode="after")
    def _full_denominator(self) -> GroundingDispositionSummary:
        if (
            self.shadow_bound
            + self.novel_cg3
            + self.veto_false_analog
            + self.abstain_or_blocked
            != self.total_candidates
        ):
            raise ValueError("grounding_disposition_counts_not_full_denominator")
        if self.legacy_exact_match_would_bind + self.legacy_exact_match_would_reject != (
            self.total_candidates
        ):
            raise ValueError("legacy_exact_match_counts_not_full_denominator")
        return self


class PromptSizeEstimate(_StrictModel):
    """Prompt-size receipt for the owner-derived lever slice."""

    frame_without_slice_chars: int = Field(0, ge=0)
    frame_with_slice_chars: int = Field(0, ge=0)
    slice_added_chars: int = Field(0, ge=0)
    frame_without_slice_estimated_tokens: int = Field(0, ge=0)
    frame_with_slice_estimated_tokens: int = Field(0, ge=0)
    slice_added_estimated_tokens: int = Field(0, ge=0)


class EffectiveGenerationRuntimeConfig(_StrictModel):
    """Effective timeout/retry/schema-normalization values recorded per N4 run."""

    drafter_pass_timeout_s: float = Field(..., gt=0.0)
    drafter_pass_retry_count: int = Field(..., ge=0)
    formalizer_timeout_s: float = Field(..., gt=0.0)
    formalizer_retry_count: int = Field(..., ge=0)
    critic_timeout_s: float = Field(..., gt=0.0)
    terminal_salvage_retry_count: int = Field(..., ge=0)
    terminal_salvage_backoff_base_s: float = Field(..., ge=0.0)
    gateway_timeout_s: float | None = Field(None, gt=0.0)
    gateway_max_retries: int | None = Field(None, ge=0)
    prompt_cache_ttl_s: float | None = Field(None, ge=0.0)
    prompt_cache_maxsize: int | None = Field(None, ge=0)
    cg1_index_prewarm_enabled: bool = False
    cg1_index_prewarm_wall_seconds: float | None = Field(None, ge=0.0)
    formalizer_schema_healing_events: tuple[dict[str, Any], ...] = ()
    streaming_status: Literal["not_wired_followup"] = "not_wired_followup"
    prompt_size_estimate: PromptSizeEstimate = Field(default_factory=PromptSizeEstimate)


class GenerationUnderAResult(_StrictModel):
    """Runtime artifact emitted by N4 generation under A."""

    schema_version: str = DESIGN_GENERATION_SCHEMA_VERSION
    artifact_kind: str = DESIGN_GENERATION_ARTIFACT_KIND
    status: GenerationStatus
    design_problem_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    model_id: str = Field(..., min_length=1)
    preflight: ModelProfilePreflight
    candidates: tuple[ShadowGeneratedCandidate, ...] = ()
    grounding_dispositions: tuple[GroundingDispositionRecord, ...] = ()
    grounding_disposition_summary: GroundingDispositionSummary = Field(
        default_factory=lambda: GroundingDispositionSummary(total_candidates=0)
    )
    effective_runtime_config: EffectiveGenerationRuntimeConfig | None = None
    lever_space_prompt_slice: LeverSpacePromptSlice = Field(
        default_factory=lambda: LeverSpacePromptSlice(
            status="unavailable",
            failure_reason="not_attempted",
        )
    )
    degraded_artifacts: tuple[DegradedGenerationArtifact, ...] = ()
    diversity_report: GenerationDiversityReport
    surrogate_rankings: tuple[SurrogateRanking, ...] = ()
    llm_calls: tuple[LLMGenerationCall, ...] = ()
    firewall_evidence: tuple[FirewallEvidence, ...] = ()
    strangle_receipts: tuple[dict[str, Any], ...] = ()

    @model_validator(mode="after")
    def _terminal_semantics(self) -> GenerationUnderAResult:
        if self.status != "generated" and self.candidates:
            raise ValueError("terminal_generation_must_not_emit_candidates")
        if self.status != "generated" and self.grounding_dispositions:
            raise ValueError("terminal_generation_must_not_emit_grounding_dispositions")
        if (
            self.status == "generated"
            and not self.diversity_report.diverse_enough
            and self.grounding_disposition_summary.total_candidates
            < self.diversity_report.min_required
        ):
            raise ValueError("generated_result_insufficient_diversity")
        if self.preflight.status != "supported" and self.status == "generated":
            raise ValueError("generated_result_without_supported_preflight")
        if self.status == "generated":
            if (
                self.grounding_disposition_summary.total_candidates
                != len(self.grounding_dispositions)
            ):
                raise ValueError("grounding_disposition_summary_denominator_mismatch")
            bound_ids = {candidate.candidate_id for candidate in self.candidates}
            disposition_ids = {
                item.candidate_id
                for item in self.grounding_dispositions
                if item.disposition == "shadow_bound"
            }
            if bound_ids != disposition_ids:
                raise ValueError("shadow_candidate_dispositions_mismatch")
        return self

    def as_organ_run(
        self,
        *,
        draft: object | None = None,
        trinity_bundle: TrinityBundle | None = None,
        critique: object | None = None,
    ) -> DesignGenerationOrganRun:
        """Wrap a terminal or successful result for canonical-path callers."""

        return DesignGenerationOrganRun(
            result=self,
            draft=draft,
            trinity_bundle=trinity_bundle,
            critique=critique,
        )


class RecordingLLMClient:
    """Thin replay wrapper that records prompt hashes and raw model responses."""

    def __init__(self, inner: object, *, model_id: str) -> None:
        self._inner = inner
        self._model_id = model_id
        self.calls: list[LLMGenerationCall] = []

    async def list_model_ids(self, *, timeout: float | None = None) -> list[str]:
        method = getattr(self._inner, "list_model_ids", None)
        if method is None:
            raise RuntimeError("llm_client_models_endpoint_missing")
        result = method(timeout=timeout)
        if inspect.isawaitable(result):
            result = await result
        return [str(item) for item in result]

    async def generate(self, **kwargs: object) -> object:
        prompt_hash = gy_content_hash(
            {
                "system": kwargs.get("system"),
                "user": kwargs.get("user"),
                "messages": kwargs.get("messages"),
                "response_format": kwargs.get("response_format"),
                "tools": kwargs.get("tools"),
                "tool_choice": kwargs.get("tool_choice"),
                "temperature": kwargs.get("temperature"),
                "max_tokens": kwargs.get("max_tokens"),
                "metadata": kwargs.get("metadata"),
            }
        )
        role_hint = _llm_role_hint(kwargs)
        started = time.monotonic()
        try:
            result = self._inner.generate(**kwargs)
            if inspect.isawaitable(result):
                response = await result
            else:
                response = result
        except BaseException as exc:
            details = _llm_exception_details(exc)
            self._record_call(
                LLMGenerationCall(
                    call_index=len(self.calls),
                    role_hint=role_hint,
                    status="error",
                    model_id=self._model_id,
                    prompt_hash=prompt_hash,
                    response_format=(
                        dict(kwargs["response_format"])
                        if isinstance(kwargs.get("response_format"), Mapping)
                        else None
                    ),
                    wall_seconds=max(0.0, time.monotonic() - started),
                    error_type=type(exc).__name__,
                    error_message=str(exc)[:1000],
                    error_status=details.get("error_status"),
                    error_code=details.get("error_code"),
                    retry_after_s=details.get("retry_after_s"),
                    request_id=details.get("request_id"),
                )
            )
            raise
        content = response.content if hasattr(response, "content") else str(response)
        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        total_tokens = int(
            getattr(usage, "total_tokens", 0)
            or (prompt_tokens + completion_tokens)
        )
        cache_info = _response_cache_info(response)
        self._record_call(
            LLMGenerationCall(
                call_index=len(self.calls),
                role_hint=role_hint,
                status="success",
                model_id=str(getattr(response, "model", None) or self._model_id),
                provider=getattr(response, "provider", None),
                prompt_hash=prompt_hash,
                raw_llm_response=content,
                parsed_json=_try_parse_json(content),
                response_format=(
                    dict(kwargs["response_format"])
                    if isinstance(kwargs.get("response_format"), Mapping)
                    else None
                ),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                wall_seconds=max(0.0, time.monotonic() - started),
                cache_status=cache_info.get("cache_status"),
                cache_key=cache_info.get("cache_key"),
            )
        )
        return response

    def _record_call(self, call: LLMGenerationCall) -> None:
        self.calls.append(call)
        _append_llm_call_journal(call)


def _llm_role_hint(kwargs: Mapping[str, object]) -> str | None:
    user = str(kwargs.get("user") or "")
    if "Generate a draft JSON object" in user:
        return "draft"
    if "Review the draft and return strict JSON with findings" in user:
        return "drafter_multipass"
    if "Integrate findings and return strict JSON" in user:
        return "drafter_consolidation"
    if "Generate a valid TrinityBundle" in user:
        return "formalizer"
    if "Provide your critique as a JSON object" in user:
        return "critic"
    return None


def _append_llm_call_journal(call: LLMGenerationCall) -> None:
    journal_path = os.getenv("POLISYOS_N4_CALL_JOURNAL_PATH", "").strip()
    if not journal_path:
        return
    path = Path(journal_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(call.model_dump(mode="json"), sort_keys=True) + "\n")
    except OSError:
        # Journaling is diagnostic-only; generation authority remains the in-memory call record.
        return


def _response_cache_info(response: object) -> dict[str, str]:
    raw = getattr(response, "raw", None)
    if not isinstance(raw, Mapping):
        return {}
    cache = raw.get("_polisyos_cache")
    if not isinstance(cache, Mapping):
        return {}
    info: dict[str, str] = {}
    status = cache.get("status")
    if isinstance(status, str) and status:
        info["cache_status"] = status
    key = cache.get("cache_key")
    if isinstance(key, str) and key:
        info["cache_key"] = key
    return info


def _llm_exception_details(exc: BaseException) -> dict[str, Any]:
    details: dict[str, Any] = {}
    current: BaseException | None = exc
    seen = 0
    while current is not None and seen < 8:
        status = getattr(current, "status", None)
        if isinstance(status, int):
            details.setdefault("error_status", status)
        error_code = getattr(current, "error_code", None)
        if isinstance(error_code, str) and error_code:
            details.setdefault("error_code", error_code)
        retry_after_s = getattr(current, "retry_after_s", None)
        if isinstance(retry_after_s, int | float):
            details.setdefault("retry_after_s", float(retry_after_s))
        request_id = getattr(current, "request_id", None)
        if isinstance(request_id, str) and request_id:
            details.setdefault("request_id", request_id)
        current = current.__cause__ or current.__context__
        seen += 1
    if "error_status" not in details:
        status = _error_status_from_message(str(exc))
        if status is not None:
            details["error_status"] = status
    return details


def _error_status_from_message(message: str) -> int | None:
    match = re.search(r"\b(?:status=|status |failed \()(?P<status>[1-5][0-9]{2})\b", message)
    if match:
        return int(match.group("status"))
    match = re.search(r"\b(?P<status>429|5[0-9]{2})\b", message)
    if match:
        return int(match.group("status"))
    return None


@dataclass(frozen=True)
class DesignGenerationOrganRun:
    """Internal bridge for callers that need the real organ artifacts."""

    result: GenerationUnderAResult
    draft: object | None = None
    trinity_bundle: TrinityBundle | None = None
    critique: object | None = None


async def preflight_model_profile(client: object, *, model_id: str) -> ModelProfilePreflight:
    """Fail closed unless ``model_id`` is returned by live gateway ``/models``."""

    catalog_fallback = tuple(SUPPORTED_GENERATION_MODEL_IDS)
    try:
        live = tuple(await client.list_model_ids(timeout=10.0))
    except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
        return ModelProfilePreflight(
            status="gateway_unavailable",
            model_id=model_id,
            supported_model_ids=catalog_fallback,
            reason=f"models_endpoint_unavailable:{type(exc).__name__}",
        )
    if model_id not in live:
        return ModelProfilePreflight(
            status="unsupported",
            model_id=model_id,
            supported_model_ids=live,
            live_model_ids=live,
            reason="model_profile_not_returned_by_gateway_models",
        )
    return ModelProfilePreflight(
        status="supported",
        model_id=model_id,
        supported_model_ids=live,
        live_model_ids=live,
        reason="model_profile_supported_by_gateway_models",
    )


async def generate_design_candidates_under_a(
    design_problem: DesignProblem,
    *,
    model_id: str,
    llm_client: object | None = None,
    repo_root: Path | None = None,
    min_diverse_candidates: int = 3,
    data_context: dict[str, Any] | None = None,
    world_model_record_ref: str | None = None,
) -> GenerationUnderAResult:
    """Generate shadow candidates by reusing the real LLM organs and N2 atom bridge."""

    organ_run = await generate_design_candidate_bundle_under_a(
        design_problem,
        model_id=model_id,
        llm_client=llm_client,
        repo_root=repo_root,
        min_diverse_candidates=min_diverse_candidates,
        data_context=data_context,
        world_model_record_ref=world_model_record_ref,
    )
    return organ_run.result


def _with_generation_cycle_revision_context(
    scientist_frame: object,
    *,
    design_problem: DesignProblem,
) -> object:
    """Bind N6 revision inputs into fields serialized by the real N4 prompt."""

    revision = design_problem.runtime_hints.get("generation_cycle_revision")
    if not isinstance(revision, Mapping):
        return scientist_frame
    source_counterexample_ref = str(revision.get("source_counterexample_ref") or "")
    previous_candidate_ref = str(revision.get("previous_candidate_ref") or "")
    raw_new_grammar = revision.get("new_grammar_elements")
    if isinstance(raw_new_grammar, str):
        new_grammar_elements = (raw_new_grammar,)
    elif isinstance(raw_new_grammar, Sequence):
        new_grammar_elements = tuple(str(item) for item in raw_new_grammar if str(item))
    else:
        new_grammar_elements = ()
    raw_grammar = design_problem.runtime_hints.get("generation_cycle_grammar")
    if isinstance(raw_grammar, str):
        grammar_elements = (raw_grammar,)
    elif isinstance(raw_grammar, Sequence):
        grammar_elements = tuple(str(item) for item in raw_grammar if str(item))
    else:
        grammar_elements = ()
    if not source_counterexample_ref or not new_grammar_elements:
        return scientist_frame
    revision_prompt_context = {
        "source_counterexample_ref": source_counterexample_ref,
        "previous_candidate_ref": previous_candidate_ref,
        "new_grammar_elements": list(new_grammar_elements),
        "active_grammar_elements": list(grammar_elements),
        "instruction": (
            "Revise the candidate generation in response to the named counterexample; "
            "do not repeat the previous candidate without introducing the new grammar."
        ),
    }
    success_criteria = dict(getattr(scientist_frame, "success_criteria", {}) or {})
    success_criteria["generation_cycle_revision"] = revision_prompt_context
    assumptions = (
        *tuple(getattr(scientist_frame, "assumptions", ()) or ()),
        "generation_cycle_revision:"
        + json.dumps(revision_prompt_context, sort_keys=True, separators=(",", ":")),
    )
    context = dict(getattr(scientist_frame, "context", {}) or {})
    context["generation_cycle_revision"] = revision_prompt_context
    return replace(
        scientist_frame,
        success_criteria=success_criteria,
        assumptions=assumptions,
        context=context,
    )


async def generate_design_candidate_bundle_under_a(
    design_problem: DesignProblem,
    *,
    model_id: str,
    llm_client: object | None = None,
    repo_root: Path | None = None,
    min_diverse_candidates: int = 3,
    data_context: dict[str, Any] | None = None,
    world_model_record_ref: str | None = None,
) -> DesignGenerationOrganRun:
    """Run the canonical N4 organ path and expose real draft/bundle/critique artifacts."""

    repo_root = (repo_root or Path.cwd()).resolve()
    design_problem_ref = gy_content_hash(design_problem.model_dump(mode="json"))
    if llm_client is None:
        from polisyos.scientist.orchestration.llm.factory import create_traced_gateway_client

        llm_client = create_traced_gateway_client(
            model_name=model_id,
            run_id="gy_n4_generation_under_a",
            model_variant_id=_model_variant_id(model_id),
        )
    if llm_client is None:
        preflight = ModelProfilePreflight(
            status="gateway_unavailable",
            model_id=model_id,
            supported_model_ids=tuple(SUPPORTED_GENERATION_MODEL_IDS),
            reason="gateway_client_not_configured",
        )
        return _terminal_result(
            design_problem_ref=design_problem_ref,
            model_id=model_id,
            preflight=preflight,
            status="generation_unavailable",
            reason="gateway_client_not_configured",
            organ="gateway",
            min_diverse_candidates=min_diverse_candidates,
        ).as_organ_run()

    recording_client = RecordingLLMClient(llm_client, model_id=model_id)
    preflight = await preflight_model_profile(recording_client, model_id=model_id)
    if preflight.status != "supported":
        status: GenerationStatus = (
            "preflight_rejected" if preflight.status == "unsupported" else "generation_unavailable"
        )
        return _terminal_result(
            design_problem_ref=design_problem_ref,
            model_id=model_id,
            preflight=preflight,
            status=status,
            reason=preflight.reason,
            organ="preflight",
            min_diverse_candidates=min_diverse_candidates,
            llm_calls=tuple(recording_client.calls),
        ).as_organ_run()

    reference: CredalReference | None = None
    try:
        reference = build_credal_reference(repo_root)
    except (OSError, RuntimeError, ValueError) as exc:
        lever_space_prompt_slice = LeverSpacePromptSlice(
            status="unavailable",
            failure_reason=f"credal_reference_unavailable:{type(exc).__name__}",
        )
    else:
        lever_space_prompt_slice = derive_lever_space_prompt_slice(
            design_problem,
            repo_root=repo_root,
            reference=reference,
        )
    base_scientist_frame = _with_generation_cycle_revision_context(
        design_problem.to_scientist_problem_frame(),
        design_problem=design_problem,
    )
    scientist_frame = _with_lever_space_prompt_slice(
        base_scientist_frame,
        lever_space_prompt_slice=lever_space_prompt_slice,
    )
    prompt_size_estimate = _prompt_size_estimate(base_scientist_frame, scientist_frame)
    multipass_config = _n4_multipass_config()
    multipass_config = multipass_config.model_copy(
        update={
            "max_passes": 4,
            "early_exit_confidence": 1.0,
            "finding_severity_threshold": "high",
            "budget_limit_usd": 0.20,
            "max_extra_llm_calls": 3,
            "constitution_enabled": False,
            "code_verification_enabled": False,
            "rag_enabled": False,
        }
    )
    effective_runtime_config = _effective_runtime_config(
        multipass_config=multipass_config,
        formalizer=None,
        critic=None,
        prompt_size_estimate=prompt_size_estimate,
    )
    multipass_config = MultiPassConfig(
        max_passes=4,
        early_exit_confidence=1.0,
        finding_severity_threshold="high",
        budget_limit_usd=0.20,
        max_extra_llm_calls=3,
        pass_timeout_s=multipass_config.pass_timeout_s,
        pass_retry_count=multipass_config.pass_retry_count,
        constitution_enabled=False,
        code_verification_enabled=False,
        rag_enabled=False,
    )
    drafter = create_drafter_agent(
        recording_client,
        model_name=model_id,
        config=multipass_config,
        multipass_mode="active",
    )
    formalizer = LLMFormalizerAgent(
        recording_client,
        model_name=model_id,
        enable_response_healing=True,
    )
    formalizer.MAX_RETRIES = max(
        int(getattr(formalizer, "MAX_RETRIES", 0) or 0),
        _int_env("POLISYOS_FORMALIZER_LLM_RETRIES", 2),
    )
    critic = create_critic_agent(recording_client, model_name=model_id)
    effective_runtime_config = _effective_runtime_config(
        multipass_config=multipass_config,
        formalizer=formalizer,
        critic=critic,
        prompt_size_estimate=prompt_size_estimate,
    )
    relation_engine: GroundingRelationEngine | None = None
    if reference is not None:
        relation_engine = GroundingRelationEngine(reference)
    if _cg1_index_prewarm_enabled():
        if relation_engine is None:
            return _terminal_result(
                design_problem_ref=design_problem_ref,
                model_id=model_id,
                preflight=preflight,
                status="generation_unavailable",
                reason="cg1_index_prewarm_reference_unavailable",
                organ="grounding_relation",
                min_diverse_candidates=min_diverse_candidates,
                llm_calls=tuple(recording_client.calls),
                lever_space_prompt_slice=lever_space_prompt_slice,
                effective_runtime_config=effective_runtime_config.model_copy(
                    update={"cg1_index_prewarm_enabled": True}
                ),
            ).as_organ_run()
        try:
            prewarm_wall = _prewarm_grounding_relation_index(
                relation_engine,
                design_problem=design_problem,
            )
        except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
            return _terminal_result(
                design_problem_ref=design_problem_ref,
                model_id=model_id,
                preflight=preflight,
                status="generation_unavailable",
                reason=f"cg1_index_prewarm_failed:{type(exc).__name__}",
                organ="grounding_relation",
                min_diverse_candidates=min_diverse_candidates,
                llm_calls=tuple(recording_client.calls),
                lever_space_prompt_slice=lever_space_prompt_slice,
                effective_runtime_config=effective_runtime_config.model_copy(
                    update={"cg1_index_prewarm_enabled": True}
                ),
            ).as_organ_run()
        effective_runtime_config = effective_runtime_config.model_copy(
            update={
                "cg1_index_prewarm_enabled": True,
                "cg1_index_prewarm_wall_seconds": prewarm_wall,
            }
        )

    draft_call_start = len(recording_client.calls)
    try:
        draft = await drafter.draft_policy(
            scientist_frame,
            data_context=data_context or {},
        )
    except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
        return _terminal_result(
            design_problem_ref=design_problem_ref,
            model_id=model_id,
            preflight=preflight,
            status="generation_unavailable",
            reason=f"drafter_call_failed:{type(exc).__name__}",
            organ="drafter",
            min_diverse_candidates=min_diverse_candidates,
            llm_calls=tuple(recording_client.calls),
            lever_space_prompt_slice=lever_space_prompt_slice,
            effective_runtime_config=effective_runtime_config,
        ).as_organ_run()
    draft_path = _draft_generator_path(recording_client.calls[draft_call_start:], draft)
    if draft_path != _REAL_GENERATOR_PATH:
        return _terminal_result(
            design_problem_ref=design_problem_ref,
            model_id=model_id,
            preflight=preflight,
            status="generation_unavailable",
            reason="drafter_degraded_mock_fallback",
            organ="drafter",
            min_diverse_candidates=min_diverse_candidates,
            llm_calls=tuple(recording_client.calls),
            lever_space_prompt_slice=lever_space_prompt_slice,
            effective_runtime_config=effective_runtime_config,
        ).as_organ_run()

    formalizer_call_start = len(recording_client.calls)
    try:
        bundle = await formalizer.formalize(draft)
    except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
        return _terminal_result(
            design_problem_ref=design_problem_ref,
            model_id=model_id,
            preflight=preflight,
            status="generation_unavailable",
            reason=f"formalizer_call_failed:{type(exc).__name__}",
            organ="formalizer",
            min_diverse_candidates=min_diverse_candidates,
            llm_calls=tuple(recording_client.calls),
            lever_space_prompt_slice=lever_space_prompt_slice,
            effective_runtime_config=effective_runtime_config,
        ).as_organ_run(draft=draft)
    formalizer_path = trinity_bundle_formalizer_generator_path(
        bundle,
        recorded_calls=recording_client.calls[formalizer_call_start:],
    )
    if formalizer_path != _REAL_GENERATOR_PATH:
        bundle, formalizer_path = await _salvage_formalizer_terminal(
            formalizer=formalizer,
            draft=draft,
            recording_client=recording_client,
            terminal_start=formalizer_call_start,
            current_bundle=bundle,
            current_path=formalizer_path,
        )
    effective_runtime_config = effective_runtime_config.model_copy(
        update={
            "formalizer_schema_healing_events": tuple(
                getattr(formalizer, "schema_healing_events", ())
            )
        }
    )
    if formalizer_path != _REAL_GENERATOR_PATH:
        return _terminal_result(
            design_problem_ref=design_problem_ref,
            model_id=model_id,
            preflight=preflight,
            status="generation_unavailable",
            reason=(
                "formalizer_path_unrecorded"
                if formalizer_path == "path_unrecorded"
                else "formalizer_degraded_mock_fallback"
            ),
            organ="formalizer",
            min_diverse_candidates=min_diverse_candidates,
            llm_calls=tuple(recording_client.calls),
            lever_space_prompt_slice=lever_space_prompt_slice,
            effective_runtime_config=effective_runtime_config,
        ).as_organ_run(draft=draft)

    critic_call_start = len(recording_client.calls)
    critique = await critic.critique(bundle, scientist_frame, depth="standard")
    critic_path = str(critique.metadata.get("generator_path") or "")
    if critic_path != _REAL_GENERATOR_PATH:
        critique, critic_path = await _salvage_critic_terminal(
            critic=critic,
            bundle=bundle,
            scientist_frame=scientist_frame,
            recording_client=recording_client,
            terminal_start=critic_call_start,
            current_critique=critique,
            current_path=critic_path,
        )
    if critic_path != _REAL_GENERATOR_PATH:
        return _terminal_result(
            design_problem_ref=design_problem_ref,
            model_id=model_id,
            preflight=preflight,
            status="generation_unavailable",
            reason="critic_degraded_mock_fallback",
            organ="critic",
            min_diverse_candidates=min_diverse_candidates,
            llm_calls=tuple(recording_client.calls),
            lever_space_prompt_slice=lever_space_prompt_slice,
            effective_runtime_config=effective_runtime_config,
        ).as_organ_run(draft=draft, trinity_bundle=bundle, critique=critique)

    try:
        candidates, dispositions = _content_bound_candidates(
            design_problem=design_problem,
            design_problem_ref=design_problem_ref,
            bundle=bundle,
            model_id=model_id,
            draft_path=draft_path,
            formalizer_path=formalizer_path,
            critic_path=critic_path,
            critique_verdict=str(critique.verdict),
            calls=tuple(recording_client.calls),
            repo_root=repo_root,
            world_model_record_ref=world_model_record_ref,
            reference=reference,
            relation_engine=relation_engine,
        )
    except (DesignGenerationError, InterventionSubstrateError, ValueError) as exc:
        return _terminal_result(
            design_problem_ref=design_problem_ref,
            model_id=model_id,
            preflight=preflight,
            status="generation_unavailable",
            reason=str(exc),
            organ="atom_binding",
            min_diverse_candidates=min_diverse_candidates,
            llm_calls=tuple(recording_client.calls),
            lever_space_prompt_slice=lever_space_prompt_slice,
            effective_runtime_config=effective_runtime_config,
        ).as_organ_run(draft=draft, trinity_bundle=bundle, critique=critique)

    diversity_report = measure_generation_diversity(
        candidates,
        min_required=min_diverse_candidates,
        dispositions=dispositions,
    )
    if not diversity_report.diverse_enough:
        return GenerationUnderAResult(
            status="generation_unavailable",
            design_problem_ref=design_problem_ref,
            model_id=model_id,
            preflight=preflight,
            degraded_artifacts=(
                DegradedGenerationArtifact(
                    reason="insufficient_diverse_model_generated_candidates",
                    organ="diversity",
                    details=diversity_report.model_dump(mode="json"),
                ),
            ),
            diversity_report=diversity_report,
            llm_calls=tuple(recording_client.calls),
            firewall_evidence=default_firewall_evidence(),
            strangle_receipts=design_generation_strangle_receipts(repo_root),
            lever_space_prompt_slice=lever_space_prompt_slice,
            effective_runtime_config=effective_runtime_config,
        ).as_organ_run(draft=draft, trinity_bundle=bundle, critique=critique)

    try:
        rankings = rank_shadow_candidates_with_graph_causal_surrogate(
            candidates,
            design_problem=design_problem,
            repo_root=repo_root,
        )
    except DesignGenerationError as exc:
        return _terminal_result(
            design_problem_ref=design_problem_ref,
            model_id=model_id,
            preflight=preflight,
            status="generation_unavailable",
            reason=str(exc),
            organ="surrogate",
            min_diverse_candidates=min_diverse_candidates,
            llm_calls=tuple(recording_client.calls),
            lever_space_prompt_slice=lever_space_prompt_slice,
            effective_runtime_config=effective_runtime_config,
        ).as_organ_run(draft=draft, trinity_bundle=bundle, critique=critique)
    result = GenerationUnderAResult(
        status="generated",
        design_problem_ref=design_problem_ref,
        model_id=model_id,
        preflight=preflight,
        candidates=tuple(candidates),
        grounding_dispositions=tuple(dispositions),
        grounding_disposition_summary=_grounding_disposition_summary(dispositions),
        effective_runtime_config=effective_runtime_config,
        lever_space_prompt_slice=lever_space_prompt_slice,
        diversity_report=diversity_report,
        surrogate_rankings=tuple(rankings),
        llm_calls=tuple(recording_client.calls),
        firewall_evidence=default_firewall_evidence(),
        strangle_receipts=design_generation_strangle_receipts(repo_root),
    )
    return DesignGenerationOrganRun(
        result=result,
        draft=draft,
        trinity_bundle=bundle,
        critique=critique,
    )


def _n4_multipass_config() -> MultiPassConfig:
    base = MultiPassConfig.from_env()
    timeout_s = max(
        float(base.pass_timeout_s),
        _float_env("POLISYOS_DRAFTER_PASS_TIMEOUT_S", 120.0),
    )
    retry_count = max(
        int(base.pass_retry_count),
        _int_env("POLISYOS_DRAFTER_PASS_RETRY_COUNT", 2),
    )
    return base.model_copy(
        update={
            "pass_timeout_s": timeout_s,
            "pass_retry_count": retry_count,
        }
    )


def _terminal_salvage_retry_count() -> int:
    return max(0, _int_env("POLISYOS_N4_TERMINAL_SALVAGE_RETRIES", 2))


def _terminal_salvage_backoff_base_s() -> float:
    return max(0.0, _float_env("POLISYOS_N4_TERMINAL_SALVAGE_BACKOFF_BASE_S", 2.0))


def _cg1_index_prewarm_enabled() -> bool:
    return _bool_env("POLISYOS_N4_PREWARM_CG1_INDEX", False)


def _prewarm_grounding_relation_index(
    relation_engine: GroundingRelationEngine,
    *,
    design_problem: DesignProblem,
) -> float:
    started = time.monotonic()
    query = " ".join(
        (
            design_problem.problem_statement,
            design_problem.outcome_of_interest.target_variable,
            design_problem.outcome_of_interest.metric_id,
        )
    )
    parsed = parse_n4_proposal(
        query,
        proposal_id="gy_n4.cg1_full_reference_index_prewarm",
        reference=relation_engine.reference,
    )
    relation_engine.retrieve_candidates(
        parsed,
        include_adversarial_countercandidates=False,
    )
    return max(0.0, time.monotonic() - started)


async def _salvage_formalizer_terminal(
    *,
    formalizer: object,
    draft: object,
    recording_client: RecordingLLMClient,
    terminal_start: int,
    current_bundle: TrinityBundle,
    current_path: str,
) -> tuple[TrinityBundle, str]:
    if current_path != "path_unrecorded" and not _terminal_window_is_transient(
        recording_client.calls[terminal_start:]
    ):
        return current_bundle, current_path
    first_prompt_hash = _first_prompt_hash(recording_client.calls[terminal_start:])
    bundle = current_bundle
    path = current_path
    for salvage_index in range(_terminal_salvage_retry_count()):
        await _sleep_terminal_salvage(recording_client.calls[terminal_start:], salvage_index)
        retry_start = len(recording_client.calls)
        bundle = await formalizer.formalize(draft)  # type: ignore[attr-defined]
        _assert_terminal_salvage_prompt_hash(
            recording_client.calls[retry_start:],
            first_prompt_hash=first_prompt_hash,
        )
        path = trinity_bundle_formalizer_generator_path(
            bundle,
            recorded_calls=recording_client.calls[retry_start:],
        )
        if path == _REAL_GENERATOR_PATH:
            return bundle, path
        if not _terminal_window_is_transient(recording_client.calls[retry_start:]):
            return bundle, path
    return bundle, path


async def _salvage_critic_terminal(
    *,
    critic: object,
    bundle: TrinityBundle,
    scientist_frame: object,
    recording_client: RecordingLLMClient,
    terminal_start: int,
    current_critique: object,
    current_path: str,
) -> tuple[object, str]:
    if not _terminal_window_is_transient(recording_client.calls[terminal_start:]):
        return current_critique, current_path
    first_prompt_hash = _first_prompt_hash(recording_client.calls[terminal_start:])
    critique = current_critique
    path = current_path
    for salvage_index in range(_terminal_salvage_retry_count()):
        await _sleep_terminal_salvage(recording_client.calls[terminal_start:], salvage_index)
        retry_start = len(recording_client.calls)
        critique = await critic.critique(bundle, scientist_frame, depth="standard")  # type: ignore[attr-defined]
        _assert_terminal_salvage_prompt_hash(
            recording_client.calls[retry_start:],
            first_prompt_hash=first_prompt_hash,
        )
        metadata = getattr(critique, "metadata", {}) or {}
        path = str(metadata.get("generator_path") or "") if isinstance(metadata, Mapping) else ""
        if path == _REAL_GENERATOR_PATH:
            return critique, path
        if not _terminal_window_is_transient(recording_client.calls[retry_start:]):
            return critique, path
    return critique, path


async def _sleep_terminal_salvage(
    calls: Sequence[LLMGenerationCall],
    salvage_index: int,
) -> None:
    retry_after = _latest_retry_after(calls)
    if retry_after is not None:
        delay = retry_after
    else:
        delay = min(_terminal_salvage_backoff_base_s() * (2**salvage_index), 60.0)
    if delay > 0.0:
        await asyncio.sleep(delay)


def _terminal_window_is_transient(calls: Sequence[LLMGenerationCall]) -> bool:
    if not calls:
        return False
    if any(call.status == "success" for call in calls):
        return False
    return all(_llm_call_error_is_transient(call) for call in calls)


def _llm_call_error_is_transient(call: LLMGenerationCall) -> bool:
    if call.status != "error":
        return False
    if call.error_status == 429 or (call.error_status is not None and call.error_status >= 500):
        return True
    haystack = f"{call.error_type or ''} {call.error_code or ''} {call.error_message or ''}".lower()
    return any(
        marker in haystack
        for marker in (
            "failed llm gateway call",
            "gateway request failed (429)",
            "rate_limit",
            "rate limit",
            "timeout",
            "temporarily unavailable",
            "service_unavailable",
        )
    )


def _first_prompt_hash(calls: Sequence[LLMGenerationCall]) -> str | None:
    for call in calls:
        if call.prompt_hash:
            return call.prompt_hash
    return None


def _assert_terminal_salvage_prompt_hash(
    calls: Sequence[LLMGenerationCall],
    *,
    first_prompt_hash: str | None,
) -> None:
    if first_prompt_hash is None:
        return
    for call in calls:
        if call.prompt_hash == first_prompt_hash:
            return
    raise DesignGenerationError(
        "terminal_salvage_prompt_hash_drift",
        "terminal salvage changed the organ prompt instead of retrying the same input",
    )


def _latest_retry_after(calls: Sequence[LLMGenerationCall]) -> float | None:
    for call in reversed(calls):
        if call.retry_after_s is not None:
            return float(call.retry_after_s)
    return None


def _effective_runtime_config(
    *,
    multipass_config: MultiPassConfig,
    formalizer: object | None,
    critic: object | None,
    prompt_size_estimate: PromptSizeEstimate,
) -> EffectiveGenerationRuntimeConfig:
    return EffectiveGenerationRuntimeConfig(
        drafter_pass_timeout_s=float(multipass_config.pass_timeout_s),
        drafter_pass_retry_count=int(multipass_config.pass_retry_count),
        formalizer_timeout_s=float(
            getattr(
                formalizer,
                "_timeout_s",
                _float_env("POLISYOS_FORMALIZER_LLM_TIMEOUT_S", 120.0),
            )
        ),
        formalizer_retry_count=int(
            getattr(
                formalizer,
                "MAX_RETRIES",
                _int_env("POLISYOS_FORMALIZER_LLM_RETRIES", 2),
            )
        ),
        critic_timeout_s=float(
            getattr(
                critic,
                "_timeout_s",
                _float_env("POLISYOS_CRITIC_LLM_TIMEOUT_S", 120.0),
            )
        ),
        terminal_salvage_retry_count=_terminal_salvage_retry_count(),
        terminal_salvage_backoff_base_s=_terminal_salvage_backoff_base_s(),
        gateway_timeout_s=_float_env("POLISYOS_LLM_GATEWAY_TIMEOUT_S", 120.0),
        gateway_max_retries=_int_env("POLISYOS_LLM_GATEWAY_MAX_RETRIES", 3),
        prompt_cache_ttl_s=_float_env("POLISYOS_LLM_CACHE_TTL_S", 300.0),
        prompt_cache_maxsize=_int_env("POLISYOS_LLM_CACHE_MAXSIZE", 128),
        formalizer_schema_healing_events=tuple(
            dict(item) for item in getattr(formalizer, "schema_healing_events", ())
        ),
        prompt_size_estimate=prompt_size_estimate,
    )


def _prompt_size_estimate(base_frame: object, sliced_frame: object) -> PromptSizeEstimate:
    base_chars = len(_json_for_prompt_size(base_frame))
    sliced_chars = len(_json_for_prompt_size(sliced_frame))
    added = max(0, sliced_chars - base_chars)
    return PromptSizeEstimate(
        frame_without_slice_chars=base_chars,
        frame_with_slice_chars=sliced_chars,
        slice_added_chars=added,
        frame_without_slice_estimated_tokens=_estimated_tokens(base_chars),
        frame_with_slice_estimated_tokens=_estimated_tokens(sliced_chars),
        slice_added_estimated_tokens=_estimated_tokens(added),
    )


def _json_for_prompt_size(value: object) -> str:
    payload = value.__dict__ if hasattr(value, "__dict__") else value
    return json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))


def _estimated_tokens(char_count: int) -> int:
    return max(0, (int(char_count) + 3) // 4)


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def measure_generation_diversity(
    candidates: Sequence[ShadowGeneratedCandidate],
    *,
    min_required: int = 3,
    dispositions: Sequence[GroundingDispositionRecord] = (),
) -> GenerationDiversityReport:
    """Measure real diversity over atom operator/selector/mechanism/parameterization."""

    keys = {candidate.diversity_key for candidate in candidates}
    for disposition in dispositions:
        if disposition.disposition != "shadow_bound":
            keys.add(
                (
                    disposition.selected_relation,
                    disposition.identified_atom_id or disposition.proposal_id,
                    disposition.cg3_decision or disposition.cg2_decision or disposition.disposition,
                    disposition.raw_candidate_hash,
                )
            )
    operator_kinds = tuple(
        sorted(
            {
                *(candidate.diversity_key[0] for candidate in candidates),
                *(item.selected_relation for item in dispositions),
            }
        )
    )
    target_selectors = tuple(
        sorted(
            {
                *(candidate.diversity_key[1] for candidate in candidates),
                *(
                    item.identified_atom_id or item.proposal_id
                    for item in dispositions
                    if item.disposition != "shadow_bound"
                ),
            }
        )
    )
    mechanisms = tuple(
        sorted(
            {
                *(candidate.diversity_key[2] for candidate in candidates),
                *(item.disposition for item in dispositions),
            }
        )
    )
    parameterizations = tuple(
        sorted(
            {
                *(candidate.diversity_key[3] for candidate in candidates),
                *(item.raw_candidate_hash for item in dispositions),
            }
        )
    )
    hardcode_detected = mechanisms in {("tax_subsidy",), ("credit_guarantee",)}
    candidate_count = len(dispositions) if dispositions else len(candidates)
    return GenerationDiversityReport(
        min_required=min_required,
        candidate_count=candidate_count,
        unique_diversity_key_count=len(keys),
        unique_operator_kinds=operator_kinds,
        unique_target_selectors=target_selectors,
        unique_mechanisms=mechanisms,
        unique_parameterizations=parameterizations,
        diverse_enough=candidate_count >= min_required and len(keys) >= min_required,
        domain_mechanism_hardcode_detected=hardcode_detected,
    )


def rank_shadow_candidates_with_graph_causal_surrogate(
    candidates: Sequence[ShadowGeneratedCandidate],
    *,
    design_problem: DesignProblem,
    repo_root: Path,
) -> tuple[SurrogateRanking, ...]:
    """Rank candidates for search/VOI using real owner inputs without certification."""

    try:
        substrate = load_l6_intervention_substrate(repo_root.resolve())
        routed_families = _observation_manifest_families(substrate.observation_manifest)
        trust: SurrogateTrustLevel = "search_guiding"
    except (InterventionSubstrateError, OSError, ValueError):
        routed_families = ()
        trust = "proposal_only"
    owner_feature_refs = _resolved_surrogate_owner_feature_refs()
    if not owner_feature_refs:
        trust = "proposal_only"
    rankings: list[SurrogateRanking] = []
    target_tokens = _tokens(
        " ".join(
            (
                design_problem.outcome_of_interest.target_variable,
                design_problem.outcome_of_interest.metric_id,
                design_problem.problem_statement,
            )
        )
    )
    for index, candidate in enumerate(candidates):
        atom = candidate.atom
        feature_text = " ".join(
            (
                atom.operator_kind.trinity_kind,
                atom.direct_effect_bundle.mechanism_id,
                " ".join(atom.target_world_slots),
            )
        )
        overlap = len(target_tokens & _tokens(feature_text))
        route_bonus = min(0.25, 0.05 * len(routed_families))
        score = min(1.0, 0.35 + route_bonus + 0.08 * len(atom.target_world_slots) + 0.04 * overlap)
        rankings.append(
            SurrogateRanking(
                candidate_id=candidate.candidate_id,
                trust_level=trust,
                score=round(score, 6),
                voi_estimate=round(score * (1.0 + index / max(len(candidates), 1)), 6),
                promotion_allowed=False,
                feature_refs=(
                    atom.content_hash,
                    *owner_feature_refs,
                    *tuple(f"observation_family:{family}" for family in routed_families[:3]),
                ),
                owner_refs=tuple(_SEARCH_SURROGATE_OWNERS),
            )
        )
    return tuple(rankings)


def default_firewall_evidence() -> tuple[FirewallEvidence, ...]:
    """Return the full P15/P32 set of signals that are not certificates."""

    return tuple(
        FirewallEvidence(
            evidence_kind=kind,
            authority_state="candidate_unverified",
            blocked_from_authority=True,
            reason="N4 proposer signal; only A Ring-2/N9 can promote",
        )
        for kind in NOT_CERTIFICATE_KINDS
    )


_STRANGLE_RECEIPT_SPECS: tuple[dict[str, Any], ...] = (
    {
        "predecessor_ref": "runtime.http.nl_pipeline.none_to_mock_generator_fork",
        "replacement_ref": (
            f"{DESIGN_GENERATION_PRODUCER_REF}.generate_design_candidate_bundle_under_a"
        ),
        "file": "src/polisyos/runtime/http/services/control/nl_pipeline.py",
        "forbidden": (
            "drafter = MockDrafterAgent()",
            "formalizer = MockFormalizerAgent()",
            "critic = MockCriticAgent()",
            "selected_variant = await _run_variant(None",
        ),
        "required": (
            "NaturalLanguagePipelineRefusalError",
            "_execute_nl_pipeline_for_contract_testing",
            "generate_design_candidate_bundle_under_a",
            "generation_unavailable",
            "n4_generation_terminal",
            "fabric_generation_bypass_blocked",
        ),
        "default_before": "llm_client None selected MockDrafter/MockFormalizer/MockCritic.",
        "default_after": (
            "missing model refuses; unavailable gateway returns N4 generation_unavailable."
        ),
        "disposition": "contract_testing_only",
        "removed_loc": "nl_pipeline.py:llm_client_none_mock_generator_fork",
    },
    {
        "predecessor_ref": "scientist.validation.policy_verified.mock_formalizer_tax_subsidy",
        "replacement_ref": (
            "polisyos.scientist.nodes.builtins.compile.formalize_verified_policy."
            "FormalizeVerifiedPolicyNode"
        ),
        "file": "src/polisyos/scientist/validation/policy_verified/service.py",
        "forbidden": (),
        "required": (
            "POLICY_VERIFIED_HARDCODED_FORMALIZER_STRANGLED",
            "INPUT_TRINITY_BUNDLE_REF",
        ),
        "default_before": (
            "verified-policy formalized a hardcoded tax_subsidy draft with MockFormalizer."
        ),
        "default_after": "verified-policy consumes a supplied real TrinityBundleRef by default.",
        "disposition": "supplied_real_or_typed_refusal",
        "removed_loc": "policy_verified/service.py:formalize_policy_option_set",
    },
    {
        "predecessor_ref": "pdc._impl.layer2_design_search.fixed_credit_guarantee_candidate",
        "replacement_ref": (
            "polisyos.pdc._impl.layer2_design_search."
            "run_s2_shadow_design_loop.input_derived_candidate_space"
        ),
        "file": "src/polisyos/pdc/_impl/layer2_design_search.py",
        "forbidden": (
            "s2_fixed_credit_guarantee_fixture_authorized: Literal[True] = True",
            "s2_fixed_credit_guarantee_fixture_authorized: bool = True",
            "def fixed_credit_guarantee_candidate",
        ),
        "required": (
            "instrument_families=list(input.instrument_families)",
            "_candidate_from_expansion",
            "source_authority=input.candidate_source_authority",
        ),
        "default_before": "S2 emitted a fixed credit_guarantee candidate as its replay body.",
        "default_after": "S2 candidate family and parameters derive from input-carried evidence.",
        "disposition": "input_derived_candidate_space",
        "removed_loc": "layer2_design_search.py:_candidate",
    },
)


def design_generation_strangle_receipts(
    repo_root: Path | None = None,
) -> tuple[dict[str, Any], ...]:
    """Recompute receipts fencing legacy/hardcoded generation paths from authority."""

    root = (repo_root or Path.cwd()).resolve()
    return tuple(_build_strangle_receipt(root, spec) for spec in _STRANGLE_RECEIPT_SPECS)


def validate_design_generation_strangle_receipts(
    repo_root: Path | None = None,
) -> tuple[dict[str, Any], ...]:
    """Return drift issues for the recomputed GY-N4 strangle receipts."""

    issues: list[dict[str, Any]] = []
    for receipt in design_generation_strangle_receipts(repo_root):
        if receipt.get("status") != "strangled":
            issues.append(
                {
                    "code": "design_generation_strangle_receipt_not_strangled",
                    "predecessor_ref": receipt.get("predecessor_ref"),
                    "status": receipt.get("status"),
                    "remaining_callers": receipt.get("remaining_callers"),
                }
            )
    return tuple(issues)


def _build_strangle_receipt(root: Path, spec: Mapping[str, Any]) -> dict[str, Any]:
    relative = str(spec["file"])
    path = root / relative
    source = path.read_text(encoding="utf-8") if path.is_file() else ""
    forbidden_hits = [item for item in spec["forbidden"] if item in source]
    missing_required = [item for item in spec["required"] if item not in source]
    ast_callers: list[dict[str, str]] = []
    if spec["predecessor_ref"] == (
        "pdc._impl.layer2_design_search.fixed_credit_guarantee_candidate"
    ):
        ast_callers = _s2_forbidden_candidate_callers(source)
    elif spec["predecessor_ref"] == "runtime.http.nl_pipeline.none_to_mock_generator_fork":
        ast_callers = _nl_pipeline_fixture_callers(root)
    elif spec["predecessor_ref"] == (
        "scientist.validation.policy_verified.mock_formalizer_tax_subsidy"
    ):
        ast_callers = _policy_verified_fixture_callers(root)
    status = "strangled" if not forbidden_hits and not missing_required else "drift"
    if ast_callers:
        status = "drift"
    return {
        "predecessor_ref": spec["predecessor_ref"],
        "replacement_ref": spec["replacement_ref"],
        "disposition": spec["disposition"],
        "status": status,
        "default_before": spec["default_before"],
        "default_after": spec["default_after"],
        "remaining_callers": (
            [
                {
                    "path": relative,
                    "reason": "forbidden_live_default_present",
                    "pattern": item,
                }
                for item in forbidden_hits
            ]
            + [
                {
                    "path": relative,
                    "reason": "required_guard_missing",
                    "pattern": item,
                }
                for item in missing_required
            ]
            + ast_callers
        ),
        "removed_loc": spec["removed_loc"],
        "verified_by": (
            f"{DESIGN_GENERATION_PRODUCER_REF}.validate_design_generation_strangle_receipts",
            "tools.quality.validation.check_layer3_gy_design_generation_contract",
        ),
    }


def _s2_forbidden_candidate_callers(source: str) -> list[dict[str, str]]:
    """Prove S2 candidate vocabulary and parameters derive from input data."""

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [
            {
                "path": "src/polisyos/pdc/_impl/layer2_design_search.py",
                "reason": "source_not_parseable",
                "pattern": str(exc),
            }
        ]
    issues: list[dict[str, str]] = []
    assigned_names = {
        target.id
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (
            (*node.targets,) if isinstance(node, ast.Assign) else (node.target,)
        )
        if isinstance(target, ast.Name)
    }
    if "_INSTRUMENT_FAMILIES" in assigned_names or "credit_guarantee" in source:
        issues.append(
            {
                "path": "src/polisyos/pdc/_impl/layer2_design_search.py",
                "reason": "fixed_candidate_body_in_engine",
                "pattern": "credit_guarantee",
            }
        )
    if any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "_candidate"
        for node in ast.walk(tree)
    ):
        issues.append(
            {
                "path": "src/polisyos/pdc/_impl/layer2_design_search.py",
                "reason": "legacy_fixed_candidate_owner_present",
                "pattern": "_candidate",
            }
        )
    try:
        from polisyos.pdc._impl.layer2_design_search import (
            Layer2S2DesignSearchInput,
            run_s2_shadow_design_loop,
        )

        shapes = (
            (
                ("energy_storage", "demand_response", "grid_efficiency"),
                {
                    "dispatch": ("peak_shaving", "load_shift"),
                    "ownership": ("municipal", "cooperative"),
                },
            ),
            (
                ("public_transit_fare", "service_frequency", "fleet_electrification"),
                {
                    "coverage": ("low_income", "all_riders"),
                    "timing": ("off_peak", "all_day"),
                },
            ),
        )
        for index, (families, parameters) in enumerate(shapes):
            input_row = Layer2S2DesignSearchInput.model_validate(
                {
                    "case_id": f"n4-s2-unseen-{index}",
                    "intent_ref": f"intent://n4-s2-unseen-{index}",
                    "grammar_ref": f"grammar://n4-s2-unseen-{index}",
                    "instrument_families": families,
                    "parameter_space": parameters,
                    "actor_ref": "actor://contract-probe",
                    "domain": "unseen_contract_probe",
                    "objective_refs": ("objective://outcome",),
                    "construct_refs": ("construct://outcome",),
                    "authority_profile_ref": "authority://shadow",
                    "generated_at": "2026-07-11T00:00:00Z",
                }
            )
            run = run_s2_shadow_design_loop(input_row)
            expected_params = {
                dimension: values[0] for dimension, values in parameters.items()
            }
            if not (
                run.grammar_expansion.instrument_families == list(families)
                and run.grammar_expansion.parameter_space
                == {dimension: list(values) for dimension, values in parameters.items()}
                and run.candidates[0].instrument_family == families[0]
                and run.candidates[0].parameterization == expected_params
                and run.search_ledger.instrument_family_coverage == list(families)
            ):
                issues.append(
                    {
                        "path": "src/polisyos/pdc/_impl/layer2_design_search.py",
                        "reason": "s2_fixed_candidate_derivation_not_data_driven",
                        "pattern": f"unseen_shape_{index}",
                    }
                )
    except Exception as exc:
        issues.append(
            {
                "path": "src/polisyos/pdc/_impl/layer2_design_search.py",
                "reason": "s2_candidate_derivation_probe_failed",
                "pattern": f"{type(exc).__name__}:{exc}",
            }
        )
    return issues


def _policy_verified_fixture_callers(root: Path) -> list[dict[str, str]]:
    """Census production calls and authority-shaped remnants of the verified-policy fixture."""

    source_root = root / "src"
    fixture_path = (
        source_root / "polisyos/scientist/validation/policy_verified/testing.py"
    ).resolve()
    service_path = (
        source_root / "polisyos/scientist/validation/policy_verified/service.py"
    ).resolve()
    node_path = (
        source_root
        / "polisyos/scientist/nodes/builtins/compile/formalize_verified_policy.py"
    ).resolve()
    issues: list[dict[str, str]] = []
    for path in source_root.rglob("*.py"):
        resolved = path.resolve()
        source = path.read_text(encoding="utf-8")
        if (
            resolved not in {service_path, node_path, fixture_path}
            and "formalize_policy_option_set_for_contract_testing" not in source
        ):
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            if resolved in {service_path, node_path, fixture_path}:
                issues.append(
                    {
                        "path": path.relative_to(root).as_posix(),
                        "reason": "source_not_parseable",
                        "pattern": str(exc),
                    }
                )
            continue
        relative = path.relative_to(root).as_posix()
        if resolved != fixture_path:
            for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
                name = _ast_call_name(call)
                if name == "formalize_policy_option_set_for_contract_testing":
                    issues.append(
                        {
                            "path": relative,
                            "reason": "forbidden_contract_fixture_caller",
                            "pattern": name,
                        }
                    )
        if resolved == service_path:
            for function in (
                node
                for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == "formalize_policy_option_set"
            ):
                call_names = {
                    _ast_call_name(call)
                    for call in ast.walk(function)
                    if isinstance(call, ast.Call)
                }
                constants = {
                    node.value
                    for node in ast.walk(function)
                    if isinstance(node, ast.Constant) and isinstance(node.value, str)
                }
                for forbidden in (
                    "MockFormalizerAgent",
                    "formalize_policy_option_set_for_contract_testing",
                    "put_json",
                ):
                    if forbidden in call_names:
                        issues.append(
                            {
                                "path": relative,
                                "reason": "authority_shaped_fixture_in_production_owner",
                                "pattern": forbidden,
                            }
                        )
                if "tax_subsidy" in constants:
                    issues.append(
                        {
                            "path": relative,
                            "reason": "fixed_fixture_body_in_production_owner",
                            "pattern": "tax_subsidy",
                        }
                    )
    if not fixture_path.is_file():
        issues.append(
            {
                "path": fixture_path.relative_to(root).as_posix(),
                "reason": "explicit_contract_fixture_missing",
                "pattern": "formalize_policy_option_set_for_contract_testing",
            }
        )
    return issues


def _nl_pipeline_fixture_callers(root: Path) -> list[dict[str, str]]:
    """Census NL mock reachability and require the production refusal/default flip."""

    source_root = root / "src"
    pipeline_path = (
        source_root / "polisyos/runtime/http/services/control/nl_pipeline.py"
    ).resolve()
    testing_path = (
        source_root / "polisyos/runtime/http/services/control/nl_pipeline_testing.py"
    ).resolve()
    lifecycle_path = (
        source_root / "polisyos/runtime/http/services/control/run_lifecycle.py"
    ).resolve()
    issues: list[dict[str, str]] = []
    parsed: dict[Path, ast.Module] = {}
    for path in (pipeline_path, testing_path, lifecycle_path):
        if not path.is_file():
            issues.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "reason": "required_owner_missing",
                    "pattern": path.name,
                }
            )
            continue
        try:
            parsed[path] = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            issues.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "reason": "source_not_parseable",
                    "pattern": str(exc),
                }
            )
    pipeline_tree = parsed.get(pipeline_path)
    if pipeline_tree is not None:
        functions = {
            node.name: node
            for node in ast.walk(pipeline_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        production = functions.get("_execute_nl_pipeline")
        contract = functions.get("_execute_nl_pipeline_for_contract_testing")
        implementation = functions.get("_execute_nl_pipeline_impl")
        for name, function in (
            ("_execute_nl_pipeline", production),
            ("_execute_nl_pipeline_for_contract_testing", contract),
            ("_execute_nl_pipeline_impl", implementation),
        ):
            if function is None:
                issues.append(
                    {
                        "path": pipeline_path.relative_to(root).as_posix(),
                        "reason": "required_router_missing",
                        "pattern": name,
                    }
                )
        if production is not None:
            constants = {
                node.value
                for node in ast.walk(production)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
            }
            calls = {
                _ast_call_name(call)
                for call in ast.walk(production)
                if isinstance(call, ast.Call)
            }
            if "llm_model_unconfigured" not in constants:
                issues.append(
                    {
                        "path": pipeline_path.relative_to(root).as_posix(),
                        "reason": "production_empty_model_refusal_missing",
                        "pattern": "llm_model_unconfigured",
                    }
                )
            if "build_nl_contract_testing_agents" in calls:
                issues.append(
                    {
                        "path": pipeline_path.relative_to(root).as_posix(),
                        "reason": "contract_fixture_reachable_from_production_router",
                        "pattern": "build_nl_contract_testing_agents",
                    }
                )
        if implementation is not None:
            calls = {
                _ast_call_name(call)
                for call in ast.walk(implementation)
                if isinstance(call, ast.Call)
            }
            for mock_name in (
                "MockPIAgent",
                "MockDataNeedExtractorAgent",
                "MockDrafterAgent",
                "MockFormalizerAgent",
                "MockCriticAgent",
            ):
                if mock_name in calls:
                    issues.append(
                        {
                            "path": pipeline_path.relative_to(root).as_posix(),
                            "reason": "mock_constructor_in_shared_pipeline",
                            "pattern": mock_name,
                        }
                    )
    lifecycle_tree = parsed.get(lifecycle_path)
    if lifecycle_tree is not None:
        launch = next(
            (
                node
                for node in ast.walk(lifecycle_tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == "launch_nl_run"
            ),
            None,
        )
        constants = (
            {
                node.value
                for node in ast.walk(launch)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
            }
            if launch is not None
            else set()
        )
        if "llm_model_unconfigured" not in constants:
            issues.append(
                {
                    "path": lifecycle_path.relative_to(root).as_posix(),
                    "reason": "launch_default_not_flipped",
                    "pattern": "llm_model_unconfigured",
                }
            )
    for path in source_root.rglob("*.py"):
        if path.resolve() == pipeline_path:
            continue
        source = path.read_text(encoding="utf-8")
        if "_execute_nl_pipeline_for_contract_testing" not in source:
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        if any(
            _ast_call_name(call) == "_execute_nl_pipeline_for_contract_testing"
            for call in ast.walk(tree)
            if isinstance(call, ast.Call)
        ):
            issues.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "reason": "contract_testing_lane_called_from_source",
                    "pattern": "_execute_nl_pipeline_for_contract_testing",
                }
            )
    return issues


def _ast_call_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return ""


def firewall_issues_for_result(result: GenerationUnderAResult) -> tuple[dict[str, Any], ...]:
    """Behaviorally validate N4's role separation and shadow-only output."""

    issues: list[dict[str, Any]] = []
    if result.preflight.status != "supported" and result.status == "generated":
        issues.append({"code": "unsupported_model_not_rejected", "model_id": result.model_id})
    if result.status == "generated" and result.preflight.status != "supported":
        issues.append({"code": "generated_without_supported_preflight"})
    if (
        result.status == "generated"
        and result.preflight.live_model_ids
        and result.model_id not in result.preflight.live_model_ids
    ):
        issues.append({"code": "generated_model_not_in_live_catalog", "model_id": result.model_id})
    for candidate in result.candidates:
        if candidate.generator_path != _REAL_GENERATOR_PATH:
            issues.append(
                {
                    "code": "degraded_candidate_counted_real",
                    "candidate_id": candidate.candidate_id,
                }
            )
        candidate_promoted = (
            candidate.status != "candidate_unverified"
            or candidate.atom.status != "candidate_unverified"
        )
        if candidate_promoted:
            issues.append(
                {
                    "code": "candidate_reached_authority_without_A",
                    "candidate_id": candidate.candidate_id,
                }
            )
        if candidate.atom.world_model_record_ref.startswith("world_model_record_pending:"):
            issues.append(
                {
                    "code": "pending_world_model_record_ref_admitted",
                    "candidate_id": candidate.candidate_id,
                    "world_model_record_ref": candidate.atom.world_model_record_ref,
                }
            )
        try:
            validated = InterventionAtomBinding.model_validate(
                candidate.atom.model_dump(mode="json")
            )
            consume_intervention_atom_for_cycle(validated)
        except (TypeError, ValueError) as exc:
            issues.append(
                {
                    "code": "candidate_without_content_bound_atom",
                    "candidate_id": candidate.candidate_id,
                    "error": str(exc),
                }
            )
    disposition_by_candidate = {
        item.candidate_id: item
        for item in result.grounding_dispositions
        if item.disposition == "shadow_bound" and item.candidate_id
    }
    for candidate in result.candidates:
        disposition = disposition_by_candidate.get(candidate.candidate_id)
        if disposition is None:
            issues.append(
                {
                    "code": "candidate_bound_without_grounding_disposition",
                    "candidate_id": candidate.candidate_id,
                }
            )
            continue
        parsed = candidate.provenance.parsed_candidate
        chain = disposition.certificate_chain
        causal_context = candidate.atom.causal_do_expr.context
        assumptions = tuple(
            _string_values(
                causal_context.get("assumptions")
                if isinstance(causal_context, Mapping)
                else ()
            )
        )
        if parsed.get("grounding_relation_content_hash") != chain.cg1_content_hash:
            issues.append(
                {
                    "code": "candidate_grounding_relation_hash_mismatch",
                    "candidate_id": candidate.candidate_id,
                }
            )
        if parsed.get("grounding_decision_content_hash") != chain.cg2_content_hash:
            issues.append(
                {
                    "code": "candidate_grounding_decision_hash_mismatch",
                    "candidate_id": candidate.candidate_id,
                }
            )
        if f"grounding_relation_content_hash:{chain.cg1_content_hash}" not in assumptions:
            issues.append(
                {
                    "code": "candidate_atom_missing_grounding_relation_assumption",
                    "candidate_id": candidate.candidate_id,
                }
            )
        if chain.cg1_content_hash not in candidate.atom.provenance_refs:
            issues.append(
                {
                    "code": "candidate_atom_missing_grounding_relation_provenance",
                    "candidate_id": candidate.candidate_id,
                }
            )
    for disposition in result.grounding_dispositions:
        if disposition.status != "candidate_unverified":
            issues.append(
                {
                    "code": "grounding_disposition_not_shadow",
                    "proposal_id": disposition.proposal_id,
                }
            )
        if disposition.disposition == "shadow_bound":
            if not disposition.certificate_chain.cg1_content_hash:
                issues.append(
                    {
                        "code": "shadow_binding_without_grounding_relation_certificate",
                        "proposal_id": disposition.proposal_id,
                    }
                )
            if disposition.selected_relation not in {"exact", "certified-specialization"}:
                issues.append(
                    {
                        "code": "shadow_binding_without_identifying_grounding_relation",
                        "proposal_id": disposition.proposal_id,
                    }
                )
    for evidence in result.firewall_evidence:
        evidence_reached_authority = (
            evidence.authority_state != "candidate_unverified"
            or not evidence.blocked_from_authority
        )
        if evidence.evidence_kind in NOT_CERTIFICATE_KINDS and evidence_reached_authority:
            issues.append(
                {
                    "code": "not_certificate_reached_authority",
                    "evidence_kind": evidence.evidence_kind,
                }
            )
    for ranking in result.surrogate_rankings:
        if ranking.trust_level != "certified" and ranking.promotion_allowed:
            issues.append(
                {
                    "code": "surrogate_below_certified_promoted",
                    "candidate_id": ranking.candidate_id,
                }
            )
    if result.diversity_report.domain_mechanism_hardcode_detected:
        issues.append({"code": "domain_mechanism_hardcode_detected"})
    if result.status == "generated" and not result.diversity_report.diverse_enough:
        issues.append({"code": "insufficient_diverse_model_generated_candidates"})
    issues.extend(validate_design_generation_strangle_receipts())
    return tuple(issues)


def _content_bound_candidates(
    *,
    design_problem: DesignProblem,
    design_problem_ref: str,
    bundle: TrinityBundle,
    model_id: str,
    draft_path: GeneratorPath,
    formalizer_path: GeneratorPath,
    critic_path: GeneratorPath,
    critique_verdict: str,
    calls: tuple[LLMGenerationCall, ...],
    repo_root: Path,
    world_model_record_ref: str | None,
    reference: CredalReference | None,
    relation_engine: GroundingRelationEngine | None = None,
) -> tuple[tuple[ShadowGeneratedCandidate, ...], tuple[GroundingDispositionRecord, ...]]:
    world_record = None
    resolved_world_model_record_ref = world_model_record_ref
    if resolved_world_model_record_ref is None:
        world_record = production_composed_world_model_record(repo_root.resolve())
        resolved_world_model_record_ref = world_record.world_model_record_id
    if str(resolved_world_model_record_ref).startswith("world_model_record_pending:"):
        raise DesignGenerationError(
            "world_model_record_ref_pending",
            str(resolved_world_model_record_ref),
        )
    reference = reference or build_credal_reference(repo_root)
    relation_engine = relation_engine or GroundingRelationEngine(reference)
    bind_gate = GroundingBindGate(reference)
    admission_engine = GroundingAdmissionEngine(reference)
    phrasing_engine = GroundingPhrasingDefenseEngine(reference)
    if getattr(relation_engine, "reference", None) is reference:
        phrasing_engine._full_relation_engine = relation_engine
    active_controller = GroundingActiveController(reference)
    legacy = _legacy_exact_match_report(bundle, repo_root=repo_root)
    bundle_ref = gy_content_hash(bundle.model_dump(mode="json"))
    policy_spec_ref = gy_content_hash(bundle.policy_spec.model_dump(mode="json"))
    prompt_hashes = tuple(call.prompt_hash for call in calls)
    raw_responses = tuple(call.raw_llm_response for call in calls if call.raw_llm_response)
    candidates: list[ShadowGeneratedCandidate] = []
    dispositions: list[GroundingDispositionRecord] = []
    for index, intervention in enumerate(bundle.policy_spec.interventions):
        proposal_id = f"gy_n4.{intervention.intervention_id}"
        proposal = _grounding_proposal_for_intervention(
            intervention,
            design_problem=design_problem,
            bundle_ref=bundle_ref,
        )
        cg1 = relation_engine.certificate_for(proposal, proposal_id=proposal_id)
        cg2 = bind_gate.certificate_for(cg1)
        cg3 = admission_engine.decide(cg2, cg1_certificate=cg1)
        proxy_gap, quarantine = _cg4_proxy_gap_records(
            phrasing_engine,
            proposal,
            proposal_id=proposal_id,
        )
        cg5 = _cg5_action_certificate(
            active_controller,
            proposal=proposal,
            proposal_id=proposal_id,
            cg1=cg1,
            cg2=cg2,
            cg3=cg3,
            proxy_gap=proxy_gap,
        )
        legacy_disposition, legacy_issues = _legacy_linker_disposition(
            legacy,
            intervention_index=index,
        )
        bridge_records = _bridge_missing_records(
            cg3=cg3,
            proxy_gap=proxy_gap,
            quarantine=quarantine,
            cg5=cg5,
        )
        chain = _grounding_certificate_chain(
            cg1=cg1,
            cg2=cg2,
            cg3=cg3,
            proxy_gap=proxy_gap,
            quarantine=quarantine,
            cg5=cg5,
        )
        raw_candidate_hash = gy_content_hash(intervention.model_dump(mode="json"))
        if cg1.selected_relation in {"exact", "certified-specialization"}:
            try:
                candidate = _shadow_candidate_from_grounding(
                    design_problem=design_problem,
                    design_problem_ref=design_problem_ref,
                    intervention=intervention,
                    model_id=model_id,
                    draft_path=draft_path,
                    formalizer_path=formalizer_path,
                    critic_path=critic_path,
                    critique_verdict=critique_verdict,
                    bundle_ref=bundle_ref,
                    policy_spec_ref=policy_spec_ref,
                    prompt_hashes=prompt_hashes,
                    raw_responses=raw_responses,
                    cg1=cg1,
                    cg2=cg2,
                    resolved_world_model_record_ref=str(resolved_world_model_record_ref),
                    world_record=world_record,
                )
            except (InterventionSubstrateError, ValueError) as exc:
                dispositions.append(
                    GroundingDispositionRecord(
                        proposal_id=proposal_id,
                        raw_candidate_hash=raw_candidate_hash,
                        disposition="unknown_blocked",
                        selected_relation=cg1.selected_relation,
                        identified_atom_id=_selected_atom_id_from_cg1(cg1),
                        cg2_decision=cg2.decision,
                        cg2_reason=cg2.decisive_reason,
                        cg3_decision=cg3.decision,
                        cg3_reason=cg3.decisive_reason,
                        rejected_cause={
                            "code": "shadow_atom_binding_failed",
                            "error": str(exc),
                        },
                        legacy_exact_match=legacy_disposition,
                        legacy_linker_issues=legacy_issues,
                        certificate_chain=chain,
                        bridge_missing_records=bridge_records,
                    )
                )
                continue
            candidates.append(candidate)
            dispositions.append(
                GroundingDispositionRecord(
                    proposal_id=proposal_id,
                    candidate_id=candidate.candidate_id,
                    raw_candidate_hash=raw_candidate_hash,
                    disposition="shadow_bound",
                    selected_relation=cg1.selected_relation,
                    identified_atom_id=_selected_atom_id_from_cg1(cg1),
                    shadow_atom_content_hash=candidate.atom.content_hash,
                    cg2_decision=cg2.decision,
                    cg2_reason=cg2.decisive_reason,
                    cg3_decision=cg3.decision,
                    cg3_reason=cg3.decisive_reason,
                    legacy_exact_match=legacy_disposition,
                    legacy_linker_issues=legacy_issues,
                    certificate_chain=chain,
                    bridge_missing_records=bridge_records,
                )
            )
            continue
        if cg1.selected_relation == "false-analog":
            dispositions.append(
                GroundingDispositionRecord(
                    proposal_id=proposal_id,
                    raw_candidate_hash=raw_candidate_hash,
                    disposition="veto_false_analog",
                    selected_relation=cg1.selected_relation,
                    identified_atom_id=_selected_atom_id_from_cg1(cg1),
                    cg2_decision=cg2.decision,
                    cg2_reason=cg2.decisive_reason,
                    cg3_decision=cg3.decision,
                    cg3_reason=cg3.decisive_reason,
                    rejected_cause=_false_analog_cause(cg1),
                    legacy_exact_match=legacy_disposition,
                    legacy_linker_issues=legacy_issues,
                    certificate_chain=chain,
                    bridge_missing_records=bridge_records,
                )
            )
            continue
        disposition: GroundingDispositionKind = (
            "novel_cg3"
            if cg1.selected_relation == "novel-candidate" or cg2.decision == "novel_candidate"
            else "non_binding_abstain"
        )
        if cg1.selected_relation in {"unknown", "blocked"}:
            disposition = "unknown_blocked"
        dispositions.append(
            GroundingDispositionRecord(
                proposal_id=proposal_id,
                raw_candidate_hash=raw_candidate_hash,
                disposition=disposition,
                selected_relation=cg1.selected_relation,
                identified_atom_id=_selected_atom_id_from_cg1(cg1),
                cg2_decision=cg2.decision,
                cg2_reason=cg2.decisive_reason,
                cg3_decision=cg3.decision,
                cg3_reason=cg3.decisive_reason,
                rejected_cause=_non_binding_cause(cg1, cg2, cg3),
                legacy_exact_match=legacy_disposition,
                legacy_linker_issues=legacy_issues,
                certificate_chain=chain,
                bridge_missing_records=bridge_records,
            )
        )
    return tuple(candidates), tuple(dispositions)


def derive_lever_space_prompt_slice(
    design_problem: DesignProblem,
    *,
    repo_root: Path,
    reference: CredalReference | None = None,
) -> LeverSpacePromptSlice:
    """Derive the non-authoritative RAG-in-prompt lever slice from live owners."""

    try:
        bundle = load_l6_intervention_substrate(repo_root.resolve())
    except (InterventionSubstrateError, OSError, RuntimeError, ValueError) as exc:
        return LeverSpacePromptSlice(
            status="unavailable",
            failure_reason=f"owner_slice_derivation_failed:{type(exc).__name__}",
        )
    if reference is None:
        return LeverSpacePromptSlice(
            status="unavailable",
            failure_reason="owner_slice_derivation_failed:credal_reference_missing",
        )
    atom_facts = _reference_atom_prompt_facts(reference)
    entries: list[LeverSpaceSliceEntry] = []
    allowed_ops = {
        _id_token(item)
        for item in design_problem.candidate_lever_space.allowed_operator_kinds
        if str(item).strip()
    }
    problem_tokens = _design_problem_filter_tokens(design_problem)
    for operator_kind, raw in sorted(bundle.knob_dictionary.items()):
        raw_knob = _mapping(raw)
        if not raw_knob:
            continue
        aliases = _owner_aliases_for_operator(
            str(operator_kind),
            raw_knob=raw_knob,
            lex_intervention_map=bundle.lex_intervention_map,
        )
        if not _operator_in_prompt_slice(
            str(operator_kind),
            aliases=aliases,
            allowed_ops=allowed_ops,
            problem_tokens=problem_tokens,
        ):
            continue
        owner_fact = atom_facts.get(str(operator_kind), {})
        mechanism = _owner_mechanism_entry(bundle, str(operator_kind))
        target_world_slots = tuple(
            _string_values(mechanism.get("writes_slots"))
            or _string_values(owner_fact.get("target_world_slots"))
        )
        if not target_world_slots:
            continue
        parameter_key, parameter_bounds, unit = _compact_parameter_facts(raw_knob, mechanism)
        entries.append(
            LeverSpaceSliceEntry(
                operator_kind=str(operator_kind),
                aliases=aliases,
                target_world_slots=target_world_slots,
                unit=unit,
                parameter_key=parameter_key,
                parameter_bounds=parameter_bounds,
                sign_semantics=str(owner_fact.get("sign") or "") or None,
                expected_outcome_slots=tuple(_string_values(owner_fact.get("outcome_slots"))),
                effect_path=tuple(_string_values(owner_fact.get("effect_path"))),
                source_refs=(
                    bundle.source_refs.get("intervention_knob_dictionary", ""),
                    bundle.source_refs.get("owner_authority_bindings", ""),
                    bundle.source_content_hashes.get(
                        "intervention_knob_dictionary",
                        bundle.content_hash,
                    ),
                    bundle.source_content_hashes.get("owner_authority_bindings", ""),
                ),
            )
        )
    if not entries:
        return LeverSpacePromptSlice(
            status="unavailable",
            failure_reason="owner_slice_empty_after_design_problem_filter",
        )
    owner_refs = (
        bundle.source_refs.get("intervention_knob_dictionary", ""),
        bundle.source_refs.get("lex_intervention_map", ""),
        bundle.source_refs.get("slot_family_manifest", ""),
        bundle.source_refs.get("owner_authority_bindings", ""),
        bundle.source_content_hashes.get("intervention_knob_dictionary", ""),
        bundle.source_content_hashes.get("lex_intervention_map", ""),
        bundle.source_content_hashes.get("slot_family_manifest", ""),
        bundle.source_content_hashes.get("owner_authority_bindings", ""),
    )
    payload = {
        "design_problem_id": design_problem.design_problem_id,
        "entries": [
            entry.model_dump(mode="json")
            for entry in _cap_lever_space_entries(entries, design_problem=design_problem)
        ],
        "owner_refs": [item for item in owner_refs if item],
        "non_constraining": True,
    }
    return LeverSpacePromptSlice(
        status="derived",
        content_hash=gy_content_hash(payload),
        entries=tuple(LeverSpaceSliceEntry.model_validate(item) for item in payload["entries"]),
        owner_refs=tuple(item for item in owner_refs if item),
    )


def _with_lever_space_prompt_slice(
    scientist_frame: object,
    *,
    lever_space_prompt_slice: LeverSpacePromptSlice,
) -> object:
    if lever_space_prompt_slice.status != "derived":
        return scientist_frame
    payload = {
        "content_hash": lever_space_prompt_slice.content_hash,
        "non_constraining": True,
        "entries": [
            _compact_slice_entry_payload(entry) for entry in lever_space_prompt_slice.entries
        ],
    }
    success_criteria = dict(getattr(scientist_frame, "success_criteria", {}) or {})
    success_criteria["lever_space_prompt_slice"] = payload
    context = dict(getattr(scientist_frame, "context", {}) or {})
    context["lever_space_prompt_slice_ref"] = {
        "content_hash": lever_space_prompt_slice.content_hash,
        "non_constraining": True,
    }
    assumptions = (
        *tuple(getattr(scientist_frame, "assumptions", ()) or ()),
        "lever_space_prompt_slice:"
        + json.dumps(
            {
                "content_hash": lever_space_prompt_slice.content_hash,
                "non_constraining": True,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
    )
    return replace(
        scientist_frame,
        success_criteria=success_criteria,
        assumptions=assumptions,
        context=context,
    )


def _design_problem_filter_tokens(design_problem: DesignProblem) -> set[str]:
    text = " ".join(
        (
            design_problem.design_problem_id,
            design_problem.domain,
            design_problem.problem_statement,
            design_problem.outcome_of_interest.target_variable,
            design_problem.outcome_of_interest.metric_id,
            " ".join(item.description for item in design_problem.objectives),
            " ".join(item.description for item in design_problem.constraints),
            " ".join(item.name for item in design_problem.stakeholders),
            " ".join(
                f"{lever.operator_kind} {lever.instrument} {lever.target_slot}"
                for lever in design_problem.candidate_lever_space.candidate_levers
            ),
        )
    )
    return _tokens(text)


def _operator_in_prompt_slice(
    operator_kind: str,
    *,
    aliases: Sequence[str],
    allowed_ops: set[str],
    problem_tokens: set[str],
) -> bool:
    canonical = _id_token(operator_kind)
    if canonical in allowed_ops:
        return True
    terms = _tokens(" ".join((operator_kind, *aliases)).replace("_", " "))
    return bool(terms & problem_tokens)


def _owner_aliases_for_operator(
    operator_kind: str,
    *,
    raw_knob: Mapping[str, Any],
    lex_intervention_map: Mapping[str, Any],
) -> tuple[str, ...]:
    aliases: set[str] = set()
    for key in ("alias", "aliases", "label", "name", "description", "instrument"):
        aliases.update(_string_values(raw_knob.get(key)))
    for law_token, raw in lex_intervention_map.items():
        raw_map = _mapping(raw)
        knob_ids = _string_values(raw_map.get("knobs") or raw_map.get("knob_ids") or raw)
        if operator_kind in knob_ids:
            aliases.add(str(law_token))
            aliases.update(_string_values(raw_map.get("aliases") or raw_map.get("labels")))
    return tuple(sorted(item for item in aliases if item and item != operator_kind))


def _reference_atom_prompt_facts(reference: CredalReference) -> dict[str, dict[str, Any]]:
    facts: dict[str, dict[str, Any]] = {}
    for atom in GroundingRelationEngine(reference).reference_atoms:
        signature = atom.signature
        op = str(signature.op or "")
        if not op:
            continue
        current = facts.setdefault(
            op,
            {
                "target_world_slots": set(),
                "outcome_slots": set(),
                "effect_path": set(),
                "sign": signature.sign,
            },
        )
        current["target_world_slots"].update(signature.X_do)
        current["outcome_slots"].update(signature.outcome)
        current["effect_path"].update(signature.effect_path)
        if not current.get("sign") and signature.sign:
            current["sign"] = signature.sign
    return {
        op: {
            "target_world_slots": tuple(sorted(value["target_world_slots"])),
            "outcome_slots": tuple(sorted(value["outcome_slots"])),
            "effect_path": tuple(sorted(value["effect_path"])),
            "sign": value.get("sign"),
        }
        for op, value in sorted(facts.items())
    }


def _owner_mechanism_entry(
    bundle: object,
    operator_kind: str,
) -> Mapping[str, Any]:
    raw_manifest = _mapping(getattr(bundle, "world_mechanism_manifest", {}))
    mechanisms = _mapping(raw_manifest.get("mechanisms"))
    return _mapping(mechanisms.get(operator_kind))


def _compact_parameter_facts(
    raw_knob: Mapping[str, Any],
    mechanism: Mapping[str, Any],
) -> tuple[str | None, dict[str, Any], str | None]:
    param_path = str(raw_knob.get("param_path") or "").strip()
    parameter_key = param_path.rsplit(".", 1)[-1] if param_path else None
    params = _mapping(mechanism.get("params"))
    mechanism_param = _mapping(params.get(parameter_key or ""))
    unit = str(mechanism_param.get("unit_id") or raw_knob.get("unit") or "").strip() or None
    bounds: dict[str, Any] = {}
    for source_key, output_key in (
        ("min", "min"),
        ("min_value", "min"),
        ("max", "max"),
        ("max_value", "max"),
        ("type", "value_type"),
        ("value_type", "value_type"),
    ):
        value = raw_knob.get(source_key)
        if value is None:
            value = mechanism_param.get(source_key)
        if value is not None and output_key not in bounds:
            bounds[output_key] = value
    values = _string_values(raw_knob.get("values") or raw_knob.get("allowed_values"))
    if values:
        bounds["allowed_values"] = values[:8]
    return parameter_key, bounds, unit


def _cap_lever_space_entries(
    entries: Sequence[LeverSpaceSliceEntry],
    *,
    design_problem: DesignProblem,
) -> tuple[LeverSpaceSliceEntry, ...]:
    top_k = max(1, min(_int_env("POLISYOS_GY_N4_LEVER_SLICE_TOP_K", 20), 20))
    max_chars = max(800, _int_env("POLISYOS_GY_N4_LEVER_SLICE_MAX_CHARS", 3000))
    problem_tokens = _design_problem_filter_tokens(design_problem)

    def score(entry: LeverSpaceSliceEntry) -> tuple[int, str]:
        terms = _tokens(" ".join((entry.operator_kind, *entry.aliases)).replace("_", " "))
        return (len(terms & problem_tokens), entry.operator_kind)

    selected: list[LeverSpaceSliceEntry] = []
    running_chars = 2
    for entry in sorted(entries, key=score, reverse=True):
        compact = _compact_slice_entry_payload(entry)
        char_count = len(json.dumps(compact, sort_keys=True, separators=(",", ":")))
        if len(selected) >= top_k:
            break
        if selected and running_chars + char_count > max_chars:
            continue
        selected.append(entry)
        running_chars += char_count
    return tuple(selected)


def _compact_slice_entry_payload(entry: LeverSpaceSliceEntry) -> dict[str, Any]:
    payload = entry.model_dump(mode="json")
    return {key: value for key, value in payload.items() if value not in (None, {}, [], ())}


def _legacy_exact_match_report(bundle: TrinityBundle, *, repo_root: Path) -> dict[str, Any]:
    try:
        registries = intervention_generation_registry_bundle(repo_root)
        _linked_bundle, report = link_trinity(
            bundle,
            registries,
            allow_extra_params=True,
            strict=True,
        )
    except (InterventionSubstrateError, OSError, RuntimeError, ValueError) as exc:
        return {
            "ok": False,
            "issues": (
                {
                    "severity": "error",
                    "code": "legacy_exact_match_exception",
                    "message": str(exc),
                    "path": [],
                },
            ),
        }
    return {
        "ok": bool(report.ok),
        "issues": tuple(issue.model_dump(mode="json") for issue in report.issues),
    }


def _legacy_linker_disposition(
    legacy: Mapping[str, Any],
    *,
    intervention_index: int,
) -> tuple[LegacyLinkerDisposition, tuple[dict[str, Any], ...]]:
    raw_issues = tuple(
        item for item in _sequence(legacy.get("issues")) if isinstance(item, Mapping)
    )
    if legacy.get("ok") is True:
        return "would_bind", ()
    scoped = []
    for issue in raw_issues:
        path = _sequence(issue.get("path"))
        if intervention_index in path or not path:
            scoped.append(dict(issue))
    return "would_reject", tuple(scoped or [dict(item) for item in raw_issues])


def _grounding_proposal_for_intervention(
    intervention: InterventionSpec,
    *,
    design_problem: DesignProblem,
    bundle_ref: str,
) -> dict[str, Any]:
    target_hint = _candidate_declared_target_hint(intervention)
    signature = _candidate_grounding_signature(
        intervention,
        target_hint=target_hint,
    )
    raw_text = " ".join(
        item
        for item in (
            f"Generated policy candidate {intervention.intervention_id}.",
            f"operator={intervention.kind}.",
            f"target={json.dumps(intervention.target.model_dump(mode='json'), sort_keys=True)}.",
            f"params={json.dumps(intervention.params, sort_keys=True, default=str)}.",
            "measurement="
            f"{json.dumps(intervention.measurement_expectations, sort_keys=True, default=str)}.",
            f"do.target={target_hint}." if target_hint else "",
            f"candidate_signature={json.dumps(signature, sort_keys=True, default=str)}."
            if signature
            else "",
        )
        if item
    )
    proposal: dict[str, Any] = {
        "candidate_id": intervention.intervention_id,
        "proposal_id": f"gy_n4.{intervention.intervention_id}",
        "raw_text": raw_text,
        "bundle_ref": bundle_ref,
        "parsed_candidate": intervention.model_dump(mode="json"),
    }
    if signature:
        proposal["signature"] = signature
    return proposal


def _candidate_declared_target_hint(intervention: InterventionSpec) -> str:
    params = _mapping(intervention.params)
    for key in (
        "target_world_slot",
        "world_slot",
        "slot",
        "target_slot",
        "state_variable",
    ):
        text = str(params.get(key) or "").strip()
        if text:
            return text
    for note in intervention.notes:
        if "do.target=" in note:
            return note.split("do.target=", 1)[1].split()[0].strip(".,;")
    return ""


def _candidate_grounding_signature(
    intervention: InterventionSpec,
    *,
    target_hint: str,
) -> dict[str, Any]:
    target_slot = str(target_hint or "").strip()
    candidate_axes = _candidate_declared_axes(intervention)
    if not target_slot and not candidate_axes:
        return {}
    operator_kind = str(intervention.kind)
    params = _candidate_direct_params(intervention)
    signature = {
        "op": operator_kind,
        "target": [target_slot] if target_slot else [],
        "x_do": params,
        "params": params,
        "admissibility": "candidate_unverified",
    }
    if "sign" in candidate_axes:
        signature["sign"] = candidate_axes["sign"]
    if "scope" in candidate_axes:
        signature["scope"] = candidate_axes["scope"]
    if "population" in candidate_axes:
        signature["population"] = candidate_axes["population"]
    if "unit" in candidate_axes:
        signature["unit"] = candidate_axes["unit"]
    if "time" in candidate_axes:
        signature["time"] = candidate_axes["time"]
    if "estimand" in candidate_axes:
        signature["estimand"] = candidate_axes["estimand"]
    if "outcome" in candidate_axes:
        signature["outcome"] = list(_string_values(candidate_axes["outcome"]))
    if "effect_path" in candidate_axes:
        signature["effect_path"] = list(_string_values(candidate_axes["effect_path"]))
    return signature


def _candidate_direct_params(intervention: InterventionSpec) -> dict[str, Any]:
    params = dict(_mapping(intervention.params))
    for key in _CANDIDATE_AXIS_PARAM_KEYS | _CANDIDATE_TARGET_PARAM_KEYS:
        params.pop(key, None)
    return params


_CANDIDATE_TARGET_PARAM_KEYS = frozenset(
    {
        "target_world_slot",
        "world_slot",
        "slot",
        "target_slot",
        "state_variable",
    }
)
_CANDIDATE_AXIS_PARAM_KEYS = frozenset(
    {
        "sign",
        "direction",
        "effect_direction",
        "outcome",
        "outcome_slot",
        "outcome_slots",
        "expected_outcome",
        "expected_outcome_slot",
        "expected_outcome_slots",
        "effect_path",
        "estimand",
        "scope",
        "population",
        "unit",
        "time",
        "wm_version",
    }
)


def _candidate_declared_axes(intervention: InterventionSpec) -> dict[str, Any]:
    declared: dict[str, Any] = {}
    sources = (
        _mapping(intervention.params),
        _mapping(intervention.measurement_expectations),
        _note_axis_claims(intervention.notes),
    )
    for source in sources:
        _copy_axis(source, declared, "sign", ("sign", "direction", "effect_direction"))
        _copy_axis(source, declared, "estimand", ("estimand",))
        _copy_axis(source, declared, "scope", ("scope",))
        _copy_axis(source, declared, "population", ("population",))
        _copy_axis(source, declared, "unit", ("unit",))
        _copy_axis(source, declared, "time", ("time",))
        _copy_axis(source, declared, "wm_version", ("wm_version",))
        _copy_axis(
            source,
            declared,
            "outcome",
            (
                "outcome",
                "outcome_slot",
                "outcome_slots",
                "expected_outcome",
                "expected_outcome_slot",
                "expected_outcome_slots",
            ),
        )
        _copy_axis(source, declared, "effect_path", ("effect_path",))
    return declared


def _copy_axis(
    source: Mapping[str, Any],
    target: dict[str, Any],
    axis: str,
    keys: Sequence[str],
) -> None:
    if axis in target:
        return
    for key in keys:
        if key not in source:
            continue
        value = source.get(key)
        if axis in {"outcome", "effect_path"}:
            values = _string_values(value)
            if values:
                target[axis] = values
                return
        else:
            text = str(value or "").strip()
            if text:
                target[axis] = text
                return


def _note_axis_claims(notes: Sequence[str]) -> dict[str, Any]:
    claims: dict[str, Any] = {}
    for note in notes:
        for raw_part in str(note).replace(";", " ").split():
            if "=" not in raw_part:
                continue
            key, value = raw_part.split("=", 1)
            key = key.strip().strip(".,:")
            value = value.strip().strip(".,:")
            if key and value:
                claims[key] = tuple(item for item in value.split("|") if item) or value
    return claims


def _shadow_candidate_from_grounding(
    *,
    design_problem: DesignProblem,
    design_problem_ref: str,
    intervention: InterventionSpec,
    model_id: str,
    draft_path: GeneratorPath,
    formalizer_path: GeneratorPath,
    critic_path: GeneratorPath,
    critique_verdict: str,
    bundle_ref: str,
    policy_spec_ref: str,
    prompt_hashes: tuple[str, ...],
    raw_responses: tuple[str, ...],
    cg1: GroundingRelationCertificate,
    cg2: GroundingDecisionCertificate,
    resolved_world_model_record_ref: str,
    world_record: object | None,
) -> ShadowGeneratedCandidate:
    selected_atom_id = _selected_atom_id_from_cg1(cg1)
    selected_atom = _selected_atom_payload(cg1, selected_atom_id)
    signature = _mapping(selected_atom.get("signature"))
    operator_kind = _id_token(signature.get("op"))
    target_slots = tuple(_string_values(signature.get("X_do") or signature.get("target")))
    if not selected_atom_id or not operator_kind or not target_slots:
        raise DesignGenerationError("grounding_certificate_identifying_atom_missing")
    selected_intervention = _intervention_for_grounded_atom(
        intervention,
        operator_kind=operator_kind,
        cg1=cg1,
        cg2=cg2,
        selected_atom_id=selected_atom_id,
    )
    schedule_start, schedule_end = _schedule_bounds(selected_intervention.schedule)
    linked = LinkedIntervention(
        intervention_id=selected_intervention.intervention_id,
        mechanism_id=operator_kind,
        reads_slots=[],
        writes_slots=list(target_slots),
        schedule_start=schedule_start,
        schedule_end=schedule_end,
    )
    causal = NodeIntervention(
        assignments=tuple(
            VariableAssignment(
                variable=slot_id,
                value_expr=_slot_value_expr(operator_kind, selected_intervention.params, slot_id),
            )
            for slot_id in sorted(target_slots)
        )
    )
    query_target = QueryTarget(
        outcome_variables=(design_problem.outcome_of_interest.target_variable,),
        conditioning=(),
        functional=design_problem.outcome_of_interest.estimand,
    )
    selector_ref = intervention_atom_target_selector_ref(selected_intervention)
    context = InterventionContext(
        source_domain=f"{design_problem.design_problem_id}:observed",
        target_domain=design_problem.jurisdiction_time.region,
        selection_diagram_ref=selector_ref,
        available_data_refs=(
            (design_problem.model_spec_ref,) if design_problem.model_spec_ref is not None else ()
        ),
        assumptions=(
            "llm_candidate_shadow_only",
            "target_selector_content_bound",
            f"grounding_relation_certificate_id:{cg1.certificate_id}",
            f"grounding_relation_content_hash:{cg1.content_hash}",
            f"grounding_decision_certificate_id:{cg2.certificate_id}",
            f"grounding_decision_content_hash:{cg2.content_hash}",
            f"identified_cg0_atom:{selected_atom_id}",
        ),
    )
    atom = build_intervention_atom_binding(
        problem_frame_ref=design_problem_ref,
        policy_spec_ref=policy_spec_ref,
        intervention=selected_intervention,
        linked_intervention=linked,
        causal_intervention=causal,
        query_target=query_target,
        identification_plan=identification_plan_for_intervention(causal),
        causal_context=context,
        world_model_record_ref=resolved_world_model_record_ref,
        producer_ref=f"{DESIGN_GENERATION_PRODUCER_REF}.generate_design_candidates_under_a",
        provenance_refs=(bundle_ref, *prompt_hashes, cg1.content_hash, cg2.content_hash),
        operator_proof_type_map={operator_kind: "node"},
        mechanism_variable_map={operator_kind: target_slots},
        estimand_metric_id=design_problem.outcome_of_interest.metric_id,
        target_population=design_problem.jurisdiction_time.region,
        normalized_from=_normalization_record_for_grounded_candidate(
            intervention,
            normalized_intervention=selected_intervention,
            normalized_target_slots=target_slots,
            cg1=cg1,
        ),
        status="candidate_unverified",
    )
    if world_record is not None:
        resolve_intervention_atom_world_binding(atom, world_record)
    candidate_ref = gy_content_hash(
        {
            "atom_content_hash": atom.content_hash,
            "generator_path": _REAL_GENERATOR_PATH,
            "model_id": model_id,
            "cg1_content_hash": cg1.content_hash,
        }
    )
    return ShadowGeneratedCandidate(
        candidate_id=f"candidate_{candidate_ref.removeprefix('sha256:')[:16]}",
        status="candidate_unverified",
        generator_path="model_generated",
        atom=atom,
        diversity_key=_candidate_diversity_key(atom),
        provenance=GenerationCandidateProvenance(
            model_id=model_id,
            generator_path="model_generated",
            draft_generator_path=draft_path,
            formalizer_generator_path=formalizer_path,
            critic_generator_path=critic_path,
            prompt_hashes=prompt_hashes,
            raw_llm_responses=raw_responses,
            parsed_candidate={
                **intervention.model_dump(mode="json"),
                "grounding_relation_certificate_id": cg1.certificate_id,
                "grounding_relation_content_hash": cg1.content_hash,
                "grounding_decision_certificate_id": cg2.certificate_id,
                "grounding_decision_content_hash": cg2.content_hash,
                "identified_cg0_atom_id": selected_atom_id,
            },
            trinity_bundle_ref=bundle_ref,
            content_hash=atom.content_hash,
        ),
        critique_verdict=critique_verdict,
    )


def _intervention_for_grounded_atom(
    intervention: InterventionSpec,
    *,
    operator_kind: str,
    cg1: GroundingRelationCertificate,
    cg2: GroundingDecisionCertificate,
    selected_atom_id: str,
) -> InterventionSpec:
    payload = intervention.model_dump(mode="json")
    notes = [
        *list(payload.get("notes") or ()),
        f"cg1_certificate:{cg1.certificate_id}",
        f"cg1_hash:{cg1.content_hash}",
        f"cg2_certificate:{cg2.certificate_id}",
        f"cg2_hash:{cg2.content_hash}",
        f"identified_atom:{selected_atom_id}",
    ][:10]
    payload.update({"kind": operator_kind, "notes": notes})
    return InterventionSpec.model_validate(payload)


def _normalization_record_for_grounded_candidate(
    intervention: InterventionSpec,
    *,
    normalized_intervention: InterventionSpec,
    normalized_target_slots: Sequence[str],
    cg1: GroundingRelationCertificate,
) -> dict[str, Any] | None:
    original_slots = tuple(
        _string_values(_candidate_declared_target_hint(intervention))
    )
    normalized_slots = tuple(str(item) for item in normalized_target_slots if str(item))
    if (
        intervention.kind == normalized_intervention.kind
        and tuple(sorted(original_slots)) == tuple(sorted(normalized_slots))
    ):
        return None
    return {
        "original_kind": intervention.kind,
        "original_target_world_slots": original_slots,
        "normalized_kind": normalized_intervention.kind,
        "normalized_target_world_slots": normalized_slots,
        "grounding_relation": cg1.selected_relation,
        "grounding_relation_certificate_id": cg1.certificate_id,
        "grounding_relation_content_hash": cg1.content_hash,
    }


def _schedule_bounds(schedule: ScheduleSpec) -> tuple[int, int]:
    start = schedule.start_step
    if schedule.end_step is not None:
        return start, schedule.end_step
    return start, start + int(schedule.duration_steps or 1) - 1


def _selected_atom_id_from_cg1(cg1: GroundingRelationCertificate) -> str | None:
    selected = _mapping(cg1.cross_modal_witnesses).get("selected_pair")
    if isinstance(selected, Mapping):
        atom_id = str(selected.get("atom_id") or "")
        if atom_id:
            return atom_id
    for result in _sequence(_mapping(cg1.relation_set).get("candidate_results")):
        if not isinstance(result, Mapping):
            continue
        if str(result.get("selected_relation")) == cg1.selected_relation:
            atom_id = str(result.get("atom_id") or "")
            if atom_id:
                return atom_id
    return None


def _selected_atom_payload(
    cg1: GroundingRelationCertificate,
    selected_atom_id: str | None,
) -> Mapping[str, Any]:
    atoms = _mapping(cg1.atom_signature_or_bundle)
    if selected_atom_id and isinstance(atoms.get(selected_atom_id), Mapping):
        return _mapping(atoms[selected_atom_id])
    return {}


def _cg4_proxy_gap_records(
    phrasing_engine: GroundingPhrasingDefenseEngine,
    proposal: Mapping[str, Any],
    *,
    proposal_id: str,
) -> tuple[GroundingProxyGapRisk | None, QuarantineHandoffRecord | None]:
    try:
        run = phrasing_engine.run_pipeline(proposal, proposal_id=proposal_id)
        risk = phrasing_engine.detect_proxy_gap(run)
    except (RuntimeError, ValueError):
        return None, None
    if risk is None:
        return None, None
    return risk, phrasing_engine.quarantine_handoff(risk)


def _cg5_action_certificate(
    active_controller: GroundingActiveController,
    *,
    proposal: Mapping[str, Any],
    proposal_id: str,
    cg1: GroundingRelationCertificate,
    cg2: GroundingDecisionCertificate,
    cg3: GroundingAdmissionCertificate,
    proxy_gap: GroundingProxyGapRisk | None,
) -> GroundingActionCertificate | None:
    if (
        cg2.decision == "bind"
        and cg3.decision == "non_new"
        and proxy_gap is None
        and not cg2.open_obligations
    ):
        return None
    try:
        return active_controller.certificate_for(
            GroundingControllerCase(
                case_id=f"{proposal_id}.cg5",
                proposal=dict(proposal),
                cg1_certificate=cg1,
                cg2_certificate=cg2,
                cg3_certificate=cg3,
                proxy_gap_risk=proxy_gap,
            )
        )
    except (RuntimeError, ValueError):
        return None


def _grounding_certificate_chain(
    *,
    cg1: GroundingRelationCertificate,
    cg2: GroundingDecisionCertificate,
    cg3: GroundingAdmissionCertificate,
    proxy_gap: GroundingProxyGapRisk | None,
    quarantine: QuarantineHandoffRecord | None,
    cg5: GroundingActionCertificate | None,
) -> GroundingCertificateChain:
    ticket = cg5.selected_ticket if cg5 is not None else None
    return GroundingCertificateChain(
        cg1_certificate_id=cg1.certificate_id,
        cg1_content_hash=cg1.content_hash,
        cg2_certificate_id=cg2.certificate_id,
        cg2_content_hash=cg2.content_hash,
        cg3_certificate_id=cg3.certificate_id,
        cg3_content_hash=cg3.content_hash,
        cg4_proxy_gap_risk_id=proxy_gap.risk_id if proxy_gap else None,
        cg4_proxy_gap_content_hash=proxy_gap.content_hash if proxy_gap else None,
        cg4_quarantine_handoff_id=quarantine.handoff_id if quarantine else None,
        cg4_quarantine_handoff_hash=quarantine.content_hash if quarantine else None,
        cg5_action_certificate_id=cg5.certificate_id if cg5 else None,
        cg5_action_content_hash=cg5.content_hash if cg5 else None,
        cg5_ticket_id=ticket.ticket_id if ticket else None,
        cg5_ticket_hash=ticket.content_hash if ticket else None,
    )


def _bridge_missing_records(
    *,
    cg3: GroundingAdmissionCertificate,
    proxy_gap: GroundingProxyGapRisk | None,
    quarantine: QuarantineHandoffRecord | None,
    cg5: GroundingActionCertificate | None,
) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    if proxy_gap is not None and quarantine is not None:
        records.append(
            {
                "pattern": "bridge_missing",
                "owner": "CG4",
                "target_surface": quarantine.target_surface,
                "integration_status": quarantine.integration_status,
                "record_id": quarantine.handoff_id,
                "content_hash": quarantine.content_hash,
            }
        )
    if cg3.acquisition_need is not None:
        records.append(
            {
                "pattern": "bridge_missing",
                "owner": "CG3",
                "target_surface": cg3.acquisition_need.owner,
                "integration_status": "handoff_artifact_gy_n7_direct_intake_not_wired",
                "record_id": cg3.acquisition_need.blocker_id,
                "needed_evidence": list(cg3.acquisition_need.needed_evidence),
            }
        )
    if cg5 is not None and cg5.selected_ticket is not None:
        records.append(
            {
                "pattern": "bridge_missing",
                "owner": "CG5",
                "target_surface": cg5.selected_ticket.target_surface,
                "integration_status": cg5.selected_ticket.integration_status,
                "record_id": cg5.selected_ticket.ticket_id,
                "content_hash": cg5.selected_ticket.content_hash,
            }
        )
    return tuple(records)


def _false_analog_cause(cg1: GroundingRelationCertificate) -> dict[str, Any]:
    critical = set(cg1.critical_contradictions)
    witnesses = [
        witness.model_dump(mode="json")
        for witness in cg1.axis_witnesses
        if witness.axis in critical or witness.relation == "contradiction"
    ]
    return {
        "reason": "proposal_level_false_analog_veto",
        "critical_contradictions": list(cg1.critical_contradictions),
        "witnesses": witnesses,
    }


def _non_binding_cause(
    cg1: GroundingRelationCertificate,
    cg2: GroundingDecisionCertificate,
    cg3: GroundingAdmissionCertificate,
) -> dict[str, Any]:
    return {
        "cg1_relation": cg1.selected_relation,
        "cg1_critical_contradictions": list(cg1.critical_contradictions),
        "cg1_unresolved_axes": list(cg1.unresolved_axes),
        "cg2_decision": cg2.decision,
        "cg2_reason": cg2.decisive_reason,
        "cg2_open_obligations": list(cg2.open_obligations),
        "cg3_decision": cg3.decision,
        "cg3_reason": cg3.decisive_reason,
        "cg3_open_obligations": list(cg3.open_obligations),
    }


def _grounding_disposition_summary(
    dispositions: Sequence[GroundingDispositionRecord],
) -> GroundingDispositionSummary:
    counts = Counter(item.disposition for item in dispositions)
    legacy = Counter(item.legacy_exact_match for item in dispositions)
    return GroundingDispositionSummary(
        total_candidates=len(dispositions),
        shadow_bound=counts["shadow_bound"],
        novel_cg3=counts["novel_cg3"],
        veto_false_analog=counts["veto_false_analog"],
        abstain_or_blocked=counts["non_binding_abstain"] + counts["unknown_blocked"],
        legacy_exact_match_would_bind=legacy["would_bind"],
        legacy_exact_match_would_reject=legacy["would_reject"],
    )


def _terminal_result(
    *,
    design_problem_ref: str,
    model_id: str,
    preflight: ModelProfilePreflight,
    status: GenerationStatus,
    reason: str,
    organ: str,
    min_diverse_candidates: int,
    llm_calls: tuple[LLMGenerationCall, ...] = (),
    lever_space_prompt_slice: LeverSpacePromptSlice | None = None,
    effective_runtime_config: EffectiveGenerationRuntimeConfig | None = None,
) -> GenerationUnderAResult:
    return GenerationUnderAResult(
        status=status,
        design_problem_ref=design_problem_ref,
        model_id=model_id,
        preflight=preflight,
        degraded_artifacts=(
            DegradedGenerationArtifact(reason=reason, organ=organ),
        ),
        diversity_report=GenerationDiversityReport(
            min_required=min_diverse_candidates,
            candidate_count=0,
            unique_diversity_key_count=0,
            diverse_enough=False,
        ),
        llm_calls=llm_calls,
        firewall_evidence=default_firewall_evidence(),
        strangle_receipts=design_generation_strangle_receipts(),
        lever_space_prompt_slice=lever_space_prompt_slice
        or LeverSpacePromptSlice(status="unavailable", failure_reason="not_attempted"),
        effective_runtime_config=effective_runtime_config,
    )


def _draft_generator_path(
    calls: Sequence[LLMGenerationCall],
    draft: object,
) -> GeneratorPath:
    if not calls:
        return "degraded_mock_fallback"
    first_call = calls[0]
    if not isinstance(first_call.parsed_json, Mapping):
        return "degraded_mock_fallback"
    if not getattr(draft, "raw_llm_response", None):
        return "degraded_mock_fallback"
    if not getattr(draft, "interventions", None):
        return "degraded_mock_fallback"
    return "model_generated"


def _candidate_diversity_key(atom: InterventionAtomBinding) -> tuple[str, str, str, str]:
    return (
        atom.operator_kind.trinity_kind,
        atom.target_selector.selector_content_ref,
        atom.direct_effect_bundle.mechanism_id,
        gy_content_hash(atom.direct_effect_bundle.params),
    )


def _slot_value_expr(kind: str, params: Mapping[str, Any], slot_id: str) -> str:
    return (
        f"do({slot_id}) via {kind} "
        f"params_ref={gy_content_hash(dict(params)).removeprefix('sha256:')[:16]}"
    )


def _try_parse_json(content: str) -> object | None:
    try:
        return extract_llm_json(content)
    except json.JSONDecodeError:
        return None


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in (
            item.strip(".,:;()[]{}").lower()
            for item in text.replace("_", " ").replace(".", " ").split()
        )
        if token
    }


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return value
    return ()


def _string_values(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    if isinstance(value, Mapping):
        values: list[str] = []
        for item in value.values():
            values.extend(_string_values(item))
        return tuple(values)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return tuple(str(item).strip() for item in value if str(item).strip())
    text = str(value or "").strip()
    return (text,) if text else ()


def _id_token(value: object) -> str:
    cleaned = "".join(
        char if char.isalnum() or char == "_" else "_"
        for char in str(value or "").strip().casefold()
    ).strip("_")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"generated_{cleaned}"
    return cleaned[:80]


def _observation_manifest_families(manifest: Mapping[str, Any]) -> tuple[str, ...]:
    routes = manifest.get("routes")
    if isinstance(routes, Mapping):
        return tuple(sorted(str(item) for item in routes))
    if isinstance(routes, Sequence) and not isinstance(routes, str | bytes):
        families: list[str] = []
        for item in routes:
            if not isinstance(item, Mapping):
                continue
            family = item.get("family") or item.get("observation_family")
            if family is not None:
                families.append(str(family))
        return tuple(sorted(set(families)))
    families = manifest.get("families")
    if isinstance(families, Sequence) and not isinstance(families, str | bytes):
        return tuple(sorted(str(item) for item in families))
    return ()


def _resolved_surrogate_owner_feature_refs() -> tuple[str, ...]:
    """Resolve the real NCM/GCM/SKG owner contracts used for N4 search ranking."""

    refs: list[str] = []
    for owner_ref in _SEARCH_SURROGATE_OWNERS:
        module_name, symbol_name, owner = _resolve_owner_symbol(owner_ref)
        signature = getattr(owner, "signature", None)
        if signature is not None:
            refs.append(
                "foundry_method:"
                f"{module_name}.{symbol_name}:"
                f"{getattr(signature, 'name', symbol_name)}@"
                f"{getattr(signature, 'version', 'unknown')}"
            )
        if hasattr(owner, "resolve_grounded_causal_prior"):
            refs.append(f"skg_prior:{module_name}.{symbol_name}.resolve_grounded_causal_prior")
        if hasattr(owner, "parameter_estimate_value_outer_set"):
            refs.append(f"skg_prior:{module_name}.{symbol_name}.parameter_estimate_value_outer_set")
        if symbol_name == "load_l6_intervention_substrate":
            refs.append(f"l6_manifest_owner:{module_name}.{symbol_name}")
    return tuple(refs)


def _resolve_owner_symbol(owner_ref: str) -> tuple[str, str, object]:
    module_name, separator, symbol_name = owner_ref.rpartition(".")
    if not separator or not module_name or not symbol_name:
        raise DesignGenerationError("surrogate_owner_ref_unresolved", owner_ref)
    try:
        owner = getattr(importlib.import_module(module_name), symbol_name)
    except (AttributeError, ImportError, ModuleNotFoundError) as exc:
        raise DesignGenerationError("surrogate_owner_ref_unresolved", owner_ref) from exc
    return module_name, symbol_name, owner


def _model_variant_id(model_id: str) -> str:
    cleaned = "".join(char if char.isalnum() else "_" for char in model_id.lower()).strip("_")
    return cleaned[:80] or "gy_n4_model"


def run_generate_design_candidates_under_a(
    design_problem: DesignProblem,
    *,
    model_id: str,
    llm_client: object | None = None,
    repo_root: Path | None = None,
    min_diverse_candidates: int = 3,
) -> GenerationUnderAResult:
    """Synchronous wrapper for contract validators."""

    return asyncio.run(
        generate_design_candidates_under_a(
            design_problem,
            model_id=model_id,
            llm_client=llm_client,
            repo_root=repo_root,
            min_diverse_candidates=min_diverse_candidates,
        )
    )


__all__ = [
    "DESIGN_GENERATION_ARTIFACT_KIND",
    "DESIGN_GENERATION_CONTRACT_SCHEMA_VERSION",
    "DESIGN_GENERATION_PRODUCER_REF",
    "DESIGN_GENERATION_SCHEMA_VERSION",
    "NOT_CERTIFICATE_KINDS",
    "SUPPORTED_GENERATION_MODEL_IDS",
    "DegradedGenerationArtifact",
    "DesignGenerationError",
    "DesignGenerationOrganRun",
    "FirewallEvidence",
    "GenerationCandidateProvenance",
    "GenerationDiversityReport",
    "GenerationUnderAResult",
    "GroundingDispositionKind",
    "LLMGenerationCall",
    "ModelProfilePreflight",
    "RecordingLLMClient",
    "ShadowGeneratedCandidate",
    "SurrogateRanking",
    "default_firewall_evidence",
    "design_generation_strangle_receipts",
    "firewall_issues_for_result",
    "generate_design_candidate_bundle_under_a",
    "generate_design_candidates_under_a",
    "measure_generation_diversity",
    "preflight_model_profile",
    "rank_shadow_candidates_with_graph_causal_surrogate",
    "run_generate_design_candidates_under_a",
    "validate_design_generation_strangle_receipts",
]
