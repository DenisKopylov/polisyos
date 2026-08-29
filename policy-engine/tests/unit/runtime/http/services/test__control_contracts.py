from __future__ import annotations

import importlib

import pytest

from polisyos.core.contracts.control import DataSourceBinding
from polisyos.runtime.http.services import _control_contracts as contracts
from polisyos.runtime.http.services import control as runtime
from polisyos.runtime.http.services.control import (
    admission,
    api,
    response_shapes,
    run_lifecycle,
)

control_artifacts = importlib.import_module(
    "polisyos.runtime.http.services.control.artifacts"
)


def test_control_contract_helpers_are_reexported_from_runtime_module() -> None:
    assert runtime._coerce_control_job_kind is contracts._coerce_control_job_kind
    assert runtime._resolve_data_source is contracts._resolve_data_source
    assert runtime._build_api_meta is contracts._build_api_meta


def test_control_split_modules_preserve_legacy_api_aliases() -> None:
    assert runtime.ControlPlaneService is api.ControlPlaneService
    assert api.ControlPlaneService is run_lifecycle.ControlPlaneService
    assert runtime._record_control_plane_job_admission_metric is (
        admission._record_control_plane_job_admission_metric
    )
    assert runtime._build_api_meta is response_shapes._build_api_meta
    assert runtime._make_artifact_ref is control_artifacts._make_artifact_ref


def test_control_split_modules_own_moved_helpers() -> None:
    assert admission._record_control_plane_job_admission_metric.__module__ == admission.__name__
    assert control_artifacts._make_artifact_ref.__module__ == control_artifacts.__name__
    assert response_shapes._sum_call_events.__module__ == response_shapes.__name__


def test_control_contract_helper_behavior_is_characterized() -> None:
    assert contracts._coerce_control_job_kind("workflow_run") == "workflow_run"
    assert contracts._coerce_control_job_kind("acquisition") == "acquisition"
    with pytest.raises(ValueError, match="Unsupported control job kind"):
        contracts._coerce_control_job_kind("unknown")

    binding = DataSourceBinding(input_bindings_ref="artifact://input-bindings")
    assert contracts._resolve_data_source(binding) == (
        "input_bindings_ref",
        "artifact://input-bindings",
    )

    meta = contracts._build_api_meta("request-1")
    assert meta.request_id == "request-1"
