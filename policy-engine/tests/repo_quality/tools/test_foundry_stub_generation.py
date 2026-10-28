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
    committed_before = {path: path.read_bytes() for path in generate_stubs.OUTPUT_MAP.values()}
    assert generate_stubs.main(["--output-root", str(staged)]) == 0
    outputs = {
        staged / target.relative_to(generate_stubs.REPO_ROOT): target
        for target in generate_stubs.OUTPUT_MAP.values()
    }
    expected = {path: path.read_bytes() for path in outputs}
    for content in expected.values():
        ast.parse(content.decode())
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
    assert {path: path.read_bytes() for path in committed_before} == committed_before


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
