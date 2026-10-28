"""Behavioral witnesses for federation execution-observer identity and origin scope."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import CodeType, FunctionType

from _helpers.code_identity import CODE_FINGERPRINT_SCHEME, code_fingerprint


def _observer_module():
    product_root = Path(__file__).resolve().parents[4]
    path = product_root / "tests/observers/c93_same_pid_pytest.py"
    spec = importlib.util.spec_from_file_location("c93_observer_fixture", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _real_function(path, module_name, source):
    module_code = compile(source, str(path), "exec", dont_inherit=True)
    code = next(
        item
        for item in module_code.co_consts
        if isinstance(item, CodeType) and item.co_name == "observed"
    )
    return FunctionType(code, {"__name__": module_name})


def _record_real_calls(observer, function, *, repetitions=1):
    previous = sys.getprofile()
    try:
        sys.setprofile(observer.profile)
        for _ in range(repetitions):
            function()
    finally:
        sys.setprofile(previous)


def test_actual_called_code_matches_pinned_source_and_rejects_spoofed_body(tmp_path):
    owner = _observer_module()
    path = tmp_path / "src/polisyos/fixture.py"
    path.parent.mkdir(parents=True)
    original = b'def observed():\n    return "candidate alpha"\n'
    spoofed = b'def observed():\n    return "candidate beta"\n'
    original_function = _real_function(path, "polisyos.fixture", original)
    spoofed_function = _real_function(path, "polisyos.fixture", spoofed)
    assert type(original_function) is FunctionType
    assert type(spoofed_function) is FunctionType
    # This is the removal-control premise, not an assumption about bytecode layout.
    assert original_function.__code__.co_code == spoofed_function.__code__.co_code
    assert original_function() == "candidate alpha"
    assert spoofed_function() == "candidate beta"
    assert original_function() != spoofed_function()
    path.write_bytes(original)
    expected = {"src/polisyos/fixture.py": hashlib.sha256(original).hexdigest()}
    observer = owner.ExecutionObserver(
        tmp_path, expected, [], code_fingerprint, CODE_FINGERPRINT_SCHEME
    )
    _record_real_calls(observer, original_function, repetitions=2)
    _record_real_calls(observer, spoofed_function)
    rows = [
        row for row in observer.result()["executed_project_calls"] if row["qualname"] == "observed"
    ]
    assert len(rows) == 2
    good = next(row for row in rows if row["calls"] == 2)
    bad = next(row for row in rows if row["calls"] == 1)
    assert good["code_identity_scheme"] == CODE_FINGERPRINT_SCHEME
    assert good["source_code_binding"]["status"] == "matched_declared_source"
    assert bad["source_code_binding"]["status"] == "not_established"
    assert good["code_sha256"] != bad["code_sha256"]


def test_installed_project_origin_is_observed_and_unbound_while_third_party_is_excluded(tmp_path):
    owner = _observer_module()
    site = tmp_path / ".venv/lib/python3.14/site-packages"
    project = site / "polisyos/federation.py"
    third_party = site / "numpy/fixture.py"
    for path in (project, third_party):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("def observed():\n    return 1\n")
    observer = owner.ExecutionObserver(tmp_path, {}, [], code_fingerprint, CODE_FINGERPRINT_SCHEME)
    _record_real_calls(
        observer, _real_function(project, "polisyos.federation", project.read_bytes())
    )
    _record_real_calls(observer, _real_function(project, "aliased_module", project.read_bytes()))
    _record_real_calls(
        observer, _real_function(third_party, "numpy.fixture", third_party.read_bytes())
    )
    result = observer.result()
    project_rows = [row for row in result["executed_project_calls"] if row["path"] == str(project)]
    assert project_rows and sum(row["calls"] for row in project_rows) == 2
    assert all(row["source_code_binding"]["status"] == "not_established" for row in project_rows)
    assert str(project) in result["unbound_project_sources"]
    assert any(
        "installed project-origin candidate" in value for value in result["unobserved_boundaries"]
    )
    assert all(row["path"] != str(third_party) for row in result["executed_project_calls"])
    observer.audit("open", (str(third_party), "r", 0))
    assert str(third_party) not in observer.reads


def test_shared_helper_is_loaded_only_from_declared_matching_checkout_bytes():
    owner = _observer_module()
    product_root = Path(__file__).resolve().parents[4]
    helper = product_root / "tests/_helpers/code_identity.py"
    loaded_helper = Path(sys.modules[code_fingerprint.__module__].__file__).resolve()
    assert loaded_helper == helper.resolve()
    key = "tests/_helpers/code_identity.py"
    expected = {key: hashlib.sha256(helper.read_bytes()).hexdigest()}
    function, identity = owner._load_code_identity(product_root, expected)
    assert callable(function)
    assert identity["status"] == "matched_declared_source"
    assert identity["scheme"] == CODE_FINGERPRINT_SCHEME
    refused, refused_identity = owner._load_code_identity(product_root, {key: "0" * 64})
    assert refused is None
    assert refused_identity["status"] == "not_established"


def test_outside_checkout_project_origin_is_not_silently_discarded(tmp_path):
    owner = _observer_module()
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    origin = tmp_path / "other-install/polisyos/federation.py"
    origin.parent.mkdir(parents=True)
    source = b"def observed():\n    return 1\n"
    origin.write_bytes(source)
    observer = owner.ExecutionObserver(checkout, {}, [], code_fingerprint, CODE_FINGERPRINT_SCHEME)
    _record_real_calls(observer, _real_function(origin, "polisyos.federation", source))
    result = observer.result()
    row = next(row for row in result["executed_project_calls"] if row["path"] == str(origin))
    assert row["source_code_binding"]["status"] == "not_established"
    assert str(origin) in result["unbound_project_sources"]
    assert row["pid"] == os.getpid()


def test_unavailable_code_helper_records_unbound_actual_call(tmp_path):
    owner = _observer_module()
    path = tmp_path / "src/polisyos/fixture.py"
    path.parent.mkdir(parents=True)
    source = b"def observed():\n    return 1\n"
    path.write_bytes(source)
    expected = {"src/polisyos/fixture.py": hashlib.sha256(source).hexdigest()}
    observer = owner.ExecutionObserver(tmp_path, expected, [], None)
    _record_real_calls(observer, _real_function(path, "polisyos.fixture", source))
    row = next(
        row for row in observer.result()["executed_project_calls"] if row["qualname"] == "observed"
    )
    assert row["calls"] == 1
    assert row["code_sha256"] is None
    assert row["source_code_binding"]["status"] == "not_established"


def test_real_entrypoint_rejects_project_preimport_in_fresh_process(tmp_path):
    """The deciding entry, not the synthetic fixture constructor, enforces bootstrap."""
    product_root = Path(__file__).resolve().parents[4]
    observer = product_root / "tests/observers/c93_same_pid_pytest.py"
    helper = product_root / "tests/_helpers/code_identity.py"
    expected = tmp_path / "expected.json"
    import json

    expected.write_text(
        json.dumps(
            {"tests/_helpers/code_identity.py": hashlib.sha256(helper.read_bytes()).hexdigest()}
        )
    )
    cache = tmp_path / "empty-cache"
    cache.mkdir()
    receipt = tmp_path / "observer-receipt.json"
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "PYTHONPATH",
            "PYTHONHOME",
            "PYTEST_ADDOPTS",
            "PYTEST_PLUGINS",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
            "PYTHONPYCACHEPREFIX",
        }
        and not key.startswith(("E02_", "POLISYOS_"))
    }
    env["PYTHONPYCACHEPREFIX"] = str(cache)
    bootstrap = (
        "import runpy,sys,types; "
        "sys.modules['polisyos.synthetic_preimport'] = types.ModuleType('polisyos.synthetic_preimport'); "
        "sys.argv = sys.argv[1:]; runpy.run_path(sys.argv[0], run_name='__main__')"
    )
    command = [
        sys.executable,
        "-B",
        "-c",
        bootstrap,
        str(observer),
        "--receipt",
        str(receipt),
        "--project-root",
        str(product_root),
        "--expected-sources",
        str(expected),
        "--",
        "--version",
    ]
    run = subprocess.run(command, cwd=product_root, env=env, capture_output=True, check=False)
    (tmp_path / "guard-child.stdout").write_bytes(run.stdout)
    (tmp_path / "guard-child.stderr").write_bytes(run.stderr)
    (tmp_path / "guard-child.json").write_text(
        json.dumps({"argv": command, "returncode": run.returncode}) + "\n"
    )
    assert run.returncode != 0
    assert b"Product modules already imported before deciding observer" in run.stderr
    assert not receipt.exists()
