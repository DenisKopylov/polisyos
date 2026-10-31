"""Versioned source basis and bounded replay for Phase D.4 challenge cases."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.artifacts import (
    ArtifactManifest,
    ArtifactRef,
    CoreJSONArtifactStore,
    InputRef,
    ProducerInfo,
    PutOptions,
    SchemaInfo,
    artifact_manifest_profile_sha256,
    artifact_ref_for_manifest,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
    resolve_manifest_by_profile,
)
from polisyos.core.canon import CanonSpec
from polisyos.scientist.methods.autotune.models import (
    _BENCHMARK_EVALUATION_SCHEMA_NAME,
    BenchmarkEvaluation,
    BenchmarkSplit,
    _benchmark_evaluation_artifact_kind,
)

if TYPE_CHECKING:
    from polisyos.scientist.methods.backtesting.adversarial import ChallengeSuiteResult

PHASE_D4_REPLAY_SOURCE_ARTIFACT_KIND = "scientist.phase_d4_replay_source"
PHASE_D4_REPLAY_SOURCE_SCHEMA_NAME = "polisyos.scientist.PhaseD4ReplaySource"
PHASE_D4_REPLAY_SOURCE_SCHEMA_VERSION = "1.1"
PHASE_D4_REPLAY_SOURCE_INPUT_ROLE = "phase_d4_replay_source"
PHASE_D4_SELECTION_INPUT_ROLE = "selection_evaluation"
PHASE_D4_SELECTED_EVALUATION_INPUT_ROLE = "phase_d4_selected_suite_evaluation"

_PHASE_D4_PARAM_KEYS = frozenset(
    {
        "strategic_scm",
        "strategic_payoff_tables",
        "macro_strategic_payoff_tables",
        "baseline_policy_value",
        "policy_value",
        "selection_score",
        "strategic_response",
        "strategic_response_summary",
        "abstraction_preservation_type",
        "abm_alignment_warnings",
    }
)
_PHASE_D4_ARTIFACT_INDEX_KEYS = frozenset(
    {
        "abm_alignment_report_ref",
        "abstraction_certificate_ref",
        "finite_state_abstraction_map_ref",
        "strategic_response_bundle_ref",
    }
)


type _SourceParameterValue = (
    str
    | int
    | bool
    | float
    | Decimal
    | None
    | list[_SourceParameterValue]
    | dict[str, _SourceParameterValue]
)


class PhaseD4ReplaySource(BaseModel):
    """Exact selected runtime inputs consumed to produce one D.4 suite family."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0", "1.1"] = "1.1"
    authority_purpose: Literal["recompute_phase_d4_case_truth"] = "recompute_phase_d4_case_truth"
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    run_id: str = Field(min_length=1, max_length=128)
    loop_id: str = Field(min_length=1, max_length=128)
    candidate_ref: ArtifactRef
    selection_evaluation_ref: ArtifactRef
    params: dict[str, _SourceParameterValue] = Field(default_factory=dict)
    artifacts_index: dict[str, ArtifactRef] = Field(default_factory=dict)

    @field_validator("params", mode="before")
    @classmethod
    def validate_source_parameters(cls, value: Any) -> Any:
        """Reject unsupported values before Pydantic can coerce their types."""
        return _json_value(value)

    @model_validator(mode="after")
    def validate_selected_inputs(self) -> PhaseD4ReplaySource:
        """Reject incomplete or unselected runtime source references."""
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise ValueError("phase_d4_replay_source_capture_time_must_be_aware")
        if set(self.params) - _PHASE_D4_PARAM_KEYS:
            raise ValueError("phase_d4_replay_source_contains_unconsumed_parameters")
        if set(self.artifacts_index) - _PHASE_D4_ARTIFACT_INDEX_KEYS:
            raise ValueError("phase_d4_replay_source_contains_unconsumed_artifact_refs")
        _json_value(self.params, allow_decimal=self.schema_version == "1.1")
        refs = [self.candidate_ref, self.selection_evaluation_ref, *self.artifacts_index.values()]
        if any(ref.manifest_profile_sha256 is None for ref in refs):
            raise ValueError("phase_d4_replay_source_selected_profile_missing")
        return self


class PhaseD4SuiteSelection(BaseModel):
    """One selected D.4 suite and its exact current evaluation/source refs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    suite_id: str = Field(min_length=1, max_length=128)
    suite_version: str = Field(min_length=1, max_length=64)
    benchmark_evaluation_ref: ArtifactRef
    replay_source_ref: ArtifactRef


class PhaseD4SuiteRoster(BaseModel):
    """Typed D.4 suite roster recomputed from the current selected CAS refs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(min_length=1, max_length=128)
    loop_id: str = Field(min_length=1, max_length=128)
    candidate_ref: ArtifactRef
    selection_evaluation_ref: ArtifactRef
    rotating_evaluation_refs: list[ArtifactRef] = Field(default_factory=list)
    suites: list[PhaseD4SuiteSelection] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_selected_roster(self) -> PhaseD4SuiteRoster:
        """Reject duplicate evaluation refs and duplicate typed suite identities."""
        selected_keys = [item.model_dump_json() for item in self.rotating_evaluation_refs]
        suite_ids = [item.suite_id for item in self.suites]
        suite_refs = [item.benchmark_evaluation_ref.model_dump_json() for item in self.suites]
        if len(selected_keys) != len(set(selected_keys)):
            raise ValueError("phase_d4_selected_evaluation_ref_duplicated")
        if len(suite_ids) != len(set(suite_ids)):
            raise ValueError("phase_d4_selected_suite_id_duplicated")
        if len(suite_refs) != len(set(suite_refs)):
            raise ValueError("phase_d4_selected_suite_evaluation_duplicated")
        if any(item not in set(selected_keys) for item in suite_refs):
            raise ValueError("phase_d4_suite_evaluation_outside_selected_roster")
        if (
            self.candidate_ref.manifest_profile_sha256 is None
            or self.selection_evaluation_ref.manifest_profile_sha256 is None
            or any(item.manifest_profile_sha256 is None for item in self.rotating_evaluation_refs)
        ):
            raise ValueError("phase_d4_selected_roster_profile_missing")
        return self

    @property
    def suite_evaluation_refs(self) -> list[ArtifactRef]:
        """Return the exact current D.4 evaluation refs in selected order."""
        return [item.benchmark_evaluation_ref for item in self.suites]


class PhaseD4ReplayError(ValueError):
    """A source-bound D.4 case replay or selected roster could not be established."""


def _has_exact_single_input(manifest: ArtifactManifest, ref: ArtifactRef, *, role: str) -> bool:
    expected = input_ref_from_artifact_ref(ref, role=role).model_dump_json()
    actual = [item.model_dump_json() for item in manifest.inputs if item.role == role]
    return actual == [expected]


def _json_value(value: Any, *, allow_decimal: bool = True) -> _SourceParameterValue:
    """Project supported source values for the existing Core typed JSON codec."""
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="python", by_alias=True)
    elif isinstance(value, Enum):
        value = value.value
    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is Decimal:
        if not allow_decimal:
            raise ValueError("phase_d4_replay_source_decimal_requires_v1_1")
        if not value.is_finite():
            raise ValueError("phase_d4_replay_source_non_finite_parameter")
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("phase_d4_replay_source_non_finite_parameter")
        return value
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise ValueError("phase_d4_replay_source_parameter_key_invalid")
        return {key: _json_value(item, allow_decimal=allow_decimal) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item, allow_decimal=allow_decimal) for item in value]
    raise ValueError("phase_d4_replay_source_parameter_not_json_compatible")


def build_phase_d4_replay_source(
    *,
    run_id: str,
    loop_id: str,
    candidate_ref: ArtifactRef,
    selection_evaluation_ref: ArtifactRef,
    selection_evaluation: BenchmarkEvaluation,
    params: Mapping[str, Any],
    artifacts_index: Mapping[str, ArtifactRef],
    store: CoreJSONArtifactStore,
) -> PhaseD4ReplaySource:
    """Build a compact source snapshot after matching the selected evaluation in CAS."""
    stored_selection = load_selected_benchmark_evaluation(store, selection_evaluation_ref)
    selection_manifest = store.get_manifest(selection_evaluation_ref)
    if not _has_exact_single_input(selection_manifest, candidate_ref, role="candidate"):
        raise ValueError("phase_d4_replay_source_selection_candidate_lineage_mismatch")
    if (
        stored_selection != selection_evaluation
        or stored_selection.suite_id != "policy_selection"
        or stored_selection.resolved_runtime_split_type() is not BenchmarkSplit.SELECTION
        or stored_selection.loop_id != loop_id
        or stored_selection.candidate_ref != candidate_ref
    ):
        raise ValueError("phase_d4_replay_source_selection_binding_mismatch")
    projected_params = {
        key: _json_value(params[key]) for key in sorted(_PHASE_D4_PARAM_KEYS) if key in params
    }
    projected_artifacts: dict[str, ArtifactRef] = {}
    for key, raw_ref in artifacts_index.items():
        if key not in _PHASE_D4_ARTIFACT_INDEX_KEYS:
            continue
        ref = raw_ref if isinstance(raw_ref, ArtifactRef) else ArtifactRef.model_validate(raw_ref)
        if ref.manifest_profile_sha256 is None:
            raise ValueError("phase_d4_replay_source_artifact_profile_missing")
        projected_artifacts[key] = ref
    return PhaseD4ReplaySource(
        run_id=run_id,
        loop_id=loop_id,
        candidate_ref=candidate_ref,
        selection_evaluation_ref=selection_evaluation_ref,
        params=projected_params,
        artifacts_index=projected_artifacts,
    )


def persist_phase_d4_replay_source(
    store: CoreJSONArtifactStore,
    source: PhaseD4ReplaySource,
) -> ArtifactRef:
    """Persist the selected D.4 input projection with complete direct source edges."""
    inputs = [
        input_ref_from_artifact_ref(source.candidate_ref, role="candidate"),
        input_ref_from_artifact_ref(
            source.selection_evaluation_ref,
            role=PHASE_D4_SELECTION_INPUT_ROLE,
        ),
    ]
    inputs.extend(
        input_ref_from_artifact_ref(ref, role=f"phase_d4_input:{key}")
        for key, ref in sorted(source.artifacts_index.items())
    )
    return store.put_json(
        source.model_dump(mode="python"),
        PutOptions(
            kind=PHASE_D4_REPLAY_SOURCE_ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=PHASE_D4_REPLAY_SOURCE_SCHEMA_NAME,
                version=source.schema_version,
            ),
            producer=ProducerInfo(
                component="polisyos.scientist.methods.backtesting.phase_d4_source",
                version="1.1",
            ),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
        return_selected_profile=True,
    )


def load_selected_phase_d4_replay_source(
    store: CoreJSONArtifactStore,
    ref: ArtifactRef,
) -> tuple[PhaseD4ReplaySource, ArtifactManifest]:
    """Load a source basis only after exact manifest, schema, producer, and edges match."""
    if ref.manifest_profile_sha256 is None:
        raise PhaseD4ReplayError("phase_d4_replay_source_profile_missing")
    try:
        manifest = store.get_manifest(ref)
    except Exception as exc:
        raise PhaseD4ReplayError("phase_d4_replay_source_manifest_unreadable") from exc
    if (
        manifest.artifact_id != ref.artifact_id
        or manifest.kind != PHASE_D4_REPLAY_SOURCE_ARTIFACT_KIND
        or ref.kind != PHASE_D4_REPLAY_SOURCE_ARTIFACT_KIND
        or manifest.media_type != "application/json"
        or ref.media_type != "application/json"
        or manifest.artifact_schema is None
        or manifest.artifact_schema.name != PHASE_D4_REPLAY_SOURCE_SCHEMA_NAME
        or manifest.artifact_schema.version not in {"1.0", "1.1"}
        or manifest.producer is None
        or manifest.producer.component != "polisyos.scientist.methods.backtesting.phase_d4_source"
        or manifest.producer.version not in {"1.0", "1.1"}
        or artifact_manifest_profile_sha256(manifest) != ref.manifest_profile_sha256
    ):
        raise PhaseD4ReplayError("phase_d4_replay_source_manifest_mismatch")
    try:
        source = PhaseD4ReplaySource.model_validate(
            load_core_json_artifact(
                store,
                ref,
                manifest_profile_sha256=ref.manifest_profile_sha256,
            )
        )
    except Exception as exc:
        raise PhaseD4ReplayError("phase_d4_replay_source_body_unreadable") from exc
    if manifest.artifact_schema.version != source.schema_version:
        raise PhaseD4ReplayError("phase_d4_replay_source_schema_version_mismatch")
    expected_inputs = [
        input_ref_from_artifact_ref(source.candidate_ref, role="candidate"),
        input_ref_from_artifact_ref(
            source.selection_evaluation_ref,
            role=PHASE_D4_SELECTION_INPUT_ROLE,
        ),
    ]
    expected_inputs.extend(
        input_ref_from_artifact_ref(ref, role=f"phase_d4_input:{key}")
        for key, ref in sorted(source.artifacts_index.items())
    )
    if sorted(item.model_dump_json() for item in manifest.inputs) != sorted(
        item.model_dump_json() for item in expected_inputs
    ):
        raise PhaseD4ReplayError("phase_d4_replay_source_lineage_mismatch")
    return source, manifest


def load_selected_benchmark_evaluation(
    store: CoreJSONArtifactStore,
    ref: ArtifactRef,
) -> BenchmarkEvaluation:
    """Load one selected benchmark evaluation under its persisted owner schema."""
    if ref.manifest_profile_sha256 is None:
        raise PhaseD4ReplayError("phase_d4_selection_profile_missing")
    try:
        manifest = store.get_manifest(ref)
        payload = load_core_json_artifact(
            store,
            ref,
            manifest_profile_sha256=ref.manifest_profile_sha256,
        )
        evaluation = BenchmarkEvaluation.model_validate(payload)
    except Exception as exc:
        raise PhaseD4ReplayError("phase_d4_selection_evaluation_unreadable") from exc
    if (
        artifact_manifest_profile_sha256(manifest) != ref.manifest_profile_sha256
        or manifest.artifact_id != ref.artifact_id
        or manifest.kind != _benchmark_evaluation_artifact_kind(evaluation.loop_id)
        or ref.kind != manifest.kind
        or manifest.media_type != "application/json"
        or ref.media_type != manifest.media_type
        or manifest.artifact_schema is None
        or manifest.artifact_schema.name != _BENCHMARK_EVALUATION_SCHEMA_NAME
        or manifest.artifact_schema.version != evaluation.suite_version
        or manifest.producer is None
        or manifest.producer.component != "polisyos.scientist.methods.autotune.benchmark_evaluator"
        or manifest.producer.version not in {"1.0", "2.0"}
        or not _has_exact_single_input(
            manifest,
            evaluation.candidate_ref,
            role="candidate",
        )
    ):
        raise PhaseD4ReplayError("phase_d4_selection_evaluation_manifest_mismatch")
    return evaluation


def build_phase_d4_suite_roster(
    store: CoreJSONArtifactStore,
    *,
    rotating_evaluation_refs: Sequence[ArtifactRef] | None,
    expected_candidate_ref: ArtifactRef,
    expected_selection_evaluation_ref: ArtifactRef,
    expected_run_id: str,
    expected_loop_id: str,
) -> PhaseD4SuiteRoster:
    """Resolve a complete current D.4 roster from selected benchmark CAS refs.

    A missing ref sequence is not an empty roster. An explicit empty sequence is
    valid only as the current caller's statement that it selected no rotating
    evaluations. Every provided ref is loaded and bound to the current candidate
    and loop; D.4 membership is derived from its typed replay-source edge, not
    from a suite name or report/component identifier.
    """
    if rotating_evaluation_refs is None:
        raise PhaseD4ReplayError("phase_d4_selected_roster_missing")
    if (
        not expected_run_id.strip()
        or not expected_loop_id.strip()
        or expected_candidate_ref.manifest_profile_sha256 is None
        or expected_selection_evaluation_ref.manifest_profile_sha256 is None
    ):
        raise PhaseD4ReplayError("phase_d4_selected_roster_context_missing")
    selected_refs = list(rotating_evaluation_refs)
    selected_keys = [item.model_dump_json() for item in selected_refs]
    if len(selected_keys) != len(set(selected_keys)):
        raise PhaseD4ReplayError("phase_d4_selected_evaluation_ref_duplicated")

    selections: list[PhaseD4SuiteSelection] = []
    for evaluation_ref in selected_refs:
        if evaluation_ref.manifest_profile_sha256 is None:
            raise PhaseD4ReplayError("phase_d4_selected_evaluation_profile_missing")
        try:
            evaluation = load_selected_benchmark_evaluation(store, evaluation_ref)
            evaluation_manifest = store.get_manifest(evaluation_ref)
        except Exception as exc:
            raise PhaseD4ReplayError("phase_d4_selected_evaluation_unreadable") from exc
        if (
            evaluation.candidate_ref != expected_candidate_ref
            or evaluation.loop_id != expected_loop_id
            or evaluation.resolved_runtime_split_type() is not BenchmarkSplit.ROTATING_CHALLENGE
            or not _has_exact_single_input(
                evaluation_manifest,
                expected_candidate_ref,
                role="candidate",
            )
        ):
            raise PhaseD4ReplayError("phase_d4_selected_evaluation_context_mismatch")

        replay_inputs = [
            item
            for item in evaluation_manifest.inputs
            if item.role == PHASE_D4_REPLAY_SOURCE_INPUT_ROLE
        ]
        if not replay_inputs:
            continue
        if len(replay_inputs) != 1 or replay_inputs[0].manifest_profile_sha256 is None:
            raise PhaseD4ReplayError("phase_d4_selected_evaluation_replay_edge_invalid")
        if not _has_exact_single_input(
            evaluation_manifest,
            expected_selection_evaluation_ref,
            role=PHASE_D4_SELECTION_INPUT_ROLE,
        ):
            raise PhaseD4ReplayError("phase_d4_selected_evaluation_selection_edge_mismatch")
        try:
            replay_manifest = resolve_manifest_by_profile(
                store,
                replay_inputs[0].artifact_id,
                replay_inputs[0].manifest_profile_sha256,
            )
            replay_source_ref = artifact_ref_for_manifest(replay_manifest)
            replay_source, _ = load_selected_phase_d4_replay_source(store, replay_source_ref)
        except Exception as exc:
            raise PhaseD4ReplayError("phase_d4_selected_replay_source_unreadable") from exc
        if (
            replay_source.run_id != expected_run_id
            or replay_source.loop_id != expected_loop_id
            or replay_source.candidate_ref != expected_candidate_ref
            or replay_source.selection_evaluation_ref != expected_selection_evaluation_ref
        ):
            raise PhaseD4ReplayError("phase_d4_selected_replay_source_context_mismatch")
        selections.append(
            PhaseD4SuiteSelection(
                suite_id=evaluation.suite_id,
                suite_version=evaluation.suite_version,
                benchmark_evaluation_ref=evaluation_ref,
                replay_source_ref=replay_source_ref,
            )
        )

    selections.sort(key=lambda item: item.suite_id)
    try:
        return PhaseD4SuiteRoster(
            run_id=expected_run_id,
            loop_id=expected_loop_id,
            candidate_ref=expected_candidate_ref,
            selection_evaluation_ref=expected_selection_evaluation_ref,
            rotating_evaluation_refs=selected_refs,
            suites=selections,
        )
    except ValueError as exc:
        raise PhaseD4ReplayError(str(exc)) from exc


def revalidate_phase_d4_suite_roster(
    store: CoreJSONArtifactStore,
    roster: PhaseD4SuiteRoster,
) -> PhaseD4SuiteRoster:
    """Recompute a roster's entire selected CAS mapping before a consumer uses it."""
    actual = build_phase_d4_suite_roster(
        store,
        rotating_evaluation_refs=roster.rotating_evaluation_refs,
        expected_candidate_ref=roster.candidate_ref,
        expected_selection_evaluation_ref=roster.selection_evaluation_ref,
        expected_run_id=roster.run_id,
        expected_loop_id=roster.loop_id,
    )
    if actual != roster:
        raise PhaseD4ReplayError("phase_d4_selected_roster_projection_mismatch")
    return actual


def replay_phase_d4_suite(
    store: CoreJSONArtifactStore,
    *,
    source_ref: ArtifactRef,
    expected_candidate_ref: ArtifactRef,
    expected_selection_evaluation_ref: ArtifactRef,
    expected_loop_id: str,
    expected_suite_id: str,
    expected_suite_version: str,
    expected_run_id: str | None = None,
) -> ChallengeSuiteResult:
    """Re-run the canonical D.4 suite evaluator from its selected inputs."""
    source, _source_manifest = load_selected_phase_d4_replay_source(store, source_ref)
    if (
        source.candidate_ref != expected_candidate_ref
        or source.selection_evaluation_ref != expected_selection_evaluation_ref
        or source.loop_id != expected_loop_id
        or (expected_run_id is not None and source.run_id != expected_run_id)
    ):
        raise PhaseD4ReplayError("phase_d4_replay_source_expected_context_mismatch")
    selection = load_selected_benchmark_evaluation(store, source.selection_evaluation_ref)
    if (
        selection.suite_id != "policy_selection"
        or selection.resolved_runtime_split_type() is not BenchmarkSplit.SELECTION
        or selection.candidate_ref != source.candidate_ref
        or selection.loop_id != source.loop_id
    ):
        raise PhaseD4ReplayError("phase_d4_replay_selection_context_mismatch")
    from polisyos.scientist.methods.backtesting.adversarial import run_phase_d4_challenge_suites

    try:
        suites, _warnings = run_phase_d4_challenge_suites(
            store=store,
            run_id=source.run_id,
            loop_id=source.loop_id,
            candidate_ref=source.candidate_ref,
            params=source.params,
            artifacts_index=source.artifacts_index,
            selection_metadata=selection.metadata,
        )
    except Exception as exc:
        raise PhaseD4ReplayError("phase_d4_replay_evaluator_failed") from exc
    selected = [item for item in suites if item.suite_id == expected_suite_id]
    if len(selected) != 1:
        raise PhaseD4ReplayError("phase_d4_replay_suite_missing_or_duplicated")
    suite = selected[0]
    if (
        suite.suite_version != expected_suite_version
        or suite.benchmark_evaluation.loop_id != expected_loop_id
        or suite.benchmark_evaluation.candidate_ref != expected_candidate_ref
    ):
        raise PhaseD4ReplayError("phase_d4_replay_suite_identity_mismatch")
    return suite
