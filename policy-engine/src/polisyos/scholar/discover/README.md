# Scholar Discover (`polisyos.scholar.discover`)

`polisyos.scholar.discover` normalizes scholar seed sources and acquires their payloads. It keeps the
input side of the scholar pipeline deterministic before document processing and claim extraction begin.

## Role in System

- **Depends on:** `core.contracts.scholar` and the scholar orchestration layer.
- **Used by:** `scholar.orchestrator` during the discover/acquire phase.
- **Boundary function:** makes source normalization and acquisition logic reusable and testable.

## Key Concepts

- **Source normalization** - `manual.py` canonicalizes URLs, local files, and identity keys.
- **HTTP acquire** - `http_fetch.py` fetches remote content with size/time limits.
- **Local file acquire** - `local_files.py` reads file-based sources and resolves mime types.

## Public API

- `fetch_url`
- `read_local_file`
- `normalize_seed_sources`
- `source_identity_key`

## Current State

- Last updated: 2026-04-03
- The package still supports `url`, `local_file`, and `bytes` source kinds through the discover/acquire boundary.
- Source deduplication continues to prefer canonical URL, then official id, then source locator.
