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


def test_owner_snapshot_is_partial_sticky_and_never_establishes_deployment_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The owner retains reconciled evidence while unknown roles stay unresolved."""
    import sys
    import types

    class Capture:
        failed = False

        def __init__(self) -> None:
            self.diagnostic_calls = 0
            self.execution = types.SimpleNamespace(module=ledger)

        def diagnostic(self) -> object:
            self.diagnostic_calls += 1
            return types.SimpleNamespace(phase="collecting", failed_premise=None, failure_code=None)

        def assert_retained(self, required: frozenset[str]) -> None:
            assert required == frozenset({ledger.__name__})

        def completed(self, module_name: str) -> object:
            assert module_name == ledger.__name__
            return self.execution

        def relevant_graph(self, roots: frozenset[str]) -> object:
            assert roots == frozenset({ledger.__name__})
            return types.SimpleNamespace(
                reached_sources=(ledger.__name__,),
                external_providers=("external.provider",),
                failed_imports=(("polisyos.runtime.consumer", "missing.provider"),),
                failed_modules=(),
                unresolved_importers=(("polisyos.runtime.consumer", "runtime_lookup"),),
                pending_modules=(),
            )

        def import_events(self) -> tuple[object, ...]:
            return ()

    capture = Capture()
    recorder = types.ModuleType("candidate_recorder")
    monkeypatch.setattr(ledger, "_LOADED_EXECUTION_OBSERVATION_SEAL", None)
    monkeypatch.setattr(ledger, "_host_recorder_anchor_matches", lambda *_: True)
    monkeypatch.setitem(
        sys.__dict__,
        "_polisyos_loaded_host_v1",
        {"capture": capture, "recorder": recorder},
    )

    report = ledger._seal_loaded_execution_capture(recorder, capture)

    assert report["status"] == "not_established"
    assert report["protected_loaded_execution_status"] == "not_established"
    assert report["owner_observation_state"] == "retained"
    assert report["currentness_status"] == "not_established"
    assert report["held_binding_endpoint_currentness"] == "not_checked"
    assert report["external_provider_modules"] == ("external.provider",)
    assert report["failed_reachable_imports"] == (
        ("polisyos.runtime.consumer", "missing.provider"),
    )
    assert report["unresolved_importers"] == (("polisyos.runtime.consumer", "runtime_lookup"),)
    retained = ledger._LOADED_EXECUTION_OBSERVATION_SEAL
    assert retained is not None
    assert retained.capture is capture
    assert retained.owner_execution is capture.execution
    assert retained.binding_references == ()
    assert retained.external_provider_modules == ("external.provider",)
    assert retained.failed_reachable_imports == (("polisyos.runtime.consumer", "missing.provider"),)
    assert retained.unresolved_importers == (("polisyos.runtime.consumer", "runtime_lookup"),)

    repeated = ledger._seal_loaded_execution_capture(recorder, capture)
    assert repeated["owner_observation_state"] == "retained"
    assert repeated["status"] == "not_established"
    assert capture.diagnostic_calls == 1


def test_unmatched_owner_snapshot_cannot_poison_the_later_host_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A direct candidate call without the exact host slot leaves owner state free."""
    import sys
    import types

    monkeypatch.setattr(ledger, "_LOADED_EXECUTION_OBSERVATION_SEAL", None)
    monkeypatch.delitem(sys.__dict__, "_polisyos_loaded_host_v1", raising=False)
    recorder = types.ModuleType("candidate_recorder")
    capture = object()
    report = ledger._seal_loaded_execution_capture(recorder, capture)
    assert report["failure"] == "host_capture_session_unmatched"
    assert ledger._LOADED_EXECUTION_OBSERVATION_SEAL is None

    monkeypatch.setitem(
        sys.__dict__,
        "_polisyos_loaded_host_v1",
        {"capture": capture, "recorder": recorder},
    )
    monkeypatch.setattr(ledger, "_host_recorder_anchor_matches", lambda *_: False)
    failed = ledger._seal_loaded_execution_capture(recorder, capture)
    assert failed["owner_observation_state"] == "failed"
    assert ledger._LOADED_EXECUTION_OBSERVATION_SEAL is not None
    assert ledger._LOADED_EXECUTION_OBSERVATION_SEAL.state == "failed"

    monkeypatch.setattr(ledger, "_host_recorder_anchor_matches", lambda *_: True)
    retry = ledger._seal_loaded_execution_capture(recorder, capture)
    assert retry["owner_observation_state"] == "failed"
    assert retry["failure"] == "host_execution_anchor_unavailable"


def test_failed_owner_snapshot_keeps_partial_observations_without_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An incomplete reachable graph sticks as failed while retaining its diagnostics."""
    import sys
    import types

    capture = object()
    recorder = types.ModuleType("candidate_recorder")
    owner_execution = types.SimpleNamespace(module=ledger)

    def failed_observation(
        _recorder: object,
        _capture: object,
        *,
        _host_anchor_verified: bool,
        _retained_owner_executions: list[object],
        _retained_bindings: list[tuple[object, ...]],
    ) -> dict[str, object]:
        assert _host_anchor_verified is True
        _retained_owner_executions.append(owner_execution)
        _retained_bindings.append(("observed",))
        return {
            "status": "not_established",
            "protected_loaded_execution_status": "not_established",
            "failure": "reachable_graph_failed",
            "external_provider_modules": ("external.provider",),
            "failed_reachable_imports": (("owner", "missing.provider"),),
            "failed_reachable_modules": ("owner.missing",),
            "unresolved_importers": (("owner", "runtime_lookup"),),
            "pending_modules": (),
            "observed_binding_disagreements": (("provider", "value"),),
        }

    monkeypatch.setattr(ledger, "_LOADED_EXECUTION_OBSERVATION_SEAL", None)
    monkeypatch.setattr(ledger, "_host_recorder_anchor_matches", lambda *_: True)
    monkeypatch.setattr(ledger, "_observe_unsealed_host_capture", failed_observation)
    monkeypatch.setitem(
        sys.__dict__,
        "_polisyos_loaded_host_v1",
        {"capture": capture, "recorder": recorder},
    )

    report = ledger._seal_loaded_execution_capture(recorder, capture)

    assert report["owner_observation_state"] == "failed"
    assert report["status"] == report["protected_loaded_execution_status"] == "not_established"
    retained = ledger._LOADED_EXECUTION_OBSERVATION_SEAL
    assert retained is not None
    assert retained.state == "failed"
    assert retained.owner_execution is owner_execution
    assert retained.binding_references == (("observed",),)
    assert retained.external_provider_modules == ("external.provider",)
    assert retained.failed_reachable_imports == (("owner", "missing.provider"),)
    assert retained.unresolved_importers == (("owner", "runtime_lookup"),)
    assert retained.binding_disagreements == (("provider", "value"),)


def test_held_binding_endpoint_recheck_is_scoped_and_failure_sticks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The close-time check reuses held edges and cannot promote deployment status."""
    import sys
    import types

    provider_module = types.ModuleType("provider")
    importer_module = types.ModuleType("importer")
    provider = types.SimpleNamespace(module=provider_module)
    importer = types.SimpleNamespace(module=importer_module)
    event = types.SimpleNamespace(
        provider=provider_module,
        importer=importer_module,
        provider_name="provider",
        importer_name="importer",
    )
    value = object()
    calls: list[tuple[object, str, str]] = []
    owner_execution = types.SimpleNamespace(module=ledger)

    class Capture:
        def assert_retained(self, required: frozenset[str]) -> None:
            assert required == frozenset({ledger.__name__})

        def completed(self, module_name: str) -> object:
            return {
                ledger.__name__: owner_execution,
                "provider": provider,
                "importer": importer,
            }[module_name]

        def assert_import_binding(
            self, received: object, *, importer_attribute: str, provider_export: str
        ) -> None:
            calls.append((received, importer_attribute, provider_export))
            if len(calls) > 1:
                raise ValueError("import_event_binding_changed")

    capture = Capture()
    recorder = object()
    seal = ledger._LoadedExecutionObservationSeal(
        capture=capture,
        recorder_module=recorder,
        owner_module=ledger,
        state="retained",
        owner_execution=owner_execution,
        binding_references=((event, provider, importer, "Export", "Alias", value, value),),
        external_provider_modules=("external.provider",),
        failed_reachable_imports=(("consumer", "missing"),),
        failed_reachable_modules=(),
        unresolved_importers=(("consumer", "dynamic_lookup"),),
        pending_modules=(),
        binding_disagreements=(),
        failure=None,
    )
    monkeypatch.setattr(ledger, "_LOADED_EXECUTION_OBSERVATION_SEAL", seal)
    monkeypatch.setitem(
        sys.__dict__,
        "_polisyos_loaded_host_v1",
        {"capture": capture, "recorder": recorder},
    )
    monkeypatch.setattr(ledger, "_host_recorder_anchor_matches", lambda *_: True)

    first = ledger._check_loaded_execution_observation_currentness(capture)
    assert first["held_binding_endpoint_currentness"] == "current_at_endpoint"
    assert first["currentness_status"] == "not_established"
    assert first["protected_through_use"] == "not_established"
    assert calls == [(event, "Alias", "Export")]

    second = ledger._check_loaded_execution_observation_currentness(capture)
    assert second["owner_observation_state"] == "failed"
    assert second["held_binding_endpoint_currentness"] == "failed"
    assert second["held_binding_endpoint_failure"] == "import_event_binding_changed"
    assert ledger._LOADED_EXECUTION_OBSERVATION_SEAL is not None
    assert ledger._LOADED_EXECUTION_OBSERVATION_SEAL.state == "failed"

    # No reconciled owner-direct bindings means there is no denominator for a
    # positive endpoint currentness result.
    empty_seal = ledger._LoadedExecutionObservationSeal(
        capture=capture,
        recorder_module=recorder,
        owner_module=ledger,
        state="retained",
        owner_execution=owner_execution,
        binding_references=(),
        external_provider_modules=("external.provider",),
        failed_reachable_imports=(("consumer", "missing"),),
        failed_reachable_modules=(),
        unresolved_importers=(("consumer", "dynamic_lookup"),),
        pending_modules=(),
        binding_disagreements=(),
        failure=None,
    )
    monkeypatch.setattr(ledger, "_LOADED_EXECUTION_OBSERVATION_SEAL", empty_seal)
    no_direct_bindings = ledger._check_loaded_execution_observation_currentness(capture)
    assert no_direct_bindings["owner_observation_state"] == "retained"
    assert no_direct_bindings["held_binding_endpoint_currentness"] == "not_established"
    assert no_direct_bindings["held_binding_endpoint_checked_count"] == 0
    assert no_direct_bindings["held_binding_endpoint_reason"] == (
        "no_reconciled_owner_direct_bindings"
    )
    assert no_direct_bindings["currentness_status"] == "not_established"


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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
    closure = ledger._resolve_authority_import_closure(tmp_path, "polisyos.witness.consumer")
    assert set(diagnostic.source_candidates).issubset(set(closure))

    # This exact decorated provider is still outside the strict admitted route.
    # Candidate discovery does not change that fail-closed result.
    with pytest.raises(
        ledger.ConfidenceLedgerError,
        match="decorated direct source binding is unresolved",
    ):
        ledger._source_facade_runtime_projection(tmp_path, closure)

    # A separate supported source route demonstrates the actual consumer's
    # source/live binding check, independent of diagnostic discovery.
    import importlib.util
    import sys
    import types

    strict_root = tmp_path / "strict"
    _write_source(strict_root, "src/polisyos/__init__.py", "")
    _write_source(strict_root, "src/polisyos/strict_witness/__init__.py", "")
    _write_source(
        strict_root,
        "src/polisyos/strict_witness/provider.py",
        "class Capability:\n    def read(self) -> str:\n        return 'source-bound'\n",
    )
    _write_source(
        strict_root,
        "src/polisyos/strict_witness/facade.py",
        "from .provider import Capability as DeclaredCapability\nAlias = DeclaredCapability\n",
    )
    _write_source(
        strict_root,
        "src/polisyos/strict_witness/consumer.py",
        "from .facade import Alias\n",
    )
    strict_closure = ledger._resolve_authority_import_closure(
        strict_root, "polisyos.strict_witness.consumer"
    )
    witness_path = strict_root / "src/polisyos/strict_witness/__init__.py"
    package_spec = importlib.util.spec_from_file_location(
        "polisyos.strict_witness",
        witness_path,
        submodule_search_locations=[str(witness_path.parent)],
    )
    assert package_spec is not None and package_spec.loader is not None
    witness = importlib.util.module_from_spec(package_spec)
    monkeypatch.setitem(sys.modules, "polisyos.strict_witness", witness)
    monkeypatch.setattr(sys.modules["polisyos"], "strict_witness", witness, raising=False)
    package_spec.loader.exec_module(witness)

    def load_fixture_module(name: str, relative_path: str) -> types.ModuleType:
        source_path = strict_root / relative_path
        spec = importlib.util.spec_from_file_location(name, source_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        return module

    load_fixture_module(
        "polisyos.strict_witness.provider", "src/polisyos/strict_witness/provider.py"
    )
    facade = load_fixture_module(
        "polisyos.strict_witness.facade", "src/polisyos/strict_witness/facade.py"
    )
    consumer = load_fixture_module(
        "polisyos.strict_witness.consumer", "src/polisyos/strict_witness/consumer.py"
    )
    assert facade.Alias is consumer.Alias
    ledger._source_facade_runtime_projection(strict_root, strict_closure)

    monkeypatch.setattr(consumer, "Alias", object())
    with pytest.raises(
        ledger.ConfidenceLedgerError,
        match=r"cached source facade binding differs: polisyos\.strict_witness\.consumer\.Alias",
    ):
        ledger._source_facade_runtime_projection(strict_root, strict_closure)


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
    closure = ledger._resolve_authority_import_closure(tmp_path, "polisyos.witness.consumer")
    assert ("polisyos.witness.provider", "src/polisyos/witness/provider.py") in closure
    with pytest.raises(
        ledger.ConfidenceLedgerError, match="side-effecting direct source assignment"
    ):
        ledger._source_facade_runtime_projection(tmp_path, closure)
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
