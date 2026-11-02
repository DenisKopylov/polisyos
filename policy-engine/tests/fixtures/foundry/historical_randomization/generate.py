"""Generate today's bounded software fixture using an exact immutable old Git source."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import site
import sys
from pathlib import Path

old_product = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
current_product = Path(sys.argv[3]).resolve()
source_admission = json.loads(Path(sys.argv[4]).read_text())
old_executor = Path(
    "/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos"
).resolve()
allowed_sites = [Path(x).resolve() for x in site.getsitepackages()]
prior_paths = list(sys.path)
kept = []
for value in prior_paths:
    if not value:
        continue
    path = Path(value).resolve()
    dependency_site = any(path.is_relative_to(x) for x in allowed_sites)
    project_source = path.is_relative_to(current_product.parent) or path.is_relative_to(
        old_executor
    )
    if dependency_site or not project_source:
        kept.append(value)
if any(
    name == "polisyos"
    or name.startswith("polisyos.")
    or name == "tools"
    or name.startswith("tools.")
    for name in sys.modules
):
    raise RuntimeError("first-party import occurred before historical source admission")
sys.path[:] = [str(old_product / "src"), str(old_product), *kept]
os.environ["PYTHONPATH"] = os.pathsep.join([str(old_product / "src"), str(old_product)])
output.mkdir(parents=True, exist_ok=False)
os.chdir(output)

import jax
import jax.numpy as jnp
import numpy as np

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.compiler.report import CompileReport
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    CompileRequest,
    ExecPlan,
    ExecPlanRef,
    ExecuteRequest,
    FoundryCompileConfig,
    FoundryExecConfig,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    ProgramGraph,
    SimulationResult,
    StateSnapshotRef,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.foundry.compile.api import compile
from polisyos.foundry.compile.randomization import TreasuryPlan
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.api import execute
from polisyos.foundry.execute.executor import load_state_snapshot, put_state_snapshot
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle

PARAMS = {
    "observation_space": ["agents.income"],
    "action_space": {"type": "continuous", "affects": ["agents.income"]},
    "policy_model": {"type": "mlp", "hidden_layers": []},
    "utility": "linear",
    "seed": 0,
    "stochastic": True,
}


def require(condition, detail):
    if not condition:
        raise AssertionError(detail)


def load(store, ref, model):
    return model.model_validate(from_canonical_bytes(store.get_bytes(ref)))


results = []
for seed in (0, 17, -3):
    store = FileSystemCAS(output / f"seed-{seed}" / "cas")
    registry = build_default_registry_bundle(store)
    bundle = TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="historical_treasury_software", domain=ProblemDomain.FISCAL
        ),
        policy_spec=PolicySpec(
            policy_id="historical_treasury_software",
            interventions=[
                InterventionSpec(
                    intervention_id="stochastic_action",
                    kind="adaptive_agent",
                    target={"kind": "predicate", "field": "id", "operator": "==", "value": "all"},
                    schedule={"start_step": 0, "duration_steps": 1},
                    params=PARAMS,
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="historical_treasury_software",
            data_snapshot_ref="sha256:" + "0" * 64,
            registry_bundle_ref=str(registry.bundle_ref.artifact_id),
        ),
    )
    source = store.put_json(
        bundle,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=bundle.schema_version),
        ),
    )
    compiled = compile(
        store,
        CompileRequest(
            policy_ref=source,
            registry_bundle_ref=registry.bundle_ref,
            compile_config=FoundryCompileConfig(random_seed=seed, max_steps=1),
        ),
    )
    require(compiled.ok, compiled.notes)
    report = load(store, compiled.compile_report_ref, CompileReport)
    plan = load(store, report.exec_plan_ref, ExecPlan)
    graph = load(store, report.program_graph_ref, ProgramGraph)
    treasury = load(store, report.treasury_plan_ref, TreasuryPlan)
    require(
        not any(note.startswith("randomization:") for note in plan.notes),
        "old source unexpectedly emits a versioned randomization marker",
    )
    require(plan.random_seed == seed, "old compile seed differs")
    base = GlobalState.empty(n_agents=32, n_firms=0)
    base = base.replace(
        agents=base.agents.replace(active=jnp.ones(32, dtype=jnp.bool_), income=jnp.zeros(32))
    )
    snapshot = put_state_snapshot(store, state=base, step=0)
    snapshot_ref = StateSnapshotRef(artifact_id=snapshot.artifact_id)
    data_ref = store.put_json(
        DataSnapshot(data_ref=snapshot_ref),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
        ),
    )
    bindings_ref = store.put_json(
        FoundryInputBindings(
            data_snapshot_ref=data_ref,
            registry_bundle_ref=registry.bundle_ref,
            rules=[],
            bound_state_snapshot_ref=snapshot_ref,
        ),
        PutOptions(
            kind="foundry.input_bindings",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.core.FoundryInputBindings",
                version="1.0",
            ),
        ),
    )
    executed = execute(
        store,
        ExecuteRequest(
            exec_plan_ref=ExecPlanRef.model_validate(report.exec_plan_ref.model_dump()),
            input_bindings_ref=FoundryInputBindingsRef(artifact_id=bindings_ref.artifact_id),
            registry_bundle_ref=registry.bundle_ref,
            exec_config=FoundryExecConfig(seed=seed, max_steps=1),
            welfare_bound_mode="ex_ante",
        ),
    )
    require(executed.ok, executed.notes)
    fresh = FileSystemCAS(output / f"seed-{seed}" / "cas")
    simulation = load(fresh, executed.simulation_result_ref, SimulationResult)
    final = load_state_snapshot(fresh, snapshot_ref=simulation.state_snapshot_ref)
    income = np.asarray(final.agents.income)
    require(
        income.shape == (32,) and np.isfinite(income).all(), "old actual result is not finite32"
    )
    refs = {
        "registry_bundle": registry.bundle_ref,
        "source": source,
        "compile_report": compiled.compile_report_ref,
        "program_graph": report.program_graph_ref,
        "exec_plan": report.exec_plan_ref,
        "treasury_plan": report.treasury_plan_ref,
        "slot_layout": report.slot_layout_ref,
        "simulation_result": executed.simulation_result_ref,
    }
    result = {
        "seed": seed,
        "refs": {name: ref.model_dump(mode="json") for name, ref in refs.items()},
        "program": graph.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
        "treasury": treasury.model_dump(mode="json"),
        "observed_income": income.tolist(),
        "observed_income_dtype": str(income.dtype),
        "observed_active": np.asarray(final.agents.active).tolist(),
        "observed_reported_income": np.asarray(final.agents.reported_income).tolist(),
        "observed_government_balance": float(final.government_balance),
    }
    (output / f"seed-{seed}" / "observed.json").write_text(json.dumps(result, indent=2) + "\n")
    results.append(result)

origins = []
for name, module in sorted(sys.modules.copy().items()):
    if (
        name == "polisyos"
        or name.startswith("polisyos.")
        or name == "tools"
        or name.startswith("tools.")
    ):
        filename = getattr(module, "__file__", None)
        if filename is not None:
            origin = Path(filename).resolve()
            require(
                origin.is_relative_to(old_product / "src")
                or origin.is_relative_to(old_product / "tools"),
                (name, origin),
            )
            origins.append(
                {
                    "module": name,
                    "path": str(origin),
                    "sha256": hashlib.sha256(origin.read_bytes()).hexdigest(),
                }
            )
receipt = {
    "status": "PASS",
    "old_commit": source_admission["old_commit"],
    "old_tree": source_admission["old_tree"],
    "generated_today": True,
    "retained_production_provenance": False,
    "profile": {
        "python": sys.version,
        "executable": sys.executable,
        "versions": {
            name: importlib.metadata.version(name)
            for name in ("jax", "jaxlib", "numpy", "pydantic", "optax")
        },
        "jax_backend": jax.default_backend(),
        "x64": jax.config.x64_enabled,
    },
    "source_paths_before": prior_paths,
    "source_paths_after": sys.path,
    "all_first_party_origins_old_selected_source": True,
    "loaded_first_party_modules": origins,
    "seeds": [
        {
            "seed": r["seed"],
            "exec_plan_ref": r["refs"]["exec_plan"],
            "observed_income": r["observed_income"],
        }
        for r in results
    ],
    "scope": "Exact old-source compiler and public executor, generated today with current supported backend over bounded synthetic input. Not a retained production corpus or old-environment qualification.",
}
(output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
sys.stdout.write(
    json.dumps(
        {
            k: v
            for k, v in receipt.items()
            if k not in {"loaded_first_party_modules", "source_paths_before", "source_paths_after"}
        },
        indent=2,
    )
    + "\n"
)
