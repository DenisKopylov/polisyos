from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.contracts.foundry import ExecPlanRef, ExecuteRequest


def test_execute_request_requires_input_bindings_ref() -> None:
    with pytest.raises(ValidationError):
        ExecuteRequest(
            exec_plan_ref=ExecPlanRef(artifact_id="sha256:" + ("0" * 64)),
        )
