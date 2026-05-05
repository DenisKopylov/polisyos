"""Tests for DefaultFoundryPort (foundry_bridge adapter)."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import (
    CompileRequest,
    CompileResult,
    ExecuteRequest,
    ExecuteResult,
)
from polisyos.core.security.tee import AttestationResult, AttestationStatus
from polisyos.scientist.engine.context import FoundryPort


class TestDefaultFoundryPortCompile:
    @patch("polisyos.scientist.adapters.foundry_bridge.compile_foundry")
    @patch("polisyos.scientist.adapters.foundry_bridge.get_security_settings")
    def test_compile_success(self, mock_settings, mock_compile, tmp_path):
        mock_settings.return_value = MagicMock(tee_enabled=False)
        expected = MagicMock(spec=CompileResult)
        mock_compile.return_value = expected

        from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort

        port = DefaultFoundryPort()
        store = FileSystemCAS(tmp_path)
        request = MagicMock(spec=CompileRequest)

        result = port.compile(store, request)
        assert result is expected
        mock_compile.assert_called_once_with(store, request)

    @patch("polisyos.scientist.adapters.foundry_bridge.compile_foundry")
    @patch("polisyos.scientist.adapters.foundry_bridge.get_security_settings")
    def test_compile_error_propagation(self, mock_settings, mock_compile, tmp_path):
        mock_settings.return_value = MagicMock(tee_enabled=False)
        mock_compile.side_effect = ValueError("bad input")

        from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort

        port = DefaultFoundryPort()
        store = FileSystemCAS(tmp_path)

        with pytest.raises(ValueError, match="bad input"):
            port.compile(store, MagicMock(spec=CompileRequest))


class TestDefaultFoundryPortExecute:
    @patch("polisyos.scientist.adapters.foundry_bridge.execute_foundry")
    @patch("polisyos.scientist.adapters.foundry_bridge.get_security_settings")
    def test_execute_without_tee(self, mock_settings, mock_execute, tmp_path):
        mock_settings.return_value = MagicMock(tee_enabled=False, sbom_enabled=False)
        result_mock = MagicMock(spec=ExecuteResult)
        result_mock.derived_refs = []
        result_mock.notes = []
        mock_execute.return_value = result_mock

        from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort

        port = DefaultFoundryPort()
        store = FileSystemCAS(tmp_path)

        result = port.execute(store, MagicMock(spec=ExecuteRequest))
        assert result is not None
        mock_execute.assert_called_once()

    @patch("polisyos.scientist.adapters.foundry_bridge.execute_foundry")
    @patch("polisyos.scientist.adapters.foundry_bridge.get_security_settings")
    def test_execute_with_tee_gatekeeper(self, mock_settings, mock_execute, tmp_path):
        mock_settings.return_value = MagicMock(tee_enabled=False, sbom_enabled=False)
        gatekeeper = MagicMock()
        attestation = AttestationResult(
            status=AttestationStatus.VERIFIED,
        )
        gatekeeper.enforce.return_value = attestation

        result_mock = MagicMock()
        result_mock.derived_refs = []
        result_mock.notes = []
        # model_copy returns a new mock with updated attributes
        updated_mock = MagicMock()
        updated_mock.derived_refs = []
        updated_mock.notes = []
        result_mock.model_copy.return_value = updated_mock
        mock_execute.return_value = result_mock

        from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort

        port = DefaultFoundryPort(gatekeeper=gatekeeper)
        store = FileSystemCAS(tmp_path)

        port.execute(store, MagicMock(spec=ExecuteRequest))
        gatekeeper.enforce.assert_called_once()


class TestProtocolConformance:
    def test_implements_foundry_port_protocol(self):
        from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort

        # FoundryPort is runtime_checkable
        with patch(
            "polisyos.scientist.adapters.foundry_bridge.get_security_settings",
        ) as mock_settings:
            mock_settings.return_value = MagicMock(tee_enabled=False)
            port = DefaultFoundryPort()
            assert isinstance(port, FoundryPort)


class TestTEEEnvScope:
    def test_rejects_control_characters_in_env_values(self):
        from polisyos.scientist.adapters.foundry_bridge import (
            FoundryBridgeSecurityError,
            _tee_env_scope,
        )

        attestation = AttestationResult(
            status=AttestationStatus.VERIFIED,
            measurement="good\nBAD=1",
            verified_at=datetime.now(UTC),
        )

        with pytest.raises(FoundryBridgeSecurityError, match="control characters"):
            with _tee_env_scope(attestation):
                pass

    def test_sets_and_restores_sanitized_env_values(self):
        from polisyos.scientist.adapters.foundry_bridge import _tee_env_scope

        attestation = AttestationResult(
            status=AttestationStatus.VERIFIED,
            report_hash="abc123",
            measurement="measurement-1",
            verified_at=datetime.now(UTC),
        )

        assert os.environ.get("POLISYOS_TEE_REPORT_HASH") is None
        with _tee_env_scope(attestation):
            assert os.environ["POLISYOS_TEE_REPORT_HASH"] == "abc123"
            assert os.environ["POLISYOS_TEE_MEASUREMENT"] == "measurement-1"
        assert os.environ.get("POLISYOS_TEE_REPORT_HASH") is None
