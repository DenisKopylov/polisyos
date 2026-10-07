"""Test owner-aware static census of the E02 single-pass strangle."""

from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.runtime.quality.generation_cycle import StrangleReceipt

_OWNER_MODULE = "polisyos.runtime.quality.workspace.loop"
_OWNER_SOURCE = "src/polisyos/runtime/quality/workspace/loop.py"


def _write_source(root: Path, relative: str, content: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _workspace_loop(root: Path, content: str | None = None) -> Path:
    return _write_source(
        root,
        _OWNER_SOURCE,
        content
        or "class WorkspaceLoop:\n    def run_fixture(self, name):\n        return name\n",
    )


def test_strangle_census_resolves_aliased_owner_import_and_receiver_alias(
    tmp_path: Path,
) -> None:
    _workspace_loop(tmp_path)
    caller = _write_source(
        tmp_path,
        "src/polisyos/runtime/http/services/control/entry.py",
        f"from {_OWNER_MODULE} import WorkspaceLoop as LoopOwner\n"
        "\n"
        "def dispatch():\n"
        "    instance = LoopOwner()\n"
        "    receiver = instance\n"
        "    return receiver.run_fixture('fixture')\n",
    )

    receipt = StrangleReceipt.recompute(tmp_path)

    assert receipt.status == "drift"
    assert receipt.allowed_fixture_callers == ()
    assert receipt.production_single_pass_callers == (
        f"{caller.relative_to(tmp_path).as_posix()}:6",
    )


def test_strangle_census_ignores_unrelated_class_with_same_method_name(
    tmp_path: Path,
) -> None:
    _workspace_loop(tmp_path)
    _write_source(
        tmp_path,
        "src/polisyos/runtime/quality/other_loop.py",
        "class OtherLoop:\n"
        "    def run_fixture(self, name):\n"
        "        return name\n"
        "\n"
        "def dispatch():\n"
        "    other = OtherLoop()\n"
        "    return other.run_fixture('fixture')\n",
    )

    receipt = StrangleReceipt.recompute(tmp_path)

    assert receipt.status == "strangled"
    assert receipt.allowed_fixture_callers == ()
    assert receipt.production_single_pass_callers == ()


def test_strangle_census_allows_only_the_two_workspace_loop_delegations(
    tmp_path: Path,
) -> None:
    _workspace_loop(
        tmp_path,
        "class WorkspaceLoop:\n"
        "    def run_fixture(self, name):\n"
        "        return name\n"
        "\n"
        "    def decompose_fixture(self):\n"
        "        return self.run_fixture('decomposed')\n"
        "\n"
        "    def run_control_plane_fixture(self):\n"
        "        return self.run_fixture('control-plane')\n"
        "\n"
        "    def unrelated_dispatch(self):\n"
        "        return self.run_fixture('unrelated')\n",
    )

    receipt = StrangleReceipt.recompute(tmp_path)

    assert receipt.status == "drift"
    assert receipt.allowed_fixture_callers == (
        f"{_OWNER_SOURCE}:6",
        f"{_OWNER_SOURCE}:9",
    )
    assert receipt.production_single_pass_callers == (f"{_OWNER_SOURCE}:12",)


def test_strangle_census_does_not_promote_missing_source_root(tmp_path: Path) -> None:
    receipt = StrangleReceipt.recompute(tmp_path)

    assert receipt.status == "not_established"
    assert receipt.source_state == "missing"
    assert receipt.source_content_hash is None


def test_strangle_census_does_not_promote_parse_error(tmp_path: Path) -> None:
    _write_source(tmp_path, "src/polisyos/broken.py", "def broken(:\n    pass\n")

    receipt = StrangleReceipt.recompute(tmp_path)

    assert receipt.status == "not_established"
    assert receipt.source_state == "parse_error"
    assert receipt.source_content_hash is None
    assert any("parse_error" in item for item in receipt.parse_errors)


def test_strangle_census_does_not_promote_read_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_source(tmp_path, "src/polisyos/read_error.py", "value = 1\n")
    original_read_bytes = Path.read_bytes

    def fail_one_source(path: Path) -> bytes:
        if path.resolve() == source.resolve():
            raise PermissionError("source unavailable")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", fail_one_source)

    receipt = StrangleReceipt.recompute(tmp_path)

    assert receipt.status == "not_established"
    assert receipt.source_state == "read_error"
    assert receipt.source_content_hash is None
    assert any("read_error" in item for item in receipt.parse_errors)


def test_strangle_census_does_not_treat_symlink_directory_as_complete(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "src" / "polisyos"
    source_root.mkdir(parents=True)
    (source_root / "ordinary.py").write_text("value = 1\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "hidden.py").write_text("value = 1\n", encoding="utf-8")
    link = source_root / "linked-package"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks unavailable: {exc}")

    receipt = StrangleReceipt.recompute(tmp_path)

    assert receipt.status == "not_established"


def test_strangle_census_does_not_follow_ancestor_source_symlink(
    tmp_path: Path,
) -> None:
    source = (
        "class WorkspaceLoop:\n"
        "    def run_fixture(self, name):\n"
        "        return name\n"
    )
    contained_root = tmp_path / "contained-repo"
    contained_source = _write_source(contained_root, _OWNER_SOURCE, source)

    contained = StrangleReceipt.recompute(contained_root)

    assert contained.status == "strangled"
    assert contained.source_state == "available"
    assert contained.source_content_hash is not None
    assert contained.source_file_count == 1

    external_root = tmp_path / "external-source"
    external_source = _write_source(external_root, _OWNER_SOURCE, source)
    assert external_source.read_bytes() == contained_source.read_bytes()

    symlink_repo_root = tmp_path / "symlink-repo"
    symlink_repo_root.mkdir()
    try:
        (symlink_repo_root / "src").symlink_to(
            external_root / "src", target_is_directory=True
        )
    except OSError as exc:
        pytest.skip(f"directory symlinks unavailable: {exc}")
    linked_source = symlink_repo_root / _OWNER_SOURCE
    assert linked_source.is_file()
    assert linked_source.read_bytes() == contained_source.read_bytes()

    receipt = StrangleReceipt.recompute(symlink_repo_root)

    assert receipt.status == "not_established"
    assert receipt.source_state == "not_established"
    assert receipt.source_content_hash is None
    assert receipt.source_file_count == 0


def test_strangle_census_leaves_reflection_unresolved(
    tmp_path: Path,
) -> None:
    _workspace_loop(tmp_path)
    _write_source(
        tmp_path,
        "src/polisyos/runtime/http/services/control/reflective.py",
        "def dispatch(receiver):\n"
        "    return getattr(receiver, 'run_fixture')('fixture')\n",
    )

    receipt = StrangleReceipt.recompute(tmp_path)

    assert receipt.status == "not_established"


def test_strangle_census_leaves_rebound_receiver_unresolved(
    tmp_path: Path,
) -> None:
    _workspace_loop(tmp_path)
    _write_source(
        tmp_path,
        "src/polisyos/runtime/http/services/control/rebound.py",
        f"from {_OWNER_MODULE} import WorkspaceLoop as LoopOwner\n"
        "\n"
        "def dispatch():\n"
        "    receiver = LoopOwner()\n"
        "    receiver = lookup_receiver()\n"
        "    return receiver.run_fixture('fixture')\n",
    )

    receipt = StrangleReceipt.recompute(tmp_path)

    assert receipt.status == "not_established"


def test_strangle_census_leaves_inherited_owner_member_unresolved(
    tmp_path: Path,
) -> None:
    _workspace_loop(tmp_path)
    _write_source(
        tmp_path,
        "src/polisyos/runtime/quality/child_loop.py",
        f"from {_OWNER_MODULE} import WorkspaceLoop\n"
        "\n"
        "class ChildLoop(WorkspaceLoop):\n"
        "    def dispatch(self):\n"
        "        return self.run_fixture('fixture')\n",
    )

    receipt = StrangleReceipt.recompute(tmp_path)

    assert receipt.status == "not_established"


@pytest.mark.parametrize(
    "source",
    [
        "import builtins\n"
        "\n"
        "def dispatch(receiver):\n"
        "    return builtins.getattr(receiver, 'run_fixture')('fixture')\n",
        "def dispatch(receiver):\n"
        "    return receiver.__getattribute__('run_fixture')('fixture')\n",
    ],
    ids=("qualified-getattr", "qualified-getattribute"),
)
def test_strangle_census_leaves_qualified_reflection_unresolved(
    tmp_path: Path,
    source: str,
) -> None:
    _workspace_loop(tmp_path)
    _write_source(
        tmp_path,
        "src/polisyos/runtime/http/services/control/qualified_reflection.py",
        source,
    )

    receipt = StrangleReceipt.recompute(tmp_path)

    assert receipt.status == "not_established"


def test_strangle_census_resolves_bound_method_alias_with_arbitrary_name(
    tmp_path: Path,
) -> None:
    _workspace_loop(tmp_path)
    caller = _write_source(
        tmp_path,
        "src/polisyos/runtime/http/services/control/bound_alias.py",
        f"from {_OWNER_MODULE} import WorkspaceLoop as LoopOwner\n"
        "\n"
        "def dispatch():\n"
        "    loop = LoopOwner()\n"
        "    arbitrary_name = loop.run_fixture\n"
        "    return arbitrary_name('fixture')\n",
    )

    receipt = StrangleReceipt.recompute(tmp_path)

    assert receipt.status == "drift"
    assert receipt.production_single_pass_callers == (
        f"{caller.relative_to(tmp_path).as_posix()}:6",
    )


def test_strangle_census_leaves_nested_attribute_receiver_unresolved(
    tmp_path: Path,
) -> None:
    _workspace_loop(tmp_path)
    _write_source(
        tmp_path,
        "src/polisyos/runtime/http/services/control/nested_receiver.py",
        "def dispatch(container):\n"
        "    return container.loop.run_fixture('fixture')\n",
    )

    receipt = StrangleReceipt.recompute(tmp_path)

    assert receipt.status == "not_established"


def test_strangle_census_keeps_nested_owner_call_with_unknown_outer_dispatch(
    tmp_path: Path,
) -> None:
    _workspace_loop(
        tmp_path,
        "class WorkspaceLoop:\n"
        "    def run_fixture(self, name):\n"
        "        return name\n"
        "\n"
        "    def decompose_fixture(self):\n"
        "        def nested(): return foreign.run_fixture(self.run_fixture('inner'))\n",
    )

    receipt = StrangleReceipt.recompute(tmp_path)

    assert receipt.status == "not_established"
    assert receipt.allowed_fixture_callers == ()
    assert receipt.production_single_pass_callers == (f"{_OWNER_SOURCE}:6",)


def test_strangle_census_keeps_forbidden_owner_call_sharing_allowed_call_line(
    tmp_path: Path,
) -> None:
    _workspace_loop(
        tmp_path,
        "class WorkspaceLoop:\n"
        "    def run_fixture(self, name):\n"
        "        return name\n"
        "\n"
        "    def decompose_fixture(self):\n"
        "        foreign = WorkspaceLoop()\n"
        "        return foreign.run_fixture(self.run_fixture('inner'))\n",
    )

    receipt = StrangleReceipt.recompute(tmp_path)

    assert receipt.status == "drift"
    assert receipt.allowed_fixture_callers == ()
    assert receipt.production_single_pass_callers == (f"{_OWNER_SOURCE}:7",)
