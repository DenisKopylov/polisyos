"""Thin orchestrator for staged dataset pipeline commands."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from math import isfinite
from pathlib import Path
from typing import TYPE_CHECKING

from polisyos.data_forge.domains.catalog.batch.checkpoints import (
    OUTPUT_INVENTORY_SCHEMA_VERSION,
    build_content_basis,
    build_output_inventory,
    fingerprint_paths,
    hash_payload,
    load_json,
    save_stage_state,
    stage_can_skip,
    write_json,
)
from polisyos.data_forge.domains.catalog.batch.config import (
    _producer_config_snapshot,
    profile_input_coverage_currentness,
)
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
    "benchmark": "policyos.catalog.benchmark.v2",
    "qc": "policyos.catalog.qc.v3",
    "publish": "policyos.catalog.publish.v2",
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
            encoder_identity, encoder_identity_state = (
                encoder_identity_override,
                "established",
            )
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
        if stage in {"benchmark", "qc", "publish"}:
            stage_state = load_json(config.stage_state_path, default={})
            core_state = (
                stage_state.get("core_sources_ingest") if isinstance(stage_state, dict) else None
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
                _previous_snapshot_payloads(previous_root) if previous_root is not None else []
            )
        if stage == "benchmark":
            inputs = common_inputs
            settings["embedding_model"] = config.embedding_model
        elif stage == "qc":
            inputs = {**common_inputs, "benchmark_report": config.benchmark_report_path}
            settings["fail_fast_qc"] = config.fail_fast_qc
        else:
            report_basis = current_catalog_report_basis(config)
            settings["report_basis"] = {
                key: report_basis.get(key)
                for key in (
                    "state",
                    "reason",
                    "digest",
                    "evaluation_mode",
                    "benchmark_stage",
                    "qc_stage",
                )
            }
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
        "benchmark": [config.benchmark_report_path, config.manifests_dir / "benchmark.json"],
        "qc": [
            config.qc_report_path,
            config.manifests_dir / "qc.json",
            config.component_dir / "coverage_heatmap.json",
            config.component_dir / "observed_support.json",
        ],
        "publish": [
            config.publish_manifest_path,
            config.consumer_readiness_path,
            config.manifests_dir / "publish.json",
        ],
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
        except OSError, TypeError, ValueError, KeyError, AttributeError, IndexError:
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


def _basis_profile_input_currentness(
    basis: Mapping[str, object],
) -> tuple[str, dict[str, str] | None]:
    """Apply the shared profile-input rule to a saved or live content basis."""
    config = basis.get("config")
    if not isinstance(config, Mapping):
        return "malformed", None
    producer_config = config.get("effective_producer_config")
    if not isinstance(producer_config, Mapping):
        return "malformed", None
    coverage_key = "resolved_profile_input_coverage"
    return profile_input_coverage_currentness(
        producer_config.get(coverage_key),
        missing=coverage_key not in producer_config,
    )


def _profile_input_currentness_reason(state: str) -> str:
    if state == "not_established":
        return "profile_private_inputs_unversioned"
    if state == "legacy_unknown":
        return "profile_input_coverage_legacy_unknown"
    if state == "malformed":
        return "profile_input_coverage_malformed"
    return "recomputed_profile_inputs_covered"


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
        if stage in {"benchmark", "publish"}:
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
        profile_state, _profile_coverage = _basis_profile_input_currentness(input_basis)
        if profile_state != "established":
            return False
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
    profile_state, _profile_coverage = _basis_profile_input_currentness(current_basis)
    receipt_state = "current" if profile_state == "established" else "not_established"
    return {
        "stage": stage,
        "state": receipt_state,
        "reason": _profile_input_currentness_reason(profile_state),
        "profile_input_coverage_state": profile_state,
        "input_basis": saved_basis,
        "input_basis_digest": saved_basis.get("basis_digest"),
        "output_inventory": saved_inventory,
        "output_inventory_digest": saved_inventory.get("inventory_digest"),
    }


def _report_stage_manifest_is_bound(
    config: DatasetBatchConfig,
    stage: str,
    report: Mapping[str, object],
) -> tuple[bool, str]:
    """Check that a native stage manifest names the exact report bytes."""
    report_path = config.benchmark_report_path if stage == "benchmark" else config.qc_report_path
    manifest_path = config.manifests_dir / f"{stage}.json"
    manifest = load_json(manifest_path, default=None)
    if not isinstance(manifest, dict):
        return False, f"{stage}_stage_manifest_missing_or_malformed"
    expected_status = "ok"
    if stage == "qc":
        expected_status = "ok" if report.get("passed") is True else "failed"
    if (
        manifest.get("kind") != "stage"
        or manifest.get("stage") != stage
        or manifest.get("status") != expected_status
    ):
        return False, f"{stage}_stage_manifest_identity_mismatch"
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 1 or not isinstance(artifacts[0], dict):
        return False, f"{stage}_stage_manifest_artifact_set_mismatch"
    artifact = artifacts[0]
    artifact_path = artifact.get("path")
    try:
        exact_path = (
            isinstance(artifact_path, str)
            and Path(artifact_path).resolve() == report_path.resolve()
        )
        digest = sha256_file(report_path)
    except (OSError, TypeError, ValueError):
        return False, f"{stage}_stage_manifest_artifact_unreadable"
    if not exact_path or artifact.get("sha256") != digest:
        return False, f"{stage}_stage_manifest_artifact_mismatch"
    metrics = manifest.get("metrics")
    if not isinstance(metrics, dict):
        return False, f"{stage}_stage_manifest_metrics_missing"
    report_metrics = report.get("metrics")
    if not isinstance(report_metrics, dict):
        return False, f"{stage}_report_metrics_missing"
    for name, value in report_metrics.items():
        if metrics.get(name) != value:
            return False, f"{stage}_stage_manifest_metrics_mismatch"
    if stage == "qc" and metrics.get("passed") is not report.get("passed"):
        return False, "qc_stage_manifest_passed_mismatch"
    try:
        started_at = datetime.fromisoformat(str(manifest.get("started_at")))
        finished_at = datetime.fromisoformat(str(manifest.get("finished_at")))
        report_generated_at = datetime.fromisoformat(str(report.get("generated_at")))
    except (TypeError, ValueError):
        return False, f"{stage}_stage_timestamp_malformed"
    if (
        started_at.tzinfo is None
        or finished_at.tzinfo is None
        or report_generated_at.tzinfo is None
        or finished_at < started_at
        or report_generated_at < started_at
        or report_generated_at > finished_at
    ):
        return False, f"{stage}_report_timestamp_outside_producer_window"
    return True, "current"


def _finite_report_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and isfinite(float(value))


def _report_semantic_payload(payload: Mapping[str, object]) -> dict[str, object]:
    """Drop only the producer timestamp before comparing recomputed report content."""

    def json_compatible(value: object) -> object:
        if isinstance(value, Mapping):
            return {str(key): json_compatible(item) for key, item in value.items()}
        if isinstance(value, tuple | list):
            return [json_compatible(item) for item in value]
        return value

    return {key: json_compatible(value) for key, value in payload.items() if key != "generated_at"}


def _report_stage_state(
    config: DatasetBatchConfig,
    stage: str,
) -> tuple[dict[str, object] | None, str, str]:
    """Return one current producer receipt or its exact absent/stale state."""
    receipt = current_content_stage_receipt(config, stage)
    if receipt is not None:
        state = str(receipt.get("state") or "not_established")
        return receipt, state, str(receipt.get("reason") or f"{stage}_currentness_not_established")
    saved_state = load_json(config.stage_state_path, default={})
    saved_stage = saved_state.get(stage) if isinstance(saved_state, dict) else None
    if isinstance(saved_stage, dict) and saved_stage.get("status") == "complete":
        return None, "stale", f"{stage}_basis_or_output_drift"
    return None, "not_established", f"{stage}_producer_receipt_absent"


def _derive_catalog_readiness(
    config: DatasetBatchConfig,
    report_basis: Mapping[str, object],
) -> dict[str, object]:
    """Derive readiness once from an admitted producer report basis."""
    from polisyos.data_forge.domains.catalog.batch.benchmark import (
        readiness_thresholds_for_profile,
    )

    benchmark = report_basis.get("benchmark_payload")
    qc = report_basis.get("qc_payload")
    if (
        report_basis.get("state") != "current"
        or not isinstance(benchmark, dict)
        or not isinstance(qc, dict)
    ):
        raise ValueError("a current benchmark/QC report basis is required")
    metrics = benchmark.get("metrics")
    source_preflight = benchmark.get("source_preflight")
    source_rows = source_preflight.get("sources") if isinstance(source_preflight, dict) else None
    if not isinstance(metrics, dict) or not isinstance(source_rows, list):
        raise ValueError("the admitted benchmark report is incomplete")
    thresholds = readiness_thresholds_for_profile(config.run_profile)
    source_statuses = {
        str(row["source"]): str(row["status"]) for row in source_rows if isinstance(row, dict)
    }
    blocking_specs = [
        spec
        for spec in config.load_registry().sources
        if spec.enabled and spec.publish_blocking and spec.run_lane == "empirical"
    ]
    missing_statuses = sorted(
        spec.name for spec in blocking_specs if spec.name not in source_statuses
    )
    if missing_statuses:
        raise ValueError("missing blocking source statuses: " + ", ".join(missing_statuses))
    evaluation_mode = str(report_basis["evaluation_mode"])
    readiness = {
        "qc_ready": qc.get("passed") is True,
        "benchmark_ready": bool(metrics),
        "search_ready": float(metrics["benchmark_search_top5_relevance_pct"])
        >= thresholds["benchmark_search_top5_relevance_pct"],
        "fetchability_ready": float(metrics["benchmark_retrieval_ready_pct"])
        >= thresholds["benchmark_retrieval_ready_pct"],
        "transportability_ready": float(metrics["benchmark_transport_ready_pct"])
        >= thresholds["benchmark_transport_ready_pct"],
        "foundry_ready": float(metrics["benchmark_foundry_fitness_pct"])
        >= thresholds["benchmark_foundry_fitness_pct"],
        "source_preflight_ready": float(metrics["benchmark_source_preflight_ready_pct"])
        >= thresholds["benchmark_source_preflight_ready_pct"],
        "evaluation_ready": evaluation_mode in {"core-ready", "full-ready"},
        "equivalence_ready": (
            float(metrics["benchmark_bulk_equivalence_mismatch_rate"]) <= 2.0
            and int(metrics["benchmark_bulk_equivalence_blocking_sources_total"]) <= 0
        ),
    }
    readiness["consumer_ready"] = all(readiness.values())
    readiness["full_publish_ready"] = (
        readiness["consumer_ready"] and evaluation_mode == "full-ready"
    )
    return {
        "readiness": readiness,
        "thresholds": thresholds,
        "blocking_source_statuses": source_statuses,
    }


def current_catalog_report_basis(config: DatasetBatchConfig) -> dict[str, object]:
    """Recompute the exact native benchmark and QC report basis for publication.

    A report's own fields are admitted only when the canonical stage receipt is
    current, its output inventory binds both report and producer manifest, and
    report content agrees with that manifest and the selected producer config.
    """
    receipts: dict[str, dict[str, object]] = {}
    for stage in ("benchmark", "qc"):
        receipt, state, reason = _report_stage_state(config, stage)
        if receipt is None or state != "current":
            return {"state": state, "reason": reason, "stage": stage}
        receipts[stage] = receipt

    benchmark = load_json(config.benchmark_report_path, default=None)
    qc = load_json(config.qc_report_path, default=None)
    if not isinstance(benchmark, dict) or not isinstance(qc, dict):
        return {"state": "not_established", "reason": "report_json_missing_or_malformed"}
    expected_roots = {
        "snapshot_root": str(config.snapshot_root),
        "component_dir": str(config.component_dir),
    }
    if (
        benchmark.get("kind") != "datasets_benchmark"
        or benchmark.get("run_profile") != config.run_profile
        or any(benchmark.get(name) != value for name, value in expected_roots.items())
    ):
        return {"state": "not_established", "reason": "benchmark_report_identity_mismatch"}
    evaluation_mode = benchmark.get("evaluation_mode")
    if evaluation_mode not in {"partial-eval", "full-eval", "core-ready", "full-ready"}:
        return {
            "state": "not_established",
            "reason": "benchmark_evaluation_mode_missing_or_invalid",
        }
    from polisyos.data_forge.domains.catalog.batch.benchmark import (
        readiness_thresholds_for_profile,
    )

    expected_thresholds = readiness_thresholds_for_profile(config.run_profile)
    thresholds = benchmark.get("thresholds")
    if not isinstance(thresholds, dict) or thresholds != expected_thresholds:
        return {"state": "not_established", "reason": "benchmark_threshold_basis_mismatch"}
    benchmark_metrics = benchmark.get("metrics")
    if not isinstance(benchmark_metrics, dict):
        return {"state": "not_established", "reason": "benchmark_metrics_missing"}
    for metric in expected_thresholds:
        value = benchmark_metrics.get(metric)
        if not _finite_report_number(value) or not 0 <= float(value) <= 100:
            return {"state": "not_established", "reason": f"benchmark_metric_invalid:{metric}"}
    mismatch_rate = benchmark_metrics.get("benchmark_bulk_equivalence_mismatch_rate")
    blocking_sources = benchmark_metrics.get("benchmark_bulk_equivalence_blocking_sources_total")
    if not _finite_report_number(mismatch_rate) or float(mismatch_rate) < 0:
        return {"state": "not_established", "reason": "benchmark_bulk_mismatch_metric_invalid"}
    if type(blocking_sources) is not int or blocking_sources < 0:
        return {"state": "not_established", "reason": "benchmark_blocking_source_count_invalid"}
    preflight = benchmark.get("source_preflight")
    source_rows = preflight.get("sources") if isinstance(preflight, dict) else None
    if not isinstance(source_rows, list):
        return {"state": "not_established", "reason": "benchmark_source_preflight_missing"}
    source_statuses: dict[str, str] = {}
    for row in source_rows:
        if not isinstance(row, dict):
            return {"state": "not_established", "reason": "benchmark_source_preflight_row_invalid"}
        name, status = row.get("source"), row.get("status")
        if (
            not isinstance(name, str)
            or not name.strip()
            or not isinstance(status, str)
            or not status.strip()
        ):
            return {
                "state": "not_established",
                "reason": "benchmark_source_preflight_identity_invalid",
            }
        if name in source_statuses:
            return {"state": "not_established", "reason": "benchmark_source_preflight_duplicate"}
        source_statuses[name] = status
    blocking_specs = [
        spec
        for spec in config.load_registry().sources
        if spec.enabled and spec.publish_blocking and spec.run_lane == "empirical"
    ]
    missing_statuses = sorted(
        spec.name for spec in blocking_specs if spec.name not in source_statuses
    )
    if missing_statuses:
        return {
            "state": "not_established",
            "reason": "benchmark_blocking_source_status_missing",
            "missing_sources": missing_statuses,
        }

    if qc.get("scope") != "datasets" or qc.get("metrics") is None:
        return {"state": "not_established", "reason": "qc_report_identity_or_metrics_missing"}
    qc_metrics = qc.get("metrics")
    checks = qc.get("checks")
    if not isinstance(qc_metrics, dict) or not isinstance(checks, list) or not checks:
        return {"state": "not_established", "reason": "qc_report_checks_missing_or_invalid"}
    recomputed_qc_passed = True
    for check in checks:
        if not isinstance(check, dict) or not isinstance(check.get("passed"), bool):
            return {"state": "not_established", "reason": "qc_check_shape_invalid"}
        severity = check.get("severity")
        if severity not in {"critical", "warning", "info"}:
            return {"state": "not_established", "reason": "qc_check_severity_invalid"}
        if not check["passed"] and severity == "critical":
            recomputed_qc_passed = False
    if type(qc.get("passed")) is not bool or qc.get("passed") is not recomputed_qc_passed:
        return {"state": "not_established", "reason": "qc_passed_not_recomputed"}
    if qc_metrics.get("qc_evaluation_mode") != evaluation_mode:
        return {"state": "not_established", "reason": "qc_benchmark_mode_mismatch"}

    from polisyos.data_forge.domains.catalog.batch.benchmark import evaluate_benchmark
    from polisyos.data_forge.domains.catalog.batch.qc import evaluate_qc

    recomputed_benchmark = evaluate_benchmark(config).report
    if _report_semantic_payload(benchmark) != _report_semantic_payload(recomputed_benchmark):
        return {
            "state": "not_established",
            "reason": "benchmark_report_not_recomputed_from_selected_catalog",
        }
    recomputed_qc = evaluate_qc(
        config,
        benchmark_report_payload=recomputed_benchmark,
    ).to_dict()
    if _report_semantic_payload(qc) != _report_semantic_payload(recomputed_qc):
        return {
            "state": "not_established",
            "reason": "qc_report_not_recomputed_from_selected_catalog",
        }

    benchmark_bound, benchmark_reason = _report_stage_manifest_is_bound(
        config,
        "benchmark",
        benchmark,
    )
    if not benchmark_bound:
        return {"state": "not_established", "reason": benchmark_reason}
    qc_bound, qc_reason = _report_stage_manifest_is_bound(config, "qc", qc)
    if not qc_bound:
        return {"state": "not_established", "reason": qc_reason}

    stage_summaries = {
        stage: {
            "state": "current",
            "input_basis_digest": receipts[stage].get("input_basis_digest"),
            "output_inventory_digest": receipts[stage].get("output_inventory_digest"),
        }
        for stage in ("benchmark", "qc")
    }
    digest = hash_payload(
        {
            "schema_version": "policyos.catalog_report_basis.v1",
            "run_profile": config.run_profile,
            "stages": stage_summaries,
            "evaluation_mode": evaluation_mode,
        }
    )
    return {
        "state": "current",
        "reason": "recomputed_native_benchmark_and_qc_receipts",
        "schema_version": "policyos.catalog_report_basis.v1",
        "digest": digest,
        "run_profile": config.run_profile,
        "evaluation_mode": evaluation_mode,
        "benchmark_stage": stage_summaries["benchmark"],
        "qc_stage": stage_summaries["qc"],
        "benchmark_payload": benchmark,
        "qc_payload": qc,
        "basis_predicates": {
            "benchmark_metrics": "recomputed_from_selected_catalog_and_source_basis",
            "qc_checks": "recomputed_from_selected_catalog_and_native_benchmark",
            "qc_url_reachability": "recomputed_from_current_selected_distribution_urls",
        },
    }


def current_catalog_publish_receipt(
    database_path: Path, *, run_profile: str | None = None
) -> dict[str, object]:
    """Recompute local producer currentness for one exact batch-owned database."""
    from polisyos.data_forge.domains.catalog.batch.config import (
        DatasetBatchConfig,
        parse_profile_input_coverage,
    )
    from polisyos.data_forge.domains.catalog.batch.core_sources.validators import (
        _current_core_output_receipt_state,
    )

    path = Path(database_path).resolve()
    if (
        path.name != "dataset_catalog.duckdb"
        or path.parent.name != "graph"
        or path.parent.parent.name != "datasets"
    ):
        return {"state": "not_established", "reason": "unmatched_batch_database"}
    stage_path = path.parents[2] / "datasets" / "manifests" / "stage_state.json"
    if not stage_path.is_file():
        return {"state": "not_established", "reason": "producer_stage_state_absent"}
    state = load_json(stage_path, default={})
    publish = state.get("publish") if isinstance(state, dict) else None
    if not isinstance(publish, dict) or publish.get("status") != "complete":
        return {"state": "not_established", "reason": "publish_lineage_absent"}
    basis = publish.get("input_basis")
    config_basis = basis.get("config") if isinstance(basis, dict) else None
    saved = (
        config_basis.get("effective_producer_config") if isinstance(config_basis, dict) else None
    )
    if not isinstance(saved, dict):
        return {"state": "not_established", "reason": "publish_config_intent_absent"}
    coverage_state, profile_coverage = parse_profile_input_coverage(
        saved.get("resolved_profile_input_coverage"),
        missing="resolved_profile_input_coverage" not in saved,
    )
    if coverage_state != "established" or profile_coverage is None:
        reason = (
            "producer_profile_input_coverage_legacy_unknown"
            if coverage_state == "legacy_unknown"
            else "producer_profile_input_coverage_malformed"
        )
        return {
            "state": "not_established",
            "reason": reason,
            "profile_input_coverage_state": coverage_state,
        }
    config = DatasetBatchConfig.from_producer_config_snapshot(saved)
    if config is None:
        return {
            "state": "not_established",
            "reason": "producer_config_intent_unreconstructable",
        }
    if config.db_path.resolve() != path:
        return {
            "state": "not_established",
            "reason": "producer_config_intent_unreconstructable",
        }
    if run_profile is not None and config.run_profile != run_profile:
        return {
            "state": "not_established",
            "reason": "producer_consumer_profile_mismatch",
        }
    try:
        report_basis = current_catalog_report_basis(config)
        if report_basis.get("state") != "current":
            state = str(report_basis.get("state") or "not_established")
            reason = str(report_basis.get("reason") or "report_basis_not_current")
            return {
                "state": state,
                "reason": f"catalog_report_basis_{reason}",
                "report_basis_state": state,
            }
        receipt = current_content_stage_receipt(config, "publish")
        if receipt is None:
            return {"state": "stale", "reason": "publish_basis_or_output_drift"}
        if receipt.get("state") != "current":
            return {
                "state": "not_established",
                "reason": receipt.get("reason")
                or "publish_profile_input_currentness_not_established",
                "profile_input_coverage_state": receipt.get("profile_input_coverage_state"),
            }
        derived = _derive_catalog_readiness(config, report_basis)
        readiness_payload = load_json(config.consumer_readiness_path, default=None)
        publish_payload = load_json(config.publish_manifest_path, default=None)
        publish_extra = publish_payload.get("extra") if isinstance(publish_payload, dict) else None
        declared_basis = (
            readiness_payload.get("report_basis") if isinstance(readiness_payload, dict) else None
        )
        manifest_basis = (
            publish_extra.get("report_basis") if isinstance(publish_extra, dict) else None
        )
        expected_readiness = derived["readiness"]
        if (
            not isinstance(readiness_payload, dict)
            or readiness_payload.get("readiness") != expected_readiness
            or not isinstance(declared_basis, dict)
            or declared_basis.get("digest") != report_basis.get("digest")
            or declared_basis.get("state") != "current"
            or not isinstance(publish_extra, dict)
            or publish_extra.get("consumer_ready") is not expected_readiness["consumer_ready"]
            or publish_extra.get("full_publish_ready")
            is not expected_readiness["full_publish_ready"]
            or not isinstance(manifest_basis, dict)
            or manifest_basis.get("digest") != report_basis.get("digest")
            or manifest_basis.get("state") != "current"
            or expected_readiness["consumer_ready"] is not True
        ):
            return {
                "state": "stale",
                "reason": "publish_readiness_basis_or_derivation_mismatch",
            }
        core = _current_core_output_receipt_state(config)
        if core.expected and core.reconciled_receipt is None:
            return {
                "state": "stale",
                "reason": "expected_core_output_receipt_unreconciled",
            }
        input_basis = receipt.get("input_basis")
        inputs = input_basis.get("inputs") if isinstance(input_basis, dict) else None
        db_input = inputs.get("graph_database") if isinstance(inputs, dict) else None
        records = db_input.get("records") if isinstance(db_input, dict) else None
        paths = db_input.get("paths") if isinstance(db_input, dict) else None
        if not isinstance(records, list) or len(records) != 1 or not isinstance(records[0], dict):
            return {
                "state": "not_established",
                "reason": "graph_database_record_unreadable",
            }
        row = records[0]
        digest = row.get("sha256")
        size = row.get("size")
        if (
            paths != [str(path)]
            or row.get("path") != str(path)
            or row.get("kind") != "file"
            or row.get("exists") is not True
            or type(size) is not int
            or size <= 0
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(ch not in "0123456789abcdef" for ch in digest)
        ):
            return {
                "state": "not_established",
                "reason": "graph_database_record_unverified",
            }
        return {
            "state": "current",
            "reason": "recomputed_publish_basis_outputs_and_core_receipt",
            "run_profile": config.run_profile,
            "input_basis_digest": receipt.get("input_basis_digest"),
            "output_inventory_digest": receipt.get("output_inventory_digest"),
            "profile_input_coverage_state": coverage_state,
            "profile_input_coverage": {
                "schema_version": "policyos.catalog.profile_input_coverage.v1",
                "profiles": profile_coverage,
            },
            "database_identity": {
                "source_path": str(path),
                "content_sha256": f"sha256:{digest}",
                "byte_size": size,
            },
            "report_basis": {
                key: report_basis[key]
                for key in (
                    "state",
                    "schema_version",
                    "digest",
                    "run_profile",
                    "evaluation_mode",
                    "benchmark_stage",
                    "qc_stage",
                )
            },
        }
    except AttributeError, KeyError, OSError, TypeError, ValueError:
        return {
            "state": "not_established",
            "reason": "publish_currentness_recompute_unavailable",
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

        result = run_qc(
            config,
            fail_fast=config.fail_fast_qc,
            _content_basis=initial_basis,
        )
        stage_metadata = {"passed": bool(result.passed)}
    else:
        from polisyos.data_forge.domains.catalog.batch.publish import run_publish

        result = run_publish(config)
        stage_metadata = {"manifest": str(result)}
    if _stage_input_basis(config, stage) != initial_basis:
        raise RuntimeError(f"{stage} inputs changed while its producer was running")
    _record_stage_completion(config, stage, metadata=stage_metadata)
    receipt = current_content_stage_receipt(config, stage)
    if receipt is None or receipt.get("state") not in {"current", "not_established"}:
        raise RuntimeError(f"{stage} producer did not publish a content-bound receipt")
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
            from polisyos.data_forge.domains.catalog.batch.embedder import (
                _cached_encoder,
            )

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
    if isinstance(input_basis, Mapping):
        profile_state, _profile_coverage = _basis_profile_input_currentness(input_basis)
        stage_metadata["currentness_state"] = (
            "current" if profile_state == "established" else "not_established"
        )
        stage_metadata["currentness_reason"] = _profile_input_currentness_reason(profile_state)
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
    from polisyos.data_forge.domains.catalog.batch.config import (
        _runtime_source_profile_snapshot_scope,
    )

    with _runtime_source_profile_snapshot_scope():
        return await _run_dataset_pipeline_with_profile_snapshot(config, thermal=thermal)


async def _run_dataset_pipeline_with_profile_snapshot(
    config: DatasetBatchConfig, *, thermal: bool = False
) -> PipelineStats:
    """Run stages under the single profile snapshot captured by the public entrypoint."""
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
    from polisyos.data_forge.domains.catalog.batch.normalizer import (
        normalize_raw_sources,
    )

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
                    config,
                    "harvest",
                    metadata={"records": stats.metrics["harvest_records"]},
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
                    config,
                    "normalize",
                    metadata={"records": stats.metrics["normalized_records"]},
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
