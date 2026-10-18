"""Strict N13b contract support and epoch readers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel, ConfigDict

from tools.quality.validation.layer3_gy_n13b_derivation_universality import (
    DEFAULT_DERIVATION_FAMILY_REGISTRY,
)

SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"

N13B_FAMILY_ID = "policy-design-case-layer3-gy-n13b-acquisition-executor"

N13B_SOURCE_FAMILY_ID = "policy-design-case-layer3-gy-n13b-frozen-acquisition-evidence"

DEFAULT_N13B_CONTRACT = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acquisition_executor_contract.json"
)

DEFAULT_N13B_LIFECYCLE_MANIFEST = Path(
    "architecture/policy_design_case/layer3_gy_n13b_lifecycle_manifest.json"
)

DEFAULT_GENERATED_ARTIFACTS = Path("architecture/generated_artifacts.toml")

DEFAULT_N13B_JOURNAL = Path(
    "architecture/policy_design_case/layer3_gy_acquisition_raw_journal.jsonl"
)

DEFAULT_N13B_CAS = Path("architecture/policy_design_case/layer3_gy_acquisition_cas")

DEFAULT_N13B_PROVISION = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acquisition_provision.json"
)

DEFAULT_N13B_REGISTRY = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acquisition_registry.json"
)

DEFAULT_DERIVED_ACCEPTANCE = Path(
    "architecture/policy_design_case/layer3_gy_n13b_derived_acceptance_case.json"
)

DEFAULT_N13A_CENSUS = Path("architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json")

DEFAULT_CARRIER_LIVENESS = Path(
    "architecture/policy_design_case/"
    "layer3_gy_n13a_worldbank_government_balance_carrier_liveness.json"
)

DEFAULT_R1_FORENSIC = Path(
    "architecture/policy_design_case/layer3_gy_n13b_r1_forensic_receipt.json"
)

DEFAULT_R2_METADATA_EVIDENCE = Path(
    "architecture/policy_design_case/"
    "layer3_gy_n13b_worldbank_government_balance_metadata_evidence.json"
)

DEFAULT_D6_ROUTE = Path("architecture/policy_design_case/layer3_gy_n13b_d6_route_selection.json")

DEFAULT_R3_METADATA_EVIDENCE = Path(
    "architecture/policy_design_case/"
    "layer3_gy_n13b_worldbank_government_balance_percent_gdp_metadata_evidence.json"
)

DEFAULT_ACCEPTANCE_INPUTS = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acceptance_input_selection.json"
)

DEFAULT_ACCEPTANCE_EXECUTION = Path(
    "architecture/policy_design_case/layer3_gy_n13b_cpi_live_execution_evidence.json"
)

DEFAULT_ACCEPTANCE_FALLBACK = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acceptance_fallback_selection.json"
)

DEFAULT_REENTRY_TRACE = Path("architecture/policy_design_case/layer3_gy_n13b_reentry_trace.json")

_SOURCE_OWNER_PATHS = (
    DEFAULT_DERIVATION_FAMILY_REGISTRY.as_posix(),
    "src/polisyos/data_forge/domains/catalog/knowledge/acquisition_authority.py",
    "src/polisyos/data_forge/domains/catalog/knowledge/derivation_catalog_selection.py",
    "src/polisyos/data_forge/domains/catalog/knowledge/overlay.py",
    "src/polisyos/fabric/data_plane/evidence_journal.py",
    "src/polisyos/ir/kernel/units.py",
    "src/polisyos/runtime/quality/acquisition_executor.py",
    "src/polisyos/runtime/quality/acquisition_planner.py",
    "src/polisyos/runtime/quality/data_state_substrate.py",
    "src/polisyos/runtime/quality/derived_observations.py",
    "tools/quality/validation/check_layer3_gy_generated_public_lifecycle_audit.py",
    "tools/quality/validation/layer3_gy_n13b_derivation_universality.py",
)

_SOURCE_GROWTH_REQUIREMENT_SCHEMA_VERSION = "policyos.layer3.gy.n13b.connector_request_lever_gap.v1"

_SOURCE_GROWTH_PLANNER_GENERATED_AT = datetime(2026, 7, 19, tzinfo=UTC)


class N13bContractError(RuntimeError):
    """Fail-closed N13b contract error with a stable code."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail or code
        super().__init__(f"{code}: {self.detail}")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _read_epoch_model(path: Path, models: Mapping[str, type[BaseModel]]) -> BaseModel:
    try:
        data = Path(path).read_bytes()
        payload = json.loads(data)
        model = (
            models.get(str(payload.get("schema_version"))) if isinstance(payload, dict) else None
        )
        if model is None:
            raise N13bContractError("n13b_receipt_epoch_unsupported", path.as_posix())
        return model.model_validate_json(data)
    except (OSError, ValueError) as exc:
        raise N13bContractError("n13b_source_artifact_invalid", path.as_posix()) from exc


def _read_model(path: Path, model: type[BaseModel]) -> Any:
    try:
        return model.model_validate_json(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise N13bContractError("n13b_source_artifact_invalid", path.as_posix()) from exc


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _bytes_sha256(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_value(item) for item in value]
    return value


if TYPE_CHECKING:
    from .acquisition_response_receipts import R1ForensicReceipt
    from .artifact_lifecycle_manifest import N13bLifecycleManifest
    from .catalog_candidate_admission import D6RouteSelection
    from .metadata_execution_evidence import (
        D6MetadataProbeOwner,
        MetadataProbeExecutionEvidence,
        MetadataProbeOwner,
    )


class LifecycleManifestFactory(Protocol):
    """Describe the facade callback used by acquisition contract composition."""

    def __call__(
        self,
        repo_root: Path,
        *,
        derived_artifact_id: str | None = ...,
        certificate_artifact_id: str | None = ...,
        prospective_outputs: Mapping[str, bytes] | None = ...,
        generated_artifacts_bytes: bytes | None = ...,
        required_cas_artifact_ids: Sequence[str] | None = ...,
    ) -> N13bLifecycleManifest: ...


class MetadataEvidenceFactory(Protocol):
    """Describe the current R2 journal/CAS reopening owner."""

    def __call__(
        self,
        *,
        owner: MetadataProbeOwner,
        r1_receipt: R1ForensicReceipt,
        journal_path: Path,
        cas_root: Path,
        baseline_path: Path,
    ) -> tuple[MetadataProbeExecutionEvidence, BaseModel]: ...


class D6MetadataEvidenceFactory(Protocol):
    """Describe the current D6/R3 journal/CAS reopening owner."""

    def __call__(
        self,
        *,
        owner: D6MetadataProbeOwner,
        selection: D6RouteSelection,
        journal_path: Path,
        cas_root: Path,
        baseline_path: Path,
    ) -> MetadataProbeExecutionEvidence: ...


@dataclass(frozen=True, slots=True)
class AdmissionDependencies:
    """Call-time collaborators that retain the historical facade's live bindings."""

    derive_lifecycle_manifest: LifecycleManifestFactory
    derive_metadata_probe_execution_evidence: MetadataEvidenceFactory
    derive_d6_metadata_probe_execution_evidence: D6MetadataEvidenceFactory
