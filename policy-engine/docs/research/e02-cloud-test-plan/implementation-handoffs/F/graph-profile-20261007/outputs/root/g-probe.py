from __future__ import annotations

import hashlib
import importlib.machinery
import json
import logging
import os
import resource
import sys
import time
import traceback
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RUN_TAG = os.environ.get("PROBE_RUN_TAG", "attempt2-confidence-annotated")
RUN_DIR = HERE / RUN_TAG
ROOT = Path("/Users/deniskopylov/.codex/worktrees/e02-integration-6971/polisyos").resolve()
SOURCE_ROOT = (HERE / "candidate/policy-engine/src").resolve()
MANIFEST_PATH = HERE / "source-manifest.json"
manifest = json.loads(MANIFEST_PATH.read_text())
manifest_by_path = {entry["path"]: entry for entry in manifest["entries"]}
ASSETS_MANIFEST_PATH = HERE / "working-assets-manifest.json"
assets_manifest = json.loads(ASSETS_MANIFEST_PATH.read_text())

# Remove the attached integration checkout's editable source path and require every
# Polisyos import to resolve from the pinned F source extraction.
clean_path: list[str] = []
for item in sys.path:
    if not item:
        continue
    try:
        resolved = Path(item).resolve()
    except OSError:
        clean_path.append(item)
        continue
    if resolved == (ROOT / "policy-engine/src").resolve():
        continue
    if resolved == ROOT or resolved == (ROOT / "policy-engine").resolve():
        continue
    clean_path.append(item)
sys.path[:] = [str(SOURCE_ROOT), *clean_path]

class CandidatePolisyosFinder:
    """Forbid fallback to any installed/live Polisyos source."""

    def find_spec(self, fullname: str, path: Any = None, target: Any = None):
        if fullname != "polisyos" and not fullname.startswith("polisyos."):
            return None
        search = [str(SOURCE_ROOT)] if path is None else [
            str(Path(item).resolve()) for item in path
            if Path(item).resolve() == SOURCE_ROOT
            or SOURCE_ROOT in Path(item).resolve().parents
        ]
        spec = importlib.machinery.PathFinder.find_spec(fullname, search)
        if spec is None:
            raise ModuleNotFoundError(
                f"candidate source closure has no module {fullname!r}; installed fallback forbidden"
            )
        origin = getattr(spec, "origin", None)
        if origin and origin not in ("built-in", "frozen"):
            resolved_origin = Path(origin).resolve()
            if SOURCE_ROOT not in resolved_origin.parents:
                raise ModuleNotFoundError(f"non-candidate Polisyos origin refused: {origin}")
        return spec

sys.meta_path.insert(0, CandidatePolisyosFinder())


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def verify_source_tree() -> dict[str, Any]:
    observed = 0
    bytes_total = 0
    paths = []
    for entry in manifest["entries"]:
        path = HERE / "candidate" / entry["path"]
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"source path missing or symlink: {entry['path']}")
        mode = oct(path.stat().st_mode & 0o777)[2:]
        if mode != entry["mode"][-3:]:
            raise RuntimeError(f"source mode mismatch: {entry['path']}: {mode}")
        actual = git_blob_sha1(path)
        if actual != entry["blob"]:
            raise RuntimeError(f"source blob mismatch: {entry['path']}: {actual}")
        observed += 1
        bytes_total += path.stat().st_size
        paths.append(entry["path"] + "\0" + actual + "\n")
    return {
        "file_count": observed,
        "bytes": bytes_total,
        "inventory_sha256": hashlib.sha256("".join(paths).encode()).hexdigest(),
    }


def verify_working_assets() -> dict[str, Any]:
    observed = 0
    bytes_total = 0
    paths = []
    for entry in assets_manifest["entries"]:
        path = HERE / "candidate" / entry["path"]
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"working asset missing or symlink: {entry['path']}")
        mode = oct(path.stat().st_mode & 0o777)[2:]
        if mode != entry["mode"][-3:]:
            raise RuntimeError(f"working asset mode mismatch: {entry['path']}: {mode}")
        actual = git_blob_sha1(path)
        if actual != entry["blob"]:
            raise RuntimeError(f"working asset blob mismatch: {entry['path']}: {actual}")
        observed += 1
        bytes_total += path.stat().st_size
        paths.append(entry["path"] + "\0" + actual + "\n")
    return {
        "file_count": observed,
        "bytes": bytes_total,
        "inventory_sha256": hashlib.sha256("".join(paths).encode()).hexdigest(),
    }


def audit_loaded_modules() -> dict[str, Any]:
    found: dict[str, dict[str, str]] = {}
    for name, module in sorted(sys.modules.items()):
        if name != "polisyos" and not name.startswith("polisyos."):
            continue
        origin = getattr(module, "__file__", None)
        if origin is None:
            locations = list(getattr(module, "__path__", []))
            resolved_locations = [str(Path(location).resolve()) for location in locations]
            if not resolved_locations or any(
                Path(location).resolve() != SOURCE_ROOT
                and SOURCE_ROOT not in Path(location).resolve().parents
                for location in locations
            ):
                raise RuntimeError(f"unbound namespace module origin {name}: {resolved_locations}")
            found[name] = {"origin": ",".join(resolved_locations), "blob": "namespace"}
            continue
        path = Path(origin).resolve()
        if SOURCE_ROOT not in path.parents:
            raise RuntimeError(f"loaded Polisyos module escaped candidate source: {name}={path}")
        rel = "policy-engine/src/" + path.relative_to(SOURCE_ROOT).as_posix()
        entry = manifest_by_path.get(rel)
        if entry is None:
            raise RuntimeError(f"loaded Polisyos module is not in exact Git archive: {name}={rel}")
        blob = git_blob_sha1(path)
        if blob != entry["blob"]:
            raise RuntimeError(f"loaded Polisyos module differs from exact Git blob: {name}={rel}")
        found[name] = {"origin": str(path), "blob": blob}
    return found


def relations(graph: Any) -> list[list[Any]]:
    return sorted(
        [
            edge.src,
            edge.dst,
            edge.mark_src.value,
            edge.mark_dst.value,
            edge.lag,
        ]
        for edge in graph.edges
    )


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    source_before = verify_source_tree()
    result: dict[str, Any] = {
        "candidate": manifest["candidate"],
        "candidate_tree": manifest["candidate_tree"],
        "run_tag": RUN_TAG,
        "source_before": source_before,
        "working_assets_before": verify_working_assets(),
        "environment": {
            "python": sys.version,
            "executable": sys.executable,
            "cwd": os.getcwd(),
            "platform": sys.platform,
            "pythonpath": os.environ.get("PYTHONPATH"),
            "pythondontwritebytecode": os.environ.get("PYTHONDONTWRITEBYTECODE"),
            "threads": {
                key: os.environ.get(key)
                for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")
            },
        },
        "controls": {},
        "verdict": "ERROR",
    }
    try:
        import pydantic
        import numpy
        from polisyos.core.artifacts import PutOptions, SchemaInfo
        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.core.canon import CanonSpec, from_canonical_bytes
        from polisyos.core.registry import build_default_registry_bundle
        from polisyos.core.run.context import RunContext
        from polisyos.foundry.methods.catalog.causal.graph_reconciliation import ReconcileCausalGraph
        from polisyos.foundry.methods.catalog.causal.protocols import GraphReconciliationData
        from polisyos.foundry.methods.registry import MethodRegistry
        from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, EdgeSource, GraphType, load_causal_graph_model
        from polisyos.ir.analytics.mgraph import MissingnessKind, build_mgraph, extract_mgraph_metadata
        from polisyos.scientist.compute.job_spec import JobSpec
        from polisyos.scientist.compute.runner import run_job
        from polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph import (
            ReconcileCausalGraphNode,
            _extract_graph,
        )
        from polisyos.scientist.nodes.builtins.state_keys import (
            ARTIFACT_CAUSAL_METHOD_RESULT_REF,
            ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
        )
        from polisyos.scientist.orchestration.engine.context import ExecutionContext
        from polisyos.scientist.orchestration.engine.state import ExperimentState
        from polisyos.foundry.methods.backends.circuit_breaker import get_circuit_breaker_registry

        result["environment"]["pydantic"] = pydantic.__version__
        result["environment"]["numpy"] = numpy.__version__

        dag = CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["X", "Y"],
            edges=[CausalEdge(
                src="X", dst="Y", sources=[EdgeSource.DATA],
                data_confidence=0.9, combined_confidence=0.9,
            )],
            discovery_method="native-probe-dag-control",
        )
        admg = CausalGraphModel(
            graph_type=GraphType.ADMG,
            nodes=["X", "Y"],
            edges=[
                CausalEdge(src="X", dst="Y", sources=[EdgeSource.DATA], data_confidence=0.9, combined_confidence=0.9),
                CausalEdge(src="X", dst="Y", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW,
                           sources=[EdgeSource.DATA], data_confidence=0.9, combined_confidence=0.9),
            ],
            discovery_method="native-probe-admg-control",
        )
        mgraph_built = build_mgraph(
            substantive_vars=["X", "Y"],
            directed_edges=[("X", "Y")],
            bidirected_edges=[("X", "Y")],
            missingness_map={"X": MissingnessKind.MCAR},
            discovery_method="native-probe-mgraph",
        )
        # Preserve the builder's validated M-graph structure and metadata, then
        # attach an explicit synthetic DATA weight to each generated edge so the
        # real reconciler's default threshold does not remove the discriminator.
        mgraph_payload = mgraph_built.model_dump(mode="json")
        mgraph_payload["edges"] = [
            {
                **edge,
                "sources": ["data"],
                "data_confidence": 0.9,
                "combined_confidence": 0.9,
            }
            for edge in mgraph_payload["edges"]
        ]
        mgraph = CausalGraphModel.model_validate(mgraph_payload)
        graph_cases = [("dag-control", dag), ("admg-control", admg), ("mgraph-target", mgraph)]
        input_dir = RUN_DIR / "inputs"
        output_dir = RUN_DIR / "outputs"
        input_dir.mkdir(exist_ok=True)
        output_dir.mkdir(exist_ok=True)
        (input_dir / "mgraph-builder-arguments.json").write_text(
            json.dumps(
                {
                    "substantive_vars": ["X", "Y"],
                    "directed_edges": [["X", "Y"]],
                    "bidirected_edges": [["X", "Y"]],
                    "missingness_map": {"X": "mcar"},
                    "discovery_method": "native-probe-mgraph",
                    "reconciliation_min_edge_confidence": 0.1,
                    "post_build_edge_evidence": {
                        "sources": ["data"],
                        "data_confidence": 0.9,
                        "combined_confidence": 0.9,
                        "meaning": "synthetic fixture only; no empirical or authority claim",
                    },
                    "note": "The graph structure and MGraphMetadata come from build_mgraph; the edge evidence annotation is revalidated so default reconciliation retains the structural discriminator.",
                },
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )
        (input_dir / "mgraph-builder-unscored.json").write_text(
            json.dumps(mgraph_built.model_dump(mode="json"), sort_keys=True, indent=2) + "\n"
        )
        for name, graph in graph_cases:
            raw = graph.model_dump(mode="json")
            (input_dir / f"{name}.json").write_text(json.dumps(raw, sort_keys=True, indent=2) + "\n")

        def run_case(name: str, graph: CausalGraphModel) -> dict[str, Any]:
            case_started = time.monotonic()
            cas_root = RUN_DIR / "cas" / name
            cas_root.mkdir(parents=True, exist_ok=True)
            store = FileSystemCAS(cas_root)
            bundle = build_default_registry_bundle(store).bundle_ref
            run = RunContext.start(store=store, registry_bundle=bundle, run_id=f"mgraph-local-{name}")
            ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(name))
            MethodRegistry.get_instance().register(ReconcileCausalGraph, override=True)
            request = GraphReconciliationData(data_graph=graph)
            (input_dir / f"{name}-request.json").write_text(
                json.dumps(request.model_dump(mode="json"), sort_keys=True, indent=2) + "\n"
            )
            source_ref = store.put_json(
                request.model_dump(mode="json"),
                PutOptions(
                    kind="tests.synthetic.graph_reconciliation_input",
                    media_type="application/json",
                    schema=SchemaInfo(name="tests.GraphReconciliationData", version="1.0"),
                ),
                canon_spec=CanonSpec(forbid_floats=False),
            )
            get_circuit_breaker_registry().reset_all()
            job = run_job(
                JobSpec(
                    job_kind="method",
                    method_fqn=ReconcileCausalGraph.signature.fqn,
                    input_refs={"graph_reconciliation_data": source_ref},
                    seed=23,
                ),
                cas_root=store.root,
                method_state=request,
            )
            row: dict[str, Any] = {
                "input_graph_type": graph.graph_type.value,
                "input_edges": relations(graph),
                "input_metadata_mgraph": graph.metadata.get("mgraph"),
                "input_schema_validated": True,
                "input_graph_validated_dump": graph.model_dump(mode="json"),
                "input_mgraph_metadata_reader": None,
                "source_artifact_id": source_ref.artifact_id,
                "producer_issues": [str(issue) for issue in (job.issues or [])],
                "producer_result_ref": str(job.method_result_ref) if job.method_result_ref else None,
                "producer_complete": not bool(job.issues) and job.method_result_ref is not None,
                "phase": "producer",
            }
            if graph.graph_type is GraphType.MGRAPH:
                try:
                    row["input_mgraph_metadata_reader"] = {
                        "outcome": "PASS",
                        "value": extract_mgraph_metadata(graph).model_dump(mode="json"),
                    }
                except Exception as exc:
                    row["input_mgraph_metadata_reader"] = {
                        "outcome": "FAIL",
                        "exception_type": type(exc).__name__,
                        "message": str(exc),
                    }
            if not row["producer_complete"]:
                row["elapsed_seconds"] = round(time.monotonic() - case_started, 6)
                return row
            method_result_payload = from_canonical_bytes(store.get_bytes(job.method_result_ref))
            producer_graph = _extract_graph(method_result_payload)
            row["producer_result_payload_keys"] = sorted(method_result_payload)
            row["producer_reconciled_graph_type"] = producer_graph.graph_type.value
            row["producer_reconciled_edges"] = relations(producer_graph)
            row["producer_reconciled_metadata_mgraph"] = producer_graph.metadata.get("mgraph")
            row["producer_mgraph_metadata_preserved"] = (
                graph.metadata.get("mgraph") == producer_graph.metadata.get("mgraph")
            )
            if graph.graph_type is GraphType.MGRAPH:
                try:
                    row["producer_extract_mgraph_metadata"] = {
                        "outcome": "PASS",
                        "value": extract_mgraph_metadata(producer_graph).model_dump(mode="json"),
                    }
                except Exception as exc:
                    row["producer_extract_mgraph_metadata"] = {
                        "outcome": "FAIL",
                        "exception_type": type(exc).__name__,
                        "message": str(exc),
                    }
            state = ExperimentState(
                run_id=f"mgraph-local-{name}",
                artifacts_index={ARTIFACT_CAUSAL_METHOD_RESULT_REF: job.method_result_ref},
            )
            outcome = ReconcileCausalGraphNode().execute(ctx, state)
            row["node_status"] = getattr(outcome.status, "value", str(outcome.status))
            row["node_error"] = str(outcome.error) if outcome.error else None
            row["phase"] = "node"
            if row["node_status"] != "ok":
                row["elapsed_seconds"] = round(time.monotonic() - case_started, 6)
                return row
            graph_ref = outcome.state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF]
            fresh_store = FileSystemCAS(cas_root)
            reopened = load_causal_graph_model(fresh_store, graph_ref)
            row["fresh_cas_ref"] = str(graph_ref)
            row["fresh_reader_graph_type"] = reopened.graph_type.value
            row["fresh_reader_edges"] = relations(reopened)
            row["fresh_reader_metadata_mgraph"] = reopened.metadata.get("mgraph")
            row["fresh_reader_graph_dump"] = reopened.model_dump(mode="json")
            row["mgraph_metadata_preserved"] = graph.metadata.get("mgraph") == reopened.metadata.get("mgraph")
            row["fresh_cas_artifact_available"] = fresh_store.has(graph_ref.artifact_id)
            row["phase"] = "fresh-reader"
            try:
                extracted = extract_mgraph_metadata(reopened)
                row["extract_mgraph_metadata"] = {
                    "outcome": "PASS",
                    "value": extracted.model_dump(mode="json"),
                }
            except Exception as exc:
                row["extract_mgraph_metadata"] = {
                    "outcome": "FAIL",
                    "exception_type": type(exc).__name__,
                    "message": str(exc),
                }
            row["elapsed_seconds"] = round(time.monotonic() - case_started, 6)
            return row

        for name, graph in graph_cases:
            result["controls"][name] = run_case(name, graph)
            (output_dir / f"{name}.json").write_text(
                json.dumps(result["controls"][name], sort_keys=True, indent=2, default=str) + "\n"
            )

        dag_row = result["controls"]["dag-control"]
        admg_row = result["controls"]["admg-control"]
        target = result["controls"]["mgraph-target"]
        dag_ok = (
            dag_row.get("producer_complete") is True
            and dag_row.get("node_status") == "ok"
            and dag_row.get("fresh_reader_graph_type") == "dag"
            and ["X", "Y", "tail", "arrow", None] in dag_row.get("fresh_reader_edges", [])
        )
        admg_ok = (
            admg_row.get("producer_complete") is True
            and admg_row.get("node_status") == "ok"
            and admg_row.get("fresh_reader_graph_type") == "admg"
            and ["X", "Y", "arrow", "arrow", None] in admg_row.get("fresh_reader_edges", [])
        )
        target_fails_after_admission = (
            target.get("producer_complete") is True
            and target.get("producer_reconciled_graph_type") == "admg"
            and target.get("node_status") == "ok"
            and target.get("fresh_reader_graph_type") == "admg"
            and target.get("producer_mgraph_metadata_preserved") is True
            and target.get("mgraph_metadata_preserved") is True
            and target.get("producer_extract_mgraph_metadata", {}).get("outcome") == "FAIL"
            and target.get("extract_mgraph_metadata", {}).get("outcome") == "FAIL"
            and target.get("extract_mgraph_metadata", {}).get("exception_type") == "ValueError"
        )
        target_refused_early = (
            not target.get("producer_complete", False)
            or target.get("node_status") not in (None, "ok")
        )
        result["decision"] = {
            "dag_control_valid": dag_ok,
            "admg_control_valid": admg_ok,
            "mgraph_target_early_typed_refusal": target_refused_early,
            "mgraph_target_admitted_then_type_erased_reader_failure": target_fails_after_admission,
            "mgraph_target_producer_output_type": target.get("producer_reconciled_graph_type"),
            "mgraph_target_producer_edges": target.get("producer_reconciled_edges"),
            "mgraph_target_producer_metadata_preserved": target.get("producer_mgraph_metadata_preserved"),
            "mgraph_target_producer_reader": target.get("producer_extract_mgraph_metadata"),
            "mgraph_target_output_type": target.get("fresh_reader_graph_type"),
            "mgraph_target_metadata_preserved": target.get("mgraph_metadata_preserved"),
            "mgraph_target_actual_reader": target.get("extract_mgraph_metadata"),
        }
        if not dag_ok or not admg_ok:
            result["verdict"] = "HARNESS_OR_CONTROL_ERROR"
        elif target_fails_after_admission:
            result["verdict"] = "CONFIRMED_ADMITTED_TYPE_ERASURE"
        elif target_refused_early:
            result["verdict"] = "SAFE_EARLY_REFUSAL"
        else:
            result["verdict"] = "INCONCLUSIVE_OTHER_PATH"
    except BaseException as exc:
        result["fatal"] = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
        result["verdict"] = "HARNESS_ERROR"
        print("PROBE_FATAL", type(exc).__name__, str(exc), file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
    finally:
        try:
            result["loaded_polisyos_modules"] = audit_loaded_modules()
        except BaseException as exc:
            result["module_origin_audit_error"] = {"type": type(exc).__name__, "message": str(exc)}
            result["verdict"] = "ORIGIN_AUDIT_ERROR"
        result["source_after"] = verify_source_tree()
        result["source_immutable"] = result.get("source_before") == result["source_after"]
        result["working_assets_after"] = verify_working_assets()
        result["working_assets_immutable"] = (
            result.get("working_assets_before") == result["working_assets_after"]
        )
        result["elapsed_seconds"] = round(time.monotonic() - started, 6)
        result["max_rss_platform_units"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        (RUN_DIR / "probe-results.json").write_text(json.dumps(result, sort_keys=True, indent=2, default=str) + "\n")
        print("PROBE_VERDICT", result["verdict"])
        print("PROBE_DECISION", json.dumps(result.get("decision", {}), sort_keys=True))
        print("PROBE_RUNTIME_SECONDS", result["elapsed_seconds"])
        print("PROBE_MAX_RSS_PLATFORM_UNITS", result["max_rss_platform_units"])
        print("PROBE_SOURCE_IMMUTABLE", result["source_immutable"])
    return 0 if result["verdict"] not in ("HARNESS_ERROR", "ORIGIN_AUDIT_ERROR", "HARNESS_OR_CONTROL_ERROR") else 2

if __name__ == "__main__":
    raise SystemExit(main())
