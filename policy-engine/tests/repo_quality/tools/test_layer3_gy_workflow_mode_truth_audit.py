from __future__ import annotations

import builtins
import importlib
import sys
from types import ModuleType, SimpleNamespace

import pytest


def _audit_module():
    return importlib.import_module(
        "tools.quality.validation.check_layer3_gy_workflow_mode_truth_audit"
    )


def _workflow_import_stubs() -> dict[str, ModuleType]:
    entries = (
        (
            "polisyos.scientist.orchestration.workflows.policy_design",
            "policy_design_workflow_spec",
            "policy_design",
        ),
        (
            "polisyos.scientist.orchestration.workflows.causal_full",
            "causal_full_workflow_spec",
            "causal_full",
        ),
        (
            "polisyos.scientist.orchestration.workflows.policy_verified",
            "policy_verified_workflow_spec",
            "policy_verified",
        ),
    )
    modules: dict[str, ModuleType] = {}
    for module_name, function_name, alias in entries:
        module = ModuleType(module_name)

        def build_spec(*, _alias: str = alias) -> SimpleNamespace:
            return SimpleNamespace(
                nodes=[SimpleNamespace(alias=_alias, node_id=f"{_alias}-node")]
            )

        setattr(module, function_name, build_spec)
        modules[module_name] = module
    return modules


def _install_workflow_import_stubs(
    monkeypatch: pytest.MonkeyPatch,
    modules: dict[str, ModuleType],
) -> None:
    packages = (
        "polisyos",
        "polisyos.scientist",
        "polisyos.scientist.orchestration",
        "polisyos.scientist.orchestration.workflows",
    )
    parents: dict[str, ModuleType] = {}
    for package_name in packages:
        package = ModuleType(package_name)
        package.__path__ = []
        parents[package_name] = package
        monkeypatch.setitem(sys.modules, package_name, package)
        if "." in package_name:
            parent_name, child_name = package_name.rsplit(".", 1)
            setattr(parents[parent_name], child_name, package)
    for module_name, module in modules.items():
        monkeypatch.setitem(sys.modules, module_name, module)
        parent_name, child_name = module_name.rsplit(".", 1)
        setattr(parents[parent_name], child_name, module)


def test_live_specs_tolerates_only_direct_loguru_absence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit = _audit_module()
    monkeypatch.setattr(audit.sys, "path", list(audit.sys.path))
    modules = _workflow_import_stubs()
    _install_workflow_import_stubs(monkeypatch, modules)
    original_import = builtins.__import__

    def missing_loguru(name: str, *args: object, **kwargs: object) -> object:
        if name == "loguru":
            raise ModuleNotFoundError("No module named 'loguru'", name="loguru")
        if name in modules:
            return modules[name]
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_loguru)
    assert set(audit._live_specs()) == {"policy_design", "causal_full", "policy_verified"}


def test_live_specs_propagates_transitive_loguru_import_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit = _audit_module()
    monkeypatch.setattr(audit.sys, "path", list(audit.sys.path))
    original_import = builtins.__import__

    def missing_dependency(name: str, *args: object, **kwargs: object) -> object:
        if name == "loguru":
            raise ModuleNotFoundError("No module named 'logger_backend'", name="logger_backend")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_dependency)
    with pytest.raises(ModuleNotFoundError) as captured:
        audit._live_specs()
    assert captured.value.name == "logger_backend"


def test_live_spec_loading_propagates_logger_setup_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit = _audit_module()
    monkeypatch.setattr(audit.sys, "path", list(audit.sys.path))
    loguru = ModuleType("loguru")

    def fail_remove() -> None:
        raise RuntimeError("logger sink removal failed")

    loguru.logger = SimpleNamespace(remove=fail_remove)
    monkeypatch.setitem(sys.modules, "loguru", loguru)

    with pytest.raises(RuntimeError, match="logger sink removal failed"):
        audit._live_specs()
