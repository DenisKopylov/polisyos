from __future__ import annotations

import builtins

import pytest

from polisyos.scientist.agent.code_verifier import (
    CodeVerificationSandbox,
    DraftVariableExtractor,
    SandboxConfig,
    VerificationCodeExtractor,
    VerificationStatus,
    _apply_resource_limits,
    _load_allowed_modules,
    _verification_worker,
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


def test_verification_code_extractor_accepts_think_prefixed_json() -> None:
    raw = '<think>verification reasoning</think>{"verification_code":"assert 2 == 2"}'

    assert VerificationCodeExtractor.extract_from_llm_response(raw) == "assert 2 == 2"


def test_draft_variable_extractor() -> None:
    variables = DraftVariableExtractor.extract(_draft(), _problem_frame())
    assert variables["total_budget"] == 1000.0
    assert len(variables["intervention_rates"]) == 2


def test_code_verifier_passes_simple_assertion() -> None:
    sandbox = CodeVerificationSandbox()
    result = sandbox.execute(
        "assert sum(intervention_rates) <= 2.0",
        variables={"intervention_rates": [1, 1]},
    )
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


def test_code_verifier_timeout_kills_process() -> None:
    sandbox = CodeVerificationSandbox(SandboxConfig(timeout_seconds=0.1, cpu_seconds_limit=1))
    result = sandbox.execute("while True:\n    pass")

    assert result.status == VerificationStatus.ERROR
    assert not result.passed
    assert "timeout" in result.errors[0].lower()


def test_load_allowed_modules_assertion_is_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def _import(name: str, *args, **kwargs):
        if name == "math":
            raise AssertionError("module import invariant failed")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _import)

    with pytest.raises(AssertionError, match="module import invariant failed"):
        _load_allowed_modules(("math",))


def test_apply_resource_limits_import_assertion_is_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def _import(name: str, *args, **kwargs):
        if name == "resource":
            raise AssertionError("resource import invariant failed")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _import)

    with pytest.raises(AssertionError, match="resource import invariant failed"):
        _apply_resource_limits(SandboxConfig())


def test_verification_worker_restrictedpython_import_assertion_is_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Queue:
        def put(self, _payload) -> None:
            raise AssertionError("queue should not be used on helper assertion")

    monkeypatch.setattr(
        "polisyos.scientist.agent.code_verifier._apply_resource_limits",
        lambda _config: None,
    )
    monkeypatch.setattr(
        "polisyos.scientist.agent.code_verifier._load_allowed_modules",
        lambda _modules: {},
    )
    original_import = builtins.__import__

    def _import(name: str, *args, **kwargs):
        if name == "RestrictedPython":
            raise AssertionError("restrictedpython import invariant failed")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _import)

    with pytest.raises(AssertionError, match="restrictedpython import invariant failed"):
        _verification_worker(
            "pass",
            {},
            SandboxConfig(use_restrictedpython_if_available=True).model_dump(mode="python"),
            _Queue(),
        )
