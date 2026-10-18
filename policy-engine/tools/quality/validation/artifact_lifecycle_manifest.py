"""Generated and frozen artifact lifecycle manifests."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from polisyos.fabric.data_plane import content_sha256
from tools.quality.validation.layer3_gy_n13b_acceptance import AcceptanceCaseReceipt
from tools.quality.validation.layer3_gy_n13b_derivation_universality import (
    DEFAULT_UNIVERSALITY_RECEIPT,
)

from .acquisition_contract_support import (
    DEFAULT_DERIVED_ACCEPTANCE,
    DEFAULT_GENERATED_ARTIFACTS,
    DEFAULT_N13B_CAS,
    DEFAULT_N13B_CONTRACT,
    DEFAULT_N13B_LIFECYCLE_MANIFEST,
    DEFAULT_N13B_PROVISION,
    DEFAULT_N13B_REGISTRY,
    N13B_FAMILY_ID,
    N13B_SOURCE_FAMILY_ID,
    SHA256_PATTERN,
    N13bContractError,
    _bytes_sha256,
    _file_sha256,
    _json_value,
    _read_epoch_model,
    _read_model,
    _StrictModel,
)
from .evidence_journal_custody import (
    _cas_blob_relative,
    _cas_manifest_relative,
    _n13b_lifecycle_families,
    _verify_n13b_source_integrity,
)


class LifecycleRegistration(_StrictModel):
    """One exact output row from the generated-artifact family denominator."""

    path: str = Field(min_length=1)
    role: Literal[
        "writer_managed",
        "journal",
        "cas_blob",
        "cas_manifest",
        "provision",
        "registry",
        "receipt",
    ]
    registration_status: Literal["writer_managed", "content_bound"]
    byte_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    byte_size: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _registration_is_well_formed(self) -> Self:
        if self.registration_status == "writer_managed":
            if self.role != "writer_managed" or self.byte_sha256 is not None:
                raise ValueError("writer-managed outputs cannot self-bind content")
        elif self.role == "writer_managed" or self.byte_sha256 is None or self.byte_size is None:
            raise ValueError("content-bound lifecycle output is incomplete")
        return self


class N13bLifecycleManifestV2(_StrictModel):
    """Historical lifecycle epoch with the original combined registry family."""

    schema_version: Literal["policyos.layer3.gy.n13b.lifecycle_manifest.v2"] = (
        "policyos.layer3.gy.n13b.lifecycle_manifest.v2"
    )
    generated_family_id: Literal["policy-design-case-layer3-gy-n13b-acquisition-executor"]
    generated_family_projection_sha256: str = Field(pattern=SHA256_PATTERN)
    registrations: tuple[LifecycleRegistration, ...] = Field(min_length=1)
    registered_output_count: int = Field(ge=1)
    content_bound_output_count: int = Field(ge=1)
    phantom_output_count: int = Field(ge=0)
    materialized_acquired_snapshot_count: int = Field(ge=0)
    registered_acquired_snapshot_count: int = Field(ge=0)
    canonical_provision_registered: bool
    derived_artifact_registered: bool
    derivation_certificate_registered: bool
    universality_receipt_registered: bool
    owner_registration_derivation_missing_closed: bool
    manifest_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _closure_is_recomputed(self) -> Self:
        paths = tuple(row.path for row in self.registrations)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("lifecycle output denominator must be unique and sorted")
        content_bound = sum(
            row.registration_status == "content_bound" for row in self.registrations
        )
        if (
            self.registered_output_count != len(self.registrations)
            or self.content_bound_output_count != content_bound
        ):
            raise ValueError("lifecycle registration counts must be recomputed")
        expected_closed = (
            self.phantom_output_count == 0
            and self.materialized_acquired_snapshot_count == self.registered_acquired_snapshot_count
            and self.canonical_provision_registered
            and self.derived_artifact_registered
            and self.derivation_certificate_registered
            and self.universality_receipt_registered
        )
        if self.owner_registration_derivation_missing_closed != expected_closed:
            raise ValueError("owner-registration residual must be recomputed")
        if self.manifest_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("lifecycle manifest identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        value = {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "manifest_sha256"
        }
        value["registrations"] = [
            {
                "path": row.path,
                "role": row.role,
                "registration_status": row.registration_status,
            }
            for row in self.registrations
        ]
        return value


class N13bLifecycleManifest(N13bLifecycleManifestV2):
    """Current custody union of generated outputs and frozen source evidence."""

    schema_version: Literal["policyos.layer3.gy.n13b.lifecycle_manifest.v3"] = (
        "policyos.layer3.gy.n13b.lifecycle_manifest.v3"
    )
    source_family_id: Literal["policy-design-case-layer3-gy-n13b-frozen-acquisition-evidence"]


def derive_lifecycle_manifest(
    repo_root: Path,
    *,
    derived_artifact_id: str | None = None,
    certificate_artifact_id: str | None = None,
    prospective_outputs: Mapping[str, bytes] | None = None,
    generated_artifacts_bytes: bytes | None = None,
    required_cas_artifact_ids: Sequence[str] | None = None,
) -> N13bLifecycleManifest:
    """Derive full custody registrations from both real lifecycle owner families."""

    root = Path(repo_root)
    if derived_artifact_id is None or certificate_artifact_id is None:
        acceptance = _read_model(
            root / DEFAULT_DERIVED_ACCEPTANCE,
            AcceptanceCaseReceipt,
        )
        derived_artifact_id = acceptance.derived_artifact_id
        certificate_artifact_id = acceptance.certificate_artifact_id
    generated_path = root / DEFAULT_GENERATED_ARTIFACTS
    try:
        registry_bytes = (
            generated_artifacts_bytes
            if generated_artifacts_bytes is not None
            else generated_path.read_bytes()
        )
        payload = tomllib.loads(registry_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise N13bContractError("generated_artifact_registry_unreadable") from exc
    families = _n13b_lifecycle_families(payload)
    _verify_n13b_source_integrity(root, families[1])
    outputs = tuple(sorted(str(value) for family in families for value in family["outputs"]))
    if required_cas_artifact_ids is not None:
        expected_cas_outputs = {
            path
            for artifact_id in required_cas_artifact_ids
            for path in (
                _cas_blob_relative(str(artifact_id)),
                _cas_manifest_relative(str(artifact_id)),
            )
        }
        cas_prefix = (DEFAULT_N13B_CAS / "artifacts/sha256").as_posix() + "/"
        registered_cas_outputs = {path for path in outputs if path.startswith(cas_prefix)}
        if registered_cas_outputs != expected_cas_outputs:
            raise N13bContractError("n13b_generated_cas_output_denominator_drift")
    writer_paths = {
        DEFAULT_N13B_CONTRACT.as_posix(),
        DEFAULT_N13B_LIFECYCLE_MANIFEST.as_posix(),
    }
    prospective = dict(prospective_outputs or {})
    if set(prospective) - set(outputs):
        raise N13bContractError("n13b_prospective_output_not_registered")
    registrations: list[LifecycleRegistration] = []
    phantom = 0
    for relative in outputs:
        path = root / relative
        if relative in writer_paths:
            registrations.append(
                LifecycleRegistration(
                    path=relative,
                    role="writer_managed",
                    registration_status="writer_managed",
                    byte_sha256=None,
                    byte_size=None,
                )
            )
            continue
        if relative in prospective:
            payload = prospective[relative]
            registrations.append(
                LifecycleRegistration(
                    path=relative,
                    role=_lifecycle_role(relative),
                    registration_status="content_bound",
                    byte_sha256=_bytes_sha256(payload),
                    byte_size=len(payload),
                )
            )
            continue
        if not path.is_file():
            phantom += 1
            continue
        registrations.append(
            LifecycleRegistration(
                path=relative,
                role=_lifecycle_role(relative),
                registration_status="content_bound",
                byte_sha256=_file_sha256(path),
                byte_size=path.stat().st_size,
            )
        )
    registration_paths = {row.path for row in registrations}
    derived_path = _cas_blob_relative(derived_artifact_id)
    certificate_path = _cas_blob_relative(certificate_artifact_id)
    snapshots = tuple(
        path
        for path in outputs
        if "snapshot" in Path(path).name or "overlay.duckdb" in Path(path).name
    )
    materialized_snapshots = tuple(path for path in snapshots if (root / path).is_file())
    family_projection = {
        str(family["id"]): {
            key: family.get(key)
            for key in (
                "id",
                "lifecycle",
                "gy_lifecycle_family",
                "generator",
                "verifier",
                "promotion_target",
                "stale_output_behavior",
                "source_of_truth",
                "source_committed_rationale",
                "source_integrity_sha256",
                "outputs",
                "regenerate_commands",
                "workflow",
                "check_command",
            )
        }
        for family in families
    }
    values = {
        "schema_version": "policyos.layer3.gy.n13b.lifecycle_manifest.v3",
        "generated_family_id": N13B_FAMILY_ID,
        "source_family_id": N13B_SOURCE_FAMILY_ID,
        "generated_family_projection_sha256": content_sha256(family_projection),
        "registrations": tuple(sorted(registrations, key=lambda row: row.path)),
        "registered_output_count": len(registrations),
        "content_bound_output_count": sum(
            row.registration_status == "content_bound" for row in registrations
        ),
        "phantom_output_count": phantom,
        "materialized_acquired_snapshot_count": len(materialized_snapshots),
        "registered_acquired_snapshot_count": sum(
            path in registration_paths for path in materialized_snapshots
        ),
        "canonical_provision_registered": DEFAULT_N13B_PROVISION.as_posix() in registration_paths,
        "derived_artifact_registered": derived_path in registration_paths,
        "derivation_certificate_registered": certificate_path in registration_paths,
        "universality_receipt_registered": (
            DEFAULT_UNIVERSALITY_RECEIPT.as_posix() in registration_paths
        ),
        "owner_registration_derivation_missing_closed": False,
    }
    values["owner_registration_derivation_missing_closed"] = (
        phantom == 0
        and len(materialized_snapshots)
        == sum(path in registration_paths for path in materialized_snapshots)
        and values["canonical_provision_registered"]
        and values["derived_artifact_registered"]
        and values["derivation_certificate_registered"]
        and values["universality_receipt_registered"]
    )
    identity = _json_value(values)
    identity["registrations"] = [
        {
            "path": row.path,
            "role": row.role,
            "registration_status": row.registration_status,
        }
        for row in values["registrations"]
    ]
    return N13bLifecycleManifest(**values, manifest_sha256=content_sha256(identity))


def read_n13b_lifecycle_manifest(path: Path) -> N13bLifecycleManifestV2 | N13bLifecycleManifest:
    """Read either recorded lifecycle epoch without promoting historical evidence."""

    receipt = _read_epoch_model(
        path,
        {
            "policyos.layer3.gy.n13b.lifecycle_manifest.v2": N13bLifecycleManifestV2,
            "policyos.layer3.gy.n13b.lifecycle_manifest.v3": N13bLifecycleManifest,
        },
    )
    assert isinstance(receipt, N13bLifecycleManifestV2)
    return receipt


def _lifecycle_role(
    path: str,
) -> Literal[
    "journal",
    "cas_blob",
    "cas_manifest",
    "provision",
    "registry",
    "receipt",
]:
    if path.endswith(".jsonl"):
        return "journal"
    if path.endswith(".blob"):
        return "cas_blob"
    if path.endswith(".manifest.json"):
        return "cas_manifest"
    if path == DEFAULT_N13B_PROVISION.as_posix():
        return "provision"
    if path == DEFAULT_N13B_REGISTRY.as_posix():
        return "registry"
    return "receipt"
