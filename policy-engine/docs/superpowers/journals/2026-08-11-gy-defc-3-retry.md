# GY-DEFC-3 retry — catalog the lane before reissue

Date: 2026-08-11

Branch: `codex/gy-defc-3-retry`

Base: `c1a89b6cf`

DI2 commit: `1b34c7f6c` — `fix(tools): derive timing budgets from successful runs`

## Current verdict

`GY-DI2` is implemented, behaviorally verified, independently reviewed, committed, and read back
from the attached branch. The effective timing catalog is now derived from every successful exact
tool-and-mode lane in the complete recorded log, with the repository catalog retained only as a
fallback. `[P37: recomputed]`

The N10a writer has not been launched in this retry. The implemented literal Rev 35 admission rule
correctly excludes every non-zero-exit record, while the canonical N10a corrupt-field verifier is
healthy only when it exits `1`. Its recorded lane therefore has no accepted duration sample or
governed timeout, although section 3 also requires that verifier to run at its "now-catalogued
budget." These predicates cannot both be satisfied without an architect ruling; silently admitting
exit-1 durations or borrowing another lane's timeout would contradict the task. `[P37:
independently_reconciled]`

Because an accepted N10a reissue could not then complete all three required budgeted verifications,
the expensive wave stopped before the writer. No N10a output changed and the one-cold-N11 allowance
remains unused. The cold objective is therefore `not_established`, not failed. `[P37:
not_established]`

## Step-two ruling — completion, GY-DI4, and the declared corrupt fence

The architect's step-two ruling supersedes the checkpoint blocker above. Timing-sample admission is
governed by **contract-declared completion**, not by the proxy `exit_code == 0`: the default healthy
terminal set is `{0}`, while each of the four `corrupt-field-drift-check` lanes declares `{1}`.
Harness/timeout termination, signal death, skips, malformed records, and terminals outside the
lane's declared set remain inadmissible. `[P37: institutionally_supplied]`

For N10a specifically, the canonical validator computes `missing`, returns report status `"fail"`
when `missing` is empty, and maps that completed outcome to exit `1`; exit `2` means at least one
expected mutation went undetected. Thus healthy exit `1` is grounded in the lane's own return
mapping, not inferred from the timing log or widened globally. `[P37: recomputed]`

The six lanes exposed as unbudgeted by the accepted GY-DI2 implementation split `2/4`: guardrails'
real exit-1 failures and the UDF-performance skip are correctly excluded, while the four corrupt
lanes are completed-work receipts that the proxy misclassifies. The report must remain unchanged in
this session; this split is evidence for the registered substrate defect, not authority to patch it
locally. `[P37: independently_reconciled]`

`GY-DI4` is registered here and deliberately not implemented. The timing substrate currently derives
lane health from `exit_code == 0`, although authority over a validator's healthy terminal lives in
that validator's return mapping. The smallest correct closure is a per-lane healthy-terminal set at
the tool-declaration layer, default `{0}`, consumed by sample admission; no declaration may admit a
harness termination, signal death, or skip, and every catalog row must record the predicate that
admitted its samples. Inferring the set from the log, letting the budget consumer select it, or
widening exit `1` globally are forbidden closures. `[P37: institutionally_supplied]`

For this wave only, N10a's corrupt verifier has a `300` s `declared_ceiling`: a hang fence about
twelve times the maximum of its five healthy completed runs (`13.403`, `13.466`, `14.522`, `19.605`,
and `24.675` s), not a measured budget and not a catalog value. Green is exit `1` with empty
`missing`; exit `2` or exceeding the ceiling stops the task. `[P37: institutionally_supplied for the
ceiling and admission; recomputed for the recorded durations]`

`GY-DI3` is sharpened but remains out of scope: the receipt-equivalent interpreter and dependency
posture also live under `/private/tmp`, so a reboot can erase both the measurement substrate and the
ability to execute this chain. Durability remains `not_established`; no relocation or persistence
repair is performed here. `[P37: not_established]`

## GY-DI2 catalog closure

The complete `/tmp/polisyos-tools/timing.jsonl` input initially contained 109/109 parseable JSONL
records. Exactly 58 exit-zero, `status=ok` records represented 19 exact tool-and-mode lanes; the
static repository catalog contained 22 lanes and overlapped only four of the 19, leaving 15
successful recorded lanes absent before this repair. `[P37: recomputed]`

The generic derivation now groups the complete log by exact `tool:mode`, admits only records with
`status == "ok"`, integer `exit_code == 0`, and finite non-negative duration, recomputes nearest-rank
p95 from `samples_ms`, and derives the timeout as exactly `2 * p95`. A log-derived lane replaces a
same-key repository fallback, while unobserved repository rows remain available as fallbacks.
`[P37: recomputed]`

Malformed raw records fail closed before either summary or budget derivation: missing receipt
fields, blank identities or timestamps, invalid timestamps, Boolean exit codes, and negative or
non-finite durations are rejected. A repository row with no samples/p95/2x timeout is not treated as
an executable budget merely because its key exists. `[P37: recomputed]`

`report-timing` now names its scope as
`recorded_successful_lanes_plus_repository_fallbacks`, reports repository/effective/observed/
successful/uncatalogued denominators, and exposes every observed lane without an accepted budget in
JSON, text, and Markdown. Each derived lane carries the resolved exact log origin in both
`sample_source` and `source_refs`. `[P37: recomputed]`

After three early unified-CLI test invocations appended telemetry, the complete log contained 115
records and 27 observed lanes. The six added rows were three skipped
`diagnostics.check-udf-perf:default` records and three successful
`diagnostics.check-setup:default` records; no N10a sample changed. Subsequent tests used an ignored,
task-local timing log. `[P37: recomputed]`

The post-commit report read back these complete-set counts: 22 repository lanes, 37 effective
lanes, 27 observed lanes, 19 successful observed lanes, and six observed lanes without an accepted
budget. The six are: `[P37: recomputed]`

1. `architecture.guardrails:default`
2. `diagnostics.check-udf-perf:default`
3. `quality.validation.check_layer3_gy_generation_cycle_contract:corrupt-field-drift-check`
4. `quality.validation.check_layer3_gy_promotion_contract:corrupt-field-drift-check`
5. `quality.validation.check_layer3_gy_second_domain_pack:corrupt-field-drift-check`
6. `quality.validation.check_layer3_gy_value_gate_contract:corrupt-field-drift-check`

The six successful N10a writer samples remain exactly `194867.984`, `233056.514`, `292902.311`,
`334561.053`, `397509.035`, and `426349.573` ms. The recomputed p95 is `426349.573` ms and its exact
2x timeout is `852699.146` ms (`852.699146` s). `[P37: recomputed]`

N10a's other accepted lanes read back as follows: `[P37: recomputed]`

| Lane | Accepted samples | p95 (ms) | 2x timeout (ms) |
| --- | ---: | ---: | ---: |
| `check` | 6 | `37136.084` | `74272.168` |
| `rederive-audit` | 4 | `363402.688` | `726805.376` |
| `write` | 6 | `426349.573` | `852699.146` |
| `corrupt-field-drift-check` | 0 | not established | not established |

The corrupt lane has six observed non-zero receipts: five exit `1` and one exit `2`. Rev 35's
literal rule excludes all six from samples, and the report surfaces the lane as unbudgeted rather
than silently treating a semantically expected exit `1` as timing success. `[P37: recomputed]`

`GY-DI3` remains registered and out of scope. The live log's survival across reboot is
`not_established`; this task neither relocated it nor copied it into a durable substrate. `[P37:
not_established]`

## Behavioral verification

The final focused suite used an isolated timing log and passed `59` tests. Ruff passed over all four
changed Python paths, and `git diff --check` exited `0`. `[P37: recomputed]`

The marker-preserving mutation removed only the text/Markdown list rendering for uncatalogued lanes
while retaining the fields and headings. The real CLI behavioral test then failed because the
failure-only lane was absent; restoring the runtime rendering made the same test pass. This proves
the point-of-use visibility gate exercises the property rather than only checking markers. `[P37:
recomputed]`

Architecture guardrails exited `1` only on the pre-existing deep-import baseline drift in these
untouched paths: `[P37: independently_reconciled]`

- `architecture/baselines/imports/deep_import.json`
- `src/polisyos/runtime/http/execution_policy.py`
- `src/polisyos/runtime/http/routes/runs.py`
- `src/polisyos/runtime/http/services/channel_contracts.py`
- `src/polisyos/runtime/http/services/control/lex_pipeline.py`
- `src/polisyos/runtime/http/services/control/lex_search_projection.py`

The changed-path intersection was empty, so the baseline was not synchronized. `[P37:
independently_reconciled]`

## Three dispositions that must remain distinct

1. **Address binding (`GY-DEF13`).** Editable `direct_url.json` bytes encode a checkout address, not
   a content identity. The correct repair records the editable posture and leaves the address hash
   unbound/non-decisive; two checkout paths then produce the same governed identity. `[P37:
   independently_reconciled]`
2. **Ambient-but-decisive state (`GY-DEF14`).** Example-plugin import posture is ambient state that
   the design says should not govern, yet it still feeds the decisive manifest identity. That defect
   is registered and deliberately out of scope here. Its closure is `not_established`. `[P37:
   not_established]`
3. **Stale content identity (this N10a reissue).** N10a intentionally pins N8's contract content
   hash. When N8 is legitimately reissued, that identity and its dependent receipt ref move; the
   frozen downstream receipt becoming stale is correct behavior, and its canonical producer must
   reissue the complete owned five-artifact set. `[P37: independently_reconciled]`

## Non-receipts

1. The inherited prior `GY-DEFC-3` writer invocations were killed at approximately `526.392` s and
   `726.8` s with zero changed bytes and produced no accepted reissue; both are timing/harness
   non-receipts. `[P37: recomputed]` The architect's Rev 35 ruling says such a
   zero-byte non-receipt consumes no accepted-reissue allowance. `[P37: institutionally_supplied]`
2. The first focused baseline suite exposed an existing classifier omission for the canonical
   `--reissue-catalog-provenance` action. It was a red test, not product evidence; the generic action
   classifier and its coverage test now include that real surface. `[P37: recomputed]`
3. Early unified-CLI tests appended six diagnostic rows to the shared timing log. Those rows were
   enumerated above, changed no N10a lane, and are not N10a reissue or verification receipts.
   `[P37: recomputed]`
4. Architecture guardrails exited `1` on the untouched baseline drift enumerated above. The empty
   changed-path intersection makes it a guardrail non-receipt for this delta, not a green check and
   not a defect caused by this task. `[P37: independently_reconciled]`
5. The local commit hook printed that no Lefthook configuration existed. The ordinary Git commit
   succeeded after explicit-path staging, but no hook receipt exists. `[P37: recomputed]`
6. No current-retry N10a writer, N10a check, rederive audit, corrupt-field check, or cold N11 call
   has run. No claim is made about any of their outcomes. `[P37: not_established]`

## Orchestration note

Exactly three Terra agents and no Sol agent were used. Their independent read-only tracks covered
the timing-log/catalog census, frozen N10a/N11 reconstruction, and verification/fence audit. Root
was the sole writer. Censuses and reviews ran in parallel; all three final delta reviews reported no
Critical or Important DI2 source finding. The serialized writer/cold-run wave was not entered because
the corrupt-lane budget predicate remains unresolved. `[P37: independently_reconciled]`

## Branch readback at this checkpoint

Immediately after the DI2 commit, the attached branch head was
`1b34c7f6c37fa67acc7cb8d258b0d0deda4d716d`, exactly one commit ahead of `c1a89b6cf`, and the tree
was clean. The committed file set was read back as: `[P37: recomputed]`

1. `tests/repo_quality/tools/test_timing.py`
2. `tests/repo_quality/tools/test_unified_cli.py`
3. `tools/cli.py`
4. `tools/lib/timing.py`

The unrelated main-checkout edit at `src/polisyos/data_forge/read_api/catalog.py` never entered this
worktree, staging area, commit, or execution identity. `[P37: independently_reconciled]`
