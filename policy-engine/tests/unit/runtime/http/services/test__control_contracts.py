from __future__ import annotations

import pytest

from polisyos.core.contracts.control import DataSourceBinding
from polisyos.runtime.http.services import _control_contracts as contracts
from polisyos.runtime.http.services import control as runtime


def test_control_contract_helpers_are_reexported_from_runtime_module() -> None:
    assert runtime._coerce_control_job_kind is contracts._coerce_control_job_kind
    assert runtime._resolve_data_source is contracts._resolve_data_source
    assert runtime._build_api_meta is contracts._build_api_meta


def test_control_contract_helper_behavior_is_characterized() -> None:
    assert contracts._coerce_control_job_kind("workflow_run") == "workflow_run"
    with pytest.raises(ValueError, match="Unsupported control job kind"):
        contracts._coerce_control_job_kind("unknown")

    binding = DataSourceBinding(input_bindings_ref="artifact://input-bindings")
    assert contracts._resolve_data_source(binding) == (
        "input_bindings_ref",
        "artifact://input-bindings",
    )

    meta = contracts._build_api_meta("request-1")
    assert meta.request_id == "request-1"
