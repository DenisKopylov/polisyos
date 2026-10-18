"""D6 catalog candidate and certified-transform admission owners."""

from __future__ import annotations

import json
import tomllib
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, Self

import duckdb
from pydantic import Field, model_validator

from polisyos.data_forge import read_api as data_forge_read_api
from polisyos.data_forge.domains.catalog.knowledge.variable_alignment import (
    VariablePairAlignmentScore,  # noqa: TC001 - Pydantic resolves this at runtime.
)
from polisyos.data_forge.read_api.catalog import (
    CatalogSelectionCandidateEvidence,
    CatalogSelectionPolicyConfig,
    CatalogSelectionRoleConfig,
)
from polisyos.fabric.data_plane import canonical_json_bytes, content_sha256
from polisyos.runtime.quality.derived_observations import (
    BasisSignature,
    DerivationRefusalCode,
    DerivationRefusalReason,
    TransformFamily,
    TransformFamilyRegistry,
    TransformInputSpec,
    load_transform_family_registry,
)

from .acquisition_executor_support import (
    _json_object,
    _string_values,
)
from .acquisition_response_receipts import (
    AcquisitionSelectionError,
    _StrictModel,
)


class D6CatalogCarrier(_StrictModel):
    """One catalog-owned carrier scored for a single certified D6 transform role."""

    role: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    distribution_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    request_dataset_id: str = Field(min_length=1)
    metric_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    agency: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str
    themes: tuple[str, ...]
    access_license: str = Field(min_length=1)
    execution_tier: Literal["fetchable", "transport_ready"]
    binding_confidence: float = Field(ge=0.0, le=1.0)
    distribution_quality_score: float = Field(ge=0.0, le=1.0)
    unit: str = Field(min_length=1)
    basis: BasisSignature | None = None
    connector_params: dict[str, Any]
    default_filters: dict[str, list[str]]
    source_selector_declared: bool
    identifier_anchor: str = Field(min_length=1)
    title_anchor: str = Field(min_length=1)
    anchor_unit: str = Field(min_length=1)
    identifier_alignment: VariablePairAlignmentScore
    title_alignment: VariablePairAlignmentScore
    rank_score: float = Field(ge=0.0)
    projection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _carrier_projection_is_recomputed(self) -> Self:
        if self.themes != tuple(sorted(set(self.themes))):
            raise ValueError("D6 carrier themes must be unique and sorted")
        owner_unit = data_forge_read_api.catalog.derive_catalog_unit_from_text(
            f"{self.title} {self.description}"
        )
        if owner_unit != self.unit:
            raise ValueError("D6 carrier unit must be recomputed from catalog text")
        expected_selector = any(
            key.casefold() in {"source", "source_id"}
            for mapping in (self.connector_params, self.default_filters)
            for key in mapping
        )
        if self.source_selector_declared != expected_selector:
            raise ValueError("D6 source-selector status must derive from catalog config")
        identifier_alignment = data_forge_read_api.catalog.score_variable_pair(
            left_name=self.identifier_anchor,
            right_name=self.request_dataset_id,
            left_unit=self.anchor_unit,
            right_unit=self.unit,
        )
        title_alignment = data_forge_read_api.catalog.score_variable_pair(
            left_name=self.title_anchor,
            right_name=self.title,
            left_unit=self.anchor_unit,
            right_unit=self.unit,
        )
        if (
            self.identifier_alignment != identifier_alignment
            or self.title_alignment != title_alignment
        ):
            raise ValueError("D6 carrier alignment must be recomputed by its owner")
        expected_rank = round(
            identifier_alignment.overall_score + title_alignment.overall_score,
            6,
        )
        if abs(self.rank_score - expected_rank) > 1e-9:
            raise ValueError("D6 carrier rank must derive from owner alignment scores")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("D6 carrier projection identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the narrow catalog/score projection without its self-hash."""

        return {
            key: value
            for key, value in self.model_dump(mode="json", exclude_none=True).items()
            if key != "projection_sha256"
        }


class D6RouteSelection(_StrictModel):
    """Evidence-derived one-transform route from a paid basis mismatch."""

    schema_version: Literal[
        "policyos.layer3.gy.n13b.d6_route_selection.v1",
        "policyos.layer3.gy.n13b.d6_route_selection.v2",
    ] = "policyos.layer3.gy.n13b.d6_route_selection.v2"
    baseline_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    census_backlog_projection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    substrate_slot_projection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    r1_receipt_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    carrier_liveness_receipt_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    target_variable: str = Field(min_length=1)
    backlog_rank: int = Field(ge=1)
    demand_sources: tuple[str, ...] = Field(min_length=1)
    required_output_unit: str = Field(min_length=1)
    failed_request_dataset_id: str = Field(min_length=1)
    failed_metric_id: str = Field(min_length=1)
    failed_catalog_title: str | None = Field(default=None, min_length=1)
    failed_catalog_unit: str | None = Field(default=None, min_length=1)
    failed_carrier_disposition: Literal[
        "carrier_current_no_data_for_scope",
        "carrier_current_source_profile_mismatch",
        "carrier_retired_or_invalid",
    ]
    failed_missing_request_levers: tuple[str, ...]
    route_disposition: Literal["derivation_requirement"]
    transform_method_id: str = Field(min_length=1)
    transform_method_version: str = Field(min_length=1)
    transform_formula: str = Field(min_length=1)
    transform_family: TransformFamily | None = None
    transform_family_projection_sha256: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    transform_registry_projection_sha256: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    selection_policy: CatalogSelectionPolicyConfig | None = None
    selection_policy_projection_sha256: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    primary_catalog_denominator: int = Field(ge=1)
    primary_candidate_denominator: int = Field(ge=1)
    primary_rejected_counts: dict[str, int]
    auxiliary_catalog_denominator: int = Field(ge=1)
    auxiliary_candidate_denominator: int = Field(ge=1)
    auxiliary_rejected_counts: dict[str, int]
    primary: D6CatalogCarrier
    auxiliary: D6CatalogCarrier
    primary_requires_source_characterization: bool
    selection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _route_is_recomputed(self) -> Self:
        if self.demand_sources != tuple(sorted(set(self.demand_sources))):
            raise ValueError("D6 demand sources must be unique and sorted")
        if any(value < 0 for value in self.primary_rejected_counts.values()):
            raise ValueError("D6 primary rejection counts must be nonnegative")
        if any(value < 0 for value in self.auxiliary_rejected_counts.values()):
            raise ValueError("D6 auxiliary rejection counts must be nonnegative")
        if (
            self.primary_candidate_denominator + sum(self.primary_rejected_counts.values())
            != self.primary_catalog_denominator
            or self.auxiliary_candidate_denominator + sum(self.auxiliary_rejected_counts.values())
            != self.auxiliary_catalog_denominator
        ):
            raise ValueError("D6 candidate outcomes must cover both complete denominators")
        generic_fields = (
            self.failed_catalog_title,
            self.failed_catalog_unit,
            self.transform_family,
            self.transform_family_projection_sha256,
            self.transform_registry_projection_sha256,
            self.selection_policy,
            self.selection_policy_projection_sha256,
        )
        if self.schema_version.endswith(".v1"):
            if any(value is not None for value in generic_fields):
                raise ValueError("legacy D6 routes cannot carry partial generic owner data")
            if self.selection_sha256 != content_sha256(self.identity_payload()):
                raise ValueError("D6 route selection identity must be recomputed")
            return self
        if any(value is None for value in generic_fields):
            raise ValueError("generic D6 routes require complete family and policy owner data")
        assert self.failed_catalog_title is not None
        assert self.failed_catalog_unit is not None
        assert self.transform_family is not None
        assert self.transform_family_projection_sha256 is not None
        assert self.transform_registry_projection_sha256 is not None
        assert self.selection_policy is not None
        assert self.selection_policy_projection_sha256 is not None
        family = self.transform_family
        policy = self.selection_policy
        if family.family_id != policy.family_id:
            raise ValueError("D6 route family must derive from selection policy")
        if family.method_version != policy.method_version:
            raise ValueError("D6 route method version must derive from selection policy")
        specs = {item.role: item for item in family.input_specs}
        if set(specs) != {item.role for item in policy.roles}:
            raise ValueError("D6 route policy must cover the selected transform family")
        try:
            primary_policy, auxiliary_policy = _d6_failed_and_auxiliary_roles(
                policy,
                self.failed_metric_id,
            )
        except (ValueError, data_forge_read_api.catalog.CatalogSelectionError) as exc:
            raise ValueError("D6 paid carrier must select one transform input role") from exc
        primary_values = _resolve_d6_catalog_role_policy(
            primary_policy,
            is_failed_carrier=True,
            failed_metric_id=self.failed_metric_id,
            failed_request_dataset_id=self.failed_request_dataset_id,
            failed_catalog_title=self.failed_catalog_title,
            failed_catalog_unit=self.failed_catalog_unit,
        )
        auxiliary_values = _resolve_d6_catalog_role_policy(
            auxiliary_policy,
            is_failed_carrier=False,
            failed_metric_id=self.failed_metric_id,
            failed_request_dataset_id=self.failed_request_dataset_id,
            failed_catalog_title=self.failed_catalog_title,
            failed_catalog_unit=self.failed_catalog_unit,
        )
        if (
            self.required_output_unit != family.output_basis.unit
            or self.required_output_unit != self.failed_catalog_unit
            or self.transform_method_id != family.method_id
            or self.transform_method_version != family.method_version
            or self.transform_formula != _d6_transform_formula(family)
            or self.transform_family_projection_sha256
            != content_sha256(family.model_dump(mode="json"))
            or self.selection_policy_projection_sha256
            != content_sha256(policy.model_dump(mode="json"))
            or not _d6_carrier_matches_role(
                self.primary,
                role=primary_policy.role,
                role_spec=specs[primary_policy.role],
                role_policy=primary_policy,
                resolved_policy=primary_values,
            )
            or not _d6_carrier_matches_role(
                self.auxiliary,
                role=auxiliary_policy.role,
                role_spec=specs[auxiliary_policy.role],
                role_policy=auxiliary_policy,
                resolved_policy=auxiliary_values,
            )
        ):
            raise ValueError("D6 transform edge must recompute from family and policy data")
        expected_characterization = _d6_requires_source_characterization(
            self.primary,
            primary_policy,
        )
        if self.primary_requires_source_characterization != expected_characterization:
            raise ValueError("D6 primary characterization gate must derive from source owners")
        if self.selection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("D6 route selection identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the projection defining the D6 route selection."""

        return {
            key: value
            for key, value in self.model_dump(mode="json", exclude_none=True).items()
            if key != "selection_sha256"
        }


def _read_d6_catalog_denominator(
    catalog_path: Path,
    *,
    connector_id: str,
    metric_id: str,
) -> tuple[dict[str, object], ...]:
    """Return every catalog row in one D6 role denominator, before filtering."""

    with duckdb.connect(str(catalog_path), read_only=True) as con:
        rows = con.execute(
            """
            SELECT b.dataset_id, b.distribution_id, b.connector_id, b.profile_id,
                   b.request_dataset_id, b.metric_id, b.confidence,
                   b.default_filters, b.execution_tier,
                   d.source, d.agency, d.title, d.description, d.themes,
                   d.access_license, d.access_auth_required,
                   x.connector_params, x.quality_score, x.parser_supported
            FROM ds_metric_bindings b
            JOIN ds_datasets d ON d.id = b.dataset_id
            JOIN ds_distributions x
              ON x.id = b.distribution_id AND x.dataset_id = b.dataset_id
            WHERE b.connector_id = ? AND b.metric_id = ?
            ORDER BY b.dataset_id, b.distribution_id, b.request_dataset_id
            """,
            [connector_id, metric_id],
        ).fetchall()
    if not rows:
        raise AcquisitionSelectionError(
            "d6_catalog_role_denominator_empty",
            f"{connector_id}:{metric_id}",
        )
    fields = (
        "dataset_id",
        "distribution_id",
        "connector_id",
        "profile_id",
        "request_dataset_id",
        "metric_id",
        "binding_confidence",
        "default_filters",
        "execution_tier",
        "source",
        "agency",
        "title",
        "description",
        "themes",
        "access_license",
        "access_auth_required",
        "connector_params",
        "distribution_quality_score",
        "parser_supported",
    )
    return tuple(dict(zip(fields, row, strict=True)) for row in rows)


def _load_d6_transform_registry(
    source: TransformFamilyRegistry | str | Path | Mapping[str, object],
) -> TransformFamilyRegistry:
    if isinstance(source, TransformFamilyRegistry):
        return TransformFamilyRegistry.model_validate(source.model_dump(mode="python"))
    payload: Mapping[str, object]
    if isinstance(source, Mapping):
        payload = source
    else:
        path = Path(source)
        try:
            if path.suffix.casefold() == ".json":
                raw = json.loads(path.read_bytes())
            else:
                raw = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
            raise AcquisitionSelectionError(
                "d6_transform_registry_invalid",
                path.as_posix(),
            ) from exc
        if not isinstance(raw, Mapping):
            raise AcquisitionSelectionError("d6_transform_registry_invalid", path.as_posix())
        payload = raw
    family_rows = payload.get("families")
    try:
        return load_transform_family_registry({"families": family_rows})
    except (TypeError, ValueError) as exc:
        raise AcquisitionSelectionError("d6_transform_registry_invalid") from exc


def _load_d6_selection_policy(
    source: CatalogSelectionPolicyConfig | str | Path | Mapping[str, object],
    *,
    failed_metric_id: str,
) -> CatalogSelectionPolicyConfig:
    if isinstance(source, CatalogSelectionPolicyConfig):
        policy = CatalogSelectionPolicyConfig.model_validate(source.model_dump(mode="python"))
        return _require_d6_policy_purpose(policy, failed_metric_id=failed_metric_id)
    payload: object
    if isinstance(source, Mapping):
        payload = source
    else:
        path = Path(source)
        try:
            if path.suffix.casefold() == ".json":
                payload = json.loads(path.read_bytes())
            else:
                payload = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
            raise AcquisitionSelectionError(
                "d6_selection_policy_invalid",
                path.as_posix(),
            ) from exc
    try:
        if isinstance(payload, Mapping) and "catalog_selection_policies" in payload:
            owner = data_forge_read_api.catalog.load_derivation_catalog_selection(payload)
            return data_forge_read_api.catalog.resolve_catalog_selection_policy(
                owner,
                purpose="d6_route",
                owner_metric_id=failed_metric_id,
            )
        policy = CatalogSelectionPolicyConfig.model_validate_json(canonical_json_bytes(payload))
        return _require_d6_policy_purpose(policy, failed_metric_id=failed_metric_id)
    except (
        TypeError,
        ValueError,
        data_forge_read_api.catalog.CatalogSelectionError,
    ) as exc:
        raise AcquisitionSelectionError("d6_selection_policy_invalid") from exc


def _require_d6_policy_purpose(
    policy: CatalogSelectionPolicyConfig,
    *,
    failed_metric_id: str,
) -> CatalogSelectionPolicyConfig:
    if "d6_route" not in policy.purposes:
        raise data_forge_read_api.catalog.CatalogSelectionError(
            "catalog_selection_policy_unresolved",
            f"purpose=d6_route/metric={failed_metric_id}/count=0",
        )
    policy.role_policy_for_owner_metric(failed_metric_id)
    return policy


def _d6_failed_and_auxiliary_roles(
    policy: CatalogSelectionPolicyConfig,
    failed_metric_id: str,
) -> tuple[CatalogSelectionRoleConfig, CatalogSelectionRoleConfig]:
    primary = policy.role_policy_for_owner_metric(failed_metric_id)
    auxiliary = tuple(item for item in policy.roles if item.role != primary.role)
    if len(auxiliary) != 1:
        raise ValueError("D6 transform requires exactly one auxiliary role")
    return primary, auxiliary[0]


def _resolve_d6_transform_family(
    registry: TransformFamilyRegistry,
    *,
    family_id: str,
    method_version: str,
) -> TransformFamily:
    families = tuple(
        family
        for family in registry.families
        if (family.family_id, family.method_version) == (family_id, method_version)
    )
    if len(families) != 1:
        _raise_d6_no_certified_transform(family_id)
    return families[0]


def _raise_d6_no_certified_transform(detail: str) -> None:
    raise AcquisitionSelectionError(
        DerivationRefusalCode.BASIS_MISMATCH.value,
        detail,
        reason=DerivationRefusalReason.NO_CERTIFIED_TRANSFORM.value,
    )


def _resolve_d6_catalog_role_policy(
    policy: CatalogSelectionRoleConfig,
    *,
    is_failed_carrier: bool,
    failed_metric_id: str,
    failed_request_dataset_id: str,
    failed_catalog_title: str,
    failed_catalog_unit: str,
) -> dict[str, str]:
    if is_failed_carrier:
        if policy.owner_metric_id != failed_metric_id:
            raise AcquisitionSelectionError("d6_failed_role_owner_metric_drift", policy.role)
        metric_id = failed_metric_id
        identifier_anchor = failed_request_dataset_id
        title_anchor = failed_catalog_title
        anchor_unit = failed_catalog_unit
    else:
        metric_id = policy.owner_metric_id
        identifier_anchor = policy.owner_metric_id
        title_anchor = policy.semantic_anchor
        anchor_unit = policy.catalog_unit
    return {
        "metric_id": metric_id,
        "identifier_anchor": identifier_anchor,
        "title_anchor": title_anchor,
        "anchor_unit": anchor_unit,
    }


def _d6_carrier_matches_role(
    carrier: D6CatalogCarrier,
    *,
    role: str,
    role_spec: TransformInputSpec,
    role_policy: CatalogSelectionRoleConfig,
    resolved_policy: Mapping[str, str],
) -> bool:
    return (
        carrier.role == role
        and carrier.metric_id == resolved_policy["metric_id"]
        and carrier.identifier_anchor == resolved_policy["identifier_anchor"]
        and carrier.title_anchor == resolved_policy["title_anchor"]
        and carrier.anchor_unit == resolved_policy["anchor_unit"]
        and carrier.unit == role_policy.catalog_unit
        and carrier.basis == role_spec.basis
    )


def _d6_requires_source_characterization(
    carrier: D6CatalogCarrier,
    policy: CatalogSelectionRoleConfig,
) -> bool:
    """Recompute the generic policy evidence that blocks direct source admission."""

    normalized_themes = tuple(theme.casefold() for theme in carrier.themes)
    return not carrier.source_selector_declared and any(
        fragment.casefold() in theme
        for fragment in policy.forbidden_theme_fragments
        for theme in normalized_themes
    )


def _d6_transform_formula(family: TransformFamily) -> str:
    """Project the family-owned arithmetic AST without interpreting vocabulary."""

    return canonical_json_bytes(family.expression.model_dump(mode="json")).decode().strip()


def _select_d6_carrier(
    *,
    rows: Sequence[Mapping[str, object]],
    role: str,
    role_policy: CatalogSelectionRoleConfig,
    required_basis: BasisSignature,
    identifier_anchor: str,
    title_anchor: str,
    anchor_unit: str,
) -> tuple[D6CatalogCarrier, Counter[str], int]:
    """Classify a complete role denominator and select its owner-scored carrier."""

    rejected: Counter[str] = Counter()
    candidates: list[
        tuple[
            D6CatalogCarrier,
            data_forge_read_api.catalog.CatalogSelectionCandidateEvaluation,
        ]
    ] = []
    for row in rows:
        execution_tier = str(row.get("execution_tier") or "")
        access_license = str(row.get("access_license") or "")
        title = str(row.get("title") or "")
        description = str(row.get("description") or "")
        unit = data_forge_read_api.catalog.derive_catalog_unit_from_text(f"{title} {description}")
        connector_params = _json_object(row.get("connector_params"))
        default_filters = _d6_filter_map(row.get("default_filters"))
        identifier_alignment = data_forge_read_api.catalog.score_variable_pair(
            left_name=identifier_anchor,
            right_name=str(row["request_dataset_id"]),
            left_unit=anchor_unit,
            right_unit=unit or "unresolved",
        )
        title_alignment = data_forge_read_api.catalog.score_variable_pair(
            left_name=title_anchor,
            right_name=title,
            left_unit=anchor_unit,
            right_unit=unit or "unresolved",
        )
        themes = tuple(sorted(set(_string_values(row.get("themes")))))
        binding_confidence = float(row.get("binding_confidence") or 0.0)
        distribution_quality = float(row.get("distribution_quality_score") or 0.0)
        evaluation = data_forge_read_api.catalog.evaluate_catalog_selection_candidate(
            role_policy,
            CatalogSelectionCandidateEvidence(
                candidate_kind="live_carrier",
                catalog_unit=unit,
                metric_id=str(row["metric_id"]),
                canonical_variable=str(row["metric_id"]),
                title=title,
                description=description,
                access_license=access_license,
                alignment_method="catalog_owner_scored",
                alignment_confidence=min(
                    identifier_alignment.overall_score,
                    title_alignment.overall_score,
                ),
                alignment_is_proxy=False,
                alignment_proxy_penalty=0.0,
                exact_binding_count=1,
                maximum_binding_confidence=binding_confidence,
                maximum_distribution_quality=distribution_quality,
                connector_id=str(row["connector_id"]),
                execution_tier=execution_tier,
                access_auth_required=bool(row.get("access_auth_required")),
                parser_supported=bool(row.get("parser_supported")),
                themes=themes,
            ),
        )
        decisive_codes = {
            code.value
            for code in evaluation.rejection_codes
            if code
            is not data_forge_read_api.catalog.CatalogSelectionRejectionCode.FORBIDDEN_THEME_PRESENT
        }
        if decisive_codes:
            # The route receipt is a row denominator, so every rejected carrier
            # receives exactly one stable terminal disposition.  Additional
            # failed checks remain available in the owner evaluation and must
            # not inflate the denominator by being counted as extra rows.
            rejected[min(decisive_codes)] += 1
            continue
        values: dict[str, object] = {
            "role": role,
            "dataset_id": str(row["dataset_id"]),
            "distribution_id": str(row["distribution_id"]),
            "connector_id": str(row["connector_id"]),
            "profile_id": str(row["profile_id"]),
            "request_dataset_id": str(row["request_dataset_id"]),
            "metric_id": str(row["metric_id"]),
            "source": str(row.get("source") or ""),
            "agency": str(row.get("agency") or ""),
            "title": title,
            "description": description,
            "themes": themes,
            "access_license": access_license,
            "execution_tier": execution_tier,
            "binding_confidence": binding_confidence,
            "distribution_quality_score": distribution_quality,
            "unit": role_policy.catalog_unit,
            "basis": required_basis,
            "connector_params": connector_params,
            "default_filters": default_filters,
            "source_selector_declared": any(
                key.casefold() in {"source", "source_id"}
                for mapping in (connector_params, default_filters)
                for key in mapping
            ),
            "identifier_anchor": identifier_anchor,
            "title_anchor": title_anchor,
            "anchor_unit": anchor_unit,
            "identifier_alignment": identifier_alignment,
            "title_alignment": title_alignment,
            "rank_score": round(
                identifier_alignment.overall_score + title_alignment.overall_score,
                6,
            ),
        }
        candidates.append(
            (
                D6CatalogCarrier(
                    **values,
                    projection_sha256=content_sha256(values),
                ),
                evaluation,
            )
        )
    if not candidates:
        raise AcquisitionSelectionError(
            "d6_eligible_role_denominator_empty",
            role,
        )
    candidates.sort(
        key=lambda item: data_forge_read_api.catalog.catalog_selection_candidate_rank(
            item[1],
            identity=(
                item[0].dataset_id,
                item[0].distribution_id,
                item[0].request_dataset_id,
            ),
        )
    )
    return candidates[0][0], rejected, len(candidates)


def _d6_filter_map(value: object) -> dict[str, list[str]]:
    parsed = _json_object(value)
    normalized: dict[str, list[str]] = {}
    for key, raw in parsed.items():
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
            normalized[str(key)] = [str(item) for item in raw]
        else:
            normalized[str(key)] = [str(raw)]
    return normalized
