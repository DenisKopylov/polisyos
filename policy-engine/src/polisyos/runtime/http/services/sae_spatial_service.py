"""Runtime orchestration for spatial small-area estimation endpoints."""
from __future__ import annotations

from io import BytesIO
from typing import Any

from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon.canon_json import CanonSpec
from polisyos.core.contracts.control import CausalFrontierSAERequest
from polisyos.core.governance.passes.base import PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.foundry.methods.catalog.survey.causal_frontier import CausalFrontierFayHerriotEstimator
from polisyos.foundry.methods.catalog.survey.causal_frontier_calibration import (
    calibrate_boundary_leakage_thresholds,
)
from polisyos.foundry.methods.catalog.survey.causal_frontier_io import (
    build_causal_frontier_state_from_records,
    load_causal_frontier_bundle,
    result_to_estimates_frame,
    write_output_bundle,
)
from polisyos.foundry.methods.catalog.survey.protocols import SAEResult
from polisyos.scientist.governance.passes.causal_frontier_leakage_pass import (
    CausalFrontierLeakagePass,
)


class SAESpatialService:
    """Runtime-facing orchestration for causal-frontier SAE bundle execution."""

    def __init__(self, *, store: Any) -> None:
        self._store = store

    def estimate_causal_frontier(
        self,
        request: CausalFrontierSAERequest,
    ) -> dict[str, Any]:
        state, contract_metadata = self._load_request_state(request)
        if request.persist_artifacts:
            state["artifact_store"] = ensure_ir_artifact_store(self._store)

        params = {
            "lambda_spatial": request.lambda_spatial,
            "component_ridge": request.component_ridge,
            "contrast_eps": request.contrast_eps,
            "green_threshold": request.green_threshold,
            "red_threshold": request.red_threshold,
        }
        result = CausalFrontierFayHerriotEstimator.pure_step(state, params)["result"]
        if request.calibration_reps > 0:
            calibration = calibrate_boundary_leakage_thresholds(
                state,
                lambda_spatial=request.lambda_spatial,
                component_ridge=request.component_ridge,
                contrast_eps=request.contrast_eps,
                reps=request.calibration_reps,
                seed=request.calibration_seed,
            )
            result = _apply_calibration(result, calibration)

        profile = _resolve_profile(request.governance_profile)
        issues = CausalFrontierLeakagePass().validate(
            PassContext(
                ir=None,
                state={"result": result},
                registry_bundle=None,
                profile=profile,
                run_id="R_runtime_causal_frontier_sae",
            )
        )
        diagnostics = dict(result.statistics.get("diagnostics", {}))
        governance_artifact = _build_governance_artifact(
            result=result,
            input_metadata=contract_metadata,
            issues=issues,
        )
        estimates = result_to_estimates_frame(result)

        output_bundle = {}
        if request.output_dir is not None:
            output_bundle = write_output_bundle(
                request.output_dir,
                estimates=estimates,
                diagnostics=diagnostics,
                governance_artifact=governance_artifact,
            )

        output_refs = {
            "dependence_ref": _artifact_ref_from_payload(result.dependence_ref),
            "quality_certificate_ref": _artifact_ref_from_payload(result.quality_certificate_ref),
            "sae_estimates_ref": None,
            "causal_diagnostics_ref": None,
            "governance_artifact_ref": None,
        }
        if request.persist_artifacts:
            output_refs.update(
                self._persist_output_artifacts(
                    estimates=estimates,
                    diagnostics=diagnostics,
                    governance_artifact=governance_artifact,
                )
            )

        return {
            "result": result,
            "diagnostics": diagnostics,
            "governance_artifact": governance_artifact,
            "estimates": estimates,
            "output_bundle": output_bundle,
            "output_refs": output_refs,
        }

    def _persist_output_artifacts(
        self,
        *,
        estimates: Any,
        diagnostics: dict[str, Any],
        governance_artifact: dict[str, Any],
    ) -> dict[str, ArtifactRef | None]:
        buffer = BytesIO()
        estimates.to_parquet(buffer, index=False)
        estimates_ref = self._store.put_bytes(
            buffer.getvalue(),
            ArtifactWriteOptions(
                kind="survey.sae_estimates_bundle",
                media_type="application/x-parquet",
            ),
        )
        diagnostics_ref = self._store.put_json(
            diagnostics,
            ArtifactWriteOptions(
                kind="survey.causal_frontier_diagnostics",
                media_type="application/json",
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        governance_ref = self._store.put_json(
            governance_artifact,
            ArtifactWriteOptions(
                kind="scientist.governance_artifact",
                media_type="application/json",
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        return {
            "sae_estimates_ref": ArtifactRef.model_validate(estimates_ref.model_dump(mode="json")),
            "causal_diagnostics_ref": ArtifactRef.model_validate(diagnostics_ref.model_dump(mode="json")),
            "governance_artifact_ref": ArtifactRef.model_validate(governance_ref.model_dump(mode="json")),
        }

    @staticmethod
    def _load_request_state(
        request: CausalFrontierSAERequest,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if request.bundle_dir is not None:
            return load_causal_frontier_bundle(
                request.bundle_dir,
                covariate_columns=request.covariate_columns,
                add_intercept=request.add_intercept,
            )
        return build_causal_frontier_state_from_records(
            areas=[item.model_dump(mode="json") for item in request.areas],
            edges=[item.model_dump(mode="json") for item in request.edges],
            exposure=[item.model_dump(mode="json") for item in request.exposure] or None,
            metadata=dict(request.metadata),
            covariate_columns=request.covariate_columns,
            add_intercept=request.add_intercept,
        )


def _resolve_profile(profile_name: str) -> ValidationProfile:
    if profile_name == "fast":
        return ValidationProfile.fast()
    if profile_name == "strict":
        return ValidationProfile.strict()
    return ValidationProfile.mvp()


def _apply_calibration(result: SAEResult, calibration: dict[str, Any]) -> SAEResult:
    statistics = dict(result.statistics)
    diagnostics = dict(statistics.get("diagnostics", {}))
    diagnostics["calibration_quantiles"] = calibration
    warning_threshold = float(calibration["warning_threshold"])
    blocker_threshold = float(calibration["blocker_threshold"])
    diagnostics["alert_level"] = _alert_level(
        float(diagnostics.get("blr", 0.0)),
        green_threshold=warning_threshold,
        red_threshold=blocker_threshold,
    )
    statistics["diagnostics"] = diagnostics
    metadata = dict(result.metadata)
    quality_certificate = dict(metadata.get("quality_certificate", {}))
    quality_certificate["diagnostics"] = diagnostics
    metadata["quality_certificate"] = quality_certificate
    metadata["diagnostics"] = diagnostics
    return result.model_copy(
        update={
            "statistics": statistics,
            "metadata": metadata,
        }
    )


def _build_governance_artifact(
    *,
    result: SAEResult,
    input_metadata: dict[str, Any],
    issues: list[ComplianceIssue],
) -> dict[str, Any]:
    diagnostics = dict(result.statistics.get("diagnostics", {}))
    quality_certificate = dict(result.metadata.get("quality_certificate", {}))
    spillover_flag = bool(diagnostics.get("spillover_term_included"))
    severities = {issue.severity for issue in issues}
    if IssueSeverity.BLOCKER in severities:
        leakage_status = "blocker"
    elif IssueSeverity.WARNING in severities:
        leakage_status = "warning"
    else:
        leakage_status = "pass"
    return {
        "assumptions": quality_certificate.get("assumptions", {}),
        "frontier_provenance": {
            "bundle_dir": input_metadata.get("bundle_dir"),
            "frontier_semantics": input_metadata.get("frontier_semantics"),
            "frontier_sources": input_metadata.get("frontier_sources", []),
            "frontier_types": input_metadata.get("frontier_types", []),
            "adjacency_types": input_metadata.get("adjacency_types", []),
        },
        "leakage_verdict": {
            "status": leakage_status,
            "alert_level": diagnostics.get("alert_level"),
            "blr": diagnostics.get("blr"),
            "issues": [issue.to_dict() for issue in issues],
            "calibration_quantiles": diagnostics.get("calibration_quantiles", {}),
        },
        "spillover_flag": {
            "term_included": spillover_flag,
            "allowed_by_metadata": bool(
                input_metadata.get("spillover_allowed")
                or input_metadata.get("spillover_term_allowed")
            ),
            "mapping_versions": input_metadata.get("exposure_mapping_versions", []),
        },
        "transportability_required": bool(input_metadata.get("transportability_required", False)),
        "sutva_warning": spillover_flag and bool(diagnostics.get("blr", 0.0) > 0.0),
        "benchmark_evidence_refs": [
            "survey_causal_frontier_sae",
            "benchmarks/survey/causal_frontier_sae_benchmark.py",
        ],
    }


def _artifact_ref_from_payload(payload: Any) -> ArtifactRef | None:
    if payload is None:
        return None
    if isinstance(payload, ArtifactRef):
        return payload
    if hasattr(payload, "model_dump"):
        return ArtifactRef.model_validate(payload.model_dump(mode="json"))
    if isinstance(payload, dict):
        return ArtifactRef.model_validate(payload)
    return None


def _alert_level(blr: float, *, green_threshold: float, red_threshold: float) -> str:
    if blr < green_threshold:
        return "green"
    if blr < red_threshold:
        return "amber"
    return "red"


__all__ = ["SAESpatialService"]
