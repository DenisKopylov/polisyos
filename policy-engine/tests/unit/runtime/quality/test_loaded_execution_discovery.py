"""Candidate-only source discovery must never stand in for loaded admission."""

from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.runtime.quality import confidence_ledger as ledger


def _write_source(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_fake_capture_is_refused_without_invoking_candidate_methods(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A matching type and process slot cannot authorize diagnostic callbacks."""
    import sys
    import types

    invoked: list[str] = []

    class CandidateCapture:
        def diagnostic(self) -> object:
            invoked.append("diagnostic")
            raise AssertionError("candidate callback ran")

    candidate = CandidateCapture()
    recorder = types.ModuleType("candidate_recorder")
    recorder.SourceExecutionCapture = CandidateCapture
    monkeypatch.setitem(sys.__dict__, "_polisyos_loaded_execution_owner_v1", candidate)
    result = ledger._observe_unsealed_host_capture(recorder, candidate)
    assert result["status"] == "not_established"
    assert result["failure"] == "host_execution_anchor_unavailable"
    assert invoked == []


@pytest.mark.parametrize("mutation", ["instance", "method_code", "helper_code", "class_method"])
def test_changed_recorder_callable_is_not_invoked_even_with_matching_code_anchors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    """A simulated host session refuses a changed recorder callable passively."""
    import hashlib
    import os
    import sys
    import types

    root = Path(__file__).resolve().parents[4]
    host_path = root / "tools/authority_bootstrap.py"
    recorder_path = root / "tools/loaded_execution_capture.py"
    host_source = host_path.read_bytes()
    recorder_source = recorder_path.read_bytes()
    host_code = compile(host_source, str(host_path), "exec", dont_inherit=True)
    recorder_code = compile(recorder_source, str(recorder_path), "exec", dont_inherit=True)
    host = types.ModuleType("_polisyos_early_host")
    recorder = types.ModuleType("_polisyos_loaded_source_capture")
    host.__file__ = str(host_path)
    recorder.__file__ = str(recorder_path)
    host._HOST_EXECUTION_CODE = host_code
    monkeypatch.setitem(sys.modules, host.__name__, host)
    monkeypatch.setitem(sys.modules, recorder.__name__, recorder)
    exec(host_code, host.__dict__)  # noqa: S102 - candidate-only source continuity fixture
    exec(recorder_code, recorder.__dict__)  # noqa: S102 - candidate-only source continuity fixture
    source = b"value = 1\n"
    capture = recorder.SourceExecutionCapture(
        tmp_path,
        {"candidate": recorder.ExpectedSource("candidate.py", hashlib.sha256(source).hexdigest())},
    )
    recorder_type, descriptors, globals_, functions, classes = host._retained_recorder_surface(
        recorder, recorder_code
    )
    session = {
        "pid": os.getpid(),
        "recorder": recorder,
        "capture": capture,
        "host_code": host_code,
        "recorder_code": recorder_code,
        "recorder_type": recorder_type,
        "recorder_descriptors": descriptors,
        "recorder_globals": globals_,
        "recorder_functions": functions,
        "recorder_classes": classes,
        "host_sha256": hashlib.sha256(host_source).hexdigest(),
        "recorder_sha256": hashlib.sha256(recorder_source).hexdigest(),
        "handoff": host.handoff_if_ready,
    }
    host._HOST_SESSION = session
    monkeypatch.setitem(sys.__dict__, "_polisyos_loaded_host_v1", session)
    monkeypatch.setitem(sys.__dict__, "_polisyos_loaded_execution_owner_v1", capture)
    assert ledger._host_recorder_anchor_matches(recorder, capture)
    invoked: list[str] = []
    if mutation == "instance":
        capture.__dict__["diagnostic"] = lambda: invoked.append("diagnostic")
    elif mutation == "method_code":
        monkeypatch.setattr(
            recorder.SourceExecutionCapture.completed,
            "__code__",
            recorder.SourceExecutionCapture._fail.__code__,
        )
    elif mutation == "helper_code":

        def forged_helper(mapping: object, key: object) -> object:
            raise AssertionError("changed helper ran")

        monkeypatch.setattr(recorder._passive_lookup, "__code__", forged_helper.__code__)
    else:

        def forged_init(self: object, *args: object, **kwargs: object) -> None:
            raise AssertionError("changed recorder class ran")

        monkeypatch.setattr(recorder.SourceCaptureDiagnostic, "__init__", forged_init)
    result = ledger._observe_unsealed_host_capture(recorder, capture)
    assert result["status"] == "not_established"
    assert result["failure"] == "host_execution_anchor_unavailable"
    assert invoked == []


def test_diagnostic_closure_tracks_unqualified_decorator_and_alias_without_admitting_them(
    tmp_path: Path,
) -> None:
    _write_source(tmp_path, "src/polisyos/__init__.py", "")
    _write_source(tmp_path, "src/polisyos/witness/__init__.py", "")
    _write_source(
        tmp_path,
        "src/polisyos/witness/provider.py",
        "from typing import Protocol, runtime_checkable\n"
        "@runtime_checkable\n"
        "class Capability(Protocol):\n"
        "    def read(self) -> str: ...\n",
    )
    _write_source(
        tmp_path,
        "src/polisyos/witness/facade.py",
        "from .provider import Capability as DeclaredCapability\nAlias = DeclaredCapability\n",
    )
    _write_source(
        tmp_path,
        "src/polisyos/witness/consumer.py",
        "from .facade import Alias\n",
    )
    diagnostic = ledger._diagnose_unqualified_authority_import_candidates(
        tmp_path,
        "polisyos.witness.consumer",
    )
    assert (
        "polisyos.witness.provider",
        "src/polisyos/witness/provider.py",
    ) in diagnostic.source_candidates
    assert (
        "polisyos.witness.facade",
        "src/polisyos/witness/facade.py",
    ) in diagnostic.source_candidates
    assert {
        ("polisyos.witness.provider", "Capability"),
        ("polisyos.witness.facade", "Alias"),
    }.issubset(diagnostic.unqualified_direct_bindings)
    assert "actual_source_execution_and_selected_provider" in diagnostic.unresolved_by_construction

    # The diagnostic's candidates do not qualify either binding as an actual
    # executed provider. The original strict path still refuses this fixture.
    with pytest.raises(ledger.ConfidenceLedgerError, match="unresolved"):
        ledger._resolve_authority_import_closure(tmp_path, "polisyos.witness.consumer")


def test_unqualified_side_effecting_export_is_only_a_diagnostic_candidate(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "factory-executed"
    _write_source(tmp_path, "src/polisyos/__init__.py", "")
    _write_source(tmp_path, "src/polisyos/witness/__init__.py", "")
    _write_source(
        tmp_path,
        "src/polisyos/witness/provider.py",
        "from pathlib import Path\n"
        "def replacement_factory():\n"
        f"    Path({str(marker)!r}).write_text('executed')\n"
        "    return object()\n"
        "Export = replacement_factory()\n",
    )
    _write_source(
        tmp_path,
        "src/polisyos/witness/consumer.py",
        "from .provider import Export\n",
    )
    diagnostic = ledger._diagnose_unqualified_authority_import_candidates(
        tmp_path,
        "polisyos.witness.consumer",
    )
    assert ("polisyos.witness.provider", "Export") in diagnostic.unqualified_direct_bindings
    assert (
        "polisyos.witness.provider",
        "src/polisyos/witness/provider.py",
    ) in diagnostic.source_candidates
    with pytest.raises(ledger.ConfidenceLedgerError, match="side-effecting direct source"):
        ledger._resolve_authority_import_closure(tmp_path, "polisyos.witness.consumer")
    assert not marker.exists()


def test_observed_alias_is_resolved_by_real_owner_and_spoof_refused(tmp_path: Path) -> None:
    """The owner's alias reconciliation rejects a changed candidate binding.

    The owner is imported before this candidate-only fixture starts collecting;
    this test does not claim it was loaded by the early host.
    """
    import subprocess
    import sys

    product = Path(__file__).resolve().parents[4]
    program = r"""
import hashlib
import importlib
import os
import pathlib
import sys
product = pathlib.Path(sys.argv[1])
root = pathlib.Path(sys.argv[2])
sys.path[:0] = [str(product), str(product / "src"), str(product / ".venv/lib/python3.14/site-packages")]
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
initial_meta_path = tuple(sys.meta_path)
from polisyos.runtime.quality import confidence_ledger as owner
# This unit fixture tests only the owner's alias helper, not early startup.
# Its separate synthetic package is collected after restoring the test
# process's original hooks; no authority can be established by this capture.
sys.meta_path[:] = initial_meta_path
package = root / "alias_witness"
package.mkdir()
files = {
    "alias_witness": ("alias_witness/__init__.py", b""),
    "alias_witness.provider": ("alias_witness/provider.py", b"class Capability:\n    pass\n"),
    "alias_witness.consumer": ("alias_witness/consumer.py", b"from .provider import Capability as RenamedCapability\n"),
}
for relative, source in files.values():
    (root / relative).write_bytes(source)
capture_root = pathlib.Path(os.path.commonpath((product, root))).resolve()
sources = {}
for name, (relative, source) in files.items():
    sources[name] = ExpectedSource(
        (root / relative).relative_to(capture_root).as_posix(), hashlib.sha256(source).hexdigest()
    )
# The test-selected mapping is candidate evidence only, not an appointed host profile.
capture = SourceExecutionCapture(
    capture_root,
    sources,
    exports={"alias_witness.provider": {"Capability"}},
)
capture.install()
sys.path.insert(0, str(root))
consumer = importlib.import_module("alias_witness.consumer")
events = [event for event in capture.import_events() if event.importer_name == "alias_witness.consumer" and event.provider_name == "alias_witness.provider"]
assert len(events) == 1
assert owner._source_import_aliases_for_event(capture_root, capture, events[0], "Capability") == ("RenamedCapability",)
assert capture.diagnostic().status == "not_established"
capture.assert_import_binding(events[0], importer_attribute="RenamedCapability", provider_export="Capability")
consumer.RenamedCapability = type("Capability", (), {})
try:
    capture.assert_import_binding(events[0], importer_attribute="RenamedCapability", provider_export="Capability")
except CaptureError as exc:
    assert str(exc) == "import_event_binding_changed"
else:
    raise AssertionError("same-name aliased consumer replacement was accepted")
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", program, str(product), str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
