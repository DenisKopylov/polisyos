"""Persisted content joins preserve channels without manufacturing authority."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from fractions import Fraction

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.value_outer_set import DataTrust, ValueOuterSet
from polisyos.ir.analytics.estimand import make_backdoor_estimand, persist_estimand_ast
from polisyos.ir.analytics.uncertainty import (
    UncertaintyEnvelope,
    UncertaintySource,
    ValueArtifactSubject,
    load_uncertainty_envelope,
    load_value_subject_relation,
    persist_uncertainty_envelope,
    persist_value_artifact_subject,
    persist_value_subject_relation,
    resolve_value_subject_relation,
    value_subject_producer_inputs,
)
from polisyos.ir.artifacts import InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.kernel.units import CountUnit, RateUnit
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import ArtifactRefModel, ValueSubjectRelationRef


def _producer_pair(
    tmp_path, *, native_changes=None, lineage_change=None, method_label="method.one"
):
    store = FileSystemCAS(tmp_path / "cas")
    source = ArtifactRefModel.model_validate(
        put_json_artifact(
            store,
            {"rows": [[0, 0], [1, 4]], "fixture": "bounded_synthetic"},
            kind="synthetic.value_source",
            schema_name="synthetic.value_source",
            schema_version="1.0",
        )
    )
    ast = persist_estimand_ast(
        store,
        make_backdoor_estimand(
            treatment="X",
            outcome="Y",
            adjustment_set=(),
        ),
    )
    subject = ValueArtifactSubject(
        estimand_ref=ast,
        estimand_id="ate-X-Y",
        outcome="Y",
        control_value=0.0,
        treatment_value=1.0,
        population="synthetic-adults",
        unit=RateUnit(base="percent"),
        time_horizon="cross_section",
        epoch="synthetic-v1",
        source_refs=(source,),
    )
    identified_subject_ref = persist_value_artifact_subject(store, subject)
    identified_inputs = value_subject_producer_inputs(subject, identified_subject_ref)
    outer = ValueOuterSet.interval_box(
        coordinates=(subject.estimand_id,),
        lower=(4.0,),
        upper=(4.0,),
        identification_mode="point",
        assumptions=("synthetic_fixture_only",),
        assumption_status="declared",
        calibration_scope={},
        data_trust=DataTrust(
            tier="fixture",
            trust_cap=0.0,
            trust_multiplier=0.0,
            authority_ref="non-authoritative-fixture",
        ),
        world_model_record_ref=str(source.artifact_id),
        epoch=subject.epoch,
        representation_status="search_only",
    )
    identified_ref = ArtifactRefModel.model_validate(
        put_json_artifact(
            store,
            outer.model_dump(mode="python"),
            kind="synthetic.identification_set",
            schema_name="synthetic.identification_set",
            schema_version="1.0",
            inputs=identified_inputs,
            canon_spec=CanonSpec(forbid_floats=False),
        )
    )
    native_subject = ValueArtifactSubject.model_validate(
        {
            **subject.model_dump(mode="python"),
            **(native_changes or {}),
        }
    )
    native_subject_ref = persist_value_artifact_subject(store, native_subject)
    native_inputs = value_subject_producer_inputs(native_subject, native_subject_ref)
    if lineage_change == "missing":
        native_inputs = [item for item in native_inputs if item.role != "value_subject"]
    elif lineage_change == "duplicate":
        native_inputs.append(native_inputs[0])
    elif lineage_change == "extra":
        native_inputs.append(InputRef(artifact_id=source.artifact_id, role="undeclared"))
    factor = (
        0.01
        if isinstance(native_subject.unit, RateUnit) and native_subject.unit.base == "ratio"
        else 1.0
    )
    envelope = UncertaintyEnvelope(
        point_estimate=4.0 * factor,
        confidence_interval=(1.0 * factor, 10.0 * factor),
        source=UncertaintySource.MANUAL,
        gate_eligible=False,
        metadata={
            "fixture": "synthetic",
            "declared_matching_subject": subject.estimand_id,
            "method_fqn": method_label,
        },
    )
    native_ref = persist_uncertainty_envelope(store, envelope, inputs=native_inputs)
    return store, subject, identified_ref, native_ref


def test_persisted_fresh_child_preserves_separate_asymmetric_channels(tmp_path):
    store, subject, identified_ref, native_ref = _producer_pair(tmp_path)
    relation_ref = persist_value_subject_relation(
        store,
        identification_ref=identified_ref,
        native_uncertainty_ref=native_ref,
    )
    script = """
import json,sys
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.value_outer_set import ValueOuterSet
from polisyos.ir.artifacts import get_json_artifact
from polisyos.ir.registry.refs import ValueSubjectRelationRef, UncertaintyEnvelopeRef
from polisyos.ir.analytics.uncertainty import load_value_subject_relation, load_uncertainty_envelope
store=FileSystemCAS(sys.argv[1])
r=load_value_subject_relation(store,ValueSubjectRelationRef.model_validate_json(sys.argv[2]))
o=ValueOuterSet.from_persisted_payload(get_json_artifact(store,r.identification.ref.artifact_id))
n=load_uncertainty_envelope(store,UncertaintyEnvelopeRef.model_validate(r.native_uncertainty.ref.model_dump(mode="python")))
print(json.dumps({'pid':__import__('os').getpid(),'point':o.lower,'identification_width':o.width,
'native_ci':n.confidence_interval,'native_point':n.point_estimate,'coordinate':o.coordinates,
'authority':r.production_value_eligible,'factor':r.native_to_identification_factor}))
"""
    child = subprocess.run(
        [sys.executable, "-c", script, str(store.root), relation_ref.model_dump_json()],
        check=False,
        capture_output=True,
        text=True,
    )
    assert child.returncode == 0, child.stdout + child.stderr
    result = json.loads(child.stdout)
    assert result["pid"] != os.getpid()
    assert result["point"] == [4.0]
    assert result["identification_width"] == [0.0]
    assert result["native_ci"] == [1.0, 10.0]
    assert result["native_point"] == 4.0
    assert result["coordinate"] == [subject.estimand_id]
    assert result["authority"] is False


def test_exact_typed_rate_conversion_preserves_native_payload(tmp_path):
    store, _, identified_ref, native_ref = _producer_pair(
        tmp_path,
        native_changes={"unit": RateUnit(base="ratio")},
    )
    relation = resolve_value_subject_relation(
        store,
        identification_ref=identified_ref,
        native_uncertainty_ref=native_ref,
    )
    assert relation.native_to_identification_factor == float(Fraction(100, 1))
    native = load_uncertainty_envelope(store, native_ref)
    assert native.confidence_interval == (0.01, 0.1)
    assert native.point_estimate == 0.04
    converted = tuple(
        Fraction(str(x)) * Fraction(str(relation.native_to_identification_factor))
        for x in native.confidence_interval
    )
    assert converted == (Fraction(1), Fraction(10))


@pytest.mark.parametrize(
    "changes",
    [
        {"population": "foreign"},
        {"control_value": 2.0},
        {"treatment_value": 2.0},
        {"time_horizon": "other"},
        {"prediction_origin": "other"},
        {"epoch": "other"},
        {"estimand_id": "foreign"},
        {"unit": CountUnit(label="persons")},
    ],
)
def test_resolved_quantity_mismatch_refuses_despite_matching_metadata(tmp_path, changes):
    store, _, identified_ref, native_ref = _producer_pair(tmp_path, native_changes=changes)
    with pytest.raises(ValueError, match="value_subject_(quantity|unit)_mismatch"):
        resolve_value_subject_relation(
            store,
            identification_ref=identified_ref,
            native_uncertainty_ref=native_ref,
        )


@pytest.mark.parametrize("change", ["missing", "duplicate", "extra"])
def test_complete_producer_roster_refuses_missing_extra_duplicate(tmp_path, change):
    store, _, identified_ref, native_ref = _producer_pair(tmp_path, lineage_change=change)
    with pytest.raises(ValueError, match="value_subject_(lineage|complete_lineage)"):
        persist_value_subject_relation(
            store,
            identification_ref=identified_ref,
            native_uncertainty_ref=native_ref,
        )


def test_missing_relation_and_marker_preserving_forgery_refuse(tmp_path):
    store, _, identified_ref, native_ref = _producer_pair(tmp_path)
    with pytest.raises((FileNotFoundError, ValueError)):
        load_value_subject_relation(
            store, ValueSubjectRelationRef(artifact_id="sha256:" + "f" * 64)
        )
    relation = resolve_value_subject_relation(
        store,
        identification_ref=identified_ref,
        native_uncertainty_ref=native_ref,
    )
    forged = relation.model_dump(mode="python")
    forged["native_to_identification_factor"] = 100.0
    ref = ValueSubjectRelationRef.model_validate(
        put_json_artifact(
            store,
            forged,
            kind="ir.value_subject_relation",
            schema_name="ir.value_subject_relation",
            schema_version="1.0",
            canon_spec=CanonSpec(forbid_floats=False),
            inputs=[
                InputRef(artifact_id=identity.ref.artifact_id, role=role)
                for role, identity in (
                    ("identification", relation.identification),
                    ("native_uncertainty", relation.native_uncertainty),
                    ("identification_subject", relation.identification_subject),
                    ("native_subject", relation.native_subject),
                )
            ],
        )
    )
    with pytest.raises(ValueError, match="value_subject_relation_stale_or_forged"):
        load_value_subject_relation(store, ref)


def test_selected_manifest_view_is_explicitly_unsupported(tmp_path):
    from polisyos.core.artifacts.manifest import ProducerInfo
    from polisyos.core.artifacts.store import PutOptions

    store, _, identified_ref, native_ref = _producer_pair(tmp_path)
    old_manifest = store.get_manifest(str(identified_ref.artifact_id))
    selected = store.put_json(
        get_json_artifact(store, identified_ref.artifact_id),
        PutOptions(
            kind=identified_ref.kind,
            media_type=identified_ref.media_type,
            schema=old_manifest.artifact_schema,
            inputs=old_manifest.inputs,
            producer=ProducerInfo(component="fixture.producer", version="different-view"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    assert selected.manifest_profile_sha256 is not None
    assert store.get_bytes(selected) == store.get_bytes(str(identified_ref.artifact_id))
    with pytest.raises(ValueError, match="value_subject_selected_manifest_view_unsupported"):
        resolve_value_subject_relation(
            store,
            identification_ref=selected,
            native_uncertainty_ref=native_ref,
        )
    assert (
        resolve_value_subject_relation(
            store,
            identification_ref=identified_ref,
            native_uncertainty_ref=native_ref,
        ).production_value_eligible
        is False
    )


def test_distinct_method_provenance_does_not_split_subject_coordinate(tmp_path):
    one = _producer_pair(tmp_path / "one", method_label="method.one")
    two = _producer_pair(tmp_path / "two", method_label="method.two")
    first = resolve_value_subject_relation(
        one[0], identification_ref=one[2], native_uncertainty_ref=one[3]
    )
    second = resolve_value_subject_relation(
        two[0], identification_ref=two[2], native_uncertainty_ref=two[3]
    )
    assert first.resolved_subject == second.resolved_subject
    assert first.native_uncertainty.ref.artifact_id != second.native_uncertainty.ref.artifact_id


def test_actual_bytes_corruption_refuses_before_combined_claim(tmp_path):
    store, _, identified_ref, native_ref = _producer_pair(tmp_path)
    relation_ref = persist_value_subject_relation(
        store,
        identification_ref=identified_ref,
        native_uncertainty_ref=native_ref,
    )
    blob, _ = store._paths(native_ref.artifact_id)
    blob.chmod(0o600)
    blob.write_bytes(b'{"status":"success","subject":"retained-marker"}')
    with pytest.raises(
        ValueError, match="(value_subject_artifact_content_mismatch|Blob sha256 mismatch)"
    ):
        load_value_subject_relation(FileSystemCAS(store.root), relation_ref)


def test_root_and_analytics_facades_share_canonical_types():
    import polisyos.ir as root
    import polisyos.ir.analytics as analytics
    from polisyos.ir.analytics.uncertainty import ValueSubjectRelation

    for name, owner in (
        ("ValueArtifactSubject", ValueArtifactSubject),
        ("ValueSubjectRelation", ValueSubjectRelation),
        ("ValueSubjectRelationRef", ValueSubjectRelationRef),
    ):
        assert getattr(root, name) is owner
        assert getattr(analytics, name) is owner
