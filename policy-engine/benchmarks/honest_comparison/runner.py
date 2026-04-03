"""Main orchestrator for the honest head-to-head benchmark."""

from __future__ import annotations

import importlib
import json
import logging
import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from benchmarks.honest_comparison.adapters.base import EstimatorResult, safe_run, config_digest
from benchmarks.honest_comparison.config import (
    BenchmarkConfig,
    FairnessTier,
    nuisance_config_for_tier,
)
from benchmarks.honest_comparison.dgp_library import DGP_REGISTRY, DGPData
from benchmarks.honest_comparison.fairness_audit import audit_fairness
from benchmarks.honest_comparison.metrics import (
    AggregatedMetrics,
    aggregate_metrics,
    pairwise_wilcoxon,
)
from benchmarks.honest_comparison.reporting import (
    build_json_report,
    build_markdown_table,
    build_tier_comparison_table,
)

logger = logging.getLogger("honest_benchmark")


# -----------------------------------------------------------------------
# Method registry
# -----------------------------------------------------------------------

def _try_import(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False


def build_method_registry() -> list[Any]:
    """Build list of all available adapter instances."""
    methods = []

    # Baselines (always available)
    from benchmarks.honest_comparison.adapters.baseline import OLSBaseline, NaiveDiffMeans
    methods.extend([OLSBaseline(), NaiveDiffMeans()])

    # PolicyOS ATE
    try:
        from benchmarks.honest_comparison.adapters.policyos_ate import (
            PolicyOSTMLE, PolicyOSAIPW, PolicyOSIPW,
        )
        methods.extend([PolicyOSTMLE(), PolicyOSAIPW(), PolicyOSIPW()])
        logger.info("PolicyOS ATE adapters loaded")
    except ImportError as e:
        logger.warning(f"PolicyOS ATE adapters unavailable: {e}")

    # PolicyOS CATE
    try:
        from benchmarks.honest_comparison.adapters.policyos_cate import (
            PolicyOSCausalForest, PolicyOSXLearner, PolicyOSDML,
        )
        methods.extend([PolicyOSCausalForest(), PolicyOSXLearner(), PolicyOSDML()])
        logger.info("PolicyOS CATE adapters loaded")
    except ImportError as e:
        logger.warning(f"PolicyOS CATE adapters unavailable: {e}")

    # Raw EconML
    if _try_import("econml"):
        from benchmarks.honest_comparison.adapters.econml_raw import (
            RawEconMLLinearDML, RawEconMLCausalForestDML, RawEconMLXLearner,
            RawEconMLTLearner, RawEconMLForestDR, RawEconMLDRLearner,
        )
        methods.extend([
            RawEconMLLinearDML(), RawEconMLCausalForestDML(), RawEconMLXLearner(),
            RawEconMLTLearner(), RawEconMLForestDR(), RawEconMLDRLearner(),
        ])
        logger.info("EconML adapters loaded")
    else:
        logger.warning("econml not installed — skipping EconML adapters")

    # Raw zepid
    if _try_import("zepid"):
        from benchmarks.honest_comparison.adapters.zepid_raw import (
            RawZepidTMLE, RawZepidIPTW, RawZepidAIPTW,
        )
        methods.extend([RawZepidTMLE(), RawZepidIPTW(), RawZepidAIPTW()])
        logger.info("zepid adapters loaded")
    else:
        logger.warning("zepid not installed — skipping zepid adapters")

    # Raw DoWhy
    if _try_import("dowhy"):
        from benchmarks.honest_comparison.adapters.dowhy_raw import (
            RawDoWhyLinear, RawDoWhyIPW,
        )
        methods.extend([RawDoWhyLinear(), RawDoWhyIPW()])
        logger.info("DoWhy adapters loaded")
    else:
        logger.warning("dowhy not installed — skipping DoWhy adapters")

    # Raw CausalML (optional)
    if _try_import("causalml"):
        from benchmarks.honest_comparison.adapters.causalml_raw import (
            RawCausalMLXLearner, RawCausalMLTLearner,
        )
        methods.extend([RawCausalMLXLearner(), RawCausalMLTLearner()])
        logger.info("CausalML adapters loaded")

    # Raw stochtree (optional)
    if _try_import("stochtree"):
        from benchmarks.honest_comparison.adapters.stochtree_raw import RawBCF
        methods.append(RawBCF())
        logger.info("stochtree BCF adapter loaded")

    logger.info(f"Total methods registered: {len(methods)}")
    return methods


# -----------------------------------------------------------------------
# Environment snapshot
# -----------------------------------------------------------------------

def environment_snapshot() -> dict[str, Any]:
    """Capture hardware/software snapshot for reproducibility."""
    snap = {
        "python_version": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "machine": platform.machine(),
    }

    # Package versions
    for pkg in ["econml", "dowhy", "zepid", "causalml", "stochtree",
                "sklearn", "lightgbm", "numpy", "scipy", "pandas"]:
        try:
            mod = importlib.import_module(pkg)
            snap[f"{pkg}_version"] = getattr(mod, "__version__", "unknown")
        except ImportError:
            snap[f"{pkg}_version"] = "not_installed"

    # Try to get CPU/memory info on Linux
    try:
        import os
        with open("/proc/cpuinfo") as f:
            cpuinfo = f.read()
        snap["cpu_model"] = [l.split(":")[1].strip() for l in cpuinfo.split("\n") if "model name" in l][0]
        snap["cpu_count"] = os.cpu_count()
        with open("/proc/meminfo") as f:
            meminfo = f.read()
        snap["total_memory_gb"] = int([l.split()[1] for l in meminfo.split("\n") if "MemTotal" in l][0]) / 1024 / 1024
    except Exception:
        import os
        snap["cpu_count"] = os.cpu_count()

    return snap


# -----------------------------------------------------------------------
# Main run
# -----------------------------------------------------------------------

def run_benchmark(cfg: BenchmarkConfig, output_path: Path | None = None) -> dict[str, Any]:
    """Execute the full benchmark."""
    logger.info("=== Honest Head-to-Head Benchmark ===")
    logger.info(f"Config: smoke={cfg.smoke}, tiers={[t.value for t in cfg.effective_tiers()]}")

    env_snap = environment_snapshot()
    logger.info(f"Python: {env_snap['python_version']}")

    methods = build_method_registry()
    if not methods:
        raise RuntimeError("No methods available!")

    all_metrics: dict[str, list[AggregatedMetrics]] = {}
    all_pairwise: dict[str, list] = {}
    fairness_manifests: dict[str, str] = {}

    for tier in cfg.effective_tiers():
        tier_key = tier.value
        logger.info(f"\n--- Tier {tier_key} ---")
        shared_config = nuisance_config_for_tier(tier)

        # Fairness audit for Tier A/B
        if shared_config is not None:
            method_configs = {}
            for m in methods:
                method_configs[m.name] = dict(shared_config)
            audit = audit_fairness(method_configs)
            fairness_manifests[tier_key] = audit.manifest_json
            if not audit.passed:
                logger.error(f"Fairness audit FAILED for Tier {tier_key}: {audit.violations}")
                continue
            logger.info(f"Fairness audit passed for Tier {tier_key}")

        tier_metrics: list[AggregatedMetrics] = []

        for dgp_name, dgp_fn in DGP_REGISTRY.items():
            for n in cfg.effective_sample_sizes():
                logger.info(f"  DGP={dgp_name}, n={n}, K={cfg.effective_k(dgp_name)}")
                K = cfg.effective_k(dgp_name)

                # Pre-generate all datasets for this DGP+n
                datasets: list[DGPData] = []
                for k in range(K):
                    rng = np.random.default_rng(cfg.base_seed + k)
                    datasets.append(dgp_fn(n, rng))

                for method in methods:
                    method_results: list[EstimatorResult] = []
                    true_cates: list[np.ndarray | None] = []

                    for k, data in enumerate(datasets):
                        config = dict(shared_config) if shared_config else {}
                        result = safe_run(
                            method.fit_predict,
                            data.X, data.T, data.Y,
                            config, seed=cfg.base_seed + k,
                            timeout_s=cfg.timeout_per_method_s,
                        )
                        method_results.append(result)
                        true_cates.append(data.true_cate)

                    agg = aggregate_metrics(
                        method_name=method.name,
                        dataset_name=f"{dgp_name}_n{n}",
                        tier=tier_key,
                        true_ate=datasets[0].true_ate,
                        results=method_results,
                        true_cates=true_cates if method.supports_cate() else None,
                        n_bootstrap=cfg.bootstrap_metric_resamples,
                        seed=cfg.base_seed,
                    )
                    tier_metrics.append(agg)

                    status = "OK" if agg.failure_rate < 1.0 else "ALL_FAILED"
                    logger.info(
                        f"    {method.name}: RMSE={agg.ate_rmse:.4f}, "
                        f"Cov={agg.ci_coverage:.3f}, "
                        f"Time={agg.wall_time_mean:.2f}s [{status}]"
                    )

        # Pairwise tests per dataset
        dataset_names = {m.dataset_name for m in tier_metrics}
        tier_pairwise = []
        for ds in dataset_names:
            ds_metrics = [m for m in tier_metrics if m.dataset_name == ds]
            tier_pairwise.extend(pairwise_wilcoxon(ds_metrics))

        all_metrics[tier_key] = tier_metrics
        all_pairwise[tier_key] = tier_pairwise

    # Build report
    json_report = build_json_report(all_metrics, all_pairwise, fairness_manifests, env_snap)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_report)
        logger.info(f"JSON report saved to {output_path}")

        # Markdown report
        md_path = output_path.with_suffix(".md")
        md_lines = ["# Honest Head-to-Head Benchmark Results\n"]
        for tier_key, metrics_list in all_metrics.items():
            dataset_names = sorted({m.dataset_name for m in metrics_list})
            for ds in dataset_names:
                md_lines.append(build_markdown_table(metrics_list, tier_key, ds))

        if len(all_metrics) > 1:
            md_lines.append("\n# Tier Comparison\n")
            all_ds = sorted({m.dataset_name for ml in all_metrics.values() for m in ml})
            for ds in all_ds:
                md_lines.append(build_tier_comparison_table(all_metrics, ds))

        md_path.write_text("\n".join(md_lines))
        logger.info(f"Markdown report saved to {md_path}")

    logger.info("=== Benchmark complete ===")
    return {"metrics": all_metrics, "pairwise": all_pairwise, "env": env_snap}
