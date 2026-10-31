from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pytest

import polisyos.ir.analytics.value_subject as subject_module
from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.calibration.uncertainty_adapter import (
    summarize_bayesian_calibration_posterior,
)
from polisyos.ir.analytics.estimand import make_backdoor_estimand, persist_estimand_ast
from polisyos.ir.analytics.partial_identification import (
    bounds_bundle_from_partial_identification_result,
    compute_manski_bounds,
    load_bounds_bundle,
    persist_bounds_bundle,
)
from polisyos.ir.analytics.uncertainty import (
    IntervalSemantics,
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
)
from polisyos.ir.analytics.value_subject import (
    ValueArtifactSubject,
    ValueArtifactSubjectRef,
    ValueSubjectRelationRef,
    load_value_artifact_subject,
    load_value_subject_relation,
    persist_value_artifact_subject,
    persist_value_subject_relation,
    resolve_value_subject_relation,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef
from polisyos.ir.artifacts.io import put_json_artifact
from polisyos.ir.kernel.units import CountUnit, MoneyUnit, RateUnit
from polisyos.ir.model_layer.canon import CanonSpec, from_canonical_bytes
from polisyos.ir.registry.refs import ArtifactRefModel, BoundsBundleRef, UncertaintyEnvelopeRef


def _source(store: ArtifactStore, **changes: Any) -> ArtifactRefModel:
    payload = {
        "outcomes": [4.0, 8.0],
        "treatment_probs": [0.5, 0.5],
        "outcome_support": [0.0, 20.0],
        # Test caller inputs, not draws claimed to come from an actual fitted model.
        "draws": [1.0, 2.0, 3.0, 5.0, 15.0],
        **changes,
    }
    return ArtifactRefModel.from_selected_write(
        put_json_artifact(
            store,
            payload,
            kind="test.value_inputs",
            schema_name="test.value_inputs",
            schema_version="1.0",
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
    )


def _subject(
    store: ArtifactStore, source: ArtifactRefModel, **changes: Any
) -> ValueArtifactSubject:
    estimand = persist_estimand_ast(
        store, make_backdoor_estimand(treatment="X", outcome="Y", adjustment_set=())
    )
    return ValueArtifactSubject.model_validate(
        {
            "estimand_ref": estimand,
            "estimand_id": "ate",
            "exposure": "X",
            "outcome": "Y",
            "control_value": 0.0,
            "treatment_value": 1.0,
            "population": "declared-test-population",
            "unit": RateUnit(base="percent"),
            "time_horizon": "declared-test-horizon",
            "epoch": "test-epoch",
            "source_refs": (source,),
            **changes,
        }
    )


def _produce(
    store: ArtifactStore,
    source: ArtifactRefModel,
    *,
    identification_subject: ValueArtifactSubject,
    native_subject: ValueArtifactSubject | None = None,
    native_scale: float = 1.0,
    estimand_type: str = "ate",
) -> tuple[BoundsBundleRef, UncertaintyEnvelopeRef]:
    payload = from_canonical_bytes(store.get_bytes(source))
    assert isinstance(payload, dict)
    partial = compute_manski_bounds(
        np.asarray(payload["outcomes"]),
        np.asarray(payload["treatment_probs"]),
        tuple(payload["outcome_support"]),
    )
    bundle = bounds_bundle_from_partial_identification_result(partial, estimand_type=estimand_type)
    summary = summarize_bayesian_calibration_posterior(
        {"Y": np.asarray(payload["draws"]) * native_scale}, credible_mass=0.8
    )
    declared_identification = persist_value_artifact_subject(store, identification_subject)
    declared_native = persist_value_artifact_subject(
        store, native_subject or identification_subject
    )
    # Existing real producer inputs are preserved alongside the reserved join edges.
    producer_inputs = [
        InputRef(
            artifact_id=source.artifact_id,
            role="numerical_source",
            manifest_profile_sha256=source.manifest_profile_sha256,
        )
    ]
    return (
        persist_bounds_bundle(
            store, bundle, inputs=producer_inputs, value_subject_ref=declared_identification
        ),
        persist_uncertainty_envelope(
            store,
            summary.parameter_envelopes["Y"],
            inputs=producer_inputs,
            value_subject_ref=declared_native,
        ),
    )


def _rewrite(
    store: ArtifactStore,
    ref: ArtifactRefModel,
    *,
    payload_changes: Mapping[str, Any] | None = None,
    inputs: list[InputRef] | None = None,
) -> dict[str, str]:
    payload = from_canonical_bytes(store.get_bytes(ref))
    assert isinstance(payload, dict)
    manifest = store.get_manifest(ref)
    assert manifest.artifact_schema is not None
    return put_json_artifact(
        store,
        {**payload, **dict(payload_changes or {})},
        kind=ref.kind,
        schema_name=ref.kind,
        schema_version=str(payload.get("schema_version", manifest.artifact_schema.version)),
        inputs=list(manifest.inputs) if inputs is None else inputs,
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False)
        if ref.kind in {"ir.value_subject_relation", "ir.value_artifact_subject"}
        else CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def test_real_producers_fresh_reader_preserve_both_intervals_without_promotion(
    tmp_path: Path,
) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    source = _source(store)
    subject = _subject(store, source)
    bounds_ref, native_ref = _produce(store, source, identification_subject=subject)
    relation_ref = persist_value_subject_relation(
        store, identification_ref=bounds_ref, native_uncertainty_ref=native_ref
    )

    fresh = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    relation = load_value_subject_relation(fresh, relation_ref)
    bounds = load_bounds_bundle(fresh, bounds_ref)
    native = load_uncertainty_envelope(fresh, native_ref)
    # Independent arithmetic: 0.5*8 - 0.5*4 +/- 0.5*20 = [-8, 12].
    assert (bounds.lower_bound, bounds.upper_bound) == (-8.0, 12.0)
    assert native.point_estimate == pytest.approx(5.2)
    assert native.confidence_interval == pytest.approx((1.4, 11.0))
    assert native.interval_semantics is IntervalSemantics.CREDIBLE_INTERVAL
    assert native.confidence_interval != (bounds.lower_bound, bounds.upper_bound)
    assert relation.native_to_identification_factor == 1.0
    assert relation.resolved_subject.unit == RateUnit(base="percent")
    assert relation.subject_provenance == "consumer_asserted"
    assert relation.authority_scope == "resolved_declared_content_join_only"
    assert relation.production_value_eligible is False
    assert native.gate_eligible is False

    # This reader starts without producer memory, loads the selected CAS view,
    # and checks the native interval instead of accepting a stored relation flag.
    src_root = Path(subject_module.__file__).resolve().parents[3]
    reader = """
import json, sys
from pathlib import Path
from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
import polisyos.ir.analytics.value_subject as owner
from polisyos.ir.analytics.uncertainty import load_uncertainty_envelope
assert Path(owner.__file__).resolve().is_relative_to(Path(sys.argv[3]).resolve())
ref = owner.ValueSubjectRelationRef.model_validate_json(sys.argv[2])
relation = owner.load_value_subject_relation(ensure_ir_artifact_store(FileSystemCAS(sys.argv[1])), ref)
native = load_uncertainty_envelope(ensure_ir_artifact_store(FileSystemCAS(sys.argv[1])), relation.native_uncertainty.ref)
print(json.dumps({"native_ci": native.confidence_interval, "eligible": relation.production_value_eligible}))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            reader,
            str(tmp_path / "cas"),
            relation_ref.model_dump_json(),
            str(src_root),
        ],
        env={**os.environ, "PYTHONPATH": str(src_root)},
        capture_output=True,
        text=True,
        check=True,
    )
    observed = json.loads(result.stdout)
    assert observed["native_ci"] == pytest.approx([1.4, 11.0])
    assert observed["eligible"] is False


@pytest.mark.parametrize(
    ("native_base", "identified_base", "scale", "factor"),
    [("ratio", "percent", 0.01, 100.0), ("percent", "ratio", 100.0, 0.01)],
)
def test_exact_rate_scale_is_disclosed_without_mutating_native_values(
    tmp_path: Path, native_base: str, identified_base: str, scale: float, factor: float
) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    source = _source(store)
    subject = _subject(store, source, unit=RateUnit(base=identified_base))
    bounds_ref, native_ref = _produce(
        store,
        source,
        identification_subject=subject,
        native_subject=subject.model_copy(update={"unit": RateUnit(base=native_base)}),
        native_scale=scale,
    )
    relation = resolve_value_subject_relation(
        store, identification_ref=bounds_ref, native_uncertainty_ref=native_ref
    )
    assert relation.native_to_identification_factor == factor
    assert load_uncertainty_envelope(store, native_ref).point_estimate == pytest.approx(5.2 * scale)
    assert load_bounds_bundle(store, bounds_ref).lower_bound == -8.0


@pytest.mark.parametrize(
    "changes",
    [
        {"population": "another-population"},
        {"control_value": 0.5},
        {"treatment_value": 2.0},
        {"epoch": "another-epoch"},
        {"time_horizon": "another-horizon"},
        {"prediction_origin": "another-origin"},
        {"scale": "identity", "estimand_id": "att"},
    ],
)
def test_same_shape_native_channel_with_different_quantity_is_refused(
    tmp_path: Path, changes: dict[str, Any]
) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    source = _source(store)
    subject = _subject(store, source)
    bounds_ref, native_ref = _produce(
        store,
        source,
        identification_subject=subject,
        native_subject=subject.model_copy(update=changes),
    )
    with pytest.raises(ValueError, match="value_subject_quantity_mismatch"):
        resolve_value_subject_relation(
            store, identification_ref=bounds_ref, native_uncertainty_ref=native_ref
        )


@pytest.mark.parametrize("unit", [CountUnit(label="people"), MoneyUnit(currency="USD")])
def test_incompatible_units_are_refused_even_for_identical_numbers(
    tmp_path: Path, unit: CountUnit | MoneyUnit
) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    source = _source(store)
    subject = _subject(store, source)
    bounds_ref, native_ref = _produce(
        store,
        source,
        identification_subject=subject,
        native_subject=subject.model_copy(update={"unit": unit}),
    )
    with pytest.raises(ValueError, match="value_subject_unit_mismatch"):
        resolve_value_subject_relation(
            store, identification_ref=bounds_ref, native_uncertainty_ref=native_ref
        )


def test_bounds_payload_estimand_cannot_be_hidden_by_a_matching_declaration(tmp_path: Path) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    source = _source(store)
    subject = _subject(store, source)
    bounds_ref, native_ref = _produce(
        store, source, identification_subject=subject, estimand_type="att"
    )
    with pytest.raises(ValueError, match="value_subject_bounds_estimand_mismatch"):
        resolve_value_subject_relation(
            store, identification_ref=bounds_ref, native_uncertainty_ref=native_ref
        )


@pytest.mark.parametrize("field", ["exposure", "outcome"])
def test_declared_names_must_match_the_resolved_scalar_estimand(tmp_path: Path, field: str) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    subject = _subject(store, _source(store)).model_copy(update={field: "another-variable"})
    with pytest.raises(ValueError, match="value_subject_estimand_mismatch"):
        persist_value_artifact_subject(store, subject)


def test_different_source_or_model_cannot_be_joined_by_equal_intervals(tmp_path: Path) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    source = _source(store)
    other = _source(store, note="different-selected-source")
    subject = _subject(store, source)
    for change in ({"source_refs": (other,)}, {"model_ref": other}):
        bounds_ref, native_ref = _produce(
            store,
            source,
            identification_subject=subject,
            native_subject=subject.model_copy(update=change),
        )
        with pytest.raises(ValueError, match="value_subject_quantity_mismatch"):
            resolve_value_subject_relation(
                store, identification_ref=bounds_ref, native_uncertainty_ref=native_ref
            )


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "wrong_source"])
def test_producer_lineage_is_reconciled_instead_of_trusting_a_subject_marker(
    tmp_path: Path, mutation: str
) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    source = _source(store)
    bounds_ref, native_ref = _produce(store, source, identification_subject=_subject(store, source))
    inputs = list(store.get_manifest(native_ref).inputs)
    if mutation == "missing":
        inputs = [edge for edge in inputs if edge.role != "value_subject"]
    elif mutation == "duplicate":
        inputs.extend(edge for edge in list(inputs) if edge.role == "value_subject")
    else:
        other = _source(store, note="forged-lineage")
        inputs = [edge for edge in inputs if edge.role != "value_source"]
        inputs.append(
            InputRef(
                artifact_id=other.artifact_id,
                role="value_source",
                manifest_profile_sha256=other.manifest_profile_sha256,
            )
        )
    forged = UncertaintyEnvelopeRef.model_validate(_rewrite(store, native_ref, inputs=inputs))
    with pytest.raises(ValueError, match="value_subject_.*lineage"):
        resolve_value_subject_relation(
            store, identification_ref=bounds_ref, native_uncertainty_ref=forged
        )


def test_profileless_and_wrong_profile_subjects_do_not_upgrade_to_default(tmp_path: Path) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    source = _source(store)
    ref = persist_value_artifact_subject(store, _subject(store, source))
    profileless = ValueArtifactSubjectRef(artifact_id=ref.artifact_id)
    with pytest.raises(ValueError, match="value_subject_selected_profile_required"):
        load_value_artifact_subject(store, profileless)
    wrong = ref.model_copy(update={"manifest_profile_sha256": "sha256:" + "0" * 64})
    with pytest.raises((ValueError, FileNotFoundError, KeyError)):
        load_value_artifact_subject(store, wrong)


def test_same_source_bytes_with_another_valid_profile_are_a_different_join(tmp_path: Path) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    source = _source(store)
    context = _source(store, note="another-profile-context")
    alternate = ArtifactRefModel.model_validate(
        _rewrite(
            store,
            source,
            inputs=[
                InputRef(
                    artifact_id=context.artifact_id,
                    role="source_context",
                    manifest_profile_sha256=context.manifest_profile_sha256,
                )
            ],
        )
    )
    assert source.artifact_id == alternate.artifact_id
    assert source.manifest_profile_sha256 != alternate.manifest_profile_sha256
    assert store.get_bytes(source) == store.get_bytes(alternate)
    subject = _subject(store, source)
    bounds_ref, native_ref = _produce(
        store,
        source,
        identification_subject=subject,
        native_subject=subject.model_copy(update={"source_refs": (alternate,)}),
    )
    with pytest.raises(ValueError, match="value_subject_quantity_mismatch"):
        resolve_value_subject_relation(
            store, identification_ref=bounds_ref, native_uncertainty_ref=native_ref
        )


def test_producers_cannot_spoof_reserved_subject_edges(tmp_path: Path) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    source = _source(store)
    subject_ref = persist_value_artifact_subject(store, _subject(store, source))
    partial = compute_manski_bounds(np.asarray([4.0, 8.0]), np.asarray([0.5, 0.5]), (0.0, 20.0))
    with pytest.raises(ValueError, match="value_subject_reserved_producer_lineage"):
        persist_bounds_bundle(
            store,
            bounds_bundle_from_partial_identification_result(partial),
            inputs=[InputRef(artifact_id=source.artifact_id, role="value_subject")],
            value_subject_ref=subject_ref,
        )


def test_valid_hash_forged_relation_is_recomputed_by_a_fresh_consumer(tmp_path: Path) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    source = _source(store)
    bounds_ref, native_ref = _produce(store, source, identification_subject=_subject(store, source))
    ref = persist_value_subject_relation(
        store, identification_ref=bounds_ref, native_uncertainty_ref=native_ref
    )
    forged = ValueSubjectRelationRef.model_validate(
        _rewrite(store, ref, payload_changes={"native_to_identification_factor": 100.0})
    )
    fresh = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    with pytest.raises(ValueError, match="value_subject_relation_stale_or_forged"):
        load_value_subject_relation(fresh, forged)


@pytest.mark.parametrize(
    "changes",
    [
        {"production_value_eligible": True},
        {"authority_scope": "production_verified"},
        {"verifier_provenance": "caller_verified"},
        {"subject_provenance": "institutionally_supplied"},
        {"native_to_identification_factor": True},
    ],
)
def test_forged_authority_markers_are_refused_by_the_owned_reader(
    tmp_path: Path, changes: dict[str, Any]
) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    source = _source(store)
    bounds_ref, native_ref = _produce(store, source, identification_subject=_subject(store, source))
    ref = persist_value_subject_relation(
        store, identification_ref=bounds_ref, native_uncertainty_ref=native_ref
    )
    forged = ValueSubjectRelationRef.model_validate(_rewrite(store, ref, payload_changes=changes))
    with pytest.raises(ValueError):
        load_value_subject_relation(ensure_ir_artifact_store(FileSystemCAS(tmp_path)), forged)


def test_unverified_other_producer_inputs_cannot_promote_a_declared_join(tmp_path: Path) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    source = _source(store)
    other = _source(store, note="unverified-producer-input")
    bounds_ref, native_ref = _produce(store, source, identification_subject=_subject(store, source))
    edges = [
        edge for edge in store.get_manifest(native_ref).inputs if edge.role != "numerical_source"
    ]
    edges.append(
        InputRef(
            artifact_id=other.artifact_id,
            role="numerical_source",
            manifest_profile_sha256=other.manifest_profile_sha256,
        )
    )
    changed = UncertaintyEnvelopeRef.model_validate(_rewrite(store, native_ref, inputs=edges))
    relation = resolve_value_subject_relation(
        store, identification_ref=bounds_ref, native_uncertainty_ref=changed
    )
    # Declared-source equality is established; actual producer use is a separate
    # unverified predicate. This surface cannot turn either into authority.
    assert relation.authority_scope == "resolved_declared_content_join_only"
    assert relation.subject_provenance == "consumer_asserted"
    assert relation.production_value_eligible is False


def test_existing_unbound_producers_remain_readable_without_inventing_a_subject(
    tmp_path: Path,
) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    partial = compute_manski_bounds(np.asarray([4.0, 8.0]), np.asarray([0.5, 0.5]), (0.0, 20.0))
    bounds_ref = persist_bounds_bundle(
        store, bounds_bundle_from_partial_identification_result(partial)
    )
    summary = summarize_bayesian_calibration_posterior({"Y": [1.0, 2.0, 3.0]})
    native_ref = persist_uncertainty_envelope(store, summary.parameter_envelopes["Y"])
    assert load_bounds_bundle(store, bounds_ref).lower_bound == -8.0
    assert load_uncertainty_envelope(store, native_ref).point_estimate == 2.0
    with pytest.raises(ValueError, match="value_subject_lineage_missing_or_duplicate"):
        resolve_value_subject_relation(
            store, identification_ref=bounds_ref, native_uncertainty_ref=native_ref
        )
