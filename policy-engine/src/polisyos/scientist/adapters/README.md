# Adapters (`polisyos.scientist.adapters`)

`adapters` implements the bridge between the Scientist workflow runtime and
external execution/data systems without routing direct Foundry/Fabric calls
through nodes.

## Role in the system

- **Depends on:** `core.contracts`, `core.security`, `foundry`, `fabric`
- **Used by:** `scientist.workflows`, built-in data/compile/simulate nodes
- The package isolates compile/execute and snapshot/materialization protocols behind typed ports.

## Key concepts

- **DefaultFoundryPort** — compile/execute bridge to the Foundry API.
- **DefaultFabricPort** — converts `DataViewRequest` into the snapshot/artifact surface.
- **Derived security artifacts** — TEE attestations and SBOMs can be published through the adapter path.
- **Workflow injection** — adapters are injected into `ExecutionContext` rather than hard-coded in nodes.

## Public API

- `DefaultFoundryPort`
- `DefaultFabricPort`

Details: [Reference →](../../../../docs/reference/scientist/index.md)

## Current state

- Last updated: 2026-04-03
- Python modules: 3
- Exports: 2
- The README follows the shared template; the API surface remains compact and stable.

## Explicit Federation capture consumer

DefaultFabricPort accepts an optional FederationFetchRequest while retaining the
legacy callback/default route. The opt-in supports one explicit unfiltered table
metric and a captured-row candidate scope; additional filters, temporal or other
query scopes, aggregation, access hints and cursor requests are refused before
producer invocation. Pagination limit bounds each actual capture and the final composed output;
known excess is refused before snapshot success, never waived as unknown EOF.

Before invoking even an injected callback, the port freezes the expected
constructor/request/source/order context and independently holds output_root.
It reopens the selected acquisition receipt from that root, verifies actual
selected kernel request/source members after replay, and ignores mutable
returned data/observations. A valid artifact for another request is not accepted
under the current DataViewRequest. The selected request ref is retained in the
actual persisted audit and snapshot input chain.

All FED Core payloads undergo bounded real CAN.2 encoding/decoding and semantic
comparison before publication, plus fresh selected readback. Data checks every
row/scalar/key; the schema retains column/dtype projection even when empty.
Kernel-declared null equivalence is preserved. Other semantics that CAN.2 rows
cannot exactly express produce a typed profile refusal, never silent float/sign,
timestamp or user-key coercion. No new row wire format or CAN.3 rollout is hidden.

The existing WarningsBundle carries the strict request-bound candidate audit.
Selected parents have explicit unavailable observation/warning history until an
independently bound bridge history exists; this is propagated as typed status
and actual warning flags, not erased into an empty quality set. Freshness,
source/output completeness and query fulfillment remain unestablished. The
selected digest proves conditional software derivation, not source authority.
Public/generated companions and real production/removal evidence require root
composition on exact source/profile.

The single fresh capture intake recomputes all row and declared whole-leaf
preferences from the independently frozen request and actual R4 graph. Receipt
hashes do not authenticate a connector fetch: same-intent synthetic content is
only a consumer-asserted candidate. The snapshot records that source scope and
keeps quality UNVERIFIED; no callback can self-upgrade capture origin.

The Federation opt-in compiles its complete supported query profile before the
legacy dataset resolver or any callback. A request ID is never a substitute for
the single explicit nonblank metric on this route. Every fresh source and held
parent is admitted against frozen captured-row bounds even when an inner JOIN
produces fewer rows.

No admitted dataset-shape/workflow basis exists in this captured-candidate
profile. Column names remain schema, not repeated-survey evidence. The FED
snapshot/audit therefore carry shape and workflow basis `not_established`;
legacy name-derived definite shape and routing notes are withheld on this route.
The default single-connector behavior is unchanged. A future shape projection
requires an independently admitted typed design basis, not a column-name rule.

An explicitly injected port may opt into a narrower registered-SQL acquisition
by supplying the actual registry, connector id, and
`require_fresh_registered_sql=True`. It captures one frozen configuration for the
connection and actual SQLite driver call, applies the configured SQLite
connection timeout, checks the registration, and refuses configured SQL,
unapplied connection settings, relative database paths, active event-loop
callers, other dialects, unsupported request scopes, table mismatch, and full limited
pages whose continuation cannot be established. It uses no result cache, retry,
or fallback. The bounded JSON-scalar result is the produced pandas view after
SQLite/driver conversion; it is not a claim about raw database representation.
The SQLite connection timeout does not bound an executing query.
It checks selected stored rows and schema against that observation and keeps
unknown source freshness/completeness and unsupported workflow shape explicit.

The installed Runtime can register, admit and withdraw an occurrence only for a
configured service principal with the corresponding distinct source permission.
It re-verifies the bearer, source slot and command through a verifier pinned to
the existing C105 owner; a role, source key or caller callback is not a grant.
The actual producer binds its driver observation and selected CAS edges to that
owner. Admission is a separately authorized source act: a cancelled job can
leave an admitted source orphan. Job adoption and publication remain subject to
the existing ControlJob lease; no cross-store atomic transaction is claimed.

The Foundry workflow accepts the exact `foundry.selected_basis` use with its
`any_active` mode. Its immutable transport carries the original receipt and
materialization, not permission or currentness. The identity-only execution
basis carries the selected source, and the consumer independently reopens and
replays the rows, actual binding rules and persisted state bytes. For the
restricted single-step Ex-Ante NumPy builtin, the existing method occurrence
records the actual selected callable, runner, bounded input-map reads, literal
parameter origin and output. Fresh Debug reads reverify the supported profile,
recompute its mean-change law, resolve the original source event, and query the
same C105 owner. Default and exact result selection share the no-store current-use
projection; unsupported or legacy calls remain unknown. Historical result bytes
are not rewritten. This is bounded internal custody only, not a claim about
external SQL currentness, completeness, rights, causal validity or calibration.

Same-event acquisitions use a fixed owner-local lock stripe around the original
event lookup, actual capture, and owner commit. Overlapping retries fail busy;
a later retry can recover an already committed occurrence without rereading SQL.
If a guarded store/owner operation times out while still running, the stripe is
retained until it completes. A never-completing operation can hold that stripe
and any colliding event until process exit, so eventual recovery is not assured.
A different command still conflicts under the existing event owner. The bounded
lock probe and proposed tests do not establish
production concurrency behavior.
This lock is coordination, not a new authority or ledger. A guard timeout can
leave an already-running action in flight; caller acknowledgement and recovery
semantics must be specified by the installed source service.
