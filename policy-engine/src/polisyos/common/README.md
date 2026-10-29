# Common (`polisyos.common`)

## Purpose

`polisyos.common` is the lowest reusable layer in the PolicyOS dependency
graph. It owns side-effect-sensitive bootstrap helpers, logging, async
bridging, canonical JSON serialization, UTC time utilities, and package-local
migration primitives. Keep domain logic out of this package.

## Where to Start

- `src/polisyos/common/__init__.py` for the lazy facade contract.
- `src/polisyos/common/serialization/__init__.py` owns canonical JSON conversion, LLM-response
  extraction, and the public strict object decoder. Its `_strict_json.py` child owns duplicate-key,
  non-finite, and overflowing-number rejection for persisted object intake.
- `src/polisyos/common/timestamps/__init__.py` owns aware-UTC parsing and formatting;
  `_ordering.py` owns latest-fact selection.
- `src/polisyos/common/async_tools/__init__.py` owns the sync/async bridge API, shared worker
  admission, and Future lifecycle classes. Keep those class bodies in this owner so reflection and
  pickle lookup resolve the real definitions.
- `src/polisyos/common/job_execution_interrupt.py` carries a context-local signal bound to a
  leased job, worker and attempt. It reports observed lease loss to cooperating owners;
  it does not attest that a thread, provider, or external effect has stopped.
- `src/polisyos/common/config/__init__.py` owns process configuration and private environment
  parsing. `_logging.py` installs sinks only when explicit bootstrap calls it.
- `src/polisyos/common/jax_env/__init__.py` applies the safe backend defaults; `_policy.py` is the
  private pure backend-selection predicate.
- `src/polisyos/common/logger/__init__.py` owns the logger adapter classes and trace-context behavior.
- `src/polisyos/common/migrations/README.md` documents package-local artifact migrations.

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

- Supported package entrypoints: `polisyos.common`, `polisyos.common.text`,
  `polisyos.common.canonical`, `polisyos.common.canonical_profile`, and
  `polisyos.common.hashing`.
- `polisyos.common.text` provides pure shared whitespace normalization through
  `collapse_ws`; existing Lex consumers retain that same function object through
  the lazy root facade.
- The canonical modules own shared byte/profile mechanics. A verified
  CanonicalProfileRead may name the fixed reader policy that materialized it;
  core-tag-policy@1 and ir-tag-policy@1 remain separate owner identities.
  This context does not attest a producer or establish schema, authority, or
  currentness; Core and IR keep their distinct tags and admission rules. The reader identity is materialization context only and never a substitute for the caller's expected artifact contract.
- Lazy facade exports from `src/polisyos/common/__init__.py` remain:
  `async_tools`, `config`, `jax_env`, `logger`, `migrations`,
  `serialization`, `text`, `timestamps`.

- Private environment parser functions remain in `config/__init__.py`; do not treat them as
  stable public surface without updating the facade and
  [Public Surface](../../../docs/reference/public-surface.md).

## Bounded canonical codec

`polisyos.common.canonical.to_bounded_canonical_bytes` is a direct codec entry point for
callback-free values under a caller-supplied `CanonicalResourceLimits`. The vector separates
encoded wire bytes, JSON container depth and lexical elements (including member-name strings)
from `CanonSpec.max_depth`, which governs logical value depth. The encoder admits a detached
specification before reading the value, incrementally measures the wire grammar and serializes
an owned snapshot of the measured value. A missing or exceeded limit gives a typed refusal.
Each occurrence of a shared value counts; cycles and unsupported projections refuse.

The bounded domain consists of exact built-in `None`, `bool`, `int`, `float`, `str`, `bytes`,
`list`, `tuple` and `dict` values with exact `str` keys, plus the three exact Core representation
carrier types under the selected `.3` grammar and tag policy. The bounded `canonical_types`
argument must be an exact `frozenset` whose strings belong to the shared native-tag registry.
Pydantic models, dataclasses, Decimal, enums, custom mappings and other callback-bearing values
need an owner-provided bounded projection and are refused by this entry point. Existing unbounded
codec calls and accepted `.2` named hash domains retain their own historical behavior.

`policy_id` labels the supplied vector; it does not establish owner authorization, reader
readiness, backend limits or producer authority. Wire limits are not a process RSS guarantee,
and construction of a carrier before this call is outside its vector. The snapshot is not an
atomic event-consistent read of a graph concurrently mutated by a caller; owners that need that
property must use their own version or lock. The `.3` artifact writer remains disabled until its
actual selected reader, owner policy and consumer cohort are admitted and verified. This direct
codec does not by itself establish persisted-profile or E02 acceptance.

## Internal Layout

- `__init__.py` owns the public lazy facade.
- The six stable helper module identities are implemented as same-name packages. Their package
  initializers preserve existing public module paths and define every pre-existing class at its natural
  owner FQN, so `__module__`, `inspect.getsource`, and class-object pickle lookup resolve to the class
  body. Cohesive children hold only extracted helper concerns: logging sinks, JAX backend selection,
  strict JSON intake, and latest-fact ordering. New helpers stay private when they were not old module
  bindings.
- `canonical_profile.py` is a supported, storage-agnostic owner: it parses the exact raw selected
  manifest, distinguishes a missing declaration from malformed-present data, verifies declared
  payload bytes with caller-supplied codecs, and preserves the shared selected-read distinction
  between true absence and owner-coded refusal. Callers retain their own typed tags, exception codes,
  and admission rules. `common/_selected_artifact_intake.py` is an identity-preserving compatibility
  import path to the same selected-read helper. Neither helper establishes writer identity or producer
  authority.
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

- Focused Common behavior tests:
  `uv run pytest -q tests/unit/common/test_package_rehome.py tests/unit/common/test_async_tools.py tests/unit/common/test_config_bootstrap.py tests/unit/common/test_fast_json_serialization.py tests/unit/common/serialization/test__strict_json.py tests/property/common/test_serialization_properties.py tests/unit/common/test_logger.py tests/unit/common/test_timestamps.py tests/unit/common/test_migrations_purity.py tests/unit/common/migrations/test_base.py tests/unit/common/migrations/test_manifest.py tests/unit/common/test__selected_artifact_intake.py tests/unit/common/jax_env/test__policy.py tests/unit/common/test_text.py`

- Conceptual release gate: `uv run python tools/devx/workspace/core_runtime_mypy.py`
- Conceptual release gate:
  `uv run python tools/devx/workspace/core_runtime_basedpyright.py`

## Shared executor ownership

`async_tools/__init__.py` returns a `concurrent.futures.Future` compatible proxy. A job
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

`run_blocking_async` records the callable's monotonic completion time in its
worker receipt before the executor Future is delivered to the event loop. If
that receipt proves the callable completed within the helper wait deadline, a
late Future callback does not discard the completed value or original error.
A completion after that deadline remains a helper timeout. Cancelling queued
work is supported; an already running thread remains cooperative and can finish
after the caller receives a timeout.

These helpers own execution/callback lifecycle, not tenant authority or external
effect rollback. Callers retain their current publication and permission checks;
a timely helper completion does not extend an owner's separate commit deadline.

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

- Last updated: 2026-10-18

## Selected persisted canonical readers

Concrete Core and IR readers explicitly admit canonical JSON `.2` and `.3`
versions when parsing a selected manifest. `parse_canonical_profile` accepts the
reader owner's optional `supported_versions` tuple; omission retains its default
version-only behavior. This tuple selects declared codec support, not producer
authenticity, schema ownership, resource admission or policy authority. Unknown
versions remain candidates until the concrete owner supplies an interpretation.
See the [qualified read contract](../../../docs/reference/canonical-json-profile-reads.md).

## Scoped bounded artifact writer mechanics

The private bounded encoder can return its owned primitive snapshot with the same
bytes calculation. Core may issue a per-call mechanical `.3` writer context for
an exact `CanonSpec` and resource vector. The context does not appoint an artifact
owner, producer, ready reader or authority. Core separately validates and seals
the real source policy, value, selected inputs, backend and actual manifest before
publication. The public unqualified artifact writer remains `.2`.

The first source-owned JSON sidecar cohort accepts exact JSON builtins only. It
refuses models, Decimal, bytes, tuple, custom mappings and signed negative zero
before their projection/serializer callbacks. Generic canonical `.2` and explicit
bounded native APIs keep their existing contracts. The `.3` primitive cohort
refuses signed negative zero because historical generic float canonicalization
normalizes it; this does not change Foundry's distinct float-hex carrier law.

The same private traversal also supplies a non-emitting preflight for Core's
primitive manifest metadata. It charges the complete actual projection before
the final JSON serializer; it does not introduce another codec or budget owner.

## Candidate producer request boundary

The governed `polisyos.common.producer_request` facade routes the generic
stdlib-only implementation. Actual owners issue complete prepared calls; async
scopes reconcile the complete signature-derived quantity and mandatory context.
The actual Gateway prepares an immutable emission obligation and checks it at
send, including deferred execution and its closed JSON-only fallback. This
carrier has no N4 stage vocabulary and authenticates no external issuer.

Core's prepared-input occurrence reuses a transform only after this actual active
owner scope reconciles its complete call. Text, a flag, or a marker hash does not
establish that occurrence. New raw input always remains subject to its real
configured privacy transform.

A Core preparation scope is not itself an invocation permit: the actual Core
generate entry consumes the shared atomic permit before its first await. The
Recorder's opaque handle is a reserved local Python argument, removed before the
common complete wire-call admission; it never enters JSON metadata or digests.
