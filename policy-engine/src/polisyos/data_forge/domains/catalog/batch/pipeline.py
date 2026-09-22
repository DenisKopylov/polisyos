"""Thin orchestrator for staged dataset pipeline commands."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from polisyos.data_forge.domains.catalog.batch.checkpoints import (
    OUTPUT_INVENTORY_SCHEMA_VERSION,
    build_content_basis,
    build_output_inventory,
    fingerprint_paths,
    load_stage_state,
    save_stage_state,
    stage_can_skip,
    write_json,
)
from polisyos.data_forge.kernel.embeddings import embedding_generation_manifest
from polisyos.data_forge.kernel.io.hashing import sha256_file
from polisyos.data_forge.kernel.runtime import cooldown

if TYPE_CHECKING:
    from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig


_CONTENT_BOUND_STAGES = frozenset({"harvest", "normalize", "merge_dedup", "embed"})
_STAGE_RULE_VERSIONS = {
    "harvest": "policyos.catalog.harvest.v1",
    "normalize": "policyos.catalog.normalize.v1",
    "merge_dedup": "policyos.catalog.merge_dedup.v1",
    "embed": "policyos.catalog.embed.v2",
}


@dataclass
class PipelineStats:
    """Pipeline stats public type."""

    elapsed_seconds: float = 0.0
    stage_times: dict[str, float] = field(default_factory=dict)
    metrics: dict[str, float | int | str] = field(default_factory=dict)
    skipped_stages: list[str] = field(default_factory=list)


def _stage_input_fingerprint(config: DatasetBatchConfig, stage: str) -> str:
    if stage in _CONTENT_BOUND_STAGES:
        return str(_stage_input_basis(config, stage)["basis_digest"])
    if stage == "harvest":
        return config.run_signature
    if stage == "normalize":
        manifests = sorted(config.raw_dir.glob("*/**/manifest.json"))
        return fingerprint_paths(manifests)
    if stage == "merge_dedup":
        return fingerprint_paths(sorted(config.normalized_dir.glob("*.jsonl")))
    if stage == "graph_load":
        return fingerprint_paths([config.merged_records_path])
    if stage == "graph_index":
        return fingerprint_paths([config.db_path])
    if stage == "core_sources_ingest":
        return fingerprint_paths([config.db_path]) + ":" + config.run_signature
    if stage == "embed":
        return fingerprint_paths([config.db_path]) + ":" + config.embedding_model
    if stage == "benchmark":
        return fingerprint_paths([config.db_path])
    if stage == "qc":
        return fingerprint_paths([config.db_path, config.benchmark_report_path])
    if stage == "publish":
        return fingerprint_paths(
            [config.qc_report_path, config.benchmark_report_path, config.db_path]
        )
    return config.run_signature


def _stage_input_basis(config: DatasetBatchConfig, stage: str) -> dict[str, object]:
    """Build the selected, content-bound input basis for a resumable stage."""
    if stage == "harvest":
        inputs: dict[str, Path | list[Path] | None] = {
            "source_registry": config.registry_path or config.default_registry_path,
            "metrics_map": config.resolved_metrics_map_path,
        }
        settings: dict[str, object] = {
            "run_signature": config.run_signature,
            "run_profile": config.run_profile,
            "max_datasets_per_source": config.max_datasets_per_source,
            "promoted_sources": list(config.promoted_sources),
            "date_start": config.date_start,
            "date_end": config.date_end,
            "harvest_timeout": config.harvest_timeout,
        }
    elif stage == "normalize":
        inputs = {
            "raw_manifests": sorted(config.raw_dir.rglob("manifest.json")),
            "raw_payloads": sorted(config.raw_dir.rglob("payload.jsonl")),
            "source_registry": config.registry_path or config.default_registry_path,
            "metrics_map": config.resolved_metrics_map_path,
        }
        settings = {
            "run_signature": config.run_signature,
            "run_profile": config.run_profile,
            "observation_mode": config.observation_mode,
        }
    elif stage == "merge_dedup":
        inputs = {
            "normalized_records": sorted(config.normalized_dir.glob("*.jsonl")),
        }
        settings = {"run_signature": config.run_signature}
    elif stage == "embed":
        inputs = {"graph_database": config.db_path}
        settings = {
            "run_signature": config.run_signature,
            "embedding_model": config.embedding_model,
            "embedding_device": config.resolved_embedding_device,
            "embedding_dimension": config.embedding_dimension,
            "embedding_batch_size": config.embedding_batch_size,
            "projection_rule_version": "policyos.catalog_dataset_embedding_projection.v1",
        }
        trusted = _graph_load_immutable_receipt(config)
        return build_content_basis(
            stage=stage,
            rule_version=_STAGE_RULE_VERSIONS[stage],
            config=settings,
            inputs=inputs,
            trusted_inputs={"graph_database": trusted} if trusted else None,
        )
    else:
        raise ValueError(f"content-bound basis is not defined for stage {stage!r}")
    return build_content_basis(
        stage=stage,
        rule_version=_STAGE_RULE_VERSIONS[stage],
        config=settings,
        inputs=inputs,
    )


def _stage_outputs(config: DatasetBatchConfig, stage: str) -> list:
    mapping = {
        "harvest": [config.raw_dir],
        "normalize": [config.normalized_dir],
        "merge_dedup": [config.merged_records_path, config.duplicates_report_path],
        "graph_load": [config.db_path],
        "graph_index": [config.db_path],
        "core_sources_ingest": [config.manifests_dir / "core_sources_ingest.json"],
        "embed": [config.index_dir / "embedding_generation.json"],
        "benchmark": [config.benchmark_report_path],
        "qc": [config.qc_report_path],
        "publish": [config.publish_manifest_path, config.consumer_readiness_path],
    }
    return mapping.get(stage, [])


def _stage_output_inventory(config: DatasetBatchConfig, stage: str) -> dict[str, object]:
    """Build the stage-specific output inventory used for a resume decision."""
    if stage == "embed":
        try:
            generation = embedding_generation_manifest(
                config.index_dir,
                legacy_embeddings_path=config.index_dir / "ds_dataset_embeddings.npz",
                legacy_index_path=config.index_dir / "ds_dataset_index.hnsw",
            )
            if generation is None or generation[0].get("status") not in {
                "complete",
                "empty_generation",
            }:
                return {
                    "schema_version": OUTPUT_INVENTORY_SCHEMA_VERSION,
                    "status": "unavailable",
                    "entries": [],
                }
            metadata, artifacts = generation
            return {
                "schema_version": OUTPUT_INVENTORY_SCHEMA_VERSION,
                "status": str(metadata["status"]),
                "generation": metadata,
                "artifacts": build_output_inventory(artifacts),
            }
        except (OSError, TypeError, ValueError, KeyError, AttributeError, IndexError):
            return {
                "schema_version": OUTPUT_INVENTORY_SCHEMA_VERSION,
                "status": "unavailable",
                "entries": [],
            }
    return build_output_inventory(_stage_outputs(config, stage))


def _graph_load_immutable_receipt(config: DatasetBatchConfig) -> Mapping[str, object] | None:
    """Return a validated one-time graph-load receipt for the large DB input."""
    state = load_stage_state(config.stage_state_path).get("graph_load")
    if not isinstance(state, Mapping):
        return None
    metadata = state.get("metadata")
    if not isinstance(metadata, Mapping):
        return None
    receipts = metadata.get("immutable_outputs")
    if not isinstance(receipts, list):
        return None
    resolved = str(config.db_path.resolve())
    for raw in receipts:
        if not isinstance(raw, Mapping):
            continue
        if (
            raw.get("source") == "pipeline_owned_immutable_output"
            and str(raw.get("path")) == resolved
            and raw.get("kind") == "file"
            and raw.get("exists") is True
            and isinstance(raw.get("size"), int)
            and isinstance(raw.get("mtime_ns"), int)
            and isinstance(raw.get("sha256"), str)
            and raw.get("sha256")
        ):
            return raw
    return None


def _immutable_output_receipt(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "kind": "file",
        "exists": True,
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "sha256": sha256_file(path),
        "source": "pipeline_owned_immutable_output",
    }


def _should_skip_stage(config: DatasetBatchConfig, stage: str) -> bool:
    if not config.resume or config.resume_mode == "off":
        return False
    if stage in _CONTENT_BOUND_STAGES:
        input_basis = _stage_input_basis(config, stage)
        return stage_can_skip(
            config.stage_state_path,
            stage=stage,
            input_fingerprint=str(input_basis["basis_digest"]),
            required_outputs=_stage_outputs(config, stage),
            expected_input_basis=input_basis,
            expected_output_inventory=_stage_output_inventory(config, stage),
            require_content_bound=True,
        )
    fingerprint = _stage_input_fingerprint(config, stage)
    return stage_can_skip(
        config.stage_state_path,
        stage=stage,
        input_fingerprint=fingerprint,
        required_outputs=_stage_outputs(config, stage),
    )


def _record_stage_completion(
    config: DatasetBatchConfig, stage: str, *, metadata: dict[str, object] | None = None
) -> None:
    stage_metadata = dict(metadata or {})
    if stage == "graph_load":
        receipt = _immutable_output_receipt(config.db_path)
        if receipt is not None:
            stage_metadata["immutable_outputs"] = [receipt]
    input_basis = _stage_input_basis(config, stage) if stage in _CONTENT_BOUND_STAGES else None
    output_inventory = (
        _stage_output_inventory(config, stage) if stage in _CONTENT_BOUND_STAGES else None
    )
    save_stage_state(
        config.stage_state_path,
        stage=stage,
        status="complete",
        input_fingerprint=_stage_input_fingerprint(config, stage),
        outputs=_stage_outputs(config, stage),
        metadata=stage_metadata,
        input_basis=input_basis,
        output_inventory=output_inventory,
    )


async def run_dataset_pipeline(
    config: DatasetBatchConfig, *, thermal: bool = False
) -> PipelineStats:
    """Run selected stages sequentially (used by `run` CLI wrapper)."""
    from polisyos.data_forge.domains.catalog.batch.benchmark import run_benchmark
    from polisyos.data_forge.domains.catalog.batch.core_sources.api import (
        run_core_sources_ingest_async,
    )
    from polisyos.data_forge.domains.catalog.batch.dedup import merge_and_dedup
    from polisyos.data_forge.domains.catalog.batch.embedder import run_embed
    from polisyos.data_forge.domains.catalog.batch.graph_builder import (
        run_graph_index,
        run_graph_load,
    )
    from polisyos.data_forge.domains.catalog.batch.harvester import harvest_sources
    from polisyos.data_forge.domains.catalog.batch.normalizer import normalize_raw_sources
    from polisyos.data_forge.domains.catalog.batch.publish import run_publish
    from polisyos.data_forge.domains.catalog.batch.qc import run_qc

    t0 = time.monotonic()
    stats = PipelineStats()
    telemetry: dict[str, object] = {
        "run_profile": config.run_profile,
        "resume_mode": config.resume_mode,
        "country_scope": config.country_scope,
        "active_countries": list(config.resolved_active_countries),
        "active_year_window": list(config.resolved_year_window),
        "stages": {},
    }
    current_stage = ""
    pipeline_status = "success"
    error_message = ""
    try:
        if "harvest" in config.stages:
            current_stage = "harvest"
            if _should_skip_stage(config, "harvest"):
                stats.skipped_stages.append("harvest")
            else:
                st = time.monotonic()
                harvested = await harvest_sources(config)
                stats.stage_times["harvest"] = time.monotonic() - st
                stats.metrics["harvest_records"] = sum(len(v) for v in harvested.values())
                _record_stage_completion(
                    config, "harvest", metadata={"records": stats.metrics["harvest_records"]}
                )

        if "normalize" in config.stages:
            current_stage = "normalize"
            if _should_skip_stage(config, "normalize"):
                stats.skipped_stages.append("normalize")
            else:
                st = time.monotonic()
                norm_counts = normalize_raw_sources(config)
                stats.stage_times["normalize"] = time.monotonic() - st
                stats.metrics["normalized_records"] = sum(norm_counts.values())
                _record_stage_completion(
                    config, "normalize", metadata={"records": stats.metrics["normalized_records"]}
                )

        if "merge_dedup" in config.stages:
            current_stage = "merge_dedup"
            if _should_skip_stage(config, "merge_dedup"):
                stats.skipped_stages.append("merge_dedup")
            else:
                st = time.monotonic()
                merge_stats = merge_and_dedup(config)
                stats.stage_times["merge_dedup"] = time.monotonic() - st
                stats.metrics.update({f"merge_{k}": v for k, v in merge_stats.items()})
                _record_stage_completion(
                    config,
                    "merge_dedup",
                    metadata={k: merge_stats.get(k) for k in sorted(merge_stats)},
                )

        if "graph_load" in config.stages:
            current_stage = "graph_load"
            if _should_skip_stage(config, "graph_load"):
                stats.skipped_stages.append("graph_load")
            else:
                st = time.monotonic()
                gstats = run_graph_load(config)
                stats.stage_times["graph_load"] = time.monotonic() - st
                stats.metrics["graph_datasets"] = gstats.datasets
                stats.metrics["graph_distributions"] = gstats.distributions
                _record_stage_completion(
                    config,
                    "graph_load",
                    metadata={"datasets": gstats.datasets, "distributions": gstats.distributions},
                )

        if "graph_index" in config.stages:
            current_stage = "graph_index"
            if _should_skip_stage(config, "graph_index"):
                stats.skipped_stages.append("graph_index")
            else:
                st = time.monotonic()
                run_graph_index(config)
                stats.stage_times["graph_index"] = time.monotonic() - st
                _record_stage_completion(config, "graph_index")

        if "core_sources_ingest" in config.stages:
            current_stage = "core_sources_ingest"
            if _should_skip_stage(config, "core_sources_ingest"):
                stats.skipped_stages.append("core_sources_ingest")
            else:
                st = time.monotonic()
                cstats = await run_core_sources_ingest_async(config)
                stats.stage_times["core_sources_ingest"] = time.monotonic() - st
                stats.metrics["core_registry_datasets"] = cstats.registry_datasets
                stats.metrics["core_variable_alignments"] = cstats.variable_alignments
                stats.metrics["core_observations"] = cstats.observations
                stats.metrics["core_observations_attempted"] = cstats.observations_attempted
                stats.metrics["core_observations_inserted"] = cstats.observations_inserted
                stats.metrics["core_observations_replaced"] = cstats.observations_replaced
                stats.metrics["core_failures"] = cstats.failures
                _record_stage_completion(
                    config,
                    "core_sources_ingest",
                    metadata={"failures": cstats.failures, "observations": cstats.observations},
                )

        if "embed" in config.stages:
            current_stage = "embed"
            if _should_skip_stage(config, "embed"):
                stats.skipped_stages.append("embed")
            else:
                st = time.monotonic()
                embedded = run_embed(config, thermal=thermal)
                stats.stage_times["embed"] = time.monotonic() - st
                stats.metrics["embedded"] = embedded
                _record_stage_completion(config, "embed", metadata={"embedded": embedded})

        if "benchmark" in config.stages:
            current_stage = "benchmark"
            if _should_skip_stage(config, "benchmark"):
                stats.skipped_stages.append("benchmark")
            else:
                st = time.monotonic()
                benchmark = run_benchmark(config)
                stats.stage_times["benchmark"] = time.monotonic() - st
                stats.metrics.update(benchmark.metrics)
                _record_stage_completion(
                    config, "benchmark", metadata={"report_path": str(benchmark.report_path)}
                )

        if "qc" in config.stages:
            current_stage = "qc"
            if _should_skip_stage(config, "qc"):
                stats.skipped_stages.append("qc")
            else:
                st = time.monotonic()
                report = run_qc(config, fail_fast=config.fail_fast_qc)
                stats.stage_times["qc"] = time.monotonic() - st
                stats.metrics["qc_passed"] = int(report.passed)
                _record_stage_completion(config, "qc", metadata={"passed": bool(report.passed)})

        if "publish" in config.stages:
            current_stage = "publish"
            if _should_skip_stage(config, "publish"):
                stats.skipped_stages.append("publish")
            else:
                st = time.monotonic()
                manifest = run_publish(config)
                stats.stage_times["publish"] = time.monotonic() - st
                stats.metrics["publish_manifest"] = str(manifest)
                _record_stage_completion(config, "publish", metadata={"manifest": str(manifest)})

        if thermal and config.cooldown_seconds > 0:
            cooldown(float(config.cooldown_seconds))
    except Exception as exc:
        pipeline_status = "failed"
        error_message = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        stats.elapsed_seconds = time.monotonic() - t0
        telemetry["elapsed_seconds"] = stats.elapsed_seconds
        telemetry["stage_times"] = stats.stage_times
        telemetry["metrics"] = stats.metrics
        telemetry["skipped_stages"] = stats.skipped_stages
        telemetry["pipeline_status"] = pipeline_status
        telemetry["current_stage"] = current_stage
        telemetry["error"] = error_message
        write_json(config.telemetry_path, telemetry)
    return stats


def run_dataset_pipeline_sync(
    config: DatasetBatchConfig, *, thermal: bool = False
) -> PipelineStats:
    """Sync wrapper for callers that are not in asyncio context."""
    return asyncio.run(run_dataset_pipeline(config, thermal=thermal))
