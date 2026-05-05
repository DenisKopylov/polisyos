"""
End-to-end demo: Mechanism Design через IR/Compiler/Foundry runtime + JAX grad.
FIXED VERSION: Stabilized Gradients & Agent Training
"""

import io
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from tools.lib.imports import repo_root_from

# --- Make `polisyos` importable ---
POLICY_ENGINE_ROOT = repo_root_from(__file__)
SRC_ROOT = POLICY_ENGINE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

os.environ.setdefault("JAX_PLATFORMS", "cpu")
os.environ.setdefault("JAX_PLATFORM_NAME", "cpu")

import equinox as eqx
import jax
import jax.numpy as jnp
import optax
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import CompileRequest, ExecPlan, ProgramGraph
from polisyos.core.registry import build_default_registry_bundle
from polisyos.foundry._registry import create_mechanism_from_spec
from polisyos.foundry.agent_sim.agents import AgentPolicy
from polisyos.foundry.base import Mechanism
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.domain.state import GlobalState
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
)
from polisyos.ir.kernel.merge_rules import MergeRuleKind
from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle

# --- CONFIG (TWEAKED) ---
N_AGENTS = 5000
SEED = 42
# Coef 1.2 implies crossover at Tax ~ 0.6 for avg risk (0.5 * 1.2)
RISK_PENALTY_COEF = 0.6
ENTROPY_COEF = 0.1


def print_header(title: str) -> None:
    print(f"\n{'=' * 60}\n {title}\n{'=' * 60}")


def _load_json(store: FileSystemCAS, artifact_id: ArtifactID) -> Any:
    payload = store.get_bytes(artifact_id)
    return json.loads(payload.decode("utf-8"))


def _merge_rule_code(kind: MergeRuleKind) -> int:
    if kind == MergeRuleKind.SUM:
        return 0
    if kind == MergeRuleKind.OVERRIDE:
        return 1
    if kind == MergeRuleKind.PRIORITY:
        return 2
    return 3


class SystemBundle(eqx.Module):
    mechanisms: dict[str, Mechanism]
    slot_state_path: dict[str, str] = eqx.field(static=True)
    slot_merge_code: dict[str, int] = eqx.field(static=True)


# --- Phase 1: Training & Artifacts ---
def train_and_store_artifact(key: jax.Array, n_agents: int, store: FileSystemCAS) -> str:
    print(">>> [Phase 1] Обучение популяции и сохранение в CAS...")
    key, subkey = jax.random.split(key)
    policy = AgentPolicy(
        subkey, in_dim=3, action_type="continuous", out_dim=1, hidden_layers=(64, 64)
    )

    params = eqx.filter(policy, eqx.is_inexact_array)
    static = eqx.filter(policy, eqx.is_inexact_array, inverse=True)
    optimizer = optax.adam(0.01)
    opt_state = optimizer.init(params)

    @eqx.filter_jit
    def train_step(p, opt_st, k):
        k1, k2, k3 = jax.random.split(k, 3)
        incomes = jnp.exp(jax.random.normal(k1, (n_agents,)) * 0.5 + 3.0)
        risks = jax.random.uniform(k2, (n_agents,))
        taxes = jax.random.uniform(k3, (n_agents,))

        def loss_fn(model_params):
            model = eqx.combine(model_params, static)
            obs = jnp.stack([jnp.log1p(incomes), risks, taxes], axis=1)
            logits = model(obs)
            fraction = jax.nn.sigmoid(logits).reshape(-1)

            tax_paid = incomes * fraction * taxes
            hidden = incomes * (1.0 - fraction)
            penalty = risks * hidden * jnp.array(RISK_PENALTY_COEF, dtype=jnp.float32)
            utility = (incomes - tax_paid) - penalty

            # Fix: Safer clip for entropy
            probs = jnp.clip(fraction, 1e-4, 1 - 1e-4)
            entropy = -(probs * jnp.log(probs) + (1 - probs) * jnp.log(1 - probs))

            return -jnp.mean(utility) - jnp.array(ENTROPY_COEF, dtype=jnp.float32) * jnp.mean(
                entropy
            )

        grads = jax.grad(loss_fn)(p)
        updates, new_opt = optimizer.update(grads, opt_st, p)
        return eqx.apply_updates(p, updates), new_opt

    curr_params = params
    # Fix: Increased steps from 100 to 500 for better convergence
    for i in range(500):
        key, step_key = jax.random.split(key)
        curr_params, opt_state = train_step(curr_params, opt_state, step_key)
        if i % 100 == 0:
            print(f"    Step {i}: Training...")

    final_policy = eqx.combine(curr_params, static)

    # --- DEBUG: Verify Agent Rationality ---
    debug_agent_response(final_policy)
    # ---------------------------------------

    with io.BytesIO() as f:
        eqx.tree_serialise_leaves(f, final_policy)
        policy_bytes = f.getvalue()

    ref = store.put_bytes(
        policy_bytes,
        PutOptions(kind="demo.agent_policy", media_type="application/octet-stream"),
    )
    print(f"    Artifact Saved: {str(ref.artifact_id)[:19]}... ({len(policy_bytes)} bytes)")
    return str(ref.artifact_id)


def debug_agent_response(policy: AgentPolicy):
    """Sanity check to ensure agents actually react to tax."""
    print("\n    [DEBUG] Checking Agent Rationality Table:")
    print("    Tax Rate | Risk=0.2 (Brave) | Risk=0.8 (Cautious)")
    print("    " + "-" * 45)

    test_taxes = jnp.array([0.1, 0.3, 0.5, 0.7, 0.9])

    # Mock inputs: Income constant (High), Risk varied
    for t in test_taxes:
        # Case 1: Brave
        obs_brave = jnp.array([4.0, 0.2, t])
        resp_brave = jax.nn.sigmoid(policy(obs_brave))[0]

        # Case 2: Cautious
        obs_cautious = jnp.array([4.0, 0.8, t])
        resp_cautious = jax.nn.sigmoid(policy(obs_cautious))[0]

        print(f"    {t * 100:4.0f}%    | {resp_brave:14.3f}   | {resp_cautious:17.3f}")
    print("    " + "-" * 45 + "\n")


# --- Phase 3: Hydration Logic ---
def hydrate_system(
    program_graph: ProgramGraph, store: FileSystemCAS, *, n_agents: int, n_firms: int
) -> SystemBundle:
    mechanisms: dict[str, Mechanism] = {}
    for node in program_graph.nodes:
        if not (node.node_kind == "op" and node.op and node.op.op_kind == "apply_mechanism"):
            continue
        if node.params_ref is None:
            raise ValueError(f"apply_mechanism node '{node.node_id}' missing params_ref")

        payload = _load_json(store, node.params_ref.artifact_id)
        mech_type = payload.get("kind") or node.mechanism_type
        params = payload.get("params") or {}

        mech_spec = DEFAULT_MECHANISM_REGISTRY.mechanisms.get(mech_type)
        mech = create_mechanism_from_spec(
            mech_type,
            params,
            n_agents=n_agents,
            n_firms=n_firms,
            mechanism_spec=mech_spec,
        )
        mechanisms[node.node_id] = mech

    slot_state_path: dict[str, str] = {}
    slot_merge_code: dict[str, int] = {}
    for slot_id, slot_spec in DEFAULT_SLOT_REGISTRY.slots.items():
        state_path = slot_spec.state_path or slot_id
        rule_id = slot_spec.merge_rule.rule_id
        rule = DEFAULT_MERGE_RULE_REGISTRY.rules.get(rule_id)
        kind = rule.kind if rule is not None else MergeRuleKind.ERROR
        slot_state_path[slot_id] = state_path
        slot_merge_code[slot_id] = _merge_rule_code(kind)

    return SystemBundle(
        mechanisms=mechanisms, slot_state_path=slot_state_path, slot_merge_code=slot_merge_code
    )


# --- Phase 4: Pure Executor & VM ---
def apply_patch_pure(
    state: GlobalState, *, state_path: str, value: jnp.ndarray, rule_code: int
) -> GlobalState:
    if "." in state_path:
        scope_name, field_name = state_path.split(".", 1)
        scope_obj = getattr(state, scope_name)
        current_val = getattr(scope_obj, field_name)
    else:
        scope_name, field_name = "", state_path
        scope_obj = None
        current_val = getattr(state, field_name)

    is_sum = rule_code == 0
    is_override = rule_code == 1

    res_sum = current_val + value
    res_override = value

    temp_val = jnp.where(is_sum, res_sum, current_val)
    final_val = jnp.where(is_override, res_override, temp_val)

    if scope_obj is None:
        return state.replace(**{field_name: final_val})
    new_scope = scope_obj.replace(**{field_name: final_val})
    return state.replace(**{scope_name: new_scope})


def execute_pure(
    state: GlobalState, bundle: SystemBundle, exec_order: list[str], key: jax.Array
) -> GlobalState:
    for node_id in exec_order:
        mech = bundle.mechanisms[node_id]
        patches, key = mech.emit_patches(state, key)
        if not patches:
            continue
        for slot_id, ops in patches.items():
            state_path = bundle.slot_state_path.get(slot_id, slot_id)
            rule_code = bundle.slot_merge_code.get(slot_id, 3)
            for op in ops:
                if "delta" in op:
                    val = op["delta"]
                else:
                    val = op.get("value")
                state = apply_patch_pure(
                    state, state_path=state_path, value=val, rule_code=rule_code
                )
    return state


def main() -> None:
    print_header("POLISYOS: END-TO-END DIFFERENTIABLE MECHANISM DESIGN (IR -> Foundry -> grad)")

    tmp_dir = Path(tempfile.mkdtemp(prefix="polisyos-mech-design-"))
    os.environ["POLISYOS_CAS_ROOT"] = str(tmp_dir)
    store = FileSystemCAS(tmp_dir)
    registry_bundle = build_default_registry_bundle(store)
    key = jax.random.PRNGKey(SEED)

    # Phase 1: train + save weights
    weights_id = train_and_store_artifact(key, N_AGENTS, store)

    # Minimal context snapshot
    ctx_ref = store.put_json(
        {"schema_version": "1.0", "notes": ["demo context snapshot"]},
        PutOptions(kind="foundry.context_snapshot", media_type="application/json"),
    )

    trinity_bundle = TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="mechanism_design_problem",
            domain=ProblemDomain.FISCAL,
        ),
        policy_spec=PolicySpec(
            policy_id="mechanism_design_policy",
            interventions=[
                InterventionSpec(
                    intervention_id="smart_pop",
                    kind="adaptive_agent",
                    target=SelectorPredicate(field="entity_type", operator="==", value="agent"),
                    schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    params={
                        "observation_space": [
                            "agents.skill_level",
                            "agents.risk_aversion",
                            "global.tax_rate",
                        ],
                        "action_space": {
                            "type": "continuous",
                            "affects": "agents.reported_income",
                            "range": ["0.0", "1.0"],
                        },
                        "utility": "demo_utility",
                        "policy_model": {"type": "mlp", "hidden_layers": [64, 64]},
                        "weights_artifact": weights_id,
                        "stochastic": False,
                    },
                ),
                InterventionSpec(
                    intervention_id="tax_gov",
                    kind="income_tax",
                    target=SelectorPredicate(field="entity_type", operator="==", value="agent"),
                    schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    params={"rate": "0.10"},
                ),
            ],
        ),
        model_spec=ModelSpec(
            model_id="mechanism_design_model",
            data_snapshot_ref=str(ctx_ref.artifact_id),
            registry_bundle_ref=str(registry_bundle.bundle_ref.artifact_id),
        ),
    )

    print("\n>>> [Phase 2] Compilation (TrinityBundle -> ProgramGraph/ExecPlan)...")
    trinity_ref = store.put_json(
        trinity_bundle,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.ir.TrinityBundle", version=trinity_bundle.schema_version
            ),
        ),
    )
    compile_result = compile_foundry(
        store,
        CompileRequest(
            input_kind="trinity",
            policy_ref=trinity_ref,
            registry_bundle_ref=registry_bundle.bundle_ref,
        ),
    )
    if not compile_result.ok or compile_result.exec_plan_ref is None:
        raise RuntimeError(f"Compilation failed: {compile_result.notes}")
    program_ref = next(
        ref.ref for ref in compile_result.derived_refs if ref.role == "program_graph"
    )
    program_graph = ProgramGraph.model_validate(_load_json(store, program_ref.artifact_id))
    exec_plan = ExecPlan.model_validate(_load_json(store, compile_result.exec_plan_ref.artifact_id))

    mech_node_ids = {
        node.node_id
        for node in program_graph.nodes
        if node.node_kind == "op" and node.op and node.op.op_kind == "apply_mechanism"
    }
    exec_order = [node_id for node_id in exec_plan.order if node_id in mech_node_ids]

    print(">>> [Phase 3] Hydration (ProgramGraph -> runtime mechanisms + VM tables)...")
    bundle = hydrate_system(program_graph, store, n_agents=N_AGENTS, n_firms=1)

    print("\n>>> [Phase 4] Preparing base state...")
    base_state = GlobalState.empty(n_agents=N_AGENTS, n_firms=1)
    k1, k2 = jax.random.split(key)
    incomes = jnp.exp(jax.random.normal(k1, (N_AGENTS,)) * 0.5 + 3.0)
    base_state = base_state.replace(
        agents=base_state.agents.replace(
            income=incomes,
            skill_level=jnp.log1p(incomes),
            risk_aversion=jax.random.uniform(k2, (N_AGENTS,)),
        )
    )

    # Init mechanisms once
    init_key = jax.random.PRNGKey(999)
    for nid in exec_order:
        base_state, init_key = bundle.mechanisms[nid].init_state(base_state, init_key)

    env_key = jax.random.PRNGKey(101)
    n_agents_f = jnp.array(float(N_AGENTS), dtype=jnp.float32)

    @eqx.filter_jit
    def objective(
        tax_param: jnp.ndarray, state: GlobalState, sys_bundle: SystemBundle
    ) -> jnp.ndarray:
        # Micro-heterogeneity to prevent batch-norm singularities in AgentPolicy
        risk = state.agents.risk_aversion
        noise = jnp.array(1e-3, dtype=jnp.float32) * (risk - jnp.mean(risk))
        tax_feature = tax_param + noise
        state2 = state.replace(tax_rate=tax_feature)

        new_tax_mech = eqx.tree_at(lambda m: m.rate, sys_bundle.mechanisms["tax_gov"], tax_param)
        new_mechs = {**sys_bundle.mechanisms, "tax_gov": new_tax_mech}
        new_bundle = eqx.tree_at(lambda b: b.mechanisms, sys_bundle, new_mechs)

        final_state = execute_pure(state2, new_bundle, exec_order, env_key)
        return -final_state.government_balance / n_agents_f

    grad_fn = eqx.filter_value_and_grad(objective)

    print("\n>>> [Phase 5] Differentiable optimization loop...")
    current_tax = jnp.array(0.05, dtype=jnp.float32)
    # Fix: Reduced LR
    lr = jnp.array(0.05, dtype=jnp.float32)

    print(f"{'STEP':<5} | {'TAX':<10} | {'REVENUE':<15} | {'GRADIENT':<10}")
    print("-" * 55)

    for i in range(100):  # Increased steps slightly to see curve
        loss, grad = grad_fn(current_tax, base_state, bundle)
        loss.block_until_ready()
        revenue = (-loss) * n_agents_f
        print(
            f"{i:<5} | {float(current_tax) * 100:6.1f}%    | {float(revenue):15.2f} | {float(grad):10.4f}"
        )

        safe_grad = jnp.nan_to_num(grad, nan=0.0, posinf=0.0, neginf=0.0)

        # Fix: Gradient Normalization (instead of hard clip)
        # This keeps the direction but limits the step size safely
        grad_norm = jnp.abs(safe_grad) + 1e-6
        norm_grad = safe_grad / grad_norm
        # Apply reduced step. If gradient is huge, we just take 'lr' step.
        # If gradient is small, we take smaller step.
        effective_step = jnp.where(grad_norm > 1.0, norm_grad, safe_grad)

        current_tax = jnp.clip(current_tax - lr * effective_step, 0.0, 1.0)

        # Mild LR decay
        lr = lr * jnp.array(0.98, dtype=jnp.float32)

    print("-" * 55)
    print(f"Optimal Tax Found: {float(current_tax) * 100:.1f}%")

    if 0.30 < float(current_tax) < 0.55:
        print("✅ SUCCESS: Пик Лаффера найден (30-55%).")
    else:
        print(f"⚠️ RESULT: Оптимум {float(current_tax):.3f}. Проверьте Debug Table выше.")


if __name__ == "__main__":
    main()
