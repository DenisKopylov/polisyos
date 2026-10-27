"""Persisted BenchmarkEvaluation wire compatibility for source-unit projection."""

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import input_ref_from_artifact_ref, load_core_json_artifact
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.autotune import (
    BenchmarkEvaluation,
    BenchmarkSuite,
    MutationArtifact,
    persist_benchmark_evaluation,
    persist_benchmark_suite,
    persist_mutation_artifact,
)
from polisyos.scientist.methods.autotune.runtime import (
    _persist_search_benchmark_evaluation,
)


@pytest.mark.parametrize("suite_version", ["1.0", "2.0"])
@pytest.mark.parametrize("declared_unit", [None, "dimensionless"])
def test_both_evaluation_writers_preserve_the_legacy_wire_shape(
    tmp_path, suite_version: str, declared_unit: str | None
) -> None:
    """The existing strict reader accepts both producer paths and suite versions."""
    store = FileSystemCAS(tmp_path / "cas")
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="legacy_wire_suite", suite_version=suite_version),
        return_selected_profile=True,
    )
    candidate_ref = persist_mutation_artifact(
        store,
        MutationArtifact(loop_id="legacy_wire"),
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
        return_selected_profile=True,
    )
    metadata = {} if declared_unit is None else {"metric_unit": declared_unit}
    evaluation = BenchmarkEvaluation(
        loop_id="legacy_wire",
        suite_id="legacy_wire_suite",
        suite_version=suite_version,
        candidate_ref=candidate_ref,
        selection_metrics={"score": 0.5},
        metadata=metadata,
    )
    public_ref = persist_benchmark_evaluation(
        store,
        evaluation,
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
        return_selected_profile=True,
    )
    search_ref = _persist_search_benchmark_evaluation(store, evaluation, suite_ref=suite_ref)
    assert public_ref.artifact_id == search_ref.artifact_id
    assert public_ref.manifest_profile_sha256 != search_ref.manifest_profile_sha256
    for ref, producer_version in ((public_ref, "1.0"), (search_ref, "2.0")):
        manifest = store.get_manifest(ref)
        assert manifest.artifact_schema is not None
        assert manifest.artifact_schema.name == (
            "polisyos.scientist.methods.autotune.BenchmarkEvaluation"
        )
        assert manifest.artifact_schema.version == suite_version
        assert manifest.producer is not None
        assert manifest.producer.version == producer_version
        payload = load_core_json_artifact(store, ref)
        assert "metric_units" not in payload
        assert payload["metadata"] == metadata
        assert BenchmarkEvaluation.model_validate(payload) == evaluation
        # The old strict model did not admit a new top-level unit field.
        with pytest.raises(ValidationError):
            BenchmarkEvaluation.model_validate({**payload, "metric_units": {"score": "1"}})


def test_generic_candidate_parameters_bind_nested_producer_payload(tmp_path) -> None:
    """The generic selected candidate, not a replacement X, owns nested parameters."""
    from polisyos.scientist.methods.autotune.source_profile_verification import (
        _resolve_search_history_source,
        _SearchHistorySourceDisposition,
    )

    class NestedCandidate(MutationArtifact):
        params: dict[str, float]

    store = FileSystemCAS(tmp_path / "cas")
    suite_ref = persist_benchmark_suite(
        store, BenchmarkSuite(suite_id="nested_params"), return_selected_profile=True
    )
    candidate_ref = persist_mutation_artifact(
        store,
        NestedCandidate(loop_id="nested_params", params={"value": 0.4}),
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
        return_selected_profile=True,
    )
    evaluation = BenchmarkEvaluation(
        loop_id="nested_params",
        suite_id="nested_params",
        candidate_ref=candidate_ref,
        selection_metrics={"score": 0.4},
        metadata={"metric_unit": "dimensionless"},
    )
    evaluation_ref = _persist_search_benchmark_evaluation(store, evaluation, suite_ref=suite_ref)
    correct = _resolve_search_history_source(
        store=store, evaluation_ref=evaluation_ref, expected_params={"value": 0.4}
    )
    replaced = _resolve_search_history_source(
        store=store, evaluation_ref=evaluation_ref, expected_params={"value": 0.6}
    )
    assert correct.disposition is _SearchHistorySourceDisposition.NOT_APPLICABLE
    assert replaced.disposition is _SearchHistorySourceDisposition.REFUSED

    from polisyos.core.artifacts.manifest import ProducerInfo
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions

    def with_manifest(ref, *, inputs=None, producer=None):
        manifest = store.get_manifest(ref)
        return store.put_bytes(
            store.get_bytes(ref),
            ArtifactWriteOptions(
                kind=manifest.kind,
                media_type=manifest.media_type,
                schema=manifest.artifact_schema,
                producer=manifest.producer if producer is None else producer,
                env=manifest.env,
                inputs=list(manifest.inputs) if inputs is None else inputs,
                canon=manifest.canon,
                governance=manifest.governance,
                tenant_context=manifest.tenant_context,
                same_input_closure=manifest.same_input_closure,
                authority=manifest.authority,
                warnings=manifest.warnings,
            ),
            return_selected_profile=True,
        )

    alternate_suite = with_manifest(
        suite_ref,
        producer=ProducerInfo(component="tests.alternate_suite", version="1.0"),
    )
    assert alternate_suite.artifact_id == suite_ref.artifact_id
    assert alternate_suite.manifest_profile_sha256 != suite_ref.manifest_profile_sha256
    evaluation_manifest = store.get_manifest(evaluation_ref)
    for suite_edge in (
        input_ref_from_artifact_ref(alternate_suite, role="benchmark_suite"),
        input_ref_from_artifact_ref(suite_ref, role="benchmark_suite").model_copy(
            update={"manifest_profile_sha256": None}
        ),
    ):
        changed_inputs = [
            suite_edge if edge.role == "benchmark_suite" else edge
            for edge in evaluation_manifest.inputs
        ]
        changed_ref = with_manifest(evaluation_ref, inputs=changed_inputs)
        assert changed_ref.artifact_id == evaluation_ref.artifact_id
        # Old-shape payload stays readable, but the exact history join refuses.
        assert BenchmarkEvaluation.model_validate(load_core_json_artifact(store, changed_ref))
        assert (
            _resolve_search_history_source(
                store=store, evaluation_ref=changed_ref, expected_params={"value": 0.4}
            ).disposition
            is _SearchHistorySourceDisposition.REFUSED
        )

    # A genuinely legacy candidate and evaluation can both select the same
    # unprofiled suite. The payload is readable, but its view is not known.
    unselected_suite = suite_ref.model_copy(update={"manifest_profile_sha256": None})
    legacy_candidate = persist_mutation_artifact(
        store,
        NestedCandidate(loop_id="nested_params", params={"value": 0.4}),
        inputs=[input_ref_from_artifact_ref(unselected_suite, role="benchmark_suite")],
        return_selected_profile=True,
    )
    legacy_evaluation = evaluation.model_copy(update={"candidate_ref": legacy_candidate})
    legacy_ref = _persist_search_benchmark_evaluation(
        store, legacy_evaluation, suite_ref=unselected_suite
    )
    assert BenchmarkEvaluation.model_validate(load_core_json_artifact(store, legacy_ref))
    assert (
        _resolve_search_history_source(
            store=store, evaluation_ref=legacy_ref, expected_params={"value": 0.4}
        ).disposition
        is _SearchHistorySourceDisposition.REFUSED
    )
