# C1 graph capacity decision

Date: 2026-09-09. State: architecture agreed; implementation awaits the
coordinator's explicit campaign-freeze release. This document records a proposed
mechanism, not a completed capacity measurement.

## Decision and boundary

Extend the existing academic graph owners with disk-backed staging and finite
operational limits. Preserve their table schemas, schema epochs, aggregation
formulas, authority admission, synthetic ancestry and output projections. Rebuild
a private graph from the campaign's durable WorkRecord outputs after interruption;
publish only a completely finalized graph. The campaign remains the checkpoint
owner. The graph staging database is disposable build state, not another source
of extraction completion or authority.

The target property is bounded working memory as corpus identity count grows,
subject to explicit limits on one input record, one aggregate group, canonical
resolution state, and disk consumption. An oversized group must refuse visibly
before its full arrays are materialized. It must not drop contributions, emit a
partial completed graph, or weaken an existing semantic gate.

This does not authorize a full extraction pass. A/B/C2 remain closed. No graph
table/schema epoch change, receipt construction, adjudication bypass, provider
call, or credential access belongs to this graph subtask.

## Measured source seams

The following are source observations, not runtime capacity measurements.

- `graph_builder.load_graph` accepts an Iterable but calls `_truncate` on every
  invocation. Ordinary rows flush at the work-batch threshold; SKG article,
  parameter, evidence and context lists, variable maps, and exact/moderation
  accumulators remain resident until finalization. Repeated chunk invocations
  therefore erase preceding chunks.
- `_materialize_skg` creates complete variable, validated parameter, exact-edge,
  numeric and moderation row collections. `_edge_quality_summary` and the
  existing SKG confidence functions consume each complete logical aggregate.
- `edge_synthesize.run_edge_synthesize` builds complete metadata and resolution
  maps, evidence rows, directional groups, whole-pair groups, family rows,
  contested rows and a sorted review queue in Python.
- Exact/family/contested projections embed complete reference arrays. A single
  high-fan-in aggregate can grow with the corpus even after global maps move to
  disk. A whole-family-pair limit is necessary in addition to an exact-edge or
  directional-group limit.
- `VerifiedClaimAdjudicationRows._read` reconstructs a complete admitted result
  batch on authority reads; `for_current_subject` also decodes the complete raw
  input batch. Candidate-only C1 runs do not supply admitted adjudications. This
  closed authority mechanism must remain unchanged; no bounded-memory claim for
  arbitrarily large signed adjudication batches follows from this C1 work.

## Owners and interfaces

Mechanism files are the existing `batch/graph_builder.py` and
`batch/edge_synthesize.py`, plus a private `batch/_graph_staging.py` helper owned
by the same academic batch package. The helper owns storage mechanics, not graph
semantics. Mirrored graph staging/capacity tests and this decision are required
companions, outside the mechanism file inventory.

Proposed internal interfaces:

```python
rows.append(row)
rows.iter_batches(batch_size)
rows.count()

with groups.edit(key, default_factory, contribution_delta=1) as payload:
    # Existing graph-owner mutations, persisted on successful scope exit.
    ...
groups.iter_items(order="first_seen")

seen.add(value)
seen.contains(value)
counts.increment(key, amount=1)
counts.iter_items()
```

The group editor must commit nested list/set/Counter mutations explicitly and
roll back on exceptions. It must not masquerade as a MutableMapping whose
`get()` returns a detached mutable object. Store a first-seen ordinal and
contribution count beside each payload; check the next contribution against the
limit before decoding or extending the aggregate. Use an explicit data codec,
not executable pickle input. Preserve missing/null values and existing counter
insertion order.

Resource controls cover input-record bytes, per-work auxiliary rows, aggregate
contribution count, aggregate serialized bytes, canonical-resolution state,
row-batch bytes/count, spool cache and disk consumption. Values must be explicit
in the capacity run. SQLite cache/spill settings and DuckDB memory settings are
operational settings; actual RSS still requires process measurement. A typed
capacity exception identifies the limit, aggregate/input identity and observed
quantity. The campaign retains durable work outputs and records unsuccessful
graph finalization through its existing failure handling.

## Complete mutable-state treatment

In `graph_builder`, ordinary work/concept/estimate/raw-claim/adjudication/claim,
topic/selection/extraction/boundary/error rows and SKG article/parameter/numeric/
evidence/context rows become disk row spools or bounded write batches. Topic
catalog loading and ingest-error loading must use that same discipline.
`topic_seen`, variable mention counts and variable display names move to disk.
The optional simulation-numeric file becomes a work-indexed disk spool, with a
per-work capacity check.

Exact and moderation accumulation use explicit editor scopes. The moderation
first-occurrence branch must persist before its `continue`. Existing record
projection and admission bodies are reused. Finalization removes the
`dict(variable_mentions)` materialization and complete moderation list
comprehension, iterates staged items in original order, and flushes every
generated output row family in bounded batches. Statistics accumulate as
scalars or SQL counts.

In `edge_synthesize`, stream evidence rows and obtain metadata through bounded
lookups/SQL joins. Preserve adjudication-row precedence for source basis even
when that row's value is null or empty; a generic COALESCE over adjudication and
raw values would change current behavior. Resolve names through the existing
CanonicalVariableResolver, with finite capacity around its vocabulary and
unknown-name state. Do not replace its approval rules or silently broaden the
family-name vocabulary.

Directional groups and whole-pair groups live on disk. Check pair capacity
before `extend`/set union; a bounded directional group alone is insufficient.
Family and contested output rows are spooled or flushed in bounded batches.
Review deduplication and mention lookups use disk state, while SQL performs the
existing global sort. Canonization summary becomes a bounded scan or equivalent
SQL scalar aggregation. Existing confidence, dissent, synthetic and output-row
projection functions remain the semantic owners.

## Finalization and compatibility

Global reconciliation occurs only after complete ingestion. Preserve distinct
work/claim references, cross-direction conflict, replication count, strength
floors, noisy-OR order, strongest-dissent selection, moderation first-seen ties,
and review-queue ordering. Never average chunk confidences or finalize contested
status independently within chunks.

Build in a private owned directory and database. An interrupted build is not a
completed artifact; restart derives a new build from the durable input ledger.
Only publish the graph reference after graph load and edge synthesis both
complete. This avoids cross-database checkpoint atomicity claims. A finished
graph keeps its existing schema and projection format. Previous declarations
and frozen provider runs remain immutable.

## Falsifiers and implementation order

1. Before repair, demonstrate the absent bounded staging/capacity behavior with
   a focused test that fails for the intended reason. Then implement the disk
   helper. Kill/reopen and nested-mutation tests must prove that persisted
   accumulator contents survive, while exceptions do not commit half an edit.
2. Integrate graph load. Compare complete identities and projected values with
   characterized owner output, crossing batch boundaries with duplicates,
   moderation ties, auxiliary rows and synthetic/missing ancestry. Remove the
   nested-mutation commit while keeping markers: the gate must fail.
3. Integrate synthesis. Place opposing directions across ingestion batches and
   compare exact/family/contested records and globally sorted review outputs.
   Remove cross-batch reconciliation: contested parity must fail while the
   ordinary happy path remains valid.
4. Exercise capacity at and beyond each active boundary. At-limit input remains
   valid; the next contribution causes an explicit operational refusal with no
   completed graph. Remove the capacity check while retaining its declaration:
   the refusal test must fail. An operational limit never changes the canonical
   evidence denominator.
5. Kill finalization and restart through the campaign's durable WorkRecords.
   The rebuilt graph must match uninterrupted identity sets and values, without
   new provider calls or duplicate contributions. Partial publication must be
   absent. Measure process RSS for increasing corpus cardinality under fixed
   declared limits, and separately exercise the high-fan-in refusal boundary.
6. Freeze source, perform independent review, then run only targeted graph,
   synthesis, confidence and C1 importer tests, ruff and required guardrails.
   Retain complete deciding/removal-probe outputs; cite tracked source by SHA
   instead of copying it into evidence. All unrun properties remain
   `not_established`.

## Pattern pass and routed limitations

P27: retain one graph projection owner. P28: subordinate the resident collection
implementation through the existing entry points; record the default transition
before claiming migration. P29/P37/P38: exercise nested persistence, resource
limits, complete-set reconciliation and publication, rather than testing marker
presence or merely observing an Iterable signature. P31/P35: cover every named
mutable row/aggregate family, and reconcile complete output identity sets.
P40: a second memory escape in the same class widens the capacity quantity or
becomes an explicit tested operational limitation, not another cosmetic patch.

The signed adjudication batch's materialization belongs to its existing
adjudication owner and is outside this candidate-only C1 readiness claim. The
resolver vocabulary and a logical output row receive explicit capacity limits.
No unlimited-data or full-pass completion claim is established by this decision.
