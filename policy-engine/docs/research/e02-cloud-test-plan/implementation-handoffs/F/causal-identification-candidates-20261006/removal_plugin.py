"""Source-derived, process-local removals on canonical function objects."""
from __future__ import annotations

import __future__
import ast
import hashlib
import importlib
import json
import marshal
import os
from pathlib import Path
import subprocess

ROOT = Path("/workspace/e02-F-tmle-20261006")
SHA = "2577a3fa7f11fdaf596d30b364d6ad527d4430b6"
BASE = "f460bd81b8124be58f890f59a53e2aba9e7ceb76"


def _source(ref: str, relative: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), "show", f"{ref}:{relative}"]).decode()


def _node(source: str, class_name: str | None, function_name: str) -> ast.FunctionDef:
    parent = ast.parse(source)
    if class_name:
        parent = next(node for node in parent.body if isinstance(node, ast.ClassDef)
                      and node.name == class_name)
    return next(node for node in parent.body if isinstance(node, ast.FunctionDef)
                and node.name == function_name)


def pytest_sessionstart(session) -> None:
    mode = os.environ["E02_REMOVAL_MODE"]
    if mode == "emission":
        module_name, class_name, function_name = (
            "polisyos.ir.analytics.causal", "CausalEffectReport", "to_uncertainty_envelope")
    elif mode == "role_intake":
        module_name, class_name, function_name = (
            "polisyos.scientist.governance.passes.confidence_pass", "ConfidencePass", "validate")
    elif mode == "reference_shape":
        module_name, class_name, function_name = (
            "polisyos.scientist.governance.passes.confidence_pass", None, "_resolve_causal_envelope_ref")
    else:
        raise ValueError(mode)
    module = importlib.import_module(module_name)
    relative = "policy-engine/src/" + module_name.replace(".", "/") + ".py"
    source = _source(SHA, relative)
    assert Path(module.__file__).read_text() == source
    owner = getattr(module, class_name) if class_name else module
    function = getattr(owner, function_name)
    original_id = id(function)
    original_hash = hashlib.sha256(marshal.dumps(function.__code__)).hexdigest()
    node = _node(source, class_name, function_name)
    if mode == "emission":
        # The successful return is the final return; the failure sentinel stays
        # unchanged. Keep status, numeric CI, metadata reason and proof labels.
        expression = next(item for item in reversed(node.body) if isinstance(item, ast.Return)).value
        keyword = next(item for item in expression.keywords if item.arg == "gate_eligible")
        assert keyword.value.value is False
        keyword.value = ast.Constant(value=True)
    elif mode == "role_intake":
        candidate_block = next(item for item in node.body if isinstance(item, ast.If)
                               and ast.unparse(item.test) == "causal_ref is not None")
        candidate_block.test = ast.Constant(value=False)
    else:
        node = _node(_source(BASE, relative), class_name, function_name)
    replacement = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(replacement)
    namespace = dict(vars(module))
    exec(compile(replacement, module.__file__, "exec", flags=__future__.annotations.compiler_flag), namespace)
    function.__code__ = namespace[function_name].__code__
    assert id(getattr(owner, function_name)) == original_id
    print(json.dumps({"removal": mode, "candidate_sha": SHA, "base_sha": BASE,
                      "provider_path": relative, "provider_source_sha256": hashlib.sha256(source.encode()).hexdigest(),
                      "canonical_function": module_name + "." + (class_name + "." if class_name else "") + function_name,
                      "function_object_preserved": True, "original_code_sha256": original_hash,
                      "removed_code_sha256": hashlib.sha256(marshal.dumps(function.__code__)).hexdigest(),
                      "source_files_written": False}, sort_keys=True))
