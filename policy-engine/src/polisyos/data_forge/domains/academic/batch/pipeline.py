"""Thin orchestrator for staged academic pipeline."""

from __future__ import annotations

import asyncio
import gc
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from polisyos.data_forge.kernel.runtime import cooldown

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
    from polisyos.data_forge.kernel.pipeline.manifests import ArtifactRef

    from ._graph_staging import GraphCapacityLimits
    from .reextraction_campaign import CampaignCheckpoint, CampaignPlan, SafeJSONWriter


ClaimAdjudicationRunner = Callable[
    ["AcademicBatchConfig"], Awaitable[dict[str, int | float]]
]


@dataclass
class PipelineStats:
    """Pipeline stats public type."""

    elapsed_seconds: float = 0.0
    stage_times: dict[str, float] = field(default_factory=dict)
    metrics: dict[str, float | int | str] = field(default_factory=dict)


def _ensure_graph_inputs(
    config: AcademicBatchConfig,
    *,
    merge_and_dedup_fn,
) -> dict[str, int] | None:
    if config.merged_records_path.exists():
        return None
    return merge_and_dedup_fn(config)


async def run_academic_pipeline(
    config: AcademicBatchConfig,
    *,
    thermal: bool = False,
    claim_adjudication_runner: ClaimAdjudicationRunner | None = None,
) -> PipelineStats:
    """Run selected academic stages sequentially."""
    from polisyos.data_forge.domains.academic.batch.benchmark import run_benchmark
    from polisyos.data_forge.domains.academic.batch.conflict_resolve import run_conflict_resolve
    from polisyos.data_forge.domains.academic.batch.dedup import merge_and_dedup
    from polisyos.data_forge.domains.academic.batch.demand_harvest import run_demand_harvest
    from polisyos.data_forge.domains.academic.batch.doc_normalize import run_doc_normalize
    from polisyos.data_forge.domains.academic.batch.edge_synthesize import run_edge_synthesize
    from polisyos.data_forge.domains.academic.batch.embedder import run_embed
    from polisyos.data_forge.domains.academic.batch.graph_builder import (
        run_graph_index,
        run_graph_load,
    )
    from polisyos.data_forge.domains.academic.batch.harvester import harvest_all
    from polisyos.data_forge.domains.academic.batch.numeric_extract import run_numeric_extract
    from polisyos.data_forge.domains.academic.batch.parser import parse_raw_sources
    from polisyos.data_forge.domains.academic.batch.publish import run_publish
    from polisyos.data_forge.domains.academic.batch.qc import run_qc
    from polisyos.data_forge.domains.academic.batch.resolve_extract import run_resolve_extract
    from polisyos.data_forge.domains.academic.batch.resolve_finalize import run_resolve_finalize
    from polisyos.data_forge.domains.academic.batch.topic_select import run_topic_select

    t0 = time.monotonic()
    stats = PipelineStats()
    resolve_extract_done = False

    if "topic_select" in config.stages:
        st = time.monotonic()
        selected = await run_topic_select(config)
        stats.stage_times["topic_select"] = time.monotonic() - st
        stats.metrics.update({f"topic_select_{k}": v for k, v in selected.items()})

    if "demand_harvest" in config.stages and config.demand_harvest_enabled:
        st = time.monotonic()
        dh_metrics = await run_demand_harvest(config)
        stats.stage_times["demand_harvest"] = time.monotonic() - st
        stats.metrics.update({f"demand_harvest_{k}": v for k, v in dh_metrics.items()})

    stream_doc_handoff = "doc_normalize" in config.stages and "resolve_extract" in config.stages
    if stream_doc_handoff:
        doc_st = time.monotonic()
        doc_task = asyncio.create_task(run_doc_normalize(config))
        await asyncio.sleep(0)
        resolve_st = time.monotonic()
        stream_cfg = replace(config, stream_doc_normalize_to_resolve_extract=True)
        try:
            resolve_stats = await run_resolve_extract(stream_cfg)
        finally:
            normalized = await doc_task
        stats.stage_times["resolve_extract"] = time.monotonic() - resolve_st
        stats.metrics.update({f"resolve_extract_{k}": v for k, v in resolve_stats.items()})
        stats.stage_times["doc_normalize"] = time.monotonic() - doc_st
        stats.metrics.update({f"doc_normalize_{k}": v for k, v in normalized.items()})
        resolve_extract_done = True
    elif "doc_normalize" in config.stages:
        st = time.monotonic()
        normalized = await run_doc_normalize(config)
        stats.stage_times["doc_normalize"] = time.monotonic() - st
        stats.metrics.update({f"doc_normalize_{k}": v for k, v in normalized.items()})

    if "harvest" in config.stages:
        st = time.monotonic()
        harvested = await harvest_all(config)
        stats.stage_times["harvest"] = time.monotonic() - st
        stats.metrics["harvest_records"] = sum(len(v) for v in harvested.values())
        del harvested
        gc.collect()

    if "parse" in config.stages:
        st = time.monotonic()
        parsed = parse_raw_sources(config)
        stats.stage_times["parse"] = time.monotonic() - st
        stats.metrics["parsed_records"] = sum(parsed.values())
        del parsed
        gc.collect()

    if "resolve_extract" in config.stages and not resolve_extract_done:
        st = time.monotonic()
        resolve_stats = await run_resolve_extract(config)
        stats.stage_times["resolve_extract"] = time.monotonic() - st
        stats.metrics.update({f"resolve_extract_{k}": v for k, v in resolve_stats.items()})
        resolve_extract_done = True

    for lane_stage, lane_name in (
        ("claim_extract", "claim"),
        ("context_extract", "context"),
        ("mechanism_extract", "mechanism"),
    ):
        if lane_stage in config.stages:
            st = time.monotonic()
            previous_lane = config.extraction_lane
            config.extraction_lane = lane_name
            try:
                resolve_stats = await run_resolve_extract(config)
            finally:
                config.extraction_lane = previous_lane
            stats.stage_times[lane_stage] = time.monotonic() - st
            stats.metrics.update({f"{lane_stage}_{k}": v for k, v in resolve_stats.items()})

    if "resolve_finalize" in config.stages:
        st = time.monotonic()
        finalize_stats = run_resolve_finalize(config)
        stats.stage_times["resolve_finalize"] = time.monotonic() - st
        stats.metrics.update({f"resolve_finalize_{k}": v for k, v in finalize_stats.items()})

    if "numeric_extract" in config.stages:
        st = time.monotonic()
        numeric_stats = run_numeric_extract(config)
        stats.stage_times["numeric_extract"] = time.monotonic() - st
        stats.metrics.update({f"numeric_extract_{k}": v for k, v in numeric_stats.items()})

    if "merge_dedup" in config.stages:
        st = time.monotonic()
        merged = merge_and_dedup(config)
        stats.stage_times["merge_dedup"] = time.monotonic() - st
        stats.metrics.update({f"merge_{k}": v for k, v in merged.items()})

    if "claim_adjudicate" in config.stages:
        if claim_adjudication_runner is None:
            raise RuntimeError(
                "claim_adjudicate requires a Scientist-owned claim adjudication runner"
            )
        st = time.monotonic()
        adjudicated = await claim_adjudication_runner(config)
        stats.stage_times["claim_adjudicate"] = time.monotonic() - st
        stats.metrics.update({f"claim_adjudicate_{k}": v for k, v in adjudicated.items()})

    if "conflict_resolve" in config.stages:
        st = time.monotonic()
        resolved = run_conflict_resolve(config)
        stats.stage_times["conflict_resolve"] = time.monotonic() - st
        stats.metrics.update({f"conflict_resolve_{k}": v for k, v in resolved.items()})

    if "graph_load" in config.stages:
        if "merge_dedup" not in config.stages:
            auto_merged = _ensure_graph_inputs(config, merge_and_dedup_fn=merge_and_dedup)
            if auto_merged is not None:
                stats.metrics.update({f"merge_{k}": v for k, v in auto_merged.items()})
                stats.metrics["merge_dedup_auto"] = 1
        st = time.monotonic()
        gstats = run_graph_load(config)
        stats.stage_times["graph_load"] = time.monotonic() - st
        stats.metrics["works"] = gstats.works
        stats.metrics["estimates"] = gstats.estimates
        stats.metrics["claims"] = gstats.claims
        stats.metrics["topic_selections"] = gstats.topic_selections

    if "edge_synthesize" in config.stages:
        st = time.monotonic()
        synthesis = run_edge_synthesize(config)
        stats.stage_times["edge_synthesize"] = time.monotonic() - st
        stats.metrics.update({f"edge_synthesize_{k}": v for k, v in synthesis.items()})

    if "graph_index" in config.stages:
        st = time.monotonic()
        run_graph_index(config)
        stats.stage_times["graph_index"] = time.monotonic() - st

    if "transport_score" in config.stages:
        from polisyos.data_forge.domains.academic.batch.transport_score import run_transport_score

        st = time.monotonic()
        ts_stats = run_transport_score(config)
        stats.stage_times["transport_score"] = time.monotonic() - st
        stats.metrics.update({f"transport_{k}": v for k, v in ts_stats.items()})

    if "benchmark" in config.stages:
        st = time.monotonic()
        benchmark_stats = run_benchmark(config)
        stats.stage_times["benchmark"] = time.monotonic() - st
        stats.metrics.update({f"benchmark_{k}": v for k, v in benchmark_stats.metrics.items()})
        stats.metrics["benchmark_passed"] = int(benchmark_stats.passed)

    if "embed" in config.stages:
        st = time.monotonic()
        embedded = run_embed(config, thermal=thermal)
        stats.stage_times["embed"] = time.monotonic() - st
        stats.metrics["embedded"] = embedded

    if "qc" in config.stages:
        st = time.monotonic()
        report = run_qc(config, fail_fast=config.fail_fast_qc)
        stats.stage_times["qc"] = time.monotonic() - st
        stats.metrics["qc_passed"] = int(report.passed)

    if "publish" in config.stages:
        st = time.monotonic()
        manifest = run_publish(config)
        stats.stage_times["publish"] = time.monotonic() - st
        stats.metrics["publish_manifest"] = str(manifest)

    if thermal and config.cooldown_seconds > 0:
        cooldown(float(config.cooldown_seconds))

    stats.elapsed_seconds = time.monotonic() - t0
    return stats


def run_academic_pipeline_sync(
    config: AcademicBatchConfig,
    *,
    thermal: bool = False,
    claim_adjudication_runner: ClaimAdjudicationRunner | None = None,
) -> PipelineStats:
    """Sync wrapper for non-async callers."""
    return asyncio.run(
        run_academic_pipeline(
            config,
            thermal=thermal,
            claim_adjudication_runner=claim_adjudication_runner,
        )
    )


def campaign_graph_owner_projection() -> dict[str, object]:
    """Bind the finite graph execution owners separately from provider execution.

    This is a file-byte projection, not a transitive or loaded-process attestation.
    """
    from pathlib import Path

    from polisyos.data_forge.kernel.io import sha256_file

    from .reextraction_campaign import _digest

    root = Path(__file__).resolve().parents[6]
    batch = "src/polisyos/data_forge/domains/academic/batch/"
    knowledge = "src/polisyos/data_forge/domains/academic/knowledge/"
    paths = (
        *(batch + name for name in (
            "pipeline.py", "graph_builder.py", "edge_synthesize.py", "_graph_staging.py",
            "config.py", "claim_ids.py", "admitted_claim_adjudications.py",
        )),
        *(knowledge + name for name in (
            "types.py", "skg_store.py", "canonical_resolver.py", "canonical_seed.py",
        )),
        "src/polisyos/data_forge/kernel/pipeline/manifests.py",
        "src/polisyos/data_forge/kernel/io/hashing.py",
        "src/polisyos/data_forge/kernel/io/atomic.py",
        "uv.lock",
    )
    sources = {path: "sha256:" + sha256_file(root / path) for path in paths}
    return {"sources": sources, "content_hash": _digest(sources)}


def _complete_campaign_graph_inputs(
    checkpoint: CampaignCheckpoint,
) -> tuple[int, str, dict[str, int], bool]:
    from .reextraction_campaign import _completed_projection, _contains_synthetic

    # Reuse the complete-frame owner without changing historical inputs.
    checkpoint.validate_complete_frame()
    summary = checkpoint.summary()
    if summary["works"] != {"complete": checkpoint.plan.input_count}:
        raise ValueError("campaign_graph_inputs_incomplete")
    count, output_digest = _completed_projection(checkpoint)
    outcomes = summary["outcomes"]
    if count != checkpoint.plan.input_count or sum(outcomes.values()) != count:
        raise ValueError("campaign_graph_input_outcomes_mismatch")
    synthetic = checkpoint.plan.synthetic
    for record in checkpoint.iter_records():
        if _contains_synthetic(record):
            synthetic = True
    return count, output_digest, outcomes, synthetic


def _validate_campaign_graph_packet(packet: object) -> dict[str, Any]:
    """Validate this owner's finite artifact grammar without coercing provenance."""
    import re

    expected = {
        "schema_version", "artifact_kind", "scope", "synthetic", "campaign_binding",
        "input_frame_digest", "completed_input_count", "completed_output_digest",
        "work_outcomes", "capacity_limits", "graph_owner_projection", "graph_metrics",
        "artifacts", "staging_usage", "input_mode", "input_execution_epoch",
        "input_owner_source_hash", "strangle_receipt",
    }
    if not isinstance(packet, dict) or set(packet) != expected:
        raise ValueError("campaign_graph_manifest_shape_mismatch")
    if (
        packet["schema_version"] != "policyos.academic.campaign_graph.v1"
        or packet["artifact_kind"] != "completed_candidate_graph"
        or packet["scope"] != "candidate_only"
        or packet["input_mode"] != "historical_source_epoch"
        or packet["input_execution_epoch"] not in {"v1", "v2"}
        or type(packet["synthetic"]) is not bool
        or type(packet["completed_input_count"]) is not int
        or packet["completed_input_count"] <= 0
    ):
        raise ValueError("campaign_graph_manifest_scope_mismatch")
    for name in (
        "campaign_binding", "input_frame_digest", "completed_output_digest",
        "input_owner_source_hash",
    ):
        if not isinstance(packet[name], str) or not re.fullmatch(
            r"sha256:[a-f0-9]{64}", packet[name],
        ):
            raise ValueError("campaign_graph_manifest_hash_malformed")
    for name in (
        "work_outcomes", "capacity_limits", "graph_metrics", "graph_owner_projection",
        "staging_usage", "strangle_receipt",
    ):
        if not isinstance(packet[name], dict):
            raise ValueError("campaign_graph_manifest_projection_malformed")
    if not isinstance(packet["artifacts"], list) or not packet["artifacts"]:
        raise ValueError("campaign_graph_manifest_artifacts_missing")
    from polisyos.data_forge.kernel.pipeline.manifests import ManifestArtifact

    paths: set[str] = set()
    for item in packet["artifacts"]:
        entry = ManifestArtifact.model_validate(item)
        if not entry.sha256 or entry.path in paths:
            raise ValueError("campaign_graph_manifest_artifact_identity_mismatch")
        paths.add(entry.path)
    return packet



@dataclass(frozen=True)
class GraphStagingStrangleReceipt:
    """Recomputed run use of disk staging; migration equivalence is a release proof."""

    synthetic: bool
    default_flipped: bool
    campaign_binding: str
    completed_output_digest: str
    graph_owner_projection_hash: str
    stages: dict[str, dict[str, Any]]
    schema_version: str = field(default="policyos.academic.graph_staging_strangle.v1", init=False)
    scope: str = field(default="candidate_only", init=False)
    predicate_posture: str = field(default="recomputed", init=False)
    predicate: str = field(
        default="both_default_staging_owners_consumed_with_bound_limits", init=False,
    )
    legacy_path: str = field(default="resident_corpus_collections", init=False)
    replacement_path: str = field(default="bounded_disk_staging", init=False)
    migration_equivalence: str = field(default="not_established_by_this_run", init=False)


def _recompute_graph_staging_strangle(
    checkpoint: CampaignCheckpoint, build_root: Path, *, limits: GraphCapacityLimits,
    synthetic: bool, output_digest: str, source_projection: dict[str, Any],
) -> GraphStagingStrangleReceipt:
    from dataclasses import asdict

    from polisyos.data_forge.kernel.io import sha256_file

    from ._graph_staging import read_staging_usage

    stages = {}
    default_flipped = True
    for name, filename in (("graph_load", "graph-load.sqlite"),
                           ("edge_synthesize", "edge-synthesize.sqlite")):
        path = build_root / "staging" / filename
        usage = read_staging_usage(path)
        if usage.get("applied_limits") != asdict(limits):
            raise ValueError("campaign_graph_staging_limits_mismatch")
        operations = usage.get("namespace_operations")
        if not isinstance(operations, dict):
            raise ValueError("campaign_graph_staging_operations_missing")
        exercised = False
        for namespace, entry in operations.items():
            if (not isinstance(namespace, str) or not namespace or not isinstance(entry, dict)
                    or set(entry) != {"kind", "writes", "batches"}
                    or entry["kind"] not in {"rows", "values", "counts", "groups", "pairs"}
                    or any(type(entry[key]) is not int or entry[key] < 0
                           for key in ("writes", "batches"))):
                raise ValueError("campaign_graph_staging_operations_malformed")
            exercised |= entry["writes"] > 0 or entry["batches"] > 0
        default_flipped &= exercised
        stages[name] = {
            "path": path.relative_to(checkpoint.root).as_posix(),
            "sha256": sha256_file(path), "usage": usage,
            "actual_staging_operations_exercised": exercised,
        }
    return GraphStagingStrangleReceipt(
        synthetic=synthetic, default_flipped=default_flipped,
        campaign_binding=checkpoint._binding, completed_output_digest=output_digest,
        graph_owner_projection_hash=source_projection["content_hash"], stages=stages,
    )


def _campaign_graph_artifact_paths(config: AcademicBatchConfig) -> tuple[Path, ...]:
    """Project the complete outputs of the two graph owners used by this bridge."""
    return (
        config.db_path, config.canonical_review_queue_path,
        config.edge_synthesis_report_path, config.manifests_dir / "edge_synthesize.json",
    )


def _require_campaign_graph_artifact_set(
    packet: dict[str, Any], config: AcademicBatchConfig, checkpoint_root: Path,
) -> None:
    expected = {
        path.relative_to(checkpoint_root).as_posix()
        for path in _campaign_graph_artifact_paths(config)
    }
    observed = {item["path"] for item in packet["artifacts"]}
    if observed != expected:
        raise ValueError("campaign_graph_artifact_membership_mismatch")


def finalize_extraction_campaign_graph(
    plan: CampaignPlan,
    checkpoint_root: Path,
    *,
    capacity_limits: GraphCapacityLimits | None = None,
    safe_write_json: SafeJSONWriter,
) -> ArtifactRef:
    """Publish an intact candidate graph built from complete durable work outputs.

    The graph is rebuilt in unique private state. A killed or refused build has
    no completed manifest and never requires another provider request. Completed
    work includes refusal/error dispositions, which remain explicit in the output.
    """
    import json
    import uuid
    from dataclasses import asdict

    from polisyos.data_forge.kernel.pipeline.manifests import ArtifactRef

    from .reextraction_campaign import CampaignCheckpoint, validate_campaign_output_root

    validate_campaign_output_root(checkpoint_root, synthetic=plan.synthetic)
    with CampaignCheckpoint.read_only_history(checkpoint_root, plan) as checkpoint:
        count, output_digest, outcomes, synthetic = _complete_campaign_graph_inputs(checkpoint)
        # Heavy owners are reached only after complete input replay succeeds.
        from polisyos.data_forge.domains.academic.knowledge.types import WorkRecord
        from polisyos.data_forge.kernel.io import sha256_file

        from ._graph_staging import (
            GraphCapacityLimits,
            publish_owned_output,
            read_staging_usage,
        )
        from .config import AcademicBatchConfig
        from .edge_synthesize import run_edge_synthesize
        from .graph_builder import load_graph

        limits = capacity_limits if capacity_limits is not None else GraphCapacityLimits()
        source_projection = campaign_graph_owner_projection()
        build_id = uuid.uuid4().hex
        build_root = checkpoint.root / "graph-builds" / build_id
        config = AcademicBatchConfig(
            snapshot_root=build_root, run_id=plan.campaign_id,
            pass_name="abstract_campaign_graph",  # noqa: S106 - existing processing-stage label
        )
        config.db_path.parent.mkdir(parents=True, exist_ok=True)
        staging = build_root / "staging"
        provenance = {
            "synthetic": synthetic, "scope": "candidate_only",
            "campaign_binding": checkpoint._binding,
            "completed_output_digest": output_digest,
            "graph_owner_projection": source_projection["content_hash"],
        }
        stats = load_graph(
            records=(WorkRecord.model_validate(record) for record in checkpoint.iter_records()),
            db_path=config.db_path, run_id=plan.campaign_id, pass_name=config.pass_name,
            config_json=json.dumps(provenance, sort_keys=True),
            capacity_limits=limits, staging_dir=staging, source_provenance=provenance,
        )
        synthesis = run_edge_synthesize(
            config, source_provenance=provenance, capacity_limits=limits, staging_dir=staging,
        )
        if campaign_graph_owner_projection() != source_projection:
            raise ValueError("campaign_graph_owner_changed_during_build")
        paths = _campaign_graph_artifact_paths(config)
        # Stable private paths preserve the existing stage manifest's references.
        artifacts = [
            {"path": path.relative_to(checkpoint.root).as_posix(), "sha256": sha256_file(path)}
            for path in paths
        ]
        strangle = _recompute_graph_staging_strangle(
            checkpoint, build_root, limits=limits, synthetic=synthetic,
            output_digest=output_digest, source_projection=source_projection,
        )
        packet = _validate_campaign_graph_packet({
            "schema_version": "policyos.academic.campaign_graph.v1",
            "artifact_kind": "completed_candidate_graph", "scope": "candidate_only",
            "synthetic": synthetic, "campaign_binding": checkpoint._binding,
            "input_mode": "historical_source_epoch",
            "input_execution_epoch": plan.execution_epoch,
            "input_owner_source_hash": plan.owner_source_hash,
            "input_frame_digest": plan.input_digest, "completed_input_count": count,
            "completed_output_digest": output_digest, "work_outcomes": outcomes,
            "capacity_limits": asdict(limits), "graph_owner_projection": source_projection,
            "graph_metrics": {**asdict(stats), **synthesis}, "artifacts": artifacts,
            "strangle_receipt": asdict(strangle),
            "staging_usage": {
                "graph_load": read_staging_usage(staging / "graph-load.sqlite"),
                "edge_synthesize": read_staging_usage(staging / "edge-synthesize.sqlite"),
            },
        })
        _require_campaign_graph_artifact_set(packet, config, checkpoint.root)
        # The shared owner measures actual safe-writer bytes privately before
        # exposing a completed reference. Refused builds remain rebuildable.
        manifest = checkpoint.root / "graphs" / f"{build_id}.json"
        publish_owned_output(
            manifest, lambda private: safe_write_json(private, packet),
            paths=(build_root,), limits=limits, temporary_root=build_root,
        )
        return ArtifactRef(
            path=manifest.relative_to(checkpoint.root).as_posix(), sha256=sha256_file(manifest),
        )


def resolve_extraction_campaign_graph(
    plan: CampaignPlan,
    checkpoint_root: Path,
    ref: ArtifactRef,
    *,
    safe_write_json: SafeJSONWriter | None = None,
) -> dict[str, Any]:
    """Reconcile the candidate manifest with its current inputs and actual artifacts."""
    import json
    from pathlib import Path

    from polisyos.data_forge.kernel.io import sha256_file

    from ._graph_staging import (
        GraphCapacityLimits,
        enforce_owned_output_budget,
        read_staging_usage,
    )
    from .config import AcademicBatchConfig
    from .reextraction_campaign import CampaignCheckpoint, _bytes_digest

    del safe_write_json  # Historical resolution never needs credentials or writes.
    with CampaignCheckpoint.read_only_history(checkpoint_root, plan) as checkpoint:
        path = (checkpoint.root / ref.path).resolve()
        if path.parent != checkpoint.root / "graphs" or Path(ref.path).is_absolute():
            raise ValueError("campaign_graph_manifest_path_refused")
        raw = checkpoint._bounded_bytes(path)
        if _bytes_digest(raw)[7:] != ref.sha256:
            raise ValueError("campaign_graph_manifest_hash_mismatch")
        packet = _validate_campaign_graph_packet(json.loads(raw))
        count, output_digest, outcomes, synthetic = _complete_campaign_graph_inputs(checkpoint)
        if (
            packet["campaign_binding"] != checkpoint._binding
            or packet["input_frame_digest"] != plan.input_digest
            or packet["synthetic"] is not synthetic
            or packet["input_execution_epoch"] != plan.execution_epoch
            or packet["input_owner_source_hash"] != plan.owner_source_hash
            or packet["completed_input_count"] != count
            or packet["completed_output_digest"] != output_digest
            or packet["work_outcomes"] != outcomes
            or packet["graph_owner_projection"] != campaign_graph_owner_projection()
        ):
            raise ValueError("campaign_graph_current_binding_mismatch")
        limits = GraphCapacityLimits(**packet["capacity_limits"])
        build_root = checkpoint.root / "graph-builds" / path.stem
        enforce_owned_output_budget((build_root, path), limits)
        config = AcademicBatchConfig(
            snapshot_root=build_root, run_id=plan.campaign_id,
            pass_name="abstract_campaign_graph",  # noqa: S106 - processing-stage label
        )
        _require_campaign_graph_artifact_set(packet, config, checkpoint.root)
        for item in packet["artifacts"]:
            artifact = (checkpoint.root / item["path"]).resolve()
            if not artifact.is_relative_to(build_root) or Path(item["path"]).is_absolute():
                raise ValueError("campaign_graph_artifact_path_refused")
            if sha256_file(artifact) != item["sha256"]:
                raise ValueError("campaign_graph_artifact_hash_mismatch")
        if packet["staging_usage"] != {
            "graph_load": read_staging_usage(build_root / "staging" / "graph-load.sqlite"),
            "edge_synthesize": read_staging_usage(
                build_root / "staging" / "edge-synthesize.sqlite",
            ),
        }:
            raise ValueError("campaign_graph_staging_usage_mismatch")
        from dataclasses import asdict

        strangle = _recompute_graph_staging_strangle(
            checkpoint, build_root, limits=limits, synthetic=synthetic,
            output_digest=output_digest, source_projection=packet["graph_owner_projection"],
        )
        if packet["strangle_receipt"] != asdict(strangle):
            raise ValueError("campaign_graph_strangle_recomputation_mismatch")
        return packet
