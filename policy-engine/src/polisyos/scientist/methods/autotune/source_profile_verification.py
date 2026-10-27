"""Fresh-read verification for candidate-grade autotune search profiles.

This module owns profile receipt validation and fitted-basis recomputation so
both the persisted runtime and Bayesian producer can consume the same verifier
without importing each other.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from enum import Enum
from math import isclose, isfinite
from typing import Any

from pydantic import ValidationError

from polisyos.core.artifacts import (
    ArtifactManifest,
    ArtifactRef,
    CoreJSONArtifactStore,
    SchemaInfo,
    resolve_manifest_by_profile,
    validate_core_model_json_artifact,
)
from polisyos.core.canon import CanonSpec, fingerprint
from polisyos.core.contracts import DataSnapshot
from polisyos.scientist.compute.job_spec import JobKey, JobSpec
from polisyos.scientist.methods.search.objective import (
    _configured_search_metric_profile_fingerprint,
)

from .models import (
    BayesianSourceProfile,
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSuite,
    MetricDirection,
    SearchGPFitBasis,
    SearchGPProposalUncertainty,
    SearchMethodRunProfile,
    _search_method_parameters_match_run_profile,
)


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
) -> bool:
    """Reconcile one unambiguous lineage edge with its selected reference.

    An ID can have several valid manifests. The receipt's ref is subsequently
    opened through Core, which validates kind and media type against that exact
    selected manifest; the edge must select the very same profile. A matching
    edge cannot excuse a second, conflicting edge with the same role.
    """
    matching_role = [item for item in manifest.inputs if item.role == role]
    return (
        len(matching_role) == 1
        and matching_role[0].artifact_id == ref.artifact_id
        and ref.manifest_profile_sha256 is not None
        and matching_role[0].manifest_profile_sha256 == ref.manifest_profile_sha256
    )


class _SearchHistorySourceDisposition(str, Enum):
    """Owner-resolved status for one persisted Search history source."""

    NOT_APPLICABLE = "not_applicable"
    REFUSED = "refused"
    VERIFIED = "verified"


@dataclass(frozen=True, slots=True)
class _SearchHistorySourceResolution:
    """Carry the source owner's disposition and any resolved evaluation evidence."""

    disposition: _SearchHistorySourceDisposition
    evaluation: BenchmarkEvaluation | None = None
    verified: tuple[BayesianSourceProfile, dict[str, Any], ArtifactRef] | None = None


_SEARCH_HISTORY_METHOD_INPUT_ROLES = frozenset(
    {"method_result", "method_evidence", "execution_work_packet"}
)
_SEARCH_HISTORY_METHOD_METADATA_KEYS = frozenset(
    {
        "method_fqn",
        "method_version",
        "method_seed",
        "method_job_key",
        "method_input_bindings",
        "method_result_ref",
        "method_evidence_ref",
        "method_request_basis",
        _SEARCH_SOURCE_RECEIPT_KEY,
        "search_source_evaluation_ref",
    }
)


def _search_history_source_payload_claimed(evaluation: BenchmarkEvaluation) -> bool:
    """Detect MethodJob payload assertions even without a readable manifest."""
    return (
        evaluation.method_result_ref is not None
        or evaluation.method_evidence_ref is not None
        or evaluation.method_job_key is not None
        or evaluation.execution_work_packet_ref is not None
        or evaluation.execution_work_packet_status != "unavailable"
        or evaluation.execution_work_packet_note is not None
        or any(key in evaluation.metadata for key in _SEARCH_HISTORY_METHOD_METADATA_KEYS)
    )


def _search_history_source_claimed(
    evaluation: BenchmarkEvaluation,
    manifest: ArtifactManifest,
) -> bool:
    """Classify persisted MethodJob claims, not a profile-only generic record."""
    return _search_history_source_payload_claimed(evaluation) or any(
        item.role in _SEARCH_HISTORY_METHOD_INPUT_ROLES for item in manifest.inputs
    )


def _search_evaluation_manifest_matches(
    manifest: ArtifactManifest, ref: ArtifactRef, evaluation: BenchmarkEvaluation
) -> bool:
    """Bind selected evaluation to the existing suite-versioned writer ABI."""
    return (
        ref.manifest_profile_sha256 is not None
        and manifest.artifact_id == ref.artifact_id
        and manifest.kind == ref.kind == f"scientist.autotune.{evaluation.loop_id}.evaluation"
        and manifest.media_type == ref.media_type == "application/json"
        and _search_source_manifest_schema_matches(
            manifest,
            name="polisyos.scientist.methods.autotune.BenchmarkEvaluation",
            version=evaluation.suite_version,
        )
        and manifest.producer is not None
        and str(manifest.producer.component)
        == "polisyos.scientist.methods.autotune.benchmark_evaluator"
        and manifest.producer.version in {"1.0", "2.0"}
    )


def _resolve_search_history_source(
    *,
    store: CoreJSONArtifactStore | None,
    evaluation_ref: Any,
    expected_params: Any = None,
    expected_scalar: Any = None,
    expected_proposal_id: Any = None,
    expected_provenance_ref: Any = None,
) -> _SearchHistorySourceResolution:
    """Resolve source ownership before a persisted scalar can use generic history fallback.

    Genuine generic BenchmarkEvaluation artifacts remain applicable to the ordinary
    candidate-history path. Any typed payload claim or persisted MethodJob input role
    requires the full existing receipt, producer-basis, and CAS verifier; partial or
    unreadable source claims are refused.
    """
    if evaluation_ref is None:
        return _SearchHistorySourceResolution(
            disposition=_SearchHistorySourceDisposition.NOT_APPLICABLE
        )
    if store is None:
        return _SearchHistorySourceResolution(disposition=_SearchHistorySourceDisposition.REFUSED)

    from polisyos.core.artifacts import load_core_json_artifact

    try:
        exact_ref = ArtifactRef.model_validate(evaluation_ref)
        manifest = store.get_manifest(exact_ref)
        if (
            manifest.artifact_id != exact_ref.artifact_id
            or not _search_source_manifest_schema_matches(
                manifest,
                name="polisyos.scientist.methods.autotune.BenchmarkEvaluation",
            )
        ):
            return _SearchHistorySourceResolution(
                disposition=_SearchHistorySourceDisposition.REFUSED
            )
        raw_evaluation = load_core_json_artifact(store, exact_ref)
        evaluation = BenchmarkEvaluation.model_validate(raw_evaluation)
        if not _search_evaluation_manifest_matches(manifest, exact_ref, evaluation):
            return _SearchHistorySourceResolution(
                disposition=_SearchHistorySourceDisposition.REFUSED
            )
    except Exception:
        return _SearchHistorySourceResolution(disposition=_SearchHistorySourceDisposition.REFUSED)

    if not _search_history_source_claimed(evaluation, manifest):
        # Generic status is candidate-grade, but its optimizer coordinates must
        # still come from the exact candidate selected by the evaluation.
        try:
            candidate_ref = evaluation.candidate_ref
            if not _search_source_manifest_input_matches(manifest, "candidate", candidate_ref):
                raise ValueError("generic_benchmark_candidate_edge_mismatch")
            candidate_manifest = store.get_manifest(candidate_ref)
            if (
                candidate_manifest.kind != f"scientist.autotune.{evaluation.loop_id}.candidate"
                or candidate_manifest.media_type != "application/json"
                or candidate_manifest.producer is None
                or str(candidate_manifest.producer.component)
                != "polisyos.scientist.methods.autotune.mutation_artifact"
                or candidate_manifest.producer.version != "1.0"
            ):
                raise ValueError("generic_benchmark_candidate_source_mismatch")
            candidate_payload = load_core_json_artifact(store, candidate_ref)
            if (
                not isinstance(candidate_payload, Mapping)
                or candidate_payload.get("loop_id") != evaluation.loop_id
            ):
                raise ValueError("generic_benchmark_candidate_payload_mismatch")
            candidate_schema = candidate_manifest.artifact_schema
            if (
                candidate_schema is None
                or not candidate_schema.name.startswith("polisyos.scientist.methods.autotune.")
                or candidate_schema.version != candidate_payload.get("artifact_version")
            ):
                raise ValueError("generic_benchmark_candidate_schema_mismatch")
            suite_edges = [edge for edge in manifest.inputs if edge.role == "benchmark_suite"]
            candidate_suite_edges = [
                edge for edge in candidate_manifest.inputs if edge.role == "benchmark_suite"
            ]
            if (
                len(suite_edges) != 1
                or len(candidate_suite_edges) != 1
                or suite_edges[0] != candidate_suite_edges[0]
                or suite_edges[0].manifest_profile_sha256 is None
            ):
                raise ValueError("generic_benchmark_suite_edge_mismatch")
            suite_edge = suite_edges[0]
            suite_manifest = resolve_manifest_by_profile(
                store, suite_edge.artifact_id, suite_edge.manifest_profile_sha256
            )
            suite_ref = ArtifactRef(
                artifact_id=suite_edge.artifact_id,
                kind=suite_manifest.kind,
                media_type=suite_manifest.media_type,
                manifest_profile_sha256=suite_edge.manifest_profile_sha256,
            )
            suite = BenchmarkSuite.model_validate(load_core_json_artifact(store, suite_ref))
            if (
                suite.suite_id != evaluation.suite_id
                or suite.suite_version != evaluation.suite_version
                or suite_manifest.kind != f"scientist.autotune.{suite.kind}.suite"
                or suite_manifest.media_type != "application/json"
                or not _search_source_manifest_schema_matches(
                    suite_manifest,
                    name="polisyos.scientist.methods.autotune.BenchmarkSuite",
                    version=suite.suite_version,
                )
            ):
                raise ValueError("generic_benchmark_suite_source_mismatch")
            if expected_params is not None:
                if not isinstance(expected_params, Mapping):
                    raise ValueError("generic_benchmark_candidate_params_invalid")
                nested_params = candidate_payload.get("params")
                parameter_source = (
                    nested_params if isinstance(nested_params, Mapping) else candidate_payload
                )
                selected_params = {
                    name: parameter_source[name]
                    for name in expected_params
                    if isinstance(name, str) and name in parameter_source
                }
                if (
                    set(selected_params) != set(expected_params)
                    or _search_source_fingerprint(selected_params) is None
                    or _search_source_fingerprint(selected_params)
                    != _search_source_fingerprint(dict(expected_params))
                ):
                    raise ValueError("generic_benchmark_candidate_params_mismatch")
        except (KeyError, OSError, RuntimeError, TypeError, ValueError, ValidationError):
            return _SearchHistorySourceResolution(
                disposition=_SearchHistorySourceDisposition.REFUSED,
                evaluation=evaluation,
            )
        return _SearchHistorySourceResolution(
            disposition=_SearchHistorySourceDisposition.NOT_APPLICABLE,
            evaluation=evaluation,
        )

    verified = _verify_search_source_profile_receipt(
        store=store,
        evaluation_ref=exact_ref,
        expected_params=expected_params,
        expected_scalar=expected_scalar,
        expected_proposal_id=expected_proposal_id,
        expected_provenance_ref=expected_provenance_ref,
    )
    if verified is None:
        return _SearchHistorySourceResolution(
            disposition=_SearchHistorySourceDisposition.REFUSED,
            evaluation=evaluation,
        )
    return _SearchHistorySourceResolution(
        disposition=_SearchHistorySourceDisposition.VERIFIED,
        evaluation=evaluation,
        verified=verified,
    )


def _verify_search_source_profile_receipt(
    *,
    store: CoreJSONArtifactStore,
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

    try:
        exact_evaluation_ref = ArtifactRef.model_validate(evaluation_ref)
        reader = store
        evaluation_manifest = reader.get_manifest(exact_evaluation_ref)
        if not _search_source_manifest_schema_matches(
            evaluation_manifest,
            name="polisyos.scientist.methods.autotune.BenchmarkEvaluation",
        ):
            return None
        raw_evaluation = load_core_json_artifact(reader, exact_evaluation_ref)
        evaluation = BenchmarkEvaluation.model_validate(raw_evaluation)
        if not _search_evaluation_manifest_matches(
            evaluation_manifest, exact_evaluation_ref, evaluation
        ):
            return None
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
        expected_objective_fingerprint = _configured_search_metric_profile_fingerprint(
            receipt.get("metric"), receipt.get("direction"), receipt.get("unit")
        )
        if (
            expected_objective_fingerprint is None
            or profile.objective_fingerprint != expected_objective_fingerprint
            or _search_source_fingerprint(dict(profile_payload)) != receipt.get("profile_sha256")
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

        if not all(
            _search_source_manifest_input_matches(evaluation_manifest, role, ref)
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
            snapshot = validate_core_model_json_artifact(DataSnapshot, reader, data_snapshot_ref)
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
        if any(ref.manifest_profile_sha256 is None for ref in expected_result_inputs.values()):
            return None
        result_input_edges = [
            item for item in result_manifest.inputs if item.role.startswith("input:")
        ]
        actual_result_inputs = {item.role: item for item in result_input_edges}
        if (
            len(result_input_edges) != len(actual_result_inputs)
            or set(actual_result_inputs) != set(expected_result_inputs)
            or not all(
                actual_result_inputs[role].artifact_id == ref.artifact_id
                and actual_result_inputs[role].manifest_profile_sha256
                == ref.manifest_profile_sha256
                for role, ref in expected_result_inputs.items()
            )
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
        # Metadata is only a projection; the actual MethodJob output is the
        # source. Receipt, projected unit and selected result must all agree.
        if (
            source_unit != receipt.get("unit")
            or evaluation.metadata.get("metric_unit") != source_unit
        ):
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
        expected_objective = _configured_search_metric_profile_fingerprint(
            metric, direction.value, receipt.get("unit")
        )
        if expected_objective is None or profile.objective_fingerprint != expected_objective:
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
                evaluation_manifest,
                "search_gp_fit_basis",
                fit_basis_ref,
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
    reader: CoreJSONArtifactStore,
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
        expected_objective_fingerprint = _configured_search_metric_profile_fingerprint(
            run_profile.primary_metric, run_profile.direction, run_profile.unit
        )
        if (
            expected_objective_fingerprint is None
            or run_profile.objective_fingerprint != expected_objective_fingerprint
        ):
            return False
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
        snapshot = validate_core_model_json_artifact(DataSnapshot, reader, data_snapshot_ref)
        if (
            snapshot_manifest.kind != "fabric.data_snapshot"
            or snapshot.data_ref != data_ref
            or not _search_source_manifest_input_matches(snapshot_manifest, "data_ref", data_ref)
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
    reader: CoreJSONArtifactStore,
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
            (
                "acquisition_evaluation",
                str(ref.artifact_id),
                ref.manifest_profile_sha256,
            )
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
            ObjectiveScoreStatus,
            ObjectiveValue,
            _assess_search_metric,
            _configured_search_metric_binding,
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
        objective_binding = _configured_search_metric_binding(
            run_profile.primary_metric, run_profile.direction, run_profile.unit
        )
        if objective_binding is None:
            return False
        objective_name, objective_direction, _ = objective_binding
        optimizer = BayesianOptimizer(
            native_space,
            config=BayesianConfig(**fit_config),
            objective_name=objective_name,
            objective_source_direction=run_profile.direction,
            objective_source_unit=run_profile.unit,
        )
        if not optimizer.native_gp_ready or str(optimizer._device) != fit_basis.fit_backend:
            return False
        optimizer.set_search_run_profile(
            context_fingerprint=run_profile.context_fingerprint,
            objective_fingerprint=run_profile.objective_fingerprint,
            objective_unit=run_profile.unit,
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
            raw_metric = source_evaluation.primary_value(
                split=BenchmarkSplit(run_profile.split), metric=run_profile.primary_metric
            )
            source_result = (
                {
                    "metrics": {run_profile.primary_metric: raw_metric},
                    "metric_units": {run_profile.primary_metric: run_profile.unit},
                }
                if raw_metric is not None and run_profile.unit is not None
                else None
            )
            assessment = (
                _assess_search_metric(
                    source_result,
                    run_profile.primary_metric,
                    run_profile.direction,
                    run_profile.unit,
                )
                if source_result is not None
                else None
            )
            if (
                not isinstance(params, Mapping)
                or isinstance(scalar, bool)
                or not isinstance(scalar, (int, float))
                or not isfinite(float(scalar))
                or source_result is None
                or assessment is None
                or assessment.status is not ObjectiveScoreStatus.AVAILABLE
                or assessment.value is None
                or assessment.value != float(scalar)
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
                        name=objective_name,
                        raw_value=float(assessment.value),
                        direction=objective_direction,
                        score_status=assessment.status,
                        score_assessment=assessment,
                    )
                ],
                scalar_score=float(assessment.value),
                stage_a_passed=True,
                stage_b_result=source_result,
                status=EvaluationStatus.SUCCESS,
                provenance_ref=str(source_receipt["method_result_ref"]["artifact_id"]),
                score_status=assessment.status,
                score_assessment=assessment,
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
        predicted_mean = prediction["predicted_mean"]
        predicted_std = prediction["predicted_std"]
        acquisition_value = prediction["acquisition_value"]
        if not isinstance(predicted_mean, (int, float)):
            return False
        if not isinstance(predicted_std, (int, float)):
            return False
        if not isinstance(acquisition_value, (int, float)):
            return False
        return (
            proposal_uncertainty.acquisition_type == prediction["acquisition_type"]
            and isclose(
                proposal_uncertainty.predicted_mean,
                predicted_mean,
                rel_tol=1e-10,
                abs_tol=1e-12,
            )
            and isclose(
                proposal_uncertainty.predicted_std,
                predicted_std,
                rel_tol=1e-10,
                abs_tol=1e-12,
            )
            and isclose(
                proposal_uncertainty.acquisition_value,
                acquisition_value,
                rel_tol=1e-10,
                abs_tol=1e-12,
            )
        )
    except (KeyError, OSError, RuntimeError, TypeError, ValueError, ValidationError):
        return False
