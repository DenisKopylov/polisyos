import importlib.util, json, sys
from pathlib import Path
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.ir.analytics.causal_graph import load_causal_graph_model
from polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph import ReconcileCausalGraphNode
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_CAUSAL_METHOD_RESULT_REF, ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
from polisyos.scientist.orchestration.engine.state import ExperimentState
if "--removal" in sys.argv:
    original = ReconcileCausalGraphNode.execute
    def old_cached(self, ctx, state):
        if ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF in state.artifacts_index:
            return NodeOutcome(status="ok", state=state)
        return original(self, ctx, state)
    ReconcileCausalGraphNode.execute = old_cached
path = Path("tests/unit/scientist/methods/causal/test_reconcile_graph_intake_contract.py")
spec = importlib.util.spec_from_file_location("actual_graph_intake_fixture", path)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
root = Path(sys.argv[1]);root.mkdir(parents=True, exist_ok=False)
ctx = fixture._ctx(root)
source = fixture._real_graph_job(ctx, fixture._graph())
state = ExperimentState(run_id="graph-intake", params={"random_seed":23}, artifacts_index={ARTIFACT_CAUSAL_METHOD_RESULT_REF:source})
old = ReconcileCausalGraphNode().execute(ctx,state)
current = old.state.model_copy(deep=True);current.params["random_seed"] = 24
new = ReconcileCausalGraphNode().execute(ctx,current)
records = []
for requested, outcome in [(23,old),(24,new)]:
    assert outcome.status == "ok"
    graph = load_causal_graph_model(ctx.store,outcome.state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF])
    ref = ArtifactRef.model_validate(graph.metadata["reconciliation_request_ref"])
    snapshot = from_canonical_bytes(ctx.store.get_bytes(ref))
    records.append({"requested_seed":requested,"resolved_seed":snapshot["random_seed"],"source_ref":snapshot["data_graph_ref"],"request_ref":ref.model_dump(mode="json"),"edges":[e.model_dump(mode="json") for e in graph.edges]})
print(json.dumps({"actual_registered_job":str(source.artifact_id),"records":records},sort_keys=True))
assert [row["resolved_seed"] for row in records] == [23,24], "cached bytes do not bind actual current seed context"
assert records[0]["edges"] == records[1]["edges"], "STRICT_CPU graph has no numerical RNG"
assert records[0]["request_ref"] != records[1]["request_ref"]
