# Common (`polisyos.common`)

## Purpose

`polisyos.common` is the lowest reusable layer in the PolicyOS dependency
graph. It owns side-effect-sensitive bootstrap helpers, logging, async
bridging, canonical JSON serialization, UTC time utilities, and package-local
migration primitives. Keep domain logic out of this package.

## Where to Start

- `src/polisyos/common/__init__.py` for the lazy facade contract.
- `src/polisyos/common/serialization.py` for canonical JSON helpers and
  round-trip guarantees. Its strict UTF-8 JSON-object decoder is the shared
  persisted-record intake primitive. It refuses malformed/non-object input, non-finite or
  overflowing numbers, and duplicate object keys at any depth. Valid JSON null and booleans remain
  values for the owning typed consumer to validate.
  It also owns extraction of syntactically valid JSON
  from LLM response text. Extraction produces a candidate value; downstream
  schema, grounding and authority checks remain mandatory. The former
  unregistered `common/llm_json.py` implementation is consolidated here.

- `src/polisyos/common/timestamps.py` for aware-UTC parsing and formatting.
- `src/polisyos/common/async_tools.py` for sync/async bridge utilities and the
  shared executor.

- `src/polisyos/common/config.py` and `src/polisyos/common/jax_env.py` for
  early-process bootstrap behavior.

- `src/polisyos/common/migrations/README.md` for package-local artifact
  migrations.

- `src/polisyos/common/env_parsing.py` if you are working on bootstrap
  internals; it is intentionally not part of the exported facade.

## Internal Markdown table syntax

`markdown.py` owns `split_markdown_table_row(text: str) -> list[str]`, an internal,
stdlib-only syntax API. It separates delimiter pipes from escaped pipes and
pipes inside matched, equal-length backtick runs (including multiple backticks).
Unmatched runs remain literal. Optional outer delimiters are removed; empty cells
and source text inside cells, including whitespace and escapes, are preserved.
Consumers trim display values themselves and retain original bytes for hashes.

Ledger and custody consumers share this tokenizer before applying their own
column grammar. Tokenization establishes no identity, status, ownership or
command authority; custody admission still checks the fixed appointment contract
and byte digests. The browser counterpart lives beside the trust posture consumer.
Both implementations exercise `tests/fixtures/common/markdown_table_rows.json`.
This module is not exported through the Common facade. For consumer authoring,
follow the [measurement register decision](../../../docs/superpowers/specs/2026-09-12-measurement-register-format.md).

## Public API

- Supported package entrypoints: `polisyos.common`, `polisyos.common.canonical`,
  `polisyos.common.canonical_profile`, and `polisyos.common.hashing`.
- The canonical modules are the shared mechanics and strict selected-profile
  readers. They do not attest producer identity or authority; Core and IR keep
  their own profile-specific tags, exceptions, and admission rules.
- Lazy facade exports from `src/polisyos/common/__init__.py` remain:
  `async_tools`, `config`, `jax_env`, `logger`, `migrations`,
  `serialization`, `timestamps`.

- Internal-but-frequently-touched helper: `env_parsing.py`; do not treat it as
  stable public surface without updating the facade and
  [Public Surface](../../../docs/reference/public-surface.md).

## Internal Layout

- `__init__.py` owns the public lazy facade.
- `serialization.py`, `timestamps.py`, and `async_tools.py` are the shared
  helper surfaces used across packages. `canonical_profile.py` is a supported, storage-agnostic helper: it parses the exact raw selected manifest, distinguishes
  a missing declaration from malformed-present data, and applies caller-supplied
  codecs to verify declared payload bytes. The caller keeps its own typed tags and
  exceptions. The internal `common/_selected_artifact_intake.py` wrapper preserves
  `None` only for a missing selector; once selected, expected storage, decoding,
  and validation failures or a reader-returned `None` become an owner-coded
  `CanonicalProfileRefusalError`, while unexpected exceptions propagate unchanged.
  It is not exported by either Common facade or the supported profile module.
  The intake wrapper establishes no writer identity or producer authority.
- `config.py`, `jax_env.py`, and `env_parsing.py` are early-process bootstrap
  helpers; keep domain behavior out of them.
- `migrations/` owns package-local migration manifest helpers.

## Extension Points

`polisyos.common` is not an extension host. Extension hosts should depend on
Common only for bootstrap-safe helpers and must declare their own entry-point
group in [architecture/extension_points.toml](../../../architecture/extension_points.toml).

## Depends on / depended on by

Depends on: Python stdlib plus a small set of optional bootstrap/runtime
dependencies pulled in by individual helper modules.

Depended on by: `polisyos.core`, `polisyos.runtime`, `polisyos.fabric`,
`polisyos.foundry`, `polisyos.scientist`, `polisyos.lex`,
`polisyos.scholar`, and workspace tooling.

## Common commands

Run commands from the repository root `policy-engine/`.

- Smoke-tested:
  `PYTHONPATH=src:. uv run python -c "import polisyos.common as common; print(sorted(common.__all__))"`

- Smoke-tested:
  `PYTHONPATH=src:. uv run python -c "from polisyos.common.migrations.manifest import MANIFEST_CURRENT_VERSION; print(MANIFEST_CURRENT_VERSION)"`

The legacy manifest import above is a deprecated compatibility adapter.  The
schema-owner converter is
`polisyos.fabric.identity.migrations.migrate_manifest_0_9_to_1_0`; generic
Common migration imports stay Fabric-neutral.

## Tests

Run commands from the repository root `policy-engine/`.

- Smoke-tested:
  `uv run pytest -q tests/unit/common/test_async_tools.py tests/unit/common/test_config_bootstrap.py tests/unit/common/test_fast_json_serialization.py tests/unit/common/test_serialization_properties.py tests/unit/common/test_timestamps.py tests/unit/common/test_migrations_purity.py`

- Conceptual release gate: `uv run python tools/devx/workspace/core_runtime_mypy.py`
- Conceptual release gate:
  `uv run python tools/devx/workspace/core_runtime_basedpyright.py`

## Shared executor ownership

`async_tools.py` returns a `concurrent.futures.Future` compatible proxy. A job
retains its logical reservation while its worker wrapper or synchronous done
callbacks run, even after `result()` becomes available. Physical workers are
counted separately. Direct nested submissions from that executor's worker or
callback context receive `SharedExecutorReentrancyError` when capacity is fully
reserved or occupied. Ordinary external callers can queue work. Late callbacks
execute in their registering thread and retain the direct-submission reentry
guard; callbacks retain registration order and execute in the completing
thread. The synchronous dispatch bridge inlines only on a physical
shared-executor worker. A late callback using that bridge queues its dispatch
through the same bounded pool, and the submission captures the callback
thread's current context. Callback exceptions follow the standard Future
logging behavior.

Every submission captures its own current context. Queue cancellation prevents
unstarted work and notifies Future waiters; running callables and arbitrary
callback waits remain cooperative. Shutdown closes admission before entering
the base executor's shutdown lock, and no user callback runs under the admission
lock. `run_blocking_async(..., unbounded=True)` explicitly represents an owner
with no configured helper deadline. Omitted/None timeouts keep the existing
default; combining `unbounded=True` with a float timeout is invalid.

These helpers own execution/callback lifecycle, not tenant authority or external
effect rollback. Callers retain their current publication and permission checks.

Runtime composition may pin this same process-wide owner with the typed
`process_worker_capacity` and `process_worker_profile_revision` settings. The
Scientist `MethodBackend` submits its synchronous method dispatch through that
owner; nested dispatch from one of its workers runs inline. An omitted profile
keeps the legacy CPU-derived candidate fallback, and an explicit revision does
not establish deployment authority. The cap applies within one Python process;
separate processes do not share worker slots.

## Operability Links

- [Common component SLO](../../../ops/components/common/slo.yaml)
- [Common component runbooks](../../../ops/components/common/runbooks.md)
- [Generated artifacts reference](../../../docs/reference/generated-artifacts.md)
- [Core / Common / Runtime audit plan](../../../docs/plans/active/CORE_COMMON_RUNTIME_AUDIT_REMEDIATION_PLAN.md)

## Known Shims/Deprecations

There are no active package-local shims for `polisyos.common` in
[architecture/shims.toml](../../../architecture/shims.toml) as of 2026-05-06.
Promoting an internal helper such as `env_parsing.py` requires a facade update,
public-surface refresh, and compatibility note.

## Reference docs

- [Public Surface](../../../docs/reference/public-surface.md)
- [Generated Artifacts](../../../docs/reference/generated-artifacts.md)
- [Core / Common / Runtime Audit Remediation Plan](../../../docs/plans/active/CORE_COMMON_RUNTIME_AUDIT_REMEDIATION_PLAN.md)
- [Common migrations](migrations/README.md)

- Last updated: 2026-10-09
