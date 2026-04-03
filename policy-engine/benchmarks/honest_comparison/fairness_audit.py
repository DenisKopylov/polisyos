"""Pre-run fairness audit: verify symmetric configs before Tier A/B runs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass
class AuditVerdict:
    passed: bool
    method_digests: dict[str, str]
    violations: list[str]
    manifest_json: str


def _canonical_param_count(config: dict[str, Any]) -> int:
    """Count tunable hyper-parameters (non-None values)."""
    return sum(1 for v in config.values() if v is not None)


def _digest(config: dict[str, Any]) -> str:
    raw = json.dumps(config, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def audit_fairness(
    method_configs: dict[str, dict[str, Any]],
    *,
    require_same_cv: bool = True,
    require_same_param_count: bool = True,
) -> AuditVerdict:
    """Validate that all methods in a tier share symmetric configs.

    Parameters
    ----------
    method_configs : dict mapping method_name -> config dict
    require_same_cv : if True, cv_folds must match across all methods
    require_same_param_count : if True, hyper-parameter counts must match

    Returns
    -------
    AuditVerdict with pass/fail and any violations found
    """
    violations: list[str] = []
    digests: dict[str, str] = {}

    if not method_configs:
        return AuditVerdict(True, {}, [], "{}")

    names = list(method_configs.keys())
    configs = list(method_configs.values())

    for name, cfg in method_configs.items():
        digests[name] = _digest(cfg)

    # Check CV folds
    if require_same_cv:
        cv_vals = {
            name: cfg.get("cv_folds", cfg.get("crossfit_folds"))
            for name, cfg in method_configs.items()
            if cfg.get("cv_folds") is not None or cfg.get("crossfit_folds") is not None
        }
        unique_cv = set(cv_vals.values())
        if len(unique_cv) > 1:
            violations.append(
                f"CV folds mismatch: {cv_vals}"
            )

    # Check param counts
    if require_same_param_count:
        counts = {name: _canonical_param_count(cfg) for name, cfg in method_configs.items()}
        unique_counts = set(counts.values())
        if len(unique_counts) > 1:
            # Allow tolerance of 2 (library-specific plumbing params)
            min_c, max_c = min(unique_counts), max(unique_counts)
            if max_c - min_c > 2:
                violations.append(
                    f"Hyper-parameter count spread too large ({max_c - min_c}): {counts}"
                )

    # Check bootstrap draws
    bootstrap_vals = {
        name: cfg.get("bootstrap_draws")
        for name, cfg in method_configs.items()
        if "bootstrap_draws" in cfg
    }
    if bootstrap_vals:
        unique_bs = set(bootstrap_vals.values())
        if len(unique_bs) > 1:
            violations.append(f"Bootstrap draws mismatch: {bootstrap_vals}")

    manifest = {
        "method_digests": digests,
        "violations": violations,
        "passed": len(violations) == 0,
    }

    return AuditVerdict(
        passed=len(violations) == 0,
        method_digests=digests,
        violations=violations,
        manifest_json=json.dumps(manifest, indent=2),
    )
