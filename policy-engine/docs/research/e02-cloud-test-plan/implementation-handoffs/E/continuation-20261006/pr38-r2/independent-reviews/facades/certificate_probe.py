"""Actual Scientist uncertainty and welfare consumers, forged denominator control."""
import copy
import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from polisyos.foundry import uncertainty as public
from polisyos.foundry.uncertainty import sampling_admission as canonical
from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import ExecPlanRef, Metrics, MetricsRef, SimulationResult
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.uncertainty import DistributionFamily, IntervalSemantics, UncertaintyEnvelope, UncertaintySource, persist_uncertainty_envelope
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState

mode=sys.argv[1]
root=Path(sys.argv[2]);source=Path(sys.argv[3]).resolve()
required=("BoundedIndicatorResponse","reconcile_draw_outcomes","sampling_content_digest","verify_mean_certificate")
assert all(getattr(public,n) is getattr(canonical,n) for n in required)
assert set(required)<=set(public.__all__)
if mode=="certificate_removed":
    public.verify_mean_certificate=lambda *a,**kw:None
from polisyos.scientist.nodes.builtins.simulate import propagate_uncertainty as un
from polisyos.scientist.nodes.builtins.simulate import propagate_welfare as wn
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_PROPAGATION_REPORT_REF,ARTIFACT_SIMULATION_RESULT_REF,INPUT_DATA_SNAPSHOT_REF
assert un.reconcile_draw_outcomes is wn.reconcile_draw_outcomes is public.reconcile_draw_outcomes
assert un.verify_mean_certificate is public.verify_mean_certificate
assert wn.sampling_content_digest is public.sampling_content_digest

store=FileSystemCAS(root/"uncertainty-cas")
registry=build_default_registry_bundle(store).bundle_ref
run=RunContext.start(store=store,registry_bundle=registry,run_id="independent-facade-uncertainty")
ctx=ExecutionContext(store=store,run=run,logger=logging.getLogger("independent.facade"))
env=UncertaintyEnvelope(point_estimate=.5,confidence_interval=(0.0,1.0),confidence_level=None,distribution_family=DistributionFamily.UNIFORM,source=UncertaintySource.CALIBRATION,interval_semantics=IntervalSemantics.HEURISTIC_RANGE,is_heuristic_ci=True,gate_eligible=False)
env_ref=persist_uncertainty_envelope(store,env)
data=store.put_json({"state":{}},PutOptions(kind="foundry.state_snapshot",media_type="application/json"))
snapshot=store.put_json(DataSnapshot(data_ref=data,uncertainty_envelope_ref=env_ref),PutOptions(kind="fabric.data_snapshot",media_type="application/json",schema=SchemaInfo(name="polisyos.core.DataSnapshot",version="0.1.0")))
plan=store.put_json({"program_ref":{"artifact_id":str(data.artifact_id),"kind":"foundry.program_graph","media_type":"application/json"},"order":[]},PutOptions(kind="foundry.exec_plan",media_type="application/json"))
metrics=store.put_json(Metrics(values={"independent_metric":10}),PutOptions(kind="foundry.metrics",media_type="application/json"))
sim=store.put_json(SimulationResult(exec_plan_ref=ExecPlanRef(artifact_id=plan.artifact_id),metrics_ref=MetricsRef(artifact_id=metrics.artifact_id)),PutOptions(kind="foundry.simulation_result",media_type="application/json"))
state=ExperimentState(run_id="independent-facade-uncertainty",inputs={INPUT_DATA_SNAPSHOT_REF:DataSnapshotRef(artifact_id=snapshot.artifact_id)},artifacts_index={ARTIFACT_SIMULATION_RESULT_REF:sim},params={"propagation_config":{"preferred_method":"monte_carlo","mc_n_samples":128,"mc_batch_size":128,"mc_min_valid_samples":10,"mc_seed":41,"compute_sensitivity":False},"propagation_sensitivity":{"independent_metric":{"data_snapshot":1.0}}})
state=state.model_copy(update={"params":{"propagation_config":{"mc_seed":41,"compute_sensitivity":False,"bounded_iid_mean":{"metric_id":"independent_metric","response_threshold":.001}}}})
assert un._load_config(state)==public.PropagationConfig.model_validate(state.params["propagation_config"])
outcome=un.PropagateUncertaintyNode().execute(ctx,state)
assert outcome.status=="ok"
fresh=FileSystemCAS(root/"uncertainty-cas")
updated=SimulationResult.model_validate(from_canonical_bytes(fresh.get_bytes(outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF].artifact_id)))
from polisyos.ir.analytics.uncertainty import load_uncertainty_envelope
envelope=load_uncertainty_envelope(fresh,updated.uncertainty_envelopes["independent_metric"])
certificate=canonical.verify_mean_certificate(envelope)
assert certificate is not None and certificate.pilot_stream!=certificate.main_stream
original_persist=un.persist_uncertainty_envelope
def persist_bad_certificate(store,envelope,*args,**kwargs):
    metadata=copy.deepcopy(envelope.metadata)
    metadata["mean_estimator_certificate"]["main_stream"]=metadata["mean_estimator_certificate"]["pilot_stream"]
    altered=envelope.model_copy(update={"metadata":metadata})
    return original_persist(store,altered,*args,**kwargs)
un.persist_uncertainty_envelope=persist_bad_certificate
try:
    un.PropagateUncertaintyNode().execute(ctx,state)
    refusal=None
except ValueError as exc:
    refusal=str(exc)
print(json.dumps({"mode":mode,"positive_certificate":certificate.model_dump(mode="json"),"fresh_actual_node_corrupt_certificate_refusal":refusal,"root_export_retained":"verify_mean_certificate" in public.__all__}),flush=True)
assert refusal is not None and "reconciliation" in refusal,refusal
print(json.dumps({"mode":mode,"scope":"mathematical bound for declared canonical IID U01 indicator mean; does not grant served/institutional authority","module_origins":{n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if n.startswith("polisyos.") and getattr(m,"__file__",None)}}),flush=True)
