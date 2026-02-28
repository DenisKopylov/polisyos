"""Thin orchestrator for staged dataset pipeline commands."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from polisyos.batch_common.thermal import cooldown
from polisyos.datasets.batch.config import DatasetBatchConfig


@dataclass
class PipelineStats:
    elapsed_seconds: float = 0.0
    stage_times: dict[str, float] = field(default_factory=dict)
    metrics: dict[str, float | int | str] = field(default_factory=dict)


async def run_dataset_pipeline(config: DatasetBatchConfig, *, thermal: bool = False) -> PipelineStats:
    """Run selected stages sequentially (used by `run` CLI wrapper)."""
    from polisyos.datasets.batch.dedup import merge_and_dedup
    from polisyos.datasets.batch.embedder import run_embed
    from polisyos.datasets.batch.graph_builder import run_graph_index, run_graph_load
    from polisyos.datasets.batch.harvester import harvest_sources
    from polisyos.datasets.batch.normalizer import normalize_raw_sources
    from polisyos.datasets.batch.publish import run_publish
    from polisyos.datasets.batch.qc import run_qc

    t0 = time.monotonic()
    stats = PipelineStats()

    if "harvest" in config.stages:
        st = time.monotonic()
        harvested = await harvest_sources(config)
        stats.stage_times["harvest"] = time.monotonic() - st
        stats.metrics["harvest_records"] = sum(len(v) for v in harvested.values())

    if "normalize" in config.stages:
        st = time.monotonic()
        norm_counts = normalize_raw_sources(config)
        stats.stage_times["normalize"] = time.monotonic() - st
        stats.metrics["normalized_records"] = sum(norm_counts.values())

    if "merge_dedup" in config.stages:
        st = time.monotonic()
        merge_stats = merge_and_dedup(config)
        stats.stage_times["merge_dedup"] = time.monotonic() - st
        stats.metrics.update({f"merge_{k}": v for k, v in merge_stats.items()})

    if "graph_load" in config.stages:
        st = time.monotonic()
        gstats = run_graph_load(config)
        stats.stage_times["graph_load"] = time.monotonic() - st
        stats.metrics["graph_datasets"] = gstats.datasets
        stats.metrics["graph_distributions"] = gstats.distributions

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


def run_dataset_pipeline_sync(config: DatasetBatchConfig, *, thermal: bool = False) -> PipelineStats:
    """Sync wrapper for callers that are not in asyncio context."""
    return asyncio.run(run_dataset_pipeline(config, thermal=thermal))
