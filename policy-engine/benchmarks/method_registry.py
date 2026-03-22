"""Method grouping helpers for benchmark reports."""

from __future__ import annotations

import dataclasses
from typing import Iterable, Mapping


@dataclasses.dataclass(frozen=True)
class MethodDescriptor:
    name: str
    group: str
    backend: str
    label: str | None = None


BENCHMARK_ROLES = frozenset({"flagship", "production_challenger", "exploratory"})


BASELINE_METHODS = {
    "ols",
    "ipw",
    "naive",
    "t_learner",
    "t_learner_rf",
    "s_learner_linear",
}

METHOD_ALIASES = {
    "policy_os_aipw": "policy_os_aipw_cf",
    "policy_os_tmle": "policy_os_tmle_cf",
    "policy_os_drlearner": "policy_os_drlearner_cf",
    "policy_os_rlearner": "policy_os_rlearner_cf",
    "external_causal_forest_econml": "policy_os_causal_forest",
    "external_xlearner_econml": "policy_os_xlearner_cf",
}


def canonical_method_name(name: str) -> str:
    return METHOD_ALIASES.get(name, name)


def infer_method_group(name: str) -> str:
    normalized = canonical_method_name(name)
    if normalized in BASELINE_METHODS:
        return "policy_os_baseline_lightweight"
    if normalized.startswith("external_"):
        return "external_comparators"
    if normalized.startswith("policy_os_"):
        return "policy_os_competitive"
    return "policy_os_baseline_lightweight"


def infer_benchmark_role(
    name: str,
    benchmark_roles: Mapping[str, str] | None = None,
) -> str:
    normalized = canonical_method_name(name)
    overrides = dict(benchmark_roles or {})
    role = overrides.get(name, overrides.get(normalized))
    if role is not None:
        if role not in BENCHMARK_ROLES:
            raise ValueError(f"Unknown benchmark role {role!r} for method {name!r}")
        return role
    if normalized.startswith("policy_os_"):
        return "production_challenger"
    return "exploratory"


def build_method_registry(
    method_names: Iterable[str],
    *,
    benchmark_roles: Mapping[str, str] | None = None,
) -> dict[str, dict[str, str]]:
    registry: dict[str, dict[str, str]] = {}
    for name in method_names:
        normalized = canonical_method_name(name)
        group = infer_method_group(name)
        registry[name] = {
            "group": group,
            "backend": "external" if group == "external_comparators" else "policyos",
            "label": normalized,
            "canonical_name": normalized,
            "benchmark_role": infer_benchmark_role(name, benchmark_roles),
        }
    return registry


__all__ = [
    "BENCHMARK_ROLES",
    "MethodDescriptor",
    "build_method_registry",
    "canonical_method_name",
    "infer_benchmark_role",
    "infer_method_group",
]
