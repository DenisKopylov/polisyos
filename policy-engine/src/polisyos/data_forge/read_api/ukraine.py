"""Runtime-safe read API for Ukraine source snapshots and demographic artifacts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal, Never

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    TypeAdapter,
    model_validator,
)
from typing_extensions import TypeForm

from polisyos.core import artifacts as core_artifacts
from polisyos.data_forge._ukraine_release_contracts import (
    D5ReleaseHandoffRequest as D5ReleaseHandoffRequest,
)

from ._lazy import lazy_dir, load_lazy_export

if TYPE_CHECKING:
    import numpy.typing as npt

    from polisyos.data_forge.domains.ukraine import (
        UKRAINE_ASSET_GROUP as UKRAINE_ASSET_GROUP,
    )
    from polisyos.data_forge.domains.ukraine import (
        UKRAINE_DEMOGRAPHY_DONOR_POOL_KEY as UKRAINE_DEMOGRAPHY_DONOR_POOL_KEY,
    )
    from polisyos.data_forge.domains.ukraine import (
        UKRAINE_DEMOGRAPHY_PRIORS_KEY as UKRAINE_DEMOGRAPHY_PRIORS_KEY,
    )
    from polisyos.data_forge.domains.ukraine import (
        UKRAINE_DEMOGRAPHY_SOURCE_INVENTORY_KEY as UKRAINE_DEMOGRAPHY_SOURCE_INVENTORY_KEY,
    )
    from polisyos.data_forge.domains.ukraine import (
        UKRAINE_DEMOGRAPHY_TARGETS_KEY as UKRAINE_DEMOGRAPHY_TARGETS_KEY,
    )
    from polisyos.data_forge.domains.ukraine import (
        UKRAINE_NORMALIZED_SOURCES_KEY as UKRAINE_NORMALIZED_SOURCES_KEY,
    )
    from polisyos.data_forge.domains.ukraine import (
        UKRAINE_RAW_SOURCES_KEY as UKRAINE_RAW_SOURCES_KEY,
    )
    from polisyos.data_forge.domains.ukraine import (
        UKRAINE_READINESS_KEY as UKRAINE_READINESS_KEY,
    )
    from polisyos.data_forge.domains.ukraine import (
        UKRAINE_SOURCE_CONFIG_KEY as UKRAINE_SOURCE_CONFIG_KEY,
    )
    from polisyos.data_forge.domains.ukraine import (
        UKRAINE_STATIC_AGING_INPUTS_KEY as UKRAINE_STATIC_AGING_INPUTS_KEY,
    )
    from polisyos.data_forge.domains.ukraine import (
        DemographyRoleProjection as DemographyRoleProjection,
    )
    from polisyos.data_forge.domains.ukraine import (
        DemographySourceEvidence as DemographySourceEvidence,
    )
    from polisyos.data_forge.domains.ukraine import (
        DemographySourceRequest as DemographySourceRequest,
    )
    from polisyos.data_forge.domains.ukraine import (
        HistoricalLayoutRequest as HistoricalLayoutRequest,
    )
    from polisyos.data_forge.domains.ukraine import (
        InventorySourceRequest as InventorySourceRequest,
    )
    from polisyos.data_forge.domains.ukraine import (
        SourceResolutionRefusalError as SourceResolutionRefusalError,
    )
    from polisyos.data_forge.domains.ukraine import (
        UkraineDemographyArtifacts as UkraineDemographyArtifacts,
    )
    from polisyos.data_forge.domains.ukraine import (
        UkraineLexPreShardDiff as UkraineLexPreShardDiff,
    )
    from polisyos.data_forge.domains.ukraine import (
        UkraineLexPreShardSummary as UkraineLexPreShardSummary,
    )
    from polisyos.data_forge.domains.ukraine import (
        UkraineLexShardEntry as UkraineLexShardEntry,
    )
    from polisyos.data_forge.domains.ukraine import (
        UkraineLexShardPassSummary as UkraineLexShardPassSummary,
    )
    from polisyos.data_forge.domains.ukraine import (
        UkraineReadinessSummary as UkraineReadinessSummary,
    )
    from polisyos.data_forge.domains.ukraine import (
        UkraineShadowArtifact as UkraineShadowArtifact,
    )
    from polisyos.data_forge.domains.ukraine import (
        UkraineShadowBundle as UkraineShadowBundle,
    )
    from polisyos.data_forge.domains.ukraine import (
        UkraineShadowDiff as UkraineShadowDiff,
    )
    from polisyos.data_forge.domains.ukraine import (
        UkraineSourceSummary as UkraineSourceSummary,
    )
    from polisyos.data_forge.domains.ukraine import (
        compare_lex_pre_shard_summaries as compare_lex_pre_shard_summaries,
    )
    from polisyos.data_forge.domains.ukraine import (
        compare_ukraine_shadow_bundles as compare_ukraine_shadow_bundles,
    )
    from polisyos.data_forge.domains.ukraine import (
        infer_lex_snapshot_label as infer_lex_snapshot_label,
    )
    from polisyos.data_forge.domains.ukraine import (
        lex_pre_shard_index as lex_pre_shard_index,
    )
    from polisyos.data_forge.domains.ukraine import (
        lex_pre_shard_pass_name as lex_pre_shard_pass_name,
    )
    from polisyos.data_forge.domains.ukraine import (
        load_demography_artifacts as load_demography_artifacts,
    )
    from polisyos.data_forge.domains.ukraine import (
        load_donor_pool as load_donor_pool,
    )
    from polisyos.data_forge.domains.ukraine import (
        load_lex_pre_shard_summary as load_lex_pre_shard_summary,
    )
    from polisyos.data_forge.domains.ukraine import (
        load_reconciled_targets as load_reconciled_targets,
    )
    from polisyos.data_forge.domains.ukraine import (
        load_transition_priors as load_transition_priors,
    )
    from polisyos.data_forge.domains.ukraine import (
        load_ukraine_shadow_bundle as load_ukraine_shadow_bundle,
    )
    from polisyos.data_forge.domains.ukraine.builders.demography import (
        build_household_diagnostic_panel as build_household_diagnostic_panel,
    )
    from polisyos.data_forge.domains.ukraine.builders.observation import (
        UKRAINE_PERIOD_PROJECTION_VERSION as UKRAINE_PERIOD_PROJECTION_VERSION,
    )
    from polisyos.data_forge.domains.ukraine.builders.observation import (
        project_ukraine_observation_periods as project_ukraine_observation_periods,
    )
    from polisyos.data_forge.domains.ukraine.contracts import (
        RealBacktestBundleContract as RealBacktestBundleContract,
    )
    from polisyos.data_forge.domains.ukraine.manifests import (
        ArtifactRecord as ArtifactRecord,
    )
    from polisyos.data_forge.domains.ukraine.manifests import (
        CalibrationBundleManifest as CalibrationBundleManifest,
    )
    from polisyos.data_forge.domains.ukraine.manifests import (
        HouseholdDiagnosticPanelBasis as HouseholdDiagnosticPanelBasis,
    )
    from polisyos.data_forge.domains.ukraine.manifests import (
        NormalizedArtifactManifest as NormalizedArtifactManifest,
    )
    from polisyos.data_forge.domains.ukraine.manifests import (
        ReleaseManifest as ReleaseManifest,
    )
    from polisyos.data_forge.domains.ukraine.manifests import (
        SourceSnapshotManifest as SourceSnapshotManifest,
    )
    from polisyos.data_forge.domains.ukraine.manifests import (
        directory_tree_entries as directory_tree_entries,
    )
    from polisyos.data_forge.domains.ukraine.manifests import (
        load_manifest as load_manifest,
    )

_UKRAINE_DOMAIN = "polisyos.data_forge.domains.ukraine"
_UKRAINE_OBSERVATION = "polisyos.data_forge.domains.ukraine.builders.observation"
REAL_BACKTEST_BUNDLE_CONTRACT_FQN = (
    "polisyos.data_forge.domains.ukraine.contracts.RealBacktestBundleContract"
)
_EXPORTS = {
    "UKRAINE_ASSET_GROUP": _UKRAINE_DOMAIN,
    "UKRAINE_DEMOGRAPHY_DONOR_POOL_KEY": _UKRAINE_DOMAIN,
    "UKRAINE_DEMOGRAPHY_PRIORS_KEY": _UKRAINE_DOMAIN,
    "UKRAINE_DEMOGRAPHY_SOURCE_INVENTORY_KEY": _UKRAINE_DOMAIN,
    "UKRAINE_DEMOGRAPHY_TARGETS_KEY": _UKRAINE_DOMAIN,
    "UKRAINE_NORMALIZED_SOURCES_KEY": _UKRAINE_DOMAIN,
    "UKRAINE_RAW_SOURCES_KEY": _UKRAINE_DOMAIN,
    "UKRAINE_READINESS_KEY": _UKRAINE_DOMAIN,
    "UKRAINE_SOURCE_CONFIG_KEY": _UKRAINE_DOMAIN,
    "UKRAINE_STATIC_AGING_INPUTS_KEY": _UKRAINE_DOMAIN,
    "UKRAINE_PERIOD_PROJECTION_VERSION": _UKRAINE_OBSERVATION,
    "project_ukraine_observation_periods": _UKRAINE_OBSERVATION,
    "DemographyRoleProjection": _UKRAINE_DOMAIN,
    "DemographySourceEvidence": _UKRAINE_DOMAIN,
    "DemographySourceRequest": _UKRAINE_DOMAIN,
    "HistoricalLayoutRequest": _UKRAINE_DOMAIN,
    "InventorySourceRequest": _UKRAINE_DOMAIN,
    "SourceResolutionRefusalError": _UKRAINE_DOMAIN,
    "UkraineDemographyArtifacts": _UKRAINE_DOMAIN,
    "UkraineLexPreShardDiff": _UKRAINE_DOMAIN,
    "UkraineLexPreShardSummary": _UKRAINE_DOMAIN,
    "UkraineLexShardEntry": _UKRAINE_DOMAIN,
    "UkraineLexShardPassSummary": _UKRAINE_DOMAIN,
    "UkraineReadinessSummary": _UKRAINE_DOMAIN,
    "UkraineShadowArtifact": _UKRAINE_DOMAIN,
    "UkraineShadowBundle": _UKRAINE_DOMAIN,
    "UkraineShadowDiff": _UKRAINE_DOMAIN,
    "UkraineSourceSummary": _UKRAINE_DOMAIN,
    "CalibrationBundleManifest": "polisyos.data_forge.domains.ukraine.manifests",
    "ReleaseManifest": "polisyos.data_forge.domains.ukraine.manifests",
    "ArtifactRecord": "polisyos.data_forge.domains.ukraine.manifests",
    "D5ReleaseHandoffRequest": "polisyos.data_forge._ukraine_release_contracts",
    "HouseholdDiagnosticPanelBasis": "polisyos.data_forge.domains.ukraine.manifests",
    "NormalizedArtifactManifest": "polisyos.data_forge.domains.ukraine.manifests",
    "SourceSnapshotManifest": "polisyos.data_forge.domains.ukraine.manifests",
    "directory_tree_entries": "polisyos.data_forge.domains.ukraine.manifests",
    "build_household_diagnostic_panel": "polisyos.data_forge.domains.ukraine.builders.demography",
    "RealBacktestBundleContract": "polisyos.data_forge.domains.ukraine.contracts",
    "compare_lex_pre_shard_summaries": _UKRAINE_DOMAIN,
    "compare_ukraine_shadow_bundles": _UKRAINE_DOMAIN,
    "infer_lex_snapshot_label": _UKRAINE_DOMAIN,
    "lex_pre_shard_index": _UKRAINE_DOMAIN,
    "lex_pre_shard_pass_name": _UKRAINE_DOMAIN,
    "load_demography_artifacts": _UKRAINE_DOMAIN,
    "load_donor_pool": _UKRAINE_DOMAIN,
    "load_lex_pre_shard_summary": _UKRAINE_DOMAIN,
    "load_manifest": "polisyos.data_forge.domains.ukraine.manifests",
    "load_reconciled_targets": _UKRAINE_DOMAIN,
    "load_transition_priors": _UKRAINE_DOMAIN,
    "load_ukraine_shadow_bundle": _UKRAINE_DOMAIN,
}


def _validate_sha256_reference(value: str) -> str:
    """Validate the prefixed SHA-256 wire form with Core's ArtifactID owner."""
    return str(core_artifacts.ArtifactID.model_validate(value))


def _validate_sha256_hex(value: str) -> str:
    """Validate a bare SHA-256 content digest with Core's canonical parser."""
    return core_artifacts.ArtifactID.from_sha256_hex(value).hex


# Selected references/profile digests include their canonical algorithm prefix.
_Sha256Reference = Annotated[
    StrictStr,
    Field(pattern=r"^sha256:[0-9a-f]{64}$"),
    AfterValidator(_validate_sha256_reference),
]
# Payload/content digests remain bare 64-hex values throughout producer receipts.
_Sha256ContentHex = Annotated[
    StrictStr,
    Field(pattern=r"^[0-9a-f]{64}$"),
    AfterValidator(_validate_sha256_hex),
]


class UkraineStageArtifactVerificationError(RuntimeError):
    """Raised when a Ukraine producer artifact cannot be content-bound fail closed."""


UkraineJSONSnapshotStatus = Literal[
    "declared_bytes_conformant",
    "profile_absent_raw_snapshot_candidate",
    "declared_unknown_candidate",
]


UKRAINE_D4_SOURCE_JSON_SNAPSHOT_ROLE_BY_CONTRACT: dict[str, str] = {
    "scientist.d4.governance_request": "d4_governance_request",
    "scientist.d4.identity_resolution_cohort": "identity_resolution_cohort",
    "scientist.d4.calibration_splits": "selected_split_manifest",
}


class UkraineD4GovernanceRequest(BaseModel):
    """Strict candidate payload shape for a D4 governance request snapshot."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    authority_purpose: str
    may_not_use_for: list[str]
    required_stage_manifests: dict[str, str]


class UkraineIdentityResolutionCohortRow(BaseModel):
    """One source-owned identity-resolution cohort record."""

    model_config = ConfigDict(extra="forbid")

    cohort: str = Field(pattern="^(spending|procurement)$")
    raw_identity: str = Field(min_length=1)


class UkraineIdentityResolutionCohort(BaseModel):
    """Strict candidate payload shape for identity-resolution source snapshots."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    rows: list[UkraineIdentityResolutionCohortRow] = Field(default_factory=list)


_UkraineD4JSONSnapshotModel = (
    TypeForm[UkraineD4GovernanceRequest]
    | TypeForm[UkraineIdentityResolutionCohort]
    | TypeForm[dict[str, dict[str, str]]]
)
_UKRAINE_D4_JSON_SNAPSHOT_MODEL_BY_CONTRACT: dict[str, _UkraineD4JSONSnapshotModel] = {
    "scientist.d4.governance_request": UkraineD4GovernanceRequest,
    "scientist.d4.identity_resolution_cohort": UkraineIdentityResolutionCohort,
    "scientist.d4.calibration_splits": dict[str, dict[str, str]],
}


def ukraine_d4_json_snapshot_model_type(
    consumer_contract: str,
) -> _UkraineD4JSONSnapshotModel | None:
    """Resolve the Data Forge-owned candidate model for one D4 JSON contract."""
    return _UKRAINE_D4_JSON_SNAPSHOT_MODEL_BY_CONTRACT.get(consumer_contract)


class UkraineJSONSnapshotRefusalError(UkraineStageArtifactVerificationError):
    """A fail-closed refusal at the typed Ukraine JSON snapshot boundary."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class UkraineJSONSnapshotProvenance(BaseModel):
    """Recomputed selection/content facts, never producer or source authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_ref: core_artifacts.ArtifactRef
    selected_artifact_id: _Sha256Reference
    selected_manifest_profile_sha256: _Sha256Reference
    content_sha256: _Sha256ContentHex
    content_size_bytes: int = Field(ge=0)
    artifact_kind: str = Field(min_length=1)
    media_type: Literal["application/json"] = "application/json"
    schema_name: str | None = None
    schema_version: str | None = None
    profile_status: UkraineJSONSnapshotStatus
    consumer_contract: str = Field(min_length=1)
    profile_selection_provenance: Literal["recomputed"] = "recomputed"
    content_binding_provenance: Literal["recomputed"] = "recomputed"
    schema_validation_provenance: Literal["recomputed", "not_evaluated"]
    source_materialization: Literal[
        "reader_materialized",
        "raw_snapshot_candidate",
        "raw_only_candidate",
    ]
    producer_attestation_status: Literal["not_established"] = "not_established"
    currentness_provenance: Literal["not_established"] = "not_established"
    authority_provenance: Literal["not_established"] = "not_established"

    @model_validator(mode="after")
    def _bind_selected_content(self) -> UkraineJSONSnapshotProvenance:
        if self.artifact_ref.artifact_id.hex != self.content_sha256:
            raise ValueError("snapshot content digest differs from its selected artifact ID")
        if self.selected_artifact_id != str(self.artifact_ref.artifact_id):
            raise ValueError("snapshot provenance selected ID differs from the artifact ref")
        if self.artifact_ref.manifest_profile_sha256 != self.selected_manifest_profile_sha256:
            raise ValueError("snapshot provenance profile differs from the selected artifact ref")
        if self.profile_status == "declared_unknown_candidate":
            if (
                self.schema_validation_provenance != "not_evaluated"
                or self.source_materialization != "raw_only_candidate"
            ):
                raise ValueError("unknown profiles may be carried raw only")
        elif self.schema_validation_provenance != "recomputed":
            raise ValueError("typed snapshot candidates require recomputed schema validation")
        return self


@dataclass(frozen=True)
class UkraineJSONSnapshotRead[SnapshotT]:
    """One exact CAS JSON read with a status-gated semantic value."""

    provenance: UkraineJSONSnapshotProvenance
    raw_payload_bytes: bytes
    _candidate_value: SnapshotT | None = None

    @property
    def value(self) -> SnapshotT:
        """Return a value only when the declared selected Core profile conforms."""
        if (
            self.provenance.profile_status != "declared_bytes_conformant"
            or self._candidate_value is None
        ):
            raise UkraineJSONSnapshotRefusalError(
                "ukraine_snapshot_profile_not_verified",
                "semantic value is not declared-profile conformant",
            )
        return self._candidate_value

    @property
    def raw_only_candidate_bytes(self) -> bytes:
        """Return exact bytes for an unsupported declared profile without decoding."""
        if self.provenance.profile_status != "declared_unknown_candidate":
            raise UkraineJSONSnapshotRefusalError(
                "ukraine_snapshot_not_raw_only",
                "selected profile is not an unsupported declaration",
            )
        return self.raw_payload_bytes

    def value_for_candidate(self) -> SnapshotT:
        """Return a typed candidate value, never an unknown-profile value."""
        if (
            self.provenance.profile_status == "declared_unknown_candidate"
            or self._candidate_value is None
        ):
            raise UkraineJSONSnapshotRefusalError(
                "ukraine_snapshot_unknown_profile_raw_only",
                "unsupported profile has no decoded value",
            )
        return self._candidate_value


def _reject_duplicate_snapshot_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_snapshot_json_constant(value: str) -> Never:
    raise ValueError(f"invalid JSON numeric constant: {value}")


def read_ukraine_json_snapshot[SnapshotT](
    store: core_artifacts.ArtifactStore,
    artifact_ref: core_artifacts.ArtifactRef,
    *,
    raw_payload_bytes: bytes,
    expected_sha256: _Sha256ContentHex,
    expected_size_bytes: int,
    expected_kind: str,
    consumer_contract: str,
    model_type: TypeForm[SnapshotT],
    expected_schema: tuple[str, str] | None = None,
) -> UkraineJSONSnapshotRead[SnapshotT]:
    """Bind one exact JSON snapshot to its selected raw manifest before typed use.

    A profileless snapshot is explicitly candidate-only and never receives a
    reader-default canonical profile. A well-formed unsupported profile is
    raw-only: this function does not parse its JSON value. Malformed-present
    profile metadata remains a refusal from the shared Core parser.
    """
    if artifact_ref.manifest_profile_sha256 is None:
        raise UkraineJSONSnapshotRefusalError(
            "ukraine_snapshot_profile_selector_missing",
            "semantic JSON reads require the exact writer-selected manifest profile",
        )
    try:
        manifest, declaration = core_artifacts.read_core_manifest_profile(
            store,
            artifact_ref,
            allow_profile_absent=True,
        )
    except FileNotFoundError as exc:
        raise UkraineJSONSnapshotRefusalError(
            "ukraine_snapshot_manifest_missing", str(exc)
        ) from exc
    except Exception as exc:
        code = getattr(exc, "code", "ukraine_snapshot_manifest_unavailable")
        raise UkraineJSONSnapshotRefusalError(str(code), str(exc)) from exc
    if manifest.artifact_id != artifact_ref.artifact_id or manifest.kind != expected_kind:
        raise UkraineJSONSnapshotRefusalError(
            "ukraine_snapshot_kind_or_identity_mismatch",
            "selected manifest differs from the receipt",
        )
    if manifest.media_type != "application/json":
        raise UkraineJSONSnapshotRefusalError(
            "ukraine_snapshot_media_type_mismatch",
            "typed JSON consumer selected a non-JSON artifact",
        )
    actual_schema = manifest.artifact_schema
    if expected_schema is not None and (
        actual_schema is None
        or actual_schema.name != expected_schema[0]
        or actual_schema.version != expected_schema[1]
    ):
        raise UkraineJSONSnapshotRefusalError(
            "ukraine_snapshot_schema_mismatch",
            "selected schema differs from the consumer contract",
        )
    if type(raw_payload_bytes) is not bytes or type(expected_size_bytes) is not int:
        raise UkraineJSONSnapshotRefusalError(
            "ukraine_snapshot_payload_invalid",
            "payload or size has an invalid type",
        )
    actual_sha256 = hashlib.sha256(raw_payload_bytes).hexdigest()
    if (
        len(raw_payload_bytes) != expected_size_bytes
        or actual_sha256 != expected_sha256
        or actual_sha256 != manifest.artifact_id.hex
    ):
        raise UkraineJSONSnapshotRefusalError(
            "ukraine_snapshot_content_binding_mismatch",
            "selected bytes differ from the admitted content identity",
        )
    profile_sha256 = core_artifacts.artifact_manifest_profile_sha256(manifest)
    selected_ref = core_artifacts.ArtifactRef(
        artifact_id=manifest.artifact_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
        manifest_profile_sha256=profile_sha256,
    )
    if (
        artifact_ref.manifest_profile_sha256 is not None
        and artifact_ref.manifest_profile_sha256 != profile_sha256
    ):
        raise UkraineJSONSnapshotRefusalError(
            "ukraine_snapshot_profile_selection_mismatch",
            "receipt selected a different manifest profile",
        )

    value: SnapshotT | None = None
    if declaration.status == "declared_unknown_candidate":
        try:
            read = core_artifacts.read_core_json_artifact(
                store,
                selected_ref,
                raw_payload_bytes=raw_payload_bytes,
                manifest_profile_sha256=profile_sha256,
            )
            if read.raw_only_candidate_bytes != raw_payload_bytes:
                raise ValueError("raw-only Core read changed the selected payload bytes")
        except Exception as exc:
            code = getattr(exc, "code", "ukraine_snapshot_unknown_profile_invalid")
            raise UkraineJSONSnapshotRefusalError(str(code), str(exc)) from exc
        status: UkraineJSONSnapshotStatus = "declared_unknown_candidate"
        validation_provenance: Literal["recomputed", "not_evaluated"] = "not_evaluated"
        materialization: Literal[
            "reader_materialized", "raw_snapshot_candidate", "raw_only_candidate"
        ] = "raw_only_candidate"
    elif declaration.status == "absent":
        try:
            json.loads(
                raw_payload_bytes,
                object_pairs_hook=_reject_duplicate_snapshot_keys,
                parse_constant=_reject_snapshot_json_constant,
            )
            value = TypeAdapter(model_type).validate_json(raw_payload_bytes, strict=True)
        except Exception as exc:
            raise UkraineJSONSnapshotRefusalError(
                "ukraine_snapshot_json_or_schema_invalid", str(exc)
            ) from exc
        status = "profile_absent_raw_snapshot_candidate"
        validation_provenance = "recomputed"
        materialization = "raw_snapshot_candidate"
    else:
        try:
            read = core_artifacts.read_core_json_artifact(
                store,
                selected_ref,
                raw_payload_bytes=raw_payload_bytes,
                manifest_profile_sha256=profile_sha256,
            )
            if read.status != "declared_bytes_conformant":
                raise ValueError("selected profile was not byte-conformant")
            json.loads(
                raw_payload_bytes,
                object_pairs_hook=_reject_duplicate_snapshot_keys,
                parse_constant=_reject_snapshot_json_constant,
            )
            value = TypeAdapter(model_type).validate_json(raw_payload_bytes, strict=True)
        except Exception as exc:
            code = getattr(exc, "code", "ukraine_snapshot_json_or_schema_invalid")
            raise UkraineJSONSnapshotRefusalError(str(code), str(exc)) from exc
        status = "declared_bytes_conformant"
        validation_provenance = "recomputed"
        materialization = "reader_materialized"

    provenance = UkraineJSONSnapshotProvenance(
        artifact_ref=selected_ref,
        selected_artifact_id=f"sha256:{manifest.artifact_id.hex}",
        selected_manifest_profile_sha256=profile_sha256,
        content_sha256=actual_sha256,
        content_size_bytes=len(raw_payload_bytes),
        artifact_kind=manifest.kind,
        schema_name=actual_schema.name if actual_schema is not None else None,
        schema_version=actual_schema.version if actual_schema is not None else None,
        profile_status=status,
        consumer_contract=consumer_contract,
        schema_validation_provenance=validation_provenance,
        source_materialization=materialization,
    )
    return UkraineJSONSnapshotRead(
        provenance=provenance,
        raw_payload_bytes=raw_payload_bytes,
        _candidate_value=value,
    )


def load_verified_stage_json_output[SnapshotT](
    store: core_artifacts.FileSystemCAS,
    receipt: VerifiedUkraineStageArtifacts,
    output_name: str,
    *,
    model_type: TypeForm[SnapshotT],
    consumer_contract: str,
    expected_schema: tuple[str, str] | None = None,
) -> UkraineJSONSnapshotRead[SnapshotT]:
    """Read one JSON output through its exact verified stage receipt and profile."""
    output = receipt.outputs.get(output_name)
    if output is None:
        raise UkraineJSONSnapshotRefusalError("ukraine_snapshot_output_missing", output_name)
    raw = load_verified_stage_output_bytes(store, receipt, output_name)
    return read_ukraine_json_snapshot(
        store,
        output.content_ref,
        raw_payload_bytes=raw,
        expected_sha256=output.sha256,
        expected_size_bytes=output.size_bytes,
        expected_kind="data_forge.ukraine.stage_output_snapshot",
        expected_schema=expected_schema,
        consumer_contract=consumer_contract,
        model_type=model_type,
    )


def load_verified_stage_manifest_json[SnapshotT](
    store: core_artifacts.FileSystemCAS,
    receipt: VerifiedUkraineStageArtifacts,
    *,
    model_type: TypeForm[SnapshotT],
    consumer_contract: str,
) -> UkraineJSONSnapshotRead[SnapshotT]:
    """Read the exact stored BuildRunManifest snapshot without a reader default."""
    try:
        raw = store.get_bytes(receipt.manifest_ref)
    except Exception as exc:
        raise UkraineJSONSnapshotRefusalError(
            "ukraine_snapshot_manifest_missing", str(exc)
        ) from exc
    return read_ukraine_json_snapshot(
        store,
        receipt.manifest_ref,
        raw_payload_bytes=raw,
        expected_sha256=receipt.manifest_sha256,
        expected_size_bytes=len(raw),
        expected_kind="data_forge.ukraine.stage_manifest_snapshot",
        expected_schema=("polisyos.data_forge.ukraine.BuildRunManifest", "1.0"),
        consumer_contract=consumer_contract,
        model_type=model_type,
    )


def load_verified_release_manifest_json[SnapshotT](
    store: core_artifacts.FileSystemCAS,
    receipt: VerifiedUkraineReleaseArtifacts,
    *,
    model_type: TypeForm[SnapshotT],
    consumer_contract: str,
    raw_payload_bytes: bytes | None = None,
) -> UkraineJSONSnapshotRead[SnapshotT]:
    """Read the exact stored ReleaseManifest snapshot under its selected profile."""
    if raw_payload_bytes is None:
        try:
            raw_payload_bytes = store.get_bytes(receipt.manifest_ref)
        except Exception as exc:
            raise UkraineJSONSnapshotRefusalError(
                "ukraine_snapshot_manifest_missing", str(exc)
            ) from exc
    return read_ukraine_json_snapshot(
        store,
        receipt.manifest_ref,
        raw_payload_bytes=raw_payload_bytes,
        expected_sha256=receipt.manifest_sha256,
        expected_size_bytes=receipt.manifest_size_bytes,
        expected_kind="data_forge.ukraine.release_manifest_snapshot",
        expected_schema=("polisyos.data_forge.ukraine.ReleaseManifest", "1.0"),
        consumer_contract=consumer_contract,
        model_type=model_type,
    )


def load_verified_release_json_artifact[SnapshotT](
    store: core_artifacts.FileSystemCAS,
    artifact: VerifiedUkraineReleaseArtifact,
    *,
    model_type: TypeForm[SnapshotT],
    consumer_contract: str,
    expected_schema: tuple[str, str] | None = None,
    raw_payload_bytes: bytes | None = None,
) -> UkraineJSONSnapshotRead[SnapshotT]:
    """Read one receipt-bound JSON release member; opaque/Parquet bytes stay raw."""
    if artifact.content_ref.kind not in {
        "data_forge.ukraine.release_bundle_file_snapshot",
        "data_forge.ukraine.release_evidence_snapshot",
        "data_forge.ukraine.release_handoff_snapshot",
    }:
        raise UkraineJSONSnapshotRefusalError(
            "ukraine_snapshot_kind_mismatch",
            "release member is outside the typed JSON snapshot kinds",
        )
    raw = (
        load_verified_release_artifact_bytes(store, artifact)
        if raw_payload_bytes is None
        else raw_payload_bytes
    )
    return read_ukraine_json_snapshot(
        store,
        artifact.content_ref,
        raw_payload_bytes=raw,
        expected_sha256=artifact.sha256,
        expected_size_bytes=artifact.size_bytes,
        expected_kind=artifact.content_ref.kind,
        expected_schema=expected_schema,
        consumer_contract=consumer_contract,
        model_type=model_type,
    )


class VerifiedUkraineStageArtifact(BaseModel):
    """One producer output whose verified bytes were admitted into immutable storage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_path: str = Field(min_length=1)
    content_ref: core_artifacts.ArtifactRef
    sha256: _Sha256ContentHex
    size_bytes: int = Field(ge=0)
    row_count: int | None = Field(default=None, ge=0)
    nnz: int | None = Field(default=None, ge=0)
    producer_artifact_id: str | None = None

    @model_validator(mode="after")
    def _content_ref_matches_verified_hash(self) -> VerifiedUkraineStageArtifact:
        if self.content_ref.artifact_id.hex != self.sha256:
            raise ValueError("content_ref does not match the verified output hash")
        return self


class VerifiedUkraineStageArtifacts(BaseModel):
    """Fail-closed receipt for one completed Ukraine producer stage.

    This receipt proves file identity and content binding only. It deliberately
    cannot stand in for Scientist governance or Foundry release acceptance.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.data_forge.ukraine.verified_stage.v2"] = (
        "policyos.data_forge.ukraine.verified_stage.v2"
    )
    verification_rule_version: Literal["ukraine-stage-artifacts.v2"] = "ukraine-stage-artifacts.v2"
    stage_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    status: Literal["completed"] = "completed"
    finished_at: str = Field(min_length=1)
    manifest_source_path: str = Field(min_length=1)
    manifest_ref: core_artifacts.ArtifactRef
    manifest_sha256: _Sha256ContentHex
    provenance_ref: Literal["polisyos.data_forge.domains.ukraine.manifests.BuildRunManifest"] = (
        "polisyos.data_forge.domains.ukraine.manifests.BuildRunManifest"
    )
    authority_purpose: Literal["producer_artifact_receipt"] = "producer_artifact_receipt"
    stage_status_provenance: Literal["institutionally_supplied"] = "institutionally_supplied"
    path_scope_provenance: Literal["recomputed"] = "recomputed"
    content_binding_provenance: Literal["recomputed"] = "recomputed"
    authoritative_for: tuple[str, ...] = (
        "producer_artifact_identity",
        "producer_artifact_content_binding",
    )
    may_not_use_for: tuple[str, ...] = (
        "governance_admissibility",
        "release_acceptance",
        "legal_intervention_compilation",
        "method_validity",
    )
    outputs: dict[str, VerifiedUkraineStageArtifact] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _manifest_ref_matches_verified_hash(self) -> VerifiedUkraineStageArtifacts:
        if self.manifest_ref.artifact_id.hex != self.manifest_sha256:
            raise ValueError("manifest_ref does not match the verified manifest hash")
        return self


class VerifiedUkraineReleaseArtifact(BaseModel):
    """One D5 release file admitted into CAS after path and content verification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_path: str = Field(min_length=1)
    content_ref: core_artifacts.ArtifactRef
    sha256: _Sha256ContentHex
    size_bytes: int = Field(ge=0)

    @model_validator(mode="after")
    def _content_ref_matches_verified_hash(self) -> VerifiedUkraineReleaseArtifact:
        if self.content_ref.artifact_id.hex != self.sha256:
            raise ValueError("content_ref does not match the verified release artifact hash")
        return self


class VerifiedUkraineReleaseArtifacts(BaseModel):
    """Non-authoritative admission receipt for a complete D5 release inventory."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[
        "policyos.data_forge.ukraine.verified_release.v1",
        "policyos.data_forge.ukraine.verified_release.v2",
    ] = "policyos.data_forge.ukraine.verified_release.v2"
    verification_rule_version: Literal[
        "ukraine-release-artifacts.v1",
        "ukraine-release-artifacts.v2",
    ] = "ukraine-release-artifacts.v2"
    stage_id: Literal["d5"] = "d5"
    declared_release_root: str = Field(min_length=1)
    manifest_source_path: str = Field(min_length=1)
    manifest_ref: core_artifacts.ArtifactRef
    manifest_sha256: _Sha256ContentHex
    manifest_size_bytes: int = Field(ge=0)
    provenance_ref: Literal["polisyos.data_forge.domains.ukraine.manifests.ReleaseManifest"] = (
        "polisyos.data_forge.domains.ukraine.manifests.ReleaseManifest"
    )
    authority_purpose: Literal["non_authoritative_release_artifact_admission"] = (
        "non_authoritative_release_artifact_admission"
    )
    stage_declaration_provenance: Literal["institutionally_supplied"] = "institutionally_supplied"
    release_root_declaration_provenance: Literal["institutionally_supplied"] = (
        "institutionally_supplied"
    )
    path_scope_provenance: Literal["recomputed"] = "recomputed"
    content_binding_provenance: Literal["recomputed"] = "recomputed"
    authoritative_for: tuple[str, ...] = ()
    verified_for: tuple[str, ...] = (
        "producer_artifact_identity",
        "producer_artifact_content_binding",
    )
    may_not_use_for: tuple[str, ...] = (
        "governance_admissibility",
        "release_acceptance",
        "publication",
        "method_validity",
    )
    handoff_request: D5ReleaseHandoffRequest
    handoff_snapshot_profile_status: UkraineJSONSnapshotStatus | Literal["not_established"] = (
        "not_established"
    )
    bundle_contents: dict[str, dict[str, VerifiedUkraineReleaseArtifact]] = Field(
        default_factory=dict
    )
    evidence: dict[str, VerifiedUkraineReleaseArtifact] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _manifest_ref_matches_verified_hash(self) -> VerifiedUkraineReleaseArtifacts:
        if self.manifest_ref.artifact_id.hex != self.manifest_sha256:
            raise ValueError("manifest_ref does not match the verified release manifest hash")
        versions_match = (
            self.schema_version.endswith(".v1") and self.verification_rule_version.endswith(".v1")
        ) or (
            self.schema_version.endswith(".v2") and self.verification_rule_version.endswith(".v2")
        )
        if not versions_match:
            raise ValueError("release admission receipt schema and rule versions must match")
        if (
            self.schema_version.endswith(".v1")
            and self.handoff_snapshot_profile_status != "not_established"
        ):
            raise ValueError("legacy v1 release receipts cannot claim handoff profile status")
        if self.authoritative_for:
            raise ValueError("release admission receipt cannot declare downstream authority")
        if set(self.verified_for) != {
            "producer_artifact_identity",
            "producer_artifact_content_binding",
        }:
            raise ValueError("release admission receipt has an invalid evidence-band scope")
        if set(self.may_not_use_for) != {
            "governance_admissibility",
            "release_acceptance",
            "publication",
            "method_validity",
        }:
            raise ValueError("release admission receipt must retain every authority denial")
        return self


def load_verified_stage_artifacts(
    manifest_path: Path,
    *,
    store: core_artifacts.FileSystemCAS,
    allowed_root: Path,
    expected_stage: str,
    required_outputs: tuple[str, ...] = (),
) -> VerifiedUkraineStageArtifacts:
    """Resolve one completed stage and preserve each exact admitted byte string.

    CAS writes return the exact manifest profile selected by each write. This importer
    does not canonicalize producer bytes, attach CanonInfo, or establish producer
    attestation, source currentness, or authority. Typed JSON consumers use the shared
    profile-aware snapshot reader after selection.

    Args:
        manifest_path: Producer-emitted ``BuildRunManifest`` JSON path.
        store: CAS that receives the exact manifest and output bytes admitted.
        allowed_root: Root that must contain the manifest and every output.
        expected_stage: Exact stage identifier the consumer requested.
        required_outputs: Output basenames the consumer requires.

    Returns:
        A purpose-limited receipt whose output hashes and sizes were recomputed.

    Raises:
        UkraineStageArtifactVerificationError: If any admission check fails.
    """
    from polisyos.data_forge.domains.ukraine.manifests import (
        BuildRunManifest,
    )

    root = allowed_root.resolve()
    resolved_manifest = _resolve_within_root(
        manifest_path,
        root=root,
        label="manifest",
    )
    try:
        manifest_bytes = resolved_manifest.read_bytes()
    except OSError as exc:
        raise UkraineStageArtifactVerificationError(
            f"failed to read stage manifest {resolved_manifest}: {exc}"
        ) from exc
    try:
        manifest = BuildRunManifest.model_validate_json(manifest_bytes)
    except Exception as exc:
        raise UkraineStageArtifactVerificationError(
            f"failed to parse stage manifest {resolved_manifest}: {exc}"
        ) from exc

    stage_id = str(manifest.stage_id.value)
    if stage_id != expected_stage:
        raise UkraineStageArtifactVerificationError(
            f"stage mismatch: expected {expected_stage}, received {stage_id}"
        )
    if manifest.status != "completed":
        raise UkraineStageArtifactVerificationError(
            f"stage status must be completed, received {manifest.status}"
        )

    validated_outputs: dict[str, tuple[Path, bytes, ArtifactRecord]] = {}
    for output in manifest.outputs:
        output_path = _resolve_within_root(Path(output.path), root=root, label="output")
        output_name = output_path.name
        if output_name in validated_outputs:
            raise UkraineStageArtifactVerificationError(
                f"duplicate output basename in stage manifest: {output_name}"
            )
        if not output.sha256:
            raise UkraineStageArtifactVerificationError(
                f"output is missing a declared content hash: {output_name}"
            )
        try:
            output_bytes = output_path.read_bytes()
        except OSError as exc:
            raise UkraineStageArtifactVerificationError(
                f"failed to read stage output {output_name}: {exc}"
            ) from exc
        recomputed_sha256 = _sha256_bytes(output_bytes)
        if recomputed_sha256 != output.sha256:
            raise UkraineStageArtifactVerificationError(
                f"content hash mismatch for output {output_name}"
            )
        recomputed_size = len(output_bytes)
        if recomputed_size != output.size_bytes:
            raise UkraineStageArtifactVerificationError(
                f"content size mismatch for output {output_name}"
            )
        validated_outputs[output_name] = (output_path, output_bytes, output)

    required = {name.strip() for name in required_outputs if name.strip()}
    missing = sorted(required.difference(validated_outputs))
    if missing:
        raise UkraineStageArtifactVerificationError(
            "required stage outputs are missing: " + ",".join(missing)
        )

    manifest_ref = store.put_bytes(
        manifest_bytes,
        core_artifacts.PutOptions(
            kind="data_forge.ukraine.stage_manifest_snapshot",
            media_type="application/json",
            schema=core_artifacts.SchemaInfo(
                name="polisyos.data_forge.ukraine.BuildRunManifest",
                version="1.0",
            ),
        ),
        return_selected_profile=True,
    )
    verified_outputs: dict[str, VerifiedUkraineStageArtifact] = {}
    for output_name, (
        output_path,
        output_bytes,
        output_record,
    ) in validated_outputs.items():
        content_ref = store.put_bytes(
            output_bytes,
            core_artifacts.PutOptions(
                kind="data_forge.ukraine.stage_output_snapshot",
                media_type=_snapshot_media_type(output_path),
            ),
            return_selected_profile=True,
        )
        verified_outputs[output_name] = VerifiedUkraineStageArtifact(
            source_path=str(output_path),
            content_ref=content_ref,
            sha256=_sha256_bytes(output_bytes),
            size_bytes=len(output_bytes),
            row_count=output_record.row_count,
            nnz=output_record.nnz,
            producer_artifact_id=output_record.artifact_id,
        )

    return VerifiedUkraineStageArtifacts(
        stage_id=stage_id,
        run_id=manifest.run_id,
        finished_at=manifest.finished_at,
        manifest_source_path=str(resolved_manifest),
        manifest_ref=manifest_ref,
        manifest_sha256=_sha256_bytes(manifest_bytes),
        outputs=verified_outputs,
    )


def load_verified_stage_output_bytes(
    store: core_artifacts.FileSystemCAS,
    receipt: VerifiedUkraineStageArtifacts,
    output_name: str,
) -> bytes:
    """Read one admitted output from CAS without reopening its producer path.

    Args:
        store: CAS containing the output snapshot named by the receipt.
        receipt: Verified stage receipt produced by :func:`load_verified_stage_artifacts`.
        output_name: Exact output basename to read.

    Returns:
        The immutable bytes admitted during stage verification.

    Raises:
        UkraineStageArtifactVerificationError: If the output is absent or its
            stored bytes no longer match the receipt.
    """

    output = receipt.outputs.get(output_name)
    if output is None:
        raise UkraineStageArtifactVerificationError(
            f"verified receipt lacks required output: {output_name}"
        )
    try:
        output_bytes = store.get_bytes(output.content_ref)
    except Exception as exc:
        raise UkraineStageArtifactVerificationError(
            f"failed to read admitted stage output {output_name}: {exc}"
        ) from exc
    if len(output_bytes) != output.size_bytes:
        raise UkraineStageArtifactVerificationError(
            f"admitted content size mismatch for output {output_name}"
        )
    if _sha256_bytes(output_bytes) != output.sha256:
        raise UkraineStageArtifactVerificationError(
            f"admitted content hash mismatch for output {output_name}"
        )
    return output_bytes


def load_verified_release_artifacts(
    manifest_path: Path,
    *,
    store: core_artifacts.FileSystemCAS,
    allowed_root: Path,
    expected_stage: str,
) -> VerifiedUkraineReleaseArtifacts:
    """Admit exact D5 source bytes and return each write-selected CAS profile.

    The producer's stage and release-root fields remain institutional
    declarations. Path containment, file-set completeness, hashes, sizes, and
    CAS identity are recomputed by this boundary and cannot authorize release.

    Args:
        manifest_path: Producer-emitted ``ReleaseManifest`` path.
        store: CAS receiving the exact bytes read during admission.
        allowed_root: Root containing every declared release path.
        expected_stage: Stage requested by the downstream consumer.

    Returns:
        A frozen, purpose-limited receipt for the admitted release bytes.

    Raises:
        UkraineStageArtifactVerificationError: If any declaration is missing,
            malformed, out of scope, incomplete, or content-drifted.
    """

    from polisyos.data_forge._ukraine_release_contracts import (
        D5ReleaseContentRef,
        D5ReleaseHandoffRequest,
    )
    from polisyos.data_forge.domains.ukraine.manifests import ReleaseManifest

    required_evidence = {
        "cell_registry",
        "d4_governance_request",
        "d5_release_handoff_request",
        "graph_compression_bundle",
    }
    root = allowed_root.resolve()
    resolved_manifest = _resolve_within_root(manifest_path, root=root, label="manifest")
    try:
        manifest_bytes = resolved_manifest.read_bytes()
    except OSError as exc:
        raise UkraineStageArtifactVerificationError(
            f"failed to read release manifest {resolved_manifest}: {exc}"
        ) from exc
    try:
        manifest = ReleaseManifest.model_validate_json(manifest_bytes)
    except Exception as exc:
        raise UkraineStageArtifactVerificationError(
            f"failed to parse release manifest {resolved_manifest}: {exc}"
        ) from exc
    if set(manifest.evidence_refs) != required_evidence:
        raise UkraineStageArtifactVerificationError(
            "release manifest evidence_refs must match the exact D5 set"
        )
    if set(manifest.bundles) != set(manifest.bundle_contents):
        raise UkraineStageArtifactVerificationError(
            "release bundle declarations and content inventories must match exactly"
        )

    read_cache: dict[Path, bytes] = {}

    def _read_record(
        record: ArtifactRecord,
        *,
        label: str,
        containing_directory: Path | None = None,
    ) -> tuple[Path, bytes]:
        resolved = _resolve_within_root(Path(record.path), root=root, label=label)
        if containing_directory is not None and not resolved.is_relative_to(containing_directory):
            raise UkraineStageArtifactVerificationError(
                f"{label} path escapes declared bundle directory: {resolved}"
            )
        if not record.sha256:
            raise UkraineStageArtifactVerificationError(
                f"{label} is missing a declared content hash"
            )
        if resolved not in read_cache:
            try:
                read_cache[resolved] = resolved.read_bytes()
            except OSError as exc:
                raise UkraineStageArtifactVerificationError(
                    f"failed to read {label} {resolved}: {exc}"
                ) from exc
        payload = read_cache[resolved]
        if _sha256_bytes(payload) != record.sha256:
            raise UkraineStageArtifactVerificationError(f"content hash mismatch for {label}")
        if len(payload) != record.size_bytes:
            raise UkraineStageArtifactVerificationError(f"content size mismatch for {label}")
        return resolved, payload

    verified_bundle_bytes: dict[str, dict[str, tuple[Path, bytes]]] = {}
    for bundle_name, bundle_record in manifest.bundles.items():
        bundle_root = _resolve_directory_within_root(
            Path(bundle_record.path), root=root, label=f"bundle {bundle_name}"
        )
        declared_files: dict[str, tuple[Path, bytes]] = {}
        for relative_name, record in manifest.bundle_contents[bundle_name].items():
            declared_files[relative_name] = _read_record(
                record,
                label=f"bundle file {bundle_name}:{relative_name}",
                containing_directory=bundle_root,
            )
            declared_path = declared_files[relative_name][0]
            if declared_path.relative_to(bundle_root).as_posix() != relative_name:
                raise UkraineStageArtifactVerificationError(
                    f"bundle inventory key does not match its path for {bundle_name}"
                )
        actual_paths = {
            candidate.resolve() for candidate in bundle_root.rglob("*") if candidate.is_file()
        }
        declared_paths = {path for path, _payload in declared_files.values()}
        if actual_paths != declared_paths:
            raise UkraineStageArtifactVerificationError(
                f"bundle file inventory mismatch for {bundle_name}"
            )
        if sum(len(payload) for _path, payload in declared_files.values()) != (
            bundle_record.size_bytes
        ):
            raise UkraineStageArtifactVerificationError(
                f"bundle content size mismatch for {bundle_name}"
            )
        verified_bundle_bytes[bundle_name] = declared_files

    verified_evidence_bytes = {
        name: _read_record(record, label=f"release evidence {name}")
        for name, record in manifest.evidence_refs.items()
    }
    _handoff_path, handoff_bytes = verified_evidence_bytes["d5_release_handoff_request"]
    try:
        handoff = D5ReleaseHandoffRequest.model_validate_json(handoff_bytes)
    except Exception as exc:
        raise UkraineStageArtifactVerificationError(f"invalid D5 release handoff: {exc}") from exc
    if handoff.declared_stage != expected_stage:
        raise UkraineStageArtifactVerificationError(
            f"release stage mismatch: expected {expected_stage}, received {handoff.declared_stage}"
        )
    declared_release_root = _resolve_directory_within_root(
        Path(handoff.declared_release_root), root=root, label="declared release root"
    )
    if declared_release_root != resolved_manifest.parent:
        raise UkraineStageArtifactVerificationError(
            "declared release root does not contain the release manifest"
        )
    expected_handoff_refs = {
        name: D5ReleaseContentRef.from_artifact_record(record)
        for name, record in manifest.evidence_refs.items()
        if name != "d5_release_handoff_request"
    }
    if handoff.content_refs != expected_handoff_refs:
        raise UkraineStageArtifactVerificationError(
            "handoff content_refs must equal manifest evidence_refs without the handoff envelope"
        )

    def _persist(path: Path, payload: bytes, *, kind: str) -> VerifiedUkraineReleaseArtifact:
        content_ref = store.put_bytes(
            payload,
            core_artifacts.PutOptions(
                kind=kind,
                media_type=_snapshot_media_type(path),
            ),
            return_selected_profile=True,
        )
        return VerifiedUkraineReleaseArtifact(
            source_path=str(path),
            content_ref=content_ref,
            sha256=_sha256_bytes(payload),
            size_bytes=len(payload),
        )

    manifest_ref = store.put_bytes(
        manifest_bytes,
        core_artifacts.PutOptions(
            kind="data_forge.ukraine.release_manifest_snapshot",
            media_type="application/json",
            schema=core_artifacts.SchemaInfo(
                name="polisyos.data_forge.ukraine.ReleaseManifest",
                version="1.0",
            ),
        ),
        return_selected_profile=True,
    )
    verified_bundles = {
        bundle_name: {
            relative_name: _persist(
                path,
                payload,
                kind="data_forge.ukraine.release_bundle_file_snapshot",
            )
            for relative_name, (path, payload) in files.items()
        }
        for bundle_name, files in verified_bundle_bytes.items()
    }
    verified_evidence = {
        name: _persist(
            path,
            payload,
            kind=(
                "data_forge.ukraine.release_handoff_snapshot"
                if name == "d5_release_handoff_request"
                else "data_forge.ukraine.release_evidence_snapshot"
            ),
        )
        for name, (path, payload) in verified_evidence_bytes.items()
    }
    handoff_snapshot = verified_evidence["d5_release_handoff_request"]
    handoff_profile_read = read_ukraine_json_snapshot(
        store,
        handoff_snapshot.content_ref,
        raw_payload_bytes=handoff_bytes,
        expected_sha256=handoff_snapshot.sha256,
        expected_size_bytes=handoff_snapshot.size_bytes,
        expected_kind="data_forge.ukraine.release_handoff_snapshot",
        consumer_contract="data_forge.ukraine.d5_release_handoff_request",
        model_type=D5ReleaseHandoffRequest,
    )
    selected_handoff = handoff_profile_read.value_for_candidate()
    if selected_handoff != handoff:
        raise UkraineJSONSnapshotRefusalError(
            "ukraine_snapshot_handoff_candidate_mismatch",
            "selected CAS handoff differs from the source-admitted request",
        )
    return VerifiedUkraineReleaseArtifacts(
        stage_id="d5",
        declared_release_root=str(declared_release_root),
        manifest_source_path=str(resolved_manifest),
        manifest_ref=manifest_ref,
        manifest_sha256=_sha256_bytes(manifest_bytes),
        manifest_size_bytes=len(manifest_bytes),
        handoff_request=selected_handoff,
        handoff_snapshot_profile_status=handoff_profile_read.provenance.profile_status,
        bundle_contents=verified_bundles,
        evidence=verified_evidence,
    )


def load_verified_release_artifact_bytes(
    store: core_artifacts.FileSystemCAS,
    artifact: VerifiedUkraineReleaseArtifact,
) -> bytes:
    """Read and recheck one admitted D5 file from CAS only."""

    try:
        payload = store.get_bytes(artifact.content_ref)
    except Exception as exc:
        raise UkraineStageArtifactVerificationError(
            f"failed to read admitted release artifact: {exc}"
        ) from exc
    if len(payload) != artifact.size_bytes:
        raise UkraineStageArtifactVerificationError("admitted release artifact size mismatch")
    if _sha256_bytes(payload) != artifact.sha256:
        raise UkraineStageArtifactVerificationError("admitted release artifact hash mismatch")
    return payload


def _resolve_within_root(path: Path, *, root: Path, label: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise UkraineStageArtifactVerificationError(f"{label} path is unavailable: {path}") from exc
    if not resolved.is_relative_to(root):
        raise UkraineStageArtifactVerificationError(
            f"{label} path escapes allowed root: {resolved}"
        )
    if not resolved.is_file():
        raise UkraineStageArtifactVerificationError(f"{label} path is not a file: {resolved}")
    return resolved


def _resolve_directory_within_root(path: Path, *, root: Path, label: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise UkraineStageArtifactVerificationError(f"{label} path is unavailable: {path}") from exc
    if not resolved.is_relative_to(root):
        raise UkraineStageArtifactVerificationError(
            f"{label} path escapes allowed root: {resolved}"
        )
    if not resolved.is_dir():
        raise UkraineStageArtifactVerificationError(f"{label} path is not a directory: {resolved}")
    return resolved


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _snapshot_media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "application/json"
    if suffix == ".parquet":
        return "application/vnd.apache.parquet"
    if suffix == ".csv":
        return "text/csv"
    return "application/octet-stream"


def load_demography_candidate_artifacts(
    manifest_path: Path,
    *,
    store: core_artifacts.FileSystemCAS,
    allowed_root: Path,
) -> UkraineDemographyArtifacts:
    """Load a candidate inventory stage through the verified-stage/CAS boundary."""
    from polisyos.data_forge.domains.ukraine.demography import (
        InventorySourceRequest,
        load_demography_artifacts,
    )
    from polisyos.data_forge.domains.ukraine.demography.source_inventory import (
        SOURCE_INVENTORY_STAGE_ID,
    )

    receipt = load_verified_stage_artifacts(
        manifest_path,
        store=store,
        allowed_root=allowed_root,
        expected_stage=SOURCE_INVENTORY_STAGE_ID,
        required_outputs=("inventory.json",),
    )
    return load_demography_artifacts(
        source=InventorySourceRequest(kind="inventory", stage_receipt=receipt, store=store)
    )


def __getattr__(name: str) -> object:
    """Lazily resolve Ukraine exports without importing domain internals at module import."""
    return load_lazy_export(name, exports=_EXPORTS, module_name=__name__, namespace=globals())


def __dir__() -> list[str]:
    """Return public Ukraine read_api names without resolving exports."""
    return lazy_dir(globals(), _EXPORTS)


def build_static_aging_state(
    *,
    base_weights: npt.ArrayLike,
    origin_state_index: npt.ArrayLike,
    artifacts: UkraineDemographyArtifacts,
    exit_weights: npt.ArrayLike | None = None,
    microsim_calibration_report: object | None = None,
    microsim_calibration_report_ref: object | None = None,
) -> dict[str, object]:
    """Compose a Foundry-ready state dict for static aging from read_api artifacts."""

    from polisyos.data_forge.domains.ukraine.static_aging import (
        build_static_aging_state as _build_static_aging_state,
    )

    return _build_static_aging_state(
        base_weights=base_weights,
        origin_state_index=origin_state_index,
        artifacts=artifacts,
        exit_weights=exit_weights,
        microsim_calibration_report=microsim_calibration_report,
        microsim_calibration_report_ref=microsim_calibration_report_ref,
    )


# Preserve the previous case-sensitive sorted order of this public sequence.
__all__ = [  # noqa: RUF022
    "ArtifactRecord",
    "CalibrationBundleManifest",
    "D5ReleaseHandoffRequest",
    "DemographyRoleProjection",
    "DemographySourceEvidence",
    "DemographySourceRequest",
    "HistoricalLayoutRequest",
    "HouseholdDiagnosticPanelBasis",
    "InventorySourceRequest",
    "NormalizedArtifactManifest",
    "REAL_BACKTEST_BUNDLE_CONTRACT_FQN",
    "RealBacktestBundleContract",
    "ReleaseManifest",
    "SourceResolutionRefusalError",
    "SourceSnapshotManifest",
    "UKRAINE_ASSET_GROUP",
    "UKRAINE_D4_SOURCE_JSON_SNAPSHOT_ROLE_BY_CONTRACT",
    "UKRAINE_DEMOGRAPHY_DONOR_POOL_KEY",
    "UKRAINE_DEMOGRAPHY_PRIORS_KEY",
    "UKRAINE_DEMOGRAPHY_SOURCE_INVENTORY_KEY",
    "UKRAINE_DEMOGRAPHY_TARGETS_KEY",
    "UKRAINE_NORMALIZED_SOURCES_KEY",
    "UKRAINE_PERIOD_PROJECTION_VERSION",
    "UKRAINE_RAW_SOURCES_KEY",
    "UKRAINE_READINESS_KEY",
    "UKRAINE_SOURCE_CONFIG_KEY",
    "UKRAINE_STATIC_AGING_INPUTS_KEY",
    "UkraineD4GovernanceRequest",
    "UkraineDemographyArtifacts",
    "UkraineIdentityResolutionCohort",
    "UkraineIdentityResolutionCohortRow",
    "UkraineJSONSnapshotProvenance",
    "UkraineJSONSnapshotRead",
    "UkraineJSONSnapshotRefusalError",
    "UkraineLexPreShardDiff",
    "UkraineLexPreShardSummary",
    "UkraineLexShardEntry",
    "UkraineLexShardPassSummary",
    "UkraineReadinessSummary",
    "UkraineShadowArtifact",
    "UkraineShadowBundle",
    "UkraineShadowDiff",
    "UkraineSourceSummary",
    "UkraineStageArtifactVerificationError",
    "VerifiedUkraineReleaseArtifact",
    "VerifiedUkraineReleaseArtifacts",
    "VerifiedUkraineStageArtifact",
    "VerifiedUkraineStageArtifacts",
    "build_household_diagnostic_panel",
    "build_static_aging_state",
    "compare_lex_pre_shard_summaries",
    "compare_ukraine_shadow_bundles",
    "directory_tree_entries",
    "infer_lex_snapshot_label",
    "lex_pre_shard_index",
    "lex_pre_shard_pass_name",
    "load_demography_artifacts",
    "load_demography_candidate_artifacts",
    "load_donor_pool",
    "load_lex_pre_shard_summary",
    "load_manifest",
    "load_reconciled_targets",
    "load_transition_priors",
    "load_ukraine_shadow_bundle",
    "load_verified_release_artifact_bytes",
    "load_verified_release_artifacts",
    "load_verified_release_json_artifact",
    "load_verified_release_manifest_json",
    "load_verified_stage_artifacts",
    "load_verified_stage_json_output",
    "load_verified_stage_manifest_json",
    "load_verified_stage_output_bytes",
    "project_ukraine_observation_periods",
    "read_ukraine_json_snapshot",
    "ukraine_d4_json_snapshot_model_type",
]
