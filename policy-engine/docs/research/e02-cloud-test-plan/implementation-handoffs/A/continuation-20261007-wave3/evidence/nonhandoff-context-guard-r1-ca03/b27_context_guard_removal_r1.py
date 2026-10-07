"""Bounded R1 mutation probe for the ordinary N6 context-reissue guard.

Load with ``-p b27_context_guard_removal_r1`` and put this directory on
``PYTHONPATH``. The plugin removes exactly one 12-line block from the in-memory
``GenerationCycleController._revise_node`` method, leaving checkout bytes and
all other guards unchanged. It captures whether the pinned positive witness
reaches the real stale-context validator on default N4 and fails for that
specific reason. Set ``POLISYOS_B27_R1_RECEIPT_PATH`` to place the JSON receipt
elsewhere under ignored ``policy-engine/_build``; relative paths resolve from
the product root. The default is ``r1-receipt.json`` beside this plugin.
"""

from __future__ import annotations

import ast
import hashlib
import importlib
import inspect
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

EXPECTED_HEAD = "ca038ac238af074b938ea532f0182664fe611b41"
EXPECTED_TREE = "51d874b3ce4f6c057b7495c312b591d4ad227d23"
EXPECTED_SOURCE_BLOB = "c970465dd426bc29495ea6dbbff9d1f1cbcd8cb8"
EXPECTED_SOURCE_SHA256 = "899159c295220e43b464ce34ef2de4549b2c78804e8ffbb4a77a58eb3acef691"
EXPECTED_TEST_BLOB = "a23d4b137da02b8b4fc909904e21abbb31140b98"
EXPECTED_TEST_SHA256 = "dcaee38888be649650c2d335ebddce10d0887bb55ff58797dcd859e545ff3446"
SOURCE_RELATIVE = Path("policy-engine/src/polisyos/runtime/quality/generation_cycle.py")
TEST_RELATIVE = Path(
    "policy-engine/tests/integration/core_runtime/test_e02_nonhandoff_context_revision.py"
)
TARGET_NODEID = (
    "tests/integration/core_runtime/test_e02_nonhandoff_context_revision.py::"
    "test_nonhandoff_revision_blocks_before_stale_context_n4_and_roundtrips_history"
)
REMOVED_GUARD = """\
    if (
        next_action.next_action == "advance"
        and self._cycle_substrate_context is not None
        and self._cycle_substrate_context.design_problem_ref
        != _problem_ref(revision.revised_problem)
    ):
        next_action = next_action.model_copy(
            update={
                "next_action": "blocked",
                "reason": "cycle_substrate_context_reissue_required",
            }
        )
"""
RETAINED_GUARD_MARKERS = (
    "if state.get(\"n5_preflight_enforced\")",
    "not_run_hard_feasibility_blocked",
    "if self._candidate_simulation_handoff is not None",
    "self.decide_next_action(",
)
RECEIPT_PATH_ENV = "POLISYOS_B27_R1_RECEIPT_PATH"
_STATE: dict[str, Any] = {}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / SOURCE_RELATIVE).is_file():
            return parent
    raise pytest.UsageError("R1 plugin cannot locate the pinned PolicyOS checkout")


def _receipt_path(root: Path) -> Path:
    """Resolve the runner's receipt path, confined to ignored build scratch."""

    configured = os.environ.get(RECEIPT_PATH_ENV, "").strip()
    if configured:
        path = Path(configured)
        if not path.is_absolute():
            path = root / "policy-engine" / path
    else:
        path = Path(__file__).with_name("r1-receipt.json")
    resolved = path.resolve()
    ignored_build_root = (root / "policy-engine" / "_build").resolve()
    if not resolved.is_relative_to(ignored_build_root):
        raise pytest.UsageError(
            f"{RECEIPT_PATH_ENV} must resolve under ignored policy-engine/_build"
        )
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def _test_ast_hash(source: bytes) -> tuple[str, str]:
    parsed = ast.parse(source.decode("utf-8"))
    functions = [
        node
        for node in parsed.body
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == TARGET_NODEID.rsplit("::", 1)[1]
    ]
    if len(functions) != 1:
        raise pytest.UsageError("R1 target test AST is absent or ambiguous")
    module_ast = ast.dump(parsed, include_attributes=False).encode("utf-8")
    function_ast = ast.dump(functions[0], include_attributes=False).encode("utf-8")
    return _sha256(module_ast), _sha256(function_ast)


def _pin_checkout(root: Path) -> dict[str, str]:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD", "HEAD^{tree}"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    head, tree = result.stdout.splitlines()
    if head != EXPECTED_HEAD or tree != EXPECTED_TREE:
        raise pytest.UsageError(f"R1 checkout pin mismatch: {head} {tree}")
    source_path = root / SOURCE_RELATIVE
    test_path = root / TEST_RELATIVE
    source_bytes = source_path.read_bytes()
    test_bytes = test_path.read_bytes()
    if _sha256(source_bytes) != EXPECTED_SOURCE_SHA256:
        raise pytest.UsageError("R1 runtime source bytes differ from the pinned source")
    if _sha256(test_bytes) != EXPECTED_TEST_SHA256:
        raise pytest.UsageError("R1 witness bytes differ from the pinned test")
    module_ast_sha256, function_ast_sha256 = _test_ast_hash(test_bytes)
    return {
        "head": head,
        "tree": tree,
        "source_path": str(source_path.resolve()),
        "source_blob": EXPECTED_SOURCE_BLOB,
        "source_sha256": _sha256(source_bytes),
        "test_path": str(test_path.resolve()),
        "test_blob": EXPECTED_TEST_BLOB,
        "test_sha256": _sha256(test_bytes),
        "test_module_ast_sha256": module_ast_sha256,
        "test_function_ast_sha256": function_ast_sha256,
    }


def _remove_only_context_guard(root: Path) -> dict[str, Any]:
    module = importlib.import_module("polisyos.runtime.quality.generation_cycle")
    module_path = Path(module.__file__).resolve()
    expected_path = (root / SOURCE_RELATIVE).resolve()
    if module_path != expected_path or sys.modules.get(module.__name__) is not module:
        raise pytest.UsageError("R1 runtime import identity is not the pinned checkout")
    controller = module.GenerationCycleController
    if controller.__module__ != module.__name__:
        raise pytest.UsageError("R1 controller class is not owned by the pinned module")

    source = textwrap.dedent(inspect.getsource(controller._revise_node))
    if source.count(REMOVED_GUARD) != 1:
        raise pytest.UsageError("R1 mutation target is not exactly one 12-line guard")
    mutated = source.replace(REMOVED_GUARD, "", 1)
    if "cycle_substrate_context_reissue_required" in mutated:
        raise pytest.UsageError("R1 removed guard reason remains in the mutated method")
    if not all(marker in mutated for marker in RETAINED_GUARD_MARKERS):
        raise pytest.UsageError("R1 mutation would remove or alter a neighboring guard")
    compile(mutated, str(module_path), "exec")
    namespace: dict[str, Any] = {}
    exec(compile(mutated, str(module_path), "exec"), module.__dict__, namespace)
    controller._revise_node = namespace["_revise_node"]
    return {
        "module_name": module.__name__,
        "module_file": str(module_path),
        "module_identity_is_sys_modules_entry": sys.modules.get(module.__name__) is module,
        "controller_class_module": controller.__module__,
        "controller_class_identity_is_module_export": (
            getattr(module, "GenerationCycleController") is controller
        ),
        "removed_guard_occurrences": 1,
        "removed_guard_line_count": 12,
        "removed_guard_method_sha256": _sha256(source.encode("utf-8")),
        "mutated_method_sha256": _sha256(mutated.encode("utf-8")),
        "retained_guard_markers": list(RETAINED_GUARD_MARKERS),
        "checkout_source_sha256_after_in_memory_mutation": _sha256(module_path.read_bytes()),
    }


def pytest_configure(config: pytest.Config) -> None:
    """Pin the run and patch only the exact in-memory N6 guard."""

    del config
    root = _repository_root()
    pinned = _pin_checkout(root)
    receipt_path = _receipt_path(root)
    _STATE.update(
        {
            "pinned": pinned,
            "mutation": _remove_only_context_guard(root),
            "receipt_path": str(receipt_path),
        }
    )


def pytest_collection_finish(session: pytest.Session) -> None:
    """Require the one bounded B27 context witness and no neighboring tests."""

    nodeids = [item.nodeid for item in session.items]
    if len(nodeids) != 1 or not nodeids[0].endswith(TARGET_NODEID):
        raise pytest.UsageError(f"R1 must collect only the pinned witness, got {nodeids!r}")
    _STATE["collected_nodeid"] = nodeids[0]


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: Any) -> Any:
    """Write a small receipt proving whether the removed guard exposed N4."""

    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not item.nodeid.endswith(TARGET_NODEID):
        return

    test_locals: dict[str, Any] = {}
    error = call.excinfo.value if call.excinfo is not None else None
    traceback = error.__traceback__ if error is not None else None
    while traceback is not None:
        if traceback.tb_frame.f_code.co_name == TARGET_NODEID.rsplit("::", 1)[1]:
            test_locals = traceback.tb_frame.f_locals
            break
        traceback = traceback.tb_next

    dispatched = list(test_locals.get("dispatched_cycles", ()))
    default_inputs = list(test_locals.get("default_n4_inputs", ()))
    n5_observations = list(test_locals.get("n5_observations", ()))
    n4_error = (
        {
            "error_type": f"{type(error).__module__}.{type(error).__qualname__}",
            "error_code": getattr(error, "code", None),
            "error_message": str(error),
        }
        if error is not None
        else None
    )
    n4_type = None
    if "default_n4" in test_locals:
        default_n4_type = type(test_locals["default_n4"])
        n4_type = f"{default_n4_type.__module__}.{default_n4_type.__qualname__}"
    if default_inputs:
        problem, context = default_inputs[-1]
        from polisyos.pdc import gy_content_hash

        n4_input = {
            "problem_ref": gy_content_hash(problem.model_dump(mode="json")),
            "context_problem_ref": getattr(context, "design_problem_ref", None),
        }
    else:
        n4_input = None

    expected_mismatch = bool(
        n4_error is not None
        and n4_error.get("error_type", "").endswith("DesignGenerationError")
        and n4_error.get("error_code") == "cycle_substrate_design_problem_mismatch"
        and n4_input is not None
        and n4_input["context_problem_ref"] != n4_input["problem_ref"]
    )
    qualified = bool(
        n4_type
        and report.failed
        and expected_mismatch
        and dispatched == [0, 1]
        and len(default_inputs) == 1
        and len(n5_observations) == 1
        and n4_type.endswith("N4GenerationPort")
    )
    receipt = {
        "probe": "B27 R1 exact N6 context-reissue guard removal",
        "scope": "one test; one in-memory method-block mutation",
        "receipt_path_env": RECEIPT_PATH_ENV,
        "receipt_path": _STATE["receipt_path"],
        **_STATE["pinned"],
        "mutation": _STATE["mutation"],
        "test": {
            "nodeid": item.nodeid,
            "outcome_after_guard_removal": report.outcome,
            "exception_type": (
                f"{type(error).__module__}.{type(error).__qualname__}" if error else None
            ),
            "exception_code": getattr(error, "code", None),
            "exception_message": str(error) if error else None,
            "n4_generation_port_type": n4_type,
            "generator_dispatch_cycle_indices": dispatched,
            "default_n4_invocation_count_at_real_context_boundary": len(default_inputs),
            "default_n4_context_input": n4_input,
            "default_n4_error": n4_error,
            "n5_call_count": len(n5_observations),
            "expected_stale_context_mismatch_observed": expected_mismatch,
        },
        "r1_positive_control_qualified": qualified,
    }
    Path(_STATE["receipt_path"]).write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    )
