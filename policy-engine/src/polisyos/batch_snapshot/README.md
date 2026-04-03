# Batch Snapshot (`polisyos.batch_snapshot`)

`polisyos.batch_snapshot` завершает unified snapshot manifests и publish-time
metadata для offline pipeline outputs.

## Role in System

- **Depends on:** batch publishing metadata and snapshot conventions
- **Used by:** snapshot finalization flows and offline publish tooling
- Пакет остаётся узким boundary around snapshot finalization instead of spreading those rules across batch jobs.

## Key Concepts

- **Snapshot finalize** - единая точка, где staged artifacts становятся publishable snapshot.
- **Manifest closure** - финальная metadata envelope для downstream consumers.

## Public API

- Root package intentionally stays narrow; start from `cli.py`.

## Current State

- Last updated: 2026-04-03
- Status: experimental publish/finalization surface
