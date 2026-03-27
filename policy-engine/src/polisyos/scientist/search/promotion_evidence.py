"""Promotion-evidence bundle for blueprint-native Level 6 promotion."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.scientist.autotune.models import BenchmarkEvaluation, BenchmarkSplit
from polisyos.scientist.replay.verification import load_replay_verification_report
from polisyos.scientist.search.adversarial import load_platform_meta_evaluation_report

PROMOTION_EVIDENCE_BUNDLE_SCHEMA_NAME = (
    "polisyos.scientist.search.PromotionEvidenceBundle"
)


class PromotionEvidenceBundle(BaseModel):
    """Canonical promotion evidence required by Level 6."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    run_id: str = Field(min_length=1)
    produced_by_run_id: str = Field(min_length=1)
    candidate_ref: ArtifactRef
    evaluation_ref: ArtifactRef | None = None
    selection_evaluation_ref: ArtifactRef | None = None
    hidden_holdout_evaluation_ref: ArtifactRef | None = None
    rotating_challenge_evaluation_refs: list[ArtifactRef] = Field(default_factory=list)
    adversarial_meta_evaluation_ref: ArtifactRef | None = None
    replay_bundle_ref: ArtifactRef | None = None
    replay_verification_ref: ArtifactRef | None = None
    calibration_report_ref: ArtifactRef | None = None
    governance_report_ref: ArtifactRef | None = None
    stress_test_report_ref: ArtifactRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def missing_required_refs(
        self,
        *,
        require_hidden_holdout: bool = True,
        require_replay_bundle: bool = True,
        require_replay_verification: bool = False,
        require_governance: bool = True,
        require_calibration: bool = False,
    ) -> list[str]:
        missing: list[str] = []
        if self.selection_evaluation_ref is None:
            missing.append("selection_evaluation_ref")
        if require_hidden_holdout and self.hidden_holdout_evaluation_ref is None:
            missing.append("hidden_holdout_evaluation_ref")
        if self.adversarial_meta_evaluation_ref is None:
            missing.append("adversarial_meta_evaluation_ref")
        if require_replay_bundle and self.replay_bundle_ref is None:
            missing.append("replay_bundle_ref")
        if require_replay_verification and self.replay_verification_ref is None:
            missing.append("replay_verification_ref")
        if require_governance and self.governance_report_ref is None:
            missing.append("governance_report_ref")
        if require_calibration and self.calibration_report_ref is None:
            missing.append("calibration_report_ref")
        return missing

    def assert_compatible_with_run(self, run_id: str) -> None:
        if self.run_id != run_id or self.produced_by_run_id != run_id:
            raise ValueError(
                "PromotionEvidenceBundle must be produced by and pinned to the current run."
            )

    def assert_runtime_compatible(
        self,
        *,
        run_id: str,
        store: FileSystemCAS,
        expected_loop_id: str | None = None,
        expected_refs: Mapping[str, ArtifactRef | list[ArtifactRef] | None] | None = None,
    ) -> None:
        self.assert_compatible_with_run(run_id)
        if expected_refs:
            _assert_expected_refs(self, expected_refs)
        _require_manifest(store, self.candidate_ref, role="candidate_ref")
        if self.evaluation_ref is not None:
            manifest = _require_manifest(store, self.evaluation_ref, role="evaluation_ref")
            if manifest.kind != "scientist.policy_evaluation_vector":
                raise ValueError("PromotionEvidenceBundle evaluation_ref must be a policy evaluation vector.")
            if not any(
                item.artifact_id == self.candidate_ref.artifact_id and item.role == "candidate"
                for item in manifest.inputs
            ):
                raise ValueError(
                    "PromotionEvidenceBundle evaluation_ref is stale or detached from the current candidate."
                )
        if self.selection_evaluation_ref is not None:
            _validate_benchmark_ref(
                store,
                self.selection_evaluation_ref,
                role="selection_evaluation_ref",
                candidate_ref=self.candidate_ref,
                expected_loop_id=expected_loop_id,
                expected_split=BenchmarkSplit.SELECTION,
            )
        if self.hidden_holdout_evaluation_ref is not None:
            _validate_benchmark_ref(
                store,
                self.hidden_holdout_evaluation_ref,
                role="hidden_holdout_evaluation_ref",
                candidate_ref=self.candidate_ref,
                expected_loop_id=expected_loop_id,
                expected_split=BenchmarkSplit.HIDDEN_HOLDOUT,
            )
        for ref in self.rotating_challenge_evaluation_refs:
            _validate_benchmark_ref(
                store,
                ref,
                role="rotating_challenge_evaluation_refs",
                candidate_ref=self.candidate_ref,
                expected_loop_id=expected_loop_id,
                expected_split=BenchmarkSplit.ROTATING_CHALLENGE,
            )
        if self.adversarial_meta_evaluation_ref is not None:
            manifest = _require_manifest(
                store,
                self.adversarial_meta_evaluation_ref,
                role="adversarial_meta_evaluation_ref",
            )
            if manifest.kind != "scientist.platform_meta_evaluation_report":
                raise ValueError(
                    "PromotionEvidenceBundle adversarial_meta_evaluation_ref has unexpected kind."
                )
            report = load_platform_meta_evaluation_report(store, self.adversarial_meta_evaluation_ref)
            source_selection = report.source_refs.get("selection_evaluation_ref")
            if self.selection_evaluation_ref is not None and source_selection != self.selection_evaluation_ref:
                raise ValueError(
                    "PromotionEvidenceBundle adversarial_meta_evaluation_ref is stale for the current selection evidence."
                )
            report_run_id = str(report.metadata.get("run_id") or "").strip()
            if report_run_id and report_run_id != run_id:
                raise ValueError(
                    "PromotionEvidenceBundle adversarial_meta_evaluation_ref belongs to another run."
                )
        if self.replay_bundle_ref is not None:
            manifest = _require_manifest(store, self.replay_bundle_ref, role="replay_bundle_ref")
            if manifest.kind != "scientist.replayable_audit_bundle":
                raise ValueError(
                    "PromotionEvidenceBundle replay_bundle_ref must point to a replayable audit bundle."
                )
        if self.replay_verification_ref is not None:
            manifest = _require_manifest(
                store,
                self.replay_verification_ref,
                role="replay_verification_ref",
            )
            if manifest.kind != "scientist.replay_verification_report":
                raise ValueError(
                    "PromotionEvidenceBundle replay_verification_ref has unexpected kind."
                )
            report = load_replay_verification_report(store, self.replay_verification_ref)
            if (
                self.replay_bundle_ref is not None
                and report.replay_bundle_ref.artifact_id != self.replay_bundle_ref.artifact_id
            ):
                raise ValueError(
                    "PromotionEvidenceBundle replay_verification_ref is stale for the current replay bundle."
                )
            report_run_id = str(report.run_id).strip()
            if report_run_id and report_run_id != run_id:
                raise ValueError(
                    "PromotionEvidenceBundle replay_verification_ref belongs to another run."
                )
        if self.calibration_report_ref is not None:
            manifest = _require_manifest(store, self.calibration_report_ref, role="calibration_report_ref")
            if manifest.kind != "scientist.search.calibration_report":
                raise ValueError(
                    "PromotionEvidenceBundle calibration_report_ref has unexpected kind."
                )
        if self.governance_report_ref is not None:
            _require_manifest(store, self.governance_report_ref, role="governance_report_ref")
        if self.stress_test_report_ref is not None:
            manifest = _require_manifest(store, self.stress_test_report_ref, role="stress_test_report_ref")
            if manifest.kind != "scientist.stress_test_report":
                raise ValueError(
                    "PromotionEvidenceBundle stress_test_report_ref has unexpected kind."
                )


def _assert_expected_refs(
    bundle: PromotionEvidenceBundle,
    expected_refs: Mapping[str, ArtifactRef | list[ArtifactRef] | None],
) -> None:
    for key, expected in expected_refs.items():
        if not hasattr(bundle, key):
            continue
        actual = getattr(bundle, key)
        if expected is None or actual is None:
            continue
        if isinstance(expected, list):
            if list(actual) != expected:
                raise ValueError(f"PromotionEvidenceBundle {key} is stale for the current run snapshot.")
            continue
        if actual != expected:
            raise ValueError(f"PromotionEvidenceBundle {key} is stale for the current run snapshot.")


def _require_manifest(
    store: FileSystemCAS,
    ref: ArtifactRef,
    *,
    role: str,
):
    try:
        return store.get_manifest(ref.artifact_id)
    except FileNotFoundError as exc:  # pragma: no cover - defensive runtime error path
        raise ValueError(f"PromotionEvidenceBundle {role} is missing from CAS.") from exc


def _validate_benchmark_ref(
    store: FileSystemCAS,
    ref: ArtifactRef,
    *,
    role: str,
    candidate_ref: ArtifactRef,
    expected_loop_id: str | None,
    expected_split: BenchmarkSplit,
) -> None:
    manifest = _require_manifest(store, ref, role=role)
    if not (
        manifest.kind == "scientist.benchmark_evaluation"
        or manifest.kind.endswith(".evaluation")
        or (
            manifest.artifact_schema is not None
            and manifest.artifact_schema.name
            == "polisyos.scientist.autotune.BenchmarkEvaluation"
        )
    ):
        raise ValueError(f"PromotionEvidenceBundle {role} has unexpected kind.")
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    evaluation = BenchmarkEvaluation.model_validate(payload)
    if evaluation.candidate_ref != candidate_ref:
        raise ValueError(f"PromotionEvidenceBundle {role} belongs to another candidate.")
    if expected_loop_id is not None and evaluation.loop_id != expected_loop_id:
        raise ValueError(f"PromotionEvidenceBundle {role} belongs to another loop.")
    if evaluation.resolved_runtime_split_type() is not expected_split:
        raise ValueError(f"PromotionEvidenceBundle {role} has unexpected benchmark split.")


def persist_promotion_evidence_bundle(
    store: FileSystemCAS,
    bundle: PromotionEvidenceBundle,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    return store.put_json(
        bundle,
        PutOptions(
            kind="scientist.promotion_evidence_bundle",
            media_type="application/json",
            schema=SchemaInfo(
                name=PROMOTION_EVIDENCE_BUNDLE_SCHEMA_NAME,
                version=bundle.schema_version,
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_promotion_evidence_bundle(
    store: FileSystemCAS,
    ref: ArtifactRef,
) -> PromotionEvidenceBundle:
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return PromotionEvidenceBundle.model_validate(payload)


__all__ = [
    "PROMOTION_EVIDENCE_BUNDLE_SCHEMA_NAME",
    "PromotionEvidenceBundle",
    "load_promotion_evidence_bundle",
    "persist_promotion_evidence_bundle",
]
