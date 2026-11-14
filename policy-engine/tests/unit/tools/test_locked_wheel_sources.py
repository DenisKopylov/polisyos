"""The host binds installed Python source to exact locked wheel members."""

from __future__ import annotations

import base64
import hashlib
import importlib
import io
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from tools import authority_bootstrap as host


def test_numpy_native_export_inside_host(request: pytest.FixtureRequest) -> None:
    """Observe a real native export without numerical execution or a broad seal."""
    node = f"{__file__}::test_numpy_native_export_inside_host"
    if node not in request.config.invocation_params.args:
        pytest.skip("requires the explicit fresh-host test invocation")

    session = sys.__dict__["_polisyos_loaded_host_v1"]
    assert session["profile"]["native_capture_scope"] == (
        "actually-loaded-locked-wheel-providers/1"
    )
    import numpy as np

    from polisyos.runtime.quality import confidence_ledger as ledger
    from polisyos.runtime.quality import n5_execution_basis as basis

    # The candidate reference binds actual recorder inputs, not optional-import
    # closure or the broader protected observation seal.
    assert ledger._LOADED_EXECUTION_OBSERVATION_SEAL is None
    assert ledger._candidate_n5_host_capture() is not None
    before = basis.snapshot_n5_callable_content_v3(np.random.default_rng)
    assert before is not None
    projection = json.loads(before)["nodes"][0]
    assert projection["kind"] == "recorded_native_export"
    binding = projection["binding"]
    assert binding["provider_module"] == "numpy.random._generator"
    assert binding["native_state_completeness"] == "not_established"
    assert binding["mapped_image_identity"] == "not_established"
    capture = session["capture"]
    native = capture.completed_native(binding["provider_module"])
    assert (
        binding["provider_file_sha256"]
        == hashlib.sha256(Path(native.spec.origin).read_bytes()).hexdigest()
    )
    assert session["profile"]["authority"] is False

    original_reader = session["locked_native_member"]
    calls = []

    def foreign_reader(module_name):
        calls.append(module_name)
        return original_reader(module_name)

    session["locked_native_member"] = foreign_reader
    try:
        assert basis.snapshot_n5_callable_content_v3(np.random.default_rng) is None
        assert calls == []
    finally:
        session["locked_native_member"] = original_reader
    assert basis.snapshot_n5_callable_content_v3(np.random.default_rng) == before

    # Remove the actual recorded native import, with image and callable held
    # fixed. A current namespace/name alone must no longer establish identity.
    events = capture._import_events[:]
    capture._import_events[:] = [
        event
        for event in events
        if not (
            event.provider_name == binding["provider_module"]
            and any(value is np.random.default_rng for value in event.retained_exports.values())
        )
    ]
    try:
        assert basis.snapshot_n5_callable_content_v3(np.random.default_rng) is None
    finally:
        capture._import_events[:] = events
    assert basis.snapshot_n5_callable_content_v3(np.random.default_rng) == before


def test_native_ledger_provider_inside_host(request: pytest.FixtureRequest) -> None:
    """The completed owner retains the validator's actual native provider."""
    node = f"{__file__}::test_native_ledger_provider_inside_host"
    if node not in request.config.invocation_params.args:
        pytest.skip("requires the explicit fresh-host test invocation")

    live_host = sys.modules["_polisyos_early_host"]
    session = sys.__dict__["_polisyos_loaded_host_v1"]
    assert session["phase"] == "collecting", session["last_owner_diagnostic"]
    module_name = "pydantic_core._pydantic_core"
    ledger = importlib.import_module("polisyos.runtime.quality.confidence_ledger")
    provider = importlib.import_module(module_name)
    rational = ledger.RationalSpec.model_validate({"numerator": 6, "denominator": 9})
    assert str(rational.fraction) == "2/3"
    with pytest.raises(ValueError, match="greater than 0"):
        ledger.RationalSpec.model_validate({"numerator": 6, "denominator": 0})

    live_host.handoff_if_ready()
    report = session["last_owner_diagnostic"]
    assert session["owner_capture_state"] == "retained", (
        report.get("failure"),
        report.get("capture_failure"),
    )
    native = report["native_validation_provider"]
    assert native["status"] == "reconciled_at_seal", (
        native,
        session["external_source_selector"].failure_for(module_name),
    )
    assert native["module"] == module_name
    assert native["file_sha256"] == hashlib.sha256(Path(provider.__file__).read_bytes()).hexdigest()
    assert native["lock_sha256"] == hashlib.sha256(Path("uv.lock").read_bytes()).hexdigest()
    assert report["protected_loaded_execution_status"] == "not_established"

    capture = session["capture"]
    current = ledger._check_loaded_execution_observation_currentness(capture)
    assert current["native_validation_provider_endpoint_currentness"] == "current_at_endpoint"
    assert current["protected_through_use"] == "not_established"

    # The native module, file, and validator class stay the same. The actual
    # consumer can now return an integer because its held validator changed.
    original = ledger.RationalSpec.__pydantic_validator__
    replacement = provider.SchemaValidator({"type": "int"})
    assert type(replacement) is type(original)
    ledger.RationalSpec.__pydantic_validator__ = replacement
    try:
        assert ledger.RationalSpec.model_validate(17) == 17
        live_host._check_owner_capture_at_endpoint(session, "native_provider_substitution")
        changed = session["last_owner_diagnostic"]
        assert changed["owner_observation_state"] == "failed", changed
        assert changed["held_binding_endpoint_failure"] == "locked_native_validator_binding_changed"
        assert changed["native_validation_provider_endpoint_currentness"] == "failed"
    finally:
        ledger.RationalSpec.__pydantic_validator__ = original
    assert (
        ledger._check_loaded_execution_observation_currentness(capture)["owner_observation_state"]
        == "failed"
    )


@pytest.mark.integration
def test_authority_launcher_retains_locked_native_ledger_provider() -> None:
    """Run real ledger validation and its removal control under the normal host."""
    wheel_directory = os.environ.get("POLISYOS_N6_PROVIDER_WHEEL_DIR")
    if wheel_directory is None:
        pytest.skip("requires retained pydantic-core and import-finder wheels selected by uv.lock")
    product = Path(__file__).resolve().parents[3]
    node = f"{__file__}::test_native_ledger_provider_inside_host"
    result = subprocess.run(
        [
            str(product / "tools/authority"),
            "--wheel-dir",
            str(Path(wheel_directory).resolve(strict=True)),
            "test",
            "--noconftest",
            "--assert=plain",
            "-q",
            node,
        ],
        cwd=product,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout, result.stdout + result.stderr


@pytest.mark.parametrize(
    "mode",
    [
        "normal",
        "unselected",
        "wrong_wheel",
        "removed",
        "replaced",
        "loader",
        "stdlib_loader",
        "stdlib_loader_code",
        "reload",
        "failed_load",
        "origin_callback",
        "file_callback",
        "changed_precreate",
        "precreate_loader_callback",
        "all_locked",
        "reference",
        "reference_missing_event",
        "reference_foreign_value",
        "reference_removed_image",
        "reference_unrelated_failed_importer",
    ],
)
def test_selected_native_member_tracks_actual_extension_load(tmp_path: Path, mode: str) -> None:
    """Observe a real extension against a bounded test wheel and refuse drift."""
    extension = next(
        (Path(sys.base_prefix) / "lib/python3.14/lib-dynload").glob("_ctypes_test*.so"), None
    )
    if extension is None:
        pytest.skip("the selected CPython does not provide the _ctypes_test extension")
    site = tmp_path / "site"
    site.mkdir()
    native = site / extension.name
    shutil.copyfile(extension, native)
    other_native = site / native.name.replace("_ctypes_test", "_dbm", 1)
    shutil.copyfile(extension, other_native)
    if mode == "failed_load":
        shutil.copyfile(native, tmp_path / "native.valid")
        native.write_bytes(b"invalid native image")
    info = site / "native_probe-1.0.dist-info"
    info.mkdir()
    metadata = b"Metadata-Version: 2.1\nName: native-probe\nVersion: 1.0\n\n"
    wheel_metadata = b"Wheel-Version: 1.0\nRoot-Is-Purelib: false\nTag: py3-none-any\n\n"
    (info / "METADATA").write_bytes(metadata)
    (info / "WHEEL").write_bytes(wheel_metadata)
    (info / "RECORD").write_text(f"{native.name},,\n{other_native.name},,\n", encoding="utf-8")
    archive_path = tmp_path / "native_probe-1.0-py3-none-any.whl"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.write(native, native.name)
        archive.write(other_native, other_native.name)
        archive.writestr("native_probe-1.0.dist-info/METADATA", metadata)
        archive.writestr("native_probe-1.0.dist-info/WHEEL", wheel_metadata)
    archive_bytes = archive_path.read_bytes()
    lock = (
        (
            '[[package]]\nname = "native-probe"\nversion = "1.0"\n'
            'wheels = [{ url = "https://example.invalid/native_probe-1.0-py3-none-any.whl", '
            f'hash = "sha256:{hashlib.sha256(archive_bytes).hexdigest()}", '
            f"size = {len(archive_bytes)} }}]\\n"
        )
        .replace("\\n", "\n")
        .encode()
    )
    (tmp_path / "lock.toml").write_bytes(lock)
    (tmp_path / "consumer.py").write_text(
        "import _ctypes_test\n"
        + (
            "from _ctypes_test import func as native_func\n" if mode.startswith("reference") else ""
        ),
        encoding="utf-8",
    )
    (tmp_path / "unrelated.py").write_text(
        "from _ctypes_test import func as native_func\nraise RuntimeError('fixture_failed')\n",
        encoding="utf-8",
    )
    product = Path(__file__).resolve().parents[3]
    script = r"""
import hashlib, importlib, importlib.machinery, pathlib, sys, types
product, root, mode = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3]
sys.path.insert(0, str(product))
from tools import authority_bootstrap as host
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
site = root / 'site'
archive = next(root.glob('*.whl')).read_bytes()
fetches = []
def fetch(url, size):
    fetches.append(url)
    return archive + (b'changed' if mode == 'wrong_wheel' else b'')
host._LockedWheelSourceSelector._archive_bytes = staticmethod(fetch)
selector = host._LockedWheelSourceSelector(root, site, (root / 'lock.toml').read_bytes())
consumer = root / 'consumer.py'
sources = {'consumer': ExpectedSource('consumer.py', hashlib.sha256(consumer.read_bytes()).hexdigest())}
if mode == 'reference_unrelated_failed_importer':
    unrelated = root / 'unrelated.py'
    sources['unrelated'] = ExpectedSource('unrelated.py', hashlib.sha256(unrelated.read_bytes()).hexdigest())
capture = SourceExecutionCapture(
    root, sources,
    exports={'consumer': {'_ctypes_test', 'native_func'}},
    external_native_selector=selector.select_native,
    external_native_modules=frozenset({'_dbm'} if mode in ('unselected', 'all_locked') else {'_ctypes_test'}),
    external_source_root=site,
    external_native_profile='locked_wheel_providers' if mode == 'all_locked' else 'selected_modules',
)
capture.install()
sys.path[:0] = [str(root), str(site)]
if mode == 'reference_unrelated_failed_importer':
    try:
        import unrelated
    except RuntimeError as exc:
        assert str(exc) == 'fixture_failed'
    else:
        raise AssertionError('fixture initializer unexpectedly succeeded')
if mode in ('changed_precreate', 'precreate_loader_callback'):
    spec = importlib.util.find_spec('_ctypes_test')
    assert spec is not None
    if mode == 'changed_precreate':
        spec.origin = str(next(site.glob('_dbm*.so')))
    else:
        class Canary:
            def __fspath__(self):
                raise AssertionError('verification called candidate __fspath__')
        spec.loader._loader.path = Canary()
    spec.loader.create_module(spec)
    assert capture._module_failures['_ctypes_test'] == 'native_selected_file_mismatch'
    raise SystemExit(0)
if mode == 'failed_load':
    try:
        import consumer
    except ImportError:
        pass
    else:
        raise AssertionError('invalid native image loaded')
    assert capture._module_failures['_ctypes_test'] == 'native_initialization_failed'
    next(site.glob('_ctypes_test*.so')).write_bytes((root / 'native.valid').read_bytes())
    import consumer
    try:
        capture.completed_native('_ctypes_test')
    except CaptureError:
        pass
    else:
        raise AssertionError('native failure was erased by retry')
    raise SystemExit(0)
import consumer
if mode in ('unselected', 'wrong_wheel'):
    try:
        capture.completed_native('_ctypes_test')
    except CaptureError as exc:
        assert str(exc) == 'native_module_not_completed'
    else:
        raise AssertionError('unselected extension was captured')
    if mode == 'wrong_wheel':
        assert selector.failure_for('_ctypes_test') == 'provider_wheel_digest_mismatch'
else:
    record = capture.completed_native('_ctypes_test')
    assert record.module is consumer._ctypes_test
    assert isinstance(record.spec.loader, importlib.machinery.ExtensionFileLoader)
    assert pathlib.Path(record.spec.loader.get_filename('_ctypes_test')).resolve() == pathlib.Path(record.spec.origin).resolve()
    assert record.file_sha256 == hashlib.sha256(pathlib.Path(record.spec.origin).read_bytes()).hexdigest()
    capture.assert_retained(frozenset({'consumer'}))
    if mode.startswith('reference'):
        reference = capture.completed_native_export_reference(consumer.native_func)
        assert reference.importer is capture.completed('consumer')
        assert reference.importer_export == 'native_func'
        assert reference.provider is record and reference.provider_export == 'func'
        if mode == 'reference_missing_event':
            original_events = capture._import_events[:]
            capture._import_events.clear()
            try:
                capture.completed_native_export_reference(consumer.native_func)
            except CaptureError as exc:
                assert str(exc) == 'native_export_binding_not_recorded'
            else:
                raise AssertionError('native reference survived event removal')
            capture._import_events.extend(original_events)
            assert capture.completed_native_export_reference(consumer.native_func).provider is record
        elif mode == 'reference_foreign_value':
            def replacement(): pass
            replacement.__name__ = 'func'
            replacement.__module__ = '_ctypes_test'
            try:
                capture.completed_native_export_reference(replacement)
            except CaptureError as exc:
                assert str(exc) == 'native_export_binding_not_recorded'
            else:
                raise AssertionError('same-name foreign native export accepted')
        elif mode == 'reference_removed_image':
            path = pathlib.Path(record.spec.origin)
            backup = path.with_name(path.name + '.held')
            path.rename(backup)
            try:
                capture.completed_native_export_reference(consumer.native_func)
            except CaptureError as exc:
                assert str(exc) == 'native_module_changed'
            else:
                raise AssertionError('native reference survived native-image removal')
            finally:
                backup.rename(path)
    if mode == 'normal':
        assert selector.select_native('_ctypes_test', record.spec.origin, _retained_only=True) == (
            record.relative_path, record.file_sha256
        )
        other = next(site.glob('_dbm*.so'))
        assert selector.select_native('_dbm', str(other)) is not None
        assert len(fetches) == 1
        capture.close()
        assert not capture._native_completed and not capture._native_anchors
        assert capture._external_native_selector is None and not capture._external_native_modules
        try:
            capture.completed_native('_ctypes_test')
        except CaptureError:
            pass
        else:
            raise AssertionError('closed native capture remained available')
    if mode == 'removed':
        path = pathlib.Path(record.spec.origin)
        backup = path.with_name(path.name + '.held')
        path.rename(backup)
    elif mode == 'replaced':
        original = sys.modules['_ctypes_test']
        sys.modules['_ctypes_test'] = types.ModuleType('_ctypes_test')
    elif mode == 'loader':
        type(record.loader).create_module = lambda self, spec: None
    elif mode == 'stdlib_loader':
        importlib.machinery.ExtensionFileLoader.exec_module = lambda self, module: None
    elif mode == 'stdlib_loader_code':
        def changed_exec(self, module):
            return None
        importlib.machinery.ExtensionFileLoader.exec_module.__code__ = changed_exec.__code__
    elif mode in ('origin_callback', 'file_callback'):
        class Canary:
            def __str__(self):
                raise AssertionError('verification called candidate __str__')
        if mode == 'origin_callback':
            record.spec.origin = Canary()
        else:
            record.module.__file__ = Canary()
    elif mode == 'reload':
        importlib.reload(record.module)
    if mode in ('removed', 'replaced', 'loader', 'stdlib_loader', 'stdlib_loader_code', 'reload', 'origin_callback', 'file_callback'):
        try:
            capture.completed_native('_ctypes_test')
        except CaptureError as exc:
            assert str(exc) == ('native_module_not_completed' if mode == 'reload' else 'native_module_changed')
        else:
            raise AssertionError('changed extension observation was accepted')
        if mode == 'removed':
            backup.rename(path)
        elif mode == 'replaced':
            sys.modules['_ctypes_test'] = original
        try:
            capture.completed_native('_ctypes_test')
        except CaptureError:
            pass
        else:
            raise AssertionError('restoration erased native capture refusal')
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", script, str(product), str(tmp_path), mode],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def _distribution(
    root: Path, *, finder: bool = False, pending_lookup: bool = False
) -> tuple[Path, Path, bytes, bytes]:
    site = root / "site"
    package = site / "sample_provider"
    info = site / "sample_provider-1.0.dist-info"
    package.mkdir(parents=True)
    info.mkdir()
    source = (
        b"import sys\nfrom .base import Base\nclass Finder(Base): pass\n"
        b"finder = Finder()\nsys.meta_path.append(finder)\nvalue = 7\n"
        if finder
        else b"from importlib.machinery import PathFinder\n"
        b"during_initialization = PathFinder().find_spec(__name__)\nvalue = 7\n"
        if pending_lookup
        else b"value = 7\n"
    )
    base_source = (
        b"class Base:\n"
        b"    @staticmethod\n"
        b"    def find_spec(fullname, path=None, target=None): return None\n"
        b"    @staticmethod\n"
        b"    def substitute(fullname, path=None, target=None): return 'changed'\n"
    )
    metadata = b"Metadata-Version: 2.1\nName: sample-provider\nVersion: 1.0\n\n"
    wheel = b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n\n"
    (package / "__init__.py").write_bytes(source)
    (info / "METADATA").write_bytes(metadata)
    (info / "WHEEL").write_bytes(wheel)
    record = "sample_provider/__init__.py,,\n"
    if finder:
        (package / "base.py").write_bytes(base_source)
        record += "sample_provider/base.py,,\n"
    (info / "RECORD").write_text(record, encoding="utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("sample_provider/__init__.py", source)
        if finder:
            archive.writestr("sample_provider/base.py", base_source)
        archive.writestr("sample_provider-1.0.dist-info/METADATA", metadata)
        archive.writestr("sample_provider-1.0.dist-info/WHEEL", wheel)
    content = buffer.getvalue()
    digest = hashlib.sha256(content).hexdigest()
    lock = (
        '[[package]]\nname = "sample-provider"\nversion = "1.0"\n'
        'wheels = [{ url = "https://example.invalid/sample_provider-1.0-py3-none-any.whl", '
        f'hash = "sha256:{digest}", size = {len(content)} }}]\n'
    ).encode()
    return site, package / "__init__.py", lock, content


def test_locked_wheel_selects_exact_installed_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    site, source, lock, content = _distribution(tmp_path)
    calls: list[str] = []

    def fetch(url: str, size: int) -> bytes:
        calls.append(url)
        assert size == len(content)
        return content

    monkeypatch.setattr(host._LockedWheelSourceSelector, "_archive_bytes", staticmethod(fetch))
    selector = host._LockedWheelSourceSelector(tmp_path, site, lock)
    expected = ("site/sample_provider/__init__.py", hashlib.sha256(source.read_bytes()).hexdigest())
    assert selector.select("sample_provider", str(source)) == expected
    assert selector.select("sample_provider", str(source)) == expected
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("mode", "failure"),
    [
        ("matched", None),
        ("missing", "provider_local_wheel_unavailable"),
        ("wrong_size", "provider_wheel_size_mismatch"),
        ("same_name", "provider_wheel_digest_mismatch"),
    ],
)
def test_authority_launcher_reconciles_an_explicit_retained_wheel(
    tmp_path: Path, mode: str, failure: str | None
) -> None:
    """The real launcher supplies only completed, hash-bound local provider members."""
    original_product = Path(__file__).resolve().parents[3]
    root = tmp_path.resolve()
    product = root / "policy-engine"
    site, provider_source, lock, content = _distribution(product)
    member_sha256 = hashlib.sha256(provider_source.read_bytes()).hexdigest()
    venv = product / ".venv"
    python = venv / "bin/python"
    python.parent.mkdir(parents=True)
    interpreter = Path(sys.executable).resolve()
    python.symlink_to(interpreter)
    (venv / "pyvenv.cfg").write_text(
        f"home = {interpreter.parent}\ninclude-system-site-packages = false\n",
        encoding="utf-8",
    )
    install_site = venv / "lib/python3.14/site-packages"
    install_site.parent.mkdir(parents=True)
    site.rename(install_site)
    retained = root / "retained wheels"
    retained.mkdir()
    archive = retained / "sample_provider-1.0-py3-none-any.whl"
    if mode == "matched":
        archive.write_bytes(content)
    elif mode == "wrong_size":
        archive.write_bytes(content + b"!")
    elif mode == "same_name":
        archive.write_bytes(bytes([content[0] ^ 1]) + content[1:])

    fixture_source = {
        "src/polisyos/__init__.py": "",
        "src/polisyos/runtime/quality/confidence_ledger.py": "",
        "tools/__init__.py": "",
        "tools/ops_runners/__init__.py": "",
        "tools/ops_runners/runtime_cli.py": r"""
import importlib
import importlib.util
import json
import sys
import urllib.request
from pathlib import Path


def main(argv):
    network_calls = []

    def unexpected_network(*args, **kwargs):
        network_calls.append(True)
        raise AssertionError("retained-wheel mode attempted network transport")

    urllib.request.urlopen = unexpected_network
    session = sys.__dict__["_polisyos_loaded_host_v1"]
    read_member = session["locked_python_member"]
    assert importlib.util.find_spec("sample_provider") is not None
    lookup_only = read_member("sample_provider")
    provider = importlib.import_module("sample_provider")
    member = read_member("sample_provider")
    selector = session["external_source_selector"]
    failure = selector.failure_for("sample_provider")
    if member is not None:
        session["external_source_selector"] = object()
        assert read_member("sample_provider") is None
        session["external_source_selector"] = selector
        selected = selector._selected["sample_provider"]
        wheel_key = next(
            key for key, row in selector._wheels.items() if row and row[0] == member[3]
        )
        wheel = selector._wheels[wheel_key]
        forged = "sha256:" + "0" * 64
        selector._selected["sample_provider"] = (*selected[:2], forged)
        selector._wheels[wheel_key] = (forged, wheel[1])
        assert read_member("sample_provider") is None
        selector._wheels[wheel_key] = wheel
        selector._selected["sample_provider"] = selected
        assert read_member("sample_provider") == member
        lock = Path("uv.lock")
        original_lock = lock.read_bytes()
        lock.write_bytes(original_lock + b"\n")
        assert read_member("sample_provider") is None
        lock.write_bytes(original_lock)
        assert read_member("sample_provider") == member
        source = Path(provider.__file__)
        source.write_bytes(b"value = 8\n")
        assert read_member("sample_provider") is None
    print(json.dumps({
        "value": provider.value,
        "member": member,
        "failure": failure,
        "lookup_only": lookup_only,
        "network_calls": network_calls,
        "authority": session["profile"]["authority"],
        "argv": argv,
    }))
""",
        "pyproject.toml": "",
    }
    for relative, body in fixture_source.items():
        path = product / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    (product / "uv.lock").write_bytes(lock)
    launcher_paths = (
        "tools/authority",
        "tools/authority_bootstrap.py",
        "tools/loaded_execution_capture.py",
    )
    for relative in launcher_paths:
        shutil.copy2(original_product / relative, product / relative)
    git = ["/usr/bin/git", "-C", str(root)]
    git_env = host._git_environment()
    subprocess.run([*git, "init", "-q"], env=git_env, check=True, capture_output=True, timeout=10)
    tracked = [str(product / name) for name in (*fixture_source, "uv.lock", *launcher_paths)]
    subprocess.run(
        [*git, "add", "--", *tracked], env=git_env, check=True, capture_output=True, timeout=10
    )
    subprocess.run(
        [
            *git,
            "-c",
            "user.name=Wheel Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "Select launcher and locked input",
        ],
        env=git_env,
        check=True,
        capture_output=True,
        timeout=10,
    )
    result = subprocess.run(
        [str(product / "tools/authority"), "--wheel-dir", str(retained), "runtime", "probe"],
        capture_output=True,
        text=True,
        check=False,
        timeout=25,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    expected_member = [
        "sample_provider",
        ".venv/lib/python3.14/site-packages/sample_provider/__init__.py",
        member_sha256,
        f"sha256:{hashlib.sha256(content).hexdigest()}",
        hashlib.sha256(lock).hexdigest(),
    ]
    assert json.loads(result.stdout) == {
        "value": 7,
        "member": expected_member if failure is None else None,
        "failure": failure,
        "lookup_only": None,
        "network_calls": [],
        "authority": False,
        "argv": ["probe"],
    }


@pytest.mark.parametrize(
    "mode",
    [
        "positive",
        "consumer",
        "provider",
        "pre_event",
        "pre_event_remove_guard",
        "late",
        "source",
        "unselected",
        "remove_guard",
    ],
)
def test_dynamic_wheel_import_binding_uses_actual_anchored_events(
    tmp_path: Path, mode: str
) -> None:
    """Bind the observed wheel provider, facade and consumer without guessing exports."""
    site = tmp_path / "site"
    package = site / "sample_provider"
    info = site / "sample_provider-1.0.dist-info"
    package.mkdir(parents=True)
    info.mkdir()
    sources = {
        "sample_provider/__init__.py": b"from .base import Capability\n",
        "sample_provider/base.py": b"class Capability: pass\n",
    }
    metadata = b"Metadata-Version: 2.1\nName: sample-provider\nVersion: 1.0\n\n"
    wheel = b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n\n"
    for name, content in sources.items():
        (site / name).write_bytes(content)
    (info / "METADATA").write_bytes(metadata)
    (info / "WHEEL").write_bytes(wheel)
    (info / "RECORD").write_text("".join(f"{name},,\n" for name in sources))
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        for name, content in sources.items():
            archive.writestr(name, content)
        archive.writestr("sample_provider-1.0.dist-info/METADATA", metadata)
        archive.writestr("sample_provider-1.0.dist-info/WHEEL", wheel)
    content = archive_buffer.getvalue()
    lock = (
        '[[package]]\nname = "sample-provider"\nversion = "1.0"\n'
        'wheels = [{ url = "https://example.invalid/sample_provider-1.0-py3-none-any.whl", '
        f'hash = "sha256:{hashlib.sha256(content).hexdigest()}", size = {len(content)} }}]\n'
    ).encode()
    consumer = tmp_path / "consumer.py"
    consumer.write_text(
        (
            "import sample_provider\nsample_provider.Capability = object()\n"
            if mode in ("pre_event", "pre_event_remove_guard")
            else ""
        )
        + "from sample_provider import Capability as Selected\n"
        "def later():\n"
        "    from sample_provider import Capability as Selected\n"
        "    return Selected\n"
    )
    product = Path(__file__).resolve().parents[3]
    script = r"""
import __future__, ast, base64, hashlib, pathlib, sys, types, typing
product, root, archive, lock, mode = sys.argv[1:]
product, root = pathlib.Path(product), pathlib.Path(root)
sys.path.insert(0, str(product))
from tools import authority_bootstrap as host
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
host._LockedWheelSourceSelector._archive_bytes = staticmethod(lambda url, size: base64.b64decode(archive))
selector = host._LockedWheelSourceSelector(root, root / 'site', base64.b64decode(lock))
source = root / 'consumer.py'
capture = SourceExecutionCapture(root, {
    'consumer': ExpectedSource('consumer.py', hashlib.sha256(source.read_bytes()).hexdigest())
}, external_source_selector=(lambda name, path: None) if mode == 'unselected' else selector.select)
capture.install()
sys.path[:0] = [str(root), str(root / 'site')]
import consumer
graph = capture.relevant_graph(frozenset({'consumer'}))
source_file = product / 'src/polisyos/runtime/quality/confidence_ledger.py'
tree = ast.parse(source_file.read_bytes(), filename=str(source_file))
names = {'_passive_capture_lookup', '_source_import_aliases_for_event', '_observed_source_bindings'}
functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
scope = {'ast': ast, 'hashlib': hashlib, 'types': types, 'Path': pathlib.Path,
         'Iterable': typing.Iterable, 'Mapping': typing.Mapping, 'Any': typing.Any,
         'cast': typing.cast, '_NO_EXECUTION_BINDING': object()}
exec(compile(ast.Module(body=functions, type_ignores=[]), str(source_file), 'exec',
             flags=__future__.annotations.compiler_flag, dont_inherit=True), scope)
observe = scope['_observed_source_bindings']
if mode == 'unselected':
    bindings, _ = observe(root, capture, graph)
    assert not bindings and 'sample_provider' in graph.external_providers
    raise SystemExit(0)
bindings, disagreements = observe(root, capture, graph)
if mode in ('pre_event', 'pre_event_remove_guard'):
    assert ('sample_provider', 'Capability', 'consumer', 'Selected') in disagreements
    event = next(event for event in capture.import_events()
                 if event.importer_name == 'consumer' and event.provider_name == 'sample_provider'
                 and event.requested_exports == ('Capability',))
    if mode == 'pre_event_remove_guard':
        capture.completed_binding = lambda *args: consumer.Selected
    try:
        capture.assert_import_binding(event, importer_attribute='Selected', provider_export='Capability')
    except CaptureError as exc:
        assert str(exc) == 'retained_export_changed'
    else:
        raise AssertionError('pre-event provider mutation accepted')
    assert capture.failed
    raise SystemExit(0)
assert not disagreements
assert any(row[0] == 'sample_provider.base' and row[1] == 'Capability'
           and ('sample_provider', 'Capability') in row[3] for row in bindings)
assert any(row[0] == 'sample_provider' and row[1] == 'Capability'
           and ('consumer', 'Selected') in row[3] for row in bindings)
event = next(event for event in capture.import_events()
             if event.importer_name == 'consumer' and event.provider_name == 'sample_provider')
if mode == 'remove_guard': capture.assert_import_binding = lambda *args, **kwargs: None
if mode in ('consumer', 'remove_guard'): consumer.Selected = object()
if mode == 'provider': sys.modules['sample_provider'].Capability = object()
if mode in ('consumer', 'provider', 'remove_guard'):
    try:
        capture.assert_import_binding(event, importer_attribute='Selected', provider_export='Capability')
    except CaptureError as exc:
        assert str(exc) == ('retained_export_changed' if mode == 'provider' else 'import_event_binding_changed')
    else:
        raise AssertionError('changed binding accepted')
    assert capture.failed
if mode == 'late':
    consumer.later()
    late = [event for event in capture.import_events() if event.importer_name == 'consumer'
            and event.provider_name == 'sample_provider'][-1]
    try:
        capture.assert_import_binding(late, importer_attribute='Selected', provider_export='Capability')
    except CaptureError as exc:
        assert str(exc) == 'import_event_binding_unresolved'
    else:
        raise AssertionError('late event accepted')
if mode == 'source':
    path = root / 'site/sample_provider/base.py'
    path.write_bytes(path.read_bytes() + b'# changed\n')
    try:
        observe(root, capture, graph)
    except ValueError as exc:
        assert str(exc) == 'importer_source_observation_mismatch' or str(exc) == 'executed_source_observation_mismatch'
    else:
        raise AssertionError('changed provider source accepted')
"""
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            "-c",
            script,
            str(product),
            str(tmp_path),
            base64.b64encode(content).decode(),
            base64.b64encode(lock).decode(),
            mode,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    if mode in ("remove_guard", "pre_event_remove_guard"):
        assert result.returncode != 0
        expected = (
            "pre-event provider mutation accepted"
            if mode == "pre_event_remove_guard"
            else "changed binding accepted"
        )
        assert expected in result.stderr
    else:
        assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("mutation", ["installed_source", "archive_digest", "record_owner"])
def test_locked_wheel_refusal_is_sticky_after_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    site, source, lock, content = _distribution(tmp_path)
    original = source.read_bytes()
    record = site / "sample_provider-1.0.dist-info/RECORD"
    original_record = record.read_bytes()
    selected_content = content
    if mutation == "installed_source":
        source.write_bytes(b"value = 99\n")
    elif mutation == "archive_digest":
        selected_content += b"changed"
    else:
        record.write_text("other.py,,\n", encoding="utf-8")

    monkeypatch.setattr(
        host._LockedWheelSourceSelector,
        "_archive_bytes",
        staticmethod(lambda url, size: selected_content),
    )
    selector = host._LockedWheelSourceSelector(tmp_path, site, lock)
    assert selector.select("sample_provider", str(source)) is None
    expected_reason = {
        "installed_source": "provider_installed_source_mismatch",
        "archive_digest": "provider_wheel_digest_mismatch",
        "record_owner": "provider_distribution_owner_unavailable",
    }[mutation]
    assert selector.failure_for("sample_provider") == expected_reason
    source.write_bytes(original)
    record.write_bytes(original_record)
    selected_content = content
    assert selector.select("sample_provider", str(source)) is None
    assert selector.failure_for("sample_provider") == expected_reason


def test_selected_wheel_source_drift_remains_refused_after_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    site, source, lock, content = _distribution(tmp_path)
    monkeypatch.setattr(
        host._LockedWheelSourceSelector,
        "_archive_bytes",
        staticmethod(lambda url, size: content),
    )
    selector = host._LockedWheelSourceSelector(tmp_path, site, lock)
    original = source.read_bytes()
    assert selector.select("sample_provider", str(source)) is not None
    source.write_bytes(b"value = 8\n")
    assert selector.select("sample_provider", str(source)) is None
    source.write_bytes(original)
    assert selector.select("sample_provider", str(source)) is None


def test_locked_provider_under_selected_symlinked_site_is_captured(tmp_path: Path) -> None:
    """The selected checkout may reuse a venv without copying its provider files."""
    shared = tmp_path / "shared"
    shared.mkdir()
    real_site, source, lock, content = _distribution(shared)
    root = tmp_path / "checkout"
    root.mkdir()
    alias = root / "site"
    alias.symlink_to(real_site, target_is_directory=True)
    (real_site / "sample_provider/relocated.py").symlink_to(source)
    consumer = root / "consumer.py"
    consumer.write_text("from sample_provider import value\n", encoding="utf-8")
    product = Path(__file__).resolve().parents[3]
    script = r"""
import base64, hashlib, json, pathlib, sys
product, root, archive, lock, mode = sys.argv[1:]
root = pathlib.Path(root)
site = root / 'site'
sys.path.insert(0, product)
from tools import authority_bootstrap as host
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
host._LockedWheelSourceSelector._archive_bytes = staticmethod(lambda url, size: base64.b64decode(archive))
selector = host._LockedWheelSourceSelector(root, site, base64.b64decode(lock))
assert selector.select('sample_provider.relocated', str(site / 'sample_provider/relocated.py')) is None
assert selector.failure_for('sample_provider.relocated') == 'provider_source_origin_invalid'
source = root / 'consumer.py'
capture = SourceExecutionCapture(root, {
    'consumer': ExpectedSource('consumer.py', hashlib.sha256(source.read_bytes()).hexdigest())
}, external_source_selector=selector.select, external_source_root=site)
if mode == 'remove_nested_guard':
    capture._selected_path = lambda expected: (root / expected.relative_path).resolve()
nested = ExpectedSource('site/sample_provider/relocated.py', hashlib.sha256(source.read_bytes()).hexdigest())
try:
    capture._selected_path(nested)
except ValueError:
    pass
else:
    raise AssertionError('nested provider symlink was admitted')
capture.install()
sys.path[:0] = [str(root), str(site)]
import consumer
assert consumer.value == 7
capture.assert_retained(frozenset({'consumer', 'sample_provider'}))
record = capture.completed('sample_provider')
assert record.relative_path == 'site/sample_provider/__init__.py'
provider = sys.modules['sample_provider']
assert record.origin == str(site / 'sample_provider/__init__.py')
print(json.dumps([provider.__file__, provider.__spec__.origin, provider.__loader__.path,
                  provider.__path__, provider.__spec__.submodule_search_locations]))
if mode == 'remove_alias_currentness':
    capture._selected_path = lambda expected: root / expected.relative_path
original_resolve = pathlib.Path.resolve
def changed_alias(self, *args, **kwargs):
    if self == site / 'sample_provider/__init__.py':
        return self
    return original_resolve(self, *args, **kwargs)
pathlib.Path.resolve = changed_alias
try:
    capture.assert_retained(frozenset({'consumer', 'sample_provider'}))
except CaptureError as exc:
    assert str(exc) == 'retained_module_changed'
else:
    raise AssertionError('changed selected site target was accepted')
finally:
    pathlib.Path.resolve = original_resolve
assert capture.failed
try:
    capture.assert_retained(frozenset({'consumer', 'sample_provider'}))
except CaptureError:
    pass
else:
    raise AssertionError('restored site target erased failure')
"""
    baseline_script = r"""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(sys.argv[1]) / 'site'))
import sample_provider as provider
print(json.dumps([provider.__file__, provider.__spec__.origin, provider.__loader__.path,
                  provider.__path__, provider.__spec__.submodule_search_locations]))
"""
    baseline = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", baseline_script, str(root)],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert baseline.returncode == 0, baseline.stderr
    for mode in ("normal", "remove_nested_guard", "remove_alias_currentness"):
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "-B",
                "-c",
                script,
                str(product),
                str(root),
                base64.b64encode(content).decode(),
                base64.b64encode(lock).decode(),
                mode,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
        if mode == "remove_nested_guard":
            print(f"nested symlink guard removal exit: {result.returncode}")
            print(result.stderr, end="")
            assert result.returncode != 0
            assert "nested provider symlink was admitted" in result.stderr
        elif mode == "remove_alias_currentness":
            print(f"site target currentness removal exit: {result.returncode}")
            print(result.stderr, end="")
            assert result.returncode != 0
            assert "changed selected site target was accepted" in result.stderr
        else:
            assert result.returncode == 0, result.stderr
            assert json.loads(result.stdout) == json.loads(baseline.stdout)


def test_real_import_captures_locked_provider_and_refuses_mutation(tmp_path: Path) -> None:
    """A source-bound external finder remains held across the actual import."""
    _, _, lock, content = _distribution(tmp_path, finder=True)
    consumer = tmp_path / "consumer.py"
    consumer.write_text("from sample_provider import value\n", encoding="utf-8")
    product = Path(__file__).resolve().parents[3]
    script = r"""
import base64, hashlib, importlib, pathlib, sys
product, root, archive, lock, mode = sys.argv[1:]
root = pathlib.Path(root)
sys.path.insert(0, product)
from tools import authority_bootstrap as host
from tools import loaded_execution_capture as recorder
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
host._LockedWheelSourceSelector._archive_bytes = staticmethod(lambda url, size: base64.b64decode(archive))
selector = host._LockedWheelSourceSelector(root, root / 'site', base64.b64decode(lock))
consumer = root / 'consumer.py'
capture = SourceExecutionCapture(root, {
    'consumer': ExpectedSource('consumer.py', hashlib.sha256(consumer.read_bytes()).hexdigest())
}, external_source_selector=selector.select)
capture.install()
if mode == 'remove_capture':
    capture._external_finder.find_spec = lambda *args: recorder._FIND_SPEC(*args)
sys.path[:0] = [str(root), str(root / 'site')]
path = root / 'site/sample_provider/__init__.py'
original = path.read_bytes()
if mode == 'changed_bytes':
    path.write_bytes(original.replace(b'value = 7', b'value = 8'))
try:
    assert importlib.util.find_spec('sample_provider') is not None
    assert 'sample_provider' not in sys.modules
    import consumer
finally:
    if mode == 'changed_bytes':
        path.write_bytes(original)
if mode == 'changed_bytes':
    assert consumer.value == 8
    assert selector.failure_for('sample_provider') == 'provider_installed_source_mismatch'
    assert capture.failed and capture.failure_reason == 'capture_finder_unqualified'
    try:
        capture.assert_retained(frozenset({'consumer'}))
    except CaptureError:
        pass
    else:
        raise AssertionError('restoring changed provider bytes erased capture failure')
else:
    assert consumer.value == 7
    required = frozenset({'consumer', 'sample_provider', 'sample_provider.base'})
    capture.assert_retained(required)
    graph = capture.relevant_graph(frozenset({'consumer'}))
    assert required.issubset(graph.reached_sources)
    if mode == 'reimport':
        original_module = sys.modules.pop('sample_provider')
        importlib.import_module('sample_provider')
        assert capture.failed and capture.failure_reason == 'capture_finder_state_changed'
        sys.modules['sample_provider'] = original_module
        try:
            capture.assert_retained(required)
        except CaptureError:
            assert capture.failed
        else:
            raise AssertionError('restored provider erased reimport failure')
        raise SystemExit(0)
    from sample_provider.base import Base
    original_code = Base.find_spec.__code__
    Base.find_spec.__code__ = Base.substitute.__code__
    try:
        capture.assert_retained(required)
    except CaptureError as exc:
        assert str(exc) == 'capture_finder_state_changed'
    else:
        raise AssertionError('changed provider method was accepted')
    finally:
        Base.find_spec.__code__ = original_code
    assert capture.failed
    try:
        capture.assert_retained(required)
    except CaptureError:
        pass
    else:
        raise AssertionError('restoring provider method erased capture failure')
"""
    for mode in ("normal", "changed_bytes", "reimport", "remove_capture"):
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "-B",
                "-c",
                script,
                str(product),
                str(tmp_path),
                base64.b64encode(content).decode(),
                base64.b64encode(lock).decode(),
                mode,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
        if mode == "remove_capture":
            print(f"external capture removal exit: {result.returncode}")
            print(result.stderr, end="")
            assert result.returncode != 0
            assert "capture_incomplete" in result.stderr
        else:
            assert result.returncode == 0, f"{mode}: {result.stderr}"


def test_executed_locked_source_cannot_be_reimported(tmp_path: Path) -> None:
    """A completed provider cannot be recaptured by a later reimport."""
    _, _, lock, content = _distribution(tmp_path)
    source = tmp_path / "consumer.py"
    source.write_text("from sample_provider import value\n", encoding="utf-8")
    product = Path(__file__).resolve().parents[3]
    script = r"""
import base64, hashlib, importlib, pathlib, sys
product, root, archive, lock = sys.argv[1:]
root = pathlib.Path(root)
sys.path.insert(0, product)
from tools import authority_bootstrap as host
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
host._LockedWheelSourceSelector._archive_bytes = staticmethod(lambda url, size: base64.b64decode(archive))
selector = host._LockedWheelSourceSelector(root, root / 'site', base64.b64decode(lock))
source = root / 'consumer.py'
capture = SourceExecutionCapture(root, {
    'consumer': ExpectedSource('consumer.py', hashlib.sha256(source.read_bytes()).hexdigest())
}, external_source_selector=selector.select)
capture.install()
sys.path[:0] = [str(root), str(root / 'site')]
assert importlib.util.find_spec('sample_provider') is not None
import consumer
required = frozenset({'consumer', 'sample_provider'})
capture.assert_retained(required)
original = sys.modules.pop('sample_provider')
replacement = importlib.import_module('sample_provider')
assert replacement.value == 7
assert capture._module_failures['sample_provider'] == 'module_reload_not_admitted'
sys.modules['sample_provider'] = original
try:
    capture.assert_retained(required)
except CaptureError as exc:
    assert str(exc) == 'required_module_initialization_failed'
else:
    raise AssertionError('completed provider reimport was accepted')
assert capture.failed
try:
    capture.assert_retained(required)
except CaptureError:
    pass
else:
    raise AssertionError('restored provider erased reimport failure')
"""
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            "-c",
            script,
            str(product),
            str(tmp_path),
            base64.b64encode(content).decode(),
            base64.b64encode(lock).decode(),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "mode",
    ["lookup", "pending", "direct_exec", "reload"],
)
def test_completed_wheel_provider_distinguishes_lookup_from_execution(
    tmp_path: Path, mode: str
) -> None:
    """A real PathFinder lookup stays guarded without replaying the provider."""
    _, _, lock, content = _distribution(tmp_path, pending_lookup=mode == "pending")
    consumer = tmp_path / "consumer.py"
    consumer.write_text("from sample_provider import value\n", encoding="utf-8")
    product = Path(__file__).resolve().parents[3]
    script = r"""
import base64, hashlib, importlib, importlib.machinery, pathlib, sys
product, root, archive, lock, mode = sys.argv[1:]
root = pathlib.Path(root)
sys.path.insert(0, product)
from tools import authority_bootstrap as host
from tools import loaded_execution_capture as recorder
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture
host._LockedWheelSourceSelector._archive_bytes = staticmethod(lambda url, size: base64.b64decode(archive))
selector = host._LockedWheelSourceSelector(root, root / 'site', base64.b64decode(lock))
consumer = root / 'consumer.py'
capture = SourceExecutionCapture(root, {
    'consumer': ExpectedSource('consumer.py', hashlib.sha256(consumer.read_bytes()).hexdigest())
}, external_source_selector=selector.select)
capture.install()
sys.path[:0] = [str(root), str(root / 'site')]
import consumer
import sample_provider as provider
required = frozenset({'consumer', 'sample_provider'})
prior = capture.completed('sample_provider')
capture.assert_binding('consumer', 'value', 'sample_provider', 'value')
assert provider.value == consumer.value == 7
if mode == 'pending':
    assert type(provider.during_initialization.loader) is recorder._CapturedSourceLoader
    assert 'sample_provider' not in capture._module_failures
spec = importlib.machinery.PathFinder().find_spec('sample_provider')
assert spec is not None
assert type(spec.loader) is recorder._CapturedSourceLoader
assert capture.completed('sample_provider') is prior
assert sys.modules['sample_provider'] is provider
assert provider.value == consumer.value == 7
capture.assert_binding('consumer', 'value', 'sample_provider', 'value')
if mode in ('lookup', 'pending'):
    assert 'sample_provider' not in capture._module_failures
    raise SystemExit(0)
if mode == 'direct_exec':
    spec.loader.exec_module(provider)
else:
    importlib.reload(provider)
assert capture._module_failures['sample_provider'] == 'module_reload_not_admitted'
try:
    capture.assert_retained(required)
except CaptureError as exc:
    assert str(exc) == 'required_module_initialization_failed'
else:
    raise AssertionError('changed or reexecuted provider was accepted')
try:
    capture.assert_retained(required)
except CaptureError:
    pass
else:
    raise AssertionError('restoring provider erased capture refusal')
"""
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            "-c",
            script,
            str(product),
            str(tmp_path),
            base64.b64encode(content).decode(),
            base64.b64encode(lock).decode(),
            mode,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr


def test_dynamic_capture_respects_an_earlier_provider_finder(tmp_path: Path) -> None:
    """The source recorder must not override an earlier normal meta-path finder."""
    _, _, lock, content = _distribution(tmp_path)
    consumer = tmp_path / "consumer.py"
    consumer.write_text(
        "import importlib.util\n"
        "import sys\n"
        "class Loader:\n"
        "    def create_module(self, spec): return None\n"
        "    def exec_module(self, module): module.value = 11\n"
        "class Finder:\n"
        "    def find_spec(self, fullname, path=None, target=None):\n"
        "        if fullname == 'sample_provider':\n"
        "            return importlib.util.spec_from_loader(fullname, Loader())\n"
        "        return None\n"
        "finder = Finder()\n"
        "sys.meta_path.insert(0, finder)\n"
        "import sample_provider\n"
        "value = sample_provider.value\n",
        encoding="utf-8",
    )
    product = Path(__file__).resolve().parents[3]
    script = r"""
import base64, hashlib, pathlib, sys
product, root, archive, lock = sys.argv[1:]
root = pathlib.Path(root)
sys.path.insert(0, product)
from tools import authority_bootstrap as host
from tools.loaded_execution_capture import ExpectedSource, SourceExecutionCapture
host._LockedWheelSourceSelector._archive_bytes = staticmethod(lambda url, size: base64.b64decode(archive))
selector = host._LockedWheelSourceSelector(root, root / 'site', base64.b64decode(lock))
source = root / 'consumer.py'
capture = SourceExecutionCapture(root, {
    'consumer': ExpectedSource('consumer.py', hashlib.sha256(source.read_bytes()).hexdigest())
}, external_source_selector=selector.select)
capture.install()
sys.path[:0] = [str(root), str(root / 'site')]
import consumer
assert consumer.value == 11
assert not selector._selected
capture.assert_retained(frozenset({'consumer'}))
graph = capture.relevant_graph(frozenset({'consumer'}))
assert 'sample_provider' in graph.external_providers
"""
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            "-c",
            script,
            str(product),
            str(tmp_path),
            base64.b64encode(content).decode(),
            base64.b64encode(lock).decode(),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr


def test_unselected_source_uses_one_normal_pathfinder_lookup(tmp_path: Path) -> None:
    """A declined provider selection does not invoke a path hook a second time."""
    _distribution(tmp_path)
    source = tmp_path / "consumer.py"
    source.write_text(
        "import sys\n"
        "class LaterFinder:\n"
        "    def __init__(self): self.seen = []\n"
        "    def find_spec(self, fullname, path=None, target=None):\n"
        "        if fullname == 'n7_missing_probe': self.seen.append(fullname)\n"
        "        return None\n"
        "later = LaterFinder()\n"
        "sys.meta_path.append(later)\n"
        "import sample_provider\n"
        "try:\n"
        "    import n7_missing_probe\n"
        "except ModuleNotFoundError:\n"
        "    pass\n"
        "value = sample_provider.value\n",
        encoding="utf-8",
    )
    (tmp_path / "fork_candidate.py").write_text("value = 23\n", encoding="utf-8")
    (tmp_path / "failed_candidate.py").write_text("value = 29\n", encoding="utf-8")
    product = Path(__file__).resolve().parents[3]
    script = r"""
import hashlib, importlib.machinery, os, pathlib, sys
product, root, mode = sys.argv[1:]
root = pathlib.Path(root)
sys.path.insert(0, product)
from tools import loaded_execution_capture as recorder
original = importlib.machinery.PathFinder.find_spec
calls = []
def counted(fullname, path=None, target=None):
    if fullname in {'sample_provider', 'n7_missing_probe'}: calls.append(fullname)
    return original(fullname, path, target)
recorder._FIND_SPEC = counted
source = root / 'consumer.py'
capture = recorder.SourceExecutionCapture(root, {
    'consumer': recorder.ExpectedSource('consumer.py', hashlib.sha256(source.read_bytes()).hexdigest())
}, external_source_selector=lambda name, path: None)
capture.install()
assert any(finder is importlib.machinery.PathFinder for finder in sys.meta_path)
sys.path[:0] = [str(root), str(root / 'site')]
import consumer
assert consumer.value == 7
assert calls == ['sample_provider', 'n7_missing_probe'], calls
assert consumer.later.seen == ['n7_missing_probe']
assert 'sample_provider' in capture.relevant_graph(frozenset({'consumer'})).external_providers
if hasattr(os, 'fork'):
    pid = os.fork()
    if pid == 0:
        try:
            import fork_candidate
            os._exit(0 if fork_candidate.value == 23 else 1)
        except BaseException:
            os._exit(1)
    _, status = os.waitpid(pid, 0)
    assert os.waitstatus_to_exitcode(status) == 0
descriptor = vars(importlib.machinery.PathFinder)['find_spec']
if mode == 'remove_guard':
    capture._path_finder_descriptor = None
type.__setattr__(importlib.machinery.PathFinder, 'find_spec', classmethod(lambda cls, *args: None))
try:
    capture.assert_retained(frozenset({'consumer'}))
except recorder.CaptureError as exc:
    assert str(exc) == 'capture_path_finder_changed'
else:
    raise AssertionError('changed standard path finder was accepted')
finally:
    type.__setattr__(importlib.machinery.PathFinder, 'find_spec', descriptor)
assert capture.failed and capture.failure_reason == 'capture_path_finder_changed'
import failed_candidate
assert failed_candidate.value == 29
try:
    capture.assert_retained(frozenset({'consumer'}))
except recorder.CaptureError:
    pass
else:
    raise AssertionError('restoring path finder erased capture failure')
"""
    for mode in ("normal", "remove_guard"):
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-B", "-c", script, str(product), str(tmp_path), mode],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
        if mode == "remove_guard":
            print(f"path finder guard removal exit: {result.returncode}")
            print(result.stderr, end="")
            assert result.returncode != 0
            assert "changed standard path finder was accepted" in result.stderr
        else:
            assert result.returncode == 0, result.stderr
