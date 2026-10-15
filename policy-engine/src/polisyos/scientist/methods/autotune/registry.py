"""Public autotune registry module API."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from math import isfinite
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from polisyos.core.artifacts import validate_core_model_json_artifact
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts import DataSnapshot
from polisyos.data_forge.read_api import academic
from polisyos.foundry.methods import MethodNotFoundError, MethodRegistry, MethodSignature
from polisyos.scientist.compute.job_spec import JobKey, JobSpec

from .execution_work import (
    MethodDispatchBinding,
    _fingerprint_method_request_material,
    fingerprint_method_input_value,
)
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

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore

claim_promotion_policy = academic.claim_promotion_policy
metric_is_improved = academic.metric_is_improved
read_claim_promotion_predecessor = academic.read_claim_promotion_predecessor


def _methodjob_suite_source_data_ref(
    store: ArtifactStore,
    suite_ref: ArtifactRef,
    suite: BenchmarkSuite,
) -> ArtifactRef | None:
    """Read the exact source selected by a versioned MethodJob suite producer."""
    suite_manifest = store.get_manifest(suite_ref)
    expected_producer_component = "polisyos.scientist.methods.autotune.benchmark_suite"
    if (
        suite.kind != "method_job"
        or suite_manifest.kind != "scientist.autotune.method_job.suite"
        or suite_manifest.media_type != "application/json"
        or suite_manifest.artifact_schema is None
        or suite_manifest.artifact_schema.name
        != "polisyos.scientist.methods.autotune.BenchmarkSuite"
        or suite_manifest.producer is None
        or suite_manifest.producer.component != expected_producer_component
        or suite_ref.manifest_profile_sha256 is None
    ):
        raise ValueError("methodjob_suite_source_manifest_mismatch")
    if suite.data_snapshot_ref is None:
        if (
            suite.suite_version != "1.0"
            or suite_manifest.artifact_schema.version != "1.0"
            or suite_manifest.producer.version != "1.0"
            or any(item.role in {"data_snapshot", "data"} for item in suite_manifest.inputs)
        ):
            raise ValueError("methodjob_suite_unselected_data_source")
        return None
    snapshot_ref = suite.data_snapshot_ref
    if (
        suite.kind != "method_job"
        or suite.suite_version != "2.0"
        or suite_ref.manifest_profile_sha256 is None
        or snapshot_ref.kind != "fabric.data_snapshot"
        or snapshot_ref.media_type != "application/json"
        or snapshot_ref.manifest_profile_sha256 is None
    ):
        raise ValueError("methodjob_suite_selected_source_invalid")
    if (
        suite_manifest.artifact_schema.version != "2.0"
        or suite_manifest.producer.version != "2.0"
        or suite_manifest.inputs
        != [input_ref_from_artifact_ref(snapshot_ref, role="data_snapshot")]
    ):
        raise ValueError("methodjob_suite_source_manifest_mismatch")
    snapshot_manifest = store.get_manifest(snapshot_ref)
    snapshot = validate_core_model_json_artifact(DataSnapshot, store, snapshot_ref)
    if (
        snapshot_manifest.kind != "fabric.data_snapshot"
        or snapshot_manifest.media_type != "application/json"
        or snapshot_manifest.artifact_schema is None
        or snapshot_manifest.artifact_schema.name != DataSnapshot.ARTIFACT_SCHEMA_NAME
        or snapshot_manifest.artifact_schema.version != DataSnapshot.ARTIFACT_SCHEMA_VERSION
        or not isinstance(snapshot, DataSnapshot)
        or snapshot.data_ref.manifest_profile_sha256 is None
        or snapshot_manifest.inputs
        != [input_ref_from_artifact_ref(snapshot.data_ref, role="data_ref")]
    ):
        raise ValueError("methodjob_suite_snapshot_data_binding_mismatch")
    return snapshot.data_ref


def _methodjob_method_inputs_only_basis(
    *,
    signature: MethodSignature,
    job_spec: JobSpec,
    candidate_bindings: dict[str, str],
    source_state: Mapping[str, Any],
    dispatch_binding: MethodDispatchBinding,
) -> dict[str, Any]:
    """Derive the no-dataset basis from the selected method request and dispatch."""
    return {
        "schema_version": "1",
        "method_fqn": signature.fqn,
        "method_version": signature.version,
        "input_slots": sorted(slot.name for slot in signature.input_slots),
        "candidate_input_bindings": dict(sorted(candidate_bindings.items())),
        "method_params_fingerprint": _fingerprint_method_request_material(
            dict(job_spec.method_params)
        ),
        "source_state_fingerprint": _fingerprint_method_request_material(dict(source_state)),
        "dispatch_binding_fingerprint": _fingerprint_method_request_material(
            dispatch_binding.model_dump(mode="json")
        ),
    }


def _has_methodjob_source_markers(
    *, evaluation: BenchmarkEvaluation, suite_ref: ArtifactRef
) -> bool:
    """Identify the persisted MethodJob evidence family without trusting its contents."""
    metadata = evaluation.metadata
    return any(
        (
            suite_ref.kind == "scientist.autotune.method_job.suite",
            evaluation.method_result_ref is not None,
            evaluation.method_evidence_ref is not None,
            evaluation.method_job_key is not None,
            "method_request_basis" in metadata,
            "method_fqn" in metadata,
        )
    )


def _methodjob_execution_provenance_failure(
    *, evaluation: BenchmarkEvaluation, suite_ref: ArtifactRef
) -> str | None:
    """Hold protected promotion when the execution identity cannot be verified.

    Persisted CAS dispatch and result bytes establish internal consistency, but this
    repository has no configured trusted-executor receipt verifier for MethodJob.
    A self-consistent graph (or generic CAS signature) therefore remains candidate
    evidence and cannot establish who executed it.
    """
    if not _has_methodjob_source_markers(evaluation=evaluation, suite_ref=suite_ref):
        return None
    return "methodjob_execution_provenance_not_established"


def _methodjob_source_admission_failure(
    *,
    store: ArtifactStore,
    candidate_ref: ArtifactRef,
    evaluation_ref: ArtifactRef | None,
    evaluation: BenchmarkEvaluation,
    suite_ref: ArtifactRef,
    policy: PromotionPolicy,
) -> str | None:
    """Recompute MethodJob source, dispatch, metric and lineage before promotion."""
    metadata = evaluation.metadata
    has_methodjob_markers = _has_methodjob_source_markers(
        evaluation=evaluation,
        suite_ref=suite_ref,
    )
    if not has_methodjob_markers:
        return None
    if (
        evaluation.method_result_ref is None
        or evaluation.method_evidence_ref is None
        or evaluation.method_job_key is None
        or not isinstance(metadata.get("method_request_basis"), dict)
    ):
        return "methodjob_source_request_incomplete"

    request_basis = metadata["method_request_basis"]
    if request_basis.get("schema_version") not in {"1", "2"}:
        return "methodjob_source_request_schema_invalid"
    try:
        job_spec = JobSpec.model_validate(request_basis.get("job_spec"))
        basis_candidate_ref = ArtifactRef.model_validate(request_basis.get("candidate_ref"))
        basis_suite_ref = ArtifactRef.model_validate(request_basis.get("suite_ref"))
    except (TypeError, ValueError, ValidationError):
        return "methodjob_source_request_invalid"
    if (
        job_spec.job_kind != "method"
        or isinstance(job_spec.seed, bool)
        or basis_candidate_ref != candidate_ref
        or basis_suite_ref != suite_ref
        or evaluation.candidate_ref != candidate_ref
        or evaluation.loop_id != policy.loop_id
        or metadata.get("method_fqn") != job_spec.method_fqn
        or metadata.get("method_version") != job_spec.method_version
        or metadata.get("method_seed") != job_spec.seed
        or evaluation.method_job_key != JobKey.from_spec(job_spec).value
        or request_basis.get("primary_metric") != policy.primary_metric
        or request_basis.get("direction") != policy.direction.value
        or request_basis.get("split") != evaluation.resolved_runtime_split_type().value
        or request_basis.get("unit") != policy.unit
    ):
        return "methodjob_source_request_binding_mismatch"

    selected_refs = [
        candidate_ref,
        suite_ref,
        evaluation.method_result_ref,
        evaluation.method_evidence_ref,
    ]
    if evaluation_ref is not None:
        selected_refs.append(evaluation_ref)
    if any(ref.manifest_profile_sha256 is None for ref in selected_refs):
        return "methodjob_source_selected_profile_required"
    try:
        suite = load_model_artifact(store, suite_ref, BenchmarkSuite)
        if not isinstance(suite, BenchmarkSuite):
            return "methodjob_suite_payload_unavailable"
        source_data_ref = _methodjob_suite_source_data_ref(store, suite_ref, suite)
    except (KeyError, OSError, RuntimeError, TypeError, ValueError, ValidationError):
        return "methodjob_suite_source_rejected"

    candidate = load_json_artifact(store, candidate_ref)
    if not isinstance(candidate, dict) or candidate.get("loop_id") != evaluation.loop_id:
        return "methodjob_candidate_source_mismatch"
    candidate_manifest = store.get_manifest(candidate_ref)
    candidate_schema = candidate_manifest.artifact_schema
    candidate_producer = candidate_manifest.producer
    artifact_version = candidate.get("artifact_version")
    if (
        candidate_ref.kind != f"scientist.autotune.{evaluation.loop_id}.candidate"
        or candidate_manifest.kind != candidate_ref.kind
        or candidate_manifest.media_type != "application/json"
        or candidate_schema is None
        or not candidate_schema.name.startswith("polisyos.scientist.methods.autotune.")
        or not isinstance(artifact_version, str)
        or candidate_schema.version != artifact_version
        or candidate_producer is None
        or str(candidate_producer.component)
        != "polisyos.scientist.methods.autotune.mutation_artifact"
        or candidate_producer.version != "1.0"
        or candidate_manifest.inputs
        != [input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")]
    ):
        return "methodjob_candidate_source_manifest_mismatch"
    if request_basis.get("candidate_ref") != candidate_ref.model_dump(mode="json") or (
        request_basis.get("suite_ref") != suite_ref.model_dump(mode="json")
    ):
        return "methodjob_source_request_reference_mismatch"

    candidate_bindings = request_basis.get("candidate_input_bindings")
    data_bindings = request_basis.get("data_snapshot_bindings")
    if not isinstance(candidate_bindings, dict) or not isinstance(data_bindings, dict):
        return "methodjob_source_bindings_unavailable"
    if any(
        not isinstance(slot, str) or not slot or not isinstance(field, str) or not field
        for bindings in (candidate_bindings, data_bindings)
        for slot, field in bindings.items()
    ):
        return "methodjob_source_bindings_invalid"
    if set(candidate_bindings) & set(data_bindings):
        return "methodjob_source_slot_binding_conflict"

    expected_input_refs = {
        "candidate": candidate_ref,
        "benchmark_suite": suite_ref,
    }
    data_payload: dict[str, Any] | None = None
    snapshot_ref = suite.data_snapshot_ref
    if source_data_ref is not None:
        if snapshot_ref is None or not data_bindings:
            return "methodjob_suite_data_source_binding_mismatch"
        expected_input_refs.update({"data_snapshot": snapshot_ref, "data": source_data_ref})
        if job_spec.input_refs.get("data_snapshot") != snapshot_ref:
            return "methodjob_request_snapshot_mismatch"
        if job_spec.input_refs.get("data") != source_data_ref:
            return "methodjob_request_data_mismatch"
        raw_data_payload = load_json_artifact(store, source_data_ref)
        if not isinstance(raw_data_payload, dict):
            return "methodjob_source_data_unavailable"
        data_payload = raw_data_payload
    elif data_bindings or snapshot_ref is not None:
        return "methodjob_suite_data_source_binding_mismatch"
    if job_spec.input_refs != expected_input_refs:
        return "methodjob_request_input_refs_mismatch"

    source_state: dict[str, Any] = {}
    for slot, field in candidate_bindings.items():
        if field not in candidate:
            return "methodjob_candidate_slot_source_missing"
        source_state[slot] = candidate[field]
    for slot, field in data_bindings.items():
        if data_payload is None or field not in data_payload:
            return "methodjob_data_slot_source_missing"
        source_state[slot] = data_payload[field]
    try:
        signature = (
            MethodRegistry.get_instance()
            .get(
                job_spec.method_fqn,
                version=job_spec.method_version,
            )
            .signature
        )
    except MethodNotFoundError:
        return "methodjob_source_signature_unavailable"
    if signature.fqn != job_spec.method_fqn or signature.version != job_spec.method_version:
        return "methodjob_source_signature_mismatch"
    expected_method_slots = {slot.name for slot in signature.input_slots}
    if set(candidate_bindings) | set(data_bindings) != expected_method_slots or set(
        candidate_bindings
    ) & set(data_bindings):
        return "methodjob_input_slot_binding_mismatch"
    try:
        source_state_fingerprint = _fingerprint_method_request_material(source_state)
    except (OverflowError, TypeError, ValueError):
        return "methodjob_source_slot_basis_unfingerprintable"
    if request_basis.get("method_state_fingerprint") != source_state_fingerprint:
        return "methodjob_source_slot_basis_mismatch"

    expected_evaluation_inputs = {
        "candidate": input_ref_from_artifact_ref(candidate_ref, role="candidate"),
        "benchmark_suite": input_ref_from_artifact_ref(suite_ref, role="benchmark_suite"),
        "method_result": input_ref_from_artifact_ref(
            evaluation.method_result_ref,
            role="method_result",
        ),
        "method_evidence": input_ref_from_artifact_ref(
            evaluation.method_evidence_ref,
            role="method_evidence",
        ),
    }
    if evaluation.execution_work_packet_ref is not None:
        expected_evaluation_inputs["execution_work_packet"] = input_ref_from_artifact_ref(
            evaluation.execution_work_packet_ref,
            role="execution_work_packet",
        )
    raw_fit_basis_ref = metadata.get("search_gp_fit_basis_ref")
    if raw_fit_basis_ref is not None:
        try:
            fit_basis_ref = ArtifactRef.model_validate(raw_fit_basis_ref)
        except (TypeError, ValueError, ValidationError):
            return "methodjob_search_fit_basis_invalid"
        if fit_basis_ref.manifest_profile_sha256 is None:
            return "methodjob_search_fit_basis_selected_profile_required"
        expected_evaluation_inputs["search_gp_fit_basis"] = input_ref_from_artifact_ref(
            fit_basis_ref,
            role="search_gp_fit_basis",
        )
    if evaluation_ref is not None:
        evaluation_manifest = store.get_manifest(evaluation_ref)
        evaluation_inputs = {item.role: item for item in evaluation_manifest.inputs}
        if (
            len(evaluation_inputs) != len(evaluation_manifest.inputs)
            or evaluation_inputs != expected_evaluation_inputs
        ):
            return "methodjob_evaluation_source_lineage_mismatch"

    result_ref = evaluation.method_result_ref
    evidence_ref = evaluation.method_evidence_ref
    result_inputs = {
        f"input:{name}": input_ref_from_artifact_ref(ref, role=f"input:{name}")
        for name, ref in expected_input_refs.items()
    }
    result_manifest = store.get_manifest(result_ref)
    actual_result_inputs = {item.role: item for item in result_manifest.inputs}
    if (
        not result_manifest.kind.startswith("scientist.method_result.")
        or len(actual_result_inputs) != len(result_manifest.inputs)
        or actual_result_inputs != result_inputs
    ):
        return "methodjob_result_source_lineage_mismatch"
    evidence_manifest = store.get_manifest(evidence_ref)
    evidence_payload = load_json_artifact(store, evidence_ref)
    if not isinstance(evidence_payload, dict):
        return "methodjob_execution_evidence_unavailable"
    try:
        evidence_result_ref = ArtifactRef.model_validate(evidence_payload.get("method_result_ref"))
    except (TypeError, ValueError, ValidationError):
        return "methodjob_execution_evidence_binding_invalid"
    if (
        evidence_manifest.kind != "scientist.method_evidence"
        or evidence_manifest.inputs
        != [input_ref_from_artifact_ref(result_ref, role="method_result")]
        or evidence_payload.get("authority_purpose") != "method_execution"
        or evidence_payload.get("result_ref") != str(result_ref.artifact_id)
        or evidence_result_ref != result_ref
        or evidence_payload.get("method_fqn") != job_spec.method_fqn
    ):
        return "methodjob_execution_evidence_binding_mismatch"
    if evidence_payload.get("method_dispatch_binding_status") != "recomputed":
        return "methodjob_dispatch_binding_unavailable"
    try:
        dispatch_binding = MethodDispatchBinding.model_validate(
            evidence_payload.get("method_dispatch_binding")
        )
        expected_method_params_fingerprint = _fingerprint_method_request_material(
            job_spec.method_params
        )
        expected_input_state_fingerprints = {
            name: fingerprint_method_input_value(value)
            for name, value in sorted(source_state.items())
        }
        expected_input_schemas = {
            name: store.get_manifest(ref).artifact_schema
            for name, ref in sorted(expected_input_refs.items())
        }
    except (KeyError, OSError, OverflowError, RuntimeError, TypeError, ValueError, ValidationError):
        return "methodjob_dispatch_binding_invalid"
    if (
        dispatch_binding.method_fqn != job_spec.method_fqn
        or dispatch_binding.method_version != job_spec.method_version
        or dispatch_binding.method_seed != job_spec.seed
        or dispatch_binding.method_params_fingerprint != expected_method_params_fingerprint
        or dispatch_binding.input_refs != job_spec.input_refs
        or dispatch_binding.input_schemas != expected_input_schemas
        or dispatch_binding.input_state_fingerprints != expected_input_state_fingerprints
    ):
        return "methodjob_dispatch_source_mismatch"
    if source_data_ref is None:
        try:
            expected_method_inputs_only_basis = _methodjob_method_inputs_only_basis(
                signature=signature,
                job_spec=job_spec,
                candidate_bindings=candidate_bindings,
                source_state=source_state,
                dispatch_binding=dispatch_binding,
            )
        except (OverflowError, TypeError, ValueError):
            return "methodjob_method_inputs_only_basis_unfingerprintable"
        if request_basis.get("method_inputs_only_basis") != expected_method_inputs_only_basis:
            return "methodjob_method_inputs_only_basis_mismatch"
    elif "method_inputs_only_basis" in request_basis:
        return "methodjob_method_inputs_only_basis_unexpected"

    result_payload = load_json_artifact(store, result_ref)
    if not isinstance(result_payload, dict):
        return "methodjob_result_payload_unavailable"
    if "result" in result_payload:
        result_body = result_payload.get("result")
        if not isinstance(result_body, dict):
            return "methodjob_result_body_unavailable"
    else:
        result_body = result_payload
    raw_metric = result_body.get(policy.primary_metric)
    raw_units = result_body.get("metric_units")
    source_unit = raw_units.get(policy.primary_metric) if isinstance(raw_units, dict) else None
    if isinstance(raw_metric, bool) or raw_metric is None:
        return "methodjob_result_metric_unavailable"
    try:
        actual_metric = float(raw_metric)
    except (TypeError, ValueError, OverflowError):
        return "methodjob_result_metric_invalid"
    if not isfinite(actual_metric) or (policy.unit is not None and source_unit != policy.unit):
        return "methodjob_result_metric_invalid"
    actual_metrics = evaluation.metrics_for_split(policy.compare_split)
    if actual_metrics.get(policy.primary_metric) != actual_metric:
        return "methodjob_evaluation_metric_mismatch"
    actual_count_map = result_body.get("sample_counts")
    actual_counts = (
        {
            key: value
            for key, value in actual_count_map.items()
            if isinstance(key, str)
            and isinstance(value, int)
            and not isinstance(value, bool)
            and value >= 0
        }
        if isinstance(actual_count_map, dict)
        else {}
    )
    actual_guardrail_map = result_body.get("guardrails")
    actual_guardrails = (
        {
            key: value
            for key, value in actual_guardrail_map.items()
            if isinstance(key, str) and isinstance(value, bool)
        }
        if isinstance(actual_guardrail_map, dict)
        else {}
    )
    if (
        evaluation.sample_counts != actual_counts
        or evaluation.guardrails != actual_guardrails
        or metadata.get("metric_unit") != source_unit
        or evaluation.status != "measured_candidate"
    ):
        return "methodjob_evaluation_result_summary_mismatch"
    actual_count = actual_counts.get(policy.compare_split.value, 0)
    metric_promotable = (
        actual_count > 0
        and actual_count >= policy.min_sample_count
        and evaluation.resolved_runtime_split_type() == policy.compare_split
        and all(actual_guardrails.get(name) is True for name in policy.required_guardrails)
    )
    expected_promotable = (
        metric_promotable
        and _methodjob_execution_provenance_failure(
            evaluation=evaluation,
            suite_ref=suite_ref,
        )
        is None
    )
    if evaluation.promotable is not expected_promotable:
        return "methodjob_evaluation_promotability_mismatch"
    return None


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
        try:
            methodjob_failure = _methodjob_source_admission_failure(
                store=self._store,
                candidate_ref=candidate_ref,
                evaluation_ref=evaluation_ref,
                evaluation=evaluation,
                suite_ref=suite_ref,
                policy=policy,
            )
        except (KeyError, OSError, OverflowError, RuntimeError, TypeError, ValueError):
            return "methodjob_source_admission_check_failed"
        if methodjob_failure is not None:
            return methodjob_failure
        return _methodjob_execution_provenance_failure(
            evaluation=evaluation,
            suite_ref=suite_ref,
        )

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
                read_claim_promotion_predecessor(
                    self._root, current.model_dump(mode="json"), store=self._store
                )
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
