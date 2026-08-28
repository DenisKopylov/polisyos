from __future__ import annotations

import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from polisyos.data_forge.domains.ukraine.builders import (
    MemoryAwareScheduler,
    ScheduledTask,
    _aggregate_employment_admin_panel,
    _augment_lookup_with_identity_bridge,
    _build_edr_identity_bridge,
    _build_household_distribution_observation_panel,
    _build_labor_validation_artifacts,
    _build_synthetic_multiscale_payload,
    _build_unique_name_lookup,
    _collect_graph_node_ids,
    _compact_locator_value,
    _directory_file_size_gib,
    _entity_scope_identity,
    _filter_identity_bridge_inputs,
    _graph_arrays_from_edges,
    _identity_resolution_cohort_rows,
    _kernel_safe_id,
    _participant_resolution_coverage,
    _period_to_dates,
    _reindex_edge_arrays_to_node_subset,
    _resolve_agent_id,
    _resolve_agent_lookup,
    _select_contract_graph_node_ids,
    _select_procurement_frame,
    _stream_parquet_numeric_column_stats,
    _validation_subset,
    build_d3_stage,
    build_d4_stage,
    build_d5_stage,
)
from polisyos.data_forge.domains.ukraine.builders import sources as source_builders
from polisyos.data_forge.domains.ukraine.manifests import D5ReleaseHandoffRequest
from polisyos.data_forge.domains.ukraine.models import (
    SourceConfig,
    StageId,
    build_default_pipeline_config,
)
from polisyos.ir.analytics.calibration import (
    CalibrationRunManifest,
    HoldoutScoresManifest,
    SpecificationCurveSummaryManifest,
    StrategicResponseMetricsManifest,
    TransportabilitySummaryManifest,
)
from polisyos.ir.model_layer.types import TimeFrequency
from polisyos.ir.observation.contracts import EntityScope, ObservationFamily
from polisyos.scientist.governance import (
    StrategicResponseRunner,
    build_family_eligibility_registry,
)
from polisyos.scientist.governance.blueprint_release import run_verified_ukraine_d5_release


def test_ukraine_builder_reads_canonical_l5_registry_without_regime_literals() -> None:
    registry = source_builders._load_l5_schema_regime_registry()
    calendar = source_builders._regime_calendar_from_l5_schema_registry(registry)
    source = source_builders.Path(source_builders.__file__).read_text(encoding="utf-8")

    assert tuple(row.regime_id for row in calendar.entries) == tuple(
        row.regime_id or row.schema_regime_id
        for row in sorted(registry.regimes.values(), key=lambda item: item.effective_start)
    )
    assert all(
        token not in source
        for token in (
            "regime_a",
            "regime_b",
            "ukraine_schema_v1",
            "ukraine_schema_v2",
        )
    )
    assert "2022-02-24" not in source


def test_memory_aware_scheduler_runs_tasks_in_order() -> None:
    scheduler = MemoryAwareScheduler(max_workers=4, memory_budget_gib=8.0)
    observed: list[str] = []

    results = scheduler.run(
        [
            ScheduledTask("a", 2.0, lambda: observed.append("a") or {"ok": True}),
            ScheduledTask("b", 3.0, lambda: observed.append("b") or {"ok": True}),
        ]
    )

    assert observed == ["a", "b"]
    assert list(results) == ["a", "b"]


def test_scientist_reexports_ir_owned_d4_release_read_contracts() -> None:
    """Keep Scientist's published names as consumers of the lower D4 schema."""
    from polisyos.scientist import governance

    assert governance.CalibrationRunManifest is CalibrationRunManifest
    assert governance.HoldoutScoresManifest is HoldoutScoresManifest
    assert governance.SpecificationCurveSummaryManifest is SpecificationCurveSummaryManifest
    assert governance.StrategicResponseMetricsManifest is StrategicResponseMetricsManifest
    assert governance.TransportabilitySummaryManifest is TransportabilitySummaryManifest


def test_memory_aware_scheduler_rejects_oversized_task() -> None:
    scheduler = MemoryAwareScheduler(max_workers=4, memory_budget_gib=4.0)

    with pytest.raises(ValueError, match="requests 8.00 GiB"):
        scheduler.run([ScheduledTask("too_big", 8.0, lambda: {"ok": False})])


def test_agent_lookup_normalizes_numeric_identity_keys() -> None:
    registry = pd.DataFrame(
        {
            "agent_id": ["agent::one", "agent::two"],
            "registration_code": ["08252623", "34971128"],
        }
    )

    lookup = _resolve_agent_lookup(registry)

    assert _resolve_agent_id("08252623", lookup) == "agent::one"
    assert _resolve_agent_id("8252623", lookup) == "agent::one"
    assert _resolve_agent_id("34971128", lookup) == "agent::two"


def test_participant_resolution_coverage_counts_raw_vs_resolved_identities() -> None:
    frame = pd.DataFrame(
        {
            "_source_agent_raw_id": ["08252623", "08252623", "34971128", ""],
            "_target_agent_raw_id": ["14361575", "14361575", None, ""],
            "source_agent_id": ["agent::a", "agent::a", None, None],
            "target_agent_id": ["agent::b", "agent::b", None, None],
        }
    )

    coverage, resolved, total = _participant_resolution_coverage(
        frame,
        raw_columns=["_source_agent_raw_id", "_target_agent_raw_id"],
        resolved_columns=["source_agent_id", "target_agent_id"],
    )

    assert coverage == pytest.approx(2 / 3)
    assert resolved == 2
    assert total == 3


def test_identity_resolution_cohort_rows_preserve_the_unique_coverage_denominator() -> None:
    frame = pd.DataFrame(
        {
            "_source_agent_raw_id": ["08252623", "08252623", "34971128"],
            "_target_agent_raw_id": ["14361575", "14361575", None],
            "source_agent_id": ["agent::a", "agent::a", None],
            "target_agent_id": ["agent::b", "agent::b", None],
        }
    )

    rows = _identity_resolution_cohort_rows(
        frame,
        cohort="spending",
        raw_identity_columns=(
            "_source_agent_raw_id",
            "_target_agent_raw_id",
        ),
    )

    assert rows == [
        {"cohort": "spending", "raw_identity": "08252623"},
        {"cohort": "spending", "raw_identity": "14361575"},
        {"cohort": "spending", "raw_identity": "34971128"},
    ]


def test_validation_subset_downsamples_large_runtime_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POLISYOS_UKRAINE_DATA_BINDINGS_AGENT_LIMIT", "2")
    monkeypatch.setenv("POLISYOS_UKRAINE_DATA_BINDINGS_CELL_LIMIT", "1")
    runtime_agents = pd.DataFrame(
        {
            "agent_id": ["agent::1", "agent::2", "agent::3"],
            "cell_id": ["cell::a", "cell::a", "cell::b"],
        }
    )
    cell_registry = pd.DataFrame(
        {
            "cell_id": ["cell::a", "cell::b"],
            "region_code": ["01", "02"],
            "sector_id": ["A", "B"],
            "agent_count": [2, 1],
        }
    )
    cell_state = pd.DataFrame(
        {
            "cell_id": ["cell::a", "cell::b"],
            "region_numeric": [0, 1],
            "sector_numeric": [0, 1],
            "population": [10.0, 5.0],
            "employment": [4.0, 2.0],
            "output": [100.0, 50.0],
            "distress_score": [0.1, 0.2],
            "public_service_index": [0.3, 0.4],
        }
    )

    agents_subset, cells_subset, cell_state_subset, warnings = _validation_subset(
        runtime_agents,
        cell_registry,
        cell_state,
    )

    assert len(agents_subset) == 2
    assert len(cells_subset) == 1
    assert len(cell_state_subset) == 1
    assert warnings == [
        "bindings_validation_agent_sampled:2/3",
        "bindings_validation_cell_sampled:1/2",
    ]


def test_stream_parquet_numeric_column_stats_streams_mean_and_head(tmp_path) -> None:
    path = tmp_path / "observations.parquet"
    pd.DataFrame(
        {
            "observed_value": [-2.0, None, 3.0, -5.0],
            "other": ["a", "b", "c", "d"],
        }
    ).to_parquet(path, index=False)

    mean_abs, head = _stream_parquet_numeric_column_stats(path, "observed_value", head_limit=2)

    assert mean_abs == pytest.approx((2.0 + 3.0 + 5.0) / 3.0)
    assert head.tolist() == [-2.0, 3.0]


def test_directory_file_size_gib_sums_only_files(tmp_path) -> None:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "a.bin").write_bytes(b"a" * 1024)
    (bundle_dir / "b.bin").write_bytes(b"b" * 2048)
    (bundle_dir / "nested").mkdir()
    (bundle_dir / "nested" / "c.bin").write_bytes(b"c" * 4096)

    size_gib = _directory_file_size_gib(bundle_dir)

    assert size_gib == pytest.approx((1024 + 2048) / (1024**3))


def test_select_procurement_frame_prefers_spending_contracts_proxy(tmp_path) -> None:
    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    proxy_path = (
        config.build_root.normalized_dir
        / "spending_contracts_procurement_proxy"
        / "procurement_contracts_monthly.parquet"
    )
    proxy_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "buyer_agent_id": ["11111111"],
            "supplier_agent_id": ["22222222"],
            "amount": [100.0],
            "period_id": ["2024-01"],
            "registration_code": ["11111111"],
        }
    ).to_parquet(proxy_path, index=False)

    frame, source_id, warnings = _select_procurement_frame(config)

    assert source_id == "spending_contracts_procurement_proxy"
    assert frame.loc[0, "buyer_agent_id"] == "11111111"
    assert warnings == ["procurement_source_selected:spending_contracts_procurement_proxy"]


def test_collect_graph_node_ids_includes_non_runtime_edge_nodes() -> None:
    trade = pd.DataFrame(
        {
            "source_agent_id": ["agent::runtime", "agent::customs"],
            "target_agent_id": ["agent::partner", "agent::runtime"],
        }
    )

    node_ids = _collect_graph_node_ids(
        base_node_ids=["agent::runtime"],
        edge_frames=[(trade, "source_agent_id", "target_agent_id")],
    )

    assert node_ids == ["agent::customs", "agent::partner", "agent::runtime"]


def test_select_contract_graph_node_ids_caps_dense_contract_size() -> None:
    frame = pd.DataFrame(
        {
            "source_agent_id": ["agent::a", "agent::a", "agent::b", "agent::c"],
            "target_agent_id": ["agent::b", "agent::c", "agent::c", "agent::d"],
            "trade_value": [10.0, 3.0, 5.0, 1.0],
            "period_id": ["2025-01"] * 4,
        }
    )
    arrays = _graph_arrays_from_edges(
        frame,
        src_col="source_agent_id",
        dst_col="target_agent_id",
        weight_col="trade_value",
    )

    node_ids = _select_contract_graph_node_ids([arrays], max_nodes=2)

    assert node_ids == ["agent::b", "agent::a"]


def test_reindex_edge_arrays_to_node_subset_filters_non_selected_nodes() -> None:
    frame = pd.DataFrame(
        {
            "source_agent_id": ["agent::a", "agent::a", "agent::c"],
            "target_agent_id": ["agent::b", "agent::c", "agent::b"],
            "trade_value": [10.0, 3.0, 1.0],
            "period_id": ["2025-01"] * 3,
        }
    )
    arrays = _graph_arrays_from_edges(
        frame,
        src_col="source_agent_id",
        dst_col="target_agent_id",
        weight_col="trade_value",
    )

    compact = _reindex_edge_arrays_to_node_subset(arrays, node_ids=["agent::a", "agent::b"])

    assert compact["node_ids"].tolist() == ["agent::a", "agent::b"]
    assert compact["src_ids"].tolist() == ["agent::a"]
    assert compact["dst_ids"].tolist() == ["agent::b"]
    assert compact["weight"].tolist() == [10.0]


def test_kernel_safe_id_rewrites_invalid_observation_delimiters() -> None:
    value = _kernel_safe_id("obs", "budget_managers", "is_budget_manager", "00000000", prefix="obs")

    assert value == "obs.budget_managers.is_budget_manager.00000000"


def test_period_to_dates_supports_yyyymm_m_and_quarter_formats() -> None:
    month_start, month_end = _period_to_dates("2024M03", TimeFrequency.MONTH)
    quarter_start, quarter_end = _period_to_dates("2024Q2", TimeFrequency.QUARTER)

    assert month_start.isoformat() == "2024-03-01"
    assert month_end.isoformat() == "2024-03-31"
    assert quarter_start.isoformat() == "2024-04-01"
    assert quarter_end.isoformat() == "2024-06-30"


def test_compact_locator_value_hashes_overlong_labels() -> None:
    value = _compact_locator_value("X" * 200, max_length=32, prefix="sector")

    assert value is not None
    assert value.startswith("sector.")
    assert len(value) <= 32


def test_entity_scope_identity_uses_identity_columns_when_agent_id_missing() -> None:
    source = SourceConfig(
        source_id="customs_trade",
        display_name="Customs trade",
        stage_id=StageId.D1,
        normalized_artifact="trade_exposure_monthly.parquet",
        required_columns=["source_agent_id", "target_agent_id", "trade_value", "period_id"],
        observation_family=ObservationFamily.TRADE_EXPOSURE,
        entity_scope=EntityScope.AGENT,
        identity_columns=["source_agent_id", "target_agent_id"],
    )
    row = pd.Series({"source_agent_id": "agent::source", "target_agent_id": "agent::target"})

    entity_id, cell_id, region_code, sector_id = _entity_scope_identity(source, row)

    assert entity_id == "agent::source"
    assert cell_id is None
    assert region_code is None
    assert sector_id is None


def test_build_synthetic_multiscale_payload_sanitizes_huge_cell_metrics() -> None:
    runtime_agents = pd.DataFrame(
        {
            "agent_id": ["agent::1", "agent::2"],
            "revenue": [100.0, 200.0],
            "employees": [1.0, 0.0],
            "region_numeric": [0.0, 1.0],
            "assets": [10.0, 20.0],
            "liabilities": [1.0, 2.0],
        }
    )
    cell_registry = pd.DataFrame({"cell_id": ["cell::1"]})
    cell_state = pd.DataFrame(
        {
            "cell_id": ["cell::1"],
            "region_numeric": [0],
            "sector_numeric": [0],
            "population": [4.2948885745430835e29],
            "employment": [4.2948885745430835e29],
            "output": [1000.0],
            "distress_score": [5.0],
            "public_service_index": [3.0],
        }
    )

    payload = _build_synthetic_multiscale_payload(runtime_agents, cell_registry, cell_state)

    assert payload["cells"]["population"] == [1_000_000_000.0]
    assert payload["cells"]["employment"] == [1_000_000_000.0]
    assert payload["cells"]["distress_score"] == [1.0]
    assert payload["cells"]["public_service_index"] == [1.0]


def test_build_d4_stage_emits_only_a_purpose_limited_governance_handoff(tmp_path) -> None:
    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    result = build_d4_stage(config)

    assert not result.findings
    assert set(result.outputs) == {"d4_governance_request.json"}
    request = json.loads(
        (config.build_root.calibration_dir / "d4" / "d4_governance_request.json").read_text(
            encoding="utf-8"
        )
    )
    assert request["authority_purpose"] == "producer_governance_handoff"
    assert "governance_admissibility" in request["may_not_use_for"]
    assert "coverage_threshold" not in request
    assert "waived_signoff_families" not in request
    assert "governance_verdict" not in request


def test_family_eligibility_registry_respects_signoff_waivers() -> None:
    observation_panel = pd.DataFrame(
        {
            "family": ["budget_flows", "procurement_flows"],
            "coverage_estimate": [0.97, 0.60],
            "measurement_bias_flag": [False, False],
            "source_id": ["budget_transactions", "spending_contracts_procurement_proxy"],
            "identification_mode": ["point_identified", "proxy_identified"],
            "source_confidence_tier": ["validated", "validated"],
            "proxy_source_id": [None, "spending_contracts_procurement_proxy"],
        }
    )

    registry = build_family_eligibility_registry(
        observation_panel,
        coverage_threshold=0.95,
        spending_coverage=0.97,
        procurement_coverage=0.60,
        waived_families=[ObservationFamily.PROCUREMENT_FLOWS],
    )

    procurement_entry = registry.families[ObservationFamily.PROCUREMENT_FLOWS.value]
    assert procurement_entry.signoff_waived is True
    assert procurement_entry.tier.value == "B"
    assert "signoff_waived_by_policy" in procurement_entry.reasons
    registry.require_final_signoff_ready(
        [ObservationFamily.BUDGET_FLOWS, ObservationFamily.PROCUREMENT_FLOWS]
    )


def test_strategic_required_channel_count_excludes_waived_families() -> None:
    assert StrategicResponseRunner.required_channel_count() == 3
    assert (
        StrategicResponseRunner.required_channel_count(
            waived_families=[ObservationFamily.PROCUREMENT_FLOWS]
        )
        == 2
    )


def test_edr_identity_bridge_resolves_unique_supplier_name_match(tmp_path) -> None:
    agent_registry = pd.DataFrame(
        {
            "agent_id": ["agent::one", "agent::two"],
            "registration_code": ["11111111", "22222222"],
            "region_code": ["01", "02"],
            "name": ["ACME TRADE LLC", "BETA SERVICES"],
        }
    )
    unresolved_rows = pd.DataFrame(
        {
            "raw_registration_code": ["99999999"],
            "normalized_raw_registration_code": ["99999999"],
            "source_family": ["procurement_flows"],
            "source_id": ["spending_contracts_procurement_proxy"],
            "counterparty_name": ["ACME TRADE LLC"],
            "counterparty_name_key": ["ACME TRADE LLC"],
            "region_code": [None],
            "period_id": ["2025-01"],
            "amount_weight": [1500.0],
            "observation_count": [1],
        }
    )

    unresolved, candidates, resolved, manifest = _build_edr_identity_bridge(
        build_root=build_default_pipeline_config(root=tmp_path / "ukraine").build_root,
        agent_registry=agent_registry,
        unresolved_rows=unresolved_rows,
    )

    assert len(unresolved) == 1
    assert len(candidates) == 1
    assert len(resolved) == 1
    assert resolved.iloc[0]["agent_id"] == "agent::one"
    assert manifest["resolved_matches"] == 1

    augmented = _augment_lookup_with_identity_bridge({}, resolved)
    assert _resolve_agent_id("99999999", augmented) == "agent::one"


def test_filter_identity_bridge_inputs_requires_name_without_seed() -> None:
    unresolved_rows = pd.DataFrame(
        {
            "normalized_raw_registration_code": ["11111111", "22222222"],
            "counterparty_name_key": ["named supplier", ""],
            "amount_weight": [10.0, 20.0],
        }
    )

    filtered = _filter_identity_bridge_inputs(
        unresolved_rows,
        pd.DataFrame(columns=["normalized_raw_registration_code", "agent_id"]),
    )

    assert filtered["normalized_raw_registration_code"].tolist() == ["11111111"]


def test_filter_identity_bridge_inputs_keeps_seeded_codes_without_name() -> None:
    unresolved_rows = pd.DataFrame(
        {
            "normalized_raw_registration_code": ["11111111", "22222222"],
            "counterparty_name_key": ["", ""],
            "amount_weight": [10.0, 20.0],
        }
    )
    seed_frame = pd.DataFrame(
        {
            "normalized_raw_registration_code": ["22222222"],
            "agent_id": ["agent::seeded"],
            "match_method": ["manual_seed"],
            "match_confidence": [1.0],
        }
    )

    filtered = _filter_identity_bridge_inputs(unresolved_rows, seed_frame)

    assert filtered["normalized_raw_registration_code"].tolist() == ["22222222"]


def test_build_unique_name_lookup_filters_to_requested_name_keys() -> None:
    agent_registry = pd.DataFrame(
        {
            "agent_id": ["agent::one", "agent::two"],
            "registration_code": ["11111111", "22222222"],
            "region_code": ["01", "02"],
            "name": ["ACME TRADE LLC", "BETA SERVICES"],
        }
    )

    lookup = _build_unique_name_lookup(
        agent_registry,
        allowed_name_keys={"ACME TRADE LLC"},
    )

    assert set(lookup) == {"ACME TRADE LLC"}
    assert lookup["ACME TRADE LLC"]["agent_id"] == "agent::one"


def test_aggregate_employment_admin_panel_normalizes_region_names() -> None:
    employment_service = pd.DataFrame(
        {
            "region_code": ["Вінницька", "Україна"],
            "period_id": ["2023-01", "2023-01"],
            "employment_count": [10.0, 100.0],
            "vacancies": [1.0, 0.0],
        }
    )

    aggregated = _aggregate_employment_admin_panel(employment_service)

    assert set(aggregated["region_code"]) == {"05", "00"}


def test_build_household_distribution_observation_panel_emits_exact_family_rows() -> None:
    calibrated_household_cells = pd.DataFrame(
        {
            "cell_id": ["cell::05::household_distribution"],
            "region_code": ["05"],
            "period_id": ["2018-12"],
            "household_income_mean": [123.0],
            "measurement_bias_flag": [False],
            "trust_weight": [0.95],
        }
    )

    observation_panel = _build_household_distribution_observation_panel(calibrated_household_cells)

    assert len(observation_panel) == 1
    assert observation_panel.iloc[0]["family"] == ObservationFamily.HOUSEHOLD_DISTRIBUTION.value
    assert observation_panel.iloc[0]["identification_mode"] == "point_identified"
    assert observation_panel.iloc[0]["source_confidence_tier"] == "core"


def test_build_labor_validation_artifacts_reports_temporal_gap() -> None:
    labor = pd.DataFrame(
        {
            "region_code": ["05", "05"],
            "period_id": ["2020-12", "2021-12"],
            "weight": [1.0, 1.0],
            "participation_rate": [1.0, 1.0],
            "employment_flag": [1.0, 1.0],
            "informal_employment_flag": [0.0, 0.0],
        }
    )
    household = pd.DataFrame(columns=["region_code", "period_id", "income", "weight"])
    employment_service = pd.DataFrame(
        {
            "region_code": ["Вінницька"],
            "period_id": ["2023-01"],
            "employment_count": [10.0],
            "vacancies": [1.0],
        }
    )
    macro = pd.DataFrame(columns=["metric_id", "observed_value", "region_code", "period_id"])

    _, _, report = _build_labor_validation_artifacts(
        labor=labor,
        household=household,
        employment_service=employment_service,
        macro=macro,
    )

    assert report["bias_validated"] is False
    assert "no_temporal_overlap_between_micro_and_admin_labor_panels" in report["rationale"]


def test_family_eligibility_registry_promotes_bias_validated_labor_proxy() -> None:
    observation_panel = pd.DataFrame(
        {
            "family": ["labor_market"],
            "coverage_estimate": [0.95],
            "measurement_bias_flag": [False],
            "source_id": ["employment_service"],
            "identification_mode": ["proxy_identified"],
            "source_confidence_tier": ["validated"],
            "proxy_source_id": ["employment_service_proxy"],
        }
    )

    registry = build_family_eligibility_registry(
        observation_panel,
        coverage_threshold=0.95,
        proxy_promoted_families=[ObservationFamily.LABOR_MARKET],
    )

    labor_entry = registry.families[ObservationFamily.LABOR_MARKET.value]
    assert labor_entry.tier.value == "A"
    assert labor_entry.eligible_for_scoring is True
    assert "proxy_promoted_via_bias_validation" in labor_entry.reasons


def test_build_d3_stage_emits_labor_validation_artifacts(tmp_path) -> None:
    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    normalized = config.build_root.normalized_dir
    for source_id, artifact_name, frame in (
        (
            "household_microdata",
            "household_synthetic_targets.parquet",
            pd.DataFrame(
                {
                    "household_id": ["hh::1", "hh::2"],
                    "cell_id": [
                        "cell::01::household_distribution",
                        "cell::02::household_distribution",
                    ],
                    "period_id": ["2025-12", "2025-12"],
                    "income": [1000.0, 800.0],
                    "weight": [1.0, 1.0],
                    "market_income": [900.0, 700.0],
                    "region_code": ["01", "02"],
                }
            ),
        ),
        (
            "labor_force_microdata",
            "labor_force_micro_targets.parquet",
            pd.DataFrame(
                {
                    "household_id": ["lfs::1", "lfs::2", "lfs::3", "lfs::4"],
                    "cell_id": [
                        "cell::01::labor_market",
                        "cell::01::labor_market",
                        "cell::02::labor_market",
                        "cell::02::labor_market",
                    ],
                    "period_id": ["2025-12"] * 4,
                    "participation_rate": [0.9, 0.8, 0.6, 0.5],
                    "weight": [1.0, 1.0, 1.0, 1.0],
                    "employment_flag": [0.8, 0.7, 0.4, 0.5],
                    "informal_employment_flag": [0.1, 0.2, 0.1, 0.1],
                    "region_code": ["01", "01", "02", "02"],
                }
            ),
        ),
        (
            "pfu_debt",
            "arrears_panel_monthly.parquet",
            pd.DataFrame(
                {"agent_id": ["agent::1"], "period_id": ["2025-12"], "debt_amount": [10.0]}
            ),
        ),
        (
            "wage_arrears",
            "wage_arrears_panel_monthly.parquet",
            pd.DataFrame(
                {"agent_id": ["agent::1"], "period_id": ["2025-12"], "arrears_amount": [5.0]}
            ),
        ),
        (
            "distress_events",
            "distress_events_panel_monthly.parquet",
            pd.DataFrame(
                {
                    "agent_id": ["agent::1"],
                    "period_id": ["2025-12"],
                    "months_to_event": [12],
                    "event_flag": [1],
                }
            ),
        ),
        (
            "employment_service",
            "labor_market_panel_monthly.parquet",
            pd.DataFrame(
                {
                    "agent_id": ["agent::a", "agent::b"],
                    "region_code": ["01", "02"],
                    "period_id": ["2025-12", "2025-12"],
                    "employment_count": [80.0, 45.0],
                    "vacancies": [10.0, 6.0],
                }
            ),
        ),
        (
            "macro_nbu_derzhstat",
            "macro_panel_monthly.parquet",
            pd.DataFrame(
                {
                    "metric_id": ["employment_index", "employment_index"],
                    "observed_value": [0.82, 0.48],
                    "region_code": ["01", "02"],
                    "period_id": ["2025-12", "2025-12"],
                }
            ),
        ),
    ):
        source_dir = normalized / source_id
        source_dir.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(source_dir / artifact_name, index=False)

    result = build_d3_stage(config)

    assert "labor_validation_panel.parquet" in result.outputs
    assert "labor_market_corrected_panel.parquet" in result.outputs
    assert "labor_bias_validation.json" in result.outputs
    report = json.loads(
        (config.build_root.calibration_dir / "d3" / "labor_bias_validation.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["family"] == "labor_market"
    assert report["overlap_rows"] >= 1


def test_build_d5_stage_emits_only_a_purpose_limited_release_handoff_request(tmp_path) -> None:
    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    runtime_dir = config.build_root.runtime_dir / "d0_p0"
    d1_dir = config.build_root.runtime_dir / "d1"
    d2_dir = config.build_root.calibration_dir / "d2"
    d3_dir = config.build_root.calibration_dir / "d3"
    d4_dir = config.build_root.calibration_dir / "d4"
    for directory in (runtime_dir, d1_dir, d2_dir, d3_dir, d4_dir):
        directory.mkdir(parents=True, exist_ok=True)

    runtime_agents = pd.DataFrame(
        {
            "agent_id": ["agent::1", "agent::2", "agent::3"],
            "cell_id": ["cell::01", "cell::01", "cell::02"],
            "region_code": ["01", "01", "02"],
            "revenue": [100.0, 120.0, 80.0],
            "assets": [50.0, 55.0, 40.0],
            "liabilities": [10.0, 12.0, 8.0],
            "employees": [5.0, 6.0, 4.0],
        }
    )
    runtime_agents.to_parquet(runtime_dir / "agent_registry_runtime.parquet", index=False)
    cell_registry = pd.DataFrame(
        {
            "cell_id": ["cell::01", "cell::02"],
            "region_code": ["01", "02"],
            "sector_id": ["A", "B"],
            "agent_count": [2, 1],
        }
    )
    cell_registry.to_parquet(runtime_dir / "cell_registry_region_sector.parquet", index=False)
    pd.DataFrame({"cell_id": ["cell::01", "cell::02"], "lat": [1.0, 2.0]}).to_parquet(
        runtime_dir / "geo_index_runtime.parquet",
        index=False,
    )
    (runtime_dir / "runtime_bundle_manifest.json").write_text("{}", encoding="utf-8")
    (runtime_dir / "slot_family_manifest.json").write_text("{}", encoding="utf-8")

    calibrated_cells = pd.DataFrame(
        {
            "cell_id": ["cell::01", "cell::02"],
            "household_income": [1000.0, 800.0],
            "employment_rate": [0.8, 0.75],
        }
    )
    calibrated_cells.to_parquet(d3_dir / "calibrated_household_cells.parquet", index=False)

    for directory, name in (
        (runtime_dir, "budget_graph_sparse.npz"),
        (runtime_dir, "procurement_graph_sparse.npz"),
        (d1_dir, "trade_graph_sparse.npz"),
        (d1_dir, "distress_graph_sparse.npz"),
        (d1_dir, "public_service_graph_sparse.npz"),
    ):
        np.savez_compressed(
            directory / name,
            node_ids=np.asarray(["agent::1", "agent::2", "agent::3"], dtype=object),
            src_ids=np.asarray(["agent::1", "agent::2"], dtype=object),
            dst_ids=np.asarray(["agent::2", "agent::3"], dtype=object),
            src_index=np.asarray([0, 1], dtype=int),
            dst_index=np.asarray([1, 2], dtype=int),
            weight=np.asarray([1.0, 2.0], dtype=float),
            period_id=np.asarray(["2025-01", "2025-01"], dtype=object),
        )

    (d2_dir / "calibration_bundle_manifest.json").write_text("{}", encoding="utf-8")
    pd.DataFrame({"family": ["budget_flows"], "observed_value": [1.0]}).to_parquet(
        d2_dir / "observation_panel_monthly.parquet",
        index=False,
    )
    pd.DataFrame({"family": ["macro_state"], "observed_value": [1.0]}).to_parquet(
        d2_dir / "observation_panel_annual.parquet",
        index=False,
    )
    (d2_dir / "observation_to_contract_manifest.json").write_text("{}", encoding="utf-8")
    (d2_dir / "network_contract_bundle_v1.json").write_text("{}", encoding="utf-8")
    (d2_dir / "network_causal_contract_bundle_v1.json").write_text("{}", encoding="utf-8")
    (d2_dir / "bounds_estimation_bundle_v1.json").write_text("{}", encoding="utf-8")
    (d2_dir / "backtest_plan_bundle.json").write_text("{}", encoding="utf-8")

    d4_result = build_d4_stage(config)
    assert set(d4_result.outputs) == {"d4_governance_request.json"}
    result = build_d5_stage(config)

    assert not any(finding.severity == "error" for finding in result.findings)
    assert any(
        finding.code == "downstream_release_authority_not_established"
        for finding in result.findings
    )
    assert set(result.outputs) == set(config.stages[StageId.D5.value].output_artifacts)
    assert "d5_release_handoff_request.json" in result.outputs
    assert not {
        "lex_intervention_map.json",
        "intervention_knob_dictionary.json",
        "temporal_intervention_sequences.json",
        "policy_scenario_templates.json",
        "provision_to_program_crosswalk.parquet",
        "advanced_policy_trials.json",
        "release_acceptance_report.json",
    }.intersection(result.outputs)
    handoff = D5ReleaseHandoffRequest.model_validate_json(
        (config.build_root.bundles_dir / "d5" / "d5_release_handoff_request.json").read_bytes()
    )
    assert handoff.authority_purpose == "producer_release_handoff_request"
    assert handoff.capability_state == "bridge_missing"
    assert handoff.consumer_state == "consumer_missing"
    assert set(handoff.may_not_use_for) == {
        "legal_intervention_compilation",
        "governance_admissibility",
        "release_acceptance",
        "publication",
    }
    assert handoff.producer_facts.model_dump(mode="json") == {
        "graph_compression_degree_preservation_score": 1.0,
        "graph_compression_edge_weight_reconstruction_error": 0.0,
        "primary_region_id": "01",
        "primary_sector_id": "A",
    }
    assert set(handoff.content_refs) == {
        "cell_registry",
        "d4_governance_request",
        "graph_compression_bundle",
    }
    assert all(record.sha256 for record in handoff.content_refs.values())
    with pytest.raises(ValidationError, match="unexpected_authority"):
        D5ReleaseHandoffRequest.model_validate(
            {**handoff.model_dump(mode="json"), "unexpected_authority": True}
        )
    with pytest.raises(ValidationError, match="frozen"):
        handoff.authority_purpose = "release_acceptance"
    manifest = json.loads(
        (config.build_root.bundles_dir / "d5" / "release_manifest_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert set(manifest["evidence_refs"]) == {
        "cell_registry",
        "d4_governance_request",
        "d5_release_handoff_request",
        "graph_compression_bundle",
    }
    assert manifest["lineage"]["authority_purpose"] == "producer_bundle_inventory"
    assert manifest["lineage"]["capability_state"] == "bridge_missing"
    assert "publication" in manifest["lineage"]["may_not_use_for"]
    assert "intervention_bundle_v1" not in manifest["bundles"]
    assert "governance_report_v1" not in manifest["bundles"]
    assert "acceptance_contract_bundle.json" not in manifest["bundle_contents"][
        "method_contract_bundle_v1"
    ]
    compression = json.loads(
        (config.build_root.bundles_dir / "d5" / "graph_compression_bundle.json").read_text(
            encoding="utf-8"
        )
    )
    assert compression["fidelity_metrics"]["downstream_policy_response_stability"] == {
        "status": "not_established",
        "reason": "requires the absent D5 downstream bridge and consumer",
    }
    release_report = run_verified_ukraine_d5_release(
        build_root=config.build_root.root,
        release_manifest_path=config.build_root.bundles_dir / "d5" / "release_manifest_v1.json",
        runtime_bundle_dir=config.build_root.bundles_dir / "d5" / "runtime_bundle_v1",
        method_contract_bundle_dir=(
            config.build_root.bundles_dir / "d5" / "method_contract_bundle_v1"
        ),
        cas_root=tmp_path / "release-cas",
    )
    assert release_report.passed is False
    assert release_report.governance_verdict == "reject"
    assert release_report.release_admissibility_status == "blocked"
    assert "d4_governance_not_established" in release_report.notes
    assert release_report.admission_receipt_ref
    assert release_report.foundry_receipt_ref
    assert release_report.postflight_receipt_ref
    assert release_report.packet_ref


def test_d5_release_builder_has_no_lex_or_foundry_imports() -> None:
    """Keep D5 producer-only until a downstream bridge is explicitly wired."""

    release_path = (
        Path(__file__).parents[5]
        / "src/polisyos/data_forge/domains/ukraine/builders/release.py"
    )
    tree = ast.parse(release_path.read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert not any(
        module.startswith(("polisyos.lex", "polisyos.foundry")) for module in imported_modules
    )
