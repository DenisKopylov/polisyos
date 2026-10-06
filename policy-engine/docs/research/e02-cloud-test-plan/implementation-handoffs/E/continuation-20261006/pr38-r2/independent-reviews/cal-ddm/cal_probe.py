"""Independent native scalar-admission/copy oracle; no repository changes."""
import json
import math
import sys
from fractions import Fraction
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.foundry import ExecPlan, ProgramGraph, ProgramGraphRef, ProgramNode
from polisyos.foundry.calibration import calibrator as cm
from polisyos.foundry.calibration.calibrator import Calibrator, CalibratorInputs
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.mechanisms.fiscal import IncomeTax
from polisyos.ir.analytics.calibration import CalibrationConfig, CalibrationTarget
from polisyos.ir.kernel import DEFAULT_MECHANISM_REGISTRY, DEFAULT_MERGE_RULE_REGISTRY, DEFAULT_SLOT_REGISTRY

mode = sys.argv[1] if len(sys.argv) > 1 else "native"
source = Path(cm.__file__).resolve()
assert source.is_relative_to(Path(sys.argv[2]).resolve()), source
if mode == "guard_removed":
    cm.validate_gaussian_observation_std = lambda scales: dict(scales) if scales is not None else None
if mode == "copy_removed":
    original_guard = cm.validate_gaussian_observation_std
    def uncopied(scales):
        original_guard(scales)
        return scales
    cm.validate_gaussian_observation_std = uncopied

counts = {"loader": 0, "emitter": 0}
original_emitter = IncomeTax.emit_patches
def observed_emitter(self, *a, **kw):
    counts["emitter"] += 1
    return original_emitter(self, *a, **kw)
IncomeTax.emit_patches = observed_emitter

def run(scales, mutate=None):
    counts.update(loader=0, emitter=0)
    def loader(_):
        counts["loader"] += 1
        if mutate is not None:
            mutate(scales)
        return {"params": {"rate": 0.4}, "schedule": {"start_step": 0, "end_step": 0}}
    aid = ArtifactID.from_sha256_hex("1" * 64)
    graph = ProgramGraph(ir_ref=ArtifactRef(artifact_id=aid, kind="ir.trinity_bundle", media_type="application/json"),
        nodes=[ProgramNode(node_id="actual-tax", node_kind="mechanism", mechanism_type="income_tax", outputs=["agents.income", "government.balance"])],
        edges=[], entrypoints=[])
    state = GlobalState.empty(n_agents=1, n_firms=1)
    state = state.replace(agents=state.agents.replace(income=jnp.array([100.0], dtype=jnp.float32), reported_income=jnp.array([100.0], dtype=jnp.float32)), government_balance=jnp.array(0.0, dtype=jnp.float32))
    config = CalibrationConfig(targets=[CalibrationTarget(target_id="revenue", model_metric_path="government_balance", loss={"relative": False})], steps=1, max_steps=1, seed=31, learning_rate=1e-9, hessian={"enabled": False})
    inputs = CalibratorInputs(config=config, program_graph=graph, exec_plan=ExecPlan(program_ref=ProgramGraphRef(artifact_id=aid), order=["actual-tax"]), base_state=state,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY, slot_registry=DEFAULT_SLOT_REGISTRY, merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        selector_field_registry=None, parameter_loader=loader, raw_targets={"revenue": [35.0]}, gaussian_observation_std=scales)
    return Calibrator(inputs).run()

results = []
if mode in ("native", "guard_removed"):
    for value in [True, np.bool_(True), False, np.bool_(False), 0.0, -0.1, math.inf, -math.inf, math.nan, "2.5", np.array(2.5), 10**1000]:
        try:
            run({"revenue": value})
            error = None
        except ValueError as exc:
            error = str(exc)
        entry = {"case": type(value).__name__ + ":" + str(value), "counts": dict(counts), "error": error}
        results.append(entry)
        print(json.dumps(entry), flush=True)
        assert error is not None and counts == {"loader": 0, "emitter": 0}, entry

if mode == "native":
    for value in [2.5, np.float32(2.5), np.float64(2.5), Fraction(5, 2), 5]:
        report = run({"revenue": value})
        profile = report.execution_context["objective_profile"]
        # Independent law: tax = 100*.4 = 40, observed = 35; .5*(5/sigma)^2.
        expected = 0.5 * (5.0 / float(value))**2
        entry = {"case": "positive-" + type(value).__name__, "counts": dict(counts), "loss": report.total_loss, "expected": expected, "profile": profile}
        results.append(entry)
        print(json.dumps(entry), flush=True)
        assert math.isclose(report.total_loss, expected, abs_tol=1e-6)
        assert profile["observation_std"] == {"revenue": float(value)}
        assert profile["gate_eligible"] is False and profile["row_law_basis"] == "consumer_asserted"
        assert counts["loader"] == 1 and counts["emitter"] > 0

if mode in ("native", "copy_removed"):
    for replacement in [5.0, True, math.nan]:
        scales = {"revenue": 2.5}
        report = run(scales, lambda values: values.update(revenue=replacement))
        profile = report.execution_context["objective_profile"]
        entry = {"case": "loader-mutates-original-" + str(replacement), "counts": dict(counts), "loss": report.total_loss, "profile": profile}
        results.append(entry)
        print(json.dumps(entry), flush=True)
        assert profile["observation_std"] == {"revenue": 2.5} and math.isclose(report.total_loss, 2.0, abs_tol=1e-6), entry

if mode == "native":
    try:
        run({"other-target": 2.5})
        raise AssertionError("target join admitted foreign key")
    except ValueError as exc:
        assert "cover exactly" in str(exc)
        assert counts == {"loader": 1, "emitter": 0}, counts
    report = run(None)
    assert math.isclose(report.total_loss, 25.0, abs_tol=1e-6), report.total_loss

origins = {n: str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if n.startswith("polisyos.") and getattr(m,"__file__",None)}
assert all(Path(p).is_relative_to(Path(sys.argv[2]).resolve()) for p in origins.values()), origins
print(json.dumps({"mode":mode,"checks":len(results),"module_origins":origins,"jax_devices":[str(d) for d in jax.devices()],"jax_x64":bool(jax.config.jax_enable_x64),"oracle":{"income":100,"rate":.4,"actual_revenue":40,"observed":35,"frozen_sigma":2.5,"nll":2.0}},sort_keys=True),flush=True)
