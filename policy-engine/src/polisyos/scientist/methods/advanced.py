"""Scientist C7 adapters for advanced econometric and sensitivity bundles."""

from __future__ import annotations

import importlib
import logging
import threading
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import numpy as np

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.foundry.methods.catalog.ml.protocols import (
    ClusteringResult,
    SurvivalData,
    SurvivalResult,
    TabularData,
)
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.observation.bundles import (
    AgentFactorEmbeddingsBundleManifest,
    BilevelProblemBundle,
    BundleAxisSemantic,
    BundleLineageRef,
    CellPrototypeEmbeddingsBundleManifest,
    ContractCompatibilityTarget,
    HeckmanCorrectionBundle,
    RequiredArraySpec,
    RequiredColumnSpec,
    SobolDiagnosticsBundle,
    SpecificationCurveDiagnosticsBundle,
    SurvivalHazardBundle,
)
from polisyos.ir.observation.contract_compilers import (
    SpecificationCurveInput,
    write_json_bundle,
    write_npz_payload,
    write_parquet_rows,
)

from polisyos.scientist.compute.runner import MethodBackend, MethodRuntimeProviders

if TYPE_CHECKING:
    from polisyos.ir.kernel.base import KernelModel

_LOGGER = logging.getLogger(__name__)

_RESERVED_ID_FIELDS = {
    "agent_id",
    "firm_id",
    "cell_id",
    "household_cell_id",
    "period_id",
    "period_start",
    "period_end",
    "source_id",
    "source_version",
}

_HECKMAN_TARGET = ContractCompatibilityTarget(
    contract_id="econometrics.selection.heckman@1.0.0",
    contract_fqn="polisyos.foundry.methods.catalog.econometrics.selection.HeckmanSelectionEstimator",
)
_SURVIVAL_RESULT_TARGET = ContractCompatibilityTarget(
    contract_id="foundry.ml.survival_result.v1",
    contract_fqn="polisyos.foundry.methods.catalog.ml.protocols.SurvivalResult",
)
_METHOD_MODULES = {
    "econometrics.factor": "polisyos.foundry.methods.catalog.econometrics.factor_models",
    "ml.clustering": "polisyos.foundry.methods.catalog.ml.clustering",
    "optimization.bilevel": "polisyos.foundry.methods.catalog.optimization.advanced_stochastic",
    "econometrics.selection": "polisyos.foundry.methods.catalog.econometrics.selection",
    "ml.survival": "polisyos.foundry.methods.catalog.ml.survival",
    "sensitivity.global": "polisyos.foundry.methods.catalog.sensitivity",
    "sensitivity.specification": "polisyos.foundry.methods.catalog.sensitivity.specification",
}
_METHOD_MODULE_LOAD_LOCK = threading.RLock()


@dataclass(frozen=True)
class C7AdvancedInputs:
    """Input contract for the Scientist C7 advanced-method suite.

    Bundles the panel slices, survival contract, and sensitivity payloads
    needed to materialize the seven advanced artifacts emitted by
    :func:`run_c7_advanced_suite`.

    Key fields:
        agent_panel_rows: Agent-period rows used for latent-factor embeddings
        firm_panel_rows: Firm-period rows used for Heckman and survival runs
        cell_rows: Cell-level rows used to derive prototype clusters
        survival_contract: Prepared survival-analysis design matrix
        sobol_targets: Per-target Monte Carlo payloads for Sobol diagnostics
        intervention_knobs: Policy search knob magnitudes for bilevel setup
    """

    agent_panel_rows: Sequence[Mapping[str, Any]]
    firm_panel_rows: Sequence[Mapping[str, Any]]
    cell_rows: Sequence[Mapping[str, Any]]
    household_cell_rows: Sequence[Mapping[str, Any]]
    survival_contract: SurvivalData
    survival_row_metadata: Sequence[Mapping[str, Any]]
    specification_curve_input: SpecificationCurveInput
    sobol_targets: Mapping[str, Mapping[str, Any]]
    intervention_knobs: Mapping[str, float]
    bilevel_ambiguity_mode: str = "auto"
    bilevel_tie_break: str | None = None
    bilevel_delta_near_opt: float = 0.0
    bilevel_certificate_mode: str = "residual_or_bounds"
    calibration_cut_period: str | None = None
    temporal_embedding_mode: str = "pca"
    seed: int = 20260328
    agent_feature_fields: tuple[str, ...] = ()
    cell_feature_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class C7PersistedArtifact:
    """Manifest, CAS reference, and method evidence for one C7 artifact."""

    artifact_name: str
    bundle_ref: ArtifactRef
    manifest: KernelModel
    method_result_refs: tuple[ArtifactRef, ...] = ()
    method_evidence_refs: tuple[ArtifactRef, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class C7AdvancedSuiteResult:
    """Collection of persisted artifacts emitted by the C7 advanced suite.

    Each field points to the canonical bundle for one advanced-method family,
    allowing downstream governance and reporting code to dereference the full
    C7 surface without guessing artifact names.
    """

    factor_embeddings: C7PersistedArtifact
    cell_prototypes: C7PersistedArtifact
    bilevel_problem: C7PersistedArtifact
    heckman_correction: C7PersistedArtifact
    survival_hazards: C7PersistedArtifact
    sobol_diagnostics: C7PersistedArtifact
    specification_curve: C7PersistedArtifact

    def bundle_refs(self) -> dict[str, ArtifactRef]:
        """Return a stable artifact-name to bundle-ref mapping for CAS lookups."""

        return {
            "factor_embeddings": self.factor_embeddings.bundle_ref,
            "cell_prototypes": self.cell_prototypes.bundle_ref,
            "bilevel_problem": self.bilevel_problem.bundle_ref,
            "heckman_correction": self.heckman_correction.bundle_ref,
            "survival_hazards": self.survival_hazards.bundle_ref,
            "sobol_diagnostics": self.sobol_diagnostics.bundle_ref,
            "specification_curve": self.specification_curve.bundle_ref,
        }


def _coerce_float(value: Any) -> float:
    if value is None:
        return 0.0
    return float(value)


def _period_key(row: Mapping[str, Any]) -> str:
    if row.get("period_id") is not None:
        return str(row["period_id"])
    if row.get("period_start") is not None:
        return str(row["period_start"])
    return ""


def _numeric_feature_fields(
    rows: Sequence[Mapping[str, Any]],
    *,
    exclude: set[str] | None = None,
    preferred: Sequence[str] = (),
) -> tuple[str, ...]:
    exclusions = set(exclude or set())
    if preferred:
        present = [field for field in preferred if any(field in row for row in rows)]
        if present:
            return tuple(present)
    candidates: list[str] = []
    if not rows:
        return ()
    for key in rows[0]:
        if key in exclusions:
            continue
        if all(
            row.get(key) is None
            or isinstance(row.get(key), (bool, int, float, np.bool_, np.integer, np.floating))
            for row in rows
        ):
            candidates.append(key)
    return tuple(candidates)


def _rows_to_matrix(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> np.ndarray:
    return cast(
        "np.ndarray",
        np.asarray(
            [[_coerce_float(row.get(field)) for field in fields] for row in rows],
            dtype=float,
        ).astype(float, copy=False),
    )


def _artifact_kind(artifact_name: str) -> str:
    stem = artifact_name.rsplit(".", 1)[0]
    return f"scientist.c7.{stem}"


def _persist_bytes(
    store: FileSystemCAS,
    *,
    artifact_name: str,
    media_type: str,
    payload: bytes,
    schema_name: str,
    schema_version: str,
    inputs: Sequence[ArtifactRef] = (),
) -> ArtifactRef:
    return store.put_bytes(
        payload,
        PutOptions(
            kind=_artifact_kind(artifact_name),
            media_type=media_type,
            schema=SchemaInfo(name=schema_name, version=schema_version),
            inputs=[
                InputRef(artifact_id=ref.artifact_id, role=f"upstream:{index}")
                for index, ref in enumerate(inputs)
            ],
        ),
    )


def _persist_json_model(
    store: FileSystemCAS,
    *,
    bundle: KernelModel,
    inputs: Sequence[ArtifactRef] = (),
) -> ArtifactRef:
    with TemporaryDirectory() as tmpdir:
        path = write_json_bundle(bundle, Path(tmpdir) / bundle.artifact_name)
        return _persist_bytes(
            store,
            artifact_name=bundle.artifact_name,
            media_type="application/json",
            payload=path.read_bytes(),
            schema_name=bundle.__class__.__name__,
            schema_version=str(getattr(bundle, "schema_version", "1.0")),
            inputs=inputs,
        )


def _persist_npz_payload(
    store: FileSystemCAS,
    *,
    artifact_name: str,
    payload: Mapping[str, Any],
    manifest: KernelModel,
    inputs: Sequence[ArtifactRef] = (),
) -> ArtifactRef:
    with TemporaryDirectory() as tmpdir:
        path = write_npz_payload(payload, Path(tmpdir) / artifact_name)
        return _persist_bytes(
            store,
            artifact_name=artifact_name,
            media_type="application/x-npz",
            payload=path.read_bytes(),
            schema_name=manifest.__class__.__name__,
            schema_version=str(getattr(manifest, "schema_version", "1.0")),
            inputs=inputs,
        )


def _persist_parquet_rows_bundle(
    store: FileSystemCAS,
    *,
    artifact_name: str,
    rows: Sequence[Mapping[str, Any]],
    manifest: KernelModel,
    inputs: Sequence[ArtifactRef] = (),
) -> ArtifactRef:
    with TemporaryDirectory() as tmpdir:
        path = write_parquet_rows(rows, Path(tmpdir) / artifact_name)
        return _persist_bytes(
            store,
            artifact_name=artifact_name,
            media_type="application/parquet",
            payload=path.read_bytes(),
            schema_name=manifest.__class__.__name__,
            schema_version=str(getattr(manifest, "schema_version", "1.0")),
            inputs=inputs,
        )


class _AdvancedMethodBase:
    def __init__(
        self,
        store: FileSystemCAS,
        backend: MethodBackend | None = None,
        *,
        method_registry: MethodRegistry | None = None,
        method_registry_provider: Callable[[], MethodRegistry] | None = None,
    ) -> None:
        self.store = store
        self.backend = backend or MethodBackend()
        self._method_registry = method_registry
        if method_registry_provider is not None:
            self._method_registry_provider = method_registry_provider
        elif method_registry is not None:
            self._method_registry_provider = lambda: method_registry
        else:
            self._method_registry_provider = None

    def _run_method(
        self,
        *,
        method_fqn: str,
        input_state: Any,
        method_params: Mapping[str, Any],
        seed: int,
        input_refs: Mapping[str, ArtifactRef] | None = None,
    ) -> tuple[dict[str, Any], ArtifactRef, ArtifactRef]:
        _ensure_method_module_loaded(
            method_fqn,
            registry=self._method_registry,
            registry_provider=self._method_registry_provider,
        )
        execution = self.backend.run(
            cas_root=self.store.root,
            method_fqn=method_fqn,
            method_version=None,
            input_state=input_state,
            method_params=method_params,
            seed=seed,
            input_refs=input_refs,
        )
        final_state = execution.final_state
        payload = dict(final_state) if isinstance(final_state, Mapping) else {"result": final_state}
        return (
            payload,
            execution.exec_artifacts.result_ref,
            execution.exec_artifacts.evidence_ref,
        )


def _ensure_method_module_loaded(
    method_fqn: str,
    *,
    registry: MethodRegistry | None = None,
    registry_provider: Callable[[], MethodRegistry] | None = None,
) -> None:
    for namespace, module_name in _METHOD_MODULES.items():
        if method_fqn.startswith(namespace):
            with _METHOD_MODULE_LOAD_LOCK:
                module = importlib.import_module(module_name)
                if registry is not None:
                    resolved_registry = registry
                elif registry_provider is not None:
                    resolved_registry = registry_provider()
                else:
                    resolved_registry = _default_method_registry()
                for attr_name in dir(module):
                    candidate = getattr(module, attr_name)
                    if (
                        isinstance(candidate, type)
                        and hasattr(candidate, "signature")
                        and hasattr(candidate, "pure_step")
                    ):
                        try:
                            resolved_registry.register(candidate)
                        except Exception as exc:
                            _LOGGER.debug(
                                "advanced_methods_registry_register_failed method=%s attr=%s error=%s",
                                method_fqn,
                                attr_name,
                                exc,
                            )
                            continue
            return


def _default_method_registry() -> MethodRegistry:
    return MethodRegistry.get_instance()


class FactorModelEmbeddingBuilder(_AdvancedMethodBase):
    """Build latent agent embeddings from agent-panel trajectories.

    Chooses either PCA or a dynamic-factor backend based on
    ``inputs.temporal_embedding_mode`` and persists the resulting
    ``AgentFactorEmbeddingsBundleManifest`` to CAS.
    """

    def run(self, inputs: C7AdvancedInputs) -> C7PersistedArtifact:
        sorted_rows = sorted(
            inputs.agent_panel_rows,
            key=lambda row: (str(row.get("agent_id", "")), _period_key(row)),
        )
        feature_fields = inputs.agent_feature_fields or _numeric_feature_fields(
            sorted_rows,
            exclude=_RESERVED_ID_FIELDS,
            preferred=(
                "income",
                "employment_score",
                "consumption",
                "distress_signal",
                "network_exposure",
            ),
        )
        if not feature_fields:
            raise ValueError(
                "agent panel must include numeric feature fields for factor embeddings"
            )
        matrix = _rows_to_matrix(sorted_rows, feature_fields)
        n_factors = max(1, min(4, matrix.shape[1], matrix.shape[0]))
        method_fqn = (
            "econometrics.factor.dynamic_factor_model@1.0.0"
            if inputs.temporal_embedding_mode == "dynamic"
            else "econometrics.factor.principal_components@1.0.0"
        )
        result, method_result_ref, method_evidence_ref = self._run_method(
            method_fqn=method_fqn,
            input_state=SimpleNamespace(exog=matrix),
            method_params={"n_factors": n_factors},
            seed=inputs.seed,
        )
        factor_scores = np.asarray(result["factor_scores"], dtype=float)
        factor_loadings = np.asarray(result["factor_loadings"], dtype=float)
        explained = np.asarray(result["explained_var_ratio"], dtype=float)[: factor_scores.shape[1]]
        grouped: dict[str, list[np.ndarray]] = defaultdict(list)
        for row, score in zip(sorted_rows, factor_scores, strict=True):
            grouped[str(row["agent_id"])].append(np.asarray(score, dtype=float))
        agent_ids = np.asarray(sorted(grouped), dtype=str)
        embeddings = np.vstack(
            [np.mean(np.vstack(grouped[agent_id]), axis=0) for agent_id in agent_ids]
        )
        manifest = AgentFactorEmbeddingsBundleManifest(
            required_arrays=[
                RequiredArraySpec(name="agent_ids", axes=["agent"], dtype="string"),
                RequiredArraySpec(name="embeddings", axes=["agent", "factor"], dtype="float64"),
                RequiredArraySpec(
                    name="factor_loadings", axes=["variable", "factor"], dtype="float64"
                ),
                RequiredArraySpec(
                    name="explained_variance_ratio",
                    axes=["factor"],
                    dtype="float64",
                ),
            ],
            axis_semantics=[
                BundleAxisSemantic(axis="agent", description="Unique agent embedding axis"),
                BundleAxisSemantic(axis="factor", description="Latent factor dimension"),
                BundleAxisSemantic(axis="variable", description="Observed input feature dimension"),
            ],
            lineage=[
                BundleLineageRef(
                    source_artifact="agent_panel",
                    notes=["agent-period feature matrix aggregated back to agent embeddings"],
                )
            ],
            embedding_method=method_fqn,
            contract_payload={
                "feature_fields": list(feature_fields),
                "n_factors": int(embeddings.shape[1]),
            },
        )
        bundle_ref = _persist_npz_payload(
            self.store,
            artifact_name=manifest.artifact_name,
            payload={
                "agent_ids": agent_ids,
                "embeddings": embeddings,
                "factor_loadings": factor_loadings,
                "explained_variance_ratio": explained,
            },
            manifest=manifest,
            inputs=(method_result_ref, method_evidence_ref),
        )
        return C7PersistedArtifact(
            artifact_name=manifest.artifact_name,
            bundle_ref=bundle_ref,
            manifest=manifest,
            method_result_refs=(method_result_ref,),
            method_evidence_refs=(method_evidence_ref,),
            metadata={
                "agent_count": int(agent_ids.shape[0]),
                "feature_fields": list(feature_fields),
            },
        )


class CellPrototypeBuilder(_AdvancedMethodBase):
    """Cluster cells into reusable prototypes enriched with household features."""

    def run(self, inputs: C7AdvancedInputs) -> C7PersistedArtifact:
        cell_rows = sorted(inputs.cell_rows, key=lambda row: str(row.get("cell_id", "")))
        cell_feature_fields = inputs.cell_feature_fields or _numeric_feature_fields(
            cell_rows,
            exclude=_RESERVED_ID_FIELDS,
            preferred=(
                "population",
                "employment",
                "output",
                "distress_score",
                "public_service_index",
            ),
        )
        if not cell_feature_fields:
            raise ValueError("cell rows must include numeric feature fields for clustering")
        hh_numeric_fields = _numeric_feature_fields(
            inputs.household_cell_rows,
            exclude=_RESERVED_ID_FIELDS - {"cell_id"},
            preferred=(
                "household_count",
                "disposable_income",
                "poverty_rate",
                "transfer_intensity",
            ),
        )
        hh_aggregates: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        hh_counts: dict[str, int] = defaultdict(int)
        for row in inputs.household_cell_rows:
            cell_id = str(row.get("cell_id", ""))
            hh_counts[cell_id] += 1
            for field_name in hh_numeric_fields:
                hh_aggregates[cell_id][field_name] += _coerce_float(row.get(field_name))
        merged_rows: list[dict[str, Any]] = []
        for row in cell_rows:
            merged = dict(row)
            cell_id = str(row["cell_id"])
            count = max(hh_counts.get(cell_id, 0), 1)
            for field_name in hh_numeric_fields:
                merged[f"hh_{field_name}"] = hh_aggregates[cell_id][field_name] / count
            merged_rows.append(merged)
        feature_fields = tuple(cell_feature_fields) + tuple(
            f"hh_{field}" for field in hh_numeric_fields
        )
        matrix = _rows_to_matrix(merged_rows, feature_fields)
        k = max(2, min(8, matrix.shape[0] - 1))
        result, method_result_ref, method_evidence_ref = self._run_method(
            method_fqn="ml.clustering.kmeans@1.0.0",
            input_state=TabularData(features=matrix, feature_names=list(feature_fields)),
            method_params={"n_clusters": k, "random_state": inputs.seed},
            seed=inputs.seed,
        )
        clustering_result = ClusteringResult.model_validate(result["result"])
        cell_ids = np.asarray([str(row["cell_id"]) for row in merged_rows], dtype=str)
        manifest = CellPrototypeEmbeddingsBundleManifest(
            required_arrays=[
                RequiredArraySpec(name="cell_ids", axes=["cell"], dtype="string"),
                RequiredArraySpec(name="labels", axes=["cell"], dtype="int64"),
                RequiredArraySpec(
                    name="prototype_centers", axes=["prototype", "feature"], dtype="float64"
                ),
            ],
            axis_semantics=[
                BundleAxisSemantic(axis="cell", description="Observed cell axis"),
                BundleAxisSemantic(axis="prototype", description="Cluster centroid axis"),
                BundleAxisSemantic(axis="feature", description="Cell feature axis"),
            ],
            lineage=[
                BundleLineageRef(
                    source_artifact="cell_panel",
                    notes=[
                        "cell features enriched with household-cell aggregates before clustering"
                    ],
                )
            ],
            clustering_method="ml.clustering.kmeans@1.0.0",
            contract_payload={"feature_fields": list(feature_fields), "n_clusters": int(k)},
        )
        bundle_ref = _persist_npz_payload(
            self.store,
            artifact_name=manifest.artifact_name,
            payload={
                "cell_ids": cell_ids,
                "labels": np.asarray(clustering_result.labels, dtype=int),
                "prototype_centers": np.asarray(clustering_result.centers, dtype=float),
            },
            manifest=manifest,
            inputs=(method_result_ref, method_evidence_ref),
        )
        return C7PersistedArtifact(
            artifact_name=manifest.artifact_name,
            bundle_ref=bundle_ref,
            manifest=manifest,
            method_result_refs=(method_result_ref,),
            method_evidence_refs=(method_evidence_ref,),
            metadata={"cell_count": int(cell_ids.shape[0]), "feature_fields": list(feature_fields)},
        )


class BilevelOptimizationAdapter(_AdvancedMethodBase):
    """Compile intervention knob magnitudes into a bilevel optimization bundle."""

    def run(self, inputs: C7AdvancedInputs) -> C7PersistedArtifact:
        method_fqn = "optimization.bilevel.bilevel@1.1.0"
        knob_names = sorted(inputs.intervention_knobs)
        if not knob_names:
            raise ValueError("intervention_knobs must be non-empty")
        magnitudes = np.asarray(
            [abs(_coerce_float(inputs.intervention_knobs[name])) for name in knob_names],
            dtype=float,
        )
        upper_bounds = np.maximum(magnitudes, 1.0)
        n_knobs = upper_bounds.shape[0]
        c_upper = 1.0 + upper_bounds
        c_lower = 0.5 + upper_bounds
        A_upper = np.vstack([np.eye(n_knobs, dtype=float), np.ones((1, n_knobs), dtype=float)])
        b_upper = np.concatenate(
            [upper_bounds, np.asarray([0.6 * np.sum(upper_bounds)], dtype=float)]
        )
        A_lower = np.eye(n_knobs, dtype=float)
        b_lower = upper_bounds
        method_params = {
            "max_iter": 40,
            "step_size": 0.1,
            "ambiguity_mode": inputs.bilevel_ambiguity_mode,
            "tie_break": inputs.bilevel_tie_break,
            "delta_near_opt": float(inputs.bilevel_delta_near_opt),
            "certificate_mode": inputs.bilevel_certificate_mode,
        }
        result, method_result_ref, method_evidence_ref = self._run_method(
            method_fqn=method_fqn,
            input_state={
                "c_upper": c_upper,
                "c_lower": c_lower,
                "A_upper": A_upper,
                "b_upper": b_upper,
                "A_lower": A_lower,
                "b_lower": b_lower,
            },
            method_params=method_params,
            seed=inputs.seed,
        )
        bundle = BilevelProblemBundle(
            optimization_target=method_fqn,
            knob_names=knob_names,
            c_upper=c_upper.tolist(),
            c_lower=c_lower.tolist(),
            A_upper=A_upper.tolist(),
            b_upper=b_upper.tolist(),
            A_lower=A_lower.tolist(),
            b_lower=b_lower.tolist(),
            tie_break=inputs.bilevel_tie_break,
            ambiguity_mode=inputs.bilevel_ambiguity_mode,
            delta_near_opt=float(inputs.bilevel_delta_near_opt),
            certificate_mode=inputs.bilevel_certificate_mode,
            result_summary=dict(result["result"]),
            notes=["v1 box/budget linearization over intervention knobs"],
        )
        bundle_ref = _persist_json_model(
            self.store,
            bundle=bundle,
            inputs=(method_result_ref, method_evidence_ref),
        )
        return C7PersistedArtifact(
            artifact_name=bundle.artifact_name,
            bundle_ref=bundle_ref,
            manifest=bundle,
            method_result_refs=(method_result_ref,),
            method_evidence_refs=(method_evidence_ref,),
            metadata={"knob_names": knob_names},
        )


class HeckmanCorrectionAdapter(_AdvancedMethodBase):
    """Estimate sample-selection corrections over firm panel slices."""

    def run(self, inputs: C7AdvancedInputs) -> C7PersistedArtifact:
        if not inputs.firm_panel_rows:
            raise ValueError("firm_panel_rows must be non-empty")
        periods = sorted({_period_key(row) for row in inputs.firm_panel_rows})
        if not periods:
            raise ValueError("firm_panel_rows must include a period identifier")
        if inputs.calibration_cut_period and inputs.calibration_cut_period in periods:
            current_period = inputs.calibration_cut_period
        else:
            current_period = periods[-2] if len(periods) >= 2 else periods[-1]
        next_period = periods[min(periods.index(current_period) + 1, len(periods) - 1)]
        current_rows = [row for row in inputs.firm_panel_rows if _period_key(row) == current_period]
        next_firms = {
            str(row["firm_id"]) for row in inputs.firm_panel_rows if _period_key(row) == next_period
        }
        outcome_fields = tuple(
            field
            for field in ("employment", "wage_bill", "cell_distress")
            if any(field in row for row in current_rows)
        )
        selection_fields = outcome_fields + tuple(
            field
            for field in ("credit_stress", "prior_distress")
            if any(field in row for row in current_rows)
        )
        if not outcome_fields or not selection_fields:
            raise ValueError(
                "firm_panel_rows must include outcome and selection covariates for Heckman correction"
            )
        X_outcome = _rows_to_matrix(current_rows, outcome_fields)
        X_selection = _rows_to_matrix(current_rows, selection_fields)
        y = np.log1p(
            np.asarray([_coerce_float(row.get("output")) for row in current_rows], dtype=float)
        )
        selected = np.asarray(
            [1.0 if str(row["firm_id"]) in next_firms else 0.0 for row in current_rows],
            dtype=float,
        )
        result, method_result_ref, method_evidence_ref = self._run_method(
            method_fqn="econometrics.selection.heckman@1.0.0",
            input_state={
                "X_outcome": X_outcome,
                "X_selection": X_selection,
                "y": y,
                "selected": selected,
            },
            method_params={},
            seed=inputs.seed,
        )
        summary = dict(result["result"])
        outcome_coefficients = np.asarray(summary["outcome_coefficients"], dtype=float)
        intercept = float(outcome_coefficients[0]) if outcome_coefficients.size else 0.0
        slope = (
            outcome_coefficients[1:]
            if outcome_coefficients.size > 1
            else np.zeros(X_outcome.shape[1], dtype=float)
        )
        corrected_log_output = (
            intercept
            + X_outcome @ slope[: X_outcome.shape[1]]
            + float(summary["lambda_coefficient"]) * selected
        )
        corrected_output = np.expm1(corrected_log_output)
        rows: list[dict[str, Any]] = []
        for row, flag, corrected_log, corrected_level in zip(
            current_rows,
            selected,
            corrected_log_output,
            corrected_output,
            strict=True,
        ):
            rows.append(
                {
                    "firm_id": str(row["firm_id"]),
                    "period_id": current_period,
                    "selected": int(flag),
                    "corrected_log_output": float(corrected_log),
                    "corrected_output": float(corrected_level),
                    "lambda_coefficient": float(summary["lambda_coefficient"]),
                }
            )
        bundle = HeckmanCorrectionBundle(
            contract_target=_HECKMAN_TARGET,
            required_columns=[
                RequiredColumnSpec(name="firm_id", dtype="string"),
                RequiredColumnSpec(name="period_id", dtype="string"),
                RequiredColumnSpec(name="selected", dtype="int"),
                RequiredColumnSpec(name="corrected_log_output", dtype="float"),
                RequiredColumnSpec(name="corrected_output", dtype="float"),
                RequiredColumnSpec(name="lambda_coefficient", dtype="float"),
            ],
            lineage=[
                BundleLineageRef(
                    source_artifact="firm_panel", notes=[f"calibration_cut_period={current_period}"]
                )
            ],
            table_rows=rows,
            contract_payload={
                "outcome_fields": list(outcome_fields),
                "selection_fields": list(selection_fields),
                "summary": summary,
            },
        )
        bundle_ref = _persist_parquet_rows_bundle(
            self.store,
            artifact_name=bundle.artifact_name,
            rows=rows,
            manifest=bundle,
            inputs=(method_result_ref, method_evidence_ref),
        )
        return C7PersistedArtifact(
            artifact_name=bundle.artifact_name,
            bundle_ref=bundle_ref,
            manifest=bundle,
            method_result_refs=(method_result_ref,),
            method_evidence_refs=(method_evidence_ref,),
            metadata={
                "row_count": len(rows),
                "current_period": current_period,
                "next_period": next_period,
            },
        )


class SurvivalModelAdapter(_AdvancedMethodBase):
    """Fit firm hazard scores and persist a survival-hazard contract bundle."""

    def run(self, inputs: C7AdvancedInputs) -> C7PersistedArtifact:
        if len(inputs.survival_row_metadata) != int(inputs.survival_contract.features.shape[0]):
            raise ValueError("survival_row_metadata must align with SurvivalData rows")
        result, method_result_ref, method_evidence_ref = self._run_method(
            method_fqn="ml.survival.survival_analysis@1.0.0",
            input_state=inputs.survival_contract,
            method_params={},
            seed=inputs.seed,
        )
        survival_result = SurvivalResult.model_validate(result["result"])
        risk_scores = np.asarray(survival_result.risk_scores, dtype=float)
        rows: list[dict[str, Any]] = []
        latest_hazard_by_firm: dict[str, float] = {}
        ordered_pairs = sorted(
            zip(inputs.survival_row_metadata, risk_scores, strict=True),
            key=lambda item: (str(item[0].get("firm_id", "")), str(item[0].get("period_id", ""))),
        )
        for meta, risk_score in ordered_pairs:
            firm_id = str(meta["firm_id"])
            latest_hazard_by_firm[firm_id] = float(risk_score)
            rows.append(
                {
                    "firm_id": firm_id,
                    "period_id": str(meta["period_id"]),
                    "risk_score": float(risk_score),
                    "event": int(meta.get("event", 0)),
                }
            )
        bundle = SurvivalHazardBundle(
            contract_target=_SURVIVAL_RESULT_TARGET,
            required_columns=[
                RequiredColumnSpec(name="firm_id", dtype="string"),
                RequiredColumnSpec(name="period_id", dtype="string"),
                RequiredColumnSpec(name="risk_score", dtype="float"),
                RequiredColumnSpec(name="event", dtype="int"),
            ],
            lineage=[BundleLineageRef(source_artifact="survival_data_bundle_v1.parquet")],
            table_rows=rows,
            contract_payload={
                "latest_hazard_by_firm": latest_hazard_by_firm,
                "concordance_index": survival_result.concordance_index,
                "coefficients": dict(survival_result.coefficients),
            },
        )
        bundle_ref = _persist_parquet_rows_bundle(
            self.store,
            artifact_name=bundle.artifact_name,
            rows=rows,
            manifest=bundle,
            inputs=(method_result_ref, method_evidence_ref),
        )
        return C7PersistedArtifact(
            artifact_name=bundle.artifact_name,
            bundle_ref=bundle_ref,
            manifest=bundle,
            method_result_refs=(method_result_ref,),
            method_evidence_refs=(method_evidence_ref,),
            metadata={"row_count": len(rows), "firm_count": len(latest_hazard_by_firm)},
        )


class SobolDiagnosticsAdapter(_AdvancedMethodBase):
    """Assemble first-order Sobol sensitivity diagnostics across targets."""

    def run(self, inputs: C7AdvancedInputs) -> C7PersistedArtifact:
        target_names = sorted(inputs.sobol_targets)
        if not target_names:
            raise ValueError("sobol_targets must be non-empty")
        source_combination_ids: list[str] | None = None
        first_order_rows: list[list[float]] = []
        variance: list[float] = []
        method_result_refs: list[ArtifactRef] = []
        method_evidence_refs: list[ArtifactRef] = []
        for offset, target_name in enumerate(target_names):
            payload = dict(inputs.sobol_targets[target_name])
            candidate_ids = [str(item) for item in payload["source_combination_ids"]]
            if source_combination_ids is None:
                source_combination_ids = candidate_ids
            elif candidate_ids != source_combination_ids:
                raise ValueError(
                    "all sobol targets must share the same source_combination_ids ordering"
                )
            result, method_result_ref, method_evidence_ref = self._run_method(
                method_fqn="sensitivity.global.sobol_first_order@1.0.0",
                input_state={
                    "outputs_a": np.asarray(payload["outputs_a"], dtype=float),
                    "outputs_b": np.asarray(payload["outputs_b"], dtype=float),
                    "mixed_outputs": np.asarray(payload["mixed_outputs"], dtype=float),
                },
                method_params={},
                seed=inputs.seed + offset,
            )
            summary = dict(result["result"])
            first_order_rows.append([float(value) for value in summary["first_order_indices"]])
            variance.append(float(summary["variance"]))
            method_result_refs.append(method_result_ref)
            method_evidence_refs.append(method_evidence_ref)
        bundle = SobolDiagnosticsBundle(
            target_names=target_names,
            source_combination_ids=source_combination_ids or [],
            first_order_indices=first_order_rows,
            variance=variance,
            notes=["one target per method call; matrix assembled in repeated-run protocol"],
        )
        bundle_ref = _persist_json_model(
            self.store,
            bundle=bundle,
            inputs=(*method_result_refs, *method_evidence_refs),
        )
        return C7PersistedArtifact(
            artifact_name=bundle.artifact_name,
            bundle_ref=bundle_ref,
            manifest=bundle,
            method_result_refs=tuple(method_result_refs),
            method_evidence_refs=tuple(method_evidence_refs),
            metadata={
                "target_count": len(target_names),
                "source_combination_ids": list(source_combination_ids or []),
            },
        )


class SpecificationCurveAdapter(_AdvancedMethodBase):
    """Persist specification-curve diagnostics for robustness reporting."""

    def run(self, inputs: C7AdvancedInputs) -> C7PersistedArtifact:
        result, method_result_ref, method_evidence_ref = self._run_method(
            method_fqn="sensitivity.specification.specification_curve@1.0.0",
            input_state=inputs.specification_curve_input,
            method_params={},
            seed=inputs.seed,
        )
        summary = dict(result["result"])
        bundle = SpecificationCurveDiagnosticsBundle(
            specification_ids=list(inputs.specification_curve_input.specification_ids),
            sorted_estimates=[float(value) for value in summary["sorted_estimates"]],
            share_significant=float(summary["share_significant"]),
            sign_consistency=float(summary["sign_consistency"]),
            notes=["diagnostics summary persisted separately from specification_curve_input"],
        )
        bundle_ref = _persist_json_model(
            self.store,
            bundle=bundle,
            inputs=(method_result_ref, method_evidence_ref),
        )
        return C7PersistedArtifact(
            artifact_name=bundle.artifact_name,
            bundle_ref=bundle_ref,
            manifest=bundle,
            method_result_refs=(method_result_ref,),
            method_evidence_refs=(method_evidence_ref,),
            metadata={"specification_count": len(bundle.specification_ids)},
        )


def run_c7_advanced_suite(
    store: FileSystemCAS,
    *,
    inputs: C7AdvancedInputs,
    backend: MethodBackend | None = None,
    method_registry: MethodRegistry | None = None,
    method_runtime_providers: MethodRuntimeProviders | None = None,
) -> C7AdvancedSuiteResult:
    """Run the full C7 advanced-method bundle build in a fixed order.

    Args:
        store: CAS store used to persist all intermediate method outputs.
        inputs: Normalized C7 payload shared across advanced adapters.

    Returns:
        A ``C7AdvancedSuiteResult`` containing bundle references for factor
        embeddings, prototypes, bilevel optimization, selection correction,
        survival hazards, Sobol diagnostics, and specification-curve outputs.
    """

    registry_provider: Callable[[], MethodRegistry] | None = None
    if method_registry is not None:
        resolved_registry = method_registry

        def _registry_provider() -> MethodRegistry:
            return resolved_registry

        registry_provider = _registry_provider
    elif method_runtime_providers is not None:
        registry_provider = method_runtime_providers.registry_provider

    resolved_backend = backend or MethodBackend(
        providers=method_runtime_providers,
        registry_provider=registry_provider,
    )
    factor_embeddings = FactorModelEmbeddingBuilder(
        store,
        resolved_backend,
        method_registry=method_registry,
        method_registry_provider=registry_provider,
    ).run(inputs)
    cell_prototypes = CellPrototypeBuilder(
        store,
        resolved_backend,
        method_registry=method_registry,
        method_registry_provider=registry_provider,
    ).run(inputs)
    bilevel_problem = BilevelOptimizationAdapter(
        store,
        resolved_backend,
        method_registry=method_registry,
        method_registry_provider=registry_provider,
    ).run(inputs)
    heckman_correction = HeckmanCorrectionAdapter(
        store,
        resolved_backend,
        method_registry=method_registry,
        method_registry_provider=registry_provider,
    ).run(inputs)
    survival_hazards = SurvivalModelAdapter(
        store,
        resolved_backend,
        method_registry=method_registry,
        method_registry_provider=registry_provider,
    ).run(inputs)
    sobol_diagnostics = SobolDiagnosticsAdapter(
        store,
        resolved_backend,
        method_registry=method_registry,
        method_registry_provider=registry_provider,
    ).run(inputs)
    specification_curve = SpecificationCurveAdapter(
        store,
        resolved_backend,
        method_registry=method_registry,
        method_registry_provider=registry_provider,
    ).run(inputs)
    return C7AdvancedSuiteResult(
        factor_embeddings=factor_embeddings,
        cell_prototypes=cell_prototypes,
        bilevel_problem=bilevel_problem,
        heckman_correction=heckman_correction,
        survival_hazards=survival_hazards,
        sobol_diagnostics=sobol_diagnostics,
        specification_curve=specification_curve,
    )


__all__ = [
    "BilevelOptimizationAdapter",
    "C7AdvancedInputs",
    "C7AdvancedSuiteResult",
    "C7PersistedArtifact",
    "CellPrototypeBuilder",
    "FactorModelEmbeddingBuilder",
    "HeckmanCorrectionAdapter",
    "SobolDiagnosticsAdapter",
    "SpecificationCurveAdapter",
    "SurvivalModelAdapter",
    "run_c7_advanced_suite",
]
