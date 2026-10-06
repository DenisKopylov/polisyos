"""Exercise the autotune facade with optional imports denied in a fresh process."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "module_name",
    ["polisyos.scientist.methods.autotune", "polisyos.scientist.methods.autotune.pareto"],
)
def test_contract_import_does_not_attempt_optional_execution_backends(module_name: str) -> None:
    script = """
import importlib.abc
import importlib
import json
import sys

attempts = []
class DeniedOptionalImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'torch', 'botorch', 'gpytorch', 'hnswlib'}:
            attempts.append(fullname)
            raise ModuleNotFoundError('declared optional-backend denial: ' + fullname, name=fullname)
        return None

sys.meta_path.insert(0, DeniedOptionalImports())
module = importlib.import_module(sys.argv[1])
print(json.dumps({'module': module.__name__, 'origin': module.__file__, 'attempts': attempts}))
"""
    process = subprocess.run(
        [sys.executable, "-c", script, module_name],
        check=False,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    observed = json.loads(process.stdout)
    assert observed["module"] == module_name
    assert observed["attempts"] == [], observed


def test_lazy_facade_resolves_existing_runtime_and_propagates_loader_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import polisyos.scientist.methods.autotune as facade

    monkeypatch.delattr(facade, "SearchLoopRunner", raising=False)
    runtime_runner = facade.SearchLoopRunner
    assert runtime_runner.__module__ == "polisyos.scientist.methods.autotune.runtime"
    assert "SearchLoopRunner" in facade.__all__
    monkeypatch.delattr(facade, "SearchLoopRunner")
    failure = RuntimeError("distinct optional runtime loader failure")

    def refuse_import(name: str) -> None:
        raise failure

    monkeypatch.setattr(facade.importlib, "import_module", refuse_import)
    with pytest.raises(RuntimeError) as raised:
        _ = facade.SearchLoopRunner
    assert raised.value is failure
