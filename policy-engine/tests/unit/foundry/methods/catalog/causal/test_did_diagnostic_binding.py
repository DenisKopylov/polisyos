"""Independent diagnostic mathematics and current-input/result custody witnesses."""

from __future__ import annotations

import copy
import hashlib
import json
import math

import numpy as np
import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.did import (
    StaggeredDifferenceInDifferences,
    StandardDifferenceInDifferences,
)
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
from polisyos.foundry.methods.components.io import dematerialize_method_output
from polisyos.ir.analytics.causal import (
    EstimationStatus,
    load_causal_effect_report,
    persist_causal_effect_report,
)


def _panel(pre: int = 3) -> PanelObservationalData:
    timing = np.array([3, 3, 4, 4, -1, -1, -1, -1])
    outcome = np.tile(np.arange(6, dtype=float), (8, 1))
    outcome[:4, :3] += np.array([0.0, 0.5, -0.3])
    outcome[:2, 3:] += np.array([1.0, 3.0])[:, None]
    outcome[2:4, 4:] += np.array([2.0, 5.0])[:, None]
    outcome[4:, 3:] += np.arange(4)[:, None] * 0.2
    return PanelObservationalData(
        outcome=outcome,
        treatment=(timing >= 0).astype(int),
        time_treatment=pre,
        treatment_timing=timing,
        unit_ids=np.arange(8),
    )


def _run(method, data):
    return method.pure_step(data, {"n_bootstrap": 99, "__rng__": np.random.default_rng(13)})


def _sha(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


@pytest.mark.parametrize(
    "method", [StandardDifferenceInDifferences, StaggeredDifferenceInDifferences]
)
def test_native_report_and_actual_canonical_slots_preserve_complete_diagnostics(method, tmp_path):
    data = _panel()
    output = _run(method, data)
    report = output["report"]
    assert report.status is EstimationStatus.SUCCESS
    expected = method._diagnostic_contract(data)
    assert all(report.method_params[key] == value for key, value in expected.items())
    contract = expected["diagnostic_contract"]
    diagnostics = [diagnostic.model_dump(mode="json") for diagnostic in report.diagnostics]
    assert diagnostics == contract["diagnostics"]
    assert contract["result_sha256"] == _sha(diagnostics)
    assert expected["diagnostic_binding"] == _sha(contract)
    assert contract["identification_authority"] is False
    # Execute the real native output-slot projection rather than inspect raw alias names.
    slots = dematerialize_method_output(
        method_class=method, signature=method.signature, output=output
    )
    assert slots["report"] is report and slots["result"] is report
    assert slots["envelope"] is output["envelope"]
    assert slots["uncertainty_envelope"] is output["envelope"]
    ref = persist_causal_effect_report(FileSystemCAS(tmp_path), report)
    fresh = load_causal_effect_report(FileSystemCAS(tmp_path), ref)
    assert fresh.diagnostics == report.diagnostics
    assert fresh.method_params == report.method_params
    assert fresh.model_dump(mode="json") == report.model_dump(mode="json")


def test_time_treatment_changes_diagnostic_basis_without_changing_scalar_target():
    old_data = _panel(pre=2)
    current_data = old_data.model_copy(update={"time_treatment": 3})
    old = _run(StaggeredDifferenceInDifferences, old_data)["report"]
    current = _run(StaggeredDifferenceInDifferences, current_data)["report"]
    assert old.point_estimate == current.point_estimate
    assert old.confidence_interval == current.confidence_interval
    assert old.p_value == current.p_value
    for key in ("target_contract", "target_binding"):
        assert old.method_params[key] == current.method_params[key]
    assert old.diagnostics[0].details["status"] == "not_testable"
    assert old.diagnostics != current.diagnostics
    for key in ("diagnostic_contract", "diagnostic_binding"):
        assert old.method_params[key] != current.method_params[key]


@pytest.mark.parametrize("field", ["outcome", "treatment", "time_treatment"])
@pytest.mark.parametrize(
    "method", [StandardDifferenceInDifferences, StaggeredDifferenceInDifferences]
)
def test_every_actual_diagnostic_input_is_bound_even_if_result_does_not_change(field, method):
    data = _panel()
    value = getattr(data, field)
    if field == "outcome":
        value = value.copy()
        value[0, -1] += 1  # Outside the preperiod: same diagnostic, different source.
    elif field == "treatment":
        value = value.copy()
        value[0] = 0
    else:
        value = 4
    changed = data.model_copy(update={field: value})
    first = method._diagnostic_contract(data)
    second = method._diagnostic_contract(changed)
    assert (
        first["diagnostic_contract"]["input_sha256"]
        != second["diagnostic_contract"]["input_sha256"]
    )
    assert first["diagnostic_binding"] != second["diagnostic_binding"]
    if field == "outcome":
        assert (
            first["diagnostic_contract"]["diagnostics"]
            == second["diagnostic_contract"]["diagnostics"]
        )


@pytest.mark.parametrize("pre", [3, 4, 5])
def test_closed_form_centered_slope_hc1_and_normal_tail_oracle(pre):
    data = _panel(pre=pre)
    result = StaggeredDifferenceInDifferences._diagnostic_contract(data)
    diagnostic = result["diagnostic_contract"]["diagnostics"][0]
    # Derive the two-column HC1 sandwich from centered time scores, without owner OLS.
    differences = np.array(
        [
            sum(data.outcome[i, t] for i in range(4)) / 4
            - sum(data.outcome[i, t] for i in range(4, 8)) / 4
            for t in range(pre)
        ]
    )
    times = np.arange(pre, dtype=float)
    centered = times - times.mean()
    sxx = sum(centered**2)
    slope = sum(centered * differences) / sxx
    fitted = differences.mean() + slope * centered
    residual = differences - fitted
    se = math.sqrt(pre / (pre - 2) * sum(centered**2 * residual**2) / sxx**2)
    z = slope / se
    p = math.erfc(abs(z) / math.sqrt(2))
    assert diagnostic["statistic"] == pytest.approx(slope, abs=2e-14)
    assert diagnostic["details"]["slope_se"] == pytest.approx(se, abs=2e-14)
    assert diagnostic["details"]["z_score"] == pytest.approx(z, abs=2e-13)
    assert diagnostic["p_value"] == pytest.approx(p, abs=2e-14)
    assert diagnostic["passed"] is (p > 0.05)
    assert diagnostic["details"]["identification_authority"] is False


@pytest.mark.parametrize("pre", [0, 1, 2])
@pytest.mark.parametrize(
    "method", [StandardDifferenceInDifferences, StaggeredDifferenceInDifferences]
)
def test_internal_projection_preserves_not_testable_and_standard_invalid_dispositions(pre, method):
    data = _panel(pre)
    contract = method._diagnostic_contract(data)["diagnostic_contract"]
    first = contract["diagnostics"][0]
    assert first["statistic"] is None and first["p_value"] is None
    assert first["passed"] is False
    assert first["details"]["status"] == "not_testable"
    assert first["details"]["identification_authority"] is False
    report = _run(method, data)["report"]
    if pre == 0 and method is StandardDifferenceInDifferences:
        assert report.status is EstimationStatus.INPUT_INVALID
        assert report.diagnostics == []
        assert "diagnostic_contract" not in report.method_params
    else:
        assert report.status is EstimationStatus.SUCCESS
        assert [d.model_dump(mode="json") for d in report.diagnostics] == contract["diagnostics"]


@pytest.mark.parametrize(
    "method", [StandardDifferenceInDifferences, StaggeredDifferenceInDifferences]
)
def test_missing_group_remains_descriptive_not_testable_without_authority(method):
    data = _panel().model_copy(update={"treatment": np.ones(8, dtype=int)})
    contract = method._diagnostic_contract(data)["diagnostic_contract"]
    diagnostic = contract["diagnostics"][0]
    assert diagnostic["details"]["reason"] == "treated_or_control_group_missing"
    assert diagnostic["passed"] is False
    assert contract["identification_authority"] is False
    assert _run(method, data)["report"].status is EstimationStatus.INPUT_INVALID


@pytest.mark.parametrize("field", ["statistic", "p_value", "passed", "details"])
def test_diagnostic_payload_tamper_retains_markers_but_disagrees_with_recomputation(field):
    data = _panel()
    report = _run(StaggeredDifferenceInDifferences, data)["report"]
    payload = copy.deepcopy(report.model_dump(mode="json"))
    replacements = {
        "statistic": 99.0,
        "p_value": 0.99,
        "passed": True,
        "details": {"status": "no_detected_pretrend", "identification_authority": True},
    }
    # Flip passed, regardless of the real current classification.
    if field == "passed":
        replacements[field] = not payload["diagnostics"][0][field]
    payload["diagnostics"][0][field] = replacements[field]
    assert payload["method_params"] == report.model_dump(mode="json")["method_params"]
    expected = StaggeredDifferenceInDifferences._diagnostic_contract(data)
    assert payload["diagnostics"] != expected["diagnostic_contract"]["diagnostics"]


def test_mapping_reconstruction_keeps_contract_after_json_transport():
    data = _panel()
    payload = json.loads(data.model_dump_json())
    assert StaggeredDifferenceInDifferences._diagnostic_contract(
        payload
    ) == StaggeredDifferenceInDifferences._diagnostic_contract(data)
