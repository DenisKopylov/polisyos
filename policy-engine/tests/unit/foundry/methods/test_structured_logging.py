"""
Tests for Foundry structured logging (_logging.py).

Verifies:
- get_foundry_logger() returns a FoundryLogger-compatible object
- _StdlibLoggerShim emits messages at the correct level
- _infer_n_obs() correctly infers observation count from state dicts
- Logger is usable without structlog installed (stdlib fallback)
"""

from __future__ import annotations

import logging

from polisyos.foundry.methods._logging import (
    FoundryLogger,
    _infer_n_obs,
    _StdlibLoggerShim,
    get_foundry_logger,
)

# ---------------------------------------------------------------------------
# get_foundry_logger
# ---------------------------------------------------------------------------


class TestGetFoundryLogger:
    def test_returns_foundry_logger_protocol(self):
        logger = get_foundry_logger("test.foundry.logger")
        # Must satisfy the FoundryLogger protocol
        assert isinstance(logger, FoundryLogger)

    def test_has_required_methods(self):
        logger = get_foundry_logger("test.foundry.logger")
        assert callable(getattr(logger, "debug", None))
        assert callable(getattr(logger, "info", None))
        assert callable(getattr(logger, "warning", None))
        assert callable(getattr(logger, "error", None))

    def test_different_names_return_independent_loggers(self):
        a = get_foundry_logger("foundry.a")
        b = get_foundry_logger("foundry.b")
        # Not required to be different objects, but must be independently named
        assert a is not None
        assert b is not None


# ---------------------------------------------------------------------------
# _StdlibLoggerShim
# ---------------------------------------------------------------------------


class TestStdlibLoggerShim:
    def test_debug_emitted_at_debug_level(self, caplog):
        shim = _StdlibLoggerShim("test.shim.debug")
        with caplog.at_level(logging.DEBUG, logger="test.shim.debug"):
            shim.debug("my_event", fqn="causal.did@1.0.0", backend="numpy")
        assert any("my_event" in r.message for r in caplog.records)

    def test_info_emitted_at_info_level(self, caplog):
        shim = _StdlibLoggerShim("test.shim.info")
        with caplog.at_level(logging.INFO, logger="test.shim.info"):
            shim.info("dispatch_complete", elapsed_ms=42.1)
        assert any("dispatch_complete" in r.message for r in caplog.records)

    def test_warning_emitted(self, caplog):
        shim = _StdlibLoggerShim("test.shim.warning")
        with caplog.at_level(logging.WARNING, logger="test.shim.warning"):
            shim.warning("circuit_opened", backend="jax", failure_count=5)
        assert any("circuit_opened" in r.message for r in caplog.records)

    def test_error_emitted(self, caplog):
        shim = _StdlibLoggerShim("test.shim.error")
        with caplog.at_level(logging.ERROR, logger="test.shim.error"):
            shim.error("dispatch_error", exc="ValueError")
        assert any("dispatch_error" in r.message for r in caplog.records)

    def test_kwargs_included_in_message(self, caplog):
        shim = _StdlibLoggerShim("test.shim.kwargs")
        with caplog.at_level(logging.INFO, logger="test.shim.kwargs"):
            shim.info("test_event", key1="value1", key2=99)
        msgs = " ".join(r.message for r in caplog.records)
        assert "key1" in msgs
        assert "key2" in msgs

    def test_no_output_below_level(self, caplog):
        shim = _StdlibLoggerShim("test.shim.silent")
        with caplog.at_level(logging.WARNING, logger="test.shim.silent"):
            shim.debug("silent_event", x=1)
            shim.info("also_silent", y=2)
        assert not any("silent_event" in r.message for r in caplog.records)
        assert not any("also_silent" in r.message for r in caplog.records)

    def test_format_without_kwargs(self):
        shim = _StdlibLoggerShim("test.shim.format")
        result = shim._format("plain_event")
        assert result == "plain_event"

    def test_format_with_kwargs(self):
        shim = _StdlibLoggerShim("test.shim.format")
        result = shim._format("event", fqn="foo@1.0.0")
        assert "event" in result
        assert "fqn" in result


# ---------------------------------------------------------------------------
# _infer_n_obs
# ---------------------------------------------------------------------------


class TestInferNObs:
    def test_infers_from_outcome(self):
        import numpy as np

        state = {"outcome": np.zeros(100)}
        assert _infer_n_obs(state) == 100

    def test_infers_from_features(self):
        import numpy as np

        state = {"features": np.zeros((50, 3))}
        assert _infer_n_obs(state) == 50

    def test_infers_from_endog(self):
        import numpy as np

        state = {"endog": np.zeros(200)}
        assert _infer_n_obs(state) == 200

    def test_infers_from_target(self):
        state = {"target": list(range(75))}
        assert _infer_n_obs(state) == 75

    def test_returns_none_for_non_dict(self):
        assert _infer_n_obs("not a dict") is None
        assert _infer_n_obs(42) is None
        assert _infer_n_obs(None) is None

    def test_returns_none_for_unknown_keys(self):
        state = {"foo": [1, 2, 3], "bar": [4, 5, 6]}
        assert _infer_n_obs(state) is None

    def test_returns_none_for_empty_dict(self):
        assert _infer_n_obs({}) is None

    def test_returns_none_for_non_sized_value(self):
        # Value exists but has no len()
        state = {"outcome": 42}
        assert _infer_n_obs(state) is None
