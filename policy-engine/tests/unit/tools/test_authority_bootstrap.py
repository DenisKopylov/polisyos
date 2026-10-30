"""The early tooling launcher preserves source and candidate boundaries."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_PRODUCT = Path(__file__).resolve().parents[3]


def test_source_candidates_follow_relative_imports_and_module_aliases() -> None:
    from tools.authority_bootstrap import _source_export_candidates

    candidates = _source_export_candidates(
        "example.consumer",
        "src/example/consumer.py",
        b"from .provider import Item as Alias\nimport example.other as other\nother.answer()\n",
    )
    assert "Item" in candidates["example.provider"]
    assert "answer" in candidates["example.other"]


def test_isolated_candidate_fallback_finds_checkout_sources(tmp_path: Path) -> None:
    """A refused source snapshot still permits candidate CLI imports."""
    tools = tmp_path / "tools"
    runner = tools / "ops_runners"
    package = tmp_path / "src/polisyos"
    runner.mkdir(parents=True)
    package.mkdir(parents=True)
    (tools / "__init__.py").write_text("", encoding="utf-8")
    (runner / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text("value = 'candidate'\n", encoding="utf-8")
    (runner / "runtime_cli.py").write_text(
        "from polisyos import value\ndef main(argv):\n    print(value, *argv)\n    return 0\n",
        encoding="utf-8",
    )
    script = """
import pathlib
import sys
product = sys.argv[1]
sys.path.insert(0, product)
from tools import authority_bootstrap as host
host._PRODUCT = pathlib.Path(sys.argv[2])
sys.path.remove(product)
sys.modules.pop('tools.authority_bootstrap', None)
sys.modules.pop('tools', None)
if sys.argv[3] == 'without_paths':
    host.Path.is_dir = lambda self: False
raise SystemExit(host.runtime_main(['ok']))
"""

    def run(mode: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-I", "-S", "-B", "-c", script, str(_PRODUCT), str(tmp_path), mode],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )

    result = run("normal")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "candidate ok"
    removal = run("without_paths")
    print(f"fallback removal exit: {removal.returncode}")
    print(removal.stdout, end="")
    print(removal.stderr, end="")
    assert removal.returncode != 0
    assert "No module named 'tools'" in removal.stderr


def test_candidate_test_and_diagnose_modes_are_available_without_a_source_snapshot(
    tmp_path: Path,
) -> None:
    """Both advertised modes retain candidate behavior when source selection fails."""
    script = """
import pathlib
import sys
product = sys.argv[1]
root = pathlib.Path(sys.argv[2])
mode = sys.argv[3]
control = sys.argv[4]
sys.path.insert(0, product)
from tools import authority_bootstrap as host
host._PRODUCT = root
host._REPOSITORY = root
sys.path.remove(product)
if control == 'legacy_dispatch':
    original = host._invoke_entry
    def incomplete_dispatch(mode, args, **kwargs):
        if mode not in host._ENTRY_TARGETS:
            raise RuntimeError('host_target_unsupported')
        return original(mode, args, **kwargs)
    host._invoke_entry = incomplete_dispatch
elif control == 'borrowed_session':
    host._HOST_SESSION = {'profile': {'authority': True},
                          'last_owner_diagnostic': {'status': 'established'}}
if mode == 'test':
    args = ['-o', 'addopts=', '-p', 'no:cacheprovider', '-q',
            '--basetemp=' + str(root / 'nested-pytest'), str(root / 'test_candidate_smoke.py')]
else:
    args = []
raise SystemExit(host._launch(mode, args))
"""

    def run(root: Path, mode: str, control: str = "normal") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "-B",
                "-c",
                script,
                str(_PRODUCT),
                str(root),
                mode,
                control,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )

    for case in ("missing_checkout", "snapshot_error"):
        root = tmp_path / case
        root.mkdir()
        (root / "test_candidate_smoke.py").write_text(
            "def test_candidate():\n    assert True\n", encoding="utf-8"
        )
        if case == "snapshot_error":
            (root / "src/polisyos").mkdir(parents=True)
            (root / ".venv/bin").mkdir(parents=True)
            (root / ".venv/bin/python").write_text("", encoding="utf-8")
            (root / "uv.lock").write_text("", encoding="utf-8")
        test_run = run(root, "test")
        assert test_run.returncode == 0, test_run.stdout + test_run.stderr
        assert "1 passed" in test_run.stdout
        diagnostic = run(root, "diagnose")
        assert diagnostic.returncode == 0, diagnostic.stderr
        report = json.loads(diagnostic.stdout)
        assert report["profile"]["authority"] is False
        assert report["owner"]["status"] == "not_established"
        assert report["owner"]["failure"] == (
            "source_checkout_unavailable"
            if case == "missing_checkout"
            else "source_snapshot_unavailable"
        )

    removal = run(tmp_path / "missing_checkout", "diagnose", "legacy_dispatch")
    print(f"candidate dispatcher removal exit: {removal.returncode}")
    print(removal.stdout, end="")
    print(removal.stderr, end="")
    assert removal.returncode != 0
    assert "host_target_unsupported" in removal.stderr
    borrowed = run(tmp_path / "snapshot_error", "diagnose", "borrowed_session")
    assert borrowed.returncode == 0, borrowed.stderr
    borrowed_report = json.loads(borrowed.stdout)
    assert borrowed_report["profile"]["authority"] is False
    assert borrowed_report["owner"]["status"] == "not_established"
    assert borrowed_report["owner"]["failure"] == "source_snapshot_unavailable"
