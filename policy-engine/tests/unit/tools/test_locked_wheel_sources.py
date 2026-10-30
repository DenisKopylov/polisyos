"""The host binds installed Python source to exact locked wheel members."""

from __future__ import annotations

import base64
import hashlib
import io
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from tools import authority_bootstrap as host


def _distribution(root: Path, *, finder: bool = False) -> tuple[Path, Path, bytes, bytes]:
    site = root / "site"
    package = site / "sample_provider"
    info = site / "sample_provider-1.0.dist-info"
    package.mkdir(parents=True)
    info.mkdir()
    source = (
        b"import sys\nfrom .base import Base\nclass Finder(Base): pass\n"
        b"finder = Finder()\nsys.meta_path.append(finder)\nvalue = 7\n"
        if finder
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
    """A prior source selection is reusable only before its first execution."""
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
