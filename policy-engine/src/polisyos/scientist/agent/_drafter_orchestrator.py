"""Multipass self-critique drafter orchestration.

The ``MultiPassLLMDrafter`` class composes four mixin base classes that
provide deterministic checks, LLM integration, response parsing, and
formatting/constitution logic. This module contains the high-level
orchestration (``__init__``, ``draft_policy``, and the multi-pass
pipeline).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterable
from dataclasses import replace
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.core.llm import retry_async
from polisyos.core.observability import get_metrics, get_tracer
from polisyos.ir.loading.norm_pack import NormPack
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.scientist.agent.code_verifier import (
    CodeVerificationSandbox,
    SandboxConfig,
)
from polisyos.scientist.agent.constitution import ConstitutionGenerator
from polisyos.scientist.agent.knowledge_base import CriticKnowledgeBase
from polisyos.scientist.agent.memory import ShortTermMemory
from polisyos.scientist.agent.prompts import get_self_critique_prompt
from polisyos.scientist.agent.protocols import (
    CritiqueReport,
    DrafterAgent,
    DraftResult,
    ProblemFrame,
)
from polisyos.scientist.agent.rag import CASRAGIndex, RAGConfig, format_few_shot_block
from polisyos.scientist.orchestration.engine.budget import BudgetState
from polisyos.scientist.orchestration.engine.convergence import (
    ConvergenceDetector,
    ConvergenceObservation,
    ConvergenceState,
    ConvergenceValidationError,
)

from ._drafter_formatting import _DrafterFormattingMixin
from ._drafter_llm import _DrafterLLMMixin
from ._drafter_observations import (
    confidence_request_ref,
    confidence_subject_ref,
    observe_candidate_confidence,
)
from ._drafter_parsing import _DrafterParsingMixin
from ._drafter_passes import _DrafterPassesMixin
from .drafter_clients import LLMDrafterAgent
from .drafter_models import (
    _SEVERITY_ORDER,
    FindingSeverity,
    MultiPassConfig,
    PassExecution,
    PassFinding,
)

logger = get_logger(__name__)

__all__ = ["MultiPassLLMDrafter"]


def _default_tracer():
    return get_tracer()


def _default_metrics():
    return get_metrics()


class MultiPassLLMDrafter(
    _DrafterPassesMixin,
    _DrafterLLMMixin,
    _DrafterParsingMixin,
    _DrafterFormattingMixin,
):
    """
    Multipass self-critique wrapper over an existing DrafterAgent.

    Behavior:
    - Pass 1: delegate to inner drafter.
    - Pass 1.5: deterministic checks (no LLM call).
    - Pass 2: side effects check.
    - Pass 3: constraints verification.
    - Pass 4: consolidation.
    """

    def __init__(
        self,
        inner: DrafterAgent,
        *,
        config: MultiPassConfig | None = None,
        memory: ShortTermMemory | None = None,
        llm_client: Any | None = None,
        rag_index: CASRAGIndex | None = None,
        rag_config: RAGConfig | None = None,
        code_verifier: CodeVerificationSandbox | None = None,
        constitution_generator: ConstitutionGenerator | None = None,
        knowledge_base: CriticKnowledgeBase | None = None,
        constitution_norm_pack: NormPack | None = None,
        constitution_model_spec: ModelSpec | None = None,
        tracer: Any | None = None,
        metrics: Any | None = None,
        convergence_budget_state: BudgetState | None = None,
    ) -> None:
        self._config = config or MultiPassConfig()
        if self._config.convergence is not None and type(inner) is LLMDrafterAgent:
            inner = inner._with_convergence_observations()
        self._inner = inner
        self._memory = memory
        self._llm = self._resolve_llm(llm_client, self._inner)
        self._rag_index = rag_index
        self._rag_config = rag_config or RAGConfig(
            enabled=self._config.rag_enabled,
            similarity_threshold=self._config.rag_similarity_threshold,
            top_k=self._config.rag_top_k,
            domain_filter=self._config.rag_domain_filter,
            max_few_shot_chars=self._config.rag_max_few_shot_chars,
            freeze_snapshot_per_run=self._config.rag_freeze_snapshot_per_run,
        )
        self._frozen_rag_snapshot_ref: str | None = (
            rag_index.snapshot_ref if rag_index is not None else None
        )
        self._code_verifier = code_verifier
        if self._code_verifier is None and self._config.code_verification_enabled:
            self._code_verifier = CodeVerificationSandbox(
                SandboxConfig(timeout_seconds=self._config.code_verification_timeout_s)
            )
        self._constitution_gen = constitution_generator or ConstitutionGenerator(
            max_rules_per_section=self._config.constitution_max_rules_per_section,
            max_total_rules=self._config.constitution_max_total_rules,
            max_prompt_chars=self._config.constitution_max_prompt_chars,
            include_domain_rules=self._config.constitution_include_domain_rules,
            pitfall_min_occurrences=self._config.constitution_pitfall_min_occurrences,
        )
        self._knowledge_base = knowledge_base
        self._constitution_norm_pack = constitution_norm_pack
        self._constitution_model_spec = constitution_model_spec
        self._last_constitution_hash: str | None = None
        self._tracer = tracer
        self._metrics = metrics
        self._convergence_budget_state = convergence_budget_state

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def draft_policy(
        self,
        problem_frame: ProblemFrame,
        *,
        data_context: dict[str, Any] | None = None,
        hints: list[str] | None = None,
        prior_drafts: list[DraftResult] | None = None,
    ) -> DraftResult:
        try:
            return await self._draft_policy_impl(
                problem_frame,
                data_context=data_context,
                hints=hints,
                prior_drafts=prior_drafts,
            )
        except ConvergenceValidationError:
            # Invalid configured stopping/resource inputs must not trigger another LLM call.
            raise
        except Exception as exc:
            logger.exception("Multipass drafter failed; fallback to single-pass: %s", exc)
            return await self._inner.draft_policy(
                problem_frame,
                data_context=data_context,
                hints=hints,
                prior_drafts=prior_drafts,
            )

    async def refine_draft(
        self,
        draft: DraftResult,
        critique: CritiqueReport,
    ) -> DraftResult:
        return await self._inner.refine_draft(draft, critique)

    @property
    def last_constitution_hash(self) -> str | None:
        return self._last_constitution_hash

    # ------------------------------------------------------------------
    # Multi-pass pipeline
    # ------------------------------------------------------------------

    async def _draft_policy_impl(
        self,
        problem_frame: ProblemFrame,
        *,
        data_context: dict[str, Any] | None = None,
        hints: list[str] | None = None,
        prior_drafts: list[DraftResult] | None = None,
    ) -> DraftResult:
        tracer = self._tracer if self._tracer is not None else _default_tracer()
        metrics = self._metrics if self._metrics is not None else _default_metrics()
        pass_results: list[PassExecution] = []
        cumulative_cost_usd = 0.0
        extra_llm_calls = 0
        early_exit = False
        stop_reason = ""
        convergence_detector: ConvergenceDetector | None = None
        if self._config.convergence is not None:
            convergence_detector = ConvergenceDetector(
                self._config.convergence, budget_state=self._convergence_budget_state
            )

        with tracer.start_as_current_span(
            "drafter.multi_pass",
            attributes={
                "polisyos.drafter.max_passes": self._config.max_passes,
                "polisyos.drafter.budget_limit_usd": self._config.budget_limit_usd,
                "polisyos.drafter.early_exit_confidence": self._config.early_exit_confidence,
                "polisyos.drafter.problem_frame_id": problem_frame.frame_id,
            },
        ) as parent_span:
            pass1 = await self._execute_pass1(
                problem_frame,
                data_context=data_context,
                hints=hints,
                prior_drafts=prior_drafts,
            )
            pass_results.append(pass1)
            if pass1.draft is None:
                raise RuntimeError("Pass 1 did not produce a draft")
            current_draft = pass1.draft
            cumulative_cost_usd += pass1.cost_usd

            deterministic = self._execute_deterministic_checks(current_draft)
            pass_results.append(deterministic)
            current_draft = self._update_confidence(
                current_draft,
                deterministic.findings,
                confidence_adjustment=None,
            )

            all_findings: list[PassFinding] = list(deterministic.findings)

            if convergence_detector is not None:
                current_draft, conv_state = self._record_current_convergence(
                    convergence_detector, problem_frame, pass1, current_draft
                )
                if conv_state.should_stop:
                    stop_reason = self._convergence_stop_reason(conv_state)
                    for number, name in (
                        (2, "side_effects_check"),
                        (3, "constraint_verify"),
                        (4, "consolidation"),
                    ):
                        if number <= self._config.max_passes:
                            pass_results.append(self._skipped_pass(name, number, stop_reason))
                    return self._finalize(
                        problem_frame=problem_frame,
                        draft=current_draft,
                        pass_results=pass_results,
                        cumulative_cost_usd=cumulative_cost_usd,
                        extra_llm_calls=extra_llm_calls,
                        early_exit=True,
                        stop_reason=stop_reason,
                        parent_span=parent_span,
                        metrics=metrics,
                    )

            if self._config.max_passes <= 1:
                return self._finalize(
                    problem_frame=problem_frame,
                    draft=current_draft,
                    pass_results=pass_results,
                    cumulative_cost_usd=cumulative_cost_usd,
                    extra_llm_calls=extra_llm_calls,
                    early_exit=early_exit,
                    stop_reason=stop_reason,
                    parent_span=parent_span,
                    metrics=metrics,
                )

            can_continue, stop_reason = self._can_run_next_pass(
                cumulative_cost_usd=cumulative_cost_usd,
                extra_llm_calls=extra_llm_calls,
            )
            if not can_continue:
                pass_results.append(self._skipped_pass("side_effects_check", 2, stop_reason))
                if self._config.max_passes >= 3:
                    pass_results.append(self._skipped_pass("constraint_verify", 3, stop_reason))
                if self._config.max_passes >= 4:
                    pass_results.append(self._skipped_pass("consolidation", 4, stop_reason))
                return self._finalize(
                    problem_frame=problem_frame,
                    draft=current_draft,
                    pass_results=pass_results,
                    cumulative_cost_usd=cumulative_cost_usd,
                    extra_llm_calls=extra_llm_calls,
                    early_exit=early_exit,
                    stop_reason=stop_reason,
                    parent_span=parent_span,
                    metrics=metrics,
                )

            pass2 = await self._execute_critique_pass(
                pass_name="side_effects_check",
                pass_number=2,
                pass_type="side_effects",
                problem_frame=problem_frame,
                draft=current_draft,
                previous_findings=(),
            )
            pass_results.append(pass2)
            if pass2.executed:
                extra_llm_calls += 1
                cumulative_cost_usd += pass2.cost_usd
                all_findings.extend(pass2.findings)
                current_draft = self._update_confidence(
                    current_draft,
                    pass2.findings,
                    confidence_adjustment=pass2.confidence_adjustment,
                )

            # Consume only this executed, parsed producer observation.
            if convergence_detector is not None:
                current_draft, conv_state = self._record_current_convergence(
                    convergence_detector, problem_frame, pass2, current_draft
                )
                if conv_state.should_stop:
                    early_exit = True
                    stop_reason = self._convergence_stop_reason(conv_state)
                    remaining = list(range(3, self._config.max_passes + 1))
                    pass_names = {3: "constraint_verify", 4: "consolidation"}
                    for pn in remaining:
                        if pn in pass_names:
                            pass_results.append(self._skipped_pass(pass_names[pn], pn, stop_reason))
                    return self._finalize(
                        problem_frame=problem_frame,
                        draft=current_draft,
                        pass_results=pass_results,
                        cumulative_cost_usd=cumulative_cost_usd,
                        extra_llm_calls=extra_llm_calls,
                        early_exit=early_exit,
                        stop_reason=stop_reason,
                        parent_span=parent_span,
                        metrics=metrics,
                    )

            if self._should_early_exit(current_draft, all_findings):
                early_exit = True
                pass_results.append(self._skipped_pass("constraint_verify", 3, "early_exit"))
                pass_results.append(self._skipped_pass("consolidation", 4, "early_exit"))
                stop_reason = "early_exit"
                return self._finalize(
                    problem_frame=problem_frame,
                    draft=current_draft,
                    pass_results=pass_results,
                    cumulative_cost_usd=cumulative_cost_usd,
                    extra_llm_calls=extra_llm_calls,
                    early_exit=early_exit,
                    stop_reason=stop_reason,
                    parent_span=parent_span,
                    metrics=metrics,
                )

            if self._config.max_passes <= 2:
                return self._finalize(
                    problem_frame=problem_frame,
                    draft=current_draft,
                    pass_results=pass_results,
                    cumulative_cost_usd=cumulative_cost_usd,
                    extra_llm_calls=extra_llm_calls,
                    early_exit=early_exit,
                    stop_reason=stop_reason,
                    parent_span=parent_span,
                    metrics=metrics,
                )

            can_continue, stop_reason = self._can_run_next_pass(
                cumulative_cost_usd=cumulative_cost_usd,
                extra_llm_calls=extra_llm_calls,
            )
            if not can_continue:
                pass_results.append(self._skipped_pass("constraint_verify", 3, stop_reason))
                if self._config.max_passes >= 4:
                    pass_results.append(self._skipped_pass("consolidation", 4, stop_reason))
                return self._finalize(
                    problem_frame=problem_frame,
                    draft=current_draft,
                    pass_results=pass_results,
                    cumulative_cost_usd=cumulative_cost_usd,
                    extra_llm_calls=extra_llm_calls,
                    early_exit=early_exit,
                    stop_reason=stop_reason,
                    parent_span=parent_span,
                    metrics=metrics,
                )

            pass3 = await self._execute_critique_pass(
                pass_name="constraint_verify",
                pass_number=3,
                pass_type="constraint_verify",
                problem_frame=problem_frame,
                draft=current_draft,
                previous_findings=all_findings,
            )
            pass_results.append(pass3)
            if pass3.executed:
                extra_llm_calls += 1
                cumulative_cost_usd += pass3.cost_usd
                if self._config.code_verification_enabled:
                    pass3 = self._augment_pass3_with_code_verification(
                        pass3,
                        draft=current_draft,
                        problem_frame=problem_frame,
                    )
                    pass_results[-1] = pass3
                all_findings.extend(pass3.findings)
                current_draft = self._update_confidence(
                    current_draft,
                    pass3.findings,
                    confidence_adjustment=pass3.confidence_adjustment,
                )

            # Consume only this executed, parsed producer observation.
            if convergence_detector is not None:
                current_draft, conv_state = self._record_current_convergence(
                    convergence_detector, problem_frame, pass3, current_draft
                )
                if conv_state.should_stop:
                    early_exit = True
                    stop_reason = self._convergence_stop_reason(conv_state)
                    pass_results.append(self._skipped_pass("consolidation", 4, stop_reason))
                    return self._finalize(
                        problem_frame=problem_frame,
                        draft=current_draft,
                        pass_results=pass_results,
                        cumulative_cost_usd=cumulative_cost_usd,
                        extra_llm_calls=extra_llm_calls,
                        early_exit=early_exit,
                        stop_reason=stop_reason,
                        parent_span=parent_span,
                        metrics=metrics,
                    )

            if self._config.max_passes <= 3:
                return self._finalize(
                    problem_frame=problem_frame,
                    draft=current_draft,
                    pass_results=pass_results,
                    cumulative_cost_usd=cumulative_cost_usd,
                    extra_llm_calls=extra_llm_calls,
                    early_exit=early_exit,
                    stop_reason=stop_reason,
                    parent_span=parent_span,
                    metrics=metrics,
                )

            if not all_findings:
                pass_results.append(
                    self._skipped_pass("consolidation", 4, "no_findings_to_consolidate")
                )
                stop_reason = "no_findings_to_consolidate"
                return self._finalize(
                    problem_frame=problem_frame,
                    draft=current_draft,
                    pass_results=pass_results,
                    cumulative_cost_usd=cumulative_cost_usd,
                    extra_llm_calls=extra_llm_calls,
                    early_exit=early_exit,
                    stop_reason=stop_reason,
                    parent_span=parent_span,
                    metrics=metrics,
                )

            can_continue, stop_reason = self._can_run_next_pass(
                cumulative_cost_usd=cumulative_cost_usd,
                extra_llm_calls=extra_llm_calls,
            )
            if not can_continue:
                pass_results.append(self._skipped_pass("consolidation", 4, stop_reason))
                return self._finalize(
                    problem_frame=problem_frame,
                    draft=current_draft,
                    pass_results=pass_results,
                    cumulative_cost_usd=cumulative_cost_usd,
                    extra_llm_calls=extra_llm_calls,
                    early_exit=early_exit,
                    stop_reason=stop_reason,
                    parent_span=parent_span,
                    metrics=metrics,
                )

            pass4 = await self._execute_consolidation_pass(
                problem_frame=problem_frame,
                draft=current_draft,
                all_findings=all_findings,
            )
            pass_results.append(pass4)
            if pass4.executed and pass4.draft is not None:
                extra_llm_calls += 1
                cumulative_cost_usd += pass4.cost_usd
                current_draft = pass4.draft

            return self._finalize(
                problem_frame=problem_frame,
                draft=current_draft,
                pass_results=pass_results,
                cumulative_cost_usd=cumulative_cost_usd,
                extra_llm_calls=extra_llm_calls,
                early_exit=early_exit,
                stop_reason=stop_reason,
                parent_span=parent_span,
                metrics=metrics,
            )

    # ------------------------------------------------------------------
    # Pass 1: naive draft
    # ------------------------------------------------------------------

    async def _execute_pass1(
        self,
        problem_frame: ProblemFrame,
        *,
        data_context: dict[str, Any] | None,
        hints: list[str] | None,
        prior_drafts: list[DraftResult] | None,
    ) -> PassExecution:
        tracer = self._tracer if self._tracer is not None else _default_tracer()
        started = time.perf_counter()
        with tracer.start_as_current_span(
            "drafter.pass.naive_draft",
            attributes={
                "polisyos.drafter.pass_name": "naive_draft",
                "polisyos.drafter.pass_number": 1,
            },
        ) as span:
            effective_hints = list(hints or [])
            prepared_problem_frame = problem_frame

            if self._config.constitution_enabled:
                constitution_started = time.perf_counter()
                constitution = self._build_constitution(problem_frame)
                constitution_duration = max(0.0, time.perf_counter() - constitution_started)
                if constitution is not None:
                    constitution_text = constitution.to_system_prompt()
                    self._last_constitution_hash = constitution.compute_hash()
                    prepared_problem_frame = self._inject_constitution_context(
                        problem_frame,
                        constitution=constitution,
                    )
                    if prepared_problem_frame is problem_frame:
                        effective_hints.append(constitution_text)
                    span.set_attribute(
                        "polisyos.constitution.hash",
                        self._last_constitution_hash,
                    )
                    span.set_attribute(
                        "polisyos.constitution.rules_count",
                        constitution.total_rules,
                    )
                    constitution_metrics = (
                        self._metrics if self._metrics is not None else _default_metrics()
                    )
                    constitution_metrics.record_constitution_generated(
                        domain=constitution.domain,
                        duration_seconds=constitution_duration,
                        section_counts={
                            section.section_type: len(section.rules)
                            for section in constitution.sections
                        },
                    )
                else:
                    self._last_constitution_hash = None

            if self._rag_config.enabled and self._rag_index is not None:
                rag_results = self._rag_index.search(
                    problem_frame,
                    top_k=self._rag_config.top_k,
                    domain_filter=self._rag_config.domain_filter,
                    similarity_threshold=self._rag_config.similarity_threshold,
                )
                span.set_attribute("polisyos.drafter.rag_results", len(rag_results))
                if rag_results:
                    few_shot = format_few_shot_block(
                        rag_results,
                        max_chars=self._rag_config.max_few_shot_chars,
                    )
                    if few_shot:
                        effective_hints.append(few_shot)
                    top_similarity = rag_results[0].similarity
                    span.set_attribute("polisyos.drafter.rag_top_similarity", top_similarity)
                if self._rag_config.freeze_snapshot_per_run and self._frozen_rag_snapshot_ref:
                    span.set_attribute(
                        "polisyos.drafter.rag_snapshot_ref",
                        self._frozen_rag_snapshot_ref,
                    )
            draft = await self._inner.draft_policy(
                prepared_problem_frame,
                data_context=data_context,
                hints=effective_hints or None,
                prior_drafts=prior_drafts,
            )
            raw = draft.raw_llm_response
            cost = self._estimate_cost_from_text(raw, model=self._inner_model_name())
            return PassExecution(
                pass_name="naive_draft",
                pass_number=1,
                executed=True,
                draft=draft,
                findings=[],
                raw_llm_response=raw,
                cost_usd=cost,
                duration_ms=int((time.perf_counter() - started) * 1000),
                confidence_request_ref=draft.confidence_request_ref,
                confidence_observation=draft.confidence_observation,
            )

    # ------------------------------------------------------------------
    # Pass 2 / 3: LLM critique
    # ------------------------------------------------------------------

    async def _execute_critique_pass(
        self,
        *,
        pass_name: str,
        pass_number: int,
        pass_type: str,
        problem_frame: ProblemFrame,
        draft: DraftResult,
        previous_findings: Iterable[PassFinding],
    ) -> PassExecution:
        if self._llm is None:
            return self._skipped_pass(pass_name, pass_number, "missing_llm_client")

        tracer = self._tracer if self._tracer is not None else _default_tracer()
        started = time.perf_counter()
        prompt = get_self_critique_prompt(
            pass_type=pass_type,
            problem_frame_summary=self._summarize_problem_frame(problem_frame),
            draft_so_far=self._serialize_draft(draft),
            constraints_list=self._format_constraints(problem_frame),
            previous_pass_findings=self._format_findings(previous_findings),
        )

        attempts = self._config.pass_retry_count + 1
        with tracer.start_as_current_span(
            f"drafter.pass.{pass_name}",
            attributes={
                "polisyos.drafter.pass_name": pass_name,
                "polisyos.drafter.pass_number": pass_number,
            },
        ) as span:
            last_error: Exception | None = None

            async def _invoke_once() -> PassExecution:
                user_message = (
                    "Review the draft and return strict JSON with findings. "
                    "Do not include markdown."
                )
                request_ref = (
                    confidence_request_ref(system=prompt, user=user_message)
                    if self._config.convergence is not None
                    else None
                )
                response = await asyncio.wait_for(
                    self._llm.generate(
                        system=prompt,
                        user=user_message,
                        response_format={"type": "json_object"},
                    ),
                    timeout=self._config.pass_timeout_s,
                )
                content, prompt_tokens, completion_tokens = self._extract_response_data(response)
                findings, confidence_adjustment, parse_ok, verification_code = (
                    self._parse_critique_payload(
                        content,
                        pass_name=pass_name,
                    )
                )
                cost = self._estimate_cost(
                    model=self._critique_model_name(),
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    raw_response=content,
                )
                span.set_attribute("polisyos.drafter.findings_count", len(findings))
                observation = None
                if (
                    self._config.convergence is not None
                    and parse_ok
                    and draft.confidence_status != "not_established"
                    and (confidence_adjustment is not None or findings)
                ):
                    assessed = self._update_confidence(draft, findings, confidence_adjustment)
                    assert request_ref is not None
                    observation = observe_candidate_confidence(
                        response=response,
                        source_text=content,
                        subject_ref=confidence_subject_ref(problem_frame),
                        request_ref=request_ref,
                        pass_number=pass_number,
                        value=assessed.confidence,
                    )
                return PassExecution(
                    pass_name=pass_name,
                    pass_number=pass_number,
                    executed=True,
                    findings=findings,
                    raw_llm_response=content,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cost_usd=cost,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    parse_ok=parse_ok,
                    confidence_adjustment=confidence_adjustment,
                    verification_code=verification_code,
                    confidence_request_ref=request_ref,
                    confidence_observation=observation,
                )

            def _on_error(exc: Exception, _attempt: int, _total: int) -> None:
                nonlocal last_error
                last_error = exc
                logger.warning("%s failed; retrying: %s", pass_name, exc)

            try:
                return await retry_async(
                    _invoke_once,
                    attempts=attempts,
                    on_error=_on_error,
                )
            except Exception as exc:
                logger.debug("Ignored exception: %s", exc)

            span.set_attribute("polisyos.drafter.pass_error", True)
            logger.warning("%s failed after retries: %s", pass_name, last_error)
            return self._skipped_pass(pass_name, pass_number, "pass_error")

    # ------------------------------------------------------------------
    # Pass 4: consolidation
    # ------------------------------------------------------------------

    async def _execute_consolidation_pass(
        self,
        *,
        problem_frame: ProblemFrame,
        draft: DraftResult,
        all_findings: Iterable[PassFinding],
    ) -> PassExecution:
        if self._llm is None:
            return self._skipped_pass("consolidation", 4, "missing_llm_client")

        tracer = self._tracer if self._tracer is not None else _default_tracer()
        started = time.perf_counter()
        prompt = get_self_critique_prompt(
            pass_type="consolidation",
            problem_frame_summary=self._summarize_problem_frame(problem_frame),
            draft_so_far=self._serialize_draft(draft),
            constraints_list=self._format_constraints(problem_frame),
            previous_pass_findings=self._format_findings(all_findings),
        )
        attempts = self._config.pass_retry_count + 1
        with tracer.start_as_current_span(
            "drafter.pass.consolidation",
            attributes={
                "polisyos.drafter.pass_name": "consolidation",
                "polisyos.drafter.pass_number": 4,
            },
        ) as span:
            last_error: Exception | None = None

            async def _invoke_once() -> PassExecution:
                response = await asyncio.wait_for(
                    self._llm.generate(
                        system=prompt,
                        user=(
                            "Integrate findings and return strict JSON of the full revised draft. "
                            "Do not include markdown."
                        ),
                        response_format={"type": "json_object"},
                    ),
                    timeout=self._config.pass_timeout_s,
                )
                content, prompt_tokens, completion_tokens = self._extract_response_data(response)
                updated_draft, parse_ok = self._parse_consolidated_draft(
                    raw_response=content,
                    original=draft,
                )
                cost = self._estimate_cost(
                    model=self._critique_model_name(),
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    raw_response=content,
                )
                span.set_attribute("polisyos.drafter.consolidation_parse_ok", parse_ok)
                return PassExecution(
                    pass_name="consolidation",
                    pass_number=4,
                    executed=True,
                    draft=updated_draft,
                    findings=[],
                    raw_llm_response=content,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cost_usd=cost,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    parse_ok=parse_ok,
                )

            def _on_error(exc: Exception, _attempt: int, _total: int) -> None:
                nonlocal last_error
                last_error = exc
                logger.warning("consolidation failed; retrying: %s", exc)

            try:
                return await retry_async(
                    _invoke_once,
                    attempts=attempts,
                    on_error=_on_error,
                )
            except Exception as exc:
                logger.debug("Ignored exception: %s", exc)

            span.set_attribute("polisyos.drafter.pass_error", True)
            logger.warning("consolidation failed after retries: %s", last_error)
            return self._skipped_pass("consolidation", 4, "pass_error")

    # ------------------------------------------------------------------
    # Confidence / early-exit / budget helpers
    # ------------------------------------------------------------------

    def _should_early_exit(self, draft: DraftResult, findings: list[PassFinding]) -> bool:
        if self._config.max_passes < 3:
            return False
        if draft.confidence < self._config.early_exit_confidence:
            return False
        threshold = _SEVERITY_ORDER[self._config.finding_severity_threshold]
        return not any(_SEVERITY_ORDER[f.severity] >= threshold for f in findings)

    def _can_run_next_pass(
        self,
        *,
        cumulative_cost_usd: float,
        extra_llm_calls: int,
    ) -> tuple[bool, str]:
        if cumulative_cost_usd >= self._config.budget_limit_usd:
            return False, "budget_usd_exceeded"
        if extra_llm_calls >= self._config.max_extra_llm_calls:
            return False, "max_extra_calls_exceeded"
        return True, ""

    def _update_confidence(
        self,
        draft: DraftResult,
        findings: list[PassFinding],
        confidence_adjustment: float | None,
    ) -> DraftResult:
        if confidence_adjustment is not None:
            adjustment = confidence_adjustment
        elif findings:
            adjustment = -sum(
                {
                    FindingSeverity.LOW: 0.02,
                    FindingSeverity.MEDIUM: 0.05,
                    FindingSeverity.HIGH: 0.10,
                    FindingSeverity.CRITICAL: 0.15,
                }[finding.severity]
                for finding in findings
            )
        else:
            adjustment = 0.0

        updated_confidence = min(0.99, max(0.05, draft.confidence + adjustment))
        if updated_confidence == draft.confidence:
            return draft
        return replace(
            draft,
            confidence=updated_confidence,
            confidence_status=(
                "candidate_after_checks"
                if draft.confidence_status != "not_established"
                else "not_established"
            ),
        )

    @staticmethod
    def _convergence_stop_reason(state: ConvergenceState) -> str:
        prefix = "resource_limit" if state.stop_kind == "resource_limit" else "candidate_stability"
        return f"{prefix}:{state.reason}"

    def _record_current_convergence(
        self,
        detector: ConvergenceDetector,
        problem_frame: ProblemFrame,
        current_pass: PassExecution,
        draft: DraftResult,
    ) -> tuple[DraftResult, ConvergenceState]:
        """Join the actual pass/parser result with its current candidate value."""
        subject_ref = confidence_subject_ref(problem_frame)
        observation = current_pass.confidence_observation
        eligible = (
            current_pass.executed
            and current_pass.parse_ok
            and observation is not None
            and draft.confidence_status != "not_established"
            and subject_ref is not None
        )
        if eligible:
            assert observation is not None
            # Code verification/deterministic checks may adjust the candidate,
            # without pretending the model itself emitted that derived value.
            observation = ConvergenceObservation.model_validate(
                {
                    **observation.model_dump(),
                    "value": draft.confidence,
                    "value_derivation": "candidate_after_checks",
                }
            )
        else:
            observation = None
        state = detector.check_candidate_observation(
            observation,
            subject_ref=subject_ref,
            request_ref=current_pass.confidence_request_ref,
            source_text=current_pass.raw_llm_response,
            value=draft.confidence if eligible else None,
            pass_number=current_pass.pass_number,
            unavailable_reason=(
                "pass_not_executed"
                if not current_pass.executed
                else "pass_parse_failed"
                if not current_pass.parse_ok
                else "semantic_subject_not_established"
                if subject_ref is None
                else "candidate_assessment_not_supplied"
            ),
        )
        return replace(
            draft,
            confidence_request_ref=current_pass.confidence_request_ref,
            confidence_observation=observation,
            convergence_state=state,
        ), state

    def _skipped_pass(self, pass_name: str, pass_number: int, reason: str) -> PassExecution:
        return PassExecution(
            pass_name=pass_name,
            pass_number=pass_number,
            executed=False,
            skip_reason=reason,
            findings=[],
        )

    # ------------------------------------------------------------------
    # Finalization
    # ------------------------------------------------------------------

    def _finalize(
        self,
        *,
        problem_frame: ProblemFrame,
        draft: DraftResult,
        pass_results: list[PassExecution],
        cumulative_cost_usd: float,
        extra_llm_calls: int,
        early_exit: bool,
        stop_reason: str,
        parent_span: Any,
        metrics: Any,
    ) -> DraftResult:
        if self._config.shadow_mode and pass_results:
            pass1 = pass_results[0]
            if pass1.executed and pass1.draft is not None:
                checked_state = draft.convergence_state
                if checked_state is not None:
                    checked_state = ConvergenceState.model_validate(
                        {
                            **checked_state.model_dump(),
                            "observation_status": "last_checked_in_shadow_run",
                        }
                    )
                draft = replace(pass1.draft, convergence_state=checked_state)

        findings_total = sum(len(p.findings) for p in pass_results)
        executed_passes = sum(1 for p in pass_results if p.executed)
        budget_stop = stop_reason in {
            "budget_usd_exceeded",
            "max_extra_calls_exceeded",
            "resource_limit:budget_pressure",
        }
        if draft.convergence_state is not None:
            parent_span.set_attribute(
                "polisyos.drafter.stop_kind", draft.convergence_state.stop_kind
            )
            parent_span.set_attribute("polisyos.drafter.scientific_converged", False)
            parent_span.set_attribute(
                "polisyos.drafter.observation_status", draft.convergence_state.observation_status
            )

        parent_span.set_attribute("polisyos.drafter.total_passes", len(pass_results))
        parent_span.set_attribute("polisyos.drafter.executed_passes", executed_passes)
        parent_span.set_attribute("polisyos.drafter.total_findings", findings_total)
        parent_span.set_attribute("polisyos.drafter.total_cost_usd", cumulative_cost_usd)
        parent_span.set_attribute("polisyos.drafter.extra_llm_calls", extra_llm_calls)
        parent_span.set_attribute("polisyos.drafter.early_exit", early_exit)
        if stop_reason:
            parent_span.set_attribute("polisyos.drafter.stop_reason", stop_reason)

        metrics.record_drafter_multipass_run(
            domain=problem_frame.domain,
            executed_passes=executed_passes,
            total_findings=findings_total,
            total_cost_usd=cumulative_cost_usd,
            early_exit=early_exit,
            budget_stop=budget_stop,
            shadow_mode=self._config.shadow_mode,
        )
        for pass_result in pass_results:
            metrics.record_drafter_multipass_pass(
                pass_name=pass_result.pass_name,
                duration_seconds=max(0.0, pass_result.duration_ms / 1000.0),
                executed=pass_result.executed,
            )

        if self._config.enable_memory_logging and self._memory is not None:
            for pass_result in pass_results:
                if pass_result.findings:
                    self._memory.add_pass_findings(
                        pass_result.pass_name,
                        [finding.as_memory_dict() for finding in pass_result.findings],
                        cost_usd=pass_result.cost_usd,
                    )

        return draft
