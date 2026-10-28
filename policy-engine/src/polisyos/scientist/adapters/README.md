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
