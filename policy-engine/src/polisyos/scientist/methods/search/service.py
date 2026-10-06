"""Concrete native service driver for the legacy search lifecycle.

The search contracts are intentionally small.  This module is the internal
bridge that drives the existing controller-owned generation, evaluation, and
run-state transitions through that contract.  It is not a second search
framework: the controller remains the owner of evaluation semantics and
``SearchRunState`` remains the sole mutable run ledger.
"""

from __future__ import annotations

import hashlib
import inspect
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from types import CodeType
from typing import TYPE_CHECKING, Any

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.manifest_profile import artifact_manifest_profile_sha256
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon.canon_json import CanonSpec, from_canonical_bytes
from polisyos.scientist.methods.search.contracts import (
    CandidateProposal,
    EvaluationBundle,
    SearchServiceCheckpoint,
    TellResult,
)
from polisyos.scientist.methods.search.controller import (
    SearchController,
    SearchResult,
    SearchStatus,
)
from polisyos.scientist.methods.search.run_state import (
    GenerationTransition,
    SearchRunState,
    checkpoint_json,
    checkpoint_value,
)
from polisyos.scientist.methods.search.sentinels import extract_sentinel_metadata

logger = get_logger(__name__)

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore


class NativeSearchService:
    """Drive one controller lifecycle through the native service boundary.

    The ask/tell methods are the concrete implementation of the existing
    ``SearchService`` protocol.  ``run_search`` calls public ``ask`` and
    ``tell`` around the controller's detached evaluator, so the autotune
    consumer no longer calls the legacy full-loop implementation directly.
    """

    def __init__(
        self,
        controller: SearchController,
        *,
        store: ArtifactStore | None = None,
        basis: dict[str, Any] | None = None,
    ) -> None:
        self.controller = controller
        self._store = store
        self._basis = deepcopy(basis or {})
        self.checkpoint_ref: ArtifactRef | None = None
        self._started_at: datetime | None = None
        self._stopped_reason: str | None = None
        self._failure: str | None = None
        self._pending_candidates: dict[str, dict[str, Any]] = {}
        self._completed_candidate_ids: set[str] = set()
        self._ask_iteration = 0
        self._initial_candidate: dict[str, Any] | None = None
        self._initial_candidate_ids: set[str] = set()

    def _configuration(self) -> dict[str, Any]:
        config = self.controller._config
        stopping = config.stopping.checkpoint_state()

        def without_clock(value: dict[str, Any]) -> dict[str, Any]:
            return {
                **value,
                "started_at": None,
                "children": [without_clock(child) for child in value["children"]],
            }

        profile = self._replay_profile()
        return checkpoint_json(
            {
                "basis": self._basis,
                "replay_profile": profile,
                "hard_limit": config.max_iterations_hard_limit,
                "max_empty_generation_attempts": config.max_empty_generation_attempts,
                "stage_a_enabled": config.enable_stage_a,
                "batch_size": config.batch_size,
                "budget_key": config.budget_key,
                "budget_cost_key": config.budget_cost_key,
                "budget_owner_identity": self.controller._budget_owner_identity(),
                "stopping": without_clock(stopping),
                "generator": f"{type(self.controller._generator).__module__}.{type(self.controller._generator).__qualname__}",
                "objectives": [
                    {
                        "type": f"{type(obj).__module__}.{type(obj).__qualname__}",
                        "name": obj.name,
                        "direction": getattr(obj, "direction", None),
                        "parameters": vars(obj) if profile is not None else None,
                    }
                    for obj in config.objective.objectives
                ],
                "transfer_fingerprint": config.transfer_fingerprint,
                "diversity_enabled": self.controller._diversity_enabled,
            }
        )

    def _replay_profile(self) -> dict[str, Any] | None:
        """Recognize the actual factory or built-in objectives/stateless ports.

        Arbitrary objects and closures are not reconstructible from a build
        digest. Such generic profiles remain persistable and refuse resume.
        """
        from polisyos.scientist.methods.autotune.models import SearchLoopSpec
        from polisyos.scientist.methods.autotune.runtime import (
            PydanticMutationCodec,
            SearchLoopRunner,
            _AutotuneObjective,
        )
        from polisyos.scientist.methods.search.objective import (
            BudgetDeficitObjective,
            EmploymentObjective,
            GDPGrowthObjective,
            InequalityObjective,
        )

        objectives = self.controller._config.objective.objectives
        stage_b = self.controller._stage_b
        closure = inspect.getclosurevars(stage_b).nonlocals if inspect.isfunction(stage_b) else {}
        runner, spec, suite = closure.get("self"), closure.get("spec"), closure.get("suite_ref")
        if (
            type(runner) is SearchLoopRunner
            and isinstance(spec, SearchLoopSpec)
            and isinstance(suite, ArtifactRef)
            and runner._store is self._store
            and type(spec.mutation_codec) is PydanticMutationCodec
            and len(objectives) == 1
            and type(objectives[0]) is _AutotuneObjective
            and objectives[0]._policy == spec.promotion_policy
            and any(
                stage_b.__code__ is code
                for code in SearchLoopRunner.create_service.__code__.co_consts
                if isinstance(code, CodeType) and code.co_freevars == ("self", "spec", "suite_ref")
            )
        ):
            return {
                "version": "native-autotune-replay.v1",
                "suite_ref": suite.model_dump(mode="json"),
                "policy": spec.promotion_policy.model_dump(mode="json"),
                "mutation_schema": spec.mutation_codec._model_cls.model_json_schema(),
                "factory_build": hashlib.sha256(
                    Path(inspect.getsourcefile(SearchLoopRunner)).read_bytes()
                ).hexdigest(),
            }
        supported = (
            BudgetDeficitObjective,
            EmploymentObjective,
            GDPGrowthObjective,
            InequalityObjective,
        )
        if any(type(obj) not in supported for obj in objectives):
            return None

        def callable_profile(function: Any) -> dict[str, Any] | None:
            if not inspect.isfunction(function) or function.__closure__ or vars(function):
                return None
            variables = inspect.getclosurevars(function)
            try:
                globals_snapshot = checkpoint_json(variables.globals)
                defaults = checkpoint_json(function.__defaults__)
                keyword_defaults = checkpoint_json(function.__kwdefaults__)
                source = inspect.getsource(function)
            except (TypeError, ValueError, OSError):
                return None
            return {
                "qualname": function.__qualname__,
                "module": function.__module__,
                "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
                "globals": globals_snapshot,
                "defaults": defaults,
                "keyword_defaults": keyword_defaults,
            }

        ports = {"stage_b": callable_profile(stage_b)}
        if self.controller._config.enable_stage_a:
            ports["stage_a"] = callable_profile(self.controller._stage_a)
        if any(port is None for port in ports.values()):
            return None
        return {
            "version": "builtin-objective-stateless-ports.v1",
            "objective_build": hashlib.sha256(
                Path(inspect.getsourcefile(BudgetDeficitObjective)).read_bytes()
            ).hexdigest(),
            "ports": ports,
        }

    def checkpoint(self) -> ArtifactRef:
        """Persist an exact immutable replay view in the configured store."""
        if self._store is None:
            raise ValueError("search_checkpoint_store_not_configured")
        generator = self.controller._generator
        get_state = getattr(generator, "get_state", None)
        set_state = getattr(generator, "set_state", None)
        state = get_state() if callable(get_state) and callable(set_state) else None
        payload = SearchServiceCheckpoint(
            configuration=self._configuration(),
            run_state=self.controller._run_state.checkpoint_state(),
            generator_state=checkpoint_json(state),
            stopping_state=self.controller._config.stopping.checkpoint_state(),
            pending_candidates=checkpoint_json(self._pending_candidates),
            pending_candidate_ids=list(self._pending_candidates),
            initial_candidate_ids=sorted(self._initial_candidate_ids),
            completed_candidate_ids=sorted(self._completed_candidate_ids),
            ask_iteration=self._ask_iteration,
            initial_candidate=checkpoint_json(self._initial_candidate),
            started_at=self._started_at.isoformat() if self._started_at else None,
            stopping_reason=self._stopped_reason,
            failure=self._failure,
        )
        ref = self._store.put_json(
            payload,
            ArtifactWriteOptions(
                kind="scientist.search.service_checkpoint",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.search.SearchServiceCheckpoint", version="2.0"
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
        )
        snapshot = self._verified_snapshot(ref)
        if SearchServiceCheckpoint.model_validate(from_canonical_bytes(snapshot.data)) != payload:
            raise ValueError("search_checkpoint_readback_mismatch")
        self.checkpoint_ref = ref.model_copy(
            update={
                "manifest_profile_sha256": artifact_manifest_profile_sha256(snapshot.manifest),
            }
        )
        return self.checkpoint_ref

    def _verified_snapshot(self, ref: ArtifactRef) -> Any:
        read = getattr(self._store, "get_verified_snapshot", None)
        if not callable(read):
            raise ValueError("search_checkpoint_verified_snapshot_port_required")
        snapshot = read(ref)
        manifest = snapshot.manifest
        if (
            manifest.kind != "scientist.search.service_checkpoint"
            or manifest.media_type != "application/json"
            or manifest.artifact_schema
            != SchemaInfo(name="polisyos.scientist.search.SearchServiceCheckpoint", version="2.0")
        ):
            raise ValueError("search_resume_checkpoint_manifest_mismatch")
        return snapshot

    def _persist(self) -> None:
        if self._store is not None:
            self.checkpoint()

    def restore(self, ref: ArtifactRef) -> None:
        """Restore into a fresh service, validating the whole view before effect."""
        if self._store is None or not isinstance(ref, ArtifactRef):
            raise ValueError("search_resume_requires_store_and_exact_reference")
        if (
            self.controller._run_state.search_id
            or self._pending_candidates
            or self._completed_candidate_ids
        ):
            raise ValueError("search_resume_requires_fresh_service")
        if ref.manifest_profile_sha256 is None:
            raise ValueError("search_resume_exact_manifest_profile_required")
        snapshot = self._verified_snapshot(ref)
        saved = SearchServiceCheckpoint.model_validate(from_canonical_bytes(snapshot.data))
        if saved.configuration.get("replay_profile") is None:
            raise ValueError("search_resume_unsupported_objective_or_evaluator_profile")
        if saved.configuration != self._configuration():
            raise ValueError("search_resume_configuration_mismatch")
        if saved.configuration["diversity_enabled"]:
            raise ValueError("search_resume_unsupported_diversity_profile")
        generator = self.controller._generator
        restore_generator = getattr(generator, "set_state", None)
        if saved.generator_state is None or not callable(restore_generator):
            raise ValueError("search_resume_unsupported_generator_profile")
        state = SearchRunState.from_checkpoint(saved.run_state)
        if (
            len(saved.completed_candidate_ids)
            != state.evaluation_iterations + state.sentinel_evaluations
        ):
            raise ValueError("search_resume_completed_candidate_counter_mismatch")
        expected_stage_a = (
            state.evaluation_iterations + state.sentinel_evaluations
            if self.controller._config.enable_stage_a
            else 0
        )
        if state.stage_a_evaluations != expected_stage_a:
            raise ValueError("search_resume_stage_a_counter_mismatch")
        stopping = deepcopy(self.controller._config.stopping)
        stopping.restore_state(saved.stopping_state)
        started_at = datetime.fromisoformat(saved.started_at) if saved.started_at else None
        if started_at is not None and started_at.tzinfo is None:
            raise ValueError("search_resume_invalid_run_clock")
        # Strategies own atomic admission of their numerical/RNG state. No run
        # ledger or candidate ownership changes precede that admission.
        restore_generator(checkpoint_value(saved.generator_state))
        self.controller._config.stopping = stopping
        self.controller._run_state = state
        pending = checkpoint_value(saved.pending_candidates)
        self._pending_candidates = {key: pending[key] for key in saved.pending_candidate_ids}
        self._initial_candidate_ids = set(saved.initial_candidate_ids)
        self._completed_candidate_ids = set(saved.completed_candidate_ids)
        self._ask_iteration = saved.ask_iteration
        self._initial_candidate = checkpoint_value(saved.initial_candidate)
        self._started_at = started_at
        self._stopped_reason = saved.stopping_reason
        self._failure = saved.failure
        self.checkpoint_ref = ref

    def resume_search(self, *, context: dict[str, Any] | None = None) -> SearchResult:
        """Continue restored pending work; terminal stops remain terminal."""
        if not self.controller._run_state.search_id:
            raise ValueError("search_resume_requires_restored_run")
        lock = self.controller._run_lock
        if not lock.acquire(blocking=False):
            raise RuntimeError("SearchController.run is not reentrant")
        try:
            if self.controller._status in (SearchStatus.STOPPED, SearchStatus.CONVERGED):
                return self._finish(self._started_at or datetime.now(UTC), self._stopped_reason)
            self.controller._status = SearchStatus.RUNNING
            self._failure = None
            return self._run_locked(
                initial_context=dict(context or {}),
                initial_candidate=self._initial_candidate,
                resume=True,
            )
        finally:
            lock.release()

    def ask(
        self,
        goal: dict[str, Any] | None,
        search_space: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> list[CandidateProposal]:
        """Generate proposals and retain candidate-ID ownership for ``tell``."""
        del goal, search_space
        self.controller._prepare_service_run()
        payloads = self.controller._generate_candidates(
            iteration=self._ask_iteration,
            initial_candidate=self._initial_candidate,
            context=context,
        )

        proposals: list[CandidateProposal] = []
        pending: dict[str, dict[str, Any]] = {}
        for index, payload in enumerate(payloads):
            if not isinstance(payload, dict):
                raise TypeError("search candidate generators must return mappings")
            if "candidate_id" not in payload:
                candidate_id = f"candidate_{self._ask_iteration}_{index}"
            else:
                raw_candidate_id = payload["candidate_id"]
                if not isinstance(raw_candidate_id, str) or not raw_candidate_id:
                    raise ValueError("search candidate_id must be an explicit non-empty string")
                candidate_id = raw_candidate_id
            if (
                candidate_id in pending
                or candidate_id in self._pending_candidates
                or candidate_id in self._completed_candidate_ids
            ):
                raise ValueError(f"duplicate search candidate id: {candidate_id}")
            candidate = deepcopy(payload)
            pending[candidate_id] = candidate
            proposals.append(
                CandidateProposal(
                    candidate_id=candidate_id,
                    payload=deepcopy(candidate),
                    metadata={"iteration": self._ask_iteration},
                )
            )

        self._pending_candidates.update(pending)
        if self._initial_candidate is not None and self._ask_iteration == 0:
            self._initial_candidate_ids.update(pending)
        self._initial_candidate = None
        self._ask_iteration += 1
        self._persist()
        return proposals

    def tell(
        self,
        candidate_id: str,
        evaluation: EvaluationBundle,
    ) -> TellResult:
        """Accept one previously asked evaluation through controller state."""
        if not isinstance(candidate_id, str) or not candidate_id:
            raise KeyError(candidate_id)
        if candidate_id in self._completed_candidate_ids:
            raise ValueError(f"duplicate search evaluation: {candidate_id}")
        if candidate_id not in self._pending_candidates:
            raise KeyError(candidate_id)

        candidate = deepcopy(self._pending_candidates[candidate_id])
        stage_b_result = self._stage_b_result(evaluation)
        before = self.controller._run_state.snapshot()
        pending_before = deepcopy(self._pending_candidates)
        completed_before = set(self._completed_candidate_ids)
        initial_before = set(self._initial_candidate_ids)
        try:
            self.controller._accept_tell(
                candidate=candidate,
                objective_value=float(evaluation.objective_value),
                objective_details=list(evaluation.objective_details),
                is_promising=bool(evaluation.is_promising),
                stage_a_passed=bool(evaluation.stage_a_passed),
                stage_b_result=stage_b_result,
                duration_seconds=float(evaluation.duration_seconds),
            )
            del self._pending_candidates[candidate_id]
            self._completed_candidate_ids.add(candidate_id)
            self._initial_candidate_ids.discard(candidate_id)
            self._persist()
        except Exception:
            self.controller._run_state = before
            self._pending_candidates = pending_before
            self._completed_candidate_ids = completed_before
            self._initial_candidate_ids = initial_before
            raise
        return TellResult(**self.controller._service_tell_snapshot())

    @staticmethod
    def _stage_b_result(evaluation: EvaluationBundle) -> dict[str, Any]:
        """Build a controller-shaped result without changing typed payloads."""
        stage_b_result = deepcopy(evaluation.stage_b_result or {})
        simulation_results = stage_b_result.get("simulation_results")
        if simulation_results is None:
            stage_b_result["simulation_results"] = {
                "objective_value": float(evaluation.objective_value),
            }
        elif not isinstance(simulation_results, dict):
            raise TypeError("EvaluationBundle.stage_b_result.simulation_results must be a mapping")

        feedback = stage_b_result.get("feedback")
        if feedback is None:
            stage_b_result["feedback"] = {
                "verdict": "APPROVE" if evaluation.is_promising else "REJECT",
            }
        elif not isinstance(feedback, dict):
            raise TypeError("EvaluationBundle.stage_b_result.feedback must be a mapping")
        else:
            feedback.setdefault(
                "verdict",
                "APPROVE" if evaluation.is_promising else "REJECT",
            )

        if evaluation.policy_evaluation is not None:
            stage_b_result.setdefault("policy_evaluation", evaluation.policy_evaluation)
        return stage_b_result

    def run_search(
        self,
        *,
        initial_context: dict[str, Any],
        initial_candidate: dict[str, Any] | None = None,
    ) -> SearchResult:
        """Run the existing generation/evaluation lifecycle through this driver."""
        run_lock = self.controller._run_lock
        if not run_lock.acquire(blocking=False):
            raise RuntimeError("SearchController.run is not reentrant")
        try:
            self._pending_candidates.clear()
            self._completed_candidate_ids.clear()
            self._ask_iteration = 0
            self._initial_candidate = deepcopy(initial_candidate)
            self._stopped_reason = None
            self._failure = None
            self._initial_candidate_ids.clear()
            return self._run_locked(
                initial_context=initial_context,
                initial_candidate=initial_candidate,
            )
        finally:
            run_lock.release()

    def _run_locked(
        self,
        *,
        initial_context: dict[str, Any],
        initial_candidate: dict[str, Any] | None,
        resume: bool = False,
    ) -> SearchResult:
        start_time = (
            self._started_at or datetime.now(UTC)
            if resume
            else self.controller._begin_native_run(initial_context)
        )
        self._started_at = start_time
        try:
            return self._drive_locked(
                initial_context=initial_context,
                initial_candidate=initial_candidate,
                start_time=start_time,
                resume=resume,
            )
        except Exception as exc:
            self.controller._status = SearchStatus.FAILED
            self._failure = f"{type(exc).__name__}: {exc}"
            self._persist()
            raise

    def _drive_locked(
        self,
        *,
        initial_context: dict[str, Any],
        initial_candidate: dict[str, Any] | None,
        start_time: datetime,
        resume: bool,
    ) -> SearchResult:
        stopping_reason: str | None = None
        candidate_to_seed = initial_candidate

        if resume and self._pending_candidates:
            stopping_reason = self._stopping_reason(initial_context)
            if stopping_reason is not None:
                self._stop(stopping_reason)
                return self._finish(start_time, stopping_reason)
            batch = [
                CandidateProposal(
                    candidate_id=key,
                    payload=deepcopy(value),
                    metadata={"initial": key in self._initial_candidate_ids},
                )
                for key, value in self._pending_candidates.items()
            ]
            stopping_reason = self._evaluate_batch(
                batch=batch, generated=True, initial_context=initial_context
            )
            if stopping_reason is not None:
                return self._finish(start_time, stopping_reason)

        while (
            self.controller._run_state.evaluation_iterations
            < self.controller._config.max_iterations_hard_limit
        ):
            stopping_reason = self._stopping_reason(initial_context)
            if stopping_reason is not None:
                self._stop(stopping_reason)
                break

            batch, generated, stopping_reason = self._prepare_batch(
                initial_context=initial_context,
                initial_candidate=candidate_to_seed,
            )
            candidate_to_seed = None
            if stopping_reason is not None:
                self._stop(stopping_reason)
                break

            if not batch:
                stopping_reason = self._handle_empty_generation()
                if stopping_reason is not None:
                    break
                continue

            self._mark_nonempty_generation()
            stopping_reason = self._evaluate_batch(
                batch=batch,
                generated=generated,
                initial_context=initial_context,
            )
            if stopping_reason is not None:
                break

        return self._finish(start_time, stopping_reason)

    def _finish(self, start_time: datetime, stopping_reason: str | None) -> SearchResult:
        result = self.controller._finish_native_run(
            start_time=start_time,
            stopping_reason=stopping_reason,
        )
        self._stopped_reason = result.stopping_reason
        self._persist()
        if self.checkpoint_ref is not None:
            result.telemetry["checkpoint_ref"] = self.checkpoint_ref.model_dump(mode="json")
        return result

    def _stopping_reason(self, context: dict[str, Any]) -> str | None:
        self.controller._refresh_budget_snapshot(context)
        stop_check = self.controller._config.stopping.check(
            [self.controller._to_history_dict(item) for item in self.controller._history],
            self.controller._stopping_state(),
        )
        return stop_check.reason if stop_check.should_stop else None

    def _prepare_batch(
        self,
        *,
        initial_context: dict[str, Any],
        initial_candidate: dict[str, Any] | None,
    ) -> tuple[list[CandidateProposal], bool, str | None]:
        generated = initial_candidate is None
        batch = self.ask(None, None, initial_context)
        if not generated:
            return batch, False, None

        self.controller._run_state.generation_attempts += 1
        stopping_reason = self._stopping_reason(initial_context)
        return batch, True, stopping_reason

    def _handle_empty_generation(self) -> str | None:
        self.controller._run_state.empty_generation_attempts += 1
        if (
            self.controller._run_state.empty_generation_attempts
            < self.controller._config.max_empty_generation_attempts
        ):
            return None
        self.controller._run_state.generation_transition = GenerationTransition.EXHAUSTED
        self._stop("generation_exhausted")
        return "generation_exhausted"

    def _mark_nonempty_generation(self) -> None:
        if self.controller._run_state.empty_generation_attempts:
            self.controller._run_state.generation_transition = GenerationTransition.TRANSIENT_EMPTY
            self.controller._run_state.empty_generation_attempts = 0

    def _evaluate_batch(
        self,
        *,
        batch: list[CandidateProposal],
        generated: bool,
        initial_context: dict[str, Any],
    ) -> str | None:
        for proposal in batch:
            if (
                self.controller._run_state.evaluation_iterations
                >= self.controller._config.max_iterations_hard_limit
            ):
                break
            evaluation = self.controller._evaluate_for_tell(
                proposal.payload,
                iteration=self.controller._run_state.evaluation_iterations,
                context=initial_context,
            )
            self.tell(proposal.candidate_id, evaluation)
            self.controller._refresh_budget_snapshot(initial_context)

            if extract_sentinel_metadata(proposal.payload) is not None and (
                not generated or proposal.metadata.get("initial", False)
            ):
                self._stop("Initial sentinel evaluated")
                return "Initial sentinel evaluated"

            stopping_reason = self._stopping_reason(initial_context)
            if stopping_reason is not None:
                self._stop(stopping_reason)
                return stopping_reason
        return None

    def _stop(self, reason: str) -> None:
        self.controller._status = SearchStatus.STOPPED
        self._stopped_reason = reason
        logger.info("Stopping: %s", reason)


_NativeSearchServiceDriver = NativeSearchService

__all__ = ["NativeSearchService", "_NativeSearchServiceDriver"]
