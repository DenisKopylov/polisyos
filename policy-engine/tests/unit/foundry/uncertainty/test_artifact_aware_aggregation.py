"""B200 source-view binding and conservative uncertainty aggregation controls."""

from __future__ import annotations

from statistics import NormalDist
from typing import TYPE_CHECKING

import pytest

from polisyos.core.artifacts import FileSystemCAS, ensure_ir_artifact_store
from polisyos.foundry.uncertainty.aggregator import (
    aggregate_envelopes,
    aggregate_persisted_envelope_views,
    load_aggregated_envelope_fresh,
    persist_aggregated_envelope,
)
from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    NumericPolicySpec,
    NumericToleranceMode,
    ParametricFitCarrier,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
)
from polisyos.ir.artifacts import (
    ArtifactStore,
    InputRef,
    normalize_input_sequence,
    put_json_artifact,
)
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import ArtifactRefModel, UncertaintyEnvelopeRef

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit


def _ir_store(tmp_path: Path) -> ArtifactStore:
    """Return a Core filesystem CAS through its supported IR bridge."""
    return ensure_ir_artifact_store(FileSystemCAS(tmp_path))


def _source_ref(store: ArtifactStore, label: str) -> ArtifactRefModel:
    return ArtifactRefModel.model_validate(
        put_json_artifact(
            store,
            {"fixture": label},
            kind="research.controlled_uncertainty_source",
            schema_name="research.ControlledUncertaintySource",
            schema_version="0.1",
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
    )


def _persist_envelope(
    store: ArtifactStore,
    *,
    source_label: str,
    point: float = 10.0,
    unit: str | None = "index_points",
    confidence_level: float | None = 0.95,
    interval_semantics: IntervalSemantics = IntervalSemantics.CONFIDENCE_INTERVAL,
    numeric_policy: NumericPolicySpec | None = None,
    context: dict[str, object] | None = None,
) -> UncertaintyEnvelopeRef:
    source = _source_ref(store, source_label)
    input_ref = InputRef(
        artifact_id=source.artifact_id,
        role="measurement_source",
        manifest_profile_sha256=source.manifest_profile_sha256,
    )
    envelope = UncertaintyEnvelope(
        numeric_policy=numeric_policy or NumericPolicySpec(),
        point_estimate=point,
        confidence_interval=(8.04 + point - 10.0, 11.96 + point - 10.0),
        confidence_level=confidence_level,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.ANALYTICAL,
        interval_semantics=interval_semantics,
        gate_eligible=True,
        metadata={
            "envelope_id": "sha256:" + "a" * 64,
            "independence": True,
            "dependency": "independent",
            **({"unit": unit} if unit else {}),
            **(context or {}),
        },
    )
    return persist_uncertainty_envelope(
        store,
        envelope,
        inputs=[input_ref],
        return_selected_profile=True,
    )


def _memory_envelope(
    *,
    point: float = 10.0,
    metadata: dict[str, object] | None = None,
    numeric_policy: NumericPolicySpec | None = None,
) -> UncertaintyEnvelope:
    return UncertaintyEnvelope(
        numeric_policy=numeric_policy or NumericPolicySpec(),
        point_estimate=point,
        confidence_interval=(point - 1.96, point + 1.96),
        confidence_level=0.95,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.ANALYTICAL,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        metadata=metadata or {},
    )


def _scalar_normal_std_one(*, metadata: dict[str, object] | None = None) -> UncertaintyEnvelope:
    """Build a numerical fixture, without establishing any information relation."""
    z_value = NormalDist().inv_cdf(0.975)
    return UncertaintyEnvelope(
        point_estimate=10.0,
        confidence_interval=(10.0 - z_value, 10.0 + z_value),
        confidence_level=0.95,
        distribution_family=DistributionFamily.NORMAL,
        distribution_payload=ParametricFitCarrier(
            family=DistributionFamily.NORMAL,
            parameters={"mean": 10.0, "std": 1.0},
        ),
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.ANALYTICAL,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        gate_eligible=True,
        metadata={"unit": "index_points", **(metadata or {})},
    )


def _assert_scalar_unit_width(envelope: UncertaintyEnvelope) -> None:
    """Compare scalar bounds with the analytic fixture, independently of Foundry scale helpers."""
    z_value = NormalDist().inv_cdf(0.975)
    lower, upper = envelope.confidence_interval
    # This goes first: a four-copy STD=0.5 mutant must fail numerically before any status check.
    assert (upper - lower) / (2.0 * z_value) == pytest.approx(1.0, rel=0.0, abs=1.0e-12)
    assert envelope.point_estimate == 10.0
    assert envelope.confidence_interval == pytest.approx(
        (10.0 - z_value, 10.0 + z_value), rel=0.0, abs=1.0e-12
    )


def test_in_memory_fake_origin_and_relation_labels_cannot_narrow() -> None:
    left = UncertaintyEnvelope(
        point_estimate=10.0,
        confidence_interval=(8.04, 11.96),
        confidence_level=0.95,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.ANALYTICAL,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        gate_eligible=True,
        metadata={
            "envelope_id": "sha256:" + "b" * 64,
            "independence": True,
            "dependency": "independent",
            "unit": "index_points",
        },
    )
    right = left.model_copy(
        update={
            "point_estimate": 11.0,
            "confidence_interval": (9.04, 12.96),
        }
    )

    assert left.metadata["envelope_id"] == "sha256:" + "b" * 64
    assert left.metadata["independence"] is True
    result = aggregate_envelopes(
        (left, right),
        method="precision_weighted",
    )

    assert result.confidence_interval == (8.04, 12.96)
    assert result.interval_semantics is IntervalSemantics.DETERMINISTIC_BOUNDS
    assert result.confidence_level is None
    assert result.gate_eligible is False
    assert result.metadata["source_count"] == 2
    assert result.metadata["duplicate_source_count"] == 0
    assert result.metadata["effective_information_count"] is None
    assert result.metadata["effective_information_count_status"] == "not_established"
    assert result.sample_size is None
    assert result.composition_provenance is not None
    assert all(
        not item.startswith("sha256:" + "b" * 64)
        for item in result.composition_provenance.origin_envelope_ids
    )


def test_exact_selected_view_repeats_once_with_ordered_fresh_lineage(tmp_path: Path) -> None:
    store = _ir_store(tmp_path)
    source = _persist_envelope(
        store,
        source_label="source-a",
        confidence_level=0.83,
        interval_semantics=IntervalSemantics.CREDIBLE_INTERVAL,
    )
    source_payload = load_uncertainty_envelope(store, source)

    preview = aggregate_persisted_envelope_views(store, (source, source), method="widest")
    receipt = persist_aggregated_envelope(store, (source, source), method="widest")
    manifest = store.get_manifest(receipt)
    expected_input = InputRef(
        artifact_id=source.artifact_id,
        role="source_uncertainty_envelope",
        manifest_profile_sha256=source.manifest_profile_sha256,
    )
    assert normalize_input_sequence(manifest.inputs) == [expected_input, expected_input]
    fresh = load_aggregated_envelope_fresh(
        _ir_store(tmp_path),
        receipt,
        source_refs=(source, source),
        method="widest",
    )

    assert preview == fresh
    assert preview.point_estimate == source_payload.point_estimate
    assert preview.confidence_interval == source_payload.confidence_interval
    assert preview.confidence_level == source_payload.confidence_level == 0.83
    assert preview.interval_semantics is source_payload.interval_semantics
    assert preview.gate_eligible is source_payload.gate_eligible is True
    assert preview.metadata["input_envelope_view_count"] == 2
    assert preview.metadata["unique_selected_view_count"] == 1
    assert preview.metadata["repeated_selected_view_count"] == 1
    assert preview.metadata["selected_view_identity_status"] == "recomputed"
    assert preview.metadata["relation_status"] == "not_established"
    assert preview.metadata["effective_information_count"] is None
    assert preview.gate_eligible is True
    with pytest.raises(ValueError, match="manifest_source_mismatch"):
        load_aggregated_envelope_fresh(
            _ir_store(tmp_path),
            receipt,
            source_refs=(source,),
            method="widest",
        )


@pytest.mark.parametrize("method", ["precision_weighted", "bayesian_combination"])
@pytest.mark.parametrize("repeat_count", [4, 10])
def test_repeated_selected_normal_view_preserves_exact_std_and_fresh_counts(
    tmp_path: Path,
    method: str,
    repeat_count: int,
) -> None:
    """One selected STD=1 view remains STD=1 through persistence and a fresh consumer."""
    store = _ir_store(tmp_path)
    source_artifact = _source_ref(store, "selected-normal-std-one")
    source = persist_uncertainty_envelope(
        store,
        _scalar_normal_std_one(),
        inputs=[
            InputRef(
                artifact_id=source_artifact.artifact_id,
                role="measurement_source",
                manifest_profile_sha256=source_artifact.manifest_profile_sha256,
            )
        ],
        return_selected_profile=True,
    )
    source_payload = load_uncertainty_envelope(store, source)
    source_refs = (source,) * repeat_count
    receipt = persist_aggregated_envelope(store, source_refs, method=method)
    fresh_store = _ir_store(tmp_path)
    result = load_aggregated_envelope_fresh(
        fresh_store, receipt, source_refs=source_refs, method=method
    )

    _assert_scalar_unit_width(source_payload)
    _assert_scalar_unit_width(result)
    assert isinstance(result.distribution_payload, ParametricFitCarrier)
    assert result.distribution_payload.family is DistributionFamily.NORMAL
    assert result.distribution_payload.parameters == {"mean": 10.0, "std": 1.0}
    assert result.distribution_payload == source_payload.distribution_payload
    assert result.confidence_level == 0.95
    assert result.interval_semantics is IntervalSemantics.CONFIDENCE_INTERVAL
    # Reuse preserves the fixture's existing flag; it does not prove new source authority.
    assert result.gate_eligible is source_payload.gate_eligible
    assert result.metadata["input_envelope_view_count"] == repeat_count
    assert result.metadata["unique_selected_view_count"] == 1
    assert result.metadata["repeated_selected_view_count"] == repeat_count - 1
    assert result.metadata["relation_status"] == "not_established"
    assert result.metadata["effective_information_count"] is None
    assert result.metadata["effective_information_count_status"] == "not_established"
    assert result.sample_size is None
    expected_input = InputRef(
        artifact_id=source.artifact_id,
        role="source_uncertainty_envelope",
        manifest_profile_sha256=source.manifest_profile_sha256,
    )
    actual_inputs = normalize_input_sequence(fresh_store.get_manifest(receipt).inputs)
    assert actual_inputs == [expected_input] * repeat_count


@pytest.mark.parametrize("method", ["precision_weighted", "bayesian_combination"])
def test_same_source_scalar_views_cannot_gain_precision_from_forged_basis(
    tmp_path: Path,
    method: str,
) -> None:
    """Different same-shaped scalar views of one held source do not create information."""
    store = _ir_store(tmp_path)
    source_artifact = _source_ref(store, "one-shared-measurement-source")
    source_input = InputRef(
        artifact_id=source_artifact.artifact_id,
        role="measurement_source",
        manifest_profile_sha256=source_artifact.manifest_profile_sha256,
    )
    source_refs = tuple(
        persist_uncertainty_envelope(
            store,
            _scalar_normal_std_one(
                metadata={
                    "view_revision": revision,
                    "origin_id": "same-declared-origin",
                    "independence": True,
                    "dependency": "independent",
                    "relation_status": "recomputed",
                    "effective_information_count": 4,
                }
            ),
            inputs=[source_input],
            return_selected_profile=True,
        )
        for revision in range(4)
    )
    assert len({str(ref.artifact_id) for ref in source_refs}) == 4
    for ref in source_refs:
        assert normalize_input_sequence(store.get_manifest(ref).inputs) == [source_input]
        payload = load_uncertainty_envelope(store, ref)
        _assert_scalar_unit_width(payload)
        assert isinstance(payload.distribution_payload, ParametricFitCarrier)
        assert payload.distribution_payload.parameters == {"mean": 10.0, "std": 1.0}

    receipt = persist_aggregated_envelope(store, source_refs, method=method)
    result = load_aggregated_envelope_fresh(
        _ir_store(tmp_path), receipt, source_refs=source_refs, method=method
    )

    # Numeric width is checked before declarations: the original four-copy 0.5 error fails here.
    _assert_scalar_unit_width(result)
    assert result.metadata["input_envelope_view_count"] == 4
    assert result.metadata["unique_selected_view_count"] == 4
    assert result.metadata["repeated_selected_view_count"] == 0
    assert result.metadata["relation_status"] == "not_established"
    assert result.metadata["common_estimand_status"] == "not_established"
    assert result.metadata["unit_binding_status"] == "not_established"
    assert result.metadata["effective_information_count"] is None
    assert result.metadata["effective_information_count_status"] == "not_established"
    assert result.sample_size is None
    assert result.confidence_level is None
    assert result.interval_semantics is IntervalSemantics.DETERMINISTIC_BOUNDS
    assert result.distribution_family is DistributionFamily.UNKNOWN
    assert result.distribution_payload is None
    assert result.gate_eligible is False


@pytest.mark.parametrize("method", ["precision_weighted", "bayesian_combination"])
def test_same_payload_with_distinct_selected_profiles_is_not_deduplicated(
    tmp_path: Path,
    method: str,
) -> None:
    store = _ir_store(tmp_path)
    envelope = _scalar_normal_std_one(metadata={"envelope_id": "sha256:" + "c" * 64})
    source_a = _source_ref(store, "source-a")
    source_b = _source_ref(store, "source-b")

    def persist_from(source: ArtifactRefModel) -> UncertaintyEnvelopeRef:
        return persist_uncertainty_envelope(
            store,
            envelope,
            inputs=[
                InputRef(
                    artifact_id=source.artifact_id,
                    role="measurement_source",
                    manifest_profile_sha256=source.manifest_profile_sha256,
                )
            ],
            return_selected_profile=True,
        )

    left = persist_from(source_a)
    right = persist_from(source_b)
    assert left.artifact_id == right.artifact_id
    assert left.manifest_profile_sha256 != right.manifest_profile_sha256
    # Marker-preserving control: dedup by content ID alone would return one eligible input.
    assert load_uncertainty_envelope(store, left).metadata["envelope_id"] == "sha256:" + "c" * 64
    source_refs = (left, right, left, right)
    receipt = persist_aggregated_envelope(store, source_refs, method=method)
    result = load_aggregated_envelope_fresh(
        _ir_store(tmp_path), receipt, source_refs=source_refs, method=method
    )

    # Same scalar carrier/bytes and different selected source profiles are not a relation basis.
    _assert_scalar_unit_width(result)
    assert result.metadata["input_envelope_view_count"] == 4
    assert result.metadata["unique_selected_view_count"] == 2
    assert result.metadata["repeated_selected_view_count"] == 2
    assert result.metadata["selected_view_identity_status"] == "recomputed"
    assert result.metadata["relation_status"] == "not_established"
    assert result.metadata["common_estimand_status"] == "not_established"
    assert result.metadata["unit_binding_status"] == "not_established"
    assert result.metadata["effective_information_count"] is None
    assert result.metadata["effective_information_count_status"] == "not_established"
    assert result.sample_size is None
    assert result.interval_semantics is IntervalSemantics.DETERMINISTIC_BOUNDS
    assert result.confidence_level is None
    assert result.distribution_payload is None
    assert result.gate_eligible is False


@pytest.mark.parametrize(
    ("left_context", "right_context"),
    [
        ({"unit": "USD"}, {"unit": "GBP"}),
        ({"subject_id": "region-a"}, {"subject_id": "region-b"}),
        ({"context": {"currency": "USD"}}, {"context": {"currency": "GBP"}}),
        ({"estimand_id": "effect-a"}, {"estimand_id": "effect-b"}),
    ],
)
def test_recognized_context_conflicts_refuse_in_memory_and_cas(
    tmp_path: Path,
    left_context: dict[str, object],
    right_context: dict[str, object],
) -> None:
    left = _memory_envelope(metadata=left_context)
    right = _memory_envelope(point=11.0, metadata=right_context)

    with pytest.raises(ValueError, match="explicit_context_mismatch"):
        aggregate_envelopes((left, right), method="widest")

    store = _ir_store(tmp_path)
    left_ref = _persist_envelope(
        store, source_label="left-context", unit=None, context=left_context
    )
    right_ref = _persist_envelope(
        store, source_label="right-context", unit=None, context=right_context
    )
    with pytest.raises(ValueError, match="explicit_context_mismatch"):
        aggregate_persisted_envelope_views(store, (left_ref, right_ref), method="widest")


def test_same_envelope_context_alias_conflict_refuses_in_memory() -> None:
    conflicting = _memory_envelope(metadata={"unit": "USD", "context": {"unit": "GBP"}})
    compatible = _memory_envelope(point=11.0, metadata={"unit": "USD"})

    assert conflicting.metadata["unit"] == "USD"
    assert conflicting.metadata["context"]["unit"] == "GBP"
    with pytest.raises(ValueError, match="explicit_context_mismatch"):
        aggregate_envelopes((conflicting, compatible), method="widest")


def test_same_envelope_context_alias_conflict_refuses_selected_cas_before_dedup(
    tmp_path: Path,
) -> None:
    store = _ir_store(tmp_path)
    conflicting_ref = _persist_envelope(
        store,
        source_label="same-envelope-alias-conflict",
        unit="USD",
        context={"context": {"unit": "GBP"}},
    )
    compatible_ref = _persist_envelope(
        store, source_label="compatible-unit", point=11.0, unit="USD"
    )
    persisted_conflicting = load_uncertainty_envelope(store, conflicting_ref)

    assert persisted_conflicting.metadata["unit"] == "USD"
    assert persisted_conflicting.metadata["context"]["unit"] == "GBP"
    assert conflicting_ref.artifact_id != compatible_ref.artifact_id
    with pytest.raises(ValueError, match="explicit_context_mismatch"):
        aggregate_persisted_envelope_views(
            store, (conflicting_ref, compatible_ref), method="widest"
        )


def test_malformed_recognized_context_refuses_in_memory_and_cas(tmp_path: Path) -> None:
    malformed = _memory_envelope(metadata={"unit": 17})
    compatible = _memory_envelope(point=11.0, metadata={"unit": "USD"})

    with pytest.raises(ValueError, match="explicit_context_malformed"):
        aggregate_envelopes((malformed, compatible), method="widest")

    store = _ir_store(tmp_path)
    malformed_ref = _persist_envelope(
        store, source_label="malformed-context", unit=None, context={"unit": 17}
    )
    compatible_ref = _persist_envelope(
        store, source_label="compatible-context", unit=None, context={"unit": "USD"}
    )
    with pytest.raises(ValueError, match="explicit_context_malformed"):
        aggregate_persisted_envelope_views(store, (malformed_ref, compatible_ref), method="widest")


def test_monte_carlo_producer_metadata_stays_per_source_in_both_entrypoints(
    tmp_path: Path,
) -> None:
    store = _ir_store(tmp_path)
    inputs = {
        "x": _memory_envelope(point=1.0),
        "z": _memory_envelope(point=2.0),
    }
    input_refs: dict[str, UncertaintyEnvelopeRef] = {}
    persisted_inputs: dict[str, UncertaintyEnvelope] = {}
    for name, envelope in inputs.items():
        source = _source_ref(store, f"mc-input-{name}")
        source_input = InputRef(
            artifact_id=source.artifact_id,
            role="measurement_source",
            manifest_profile_sha256=source.manifest_profile_sha256,
        )
        input_ref = persist_uncertainty_envelope(
            store,
            envelope,
            inputs=[source_input],
            return_selected_profile=True,
        )
        input_refs[name] = input_ref
        persisted_inputs[name] = load_uncertainty_envelope(store, input_ref)

    configs = (
        PropagationConfig(
            mc_n_samples=256,
            mc_seed=3,
            mc_sampling_method="random",
            compute_sensitivity=True,
        ),
        PropagationConfig(
            mc_n_samples=256,
            mc_seed=13,
            mc_sampling_method="sobol",
            compute_sensitivity=True,
        ),
    )
    produced = tuple(
        MonteCarloPropagator(config)
        .propagate(
            lambda x=0.0, z=0.0: {"outcome": x + z**2},
            {"x": 1.0, "z": 2.0},
            persisted_inputs,
            ["outcome"],
        )[0]
        .envelope
        for config in configs
    )
    left, right = produced
    assert left.propagation_method is PropagationMethod.MONTE_CARLO
    assert right.propagation_method is PropagationMethod.MONTE_CARLO
    assert left.metadata["mc_seed"] != right.metadata["mc_seed"]
    assert left.metadata["mc_sampling_method"] != right.metadata["mc_sampling_method"]
    assert left.metadata["sensitivity_indices"] != right.metadata["sensitivity_indices"]
    assert left.metadata["tail_risk"] != right.metadata["tail_risk"]

    direct = aggregate_envelopes((left, right), method="widest")
    assert direct.interval_semantics in {
        IntervalSemantics.DETERMINISTIC_BOUNDS,
        IntervalSemantics.HEURISTIC_RANGE,
    }
    assert direct.confidence_level is None
    assert direct.gate_eligible is False
    assert direct.metadata["effective_information_count"] is None
    assert direct.metadata["relation_status"] == "not_established"

    selected_refs = tuple(
        persist_uncertainty_envelope(
            store,
            envelope,
            inputs=[
                InputRef(
                    artifact_id=input_refs[name].artifact_id,
                    role=f"propagation_input.{name}",
                    manifest_profile_sha256=input_refs[name].manifest_profile_sha256,
                )
                for name in sorted(input_refs)
            ],
            return_selected_profile=True,
        )
        for envelope in produced
    )
    assert load_uncertainty_envelope(store, selected_refs[0]).metadata == left.metadata
    assert load_uncertainty_envelope(store, selected_refs[1]).metadata == right.metadata

    preview = aggregate_persisted_envelope_views(store, selected_refs, method="widest")
    aggregate_ref = persist_aggregated_envelope(store, selected_refs, method="widest")
    fresh = load_aggregated_envelope_fresh(
        _ir_store(tmp_path), aggregate_ref, source_refs=selected_refs, method="widest"
    )
    assert preview == fresh
    assert preview.metadata["unique_selected_view_count"] == 2
    assert preview.metadata["relation_status"] == "not_established"
    assert preview.metadata["effective_information_count"] is None
    assert preview.interval_semantics in {
        IntervalSemantics.DETERMINISTIC_BOUNDS,
        IntervalSemantics.HEURISTIC_RANGE,
    }
    assert preview.confidence_level is None
    assert preview.gate_eligible is False


def test_missing_context_is_declared_as_conditional_candidate_only() -> None:
    result = aggregate_envelopes((_memory_envelope(), _memory_envelope(point=11.0)))

    assert result.gate_eligible is False
    assert result.metadata["aggregation_context_assumption"].startswith(
        "candidate_only_conditional_hull:"
    )
    assert result.metadata["common_estimand_status"] == "not_established"
    assert result.metadata["common_subject_status"] == "not_established"
    assert result.metadata["unit_binding_status"] == "not_established"
    assert result.metadata["effective_information_count"] is None


@pytest.mark.parametrize("method", ["widest", "precision_weighted", "bayesian_combination"])
def test_nondefault_numeric_policy_is_preserved_by_both_entrypoints(
    tmp_path: Path,
    method: str,
) -> None:
    policy = NumericPolicySpec(
        policy_id="decimal_exact_e02_test",
        mode=NumericToleranceMode.DECIMAL_EXACT,
        decimal_places=15,
    )
    point = 10.0000000000004
    in_memory = (
        _memory_envelope(point=point, numeric_policy=policy),
        _memory_envelope(point=point, numeric_policy=policy),
    )
    direct = aggregate_envelopes(in_memory, method=method)
    assert direct.numeric_policy == policy
    assert direct.point_estimate == point

    store = _ir_store(tmp_path)
    left = _persist_envelope(
        store, source_label=f"left-{method}", point=point, numeric_policy=policy
    )
    right = _persist_envelope(
        store, source_label=f"right-{method}", point=point, numeric_policy=policy
    )
    persisted = aggregate_persisted_envelope_views(store, (left, right), method=method)
    assert persisted.numeric_policy == policy
    assert persisted.point_estimate == point
    assert persisted.metadata["numeric_policy_status"] == "recomputed_identical_typed_policy"


def test_numeric_policy_conflict_refuses_in_memory_and_cas(tmp_path: Path) -> None:
    exact = NumericPolicySpec(mode=NumericToleranceMode.DECIMAL_EXACT, decimal_places=15)
    left_envelope = _memory_envelope(numeric_policy=exact)
    right_envelope = _memory_envelope(point=11.0)

    with pytest.raises(ValueError, match="numeric_policy_mismatch"):
        aggregate_envelopes((left_envelope, right_envelope))

    store = _ir_store(tmp_path)
    left = _persist_envelope(store, source_label="left-exact", numeric_policy=exact)
    right = _persist_envelope(store, source_label="right-default")
    with pytest.raises(ValueError, match="numeric_policy_mismatch"):
        aggregate_persisted_envelope_views(store, (left, right))


def test_explicit_unit_conflict_is_refused(tmp_path: Path) -> None:
    store = _ir_store(tmp_path)
    dollars = _persist_envelope(store, source_label="dollars", unit="USD")
    pounds = _persist_envelope(store, source_label="pounds", unit="GBP")

    with pytest.raises(ValueError, match="explicit_context_mismatch"):
        aggregate_envelopes(
            (load_uncertainty_envelope(store, dollars), load_uncertainty_envelope(store, pounds)),
            method="widest",
        )
    with pytest.raises(ValueError, match="explicit_context_mismatch"):
        aggregate_persisted_envelope_views(store, (dollars, pounds), method="widest")


def test_unprofiled_foreign_kind_or_media_refuses_without_default_fallback(
    tmp_path: Path,
) -> None:
    store = _ir_store(tmp_path)
    source = _persist_envelope(store, source_label="source-a")
    unprofiled = source.model_copy(update={"manifest_profile_sha256": None})
    foreign_kind = source.model_copy(update={"kind": "ir.posterior_summary"})
    foreign_media = source.model_copy(update={"media_type": "application/octet-stream"})

    with pytest.raises(ValueError, match="selected_profile_missing"):
        aggregate_persisted_envelope_views(store, (unprofiled,), method="widest")
    with pytest.raises(ValueError, match="kind_or_media_mismatch"):
        aggregate_persisted_envelope_views(store, (foreign_kind,), method="widest")
    with pytest.raises(ValueError, match="kind_or_media_mismatch"):
        aggregate_persisted_envelope_views(store, (foreign_media,), method="widest")


def test_wrong_uncertainty_schema_is_rejected(tmp_path: Path) -> None:
    store = _ir_store(tmp_path)
    source = _persist_envelope(store, source_label="source-a")
    payload = load_uncertainty_envelope(store, source)
    wrong_schema_raw = put_json_artifact(
        store,
        payload.model_dump(mode="python", round_trip=True),
        kind="ir.uncertainty_envelope",
        schema_name="ir.uncertainty_envelope",
        schema_version="0.9",
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    wrong_schema = UncertaintyEnvelopeRef.model_validate(wrong_schema_raw)

    with pytest.raises(ValueError, match="selected_manifest_mismatch"):
        aggregate_persisted_envelope_views(store, (wrong_schema,), method="widest")


def test_changed_source_order_is_rejected_by_fresh_reader(tmp_path: Path) -> None:
    store = _ir_store(tmp_path)
    left = _persist_envelope(store, source_label="source-a")
    right = _persist_envelope(store, source_label="source-b")
    receipt = persist_aggregated_envelope(store, (left, right), method="widest")

    with pytest.raises(ValueError, match="manifest_source_mismatch"):
        load_aggregated_envelope_fresh(
            _ir_store(tmp_path),
            receipt,
            source_refs=(right, left),
            method="widest",
        )


@pytest.mark.parametrize("changed_field", ["role", "selected_profile"])
def test_fresh_reader_rejects_lineage_role_or_selected_profile_mismatch(
    tmp_path: Path,
    changed_field: str,
) -> None:
    store = _ir_store(tmp_path)
    source = _persist_envelope(store, source_label="source-a")
    aggregate = aggregate_persisted_envelope_views(store, (source,), method="widest")
    expected_input = InputRef(
        artifact_id=source.artifact_id,
        role="source_uncertainty_envelope",
        manifest_profile_sha256=source.manifest_profile_sha256,
    )
    role = expected_input.role
    profile = expected_input.manifest_profile_sha256
    if changed_field == "role":
        role = "tampered_source_role"
    else:
        assert profile is not None
        wrong_profile = "sha256:" + "0" * 64
        if wrong_profile == profile:
            wrong_profile = "sha256:" + "1" * 64
        profile = wrong_profile
    changed_input = InputRef(
        artifact_id=expected_input.artifact_id,
        role=role,
        manifest_profile_sha256=profile,
    )
    mismatched_receipt = persist_uncertainty_envelope(
        store,
        aggregate,
        inputs=[changed_input],
        return_selected_profile=True,
    )

    with pytest.raises(ValueError, match="manifest_source_mismatch"):
        load_aggregated_envelope_fresh(
            _ir_store(tmp_path),
            mismatched_receipt,
            source_refs=(source,),
            method="widest",
        )
