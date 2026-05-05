"""Tests for logger compatibility formatting."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from polisyos.common import logger as logger_module


class _FakeBoundLogger:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any, tuple[Any, ...], dict[str, Any]]] = []
        self.configure_calls = 0

    def bind(self, **kwargs: Any) -> _FakeBoundLogger:
        del kwargs
        return self

    def configure(self, **kwargs: Any) -> None:
        del kwargs
        self.configure_calls += 1

    def debug(self, message: Any, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("debug", message, args, kwargs))

    def info(self, message: Any, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("info", message, args, kwargs))


def test_loguru_compat_logger_formats_percent_style_messages(monkeypatch) -> None:
    fake_logger = _FakeBoundLogger()
    monkeypatch.setattr(logger_module, "_USE_LOGURU", True)
    monkeypatch.setattr(logger_module, "_trace_context_configured", True)
    monkeypatch.setattr(logger_module, "_loguru_logger", fake_logger)

    logger = logger_module.get_logger("test.logger")
    logger.debug("Prompt cache miss model=%s key=%s", "m", "abc123")

    level, message, args, kwargs = fake_logger.calls[0]
    assert level == "debug"
    assert message == "Prompt cache miss model=m key=abc123"
    assert args == ()
    assert kwargs == {}


def test_loguru_compat_logger_preserves_brace_formatting(monkeypatch) -> None:
    fake_logger = _FakeBoundLogger()
    monkeypatch.setattr(logger_module, "_USE_LOGURU", True)
    monkeypatch.setattr(logger_module, "_trace_context_configured", True)
    monkeypatch.setattr(logger_module, "_loguru_logger", fake_logger)

    logger = logger_module.get_logger("test.logger")
    logger.info("Prompt cache hit model={} key={}", "m", "abc123")

    level, message, args, kwargs = fake_logger.calls[0]
    assert level == "info"
    assert message == "Prompt cache hit model={} key={}"
    assert args == ("m", "abc123")
    assert kwargs == {}


def test_loguru_trace_context_configuration_is_thread_safe(monkeypatch) -> None:
    fake_logger = _FakeBoundLogger()
    monkeypatch.setattr(logger_module, "_USE_LOGURU", True)
    monkeypatch.setattr(logger_module, "_trace_context_configured", False)
    monkeypatch.setattr(logger_module, "_loguru_logger", fake_logger)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: logger_module.get_logger("test.logger"), range(32)))

    assert fake_logger.configure_calls == 1


def test_stdlib_compat_logger_drops_reserved_extra_keys() -> None:
    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    base_logger = logging.getLogger("test.logger.compat")
    base_logger.handlers = []
    base_logger.setLevel(logging.INFO)
    base_logger.propagate = False
    handler = _Capture()
    base_logger.addHandler(handler)
    try:
        compat = logger_module._CompatLogger(base_logger, bound_extra={"module": "bound"})
        compat.warning("streaming warning", module="structured", artifact_id="a1")
    finally:
        base_logger.removeHandler(handler)

    assert len(records) == 1
    assert getattr(records[0], "artifact_id", None) == "a1"
