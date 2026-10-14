"""Public autotune runtime module API."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from math import isclose, isfinite
from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from polisyos.core.artifacts.manifest import (
    ArtifactManifest,
    ArtifactRef,
    InputRef,
    ProducerInfo,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec, fingerprint
from polisyos.core.contracts import DataSnapshot
from polisyos.scientist.compute.job_spec import JobKey, JobSpec
from polisyos.scientist.methods.search.controller import (
    SearchConfig,
    SearchController,
    SearchResult,
    TracedLLMCandidateGenerator,
)
from polisyos.scientist.methods.search.objective import (
    BaseObjective,
    CompositeObjective,
    OptimizationDirection,
)
from polisyos.scientist.methods.search.stopping import MaxIterations

from .models import (
    _BENCHMARK_EVALUATION_SCHEMA_NAME,
    BayesianSourceProfile,
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSuite,
    ChampionPointer,
    MetricDirection,
    MutationArtifact,
    PromotionPolicy,
    PydanticMutationCodec,
    SearchGPFitBasis,
    SearchGPFitBound,
    SearchGPProposalUncertainty,
    SearchLoopSpec,
    SearchMethodRunProfile,
    _benchmark_evaluation_artifact_kind,
    _benchmark_evaluation_input_refs,
    _search_method_parameters_match_run_profile,
    default_store,
    load_json_artifact,
    load_model_artifact,
    persist_benchmark_evaluation,
    persist_mutation_artifact,
)
from .registry import ChampionRegistry

if TYPE_CHECKING:
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        BudgetLedgerProducerRunBinding,
    )
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware

    from .execution_work import MethodJobExecutionWorkPacket

ModelT = TypeVar("ModelT", bound=MutationArtifact)


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
        search_parameter_bindings: Mapping[str, str] | None = None,
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
        resolved_method_params = dict(method_params or {})
        resolved_search_bindings = dict(search_parameter_bindings or {})
        if any(
            not isinstance(search_name, str)
            or not search_name.strip()
            or not isinstance(method_name, str)
            or not method_name.strip()
            for search_name, method_name in resolved_search_bindings.items()
        ):
            raise TypeError("search_parameter_bindings must map non-empty names to non-empty names")
        method_parameter_names = list(resolved_search_bindings.values())
        if len(set(method_parameter_names)) != len(method_parameter_names):
            raise ValueError("each dynamic MethodJob parameter can have one SearchSpace binding")
        if set(method_parameter_names) & set(resolved_method_params):
            raise ValueError("bound MethodJob parameters must not also appear in method_params")
        self._method_fqn = method_fqn
        self._method_version = method_version
        self._candidate_input_bindings = dict(candidate_input_bindings)
        self._data_snapshot_bindings = resolved_data_bindings
        self._method_params = resolved_method_params
        self._search_parameter_bindings = resolved_search_bindings
        self._split = split
        self._seed = int(seed)

    @property
    def requires_source_bound_execution_work_packet(self) -> bool:
        """Require admission whenever the MethodJob consumes DataSnapshot slots."""
        return bool(self._data_snapshot_bindings)

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
        search_method_run_profile = _search_method_run_profile_from_context(context)
        configured_method_params = dict(self._method_params)
        search_parameter_values: dict[str, Any] = {}
        if self._search_parameter_bindings:
            data_sample_count = _source_sample_count(data_payload, self._data_snapshot_bindings)
            if not _search_method_run_profile_matches_evaluator(
                profile=search_method_run_profile,
                evaluator=self,
                suite_ref=suite_ref,
                policy=policy,
                loop_id=loop_id,
                method_seed=configured_seed,
                data_snapshot_ref=data_snapshot_ref,
                data_ref=data_ref,
                data_sample_count=data_sample_count,
            ):
                return self._empty_evaluation(
                    loop_id=loop_id,
                    suite=suite,
                    candidate_ref=candidate_ref,
                    split=self._split,
                    status="search_parameter_basis_unavailable",
                )
            if search_method_run_profile is None:
                return self._empty_evaluation(
                    loop_id=loop_id,
                    suite=suite,
                    candidate_ref=candidate_ref,
                    split=self._split,
                    status="search_parameter_basis_unavailable",
                )
            if any(name not in candidate for name in self._search_parameter_bindings):
                return self._empty_evaluation(
                    loop_id=loop_id,
                    suite=suite,
                    candidate_ref=candidate_ref,
                    split=self._split,
                    status="search_parameter_binding_rejected",
                )
            search_parameter_values = {
                name: candidate[name] for name in self._search_parameter_bindings
            }
            for search_name, method_name in self._search_parameter_bindings.items():
                configured_method_params[method_name] = candidate[search_name]
            if not _search_method_parameters_match_run_profile(
                profile=search_method_run_profile,
                candidate=candidate,
                method_params=configured_method_params,
            ):
                return self._empty_evaluation(
                    loop_id=loop_id,
                    suite=suite,
                    candidate_ref=candidate_ref,
                    split=self._split,
                    status="search_parameter_binding_rejected",
                )
        input_refs = {"candidate": candidate_ref, "benchmark_suite": suite_ref}
        if data_snapshot_ref is not None and data_ref is not None:
            input_refs.update({"data_snapshot": data_snapshot_ref, "data": data_ref})
        spec = JobSpec(
            job_kind="method",
            method_fqn=self._method_fqn,
            method_version=self._method_version,
            method_params=configured_method_params,
            input_refs=input_refs,
            seed=configured_seed,
        )
        method_request_basis = {
            "schema_version": "2" if search_method_run_profile is not None else "1",
            "job_spec": spec.model_dump(mode="json", exclude_none=True),
            "candidate_ref": candidate_ref.model_dump(mode="json"),
            "suite_ref": suite_ref.model_dump(mode="json"),
            "method_state_fingerprint": _search_source_fingerprint(method_state),
            "candidate_input_bindings": dict(self._candidate_input_bindings),
            "data_snapshot_bindings": dict(self._data_snapshot_bindings),
            "primary_metric": policy.primary_metric,
            "direction": policy.direction.value,
            "split": self._split.value,
            "unit": policy.unit,
        }
        if search_method_run_profile is not None:
            method_request_basis.update(
                {
                    "search_method_run_profile": search_method_run_profile.model_dump(
                        mode="json", exclude_none=True
                    ),
                    "search_parameter_values": search_parameter_values,
                }
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
            "method_request_basis": method_request_basis,
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
                search_method_run_profile=search_method_run_profile,
                search_parameter_values=search_parameter_values,
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
        search_method_run_profile: SearchMethodRunProfile | None,
        search_parameter_values: Mapping[str, Any],
    ) -> tuple[ArtifactRef | None, str, str | None]:
        """Persist and fresh-read an explicitly diagnostic source-bound work packet."""
        from .execution_work import (
            MethodJobExecutionWorkPacket,
            _fingerprint_method_request_material,
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
            method_profile_fingerprint = _fingerprint_method_request_material(
                job_spec.model_dump(mode="json", exclude_none=True)
            )
        except (OverflowError, TypeError, ValueError):
            return None, "rejected", "method_work_packet_request_profile_unfingerprintable"

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
                schema_version=("1.3" if search_method_run_profile is not None else "1.2"),
                configured_method_params=dict(job_spec.method_params),
                effective_method_config=dict(effective_config),
                candidate_slot_bindings=dict(self._candidate_input_bindings),
                data_slot_bindings=dict(self._data_snapshot_bindings),
                search_method_run_profile=search_method_run_profile,
                search_parameter_values=dict(search_parameter_values),
                method_profile_fingerprint=method_profile_fingerprint,
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
        _fingerprint_method_request_material,
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
        or packet_manifest.artifact_schema.version not in {"1.2", "1.3"}
    ):
        raise ValueError("method_work_packet_manifest_mismatch")
    packet = load_model_artifact(store, ref, MethodJobExecutionWorkPacket)
    if not isinstance(packet, MethodJobExecutionWorkPacket):
        raise TypeError("method_work_packet_payload_unavailable")
    if packet_manifest.artifact_schema.version != packet.schema_version:
        raise ValueError("method_work_packet_manifest_mismatch")

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
    if packet.schema_version == "1.3":
        profile = packet.search_method_run_profile
        if (
            profile is None
            or profile.loop_id != candidate.get("loop_id")
            or profile.suite_ref != packet.benchmark_suite_ref
            or profile.method_fqn != packet.method_fqn
            or profile.method_version != packet.method_version
            or profile.method_seed != packet.method_seed
            or profile.data_snapshot_ref != packet.data_snapshot_ref
            or profile.data_ref != packet.data_ref
            or profile.data_sample_count != packet.actual_sample_count
            or profile.candidate_input_bindings != packet.candidate_slot_bindings
            or profile.data_snapshot_bindings != packet.data_slot_bindings
        ):
            raise ValueError("method_work_packet_search_profile_mismatch")
        actual_search_values = {
            name: candidate[name] for name in profile.search_parameter_bindings if name in candidate
        }
        if (
            set(actual_search_values) != set(profile.search_parameter_bindings)
            or actual_search_values != packet.search_parameter_values
        ):
            raise ValueError("method_work_packet_search_parameter_source_mismatch")
        if not _search_method_parameters_match_run_profile(
            profile=profile,
            candidate=candidate,
            method_params=packet.configured_method_params,
        ):
            raise ValueError("method_work_packet_search_parameter_binding_mismatch")
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
    try:
        observed_method_profile_fingerprint = _fingerprint_method_request_material(
            job_spec.model_dump(mode="json", exclude_none=True)
        )
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError("method_work_packet_request_profile_unfingerprintable") from exc
    if (
        JobKey.from_spec(job_spec).value != packet.method_job_key
        or observed_method_profile_fingerprint != packet.method_profile_fingerprint
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
    try:
        expected_method_params_fingerprint = _fingerprint_method_request_material(
            packet.configured_method_params
        )
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError("method_work_packet_dispatch_params_unfingerprintable") from exc
    if (
        dispatch_binding.method_fqn != packet.method_fqn
        or dispatch_binding.method_version != packet.method_version
        or dispatch_binding.method_seed != packet.method_seed
        or dispatch_binding.method_params_fingerprint != expected_method_params_fingerprint
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


def _search_work_packet_admission_failure(
    *,
    store: FileSystemCAS,
    evaluation: BenchmarkEvaluation,
    evaluator: MethodJobBenchmarkEvaluator | None,
    candidate_ref: ArtifactRef,
    suite_ref: ArtifactRef,
    policy: PromotionPolicy,
    context: Mapping[str, Any],
    run_id: str,
    evaluation_id: str,
    evaluation_attempt_id: str,
) -> str | None:
    """Reconcile a claimed Search score with its current source-bound MethodJob."""
    if (
        evaluation.execution_work_packet_status != "available"
        or evaluation.execution_work_packet_ref is None
    ):
        return evaluation.execution_work_packet_note or "search_work_packet_not_available"
    if (
        evaluation.candidate_ref != candidate_ref
        or evaluation.loop_id != policy.loop_id
        or evaluation.method_result_ref is None
        or evaluation.method_evidence_ref is None
        or evaluation.method_job_key is None
    ):
        return "search_work_packet_evaluation_binding_mismatch"

    try:
        work_packet = read_method_job_execution_work_packet(
            store, evaluation.execution_work_packet_ref
        )
        raw_snapshot_ref = context.get("data_snapshot_ref")
        if raw_snapshot_ref is None:
            return "search_work_packet_context_snapshot_unavailable"
        expected_snapshot_ref = (
            raw_snapshot_ref
            if isinstance(raw_snapshot_ref, ArtifactRef)
            else ArtifactRef.model_validate(raw_snapshot_ref)
        )
        suite = load_model_artifact(store, suite_ref, BenchmarkSuite)
        if not isinstance(suite, BenchmarkSuite):
            return "search_work_packet_suite_unavailable"
        if (
            work_packet.candidate_ref != candidate_ref
            or work_packet.benchmark_suite_ref != suite_ref
            or work_packet.method_result_ref != evaluation.method_result_ref
            or work_packet.method_evidence_ref != evaluation.method_evidence_ref
            or work_packet.method_job_key != evaluation.method_job_key
            or work_packet.run_id != run_id
            or work_packet.evaluation_id != evaluation_id
            or work_packet.evaluation_attempt_id != evaluation_attempt_id
            or work_packet.data_snapshot_ref != expected_snapshot_ref
            or evaluation.suite_id != suite.suite_id
            or evaluation.suite_version != suite.suite_version
        ):
            return "search_work_packet_evaluation_binding_mismatch"

        if evaluator is not None:
            expected_seed = context.get("method_job_seed", evaluator._seed)
            if isinstance(expected_seed, bool) or not isinstance(expected_seed, int):
                return "search_work_packet_request_seed_unavailable"
            if (
                work_packet.method_fqn != evaluator._method_fqn
                or work_packet.method_version != evaluator._method_version
                or work_packet.method_seed != expected_seed
                or work_packet.candidate_slot_bindings != evaluator._candidate_input_bindings
                or work_packet.data_slot_bindings != evaluator._data_snapshot_bindings
            ):
                return "search_work_packet_method_request_mismatch"
            if evaluator._search_parameter_bindings:
                candidate_payload = load_json_artifact(store, candidate_ref)
                run_profile = _search_method_run_profile_from_context(context)
                if (
                    not isinstance(candidate_payload, Mapping)
                    or run_profile is None
                    or work_packet.search_method_run_profile != run_profile
                    or not _search_method_run_profile_matches_evaluator(
                        profile=run_profile,
                        evaluator=evaluator,
                        suite_ref=suite_ref,
                        policy=policy,
                        loop_id=policy.loop_id,
                        method_seed=expected_seed,
                        data_snapshot_ref=expected_snapshot_ref,
                        data_ref=work_packet.data_ref,
                        data_sample_count=work_packet.actual_sample_count,
                    )
                    or not _search_method_parameters_match_run_profile(
                        profile=run_profile,
                        candidate=candidate_payload,
                        method_params=work_packet.configured_method_params,
                    )
                ):
                    return "search_work_packet_method_request_mismatch"
            elif (
                work_packet.configured_method_params != evaluator._method_params
                or work_packet.search_method_run_profile is not None
                or work_packet.search_parameter_values
            ):
                return "search_work_packet_method_request_mismatch"

        method_output = load_json_artifact(store, work_packet.method_result_ref)
        if not isinstance(method_output, Mapping):
            return "search_work_packet_method_result_unavailable"
        metric_output = method_output.get("result")
        metric_source = metric_output if isinstance(metric_output, Mapping) else method_output
        reported_value = evaluation.primary_value(
            split=policy.compare_split,
            metric=policy.primary_metric,
        )
        if reported_value is not None and isfinite(reported_value):
            raw_metric = metric_source.get(policy.primary_metric)
            source_units = metric_source.get("metric_units")
            source_unit = (
                source_units.get(policy.primary_metric)
                if isinstance(source_units, Mapping)
                else None
            )
            if isinstance(raw_metric, bool) or raw_metric is None:
                return "search_work_packet_metric_binding_mismatch"
            actual_value = float(raw_metric)
            if (
                not isfinite(actual_value)
                or actual_value != reported_value
                or (policy.unit is not None and source_unit != policy.unit)
                or evaluation.metadata.get("metric_unit") != source_unit
            ):
                return "search_work_packet_metric_binding_mismatch"
    except (
        KeyError,
        OSError,
        OverflowError,
        RuntimeError,
        TypeError,
        ValueError,
        ValidationError,
    ):
        return "search_work_packet_cas_admission_failed"
    return None


_SEARCH_SOURCE_RECEIPT_KEY = "search_source_profile_receipt"
_SEARCH_SOURCE_CANON_SPEC = CanonSpec(forbid_floats=False, forbid_nan_inf=False)


def _search_source_fingerprint(value: Any) -> str | None:
    """Return a canonical fingerprint for candidate-grade MethodJob request values."""
    try:
        return fingerprint(value, canon_spec=_SEARCH_SOURCE_CANON_SPEC)
    except (TypeError, ValueError, OverflowError):
        return None


def _search_source_manifest_schema_matches(
    manifest: object,
    *,
    name: str,
    version: str | None = None,
) -> bool:
    """Match a typed Core manifest schema, returning false for absent or malformed metadata."""
    if not isinstance(manifest, ArtifactManifest):
        return False
    schema = manifest.artifact_schema
    return (
        isinstance(schema, SchemaInfo)
        and schema.name == name
        and (version is None or schema.version == version)
    )


def _search_source_manifest_input_matches(
    manifest: Any,
    role: str,
    ref: ArtifactRef,
    *,
    require_profile: bool = True,
) -> bool:
    return any(
        item.role == role
        and item.artifact_id == ref.artifact_id
        and (not require_profile or item.manifest_profile_sha256 == ref.manifest_profile_sha256)
        for item in manifest.inputs
    )


def _search_method_run_profile_from_context(
    context: Mapping[str, Any],
) -> SearchMethodRunProfile | None:
    """Parse the runner-owned Search → MethodJob basis without trusting caller shape."""
    raw_profile = context.get("_search_method_run_profile")
    if isinstance(raw_profile, SearchMethodRunProfile):
        return raw_profile
    if not isinstance(raw_profile, Mapping):
        return None
    try:
        return SearchMethodRunProfile.model_validate(raw_profile)
    except (TypeError, ValueError, ValidationError):
        return None


def _search_method_run_profile_matches_evaluator(
    *,
    profile: SearchMethodRunProfile | None,
    evaluator: MethodJobBenchmarkEvaluator,
    suite_ref: ArtifactRef,
    policy: PromotionPolicy,
    loop_id: str,
    method_seed: int,
    data_snapshot_ref: ArtifactRef | None,
    data_ref: ArtifactRef | None,
    data_sample_count: int | None,
) -> bool:
    """Reconcile a run profile with the evaluator's fixed request and exact data basis."""
    return (
        profile is not None
        and profile.schema_version == "2"
        and profile.loop_id == loop_id
        and profile.suite_ref == suite_ref
        and profile.method_fqn == evaluator._method_fqn
        and profile.method_version == evaluator._method_version
        and profile.method_params_fingerprint
        == _search_source_fingerprint(evaluator._method_params)
        and profile.candidate_input_bindings == evaluator._candidate_input_bindings
        and profile.data_snapshot_bindings == evaluator._data_snapshot_bindings
        and profile.search_parameter_bindings == evaluator._search_parameter_bindings
        and profile.data_snapshot_ref == data_snapshot_ref
        and profile.data_ref == data_ref
        and profile.data_sample_count == data_sample_count
        and profile.method_seed == method_seed
        and profile.primary_metric == policy.primary_metric
        and profile.direction == policy.direction.value
        and profile.split == evaluator._split.value
        and profile.unit == policy.unit
    )


def _build_search_parameter_profile(
    *,
    evaluator: MethodJobBenchmarkEvaluator,
    generator: Any,
) -> tuple[list[SearchGPFitBound], str] | None:
    """Resolve declared SearchSpace dimensions to dynamic parameters of the current ABI."""
    bindings = evaluator._search_parameter_bindings
    if not bindings:
        return [], ""
    search_space = getattr(generator, "_search_space", None)
    raw_bounds = getattr(search_space, "bounds", None)
    if not isinstance(raw_bounds, list) or not raw_bounds:
        return None
    bounds_by_name = {getattr(bound, "name", None): bound for bound in raw_bounds}
    if len(bounds_by_name) != len(raw_bounds) or not set(bindings).issubset(bounds_by_name):
        return None
    if set(bindings.values()) & set(evaluator._method_params):
        return None
    try:
        from polisyos.foundry.methods import MethodRegistry

        signature = MethodRegistry.get_instance().get_signature(evaluator._method_fqn)
        if (
            signature is None
            or signature.fqn != evaluator._method_fqn
            or signature.version != evaluator._method_version
        ):
            return None
        parameters = {parameter.name: parameter for parameter in signature.parameters}
        profile_bounds: list[SearchGPFitBound] = []
        for search_name, method_name in sorted(bindings.items()):
            bound = bounds_by_name[search_name]
            parameter = parameters.get(method_name)
            dtype = getattr(getattr(bound, "dtype", None), "value", None)
            lower = getattr(bound, "lower", None)
            upper = getattr(bound, "upper", None)
            if (
                parameter is None
                or parameter.is_static
                or type(parameter.default) not in {int, float}
                or type(lower) not in {int, float}
                or type(upper) not in {int, float}
                or not isfinite(float(lower))
                or not isfinite(float(upper))
                or lower >= upper
                or getattr(bound, "categories", None) is not None
            ):
                return None
            if type(parameter.default) is int:
                if (
                    dtype != "integer"
                    or not float(lower).is_integer()
                    or not float(upper).is_integer()
                ):
                    return None
            elif dtype not in {"continuous", "log_continuous"}:
                return None
            declared_lower, declared_upper = parameter.bounds
            if (declared_lower is not None and lower < declared_lower) or (
                declared_upper is not None and upper > declared_upper
            ):
                return None
            profile_bounds.append(
                SearchGPFitBound(
                    name=search_name,
                    lower=float(lower),
                    upper=float(upper),
                    dtype=dtype,
                    log_scale=bool(getattr(bound, "log_scale", False)),
                    categories=None,
                )
            )
        return profile_bounds, signature.abi_digest()
    except (AttributeError, TypeError, ValueError, OverflowError, ValidationError):
        return None


def _build_search_method_run_profile(
    *,
    store: FileSystemCAS,
    generator: Any,
    spec: SearchLoopSpec,
    suite_ref: ArtifactRef,
    context: Mapping[str, Any],
) -> SearchMethodRunProfile | None:
    """Resolve the exact method, data, objective, and search basis for one run."""
    from polisyos.core.artifacts import load_core_json_artifact

    evaluator = spec.benchmark_evaluator
    search_space = getattr(generator, "_search_space", None)
    context_fingerprint = getattr(generator, "_search_run_context_fingerprint", None)
    objective_fn = getattr(generator, "_objective_profile_fingerprint", None)
    if (
        type(evaluator) is not MethodJobBenchmarkEvaluator
        or search_space is None
        or not callable(objective_fn)
        or not isinstance(context_fingerprint, str)
        or not context_fingerprint
    ):
        return None
    search_space_fingerprint = search_space._native.sobol_space_fingerprint()
    objective_fingerprint = objective_fn()
    method_seed = context.get("method_job_seed", evaluator._seed)
    if (
        isinstance(method_seed, bool)
        or not isinstance(method_seed, int)
        or objective_fingerprint is None
    ):
        return None
    data_snapshot_ref: ArtifactRef | None = None
    data_ref: ArtifactRef | None = None
    data_sample_count: int | None = None
    if evaluator._data_snapshot_bindings:
        try:
            data_snapshot_ref = ArtifactRef.model_validate(context.get("data_snapshot_ref"))
            if data_snapshot_ref.manifest_profile_sha256 is None:
                return None
            snapshot_manifest = store.get_manifest(data_snapshot_ref)
            snapshot = DataSnapshot.model_validate(
                load_core_json_artifact(store, data_snapshot_ref)
            )
            data_ref = ArtifactRef.model_validate(snapshot.data_ref)
            if data_ref.manifest_profile_sha256 is None:
                return None
            if (
                snapshot_manifest.kind != "fabric.data_snapshot"
                or not _search_source_manifest_input_matches(
                    snapshot_manifest, "data_ref", data_ref, require_profile=True
                )
            ):
                return None
            data_payload = load_core_json_artifact(store, data_ref)
            if not isinstance(data_payload, Mapping):
                return None
            data_sample_count = _source_sample_count(
                data_payload, evaluator._data_snapshot_bindings
            )
            if data_sample_count is None:
                return None
        except (KeyError, OSError, RuntimeError, TypeError, ValueError, ValidationError):
            return None
    method_params_fingerprint = _search_source_fingerprint(dict(evaluator._method_params))
    if method_params_fingerprint is None:
        return None
    parameter_profile = _build_search_parameter_profile(evaluator=evaluator, generator=generator)
    if parameter_profile is None:
        return None
    parameter_bounds, method_signature_abi_digest = parameter_profile
    has_parameter_bindings = bool(evaluator._search_parameter_bindings)
    try:
        return SearchMethodRunProfile(
            schema_version="2" if has_parameter_bindings else "1",
            loop_id=spec.loop_id,
            suite_ref=suite_ref,
            method_fqn=evaluator._method_fqn,
            method_version=evaluator._method_version,
            method_params_fingerprint=method_params_fingerprint,
            candidate_input_bindings=dict(evaluator._candidate_input_bindings),
            data_snapshot_bindings=dict(evaluator._data_snapshot_bindings),
            search_parameter_bindings=dict(evaluator._search_parameter_bindings),
            search_parameter_bounds=parameter_bounds,
            method_signature_abi_digest=(
                method_signature_abi_digest if has_parameter_bindings else None
            ),
            data_snapshot_ref=data_snapshot_ref,
            data_ref=data_ref,
            data_sample_count=data_sample_count,
            method_seed=method_seed,
            primary_metric=spec.promotion_policy.primary_metric,
            direction=spec.promotion_policy.direction.value,
            split=evaluator._split.value,
            unit=spec.promotion_policy.unit,
            search_space_fingerprint=search_space_fingerprint,
            context_fingerprint=context_fingerprint,
            objective_fingerprint=objective_fingerprint,
        )
    except (TypeError, ValueError, ValidationError):
        return None


def _persist_search_benchmark_evaluation(
    store: FileSystemCAS,
    evaluation: BenchmarkEvaluation,
    *,
    suite_ref: ArtifactRef,
) -> ArtifactRef:
    """Persist an evaluation with its exact selected producer source edges."""
    return store.put_json(
        evaluation,
        ArtifactWriteOptions(
            kind=_benchmark_evaluation_artifact_kind(evaluation.loop_id),
            media_type="application/json",
            schema=SchemaInfo(
                name=_BENCHMARK_EVALUATION_SCHEMA_NAME,
                version=evaluation.suite_version,
            ),
            producer=ProducerInfo(
                component="polisyos.scientist.methods.autotune.benchmark_evaluator",
                version="2.0",
            ),
            inputs=_benchmark_evaluation_input_refs(evaluation, suite_ref=suite_ref),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def _verify_search_source_profile_receipt(
    *,
    store: Any,
    evaluation_ref: Any,
    expected_receipt: Any = None,
    expected_profile: Any = None,
    expected_params: Any = None,
    expected_scalar: Any = None,
    expected_proposal_id: Any = None,
    expected_candidate_id: Any = None,
    expected_provenance_ref: Any = None,
    expected_method_run_profile: SearchMethodRunProfile | None = None,
    require_warm_start_eligible: bool = False,
    _skip_fit_recomputation: bool = False,
) -> tuple[BayesianSourceProfile, dict[str, Any], ArtifactRef] | None:
    """Fresh-read the complete candidate-grade Search → MethodJob → CAS source chain."""
    from polisyos.core.artifacts import load_core_json_artifact

    if not isinstance(store, FileSystemCAS):
        return None
    try:
        exact_evaluation_ref = ArtifactRef.model_validate(evaluation_ref)
        reader = FileSystemCAS(store.root)
        evaluation_manifest = reader.get_manifest(exact_evaluation_ref)
        if not _search_source_manifest_schema_matches(
            evaluation_manifest,
            name="polisyos.scientist.methods.autotune.BenchmarkEvaluation",
        ):
            return None
        raw_evaluation = load_core_json_artifact(reader, exact_evaluation_ref)
        evaluation = BenchmarkEvaluation.model_validate(raw_evaluation)
        receipt_value = evaluation.metadata.get(_SEARCH_SOURCE_RECEIPT_KEY)
        if not isinstance(receipt_value, Mapping):
            return None
        receipt = dict(receipt_value)
        claimed_receipt_sha = receipt.pop("receipt_sha256", None)
        if claimed_receipt_sha != _search_source_fingerprint(receipt):
            return None
        receipt["receipt_sha256"] = claimed_receipt_sha
        if (
            receipt.get("schema_version") != "1"
            or receipt.get("authority_purpose") != "candidate_search_history_profile"
            or receipt.get("grade") != "candidate_only"
        ):
            return None
        if expected_receipt is not None and dict(expected_receipt) != receipt:
            return None
        profile_payload = receipt.get("profile")
        if not isinstance(profile_payload, Mapping):
            return None
        profile = BayesianSourceProfile.model_validate(profile_payload)
        if (
            _search_source_fingerprint(dict(profile_payload)) != receipt.get("profile_sha256")
            or evaluation.search_source_profile != profile
            or (expected_profile is not None and dict(expected_profile) != dict(profile_payload))
            or (require_warm_start_eligible and not profile.warm_start_eligible)
        ):
            return None
        if evaluation.metadata.get(_SEARCH_SOURCE_RECEIPT_KEY) != receipt:
            return None
        if evaluation.status != "measured_candidate":
            return None
        if evaluation.method_result_ref is None or evaluation.method_evidence_ref is None:
            return None

        proposal = receipt.get("proposal")
        proposal_params = proposal.get("params") if isinstance(proposal, Mapping) else None
        proposal_id = proposal.get("proposal_id") if isinstance(proposal, Mapping) else None
        if (
            not isinstance(proposal_params, Mapping)
            or not isinstance(proposal_id, str)
            or (expected_proposal_id is not None and expected_proposal_id != proposal_id)
            or (
                expected_params is not None
                and _search_source_fingerprint(dict(expected_params))
                != _search_source_fingerprint(dict(proposal_params))
            )
        ):
            return None

        candidate_ref = ArtifactRef.model_validate(receipt.get("candidate_ref"))
        suite_ref = ArtifactRef.model_validate(receipt.get("suite_ref"))
        method_result_ref = ArtifactRef.model_validate(receipt.get("method_result_ref"))
        method_evidence_ref = ArtifactRef.model_validate(receipt.get("method_evidence_ref"))
        if (
            evaluation.candidate_ref != candidate_ref
            or evaluation.method_result_ref != method_result_ref
            or evaluation.method_evidence_ref != method_evidence_ref
            or evaluation.method_job_key != receipt.get("method_job_key")
            or (
                expected_candidate_id is not None
                and expected_candidate_id != str(candidate_ref.artifact_id)
            )
            or (
                expected_provenance_ref is not None
                and expected_provenance_ref != str(method_result_ref.artifact_id)
            )
        ):
            return None
        if expected_scalar is not None and (
            not isinstance(expected_scalar, (int, float))
            or isinstance(expected_scalar, bool)
            or not isfinite(float(expected_scalar))
            or float(expected_scalar) != float(receipt.get("scalar_score", float("nan")))
        ):
            return None

        proposal_uncertainty: SearchGPProposalUncertainty | None = None
        if "proposal_uncertainty" in receipt:
            try:
                proposal_uncertainty = SearchGPProposalUncertainty.model_validate(
                    receipt["proposal_uncertainty"]
                )
            except ValidationError:
                return None
        elif require_warm_start_eligible:
            return None

        if evaluation_manifest.kind != f"scientist.autotune.{evaluation.loop_id}.evaluation":
            return None
        if not all(
            _search_source_manifest_input_matches(
                evaluation_manifest, role, ref, require_profile=False
            )
            for role, ref in (
                ("candidate", candidate_ref),
                ("benchmark_suite", suite_ref),
                ("method_result", method_result_ref),
                ("method_evidence", method_evidence_ref),
            )
        ):
            return None

        candidate_manifest = reader.get_manifest(candidate_ref)
        candidate_payload = load_core_json_artifact(reader, candidate_ref)
        if candidate_manifest.artifact_id != candidate_ref.artifact_id or not isinstance(
            candidate_payload, Mapping
        ):
            return None
        actual_proposal_params = {
            str(name): candidate_payload[name]
            for name in proposal_params
            if isinstance(name, str) and name in candidate_payload
        }
        if (
            set(actual_proposal_params) != set(proposal_params)
            or _search_source_fingerprint(actual_proposal_params)
            != _search_source_fingerprint(dict(proposal_params))
            or candidate_payload.get("loop_id") != evaluation.loop_id
        ):
            return None
        suite_manifest = reader.get_manifest(suite_ref)
        suite_payload = load_core_json_artifact(reader, suite_ref)
        suite = BenchmarkSuite.model_validate(suite_payload)
        if suite_manifest.artifact_id != suite_ref.artifact_id or (
            suite.suite_id != evaluation.suite_id or suite.suite_version != evaluation.suite_version
        ):
            return None

        basis = receipt.get("method_request_basis")
        if not isinstance(basis, Mapping) or dict(basis) != evaluation.metadata.get(
            "method_request_basis"
        ):
            return None
        if (
            basis.get("schema_version") not in {"1", "2"}
            or basis.get("candidate_ref") != candidate_ref.model_dump(mode="json")
            or basis.get("suite_ref") != suite_ref.model_dump(mode="json")
            or basis.get("primary_metric") != receipt.get("metric")
            or basis.get("direction") != receipt.get("direction")
            or basis.get("split") != receipt.get("split")
            or basis.get("unit") != receipt.get("unit")
        ):
            return None
        job_spec = JobSpec.model_validate(basis.get("job_spec"))
        if job_spec.job_kind != "method" or not job_spec.method_fqn:
            return None
        if JobKey.from_spec(job_spec).value != evaluation.method_job_key:
            return None
        if (
            job_spec.input_refs.get("candidate") != candidate_ref
            or job_spec.input_refs.get("benchmark_suite") != suite_ref
        ):
            return None

        raw_run_profile = basis.get("search_method_run_profile")
        if basis.get("schema_version") == "2":
            if not isinstance(raw_run_profile, Mapping):
                return None
            request_run_profile = SearchMethodRunProfile.model_validate(raw_run_profile)
            if (
                request_run_profile.schema_version != "2"
                or request_run_profile.loop_id != evaluation.loop_id
                or request_run_profile.suite_ref != suite_ref
                or request_run_profile.method_fqn != job_spec.method_fqn
                or request_run_profile.method_version != job_spec.method_version
                or request_run_profile.method_seed != job_spec.seed
                or request_run_profile.primary_metric != basis.get("primary_metric")
                or request_run_profile.direction != basis.get("direction")
                or request_run_profile.split != basis.get("split")
                or request_run_profile.unit != basis.get("unit")
            ):
                return None
        elif raw_run_profile is not None or basis.get("search_parameter_values") is not None:
            return None

        candidate_bindings = basis.get("candidate_input_bindings")
        data_bindings = basis.get("data_snapshot_bindings")
        if not isinstance(candidate_bindings, Mapping) or not isinstance(data_bindings, Mapping):
            return None
        method_state: dict[str, Any] = {}
        for slot_name, candidate_field in candidate_bindings.items():
            if (
                not isinstance(slot_name, str)
                or not isinstance(candidate_field, str)
                or candidate_field not in candidate_payload
            ):
                return None
            method_state[slot_name] = candidate_payload[candidate_field]
        data_snapshot_ref = job_spec.input_refs.get("data_snapshot")
        data_ref = job_spec.input_refs.get("data")
        data_payload: Mapping[str, Any] | None = None
        if bool(data_bindings) != (data_snapshot_ref is not None and data_ref is not None):
            return None
        if data_bindings:
            if data_snapshot_ref is None or data_ref is None:
                return None
            snapshot_manifest = reader.get_manifest(data_snapshot_ref)
            snapshot = DataSnapshot.model_validate(
                load_core_json_artifact(reader, data_snapshot_ref)
            )
            if (
                snapshot_manifest.kind != "fabric.data_snapshot"
                or snapshot.data_ref != data_ref
                or not _search_source_manifest_input_matches(
                    snapshot_manifest, "data_ref", data_ref
                )
            ):
                return None
            data_payload = load_core_json_artifact(reader, data_ref)
            if not isinstance(data_payload, Mapping):
                return None
            for slot_name, data_field in data_bindings.items():
                if (
                    not isinstance(slot_name, str)
                    or not isinstance(data_field, str)
                    or data_field not in data_payload
                ):
                    return None
                method_state[slot_name] = data_payload[data_field]
        if _search_source_fingerprint(method_state) != basis.get("method_state_fingerprint"):
            return None
        if basis.get("schema_version") == "2":
            assert isinstance(raw_run_profile, Mapping)
            actual_search_values = {
                name: candidate_payload[name]
                for name in request_run_profile.search_parameter_bindings
                if name in candidate_payload
            }
            if (
                actual_search_values != basis.get("search_parameter_values")
                or set(actual_search_values) != set(request_run_profile.search_parameter_bindings)
                or request_run_profile.candidate_input_bindings != dict(candidate_bindings)
                or request_run_profile.data_snapshot_bindings != dict(data_bindings)
                or request_run_profile.data_snapshot_ref != data_snapshot_ref
                or request_run_profile.data_ref != data_ref
                or request_run_profile.data_sample_count
                != _source_sample_count(data_payload, data_bindings)
                or not _search_method_parameters_match_run_profile(
                    profile=request_run_profile,
                    candidate=candidate_payload,
                    method_params=job_spec.method_params,
                )
            ):
                return None

        result_manifest = reader.get_manifest(method_result_ref)
        result_payload = load_core_json_artifact(reader, method_result_ref)
        if (
            not result_manifest.kind.startswith("scientist.method_result.")
            or not _search_source_manifest_schema_matches(
                result_manifest,
                name="polisyos.scientist.MethodResult",
            )
            or not isinstance(result_payload, Mapping)
        ):
            return None
        expected_result_inputs = {f"input:{name}": ref for name, ref in job_spec.input_refs.items()}
        actual_result_inputs = {
            item.role: item for item in result_manifest.inputs if item.role.startswith("input:")
        }
        if set(actual_result_inputs) != set(expected_result_inputs) or not all(
            actual_result_inputs[role].artifact_id == ref.artifact_id
            and actual_result_inputs[role].manifest_profile_sha256 == ref.manifest_profile_sha256
            for role, ref in expected_result_inputs.items()
        ):
            return None

        evidence_manifest = reader.get_manifest(method_evidence_ref)
        evidence_payload = load_core_json_artifact(reader, method_evidence_ref)
        if not isinstance(evidence_payload, Mapping):
            return None
        evidence_result_ref = ArtifactRef.model_validate(evidence_payload.get("method_result_ref"))
        if (
            evidence_manifest.kind != "scientist.method_evidence"
            or not _search_source_manifest_schema_matches(
                evidence_manifest,
                name="polisyos.scientist.MethodExecutionEvidence",
            )
            or evidence_payload.get("authority_purpose") != "method_execution"
            or evidence_payload.get("method_fqn") != job_spec.method_fqn
            or "execution_reproducibility" not in evidence_payload.get("authoritative_for", [])
            or not {"governance_admissibility", "method_validity"}.issubset(
                set(evidence_payload.get("may_not_use_for", []))
            )
            or evidence_result_ref != method_result_ref
            or evidence_payload.get("result_ref") != str(method_result_ref.artifact_id)
            or not _search_source_manifest_input_matches(
                evidence_manifest, "method_result", method_result_ref
            )
        ):
            return None

        metric = receipt.get("metric")
        split = BenchmarkSplit(receipt.get("split"))
        direction = MetricDirection(receipt.get("direction"))
        if not isinstance(metric, str) or not metric:
            return None
        output = result_payload.get("result")
        metric_source = output if isinstance(output, Mapping) else result_payload
        raw_metric = metric_source.get(metric)
        if isinstance(raw_metric, bool) or raw_metric is None:
            return None
        metric_value = float(raw_metric)
        if not isfinite(metric_value):
            return None
        metric_units = metric_source.get("metric_units")
        source_unit = metric_units.get(metric) if isinstance(metric_units, Mapping) else None
        if receipt.get("unit") is not None and source_unit != receipt.get("unit"):
            return None
        if evaluation.metrics_for_split(split) != {metric: metric_value}:
            return None
        opposite_metrics = (
            evaluation.holdout_metrics
            if split is BenchmarkSplit.SELECTION
            else evaluation.selection_metrics
        )
        if opposite_metrics:
            return None
        scalar = -metric_value if direction is MetricDirection.MAXIMIZE else metric_value
        if scalar != float(receipt.get("scalar_score", float("nan"))):
            return None
        expected_objective = _search_source_fingerprint(
            {
                "primary_metric": metric,
                "direction": direction.value,
                "scalarization": "finite_scalar_score_minimize",
            }
        )
        if profile.objective_fingerprint != expected_objective:
            return None
        if proposal_uncertainty is not None:
            try:
                fit_basis_ref = ArtifactRef.model_validate(receipt.get("fit_basis_ref"))
            except (TypeError, ValueError):
                return None
            if (
                profile.profile_kind != "configured_native_gp"
                or not profile.warm_start_eligible
                or profile.proposal_source != "bayesian_acquisition"
                or proposal_uncertainty.proposal_id != proposal_id
                or proposal_uncertainty.producer_optimizer_fqn != profile.optimizer_fqn
                or proposal_uncertainty.candidate_ref != candidate_ref
                or proposal_uncertainty.suite_ref != suite_ref
                or proposal_uncertainty.method_result_ref != method_result_ref
                or proposal_uncertainty.method_evidence_ref != method_evidence_ref
                or proposal_uncertainty.method_job_key != evaluation.method_job_key
                or proposal_uncertainty.metric != receipt.get("metric")
                or proposal_uncertainty.direction != receipt.get("direction")
                or proposal_uncertainty.split != receipt.get("split")
                or proposal_uncertainty.unit != receipt.get("unit")
                or proposal_uncertainty.method_request_basis_sha256
                != _search_source_fingerprint(dict(basis))
                or proposal_uncertainty.proposal_params_sha256
                != _search_source_fingerprint(dict(proposal_params))
                or proposal_uncertainty.source_profile_sha256 != receipt.get("profile_sha256")
                or proposal_uncertainty.fit_basis_ref != fit_basis_ref
                or proposal_uncertainty.optimizer_config_fingerprint
                != profile.optimizer_config_fingerprint
                or proposal_uncertainty.search_space_fingerprint != profile.search_space_fingerprint
                or proposal_uncertainty.training_corpus_fingerprint
                != profile.training_corpus_fingerprint
                or proposal_uncertainty.training_observation_count
                != profile.training_observation_count
                or proposal_uncertainty.context_fingerprint != profile.context_fingerprint
                or proposal_uncertainty.objective_fingerprint != profile.objective_fingerprint
            ):
                return None
        if require_warm_start_eligible and (
            profile.profile_kind != "configured_native_gp"
            or profile.proposal_source != "bayesian_acquisition"
            or expected_method_run_profile is None
        ):
            return None
        if require_warm_start_eligible or proposal_uncertainty is not None:
            if _skip_fit_recomputation:
                if require_warm_start_eligible:
                    return None
            elif not _recompute_search_gp_fit_basis(
                reader=reader,
                evaluation_ref=exact_evaluation_ref,
                evaluation_manifest=evaluation_manifest,
                evaluation=evaluation,
                receipt=receipt,
                profile=profile,
                proposal_params=proposal_params,
                proposal_uncertainty=proposal_uncertainty,
                expected_method_run_profile=expected_method_run_profile,
            ):
                return None
        if not _skip_fit_recomputation and receipt.get("fit_basis_ref") is not None:
            fit_basis_ref = ArtifactRef.model_validate(receipt["fit_basis_ref"])
            if not _search_source_manifest_input_matches(
                evaluation_manifest, "search_gp_fit_basis", fit_basis_ref, require_profile=True
            ):
                return None
        return profile, receipt, candidate_ref
    except (
        KeyError,
        OSError,
        OverflowError,
        RuntimeError,
        TypeError,
        ValueError,
        ValidationError,
    ):
        return None


def _method_request_matches_search_run_profile(
    *,
    reader: FileSystemCAS,
    evaluation: BenchmarkEvaluation,
    receipt: Mapping[str, Any],
    run_profile: SearchMethodRunProfile,
) -> bool:
    """Reconcile the persisted MethodJob request and full data quantity to a run profile."""
    from polisyos.core.artifacts import load_core_json_artifact

    basis = receipt.get("method_request_basis")
    if not isinstance(basis, Mapping):
        return False
    try:
        job_spec = JobSpec.model_validate(basis.get("job_spec"))
        candidate_ref = ArtifactRef.model_validate(receipt.get("candidate_ref"))
        suite_ref = ArtifactRef.model_validate(receipt.get("suite_ref"))
        candidate_payload = load_core_json_artifact(reader, candidate_ref)
        if not isinstance(candidate_payload, Mapping):
            return False
        expected_search_values = {
            name: candidate_payload[name]
            for name in run_profile.search_parameter_bindings
            if name in candidate_payload
        }
        if (
            evaluation.loop_id != run_profile.loop_id
            or suite_ref != run_profile.suite_ref
            or job_spec.method_fqn != run_profile.method_fqn
            or job_spec.method_version != run_profile.method_version
            or job_spec.seed != run_profile.method_seed
            or not _search_method_parameters_match_run_profile(
                profile=run_profile,
                candidate=candidate_payload,
                method_params=job_spec.method_params,
            )
            or basis.get("schema_version")
            != ("2" if run_profile.search_parameter_bindings else "1")
            or (
                bool(run_profile.search_parameter_bindings)
                and (
                    basis.get("search_method_run_profile")
                    != run_profile.model_dump(mode="json", exclude_none=True)
                    or basis.get("search_parameter_values") != expected_search_values
                    or set(expected_search_values) != set(run_profile.search_parameter_bindings)
                )
            )
            or basis.get("candidate_input_bindings") != run_profile.candidate_input_bindings
            or basis.get("data_snapshot_bindings") != run_profile.data_snapshot_bindings
            or basis.get("candidate_ref") != candidate_ref.model_dump(mode="json")
            or basis.get("suite_ref") != suite_ref.model_dump(mode="json")
            or basis.get("primary_metric") != run_profile.primary_metric
            or basis.get("direction") != run_profile.direction
            or basis.get("split") != run_profile.split
            or basis.get("unit") != run_profile.unit
            or job_spec.input_refs.get("candidate") != candidate_ref
            or job_spec.input_refs.get("benchmark_suite") != suite_ref
        ):
            return False
        data_snapshot_ref = job_spec.input_refs.get("data_snapshot")
        data_ref = job_spec.input_refs.get("data")
        if (
            data_snapshot_ref != run_profile.data_snapshot_ref
            or data_ref != run_profile.data_ref
            or bool(run_profile.data_snapshot_bindings)
            != (data_snapshot_ref is not None and data_ref is not None)
        ):
            return False
        if data_snapshot_ref is None:
            return run_profile.data_sample_count is None
        snapshot_manifest = reader.get_manifest(data_snapshot_ref)
        snapshot = DataSnapshot.model_validate(load_core_json_artifact(reader, data_snapshot_ref))
        if (
            snapshot_manifest.kind != "fabric.data_snapshot"
            or snapshot.data_ref != data_ref
            or not _search_source_manifest_input_matches(
                snapshot_manifest, "data_ref", data_ref, require_profile=True
            )
        ):
            return False
        data_payload = load_core_json_artifact(reader, data_ref)
        if not isinstance(data_payload, Mapping):
            return False
        return _source_sample_count(data_payload, run_profile.data_snapshot_bindings) == (
            run_profile.data_sample_count
        )
    except (KeyError, OSError, RuntimeError, TypeError, ValueError, ValidationError):
        return False


def _recompute_search_gp_fit_basis(
    *,
    reader: FileSystemCAS,
    evaluation_ref: ArtifactRef,
    evaluation_manifest: ArtifactManifest,
    evaluation: BenchmarkEvaluation,
    receipt: Mapping[str, Any],
    profile: BayesianSourceProfile,
    proposal_params: Mapping[str, Any] | None,
    proposal_uncertainty: SearchGPProposalUncertainty | None,
    expected_method_run_profile: SearchMethodRunProfile | None,
) -> bool:
    """Recompute the fitted native GP from exact CAS-backed MethodJob observations."""
    from polisyos.core.artifacts import load_core_json_artifact

    try:
        fit_basis_ref = ArtifactRef.model_validate(receipt.get("fit_basis_ref"))
        if fit_basis_ref.manifest_profile_sha256 is None:
            return False
        if evaluation.metadata.get("search_gp_fit_basis_ref") != fit_basis_ref.model_dump(
            mode="json"
        ):
            return False
        if not _search_source_manifest_input_matches(
            evaluation_manifest,
            "search_gp_fit_basis",
            fit_basis_ref,
            require_profile=True,
        ):
            return False
        fit_manifest = reader.get_manifest(fit_basis_ref)
        if (
            fit_manifest.kind != "scientist.autotune.search_gp_fit_basis"
            or not _search_source_manifest_schema_matches(
                fit_manifest,
                name="polisyos.scientist.methods.autotune.SearchGPFitBasis",
                version="2.0",
            )
        ):
            return False
        fit_basis = SearchGPFitBasis.model_validate(load_core_json_artifact(reader, fit_basis_ref))
        run_profile = fit_basis.run_profile
        if (
            (expected_method_run_profile is not None and run_profile != expected_method_run_profile)
            or fit_basis.profile != profile
            or profile.context_fingerprint != run_profile.context_fingerprint
            or profile.objective_fingerprint != run_profile.objective_fingerprint
            or profile.search_space_fingerprint != run_profile.search_space_fingerprint
            or not _method_request_matches_search_run_profile(
                reader=reader,
                evaluation=evaluation,
                receipt=receipt,
                run_profile=run_profile,
            )
        ):
            return False
        source_refs = fit_basis.training_evaluation_refs
        acquisition_refs = fit_basis.acquisition_evaluation_refs
        acquisition_manifest_inputs = [
            (str(item.artifact_id), item.manifest_profile_sha256)
            for item in fit_manifest.inputs
            if item.role == "acquisition_evaluation"
        ]
        expected_inputs = [
            ("training_evaluation", str(ref.artifact_id), ref.manifest_profile_sha256)
            for ref in source_refs
        ] + [
            ("acquisition_evaluation", str(ref.artifact_id), ref.manifest_profile_sha256)
            for ref in acquisition_refs
        ]
        actual_inputs = [
            (item.role, str(item.artifact_id), item.manifest_profile_sha256)
            for item in fit_manifest.inputs
            if item.role in {"training_evaluation", "acquisition_evaluation"}
        ]
        if (
            sorted(actual_inputs) != sorted(expected_inputs)
            or len(acquisition_manifest_inputs) != fit_basis.acquisition_observation_count
            or len(acquisition_refs) != fit_basis.acquisition_observation_count
        ):
            return False

        from polisyos.scientist.methods.search.objective import (
            ObjectiveValue,
            OptimizationDirection,
        )
        from polisyos.scientist.methods.search.strategies.bayesian import (
            BayesianConfig,
            BayesianOptimizer,
        )
        from polisyos.scientist.methods.search.strategies.space import SearchSpace
        from polisyos.scientist.methods.search.strategies.types import (
            AcquisitionType,
            Evaluation,
            EvaluationStatus,
            ParameterBounds,
            ParameterType,
        )

        native_space = SearchSpace(
            bounds=[
                ParameterBounds(
                    name=item.name,
                    lower=item.lower,
                    upper=item.upper,
                    dtype=ParameterType(item.dtype),
                    log_scale=item.log_scale,
                    categories=(tuple(item.categories) if item.categories is not None else None),
                )
                for item in fit_basis.bounds
            ]
        )
        if native_space.sobol_space_fingerprint() != run_profile.search_space_fingerprint:
            return False
        fit_config = fit_basis.fit_config.model_dump()
        fit_config["acquisition"] = AcquisitionType(fit_config["acquisition"])
        optimizer = BayesianOptimizer(
            native_space,
            config=BayesianConfig(**fit_config),
        )
        if not optimizer.native_gp_ready or str(optimizer._device) != fit_basis.fit_backend:
            return False
        optimizer.set_search_run_profile(
            context_fingerprint=run_profile.context_fingerprint,
            objective_fingerprint=run_profile.objective_fingerprint,
        )

        def load_source_evaluation(source_ref: ArtifactRef) -> Evaluation | None:
            verified = _verify_search_source_profile_receipt(
                store=reader,
                evaluation_ref=source_ref,
                require_warm_start_eligible=False,
                _skip_fit_recomputation=True,
            )
            if verified is None:
                return None
            source_profile, source_receipt, source_candidate_ref = verified
            source_evaluation_manifest = reader.get_manifest(source_ref)
            source_evaluation = BenchmarkEvaluation.model_validate(
                load_core_json_artifact(reader, source_ref)
            )
            if (
                source_profile.profile_kind != "configured_native_gp"
                or source_profile.search_space_fingerprint != profile.search_space_fingerprint
                or source_profile.context_fingerprint != run_profile.context_fingerprint
                or source_profile.objective_fingerprint != run_profile.objective_fingerprint
                or not _method_request_matches_search_run_profile(
                    reader=reader,
                    evaluation=source_evaluation,
                    receipt=source_receipt,
                    run_profile=run_profile,
                )
            ):
                return None
            proposal = source_receipt.get("proposal")
            params = proposal.get("params") if isinstance(proposal, Mapping) else None
            scalar = source_receipt.get("scalar_score")
            if (
                not isinstance(params, Mapping)
                or isinstance(scalar, bool)
                or not isinstance(scalar, (int, float))
                or not isfinite(float(scalar))
                or not _search_source_manifest_schema_matches(
                    source_evaluation_manifest,
                    name="polisyos.scientist.methods.autotune.BenchmarkEvaluation",
                )
            ):
                return None
            return Evaluation(
                candidate_id=str(source_candidate_ref.artifact_id),
                params=dict(params),
                params_normalized=tuple(native_space.normalize(dict(params))),
                objectives=[
                    ObjectiveValue(
                        name=run_profile.primary_metric,
                        raw_value=float(scalar),
                        direction=OptimizationDirection.MINIMIZE,
                    )
                ],
                scalar_score=float(scalar),
                stage_a_passed=True,
                status=EvaluationStatus.SUCCESS,
                provenance_ref=str(source_receipt["method_result_ref"]["artifact_id"]),
                metadata={"search_source_evaluation_ref": source_ref.model_dump(mode="json")},
            )

        training_evaluations: list[Evaluation] = []
        for source_ref in source_refs:
            source_evaluation = load_source_evaluation(source_ref)
            if source_evaluation is None:
                return False
            training_evaluations.append(source_evaluation)
        acquisition_evaluations: list[Evaluation] = []
        for source_ref in acquisition_refs:
            source_evaluation = load_source_evaluation(source_ref)
            if source_evaluation is None:
                return False
            acquisition_evaluations.append(source_evaluation)
        if len(training_evaluations) != fit_basis.training_observation_count:
            return False
        train_x, train_y = optimizer._prepare_training_data(training_evaluations)
        optimizer._fit_full_gp(train_x, train_y)
        if optimizer._fitted_model_state_fingerprint() != fit_basis.fitted_model_state_fingerprint:
            return False
        optimizer._record_fitted_training_corpus(training_evaluations)
        recomputed_profile = BayesianSourceProfile.model_validate(
            asdict(
                optimizer.effective_fit_profile(
                    proposal_source=fit_basis.proposal_source,
                    context_fingerprint=run_profile.context_fingerprint,
                    objective_fingerprint=run_profile.objective_fingerprint,
                )
            )
        )
        if not (
            recomputed_profile == profile
            and recomputed_profile.warm_start_eligible
            and evaluation_ref.manifest_profile_sha256 is not None
        ):
            return False
        if proposal_uncertainty is None:
            return proposal_params is None
        if proposal_params is None or (
            proposal_uncertainty.fit_backend != fit_basis.fit_backend
            or proposal_uncertainty.fitted_model_state_fingerprint
            != fit_basis.fitted_model_state_fingerprint
            or proposal_uncertainty.training_observation_count
            != fit_basis.training_observation_count
            or proposal_uncertainty.acquisition_evaluation_count
            != fit_basis.acquisition_observation_count
        ):
            return False
        prediction = optimizer.proposal_prediction(
            params=dict(proposal_params),
            evaluations=acquisition_evaluations,
        )
        return (
            proposal_uncertainty.acquisition_type == prediction["acquisition_type"]
            and isclose(
                proposal_uncertainty.predicted_mean,
                prediction["predicted_mean"],
                rel_tol=1e-10,
                abs_tol=1e-12,
            )
            and isclose(
                proposal_uncertainty.predicted_std,
                prediction["predicted_std"],
                rel_tol=1e-10,
                abs_tol=1e-12,
            )
            and isclose(
                proposal_uncertainty.acquisition_value,
                prediction["acquisition_value"],
                rel_tol=1e-10,
                abs_tol=1e-12,
            )
        )
    except (KeyError, OSError, RuntimeError, TypeError, ValueError, ValidationError):
        return False


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
        producer_settlement_store: BudgetMiddleware | None = None,
        producer_run_binding: BudgetLedgerProducerRunBinding | None = None,
    ) -> SearchResult:
        del scheduler  # reserved for future Hyperband integration
        generator = spec.candidate_generator
        if generator is None:
            raise ValueError(f"Search loop '{spec.loop_id}' is missing a candidate generator")
        if spec.loop_id == "claim_adjudication":
            if suite_ref.manifest_profile_sha256 is None:
                raise ValueError("claim_adjudication_selected_profile_required:benchmark_suite")
            self._store.get_manifest_by_profile(
                suite_ref.artifact_id, suite_ref.manifest_profile_sha256
            )
        if (producer_settlement_store is None) != (producer_run_binding is None):
            raise ValueError("durable producer budget requires both owner and run binding")
        if producer_settlement_store is not None:
            assert producer_run_binding is not None
            TracedLLMCandidateGenerator.require_bound_owner(
                generator,
                producer_settlement_store,
                producer_run_binding,
            )
        search_context = dict(context or {})
        runtime_context = dict(search_context)
        if producer_run_binding is not None:
            supplied_run_id = runtime_context.get("run_id")
            if supplied_run_id is not None and supplied_run_id != producer_run_binding.run_id:
                raise ValueError("search run_id conflicts with producer run binding")
            runtime_context["run_id"] = producer_run_binding.run_id
        else:
            runtime_context.setdefault("run_id", f"search-run:{uuid4().hex}")
        set_search_run_context = getattr(generator, "set_search_run_context", None)
        if callable(set_search_run_context):
            set_search_run_context(search_context)
        from .bayesian_generator import BayesianCandidateGenerator

        method_run_profile: SearchMethodRunProfile | None = None
        if type(generator) is BayesianCandidateGenerator:
            BayesianCandidateGenerator._configure_source_store(generator, self._store)
            method_run_profile = _build_search_method_run_profile(
                store=self._store,
                generator=generator,
                spec=spec,
                suite_ref=suite_ref,
                context=search_context,
            )
            BayesianCandidateGenerator.set_search_method_run_profile(generator, method_run_profile)
        if (
            isinstance(spec.benchmark_evaluator, MethodJobBenchmarkEvaluator)
            and spec.benchmark_evaluator._search_parameter_bindings
        ):
            runtime_context["_search_method_run_profile"] = (
                method_run_profile.model_dump(mode="json", exclude_none=True)
                if method_run_profile is not None
                else None
            )
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
                producer_settlement_store=producer_settlement_store,
                producer_run_binding=producer_run_binding,
            ),
            candidate_generator=generator,
            stage_a_evaluator=lambda candidate, ctx: (0.0, True),
            stage_b_evaluator=lambda candidate, ctx: self._evaluate_candidate(
                spec,
                suite_ref=suite_ref,
                candidate_payload=candidate,
                context=ctx,
                generator=generator,
            ),
        )
        initial_payload = (
            initial_candidate.model_dump(mode="json")
            if isinstance(initial_candidate, BaseModel)
            else initial_candidate
        )
        from polisyos.scientist.methods.search.service import _NativeSearchServiceDriver

        driver = _NativeSearchServiceDriver(controller)
        if producer_settlement_store is None:
            return driver.run_search(
                initial_context=runtime_context,
                initial_candidate=initial_payload,
            )
        if producer_run_binding is None:
            raise ValueError("producer run binding is required with settlement store")
        with producer_settlement_store.producer_run_binding_scope(producer_run_binding):
            return driver.run_search(
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
        generator: Any,
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
        claim_selected_profile = spec.loop_id == "claim_adjudication"
        if claim_selected_profile and suite_ref.manifest_profile_sha256 is None:
            raise ValueError("claim_adjudication_selected_profile_required:benchmark_suite")
        candidate_ref = persist_mutation_artifact(
            self._store,
            cast("MutationArtifact", candidate),
            inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
            return_selected_profile=claim_selected_profile,
        )
        if claim_selected_profile and candidate_ref.manifest_profile_sha256 is None:
            raise ValueError("claim_adjudication_selected_profile_required:candidate")
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
        evaluation_metadata = dict(evaluation.metadata)
        evaluation_metadata.pop(_SEARCH_SOURCE_RECEIPT_KEY, None)
        evaluation = evaluation.model_copy(
            update={"search_source_profile": None, "metadata": evaluation_metadata}
        )
        source_profile: BayesianSourceProfile | None = None
        proposal_receipt: dict[str, Any] | None = None
        from .bayesian_generator import BayesianCandidateGenerator

        if (
            type(generator) is BayesianCandidateGenerator
            and type(spec.benchmark_evaluator) is MethodJobBenchmarkEvaluator
        ):
            proposal_receipt = BayesianCandidateGenerator._consume_issued_source_profile(
                generator, candidate_payload
            )
            if proposal_receipt is not None:
                source_profile = proposal_receipt["profile"]
        if (
            source_profile is not None
            and proposal_receipt is not None
            and evaluation.status == "measured_candidate"
            and evaluation.method_result_ref is not None
            and evaluation.method_evidence_ref is not None
            and evaluation.method_job_key is not None
        ):
            request_basis = evaluation.metadata.get("method_request_basis")
            objective_fingerprint = _search_source_fingerprint(
                {
                    "primary_metric": spec.promotion_policy.primary_metric,
                    "direction": spec.promotion_policy.direction.value,
                    "scalarization": "finite_scalar_score_minimize",
                }
            )
            method_evaluator = spec.benchmark_evaluator
            metric_value = evaluation.primary_value(
                split=method_evaluator._split,
                metric=spec.promotion_policy.primary_metric,
            )
            if (
                isinstance(request_basis, Mapping)
                and request_basis.get("candidate_ref") == candidate_ref.model_dump(mode="json")
                and request_basis.get("suite_ref") == suite_ref.model_dump(mode="json")
                and source_profile.objective_fingerprint == objective_fingerprint
                and metric_value is not None
                and isfinite(metric_value)
            ):
                scalar_score = (
                    -float(metric_value)
                    if spec.promotion_policy.direction is MetricDirection.MAXIMIZE
                    else float(metric_value)
                )
                receipt: dict[str, Any] = {
                    "schema_version": "1",
                    "authority_purpose": "candidate_search_history_profile",
                    "grade": "candidate_only",
                    "profile": source_profile.model_dump(mode="json", exclude_none=True),
                    "profile_sha256": _search_source_fingerprint(
                        source_profile.model_dump(mode="json", exclude_none=True)
                    ),
                    "proposal": {
                        "proposal_id": proposal_receipt["proposal_id"],
                        "params": proposal_receipt["params"],
                    },
                    "candidate_ref": candidate_ref.model_dump(mode="json"),
                    "suite_ref": suite_ref.model_dump(mode="json"),
                    "method_request_basis": dict(request_basis),
                    "method_result_ref": evaluation.method_result_ref.model_dump(mode="json"),
                    "method_evidence_ref": evaluation.method_evidence_ref.model_dump(mode="json"),
                    "method_job_key": evaluation.method_job_key,
                    "metric": spec.promotion_policy.primary_metric,
                    "direction": spec.promotion_policy.direction.value,
                    "split": method_evaluator._split.value,
                    "unit": spec.promotion_policy.unit,
                    "scalar_score": scalar_score,
                }
                fit_basis_ref = proposal_receipt.get("fit_basis_ref")
                if source_profile.warm_start_eligible and isinstance(fit_basis_ref, ArtifactRef):
                    receipt["fit_basis_ref"] = fit_basis_ref.model_dump(mode="json")
                    raw_prediction = proposal_receipt.get("proposal_prediction")
                    fit_basis = load_model_artifact(
                        self._store,
                        fit_basis_ref,
                        SearchGPFitBasis,
                    )
                    if not isinstance(raw_prediction, Mapping) or not isinstance(
                        fit_basis, SearchGPFitBasis
                    ):
                        raise ValueError("native GP proposal lacks its typed uncertainty basis")
                    proposal_uncertainty = SearchGPProposalUncertainty(
                        producer_optimizer_fqn=source_profile.optimizer_fqn,
                        proposal_id=proposal_receipt["proposal_id"],
                        candidate_ref=candidate_ref,
                        suite_ref=suite_ref,
                        method_result_ref=evaluation.method_result_ref,
                        method_evidence_ref=evaluation.method_evidence_ref,
                        method_job_key=evaluation.method_job_key,
                        metric=spec.promotion_policy.primary_metric,
                        direction=spec.promotion_policy.direction.value,
                        split=method_evaluator._split.value,
                        unit=spec.promotion_policy.unit,
                        method_request_basis_sha256=_search_source_fingerprint(dict(request_basis)),
                        proposal_params_sha256=_search_source_fingerprint(
                            dict(proposal_receipt["params"])
                        ),
                        source_profile_sha256=receipt["profile_sha256"],
                        fit_basis_ref=fit_basis_ref,
                        fit_backend=fit_basis.fit_backend,
                        fitted_model_state_fingerprint=(fit_basis.fitted_model_state_fingerprint),
                        optimizer_config_fingerprint=(source_profile.optimizer_config_fingerprint),
                        search_space_fingerprint=source_profile.search_space_fingerprint,
                        training_corpus_fingerprint=(source_profile.training_corpus_fingerprint),
                        training_observation_count=(source_profile.training_observation_count),
                        acquisition_evaluation_count=(fit_basis.acquisition_observation_count),
                        context_fingerprint=source_profile.context_fingerprint,
                        objective_fingerprint=source_profile.objective_fingerprint,
                        acquisition_type=raw_prediction["acquisition_type"],
                        predicted_mean=raw_prediction["predicted_mean"],
                        predicted_std=raw_prediction["predicted_std"],
                        acquisition_value=raw_prediction["acquisition_value"],
                    )
                    receipt["proposal_uncertainty"] = proposal_uncertainty.model_dump(
                        mode="json",
                        exclude_none=True,
                    )
                    evaluation_metadata = {
                        **evaluation.metadata,
                        _SEARCH_SOURCE_RECEIPT_KEY: receipt,
                        "search_gp_fit_basis_ref": fit_basis_ref.model_dump(mode="json"),
                    }
                else:
                    source_profile = source_profile.model_copy(
                        update={"warm_start_eligible": False}
                    )
                    receipt["profile"] = source_profile.model_dump(mode="json", exclude_none=True)
                    receipt["profile_sha256"] = _search_source_fingerprint(receipt["profile"])
                    receipt.pop("fit_basis_ref", None)
                    receipt["receipt_sha256"] = _search_source_fingerprint(
                        {key: value for key, value in receipt.items() if key != "receipt_sha256"}
                    )
                    evaluation_metadata = {
                        **evaluation.metadata,
                        _SEARCH_SOURCE_RECEIPT_KEY: receipt,
                    }
                if "receipt_sha256" not in receipt:
                    receipt["receipt_sha256"] = _search_source_fingerprint(receipt)
                    evaluation_metadata[_SEARCH_SOURCE_RECEIPT_KEY] = receipt
                evaluation = evaluation.model_copy(
                    update={
                        "search_source_profile": source_profile,
                        "metadata": evaluation_metadata,
                    }
                )
        benchmark_evaluator = spec.benchmark_evaluator
        source_bound_work_expected = (
            isinstance(benchmark_evaluator, MethodJobBenchmarkEvaluator)
            and benchmark_evaluator.requires_source_bound_execution_work_packet
        )
        packet_admission_failure: str | None = None
        if source_bound_work_expected or evaluation.execution_work_packet_status == "available":
            packet_admission_failure = _search_work_packet_admission_failure(
                store=self._store,
                evaluation=evaluation,
                evaluator=(
                    benchmark_evaluator
                    if isinstance(benchmark_evaluator, MethodJobBenchmarkEvaluator)
                    else None
                ),
                candidate_ref=candidate_ref,
                suite_ref=suite_ref,
                policy=spec.promotion_policy,
                context=context,
                run_id=str(context.get("run_id") or ""),
                evaluation_id=evaluation_id,
                evaluation_attempt_id=evaluation_attempt_id,
            )
        source_profile_conflict = evaluation.status == "source_profile_conflict"
        search_source_rejected = packet_admission_failure is not None or source_profile_conflict
        if search_source_rejected:
            rejected_note = packet_admission_failure or "search_source_profile_conflict"
            rejected_update: dict[str, Any] = {
                "selection_metrics": {
                    name: value
                    for name, value in evaluation.selection_metrics.items()
                    if name != spec.promotion_policy.primary_metric
                },
                "holdout_metrics": {
                    name: value
                    for name, value in evaluation.holdout_metrics.items()
                    if name != spec.promotion_policy.primary_metric
                },
                "promotable": False,
                "status": (
                    "source_work_packet_rejected"
                    if packet_admission_failure is not None
                    else evaluation.status
                ),
                "guardrails": {
                    **evaluation.guardrails,
                    "primary_metric_available": False,
                },
                "notes": [*evaluation.notes, rejected_note],
            }
            if packet_admission_failure is not None:
                rejected_update.update(
                    {
                        "execution_work_packet_status": "rejected",
                        "execution_work_packet_note": packet_admission_failure,
                    }
                )
            evaluation = evaluation.model_copy(update=rejected_update)
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
                    "status": (
                        evaluation.status if search_source_rejected else "metric_unavailable"
                    ),
                    "guardrails": {
                        **evaluation.guardrails,
                        "primary_metric_available": False,
                    },
                }
            )
        if evaluation.status != "measured_candidate":
            retained_metadata = dict(evaluation.metadata)
            retained_metadata.pop(_SEARCH_SOURCE_RECEIPT_KEY, None)
            retained_metadata.pop("search_gp_fit_basis_ref", None)
            evaluation = evaluation.model_copy(
                update={"search_source_profile": None, "metadata": retained_metadata}
            )
        evaluation_ref = _persist_search_benchmark_evaluation(
            self._store,
            evaluation,
            suite_ref=suite_ref,
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
                "evaluation_artifact_ref": evaluation_ref.model_dump(mode="json"),
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
