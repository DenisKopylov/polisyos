"""Public causal gcm query module API."""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, ClassVar

import numpy as np

from polisyos.core.observability import DeterminismTier
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
from polisyos.foundry.methods.catalog.causal.protocols import SCMQueryData
from polisyos.ir.analytics.causal_queries import (
    CausalEstimatorInterval,
    CausalQuery,
    CausalQueryResult,
    CausalResultKind,
    InterventionSpec,
    InterventionType,
    QueryType,
)
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    NodeMechanism,
    StructuralCausalModelSpec,
)


def _append_warning(warnings: list[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)


def _parents_by_node(scm_spec: StructuralCausalModelSpec) -> dict[str, list[str]]:
    parents: dict[str, list[str]] = {node: [] for node in scm_spec.graph.nodes}
    for edge in scm_spec.graph.edges:
        if edge.lag not in (None, 0):
            continue
        parents.setdefault(edge.dst, []).append(edge.src)
    return parents


def _children_by_node(scm_spec: StructuralCausalModelSpec) -> dict[str, list[str]]:
    children: dict[str, list[str]] = {node: [] for node in scm_spec.graph.nodes}
    for edge in scm_spec.graph.edges:
        if edge.lag not in (None, 0):
            continue
        children.setdefault(edge.src, []).append(edge.dst)
    return children


def _descendants_of_treatment(
    scm_spec: StructuralCausalModelSpec,
    treatment_variable: str,
) -> set[str]:
    children = _children_by_node(scm_spec)
    visited: set[str] = set()
    queue: deque[str] = deque([treatment_variable])
    while queue:
        node = queue.popleft()
        for child in children.get(node, []):
            if child in visited:
                continue
            visited.add(child)
            queue.append(child)
    return visited


def _ancestors_for_targets(
    parents_map: Mapping[str, list[str]],
    targets: Sequence[str],
    *,
    stop_nodes: set[str] | frozenset[str] = frozenset(),
) -> set[str]:
    """Return the graph-surgery closure needed for the requested targets.

    A node in ``stop_nodes`` is retained as an active target, but its natural
    parents are not traversed.  This models a perfect action replacing the
    node's mechanism while retaining any other factual ancestors that feed the
    requested outcome.
    """
    active: set[str] = set()
    pending = list(targets)
    while pending:
        node = pending.pop()
        if node in active or node not in parents_map:
            continue
        active.add(node)
        if node not in stop_nodes:
            pending.extend(parents_map.get(node, ()))
    return active


def _topological_order(scm_spec: StructuralCausalModelSpec) -> list[str]:
    if any(edge.lag not in (None, 0) for edge in scm_spec.graph.edges):
        raise ValueError(
            "gcm_query is a static consumer; temporal edges require a temporal "
            "query/finite expansion before sampling"
        )

    nodes = list(scm_spec.graph.nodes)
    indegree: dict[str, int] = dict.fromkeys(nodes, 0)
    adjacency: dict[str, list[str]] = {node: [] for node in nodes}

    for edge in scm_spec.graph.edges:
        if edge.lag not in (None, 0):
            continue
        adjacency[edge.src].append(edge.dst)
        indegree[edge.dst] += 1

    queue: deque[str] = deque(sorted(node for node, deg in indegree.items() if deg == 0))
    order: list[str] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for nxt in adjacency[node]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)

    if len(order) != len(nodes):
        raise ValueError("SCM graph must be acyclic for gcm_query execution")
    return order


def _mechanism_map(scm_spec: StructuralCausalModelSpec) -> dict[str, NodeMechanism]:
    return {item.variable: item for item in scm_spec.mechanisms}


def _linear_predict(
    mechanism: NodeMechanism,
    parent_values: Mapping[str, float],
) -> float:
    params = mechanism.family_params
    if "posterior_mean" in params and isinstance(params["posterior_mean"], Mapping):
        posterior = params["posterior_mean"]
        intercept = float(posterior.get("__intercept__", 0.0))
        contribution = sum(
            float(posterior.get(parent, 0.0)) * parent_values[parent]
            for parent in mechanism.parents
        )
        return intercept + contribution

    intercept = float(params.get("intercept", 0.0))
    coefficients = params.get("coefficients")
    if not isinstance(coefficients, Mapping):
        coefficients = {}
    contribution = sum(
        float(coefficients.get(parent, 0.0)) * parent_values[parent] for parent in mechanism.parents
    )
    return intercept + contribution


def _polynomial_predict(
    mechanism: NodeMechanism,
    parent_values: Mapping[str, float],
) -> float | None:
    """Evaluate the simple stored polynomial payload, when it is complete.

    ``HybridSCMFit``/legacy payloads use a per-parent power expansion without
    cross terms.  A payload is only treated as polynomial when it explicitly
    declares ``fit_mode=additive_noise_poly``; otherwise the historical linear
    parameters remain the intentional fallback for that mechanism family.
    """
    params = mechanism.family_params
    if params.get("fit_mode") != "additive_noise_poly":
        return None
    raw_coefficients = params.get("poly_coefficients")
    if not isinstance(raw_coefficients, Mapping):
        return None
    try:
        raw_degree = params.get("poly_degree")
        if isinstance(raw_degree, bool) or not isinstance(raw_degree, (int, float)):
            return None
        degree_value = float(raw_degree)
        if not math.isfinite(degree_value) or not degree_value.is_integer():
            return None
        degree = int(degree_value)
        if degree < 1:
            return None
        required_keys = {"__intercept__"}
        required_keys.update(
            f"{parent}^{power}" for parent in mechanism.parents for power in range(1, degree + 1)
        )
        if not required_keys.issubset(raw_coefficients):
            return None
        value = float(raw_coefficients["__intercept__"])
        for parent in mechanism.parents:
            parent_value = float(parent_values[parent])
            for power in range(1, degree + 1):
                value += float(raw_coefficients[f"{parent}^{power}"]) * (parent_value**power)
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    return value if math.isfinite(value) else None


def _mechanism_predict(
    mechanism: NodeMechanism,
    parent_values: Mapping[str, float],
) -> float:
    """Evaluate the declared deterministic part of a supported mechanism."""
    if mechanism.family is MechanismFamily.ADDITIVE_NOISE:
        polynomial = _polynomial_predict(mechanism, parent_values)
        if polynomial is not None:
            return polynomial
        if mechanism.family_params.get("fit_mode") == "additive_noise_poly":
            raise ValueError(
                f"invalid additive_noise polynomial payload for node '{mechanism.variable}'"
            )
    return _linear_predict(mechanism, parent_values)


def _observed_root_samples(
    mechanisms: Mapping[str, NodeMechanism],
) -> dict[str, Sequence[float]]:
    """Return aligned empirical root rows carried by fitted mechanisms."""
    samples: dict[str, Sequence[float]] = {}
    for variable, mechanism in mechanisms.items():
        if mechanism.parents or mechanism.family is not MechanismFamily.EMPIRICAL:
            continue
        raw_samples = mechanism.family_params.get("observed_samples")
        if not isinstance(raw_samples, Sequence) or isinstance(raw_samples, (str, bytes)):
            continue
        if raw_samples and all(isinstance(value, (int, float)) for value in raw_samples):
            samples[variable] = raw_samples
    return samples


def _joint_root_sample_index(
    observed_samples: Mapping[str, Sequence[float]],
    rng: np.random.Generator,
) -> int | None:
    lengths = [len(values) for values in observed_samples.values() if values]
    if not lengths:
        return None
    if len(set(lengths)) != 1:
        raise ValueError("joint empirical roots require a common aligned row set")
    return int(rng.integers(lengths[0]))


def _linear_noise_std(mechanism: NodeMechanism) -> float:
    params = mechanism.family_params
    try:
        std = float(params.get("noise_std", 0.0))
    except (TypeError, ValueError, ArithmeticError):
        return 0.0
    if not math.isfinite(std) or std < 0.0:
        return 0.0
    return std


@dataclass(frozen=True)
class _StochasticDistribution:
    """Validated stochastic law reused by every sample in one query arm."""

    name: str
    args: tuple[float, ...]


@dataclass(frozen=True)
class _LogicalStreamFactory:
    """Derive deterministic, query-local streams from one root entropy value.

    A single mutable generator makes an active-graph optimization observable:
    pruning an irrelevant node changes every subsequent draw.  The query uses
    stable labels for each logical source instead, so a node's samples depend
    on the query seed, arm, and node, not on the set/order of unrelated nodes.
    """

    root_entropy: tuple[int, ...]

    @classmethod
    def from_seed(cls, seed: int) -> _LogicalStreamFactory:
        return cls(root_entropy=(int(seed),))

    @classmethod
    def from_generator(cls, rng: np.random.Generator) -> _LogicalStreamFactory:
        # Consume a fixed-size root token from an explicit generator.  This
        # preserves the caller's explicit RNG as the entropy source while
        # keeping later draws independent of active-node pruning.
        entropy = rng.integers(0, 2**63, size=4, dtype=np.uint64)
        return cls(root_entropy=tuple(int(value) for value in entropy))

    def generator(self, *, namespace: str, label: str) -> np.random.Generator:
        material = json.dumps(
            {
                "version": 1,
                "root_entropy": self.root_entropy,
                "namespace": namespace,
                "label": label,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        digest = hashlib.blake2b(material, digest_size=16).digest()
        words = [
            int.from_bytes(digest[offset : offset + 4], "little")
            for offset in range(0, len(digest), 4)
        ]
        return np.random.default_rng(np.random.SeedSequence(words))


def _resolve_stochastic_distribution(distribution: str) -> _StochasticDistribution:
    """Parse and validate a stochastic law before Monte Carlo sampling."""
    if not isinstance(distribution, str):
        raise ValueError(f"unsupported stochastic distribution: {distribution!r}")
    text = distribution.strip()
    match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\(([^)]*)\)", text)
    if match is None:
        raise ValueError(f"unsupported stochastic distribution format: {distribution!r}")
    name = match.group(1).lower()
    raw_args = [item.strip() for item in match.group(2).split(",")]
    if any(not item for item in raw_args):
        raise ValueError(f"stochastic distribution has an empty argument: {distribution!r}")
    try:
        args = tuple(float(item) for item in raw_args)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"stochastic distribution has non-numeric arguments: {distribution!r}"
        ) from exc
    if not all(math.isfinite(value) for value in args):
        raise ValueError(f"stochastic distribution arguments must be finite: {distribution!r}")

    expected_arity = {"normal": 2, "uniform": 2, "truncnorm": 4}.get(name)
    if expected_arity is None or len(args) != expected_arity:
        raise ValueError(f"unsupported stochastic distribution: {distribution!r}")
    if name == "normal" and args[1] <= 0.0:
        raise ValueError("normal stochastic distribution requires positive scale")
    if name == "truncnorm" and args[1] <= 0.0:
        raise ValueError("truncnorm stochastic distribution requires positive scale")
    return _StochasticDistribution(name=name, args=args)


def _sample_stochastic_distribution(
    *,
    distribution: str | _StochasticDistribution,
    rng: np.random.Generator,
) -> float:
    law = (
        distribution
        if isinstance(distribution, _StochasticDistribution)
        else _resolve_stochastic_distribution(distribution)
    )
    if law.name == "normal":
        mean, std = law.args
        return float(rng.normal(loc=mean, scale=std))
    if law.name == "uniform":
        lo, hi = sorted(law.args)
        return float(rng.uniform(low=lo, high=hi))
    if law.name == "truncnorm":
        mean, std, lo, hi = law.args
        lo, hi = sorted((lo, hi))
        if lo == hi:
            return lo
        try:
            from scipy.stats import truncnorm
        except ImportError as exc:
            raise ValueError("truncnorm stochastic intervention requires scipy") from exc
        sample = float(
            truncnorm.rvs(
                (lo - mean) / std,
                (hi - mean) / std,
                loc=mean,
                scale=std,
                random_state=rng,
            )
        )
        if not math.isfinite(sample):
            raise ValueError("truncnorm sampler returned a non-finite value")
        if sample <= lo:
            return float(np.nextafter(lo, hi))
        if sample >= hi:
            return float(np.nextafter(hi, lo))
        return sample
    raise AssertionError(f"unreachable stochastic distribution {law.name!r}")


def _apply_intervention(
    *,
    current_value: float,
    intervention_spec: InterventionSpec,
    fallback_treatment_value: float | None,
    rng: np.random.Generator,
    warnings: list[str],
    stochastic_law: _StochasticDistribution | None = None,
) -> float:
    if intervention_spec.type is InterventionType.ATOMIC:
        value = intervention_spec.value
        if value is None:
            value = fallback_treatment_value
        if value is None:
            raise ValueError("atomic intervention requires treatment_value")
        return float(value)

    if intervention_spec.type is InterventionType.SHIFTED:
        if intervention_spec.shift is None:
            raise ValueError("shifted intervention requires shift")
        return float(current_value + intervention_spec.shift)

    if intervention_spec.type is InterventionType.TRUNCATED:
        if intervention_spec.bounds is None:
            raise ValueError("truncated intervention requires bounds")
        lo, hi = intervention_spec.bounds
        return float(np.clip(current_value, lo, hi))

    if intervention_spec.type is InterventionType.STOCHASTIC:
        if not intervention_spec.distribution:
            raise ValueError("stochastic intervention requires distribution")
        try:
            return _sample_stochastic_distribution(
                distribution=stochastic_law or intervention_spec.distribution,
                rng=rng,
            )
        except (ImportError, TypeError, ValueError) as exc:
            raise ValueError(f"stochastic intervention law is invalid: {exc}") from exc

    raise ValueError(f"unsupported intervention type: {intervention_spec.type.value}")


def _sample_node_value(
    *,
    mechanism: NodeMechanism | None,
    parent_values: Mapping[str, float],
    rng: np.random.Generator,
    warnings: list[str],
    linear_noise_override: float | None = None,
    sample_index: int | None = None,
    observed_root_samples: Mapping[str, Sequence[float]] | None = None,
    allow_declared_hypothesis: bool = False,
) -> float:
    if mechanism is None:
        if not allow_declared_hypothesis:
            raise ValueError(
                "missing mechanism for node; provide a fitted root carrier or explicitly "
                "enable the declared root hypothesis"
            )
        _append_warning(
            warnings,
            "missing mechanism for node; using a declared hypothesis only "
            "(standard normal root sampler is not a fitted law)",
        )
        return float(rng.normal())

    if mechanism.family is MechanismFamily.LINEAR:
        mean = _linear_predict(mechanism, parent_values)
        if linear_noise_override is not None:
            return float(mean + linear_noise_override)
        residual_samples = mechanism.family_params.get("residual_samples")
        if residual_samples is not None:
            residuals = np.asarray(residual_samples, dtype=float)
            if residuals.ndim != 1 or len(residuals) < 1 or not np.isfinite(residuals).all():
                raise ValueError("empirical structural residuals must be a non-empty finite vector")
            return float(mean + rng.choice(residuals))
        std = _linear_noise_std(mechanism)
        if std <= 0.0:
            return float(mean)
        return float(mean + rng.normal(scale=std))

    if mechanism.family is MechanismFamily.EMPIRICAL:
        if (
            sample_index is not None
            and observed_root_samples is not None
            and mechanism.variable in observed_root_samples
            and observed_root_samples[mechanism.variable]
        ):
            values = observed_root_samples[mechanism.variable]
            if not 0 <= sample_index < len(values):
                raise ValueError("joint root row index is outside its aligned source rows")
            return float(values[sample_index])
        mean = float(mechanism.family_params.get("mean", 0.0))
        std = float(mechanism.family_params.get("std", 1.0))
        if not math.isfinite(mean):
            mean = 0.0
        if not math.isfinite(std) or std < 0.0:
            std = 1.0
        if std <= 0.0:
            return mean
        return float(rng.normal(loc=mean, scale=std))

    if mechanism.family is MechanismFamily.PARAMETRIC_PRIOR:
        prior = mechanism.family_params.get("prior")
        if isinstance(prior, Mapping):
            intercept_spec = prior.get("__intercept__", {})
            if not isinstance(intercept_spec, Mapping):
                intercept_spec = {}
            intercept = float(intercept_spec.get("mean", 0.0))
            value = intercept
            for parent in mechanism.parents:
                stats = prior.get(parent, {})
                if not isinstance(stats, Mapping):
                    stats = {}
                coef = float(stats.get("mean", 0.0))
                value += coef * parent_values[parent]
            std = float(mechanism.family_params.get("noise_std", 0.2))
            std = std if math.isfinite(std) and std > 0.0 else 0.2
            return float(rng.normal(loc=value, scale=std))
        mean = float(mechanism.family_params.get("mean", 0.0))
        std = float(mechanism.family_params.get("std", 1.0))
        std = std if math.isfinite(std) and std > 0.0 else 1.0
        return float(rng.normal(loc=mean, scale=std))

    if mechanism.family is MechanismFamily.ADDITIVE_NOISE:
        polynomial = _polynomial_predict(mechanism, parent_values)
        if polynomial is not None:
            if linear_noise_override is not None:
                return float(polynomial + linear_noise_override)
            std = _linear_noise_std(mechanism)
            return float(polynomial + rng.normal(scale=std)) if std > 0.0 else float(polynomial)
        if mechanism.family_params.get("fit_mode") == "additive_noise_poly":
            raise ValueError(
                f"invalid additive_noise polynomial payload for node '{mechanism.variable}'"
            )
        _append_warning(
            warnings,
            "mechanism family 'additive_noise' lacks a valid polynomial payload; "
            "using its explicit linear surrogate",
        )
        return _sample_node_value(
            mechanism=mechanism.model_copy(update={"family": MechanismFamily.LINEAR}),
            parent_values=parent_values,
            rng=rng,
            warnings=warnings,
            linear_noise_override=linear_noise_override,
            sample_index=sample_index,
            observed_root_samples=observed_root_samples,
            allow_declared_hypothesis=allow_declared_hypothesis,
        )

    if mechanism.family in {
        MechanismFamily.POST_NONLINEAR,
        MechanismFamily.CLASSIFIER,
    }:
        _append_warning(
            warnings,
            (
                f"mechanism family '{mechanism.family.value}' "
                "not fully supported in phase11; using linear/empirical fallback"
            ),
        )
        if mechanism.parents:
            return _sample_node_value(
                mechanism=mechanism.model_copy(update={"family": MechanismFamily.LINEAR}),
                parent_values=parent_values,
                rng=rng,
                warnings=warnings,
                linear_noise_override=linear_noise_override,
                sample_index=sample_index,
                observed_root_samples=observed_root_samples,
                allow_declared_hypothesis=allow_declared_hypothesis,
            )
        return _sample_node_value(
            mechanism=mechanism.model_copy(update={"family": MechanismFamily.EMPIRICAL}),
            parent_values=parent_values,
            rng=rng,
            warnings=warnings,
            linear_noise_override=linear_noise_override,
            sample_index=sample_index,
            observed_root_samples=observed_root_samples,
            allow_declared_hypothesis=allow_declared_hypothesis,
        )

    raise ValueError(f"unsupported mechanism family: {mechanism.family.value}")


def _abduce_linear_noises(
    *,
    query: CausalQuery,
    order: list[str],
    parents_map: Mapping[str, list[str]],
    mechanisms: Mapping[str, NodeMechanism],
) -> dict[str, float]:
    if not query.condition:
        return {}

    pseudo_observed: dict[str, float] = {}
    noise: dict[str, float] = {}
    for node in order:
        if node in query.condition:
            pseudo_observed[node] = float(query.condition[node])
        else:
            mechanism = mechanisms.get(node)
            if mechanism is None:
                pseudo_observed[node] = 0.0
            elif mechanism.family in {
                MechanismFamily.LINEAR,
                MechanismFamily.ADDITIVE_NOISE,
            } and all(parent in pseudo_observed for parent in parents_map.get(node, [])):
                parent_values = {p: pseudo_observed[p] for p in parents_map.get(node, [])}
                pseudo_observed[node] = _mechanism_predict(mechanism, parent_values)
            else:
                pseudo_observed[node] = 0.0

        mechanism = mechanisms.get(node)
        if (
            mechanism is not None
            and mechanism.family
            in {
                MechanismFamily.LINEAR,
                MechanismFamily.ADDITIVE_NOISE,
            }
            and node in query.condition
            and all(parent in pseudo_observed for parent in parents_map.get(node, []))
        ):
            parent_values = {p: pseudo_observed[p] for p in parents_map.get(node, [])}
            mean = _mechanism_predict(mechanism, parent_values)
            noise[node] = float(query.condition[node] - mean)
    return noise


def _abduce_noises_unified(
    *,
    condition: Mapping[str, float],
    order: list[str],
    parents_map: Mapping[str, list[str]],
    mechanisms: Mapping[str, NodeMechanism],
    warnings: list[str],
) -> dict[str, float]:
    """Abduct exogenous noise values from a factual observation.

    Extends :func:`_abduce_linear_noises` to handle additional mechanism families:

    - ``LINEAR``: exact closed-form residual U = Y − f(pa_Y)
    - ``ADDITIVE_NOISE``: same as LINEAR since f is stored as linear params
    - ``PARAMETRIC_PRIOR``: approximate, uses prior-mean linear prediction
    - ``EMPIRICAL``, ``POST_NONLINEAR``, ``CLASSIFIER``: skip (U = 0), emit warning

    Parameters
    ----------
    condition:
        Observed variable values {node: value} (the factual world).
    order:
        Topological order of all SCM nodes.
    parents_map:
        {node: [parent, ...]} mapping.
    mechanisms:
        {node: NodeMechanism} mapping.
    warnings:
        Mutable list; abduction warnings are appended here.

    Returns
    -------
    dict[str, float]
        Abducted noise values {node: U_node}.
    """
    if not condition:
        return {}

    pseudo_observed: dict[str, float] = {}
    noise: dict[str, float] = {}

    for node in order:
        # Pin observed nodes directly
        if node in condition:
            pseudo_observed[node] = float(condition[node])
        else:
            mechanism = mechanisms.get(node)
            if mechanism is None:
                pseudo_observed[node] = 0.0
            elif mechanism.family in (
                MechanismFamily.LINEAR,
                MechanismFamily.ADDITIVE_NOISE,
            ) and all(parent in pseudo_observed for parent in parents_map.get(node, [])):
                parent_values = {p: pseudo_observed[p] for p in parents_map.get(node, [])}
                pseudo_observed[node] = _mechanism_predict(mechanism, parent_values)
            elif mechanism.family is MechanismFamily.PARAMETRIC_PRIOR and all(
                parent in pseudo_observed for parent in parents_map.get(node, [])
            ):
                # Approximate: use prior-mean linear prediction
                prior = mechanism.family_params.get("prior")
                if isinstance(prior, Mapping):
                    intercept = float(prior.get("__intercept__", {}).get("mean", 0.0))
                    val = intercept
                    for parent in parents_map.get(node, []):
                        stats = prior.get(parent, {})
                        val += float(stats.get("mean", 0.0)) * pseudo_observed[parent]
                    pseudo_observed[node] = val
                else:
                    pseudo_observed[node] = float(mechanism.family_params.get("mean", 0.0))
            else:
                pseudo_observed[node] = 0.0

        # Abduct noise for observed nodes where we can compute it
        mechanism = mechanisms.get(node)
        if mechanism is None or node not in condition:
            continue
        all_parents_known = all(parent in pseudo_observed for parent in parents_map.get(node, []))
        if not all_parents_known:
            continue

        parent_values = {p: pseudo_observed[p] for p in parents_map.get(node, [])}

        if mechanism.family in (MechanismFamily.LINEAR, MechanismFamily.ADDITIVE_NOISE):
            mean = _mechanism_predict(mechanism, parent_values)
            noise[node] = float(condition[node]) - mean

        elif mechanism.family is MechanismFamily.PARAMETRIC_PRIOR:
            # Approximate abduction via prior-mean linear prediction
            prior = mechanism.family_params.get("prior")
            if isinstance(prior, Mapping):
                intercept = float(prior.get("__intercept__", {}).get("mean", 0.0))
                val = intercept
                for parent in parents_map.get(node, []):
                    stats = prior.get(parent, {})
                    val += float(stats.get("mean", 0.0)) * parent_values[parent]
                noise[node] = float(condition[node]) - val
            else:
                mean_val = float(mechanism.family_params.get("mean", 0.0))
                noise[node] = float(condition[node]) - mean_val

        else:
            # EMPIRICAL, POST_NONLINEAR, CLASSIFIER: cannot abduct analytically
            _append_warning(
                warnings,
                (
                    f"cannot abduct noise for node '{node}' "
                    f"with family '{mechanism.family.value}'; "
                    "treating as U=0 (factual condition ignored for this node)"
                ),
            )

    return noise


@dataclass(frozen=True)
class _LinearGaussianPosterior:
    """Conditional distribution of exogenous noises for a linear SCM."""

    node_order: tuple[str, ...]
    mean: np.ndarray
    covariance: np.ndarray


@dataclass(frozen=True)
class _AbductionDiagnostic:
    """Typed provenance and eligibility for one factual-abduction attempt."""

    profile: str
    observed_nodes: tuple[str, ...] = ()
    noise_nodes: tuple[str, ...] = ()
    gate_eligible: bool = True
    limitation: str | None = None

    def with_noise_nodes(
        self,
        noise_nodes: Mapping[str, float] | Sequence[str],
    ) -> _AbductionDiagnostic:
        """Return this diagnostic with the noises actually supplied to prediction."""
        names = tuple(noise_nodes) if not isinstance(noise_nodes, Mapping) else tuple(noise_nodes)
        return _AbductionDiagnostic(
            profile=self.profile,
            observed_nodes=self.observed_nodes,
            noise_nodes=tuple(sorted(names)),
            gate_eligible=self.gate_eligible,
            limitation=self.limitation,
        )

    def as_metadata(self) -> dict[str, Any]:
        """Expose provenance without changing the persisted DTO schema."""
        metadata: dict[str, Any] = {
            "abduction_profile": self.profile,
            "abduction_observed_nodes": list(self.observed_nodes),
            "abduction_noise_nodes": list(self.noise_nodes),
            "abduction_gate_eligible": self.gate_eligible,
        }
        if self.limitation is not None:
            metadata["abduction_limitation"] = self.limitation
        return metadata


def _fallback_residual_is_exact(
    *,
    condition: Mapping[str, float],
    order: list[str],
    parents_map: Mapping[str, list[str]],
    mechanisms: Mapping[str, NodeMechanism],
    treatment_variable: str,
    allow_observed_empirical_roots: bool = True,
) -> bool:
    """Check whether legacy fallback only uses directly observed residual inputs."""
    observed = set(condition).intersection(order)
    for node in order:
        if node not in observed or node == treatment_variable:
            continue
        mechanism = mechanisms.get(node)
        if mechanism is None:
            return False
        if mechanism.family in {
            MechanismFamily.LINEAR,
            MechanismFamily.ADDITIVE_NOISE,
        }:
            if not set(parents_map.get(node, ())).issubset(observed):
                return False
            continue
        if (
            allow_observed_empirical_roots
            and mechanism.family is MechanismFamily.EMPIRICAL
            and not mechanism.parents
        ):
            continue
        return False
    return True


def _prepare_linear_gaussian_abduction(
    *,
    condition: Mapping[str, float],
    order: list[str],
    parents_map: Mapping[str, list[str]],
    mechanisms: Mapping[str, NodeMechanism],
    treatment_variable: str,
    allow_observed_empirical_roots: bool = True,
) -> tuple[_LinearGaussianPosterior | None, _AbductionDiagnostic]:
    """Select supported posterior, exact residual, or limited fallback explicitly."""
    observed_nodes = tuple(node for node in order if node in condition)
    if not observed_nodes:
        return None, _AbductionDiagnostic(profile="not_requested")

    posterior = _linear_gaussian_posterior(
        condition=condition,
        order=order,
        parents_map=parents_map,
        mechanisms=mechanisms,
    )
    if posterior is not None:
        return posterior, _AbductionDiagnostic(
            profile="linear_gaussian_posterior",
            observed_nodes=observed_nodes,
            noise_nodes=posterior.node_order,
        )

    if _fallback_residual_is_exact(
        condition=condition,
        order=order,
        parents_map=parents_map,
        mechanisms=mechanisms,
        treatment_variable=treatment_variable,
        allow_observed_empirical_roots=allow_observed_empirical_roots,
    ):
        return None, _AbductionDiagnostic(
            profile="exact_residual_fallback",
            observed_nodes=observed_nodes,
        )

    observed_empirical_roots = tuple(
        node
        for node in observed_nodes
        if (
            mechanisms.get(node) is not None
            and mechanisms[node].family is MechanismFamily.EMPIRICAL
            and not mechanisms[node].parents
        )
    )
    if not allow_observed_empirical_roots and observed_empirical_roots:
        limitation = (
            "twin prediction cannot pin observed empirical root values; "
            f"the factual root condition is not applied for {list(observed_empirical_roots)}"
        )
    else:
        limitation = (
            "linear-Gaussian posterior unavailable for partial factual evidence; "
            "legacy abduction uses model-imputed inputs and is not gate eligible"
        )
    profile = (
        "limited_unpinned_empirical_root"
        if not allow_observed_empirical_roots and observed_empirical_roots
        else "limited_imputed_fallback"
    )
    return None, _AbductionDiagnostic(
        profile=profile,
        observed_nodes=observed_nodes,
        gate_eligible=False,
        limitation=limitation,
    )


def _linear_gaussian_posterior(
    *,
    condition: Mapping[str, float],
    order: list[str],
    parents_map: Mapping[str, list[str]],
    mechanisms: Mapping[str, NodeMechanism],
) -> _LinearGaussianPosterior | None:
    """Build ``P(U | observed nodes)`` for a supported linear-Gaussian SCM.

    Each node is represented as an affine function of independent structural
    noises.  Conditioning the observed rows of that affine system avoids
    treating an unobserved parent as if its prior mean were factual evidence.
    ``None`` means that the model is outside this deliberately small supported
    posterior profile; callers may retain the legacy fallback only as an
    explicitly limited, non-gate-eligible result when it imputes evidence.
    """
    if not condition or not order:
        return None

    node_count = len(order)
    node_index = {node: index for index, node in enumerate(order)}
    intercepts = np.zeros(node_count, dtype=float)
    affine = np.zeros((node_count, node_count), dtype=float)
    variances = np.zeros(node_count, dtype=float)

    for node in order:
        mechanism = mechanisms.get(node)
        if mechanism is None or mechanism.family not in {
            MechanismFamily.LINEAR,
            MechanismFamily.ADDITIVE_NOISE,
        }:
            return None
        if mechanism.family_params.get("fit_mode") == "additive_noise_poly":
            return None

        params = mechanism.family_params
        if "residual_samples" in params:
            return None  # An empirical residual law is not a Gaussian posterior.
        raw_posterior = params.get("posterior_mean")
        if raw_posterior is not None and not isinstance(raw_posterior, Mapping):
            return None
        coefficients = (
            raw_posterior if isinstance(raw_posterior, Mapping) else params.get("coefficients", {})
        )
        if not isinstance(coefficients, Mapping):
            coefficients = {}
        try:
            intercept = float(coefficients.get("__intercept__", params.get("intercept", 0.0)))
            for parent in parents_map.get(node, []):
                if parent not in node_index:
                    return None
                coefficient = float(coefficients.get(parent, 0.0))
                parent_index = node_index[parent]
                intercept += coefficient * intercepts[parent_index]
                affine[node_index[node]] += coefficient * affine[parent_index]
            std = _linear_noise_std(mechanism)
        except (TypeError, ValueError, OverflowError):
            return None
        if not math.isfinite(intercept) or not math.isfinite(std):
            return None
        intercepts[node_index[node]] = intercept
        affine[node_index[node], node_index[node]] += 1.0
        variances[node_index[node]] = std**2

    observed_nodes = [node for node in order if node in condition]
    if not observed_nodes:
        return None
    observed_indices = [node_index[node] for node in observed_nodes]
    observation_matrix = affine[observed_indices, :]
    prior_covariance = np.diag(variances)
    residual = np.asarray(
        [float(condition[node]) - intercepts[node_index[node]] for node in observed_nodes],
        dtype=float,
    )
    if not np.isfinite(residual).all():
        return None

    observation_covariance = observation_matrix @ prior_covariance @ observation_matrix.T
    try:
        observation_pseudoinverse = np.linalg.pinv(observation_covariance, hermitian=True)
    except (TypeError, ValueError, np.linalg.LinAlgError):
        return None

    projected_residual = observation_covariance @ observation_pseudoinverse @ residual
    if not np.allclose(projected_residual, residual, atol=1.0e-8, rtol=1.0e-8):
        raise ValueError("factual evidence is incompatible with the singular Gaussian SCM")

    gain = prior_covariance @ observation_matrix.T @ observation_pseudoinverse
    posterior_mean = gain @ residual
    posterior_covariance = prior_covariance - gain @ observation_matrix @ prior_covariance
    posterior_covariance = (posterior_covariance + posterior_covariance.T) / 2.0
    try:
        eigenvalues, eigenvectors = np.linalg.eigh(posterior_covariance)
    except np.linalg.LinAlgError:
        return None
    if np.any(eigenvalues < -1.0e-8):
        return None
    posterior_covariance = eigenvectors @ np.diag(np.clip(eigenvalues, 0.0, None)) @ eigenvectors.T
    if not np.isfinite(posterior_mean).all() or not np.isfinite(posterior_covariance).all():
        return None
    return _LinearGaussianPosterior(
        node_order=tuple(order),
        mean=posterior_mean,
        covariance=posterior_covariance,
    )


def _draw_linear_gaussian_noises(
    posterior: _LinearGaussianPosterior,
    rng: np.random.Generator,
) -> dict[str, float]:
    """Draw one jointly conditioned structural-noise realization."""
    if np.allclose(posterior.covariance, 0.0, atol=1.0e-12, rtol=0.0):
        draw = posterior.mean
    else:
        draw = rng.multivariate_normal(
            posterior.mean,
            posterior.covariance,
            check_valid="raise",
        )
    return {node: float(value) for node, value in zip(posterior.node_order, draw, strict=True)}


_INTERVENTION_UNSET = object()


def _effective_intervention(query: CausalQuery) -> InterventionSpec | None:
    if query.intervention_spec is not None:
        return query.intervention_spec
    if query.query_type is QueryType.ATTRIBUTION and query.contrast is not None:
        return query.contrast.target
    if query.query_type in {QueryType.INTERVENTIONAL, QueryType.COUNTERFACTUAL}:
        return InterventionSpec(type=InterventionType.ATOMIC, value=query.treatment_value)
    if query.query_type is QueryType.ATTRIBUTION and query.treatment_value is not None:
        return InterventionSpec(type=InterventionType.ATOMIC, value=query.treatment_value)
    return None


def _attribution_comparator(query: CausalQuery) -> InterventionSpec | None:
    """Return the explicit comparator intervention, or natural observation."""
    if query.contrast is None or query.contrast.comparator.kind == "observational":
        return None
    return query.contrast.comparator.intervention


def _linear_intervention_mean(
    scm_spec: StructuralCausalModelSpec,
    query: CausalQuery,
    intervention: InterventionSpec | None,
) -> float:
    """Evaluate the exact fixed linear/empirical model expectation after surgery."""
    if intervention is not None and (
        intervention.type is not InterventionType.ATOMIC or intervention.value is None
    ):
        raise ValueError("refit bootstrap supports explicit atomic intervention means only")
    mechanisms = _mechanism_map(scm_spec)
    values: dict[str, float] = {}
    for node in _topological_order(scm_spec):
        if node == query.treatment_variable and intervention is not None:
            values[node] = float(intervention.value)
            continue
        mechanism = mechanisms[node]
        if mechanism.family is MechanismFamily.EMPIRICAL and not mechanism.parents:
            values[node] = float(np.mean(mechanism.family_params["observed_samples"]))
        elif mechanism.family is MechanismFamily.LINEAR:
            values[node] = _linear_predict(mechanism, values) + float(
                np.mean(mechanism.family_params["residual_samples"])
            )
        else:
            raise ValueError(
                "refit bootstrap supports declared empirical/linear GCM mechanisms only"
            )
    return values[query.outcome_variable]


def _refit_target_estimate(scm_spec: StructuralCausalModelSpec, query: CausalQuery) -> float:
    if query.condition or query.query_type not in {QueryType.INTERVENTIONAL, QueryType.ATTRIBUTION}:
        raise ValueError(
            "iid refit bootstrap does not establish conditional individual counterfactual inference"
        )
    target = _linear_intervention_mean(scm_spec, query, _effective_intervention(query))
    if query.query_type is QueryType.ATTRIBUTION:
        target -= _linear_intervention_mean(scm_spec, query, _attribution_comparator(query))
    return target


def _refit_interval_from_models(
    scm_spec: StructuralCausalModelSpec,
    query: CausalQuery,
    *,
    seed: int,
    confidence_level: float,
    indices: list[list[int]],
    base: StructuralCausalModelSpec,
    refits: Sequence[StructuralCausalModelSpec],
) -> CausalEstimatorInterval:
    training = scm_spec.training_rows
    if training is None or base.fit_provenance is None:
        raise ValueError("refit interval requires source-bound GCM training rows")
    if base.graph != scm_spec.graph or base.mechanisms != scm_spec.mechanisms:
        raise ValueError("consumed GCM mechanisms differ from the actual source-row refit")
    estimates = tuple(_refit_target_estimate(model, query) for model in refits)
    point = _refit_target_estimate(base, query)
    bounds = _percentile_ci(np.asarray(estimates), confidence_level=confidence_level)

    def digest(value: Any) -> str:
        return hashlib.sha256(
            json.dumps(
                value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
            ).encode()
        ).hexdigest()

    return CausalEstimatorInterval(
        confidence_level=confidence_level,
        point_estimate=point,
        interval=bounds,
        source_artifact_id=str(training.source_ref.artifact_id),
        source_sha256=training.source_sha256,
        data_sha256=training.data_sha256,
        row_sha256=training.row_sha256,
        graph_sha256=training.graph_sha256,
        resample_indices_sha256=digest(indices),
        target_sha256=digest(query.model_dump(mode="json")),
        n_units=len(training.rows),
        replicate_count=len(refits),
        seed=seed,
        refit_scope=tuple(scm_spec.graph.nodes),
        fit_profile="dowhy-014",
        fit_request_sha256=base.fit_provenance.request_sha256,
        refit_worker_response=base.fit_provenance.worker_response,
        replicate_estimates=estimates,
    )


def _refit_bootstrap_interval(
    scm_spec: StructuralCausalModelSpec,
    query: CausalQuery,
    *,
    seed: int,
    confidence_level: float,
    replicate_count: int,
) -> CausalEstimatorInterval:
    """Resample complete declared iid units and genuinely refit every mechanism."""
    from polisyos.foundry.methods.catalog.causal.gcm_fit import _fit_gcm_specs
    from polisyos.foundry.methods.catalog.causal.protocols import SCMFitData

    training = scm_spec.training_rows
    if scm_spec.fit_method != "gcm" or training is None or scm_spec.fit_provenance is None:
        raise ValueError("iid refit bootstrap requires actual source-bound selected GCM fit")
    fit_input = SCMFitData.model_validate(training.fit_input)
    if fit_input.metadata.get("sampling_unit") != "iid_observation_row":
        raise ValueError(
            "refit bootstrap requires an explicit iid observation-row sampling declaration"
        )
    if not 20 <= replicate_count <= 500:
        raise ValueError("bootstrap_replicates must be between20 and500")
    _refit_target_estimate(scm_spec, query)  # Refuse unsupported estimands before launching fits.
    n = len(training.rows)
    indices = np.random.default_rng(seed).integers(0, n, size=(replicate_count, n)).tolist()
    base, refits = _fit_gcm_specs(fit_input, seed=seed, bootstrap_indices=indices)
    return _refit_interval_from_models(
        scm_spec,
        query,
        seed=seed,
        confidence_level=confidence_level,
        indices=indices,
        base=base,
        refits=refits,
    )


def validate_persisted_estimator_interval(
    interval: CausalEstimatorInterval,
    scm_spec: StructuralCausalModelSpec,
    query: CausalQuery,
    store: Any,
) -> None:
    """Reconcile the persisted interval with actual source custody and refit outputs."""
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.foundry.methods.catalog.causal._dowhy_worker import (
        validate_persisted_worker_response,
    )
    from polisyos.foundry.methods.catalog.causal.gcm_fit import _gcm_spec_from_worker
    from polisyos.foundry.methods.catalog.causal.protocols import SCMFitData

    training = scm_spec.training_rows
    if training is None:
        raise ValueError("persisted refit interval has no source-bound GCM training rows")
    state = SCMFitData.model_validate(training.fit_input)
    if scm_spec.fit_method != "gcm" or scm_spec.fit_provenance is None:
        raise ValueError("persisted refit interval requires the actual selected GCM profile")
    if (
        state.metadata.get("sampling_unit") != "iid_observation_row"
        or not 20 <= interval.replicate_count <= 500
    ):
        raise ValueError(
            "persisted refit interval requires the supported declared iid-row sampling law"
        )
    _refit_target_estimate(scm_spec, query)
    response = interval.refit_worker_response
    validate_persisted_worker_response(
        response=response,
        state=state,
        store=store,
        source_ref=ArtifactRef.model_validate(training.source_ref.model_dump(mode="json")),
    )
    if response["parent_observed"]["request_binding"]["seed"] != interval.seed:
        raise ValueError("persisted refit interval seed differs from its actual worker request")
    indices = (
        np.random.default_rng(interval.seed)
        .integers(
            0,
            len(training.rows),
            size=(interval.replicate_count, len(training.rows)),
        )
        .tolist()
    )
    if response["parent_observed"]["request_binding"]["payload"]["bootstrap_indices"] != indices:
        raise ValueError("persisted bootstrap indices differ from the declared iid resampling law")
    base = _gcm_spec_from_worker(state, response, response["result"], seed=interval.seed)
    models = response["result"].get("bootstrap_models")
    if not isinstance(models, list) or len(models) != len(indices):
        raise ValueError("persisted bootstrap worker output omits requested refits")
    refits = [
        _gcm_spec_from_worker(state, response, model, seed=interval.seed, resample_indices=idx)
        for model, idx in zip(models, indices, strict=True)
    ]
    expected = _refit_interval_from_models(
        scm_spec,
        query,
        seed=interval.seed,
        confidence_level=interval.confidence_level,
        indices=indices,
        base=base,
        refits=refits,
    )
    if expected != interval:
        raise ValueError(
            "persisted estimator interval differs from source-bound refitted estimates"
        )


def _intervention_replaces_natural(intervention: InterventionSpec | None) -> bool:
    """Whether an action replaces a node's natural mechanism entirely."""
    return intervention is not None and intervention.type in {
        InterventionType.ATOMIC,
        InterventionType.STOCHASTIC,
    }


def _intervention_stream_label(intervention: InterventionSpec | None) -> str:
    """Return a stable label for one intervention arm's stochastic draws."""
    if intervention is None:
        return "natural"
    return json.dumps(
        intervention.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )


def _active_query_nodes(
    scm_spec: StructuralCausalModelSpec,
    query: CausalQuery,
    *,
    intervention: InterventionSpec | None,
) -> set[str]:
    """Build the active graph slice for one query arm.

    The outcome and treatment are always retained.  Counterfactual factual
    conditions are retained as additional targets.  A direct interventional
    action cuts only the treatment's incoming natural mechanism; ancestors that
    still feed the outcome through another path remain active.
    """
    parents_map = _parents_by_node(scm_spec)
    targets = [query.outcome_variable, query.treatment_variable]
    if query.query_type is QueryType.COUNTERFACTUAL:
        targets.extend(query.condition)
    stop_nodes: set[str] = set()
    if query.query_type is not QueryType.COUNTERFACTUAL and _intervention_replaces_natural(
        intervention
    ):
        stop_nodes.add(query.treatment_variable)
    return _ancestors_for_targets(parents_map, targets, stop_nodes=stop_nodes)


def _required_missing_root_nodes(
    scm_spec: StructuralCausalModelSpec,
    query: CausalQuery,
) -> list[str]:
    """Find roots whose natural law is required by any simulated query arm."""
    order = _topological_order(scm_spec)
    mechanisms = _mechanism_map(scm_spec)
    interventions: list[InterventionSpec | None] = [_effective_intervention(query)]
    if query.query_type is QueryType.ATTRIBUTION:
        interventions.append(_attribution_comparator(query))
    active_nodes: set[str] = set()
    for intervention in interventions:
        active_nodes.update(
            _active_query_nodes(
                scm_spec,
                query,
                intervention=intervention,
            )
        )
    parents_map = _parents_by_node(scm_spec)
    roots = {node for node in active_nodes if not parents_map.get(node)}
    all_arms_replace_natural = all(
        _intervention_replaces_natural(intervention) for intervention in interventions
    )
    directly_intervened_root = query.treatment_variable in roots and all_arms_replace_natural
    return sorted(
        root
        for root in roots
        if root not in mechanisms
        and not (directly_intervened_root and root == query.treatment_variable)
    )


def _simulate_samples(
    *,
    scm_spec: StructuralCausalModelSpec,
    query: CausalQuery,
    n_samples: int,
    rng: np.random.Generator,
    warnings: list[str],
    logical_streams: _LogicalStreamFactory | None = None,
    stream_namespace: str = "primary",
    intervention_override: InterventionSpec | None | object = _INTERVENTION_UNSET,
    condition_override: Mapping[str, float] | None = None,
    precomputed_abduced_noises: dict[str, float] | None = None,
    allow_declared_hypothesis: bool = False,
    include_all_nodes: bool = False,
    # Existing remediation consumers unpack two values; provenance is opt-in
    # for the owning GCM query path rather than a breaking helper change.
    return_diagnostic: bool = False,
) -> (
    tuple[np.ndarray, dict[str, np.ndarray]]
    | tuple[np.ndarray, dict[str, np.ndarray], _AbductionDiagnostic]
):
    full_order = _topological_order(scm_spec)
    parents_map = _parents_by_node(scm_spec)
    mechanisms = _mechanism_map(scm_spec)
    condition = (
        dict(condition_override) if condition_override is not None else dict(query.condition)
    )
    intervention = (
        _effective_intervention(query)
        if intervention_override is _INTERVENTION_UNSET
        else intervention_override
    )
    if intervention is not None and not isinstance(intervention, InterventionSpec):
        raise TypeError("intervention_override must be an InterventionSpec or None")
    active_nodes = (
        set(full_order)
        if include_all_nodes
        else _active_query_nodes(
            scm_spec,
            query,
            intervention=intervention,
        )
    )
    order = [node for node in full_order if node in active_nodes]
    streams = logical_streams or _LogicalStreamFactory.from_generator(rng)
    node_rngs = {
        node: streams.generator(namespace=stream_namespace, label=f"node:{node}") for node in order
    }
    root_index_rng = streams.generator(
        namespace=stream_namespace,
        label="observed-root-index",
    )
    abduction_rng = streams.generator(namespace=stream_namespace, label="abduction")
    intervention_rng = streams.generator(
        namespace=stream_namespace,
        label=f"intervention:{_intervention_stream_label(intervention)}",
    )
    observed_root_samples = {
        node: values
        for node, values in _observed_root_samples(mechanisms).items()
        if node in active_nodes
    }
    descendants = _descendants_of_treatment(scm_spec, query.treatment_variable)

    linear_gaussian_posterior: _LinearGaussianPosterior | None = None
    abduction_diagnostic = _AbductionDiagnostic(profile="not_requested")
    if precomputed_abduced_noises is not None:
        # Caller provided pre-computed noises (e.g. from twin-network query)
        abduced_noises = precomputed_abduced_noises
        abduction_diagnostic = _AbductionDiagnostic(
            profile="precomputed_abduction",
            noise_nodes=tuple(sorted(precomputed_abduced_noises)),
        )
    elif query.query_type is QueryType.COUNTERFACTUAL:
        linear_gaussian_posterior, abduction_diagnostic = _prepare_linear_gaussian_abduction(
            condition=condition,
            order=order,
            parents_map=parents_map,
            mechanisms=mechanisms,
            treatment_variable=query.treatment_variable,
        )
        abduced_noises = {}
        if linear_gaussian_posterior is None:
            abduced_noises = _abduce_linear_noises(
                query=query.model_copy(update={"condition": condition}),
                order=order,
                parents_map=parents_map,
                mechanisms=mechanisms,
            )
            abduction_diagnostic = abduction_diagnostic.with_noise_nodes(abduced_noises)
        if abduction_diagnostic.limitation is not None:
            _append_warning(warnings, f"limited abduction: {abduction_diagnostic.limitation}")
    else:
        abduced_noises = {}

    stochastic_law = None
    if intervention is not None and intervention.type is InterventionType.STOCHASTIC:
        try:
            stochastic_law = _resolve_stochastic_distribution(intervention.distribution or "")
        except (TypeError, ValueError) as exc:
            raise ValueError(f"stochastic intervention law is invalid: {exc}") from exc
    by_node: dict[str, list[float]] = {node: [] for node in order}
    outcome_values = np.zeros(n_samples, dtype=float)

    for index in range(n_samples):
        assignment: dict[str, float] = {}
        sample_abduced_noises = (
            _draw_linear_gaussian_noises(linear_gaussian_posterior, abduction_rng)
            if linear_gaussian_posterior is not None
            else abduced_noises
        )
        root_sample_index = _joint_root_sample_index(observed_root_samples, root_index_rng)
        for node in order:
            parent_values = {
                parent: assignment[parent]
                for parent in parents_map.get(node, [])
                if parent in assignment
            }

            if (
                query.query_type is QueryType.COUNTERFACTUAL
                and node in condition
                and node != query.treatment_variable
                and node not in descendants
            ):
                value = float(condition[node])
            else:
                if node == query.treatment_variable and _intervention_replaces_natural(
                    intervention
                ):
                    value = 0.0
                else:
                    mechanism = mechanisms.get(node)
                    noise_override = (
                        sample_abduced_noises.get(node)
                        if query.query_type is QueryType.COUNTERFACTUAL
                        else None
                    )
                    value = _sample_node_value(
                        mechanism=mechanism,
                        parent_values=parent_values,
                        rng=node_rngs[node],
                        warnings=warnings,
                        linear_noise_override=noise_override,
                        sample_index=root_sample_index,
                        observed_root_samples=observed_root_samples,
                        allow_declared_hypothesis=allow_declared_hypothesis,
                    )

            if node == query.treatment_variable and intervention is not None:
                baseline = (
                    0.0
                    if _intervention_replaces_natural(intervention)
                    else float(condition[node])
                    if node in condition
                    else float(value)
                )
                value = _apply_intervention(
                    current_value=baseline,
                    intervention_spec=intervention,
                    fallback_treatment_value=query.effective_treatment_value,
                    rng=intervention_rng,
                    warnings=warnings,
                    stochastic_law=stochastic_law,
                )

            assignment[node] = float(value)
            by_node[node].append(float(value))

        outcome_values[index] = assignment[query.outcome_variable]

    samples_by_node = {node: np.asarray(values, dtype=float) for node, values in by_node.items()}
    if return_diagnostic:
        return outcome_values, samples_by_node, abduction_diagnostic
    return outcome_values, samples_by_node


def _percentile_ci(samples: np.ndarray, confidence_level: float) -> tuple[float, float]:
    alpha = 1.0 - confidence_level
    lo = float(np.percentile(samples, 100.0 * alpha / 2.0))
    hi = float(np.percentile(samples, 100.0 * (1.0 - alpha / 2.0)))
    if lo > hi:
        lo, hi = hi, lo
    return (lo, hi)


def _load_dowhy_dependencies() -> tuple[Any, Any]:
    import dowhy
    import pandas as pd

    return dowhy, pd


def _to_float_scalar(value: Any) -> float:
    array = np.asarray(value, dtype=float)
    if array.size != 1:
        raise ValueError(f"expected scalar value, got shape={array.shape}")
    scalar = float(array.reshape(-1)[0])
    if not math.isfinite(scalar):
        raise ValueError("scalar value must be finite")
    return scalar


def _build_dowhy_comparison(
    *,
    scm_spec: StructuralCausalModelSpec,
    query: CausalQuery,
    gcm_query_mean: float,
    params: Mapping[str, Any],
    rng: np.random.Generator,
    logical_streams: _LogicalStreamFactory,
    warnings: list[str],
) -> dict[str, Any] | None:
    intervention = _effective_intervention(query)
    if intervention is None:
        return None
    if intervention.type is not InterventionType.ATOMIC:
        return None
    if query.query_type is not QueryType.INTERVENTIONAL:
        return None
    if query.effective_treatment_value is None:
        return None

    try:
        _, pd = _load_dowhy_dependencies()
    except ModuleNotFoundError:
        return None
    except Exception as exc:
        _append_warning(warnings, f"DoWhy comparison unavailable: {exc}")
        return None

    try:
        graph_dot = scm_spec.graph.to_dot()
    except Exception as exc:
        _append_warning(warnings, f"DoWhy comparison skipped; graph export failed: {exc}")
        return None

    n_obs = int(params.get("dowhy_n_samples", max(query.n_samples, 500)))
    n_obs = max(50, n_obs)
    try:
        obs_query = query.model_copy(
            update={
                "condition": {},
                "query_type": QueryType.ATTRIBUTION,
                "intervention_spec": None,
                "treatment_value": None,
            }
        )
        _, node_samples = _simulate_samples(
            scm_spec=scm_spec,
            query=obs_query,
            n_samples=n_obs,
            rng=rng,
            warnings=warnings,
            logical_streams=logical_streams,
            stream_namespace="dowhy-observational",
            intervention_override=None,
            condition_override={},
            include_all_nodes=True,
        )
        frame = pd.DataFrame({node: node_samples[node] for node in scm_spec.graph.nodes})
        treatment_col = query.treatment_variable
        outcome_col = query.outcome_variable
        method_name = str(params.get("dowhy_method_name", "backdoor.linear_regression"))
        model = _load_dowhy_dependencies()[0].CausalModel(
            data=frame,
            treatment=treatment_col,
            outcome=outcome_col,
            graph=graph_dot,
        )
        estimand = model.identify_effect(proceed_when_unidentifiable=False)
        estimate = model.estimate_effect(estimand, method_name=method_name)
        dowhy_ate = _to_float_scalar(estimate.value)

        control_value = float(params.get("dowhy_control_value", 0.0))
        treat_value = float(query.effective_treatment_value)
        treat_spec = InterventionSpec(type=InterventionType.ATOMIC, value=treat_value)
        control_spec = InterventionSpec(type=InterventionType.ATOMIC, value=control_value)

        treat_query = query.model_copy(
            update={
                "query_type": QueryType.INTERVENTIONAL,
                "intervention_spec": treat_spec,
                "treatment_value": treat_value,
                "condition": {},
            }
        )
        control_query = query.model_copy(
            update={
                "query_type": QueryType.INTERVENTIONAL,
                "intervention_spec": control_spec,
                "treatment_value": control_value,
                "condition": {},
            }
        )
        treated_outcomes, _ = _simulate_samples(
            scm_spec=scm_spec,
            query=treat_query,
            n_samples=query.n_samples,
            rng=rng,
            warnings=warnings,
            logical_streams=logical_streams,
            stream_namespace="dowhy-interventional",
            intervention_override=treat_query.intervention_spec,
            condition_override={},
        )
        control_outcomes, _ = _simulate_samples(
            scm_spec=scm_spec,
            query=control_query,
            n_samples=query.n_samples,
            rng=rng,
            warnings=warnings,
            logical_streams=logical_streams,
            stream_namespace="dowhy-interventional",
            intervention_override=control_query.intervention_spec,
            condition_override={},
        )
        gcm_ate = float(np.mean(treated_outcomes) - np.mean(control_outcomes))

        return {
            "method_name": method_name,
            "do_treatment_value": treat_value,
            "do_control_value": control_value,
            "gcm_query_mean": float(gcm_query_mean),
            "gcm_ate": gcm_ate,
            "dowhy_ate": float(dowhy_ate),
            "delta_abs": float(abs(gcm_ate - dowhy_ate)),
            "delta_signed": float(gcm_ate - dowhy_ate),
        }
    except ModuleNotFoundError:
        return None
    except Exception as exc:
        _append_warning(warnings, f"DoWhy comparison failed: {exc}")
        return None


@foundry_method(
    namespace="causal.structural",
    version="1.0.0",
    tags={"causal", "structural", "gcm", "query"},
)
class GCMQuery:
    """Monte Carlo SCM query runner for interventions and counterfactuals."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="gcm_query",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="scm_query_data",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("query", "json"),
                )
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="causal_query_result",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("report", "json"),
                ),
            }
        ),
        parameters=(
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="store_distribution", default=True),
            ParameterSpec(name="enable_dowhy_comparison", default=True),
            ParameterSpec(name="dowhy_method_name", default="backdoor.linear_regression"),
            ParameterSpec(name="dowhy_control_value", default=0.0),
            ParameterSpec(name="allow_declared_root_hypothesis", default=False),
            ParameterSpec(name="bootstrap_replicates", default=0),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Run SCM interventional/counterfactual queries with Monte Carlo sampling.",
        tags=frozenset({"causal", "structural", "gcm", "query"}),
        assumptions={
            "acyclic_graph": "SCM graph must be acyclic for topological sampling.",
            "mechanism_coverage": (
                "Missing root mechanisms fail closed unless the caller explicitly opts into "
                "a limited declared hypothesis; such results are not gate eligible."
            ),
            "counterfactual_scope": (
                "Counterfactual abduction-action-prediction is exact only for "
                "linear mechanisms with identifiable residuals."
            ),
        },
        when_to_use="Query fitted GCM for counterfactuals, interventions, or attribution after GCMFit",
        citations=(
            "Pearl, J. (2009). Causality: Models, Reasoning, and Inference. Cambridge University Press.",
        ),
        when_not_to_use="GCM has not been fitted; query is purely observational; non-acyclic graph",
        output_interpretation="Counterfactual distribution P(Y|do(X=x)). Attribution of anomaly/change to each causal parent.",
    )

    @staticmethod
    def pure_step(state: SCMQueryData, params: Mapping[str, Any]) -> dict[str, Any]:
        payload = state if isinstance(state, SCMQueryData) else SCMQueryData.model_validate(state)
        query = payload.query
        scm_spec = payload.scm_spec

        seed = int(params.get("__seed__", 0) or 0)
        rng_param = params.get("__rng__")
        if isinstance(rng_param, np.random.Generator):
            rng = rng_param
            logical_streams = _LogicalStreamFactory.from_generator(rng)
        else:
            rng = np.random.default_rng(seed)
            logical_streams = _LogicalStreamFactory.from_seed(seed)
        confidence_level = float(params.get("confidence_level", 0.95))
        if not (0.0 < confidence_level < 1.0):
            raise ValueError("confidence_level must be in (0, 1)")
        warnings: list[str] = []
        started_at = time.perf_counter()
        allow_declared_hypothesis = params.get("allow_declared_root_hypothesis", False) is True
        missing_root_nodes = _required_missing_root_nodes(scm_spec, query)
        if missing_root_nodes and not allow_declared_hypothesis:
            raise ValueError(
                "missing mechanism for required root node(s): "
                f"{missing_root_nodes}; provide fitted carriers or explicitly enable "
                "allow_declared_root_hypothesis"
            )
        if missing_root_nodes:
            _append_warning(
                warnings,
                "declared root hypothesis used for missing node(s): "
                f"{missing_root_nodes}; result is limited and not gate eligible",
            )

        if query.query_type is QueryType.ATTRIBUTION:
            intervention = _effective_intervention(query)
            if intervention is None:
                raise ValueError("attribution queries require intervention context")
            treated, _, treated_abduction = _simulate_samples(
                scm_spec=scm_spec,
                query=query.model_copy(update={"query_type": QueryType.INTERVENTIONAL}),
                n_samples=query.n_samples,
                rng=rng,
                warnings=warnings,
                logical_streams=logical_streams,
                stream_namespace="attribution",
                intervention_override=intervention,
                condition_override={},
                allow_declared_hypothesis=allow_declared_hypothesis,
                return_diagnostic=True,
            )
            baseline, _, baseline_abduction = _simulate_samples(
                scm_spec=scm_spec,
                query=query.model_copy(update={"query_type": QueryType.INTERVENTIONAL}),
                n_samples=query.n_samples,
                rng=rng,
                warnings=warnings,
                logical_streams=logical_streams,
                stream_namespace="attribution",
                intervention_override=_attribution_comparator(query),
                condition_override={},
                allow_declared_hypothesis=allow_declared_hypothesis,
                return_diagnostic=True,
            )
            samples = treated - baseline
            abduction_diagnostic = (
                treated_abduction if not treated_abduction.gate_eligible else baseline_abduction
            )
        else:
            samples, _, abduction_diagnostic = _simulate_samples(
                scm_spec=scm_spec,
                query=query,
                n_samples=query.n_samples,
                rng=rng,
                warnings=warnings,
                logical_streams=logical_streams,
                stream_namespace="primary",
                intervention_override=_effective_intervention(query),
                allow_declared_hypothesis=allow_declared_hypothesis,
                return_diagnostic=True,
            )

        result_mean = float(np.mean(samples))
        result_std = float(np.std(samples))
        result_ci = _percentile_ci(samples, confidence_level=confidence_level)
        ci_lo, ci_hi = result_ci
        if result_mean < ci_lo:
            ci_lo = result_mean
        if result_mean > ci_hi:
            ci_hi = result_mean
        result_ci = (ci_lo, ci_hi)
        elapsed = float(time.perf_counter() - started_at)

        store_distribution = params.get("store_distribution", True) is not False
        replicate_count = params.get("bootstrap_replicates", 0)
        if type(replicate_count) is not int:
            raise ValueError("bootstrap_replicates must be an integer")
        estimator_interval = (
            _refit_bootstrap_interval(
                scm_spec,
                query,
                seed=seed,
                confidence_level=confidence_level,
                replicate_count=replicate_count,
            )
            if replicate_count != 0
            else None
        )
        query_result = CausalQueryResult(
            query=query,
            result_kind=(
                CausalResultKind.POSTERIOR_CREDIBLE_INTERVAL
                if abduction_diagnostic.profile == "linear_gaussian_posterior"
                else CausalResultKind.ITE_DISTRIBUTION
                if query.query_type is QueryType.ATTRIBUTION
                else CausalResultKind.OUTCOME_DISTRIBUTION
            ),
            interval_level=confidence_level,
            estimator_interval=estimator_interval,
            result_mean=result_mean,
            result_std=result_std,
            result_ci=result_ci,
            result_distribution=samples.tolist() if store_distribution else None,
            computation_time_seconds=elapsed,
            metadata={
                "confidence_level": confidence_level,
                "warnings_count": len(warnings),
                "declared_root_hypothesis": missing_root_nodes,
                **abduction_diagnostic.as_metadata(),
            },
        )

        envelope = query_result.to_uncertainty_envelope()
        if missing_root_nodes or not abduction_diagnostic.gate_eligible:
            envelope = envelope.model_copy(
                update={
                    "gate_eligible": False,
                    "metadata": {
                        **dict(envelope.metadata),
                        "declared_root_hypothesis": missing_root_nodes,
                        **abduction_diagnostic.as_metadata(),
                    },
                }
            )

        output: dict[str, Any] = {
            "causal_query_result": query_result,
            "query_result": query_result,
            "envelope": envelope,
            "estimator_envelope": query_result.to_estimator_uncertainty_envelope(),
            "warnings": warnings,
            "__determinism_tier__": DeterminismTier.STATISTICAL,
        }

        if params.get("enable_dowhy_comparison", True) is not False:
            comparison = _build_dowhy_comparison(
                scm_spec=scm_spec,
                query=query,
                gcm_query_mean=result_mean,
                params=params,
                rng=rng,
                logical_streams=logical_streams,
                warnings=warnings,
            )
            if comparison is not None:
                output["dowhy_comparison"] = comparison
        return output


__all__ = [
    "GCMQuery",
    "_abduce_noises_unified",
    "_effective_intervention",
    "_mechanism_map",
    "_parents_by_node",
    "_percentile_ci",
    "_sample_node_value",
    "_simulate_samples",
    "_topological_order",
]
