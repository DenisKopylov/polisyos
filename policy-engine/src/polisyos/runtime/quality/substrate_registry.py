"""Production-data substrate registry lifted from existing L5/L1 catalogs.

The registry projects existing L5/L1 metadata and validates registrations
against their declared caps. Explicit source selection additionally streams
baseline and overlay bytes through the existing Catalog identity owner; it
does not load or retain those row payloads. A byte identity is not source
authority, empirical quality, or production currentness.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, NoReturn

import duckdb
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

import polisyos.core as core
from polisyos.pdc import SubstrateLayer, gy_content_hash

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactStore, CoreJSONArtifactStore
    from polisyos.data_forge.read_api.catalog import CatalogContentIdentity, DatasetCatalogStore
    from polisyos.runtime.quality.data_forge_binding import (
        MeasurementRootExecutionBinding,
        ResolvedMeasurementRootEvidence,
    )

ArtifactID = core.artifacts.ArtifactID
ArtifactRef = core.artifacts.ArtifactRef
epoch_contract = core.contracts.epoch

SUBSTRATE_REGISTRY_SCHEMA_VERSION = "policyos.runtime.substrate_registry.v1"
SUBSTRATE_REGISTRY_SCHEMA_NAME = "polisyos.runtime.quality.SubstrateRegistry"
SUBSTRATE_REGISTRY_ARTIFACT_KIND = "runtime.quality.production_data_substrate_registry"
DEFAULT_PRODUCTION_DATA_ROOT = Path("production_data")
DEFAULT_L5_REGISTRY_DIR = Path(
    "production_data/canonical/local_data_20260501/"
    "ukraine_server_support_20260410/runtime_calibration_internals/calibration/d2"
)
DEFAULT_L1_DCAT_PATH = Path(
    "production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb"
)
DEFAULT_ROOT_MANIFEST_PATH = Path("production_data/manifest.json")
DEFAULT_L2_SCHOLAR_KG_PATH = Path(
    "production_data/policyos_academic_runtime_slim_20260411T112032Z/"
    "academic/graph/scholar_knowledge.duckdb"
)
DEFAULT_L3_LEX_KG_PATH = Path(
    "production_data/lex/lex-amendment-only-optimized-20260501-v3/"
    "finalize/lex_knowledge_graph.duckdb"
)
DEFAULT_EPOCH_L5_REGIME_REGISTRY_PATH = Path(
    "architecture/policy_design_case/layer3_gy_l5_schema_regime_registry.json"
)
DEFAULT_EPOCH_L5_SCOPE_REGISTRY_PATH = Path(
    "architecture/policy_design_case/layer3_gy_l5_schema_regime_scope_registry.json"
)


class SubstrateRegistryError(ValueError):
    """Fail-closed error raised when substrate metadata would inflate authority."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


class _StrictModel(BaseModel):
    """Strict immutable base for registry contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class SubstrateCoverage(_StrictModel):
    """Coverage signal copied from an existing catalog authority."""

    coverage_score: float = Field(..., ge=0.0, le=1.0)
    coverage_kind: str = Field(..., min_length=1)
    coverage_rule_ref: str = Field(..., min_length=1)
    dataset_count: int | None = Field(None, ge=0)
    metric_binding_count: int | None = Field(None, ge=0)
    observation_count: int | None = Field(None, ge=0)
    quality_scores: dict[str, float] = Field(default_factory=dict)
    coverage_dimensions: dict[str, Any] = Field(default_factory=dict)


class SubstrateTrustTier(_StrictModel):
    """Trust tier with the L5-declared cap carried explicitly."""

    tier: str = Field(..., min_length=1)
    trust_cap: float = Field(..., ge=0.0, le=1.0)
    trust_multiplier: float = Field(..., ge=0.0, le=1.0)
    min_coverage: float | None = Field(None, ge=0.0, le=1.0)
    max_coverage: float | None = Field(None, ge=0.0, le=1.0)
    authority_ref: str = Field(..., min_length=1)


class SubstrateSchemaRegime(_StrictModel):
    """Schema-regime reference lifted from L5 or the source catalog."""

    schema_regime_id: str = Field(..., min_length=1)
    authority_ref: str = Field(..., min_length=1)
    effective_start: str | None = None
    effective_end: str | None = None
    boundary_buffer_periods: int | None = Field(None, ge=0)
    source_version: str | None = None


class SubstrateRegistryEntry(_StrictModel):
    """One source/family row in the runtime-authority substrate index."""

    source_id: str = Field(..., min_length=1)
    family_id: str = Field(..., min_length=1)
    layer: SubstrateLayer
    coverage: SubstrateCoverage
    trust_tier: SubstrateTrustTier
    identification_mode: str = Field(..., min_length=1)
    schema_regime: SubstrateSchemaRegime
    data_version: str = Field(..., min_length=1)
    snapshot_id: str = Field(..., min_length=1)
    source_snapshot_id: str = Field(..., min_length=1)
    provenance_refs: tuple[str, ...]
    authority_refs: tuple[str, ...]
    entry_content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")

    @field_validator("provenance_refs", "authority_refs")
    @classmethod
    def _refs_must_be_present(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("substrate_entry_refs_missing")
        return value

    @model_validator(mode="after")
    def _validate_entry_content_hash(self) -> SubstrateRegistryEntry:
        expected = substrate_entry_content_hash(self)
        if self.entry_content_hash != expected:
            raise ValueError(
                f"entry_content_hash_mismatch: expected {expected}, got {self.entry_content_hash}"
            )
        return self

    @property
    def registry_key(self) -> tuple[str, str, SubstrateLayer]:
        """Return the unique source/family/layer key."""

        return (self.source_id, self.family_id, self.layer)


class SubstrateRegistration(_StrictModel):
    """Generic free-grow registration input for one substrate source/family."""

    source_id: str = Field(..., min_length=1)
    family_id: str = Field(..., min_length=1)
    layer: SubstrateLayer
    coverage: SubstrateCoverage
    trust_tier: SubstrateTrustTier
    identification_mode: str = Field(..., min_length=1)
    schema_regime: SubstrateSchemaRegime
    data_version: str = Field(..., min_length=1)
    snapshot_id: str = Field(..., min_length=1)
    source_snapshot_id: str = Field(..., min_length=1)
    provenance_refs: tuple[str, ...]
    authority_refs: tuple[str, ...]


class SubstrateRegistry(_StrictModel):
    """Content-addressed version of the production-data metadata substrate."""

    substrate_version_id: str = Field(..., pattern=r"^substrate_version_[a-f0-9]{16}$")
    schema_version: str = SUBSTRATE_REGISTRY_SCHEMA_VERSION
    producer_ref: str = Field(..., min_length=1)
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    source_catalog_refs: tuple[str, ...]
    entries: tuple[SubstrateRegistryEntry, ...]

    @field_validator("entries", "source_catalog_refs")
    @classmethod
    def _not_empty(cls, value: tuple[Any, ...]) -> tuple[Any, ...]:
        if not value:
            raise ValueError("substrate_registry_empty")
        return value

    @model_validator(mode="after")
    def _validate_registry_hash_and_keys(self) -> SubstrateRegistry:
        seen: set[tuple[str, str, SubstrateLayer]] = set()
        duplicates: list[str] = []
        for entry in self.entries:
            if entry.registry_key in seen:
                duplicates.append("|".join(str(part) for part in entry.registry_key))
            seen.add(entry.registry_key)
        if duplicates:
            raise ValueError(f"substrate_registry_duplicate_entry:{','.join(duplicates)}")
        expected = substrate_registry_content_hash(self)
        if self.content_hash != expected:
            raise ValueError(
                f"substrate_registry_content_hash_mismatch: expected {expected}, "
                f"got {self.content_hash}"
            )
        return self

    def resolve(
        self,
        *,
        source_id: str | None = None,
        family_id: str | None = None,
        layer: SubstrateLayer | str | None = None,
    ) -> tuple[SubstrateRegistryEntry, ...]:
        """Resolve entries by source, family, and/or layer."""

        normalized_layer = SubstrateLayer(layer) if layer is not None else None
        matches = [
            entry
            for entry in self.entries
            if (source_id is None or entry.source_id == source_id)
            and (family_id is None or entry.family_id == family_id)
            and (normalized_layer is None or entry.layer is normalized_layer)
        ]
        if not matches:
            raise SubstrateRegistryError(
                "substrate_entry_unresolved",
                json.dumps(
                    {
                        "source_id": source_id,
                        "family_id": family_id,
                        "layer": None if normalized_layer is None else normalized_layer.value,
                    },
                    sort_keys=True,
                ),
            )
        return tuple(matches)


@dataclass(frozen=True)
class MeasurementRootRegistryAdmission:
    """Persisted registry update admitted from an already replayed root.

    The root, fetch, and catalog references are lineage inputs only.  Source,
    family, coverage, trust, identification, and schema fields always come
    from the separately issued :class:`SubstrateRegistration` and are checked
    against the existing L5 authority before a new registry version is built.
    """

    registry: SubstrateRegistry
    registry_ref: ArtifactRef
    input_refs: tuple[core.artifacts.InputRef, ...]
    measurement_root_ref: ArtifactRef
    fetch_receipt_ref: ArtifactRef
    catalog_binding_ref: ArtifactRef
    baseline_registry_ref: ArtifactRef | None


@dataclass(frozen=True)
class SubstrateCatalogPaths:
    """Resolved catalog paths used to lift production-data metadata."""

    production_root: Path
    root_manifest_path: Path
    measurement_registry_path: Path
    identification_mode_registry_path: Path
    schema_regime_registry_path: Path
    l1_dcat_path: Path
    epoch_schema_regime_registry_path: Path | None = None
    epoch_schema_regime_scope_registry_path: Path | None = None


def _catalog_member_relative_path(value: Path) -> Path:
    """Validate the same declared member rule at configuration and fresh read."""

    if not isinstance(value, Path) or value.is_absolute() or not value.parts or ".." in value.parts:
        raise SubstrateRegistryError("catalog_source_database_relative_path_invalid")
    return value


class CatalogServingSourceSelection(_StrictModel):
    """Immutable app configuration selecting a candidate catalog snapshot."""

    snapshot_root: Path
    catalog_run_profile: core.contracts.CatalogRunProfile
    source_owner_root: Path | None = None
    database_relative_path: Path = Path("datasets/graph/dataset_catalog.duckdb")

    @field_validator("database_relative_path")
    @classmethod
    def _database_relative_path_must_stay_within_snapshot(cls, value: Path) -> Path:
        return _catalog_member_relative_path(value)

    @field_validator("source_owner_root")
    @classmethod
    def _source_owner_root_must_be_absolute(cls, value: Path | None) -> Path | None:
        if value is not None and not value.is_absolute():
            raise ValueError("catalog_source_owner_root_must_be_absolute")
        return value

    @field_validator("snapshot_root")
    @classmethod
    def _snapshot_root_must_be_absolute(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("catalog_source_snapshot_root_must_be_absolute")
        return value


@dataclass(frozen=True)
class CatalogServingSourcePaths:
    """Resolved per-app source context; no currentness follows from selecting a path."""

    repo_root: Path
    snapshot_root: Path
    database_path: Path
    index_dir: Path
    overlay_path: Path
    catalog_run_profile: core.contracts.CatalogRunProfile | None
    selection_basis: Literal["legacy_default_candidate_only", "explicit_path_candidate_only"]
    substrate_paths: SubstrateCatalogPaths
    source_owner_root: Path | None = None
    database_relative_path: Path = Path("datasets/graph/dataset_catalog.duckdb")
    read_source_identity: (
        tuple[CatalogContentIdentity, str | None, CatalogContentIdentity | None] | None
    ) = None


_ACTIVE_CATALOG_SOURCE: ContextVar[CatalogServingSourcePaths | None] = ContextVar(
    "polisyos_active_catalog_source",
    default=None,
)


@contextmanager
def catalog_serving_source_scope(
    source: CatalogServingSourcePaths | None,
) -> Iterator[None]:
    """Bind one exact source through a complete sync or async candidate call chain."""

    if source is None:
        yield
        return
    if type(source) is not CatalogServingSourcePaths:
        raise SubstrateRegistryError("catalog_source_context_invalid")
    token = _ACTIVE_CATALOG_SOURCE.set(source)
    try:
        yield
    finally:
        _ACTIVE_CATALOG_SOURCE.reset(token)


def current_catalog_serving_source() -> CatalogServingSourcePaths | None:
    """Return the source bound to this request context, if any."""

    return _ACTIVE_CATALOG_SOURCE.get()


def require_active_catalog_source(source: CatalogServingSourcePaths | None) -> None:
    """Require an owner to run inside the exact source context used to construct it."""

    if source is not None and current_catalog_serving_source() is not source:
        raise SubstrateRegistryError("catalog_source_context_mismatch")


async def run_catalog_source_awaitable[CatalogAwaitableResult](
    source: CatalogServingSourcePaths,
    awaitable: Awaitable[CatalogAwaitableResult],
) -> CatalogAwaitableResult:
    """Await one complete run while its immutable catalog source is context-bound."""

    with catalog_serving_source_scope(source):
        return await awaitable


def run_catalog_source_call[**CatalogCallParameters, CatalogCallResult](
    source: CatalogServingSourcePaths | None,
    call: Callable[CatalogCallParameters, CatalogCallResult],
    *args: CatalogCallParameters.args,
    **kwargs: CatalogCallParameters.kwargs,
) -> CatalogCallResult:
    """Call one complete synchronous run with the same request-local source binding."""

    with catalog_serving_source_scope(source):
        return call(*args, **kwargs)


def _catalog_read_source_identity(
    source: CatalogServingSourcePaths,
) -> tuple[CatalogContentIdentity, str | None, CatalogContentIdentity | None]:
    """Recompute the exact deciding baseline/overlay tuple at its Catalog owner."""

    from polisyos.data_forge.read_api import catalog as data_forge_catalog
    from polisyos.data_forge.read_api.catalog import DatasetCatalogStore

    expected = source.snapshot_root / _catalog_member_relative_path(source.database_relative_path)
    try:
        resolved = expected.resolve(strict=True)
        if resolved != expected or resolved != source.database_path or not resolved.is_file():
            raise SubstrateRegistryError("catalog_source_database_path_unbound")
        if source.source_owner_root is not None:
            _require_catalog_path_within_owner(resolved, source.source_owner_root)
        return DatasetCatalogStore.identify_read_sources(resolved, overlay_path=source.overlay_path)
    except SubstrateRegistryError:
        raise
    except data_forge_catalog.CatalogSelectionError as exc:
        raise SubstrateRegistryError(exc.code, str(exc)) from exc
    except (OSError, RuntimeError, ValueError) as exc:
        raise SubstrateRegistryError("catalog_source_database_unavailable", str(exc)) from exc


def require_catalog_serving_source_unchanged(source: CatalogServingSourcePaths) -> None:
    """Refuse a missing admission or changed explicit catalog before consumption."""

    if source.selection_basis == "legacy_default_candidate_only":
        return
    if source.selection_basis != "explicit_path_candidate_only":
        raise SubstrateRegistryError("catalog_source_context_invalid")
    if source.read_source_identity is None:
        raise SubstrateRegistryError("catalog_source_readmission_required")
    if _catalog_read_source_identity(source) != source.read_source_identity:
        raise SubstrateRegistryError("catalog_source_content_changed_readmission_required")


def _catalog_content_ref(source: CatalogServingSourcePaths) -> str:
    """Name exact selected read sources without granting their bytes authority."""

    require_catalog_serving_source_unchanged(source)
    identity = source.read_source_identity
    if identity is None:
        raise SubstrateRegistryError("catalog_source_readmission_required")
    baseline, overlay_path, overlay = identity
    payload = {
        "baseline": baseline.model_dump(mode="json"),
        "overlay_path": overlay_path,
        "overlay": None if overlay is None else overlay.model_dump(mode="json"),
    }
    return f"catalog_read_source_content://{gy_content_hash(payload)}"


def require_catalog_serving_graph_binding(graph: object, source: CatalogServingSourcePaths) -> None:
    """Reject an injected graph that does not use the explicitly selected database."""

    require_catalog_serving_source_unchanged(source)
    if source.selection_basis == "explicit_path_candidate_only":
        from polisyos.data_forge.read_api.catalog import DatasetCatalogGraph, DatasetCatalogStore

        if type(graph) not in (DatasetCatalogGraph, DatasetCatalogStore):
            raise SubstrateRegistryError("catalog_source_graph_owner_unverified")
        observed = getattr(graph, "database_path", None)
        identity = getattr(graph, "read_source_identity", None)
        if (
            observed is None
            or Path(observed).resolve() != source.database_path
            or identity is None
            or source.read_source_identity is None
            or identity != source.read_source_identity
        ):
            raise SubstrateRegistryError("catalog_source_graph_binding_mismatch")


@contextmanager
def catalog_source_reader(
    repo_root: Path,
    *,
    overlay_path: Path | None = None,
    production_data_root: Path | None = None,
) -> Iterator[DatasetCatalogStore]:
    """Guard a complete Runtime read through the canonical Catalog owner.

    The scope spans profile reconstruction as well as native row reads.
    Count semantics remain owned by Store; source-state failures retain their
    exact codes and are never interpreted as a missing variable's zero count.
    """

    from polisyos.data_forge.read_api import catalog as catalog_api

    source = current_catalog_serving_source()
    paths = default_substrate_catalog_paths(repo_root, source_owner_root=production_data_root)
    selected_overlay = (
        overlay_path
        if overlay_path is not None
        else (
            source.overlay_path
            if source is not None
            else catalog_api.default_acquisition_overlay_path(repo_root)
        )
    )
    try:
        reader = catalog_api.DatasetCatalogStore(
            paths.l1_dcat_path, paths.l1_dcat_path.parent, overlay_path=selected_overlay
        )
    except catalog_api.CatalogSelectionError as exc:
        raise SubstrateRegistryError(exc.code, str(exc)) from exc
    except (catalog_api.BaselineMutationError, catalog_api.OverlayAdmissionError) as exc:
        raise SubstrateRegistryError(exc.code, str(exc)) from exc
    except (OSError, ValueError, duckdb.Error) as exc:
        raise SubstrateRegistryError("catalog_read_session_unavailable", str(exc)) from exc
    try:
        try:
            with reader.read_session():
                if source is not None:
                    require_catalog_serving_graph_binding(reader, source)
                yield reader
        except catalog_api.CatalogSelectionError as exc:
            if isinstance(exc, catalog_api.CatalogReadSourceError):
                raise SubstrateRegistryError(exc.code, str(exc)) from exc
            raise
    finally:
        reader.close()


def require_catalog_source_registry_binding(
    repo_root: Path,
    registry: SubstrateRegistry,
    source: CatalogServingSourcePaths | None,
) -> None:
    """Reconcile a pre-bound registry against the source selected for this run."""

    if source is None:
        return
    require_catalog_serving_source_unchanged(source)
    if source.selection_basis != "explicit_path_candidate_only":
        return
    require_active_catalog_source(source)
    selected_ref = _catalog_content_ref(source)
    if not any(
        ref.startswith("catalog_read_source_content://") for ref in registry.source_catalog_refs
    ):
        raise SubstrateRegistryError("catalog_source_registry_readmission_required")
    if selected_ref not in registry.source_catalog_refs:
        raise SubstrateRegistryError("catalog_source_registry_binding_mismatch")
    selected = build_substrate_registry_from_existing_catalogs(repo_root)
    if selected.content_hash != registry.content_hash:
        raise SubstrateRegistryError("catalog_source_registry_binding_mismatch")


def resolve_catalog_serving_source(
    repo_root: Path,
    *,
    selection: CatalogServingSourceSelection | None,
    requested_profile: core.contracts.CatalogRunProfile | None,
) -> CatalogServingSourcePaths:
    """Resolve one source at composition time; a selected path is candidate input only."""

    from polisyos.data_forge.read_api.catalog import default_acquisition_overlay_path

    root = Path(repo_root).resolve()
    defaults = default_substrate_catalog_paths(root)
    overlay = default_acquisition_overlay_path(root)
    if selection is None:
        return CatalogServingSourcePaths(
            repo_root=root,
            snapshot_root=root,
            database_path=defaults.l1_dcat_path,
            index_dir=defaults.l1_dcat_path.parent,
            overlay_path=overlay,
            catalog_run_profile=requested_profile,
            selection_basis="legacy_default_candidate_only",
            substrate_paths=defaults,
        )
    if type(selection) is not CatalogServingSourceSelection:
        raise SubstrateRegistryError("catalog_source_selection_invalid")
    if requested_profile is not None and requested_profile != selection.catalog_run_profile:
        raise SubstrateRegistryError("catalog_source_selection_profile_mismatch")
    try:
        snapshot_root = selection.snapshot_root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise SubstrateRegistryError("catalog_source_snapshot_missing") from exc
    if not snapshot_root.is_dir():
        raise SubstrateRegistryError("catalog_source_snapshot_not_directory")
    expected = snapshot_root / selection.database_relative_path
    try:
        database_path = expected.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise SubstrateRegistryError("catalog_source_database_missing") from exc
    # Canonicalize a declared root symlink; reject a database member that redirects below it.
    if database_path != expected or not database_path.is_file():
        raise SubstrateRegistryError("catalog_source_database_path_unbound")
    source_owner_root = None
    if selection.source_owner_root is not None:
        try:
            source_owner_root = selection.source_owner_root.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise SubstrateRegistryError("substrate_source_owner_root_unavailable") from exc
        if not source_owner_root.is_dir():
            raise SubstrateRegistryError("substrate_source_owner_root_not_directory")
        owner_defaults = default_substrate_catalog_paths(root, source_owner_root=source_owner_root)
        _require_catalog_path_within_owner(snapshot_root, source_owner_root)
        paths = replace(owner_defaults, l1_dcat_path=database_path)
    else:
        paths = replace(defaults, l1_dcat_path=database_path)
    source = CatalogServingSourcePaths(
        repo_root=root,
        snapshot_root=snapshot_root,
        database_path=database_path,
        index_dir=database_path.parent,
        overlay_path=overlay,
        catalog_run_profile=selection.catalog_run_profile,
        selection_basis="explicit_path_candidate_only",
        substrate_paths=paths,
        source_owner_root=source_owner_root,
        database_relative_path=selection.database_relative_path,
    )
    return replace(source, read_source_identity=_catalog_read_source_identity(source))


@dataclass(frozen=True)
class L5CatalogAuthority:
    """L5 authority rows used to cap coverage, trust, and identification."""

    measurement_registry_ref: str
    identification_mode_registry_ref: str
    schema_regime_registry_ref: str
    coverage_rules: Mapping[str, float]
    trust_tiers: Mapping[str, SubstrateTrustTier]
    proxy_mappings: Mapping[str, Mapping[str, Any]]
    identification_modes: Mapping[str, str]
    schema_regimes: Mapping[str, SubstrateSchemaRegime]
    schema_regime_rows: Mapping[str, Mapping[str, Any]]
    schema_regime_scope_relations: tuple[epoch_contract.L5SchemaRegimeScopeRelation, ...]
    schema_regime_changepoints: tuple[Mapping[str, Any], ...]
    epoch_schema_regime_registry_ref: ArtifactRef
    epoch_schema_regime_registry_content_hash: epoch_contract.Digest
    epoch_schema_regime_scope_registry_ref: ArtifactRef
    epoch_schema_regime_scope_registry_content_hash: epoch_contract.Digest
    epoch_schema_regime_registry_source_bytes: bytes = b""
    epoch_schema_regime_scope_registry_source_bytes: bytes = b""

    def load_schema_regime_source_artifact_bytes(self, *, ref: ArtifactRef) -> bytes:
        """Return exact registry bytes only for the matching owner-issued file ref."""
        sources = (
            (
                self.epoch_schema_regime_registry_ref,
                self.epoch_schema_regime_registry_content_hash,
                self.epoch_schema_regime_registry_source_bytes,
            ),
            (
                self.epoch_schema_regime_scope_registry_ref,
                self.epoch_schema_regime_scope_registry_content_hash,
                self.epoch_schema_regime_scope_registry_source_bytes,
            ),
        )
        for expected_ref, expected_hash, payload in sources:
            if ref == expected_ref:
                actual_hash = f"sha256:{hashlib.sha256(payload).hexdigest()}"
                if (
                    not payload
                    or actual_hash != expected_hash
                    or str(ref.artifact_id) != expected_hash
                ):
                    raise SubstrateRegistryError("l5_registry_source_bytes_not_established")
                return payload
        raise SubstrateRegistryError("l5_registry_source_ref_not_owned")

    def _schema_regime_owner_snapshot_bytes(self) -> bytes:
        return epoch_contract.canonical_epoch_bytes(
            {
                "regimes": {
                    key: dict(value) for key, value in sorted(self.schema_regime_rows.items())
                },
                "scope_relations": [
                    row.model_dump(mode="json") for row in self.schema_regime_scope_relations
                ],
                "changepoints": [dict(row) for row in self.schema_regime_changepoints],
            }
        )

    def load_schema_regime_owner_snapshot(self, *, ref: ArtifactRef) -> bytes:
        """Reload the exact owner bytes named by a denominator receipt."""

        payload = self._schema_regime_owner_snapshot_bytes()
        expected = ArtifactRef(
            artifact_id=ArtifactID.model_validate(f"sha256:{hashlib.sha256(payload).hexdigest()}"),
            kind="l5.schema_regime_owner_snapshot",
            media_type="application/json",
        )
        if ref != expected:
            raise SubstrateRegistryError("l5_schema_regime_owner_snapshot_ref_stale")
        return payload

    def resolve_schema_regime_denominator(
        self, *, query: epoch_contract.L5SchemaRegimeResolutionQuery
    ) -> epoch_contract.L5SchemaRegimeDenominatorReceipt:
        """Assess every L5 regime against owner-held scope and valid time."""

        visibility_cutoff = _l5_cutoff_datetime(
            query.visibility_knowledge_cutoff_bytes,
            role="visibility_knowledge_cutoff",
        )
        admission_cutoff = _l5_cutoff_datetime(
            query.purpose_admission_cutoff_bytes,
            role="purpose_admission_cutoff",
        )
        relations_by_regime: dict[str, list[epoch_contract.L5SchemaRegimeScopeRelation]] = {}
        for relation in self.schema_regime_scope_relations:
            if (
                relation.visibility_knowledge_from <= visibility_cutoff
                and relation.purpose_admission_from <= admission_cutoff
            ):
                relations_by_regime.setdefault(relation.schema_regime_id, []).append(relation)
        assessments: list[epoch_contract.L5SchemaRegimeAssessment] = []
        scope_regime_ids = {
            regime_id
            for regime_id, relations in relations_by_regime.items()
            if any(
                query.scope_identity_ref in relation.scope_identity_refs for relation in relations
            )
        }
        effective_starts = sorted(
            date.fromisoformat(regime.effective_start)
            for regime_id, regime in self.schema_regimes.items()
            if regime_id in scope_regime_ids and regime.effective_start is not None
        )
        for regime_id, regime in sorted(self.schema_regimes.items()):
            raw_row = dict(self.schema_regime_rows[regime_id])
            row_bytes = epoch_contract.canonical_epoch_bytes(raw_row)
            row_digest = f"sha256:{hashlib.sha256(row_bytes).hexdigest()}"
            row_ref = ArtifactRef(
                artifact_id=ArtifactID.model_validate(row_digest),
                kind="l5.schema_regime",
                media_type="application/json",
            )
            relations = relations_by_regime.get(regime_id, [])
            distinct_relations = {
                (
                    tuple(relation.scope_identity_refs),
                    str(relation.relation_provenance_ref.artifact_id),
                )
                for relation in relations
            }
            relation: epoch_contract.L5SchemaRegimeScopeRelation | None = None
            failure_code: str | None = None
            if not relations:
                failure_code = "schema_regime_scope_missing"
            elif len(distinct_relations) != 1:
                failure_code = "schema_regime_scope_ambiguous"
            else:
                relation = relations[0]
            start = (
                None
                if regime.effective_start is None
                else date.fromisoformat(regime.effective_start)
            )
            end = None if regime.effective_end is None else date.fromisoformat(regime.effective_end)
            next_start = next(
                (value for value in effective_starts if start is not None and value > start),
                None,
            )
            effective_end_exclusive = next_start if end is None else end
            in_window = (start is None or start <= query.valid_effect_value) and (
                effective_end_exclusive is None
                or query.valid_effect_value < effective_end_exclusive
            )
            if failure_code is not None:
                disposition = "unresolved"
            elif relation is not None and (
                query.scope_identity_ref in relation.scope_identity_refs and in_window
            ):
                disposition = "applicable"
            else:
                disposition = "not_applicable"
            assessments.append(
                epoch_contract.L5SchemaRegimeAssessment(
                    schema_regime_id=regime_id,
                    regime_source_ref=row_ref,
                    regime_content_hash=row_digest,
                    scope_relation=relation,
                    disposition=disposition,
                    failure_code=failure_code,
                )
            )
        snapshot_bytes = self._schema_regime_owner_snapshot_bytes()
        snapshot_digest = f"sha256:{hashlib.sha256(snapshot_bytes).hexdigest()}"
        snapshot_ref = ArtifactRef(
            artifact_id=ArtifactID.model_validate(snapshot_digest),
            kind="l5.schema_regime_owner_snapshot",
            media_type="application/json",
        )
        failures = tuple(sorted({row.failure_code for row in assessments if row.failure_code}))
        denominator_bytes = epoch_contract.canonical_epoch_bytes(
            {
                "query": query.model_dump(mode="json"),
                "owner_source_snapshot_content_hash": snapshot_digest,
                "assessments": [row.model_dump(mode="json") for row in assessments],
            }
        )
        return epoch_contract.L5SchemaRegimeDenominatorReceipt(
            query=query,
            owner_source_snapshot_ref=snapshot_ref,
            owner_source_snapshot_content_hash=snapshot_digest,
            regime_registry_ref=self.epoch_schema_regime_registry_ref,
            regime_registry_content_hash=self.epoch_schema_regime_registry_content_hash,
            scope_registry_ref=self.epoch_schema_regime_scope_registry_ref,
            scope_registry_content_hash=self.epoch_schema_regime_scope_registry_content_hash,
            declared_regime_count=len(assessments),
            assessments=tuple(assessments),
            denominator_hash=(f"sha256:{hashlib.sha256(denominator_bytes).hexdigest()}"),
            status="unresolved" if failures else "resolved",
            failure_codes=failures,
            predicate_class="independently_reconciled",
        )

    def project_scoped_schema_regimes(
        self, *, receipt: epoch_contract.L5SchemaRegimeDenominatorReceipt
    ) -> epoch_contract.ScopedSchemaRegimeProjection:
        """Project only regimes admitted by the exact recomputed L5 receipt."""

        if self.resolve_schema_regime_denominator(query=receipt.query) != receipt:
            raise SubstrateRegistryError("l5_schema_regime_receipt_stale")
        applicable = tuple(row for row in receipt.assessments if row.disposition == "applicable")
        changepoint_refs = tuple(
            f"sha256:{hashlib.sha256(epoch_contract.canonical_epoch_bytes(dict(row))).hexdigest()}"
            for row in self.schema_regime_changepoints
            if str(row.get("from_schema_regime_id"))
            in {item.schema_regime_id for item in applicable}
            or str(row.get("to_schema_regime_id")) in {item.schema_regime_id for item in applicable}
        )
        status: Literal["resolved", "unresolved", "contested"]
        if receipt.status == "unresolved" or not applicable:
            status = "unresolved"
        elif len(applicable) > 1:
            status = "contested"
        else:
            status = "resolved"
        owner_source_snapshot_ref = ArtifactRef.model_validate(
            receipt.owner_source_snapshot_ref.model_dump(mode="python")
        )
        receipt_bytes = epoch_contract.canonical_epoch_bytes(receipt)
        denominator_receipt_ref = ArtifactRef.model_validate(
            {
                "artifact_id": (
                    "sha256:"
                    + hashlib.sha256(
                        len(receipt_bytes).to_bytes(8, "big") + receipt_bytes
                    ).hexdigest()
                ),
                "kind": "l5.schema_regime_denominator_receipt",
                "media_type": "application/vnd.polisyos.epoch+json",
            }
        )
        mapping = {
            "scope_identity_ref": receipt.query.scope_identity_ref,
            "valid_effect_coordinate_ref": receipt.query.valid_effect_coordinate_ref,
            "requested_query_context_ref": receipt.query.requested_query_context_ref,
            "owner_source_snapshot_ref": owner_source_snapshot_ref,
            "denominator_receipt_ref": denominator_receipt_ref,
            "applicable_regime_ids": [row.schema_regime_id for row in applicable],
            "applicable_regime_content_hashes": [row.regime_content_hash for row in applicable],
            "changepoint_refs": list(changepoint_refs),
            "status": status,
        }
        projection_content_hash = epoch_contract.scoped_schema_regime_projection_content_hash(
            mapping
        )
        return epoch_contract.ScopedSchemaRegimeProjection(
            **mapping,
            projection_content_hash=projection_content_hash,
        )

    def latest_schema_regime(self) -> SubstrateSchemaRegime:
        """Return the latest effective L5 schema regime."""

        if not self.schema_regimes:
            raise SubstrateRegistryError("l5_schema_regime_missing")
        return max(
            self.schema_regimes.values(),
            key=lambda regime: regime.effective_start or "",
        )

    def expected_trust_tier(self, family_id: str) -> SubstrateTrustTier:
        """Return the L5-capped trust tier for a family."""

        coverage = self.coverage_rules.get(family_id)
        if coverage is None:
            raise SubstrateRegistryError("l5_family_coverage_missing", family_id)
        return self._trust_tier_for_score(float(coverage))

    def trust_tier_for_score(self, score: float) -> SubstrateTrustTier:
        """Cap a source-quality score using only L5-declared tier bounds."""

        return self._trust_tier_for_score(float(score))

    def minimum_positive_coverage_floor(self, *, default: float) -> float:
        """Return the lowest positive L5 trust-tier coverage floor."""

        floors = sorted(
            float(tier.min_coverage)
            for tier in self.trust_tiers.values()
            if tier.min_coverage is not None and tier.min_coverage > 0.0
        )
        return floors[0] if floors else default

    def validate_trust_tier_bounds(
        self,
        registration: SubstrateRegistration,
        *,
        expected_tier: SubstrateTrustTier | None = None,
    ) -> None:
        """Reject trust fields that exceed the real L5 row for the tier."""

        tier = expected_tier or self.trust_tiers.get(registration.trust_tier.tier)
        if tier is None:
            raise SubstrateRegistryError(
                "substrate_trust_tier_unresolved",
                registration.trust_tier.tier,
            )
        if registration.trust_tier.trust_cap > tier.trust_cap + 1e-9:
            raise SubstrateRegistryError(
                "substrate_trust_cap_inflated",
                (
                    f"{registration.family_id}: {registration.trust_tier.trust_cap} "
                    f"> {tier.trust_cap} for tier {tier.tier}"
                ),
            )
        if registration.trust_tier.trust_multiplier > tier.trust_multiplier + 1e-9:
            raise SubstrateRegistryError(
                "substrate_trust_multiplier_inflated",
                (
                    f"{registration.family_id}: {registration.trust_tier.trust_multiplier} "
                    f"> {tier.trust_multiplier} for tier {tier.tier}"
                ),
            )

    def validate_registration(self, registration: SubstrateRegistration) -> None:
        """Reject registrations that claim more authority than L5 allows."""

        family_id = registration.family_id
        self.validate_trust_tier_bounds(registration)
        if family_id in self.coverage_rules:
            allowed_coverage = float(self.coverage_rules[family_id])
            if registration.coverage.coverage_score > allowed_coverage + 1e-9:
                raise SubstrateRegistryError(
                    "substrate_coverage_inflated",
                    f"{family_id}: {registration.coverage.coverage_score} > {allowed_coverage}",
                )
            expected_identification = self.identification_modes.get(family_id)
            if (
                expected_identification is not None
                and registration.identification_mode != expected_identification
            ):
                raise SubstrateRegistryError(
                    "substrate_identification_mode_inflated",
                    f"{family_id}: {registration.identification_mode} != {expected_identification}",
                )
            expected_tier = self.expected_trust_tier(family_id)
            self.validate_trust_tier_bounds(registration, expected_tier=expected_tier)
        if (
            registration.schema_regime.schema_regime_id not in self.schema_regimes
            and not registration.schema_regime.schema_regime_id.startswith("dcat:")
            and not registration.schema_regime.schema_regime_id.startswith("manifest:")
        ):
            raise SubstrateRegistryError(
                "substrate_schema_regime_unresolved",
                registration.schema_regime.schema_regime_id,
            )

    def _tier(self, tier: str) -> SubstrateTrustTier:
        value = self.trust_tiers.get(tier)
        if value is None:
            raise SubstrateRegistryError("l5_trust_tier_missing", tier)
        return value

    def _trust_tier_for_score(self, score: float) -> SubstrateTrustTier:
        """Select the strongest L5 tier whose numeric coverage bounds admit score."""

        eligible = [
            tier
            for tier in self.trust_tiers.values()
            if score + 1e-9 >= (tier.min_coverage or 0.0)
            and score <= (tier.max_coverage if tier.max_coverage is not None else 1.0) + 1e-9
        ]
        if not eligible:
            raise SubstrateRegistryError("l5_trust_tier_missing_for_score", str(score))

        positive_floor = self.minimum_positive_coverage_floor(default=1.0)
        if score + 1e-9 < positive_floor:
            return min(eligible, key=_trust_tier_strength_key)
        return max(eligible, key=_trust_tier_strength_key)


def _trust_tier_strength_key(
    tier: SubstrateTrustTier,
) -> tuple[float, float, float, str]:
    return (
        float(tier.min_coverage or 0.0),
        float(tier.trust_cap),
        float(tier.trust_multiplier),
        tier.tier,
    )


def _l5_cutoff_datetime(raw: bytes, *, role: str) -> datetime:
    """Decode one owner-interpreted cutoff without present-time substitution."""

    try:
        text = raw.decode("utf-8")
        value = datetime.fromisoformat(
            text.removesuffix("Z") + ("+00:00" if text.endswith("Z") else "")
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise SubstrateRegistryError(f"l5_{role}_invalid") from exc
    if value.tzinfo is None:
        raise SubstrateRegistryError(f"l5_{role}_timezone_missing")
    return value.astimezone(UTC)


def _l5_current_cutoff_bytes(
    authority: L5CatalogAuthority,
    *,
    role: Literal["visibility_knowledge", "purpose_admission"],
) -> bytes:
    """Derive the current owner snapshot cutoff from its complete relation history."""

    if not authority.schema_regime_scope_relations:
        raise SubstrateRegistryError("l5_schema_regime_scope_relation_missing")
    values = (
        (
            row.visibility_knowledge_from
            if role == "visibility_knowledge"
            else row.purpose_admission_from
        )
        for row in authority.schema_regime_scope_relations
    )
    latest = max(value.astimezone(UTC) for value in values)
    return latest.isoformat().replace("+00:00", "Z").encode("utf-8")


def resolve_l5_schema_regime_projection(
    authority: L5CatalogAuthority,
    *,
    scope_identity_ref: epoch_contract.Digest,
    valid_effect_value: date,
    authority_purpose: str,
) -> tuple[
    epoch_contract.L5SchemaRegimeDenominatorReceipt,
    epoch_contract.ScopedSchemaRegimeProjection,
]:
    """Resolve one exact owner-scoped projection from current tracked L5 bytes."""

    valid_bytes = valid_effect_value.isoformat().encode("utf-8")
    visibility_bytes = _l5_current_cutoff_bytes(
        authority,
        role="visibility_knowledge",
    )
    admission_bytes = _l5_current_cutoff_bytes(
        authority,
        role="purpose_admission",
    )
    profiles = {
        "valid_effect": "polisyos.l5.valid-date.v1",
        "visibility_knowledge_cutoff": "polisyos.l5.knowledge-time.v1",
        "purpose_admission_cutoff": "polisyos.l5.admission-time.v1",
    }
    coordinate_refs = {
        "valid_effect": epoch_contract.native_coordinate_ref(
            family="l5_schema_regime",
            role="valid_effect",
            schema_profile=profiles["valid_effect"],
            coordinate_bytes=valid_bytes,
        ),
        "visibility_knowledge_cutoff": epoch_contract.native_coordinate_ref(
            family="l5_schema_regime",
            role="visibility_knowledge_cutoff",
            schema_profile=profiles["visibility_knowledge_cutoff"],
            coordinate_bytes=visibility_bytes,
        ),
        "purpose_admission_cutoff": epoch_contract.native_coordinate_ref(
            family="l5_schema_regime",
            role="purpose_admission_cutoff",
            schema_profile=profiles["purpose_admission_cutoff"],
            coordinate_bytes=admission_bytes,
        ),
    }
    query = epoch_contract.L5SchemaRegimeResolutionQuery(
        scope_identity_ref=scope_identity_ref,
        authority_purpose=authority_purpose,
        valid_effect_value=valid_effect_value,
        valid_effect_coordinate_schema_profile=profiles["valid_effect"],
        valid_effect_coordinate_ref=coordinate_refs["valid_effect"],
        visibility_knowledge_cutoff_schema_profile=profiles["visibility_knowledge_cutoff"],
        visibility_knowledge_cutoff_bytes=visibility_bytes,
        visibility_knowledge_cutoff_ref=coordinate_refs["visibility_knowledge_cutoff"],
        purpose_admission_cutoff_schema_profile=profiles["purpose_admission_cutoff"],
        purpose_admission_cutoff_bytes=admission_bytes,
        purpose_admission_cutoff_ref=coordinate_refs["purpose_admission_cutoff"],
        requested_query_context_ref=epoch_contract.epoch_query_context_ref(
            family="l5_schema_regime",
            scope_bytes=scope_identity_ref.encode("ascii"),
            authority_purpose=authority_purpose,
            coordinate_refs=tuple(coordinate_refs.values()),
        ),
    )
    receipt = authority.resolve_schema_regime_denominator(query=query)
    return receipt, authority.project_scoped_schema_regimes(receipt=receipt)


def l5_owner_scope_identity_refs(
    authority: L5CatalogAuthority,
) -> tuple[epoch_contract.Digest, ...]:
    """Return the complete owner-declared scope denominator."""

    return tuple(
        sorted(
            {
                scope_ref
                for relation in authority.schema_regime_scope_relations
                for scope_ref in relation.scope_identity_refs
            }
        )
    )


def default_substrate_catalog_paths(
    repo_root: Path,
    *,
    source_owner_root: Path | None = None,
) -> SubstrateCatalogPaths:
    """Return typed catalog paths with code and selected data roots kept separate.

    ``repo_root`` remains the owner of architecture and epoch registries. When
    ``source_owner_root`` is supplied, only production-data paths are resolved
    beneath that physical owner. The one-root default and active serving-source
    behavior remain unchanged.
    """

    root = repo_root.resolve()
    active_source = current_catalog_serving_source()
    if source_owner_root is None and active_source is not None:
        if active_source.repo_root != root:
            raise SubstrateRegistryError("catalog_source_repo_root_mismatch")
        require_catalog_serving_source_unchanged(active_source)
        return active_source.substrate_paths

    data_root = root
    if source_owner_root is not None:
        try:
            data_root = Path(source_owner_root).resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise SubstrateRegistryError("substrate_source_owner_root_unavailable") from exc
        if not data_root.is_dir():
            raise SubstrateRegistryError("substrate_source_owner_root_not_directory")
    l5_dir = data_root / DEFAULT_L5_REGISTRY_DIR
    expected = SubstrateCatalogPaths(
        production_root=data_root / DEFAULT_PRODUCTION_DATA_ROOT,
        root_manifest_path=data_root / DEFAULT_ROOT_MANIFEST_PATH,
        measurement_registry_path=l5_dir / "measurement_registry.json",
        identification_mode_registry_path=l5_dir / "identification_mode_registry.json",
        schema_regime_registry_path=l5_dir / "schema_regime_registry.json",
        l1_dcat_path=data_root / DEFAULT_L1_DCAT_PATH,
        epoch_schema_regime_registry_path=root / DEFAULT_EPOCH_L5_REGIME_REGISTRY_PATH,
        epoch_schema_regime_scope_registry_path=root / DEFAULT_EPOCH_L5_SCOPE_REGISTRY_PATH,
    )
    if active_source is None:
        return expected
    if active_source.repo_root != root:
        raise SubstrateRegistryError("catalog_source_repo_root_mismatch")
    require_catalog_serving_source_unchanged(active_source)
    active_paths = active_source.substrate_paths
    if active_paths.root_manifest_path.resolve() != expected.root_manifest_path.resolve():
        raise SubstrateRegistryError("catalog_source_split_root_mismatch")
    _require_catalog_path_within_owner(active_paths.production_root, data_root)
    for path in (
        active_paths.root_manifest_path,
        active_paths.measurement_registry_path,
        active_paths.identification_mode_registry_path,
        active_paths.schema_regime_registry_path,
        active_paths.l1_dcat_path,
    ):
        _require_catalog_path_within_owner(path, data_root)
    for path in (
        active_paths.epoch_schema_regime_registry_path,
        active_paths.epoch_schema_regime_scope_registry_path,
    ):
        if path is None:
            raise SubstrateRegistryError("l5_epoch_registry_paths_not_established")
        _require_catalog_path_within_owner(path, root)
    return active_paths


def _require_catalog_path_within_owner(path: Path, owner_root: Path) -> None:
    """Reject a declared catalog path that resolves outside its typed owner."""

    try:
        resolved_root = Path(owner_root).resolve(strict=True)
        resolved_path = Path(path).resolve(strict=False)
        resolved_path.relative_to(resolved_root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise SubstrateRegistryError("substrate_source_path_outside_repo_root", str(path)) from exc


def _file_artifact_ref(
    path: Path, *, kind: str, payload: bytes | None = None
) -> tuple[ArtifactRef, epoch_contract.Digest]:
    raw = path.read_bytes() if payload is None else payload
    digest = f"sha256:{hashlib.sha256(raw).hexdigest()}"
    return (
        ArtifactRef(
            artifact_id=ArtifactID.model_validate(digest),
            kind=kind,
            media_type="application/json",
        ),
        digest,
    )


def load_l5_catalog_authority(
    paths: SubstrateCatalogPaths,
    *,
    repo_root: Path,
    source_owner_root: Path | None = None,
) -> L5CatalogAuthority:
    """Load L5 data metadata and code-owned epoch registries from their roots."""

    try:
        repo_root = Path(repo_root).resolve(strict=True)
        data_root = (
            Path(source_owner_root).resolve(strict=True)
            if source_owner_root is not None
            else repo_root
        )
    except (OSError, RuntimeError) as exc:
        raise SubstrateRegistryError("substrate_source_repo_root_unavailable") from exc
    if not repo_root.is_dir():
        raise SubstrateRegistryError("substrate_source_repo_root_not_directory")
    if not data_root.is_dir():
        raise SubstrateRegistryError("substrate_source_owner_root_not_directory")
    epoch_regime_path = paths.epoch_schema_regime_registry_path
    epoch_scope_path = paths.epoch_schema_regime_scope_registry_path
    if epoch_regime_path is None or epoch_scope_path is None:
        raise SubstrateRegistryError("l5_epoch_registry_paths_not_established")
    for source_path in (
        paths.root_manifest_path,
        paths.measurement_registry_path,
        paths.identification_mode_registry_path,
        paths.schema_regime_registry_path,
    ):
        _repo_relative_path(source_path, repo_root=data_root)
    for source_path in (epoch_regime_path, epoch_scope_path):
        _repo_relative_path(source_path, repo_root=repo_root)
    if source_owner_root is not None:
        _load_json(paths.root_manifest_path, strict_object=True)
    measurement = _load_json(paths.measurement_registry_path)
    identification = _load_json(paths.identification_mode_registry_path)
    schema_regime = _load_json(paths.schema_regime_registry_path)
    epoch_regime, epoch_regime_source_bytes = _load_json_source_bytes(epoch_regime_path)
    epoch_scope, epoch_scope_source_bytes = _load_json_source_bytes(epoch_scope_path)
    measurement_ref = _repo_ref(
        paths.measurement_registry_path,
        marker="measurement_registry",
        repo_root=data_root,
    )
    identification_ref = _repo_ref(
        paths.identification_mode_registry_path,
        marker="identification_mode_registry",
        repo_root=data_root,
    )
    schema_ref = _repo_ref(
        paths.schema_regime_registry_path,
        marker="schema_regime_registry",
        repo_root=data_root,
    )
    trust_tiers = {
        str(tier_id): SubstrateTrustTier(
            tier=str(row.get("tier") or tier_id),
            trust_cap=float(row.get("trust_cap")),
            trust_multiplier=float(row.get("trust_multiplier")),
            min_coverage=_optional_float(row.get("min_coverage")),
            max_coverage=_optional_float(row.get("max_coverage")),
            authority_ref=f"{measurement_ref}#/trust_tiers/{tier_id}",
        )
        for tier_id, row in _mapping(measurement.get("trust_tiers")).items()
    }
    dynamic_regime_rows = _mapping(schema_regime.get("regimes"))
    static_regime_rows = _mapping(epoch_regime.get("regimes"))
    duplicate_regime_ids = set(dynamic_regime_rows).intersection(static_regime_rows)
    for regime_id in duplicate_regime_ids:
        if dict(dynamic_regime_rows[regime_id]) != dict(static_regime_rows[regime_id]):
            raise SubstrateRegistryError(
                "l5_schema_regime_owner_sources_disagree",
                str(regime_id),
            )
    complete_regime_rows = {**dynamic_regime_rows, **static_regime_rows}
    regimes = {
        str(regime_id): SubstrateSchemaRegime(
            schema_regime_id=str(row.get("schema_regime_id") or regime_id),
            authority_ref=f"{schema_ref}#/regimes/{regime_id}",
            effective_start=_optional_str(row.get("effective_start")),
            effective_end=_optional_str(row.get("effective_end")),
            boundary_buffer_periods=_optional_int(row.get("boundary_buffer_periods")),
            source_version=_optional_str(row.get("source_version")),
        )
        for regime_id, row in complete_regime_rows.items()
    }
    relations = tuple(
        epoch_contract.L5SchemaRegimeScopeRelation.model_validate(row)
        for row in epoch_scope.get("relations", ())
        if isinstance(row, Mapping)
    )
    epoch_regime_ref, epoch_regime_hash = _file_artifact_ref(
        epoch_regime_path,
        kind="l5.schema_regime_registry",
        payload=epoch_regime_source_bytes,
    )
    epoch_scope_ref, epoch_scope_hash = _file_artifact_ref(
        epoch_scope_path,
        kind="l5.schema_regime_scope_registry",
        payload=epoch_scope_source_bytes,
    )
    return L5CatalogAuthority(
        measurement_registry_ref=measurement_ref,
        identification_mode_registry_ref=identification_ref,
        schema_regime_registry_ref=schema_ref,
        coverage_rules={
            str(family_id): float(value)
            for family_id, value in _mapping(measurement.get("coverage_rules")).items()
        },
        trust_tiers=trust_tiers,
        proxy_mappings={
            str(family_id): dict(row)
            for family_id, row in _mapping(measurement.get("proxy_mappings")).items()
            if isinstance(row, Mapping)
        },
        identification_modes={
            str(family_id): str(row.get("selected_mode") or row.get("primary_mode") or "")
            for family_id, row in _mapping(identification).items()
            if isinstance(row, Mapping)
        },
        schema_regimes=regimes,
        schema_regime_rows={str(key): dict(value) for key, value in complete_regime_rows.items()},
        schema_regime_scope_relations=relations,
        schema_regime_changepoints=tuple(
            dict(row) for row in epoch_regime.get("changepoints", ()) if isinstance(row, Mapping)
        ),
        epoch_schema_regime_registry_ref=epoch_regime_ref,
        epoch_schema_regime_registry_content_hash=epoch_regime_hash,
        epoch_schema_regime_scope_registry_ref=epoch_scope_ref,
        epoch_schema_regime_scope_registry_content_hash=epoch_scope_hash,
        epoch_schema_regime_registry_source_bytes=epoch_regime_source_bytes,
        epoch_schema_regime_scope_registry_source_bytes=epoch_scope_source_bytes,
    )


def build_substrate_registry_from_existing_catalogs(
    repo_root: Path,
    *,
    source_owner_root: Path | None = None,
    l5_receipt_projections: Sequence[
        tuple[
            epoch_contract.L5SchemaRegimeDenominatorReceipt,
            epoch_contract.ScopedSchemaRegimeProjection,
        ]
    ]
    | None = None,
) -> SubstrateRegistry:
    """Lift the current production-data substrate metadata from L5 and L1 catalogs."""

    repo_root = Path(repo_root).resolve()
    active_source = current_catalog_serving_source()
    if source_owner_root is None and active_source is not None:
        if active_source.repo_root != repo_root:
            raise SubstrateRegistryError("catalog_source_repo_root_mismatch")
        source_owner_root = active_source.source_owner_root
    data_root = Path(source_owner_root).resolve() if source_owner_root is not None else repo_root
    paths = default_substrate_catalog_paths(
        repo_root,
        source_owner_root=data_root if source_owner_root is not None else None,
    )
    for required in (
        paths.root_manifest_path,
        paths.measurement_registry_path,
        paths.identification_mode_registry_path,
        paths.schema_regime_registry_path,
        paths.l1_dcat_path,
    ):
        if not required.exists():
            raise SubstrateRegistryError("substrate_catalog_missing", required.as_posix())
    l5 = load_l5_catalog_authority(
        paths,
        repo_root=repo_root,
        source_owner_root=data_root if source_owner_root is not None else None,
    )
    root_manifest = _load_json(
        paths.root_manifest_path,
        strict_object=source_owner_root is not None,
    )
    receipt_projections = tuple(l5_receipt_projections or ())
    if not receipt_projections:
        receipt_projections = tuple(
            resolve_l5_schema_regime_projection(
                l5,
                scope_identity_ref=scope_identity_ref,
                valid_effect_value=date.max,
                authority_purpose="substrate_inventory",
            )
            for scope_identity_ref in l5_owner_scope_identity_refs(l5)
        )
    l5_entries_by_key: dict[tuple[str, str, SubstrateLayer], SubstrateRegistryEntry] = {}
    for receipt, projection in receipt_projections:
        for entry in _entries_from_l5(l5, receipt=receipt, projection=projection):
            l5_entries_by_key[entry.registry_key] = entry
    entries = [
        *l5_entries_by_key.values(),
        *_entries_from_l1_dcat(
            paths.l1_dcat_path,
            repo_root=data_root,
            root_manifest=root_manifest,
            l5=l5,
        ),
        *_entries_from_root_manifest(
            data_root,
            root_manifest,
            root_manifest_path=paths.root_manifest_path,
            l5=l5,
        ),
        *_entries_from_l2_l3_knowledge_substrates(data_root, l5=l5),
        *_entries_from_l6_agent_sim_control_artifacts(
            data_root,
            root_manifest,
            root_manifest_path=paths.root_manifest_path,
            l5=l5,
        ),
    ]
    knowledge_source_refs = _knowledge_substrate_refs(data_root)
    l6_source_refs = _l6_agent_sim_control_refs(
        repo_root,
        root_manifest,
        root_manifest_path=paths.root_manifest_path,
        source_owner_root=data_root if source_owner_root is not None else None,
    )
    selected_content_refs = (
        (_catalog_content_ref(active_source),)
        if active_source is not None
        and active_source.selection_basis == "explicit_path_candidate_only"
        else ()
    )
    return build_substrate_registry(
        entries,
        producer_ref="polisyos.runtime.quality.substrate_registry.build_substrate_registry_from_existing_catalogs",
        source_catalog_refs=(
            _repo_ref(
                paths.root_manifest_path,
                marker="production_data_root_manifest",
                repo_root=data_root,
            ),
            l5.measurement_registry_ref,
            l5.identification_mode_registry_ref,
            l5.schema_regime_registry_ref,
            str(l5.epoch_schema_regime_registry_ref.artifact_id),
            str(l5.epoch_schema_regime_scope_registry_ref.artifact_id),
            _repo_ref(
                paths.l1_dcat_path,
                marker="dataset_catalog.duckdb",
                repo_root=data_root,
            ),
            *knowledge_source_refs,
            *l6_source_refs,
            *selected_content_refs,
        ),
    )


def build_substrate_registry(
    entries: Iterable[SubstrateRegistryEntry],
    *,
    producer_ref: str,
    source_catalog_refs: Sequence[str],
) -> SubstrateRegistry:
    """Build a content-addressed registry version from entries."""

    sorted_entries = tuple(
        sorted(
            entries,
            key=lambda entry: (entry.layer.value, entry.source_id, entry.family_id),
        )
    )
    fields = {
        "schema_version": SUBSTRATE_REGISTRY_SCHEMA_VERSION,
        "producer_ref": producer_ref,
        "source_catalog_refs": tuple(source_catalog_refs),
        "entries": sorted_entries,
    }
    content_hash = gy_content_hash(_registry_content_payload_from_fields(fields))
    return SubstrateRegistry(
        substrate_version_id=f"substrate_version_{content_hash.removeprefix('sha256:')[:16]}",
        content_hash=content_hash,
        **fields,
    )


def build_substrate_registry_entry(
    registration: SubstrateRegistration,
) -> SubstrateRegistryEntry:
    """Content-address a generic substrate registration."""

    fields = registration.model_dump(mode="python")
    content_hash = gy_content_hash(_entry_content_payload_from_fields(fields))
    return SubstrateRegistryEntry(entry_content_hash=content_hash, **fields)


def register_substrate_entry(
    registry: SubstrateRegistry,
    registration: SubstrateRegistration,
    *,
    l5_authority: L5CatalogAuthority | None = None,
    producer_ref: str = "polisyos.runtime.quality.substrate_registry.register_substrate_entry",
) -> SubstrateRegistry:
    """Return a new registry version with one generic registration applied.

    The interface is data-driven: callers supply the source/family metadata.
    Existing entries with the same source/family/layer key are replaced; new
    sources require no code or enum change.
    """

    if l5_authority is not None:
        l5_authority.validate_registration(registration)
    entry = build_substrate_registry_entry(registration)
    entries_by_key = {existing.registry_key: existing for existing in registry.entries}
    entries_by_key[entry.registry_key] = entry
    source_catalog_refs = tuple(
        dict.fromkeys((*registry.source_catalog_refs, *entry.authority_refs))
    )
    return build_substrate_registry(
        entries_by_key.values(),
        producer_ref=producer_ref,
        source_catalog_refs=source_catalog_refs,
    )


def persist_measurement_root_substrate_registry(
    store: CoreJSONArtifactStore,
    *,
    baseline_registry: SubstrateRegistry,
    registration: SubstrateRegistration,
    l5_authority: L5CatalogAuthority,
    evidence: ResolvedMeasurementRootEvidence,
    baseline_registry_ref: ArtifactRef | None = None,
    execution_scope_binding: MeasurementRootExecutionBinding | None = None,
) -> MeasurementRootRegistryAdmission:
    """Admit one owner registration from replay-verified root evidence.

    The public seam accepts only the typed evidence object emitted by the
    measurement-root resolver.  Raw refs are deliberately not an admission
    API: accepting them would turn a shape-only lineage claim into a custody
    claim.  The resolver's content-bound projection and deterministic evidence
    fingerprint are rechecked before the private persistence helper is reached.
    """

    from polisyos.runtime.quality.data_forge_binding import (
        ResolvedMeasurementRootEvidence,
        _validate_resolved_measurement_root_evidence,
    )

    if not isinstance(evidence, ResolvedMeasurementRootEvidence):
        raise SubstrateRegistryError("substrate_registry_measurement_root_evidence_invalid")
    try:
        _validate_resolved_measurement_root_evidence(
            evidence,
            store=store,
            execution_scope_binding=execution_scope_binding,
        )
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        raise SubstrateRegistryError(
            "substrate_registry_measurement_root_evidence_invalid"
        ) from exc
    return _persist_measurement_root_substrate_registry(
        store,
        baseline_registry=baseline_registry,
        registration=registration,
        l5_authority=l5_authority,
        measurement_root_ref=evidence.measurement_root_ref,
        fetch_receipt_ref=evidence.fetch_receipt_ref,
        catalog_binding_ref=evidence.catalog_binding_ref,
        baseline_registry_ref=baseline_registry_ref,
    )


def _persist_measurement_root_substrate_registry(
    store: CoreJSONArtifactStore,
    *,
    baseline_registry: SubstrateRegistry,
    registration: SubstrateRegistration,
    l5_authority: L5CatalogAuthority,
    measurement_root_ref: ArtifactRef,
    fetch_receipt_ref: ArtifactRef,
    catalog_binding_ref: ArtifactRef,
    baseline_registry_ref: ArtifactRef | None = None,
) -> MeasurementRootRegistryAdmission:
    """Persist refs after the public resolver seam has verified their custody."""

    _validate_measurement_root_registry_inputs(
        measurement_root_ref=measurement_root_ref,
        fetch_receipt_ref=fetch_receipt_ref,
        catalog_binding_ref=catalog_binding_ref,
        baseline_registry_ref=baseline_registry_ref,
    )
    _validate_owner_registration(registration)
    if baseline_registry_ref is not None:
        persisted_baseline = load_substrate_registry(store, baseline_registry_ref)
        if persisted_baseline != baseline_registry:
            raise SubstrateRegistryError("substrate_registry_baseline_mismatch")

    # This is the sole authority check for the registration.  In particular,
    # the MeasurementRoot is never used to select or inflate any registration
    # property.
    updated = register_substrate_entry(
        baseline_registry,
        registration,
        l5_authority=l5_authority,
        producer_ref=(
            "polisyos.runtime.quality.substrate_registry."
            "persist_measurement_root_substrate_registry"
        ),
    )
    input_refs = _measurement_root_registry_input_refs(
        measurement_root_ref=measurement_root_ref,
        fetch_receipt_ref=fetch_receipt_ref,
        catalog_binding_ref=catalog_binding_ref,
        baseline_registry_ref=baseline_registry_ref,
    )
    registry_ref = ArtifactRef.model_validate(
        persist_substrate_registry(store, updated, inputs=input_refs)
    )
    loaded = load_substrate_registry(
        store,
        registry_ref,
        expected_inputs=input_refs,
    )
    return MeasurementRootRegistryAdmission(
        registry=loaded,
        registry_ref=registry_ref,
        input_refs=input_refs,
        measurement_root_ref=measurement_root_ref,
        fetch_receipt_ref=fetch_receipt_ref,
        catalog_binding_ref=catalog_binding_ref,
        baseline_registry_ref=baseline_registry_ref,
    )


def _validate_measurement_root_registry_inputs(
    *,
    measurement_root_ref: ArtifactRef,
    fetch_receipt_ref: ArtifactRef,
    catalog_binding_ref: ArtifactRef,
    baseline_registry_ref: ArtifactRef | None,
) -> None:
    """Validate immutable CAS reference kinds before building a registry."""

    refs = (
        (
            measurement_root_ref,
            "measurement_root",
            "policyos.gy.measurement_root_payload",
        ),
        (fetch_receipt_ref, "fabric_fetch", "fabric.fetch_receipt"),
        (catalog_binding_ref, "catalog_binding", "fabric.catalog_fetch_binding"),
    )
    if baseline_registry_ref is not None:
        refs += (
            (
                baseline_registry_ref,
                "baseline_substrate_registry",
                SUBSTRATE_REGISTRY_ARTIFACT_KIND,
            ),
        )
    seen: set[str] = set()
    for ref, role, expected_kind in refs:
        if not isinstance(ref, ArtifactRef):
            raise SubstrateRegistryError(f"substrate_registry_{role}_ref_invalid")
        artifact_id = str(ref.artifact_id)
        if not artifact_id.startswith("sha256:") or artifact_id in seen:
            raise SubstrateRegistryError(f"substrate_registry_{role}_ref_invalid")
        if ref.kind != expected_kind:
            raise SubstrateRegistryError(f"substrate_registry_{role}_kind_invalid")
        seen.add(artifact_id)


def _validate_owner_registration(registration: SubstrateRegistration) -> None:
    """Reject owner responses that omit the provenance needed for admission."""

    if not isinstance(registration, SubstrateRegistration):
        raise SubstrateRegistryError("substrate_registration_incomplete")
    if any(not isinstance(ref, str) or not ref.strip() for ref in registration.provenance_refs):
        raise SubstrateRegistryError("substrate_registration_provenance_missing")
    if any(not isinstance(ref, str) or not ref.strip() for ref in registration.authority_refs):
        raise SubstrateRegistryError("substrate_registration_authority_missing")
    if not registration.provenance_refs or not registration.authority_refs:
        raise SubstrateRegistryError("substrate_registration_incomplete")


def _measurement_root_registry_input_refs(
    *,
    measurement_root_ref: ArtifactRef,
    fetch_receipt_ref: ArtifactRef,
    catalog_binding_ref: ArtifactRef,
    baseline_registry_ref: ArtifactRef | None,
) -> tuple[core.artifacts.InputRef, ...]:
    refs = [
        core.artifacts.InputRef(
            artifact_id=measurement_root_ref.artifact_id,
            role="measurement_root",
            manifest_profile_sha256=measurement_root_ref.manifest_profile_sha256,
        ),
        core.artifacts.InputRef(
            artifact_id=fetch_receipt_ref.artifact_id,
            role="fabric_fetch",
        ),
        core.artifacts.InputRef(
            artifact_id=catalog_binding_ref.artifact_id,
            role="catalog_binding",
        ),
    ]
    if baseline_registry_ref is not None:
        refs.append(
            core.artifacts.InputRef(
                artifact_id=baseline_registry_ref.artifact_id,
                role="baseline_substrate_registry",
            )
        )
    return tuple(refs)


def persist_substrate_registry(
    store: ArtifactStore,
    registry: SubstrateRegistry,
    *,
    inputs: Sequence[object] | None = None,
) -> ArtifactRef:
    """Persist a substrate registry as a typed CAS artifact."""

    artifacts = core.artifacts
    canon = core.canon
    validated = SubstrateRegistry.model_validate(registry.model_dump(mode="json"))
    selected_ref = store.put_json(
        validated,
        artifacts.PutOptions(
            kind=SUBSTRATE_REGISTRY_ARTIFACT_KIND,
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name=SUBSTRATE_REGISTRY_SCHEMA_NAME,
                version=validated.schema_version,
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=canon.CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    if (
        not isinstance(selected_ref, artifacts.ArtifactRef)
        or selected_ref.manifest_profile_sha256 is None
    ):
        raise SubstrateRegistryError("substrate_registry_write_profile_not_selected")
    return selected_ref


def load_substrate_registry(
    store: CoreJSONArtifactStore,
    ref: ArtifactRef | ArtifactID | str,
    *,
    expected_inputs: Sequence[object] | None = None,
) -> SubstrateRegistry:
    """Load a persisted registry, optionally checking its direct lineage."""

    artifacts = core.artifacts
    if isinstance(ref, artifacts.ArtifactRef | artifacts.ArtifactID):
        read_ref = ref
    else:
        read_ref = ArtifactID.model_validate(ref)
    if not isinstance(read_ref, artifacts.ArtifactRef) or read_ref.manifest_profile_sha256 is None:
        raise SubstrateRegistryError("substrate_registry_profile_selector_missing")
    if (
        read_ref.kind != SUBSTRATE_REGISTRY_ARTIFACT_KIND
        or read_ref.media_type != "application/json"
    ):
        raise SubstrateRegistryError("substrate_registry_ref_kind_invalid")
    try:
        loaded = artifacts.validate_core_model_json_artifact(SubstrateRegistry, store, read_ref)
    except Exception as exc:
        code = getattr(exc, "code", "substrate_registry_profile_or_content_invalid")
        raise SubstrateRegistryError(str(code), str(exc)) from exc
    manifest = store.get_manifest(read_ref)
    if (
        manifest.kind != SUBSTRATE_REGISTRY_ARTIFACT_KIND
        or manifest.media_type != "application/json"
        or manifest.artifact_schema
        != artifacts.SchemaInfo(
            name=SUBSTRATE_REGISTRY_SCHEMA_NAME,
            version=SUBSTRATE_REGISTRY_SCHEMA_VERSION,
        )
    ):
        raise SubstrateRegistryError("substrate_registry_manifest_invalid")
    if expected_inputs is not None:
        actual_inputs = tuple(manifest.inputs)
        expected = tuple(
            input_ref
            if isinstance(input_ref, artifacts.InputRef)
            else artifacts.InputRef.model_validate(input_ref)
            for input_ref in expected_inputs
        )
        if actual_inputs != expected:
            raise SubstrateRegistryError("substrate_registry_manifest_inputs_mismatch")
    return loaded


def substrate_entry_content_hash(entry: SubstrateRegistryEntry) -> str:
    """Return the time/location-invariant content hash for an entry."""

    return gy_content_hash(_entry_content_payload_from_record(entry))


def substrate_registry_content_hash(registry: SubstrateRegistry) -> str:
    """Return the time/location-invariant content hash for a registry."""

    return gy_content_hash(_registry_content_payload_from_record(registry))


def _entries_from_l5(
    l5: L5CatalogAuthority,
    *,
    receipt: epoch_contract.L5SchemaRegimeDenominatorReceipt,
    projection: epoch_contract.ScopedSchemaRegimeProjection,
) -> tuple[SubstrateRegistryEntry, ...]:
    entries: list[SubstrateRegistryEntry] = []
    if (
        l5.resolve_schema_regime_denominator(query=receipt.query) != receipt
        or l5.project_scoped_schema_regimes(receipt=receipt) != projection
    ):
        raise SubstrateRegistryError("l5_scoped_schema_regime_evidence_mismatch")
    if projection.status != "resolved" or not projection.applicable_regime_ids:
        raise SubstrateRegistryError("l5_scoped_schema_regime_projection_unresolved")
    for regime_id, observed_hash in zip(
        projection.applicable_regime_ids,
        projection.applicable_regime_content_hashes,
        strict=True,
    ):
        schema_regime = l5.schema_regimes.get(regime_id)
        if schema_regime is None:
            raise SubstrateRegistryError("l5_scoped_schema_regime_unknown", regime_id)
        regime_bytes = epoch_contract.canonical_epoch_bytes(dict(l5.schema_regime_rows[regime_id]))
        expected_hash = f"sha256:{hashlib.sha256(regime_bytes).hexdigest()}"
        if observed_hash != expected_hash:
            raise SubstrateRegistryError("l5_scoped_schema_regime_content_hash_mismatch", regime_id)
        for family_id, coverage_score in sorted(l5.coverage_rules.items()):
            identification_mode = l5.identification_modes.get(family_id, "unknown")
            proxy = l5.proxy_mappings.get(family_id)
            source_id = str(proxy.get("proxy_source_id")) if proxy else "l5_measurement_registry"
            registration = SubstrateRegistration(
                source_id=f"{source_id}:{regime_id}",
                family_id=family_id,
                layer=SubstrateLayer.L5,
                coverage=SubstrateCoverage(
                    coverage_score=float(coverage_score),
                    coverage_kind="l5.measurement_registry.coverage_rules",
                    coverage_rule_ref=(
                        f"{l5.measurement_registry_ref}#/coverage_rules/{family_id}"
                    ),
                    coverage_dimensions={"proxy_mapping": proxy or {}},
                ),
                trust_tier=l5.expected_trust_tier(family_id),
                identification_mode=identification_mode,
                schema_regime=schema_regime,
                data_version="l5-calibration-d2",
                snapshot_id=f"l5-scoped:{projection.projection_content_hash}",
                source_snapshot_id=str(projection.owner_source_snapshot_ref.artifact_id),
                provenance_refs=(
                    f"{l5.measurement_registry_ref}#/coverage_rules/{family_id}",
                    f"{l5.identification_mode_registry_ref}#/{family_id}",
                    schema_regime.authority_ref,
                    str(projection.owner_source_snapshot_ref.artifact_id),
                    str(projection.denominator_receipt_ref.artifact_id),
                    projection.projection_content_hash,
                ),
                authority_refs=(
                    l5.measurement_registry_ref,
                    l5.identification_mode_registry_ref,
                    l5.schema_regime_registry_ref,
                    str(l5.epoch_schema_regime_registry_ref.artifact_id),
                    str(l5.epoch_schema_regime_scope_registry_ref.artifact_id),
                ),
            )
            entries.append(build_substrate_registry_entry(registration))
    return tuple(entries)


def _entries_from_l1_dcat(
    dcat_path: Path,
    *,
    repo_root: Path,
    root_manifest: Mapping[str, Any],
    l5: L5CatalogAuthority,
) -> tuple[SubstrateRegistryEntry, ...]:
    import duckdb

    dataset_bundle = _bundle(root_manifest, "datasets")
    source_statuses = _mapping(
        _mapping(dataset_bundle.get("extra")).get("blocking_source_statuses")
    )
    source_publish_blocking = _mapping(
        _mapping(dataset_bundle.get("extra")).get("source_publish_blocking")
    )
    dcat_ref = _repo_ref(dcat_path, marker="ds_datasets", repo_root=repo_root)
    con = duckdb.connect(str(dcat_path), read_only=True)
    try:
        rows = con.execute(
            """
            SELECT
                source,
                count(*) AS dataset_count,
                avg(quality_execution_readiness_score) AS avg_execution_readiness,
                min(quality_execution_readiness_score) AS min_execution_readiness,
                max(quality_execution_readiness_score) AS max_execution_readiness,
                avg(quality_description_score) AS avg_description_score,
                avg(quality_machine_readable_score) AS avg_machine_readable_score,
                avg(quality_parser_support_score) AS avg_parser_support_score,
                avg(quality_freshness_score) AS avg_freshness_score
            FROM ds_datasets
            WHERE source IS NOT NULL AND source <> ''
            GROUP BY source
            ORDER BY source
            """
        ).fetchall()
        metric_rows = dict(
            con.execute(
                """
                SELECT source, count(*) AS metric_binding_count
                FROM ds_metric_bindings
                WHERE source IS NOT NULL AND source <> ''
                GROUP BY source
                """
            ).fetchall()
        )
    finally:
        con.close()
    entries: list[SubstrateRegistryEntry] = []
    for row in rows:
        (
            source,
            dataset_count,
            avg_execution_readiness,
            min_execution_readiness,
            max_execution_readiness,
            avg_description_score,
            avg_machine_readable_score,
            avg_parser_support_score,
            avg_freshness_score,
        ) = row
        source_id = f"l1_dcat:{source}"
        quality_scores = {
            "avg_execution_readiness": float(avg_execution_readiness or 0.0),
            "min_execution_readiness": float(min_execution_readiness or 0.0),
            "max_execution_readiness": float(max_execution_readiness or 0.0),
            "avg_description_score": float(avg_description_score or 0.0),
            "avg_machine_readable_score": float(avg_machine_readable_score or 0.0),
            "avg_parser_support_score": float(avg_parser_support_score or 0.0),
            "avg_freshness_score": float(avg_freshness_score or 0.0),
        }
        conservative_score = min(
            quality_scores["min_execution_readiness"],
            quality_scores["avg_execution_readiness"],
        )
        if source_publish_blocking.get(str(source)) is True:
            conservative_score = min(
                conservative_score,
                l5.minimum_positive_coverage_floor(default=0.5),
            )
        registration = SubstrateRegistration(
            source_id=source_id,
            family_id=f"dcat_source:{source}",
            layer=SubstrateLayer.L1,
            coverage=SubstrateCoverage(
                coverage_score=conservative_score,
                coverage_kind="l1.dcat.quality_execution_readiness_conservative",
                coverage_rule_ref=f"{dcat_ref}#/ds_datasets/source/{source}",
                dataset_count=int(dataset_count or 0),
                metric_binding_count=int(metric_rows.get(source) or 0),
                quality_scores=quality_scores,
                coverage_dimensions={
                    "source_publish_blocking": bool(source_publish_blocking.get(str(source))),
                    "blocking_source_status": source_statuses.get(str(source)),
                },
            ),
            trust_tier=l5.trust_tier_for_score(conservative_score),
            identification_mode="catalog_metadata_only",
            schema_regime=SubstrateSchemaRegime(
                schema_regime_id="dcat:ds_datasets.v1",
                authority_ref=f"{dcat_ref}#/schema/ds_datasets",
                source_version=str(dataset_bundle.get("version_id") or "unknown"),
            ),
            data_version=str(dataset_bundle.get("version_id") or "datasets"),
            snapshot_id=str(dataset_bundle.get("version_id") or "datasets"),
            source_snapshot_id=str(dataset_bundle.get("version_id") or "datasets"),
            provenance_refs=(
                f"{dcat_ref}#/ds_datasets/source/{source}",
                f"{dcat_ref}#/ds_metric_bindings/source/{source}",
            ),
            authority_refs=(dcat_ref, l5.measurement_registry_ref),
        )
        entries.append(build_substrate_registry_entry(registration))
    return tuple(entries)


def _entries_from_l2_l3_knowledge_substrates(
    repo_root: Path,
    *,
    l5: L5CatalogAuthority,
) -> tuple[SubstrateRegistryEntry, ...]:
    specs = (
        {
            "path": repo_root / DEFAULT_L2_SCHOLAR_KG_PATH,
            "source_id": "l2_scholar_kg:scholar_knowledge.duckdb",
            "family_id": "l2_scholar_kg_causal_priors_transport",
            "layer": SubstrateLayer.L2,
            "tables": (
                "ac_parameter_estimates",
                "ac_causal_claims",
                "ac_skg_edges",
                "ac_skg_transport_scores",
                "ac_skg_contested_edges",
                "ac_claim_adjudications",
                "ac_skg_variables",
                "ac_context_attributes",
                "ac_simulation_parameters",
                "ac_boundary_conditions",
            ),
            "version_sql": "SELECT MAX(version_id) FROM ac_skg_versions",
            "identification_mode": "credal_interval_prior",
            "schema_regime_id": "manifest:l2_scholar_kg.duckdb.v1",
            "coverage_kind": "l2.duckdb.real_store.table_coverage",
        },
        {
            "path": repo_root / DEFAULT_L3_LEX_KG_PATH,
            "source_id": "l3_lex_kg:lex_knowledge_graph.duckdb",
            "family_id": "l3_lex_kg_admissibility_obligations",
            "layer": SubstrateLayer.L3,
            "tables": (
                "lex_provisions",
                "lex_normative_ready_facts",
                "lex_rule_thresholds",
                "lex_rule_clauses",
                "lex_amendments",
                "lex_entities",
                "lex_doc_domains",
                "lex_temporal_audit",
            ),
            "version_sql": "SELECT MAX(effective_from) FROM lex_amendments",
            "identification_mode": "normative_admissibility_authority",
            "schema_regime_id": "manifest:l3_lex_kg.duckdb.v1",
            "coverage_kind": "l3.duckdb.real_store.table_coverage",
        },
    )
    entries: list[SubstrateRegistryEntry] = []
    for spec in specs:
        path = spec["path"]
        if not isinstance(path, Path) or not path.exists():
            continue
        duckdb_ref = _repo_ref(path, marker="duckdb", repo_root=repo_root)
        coverage_ref = _repo_ref(path, marker="table_counts", repo_root=repo_root)
        schema_ref = _repo_ref(path, marker="duckdb_schema", repo_root=repo_root)
        con = duckdb.connect(str(path), read_only=True)
        try:
            table_counts = _duckdb_table_counts(con, spec["tables"])
            raw_version = con.execute(str(spec["version_sql"])).fetchone()[0]
        finally:
            con.close()
        present_tables = sum(1 for count in table_counts.values() if count > 0)
        required_tables = len(table_counts)
        coverage_score = round(present_tables / max(required_tables, 1), 6)
        data_version = str(raw_version or path.parent.name)
        snapshot_payload = {
            "path": duckdb_ref,
            "data_version": data_version,
            "table_counts": table_counts,
        }
        snapshot_id = f"{spec['family_id']}:{gy_content_hash(snapshot_payload)}"
        schema_regime = SubstrateSchemaRegime(
            schema_regime_id=str(spec["schema_regime_id"]),
            authority_ref=schema_ref,
            source_version=data_version,
        )
        registration = SubstrateRegistration(
            source_id=str(spec["source_id"]),
            family_id=str(spec["family_id"]),
            layer=SubstrateLayer(spec["layer"]),
            coverage=SubstrateCoverage(
                coverage_score=coverage_score,
                coverage_kind=str(spec["coverage_kind"]),
                coverage_rule_ref=coverage_ref,
                dataset_count=1,
                metric_binding_count=present_tables,
                observation_count=sum(table_counts.values()),
                coverage_dimensions={
                    "required_tables": list(spec["tables"]),
                    "present_table_count": present_tables,
                    "required_table_count": required_tables,
                    "table_counts": table_counts,
                },
            ),
            trust_tier=l5.trust_tier_for_score(coverage_score),
            identification_mode=str(spec["identification_mode"]),
            schema_regime=schema_regime,
            data_version=data_version,
            snapshot_id=snapshot_id,
            source_snapshot_id=snapshot_id,
            provenance_refs=(coverage_ref, schema_ref),
            authority_refs=(
                coverage_ref,
                l5.measurement_registry_ref,
            ),
        )
        entries.append(build_substrate_registry_entry(registration))
    return tuple(entries)


def _duckdb_table_counts(
    connection: duckdb.DuckDBPyConnection,
    table_names: Sequence[str],
) -> dict[str, int]:
    existing = {
        str(row[0])
        for row in connection.execute("SELECT table_name FROM information_schema.tables").fetchall()
    }
    counts: dict[str, int] = {}
    for table_name in table_names:
        name = str(table_name)
        if name not in existing:
            counts[name] = 0
            continue
        row = connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()  # noqa: S608
        counts[name] = int(row[0] or 0)
    return counts


def _knowledge_substrate_refs(repo_root: Path) -> tuple[str, ...]:
    refs: list[str] = []
    for path in (
        repo_root / DEFAULT_L2_SCHOLAR_KG_PATH,
        repo_root / DEFAULT_L3_LEX_KG_PATH,
    ):
        if path.exists():
            refs.append(_repo_ref(path, marker="duckdb", repo_root=repo_root))
    return tuple(refs)


def _entries_from_l6_agent_sim_control_artifacts(
    repo_root: Path,
    root_manifest: Mapping[str, Any],
    *,
    root_manifest_path: Path,
    l5: L5CatalogAuthority,
) -> tuple[SubstrateRegistryEntry, ...]:
    bundle = _mapping(_mapping(root_manifest.get("bundles")).get("ukraine_simulation"))
    bundle_path = _optional_str(bundle.get("path"))
    if not bundle_path:
        return ()
    root = repo_root / DEFAULT_PRODUCTION_DATA_ROOT / bundle_path / "production_bundle/bundles"
    specs = (
        {
            "path": root / "intervention_bundle_v1/intervention_knob_dictionary.json",
            "family_id": "l6_intervention_knob_dictionary",
            "source_id": "l6_agent_sim:intervention_knob_dictionary.json",
            "identification_mode": "intervention_lever_space",
            "coverage_kind": "l6.agent_sim.knob_dictionary.real_control_artifact",
        },
        {
            "path": root / "intervention_bundle_v1/lex_intervention_map.json",
            "family_id": "l6_lex_intervention_map",
            "source_id": "l6_agent_sim:lex_intervention_map.json",
            "identification_mode": "law_to_lever_route_candidate",
            "coverage_kind": "l6.agent_sim.lex_intervention_map.real_control_artifact",
        },
        {
            "path": root / "method_contract_bundle_v1/observation_to_contract_manifest.json",
            "family_id": "l6_observation_contract_routes",
            "source_id": "l6_agent_sim:observation_to_contract_manifest.json",
            "identification_mode": "value_method_route",
            "coverage_kind": "l6.agent_sim.observation_contract_manifest.real_control_artifact",
        },
        {
            "path": root / "intervention_bundle_v1/policy_scenario_templates.json",
            "family_id": "l6_policy_scenario_templates",
            "source_id": "l6_agent_sim:policy_scenario_templates.json",
            "identification_mode": "scenario_template_catalog_deferred",
            "coverage_kind": "l6.agent_sim.policy_scenario_templates.real_control_artifact",
        },
    )
    entries: list[SubstrateRegistryEntry] = []
    root_ref = f"{_repo_uri(root_manifest_path, repo_root=repo_root)}#/bundles/ukraine_simulation"
    for spec in specs:
        path = spec["path"]
        if not isinstance(path, Path) or not path.exists():
            continue
        family_id = str(spec["family_id"])
        artifact_ref = _repo_ref(
            path,
            marker=family_id.removeprefix("l6_"),
            repo_root=repo_root,
        )
        payload = _load_json(path)
        observation_count = _l6_payload_observation_count(payload)
        if observation_count <= 0:
            continue
        payload_hash = gy_content_hash(payload)
        registration = SubstrateRegistration(
            source_id=str(spec["source_id"]),
            family_id=family_id,
            layer=SubstrateLayer.L6,
            coverage=SubstrateCoverage(
                coverage_score=1.0,
                coverage_kind=str(spec["coverage_kind"]),
                coverage_rule_ref=artifact_ref,
                dataset_count=1,
                metric_binding_count=observation_count,
                observation_count=observation_count,
                coverage_dimensions={
                    "artifact_content_hash": payload_hash,
                    "artifact_keys": sorted(str(key) for key in payload),
                    "root_manifest_bundle": "ukraine_simulation",
                },
            ),
            trust_tier=l5.trust_tier_for_score(1.0),
            identification_mode=str(spec["identification_mode"]),
            schema_regime=SubstrateSchemaRegime(
                schema_regime_id=f"manifest:{family_id}.v1",
                authority_ref=artifact_ref,
                source_version=str(bundle.get("version_id") or "ukraine_simulation"),
            ),
            data_version=str(bundle.get("version_id") or "ukraine_simulation"),
            snapshot_id=f"{family_id}:{payload_hash}",
            source_snapshot_id=str(bundle.get("version_id") or "ukraine_simulation"),
            provenance_refs=(artifact_ref,),
            authority_refs=(root_ref, artifact_ref, l5.measurement_registry_ref),
        )
        entries.append(build_substrate_registry_entry(registration))
    return tuple(entries)


def _l6_agent_sim_control_refs(
    repo_root: Path,
    root_manifest: Mapping[str, Any],
    *,
    root_manifest_path: Path,
    source_owner_root: Path | None = None,
) -> tuple[str, ...]:
    data_root = Path(source_owner_root).resolve() if source_owner_root is not None else repo_root
    paths = default_substrate_catalog_paths(
        repo_root,
        source_owner_root=data_root if source_owner_root is not None else None,
    )
    return tuple(
        entry.provenance_refs[0]
        for entry in _entries_from_l6_agent_sim_control_artifacts(
            data_root,
            root_manifest,
            root_manifest_path=root_manifest_path,
            l5=load_l5_catalog_authority(
                paths,
                repo_root=repo_root,
                source_owner_root=data_root if source_owner_root is not None else None,
            ),
        )
    )


def _l6_payload_observation_count(payload: Mapping[str, Any]) -> int:
    routes = payload.get("routes")
    artifacts = payload.get("artifacts")
    if isinstance(routes, Sequence) and not isinstance(routes, str | bytes | bytearray):
        artifact_count = (
            len(artifacts)
            if isinstance(artifacts, Sequence)
            and not isinstance(artifacts, str | bytes | bytearray)
            else 0
        )
        return len(routes) + artifact_count
    return len(payload)


def _entries_from_root_manifest(
    repo_root: Path,
    root_manifest: Mapping[str, Any],
    *,
    root_manifest_path: Path,
    l5: L5CatalogAuthority,
) -> tuple[SubstrateRegistryEntry, ...]:
    entries: list[SubstrateRegistryEntry] = []
    bundles = _mapping(root_manifest.get("bundles"))
    root_ref = _repo_uri(root_manifest_path, repo_root=repo_root)
    for bundle_id, bundle in sorted(bundles.items()):
        if not isinstance(bundle, Mapping):
            continue
        layer = _layer_for_manifest_bundle(str(bundle_id), str(bundle.get("role") or ""))
        readiness = str(bundle.get("readiness") or "")
        coverage_score = _coverage_from_readiness(readiness)
        registration = SubstrateRegistration(
            source_id=f"production_data:{bundle_id}",
            family_id=str(bundle.get("role") or bundle_id),
            layer=layer,
            coverage=SubstrateCoverage(
                coverage_score=coverage_score,
                coverage_kind="production_data_root_manifest.readiness",
                coverage_rule_ref=f"{root_ref}#/bundles/{bundle_id}/readiness",
                coverage_dimensions={
                    "readiness": readiness,
                    "required_files": list(bundle.get("required_files") or []),
                },
            ),
            trust_tier=l5.trust_tier_for_score(coverage_score),
            identification_mode=_identification_mode_for_manifest_bundle(layer),
            schema_regime=SubstrateSchemaRegime(
                schema_regime_id=f"manifest:{bundle_id}",
                authority_ref=f"{root_ref}#/bundles/{bundle_id}",
                source_version=_optional_str(bundle.get("version_id")),
            ),
            data_version=str(bundle.get("version_id") or bundle_id),
            snapshot_id=str(bundle.get("version_id") or bundle_id),
            source_snapshot_id=str(bundle.get("version_id") or bundle_id),
            provenance_refs=(f"{root_ref}#/bundles/{bundle_id}",),
            authority_refs=(root_ref, l5.measurement_registry_ref),
        )
        entries.append(build_substrate_registry_entry(registration))
    return tuple(entries)


def _layer_for_manifest_bundle(bundle_id: str, role: str) -> SubstrateLayer:
    text = f"{bundle_id} {role}".casefold()
    if "dataset" in text or "dcat" in text:
        return SubstrateLayer.L1
    if "academic" in text or "scholar" in text:
        return SubstrateLayer.L2
    if "legal" in text or "lex" in text:
        return SubstrateLayer.L3
    if "calibration" in text:
        return SubstrateLayer.L5
    if "simulation" in text or "intervention" in text or "method" in text:
        return SubstrateLayer.L6
    return SubstrateLayer.L4


def _coverage_from_readiness(readiness: str) -> float:
    if readiness == "ready":
        return 1.0
    if readiness.startswith("ready_with_partial"):
        return 0.5
    if readiness:
        return 0.25
    return 0.0


def _identification_mode_for_manifest_bundle(layer: SubstrateLayer) -> str:
    if layer is SubstrateLayer.L2:
        return "scholarly_prior_not_direct_identification"
    if layer is SubstrateLayer.L3:
        return "normative_fact_not_causal_identification"
    if layer is SubstrateLayer.L6:
        return "intervention_or_method_route"
    return "manifest_registered"


def _bundle(root_manifest: Mapping[str, Any], bundle_id: str) -> Mapping[str, Any]:
    bundle = _mapping(root_manifest.get("bundles")).get(bundle_id)
    if not isinstance(bundle, Mapping):
        raise SubstrateRegistryError("production_data_bundle_missing", bundle_id)
    return bundle


def _entry_content_payload_from_record(entry: SubstrateRegistryEntry) -> dict[str, Any]:
    return _entry_content_payload_from_fields(entry.model_dump(mode="json"))


def _entry_content_payload_from_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    return {key: _json_ready(value) for key, value in fields.items() if key != "entry_content_hash"}


def _registry_content_payload_from_record(
    registry: SubstrateRegistry,
) -> dict[str, Any]:
    return _registry_content_payload_from_fields(registry.model_dump(mode="json"))


def _registry_content_payload_from_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    entries = fields.get("entries") or ()
    return {
        "schema_version": fields.get("schema_version"),
        "source_catalog_refs": tuple(fields.get("source_catalog_refs") or ()),
        "entries": [
            _entry_content_payload_from_fields(_entry_as_mapping(entry))
            for entry in sorted(
                entries,
                key=lambda item: (
                    str(_entry_as_mapping(item).get("layer")),
                    str(_entry_as_mapping(item).get("source_id")),
                    str(_entry_as_mapping(item).get("family_id")),
                ),
            )
        ],
    }


def _entry_as_mapping(entry: object) -> Mapping[str, Any]:
    if isinstance(entry, BaseModel):
        return entry.model_dump(mode="json")
    if isinstance(entry, Mapping):
        return entry
    raise TypeError(f"unsupported entry type: {type(entry)!r}")


def _json_ready(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_ready(item) for item in value]
    return value


def _load_json(path: Path, *, strict_object: bool = False) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        payload = (
            json.loads(
                raw,
                object_pairs_hook=_unique_json_object,
                parse_constant=_reject_json_constant,
            )
            if strict_object
            else json.loads(raw)
        )
    except FileNotFoundError as exc:
        raise SubstrateRegistryError("substrate_catalog_missing", path.as_posix()) from exc
    except (UnicodeDecodeError, ValueError) as exc:
        raise SubstrateRegistryError("substrate_catalog_invalid", path.as_posix()) from exc
    if not isinstance(payload, dict):
        raise SubstrateRegistryError("substrate_catalog_invalid", path.as_posix())
    return payload


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate members when binding a selected production-data root."""

    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_object_key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> NoReturn:
    """Reject non-standard constants in selected production-data root JSON."""

    raise ValueError(f"non_json_constant:{value}")


def _load_json_source_bytes(path: Path) -> tuple[dict[str, Any], bytes]:
    """Parse one owner JSON file while retaining the exact bytes behind its ref."""
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except FileNotFoundError as exc:
        raise SubstrateRegistryError("substrate_catalog_missing", path.as_posix()) from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SubstrateRegistryError("substrate_catalog_invalid", path.as_posix()) from exc
    if not isinstance(value, dict):
        raise SubstrateRegistryError("substrate_catalog_invalid", path.as_posix())
    return value, raw


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _repo_relative_path(path: Path, *, repo_root: Path) -> str:
    """Resolve a source file beneath the canonical owner root or refuse it."""

    try:
        resolved_root = Path(repo_root).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise SubstrateRegistryError("substrate_source_repo_root_unavailable") from exc
    if not resolved_root.is_dir():
        raise SubstrateRegistryError("substrate_source_repo_root_not_directory")
    try:
        resolved_path = Path(path).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise SubstrateRegistryError("substrate_source_path_unavailable", str(path)) from exc
    if not resolved_path.is_file():
        raise SubstrateRegistryError("substrate_source_path_not_file", str(path))
    try:
        relative = resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise SubstrateRegistryError(
            "substrate_source_path_outside_repo_root",
            f"{resolved_path} is outside {resolved_root}",
        ) from exc
    if not relative.parts:
        raise SubstrateRegistryError("substrate_source_path_not_file", str(path))
    return relative.as_posix()


def _repo_uri(path: Path, *, repo_root: Path) -> str:
    """Return a normalized repo URI for a source under the selected owner root."""

    return f"repo://{_repo_relative_path(path, repo_root=repo_root)}"


def _repo_ref(path: Path, *, marker: str, repo_root: Path) -> str:
    """Return a repository-relative source ref under the selected owner root."""

    return f"{_repo_uri(path, repo_root=repo_root)}#{marker}"
