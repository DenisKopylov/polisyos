"""Split Ukraine stage-builder surface owned by Data Forge."""

from __future__ import annotations

from polisyos.data_forge.domains.ukraine.models import StageId

from . import common as _common
from . import demography as _demography
from . import observation as _observation
from . import sources as _sources
from .common import (
    MONTHLY_END_MONTH,
    OBSERVATION_FRAME_COLUMNS,
    MemoryAwareScheduler,
    ScheduledTask,
    StageBuildResult,
)
from .demography import build_d3_stage
from .governance_handoff import build_d4_stage
from .release import build_d5_stage
from .sources import build_d0_p0_stage, build_d1_stage, build_d2_stage

# These explicit aliases preserve the pre-relocation import surface for
# existing internal callers while keeping implementation helpers out of the
# package's declared public ``__all__``.
_build_synthetic_multiscale_payload = _common._build_synthetic_multiscale_payload
_collect_graph_node_ids = _common._collect_graph_node_ids
_compact_locator_value = _common._compact_locator_value
_directory_file_size_gib = _common._directory_file_size_gib
_ensure_agent_numeric_columns = _common._ensure_agent_numeric_columns
_extract_unresolved_identity_rows = _common._extract_unresolved_identity_rows
_filter_identity_bridge_inputs = _common._filter_identity_bridge_inputs
_graph_arrays_from_edges = _common._graph_arrays_from_edges
_kernel_safe_id = _common._kernel_safe_id
_link_participants = _common._link_participants
_load_source_frame = _common._load_source_frame
_participant_resolution_coverage = _common._participant_resolution_coverage
_read_parquet_frame = _common._read_parquet_frame
_reindex_edge_arrays_to_node_subset = _common._reindex_edge_arrays_to_node_subset
_resolve_agent_id = _common._resolve_agent_id
_resolve_agent_lookup = _common._resolve_agent_lookup
_select_contract_graph_node_ids = _common._select_contract_graph_node_ids
_stream_parquet_numeric_column_stats = _common._stream_parquet_numeric_column_stats
_validation_subset = _common._validation_subset
_write_frame = _common._write_frame
_write_json = _common._write_json
_aggregate_employment_admin_panel = _demography._aggregate_employment_admin_panel
_build_household_distribution_observation_panel = (
    _demography._build_household_distribution_observation_panel
)
_build_labor_validation_artifacts = _demography._build_labor_validation_artifacts
_period_series_to_iso_bounds = _observation._period_series_to_iso_bounds
_period_to_dates = _observation._period_to_dates
_augment_lookup_with_identity_bridge = _common._augment_lookup_with_identity_bridge
_build_edr_identity_bridge = _common._build_edr_identity_bridge
_build_unique_name_lookup = _common._build_unique_name_lookup
_entity_scope_identity = _sources._entity_scope_identity
_identity_resolution_cohort_rows = _sources._identity_resolution_cohort_rows
_select_procurement_frame = _common._select_procurement_frame

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
)
