"""Thin orchestrator for staged dataset pipeline commands."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING

from polisyos.data_forge.domains.catalog.batch.checkpoints import (
    OUTPUT_INVENTORY_SCHEMA_VERSION,
    build_content_basis,
    build_output_inventory,
    fingerprint_paths,
    load_json,
    save_stage_state,
    stage_can_skip,
    write_json,
)
from polisyos.data_forge.domains.catalog.batch.config import _producer_config_snapshot
from polisyos.data_forge.kernel.embeddings import embedding_generation_manifest
from polisyos.data_forge.kernel.io.hashing import sha256_file
from polisyos.data_forge.kernel.runtime import cooldown

if TYPE_CHECKING:
    from polisyos.data_forge.domains.catalog.batch.benchmark import BenchmarkOutcome
    from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
    from polisyos.data_forge.kernel.quality import QCReport


_CONTENT_BOUND_STAGES = frozenset(
    {
        "harvest",
        "normalize",
        "merge_dedup",
        "graph_load",
        "graph_index",
        "embed",
        "benchmark",
        "qc",
        "publish",
    }
)
_NON_EMPTY_BOUND_STAGES = frozenset({"harvest", "normalize", "merge_dedup"})
_STAGE_RULE_VERSIONS = {
    "harvest": "policyos.catalog.harvest.v1",
    "normalize": "policyos.catalog.normalize.v1",
    "merge_dedup": "policyos.catalog.merge_dedup.v1",
    "graph_load": "policyos.catalog.graph_load.v1",
    "graph_index": "policyos.catalog.graph_index.v1",
    "embed": "policyos.catalog.embed.v2",
    "benchmark": "policyos.catalog.benchmark.v1",
    "qc": "policyos.catalog.qc.v1",
    "publish": "policyos.catalog.publish.v1",
}


def _files_under(path: Path) -> list[Path]:
    """Enumerate the complete file set a local stage consumer can traverse."""
    if path.is_file():
        return [path]
    if not path.is_dir():
        return []
    return sorted(item for item in path.rglob("*") if item.is_file())


def _qc_previous_snapshot_context(
    config: DatasetBatchConfig,
) -> tuple[Path | None, dict[str, object]]:
    """Bind QC's sibling scan and exact selected prior snapshot."""
    from polisyos.data_forge.domains.catalog.batch.qc import _previous_snapshot_root

    parent = config.snapshot_root.parent
    current = config.snapshot_root.resolve()
    siblings = []
    if parent.exists():
        siblings = sorted(
            [path for path in parent.iterdir() if path.is_dir() and (path / "datasets").exists()],
            key=lambda item: (item.name, item.stat().st_mtime_ns),
        )
    selection = {
        "current_snapshot": str(current),
        "candidate_siblings": [
            {
                "path": str(path.resolve()),
                "name": path.name,
                "mtime_ns": int(path.stat().st_mtime_ns),
            }
            for path in siblings
        ],
    }
    previous = _previous_snapshot_root(config)
    selection["selected_previous_snapshot"] = (
        str(previous.resolve()) if previous is not None else None
    )
    return previous, selection


def _previous_snapshot_payloads(snapshot_root: Path) -> list[Path]:
    """Include payload paths named by every source's selected old manifest."""
    from polisyos.data_forge.domains.catalog.batch.qc import _latest_manifest

    raw_root = snapshot_root / "datasets" / "raw"
    payloads: list[Path] = []
    if not raw_root.is_dir():
        return payloads
    for source_dir in sorted(path for path in raw_root.iterdir() if path.is_dir()):
        manifest_path = _latest_manifest(source_dir)
        manifest = load_json(manifest_path, default=None) if manifest_path is not None else None
        if isinstance(manifest, dict) and isinstance(manifest.get("payload"), str):
            payloads.append(Path(manifest["payload"]))
    return payloads


def _embedding_basis_is_established(basis: Mapping[str, object]) -> bool:
    config = basis.get("config")
    return isinstance(config, Mapping) and config.get("encoder_asset_identity_state") in {
        "established",
        "not_required_empty",
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


def _stage_input_basis(
    config: DatasetBatchConfig,
    stage: str,
    *,
    encoder_identity_override: str | None = None,
    core_receipt_basis_member: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build the selected, content-bound input basis for a resumable stage."""
    producer_config = _producer_config_snapshot(config)
    if stage == "harvest":
        registry = config.load_registry()
        selected_sources = registry.enabled_sources(
            wave=config.wave,
            run_profile=config.run_profile,
        )
        inputs: dict[str, Path | list[Path] | None] = {
            "source_registry": config.registry_path or config.default_registry_path,
            "metrics_map": config.resolved_metrics_map_path,
        }
        settings: dict[str, object] = {
            "effective_producer_config": producer_config,
            "registry_version": registry.version,
            "selected_sources": [asdict(spec) for spec in selected_sources],
            "wave": config.wave,
            "run_profile": config.run_profile,
            "max_datasets_per_source": config.max_datasets_per_source,
            "promoted_sources": sorted(config.promoted_sources),
            "date_start": config.date_start,
            "date_end": config.date_end,
            "harvest_timeout": config.harvest_timeout,
        }
    elif stage == "normalize":
        registry = config.load_registry()
        selected_sources = registry.enabled_sources(
            wave=config.wave,
            run_profile=config.run_profile,
        )
        harvest_receipt = _harvest_stage_receipt(config)
        inputs = {
            "raw_manifests": sorted(config.raw_dir.rglob("manifest.json")),
            "raw_payloads": sorted(config.raw_dir.rglob("payload.jsonl")),
            "source_registry": config.registry_path or config.default_registry_path,
            "metrics_map": config.resolved_metrics_map_path,
        }
        settings = {
            "effective_producer_config": producer_config,
            "run_signature": config.run_signature,
            "run_profile": config.run_profile,
            "observation_mode": config.observation_mode,
            "selected_sources": [asdict(spec) for spec in selected_sources],
            "harvest_receipt": (
                None
                if harvest_receipt is None
                else {
                    "selected_sources": list(harvest_receipt[0]),
                    "source_outcomes": harvest_receipt[1],
                }
            ),
        }
    elif stage == "merge_dedup":
        inputs = {
            "normalized_records": sorted(config.normalized_dir.glob("*.jsonl")),
        }
        settings = {
            "effective_producer_config": producer_config,
            "run_signature": config.run_signature,
        }
    elif stage == "graph_load":
        inputs = {"merged_records": config.merged_records_path}
        settings = {
            "effective_producer_config": producer_config,
            "run_signature": config.run_signature,
        }
    elif stage == "graph_index":
        inputs = {"graph_database": config.db_path}
        settings = {
            "effective_producer_config": producer_config,
            "run_signature": config.run_signature,
        }
    elif stage == "embed":
        from polisyos.data_forge.domains.catalog.batch.embedder import (
            _encoder_identity_for_resume,
        )

        if encoder_identity_override is None:
            encoder_identity, encoder_identity_state = _encoder_identity_for_resume(config)
        else:
            encoder_identity, encoder_identity_state = encoder_identity_override, "established"
        inputs = {"graph_database": config.db_path}
        settings = {
            "effective_producer_config": producer_config,
            "run_signature": config.run_signature,
            "embedding_model": config.embedding_model,
            "embedding_device": config.resolved_embedding_device,
            "embedding_dimension": config.embedding_dimension,
            "embedding_batch_size": config.embedding_batch_size,
            "encoder_asset_identity": encoder_identity,
            "encoder_asset_identity_state": encoder_identity_state,
            "projection_rule_version": "policyos.catalog_dataset_embedding_projection.v1",
        }
        return build_content_basis(
            stage=stage,
            rule_version=_STAGE_RULE_VERSIONS[stage],
            config=settings,
            inputs=inputs,
        )
    elif stage in {"benchmark", "qc", "publish"}:
        registry = config.load_registry()
        selected_sources = registry.enabled_sources(
            wave=config.wave,
            run_profile=config.run_profile,
        )
        harvest_receipt = _harvest_stage_receipt(config)
        harvest_artifacts = harvest_receipt[2] if harvest_receipt is not None else []
        generation = embedding_generation_manifest(
            config.index_dir,
            legacy_embeddings_path=config.index_dir / "ds_dataset_embeddings.npz",
            legacy_index_path=config.index_dir / "ds_dataset_index.hnsw",
        )
        generation_artifacts = list(generation[1]) if generation is not None else []
        common_inputs: dict[str, Path | list[Path] | None] = {
            "source_registry": config.registry_path or config.default_registry_path,
            "metrics_map": config.resolved_metrics_map_path,
            "harvest_receipt_artifacts": harvest_artifacts,
            "merged_records": config.merged_records_path,
            "duplicates_report": config.duplicates_report_path,
            "graph_database": config.db_path,
            "embedding_generation": generation_artifacts,
            "core_ingest_report": config.manifests_dir / "core_sources_ingest.json",
            "raw_source_artifacts": _files_under(config.raw_dir),
            "observation_manifests": _files_under(config.manifests_dir / "observations"),
            "observation_progress": [
                config.manifests_dir / name
                for name in (
                    "completed_observation_shards.json",
                    "failed_observation_shards.json",
                    "deferred_observation_plans.json",
                    "observation_source_summary.json",
                )
            ],
        }
        settings = {
            "effective_producer_config": producer_config,
            "run_signature": config.run_signature,
            "run_profile": config.run_profile,
            "wave": config.wave,
            "registry_version": registry.version,
            "selected_sources": [asdict(spec) for spec in selected_sources],
            "harvest_receipt": (
                None
                if harvest_receipt is None
                else {
                    "selected_sources": list(harvest_receipt[0]),
                    "source_outcomes": harvest_receipt[1],
                }
            ),
            "max_datasets_per_source": config.max_datasets_per_source,
            "promoted_sources": sorted(config.promoted_sources),
            "date_start": config.date_start,
            "date_end": config.date_end,
            "active_countries": list(config.resolved_active_countries),
            "active_year_window": list(config.resolved_year_window),
            "observation_mode": config.observation_mode,
        }
        if stage == "benchmark":
            stage_state = load_json(config.stage_state_path, default={})
            core_state = (
                stage_state.get("core_sources_ingest")
                if isinstance(stage_state, dict)
                else None
            )
            settings["core_sources_ingest_stage_state"] = core_state
            if core_receipt_basis_member is None:
                from polisyos.data_forge.domains.catalog.batch.core_sources.validators import (
                    _current_core_output_receipt_state,
                )

                core_receipt_basis_member = _current_core_output_receipt_state(
                    config
                ).basis_member()
            settings["core_output_receipt_state"] = dict(core_receipt_basis_member)
        if stage == "qc":
            previous_root, previous_context = _qc_previous_snapshot_context(config)
            settings["qc_previous_snapshot_selection"] = previous_context
            common_inputs["qc_previous_raw_artifacts"] = (
                _files_under(previous_root / "datasets" / "raw")
                if previous_root is not None
                else []
            )
            common_inputs["qc_previous_referenced_payloads"] = (
                _previous_snapshot_payloads(previous_root)
                if previous_root is not None
                else []
            )
        if stage == "benchmark":
            inputs = common_inputs
            settings["embedding_model"] = config.embedding_model
        elif stage == "qc":
            inputs = {**common_inputs, "benchmark_report": config.benchmark_report_path}
            settings["fail_fast_qc"] = config.fail_fast_qc
        else:
            inputs = {
                **common_inputs,
                "benchmark_report": config.benchmark_report_path,
                "qc_report": config.qc_report_path,
            }
        return build_content_basis(
            stage=stage,
            rule_version=_STAGE_RULE_VERSIONS[stage],
            config=settings,
            inputs=inputs,
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
    if stage == "harvest":
        receipt = _harvest_stage_receipt(config)
        if receipt is None:
            return {
                "schema_version": OUTPUT_INVENTORY_SCHEMA_VERSION,
                "status": "unavailable",
                "entries": [],
            }
        selected_sources, source_outcomes, artifacts = receipt
        return {
            **build_output_inventory(artifacts),
            "status": "complete",
            "selected_sources": selected_sources,
            "source_outcomes": source_outcomes,
        }
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


def _has_material_output(inventory: Mapping[str, object]) -> bool:
    """Return whether a directory inventory contains a published member."""
    entries = inventory.get("entries")
    if not isinstance(entries, list):
        return False
    for raw_entry in entries:
        if not isinstance(raw_entry, Mapping):
            continue
        if raw_entry.get("kind") == "file" and raw_entry.get("exists") is True:
            return True
        if raw_entry.get("kind") == "directory" and raw_entry.get("members"):
            return True
    return False


def _harvest_stage_receipt(
    config: DatasetBatchConfig,
) -> tuple[list[str], dict[str, dict[str, object]], list[Path]] | None:
    """Reconcile a harvest receipt against the selected registry and source bytes."""
    registry = config.load_registry()
    specs = registry.enabled_sources(wave=config.wave, run_profile=config.run_profile)
    selected_sources = [spec.name for spec in specs]
    stage_path = config.manifests_dir / "harvest.json"
    stage = load_json(stage_path, default=None)
    checkpoint = load_json(config.harvest_checkpoint_path, default=None)
    if not isinstance(stage, dict) or not isinstance(checkpoint, dict):
        return None
    metrics = stage.get("metrics")
    if (
        stage.get("stage") != "harvest"
        or stage.get("status") != "ok"
        or not isinstance(metrics, dict)
        or metrics.get("selected_sources") != selected_sources
        or metrics.get("successful_sources") != selected_sources
        or metrics.get("failed_sources") != []
    ):
        return None
    raw_outcomes = metrics.get("source_outcomes")
    if not isinstance(raw_outcomes, dict) or set(raw_outcomes) != set(selected_sources):
        return None

    outcomes: dict[str, dict[str, object]] = {}
    artifacts: list[Path] = [stage_path, config.harvest_checkpoint_path]
    for spec in specs:
        outcome = raw_outcomes.get(spec.name)
        entry = checkpoint.get(spec.name)
        if (
            not isinstance(outcome, dict)
            or outcome.get("status") != "complete"
            or not isinstance(entry, dict)
            or entry.get("status") != "complete"
        ):
            return None
        payload_path = Path(str(outcome.get("payload_path", ""))).resolve()
        manifest_path = Path(str(outcome.get("manifest_path", ""))).resolve()
        source_root = (config.raw_dir / spec.name).resolve()
        if (
            not payload_path.is_relative_to(source_root)
            or not manifest_path.is_relative_to(source_root)
            or not payload_path.is_file()
            or not manifest_path.is_file()
            or str(entry.get("payload_path", "")) != str(payload_path)
            or str(entry.get("manifest_path", "")) != str(manifest_path)
        ):
            return None
        payload_digest = sha256_file(payload_path)
        if (
            outcome.get("payload_sha256") != payload_digest
            or entry.get("payload_hash") != payload_digest
        ):
            return None
        raw_manifest = load_json(manifest_path, default=None)
        if (
            not isinstance(raw_manifest, dict)
            or raw_manifest.get("source") != spec.name
            or Path(str(raw_manifest.get("payload", ""))).resolve() != payload_path
            or raw_manifest.get("sha256") != payload_digest
        ):
            return None
        with payload_path.open(encoding="utf-8") as payload_file:
            payload_rows = sum(1 for line in payload_file if line.strip())
        if (
            int(raw_manifest.get("count", -1)) != payload_rows
            or int(entry.get("records_fetched", -1)) != payload_rows
            or int(outcome.get("records_fetched", -1)) != payload_rows
        ):
            return None
        outcomes[spec.name] = dict(outcome)
        artifacts.extend((payload_path, manifest_path))
    return selected_sources, outcomes, list(dict.fromkeys(artifacts))


def _should_skip_stage(config: DatasetBatchConfig, stage: str) -> bool:
    if not config.resume or config.resume_mode == "off":
        return False
    if stage in {"core_sources_ingest", "qc"}:
        # Core ingest consumes external fetched inputs without a complete
        # content receipt. QC also includes volatile live-readiness checks.
        # Recompute these producers instead of reusing a stored declaration.
        return False
    if stage in _CONTENT_BOUND_STAGES:
        core_receipt_basis_member = None
        if stage == "benchmark":
            from polisyos.data_forge.domains.catalog.batch.core_sources.validators import (
                _current_core_output_receipt_state,
            )

            core_receipt_state = _current_core_output_receipt_state(config)
            if core_receipt_state.expected and core_receipt_state.reconciled_receipt is None:
                return False
            core_receipt_basis_member = core_receipt_state.basis_member()
        input_basis = _stage_input_basis(
            config,
            stage,
            core_receipt_basis_member=core_receipt_basis_member,
        )
        output_inventory = _stage_output_inventory(config, stage)
        if stage == "harvest":
            receipt = _harvest_stage_receipt(config)
            if receipt is None:
                return False
            _selected_sources, _source_outcomes, required_outputs = receipt
        elif stage == "normalize":
            if _harvest_stage_receipt(config) is None:
                return False
            required_outputs = _stage_outputs(config, stage)
        else:
            required_outputs = _stage_outputs(config, stage)
        if stage == "embed" and not _embedding_basis_is_established(input_basis):
            return False
        if stage == "embed" and output_inventory.get("status") not in {
            "complete",
            "empty_generation",
        }:
            return False
        if stage in _NON_EMPTY_BOUND_STAGES and not _has_material_output(output_inventory):
            return False
        return stage_can_skip(
            config.stage_state_path,
            stage=stage,
            input_fingerprint=str(input_basis["basis_digest"]),
            required_outputs=required_outputs,
            expected_input_basis=input_basis,
            expected_output_inventory=output_inventory,
            require_content_bound=True,
        )
    fingerprint = _stage_input_fingerprint(config, stage)
    return stage_can_skip(
        config.stage_state_path,
        stage=stage,
        input_fingerprint=fingerprint,
        required_outputs=_stage_outputs(config, stage),
    )


def current_content_stage_receipt(
    config: DatasetBatchConfig, stage: str
) -> dict[str, object] | None:
    """Return the exact saved basis and output inventory for a current stage.

    A receipt is available only when saved bytes still equal the freshly
    recomputed input basis and output inventory. Downstream owners can consume
    this persisted receipt without implementing their own fingerprint rules.
    """
    if stage not in _CONTENT_BOUND_STAGES:
        return None
    state = load_json(config.stage_state_path, default={})
    if not isinstance(state, dict):
        return None
    saved = state.get(stage)
    if not isinstance(saved, dict) or saved.get("status") != "complete":
        return None
    saved_basis = saved.get("input_basis")
    saved_inventory = saved.get("output_inventory")
    if not isinstance(saved_basis, dict) or not isinstance(saved_inventory, dict):
        return None
    required_outputs = _stage_outputs(config, stage)
    if not required_outputs or not all(path.exists() for path in required_outputs):
        return None
    current_basis = _stage_input_basis(config, stage)
    current_inventory = _stage_output_inventory(config, stage)
    if saved_basis != current_basis or saved_inventory != current_inventory:
        return None
    if stage in {"harvest", "normalize"} and _harvest_stage_receipt(config) is None:
        return None
    if stage == "embed" and current_inventory.get("status") not in {
        "complete",
        "empty_generation",
    }:
        return None
    if stage == "embed" and not _embedding_basis_is_established(current_basis):
        return None
    if stage in _NON_EMPTY_BOUND_STAGES and not _has_material_output(current_inventory):
        return None
    return {
        "stage": stage,
        "input_basis": saved_basis,
        "input_basis_digest": saved_basis.get("basis_digest"),
        "output_inventory": saved_inventory,
        "output_inventory_digest": saved_inventory.get("inventory_digest"),
    }


def run_content_stage_with_receipt(
    config: DatasetBatchConfig,
    stage: str,
) -> BenchmarkOutcome | QCReport | Path:
    """Run a content stage and record its exact basis and output inventory.

    Only the canonical benchmark, QC, and publish producers can create these
    receipts.  The complete input basis must remain unchanged across execution.
    """
    if stage not in {"benchmark", "qc", "publish"}:
        raise ValueError(f"standalone content receipt is unsupported for stage {stage!r}")
    initial_basis = _stage_input_basis(config, stage)
    if stage == "benchmark":
        from polisyos.data_forge.domains.catalog.batch.benchmark import run_benchmark

        result = run_benchmark(config)
        stage_metadata = {"report_path": str(result.report_path)}
    elif stage == "qc":
        from polisyos.data_forge.domains.catalog.batch.qc import run_qc

        result = run_qc(config, fail_fast=config.fail_fast_qc)
        stage_metadata = {"passed": bool(result.passed)}
    else:
        from polisyos.data_forge.domains.catalog.batch.publish import run_publish

        result = run_publish(config)
        stage_metadata = {"manifest": str(result)}
    if _stage_input_basis(config, stage) != initial_basis:
        raise RuntimeError(f"{stage} inputs changed while its producer was running")
    _record_stage_completion(config, stage, metadata=stage_metadata)
    if current_content_stage_receipt(config, stage) is None:
        raise RuntimeError(f"{stage} producer did not publish a current content-bound receipt")
    return result


def _uncached_content_stage_config(config: DatasetBatchConfig) -> DatasetBatchConfig:
    """Disable inner stat-based checkpoints after outer content validation misses."""
    return replace(config, resume=False) if config.resume else config


def _record_stage_completion(
    config: DatasetBatchConfig, stage: str, *, metadata: dict[str, object] | None = None
) -> None:
    stage_metadata = dict(metadata or {})
    if stage == "harvest" and _harvest_stage_receipt(config) is None:
        raise RuntimeError("cannot record a complete harvest without a reconciled source receipt")
    if stage == "normalize" and _harvest_stage_receipt(config) is None:
        raise RuntimeError(
            "cannot record complete normalization without a complete harvest receipt"
        )
    if stage == "core_sources_ingest":
        # Remote observations and fetched source payloads do not yet have a
        # complete producer receipt that can authorize resume.
        input_basis = None
        output_inventory = None
    else:
        encoder_identity_override = None
        if stage == "embed":
            from polisyos.data_forge.domains.catalog.batch.embedder import _cached_encoder

            cached_encoder = _cached_encoder(config)
            if cached_encoder is not None:
                _encoder, identity = cached_encoder
                encoder_identity_override = identity.content_identity
        input_basis = (
            _stage_input_basis(
                config,
                stage,
                encoder_identity_override=encoder_identity_override,
            )
            if stage in _CONTENT_BOUND_STAGES
            else None
        )
        output_inventory = (
            _stage_output_inventory(config, stage) if stage in _CONTENT_BOUND_STAGES else None
        )
    input_fingerprint = (
        str(input_basis["basis_digest"])
        if isinstance(input_basis, Mapping) and "basis_digest" in input_basis
        else _stage_input_fingerprint(config, stage)
    )
    save_stage_state(
        config.stage_state_path,
        stage=stage,
        status="complete",
        input_fingerprint=input_fingerprint,
        outputs=_stage_outputs(config, stage),
        metadata=stage_metadata,
        input_basis=input_basis,
        output_inventory=output_inventory,
    )


async def run_dataset_pipeline(
    config: DatasetBatchConfig, *, thermal: bool = False
) -> PipelineStats:
    """Run selected stages sequentially (used by `run` CLI wrapper)."""
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
    deferred_graph_receipts: set[str] = set()
    graph_receipt_metadata: dict[str, dict[str, object]] = {}
    try:
        if "harvest" in config.stages:
            current_stage = "harvest"
            if _should_skip_stage(config, "harvest"):
                stats.skipped_stages.append("harvest")
            else:
                st = time.monotonic()
                harvested = await harvest_sources(_uncached_content_stage_config(config))
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
                if _harvest_stage_receipt(config) is None:
                    raise RuntimeError(
                        "normalize requires a complete receipt for every selected harvest source"
                    )
                st = time.monotonic()
                norm_counts = normalize_raw_sources(_uncached_content_stage_config(config))
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
                graph_receipt_metadata["graph_load"] = {
                    "datasets": gstats.datasets,
                    "distributions": gstats.distributions,
                }
            deferred_graph_receipts.add("graph_load")

        if "graph_index" in config.stages:
            current_stage = "graph_index"
            if _should_skip_stage(config, "graph_index"):
                stats.skipped_stages.append("graph_index")
            else:
                st = time.monotonic()
                run_graph_index(config)
                stats.stage_times["graph_index"] = time.monotonic() - st
            deferred_graph_receipts.add("graph_index")

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

        # These stages share a DuckDB artifact, and core-source ingestion may
        # update it after graph/index construction. Record both receipts after
        # the selected DB writers finish so their output inventory describes
        # the exact persisted state that the next run will inspect.
        previous_state = load_json(config.stage_state_path, default={})
        for stage in sorted(deferred_graph_receipts):
            saved = previous_state.get(stage) if isinstance(previous_state, dict) else None
            saved_metadata = saved.get("metadata") if isinstance(saved, dict) else None
            metadata = graph_receipt_metadata.get(
                stage,
                saved_metadata if isinstance(saved_metadata, dict) else {},
            )
            _record_stage_completion(config, stage, metadata=dict(metadata))

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
                benchmark = run_content_stage_with_receipt(config, "benchmark")
                stats.stage_times["benchmark"] = time.monotonic() - st
                stats.metrics.update(benchmark.metrics)

        if "qc" in config.stages:
            current_stage = "qc"
            if _should_skip_stage(config, "qc"):
                stats.skipped_stages.append("qc")
            else:
                st = time.monotonic()
                report = run_content_stage_with_receipt(config, "qc")
                stats.stage_times["qc"] = time.monotonic() - st
                stats.metrics["qc_passed"] = int(report.passed)

        if "publish" in config.stages:
            current_stage = "publish"
            if _should_skip_stage(config, "publish"):
                stats.skipped_stages.append("publish")
            else:
                st = time.monotonic()
                manifest = run_content_stage_with_receipt(config, "publish")
                stats.stage_times["publish"] = time.monotonic() - st
                stats.metrics["publish_manifest"] = str(manifest)

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
