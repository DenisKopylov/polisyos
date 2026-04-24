"""Governance helpers for Phase 1 readiness closure and global gate enforcement."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics.dependence_structure import DependenceStructure
from polisyos.ir.analytics.microsim_calibration import MicrosimCalibrationReport
from polisyos.ir.analytics.mobility import MobilityReport
from polisyos.ir.analytics.survey_quality import SurveyQualityCertificate

if TYPE_CHECKING:
    from polisyos.ir.artifacts.contracts import ArtifactStore


_FLAGSHIP_MANIFEST_RESOURCE = "phase1_flagship_government_datasets.json"
_REQUIRED_REGIMES = ("panel", "areal", "network_adjacent")


class Phase1GateSummary(BaseModel):
    """Machine-checkable summary used by Phase 1 global readiness gates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    flagship_dataset_ids: list[str] = Field(default_factory=list)
    certified_flagship_dataset_ids: list[str] = Field(default_factory=list)
    flagship_dataset_coverage_ready: bool = False
    required_dependence_regimes: list[str] = Field(default_factory=lambda: list(_REQUIRED_REGIMES))
    calibrated_dependence_regimes: list[str] = Field(default_factory=list)
    dependence_regime_coverage_ready: bool = False
    microsim_gate_ready: bool = False
    mobility_shell_ready: bool = False
    overall_passed: bool = False
    blocking_reasons: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def load_phase1_flagship_dataset_ids() -> tuple[str, ...]:
    """Load the checked-in flagship government dataset manifest."""

    resource = files("polisyos.ir.governance").joinpath(_FLAGSHIP_MANIFEST_RESOURCE)
    payload = json.loads(resource.read_text(encoding="utf-8"))
    datasets = payload.get("dataset_ids", [])
    return tuple(str(item).strip() for item in datasets if str(item).strip())


def build_phase1_gate_summary(
    artifact_store: ArtifactStore | None,
) -> Phase1GateSummary:
    """Summarize whether the Phase 1 closure lane is materially available."""

    flagship_ids = load_phase1_flagship_dataset_ids()
    certified_flagships: set[str] = set()
    calibrated_regimes: set[str] = set()
    microsim_gate_ready = False
    mobility_shell_ready = False
    metadata: dict[str, Any] = {"artifact_scan_enabled": artifact_store is not None}

    if artifact_store is not None:
        from polisyos.ir.artifacts.io import get_json_artifact

        for artifact_id in artifact_store.iter_artifact_ids():
            manifest = artifact_store.get_manifest(artifact_id)
            if manifest.kind == "ir.survey_quality_certificate":
                payload = get_json_artifact(artifact_store, artifact_id)
                certificate = SurveyQualityCertificate.model_validate(payload)
                dataset_id = str(certificate.dataset_id or "").strip()
                if (
                    dataset_id
                    and dataset_id in flagship_ids
                    and certificate.overall_pass
                    and certificate.regime_validated is not None
                ):
                    certified_flagships.add(dataset_id)
            elif manifest.kind == "ir.dependence_structure":
                payload = get_json_artifact(artifact_store, artifact_id)
                structure = DependenceStructure.model_validate(payload)
                if structure.calibrated:
                    calibrated_regimes.add(structure.regime)
            elif manifest.kind == "ir.microsim_calibration_report":
                payload = get_json_artifact(artifact_store, artifact_id)
                report = MicrosimCalibrationReport.model_validate(payload)
                if report.can_run_microsim:
                    microsim_gate_ready = True
            elif manifest.kind == "ir.mobility_report":
                payload = get_json_artifact(artifact_store, artifact_id)
                MobilityReport.model_validate(payload)
                mobility_shell_ready = True

    blocking_reasons: list[str] = []
    if len(certified_flagships) < len(flagship_ids):
        blocking_reasons.append("phase1_flagship_dataset_coverage_incomplete")
    if not set(_REQUIRED_REGIMES).issubset(calibrated_regimes):
        blocking_reasons.append("phase1_dependence_regime_coverage_incomplete")
    if not microsim_gate_ready:
        blocking_reasons.append("phase1_microsim_gate_unverified")
    if not mobility_shell_ready:
        blocking_reasons.append("phase1_mobility_shell_unverified")

    overall_passed = (
        len(certified_flagships) == len(flagship_ids)
        and set(_REQUIRED_REGIMES).issubset(calibrated_regimes)
        and microsim_gate_ready
        and mobility_shell_ready
    )
    return Phase1GateSummary(
        flagship_dataset_ids=list(flagship_ids),
        certified_flagship_dataset_ids=sorted(certified_flagships),
        flagship_dataset_coverage_ready=len(certified_flagships) == len(flagship_ids),
        calibrated_dependence_regimes=sorted(calibrated_regimes),
        dependence_regime_coverage_ready=set(_REQUIRED_REGIMES).issubset(calibrated_regimes),
        microsim_gate_ready=microsim_gate_ready,
        mobility_shell_ready=mobility_shell_ready,
        overall_passed=overall_passed,
        blocking_reasons=blocking_reasons,
        metadata=metadata,
    )


__all__ = ["Phase1GateSummary", "build_phase1_gate_summary", "load_phase1_flagship_dataset_ids"]
