"""Behavioral witnesses for the HYG-04 canonical entrypoints and boundaries.

The tests exercise supported compatibility contracts, JAX import ordering,
canonical object identity, lifecycle rejection, and protected workspace and
benchmark surfaces; source-text markers alone are not sufficient evidence.
"""

from __future__ import annotations

import ast
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

from tools.lib.fs import iter_repository_files
from tools.quality.validation import check_docs_lifecycle, schema_fqn_census

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


def _literal_module_address(
    node: ast.AST | None,
    constants: dict[str, str],
) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _literal_module_address(node.left, constants)
        right = _literal_module_address(node.right, constants)
        return left + right if left is not None and right is not None else None
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            part = _literal_module_address(
                value.value if isinstance(value, ast.FormattedValue) else value,
                constants,
            )
            if part is None:
                return None
            parts.append(part)
        return "".join(parts)
    return None


def _literal_module_fragments(
    node: ast.AST | None,
    constants: dict[str, str],
    assigned_fragments: dict[str, set[str]] | None = None,
) -> set[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, ast.Name):
        value = constants.get(node.id)
        if value is not None:
            return {value}
        return set((assigned_fragments or {}).get(node.id, set()))
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _literal_module_fragments(
            node.left, constants, assigned_fragments
        ) | _literal_module_fragments(node.right, constants, assigned_fragments)
    if isinstance(node, ast.JoinedStr):
        return set().union(
            *(
                _literal_module_fragments(
                    value.value if isinstance(value, ast.FormattedValue) else value,
                    constants,
                    assigned_fragments,
                )
                for value in node.values
            )
        )
    if isinstance(node, ast.Dict):
        return set().union(
            *(
                _literal_module_fragments(value, constants, assigned_fragments)
                for value in (*node.keys, *node.values)
                if value is not None
            )
        )
    if isinstance(node, (ast.List, ast.Set, ast.Tuple)):
        return set().union(
            *(
                _literal_module_fragments(value, constants, assigned_fragments)
                for value in node.elts
            )
        )
    if isinstance(node, ast.Starred):
        return _literal_module_fragments(node.value, constants, assigned_fragments)
    return set()


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


def _assignment_target_names(target: ast.AST) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        return set().union(*(_assignment_target_names(item) for item in target.elts))
    if isinstance(target, ast.Starred):
        return _assignment_target_names(target.value)
    return set()


def _whole_ast_target_name_hints(
    tree: ast.Module,
    constants: dict[str, str],
    target_modules: set[str],
) -> dict[str, set[str]]:
    """Conservatively associate target-bearing assignments and aliases across scopes."""

    bindings: list[tuple[set[str], set[str], set[str]]] = []
    for node in ast.walk(tree):
        targets: list[ast.AST] = []
        values: list[ast.AST] = []
        if isinstance(node, ast.Assign):
            targets = node.targets
            values = [node.value]
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            values = [node.value] if node.value is not None else []
        elif isinstance(node, ast.NamedExpr):
            targets = [node.target]
            values = [node.value]
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            targets = [node.target]
            values = [node.iter]
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    targets.append(item.optional_vars)
                    values.append(item.context_expr)
        bound_names = set().union(*(_assignment_target_names(target) for target in targets))
        for value in values:
            if not bound_names:
                continue
            fragments = _literal_module_fragments(value, constants)
            source_names = {child.id for child in ast.walk(value) if isinstance(child, ast.Name)}
            bindings.append((bound_names, fragments, source_names))

    hints: dict[str, set[str]] = {}
    changed = True
    while changed:
        changed = False
        for bound_names, fragments, source_names in bindings:
            propagated = set(fragments)
            for source_name in source_names:
                propagated.update(hints.get(source_name, set()))
            if not _target_related_fragments(propagated, target_modules):
                continue
            for bound_name in bound_names:
                before = len(hints.setdefault(bound_name, set()))
                hints[bound_name].update(propagated)
                changed |= len(hints[bound_name]) != before
    return hints


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


def _dynamic_import_aliases(tree: ast.Module) -> dict[str, str]:
    aliases: dict[str, str] = {"__import__": "builtins.__import__"}
    import_modules = {"builtins", "importlib", "runpy"}
    imported_functions = {
        ("builtins", "__import__"): "builtins.__import__",
        ("importlib", "import_module"): "importlib.import_module",
        ("runpy", "run_module"): "runpy.run_module",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_root = alias.name.split(".", 1)[0]
                if module_root in import_modules:
                    aliases[alias.asname or module_root] = (
                        alias.name if alias.asname else module_root
                    )
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                resolved = imported_functions.get((node.module or "", alias.name))
                if resolved is not None:
                    aliases[alias.asname or alias.name] = resolved

    def resolve(node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return aliases.get(node.id)
        if isinstance(node, ast.Attribute):
            base = resolve(node.value)
            return f"{base}.{node.attr}" if base else None
        return None

    for node in ast.walk(tree):
        targets = (
            node.targets
            if isinstance(node, ast.Assign)
            else [node.target]
            if isinstance(node, ast.AnnAssign)
            else []
        )
        resolved = resolve(node.value) if targets else None
        if resolved in {*imported_functions.values(), *import_modules}:
            for target in targets:
                if isinstance(target, ast.Name):
                    aliases[target.id] = resolved
    return aliases


def _tracked_python_reference_inventory(
    repo_root: Path,
    target_modules: set[str],
) -> dict[str, object]:
    """Keep all tracked text references and select bounded Python syntax candidates.

    The text inventory is evidence only. Candidate Python files come from exact
    target/package/path tokens, supported loader spellings, or relative-import
    syntax; docs and research paths are searched by the same rule as executable
    folders.
    """

    repo_root = repo_root.resolve()
    tracked_files = tuple(iter_repository_files(repo_root))
    tracked_paths = {path.relative_to(repo_root).as_posix() for path in tracked_files}
    tracked_suffix_counts = Counter(
        path.suffix.lower() or "<extensionless>" for path in tracked_files
    )
    assert sum(tracked_suffix_counts.values()) == len(tracked_files)

    parent_modules = {module.rpartition(".")[0] for module in target_modules}
    source_paths = {
        f"tools/research/benchmarks/{module.rsplit('.', 1)[-1]}.py" for module in target_modules
    }
    fixed_tokens = sorted(
        target_modules
        | parent_modules
        | source_paths
        | {"importlib", "runpy", "builtins", "__import__"}
    )
    fixed_command = ["git", "grep", "-I", "-l", "-F"]
    for token in fixed_tokens:
        fixed_command.extend(("-e", token))
    fixed_command.extend(("--", "."))
    fixed_result = subprocess.run(
        fixed_command,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert fixed_result.returncode in {0, 1}, fixed_result.stderr
    fixed_matches = set(fixed_result.stdout.splitlines())

    relative_import_result = subprocess.run(
        [
            "git",
            "grep",
            "-I",
            "-l",
            "-E",
            "-e",
            r"^[[:space:]]*from[[:space:]]+\.+([[:space:]]*[A-Za-z_][A-Za-z_0-9.]*)?[[:space:]]+import([[:space:]]|\()",
            "--",
            ".",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert relative_import_result.returncode in {0, 1}, relative_import_result.stderr
    relative_matches = set(relative_import_result.stdout.splitlines())
    matched_paths = fixed_matches | relative_matches
    assert matched_paths <= tracked_paths
    python_paths = {path for path in matched_paths if Path(path).suffix.lower() in {".py", ".pyi"}}
    matched_suffix_counts = Counter(
        Path(path).suffix.lower() or "<extensionless>" for path in matched_paths
    )
    assert sum(matched_suffix_counts.values()) == len(matched_paths)

    return {
        "tracked_paths": tracked_paths,
        "tracked_file_count": len(tracked_files),
        "tracked_python_denominator": sum(
            path.suffix.lower() in {".py", ".pyi"} for path in tracked_files
        ),
        "tracked_suffix_counts": dict(sorted(tracked_suffix_counts.items())),
        "matched_paths": matched_paths,
        "matched_path_count": len(matched_paths),
        "matched_suffix_counts": dict(sorted(matched_suffix_counts.items())),
        "python_candidate_paths": python_paths,
        "python_candidate_count": len(python_paths),
        "fixed_tokens": fixed_tokens,
        "relative_import_selector": "tracked-text Python relative-import syntax",
    }


def _python_import_package(repo_root: Path, path: Path) -> str:
    relative_parent = path.relative_to(repo_root).parent
    return ".".join(relative_parent.parts)


def _is_verified_archived_source_pair(
    repo_root: Path,
    relative_path: str,
    raw: bytes,
    selected_paths: set[str],
    evidence_json_cache: dict[str, tuple[dict[str, object], str, int] | None],
) -> str | None:
    """Recognize only source excerpts bound by the existing evidence index."""

    evidence = schema_fqn_census._indexed_evidence_snapshot(
        repo_root,
        relative_path,
        relative_path,
        raw,
        selected_paths,
        evidence_json_cache,
    )
    return str(evidence["pair_format"]) if evidence is not None else None


def _scan_tracked_python_callers(
    repo_root: Path,
    target_modules: set[str],
    reference_inventory: dict[str, object],
) -> dict[str, object]:
    """Resolve imports in lexical Python candidates from the complete tracked set.

    Direct and relative imports plus literal importlib.import_module,
    __import__ and runpy.run_module addresses are in scope, including positional
    and documented keyword name bindings, simple aliases, uniquely assigned
    top-level string constants, concatenation, and literal f-strings. Literal
    importlib relative names resolve with their literal package; relative
    __import__/runpy names and ambiguous/starred/** argument bindings fail closed.
    Whole-AST assignment/use hints make target-bearing local, block, alias, and
    ambiguous bindings unresolved when a supported loader consumes them. Computed
    or cross-file values without any target-bearing assignment/use hint remain
    outside this bounded property.
    """

    repo_root = repo_root.resolve()
    tracked_files = tuple(iter_repository_files(repo_root))
    candidate_paths = reference_inventory["python_candidate_paths"]
    assert isinstance(candidate_paths, set)
    selected_paths = {
        path.relative_to(repo_root).as_posix()
        for path in tracked_files
        if schema_fqn_census._is_selected_text(path.as_posix())
    }
    caller_targets: dict[str, set[str]] = {}
    dynamic_callers: list[dict[str, object]] = []
    parse_failures: list[dict[str, str]] = []
    archived_source_pairs: list[dict[str, str]] = []
    unresolved: list[dict[str, object]] = []
    evidence_json_cache: dict[str, tuple[dict[str, object], str, int] | None] = {}
    target_parents = {target.rpartition(".")[0] for target in target_modules}

    for relative in sorted(candidate_paths):
        path = repo_root / relative
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeError) as error:
            parse_failures.append({"path": relative, "error": str(error)})
            continue
        try:
            tree = ast.parse(text, filename=relative)
        except (SyntaxError, ValueError, RecursionError) as error:
            pair_format = _is_verified_archived_source_pair(
                repo_root,
                relative,
                raw,
                selected_paths,
                evidence_json_cache,
            )
            if pair_format is not None:
                archived_source_pairs.append({"path": relative, "pair_format": pair_format})
                continue
            parse_failures.append(
                {
                    "path": relative,
                    "error": f"{type(error).__name__}: {error}",
                }
            )
            continue

        constant_history: dict[str, list[tuple[str | None, set[str]]]] = {}
        provisional_constants: dict[str, str] = {}
        for statement in tree.body:
            targets = (
                statement.targets
                if isinstance(statement, ast.Assign)
                else [statement.target]
                if isinstance(statement, ast.AnnAssign)
                else []
            )
            if not targets:
                continue
            value = _literal_module_address(statement.value, provisional_constants)
            fragments = _literal_module_fragments(statement.value, provisional_constants)
            for target in targets:
                if not isinstance(target, ast.Name):
                    continue
                constant_history.setdefault(target.id, []).append((value, fragments))
                if value is None:
                    provisional_constants.pop(target.id, None)
                else:
                    provisional_constants[target.id] = value
        constants = {
            name: rows[0][0]
            for name, rows in constant_history.items()
            if len(rows) == 1 and rows[0][0] is not None
        }
        assigned_fragments = {
            name: set().union(*(fragments for _, fragments in rows))
            for name, rows in constant_history.items()
            if any(fragments for _, fragments in rows)
        }
        target_name_hints = _whole_ast_target_name_hints(tree, constants, target_modules)
        dynamic_aliases = _dynamic_import_aliases(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    caller_targets.setdefault(relative, set()).update(
                        _module_targets(alias.name, target_modules)
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level:
                    package = _python_import_package(repo_root, path)
                    try:
                        module = importlib.util.resolve_name(
                            "." * node.level + module,
                            package,
                        )
                    except (ImportError, ValueError):
                        module = ""
                direct_matches = _module_targets(module, target_modules)
                if direct_matches:
                    caller_targets.setdefault(relative, set()).update(direct_matches)
                for alias in node.names:
                    if alias.name == "*":
                        if module in target_parents:
                            caller_targets.setdefault(relative, set()).update(target_modules)
                        continue
                    caller_targets.setdefault(relative, set()).update(
                        _module_targets(f"{module}.{alias.name}", target_modules)
                    )
            elif isinstance(node, ast.Call):
                function = node.func
                if isinstance(function, ast.Name):
                    function_name = dynamic_aliases.get(function.id)
                elif isinstance(function, ast.Attribute):
                    base = function.value
                    if isinstance(base, ast.Name):
                        function_name = f"{dynamic_aliases.get(base.id, base.id)}.{function.attr}"
                    else:
                        function_name = None
                else:
                    function_name = None
                if function_name not in {
                    "importlib.import_module",
                    "builtins.__import__",
                    "runpy.run_module",
                }:
                    continue
                arguments, binding_error = _bound_loader_arguments(node, function_name)
                name_parameter = "mod_name" if function_name == "runpy.run_module" else "name"
                address_node = arguments.get(name_parameter)
                address = _literal_module_address(address_node, constants)
                call_arguments = [
                    *node.args,
                    *(keyword.value for keyword in node.keywords),
                ]
                fragments = set().union(
                    *(
                        _literal_module_fragments(argument, constants, assigned_fragments)
                        for argument in (address_node, *arguments.values(), *call_arguments)
                        if argument is not None
                    ),
                    *(
                        target_name_hints.get(child.id, set())
                        for argument in call_arguments
                        for child in ast.walk(argument)
                        if isinstance(child, ast.Name)
                    ),
                )
                if binding_error is not None:
                    if _target_related_fragments(fragments, target_modules):
                        unresolved.append(
                            {
                                "path": relative,
                                "line": node.lineno,
                                "reason": binding_error,
                            }
                        )
                    continue
                if address_node is None:
                    continue
                if address is None:
                    if _target_related_fragments(fragments, target_modules):
                        unresolved.append(
                            {
                                "path": relative,
                                "line": node.lineno,
                                "reason": f"computed {function_name} address in target-bearing source",
                            }
                        )
                    continue

                if function_name == "importlib.import_module" and address.startswith("."):
                    package = _literal_module_address(arguments.get("package"), constants)
                    if package is None:
                        if _target_related_fragments({address}, target_modules):
                            unresolved.append(
                                {
                                    "path": relative,
                                    "line": node.lineno,
                                    "reason": "relative importlib name has no literal package binding",
                                }
                            )
                        continue
                    try:
                        address = importlib.util.resolve_name(address, package)
                    except (ImportError, ValueError):
                        if _target_related_fragments({address}, target_modules):
                            unresolved.append(
                                {
                                    "path": relative,
                                    "line": node.lineno,
                                    "reason": "relative importlib name/package is invalid",
                                }
                            )
                        continue
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
                            unresolved.append(
                                {
                                    "path": relative,
                                    "line": node.lineno,
                                    "reason": "relative or dynamic builtins.__import__ level is unsupported",
                                }
                            )
                        continue
                elif function_name == "runpy.run_module" and address.startswith("."):
                    if _target_related_fragments({address}, target_modules):
                        unresolved.append(
                            {
                                "path": relative,
                                "line": node.lineno,
                                "reason": "relative runpy module names are unsupported",
                            }
                        )
                    continue

                matches = _module_targets(address, target_modules)
                if matches:
                    caller_targets.setdefault(relative, set()).update(matches)
                    dynamic_callers.append(
                        {
                            "path": relative,
                            "line": node.lineno,
                            "function": function_name,
                            "address": address,
                        }
                    )

    return {
        "tracked_python_denominator": reference_inventory["tracked_python_denominator"],
        "lexical_python_candidate_count": len(candidate_paths),
        "archived_source_pairs": archived_source_pairs,
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


def test_benchmark_wrapper_caller_census_is_complete_and_bounded() -> None:
    """Derive source callers while retaining a complete tracked-text inventory."""

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
    assert caller_census["lexical_python_candidate_count"] == inventory["python_candidate_count"]
    assert caller_census["parse_failures"] == [], caller_census["parse_failures"]
    assert caller_census["unresolved"] == [], caller_census["unresolved"]
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
        assert {row["path"] for row in fail_closed["unresolved"]} == {
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
        }
        assert {
            "unrelated_local_binding.py",
            "unrelated_same_basename.py",
        }.isdisjoint({row["path"] for row in fail_closed["unresolved"]})


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
