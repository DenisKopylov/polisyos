"""Promotion-evidence bundle for blueprint-native Level 6 promotion."""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import (
    ArtifactManifest,
    ArtifactRef,
    InputRef,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.methods.autotune.models import (
    _BENCHMARK_EVALUATION_SCHEMA_NAME,
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSuite,
    PromotionPolicy,
    load_json_artifact,
    load_model_artifact,
)
from polisyos.scientist.methods.search.adversarial import load_platform_meta_evaluation_report
from polisyos.scientist.replay.verification import load_replay_verification_report

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactStore, CoreJSONArtifactStore

PROMOTION_EVIDENCE_BUNDLE_SCHEMA_NAME = "polisyos.scientist.search.PromotionEvidenceBundle"


class _PolicyRuntimeSelectionSourceBasis(BaseModel):
    """Current policy-runtime selection projection recomputed by its orchestration caller."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_kind: Literal["policy_runtime_selection"] = "policy_runtime_selection"
    expected_evaluation: BenchmarkEvaluation


class _MethodJobPromotionSourceBasis(BaseModel):
    """Trusted call context needed to reconcile one MethodJob result for promotion input."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_kind: Literal["method_job"] = "method_job"
    expected_run_id: str = Field(min_length=1)
    expected_candidate_ref: ArtifactRef
    expected_suite_ref: ArtifactRef
    expected_policy: PromotionPolicy


class _PhaseD4ChallengeSourceBasis(BaseModel):
    """Recomputed D4 source report that binds rotating evaluations to measured outcomes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_kind: Literal["phase_d4_challenge"] = "phase_d4_challenge"
    stress_report_ref: ArtifactRef


_BenchmarkEvaluationSourceBasis = (
    _PolicyRuntimeSelectionSourceBasis
    | _MethodJobPromotionSourceBasis
    | _PhaseD4ChallengeSourceBasis
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
        store: CoreJSONArtifactStore,
        expected_loop_id: str | None = None,
        expected_refs: Mapping[str, ArtifactRef | list[ArtifactRef] | None] | None = None,
        source_basis_by_role: Mapping[str, _BenchmarkEvaluationSourceBasis] | None = None,
    ) -> None:
        self.assert_compatible_with_run(run_id)
        if expected_refs:
            _assert_expected_refs(self, expected_refs)
        _require_manifest(store, self.candidate_ref, role="candidate_ref")
        if self.evaluation_ref is not None:
            manifest = _require_manifest(store, self.evaluation_ref, role="evaluation_ref")
            if manifest.kind != "scientist.policy_evaluation_vector":
                raise ValueError(
                    "PromotionEvidenceBundle evaluation_ref must be a policy evaluation vector."
                )
            _assert_exact_evaluation_inputs(
                store,
                ref=self.evaluation_ref,
                expected={"candidate": self.candidate_ref},
                role="evaluation_ref",
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
            _validate_benchmark_source_basis(
                store,
                role="selection_evaluation_ref",
                refs=(self.selection_evaluation_ref,),
                source_basis=(source_basis_by_role or {}).get("selection_evaluation_ref"),
                run_id=run_id,
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
            _validate_benchmark_source_basis(
                store,
                role="hidden_holdout_evaluation_ref",
                refs=(self.hidden_holdout_evaluation_ref,),
                source_basis=(source_basis_by_role or {}).get("hidden_holdout_evaluation_ref"),
                run_id=run_id,
                candidate_ref=self.candidate_ref,
                expected_loop_id=expected_loop_id,
                expected_split=BenchmarkSplit.HIDDEN_HOLDOUT,
            )
        if self.rotating_challenge_evaluation_refs:
            _validate_benchmark_ref(
                store,
                self.rotating_challenge_evaluation_refs[0],
                role="rotating_challenge_evaluation_refs",
                candidate_ref=self.candidate_ref,
                expected_loop_id=expected_loop_id,
                expected_split=BenchmarkSplit.ROTATING_CHALLENGE,
            )
            for ref in self.rotating_challenge_evaluation_refs[1:]:
                _validate_benchmark_ref(
                    store,
                    ref,
                    role="rotating_challenge_evaluation_refs",
                    candidate_ref=self.candidate_ref,
                    expected_loop_id=expected_loop_id,
                    expected_split=BenchmarkSplit.ROTATING_CHALLENGE,
                )
            _validate_benchmark_source_basis(
                store,
                role="rotating_challenge_evaluation_refs",
                refs=tuple(self.rotating_challenge_evaluation_refs),
                source_basis=(source_basis_by_role or {}).get("rotating_challenge_evaluation_refs"),
                run_id=run_id,
                candidate_ref=self.candidate_ref,
                expected_loop_id=expected_loop_id,
                expected_split=BenchmarkSplit.ROTATING_CHALLENGE,
                stress_report_ref=self.stress_test_report_ref,
            )
        present_benchmark_roles = {
            role
            for role, present in (
                ("selection_evaluation_ref", self.selection_evaluation_ref is not None),
                ("hidden_holdout_evaluation_ref", self.hidden_holdout_evaluation_ref is not None),
                (
                    "rotating_challenge_evaluation_refs",
                    bool(self.rotating_challenge_evaluation_refs),
                ),
            )
            if present
        }
        supplied_benchmark_roles = set(source_basis_by_role or {})
        if supplied_benchmark_roles != present_benchmark_roles:
            raise ValueError(
                "PromotionEvidenceBundle benchmark source basis does not match its protected roles."
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
            report = load_platform_meta_evaluation_report(
                store, self.adversarial_meta_evaluation_ref
            )
            source_selection = report.source_refs.get("selection_evaluation_ref")
            if (
                self.selection_evaluation_ref is not None
                and source_selection != self.selection_evaluation_ref
            ):
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
            if self.replay_bundle_ref is None:
                raise ValueError(
                    "PromotionEvidenceBundle replay_verification_ref requires replay_bundle_ref context."
                )
            load_replay_verification_report(
                store,
                self.replay_verification_ref,
                expected_run_id=run_id,
                expected_replay_bundle_ref=self.replay_bundle_ref,
                expected_candidate_ref=self.candidate_ref,
                expected_evaluation_ref=self.evaluation_ref,
            )
        if self.calibration_report_ref is not None:
            manifest = _require_manifest(
                store, self.calibration_report_ref, role="calibration_report_ref"
            )
            if manifest.kind != "scientist.search.calibration_report":
                raise ValueError(
                    "PromotionEvidenceBundle calibration_report_ref has unexpected kind."
                )
        if self.governance_report_ref is not None:
            _require_manifest(store, self.governance_report_ref, role="governance_report_ref")
        if self.stress_test_report_ref is not None:
            manifest = _require_manifest(
                store, self.stress_test_report_ref, role="stress_test_report_ref"
            )
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
                raise ValueError(
                    f"PromotionEvidenceBundle {key} is stale for the current run snapshot."
                )
            continue
        if actual != expected:
            raise ValueError(
                f"PromotionEvidenceBundle {key} is stale for the current run snapshot."
            )


def _require_manifest(
    store: CoreJSONArtifactStore,
    ref: ArtifactRef,
    *,
    role: str,
) -> ArtifactManifest:
    if ref.manifest_profile_sha256 is None:
        raise ValueError(f"PromotionEvidenceBundle {role} requires a selected manifest profile.")
    from polisyos.core.artifacts import read_core_manifest_profile

    try:
        manifest, _declaration = read_core_manifest_profile(
            store,
            ref,
            manifest_profile_sha256=ref.manifest_profile_sha256,
        )
        return manifest
    except FileNotFoundError as exc:  # pragma: no cover - defensive runtime error path
        raise ValueError(f"PromotionEvidenceBundle {role} is missing from CAS.") from exc


def _validate_benchmark_ref(
    store: CoreJSONArtifactStore,
    ref: ArtifactRef,
    *,
    role: str,
    candidate_ref: ArtifactRef,
    expected_loop_id: str | None,
    expected_split: BenchmarkSplit,
) -> None:
    from polisyos.core.artifacts import load_core_json_artifact

    manifest = _require_manifest(store, ref, role=role)
    if not (
        manifest.kind == "scientist.benchmark_evaluation"
        or manifest.kind.endswith(".evaluation")
        or (
            manifest.artifact_schema is not None
            and manifest.artifact_schema.name
            == "polisyos.scientist.methods.autotune.BenchmarkEvaluation"
        )
    ):
        raise ValueError(f"PromotionEvidenceBundle {role} has unexpected kind.")
    payload = load_core_json_artifact(store, ref)
    evaluation = BenchmarkEvaluation.model_validate(payload)
    if (
        ref.kind != manifest.kind
        or ref.media_type != manifest.media_type
        or manifest.kind != f"scientist.autotune.{evaluation.loop_id}.evaluation"
        or manifest.media_type != "application/json"
        or manifest.artifact_schema is None
        or manifest.artifact_schema.name != _BENCHMARK_EVALUATION_SCHEMA_NAME
        or manifest.artifact_schema.version != evaluation.suite_version
        or manifest.producer is None
        or manifest.producer.component != "polisyos.scientist.methods.autotune.benchmark_evaluator"
        or manifest.producer.version not in {"1.0", "2.0"}
    ):
        raise ValueError(f"PromotionEvidenceBundle {role} has unsupported benchmark source ABI.")
    if evaluation.candidate_ref != candidate_ref:
        raise ValueError(f"PromotionEvidenceBundle {role} belongs to another candidate.")
    if expected_loop_id is not None and evaluation.loop_id != expected_loop_id:
        raise ValueError(f"PromotionEvidenceBundle {role} belongs to another loop.")
    if evaluation.resolved_runtime_split_type() is not expected_split:
        raise ValueError(f"PromotionEvidenceBundle {role} has unexpected benchmark split.")


def _validate_benchmark_source_basis(
    store: CoreJSONArtifactStore,
    *,
    role: str,
    refs: tuple[ArtifactRef, ...],
    source_basis: _BenchmarkEvaluationSourceBasis | None,
    run_id: str,
    candidate_ref: ArtifactRef,
    expected_loop_id: str | None,
    expected_split: BenchmarkSplit,
    stress_report_ref: ArtifactRef | None = None,
) -> None:
    if source_basis is None:
        raise ValueError(f"PromotionEvidenceBundle {role} source basis is required.")
    if isinstance(source_basis, _PolicyRuntimeSelectionSourceBasis):
        if role != "selection_evaluation_ref" or len(refs) != 1:
            raise ValueError(f"PromotionEvidenceBundle {role} has an incompatible source basis.")
        if source_basis.expected_evaluation.candidate_ref != candidate_ref:
            raise ValueError(f"PromotionEvidenceBundle {role} source basis has another candidate.")
        if (
            expected_loop_id is not None
            and source_basis.expected_evaluation.loop_id != expected_loop_id
        ):
            raise ValueError(
                f"PromotionEvidenceBundle {role} source basis belongs to another loop."
            )
        _validate_policy_runtime_selection_projection(
            store,
            ref=refs[0],
            expected=source_basis.expected_evaluation,
            role=role,
        )
        return
    if isinstance(source_basis, _MethodJobPromotionSourceBasis):
        if len(refs) != 1:
            raise ValueError(f"PromotionEvidenceBundle {role} requires one MethodJob source basis.")
        if (
            source_basis.expected_run_id != run_id
            or source_basis.expected_candidate_ref != candidate_ref
            or source_basis.expected_policy.loop_id != expected_loop_id
            or source_basis.expected_policy.compare_split is not expected_split
        ):
            raise ValueError(f"PromotionEvidenceBundle {role} MethodJob source basis is stale.")
        _validate_method_job_benchmark_ref(
            store,
            ref=refs[0],
            role=role,
            basis=source_basis,
        )
        return
    if isinstance(source_basis, _PhaseD4ChallengeSourceBasis):
        if (
            role != "rotating_challenge_evaluation_refs"
            or expected_split is not BenchmarkSplit.ROTATING_CHALLENGE
            or stress_report_ref is None
            or source_basis.stress_report_ref != stress_report_ref
            or not refs
            or len({ref.model_dump_json() for ref in refs}) != len(refs)
        ):
            raise ValueError(f"PromotionEvidenceBundle {role} has no current D4 source report.")
        _validate_phase_d4_benchmark_source(
            store,
            refs=refs,
            stress_report_ref=stress_report_ref,
            candidate_ref=candidate_ref,
        )
        return
    raise ValueError(f"PromotionEvidenceBundle {role} has an unsupported source basis.")


def _validate_phase_d4_benchmark_source(
    store: CoreJSONArtifactStore,
    *,
    refs: tuple[ArtifactRef, ...],
    stress_report_ref: ArtifactRef,
    candidate_ref: ArtifactRef,
) -> None:
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.scientist.methods.doe.stress_report import (
        StressOutcomeBasis,
        resolve_stress_report_artifact,
    )

    report, resolution = resolve_stress_report_artifact(
        store,
        stress_report_ref,
        expected_candidate_ref=candidate_ref,
    )
    if resolution.status != "available" or resolution.predicate_status != "recomputed":
        raise ValueError("PromotionEvidenceBundle rotating challenge source was not recomputed.")

    d4_refs: list[ArtifactRef] = []
    for component in report.score_components:
        if not component.component_id.startswith("phase_d4:"):
            continue
        basis = StressOutcomeBasis.model_validate(
            load_core_json_artifact(store, component.outcome_basis_ref)
        )
        if basis.source_kind != "phase_d4_suite":
            raise ValueError("PromotionEvidenceBundle D4 component has another source kind.")
        if (
            basis.candidate_ref != candidate_ref
            or basis.benchmark_evaluation_ref is None
            or basis.suite_id is None
            or basis.suite_version is None
        ):
            raise ValueError("PromotionEvidenceBundle D4 outcome basis is incomplete.")
        d4_refs.append(basis.benchmark_evaluation_ref)

    source_keys = [ref.model_dump_json() for ref in d4_refs]
    expected_keys = [ref.model_dump_json() for ref in refs]
    if (
        not d4_refs
        or len(source_keys) != len(set(source_keys))
        or len(expected_keys) != len(set(expected_keys))
        or set(source_keys) != set(expected_keys)
    ):
        raise ValueError(
            "PromotionEvidenceBundle rotating evaluations differ from recomputed D4 sources."
        )


def _validate_policy_runtime_selection_projection(
    store: CoreJSONArtifactStore,
    *,
    ref: ArtifactRef,
    expected: BenchmarkEvaluation,
    role: str,
) -> None:
    from polisyos.core.artifacts import load_core_json_artifact

    actual = BenchmarkEvaluation.model_validate(load_core_json_artifact(store, ref))
    if (
        expected.suite_id != "policy_selection"
        or expected.resolved_runtime_split_type() is not BenchmarkSplit.SELECTION
        or actual.loop_id != expected.loop_id
        or actual.suite_id != expected.suite_id
        or actual.suite_version != expected.suite_version
        or actual.candidate_ref != expected.candidate_ref
        or actual.selection_metrics != expected.selection_metrics
        or actual.holdout_metrics != expected.holdout_metrics
        or actual.sample_counts != expected.sample_counts
        or actual.guardrails != expected.guardrails
        or actual.promotable != expected.promotable
        or actual.status != expected.status
        or actual.resolved_runtime_split_type() is not expected.resolved_runtime_split_type()
        or actual.method_result_ref is not None
        or actual.method_evidence_ref is not None
        or actual.method_job_key is not None
        or actual.execution_work_packet_ref is not None
        or actual.search_source_profile is not None
    ):
        raise ValueError(f"PromotionEvidenceBundle {role} differs from current policy evaluation.")
    _assert_exact_evaluation_inputs(
        store,
        ref=ref,
        expected={"candidate": expected.candidate_ref},
        role=role,
    )


def _validate_method_job_benchmark_ref(
    store: CoreJSONArtifactStore,
    *,
    ref: ArtifactRef,
    role: str,
    basis: _MethodJobPromotionSourceBasis,
) -> None:
    selected_owner_refs = {
        "candidate": basis.expected_candidate_ref,
        "benchmark_suite": basis.expected_suite_ref,
        "benchmark_evaluation": ref,
    }
    if any(
        source_ref.manifest_profile_sha256 is None for source_ref in selected_owner_refs.values()
    ):
        missing = sorted(
            source_role
            for source_role, source_ref in selected_owner_refs.items()
            if source_ref.manifest_profile_sha256 is None
        )
        raise ValueError(
            f"PromotionEvidenceBundle {role} MethodJob source refs require selected manifest "
            f"profiles: {', '.join(missing)}."
        )

    from polisyos.scientist.methods.autotune.runtime import (
        read_method_job_execution_work_packet,
    )

    evaluation = BenchmarkEvaluation.model_validate(load_json_artifact(store, ref))
    if (
        evaluation.candidate_ref != basis.expected_candidate_ref
        or evaluation.loop_id != basis.expected_policy.loop_id
        or evaluation.suite_id == ""
        or evaluation.execution_work_packet_status != "available"
        or evaluation.execution_work_packet_ref is None
        or evaluation.method_result_ref is None
        or evaluation.method_evidence_ref is None
        or evaluation.method_job_key is None
    ):
        raise ValueError(f"PromotionEvidenceBundle {role} MethodJob evidence is unavailable.")
    suite_manifest = store.get_manifest(basis.expected_suite_ref)
    if (
        basis.expected_suite_ref.kind != suite_manifest.kind
        or suite_manifest.kind != "scientist.autotune.method_job.suite"
        or suite_manifest.media_type != "application/json"
        or suite_manifest.artifact_schema is None
        or suite_manifest.artifact_schema.name
        != "polisyos.scientist.methods.autotune.BenchmarkSuite"
    ):
        raise ValueError(f"PromotionEvidenceBundle {role} MethodJob suite is unavailable.")
    suite = load_model_artifact(store, basis.expected_suite_ref, BenchmarkSuite)
    if (
        not isinstance(suite, BenchmarkSuite)
        or suite.suite_id != evaluation.suite_id
        or suite.suite_version != evaluation.suite_version
    ):
        raise ValueError(f"PromotionEvidenceBundle {role} MethodJob suite differs from evaluation.")

    packet = read_method_job_execution_work_packet(store, evaluation.execution_work_packet_ref)
    if (
        packet.run_id != basis.expected_run_id
        or packet.candidate_ref != basis.expected_candidate_ref
        or packet.benchmark_suite_ref != basis.expected_suite_ref
        or packet.method_result_ref != evaluation.method_result_ref
        or packet.method_evidence_ref != evaluation.method_evidence_ref
        or packet.method_job_key != evaluation.method_job_key
        or packet.method_fqn != evaluation.metadata.get("method_fqn")
        or packet.method_version != evaluation.metadata.get("method_version")
        or packet.method_seed != evaluation.metadata.get("method_seed")
        or evaluation.execution_work_packet_note is not None
    ):
        raise ValueError(f"PromotionEvidenceBundle {role} MethodJob source binding is stale.")

    _assert_exact_evaluation_inputs(
        store,
        ref=ref,
        expected={
            "candidate": basis.expected_candidate_ref,
            "benchmark_suite": basis.expected_suite_ref,
            "method_result": packet.method_result_ref,
            "method_evidence": packet.method_evidence_ref,
            "execution_work_packet": evaluation.execution_work_packet_ref,
        },
        role=role,
        optional_basis_ref=evaluation.metadata.get("search_gp_fit_basis_ref"),
    )
    _assert_method_job_evaluation_matches_source(
        store,
        evaluation=evaluation,
        packet=packet,
        basis=basis,
        role=role,
    )


def _assert_method_job_evaluation_matches_source(
    store: CoreJSONArtifactStore,
    *,
    evaluation: BenchmarkEvaluation,
    packet: Any,
    basis: _MethodJobPromotionSourceBasis,
    role: str,
) -> None:
    method_output = load_json_artifact(store, packet.method_result_ref)
    if not isinstance(method_output, Mapping):
        raise ValueError(f"PromotionEvidenceBundle {role} MethodJob result is unavailable.")
    raw_result = method_output.get("result")
    metric_source = raw_result if isinstance(raw_result, Mapping) else method_output
    raw_metric = metric_source.get(basis.expected_policy.primary_metric)
    source_units = metric_source.get("metric_units")
    source_unit = (
        source_units.get(basis.expected_policy.primary_metric)
        if isinstance(source_units, Mapping)
        else None
    )
    if isinstance(raw_metric, bool) or raw_metric is None:
        raise ValueError(f"PromotionEvidenceBundle {role} MethodJob metric is unavailable.")
    try:
        metric_value = float(raw_metric)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"PromotionEvidenceBundle {role} MethodJob metric is invalid.") from exc
    if not isfinite(metric_value) or (
        basis.expected_policy.unit is not None and source_unit != basis.expected_policy.unit
    ):
        raise ValueError(f"PromotionEvidenceBundle {role} MethodJob metric is not admissible.")

    expected_sample_counts = _source_sample_counts(metric_source.get("sample_counts"))
    expected_guardrails = _source_guardrails(metric_source.get("guardrails"))
    split = evaluation.resolved_runtime_split_type()
    metric_projection = {basis.expected_policy.primary_metric: metric_value}
    expected_selection_metrics = metric_projection if split is BenchmarkSplit.SELECTION else {}
    expected_holdout_metrics = metric_projection if split is BenchmarkSplit.HOLDOUT else {}
    count = expected_sample_counts.get(split.value, 0)
    expected_promotable = (
        count > 0
        and count >= basis.expected_policy.min_sample_count
        and split is basis.expected_policy.compare_split
        and all(
            expected_guardrails.get(name) is True
            for name in basis.expected_policy.required_guardrails
        )
    )

    raw_request_basis = evaluation.metadata.get("method_request_basis")
    if not isinstance(raw_request_basis, Mapping):
        raise ValueError(f"PromotionEvidenceBundle {role} MethodJob request basis is unavailable.")
    try:
        expected_job_spec = JobSpec(
            job_kind="method",
            method_fqn=packet.method_fqn,
            method_version=packet.method_version,
            method_params=packet.configured_method_params,
            input_refs={
                "candidate": packet.candidate_ref,
                "benchmark_suite": packet.benchmark_suite_ref,
                "data_snapshot": packet.data_snapshot_ref,
                "data": packet.data_ref,
            },
            seed=packet.method_seed,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"PromotionEvidenceBundle {role} MethodJob request is invalid.") from exc
    if (
        raw_request_basis.get("schema_version")
        != ("2" if packet.search_method_run_profile is not None else "1")
        or raw_request_basis.get("job_spec")
        != expected_job_spec.model_dump(mode="json", exclude_none=True)
        or raw_request_basis.get("candidate_ref")
        != packet.candidate_ref.model_dump(mode="json", exclude_none=True)
        or raw_request_basis.get("suite_ref")
        != packet.benchmark_suite_ref.model_dump(mode="json", exclude_none=True)
        or raw_request_basis.get("candidate_input_bindings") != packet.candidate_slot_bindings
        or raw_request_basis.get("data_snapshot_bindings") != packet.data_slot_bindings
        or raw_request_basis.get("primary_metric") != basis.expected_policy.primary_metric
        or raw_request_basis.get("direction") != basis.expected_policy.direction.value
        or raw_request_basis.get("split") != split.value
        or raw_request_basis.get("unit") != basis.expected_policy.unit
        or evaluation.metadata.get("metric_unit") != source_unit
        or evaluation.metadata.get("method_input_bindings") != packet.candidate_slot_bindings
        or evaluation.selection_metrics != expected_selection_metrics
        or evaluation.holdout_metrics != expected_holdout_metrics
        or evaluation.sample_counts != expected_sample_counts
        or evaluation.guardrails != expected_guardrails
        or evaluation.promotable != expected_promotable
        or evaluation.status != "measured_candidate"
        or split not in {BenchmarkSplit.SELECTION, BenchmarkSplit.HOLDOUT}
    ):
        raise ValueError(f"PromotionEvidenceBundle {role} differs from MethodJob measurements.")


def _source_sample_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    return {
        split.value: count
        for split in BenchmarkSplit
        if isinstance((count := value.get(split.value)), int)
        and not isinstance(count, bool)
        and count >= 0
    }


def _source_guardrails(value: Any) -> dict[str, bool]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(name): status
        for name, status in value.items()
        if isinstance(name, str) and isinstance(status, bool)
    }


def _assert_exact_evaluation_inputs(
    store: CoreJSONArtifactStore,
    *,
    ref: ArtifactRef,
    expected: Mapping[str, ArtifactRef],
    role: str,
    optional_basis_ref: Any = None,
) -> None:
    manifest = store.get_manifest(ref)
    expected_inputs = {
        input_role: input_ref_from_artifact_ref(input_ref, role=input_role)
        for input_role, input_ref in expected.items()
    }
    if optional_basis_ref is not None:
        try:
            fit_basis_ref = ArtifactRef.model_validate(optional_basis_ref)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"PromotionEvidenceBundle {role} fit basis ref is invalid.") from exc
        expected_inputs["search_gp_fit_basis"] = input_ref_from_artifact_ref(
            fit_basis_ref,
            role="search_gp_fit_basis",
        )
    actual_inputs = {item.role: item for item in manifest.inputs}
    if len(actual_inputs) != len(manifest.inputs) or actual_inputs != expected_inputs:
        raise ValueError(f"PromotionEvidenceBundle {role} manifest source edges are incomplete.")


def persist_promotion_evidence_bundle(
    store: ArtifactStore,
    bundle: PromotionEvidenceBundle,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist promotion evidence bundle helper."""
    projected_inputs = _promotion_evidence_input_refs(bundle)
    projected_by_role = {item.role: item for item in projected_inputs}
    supplied_by_role: dict[str, InputRef] = {}
    for item in inputs or []:
        if item.role in supplied_by_role:
            raise ValueError(f"PromotionEvidenceBundle {item.role} input is duplicated.")
        projected = projected_by_role.get(item.role)
        if projected is not None:
            if item.artifact_id != projected.artifact_id or (
                item.manifest_profile_sha256 is not None
                and item.manifest_profile_sha256 != projected.manifest_profile_sha256
            ):
                raise ValueError(f"PromotionEvidenceBundle {item.role} input profile mismatches.")
            supplied_by_role[item.role] = projected
        else:
            supplied_by_role[item.role] = item
    persisted_inputs = list(projected_inputs)
    persisted_inputs.extend(
        item for role, item in supplied_by_role.items() if role not in projected_by_role
    )
    return store.put_json(
        bundle,
        PutOptions(
            kind="scientist.promotion_evidence_bundle",
            media_type="application/json",
            schema=SchemaInfo(
                name=PROMOTION_EVIDENCE_BUNDLE_SCHEMA_NAME,
                version=bundle.schema_version,
            ),
            inputs=persisted_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def _promotion_evidence_input_refs(bundle: PromotionEvidenceBundle) -> list[InputRef]:
    """Project every persisted artifact reference into an exact selected-view edge."""
    references: list[InputRef] = []
    for role, ref in (
        ("candidate", bundle.candidate_ref),
        ("evaluation", bundle.evaluation_ref),
        ("selection_evaluation", bundle.selection_evaluation_ref),
        ("hidden_holdout_evaluation", bundle.hidden_holdout_evaluation_ref),
        ("adversarial_meta_evaluation", bundle.adversarial_meta_evaluation_ref),
        ("replay_bundle", bundle.replay_bundle_ref),
        ("replay_verification", bundle.replay_verification_ref),
        ("calibration_report", bundle.calibration_report_ref),
        ("governance_report", bundle.governance_report_ref),
        ("stress_test_report", bundle.stress_test_report_ref),
    ):
        if ref is not None:
            references.append(input_ref_from_artifact_ref(ref, role=role))
    references.extend(
        input_ref_from_artifact_ref(ref, role=f"rotating_challenge_evaluation:{index}")
        for index, ref in enumerate(bundle.rotating_challenge_evaluation_refs)
    )
    roles = [item.role for item in references]
    if len(roles) != len(set(roles)):
        raise ValueError("PromotionEvidenceBundle projected input roles are duplicated.")
    return references


def load_promotion_evidence_bundle(
    store: CoreJSONArtifactStore,
    ref: ArtifactRef,
) -> PromotionEvidenceBundle:
    """Load promotion evidence bundle."""
    from polisyos.core.artifacts import load_core_json_artifact

    payload = load_core_json_artifact(store, ref)
    return PromotionEvidenceBundle.model_validate(payload)


__all__ = [
    "PROMOTION_EVIDENCE_BUNDLE_SCHEMA_NAME",
    "PromotionEvidenceBundle",
    "load_promotion_evidence_bundle",
    "persist_promotion_evidence_bundle",
]
