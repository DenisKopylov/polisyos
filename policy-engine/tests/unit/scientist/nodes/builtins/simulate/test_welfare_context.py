from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import Metrics
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)
from polisyos.ir.registry.refs import ArtifactRefModel
from polisyos.scientist.nodes.builtins.simulate.welfare_context import (
    _admit_input_envelope,
    _extract_numeric_metrics,
    _resolve_base_response,
    _resolve_pe_sensitivity,
    _resolve_weights,
)
from polisyos.scientist.nodes.builtins.simulate.welfare_types import _WelfareNodeFailure


def _envelope(value: float = 1.0) -> UncertaintyEnvelope:
    return UncertaintyEnvelope(
        point_estimate=value,
        confidence_interval=(value - 0.5, value + 0.5),
        distribution_family=DistributionFamily.UNKNOWN,
        source=UncertaintySource.TRUST,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        metadata={"param_name": "rate"},
    )


def test_base_response_obeys_declared_order_and_refuses_missing_metric() -> None:
    labels, response = _resolve_base_response(
        welfare_params={
            "pe_response": {"benefit": 20.0, "cost": 3.0},
            "metric_order": ["cost", "benefit"],
        },
        numeric_metrics={},
    )

    assert labels == ("cost", "benefit")
    assert response.tolist() == [3.0, 20.0]

    with pytest.raises(_WelfareNodeFailure) as failure:
        _resolve_base_response(
            welfare_params={"metric_order": ["benefit", "missing"]},
            numeric_metrics={"benefit": 20.0},
        )

    assert failure.value.error.code == "ERROR_WELFARE_DIMENSION_MISMATCH"


@pytest.mark.parametrize("malformed", [None, "malformed", 42, {"fallback": "invalid"}])
def test_malformed_present_response_does_not_fall_back_to_valid_metrics(malformed) -> None:
    with pytest.raises(_WelfareNodeFailure) as failure:
        _resolve_base_response(
            welfare_params={"pe_response": malformed, "metric_order": ["fallback"]},
            numeric_metrics={"fallback": 9.0},
        )

    assert failure.value.error.code == "ERROR_WELFARE_DIMENSION_MISMATCH"


@pytest.mark.parametrize("response", [[], {}])
def test_present_empty_response_is_not_an_empty_welfare_basis(response: object) -> None:
    with pytest.raises(_WelfareNodeFailure) as failure:
        _resolve_base_response(
            welfare_params={"pe_response": response},
            numeric_metrics={"fallback": 9.0},
        )

    assert failure.value.error.code == "ERROR_WELFARE_DIMENSION_MISMATCH"


@pytest.mark.parametrize("weights", [[], {}])
def test_present_empty_weights_cannot_define_an_empty_aggregation(weights: object) -> None:
    with pytest.raises(_WelfareNodeFailure) as failure:
        _resolve_weights(None, welfare_params={"weights": weights}, labels=("benefit",))

    assert failure.value.error.code == "ERROR_WELFARE_DIMENSION_MISMATCH"


@pytest.mark.parametrize("boolean", [True, np.bool_(True)])
def test_response_admission_rejects_boolean_numeric_scalars(boolean: object) -> None:
    with pytest.raises(_WelfareNodeFailure) as failure:
        _resolve_base_response(
            welfare_params={"pe_response": [boolean]},
            numeric_metrics={"fallback": 9.0},
        )

    assert failure.value.error.code == "ERROR_WELFARE_DIMENSION_MISMATCH"


def test_selected_response_rejects_malformed_unselected_mapping_value() -> None:
    with pytest.raises(_WelfareNodeFailure) as failure:
        _resolve_base_response(
            welfare_params={
                "pe_response": {"benefit": 2.0, "unselected": np.bool_(True)},
                "metric_order": ["benefit"],
            },
            numeric_metrics={"benefit": 9.0},
        )

    assert failure.value.error.code == "ERROR_WELFARE_DIMENSION_MISMATCH"


@pytest.mark.parametrize("boolean", [True, np.bool_(True)])
def test_weight_admission_rejects_boolean_numeric_scalars(tmp_path: Path, boolean: object) -> None:
    with pytest.raises(_WelfareNodeFailure) as failure:
        _resolve_weights(
            SimpleNamespace(store=FileSystemCAS(tmp_path)),
            welfare_params={"weights": [boolean]},
            labels=("benefit",),
        )

    assert failure.value.error.code == "ERROR_WELFARE_DIMENSION_MISMATCH"


def test_selected_weights_reject_malformed_unselected_mapping_value(tmp_path: Path) -> None:
    with pytest.raises(_WelfareNodeFailure) as failure:
        _resolve_weights(
            SimpleNamespace(store=FileSystemCAS(tmp_path)),
            welfare_params={"weights": {"benefit": 1.0, "unselected": np.bool_(True)}},
            labels=("benefit",),
        )

    assert failure.value.error.code == "ERROR_WELFARE_DIMENSION_MISMATCH"


def test_sensitivity_admission_rejects_numpy_boolean_coefficient() -> None:
    with pytest.raises(_WelfareNodeFailure) as failure:
        _resolve_pe_sensitivity(
            welfare_params={"pe_sensitivity": {"benefit": {"rate": np.bool_(True)}}},
            labels=("benefit",),
        )

    assert failure.value.error.code == "ERROR_WELFARE_DIMENSION_MISMATCH"


def test_response_does_not_coerce_numeric_strings() -> None:
    with pytest.raises(_WelfareNodeFailure) as failure:
        _resolve_base_response(
            welfare_params={"pe_response": ["2.5"]},
            numeric_metrics={"fallback": 9.0},
        )

    assert failure.value.error.code == "ERROR_WELFARE_DIMENSION_MISMATCH"


def test_weights_do_not_coerce_numeric_strings(tmp_path: Path) -> None:
    with pytest.raises(_WelfareNodeFailure) as failure:
        _resolve_weights(
            SimpleNamespace(store=FileSystemCAS(tmp_path)),
            welfare_params={"weights": ["0.5"]},
            labels=("benefit",),
        )

    assert failure.value.error.code == "ERROR_WELFARE_DIMENSION_MISMATCH"


def test_sensitivity_does_not_coerce_numeric_strings() -> None:
    with pytest.raises(_WelfareNodeFailure) as failure:
        _resolve_pe_sensitivity(
            welfare_params={"pe_sensitivity": {"benefit": {"rate": "1.25"}}},
            labels=("benefit",),
        )

    assert failure.value.error.code == "ERROR_WELFARE_DIMENSION_MISMATCH"


def test_numeric_admission_preserves_decimal_numpy_and_declared_metric_strings(
    tmp_path: Path,
) -> None:
    labels, response = _resolve_base_response(
        welfare_params={"pe_response": [Decimal("2.5")]},
        numeric_metrics={},
    )
    weights, _ = _resolve_weights(
        SimpleNamespace(store=FileSystemCAS(tmp_path)),
        welfare_params={"weights": [np.float32(0.5)]},
        labels=labels,
    )
    sensitivity = _resolve_pe_sensitivity(
        welfare_params={"pe_sensitivity": {"component_0": {"rate": Decimal("1.25")}}},
        labels=labels,
    )

    assert response.tolist() == [2.5]
    assert weights.tolist() == [0.5]
    assert sensitivity == {"component_0": {"rate": 1.25}}
    assert _extract_numeric_metrics(
        Metrics(values={"numeric_metric": "3.25", "descriptive_metric": "qualitative"})
    ) == {"numeric_metric": 3.25}


@pytest.mark.parametrize("malformed", [None, {}, ["benefit", "benefit"], "benefit"])
def test_malformed_present_metric_order_does_not_become_omission(malformed) -> None:
    with pytest.raises(_WelfareNodeFailure) as failure:
        _resolve_base_response(
            welfare_params={"metric_order": malformed},
            numeric_metrics={"fallback": 9.0},
        )

    assert failure.value.error.code == "ERROR_WELFARE_DIMENSION_MISMATCH"


def test_all_invalid_present_sensitivity_does_not_become_identity_default() -> None:
    with pytest.raises(_WelfareNodeFailure) as failure:
        _resolve_pe_sensitivity(
            welfare_params={"pe_sensitivity": {"benefit": {"rate": "invalid"}}},
            labels=("benefit",),
        )

    assert failure.value.error.code == "ERROR_WELFARE_DIMENSION_MISMATCH"


@pytest.mark.parametrize(
    "malformed",
    [None, {}, "invalid", {"benefit": {"rate": "invalid"}}, {"other": {"rate": 1.0}}],
)
def test_present_sensitivity_rejects_each_malformed_shape(malformed) -> None:
    with pytest.raises(_WelfareNodeFailure) as failure:
        _resolve_pe_sensitivity(
            welfare_params={"pe_sensitivity": malformed},
            labels=("benefit",),
        )

    assert failure.value.error.code == "ERROR_WELFARE_DIMENSION_MISMATCH"


def test_malformed_sensitivity_entry_is_not_dropped_beside_valid_entry() -> None:
    with pytest.raises(_WelfareNodeFailure) as failure:
        _resolve_pe_sensitivity(
            welfare_params={
                "pe_sensitivity": {
                    "benefit": {"rate": 2.0},
                    "cost": {"cost": "invalid"},
                }
            },
            labels=("benefit", "cost"),
        )

    assert failure.value.error.code == "ERROR_WELFARE_DIMENSION_MISMATCH"


def test_explicit_null_weights_do_not_select_single_label_default() -> None:
    with pytest.raises(_WelfareNodeFailure) as failure:
        _resolve_weights(
            None,
            welfare_params={"weights": None},
            labels=("benefit",),
        )

    assert failure.value.error.code == "ERROR_WELFARE_DIMENSION_MISMATCH"


def test_envelope_admission_deduplicates_same_source_but_records_source_conflict(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    first_ref = ArtifactRefModel.model_validate(
        store.put_json(
            {"source": "first"},
            PutOptions(kind="test.welfare_input", media_type="application/json"),
        ).model_dump()
    )
    other_ref = ArtifactRefModel.model_validate(
        store.put_json(
            {"source": "other"},
            PutOptions(kind="test.welfare_input", media_type="application/json"),
        ).model_dump()
    )
    envelopes = {}
    refs = {}
    origins = {}
    calibration_issues: set[str] = set()

    _admit_input_envelope(
        "rate",
        _envelope(),
        source_role="calibration_report",
        envelopes=envelopes,
        refs=refs,
        origins=origins,
        calibration_issues=calibration_issues,
        origin_ref=first_ref,
    )
    # Equal values under the same content-addressed source are one admitted input.
    assert calibration_issues == set()
    assert origins["rate"].artifact_key == (first_ref.kind, str(first_ref.artifact_id))

    _admit_input_envelope(
        "rate",
        _envelope(),
        source_role="inline",
        envelopes=envelopes,
        refs=refs,
        origins=origins,
        calibration_issues=calibration_issues,
        origin_ref=other_ref,
    )
    assert "calibration_envelope_conflict" in calibration_issues
    # A conflict cannot silently replace the previously admitted source.
    assert origins["rate"].artifact_key == (first_ref.kind, str(first_ref.artifact_id))


def test_pe_sensitivity_retains_valid_entries_and_defaults_only_when_all_are_absent() -> None:
    resolved = _resolve_pe_sensitivity(
        welfare_params={"pe_sensitivity": {"benefit": {"rate": 2.5}}},
        labels=("benefit", "cost"),
    )

    # An explicit sparse map stays sparse; only an absent field receives identity defaults.
    assert resolved == {"benefit": {"rate": 2.5}}
    assert _resolve_pe_sensitivity(welfare_params={}, labels=("cost",)) == {"cost": {"cost": 1.0}}
