from __future__ import annotations

import ast
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tools.quality.validation import decomposition_preflight as preflight


def _scan_temporal_source(
    module: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    source_text: str | None = None,
) -> list[dict[str, Any]]:
    for scope in ("src", "tools", "apps", "packages"):
        (tmp_path / scope).mkdir(exist_ok=True)
    (tmp_path / "architecture/imports").mkdir(parents=True, exist_ok=True)
    package = tmp_path / "src/polisyos"
    package.mkdir(parents=True, exist_ok=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    consumer = package / "consumer.py"
    consumer.write_text(
        source_text
        or """import importlib

def load_hidden() -> None:
    importlib.import_module("polisyos.hidden")

load_hidden()
importlib = None
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "SRC_ROOT", tmp_path / "src")
    monkeypatch.setattr(
        module, "DYNAMIC_IMPORTS_PATH", tmp_path / "architecture/imports/dynamic.toml"
    )
    source_paths = module._dynamic_source_paths("src")
    source_context = module._dynamic_read_source_context(source_paths)
    source_bindings = module._DynamicImportSourceBindings(
        source_paths,
        source_context=source_context,
    )
    scanner = module._DynamicImportSourceScanner(
        consumer,
        relative_path="src/polisyos/consumer.py",
        source_bindings=source_bindings,
        source_context=source_context,
    )
    tree = ast.parse(consumer.read_text(encoding="utf-8"), filename=str(consumer))
    return scanner.scan(tree)


def test_module_call_uses_callsite_globals_before_late_rebinding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entries = _scan_temporal_source(preflight, tmp_path, monkeypatch)
    matches = [entry for entry in entries if entry["pattern"] == "polisyos.hidden"]
    assert len(matches) == 1
    assert matches[0]["source_file"] == "src/polisyos/consumer.py"
    assert matches[0]["line"] == 4


def test_module_call_binds_positional_keyword_and_definition_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases = (
        """import importlib

def load_hidden(module_name: str) -> None:
    importlib.import_module(module_name)

load_hidden("polisyos.hidden")
importlib = None
""",
        """import importlib

def load_hidden(module_name: str) -> None:
    importlib.import_module(module_name)

load_hidden(module_name="polisyos.hidden")
importlib = None
""",
        """import importlib

def load_hidden(module_name: str = "polisyos.hidden") -> None:
    importlib.import_module(module_name)

load_hidden()
importlib = None
""",
    )
    for index, source_text in enumerate(cases):
        case_path = tmp_path / str(index)
        case_path.mkdir()
        entries = _scan_temporal_source(
            preflight,
            case_path,
            monkeypatch,
            source_text=source_text,
        )
        assert [entry["pattern"] for entry in entries] == ["module_name"]
        assert entries[0]["allowed_targets"] == ["polisyos.hidden"]


def test_module_call_and_deferred_scan_emit_one_site_when_globals_stay_stable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_text = """import importlib

def load_hidden() -> None:
    importlib.import_module("polisyos.hidden")

load_hidden()
"""
    entries = _scan_temporal_source(preflight, tmp_path, monkeypatch, source_text=source_text)
    assert [entry["pattern"] for entry in entries] == ["polisyos.hidden"]


def test_module_call_after_rebinding_does_not_claim_an_import_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_text = """import importlib

def load_hidden() -> None:
    importlib.import_module("polisyos.hidden")

importlib = None
load_hidden()
"""
    entries = _scan_temporal_source(preflight, tmp_path, monkeypatch, source_text=source_text)
    assert entries == []


def test_module_time_call_transfers_globals_through_a_known_local_call_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_text = """import importlib

def import_hidden() -> None:
    importlib.import_module("polisyos.hidden")

def load_hidden() -> None:
    import_hidden()

load_hidden()
importlib = None
"""
    entries = _scan_temporal_source(preflight, tmp_path, monkeypatch, source_text=source_text)
    assert [entry["pattern"] for entry in entries] == ["polisyos.hidden"]


def test_module_time_call_with_joined_global_state_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_text = """import importlib

def load_hidden() -> None:
    importlib.import_module("polisyos.hidden")

if unknown_condition:
    importlib = None
load_hidden()
"""
    with pytest.raises(preflight.DynamicImportCollectionError):
        _scan_temporal_source(preflight, tmp_path, monkeypatch, source_text=source_text)


def test_callsite_transfer_removal_keeps_function_marker_and_reopens_regression(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert (
        preflight._DynamicImportBinding("source_function", origin_name="test.function").kind
        == "source_function"
    )

    def without_callsite_transfer(*args: object, **kwargs: object) -> None:
        del args, kwargs
        return None

    with monkeypatch.context() as patch:
        patch.setattr(
            preflight._DynamicImportSourceScanner,
            "_source_function_call",
            without_callsite_transfer,
        )
        with pytest.raises(preflight.DynamicImportCollectionError, match="inventory is incomplete"):
            _scan_temporal_source(preflight, tmp_path, patch)


@pytest.mark.parametrize(
    ("source_text", "expected"),
    [
        (
            'import importlib\nclass Loader:\n    def load(self):\n        importlib.import_module("polisyos.hidden")\nLoader().load()\nimportlib = None\n',
            "incomplete",
        ),
        (
            'import importlib\nclass Loader:\n    def load(self):\n        importlib.import_module("polisyos.hidden")\nimportlib = None\nLoader().load()\n',
            "incomplete",
        ),
        (
            'import importlib\nclass Loader:\n    def load(self):\n        importlib.import_module("polisyos.hidden")\nLoader().load()\n',
            "import",
        ),
        (
            'import importlib\ndef invoke(callback):\n    callback()\ninvoke(lambda: importlib.import_module("polisyos.hidden"))\nimportlib = None\n',
            "incomplete",
        ),
        (
            'import importlib\ndef eager(function):\n    function()\n@eager\ndef load_hidden():\n    importlib.import_module("polisyos.hidden")\nimportlib = None\n',
            "incomplete",
        ),
        (
            'import importlib\nclass Loader:\n    def __init__(self):\n        importlib.import_module("polisyos.hidden")\nLoader()\nimportlib = None\n',
            "incomplete",
        ),
    ],
)
def test_unmodeled_module_time_forms_use_the_same_guarded_temporal_rule(
    source_text: str,
    expected: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if expected == "incomplete":
        with pytest.raises(preflight.DynamicImportCollectionError, match="inventory is incomplete"):
            _scan_temporal_source(preflight, tmp_path, monkeypatch, source_text=source_text)
        return
    entries = _scan_temporal_source(preflight, tmp_path, monkeypatch, source_text=source_text)
    if expected == "import":
        assert [entry["pattern"] for entry in entries] == ["polisyos.hidden"]
    else:
        assert entries == []


def test_unmodeled_method_call_fails_closed_with_scanner_markers_present(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_text = """import importlib
class Loader:
    def load(self):
        importlib.import_module(\"polisyos.hidden\")
Loader().load()
importlib = None
"""
    assert hasattr(preflight._DynamicImportSourceScanner, "_source_function_call")
    assert hasattr(preflight._DynamicImportSourceScanner, "_record_call")
    with pytest.raises(preflight.DynamicImportCollectionError, match="inventory is incomplete"):
        _scan_temporal_source(preflight, tmp_path, monkeypatch, source_text=source_text)


def test_deferred_class_suite_uses_definition_time_importer_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert hasattr(preflight._DynamicImportSourceScanner, "_remember_unmodeled_temporal_invocation")
    assert hasattr(preflight._DynamicImportSourceScanner, "_scan_class")
    source_before_rebind = """import importlib
class Loader:
    target = importlib.import_module(\"polisyos.hidden\")
importlib = None
"""
    with pytest.raises(preflight.DynamicImportCollectionError, match="inventory is incomplete"):
        _scan_temporal_source(preflight, tmp_path, monkeypatch, source_text=source_before_rebind)


def test_deferred_class_suite_after_rebind_does_not_invent_an_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_after_rebind = """import importlib
importlib = None
class Loader:
    target = 0
"""
    entries = _scan_temporal_source(
        preflight, tmp_path, monkeypatch, source_text=source_after_rebind
    )
    assert entries == []


def test_deferred_class_suite_stable_importer_keeps_positive_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_stable = """import importlib
class Loader:
    target = importlib.import_module(\"polisyos.hidden\")
"""
    entries = _scan_temporal_source(preflight, tmp_path, monkeypatch, source_text=source_stable)
    assert [entry["pattern"] for entry in entries] == ["polisyos.hidden"]


def test_definition_time_scope_inside_module_function_is_checked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_text = """import importlib
def define_loader():
    class Loader:
        target = importlib.import_module(\"polisyos.hidden\")
define_loader()
importlib = None
"""
    with pytest.raises(preflight.DynamicImportCollectionError, match="inventory is incomplete"):
        _scan_temporal_source(preflight, tmp_path, monkeypatch, source_text=source_text)


def test_proven_importer_alias_rebinding_still_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_text = """from importlib import import_module as load
class Loader:
    def load(self):
        load("polisyos.hidden")
Loader().load()
load = None
"""
    with pytest.raises(preflight.DynamicImportCollectionError, match="inventory is incomplete"):
        _scan_temporal_source(preflight, tmp_path, monkeypatch, source_text=source_text)


def test_joined_importer_alias_keeps_temporal_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert callable(preflight._dynamic_importer_origins)
    assert callable(preflight._DynamicImportSourceScanner._raise_for_unproven_temporal_invocations)
    source_text = """import importlib
import pkgutil
import os
load = importlib.import_module if os.getenv(\"E02_TEMPORAL_PICK\") else pkgutil.iter_modules
class Loader:
    def load(self):
        load(\"polisyos.hidden\")
Loader().load()
load = None
"""
    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match="deferred source effects cross a proven importer rebind",
    ):
        _scan_temporal_source(preflight, tmp_path, monkeypatch, source_text=source_text)


def test_implicit_context_manager_effect_fails_closed_after_importer_rebind(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_text = """import importlib
class Meta(type):
    def __enter__(cls):
        return importlib.import_module(\"polisyos.hidden\")
class Loader(metaclass=Meta):
    pass
with Loader:
    pass
importlib = None
"""
    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match="deferred source effects cross a proven importer rebind",
    ):
        _scan_temporal_source(preflight, tmp_path, monkeypatch, source_text=source_text)
