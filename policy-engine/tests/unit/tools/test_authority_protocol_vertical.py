"""Exercise the real early host with the actual ArtifactReader Protocol."""

from __future__ import annotations

import _abc
import importlib
import importlib.machinery
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from types import CodeType

import pytest

_PRODUCT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("remove_execution_custody", [False, True], ids=["captured", "removal"])
def test_protocol_inside_host(
    request: pytest.FixtureRequest, remove_execution_custody: bool
) -> None:
    """Exercise canonical initialization and a same-name provider substitution."""
    mode = "removal" if remove_execution_custody else "captured"
    if not any(
        argument.endswith(f"::test_protocol_inside_host[{mode}]")
        for argument in request.config.invocation_params.args
    ):
        pytest.skip("fresh-host controls require explicit node selection")
    capture = sys.__dict__.get("_polisyos_loaded_execution_owner_v1")
    assert capture is not None, "early capture unavailable"
    name = "polisyos.core.artifacts.protocol"
    assert name not in sys.modules, "Protocol was loaded before the loader patch"
    recorder = sys.modules["_polisyos_loaded_source_capture"]
    diagnostic = capture.diagnostic()
    assert diagnostic.phase == "collecting", diagnostic.failure_code
    original_get_code = importlib.machinery.SourceFileLoader.get_code
    original_exec_module = recorder._CapturedSourceLoader.exec_module
    calls: list[str] = []

    def substituted_get_code(
        loader: importlib.machinery.SourceFileLoader, fullname: str
    ) -> CodeType | None:
        if fullname == name:
            calls.append(fullname)
            raise RuntimeError("PROTOCOL_LOADER_SUBSTITUTION_EXECUTED")
        return original_get_code(loader, fullname)

    importlib.machinery.SourceFileLoader.get_code = substituted_get_code
    if remove_execution_custody:
        recorder._CapturedSourceLoader.exec_module = (
            importlib.machinery.SourceFileLoader.exec_module
        )
    try:
        provider = importlib.import_module(name)
        facade = importlib.import_module("polisyos.core.artifacts")
    finally:
        importlib.machinery.SourceFileLoader.get_code = original_get_code
        recorder._CapturedSourceLoader.exec_module = original_exec_module
    assert not calls
    assert provider.ArtifactReader._is_protocol
    assert facade.ArtifactReader is provider.ArtifactReader
    assert capture.completed(name).module is provider
    event = next(
        event
        for event in capture.import_events()
        if event.provider_name == name
        and event.importer_name == "polisyos.core.artifacts"
        and "ArtifactReader" in event.retained_exports
    )

    class WarmedFileSystemCAS(facade.FileSystemCAS):
        pass

    before = _abc._get_dump(provider.ArtifactReader)[1]
    assert not any(reference() is WarmedFileSystemCAS for reference in before)
    assert issubclass(WarmedFileSystemCAS, provider.ArtifactReader)
    after = _abc._get_dump(provider.ArtifactReader)[1]
    assert any(reference() is WarmedFileSystemCAS for reference in after)
    assert facade.ArtifactReader is provider.ArtifactReader
    capture.assert_import_binding(
        event, importer_attribute="ArtifactReader", provider_export="ArtifactReader"
    )
    original = provider.ArtifactReader
    replacement = type("ArtifactReader", (), {})
    provider.ArtifactReader = replacement
    facade.ArtifactReader = replacement
    try:
        with pytest.raises(recorder.CaptureError, match=r"^retained_export_changed$"):
            capture.assert_import_binding(
                event, importer_attribute="ArtifactReader", provider_export="ArtifactReader"
            )
    finally:
        provider.ArtifactReader = original
        facade.ArtifactReader = original
    assert capture.failed and capture.failure_reason == "retained_export_changed"
    with pytest.raises(recorder.CaptureError):
        capture.assert_retained(frozenset({name}))


@pytest.mark.integration
def test_host_protocol_execution_and_removal() -> None:
    """Use fresh hosts with pytest's plain-assert profile for both controls."""
    host = sys.modules.get("_polisyos_early_host")
    product = Path(host.__file__).resolve().parents[1] if host is not None else _PRODUCT
    for mode in ("captured", "removal"):
        node = f"{__file__}::test_protocol_inside_host[{mode}]"
        print(f"START {node} at {datetime.now(UTC).isoformat()}", flush=True)
        started = time.monotonic()
        result = subprocess.run(
            [
                str(product / "tools/authority"),
                "test",
                "--noconftest",
                "--assert=plain",
                "-s",
                node,
            ],
            cwd=product,
            capture_output=True,
            text=True,
            check=False,
            timeout=240,
        )
        print(f"host protocol {mode} exit: {result.returncode}; {time.monotonic() - started:.3f}s")
        print(result.stdout, end="")
        print(result.stderr, end="")
        if mode == "captured":
            assert result.returncode == 0
            assert any(line.startswith("1 passed") for line in result.stdout.splitlines())
        else:
            assert result.returncode != 0
            assert any(
                line.lstrip().startswith("E")
                and "RuntimeError: PROTOCOL_LOADER_SUBSTITUTION_EXECUTED" in line
                for line in result.stdout.splitlines()
            )
