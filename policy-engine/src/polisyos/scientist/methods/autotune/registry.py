"""Public autotune registry module API."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from math import isfinite
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Any, Protocol, cast

from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
from polisyos.data_forge.read_api import academic

from .models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSuite,
    ChampionPointer,
    MetricDirection,
    MutationArtifact,
    PromotionDecision,
    PromotionPolicy,
    benchmark_comparison_basis,
    default_search_registry_root,
    load_benchmark_inputs,
    load_json_artifact,
    load_model_artifact,
    require_benchmark_input,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore


class _MetricComparison(Protocol):
    def __call__(
        self, *, current: float, new: float, direction: str, min_improvement: float
    ) -> bool: ...


claim_promotion_policy = cast("Callable[[], dict[str, Any]]", academic.claim_promotion_policy)
metric_is_improved = cast("_MetricComparison", academic.metric_is_improved)
read_claim_promotion_predecessor = cast(
    "Callable[[Path, dict[str, Any]], dict[str, Any] | None]",
    academic.read_claim_promotion_predecessor,
)


class ChampionRegistry:
    """Atomic registry of active autotune champions."""

    def __init__(
        self,
        root: Path | None = None,
        *,
        store: ArtifactStore,
    ) -> None:
        self._root = (root or default_search_registry_root()).resolve()
        self._store = store

    def get(self, loop_id: str) -> ChampionPointer | None:
        path = self._pointer_path(loop_id)
        if not path.exists():
            return None
        return ChampionPointer.model_validate_json(path.read_text(encoding="utf-8"))

    def seed_baseline(
        self,
        loop_id: str,
        *,
        candidate_ref: ArtifactRef,
        evaluation_ref: ArtifactRef,
        suite_version: str = "1.0",
        metadata: dict[str, Any] | None = None,
    ) -> ChampionPointer:
        with self._promotion_lock(loop_id):
            existing = self.get(loop_id)
            if existing is not None:
                return existing
            pointer = ChampionPointer(
                loop_id=loop_id,
                candidate_ref=candidate_ref,
                evaluation_ref=evaluation_ref,
                metrics={},
                suite_version=suite_version,
                search_space_version=self._search_space_version(candidate_ref),
                metadata={"seeded_baseline": True, **(metadata or {})},
            )
            self._write_pointer(loop_id, pointer)
            return pointer

    def consider_promotion(
        self,
        loop_id: str,
        candidate_ref: ArtifactRef,
        evaluation_ref: ArtifactRef,
        policy: PromotionPolicy,
        *,
        suite_ref: ArtifactRef | None = None,
        pareto_promoter: Any | None = None,
    ) -> PromotionDecision:
        evaluation = load_model_artifact(self._store, evaluation_ref, BenchmarkEvaluation)
        if not isinstance(evaluation, BenchmarkEvaluation):
            raise TypeError("Expected BenchmarkEvaluation")
        with self._promotion_lock(loop_id):
            current = self.get(loop_id)
            rejection = self._promotion_binding_failure(
                loop_id=loop_id,
                candidate_ref=candidate_ref,
                evaluation=evaluation,
                evaluation_ref=evaluation_ref,
                policy=policy,
                suite_ref=suite_ref,
            )
            if rejection is not None:
                return PromotionDecision(
                    loop_id=loop_id,
                    promoted=False,
                    reason=rejection,
                    champion=current,
                    previous_champion=current,
                )
            return self._consider_promotion_locked(
                loop_id=loop_id,
                candidate_ref=candidate_ref,
                evaluation=evaluation,
                evaluation_ref=evaluation_ref,
                policy=policy,
                suite_ref=suite_ref,
                current=current,
            )

    def _promotion_binding_failure(
        self,
        *,
        loop_id: str,
        candidate_ref: ArtifactRef,
        evaluation: BenchmarkEvaluation,
        evaluation_ref: ArtifactRef,
        policy: PromotionPolicy,
        suite_ref: ArtifactRef | None,
    ) -> str | None:
        if policy.loop_id != loop_id:
            return "policy_loop_mismatch"
        if evaluation.loop_id != loop_id:
            return "evaluation_loop_mismatch"
        if artifact_ref_identity_key(evaluation.candidate_ref) != artifact_ref_identity_key(
            candidate_ref
        ):
            return "evaluation_candidate_mismatch"
        candidate = load_json_artifact(self._store, candidate_ref)
        if not isinstance(candidate, dict) or candidate.get("loop_id") != loop_id:
            return "candidate_loop_mismatch"
        if candidate_ref.kind != f"scientist.autotune.{loop_id}.candidate":
            return "candidate_type_mismatch"
        manifest = self._store.get_manifest(evaluation_ref)
        if (
            evaluation_ref.kind != f"scientist.autotune.{loop_id}.evaluation"
            or manifest.artifact_schema is None
            or manifest.artifact_schema.name
            != "polisyos.scientist.methods.autotune.BenchmarkEvaluation"
            or manifest.artifact_schema.version != evaluation.suite_version
        ):
            return "evaluation_type_mismatch"
        require_benchmark_input(self._store, evaluation_ref, candidate_ref, role="candidate")
        if suite_ref is None:
            if loop_id != "claim_adjudication":
                return "suite_ref_required"
            # The claim-adjudication producer predates the generic split binding
            # and is independently replayed by its verifier. Keep that narrow
            # compatibility path explicit; ordinary loops remain fail-closed.
            if evaluation.runtime_split_type is not None and (
                evaluation.runtime_split_type != policy.compare_split
            ):
                return "runtime_split_mismatch"
            return None

        resolved_split = evaluation.runtime_split_type
        if resolved_split is None:
            resolved_split = evaluation.resolved_runtime_split_type()
        if resolved_split != policy.compare_split and loop_id != "claim_adjudication":
            return "runtime_split_mismatch"
        if (
            evaluation.runtime_split_type is not None
            and evaluation.runtime_split_type != policy.compare_split
        ):
            return "runtime_split_mismatch"

        suite = load_model_artifact(self._store, suite_ref, BenchmarkSuite)
        if not isinstance(suite, BenchmarkSuite):
            raise TypeError("Expected BenchmarkSuite")
        if evaluation.suite_id != suite.suite_id:
            return "suite_mismatch"
        if evaluation.suite_version != suite.suite_version:
            return "suite_version_mismatch"
        for artifact_ref in (candidate_ref, evaluation_ref):
            try:
                require_benchmark_input(
                    self._store, artifact_ref, suite_ref, role="benchmark_suite"
                )
            except ValueError:
                return "suite_basis_mismatch"
        return self._evaluation_basis_failure(evaluation, evaluation_ref, policy, suite_ref)

    def _evaluation_basis_failure(
        self,
        evaluation: BenchmarkEvaluation,
        evaluation_ref: ArtifactRef,
        policy: PromotionPolicy,
        suite_ref: ArtifactRef,
    ) -> str | None:
        basis = evaluation.comparison_basis
        if basis is None:
            return "evaluation_comparison_basis_required"
        suite = load_model_artifact(self._store, suite_ref, BenchmarkSuite)
        if evaluation.suite_id != suite.suite_id or evaluation.suite_version != suite.suite_version:
            return "evaluation_suite_identity_mismatch"
        manifest = self._store.get_manifest(evaluation_ref)
        if (
            evaluation_ref.kind != f"scientist.autotune.{evaluation.loop_id}.evaluation"
            or manifest.artifact_schema is None
            or manifest.artifact_schema.name
            != "polisyos.scientist.methods.autotune.BenchmarkEvaluation"
            or manifest.artifact_schema.version != evaluation.suite_version
        ):
            return "evaluation_type_mismatch"
        expected = benchmark_comparison_basis(
            self._store, suite_ref, policy, basis.evaluator_profile
        )
        if basis != expected:
            return "evaluation_comparison_basis_mismatch"
        require_benchmark_input(self._store, evaluation_ref, suite_ref, role="benchmark_suite")
        if basis.dataset_ref is not None:
            require_benchmark_input(
                self._store, evaluation_ref, basis.dataset_ref, role="benchmark_dataset"
            )
        if basis.split_manifest_ref is not None:
            require_benchmark_input(
                self._store, evaluation_ref, basis.split_manifest_ref, role="benchmark_split"
            )
        if evaluation.resolved_runtime_split_type() != policy.compare_split:
            return "runtime_split_mismatch"
        if basis.data_basis == "dataset":
            _, split = load_benchmark_inputs(self._store, suite)
            count = len(split.ids_for_split(policy.compare_split))
            if evaluation.sample_count(split=policy.compare_split) != count or not count:
                return "evaluation_dataset_sample_count_mismatch"
        if evaluation.status != "ok":
            return "evaluation_status_not_comparable"
        if any(
            not isfinite(float(value))
            for value in evaluation.metrics_for_split(policy.compare_split).values()
        ):
            return "evaluation_metrics_not_finite"
        return None

    def _incumbent_comparison(
        self,
        *,
        current: ChampionPointer,
        evaluation: BenchmarkEvaluation,
        policy: PromotionPolicy,
        suite_ref: ArtifactRef,
        evaluation_ref: ArtifactRef,
    ) -> tuple[BenchmarkEvaluation | None, str | None]:
        incumbent = load_model_artifact(self._store, current.evaluation_ref, BenchmarkEvaluation)
        if (
            current.loop_id != policy.loop_id
            or incumbent.loop_id != current.loop_id
            or artifact_ref_identity_key(incumbent.candidate_ref)
            != artifact_ref_identity_key(current.candidate_ref)
        ):
            return None, "champion_evaluation_binding_mismatch"
        candidate = load_json_artifact(self._store, current.candidate_ref)
        if not isinstance(candidate, dict) or candidate.get("loop_id") != current.loop_id:
            return None, "champion_candidate_binding_mismatch"
        require_benchmark_input(
            self._store, current.evaluation_ref, current.candidate_ref, role="candidate"
        )
        previous_policy = current.metadata.get("promoted_by_policy")
        seeded = (
            incumbent.status == "seeded_baseline"
            and not current.metrics
            and current.metadata.get("seeded_baseline") is True
        )
        if not seeded and previous_policy != policy.model_dump(mode="json"):
            return None, "champion_policy_basis_mismatch"
        old_split = BenchmarkSplit(
            current.metadata.get("compare_split", policy.compare_split.value)
        )
        if current.metrics != incumbent.metrics_for_split(old_split):
            return None, "champion_evaluation_metrics_mismatch"
        ref = evaluation.incumbent_evaluation_ref
        if ref is None:
            if incumbent.comparison_basis != evaluation.comparison_basis:
                return None, "champion_comparison_basis_mismatch"
            failure = self._evaluation_basis_failure(
                incumbent, current.evaluation_ref, policy, suite_ref
            )
            return (None, failure) if failure else (incumbent, None)
        require_benchmark_input(
            self._store, evaluation_ref, ref, role="comparison_incumbent_evaluation"
        )
        fresh = load_model_artifact(self._store, ref, BenchmarkEvaluation)
        if artifact_ref_identity_key(fresh.candidate_ref) != artifact_ref_identity_key(
            current.candidate_ref
        ):
            return None, "incumbent_changed_during_evaluation"
        if (
            fresh.loop_id != current.loop_id
            or fresh.comparison_basis != evaluation.comparison_basis
            or fresh.incumbent_evaluation_ref is not None
        ):
            return None, "incumbent_reevaluation_basis_mismatch"
        require_benchmark_input(self._store, ref, current.candidate_ref, role="candidate")
        failure = self._evaluation_basis_failure(fresh, ref, policy, suite_ref)
        return (None, failure) if failure else (fresh, None)

    def _consider_promotion_locked(
        self,
        *,
        loop_id: str,
        candidate_ref: ArtifactRef,
        evaluation: BenchmarkEvaluation,
        evaluation_ref: ArtifactRef,
        policy: PromotionPolicy,
        suite_ref: ArtifactRef | None,
        current: ChampionPointer | None,
    ) -> PromotionDecision:
        if loop_id == "claim_adjudication":
            if policy.model_dump(mode="json") != claim_promotion_policy():
                return PromotionDecision(
                    loop_id=loop_id,
                    promoted=False,
                    reason="claim_promotion_policy_mismatch",
                    champion=current,
                    previous_champion=current,
                )
            basis_path = self._root / loop_id / "promotion_basis.json"
            if current is not None:
                read_claim_promotion_predecessor(self._root, current.model_dump(mode="json"))
            elif basis_path.exists():
                raise ValueError("claim_adjudication_promotion_basis_current_pointer_missing")
        if (
            current is not None
            and suite_ref is not None
            and evaluation.incumbent_evaluation_ref is None
        ):
            if loop_id != "claim_adjudication" and (
                current.metadata.get("suite_id") is None
                or current.metadata.get("suite_ref") is None
            ):
                return PromotionDecision(
                    loop_id=loop_id,
                    promoted=False,
                    reason="champion_suite_basis_unknown",
                    champion=current,
                    previous_champion=current,
                )
            current_suite_id = current.metadata.get("suite_id")
            if current_suite_id is not None and current_suite_id != evaluation.suite_id:
                return PromotionDecision(
                    loop_id=loop_id,
                    promoted=False,
                    reason="champion_suite_mismatch",
                    champion=current,
                    previous_champion=current,
                )
            if current.suite_version != evaluation.suite_version:
                return PromotionDecision(
                    loop_id=loop_id,
                    promoted=False,
                    reason="champion_suite_version_mismatch",
                    champion=current,
                    previous_champion=current,
                )
            current_suite_ref = current.metadata.get("suite_ref")
            if current_suite_ref is not None and current_suite_ref != str(suite_ref.artifact_id):
                return PromotionDecision(
                    loop_id=loop_id,
                    promoted=False,
                    reason="champion_suite_basis_mismatch",
                    champion=current,
                    previous_champion=current,
                )
        if current is not None:
            if artifact_ref_identity_key(current.candidate_ref) == artifact_ref_identity_key(
                candidate_ref
            ) and artifact_ref_identity_key(current.evaluation_ref) == artifact_ref_identity_key(
                evaluation_ref
            ):
                return PromotionDecision(
                    loop_id=loop_id,
                    promoted=False,
                    reason="already_champion",
                    champion=current,
                    previous_champion=current,
                )

        guardrail_failure = next(
            (
                name
                for name in policy.required_guardrails
                if not bool(evaluation.guardrails.get(name))
            ),
            None,
        )
        if guardrail_failure is not None:
            return PromotionDecision(
                loop_id=loop_id,
                promoted=False,
                reason=f"guardrail_failed:{guardrail_failure}",
                champion=current,
                previous_champion=current,
            )
        if not evaluation.promotable:
            return PromotionDecision(
                loop_id=loop_id,
                promoted=False,
                reason="evaluation_not_promotable",
                champion=current,
                previous_champion=current,
            )

        sample_count = evaluation.sample_count(split=policy.compare_split)
        if sample_count < policy.min_sample_count:
            return PromotionDecision(
                loop_id=loop_id,
                promoted=False,
                reason=f"insufficient_samples:{sample_count}",
                champion=current,
                previous_champion=current,
            )

        new_value = evaluation.primary_value(
            split=policy.compare_split, metric=policy.primary_metric
        )
        if new_value is None:
            return PromotionDecision(
                loop_id=loop_id,
                promoted=False,
                reason=f"missing_primary_metric:{policy.primary_metric}",
                champion=current,
                previous_champion=current,
            )

        current_value = None
        if current is not None:
            if suite_ref is not None:
                incumbent, failure = self._incumbent_comparison(
                    current=current,
                    evaluation=evaluation,
                    policy=policy,
                    suite_ref=suite_ref,
                    evaluation_ref=evaluation_ref,
                )
                if failure:
                    return PromotionDecision(
                        loop_id=loop_id,
                        promoted=False,
                        reason=failure,
                        champion=current,
                        previous_champion=current,
                    )
                assert incumbent is not None
                current_value = incumbent.primary_value(
                    split=policy.compare_split, metric=policy.primary_metric
                )
                if current_value is None:
                    return PromotionDecision(
                        loop_id=loop_id,
                        promoted=False,
                        reason="champion_primary_metric_missing",
                        champion=current,
                        previous_champion=current,
                    )
            else:
                current_value = current.metrics.get(policy.primary_metric)

        if current_value is not None and not self._is_improved(
            current=float(current_value),
            new=float(new_value),
            direction=policy.direction,
            min_improvement=policy.min_improvement,
        ):
            return PromotionDecision(
                loop_id=loop_id,
                promoted=False,
                reason="not_better_than_champion",
                champion=current,
                previous_champion=current,
            )

        pointer = ChampionPointer(
            loop_id=loop_id,
            candidate_ref=candidate_ref,
            evaluation_ref=evaluation_ref,
            metrics=evaluation.metrics_for_split(policy.compare_split),
            suite_version=evaluation.suite_version,
            search_space_version=self._search_space_version(candidate_ref),
            metadata={
                "promoted_by_policy": policy.model_dump(mode="json"),
                "compare_split": policy.compare_split.value,
                **(
                    {
                        "suite_id": evaluation.suite_id,
                        "suite_ref": str(suite_ref.artifact_id),
                    }
                    if suite_ref is not None
                    else {}
                ),
            },
        )
        if loop_id == "claim_adjudication":
            # Record the actual comparator before the pointer transition. A crash
            # between the two atomic writes leaves a mismatch and fails closed.
            payload = pointer.model_dump(mode="json")
            pointer_digest = hashlib.sha256(
                json.dumps(
                    payload,
                    sort_keys=True,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode()
            ).hexdigest()
            basis = {
                "schema_version": "claim-promotion-basis.v1",
                "transition": "successor" if current is not None else "genesis",
                "current_pointer_sha256": pointer_digest,
                "previous_pointer": current.model_dump(mode="json")
                if current is not None
                else None,
            }
            self._write_json(
                self._root / loop_id / "promotion_basis.json",
                json.dumps(basis, sort_keys=True).encode(),
            )
        self._write_pointer(loop_id, pointer)
        return PromotionDecision(
            loop_id=loop_id,
            promoted=True,
            reason="promoted",
            champion=pointer,
            previous_champion=current,
        )

    @contextmanager
    def _promotion_lock(self, loop_id: str) -> Iterator[None]:
        """Serialize one loop's read/compare/publish transition across processes."""
        lock_path = self._root / loop_id / "champion.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+b") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _search_space_version(self, candidate_ref: ArtifactRef) -> str:
        payload = load_json_artifact(self._store, candidate_ref)
        if isinstance(payload, dict):
            value = payload.get("search_space_version")
            if isinstance(value, str) and value:
                return value
        try:
            artifact = MutationArtifact.model_validate(payload)
        except Exception:
            return "1.0"
        return artifact.search_space_version

    @staticmethod
    def _is_improved(
        *,
        current: float,
        new: float,
        direction: MetricDirection,
        min_improvement: float,
    ) -> bool:
        return metric_is_improved(
            current=current, new=new, direction=direction.value, min_improvement=min_improvement
        )

    def _pointer_path(self, loop_id: str) -> Path:
        return self._root / loop_id / "champion.json"

    def write_pointer(self, loop_id: str, pointer: ChampionPointer) -> None:
        """Attach metadata to the current admitted pointer without replacing its comparison."""
        if loop_id == "claim_adjudication":
            raise ValueError("claim_adjudication_manual_pointer_transition_unverified")
        with self._promotion_lock(loop_id):
            current = self.get(loop_id)
            if current is None or pointer.model_dump(exclude={"metadata"}) != current.model_dump(
                exclude={"metadata"}
            ):
                raise ValueError("champion_pointer_transition_requires_comparison")
            if any(
                key in pointer.metadata and pointer.metadata[key] != value
                for key, value in current.metadata.items()
            ):
                raise ValueError("champion_metadata_conflict")
            updated = current.model_copy(
                update={"metadata": {**current.metadata, **pointer.metadata}}
            )
            self._write_pointer(loop_id, updated)

    def _write_pointer(self, loop_id: str, pointer: ChampionPointer) -> None:
        path = self._pointer_path(loop_id)
        payload = pointer.model_dump_json(indent=2, exclude_none=True).encode("utf-8")
        self._write_json(path, payload)

    @staticmethod
    def _write_json(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            mode="wb",
            delete=False,
            dir=str(path.parent),
            prefix=".champion.",
            suffix=".tmp",
        ) as tmp:
            tmp.write(payload)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
