"""Behavioral witnesses for the HYG-04 canonical entrypoints and boundaries.

The tests exercise supported compatibility contracts, JAX import ordering,
canonical object identity, lifecycle rejection, and protected workspace and
benchmark surfaces; source-text markers alone are not sufficient evidence.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tomllib
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from tools.lib import imports as tool_imports
from tools.lib.fs import iter_repository_files
from tools.quality.validation import (
    check_docs_lifecycle,
    decomposition_preflight,
)

REPO_ROOT = Path(__file__).resolve().parents[3]

pytestmark = pytest.mark.unit

_FRONTEND_DIR = "front" + "end"
_FRONTEND_README = f"{_FRONTEND_DIR}/README.md"


@pytest.mark.parametrize(
    "entrypoint",
    [
        "tools/research/benchmarks/jax/bench_domain.py",
        "tools/research/benchmarks/jax/bench_simulation.py",
        "tools/research/demos/run_laffer_demo.py",
        "tools/research/demos/run_mechanism_design.py",
    ],
)
@pytest.mark.parametrize(
    ("operator_environment", "expected_platforms"),
    [
        ({}, ("cpu", "cpu")),
        (
            {
                "JAX_PLATFORMS": "metal",
                "JAX_PLATFORM_NAME": "metal",
                "POLICY_ENGINE_ALLOW_JAX_METAL": "1",
            },
            ("metal", "metal"),
        ),
        (
            {"JAX_PLATFORMS": "metal", "POLICY_ENGINE_ALLOW_JAX_METAL": "1"},
            ("metal", None),
        ),
        (
            {
                "JAX_PLATFORM_NAME": "metal",
                "POLICY_ENGINE_ALLOW_JAX_METAL": "1",
            },
            (None, "metal"),
        ),
    ],
)
def test_jax_research_entrypoints_apply_defaults_before_jax_stack(
    entrypoint: str,
    operator_environment: dict[str, str],
    expected_platforms: tuple[str | None, str | None],
) -> None:
    """JAX research entrypoints apply defaults before loading numerical dependencies."""

    probe = f"""
import builtins
import os
import runpy
import sys

from polisyos.common import jax_env

sys.platform = "darwin"
for name in (
    "JAX_PLATFORMS",
    "JAX_PLATFORM_NAME",
    "POLICY_ENGINE_ALLOW_JAX_METAL",
):
    os.environ.pop(name, None)
os.environ.update({operator_environment!r})

expected = {expected_platforms!r}
applied = []
original_apply = jax_env.apply_jax_env_defaults

def record_defaults():
    original_apply()
    applied.append((os.environ.get("JAX_PLATFORMS"), os.environ.get("JAX_PLATFORM_NAME")))

jax_env.apply_jax_env_defaults = record_defaults
original_import = builtins.__import__

class ReachedNumericalStack(Exception):
    pass

def stop_before_numerical_stack(name, *args, **kwargs):
    reaches_numerical_stack = (
        name == "numpy"
        or name.startswith("numpy.")
        or name == "jax"
        or name.startswith("jax.")
        or name == "jaxlib"
        or name.startswith("jaxlib.")
        or name == "equinox"
    )
    if reaches_numerical_stack:
        observed = (os.environ.get("JAX_PLATFORMS"), os.environ.get("JAX_PLATFORM_NAME"))
        if observed != expected:
            raise AssertionError((name, observed, expected))
        if applied != [expected]:
            raise AssertionError((name, applied))
        raise ReachedNumericalStack(name)
    return original_import(name, *args, **kwargs)

builtins.__import__ = stop_before_numerical_stack
try:
    entrypoint_namespace = runpy.run_path(
        {str(REPO_ROOT / entrypoint)!r}, run_name="jax_order_probe"
    )
    run_benchmarks = entrypoint_namespace.get("run_benchmarks")
    if run_benchmarks is not None:
        main = entrypoint_namespace.get("main")
        if main is None:
            raise AssertionError("benchmark runner has no direct command entrypoint")
        sys.argv = [
            {str(REPO_ROOT / entrypoint)!r},
            "--warmup",
            "0",
            "--repeat",
            "1",
        ]
        main()
except ReachedNumericalStack:
    pass
else:
    raise AssertionError("entrypoint never reached a guarded numerical import")
if applied != [expected]:
    raise AssertionError(applied)
if any(name == "jax" or name.startswith("jax.") for name in sys.modules):
    raise AssertionError("JAX imported before the guarded bootstrap boundary")
"""
    environment = os.environ.copy()
    for name in (
        "JAX_PLATFORMS",
        "JAX_PLATFORM_NAME",
        "POLICY_ENGINE_ALLOW_JAX_METAL",
    ):
        environment.pop(name, None)
    environment.update(operator_environment)
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(
            None,
            (
                str(REPO_ROOT),
                str(REPO_ROOT / "src"),
                environment.get("PYTHONPATH", ""),
            ),
        )
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_workspace_bootstrap_subprocess_exposes_real_profiles(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The registered public command forwards each profile to canonical bootstrap."""

    from tools.cli import main as tools_cli_main
    from tools.devx.workspace import bootstrap

    capture = tmp_path / "uv-argv.txt"
    fake_uv = tmp_path / "uv"
    fake_uv.write_text(
        '#!/bin/sh\nprintf \'%s\\n\' "$@" > "$HYG04_BOOTSTRAP_CAPTURE"\n',
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)
    monkeypatch.setenv("HYG04_BOOTSTRAP_CAPTURE", str(capture))
    monkeypatch.setattr(bootstrap, "_ensure_python_baseline", lambda: None)
    monkeypatch.setattr(bootstrap, "_ensure_uv_available", lambda **_: None)
    monkeypatch.setattr(bootstrap, "_ensure_node_baseline", lambda **_: None)
    monkeypatch.setattr(bootstrap, "uv_command", lambda: (str(fake_uv),))

    expected_profiles = {
        "minimal": ("lint", "test"),
        "docs": ("lint", "docs"),
        "runtime": ("lint", "test", "runtime"),
        "research": ("lint", "test", "runtime", "research"),
    }
    for profile, extras in expected_profiles.items():
        expected_argv = ["sync", "--frozen"]
        for extra in extras:
            expected_argv.extend(("--extra", extra))
        assert (
            tools_cli_main(
                [
                    "workspace",
                    "bootstrap",
                    "--skip-preflight",
                    "--timing-log",
                    str(tmp_path / "bootstrap-timing.jsonl"),
                    "--profile",
                    profile,
                    "--skip-frontend",
                    "--skip-hooks",
                    "--skip-doctor",
                    "--no-install-uv",
                ]
            )
            == 0
        )
        assert capture.read_text(encoding="utf-8").splitlines() == expected_argv


@pytest.mark.parametrize(
    ("malformed_sentinel", "malformed_type"),
    [("pyproject.toml", "directory"), ("tools", "file"), ("src", "file")],
)
def test_repo_root_resolution_rejects_malformed_sentinel_layouts(
    tmp_path: Path,
    malformed_sentinel: str,
    malformed_type: str,
) -> None:
    """Root lookup requires expected file and directory types, not just names."""

    fake_root = tmp_path / f"malformed-{malformed_sentinel.replace('.', '-')}"
    fake_root.mkdir()
    for sentinel in ("pyproject.toml", "tools", "src"):
        path = fake_root / sentinel
        if sentinel == malformed_sentinel:
            if malformed_type == "directory":
                path.mkdir()
            else:
                path.write_text("not a directory", encoding="utf-8")
        elif sentinel == "pyproject.toml":
            path.write_text("[project]\nname = 'decoy'\n", encoding="utf-8")
        else:
            path.mkdir()

    fake_module = fake_root / "fake_module.py"
    fake_module.touch()

    with pytest.raises(ValueError, match="Could not infer repository root"):
        tool_imports.repo_root_from(fake_module)


def test_repo_root_resolution_accepts_current_product_layout() -> None:
    """The actual product source path still resolves to its workspace root."""

    assert tool_imports.repo_root_from(__file__) == REPO_ROOT


def test_benchmark_shims_preserve_canonical_object_identity() -> None:
    """Legacy benchmark imports must expose the root implementation objects."""

    from benchmarks import harness as canonical_harness
    from benchmarks import metrics as canonical_metrics
    from benchmarks import suite_registry as canonical_registry
    from tools.research.benchmarks import harness as legacy_harness
    from tools.research.benchmarks import metrics as legacy_metrics
    from tools.research.benchmarks import suite_registry as legacy_registry

    assert legacy_harness.BenchmarkHarness is canonical_harness.BenchmarkHarness
    assert legacy_metrics.compute_timing_stats is canonical_metrics.compute_timing_stats
    assert legacy_registry.SuiteSpec is canonical_registry.SuiteSpec
    assert legacy_registry.canonical_suite_id is canonical_registry.canonical_suite_id


def test_benchmark_suite_registry_shim_forwards_cli_and_exit_code() -> None:
    """The legacy script path must preserve canonical CLI output and failures."""

    wrapper = REPO_ROOT / "tools/research/benchmarks/suite_registry.py"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(
            None,
            (str(REPO_ROOT), str(REPO_ROOT / "src"), environment.get("PYTHONPATH", "")),
        )
    )

    valid = subprocess.run(
        [sys.executable, str(wrapper), "--profile", "air-m2", "--format", "json"],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert valid.returncode == 0, valid.stderr
    payload = json.loads(valid.stdout)
    assert payload
    assert all("air-m2" in item["profiles"] for item in payload)
    assert all({"suite_id", "script_path", "profiles"} <= set(item) for item in payload)

    invalid = subprocess.run(
        [sys.executable, str(wrapper), "--format", "not-a-format"],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert invalid.returncode == 2
    assert "invalid choice" in invalid.stderr


def _module_targets(address: str, target_modules: set[str]) -> set[str]:
    return {
        target for target in target_modules if address == target or address.startswith(f"{target}.")
    }


def _bound_loader_arguments(
    call: ast.Call,
    function_name: str,
) -> tuple[dict[str, ast.AST | None], str | None]:
    """Bind the documented name/package/level slots of the three supported loaders."""

    parameter_slots = {
        "importlib.import_module": {"name": 0, "package": 1},
        "builtins.__import__": {"name": 0, "level": 4},
        "runpy.run_module": {"mod_name": 0},
    }
    slots = parameter_slots[function_name]
    arguments: dict[str, ast.AST | None] = {}
    if any(isinstance(argument, ast.Starred) for argument in call.args):
        return arguments, "starred positional expansion prevents complete argument binding"
    for parameter, position in slots.items():
        positional = call.args[position] if len(call.args) > position else None
        keywords = [keyword.value for keyword in call.keywords if keyword.arg == parameter]
        if positional is not None and isinstance(positional, ast.Starred):
            return arguments, f"starred positional {parameter} argument"
        if (positional is not None and keywords) or len(keywords) > 1:
            return arguments, f"multiple {parameter} bindings"
        arguments[parameter] = (
            positional if positional is not None else (keywords[0] if keywords else None)
        )
    if any(keyword.arg is None for keyword in call.keywords):
        return arguments, "keyword expansion prevents complete argument binding"
    return arguments, None


def _target_related_fragments(
    fragments: set[str],
    target_modules: set[str],
) -> bool:
    target_names = {target.rsplit(".", 1)[-1] for target in target_modules}
    for fragment in fragments:
        normalized = fragment.lstrip(".")
        if _module_targets(normalized, target_modules):
            return True
        if fragment.startswith(".") and normalized.rsplit(".", 1)[-1] in target_names:
            return True
        if len(normalized) >= 5 and any(
            normalized in target or target in normalized for target in target_modules
        ):
            return True
    return False


def _relative_import_target_name(
    address: str,
    target_modules: set[str],
) -> bool:
    target_names = {target.rsplit(".", 1)[-1] for target in target_modules}
    return (
        _target_related_fragments({address}, target_modules)
        or address.lstrip(".").rsplit(".", 1)[-1] in target_names
    )


def _tracked_python_reference_inventory(
    repo_root: Path,
    target_modules: set[str],
) -> dict[str, object]:
    """Declare every tracked .py/.pyi path as the AST input set."""

    repo_root = repo_root.resolve()
    tracked_files = tuple(iter_repository_files(repo_root))
    tracked_paths = {path.relative_to(repo_root).as_posix() for path in tracked_files}
    tracked_suffix_counts = Counter(
        path.suffix.lower() or "<extensionless>" for path in tracked_files
    )
    python_paths = {
        path.relative_to(repo_root).as_posix()
        for path in tracked_files
        if path.suffix.lower() in {".py", ".pyi"}
    }
    python_suffix_counts = Counter(Path(path).suffix.lower() for path in python_paths)
    assert sum(tracked_suffix_counts.values()) == len(tracked_files)
    assert sum(python_suffix_counts.values()) == len(python_paths)
    assert python_paths <= tracked_paths
    return {
        "tracked_paths": tracked_paths,
        "tracked_file_count": len(tracked_files),
        "tracked_suffix_counts": dict(sorted(tracked_suffix_counts.items())),
        "tracked_python_paths": python_paths,
        "tracked_python_denominator": len(python_paths),
        # Compatibility fields now describe the full analyzed set; there is no
        # git-grep candidate selector in this census.
        "matched_paths": python_paths,
        "matched_path_count": len(python_paths),
        "matched_suffix_counts": dict(sorted(python_suffix_counts.items())),
        "python_candidate_paths": python_paths,
        "python_candidate_count": len(python_paths),
        "token_python_candidate_count": 0,
        "input_selector": "all tracked .py and .pyi paths from iter_repository_files",
    }


def _python_import_package(repo_root: Path, path: Path) -> str:
    relative_parent = path.relative_to(repo_root).parent
    return ".".join(relative_parent.parts)


def _hyg_ast_coverage(tree: ast.Module) -> tuple[dict[str, int], list[dict[str, object]]]:
    """Reconcile encountered value expressions and binder contexts to a route."""
    nodes = tuple(ast.walk(tree))
    counts = Counter(type(node).__name__ for node in nodes)
    parents = {id(child): parent for parent in nodes for child in ast.iter_child_nodes(parent)}
    supported_expressions = {
        "Constant",
        "Name",
        "BinOp",
        "IfExp",
        "BoolOp",
        "Tuple",
        "List",
        "Set",
        "Dict",
        "Subscript",
        "UnaryOp",
        "Compare",
        "NamedExpr",
        "Starred",
    }
    # Every other encountered ast.expr is explicitly refused by the R8 value
    # evaluator's generic unknown fallback; record that path instead of dropping it.
    explicit_refusal_expressions = {
        "Attribute",
        "Call",
        "FormattedValue",
        "JoinedStr",
        "Lambda",
        "ListComp",
        "SetComp",
        "DictComp",
        "GeneratorExp",
        "Await",
        "Yield",
        "YieldFrom",
        "Slice",
        "TemplateStr",
        "Interpolation",
    }
    binder_classes = {
        "Assign",
        "AnnAssign",
        "AugAssign",
        "NamedExpr",
        "For",
        "AsyncFor",
        "comprehension",
        "With",
        "AsyncWith",
        "withitem",
        "FunctionDef",
        "AsyncFunctionDef",
        "Lambda",
        "ClassDef",
        "Import",
        "ImportFrom",
        "ExceptHandler",
        "Delete",
        "Match",
        "MatchAs",
        "MatchStar",
        "MatchMapping",
        "MatchSequence",
        "MatchClass",
        "MatchOr",
        "arguments",
        "arg",
        "alias",
        "TypeAlias",
        "TypeVar",
        "ParamSpec",
        "TypeVarTuple",
        "Global",
        "Nonlocal",
    }
    failures: list[dict[str, object]] = []
    for node in nodes:
        if isinstance(node, ast.expr):
            if type(node).__name__ not in supported_expressions | explicit_refusal_expressions:
                failures.append(
                    {
                        "line": getattr(node, "lineno", 0),
                        "node": type(node).__name__,
                        "reason": "expression class has no transfer/refusal route",
                    }
                )
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            parent = parents.get(id(node))
            while isinstance(parent, (ast.Tuple, ast.List, ast.Starred)):
                parent = parents.get(id(parent))
            if parent is None or type(parent).__name__ not in binder_classes:
                failures.append(
                    {
                        "line": node.lineno,
                        "node": type(parent).__name__ if parent else None,
                        "reason": "store target has no binding-form route",
                    }
                )
        if isinstance(node, ast.arg) and "arg" not in binder_classes:
            failures.append(
                {
                    "line": node.lineno,
                    "node": "arg",
                    "reason": "formal parameter has no binding-form route",
                }
            )
    return dict(sorted(counts.items())), failures


def _hyg_namespace_residuals(tree: ast.Module, relative: str) -> list[dict[str, object]]:
    """Report actual dynamic namespace/code execution uses as bounded residuals."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "builtins":
                    aliases[alias.asname or "builtins"] = "builtins"
        elif isinstance(node, ast.ImportFrom) and node.module == "builtins":
            for alias in node.names:
                if alias.name in {"exec", "eval", "globals", "locals", "vars"}:
                    aliases[alias.asname or alias.name] = alias.name
    residuals: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            symbol = None
            if isinstance(node.func, ast.Name):
                symbol = aliases.get(node.func.id, node.func.id)
            elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                base = aliases.get(node.func.value.id, node.func.value.id)
                if base == "builtins":
                    symbol = node.func.attr
            if symbol in {"exec", "eval", "globals", "locals", "vars"}:
                residuals.append(
                    {
                        "path": relative,
                        "line": node.lineno,
                        "kind": symbol,
                        "reason": "dynamic namespace/code path is outside static source-value proof",
                    }
                )
        elif isinstance(node, ast.ClassDef):
            for keyword in node.keywords:
                if (
                    keyword.arg == "metaclass"
                    and not (isinstance(keyword.value, ast.Name) and keyword.value.id == "type")
                    and not (
                        isinstance(keyword.value, ast.Attribute)
                        and keyword.value.attr == "type"
                        and isinstance(keyword.value.value, ast.Name)
                        and keyword.value.value.id == "builtins"
                    )
                ):
                    residuals.append(
                        {
                            "path": relative,
                            "line": node.lineno,
                            "kind": "custom_metaclass",
                            "reason": "custom class namespace effects are bounded",
                        }
                    )
    return residuals


def _source_value_strings(binding: object) -> set[str]:
    """Read exact string alternatives from the shared R8 value lattice."""
    kind = getattr(binding, "kind", None)
    if kind == "string":
        name = getattr(binding, "name", None)
        return {name} if isinstance(name, str) else set()
    if kind == "union":
        items = getattr(binding, "items", None)
        return set().union(*(_source_value_strings(item) for item in items or ()))
    return set()


def _source_value_has_unknown(binding: object) -> bool:
    """Unknown stays open through a union or retained sequence/mapping shape."""
    kind = getattr(binding, "kind", None)
    if binding is None or kind in {"unknown", "ambiguous"}:
        return True
    if kind == "union":
        items = getattr(binding, "items", None)
        return items is None or any(_source_value_has_unknown(item) for item in items)
    if kind in {"sequence", "iterable"}:
        items = getattr(binding, "items", None)
        return items is None or any(_source_value_has_unknown(item) for item in items)
    if kind == "mapping":
        keys = getattr(binding, "items", None)
        values = getattr(binding, "values", None)
        return (
            keys is None
            or values is None
            or any(_source_value_has_unknown(item) for item in (*keys, *values))
        )
    return False


def _source_value_slot(
    call: ast.Call,
    argument: ast.AST,
) -> str | None:
    for index, value in enumerate(call.args):
        if value is argument:
            return f"positional:{index}"
    for keyword in call.keywords:
        if keyword.value is argument:
            return f"keyword:{keyword.arg}" if keyword.arg is not None else "keyword:**"
    return None


def _scan_tracked_python_callers(
    repo_root: Path,
    target_modules: set[str],
    reference_inventory: dict[str, object],
) -> dict[str, object]:
    """Join every tracked Python call to R8's source/value context owner."""
    repo_root = repo_root.resolve()
    tracked_files = tuple(iter_repository_files(repo_root))
    declared_paths = reference_inventory["python_candidate_paths"]
    assert isinstance(declared_paths, set)
    input_paths = {
        path.relative_to(repo_root).as_posix(): path
        for path in tracked_files
        if path.suffix.lower() in {".py", ".pyi"}
    }
    assert set(input_paths) == declared_paths

    caller_targets: dict[str, set[str]] = {}
    dynamic_callers: list[dict[str, object]] = []
    parse_failures: list[dict[str, str]] = []
    source_scope_failures: list[dict[str, str]] = []
    unresolved: list[dict[str, object]] = []
    trees: dict[str, ast.Module] = {}
    module_paths: dict[str, Path] = {}
    relative_for_module: dict[str, str] = {}
    call_index: dict[tuple[str, int, int], tuple[str, ast.Call]] = {}
    target_parents = {target.rpartition(".")[0] for target in target_modules}
    ast_node_counts: Counter[str] = Counter()
    coverage_failures: list[dict[str, object]] = []
    namespace_residuals: list[dict[str, object]] = []
    supported_loaders = {
        "importlib.import_module",
        "builtins.__import__",
        "runpy.run_module",
    }
    dynamic_namespace_builtins = {"eval", "exec", "compile", "globals", "locals"}

    # Parse every declared .py/.pyi input; the token index is not a selector.
    for relative, path in sorted(input_paths.items()):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except (OSError, UnicodeError, SyntaxError, ValueError, RecursionError) as error:
            parse_failures.append({"path": relative, "error": f"{type(error).__name__}: {error}"})
            continue
        module = "__hyg_source__." + hashlib.sha256(relative.encode("utf-8")).hexdigest()
        trees[module] = tree
        module_paths[module] = path
        relative_for_module[module] = relative
        file_node_counts, file_coverage_failures = _hyg_ast_coverage(tree)
        ast_node_counts.update(file_node_counts)
        coverage_failures.extend({"path": relative, **row} for row in file_coverage_failures)
        namespace_residuals.extend(_hyg_namespace_residuals(tree, relative))

        # Direct import statements retain the existing HYG normalization behavior.
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call_index[(module, node.lineno, node.col_offset)] = (relative, node)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    caller_targets.setdefault(relative, set()).update(
                        _module_targets(alias.name, target_modules)
                    )
            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                if node.level:
                    package = _python_import_package(repo_root, path)
                    try:
                        module_name = importlib.util.resolve_name(
                            "." * node.level + module_name, package
                        )
                    except (ImportError, ValueError):
                        module_name = ""
                direct_matches = _module_targets(module_name, target_modules)
                if direct_matches:
                    caller_targets.setdefault(relative, set()).update(direct_matches)
                for alias in node.names:
                    if alias.name == "*":
                        if module_name in target_parents:
                            caller_targets.setdefault(relative, set()).update(target_modules)
                        continue
                    caller_targets.setdefault(relative, set()).update(
                        _module_targets(f"{module_name}.{alias.name}", target_modules)
                    )

        # Retain R8's explicit refusals for guarded source operations. Its selected
        # sink-site inventory no longer controls which calls reach the value owner.
        scanner = decomposition_preflight._DynamicImportSourceScanner(path, relative_path=relative)
        try:
            scanner.scan_with_sites(tree)
        except decomposition_preflight.DynamicImportCollectionError as error:
            source_scope_failures.append({"path": relative, "error": str(error)})

    source_observations: list[dict[str, object]] = []
    missing_observations: list[dict[str, object]] = []
    if not parse_failures:
        source_observations, missing_observations = (
            decomposition_preflight.collect_source_value_call_observations(
                trees, module_paths, value_target_names=supported_loaders
            )
        )
    for row in missing_observations:
        module = str(row.get("module", ""))
        unresolved.append(
            {
                "path": relative_for_module.get(module, module),
                "line": row.get("line"),
                "reason": str(row.get("reason", "declared AST call has no R8 observation")),
                "kind": "missing source-call observation",
            }
        )

    observation_index = {
        (str(row["module"]), int(row["line"]), int(row["column"])): row
        for row in source_observations
    }
    observed_call_ids = set(observation_index)
    declared_call_ids = set(call_index)
    if observed_call_ids != declared_call_ids:
        for module, line, column in sorted(declared_call_ids - observed_call_ids):
            relative, _call = call_index[(module, line, column)]
            unresolved.append(
                {
                    "path": relative,
                    "line": line,
                    "reason": "declared AST call has no joined R8 target/value observation",
                    "kind": "missing source-call observation",
                }
            )

    loader_call_ids: set[tuple[str, int, int]] = set()
    unknown_calltarget_ids: set[tuple[str, int, int]] = set()
    unsupported_calltarget_ids: set[tuple[str, int, int]] = set()
    for key, (relative, call) in sorted(call_index.items()):
        observation = observation_index.get(key)
        if observation is None:
            continue
        raw_targets = observation.get("call_targets", [])
        targets = raw_targets if isinstance(raw_targets, list) else []
        recognized_loaders: set[str] = set()
        unsupported_targets: list[str] = []
        for target in targets:
            if not isinstance(target, dict):
                unsupported_targets.append("malformed R8 call-target row")
                continue
            kind = target.get("kind")
            module = target.get("module")
            symbol = target.get("symbol")
            if kind == "import" and isinstance(module, str) and isinstance(symbol, str):
                qualified = f"{module}.{symbol}"
                if qualified in supported_loaders:
                    recognized_loaders.add(qualified)
                else:
                    unsupported_targets.append(f"opaque imported callable {qualified}")
            elif kind == "builtin" and module == "builtins" and isinstance(symbol, str):
                if symbol == "__import__":
                    recognized_loaders.add("builtins.__import__")
                elif symbol in dynamic_namespace_builtins:
                    unsupported_targets.append(f"dynamic namespace builtin {symbol}")
            elif kind == "callable" and module in trees:
                # R8 has resolved this target to a source-owned callable. Its body
                # is walked by the same owner; a transferred loader formal appears
                # at the inner call site as an exact import target.
                continue
            else:
                unsupported_targets.append(f"unmodeled call target {kind!r}")

        target_unknown = observation.get("call_target_unknown") is not False
        if target_unknown:
            unknown_calltarget_ids.add(key)
            unresolved.append(
                {
                    "path": relative,
                    "line": call.lineno,
                    "reason": "call target has an unknown alternative",
                    "kind": "unknown call target",
                }
            )
        if unsupported_targets:
            unsupported_calltarget_ids.add(key)
            unresolved.append(
                {
                    "path": relative,
                    "line": call.lineno,
                    "reason": "; ".join(sorted(set(unsupported_targets))),
                    "kind": "unsupported call target",
                }
            )
        if not targets and not target_unknown:
            unsupported_calltarget_ids.add(key)
            unresolved.append(
                {
                    "path": relative,
                    "line": call.lineno,
                    "reason": "call observation has neither a target nor explicit unknown",
                    "kind": "unsupported call target",
                }
            )

        slots = observation.get("slots", {})
        for function_name in sorted(recognized_loaders):
            loader_call_ids.add(key)
            arguments, binding_error = _bound_loader_arguments(call, function_name)
            if binding_error is not None:
                unresolved.append(
                    {
                        "path": relative,
                        "line": call.lineno,
                        "sink": function_name,
                        "reason": binding_error,
                    }
                )
                continue
            name_parameter = "mod_name" if function_name == "runpy.run_module" else "name"
            address_node = arguments.get(name_parameter)
            if address_node is None:
                unresolved.append(
                    {
                        "path": relative,
                        "line": call.lineno,
                        "sink": function_name,
                        "reason": "loader name argument is absent/unbound",
                    }
                )
                continue
            address_slot = _source_value_slot(call, address_node)
            binding = slots.get(address_slot) if isinstance(slots, dict) and address_slot else None
            if binding is None:
                unresolved.append(
                    {
                        "path": relative,
                        "line": call.lineno,
                        "sink": function_name,
                        "formal_or_slot": address_slot,
                        "reason": "loader argument has no source-value payload",
                    }
                )
                continue
            exact_addresses = _source_value_strings(binding)
            unknown_value = _source_value_has_unknown(binding)
            fragments = set(exact_addresses)
            fragments.update(
                child.value
                for child in ast.walk(address_node)
                if isinstance(child, ast.Constant) and isinstance(child.value, str)
            )

            normalized_addresses: set[str] = set()
            for address in exact_addresses:
                if function_name == "importlib.import_module" and address.startswith("."):
                    package_node = arguments.get("package")
                    package_slot = _source_value_slot(call, package_node) if package_node else None
                    package_binding = (
                        slots.get(package_slot)
                        if isinstance(slots, dict) and package_slot
                        else None
                    )
                    package_values = (
                        _source_value_strings(package_binding) if package_binding else set()
                    )
                    if not package_values or _source_value_has_unknown(package_binding):
                        unknown_value = True
                        continue
                    for package in package_values:
                        try:
                            normalized_addresses.add(importlib.util.resolve_name(address, package))
                        except (ImportError, ValueError):
                            unknown_value = True
                elif function_name == "builtins.__import__":
                    level_node = arguments.get("level")
                    if level_node is None:
                        level = 0
                    elif isinstance(level_node, ast.Constant) and isinstance(level_node.value, int):
                        level = level_node.value
                    else:
                        level = None
                    if level != 0:
                        if _relative_import_target_name(address, target_modules):
                            unknown_value = True
                        continue
                    normalized_addresses.add(address)
                elif function_name == "runpy.run_module" and address.startswith("."):
                    if _relative_import_target_name(address, target_modules):
                        unknown_value = True
                    continue
                else:
                    normalized_addresses.add(address)

            matches = (
                set().union(
                    *(_module_targets(address, target_modules) for address in normalized_addresses)
                )
                if normalized_addresses
                else set()
            )
            if matches:
                caller_targets.setdefault(relative, set()).update(matches)
                for address in sorted(normalized_addresses):
                    if _module_targets(address, target_modules):
                        dynamic_callers.append(
                            {
                                "path": relative,
                                "line": call.lineno,
                                "function": function_name,
                                "address": address,
                            }
                        )
            if unknown_value:
                unresolved.append(
                    {
                        "path": relative,
                        "line": call.lineno,
                        "sink": function_name,
                        "formal_or_slot": address_slot,
                        "reason": "source value contains unknown alternative",
                        "fragments": sorted(fragments),
                    }
                )
            elif not exact_addresses and getattr(binding, "kind", None) not in {
                "other",
                "boolean",
                "none",
                "sequence",
                "iterable",
                "mapping",
            }:
                unresolved.append(
                    {
                        "path": relative,
                        "line": call.lineno,
                        "sink": function_name,
                        "formal_or_slot": address_slot,
                        "reason": ("empty/unclassified sink value is not a non-target proof"),
                        "fragments": sorted(fragments),
                    }
                )

    unresolved.extend(
        {"path": row["path"], "reason": row["error"], "kind": "R8 sink-scan refusal"}
        for row in source_scope_failures
    )
    unresolved.extend(
        {**row, "kind": "bounded dynamic namespace residual"} for row in namespace_residuals
    )
    unresolved.extend({**row, "kind": "unclassified source syntax"} for row in coverage_failures)
    bounded_complete = (
        not parse_failures
        and not source_scope_failures
        and not namespace_residuals
        and not coverage_failures
        and set(input_paths) == set(declared_paths)
        and declared_call_ids == observed_call_ids
        and not unresolved
    )
    return {
        "status": "BOUNDED_COMPLETE" if bounded_complete else "BOUNDED_INCOMPLETE",
        "bounded_source_grammar": [
            "tracked .py/.pyi AST calls observed by the R8 source-owned worklist",
            "exact recognized dynamic-loader identities and closed source-value alternatives",
            "source-owned call-target/formal transfers resolved by the shared owner",
        ],
        "bounded_unknowns": [
            "opaque imported or returned callable targets",
            "unobserved AST calls, dynamic namespace/code-generation "
            "boundaries, and unsupported values",
        ],
        "tracked_python_denominator": reference_inventory["tracked_python_denominator"],
        "tracked_python_input_count": len(input_paths),
        "declared_python_paths": sorted(declared_paths),
        "parsed_python_paths": sorted(
            relative for module, relative in relative_for_module.items() if module in trees
        ),
        "lexical_python_candidate_count": len(input_paths),
        "token_python_candidate_count": reference_inventory["token_python_candidate_count"],
        "ast_call_count": len(declared_call_ids),
        "source_value_observation_count": len(observed_call_ids),
        "loader_call_count": len(loader_call_ids),
        "unknown_calltarget_count": len(unknown_calltarget_ids),
        "unsupported_calltarget_count": len(unsupported_calltarget_ids),
        "source_scope_failures": source_scope_failures,
        "namespace_residuals": namespace_residuals,
        "ast_node_counts": dict(sorted(ast_node_counts.items())),
        "coverage_failures": coverage_failures,
        "parse_failures": parse_failures,
        "unresolved": unresolved,
        "callers": {
            path: sorted(targets) for path, targets in sorted(caller_targets.items()) if targets
        },
        "dynamic_callers": sorted(
            dynamic_callers,
            key=lambda row: (str(row["path"]), int(row["line"]), str(row["function"])),
        ),
    }


def test_benchmark_wrapper_caller_census_is_bounded_and_fails_closed() -> None:
    """Derive source callers without claiming closure over opaque call targets."""

    legacy_modules = {
        "harness": "tools.research.benchmarks.harness",
        "metrics": "tools.research.benchmarks.metrics",
        "suite_registry": "tools.research.benchmarks.suite_registry",
    }
    target_modules = set(legacy_modules.values())
    inventory = _tracked_python_reference_inventory(REPO_ROOT, target_modules)
    tracked_files = tuple(iter_repository_files(REPO_ROOT))
    tracked_paths = inventory["tracked_paths"]
    matched_paths = inventory["matched_paths"]
    assert isinstance(tracked_paths, set) and isinstance(matched_paths, set)
    assert inventory["tracked_file_count"] == len(tracked_files)
    assert sum(inventory["tracked_suffix_counts"].values()) == len(tracked_files)
    assert inventory["tracked_python_denominator"] == sum(
        path.suffix.lower() in {".py", ".pyi"} for path in tracked_files
    )
    assert inventory["matched_path_count"] == len(matched_paths)
    assert sum(inventory["matched_suffix_counts"].values()) == len(matched_paths)
    assert matched_paths <= tracked_paths
    assert "tests/unit/remediation/test_hyg_04.py" in matched_paths

    caller_census = _scan_tracked_python_callers(
        REPO_ROOT,
        target_modules,
        inventory,
    )
    assert caller_census["tracked_python_denominator"] == inventory["tracked_python_denominator"]
    assert caller_census["lexical_python_candidate_count"] == len(
        inventory["python_candidate_paths"]
    )
    assert caller_census["tracked_python_input_count"] == inventory["tracked_python_denominator"]
    assert set(caller_census["declared_python_paths"]) == set(caller_census["parsed_python_paths"])
    assert caller_census["parse_failures"] == [], caller_census["parse_failures"]
    assert caller_census["status"] == "BOUNDED_INCOMPLETE"
    assert caller_census["source_value_observation_count"] <= caller_census["ast_call_count"]
    assert caller_census["unresolved"], "opaque call targets must keep the census bounded"
    callers = caller_census["callers"]
    assert isinstance(callers, dict)
    assert set(callers) == {"tests/unit/remediation/test_hyg_04.py"}
    assert callers["tests/unit/remediation/test_hyg_04.py"] == sorted(target_modules)

    with TemporaryDirectory() as temporary_root:
        fixture_root = Path(temporary_root)
        subprocess.run(["git", "init", "--quiet"], cwd=fixture_root, check=True)
        (fixture_root / "baseline.py").write_text("value = 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "baseline.py"], cwd=fixture_root, check=True)
        baseline_inventory = _tracked_python_reference_inventory(
            fixture_root,
            target_modules,
        )
        baseline = _scan_tracked_python_callers(
            fixture_root,
            target_modules,
            baseline_inventory,
        )
        assert baseline["callers"] == {}
        assert baseline["parse_failures"] == []
        assert baseline["unresolved"] == []

        (fixture_root / "actual_caller.py").write_text(
            "import importlib as loader\n"
            "import runpy as runner\n"
            "import builtins as native\n"
            "from importlib import import_module as load_module\n"
            "from runpy import run_module as execute_module\n"
            "import tools.research.benchmarks.harness as direct_harness\n"
            'loader.import_module("tools.research." + "benchmarks.metrics")\n'
            'load_module("tools.research.benchmarks.suite_registry")\n'
            'native.__import__("tools.research.benchmarks.harness")\n'
            'execute_module("tools.research.benchmarks.metrics")\n'
            'runner.run_module("tools.research.benchmarks.suite_registry")\n'
            'loader.import_module(name=".metrics", package="tools.research.benchmarks")\n'
            'load_module(name="tools.research.benchmarks.harness")\n'
            'native.__import__(name="tools.research.benchmarks.metrics")\n'
            'runner.run_module(mod_name="tools.research.benchmarks.suite_registry")\n'
            "_ = direct_harness\n",
            encoding="utf-8",
        )
        relative_source = fixture_root / "tools/research/benchmarks/consumer.py"
        relative_source.parent.mkdir(parents=True)
        relative_source.write_text(
            "from . import metrics as legacy_metrics\n",
            encoding="utf-8",
        )
        (fixture_root / "typed_caller.pyi").write_text(
            "from tools.research.benchmarks import metrics as benchmark_metrics\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "add", "actual_caller.py", "typed_caller.pyi", str(relative_source)],
            cwd=fixture_root,
            check=True,
        )
        inserted_inventory = _tracked_python_reference_inventory(
            fixture_root,
            target_modules,
        )
        assert "actual_caller.py" in inserted_inventory["python_candidate_paths"]
        assert (
            "tools/research/benchmarks/consumer.py" in inserted_inventory["python_candidate_paths"]
        )
        inserted = _scan_tracked_python_callers(
            fixture_root,
            target_modules,
            inserted_inventory,
        )
        assert inserted["callers"] == {
            "actual_caller.py": sorted(target_modules),
            "tools/research/benchmarks/consumer.py": [legacy_modules["metrics"]],
            "typed_caller.pyi": [legacy_modules["metrics"]],
        }
        assert inserted["parse_failures"] == []
        assert inserted["unresolved"] == []
        dynamic_targets = {
            row["address"] for row in inserted["dynamic_callers"] if isinstance(row, dict)
        }
        assert dynamic_targets == target_modules

        local_assignment_target = fixture_root / "local_assignment_target.py"
        local_assignment_target.write_text(
            "import importlib\n"
            "def load():\n"
            '    name = "tools.research.benchmarks.metrics"\n'
            "    importlib.import_module(name)\n",
            encoding="utf-8",
        )
        block_assignment_target = fixture_root / "block_assignment_target.py"
        block_assignment_target.write_text(
            "import importlib\n"
            "if enabled:\n"
            '    module_name = "tools.research.benchmarks.harness"\n'
            "importlib.import_module(module_name)\n",
            encoding="utf-8",
        )
        alias_assignment_target = fixture_root / "alias_assignment_target.py"
        alias_assignment_target.write_text(
            "import importlib\n"
            "def load():\n"
            '    prefix = "tools.research."\n'
            '    module_name = prefix + "benchmarks.suite_registry"\n'
            "    alias = module_name\n"
            "    importlib.import_module(alias)\n",
            encoding="utf-8",
        )
        ambiguous_local_target = fixture_root / "ambiguous_local_target.py"
        ambiguous_local_target.write_text(
            "import importlib\n"
            "def load():\n"
            '    module_name = "tools.research.benchmarks.metrics"\n'
            "    if enabled:\n"
            "        module_name = discover_module_name()\n"
            "    importlib.import_module(module_name)\n",
            encoding="utf-8",
        )
        unrelated_local_binding = fixture_root / "unrelated_local_binding.py"
        unrelated_local_binding.write_text(
            "import importlib\n"
            "def load():\n"
            '    module_name = "third_party.module"\n'
            "    importlib.import_module(module_name)\n",
            encoding="utf-8",
        )
        unrelated_same_basename = fixture_root / "unrelated_same_basename.py"
        unrelated_same_basename.write_text(
            "import importlib\n"
            "def load():\n"
            '    module_name = "polisyos.foundry.agent_sim.metrics"\n'
            "    importlib.import_module(module_name)\n",
            encoding="utf-8",
        )
        malformed_target = fixture_root / "malformed_target.py"
        malformed_target.write_text(
            "import tools.research.benchmarks.\n",
            encoding="utf-8",
        )
        keyword_expansion_target = fixture_root / "keyword_expansion_target.py"
        keyword_expansion_target.write_text(
            "import importlib\n"
            'importlib.import_module(**{"name": "tools.research.benchmarks.harness"})\n',
            encoding="utf-8",
        )
        duplicate_argument_target = fixture_root / "duplicate_argument_target.py"
        duplicate_argument_target.write_text(
            "import importlib\n"
            "import builtins\n"
            "import runpy\n"
            'importlib.import_module("not_the_target", name="tools.research.benchmarks.metrics")\n'
            'builtins.__import__("not_the_target", name="tools.research.benchmarks.harness")\n'
            'runpy.run_module("not_the_target", mod_name="tools.research.benchmarks.suite_registry")\n',
            encoding="utf-8",
        )
        unknown_expansion_target = fixture_root / "unknown_expansion_target.py"
        unknown_expansion_target.write_text(
            "import importlib\n"
            "import builtins\n"
            "import runpy\n"
            'import_options = {"name": "tools.research.benchmarks.harness"}\n'
            'builtin_options = {"name": "tools.research.benchmarks.metrics"}\n'
            'runpy_options = {"mod_name": "tools.research.benchmarks.suite_registry"}\n'
            "importlib.import_module(**import_options)\n"
            "builtins.__import__(**builtin_options)\n"
            "runpy.run_module(**runpy_options)\n",
            encoding="utf-8",
        )
        starred_argument_target = fixture_root / "starred_argument_target.py"
        starred_argument_target.write_text(
            "import importlib\n"
            'importlib.import_module(*( "tools.research.benchmarks.metrics", ))\n',
            encoding="utf-8",
        )
        relative_package_unknown = fixture_root / "relative_package_unknown.py"
        relative_package_unknown.write_text(
            "import importlib\n"
            'importlib.import_module(name=".harness", package=discover_package())\n',
            encoding="utf-8",
        )
        relative_builtin_target = fixture_root / "relative_builtin_target.py"
        relative_builtin_target.write_text(
            "import builtins\n"
            'builtins.__import__(name="metrics", globals={"__package__": "tools.research.benchmarks"}, level=1)\n',
            encoding="utf-8",
        )
        relative_runpy_target = fixture_root / "relative_runpy_target.py"
        relative_runpy_target.write_text(
            'import runpy\nrunpy.run_module(mod_name=".suite_registry")\n',
            encoding="utf-8",
        )
        ambiguous_constant_target = fixture_root / "ambiguous_constant_target.py"
        ambiguous_constant_target.write_text(
            "import importlib\n"
            'module_name = "tools.research.benchmarks.harness"\n'
            "module_name = discover_module_name()\n"
            "importlib.import_module(module_name)\n",
            encoding="utf-8",
        )
        unresolved_target = fixture_root / "unresolved_target.py"
        unresolved_target.write_text(
            "import importlib\n"
            'prefix = "tools.research."\n'
            "suffix = discover_module_name()\n"
            "importlib.import_module(prefix + suffix)\n",
            encoding="utf-8",
        )
        subprocess.run(
            [
                "git",
                "add",
                str(malformed_target),
                str(local_assignment_target),
                str(block_assignment_target),
                str(alias_assignment_target),
                str(ambiguous_local_target),
                str(unrelated_local_binding),
                str(unrelated_same_basename),
                str(keyword_expansion_target),
                str(duplicate_argument_target),
                str(unknown_expansion_target),
                str(starred_argument_target),
                str(relative_package_unknown),
                str(relative_builtin_target),
                str(relative_runpy_target),
                str(ambiguous_constant_target),
                str(unresolved_target),
            ],
            cwd=fixture_root,
            check=True,
        )
        fail_closed_inventory = _tracked_python_reference_inventory(
            fixture_root,
            target_modules,
        )
        fail_closed = _scan_tracked_python_callers(
            fixture_root,
            target_modules,
            fail_closed_inventory,
        )
        assert [row["path"] for row in fail_closed["parse_failures"]] == ["malformed_target.py"]
        # Preserve all inherited unresolved witnesses; the shared owner can add
        # explicit unknown/refusal rows that the old token-selected scan dropped.
        assert {
            "alias_assignment_target.py",
            "ambiguous_constant_target.py",
            "ambiguous_local_target.py",
            "block_assignment_target.py",
            "duplicate_argument_target.py",
            "keyword_expansion_target.py",
            "local_assignment_target.py",
            "relative_builtin_target.py",
            "relative_package_unknown.py",
            "relative_runpy_target.py",
            "starred_argument_target.py",
            "unknown_expansion_target.py",
            "unresolved_target.py",
        } <= {row["path"] for row in fail_closed["unresolved"]}
        assert {
            "unrelated_local_binding.py",
            "unrelated_same_basename.py",
        }.isdisjoint({row["path"] for row in fail_closed["unresolved"]})


def test_hyg_calltarget_transfer_is_consumed_and_opaque_return_refuses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real HYG consumer sees formal call-target transfer and unknown returns."""

    source_path = tmp_path / "higher_order.py"
    source_path.write_text(
        "import importlib\n"
        "def invoke(loader, name):\n"
        "    loader(name)\n"
        'invoke(importlib.import_module, "tools.research.benchmarks.harness")\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys.modules[__name__], "iter_repository_files", lambda _root: (source_path,)
    )
    target_modules = {"tools.research.benchmarks.harness"}
    inventory: dict[str, object] = {
        "python_candidate_paths": {"higher_order.py"},
        "tracked_python_denominator": 1,
        "token_python_candidate_count": 1,
    }

    transferred = _scan_tracked_python_callers(tmp_path, target_modules, inventory)
    assert transferred["status"] == "BOUNDED_COMPLETE"
    assert transferred["callers"] == {"higher_order.py": ["tools.research.benchmarks.harness"]}
    assert transferred["unresolved"] == []

    # Remove only the target-transfer property while retaining every call row,
    # source-value slot, status field, and completeness marker. The actual HYG
    # consumer must refuse instead of remaining green on the retained markers.
    owner = decomposition_preflight.collect_source_value_call_observations

    def without_calltarget_transfer(trees, module_paths, **kwargs):
        rows, missing = owner(trees, module_paths, **kwargs)
        for row in rows:
            row["call_targets"] = []
            row["call_target_unknown"] = False
        return rows, missing

    monkeypatch.setattr(
        decomposition_preflight,
        "collect_source_value_call_observations",
        without_calltarget_transfer,
    )
    removed = _scan_tracked_python_callers(tmp_path, target_modules, inventory)
    assert removed["status"] == "BOUNDED_INCOMPLETE"
    assert removed["callers"] == {}
    assert any(row.get("kind") == "unsupported call target" for row in removed["unresolved"])

    source_path.write_text(
        "import vendor\n"
        "loader = vendor.make_loader()\n"
        'loader("tools.research.benchmarks.harness")\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(decomposition_preflight, "collect_source_value_call_observations", owner)
    returned = _scan_tracked_python_callers(tmp_path, target_modules, inventory)
    assert returned["status"] == "BOUNDED_INCOMPLETE"
    assert any(row.get("kind") == "unknown call target" for row in returned["unresolved"])
    assert any(row.get("kind") == "unsupported call target" for row in returned["unresolved"])


@pytest.mark.parametrize(
    ("binding_case", "source", "expected_status", "expected_caller"),
    [
        (
            "unbound_builtin",
            '__import__("tools.research.benchmarks.harness")\n',
            "BOUNDED_COMPLETE",
            True,
        ),
        (
            "explicit_builtin_name_import",
            "from builtins import __import__ as loader\n"
            'loader("tools.research.benchmarks.harness")\n',
            "BOUNDED_COMPLETE",
            True,
        ),
        (
            "explicit_builtin_module_import",
            'import builtins as native\nnative.__import__("tools.research.benchmarks.harness")\n',
            "BOUNDED_COMPLETE",
            True,
        ),
        (
            "local_none",
            '__import__ = None\n__import__("tools.research.benchmarks.harness")\n',
            "BOUNDED_INCOMPLETE",
            False,
        ),
        (
            "local_literal",
            '__import__ = 7\n__import__("tools.research.benchmarks.harness")\n',
            "BOUNDED_INCOMPLETE",
            False,
        ),
        (
            "local_object_value",
            '__import__ = []\n__import__("tools.research.benchmarks.harness")\n',
            "BOUNDED_INCOMPLETE",
            False,
        ),
        (
            "local_mapping_object",
            '__import__ = {}\n__import__("tools.research.benchmarks.harness")\n',
            "BOUNDED_INCOMPLETE",
            False,
        ),
        (
            "local_callable_value",
            "def replacement(name):\n    return None\n"
            "__import__ = replacement\n"
            '__import__("tools.research.benchmarks.harness")\n',
            "BOUNDED_COMPLETE",
            False,
        ),
        (
            "callable_return",
            "def make_loader():\n    return None\n"
            "__import__ = make_loader()\n"
            '__import__("tools.research.benchmarks.harness")\n',
            "BOUNDED_INCOMPLETE",
            False,
        ),
        (
            "parameter_value",
            "def invoke(__import__):\n"
            '    __import__("tools.research.benchmarks.harness")\n'
            "invoke(None)\n",
            "BOUNDED_INCOMPLETE",
            False,
        ),
        (
            "bare_alias_of_unbound_builtin",
            'loader = __import__\nloader("tools.research.benchmarks.harness")\n',
            "BOUNDED_INCOMPLETE",
            False,
        ),
        (
            "rebound_builtin_module",
            "import builtins as native\n"
            "native = None\n"
            'native.__import__("tools.research.benchmarks.harness")\n',
            "BOUNDED_INCOMPLETE",
            False,
        ),
        (
            "rebound_imported_builtin",
            "from builtins import __import__ as loader\n"
            "loader = None\n"
            'loader("tools.research.benchmarks.harness")\n',
            "BOUNDED_INCOMPLETE",
            False,
        ),
        (
            "opaque_imported_callable",
            "from vendor import __import__ as loader\n"
            'loader("tools.research.benchmarks.harness")\n',
            "BOUNDED_INCOMPLETE",
            False,
        ),
    ],
)
def test_hyg_builtin_identity_uses_the_whole_binding_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    binding_case: str,
    source: str,
    expected_status: str,
    expected_caller: bool,
) -> None:
    """The HYG consumer distinguishes unbound builtins from bound values."""
    source_path = tmp_path / "binding_identity.py"
    source_path.write_text(source, encoding="utf-8")
    monkeypatch.setattr(
        sys.modules[__name__], "iter_repository_files", lambda _root: (source_path,)
    )
    target_modules = {"tools.research.benchmarks.harness"}
    inventory: dict[str, object] = {
        "python_candidate_paths": {"binding_identity.py"},
        "tracked_python_denominator": 1,
        "token_python_candidate_count": 1,
    }

    result = _scan_tracked_python_callers(tmp_path, target_modules, inventory)

    assert result["status"] == expected_status, binding_case
    assert result["callers"] == (
        {"binding_identity.py": ["tools.research.benchmarks.harness"]} if expected_caller else {}
    ), binding_case
    assert result["parse_failures"] == [], binding_case
    if expected_status == "BOUNDED_INCOMPLETE":
        assert result["unresolved"], binding_case


def test_benchmark_wrapper_cli_matches_canonical_entrypoint() -> None:
    """The registry shim preserves canonical stdout, stderr, and exit status."""

    canonical = REPO_ROOT / "benchmarks/suite_registry.py"
    wrapper = REPO_ROOT / "tools/research/benchmarks/suite_registry.py"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(
            None,
            (str(REPO_ROOT), str(REPO_ROOT / "src"), environment.get("PYTHONPATH", "")),
        )
    )

    for arguments in (
        ("--profile", "air-m2", "--format", "json"),
        ("--format", "not-a-format"),
    ):
        canonical_result = subprocess.run(
            [sys.executable, str(canonical), *arguments],
            cwd=REPO_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        wrapper_result = subprocess.run(
            [sys.executable, str(wrapper), *arguments],
            cwd=REPO_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        assert (
            wrapper_result.returncode,
            wrapper_result.stdout,
            wrapper_result.stderr,
        ) == (
            canonical_result.returncode,
            canonical_result.stdout,
            canonical_result.stderr,
        )


def test_frontend_redirect_stub_is_retired_without_touching_live_workspaces() -> None:
    """The legacy handoff is absent while canonical roots remain protected."""

    readme = REPO_ROOT / _FRONTEND_DIR / "README.md"
    assert not readme.exists()

    findings = [
        finding
        for finding in check_docs_lifecycle.check_redirect_stubs(REPO_ROOT)
        if finding.path == _FRONTEND_README
    ]
    assert findings == []

    for protected in (
        "apps/runtime-dashboard",
        "apps/runtime-reference-shell",
        "packages/runtime-api-client",
        "tools/research/benchmarks",
    ):
        assert (REPO_ROOT / protected).is_dir(), protected


def test_frontend_workspace_build_paths_and_python_package_boundaries() -> None:
    """Workspace build commands and Python package inclusion stay bounded."""

    workspace_lines = (REPO_ROOT / "pnpm-workspace.yaml").read_text(encoding="utf-8")
    workspace_globs = tuple(
        line.strip()[2:].strip().strip("'\"")
        for line in workspace_lines.splitlines()
        if line.strip().startswith("- ")
    )
    assert workspace_globs == ("apps/*", "packages/*")

    root_manifest = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    assert "--workspace-concurrency=1" in root_manifest["scripts"]["build"]

    workspace_manifests = {
        relative: json.loads((REPO_ROOT / relative / "package.json").read_text(encoding="utf-8"))
        for relative in (
            "apps/runtime-dashboard",
            "apps/runtime-reference-shell",
            "packages/runtime-api-client",
        )
    }
    for manifest in workspace_manifests.values():
        assert manifest["private"] is True
        assert manifest["engines"]["node"] == ">=22 <23"
        assert "build" in manifest["scripts"]
    assert "vite build" in workspace_manifests["apps/runtime-dashboard"]["scripts"]["build"]
    assert "typecheck" in workspace_manifests["apps/runtime-reference-shell"]["scripts"]["build"]
    assert "typecheck" in workspace_manifests["packages/runtime-api-client"]["scripts"]["build"]

    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    hatch_config = tomllib.loads((REPO_ROOT / "hatch.toml").read_text(encoding="utf-8"))
    assert "hatch" not in pyproject.get("tool", {})
    wheel_packages = hatch_config["build"]["targets"]["wheel"]["packages"]
    sdist_includes = set(hatch_config["build"]["targets"]["sdist"]["include"])
    assert wheel_packages == ["src/polisyos", "tools"]
    assert {"benchmarks", "docs", "ops", "schemas", "tools"} <= sdist_includes
    assert not any(
        item == prefix or item.startswith(f"{prefix}/")
        for item in sdist_includes
        for prefix in ("apps", "packages", "node_modules", "dist", "coverage")
    )

    ignored = subprocess.run(
        ["git", "check-ignore", "--no-index", "--stdin"],
        cwd=REPO_ROOT,
        input=(
            "apps/runtime-dashboard/dist/index.js\n"
            "packages/runtime-api-client/node_modules/.bin/tool\n"
        ),
        capture_output=True,
        text=True,
        check=False,
    )
    assert ignored.returncode == 0
    assert set(ignored.stdout.splitlines()) == {
        "apps/runtime-dashboard/dist/index.js",
        "packages/runtime-api-client/node_modules/.bin/tool",
    }


def test_redirect_lifecycle_rejects_an_unqualified_expired_stub() -> None:
    """An expired redirect cannot be retired or prolonged without an ADR."""

    with TemporaryDirectory() as temporary_root:
        fixture_root = Path(temporary_root)
        frontend = fixture_root / _FRONTEND_DIR
        frontend.mkdir()
        (frontend / "README.md").write_text(
            "\n".join(
                (
                    "---",
                    "redirect_stub: true",
                    "owner: team-frontend",
                    "target_path: apps; packages/runtime-api-client",
                    "reason: compatibility handoff",
                    "created_date: 2026-01-01",
                    "sunset_date: 2026-05-01",
                    "removal_gate: uv run python tools/quality/validation/check_docs_lifecycle.py",
                    "---",
                    "",
                    "Use the canonical workspaces.",
                )
            )
            + "\n",
            encoding="utf-8",
        )

        assert check_docs_lifecycle.check_redirect_stubs(fixture_root) == [
            check_docs_lifecycle.LifecycleFinding(
                "redirect_stub",
                _FRONTEND_README,
                "redirect stub sunset exceeds the 90-day policy without `compatibility_adr`.",
            )
        ]
