"""Behavioral tests for the Python consumer of the DS18 execution outcome."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

POLICY_ENGINE_ROOT = Path(__file__).resolve().parents[2]
ADAPTER_PATH = POLICY_ENGINE_ROOT / "apps/runtime-dashboard/scripts/persist_atlas_evidence.py"


def _load_adapter() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "ds18_execution_outcome_consumer_under_test",
        ADAPTER_PATH,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("could not load Atlas evidence persistence adapter")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _completed(stdout: bytes, *, returncode: int = 0, stderr: bytes = b"") -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def _established_outcome() -> dict[str, object]:
    return {
        "kind": "established",
        "projection": {
            "predicate_provenance": "independently_reconciled",
            "source_file_count": 623,
            "root_count": 759,
            "obligated_root_count": 126,
            "covered_root_count": 126,
        },
    }


def test_python_consumer_invokes_the_typed_outcome_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _load_adapter()
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        calls.append((command, kwargs))
        return _completed(json.dumps(_established_outcome()).encode("utf-8"))

    monkeypatch.setattr(adapter.subprocess, "run", fake_run)
    node = Path("/fixed/node")

    outcome = adapter._ds18_time_semantics_coverage_projection(node)

    assert outcome == _established_outcome()  # noqa: S101 - behavioral contract
    assert (  # noqa: S101 - fixed process boundary
        calls
        == [
            (
                [
                    str(node),
                    str(
                        POLICY_ENGINE_ROOT / "apps/runtime-dashboard/scripts/"
                        "run-ds18-time-semantics-outcome.mjs"
                    ),
                ],
                {
                    "cwd": POLICY_ENGINE_ROOT,
                    "check": False,
                    "stdin": subprocess.DEVNULL,
                    "capture_output": True,
                    "env": adapter.HEALTH_CHILD_ENV,
                },
            )
        ]
    )


def test_python_consumer_preserves_not_established_raw_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _load_adapter()
    outcome = {
        "kind": "not_established",
        "error_code": "checker_exit_nonzero",
        "exit_code": 1,
        "stdout_byte_count": 7,
        "stdout_sha256": "sha256:" + "1" * 64,
        "stderr_byte_count": 3,
        "stderr_sha256": "sha256:" + "2" * 64,
    }
    monkeypatch.setattr(
        adapter.subprocess,
        "run",
        lambda *_args, **_kwargs: _completed(json.dumps(outcome).encode("utf-8")),
    )

    admitted = adapter._ds18_time_semantics_coverage_projection(Path("/fixed/node"))

    assert admitted == outcome  # noqa: S101 - raw envelope is preserved
    assert adapter._ds18_outcome_limitation(admitted) == (  # noqa: S101
        "The DS18 execution outcome is not established (checker_exit_nonzero)."
    )


@pytest.mark.parametrize(
    "projection",
    [
        {
            "predicate_provenance": "independently_reconciled",
            "source_file_count": 5,
            "root_count": 12,
            "obligated_root_count": 13,
            "covered_root_count": 7,
        },
        {
            "predicate_provenance": "independently_reconciled",
            "source_file_count": 5,
            "root_count": 12,
            "obligated_root_count": 9,
            "covered_root_count": 10,
        },
    ],
)
def test_python_consumer_rejects_relationally_invalid_outcomes(
    monkeypatch: pytest.MonkeyPatch,
    projection: dict[str, object],
) -> None:
    adapter = _load_adapter()
    encoded = json.dumps({"kind": "established", "projection": projection}).encode()
    monkeypatch.setattr(
        adapter.subprocess,
        "run",
        lambda *_args, **_kwargs: _completed(encoded),
    )

    with pytest.raises(
        adapter.AtlasEvidencePersistenceError,
        match="typed DS18 execution outcome contract mismatch",
    ):
        adapter._ds18_time_semantics_coverage_projection(Path("/fixed/node"))


def test_python_consumer_rejects_duplicate_envelope_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _load_adapter()
    encoded = (
        b'{"kind":"not_established","kind":"not_established",'
        b'"error_code":"stdout_invalid_json","exit_code":0,'
        b'"stdout_byte_count":0,"stdout_sha256":"sha256:'
        + b"0" * 64
        + b'","stderr_byte_count":0,"stderr_sha256":"sha256:'
        + b"0" * 64
        + b'"}'
    )
    monkeypatch.setattr(
        adapter.subprocess,
        "run",
        lambda *_args, **_kwargs: _completed(encoded),
    )

    with pytest.raises(
        adapter.AtlasEvidencePersistenceError,
        match="typed DS18 execution outcome is not canonical UTF-8 JSON",
    ):
        adapter._ds18_time_semantics_coverage_projection(Path("/fixed/node"))


@pytest.mark.parametrize("encoded", [b"{", b"\xff"])
def test_python_consumer_rejects_malformed_utf8_json_envelopes(
    monkeypatch: pytest.MonkeyPatch,
    encoded: bytes,
) -> None:
    adapter = _load_adapter()
    monkeypatch.setattr(
        adapter.subprocess,
        "run",
        lambda *_args, **_kwargs: _completed(encoded),
    )

    with pytest.raises(
        adapter.AtlasEvidencePersistenceError,
        match="typed DS18 execution outcome is not canonical UTF-8 JSON",
    ):
        adapter._ds18_time_semantics_coverage_projection(Path("/fixed/node"))


def test_python_consumer_does_not_echo_runner_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _load_adapter()
    monkeypatch.setattr(
        adapter.subprocess,
        "run",
        lambda *_args, **_kwargs: _completed(b"", returncode=9, stderr="\ufeffsecret".encode()),
    )

    with pytest.raises(
        adapter.AtlasEvidencePersistenceError,
        match=r"typed DS18 execution-outcome runner failed \(9\)$",
    ) as raised:
        adapter._ds18_time_semantics_coverage_projection(Path("/fixed/node"))
    assert "secret" not in str(raised.value)  # noqa: S101 - raw stderr stays opaque
