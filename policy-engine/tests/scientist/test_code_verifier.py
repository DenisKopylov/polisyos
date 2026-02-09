from __future__ import annotations

from polisyos.scientist.agent.code_verifier import (
    CodeVerificationSandbox,
    DraftVariableExtractor,
    VerificationCodeExtractor,
    VerificationStatus,
)
from polisyos.scientist.agent.protocols import DraftResult, ProblemFrame


def _problem_frame() -> ProblemFrame:
    return ProblemFrame(
        frame_id="pf_verifier",
        domain="economic",
        problem_statement="Reduce poverty while preserving budget",
        constraints=("Budget <= 1000",),
    )


def _draft() -> DraftResult:
    return DraftResult(
        draft_id="draft_1",
        problem_frame_ref="pf_verifier",
        narrative="sample",
        interventions=[
            {"kind": "tax_subsidy", "params": {"rate": 0.6}, "cost": 700},
            {"kind": "income_tax", "params": {"rate": 0.5}, "cost": 500},
        ],
        rationale="r",
        confidence=0.7,
    )


def test_verification_code_extractor() -> None:
    raw = '{"findings":[],"confidence_adjustment":0.0,"verification_code":"assert 1 == 1"}'
    code = VerificationCodeExtractor.extract_from_llm_response(raw)
    assert code == "assert 1 == 1"


def test_draft_variable_extractor() -> None:
    variables = DraftVariableExtractor.extract(_draft(), _problem_frame())
    assert variables["total_budget"] == 1000.0
    assert len(variables["intervention_rates"]) == 2


def test_code_verifier_passes_simple_assertion() -> None:
    sandbox = CodeVerificationSandbox()
    result = sandbox.execute("assert sum(intervention_rates) <= 2.0", variables={"intervention_rates": [1, 1]})
    assert result.status == VerificationStatus.PASSED
    assert result.passed


def test_code_verifier_reports_assertion_failure() -> None:
    sandbox = CodeVerificationSandbox()
    result = sandbox.execute(
        'assert sum(intervention_rates) <= 1.0, "Rates exceed 100%"',
        variables={"intervention_rates": [0.7, 0.6]},
    )
    assert result.status == VerificationStatus.FAILED
    assert not result.passed
    assert "Rates exceed 100%" in result.errors[0]
    findings = result.to_findings()
    assert findings
    assert findings[0]["category"] == "parameter_error"

