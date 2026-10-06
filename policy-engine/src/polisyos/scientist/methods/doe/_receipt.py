"""Persist and reproduce exploratory DOE analyses in the configured artifact store."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict

from .analysis import _analysis_identity, analyze_sensitivity
from .designs import SensitivityPlan, SensitivityResult

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactRef, ArtifactStore

_KIND = "doe_sensitivity_analysis"
_VERSION = "1.0"


class _AnalysisReceipt(BaseModel):
    """Bind the actual complete ordered experiment to its numerical result."""

    model_config = ConfigDict(extra="forbid")

    protocol: Literal["doe-analysis-v1"] = "doe-analysis-v1"
    plan: SensitivityPlan
    samples: list[list[float | Literal["nan", "inf", "-inf"]]]
    outputs: list[float | Literal["nan", "inf", "-inf"]]
    result: SensitivityResult
    authority_purpose: Literal["exploratory_parameter_experiment"] = (
        "exploratory_parameter_experiment"
    )
    evaluator_provenance: Literal["not_established"] = "not_established"
    population_law_status: Literal["not_established"] = "not_established"


def _persist_analysis(
    store: ArtifactStore,
    plan: SensitivityPlan,
    samples: np.ndarray,
    outputs: np.ndarray,
    result: SensitivityResult,
) -> ArtifactRef:
    """Persist complete rows, preserving each nonfinite outcome without dropping it."""
    from polisyos.core.artifacts import ArtifactWriteOptions, SchemaInfo
    from polisyos.core.canon import CanonSpec

    if plan.seed is None:
        raise ValueError("Persisted DOE analysis requires an explicit replay seed")
    identity = _analysis_identity(plan, samples, outputs)
    if any(result.metadata.get(key) != value for key, value in identity.items()):
        raise ValueError("Sensitivity result does not bind the supplied ordered experiment")
    receipt = _AnalysisReceipt(
        plan=plan,
        samples=[
            [float(value) if np.isfinite(value) else str(value) for value in row] for row in samples
        ],
        outputs=[float(value) if np.isfinite(value) else str(value) for value in outputs],
        result=result,
    )
    return store.put_json(
        receipt.model_dump(mode="json"),
        ArtifactWriteOptions(
            kind=_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=_KIND, version=_VERSION),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def _load_analysis(store: ArtifactStore, ref: ArtifactRef) -> SensitivityResult:
    """Resolve exact kind/schema/bytes and reproduce the analysis before consumption."""
    from polisyos.core.canon import from_canonical_bytes

    manifest = store.get_manifest(ref)
    if (
        manifest.kind != _KIND
        or manifest.media_type != "application/json"
        or manifest.artifact_schema is None
        or manifest.artifact_schema.name != _KIND
        or manifest.artifact_schema.version != _VERSION
    ):
        raise ValueError("Expected a DOE sensitivity analysis artifact kind/schema")
    if not store.verify(ref).ok:
        raise ValueError("DOE sensitivity analysis artifact integrity failed")
    receipt = _AnalysisReceipt.model_validate(from_canonical_bytes(store.get_bytes(ref)))
    if receipt.plan.seed is None:
        raise ValueError("Persisted DOE analysis requires an explicit replay seed")
    samples = np.asarray(receipt.samples, dtype=float)
    outputs = np.asarray(receipt.outputs, dtype=float)
    reproduced = analyze_sensitivity(receipt.plan, samples, outputs)
    if reproduced.model_dump(mode="json") != receipt.result.model_dump(mode="json"):
        raise ValueError("Persisted DOE sensitivity result does not reproduce")
    return reproduced
