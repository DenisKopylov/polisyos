from __future__ import annotations

import pytest
from polisyos.core.contracts.foundry import ExecPlanRef, ExecuteRequest
from pydantic import ValidationError


def test_execute_request_requires_input_bindings_ref() -> None:
    with pytest.raises(ValidationError):
        ExecuteRequest(
            exec_plan_ref=ExecPlanRef(artifact_id="sha256:" + ("0" * 64)),
        )
