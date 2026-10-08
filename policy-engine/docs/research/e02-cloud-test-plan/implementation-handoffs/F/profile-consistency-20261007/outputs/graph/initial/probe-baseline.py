"""Independent known-MGraph semantic-profile intake discriminator."""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import logging
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--source", required=True)
parser.add_argument("--out", required=True)
parser.add_argument("--expect", choices=("baseline", "repaired"), required=True)
parser.add_argument("--remove-known-profile-guard", action="store_true")
args = parser.parse_args()
source = Path(args.source).resolve()
out = Path(args.out).resolve()
out.mkdir(parents=True, exist_ok=False)
sys.path.insert(0, str(source / "policy-engine" / "src"))

from polisyos.core.artifacts import PutOptions, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.methods.backends.circuit_breaker import get_circuit_breaker_registry
from polisyos.foundry.methods.catalog.causal import graph_reconciliation as owner
from polisyos.foundry.methods.catalog.causal.protocols import GraphReconciliationData
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal_graph import CausalGraphModel, GraphType, load_causal_graph_model, persist_causal_graph_model
from polisyos.ir.analytics.mgraph import MGraphMetadata, MissingnessKind, build_mgraph, extract_mgraph_metadata
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.compute.runner import run_job
from polisyos.scientist.nodes.builtins.causal import reconcile_causal_graph as node_module
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_CAUSAL_METHOD_RESULT_REF, ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState

guard_source = inspect.getsource(owner._validate_reconciliation_profile)
mutation = {"enabled": args.remove_known_profile_guard, "guard_source_sha256": hashlib.sha256(guard_source.encode()).hexdigest()}
if args.remove_known_profile_guard:
    def old_declared_static_profile_only(graph):
        if graph.graph_type not in {GraphType.DAG, GraphType.ADMG}:
            raise ValueError(f"Unsupported graph reconciliation profile: graph_type={graph.graph_type.value}; requires declared static DAG/ADMG")
        owner._validate_static_admg(graph)
    owner._validate_reconciliation_profile = old_declared_static_profile_only
    node_module._validate_reconciliation_profile = old_declared_static_profile_only
    mutation["scope"] = "Replace only new known-profile consistency predicate with pre-repair declared-static invariant in-process; tracked source/markers unchanged."

store = FileSystemCAS(out / "cas")
bundle = build_default_registry_bundle(store).bundle_ref
run = RunContext.start(store=store, registry_bundle=bundle, run_id="independent-profile")
ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("independent-profile"))
MethodRegistry.get_instance().register(owner.ReconcileCausalGraph, override=True)

original = build_mgraph(substantive_vars=["X", "Y"], directed_edges=[("X", "Y")], bidirected_edges=[("X", "Y")], missingness_map={"X": MissingnessKind.MCAR}, discovery_method="independent-semantic-profile")
payload = original.model_dump(mode="json")
for edge in payload["edges"]:
    edge.update(sources=["data"], data_confidence=0.9, combined_confidence=0.9)
original = CausalGraphModel.model_validate(payload)
assert extract_mgraph_metadata(original).r_nodes[0].missingness_kind is MissingnessKind.MCAR
original_ref = persist_causal_graph_model(store, original)
payload["graph_type"] = "admg"
retagged = CausalGraphModel.model_validate(payload)
assert MGraphMetadata.model_validate(retagged.metadata["mgraph"]) == extract_mgraph_metadata(original)
encoded = retagged.model_dump(mode="json")
encoded["metadata"]["mgraph"] = json.dumps(encoded["metadata"]["mgraph"], sort_keys=True)
json_profile = CausalGraphModel.model_validate(encoded)
clean_payload = retagged.model_dump(mode="json")
clean_payload["metadata"] = {"research_note": "R_X and X_star names alone have no typed profile"}
clean = CausalGraphModel.model_validate(clean_payload)
for name, value in (("original", original), ("retagged", retagged), ("json-profile", json_profile), ("clean", clean)):
    (out / f"input-{name}.json").write_text(json.dumps(value.model_dump(mode="json"), indent=2, sort_keys=True) + "\n")

def produce(value):
    get_circuit_breaker_registry().reset_all()
    request = GraphReconciliationData(data_graph=value)
    ref = store.put_json(request.model_dump(mode="json"), PutOptions(kind="tests.synthetic.graph_reconciliation_input", media_type="application/json", schema=SchemaInfo(name="tests.GraphReconciliationData", version="1.0")), canon_spec=CanonSpec(forbid_floats=False))
    return run_job(JobSpec(job_kind="method", method_fqn=owner.ReconcileCausalGraph.signature.fqn, input_refs={"graph_reconciliation_data": ref}, seed=41), cas_root=store.root, method_state=request)

def method_ref(value):
    return store.put_json({"graph": value.model_dump(mode="json")}, PutOptions(kind="scientist.method_result.causal.discovery", media_type="application/json", schema=SchemaInfo(name="polisyos.scientist.MethodResult", version="0.1.0")), canon_spec=CanonSpec(forbid_floats=False))

def execute(label, value, path, cutoff=0.1):
    if path == "direct":
        state = ExperimentState(run_id="independent-profile", params={"data_causal_graph": value.model_dump(mode="json"), "reconciliation_min_edge_confidence": cutoff})
    elif path == "supplied_result":
        state = ExperimentState(run_id="independent-profile", params={"reconciliation_min_edge_confidence": cutoff}, artifacts_index={ARTIFACT_CAUSAL_METHOD_RESULT_REF: method_ref(value)})
    elif path == "current_and_selected":
        selected = persist_causal_graph_model(store, value)
        state = ExperimentState(run_id="independent-profile", artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: selected, ARTIFACT_CAUSAL_METHOD_RESULT_REF: method_ref(value)})
    elif path == "selected_only":
        selected = persist_causal_graph_model(store, value)
        state = ExperimentState(run_id="independent-profile", artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: selected})
    else:
        raise AssertionError(path)
    outcome = node_module.ReconcileCausalGraphNode().execute(ctx, state)
    result = {"label": label, "path": path, "cutoff": cutoff, "status": outcome.status, "error": None if outcome.error is None else outcome.error.model_dump(mode="json"), "published_count": len(outcome.artifacts), "reconciled_ref": None, "profile_retained": None}
    # Existing selected refs are source inputs, never evidence of publication.
    if outcome.status == "ok":
        ref = outcome.state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF]
        reopened = load_causal_graph_model(FileSystemCAS(store.root), ref)
        result.update(reconciled_ref=str(ref.artifact_id), reopened_type=reopened.graph_type.value, profile_retained=reopened.metadata.get("mgraph") == value.metadata.get("mgraph"), relations=[(e.src, e.dst, e.mark_src.value, e.mark_dst.value, e.lag) for e in reopened.edges])
        (out / f"reopened-{label}-{path}-{cutoff}.json").write_text(json.dumps(reopened.model_dump(mode="json"), indent=2, sort_keys=True) + "\n")
    return result

rows = []
jobs = []
for label, value in (("retagged", retagged), ("json-profile", json_profile)):
    job = produce(value)
    jobs.append({"label": label, "issues": [issue.model_dump(mode="json") for issue in job.issues], "method_result_ref": None if job.method_result_ref is None else str(job.method_result_ref.artifact_id)})
    for path in ("direct", "supplied_result", "current_and_selected", "selected_only"):
        rows.append(execute(label, value, path))
    rows.append(execute(label, value, "direct", 0.99))

positive_job = produce(clean)
assert not positive_job.issues and positive_job.method_result_ref is not None, positive_job
positive_state = ExperimentState(run_id="independent-profile", artifacts_index={ARTIFACT_CAUSAL_METHOD_RESULT_REF: positive_job.method_result_ref})
positive_outcome = node_module.ReconcileCausalGraphNode().execute(ctx, positive_state)
assert positive_outcome.status == "ok" and len(positive_outcome.artifacts) == 1, positive_outcome
positive_ref = positive_outcome.state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF]
positive_reader = load_causal_graph_model(FileSystemCAS(store.root), positive_ref)
assert positive_reader.graph_type is GraphType.ADMG and "mgraph" not in positive_reader.metadata
assert { (e.src, e.dst, e.mark_src.value, e.mark_dst.value) for e in positive_reader.edges } == {("X", "Y", "tail", "arrow"), ("X", "Y", "arrow", "arrow"), ("R_X", "X_star", "tail", "arrow")}
assert positive_reader.metadata["research_note"] == clean.metadata["research_note"]
reopened_original = load_causal_graph_model(FileSystemCAS(store.root), original_ref)
assert reopened_original == original and extract_mgraph_metadata(reopened_original) == extract_mgraph_metadata(original)

origin_errors = []
origins = {}
for module_name, module in sorted(sys.modules.items()):
    path = getattr(module, "__file__", None)
    if module_name.startswith("polisyos") and path:
        resolved = Path(path).resolve()
        origins[module_name] = str(resolved)
        if not resolved.is_relative_to(source / "policy-engine" / "src"):
            origin_errors.append({"module": module_name, "path": str(resolved)})
assert not origin_errors, origin_errors
(out / "origins.json").write_text(json.dumps(origins, indent=2, sort_keys=True) + "\n")
failed_expectations = []
if args.expect == "repaired":
    for job in jobs:
        if not job["issues"] or job["method_result_ref"] is not None:
            failed_expectations.append({"job": job})
    for row in rows:
        if row["status"] != "fail" or row["published_count"] != 0:
            failed_expectations.append({"intake": row})
        # selected_only must fail at semantic intake, not just lack current source.
        elif "profile" not in str(row["error"]).lower():
            failed_expectations.append({"semantic_error_missing": row})
else:
    assert all(not job["issues"] and job["method_result_ref"] for job in jobs), jobs
    assert all(row["status"] == "ok" and row["profile_retained"] for row in rows if row["path"] != "selected_only"), rows

report = {"scope": "Synthetic known typed MGraph consistency only; no unknown-profile classifier, empirical missingness, causal authority, or general identification claim.", "input_profile": "real build_mgraph -> synthetic confidence=0.9 -> graph_type only retag ADMG; dict and existing-reader-supported JSON string", "mutation": mutation, "jobs": jobs, "intakes": rows, "positive": {"actual_job_node_fresh_store_reader": True, "declared": positive_reader.graph_type.value, "mgraph_key_absent": "mgraph" not in positive_reader.metadata, "same_node_names_and_relations": True, "actual_ref": str(positive_ref.artifact_id)}, "original_mgraph_readable": True, "origin_count": len(origins), "origin_errors": origin_errors, "failed_expectations": failed_expectations, "outcome": "FAIL" if failed_expectations else "PASS"}
(out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
print(json.dumps(report, indent=2, sort_keys=True))
if failed_expectations:
    raise AssertionError(f"Known profile semantic intake expectations failed in {len(failed_expectations)} cases")
