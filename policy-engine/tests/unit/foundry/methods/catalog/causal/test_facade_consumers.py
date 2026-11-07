"""Behavioral ABI witnesses for the existing causal package facades (LA-020).

These controls concern supported imports, identification and serialization;
they do not attest optional estimation backends or effects on admitted data.
"""

from __future__ import annotations

import ast
import hashlib
import importlib
import io
import json
import pickle
import pydoc
import subprocess
import tokenize
from pathlib import Path
from types import ModuleType

import pytest

from benchmarks.harness import BenchmarkCase, BenchmarkHarness
from benchmarks.interference import policy_did_interference
from polisyos.foundry.methods.catalog.causal import causal_engine, interference
from polisyos.foundry.methods.catalog.causal.causal_engine import identification
from polisyos.foundry.methods.catalog.causal.id_engine import (
    IdentificationResult,
    IdentificationStatus,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.causal_queries import CausalQuery, QueryType
from polisyos.ir.analytics.evidence_bundle import EvidenceBundle
from polisyos.ir.analytics.negative_certificate import NegativeCertificate
from polisyos.scientist.methods.discovery.stability import _evaluate_identifiability


def _graph(*, confounded: bool = False) -> CausalGraphModel:
    edges = [CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)]
    if confounded:
        edges.append(CausalEdge(src="X", dst="Y", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW))
    return CausalGraphModel(graph_type=GraphType.ADMG, nodes=["X", "Y"], edges=edges)


@pytest.mark.parametrize("confounded", [False, True])
def test_scientist_consumer_uses_facade_identification_status(confounded: bool) -> None:
    """The actual discovery consumer distinguishes an identified DAG from a bow graph."""
    query = CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="X",
        treatment_value=1.0,
        outcome_variable="Y",
    )
    assert _evaluate_identifiability(_graph(confounded=confounded), query) is not confounded


@pytest.mark.parametrize("confounded", [False, True])
def test_facade_run_bundle_roundtrip_preserves_identification_boundary(confounded: bool) -> None:
    """Run the real public engine and consume its serialized evidence without an estimator."""
    report, bundle, certificate = causal_engine.CausalEngine().run(
        "X", "Y", _graph(confounded=confounded), run_id="api-consumer-abi"
    )
    rebuilt = EvidenceBundle.model_validate_json(bundle.model_dump_json())
    assert rebuilt == bundle
    assert rebuilt.run_id == "api-consumer-abi"
    assert report is None  # This witness has no numeric-estimation registry.
    if confounded:
        assert rebuilt.identification_status == "hedge_found"
        assert isinstance(certificate, NegativeCertificate)
    else:
        assert rebuilt.identification_status == "identified"
        assert certificate is None


def test_supported_facade_monkeypatch_executes_real_leaf_and_restores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A historical patch address must affect execution, then return to the real algorithm."""
    original = causal_engine.id_with_oracle_fallback
    calls: list[dict[str, object]] = []

    def observed_algorithm(**kwargs: object) -> IdentificationResult:
        calls.append(kwargs)
        return original(**kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(causal_engine, "id_with_oracle_fallback", observed_algorithm)
        result = causal_engine.CausalEngine().identify("X", "Y", _graph())
        assert result.status is IdentificationStatus.IDENTIFIED
        assert len(calls) == 1
        assert calls[0]["treatment"] == frozenset({"X"})
        assert calls[0]["outcome"] == frozenset({"Y"})

    restored = causal_engine.CausalEngine().identify("X", "Y", _graph())
    assert restored.status is IdentificationStatus.IDENTIFIED
    assert len(calls) == 1
    assert identification.id_with_oracle_fallback is original


def test_export_identity_proxy_misses_deleted_monkeypatch_bridge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep public names and class identity while removing the runtime ABI property."""
    original = causal_engine.id_with_oracle_fallback
    calls: list[object] = []

    def observed_algorithm(**kwargs: object) -> IdentificationResult:
        calls.append(kwargs)
        return original(**kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(causal_engine, "id_with_oracle_fallback", observed_algorithm)
        patch.setattr(identification, "_sync_public_algorithm_overrides", lambda: None)
        # The cheap public-export/identity proxy is still green.
        api = importlib.import_module(f"{causal_engine.__name__}.api")
        assert causal_engine.CausalEngine is api.CausalEngine
        assert causal_engine.__all__ == ["CausalEngine", "DataReadinessBlockedError"]
        result = causal_engine.CausalEngine().identify("X", "Y", _graph())
        assert result.status is IdentificationStatus.IDENTIFIED
        assert calls == []  # The supported patch did not reach the real invocation.


@pytest.mark.parametrize("module", [causal_engine, interference])
def test_supported_objects_keep_leaf_fqns_and_pickle_identity(module: ModuleType) -> None:
    """Public symbols resolve from their serialized owner addresses without wrapper types."""
    for name in module.__all__:
        value = getattr(module, name)
        owner = importlib.import_module(value.__module__)
        assert getattr(owner, value.__qualname__) is value
        assert pickle.loads(pickle.dumps(value)) is value  # noqa: S301 - locally produced bytes


@pytest.mark.parametrize("module", [causal_engine, interference])
def test_runtime_documentation_renders_supported_facade(module: ModuleType) -> None:
    """Generate runtime API documentation from the actual modules, rather than source markers."""
    document = pydoc.plain(pydoc.render_doc(module))
    for name in module.__all__:
        assert name in document


def test_interference_serialized_result_consumed_via_supported_facade() -> None:
    """Identify cross-unit interference and read the resulting typed graph through the facade."""
    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["T_1", "Y_1", "T_2", "Y_2"],
        edges=[
            CausalEdge(src=src, dst=dst, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)
            for src, dst in [("T_1", "Y_1"), ("T_2", "Y_2"), ("T_1", "Y_2")]
        ],
        metadata={"cluster_partition": [["T_1", "Y_1"], ["T_2", "Y_2"]]},
    )
    result = interference.identify_interference_effect(graph, treatment="T_1", outcome="Y_1")
    rebuilt = interference.InterferenceIdentificationResult.model_validate_json(
        result.model_dump_json()
    )
    assert rebuilt == result
    assert rebuilt.interference_detected
    assert rebuilt.sutva_violated
    assert rebuilt.schema_version == "1.1"
    assert rebuilt.status == "oracle_needed"
    assert rebuilt.identification_method == "unsupported_exposure_law"
    assert rebuilt.base_identification_status is None
    assert rebuilt.estimand_ast is None
    assert rebuilt.negative_certificate is None
    assert isinstance(rebuilt.augmented_graph, interference.InterferenceAugmentedGraph)
    assert rebuilt.augmented_graph.exposure_nodes == ()
    assert rebuilt.augmented_graph.augmented_graph == graph


_CAUSAL_PREFIX = "polisyos.foundry.methods.catalog.causal"
_FACADE_TARGETS = {f"{_CAUSAL_PREFIX}.causal_engine", f"{_CAUSAL_PREFIX}.interference"}
_FACADE_SIBLING_MODULES = {
    f"{_CAUSAL_PREFIX}.causal_engine": frozenset(
        {"api", "artifacts", "discovery", "estimation", "identification", "sensitivity"}
    ),
    f"{_CAUSAL_PREFIX}.interference": frozenset({"api", "estimation", "identification"}),
}
_INTERNAL_SIBLING_MODULES = frozenset(
    f"{facade}.{child}"
    for facade, children in _FACADE_SIBLING_MODULES.items()
    for child in children
)
# The B114 recovery packet retains eighteen indented function pre/postimages,
# not standalone executable modules. Bind their exact paths/bytes/error types;
# do not exempt docs generally or silently omit them from the full denominator.
_HISTORICAL_EXCERPT_COUNT = 18
_HISTORICAL_EXCERPT_SCOPE_SHA256 = (
    "56712caa1285668e82ee53a954bbb942e3d98e06370ddba73f91d4fa54a56e46"
)


_RELATIVE_FACADE_CALLERS = {
    (
        "__init__.py",
        f"{_CAUSAL_PREFIX}.causal_engine",
        ("CausalEngine",),
    ),
    (
        "__init__.py",
        f"{_CAUSAL_PREFIX}.interference",
        (
            "BipartiteInterferenceEstimator",
            "NetworkAIPWEstimator",
            "PartialInterferenceEstimator",
            "SpatialInterferenceEstimator",
            "build_block_stratified_network_causal_data",
        ),
    ),
}


def _assert_checkout_import_origin(module: ModuleType, source_root: Path) -> None:
    """Reject an ambient distribution satisfying imports on behalf of the tested source."""
    relative = Path(*module.__name__.split("."))
    candidates = {
        (source_root / relative).with_suffix(".py").resolve(),
        (source_root / relative / "__init__.py").resolve(),
    }
    assert Path(module.__file__).resolve() in candidates, (
        module.__name__,
        module.__file__,
        source_root,
    )


def _literal_import_rows(
    path: str,
    source: str,
) -> tuple[
    list[tuple[int, str, tuple[str, ...], str]],
    list[tuple[int, str, tuple[str, ...], str]],
]:
    """Resolve public facade and internal sibling imports in one source pass."""
    tree = ast.parse(source, filename=path)
    package = ""
    if "/src/" in path:
        address = path.split("/src/", 1)[1].removesuffix(".py").replace("/", ".")
        package = (
            address.removesuffix(".__init__")
            if address.endswith(".__init__")
            else address.rsplit(".", 1)[0]
        )
    public_rows: list[tuple[int, str, tuple[str, ...], str]] = []
    sibling_rows: list[tuple[int, str, tuple[str, ...], str]] = []

    def resolve_module(node: ast.ImportFrom) -> str | None:
        module = node.module or ""
        if not node.level:
            return module
        if not package:
            # Non-product scripts/tests have no declared polisyos package address.
            return None
        return importlib.util.resolve_name("." * node.level + module, package)

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = resolve_module(node)
            if module is None:
                continue
            if module in _FACADE_TARGETS:
                sibling_rows.extend(
                    (
                        node.lineno,
                        f"{module}.{alias.name}",
                        (alias.asname or alias.name,),
                        "relative" if node.level else "absolute",
                    )
                    for alias in node.names
                    if alias.name in _FACADE_SIBLING_MODULES[module]
                )
                names = tuple(
                    alias.name
                    for alias in node.names
                    if alias.name not in _FACADE_SIBLING_MODULES[module]
                )
                if names:
                    public_rows.append(
                        (node.lineno, module, names, "relative" if node.level else "absolute")
                    )
            elif module == _CAUSAL_PREFIX:
                names = tuple(
                    alias.name
                    for alias in node.names
                    if f"{_CAUSAL_PREFIX}.{alias.name}" in _FACADE_TARGETS
                )
                if names:
                    public_rows.append(
                        (node.lineno, module, names, "relative" if node.level else "absolute")
                    )
            elif module in _INTERNAL_SIBLING_MODULES:
                sibling_rows.append(
                    (
                        node.lineno,
                        module,
                        tuple(alias.asname or alias.name for alias in node.names),
                        "relative" if node.level else "absolute",
                    )
                )
        elif isinstance(node, ast.Import):
            public_rows.extend(
                (node.lineno, alias.name, (), "absolute")
                for alias in node.names
                if alias.name in _FACADE_TARGETS
            )
            sibling_rows.extend(
                (node.lineno, alias.name, (alias.asname or alias.name,), "absolute")
                for alias in node.names
                if alias.name in _INTERNAL_SIBLING_MODULES
            )
    return public_rows, sibling_rows


@pytest.mark.parametrize("facade", ["causal_engine", "interference"])
@pytest.mark.parametrize(
    ("relative_path", "source", "expected_names"),
    [
        ("__init__.py", "from . import artifacts\n", ("artifacts",)),
        ("reader.py", "from . import identification as selected\n", ("identification",)),
        ("internal/reader.py", "from .. import CausalEngine\n", ("CausalEngine",)),
    ],
)
def test_literal_census_includes_relative_imports_without_facade_text(
    facade: str, relative_path: str, source: str, expected_names: tuple[str, ...]
) -> None:
    """Path-derived package identity covers initializers, normal modules and deeper relatives."""
    path = f"policy-engine/src/{_CAUSAL_PREFIX.replace('.', '/')}/{facade}/{relative_path}"
    assert "causal_engine" not in source and "interference" not in source
    if expected_names[0] in _FACADE_SIBLING_MODULES[f"{_CAUSAL_PREFIX}.{facade}"]:
        expected_module = f"{_CAUSAL_PREFIX}.{facade}.{expected_names[0]}"
        public_rows, sibling_rows = _literal_import_rows(path, source)
        expected_binding = (
            "selected" if expected_names[0] == "identification" else expected_names[0]
        )
        assert public_rows == []
        assert sibling_rows == [(1, expected_module, (expected_binding,), "relative")]
        return
    expected = [(1, f"{_CAUSAL_PREFIX}.{facade}", expected_names, "relative")]
    public_rows, sibling_rows = _literal_import_rows(path, source)
    assert public_rows == expected
    assert sibling_rows == []
    # Removing package context while retaining the old text filter loses this public caller.
    old_prefilter_rows = (
        public_rows if "causal_engine" in source or "interference" in source else []
    )
    assert old_prefilter_rows == []


def test_literal_census_resolves_absolute_parent_imports_and_ignores_comments() -> None:
    """Actual AST statements, aliases and submodule fallback define the measured imports."""
    path = "policy-engine/src/polisyos/foundry/methods/catalog/causal/reader.py"
    source = (
        f"from {_CAUSAL_PREFIX} import causal_engine as selected, interference\n"
        "from .causal_engine import CausalEngine as Owner\n"
        f"import {_CAUSAL_PREFIX}.interference as effects\n"
        f"# from {_CAUSAL_PREFIX}.causal_engine import fake\n"
        f"TEXT = 'from {_CAUSAL_PREFIX}.interference import fake'\n"
    )
    public_rows, sibling_rows = _literal_import_rows(path, source)
    assert public_rows == [
        (1, _CAUSAL_PREFIX, ("causal_engine", "interference"), "absolute"),
        (2, f"{_CAUSAL_PREFIX}.causal_engine", ("CausalEngine",), "relative"),
        (3, f"{_CAUSAL_PREFIX}.interference", (), "absolute"),
    ]
    assert sibling_rows == []


def test_repository_literal_facade_imports_resolve() -> None:
    """Parse every tracked Python member and execute every resolved facade from-import.

    Encoding/parse/relative-resolution failures are explicit gaps, never silent exclusions.
    This census requires source-checkout origins; installed ABI checks live in the
    separate ``test_installed_facade_contract.py``. Literal AST imports cannot
    establish computed addresses or external consumer behavior.
    """
    root = next(parent for parent in Path(__file__).resolve().parents if (parent / ".git").exists())
    inventory = subprocess.check_output(["git", "ls-files", "-z", "--", "*.py"], cwd=root)
    paths = [entry.decode() for entry in inventory.split(b"\0") if entry]
    occurrences: list[dict[str, object]] = []
    internal_sibling_occurrences: list[dict[str, object]] = []
    callers: set[str] = set()
    gaps: list[dict[str, object]] = []
    parsed = 0
    content_digest = hashlib.sha256()
    source_root = root / "policy-engine/src"
    for path in paths:
        raw: bytes | None = None
        try:
            raw = (root / path).read_bytes()
            content_digest.update(path.encode() + b"\0" + hashlib.sha256(raw).digest())
            encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
            source = raw.decode(encoding)
            rows, sibling_rows = _literal_import_rows(path, source)
        except (OSError, UnicodeError, SyntaxError, ImportError, ValueError) as error:
            gaps.append(
                {
                    "path": path,
                    "content_sha256": (
                        hashlib.sha256(raw).hexdigest() if raw is not None else None
                    ),
                    "error_type": type(error).__name__,
                    "detail": str(error),
                }
            )
            continue
        parsed += 1
        for line, module, names, import_form in rows:
            if names:
                # Execute real from-import semantics, including package submodule fallback.
                namespace: dict[str, object] = {}
                exec(f"from {module} import {', '.join(names)}", namespace)  # noqa: S102
                for value in namespace.values():
                    owner_name = getattr(value, "__module__", "")
                    owner = (
                        value
                        if isinstance(value, ModuleType)
                        else importlib.import_module(owner_name)
                        if owner_name.startswith("polisyos.")
                        else None
                    )
                    if owner is not None and owner.__name__.startswith("polisyos."):
                        _assert_checkout_import_origin(owner, source_root)
            _assert_checkout_import_origin(importlib.import_module(module), source_root)
            role = (
                "historical_research_source"
                if "/docs/research/" in path
                else "runtime_source"
                if "/src/" in path
                else "test_source"
                if "/tests/" in path
                else "tool_source"
                if "/tools/" in path
                else "other_tracked_source"
            )
            occurrences.append(
                {
                    "path": path,
                    "line": line,
                    "module": module,
                    "names": names,
                    "import_form": import_form,
                    "source_role": role,
                    "runtime_client_established": False,
                }
            )
            callers.add(path)
        for line, module, names, import_form in sibling_rows:
            internal_sibling_occurrences.append(
                {
                    "path": path,
                    "line": line,
                    "module": module,
                    "names": names,
                    "import_form": import_form,
                }
            )
    gap_scope = sorted((gap["path"], gap["content_sha256"], gap["error_type"]) for gap in gaps)
    gap_scope_sha256 = hashlib.sha256(
        json.dumps(gap_scope, separators=(",", ":")).encode()
    ).hexdigest()
    historical_scope_matches = (
        len(gaps) == _HISTORICAL_EXCERPT_COUNT
        and gap_scope_sha256 == _HISTORICAL_EXCERPT_SCOPE_SHA256
    )
    print(
        json.dumps(
            {
                "executing_party": "F/causal_api",
                "git_head_context": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=root, text=True
                ).strip(),
                "tracked_python_denominator": len(paths),
                "tracked_python_inventory_sha256": hashlib.sha256(inventory).hexdigest(),
                "working_tree_python_content_sha256": content_digest.hexdigest(),
                "tracked_python_dirty_paths": subprocess.check_output(
                    ["git", "diff", "--name-only", "HEAD", "--", "*.py"], cwd=root, text=True
                ).splitlines(),
                "import_origin_profile": str(source_root.resolve()),
                "python_parsed": parsed,
                "parse_encoding_resolution_gaps": gaps,
                "gap_scope_sha256": gap_scope_sha256,
                "known_historical_excerpt_scope_matches": historical_scope_matches,
                "unparsed_excerpt_status": "BLOCKED",
                "unparsed_excerpt_boundary": (
                    "Exact eighteen B114 recovery function excerpts are not Python modules; "
                    "their unparsed contents do not support an exhaustive module/import claim."
                ),
                "literal_import_occurrences": len(occurrences),
                "literal_import_files": len(callers),
                "literal_imports": occurrences,
                "internal_sibling_import_occurrences": len(internal_sibling_occurrences),
                "internal_sibling_import_files": len(
                    {row["path"] for row in internal_sibling_occurrences}
                ),
                "internal_sibling_imports": internal_sibling_occurrences,
                "unresolved_boundary": "computed import addresses and external callers",
            },
            sort_keys=True,
        )
    )
    assert historical_scope_matches, f"Unexpected Python module/census gaps: {gaps}"
    expected_relative = {
        (
            f"policy-engine/src/{_CAUSAL_PREFIX.replace('.', '/')}/{suffix}",
            module,
            names,
            "relative",
        )
        for suffix, module, names in _RELATIVE_FACADE_CALLERS
    }
    actual_relative = {
        (row["path"], row["module"], tuple(row["names"]), row["import_form"])
        for row in occurrences
        if row["import_form"] == "relative"
    }
    assert actual_relative == expected_relative
    expected_internal_absolute = {
        (
            f"policy-engine/src/{_CAUSAL_PREFIX.replace('.', '/')}/causal_engine/{filename}",
            f"{_CAUSAL_PREFIX}.causal_engine.{module}",
            (binding,),
            "absolute",
        )
        for filename, module, binding in (
            ("__init__.py", "artifacts", "_artifacts"),
            ("api.py", "artifacts", "_artifacts"),
            ("api.py", "discovery", "_discovery"),
            ("api.py", "identification", "_identification"),
            ("discovery.py", "artifacts", "_artifacts"),
            ("estimation.py", "artifacts", "_artifacts"),
            ("identification.py", "artifacts", "_artifacts"),
            ("sensitivity.py", "artifacts", "_artifacts"),
        )
    }
    actual_internal = {
        (row["path"], row["module"], tuple(row["names"]), row["import_form"])
        for row in internal_sibling_occurrences
    }
    assert expected_internal_absolute <= actual_internal
    assert parsed + len(gaps) == len(paths)
    assert occurrences  # An empty measurement cannot qualify the supported consumers.


def test_benchmark_aggregate_and_json_report_preserve_unknown_topology() -> None:
    """The real benchmark aggregation and report serializer preserve nullable topology."""
    unknown_graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["T_1", "Y_1"],
        edges=[CausalEdge(src="T_1", dst="Y_1", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)],
        metadata={"dataset_ref": "unknown-unit-partition"},
    )
    unknown_artifact = interference.identify_interference_effect(
        unknown_graph,
        treatment="T_1",
        outcome="Y_1",
    )
    assert unknown_artifact.status == "oracle_needed"
    assert unknown_artifact.interference_detected is None
    assert unknown_artifact.sutva_violated is None

    known_graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["T_1", "Y_1", "T_2", "Y_2"],
        edges=[
            CausalEdge(src="T_1", dst="Y_1", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="T_2", dst="Y_2", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ],
        metadata={
            "dataset_ref": "known-no-cross-unit",
            "cluster_partition": [["T_1", "Y_1"], ["T_2", "Y_2"]],
        },
    )
    known_artifact = interference.identify_interference_effect(
        known_graph,
        treatment="T_1",
        outcome="Y_1",
    )
    assert known_artifact.status == "identified"
    assert known_artifact.interference_detected is False
    assert known_artifact.sutva_violated is False

    harness = BenchmarkHarness()
    for name, artifact in (
        ("unknown_partition", unknown_artifact),
        ("known_no_cross_unit", known_artifact),
    ):
        harness.register(
            BenchmarkCase(
                name=f"interference::{name}",
                circuit=policy_did_interference.CIRCUIT,
                runner=lambda value=artifact, case_name=name: {
                    "artifact": value,
                    "artifact_kind": "interference_detection",
                    "design": case_name,
                },
                checker=lambda _result: True,
            )
        )
    report = harness.run(circuit=policy_did_interference.CIRCUIT)
    aggregate = policy_did_interference._aggregate_metrics(report)
    rows = {row["case"]: row for row in aggregate["case_rows"]}

    unknown_row = rows["interference::unknown_partition"]
    assert unknown_row["interference_detected"] is None
    assert unknown_row["sutva_violated"] is None
    known_row = rows["interference::known_no_cross_unit"]
    assert known_row["interference_detected"] is False
    assert known_row["sutva_violated"] is False
    assert aggregate["n_detected_spillover_cases"] == 0
    assert aggregate["n_unknown_topology_cases"] == 1
    assert aggregate["flagship_scorecard"]["checks"]["spillover_detection"] is None
    assert aggregate["flagship_scorecard"]["passes_all"] is False

    known_only = BenchmarkHarness()
    known_only.register(
        BenchmarkCase(
            name="interference::known_no_cross_unit_only",
            circuit=policy_did_interference.CIRCUIT,
            runner=lambda: {
                "artifact": known_artifact,
                "artifact_kind": "interference_detection",
                "design": "known_no_cross_unit",
            },
            checker=lambda _result: True,
        )
    )
    known_only_aggregate = policy_did_interference._aggregate_metrics(
        known_only.run(circuit=policy_did_interference.CIRCUIT)
    )
    assert known_only_aggregate["flagship_scorecard"]["checks"]["spillover_detection"] is False
    assert known_only_aggregate["n_unknown_topology_cases"] == 0

    cross_graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["T_1", "Y_1", "T_2", "Y_2"],
        edges=[
            CausalEdge(src="T_1", dst="Y_1", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="T_2", dst="Y_2", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="T_1", dst="Y_2", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ],
        metadata={
            "dataset_ref": "known-cross-unit",
            "cluster_partition": [["T_1", "Y_1"], ["T_2", "Y_2"]],
        },
    )
    positive_artifact = interference.identify_interference_effect(
        cross_graph,
        treatment="T_1",
        outcome="Y_1",
    )
    assert positive_artifact.interference_detected is True
    assert positive_artifact.sutva_violated is True
    mixed_positive = BenchmarkHarness()
    for case_name, artifact in (
        ("unknown_partition", unknown_artifact),
        ("known_cross_unit", positive_artifact),
    ):
        mixed_positive.register(
            BenchmarkCase(
                name=f"interference::{case_name}",
                circuit=policy_did_interference.CIRCUIT,
                runner=lambda value=artifact: {
                    "artifact": value,
                    "artifact_kind": "interference_detection",
                },
                checker=lambda _result: True,
            )
        )
    mixed_positive_aggregate = policy_did_interference._aggregate_metrics(
        mixed_positive.run(circuit=policy_did_interference.CIRCUIT)
    )
    assert mixed_positive_aggregate["flagship_scorecard"]["checks"]["spillover_detection"] is True
    assert mixed_positive_aggregate["n_detected_spillover_cases"] == 1
    assert mixed_positive_aggregate["n_unknown_topology_cases"] == 1

    report_payload = policy_did_interference._report_to_dict(
        report,
        mode="smoke",
        preflight={"run_id": "unknown-topology-aggregate", "data_source": "synthetic"},
    )
    wire = json.loads(json.dumps(report_payload))
    wire_aggregate = wire["aggregate_metrics"]
    wire_rows = {row["case"]: row for row in wire_aggregate["case_rows"]}
    assert wire_rows["interference::unknown_partition"]["interference_detected"] is None
    assert wire_rows["interference::unknown_partition"]["sutva_violated"] is None
    assert wire_aggregate["n_unknown_topology_cases"] == 1
    serialized_unknown = next(
        case for case in wire["cases"] if case["case_id"] == "interference::unknown_partition"
    )
    serialized_artifact = serialized_unknown["result_payload"]["artifact"]
    assert serialized_artifact["interference_detected"] is None
    assert serialized_artifact["sutva_violated"] is None
