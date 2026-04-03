# Batch Common (`polisyos.batch_common`)

`polisyos.batch_common` содержит shared helpers для staged/offline pipelines:
manifest writing, QC, thermal pacing, hashing и snapshot-path conventions для
Lex, Scholar, datasets и related batch surfaces.

## Role in System

- **Depends on:** `polisyos.core`, `polisyos.ir`, standard library helpers
- **Used by:** `polisyos.academic`, `polisyos.datasets`, batch-style ingestion and publishing flows
- Пакет удерживает общие batch primitives вне доменных модулей, чтобы новые offline subsystems начинались с общего house style.

## Key Concepts

- **Manifest writers** - canonical publish/raw/stage manifest helpers.
- **QC contracts** - shared pass/fail report objects for offline stages.
- **Thermal pacing** - cooldown and pacing helpers for rate-limited harvest loops.
- **Snapshot paths** - deterministic directory conventions for staged outputs.

## Public API

- `write_publish_manifest(...)`, `write_raw_manifest(...)`, `write_stage_manifest(...)`
- `QCCheck`, `QCReport`, `evaluate_fail_fast(...)`, `write_qc_report(...)`
- `Phase0QualityCheck`, `Phase0QualityReport`, `evaluate_phase0_quality(...)`
- `snapshot_component_dir(...)`, `sha256_file(...)`, `sha256_jsonl(...)`

## Current State

- Last updated: 2026-04-03
- Status: shared experimental helper surface for offline pipelines
