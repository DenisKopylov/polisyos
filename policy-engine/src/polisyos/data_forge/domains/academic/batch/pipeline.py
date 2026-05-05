"""Thin orchestrator for staged academic pipeline."""

from __future__ import annotations

import asyncio
import gc
import time
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from polisyos.data_forge.kernel.runtime import cooldown

if TYPE_CHECKING:
    from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig


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
    config: AcademicBatchConfig, *, thermal: bool = False
) -> PipelineStats:
    """Run selected academic stages sequentially."""
    from polisyos.data_forge.domains.academic.batch.benchmark import run_benchmark
    from polisyos.data_forge.domains.academic.batch.claim_adjudicator import (
        run_claim_adjudicate,
        run_consensus_aggregate,
    )
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
        st = time.monotonic()
        adjudicated = await run_claim_adjudicate(config)
        adjudicated.update(
            {f"consensus_{k}": v for k, v in run_consensus_aggregate(config).items()}
        )
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
    config: AcademicBatchConfig, *, thermal: bool = False
) -> PipelineStats:
    """Sync wrapper for non-async callers."""
    return asyncio.run(run_academic_pipeline(config, thermal=thermal))
