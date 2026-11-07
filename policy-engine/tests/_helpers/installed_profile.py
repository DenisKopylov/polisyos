"""Prepare one reusable installed-origin profile without building or installing it.

The profile reuses Q2's dependency measurement and origin checker. Its local
startup observer covers normally terminating Python children as well as pytest;
an interrupted child leaves a started record rather than implying qualification.
This helper makes no package, dependency-authenticity, or product authority claim.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping


def clean_installed_environment(environment: Mapping[str, str]) -> dict[str, str]:
    """Remove source injection and inherited task observers from a child profile."""
    result = dict(environment)
    for key in (
        "PYTHONPATH",
        "PYTHONHOME",
        "PYTHONUSERBASE",
        "PYTHONSTARTUP",
        "VIRTUAL_ENV",
        "CONDA_PREFIX",
        "UV_PROJECT_ENVIRONMENT",
        "UV_PYTHON",
        "PYTEST_ADDOPTS",
        "PYTEST_PLUGINS",
    ):
        result.pop(key, None)
    for key in tuple(result):
        if key.startswith("C97_") or key.startswith("POLISYOS_INSTALLED_PROFILE_"):
            result.pop(key)
    result.update(
        PYTHONNOUSERSITE="1",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONSAFEPATH="1",
        POLISYOS_INSTALLED_PROFILE_ACTIVE="1",
    )
    return result


def installed_child_environment(environment: Mapping[str, str]) -> dict[str, str] | None:
    """Select installed child mode only from this interpreter's real package origin.

    Absence preserves source-test behavior. A declared installed mode must match
    actual sysconfig and the loaded package file/spec/search path; the startup
    observer remains responsible for all other imports and wheel-byte binding.
    """
    import importlib
    import sysconfig

    marker = environment.get("POLISYOS_INSTALLED_PROFILE_PURELIB")
    if marker is None:
        if environment.get("POLISYOS_INSTALLED_PROFILE_ACTIVE") == "1":
            raise ValueError("active installed profile has no admitted purelib")
        return None
    expected = Path(marker)
    if not expected.is_absolute():
        raise ValueError("installed purelib marker is not absolute")
    expected = expected.resolve(strict=True)
    if expected != Path(sysconfig.get_path("purelib")).resolve(strict=True):
        raise ValueError("installed purelib differs from actual sysconfig")
    package = importlib.import_module("polisyos")
    origin = getattr(package, "__file__", None)
    spec_origin = getattr(getattr(package, "__spec__", None), "origin", None)
    package_root = expected / "polisyos"
    if not isinstance(origin, str) or not isinstance(spec_origin, str):
        raise ValueError("installed package is not file-backed")
    actual = Path(origin).resolve(strict=True)
    if (
        actual.parent != package_root
        or Path(spec_origin).resolve(strict=True) != actual
        or [Path(path).resolve(strict=True) for path in package.__path__] != [package_root]
    ):
        raise ValueError("running package is outside the admitted installed purelib")
    return clean_installed_environment(environment)


def read_completed_observer_reports(reports: Path, *, wheel_sha256: str) -> list[dict[str, Any]]:
    """Read the whole named process record set, refusing absent or incomplete proof.

    The caller supplies a fresh output directory for its one controlled wave.
    This checks observed startup records, not processes that bypassed Python's
    normal inherited startup entirely.
    """
    import json

    rows = [json.loads(path.read_text()) for path in sorted(reports.glob("*.json"))]
    if not rows:
        raise ValueError("no installed process records")
    for row in rows:
        if row.get("phase") != "finished" or row.get("errors"):
            raise ValueError("installed process record failed or is incomplete")
        if row.get("wheel_sha256") != wheel_sha256:
            raise ValueError("installed process record names a different wheel")
    if not any("polisyos" in row.get("origins", {}) for row in rows):
        raise ValueError("no installed product import was observed")
    return rows


def _write_owned(path: Path, payload: bytes) -> None:
    """Replace only the named regular profile file, detaching any hardlink."""
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError(f"installed observer target is not an owned regular file: {path}")
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        stream.write(payload)
        temporary = Path(stream.name)
    temporary.chmod(mode)
    os.replace(temporary, path)


def prepare_installed_observer(
    *,
    product: Path,
    prefix: Path,
    purelib: Path,
    app_python: Path,
    dependency_site: Path,
    wheel: Path,
    reports: Path,
    tests_root: Path | None = None,
) -> dict[str, Any]:
    """Materialize the explicit profile's startup guard; never install a package.

    Args:
        product: Frozen product root containing the canonical Q2 helpers.
        prefix: Existing external qualification environment, never the app env.
        purelib: That environment's real installed site-packages directory.
        app_python: Existing app interpreter used only to measure dependencies.
        dependency_site: Its exact site appended without executing any .pth file.
        wheel: The one built wheel whose loaded first-party bytes must match.
        reports: Owned output directory for one start/final record per process.
        tests_root: Optional explicit test-only namespace, never a sys.path entry.

    Returns:
        The actual generated file paths and hashes for the caller's change record.

    Raises:
        ValueError: A path or profile input cannot meet the installed boundary.
    """
    product = product.resolve(strict=True)
    prefix = prefix.resolve(strict=True)
    purelib = purelib.resolve(strict=True)
    dependency_site = dependency_site.resolve(strict=True)
    wheel = wheel.resolve(strict=True)
    if reports.is_symlink():
        raise ValueError("observer outputs must not use a report-directory symlink")
    reports = reports.resolve()
    if prefix.is_relative_to(product.parent) or not purelib.is_relative_to(prefix):
        raise ValueError("qualification prefix must be outside checkout with its own purelib")
    if purelib == dependency_site or tuple(purelib.glob("*.pth")):
        raise ValueError(
            "installed purelib cannot be the app dependency site or process .pth files"
        )
    if reports.is_relative_to(prefix):
        raise ValueError("observer outputs must not change the installed prefix")
    if tests_root is not None:
        tests_root = tests_root.resolve(strict=True)
        if tests_root != product / "tests":
            raise ValueError("test-only namespace must be the explicit frozen tests root")

    recipe_path = product / (
        "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/run.py"
    )
    spec = importlib.util.spec_from_file_location("_e02_installed_q2_recipe", recipe_path)
    if spec is None or spec.loader is None:
        raise ValueError("canonical Q2 recipe is unavailable")
    recipe = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = recipe
    spec.loader.exec_module(recipe)
    reports.mkdir(parents=True, exist_ok=True)
    setup = reports / "setup"
    setup.mkdir(exist_ok=True)
    profile = recipe.measure_app_dependency_profile(app_python, dependency_site, setup)
    gate, _ = recipe.load_installed_origin_gate()
    config = {
        "prefix": str(prefix),
        "purelib": str(purelib),
        "dependency_site": str(dependency_site),
        "checkout": str(product.parent),
        "tests_root": str(tests_root) if tests_root is not None else None,
        "wheel": str(wheel),
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "gate_sha256": hashlib.sha256(gate).hexdigest(),
        "reports": str(reports),
    }
    observer = (
        "from __future__ import annotations\n"
        "from pathlib import Path\n"
        + recipe.dependency_profile_guard(profile)
        + "\n_CONFIG = "
        + repr(config)
        + "\n"
        + _OBSERVER
    ).encode()
    startup = (
        "import os, sys\n"
        "def _e02_failed_startup(error):\n"
        "    try:\n"
        "        sys.stderr.write('installed observer startup failed: ' + repr(error) + '\\n')\n"
        "    finally:\n"
        "        for stream in (sys.stdout, sys.stderr):\n"
        "            try:\n"
        "                stream.flush()\n"
        "            except BaseException:\n"
        "                pass\n"
        "        os._exit(86)\n"
        "try:\n"
        f"    _dependency = {str(dependency_site)!r}\n"
        "    if _dependency in sys.path:\n"
        "        raise RuntimeError('dependency site was already processed')\n"
        "    sys.path.append(_dependency)\n"
        "    if os.environ.get('POLISYOS_INSTALLED_PROFILE_ACTIVE') == '1':\n"
        "        import e02_installed_origin_observer\n"
        "        e02_installed_origin_observer.install()\n"
        "except BaseException as error:\n"
        "    _e02_failed_startup(error)\n"
    ).encode()
    generated = {
        "q2_installed_origin_gate.py": gate,
        "e02_installed_origin_observer.py": observer,
        "sitecustomize.py": startup,
    }
    for name, payload in generated.items():
        _write_owned(purelib / name, payload)
    return {
        "prefix": str(prefix),
        "purelib": str(purelib),
        "reports": str(reports),
        "wheel_sha256": config["wheel_sha256"],
        "generated": {
            str(purelib / name): hashlib.sha256(payload).hexdigest()
            for name, payload in generated.items()
        },
    }


_OBSERVER = r"""
import atexit
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import sys
import sysconfig
import time
import types
import zipfile

_REPORT = Path(_CONFIG["reports"]) / (str(os.getpid()) + "-" + str(time.time_ns()) + ".json")
_INITIAL = {
    "pid": os.getpid(), "ppid": os.getppid(), "phase": "started",
    "argv_sha256": hashlib.sha256(json.dumps(sys.argv).encode()).hexdigest(),
    "prefix": sys.prefix, "purelib": sysconfig.get_path("purelib"),
    "wheel_sha256": _CONFIG["wheel_sha256"], "errors": [],
}
_VERIFY_ORIGINS = None


def _write(record):
    temporary = _REPORT.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, sort_keys=True) + "\n")
    os.replace(temporary, _REPORT)


def _namespace(name, directory):
    existing = sys.modules.get(name)
    if existing is not None:
        if [str(Path(p).resolve()) for p in getattr(existing, "__path__", ())] != [directory]:
            raise RuntimeError("foreign test namespace already loaded: " + name)
        return
    spec = importlib.machinery.ModuleSpec(name, loader=None, is_package=True)
    spec.submodule_search_locations = [directory]
    module = types.ModuleType(name)
    module.__spec__ = spec
    module.__package__ = name
    module.__path__ = [directory]
    sys.modules[name] = module


def _profile_errors():
    purelib = Path(_CONFIG["purelib"])
    errors = []
    if Path(sys.prefix).resolve() != Path(_CONFIG["prefix"]):
        errors.append("actual prefix differs")
    if Path(sysconfig.get_path("purelib")).resolve() != purelib:
        errors.append("actual purelib differs")
    if os.environ.get("PYTHONPATH") is not None:
        errors.append("PYTHONPATH was not cleared")
    if tuple(purelib.glob("*.pth")):
        errors.append("installed .pth file present")
    if not sys.dont_write_bytecode:
        errors.append("bytecode writes were not disabled")
    dependency = _CONFIG["dependency_site"]
    if not _q2_dependency_site_allowed(dependency):
        errors.append("dependency profile not bound")
    paths = [Path(p).resolve() for p in sys.path if p]
    if purelib not in paths or Path(dependency) not in paths:
        errors.append("installed/dependency site missing")
    elif paths.index(purelib) >= paths.index(Path(dependency)):
        errors.append("installed site does not precede dependency site")
    checkout = Path(_CONFIG["checkout"])
    if any(p.is_relative_to(checkout) and p != Path(dependency) for p in paths):
        errors.append("checkout path injected")
    gate_path = purelib / "q2_installed_origin_gate.py"
    if hashlib.sha256(gate_path.read_bytes()).hexdigest() != _CONFIG["gate_sha256"]:
        errors.append("canonical origin gate bytes differ")
    return errors


def _abort(message):
    try:
        sys.stderr.write(message + "\n")
    finally:
        # os._exit deliberately preserves a failing qualification code during
        # interpreter shutdown. Flush both deciding streams before bypassing
        # normal shutdown; otherwise a valid negative witness may disappear.
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.flush()
            except BaseException:
                pass
        os._exit(86)


def _finish():
    record = dict(_INITIAL)
    errors = []
    try:
        errors.extend(_profile_errors())
        origins, origin_errors = _VERIFY_ORIGINS(
            Path(_CONFIG["purelib"]), sys.modules.copy()
        )
        errors.extend(origin_errors)
        subjects = {name: row for name, row in origins.items()
                    if name == "polisyos" or name.startswith("polisyos.")
                    or name == "tools" or name.startswith("tools.")}
        wheel = Path(_CONFIG["wheel"])
        if hashlib.sha256(wheel.read_bytes()).hexdigest() != _CONFIG["wheel_sha256"]:
            errors.append("selected wheel bytes differ")
        with zipfile.ZipFile(wheel) as archive:
            if len(archive.namelist()) != len(set(archive.namelist())):
                errors.append("duplicate wheel member")
            for name, row in subjects.items():
                file = row.get("resolved_file")
                if file is None:
                    continue
                path = Path(file)
                member = path.relative_to(Path(_CONFIG["purelib"])).as_posix()
                try:
                    expected = archive.read(member)
                except KeyError:
                    errors.append({"module": name, "reason": "loaded file not in wheel"})
                    continue
                if path.read_bytes() != expected:
                    errors.append({"module": name, "reason": "loaded file differs from wheel"})
        record["origins"] = subjects
        record["test_inputs"] = {
            name: {"path": str(Path(module.__file__).resolve()),
                   "sha256": hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()}
            for name, module in tuple(sys.modules.items())
            if (name == "tests" or name.startswith("tests.")
                or name == "_helpers" or name.startswith("_helpers."))
            and getattr(module, "__file__", None)
            and Path(module.__file__).is_file()
        }
    except BaseException as error:
        errors.append(repr(error))
    record.update(phase="failed" if errors else "finished", errors=errors)
    try:
        _write(record)
    except BaseException as error:
        _abort("installed observer output failed: " + repr(error))
    if errors:
        _abort("installed origin qualification failed: " + repr(errors))


def install():
    global _VERIFY_ORIGINS
    _write(_INITIAL)
    try:
        errors = _profile_errors()
        if errors:
            raise RuntimeError(repr(errors))
        # Bind the actual checked file and callable before the body can change
        # the import path. Hashing one file while importing another is not proof.
        spec = importlib.util.spec_from_file_location(
            "q2_installed_origin_gate", Path(_CONFIG["purelib"]) / "q2_installed_origin_gate.py"
        )
        gate = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = gate
        spec.loader.exec_module(gate)
        _VERIFY_ORIGINS = gate.verify_loaded_module_origins
        test_root = _CONFIG["tests_root"]
        if test_root is not None:
            _namespace("tests", test_root)
            _namespace("_helpers", str(Path(test_root) / "_helpers"))
        os.environ["POLISYOS_INSTALLED_PROFILE_PURELIB"] = _CONFIG["purelib"]
    except BaseException as error:
        _write(dict(_INITIAL, phase="failed", errors=[repr(error)]))
        raise
    atexit.register(_finish)
"""
