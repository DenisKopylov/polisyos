"""Tests for engine/runner/error_classifier.py."""

from __future__ import annotations

from polisyos.scientist.orchestration.engine.runner.error_classifier import (
    RemoteErrorCategory,
    classify_remote_error,
    should_retry,
)

# ---------------------------------------------------------------------------
# classify_remote_error
# ---------------------------------------------------------------------------


class TestClassifyRemoteError:
    """Verify correct classification for known exception types."""

    def test_timeout_error_is_transient(self) -> None:
        assert classify_remote_error(TimeoutError()) is RemoteErrorCategory.TRANSIENT

    def test_asyncio_timeout_is_transient(self) -> None:
        assert classify_remote_error(TimeoutError()) is RemoteErrorCategory.TRANSIENT

    def test_connection_error_is_transient(self) -> None:
        assert classify_remote_error(ConnectionError("refused")) is RemoteErrorCategory.TRANSIENT

    def test_connection_refused_is_transient(self) -> None:
        assert classify_remote_error(ConnectionRefusedError()) is RemoteErrorCategory.TRANSIENT

    def test_os_error_is_transient(self) -> None:
        assert (
            classify_remote_error(OSError("network unreachable")) is RemoteErrorCategory.TRANSIENT
        )

    def test_value_error_is_fatal(self) -> None:
        assert classify_remote_error(ValueError("bad param")) is RemoteErrorCategory.FATAL

    def test_type_error_is_fatal(self) -> None:
        assert classify_remote_error(TypeError("wrong type")) is RemoteErrorCategory.FATAL

    def test_memory_error_is_fatal(self) -> None:
        assert classify_remote_error(MemoryError()) is RemoteErrorCategory.FATAL

    def test_not_implemented_error_is_fatal(self) -> None:
        assert classify_remote_error(NotImplementedError()) is RemoteErrorCategory.FATAL

    def test_unknown_exception_is_unknown(self) -> None:
        class CustomError(Exception):
            pass

        assert classify_remote_error(CustomError()) is RemoteErrorCategory.UNKNOWN

    def test_name_based_transient(self) -> None:
        """Exception with a well-known transient type name is classified correctly."""

        class RayTaskError(Exception):
            pass

        assert classify_remote_error(RayTaskError()) is RemoteErrorCategory.TRANSIENT

    def test_name_based_fatal(self) -> None:
        """Exception with a well-known fatal type name is classified correctly."""

        class ValidationError(Exception):
            pass

        assert classify_remote_error(ValidationError()) is RemoteErrorCategory.FATAL

    def test_error_category_attribute_transient(self) -> None:
        """If exc has default_category=TRANSIENT, classify as transient."""
        from polisyos.core.errors import ErrorCategory

        class AppError(Exception):
            default_category = ErrorCategory.TRANSIENT

        assert classify_remote_error(AppError()) is RemoteErrorCategory.TRANSIENT

    def test_error_category_attribute_fatal(self) -> None:
        from polisyos.core.errors import ErrorCategory

        class AppError(Exception):
            default_category = ErrorCategory.FATAL

        assert classify_remote_error(AppError()) is RemoteErrorCategory.FATAL


# ---------------------------------------------------------------------------
# should_retry
# ---------------------------------------------------------------------------


class TestShouldRetry:
    """Verify retry decisions."""

    def test_transient_always_retries(self) -> None:
        assert should_retry(TimeoutError(), attempt=0) is True
        assert should_retry(TimeoutError(), attempt=5) is True

    def test_fatal_never_retries(self) -> None:
        assert should_retry(ValueError(), attempt=0) is False

    def test_unknown_retries_once(self) -> None:
        class X(Exception):
            pass

        assert should_retry(X(), attempt=0) is True
        assert should_retry(X(), attempt=1) is False
        assert should_retry(X(), attempt=2) is False
