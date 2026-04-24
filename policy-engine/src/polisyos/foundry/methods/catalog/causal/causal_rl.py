"""Causal Reinforcement Learning: Off-Policy Evaluation and Causal Bandits.

Implements:
  - OffPolicyEvaluator:  IS and DR estimators for policy value evaluation
  - CausalBandit:        UCB1-based arm selection exploiting causal effect structure

References:
    Precup, D., Sutton, R.S. & Singh, S. (2000). Eligibility traces for off-policy
        policy evaluation. ICML.
    Dudík, M., Langford, J. & Li, L. (2011). Doubly robust policy evaluation and
        learning. ICML.
    Lattimore, F., Lattimore, T. & Reid, M. (2016). Causal bandits: Learning good
        interventions via causal inference. NeurIPS.
    Bareinboim, E., Forney, A. & Pearl, J. (2015). Bandits with unobserved
        confounders: A causal approach. NeurIPS.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.foundry.methods.catalog.causal._common import (
    bootstrap_ci,
    build_failure_report,
    build_success_report,
    wrap_causal_output,
)
from polisyos.foundry.methods.catalog.causal.g_computation import (
    _build_history_matrix,
    _dynamic_input_slots,
    _extract_dynamic_data,
    _fit_outcome_model,
    _ice_estimate,
)
from polisyos.foundry.methods.catalog.causal.protocols import DynamicTreatmentData
from polisyos.ir.analytics.causal import CausalMethod, EstimationStatus
from polisyos.ir.analytics.dynamic_regime import BanditResult, OPEResult

_ASSUMPTIONS_OPE = {
    "common_support": "π_target(a|s) > 0 ⟹ π_behavior(a|s) > 0 for all (a,s)",
    "positivity_behavior": "π_behavior(a|s) > 0 for all observed (a,s)",
    "consistency": "Observed Y_i = Y_i^{π_behavior} under the behavior policy",
}

_ASSUMPTIONS_BANDIT = {
    "causal_structure": (
        "A causal graph is available or interventional effects can be estimated from data"
    ),
    "no_hidden_confounders": ("Causal effects are identifiable from observational data"),
}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _compute_cumulative_is_ratios(
    A_seq: np.ndarray,
    behavior_probs: np.ndarray,
    target_probs: np.ndarray,
) -> np.ndarray:
    """Compute per-unit cumulative importance ratios.

    ρ_i = Π_t  π_target(A_{i,t}) / π_behavior(A_{i,t})

    Returns array of shape (n_units,).
    """
    n_units, n_periods = A_seq.shape
    log_ratio = np.zeros(n_units)
    for t in range(n_periods):
        pi_b = behavior_probs[:, t]
        pi_t = target_probs[:, t]
        prob_b = np.where(A_seq[:, t] == 1, pi_b, 1 - pi_b)
        prob_t = np.where(A_seq[:, t] == 1, pi_t, 1 - pi_t)
        log_ratio += np.log(np.clip(prob_t / np.clip(prob_b, 1e-8, None), 1e-8, None))
    return np.exp(np.clip(log_ratio, -20, 20))


def _kish_ess(weights: np.ndarray) -> float:
    """Kish effective sample size: (Σ w)^2 / Σ w^2."""
    w = np.clip(weights, 0, None)
    s = float(np.sum(w))
    s2 = float(np.sum(w**2))
    return float(s**2 / (s2 + 1e-12))


# ---------------------------------------------------------------------------
# OffPolicyEvaluator
# ---------------------------------------------------------------------------


@foundry_method(namespace="causal.dynamic.ope", version="1.0.0")
class OffPolicyEvaluator:
    """Off-Policy Evaluation (IS and DR) for dynamic treatment policies.

    Estimates V^π = E_π[Y] — the expected outcome under a target policy π —
    using historical data collected under a (possibly different) behavior policy π_b.

    Requires `behavior_policy_probs` in the input DynamicTreatmentData to compute
    importance ratios ρ_i = Π_t π_target(A_t|H_t) / π_behavior(A_t|H_t).

    Two estimators:
        IS (Importance Sampling):
            V̂^IS = (1/n) Σ_i ρ_i · Y_i

        DR (Doubly Robust):
            V̂^DR = (1/n) Σ_i [Q̃(H_i) + ρ_i · (Y_i - Q̃_last(H_i, A_i))]
            where Q̃ is estimated via ICE g-formula under the behavior policy.

    References:
        Precup, Sutton & Singh (2000). Eligibility traces for off-policy evaluation.
        Dudík, Langford & Li (2011). Doubly robust policy evaluation and learning. ICML.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="ope",
        namespace="",
        version="0.0.0",
        input_slots=_dynamic_input_slots()
        | frozenset(
            {
                SlotSpec(
                    "behavior_policy_probs",
                    SlotType.MATRIX,
                    Unit("probability", "conditional"),
                    shape=("n_units", "n_periods"),
                    description=(
                        "Behavior policy probabilities π_b(A_t=1|H_t) per unit per period."
                    ),
                ),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec("result", SlotType.SCALAR, Unit("report", "json")),
                SlotSpec("ope_result", SlotType.SCALAR, Unit("ope_result", "json")),
                SlotSpec("warnings", SlotType.SCALAR, Unit("warning", "list")),
            }
        ),
        parameters=(
            ParameterSpec("method", default="dr"),  # "is" or "dr"
            ParameterSpec("target_policy", default="always_treat"),
            ParameterSpec("n_bootstrap", default=200, bounds=(50, 1000)),
            ParameterSpec("confidence_level", default=0.95, bounds=(0.8, 0.99)),
            ParameterSpec("clip_weights", default=20.0, bounds=(1.0, 1000.0)),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Off-policy evaluation: estimate V^π from historical data collected "
            "under a different policy π_b. Uses IS or DR estimators."
        ),
        tags=frozenset(
            {
                "causal",
                "dynamic",
                "ope",
                "off_policy",
                "importance_sampling",
                "doubly_robust",
                "policy_evaluation",
            }
        ),
        citations=(
            "Precup, D., Sutton, R.S. & Singh, S. (2000). Eligibility traces for "
            "off-policy policy evaluation. ICML.",
            "Dudík, M., Langford, J. & Li, L. (2011). Doubly robust policy evaluation. ICML.",
        ),
        equations={
            "is": "V̂^IS = (1/n) Σ_i ρ_i · Y_i,  ρ_i = Π_t π(A_t)/π_b(A_t)",
            "dr": "V̂^DR = (1/n) Σ_i [Q̃(H_i) + ρ_i · (Y_i - Q̃_T(H_i, A_i))]",
        },
        assumptions=dict(_ASSUMPTIONS_OPE),
        when_to_use=(
            "Evaluating a treatment policy without implementing it; "
            "requires knowledge of the behavior policy that generated the data."
        ),
        when_not_to_use=(
            "When behavior policy is unknown or coverage is poor "
            "(large IS weights indicate poor coverage)."
        ),
        typical_min_obs=50,
        output_interpretation=(
            "policy_value = V̂^π — estimated mean outcome if target policy were followed. "
            "effective_sample_size < 20 indicates high variance estimate."
        ),
    )

    @staticmethod
    def pure_step(state: DynamicTreatmentData, params: Mapping[str, Any]) -> dict[str, Any]:
        try:
            data = _extract_dynamic_data(state)
        except Exception as exc:
            dummy = build_failure_report(
                method=CausalMethod.OFF_POLICY_EVALUATION,
                status=EstimationStatus.INPUT_INVALID,
                reason=str(exc),
                estimand="V^π",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions={},
            )
            return wrap_causal_output(dummy, extras={"ope_result": None})

        if data.behavior_policy_probs is None:
            dummy = build_failure_report(
                method=CausalMethod.OFF_POLICY_EVALUATION,
                status=EstimationStatus.INPUT_INVALID,
                reason=(
                    "behavior_policy_probs is required for off-policy evaluation. "
                    "Provide P(A_t=1|H_t) for each unit and time period under "
                    "the behavior policy that collected the data."
                ),
                estimand="V^π",
                sample_size=data.n_units,
                n_treated=int(np.sum(data.treatment_sequence[:, 0])),
                n_control=data.n_units - int(np.sum(data.treatment_sequence[:, 0])),
                pre_periods=data.n_periods,
                post_periods=0,
                assumptions=dict(_ASSUMPTIONS_OPE),
            )
            return wrap_causal_output(dummy, extras={"ope_result": None})

        Y = data.outcome.astype(float)
        A_seq = data.treatment_sequence.astype(float)
        L_seq = data.covariate_sequence.astype(float)
        behavior_probs = data.behavior_policy_probs.astype(float)
        n_units, n_periods = data.n_units, data.n_periods
        method = str(params.get("method", "dr"))
        target_policy = str(params.get("target_policy", "always_treat"))
        n_boot = int(params.get("n_bootstrap", 200))
        conf_level = float(params.get("confidence_level", 0.95))
        clip_w = float(params.get("clip_weights", 20.0))

        # Build target policy probabilities
        # For "always_treat": π_target(A=1|H) = 1.0 everywhere
        # For "never_treat":  π_target(A=1|H) = 0.0 everywhere
        # For a learned policy: would require fitting — use always_treat as default
        if target_policy == "always_treat":
            target_probs = np.ones((n_units, n_periods))
        elif target_policy == "never_treat":
            target_probs = np.zeros((n_units, n_periods))
        else:
            # Uniform (0.5) as placeholder for unknown target policy
            target_probs = np.full((n_units, n_periods), 0.5)

        warnings: list[str] = []

        def _ope_once(
            Y_b: np.ndarray,
            A_b: np.ndarray,
            L_b: np.ndarray,
            beh_b: np.ndarray,
            tgt_b: np.ndarray,
        ) -> float:
            rho = _compute_cumulative_is_ratios(A_b, beh_b, tgt_b)
            rho_clipped = np.clip(rho, 0, clip_w)

            if method == "is":
                return float(np.mean(rho_clipped * Y_b))

            # DR: augment with outcome model
            regime_params = {
                "regime": target_policy,
                "threshold_covariate_index": 0,
                "threshold_value": 0.0,
            }
            q_init = _ice_estimate(Y_b, A_b, L_b, regime_params)

            # Last-period outcome model residual
            H_last = _build_history_matrix(A_b, L_b, n_periods - 1)
            X_last = np.hstack([H_last, A_b[:, n_periods - 1 : n_periods]])
            q_last_model = _fit_outcome_model(X_last, Y_b)
            q_last_pred = q_last_model.predict(X_last)

            dr_scores = q_init + rho_clipped * (Y_b - q_last_pred)
            return float(np.mean(dr_scores))

        point = _ope_once(Y, A_seq, L_seq, behavior_probs, target_probs)

        rho_full = _compute_cumulative_is_ratios(A_seq, behavior_probs, target_probs)
        rho_full = np.clip(rho_full, 0, clip_w)
        ess = _kish_ess(rho_full)
        w_max = float(np.max(rho_full))

        if w_max > clip_w * 0.8:
            warnings.append(
                f"High maximum importance weight ({w_max:.1f} > {clip_w * 0.8:.1f}). "
                "Consider increasing clip_weights or using a closer behavior policy."
            )
        if ess < 10:
            warnings.append(
                f"Low effective sample size ({ess:.1f}). OPE estimates may have high variance."
            )

        rng = np.random.default_rng(42)
        boot_values = np.empty(n_boot)
        for b in range(n_boot):
            idx = rng.integers(0, n_units, size=n_units)
            boot_values[b] = _ope_once(
                Y[idx],
                A_seq[idx],
                L_seq[idx],
                behavior_probs[idx],
                target_probs[idx],
            )

        ci = bootstrap_ci(boot_values, conf_level)
        lo = min(float(ci[0]), point)
        hi = max(float(ci[1]), point)

        ope_result = OPEResult(
            method=method,  # type: ignore[arg-type]
            policy_value=point,
            confidence_interval=(lo, hi),
            effective_sample_size=ess,
            n_trajectories=n_units,
            importance_weight_max=w_max,
        )
        n_treated = int(np.sum(A_seq[:, 0]))
        report = build_success_report(
            method=CausalMethod.OFF_POLICY_EVALUATION,
            estimand=f"V^π under target_policy={target_policy} (method={method})",
            point_estimate=point,
            confidence_interval=(lo, hi),
            inference_method="bootstrap",
            sample_size=n_units,
            n_treated=n_treated,
            n_control=n_units - n_treated,
            pre_periods=n_periods,
            post_periods=0,
            assumptions=dict(_ASSUMPTIONS_OPE),
            metadata={
                "ope_method": method,
                "target_policy": target_policy,
                "ess": ess,
                "w_max": w_max,
            },
        )
        return wrap_causal_output(report, warnings=warnings, extras={"ope_result": ope_result})


# ---------------------------------------------------------------------------
# CausalBandit
# ---------------------------------------------------------------------------


@foundry_method(namespace="causal.dynamic.causal_bandit", version="1.0.0")
class CausalBandit:
    """Causal Bandit with UCB1 exploration (Lattimore et al. 2016).

    Estimates the optimal intervention arm by exploiting causal structure.
    Each arm corresponds to a binary treatment intervention do(A=a_k) at time t=0.

    Algorithm:
        For each arm k ∈ {0, 1, ..., K-1}:
            1. Estimate initial causal effect μ_k = E[Y | A_0 = arm_k]
               (observational proxy when graph is unavailable, else via do-calculus)
            2. Compute UCB: UCB_k = μ_k + sqrt(2 * log(t) / n_k)
        Over n_rounds simulated exploration rounds:
            3. Select arm k* = argmax_k UCB_k(t)
            4. Observe reward (simulated from data) and update μ_k, n_k

    When `true_optimal_arm` is provided via metadata, cumulative regret is computed.

    References:
        Lattimore, F., Lattimore, T. & Reid, M. (2016). Causal bandits: Learning
            good interventions via causal inference. NeurIPS.
        Bareinboim, E., Forney, A. & Pearl, J. (2015). Bandits with unobserved
            confounders. NeurIPS.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="causal_bandit",
        namespace="",
        version="0.0.0",
        input_slots=_dynamic_input_slots(),
        output_slots=frozenset(
            {
                SlotSpec("result", SlotType.SCALAR, Unit("report", "json")),
                SlotSpec("bandit_result", SlotType.SCALAR, Unit("bandit_result", "json")),
                SlotSpec("warnings", SlotType.SCALAR, Unit("warning", "list")),
            }
        ),
        parameters=(
            ParameterSpec("n_rounds", default=50, bounds=(10, 10000)),
            ParameterSpec("n_arms", default=2, bounds=(2, 20)),
            ParameterSpec("true_optimal_arm_index", default=-1),
            ParameterSpec("exploration_coef", default=2.0, bounds=(0.1, 10.0)),
            ParameterSpec("confidence_level", default=0.95, bounds=(0.8, 0.99)),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Causal bandit with UCB1 exploration. "
            "Selects the optimal intervention arm by combining causal effect "
            "estimates with UCB1 exploration bonuses."
        ),
        tags=frozenset(
            {
                "causal",
                "bandit",
                "ucb",
                "off_policy",
                "causal_rl",
                "exploration",
                "intervention",
            }
        ),
        citations=(
            "Lattimore, F., Lattimore, T. & Reid, M. (2016). Causal bandits. NeurIPS.",
            "Bareinboim, E., Forney, A. & Pearl, J. (2015). Bandits with unobserved "
            "confounders: A causal approach. NeurIPS.",
        ),
        equations={
            "ucb1": "UCB_k(t) = μ_k + sqrt(c · log(t) / n_k)",
            "regret": "R(T) = Σ_t [μ* − μ_{k_t}]",
        },
        assumptions=dict(_ASSUMPTIONS_BANDIT),
        when_to_use=(
            "Selecting the best treatment intervention from a small set of options "
            "when each pull is expensive and you want to minimize experimentation cost."
        ),
        when_not_to_use=(
            "Large continuous action spaces; causal graph required for full exploitation "
            "of causal structure (this implementation uses observational proxy)."
        ),
        typical_min_obs=50,
        output_interpretation=(
            "optimal_arm is the arm with highest estimated causal effect. "
            "arm_estimates contains E[Y | do(A=arm_k)] for each arm. "
            "cumulative_regret tracks exploration cost (lower = better)."
        ),
    )

    @staticmethod
    def pure_step(state: DynamicTreatmentData, params: Mapping[str, Any]) -> dict[str, Any]:
        try:
            data = _extract_dynamic_data(state)
        except Exception as exc:
            dummy = build_failure_report(
                method=CausalMethod.CAUSAL_BANDIT,
                status=EstimationStatus.INPUT_INVALID,
                reason=str(exc),
                estimand="optimal intervention arm",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions={},
            )
            return wrap_causal_output(dummy, extras={"bandit_result": None})

        Y = data.outcome.astype(float)
        A_seq = data.treatment_sequence.astype(float)
        L_seq = data.covariate_sequence.astype(float)
        n_units = data.n_units

        n_rounds = int(params.get("n_rounds", 50))
        n_arms = int(params.get("n_arms", 2))
        true_opt_idx = int(params.get("true_optimal_arm_index", -1))
        c = float(params.get("exploration_coef", 2.0))
        conf_level = float(params.get("confidence_level", 0.95))

        # Arms: 0 = never treat (A_0=0), 1 = always treat (A_0=1)
        # For n_arms > 2: split equally between 0 and 1 probabilities
        arm_labels = [str(k) for k in range(n_arms)]

        # Initial causal effect estimates for each arm via observational proxy
        # E_hat[k] = mean Y among units with A_0 == arm_action[k]
        arm_actions = np.linspace(0, 1, n_arms).round().astype(int)[:n_arms]
        if n_arms == 2:
            arm_actions = np.array([0, 1])
        arm_labels = [f"do(A_0={a})" for a in arm_actions]

        mu_hat = np.zeros(n_arms)
        for k, a_k in enumerate(arm_actions):
            mask = A_seq[:, 0] == a_k
            if mask.sum() > 0:
                mu_hat[k] = float(np.mean(Y[mask]))
            else:
                mu_hat[k] = float(np.mean(Y))

        # UCB1 simulation
        n_pulls = np.ones(n_arms)  # start with 1 pull each
        sum_rewards = mu_hat.copy() * n_pulls
        rng = np.random.default_rng(42)
        pull_seq: list[int] = []
        cumulative_regret = 0.0

        if true_opt_idx >= 0 and true_opt_idx < n_arms:
            true_opt_mu = mu_hat[true_opt_idx]
        else:
            true_opt_mu = float(np.max(mu_hat))

        for t in range(1, n_rounds + 1):
            total_pulls = float(np.sum(n_pulls))
            ucb = sum_rewards / n_pulls + np.sqrt(c * np.log(total_pulls + 1) / n_pulls)
            k_star = int(np.argmax(ucb))
            pull_seq.append(k_star)

            # Simulate reward: sample from units with matching A_0
            a_k = arm_actions[k_star]
            mask = A_seq[:, 0] == a_k
            if mask.sum() > 0:
                reward = float(Y[rng.integers(0, int(mask.sum()))])
                reward = float(Y[np.where(mask)[0][rng.integers(0, int(mask.sum()))]])
            else:
                reward = float(np.mean(Y))

            n_pulls[k_star] += 1
            sum_rewards[k_star] += reward

            # Regret
            cumulative_regret += true_opt_mu - mu_hat[k_star]

        mu_final = sum_rewards / n_pulls

        # CIs via bootstrap of observational estimates
        boot_mus = np.empty((200, n_arms))
        for b in range(200):
            idx = rng.integers(0, n_units, size=n_units)
            for k, a_k in enumerate(arm_actions):
                mask = A_seq[idx, 0] == a_k
                if mask.sum() > 0:
                    boot_mus[b, k] = float(np.mean(Y[idx][mask]))
                else:
                    boot_mus[b, k] = float(np.mean(Y[idx]))

        arm_cis = {}
        for k, label in enumerate(arm_labels):
            ci = bootstrap_ci(boot_mus[:, k], conf_level)
            arm_cis[label] = (float(ci[0]), float(ci[1]))

        arm_estimates = {label: float(mu_final[k]) for k, label in enumerate(arm_labels)}
        optimal_arm = arm_labels[int(np.argmax(mu_final))]
        pull_counts = {label: int(n_pulls[k]) for k, label in enumerate(arm_labels)}

        bandit_result = BanditResult(
            optimal_arm=optimal_arm,
            arm_estimates=arm_estimates,
            arm_cis=arm_cis,
            n_rounds=n_rounds,
            arm_pull_counts=pull_counts,
            cumulative_regret=float(cumulative_regret) if true_opt_idx >= 0 else None,
        )

        # CausalEffectReport: point estimate = effect of optimal arm vs worst arm
        best_mu = float(mu_final[np.argmax(mu_final)])
        worst_mu = float(mu_final[np.argmin(mu_final)])
        effect = best_mu - worst_mu
        best_ci = arm_cis[optimal_arm]
        worst_label = arm_labels[int(np.argmin(mu_final))]
        worst_ci = arm_cis[worst_label]
        # Conservative CI for effect
        eff_lo = float(best_ci[0]) - float(worst_ci[1])
        eff_hi = float(best_ci[1]) - float(worst_ci[0])
        eff_lo = min(eff_lo, effect)
        eff_hi = max(eff_hi, effect)

        n_treated = int(np.sum(A_seq[:, 0]))
        report = build_success_report(
            method=CausalMethod.CAUSAL_BANDIT,
            estimand=f"causal effect of {optimal_arm} vs worst arm",
            point_estimate=effect,
            confidence_interval=(eff_lo, eff_hi),
            inference_method="bootstrap",
            sample_size=n_units,
            n_treated=n_treated,
            n_control=n_units - n_treated,
            pre_periods=1,
            post_periods=0,
            assumptions=dict(_ASSUMPTIONS_BANDIT),
            metadata={
                "optimal_arm": optimal_arm,
                "n_rounds": n_rounds,
                "cumulative_regret": float(cumulative_regret) if true_opt_idx >= 0 else None,
            },
        )
        return wrap_causal_output(report, extras={"bandit_result": bandit_result})


__all__ = [
    "BanditResult",
    "CausalBandit",
    "OPEResult",
    "OffPolicyEvaluator",
]
