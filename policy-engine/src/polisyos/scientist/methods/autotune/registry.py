"""Public autotune registry module API."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.data_forge.read_api import academic

from .models import (
    BenchmarkEvaluation,
    ChampionPointer,
    MetricDirection,
    MutationArtifact,
    PromotionDecision,
    PromotionPolicy,
    default_search_registry_root,
    load_json_artifact,
    load_model_artifact,
)

claim_promotion_policy = academic.claim_promotion_policy
metric_is_improved = academic.metric_is_improved
read_claim_promotion_predecessor = academic.read_claim_promotion_predecessor


class ChampionRegistry:
    """Atomic registry of active autotune champions."""

    def __init__(
        self,
        root: Path | None = None,
        *,
        store: FileSystemCAS,
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
        pareto_promoter: Any | None = None,
    ) -> PromotionDecision:
        evaluation = load_model_artifact(self._store, evaluation_ref, BenchmarkEvaluation)
        if not isinstance(evaluation, BenchmarkEvaluation):
            raise TypeError("Expected BenchmarkEvaluation")
        current = self.get(loop_id)
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
        if current is not None:
            if (
                current.candidate_ref.artifact_id == candidate_ref.artifact_id
                and current.evaluation_ref.artifact_id == evaluation_ref.artifact_id
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
        if loop_id == "claim_adjudication":
            raise ValueError("claim_adjudication_manual_pointer_transition_unverified")
        self._write_pointer(loop_id, pointer)

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
