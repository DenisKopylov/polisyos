"""Expose stable batch-pipeline helpers for manifests, QC, and thermal pacing.

This package is the shared platform layer for staged offline pipelines such as
Lex and Scholar batch runs. The exports are imported eagerly because they are
pure helper modules with no import-time hardware or network side effects.
"""

from __future__ import annotations

from polisyos.batch_common.hashing import sha256_file, sha256_jsonl
from polisyos.batch_common.manifest import (
    write_publish_manifest,
    write_raw_manifest,
    write_stage_manifest,
)
from polisyos.batch_common.paths import snapshot_component_dir
from polisyos.batch_common.phase0_quality_validation import (
    Phase0QualityCheck,
    Phase0QualityReport,
    Phase0QualityThresholds,
    evaluate_phase0_quality,
)
from polisyos.batch_common.qc import QCCheck, QCReport, evaluate_fail_fast, write_qc_report
from polisyos.batch_common.thermal import ThermalProfile, cooldown, pause_between_batches

__all__ = [
    "Phase0QualityCheck",
    "Phase0QualityReport",
    "Phase0QualityThresholds",
    "QCCheck",
    "QCReport",
    "ThermalProfile",
    "cooldown",
    "evaluate_fail_fast",
    "evaluate_phase0_quality",
    "pause_between_batches",
    "sha256_file",
    "sha256_jsonl",
    "snapshot_component_dir",
    "write_publish_manifest",
    "write_qc_report",
    "write_raw_manifest",
    "write_stage_manifest",
]
