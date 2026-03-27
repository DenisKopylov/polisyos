"""Identifiability diagnostics via Hessian eigenstructure."""

from __future__ import annotations

from enum import Enum
from typing import List

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from polisyos.foundry.calibration.hessian import HessianResult


class IdentifiabilityStatus(str, Enum):
    """Per-parameter identifiability classification."""

    IDENTIFIED = "identified"
    SLOPPY = "sloppy"
    NON_IDENTIFIED = "non_identified"


class ParamIdentifiability(BaseModel):
    """Identifiability diagnostic for a single parameter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    status: IdentifiabilityStatus
    eigenvalue: float
    std: float


class IdentifiabilityReport(BaseModel):
    """Aggregate identifiability diagnostics for all calibrated parameters."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    params: List[ParamIdentifiability] = Field(default_factory=list)
    n_identified: int = 0
    n_sloppy: int = 0
    n_non_identified: int = 0
    effective_dimension: int = 0


def diagnose_identifiability(
    hessian_result: HessianResult,
    *,
    identified_threshold: float = 1e-3,
    sloppy_threshold: float = 1e-8,
) -> IdentifiabilityReport:
    """Check parameter identifiability via Hessian eigenstructure.

    Per-parameter classification based on the diagonal of H (which reflects
    the curvature of the loss w.r.t. each parameter):
      - identified:     eigenvalue contribution > *identified_threshold*
      - sloppy:         eigenvalue contribution in (*sloppy_threshold*, *identified_threshold*]
      - non_identified: eigenvalue contribution <= *sloppy_threshold*
    """
    n = len(hessian_result.param_names)
    hessian_diag = np.diag(hessian_result.hessian)

    params: list[ParamIdentifiability] = []
    n_identified = 0
    n_sloppy = 0
    n_non_identified = 0

    for i in range(n):
        ev = float(hessian_diag[i])
        std_i = float(hessian_result.std[i])

        if ev > identified_threshold:
            status = IdentifiabilityStatus.IDENTIFIED
            n_identified += 1
        elif ev > sloppy_threshold:
            status = IdentifiabilityStatus.SLOPPY
            n_sloppy += 1
        else:
            status = IdentifiabilityStatus.NON_IDENTIFIED
            n_non_identified += 1

        params.append(
            ParamIdentifiability(
                name=hessian_result.param_names[i],
                status=status,
                eigenvalue=ev,
                std=std_i,
            )
        )

    effective_dimension = int(np.sum(hessian_result.eigenvalues > sloppy_threshold))

    return IdentifiabilityReport(
        params=params,
        n_identified=n_identified,
        n_sloppy=n_sloppy,
        n_non_identified=n_non_identified,
        effective_dimension=effective_dimension,
    )
