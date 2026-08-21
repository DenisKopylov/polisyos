# GY-GAP4 — producer-signed run terminality

Date: 2026-08-16
Branch: `codex/gy-gap4-run-terminality`
Pinned base: `c1a89b6cf0c63573abad6b0ca8374e16b78c47dd`
Reviewed implementation head: `1b096b222768cab2841dff488a10bc50428951a0`
Implementation commits: `ec7228eff64cf2d3ec5c66048c81b897da78a75c`,
`1775cf8a5d07a7d2e92278040bcfd59bc7311e7c`,
`09f9e16dc1759f47c86ba02cdf0f81eb35e04961`,
`03e8fa83d6f4b30b67dfa327dfa79be74c630e55`,
`1b096b222768cab2841dff488a10bc50428951a0`

## Receipt and standing

The isolated worktree opened attached to the requested branch at the exact pinned base with an empty
tracked and staged diff. The complete pinned-tree census covered 9,734 tracked paths: 9,713 NUL-free
text blobs and 21 NUL-bearing binary blobs. It found zero files, lines, or occurrences for either
`GY-GAP4` or `registered_not_scheduled`. The GY plan at that base was Rev 35 and contained only
GY-GAP1–GY-GAP3. The task commission said Rev 39 and supplied the missing GY-GAP4 registration,
including its ten-day Atlas-only interval after the 2026-08-01 reassignment. Measurement therefore
wins: this change reconstructs and advances the commission-supplied row to
`producer_input_landed` as the repository's next measured Rev 36; it does not fabricate absent
Rev 36–39 plan bytes or claim the downstream DS5/DS7 capability is closed.

Standing at the reviewed implementation head:

- producer/event/local-artifact/adapter/run-index/REST/OpenAPI chain: `implemented`;
- governed runs list/detail SSE consumer: `implemented` and versioned v2;
- package and dashboard generated clients: `bridge_missing`, explicitly handed to DS5/Atlas;
- DS7 dashboard consumption: `consumer_missing`;
- CAS `trace_ref` terminal event and recovery audit-chain fanout: `artifact_missing` on those two
  persistence projections, while the fsynced local trace consumed by HTTP is implemented.

No §4 stop fired. The representation did not change the open status vocabulary, required no second
lifecycle owner, and the registered exporter changed only the declared RunSummary/list example and
runs-channel registry example cut.

## Pattern pass

Relevant register rows were read before design and again before closeout.

- `P04`/`P05`: absent lifecycle knowledge is represented by `not_established`, never collapsed into
  non-terminal; only the lifecycle owner writes facts.
- `P07`: the changed schema-hidden runs channel and both snapshot schemas moved to v2 rather than
  mutating the v1 boolean contract in place.
- `P10`/`P29`/`P33`: witnesses execute the real producer, trace, adapter, REST, and SSE paths; they
  include novel status in both directions, malformed enum, invalid pair, non-owner phase, foreign
  identity, missing fact/ref/provenance, terminal regression, cache recovery, durability failure,
  and recovery-binding variants.
- `P32`: a terminal event is authority-bearing only after its exact manifest ref, CAS integrity,
  sidecar schema/provenance/lineage, payload identity, and tenant/cell scope all bind.
- `P27`/`P31`: the HTTP SSE status-substring parser was removed instead of adding a second fact; the
  remaining audit/canary siblings are named below.
- `P35`: zeroes and counts use complete tracked sets with denominators, not sampled search output.
- `P37`: fact admission is recomputed from the exact owner phase/event/value/identity sequence and
  recovery manifest binding; status, timestamps, and event-name presence are not admitted premises.

## Producer and contract

`RunTerminality` is the closed string enum:

- `terminal`
- `non_terminal`
- `not_established`

`TraceRecord.run_terminality` is optional so historical and non-lifecycle trace events remain
readable. `RunContext.start` emits `core/RUN_STARTED/non_terminal`; normal finalize and validated
recovery emit `core/RUN_FINALIZED/terminal`. Public `RunContext.emit` cannot set the fact.

The adapter establishes the run identity from a complete singleton set of valid core
`RUN_STARTED` owner records over `(run_id, tenant_id, cell_id)`. Recovery refuses and retains its
journal when that identity is absent, ambiguous, malformed, or different from the pending manifest.
A pre-existing terminal record suppresses recovery append only when it is the exact core terminal
pair for the same full owner identity and carries the exact recovered `core.run_manifest`
`ArtifactRef`, including media type, as the only run-manifest output. Recovery records the recovered
manifest's artifact owner. Non-object, unreadable, missing-version, and unsupported-version finalize
journal envelopes are refused without clearing the journal or aborting run-index refresh.
Run-directory aliases remain supported; the directory basename is not treated as authority.

The fold admits only exact owner pairs. A terminal candidate additionally needs one exact manifest
ref whose CAS bytes and sidecar verify, whose sidecar names the canonical run-manifest schema and
binds producer/environment/registry lineage, and whose payload binds the full owner identity.
Missing, unresolvable, self-described, scope-substituted, or conflicting evidence latches
`not_established`. A factless legacy final invalidates a prior non-terminal state without being
interpreted as terminal; a later owner recovery terminal may establish terminality. The fold never
reads `status`, `finished_at`, or any substring.

The run-index fingerprint includes both trace and finalize-journal state, so a journal-only crash
invalidates a cached active record and invokes recovery. In audit-chain mode the canonical local
JSONL sink is fail-hard, optional audit fanout remains best-effort, and the finalize journal is
cleared only after the required local terminal event is durably emitted.
Ordinary failures from optional audit emit or close are isolated after that canonical receipt.

`RunSummary.run_terminality` is required. This is the type-level witness: a consumer deserializing a
summary cannot turn unknown into a default `false`. `RunDetails` was deliberately not widened;
doing so would broaden GET-detail/batch contracts and conflict with temporal projections that replay
a completed run before its finish time.

## Behavioral witnesses

The mirrored HTTP/core tests prove:

1. a live `RunContext.start` projects `non_terminal` through GET `/api/v1/runs`;
2. finalizing with the novel label `still_running_but_owner_finalized_v47` preserves that opaque
   status and independently projects `terminal`;
3. a completed, timestamped legacy manifest with no producer fact projects required
   `not_established`, and `not_established != non_terminal`;
4. malformed enum values, invalid event/value pairs, non-owner phases, foreign run events, missing
   or unresolvable refs, wrong media types, missing producer sidecar provenance, scope substitution,
   a factless final, and terminal regression fail closed;
5. foreign, ownerless, ambiguous, scope-substituted, or ref-unbound recovery evidence cannot sign or
   suppress the current run's recovery event;
6. malformed/version-unknown journal envelopes remain retained, and a journal-only crash with a
   valid envelope invalidates a cached active record and recovers terminality;
7. a failed required local terminal-event write propagates and retains the finalize journal even
   when optional audit fanout is enabled, while optional audit emit/close failures do not revoke a
   persisted finalization;
8. detail SSE exits on the producer fact even when status says “running”, while completed-looking
   status with either `non_terminal` or `not_established` remains open.

The terminal-regression witness was mutation-checked: with the absorbing-terminal branch removed it
failed as `non_terminal != not_established` in 14.41s; restored code passed in 12.37s.
The schema-provenance witness was independently isolated before closeout: it starts from the
canonical manifest write options and removes only `schema`, preserving media type, producer,
environment, and registry lineage. With only the adapter's schema rejection disabled, the case
failed because `terminal` leaked through; restored code projected `not_established`. Independent
delta review returned GO on that final witness.

## Generated OpenAPI receipt

The snapshot was changed only by the registered exporter:

```text
PYTHONPATH=src:. uv run --extra runtime --extra ml python \
  tools/ops_runners/runtime/export_runtime_openapi.py \
  --output schemas/runtime_api_v1.openapi.json
```

The tracked snapshot diff is 18 inserted and 3 removed lines, limited to:

- required `RunSummary.run_terminality` referencing a new `RunTerminality` component;
- enum values exactly `terminal`, `non_terminal`, `not_established`;
- the list-runs success example's `run_terminality: terminal`;
- two governed runs-channel registry example values moving v1 → v2.

There are no changed path references, no `RunDetails`, batch, or unrelated component changes. The
snapshot-only freshness gate passed:

```text
PYTHONPATH=src:. uv run --extra runtime --extra ml python \
  tools/ops_runners/runtime/check_runtime_api_contract.py \
  --skip-client-drift
```

`--skip-client-drift` is intentional, not a green client receipt.

## SSE closure and downstream handoff

The prior `_is_terminal_status` owner is gone. Runs list and detail snapshots require the three-state
field; detail streaming exits only on `terminal`. This closes the in-fence P27 sibling.

DS5/Atlas must regenerate, outside this fence:

```text
corepack pnpm --dir packages/runtime-api-client run generate
corepack pnpm --filter @polisyos/runtime-dashboard run generate:api
```

The package command updates `types.ts`, `runtimeApiClient.{ts,js}`, and
`canonicalRuntimeApiClient.{ts,js}`. The generated-artifact registry names only the raw client pair,
so that package-output registration asymmetry is a handoff finding. The second command updates
`apps/runtime-dashboard/src/api/types.ts`.

DS7 may then consume only generated `run_terminality`. Its negative control must reject status
substrings, `finished_at`, event-name presence, and every other proxy. At the pinned base the live
dashboard machine still declares `terminal?: boolean`; `RunsLiveProvider` uses that boolean as one
list-invalidation trigger, while `useRunLiveUpdates` ignores terminality. DS7 therefore owns enum
parsing/propagation plus the invalidation/polling behavior; those fenced consumer bytes were not
changed here.

Because the required field changes the committed v1 wire shape, the runtime API release owner must
make an explicit compatibility/version ruling and issue the repository's structured release
handoff before integration. This lane preserves the required field (the unknown-is-not-false
witness) but is not claiming merge/release readiness while that ruling and generated outputs are
outstanding.

## Duplication census and disposition

Implementation-head denominators: 9,734 tracked files / 5,560 Python; `src` 2,770 / 2,560 Python;
runtime HTTP 92 / 87 Python; mirrored HTTP tests 61 / 59 Python. The complete production search has
exactly three direct fact writes, all in `RunContext` (start, normal finalize, recovery), and zero
`_is_terminal_status` occurrences under runtime HTTP.

| Site / owner | Complete evidence | Classification | Disposition / smallest closure | Standing |
|---|---|---|---|---|
| `core/run/context.py` | 3/3 production `run_terminality=RunTerminality.*` writes | canonical producer | retain sole owner | `implemented` |
| HTTP adapter + run index | every fact is owner/scope/ref/content-bound; trace+journal cache key | canonical bridge/consumer | no proxy inference | `implemented` |
| runs list/detail SSE | prior parser removed; both consume the same fact | closed P27 sibling | v2 typed field | `implemented` |
| `core/audit/_assembler_core.py:171,192` | one status+`finished_at` completeness gate and one RUN_FINALIZED-presence path | live P27 sibling outside cut | first persist the fact into the consumed trace projection, then fail closed on unknown/conflict | `bridge_missing` |
| `tools/ops_runners/runtime/local_production_canary.py:2216` | one RUN_FINALIZED-presence completion inference | live P27 sibling outside cut | validate/consume the producer fact | `consumer_missing` |
| `runtime/api.py:start_run/finalize_run` | two definitions; complete src/tests/tools search finds no `finalize_run` caller and only legacy manifest-test start calls | dormant parallel owner / P28 | strangle or delegate before reuse | `implemented_but_not_orchestrated` |
| `runtime/quality/workspace/loop.py:940` and `scientist/methods/backtesting/composition_bridge.py:128` | two of four production `RunContext.start` sites; no module-local finalize | lifecycle-closure debt, not permission to infer | wire owner finalize or record deliberate transfer | `bridge_missing` |
| temporal status/timestamp uses | lexical matches only | false positives | no terminality field was added to temporal RunDetails | out of this capability |

The implementation-head complete search found 9 `RUN_FINALIZED` occurrences across 4 tracked
production files in `src/polisyos` plus `tools/ops_runners/runtime`; only the core owner emits the
fact. The audit and canary rows above are the remaining consumer re-derivations, not producer
authority.

## Verification and load receipts

Heavy lanes were serialized. Times are `/usr/bin/time -p` real seconds; load is 1/5/15-minute
average at command boundaries.

| Command / receipt | Result | Wall | Load start → end |
|---|---:|---:|---|
| base OpenAPI freshness, before edits | pass | 156.52s | 3.85/3.81/2.89 (start; cold receipt) |
| first focused run/API wave | 3 failures; one task test fixed, two base-reproduced control failures retained below | 21.49s | 1.88/2.30/2.62 → 2.47/2.41/2.65 |
| core recovery/importer wave exposing alias invariant | 1 task failure, then fixed | 38.97s | 4.77/4.17/3.40 → 5.74/4.48/3.55 |
| post-review semantic wave | 18 passed | 26.94s | 4.39/4.81/3.91 → 4.44/4.79/3.93 |
| terminal regression mutation RED | expected fail | 14.41s | 2.06/2.69/3.15 → 2.27/2.70/3.14 |
| terminal regression GREEN | pass | 12.37s | 2.25/2.69/3.14 → 2.12/2.64/3.11 |
| registered OpenAPI exporter | pass | 16.66s | 2.02/2.59/3.08 → 3.37/2.84/3.16 |
| snapshot-only OpenAPI freshness | pass | 17.70s | 5.47/3.36/3.35 → 5.16/3.39/3.36 |
| focused closeout: core recovery/audit + HTTP/SSE/strangle | 22 passed | 22.29s | 4.35/3.32/3.33 → 3.95/3.30/3.32 |
| exact changed-file ruff + diff check | pass | 0.13s | 3.96/3.31/3.33 → unchanged |
| post-adapter delta semantic wave | 17 passed | 20.64s | 6.49/4.44/3.79 → 5.91/4.45/3.80 |
| review-blocker adversarial RED (inverse SSE already green) | expected 2 pass / 7 fail | 32.25s | 5.94/4.81/4.40 → 7.06/5.22/4.56 |
| authority/recovery/durability/cache adversarial GREEN | 9 passed | 32.50s | 6.29/5.85/5.06 → 7.04/6.10/5.18 |
| first widened post-fix wave | 42 pass / 3 fail; legacy scope + diagnostic ordering fixed | 33.14s | 5.31/5.93/5.23 → 4.49/5.66/5.16 |
| widened post-fix wave: runs API, core recovery/audit, cache | 45 passed | 32.47s | 3.28/5.04/4.96 → 3.79/4.95/4.93 |
| authority-fix changed-file ruff + diff check | pass | 0.07s | 3.73/4.92/4.92 → unchanged |
| second-review adversarial RED | expected 8 pass / 5 fail | 28.62s | 4.42/3.91/4.21 → 4.41/3.97/4.22 |
| second-review focused GREEN | 13 passed | 64.00s | not sampled; closeout rerun supersedes this receipt |
| second-review widened lifecycle/cache/audit wave | 54 passed | 51.10s | 11.57/6.43/5.13 → 9.37/6.59/5.26 |
| architecture guardrail before package adapter | expected exit 1 plus 3 attributable trace-facade edges | 40.28s | 3.79/3.36/3.34 → 4.82/3.69/3.46 |
| architecture guardrail after package adapter | expected exit 1, attributable added-edge intersection 0 | 46.93s | 3.00/3.48/3.42 → 5.72/4.11/3.65 |
| exact two-test archive isolation at `c1a89b6cf` | both control failures reproduced | 19.19s | 5.35/4.45/3.93 at start; fail-fast exit before end sample |
| isolated schema witness before mutation | pass | 14.30s | 3.17/4.62/4.72 → 3.13/4.54/4.69 |
| schema-guard mutation RED | expected fail: `terminal` leaked | 14.01s | 2.96/4.43/4.64 → 3.04/4.38/4.62 |
| restored schema witness GREEN | pass | 24.00s | 3.10/4.35/4.61 → 4.12/4.51/4.66 |
| final registered exporter; output hash unchanged `623c788c9b…` | pass | 24.30s | 3.91/4.43/4.63 → 4.23/4.46/4.63 |
| final snapshot-only OpenAPI freshness | pass | 20.71s | 4.13/4.44/4.62 → 4.31/4.46/4.62 |
| final changed-path/importer behavioral wave | 60 passed | 68.78s | 4.26/4.44/4.61 → 5.14/4.62/4.67 |
| final exact changed-Python ruff + base/working diff checks | pass | 0.40s | not sampled; non-heavy lane |
| final architecture guardrail | expected exit 1; no branch-added flagged edge | 55.21s | 5.05/4.62/4.67 → 6.69/5.12/4.84 |

The final guardrail output retains five baseline-creep edges in three files:
`channel_contracts.py` (2), untouched `control/lex_pipeline.py` (1), and untouched
`control/lex_search_projection.py` (2). Raw changed-path intersection is one file because
`channel_contracts.py` is the governed SSE contract touched here. Both reported imports in that file
(`core.artifacts.manifest` and `core.contracts.decision_validity`) are byte-present at the pinned
base and unchanged by GY-GAP4. The set of guardrail-reported import edges added by
`c1a89b6cf..1b096b222` is therefore empty. The same output shows this branch removing two old
deep imports from `routes/runs.py`. The deep-import baseline was not synced.

## Non-receipts and exclusions

- Pinned GY plan bytes for Rev 36–39, an existing GY-GAP4 row, and the literal
  `registered_not_scheduled` were not received. The commission is the registration source.
- The unrelated in-flight `src/polisyos/data_forge/read_api/catalog.py` edit was never admitted:
  `src/polisyos/data_forge/**` intersection is zero in status, diff, staging, and all implementation
  commits.
- `packages/runtime-api-client/**`, `apps/**`, `src/polisyos/pdc/**`,
  `src/polisyos/runtime/quality/**`, and `architecture/policy_design_case/**` were not changed.
- Client/dashboard generation and client-drift verification were deliberately not run; DS5/Atlas
  own them. The Atlas owner register also remains unchanged due the fence.
- DS7 consumption is not verified in this lane; it remains `consumer_missing`.
- `RunContext.finalize` snapshots the CAS `trace_ref` before emitting RUN_FINALIZED. Thus normal and
  recovered terminal facts exist in the fsynced local HTTP trace but not in that CAS trace snapshot;
  recovery also does not fan out through the chained audit sink. Smallest later closure is a
  non-cyclic terminal receipt/post-final trace segment, never status inference.
- `non_terminal` is established at owner start but carries no freshness lease. A producer that
  disappears before beginning finalize remains non-terminal rather than becoming lifecycle-unknown;
  this is deferred lifecycle-reconciliation/P08 debt, not permission for a consumer to infer from
  process liveness or status.
- Two whole-file `test_runs_api.py` control tests are pinned-base failures outside this cut. A
  fail-fast `git archive c1a89b6cf` isolation reproduced both in 19.19s:
  `test_evaluate_feedback_endpoint_persists_monitoring_report` returned 400 rather than 200 because
  `DecisionMonitoringContract` rejected pre-existing authority fields, and
  `test_reissue_endpoint_fails_closed_without_durable_control_plane` returned 400 rather than 422.
  Their control/monitoring owners and schemas are outside every changed production path. Focused
  run-lifecycle tests are green. Full backend verify was not run because its canonical sequence
  invokes the unskipped generated-client drift gate that this fence deliberately hands to DS5 and
  would therefore stop before its backend pytest lane; CI parity was also not run under the
  blast-radius/fenced-client rule.
- The worktree `.venv` initially lacked ruff. Offline provisioning failed in 0.22s because the cache
  lacked `nodejs-wheel-binaries==24.14.1`; verification used the existing repository venv executable
  with `PYTHONPATH` bound to this worktree. The cold base freshness receipt created only ignored
  worktree `.venv` bytes.
- All five implementation commits and the governance commit reported no lefthook configuration in
  the worktree root. This is a hook-tooling non-receipt, not a product gate.
- The independent review returned a no-blocker interim verdict after its requested delta review;
  its final status message was not received because the reviewer workspace exhausted credits.
- A final documentation-only governance re-read was dispatched after all source reviews; that
  reviewer workspace was also out of credits before it could inspect the files, so it returned no
  review receipt and changed no bytes. Closeout relies on the completed source/delta reviews plus
  direct plan, journal, fence, and branch readback.
- A later independent full delta review returned NO-GO with terminal content binding, recovery
  scope/ref binding, journal-cache invalidation, mandatory local durability, and inverse-SSE witness
  findings. All five were reproduced; the first adversarial wave failed 7 of 9 cases, and commit
  `09f9e16dc` closed those instances. Its delta re-review found ambiguous recovery outputs,
  journal-envelope admission, optional-audit isolation, and independent binding-witness gaps. That
  second adversarial wave failed 5 of 13 cases; commit `03e8fa83d` closed them. Final re-review found
  no production blocker and requested only that the schema-provenance test isolate that one field;
  commit `1b096b222` makes that isolation, its mutation went RED/GREEN, and delta review returned GO.
- The exact-blob census had two discarded setup attempts (one interrupted `cat-file --batch` pipe
  deadlock and one short-read assertion) before the corrected streaming pass produced the complete
  denominator above. No tracked bytes changed in those attempts.
- The first base-archive isolation command used a subdirectory-relative pathspec, failed before
  extraction, then (without fail-fast semantics) re-ran the two tests at the feature head in 28.70s.
  That receipt was discarded. The retry ran from the Git top level with `set -e`, printed the exact
  pinned SHA and archive path, and is the 19.19s base receipt above.
- The first mechanical plan-header substitution omitted multiline mode and changed zero bytes. Its
  retry used multiline mode, then read back the Rev 36 prefix and the unchanged Rev 35 suffix.
- The first forbidden-prefix readback loop reused zsh's special `path` variable, which removed Git
  and core utilities from that subprocess's command lookup. Its incomplete output was discarded;
  the retry used a task-specific variable and returned zero files for every fenced prefix.
- The first final exact-`catalog.py` readback supplied a Git-top-prefixed path while already inside
  the product directory; Git warned about the doubled nonexistent directory, so its zeroes were
  discarded. The product-relative retry returned `0/0/0` for status/diff/commit entries.
- The first staged-document `git diff --check` found four Markdown hard-break spaces in the journal
  header. They were removed before the governance commit; no source or generated bytes changed.
- No release fragment was added: the task fence did not authorize the repository's broader
  schema/OpenAPI ABI release-fragment family. The required-field compatibility/version ruling and
  structured fragment are routed to the runtime API release owner before integration, rather than
  silently omitted.

## Readback discipline

The five implementation commits were read back from the attached branch after commit. Final delivery
must again report the branch head, commits ahead of `c1a89b6cf`, clean status, and the complete
base-to-head file set after this journal and the plan receipt are committed.
