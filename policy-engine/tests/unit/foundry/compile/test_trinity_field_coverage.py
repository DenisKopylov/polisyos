from __future__ import annotations

from polisyos.foundry.compile._lowering import TRINITY_FIELD_COVERAGE, audit_trinity_field_coverage
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemFrame
from polisyos.ir.model_spec import ModelSpec


def test_trinity_field_coverage_matrix_is_complete() -> None:
    assert audit_trinity_field_coverage(strict=True) == ["trinity_coverage_audit:ok"]

    assert set(TRINITY_FIELD_COVERAGE["ProblemFrame"]) == set(ProblemFrame.model_fields)
    assert set(TRINITY_FIELD_COVERAGE["PolicySpec"]) == set(PolicySpec.model_fields)
    assert set(TRINITY_FIELD_COVERAGE["ModelSpec"]) == set(ModelSpec.model_fields)
