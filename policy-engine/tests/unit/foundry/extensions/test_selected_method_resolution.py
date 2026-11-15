"""Exact selected-method consumers bootstrap only the governed builtin source."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_PRODUCT_ROOT = Path(__file__).resolve().parents[4]


def _method(version: str):
    from polisyos.foundry.methods import (
        ComplexityClass,
        ComputeBackend,
        FidelityLevel,
        MethodMetadata,
        MethodSignature,
    )

    class Method:
        metadata = MethodMetadata(description="Explicit test-owned method")

        @staticmethod
        def pure_step(state, params):
            return {"version": version}

    Method.signature = MethodSignature(
        name="selected",
        namespace="fixture.exact",
        version=version,
        input_slots=frozenset(),
        output_slots=frozenset(),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    return Method


def test_exact_builtin_consumer_bootstraps_in_a_fresh_process(tmp_path: Path) -> None:
    """A cold installed-source consumer resolves the catalog without fixture registration."""
    probe = r"""
import atexit
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

root = Path.cwd().resolve()
source = root / "src/polisyos"
output = Path(os.environ["SELECTED_METHOD_COLD_OUTPUT"])
spec = importlib.util.find_spec("polisyos")
assert spec is not None
assert {Path(path).resolve() for path in spec.submodule_search_locations or ()} == {source}
preimage = {
    str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in source.rglob("*.py") if path.is_file()
}
def source_readback():
    imported, foreign, changed = {}, [], []
    for name, module in tuple(sys.modules.items()):
        if name != "polisyos" and not name.startswith("polisyos."):
            continue
        origin = getattr(module, "__file__", None)
        if origin is None:
            continue
        path = Path(origin).resolve()
        if not path.is_relative_to(source):
            foreign.append([name, str(path)])
            continue
        if path.suffix != ".py":
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        imported[str(path.relative_to(root))] = digest
        if preimage.get(str(path)) != digest:
            changed.append(str(path.relative_to(root)))
    record = {"imported_first_party_files": len(imported),
              "foreign_origins": foreign, "changed_pins": changed}
    (output / "cold-process.imported-source-pins.json").write_text(
        json.dumps(imported, sort_keys=True, indent=2) + "\n"
    )
    (output / "cold-process.source-readback.json").write_text(
        json.dumps(record, sort_keys=True, indent=2) + "\n"
    )
    print("cold-process-source-readback:", json.dumps(record, sort_keys=True), flush=True)
atexit.register(source_readback)

from polisyos.foundry.methods import (
    MethodRegistry, resolve_selected_method, resolve_selected_method_entry,
)
from polisyos.foundry.methods.exceptions import MethodNotFoundError

registry = MethodRegistry.get_instance()
before = {entry.fqn for entry in registry.snapshot().entries()}
fqn = "policy.accounting.period_flow_to_stock@1.0.0"
assert fqn not in before
assert "polisyos.foundry.methods.catalog.policy.accounting" not in __import__("sys").modules
method = resolve_selected_method("policy.accounting.period_flow_to_stock", version="1.0.0")
assert method.signature.fqn == fqn
assert {entry.fqn for entry in registry.snapshot().entries()} == before | {fqn}
assert resolve_selected_method(fqn, version="1.0.0") is method
assert resolve_selected_method_entry(fqn).signature is method.signature
for name in ("policy.accounting.period_flow_to_stock@9.0.0", "unknown.reader@1.0.0"):
    try:
        resolve_selected_method(name)
    except MethodNotFoundError:
        pass
    else:
        raise AssertionError("unknown exact method/version was silently replaced")
assert {entry.fqn for entry in registry.snapshot().entries()} == before | {fqn}
print(json.dumps({"probe":"selected_method_cold_probe_pass", "selected":fqn,
                  "added":sorted({entry.fqn for entry in registry.snapshot().entries()} - before)}))
"""
    environment = {
        **os.environ,
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(_PRODUCT_ROOT / "src"),
        "FOUNDRY_SHAPE_CHECK": "0",
        "SELECTED_METHOD_COLD_OUTPUT": str(tmp_path),
    }
    # Fixed source-owned probe, current interpreter, no shell or provider call.
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-B", "-c", probe],
        cwd=_PRODUCT_ROOT,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
        timeout=120,
    )
    (tmp_path / "cold-process.stdout").write_text(completed.stdout)
    (tmp_path / "cold-process.stderr").write_text(completed.stderr)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "selected_method_cold_probe_pass" in completed.stdout
    import json

    readback = json.loads((tmp_path / "cold-process.source-readback.json").read_text())
    assert readback["imported_first_party_files"] > 0
    assert readback["foreign_origins"] == []
    assert readback["changed_pins"] == []


def test_custom_registry_is_exact_and_lookup_only(monkeypatch: pytest.MonkeyPatch) -> None:
    from polisyos.foundry.extensions import discovery
    from polisyos.foundry.methods import MethodRegistry, registry_scope, resolve_selected_method
    from polisyos.foundry.methods.exceptions import MethodNotFoundError

    def no_discovery(**kwargs):
        raise AssertionError("custom registry must not discover another catalog")

    monkeypatch.setattr(discovery, "build_foundry_method_components_index", no_discovery)
    default_registry = MethodRegistry.get_instance()
    default_before = tuple(default_registry.snapshot().entries())
    with registry_scope() as registry:
        older, newer = _method("1.0.0"), _method("2.0.0")
        registry.register(older)
        registry.register(newer)
        before = tuple(registry.list_all())
        assert resolve_selected_method("fixture.exact.selected", version="1.0.0") is older
        assert resolve_selected_method("fixture.exact.selected@2.0.0") is newer
        with pytest.raises(MethodNotFoundError):
            resolve_selected_method("fixture.exact.selected@3.0.0", registry=registry)
        with pytest.raises(MethodNotFoundError):
            resolve_selected_method("policy.accounting.period_flow_to_stock@1.0.0")
        assert tuple(registry.list_all()) == before
    assert tuple(default_registry.snapshot().entries()) == default_before


def test_selected_consumer_preserves_canonical_bootstrap_lock_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from threading import Event, Thread

    from polisyos.foundry.extensions import discovery
    from polisyos.foundry.methods import MethodRegistry, registry_scope, resolve_selected_method
    from polisyos.foundry.methods.components.bridge import _BOOTSTRAP_LOCK

    registry = MethodRegistry._create_fresh()
    monkeypatch.setattr(MethodRegistry, "_instance", registry)
    with registry_scope():
        index, report = discovery.build_foundry_method_components_index(
            include_builtins=True, include_entry_points=False, include_dev_scan=False
        )
    assert report.manifest is not None and report.manifest.is_bound and not report.errors
    discovered = Event()
    failures = []

    def selected_discovery(**kwargs):
        discovered.set()
        return index, report

    def resolve():
        try:
            resolve_selected_method("policy.accounting.period_flow_to_stock@1.0.0")
        except BaseException as exc:
            failures.append(exc)

    monkeypatch.setattr(discovery, "build_foundry_method_components_index", selected_discovery)
    worker = Thread(target=resolve, daemon=True)
    # A canonical bootstrap already owning its admission lock must still be
    # able to acquire the destination lock while a selected consumer is cold.
    with _BOOTSTRAP_LOCK:
        worker.start()
        assert discovered.wait(5)
        destination_available = registry._reg_lock.acquire(timeout=1)
        if destination_available:
            registry._reg_lock.release()
    worker.join(timeout=10)
    assert not worker.is_alive()
    assert failures == []
    assert destination_available
    assert {signature.fqn for signature in registry.list_all()} == {
        "policy.accounting.period_flow_to_stock@1.0.0"
    }


def test_concurrent_cold_consumers_preserve_each_selected_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from threading import Barrier, Event, Thread, current_thread

    from polisyos.foundry.extensions import discovery
    from polisyos.foundry.methods import MethodRegistry, registry_scope, resolve_selected_method

    registry = MethodRegistry._create_fresh()
    monkeypatch.setattr(MethodRegistry, "_instance", registry)
    with registry_scope():
        index, report = discovery.build_foundry_method_components_index(
            include_builtins=True, include_entry_points=False, include_dev_scan=False
        )
    assert report.manifest is not None and report.manifest.is_bound and not report.errors
    selected = (
        "policy.accounting.period_flow_to_stock@1.0.0",
        "policy.evaluation.ex_ante_simulation@1.0.0",
    )
    assert all(index.get(fqn) is not None for fqn in selected)
    discovered = Barrier(2, timeout=5)
    first_finished = Event()
    failures = []

    def selected_discovery(**kwargs):
        discovered.wait()
        if current_thread().name == "second-selected-consumer":
            assert first_finished.wait(5)
        return index, report

    def resolve(fqn, *, first=False):
        try:
            assert resolve_selected_method(fqn).signature.fqn == fqn
        except BaseException as exc:
            failures.append(exc)
        finally:
            if first:
                first_finished.set()

    monkeypatch.setattr(discovery, "build_foundry_method_components_index", selected_discovery)
    first = Thread(target=resolve, args=(selected[0],), kwargs={"first": True}, daemon=True)
    second = Thread(
        target=resolve, args=(selected[1],), name="second-selected-consumer", daemon=True
    )
    first.start()
    second.start()
    first.join(timeout=10)
    second.join(timeout=10)
    assert not first.is_alive() and not second.is_alive()
    assert failures == []
    assert {signature.fqn for signature in registry.list_all()} == set(selected)


@pytest.mark.parametrize(
    ("name", "version", "code"),
    (
        ("policy.accounting.period_flow_to_stock", None, "selected_method_version_missing"),
        (
            "policy.accounting.period_flow_to_stock@1.0.0",
            "9.0.0",
            "selected_method_version_conflict",
        ),
    ),
)
def test_incomplete_or_conflicting_selection_refuses_before_discovery(
    monkeypatch: pytest.MonkeyPatch, name: str, version: str | None, code: str
) -> None:
    from polisyos.foundry.extensions import discovery
    from polisyos.foundry.methods import registry_scope, resolve_selected_method

    def no_discovery(**kwargs):
        raise AssertionError("invalid selection must not discover a catalog")

    monkeypatch.setattr(discovery, "build_foundry_method_components_index", no_discovery)
    with registry_scope() as registry:
        with pytest.raises(ValueError, match=code):
            resolve_selected_method(name, version=version)
        assert registry.list_all() == []


def test_missing_declared_builtin_target_refuses_without_registry_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.core.components import DeclaredBuiltinLoader
    from polisyos.foundry.extensions import discovery
    from polisyos.foundry.extensions.registry import UnboundFoundryDiscoveryInputError
    from polisyos.foundry.methods import MethodRegistry, resolve_selected_method

    registry = MethodRegistry._create_fresh()
    monkeypatch.setattr(MethodRegistry, "_instance", registry)
    monkeypatch.setattr(
        discovery,
        "BUILTIN_LOADER",
        DeclaredBuiltinLoader(
            target="missing_selected_builtin_source:components", group=discovery.ENTRY_POINT_GROUP
        ),
    )
    with pytest.raises(UnboundFoundryDiscoveryInputError):
        resolve_selected_method("policy.accounting.period_flow_to_stock@1.0.0")
    assert registry.list_all() == []
