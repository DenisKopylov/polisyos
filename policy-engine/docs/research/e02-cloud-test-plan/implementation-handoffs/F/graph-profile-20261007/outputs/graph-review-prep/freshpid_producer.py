"""Independent native producer/node refusal and a distinct-PID CAS reader."""

import hashlib
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path("/workspace/e02-F-closeout-20261006")
PRODUCT = ROOT / "policy-engine"
SOURCE_SHA = "4ee2f2a4f1d9c4d42c6e5ec7f85f973e07358f0d"
SOURCE_TREE = "551d4e760dc1168f6ad8182c9b176f00e94a2281"
GRAPH_PATHS = (
    "policy-engine/docs/reference/scientist/causal-graph-intake.md",
    "policy-engine/release-fragments/unreleased/2026-10-07-causal-graph-intake.toml",
    "policy-engine/src/polisyos/foundry/methods/catalog/causal/graph_reconciliation.py",
    "policy-engine/src/polisyos/scientist/nodes/builtins/causal/reconcile_causal_graph.py",
    "policy-engine/tests/unit/foundry/methods/catalog/causal/test_graph_reconciliation.py",
    "policy-engine/tests/unit/scientist/methods/causal/test_graph_intake_current_content.py",
)


def digest(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


def guard():
    assert git("rev-parse", "HEAD").decode().strip() == SOURCE_SHA
    assert git("rev-parse", "HEAD^{tree}").decode().strip() == SOURCE_TREE
    rows = []
    for relative in GRAPH_PATHS:
        body = (ROOT / relative).read_bytes()
        canonical = git("show", f"{SOURCE_SHA}:{relative}")
        assert body == canonical, relative
        rows.append({"path": relative, "git_ref": SOURCE_SHA, **digest(body)})
    return rows


def bind_origins(origins):
    rows = []
    for entry in origins:
        path = Path(entry["path"])
        assert path.is_relative_to(PRODUCT / "src"), entry
        relative = path.relative_to(ROOT).as_posix()
        canonical = git("show", f"{SOURCE_SHA}:{relative}")
        assert digest(canonical) == {key: entry[key] for key in ("bytes", "sha256")}, entry
        assert path.read_bytes() == canonical, entry
        rows.append({**entry, "git_ref": SOURCE_SHA, "git_path": relative})
    return rows


def main():
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    assert not (output / "cas").exists(), "Refuse to reuse a previous witness CAS"
    started = time.monotonic()
    before = guard()
    sys.path.insert(0, str(PRODUCT / "src"))
    from polisyos.core.artifacts import PutOptions, SchemaInfo
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.canon import CanonSpec
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.foundry.methods.backends.circuit_breaker import get_circuit_breaker_registry
    from polisyos.foundry.methods.catalog.causal.graph_reconciliation import ReconcileCausalGraph
    from polisyos.foundry.methods.catalog.causal.protocols import GraphReconciliationData
    from polisyos.foundry.methods.registry import MethodRegistry
    from polisyos.ir.analytics.causal_graph import CausalGraphModel, load_causal_graph_model, persist_causal_graph_model
    from polisyos.ir.analytics.mgraph import MissingnessKind, build_mgraph, extract_mgraph_metadata
    from polisyos.scientist.compute.job_spec import JobSpec
    from polisyos.scientist.compute.runner import run_job
    from polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph import ReconcileCausalGraphNode
    from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_CAUSAL_METHOD_RESULT_REF, ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    store = FileSystemCAS(output / "cas")
    registry = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry, run_id="independent-family-profile")
    context = ExecutionContext(store=store, run=run, logger=logging.getLogger("independent-family-profile"))
    MethodRegistry.get_instance().register(ReconcileCausalGraph, override=True)
    raw = build_mgraph(
        substantive_vars=["X", "Y"],
        directed_edges=[("X", "Y")],
        bidirected_edges=[("X", "Y")],
        missingness_map={"X": MissingnessKind.MCAR},
        discovery_method="independent-native-type-profile",
    ).model_dump(mode="json")
    for edge in raw["edges"]:
        edge.update(sources=["data"], data_confidence=0.9, combined_confidence=0.9)
    mgraph = CausalGraphModel.model_validate(raw)
    original_ref = persist_causal_graph_model(store, mgraph)
    original_metadata = extract_mgraph_metadata(mgraph).model_dump(mode="json")

    def produce(graph):
        get_circuit_breaker_registry().reset_all()
        payload = GraphReconciliationData(data_graph=graph)
        source = store.put_json(
            payload.model_dump(mode="json"),
            PutOptions(
                kind="tests.synthetic.independent_graph_profile",
                media_type="application/json",
                schema=SchemaInfo(name="tests.GraphReconciliationData", version="1.0"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        result = run_job(
            JobSpec(
                job_kind="method",
                method_fqn=ReconcileCausalGraph.signature.fqn,
                input_refs={"graph_reconciliation_data": source},
                seed=37,
            ),
            cas_root=store.root,
            method_state=payload,
        )
        return result, source

    refused, refused_input = produce(mgraph)
    assert refused.issues and refused.method_result_ref is None, refused
    direct = ReconcileCausalGraphNode().execute(
        context,
        ExperimentState(
            run_id="independent-family-profile",
            params={"data_causal_graph": mgraph.model_dump(mode="json")},
        ),
    )
    assert direct.status == "fail" and not direct.artifacts, direct
    assert "Unsupported graph reconciliation profile" in direct.error.message
    assert ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF not in direct.state.artifacts_index
    admg_raw = mgraph.model_dump(mode="json")
    admg_raw["graph_type"] = "admg"
    admg = CausalGraphModel.model_validate(admg_raw)
    accepted, accepted_input = produce(admg)
    assert not accepted.issues and accepted.method_result_ref is not None, accepted
    outcome = ReconcileCausalGraphNode().execute(
        context,
        ExperimentState(
            run_id="independent-family-profile",
            artifacts_index={ARTIFACT_CAUSAL_METHOD_RESULT_REF: accepted.method_result_ref},
        ),
    )
    assert outcome.status == "ok", outcome.error
    admg_ref = outcome.state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF]
    reopened = load_causal_graph_model(FileSystemCAS(store.root), admg_ref)
    assert reopened.graph_type.value == "admg"
    assert reopened.metadata["mgraph"] == mgraph.metadata["mgraph"]
    reverse = CausalGraphModel.model_validate(
        {
            "graph_type": "admg",
            "nodes": ["X", "Y"],
            "edges": [{"src": "Y", "dst": "X", "mark_src": "arrow", "mark_dst": "tail", "sources": ["data"], "data_confidence": 0.9, "combined_confidence": 0.9}],
        }
    )
    reverse_job, reverse_input = produce(reverse)
    assert not reverse_job.issues and reverse_job.method_result_ref is not None
    reverse_outcome = ReconcileCausalGraphNode().execute(
        context,
        ExperimentState(
            run_id="independent-family-profile",
            artifacts_index={ARTIFACT_CAUSAL_METHOD_RESULT_REF: reverse_job.method_result_ref},
        ),
    )
    assert reverse_outcome.status == "ok", reverse_outcome.error
    reverse_ref = reverse_outcome.state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF]
    reverse_graph = load_causal_graph_model(FileSystemCAS(store.root), reverse_ref)
    assert {(edge.src, edge.dst, edge.mark_src.value, edge.mark_dst.value, edge.lag) for edge in reverse_graph.edges} == {("X", "Y", "tail", "arrow", None)}
    static_refusals = []
    for case, changes in (
        ("circle_endpoint", {"mark_src": "circle", "mark_dst": "arrow"}),
        ("tail_tail", {"mark_src": "tail", "mark_dst": "tail"}),
        ("compact_lag", {"lag": 1}),
    ):
        static_graph = CausalGraphModel.model_validate(
            {
                "graph_type": "admg",
                "nodes": ["X", "Y"],
                "edges": [{"src": "X", "dst": "Y", "sources": ["data"], "data_confidence": 0.9, "combined_confidence": 0.9, **changes}],
            }
        )
        static_job, static_input = produce(static_graph)
        assert static_job.issues and static_job.method_result_ref is None, case
        static_outcome = ReconcileCausalGraphNode().execute(
            context,
            ExperimentState(
                run_id="independent-family-profile",
                params={"data_causal_graph": static_graph.model_dump(mode="json"), "reconciliation_min_edge_confidence": 0.99},
            ),
        )
        assert static_outcome.status == "fail" and not static_outcome.artifacts, case
        assert "Unsupported static ADMG profile" in static_outcome.error.message, case
        assert ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF not in static_outcome.state.artifacts_index, case
        static_refusals.append({"case": case, "check": "PASS", "input_ref": static_input.model_dump(mode="json"), "input_graph": static_graph.model_dump(mode="json"), "producer": static_job.model_dump(mode="json"), "node": static_outcome.model_dump(mode="json")})
    child_inputs = {
        "source_sha": SOURCE_SHA,
        "product_root": str(PRODUCT),
        "producer_pid": os.getpid(),
        "cas_root": str(store.root),
        "original_mgraph_ref": original_ref.model_dump(mode="json"),
        "reconciled_admg_ref": admg_ref.model_dump(mode="json"),
        "original_mgraph": mgraph.model_dump(mode="json"),
        "reconciled_admg": reopened.model_dump(mode="json"),
        "original_missingness_metadata": original_metadata,
        "reverse_admg_ref": reverse_ref.model_dump(mode="json"),
        "reverse_admg": reverse_graph.model_dump(mode="json"),
    }
    child_path = output / "fresh-reader-inputs.json"
    child_path.write_text(json.dumps(child_inputs, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    child_argv = [sys.executable, "-I", "-B", str(Path(__file__).with_name("freshpid_reader.py")), str(child_path)]
    child = subprocess.run(child_argv, cwd=output, capture_output=True, check=False)
    (output / "fresh-reader.stdout.txt").write_bytes(child.stdout)
    (output / "fresh-reader.stderr.txt").write_bytes(child.stderr)
    assert child.returncode == 0, child.stderr.decode(errors="replace")
    fresh = json.loads(child.stdout)
    assert fresh["check"] == "PASS" and fresh["pid"] != os.getpid()
    reader_origins = bind_origins(fresh["loaded_origins"])
    origins = []
    for name, module in sorted(sys.modules.items()):
        if not name.startswith("polisyos"):
            continue
        origin = getattr(module, "__file__", None)
        if origin:
            path = Path(origin).resolve()
            origins.append({"module": name, "path": str(path), **digest(path.read_bytes())})
    producer_origins = bind_origins(origins)
    after = guard()
    assert before == after
    record = {
        "schema": "independent_graph_semantic_profile_native_witness/1.0",
        "reviewer": "graph_scm",
        "check": "PASS",
        "outcome": "GO_BOUNDED",
        "source_sha": SOURCE_SHA,
        "source_tree": SOURCE_TREE,
        "implementation_sha": "36b18cc142aff77a5825126b4f07bafec09a5180",
        "implementation_graph_inputs_identical": True,
        "python": sys.version,
        "interpreter": sys.executable,
        "cwd": str(Path.cwd()),
        "argv": sys.argv,
        "pid": os.getpid(),
        "reader_pid": fresh["pid"],
        "metrics_port_env": os.environ.get("POLISYOS_METRICS_PORT"),
        "wall_s": time.monotonic() - started,
        "genuine_method_fqn": ReconcileCausalGraph.signature.fqn,
        "node_id": "scientist.node_reconcile_causal_graph@1.0.0",
        "mgraph_input_ref": refused_input.model_dump(mode="json"),
        "mgraph_producer": refused.model_dump(mode="json"),
        "mgraph_node": direct.model_dump(mode="json"),
        "admg_input_ref": accepted_input.model_dump(mode="json"),
        "admg_producer": accepted.model_dump(mode="json"),
        "admg_node": outcome.model_dump(mode="json"),
        "reverse_admg_input": reverse.model_dump(mode="json"),
        "reverse_admg_input_ref": reverse_input.model_dump(mode="json"),
        "reverse_admg_producer": reverse_job.model_dump(mode="json"),
        "reverse_admg_node": reverse_outcome.model_dump(mode="json"),
        "static_refusals": static_refusals,
        "child_argv": child_argv,
        "child_returncode": child.returncode,
        "child_stdout": {"path": str(output / "fresh-reader.stdout.txt"), **digest(child.stdout)},
        "child_stderr": {"path": str(output / "fresh-reader.stderr.txt"), **digest(child.stderr)},
        "source_guard_before": before,
        "source_guard_after": after,
        "producer_loaded_origins": producer_origins,
        "reader_loaded_origins": reader_origins,
        "limits": [
            "Finite native graph family-admission witness; no general PAG/CPDAG identification property.",
            "Original B214 remains limited; no G ledger closure or scientific authority claim.",
            "DoWhy/EconML are neither selected nor witnesses in this native Python 3.14 graph profile.",
        ],
    }
    (output / "native-witness.json").write_text(json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"check": "PASS", "source_sha": SOURCE_SHA, "pid": os.getpid(), "reader_pid": fresh["pid"], "producer_origins": len(producer_origins), "reader_origins": len(reader_origins), "output": str(output / "native-witness.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
