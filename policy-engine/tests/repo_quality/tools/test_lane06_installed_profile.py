"""Exercise the shared installed observer with actual temporary Python prefixes."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

import pytest

from tests._helpers.installed_profile import (
    clean_installed_environment,
    installed_child_environment,
    prepare_installed_observer,
    read_completed_observer_reports,
)

_PRODUCT = Path(__file__).resolve().parents[3]


def _prefix(root: Path) -> tuple[Path, Path, Path]:
    subprocess.run(
        [sys._base_executable, "-I", "-B", "-m", "venv", "--without-pip", str(root)],
        check=True,
        capture_output=True,
        timeout=30,
    )
    python = root / "bin/python"
    result = subprocess.run(
        [str(python), "-I", "-S", "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return root, python, Path(result.stdout.strip())


@pytest.fixture
def installed_fixture(tmp_path: Path) -> dict[str, Any]:
    """Create tiny stdlib-only prefixes; no product build or dependencies are copied."""
    prefix, python, site = _prefix(tmp_path / "installed")
    _, app_python, dependency = _prefix(tmp_path / "dependency")
    sentinel = tmp_path / "pth-executed"
    (dependency / "not-executed.pth").write_text(
        f"import pathlib; pathlib.Path({str(sentinel)!r}).write_text('executed')\n"
    )
    wheel = tmp_path / "fixture.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("polisyos/__init__.py", "VALUE = 7\n")
        archive.writestr("tools/__init__.py", "VALUE = 11\n")
    for name in ("polisyos", "tools"):
        (site / name).mkdir()
        with zipfile.ZipFile(wheel) as archive:
            (site / name / "__init__.py").write_bytes(archive.read(name + "/__init__.py"))
    reports = tmp_path / "reports"
    prepared = prepare_installed_observer(
        product=_PRODUCT,
        prefix=prefix,
        purelib=site,
        app_python=app_python,
        dependency_site=dependency,
        wheel=wheel,
        reports=reports,
        tests_root=_PRODUCT / "tests",
    )
    return {
        "python": python,
        "site": site,
        "dependency": dependency,
        "wheel": wheel,
        "reports": reports,
        "prepared": prepared,
        "pth_sentinel": sentinel,
        "app_python": app_python,
        "cwd": tmp_path,
    }


def _run(fixture: dict[str, Any], code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(fixture["python"]), "-I", "-B", "-c", code],
        cwd=fixture["cwd"],
        env=clean_installed_environment(os.environ),
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _reports(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    return [json.loads(p.read_text()) for p in fixture["reports"].glob("*.json")]


def test_environment_clears_source_injection_and_unrelated_task_observers() -> None:
    result = clean_installed_environment(
        {"PYTHONPATH": "/source", "C97_CHILD_REPORT": "/old", "PATH": "/bin", "KEEP": "yes"}
    )
    assert "PYTHONPATH" not in result
    assert "C97_CHILD_REPORT" not in result
    assert result["PATH"] == "/bin"
    assert result["KEEP"] == "yes"
    assert result["PYTHONSAFEPATH"] == "1"
    assert result["POLISYOS_INSTALLED_PROFILE_ACTIVE"] == "1"


def test_absent_profile_keeps_source_mode_but_active_unknown_does_not() -> None:
    assert installed_child_environment({"PYTHONPATH": "/existing-source"}) is None
    with pytest.raises(ValueError, match="no admitted purelib"):
        installed_child_environment({"POLISYOS_INSTALLED_PROFILE_ACTIVE": "1"})


def test_purelib_marker_cannot_relabel_the_source_interpreter(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="actual sysconfig"):
        installed_child_environment({"POLISYOS_INSTALLED_PROFILE_PURELIB": str(tmp_path)})


def test_real_prefix_parent_and_child_read_the_same_installed_archive(
    installed_fixture: dict[str, Any],
) -> None:
    result = _run(
        installed_fixture,
        "import polisyos, tools, subprocess, sys; "
        "assert polisyos.VALUE == 7 and tools.VALUE == 11; "
        "subprocess.run([sys.executable, '-B', '-c', "
        "'import polisyos, tools; assert polisyos.VALUE == 7 and tools.VALUE == 11'], check=True)",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    reports = read_completed_observer_reports(
        installed_fixture["reports"], wheel_sha256=installed_fixture["prepared"]["wheel_sha256"]
    )
    assert len(reports) == 2
    assert all(r["phase"] == "finished" and not r["errors"] for r in reports)
    assert all({"polisyos", "tools"} <= r["origins"].keys() for r in reports)
    assert not installed_fixture["pth_sentinel"].exists()


def test_canonical_gate_shadow_cannot_launder_a_foreign_product_import(
    installed_fixture: dict[str, Any], tmp_path: Path
) -> None:
    source = tmp_path / "shadow-source"
    (source / "polisyos").mkdir(parents=True)
    (source / "polisyos/__init__.py").write_text("VALUE = 99\n")
    (source / "q2_installed_origin_gate.py").write_text(
        "def verify_loaded_module_origins(*args): return {}, []\n"
    )
    result = _run(
        installed_fixture,
        f"import sys; sys.path.insert(0, {str(source)!r}); "
        "sys.modules.pop('q2_installed_origin_gate'); "
        "import polisyos, q2_installed_origin_gate; "
        "assert polisyos.VALUE == 99; "
        "assert q2_installed_origin_gate.verify_loaded_module_origins() == ({}, [])",
    )
    assert result.returncode == 86
    report = _reports(installed_fixture)[0]
    assert report["phase"] == "failed"
    assert {e.get("module") for e in report["errors"] if isinstance(e, dict)} >= {
        "polisyos",
        "q2_installed_origin_gate",
    }


def test_actual_source_import_is_rejected_despite_a_valid_installed_prefix(
    installed_fixture: dict[str, Any], tmp_path: Path
) -> None:
    source = tmp_path / "foreign-source"
    (source / "polisyos").mkdir(parents=True)
    (source / "polisyos/__init__.py").write_text("VALUE = 99\n")
    result = _run(
        installed_fixture,
        "import sys, os\n"
        "from tests._helpers.installed_profile import installed_child_environment\n"
        f"sys.path.insert(0, {str(source)!r})\n"
        "import polisyos\n"
        "assert polisyos.VALUE == 99\n"
        "try:\n"
        "    installed_child_environment(os.environ)\n"
        "except ValueError:\n"
        "    print('foreign child profile refused')\n"
        "else:\n"
        "    raise AssertionError('foreign package was admitted')\n",
    )
    assert result.returncode == 86
    assert "foreign child profile refused" in result.stdout
    report = _reports(installed_fixture)[0]
    assert report["phase"] == "failed"
    assert any(isinstance(e, dict) and e.get("module") == "polisyos" for e in report["errors"])


def test_modified_installed_module_does_not_match_the_selected_archive(
    installed_fixture: dict[str, Any],
) -> None:
    (installed_fixture["site"] / "polisyos/__init__.py").write_text("VALUE = 13\n")
    result = _run(installed_fixture, "import polisyos; assert polisyos.VALUE == 13")
    assert result.returncode == 86
    assert any(
        isinstance(e, dict) and e.get("reason") == "loaded file differs from wheel"
        for e in _reports(installed_fixture)[0]["errors"]
    )


def test_changed_unexecuted_dependency_profile_remains_an_admission_error(
    installed_fixture: dict[str, Any],
) -> None:
    (installed_fixture["dependency"] / "not-executed.pth").write_text("changed but not executed\n")
    result = _run(installed_fixture, "raise AssertionError('must refuse before this body')")
    assert result.returncode == 86
    report = _reports(installed_fixture)[0]
    assert report["phase"] == "failed"
    assert "app profile input bytes changed" in str(report["errors"])
    assert "must refuse before this body" not in result.stderr


@pytest.mark.parametrize("streams", ["stdout_none", "stderr_none", "both_closed"])
def test_site_startup_cannot_suppress_refusal_when_output_streams_are_unavailable(
    installed_fixture: dict[str, Any], tmp_path: Path, streams: str
) -> None:
    (installed_fixture["dependency"] / "not-executed.pth").write_text("changed profile\n")
    sentinel = tmp_path / "body-executed"
    code = (
        "import sys, site\n"
        "from pathlib import Path\n"
        f"sys.path.append({str(installed_fixture['site'])!r})\n"
        f"streams = {streams!r}\n"
        "if streams == 'stdout_none':\n"
        "    sys.stdout = None\n"
        "elif streams == 'stderr_none':\n"
        "    sys.stderr = None\n"
        "else:\n"
        "    sys.stdout.close()\n"
        "    sys.stderr.close()\n"
        "site.execsitecustomize()\n"
        f"Path({str(sentinel)!r}).write_text('body ran after suppressed startup error')\n"
    )
    result = subprocess.run(
        [str(installed_fixture["python"]), "-I", "-S", "-B", "-c", code],
        cwd=installed_fixture["cwd"],
        env=clean_installed_environment(os.environ),
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 86, result.stdout + result.stderr
    assert not sentinel.exists()
    report = _reports(installed_fixture)[0]
    assert report["phase"] == "failed"
    assert "app profile input bytes changed" in str(report["errors"])


def test_interrupted_child_keeps_a_started_record_instead_of_false_completion(
    installed_fixture: dict[str, Any],
) -> None:
    result = _run(installed_fixture, "import os; os._exit(0)")
    assert result.returncode == 0
    assert _reports(installed_fixture)[0]["phase"] == "started"
    with pytest.raises(ValueError, match="incomplete"):
        read_completed_observer_reports(
            installed_fixture["reports"], wheel_sha256=installed_fixture["prepared"]["wheel_sha256"]
        )


def test_report_alias_into_installed_prefix_is_rejected(
    installed_fixture: dict[str, Any], tmp_path: Path
) -> None:
    alias = tmp_path / "report-alias"
    alias.symlink_to(installed_fixture["site"], target_is_directory=True)
    with pytest.raises(ValueError, match="outputs must not"):
        prepare_installed_observer(
            product=_PRODUCT,
            prefix=installed_fixture["site"].parents[2],
            purelib=installed_fixture["site"],
            app_python=installed_fixture["app_python"],
            dependency_site=installed_fixture["dependency"],
            wheel=installed_fixture["wheel"],
            reports=alias / "inside-prefix",
        )
    assert not (installed_fixture["site"] / "inside-prefix").exists()


def test_explicit_test_namespaces_do_not_add_checkout_to_import_path(
    installed_fixture: dict[str, Any],
) -> None:
    result = _run(
        installed_fixture,
        "import tests._helpers.installed_profile as helper, polisyos; import sys, os; "
        "assert polisyos.VALUE == 7; "
        "child = helper.installed_child_environment(os.environ); "
        "assert child['POLISYOS_INSTALLED_PROFILE_ACTIVE'] == '1'; "
        "assert 'PYTHONPATH' not in child and 'POLISYOS_INSTALLED_PROFILE_PURELIB' not in child; "
        f"assert {str(_PRODUCT)!r} not in sys.path; "
        f"assert {str(_PRODUCT / 'tests')!r} not in sys.path",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = _reports(installed_fixture)[0]
    assert "tests._helpers.installed_profile" in report["test_inputs"]


def test_normal_unqualified_interpreter_probe_does_not_run_the_observer(
    installed_fixture: dict[str, Any],
) -> None:
    environment = clean_installed_environment(os.environ)
    environment.pop("POLISYOS_INSTALLED_PROFILE_ACTIVE")
    result = subprocess.run(
        [
            str(installed_fixture["python"]),
            "-I",
            "-c",
            "import sysconfig; print(sysconfig.get_path('purelib'))",
        ],
        cwd=installed_fixture["cwd"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(installed_fixture["site"])
    assert _reports(installed_fixture) == []
    with pytest.raises(ValueError, match="no installed process records"):
        read_completed_observer_reports(
            installed_fixture["reports"], wheel_sha256=installed_fixture["prepared"]["wheel_sha256"]
        )


def test_report_consumer_refuses_wrong_wheel_and_empty_product_basis(tmp_path: Path) -> None:
    report = tmp_path / "process.json"
    report.write_text(json.dumps({"phase": "finished", "errors": [], "wheel_sha256": "wrong"}))
    with pytest.raises(ValueError, match="different wheel"):
        read_completed_observer_reports(tmp_path, wheel_sha256="expected")
    report.write_text(
        json.dumps({"phase": "finished", "errors": [], "wheel_sha256": "expected", "origins": {}})
    )
    with pytest.raises(ValueError, match="no installed product import"):
        read_completed_observer_reports(tmp_path, wheel_sha256="expected")
