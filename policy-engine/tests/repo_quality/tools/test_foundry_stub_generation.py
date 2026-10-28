from __future__ import annotations

import ast

from tools.devx.foundry.generate_stubs import _remove_private_exports


def test_private_stub_definitions_are_removed_without_orphaning_their_bodies() -> None:
    source = """\
class Public:
    value: int

class _Private:
    hidden: str

    def helper(self) -> None: ...
"""

    cleaned = _remove_private_exports(source)

    ast.parse(cleaned)
    assert "class _Private:" in cleaned


def test_actual_stub_owner_staging_and_check_detect_complete_byte_drift(tmp_path, capsys):
    """Run real stubgen and the registered owner against a staged complete family."""
    import hashlib
    import json
    import subprocess
    import sys
    from importlib import import_module
    from pathlib import Path

    from tools.devx.foundry import generate_stubs

    owner_root = generate_stubs.REPO_ROOT.resolve()

    def physical_input_path(label: str) -> Path:
        recorded = Path(label)
        return (recorded if recorded.is_absolute() else owner_root / recorded).resolve()

    def receipt(output: str):
        lines = [
            line.removeprefix("Measurement: ")
            for line in output.splitlines()
            if line.startswith("Measurement: ")
        ]
        assert len(lines) == 1
        return json.loads(lines[0])

    def assert_selected_reads(measurement, known_bytes, unreadable=None):
        known = {path.resolve(): payload for path, payload in known_bytes.items()}
        assert len(known) == len(known_bytes)
        errors = {path.resolve(): error for path, error in (unreadable or {}).items()}
        rows = [item for item in measurement["inputs"] if item["operation"] == "read_bytes"]
        observed = [(physical_input_path(item["path"]), item) for item in rows]
        assert {path for path, _item in observed} == set(known)
        for path, item in observed:
            if path in errors:
                assert item["status"] == "unreadable"
                assert item["error"] == errors[path]
                assert "bytes" not in item
                assert "sha256" not in item
            else:
                payload = known[path]
                assert path.read_bytes() == payload
                assert item["status"] == "read"
                assert item["bytes"] == len(payload)
                assert item["sha256"] == hashlib.sha256(payload).hexdigest()

    staged = (tmp_path / "staged").resolve()
    canonical_before = {path: path.read_bytes() for path in generate_stubs.OUTPUT_MAP.values()}
    assert generate_stubs.main(["--output-root", str(staged)]) == 0
    outputs = {
        staged / target.relative_to(generate_stubs.REPO_ROOT): target
        for target in generate_stubs.OUTPUT_MAP.values()
    }
    expected = {path: path.read_bytes() for path in outputs}
    for path, content in expected.items():
        ast.parse(content.decode())
        logical = outputs[path].relative_to(generate_stubs.REPO_ROOT).as_posix()
        for command in ("check", "format"):
            arguments = [sys.executable, "-m", "ruff", command]
            if command == "format":
                arguments.append("--check")
            arguments.extend(
                [
                    "--config",
                    str(generate_stubs.REPO_ROOT / "ruff.toml"),
                    "--no-cache",
                    "--stdin-filename",
                    logical,
                    "-",
                ]
            )
            checked = subprocess.run(
                arguments,
                cwd=generate_stubs.REPO_ROOT,
                input=content.decode(),
                capture_output=True,
                text=True,
                check=False,
            )
            assert checked.returncode == 0, (
                "actual generated stub must pass canonical Ruff "
                + command
                + ": "
                + logical
                + "\n"
                + checked.stdout
                + checked.stderr
            )

    # Runtime facades, not a second symbol list or the generator's own mapping,
    # independently supply the public names and canonical route for each reexport.
    actual_facade_routes = {}
    for module, target in generate_stubs.OUTPUT_MAP.items():
        source_tree = ast.parse(target.with_suffix(".py").read_text())
        routes = [
            ast.literal_eval(node.value.args[1])
            for node in source_tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(item, ast.Name) and item.id == "__all__" for item in node.targets)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "_reexport_module"
        ]
        if not routes:
            continue
        assert len(routes) == 1
        owner = routes[0]
        actual_facade_routes[module] = owner
        facade = import_module(module)
        canonical = import_module(owner)
        names = list(canonical.__all__)
        assert list(facade.__all__) == names
        assert all(getattr(facade, name) is getattr(canonical, name) for name in names)
        stub = ast.parse(expected[staged / target.relative_to(generate_stubs.REPO_ROOT)].decode())
        imports = [node for node in stub.body if isinstance(node, ast.ImportFrom)]
        assert len(imports) == 1 and imports[0].module == owner
        assert len(imports[0].names) == len(names), (
            "facade stub must preserve every actual canonical export without wildcard"
        )
        assert {(alias.name, alias.asname) for alias in imports[0].names} == {
            (name, name) for name in names
        }, "facade stub must preserve every actual canonical export without wildcard"
        declarations = [
            ast.literal_eval(node.value)
            for node in stub.body
            if isinstance(node, ast.Assign)
            and any(isinstance(item, ast.Name) and item.id == "__all__" for item in node.targets)
        ]
        assert declarations == [names]
    assert actual_facade_routes == generate_stubs.REEXPORT_OWNERS
    assert generate_stubs.main(["--check", "--output-root", str(staged)]) == 0
    capsys.readouterr()

    corrupted = {
        path: content + b"\nclass C60CorruptStub:\n    unexpected_field: object\n"
        for path, content in expected.items()
    }
    for path, content in corrupted.items():
        path.write_bytes(content)
    assert generate_stubs.main(["--check", "--output-root", str(staged)]) == 1, (
        "freshness comparator must refuse every changed declared output"
    )
    captured = capsys.readouterr()
    assert all(f"STALE {path}" in captured.err for path in expected)
    measurement = receipt(captured.out)
    assert measurement["freshness_outcome"] == "FAIL"
    assert_selected_reads(measurement, corrupted)
    for path, content in expected.items():
        path.write_bytes(content)
    assert generate_stubs.main(["--check", "--output-root", str(staged)]) == 0
    measurement = receipt(capsys.readouterr().out)
    assert measurement["freshness_outcome"] == "PASS"
    assert_selected_reads(measurement, expected)

    victim = next(iter(expected))
    victim.unlink()
    assert generate_stubs.main(["--check", "--output-root", str(staged)]) == 1
    captured = capsys.readouterr()
    assert "FileNotFoundError" in captured.err and "Freshness comparison ERROR" in captured.err
    measurement = receipt(captured.out)
    assert measurement["freshness_outcome"] == "ERROR"
    assert_selected_reads(measurement, expected, {victim: "FileNotFoundError"})
    victim.mkdir()
    assert generate_stubs.main(["--check", "--output-root", str(staged)]) == 1
    captured = capsys.readouterr()
    assert "IsADirectoryError" in captured.err and '"status": "unreadable"' in captured.out
    measurement = receipt(captured.out)
    assert measurement["freshness_outcome"] == "ERROR"
    assert_selected_reads(measurement, expected, {victim: "IsADirectoryError"})
    victim.rmdir()
    victim.write_bytes(expected[victim])

    outside = staged / "unselected.pyi"
    outside_bytes = b"# Evidence outside the selected OUTPUT_MAP\n"
    outside.write_bytes(outside_bytes)
    assert outside.read_bytes() == outside_bytes
    assert generate_stubs.main(["--check", "--output-root", str(staged)]) == 0
    captured = capsys.readouterr()
    measurement = receipt(captured.out)
    assert measurement["freshness_outcome"] == "PASS"
    assert_selected_reads(measurement, expected)
    assert outside.resolve() not in {
        physical_input_path(item["path"]) for item in measurement["inputs"]
    }
    assert any(
        "unlisted stubs" in boundary for boundary in measurement["unresolved_by_construction"]
    )
    assert {path: path.read_bytes() for path in canonical_before} == canonical_before


def test_generated_family_registration_reconciles_complete_owner_output_map():
    """Registry coverage comes from the actual owner map, without a second output list."""
    import tomllib

    from tools.devx.foundry import generate_stubs

    registry = tomllib.loads(
        (generate_stubs.REPO_ROOT / "architecture/generated_artifacts.toml").read_text()
    )
    (family,) = [item for item in registry["family"] if item["id"] == "foundry-method-stubs"]
    assert set(family["outputs"]) == {
        str(path.relative_to(generate_stubs.REPO_ROOT))
        for path in generate_stubs.OUTPUT_MAP.values()
    }
    assert family["check_command"][-1] == "--check"
    assert family["output_probe_command"][-2:] == ["--output-root", "{output_root}"]
