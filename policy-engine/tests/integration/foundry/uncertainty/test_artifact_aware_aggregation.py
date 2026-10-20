"""B200 actual producer-to-CAS-to-fresh-consumer integration witness."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from polisyos.core.artifacts import (
    FileSystemCAS,
    artifact_manifest_profile_sha256,
    ensure_ir_artifact_store,
)
from polisyos.foundry.uncertainty.aggregator import (
    aggregate_envelopes,
    load_aggregated_envelope_fresh,
    persist_aggregated_envelope,
)
from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.dispatcher import PropagationDispatcher
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
)
from polisyos.ir.artifacts import (
    ArtifactStore,
    InputRef,
    put_json_artifact,
)
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import ArtifactRefModel

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.ir.registry.refs import UncertaintyEnvelopeRef


pytestmark = pytest.mark.integration


def _ir_store(tmp_path: Path) -> ArtifactStore:
    """Return a Core filesystem CAS through its supported IR bridge."""
    return ensure_ir_artifact_store(FileSystemCAS(tmp_path))


def _persist_dispatched_envelope(
    store: ArtifactStore,
    *,
    source_label: str,
) -> UncertaintyEnvelopeRef:
    source = ArtifactRefModel.model_validate(
        put_json_artifact(
            store,
            {"fixture": source_label},
            kind="research.controlled_uncertainty_source",
            schema_name="research.ControlledUncertaintySource",
            schema_version="0.1",
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
    )
    seed = UncertaintyEnvelope(
        point_estimate=10.0,
        confidence_interval=(8.04, 11.96),
        confidence_level=0.95,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.ANALYTICAL,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        gate_eligible=True,
        metadata={
            "envelope_id": "sha256:" + "d" * 64,
            "independence": True,
            "unit": "index_points",
        },
    )
    seed_ref = persist_uncertainty_envelope(
        store,
        seed,
        inputs=[
            InputRef(
                artifact_id=source.artifact_id,
                role="measurement_source",
                manifest_profile_sha256=source.manifest_profile_sha256,
            )
        ],
        return_selected_profile=True,
    )
    seed_payload = load_uncertainty_envelope(store, seed_ref)
    produced = PropagationDispatcher(PropagationConfig(preferred_method="analytical")).propagate(
        simulation_fn=lambda **params: {"estimate": params["measurement"]},
        nominal_params={"measurement": seed_payload.point_estimate},
        input_envelopes={"measurement": seed_payload},
        output_metric_ids=["estimate"],
        is_jax_differentiable=True,
        weights={"measurement": 1.0},
    )
    assert len(produced) == 1
    result = produced[0]
    assert result.method_used is PropagationMethod.ANALYTICAL
    assert result.envelope.point_estimate == seed_payload.point_estimate
    return persist_uncertainty_envelope(
        store,
        result.envelope,
        inputs=[
            InputRef(
                artifact_id=seed_ref.artifact_id,
                role="propagation_input",
                manifest_profile_sha256=seed_ref.manifest_profile_sha256,
            )
        ],
        return_selected_profile=True,
    )


def test_real_dispatcher_source_views_are_persisted_aggregated_and_fresh_read(
    tmp_path: Path,
) -> None:
    producer = _ir_store(tmp_path)
    left = _persist_dispatched_envelope(producer, source_label="source-a")
    right = _persist_dispatched_envelope(producer, source_label="source-b")

    assert left.artifact_id == right.artifact_id
    assert left.manifest_profile_sha256 != right.manifest_profile_sha256
    left_envelope = load_uncertainty_envelope(producer, left)
    right_envelope = load_uncertainty_envelope(producer, right)
    assert left_envelope.metadata == right_envelope.metadata
    assert left_envelope.metadata.get("unit") is None

    # Keeping the producer's sha-shaped composition origins must not restore narrowing.
    assert left_envelope.composition_provenance is not None
    assert "sha256:" + "d" * 64 in left_envelope.composition_provenance.origin_envelope_ids
    direct = aggregate_envelopes(
        (left_envelope, right_envelope),
        method="precision_weighted",
    )
    assert direct.interval_semantics is IntervalSemantics.DETERMINISTIC_BOUNDS
    assert direct.confidence_level is None
    assert direct.gate_eligible is False
    assert direct.metadata["duplicate_source_count"] == 0

    combined_ref = persist_aggregated_envelope(
        producer,
        (left, right),
        method="precision_weighted",
    )
    fresh = _ir_store(tmp_path)
    combined = load_aggregated_envelope_fresh(
        fresh,
        combined_ref,
        source_refs=(left, right),
        method="precision_weighted",
    )

    assert combined.metadata["input_envelope_view_count"] == 2
    assert combined.metadata["unique_selected_view_count"] == 2
    assert combined.metadata["relation_status"] == "not_established"
    assert combined.metadata["common_estimand_status"] == "not_established"
    assert combined.metadata["unit_binding_status"] == "not_established"
    assert combined.metadata["effective_information_count"] is None
    assert combined.metadata["common_estimand_status"] == "not_established"
    assert combined.metadata["common_subject_status"] == "not_established"
    assert combined.metadata["unit_binding_status"] == "not_established"
    assert combined.metadata["aggregation_context_assumption"].startswith(
        "candidate_only_conditional_hull:"
    )
    assert combined.confidence_interval == (8.04, 11.96)
    assert combined.interval_semantics is IntervalSemantics.DETERMINISTIC_BOUNDS
    assert combined.confidence_level is None
    assert combined.gate_eligible is False
    manifest = fresh.get_manifest(combined_ref)
    assert len(manifest.inputs) == 2
    assert tuple(item.role for item in manifest.inputs) == (
        "source_uncertainty_envelope",
        "source_uncertainty_envelope",
    )
    assert all(item.manifest_profile_sha256 for item in manifest.inputs)
    assert artifact_manifest_profile_sha256(manifest) == combined_ref.manifest_profile_sha256
