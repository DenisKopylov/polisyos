"""Dispatch the real installed-wheel LA-057 consumer from a normal source cohort.

The eight defining consumer cases execute in the explicit isolated interpreter.
This outer native case preserves their complete output and XML before asserting
the outcome. It never imports the source-checkout bridge as an installed proxy.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path


def _required_path(name: str) -> Path:
    value = os.environ.get(name)
    assert value, f"explicit installed-wheel input missing: {name}"
    # Keep the venv interpreter's lexical path: resolving its symlink loses sys.prefix.
    path = Path(value).absolute()
    assert path.exists(), f"installed-wheel input absent: {path}"
    return path


def test_installed_wheel_consumers_in_isolated_child(tmp_path: Path) -> None:
    """Run the genuine package consumer in its isolated, wheel-installed Python."""
    python = _required_path("E02_LA057_INSTALLED_PYTHON")
    wheel = _required_path("E02_LA057_WHEEL_PATH")
    site = _required_path("E02_LA057_INSTALLED_SITE")
    source = _required_path("E02_LA057_SOURCE_ROOT")
    source_sha = os.environ.get("E02_LA057_SOURCE_SHA")
    consumer_sha256 = os.environ.get("E02_LA057_CONSUMER_SHA256")
    outer_sha256 = os.environ.get("E02_LA057_OUTER_TEST_SHA256")
    assert source_sha and consumer_sha256 and outer_sha256
    consumer = Path(__file__).with_name("installed_wheel_bridge_consumer.py")
    assert hashlib.sha256(consumer.read_bytes()).hexdigest() == consumer_sha256
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == outer_sha256
    stdout = tmp_path / "installed-child.txt"
    xml = tmp_path / "installed-child.xml"
    argv = [
        str(python),
        "-I",
        "-B",
        "-m",
        "pytest",
        "-q",
        "-s",
        "--noconftest",
        "--import-mode=importlib",
        "-c",
        "/dev/null",
        "-o",
        "addopts=",
        "-o",
        "pythonpath=",
        "-o",
        f"cache_dir={tmp_path / 'cache'}",
        "--basetemp",
        str(tmp_path / "child-scratch"),
        "--junitxml",
        str(xml),
        str(consumer),
    ]
    env = dict(os.environ)
    for name in ("PYTHONPATH", "PYTHONHOME", "PYTEST_ADDOPTS", "PYTEST_PLUGINS"):
        env.pop(name, None)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["E02_LA057_TEST_SHA256"] = consumer_sha256
    t0 = time.monotonic()
    # No shell or source fallback: invoke the explicitly supplied installed interpreter.
    with stdout.open("wb") as stream:
        process = subprocess.Popen(  # noqa: S603
            argv, cwd=tmp_path, env=env, stdout=stream, stderr=subprocess.STDOUT
        )
        _, status, usage = os.wait4(process.pid, 0)
        process.returncode = os.waitstatus_to_exitcode(status)
    raw = stdout.read_bytes()
    cases = []
    if xml.exists():
        # XML is emitted by this exact isolated pytest child, not an external input.
        for case in ET.parse(xml).getroot().iter("testcase"):  # noqa: S314
            outcome = next(
                (name for name in ("failure", "error", "skipped") if case.find(name) is not None),
                "passed",
            )
            cases.append({"name": case.get("name"), "outcome": outcome})
    observations = {
        "observation": "installed-wheel-child-dispatch",
        "source_sha": source_sha,
        "source_root": str(source),
        "python": str(python),
        "site": str(site),
        "wheel": str(wheel),
        "consumer_sha256": consumer_sha256,
        "outer_sha256": outer_sha256,
        "command": argv,
        "exit": process.returncode,
        "wall_s": time.monotonic() - t0,
        "child_maxrss_platform_units": usage.ru_maxrss,
        "maxrss_unit": "KiB on Linux; bytes on macOS",
        "stdout": str(stdout),
        "stdout_sha256": hashlib.sha256(raw).hexdigest(),
        "xml": str(xml),
        "xml_sha256": hashlib.sha256(xml.read_bytes()).hexdigest() if xml.exists() else None,
        "actual_consumer_cases": cases,
        "module_origin_profile": "Complete actual child stdout, source/installed/wheel binding fixture.",
        "count_scope": "One outer case and eight child consumer cases are separate denominators.",
    }
    (tmp_path / "installed-child-wrapper.json").write_text(
        json.dumps(observations, indent=2) + "\n"
    )
    print(raw.decode(errors="replace"))
    print(json.dumps(observations, sort_keys=True))
    assert process.returncode == 0, f"installed consumer failed; full output: {stdout}"
    assert len(cases) == 8, f"complete defining file expected eight cases, observed: {cases}"
    assert all(case["outcome"] == "passed" for case in cases), cases
