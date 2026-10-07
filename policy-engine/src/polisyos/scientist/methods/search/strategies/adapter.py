"""Adapter bridging SearchStrategy and SearchController CandidateGenerator protocol."""

from __future__ import annotations

import hashlib
import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any

from polisyos.common.serialization import stable_json_dumps
from polisyos.scientist.methods.search.controller import SearchIteration
from polisyos.scientist.methods.search.objective import ObjectiveValue
from polisyos.scientist.methods.search.run_state import _canonical_checkpoint_owner, checkpoint_json
from polisyos.scientist.methods.search.strategies.base import BaseSearchStrategy, SearchStrategy
from polisyos.scientist.methods.search.strategies.codec import ParameterCodec, ScalarParameterCodec
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    Evaluation,
    EvaluationStatus,
    StrategyState,
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
    ):
        self._strategy = strategy
        self._space = space
        self._codec = codec or ScalarParameterCodec()
        self._default_objective_extractor = objective_extractor is None
        self._objective_extractor = objective_extractor or (
            lambda iteration: list(iteration.objective_details)
        )
        self._evaluations: list[Evaluation] = []
        self._synced_len = 0
        self._restored_history_digests: list[str] | None = None
        self._restored_history_rows: list[dict[str, Any]] | None = None

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

    def _checkpoint_configuration(self) -> dict[str, Any]:
        if type(self._space) is not SearchSpace:
            raise ValueError("strategy_adapter_checkpoint_requires_canonical_search_space")
        if type(self._codec) is not ScalarParameterCodec:
            raise ValueError("strategy_adapter_checkpoint_requires_scalar_parameter_codec")
        if not self._default_objective_extractor:
            raise ValueError("strategy_adapter_checkpoint_requires_default_objective_extractor")
        if not callable(getattr(self._strategy, "get_state", None)) or not callable(
            getattr(self._strategy, "set_state", None)
        ):
            raise ValueError("strategy_adapter_checkpoint_requires_strategy_state_api")
        try:
            paths = [
                inspect.getsourcefile(type(value)) for value in (self, self._strategy, self._codec)
            ]
        except TypeError as exc:
            raise ValueError(
                "strategy_adapter_checkpoint_requires_declared_implementation"
            ) from exc
        if any(path is None or not Path(path).is_file() for path in paths):
            raise ValueError("strategy_adapter_checkpoint_requires_declared_implementation")
        return checkpoint_json(
            {
                "space": self._space.sobol_space_fingerprint(),
                "strategy_type": f"{type(self._strategy).__module__}.{type(self._strategy).__qualname__}",
                "strategy_configuration": getattr(self._strategy, "_config", None),
                "codec_configuration": self._codec,
                "objective_extractor": "search_iteration_objective_details.v1",
                "implementation_sha256": [
                    hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in paths
                ],
            }
        )

    @staticmethod
    def _evaluation_digest(evaluation: Evaluation) -> str:
        return hashlib.sha256(stable_json_dumps(checkpoint_json(evaluation)).encode()).hexdigest()

    def get_state(self) -> dict[str, Any] | None:
        """Return supported state; live-only profiles retain unavailable discovery."""
        if (
            not _canonical_checkpoint_owner(self, StrategyAdapter)
            or type(self._space) is not SearchSpace
            or type(self._codec) is not ScalarParameterCodec
            or not self._default_objective_extractor
            or not callable(getattr(self._strategy, "get_state", None))
            or not callable(getattr(self._strategy, "set_state", None))
            or (
                not self._base_update_has_no_effects()
                and not callable(getattr(self._strategy, "validate_consumed_history", None))
            )
        ):
            return None
        try:
            configuration = self._checkpoint_configuration()
        except ValueError as exc:
            if str(exc) != "strategy_adapter_checkpoint_requires_declared_implementation":
                raise
            return None
        strategy_state = self._strategy.get_state()
        if not isinstance(strategy_state, StrategyState):
            raise ValueError("strategy_adapter_checkpoint_requires_strategy_state")
        digests = (
            list(self._restored_history_digests)
            if self._restored_history_digests is not None
            else [self._evaluation_digest(row) for row in self._evaluations]
        )
        if len(digests) != self._synced_len:
            raise ValueError("strategy_adapter_checkpoint_history_count_mismatch")
        rows = (
            checkpoint_json(self._restored_history_rows)
            if self._restored_history_rows is not None
            else checkpoint_json(self._evaluations)
        )
        try:
            self._validate_strategy_consumption(rows, strategy_state)
        except ValueError as exc:
            if str(exc) != "strategy_adapter_checkpoint_consumption_profile_unsupported":
                raise
            return None
        return {
            "version": "strategy_adapter.v2",
            "configuration": configuration,
            "strategy_state": strategy_state.to_artifact().decode("utf-8"),
            "history_digests": digests,
            "consumed_history_count": self._synced_len,
            "history_rows": rows,
        }

    def _base_update_has_no_effects(self) -> bool:
        update = self._strategy.update
        return (
            isinstance(self._strategy, BaseSearchStrategy)
            and getattr(update, "__self__", None) is self._strategy
            and getattr(update, "__func__", None) is BaseSearchStrategy.update
        )

    def _validate_strategy_consumption(
        self, rows: list[dict[str, Any]], strategy_state: StrategyState
    ) -> None:
        # Base update has no effects. An overridden update must prove its own
        # saved consumption; a cursor declared by the adapter cannot prove an
        # arbitrary opaque strategy's update-owned state.
        if self._base_update_has_no_effects():
            return
        validate = getattr(self._strategy, "validate_consumed_history", None)
        if not callable(validate):
            raise ValueError("strategy_adapter_checkpoint_consumption_profile_unsupported")
        validate(rows, strategy_state)

    def _admit_checkpoint(
        self, state: dict[str, Any]
    ) -> tuple[StrategyState, list[str], list[dict[str, Any]]]:
        if not _canonical_checkpoint_owner(self, StrategyAdapter):
            raise ValueError("strategy_adapter_checkpoint_owner_profile_unsupported")
        if not isinstance(state, dict) or set(state) != {
            "version",
            "configuration",
            "strategy_state",
            "history_digests",
            "consumed_history_count",
            "history_rows",
        }:
            raise ValueError("strategy_adapter_checkpoint_fields_invalid")
        if state["version"] != "strategy_adapter.v2":
            raise ValueError("strategy_adapter_checkpoint_version_unsupported")
        if stable_json_dumps(state["configuration"]) != stable_json_dumps(
            self._checkpoint_configuration()
        ):
            raise ValueError("strategy_adapter_checkpoint_configuration_mismatch")
        payload = state["strategy_state"]
        if not isinstance(payload, str):
            raise ValueError("strategy_adapter_checkpoint_strategy_artifact_required")
        strategy_state = StrategyState.from_artifact(payload.encode("utf-8"))
        digests = state["history_digests"]
        if not isinstance(digests, list) or any(
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            for digest in digests
        ):
            raise ValueError("strategy_adapter_checkpoint_history_digests_invalid")
        count = state["consumed_history_count"]
        rows = checkpoint_json(state["history_rows"])
        if (
            type(count) is not int
            or count < 0
            or not isinstance(rows, list)
            or any(not isinstance(row, dict) for row in rows)
            or len(rows) != count
            or len(digests) != count
            or [hashlib.sha256(stable_json_dumps(row).encode()).hexdigest() for row in rows]
            != digests
        ):
            raise ValueError("strategy_adapter_checkpoint_history_prefix_mismatch: incomplete consumption")
        self._validate_strategy_consumption(rows, strategy_state)
        return strategy_state, list(digests), rows

    def validate_checkpoint_history(
        self, history: list[SearchIteration], state: dict[str, Any]
    ) -> None:
        """Admit the actual saved history before the service restores live state.

        Args:
            history: Complete original history read from the service checkpoint.
            state: The paired adapter checkpoint from that same artifact.
        """
        if not _canonical_checkpoint_owner(self, StrategyAdapter):
            raise ValueError("strategy_adapter_checkpoint_owner_profile_unsupported")
        _, digests, rows = self._admit_checkpoint(state)
        actual = [self._to_evaluation(row) for row in history]
        if (
            len(actual) < len(rows)
            or checkpoint_json(actual[: len(rows)]) != rows
            or [self._evaluation_digest(row) for row in actual[: len(rows)]] != digests
        ):
            raise ValueError("strategy_adapter_checkpoint_history_prefix_mismatch")

    def set_state(self, state: dict[str, Any]) -> None:
        """Delegate numerical/RNG admission, then retain the saved history custody.

        Args:
            state: Supported adapter checkpoint with the original strategy artifact.
        """
        if not _canonical_checkpoint_owner(self, StrategyAdapter):
            raise ValueError("strategy_adapter_checkpoint_owner_profile_unsupported")
        strategy_state, digests, rows = self._admit_checkpoint(state)
        self._strategy.set_state(strategy_state)
        self._evaluations = []
        self._synced_len = len(digests)
        self._restored_history_digests = digests
        self._restored_history_rows = rows

    def _sync_history(self, history: list[SearchIteration]) -> None:
        if self._restored_history_digests is not None:
            prefix = [self._to_evaluation(row) for row in history[: self._synced_len]]
            if (
                len(prefix) != self._synced_len
                or [self._evaluation_digest(row) for row in prefix]
                != self._restored_history_digests
                or checkpoint_json(prefix) != self._restored_history_rows
            ):
                raise ValueError("strategy_adapter_checkpoint_history_prefix_mismatch")
            # These updates are already represented in the restored strategy.
            # Rebuild the adapter's actual history without replaying effects.
            self._evaluations = prefix
            self._restored_history_digests = None
            self._restored_history_rows = None
        if self._synced_len > len(history):
            self._evaluations = []
            self._synced_len = 0

        for iteration in history[self._synced_len :]:
            evaluation = self._to_evaluation(iteration)
            self._evaluations.append(evaluation)
            self._strategy.update(evaluation)
        self._synced_len = len(history)

    def _to_evaluation(self, iteration: SearchIteration) -> Evaluation:
        params = self._codec.encode(iteration.candidate)
        normalized = self._space.normalize(params)

        if not iteration.stage_a_passed:
            status = EvaluationStatus.STAGE_A_REJECT
        elif iteration.stage_b_result is None:
            status = EvaluationStatus.STAGE_B_ERROR
        else:
            status = EvaluationStatus.SUCCESS

        return Evaluation(
            candidate_id=f"iter_{iteration.iteration}",
            params=params,
            params_normalized=normalized,
            objectives=self._objective_extractor(iteration),
            scalar_score=float(iteration.objective_value),
            stage_a_passed=iteration.stage_a_passed,
            stage_b_result=iteration.stage_b_result,
            status=status,
            timestamp=iteration.timestamp,
            wall_time_seconds=iteration.duration_seconds,
        )

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
