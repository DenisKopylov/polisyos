from __future__ import annotations

from polisyos.scientist.agent.code_verifier import CodeVerificationSandbox, VerificationStatus


def test_blocks_os_import() -> None:
    sandbox = CodeVerificationSandbox()
    result = sandbox.execute("import os\nos.system('echo pwned')")
    assert result.status == VerificationStatus.ERROR
    assert not result.passed


def test_blocks_open_builtin() -> None:
    sandbox = CodeVerificationSandbox()
    result = sandbox.execute("open('/etc/passwd').read()")
    assert result.status == VerificationStatus.ERROR
    assert not result.passed


def test_blocks_dunder_access() -> None:
    sandbox = CodeVerificationSandbox()
    result = sandbox.execute("''.__class__.__mro__")
    assert result.status == VerificationStatus.ERROR
    assert not result.passed


def test_timeout_enforced() -> None:
    sandbox = CodeVerificationSandbox()
    result = sandbox.execute("while True:\n    pass")
    assert result.status == VerificationStatus.ERROR
    assert not result.passed
    assert "timeout" in result.errors[0].lower()


def test_output_is_bounded() -> None:
    sandbox = CodeVerificationSandbox()
    code = "for _ in range(100000):\n    print('x' * 200)"
    result = sandbox.execute(code)
    assert result.status in {VerificationStatus.PASSED, VerificationStatus.ERROR}
    assert len(result.sandbox_output) <= sandbox.config.max_output_chars


def test_allows_identifiers_containing_blocked_substrings() -> None:
    sandbox = CodeVerificationSandbox()
    code = (
        "costs = [10.0, 20.0, 30.0]\n"
        "total_cost = sum(costs)\n"
        "assert total_cost == 60.0\n"
    )
    result = sandbox.execute(code)
    assert result.status == VerificationStatus.PASSED
    assert result.passed
