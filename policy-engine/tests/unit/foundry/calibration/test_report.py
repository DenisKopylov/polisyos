"""Content and profile admission at the Foundry calibration-report owner."""

from types import SimpleNamespace

import pytest

from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.foundry.calibration.report import (
    CalibrationReport,
    load_calibration_report,
    put_calibration_config,
    put_calibration_report,
)
from polisyos.ir.analytics.calibration import CalibrationConfig
from polisyos.scientist.nodes.builtins.simulate.propagate_welfare import _collect_input_envelopes
from polisyos.scientist.nodes.builtins.state_keys import INPUT_CALIBRATION_REPORT_REF


def test_report_same_bytes_wrong_manifest_are_rejected_by_welfare(tmp_path):
    store = FileSystemCAS(tmp_path)
    config = put_calibration_config(store, CalibrationConfig())
    report = CalibrationReport(total_loss=0, calibrated_params={"A.rate": 0.2})
    inputs = [InputRef(artifact_id=config.artifact_id, role="calibration_config")]
    valid = put_calibration_report(store, report, inputs=inputs)
    assert load_calibration_report(store, valid) == report
    forged = store.put_json(
        report,
        PutOptions(
            kind="foundry.funnel_calibration_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.CalibrationReport", version="2.0"),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
    )
    assert forged.artifact_id == valid.artifact_id  # exact same bytes, distinct CAS profile
    ctx = SimpleNamespace(store=store)
    state = SimpleNamespace(inputs={INPUT_CALIBRATION_REPORT_REF: forged})
    with pytest.raises(ValueError, match="manifest kind/schema"):
        _collect_input_envelopes(ctx, state, welfare_params={})
    # The former payload-only proxy admits these exact same bytes.
    assert CalibrationReport.model_validate(from_canonical_bytes(store.get_bytes(forged))) == report


@pytest.mark.parametrize(
    "name,version",
    [
        ("polisyos.foundry.FunnelCalibrationReport", "2.0"),
        ("polisyos.foundry.CalibrationReport", "1.0"),
    ],
)
def test_report_schema_or_payload_version_mismatch_rejected(tmp_path, name, version):
    store = FileSystemCAS(tmp_path)
    config = put_calibration_config(store, CalibrationConfig())
    ref = store.put_json(
        CalibrationReport(total_loss=0),
        PutOptions(
            kind="foundry.calibration_report",
            media_type="application/json",
            schema=SchemaInfo(name=name, version=version),
            inputs=[InputRef(artifact_id=config.artifact_id, role="calibration_config")],
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
    )
    with pytest.raises(ValueError, match="schema|version"):
        load_calibration_report(store, ref)


def test_calibration_configuration_edge_requires_resolved_correct_kind(tmp_path):
    store = FileSystemCAS(tmp_path)
    fake_config = store.put_json(
        CalibrationConfig(),
        PutOptions(kind="foundry.unrelated", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    report = put_calibration_report(
        store,
        CalibrationReport(total_loss=0),
        inputs=[InputRef(artifact_id=fake_config.artifact_id, role="calibration_config")],
    )
    with pytest.raises(ValueError, match="calibration_config manifest"):
        load_calibration_report(store, report)
