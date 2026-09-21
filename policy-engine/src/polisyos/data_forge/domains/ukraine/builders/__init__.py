"""Split Ukraine stage-builder surface owned by Data Forge."""

from __future__ import annotations

from polisyos.data_forge.domains.ukraine.models import StageId

from .common import (
    MONTHLY_END_MONTH,
    OBSERVATION_FRAME_COLUMNS,
    MemoryAwareScheduler,
    ScheduledTask,
    StageBuildResult,
    _build_synthetic_multiscale_payload,
    _collect_graph_node_ids,
    _compact_locator_value,
    _directory_file_size_gib,
    _filter_identity_bridge_inputs,
    _graph_arrays_from_edges,
    _kernel_safe_id,
    _participant_resolution_coverage,
    _reindex_edge_arrays_to_node_subset,
    _resolve_agent_id,
    _resolve_agent_lookup,
    _select_contract_graph_node_ids,
    _stream_parquet_numeric_column_stats,
    _validation_subset,
)
from .demography import (
    _aggregate_employment_admin_panel,
    _build_household_distribution_observation_panel,
    _build_labor_validation_artifacts,
    build_d3_stage,
)
from .governance_handoff import build_d4_stage
from .observation import _period_series_to_iso_bounds, _period_to_dates
from .release import build_d5_stage
from .sources import (
    _augment_lookup_with_identity_bridge,
    _build_edr_identity_bridge,
    _build_unique_name_lookup,
    _entity_scope_identity,
    _identity_resolution_cohort_rows,
    _select_procurement_frame,
    build_d0_p0_stage,
    build_d1_stage,
    build_d2_stage,
)

STAGE_BUILDERS = {
    StageId.D0_P0: build_d0_p0_stage,
    StageId.D1: build_d1_stage,
    StageId.D2: build_d2_stage,
    StageId.D3: build_d3_stage,
    StageId.D4: build_d4_stage,
    StageId.D5: build_d5_stage,
}

__all__ = (
    "MONTHLY_END_MONTH",
    "OBSERVATION_FRAME_COLUMNS",
    "MemoryAwareScheduler",
    "ScheduledTask",
    "StageBuildResult",
    "STAGE_BUILDERS",
    "build_d0_p0_stage",
    "build_d1_stage",
    "build_d2_stage",
    "build_d3_stage",
    "build_d4_stage",
    "build_d5_stage",
)
