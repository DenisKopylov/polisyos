from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tools.quality.validation import decomposition_preflight as preflight


def _candidate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, layout_value: str) -> None:
    for scope in ("src", "tools", "apps", "packages"):
        (tmp_path / scope).mkdir()
    (tmp_path / "architecture/imports").mkdir(parents=True)
    source_root = tmp_path / "src"
    package = source_root / "polisyos"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "layout.py").write_text(
        """from pathlib import Path

class CASPathLayout:
    def __init__(self, root: Path) -> None:
        self.base = root / "artifacts" / "sha256"

    def sig_path(self, artifact_id: str) -> Path:
        return self.base / artifact_id[:2] / f"{artifact_id}.sig"
""",
        encoding="utf-8",
    )
    (package / "store.py").write_text(
        f"""from pathlib import Path
from .layout import CASPathLayout

class FileSystemCAS:
    def __init__(self, root: Path) -> None:
        self._layout = {layout_value}

    def _sig_path(self, artifact_id: str) -> Path:
        return self._layout.sig_path(artifact_id)
""",
        encoding="utf-8",
    )
    (package / "target.py").write_text("TARGET = 'present'\n", encoding="utf-8")
    (package / "consumer.py").write_text(
        """from importlib import import_module
from pathlib import Path
from .store import FileSystemCAS

store = FileSystemCAS(Path("/tmp/cas"))
signature_path = store._sig_path("ab" * 32)
mode = signature_path.stat().st_mode
import_module("polisyos.target")
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(preflight, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(preflight, "SRC_ROOT", source_root)
    monkeypatch.setattr(
        preflight,
        "DYNAMIC_IMPORTS_PATH",
        tmp_path / "architecture/imports/dynamic.toml",
    )


def _scan_consumer(tmp_path: Path) -> list[dict[str, object]]:
    source_paths = preflight._dynamic_source_paths("src")
    source_context = preflight._dynamic_read_source_context(source_paths)
    source_bindings = preflight._DynamicImportSourceBindings(
        source_paths,
        source_context=source_context,
    )
    consumer = tmp_path / "src/polisyos/consumer.py"
    scanner = preflight._DynamicImportSourceScanner(
        consumer,
        relative_path="src/polisyos/consumer.py",
        source_bindings=source_bindings,
        source_context=source_context,
    )
    return scanner.scan(ast.parse(consumer.read_text(encoding="utf-8"), filename=str(consumer)))


def test_nested_source_receiver_path_return_is_resolved_by_source_scanner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _candidate(tmp_path, monkeypatch, layout_value="CASPathLayout(root)")

    entries = _scan_consumer(tmp_path)

    assert [(entry["call"], entry["pattern"]) for entry in entries] == [
        ("importlib.import_module", "polisyos.target")
    ]


def test_nested_source_receiver_unknown_field_stays_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _candidate(tmp_path, monkeypatch, layout_value="unknown_layout_factory()")

    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match="dynamic importer binding is ambiguous or unresolved",
    ):
        _scan_consumer(tmp_path)


def test_nested_source_receiver_removal_control_keeps_markers_but_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _candidate(tmp_path, monkeypatch, layout_value="CASPathLayout(root)")
    store_path = tmp_path / "src/polisyos/store.py"
    before = store_path.read_text(encoding="utf-8")
    assert "self._layout = CASPathLayout(root)" in before
    assert "def _sig_path(self, artifact_id: str) -> Path:" in before
    assert _scan_consumer(tmp_path)

    store_path.write_text(
        before.replace("self._layout = CASPathLayout(root)", "self._layout = object()", 1),
        encoding="utf-8",
    )
    after = store_path.read_text(encoding="utf-8")
    assert "self._layout = object()" in after
    assert "def _sig_path(self, artifact_id: str) -> Path:" in after
    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match="dynamic importer binding is ambiguous or unresolved",
    ):
        _scan_consumer(tmp_path)


def test_actual_core_cas_layout_and_artifact_id_prove_nested_path_receiver() -> None:
    repo = Path(preflight.REPO_ROOT)
    source_paths = [
        repo / "src/polisyos/__init__.py",
        repo / "src/polisyos/core/__init__.py",
        repo / "src/polisyos/core/artifacts/__init__.py",
        repo / "src/polisyos/core/artifacts/ids.py",
        repo / "src/polisyos/core/artifacts/store.py",
        repo / "src/polisyos/core/artifacts/_layout.py",
    ]
    source_context = preflight._dynamic_read_source_context(source_paths)
    source_bindings = preflight._DynamicImportSourceBindings(
        source_paths,
        source_context=source_context,
    )
    consumer = repo / "apps/runtime-dashboard/e2e/fixtures/serve_public_verification_api.py"
    source = """from importlib import import_module
from pathlib import Path
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS

store = FileSystemCAS(Path("/tmp/cas"))
record_ref = ArtifactID.model_validate("sha256:" + "a" * 64)
signature_path = store._sig_path(record_ref)
mode = signature_path.stat().st_mode
import_module("polisyos.core.artifacts.ids")
"""
    scanner = preflight._DynamicImportSourceScanner(
        consumer,
        relative_path="apps/runtime-dashboard/e2e/fixtures/serve_public_verification_api.py",
        source_bindings=source_bindings,
        source_context=source_context,
    )

    entries = scanner.scan(ast.parse(source, filename=str(consumer)))

    assert [(entry["call"], entry["pattern"]) for entry in entries] == [
        ("importlib.import_module", "polisyos.core.artifacts.ids")
    ]


def test_root_model_after_validator_cannot_be_assumed_to_preserve_string_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _candidate(tmp_path, monkeypatch, layout_value="CASPathLayout(root)")
    (tmp_path / "src/polisyos/ids.py").write_text(
        """from importlib import import_module
from pydantic import RootModel, field_validator

class ArtifactID(RootModel[str]):
    @field_validator("root", mode="after")
    @classmethod
    def replace_root(cls, value: str) -> str:
        return import_module
""",
        encoding="utf-8",
    )
    consumer = tmp_path / "src/polisyos/consumer.py"
    consumer.write_text(
        """from polisyos.ids import ArtifactID

identifier = ArtifactID.model_validate("sha256:" + "a" * 64).root
identifier("polisyos.hidden")
""",
        encoding="utf-8",
    )

    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match="dynamic importer binding is ambiguous or unresolved",
    ):
        _scan_consumer(tmp_path)


def test_public_collector_resolves_nested_source_receiver_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _candidate(tmp_path, monkeypatch, layout_value="CASPathLayout(root)")

    entries = preflight.collect_dynamic_imports()

    assert [(entry["call"], entry["pattern"]) for entry in entries] == [
        ("importlib.import_module", "polisyos.target")
    ]


def test_public_collector_rejects_unknown_nested_receiver_factory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _candidate(tmp_path, monkeypatch, layout_value="unknown_layout_factory()")

    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match="dynamic importer binding is ambiguous or unresolved",
    ):
        preflight.collect_dynamic_imports()


def test_public_collector_removal_of_nested_receiver_field_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _candidate(tmp_path, monkeypatch, layout_value="object()")

    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match="dynamic importer binding is ambiguous or unresolved",
    ):
        preflight.collect_dynamic_imports()


def test_public_collector_does_not_treat_unknown_source_operators_as_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _candidate(tmp_path, monkeypatch, layout_value="CASPathLayout(root)")
    (tmp_path / "src/polisyos/layout.py").write_text(
        """from pathlib import Path

class OpaqueOperatorValue:
    def __getitem__(self, key: object) -> str:
        return "safe-looking"

    def __truediv__(self, other: object) -> str:
        return "safe-looking"

class CASPathLayout:
    def __init__(self, root: Path) -> None:
        self.base = OpaqueOperatorValue()

    def sig_path(self, artifact_id: str) -> Path:
        return self.base[artifact_id[:2]] / f"{artifact_id}.sig"
""",
        encoding="utf-8",
    )

    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match="guarded importer value escapes through a function return",
    ):
        preflight.collect_dynamic_imports()


def _binding_from_expression(scanner, expression: str, environment):
    node = ast.parse(expression, mode="eval").body
    return scanner._expression_binding(
        node,
        environment,
        [],
        {"globals": set(), "nonlocals": set()},
    )


def test_sequence_concatenation_preserves_unknown_and_importer_members() -> None:
    source = Path(preflight.REPO_ROOT) / "src/polisyos/core/__init__.py"
    scanner = preflight._DynamicImportSourceScanner(
        source,
        relative_path="src/polisyos/core/__init__.py",
    )
    unknown = preflight._DYNAMIC_UNKNOWN
    importer = preflight._DynamicImportBinding("callable", "importlib.import_module", guarded=True)
    left = preflight._dynamic_sequence_binding(
        (preflight._dynamic_string_binding("known"), unknown, importer),
        sequence_type="list",
    )
    right = preflight._dynamic_sequence_binding(
        (preflight._dynamic_string_binding("tail"),),
        sequence_type="list",
    )

    result = _binding_from_expression(scanner, "left + right", {"left": left, "right": right})

    assert result.kind == "sequence"
    assert result.items == (*left.items, *right.items)
    assert result.guarded
    assert result.items[1].kind == "unknown"
    assert result.items[2] == importer
    assert result.sequence_type == "list"
    assert not preflight._dynamic_binding_is_proven_nonimporter(result)


def test_sequence_concatenation_keeps_unknown_shape_and_custom_operands_unresolved() -> None:
    source = Path(preflight.REPO_ROOT) / "src/polisyos/core/__init__.py"
    scanner = preflight._DynamicImportSourceScanner(
        source,
        relative_path="src/polisyos/core/__init__.py",
    )
    sequence = preflight._dynamic_sequence_binding(
        (preflight._dynamic_string_binding("known"),),
        sequence_type="list",
    )
    unknown = _binding_from_expression(
        scanner,
        "left + right",
        {"left": preflight._DYNAMIC_UNKNOWN, "right": sequence},
    )
    custom = _binding_from_expression(
        scanner,
        "left + right",
        {
            "left": preflight._DynamicImportBinding("object", "user.Custom"),
            "right": sequence,
        },
    )
    tuple_sequence = preflight._dynamic_sequence_binding(
        (preflight._dynamic_string_binding("tail"),),
        sequence_type="tuple",
    )
    tuple_join = _binding_from_expression(
        scanner,
        "left + right",
        {"left": tuple_sequence, "right": tuple_sequence},
    )
    mismatched_types = _binding_from_expression(
        scanner,
        "left + right",
        {"left": sequence, "right": tuple_sequence},
    )
    unknown_shape = _binding_from_expression(
        scanner,
        "left + right",
        {
            "left": preflight._dynamic_sequence_binding(None, sequence_type="list"),
            "right": sequence,
        },
    )
    oversized = _binding_from_expression(
        scanner,
        "left + right",
        {
            "left": preflight._dynamic_sequence_binding(
                tuple(
                    preflight._dynamic_string_binding("item")
                    for _ in range(preflight._DYNAMIC_COMPREHENSION_VALUE_LIMIT)
                ),
                sequence_type="list",
            ),
            "right": sequence,
        },
    )

    assert unknown.kind in {"unknown", "ambiguous"}
    assert not preflight._dynamic_binding_is_proven_nonimporter(unknown)
    assert custom.kind == "ambiguous"
    assert mismatched_types.kind == "ambiguous"
    assert tuple_join.sequence_type == "tuple"
    assert tuple_join.items == (*tuple_sequence.items, *tuple_sequence.items)
    assert unknown_shape.kind == "unknown"
    assert not preflight._dynamic_binding_is_proven_nonimporter(unknown_shape)
    assert oversized.kind == "unknown"


def test_actual_core_package_dir_source_scan_composes_known_sequences() -> None:
    repository = Path(preflight.REPO_ROOT)
    selected_sources = (
        "src/polisyos/__init__.py",
        "src/polisyos/core/__init__.py",
        "src/polisyos/core/artifacts/__init__.py",
        "src/polisyos/core/artifacts/ids.py",
        "src/polisyos/core/artifacts/store.py",
        "src/polisyos/core/artifacts/_layout.py",
    )
    source_paths = tuple(repository / relative for relative in selected_sources)
    source_context = preflight._dynamic_read_source_context(source_paths)
    source_bindings = preflight._DynamicImportSourceBindings(
        source_paths,
        source_context=source_context,
    )
    source = repository / "src/polisyos/core/__init__.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    scanner = preflight._DynamicImportSourceScanner(
        source,
        relative_path="src/polisyos/core/__init__.py",
        source_bindings=source_bindings,
        source_context=source_context,
    )

    scanner.scan(tree)
