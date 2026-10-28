"""Behavioral bounded tests for the canonical Q2 app dependency partition."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[4]
TOOL = (
    ROOT / "policy-engine/docs/research/e02-cloud-test-plan/"
    "implementation-handoffs/LOCAL/q2-packaging/raw/r"
    "un.py"
)


def helper():
    spec = importlib.util.spec_from_file_location("q2_partition_test_owner", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def measured(tmp_path):
    q2 = helper()
    prefix = (tmp_path / "source" / ".venv").resolve()
    site = prefix / "lib/python3.14/site-packages"
    site.mkdir(parents=True)
    python = prefix / "bin/python"
    python.parent.mkdir()
    python.write_text("test-only executable identity")
    (prefix / "pyvenv.cfg").write_text("home = fixture\n")
    (site / "editable.pth").write_text("THIS_MUST_NEVER_EXECUTE()\n")
    info = {
        "prefix": str(prefix),
        "purelib": str(site),
        "executable": str(python),
        "base_executable": str(python),
        "version": [3, 14, 0],
    }
    calls = []

    def actual_probe(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(stdout=json.dumps(info))

    with patch.object(q2, "run_command", actual_probe):
        profile = q2.measure_app_dependency_profile(python, site, tmp_path)
        with pytest.raises(q2.WaveFailure):
            q2.measure_app_dependency_profile(python, tmp_path, tmp_path)
    assert calls[0][0] == str(python) and calls[0][1:3] == ["-I", "-S"]
    return q2, profile, site


def test_exact_measured_site_only(tmp_path):
    q2, profile, site = measured(tmp_path)
    namespace = {"Path": Path}
    exec(q2.dependency_profile_guard(profile), namespace)  # noqa: S102 - Exercise the generated guard on owned synthetic inputs.
    allowed = namespace["_q2_dependency_site_allowed"]
    assert allowed(site)
    for forbidden in (
        site.parent,
        site.parent.parent.parent.parent / "src",
        site / "polisyos",
        tmp_path,
    ):
        assert not allowed(forbidden)
    roots = [site.parents[3]]
    paths = [site, roots[0] / "src", roots[0] / "tools", site / "polisyos"]
    bad = [p for p in paths if not allowed(p) and any(p.is_relative_to(r) for r in roots)]
    assert bad == paths[1:]


def test_changed_or_added_pth_fails_profile_not_executes_pth(tmp_path):
    q2, profile, site = measured(tmp_path)
    namespace = {"Path": Path}
    exec(q2.dependency_profile_guard(profile), namespace)  # noqa: S102 - Exercise the generated guard on owned synthetic inputs.
    pth = site / "editable.pth"
    old = pth.read_bytes()
    pth.write_bytes(old + b"changed")
    with pytest.raises(RuntimeError):
        namespace["_q2_dependency_site_allowed"](site)
    pth.write_bytes(old)
    (site / "extra.pth").write_text("raise RuntimeError()")
    with pytest.raises(RuntimeError):
        namespace["_q2_dependency_site_allowed"](site)
