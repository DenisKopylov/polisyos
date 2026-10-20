"""Source-bound host/Linux placement and primary-phase gate for Q2.

This small coordinator composes the three existing Q2 wheel profiles with the
actual platform skip predicate in selected tests. It does not change the
consumer contract or turn a platform name into execution evidence: accepted
rows are reconciled from collected node IDs, JUnit, installed-origin/resource
proofs, and immutable target snapshots.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from defusedxml import ElementTree
from split_protocol import (
    PROFILE_CHAIN_KEYS,
    SplitProtocolError,
    _validate_freeze,
    canonical_json_bytes,
    load_json_bytes,
    sha256_bytes,
    validate_inventory,
    validate_source_audit_selection,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

COMPOSITE_SCHEMA = "policyos.e02.q2.profile-composite-primary.v1"
EXECUTION_SCHEMA = "policyos.e02.q2.profile-partition-execution.v1"
BARRIER_SCHEMA = "policyos.e02.q2.profile-composite-primary-barrier.v1"
INPUT_PIN_KEYS = (
    "primary_manifest_sha256",
    "supplemental_manifest_sha256",
    "source_audit_receipt_sha256",
    "source_inventory_sha256",
    "resource_owner_inventory_sha256",
    "build_profile_sha256",
    "consumer_runner_sha256",
    "supplemental_runner_sha256",
    "test_source_closure_sha256",
    "dependency_profile_sha256",
)
ARTIFACT_CHAIN_KEYS = (
    "source_archive_sha256",
    "source_wheel_sha256",
    "source_sdist_sha256",
    "rebuilt_sdist_wheel_sha256",
    "gcp_archive_sha256",
    "rebuilt_gcp_wheel_sha256",
)
Q2_RUNNER_RELATIVE = (
    "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/run.py"
)
SUPPLEMENTAL_RUNNER_RELATIVE = (
    "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/"
    "q2-packaging/raw/supplemental_run.py"
)
_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class ProfileCompositeError(SplitProtocolError):
    """Raised when the host/Linux execution partitions do not compose exactly."""


def _sha(value: object, label: str, *, length: int = 64) -> str:
    pattern = _SHA1 if length == 40 else _SHA256
    if type(value) is not str or not pattern.fullmatch(value):
        algorithm = "SHA-1" if length == 40 else "SHA-256"
        raise ProfileCompositeError(f"{label} must be a lowercase {algorithm}")
    return value


def _canonical_node_id(value: object) -> tuple[str, tuple[str, ...], str | None]:
    if type(value) is not str:
        raise ProfileCompositeError("selected consumer node ID must be a string")
    pieces = value.split("::")
    if len(pieces) < 2:
        raise ProfileCompositeError("selected consumer node ID must be `relative.py::test_name`")
    relative, *selectors = pieces
    parsed = PurePosixPath(relative)
    if (
        parsed.is_absolute()
        or parsed.as_posix() != relative
        or not parsed.parts
        or any(part in {"", ".", ".."} for part in parsed.parts)
        or not relative.endswith(".py")
        or not selectors
        or any(not re.fullmatch(r"[A-Za-z_]\w*", selector) for selector in selectors[:-1])
    ):
        raise ProfileCompositeError(f"noncanonical or parameterized Q2 node ID: {value!r}")
    function_match = re.fullmatch(r"([A-Za-z_]\w*)(?:\[([^\[\]]*)\])?", selectors[-1])
    if function_match is None:
        raise ProfileCompositeError(f"noncanonical or parameterized Q2 node ID: {value!r}")
    return relative, (*selectors[:-1], function_match.group(1)), function_match.group(2)


def _ast_attribute(node: ast.AST) -> tuple[str, ...] | None:
    parts: list[str] = []
    cursor = node
    while isinstance(cursor, ast.Attribute):
        parts.append(cursor.attr)
        cursor = cursor.value
    if not isinstance(cursor, ast.Name):
        return None
    parts.append(cursor.id)
    return tuple(reversed(parts))


def _import_bindings(tree: ast.Module) -> dict[str, set[str]]:
    """Return source-imported names for pytest and the two platform modules."""
    bindings = {
        name: set()
        for name in ("pytest", "pytest_mark", "skipif", "pytest_param", "sys", "platform")
    }
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                if alias.name == "pytest":
                    bindings["pytest"].add(alias.asname or "pytest")
                elif alias.name == "sys" or alias.name.startswith("sys."):
                    bindings["sys"].add(alias.asname or alias.name.split(".", 1)[0])
                elif alias.name == "platform" or alias.name.startswith("platform."):
                    bindings["platform"].add(alias.asname or alias.name.split(".", 1)[0])
        elif isinstance(statement, ast.ImportFrom):
            if statement.module == "pytest":
                for alias in statement.names:
                    if alias.name == "mark":
                        bindings["pytest_mark"].add(alias.asname or alias.name)
                    elif alias.name == "param":
                        bindings["pytest_param"].add(alias.asname or alias.name)
            elif statement.module == "pytest.mark":
                for alias in statement.names:
                    if alias.name == "skipif":
                        bindings["skipif"].add(alias.asname or alias.name)
    return bindings


def _contains_platform_input(node: ast.AST, bindings: dict[str, set[str]]) -> bool:
    for child in ast.walk(node):
        chain = _ast_attribute(child)
        if chain is None:
            continue
        if (len(chain) == 2 and chain[0] in bindings["sys"] and chain[1] == "platform") or (
            len(chain) == 2 and chain[0] in bindings["platform"] and chain[1] == "system"
        ):
            return True
    return False


def _platform_value(node: ast.AST, system: str, bindings: dict[str, set[str]]) -> object:
    if isinstance(node, ast.Constant) and type(node.value) in {str, bool, int}:
        return node.value
    chain = _ast_attribute(node)
    if (
        chain is not None
        and len(chain) == 2
        and chain[0] in bindings["sys"]
        and chain[1] == "platform"
    ):
        if system == "Linux":
            return "linux"
        if system == "Darwin":
            return "darwin"
        raise ProfileCompositeError(f"unsupported selected host platform: {system}")
    if (
        isinstance(node, ast.Call)
        and not node.keywords
        and not node.args
        and (func_chain := _ast_attribute(node.func)) is not None
        and len(func_chain) == 2
        and func_chain[0] in bindings["platform"]
        and func_chain[1] == "system"
    ):
        return system
    if (
        isinstance(node, ast.Call)
        and len(node.args) == 1
        and not node.keywords
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "startswith"
    ):
        receiver = _platform_value(node.func.value, system, bindings)
        argument = _platform_value(node.args[0], system, bindings)
        if type(receiver) is str and type(argument) is str:
            return receiver.startswith(argument)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not bool(_platform_value(node.operand, system, bindings))
    if isinstance(node, ast.BoolOp):
        values = [_platform_value(value, system, bindings) for value in node.values]
        if isinstance(node.op, ast.And):
            return all(bool(value) for value in values)
        if isinstance(node.op, ast.Or):
            return any(bool(value) for value in values)
    if isinstance(node, ast.Compare) and len(node.ops) == len(node.comparators) == 1:
        left = _platform_value(node.left, system, bindings)
        right = _platform_value(node.comparators[0], system, bindings)
        if isinstance(node.ops[0], ast.Eq):
            return type(left) is type(right) and left == right
        if isinstance(node.ops[0], ast.NotEq):
            return type(left) is not type(right) or left != right
    raise ProfileCompositeError(
        "selected skipif predicate is outside the supported explicit sys.platform / "
        f"platform.system() grammar: {ast.dump(node, include_attributes=False)}"
    )


def _skipif_calls(node: ast.AST, bindings: dict[str, set[str]]) -> list[ast.Call]:
    calls: list[ast.Call] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        chain = _ast_attribute(child.func)
        recognized = chain is not None and (
            (len(chain) == 3 and chain[0] in bindings["pytest"] and chain[1:] == ("mark", "skipif"))
            or (len(chain) == 2 and chain[0] in bindings["pytest_mark"] and chain[1] == "skipif")
            or (len(chain) == 1 and chain[0] in bindings["skipif"])
        )
        potential_skipif = (chain is not None and chain[-1] == "skipif") or (
            isinstance(child.func, ast.Name) and child.func.id == "skipif"
        )
        if potential_skipif and not recognized:
            raise ProfileCompositeError(
                "selected test uses an unbound skipif decorator; platform placement is unknown"
            )
        if recognized:
            calls.append(child)
    return calls


def _class_path_for_function(
    tree: ast.Module, class_path: tuple[str, ...], function_name: str
) -> tuple[list[ast.ClassDef], ast.FunctionDef | ast.AsyncFunctionDef]:
    scope = tree.body
    classes: list[ast.ClassDef] = []
    for class_name in class_path:
        candidates = [
            node for node in scope if isinstance(node, ast.ClassDef) and node.name == class_name
        ]
        if len(candidates) != 1:
            raise ProfileCompositeError(
                f"selected test class is absent or ambiguous: {'::'.join(class_path)}"
            )
        selected = candidates[0]
        classes.append(selected)
        scope = selected.body
    functions = [
        node
        for node in scope
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name
    ]
    if len(functions) != 1:
        raise ProfileCompositeError("selected test function is absent or ambiguous")
    return classes, functions[0]


def _pytestmark_values(scope: list[ast.stmt]) -> list[ast.AST]:
    values: list[ast.AST] = []
    for statement in scope:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        if (
            any(isinstance(target, ast.Name) and target.id == "pytestmark" for target in targets)
            and statement.value is not None
        ):
            values.append(statement.value)
    return values


def _test_skipif_conditions(
    tree: ast.Module,
    classes: list[ast.ClassDef],
    test: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.AST]:
    bindings = _import_bindings(tree)
    calls: list[ast.Call] = []
    decorators = [item for cls in classes for item in cls.decorator_list]
    decorators.extend(test.decorator_list)
    for decorator in decorators:
        calls.extend(_skipif_calls(decorator, bindings))
    for scope in [tree.body, *(cls.body for cls in classes)]:
        for value in _pytestmark_values(scope):
            calls.extend(_skipif_calls(value, bindings))
    conditions: list[ast.AST] = []
    for call in calls:
        if not call.args:
            raise ProfileCompositeError("selected pytest.mark.skipif omits its condition")
        condition = call.args[0]
        if not _contains_platform_input(condition, bindings):
            raise ProfileCompositeError(
                "selected Q2 case has a non-platform skipif; it cannot be assigned by OS labels"
            )
        conditions.append(condition)
    return conditions


def _reject_parameter_specific_marks(
    test: ast.FunctionDef | ast.AsyncFunctionDef,
    parameter_id: str | None,
    bindings: dict[str, set[str]],
) -> None:
    """Fail closed when selected parametrization has a parameter-local mark."""
    if parameter_id is None:
        return
    for decorator in test.decorator_list:
        for child in ast.walk(decorator):
            if not isinstance(child, ast.Call):
                continue
            chain = _ast_attribute(child.func)
            is_pytest_param = (
                chain is not None
                and len(chain) == 2
                and chain[0] in bindings["pytest"]
                and chain[1] == "param"
            ) or (isinstance(child.func, ast.Name) and child.func.id in bindings["pytest_param"])
            if is_pytest_param and any(keyword.arg == "marks" for keyword in child.keywords):
                raise ProfileCompositeError(
                    "selected parametrized case has a parameter-local mark; platform placement "
                    "cannot be assigned from the function-level source predicate"
                )


def _read_source_file(root: Path, relative: str, expected_sha: object | None) -> bytes:
    if expected_sha is not None:
        _sha(expected_sha, f"test source pin for {relative}")
    current = root
    for component in PurePosixPath(relative).parts:
        current = current / component
        try:
            info = current.lstat()
        except OSError as error:
            raise ProfileCompositeError(f"selected test source is absent: {relative}") from error
        if stat.S_ISLNK(info.st_mode):
            raise ProfileCompositeError(f"selected test source traverses a symlink: {relative}")
    if not stat.S_ISREG(current.stat().st_mode):
        raise ProfileCompositeError(f"selected test source is not a regular file: {relative}")
    raw = current.read_bytes()
    if expected_sha is not None and hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ProfileCompositeError(f"selected test source differs from its frozen pin: {relative}")
    return raw


def _read_absolute_regular_file(path_value: str | Path, label: str) -> tuple[Path, bytes]:
    supplied = Path(path_value).absolute()
    if ".." in supplied.parts:
        raise ProfileCompositeError(f"{label} path contains parent traversal: {supplied}")
    current = Path(supplied.anchor)
    for component in supplied.parts[1:]:
        current = current / component
        try:
            info = current.lstat()
        except OSError as error:
            raise ProfileCompositeError(f"{label} is absent: {supplied}") from error
        if stat.S_ISLNK(info.st_mode):
            raise ProfileCompositeError(f"{label} traverses a symlink: {supplied}")
    if not stat.S_ISREG(current.stat().st_mode):
        raise ProfileCompositeError(f"{label} is not a regular file: {supplied}")
    return current, current.read_bytes()


def _load_source_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ProfileCompositeError(f"cannot load source-bound Q2 helper: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as error:
        raise ProfileCompositeError(f"source-bound Q2 helper failed to import: {path}") from error
    finally:
        sys.modules.pop(name, None)
    return module


def _git_source_identity(product: Path) -> tuple[Path, dict[str, str]]:
    if product.name != "policy-engine":
        raise ProfileCompositeError("product root must be the source checkout's policy-engine")
    repo = product.parent.resolve(strict=True)
    git = shutil.which("git")
    if git is None:
        raise ProfileCompositeError("Git is unavailable to recompute the source freeze")
    try:
        result = subprocess.run(  # noqa: S603 - executable is resolved from PATH; argv is literal.
            [
                str(Path(git).resolve(strict=True)),
                "-C",
                str(repo),
                "rev-parse",
                "--show-toplevel",
                "HEAD",
                "HEAD^{tree}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ProfileCompositeError("source checkout identity could not be recomputed") from error
    identities = result.stdout.splitlines()
    if result.returncode != 0 or len(identities) != 3:
        raise ProfileCompositeError("Git returned an incomplete source checkout identity")
    top, commit, tree = identities
    identity = {
        "commit": _sha(commit, "actual Git HEAD", length=40),
        "tree": _sha(tree, "actual Git tree", length=40),
    }
    if Path(top).resolve(strict=True) != repo:
        raise ProfileCompositeError("product root is not inside its actual Git checkout")
    return repo, identity


def derive_platform_placement(
    product_root: str | Path,
    primary_node_ids: list[str],
    *,
    source_file_sha256: dict[str, str],
    host_system: str,
    worker_system: str = "Linux",
    expected_count: int,
) -> dict[str, Any]:
    """Derive host/worker ownership from selected test source predicates.

    Ordinary portable tests run on the host to minimize worker bytes. A test
    whose actual selected pytest skipif excludes the host and admits Linux is
    assigned to Linux. Unknown predicates, unsupported platforms, missing
    sources, and an unassigned test fail closed.
    """
    root = Path(product_root).resolve(strict=True)
    if host_system != "Darwin" or worker_system != "Linux":
        raise ProfileCompositeError("the admitted composite placement is Darwin plus Linux")
    if (
        type(expected_count) is not int
        or expected_count <= 0
        or len(primary_node_ids) != expected_count
    ):
        raise ProfileCompositeError("primary denominator differs from the frozen source selector")
    if primary_node_ids != sorted(set(primary_node_ids)):
        raise ProfileCompositeError("primary node IDs must be sorted and unique")
    rows: list[dict[str, Any]] = []
    host_ids: list[str] = []
    worker_ids: list[str] = []
    for node_id in primary_node_ids:
        relative, selector_path, parameter_id = _canonical_node_id(node_id)
        expected_sha = source_file_sha256.get(relative)
        raw = _read_source_file(root, relative, expected_sha)
        try:
            tree = ast.parse(raw, filename=relative)
        except SyntaxError as error:
            raise ProfileCompositeError(
                f"selected test source is not valid Python: {relative}"
            ) from error
        classes, test = _class_path_for_function(tree, selector_path[:-1], selector_path[-1])
        _reject_parameter_specific_marks(test, parameter_id, _import_bindings(tree))
        conditions = _test_skipif_conditions(tree, classes, test)
        skip_by_platform = {
            system: any(
                bool(_platform_value(condition, system, _import_bindings(tree)))
                for condition in conditions
            )
            for system in (host_system, worker_system)
        }
        eligible = [
            system for system in (host_system, worker_system) if not skip_by_platform[system]
        ]
        if not eligible:
            raise ProfileCompositeError(
                f"selected test is skipped on every admitted platform: {node_id}"
            )
        executor = host_system if host_system in eligible else worker_system
        if executor == host_system:
            host_ids.append(node_id)
        else:
            worker_ids.append(node_id)
        rows.append(
            {
                "node_id": node_id,
                "source_file": relative,
                "source_sha256": expected_sha,
                "parameter_id": parameter_id,
                "skipif": [
                    ast.dump(condition, include_attributes=False) for condition in conditions
                ],
                "skip_on": skip_by_platform,
                "eligible_platforms": eligible,
                "executor": "host" if executor == host_system else "linux-worker",
            }
        )
    if set(host_ids) & set(worker_ids) or set(host_ids) | set(worker_ids) != set(primary_node_ids):
        raise ProfileCompositeError("platform placement does not partition the selected case set")
    return {
        "schema": "policyos.e02.q2.platform-placement.v1",
        "host_system": host_system,
        "worker_system": worker_system,
        "primary_node_ids": list(primary_node_ids),
        "primary_node_ids_sha256": sha256_bytes(("\n".join(primary_node_ids) + "\n").encode()),
        "host_node_ids": host_ids,
        "host_node_ids_sha256": sha256_bytes(("\n".join(host_ids) + "\n").encode()),
        "worker_node_ids": worker_ids,
        "worker_node_ids_sha256": sha256_bytes(("\n".join(worker_ids) + "\n").encode()),
        "cases": rows,
    }


def _validate_hash_map(
    values: object, expected_keys: tuple[str, ...], label: str
) -> dict[str, str]:
    if type(values) is not dict or set(values) != set(expected_keys):
        raise ProfileCompositeError(f"{label} must contain the complete named SHA-256 set")
    return {key: _sha(values[key], f"{label}.{key}") for key in expected_keys}


def _plan_digest(plan: dict[str, Any]) -> str:
    if type(plan) is not dict or type(plan.get("plan_sha256")) is not str:
        raise ProfileCompositeError("composite plan identity is missing")
    unsigned = dict(plan)
    expected = unsigned.pop("plan_sha256")
    actual = sha256_bytes(canonical_json_bytes(unsigned))
    if expected != actual:
        raise ProfileCompositeError("composite plan bytes changed after source freeze")
    return actual


def create_composite_plan(
    *,
    source: dict[str, str],
    input_pins: dict[str, str],
    expected_artifact_chain: dict[str, str],
    artifacts: list[dict[str, Any]],
    product_root: str | Path,
    primary_manifest_path: str | Path,
    supplemental_manifest_path: str | Path,
    source_audit_receipt_path: str | Path,
    source_inventory_path: str | Path,
    owner_inventory_path: str | Path,
    build_profile_path: str | Path,
    consumer_runner_path: str | Path,
    dependency_profile_path: str | Path,
    expected_primary_count: int,
    expected_supplemental_count: int = 6,
) -> dict[str, Any]:
    """Bind manifests, source audit, source bytes, resources, wheels and placement."""
    if type(source) is not dict or set(source) != {"commit", "tree"}:
        raise ProfileCompositeError("composite plan source identity is incomplete")
    source = {key: _sha(source[key], f"source.{key}", length=40) for key in ("commit", "tree")}
    input_pins = _validate_hash_map(input_pins, INPUT_PIN_KEYS, "input pins")
    chain = _validate_hash_map(expected_artifact_chain, ARTIFACT_CHAIN_KEYS, "artifact chain")
    product = Path(product_root).resolve(strict=True)
    repo_root, actual_source = _git_source_identity(product)
    if actual_source != source:
        raise ProfileCompositeError("selected source commit/tree differs from actual Git HEAD")

    support_inputs: dict[str, dict[str, str]] = {}
    for pin_name, path_value in (
        ("build_profile_sha256", build_profile_path),
        ("consumer_runner_sha256", consumer_runner_path),
        ("dependency_profile_sha256", dependency_profile_path),
    ):
        path, raw = _read_absolute_regular_file(path_value, pin_name.removesuffix("_sha256"))
        digest = hashlib.sha256(raw).hexdigest()
        if digest != input_pins[pin_name]:
            raise ProfileCompositeError(f"{pin_name} differs from its selected input file")
        support_inputs[pin_name] = {"path": str(path), "sha256": digest}

    q2_runner_path = product.joinpath(*PurePosixPath(Q2_RUNNER_RELATIVE).parts)
    q2_runner_raw = _read_source_file(product, Q2_RUNNER_RELATIVE, None)
    q2_runner_sha = hashlib.sha256(q2_runner_raw).hexdigest()
    q2_runner = _load_source_module(q2_runner_path, f"e02_q2_source_runner_{source['commit'][:12]}")
    supplemental_runner_path = product.joinpath(*PurePosixPath(SUPPLEMENTAL_RUNNER_RELATIVE).parts)
    supplemental_runner_raw = _read_source_file(product, SUPPLEMENTAL_RUNNER_RELATIVE, None)
    supplemental_runner_sha = hashlib.sha256(supplemental_runner_raw).hexdigest()
    if supplemental_runner_sha != input_pins["supplemental_runner_sha256"]:
        raise ProfileCompositeError("supplemental runner differs from its source-bound pin")
    supplemental_runner = _load_source_module(
        supplemental_runner_path, f"e02_q2_supplemental_runner_{source['commit'][:12]}"
    )

    def pinned_json(
        path_value: str | Path, pin_name: str, label: str
    ) -> tuple[Path, dict[str, Any]]:
        path, raw = _read_absolute_regular_file(path_value, label)
        if hashlib.sha256(raw).hexdigest() != input_pins[pin_name]:
            raise ProfileCompositeError(f"{label} bytes differ from their source-bound pin")
        return path, load_json_bytes(raw, label=label)

    primary_path, manifest = pinned_json(
        primary_manifest_path, "primary_manifest_sha256", "primary manifest"
    )
    supplemental_path, supplemental_manifest = pinned_json(
        supplemental_manifest_path, "supplemental_manifest_sha256", "supplemental manifest"
    )
    audit_path, audit = pinned_json(
        source_audit_receipt_path, "source_audit_receipt_sha256", "source-audit receipt"
    )
    source_inventory_path, inventory = pinned_json(
        source_inventory_path, "source_inventory_sha256", "source inventory"
    )
    validate_inventory(inventory)
    if inventory.get("source") != source:
        raise ProfileCompositeError("source package inventory belongs to another source freeze")
    primary_baseline, _ = _validate_freeze(
        manifest, expected_commit=source["commit"], expected_tree=source["tree"]
    )
    if primary_baseline.get("source_sha") != source["commit"]:
        raise ProfileCompositeError("primary manifest baseline differs from the frozen source")
    selection = validate_source_audit_selection(
        audit,
        expected_commit=source["commit"],
        expected_tree=source["tree"],
        manifest_sha256=input_pins["primary_manifest_sha256"],
        supplemental_manifest_sha256=input_pins["supplemental_manifest_sha256"],
    )
    profiles = list(PROFILE_CHAIN_KEYS)
    if selection["profiles"] != profiles:
        raise ProfileCompositeError("source-audit profiles differ from the three Q2 producers")
    primary_ids = selection["primary_node_ids"]
    supplemental_node_ids = selection["supplemental_node_ids"]
    if (
        len(primary_ids) != expected_primary_count
        or len(supplemental_node_ids) != expected_supplemental_count
    ):
        raise ProfileCompositeError(
            "source-audit case denominator differs from the admitted Q2 scope"
        )
    source_map = manifest.get("current_primary_suite", {}).get("source_file_sha256")
    if type(source_map) is not dict or not source_map:
        raise ProfileCompositeError("primary manifest omits the complete selected test-source map")
    normalized_source_map: dict[str, str] = {}
    for relative, digest in sorted(source_map.items()):
        if type(relative) is not str:
            raise ProfileCompositeError("primary source map contains a non-string path")
        raw = _read_source_file(product, relative, digest)
        normalized_source_map[relative] = hashlib.sha256(raw).hexdigest()
    source_map_digest = sha256_bytes(canonical_json_bytes(normalized_source_map))
    if source_map_digest != input_pins["test_source_closure_sha256"]:
        raise ProfileCompositeError(
            "selected test-source closure differs from its recomputed digest"
        )
    baseline_ids = q2_runner.baseline_node_ids(product, manifest)
    recomputed_primary = q2_runner.verify_current_primary_suite_sources(
        product, manifest, baseline_ids
    )
    transitive_bindings = q2_runner.verify_transitive_test_bindings(product, manifest, baseline_ids)
    if sorted(recomputed_primary) != primary_ids:
        raise ProfileCompositeError(
            "source-audit primary selector differs from the current canonical source manifest"
        )
    recomputed_supplemental = supplemental_runner.suite_node_ids(product, supplemental_manifest)
    if sorted(recomputed_supplemental) != supplemental_node_ids:
        raise ProfileCompositeError(
            "source-audit supplemental selector differs from the current canonical source manifest"
        )
    original_test_paths = manifest.get("original_q2_suite", {}).get("test_paths")
    if type(original_test_paths) is not list or not original_test_paths:
        raise ProfileCompositeError("primary manifest omits the special JUnit document source path")
    special_document_path = original_test_paths[-1]
    if type(special_document_path) is not str:
        raise ProfileCompositeError("primary manifest special JUnit document path is malformed")
    placement = derive_platform_placement(
        product,
        primary_ids,
        source_file_sha256=normalized_source_map,
        host_system="Darwin",
        worker_system="Linux",
        expected_count=expected_primary_count,
    )
    la029 = (
        "tests/unit/data_forge/domains/ukraine/test_installed_wheel_no_checkout.py::"
        "test_installed_wheel_without_checkout_reports_gate_unavailable"
    )
    if placement["worker_node_ids"] != [la029]:
        raise ProfileCompositeError("the selected Linux-only partition differs from actual LA-029")
    worker_test_path = placement["worker_node_ids"][0].split("::", 1)[0]
    worker_input_files: list[dict[str, Any]] = []
    for relative, role in (
        (worker_test_path, "selected_test"),
        ("tests/unit/data_forge/conftest.py", "pytest_conftest"),
        ("pytest.ini", "pytest_configuration"),
    ):
        raw = _read_source_file(product, relative, normalized_source_map.get(relative))
        worker_input_files.append(
            {
                "path": relative,
                "role": role,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    if len({row["path"] for row in worker_input_files}) != len(worker_input_files):
        raise ProfileCompositeError("worker test input closure repeats a source path")
    profiles = list(PROFILE_CHAIN_KEYS)
    if type(artifacts) is not list or len(artifacts) != len(profiles):
        raise ProfileCompositeError("all three source-derived wheel artifacts are required")
    artifact_rows: list[dict[str, Any]] = []
    for profile, row in zip(profiles, artifacts, strict=True):
        if type(row) is not dict or set(row) != {"profile", "chain_key", "path", "bytes", "sha256"}:
            raise ProfileCompositeError("wheel artifact row has an unsupported shape")
        if row["profile"] != profile or row["chain_key"] != PROFILE_CHAIN_KEYS[profile]:
            raise ProfileCompositeError(
                "wheel artifact order/profile chain differs from source contract"
            )
        path, wheel_raw = _read_absolute_regular_file(row["path"], f"{profile} wheel")
        if type(row["bytes"]) is not int or row["bytes"] <= 0:
            raise ProfileCompositeError(f"{profile} wheel is absent or not a regular nonempty file")
        digest = _sha(row["sha256"], f"{profile} wheel SHA-256")
        if len(wheel_raw) != row["bytes"] or hashlib.sha256(wheel_raw).hexdigest() != digest:
            raise ProfileCompositeError(f"{profile} wheel bytes differ from its artifact receipt")
        if digest != chain[PROFILE_CHAIN_KEYS[profile]]:
            raise ProfileCompositeError(f"{profile} wheel differs from the producer artifact chain")
        artifact_rows.append({**row, "path": str(path)})
    owner_path, owner_raw = _read_absolute_regular_file(
        owner_inventory_path, "runtime resource owner inventory"
    )
    if hashlib.sha256(owner_raw).hexdigest() != input_pins["resource_owner_inventory_sha256"]:
        raise ProfileCompositeError("runtime resource owner inventory differs from its source pin")
    owner_inventory = load_json_bytes(owner_raw, label="runtime resource owner inventory")
    if type(owner_inventory) is not dict or type(owner_inventory.get("assets")) is not list:
        raise ProfileCompositeError("runtime resource owner inventory omits its complete assets")
    owner_resources: list[dict[str, Any]] = []
    seen_resources: set[str] = set()
    for row in owner_inventory["assets"]:
        if type(row) is not dict or not {"source", "wheel", "bytes", "sha256"} <= set(row):
            raise ProfileCompositeError("runtime resource inventory row is malformed")
        wheel = row["wheel"]
        source_relative = row["source"]
        parsed = PurePosixPath(wheel) if type(wheel) is str else None
        parsed_source = PurePosixPath(source_relative) if type(source_relative) is str else None
        if (
            parsed is None
            or parsed_source is None
            or parsed.is_absolute()
            or parsed.as_posix() != wheel
            or any(part in {"", ".", ".."} for part in parsed.parts)
            or parsed_source.is_absolute()
            or parsed_source.as_posix() != source_relative
            or any(part in {"", ".", ".."} for part in parsed_source.parts)
            or wheel in seen_resources
            or type(row["bytes"]) is not int
            or row["bytes"] < 0
        ):
            raise ProfileCompositeError("runtime resource paths or byte counts are invalid")
        source_raw = _read_source_file(product, source_relative, row["sha256"])
        if len(source_raw) != row["bytes"]:
            raise ProfileCompositeError(f"runtime resource byte count differs from source: {wheel}")
        seen_resources.add(wheel)
        owner_resources.append(
            {
                "source": source_relative,
                "wheel": wheel,
                "bytes": row["bytes"],
                "sha256": _sha(row["sha256"], "resource SHA-256"),
            }
        )
    forced_assets = {
        (row["source"], row["wheel"], row["bytes"], row["sha256"])
        for row in inventory["rows"]
        if row["kind"] == "force_include"
    }
    owner_asset_rows = {
        (row["source"], row["wheel"], row["bytes"], row["sha256"]) for row in owner_resources
    }
    if owner_asset_rows != forced_assets:
        raise ProfileCompositeError(
            "source-owned runtime resources differ from the complete wheel force-include set"
        )
    if not owner_resources:
        raise ProfileCompositeError("runtime resource owner inventory is empty")
    owners = owner_inventory.get("owners")
    catalog_defaults = owners.get("catalog_defaults") if type(owners) is dict else None
    digest_registry = owners.get("digest_registry") if type(owners) is dict else None
    worker_assets = owners.get("worker_profile_assets") if type(owners) is dict else None
    owner_rows = [
        *(catalog_defaults if type(catalog_defaults) is list else []),
        *(worker_assets if type(worker_assets) is list else []),
        *([digest_registry] if type(digest_registry) is dict else []),
    ]
    if (
        type(catalog_defaults) is not list
        or type(digest_registry) is not dict
        or type(worker_assets) is not list
        or not catalog_defaults
        or not worker_assets
    ):
        raise ProfileCompositeError("runtime owner inventory omits a required resource owner group")
    if any(
        type(row) is not dict
        or any(type(row.get(key)) is not str or not row[key] for key in ("name", "source", "wheel"))
        for row in owner_rows
    ):
        raise ProfileCompositeError("runtime resource owner path/name records are malformed")
    if len({row["name"] for row in catalog_defaults}) != len(catalog_defaults):
        raise ProfileCompositeError("runtime owner inventory duplicates a catalog default name")
    if {row["wheel"] for row in owner_rows} != seen_resources:
        raise ProfileCompositeError(
            "runtime owner groups do not cover the complete resource inventory"
        )
    if len({row["wheel"] for row in owner_rows}) != len(owner_rows):
        raise ProfileCompositeError("runtime resource owner groups duplicate a wheel target")
    if {(row["source"], row["wheel"]) for row in owner_rows} != {
        (row["source"], row["wheel"]) for row in owner_resources
    }:
        raise ProfileCompositeError("runtime owner groups relabel a resource source or target")
    if (
        type(placement) is not dict
        or placement.get("schema") != "policyos.e02.q2.platform-placement.v1"
    ):
        raise ProfileCompositeError("placement is not source-derived platform evidence")
    primary_ids = placement.get("primary_node_ids")
    host_ids = placement.get("host_node_ids")
    worker_ids = placement.get("worker_node_ids")
    for label, values, count in (
        ("primary", primary_ids, expected_primary_count),
        ("host", host_ids, expected_primary_count - 1),
        ("worker", worker_ids, 1),
    ):
        if type(values) is not list or values != sorted(set(values)):
            raise ProfileCompositeError(f"{label} platform selector IDs are not sorted and unique")
        if len(values) != count:
            raise ProfileCompositeError(
                f"{label} platform selector denominator differs from freeze"
            )
    if set(host_ids) & set(worker_ids) or set(host_ids) | set(worker_ids) != set(primary_ids):
        raise ProfileCompositeError(
            "host and Linux selections do not form a complete disjoint partition"
        )
    for field, values in (
        ("primary_node_ids_sha256", primary_ids),
        ("host_node_ids_sha256", host_ids),
        ("worker_node_ids_sha256", worker_ids),
    ):
        observed = sha256_bytes(("\n".join(values) + "\n").encode())
        if placement.get(field) != observed:
            raise ProfileCompositeError(f"placement {field} differs from the actual ID set")
    if placement.get("host_system") != "Darwin" or placement.get("worker_system") != "Linux":
        raise ProfileCompositeError("placement platform identity differs from the admitted pair")
    if supplemental_node_ids != sorted(set(supplemental_node_ids)) or set(primary_ids) & set(
        supplemental_node_ids
    ):
        raise ProfileCompositeError(
            "primary/supplemental selector sets differ from the frozen denominator"
        )
    primary_digest = sha256_bytes(("\n".join(primary_ids) + "\n").encode())
    supplemental_digest = sha256_bytes(("\n".join(supplemental_node_ids) + "\n").encode())
    run_plan = [
        {
            "phase": "primary",
            "profile": profile,
            "executor": executor,
            "platform": placement["host_system"]
            if executor == "host"
            else placement["worker_system"],
            "artifact_sha256": chain[PROFILE_CHAIN_KEYS[profile]],
            "node_ids": host_ids if executor == "host" else worker_ids,
            "node_ids_sha256": placement["host_node_ids_sha256"]
            if executor == "host"
            else placement["worker_node_ids_sha256"],
        }
        for profile in profiles
        for executor in ("host", "linux-worker")
    ]
    plan = {
        "schema": COMPOSITE_SCHEMA,
        "source": source,
        "source_checkout": {"path": str(repo_root), **actual_source},
        "input_pins": input_pins,
        "artifact_chain": chain,
        "profiles": profiles,
        "artifacts": artifact_rows,
        "source_inputs": {
            "primary_manifest": {
                "path": str(primary_path),
                "sha256": input_pins["primary_manifest_sha256"],
            },
            "supplemental_manifest": {
                "path": str(supplemental_path),
                "sha256": input_pins["supplemental_manifest_sha256"],
            },
            "source_audit_receipt": {
                "path": str(audit_path),
                "sha256": input_pins["source_audit_receipt_sha256"],
            },
            "source_inventory": {
                "path": str(source_inventory_path),
                "sha256": input_pins["source_inventory_sha256"],
            },
            "test_source_files": normalized_source_map,
            "test_source_files_sha256": source_map_digest,
            "canonical_q2_runner": {"path": str(q2_runner_path), "sha256": q2_runner_sha},
            "canonical_supplemental_runner": {
                "path": str(supplemental_runner_path),
                "sha256": supplemental_runner_sha,
            },
            "support_files": support_inputs,
            "transitive_bindings_sha256": sha256_bytes(canonical_json_bytes(transitive_bindings)),
            "worker_test_input_files": worker_input_files,
            "worker_test_input_files_sha256": sha256_bytes(
                canonical_json_bytes(worker_input_files)
            ),
        },
        "owner_inventory": {
            "sha256": input_pins["resource_owner_inventory_sha256"],
            "path": str(owner_path),
        },
        "owner_resources": owner_resources,
        "catalog_default_names": sorted(row["name"] for row in catalog_defaults),
        "catalog_default_targets": {
            row["name"]: row["wheel"]
            for row in sorted(catalog_defaults, key=lambda row: row["name"])
        },
        "digest_registry_target": digest_registry["wheel"],
        "worker_profile_targets": sorted(row["wheel"] for row in worker_assets),
        "special_document_path": special_document_path,
        "placement": placement,
        "primary": {
            "node_ids": primary_ids,
            "node_ids_sha256": primary_digest,
            "count": expected_primary_count,
            "unique_profile_case_count": len(profiles) * expected_primary_count,
        },
        "supplemental": {
            "node_ids": supplemental_node_ids,
            "node_ids_sha256": supplemental_digest,
            "count": expected_supplemental_count,
            "admission": "blocked_until_all_primary_profile_partitions_reconcile",
        },
        "run_plan": run_plan,
    }
    plan["plan_sha256"] = sha256_bytes(canonical_json_bytes(plan))
    return plan


def _worker_mounts_module() -> ModuleType:
    module_path = Path(__file__).with_name("worker_mounts.py")
    spec = importlib.util.spec_from_file_location("e02_q2_profile_worker_mounts", module_path)
    if spec is None or spec.loader is None:
        raise ProfileCompositeError("cannot load the frozen worker mount verifier")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _safe_evidence(
    root: Path,
    ref: object,
    label: str,
    *,
    mount_map: dict[str, Any] | None = None,
    role: str = "receipts",
) -> tuple[Path, bytes]:
    if type(ref) is not dict or set(ref) != {"path", "sha256"}:
        raise ProfileCompositeError(f"{label} evidence reference has an unsupported shape")
    relative = ref["path"]
    parsed = PurePosixPath(relative) if type(relative) is str else None
    if parsed is not None and parsed.is_absolute():
        if mount_map is None:
            raise ProfileCompositeError(f"{label} absolute worker path lacks its exact mount map")
        try:
            worker_mounts = _worker_mounts_module()
            path = worker_mounts.worker_path_to_host(relative, mount_map, role=role)
        except (OSError, ValueError) as error:
            raise ProfileCompositeError(
                f"{label} worker path did not map to its bound host prefix"
            ) from error
        try:
            info = path.lstat()
        except OSError as error:
            raise ProfileCompositeError(
                f"{label} worker evidence is absent from its mapped prefix"
            ) from error
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise ProfileCompositeError(f"{label} mapped worker evidence is not a regular file")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != _sha(ref["sha256"], f"{label} digest"):
            raise ProfileCompositeError(f"{label} mapped worker bytes differ from their SHA-256")
        return path, raw
    if (
        parsed is None
        or parsed.is_absolute()
        or parsed.as_posix() != relative
        or any(part in {"", ".", ".."} for part in parsed.parts)
    ):
        raise ProfileCompositeError(f"{label} evidence path is not a rooted relative path")
    path = root
    for part in parsed.parts:
        path = path / part
        try:
            info = path.lstat()
        except OSError as error:
            raise ProfileCompositeError(f"{label} evidence is absent: {relative}") from error
        if stat.S_ISLNK(info.st_mode):
            raise ProfileCompositeError(f"{label} evidence traverses a symlink: {relative}")
    if not stat.S_ISREG(path.stat().st_mode):
        raise ProfileCompositeError(f"{label} evidence is not a regular file: {relative}")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != _sha(ref["sha256"], f"{label} digest"):
        raise ProfileCompositeError(f"{label} evidence bytes differ from its SHA-256")
    return path, raw


def _junit_observations(raw: bytes, special_document_path: str) -> tuple[list[str], dict[str, int]]:
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as error:
        raise ProfileCompositeError("primary JUnit is malformed XML") from error
    node_ids: list[str] = []
    counts = {"tests": 0, "skipped": 0, "failures": 0, "errors": 0}
    for case in root.iter("testcase"):
        classname = case.attrib.get("classname")
        name = case.attrib.get("name")
        if not classname or not name:
            raise ProfileCompositeError("primary JUnit testcase omits classname or name")
        if classname == "test_installed_catalog_defaults":
            path = special_document_path
        else:
            dotted = classname.split(".")
            path = "/".join([*dotted[:-1], dotted[-1] + ".py"])
        node_ids.append(f"{path}::{name}")
        counts["tests"] += 1
        counts["skipped"] += case.find("skipped") is not None
        counts["failures"] += case.find("failure") is not None
        counts["errors"] += case.find("error") is not None
    if len(node_ids) != len(set(node_ids)):
        raise ProfileCompositeError("primary JUnit repeats a node ID")
    return sorted(node_ids), counts


def _load_evidence_json(
    root: Path,
    ref: object,
    label: str,
    *,
    mount_map: dict[str, Any] | None = None,
    role: str = "receipts",
) -> tuple[dict[str, Any], str]:
    path, raw = _safe_evidence(root, ref, label, mount_map=mount_map, role=role)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ProfileCompositeError(f"{label} evidence is not JSON") from error
    if type(value) is not dict:
        raise ProfileCompositeError(f"{label} JSON root is not an object")
    return value, str(path)


def _resolved_directory(value: object, label: str) -> Path:
    if type(value) is not str:
        raise ProfileCompositeError(f"{label} must be an absolute path")
    supplied = Path(value)
    if not supplied.is_absolute() or ".." in supplied.parts:
        raise ProfileCompositeError(f"{label} must be an absolute canonical path")
    try:
        resolved = supplied.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ProfileCompositeError(f"{label} is unavailable") from error
    if not resolved.is_dir():
        raise ProfileCompositeError(f"{label} is not a directory")
    return resolved


def _origin_paths(origin: dict[str, Any], label: str) -> tuple[Path, Path, list[Path]]:
    purelib = _resolved_directory(origin.get("purelib"), f"{label} purelib")
    dependency_site = _resolved_directory(origin.get("dependency_site"), f"{label} dependency site")
    raw_sys_path = origin.get("sys_path")
    if type(raw_sys_path) is not list or not raw_sys_path:
        raise ProfileCompositeError(f"{label} sys.path proof is missing")
    paths: list[Path] = []
    for raw_path in raw_sys_path:
        if type(raw_path) is not str or not raw_path:
            raise ProfileCompositeError(f"{label} sys.path has a non-path entry")
        path = Path(raw_path)
        if not path.is_absolute() or ".." in path.parts:
            raise ProfileCompositeError(
                f"{label} sys.path contains a relative or noncanonical path"
            )
        paths.append(path.resolve(strict=False))
    if purelib not in paths or dependency_site not in paths:
        raise ProfileCompositeError(f"{label} sys.path omits the target or dependency site")
    if paths.index(purelib) >= paths.index(dependency_site):
        raise ProfileCompositeError(f"{label} dependencies precede the selected package target")
    return purelib, dependency_site, paths


def _validate_origin_rows(origins: object, purelib: Path, label: str) -> set[str]:
    if type(origins) is not dict or not origins:
        raise ProfileCompositeError(f"{label} has no actual Q2 module origins")
    names: set[str] = set()
    for name, row in origins.items():
        if type(name) is not str or not name or type(row) is not dict:
            raise ProfileCompositeError(f"{label} module-origin row is malformed")
        names.add(name)
        file_paths: list[object] = []
        for key in ("file", "resolved_file", "spec_origin", "resolved_spec_origin"):
            if key in row:
                file_paths.append(row[key])
        namespace = row.get("namespace_locations")
        if namespace is not None:
            if type(namespace) is not list or not namespace:
                raise ProfileCompositeError(f"{label} namespace origin is malformed")
            for location in namespace:
                if type(location) is not dict:
                    raise ProfileCompositeError(f"{label} namespace path is malformed")
                file_paths.extend(location.get(key) for key in ("path", "resolved_path"))
        if not file_paths or any(type(path) is not str for path in file_paths):
            raise ProfileCompositeError(f"{label} module origin omits actual paths")
        for raw_path in file_paths:
            path = Path(raw_path)
            if not path.is_absolute() or not path.resolve(strict=True).is_relative_to(purelib):
                raise ProfileCompositeError(f"{label} module {name} escaped installed purelib")
    return names


def _validate_worker_origin(
    origin: dict[str, Any],
    *,
    mount_map: dict[str, Any],
    runtime_contract: dict[str, Any],
    source_input_root: str,
    label: str,
) -> tuple[Path, PurePosixPath, list[PurePosixPath], PurePosixPath, set[str]]:
    """Map worker origin evidence back to its host prefix and verify every loaded file."""
    worker_mounts = _worker_mounts_module()
    raw_purelib = origin.get("purelib")
    raw_dependency = origin.get("dependency_site")
    if type(raw_purelib) is not str or type(raw_dependency) is not str:
        raise ProfileCompositeError(f"{label} worker purelib/dependency paths are malformed")
    purelib_worker = PurePosixPath(raw_purelib)
    dependency_worker = PurePosixPath(raw_dependency)
    if (
        not purelib_worker.is_absolute()
        or ".." in purelib_worker.parts
        or purelib_worker.as_posix() != raw_purelib
        or origin.get("dependency_site") != runtime_contract["worker"]["dependency_site"]
    ):
        raise ProfileCompositeError(
            f"{label} worker purelib/dependency paths are not the measured prefix"
        )
    raw_sys_path = origin.get("sys_path")
    if type(raw_sys_path) is not list or not raw_sys_path:
        raise ProfileCompositeError(f"{label} worker sys.path proof is missing")
    sys_paths: list[PurePosixPath] = []
    for value in raw_sys_path:
        path = PurePosixPath(value) if type(value) is str else None
        if path is None or not path.is_absolute() or ".." in path.parts or path.as_posix() != value:
            raise ProfileCompositeError(f"{label} worker sys.path contains a noncanonical path")
        sys_paths.append(path)
    if purelib_worker not in sys_paths or dependency_worker not in sys_paths:
        raise ProfileCompositeError(
            f"{label} worker sys.path omits purelib or measured dependencies"
        )
    if sys_paths.index(purelib_worker) >= sys_paths.index(dependency_worker):
        raise ProfileCompositeError(f"{label} worker dependencies precede the installed target")
    input_root = PurePosixPath(source_input_root)
    if not input_root.is_absolute() or any(
        path == input_root or path.is_relative_to(input_root) for path in sys_paths
    ):
        raise ProfileCompositeError(f"{label} worker sys.path exposes the transferred test inputs")
    purelib_host = worker_mounts.worker_path_to_host(
        purelib_worker.as_posix(), mount_map, role="profile-prefix"
    )
    if not purelib_host.is_dir():
        raise ProfileCompositeError(f"{label} mapped worker purelib is not a real directory")
    origins = origin.get("origin_details", origin.get("origins"))
    if type(origins) is not dict or not origins:
        raise ProfileCompositeError(f"{label} has no actual worker module origins")
    names: set[str] = set()
    for name, row in origins.items():
        if type(name) is not str or not name or type(row) is not dict:
            raise ProfileCompositeError(f"{label} worker module-origin row is malformed")
        names.add(name)
        file_paths: list[object] = []
        for key in ("file", "resolved_file", "spec_origin", "resolved_spec_origin"):
            if key in row:
                file_paths.append(row[key])
        namespace = row.get("namespace_locations")
        if namespace is not None:
            if type(namespace) is not list or not namespace:
                raise ProfileCompositeError(f"{label} worker namespace origin is malformed")
            for location in namespace:
                if type(location) is not dict:
                    raise ProfileCompositeError(f"{label} worker namespace path is malformed")
                file_paths.extend(location.get(key) for key in ("path", "resolved_path"))
        if not file_paths or any(type(value) is not str for value in file_paths):
            raise ProfileCompositeError(f"{label} worker origin omits actual paths")
        for value in file_paths:
            path = PurePosixPath(value)
            if (
                not path.is_absolute()
                or ".." in path.parts
                or not path.is_relative_to(purelib_worker)
            ):
                raise ProfileCompositeError(
                    f"{label} worker module {name} escaped installed purelib"
                )
            observed_host = worker_mounts.worker_path_to_host(
                path.as_posix(), mount_map, role="profile-prefix"
            )
            if not observed_host.is_file():
                raise ProfileCompositeError(
                    f"{label} worker module {name} is absent from the mapped prefix"
                )
    return purelib_host, dependency_worker, sys_paths, purelib_worker, names


def reconcile_primary_execution(
    result_path: str | Path,
    *,
    plan: dict[str, Any],
    profile: str,
    executor: str,
    special_document_path: str,
) -> dict[str, Any]:
    """Recompute one host or worker partition from retained output bytes."""
    plan_sha256 = _plan_digest(plan)
    result_file, result_raw = _read_absolute_regular_file(result_path, "execution result")
    try:
        receipt = json.loads(result_raw)
    except json.JSONDecodeError as error:
        raise ProfileCompositeError("execution result is not JSON") from error
    if type(receipt) is not dict or receipt.get("schema") != EXECUTION_SCHEMA:
        raise ProfileCompositeError("execution result schema is unsupported")
    if executor not in {"host", "linux-worker"} or profile not in plan["profiles"]:
        raise ProfileCompositeError("execution result profile/executor is not in the plan")
    expected_platform = "Darwin" if executor == "host" else "Linux"
    run_row = next(
        (
            row
            for row in plan["run_plan"]
            if row["profile"] == profile and row["executor"] == executor
        ),
        None,
    )
    if run_row is None:
        raise ProfileCompositeError("execution partition is not selected in the source plan")
    if (
        receipt.get("source") != plan["source"]
        or receipt.get("input_pins") != plan["input_pins"]
        or receipt.get("profile") != profile
        or receipt.get("executor") != executor
        or receipt.get("artifact_sha256") != run_row["artifact_sha256"]
        or receipt.get("plan_sha256") != plan_sha256
        or receipt.get("runner_sha256") != plan["input_pins"]["consumer_runner_sha256"]
        or type(receipt.get("returncode")) is not int
        or receipt["returncode"] != 0
    ):
        raise ProfileCompositeError("execution receipt source/artifact/runner binding differs")
    root = result_file.parent
    worker_mount_map: dict[str, Any] | None = None
    worker_contract: dict[str, Any] | None = None
    worker_transport: dict[str, Any] | None = None
    worker_request: dict[str, Any] | None = None
    worker_identity: dict[str, str] | None = None
    if executor == "linux-worker":
        worker_transport, _ = _load_evidence_json(
            root, receipt.get("transport_proof"), "worker transport proof"
        )
        worker_mount_map = worker_transport.get("mount_map")
        worker_contract = worker_transport.get("runtime_contract")
        worker_mounts = _worker_mounts_module()
        if type(worker_mount_map) is not dict or type(worker_contract) is not dict:
            raise ProfileCompositeError("Linux transport omits the actual runtime or mount mapping")
        worker_contract = worker_mounts.validate_runtime_contract(worker_contract)
        runtime_sha = hashlib.sha256(canonical_json_bytes(worker_contract)).hexdigest()
        if (
            worker_transport.get("source") != plan["source"]
            or worker_transport.get("input_pins") != plan["input_pins"]
            or worker_transport.get("transport_status") != "hash_verified_exact_artifact"
            or worker_transport.get("artifact_chain") != plan["artifact_chain"]
            or worker_transport.get("container_id") is None
            or worker_transport.get("runtime_contract_sha256") != runtime_sha
            or worker_transport.get("request_transport") != "stdin_sha256"
        ):
            raise ProfileCompositeError(
                "Linux transport differs from the selected source/runtime plan"
            )
        worker_mounts.validate_mount_map(
            worker_mount_map,
            expected_source=plan["source"],
            expected_plan_sha256=plan_sha256,
            expected_profile=profile,
            expected_artifact_sha256=run_row["artifact_sha256"],
            expected_node_ids_sha256=run_row["node_ids_sha256"],
            expected_runtime_contract_sha256=runtime_sha,
        )
        map_sha = hashlib.sha256(canonical_json_bytes(worker_mount_map)).hexdigest()
        if worker_transport.get("mount_map_sha256") != map_sha:
            raise ProfileCompositeError("Linux transport mount-map digest differs")
        host_launch_path, host_launch_raw = _read_absolute_regular_file(
            root / "host-launch.json", "host worker launch"
        )
        try:
            host_launch = load_json_bytes(host_launch_raw, label="host worker launch")
        except SplitProtocolError as error:
            raise ProfileCompositeError("host worker launch evidence is not strict JSON") from error
        launch_stdout_ref = host_launch.get("stdout")
        launch_stderr_ref = host_launch.get("stderr")
        _safe_evidence(root, launch_stdout_ref, "host worker stdout")
        _safe_evidence(root, launch_stderr_ref, "host worker stderr")
        request_ref = worker_transport.get("request_ref")
        request_path, request_raw = _safe_evidence(root, request_ref, "worker request")
        expected_worker_argv = [
            "docker",
            "--config",
            worker_contract["docker"]["config_path"],
            "--context",
            worker_contract["docker"]["context"],
            "exec",
            "-i",
            worker_transport["container_id"],
            worker_contract["worker"]["python_executable"],
            "-I",
            PurePosixPath(
                next(
                    row["worker_root"]
                    for row in worker_mount_map["mounts"]
                    if row["role"] == "inputs"
                ),
                "split_consumer.py",
            ).as_posix(),
            "--run-profile-partition",
            "--request-stdin",
            "--request-sha256",
            receipt.get("request_sha256"),
        ]
        if (
            host_launch.get("schema") != "policyos.e02.q2.worker-host-launch.v1"
            or host_launch.get("source") != plan["source"]
            or host_launch.get("profile") != profile
            or host_launch.get("artifact_sha256") != run_row["artifact_sha256"]
            or host_launch.get("request_sha256") != receipt.get("request_sha256")
            or host_launch.get("request_transport") != "stdin_sha256"
            or host_launch.get("container_identity")
            != {
                "container_id": worker_transport["container_id"],
                "image_id": worker_transport.get("image_id"),
            }
            or host_launch.get("argv") != expected_worker_argv
            or type(host_launch.get("timeout_seconds")) is not int
            or host_launch.get("timeout_seconds", 0) <= 0
            or host_launch.get("timed_out") is not False
            or host_launch.get("returncode") != 0
            or type(launch_stdout_ref) is not dict
            or set(launch_stdout_ref) != {"path", "sha256"}
            or type(launch_stderr_ref) is not dict
            or set(launch_stderr_ref) != {"path", "sha256"}
            or host_launch.get("stdout")
            != {"path": "host-command-stdout.txt", "sha256": launch_stdout_ref.get("sha256")}
            or host_launch.get("stderr")
            != {"path": "host-command-stderr.txt", "sha256": launch_stderr_ref.get("sha256")}
            or Path(host_launch_path).name != "host-launch.json"
            or request_path.name != "request.json"
            or hashlib.sha256(request_raw).hexdigest() != receipt.get("request_sha256")
        ):
            raise ProfileCompositeError(
                "Linux worker command receipt does not prove the selected stdin consumer launch"
            )
        input_members = worker_transport.get("input_members")
        artifact_members = worker_transport.get("artifact_members")
        if type(input_members) is not list or type(artifact_members) is not list:
            raise ProfileCompositeError("Linux transport omits complete mounted member lists")
        if hashlib.sha256(request_raw).hexdigest() != receipt.get("request_sha256"):
            raise ProfileCompositeError(
                "Linux source-bound request differs from its result receipt"
            )
        if worker_mounts.verify_mapped_tree(
            worker_mount_map, role="inputs", expected_files=input_members
        )["member_count"] != len(input_members):
            raise ProfileCompositeError("Linux input mount differs from its complete member list")
        if worker_mounts.verify_mapped_tree(
            worker_mount_map, role="artifacts", expected_files=artifact_members
        )["member_count"] != len(artifact_members):
            raise ProfileCompositeError(
                "Linux artifact mount differs from its complete member list"
            )
        try:
            worker_request = load_json_bytes(request_raw, label="Linux profile request")
        except SplitProtocolError as error:
            raise ProfileCompositeError("Linux profile request is not strict JSON") from error
        if (
            worker_request.get("schema") != "policyos.e02.q2.worker-profile-partition-request.v1"
            or worker_request.get("source") != plan["source"]
            or worker_request.get("profile") != profile
            or worker_request.get("artifact_sha256") != run_row["artifact_sha256"]
            or worker_request.get("node_ids") != run_row["node_ids"]
            or worker_request.get("node_ids_sha256") != run_row["node_ids_sha256"]
            or worker_request.get("composite_plan") != plan
            or worker_request.get("plan_sha256") != plan_sha256
            or worker_request.get("runtime_contract") != worker_contract
            or worker_request.get("runtime_contract_sha256") != runtime_sha
            or worker_request.get("mount_map") != worker_mount_map
            or worker_request.get("mount_map_sha256") != map_sha
            or worker_request.get("input_members") != input_members
            or worker_request.get("artifact_members") != artifact_members
            or worker_request.get("request_transport") != "stdin_sha256"
        ):
            raise ProfileCompositeError(
                "Linux profile request does not bind its exact artifacts and consumers"
            )
        inspect_ref = worker_request.get("container_inspect_ref")
        input_worker_root = next(
            row["worker_root"] for row in worker_mount_map["mounts"] if row["role"] == "inputs"
        )
        expected_inspect_worker_path = PurePosixPath(
            input_worker_root, inspect_ref.get("path", "") if type(inspect_ref) is dict else ""
        ).as_posix()
        inspect_path, inspect_raw = _safe_evidence(
            root,
            {"path": expected_inspect_worker_path, "sha256": inspect_ref.get("sha256")},
            "field-limited container inspection",
            mount_map=worker_mount_map,
            role="inputs",
        )
        try:
            inspect_receipt = load_json_bytes(
                inspect_raw, label="field-limited container inspection"
            )
        except SplitProtocolError as error:
            raise ProfileCompositeError("Linux container inspection is not strict JSON") from error
        worker_identity = worker_mounts.validate_worker_container_inspect_receipt(
            inspect_receipt,
            worker_contract,
            worker_mount_map,
            expected_container_id=worker_transport["container_id"],
        )
        if (
            worker_identity.get("image_id") != worker_transport.get("image_id")
            or worker_request.get("container_identity") != worker_identity
            or inspect_ref.get("sha256") != worker_transport.get("container_inspect_sha256")
            or worker_transport.get("container_inspect_ref")
            != {"path": expected_inspect_worker_path, "sha256": inspect_ref.get("sha256")}
            or inspect_path.stat().st_size <= 0
        ):
            raise ProfileCompositeError(
                "Linux runtime identity is not backed by the retained inspect output"
            )
        source_inputs = plan["source_inputs"]["worker_test_input_files"]
        input_mount = next(row for row in worker_mount_map["mounts"] if row["role"] == "inputs")
        if (
            worker_transport.get("source_checkout_mounted") is not False
            or worker_transport.get("source_input_members") != source_inputs
            or worker_transport.get("source_input_root")
            != PurePosixPath(input_mount["worker_root"], "test-source").as_posix()
            or worker_transport.get("source_input_root_host")
            != (Path(input_mount["host_root"]) / "test-source").as_posix()
        ):
            raise ProfileCompositeError(
                "Linux selected test closure is not isolated from the checkout"
            )
        expected_artifacts = plan["artifacts"]
        transported = worker_transport.get("artifacts")
        if type(transported) is not list or len(transported) != len(expected_artifacts):
            raise ProfileCompositeError("Linux transport omits a profile wheel")
        for expected_artifact, actual in zip(expected_artifacts, transported, strict=True):
            if (
                type(actual) is not dict
                or actual.get("profile") != expected_artifact["profile"]
                or actual.get("chain_key") != expected_artifact["chain_key"]
                or actual.get("sha256") != expected_artifact["sha256"]
                or actual.get("bytes") != expected_artifact["bytes"]
            ):
                raise ProfileCompositeError(
                    "Linux transported wheel set differs from the complete chain"
                )
            _, transported_raw = _safe_evidence(
                root,
                {"path": actual.get("path"), "sha256": actual.get("sha256")},
                "transported profile wheel",
                mount_map=worker_mount_map,
                role="artifacts",
            )
            if len(transported_raw) != expected_artifact["bytes"]:
                raise ProfileCompositeError(
                    "transported wheel bytes differ from the producer receipt"
                )
        install_ref = receipt.get("entrypoint_install_receipt")
        install_receipt, _ = _load_evidence_json(
            root, install_ref, "selected wheel install receipt"
        )
        install_plan = worker_request.get("entrypoint_install_plan")
        if type(install_plan) is not dict or hashlib.sha256(
            canonical_json_bytes(install_plan)
        ).hexdigest() != worker_request.get("entrypoint_install_plan_sha256"):
            raise ProfileCompositeError("Linux generated-entrypoint plan is absent or stale")
        runtime_probe = install_receipt.get("runtime_probe")
        worker_mounts.validate_entrypoint_install_receipt(
            install_receipt,
            install_plan,
            runtime_probe,
            worker_mount_map,
            container_identity=worker_identity,
            expected_distribution_name=install_plan["distribution"]["name"],
            expected_distribution_version=install_plan["distribution"]["version"],
        )
        if (
            receipt.get("execution_identity") is None
            or worker_transport.get("input_tree", {}).get("member_count") != len(input_members)
            or worker_transport.get("worker_visible_artifact_tree", {}).get("member_count")
            != len(artifact_members)
        ):
            raise ProfileCompositeError(
                "Linux transport is missing full input/artifact readback counts"
            )
    identity, _ = _load_evidence_json(root, receipt.get("execution_identity"), "execution identity")
    if (
        identity.get("platform_system") != expected_platform
        or identity.get("sys_platform") != ("darwin" if expected_platform == "Darwin" else "linux")
        or identity.get("runner_sha256") != receipt.get("runner_sha256")
        or identity.get("source") != plan["source"]
    ):
        raise ProfileCompositeError("measured child execution identity differs from placement")
    if executor == "host":
        source_root = _resolved_directory(
            identity.get("source_checkout_root"), "actual source checkout root"
        )
        if (
            identity.get("source_input_root") is not None
            or identity.get("source_input_members") is not None
        ):
            raise ProfileCompositeError(
                "host execution may not claim a transferred worker test closure"
            )
    else:
        source_root = None
        if (
            identity.get("source_checkout_root") is not None
            or identity.get("source_input_root") != worker_transport.get("source_input_root")
            or identity.get("source_input_members")
            != plan["source_inputs"]["worker_test_input_files"]
            or identity.get("container_id") != worker_identity["container_id"]
            or identity.get("image_id") != worker_identity["image_id"]
            or identity.get("mount_map_sha256") != worker_transport["mount_map_sha256"]
        ):
            raise ProfileCompositeError(
                "worker identity claims checkout access or loses its source closure"
            )
    python = identity.get("python")
    if (
        type(python) is not str
        or not Path(python).is_absolute()
        or (executor == "host" and not Path(python).is_file())
    ):
        raise ProfileCompositeError("execution identity omits its actual Python interpreter")
    _, collected_raw = _safe_evidence(root, receipt.get("collected_node_ids"), "collected node IDs")
    try:
        observed_ids = json.loads(collected_raw)
    except json.JSONDecodeError as error:
        raise ProfileCompositeError("collected node IDs evidence is not JSON") from error
    if type(observed_ids) is not list or observed_ids != run_row["node_ids"]:
        raise ProfileCompositeError(
            "runtime-collected IDs differ from the assigned exact partition"
        )
    junit_path, junit_raw = _safe_evidence(root, receipt.get("junit"), "primary JUnit")
    junit_ids, counts = _junit_observations(junit_raw, special_document_path)
    if junit_ids != run_row["node_ids"] or counts != {
        "tests": len(run_row["node_ids"]),
        "skipped": 0,
        "failures": 0,
        "errors": 0,
    }:
        raise ProfileCompositeError("primary JUnit does not prove the exact zero-skip partition")
    origin, origin_path = _load_evidence_json(
        root, receipt.get("origin_proof"), "installed origin proof"
    )
    target_proof, _ = _load_evidence_json(
        root, receipt.get("installed_target_proof"), "installed target proof"
    )
    if executor == "host":
        origin_purelib, origin_dependency, origin_sys_path = _origin_paths(
            origin, "installed origin"
        )
        origin_names = _validate_origin_rows(
            origin.get("origins"), origin_purelib, "installed origin"
        )
        if any(path == source_root or path.is_relative_to(source_root) for path in origin_sys_path):
            raise ProfileCompositeError("actual source checkout appears in the child sys.path")
        purelib_report_path = origin_purelib
        dependency_report_path = origin_dependency
    else:
        origin_purelib, origin_dependency, origin_sys_path, origin_purelib_worker, origin_names = (
            _validate_worker_origin(
                origin,
                mount_map=worker_mount_map,
                runtime_contract=worker_contract,
                source_input_root=worker_transport["source_input_root"],
                label="installed origin",
            )
        )
        purelib_report_path = origin_purelib_worker
        dependency_report_path = origin_dependency
    if (
        origin.get("verified") is not True
        or origin.get("errors") != []
        or not {"polisyos", "tools"} <= origin_names
        or target_proof.get("purelib") != str(purelib_report_path)
        or target_proof.get("dependency_site") != str(dependency_report_path)
        or type(target_proof.get("node_ids")) is not int
        or target_proof["node_ids"] != len(run_row["node_ids"])
    ):
        raise ProfileCompositeError("actual installed-origin or target proof did not reconcile")
    resources, _ = _load_evidence_json(
        root, receipt.get("resource_proof"), "installed resource proof"
    )
    expected_resources = plan.get("owner_resources")
    if (
        type(expected_resources) is not list
        or resources.get("schema") != "polisyos.packaged-resource-contract.v1"
        or sorted(resources.get("runtime_owner_targets", []))
        != sorted(row["wheel"] for row in expected_resources)
        or set(resources.get("importlib_resources", {}))
        != {row["wheel"] for row in expected_resources}
    ):
        raise ProfileCompositeError("actual installed resource proof omits source-owned resources")
    for row in expected_resources:
        if resources["importlib_resources"].get(row["wheel"]) != {
            "bytes": row["bytes"],
            "sha256": row["sha256"],
        }:
            raise ProfileCompositeError(
                f"installed resource bytes differ from source owner: {row['wheel']}"
            )
    poison, _ = _load_evidence_json(root, receipt.get("poison_proof"), "poison-neighbor proof")
    if executor == "host":
        poison_names = _validate_origin_rows(
            poison.get("origins"), origin_purelib, "poison-neighbor proof"
        )
    else:
        poison_origin = {
            "purelib": poison.get("purelib"),
            "dependency_site": poison.get("dependency_site"),
            "sys_path": poison.get("sys_path"),
            "origins": poison.get("origins"),
        }
        poison_names = _validate_worker_origin(
            poison_origin,
            mount_map=worker_mount_map,
            runtime_contract=worker_contract,
            source_input_root=worker_transport["source_input_root"],
            label="poison-neighbor proof",
        )[4]
    origin_details = origin.get("origin_details", origin.get("origins"))
    poison_details = poison.get("origins")
    shared_origin_names = origin_names & poison_names
    expected_catalog_readers = {
        name: PurePosixPath(purelib_report_path, target).as_posix()
        if executor == "linux-worker"
        else str((origin_purelib / target).resolve(strict=True))
        for name, target in plan["catalog_default_targets"].items()
    }
    expected_digest_registry = (
        PurePosixPath(purelib_report_path, plan["digest_registry_target"]).as_posix()
        if executor == "linux-worker"
        else str((origin_purelib / plan["digest_registry_target"]).resolve(strict=True))
    )
    worker_directories = {
        PurePosixPath(purelib_report_path, target).parent.as_posix()
        if executor == "linux-worker"
        else str((origin_purelib / target).parent.resolve(strict=True))
        for target in plan["worker_profile_targets"]
    }
    if len(worker_directories) != 1:
        raise ProfileCompositeError(
            "source-owned worker resources do not share one installed directory"
        )
    if (
        poison.get("verified") is not True
        or not {"polisyos", "tools"} <= shared_origin_names
        or (executor == "host" and poison_details != origin_details)
        or (
            executor == "linux-worker"
            and (
                type(poison_details) is not dict
                or type(origin_details) is not dict
                or any(
                    poison_details.get(name) != origin_details.get(name)
                    for name in shared_origin_names
                )
            )
        )
        or poison.get("catalog_readers") != expected_catalog_readers
        or poison.get("dependency_registry") != expected_digest_registry
        or poison.get("dowhy_worker_directory") != next(iter(worker_directories))
    ):
        raise ProfileCompositeError("poison-neighbor/import-origin control did not pass")
    for label in ("target_before_snapshot", "target_after_snapshot"):
        value, _ = _load_evidence_json(root, receipt.get(label), label.replace("_", " "))
        receipt[label + "_value"] = value
    if receipt["target_before_snapshot_value"] != receipt["target_after_snapshot_value"]:
        raise ProfileCompositeError("profile package target changed during consumer execution")
    if executor == "linux-worker":
        worker_mounts = _worker_mounts_module()
        actual_snapshot = worker_mounts.snapshot_profile_prefix(
            worker_mount_map, install_receipt["runtime_probe"]
        )
        if receipt["target_before_snapshot_value"] != actual_snapshot:
            raise ProfileCompositeError(
                "worker-reported prefix snapshot differs from mapped host bytes"
            )
    receipt.pop("target_before_snapshot_value")
    receipt.pop("target_after_snapshot_value")
    for label in ("stdout", "stderr"):
        _safe_evidence(root, receipt.get(label), f"complete consumer {label}")
    if executor == "host" and receipt.get("transport_proof") is not None:
        raise ProfileCompositeError("host execution may not claim a remote transfer receipt")
    return {
        "profile": profile,
        "executor": executor,
        "platform": expected_platform,
        "artifact_sha256": run_row["artifact_sha256"],
        "node_ids": run_row["node_ids"],
        "node_ids_sha256": run_row["node_ids_sha256"],
        "junit_path": str(junit_path),
        "junit_sha256": receipt["junit"]["sha256"],
        "origin_proof_path": origin_path,
        "origin_proof_sha256": receipt["origin_proof"]["sha256"],
        "result_path": str(result_file),
        "result_sha256": hashlib.sha256(result_file.read_bytes()).hexdigest(),
        "counts": counts,
    }


def validate_primary_barrier(
    plan: dict[str, Any],
    execution_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Release supplemental admission only after all six exact primary partitions pass."""
    plan_sha256 = _plan_digest(plan)
    if plan.get("schema") != COMPOSITE_SCHEMA:
        raise ProfileCompositeError("primary barrier received an unsupported plan")
    expected_keys = {
        (profile, executor) for profile in plan["profiles"] for executor in ("host", "linux-worker")
    }
    observed_keys: list[tuple[str, str]] = []
    for row in execution_rows:
        if type(row) is not dict:
            raise ProfileCompositeError("primary execution row is malformed")
        observed_keys.append((row.get("profile"), row.get("executor")))
    if len(observed_keys) != len(set(observed_keys)) or set(observed_keys) != expected_keys:
        raise ProfileCompositeError(
            "primary barrier is missing or duplicates a profile/platform partition"
        )
    by_key = {(row["profile"], row["executor"]): row for row in execution_rows}
    for key, row in by_key.items():
        if type(row.get("result_path")) is not str:
            raise ProfileCompositeError(
                "primary barrier accepts only recomputed execution receipts"
            )
        fresh = reconcile_primary_execution(
            row["result_path"],
            plan=plan,
            profile=key[0],
            executor=key[1],
            special_document_path=plan["special_document_path"],
        )
        if fresh != row:
            raise ProfileCompositeError(
                "primary barrier execution row differs from retained outputs"
            )
    for run in plan["run_plan"]:
        row = by_key[(run["profile"], run["executor"])]
        if (
            row.get("artifact_sha256") != run["artifact_sha256"]
            or row.get("node_ids") != run["node_ids"]
            or row.get("node_ids_sha256") != run["node_ids_sha256"]
            or row.get("counts")
            != {"tests": len(run["node_ids"]), "skipped": 0, "failures": 0, "errors": 0}
        ):
            raise ProfileCompositeError(
                "primary barrier row differs from its assigned artifact/case set"
            )
    for profile in plan["profiles"]:
        host = by_key[(profile, "host")]
        worker = by_key[(profile, "linux-worker")]
        if host["artifact_sha256"] != worker["artifact_sha256"]:
            raise ProfileCompositeError(
                "host and Linux receipts do not consume the same profile wheel"
            )
        if set(host["node_ids"]) & set(worker["node_ids"]):
            raise ProfileCompositeError("host and Linux receipts double-count a profile case")
        if set(host["node_ids"]) | set(worker["node_ids"]) != set(plan["primary"]["node_ids"]):
            raise ProfileCompositeError(
                "host and Linux receipts do not cover the complete primary set"
            )
    canonical_rows = sorted(
        execution_rows, key=lambda row: (plan["profiles"].index(row["profile"]), row["executor"])
    )
    receipt_sha = sha256_bytes(canonical_json_bytes(canonical_rows))
    return {
        "schema": BARRIER_SCHEMA,
        "status": "primary_profiles_complete",
        "source": plan["source"],
        "plan_sha256": plan_sha256,
        "input_pins": plan["input_pins"],
        "profiles": plan["profiles"],
        "primary_node_ids_sha256": plan["primary"]["node_ids_sha256"],
        "primary_unique_count_per_profile": plan["primary"]["count"],
        "execution_row_count": len(canonical_rows),
        "execution_rows_sha256": receipt_sha,
        "supplemental_admission": "admitted_after_barrier",
    }


def require_supplemental_barrier(
    barrier: dict[str, Any],
    plan: dict[str, Any],
    execution_rows: list[dict[str, Any]],
) -> str:
    """Recompute every primary receipt before admitting a supplemental run."""
    recomputed = validate_primary_barrier(plan, execution_rows)
    if type(barrier) is not dict or barrier != recomputed:
        raise ProfileCompositeError(
            "supplemental phase lacks a recomputed complete primary barrier"
        )
    return barrier["execution_rows_sha256"]


def execute_composite_plan(
    plan: dict[str, Any],
    *,
    run_primary_partition: Callable[[dict[str, Any]], str | Path],
    run_supplemental_partition: Callable[[str, dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """Run every source-selected primary partition before releasing supplementals.

    The callbacks perform real consumer commands. This coordinator owns only
    the sequencing and source-recomputed admission barrier.
    """
    if plan.get("schema") != COMPOSITE_SCHEMA:
        raise ProfileCompositeError("composite executor received an unsupported plan")
    run_plan = plan.get("run_plan")
    if type(run_plan) is not list or len(run_plan) != 6:
        raise ProfileCompositeError("composite executor requires all six primary partitions")
    primary_rows: list[dict[str, Any]] = []
    primary_results: dict[tuple[str, str], dict[str, Any]] = {}
    for partition in run_plan:
        if type(partition) is not dict or partition.get("phase") != "primary":
            raise ProfileCompositeError("composite run plan contains a non-primary partition")
        result_path = run_primary_partition(dict(partition))
        reconciled = reconcile_primary_execution(
            result_path,
            plan=plan,
            profile=partition.get("profile"),
            executor=partition.get("executor"),
            special_document_path=plan["special_document_path"],
        )
        primary_rows.append(reconciled)
        key = (reconciled["profile"], reconciled["executor"])
        if key in primary_results:
            raise ProfileCompositeError("composite executor received duplicate primary outputs")
        primary_results[key] = reconciled
    barrier = validate_primary_barrier(plan, primary_rows)
    if len(primary_rows) != 6:
        raise ProfileCompositeError("all six source-selected primary partitions are required")
    barrier_sha256 = require_supplemental_barrier(barrier, plan, primary_rows)
    supplemental: dict[str, dict[str, Any]] = {}
    for profile in plan["profiles"]:
        if profile in supplemental:
            raise ProfileCompositeError("composite plan repeats a supplemental profile")
        if require_supplemental_barrier(barrier, plan, primary_rows) != barrier_sha256:
            raise ProfileCompositeError("primary barrier changed before supplemental admission")
        supplemental[profile] = run_supplemental_partition(
            profile,
            {"barrier": barrier, "execution_rows": list(primary_rows)},
        )
    return {
        "schema": "policyos.e02.q2.composite-execution-receipt.v1",
        "source": plan["source"],
        "plan_sha256": _plan_digest(plan),
        "primary": primary_results,
        "barrier": barrier,
        "supplemental": supplemental,
    }


def execute_composite_plan_with_worker(
    plan: dict[str, Any],
    *,
    run_host_partition: Callable[[dict[str, Any]], str | Path],
    run_linux_worker_partition: Callable[[dict[str, Any]], str | Path],
    run_supplemental_partition: Callable[[str, dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """Route every selected primary to its real platform consumer callback.

    The shared executor still owns the six-row primary barrier and the
    supplemental admission boundary. This adapter prevents a caller from
    silently treating the Linux-only row as an unimplemented or skipped
    callback.
    """

    def run_primary(partition: dict[str, Any]) -> str | Path:
        executor = partition.get("executor")
        if executor == "host":
            return run_host_partition(partition)
        if executor == "linux-worker":
            return run_linux_worker_partition(partition)
        raise ProfileCompositeError("primary partition has no supported consumer route")

    return execute_composite_plan(
        plan,
        run_primary_partition=run_primary,
        run_supplemental_partition=run_supplemental_partition,
    )


def actual_execution_identity(
    source: dict[str, str], runner_sha256: str, source_checkout_root: str | Path
) -> dict[str, Any]:
    """Capture the actual host identity for a source-bound child-run receipt."""
    return {
        "schema": "policyos.e02.q2.execution-identity.v1",
        "source": dict(source),
        "platform_system": platform.system(),
        "sys_platform": sys.platform,
        "machine": platform.machine(),
        "python": os.path.realpath(sys.executable),
        "python_version": list(sys.version_info[:3]),
        "runner_sha256": _sha(runner_sha256, "execution runner pin"),
        "source_checkout_root": str(Path(source_checkout_root).resolve(strict=True)),
    }
