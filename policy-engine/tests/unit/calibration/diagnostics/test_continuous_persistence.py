"""Real ordered-pair persistence and fresh continuous-calibration recomputation."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from polisyos.calibration import (
    load_continuous_evaluation,
    persist_continuous_evaluation,
    to_validation_report,
)
from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactWriteOptions,
    CoreJsonReadLimits,
    ProducerInfo,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec, from_canonical_bytes

_CANON = CanonSpec(forbid_floats=False, exclude_none=False)


def _pairs(covered: int = 95) -> tuple[list[float], list[tuple[float, float]]]:
    outcomes = [float(i) for i in range(100)]
    intervals = [(value - 0.1, value + 0.1) for value in outcomes[:covered]]
    return outcomes, intervals + [(-1000.0, -999.0)] * (100 - covered)


def _produce(store: FileSystemCAS, covered: int = 95) -> ArtifactRef:
    outcomes, intervals = _pairs(covered)
    return persist_continuous_evaluation(store, y_true=outcomes, intervals={0.95: intervals})


def _payload(store: FileSystemCAS, ref: ArtifactRef) -> dict:
    value = from_canonical_bytes(store.get_bytes(ref))
    assert isinstance(value, dict)
    return deepcopy(value)


def _repack(
    store: FileSystemCAS,
    original: ArtifactRef,
    payload: dict,
    *,
    inputs=None,
    producer: ProducerInfo | None = None,
    kind: str | None = None,
    version: str | None = None,
) -> ArtifactRef:
    manifest = store.get_manifest(original)
    return store.put_json(
        payload,
        ArtifactWriteOptions(
            kind=manifest.kind if kind is None else kind,
            media_type=manifest.media_type,
            schema=SchemaInfo(
                name=manifest.artifact_schema.name,
                version=manifest.artifact_schema.version if version is None else version,
            ),
            inputs=manifest.inputs if inputs is None else inputs,
            producer=producer,
        ),
        canon_spec=_CANON,
        return_selected_profile=True,
    )


@pytest.mark.parametrize("covered", [95, 0])
def test_fresh_cas_recomputes_actual_interval_outcome_pairs(covered: int, tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ref = _produce(store, covered)
    assert ref.manifest_profile_sha256
    report = load_continuous_evaluation(FileSystemCAS(store.root), ref)
    outcomes, intervals = _pairs(covered)
    hits = sum(
        lower <= outcome <= upper
        for outcome, (lower, upper) in zip(outcomes, intervals, strict=True)
    )

    assert hits == covered
    assert report.curves["interval_coverage"][0].mean_observed == hits / len(outcomes)
    assert report.metrics.ece == pytest.approx(abs(hits / len(outcomes) - 0.95))
    assert report.curves["interval_coverage"][0].count == len(outcomes)
    receipt = report.to_truthfulness_receipt()
    assert receipt.runtime_truthfulness_tier == "unverified"
    assert receipt.diagnostics["measurement_source_assurance"] == "not_established"
    assert to_validation_report(diagnostics=report).verdict in {"blocked", "fail"}


@pytest.mark.parametrize("mutation", ["count", "coverage", "metric", "receipt"])
def test_valid_hash_false_summary_refuses_after_fresh_read(mutation: str, tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ref = _produce(store)
    payload = _payload(store, ref)
    if mutation == "count":
        payload["report"]["metrics"]["n_obs"] = 99
    elif mutation == "coverage":
        payload["report"]["curves"]["interval_coverage"][0]["mean_observed"] = 1.0
    elif mutation == "metric":
        payload["report"]["metrics"]["ece"] = 0.75
    else:
        payload["report"]["truthfulness_receipt"] = {"runtime_truthfulness_tier": "exact"}
    fake = _repack(store, ref, payload)
    assert store.verify(fake).ok
    with pytest.raises(ValueError, match="does not reproduce"):
        load_continuous_evaluation(FileSystemCAS(store.root), fake)


@pytest.mark.parametrize("mutation", ["outcome", "interval_order"])
def test_valid_new_pair_artifact_cannot_reuse_old_summary(mutation: str, tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ref = _produce(store)
    payload = _payload(store, ref)
    inputs_ref = ArtifactRef.model_validate(payload["inputs_ref"])
    inputs = _payload(store, inputs_ref)
    if mutation == "outcome":
        inputs["y_true"][0] = 1e6
    else:
        inputs["interval_sets"][0].reverse()
    changed_inputs = _repack(store, inputs_ref, inputs)
    payload["inputs_ref"] = changed_inputs.model_dump(mode="json")
    fake = _repack(
        store,
        ref,
        payload,
        inputs=[input_ref_from_artifact_ref(changed_inputs, role="continuous_evaluation_inputs")],
    )
    assert store.verify(fake).ok
    with pytest.raises(ValueError, match="does not reproduce"):
        load_continuous_evaluation(FileSystemCAS(store.root), fake)


def test_same_bytes_foreign_input_profile_requires_exact_edge_and_expectation(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ref = _produce(store)
    payload = _payload(store, ref)
    original = ArtifactRef.model_validate(payload["inputs_ref"])
    sibling = _repack(
        store,
        original,
        _payload(store, original),
        producer=ProducerInfo(component="test.sibling", version="1.0"),
    )
    assert original.artifact_id == sibling.artifact_id
    assert original.manifest_profile_sha256 != sibling.manifest_profile_sha256
    payload["inputs_ref"] = sibling.model_dump(mode="json")
    fake = _repack(store, ref, payload)
    with pytest.raises(ValueError, match="input manifest edge mismatch"):
        load_continuous_evaluation(FileSystemCAS(store.root), fake)
    rebound = _repack(
        store,
        ref,
        payload,
        inputs=[input_ref_from_artifact_ref(sibling, role="continuous_evaluation_inputs")],
    )
    with pytest.raises(ValueError, match="expected input profile mismatch"):
        load_continuous_evaluation(FileSystemCAS(store.root), rebound, expected_inputs_ref=original)


@pytest.mark.parametrize("edges", [0, 2])
def test_missing_or_duplicate_input_edges_refuse(edges: int, tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ref = _produce(store)
    edge = store.get_manifest(ref).inputs[0]
    fake = _repack(store, ref, _payload(store, ref), inputs=[edge] * edges)
    with pytest.raises(ValueError, match="input manifest edge mismatch"):
        load_continuous_evaluation(FileSystemCAS(store.root), fake)


@pytest.mark.parametrize(
    ("field", "value"), [("gate_eligible", True), ("measurement_source_assurance", "recomputed")]
)
def test_numeric_artifact_cannot_promote_its_authority(
    field: str, value: object, tmp_path: Path
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ref = _produce(store)
    payload = _payload(store, ref)
    payload[field] = value
    fake = _repack(store, ref, payload)
    with pytest.raises(ValueError):
        load_continuous_evaluation(FileSystemCAS(store.root), fake)


@pytest.mark.parametrize(("kind", "version"), [("wrong_kind", None), (None, "9.0")])
def test_actual_manifest_kind_and_schema_are_required(kind, version, tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ref = _produce(store)
    fake = _repack(store, ref, _payload(store, ref), kind=kind, version=version)
    with pytest.raises(ValueError):
        load_continuous_evaluation(FileSystemCAS(store.root), fake)


def test_selected_report_and_bounded_payload_are_required(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ref = _produce(store)
    unselected = ref.model_copy(update={"manifest_profile_sha256": None})
    with pytest.raises(ValueError):
        load_continuous_evaluation(FileSystemCAS(store.root), unselected)
    limits = CoreJsonReadLimits(
        max_bytes=1, max_depth=64, max_elements=2_000_000, max_manifest_bytes=1024 * 1024
    )
    with pytest.raises(ValueError):
        load_continuous_evaluation(FileSystemCAS(store.root), ref, limits=limits)


@pytest.mark.parametrize("seed", [None, True, False, 1.0, "1", -1])
def test_replay_seed_is_admitted_before_bootstrap(
    seed: object, monkeypatch, tmp_path: Path
) -> None:
    import polisyos.calibration.diagnostics.continuous as continuous

    def forbidden(*_args, **_kwargs):
        raise AssertionError("bootstrap ran before replay seed admission")

    monkeypatch.setattr(continuous, "_attach_interval_bootstrap", forbidden)
    outcomes, intervals = _pairs()
    with pytest.raises(ValueError, match="seed"):
        persist_continuous_evaluation(
            FileSystemCAS(tmp_path / "cas"),
            y_true=outcomes,
            intervals={0.95: intervals},
            uncertainty={"bootstrap": 10, "seed": seed},
        )


def test_samples_and_seeded_bootstrap_reproduce_without_promoting_source(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    rng = np.random.default_rng(42)
    samples = rng.normal(size=(100, 30)).tolist()
    ref = persist_continuous_evaluation(
        store,
        y_true=[0.0] * 100,
        predictive_samples=samples,
        levels=[0.5, 0.95],
        uncertainty={"bootstrap": 20, "seed": 2718},
    )
    report = load_continuous_evaluation(FileSystemCAS(store.root), ref)
    assert report.target_type == "predictive_distribution"
    assert report.metrics.intervals
    assert sum(report.metadata["pit_histogram"]["counts"]) == 100
    assert report.to_truthfulness_receipt().runtime_truthfulness_tier == "unverified"


@pytest.mark.parametrize("entrypoint", ["producer", "fresh_reader"])
@pytest.mark.parametrize("repetitions", [10_001, 1_000_000_000])
def test_expanded_replay_work_is_admitted_before_bootstrap(
    entrypoint: str, repetitions: int, monkeypatch, tmp_path: Path
) -> None:
    import polisyos.calibration.diagnostics.continuous as continuous

    def forbidden(*_args, **_kwargs):
        raise AssertionError("bootstrap ran before replay work admission")

    monkeypatch.setattr(continuous, "_attach_interval_bootstrap", forbidden)
    store = FileSystemCAS(tmp_path / "cas")
    if entrypoint == "producer":
        outcomes, intervals = _pairs()
        with pytest.raises(ValueError, match="replay pair budget"):
            persist_continuous_evaluation(
                store,
                y_true=outcomes,
                intervals={0.95: intervals},
                uncertainty={"bootstrap": repetitions, "seed": 0},
            )
    else:
        ref = _produce(store)
        artifact = _payload(store, ref)
        inputs_ref = ArtifactRef.model_validate(artifact["inputs_ref"])
        inputs = _payload(store, inputs_ref)
        inputs["uncertainty"] = {"bootstrap": repetitions, "seed": 0}
        changed_inputs = _repack(store, inputs_ref, inputs)
        artifact["inputs_ref"] = changed_inputs.model_dump(mode="json")
        changed_report = _repack(
            store,
            ref,
            artifact,
            inputs=[
                input_ref_from_artifact_ref(changed_inputs, role="continuous_evaluation_inputs")
            ],
        )
        with pytest.raises(ValueError, match="replay pair budget"):
            load_continuous_evaluation(FileSystemCAS(store.root), changed_report)


@pytest.mark.parametrize(
    ("intervals", "levels"), [([], []), ([[], [(0.0, 2.0)] * 100], [0.5, 0.95])]
)
def test_empty_and_partial_sets_reopen_with_their_real_denominator(
    intervals, levels, tmp_path: Path
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ref = persist_continuous_evaluation(
        store, y_true=[1.0] * 100, intervals=intervals, levels=levels
    )
    report = load_continuous_evaluation(FileSystemCAS(store.root), ref)
    expected = "not_evaluated" if not levels else "incomplete"
    assert report.metadata["interval_coverage"]["status"] == expected
    assert report.metadata["interval_coverage"]["n_comparisons"] == (0 if not levels else 1)
    assert report.to_truthfulness_receipt().runtime_truthfulness_tier == "unverified"


def test_persisted_inputs_do_not_alias_mutated_callers(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    outcomes, intervals = _pairs()
    ref = persist_continuous_evaluation(store, y_true=outcomes, intervals={0.95: intervals})
    outcomes[0] = 1e6
    intervals.reverse()
    report = load_continuous_evaluation(FileSystemCAS(store.root), ref)
    assert report.curves["interval_coverage"][0].mean_observed == 0.95
