"""Thin orchestrator for staged academic pipeline."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from polisyos.batch_common.thermal import cooldown
from polisyos.academic.batch.config import AcademicBatchConfig


@dataclass
class PipelineStats:
    elapsed_seconds: float = 0.0
    stage_times: dict[str, float] = field(default_factory=dict)
    metrics: dict[str, float | int | str] = field(default_factory=dict)


async def run_academic_pipeline(config: AcademicBatchConfig, *, thermal: bool = False) -> PipelineStats:
    """Run selected academic stages sequentially."""
    from polisyos.academic.batch.dedup import merge_and_dedup
    from polisyos.academic.batch.embedder import run_embed
    from polisyos.academic.batch.graph_builder import run_graph_index, run_graph_load
    from polisyos.academic.batch.harvester import harvest_all
    from polisyos.academic.batch.parser import parse_raw_sources
    from polisyos.academic.batch.publish import run_publish
    from polisyos.academic.batch.qc import run_qc
    from polisyos.academic.batch.resolve_extract import run_resolve_extract
    from polisyos.academic.batch.topic_select import run_topic_select

    t0 = time.monotonic()
    stats = PipelineStats()

    if "topic_select" in config.stages:
        st = time.monotonic()
        selected = await run_topic_select(config)
        stats.stage_times["topic_select"] = time.monotonic() - st
        stats.metrics.update({f"topic_select_{k}": v for k, v in selected.items()})

    if "harvest" in config.stages:
        st = time.monotonic()
        harvested = await harvest_all(config)
        stats.stage_times["harvest"] = time.monotonic() - st
        stats.metrics["harvest_records"] = sum(len(v) for v in harvested.values())

    if "parse" in config.stages:
        st = time.monotonic()
        parsed = parse_raw_sources(config)
        stats.stage_times["parse"] = time.monotonic() - st
        stats.metrics["parsed_records"] = sum(parsed.values())

    if "resolve_extract" in config.stages:
        st = time.monotonic()
        resolve_stats = await run_resolve_extract(config)
        stats.stage_times["resolve_extract"] = time.monotonic() - st
        stats.metrics.update({f"resolve_extract_{k}": v for k, v in resolve_stats.items()})

    if "merge_dedup" in config.stages:
        st = time.monotonic()
        merged = merge_and_dedup(config)
        stats.stage_times["merge_dedup"] = time.monotonic() - st
        stats.metrics.update({f"merge_{k}": v for k, v in merged.items()})

    if "graph_load" in config.stages:
        st = time.monotonic()
        gstats = run_graph_load(config)
        stats.stage_times["graph_load"] = time.monotonic() - st
        stats.metrics["works"] = gstats.works
        stats.metrics["estimates"] = gstats.estimates
        stats.metrics["claims"] = gstats.claims
        stats.metrics["topic_selections"] = gstats.topic_selections

    if "graph_index" in config.stages:
        st = time.monotonic()
        run_graph_index(config)
        stats.stage_times["graph_index"] = time.monotonic() - st

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


def run_academic_pipeline_sync(config: AcademicBatchConfig, *, thermal: bool = False) -> PipelineStats:
    """Sync wrapper for non-async callers."""
    return asyncio.run(run_academic_pipeline(config, thermal=thermal))
