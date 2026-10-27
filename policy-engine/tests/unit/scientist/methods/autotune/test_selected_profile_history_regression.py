"""Test-only witness for selected Search source manifest identity.

The pinned base omits metric_units from stage B. The explicit test-only bridge
copies the unit from the real selected MethodJob output so that the separate
selected-profile property can be falsified without inventing a source unit.
"""

from copy import deepcopy
from dataclasses import replace
from typing import Any, ClassVar

import pytest

from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    ProducerInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.foundry.methods import MethodRegistry, MethodSignature
from polisyos.scientist.methods.autotune import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSuite,
    ChampionRegistry,
    SearchLoopRunner,
    SearchLoopSpec,
    persist_benchmark_suite,
)
from polisyos.scientist.methods.autotune.bayesian_generator import (
    BayesianCandidateGenerator,
    SearchSpace,
)
from polisyos.scientist.methods.autotune.models import (
    load_json_artifact,
    load_model_artifact,
)
from polisyos.scientist.methods.autotune.runtime import (
    MethodJobBenchmarkEvaluator,
    PydanticMutationCodec,
    _verify_search_source_profile_receipt,
)
from unit.scientist.methods.autotune.test_v5_search_pipeline import (
    _policy,
    _selected_evaluation_ref,
    _V5Mutation,
    _V5ScoreMethod,
)


class _SelectedProfileUnitMethod(_V5ScoreMethod):
    """Reuse the existing dimensionless signature and declare its output unit."""

    signature: ClassVar[MethodSignature] = replace(
        _V5ScoreMethod.signature, name="selected_profile_unit_score"
    )

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "score": float(state["value"]) + float(params.get("offset", 0.0)),
            "metric_units": {"score": "dimensionless"},
        }


@pytest.fixture(autouse=True)
def _isolate_method_registry():
    MethodRegistry.reset_instance()
    yield
    MethodRegistry.reset_instance()


def test_history_refuses_same_id_with_different_selected_source_profile(
    tmp_path,
) -> None:
    """A same-payload alternative manifest must not satisfy an exact source join."""
    MethodRegistry.get_instance().register(_SelectedProfileUnitMethod, override=True)
    store = FileSystemCAS(tmp_path / "cas")
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="profile_identity_probe_suite", kind="method_job"),
    )
    generator = BayesianCandidateGenerator(
        SearchSpace(bounds=[{"name": "value", "lower": 0.0, "upper": 1.0}]),
        unit="dimensionless",
        compare_split=BenchmarkSplit.SELECTION,
        n_initial=2,
        seed=20261027,
    )
    assert generator.botorch_available, "setup: supported Bayesian backend unavailable"
    spec = SearchLoopSpec(
        loop_id="v5_search",
        mutation_codec=PydanticMutationCodec(_V5Mutation),
        candidate_generator=generator,
        benchmark_evaluator=MethodJobBenchmarkEvaluator(
            method_fqn=_SelectedProfileUnitMethod.signature.fqn,
            method_version=_SelectedProfileUnitMethod.signature.version,
            candidate_input_bindings={"value": "value"},
            split=BenchmarkSplit.SELECTION,
        ),
        promotion_policy=_policy(unit="dimensionless"),
    )
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    run = SearchLoopRunner(store=store, registry=registry).run(
        spec,
        suite_ref=suite_ref,
        context={"policy_context": {"case": "selected_profile_identity_probe"}},
        max_iterations=1,
    )
    assert len(run.history) == 1
    entry = run.history[0]
    assert entry.stage_b_result is not None
    stage_b = entry.stage_b_result
    evaluation_ref = _selected_evaluation_ref(stage_b)
    evaluation = load_model_artifact(store, evaluation_ref, BenchmarkEvaluation)
    assert evaluation.method_result_ref is not None
    source = load_json_artifact(store, evaluation.method_result_ref)
    assert isinstance(source, dict)
    output = source.get("result", source)
    assert isinstance(output, dict)
    assert output["metric_units"] == {"score": "dimensionless"}
    assert evaluation.metadata["metric_unit"] == "dimensionless"
    assert evaluation.selection_metrics["score"] == output["score"]

    # On the old producer, this is verification_missing: stage B never carries
    # its real MethodJob unit. Preserve the fact and isolate the next property.
    units_in_stage_b = stage_b["simulation_results"].get("metric_units")
    if units_in_stage_b is None:
        without_bridge = generator._history_to_evaluations([entry])[0]
        assert without_bridge.score_status.value == "unavailable"
        print(
            "UNIT_BRIDGE=test_only_from_selected_method_result; base_history=unavailable"
        )
    else:
        assert units_in_stage_b == {"score": "dimensionless"}
        print("UNIT_BRIDGE=production_stage_b; exact_output_unit_reconciled")
    bridged = deepcopy(entry)
    assert bridged.stage_b_result is not None
    bridged.stage_b_result["simulation_results"]["metric_units"] = dict(
        output["metric_units"]
    )
    positive_history = generator._history_to_evaluations([bridged])[0]
    assert positive_history.score_status.value == "available"
    assert positive_history.scalar_score is not None
    receipt = evaluation.metadata["search_source_profile_receipt"]
    assert receipt["unit"] == "dimensionless"
    assert positive_history.metadata["search_source_profile_receipt"] == receipt
    assert _verify_search_source_profile_receipt(
        store=store, evaluation_ref=evaluation_ref
    )
    assert _verify_search_source_profile_receipt(
        store=store, evaluation_ref=evaluation_ref
    )
    print("A/A=available; source_receipt=verified; selected_evaluation_reopened_twice")

    def copy_bytes_with_manifest(
        ref: ArtifactRef,
        *,
        inputs: list | None = None,
        producer: ProducerInfo | None = None,
    ) -> ArtifactRef:
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

    candidate_ref = ArtifactRef.model_validate(receipt["candidate_ref"])
    alt_candidate_ref = copy_bytes_with_manifest(
        candidate_ref,
        producer=ProducerInfo(component="tests.actual_alternate_view", version="1"),
    )
    assert alt_candidate_ref.artifact_id == candidate_ref.artifact_id
    assert alt_candidate_ref.kind == candidate_ref.kind
    assert alt_candidate_ref.media_type == candidate_ref.media_type
    assert (
        alt_candidate_ref.manifest_profile_sha256
        != candidate_ref.manifest_profile_sha256
    )
    assert store.get_bytes(alt_candidate_ref) == store.get_bytes(candidate_ref)
    evaluation_manifest = store.get_manifest(evaluation_ref)
    original_candidate_edges = [
        edge for edge in evaluation_manifest.inputs if edge.role == "candidate"
    ]
    assert original_candidate_edges == [
        input_ref_from_artifact_ref(candidate_ref, role="candidate")
    ]
    swapped_inputs = [
        input_ref_from_artifact_ref(alt_candidate_ref, role="candidate")
        if edge.role == "candidate"
        else edge
        for edge in evaluation_manifest.inputs
    ]
    swapped_ref = copy_bytes_with_manifest(evaluation_ref, inputs=swapped_inputs)
    assert swapped_ref.artifact_id == evaluation_ref.artifact_id
    assert swapped_ref.manifest_profile_sha256 != evaluation_ref.manifest_profile_sha256
    assert store.get_bytes(swapped_ref) == store.get_bytes(evaluation_ref)
    assert store.get_manifest(swapped_ref).inputs == swapped_inputs

    changed = deepcopy(bridged)
    assert changed.stage_b_result is not None
    changed.stage_b_result["metadata"]["evaluation_artifact_ref"] = (
        swapped_ref.model_dump(mode="json")
    )
    adversarial = _verify_search_source_profile_receipt(
        store=store, evaluation_ref=swapped_ref
    )
    changed_history = generator._history_to_evaluations([changed])[0]
    print(
        "A/B same_id=True same_kind=True same_media=True different_selected_profile=True "
        f"verifier={'accepted' if adversarial is not None else 'refused'} "
        f"history_status={changed_history.score_status.value} "
        f"history_scalar={changed_history.scalar_score}"
    )
    assert adversarial is None, (
        "The verifier accepted a selected evaluation edge whose candidate profile "
        "differs from the receipt, while the payload ID remained identical."
    )
    assert changed_history.scalar_score is None
    assert changed_history.score_status.value != "available"
