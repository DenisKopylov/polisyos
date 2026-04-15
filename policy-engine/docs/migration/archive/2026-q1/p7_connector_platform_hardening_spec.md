# P7 Connector Platform Hardening - Detailed Specification

- Status: Implemented
- Version: 1.0
- Effective phase: P7 (`2026-04-27` -> `2026-05-10`)
- Hard deadline for legacy helper removal: `2026-06-30`
- Scope: `policy-engine`
- Owners: `team-fabric` (primary), `team-core`, `team-scientist`
- Related docs:
  - `p6_plugin_unification_spec.md`
  - `p1_refactor_queue.md`
  - `src/polisyos/fabric/connectors/README.md`
  - `src/polisyos/fabric/connectors/sources/world_bank.py`
  - `src/polisyos/fabric/connectors/sources/eurostat.py`
  - `src/polisyos/fabric/connectors/sources/ukons.py`
  - `src/polisyos/fabric/ingestion.py`
  - `tests/fabric/connectors/sources/test_production_connectors.py`

## 1. Context and Problem Statement

After P6, plugin bootstrap is unified but production connector implementations remain partially duplicated and operationally inconsistent.

Current hardening gaps:

| Area | Current state | Impact |
| --- | --- | --- |
| HTTP runtime duplication | `world_bank.py`, `eurostat.py`, `ukons.py` duplicate connection/session/request/error/version helper logic | High maintenance cost, drift risk |
| Resilience policy shape | Retry and circuit-breaker values hardcoded per method; `ConnectionConfig.max_retries`, `retry_delay_seconds`, `rate_limit_rps` not consistently honored | Unpredictable runtime behavior across connectors |
| Fetch envelope completeness | `fetch_duration_ms`, `resilience`, `quality_flags`, `evidence_ref` are not explicitly populated in production connectors | Weak observability and downstream governance context |
| Freshness/evidence normalization | Versioning/freshness logic duplicated; evidence fields rely on ad-hoc mapping in ingestion | Inconsistent provenance semantics |
| CI guardrails | No dedicated gate preventing reintroduction of connector-source helper duplication | Drift can return after refactors |

Measured baseline (`2026-02-10`, code scan + local metrics):

1. Source size:
   - `world_bank.py`: `437` LOC
   - `eurostat.py`: `447` LOC
   - `ukons.py`: `406` LOC
2. Duplicate function blocks across the three files: `28` occurrences (including `connect`, `disconnect`, `_get_session`, `_request_json`, `_build_version`, `_retry_after_seconds`, `_parse_http_datetime`, `_frame_completeness`).
3. Pairwise file similarity:
   - `world_bank.py` vs `eurostat.py`: `0.626`
   - `world_bank.py` vs `ukons.py`: `0.677`
   - `eurostat.py` vs `ukons.py`: `0.683`
4. Architecture freeze status remains healthy:
   - `package_cycles_count = 0`
   - `import_violations_count = 0`
   - `test_collect_errors_count = 42`

Net effect: architecture is stable, but connector runtime is not yet hardened for predictable behavior at ingestion scale.

## 2. Goals and Non-Goals

### 2.1 Goals (MUST)

1. Introduce a canonical `HTTPConnectorBase` for HTTP/JSON connectors with shared lifecycle, request execution, rate-limit handling, and version construction.
2. Migrate `WorldBankConnector`, `EurostatConnector`, and `UKONSConnector` to the canonical base.
3. Standardize fetch envelope production for retry/version/freshness/evidence-ready metadata.
4. Make resilience defaults profile-driven and aligned with `ConnectionConfig` knobs.
5. Add CI and tests that prevent duplicated helper logic from reappearing in `sources/` production connectors.
6. Preserve connector external contracts (`connector_id`, schema IDs, output columns) for one-release compatibility.

### 2.2 Non-Goals (P7)

1. Redesign source-specific parsing or domain semantics of datasets.
2. Foundry input binding contract rollout (`P8` scope).
3. Full governance hard-blocking on quality tiers (deferred to data-plane quality gates stream).
4. Plugin discovery redesign (already covered by `P6`).

## 3. Normative Language

This document uses:

- `MUST` / `MUST NOT` for hard requirements.
- `SHOULD` / `SHOULD NOT` for strong recommendations.
- `MAY` for optional behavior.

## 4. Target Architecture Contract

### 4.1 Canonical HTTP connector stack

P7 introduces canonical HTTP runtime ownership:

1. New base module:
   - `src/polisyos/fabric/connectors/sources/http_base.py`
2. Optional shared helpers module:
   - `src/polisyos/fabric/connectors/sources/http_common.py` (or equivalent)
3. Production connectors under `sources/` MUST subclass `HTTPConnectorBase` unless non-HTTP.

`HTTPConnectorBase` MUST provide:

1. Session lifecycle (`connect`, `disconnect`, `_get_session`) with config-driven timeout.
2. Request execution helper with standardized status handling:
   - `429` -> `RateLimitError` with parsed retry-after.
   - `>=400` -> `FetchError` with status/URL context.
   - invalid JSON -> `FetchError`.
3. Deterministic version builder:
   - `ETag` -> `Last-Modified` -> `content_hash`.
4. Standard metrics assembly:
   - `fetch_duration_ms`
   - `bytes_transferred`
   - `version`, `source_updated_at`, `completeness`
5. Canonical retry-after parser fallback chain:
   - `Retry-After` header
   - `X-RateLimit-Reset`
   - `None`.

### 4.2 Resilience profile contract

P7 defines a per-connector resilience profile consumed by the base runtime:

1. `max_attempts`, `base_delay`, jitter policy.
2. circuit breaker config (thresholds/timeouts).
3. optional rate-limit config (`rate_limit_rps`, cooldown behavior).
4. default profile MAY be overridden by `ConnectionConfig` runtime knobs.

Hard requirements:

1. Production connectors MUST NOT hardcode retry/circuit behavior directly on each method once migrated.
2. `ConnectionConfig.max_retries` and `retry_delay_seconds` MUST be honored by default.
3. If `rate_limit_rps` is set, request path MUST apply rate-limiter middleware.

### 4.3 Fetch envelope invariants

For all P7-hardened production connectors:

1. `FetchResult.fetch_duration_ms` MUST be populated (>0 for successful online fetches).
2. `FetchResult.bytes_transferred` MUST reflect raw payload bytes (across all pages for paginated APIs).
3. `FetchResult.version.content_hash` MUST always be non-empty.
4. `source_updated_at` MUST be set when reliable source timestamps exist (headers or canonical source field).
5. `quality_flags` SHOULD include standardized freshness/evidence hints when source metadata is partial.
6. `schema_id`/`schema_version` and row-level columns MUST remain backward-compatible.

### 4.4 Evidence/freshness readiness contract

P7 does not require full governance blocking, but MUST standardize evidence-ready metadata:

1. `run_connectors_ingestion(...)` MUST persist normalized fetch activity fields:
   - version strategy/value/hash
   - row count/completeness
   - freshness-relevant timestamps
   - PII summary (existing behavior)
2. Connector-level output MUST remain sufficient for deterministic provenance graph generation.
3. Ingestion SHOULD add structured notes per dataset for downstream quality/evidence auditing (without changing `EvidenceBundle` schema in this phase).

### 4.5 Source-module hard boundaries after P7

After cutover:

1. `world_bank.py`, `eurostat.py`, `ukons.py` MUST NOT define duplicated generic helpers:
   - `_get_session`
   - `_request_json`
   - `_retry_after_seconds`
   - `_build_version`
   - `_parse_http_datetime`
   - `_frame_completeness`
   - `_safe_int` / `_safe_float` (unless source-specific behavior differs and is documented)
2. Source modules SHOULD contain only:
   - API-specific endpoint and parameter mapping
   - source-specific payload parsing/normalization
   - schema/capability metadata and dataset catalog logic.

## 5. Detailed Technical Design

### 5.1 Base runtime extraction

Required additions:

1. `src/polisyos/fabric/connectors/sources/http_base.py`
   - `HTTPConnectorBase` class.
   - protected hooks for request-plan and payload-to-frame conversion.
2. shared utility module for HTTP/version/freshness primitives.
3. unit tests for base behavior (status handling, version precedence, retry-after parsing, session lifecycle).

Required behavior:

1. Base uses `aiohttp.ClientSession` reused per connection handle.
2. Base returns typed envelopes `(payload, headers, raw_bytes)` for parser hooks.
3. Base exposes helper for paginated payload hashing via `streaming_hash(...)`.

### 5.2 Production connector migration

Files to migrate:

1. `src/polisyos/fabric/connectors/sources/world_bank.py`
2. `src/polisyos/fabric/connectors/sources/eurostat.py`
3. `src/polisyos/fabric/connectors/sources/ukons.py`

Migration requirements:

1. Preserve current connector IDs:
   - `worldbank.wdi`
   - `eurostat.data`
   - `ukons.datasets`
2. Preserve schema IDs:
   - `worldbank.wdi.generic`
   - `eurostat.data.generic`
   - `ukons.datasets.generic`
3. Preserve current output column sets and ordering in `_contracts/*`.
4. Move duplicated helper logic to base/shared modules.
5. Keep public class names unchanged for registry/discovery compatibility.

### 5.3 Fetch result normalization updates

Required updates (connector-level or base-level):

1. Populate `fetch_duration_ms` for all fetch paths.
2. Ensure pagination-aware `bytes_transferred`.
3. Standardize `DataVersion` generation via shared helper only.
4. Standardize completeness computation via shared helper.
5. Add optional `resilience` enrichment when retries/fallback/rate-limits occur.

### 5.4 Ingestion integration hardening

Required changes:

1. `src/polisyos/fabric/ingestion.py`
   - ensure fetch activity payloads include all standardized version/freshness fields emitted by hardened connectors.
   - maintain deterministic manifest hash and provenance graph generation.
2. `src/polisyos/fabric/connectors_ingestion.py`
   - no API breaking change; remains canonical entrypoint.
3. `src/polisyos/fabric/_connector_bridge.py`
   - continue returning canonical `FetchResult`; no direct dependency on connector internals.

### 5.5 Tooling and lint gates

Required additions:

1. New lint tool (name TBD, recommended `tools/lint/lint_connector_hardening.py`) to enforce:
   - production sources subclass `HTTPConnectorBase` (for HTTP connectors),
   - forbidden duplicated helper definitions are absent.
2. CI integration:
   - add lint step in `.github/workflows/arch-freeze.yml` or a dedicated connectors workflow.
3. Existing `lint_connectors.py` remains in place for Law A/B boundaries.

## 6. Migration Plan (2 Weeks)

### 6.1 Milestones

1. `M1` (`2026-04-27` -> `2026-04-29`):
   - implement `HTTPConnectorBase` + shared helper module + unit tests.
2. `M2` (`2026-04-29` -> `2026-05-03`):
   - migrate `world_bank` and `eurostat`.
3. `M3` (`2026-05-03` -> `2026-05-07`):
   - migrate `ukons`, align ingestion fields, add lint guard.
4. `M4` (`2026-05-08` -> `2026-05-10`):
   - docs/governance updates, CI stabilization, freeze evidence.

### 6.2 PR slicing (recommended)

1. `PR-A`: base extraction + tests.
2. `PR-B`: world_bank + eurostat migration.
3. `PR-C`: ukons migration + ingestion normalization.
4. `PR-D`: lint/CI/docs/governance closure.

## 7. CI and Governance Updates

### 7.1 Mandatory artifact updates

1. `p1_refactor_queue.md`
   - dedicated P7 work item (`Q8`) is closed.
2. `p7_connector_platform_hardening_spec.md`
   - status progression (`Proposed` -> `Implemented`) with evidence section.
3. `import_exceptions.toml` / `import_exceptions_registry.md`
   - P7 SHOULD not require new architecture exceptions.

### 7.2 Required verification commands

Architecture and freeze checks:

```bash
python3 tools/lint/collect_arch_metrics.py \
  --repo-root . \
  --output-dir .tmp/p7_metrics \
  --summary-path .tmp/p7_metrics/summary.json \
  --print-summary

python3 tools/lint/compare_baseline.py \
  --baseline summary.json \
  --current .tmp/p7_metrics/summary.json \
  --mode blocking \
  --exceptions import_exceptions.toml \
  --exceptions-registry import_exceptions_registry.md \
  --baseline-import-gate import_gate.txt \
  --current-import-gate .tmp/p7_metrics/import_gate.txt \
  --debt-register import_debt_register.csv
```

Connector hardening checks:

```bash
python3 tools/lint/lint_connectors.py --src-root src/polisyos/fabric/connectors --strict
python3 tools/lint/lint_connector_hardening.py
```

Targeted tests (minimum):

```bash
python3 -m pytest \
  tests/fabric/connectors/sources/test_production_connectors.py \
  tests/fabric/connectors/test_protocol_compliance.py \
  tests/fabric/connectors/test_resilience.py \
  tests/fabric/connectors/test_quality_system.py
```

Required new P7 tests:

```bash
python3 -m pytest \
  tests/fabric/connectors/sources/test_http_connector_base.py \
  tests/fabric/connectors/sources/test_http_version_policy.py \
  tests/fabric/connectors/sources/test_no_duplicate_http_helpers.py \
  tests/fabric/connectors/test_ingestion_fetch_activity_contract.py
```

## 8. Acceptance Criteria and DoD

P7 is complete only if all criteria are met:

1. `WorldBankConnector`, `EurostatConnector`, and `UKONSConnector` use shared `HTTPConnectorBase`.
2. Duplicate helper blocks in these three modules are reduced by at least `60%` (baseline: `28` duplicate occurrences).
3. All three connectors populate standardized fetch envelope metrics (`fetch_duration_ms`, `bytes_transferred`, canonical `DataVersion`).
4. Connector IDs, schema IDs, and output columns stay backward-compatible.
5. Hardening lint passes in CI and blocks helper duplication regressions.
6. Architecture freeze blocking check passes with no regressions.

## 9. Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Behavior drift in source-specific parsers during refactor | High | Golden tests for each production connector output columns and row semantics |
| Retry/rate-limit tuning regressions in production APIs | High | Profile defaults + integration tests with mocked 429/5xx flows |
| Scope creep into full quality-governance blocking | Medium | Keep P7 to normalization/readiness; defer hard gates to dedicated stream |
| CI flakiness due external dependency/env mismatch | Medium | Keep source tests mock-based; pin required test deps in CI environment |
| Reintroduction of duplicated helpers after future edits | Medium | Add dedicated lint gate and AST-based regression test |

## 10. Post-P7 Follow-Ups (Out of Scope)

1. Enforce quality/freshness gate thresholds before expensive Scientist stages (`B5` stream).
2. Extend the hardened base pattern to non-HTTP connectors where appropriate.
3. Evaluate convergence between `reference/rest_json.py` and `HTTPConnectorBase` to avoid parallel base abstractions.
4. Remove any temporary compatibility wrappers by `2026-06-30`.

## 11. Baseline Snapshot for P7 Planning (`2026-02-10`)

Reference snapshot captured for this specification:

- `package_cycles_count = 0`
- `import_violations_count = 0`
- `test_collect_errors_count = 42`
- `ruff_total_issues = 1270`
- `stale_sources_missing_paths_count = 40`
- `compare_baseline.py --mode blocking`: `[OK] Architecture freeze checks passed.`

Connector hardening baseline:

1. Production source modules total LOC: `1290`.
2. Repeated helper blocks across three production connectors: `28` occurrences.
3. No explicit `fetch_duration_ms` population in production fetch implementations.
4. Retry/rate-limit configuration currently not unified through `ConnectionConfig` knobs.

## 12. Implementation Evidence (`2026-02-10`)

### 12.1 Shared HTTP runtime implemented

1. Added canonical HTTP helper/runtime modules:
   - `src/polisyos/fabric/connectors/sources/http_common.py`
   - `src/polisyos/fabric/connectors/sources/http_base.py`
2. `HTTPConnectorBase` now owns:
   - session lifecycle (`connect`, `disconnect`, `_get_session`),
   - standardized HTTP JSON handling (`429`, `>=400`, invalid JSON),
   - deterministic data version assembly (`ETag -> Last-Modified -> content_hash`),
   - merged resilience config from `ConnectionConfig` and connector profile,
   - standardized `FetchResult` envelope assembly (duration/bytes/version/freshness/quality flags).

### 12.2 Production connectors migrated

1. Migrated production connectors to shared base:
   - `src/polisyos/fabric/connectors/sources/world_bank.py`
   - `src/polisyos/fabric/connectors/sources/eurostat.py`
   - `src/polisyos/fabric/connectors/sources/ukons.py`
2. Connector contracts preserved:
   - IDs: `worldbank.wdi`, `eurostat.data`, `ukons.datasets`
   - Schema IDs: `worldbank.wdi.generic`, `eurostat.data.generic`, `ukons.datasets.generic`
   - Output columns unchanged (source-specific normalization preserved).
3. Source modules no longer define duplicated generic helpers (`_get_session`, `_request_json`, `_build_version`, `_retry_after_seconds`, `_parse_http_datetime`, `_frame_completeness`, `_safe_int`, `_safe_float`).
4. Duplicate function-block evidence (AST identical blocks across three production connectors):
   - baseline: `28` occurrences
   - after P7: `0` occurrences
   - reduction: `100%` (`>=60%` target met).

### 12.3 Ingestion normalization hardened

1. Updated fetch activity payload generation in:
   - `src/polisyos/fabric/ingestion.py`
2. Added normalized fields:
   - `source_updated_at`
   - `fetch_duration_ms`
   - `quality_flags`
   - `not_modified`
3. Provenance graph entity attributes now include normalized freshness/duration/quality fields.
4. Evidence bundle notes now include per-dataset summary entries (`connector:dataset`, rows, version).

### 12.4 Lint and CI hardening

1. Added dedicated lint tool:
   - `tools/lint/lint_connector_hardening.py`
2. CI integration added:
   - `.github/workflows/arch-freeze.yml` now runs `python3 tools/lint/lint_connector_hardening.py`.
3. Existing Law A/B connector lint remains active:
   - `tools/lint/lint_connectors.py`.

### 12.5 Tests added/updated

Added:

1. `tests/fabric/connectors/sources/test_http_connector_base.py`
2. `tests/fabric/connectors/sources/test_http_version_policy.py`
3. `tests/fabric/connectors/sources/test_no_duplicate_http_helpers.py`
4. `tests/fabric/connectors/test_ingestion_fetch_activity_contract.py`

Updated:

1. `tests/fabric/connectors/sources/test_production_connectors.py` (envelope assertions: `fetch_duration_ms`, `quality_flags` behavior).

### 12.6 Verification results

1. Connector lint gates:
   - `python3 tools/lint/lint_connectors.py --src-root src/polisyos/fabric/connectors --strict` -> `all clean`
   - `python3 tools/lint/lint_connector_hardening.py` -> `all checks passed`
2. Targeted regression + P7 tests:
   - `uv run --group test python -m pytest ...` (production connectors + new P7 tests + protocol/resilience/quality suites)
   - Result: `85 passed`.
3. Architecture freeze:
   - `python3 tools/lint/collect_arch_metrics.py ...`
   - `python3 tools/lint/compare_baseline.py --mode blocking ...`
   - Result: `[OK] Architecture freeze checks passed.`
   - Snapshot: `package_cycles_count=0`, `import_violations_count=0`, `test_collect_errors_count=42`.

### 12.7 Governance updates

1. Closed P7 queue item:
   - `p1_refactor_queue.md` (`Q8 -> Done`, `2026-02-10`).
2. Spec status updated:
   - `p7_connector_platform_hardening_spec.md` -> `Status: Implemented`.
3. No new architecture exceptions were introduced in this phase.
