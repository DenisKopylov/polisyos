"""Estimate modern staggered-adoption DiD variants with robust cohort/event-time aggregation."""

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
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


def _panel_did_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
            SlotSpec("unit_id", SlotType.VECTOR, Unit("unit", "id"), shape=("n_obs",)),
            SlotSpec("time_id", SlotType.VECTOR, Unit("time", "period"), shape=("n_obs",)),
            SlotSpec(
                "treatment_timing", SlotType.VECTOR, Unit("timing", "period"), shape=("n_units",)
            ),
        }
    )


@foundry_method(
    namespace="causal.inference.did",
    version="1.0.0",
    tags={"causal", "did", "callaway-santanna"},
)
class CallawaySantAnnaEstimator:
    """Estimate group-time ATTs under conditional parallel trends; avoid tiny cohorts with poor overlap."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="callaway_santanna",
        namespace="",
        version="0.0.0",
        input_slots=_panel_did_slots(),
        output_slots=_result_slot(),
        parameters=(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Callaway & Sant'Anna (2021) group-time ATT for staggered DiD.",
        tags=frozenset({"causal", "did", "callaway-santanna", "staggered", "heterogeneous-timing"}),
        citations=(
            "Callaway, B. & Sant'Anna, P.H.C. (2021). Difference-in-Differences with Multiple Time Periods. JoE.",
        ),
        equations={"cs_did": "ATT(g,t) = E[Y_t - Y_{g-1} | G=g] - E[Y_t - Y_{g-1} | C=1]"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Staggered treatment adoption, heterogeneous treatment timing, panel data with multiple treatment cohorts",
        when_not_to_use="Single treatment date for all units; fewer than 3 pre-treatment periods; no clean never-treated or last-treated comparison group",
        prerequisites=("causal.validation.parallel_trends_check@1.0.0",),
        diagnostic_checks=("causal.sensitivity.sensemakr@1.0.0",),
        typical_min_obs=100,
        output_interpretation="ATT(g,t): Average Treatment Effect on treated group g at time t. Aggregate ATT via weighted average. Positive = treatment increases outcome.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        Y = np.asarray(state["outcome"], dtype=float)
        uid = np.asarray(state["unit_id"])
        tid = np.asarray(state["time_id"])
        g_timing = np.asarray(state["treatment_timing"], dtype=float)

        units = np.unique(uid)
        times = np.sort(np.unique(tid))
        n_units = len(units)
        n_times = len(times)

        # Build panel
        unit_map = {u: i for i, u in enumerate(units)}
        time_map = {t: i for i, t in enumerate(times)}
        panel = np.full((n_units, n_times), np.nan)
        for k in range(len(Y)):
            i = unit_map[uid[k]]
            j = time_map[tid[k]]
            panel[i, j] = Y[k]

        # Never-treated = treatment_timing > max(times) or inf
        max_t = float(np.max(times))
        never_treated = np.where(g_timing > max_t)[0]

        # Group-time ATTs
        groups = np.unique(g_timing[g_timing <= max_t])
        gt_atts = []

        for g in groups:
            g_units = np.where(g_timing == g)[0]
            g_idx = time_map.get(g)
            if g_idx is None or g_idx == 0:
                continue
            pre_idx = g_idx - 1

            for t_idx in range(g_idx, n_times):
                t = times[t_idx]
                # ATT(g,t) = mean change for group g - mean change for never-treated
                y_g_t = panel[g_units, t_idx]
                y_g_pre = panel[g_units, pre_idx]
                y_c_t = panel[never_treated, t_idx]
                y_c_pre = panel[never_treated, pre_idx]

                valid_g = ~(np.isnan(y_g_t) | np.isnan(y_g_pre))
                valid_c = ~(np.isnan(y_c_t) | np.isnan(y_c_pre))

                if np.sum(valid_g) == 0 or np.sum(valid_c) == 0:
                    continue

                att_gt = float(
                    np.mean(y_g_t[valid_g] - y_g_pre[valid_g])
                    - np.mean(y_c_t[valid_c] - y_c_pre[valid_c])
                )
                gt_atts.append(
                    {
                        "group": float(g),
                        "time": float(t),
                        "att": att_gt,
                        "n_treated": int(np.sum(valid_g)),
                        "n_control": int(np.sum(valid_c)),
                    }
                )

        # Aggregate ATT
        if gt_atts:
            weights = np.array([r["n_treated"] for r in gt_atts], dtype=float)
            weights /= np.sum(weights)
            agg_att = float(np.sum(weights * np.array([r["att"] for r in gt_atts])))
        else:
            agg_att = 0.0

        return {
            "result": {
                "aggregate_att": agg_att,
                "group_time_atts": gt_atts,
                "n_groups": len(groups),
                "n_never_treated": len(never_treated),
                "n_units": n_units,
                "n_periods": n_times,
            }
        }


@foundry_method(
    namespace="causal.inference.did",
    version="1.0.0",
    tags={"causal", "did", "sun-abraham"},
)
class SunAbrahamEstimator:
    """Estimate interaction-weighted event-study effects that avoid TWFE contamination; avoid unsupported control structures."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="sun_abraham",
        namespace="",
        version="0.0.0",
        input_slots=_panel_did_slots(),
        output_slots=_result_slot(),
        parameters=(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Sun & Abraham (2021) interaction-weighted estimator for staggered DiD.",
        tags=frozenset({"causal", "did", "sun-abraham", "interaction-weighted", "staggered"}),
        citations=(
            "Sun, L. & Abraham, S. (2021). Estimating Dynamic Treatment Effects in Event Studies. JoE.",
        ),
        equations={"sa": "IW estimator: weight cohort-specific CATT by cohort shares"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Staggered DiD where you want event-study estimates free of contamination from other cohorts; panel data",
        when_not_to_use="Non-staggered single-treatment designs; very small cohort sizes (<10 units per cohort)",
        prerequisites=("causal.validation.parallel_trends_check@1.0.0",),
        diagnostic_checks=("causal.sensitivity.sensemakr@1.0.0",),
        typical_min_obs=100,
        output_interpretation="CATT: Cohort-Average Treatment Effects. Event-study plot shows pre-trends (should be ~0) and post-treatment dynamics.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        Y = np.asarray(state["outcome"], dtype=float)
        uid = np.asarray(state["unit_id"])
        tid = np.asarray(state["time_id"])
        g_timing = np.asarray(state["treatment_timing"], dtype=float)

        units = np.unique(uid)
        times = np.sort(np.unique(tid))
        n_units = len(units)
        n_times = len(times)

        unit_map = {u: i for i, u in enumerate(units)}
        time_map = {t: i for i, t in enumerate(times)}
        panel = np.full((n_units, n_times), np.nan)
        for k in range(len(Y)):
            panel[unit_map[uid[k]], time_map[tid[k]]] = Y[k]

        max_t = float(np.max(times))
        never_treated = np.where(g_timing > max_t)[0]
        cohorts = np.unique(g_timing[g_timing <= max_t])

        # Cohort-specific ATTs at each relative time
        relative_effects = {}
        for g in cohorts:
            g_units = np.where(g_timing == g)[0]
            g_idx = time_map.get(g)
            if g_idx is None or g_idx == 0:
                continue
            pre_idx = g_idx - 1

            for t_idx in range(n_times):
                rel_t = t_idx - g_idx  # relative time
                y_g = panel[g_units, t_idx] - panel[g_units, pre_idx]
                y_c = panel[never_treated, t_idx] - panel[never_treated, pre_idx]

                valid_g = ~np.isnan(y_g)
                valid_c = ~np.isnan(y_c)
                if np.sum(valid_g) == 0 or np.sum(valid_c) == 0:
                    continue

                catt = float(np.mean(y_g[valid_g]) - np.mean(y_c[valid_c]))
                share = len(g_units) / max(n_units - len(never_treated), 1)

                if rel_t not in relative_effects:
                    relative_effects[rel_t] = []
                relative_effects[rel_t].append({"catt": catt, "share": share, "cohort": float(g)})

        # IW aggregation per relative time
        event_study = []
        for rel_t in sorted(relative_effects.keys()):
            entries = relative_effects[rel_t]
            total_share = sum(e["share"] for e in entries)
            if total_share > 0:
                iw_effect = sum(e["catt"] * e["share"] / total_share for e in entries)
            else:
                iw_effect = 0.0
            event_study.append({"relative_time": rel_t, "effect": iw_effect})

        # Overall ATT (post-treatment)
        post = [e for e in event_study if e["relative_time"] >= 0]
        overall_att = float(np.mean([e["effect"] for e in post])) if post else 0.0

        return {
            "result": {
                "overall_att": overall_att,
                "event_study": event_study,
                "n_cohorts": len(cohorts),
                "n_units": n_units,
                "n_periods": n_times,
            }
        }


@foundry_method(
    namespace="causal.inference.did",
    version="1.0.0",
    tags={"causal", "did", "dechaisemartin"},
)
class DeChaisemartinDHaultfoeuilleEstimator:
    """Estimate heterogeneous-effect DiD contrasts with explicit weighting diagnostics; avoid sparse switcher cells."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="dechaisemartin",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec("unit_id", SlotType.VECTOR, Unit("unit", "id"), shape=("n_obs",)),
                SlotSpec("time_id", SlotType.VECTOR, Unit("time", "period"), shape=("n_obs",)),
                SlotSpec(
                    "treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="de Chaisemartin & D'Haultfoeuille (2020) estimator robust to heterogeneous effects.",
        tags=frozenset({"causal", "did", "dechaisemartin", "heterogeneous-effects", "robust"}),
        citations=(
            "de Chaisemartin, C. & D'Haultfoeuille, X. (2020). Two-Way Fixed Effects Estimators. AER.",
        ),
        equations={"dcdh": "delta_M = weighted avg of switchers' outcomes vs stable controls"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Staggered DiD with binary or multi-valued treatment; works with treatment switchers only; identifies local ATT",
        when_not_to_use="Pure never-treated comparison only; treatment with no staggered adoption; continuous treatment variable",
        prerequisites=("causal.validation.parallel_trends_check@1.0.0",),
        diagnostic_checks=("causal.sensitivity.sensemakr@1.0.0",),
        typical_min_obs=100,
        output_interpretation="DID_M: local ATT for switchers in the current period. Aggregated to overall ATT. Negative = treatment reduces outcome.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        Y = np.asarray(state["outcome"], dtype=float)
        uid = np.asarray(state["unit_id"])
        tid = np.asarray(state["time_id"])
        D = np.asarray(state["treatment"], dtype=float)

        units = np.unique(uid)
        times = np.sort(np.unique(tid))
        n_units = len(units)

        unit_map = {u: i for i, u in enumerate(units)}
        time_map = {t: i for i, t in enumerate(times)}

        Y_panel = np.full((n_units, len(times)), np.nan)
        D_panel = np.full((n_units, len(times)), np.nan)
        for k in range(len(Y)):
            i, j = unit_map[uid[k]], time_map[tid[k]]
            Y_panel[i, j] = Y[k]
            D_panel[i, j] = D[k]

        # For each period t, identify switchers (D_{t-1}=0, D_t=1) and stable controls (D_{t-1}=0, D_t=0)
        effects = []
        for t_idx in range(1, len(times)):
            switchers = []
            controls = []
            for i in range(n_units):
                if np.isnan(D_panel[i, t_idx]) or np.isnan(D_panel[i, t_idx - 1]):
                    continue
                if np.isnan(Y_panel[i, t_idx]) or np.isnan(Y_panel[i, t_idx - 1]):
                    continue
                if D_panel[i, t_idx - 1] == 0 and D_panel[i, t_idx] == 1:
                    switchers.append(i)
                elif D_panel[i, t_idx - 1] == 0 and D_panel[i, t_idx] == 0:
                    controls.append(i)

            if len(switchers) == 0 or len(controls) == 0:
                continue

            dy_switch = np.mean(Y_panel[switchers, t_idx] - Y_panel[switchers, t_idx - 1])
            dy_control = np.mean(Y_panel[controls, t_idx] - Y_panel[controls, t_idx - 1])
            effect = float(dy_switch - dy_control)
            effects.append(
                {
                    "period": float(times[t_idx]),
                    "effect": effect,
                    "n_switchers": len(switchers),
                    "n_controls": len(controls),
                }
            )

        if effects:
            weights = np.array([e["n_switchers"] for e in effects], dtype=float)
            weights /= np.sum(weights)
            delta_m = float(np.sum(weights * np.array([e["effect"] for e in effects])))
        else:
            delta_m = 0.0

        return {
            "result": {
                "delta_m": delta_m,
                "period_effects": effects,
                "n_periods_with_switchers": len(effects),
                "n_units": n_units,
            }
        }


@foundry_method(
    namespace="causal.inference.did",
    version="1.0.0",
    tags={"causal", "did", "borusyak-jaravel-spiess"},
)
class BorusyakJaravelSpiessEstimator:
    """Estimate imputation-based DiD effects under untreated-trend extrapolation; avoid weak pre-period fit."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="borusyak_jaravel_spiess",
        namespace="",
        version="0.0.0",
        input_slots=_panel_did_slots(),
        output_slots=_result_slot(),
        parameters=(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Borusyak, Jaravel & Spiess (2024) imputation estimator for staggered DiD.",
        tags=frozenset({"causal", "did", "imputation", "borusyak", "staggered"}),
        citations=(
            "Borusyak, K., Jaravel, X. & Spiess, J. (2024). Revisiting Event Study Designs. ReStud.",
        ),
        equations={
            "bjs": "Impute Y(0) for treated using untreated outcomes, then ATT = Y - Y_hat(0)"
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Staggered DiD with imputation-based approach; robust to heterogeneous treatment effects; efficient under parallel trends",
        when_not_to_use="No clean pre-treatment periods; treatment reversal; very short panels",
        prerequisites=("causal.validation.parallel_trends_check@1.0.0",),
        diagnostic_checks=("causal.sensitivity.sensemakr@1.0.0",),
        typical_min_obs=100,
        output_interpretation="Imputation-based ATT estimates. More efficient than CS DiD under homogeneous trends.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        Y = np.asarray(state["outcome"], dtype=float)
        uid = np.asarray(state["unit_id"])
        tid = np.asarray(state["time_id"])
        g_timing = np.asarray(state["treatment_timing"], dtype=float)

        units = np.unique(uid)
        times = np.sort(np.unique(tid))
        n_units = len(units)
        n_times = len(times)

        unit_map = {u: i for i, u in enumerate(units)}
        time_map = {t: i for i, t in enumerate(times)}
        panel = np.full((n_units, n_times), np.nan)
        for k in range(len(Y)):
            panel[unit_map[uid[k]], time_map[tid[k]]] = Y[k]

        max_t = float(np.max(times))

        # Treatment indicator matrix
        treated_mat = np.zeros((n_units, n_times), dtype=bool)
        for i in range(n_units):
            if g_timing[i] <= max_t:
                g_idx = time_map.get(g_timing[i])
                if g_idx is not None:
                    treated_mat[i, g_idx:] = True

        untreated_mask = ~treated_mat & ~np.isnan(panel)

        # Step 1: Estimate unit and time FE from untreated observations
        # Y_{it} = alpha_i + gamma_t + eps for untreated (i,t)
        alpha = np.zeros(n_units)
        gamma = np.zeros(n_times)

        for _ in range(50):
            # Update gamma
            for t in range(n_times):
                mask_t = untreated_mask[:, t]
                if np.any(mask_t):
                    gamma[t] = float(np.mean(panel[mask_t, t] - alpha[mask_t]))
            # Update alpha
            for i in range(n_units):
                mask_i = untreated_mask[i, :]
                if np.any(mask_i):
                    alpha[i] = float(np.mean(panel[i, mask_i] - gamma[mask_i]))

        # Step 2: Impute Y(0) for treated
        Y0_hat = alpha[:, None] + gamma[None, :]

        # Step 3: ATT = mean(Y - Y0_hat) for treated obs
        tau_it = panel - Y0_hat
        treated_obs = treated_mat & ~np.isnan(panel)
        n_treated_obs = int(np.sum(treated_obs))

        if n_treated_obs > 0:
            att = float(np.mean(tau_it[treated_obs]))
            se = float(np.std(tau_it[treated_obs]) / np.sqrt(n_treated_obs))
        else:
            att = 0.0
            se = 0.0

        return {
            "result": {
                "att": att,
                "standard_error": se,
                "n_treated_obs": n_treated_obs,
                "n_untreated_obs": int(np.sum(untreated_mask)),
                "n_units": n_units,
                "n_periods": n_times,
            }
        }


__all__ = [
    "BorusyakJaravelSpiessEstimator",
    "CallawaySantAnnaEstimator",
    "DeChaisemartinDHaultfoeuilleEstimator",
    "SunAbrahamEstimator",
]
