"""Production World Bank WDI binding for one verified acquisition route."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, NoReturn, Protocol, Self, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import canon
from polisyos.data_forge import read_api as data_forge_read_api
from polisyos.fabric import data_plane as fabric_data_plane
from polisyos.runtime.quality.acquisition_executor import (
    LiveAcquisitionExecutionError,
    LiveCatalogExecutionConstraints,
    execute_live_catalog_acquisition,
    require_live_catalog_constraints_within_authority_scope,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.runtime.http.services.acquisition_action_service import (
        AcquisitionOwnerExecutionResult,
    )
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.quality.acquisition_route_loop import VerifiedAcquisitionRouteClosure

class _CanonicalAcquisitionAuthority(Protocol):
    registry_path: Path

    def resolve(self, entry_id: str) -> object: ...

    def resolve_live_harness_receipt(self, entry_id: str, attempt_id: str) -> object: ...


class _AcquisitionAuthorityRegistry(Protocol):
    entries: tuple[Any, ...]
    content_sha256: str
    baseline_content_sha256: str
    l5_measurement_registry_sha256: str


class _AcquisitionAuthorityProvision(Protocol):
    provision_id: str
    baseline_content_sha256: str
    baseline_owner_ref: str
    l5_measurement_registry_content_sha256: str
    l5_measurement_registry_owner_ref: str
    live_harness_receipts: tuple[Any, ...]


class _ArtifactReference(Protocol):
    artifact_id: object


class _LiveSourceExecutionEvidence(Protocol):
    raw_artifact_id: object
    evidence_bundle_ref: _ArtifactReference
    data_snapshot_ref: _ArtifactReference
    normalized_data_artifact_id: object


_CATALOG_API: Any = data_forge_read_api.catalog
ResolvedAcquisitionAuthority: Any = _CATALOG_API.ResolvedAcquisitionAuthority
ResolvedLiveHarnessReceipt: Any = _CATALOG_API.ResolvedLiveHarnessReceipt

_RUNTIME_SUBTREE = Path("runtime/acquisition/worldbank-wdi")
_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
WORLD_BANK_WDI_ROUTE_BINDING_SCHEMA_VERSION = (
    "polisyos.runtime.world_bank_wdi_route_execution_binding.v1"
)
WORLD_BANK_WDI_CONNECTOR_ID = "worldbank.wdi"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class WorldBankWDIRouteExecutionBinding(_StrictModel):
    """One content-bound route, authority entry, and provisioned live attempt."""

    schema_version: Literal[
        "polisyos.runtime.world_bank_wdi_route_execution_binding.v1"
    ] = "polisyos.runtime.world_bank_wdi_route_execution_binding.v1"
    binding_id: str = Field(pattern=r"^acquisition-route-binding:sha256:[0-9a-f]{64}$")
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    route_id: str = Field(pattern=_SHA256_PATTERN)
    target_variable: str = Field(min_length=1)
    authority_entry_id: str = Field(
        pattern=r"^acquisition-authority:sha256:[0-9a-f]{64}$"
    )
    authority_provision_id: str = Field(
        pattern=r"^acquisition-authority-provision:sha256:[0-9a-f]{64}$"
    )
    authority_provision_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    authority_registry_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    connector_id: Literal["worldbank.wdi"] = "worldbank.wdi"
    attempt_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]+$")
    harness_receipt_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    carrier_receipt_sha256: str = Field(pattern=_SHA256_PATTERN)
    constraints: LiveCatalogExecutionConstraints

    @model_validator(mode="after")
    def _identity_is_recomputed(self) -> Self:
        expected = "acquisition-route-binding:" + fabric_data_plane.content_sha256(
            self.identity_payload()
        )
        if self.binding_id != expected:
            raise ValueError("route execution binding identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the projection defining this exact executable binding."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "binding_id"
        }


class _WorldBankWDIAttemptLease(_StrictModel):
    schema_version: Literal["polisyos.runtime.world_bank_wdi_attempt_lease.v1"] = (
        "polisyos.runtime.world_bank_wdi_attempt_lease.v1"
    )
    binding: WorldBankWDIRouteExecutionBinding


def resolve_world_bank_wdi_route_execution_bindings(
    *,
    closure: VerifiedAcquisitionRouteClosure,
    authority: _CanonicalAcquisitionAuthority,
    registry: _AcquisitionAuthorityRegistry,
    provision: _AcquisitionAuthorityProvision,
    provision_content_sha256: str,
) -> tuple[WorldBankWDIRouteExecutionBinding, ...]:
    """Resolve one current data route into exact provisioned WDI attempt bindings."""

    variable_id = _require_live_variable_route(closure)
    entries = tuple(
        entry
        for entry in registry.entries
        if entry.source_lane == "live_fetch" and entry.target_variable == variable_id
    )
    if len(entries) != 1:
        code = (
            "live_route_authority_entry_missing"
            if not entries
            else "live_route_authority_entry_ambiguous"
        )
        raise LiveAcquisitionExecutionError(code, variable_id)
    entry = entries[0]
    try:
        resolved = ResolvedAcquisitionAuthority.model_validate(authority.resolve(entry.entry_id))
    except Exception as exc:
        raise LiveAcquisitionExecutionError(
            "live_route_authority_entry_unresolved",
            type(exc).__name__,
        ) from exc
    if resolved.entry != entry:
        raise LiveAcquisitionExecutionError("live_route_authority_entry_drift", entry.entry_id)
    if (
        resolved.registry_content_sha256 != registry.content_sha256
        or resolved.baseline_content_sha256 != registry.baseline_content_sha256
    ):
        raise LiveAcquisitionExecutionError(
            "live_route_authority_registry_drift",
            entry.entry_id,
        )
    if (
        resolved.authority_provision_id != provision.provision_id
        or resolved.authority_provision_content_sha256 != provision_content_sha256
        or provision.baseline_content_sha256 != registry.baseline_content_sha256
        or provision.l5_measurement_registry_content_sha256
        != registry.l5_measurement_registry_sha256
    ):
        raise LiveAcquisitionExecutionError(
            "live_route_authority_provision_drift",
            entry.entry_id,
        )
    if resolved.registration.connector_id != WORLD_BANK_WDI_CONNECTOR_ID:
        raise LiveAcquisitionExecutionError(
            "live_route_connector_family_out_of_scope",
            resolved.registration.connector_id,
        )

    constraints = _constraints_from_live_variable_route(closure)
    require_live_catalog_constraints_within_authority_scope(entry, constraints)
    attempt_provisions = tuple(
        candidate
        for candidate in provision.live_harness_receipts
        if candidate.entry_id == entry.entry_id
    )
    if not attempt_provisions:
        raise LiveAcquisitionExecutionError(
            "live_route_authority_attempt_missing",
            entry.entry_id,
        )

    bindings: list[WorldBankWDIRouteExecutionBinding] = []
    for attempt in attempt_provisions:
        try:
            receipt = ResolvedLiveHarnessReceipt.model_validate(
                authority.resolve_live_harness_receipt(entry.entry_id, attempt.attempt_id)
            )
        except Exception as exc:
            raise LiveAcquisitionExecutionError(
                "live_route_authority_attempt_unresolved",
                f"{attempt.attempt_id}:{type(exc).__name__}",
            ) from exc
        if (
            receipt.entry_id != entry.entry_id
            or receipt.attempt_id != attempt.attempt_id
            or receipt.receipt_owner_ref != attempt.receipt_owner_ref
            or receipt.receipt_content_sha256 != attempt.receipt_content_sha256
        ):
            raise LiveAcquisitionExecutionError(
                "live_route_authority_attempt_drift",
                attempt.attempt_id,
            )
        payload = {
            "schema_version": WORLD_BANK_WDI_ROUTE_BINDING_SCHEMA_VERSION,
            "tenant_id": closure.tenant_id,
            "cell_id": closure.cell_id,
            "run_id": closure.run_id,
            "route_id": closure.route_id,
            "target_variable": variable_id,
            "authority_entry_id": entry.entry_id,
            "authority_provision_id": provision.provision_id,
            "authority_provision_content_sha256": provision_content_sha256,
            "authority_registry_content_sha256": registry.content_sha256,
            "connector_id": WORLD_BANK_WDI_CONNECTOR_ID,
            "attempt_id": attempt.attempt_id,
            "harness_receipt_content_sha256": receipt.receipt_content_sha256,
            "carrier_receipt_sha256": receipt.carrier_receipt_sha256,
            "constraints": constraints.model_dump(mode="json"),
        }
        bindings.append(
            WorldBankWDIRouteExecutionBinding(
                **payload,
                binding_id=(
                    "acquisition-route-binding:"
                    + fabric_data_plane.content_sha256(payload)
                ),
            )
        )
    return tuple(bindings)


def _require_live_variable_route(closure: VerifiedAcquisitionRouteClosure) -> str:
    record = closure.planner_record
    gap_type = getattr(record.gap_type, "value", record.gap_type)
    recommended_strategy = getattr(
        record.recommended_strategy,
        "value",
        record.recommended_strategy,
    )
    if (
        gap_type != "data_snapshot_release"
        or record.requirement_family != "data_requirement"
        or record.requirement_schema_version
        != "policyos.runtime.l1_variable_availability_gap.v1"
        or recommended_strategy != "production_snapshot_build"
    ):
        raise LiveAcquisitionExecutionError("live_route_requirement_shape_invalid")
    fields = tuple(record.missing_requirement_fields)
    prefix = "canonical_variable_observations:"
    if len(fields) != 1 or not fields[0].startswith(prefix):
        raise LiveAcquisitionExecutionError("live_route_variable_requirement_invalid")
    variable_id = fields[0].removeprefix(prefix)
    if not variable_id or variable_id.strip() != variable_id:
        raise LiveAcquisitionExecutionError("live_route_variable_requirement_invalid")
    return variable_id


def _constraints_from_live_variable_route(
    closure: VerifiedAcquisitionRouteClosure,
) -> LiveCatalogExecutionConstraints:
    semantics = closure.design_problem.jurisdiction_time
    country_code = semantics.region
    data_time = semantics.data_time
    if not re.fullmatch(r"[A-Z]{3}", country_code):
        raise LiveAcquisitionExecutionError("live_route_country_scope_invalid", country_code)
    if not re.fullmatch(r"[0-9]{4}", data_time):
        raise LiveAcquisitionExecutionError("live_route_data_time_invalid", data_time)
    year = int(data_time)
    try:
        return LiveCatalogExecutionConstraints(
            country_code=country_code,
            start_year=year,
            end_year=year,
            page_size=1_000,
            max_response_bytes=65_536,
            max_decompressed_bytes=65_536,
            timeout_cap_seconds=15.0,
            heartbeat_cap_seconds=5.0,
        )
    except ValueError as exc:
        raise LiveAcquisitionExecutionError(
            "live_route_execution_constraints_invalid",
            type(exc).__name__,
        ) from exc


class WorldBankWDIAcquisitionExecutionPort:
    """Lease and execute one canonical WDI attempt for an exact tenant-bound route."""

    def __init__(
        self,
        *,
        authority: _CanonicalAcquisitionAuthority,
        registry: _AcquisitionAuthorityRegistry,
        provision: _AcquisitionAuthorityProvision,
        provision_content_sha256: str,
        runtime_state_root: Path,
        executor: Callable[..., _LiveSourceExecutionEvidence] | None = None,
    ) -> None:
        catalog_api: Any = data_forge_read_api.catalog
        if type(authority) is not catalog_api.CanonicalAcquisitionAuthority:
            raise TypeError("live acquisition authority owner must be canonical")
        if type(registry) is not catalog_api.AcquisitionAuthorityRegistry:
            raise TypeError("live acquisition registry owner must be canonical")
        if type(provision) is not catalog_api.AcquisitionAuthorityProvision:
            raise TypeError("live acquisition provision owner must be canonical")
        if executor is not None and not callable(executor):
            raise TypeError("live acquisition executor must be callable")
        root = Path(runtime_state_root).resolve()
        if root == root.parent:
            raise ValueError("live acquisition runtime root cannot be a filesystem root")
        self._authority = authority
        self._registry = registry
        self._provision = provision
        self._provision_content_sha256 = provision_content_sha256
        self._runtime_state_root = root
        self._executor = executor

    def require_route_ready(self, closure: VerifiedAcquisitionRouteClosure) -> None:
        """Resolve the binding and require an unconsumed attempt without touching a provider."""

        bindings = resolve_world_bank_wdi_route_execution_bindings(
            closure=closure,
            authority=self._authority,
            registry=self._registry,
            provision=self._provision,
            provision_content_sha256=self._provision_content_sha256,
        )
        if any(
            not self._lease_path(binding).exists()
            or self._reserved_binding_is_reusable(binding)
            for binding in bindings
        ):
            return
        from polisyos.runtime.http.services.acquisition_action_service import (
            AcquisitionActionServiceError,
        )

        raise AcquisitionActionServiceError("acquisition_live_attempt_exhausted")

    def reserve_route_binding(
        self,
        closure: VerifiedAcquisitionRouteClosure,
    ) -> WorldBankWDIRouteExecutionBinding:
        """Atomically reserve one exact attempt before any authority/provider side effect."""

        bindings = resolve_world_bank_wdi_route_execution_bindings(
            closure=closure,
            authority=self._authority,
            registry=self._registry,
            provision=self._provision,
            provision_content_sha256=self._provision_content_sha256,
        )
        return self._reserve_first_fresh(bindings)

    def execute(
        self,
        closure: VerifiedAcquisitionRouteClosure,
    ) -> AcquisitionOwnerExecutionResult:
        """Resolve, lease, and execute without admitting observations or growing the world."""

        binding = self.reserve_route_binding(closure)
        self._claim_reserved_binding(binding)
        journal_path, cas_root = self._governed_paths(binding)
        evidence: _LiveSourceExecutionEvidence
        if self._executor is None:
            evidence = execute_live_catalog_acquisition(
                authority=self._authority,
                entry_id=binding.authority_entry_id,
                attempt_id=binding.attempt_id,
                constraints=binding.constraints,
                journal_path=journal_path,
                cas_root=cas_root,
            )
        else:
            evidence = self._executor(
                authority=self._authority,
                entry_id=binding.authority_entry_id,
                attempt_id=binding.attempt_id,
                constraints=binding.constraints,
                journal_path=journal_path,
                cas_root=cas_root,
            )
        owner_receipt_refs = tuple(
            dict.fromkeys(
                (
                    str(evidence.raw_artifact_id),
                    str(evidence.evidence_bundle_ref.artifact_id),
                    str(evidence.data_snapshot_ref.artifact_id),
                    str(evidence.normalized_data_artifact_id),
                )
            )
        )
        from polisyos.runtime.http.services.acquisition_action_service import (
            AcquisitionOwnerExecutionResult,
        )

        return AcquisitionOwnerExecutionResult(
            disposition="quarantined_no_growth",
            owner_receipt_refs=owner_receipt_refs,
            admitted_observation_delta=0,
        )

    def reenter(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        result: AcquisitionOwnerExecutionResult,
    ) -> str:
        """Refuse world re-entry because N13b evidence remains quarantined."""

        del closure, result
        self._raise_reentry_not_admitted()

    def resume_reentry(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        owner_receipt_refs: tuple[str, ...],
    ) -> str:
        """Refuse re-entry recovery because this port cannot activate an epoch."""

        del closure, owner_receipt_refs
        self._raise_reentry_not_admitted()

    def _reserve_first_fresh(
        self,
        bindings: tuple[WorldBankWDIRouteExecutionBinding, ...],
    ) -> WorldBankWDIRouteExecutionBinding:
        lease_root = self._runtime_state_root / _RUNTIME_SUBTREE / "attempt-leases"
        lease_root.mkdir(parents=True, exist_ok=True)
        for binding in bindings:
            lease_path = self._lease_path(binding)
            lease = _WorldBankWDIAttemptLease(binding=binding)
            encoded = canon.to_canonical_bytes(
                lease.model_dump(mode="json"),
                canon.CanonSpec(forbid_floats=False),
            ) + b"\n"
            try:
                descriptor = os.open(
                    lease_path,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o400,
                )
            except FileExistsError:
                if self._reserved_binding_is_reusable(binding):
                    return binding
                continue
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())
                _fsync_directory(lease_root)
            except BaseException:
                # A partial or malformed lease remains consumed. Reuse would convert an
                # uncertain persistence outcome into replay authority.
                raise
            return binding
        from polisyos.runtime.http.services.acquisition_action_service import (
            AcquisitionActionServiceError,
        )

        raise AcquisitionActionServiceError("acquisition_live_attempt_exhausted")

    def _reserved_binding_is_reusable(
        self,
        binding: WorldBankWDIRouteExecutionBinding,
    ) -> bool:
        if self._execution_claim_path(binding).exists():
            return False
        try:
            lease = _WorldBankWDIAttemptLease.model_validate(
                canon.from_canonical_bytes(self._lease_path(binding).read_bytes())
            )
        except (OSError, ValueError):
            return False
        return lease.binding == binding

    def _claim_reserved_binding(
        self,
        binding: WorldBankWDIRouteExecutionBinding,
    ) -> None:
        claim_path = self._execution_claim_path(binding)
        payload = {
            "schema_version": "polisyos.runtime.world_bank_wdi_attempt_claim.v1",
            "binding_id": binding.binding_id,
        }
        encoded = canon.to_canonical_bytes(payload) + b"\n"
        try:
            descriptor = os.open(
                claim_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o400,
            )
        except FileExistsError as exc:
            from polisyos.runtime.http.services.acquisition_action_service import (
                AcquisitionActionServiceError,
            )

            raise AcquisitionActionServiceError("acquisition_live_attempt_exhausted") from exc
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        _fsync_directory(claim_path.parent)

    def _lease_path(self, binding: WorldBankWDIRouteExecutionBinding) -> Path:
        token = hashlib.sha256(
            b"polisyos.world-bank-wdi-attempt-lease.v1\0"
            + binding.attempt_id.encode("utf-8")
        ).hexdigest()
        return self._runtime_state_root / _RUNTIME_SUBTREE / "attempt-leases" / f"{token}.json"

    def _execution_claim_path(self, binding: WorldBankWDIRouteExecutionBinding) -> Path:
        return self._lease_path(binding).with_suffix(".claim")

    def _governed_paths(
        self,
        binding: WorldBankWDIRouteExecutionBinding,
    ) -> tuple[Path, Path]:
        scope = {
            "schema_version": "polisyos.runtime.world_bank_wdi_route_storage_scope.v1",
            "tenant_id": binding.tenant_id,
            "cell_id": binding.cell_id,
            "run_id": binding.run_id,
            "route_id": binding.route_id,
        }
        token = hashlib.sha256(canon.to_canonical_bytes(scope)).hexdigest()
        route_root = self._runtime_state_root / _RUNTIME_SUBTREE / "routes" / token
        cas_root = route_root / "cas"
        cas_root.mkdir(parents=True, exist_ok=True)
        return route_root / "evidence-journal.jsonl", cas_root

    @staticmethod
    def _raise_reentry_not_admitted() -> NoReturn:
        from polisyos.runtime.http.services.acquisition_action_service import (
            AcquisitionActionServiceError,
        )

        raise AcquisitionActionServiceError("acquisition_live_evidence_not_admitted")


def build_production_world_bank_wdi_execution_port(
    *,
    control_service: ControlPlaneService,
) -> WorldBankWDIAcquisitionExecutionPort | None:
    """Build the canonical port only for a production deployment with all owner files."""

    policy_resolver = getattr(control_service, "_policy_resolver", None)
    if getattr(policy_resolver, "default_profile", None) != "production":
        return None
    repo_root = Path(__file__).resolve().parents[5]
    catalog_api: Any = data_forge_read_api.catalog
    provision_path = repo_root / Path(str(catalog_api.DEFAULT_ACQUISITION_AUTHORITY_PROVISION))
    if not provision_path.is_file():
        return None
    provision_raw = provision_path.read_bytes()
    provision = cast(
        "_AcquisitionAuthorityProvision",
        catalog_api.AcquisitionAuthorityProvision.model_validate_json(provision_raw),
    )
    baseline_path = _repo_owner_path(repo_root, provision.baseline_owner_ref)
    l5_path = _repo_owner_path(repo_root, provision.l5_measurement_registry_owner_ref)
    if baseline_path is None or l5_path is None:
        return None
    if not baseline_path.is_file() or not l5_path.is_file():
        return None
    authority = cast(
        "_CanonicalAcquisitionAuthority",
        catalog_api.CanonicalAcquisitionAuthority.from_provision(
            repo_root=repo_root,
            baseline_path=baseline_path,
            l5_measurement_registry_path=l5_path,
        ),
    )
    registry_path = Path(authority.registry_path)
    if not registry_path.is_file():
        return None
    registry = cast(
        "_AcquisitionAuthorityRegistry",
        catalog_api.AcquisitionAuthorityRegistry.model_validate_json(registry_path.read_bytes()),
    )
    return WorldBankWDIAcquisitionExecutionPort(
        authority=authority,
        registry=registry,
        provision=provision,
        provision_content_sha256="sha256:" + hashlib.sha256(provision_raw).hexdigest(),
        runtime_state_root=Path(control_service._cas_root),
    )


def _repo_owner_path(repo_root: Path, owner_ref: str) -> Path | None:
    if not owner_ref.startswith("repo://"):
        return None
    relative = Path(owner_ref.removeprefix("repo://"))
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        return None
    candidate = (repo_root / relative).resolve()
    try:
        candidate.relative_to(repo_root)
    except ValueError:
        return None
    return candidate


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


__all__ = [
    "WORLD_BANK_WDI_CONNECTOR_ID",
    "WORLD_BANK_WDI_ROUTE_BINDING_SCHEMA_VERSION",
    "WorldBankWDIAcquisitionExecutionPort",
    "WorldBankWDIRouteExecutionBinding",
    "build_production_world_bank_wdi_execution_port",
    "resolve_world_bank_wdi_route_execution_bindings",
]
