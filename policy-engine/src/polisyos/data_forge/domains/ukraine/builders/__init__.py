"""Lazily expose canonical Ukraine stage builders and retained aliases."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.data_forge.domains.ukraine.models import PipelineConfig, StageId

    from . import bindings_validation, common, demography, io, observation, sources
    from .bindings_validation import (
        _augment_lookup_with_identity_bridge as _augment_lookup_with_identity_bridge,
    )
    from .bindings_validation import _build_edr_identity_bridge as _build_edr_identity_bridge
    from .bindings_validation import (
        _build_synthetic_multiscale_payload as _build_synthetic_multiscale_payload,
    )
    from .bindings_validation import _build_unique_name_lookup as _build_unique_name_lookup
    from .bindings_validation import (
        _extract_unresolved_identity_rows as _extract_unresolved_identity_rows,
    )
    from .bindings_validation import (
        _filter_identity_bridge_inputs as _filter_identity_bridge_inputs,
    )
    from .bindings_validation import _link_participants as _link_participants
    from .bindings_validation import (
        _participant_resolution_coverage as _participant_resolution_coverage,
    )
    from .bindings_validation import _resolve_agent_id as _resolve_agent_id
    from .bindings_validation import _resolve_agent_lookup as _resolve_agent_lookup
    from .bindings_validation import _validation_subset as _validation_subset
    from .common import MemoryAwareScheduler as MemoryAwareScheduler
    from .common import ScheduledTask as ScheduledTask
    from .common import _collect_graph_node_ids as _collect_graph_node_ids
    from .common import _compact_locator_value as _compact_locator_value
    from .common import _ensure_agent_numeric_columns as _ensure_agent_numeric_columns
    from .common import _graph_arrays_from_edges as _graph_arrays_from_edges
    from .common import _kernel_safe_id as _kernel_safe_id
    from .common import _reindex_edge_arrays_to_node_subset as _reindex_edge_arrays_to_node_subset
    from .common import _select_contract_graph_node_ids as _select_contract_graph_node_ids
    from .contracts import StageBuildResult as StageBuildResult
    from .demography import _aggregate_employment_admin_panel as _aggregate_employment_admin_panel
    from .demography import _build_labor_validation_artifacts as _build_labor_validation_artifacts
    from .demography import build_d3_stage as build_d3_stage
    from .demography_inventory import (
        build_demography_source_inventory_stage as build_demography_source_inventory_stage,
    )
    from .governance_handoff import build_d4_stage as build_d4_stage
    from .io import _directory_file_size_gib as _directory_file_size_gib
    from .io import _load_source_frame as _load_source_frame
    from .io import _read_parquet_frame as _read_parquet_frame
    from .io import _select_procurement_frame as _select_procurement_frame
    from .io import _stream_parquet_numeric_column_stats as _stream_parquet_numeric_column_stats
    from .io import _write_frame as _write_frame
    from .io import _write_json as _write_json
    from .observation import MONTHLY_END_MONTH as MONTHLY_END_MONTH
    from .observation import OBSERVATION_FRAME_COLUMNS as OBSERVATION_FRAME_COLUMNS
    from .observation import _period_series_to_iso_bounds as _period_series_to_iso_bounds
    from .observation import _period_to_dates as _period_to_dates
    from .release import build_d5_stage as build_d5_stage
    from .sources import _entity_scope_identity as _entity_scope_identity
    from .sources import _identity_resolution_cohort_rows as _identity_resolution_cohort_rows
    from .sources import build_d0_p0_stage as build_d0_p0_stage
    from .sources import build_d1_stage as build_d1_stage
    from .sources import build_d2_stage as build_d2_stage

    _bindings_validation = bindings_validation
    _common = common
    _demography = demography
    _io = io
    _observation = observation
    _sources = sources
    _build_household_distribution_observation_panel = (
        _demography._build_household_distribution_observation_panel
    )
    STAGE_BUILDERS: dict[StageId, Callable[[PipelineConfig], StageBuildResult]]

_LAZY_EXPORTS: dict[str, tuple[str, str | None]] = {
    "_bindings_validation": (".bindings_validation", None),
    "_common": (".common", None),
    "_demography": (".demography", None),
    "_io": (".io", None),
    "_observation": (".observation", None),
    "_sources": (".sources", None),
    "MONTHLY_END_MONTH": (".observation", "MONTHLY_END_MONTH"),
    "OBSERVATION_FRAME_COLUMNS": (".observation", "OBSERVATION_FRAME_COLUMNS"),
    "MemoryAwareScheduler": (".common", "MemoryAwareScheduler"),
    "ScheduledTask": (".common", "ScheduledTask"),
    "StageBuildResult": (".contracts", "StageBuildResult"),
    "build_d3_stage": (".demography", "build_d3_stage"),
    "build_demography_source_inventory_stage": (
        ".demography_inventory",
        "build_demography_source_inventory_stage",
    ),
    "build_d4_stage": (".governance_handoff", "build_d4_stage"),
    "build_d5_stage": (".release", "build_d5_stage"),
    "build_d0_p0_stage": (".sources", "build_d0_p0_stage"),
    "build_d1_stage": (".sources", "build_d1_stage"),
    "build_d2_stage": (".sources", "build_d2_stage"),
    "_build_synthetic_multiscale_payload": (
        ".bindings_validation",
        "_build_synthetic_multiscale_payload",
    ),
    "_collect_graph_node_ids": (".common", "_collect_graph_node_ids"),
    "_compact_locator_value": (".common", "_compact_locator_value"),
    "_directory_file_size_gib": (".io", "_directory_file_size_gib"),
    "_ensure_agent_numeric_columns": (".common", "_ensure_agent_numeric_columns"),
    "_extract_unresolved_identity_rows": (
        ".bindings_validation",
        "_extract_unresolved_identity_rows",
    ),
    "_filter_identity_bridge_inputs": (".bindings_validation", "_filter_identity_bridge_inputs"),
    "_graph_arrays_from_edges": (".common", "_graph_arrays_from_edges"),
    "_kernel_safe_id": (".common", "_kernel_safe_id"),
    "_link_participants": (".bindings_validation", "_link_participants"),
    "_load_source_frame": (".io", "_load_source_frame"),
    "_participant_resolution_coverage": (
        ".bindings_validation",
        "_participant_resolution_coverage",
    ),
    "_read_parquet_frame": (".io", "_read_parquet_frame"),
    "_reindex_edge_arrays_to_node_subset": (".common", "_reindex_edge_arrays_to_node_subset"),
    "_resolve_agent_id": (".bindings_validation", "_resolve_agent_id"),
    "_resolve_agent_lookup": (".bindings_validation", "_resolve_agent_lookup"),
    "_select_contract_graph_node_ids": (".common", "_select_contract_graph_node_ids"),
    "_stream_parquet_numeric_column_stats": (".io", "_stream_parquet_numeric_column_stats"),
    "_validation_subset": (".bindings_validation", "_validation_subset"),
    "_write_frame": (".io", "_write_frame"),
    "_write_json": (".io", "_write_json"),
    "_aggregate_employment_admin_panel": (".demography", "_aggregate_employment_admin_panel"),
    "_build_household_distribution_observation_panel": (
        ".demography",
        "_build_household_distribution_observation_panel",
    ),
    "_build_labor_validation_artifacts": (".demography", "_build_labor_validation_artifacts"),
    "_period_series_to_iso_bounds": (".observation", "_period_series_to_iso_bounds"),
    "_period_to_dates": (".observation", "_period_to_dates"),
    "_augment_lookup_with_identity_bridge": (
        ".bindings_validation",
        "_augment_lookup_with_identity_bridge",
    ),
    "_build_edr_identity_bridge": (".bindings_validation", "_build_edr_identity_bridge"),
    "_build_unique_name_lookup": (".bindings_validation", "_build_unique_name_lookup"),
    "_entity_scope_identity": (".sources", "_entity_scope_identity"),
    "_identity_resolution_cohort_rows": (".sources", "_identity_resolution_cohort_rows"),
    "_select_procurement_frame": (".io", "_select_procurement_frame"),
    "StageId": ("..models", "StageId"),
}

__all__ = (
    "MONTHLY_END_MONTH",
    "OBSERVATION_FRAME_COLUMNS",
    "STAGE_BUILDERS",
    "MemoryAwareScheduler",
    "ScheduledTask",
    "StageBuildResult",
    "build_d0_p0_stage",
    "build_d1_stage",
    "build_d2_stage",
    "build_d3_stage",
    "build_d4_stage",
    "build_d5_stage",
    "build_demography_source_inventory_stage",
)


def _stage_builders() -> dict[StageId, Callable[[PipelineConfig], StageBuildResult]]:
    from polisyos.data_forge.domains.ukraine.models import StageId

    names = {
        StageId.D0_P0: "build_d0_p0_stage",
        StageId.D1: "build_d1_stage",
        StageId.D2: "build_d2_stage",
        StageId.D3: "build_d3_stage",
        StageId.D4: "build_d4_stage",
        StageId.D5: "build_d5_stage",
        StageId.DEMOGRAPHY_SOURCE_INVENTORY: "build_demography_source_inventory_stage",
    }
    return {
        stage_id: cast("Callable[[PipelineConfig], StageBuildResult]", __getattr__(name))
        for stage_id, name in names.items()
    }


def __getattr__(name: str) -> object:
    """Resolve one retained name, or activate the stage registry on explicit access."""
    if name == "STAGE_BUILDERS":
        value = _stage_builders()
    elif name in _LAZY_EXPORTS:
        module_name, export_name = _LAZY_EXPORTS[name]
        module = import_module(module_name, __name__)
        value = module if export_name is None else getattr(module, export_name)
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """List retained names without importing their implementation modules."""
    return sorted({*globals(), *_LAZY_EXPORTS, "STAGE_BUILDERS"})
