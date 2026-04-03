"""Synthetic data generating processes with known ground truth ATE and CATE."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.special import expit


@dataclass
class DGPData:
    """Container for a single synthetic dataset."""

    X: np.ndarray          # (n, p) covariates
    T: np.ndarray          # (n,) binary treatment
    Y: np.ndarray          # (n,) observed outcome
    true_ate: float
    true_cate: np.ndarray  # (n,) individual true effects
    dgp_name: str
    params: dict[str, Any]


def _make_covariates(n: int, p: int, rng: np.random.Generator) -> np.ndarray:
    return rng.standard_normal((n, p))


# -----------------------------------------------------------------------
# DGP 1: Linear confounding — constant ATE
# -----------------------------------------------------------------------
def dgp_linear(n: int, rng: np.random.Generator, *, p: int = 10, ate: float = 1.0) -> DGPData:
    X = _make_covariates(n, p, rng)
    beta_prop = rng.standard_normal(p) * 0.5
    propensity = expit(X @ beta_prop)
    T = rng.binomial(1, propensity).astype(float)

    beta_out = rng.standard_normal(p) * 0.5
    Y0 = X @ beta_out + rng.standard_normal(n) * 0.5
    cate = np.full(n, ate)
    Y = Y0 + T * cate

    return DGPData(X=X, T=T, Y=Y, true_ate=ate, true_cate=cate, dgp_name="linear",
                   params={"n": n, "p": p, "ate": ate})


# -----------------------------------------------------------------------
# DGP 2: Nonlinear outcome — interactions + squared covariates
# -----------------------------------------------------------------------
def dgp_nonlinear(n: int, rng: np.random.Generator, *, p: int = 10, ate: float = 1.5) -> DGPData:
    X = _make_covariates(n, p, rng)
    propensity = expit(0.5 * X[:, 0] + 0.3 * X[:, 1] ** 2 - 0.2 * X[:, 2] * X[:, 3])
    T = rng.binomial(1, propensity).astype(float)

    Y0 = (np.sin(X[:, 0]) + X[:, 1] ** 2 + 0.5 * X[:, 2] * X[:, 3]
           + rng.standard_normal(n) * 0.5)
    cate = np.full(n, ate)
    Y = Y0 + T * cate

    return DGPData(X=X, T=T, Y=Y, true_ate=ate, true_cate=cate, dgp_name="nonlinear",
                   params={"n": n, "p": p, "ate": ate})


# -----------------------------------------------------------------------
# DGP 3: Heterogeneous treatment effects
# -----------------------------------------------------------------------
def dgp_hte(n: int, rng: np.random.Generator, *, p: int = 10, base_ate: float = 1.0,
            hte_strength: float = 2.0) -> DGPData:
    X = _make_covariates(n, p, rng)
    propensity = expit(0.3 * X[:, 0] + 0.3 * X[:, 1])
    T = rng.binomial(1, propensity).astype(float)

    Y0 = X[:, 0] + 0.5 * X[:, 1] + rng.standard_normal(n) * 0.5
    cate = base_ate + hte_strength * X[:, 0]
    Y = Y0 + T * cate

    return DGPData(X=X, T=T, Y=Y, true_ate=float(np.mean(cate)),
                   true_cate=cate, dgp_name="hte",
                   params={"n": n, "p": p, "base_ate": base_ate, "hte_strength": hte_strength})


# -----------------------------------------------------------------------
# DGP 4: Strong overlap (near-randomised)
# -----------------------------------------------------------------------
def dgp_strong_overlap(n: int, rng: np.random.Generator, *, p: int = 10,
                       ate: float = 1.0) -> DGPData:
    X = _make_covariates(n, p, rng)
    propensity = expit(0.05 * X[:, 0])  # very weak confounding
    T = rng.binomial(1, propensity).astype(float)

    Y0 = X[:, 0] + 0.5 * X[:, 1] + rng.standard_normal(n) * 0.5
    cate = np.full(n, ate)
    Y = Y0 + T * cate

    return DGPData(X=X, T=T, Y=Y, true_ate=ate, true_cate=cate,
                   dgp_name="strong_overlap",
                   params={"n": n, "p": p, "ate": ate})


# -----------------------------------------------------------------------
# DGP 5: Weak overlap (propensity near 0/1)
# -----------------------------------------------------------------------
def dgp_weak_overlap(n: int, rng: np.random.Generator, *, p: int = 10,
                     ate: float = 1.0) -> DGPData:
    X = _make_covariates(n, p, rng)
    propensity = expit(2.0 * X[:, 0] + 1.5 * X[:, 1] + X[:, 2])
    T = rng.binomial(1, propensity).astype(float)

    Y0 = 2.0 * X[:, 0] + X[:, 1] + rng.standard_normal(n) * 0.5
    cate = np.full(n, ate)
    Y = Y0 + T * cate

    return DGPData(X=X, T=T, Y=Y, true_ate=ate, true_cate=cate,
                   dgp_name="weak_overlap",
                   params={"n": n, "p": p, "ate": ate})


# -----------------------------------------------------------------------
# DGP 6: High-dimensional sparse
# -----------------------------------------------------------------------
def dgp_high_dim(n: int, rng: np.random.Generator, *, p: int = 50,
                 ate: float = 1.0) -> DGPData:
    X = _make_covariates(n, p, rng)
    # Only first 5 covariates matter
    propensity = expit(0.5 * X[:, 0] + 0.3 * X[:, 1] + 0.2 * X[:, 2])
    T = rng.binomial(1, propensity).astype(float)

    Y0 = X[:, 0] + 0.5 * X[:, 1] + 0.3 * X[:, 2] + rng.standard_normal(n) * 0.5
    cate = np.full(n, ate)
    Y = Y0 + T * cate

    return DGPData(X=X, T=T, Y=Y, true_ate=ate, true_cate=cate,
                   dgp_name="high_dim",
                   params={"n": n, "p": p, "ate": ate})


# -----------------------------------------------------------------------
# DGP 7: Misspecified nuisance (neither propensity nor outcome is linear)
# -----------------------------------------------------------------------
def dgp_misspecified(n: int, rng: np.random.Generator, *, p: int = 10,
                     ate: float = 1.0) -> DGPData:
    X = _make_covariates(n, p, rng)
    propensity = expit(np.sin(X[:, 0]) + np.abs(X[:, 1]) + X[:, 2] ** 2 - 1.0)
    T = rng.binomial(1, propensity).astype(float)

    Y0 = (np.exp(0.5 * X[:, 0]) + np.abs(X[:, 1]) * X[:, 2]
           + rng.standard_normal(n) * 0.5)
    cate = np.full(n, ate)
    Y = Y0 + T * cate

    return DGPData(X=X, T=T, Y=Y, true_ate=ate, true_cate=cate,
                   dgp_name="misspecified",
                   params={"n": n, "p": p, "ate": ate})


# -----------------------------------------------------------------------
# Registry
# -----------------------------------------------------------------------
DGP_REGISTRY = {
    "linear": dgp_linear,
    "nonlinear": dgp_nonlinear,
    "hte": dgp_hte,
    "strong_overlap": dgp_strong_overlap,
    "weak_overlap": dgp_weak_overlap,
    "high_dim": dgp_high_dim,
    "misspecified": dgp_misspecified,
}
