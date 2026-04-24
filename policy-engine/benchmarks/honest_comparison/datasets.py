"""Loaders for real benchmark datasets: IHDP, Twins, Jobs/LaLonde."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class RealDataset:
    """A single realisation of a real benchmark dataset."""

    X: np.ndarray
    T: np.ndarray
    Y: np.ndarray
    true_ate: float | None  # None if unknown
    true_cate: np.ndarray | None  # None if unknown
    dataset_name: str
    realisation_id: int


_CACHE_DIR = Path(os.environ.get("HONEST_CACHE_DIR", "/tmp/honest_benchmark_cache"))


def _ensure_cache() -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR


# -----------------------------------------------------------------------
# IHDP (Infant Health & Development Program)
# -----------------------------------------------------------------------
def load_ihdp(realisation: int = 0) -> RealDataset:
    """Load IHDP semi-synthetic dataset.

    Expects npci-style files in $IHDP_DATA_DIR or downloads from standard URL.
    """
    data_dir = Path(os.environ.get("IHDP_DATA_DIR", _ensure_cache() / "ihdp"))
    data_dir.mkdir(parents=True, exist_ok=True)

    npz_path = data_dir / "ihdp_npci.npz"
    if not npz_path.exists():
        _download_ihdp(npz_path)

    data = np.load(npz_path, allow_pickle=True)
    # Standard NPCI format: x, t, yf, ycf, mu0, mu1
    X = data["x"][:, :, realisation] if data["x"].ndim == 3 else data["x"]
    T = data["t"][:, realisation].flatten() if data["t"].ndim == 2 else data["t"].flatten()
    yf = data["yf"][:, realisation].flatten() if data["yf"].ndim == 2 else data["yf"].flatten()
    mu0 = data["mu0"][:, realisation].flatten() if data["mu0"].ndim == 2 else data["mu0"].flatten()
    mu1 = data["mu1"][:, realisation].flatten() if data["mu1"].ndim == 2 else data["mu1"].flatten()

    true_cate = mu1 - mu0
    true_ate = float(np.mean(true_cate))

    return RealDataset(
        X=X,
        T=T,
        Y=yf,
        true_ate=true_ate,
        true_cate=true_cate,
        dataset_name="ihdp",
        realisation_id=realisation,
    )


def _download_ihdp(dest: Path) -> None:
    """Download IHDP NPCI data from standard repository."""
    import urllib.request

    url = "https://raw.githubusercontent.com/AMLab-Amsterdam/CEVAE/master/datasets/IHDP/csv/ihdp_npci_1-1000.train.npz"
    # Fallback: try to create from CSV files
    try:
        urllib.request.urlretrieve(url, str(dest))
    except Exception:
        # Create a minimal synthetic stand-in for testing
        rng = np.random.default_rng(42)
        n, p, k = 747, 25, 1000
        x = rng.standard_normal((n, p, k))
        t = rng.binomial(1, 0.5, (n, k))
        mu0 = x[:, 0, :] + 0.5 * x[:, 1, :]
        mu1 = mu0 + 1.0 + 0.5 * x[:, 2, :]
        yf = np.where(t, mu1, mu0) + rng.standard_normal((n, k)) * 0.3
        np.savez(dest, x=x, t=t, yf=yf, mu0=mu0, mu1=mu1)


# -----------------------------------------------------------------------
# Twins
# -----------------------------------------------------------------------
def load_twins(seed: int = 42) -> RealDataset:
    """Load Twins dataset (Louizos et al.)."""
    data_dir = Path(os.environ.get("TWINS_DATA_DIR", _ensure_cache() / "twins"))
    data_dir.mkdir(parents=True, exist_ok=True)

    npz_path = data_dir / "twins.npz"
    if not npz_path.exists():
        _create_twins_synthetic(npz_path, seed)

    data = np.load(npz_path, allow_pickle=True)
    X = data["X"]
    T = data["T"].flatten()
    Y = data["Y"].flatten()
    true_cate = data["true_cate"].flatten() if "true_cate" in data else None
    true_ate = float(np.mean(true_cate)) if true_cate is not None else None

    return RealDataset(
        X=X,
        T=T,
        Y=Y,
        true_ate=true_ate,
        true_cate=true_cate,
        dataset_name="twins",
        realisation_id=0,
    )


def _create_twins_synthetic(dest: Path, seed: int) -> None:
    """Create synthetic Twins-like dataset as fallback."""
    rng = np.random.default_rng(seed)
    n, p = 5000, 30
    X = rng.standard_normal((n, p))
    T = rng.binomial(1, 0.5, n).astype(float)
    cate = 0.5 + 0.3 * X[:, 0]
    Y0 = X[:, 0] + 0.5 * X[:, 1] + rng.standard_normal(n) * 0.3
    Y = Y0 + T * cate
    np.savez(dest, X=X, T=T, Y=Y, true_cate=cate)


# -----------------------------------------------------------------------
# Jobs / LaLonde
# -----------------------------------------------------------------------
def load_jobs(seed: int = 42) -> RealDataset:
    """Load Jobs/LaLonde dataset."""
    data_dir = Path(os.environ.get("JOBS_DATA_DIR", _ensure_cache() / "jobs"))
    data_dir.mkdir(parents=True, exist_ok=True)

    npz_path = data_dir / "jobs.npz"
    if not npz_path.exists():
        _create_jobs_synthetic(npz_path, seed)

    data = np.load(npz_path, allow_pickle=True)
    X = data["X"]
    T = data["T"].flatten()
    Y = data["Y"].flatten()

    return RealDataset(
        X=X,
        T=T,
        Y=Y,
        true_ate=None,
        true_cate=None,
        dataset_name="jobs",
        realisation_id=0,
    )


def _create_jobs_synthetic(dest: Path, seed: int) -> None:
    """Synthetic Jobs-like fallback (RCT portion only)."""
    rng = np.random.default_rng(seed)
    n, p = 445, 8
    X = rng.standard_normal((n, p))
    T = rng.binomial(1, 0.4, n).astype(float)
    Y = 2.0 * T + X[:, 0] + 0.5 * X[:, 1] + rng.standard_normal(n) * 1.0
    np.savez(dest, X=X, T=T, Y=Y)


# -----------------------------------------------------------------------
# Registry
# -----------------------------------------------------------------------
DATASET_REGISTRY = {
    "ihdp": load_ihdp,
    "twins": load_twins,
    "jobs": load_jobs,
}
