"""Public autotune runtime module API."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import fingerprint
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.scientist.compute.job_spec import JobKey, JobSpec
from polisyos.scientist.methods.search.controller import (
    SearchConfig,
    SearchController,
    SearchResult,
)
from polisyos.scientist.methods.search.objective import (
    BaseObjective,
    CompositeObjective,
    OptimizationDirection,
)
from polisyos.scientist.methods.search.stopping import MaxIterations

from .models import (
    BayesianSourceProfile,
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSuite,
    ChampionPointer,
    MetricDirection,
    MutationArtifact,
    PromotionPolicy,
    SearchLoopSpec,
    default_store,
    load_json_artifact,
    load_model_artifact,
    persist_benchmark_evaluation,
    persist_mutation_artifact,
)
from .registry import ChampionRegistry

if TYPE_CHECKING:
    from .execution_work import MethodJobExecutionWorkPacket

ModelT = TypeVar("ModelT", bound=MutationArtifact)


class PydanticMutationCodec(Generic[ModelT]):
    """Pydantic mutation codec public type."""

    def __init__(self, model_cls: type[ModelT]) -> None:
        self._model_cls = model_cls

    def encode(self, payload: MutationArtifact) -> MutationArtifact:
        return self._model_cls.model_validate(payload)

    def decode(self, payload: dict[str, Any]) -> MutationArtifact:
        return self._model_cls.model_validate(payload)


def seed_loop_baseline(
    *,
    loop_id: str,
    baseline: MutationArtifact,
    store: FileSystemCAS | None = None,
    registry: ChampionRegistry | None = None,
    suite_version: str = "1.0",
    metadata: dict[str, Any] | None = None,
) -> ChampionPointer:
    """Seed loop baseline helper."""
    active_store = store or default_store()
    active_registry = registry or ChampionRegistry(store=active_store)
    candidate_ref = persist_mutation_artifact(active_store, baseline)
    evaluation = BenchmarkEvaluation(
        loop_id=loop_id,
        suite_id=f"{loop_id}.baseline",
        suite_version=suite_version,
        candidate_ref=candidate_ref,
        promotable=True,
        status="seeded_baseline",
        notes=["seeded production baseline"],
        metadata={"seeded_baseline": True, **(metadata or {})},
    )
    evaluation_ref = persist_benchmark_evaluation(
        active_store,
        evaluation,
        inputs=[InputRef(artifact_id=candidate_ref.artifact_id, role="candidate")],
    )
    return active_registry.seed_baseline(
        loop_id,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        suite_version=suite_version,
        metadata=metadata,
    )


class ChampionBackedRuntimeLoader(Generic[ModelT]):
    """Champion backed runtime loader implementation."""

    def __init__(
        self,
        *,
        loop_id: str,
        model_cls: type[ModelT],
        baseline_factory: Any,
        store: FileSystemCAS | None = None,
        registry: ChampionRegistry | None = None,
        suite_version: str = "1.0",
    ) -> None:
        self._loop_id = loop_id
        self._model_cls = model_cls
        self._baseline_factory = baseline_factory
        self._store = store or default_store()
        self._registry = registry or ChampionRegistry(store=self._store)
        self._suite_version = suite_version

    def ensure_baseline(self, context: dict[str, Any] | None = None) -> ChampionPointer:
        baseline = self._baseline_factory(context or {})
        return seed_loop_baseline(
            loop_id=self._loop_id,
            baseline=baseline,
            store=self._store,
            registry=self._registry,
            suite_version=self._suite_version,
        )

    def load(self, context: dict[str, Any] | None = None) -> ModelT:
        champion = self._registry.get(self._loop_id)
        if champion is None:
            champion = self.ensure_baseline(context)
        payload = load_model_artifact(self._store, champion.candidate_ref, self._model_cls)
        return cast("ModelT", payload)


class _AutotuneObjective(BaseObjective):
    def __init__(self, policy: PromotionPolicy):
        super().__init__(weight=1.0)
        self._policy = policy

    @property
    def name(self) -> str:
        return self._policy.primary_metric

    @property
    def direction(self) -> OptimizationDirection:
        return OptimizationDirection.MINIMIZE

    def _extract_value(self, results: dict[str, Any]) -> float:
        raw_metric = results.get(self._policy.primary_metric)
        if isinstance(raw_metric, bool) or raw_metric is None:
            return float("inf")
        try:
            metric = float(raw_metric)
        except (TypeError, ValueError, OverflowError):
            return float("inf")
        if not isfinite(metric):
            return float("inf")
        if self._policy.direction == MetricDirection.MAXIMIZE:
            return -metric
        return metric


@dataclass
class SearchRunArtifacts:
    """Search run artifacts public type."""

    candidate_ref: ArtifactRef
    evaluation_ref: ArtifactRef
    evaluation: BenchmarkEvaluation


class SequenceCandidateGenerator:
    """Sequence candidate generator implementation."""

    def __init__(self, candidates: list[dict[str, Any] | MutationArtifact]) -> None:
        self._candidates = list(candidates)
        self._index = 0

    def generate(
        self,
        history: list[Any],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        del history, current_best, context
        if self._index >= len(self._candidates):
            return (
                self._candidates[-1].model_dump(mode="json")
                if isinstance(self._candidates[-1], BaseModel)
                else dict(self._candidates[-1])
            )
        candidate = self._candidates[self._index]
        self._index += 1
        if isinstance(candidate, BaseModel):
            return candidate.model_dump(mode="json")
        return dict(candidate)


class MethodJobBenchmarkEvaluator:
    """Evaluate a candidate by executing a Foundry MethodJob and retaining its CAS evidence.

    The evaluator consumes a candidate artifact as the typed state for one method job.
    Candidate input bindings map method slot names to fields in that artifact. A metric
    is admitted only when the method returns the policy's exact metric name and, when
    the policy declares a unit, the method also returns that exact unit.
    """

    def __init__(
        self,
        *,
        method_fqn: str,
        candidate_input_bindings: Mapping[str, str],
        data_snapshot_bindings: Mapping[str, str] | None = None,
        method_version: str | None = None,
        method_params: Mapping[str, Any] | None = None,
        split: BenchmarkSplit = BenchmarkSplit.SELECTION,
        seed: int = 0,
    ) -> None:
        if not method_fqn.strip():
            raise ValueError("method_fqn must be non-empty")
        resolved_data_bindings = dict(data_snapshot_bindings or {})
        if not candidate_input_bindings and not resolved_data_bindings:
            raise ValueError(
                "candidate_input_bindings or data_snapshot_bindings must name method inputs"
            )
        if set(candidate_input_bindings) & set(resolved_data_bindings):
            raise ValueError("candidate and DataSnapshot input bindings must not overlap")
        if split not in {BenchmarkSplit.SELECTION, BenchmarkSplit.HOLDOUT}:
            raise ValueError("MethodJob evaluation supports selection or holdout splits")
        if isinstance(seed, bool):
            raise TypeError("seed must be an integer")
        self._method_fqn = method_fqn
        self._method_version = method_version
        self._candidate_input_bindings = dict(candidate_input_bindings)
        self._data_snapshot_bindings = resolved_data_bindings
        self._method_params = dict(method_params or {})
        self._split = split
        self._seed = int(seed)

    def evaluate(
        self,
        candidate_ref: ArtifactRef,
        suite_ref: ArtifactRef,
        context: dict[str, Any],
    ) -> BenchmarkEvaluation:
        """Execute one MethodJob and return the exact measured output with its refs."""
        from polisyos.scientist.compute.job_spec import JobSpec
        from polisyos.scientist.compute.runner import run_job

        store = context.get("store")
        policy = context.get("policy")
        loop_id = context.get("loop_id")
        if store is None or not callable(getattr(store, "get_bytes", None)):
            raise TypeError("MethodJobBenchmarkEvaluator requires the active artifact store")
        if not isinstance(policy, PromotionPolicy):
            raise TypeError("MethodJobBenchmarkEvaluator requires the active PromotionPolicy")
        if not isinstance(loop_id, str) or not loop_id:
            raise TypeError("MethodJobBenchmarkEvaluator requires the active loop_id")
        cas_root = getattr(store, "root", None)
        if cas_root is None:
            raise TypeError("MethodJobBenchmarkEvaluator requires a filesystem CAS root")

        candidate = load_json_artifact(store, candidate_ref)
        suite = load_model_artifact(store, suite_ref, BenchmarkSuite)
        if not isinstance(candidate, Mapping):
            raise TypeError("candidate artifact must contain an object")
        if candidate.get("loop_id") != loop_id:
            return self._empty_evaluation(
                loop_id=loop_id,
                suite=suite,
                candidate_ref=candidate_ref,
                split=self._split,
                status="candidate_loop_mismatch",
            )

        method_state: dict[str, Any] = {}
        for slot_name, candidate_field in self._candidate_input_bindings.items():
            if candidate_field not in candidate:
                return self._empty_evaluation(
                    loop_id=loop_id,
                    suite=suite,
                    candidate_ref=candidate_ref,
                    split=self._split,
                    status="method_input_unavailable",
                    notes=[f"Candidate does not contain input field '{candidate_field}'."],
                )
            method_state[slot_name] = candidate[candidate_field]

        data_snapshot_ref: ArtifactRef | None = None
        data_ref: ArtifactRef | None = None
        data_payload: Mapping[str, Any] | None = None
        if self._data_snapshot_bindings:
            try:
                raw_snapshot_ref = context.get("data_snapshot_ref")
                data_snapshot_ref = (
                    raw_snapshot_ref
                    if isinstance(raw_snapshot_ref, ArtifactRef)
                    else ArtifactRef.model_validate(raw_snapshot_ref)
                )
                if data_snapshot_ref.kind != "fabric.data_snapshot":
                    raise ValueError("data_snapshot_ref_kind_mismatch")
                snapshot_manifest = store.get_manifest(data_snapshot_ref)
                if snapshot_manifest.kind != "fabric.data_snapshot":
                    raise ValueError("data_snapshot_manifest_kind_mismatch")
                snapshot = load_model_artifact(store, data_snapshot_ref, DataSnapshot)
                if not isinstance(snapshot, DataSnapshot):
                    raise TypeError("data_snapshot_payload_unavailable")
                data_ref = snapshot.data_ref
                snapshot_input_ids = {
                    (item.role, str(item.artifact_id)) for item in snapshot_manifest.inputs
                }
                if ("data_ref", str(data_ref.artifact_id)) not in snapshot_input_ids:
                    raise ValueError("data_snapshot_data_ref_not_in_manifest")
                raw_data = load_json_artifact(store, data_ref)
                if not isinstance(raw_data, Mapping):
                    raise TypeError("data_ref_payload_must_be_object")
                data_payload = raw_data
                for slot_name, data_field in self._data_snapshot_bindings.items():
                    if data_field not in data_payload:
                        raise KeyError(f"DataSnapshot data is missing '{data_field}'")
                    method_state[slot_name] = data_payload[data_field]
            except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
                return self._empty_evaluation(
                    loop_id=loop_id,
                    suite=suite,
                    candidate_ref=candidate_ref,
                    split=self._split,
                    status="data_snapshot_unavailable",
                    notes=[str(exc)],
                )

        configured_seed = context.get("method_job_seed", self._seed)
        if isinstance(configured_seed, bool) or not isinstance(configured_seed, int):
            return self._empty_evaluation(
                loop_id=loop_id,
                suite=suite,
                candidate_ref=candidate_ref,
                split=self._split,
                status="method_seed_unavailable",
            )
        input_refs = {"candidate": candidate_ref, "benchmark_suite": suite_ref}
        if data_snapshot_ref is not None and data_ref is not None:
            input_refs.update({"data_snapshot": data_snapshot_ref, "data": data_ref})
        spec = JobSpec(
            job_kind="method",
            method_fqn=self._method_fqn,
            method_version=self._method_version,
            method_params=self._method_params,
            input_refs=input_refs,
            seed=configured_seed,
        )
        job_result = run_job(
            spec,
            cas_root=cas_root,
            method_state=method_state,
        )

        refs = {
            "method_result_ref": job_result.method_result_ref,
            "method_evidence_ref": job_result.method_evidence_ref,
            "method_job_key": job_result.job_key.value,
        }
        base_metadata: dict[str, Any] = {
            "method_fqn": self._method_fqn,
            "method_version": self._method_version,
            "method_seed": configured_seed,
            "method_job_key": job_result.job_key.value,
            "method_input_bindings": dict(self._candidate_input_bindings),
        }
        if job_result.issues or job_result.method_result_ref is None:
            return self._empty_evaluation(
                loop_id=loop_id,
                suite=suite,
                candidate_ref=candidate_ref,
                split=self._split,
                status="method_job_failed",
                notes=[f"MethodJob returned {len(job_result.issues)} issue(s)."],
                metadata=base_metadata,
                refs=refs,
            )

        fresh_reader = FileSystemCAS(cas_root)
        output = load_json_artifact(fresh_reader, job_result.method_result_ref)
        if not isinstance(output, Mapping):
            return self._empty_evaluation(
                loop_id=loop_id,
                suite=suite,
                candidate_ref=candidate_ref,
                split=self._split,
                status="method_output_unavailable",
                metadata=base_metadata,
                refs=refs,
            )

        execution_work_ref, execution_work_status, execution_work_note = (
            self._persist_execution_work_packet(
                store=fresh_reader,
                candidate=candidate,
                candidate_ref=candidate_ref,
                suite_ref=suite_ref,
                data_snapshot_ref=data_snapshot_ref,
                data_ref=data_ref,
                data_payload=data_payload,
                job_spec=spec,
                method_result_ref=job_result.method_result_ref,
                method_evidence_ref=job_result.method_evidence_ref,
                method_job_key=job_result.job_key.value,
                method_output=output,
                context=context,
            )
        )

        metric_output = output.get("result")
        metric_source = metric_output if isinstance(metric_output, Mapping) else output
        raw_metric = metric_source.get(policy.primary_metric)
        source_units = metric_source.get("metric_units")
        source_unit = (
            source_units.get(policy.primary_metric) if isinstance(source_units, Mapping) else None
        )
        metric_unit_matches = policy.unit is None or source_unit == policy.unit
        metric_value: float | None = None
        if not isinstance(raw_metric, bool) and raw_metric is not None:
            try:
                parsed = float(raw_metric)
            except (TypeError, ValueError, OverflowError):
                parsed = float("nan")
            if isfinite(parsed) and metric_unit_matches:
                metric_value = parsed

        sample_counts = self._sample_counts(metric_source.get("sample_counts"))
        guardrails = self._guardrails(metric_source.get("guardrails"))
        metadata = {
            **base_metadata,
            "metric_unit": source_unit,
            "method_warnings": list(job_result.warnings),
            "data_snapshot_ref": (
                str(data_snapshot_ref.artifact_id) if data_snapshot_ref is not None else None
            ),
            "data_ref": str(data_ref.artifact_id) if data_ref is not None else None,
        }
        if metric_value is None:
            return BenchmarkEvaluation(
                loop_id=loop_id,
                suite_id=suite.suite_id,
                suite_version=suite.suite_version,
                candidate_ref=candidate_ref,
                method_result_ref=job_result.method_result_ref,
                method_evidence_ref=job_result.method_evidence_ref,
                method_job_key=job_result.job_key.value,
                execution_work_packet_ref=execution_work_ref,
                execution_work_packet_status=execution_work_status,
                execution_work_packet_note=execution_work_note,
                sample_counts=sample_counts,
                guardrails=guardrails,
                promotable=False,
                status="metric_unavailable",
                notes=[
                    f"MethodJob did not return finite '{policy.primary_metric}'"
                    " with the policy's declared unit."
                ],
                runtime_split_type=self._split,
                metadata=metadata,
            )

        metric_mapping = {policy.primary_metric: metric_value}
        metric_counts = sample_counts.get(self._split.value, 0)
        promotable = (
            metric_counts > 0
            and metric_counts >= policy.min_sample_count
            and self._split == policy.compare_split
            and all(guardrails.get(name) is True for name in policy.required_guardrails)
        )
        return BenchmarkEvaluation(
            loop_id=loop_id,
            suite_id=suite.suite_id,
            suite_version=suite.suite_version,
            candidate_ref=candidate_ref,
            method_result_ref=job_result.method_result_ref,
            method_evidence_ref=job_result.method_evidence_ref,
            method_job_key=job_result.job_key.value,
            execution_work_packet_ref=execution_work_ref,
            execution_work_packet_status=execution_work_status,
            execution_work_packet_note=execution_work_note,
            selection_metrics=(metric_mapping if self._split == BenchmarkSplit.SELECTION else {}),
            holdout_metrics=(metric_mapping if self._split == BenchmarkSplit.HOLDOUT else {}),
            sample_counts=sample_counts,
            guardrails=guardrails,
            promotable=promotable,
            status="measured_candidate",
            notes=["MethodJob output is candidate-grade measurement."],
            runtime_split_type=self._split,
            metadata=metadata,
        )

    @staticmethod
    def _sample_counts(value: Any) -> dict[str, int]:
        if not isinstance(value, Mapping):
            return {}
        counts: dict[str, int] = {}
        for split in BenchmarkSplit:
            count = value.get(split.value)
            if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
                counts[split.value] = count
        return counts

    @staticmethod
    def _guardrails(value: Any) -> dict[str, bool]:
        if not isinstance(value, Mapping):
            return {}
        return {
            str(name): status
            for name, status in value.items()
            if isinstance(name, str) and isinstance(status, bool)
        }

    @staticmethod
    def _empty_evaluation(
        *,
        loop_id: str,
        suite: BenchmarkSuite,
        candidate_ref: ArtifactRef,
        status: str,
        split: BenchmarkSplit,
        notes: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        refs: dict[str, Any] | None = None,
    ) -> BenchmarkEvaluation:
        return BenchmarkEvaluation(
            loop_id=loop_id,
            suite_id=suite.suite_id,
            suite_version=suite.suite_version,
            candidate_ref=candidate_ref,
            method_result_ref=(refs or {}).get("method_result_ref"),
            method_evidence_ref=(refs or {}).get("method_evidence_ref"),
            method_job_key=(refs or {}).get("method_job_key"),
            promotable=False,
            status=status,
            notes=list(notes or []),
            runtime_split_type=split,
            metadata=dict(metadata or {}),
        )

    def _persist_execution_work_packet(
        self,
        *,
        store: FileSystemCAS,
        candidate: Mapping[str, Any],
        candidate_ref: ArtifactRef,
        suite_ref: ArtifactRef,
        data_snapshot_ref: ArtifactRef | None,
        data_ref: ArtifactRef | None,
        data_payload: Mapping[str, Any] | None,
        job_spec: JobSpec,
        method_result_ref: ArtifactRef,
        method_evidence_ref: ArtifactRef,
        method_job_key: str,
        method_output: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> tuple[ArtifactRef | None, str, str | None]:
        """Persist and fresh-read an explicitly diagnostic source-bound work packet."""
        from .execution_work import (
            MethodJobExecutionWorkPacket,
            persist_method_job_execution_work_packet,
        )

        if self._method_params.get("capture_execution_work") is not True:
            return None, "unavailable", "method_work_capture_not_enabled"
        if not self._data_snapshot_bindings or data_snapshot_ref is None or data_ref is None:
            return None, "unavailable", "source_data_snapshot_not_bound"
        if candidate.get("candidate_status") != "diagnostic_only":
            return None, "rejected", "candidate_is_not_marked_diagnostic_only"

        run_id = context.get("run_id")
        evaluation_id = context.get("evaluation_id")
        attempt_id = context.get("evaluation_attempt_id")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (run_id, evaluation_id, attempt_id)
        ):
            return None, "unavailable", "run_evaluation_attempt_identity_unavailable"

        raw_result = method_output.get("result")
        if not isinstance(raw_result, Mapping):
            return None, "unavailable", "method_result_payload_unavailable"
        raw_work = raw_result.get("bootstrap_execution")
        if raw_work is None:
            return None, "unavailable", "method_result_has_no_measured_bootstrap_work"
        from polisyos.foundry.methods.catalog.causal.ci_backends import BootstrapExecutionWork

        try:
            work = BootstrapExecutionWork.model_validate(raw_work)
        except (TypeError, ValueError, ValidationError):
            return None, "rejected", "method_result_bootstrap_counts_invalid"

        sample_count = _source_sample_count(data_payload, self._data_snapshot_bindings)
        raw_n_obs = raw_result.get("n_obs")
        effective_config = raw_result.get("nuisance_config")
        if (
            sample_count is None
            or isinstance(raw_n_obs, bool)
            or not isinstance(raw_n_obs, int)
            or raw_n_obs != sample_count
            or not isinstance(effective_config, Mapping)
        ):
            return None, "rejected", "method_result_sample_binding_invalid"

        try:
            packet = MethodJobExecutionWorkPacket(
                run_id=run_id,
                evaluation_id=evaluation_id,
                evaluation_attempt_id=attempt_id,
                candidate_ref=candidate_ref,
                benchmark_suite_ref=suite_ref,
                data_snapshot_ref=data_snapshot_ref,
                data_ref=data_ref,
                method_result_ref=method_result_ref,
                method_evidence_ref=method_evidence_ref,
                method_job_key=method_job_key,
                method_fqn=self._method_fqn,
                method_version=self._method_version,
                method_seed=job_spec.seed,
                configured_method_params=dict(self._method_params),
                effective_method_config=dict(effective_config),
                candidate_slot_bindings=dict(self._candidate_input_bindings),
                data_slot_bindings=dict(self._data_snapshot_bindings),
                method_profile_fingerprint=fingerprint(
                    job_spec.model_dump(mode="json", exclude_none=True)
                ),
                actual_sample_count=sample_count,
                bootstrap_execution=work,
            )
        except (TypeError, ValueError, ValidationError):
            return None, "rejected", "method_work_packet_contract_mismatch"
        try:
            packet_ref = persist_method_job_execution_work_packet(store, packet)
        except (OSError, RuntimeError, TypeError, ValueError):
            return None, "unavailable", "method_work_packet_persistence_failed"
        try:
            read_method_job_execution_work_packet(store, packet_ref)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError, ValidationError):
            return packet_ref, "rejected", "persisted_method_work_packet_failed_fresh_admission"
        return packet_ref, "available", None


def _source_sample_count(
    data_payload: Mapping[str, Any] | None,
    slot_bindings: Mapping[str, str],
) -> int | None:
    """Recompute the bound row count from every source field consumed by a method."""
    if data_payload is None or not slot_bindings:
        return None
    lengths: set[int] = set()
    for field_name in slot_bindings.values():
        value = data_payload.get(field_name)
        if isinstance(value, (str, bytes, bytearray, Mapping)) or value is None:
            return None
        try:
            length = len(value)
        except TypeError:
            return None
        if isinstance(length, bool) or length < 1:
            return None
        lengths.add(length)
    return next(iter(lengths)) if len(lengths) == 1 else None


def read_method_job_execution_work_packet(
    store: FileSystemCAS,
    ref: ArtifactRef,
) -> MethodJobExecutionWorkPacket:
    """Fresh-read and reconcile a diagnostic work packet against source CAS artifacts."""
    from .execution_work import (
        MethodDispatchBinding,
        MethodJobExecutionWorkPacket,
        fingerprint_method_input_value,
    )

    if ref.kind != "scientist.autotune.method_execution_work_packet":
        raise ValueError("method_work_packet_kind_mismatch")
    packet_manifest = store.get_manifest(ref)
    if (
        packet_manifest.kind != "scientist.autotune.method_execution_work_packet"
        or packet_manifest.artifact_schema is None
        or packet_manifest.artifact_schema.name
        != "polisyos.scientist.methods.autotune.MethodJobExecutionWorkPacket"
        or packet_manifest.artifact_schema.version != "1.2"
    ):
        raise ValueError("method_work_packet_manifest_mismatch")
    packet = load_model_artifact(store, ref, MethodJobExecutionWorkPacket)
    if not isinstance(packet, MethodJobExecutionWorkPacket):
        raise TypeError("method_work_packet_payload_unavailable")

    expected_packet_inputs = {
        role: input_ref_from_artifact_ref(source_ref, role=role)
        for role, source_ref in (
            ("candidate", packet.candidate_ref),
            ("benchmark_suite", packet.benchmark_suite_ref),
            ("data_snapshot", packet.data_snapshot_ref),
            ("data", packet.data_ref),
            ("method_result", packet.method_result_ref),
            ("method_evidence", packet.method_evidence_ref),
        )
    }
    packet_inputs = {item.role: item for item in packet_manifest.inputs}
    if (
        len(packet_manifest.inputs) != len(expected_packet_inputs)
        or packet_inputs != expected_packet_inputs
    ):
        raise ValueError("method_work_packet_lineage_mismatch")

    candidate = load_json_artifact(store, packet.candidate_ref)
    if not isinstance(candidate, Mapping) or candidate.get("candidate_status") != "diagnostic_only":
        raise ValueError("method_work_packet_candidate_status_mismatch")
    snapshot_manifest = store.get_manifest(packet.data_snapshot_ref)
    snapshot = load_model_artifact(store, packet.data_snapshot_ref, DataSnapshot)
    if (
        snapshot_manifest.kind != "fabric.data_snapshot"
        or not isinstance(snapshot, DataSnapshot)
        or snapshot.data_ref != packet.data_ref
        or not any(
            item == input_ref_from_artifact_ref(packet.data_ref, role="data_ref")
            for item in snapshot_manifest.inputs
        )
    ):
        raise ValueError("method_work_packet_snapshot_binding_mismatch")
    data_payload = load_json_artifact(store, packet.data_ref)
    if not isinstance(data_payload, Mapping):
        raise ValueError("method_work_packet_data_payload_unavailable")
    source_slot_values: dict[str, Any] = {}
    for slot_name, field_name in packet.candidate_slot_bindings.items():
        if field_name not in candidate:
            raise ValueError("method_work_packet_candidate_slot_source_mismatch")
        source_slot_values[slot_name] = candidate[field_name]
    for slot_name, field_name in packet.data_slot_bindings.items():
        if field_name not in data_payload:
            raise ValueError("method_work_packet_data_slot_source_mismatch")
        source_slot_values[slot_name] = data_payload[field_name]
    if not source_slot_values:
        raise ValueError("method_work_packet_source_slot_bindings_unavailable")
    try:
        expected_input_state_fingerprints = {
            slot_name: fingerprint_method_input_value(value).model_dump(mode="json")
            for slot_name, value in sorted(source_slot_values.items())
        }
    except (TypeError, ValueError) as exc:
        raise ValueError("method_work_packet_source_slot_not_fingerprintable") from exc
    sample_count = _source_sample_count(data_payload, packet.data_slot_bindings)
    if sample_count is None or sample_count != packet.actual_sample_count:
        raise ValueError("method_work_packet_source_sample_mismatch")

    job_spec = JobSpec(
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
    if (
        JobKey.from_spec(job_spec).value != packet.method_job_key
        or fingerprint(job_spec.model_dump(mode="json", exclude_none=True))
        != packet.method_profile_fingerprint
    ):
        raise ValueError("method_work_packet_job_profile_mismatch")

    expected_result_inputs = {
        f"input:{name}": input_ref_from_artifact_ref(
            input_ref,
            role=f"input:{name}",
        )
        for name, input_ref in job_spec.input_refs.items()
    }
    result_manifest = store.get_manifest(packet.method_result_ref)
    result_inputs = {item.role: item for item in result_manifest.inputs}
    if (
        not result_manifest.kind.startswith("scientist.method_result.")
        or len(result_manifest.inputs) != len(expected_result_inputs)
        or result_inputs != expected_result_inputs
    ):
        raise ValueError("method_work_packet_result_lineage_mismatch")

    evidence_manifest = store.get_manifest(packet.method_evidence_ref)
    evidence_payload = load_json_artifact(store, packet.method_evidence_ref)
    if not isinstance(evidence_payload, Mapping):
        raise ValueError("method_work_packet_evidence_binding_mismatch")
    try:
        evidence_result_ref = ArtifactRef.model_validate(evidence_payload.get("method_result_ref"))
    except (TypeError, ValueError, ValidationError) as exc:
        raise ValueError("method_work_packet_evidence_binding_mismatch") from exc
    if (
        evidence_manifest.kind != "scientist.method_evidence"
        or len(evidence_manifest.inputs) != 1
        or evidence_manifest.inputs[0]
        != input_ref_from_artifact_ref(packet.method_result_ref, role="method_result")
        or evidence_result_ref != packet.method_result_ref
        or evidence_payload.get("authority_purpose") != "method_execution"
        or evidence_payload.get("result_ref") != str(packet.method_result_ref.artifact_id)
        or evidence_payload.get("method_fqn") != packet.method_fqn
    ):
        raise ValueError("method_work_packet_evidence_binding_mismatch")
    raw_dispatch_binding = evidence_payload.get("method_dispatch_binding")
    if evidence_payload.get("method_dispatch_binding_status") != "recomputed" or not isinstance(
        raw_dispatch_binding, Mapping
    ):
        raise ValueError("method_work_packet_dispatch_binding_unavailable")
    try:
        dispatch_binding = MethodDispatchBinding.model_validate(raw_dispatch_binding)
    except (TypeError, ValueError, ValidationError) as exc:
        raise ValueError("method_work_packet_dispatch_binding_invalid") from exc
    expected_dispatch_input_refs = job_spec.input_refs
    selected_input_manifests = {
        name: store.get_manifest(input_ref) for name, input_ref in job_spec.input_refs.items()
    }
    expected_dispatch_input_schemas = {
        name: manifest.artifact_schema for name, manifest in selected_input_manifests.items()
    }
    if (
        dispatch_binding.method_fqn != packet.method_fqn
        or dispatch_binding.method_version != packet.method_version
        or dispatch_binding.method_seed != packet.method_seed
        or dispatch_binding.method_params_fingerprint
        != fingerprint(packet.configured_method_params)
        or dispatch_binding.input_refs != expected_dispatch_input_refs
        or dispatch_binding.input_schemas != expected_dispatch_input_schemas
        or {
            slot_name: value.model_dump(mode="json")
            for slot_name, value in dispatch_binding.input_state_fingerprints.items()
        }
        != expected_input_state_fingerprints
    ):
        raise ValueError("method_work_packet_dispatch_binding_mismatch")

    method_result = load_json_artifact(store, packet.method_result_ref)
    if not isinstance(method_result, Mapping) or not isinstance(
        method_result.get("result"), Mapping
    ):
        raise ValueError("method_work_packet_result_payload_unavailable")
    result_body = method_result["result"]
    from polisyos.foundry.methods.catalog.causal.ci_backends import BootstrapExecutionWork

    observed_work = BootstrapExecutionWork.model_validate(result_body.get("bootstrap_execution"))
    packet_work = BootstrapExecutionWork.model_validate(packet.bootstrap_execution)
    raw_n_obs = result_body.get("n_obs")
    effective_config = result_body.get("nuisance_config")
    if (
        observed_work != packet_work
        or isinstance(raw_n_obs, bool)
        or raw_n_obs != packet.actual_sample_count
        or not isinstance(effective_config, Mapping)
        or dict(effective_config) != packet.effective_method_config
    ):
        raise ValueError("method_work_packet_result_measurement_mismatch")
    return packet


class SearchLoopRunner:
    """Search loop runner public type."""

    def __init__(
        self,
        *,
        store: FileSystemCAS | None = None,
        registry: ChampionRegistry | None = None,
    ) -> None:
        self._store = store or default_store()
        self._registry = registry or ChampionRegistry(store=self._store)

    def run(
        self,
        spec: SearchLoopSpec,
        *,
        suite_ref: ArtifactRef,
        initial_candidate: MutationArtifact | dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        max_iterations: int = 10,
        scheduler: Any | None = None,
        dedup: Any | None = None,
        warm_start_bridge: Any | None = None,
        warm_start_fingerprint: Any | None = None,
    ) -> SearchResult:
        del scheduler  # reserved for future Hyperband integration
        generator = spec.candidate_generator
        if generator is None:
            raise ValueError(f"Search loop '{spec.loop_id}' is missing a candidate generator")
        search_context = dict(context or {})
        runtime_context = dict(search_context)
        runtime_context.setdefault("run_id", f"search-run:{uuid4().hex}")
        set_search_run_context = getattr(generator, "set_search_run_context", None)
        if callable(set_search_run_context):
            set_search_run_context(search_context)
        if warm_start_bridge is not None:
            if warm_start_fingerprint is None:
                raise ValueError("warm_start_fingerprint is required with a warm-start bridge")
            warm_start_evaluations = warm_start_bridge.load_warm_start(warm_start_fingerprint)
            contextual_warm_start = getattr(generator, "warm_start_for_context", None)
            if callable(contextual_warm_start):
                contextual_warm_start(
                    warm_start_evaluations,
                    context=search_context,
                )
            else:
                warm_start = getattr(generator, "warm_start", None)
                if not callable(warm_start):
                    raise TypeError("candidate generator does not accept warm-start evaluations")
                warm_start(warm_start_evaluations)
        objective = CompositeObjective([_AutotuneObjective(spec.promotion_policy)])
        controller = SearchController(
            config=SearchConfig(
                stopping=MaxIterations(max_iterations),
                objective=objective,
                enable_stage_a=False,
            ),
            candidate_generator=generator,
            stage_a_evaluator=lambda candidate, ctx: (0.0, True),
            stage_b_evaluator=lambda candidate, ctx: self._evaluate_candidate(
                spec,
                suite_ref=suite_ref,
                candidate_payload=candidate,
                context=ctx,
            ),
        )
        initial_payload = (
            initial_candidate.model_dump(mode="json")
            if isinstance(initial_candidate, BaseModel)
            else initial_candidate
        )
        from polisyos.scientist.methods.search.service import _NativeSearchServiceDriver

        return _NativeSearchServiceDriver(controller).run_search(
            initial_context=runtime_context,
            initial_candidate=initial_payload,
        )

    def _evaluate_candidate(
        self,
        spec: SearchLoopSpec,
        *,
        suite_ref: ArtifactRef,
        candidate_payload: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        codec = spec.mutation_codec
        if codec is None:
            raise ValueError(f"Search loop '{spec.loop_id}' is missing a mutation codec")
        projected_payload = dict(candidate_payload)
        generation_metadata = projected_payload.pop("_strategy_metadata", None)
        if (
            isinstance(codec, PydanticMutationCodec)
            and "semantic" not in codec._model_cls.model_fields
        ):
            projected_payload.pop("semantic", None)
        candidate = codec.decode(projected_payload)
        candidate_ref = persist_mutation_artifact(
            self._store,
            cast("MutationArtifact", candidate),
            inputs=[InputRef(artifact_id=suite_ref.artifact_id, role="benchmark_suite")],
        )
        evaluation_id = f"search-evaluation:{uuid4().hex}"
        evaluation_attempt_id = f"search-attempt:{uuid4().hex}"
        evaluation = spec.benchmark_evaluator.evaluate(
            candidate_ref,
            suite_ref,
            {
                **dict(context),
                "store": self._store,
                "registry": self._registry,
                "policy": spec.promotion_policy,
                "loop_id": spec.loop_id,
                "candidate_generation_metadata": generation_metadata,
                "evaluation_id": evaluation_id,
                "evaluation_attempt_id": evaluation_attempt_id,
            },
        )
        source_profile: BayesianSourceProfile | None = None
        if isinstance(generation_metadata, Mapping):
            raw_profile = generation_metadata.get("warm_start_compatibility")
            if isinstance(raw_profile, Mapping):
                try:
                    source_profile = BayesianSourceProfile.model_validate(raw_profile)
                except ValidationError:
                    source_profile = None
        if source_profile is not None:
            if evaluation.search_source_profile is None:
                evaluation = evaluation.model_copy(update={"search_source_profile": source_profile})
            elif evaluation.search_source_profile != source_profile:
                evaluation = evaluation.model_copy(
                    update={
                        "search_source_profile": None,
                        "promotable": False,
                        "status": "source_profile_conflict",
                    }
                )
        if (
            evaluation.execution_work_packet_status == "available"
            and evaluation.execution_work_packet_ref is not None
        ):
            try:
                work_packet = read_method_job_execution_work_packet(
                    self._store,
                    evaluation.execution_work_packet_ref,
                )
                expected_snapshot = context.get("data_snapshot_ref")
                if expected_snapshot is None:
                    raise ValueError("work_packet_context_snapshot_unavailable")
                if not isinstance(expected_snapshot, ArtifactRef):
                    expected_snapshot = ArtifactRef.model_validate(expected_snapshot)
                if (
                    work_packet.candidate_ref != candidate_ref
                    or work_packet.method_result_ref != evaluation.method_result_ref
                    or work_packet.method_evidence_ref != evaluation.method_evidence_ref
                    or work_packet.method_job_key != evaluation.method_job_key
                    or work_packet.run_id != str(context.get("run_id") or "")
                    or work_packet.evaluation_id != evaluation_id
                    or work_packet.evaluation_attempt_id != evaluation_attempt_id
                    or (
                        expected_snapshot is not None
                        and work_packet.data_snapshot_ref != expected_snapshot
                    )
                ):
                    raise ValueError("work_packet_evaluation_binding_mismatch")
            except (KeyError, OSError, RuntimeError, TypeError, ValueError, ValidationError):
                evaluation = evaluation.model_copy(
                    update={
                        "execution_work_packet_status": "rejected",
                        "execution_work_packet_note": "search_evaluation_work_packet_binding_mismatch",
                    }
                )
        primary_value = evaluation.primary_value(
            split=spec.promotion_policy.compare_split,
            metric=spec.promotion_policy.primary_metric,
        )
        if primary_value is None or not isfinite(primary_value):
            selection_metrics = {
                name: value
                for name, value in evaluation.selection_metrics.items()
                if isfinite(value)
            }
            holdout_metrics = {
                name: value for name, value in evaluation.holdout_metrics.items() if isfinite(value)
            }
            evaluation = evaluation.model_copy(
                update={
                    "selection_metrics": selection_metrics,
                    "holdout_metrics": holdout_metrics,
                    "promotable": False,
                    "status": "metric_unavailable",
                    "guardrails": {
                        **evaluation.guardrails,
                        "primary_metric_available": False,
                    },
                }
            )
        evaluation_ref = persist_benchmark_evaluation(
            self._store,
            evaluation,
            inputs=[InputRef(artifact_id=suite_ref.artifact_id, role="benchmark_suite")],
        )
        decision = self._registry.consider_promotion(
            spec.loop_id,
            candidate_ref,
            evaluation_ref,
            spec.promotion_policy,
            suite_ref=suite_ref,
        )
        metrics = evaluation.metrics_for_split(spec.promotion_policy.compare_split)
        primary_value = metrics.get(spec.promotion_policy.primary_metric)
        provenance_ref = evaluation.method_result_ref or evaluation_ref
        simulation_results: dict[str, Any] = {
            "evaluation_ref": str(evaluation_ref.artifact_id),
            "candidate_ref": str(candidate_ref.artifact_id),
        }
        if evaluation.execution_work_packet_ref is not None:
            simulation_results["execution_work_packet_ref"] = str(
                evaluation.execution_work_packet_ref.artifact_id
            )
        if primary_value is not None and isfinite(primary_value):
            simulation_results[spec.promotion_policy.primary_metric] = primary_value
        return {
            "simulation_results": simulation_results,
            "feedback": {
                "verdict": "APPROVE" if evaluation.promotable else "REJECT",
                "promotion_decision": decision.model_dump(mode="json"),
                "guardrails": dict(evaluation.guardrails),
                "status": evaluation.status,
                "execution_work_packet_status": evaluation.execution_work_packet_status,
            },
            "metadata": {
                "evaluation_id": str(evaluation_ref.artifact_id),
                "provenance_ref": str(provenance_ref.artifact_id),
                "split": evaluation.resolved_runtime_split_type().value,
            },
        }


__all__ = [
    "ChampionBackedRuntimeLoader",
    "MethodJobBenchmarkEvaluator",
    "PydanticMutationCodec",
    "SearchLoopRunner",
    "SearchRunArtifacts",
    "SequenceCandidateGenerator",
    "read_method_job_execution_work_packet",
    "seed_loop_baseline",
]
