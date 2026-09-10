"""Behavioral regressions for the bounded production-invocation instrument."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path


def _owner():
    return importlib.import_module("polisyos.runtime.quality.production_invocation")


def _write(repo: Path, files: dict[str, str]) -> None:
    for name, source in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def test_cli_reports_test_only_verifier_and_persists_negative(tmp_path):
    _git(tmp_path, "init", "-q")
    _write(tmp_path, {"src/pkg/seed.py": "# base\n"})
    _git(tmp_path, "add", ".")
    _git(
        tmp_path,
        "-c",
        "user.name=Invocation test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-qm",
        "base",
    )
    base = _git(tmp_path, "rev-parse", "HEAD")
    _write(
        tmp_path,
        {
            "src/pkg/check.py": "def verify(value):\n    return value != 'bad'\n",
            "tests/test_check.py": "from pkg.check import verify\nverify('bad')\n",
        },
    )
    _git(tmp_path, "add", ".")
    receipt = tmp_path / "receipt.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "polisyos.runtime.quality.production_invocation",
            "--repo-root",
            str(tmp_path),
            "--base",
            base,
            "--receipt",
            str(receipt),
        ],
        text=True,
        capture_output=True,
        timeout=180,
    )
    assert receipt.exists(), result.stderr
    observed = json.loads(receipt.read_text())
    assert result.returncode == 1
    assert observed["regressions"] == ["pkg.check.verify"]
    assert observed["mechanisms"]["pkg.check.verify"]["status"] == "uninvoked"
    assert observed["mechanisms"]["pkg.check.verify"]["test_callers"]

    # Recompute through the same real CLI, then corrupt a deciding denominator.
    rerun = subprocess.run(
        [
            sys.executable,
            "-m",
            "polisyos.runtime.quality.production_invocation",
            "--repo-root",
            str(tmp_path),
            "--base",
            base,
            "--receipt",
            str(receipt),
            "--check",
            str(receipt),
        ],
        text=True,
        capture_output=True,
        timeout=180,
    )
    assert rerun.returncode == 1  # The unchanged orphan is still a negative.
    corrupt = tmp_path / "corrupt.json"
    observed["denominator"]["source_files"] += 1
    corrupt.write_text(json.dumps(observed))
    rejected = subprocess.run(
        [
            sys.executable,
            "-m",
            "polisyos.runtime.quality.production_invocation",
            "--repo-root",
            str(tmp_path),
            "--base",
            base,
            "--receipt",
            str(receipt),
            "--check",
            str(corrupt),
        ],
        text=True,
        capture_output=True,
        timeout=180,
    )
    assert rejected.returncode == 2
    assert json.loads(rejected.stdout)["reason"] == "invocation_receipt_drift"


def test_import_annotation_and_orphan_helper_do_not_supply_a_runnable_caller():
    files = {
        "src/pkg/owner.py": "def verify(value):\n    return bool(value)\n",
        "src/pkg/helper.py": (
            "from pkg.owner import verify as inspect\n"
            "def wrapper(value: inspect):\n    return inspect(value)\n"
        ),
        "tests/test_owner.py": "from pkg.helper import wrapper\nwrapper(False)\n",
    }
    result = _owner().audit_sources(files, {})
    assert set(result["regressions"]) == {"pkg.owner.verify", "pkg.helper.wrapper"}
    files["src/pkg/cli.py"] = (
        "from pkg.helper import wrapper as run\n"
        "def main():\n    return run(False)\n"
        "if __name__ == '__main__':\n    main()\n"
    )
    result = _owner().audit_sources(files, {})
    assert result["regressions"] == []
    assert result["mechanisms"]["pkg.owner.verify"]["status"] == "static_path"
    assert result["mechanisms"]["pkg.owner.verify"]["terminus"] == "pkg.cli:<entry>"


def test_class_construction_does_not_invoke_its_verification_method():
    files = {
        "src/pkg/owner.py": "class Verifier:\n    def verify(self):\n        return False\n",
        "src/pkg/cli.py": (
            "from pkg.owner import Verifier as V\n"
            "def main():\n    candidate = V()\n    return candidate\n"
            "if __name__ == '__main__':\n    main()\n"
        ),
    }
    result = _owner().audit_sources(files, {})
    assert result["regressions"] == ["pkg.owner.Verifier.verify"]
    files["src/pkg/cli.py"] = files["src/pkg/cli.py"].replace(
        "return candidate", "return candidate.verify()"
    )
    assert _owner().audit_sources(files, {})["regressions"] == []


def test_removing_a_call_from_a_previously_reached_mechanism_is_a_regression():
    before = {
        "src/pkg/owner.py": "def verify():\n    return False\n",
        "src/pkg/cli.py": (
            "from pkg.owner import verify\nif __name__ == '__main__':\n    verify()\n"
        ),
    }
    after = {**before, "src/pkg/cli.py": "from pkg.owner import verify\n"}
    result = _owner().audit_sources(after, before)
    assert result["regressions"] == ["pkg.owner.verify"]


def test_named_deferral_is_explicit_and_never_a_static_path():
    sources = {"src/pkg/owner.py": "def study():\n    return False\n"}
    decision = {"pkg.owner.study": {"task": "GY-CB2", "reason": "Real study intake absent"}}
    result = _owner().audit_sources(sources, {}, deferrals=decision)
    assert result["regressions"] == []
    assert result["mechanisms"]["pkg.owner.study"]["status"] == "deferred"
    assert result["mechanisms"]["pkg.owner.study"]["terminus"] is None


def test_parameter_shadowing_does_not_turn_an_import_into_a_production_call():
    sources = {
        "src/pkg/owner.py": "def verify():\n    return False\n",
        "src/pkg/cli.py": (
            "from pkg.owner import verify\n"
            "def main(verify):\n    return verify()\n"
            "if __name__ == '__main__':\n    main(lambda: True)\n"
        ),
    }
    assert "pkg.owner.verify" in _owner().audit_sources(sources, {})["regressions"]


def test_recursion_and_literal_false_entry_do_not_establish_invocation():
    sources = {
        "src/pkg/owner.py": "def verify():\n    return verify()\n",
        "src/pkg/cli.py": (
            "from pkg.owner import verify\n"
            "if __name__ == '__main__':\n    if False:\n        verify()\n"
        ),
    }
    assert _owner().audit_sources(sources, {})["regressions"] == ["pkg.owner.verify"]


def test_executable_script_registration_is_a_root_but_test_script_is_not():
    sources = {"src/pkg/owner.py": "def verify():\n    return False\n"}
    result = _owner().audit_sources(sources, {}, entry_points=["pkg.owner:verify"])
    assert result["regressions"] == []


def test_lexical_definitions_survive_entry_and_statement_containers():
    for source in (
        "if __name__ == '__main__':\n    def run():\n        return False\n    run()\n",
        "match 1:\n    case _:\n        def run():\n            return False\n"
        "if __name__ == '__main__':\n    run()\n",
    ):
        result = _owner().audit_sources({"src/pkg/cli.py": source}, {})
        assert result["regressions"] == []
        assert result["mechanisms"]["pkg.cli.run"]["status"] == "static_path"
