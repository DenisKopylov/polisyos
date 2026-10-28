"""Exercise installed census semantics with independently reconciled Git bytes.

This test is an artifact consumer, not an installer.  The source-owned Q2 harness
must first build wheel -> sdist -> rebuilt wheel and create a non-editable prefix
outside checkout ancestry.  ``prepare_child_observer`` is a task-harness hook:
call it once after Q2 provisioning and before freezing the installed profile.
Without that complete binding these cases are SKIP, never installed PASS.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest

# Runs from task-owned installed sitecustomize, in the actual CLI interpreter.
# Reuse Q2's origin guard; do not invent another installed-origin owner.
CHILD_OBSERVER = r"""
from __future__ import annotations
import atexit, base64, configparser, csv, hashlib, importlib.machinery, inspect, marshal
import io, json, os, stat, subprocess, sys, time, tomllib, zipfile
from pathlib import Path, PurePosixPath

if os.environ.get("C97_CHILD_REPORT"):
    _started = time.time()
    _binding_path = Path(os.environ["C97_INSTALLED_BINDING"])
    _binding_bytes = _binding_path.read_bytes()
    _binding = json.loads(_binding_bytes)
    _cache = Path(sys.pycache_prefix) if sys.pycache_prefix else None
    _initial = {
        "pid": os.getpid(), "ppid": os.getppid(), "started_epoch": _started,
        "executable": sys.executable, "prefix": sys.prefix,
        "base_prefix": sys.base_prefix, "argv": list(sys.argv),
        "flags": {name: getattr(sys.flags, name) for name in dir(sys.flags)
                  if not name.startswith("_") and type(getattr(sys.flags, name)) in (int, bool)},
        "xoptions": dict(sys._xoptions), "pycache_prefix": sys.pycache_prefix,
        "cache_initially_empty": _cache is not None and _cache.is_dir()
                                 and not any(_cache.iterdir()),
        "cwd": str(Path.cwd().resolve()), "sys_path_at_start": list(sys.path),
        "environment": {name: os.environ.get(name) for name in (
            "PYTHONPATH", "PYTHONNOUSERSITE", "PYTHONDONTWRITEBYTECODE",
            "PYTHONPYCACHEPREFIX", "PYTEST_ADDOPTS", "PYTEST_DISABLE_PLUGIN_AUTOLOAD")},
        "binding_sha256": hashlib.sha256(_binding_bytes).hexdigest(),
        "observer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }

    def _digest(data):
        return hashlib.sha256(data).hexdigest()

    def _rows(data):
        result = {}
        for row in csv.reader(io.StringIO(data.decode("utf-8"), newline="")):
            if len(row) != 3 or row[0] in result:
                raise ValueError("malformed or duplicate RECORD row")
            result[row[0]] = (row[1], row[2])
        return result

    def _record_digest(data):
        return "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()

    def _finish():
        report = dict(_initial)
        errors = []
        try:
            import q2_installed_origin_gate as gate
            purelib = Path(_binding["purelib"]).resolve(strict=True)
            prefix = Path(_binding["prefix"]).resolve(strict=True)
            checkout = Path(_binding["checkout_root"]).resolve(strict=True)
            git_reads = []
            def git_bytes(*args):
                completed = subprocess.run(["git", *args], cwd=checkout,
                                           capture_output=True, check=False)
                git_reads.append({"command": ["git", *args], "cwd": str(checkout),
                                  "returncode": completed.returncode,
                                  "stdout_bytes": len(completed.stdout),
                                  "stdout_sha256": _digest(completed.stdout),
                                  "stderr_bytes": len(completed.stderr),
                                  "stderr_sha256": _digest(completed.stderr)})
                if completed.returncode or completed.stderr:
                    raise ValueError("actual source Git read failed: " + repr(args))
                return completed.stdout
            actual_head = git_bytes("rev-parse", "HEAD").decode().strip()
            actual_tree = git_bytes("rev-parse", "HEAD^{tree}").decode().strip()
            if actual_head != _binding["source_commit"] or actual_tree != _binding["source_tree"]:
                raise ValueError("actual source Git HEAD/tree mismatch: " + actual_head + "/" + actual_tree)
            report["source_git"] = {"commit": actual_head, "tree": actual_tree, "reads": git_reads}
            dependency = Path(_binding["dependency_site"]).resolve(strict=True)
            neutral = Path(_binding["neutral_cwd"]).resolve(strict=True)
            if prefix.is_relative_to(checkout) or neutral.is_relative_to(checkout):
                raise ValueError("installed prefix/CWD is inside checkout ancestry")
            if Path.cwd().resolve() != neutral or Path(sys.prefix).resolve() != prefix:
                raise ValueError("actual child prefix/CWD differs from binding")
            if sys.executable != _binding["python"] or os.environ.get("PYTHONPATH") is not None:
                raise ValueError("wrong executing interpreter or PYTHONPATH remains")
            if not sys.dont_write_bytecode or not report["cache_initially_empty"]:
                raise ValueError("actual child bytecode/cache profile differs")
            if Path(__file__).parent.resolve() != purelib:
                raise ValueError("observer was not loaded from installed purelib")
            if report["observer_sha256"] != _binding["observer_sha256"]:
                raise ValueError("task observer bytes differ")
            gate_data = Path(gate.__file__).read_bytes()
            canonical_gate = git_bytes("cat-file", "blob", actual_head + ":"
                                       "policy-engine/docs/research/e02-cloud-test-plan/"
                                       "implementation-handoffs/LOCAL/q2-packaging/raw/installed_origin_gate_r4.py")
            if gate_data != canonical_gate:
                raise ValueError("loaded Q2 origin guard differs from actual source Git")
            if _digest(gate_data) != _binding["q2_origin_gate_sha256"]:
                raise ValueError("Q2 origin guard differs from pinned source")
            normalized = [str(Path(p).resolve()) for p in sys.path if p]
            if normalized.index(str(purelib)) >= normalized.index(str(dependency)):
                raise ValueError("installed purelib is not before unprocessed dependency site")
            bad = [p for p in normalized if Path(p).is_relative_to(checkout)
                   and p != str(dependency)]
            if bad:
                raise ValueError("source/test path injected: " + repr(bad))
            if list(purelib.glob("*.pth")):
                raise ValueError("installed purelib contains executable .pth input")
            wheel_path = Path(_binding["wheel"]["path"]).resolve(strict=True)
            wheel_data = wheel_path.read_bytes()
            if _digest(wheel_data) != _binding["wheel"]["sha256"]:
                raise ValueError("selected built-wheel bytes differ")
            report["wheel_sha256"] = _digest(wheel_data)
            loaded = {}
            with zipfile.ZipFile(io.BytesIO(wheel_data)) as wheel:
                names = wheel.namelist()
                if len(names) != len(set(names)):
                    raise ValueError("duplicate wheel member")
                for info in wheel.infolist():
                    path = PurePosixPath(info.filename)
                    if path.is_absolute() or ".." in path.parts or "\\" in info.filename:
                        raise ValueError("unsafe wheel member")
                    if stat.S_ISLNK(info.external_attr >> 16):
                        raise ValueError("symlink wheel member")
                records = [n for n in names if n.endswith(".dist-info/RECORD")]
                if len(records) != 1:
                    raise ValueError("not one wheel RECORD")
                record_name = records[0]
                wheel_record = _rows(wheel.read(record_name))
                if set(wheel_record) != {n for n in names if not n.endswith("/")}:
                    raise ValueError("wheel members differ from wheel RECORD")
                for name, (digest, size) in wheel_record.items():
                    if name == record_name:
                        if digest or size:
                            raise ValueError("RECORD self row is not unhashed")
                        continue
                    data = wheel.read(name)
                    if digest != _record_digest(data) or size != str(len(data)):
                        raise ValueError("wheel member/RECORD mismatch: " + name)
                installed_record_path = purelib / record_name
                installed_record_bytes = installed_record_path.read_bytes()
                installed_record = _rows(installed_record_bytes)
                for name, (digest, size) in installed_record.items():
                    lexical = purelib / name
                    path = lexical.resolve(strict=True)
                    if not path.is_relative_to(prefix) or not path.is_file() or lexical.is_symlink():
                        raise ValueError("installed RECORD path escapes prefix or is not regular")
                    data = path.read_bytes()
                    if name == record_name:
                        if digest or size:
                            raise ValueError("installed RECORD self row is not unhashed")
                    elif digest != _record_digest(data) or size != str(len(data)):
                        raise ValueError("installed file/RECORD mismatch: " + name)
                overrides = {}
                control = _binding.get("control")
                if control is not None:
                    # Only the frozen M1 is admitted by this census oracle.
                    if control != "M1_NUL_parser":
                        raise ValueError("unrecognized census control")
                    overrides = {"tools/quality/validation/schema_fqn_census.py":
                                 "26fcae7b668aa91a9ca8c6b63ddc02ff673812e340f5b547e87e679630e377fa"}
                entrypoints = configparser.ConfigParser()
                entrypoints.read_string(wheel.read(record_name.rsplit("/", 1)[0]
                                                   + "/entry_points.txt").decode("utf-8"))
                declared = entrypoints["console_scripts"]["polisyos-tools"].strip()
                project = tomllib.loads(git_bytes("cat-file", "blob", actual_head
                                                 + ":policy-engine/pyproject.toml").decode("utf-8"))
                if declared != project["project"]["scripts"]["polisyos-tools"]:
                    raise ValueError("wheel entrypoint differs from immutable pyproject")
                declared_module, separator, declared_attribute = declared.partition(":")
                if (not separator or not all(part.isidentifier() for part in declared_module.split("."))
                        or not all(part.isidentifier() for part in declared_attribute.split("."))):
                    raise ValueError("unsupported console entrypoint declaration")
                mode = os.environ["C97_ENTRYPOINT"]
                main_module = sys.modules["__main__"]
                main_path = Path(main_module.__file__).resolve(strict=True)
                cli = Path(_binding["cli"]).resolve(strict=True)
                if mode == "console":
                    entry_module = sys.modules.get(declared_module)
                    if entry_module is None:
                        raise ValueError("console did not load its actual declared entry module")
                elif mode == "module":
                    # runpy executes the declared file in __main__.  This is an
                    # explicit execution-role view, not a sys.modules alias.
                    entry_module = main_module
                    if not sys.flags.isolated:
                        raise ValueError("actual module invocation is not isolated")
                else:
                    raise ValueError("unsupported actual CLI invocation mode")
                entry_spec = getattr(entry_module, "__spec__", None)
                if entry_spec is None or entry_spec.name != declared_module:
                    raise ValueError("executing module spec differs from the declared entrypoint")
                # Reuse one Q2 origin invariant for ordinary loaded modules and
                # this actual executing entry module; never mutate sys.modules.
                cached = sys.modules.copy()
                origins, origin_errors = gate.verify_loaded_module_origins(purelib, cached)
                entry_origins, entry_errors = gate.verify_loaded_module_origins(
                    purelib, {declared_module: entry_module})
                if origin_errors or entry_errors:
                    raise ValueError("Q2 loaded/entry origin refusal: "
                                     + repr(origin_errors + entry_errors))
                required = {"tools", "tools.quality.validation.schema_fqn_census"}
                if not required.issubset(origins):
                    raise ValueError("real public census modules did not execute")
                entry_origin = entry_origins[declared_module]
                entry_file = Path(entry_origin["resolved_file"])
                entry_member = entry_file.relative_to(purelib).as_posix()
                # Derive module layout from declared metadata AND actual archive
                # membership; no tools/cli package pathname is assumed.
                stem = declared_module.replace(".", "/")
                candidates = [path for path in (stem + ".py", stem + "/__init__.py")
                              if path in wheel_record]
                if candidates != [entry_member]:
                    raise ValueError("actual entry spec does not select the unique wheel module")
                if mode == "module" and main_path != entry_file:
                    raise ValueError("actual runpy __main__ is not the declared module file")
                callable_object = entry_module
                for attribute in declared_attribute.split("."):
                    callable_object = getattr(callable_object, attribute)
                if (not inspect.isfunction(callable_object)
                        or callable_object.__globals__ is not entry_module.__dict__
                        or Path(callable_object.__code__.co_filename).resolve(strict=True) != entry_file):
                    raise ValueError("actual entry callable code is not defined by the admitted module")
                subjects = [(name, name, cached[name], origin)
                            for name, origin in origins.items()
                            if name == "tools" or name.startswith("tools.")
                            or name == "polisyos" or name.startswith("polisyos.")]
                # The existing cache entry (if any) remains in subjects.  Add the
                # runpy execution object separately, even when it has no alias.
                if mode == "module":
                    subjects.append(("__main__", declared_module, entry_module, entry_origin))
                report["origins"] = origins
                report["entrypoint_execution"] = {
                    "declared": declared, "invocation_mode": mode,
                    "actual_name": entry_module.__name__, "spec_name": entry_spec.name,
                    "spec_origin": entry_spec.origin, "source_member": entry_member,
                    "canonical_cache_present": declared_module in cached,
                    "canonical_cache_is_execution_object": cached.get(declared_module) is entry_module,
                    "actual_origin": entry_origin,
                    "callable_module": callable_object.__module__,
                    "callable_qualname": callable_object.__qualname__,
                    "callable_code_filename": callable_object.__code__.co_filename,
                    "callable_code_sha256": _digest(marshal.dumps(callable_object.__code__)),
                    "code_boundary": "standard source loader/fresh cache; code snapshot is not a call trace",
                }
                report["sys_path_at_finish"] = list(sys.path)
                for name, canonical_name, module, origin in subjects:
                    if "file" not in origin:  # Q2 already checked finite namespace locations.
                        continue
                    if (module.__spec__.name != canonical_name
                            or type(module.__spec__.loader) is not importlib.machinery.SourceFileLoader):
                        raise ValueError("product execution spec/loader differs: " + name)
                    path = Path(origin["resolved_file"])
                    if (module.__spec__.loader.name != canonical_name
                            or Path(module.__spec__.loader.path).resolve(strict=True) != path):
                        raise ValueError("actual source loader does not select its reported file: " + name)
                    relative = path.relative_to(purelib).as_posix()
                    if relative not in wheel_record or relative not in installed_record:
                        raise ValueError("loaded product source absent from actual wheel/installed RECORD")
                    data = path.read_bytes()
                    source_relative = ("policy-engine/src/" if relative.startswith("polisyos/")
                                       else "policy-engine/") + relative
                    source_data = git_bytes("cat-file", "blob", actual_head + ":" + source_relative)
                    if source_data != wheel.read(relative):
                        raise ValueError("loaded wheel member differs from immutable source Git: " + relative)
                    expected = overrides.get(relative, _digest(source_data))
                    if _digest(data) != expected:
                        raise ValueError("loaded product bytes differ from selected wheel/control: " + relative)
                    loaded[name] = {"canonical_module": canonical_name,
                                    "actual_module_name": module.__name__,
                                    "member": relative, "bytes": len(data), "sha256": _digest(data),
                                    "loader": type(module.__spec__.loader).__name__,
                                    "source_git_path": source_relative, "source_sha256": _digest(source_data)}
                for name in wheel_record:
                    if name == record_name:
                        continue
                    if ".data/" in name:
                        raise ValueError("wheel .data remapping needs canonical Q2 handling, not guessed paths")
                    data = (purelib / name).read_bytes()
                    if _digest(data) != overrides.get(name, _digest(wheel.read(name))):
                        raise ValueError("installed wheel member differs: " + name)
                if mode == "console":
                    if main_path != cli or Path(sys.argv[0]).resolve() != cli:
                        raise ValueError("actual console __main__ is not installed script")
                    script = cli.read_bytes()
                    if script.splitlines()[0] != ("#!" + _binding["python"]).encode():
                        raise ValueError("actual console shebang differs from executing Python")
                    console_relative = os.path.relpath(cli, purelib)
                    if console_relative not in installed_record:
                        raise ValueError("console missing from actual installed RECORD")
                    if getattr(main_module, "__spec__", None) is not None:
                        raise ValueError("direct console wrapper unexpectedly has a module spec")
                    if not any(value is callable_object for value in main_module.__dict__.values()):
                        raise ValueError("native console wrapper does not hold its declared callable")
                    report["console_wrapper"] = {
                        "path": str(cli), "bytes": len(script), "sha256": _digest(script),
                        "installed_record_key": console_relative,
                        "spec_name": None,
                        "origin_kind": "installer-generated script, not a wheel/Git module member",
                        "delegates_to": declared,
                        "callable_is_admitted_module_object": True,
                    }
                report.update(loaded_product_sources=loaded,
                              wheel_record_sha256=_digest(wheel.read(record_name)),
                              installed_record_sha256=_digest(installed_record_bytes),
                              installed_record_rows=len(installed_record),
                              wheel_member_rows=len(wheel_record),
                              entrypoint=entrypoints["console_scripts"]["polisyos-tools"],
                              main_file=str(main_path),
                              main_sha256=_digest(main_path.read_bytes()),
                              gate_sha256=_digest(gate_data),
                              sitecustomize_sha256=_digest((purelib / "sitecustomize.py").read_bytes()))
        except BaseException as error:
            errors.append({"type": type(error).__name__, "message": str(error)})
        report.update(finished_epoch=time.time(), errors=errors,
                      outcome="PASS" if not errors else "ERROR",
                      unresolved_by_construction=[
                          "Finite loaded standard Python modules and actual selected wheel only; "
                          "not native/dynamic code, hostile host integrity or unloaded external clients.",
                          "This child reopens actual source Git/loaded wheel/installed RECORD bytes; "
                          "build execution and unloaded assets remain the separate Q2 build-chain proof."])
        Path(os.environ["C97_CHILD_REPORT"]).write_text(
            json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    atexit.register(_finish)
"""


def prepare_child_observer(binding_path: Path) -> None:
    """Attach this read-only observer to a task-owned, Q2-provisioned prefix.

    This hook never installs dependencies or product code.  The future execution
    recipe calls it explicitly; importing/collecting tests does not mutate a prefix.
    """
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    purelib = Path(binding["purelib"]).resolve(strict=True)
    checkout = Path(binding["checkout_root"]).resolve(strict=True)
    assert not purelib.is_relative_to(checkout)
    source = CHILD_OBSERVER.encode("utf-8")
    observer = purelib / "c97_census_child_observer.py"
    site = purelib / "sitecustomize.py"
    assert not observer.exists() and not observer.is_symlink()
    existing = site.read_bytes()
    assert hashlib.sha256(existing).hexdigest() == binding["q2_sitecustomize_sha256"]
    observer.write_bytes(source)
    site.write_bytes(existing + b"\nimport c97_census_child_observer\n")
    binding.update(
        observer_sha256=hashlib.sha256(source).hexdigest(),
        observed_sitecustomize_sha256=hashlib.sha256(site.read_bytes()).hexdigest(),
    )
    binding_path.write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@pytest.fixture(scope="session")
def installed_binding(request: pytest.FixtureRequest) -> tuple[Path, dict[str, Any]]:
    """Read exact build/install inputs; absence is an explicit unavailable profile."""
    value = os.environ.get("C97_INSTALLED_BINDING")
    if value is None:
        pytest.skip("no completed Q2 wheel/sdist/rebuilt-wheel installed binding was supplied")
    path = Path(value).resolve(strict=True)
    binding: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    assert binding["schema"] == "policyos.e02.c97.installed_binding.v1"
    for field in ("source_commit", "source_tree"):
        assert len(binding[field]) == 40 and all(c in "0123456789abcdef" for c in binding[field])
    assert binding["build_chain"]["outcome"] == "PASS"
    assert set(binding["build_chain"]["steps"]) == {
        "source_wheel",
        "sdist",
        "safe_sdist_extract",
        "rebuilt_wheel",
        "member_content_comparison",
    }
    for locator in (binding["effective_source_manifest"], binding["build_chain"]["receipt"]):
        evidence = Path(locator["path"])
        assert evidence.is_file() and not evidence.is_symlink()
        assert hashlib.sha256(evidence.read_bytes()).hexdigest() == locator["sha256"]
    # These receipt bytes are accessible inputs, not an independent rerun of
    # native Hatch; only the actual child source/wheel/installed bytes are the
    # recomputed admission predicate of this test.
    output = Path(binding["output_dir"]).resolve(strict=True)
    assert not output.is_relative_to(Path(binding["checkout_root"]).resolve(strict=True))
    observer = Path(binding["purelib"]) / "c97_census_child_observer.py"
    assert observer.read_bytes() == CHILD_OBSERVER.encode("utf-8")
    assert binding["observer_sha256"] == hashlib.sha256(observer.read_bytes()).hexdigest()
    profile = {
        "pid": os.getpid(),
        "executable": sys.executable,
        "prefix": sys.prefix,
        "argv": sys.argv,
        "sys_path": sys.path,
        "xoptions": sys._xoptions,
        "flags": {
            name: getattr(sys.flags, name)
            for name in dir(sys.flags)
            if not name.startswith("_") and type(getattr(sys.flags, name)) in (int, bool)
        },
        "pytest_version": pytest.__version__,
        "rootpath": str(request.config.rootpath),
        "inipath": str(request.config.inipath),
        "invocation_args": list(request.config.invocation_params.args),
        "active_plugins": sorted(
            name
            for name, plugin in request.config.pluginmanager.list_name_plugin()
            if plugin is not None
        ),
        "ini_addopts": request.config.getini("addopts"),
        "binding_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "test_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "unresolved_by_construction": [
            "pytest controller is not a substitute for the actual CLI child reports"
        ],
    }
    (output / "pytest-controller.json").write_text(json.dumps(profile, indent=2) + "\n")
    return path, binding


def _git(repository: Path, *args: str) -> bytes:
    result = subprocess.run(["git", *args], cwd=repository, capture_output=True, check=False)
    assert result.returncode == 0 and not result.stderr, (args, result.stderr)
    return result.stdout


def _names(raw: bytes) -> set[bytes]:
    """Decode independent NUL path lists, never porcelain status records."""
    assert not raw or raw.endswith(b"\0")
    return {item for item in raw.split(b"\0") if item}


def _oracle(repository: Path, product: Path) -> dict[str, Any]:
    """Use independent cached/uncached diff plus ls-files, with renames disabled."""
    commands = {
        "tracked": ["ls-files", "--cached", "-z"],
        "untracked": ["ls-files", "--others", "--exclude-standard", "-z"],
        "staged": ["diff", "--cached", "--no-renames", "--name-only", "-z"],
        "unstaged": ["diff", "--no-renames", "--name-only", "-z"],
    }
    raw = {name: _git(repository, *command) for name, command in commands.items()}
    prefix = os.fsencode(product.relative_to(repository).as_posix())
    prefix = b"" if prefix == b"." else prefix + b"/"

    def local(names: set[bytes]) -> set[bytes]:
        return {name[len(prefix) :] for name in names if name.startswith(prefix)}

    tracked, untracked = local(_names(raw["tracked"])), local(_names(raw["untracked"]))
    changes = local(_names(raw["staged"]) | _names(raw["unstaged"]) | _names(raw["untracked"]))
    selected = (tracked | untracked) - {b"excluded.bin"}
    expected_reads = {}
    for name in selected:
        data = Path(os.fsdecode(os.fsencode(product) + b"/" + name)).read_bytes()
        expected_reads[name.hex()] = {
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    return {
        "tracked": tracked,
        "untracked": untracked,
        "selected": selected,
        "changes": changes & selected,
        "expected_reads": expected_reads,
        "commands": {name: ["git", *command] for name, command in commands.items()},
        "raw_hex": {name: value.hex() for name, value in raw.items()},
    }


def _fixture(repository: Path, directory: str, scenario: str) -> tuple[Path, set[bytes]]:
    repository.mkdir()
    _git(repository, "init", "--quiet")
    _git(repository, "config", "user.email", "c97@example.invalid")
    _git(repository, "config", "user.name", "C97")
    _git(repository, "config", "status.renames", "true")
    product = repository / directory if directory else repository
    product.mkdir(parents=True, exist_ok=True)

    def write(name: bytes, data: bytes = b"{}\n") -> None:
        path = os.fsencode(product) + b"/" + name
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as stream:
            stream.write(data)

    names = {b"base.json"}
    if scenario in {"staged_pair", "unstaged_pair"}:
        names |= {b"configs/01 ordinary.json", b"configs/02\nline.json"}
    elif scenario.startswith("rename"):
        names |= {b"configs/01 old.json", b"configs/03 next.json"}
    for name in names:
        write(name)
    write(b"excluded.bin", b"\x00\xff")
    if directory:
        (repository / "outside.json").write_bytes(b"{}\n")
    _git(repository, "add", "--all")
    _git(repository, "commit", "--quiet", "-m", "C97 fixture base")
    expected_changes: set[bytes] = set()
    if scenario in {"staged_pair", "unstaged_pair", "added_modified_pair"}:
        expected_changes = {b"configs/01 ordinary.json", b"configs/02\nline.json"}
        if scenario == "added_modified_pair":
            for name in expected_changes:
                write(name)
            _git(repository, "add", "--all")
        for name in expected_changes:
            write(name, b'{"module":"polisyos.foundry.domain.schema"}\n')
        if scenario == "staged_pair":
            _git(repository, "add", "--all")
    elif scenario.startswith("rename"):
        old, new, sibling = b"configs/01 old.json", b"configs/02\nnew.json", b"configs/03 next.json"
        prefix = os.fsencode(directory) + b"/" if directory else b""
        result = subprocess.run(
            [b"git", b"mv", b"--", prefix + old, prefix + new],
            cwd=os.fsencode(repository),
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0 and not result.stderr
        write(sibling, b'{"module":"polisyos.data_forge.kernel.schemas.codegen"}\n')
        if scenario == "rename_modified":
            write(new, b"{}\n\n")
        expected_changes = {new, sibling}
        raw = _git(repository, "status", "--porcelain=v1", "-z", "--untracked-files=all")
        status = b"RM" if scenario == "rename_modified" else b"R "
        assert status + b" " + prefix + new + b"\0" + prefix + old + b"\0" in raw
    elif scenario == "native_byte":
        expected_changes = {b"native-\xff.json"}
        write(b"native-\xff.json", b'{"module":"polisyos.foundry.domain.schema"}\n')
        prefix = os.fsencode(directory) + b"/" if directory else b""
        result = subprocess.run(
            [b"git", b"add", b"--", prefix + b"native-\xff.json"],
            cwd=os.fsencode(repository),
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0 and not result.stderr
    else:
        assert scenario == "clean"
    if directory:
        (repository / "outside.json").write_bytes(b'{"outside":true}\n')
    return product, expected_changes


def _run(
    binding_path: Path, binding: dict[str, Any], product: Path, entrypoint: str
) -> dict[str, Any]:
    case = Path(binding["output_dir"]) / (entrypoint + "-" + uuid.uuid4().hex)
    case.mkdir()
    cache = case / "empty-pycache"
    cache.mkdir()
    report = case / "child-origin.json"
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.update(
        PYTHONNOUSERSITE="1",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPYCACHEPREFIX=str(cache),
        C97_CHILD_REPORT=str(report),
        C97_INSTALLED_BINDING=str(binding_path),
        C97_ENTRYPOINT=entrypoint,
    )
    command = (
        [binding["cli"]]
        if entrypoint == "console"
        else [
            binding["python"],
            "-I",
            "-B",
            "-X",
            "pycache_prefix=" + str(cache),
            "-m",
            "tools.cli",
        ]
    )
    command += [
        "validation",
        "schema-fqn-census",
        "--repo-root",
        str(product),
        "--output-format",
        "json",
    ]
    with subprocess.Popen(
        command,
        cwd=binding["neutral_cwd"],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as process:
        try:
            stdout, stderr = process.communicate(timeout=binding["child_timeout_seconds"])
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            (case / "timeout.json").write_text(
                json.dumps({"pid": process.pid, "command": command}) + "\n"
            )
            (case / "stdout.txt").write_bytes(stdout)
            (case / "stderr.txt").write_bytes(stderr)
            pytest.fail("installed child timeout; actual partial outputs retained")
        returncode, pid = process.returncode, process.pid
    (case / "stdout.txt").write_bytes(stdout)
    (case / "stderr.txt").write_bytes(stderr)
    (case / "command.json").write_text(
        json.dumps(
            {
                "command": command,
                "cwd": binding["neutral_cwd"],
                "pid": pid,
                "returncode": returncode,
            }
        )
        + "\n"
    )
    assert report.is_file(), "actual CLI interpreter did not deliver its own origin/profile report"
    child = json.loads(report.read_bytes())
    assert child["pid"] == pid and child["ppid"] == os.getpid()
    assert child["binding_sha256"] == hashlib.sha256(binding_path.read_bytes()).hexdigest()
    assert child["outcome"] == "PASS" and child["errors"] == [], child
    assert child["sitecustomize_sha256"] == binding["observed_sitecustomize_sha256"]
    assert returncode == 0 and not stderr, (command, returncode, stderr)
    assert stdout.isascii(), "these finite byte-name fixtures require ASCII JSON escaping"
    return json.loads(stdout)


@pytest.mark.repo_quality
@pytest.mark.parametrize("entrypoint", ["console", "module"])
@pytest.mark.parametrize("directory", ["", "policy-engine"])
@pytest.mark.parametrize(
    "scenario",
    [
        "staged_pair",
        "unstaged_pair",
        "added_modified_pair",
        "rename",
        "rename_modified",
        "native_byte",
        "clean",
    ],
)
def test_installed_census_exact_git_denominator(
    tmp_path: Path,
    installed_binding: tuple[Path, dict[str, Any]],
    scenario: str,
    directory: str,
    entrypoint: str,
) -> None:
    """The public installed CLI preserves all finite fixture records and bytes."""
    if os.name != "posix":
        pytest.skip("the C97 native invalid-byte contract requires a POSIX environment")
    binding_path, binding = installed_binding
    product, expected_changes = _fixture(tmp_path / "fixture", directory, scenario)
    expected = _oracle(tmp_path / "fixture", product)
    oracle = {
        key: value
        for key, value in expected.items()
        if key in {"commands", "raw_hex", "expected_reads"}
    }
    oracle.update(
        scenario=scenario,
        directory=directory,
        entrypoint=entrypoint,
        expected_changes_hex=sorted(value.hex() for value in expected_changes),
        product=str(product),
    )
    output = Path(binding["output_dir"]) / ("oracle-" + uuid.uuid4().hex + ".json")
    output.write_text(json.dumps(oracle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert expected["changes"] == expected_changes, "fixture/oracle preparation failed"
    receipt = _run(binding_path, binding, product, entrypoint)

    def names(values: list[str]) -> set[bytes]:
        encoded = [os.fsencode(value) for value in values]
        assert len(encoded) == len(set(encoded)), "duplicate reported path"
        assert all(os.fsdecode(value) in values for value in encoded)
        return set(encoded)

    # This is the missing discriminator: frozen M1 keeps selected/read green but
    # must fail this actual changed-path equality (including rename next record).
    assert names(receipt["selection"]["working_tree_changes"]) == expected["changes"]
    assert names(receipt["selection"]["tracked_paths"]) == expected["tracked"]
    assert names(receipt["selection"]["untracked_paths"]) == expected["untracked"]
    assert names(receipt["selection"]["selected_paths"]) == expected["selected"]
    assert names(receipt["scanned_denominator"]["read_paths"]) == expected["selected"]
    assert receipt["selection"]["selected_path_count"] == len(expected["selected"])
    assert receipt["scanned_denominator"]["successful_byte_reads"] == len(expected["selected"])
    assert receipt["scanned_denominator"]["unreadable_paths"] == []
    assert receipt["read_receipt"]["complete_verdict"] is True
    observed = {}
    for row in receipt["read_receipt"]["inputs"]:
        assert row["operation"] == "read_bytes" and row["status"] == "read"
        name = os.fsencode(row["path"])
        assert name.hex() not in observed, "duplicate explicit byte read"
        observed[name.hex()] = {"bytes": row["bytes"], "sha256": row["sha256"]}
    assert observed == expected["expected_reads"]
    assert receipt["selection"]["excluded_paths"] == [
        {"path": "excluded.bin", "reason": "known_binary_suffix"}
    ]
    assert receipt["git_enumeration"]["complete_verdict"] is True
    assert receipt["interpretation_boundary"]["not_a_retirement_authorization"] is True
