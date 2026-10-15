"""Behavioral contract for the split CausalEngine runtime namespace."""

from __future__ import annotations

import ast
import hashlib
import importlib
import importlib.util
import inspect
import os
import subprocess
import sys
from pathlib import Path

from polisyos.foundry.methods.catalog.causal.causal_engine import (
    artifacts,
    discovery,
    estimation,
    identification,
    sensitivity,
)

EXPECTED_ORDERED_BINDINGS_SHA256 = (
    "e7ed9d8a1621debc039e8bf83e68b9267d70b214b2bd24147eabd37524b32fa2"
)
EXPECTED_SORTED_BINDINGS_SHA256 = "4919b9f2996da073e05112aee64489a6b7aa0e2866e08a18dcd24483db662bb2"
EXPECTED_CURATED_IR_ROUTES = (
    ("ArtifactRefModel", "polisyos.ir", "polisyos.ir.registry.refs"),
    ("ArtifactStore", "polisyos.ir", "polisyos.ir.artifacts"),
    ("BlockingType", "polisyos.ir", "polisyos.ir.analytics.negative_certificate"),
    ("BoundsBundle", "polisyos.ir", "polisyos.ir.analytics.partial_identification"),
    ("CanonSpec", "polisyos.ir", "polisyos.ir.model_layer.canon"),
    ("CausalGraphModel", "polisyos.ir", "polisyos.ir.analytics.causal_graph"),
    ("CausalQuery", "polisyos.ir", "polisyos.ir.analytics.causal_queries"),
    ("DistributionLawQuery", "polisyos.ir", "polisyos.ir.analytics.estimand"),
    ("EdgeMark", "polisyos.ir.analytics", "polisyos.ir.analytics.causal_graph"),
    ("EstimandAST", "polisyos.ir", "polisyos.ir.analytics.estimand"),
    ("EstimationStatus", "polisyos.ir", "polisyos.ir.analytics.causal"),
    ("GraphType", "polisyos.ir.analytics", "polisyos.ir.analytics.causal_graph"),
    ("InputRef", "polisyos.ir", "polisyos.ir.artifacts"),
    ("InterventionCertificate", "polisyos.ir.analytics", "polisyos.ir.analytics.interventions"),
    ("InterventionQuery", "polisyos.ir", "polisyos.ir.analytics.interventions"),
    ("JointDecisionCertificate", "polisyos.ir.analytics", "polisyos.ir.analytics.recoverability"),
    ("NegativeCertificate", "polisyos.ir", "polisyos.ir.analytics.negative_certificate"),
    ("ProofBundle", "polisyos.ir", "polisyos.ir.analytics.causal"),
    ("QueryType", "polisyos.ir", "polisyos.ir.analytics.causal_queries"),
    ("RecoverabilityCertificate", "polisyos.ir.analytics", "polisyos.ir.analytics.recoverability"),
    ("SurveyQualityCertificateRef", "polisyos.ir", "polisyos.ir.registry.refs"),
    ("build_phase1_gate_summary", "polisyos.ir.governance", "polisyos.ir.governance.phase1"),
    ("load_phase1_flagship_dataset_ids", "polisyos.ir.governance", "polisyos.ir.governance.phase1"),
    ("persist_estimand_ast", "polisyos.ir", "polisyos.ir.analytics.estimand"),
    ("persist_negative_certificate", "polisyos.ir", "polisyos.ir.analytics.negative_certificate"),
    ("persist_proof_bundle", "polisyos.ir", "polisyos.ir.analytics.causal"),
    ("proof_bundle_from_identification_result", "polisyos.ir", "polisyos.ir.analytics.causal"),
    ("proof_bundle_from_negative_certificate", "polisyos.ir", "polisyos.ir.analytics.causal"),
    ("put_json_artifact", "polisyos.ir", "polisyos.ir.artifacts"),
)
MIXIN_MODULES = (discovery, estimation, identification, sensitivity)


def _module_runtime_bindings(module: ast.Module) -> set[str]:
    """Derive the module-level runtime binding set from source."""
    names: set[str] = set()
    for node in module.body:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            continue
        if isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                names.update(child.id for child in ast.walk(target) if isinstance(child, ast.Name))
    names.discard("__all__")
    return names


def _assert_import_bindings_are_exact_owner_objects(module: ast.Module) -> None:
    """Check every runtime import aliases the exact object from its imported owner."""
    package = artifacts.__package__
    for node in module.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                binding = alias.asname or alias.name.split(".")[0]
                module_name = alias.name if alias.asname else alias.name.split(".")[0]
                expected = importlib.import_module(module_name)
                assert getattr(artifacts, binding) is expected, binding
        elif isinstance(node, ast.ImportFrom) and node.module != "__future__":
            module_name = (
                importlib.util.resolve_name("." * node.level + (node.module or ""), package)
                if node.level
                else node.module
            )
            owner = importlib.import_module(module_name)
            for alias in node.names:
                if alias.name == "*":
                    continue
                binding = alias.asname or alias.name
                assert getattr(artifacts, binding) is getattr(owner, alias.name), binding


def test_artifact_exports_equal_its_source_derived_runtime_bindings() -> None:
    names = artifacts.__all__
    tree = ast.parse(Path(artifacts.__file__).read_text(encoding="utf-8"))

    assert len(names) == len(set(names))
    assert set(names) == _module_runtime_bindings(tree)
    assert hashlib.sha256("\n".join(names).encode()).hexdigest() == (
        EXPECTED_ORDERED_BINDINGS_SHA256
    )
    assert hashlib.sha256("\n".join(sorted(names)).encode()).hexdigest() == (
        EXPECTED_SORTED_BINDINGS_SHA256
    )
    assert all(hasattr(artifacts, name) for name in names)
    assert len(EXPECTED_CURATED_IR_ROUTES) == 29


def test_runtime_imports_keep_the_exact_objects_from_their_owner_modules() -> None:
    tree = ast.parse(Path(artifacts.__file__).read_text(encoding="utf-8"))
    _assert_import_bindings_are_exact_owner_objects(tree)

    for name, route_module, owner_module in EXPECTED_CURATED_IR_ROUTES:
        route_object = getattr(importlib.import_module(route_module), name)
        owner_object = getattr(importlib.import_module(owner_module), name)
        assert route_object is owner_object
        assert getattr(artifacts, name) is route_object


def test_all_four_mixins_receive_the_exact_runtime_namespace_objects() -> None:
    for mixin in MIXIN_MODULES:
        for name in artifacts.__all__:
            assert name in mixin.__dict__
            assert mixin.__dict__[name] is getattr(artifacts, name)


def test_evaluated_intervention_default_uses_the_runtime_export_object() -> None:
    default = (
        inspect.signature(
            identification.CausalEngineIdentificationMixin._intervention_negative_certificate
        )
        .parameters["intervention_status"]
        .default
    )

    assert default is artifacts.InterventionIdentificationStatus.NOT_IDENTIFIABLE


def test_removing_runtime_export_fails_even_while_type_checking_marker_remains() -> None:
    source_root = Path(os.environ.get("POLISYOS_SRC", Path(__file__).resolve().parents[6] / "src"))
    raw_root = Path(__file__).resolve().parents[1]
    script = """import ast
import importlib
import sys
from pathlib import Path

from polisyos.foundry.methods.catalog.causal.causal_engine import artifacts, identification

name = "InterventionIdentificationStatus"
source = ast.parse(Path(identification.__file__).read_text(encoding="utf-8"))
markers = [
    alias.asname or alias.name
    for node in source.body
    if isinstance(node, ast.If) and ast.unparse(node.test) == "TYPE_CHECKING"
    for statement in node.body
    if isinstance(statement, ast.ImportFrom) and statement.level == 1 and statement.module == "artifacts"
    for alias in statement.names
]
assert name in markers
assert name in artifacts.__all__
artifacts.__all__ = [binding for binding in artifacts.__all__ if binding != name]
delattr(artifacts, name)
sys.modules.pop(identification.__name__, None)
try:
    importlib.import_module(identification.__name__)
except NameError as exc:
    assert exc.name == name, (exc.name, name)
else:
    raise AssertionError(f"deleting runtime export {name} left mixin import green")
"""
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(raw_root), str(source_root), environment.get("PYTHONPATH", "")]
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=source_root.parent,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
