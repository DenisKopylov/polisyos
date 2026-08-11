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
5. Every local commit attempt printed that no Lefthook configuration existed. Ordinary Git commits
   succeeded after explicit-path staging, but no hook receipt exists. `[P37: recomputed]`
6. At the first checkpoint, no current-retry N10a writer, N10a check, rederive audit,
   corrupt-field check, or cold N11 call had run. That checkpoint statement is superseded only by
   the step-two receipts below. `[P37: recomputed]`

## Orchestration note

Exactly three Terra agents and no Sol agent were used in the GY-DI2 phase. Their independent
read-only tracks covered
the timing-log/catalog census, frozen N10a/N11 reconstruction, and verification/fence audit. Root
was the sole writer. Censuses and reviews ran in parallel; all three final delta reviews reported no
Critical or Important DI2 source finding. The serialized writer/cold-run wave was not entered in
that phase because the corrupt-lane budget predicate was then unresolved. `[P37:
independently_reconciled]`

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

## Step-two posture receipt

The retry worktree's ignored `production_data` link resolves to the main checkout's production data.
The receipt interpreter was
`/Users/deniskopylov/polisyos/.worktrees/gy-def13-path-witness/policy-engine/.venv/bin/python`,
CPython `3.14.0`; its editable-install `.pth` names the path-witness checkout, and its
`main-venv-dependencies.pth` names `/private/tmp/gy-def13-main.SeLIYb/deps`. Current retry source
preceded that editable witness through `PYTHONPATH="$PWD/src:$PWD"`; `JAX_PLATFORMS=cpu`, and the
receipt interpreter's `bin` directory was first in `PATH`. `[P37: recomputed]`

The durable prior GY-DEFC-3 receipt did not record `sys.executable`, so the exact interpreter used
then remains `not_established`. The path-witness interpreter was selected because it is the one
surviving environment that satisfies every step-two posture predicate simultaneously. `[P37:
not_established for the prior executable; independently_reconciled for the selected posture]`

The explicit inputs remained present and byte-stable: `[P37: recomputed]`

| Input | Bytes | SHA-256 |
| --- | ---: | --- |
| `production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb` | `1,320,693,760` | `4a1eab1363a948a875d00b0ae3929f47b763ba429c85776709641d6ca7960dd7` |
| `production_data/canonical/local_data_20260501/ukraine_server_support_20260410/runtime_calibration_internals/calibration/d2/measurement_registry.json` | `2,112` | `90f341b2e71edb28b6208f580d8a920191d67240c240db9417ba18a225187aff` |

The mandatory catalog-provenance preflight ran under its exact `227.85615` s budget and completed in
`27.931155` s with child/wrapper exit `0`, no timeout, empty stderr, and the frozen pass payload. Its
stdout SHA-256 is `58909d79dd4856cea6df4f4dfbec6a83bfdc179e33164f898b8224085b86a77c`,
exactly equal to the prior accepted posture receipt; the metadata SHA-256 is
`3aac05cae91adcee6398a065f4fb57025d092f8bf57c946534c7fd78a9505a92`. This gate
establishes receipt-equivalent plugin posture for the attempted writer. `[P37: recomputed]`

The frozen N8 input remained byte-identical at
`c3f131ce4f4729936eb3a639cfc81d5d65edb6545b2562d415f64998331bc303` throughout the
writer attempt. Its ambient manifest stayed
`component_discovery_manifest_2b8eea44cd138069e8fb6ec8b3f435a9a677dbc1b1d53d0c4d22fb740b48f70a`
and its provenance ID stayed
`method_catalog_provenance_8b24b2b394460ef1537ce385a2eff920484a390118a8cda2b4f2a5666f7e7597`.
`[P37: recomputed]`

## One canonical writer receipt — terminal success, semantic rejection

The single allowed canonical writer invocation started from clean head
`74b94f30187c980938d05d6d25f470df7cc0eb6d` and called the unmodified canonical owner with
`--write --output-format json`. Under the exact `852.699146` s governed cap, the child and wrapper
both exited `0` after `420.560466` s with no timeout; the owner reported `status=pass`, `issues=[]`,
the complete five-output denominator, and internal wall time `410.05744` s. `[P37: recomputed]`

Writer receipt identities: `[P37: recomputed]`

| Receipt | Bytes | SHA-256 |
| --- | ---: | --- |
| `tmp/gy-defc-3-retry/n10a/writer.stdout` | `129,514` | `ab7e2431f33d9cad44d5399f5db9affb1d805800732fab4c89d08e8f21337d76` |
| `tmp/gy-defc-3-retry/n10a/writer.stderr` | `322` | `5a9c4676c8930ae2eabef79c3ed0eadfedfa2b6fcd09acd5bddde56454096ec4` |
| `tmp/gy-defc-3-retry/n10a/writer.meta.json` | retained | `9ccb59c50f0cbd5b1ec61d4597db90acb92b533665735bfc9bf24c1dad01a274` |

The writer's terminal success did **not** make the artifact delta admissible. A complete recursive
scalar walk derived its five paths from the owner's `ARTIFACT_OUTPUTS`, with
`path_denominator=5` and `file_type_denominator={"json":5}`. It found `133` changed leaves:
`9` in the authorized N8 identity cascade and `124` outside it. `[P37: recomputed]`

| Owner output | Before SHA-256 | Rejected-after SHA-256 | Changed leaves |
| --- | --- | --- | ---: |
| `layer3_gy_second_domain_census.json` | `ba20cdb384eb3e00fb6f13b2fad0b6f679f6fd4debc1148e4fe39a567055e74c` | same | `0` |
| `layer3_gy_second_domain_pack.json` | `9a793bac9f24db73cfedd60c920700e61e775da74d26935f20995c07ccd32686` | `8aad9bc6944679300f582a882595d365d638d97695616dbcb3dc586d3e5a453a` | `3` |
| `layer3_gy_second_domain_smoke_design_problem.json` | `688bd3d8c845ebe99495aecb3b2c10579dbf3f43dd5e8fe0a6686cc6e8b5f76d` | same | `0` |
| `layer3_gy_second_domain_cycle_entry_trace.json` | `f87b6d4b1dc0f053748c86d8023d01dcf6e937ca89727280e116dda53c9477c6` | `8e04f32273b6ca1b6c0d6c324d3ea8d09220ca53d70733377057bbc909c50c7d` | `122` |
| `layer3_gy_second_domain_free_grow_gaps.json` | `d01f8c0440ed0244b447080aaf50d4af66366f1e0ca3af1064d01e1001fc0208` | `0ed1bb2c1978c2f4ddbe0683de8c818d8d923b0d34a0a16927220521c4f296a7` | `8` |

The nine authorized leaves were exactly the N8 contract hash and dependent receipt, the gap-5 and
trace copies, and their ordinary enclosing gap-report/trace/pack content hashes. The direct values
moved as expected: `[P37: recomputed]`

- N8 content identity:
  `sha256:578db97cb5a700f8d069dfe82a8c8d1d81c4a244d9d9cecd1b43a197e8e4727d`
  → `sha256:ad12c4fd20ceee364b1ad4e8a87db877926f8b5a77a7b161745677fa4adb3779`;
- N8 stage-2 receipt:
  `sha256:b0c6bf2b9e3f664fba02e5c1713d419e5894dba0bc8b3bafd8eb58db67953c5f`
  → `sha256:750d304c17659f01e19d14c7dd1846927f638ac31addd441296995d3530d9ea1`.

The `124` unauthorized leaves consisted of: `[P37: recomputed]`

- `116` fresh confidence-ledger/N11 verification-lineage leaves across all four promotion receipts:
  deployment, ledger-root/receipt/head identities and refs, projection hashes, eight `check_id` and
  `claim_execution_binding_hash` pairs per receipt, and risk-spend N11 refs;
- four gap-6 stage-3 leaves (`gap_content_hash`, receipt ref, run hash, and trace hash);
- one gap-6 triage receipt ref;
- the acquisition-routing `generated_at`, from `2026-08-09T21:03:40Z` to
  `2026-08-11T12:54:32Z`;
- two runtime wall-time metrics.

The repeated private verification projection moved its deployment identity from
`policy-engine-deployment:sha256:3cbc30b94a019adea731797f618549ce84a9f9eaf311cda0efe064ec0590354e`
to
`policy-engine-deployment:sha256:41ee25c6f1f294d8c366851e23bbe368969c720f7df1e6b9c4cddb4c780917f7`
and its projection hash from
`sha256:0362b6b99e7e3a4db58edaeb8cea8d1747e141d5ef89915214cc1135a32a3a29`
to `sha256:7d45918abb0b3b209013f9865bd6da8535ec94f51b17a1ae0ba52b81a2347d71`.
Gap 6's stage-3 receipt consequently moved from
`sha256:31a63da98459462f4a748806d24ca6d4e8498bd9e6baa2d7ccdc8566ed7aa449`
to `sha256:a3aa73e73af420a6689f9db832aea38490fa7f57e7667682463775e10a9c3434`.
`[P37: recomputed]`

The complete walk found no movement in governed denominators, comparison/admission outcomes,
transport covariates, the named N8 proof hashes, or the N8 ambient manifest/provenance. All four
fresh promotion projections stayed verification-only, with the same refused/ineligible outcomes,
zero spend, and unchanged budget/admission semantics. That absence does not admit the delta: the
fresh authority-lineage identities and content-visible timestamp are not derived by the N8 identity
change and would rebaseline unrelated recorded values. `[P37: recomputed for the complete absence
and observed identities; not_established for any claim that the 124 leaves derive solely from N8;
institutionally_supplied for the rejection fence]`

The owner source explains the extra movement. Every full writer constructs a temporary
`ConfidenceLedgerSession._for_verification`, passes it to the N9 promotion port, executes a fresh
`GenerationCycleController.run`, serializes that live N6/N9 result into `generation_cycle_run`, and
content-hashes it into gap 6. `_normalize_n6_run_payload` removes only value-port wall time; it leaves
the routing timestamp and private verification projection content-bound. The N11 canonical frozen
artifact is untouched and uses a distinct stable deployment identity. `[P37:
independently_reconciled]`

## Step-two outcome — observed new-class candidate, stop before verification and N11

Section 6 outcome: new-class candidate
`n10a_reissue_live_verification_lineage_drift`. This observed canonical N10a invocation reached
terminal success while reissuing live private N6/N9 verification lineage and an ambient timestamp
outside the requested N8-only receipt boundary. The durable writer receipt remains valid evidence
of execution; its output is a rejected reissue attempt, not an accepted N10a reissue and not a
recorded-value rebaseline. `[P37: recomputed for this observed instance; not_established for class
generality pending architect ratification]`

Smallest correct closure, described and not performed: establish a producer-owned deterministic
replay boundary for the N6/N9 verification projection before it becomes N10a content—explicitly
adjudicate the routing timestamp and verification-lineage identity, reproduce or exclude only what
the contract declares non-governing, and then deliberately batch every resulting downstream reissue
before authorizing another writer. A hand edit, hash substitution, ambient rebaseline, or another
writer invocation is forbidden. `[P37: not_established]`

The rejected bytes were preserved under
`tmp/gy-defc-3-retry/n10a/rejected/after/`; the complete 133-leaf before/after JSONL is
`tmp/gy-defc-3-retry/n10a/leaf-delta-full.jsonl` with SHA-256
`88c7b2ed3ed5c793fa35c4d6faf49c7c2564b004e7789bdffcf1a5af81ce3a62`, and the rejected
unified patch has SHA-256
`db5517d04a46b3fed53edec3c283a5e4c5e3257e8ae1da655b3b8a21893569f0`. After preservation,
only the three writer-dirty owner files were restored to their exact committed bytes; all six
pre-wave artifact/N8 SHA-256 values were re-read and matched. `[P37: recomputed]`

Per the step-two stop fence, N10a `--check`, rederive, and corrupt-field verification were not run,
because there was no admissible reissue to verify or commit. The single cold N11 call was not run;
its allowance remains unused, no milestone trace exists, and `owner_bundle_loaded` remains
`not_established`. `[P37: not_established]`

## Step-two additional non-receipts and orchestration

The controller observed the first ignored supervisor self-test fail before launching a child because
macOS system Python `3.9` lacks `datetime.UTC`, but that failed attempt has no retained receipt.
`[P37: consumer_asserted]` The ignored harness was then made Python-3.9-compatible; the retained
`printf` self-test exited `0`. Neither self-test is product evidence. `[P37: recomputed for the
retained second self-test]`

The controller observed the strict expected-nine-leaf discriminator exit `1` on the `124` extras;
that invocation/exit has no retained command receipt. `[P37: consumer_asserted]` The generic complete
leaf dumper independently persisted all `133` before/after rows and proves the same semantic
rejection. No field was normalized, substituted, or removed to make either discriminator green.
`[P37: recomputed for the complete leaf dump]`

The fresh closeout architecture guardrail ran under a `180` s cap and exited `1` after `72.443767` s
with the same `5,081`-byte stdout SHA-256 as the earlier accepted negative receipt:
`73b53d0a9278bcb2acffbac62e925e6ca30ce40caeb0b3588ce5323dfd1559fb`. It named only the
pre-existing deep-import baseline file plus the five untouched runtime paths enumerated above;
the complete changed-path intersection was empty, so no baseline was synchronized. `[P37:
independently_reconciled]`

The corrupt-field lane's `300` s declared ceiling was never spent because the reissue failed the
semantic acceptance gate before any verification. It remains a declared hang fence, not a catalog
sample or measured budget. `[P37: institutionally_supplied for the ceiling; not_established for a
current corrupt result]`

Step two used exactly three fresh Terra agents and no Sol agent. Their read-only tracks pinned the
posture, the five-output semantic discriminator, and the single-call N11 harness. Root alone ran the
serialized posture/writer chain. After the delta failed, two agents independently reviewed the
frozen dirty tree and both returned `REJECT/STOP`; no subagent ran or edited an owner. `[P37:
independently_reconciled]`
