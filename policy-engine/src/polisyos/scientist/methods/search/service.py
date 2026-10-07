"""Concrete native service driver for the legacy search lifecycle.

The search contracts are intentionally small.  This module is the internal
bridge that drives the existing controller-owned generation, evaluation, and
run-state transitions through that contract.  It is not a second search
framework: the controller remains the owner of evaluation semantics and
``SearchRunState`` remains the sole mutable run ledger.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from types import CodeType
from typing import TYPE_CHECKING, Any

from polisyos.common.logger import get_logger
from polisyos.common.serialization import _finite_checkpoint_json_number
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


def _decode_checkpoint(data: bytes) -> Any:
    """Refuse wire underflow before JSON decoding can turn nonzero into zero."""

    raw = json.loads(
        data,
        parse_float=_finite_checkpoint_json_number,
        parse_constant=_finite_checkpoint_json_number,
    )

    def tagged_numbers(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("_type") == "float" and isinstance(value.get("repr"), str):
                _finite_checkpoint_json_number(value["repr"])
            for item in value.values():
                tagged_numbers(item)
        elif isinstance(value, list):
            for item in value:
                tagged_numbers(item)

    tagged_numbers(raw)
    return from_canonical_bytes(data)


def _same_configuration(saved: Any, current: Any) -> bool:
    """Compare the complete profile without boolean/integer equality aliases."""
    if isinstance(current, dict):
        return (
            isinstance(saved, dict)
            and saved.keys() == current.keys()
            and all(
                _same_configuration(saved[key], value) for key, value in current.items()
            )
        )
    if isinstance(current, list):
        return (
            isinstance(saved, list)
            and len(saved) == len(current)
            and all(
                _same_configuration(a, b) for a, b in zip(saved, current, strict=True)
            )
        )
    if type(current) is float and type(saved) is int:
        try:
            return float(saved) == current
        except OverflowError:
            return False
    return type(saved) is type(current) and saved == current


if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.scientist.methods.autotune.dedup import TrialDeduplicator


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
        dedup: TrialDeduplicator | None = None,
    ) -> None:
        if dedup is not None:
            from polisyos.scientist.methods.autotune.dedup import TrialDeduplicator

            if type(dedup) is not TrialDeduplicator:
                raise ValueError("search_dedup_requires_canonical_trial_deduplicator")
        self._dedup = dedup
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
        self._checkpoint_context: dict[str, Any] = {}
        self._publication_blocked = False

    def _configuration(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        config = self.controller._config
        stopping = config.stopping.checkpoint_state()

        def without_clock(value: dict[str, Any]) -> dict[str, Any]:
            return {
                **value,
                "started_at": None,
                "children": [without_clock(child) for child in value["children"]],
            }

        profile = self._replay_profile(
            self._checkpoint_context if context is None else context
        )
        return checkpoint_json(
            {
                "basis": self._basis,
                "replay_profile": profile,
                **(
                    {"trial_deduplication": self._deduplication_profile()}
                    if self._dedup is not None
                    else {}
                ),
                "hard_limit": config.max_iterations_hard_limit,
                "max_empty_generation_attempts": config.max_empty_generation_attempts,
                "stage_a_enabled": config.enable_stage_a,
                "batch_size": config.batch_size,
                **(
                    {"candidate_identity_profile": "native_service_run_candidate.v1"}
                    if self._canonical_native_generator() is not None
                    else {}
                ),
                "budget_key": config.budget_key,
                "budget_cost_key": config.budget_cost_key,
                "budget_owner_identity": self.controller._budget_owner_identity(),
                "initial_evaluations": config.initial_evaluations,
                "policy_objective_stack": self._policy_configuration(),
                "resource_arbiter_supported": config.resource_arbiter is None,
                "pareto_registry_supported": config.pareto_registry is None,
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

    def _replay_profile(self, context: dict[str, Any]) -> dict[str, Any] | None:
        """Recognize the actual factory or built-in objectives/stateless ports.

        Arbitrary objects and closures are not reconstructible from a build
        digest. Such generic profiles remain persistable and refuse resume.
        """
        from polisyos.scientist.methods.autotune.models import (
            BenchmarkSuite,
            SearchLoopSpec,
        )
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

        config = self.controller._config
        if (
            config.resource_arbiter is not None
            or config.pareto_registry is not None
            or (
                config.policy_objective_stack is not None
                and self._policy_configuration() is None
            )
        ):
            return None

        objectives = self.controller._config.objective.objectives
        stage_b = self.controller._stage_b
        closure = (
            inspect.getclosurevars(stage_b).nonlocals
            if inspect.isfunction(stage_b)
            else {}
        )
        runner, spec, suite = (
            closure.get("self"),
            closure.get("spec"),
            closure.get("suite_ref"),
        )
        if (
            type(runner) is SearchLoopRunner
            and isinstance(spec, SearchLoopSpec)
            and isinstance(suite, ArtifactRef)
            and runner._store is self._store
            and type(spec.mutation_codec) is PydanticMutationCodec
            and set(vars(spec.mutation_codec)) == {"_model_cls"}
            and getattr(runner._evaluate_candidate, "__func__", None)
            is SearchLoopRunner._evaluate_candidate
            and len(objectives) == 1
            and type(objectives[0]) is _AutotuneObjective
            and objectives[0]._policy == spec.promotion_policy
            and any(
                stage_b.__code__ is code
                for code in SearchLoopRunner.create_service.__code__.co_consts
                if isinstance(code, CodeType)
                and code.co_freevars == ("self", "spec", "suite_ref")
            )
        ):
            try:
                snapshot = self._read_snapshot(suite)
                suite_data = BenchmarkSuite.model_validate(
                    from_canonical_bytes(snapshot.data)
                )
                evaluator_config = self._evaluator_configuration(
                    spec.benchmark_evaluator, runner
                )
                if evaluator_config is None:
                    return None
                context_data = {
                    key: self._profile_value(value) for key, value in context.items()
                }
                model_path = inspect.getsourcefile(spec.mutation_codec._model_cls)
                factory_path = inspect.getsourcefile(SearchLoopRunner)
                if model_path is None or factory_path is None:
                    return None
            except (AttributeError, TypeError, ValueError, OSError, RuntimeError):
                return None
            return {
                "version": "native-autotune-replay.v2",
                "suite_ref": suite.model_dump(mode="json"),
                "suite_content_sha256": hashlib.sha256(snapshot.data).hexdigest(),
                "suite_manifest_profile_sha256": artifact_manifest_profile_sha256(
                    snapshot.manifest
                ),
                "suite_configuration": suite_data.model_dump(mode="json"),
                "data_inputs": [
                    self._profile_value(ref)
                    for ref in (suite_data.dataset_ref, suite_data.split_manifest_ref)
                    if ref is not None
                ],
                "policy": spec.promotion_policy.model_dump(mode="json"),
                "mutation_schema": spec.mutation_codec._model_cls.model_json_schema(),
                "mutation_model_build": hashlib.sha256(
                    Path(model_path).read_bytes()
                ).hexdigest(),
                "mutation_model_type": f"{spec.mutation_codec._model_cls.__module__}.{spec.mutation_codec._model_cls.__qualname__}",
                "evaluator_configuration": evaluator_config,
                "evaluation_context": context_data,
                "factory_build": hashlib.sha256(
                    Path(factory_path).read_bytes()
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
            if (
                not inspect.isfunction(function)
                or function.__closure__
                or vars(function)
            ):
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
        objective_path = inspect.getsourcefile(BudgetDeficitObjective)
        if objective_path is None:
            return None
        return {
            "version": "builtin-objective-stateless-ports.v1",
            "objective_build": hashlib.sha256(
                Path(objective_path).read_bytes()
            ).hexdigest(),
            "ports": ports,
        }

    def _profile_value(self, value: Any) -> Any:
        """Bind supported actual data/configuration values, refusing opaque ports."""
        if isinstance(value, ArtifactRef):
            snapshot = self._read_snapshot(value)
            return {
                "artifact_ref": value.model_dump(mode="json"),
                "content_sha256": hashlib.sha256(snapshot.data).hexdigest(),
                "manifest_profile_sha256": artifact_manifest_profile_sha256(
                    snapshot.manifest
                ),
            }
        if inspect.isfunction(value):
            variables = inspect.getclosurevars(value)
            if vars(value):
                raise ValueError("stateful function replay unavailable")
            return {
                "function_source_sha256": hashlib.sha256(
                    inspect.getsource(value).encode()
                ).hexdigest(),
                "defaults": checkpoint_json(value.__defaults__),
                "keyword_defaults": checkpoint_json(value.__kwdefaults__),
                "closure": checkpoint_json(variables.nonlocals),
                "globals": checkpoint_json(variables.globals),
            }
        if isinstance(value, dict):
            if any(not isinstance(key, str) for key in value):
                raise ValueError("non-string configuration key")
            return {key: self._profile_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._profile_value(item) for item in value]
        return checkpoint_json(value)

    def _policy_configuration(self) -> dict[str, Any] | None:
        stack = self.controller._config.policy_objective_stack
        if stack is None:
            return None
        from polisyos.scientist.policy_design.objectives import ObjectiveStack

        if type(stack) is not ObjectiveStack:
            return None
        path = inspect.getsourcefile(ObjectiveStack)
        if path is None:
            return None
        return {
            "parameters": checkpoint_json(vars(stack)),
            "implementation_sha256": hashlib.sha256(
                Path(path).read_bytes()
            ).hexdigest(),
        }

    def _evaluator_configuration(
        self, evaluator: Any, runner: Any
    ) -> dict[str, Any] | None:
        """Use actual declared configuration or the exact built-in constructor profile."""
        cls = type(evaluator)
        path = inspect.getsourcefile(cls)
        if path is None:
            return None
        configuration = getattr(evaluator, "checkpoint_configuration", None)
        if callable(configuration):
            configuration = configuration()
        else:
            builtin = {
                "calibration": "CalibrationMetaEvaluator",
                "cheap_stage": "CheapStageBenchmarkEvaluator",
                "claim_adjudication": "ClaimGoldEvaluator",
                "execution_plan": "ExecutionPlanBenchmarkEvaluator",
                "reflexion": "ReflexionRoutingEvaluator",
            }
            from importlib import import_module

            module = cls.__module__.rsplit(".", 1)[-1]
            if (
                cls.__module__ != f"polisyos.scientist.methods.autotune.{module}"
                or builtin.get(module) != cls.__name__
                or getattr(import_module(cls.__module__), cls.__name__) is not cls
                or set(vars(evaluator)) != {"_store", "_registry"}
                or evaluator._store not in (None, self._store)
                or evaluator._registry not in (None, runner._registry)
            ):
                return None
            configuration = {
                "store": "native_configured_store",
                "registry_root": str(runner._registry._root),
            }
        if not isinstance(configuration, dict):
            return None
        return {
            "type": f"{cls.__module__}.{cls.__qualname__}",
            "implementation_sha256": hashlib.sha256(
                Path(path).read_bytes()
            ).hexdigest(),
            "configuration": self._profile_value(configuration),
        }

    def checkpoint(self) -> ArtifactRef:
        """Persist an exact immutable replay view in the configured store."""
        self._require_publication_ready()
        if self._store is None:
            raise ValueError("search_checkpoint_store_not_configured")
        configuration = (
            self._admit_deduplication_configuration(self._checkpoint_context)
            if self._dedup is not None
            else self._configuration()
        )
        generator = self.controller._generator
        get_state = getattr(generator, "get_state", None)
        set_state = getattr(generator, "set_state", None)
        state = get_state() if callable(get_state) and callable(set_state) else None
        validate_history = getattr(generator, "validate_checkpoint_history", None)
        if state is not None and callable(validate_history):
            validate_history(self.controller._run_state.history, state)
        payload = SearchServiceCheckpoint(
            configuration=configuration,
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
                    name="polisyos.scientist.search.SearchServiceCheckpoint",
                    version="2.0",
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
        )
        snapshot = self._verified_snapshot(ref)
        if (
            SearchServiceCheckpoint.model_validate(_decode_checkpoint(snapshot.data))
            != payload
        ):
            raise ValueError("search_checkpoint_readback_mismatch")
        self.checkpoint_ref = ref.model_copy(
            update={
                "manifest_profile_sha256": artifact_manifest_profile_sha256(
                    snapshot.manifest
                ),
            }
        )
        return self.checkpoint_ref

    def _verified_snapshot(self, ref: ArtifactRef) -> Any:
        snapshot = self._read_snapshot(ref)
        manifest = snapshot.manifest
        if (
            manifest.kind != "scientist.search.service_checkpoint"
            or manifest.media_type != "application/json"
            or manifest.artifact_schema
            != SchemaInfo(
                name="polisyos.scientist.search.SearchServiceCheckpoint", version="2.0"
            )
        ):
            raise ValueError("search_resume_checkpoint_manifest_mismatch")
        return snapshot

    def _read_snapshot(self, ref: ArtifactRef) -> Any:
        read = getattr(self._store, "get_verified_snapshot", None)
        if not callable(read):
            raise ValueError("search_checkpoint_verified_snapshot_port_required")
        return read(ref)

    def _persist(self) -> None:
        if self._store is not None:
            self.checkpoint()

    def restore(
        self, ref: ArtifactRef, *, context: dict[str, Any] | None = None
    ) -> None:
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
        saved = SearchServiceCheckpoint.model_validate(
            _decode_checkpoint(snapshot.data)
        )
        if saved.configuration.get("replay_profile") is None:
            raise ValueError("search_resume_unsupported_objective_or_evaluator_profile")
        current_configuration = self._configuration(context or {})
        if current_configuration.get("replay_profile") is None:
            raise ValueError("search_resume_unsupported_objective_or_evaluator_profile")
        if not _same_configuration(saved.configuration, current_configuration):
            raise ValueError("search_resume_configuration_mismatch")
        if saved.configuration["diversity_enabled"]:
            raise ValueError("search_resume_unsupported_diversity_profile")
        generator = self.controller._generator
        restore_generator = getattr(generator, "set_state", None)
        validate_history = getattr(generator, "validate_checkpoint_history", None)
        if (
            saved.generator_state is None
            or not callable(restore_generator)
            or not callable(validate_history)
        ):
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
        started_at = (
            datetime.fromisoformat(saved.started_at) if saved.started_at else None
        )
        if started_at is not None and started_at.tzinfo is None:
            raise ValueError("search_resume_invalid_run_clock")
        pending = checkpoint_value(saved.pending_candidates)
        initial_candidate = checkpoint_value(saved.initial_candidate)
        generator_state = checkpoint_value(saved.generator_state)
        self._validate_native_candidate_identity(
            state, pending, set(saved.completed_candidate_ids), generator_state
        )
        if self._dedup is not None:
            self._deduplication_members(
                context or {},
                state=state,
                pending=pending,
                acknowledged_configuration=saved.configuration,
            )
        validate_history(state.history, generator_state)
        # Strategies own atomic admission of their numerical/RNG state. No run
        # ledger or candidate ownership changes precede that admission.
        restore_generator(generator_state)
        self.controller._config.stopping = stopping
        self.controller._run_state = state
        self._pending_candidates = {
            key: pending[key] for key in saved.pending_candidate_ids
        }
        self._initial_candidate_ids = set(saved.initial_candidate_ids)
        self._completed_candidate_ids = set(saved.completed_candidate_ids)
        self._ask_iteration = saved.ask_iteration
        self._initial_candidate = initial_candidate
        self._started_at = started_at
        self._stopped_reason = saved.stopping_reason
        self._failure = saved.failure
        self.checkpoint_ref = ref
        self._checkpoint_context = dict(context or {})

    def resume_search(self, *, context: dict[str, Any] | None = None) -> SearchResult:
        """Continue restored pending work; terminal stops remain terminal."""
        if not self.controller._run_state.search_id:
            raise ValueError("search_resume_requires_restored_run")
        if self._dedup is not None:
            self._admit_deduplication_configuration(context or {})
        if not _same_configuration(
            self._configuration(context or {}), self._configuration()
        ):
            raise ValueError("search_resume_context_configuration_mismatch")
        lock = self.controller._run_lock
        if not lock.acquire(blocking=False):
            raise RuntimeError("SearchController.run is not reentrant")
        try:
            if self.controller._status in (
                SearchStatus.STOPPED,
                SearchStatus.CONVERGED,
            ):
                return self._finish(
                    self._started_at or datetime.now(UTC), self._stopped_reason
                )
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
        self._require_publication_ready()
        if self.controller._config.budget_middleware is not None:
            # Accounting custody belongs to the durable resource owner. Admit
            # it before the proposal transaction so a refused external charge
            # cannot be represented by the old local zero diagnostic.
            admission_error = self.controller._refresh_budget_snapshot(context)
            if admission_error is not None:
                raise admission_error
        generator = self.controller._generator
        get_state = getattr(generator, "get_state", None)
        restore = getattr(generator, "set_state", None)
        generator_before = (
            deepcopy(get_state()) if callable(get_state) and callable(restore) else None
        )
        ledger_before = self.controller._run_state.snapshot()
        stopping_before = deepcopy(self.controller._config.stopping)
        pending_before = deepcopy(self._pending_candidates)
        initial_ids_before = set(self._initial_candidate_ids)
        initial_before = deepcopy(self._initial_candidate)
        iteration_before = self._ask_iteration
        context_before = dict(self._checkpoint_context)
        ref_before = self.checkpoint_ref
        initial_acknowledged = False
        try:
            if self._dedup is not None and self.checkpoint_ref is None:
                self._checkpoint_context = dict(context)
                self.controller._prepare_service_run()
                self.checkpoint()
                # Acknowledged custody survives a later proposal rollback. The
                # fresh reader resumes this prepared state, never a changed basis.
                ref_before = self.checkpoint_ref
                initial_acknowledged = True
            return self._ask_proposals(goal, search_space, context)
        except (Exception, asyncio.CancelledError):
            self.controller._run_state = ledger_before
            self.controller._config.stopping = stopping_before
            self._pending_candidates = pending_before
            self._initial_candidate_ids = initial_ids_before
            self._initial_candidate = initial_before
            self._ask_iteration = iteration_before
            self._checkpoint_context = context_before
            self.checkpoint_ref = ref_before
            if initial_acknowledged:
                self._publication_blocked = True
            if generator_before is not None:
                try:
                    restore(generator_before)
                except (Exception, asyncio.CancelledError):
                    self._publication_blocked = True
            elif self._store is not None:
                self._publication_blocked = True
            if self.controller._diversity_enabled:
                self._publication_blocked = True
            if self.controller._config.budget_middleware is not None:
                # The canonical owner may have changed after preflight. Local
                # proposal rollback does not roll back its durable accounting;
                # re-read its current admission/evidence instead of stale cost.
                self.controller._refresh_budget_snapshot(context)
            raise

    def _require_publication_ready(self) -> None:
        if self._publication_blocked:
            raise ValueError(
                "search_publication_rollback_unavailable_reopen_last_acknowledged_ref"
            )

    def _canonical_native_generator(self) -> Any | None:
        generator = self.controller._generator
        if type(generator).__module__ not in {
            "polisyos.scientist.methods.autotune.bayesian_generator",
            "polisyos.scientist.methods.search.sensitivity_adapter",
        }:
            return None
        from polisyos.scientist.methods.autotune.bayesian_generator import (
            BayesianCandidateGenerator,
        )
        from polisyos.scientist.methods.search.sensitivity_adapter import (
            SensitivityAwareCandidateGenerator,
        )

        base = (
            generator._base
            if type(generator) is SensitivityAwareCandidateGenerator
            else generator
        )
        return base if type(base) is BayesianCandidateGenerator else None

    def _bind_native_candidate_identity(
        self, candidate: dict[str, Any], candidate_id: str
    ) -> None:
        """Assign the admitted subject before its native history consumer sees it."""
        if self._canonical_native_generator() is None:
            return
        metadata = candidate.get("_strategy_metadata")
        if metadata is None:
            metadata = candidate["_strategy_metadata"] = {}
        if not isinstance(metadata, dict):
            raise ValueError("native_service_invalid_candidate_identity_carrier")
        if "candidate_id" in candidate:
            raise ValueError("native_service_conflicting_candidate_identity")
        metadata["candidate_id"] = (
            f"{self.controller._run_state.search_id}:{candidate_id}"
        )

    def _validate_native_candidate_identity(
        self,
        state: SearchRunState,
        pending: dict[str, dict[str, Any]],
        completed: set[str],
        generator_state: dict[str, Any],
    ) -> None:
        base = self._canonical_native_generator()
        if base is None:
            return
        prefix = f"{state.search_id}:"

        def subject(candidate: dict[str, Any]) -> str:
            metadata = candidate.get("_strategy_metadata")
            native_id = (
                metadata.get("candidate_id") if isinstance(metadata, dict) else None
            )
            if (
                "candidate_id" in candidate
                or not isinstance(native_id, str)
                or not native_id.startswith(prefix)
                or not native_id.removeprefix(prefix)
            ):
                raise ValueError("search_resume_native_candidate_identity_mismatch")
            return native_id.removeprefix(prefix)

        for public_id, candidate in pending.items():
            if subject(candidate) != public_id:
                raise ValueError(
                    "search_resume_native_candidate_identity_pending_mismatch"
                )
        seen: set[str] = set()
        for row in state.history:
            if row.iteration == -1:
                continue  # Transferred observations retain their original admitted subjects.
            public_id = subject(row.candidate)
            parts = base._history_parts(row)
            identity = base._history_identity(
                candidate=parts[0],
                stage_b_result=parts[1],
                entry_mapping=parts[2],
                entry_metadata=parts[3],
            )
            if (
                public_id not in completed
                or public_id in seen
                or identity is None
                or identity.get("candidate_id") != f"{prefix}{public_id}"
            ):
                raise ValueError(
                    "search_resume_native_candidate_identity_history_mismatch"
                )
            seen.add(public_id)
        candidates = [row.candidate for row in state.history]
        derived = [point.candidate for point in state.pareto_points]
        if state.best_candidate is not None:
            derived.append(state.best_candidate)
        if any(
            not any(_same_configuration(candidate, original) for original in candidates)
            for candidate in derived
        ):
            raise ValueError(
                "search_resume_native_candidate_identity_projection_mismatch"
            )

    def _deduplication_profile(self) -> dict[str, str]:
        from polisyos.scientist.methods.search.frontier import policy_candidate_hash

        profile = {"version": "native_completed_pending.v1"}
        for name, source in (
            ("deduplication_sha256", inspect.getsourcefile(type(self._dedup))),
            ("candidate_identity_sha256", inspect.getsourcefile(policy_candidate_hash)),
            ("admission_sha256", inspect.getsourcefile(NativeSearchService)),
        ):
            if source is None:
                raise ValueError("search_dedup_source_profile_unavailable")
            try:
                profile[name] = hashlib.sha256(Path(source).read_bytes()).hexdigest()
            except OSError as exc:
                raise ValueError("search_dedup_source_profile_unavailable") from exc
        return profile

    def _admit_deduplication_configuration(
        self,
        context: dict[str, Any],
        *,
        acknowledged_configuration: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Bind active effects to the sole last-qualified CAS acknowledgement."""

        def data_context(value: object) -> None:
            if callable(value):
                raise ValueError("search_dedup_opaque_callback_context_unsupported")
            if isinstance(value, dict):
                for item in value.values():
                    data_context(item)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    data_context(item)

        data_context(context)
        configuration = self._configuration(context)
        profile = configuration.get("replay_profile")
        if (
            not isinstance(profile, dict)
            or profile.get("version") != "native-autotune-replay.v2"
        ):
            raise ValueError(
                "search_dedup_requires_native_content_bound_factory_profile"
            )
        if acknowledged_configuration is None and self.checkpoint_ref is not None:
            saved = SearchServiceCheckpoint.model_validate(
                _decode_checkpoint(self._verified_snapshot(self.checkpoint_ref).data)
            )
            if saved.run_state.get("search_id") != self.controller._run_state.search_id:
                raise ValueError("search_dedup_acknowledged_run_mismatch")
            acknowledged_configuration = saved.configuration
        if acknowledged_configuration is not None:
            if not _same_configuration(configuration, acknowledged_configuration):
                raise ValueError("search_dedup_acknowledged_configuration_mismatch")
        elif (
            not self.controller._run_state.search_id
            or self._ask_iteration
            or self._pending_candidates
            or self._completed_candidate_ids
            or any(row.iteration >= 0 for row in self.controller._history)
        ):
            raise ValueError("search_dedup_requires_initial_acknowledged_checkpoint")
        return configuration

    def _deduplication_members(
        self,
        context: dict[str, Any],
        *,
        state: SearchRunState | None = None,
        pending: dict[str, dict[str, Any]] | None = None,
        acknowledged_configuration: dict[str, Any] | None = None,
    ) -> tuple[str, list[dict[str, Any]], Any]:
        """Derive membership from real completed custody, never a cached evaluation."""
        from polisyos.common.serialization import finite_real_scalar
        from polisyos.scientist.methods.autotune.models import (
            BenchmarkEvaluation,
            benchmark_comparison_basis,
            benchmark_evaluator_profile,
            load_model_artifact,
        )

        configuration = self._admit_deduplication_configuration(
            context, acknowledged_configuration=acknowledged_configuration
        )
        closure = inspect.getclosurevars(self.controller._stage_b).nonlocals
        runner, spec, suite = closure["self"], closure["spec"], closure["suite_ref"]
        basis = benchmark_comparison_basis(
            self._store,
            suite,
            spec.promotion_policy,
            benchmark_evaluator_profile(spec.benchmark_evaluator),
        )

        def encode(candidate: dict[str, Any]) -> dict[str, Any]:
            admitted = spec.mutation_codec.decode(
                runner._codec_payload(spec, candidate)
            ).model_dump(mode="json")
            if "_strategy_metadata" in candidate:
                admitted["_strategy_metadata"] = candidate["_strategy_metadata"]
            return admitted

        members = []
        ledger = state if state is not None else self.controller._run_state
        for row in ledger.history:
            if (
                row.iteration < 0
                or not row.stage_a_passed
                or row.policy_evaluation_status == "invalid"
            ):
                continue
            results = (row.stage_b_result or {}).get("simulation_results", {})
            candidate_ref = ArtifactRef.model_validate(
                results.get("candidate_artifact_ref")
            )
            evaluation_ref = ArtifactRef.model_validate(
                results.get("evaluation_artifact_ref")
            )
            supplied_suite = ArtifactRef.model_validate(
                results.get("suite_artifact_ref")
            )
            if any(
                ref.manifest_profile_sha256 is None
                for ref in (candidate_ref, evaluation_ref, supplied_suite)
            ):
                raise ValueError(
                    "search_dedup_requires_exact_completed_artifact_profiles"
                )
            self._read_snapshot(candidate_ref)
            self._read_snapshot(evaluation_ref)
            self._read_snapshot(supplied_suite)
            actual_candidate = load_model_artifact(
                self._store, candidate_ref, spec.mutation_codec._model_cls
            )
            actual_evaluation = load_model_artifact(
                self._store, evaluation_ref, BenchmarkEvaluation
            )
            admitted = encode(row.candidate)
            typed_admitted = {
                key: value
                for key, value in admitted.items()
                if key != "_strategy_metadata"
            }
            if (
                supplied_suite != suite
                or actual_evaluation.candidate_ref != candidate_ref
                or actual_evaluation.comparison_basis != basis
                or not _same_configuration(
                    actual_candidate.model_dump(mode="json"), typed_admitted
                )
            ):
                raise ValueError("search_dedup_completed_content_or_basis_mismatch")
            measured = finite_real_scalar(
                actual_evaluation.metrics_for_split(
                    spec.promotion_policy.compare_split
                ).get(spec.promotion_policy.primary_metric)
            )
            if actual_evaluation.status != "ok" or measured is None:
                continue
            members.append(admitted)
        for candidate in (
            pending if pending is not None else self._pending_candidates
        ).values():
            if extract_sentinel_metadata(candidate) is None:
                members.append(encode(candidate))
        scope = hashlib.sha256(
            json.dumps(
                {"search_id": ledger.search_id, "configuration": configuration},
                sort_keys=True,
                allow_nan=False,
            ).encode()
        ).hexdigest()
        return scope, members, encode

    def _ask_proposals(
        self,
        goal: dict[str, Any] | None,
        search_space: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> list[CandidateProposal]:
        del goal, search_space
        if self._dedup is not None:
            scope, members, encode = self._deduplication_members(context)
            self._dedup.reset(scope)
            for member in members:
                self._dedup.register(member, scope)
        self._checkpoint_context = dict(context)
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
            if self._dedup is not None and extract_sentinel_metadata(payload) is None:
                admitted = encode(payload)
                if self._dedup.is_duplicate(admitted, scope):
                    continue
                self._dedup.register(admitted, scope)
            if "candidate_id" not in payload:
                candidate_id = f"candidate_{self._ask_iteration}_{index}"
            else:
                raw_candidate_id = payload["candidate_id"]
                if not isinstance(raw_candidate_id, str) or not raw_candidate_id:
                    raise ValueError(
                        "search candidate_id must be an explicit non-empty string"
                    )
                candidate_id = raw_candidate_id
            if (
                candidate_id in pending
                or candidate_id in self._pending_candidates
                or candidate_id in self._completed_candidate_ids
            ):
                raise ValueError(f"duplicate search candidate id: {candidate_id}")
            candidate = deepcopy(payload)
            self._bind_native_candidate_identity(candidate, candidate_id)
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
        self._require_publication_ready()
        if not isinstance(candidate_id, str) or not candidate_id:
            raise KeyError(candidate_id)
        if candidate_id in self._completed_candidate_ids:
            raise ValueError(f"duplicate search evaluation: {candidate_id}")
        if candidate_id not in self._pending_candidates:
            raise KeyError(candidate_id)
        if self._dedup is not None:
            self._admit_deduplication_configuration(self._checkpoint_context)

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
            raise TypeError(
                "EvaluationBundle.stage_b_result.simulation_results must be a mapping"
            )

        feedback = stage_b_result.get("feedback")
        if feedback is None:
            stage_b_result["feedback"] = {
                "verdict": "APPROVE" if evaluation.is_promising else "REJECT",
            }
        elif not isinstance(feedback, dict):
            raise TypeError(
                "EvaluationBundle.stage_b_result.feedback must be a mapping"
            )
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
            if self._dedup is not None:
                self._require_publication_ready()
                # Only this explicit new-run lifecycle retires its prior basis;
                # active empty/pending checkpoints never implicitly rebind it.
                self.checkpoint_ref = None
            self._checkpoint_context = dict(initial_context)
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
        except (Exception, asyncio.CancelledError) as exc:
            self.controller._status = SearchStatus.FAILED
            self._failure = f"{type(exc).__name__}: {exc}"
            try:
                self._persist()
            except (Exception, asyncio.CancelledError):
                self._publication_blocked = True
                logger.warning(
                    "Search failure checkpoint unavailable; reopen last acknowledged ref"
                )
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

    def _finish(
        self, start_time: datetime, stopping_reason: str | None
    ) -> SearchResult:
        result = self.controller._finish_native_run(
            start_time=start_time,
            stopping_reason=stopping_reason,
        )
        self._stopped_reason = result.stopping_reason
        self._persist()
        if self.checkpoint_ref is not None:
            result.telemetry["checkpoint_ref"] = self.checkpoint_ref.model_dump(
                mode="json"
            )
        return result

    def _stopping_reason(self, context: dict[str, Any]) -> str | None:
        admission_error = self.controller._refresh_budget_snapshot(context)
        stop_check = self.controller._config.stopping.check(
            [
                self.controller._to_history_dict(item)
                for item in self.controller._history
            ],
            self.controller._stopping_state(),
        )
        if stop_check.should_stop:
            return stop_check.reason
        if admission_error is not None:
            return f"budget_owner_admission_refused:{type(admission_error).__name__}"
        return None

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
        self.controller._run_state.generation_transition = (
            GenerationTransition.EXHAUSTED
        )
        self._stop("generation_exhausted")
        return "generation_exhausted"

    def _mark_nonempty_generation(self) -> None:
        if self.controller._run_state.empty_generation_attempts:
            self.controller._run_state.generation_transition = (
                GenerationTransition.TRANSIENT_EMPTY
            )
            self.controller._run_state.empty_generation_attempts = 0

    def _evaluate_batch(
        self,
        *,
        batch: list[CandidateProposal],
        generated: bool,
        initial_context: dict[str, Any],
    ) -> str | None:
        for proposal in batch:
            if self._dedup is not None:
                self._admit_deduplication_configuration(initial_context)
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
