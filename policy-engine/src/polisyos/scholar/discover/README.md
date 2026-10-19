# Scholar Discover (`polisyos.scholar.discover`)

`polisyos.scholar.discover` normalizes scholar seed sources and acquires their payloads. It keeps the
input side of the scholar pipeline deterministic before document processing and claim extraction begin.

## Role in System

- **Depends on:** `core.contracts.scholar` and the scholar orchestration layer.
- **Used by:** `scholar.orchestrator` during the discover/acquire phase.
- **Boundary function:** makes source normalization and acquisition logic reusable and testable.

## Key Concepts

- **Source normalization** - `manual.py` canonicalizes URLs, local files, and identity keys.
- **HTTP acquire** - `http_fetch.py` fetches remote content with size/time limits through the shared, redirect-aware destination-bound transport.
- **Local file acquire** - `local_files.py` reads file-based sources and resolves mime types.

## Public API

- `fetch_url`
- `read_local_file`
- `normalize_seed_sources`
- `source_identity_key`

## Current State

- Last updated: 2026-04-03
- The package still supports `url`, `local_file`, and `bytes` source kinds through the discover/acquire boundary.
- `fetch_url` and Scholar search both use `discover.transport.fetch_raw`; by default, every direct HTTP hop must resolve to globally routable numeric addresses and is bound to one of them, while the original hostname remains the HTTP Host and TLS SNI identity. Existing explicit private, loopback, link-local, multicast, reserved, and unspecified-address guards remain in force. `allow_private_networks=True` preserves the deliberate private-network exception. Redirect cycles are refused by urllib's bounded redirect lifecycle through the shared transport and both public adapters. Configured non-bypassed proxy routes fail closed until an admitted proxy destination-binding contract exists. A recognized `NO_PROXY` environment bypass is supported; on Python 3.14/macOS, SystemConfiguration wildcard exceptions may fail closed because urllib checks the supplied `hostname:port`. No broader proxy-bypass behavior is claimed.
- Source deduplication continues to prefer canonical URL, then official id, then source locator.
