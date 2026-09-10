"""Replay named owner tests after the runtime's control API startup import."""
import polisyos.runtime.http.services.control.api  # noqa: F401
import pytest

raise SystemExit(pytest.main(['tests/unit/runtime/quality/test_runtime_event_log.py', 'tests/unit/runtime/quality/test_diagnostic_event_contract.py', '-q']))
