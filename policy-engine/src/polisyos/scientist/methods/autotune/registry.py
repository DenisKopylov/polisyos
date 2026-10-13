"""Public autotune registry module API."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.data_forge.read_api import academic

from .models import (
    BenchmarkEvaluation,
    BenchmarkSuite,
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
        document = json.loads(path.read_text(encoding="utf-8"))
        if (
            loop_id == "claim_adjudication"
            and isinstance(document, dict)
            and document.get("schema_version") == "claim-champion-envelope.v1"
        ):
            pointer_data = document.get("pointer")
            if not isinstance(pointer_data, dict):
                raise ValueError("claim_adjudication_champion_envelope_pointer_invalid")
            pointer = ChampionPointer.model_validate(pointer_data)
            read_claim_promotion_predecessor(
                self._root, pointer.model_dump(mode="json", exclude_none=True)
            )
            return pointer
        return ChampionPointer.model_validate(document)

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
        if loop_id == "claim_adjudication":
            missing = next(
                (
                    name
                    for name, ref in (
                        ("candidate", candidate_ref),
                        ("evaluation", evaluation_ref),
                        ("benchmark_suite", suite_ref),
                    )
                    if ref is None or ref.manifest_profile_sha256 is None
                ),
                None,
            )
            if missing is not None:
                current = self.get(loop_id)
                return PromotionDecision(
                    loop_id=loop_id,
                    promoted=False,
                    reason=f"claim_adjudication_selected_profile_required:{missing}",
                    champion=current,
                    previous_champion=current,
                )
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
        if loop_id == "claim_adjudication" and any(
            ref is None or ref.manifest_profile_sha256 is None
            for ref in (candidate_ref, evaluation_ref, suite_ref)
        ):
            return "claim_adjudication_selected_profile_required"
        if evaluation.loop_id != loop_id:
            return "evaluation_loop_mismatch"
        if artifact_ref_identity_key(evaluation.candidate_ref) != artifact_ref_identity_key(
            candidate_ref
        ):
            return "evaluation_candidate_mismatch"
        if suite_ref is None:
            return "suite_ref_required"

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
        expected_suite_input = input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")
        candidate_manifest = self._store.get_manifest(candidate_ref)
        evaluation_manifest = self._store.get_manifest(evaluation_ref)
        for manifest in (candidate_manifest, evaluation_manifest):
            suite_inputs = [item for item in manifest.inputs if item.role == "benchmark_suite"]
            if len(suite_inputs) != 1 or suite_inputs[0] != expected_suite_input:
                return "suite_basis_mismatch"
        candidate_inputs = [item for item in evaluation_manifest.inputs if item.role == "candidate"]
        expected_candidate_input = input_ref_from_artifact_ref(candidate_ref, role="candidate")
        if len(candidate_inputs) != 1 or candidate_inputs[0] != expected_candidate_input:
            return "evaluation_candidate_basis_mismatch"
        return None

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
        if current is not None and suite_ref is not None:
            current_suite_id = current.metadata.get("suite_id")
            current_suite_ref = current.metadata.get("suite_ref")
            if current_suite_id is None or current_suite_ref is None:
                return PromotionDecision(
                    loop_id=loop_id,
                    promoted=False,
                    reason="champion_suite_basis_unknown",
                    champion=current,
                    previous_champion=current,
                )
            if current_suite_id != evaluation.suite_id:
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
            if not isinstance(current_suite_ref, dict):
                return PromotionDecision(
                    loop_id=loop_id,
                    promoted=False,
                    reason="champion_suite_basis_unknown",
                    champion=current,
                    previous_champion=current,
                )
            try:
                selected_current_suite_ref = ArtifactRef.model_validate(current_suite_ref)
            except ValueError:
                return PromotionDecision(
                    loop_id=loop_id,
                    promoted=False,
                    reason="champion_suite_basis_unknown",
                    champion=current,
                    previous_champion=current,
                )
            if artifact_ref_identity_key(selected_current_suite_ref) != artifact_ref_identity_key(
                suite_ref
            ):
                return PromotionDecision(
                    loop_id=loop_id,
                    promoted=False,
                    reason="champion_suite_basis_mismatch",
                    champion=current,
                    previous_champion=current,
                )
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
                **(
                    {
                        "suite_id": evaluation.suite_id,
                        "suite_ref": suite_ref.model_dump(mode="json"),
                    }
                    if suite_ref is not None
                    else {}
                ),
            },
        )
        if loop_id == "claim_adjudication":
            pointer_payload = pointer.model_dump(mode="json", exclude_none=True)
            pointer_digest = hashlib.sha256(
                json.dumps(
                    pointer_payload,
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
                "previous_pointer": current.model_dump(mode="json", exclude_none=True)
                if current is not None
                else None,
            }
            envelope = {
                "schema_version": "claim-champion-envelope.v1",
                "pointer": pointer_payload,
                "promotion_basis": basis,
            }
            envelope_bytes = json.dumps(
                envelope, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
            self._write_json(self._pointer_path(loop_id), envelope_bytes)
        else:
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
        if loop_id == "claim_adjudication":
            raise ValueError("claim_adjudication_manual_pointer_transition_unverified")
        with self._promotion_lock(loop_id):
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
