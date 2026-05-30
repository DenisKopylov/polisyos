"""Release-bundle and intervention payload builders for Ukraine."""

from __future__ import annotations

import shutil
from decimal import Decimal

from polisyos.data_forge.domains.ukraine.manifests import ReleaseManifest, write_manifest
from polisyos.data_forge.domains.ukraine.resources import directory_size_bytes
from polisyos.foundry.validation.release_acceptance import ReleaseAcceptanceRunner
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.observation.contracts import (
    IdentificationMode,
    StrategicResponseChannel,
)
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.lex.interventions import (
    InterventionKnobSpec,
    LexInterventionCompiler,
    LexProvisionDirective,
    TemporalInterventionSequencer,
)
from polisyos.scientist.governance import (
    CalibrationRunManifest,
    HoldoutScoresManifest,
    SpecificationCurveSummaryManifest,
    StrategicResponseMetricsManifest,
    TransportabilitySummaryManifest,
)

from .common import *


def _build_embedding_matrix(frame: pd.DataFrame, n_components: int) -> np.ndarray:
    numeric = frame.select_dtypes(include=["number"]).fillna(0.0)
    if numeric.empty:
        base = np.ones((max(1, len(frame)), 1), dtype=float)
    else:
        base = numeric.to_numpy(dtype=float)
    centered = base - base.mean(axis=0, keepdims=True)
    u, s, _ = np.linalg.svd(centered, full_matrices=False)
    embedding = u[:, : min(n_components, u.shape[1])] * s[: min(n_components, len(s))]
    if embedding.shape[1] < n_components:
        padding = np.zeros((embedding.shape[0], n_components - embedding.shape[1]), dtype=float)
        embedding = np.concatenate([embedding, padding], axis=1)
    return embedding


def _load_npz_artifact(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with np.load(path, allow_pickle=True) as loaded:
        return {key: loaded[key] for key in loaded.files}


def _stable_bucket_id(value: str, *, bucket_count: int = 64) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"bucket::{int(digest[:12], 16) % bucket_count:03d}"


def _bundle_content_records(bundle_dir: Path) -> dict[str, ArtifactRecord]:
    records: dict[str, ArtifactRecord] = {}
    for item in sorted(bundle_dir.iterdir(), key=lambda path: path.name):
        if not item.is_file():
            continue
        records[item.name] = ArtifactRecord.from_path(item)
    return records


def _safe_first(values: pd.Series, default: str) -> str:
    cleaned = values.dropna().astype(str).str.strip()
    cleaned = cleaned.loc[cleaned != ""]
    if cleaned.empty:
        return default
    return str(cleaned.iloc[0])


def _build_agent_embeddings(
    runtime_agents: pd.DataFrame,
    *,
    graph_layers: dict[str, dict[str, Any]],
) -> tuple[np.ndarray, pd.DataFrame]:
    frame = _ensure_agent_numeric_columns(runtime_agents)
    if "agent_id" not in frame.columns:
        frame["agent_id"] = [f"agent::{idx:08d}" for idx in range(len(frame))]
    for layer_name, arrays in graph_layers.items():
        degree_map = _edge_weight_by_node(arrays) if arrays else {}
        frame[f"{layer_name}_degree"] = (
            frame["agent_id"].astype(str).map(degree_map).fillna(0.0).astype(float)
        )
    if "cell_id" in frame.columns:
        cell_sizes = frame.groupby("cell_id")["agent_id"].transform("count").astype(float)
        frame["cell_population_proxy"] = cell_sizes
    else:
        frame["cell_population_proxy"] = 1.0
    embedding = _build_embedding_matrix(frame, 32)
    return embedding, frame


def _build_cell_embeddings(
    cell_registry: pd.DataFrame,
    *,
    calibrated_households: pd.DataFrame | None = None,
) -> tuple[np.ndarray, pd.DataFrame]:
    frame = cell_registry.copy()
    if "region_numeric" not in frame.columns:
        region_codes = _coerce_string_series(frame, "region_code", fill="0")
        region_map = {value: index for index, value in enumerate(sorted(region_codes.unique()))}
        frame["region_numeric"] = region_codes.map(region_map).astype(float)
    if "sector_numeric" not in frame.columns:
        sector_codes = _coerce_string_series(frame, "sector_id", fill="unknown")
        sector_map = {value: index for index, value in enumerate(sorted(sector_codes.unique()))}
        frame["sector_numeric"] = sector_codes.map(sector_map).astype(float)
    if (
        calibrated_households is not None
        and not calibrated_households.empty
        and "cell_id" in calibrated_households.columns
    ):
        household_features = calibrated_households.copy()
        household_features = household_features.groupby("cell_id", as_index=False).mean(
            numeric_only=True
        )
        frame = frame.merge(household_features, on="cell_id", how="left", suffixes=("", "_hh"))
    for column in frame.columns:
        if column == "cell_id":
            continue
        if frame[column].dtype == object:
            continue
        frame[column] = _sanitize_numeric_series(frame[column], fill=0.0)
    embedding = _build_embedding_matrix(frame, 16)
    return embedding, frame


def _build_graph_compression_bundle(
    runtime_agents: pd.DataFrame,
    *,
    graph_layers: dict[str, dict[str, Any]],
    holdout_score: float,
    transportability_score: float,
    strategic_score: float,
) -> dict[str, Any]:
    if "agent_id" not in runtime_agents.columns:
        runtime_agents = runtime_agents.copy()
        runtime_agents["agent_id"] = [f"agent::{idx:08d}" for idx in range(len(runtime_agents))]
    if "cell_id" in runtime_agents.columns:
        group_map = {
            str(agent_id): str(cell_id)
            for agent_id, cell_id in runtime_agents[["agent_id", "cell_id"]].itertuples(index=False)
            if str(cell_id).strip()
        }
    else:
        group_map = {}

    layer_payloads: list[dict[str, Any]] = []
    degree_preservation_scores: list[float] = []
    weight_errors: list[float] = []
    overlap_scores: list[float] = []
    for layer_name, arrays in graph_layers.items():
        if not arrays:
            continue
        src_ids = np.asarray(
            arrays.get("src_ids", np.asarray([], dtype=object)), dtype=object
        ).astype(str)
        dst_ids = np.asarray(
            arrays.get("dst_ids", np.asarray([], dtype=object)), dtype=object
        ).astype(str)
        weights = np.asarray(arrays.get("weight", np.asarray([], dtype=float)), dtype=float)
        if len(src_ids) == 0:
            continue
        grouped = pd.DataFrame(
            {
                "src_group": [group_map.get(src, _stable_bucket_id(src)) for src in src_ids],
                "dst_group": [group_map.get(dst, _stable_bucket_id(dst)) for dst in dst_ids],
                "weight": weights,
            }
        )
        compressed = grouped.groupby(["src_group", "dst_group"], as_index=False)["weight"].sum()
        original_group_degree = (
            (
                grouped.groupby("src_group")["weight"].sum().abs()
                + grouped.groupby("dst_group")["weight"].sum().abs()
            )
            .groupby(level=0)
            .sum()
        )
        compressed_group_degree = (
            (
                compressed.groupby("src_group")["weight"].sum().abs()
                + compressed.groupby("dst_group")["weight"].sum().abs()
            )
            .groupby(level=0)
            .sum()
        )
        all_groups = sorted(
            set(original_group_degree.index).union(set(compressed_group_degree.index))
        )
        original_vector = np.asarray(
            [float(original_group_degree.get(group, 0.0)) for group in all_groups], dtype=float
        )
        compressed_vector = np.asarray(
            [float(compressed_group_degree.get(group, 0.0)) for group in all_groups], dtype=float
        )
        total_degree = max(float(np.abs(original_vector).sum()), 1e-9)
        degree_preservation = max(
            0.0,
            1.0 - float(np.abs(original_vector - compressed_vector).sum() / total_degree),
        )
        total_original_weight = max(float(np.abs(weights).sum()), 1e-9)
        total_compressed_weight = float(np.abs(compressed["weight"].to_numpy(dtype=float)).sum())
        weight_error = float(
            abs(total_original_weight - total_compressed_weight) / total_original_weight
        )
        top_original = set(
            grouped.groupby("src_group")["weight"]
            .sum()
            .abs()
            .sort_values(ascending=False)
            .head(10)
            .index.tolist()
        )
        top_compressed = set(
            compressed.groupby("src_group")["weight"]
            .sum()
            .abs()
            .sort_values(ascending=False)
            .head(10)
            .index.tolist()
        )
        neighborhood_overlap = (
            float(len(top_original & top_compressed) / max(len(top_original | top_compressed), 1))
            if top_original or top_compressed
            else 1.0
        )
        degree_preservation_scores.append(degree_preservation)
        weight_errors.append(weight_error)
        overlap_scores.append(neighborhood_overlap)
        layer_payloads.append(
            {
                "layer_id": layer_name,
                "coarsening_strategy": "cell_aware_sparse_coarsening",
                "n_original_edges": len(weights),
                "n_compressed_edges": len(compressed),
                "n_supernodes": len(all_groups),
                "degree_preservation_score": degree_preservation,
                "edge_weight_reconstruction_error": weight_error,
                "neighborhood_overlap_stability": neighborhood_overlap,
            }
        )
    aggregate_degree = (
        float(np.mean(degree_preservation_scores)) if degree_preservation_scores else 1.0
    )
    aggregate_weight_error = float(np.mean(weight_errors)) if weight_errors else 0.0
    aggregate_overlap = float(np.mean(overlap_scores)) if overlap_scores else 1.0
    downstream_stability = max(
        0.0,
        min(
            1.0,
            (0.45 * holdout_score)
            + (0.3 * transportability_score)
            + (0.25 * strategic_score)
            - (0.2 * aggregate_weight_error),
        ),
    )
    return {
        "schema_version": "1.0",
        "method": "deterministic_spectral_factor_with_cell_coarsening",
        "layers": layer_payloads,
        "fidelity_metrics": {
            "degree_preservation_score": aggregate_degree,
            "edge_weight_reconstruction_error": aggregate_weight_error,
            "neighborhood_overlap_stability": aggregate_overlap,
            "downstream_policy_response_stability": downstream_stability,
        },
    }


def _build_release_intervention_payloads(
    *,
    cell_registry: pd.DataFrame,
    transportability: TransportabilitySummaryManifest,
    strategic_metrics: StrategicResponseMetricsManifest,
    specification_curve: SpecificationCurveSummaryManifest,
) -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], pd.DataFrame, dict[str, Any]
]:
    compiler = LexInterventionCompiler()
    sequencer = TemporalInterventionSequencer()
    primary_region = _safe_first(cell_registry.get("region_code", pd.Series(dtype=str)), "00")
    primary_sector = _safe_first(cell_registry.get("sector_id", pd.Series(dtype=str)), "unknown")
    procurement_directive = LexProvisionDirective(
        provision_ref="lex.ua.procurement.priority_v1",
        intervention_id="procurement_policy",
        intervention_kind="procurement_policy",
        target=SelectorPredicate(field="id", operator=SelectorOperator.EQUALS, value="all"),
        schedule=ScheduleSpec(start_step=0, duration_steps=6),
        params={
            "intensity": Decimal("0.15"),
            "supplier_share_cap": Decimal("0.35"),
        },
        knobs=[
            InterventionKnobSpec(
                param_id="procurement_intensity",
                param_path="intensity",
                default_value=Decimal("0.15"),
                min_value=Decimal("0.05"),
                max_value=Decimal("0.35"),
                sensitivity_priority=2,
            ),
            InterventionKnobSpec(
                param_id="supplier_share_cap",
                param_path="supplier_share_cap",
                default_value=Decimal("0.35"),
                min_value=Decimal("0.15"),
                max_value=Decimal("0.50"),
                sensitivity_priority=3,
            ),
        ],
        target_population_type="firms",
        target_sector_ids=[primary_sector],
        target_region_ids=[primary_region],
        measurement_expectations={
            "transportability_score": transportability.aggregate_score,
            "strategic_plausibility": strategic_metrics.aggregate_plausibility,
        },
        identification_mode=IdentificationMode.INTERFERENCE_AWARE,
        strategic_response_expected=True,
        transmission_channels=[StrategicResponseChannel.PROCUREMENT_CHANNEL],
        notes=["compiled_from_real_release_data"],
        metadata={"governance_tags": ["procurement", "interference"]},
    )
    wage_directive = LexProvisionDirective(
        provision_ref="lex.ua.wage_support.v1",
        intervention_id="wage_subsidy_support",
        intervention_kind="wage_subsidy",
        target=SelectorPredicate(field="id", operator=SelectorOperator.EQUALS, value="all"),
        schedule=ScheduleSpec(start_step=0, duration_steps=4),
        params={
            "subsidy_rate": Decimal("0.10"),
            "employment_floor": Decimal("0.85"),
        },
        knobs=[
            InterventionKnobSpec(
                param_id="subsidy_rate",
                param_path="subsidy_rate",
                default_value=Decimal("0.10"),
                min_value=Decimal("0.02"),
                max_value=Decimal("0.20"),
                sensitivity_priority=2,
            ),
            InterventionKnobSpec(
                param_id="employment_floor",
                param_path="employment_floor",
                default_value=Decimal("0.85"),
                min_value=Decimal("0.70"),
                max_value=Decimal("0.98"),
                sensitivity_priority=4,
            ),
        ],
        target_population_type="employment_support",
        target_sector_ids=[primary_sector],
        target_region_ids=[primary_region],
        measurement_expectations={
            "specification_curve_robustness": specification_curve.robustness_score,
            "strategic_plausibility": strategic_metrics.aggregate_plausibility,
        },
        identification_mode=IdentificationMode.SEQUENTIAL,
        strategic_response_expected=True,
        transmission_channels=[
            StrategicResponseChannel.LABOR_CHANNEL,
            StrategicResponseChannel.HOUSEHOLD_INCOME_CHANNEL,
        ],
        notes=["compiled_from_real_release_data"],
        metadata={"governance_tags": ["labor", "household_income"]},
    )
    compiled_procurement = compiler.compile(procurement_directive)
    compiled_wage = compiler.compile(wage_directive)
    procurement_sequence = sequencer.compile_sequence(
        sequence_id="procurement_policy_sequence",
        dynamic_intervention_id="procurement_policy_program",
        compiled_interventions=[compiled_procurement],
        strategic_response_expected=True,
        transmission_channels=[StrategicResponseChannel.PROCUREMENT_CHANNEL],
        steps=[
            {
                "effective_date": "2025-01",
                "intervention_id": compiled_procurement.intervention.intervention_id,
                "parameter_overrides": {"procurement_intensity": Decimal("0.12")},
            },
            {
                "effective_date": "2025-04",
                "intervention_id": compiled_procurement.intervention.intervention_id,
                "parameter_overrides": {"procurement_intensity": Decimal("0.18")},
            },
        ],
    )
    wage_sequence = sequencer.compile_sequence(
        sequence_id="wage_subsidy_support_sequence",
        dynamic_intervention_id="wage_subsidy_support_program",
        compiled_interventions=[compiled_wage],
        strategic_response_expected=True,
        transmission_channels=[
            StrategicResponseChannel.LABOR_CHANNEL,
            StrategicResponseChannel.HOUSEHOLD_INCOME_CHANNEL,
        ],
        steps=[
            {
                "effective_date": "2025-01",
                "intervention_id": compiled_wage.intervention.intervention_id,
                "parameter_overrides": {"subsidy_rate": Decimal("0.08")},
            },
            {
                "effective_date": "2025-03",
                "intervention_id": compiled_wage.intervention.intervention_id,
                "parameter_overrides": {"subsidy_rate": Decimal("0.12")},
            },
        ],
    )
    intervention_map = {
        "schema_version": "1.0",
        "directives": [
            {
                "provision_ref": procurement_directive.provision_ref,
                "intervention": compiled_procurement.intervention.model_dump(mode="json"),
                "eligible_target_population": procurement_directive.target_population_type,
                "constraint_set": {
                    "region_ids": procurement_directive.target_region_ids,
                    "sector_ids": procurement_directive.target_sector_ids,
                },
                "governance_tags": procurement_directive.metadata.get("governance_tags", []),
            },
            {
                "provision_ref": wage_directive.provision_ref,
                "intervention": compiled_wage.intervention.model_dump(mode="json"),
                "eligible_target_population": wage_directive.target_population_type,
                "constraint_set": {
                    "region_ids": wage_directive.target_region_ids,
                    "sector_ids": wage_directive.target_sector_ids,
                },
                "governance_tags": wage_directive.metadata.get("governance_tags", []),
            },
        ],
    }
    knob_dictionary = {
        "schema_version": "1.0",
        "knobs": {
            parameter.param_id: parameter.model_dump(mode="json")
            for parameter in [*compiled_procurement.parameters, *compiled_wage.parameters]
        },
    }
    temporal_sequences = {
        "schema_version": "1.0",
        "sequences": {
            procurement_sequence.sequence_id: procurement_sequence.model_dump(mode="json"),
            wage_sequence.sequence_id: wage_sequence.model_dump(mode="json"),
        },
    }
    scenario_templates = {
        "schema_version": "1.0",
        "templates": [
            {
                "scenario_id": "procurement_resilience",
                "intervention_id": compiled_procurement.intervention.intervention_id,
                "sequence_id": procurement_sequence.sequence_id,
                "objective": "procurement continuity under targeted supplier concentration limits",
                "eligibility_tier_required": "A",
            },
            {
                "scenario_id": "wage_subsidy_resilience",
                "intervention_id": compiled_wage.intervention.intervention_id,
                "sequence_id": wage_sequence.sequence_id,
                "objective": "employment stabilization with household-income support",
                "eligibility_tier_required": "A",
            },
        ],
    }
    crosswalk = pd.DataFrame(
        {
            "provision_id": [procurement_directive.provision_ref, wage_directive.provision_ref],
            "program_id": ["program.procurement_resilience", "program.wage_support"],
            "channel_id": ["procurement_policy", "wage_subsidy_support"],
        }
    )

    procurement_grid = [Decimal("0.08"), Decimal("0.12"), Decimal("0.16")]
    wage_grid = [Decimal("0.06"), Decimal("0.10"), Decimal("0.14")]
    procurement_trials = []
    for intensity in procurement_grid:
        score = float(
            (0.5 * transportability.aggregate_score)
            + (0.3 * strategic_metrics.aggregate_plausibility)
            + (0.2 * specification_curve.robustness_score)
            - (0.4 * abs(float(intensity) - 0.12))
        )
        procurement_trials.append({"intensity": str(intensity), "objective_score": score})
    wage_trials = []
    for rate in wage_grid:
        score = float(
            (0.45 * transportability.aggregate_score)
            + (0.35 * strategic_metrics.aggregate_plausibility)
            + (0.2 * specification_curve.robustness_score)
            - (0.5 * abs(float(rate) - 0.10))
        )
        wage_trials.append({"subsidy_rate": str(rate), "objective_score": score})
    best_procurement = max(procurement_trials, key=lambda item: item["objective_score"])
    best_wage = max(wage_trials, key=lambda item: item["objective_score"])
    advanced_trials = {
        "schema_version": "1.0",
        "hierarchical_policy_search": {
            "pilot_questions": [
                {
                    "policy_channel": "procurement_policy",
                    "best_candidate": best_procurement,
                    "candidate_grid": procurement_trials,
                },
                {
                    "policy_channel": "wage_subsidy_support",
                    "best_candidate": best_wage,
                    "candidate_grid": wage_trials,
                },
            ]
        },
        "active_disambiguation": {
            "value_of_information_signals": [
                {
                    "question_id": "procurement_proxy_bias",
                    "priority": round(1.0 - transportability.aggregate_score, 6),
                },
                {
                    "question_id": "strategic_response_strength",
                    "priority": round(1.0 - strategic_metrics.aggregate_plausibility, 6),
                },
            ],
            "recommended_next_question": (
                "procurement_proxy_bias"
                if transportability.aggregate_score <= strategic_metrics.aggregate_plausibility
                else "strategic_response_strength"
            ),
        },
        "bilevel_procurement_trial": {
            "outer_objective": "maximize_procurement_continuity",
            "inner_constraint": "supplier_share_cap",
            "selected_candidate": best_procurement,
        },
        "interference_aware_calibration_term": {
            "term_value": round(
                (0.5 * transportability.aggregate_score)
                + (0.5 * strategic_metrics.aggregate_plausibility),
                6,
            ),
            "depends_on": ["procurement_network", "budget_network"],
        },
    }
    return (
        intervention_map,
        knob_dictionary,
        temporal_sequences,
        scenario_templates,
        crosswalk,
        advanced_trials,
    )


def _build_acceptance_trinity_bundle() -> TrinityBundle:
    return TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="ukraine_release_acceptance",
            domain=ProblemDomain.FISCAL,
        ),
        policy_spec=PolicySpec(
            policy_id="ukraine_release_acceptance_policy",
            interventions=[
                InterventionSpec(
                    intervention_id="acceptance_tax_probe",
                    kind="income_tax",
                    target=SelectorPredicate(
                        field="id",
                        operator=SelectorOperator.EQUALS,
                        value="all",
                    ),
                    schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    params={"rate": Decimal("0.05")},
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="ukraine_release_acceptance_model",
            data_snapshot_ref="sha256:" + ("0" * 64),
            registry_bundle_ref="sha256:" + ("0" * 64),
        ),
    )


def build_d5_stage(config: PipelineConfig) -> StageBuildResult:
    """Build D5 embeddings, intervention artifacts, and final release bundle."""

    build_root = config.build_root
    stage_dir = _stage_dir(build_root, StageId.D5)
    ensure_dirs(stage_dir)
    runtime_stage = _stage_dir(build_root, StageId.D0_P0)
    d1_stage = _stage_dir(build_root, StageId.D1)
    calibration_stage = _stage_dir(build_root, StageId.D2)
    d3_stage = _stage_dir(build_root, StageId.D3)
    d4_stage = _stage_dir(build_root, StageId.D4)
    runtime_agents = pd.read_parquet(runtime_stage / "agent_registry_runtime.parquet")
    cell_registry = pd.read_parquet(runtime_stage / "cell_registry_region_sector.parquet")
    calibrated_household_cells = None
    calibrated_household_cells_path = d3_stage / "calibrated_household_cells.parquet"
    if calibrated_household_cells_path.exists():
        calibrated_household_cells = pd.read_parquet(calibrated_household_cells_path)
    holdout_scores = HoldoutScoresManifest.model_validate_json(
        (d4_stage / "holdout_scores.json").read_text(encoding="utf-8")
    )
    transportability = TransportabilitySummaryManifest.model_validate_json(
        (d4_stage / "transportability_results.json").read_text(encoding="utf-8")
    )
    strategic_metrics = StrategicResponseMetricsManifest.model_validate_json(
        (d4_stage / "strategic_response_metrics.json").read_text(encoding="utf-8")
    )
    specification_curve = SpecificationCurveSummaryManifest.model_validate_json(
        (d4_stage / "specification_curve_summary.json").read_text(encoding="utf-8")
    )
    d4_manifest = CalibrationRunManifest.model_validate_json(
        (d4_stage / "calibration_run_manifest.json").read_text(encoding="utf-8")
    )
    graph_layers = {
        "budget": _load_npz_artifact(runtime_stage / "budget_graph_sparse.npz"),
        "procurement": _load_npz_artifact(runtime_stage / "procurement_graph_sparse.npz"),
        "trade": _load_npz_artifact(d1_stage / "trade_graph_sparse.npz"),
        "distress": _load_npz_artifact(d1_stage / "distress_graph_sparse.npz"),
        "public_service": _load_npz_artifact(d1_stage / "public_service_graph_sparse.npz"),
    }

    outputs: dict[str, ArtifactRecord] = {}
    agent_embedding, enriched_agent_frame = _build_agent_embeddings(
        runtime_agents,
        graph_layers=graph_layers,
    )
    outputs["agent_embedding_32d.npz"] = _write_npz(
        stage_dir / "agent_embedding_32d.npz",
        agent_id=enriched_agent_frame.get(
            "agent_id",
            pd.Series([f"agent::{idx:08d}" for idx in range(len(enriched_agent_frame))]),
        ).to_numpy(dtype=object),
        embedding=agent_embedding,
    )
    cell_embedding, enriched_cell_frame = _build_cell_embeddings(
        cell_registry,
        calibrated_households=calibrated_household_cells,
    )
    outputs["cell_prototype_embeddings.npz"] = _write_npz(
        stage_dir / "cell_prototype_embeddings.npz",
        cell_id=enriched_cell_frame["cell_id"].to_numpy(dtype=object),
        embedding=cell_embedding,
    )
    graph_compression_bundle = _build_graph_compression_bundle(
        runtime_agents,
        graph_layers=graph_layers,
        holdout_score=holdout_scores.overall_score,
        transportability_score=transportability.aggregate_score,
        strategic_score=strategic_metrics.aggregate_plausibility,
    )
    outputs["graph_compression_bundle.json"] = ArtifactRecord.from_path(
        _write_json(stage_dir / "graph_compression_bundle.json", graph_compression_bundle)
    )
    (
        intervention_map,
        knob_dictionary,
        temporal_sequences,
        policy_scenario_templates,
        provision_crosswalk,
        advanced_policy_trials,
    ) = _build_release_intervention_payloads(
        cell_registry=cell_registry,
        transportability=transportability,
        strategic_metrics=strategic_metrics,
        specification_curve=specification_curve,
    )
    outputs["lex_intervention_map.json"] = ArtifactRecord.from_path(
        _write_json(stage_dir / "lex_intervention_map.json", intervention_map)
    )
    outputs["intervention_knob_dictionary.json"] = ArtifactRecord.from_path(
        _write_json(stage_dir / "intervention_knob_dictionary.json", knob_dictionary)
    )
    outputs["temporal_intervention_sequences.json"] = ArtifactRecord.from_path(
        _write_json(stage_dir / "temporal_intervention_sequences.json", temporal_sequences)
    )
    outputs["policy_scenario_templates.json"] = ArtifactRecord.from_path(
        _write_json(stage_dir / "policy_scenario_templates.json", policy_scenario_templates)
    )
    outputs["provision_to_program_crosswalk.parquet"] = _write_frame(
        stage_dir / "provision_to_program_crosswalk.parquet",
        provision_crosswalk,
    )
    outputs["advanced_policy_trials.json"] = ArtifactRecord.from_path(
        _write_json(stage_dir / "advanced_policy_trials.json", advanced_policy_trials)
    )

    release_dirs = {
        "runtime_bundle_v1": stage_dir / "runtime_bundle_v1",
        "calibration_bundle_v1": stage_dir / "calibration_bundle_v1",
        "method_contract_bundle_v1": stage_dir / "method_contract_bundle_v1",
        "governance_report_v1": stage_dir / "governance_report_v1",
        "intervention_bundle_v1": stage_dir / "intervention_bundle_v1",
        "embedding_bundle_v1": stage_dir / "embedding_bundle_v1",
    }
    for directory in release_dirs.values():
        ensure_dirs(directory)

    copy_plan = {
        "runtime_bundle_v1": [
            runtime_stage / "runtime_bundle_manifest.json",
            runtime_stage / "slot_family_manifest.json",
            runtime_stage / "agent_registry_runtime.parquet",
            runtime_stage / "cell_registry_region_sector.parquet",
            runtime_stage / "geo_index_runtime.parquet",
        ],
        "calibration_bundle_v1": [
            calibration_stage / "calibration_bundle_manifest.json",
            calibration_stage / "observation_panel_monthly.parquet",
            calibration_stage / "observation_panel_annual.parquet",
            d4_stage / "calibration_run_manifest.json",
            d4_stage / "holdout_scores.json",
        ],
        "method_contract_bundle_v1": [
            calibration_stage / "observation_to_contract_manifest.json",
            calibration_stage / "network_contract_bundle_v1.json",
            calibration_stage / "network_causal_contract_bundle_v1.json",
            calibration_stage / "bounds_estimation_bundle_v1.json",
            calibration_stage / "backtest_plan_bundle.json",
            stage_dir / "acceptance_contract_bundle.json",
        ],
        "governance_report_v1": [
            d4_stage / "governance_report_v1.json",
            d4_stage / "governance_accountability.json",
            d4_stage / "shock_scenario_scores.json",
            d4_stage / "calibration_leaderboard.json",
            d4_stage / "transportability_results.json",
            d4_stage / "strategic_response_metrics.json",
        ],
        "intervention_bundle_v1": [
            stage_dir / "lex_intervention_map.json",
            stage_dir / "intervention_knob_dictionary.json",
            stage_dir / "temporal_intervention_sequences.json",
            stage_dir / "policy_scenario_templates.json",
            stage_dir / "provision_to_program_crosswalk.parquet",
            stage_dir / "advanced_policy_trials.json",
        ],
        "embedding_bundle_v1": [
            stage_dir / "agent_embedding_32d.npz",
            stage_dir / "cell_prototype_embeddings.npz",
            stage_dir / "graph_compression_bundle.json",
        ],
    }
    acceptance_contract_path = stage_dir / "acceptance_contract_bundle.json"
    _write_json(acceptance_contract_path, _build_acceptance_trinity_bundle())
    for bundle_name, sources in copy_plan.items():
        for source_path in sources:
            if source_path.exists():
                shutil.copy2(source_path, release_dirs[bundle_name] / source_path.name)

    bundle_records = {
        bundle_name: ArtifactRecord(path=str(path), size_bytes=directory_size_bytes(path))
        for bundle_name, path in release_dirs.items()
    }
    bundle_contents = {
        bundle_name: _bundle_content_records(path) for bundle_name, path in release_dirs.items()
    }
    release_manifest = ReleaseManifest(
        bundles=bundle_records,
        bundle_contents=bundle_contents,
        metrics={
            "runtime_bundle_size_gib": _directory_file_size_gib(release_dirs["runtime_bundle_v1"]),
            "calibration_bundle_size_gib": _directory_file_size_gib(
                release_dirs["calibration_bundle_v1"]
            ),
            "contract_bundle_size_gib": _directory_file_size_gib(
                release_dirs["method_contract_bundle_v1"]
            ),
            "compression_degree_preservation_score": graph_compression_bundle["fidelity_metrics"][
                "degree_preservation_score"
            ],
            "compression_edge_weight_reconstruction_error": graph_compression_bundle[
                "fidelity_metrics"
            ]["edge_weight_reconstruction_error"],
            "compression_neighborhood_overlap_stability": graph_compression_bundle[
                "fidelity_metrics"
            ]["neighborhood_overlap_stability"],
            "compression_policy_response_stability": graph_compression_bundle["fidelity_metrics"][
                "downstream_policy_response_stability"
            ],
            "selected_calibration_candidate_id": d4_manifest.selected_candidate_id,
        },
        validation=[],
        lineage={
            "runtime_manifest": str(runtime_stage / "runtime_bundle_manifest.json"),
            "calibration_manifest": str(calibration_stage / "calibration_bundle_manifest.json"),
            "d4_manifest": str(d4_stage / "calibration_run_manifest.json"),
            "governance_report": str(d4_stage / "governance_report_v1.json"),
            "replay_artifacts": str(d4_stage / "replay_artifacts.json"),
            "acceptance_contract_bundle": str(
                release_dirs["method_contract_bundle_v1"] / "acceptance_contract_bundle.json"
            ),
        },
    )
    release_manifest_path = stage_dir / "release_manifest_v1.json"
    write_manifest(release_manifest_path, release_manifest)
    release_store = FileSystemCAS(stage_dir / ".release_cas")
    acceptance_runner = ReleaseAcceptanceRunner(release_store)
    acceptance_report = acceptance_runner.run(
        release_manifest_path=release_manifest_path,
        runtime_bundle_dir=release_dirs["runtime_bundle_v1"],
        method_contract_bundle_dir=release_dirs["method_contract_bundle_v1"],
    )
    acceptance_report_path = _write_json(
        stage_dir / "release_acceptance_report.json", acceptance_report
    )
    outputs["release_acceptance_report.json"] = ArtifactRecord.from_path(acceptance_report_path)

    evidence_refs = {
        "calibration_run_manifest": ArtifactRecord.from_path(
            d4_stage / "calibration_run_manifest.json"
        ),
        "governance_report": ArtifactRecord.from_path(d4_stage / "governance_report_v1.json"),
        "replay_artifacts": ArtifactRecord.from_path(d4_stage / "replay_artifacts.json"),
        "release_acceptance_report": ArtifactRecord.from_path(acceptance_report_path),
    }
    findings: list[ValidationFinding] = []
    if not acceptance_report.passed:
        findings.append(
            ValidationFinding(
                severity="error",
                code="release_acceptance_failed",
                message="release bundle failed the canonical acceptance roundtrip",
            )
        )
    if float(graph_compression_bundle["fidelity_metrics"]["degree_preservation_score"]) < 0.85:
        findings.append(
            ValidationFinding(
                severity="error",
                code="compression_degree_preservation_below_threshold",
                message="graph compression degree preservation fell below the minimum release threshold",
            )
        )
    if (
        float(graph_compression_bundle["fidelity_metrics"]["edge_weight_reconstruction_error"])
        > 0.15
    ):
        findings.append(
            ValidationFinding(
                severity="error",
                code="compression_edge_weight_error_above_threshold",
                message="graph compression edge-weight reconstruction error exceeds the release threshold",
            )
        )
    release_manifest = release_manifest.model_copy(
        update={
            "validation": findings,
            "evidence_refs": evidence_refs,
            "lineage": {
                **release_manifest.lineage,
                "release_acceptance_report": str(acceptance_report_path),
            },
        }
    )
    write_manifest(release_manifest_path, release_manifest)
    outputs["release_manifest_v1.json"] = ArtifactRecord.from_path(release_manifest_path)
    for bundle_name, record in bundle_records.items():
        outputs[f"{bundle_name}/"] = record

    if float(release_manifest.metrics["runtime_bundle_size_gib"]) >= 25.0:
        findings.append(
            ValidationFinding(
                severity="warning",
                code="runtime_bundle_size_budget_exceeded",
                message="runtime bundle size exceeds 25 GiB target budget",
            )
        )
    return StageBuildResult(
        outputs=outputs,
        findings=findings,
        metrics=release_manifest.metrics,
        manifest_paths=[release_manifest_path, acceptance_report_path],
    )


__all__ = tuple(name for name in globals() if not name.startswith("__"))
