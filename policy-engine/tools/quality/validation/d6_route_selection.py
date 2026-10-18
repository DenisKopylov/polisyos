"""D6 route selection over frozen carrier and slot denominators."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

import duckdb

from polisyos.data_forge import read_api as data_forge_read_api

if TYPE_CHECKING:
    from polisyos.data_forge.read_api.catalog import CatalogSelectionPolicyConfig
from polisyos.fabric.data_plane import content_sha256
from polisyos.runtime.quality.derived_observations import (
    DerivationRefusalCode,
    DerivationRefusalError,
    DerivationRefusalReason,
    TransformFamilyRegistry,
)

from .acquisition_executor_support import (
    _read_mapping,
    bytes_sha256,
)
from .acquisition_response_receipts import (
    AcquisitionSelectionError,
    CarrierDataDisposition,
    R1ForensicReceipt,
)
from .catalog_candidate_admission import (
    D6RouteSelection,
    _d6_failed_and_auxiliary_roles,
    _d6_requires_source_characterization,
    _d6_transform_formula,
    _load_d6_selection_policy,
    _load_d6_transform_registry,
    _raise_d6_no_certified_transform,
    _read_d6_catalog_denominator,
    _resolve_d6_catalog_role_policy,
    _resolve_d6_transform_family,
    _select_d6_carrier,
)

_ALIVE_LIVENESS_PREFIX = "alive_"

DEFAULT_CARRIER_LIVENESS_UPDATE = Path(
    "architecture/policy_design_case/"
    "layer3_gy_n13a_worldbank_government_balance_carrier_liveness.json"
)

DEFAULT_D6_ROUTE_SELECTION = Path(
    "architecture/policy_design_case/layer3_gy_n13b_d6_route_selection.json"
)


def derive_d6_route_selection(
    *,
    catalog_path: Path,
    census_path: Path,
    substrate_path: Path,
    r1_receipt: R1ForensicReceipt,
    carrier_liveness_path: Path,
    transform_registry_source: TransformFamilyRegistry | str | Path | Mapping[str, object],
    selection_policy_source: CatalogSelectionPolicyConfig | str | Path | Mapping[str, object],
) -> D6RouteSelection:
    """Derive one registered transform route from paid and catalog owner evidence."""

    from tools.quality.validation import layer3_gy_n13a_acquisition_census as census_owner

    r1 = R1ForensicReceipt.model_validate(r1_receipt.model_dump(mode="python"))
    if r1.classification.disposition not in {
        CarrierDataDisposition.NO_DATA_FOR_SCOPE,
        CarrierDataDisposition.CARRIER_RETIRED_OR_INVALID,
    }:
        raise AcquisitionSelectionError(
            "d6_failed_carrier_disposition_unresolved",
            r1.classification.disposition.value,
        )
    carrier_path = Path(carrier_liveness_path)
    try:
        carrier_update = census_owner.RecurringCarrierLivenessUpdate.model_validate_json(
            carrier_path.read_bytes()
        )
    except (OSError, ValueError) as exc:
        raise AcquisitionSelectionError(
            "d6_carrier_liveness_invalid",
            carrier_path.as_posix(),
        ) from exc
    if carrier_update.request_dataset_id != r1.request_dataset_id:
        raise AcquisitionSelectionError("d6_carrier_liveness_target_drift")
    if carrier_update.carrier_disposition.value not in {
        "carrier_current_no_data_for_scope",
        "carrier_current_source_profile_mismatch",
        "carrier_retired_or_invalid",
    }:
        raise AcquisitionSelectionError(
            "d6_carrier_not_terminal_for_direct_basis",
            carrier_update.carrier_disposition.value,
        )

    catalog_path = Path(catalog_path)
    if not catalog_path.is_file():
        raise AcquisitionSelectionError("d6_catalog_unresolved", catalog_path.as_posix())
    baseline_sha = bytes_sha256(catalog_path.read_bytes())
    with duckdb.connect(str(catalog_path), read_only=True) as con:
        failed_rows = con.execute(
            """
            SELECT DISTINCT b.metric_id, b.connector_id, b.profile_id,
                            d.title, d.description
            FROM ds_metric_bindings b
            JOIN ds_datasets d ON d.id = b.dataset_id
            WHERE b.request_dataset_id = ?
            ORDER BY b.metric_id, b.connector_id, b.profile_id, d.title, d.description
            """,
            [r1.request_dataset_id],
        ).fetchall()
    failed_owner_keys = set()
    for row in failed_rows:
        owner_unit = data_forge_read_api.catalog.derive_catalog_unit_from_text(
            f"{row[3] or ''} {row[4] or ''}"
        )
        if owner_unit is None:
            continue
        failed_owner_keys.add(
            (
                str(row[0]),
                str(row[1]),
                str(row[2]),
                str(row[3]),
                str(row[4] or ""),
                owner_unit,
            )
        )
    if len(failed_owner_keys) != 1:
        raise AcquisitionSelectionError(
            "d6_failed_catalog_owner_ambiguous",
            str(len(failed_owner_keys)),
        )
    (
        failed_metric,
        connector_id,
        profile_id,
        failed_title,
        _failed_description,
        failed_unit,
    ) = next(iter(failed_owner_keys))
    registry = _load_d6_transform_registry(transform_registry_source)
    policy = _load_d6_selection_policy(
        selection_policy_source,
        failed_metric_id=failed_metric,
    )
    family = _resolve_d6_transform_family(
        registry,
        family_id=policy.family_id,
        method_version=policy.method_version,
    )
    if family.method_version != policy.method_version:
        _raise_d6_no_certified_transform(
            f"{family.family_id}: policy/runtime method-version mismatch"
        )
    specs = {item.role: item for item in family.input_specs}
    if set(specs) != {item.role for item in policy.roles}:
        _raise_d6_no_certified_transform(
            f"{family.family_id}: policy roles differ from transform inputs"
        )
    if family.output_basis.unit != failed_unit:
        _raise_d6_no_certified_transform(
            f"{family.family_id}: output={family.output_basis.unit}, failed={failed_unit}"
        )
    try:
        primary_policy, auxiliary_policy = _d6_failed_and_auxiliary_roles(
            policy,
            failed_metric,
        )
    except (ValueError, data_forge_read_api.catalog.CatalogSelectionError) as exc:
        raise AcquisitionSelectionError(
            DerivationRefusalCode.BASIS_MISMATCH.value,
            str(exc),
            reason=DerivationRefusalReason.NO_CERTIFIED_TRANSFORM.value,
        ) from exc
    primary_spec = specs[primary_policy.role]
    auxiliary_spec = specs[auxiliary_policy.role]
    if primary_spec.basis == family.output_basis:
        _raise_d6_no_certified_transform(
            f"{family.family_id}: primary/output basis mismatch absent"
        )
    primary_role_values = _resolve_d6_catalog_role_policy(
        primary_policy,
        is_failed_carrier=True,
        failed_metric_id=failed_metric,
        failed_request_dataset_id=r1.request_dataset_id,
        failed_catalog_title=failed_title,
        failed_catalog_unit=failed_unit,
    )
    auxiliary_role_values = _resolve_d6_catalog_role_policy(
        auxiliary_policy,
        is_failed_carrier=False,
        failed_metric_id=failed_metric,
        failed_request_dataset_id=r1.request_dataset_id,
        failed_catalog_title=failed_title,
        failed_catalog_unit=failed_unit,
    )

    census = _read_mapping(Path(census_path), code="n13a_census")
    substrate = _read_mapping(Path(substrate_path), code="intervention_substrate")
    backlog = _growth_backlog(census)
    slot_units = _slot_units(substrate)
    target_candidates: list[tuple[tuple[object, ...], str, dict[str, object]]] = []
    for variable_id, row in backlog.items():
        units = slot_units.get(variable_id, ())
        if row.get("gap_kind") != "binding_gap" or units != (failed_unit,):
            continue
        score = data_forge_read_api.catalog.score_variable_pair(
            left_name=variable_id,
            right_name=failed_metric,
            left_unit=failed_unit,
            right_unit=failed_unit,
        )
        target_candidates.append(
            (
                (int(row["rank"]), -score.overall_score, variable_id),
                variable_id,
                row,
            )
        )
    if not target_candidates:
        raise AcquisitionSelectionError("d6_demanded_output_gap_denominator_empty")
    target_candidates.sort(key=lambda item: item[0])
    _target_key, target_variable, backlog_row = target_candidates[0]

    primary_rows = _read_d6_catalog_denominator(
        catalog_path,
        connector_id=connector_id,
        metric_id=primary_role_values["metric_id"],
    )
    primary, primary_rejected, primary_count = _select_d6_carrier(
        rows=primary_rows,
        role=primary_policy.role,
        role_policy=primary_policy,
        required_basis=primary_spec.basis,
        identifier_anchor=primary_role_values["identifier_anchor"],
        title_anchor=primary_role_values["title_anchor"],
        anchor_unit=primary_role_values["anchor_unit"],
    )
    auxiliary_rows = _read_d6_catalog_denominator(
        catalog_path,
        connector_id=connector_id,
        metric_id=auxiliary_role_values["metric_id"],
    )
    auxiliary, auxiliary_rejected, auxiliary_count = _select_d6_carrier(
        rows=auxiliary_rows,
        role=auxiliary_policy.role,
        role_policy=auxiliary_policy,
        required_basis=auxiliary_spec.basis,
        identifier_anchor=auxiliary_role_values["identifier_anchor"],
        title_anchor=auxiliary_role_values["title_anchor"],
        anchor_unit=auxiliary_role_values["anchor_unit"],
    )
    if primary.profile_id != profile_id or auxiliary.profile_id != profile_id:
        raise AcquisitionSelectionError("d6_profile_owner_mismatch")
    try:
        resolved_family = registry.resolve(
            input_bases={
                primary.role: primary.basis or primary_spec.basis,
                auxiliary.role: auxiliary.basis or auxiliary_spec.basis,
            },
            output_basis=family.output_basis,
            family_id=family.family_id,
        )
    except DerivationRefusalError as exc:
        raise AcquisitionSelectionError(
            exc.code.value,
            exc.detail,
            reason=exc.reason.value if exc.reason is not None else None,
        ) from exc
    if resolved_family != family:
        raise AcquisitionSelectionError("d6_transform_registry_resolution_drift")

    backlog_projection = {
        "variable_id": target_variable,
        "rank": int(backlog_row["rank"]),
        "gap_kind": str(backlog_row["gap_kind"]),
        "demand_sources": tuple(sorted(str(item) for item in backlog_row["demand_sources"])),
    }
    substrate_projection = {
        "slot_id": target_variable,
        "units": slot_units[target_variable],
    }
    values: dict[str, object] = {
        "schema_version": "policyos.layer3.gy.n13b.d6_route_selection.v2",
        "baseline_sha256": baseline_sha,
        "census_backlog_projection_sha256": content_sha256(backlog_projection),
        "substrate_slot_projection_sha256": content_sha256(substrate_projection),
        "r1_receipt_sha256": r1.receipt_sha256,
        "carrier_liveness_receipt_sha256": carrier_update.receipt_sha256,
        "target_variable": target_variable,
        "backlog_rank": int(backlog_row["rank"]),
        "demand_sources": tuple(sorted(str(item) for item in backlog_row["demand_sources"])),
        "required_output_unit": family.output_basis.unit,
        "failed_request_dataset_id": r1.request_dataset_id,
        "failed_metric_id": failed_metric,
        "failed_catalog_title": failed_title,
        "failed_catalog_unit": failed_unit,
        "failed_carrier_disposition": carrier_update.carrier_disposition.value,
        "failed_missing_request_levers": carrier_update.missing_request_levers,
        "route_disposition": "derivation_requirement",
        "transform_method_id": family.method_id,
        "transform_method_version": family.method_version,
        "transform_formula": _d6_transform_formula(family),
        "transform_family": family,
        "transform_family_projection_sha256": content_sha256(family.model_dump(mode="json")),
        "transform_registry_projection_sha256": content_sha256(registry.model_dump(mode="json")),
        "selection_policy": policy,
        "selection_policy_projection_sha256": content_sha256(policy.model_dump(mode="json")),
        "primary_catalog_denominator": len(primary_rows),
        "primary_candidate_denominator": primary_count,
        "primary_rejected_counts": dict(sorted(primary_rejected.items())),
        "auxiliary_catalog_denominator": len(auxiliary_rows),
        "auxiliary_candidate_denominator": auxiliary_count,
        "auxiliary_rejected_counts": dict(sorted(auxiliary_rejected.items())),
        "primary": primary,
        "auxiliary": auxiliary,
        "primary_requires_source_characterization": _d6_requires_source_characterization(
            primary,
            primary_policy,
        ),
    }
    draft = D6RouteSelection.model_construct(
        **values,
        selection_sha256="sha256:" + "0" * 64,
    )
    return D6RouteSelection(
        **values,
        selection_sha256=content_sha256(draft.identity_payload()),
    )


def _growth_backlog(census: Mapping[str, object]) -> dict[str, dict[str, object]]:
    raw = census.get("growth_backlog")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        raise AcquisitionSelectionError("growth_backlog_missing")
    rows: dict[str, dict[str, object]] = {}
    for item in raw:
        if not isinstance(item, Mapping):
            raise AcquisitionSelectionError("growth_backlog_row_invalid")
        variable_id = str(item.get("variable_id") or "").strip()
        gap_kind = str(item.get("gap_kind") or "").strip()
        rank = item.get("rank")
        demand_sources = item.get("demand_sources")
        if (
            not variable_id
            or isinstance(rank, bool)
            or not isinstance(rank, int)
            or rank < 1
            or not isinstance(demand_sources, Sequence)
            or isinstance(demand_sources, (str, bytes, bytearray))
        ):
            raise AcquisitionSelectionError("growth_backlog_row_invalid", variable_id)
        normalized_sources = tuple(sorted({str(value) for value in demand_sources if str(value)}))
        if not normalized_sources or variable_id in rows:
            raise AcquisitionSelectionError("growth_backlog_denominator_invalid", variable_id)
        rows[variable_id] = {
            "rank": rank,
            "gap_kind": gap_kind,
            "demand_sources": normalized_sources,
        }
    return rows


def _live_family_denominator(census: Mapping[str, object]) -> tuple[str, ...]:
    raw = census.get("family_scorecards")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        raise AcquisitionSelectionError("family_scorecards_missing")
    families: set[str] = set()
    for item in raw:
        if not isinstance(item, Mapping):
            raise AcquisitionSelectionError("family_scorecard_invalid")
        connector_id = str(item.get("connector_id") or "").strip()
        counts = item.get("liveness_counts")
        if not connector_id or not isinstance(counts, Mapping):
            raise AcquisitionSelectionError("family_scorecard_invalid", connector_id)
        alive_count = sum(
            int(value)
            for key, value in counts.items()
            if str(key).startswith(_ALIVE_LIVENESS_PREFIX)
            and isinstance(value, int)
            and not isinstance(value, bool)
            and value > 0
        )
        if alive_count:
            families.add(connector_id)
    if not families:
        raise AcquisitionSelectionError("live_family_denominator_empty")
    return tuple(sorted(families))


def _slot_units(substrate: Mapping[str, object]) -> dict[str, tuple[str, ...]]:
    units: defaultdict[str, set[str]] = defaultdict(set)

    def visit(value: object) -> None:
        if isinstance(value, Mapping):
            slot_id = value.get("slot_id")
            unit = value.get("unit")
            if isinstance(slot_id, str) and slot_id.strip() and isinstance(unit, str):
                normalized = data_forge_read_api.catalog.normalize_acquisition_unit(unit)
                if normalized:
                    units[slot_id.strip()].add(normalized)
            for nested in value.values():
                visit(nested)
        elif isinstance(value, Sequence) and not isinstance(
            value,
            (str, bytes, bytearray),
        ):
            for nested in value:
                visit(nested)

    visit(substrate)
    return {key: tuple(sorted(values)) for key, values in sorted(units.items())}
