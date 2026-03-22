from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from polisyos.foundry.methods.catalog.causal._sklearn_compat import (
    LinearRegression,
    LogisticRegression,
    SKLEARN_AVAILABLE,
)

if SKLEARN_AVAILABLE:  # pragma: no cover - exercised in integration tests
    from sklearn.ensemble import (
        HistGradientBoostingClassifier,
        HistGradientBoostingRegressor,
        RandomForestRegressor,
    )
    try:  # pragma: no cover - optional in some sklearn builds
        from sklearn.linear_model import ElasticNet
    except Exception:  # pragma: no cover - fallback covered instead
        ElasticNet = None
else:  # pragma: no cover - fallback only
    HistGradientBoostingClassifier = None
    HistGradientBoostingRegressor = None
    RandomForestRegressor = None
    ElasticNet = None

try:  # pragma: no cover - optional dependency
    from lightgbm import LGBMClassifier, LGBMRegressor  # type: ignore[import]
except Exception:  # pragma: no cover - optional dependency
    LGBMClassifier = None
    LGBMRegressor = None


@dataclass(frozen=True)
class BackendSelection:
    name: str
    model: Any
    stabilizer: Any | None = None


def backend_name() -> str:
    return "lightgbm" if LGBMClassifier is not None and LGBMRegressor is not None else "hist_gradient_boosting"


def make_propensity_backend(seed: int, family: str) -> BackendSelection:
    family = family.strip().lower()
    if family == "lightweight":
        return BackendSelection(name="logistic", model=LogisticRegression(max_iter=2000, C=1.0))

    if LGBMClassifier is not None:  # pragma: no cover - optional dependency path
        primary = LGBMClassifier(
            n_estimators=180,
            learning_rate=0.05,
            max_depth=3,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=seed,
            n_jobs=1,
            deterministic=True,
            force_col_wise=True,
        )
        stabilizer = LogisticRegression(max_iter=2000, C=1.0)
        return BackendSelection(name="lightgbm", model=primary, stabilizer=stabilizer)

    if HistGradientBoostingClassifier is not None:
        primary = HistGradientBoostingClassifier(
            max_depth=3,
            max_iter=160,
            learning_rate=0.05,
            min_samples_leaf=20,
            random_state=seed,
        )
        stabilizer = LogisticRegression(max_iter=2000, C=1.0)
        return BackendSelection(name="hist_gradient_boosting", model=primary, stabilizer=stabilizer)

    return BackendSelection(name="logistic", model=LogisticRegression(max_iter=2000, C=1.0))


def make_outcome_backends(seed: int, family: str) -> BackendSelection:
    family = family.strip().lower()
    if family == "lightweight":
        stabilizer = LinearRegression()
        return BackendSelection(name="linear", model=stabilizer, stabilizer=None)

    if LGBMRegressor is not None:  # pragma: no cover - optional dependency path
        primary = LGBMRegressor(
            n_estimators=220,
            learning_rate=0.04,
            max_depth=3,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=seed,
            n_jobs=1,
            deterministic=True,
            force_col_wise=True,
        )
        stabilizer = _make_linear_stabilizer()
        return BackendSelection(name="lightgbm", model=primary, stabilizer=stabilizer)

    if HistGradientBoostingRegressor is not None:
        primary = HistGradientBoostingRegressor(
            max_depth=3,
            max_iter=200,
            learning_rate=0.05,
            min_samples_leaf=20,
            random_state=seed,
        )
        stabilizer = _make_linear_stabilizer()
        return BackendSelection(name="hist_gradient_boosting", model=primary, stabilizer=stabilizer)

    return BackendSelection(name="linear", model=LinearRegression(), stabilizer=None)


def make_tau_backends(seed: int, family: str) -> list[Any]:
    family = family.strip().lower()
    if family == "lightweight":
        return [LinearRegression()]
    if RandomForestRegressor is not None:
        return [
            RandomForestRegressor(
                n_estimators=128,
                min_samples_leaf=8,
                max_features="sqrt",
                random_state=seed,
                n_jobs=1,
            ),
            LinearRegression(),
        ]
    return [LinearRegression()]


def _make_linear_stabilizer() -> Any:
    if ElasticNet is not None:
        return ElasticNet(alpha=0.001, l1_ratio=0.1, max_iter=4000, random_state=0)
    return LinearRegression()


def deterministic_repeat_seeds(
    *,
    base_seed: int,
    n_repeats: int,
    manifest: tuple[int, ...] = (),
) -> tuple[int, ...]:
    if manifest:
        seeds = tuple(int(seed) for seed in manifest[:n_repeats])
        if len(seeds) < n_repeats:
            start = seeds[-1] if seeds else base_seed
            extra = tuple(start + 997 * (idx + 1) for idx in range(n_repeats - len(seeds)))
            seeds = seeds + extra
        return seeds
    return tuple(base_seed + 997 * repeat for repeat in range(n_repeats))


def build_split_manifest(
    treatment: np.ndarray,
    *,
    n_folds: int,
    n_repeats: int,
    base_seed: int,
    seed_manifest: tuple[int, ...] = (),
) -> tuple[tuple[tuple[np.ndarray, np.ndarray], ...], tuple[int, ...]]:
    treatment = np.asarray(treatment, dtype=float).reshape(-1)
    n_obs = int(treatment.shape[0])
    if n_obs == 0:
        return tuple(), tuple()

    if n_obs <= n_folds:
        indices = np.arange(n_obs, dtype=int)
        repeat_seeds = deterministic_repeat_seeds(base_seed=base_seed, n_repeats=n_repeats, manifest=seed_manifest)
        manifest = tuple(tuple(((indices, indices),)) for _ in repeat_seeds)
        return manifest, repeat_seeds

    repeat_seeds = deterministic_repeat_seeds(base_seed=base_seed, n_repeats=n_repeats, manifest=seed_manifest)
    repeats: list[tuple[tuple[np.ndarray, np.ndarray], ...]] = []
    indices = np.arange(n_obs, dtype=int)
    for rep_seed in repeat_seeds:
        rng = np.random.default_rng(rep_seed)
        treated = np.flatnonzero(treatment > 0.5)
        control = np.flatnonzero(treatment <= 0.5)
        rng.shuffle(treated)
        rng.shuffle(control)
        treated_chunks = np.array_split(treated, n_folds)
        control_chunks = np.array_split(control, n_folds)
        folds: list[tuple[np.ndarray, np.ndarray]] = []
        for fold_id in range(n_folds):
            test_idx = np.concatenate([treated_chunks[fold_id], control_chunks[fold_id]])
            test_idx = np.sort(test_idx.astype(int))
            train_mask = np.ones(n_obs, dtype=bool)
            train_mask[test_idx] = False
            folds.append((indices[train_mask], test_idx))
        repeats.append(tuple(folds))
    return tuple(repeats), repeat_seeds


__all__ = [
    "BackendSelection",
    "backend_name",
    "build_split_manifest",
    "deterministic_repeat_seeds",
    "make_outcome_backends",
    "make_propensity_backend",
    "make_tau_backends",
]
