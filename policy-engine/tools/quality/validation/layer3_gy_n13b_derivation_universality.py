"""Zero-network, epoch-zero universality proof for data-defined derivations.

The proof deliberately treats every transform family in the owner registry the
same way.  It enumerates the complete local series denominator, resolves inputs
from owner units/rights/alignments/bindings, and sends the selected series
through the production recipe, CAS, certificate, and consumer path.  Family
identifiers and source identifiers are evidence fields; none steer this module.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal, Self

import duckdb
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts
from polisyos.data_forge import read_api as data_forge_read_api
from polisyos.fabric.data_plane import canonical_json_bytes, content_sha256
from polisyos.runtime.quality.acquisition_executor import (
    ObservationProvenanceClass,
    derive_observation_provenance_rejections,
)
from polisyos.runtime.quality.derived_observations import (
    AuthorityProjection,
    BasisSignature,
    CertifiedDerivationConsumption,
    DerivationCertificate,
    DerivationRecipe,
    DerivationRefusalCode,
    DerivationRefusalError,
    DerivationRefusalReason,
    SeriesPoint,
    SourceSeries,
    TransformFamily,
    TransformFamilyRegistry,
    TransformInputSpec,
    build_derivation_recipe,
    consume_certified_derivation,
    load_transform_family_registry,
    materialize_derivation,
    persist_source_series,
)

DEFAULT_DERIVATION_FAMILY_REGISTRY = Path(
    "architecture/production_quality/derivation_family_registry.toml"
)
DEFAULT_UNIVERSALITY_RECEIPT = Path(
    "architecture/policy_design_case/layer3_gy_n13b_derivation_universality.json"
)

UNIVERSALITY_SCHEMA_VERSION = "policyos.layer3.gy.n13b.derivation-universality.v1"
_SOURCE_PRODUCER = artifacts.ProducerInfo(
    component="tools.quality.validation.layer3_gy_n13b_derivation_universality",
    version="1.0.0",
)
_EVIDENCE_SCHEMA = artifacts.SchemaInfo(
    name="policyos.layer3.gy.n13b.derivation-universality-input-evidence",
    version="1.0.0",
)
_EVIDENCE_KIND = "policyos.layer3.gy.n13b.derivation_input_evidence"


class UniversalityProofError(RuntimeError):
    """Typed local-proof refusal."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail or code
        super().__init__(f"{code}: {self.detail}")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CatalogPoint(_StrictModel):
    """One owner-bound epoch-zero point used by the selector."""

    observation_id: str = Field(min_length=1)
    year: int = Field(ge=1900, le=2200)
    value: Decimal
    source_watermark: str
    dataset_version: str
    acquisition_method: str


class CatalogCandidate(_StrictModel):
    """One full-denominator disposition for one declared transform role."""

    family_id: str = Field(min_length=1)
    method_version: str = Field(min_length=1)
    role: str = Field(min_length=1)
    required_basis: BasisSignature
    dataset_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    agency: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str
    access_license: str
    raw_variable: str = Field(min_length=1)
    metric_id: str | None
    canonical_variable: str = Field(min_length=1)
    derived_unit: str | None
    alignment_method: str | None
    alignment_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    alignment_is_proxy: bool | None
    alignment_proxy_penalty: float | None = Field(default=None, ge=0.0, le=1.0)
    exact_binding_count: int = Field(ge=0)
    maximum_binding_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    maximum_distribution_quality: float | None = Field(default=None, ge=0.0, le=1.0)
    semantic_alignment_score: float = Field(ge=0.0, le=1.0)
    points: tuple[CatalogPoint, ...]
    rejection_codes: tuple[str, ...]
    eligible: bool
    authority_score: Decimal | None = Field(default=None, ge=0, le=1)
    projection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _identity_and_disposition_are_recomputed(self) -> Self:
        years = tuple(point.year for point in self.points)
        if years != tuple(sorted(years)):
            raise ValueError("candidate points must be increasing")
        if self.rejection_codes != tuple(sorted(set(self.rejection_codes))):
            raise ValueError("candidate rejection codes must be unique and sorted")
        if self.eligible != (not self.rejection_codes):
            raise ValueError("candidate eligibility must derive from rejection codes")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("candidate projection identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the candidate evidence excluding its self-hash."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class RejectionCount(_StrictModel):
    """One typed denominator count."""

    code: str = Field(min_length=1)
    count: int = Field(gt=0)


class RoleSelectionProof(_StrictModel):
    """Full-denominator projection and selected owner-admissible input."""

    family_id: str = Field(min_length=1)
    method_version: str = Field(min_length=1)
    role: str = Field(min_length=1)
    required_basis: BasisSignature
    denominator_count: int = Field(ge=1)
    denominator_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    rejection_counts: tuple[RejectionCount, ...]
    eligible_count: int = Field(ge=1)
    selected: CatalogCandidate
    exact_years: tuple[int, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def _selection_is_consistent(self) -> Self:
        if (self.selected.family_id, self.selected.method_version) != (
            self.family_id,
            self.method_version,
        ) or self.selected.role != self.role:
            raise ValueError("selected candidate differs from family role")
        if not self.selected.eligible:
            raise ValueError("selected candidate must be owner-admissible")
        if tuple(point.year for point in self.selected.points) != self.exact_years:
            raise ValueError("selected candidate must carry the shared exact-year set")
        codes = tuple(item.code for item in self.rejection_counts)
        if codes != tuple(sorted(set(codes))):
            raise ValueError("rejection counts must be unique and sorted")
        return self


class FamilyExecutionProof(_StrictModel):
    """Generic execution proof for one registry-defined family."""

    family_id: str = Field(min_length=1)
    method_version: str = Field(min_length=1)
    family_projection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    selections: tuple[RoleSelectionProof, ...] = Field(min_length=1)
    recipe: DerivationRecipe
    recipe_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    certificate: DerivationCertificate
    certificate_artifact_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    derived_artifact_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    first_materialization_cache_hit: Literal[False]
    second_materialization_cache_hit: Literal[True]
    fresh_cas_rebuild_equal: Literal[True]
    consumers: tuple[CertifiedDerivationConsumption, CertifiedDerivationConsumption]
    weakest_input_authority: Decimal = Field(ge=0, le=1)
    derived_authority: Decimal = Field(ge=0, le=1)
    monotone_authority_proven: Literal[True]
    derived_passport_rejection_codes: tuple[str, ...]
    model_output_passport_rejection_codes: tuple[str, ...]
    proof_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _family_proof_is_recomputed(self) -> Self:
        roles = tuple(item.role for item in self.selections)
        if roles != tuple(sorted(set(roles))):
            raise ValueError("family selections must be unique and sorted by role")
        if self.recipe.family.family_id != self.family_id:
            raise ValueError("recipe family differs from proof family")
        if self.recipe.family.method_version != self.method_version:
            raise ValueError("recipe version differs from proof family version")
        if any(
            (selection.family_id, selection.method_version) != (self.family_id, self.method_version)
            for selection in self.selections
        ):
            raise ValueError("selection identity differs from proof family version")
        if self.recipe_sha256 != content_sha256(self.recipe.model_dump(mode="json")):
            raise ValueError("recipe projection hash must be recomputed")
        if self.certificate.recipe != self.recipe:
            raise ValueError("certificate recipe differs from proof recipe")
        if self.derived_authority != self.weakest_input_authority:
            raise ValueError("derived authority must equal the weakest input")
        if self.certificate.effective_authority != self.derived_authority:
            raise ValueError("certificate authority differs from the recomputed ceiling")
        if tuple(item.consumer_method_id for item in self.consumers) != (
            "universality.audit.consumer.a@1.0.0",
            "universality.audit.consumer.b@1.0.0",
        ):
            raise ValueError("universality proof requires two distinct consumers")
        if self.derived_passport_rejection_codes != ("derived_cannot_enter_observed_overlay",):
            raise ValueError("derived output must fail the observed passport")
        if self.model_output_passport_rejection_codes != ("model_output_not_observation",):
            raise ValueError("model output must fail the observed passport")
        if self.proof_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("family proof identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the family proof excluding its self-hash."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "proof_sha256"
        }


class DerivationUniversalityReceipt(_StrictModel):
    """Frozen-ready receipt over every owner-registered transform family."""

    schema_version: Literal[UNIVERSALITY_SCHEMA_VERSION] = UNIVERSALITY_SCHEMA_VERSION
    registry_ref: str = Field(min_length=1)
    registry_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    catalog_ref: str = Field(min_length=1)
    catalog_sha256_before: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    catalog_sha256_after: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_epoch: Literal[0]
    country_code: str = Field(min_length=2, max_length=3)
    full_series_denominator_count: int = Field(ge=1)
    family_count: int = Field(ge=1)
    family_proofs: tuple[FamilyExecutionProof, ...] = Field(min_length=1)
    unregistered_basis_refusal_code: Literal["basis_mismatch"]
    unregistered_basis_refusal_reason: Literal["no_certified_transform"]
    network_call_count: Literal[0]
    receipt_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _receipt_is_recomputed(self) -> Self:
        if self.catalog_sha256_before != self.catalog_sha256_after:
            raise ValueError("epoch-zero catalog bytes moved during the proof")
        family_ids = tuple((item.family_id, item.method_version) for item in self.family_proofs)
        if family_ids != tuple(sorted(set(family_ids))):
            raise ValueError("family proofs must cover unique sorted registry families")
        if self.family_count != len(self.family_proofs):
            raise ValueError("family count must derive from family proofs")
        if any(
            selection.denominator_count != self.full_series_denominator_count
            for proof in self.family_proofs
            for selection in proof.selections
        ):
            raise ValueError("every role must classify the full series denominator")
        if self.receipt_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("universality receipt identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the receipt excluding its self-hash."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "receipt_sha256"
        }


@dataclass(frozen=True)
class _RawSeries:
    dataset_id: str
    source: str
    agency: str
    title: str
    description: str
    access_license: str
    raw_variable: str
    metric_id: str | None
    canonical_variable: str
    alignment_method: str | None
    alignment_confidence: float | None
    alignment_is_proxy: bool | None
    alignment_proxy_penalty: float | None
    exact_binding_count: int
    maximum_binding_confidence: float | None
    maximum_distribution_quality: float | None
    points: tuple[CatalogPoint, ...]


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


def _stable_repo_ref(path: Path) -> str:
    resolved = Path(path).resolve()
    indexes = tuple(index for index, part in enumerate(resolved.parts) if part == "policy-engine")
    if indexes:
        relative = Path(*resolved.parts[indexes[-1] + 1 :])
        return f"repo://{relative.as_posix()}"
    return resolved.as_posix()


def _read_registry(
    path: Path,
) -> tuple[
    TransformFamilyRegistry,
    dict[tuple[str, str], data_forge_read_api.catalog.CatalogSelectionPolicyConfig],
    str,
]:
    try:
        owner = data_forge_read_api.catalog.load_derivation_catalog_selection(path)
        registry = load_transform_family_registry({"families": owner.families_payload})
    except (ValueError, data_forge_read_api.catalog.CatalogSelectionError) as exc:
        raise UniversalityProofError("derivation_owner_invalid", str(exc)) from exc
    policies = data_forge_read_api.catalog.catalog_selection_policies_for_purpose(
        owner,
        purpose="universality_proof",
    )
    family_ids = tuple(
        sorted((family.family_id, family.method_version) for family in registry.families)
    )
    policy_ids = tuple(sorted((policy.family_id, policy.method_version) for policy in policies))
    if family_ids != policy_ids:
        raise UniversalityProofError(
            "universality_policy_family_not_one_to_one",
            f"families={family_ids}/policies={policy_ids}",
        )
    return (
        registry,
        {(policy.family_id, policy.method_version): policy for policy in policies},
        owner.source_sha256,
    )


def _read_epoch_zero_series(
    catalog_path: Path,
    *,
    country_code: str,
) -> tuple[_RawSeries, ...]:
    with duckdb.connect(str(catalog_path), read_only=True) as connection:
        rows = connection.execute(
            """
            WITH exact_bindings AS (
              SELECT b.dataset_id, b.request_dataset_id AS raw_variable,
                     b.metric_id,
                     count(DISTINCT b.distribution_id) AS exact_binding_count,
                     max(b.confidence) AS maximum_binding_confidence,
                     max(d.quality_score) AS maximum_distribution_quality
              FROM ds_metric_bindings AS b
              JOIN ds_distributions AS d
                ON d.id = b.distribution_id AND d.dataset_id = b.dataset_id
              GROUP BY b.dataset_id, b.request_dataset_id, b.metric_id
            )
            SELECT o.dataset_id, coalesce(ds.source, ''), coalesce(ds.agency, ''),
                   ds.title, coalesce(ds.description, ''),
                   coalesce(nullif(ds.access_license, ''), ds.license, ''),
                   o.raw_variable, o.canonical_var,
                   a.method, a.confidence, a.is_proxy, a.proxy_penalty,
                   coalesce(b.exact_binding_count, 0),
                   b.metric_id, b.maximum_binding_confidence, b.maximum_distribution_quality,
                   o.observation_id, o.year, o.value, o.source_watermark,
                   o.dataset_version, o.acquisition_method
            FROM ds_observations AS o
            JOIN ds_datasets AS ds ON ds.id = o.dataset_id
            LEFT JOIN ds_variable_alignments AS a
              ON a.dataset_id = o.dataset_id
             AND a.raw_variable = o.raw_variable
             AND a.canonical_var = o.canonical_var
            LEFT JOIN exact_bindings AS b
              ON b.dataset_id = o.dataset_id
             AND b.raw_variable = o.raw_variable
             AND b.metric_id = o.canonical_var
            WHERE o.country_code = ? AND o.year IS NOT NULL AND o.value IS NOT NULL
            ORDER BY o.dataset_id, o.raw_variable, o.canonical_var,
                     o.year, o.observation_id
            """,
            [country_code],
        ).fetchall()
    grouped: dict[tuple[str, str, str], list[tuple[object, ...]]] = {}
    for row in rows:
        key = (str(row[0]), str(row[6]), str(row[7]))
        grouped.setdefault(key, []).append(row)
    series: list[_RawSeries] = []
    for key, group in sorted(grouped.items()):
        first = group[0]
        points = tuple(
            CatalogPoint(
                observation_id=str(row[16]),
                year=int(row[17]),
                value=Decimal(str(row[18])),
                source_watermark=str(row[19] or ""),
                dataset_version=str(row[20] or ""),
                acquisition_method=str(row[21] or ""),
            )
            for row in group
        )
        series.append(
            _RawSeries(
                dataset_id=key[0],
                source=str(first[1] or "unknown"),
                agency=str(first[2] or "unknown"),
                title=str(first[3]),
                description=str(first[4]),
                access_license=str(first[5]),
                raw_variable=key[1],
                canonical_variable=key[2],
                alignment_method=None if first[8] is None else str(first[8]),
                alignment_confidence=None if first[9] is None else float(first[9]),
                alignment_is_proxy=None if first[10] is None else bool(first[10]),
                alignment_proxy_penalty=None if first[11] is None else float(first[11]),
                exact_binding_count=int(first[12]),
                maximum_binding_confidence=(None if first[14] is None else float(first[14])),
                maximum_distribution_quality=(None if first[15] is None else float(first[15])),
                metric_id=None if first[13] is None else str(first[13]),
                points=points,
            )
        )
    if not series:
        raise UniversalityProofError("epoch_zero_denominator_empty", country_code)
    return tuple(series)


def _constraint_rejections(
    spec: TransformInputSpec,
    points: Sequence[CatalogPoint],
) -> set[str]:
    codes: set[str] = set()
    for constraint in spec.value_constraints:
        values = tuple(point.value for point in points)
        valid = {
            "nonnegative": all(value >= 0 for value in values),
            "nonzero": all(value != 0 for value in values),
            "positive": all(value > 0 for value in values),
        }[constraint]
        if not valid:
            codes.add(f"value_constraint:{constraint}")
    return codes


def _candidate_rejections(
    raw: _RawSeries,
    spec: TransformInputSpec,
    *,
    shared_codes: Sequence[str],
) -> tuple[str, ...]:
    codes = set(shared_codes)
    codes.update(_constraint_rejections(spec, raw.points))
    return tuple(sorted(codes))


def _disposition(
    raw: _RawSeries,
    *,
    family: TransformFamily,
    spec: TransformInputSpec,
    policy: data_forge_read_api.catalog.CatalogSelectionRoleConfig,
) -> CatalogCandidate:
    derived_unit = data_forge_read_api.catalog.derive_catalog_unit_from_text(
        f"{raw.title} {raw.description}"
    )
    shared = data_forge_read_api.catalog.evaluate_catalog_selection_candidate(
        policy,
        data_forge_read_api.catalog.CatalogSelectionCandidateEvidence(
            candidate_kind="local_series",
            catalog_unit=derived_unit,
            metric_id=raw.metric_id,
            canonical_variable=raw.canonical_variable,
            title=raw.title,
            description=raw.description,
            access_license=raw.access_license,
            alignment_method=raw.alignment_method,
            alignment_confidence=raw.alignment_confidence,
            alignment_is_proxy=raw.alignment_is_proxy,
            alignment_proxy_penalty=raw.alignment_proxy_penalty,
            exact_binding_count=raw.exact_binding_count,
            maximum_binding_confidence=raw.maximum_binding_confidence,
            maximum_distribution_quality=raw.maximum_distribution_quality,
            point_count=len(raw.points),
            distinct_year_count=len({point.year for point in raw.points}),
            duplicate_year_count=len(raw.points) - len({point.year for point in raw.points}),
            source_watermark_count=sum(
                bool(point.source_watermark.strip()) for point in raw.points
            ),
            dataset_version_count=sum(bool(point.dataset_version.strip()) for point in raw.points),
            acquisition_method_count=sum(
                bool(point.acquisition_method.strip()) for point in raw.points
            ),
        ),
    )
    rejection_codes = _candidate_rejections(
        raw,
        spec,
        shared_codes=tuple(code.value for code in shared.rejection_codes),
    )
    authority = None if shared.authority_score is None else Decimal(str(shared.authority_score))
    payload: dict[str, object] = {
        "family_id": family.family_id,
        "method_version": family.method_version,
        "role": spec.role,
        "required_basis": spec.basis,
        "dataset_id": raw.dataset_id,
        "source": raw.source,
        "agency": raw.agency,
        "title": raw.title,
        "description": raw.description,
        "access_license": raw.access_license,
        "raw_variable": raw.raw_variable,
        "metric_id": raw.metric_id,
        "canonical_variable": raw.canonical_variable,
        "derived_unit": derived_unit,
        "alignment_method": raw.alignment_method,
        "alignment_confidence": raw.alignment_confidence,
        "alignment_is_proxy": raw.alignment_is_proxy,
        "alignment_proxy_penalty": raw.alignment_proxy_penalty,
        "exact_binding_count": raw.exact_binding_count,
        "maximum_binding_confidence": raw.maximum_binding_confidence,
        "maximum_distribution_quality": raw.maximum_distribution_quality,
        "semantic_alignment_score": shared.semantic_alignment_score,
        "points": raw.points,
        "rejection_codes": rejection_codes,
        "eligible": not rejection_codes,
        "authority_score": authority,
    }
    return CatalogCandidate(
        **payload,
        projection_sha256=content_sha256(_json_values(payload)),
    )


def _json_values(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _json_values(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_values(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    return value


def _candidate_rank(candidate: CatalogCandidate) -> tuple[object, ...]:
    evaluation = data_forge_read_api.catalog.CatalogSelectionCandidateEvaluation(
        rejection_codes=(),
        eligible=True,
        semantic_alignment_score=candidate.semantic_alignment_score,
        authority_score=(
            None if candidate.authority_score is None else float(candidate.authority_score)
        ),
        reference_value=None,
    )
    return data_forge_read_api.catalog.catalog_selection_candidate_rank(
        evaluation,
        identity=(candidate.dataset_id, candidate.raw_variable, candidate.canonical_variable),
    )


def _select_family_inputs(
    family: TransformFamily,
    policy: data_forge_read_api.catalog.CatalogSelectionPolicyConfig,
    raw_series: Sequence[_RawSeries],
) -> tuple[RoleSelectionProof, ...]:
    specs = {spec.role: spec for spec in family.input_specs}
    if set(specs) != {role.role for role in policy.roles}:
        raise UniversalityProofError(
            "universality_policy_role_contract_drift",
            family.family_id,
        )
    dispositions: dict[str, tuple[CatalogCandidate, ...]] = {}
    by_years: dict[str, dict[tuple[int, ...], list[CatalogCandidate]]] = {}
    for spec in family.input_specs:
        candidates = tuple(
            _disposition(
                raw,
                family=family,
                spec=spec,
                policy=policy.role_policy(spec.role),
            )
            for raw in raw_series
        )
        eligible = tuple(item for item in candidates if item.eligible)
        if not eligible:
            raise UniversalityProofError(
                "family_role_inputs_inadmissible",
                f"{family.family_id}/{spec.role}/{len(candidates)}",
            )
        dispositions[spec.role] = candidates
        grouped: dict[tuple[int, ...], list[CatalogCandidate]] = {}
        for candidate in eligible:
            years = tuple(point.year for point in candidate.points)
            grouped.setdefault(years, []).append(candidate)
        by_years[spec.role] = grouped
    shared_year_sets = set.intersection(*(set(groups) for groups in by_years.values()))
    shared_year_sets = {years for years in shared_year_sets if len(years) >= 2}
    if not shared_year_sets:
        raise UniversalityProofError(
            "family_exact_year_set_missing",
            family.family_id,
        )
    selections_by_years: list[
        tuple[tuple[object, ...], tuple[int, ...], dict[str, CatalogCandidate]]
    ] = []
    for years in shared_year_sets:
        selected = {
            role: sorted(groups[years], key=_candidate_rank)[0] for role, groups in by_years.items()
        }
        rank = (
            -sum(item.semantic_alignment_score for item in selected.values()),
            -min(item.authority_score or Decimal("0") for item in selected.values()),
            -len(years),
            years,
            tuple(item.projection_sha256 for _, item in sorted(selected.items())),
        )
        selections_by_years.append((rank, years, selected))
    _, exact_years, selected = sorted(selections_by_years, key=lambda item: item[0])[0]
    proofs: list[RoleSelectionProof] = []
    for spec in family.input_specs:
        candidates = dispositions[spec.role]
        rejection_counts = Counter(
            code for candidate in candidates for code in candidate.rejection_codes
        )
        denominator_payload = [candidate.model_dump(mode="json") for candidate in candidates]
        proofs.append(
            RoleSelectionProof(
                family_id=family.family_id,
                method_version=family.method_version,
                role=spec.role,
                required_basis=spec.basis,
                denominator_count=len(candidates),
                denominator_sha256=content_sha256(denominator_payload),
                rejection_counts=tuple(
                    RejectionCount(code=code, count=count)
                    for code, count in sorted(rejection_counts.items())
                ),
                eligible_count=sum(item.eligible for item in candidates),
                selected=selected[spec.role],
                exact_years=exact_years,
            )
        )
    return tuple(sorted(proofs, key=lambda item: item.role))


def _evidence_options() -> artifacts.PutOptions:
    return artifacts.PutOptions(
        kind=_EVIDENCE_KIND,
        media_type="application/json",
        schema=_EVIDENCE_SCHEMA,
        producer=_SOURCE_PRODUCER,
    )


def _authority_for_selection(
    store: artifacts.FileSystemCAS,
    *,
    selection: RoleSelectionProof,
    catalog_sha256: str,
) -> AuthorityProjection:
    score = selection.selected.authority_score
    if score is None:
        raise UniversalityProofError(
            "selected_input_authority_missing",
            f"{selection.family_id}/{selection.role}",
        )
    authority_payload = {
        "schema_version": UNIVERSALITY_SCHEMA_VERSION,
        "evidence_class": "owner_admissible_epoch_zero_series",
        "catalog_sha256": catalog_sha256,
        "family_id": selection.family_id,
        "method_version": selection.method_version,
        "role": selection.role,
        "selected_projection_sha256": selection.selected.projection_sha256,
        "denominator_sha256": selection.denominator_sha256,
        "effective_score": str(score),
    }
    authority_ref = store.put_bytes(
        canonical_json_bytes(authority_payload),
        _evidence_options(),
    )
    verifier_payload = {
        "schema_version": UNIVERSALITY_SCHEMA_VERSION,
        "evidence_class": "owner_validation_verifier",
        "catalog_sha256": catalog_sha256,
        "authority_artifact_id": str(authority_ref.artifact_id),
        "decisive_checks": [
            "alignment_owner_resolved",
            "binding_owner_resolved",
            "full_denominator_classified",
            "license_owner_admissible",
            "source_watermark_complete",
        ],
    }
    verifier_ref = store.put_bytes(
        canonical_json_bytes(verifier_payload),
        _evidence_options(),
    )
    return AuthorityProjection(
        effective_score=score,
        authority_ref=authority_ref.artifact_id,
        verifier_provenance_ref=verifier_ref.artifact_id,
        authoritative_for="series_input",
    )


def _persist_family_inputs(
    store: artifacts.FileSystemCAS,
    *,
    selections: Sequence[RoleSelectionProof],
    catalog_sha256: str,
) -> dict[str, artifacts.ArtifactRef]:
    refs: dict[str, artifacts.ArtifactRef] = {}
    for selection in selections:
        source = SourceSeries(
            variable_id=(
                f"epoch0.{selection.selected.canonical_variable}.{selection.selected.raw_variable}"
            ),
            basis=selection.required_basis,
            points=tuple(
                SeriesPoint(year=point.year, value=point.value)
                for point in selection.selected.points
            ),
            authority=_authority_for_selection(
                store,
                selection=selection,
                catalog_sha256=catalog_sha256,
            ),
            observation_class="observed",
        )
        refs[selection.role] = persist_source_series(
            store,
            source,
        )
    return refs


@dataclass(frozen=True)
class _Execution:
    recipe: DerivationRecipe
    certificate: DerivationCertificate
    certificate_artifact_id: str
    derived_artifact_id: str
    first_cache_hit: bool
    second_cache_hit: bool
    consumers: tuple[CertifiedDerivationConsumption, CertifiedDerivationConsumption]


def _execute_family(
    store: artifacts.FileSystemCAS,
    *,
    registry: TransformFamilyRegistry,
    family: TransformFamily,
    selections: Sequence[RoleSelectionProof],
    catalog_sha256: str,
) -> _Execution:
    refs = _persist_family_inputs(
        store,
        selections=selections,
        catalog_sha256=catalog_sha256,
    )
    recipe = build_derivation_recipe(
        store,
        registry=registry,
        input_refs=refs,
        output_variable_id=f"derived.{family.family_id}",
        family_id=family.family_id,
        method_version=family.method_version,
    )
    first = materialize_derivation(store, recipe)
    second = materialize_derivation(store, recipe)
    consumers = tuple(
        consume_certified_derivation(
            store,
            certificate_ref=second.certificate_artifact_ref,
            consumer_method_id=method_id,
        )
        for method_id in (
            "universality.audit.consumer.a@1.0.0",
            "universality.audit.consumer.b@1.0.0",
        )
    )
    return _Execution(
        recipe=recipe,
        certificate=second.certificate,
        certificate_artifact_id=str(second.certificate_artifact_ref.artifact_id),
        derived_artifact_id=str(second.derived_artifact_ref.artifact_id),
        first_cache_hit=first.cache_hit,
        second_cache_hit=second.cache_hit,
        consumers=(consumers[0], consumers[1]),
    )


def _execution_identity(execution: _Execution) -> dict[str, object]:
    return {
        "recipe": execution.recipe.model_dump(mode="json"),
        "certificate": execution.certificate.model_dump(mode="json"),
        "certificate_artifact_id": execution.certificate_artifact_id,
        "derived_artifact_id": execution.derived_artifact_id,
        "consumers": [item.model_dump(mode="json") for item in execution.consumers],
    }


def _family_proof(
    *,
    registry: TransformFamilyRegistry,
    family: TransformFamily,
    selections: tuple[RoleSelectionProof, ...],
    catalog_sha256: str,
    temporary_root: Path,
) -> FamilyExecutionProof:
    first_store = artifacts.FileSystemCAS(temporary_root / "first")
    rebuild_store = artifacts.FileSystemCAS(temporary_root / "rebuild")
    execution = _execute_family(
        first_store,
        registry=registry,
        family=family,
        selections=selections,
        catalog_sha256=catalog_sha256,
    )
    rebuild = _execute_family(
        rebuild_store,
        registry=registry,
        family=family,
        selections=selections,
        catalog_sha256=catalog_sha256,
    )
    if execution.first_cache_hit or rebuild.first_cache_hit:
        raise UniversalityProofError("cold_cache_materialization_was_hit", family.family_id)
    if not execution.second_cache_hit or not rebuild.second_cache_hit:
        raise UniversalityProofError("second_materialization_was_not_hit", family.family_id)
    rebuild_equal = _execution_identity(execution) == _execution_identity(rebuild)
    if not rebuild_equal:
        raise UniversalityProofError("fresh_cas_rebuild_drift", family.family_id)
    weakest = min(selection.selected.authority_score or Decimal("0") for selection in selections)
    values: dict[str, object] = {
        "family_id": family.family_id,
        "method_version": family.method_version,
        "family_projection_sha256": content_sha256(family.model_dump(mode="json")),
        "selections": selections,
        "recipe": execution.recipe,
        "recipe_sha256": content_sha256(execution.recipe.model_dump(mode="json")),
        "certificate": execution.certificate,
        "certificate_artifact_id": execution.certificate_artifact_id,
        "derived_artifact_id": execution.derived_artifact_id,
        "first_materialization_cache_hit": False,
        "second_materialization_cache_hit": True,
        "fresh_cas_rebuild_equal": True,
        "consumers": execution.consumers,
        "weakest_input_authority": weakest,
        "derived_authority": execution.certificate.effective_authority,
        "monotone_authority_proven": True,
        "derived_passport_rejection_codes": derive_observation_provenance_rejections(
            ObservationProvenanceClass.DERIVED
        ),
        "model_output_passport_rejection_codes": (
            derive_observation_provenance_rejections(ObservationProvenanceClass.MODEL_OUTPUT)
        ),
    }
    return FamilyExecutionProof(
        **values,
        proof_sha256=content_sha256(_json_values(values)),
    )


def _prove_unregistered_basis_refusal(
    *,
    registry: TransformFamilyRegistry,
    family: TransformFamily,
    selections: Sequence[RoleSelectionProof],
    catalog_sha256: str,
    temporary_root: Path,
) -> tuple[str, str]:
    store = artifacts.FileSystemCAS(temporary_root / "unregistered")
    refs = _persist_family_inputs(
        store,
        selections=selections,
        catalog_sha256=catalog_sha256,
    )
    unregistered = BasisSignature(
        quantity_kind=f"{family.output_basis.quantity_kind}.unregistered",
        unit=family.output_basis.unit,
        attributes=family.output_basis.attributes,
    )
    try:
        build_derivation_recipe(
            store,
            registry=registry,
            input_refs=refs,
            output_variable_id="derived.unregistered",
            output_basis=unregistered,
        )
    except DerivationRefusalError as exc:
        if (
            exc.code is not DerivationRefusalCode.BASIS_MISMATCH
            or exc.reason is not DerivationRefusalReason.NO_CERTIFIED_TRANSFORM
        ):
            raise
        return exc.code.value, exc.reason.value
    raise UniversalityProofError("unregistered_basis_was_accepted")


def build_derivation_universality_receipt(
    *,
    catalog_path: Path,
    registry_path: Path = DEFAULT_DERIVATION_FAMILY_REGISTRY,
    country_code: str = "UA",
) -> DerivationUniversalityReceipt:
    """Recompute every proof from immutable epoch-zero data, without network I/O."""

    baseline_before = _file_sha256(catalog_path)
    registry, policies, registry_sha256 = _read_registry(registry_path)
    if any(policy.country_code != country_code for policy in policies.values()):
        raise UniversalityProofError("universality_policy_country_drift", country_code)
    raw_series = _read_epoch_zero_series(catalog_path, country_code=country_code)
    family_proofs: list[FamilyExecutionProof] = []
    refusal: tuple[str, str] | None = None
    with tempfile.TemporaryDirectory(prefix="polisyos-n13b-universality-") as root:
        temporary_root = Path(root)
        for index, family in enumerate(
            sorted(
                registry.families,
                key=lambda item: (item.family_id, item.method_version),
            )
        ):
            selections = _select_family_inputs(
                family,
                policies[(family.family_id, family.method_version)],
                raw_series,
            )
            family_proofs.append(
                _family_proof(
                    registry=registry,
                    family=family,
                    selections=selections,
                    catalog_sha256=baseline_before,
                    temporary_root=temporary_root / f"family-{index}",
                )
            )
            if refusal is None:
                refusal = _prove_unregistered_basis_refusal(
                    registry=registry,
                    family=family,
                    selections=selections,
                    catalog_sha256=baseline_before,
                    temporary_root=temporary_root,
                )
    if refusal is None:
        raise UniversalityProofError("registry_family_denominator_empty")
    baseline_after = _file_sha256(catalog_path)
    values: dict[str, object] = {
        "schema_version": UNIVERSALITY_SCHEMA_VERSION,
        "registry_ref": _stable_repo_ref(registry_path),
        "registry_sha256": registry_sha256,
        "catalog_ref": _stable_repo_ref(catalog_path),
        "catalog_sha256_before": baseline_before,
        "catalog_sha256_after": baseline_after,
        "source_epoch": 0,
        "country_code": country_code,
        "full_series_denominator_count": len(raw_series),
        "family_count": len(family_proofs),
        "family_proofs": tuple(family_proofs),
        "unregistered_basis_refusal_code": refusal[0],
        "unregistered_basis_refusal_reason": refusal[1],
        "network_call_count": 0,
    }
    return DerivationUniversalityReceipt(
        **values,
        receipt_sha256=content_sha256(_json_values(values)),
    )


def write_derivation_universality_receipt(
    receipt: DerivationUniversalityReceipt,
    *,
    output_path: Path = DEFAULT_UNIVERSALITY_RECEIPT,
) -> None:
    """Write one byte-stable receipt; timestamps remain outside content identity."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(derivation_universality_bytes(receipt))


def derivation_universality_bytes(receipt: DerivationUniversalityReceipt) -> bytes:
    """Serialize one receipt through the sole canonical byte owner."""

    return canonical_json_bytes(receipt.model_dump(mode="json"))


def parse_derivation_universality_receipt(path: Path) -> DerivationUniversalityReceipt:
    """Parse and revalidate one frozen universality receipt."""

    return DerivationUniversalityReceipt.model_validate(
        json.loads(path.read_text(encoding="utf-8"))
    )


__all__ = [
    "DEFAULT_DERIVATION_FAMILY_REGISTRY",
    "DEFAULT_UNIVERSALITY_RECEIPT",
    "UNIVERSALITY_SCHEMA_VERSION",
    "CatalogCandidate",
    "CatalogPoint",
    "DerivationUniversalityReceipt",
    "FamilyExecutionProof",
    "RejectionCount",
    "RoleSelectionProof",
    "UniversalityProofError",
    "build_derivation_universality_receipt",
    "derivation_universality_bytes",
    "parse_derivation_universality_receipt",
    "write_derivation_universality_receipt",
]
