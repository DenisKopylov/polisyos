from __future__ import annotations

from io import BytesIO

import equinox as eqx
import jax
import jax.numpy as jnp
import optax

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.foundry.agent_metrics import (
    normalize_action,
    policy_entropy,
    risk_action_correlation,
    risk_action_gap,
    saturation_rate,
)
from polisyos.foundry.agents import (
    AdaptiveAgentMechanism,
    AgentPolicy,
    build_observations,
    continuous_actions_from_logits,
)
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.utils import gradient_health_report

OBS_SPACE = ["agents.income", "agents.risk_aversion", "policy.tax_rate"]
ACTION_SPACE = {
    "type": "continuous",
    "affects": ["agents.reported_income"],
    "range": [0.0, 1.0],
}


def _make_base_state(
    n_agents: int,
    *,
    income: float = 100.0,
    risk_aversion: jnp.ndarray | None = None,
) -> GlobalState:
    state = GlobalState.empty(n_agents=n_agents, n_firms=1)
    incomes = jnp.ones(n_agents, dtype=jnp.float32) * float(income)
    if risk_aversion is None:
        if n_agents == 1:
            risk = jnp.array([0.5], dtype=jnp.float32)
        else:
            risk = jnp.linspace(0.0, 1.0, n_agents, dtype=jnp.float32)
    else:
        risk = jnp.asarray(risk_aversion, dtype=jnp.float32)
    agents = state.agents.replace(
        income=incomes,
        reported_income=incomes,
        risk_aversion=risk,
    )
    return state.replace(agents=agents)


def _make_policy(seed: int, hidden_layers: tuple[int, ...]) -> AgentPolicy:
    key = jax.random.PRNGKey(seed)
    return AgentPolicy(
        key,
        in_dim=len(OBS_SPACE),
        action_type="continuous",
        out_dim=1,
        hidden_layers=hidden_layers,
        activation="tanh",
    )


def _policy_action(
    policy: AgentPolicy,
    base_state: GlobalState,
    *,
    tax_rate: jnp.ndarray | float,
) -> jnp.ndarray:
    obs = build_observations(
        base_state,
        OBS_SPACE,
        overrides={"tax_rate": jnp.asarray(tax_rate, dtype=jnp.float32)},
    )
    logits = policy(obs)
    return continuous_actions_from_logits(logits, ACTION_SPACE, stochastic=False)


def _tree_allclose(a, b, *, atol: float = 1e-6, rtol: float = 1e-6) -> bool:
    def _close(x, y):
        return jnp.allclose(x, y, atol=atol, rtol=rtol)

    return bool(jax.tree_util.tree_all(jax.tree_util.tree_map(_close, a, b)))


def _train_policy(
    policy: AgentPolicy,
    base_state: GlobalState,
    tax_rates: jnp.ndarray,
    *,
    steps: int,
    learning_rate: float,
    seed: int,
    risk_penalty: float = 1.0,
    entropy_beta: float = 0.0,
    saturation_epsilon: float = 1e-3,
) -> tuple[AgentPolicy, dict[str, list[float]]]:
    tax_rates = jnp.asarray(tax_rates, dtype=jnp.float32)
    if tax_rates.ndim == 0:
        tax_rates = tax_rates.reshape((1,))

    income = base_state.agents.income
    risk = base_state.agents.risk_aversion
    income_batch = jnp.broadcast_to(income, (tax_rates.shape[0],) + income.shape)
    risk_batch = jnp.broadcast_to(risk, (tax_rates.shape[0],) + risk.shape)

    policy_params, policy_static = eqx.partition(policy, eqx.is_inexact_array)
    optimizer = optax.adam(learning_rate)
    opt_state = optimizer.init(policy_params)
    key = jax.random.PRNGKey(seed)

    def _loss_fn(params, key):
        policy_eval = eqx.combine(policy_static, params)
        keys = jax.random.split(key, tax_rates.shape[0])

        def _loss_single(
            income_vec: jnp.ndarray,
            risk_vec: jnp.ndarray,
            tax_rate: jnp.ndarray,
            subkey: jax.Array,
        ):
            agents = base_state.agents.replace(
                income=income_vec,
                risk_aversion=risk_vec,
                reported_income=income_vec,
            )
            state = base_state.replace(agents=agents)
            obs = build_observations(state, OBS_SPACE, overrides={"tax_rate": tax_rate})
            logits = policy_eval(obs)
            action = continuous_actions_from_logits(
                logits,
                ACTION_SPACE,
                key=subkey,
                stochastic=False,
            )
            action_norm = normalize_action(action, ACTION_SPACE)
            reported = income_vec * action
            tax_amount = tax_rate * reported
            hidden_income = income_vec - reported
            penalty = risk_penalty * (risk_vec * hidden_income)
            reward = income_vec - tax_amount - penalty
            avg_reward = jnp.mean(reward)
            entropy = policy_entropy(action_norm)
            sat = saturation_rate(action_norm, epsilon=saturation_epsilon)
            return -(avg_reward + entropy_beta * entropy), {
                "avg_reward": avg_reward,
                "entropy": entropy,
                "saturation": sat,
                "action_mean": jnp.mean(action),
                "action_var": jnp.var(action),
            }

        losses, metrics = jax.vmap(_loss_single, in_axes=(0, 0, 0, 0))(
            income_batch, risk_batch, tax_rates, keys
        )
        loss = jnp.mean(losses)
        metrics = jax.tree_util.tree_map(lambda x: jnp.mean(x), metrics)
        return loss, metrics

    histories = {
        "reward_history": [],
        "entropy_history": [],
        "saturation_history": [],
        "action_var_history": [],
        "grad_norm_history": [],
        "grad_nan_frac_history": [],
        "grad_inf_frac_history": [],
    }

    for _ in range(steps):
        key, subkey = jax.random.split(key)
        (loss_val, aux), grads = eqx.filter_value_and_grad(_loss_fn, has_aux=True)(
            policy_params, subkey
        )
        updates, opt_state = optimizer.update(grads, opt_state, policy_params)
        policy_params = optax.apply_updates(policy_params, updates)

        health_report, _ = gradient_health_report(grads)
        histories["reward_history"].append(float(aux["avg_reward"]))
        histories["entropy_history"].append(float(aux["entropy"]))
        histories["saturation_history"].append(float(aux["saturation"]))
        histories["action_var_history"].append(float(aux["action_var"]))
        histories["grad_norm_history"].append(float(health_report.grad_norm))
        histories["grad_nan_frac_history"].append(float(health_report.nan_frac))
        histories["grad_inf_frac_history"].append(float(health_report.inf_frac))

    trained = eqx.combine(policy_static, policy_params)
    return trained, histories


def test_dummy_single_agent_learning() -> None:
    target = 0.8

    def loss_fn(w):
        return (jax.nn.sigmoid(w) - target) ** 2

    w0 = jnp.array(0.0, dtype=jnp.float32)
    grad = jax.grad(loss_fn)(w0)
    w1 = w0 - 0.5 * grad
    before = float(jax.nn.sigmoid(w0))
    after = float(jax.nn.sigmoid(w1))
    assert abs(after - target) < abs(before - target)


def test_adaptive_agent_determinism_and_serialization(tmp_path, monkeypatch) -> None:
    base_state = _make_base_state(12)
    policy_a = _make_policy(seed=0, hidden_layers=(8,))
    policy_b = _make_policy(seed=0, hidden_layers=(8,))

    trained_a, _ = _train_policy(
        policy_a,
        base_state,
        tax_rates=jnp.array(0.5, dtype=jnp.float32),
        steps=6,
        learning_rate=0.05,
        seed=0,
    )
    trained_b, _ = _train_policy(
        policy_b,
        base_state,
        tax_rates=jnp.array(0.5, dtype=jnp.float32),
        steps=6,
        learning_rate=0.05,
        seed=0,
    )

    params_a = eqx.filter(trained_a, eqx.is_inexact_array)
    params_b = eqx.filter(trained_b, eqx.is_inexact_array)
    assert _tree_allclose(params_a, params_b)

    obs = build_observations(
        base_state, OBS_SPACE, overrides={"tax_rate": jnp.array(0.5, dtype=jnp.float32)}
    )
    assert jnp.allclose(trained_a(obs), trained_b(obs))

    store = FileSystemCAS(tmp_path)
    buf = BytesIO()
    eqx.tree_serialise_leaves(buf, trained_a)
    weights_ref = store.put_bytes(
        buf.getvalue(),
        PutOptions(kind="foundry.agent_weights", media_type="application/octet-stream"),
    )

    monkeypatch.setenv("POLISYOS_CAS_ROOT", str(tmp_path))
    mech = AdaptiveAgentMechanism(
        observation_space=OBS_SPACE,
        action_space=ACTION_SPACE,
        policy_model={"hidden_layers": (8,), "activation": "tanh"},
        weights_artifact=str(weights_ref.artifact_id),
        stochastic=False,
        seed=0,
    )
    assert jnp.allclose(trained_a(obs), mech.policy(obs))


def test_adaptive_agent_behavioral_metrics_and_laffer_curve() -> None:
    base_state = _make_base_state(128)
    policy = _make_policy(seed=42, hidden_layers=(16, 16))
    tax_rates = jnp.array([0.1, 0.3, 0.5, 0.7, 0.9], dtype=jnp.float32)

    trained, metrics = _train_policy(
        policy,
        base_state,
        tax_rates=tax_rates,
        steps=60,
        learning_rate=0.05,
        seed=1,
        entropy_beta=0.01,
        saturation_epsilon=1e-3,
    )

    assert metrics["reward_history"][-1] > metrics["reward_history"][0]
    assert metrics["grad_norm_history"][0] > 0.0
    assert metrics["grad_nan_frac_history"][0] == 0.0
    assert metrics["grad_inf_frac_history"][0] == 0.0
    assert metrics["entropy_history"][1] > 0.05
    assert metrics["saturation_history"][1] < 0.9

    action_mid = _policy_action(trained, base_state, tax_rate=0.5)
    action_mid_norm = normalize_action(action_mid, ACTION_SPACE)
    corr = risk_action_correlation(base_state.agents.risk_aversion, action_mid_norm)
    gap = risk_action_gap(base_state.agents.risk_aversion, action_mid_norm)
    assert float(corr) > 0.2
    assert float(gap) > 0.2
    assert float(jnp.var(action_mid_norm)) > 1e-3

    action_low = _policy_action(trained, base_state, tax_rate=0.3)
    action_low_repeat = _policy_action(trained, base_state, tax_rate=0.3)
    action_high = _policy_action(trained, base_state, tax_rate=0.8)
    assert jnp.allclose(action_low, action_low_repeat)
    assert float(jnp.mean(action_low) - jnp.mean(action_high)) > 0.05

    def _revenue_for_rate(rate: jnp.ndarray) -> jnp.ndarray:
        action = _policy_action(trained, base_state, tax_rate=rate)
        reported = base_state.agents.income * action
        return rate * jnp.sum(reported)

    revenues = jax.vmap(_revenue_for_rate)(tax_rates)
    assert float(revenues[2]) > float(revenues[-1])
    assert float(jnp.std(revenues)) > 0.0
