"""Independent scalar oracles for the real PPO loss, gradients, and GAE targets."""

from __future__ import annotations

import inspect
import math
import struct
from types import CodeType, FunctionType

import equinox as eqx
import jax
import jax.numpy as jnp
import pytest

from polisyos.foundry.agent_sim.actor_critic import ActorCritic
from polisyos.foundry.agent_sim.rl import Trajectory, compute_returns_and_advantages, ppo_loss

_RTOL = 5e-6
_ATOL = 2e-6
_ACTIONS = (1.0, -1.0)


@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
def test_categorical_ppo_preserves_rank_two_action_coordinates(compiled: bool) -> None:
    """The actual categorical consumer accepts T != N without a synthetic action axis."""
    actor = ActorCritic(
        jax.random.PRNGKey(5), obs_dim=1, hidden_dims=(4, 4), action_dim=2, action_type="discrete"
    )
    actor = jax.tree_util.tree_map(
        lambda x: jnp.zeros_like(x) if eqx.is_inexact_array(x) else x, actor
    )
    observations = jnp.zeros((2, 3, 1), dtype=jnp.float32)
    shape = (2, 3)
    trajectory = Trajectory(
        observations=observations,
        actions=jnp.asarray([[0, 1, 0], [1, 0, 1]], dtype=jnp.int32),
        rewards=jnp.zeros(shape),
        values=jnp.zeros(shape),
        dones=jnp.zeros(shape, dtype=jnp.bool_),
        log_probs=jnp.full(shape, -math.log(2.0), dtype=jnp.float32),
        final_observation=observations[-1],
        active_mask=jnp.ones(shape, dtype=jnp.bool_),
    )
    advantages = jnp.asarray([[1.0, -1.0, 1.0], [-1.0, 1.0, -1.0]])

    def loss_for(candidate):
        return ppo_loss(
            candidate,
            trajectory,
            advantages,
            jnp.zeros(shape),
            trajectory.log_probs,
            value_coef=0.0,
            entropy_coef=0.0,
        )

    evaluate = eqx.filter_value_and_grad(loss_for, has_aux=True)
    if compiled:
        evaluate = eqx.filter_jit(evaluate)
    (loss, metrics), gradients = evaluate(actor)
    assert float(loss) == pytest.approx(0.0, abs=1e-6)
    assert float(metrics["entropy"]) == pytest.approx(math.log(2.0), rel=1e-6)
    assert all(
        bool(jnp.all(jnp.isfinite(x)))
        for x in jax.tree_util.tree_leaves(gradients)
        if eqx.is_inexact_array(x)
    )


def _float32(value: float) -> float:
    """Round a reference input to its stored float32 value without product math."""
    return struct.unpack("f", struct.pack("f", value))[0]


def _normal_log_density(action: float, mean: float = 0.0) -> float:
    return -0.5 * ((action - mean) ** 2 + math.log(2.0 * math.pi))


def _old_log_probs(ratios: tuple[float, float]) -> tuple[float, float]:
    return tuple(
        _float32(_normal_log_density(action) - math.log(ratio))
        for action, ratio in zip(_ACTIONS, ratios, strict=True)
    )


def _zero_actor() -> ActorCritic:
    actor = ActorCritic(
        jax.random.PRNGKey(0),
        obs_dim=1,
        hidden_dims=(2,),
        action_dim=1,
        action_type="continuous",
    )
    return jax.tree_util.tree_map(
        lambda leaf: jnp.zeros_like(leaf, dtype=jnp.float32)
        if eqx.is_inexact_array(leaf)
        else leaf,
        actor,
    )


def _with_coordinates(
    actor: ActorCritic,
    *,
    mean: jax.Array,
    value: jax.Array,
    log_std: jax.Array,
) -> ActorCritic:
    return eqx.tree_at(
        lambda model: (model.actor_out.bias, model.critic_out.bias, model.action_log_std),
        actor,
        tuple(jnp.reshape(coordinate, (1,)) for coordinate in (mean, value, log_std)),
    )


def _trajectory(old_log_probs: tuple[float, float]) -> Trajectory:
    observations = jnp.zeros((1, 2, 1), dtype=jnp.float32)
    return Trajectory(
        observations=observations,
        actions=jnp.asarray([[[1.0], [-1.0]]], dtype=jnp.float32),
        rewards=jnp.zeros((1, 2), dtype=jnp.float32),
        values=jnp.zeros((1, 2), dtype=jnp.float32),
        dones=jnp.zeros((1, 2), dtype=jnp.bool_),
        log_probs=jnp.asarray([old_log_probs], dtype=jnp.float32),
        final_observation=observations[-1],
        active_mask=jnp.ones((1, 2), dtype=jnp.bool_),
    )


def _policy_reference(
    old_log_probs: tuple[float, float], *, clipped: bool = True
) -> tuple[float, float]:
    """Differentiate the scalar clipped surrogate using Python math only."""
    normalizer = _float32(1.0 + _float32(1e-8))
    advantages = (1.0 / normalizer, -1.0 / normalizer)
    loss = 0.0
    mean_gradient = 0.0
    epsilon = _float32(0.2)
    for action, advantage, old_log_prob in zip(_ACTIONS, advantages, old_log_probs, strict=True):
        ratio = math.exp(_normal_log_density(action) - old_log_prob)
        bounded_ratio = min(max(ratio, 1.0 - epsilon), 1.0 + epsilon) if clipped else ratio
        raw = ratio * advantage
        bounded = bounded_ratio * advantage
        loss -= min(raw, bounded) / 2.0
        # d log Normal(action; mean, 1) / d mean = action at mean=0.
        if raw <= bounded:
            mean_gradient -= ratio * advantage * action / 2.0
    return loss, mean_gradient


@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
@pytest.mark.parametrize(
    "ratios,ideal_loss,ideal_gradient",
    [((1.3, 0.7), -0.2, 0.0), ((0.9, 1.1), 0.1, -1.0), ((0.7, 1.3), 0.3, -1.0)],
    ids=["both-clipped", "both-interior", "opposite-tails-unclipped"],
)
def test_real_ppo_actor_bias_matches_independent_clipped_surrogate(
    compiled: bool,
    ratios: tuple[float, float],
    ideal_loss: float,
    ideal_gradient: float,
) -> None:
    """Exercise both advantage signs in all three distinct clipping regimes."""
    actor = _zero_actor()
    old_log_probs = _old_log_probs(ratios)
    trajectory = _trajectory(old_log_probs)
    zero = jnp.asarray(0.0, dtype=jnp.float32)

    def loss_at_mean(mean: jax.Array) -> tuple[jax.Array, dict[str, jax.Array]]:
        return ppo_loss(
            _with_coordinates(actor, mean=mean, value=zero, log_std=zero),
            trajectory,
            jnp.asarray([[1.0, -1.0]], dtype=jnp.float32),
            jnp.zeros((1, 2), dtype=jnp.float32),
            trajectory.log_probs,
            clip_epsilon=jnp.asarray(0.2, dtype=jnp.float32),
            value_coef=zero,
            entropy_coef=zero,
        )

    evaluate = jax.value_and_grad(loss_at_mean, has_aux=True)
    if compiled:
        evaluate = jax.jit(evaluate)
    (loss, metrics), gradient = evaluate(zero)
    expected_loss, expected_gradient = _policy_reference(old_log_probs)
    assert expected_loss == pytest.approx(ideal_loss, rel=_RTOL, abs=_ATOL)
    assert expected_gradient == pytest.approx(ideal_gradient, rel=_RTOL, abs=_ATOL)
    assert loss.dtype == gradient.dtype == jnp.float32
    assert float(loss) == pytest.approx(expected_loss, rel=_RTOL, abs=_ATOL)
    assert float(metrics["policy_loss"]) == pytest.approx(expected_loss, rel=_RTOL, abs=_ATOL)
    assert float(gradient) == pytest.approx(expected_gradient, rel=_RTOL, abs=_ATOL)
    assert float(metrics["value_loss"]) == 0.0

    # Named divergent controls: reversing the objective sign fails every loss
    # oracle; removing clipping fails both loss and gradient in the first pair.
    assert not math.isclose(float(loss), -expected_loss, rel_tol=_RTOL, abs_tol=_ATOL)
    if ratios == (1.3, 0.7):
        unclipped_loss, unclipped_gradient = _policy_reference(old_log_probs, clipped=False)
        assert unclipped_loss == pytest.approx(-0.3, rel=_RTOL, abs=_ATOL)
        assert unclipped_gradient == pytest.approx(-1.0, rel=_RTOL, abs=_ATOL)
        assert not math.isclose(float(loss), unclipped_loss, rel_tol=_RTOL, abs_tol=_ATOL)
        assert not math.isclose(float(gradient), unclipped_gradient, rel_tol=_RTOL, abs_tol=_ATOL)


@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
@pytest.mark.parametrize(
    "value_coef,entropy_coef",
    [(0.5, 0.0), (0.25, 0.0), (0.0, 0.1), (0.0, 0.2), (0.5, 0.1), (0.25, 0.2)],
)
def test_real_ppo_critic_bias_and_log_std_match_independent_components(
    compiled: bool, value_coef: float, entropy_coef: float
) -> None:
    """Check reported components, total, and both real output-field derivatives."""
    actor = _zero_actor()
    trajectory = _trajectory(_old_log_probs((1.0, 1.0)))
    zero = jnp.asarray(0.0, dtype=jnp.float32)
    value_coefficient = jnp.asarray(value_coef, dtype=jnp.float32)
    entropy_coefficient = jnp.asarray(entropy_coef, dtype=jnp.float32)

    def loss_at_coordinates(
        value: jax.Array, log_std: jax.Array
    ) -> tuple[jax.Array, dict[str, jax.Array]]:
        return ppo_loss(
            _with_coordinates(actor, mean=zero, value=value, log_std=log_std),
            trajectory,
            jnp.zeros((1, 2), dtype=jnp.float32),
            jnp.asarray([[1.0, 3.0]], dtype=jnp.float32),
            trajectory.log_probs,
            clip_epsilon=jnp.asarray(0.2, dtype=jnp.float32),
            value_coef=value_coefficient,
            entropy_coef=entropy_coefficient,
        )

    evaluate = jax.value_and_grad(loss_at_coordinates, argnums=(0, 1), has_aux=True)
    if compiled:
        evaluate = jax.jit(evaluate)
    (loss, metrics), (value_gradient, log_std_gradient) = evaluate(zero, zero)
    cv, ce = _float32(value_coef), _float32(entropy_coef)
    entropy = 0.5 * (1.0 + math.log(2.0 * math.pi))
    expected_loss = 5.0 * cv - ce * entropy
    assert loss.dtype == value_gradient.dtype == log_std_gradient.dtype == jnp.float32
    assert float(metrics["policy_loss"]) == 0.0
    assert float(metrics["value_loss"]) == pytest.approx(5.0, rel=_RTOL, abs=_ATOL)
    assert float(metrics["entropy"]) == pytest.approx(entropy, rel=_RTOL, abs=_ATOL)
    assert float(loss) == pytest.approx(expected_loss, rel=_RTOL, abs=_ATOL)
    assert float(value_gradient) == pytest.approx(-4.0 * cv, rel=_RTOL, abs=_ATOL)
    assert float(log_std_gradient) == pytest.approx(-ce, rel=_RTOL, abs=_ATOL)

    # Each nonzero component has a distinguishing removal and sign control.
    if cv:
        assert not math.isclose(float(loss), -ce * entropy, rel_tol=_RTOL, abs_tol=_ATOL)
        assert not math.isclose(float(value_gradient), 4.0 * cv, rel_tol=_RTOL, abs_tol=_ATOL)
    if ce:
        assert not math.isclose(float(loss), 5.0 * cv, rel_tol=_RTOL, abs_tol=_ATOL)
        assert not math.isclose(float(log_std_gradient), ce, rel_tol=_RTOL, abs_tol=_ATOL)


def _isolated_loss_mutant(before: str, after: str) -> FunctionType:
    """Compile exactly one expression change in the actual current loss owner."""
    source = inspect.getsource(ppo_loss)
    assert source.count(before) == 1, "the mutation must identify exactly one owner expression"
    compiled = compile(source.replace(before, after, 1), "<isolated-ppo-loss-mutant>", "exec")
    code = next(
        constant
        for constant in compiled.co_consts
        if isinstance(constant, CodeType) and constant.co_name == ppo_loss.__name__
    )
    mutant = FunctionType(code, ppo_loss.__globals__, ppo_loss.__name__, ppo_loss.__defaults__)
    mutant.__kwdefaults__ = dict(ppo_loss.__kwdefaults__ or {})
    return mutant


@pytest.mark.parametrize(
    "mutation",
    [
        "objective-sign",
        "remove-clipping",
        "remove-value",
        "reverse-value",
        "remove-entropy",
        "reverse-entropy",
    ],
)
def test_independent_scalar_oracle_rejects_executable_loss_owner_mutation(
    monkeypatch, mutation: str
) -> None:
    """Each altered real owner must fail the same oracle that accepts its baseline."""
    replacements = {
        "objective-sign": ("policy_loss = -jnp.minimum(", "policy_loss = jnp.minimum("),
        "remove-clipping": (
            "clipped_ratio = jnp.clip(ratio, 1.0 - clip_epsilon, 1.0 + clip_epsilon)",
            "clipped_ratio = ratio",
        ),
        "remove-value": (" + value_coef * value_loss", " + 0.0 * value_loss"),
        "reverse-value": (" + value_coef * value_loss", " - value_coef * value_loss"),
        "remove-entropy": (" - entropy_coef * entropy_term", " - 0.0 * entropy_term"),
        "reverse-entropy": (" - entropy_coef * entropy_term", " + entropy_coef * entropy_term"),
    }
    if mutation in ("objective-sign", "remove-clipping"):
        oracle = test_real_ppo_actor_bias_matches_independent_clipped_surrogate
        arguments = (False, (1.3, 0.7), -0.2, 0.0)
    else:
        oracle = test_real_ppo_critic_bias_and_log_std_match_independent_components
        arguments = (False, 0.5, 0.1)
    original = ppo_loss
    oracle(*arguments)
    mutant = _isolated_loss_mutant(*replacements[mutation])
    with monkeypatch.context() as isolated:
        isolated.setitem(globals(), "ppo_loss", mutant)
        with pytest.raises(AssertionError):
            oracle(*arguments)
    assert ppo_loss is original


@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
@pytest.mark.parametrize(
    "dones,expected_returns,expected_advantages",
    [
        ((False, False), (2.25, 2.5), (2.0, 2.0)),
        ((False, True), (2.0, 2.0), (1.75, 1.5)),
        ((True, True), (1.0, 2.0), (0.75, 1.5)),
    ],
    ids=["bootstrap", "last-terminal", "both-terminal"],
)
def test_real_gae_matches_fixed_bootstrap_and_terminal_targets(
    compiled: bool,
    dones: tuple[bool, bool],
    expected_returns: tuple[float, float],
    expected_advantages: tuple[float, float],
) -> None:
    """A terminal cuts both bootstrapping and the recursive advantage carry."""
    observations = jnp.zeros((2, 1, 1), dtype=jnp.float32)
    trajectory = Trajectory(
        observations=observations,
        actions=jnp.zeros((2, 1, 1), dtype=jnp.float32),
        rewards=jnp.asarray([[1.0], [2.0]], dtype=jnp.float32),
        values=jnp.asarray([[0.25], [0.5]], dtype=jnp.float32),
        dones=jnp.asarray(dones, dtype=jnp.bool_).reshape(2, 1),
        log_probs=jnp.zeros((2, 1), dtype=jnp.float32),
        final_observation=observations[-1],
        active_mask=jnp.ones((2, 1), dtype=jnp.bool_),
    )

    def targets(current: Trajectory) -> tuple[jax.Array, jax.Array]:
        return compute_returns_and_advantages(
            current,
            jnp.asarray([1.0], dtype=jnp.float32),
            gamma=jnp.asarray(0.5, dtype=jnp.float32),
            gae_lambda=jnp.asarray(1.0, dtype=jnp.float32),
        )

    evaluate = jax.jit(targets) if compiled else targets
    returns, advantages = evaluate(trajectory)
    assert returns.dtype == advantages.dtype == jnp.float32
    assert returns.shape == advantages.shape == (2, 1)
    assert [float(value) for value in returns[:, 0]] == pytest.approx(
        expected_returns, rel=1e-6, abs=1e-6
    )
    assert [float(value) for value in advantages[:, 0]] == pytest.approx(
        expected_advantages, rel=1e-6, abs=1e-6
    )
