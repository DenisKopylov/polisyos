"""Selected CAS persistence and numerical replay for exploratory DOE analyses."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, ClassVar, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict

from .analysis import _analysis_identity, _array_payload, _backend_identity, analyze_sensitivity
from .designs import (
    _SALIB_BACKEND_ID,
    SensitivityMethod,
    SensitivityPlan,
    SensitivityResult,
    _admit_sensitivity_analysis_plan,
)

if TYPE_CHECKING:
    from polisyos.core import artifacts as core_artifacts
    from polisyos.core.artifacts.canonical_profile import CoreJsonReadLimits


class _AnalysisReceipt(BaseModel):
    """Bind the complete ordered numerical experiment without world authority."""

    ARTIFACT_KIND: ClassVar[str] = "doe_sensitivity_analysis"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "doe_sensitivity_analysis"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    protocol: Literal["doe-analysis-v1"] = "doe-analysis-v1"
    sampler_seed_basis: Literal["recomputed"] = "recomputed"
    plan: SensitivityPlan
    samples: list[list[float | Literal["nan", "inf", "-inf"]]]
    outputs: list[float | Literal["nan", "inf", "-inf"]]
    result: SensitivityResult
    authority_purpose: Literal["exploratory_parameter_experiment"] = (
        "exploratory_parameter_experiment"
    )
    evaluator_provenance: Literal["not_established"] = "not_established"
    population_law_status: Literal["not_established"] = "not_established"


def _replay_plan(plan: SensitivityPlan) -> SensitivityPlan:
    """Require replay inputs without changing legacy in-process analysis rules."""
    plan = _admit_sensitivity_analysis_plan(plan)
    if plan.seed is None:
        raise ValueError("Persisted DOE analysis requires an explicit replay seed")
    if plan.method == SensitivityMethod.SOBOL and plan.input_law != "independent":
        raise ValueError("Persisted Sobol analysis requires a declared independent input law")
    _require_bound_backend({"backend_identity": _backend_identity(plan)})
    return plan


def _require_bound_backend(identity: dict[str, object]) -> None:
    backend = identity["backend_identity"]
    if not isinstance(backend, dict) or backend.get("distribution") != _SALIB_BACKEND_ID:
        raise ValueError("DOE replay backend profile is not established")
    for role in ("sampler", "analyzer", "analysis_owner", "sampling_owner"):
        binding = backend.get(role)
        if not isinstance(binding, dict) or binding.get("basis") != "recomputed":
            raise ValueError("DOE direct numerical implementation is not established")


def _admit_seeded_experiment(plan: SensitivityPlan, samples: np.ndarray) -> None:
    """Recompute the complete selected design, admitting only whole-block permutations."""
    from .sampling import generate_sensitivity_samples

    expected = generate_sensitivity_samples(plan)
    if np.array_equal(samples, expected):
        return
    block_size = (
        plan.num_parameters + 1
        if plan.method == SensitivityMethod.MORRIS
        else 2 * plan.num_parameters + 2
    )
    if samples.shape == expected.shape and samples.shape[0] % block_size == 0:
        actual = np.array(samples, dtype="<f8", order="C", copy=True)
        canonical = np.array(expected, dtype="<f8", order="C", copy=True)
        actual[actual == 0.0] = 0.0
        canonical[canonical == 0.0] = 0.0
        actual_blocks = Counter(
            block.tobytes() for block in actual.reshape(-1, block_size, plan.num_parameters)
        )
        expected_blocks = Counter(
            block.tobytes() for block in canonical.reshape(-1, block_size, plan.num_parameters)
        )
        if actual_blocks == expected_blocks:
            return
    raise ValueError("DOE samples do not reconcile to the complete seeded experiment")


def _persist_analysis(
    store: core_artifacts.ArtifactStore,
    plan: SensitivityPlan,
    samples: np.ndarray,
    outputs: np.ndarray,
    result: SensitivityResult,
) -> core_artifacts.ArtifactRef:
    """Persist complete ordered rows and their actual source-bound analysis."""
    plan = _replay_plan(plan)
    from polisyos.core import artifacts as core_artifacts
    from polisyos.core import canon as core_canon

    _admit_seeded_experiment(plan, samples)
    result = SensitivityResult.model_validate(result.model_dump(mode="python"))
    identity = _analysis_identity(plan, samples, outputs)
    _require_bound_backend(identity)
    if any(result.metadata.get(key) != value for key, value in identity.items()):
        raise ValueError("Sensitivity result does not bind the supplied ordered experiment")
    receipt = _AnalysisReceipt.model_validate(
        {
            "plan": plan,
            "samples": _array_payload(samples),
            "outputs": _array_payload(outputs),
            "result": result,
        }
    )
    return store.put_json(
        receipt.model_dump(mode="python"),
        core_artifacts.ArtifactWriteOptions(
            kind=receipt.ARTIFACT_KIND,
            media_type=receipt.ARTIFACT_MEDIA_TYPE,
            schema=core_artifacts.SchemaInfo(
                name=receipt.ARTIFACT_SCHEMA_NAME, version=receipt.ARTIFACT_SCHEMA_VERSION
            ),
        ),
        canon_spec=core_canon.CanonSpec(forbid_floats=False, exclude_none=False),
        return_selected_profile=True,
    )


def _load_analysis(
    store: core_artifacts.ArtifactReader,
    ref: core_artifacts.ArtifactRef,
    *,
    limits: CoreJsonReadLimits | None = None,
) -> SensitivityResult:
    """Resolve a full selected view and reproduce it before search consumption."""
    from polisyos.core.artifacts.canonical_profile import (
        CoreJsonReadLimits,
        read_core_json_artifact_bounded,
        validate_core_model_bounded_read,
    )

    limits = limits or CoreJsonReadLimits(
        max_bytes=16 * 1024 * 1024,
        max_depth=64,
        max_elements=1_000_000,
        max_manifest_bytes=1024 * 1024,
    )
    read = read_core_json_artifact_bounded(store, ref, limits=limits)
    receipt = validate_core_model_bounded_read(_AnalysisReceipt, read)
    plan = _replay_plan(receipt.plan)
    samples = np.asarray(receipt.samples, dtype=float)
    outputs = np.asarray(receipt.outputs, dtype=float)
    _admit_seeded_experiment(plan, samples)
    identity = _analysis_identity(plan, samples, outputs)
    _require_bound_backend(identity)
    if any(receipt.result.metadata.get(key) != value for key, value in identity.items()):
        raise ValueError("Persisted DOE sensitivity result does not bind its experiment")
    reproduced = analyze_sensitivity(plan, samples, outputs)
    if reproduced.model_dump(mode="python") != receipt.result.model_dump(mode="python"):
        raise ValueError("Persisted DOE sensitivity result does not reproduce")
    return reproduced
