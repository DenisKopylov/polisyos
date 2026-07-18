"""Recomputing owners for the GY-N13b acquisition execution evidence.

This module is intentionally data-plane only.  It derives an executable target
from the frozen N13a demand denominator, the immutable catalog, and the L6 slot
vocabulary.  It never executes a connector merely to select a target.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, Self

import duckdb
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.data_forge import read_api as data_forge_read_api
from polisyos.data_forge.domains.catalog.knowledge.variable_alignment import (
    VariablePairAlignmentScore,  # noqa: TC001 - Pydantic resolves this at runtime.
)
from polisyos.fabric.connectors.sources._contracts import WDI_GENERIC_SCHEMA
from polisyos.fabric.data_plane import content_sha256

TARGET_SELECTION_SCHEMA_VERSION = "policyos.layer3.gy.n13b.live_target_selection.v1"
_EXECUTABLE_TIERS = frozenset({"fetchable", "transport_ready"})
_ALIVE_LIVENESS_PREFIX = "alive_"


class AcquisitionSelectionError(RuntimeError):
    """Typed refusal raised when source evidence cannot select one live carrier."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail or code}")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LiveTargetSelection(_StrictModel):
    """One target selected from complete source denominators and owner evidence."""

    schema_version: Literal["policyos.layer3.gy.n13b.live_target_selection.v1"] = (
        TARGET_SELECTION_SCHEMA_VERSION
    )
    selection_content_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    target_variable: str = Field(min_length=1)
    canonical_unit: str = Field(min_length=1)
    backlog_rank: int = Field(ge=1)
    demand_sources: tuple[str, ...] = Field(min_length=1)
    live_family_denominator: tuple[str, ...] = Field(min_length=1)
    eligible_target_denominator: tuple[str, ...] = Field(min_length=1)
    catalog_candidate_denominator: int = Field(ge=1)
    eligible_catalog_candidate_count: int = Field(ge=1)
    rejected_candidate_counts: dict[str, int]
    source_catalog_dataset_id: str = Field(min_length=1)
    source_catalog_distribution_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    request_dataset_id: str = Field(min_length=1)
    upstream_metric_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    agency: str = Field(min_length=1)
    source_locator: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    access_license: str = Field(min_length=1)
    execution_tier: Literal["fetchable", "transport_ready"]
    binding_confidence: float = Field(ge=0.0, le=1.0)
    distribution_quality_score: float = Field(ge=0.0, le=1.0)
    temporal_start: str | None = None
    temporal_end: str | None = None
    alignment_score: VariablePairAlignmentScore

    @model_validator(mode="after")
    def _selection_is_recomputed(self) -> Self:
        if self.demand_sources != tuple(sorted(set(self.demand_sources))):
            raise ValueError("demand sources must be unique and sorted")
        if self.live_family_denominator != tuple(sorted(set(self.live_family_denominator))):
            raise ValueError("live family denominator must be unique and sorted")
        if self.eligible_target_denominator != tuple(sorted(set(self.eligible_target_denominator))):
            raise ValueError("eligible target denominator must be unique and sorted")
        if self.target_variable not in self.eligible_target_denominator:
            raise ValueError("selected target must belong to the eligible denominator")
        if self.connector_id not in self.live_family_denominator:
            raise ValueError("selected connector must belong to the live denominator")
        if any(count < 0 for count in self.rejected_candidate_counts.values()):
            raise ValueError("rejected candidate counts must be nonnegative")
        if (
            self.eligible_catalog_candidate_count + sum(self.rejected_candidate_counts.values())
            != self.catalog_candidate_denominator
        ):
            raise ValueError("candidate outcomes must cover the complete denominator")
        owner_unit = data_forge_read_api.catalog.derive_catalog_unit_from_text(
            f"{self.title} {self.description}"
        )
        if owner_unit != self.canonical_unit:
            raise ValueError("selected catalog unit must match the demanded owner unit")
        expected_score = data_forge_read_api.catalog.score_variable_pair(
            left_name=self.target_variable,
            right_name=self.upstream_metric_id,
            left_unit=self.canonical_unit,
            right_unit=owner_unit,
        )
        if self.alignment_score != expected_score:
            raise ValueError("alignment score must be recomputed by its owner")
        if self.selection_content_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("selection identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the source-evidence projection defining target selection."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "selection_content_sha256"
        }


def derive_live_target_selection(
    *,
    catalog_path: Path,
    census_path: Path,
    substrate_path: Path,
) -> LiveTargetSelection:
    """Select one honest live carrier from the full evidence-derived denominator."""

    census = _read_mapping(census_path, code="n13a_census")
    substrate = _read_mapping(substrate_path, code="intervention_substrate")
    backlog = _growth_backlog(census)
    live_families = _live_family_denominator(census)
    owner_units = _slot_units(substrate)
    eligible_targets = tuple(
        sorted(
            variable_id
            for variable_id, row in backlog.items()
            if row["gap_kind"] == "binding_gap" and len(owner_units.get(variable_id, ())) == 1
        )
    )
    if not eligible_targets:
        raise AcquisitionSelectionError("live_target_owner_unit_denominator_empty")

    rows = _read_catalog_candidates(
        Path(catalog_path),
        live_families=live_families,
    )
    if not rows:
        raise AcquisitionSelectionError("live_catalog_candidate_denominator_empty")
    rejected: Counter[str] = Counter()
    ranked: list[tuple[tuple[object, ...], dict[str, object]]] = []
    for target_variable in eligible_targets:
        units = owner_units[target_variable]
        canonical_unit = units[0]
        for row in rows:
            catalog_unit = data_forge_read_api.catalog.derive_catalog_unit_from_text(
                f"{row['title']} {row['description']}"
            )
            if catalog_unit is None:
                rejected["catalog_unit_unresolved"] += 1
                continue
            if catalog_unit != canonical_unit:
                rejected["unit_mismatch"] += 1
                continue
            if (
                data_forge_read_api.catalog.derive_license_disposition(
                    str(row["access_license"])
                ).value
                != "admissible_open"
            ):
                rejected["license_not_admissible"] += 1
                continue
            if bool(row["access_auth_required"]):
                rejected["auth_required"] += 1
                continue
            if not bool(row["parser_supported"]):
                rejected["parser_unsupported"] += 1
                continue
            score = data_forge_read_api.catalog.score_variable_pair(
                left_name=target_variable,
                right_name=str(row["upstream_metric_id"]),
                left_unit=canonical_unit,
                right_unit=catalog_unit,
            )
            rank_key = (
                int(backlog[target_variable]["rank"]),
                -score.overall_score,
                -float(row["binding_confidence"]),
                -float(row["distribution_quality_score"]),
                str(row["source_catalog_dataset_id"]),
                str(row["source_catalog_distribution_id"]),
                str(row["request_dataset_id"]),
                str(row["upstream_metric_id"]),
            )
            ranked.append(
                (
                    rank_key,
                    {
                        **row,
                        "target_variable": target_variable,
                        "canonical_unit": canonical_unit,
                        "alignment_score": score,
                    },
                )
            )
    if not ranked:
        raise AcquisitionSelectionError(
            "live_catalog_candidate_not_admissible",
            json.dumps(dict(sorted(rejected.items())), sort_keys=True),
        )

    selected = min(ranked, key=lambda item: item[0])[1]
    target_variable = str(selected["target_variable"])
    backlog_row = backlog[target_variable]
    values: dict[str, object] = {
        "target_variable": target_variable,
        "canonical_unit": selected["canonical_unit"],
        "backlog_rank": backlog_row["rank"],
        "demand_sources": backlog_row["demand_sources"],
        "live_family_denominator": live_families,
        "eligible_target_denominator": eligible_targets,
        "catalog_candidate_denominator": len(rows) * len(eligible_targets),
        "eligible_catalog_candidate_count": len(ranked),
        "rejected_candidate_counts": dict(sorted(rejected.items())),
        "source_catalog_dataset_id": selected["source_catalog_dataset_id"],
        "source_catalog_distribution_id": selected["source_catalog_distribution_id"],
        "connector_id": selected["connector_id"],
        "profile_id": selected["profile_id"],
        "request_dataset_id": selected["request_dataset_id"],
        "upstream_metric_id": selected["upstream_metric_id"],
        "source": selected["source"],
        "agency": selected["agency"],
        "source_locator": selected["source_locator"],
        "title": selected["title"],
        "description": selected["description"],
        "access_license": selected["access_license"],
        "execution_tier": selected["execution_tier"],
        "binding_confidence": selected["binding_confidence"],
        "distribution_quality_score": selected["distribution_quality_score"],
        "temporal_start": selected["temporal_start"],
        "temporal_end": selected["temporal_end"],
        "alignment_score": selected["alignment_score"],
    }
    provisional = LiveTargetSelection.model_construct(
        **values,
        selection_content_sha256="sha256:" + "0" * 64,
    )
    return LiveTargetSelection(
        **values,
        selection_content_sha256=content_sha256(provisional.identity_payload()),
    )


def build_selected_live_authority_entry(
    selection: LiveTargetSelection,
    *,
    l5_family_id: str,
    country_codes: tuple[str, ...],
) -> Any:
    """Build the last-mile registry edge from selection and connector schema owners."""

    selected = LiveTargetSelection.model_validate(selection.model_dump(mode="python"))
    if selected.connector_id != "worldbank.wdi":
        raise AcquisitionSelectionError(
            "live_connector_schema_owner_unimplemented",
            selected.connector_id,
        )
    value_fields = tuple(
        field
        for field in WDI_GENERIC_SCHEMA.fields
        if field.name not in WDI_GENERIC_SCHEMA.primary_key and field.additivity is not None
    )
    if len(value_fields) != 1:
        raise AcquisitionSelectionError("connector_value_field_ambiguous")
    raw_field = value_fields[0].name
    schema_columns = tuple(
        sorted(
            (
                data_forge_read_api.catalog.AuthoritySchemaColumn(
                    name=field.name,
                    logical_types=(field.data_type.value,),
                    nullable=field.nullable,
                )
                for field in WDI_GENERIC_SCHEMA.fields
            ),
            key=lambda field: field.name,
        )
    )
    landing_suffix = selected.selection_content_sha256.removeprefix("sha256:")[:20]
    evidence_refs = (
        f"repo://architecture/policy_design_case/"
        f"layer3_gy_n13a_acquisition_census.json#/growth_backlog/{selected.backlog_rank - 1}",
        "repo://architecture/policy_design_case/"
        "layer3_gy_intervention_substrate_contract.json#slot/"
        f"{selected.target_variable}",
        "repo://production_data/datasets_full_phase3full_20260327_183054/"
        "dataset_catalog.duckdb#ds_metric_bindings/"
        f"{selected.source_catalog_dataset_id}/{selected.source_catalog_distribution_id}/"
        f"{selected.upstream_metric_id}",
        "python://polisyos.data_forge.domains.catalog.knowledge.variable_alignment/"
        "score_variable_pair",
    )
    return data_forge_read_api.catalog.build_authority_entry(
        source_lane="live_fetch",
        target_variable=selected.target_variable,
        landing_dataset_id=f"acquisition.live.{landing_suffix}",
        landing_distribution_id=f"acquisition.live.{landing_suffix}.wdi",
        source_catalog_dataset_id=selected.source_catalog_dataset_id,
        source_catalog_distribution_id=selected.source_catalog_distribution_id,
        upstream_metric_id=selected.upstream_metric_id,
        catalog_raw_variable=selected.request_dataset_id,
        raw_field=raw_field,
        raw_unit=selected.canonical_unit,
        canonical_unit=selected.canonical_unit,
        unit_transform="identity",
        unit_transform_ref=f"fabric://units/{selected.canonical_unit}-identity/v1",
        alignment_method="semantic",
        alignment_confidence=selected.alignment_score.overall_score,
        is_proxy=False,
        proxy_penalty=0.0,
        aggregation_method="identity",
        valid_min=None,
        valid_max=None,
        evidence_refs=evidence_refs,
        schema_contract_ref=(
            f"fabric://{WDI_GENERIC_SCHEMA.schema_id}@{WDI_GENERIC_SCHEMA.version}"
        ),
        schema_columns=schema_columns,
        l5_family_id=l5_family_id,
        title=f"Acquired {selected.title}",
        description=(
            "Passport-admitted acquisition overlay rows selected from the N13a "
            f"backlog for {selected.target_variable}."
        ),
        country_codes=tuple(sorted(set(country_codes))),
        temporal_start=selected.temporal_start,
        temporal_end=selected.temporal_end,
    )


def _read_catalog_candidates(
    catalog_path: Path,
    *,
    live_families: tuple[str, ...],
) -> tuple[dict[str, object], ...]:
    if not catalog_path.is_file():
        raise AcquisitionSelectionError("catalog_missing", catalog_path.as_posix())
    con = duckdb.connect(str(catalog_path), read_only=True)
    try:
        rows = con.execute(
            """
            SELECT
                d.id,
                x.id,
                b.connector_id,
                b.profile_id,
                b.request_dataset_id,
                b.metric_id,
                d.source,
                d.agency,
                COALESCE(x.source_locator, x.url),
                d.title,
                COALESCE(d.description, ''),
                d.access_license,
                d.access_auth_required,
                b.execution_tier,
                b.confidence,
                x.quality_score,
                x.parser_supported,
                d.temporal_start,
                d.temporal_end
            FROM ds_metric_bindings b
            JOIN ds_datasets d ON d.id = b.dataset_id
            JOIN ds_distributions x
              ON x.id = b.distribution_id AND x.dataset_id = b.dataset_id
            WHERE b.connector_id IN (SELECT UNNEST(?))
              AND b.execution_tier IN ('fetchable', 'transport_ready')
              AND x.connector_type = b.connector_id
              AND x.profile_id = b.profile_id
            ORDER BY d.id, x.id, b.metric_id, b.request_dataset_id
            """,
            [list(live_families)],
        ).fetchall()
    except Exception as exc:
        raise AcquisitionSelectionError(
            "catalog_candidate_query_failed",
            type(exc).__name__,
        ) from exc
    finally:
        con.close()

    keys = (
        "source_catalog_dataset_id",
        "source_catalog_distribution_id",
        "connector_id",
        "profile_id",
        "request_dataset_id",
        "upstream_metric_id",
        "source",
        "agency",
        "source_locator",
        "title",
        "description",
        "access_license",
        "access_auth_required",
        "execution_tier",
        "binding_confidence",
        "distribution_quality_score",
        "parser_supported",
        "temporal_start",
        "temporal_end",
    )
    return tuple(dict(zip(keys, raw, strict=True)) for raw in rows)


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


def _read_mapping(path: Path, *, code: str) -> dict[str, object]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise AcquisitionSelectionError(f"{code}_unreadable", type(exc).__name__) from exc
    if not isinstance(value, Mapping):
        raise AcquisitionSelectionError(f"{code}_mapping_required")
    return {str(key): item for key, item in value.items()}


__all__ = [
    "AcquisitionSelectionError",
    "LiveTargetSelection",
    "build_selected_live_authority_entry",
    "derive_live_target_selection",
]
