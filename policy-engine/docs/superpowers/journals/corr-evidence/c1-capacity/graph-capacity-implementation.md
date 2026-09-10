# Graph staging implementation record

State: frozen-source native and importer verification passed after the complete
stored-provenance intake and owned-output disk corrections. Independent delta
review and resource profiling remain with the coordinator.
Synthetic fixtures and mechanical reducer controls are candidate-only evidence.
This record does not authorize extraction or a full corpus run.

## Owner interface

The existing `load_graph` and `run_edge_synthesize` owners accept
`capacity_limits` and `staging_dir`. `load_graph` also accepts
`source_provenance`; synthesis forwards its existing argument. The private
directory contains `graph-load.sqlite` and `edge-synthesize.sqlite` respectively.
`read_staging_usage(path)` reads actual SQLite counters and aggregate quantities
without writing, including the store's own synthetic/unknown provenance and
`candidate_only` authority. Its additive `applied_limits` reads the effective
constructor configuration, `namespace_operations` records actual writes and
yielded batches for every opened row/value/count/group/pair namespace, and
`storage_configuration` reads actual SQLite PRAGMA and DuckDB current settings.
Clearing a row family preserves its operation counts; unsuccessful group edits
do not increment committed writes. Empty opened families have explicit zeros.
These are run observations, not a static default-flipped assertion or evidence
that the run compared itself with the old resident owner. The orchestrator owns private-build identity,
replay from durable WorkRecords, and complete-only publication.

Every spool has one provenance intake before row emission. Explicit constructed
ancestry is monotone. An absent marker remains null, never false. Candidate
records carrying a producer publication flag remain raw candidates without an
admitted adjudication. Synthetic synthesis fixtures seed mechanical reducer
inputs separately; they establish no positive adjudication capability.

## Complete state reconciliation

The recomputable `graph_state_census.py` walks all assignment nodes in the three
mechanism `.py` files and reports their full path denominator, source hashes,
schema-literal and complete owned class-field fingerprints. It additionally
walks every expression node, including inline/returned mutable construction,
without treating an assigned variable as the only possible state. The final
census receipt `graph-complete-output-state-census.json` records 43/28/12 selected
assignments and 107/91/47 mutable
expressions respectively for `graph_builder.py`, `edge_synthesize.py` and
`_graph_staging.py` under the exact three `.py` path denominator printed by the
script. These syntax counts are not resident-map or memory measurements. Its
assignment census is only an index; the
following call/alias pass supplies the memory argument.

| Owner state | Treatment |
| --- | --- |
| Ordinary work, concept, estimate, raw claim, adjudication, claim, topic, selection, extraction, boundary and ingest-error rows | SQLite row families; each DuckDB write batch obeys actual encoded-byte and row-count limits. Retraction continues cannot accumulate an unflushed Python list. |
| SKG article, parameter, simulation numeric, evidence, context and moderation output rows | SQLite row families, including validated/projection output intermediates. Statistics remain scalar operation counts with existing duplicate behavior. |
| Legacy merged WorkRecords, topic catalog, ingest-error JSONL and optional numeric input | One shared bounded binary line reader refuses before JSON/WorkRecord construction; numeric rows indexed on disk by work with explicit per-work auxiliary and group limits. |
| Topic seen identities, variable mention/display maps | Disk scalar/value tables; original first-seen order retained. |
| Exact and moderation aggregates | Explicit editor scopes, including first-seen moderation `continue`; complete nested set/list/Counter values persisted only after a successful scope. Contribution reservation/count checks precede payload decode, and actual serialized payload bytes are checked before commit. |
| Record admission, provenance scan, claim lookup, extraction payload and fallback parameter projections | Temporary per-record state under the input record/auxiliary limits. Complete persisted-carrier preflight holds one bounded source row plus the fixed current table schema/codec projection. Signed adjudication materialization is a separately declared owner limitation below. |
| Exact quality/confidence, parameter validation, moderation representative projection | Existing formulas and value projections; complete logical aggregate bounded before finalization. No chunk averaging or local contested decisions. |
| Synthesis metadata, materialized resolutions, resolution cache, source basis, exact provenance, mention lookup maps | Disk keyed values populated by independent bounded query cursors. Adjudication source-basis precedence survives null/empty values; it is not replaced by COALESCE. |
| Direction groups and whole family pairs | Disk editors. Pair admission counts all directional samples before merging; family-edge IDs are committed through a zero-contribution editor. Whole-pair references and noisy-OR/dissent ordering remain intact. |
| Family/contested output and pending canonical results | Disk row families; payload dataclasses use explicit registered data codecs, without dynamic imports or pickle. |
| Review queue, deduplication and global order | Disk queue/seen/mention state; SQLite sorts by the existing total-mentions/canonical/raw order. Existing pending-result multiplicity is preserved. |
| Canonization summary | Streamed scalar scan. |
| CanonicalVariableResolver | Full approved cache/synonym and built-in/runtime vocabulary input preflight before the existing constructor; finite vocabulary-byte/entry budgets bound its similarity structures. Unknown-name Counter is replaced by scalar disk counts. Approval rules and the narrower family-name vocabulary stay with their existing owners. |
| Storage codec, cursor batches, namespace usage and path bookkeeping | At most one bounded input/group plus one bounded row batch; fixed codec registrations, literal owner namespace counters and declared database/WAL/temp/output paths. Output UTF-8 writes are record-bounded and prospectively budgeted; directory file enumeration streams. SQLite cache and DuckDB memory/temp settings are explicit operational settings, not RSS evidence. |

Disk consumption is checked at the common staging write and DuckDB batch-flush
seams, including the owned main DB/WAL and spill directory. The same
`enforce_owned_output_budget` now measures all declared detached outputs, with
nested path deduplication independent of argument order. SQLite additionally has
a page limit. Engine growth may consume one bounded operation before measured
refusal; UTF-8 queue/report chunks are checked before growth. The unchanged
kernel manifest writer runs through `publish_owned_output`: private actual
serialization, complete owned-byte check, then the existing atomic publication
owner. A failed private artifact remains available for diagnosis and never
reaches the completion path. These are logical file-byte operational budgets,
not filesystem block accounting, evidence truncation or corpus-count limits.

The complete three-file AST output-call index in the census includes the
following call/alias reconciliation. SQLite `write` calls feed the tracked
staging root; DuckDB owns its explicitly tracked DB, WAL and configured spill
root. Synthesis queue JSONL and report JSON use `text_output`; its empty and
nonempty stage branches use the common private publisher. Legacy `run_graph_load`
also publishes its manifest through that owner. Direct configurations register
these exact output files, never `snapshot_root`, which may hold read-only input
or unrelated history. The pre-existing `run_graph_index` route and its manifest
remain unchanged and are outside the C1 finalizer's output set. The parent
finalizer uses its unique private build root plus published candidate manifest
as the complete budget boundary, through the same publisher and reader check.

## Characterization and falsifiers

`graph-owner-red.json` records both existing owner APIs refusing the absent
capacity interface. `graph-owner-baseline-final.json` records the pre-change
owner's complete 30-table output on the marked fixture, including two family
edges and one contested edge. The test compares the complete table-name set,
column descriptions and all data values via those per-table digests, as well as
direct equality across batch sizes. Volatile timestamps are treated separately
only when their schema declares CURRENT_TIMESTAMP (or the run owner explicitly
sets a run clock); their types and range are checked. No recommendation or
evidence value is normalized away.

Earlier baseline attempts are retained: one exposed an incomplete timestamp
fixture assertion, and another deliberately unapproved source name correctly
produced no family edges. The final mechanical fixture uses actual existing
seed names; it does not broaden canonical approval to obtain a positive.

The storage suite exercises nested commit/reopen/rollback, actual SIGKILL,
group/pair counts, pre-scope byte refusal, row-byte/count bounds, input/auxiliary
limits, own provenance, reset and disk refusal. `graph-staging-nested-removal.json`
removes the actual commit operation and fails on the missing persisted nested
state. Final frozen-source verification is recorded in
`graph-complete-owner-final-wave.json`: 30 targeted graph/helper controls passed
in 16.701 seconds. The importer delta in
`graph-complete-owner-importer-wave.json` passed 25 existing graph, confidence, genuine
adjudication consumer, moderation, dedicated numeric-input and parameter-origin
controls in 22.287 seconds. The exact commands and complete outputs are retained.
`graph-complete-final-ruff.json` passed on the three mechanism files, two
mirrored tests and three evidence scripts.

The initial final waves retained dots/counts only. The required identity replay
uses the same unittest invocation with `-v` in
`graph-complete-owner-verbose-wave.json` (30 passing cases, 16.352 seconds), and
the same importer pytest invocation plus JUnit in
`graph-complete-importer-junit-wave.json` (25 passing cases, 23.070 seconds).
`graph-complete-owner-identities.json` independently reconciles the complete
TestLoader set against every actual verbose execution identity;
`graph-complete-importer-identities.json` uses the existing shared pytest
collector against actual JUnit. Both report equal identity hashes and no
missing, unexpected, duplicate or nonpassing executions. The complete commands
define their exact mirrored `.py` path denominators. The additional unittest
identity helper passes `graph-identity-helper-ruff-final.json`.

The current in-memory removal harness keeps source bytes, configuration and
schema markers intact. Its five receipts
`graph-{nested_commit,group_capacity,pair_capacity,cross_direction,namespace_usage}-removal.json`
each fail the property gate: committed nested references vanish; an oversized
group enters the editor; an over-budget whole pair stops refusing; resetting a
pair between directions loses the contested edge (two family edges, zero
contested instead of one); and deleting observation leaves actual namespace
counters zero. Additional `graph-source-provenance-removal.json`,
`graph-pair_bytes-removal.json`, `graph-resolver_limits-removal.json` and
`graph-output-disk-removal.json` remove the sole stored-ancestry intake,
whole-pair byte reservation, each finite resolver limit and complete output
budget respectively; each gate then fails on the real missing behavior. The
last removal permits the 96 KiB review-queue value to cross the remaining 64 KiB
disk budget and reach completion. The native full-table comparison also checks the unchanged
pre-change 30-table identity/schema/value digests. Earlier failed attempts remain
failed; they are not relabeled green.

Standalone synthesis queue rows, report and stage manifest now share one output
ancestry projection. A nonempty queue control verifies each row's own marker;
an empty queue carries no row claim and its empty bytes are bound by the parent
manifest. The legacy graph-load manifest reads the actual staging ancestry.
The finalizer supplies complete input provenance. The second same-class intake
finding widened the sole synthesis preflight to complete owner-stored
provenance before any lossy projection or derived emission. The deciding test
walks the complete SELECT reader families in `edge_synthesize.py` and
`canonical_resolver.py`, reconciles the actual graph/SKG writers and live schema,
and emits the source hashes and codec contract in the final wave receipt.

Its 13 source-table denominator contains five persisted carriers in three
families: `ac_causal_claims_raw.synthetic` is boolean;
`ac_causal_claims_raw.source_provenance_json`,
`ac_skg_articles.extraction_json`, `ac_skg_articles.context_json` and
`ac_skg_edges.quality_signals_json` are actual writer-defined JSON containers.
Each carrier is independently exercised with a true ancestor and a false caller
through family/contested edges, queue, report, stage manifest and staging
metadata. Separate raw-only controls exercise both missing and false callers.
The common intake uses that explicit codec
contract; a `_json` suffix is never a provenance warrant. Absent columns, null
cells, and absent source families remain distinct compact observations;
malformed containers or nonboolean present markers refuse before derived writes.

The ten remaining reader families have no persisted own-ancestry carrier:
`ac_works`, `ac_parameter_estimates`, `ac_claim_adjudications`,
`ac_skg_variables`, `ac_skg_edge_evidence`, `ac_skg_context_attributes`,
`ac_skg_moderation_edges`, `ac_skg_versions`, `ac_skg_canonization_cache` and
`ac_skg_variable_synonyms`. Their scope/identity arrays and plain text are not
invented ancestry. Without supplied provenance or a true persisted ancestor,
the store and derived outputs stay candidate-only unknown. Closing historical
absence or an unrecognized future reader family requires an owner-persisted
provenance carrier and codec contract, which those families do not currently
provide. Null-only and absent-caller tests exercise this bounded residual;
historical absence cannot establish false. The runtime stores compact status
and counts, not a copied derived schema inventory.

`graph-queue-disk-red.json` records the direct synthesis escape before the shared
output correction. `graph-complete-output-disk-green.json` then passes the small
actual queue, refuses the larger actual queue, checks exact UTF-8 pre-growth and
deduplicated roots, and refuses oversized private publication. The earlier
128 KiB cache fixture encountered DuckDB's index-key limit before synthesis;
that harness attempt is retained separately and is not the disk red.

## Pattern pass and bounded claims

P27/P28: existing owners now route through disk staging by default; actual usage
is read from SQLite. P29/P37/P38: gates exercise persistence, actual aggregate
and disk quantities, complete output equality and refusal. P31/P35: the census
and call pass include ordinary rows, hidden SKG rows, aliases and resolver state.
P40: the provenance-container finding is the same class as the upstream artifact
provenance finding and is closed at the complete stored-carrier intake, with the
explicit no-carrier residual above. The detached-output disk finding is the
same operational-budget class one level deeper; the common owner now measures
the complete declared output boundary and gates publication on actual bytes.

`VerifiedClaimAdjudicationRows` can materialize a complete signed batch. That
unchanged owner is outside the candidate-only C1 memory claim; unrestricted
signed-batch memory remains `verification_missing`. This work neither constructs
positive receipts nor changes adjudication admission, table/schema epochs,
normalization or evidence-class semantics. Native RSS under increasing corpus
cardinality and independent final review remain `verification_missing` until
measured; publication belongs to the separate orchestration owner.
