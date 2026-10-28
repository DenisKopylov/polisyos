"""Adapter bridging SearchStrategy and SearchController CandidateGenerator protocol."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from polisyos.scientist.methods.search.contracts import CandidateProposal, CandidateStrategyContext
from polisyos.scientist.methods.search.controller import SearchIteration
from polisyos.scientist.methods.search.objective import ObjectiveValue
from polisyos.scientist.methods.search.strategies.base import SearchStrategy
from polisyos.scientist.methods.search.strategies.codec import (
    ParameterCodec,
    ScalarParameterCodec,
)
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    Evaluation,
    EvaluationStatus,
)


class StrategyAdapter:
    """
    Adapts `SearchStrategy` to `CandidateGenerator` protocol.

    Supports both single-candidate (`generate`) and batch (`generate_batch`) flows.
    """

    def __init__(
        self,
        strategy: SearchStrategy,
        space: SearchSpace,
        codec: ParameterCodec | None = None,
        objective_extractor: Callable[[SearchIteration], list[ObjectiveValue]] | None = None,
        canonical_template: Any | None = None,
    ):
        self._strategy = strategy
        self._space = space
        self._codec = codec or ScalarParameterCodec()
        self._objective_extractor = objective_extractor or (
            lambda iteration: list(iteration.objective_details)
        )
        self._evaluations: list[Evaluation] = []
        self._synced_len = 0
        self._canonical_template = canonical_template

    @property
    def search_space(self) -> SearchSpace:
        """Return the actual space used to produce and normalize candidates."""
        return self._space

    def generate(
        self,
        history: list[SearchIteration],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        del current_best
        self._sync_history(history)
        candidate = self._strategy.suggest(self._evaluations)
        return self._candidate_to_payload(candidate, context=context)

    def generate_batch(
        self,
        history: list[SearchIteration],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
        batch_size: int,
    ) -> list[dict[str, Any]]:
        del current_best
        self._sync_history(history)
        candidates = self._strategy.suggest_batch(self._evaluations, batch_size=batch_size)
        return [self._candidate_to_payload(candidate, context=context) for candidate in candidates]

    def generate_proposal(
        self,
        history: list[SearchIteration],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> CandidateProposal:
        """Generate a subject and keep producer-owned technical fields separate."""
        del current_best
        self._sync_history(history)
        return self._candidate_to_proposal(self._strategy.suggest(self._evaluations), context)

    def generate_batch_proposals(
        self,
        history: list[SearchIteration],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
        batch_size: int,
    ) -> list[CandidateProposal]:
        """Generate an explicitly separated batch without changing legacy methods."""
        del current_best
        self._sync_history(history)
        return [
            self._candidate_to_proposal(candidate, context)
            for candidate in self._strategy.suggest_batch(self._evaluations, batch_size=batch_size)
        ]

    def _candidate_to_proposal(self, candidate: Any, context: dict[str, Any]) -> CandidateProposal:
        from polisyos.scientist.methods.search.frontier import strategy_candidate_payload

        template = context.get("candidate_template")
        subject = self._codec.decode(
            candidate.params,
            context=context,
            template=template if isinstance(template, dict) else None,
        )
        policy_subject = False
        policy_template = self._canonical_template
        if policy_template is not None:
            from polisyos.scientist.policy_design.schema import PolicyCandidateSchema

            if type(policy_template) is not PolicyCandidateSchema:
                raise TypeError("candidate_policy_template_invalid")
            if candidate.semantic != {"interventions": []} or candidate.metadata:
                raise ValueError("policy_strategy_semantics_not_consumed")
            expected = policy_template.as_search_payload()
            if template != expected or subject.get("candidate_hash") != expected["candidate_hash"]:
                raise ValueError("candidate_policy_template_mismatch")
            subject.pop("candidate_hash")
            # Normalize the actual typed producer input once, before it is
            # passed to either evaluator or persistence. The schema owns the
            # Decimal/Value and exclude-none JSON projection.
            typed = PolicyCandidateSchema.model_validate(subject)
            subject = typed.model_dump(mode="json", exclude_none=True)
            policy_subject = candidate.semantic == {"interventions": []} and not candidate.metadata
        if not policy_subject:
            subject.setdefault("semantic", deepcopy(candidate.semantic))
        if candidate.metadata:
            if "_strategy_metadata" in subject:
                raise ValueError("candidate_strategy_metadata_subject_conflict")
            subject["_strategy_metadata"] = deepcopy(candidate.metadata)
        technical = {
            "candidate_id": candidate.candidate_id,
            "acquisition_value": candidate.acquisition_value,
            "predicted_mean": candidate.predicted_mean,
            "predicted_std": candidate.predicted_std,
            "source": candidate.source_strategy,
        }
        # Explicit producer metadata may use the same names with subject
        # meaning. Those entries stay in the subject and cannot be excluded.
        for key in candidate.metadata:
            technical.pop(key, None)
        binding = CandidateStrategyContext(
            subject=subject,
            strategy_fields=technical,
            policy_schema=policy_subject,
            policy_transport=policy_template is not None,
        )
        return CandidateProposal(
            candidate_id=candidate.candidate_id,
            payload=strategy_candidate_payload(binding),
            strategy_context=binding,
        )

    def _sync_history(self, history: list[SearchIteration]) -> None:
        if self._synced_len > len(history):
            self._evaluations = []
            self._synced_len = 0

        for iteration in history[self._synced_len :]:
            evaluation = self._to_evaluation(iteration)
            self._evaluations.append(evaluation)
            self._strategy.update(evaluation)
        self._synced_len = len(history)

    def _to_evaluation(self, iteration: SearchIteration) -> Evaluation:
        proposal = iteration.candidate_proposal
        subject = (
            proposal.strategy_context.subject
            if proposal is not None and proposal.strategy_context is not None
            else iteration.candidate
        )
        params = self._codec.encode(subject)
        normalized = self._space.normalize(params)
        metadata: dict[str, Any] = {}
        sources: list[tuple[str, dict[str, Any]]] = []
        if proposal is not None and proposal.strategy_context is not None:
            strategy_subject_metadata = proposal.strategy_context.subject.get("_strategy_metadata")
            if isinstance(strategy_subject_metadata, dict):
                sources.append(("strategy_subject_metadata", strategy_subject_metadata))
        if iteration.policy_evaluation is not None:
            sources.append(("policy_evaluation_metadata", iteration.policy_evaluation.metadata))
        if isinstance(iteration.stage_b_result, dict):
            stage_metadata = iteration.stage_b_result.get("metadata")
            if isinstance(stage_metadata, dict):
                sources.append(("stage_b_metadata", stage_metadata))
        # Preserve all fields in their source namespace. Only the existing
        # optimizer's explicitly declared replica identifiers are projected
        # into its identity interface; arbitrary source metadata cannot claim
        # a native GP compatibility profile by a coincidental key name.
        for source_name, source in sources:
            metadata[source_name] = deepcopy(source)
            for key in ("replicate_id", "replica_id", "seed"):
                if key not in source:
                    continue
                if key in metadata and metadata[key] != source[key]:
                    raise ValueError("evaluation_replica_metadata_conflict")
                metadata[key] = deepcopy(source[key])
        if proposal is not None:
            from polisyos.scientist.methods.search.frontier import policy_candidate_hash

            metadata["search_candidate_proposal"] = proposal.model_dump(mode="json")
            subject_hash = policy_candidate_hash(proposal)
            metadata["search_subject_hash"] = subject_hash
            # A semantic digest is not a resolved Core ArtifactRef. Keep its
            # identity distinct from the `sha256:` artifact-ID namespace.
            candidate_id = f"subject:{subject_hash}"
        else:
            candidate_id = f"iter_{iteration.iteration}"

        if not iteration.stage_a_passed:
            status = EvaluationStatus.STAGE_A_REJECT
        elif iteration.stage_b_result is None:
            status = EvaluationStatus.STAGE_B_ERROR
        else:
            status = EvaluationStatus.SUCCESS

        stage_b_result = deepcopy(iteration.stage_b_result)
        if isinstance(stage_b_result, dict) and "_funnel_outcome" in stage_b_result:
            from polisyos.scientist.methods.search.funnel.types import FunnelOutcome
            from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_reporting import (
                _serialize_funnel_outcome,
            )

            outcome = stage_b_result["_funnel_outcome"]
            if not isinstance(outcome, FunnelOutcome):
                raise ValueError("transfer_funnel_outcome_untyped")
            if proposal is None or outcome.candidate_hash != policy_candidate_hash(proposal):
                raise ValueError("transfer_funnel_candidate_mismatch")
            if "funnel_outcome_projection" in stage_b_result:
                raise ValueError("transfer_funnel_projection_conflict")
            selected = outcome.final_result
            if (
                selected is not None
                and stage_b_result.get("simulation_results") != selected.simulation_results
            ):
                raise ValueError("transfer_funnel_source_mismatch")
            stage_b_result.pop("_funnel_outcome")
            stage_b_result.pop("_funnel_result", None)
            stage_b_result["funnel_outcome_projection"] = _serialize_funnel_outcome(outcome)
            metadata["funnel_source_binding"] = "not_established"

        return Evaluation(
            candidate_id=candidate_id,
            params=params,
            params_normalized=normalized,
            objectives=self._objective_extractor(iteration),
            scalar_score=iteration.objective_value,
            stage_a_passed=iteration.stage_a_passed,
            stage_b_result=stage_b_result,
            status=status,
            timestamp=iteration.timestamp,
            wall_time_seconds=iteration.duration_seconds,
            metadata=metadata,
            score_status=iteration.score_status,
            score_assessment=iteration.score_assessment,
            score_admission=iteration.score_admission,
        )

    def completed_run_evaluations(self, history: list[SearchIteration]) -> list[Evaluation]:
        """Project current-run observations for the existing transfer-history owner."""
        return [self._to_evaluation(item) for item in history if item.iteration >= 0]

    def _candidate_to_payload(self, candidate, context: dict[str, Any]) -> dict[str, Any]:
        payload = self._codec.decode(
            candidate.params,
            context=context,
            template=context.get("candidate_template") if isinstance(context, dict) else None,
        )
        payload.setdefault("semantic", candidate.semantic)
        payload["_strategy_metadata"] = {
            "candidate_id": candidate.candidate_id,
            "acquisition_value": candidate.acquisition_value,
            "predicted_mean": candidate.predicted_mean,
            "predicted_std": candidate.predicted_std,
            "source": candidate.source_strategy,
            **candidate.metadata,
        }
        return payload
