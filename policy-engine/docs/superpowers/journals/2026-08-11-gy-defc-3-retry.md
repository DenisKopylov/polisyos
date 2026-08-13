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

## Rev-37 source adjudication preflight — stopped before the source batch

This continuation began attached to `codex/gy-defc-3-retry`, clean at
`9a24a4eface06f55fab3a08570e825bd749aee38`. The protected
`src/polisyos/data_forge/read_api/catalog.py` was absent from this worktree and no source, tool,
test, or governed-artifact byte was changed during the adjudication. `[P37: recomputed]`

The proposed verification-projection member of `GY-DEF14` is real. A verification confidence
ledger projection is explicitly non-authority: `promotion_sequence.py:301-305` rejects any such
receipt that becomes consumer-promotable, `_for_verification` at `:483-489` constructs a private
port whose receipts cannot authorize N6, and `:1184-1186` forces the verification-only refusal.
Nevertheless, `confidence_ledger.py:3397-3456` builds and content-hashes the N9 promotion-role,
current-head certificate projection, including verification deployment, root, head, receipt and
filtered promotion-check lineage. The prior complete leaf walk proved those fresh identities then
entered the N10a trace's decisive identity. That complete N9 projection is real recorded evidence
and must remain present and readable. The authority/status contract proves it cannot govern
consumer promotion, but no current contract declares the exact stable comparison field/path set;
defining that set is part of the repair rather than an inherited fact. `[P37:
independently_reconciled for the non-authority projection and decisive binding; not_established for
the exact comparison projection until its typed contract exists]`

The proposed `GY-DEF10` member is false on this head: its registered missing owner was already
closed by `431bcd798`. The canonical owner is
`pdc/_impl/gy_waist.py:176-262`: `strip_gy_volatile_fields` owns the semantic projection and
`reconcile_gy_operational_leaves` fails closed on semantic drift, shape drift and exact drift before
preserving shared operational leaves. Depth-N imports that owner at
`check_layer3_gy_depth_n_universality_contract.py:58-65` and uses it in controlled replay at
`:5000-5043`, the writer at `:6965-6975`, and rederive at `:7915-7924`. N10a already imports the
same owner at `check_layer3_gy_second_domain_pack.py:51-55` and applies it at `:6424-6442`.
`[P37: independently_reconciled]`

Five existing owner/N10a behavioral witnesses ran under the receipt CPython with the retry
worktree first on `PYTHONPATH` and exited `0` (`5 passed`): the two PDC operational-reconciliation
tests, N10a's same-semantic routing-time preservation test, its writer/rederive operational
normalization test, and its missing-runtime-property negative test. They establish the owner-unit
semantic/shape guards and typed recursive drift report, plus N10a's late reconciliation of declared
operational leaves conditional on an already-equal trace hash; they also prove that normalization
cannot invent an absent operational leaf. They do not execute two fresh N10a verification sessions
or establish a stable trace identity for the full recorded projection. The deeper Depth-N witness at
`tests/unit/runtime/quality/test_depth_n_universality.py:2458-2768` independently encodes the same
owner property: generated-at and wall-time changes replay byte-identically, then a semantic
`node_ref` change raises `authority_source_controlled_replay_recording_drift` with operand roles,
identities and the named changed leaf. `[P37: recomputed for the five executed witness results;
independently_reconciled for the inspected Depth-N witness; not_established for fresh-session N10a
trace-identity equivalence]`

The current failure precedes that operational owner. N10a serializes the raw
`GenerationCycleRun` at `check_layer3_gy_second_domain_pack.py:2597`, embeds it verbatim as
`generation_cycle_run` at `:2643`, and computes `trace_content_hash` at `:2653-2657` through the
tool-local `_with_content_hash`/`_hash` path at `:6394-6406` and `:6445-6446`. The only allowed
artifact-declared top-level trace exclusion is `runtime_metrics` (`:184-188`); the invoked
`gy_content_hash` also recursively strips the generic volatile key-name classes declared in
`pdc/_impl/gy_waist.py:29-45` and applied at `:166-199`. None projects away the path-specific
verification lineage. The later reconciliation at `:6424-6442` runs only when the already-computed
self-hash is equal, so it cannot absorb a fresh embedded verification lineage. `[P37:
independently_reconciled]`

Consequently, the requested runtime-quality-only fence cannot implement the correct `GY-DEF14`
closure. A helper added only under `src/polisyos/runtime/quality/**` has no call site on the decisive
N10a hash path and would be `contract_only`/`P01`; global exclusions, placeholders, and mutation of
the full verification receipt would each violate the positive specification. The smallest correct
closure is a runtime-quality-owned, typed/versioned comparison projection plus its recomputation
validator, consumed by the single N10a assembly/validation bridge in
`tools/quality/validation/check_layer3_gy_second_domain_pack.py`. That bridge must preserve and
validate the full readable verification projection while hashing an explicit stable comparison
projection in its place. No PDC or ledger-scope change is required. Two independent Terra source
audits reached the same blocker and bridge boundary. `[P37: independently_reconciled]`

Because `tools/**` is closed in this session and the architect explicitly required both premises to
be verified before acting, no red test or source batch was written, no expected-delta declaration
was minted for an unimplementable batch, and no posture gate, writer, N10a verification, or cold
N11 process was launched. The accepted-reissue and one-cold-N11 allowances remain unused;
`owner_bundle_loaded` remains `not_established`. `[P37: institutionally_supplied for the closed
tool fence and stop instruction; recomputed for the absence of invocations; not_established for the
objective]`

One attempted collection of four deeper Depth-N tests used the preserved path-witness `.venv` and
exited `4` before collecting any test: the repository's interpreter guard observed the witness
prefix where it required an isolation-local retry-worktree `.venv`, which does not exist. It changed
no bytes and is a setup non-receipt, not product evidence. The five lighter owner/N10a witnesses
above were then run with the same receipt interpreter and current-worktree source precedence; they
do not supersede the missing deep-test receipt. `[P37: recomputed]`

The rejected step-two writer bytes and their complete `133`-leaf evidence remain preserved at the
paths and hashes recorded above; this continuation did not alter them. `[P37: recomputed]`

This continuation used exactly three fresh Terra agents and no Sol agent. Their read-only tracks
adjudicated the verification projection, the already-closed operational owner, and the wave/hash
boundary; root alone inspected the branch and ran the five lightweight tests. No agent edited a
source, tool, test, or artifact. `[P37: recomputed for orchestration; independently_reconciled for
the two-agent bridge verdict]`

## GY-DEF14 blast-radius gate — outside-four stop

This continuation observed `codex/gy-defc-3-retry` attached and clean at
`0ff4ed6814a6dd4c890df1f4c0a2b9b5b62842fe`, five commits ahead of `c1a89b6cf`.
The committed `src/polisyos/data_forge/read_api/catalog.py` exists here, but the unrelated edit in
the main worktree did not enter this retry worktree's tracked diff. The branch/head and current
non-intersection are re-readable; no immutable start-status receipt was retained. `[P37: recomputed
for current branch/head and changed-path non-intersection; not_established for historical start
cleanliness]`

`GY-DEF10` is dropped from this batch under the architect's ruling and the source adjudication
recorded above. Transferable lesson: a measured claim in a plan expires when a commit lands against
it, and an architect adjudication is a claim. `[P37: institutionally_supplied for the ruling;
independently_reconciled for the stale-plan diagnosis]`

### Complete counterfactual census

The blocking walk enumerated the complete top-level JSON denominator
`architecture/policy_design_case/*.json`: `353/353` paths, file-type denominator `json=353`, and
`353/353` successfully parsed mappings. It did not substitute the recursive directory census, which
is a different set. For every member it applied the current field-name predicate and the literal
counterfactual from this task: a mapping is removed from the comparison projection only when its
own direct `authority_provenance` value is exactly the string `verification`; absent or unrecognized
declarations remain governing. `[P37: recomputed]`

The walk found `23` exact verification-declared blocks across **five**, not four, stored artifact
identities. It recomputed each affected producer's current self-identity using that producer's exact
root exclusion and reproduced all five committed values before applying the counterfactual. The
counterfactual removes `3,721` scalar leaves after the existing volatile-key projection:

- `layer3_gy_confidence_ledger_contract.json`, `artifact_content_hash`, four blocks / `1,023`
  leaves: `sha256:62df18eb9d78368cacc607790541d2237f66f9a7ab381ef83bf6116fdea4f225`
  to `sha256:b07cad0ea16450bb17571c21f3a953a93da0c5d3434ca6265fce0eb3cab09314`;
- `layer3_gy_depth_n_universality_contract.json`, `contract_content_hash`, ten blocks / `1,564`
  leaves: `sha256:c50d0d70a89502a8a55111a87bf0b3fa549b20f83a7478a0683b8953c146212a`
  to `sha256:5705126dbc5d3a564c7d7e9b90e378bd6cc500abb5f08f43cd087e2103fc94df`;
- `layer3_gy_generation_cycle_contract.json`, `contract_content_hash`, two blocks / `212` leaves:
  `sha256:90e0b024819495086752961c4d7ac80bb764586af8f89830504b8c0161c5912d`
  to `sha256:fca36509a29d2890d6349dc9244b2907e3c18cf57a44bdb469a2018c9ffae686`;
- `layer3_gy_promotion_contract.json`, `contract_content_hash`, three blocks / `210` leaves:
  `sha256:a808d43e2ced33efe4772aaacc5507e68e46dd91fcfd072d7a2b5c2f78c67b0a`
  to `sha256:6783a1560330e7f0649d4b09232896916bf2c7fe9458aeab149e4430f6edefbd`;
- `layer3_gy_second_domain_cycle_entry_trace.json`, `trace_content_hash`, four blocks / `712`
  leaves: `sha256:f9be282f0b16720d38440572aeecfc9c47f2566407fa5a68a8402796ef250430`
  to `sha256:2902c76a66a70d4f8c29f60d2ed19a447301f8c6974f3e409dc116f7255ff509`.

The block denominator is exact: confidence-ledger projections
`/conformance_ledger_projection`, `/n12_epoch_reference_projection`,
`/n9_promotion_projection`, `/real_ledger_projection`; Depth-N
`/proof_recordings/{education,first_vertical,unseen}/compiled_run/recursive_run/nodes/0/cycle_run/`
`promotion_port/receipts/{0..3,0..2,0..2}/confidence_ledger_projection`; generation-cycle
`/generation_cycle_run/promotion_port/receipts/{0,1}/confidence_ledger_projection`; promotion
`/{contract_lane_anytime_refusal,non_promotable_contract_stamp,production_honest_shadow}/`
`confidence_ledger_projection`; and N10a trace
`/generation_cycle_run/promotion_port/receipts/{0,1,2,3}/confidence_ledger_projection`.
`[P37: recomputed]`

The complete `353`-row artifact walk and every one of the `3,721` removed scalar leaf paths are
preserved under `tmp/gy-defc-3-retry/def14-blast-radius/`:

- `census.py` SHA-256
  `014f7009072656ff65c8035068947a50409941f21acbbb17c6a32ae1dc9ec5f3`;
- `summary.json` SHA-256
  `e3819bdaafc83a658e83d029ee3f5ec3b2fc0102aee2f169e35f8c80de3c3d5e`;
- `artifacts.jsonl` SHA-256
  `f5c6316fb00dc4dddfd6a07e406359bac5b1e9ff1b1b1a1cc3874269faa0404e`;
- `removed-leaves.jsonl` SHA-256
  `0b5ef1e188a41ba44116c8e97b951a1f38e295206ade40a00722fb0264a06ec6`.

Those ignored files are measurement evidence, not governed outputs. `[P37: recomputed]`

Depth-N is the fifth identity and is outside the architect's named four. It contains the ten exact
blocks above plus nine further mappings whose `authority_provenance` is the list
`["verification"]`; the literal counterfactual treats those unrecognized declarations as governing,
as required by the fail-closed rule. Their presence means the counterfactual census is a blast-radius
witness only, not a typed repair projection or a writer allow-list. `[P37: recomputed for the
serialized declarations and fifth identity; not_established for any repaired predicate]`

### Branch and stop

The task's third branch says anything outside the architect's four stops immediately. The fifth
Depth-N identity therefore selects that branch. No unit test, source batch, posture gate,
expected-delta declaration, N10a writer/check/rederive/corrupt lane, or cold N11 process was
launched. No tracked product source, tracked tool, test, governed artifact, denominator,
comparison/admission field, ledger scope, or ambient binding changed; the census wrote only the
ignored measurement evidence named above. The accepted-reissue and single-cold-N11 allowances
remain unused, and `owner_bundle_loaded` remains `not_established`. `[P37:
institutionally_supplied for the branch rule and the allowances' opening state; recomputed for the
current tracked product diff; not_established for the historical non-invocation negative and the
objective]`

Smallest next closure, described and not performed: the architect must first adjudicate the fifth
Depth-N member and the nine unrecognized declaration shapes, then authorize a typed, versioned
runtime-quality-owned N6/N9 comparison projection, its recomputation validator, the N10a validation
bridge, and the complete batched reissue/verification set. A tool-local or PDC-local projection and
a bare JSON declaration cannot themselves carry an authority-grade exclusion predicate. `[P37:
not_established]`

The three tracks newly dispatched for this gate were `def14_blast_radius_audit`,
`def14_predicate_design_audit`, and `def14_wave_audit`, covering the `353`-artifact census, the
predicate/ownership boundary, and the stopped wave. The dispatches selected Terra and no Sol. Root
alone is reported to have run the read-only census and written only ignored measurement evidence plus
this journal. Two agents independently confirmed the outside-four stop. `[P37: consumer_asserted for
the dispatch set, model selection, and root-only execution; independently_reconciled for the stop;
not_established for historical no-agent-write/no-agent-launch negatives]`

## GY-DEFC-4 — predicate contract and pre-source gate

This continuation started with `codex/gy-defc-3-retry` attached and clean at
`a9d276177b5098febebff1ba031bcb298166bda3`, six commits ahead of `c1a89b6cf`. The unrelated
main-worktree edit to `src/polisyos/data_forge/read_api/catalog.py` is not in this worktree's changed
path set. `[P37: recomputed]`

### Timing census and confidence-ledger probe

The session-start timing report parsed `117` records. Its exact admitted-sample arithmetic retained
these four measured writer ceilings: promotion `32,437.008` ms, generation cycle `56,250.878` ms,
N10a `852,699.146` ms, and Depth-N `4,942,540.412` ms. The current log had no successful
confidence-ledger writer sample; its repository fallback is not evidence that this tree's writer can
reach its own terminal. Corrupt-field runs remain unbudgeted under the registered-but-unimplemented
`GY-DI4` predicate, so the task's `300`/`600` second values remain declared hang fences rather than
measured budgets. `[P37: recomputed for log arithmetic; institutionally_supplied for the declared
hang fences; not_established for a confidence-ledger execution budget]`

The first confidence-ledger launch was a setup non-receipt. It used the surviving CPython 3.14
interpreter directly while this worktree had no ignored `.venv` link, so the validator's own
`assert_repository_interpreter` gate stopped at `wrong_interpreter_resolved` before writer work:
`byte_stable_passes=0`, `second_pass_started=false`, duration `20.862992` s, exit `1`. It wrote no
artifact bytes. The governed confidence-ledger artifact remained exactly `108,740` bytes at SHA-256
`a844a0c318a95e6f653dda34c3a7f6db6592070b8abe25b0b9e9b1bdc2824781`. The receipt is preserved
under `tmp/gy-defc-4/confidence-probe/writer.{stdout,stderr,meta.json}`. `[P37: recomputed]`

The missing ignored `.venv` link was then reconstructed to the same surviving receipt environment;
its resolved prefix and `sys.prefix` both equal
`/Users/deniskopylov/polisyos/.worktrees/gy-def13-path-witness/policy-engine/.venv`. With current
worktree source first in `PYTHONPATH`, `JAX_PLATFORMS=cpu`, explicit catalog/L5 inputs, and a scratch
`--output`, the substantive probe ran alone under the declared `1,800` s fence. It completed in
`111.920627` s without timeout and exited `1`; no scratch artifact was produced, and the governed
artifact remained byte-identical. The terminal report reached `confidence_registry_loaded`,
`owner_pre_derivation_fence_started`, `owner_pre_derivation_fence_complete`, and
`n10_owner_recomputation_started`, then raised `OwnerProjectionError` with the known chain
`n10_capstone_provenance_unstable -> n10a_owner_validation_failed ->
n8_transport_gap_receipt_drift`. It reported `process_group_clean=true`,
`byte_stable_passes=0`, and `second_pass_started=false`. Receipt SHA-256s are stdout
`4418953192944255118eb6eea263eed015a4d301383bb8d97ec997dd5f23d43b`, stderr
`c8fa7c8dc6560ff0ee5ec2bb3714332a3e164387da6934b9dd424d4eda3bb91f`, and metadata
`c8311a20264c35be1c8ecd071a2025e58f49c7a6600802b32b742c7f50327be3`.
`[P37: recomputed]`

That result selects pre-authorized branch B3: confidence-ledger is a blocked member because its
canonical writer cannot produce a clean baseline before the antecedent N10a receipt is repaired.
It is removed from this reissue batch, not repaired here; the remaining batch is promotion,
generation cycle, N10a, and Depth-N. The probe failure is the already-known stale-content-identity
class, not evidence against the `GY-DEF14` predicate. `[P37: institutionally_supplied for B3;
recomputed for the exception class and absent output]`

### Predicate contract — frozen before source work

The comparison-exclusion decision is a recomputed predicate over a mapping's own direct
`authority_provenance` declaration. A mapping is excluded from the compared identity if and only if
all of the following hold:

1. the declaration is present directly on that mapping;
2. its serialized shape is either one string or a list of strings;
3. normalizing the scalar to a one-member list yields a non-empty declaration; and
4. every declared value belongs to the closed recognized non-authority set, currently exactly
   `verification`.

Thus scalar `"verification"` and list `["verification"]` are equivalent and non-governing. Any
recognized authority element, including `canonical_repo`, keeps the whole mapping governing. An
absent, empty, malformed, mixed, or unrecognized declaration also keeps the whole mapping governing;
examples include `null`, `""`, `[]`, `{}`, `42`, `[42]`, `["verification", "canonical_repo"]`,
and `["not_established"]`. The rule fails closed rather than inferring authority from the log, the
path, a field-name allow-list, or the task that needs the hash. `[P37: institutionally_supplied for
the contract; recomputed is the required implementation-time admission label]`

Exclusion applies only to the comparison projection used by the decisive content identity. The
source mapping and every nested verification receipt remain present, complete, byte-readable, and
subject to their ordinary full-record validation. The projection is derived recursively from the
payload declaration; it does not enumerate the observed blocks or their leaves, does not replace
values with placeholders, does not widen operational normalization, and does not change ledger scope
semantics. `_normalize_n6_run_payload` must delegate to this owner rather than maintain a second
local exclusion rule. `[P37: institutionally_supplied for the positive/forbidden specification;
not_established until behavioral witnesses and readback close]`

The scalar-only blast-radius trial's `3,721` leaves is therefore not the repaired prediction. The
nine Depth-N blocks declared as `["verification"]` contribute another predicted `60` scalar leaves,
so the pre-source contract predicts `32` excluded blocks and `3,781` scalar leaves across the same
five artifact identities. Empty and unrecognized list declarations remain outside that prediction.
This correction is accepted only after a fresh complete post-repair census reproduces it per
artifact. `[P37: independently_reconciled for the prediction; not_established for the post-repair
result]`

### Red-first source batch and post-repair census

Before source changed, the new predicate/bridge witness selection returned `15` failures: the owner
accepted no payload context, scalar/list verification projections produced distinct hashes, list
members remained present in the comparison projection, and the N10a trace hash bound the fresh
lineage. That is the intended red receipt. After the source batch, the same `15` cases passed; the
expanded owner/N10a selection passed `22/22`, and Ruff plus `git diff --check` were green.
`[P37: recomputed]`

The source batch is deliberately four tracked paths:

1. `src/polisyos/pdc/_impl/gy_waist.py` extends the existing canonical predicate with the containing
   value, admits only a non-empty scalar/list made entirely of the closed `verification` set, drops
   qualifying nested mappings from the compared projection, and lets reconciliation retain the live
   full block after the recomputed projections and non-authority shapes agree;
2. `tools/quality/validation/check_layer3_gy_second_domain_pack.py` delegates its N6 wall-time
   decision to that owner rather than treating the local literal as authority;
3. `tests/unit/pdc/test_gy_waist_contracts.py` carries the scalar/list, fail-closed, mixed-authority,
   unrecognized, governing-drift, and full-record witnesses; and
4. `tests/unit/runtime/quality/test_second_domain_pack.py` proves that N10a retains two different
   complete verification projections and metrics while deriving one comparison identity, with a
   mixed authority projection remaining decisive.

No other validator needed a second predicate: their producer and verifier paths already consume
`gy_content_hash`, so the single owner change is their shared bridge. The full blocks remain in the
input/output mappings; only the recursively derived projection omits them. `[P37: independently_reconciled
for the owner/consumer map; recomputed for the executed witnesses and tracked path set]`

The post-repair walk parsed the complete `architecture/policy_design_case/*.json` denominator:
`353/353`, file-type denominator `json=353`. It independently reimplemented the old field-only
projection and compared that with the repaired owner. All five old producer self-identities reproduced
their committed values, no unregistered sixth artifact moved, and the exact repaired set was:

- confidence ledger: `4` blocks / `1,023` scalar leaves;
- Depth-N: `19` blocks / `1,624` scalar leaves;
- generation cycle: `2` blocks / `212` scalar leaves;
- promotion: `3` blocks / `210` scalar leaves; and
- N10a cycle trace: `4` blocks / `712` scalar leaves.

Total: five artifacts, `32` blocks and `3,781` scalar leaves. This closes B1 as an explained correction
to the scalar-only `3,721` input and leaves B2 inactive. The new Depth-N comparison identity predicted
by the repaired projection is
`sha256:8c0274f08473c298828ba548b02977133821689256ac6708258397b109822494`;
the other four predictions equal the earlier scalar trial because their declaration shapes were
already scalar. `[P37: recomputed]`

The ignored census receipts live at `tmp/gy-defc-4/post-repair-census/`: script SHA-256
`82b30901fc141ea64f8f74876b3ca81f9b59faaaa28dad265c7e459a0c1fdf45`, summary
`a99df3c7e2de685ee7ab0ace8283d45216b3635ef4ef9b0b386ae67c6ea4f553`, `353`-row artifact log
`8332d095927258e805baad314712076e8e80e22a7cd849926edb6da316ff29d7`, and `3,781`-row removed-leaf
log `42c4ed73793c828267e41cdf7ae40ac8d60af116800d1475cf1c261d48b5a1dd`.
`[P37: recomputed]`

The complete two-file owner/N10a unit invocation reached a terminal exit `1` with four failures after
the focused green. Two were the expected pre-reissue `trace_content_hash` drift on the still-frozen
N10a artifact. The other two asked the ordinary unit-test interpreter to validate the frozen N8
catalog posture; a direct diagnostic returned the ten known `catalog_*_mismatch` codes because this
was intentionally not the receipt-equivalent interpreter. Those four failures are pre-reissue/setup
non-receipts, not predicate counterexamples; no test was rewritten around them. `[P37: recomputed for
the failure codes and current source/artifact mismatch; independently_reconciled for the known ambient
posture class]`

### Frozen-review rejection and authority-bound correction

The first frozen source commit, `d03f0c6e6`, is rejected as an implementation receipt. Its generic
recursive projector trusted any mapping whose own bare `authority_provenance` field said
`verification`; a coherently self-labelled arbitrary mapping could therefore make retained bytes
disappear from `gy_content_hash` without a producer proof. That is `P32` trust-by-form and gives a
candidate-grade declaration authority over a custody identity. The frozen review caught it before
any governed writer, accepted reissue, posture gate, or cold N11 launch. The source commit remains in
append-only history, but no governed artifact was minted under it and the subsequent source batch
supersedes it. `[P37: independently_reconciled for the authority leak; recomputed for the current
governed-artifact diff; not_established for historical process non-invocation beyond the retained
launch receipts]`

The earlier post-repair census receipt also cannot attest `d03f0c6e6`: its script accepted a
caller-supplied `--git-head` and recorded the parent `7041a433e` while importing the dirty live
source. Its `353/353`, five-artifact, `32`-block and `3,781`-leaf arithmetic was independently
reproduced on the then-current tree, but its source-binding predicate is only
`consumer_asserted`. It is preserved as a non-receipt. A replacement census must resolve `HEAD`
internally, require a clean tree, bind the imported owner bytes to the committed blob, record a
complete sorted input manifest, and self-hash its receipt. `[P37: independently_reconciled for the
counts; consumer_asserted for the rejected receipt's source identity; not_established for the final
post-repair denominator until the source-bound rerun]`

The corrected contract separates two identities instead of weakening one:

1. `gy_content_hash` retains its pre-DEF14 meaning: it excludes only canonically named operational
   fields and continues to bind every retained verification block in full.
2. A versioned `comparison_content_hash` is opt-in. The scalar/list declaration only classifies a
   candidate block; exclusion additionally requires a caller-provided canonical owner to parse the
   exact typed projection and recompute its producer-owned `projection_hash`.
3. The runtime N9 owner admits only a strict, content-bound
   `N9PromotionCertificateProjection` whose authority provenance is `verification`. Depth-N's
   list-shaped summaries receive an exact owner scope and their own full projection hash; absent,
   empty, malformed, mixed-authority, unknown-scope, extra-field, or stale-hash summaries remain
   governing.
4. Reconciliation compares the versioned comparison identity, then preserves the already-frozen
   full verification block and recomputes the ordinary full artifact identity. The full block stays
   present, readable, and mutation-visible; the comparison identity never replaces the custody
   identity.

The protocol versions are `policyos.gy.comparison_projection.v1` and
`policyos.gy.non_authority_verification.v1`. This is the same §2 mechanism with its gate predicate
upgraded from declaration-supplied to producer-recomputed; it does not change promotion semantics,
ledger scope, a denominator, or an admission outcome. `[P37: recomputed for the implemented
owner-validation paths and full-hash counterfactuals; not_established for governed writer output
until the reviewed wave]`

The red-first sequence is retained: public comparison helpers were initially absent; strict N9
projection admission then failed until its self-hash validator existed; N10a failed on the old
two-argument field predicate and missing comparison bridge; Depth-N failed before its bound summary
owner existed. After correction, the focused receipts are green: the PDC/N9 selection passed
`15/15`; promotion plus generation comparison witnesses passed `2/2`; N10a plus Depth-N comparison
witnesses passed `2/2`; and the expanded generation/N10a/Depth reconciliation selection passed
`4/4`. Promotion and generation each validate two complete artifacts that differ only in a valid,
fresh verification projection and wall-clock-normalized content: their comparison hashes are equal,
their full hashes differ, and both validators pass. A coherently rehashed governing promotion-policy
mutation still fails with `scope_insufficient_promotion_policy_drift`. The N10a readback witness
keeps the full projection present and detects a stale full trace hash as
`artifact_content_hash_drift`; bare and unrecognized declarations remain comparison-bearing.
`[P37: recomputed]`

Two test expansions are non-receipts. The promotion module's historical assertion expects one
promotion row, while both the committed frozen artifact and a fresh current build contain two; the
repair changes projection validation, not row production, so the failing `1 == 2` expectation is
pre-existing test drift and is not rewritten here. A deliberately broader confidence-ledger unit
sweep later idled in the existing fork-based recovery test under a multithreaded pytest process;
after the relevant assertions had passed it was interrupted at the unbudgeted expansion boundary
and exited `2`. The focused strict-projection receipt remains green. `[P37: recomputed for the
frozen row denominator, current failure, focused receipts, and interrupt result; independently_reconciled
for non-intersection with row production; not_established for the uncompleted broad suite]`

### Source-bound census at the corrected freeze

The replacement census resolved clean `HEAD`
`e2f23c6eb4b72ac6541661dd61b278552c05947c` internally. It bound the loaded PDC owner, runtime N9
owner, and all five validator bridges to their committed blobs, recorded the CPython executable and
a sorted SHA-256 manifest for every input, parsed exactly `353/353`
`architecture/policy_design_case/*.json` files (`json=353`), and found no owner-admitted candidate in
an unbridged sixth artifact. Every one of the five existing full identities recomputed to its stored
value. `[P37: recomputed]`

Fail-closed admission corrects the earlier trial a second time. The current frozen set has `23`
already content-bound blocks and `3,721` scalar leaves: confidence `4/1,023`, Depth-N `10/1,564`,
generation `2/212`, promotion `3/210`, and N10a trace `4/712`. The nine legacy list-shaped Depth-N
summaries do not yet carry the new owner scope/hash and therefore remain governing; a list literal
does not admit itself. The canonical Depth summary owner deterministically adds exactly two fields
(`projection_scope`, `projection_hash`) to each of those nine blocks. The source-bound migration
projection therefore predicts the post-Depth-writer set as `32` blocks / `3,799` leaves, with
Depth-N `19/1,642` and comparison identity
`sha256:8c0274f08473c298828ba548b02977133821689256ac6708258397b109822494`.
This is B1: the difference from both `3,721` and the unsafe `3,781` trial is fully explained by the
§2 producer-admission contract, so the batch proceeds. `[P37: recomputed]`

The ignored bound receipts are `tmp/gy-defc-4/post-repair-census/census_bound.py` SHA-256
`196bfba96e0b32b8d89ed2269ddc338d711d35e3c94a846df0c0b0a734f44783`,
`summary-bound.json` SHA-256
`a80677a7c6cf028ae592c5104eaf8f38ac7e29458c0fd41045744418a397a43a`,
`input-manifest.jsonl` SHA-256
`39877a0338652bf98535acb992049c67fe797f0c9fea41e9c08b26b7a0a0bd36`,
`artifacts-bound.jsonl` SHA-256
`f6cfff8c5872ebf38c51e4b2e031c0d193a26eef6fd235069ba33305694e28d1`, and
`removed-leaves-bound.jsonl` SHA-256
`0b5ef1e188a41ba44116c8e97b951a1f38e295206ade40a00722fb0264a06ec6`.
The summary's canonical receipt hash is
`sha256:274de2fb40fc7dc5e81a08752e93c3e792114c1ae0911209621a25b5bfc4e644`.
`[P37: recomputed]`

### Producer-bound freeze candidate — superseding the self-hash design

The `e2f23c6e` census/design above is not the accepted admission design. A second frozen review
showed that an N9 DTO's strict shape plus its own recomputed `projection_hash` remained
self-attestation: an arbitrary coherent DTO could author both the values and the hash that made it
non-decisive. The nine Depth summaries had the same defect because their proposed parent proof was
only another self-computed summary hash. The `32/3,799` forecast is therefore retained as a rejected
structural upper-bound, with its admission predicate `not_established`; it is not a reissue
denominator. No governed writer ran under that design. `[P37: independently_reconciled for the P32
finding; not_established for the rejected admission forecast; recomputed only for the present
governed-artifact diff, which remains empty]`

The corrected admission unit is the complete `CanonicalPromotionReceipt`, never its detached N9
projection. While the isolated verification session is live, the N9 owner strict-parses the complete
receipt and runs the existing receipt verifier against that exact session, registry, candidate,
design problem and value receipt. Only that successful replay mints an ephemeral admission token,
bound to the exact raw full-receipt content hash and to an owner-defined typed semantic projection.
The plan binds each token to exactly one derived JSON path; copied bytes consume no second token,
duplicate paths fail closed, and a persisted path manifest is explicitly an integrity recipe rather
than authority. A manifest cannot mint an admission or select a new path because the registered
typed projector must still parse the aligned complete receipt. `[P37: recomputed]`

The owner-defined semantic projection removes only the verification session's ledger namespace and
the hashes/references mechanically derived from it: deployment/scope/root/head/receipt locators,
N9 row execution/check/binding identities, receipt/trace ledger locators, and the matching N11 risk
references. It retains the complete owner projection semantics, candidate, obligation statuses and
reasons, risk amounts and budget outcome, refusal reasons, promotion lane, consumer outcome,
computed authority boundary, non-ledger derivation facts, value method, and sequence reference. The
ordinary full receipt remains recorded byte-for-byte and its ordinary model/self-hash validators run
before projection. Reconciliation preserves that complete frozen receipt only when the old and live
typed semantic projections are exactly equal. Depth's nine list-shaped summaries are excluded only
after every complete parent receipt was live-validated; their old and live complete summary values
must also be equal before frozen bytes are retained. `[P37: recomputed]`

This realizes the §2 declaration contract without trusting the declaration. Scalar and list forms
are classified identically: every direct provenance must be the recognized non-authority value
`verification`; absent, empty, malformed, unrecognized, or mixed authority stays governing. The
classification alone never changes `gy_content_hash`. It only routes an already producer-validated
full receipt or parent-bound summary into the opt-in comparison plan. The rule version is now
`policyos.gy.non_authority_verification.v2`. `[P37: recomputed]`

Confidence-ledger remains the B3-blocked fifth member and receives no exclusion plan. Its four narrow
projections remain fully governing, and its writer emits no comparison metadata; the old frozen N11
artifact currently also fails its newer schema on missing
`owner_bundle_projection.consumed_inputs`, independently confirming that it has no clean baseline to
reissue in this batch. The post-freeze census must therefore measure the four-member batch, not the
earlier five-member trial. The structural forecast pending that source-bound walk is promotion
`3/210`, generation cycle `2/212`, N10a `4/712`, and Depth `19/1,624`: four artifacts, `28` admitted
blocks, `2,758` scalar leaves. The nine Depth summaries add `9/60` to its ten complete-receipt blocks;
no synthetic `projection_scope` or `projection_hash` leaf is added. `[P37: independently_reconciled
for the structural forecast; not_established until the clean committed census; institutionally_supplied
for the B3 recut]`

The focused pre-freeze invocation exercised `57` tests and exited `0` in `116.055869` s. It includes
the scalar/list and fail-closed declaration matrix, exact-token/copy/manifest adversaries, full
frozen/live receipt reconciliation, a coherent self-rehashed detached N9 rejection with
`confidence_ledger_projection_drift`, a governing-denominator red witness, Depth operational and
summary reconciliation, and the N10a bare-declaration bridge. Stdout SHA-256 is
`5603b3bdbd979d86e8c62be43291039331c1f18d392c470cba56f4eba489b84d`; stderr is empty with SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. The retained metadata is
`tmp/gy-defc-4/source-tests/pre-freeze.meta.json`. `[P37: recomputed]`

Additional non-receipts are preserved. A direct promotion probe first used the receipt interpreter
without current-source `PYTHONPATH` precedence and exited `1` on an import from the path-witness
checkout; the corrected diagnostic was read-only. A broad N10a unit expansion built one complete
live bundle and passed its first real-owner test, then remained CPU-heavy in the next test; it was
interrupted with `SIGINT` and exited `2` rather than spending an unbudgeted full-module wave. It
wrote no governed artifact, and the current changed-path set has no architecture JSON. Two direct
confidence frozen-payload diagnostics both returned the same B3 schema failure above and are not
writer receipts. `[P37: recomputed for the terminal codes and present changed-path intersection;
not_established for unretained launch timing/details]`

### Frozen-review correction — owner policy and the five-output boundary

The `207069dae` freeze is also rejected as an implementation receipt. Independent frozen review
found that its persisted comparison manifest could change an owner-admitted receipt from `project`
to `exclude`: frozen verification reconstructed the caller-supplied action instead of checking it
against the producer's rule. The same manifest omitted the P37 class that had admitted the predicate.
Changing `action` and recomputing the artifact identities could therefore hide governing semantic
content without a new live owner admission. This is a P32/P37 authority leak, not an artifact-delta
question, and it was found before any posture gate, governed writer, accepted reissue, or cold N11
launch under that freeze. `[P37: independently_reconciled for the authority finding; recomputed for
the current zero governed-artifact diff; not_established for historical non-invocation except where
retained launch receipts exist]`

The correction makes a comparison owner rule a three-part runtime policy: typed projector, sole
allowed action, and frozen predicate-provenance class. The canonical full-promotion-receipt rule is
`project` / `recomputed`; the Depth summary rule is `exclude` /
`independently_reconciled`. A persisted row must equal that registered policy exactly. The negative
witness changes a legitimate manifest first to `exclude` and then to a stronger provenance class;
both fail with `gy_comparison_admission_manifest_owner_policy_mismatch`. The artifact remains an
integrity recipe and cannot choose its authority effect. `[P37: recomputed]`

The promotion owner projection is now schema-bound rather than an unguarded series of dictionary
edits. It starts from each complete strict typed model and removes only an explicit lineage partition
whose fields must belong to that model; every field outside the partition is retained, so a newly
added field is governing by default. The same rule is applied to the full receipt, owner projection,
N9 certificate, every N9 row, every N11 risk-spend record, and the authority trace. Strict extra-field
validation plus the retained-field-set witness closes the structural default. `[P37: recomputed]`

Frozen review also found that N10a's canonical write call serialized five files while only the cycle
trace had a legacy transition owner. The corrected write boundary validates the old and live
self-identities of all five paths before the first write, requires census and smoke-problem semantic
identity to remain equal, names the cycle trace as producer-comparison-reconciled, names pack and
gaps explicitly as live rederived dependents, and returns the complete changed-scalar pointer set for
every member. The five-path denominator and stale-old-hash rejection are behavioral tests. Pack and
gaps are not silently called reconciled: their returned leaf sets remain subject to the journal's
predeclared-delta equality gate and exact-byte restore on any rejection. `[P37: recomputed for the
implemented pre-write accounting; not_established for candidate/accepted output until the reviewed
wave]`

The first `57`-test green receipt predates commit `207069dae` and its metadata did not bind either a
Git head or source-byte manifest. It is retained only as an iteration witness and is not evidence for
any frozen source. The ordinary-interpreter Depth collection still fails its repository-interpreter
preflight; rerunning the new parent-summary negative witness with the pre-existing required
path-witness interpreter and current `PYTHONPATH` precedence passed `1/1`. No environment was rebuilt.
`[P37: recomputed for the retained timestamps/preflight code and focused terminal; not_established
for a source-bound full focused suite until the next clean committed run]`

The first correction freeze, `ae3d713d4`, closed old/live self-hash accounting for all five N10a
outputs but still only *described* the Pack and gap deltas: the returned transition list was not an
input to `write()`. Frozen review correctly rejected that label-only boundary before a governed
writer. The canonical N10a bridge now has a two-step protocol. `--measure-write-transition` builds
and validates the complete candidate without writing, returning a strict five-row manifest bound to
the source head, old/new identities, mode, and every sorted changed scalar pointer. A writer action
requires that exact self-hashed manifest; any path, mode, source head, identity, leaf, count, ordering,
or manifest-hash mismatch raises before the first output write. The behavioral witness proves that a
forged Pack leaf blocks the actual writer and leaves all five prior bytes unchanged, then proves the
exact measured manifest admits the same candidate. `[P37: recomputed for the executable pre-write
gate and witness; not_established for the real candidate manifest until the reviewed measurement]`

The five-file write loop is still not transactionally atomic across filesystem replacements. The
wave therefore retains the external exact-byte snapshot/restore group: a nonzero exit, missing
receipt, unexpected post-write diff, or failed verification preserves the candidate bytes as an
ignored non-receipt, restores all five old byte strings, and rehashes the restored denominator.
That recovery boundary is operational protection, not a substitute for the pre-write semantic gate.
`[P37: recomputed for the current sequential writer implementation; not_established for recovery
until exercised or the accepted write completes without needing it]`

The second delta review tightened two protocol edges before the wave. Measurement and persistence
now both reject any tracked or untracked change under `src/polisyos/**` or `tools/**`; the manifest
also binds a canonical SHA-256 over every non-bytecode file in those two complete source scopes, in
addition to `HEAD`. A journal-only expected-delta declaration may therefore remain uncommitted for
the accepted write without weakening source binding, while a same-HEAD dirty source cannot measure
or persist. The capture variants are modifiers of the same measurement action, so both live-N4
capture and a supplied capture journal can obtain the exact candidate manifest their corresponding
writer must present. Focused witnesses cover dirty-source refusal and both public measurement routes.
`[P37: recomputed]`

### Final reviewed freeze and source-bound census

The final source freeze is `708d18d6b3bc4bc2380ff896c503ecdd2d4cdaf6`. Three independent
Terra review tracks covered the producer predicate/typed partition, P35/P37 and timing boundary, and
the writer/wave boundary. Their final delta passes reported no Critical or Important findings. No
governed artifact was changed during the source-review chain. `[P37: independently_reconciled for
the review verdicts; recomputed for the frozen head and current governed-artifact diff]`

The clean, source-bound census parsed the complete
`architecture/policy_design_case/*.json` set: path denominator `353`, file-type denominator
`json=353`, parse denominator `353/353`. It reproduced all five stored legacy identities and bound
the committed/live bytes for the PDC owner, confidence-ledger runtime owner and validator, promotion
owner, and the four reissue producers. Confidence has no comparison plan and remains the
B3/governing artifact. The structural batch is exactly four artifacts and `28` plan entries:

- promotion: `3` entries / `93` changed comparison leaves;
- generation cycle: `2` / `70`;
- N10a cycle trace: `4` / `204`; and
- Depth-N: `19` / `522`.

Total: `889` actually removed or changed scalar comparison leaves. This supersedes the rejected
`2,758` full-block forecast. The correction is explained by the §2 mechanism: complete typed
receipts stay recorded, while the owner projection retains governing semantics and removes only
session lineage; the nine independently reconciled Depth summaries are the only full-block
exclusions. It is B1, not the unexplained-movement stop. Live verification-session admission is
still `not_established` until each writer produces its ephemeral plan. `[P37: recomputed for the
353-byte denominator and legacy identities; independently_reconciled for the structural paths and
889-leaf projection; not_established for live writer admission; institutionally_supplied for B3]`

The ignored census receipt is under `tmp/gy-defc-4/post-repair-census/final-708d18d6b/`.
Its canonical receipt identity is
`sha256:0ab017748415bdb72071f8f9f056219fd609c4d6e8b09398d740e229e017c94f`;
the script SHA-256 is `bc24c0707c3268f42b0bcc6b14c1ba507b32cc3618628172e5085aa87661bbf7`,
artifact rows `3530fe25769ed0629f03b2dd1ecc97f4874af5010dec580f4be7ca908f17b47a`,
comparison leaves `0580de1574bdd12ccf3424e8ef48c1112db715aff629439826070923cfba7106`,
and the complete input manifest
`39877a0338652bf98535acb992049c67fe797f0c9fea41e9c08b26b7a0a0bd36`.
`[P37: recomputed]`

The frozen-source witnesses then passed `53/53` under the ordinary interpreter in `102.815026` s
and `2/2` Depth summary/parent negatives under the pre-existing required path-witness interpreter in
`14.685505` s, both with current-source `PYTHONPATH` precedence, exit `0`, no timeout and empty
stderr. Their stdout SHA-256 values are respectively
`3bf5ea7c2adce2a8def4d6995c21f699dd10c4eed53d65d3beca9cf0b2731e93` and
`99db33d5c94c6f7da021687c7391181685cc33299c5435b1c861e2db3be3ec87`.
The separate interpreter is demanded by the Depth preflight; the earlier ordinary-interpreter
collection error remains a setup non-receipt, and no environment was rebuilt. `[P37: recomputed]`

The final timing report read `121` complete local records. Governing caps remain: promotion
write/check `32,437.008/33,650.354` ms; generation write/check/rederive
`56,250.878/85,542.132/50,721.146` ms; N10a write/check/rederive
`852,699.146/74,272.168/726,805.376` ms; Depth write/check/rederive
`4,942,540.412/319,661.388/1,695,177.568` ms; and posture
`227,856.150` ms. The corrupt lanes retain declared hang fences of `300` s for promotion,
generation and N10a and `600` s for Depth; those are not catalog budgets. `[P37: recomputed for the
timing-log/catalog projection; institutionally_supplied for the declared corrupt ceilings]`

### Promotion — declared accepted delta (written before the accepted writer)

The promotion measurement completed in `27.394866` s under its `32.437008` s cap, exit `0`, then
the exact old bytes were restored and re-read at SHA-256
`03479f68e1babc404f2ae8081ab780f1ca2c6c118dd9b11f61ee4be9310f51fe`. The preserved candidate
is SHA-256 `89694280769f8917835c84d5624c2be4be976df066ee1f844ade7acdc402e01b`.
The accepted reissue is declared to move exactly these `21` scalar leaves and no others:

- `$.comparison_admission_manifest[{0,1,2}].{action,json_pointer,owner_rule,predicate_provenance}`
  (`12` leaves);
- `$.comparison_content_hash`, `$.comparison_projection_schema_version`,
  `$.comparison_rule_version`, and `$.contract_content_hash` (`4` leaves); and
- `$.behavioral_mutations[0].issue_codes[0]`,
  `$.behavioral_mutations[2].issue_codes[0]`,
  `$.behavioral_mutations[2].issue_codes[1]` (removed),
  `$.behavioral_mutations[3].issue_codes[0]`, and
  `$.behavioral_mutations[5].issue_codes[0]` (`5` leaves).

The five diagnostic leaves are mechanically produced by the new owner comparison gate: mutations
that invalidate an admitted full receipt now stop at `comparison_projection_rejected_mutation`
instead of falling through to the older downstream code. Every mutation remains `red`; promotion,
consumer-promotability, obligation, risk-budget, denominator, scope and admission outcomes are
byte-identical. No proof input or transport field moves. The accept predicate is exact equality with
the `21`-leaf set above. `[P37: recomputed for the measured bytes, leaf set and unchanged outcome
counterfactuals; not_established for accepted persistence until the writer and verifications close]`

The accepted writer then persisted the byte-identical candidate at SHA-256
`89694280769f8917835c84d5624c2be4be976df066ee1f844ade7acdc402e01b` in `27.541650` s,
exit `0`, under the `32.437008` s cap. Its recursive scalar delta is exactly the declared `21/21`
leaves, with no missing or additional pointer. Independent review reconciled the five diagnostic
movements against the mutation harness: all seven mutations remain red, while five now fail earlier
at the owner comparison-admission boundary; all three canonical promotion receipts retain the same
`shadow`/not-promoted outcome, obligations, refusal state and zero risk spend. `[P37: recomputed for
the bytes and exact leaf equality; independently_reconciled for the diagnostic-precedence and
unchanged-governed-outcome classification]`

The canonical `--check` passed with no issues in `27.567455` s, and `--rederive-audit` passed with
no issues in `27.356987` s. The corrupt-field lane completed in `11.810165` s under its declared
`300` s hang ceiling and exited `1`, its contract-defined healthy terminal, with
`corrupt_field_drift_detected` present. This validator does not emit a `missing` member; its green
predicate is the detected corruption plus exit `1`, not an invented empty field. All four stderr
streams are empty. The accepted promotion reissue is therefore closed. `[P37: recomputed]`

### Generation cycle — declared accepted delta (written before the accepted writer)

The generation-cycle measurement completed in `39.353171` s under its `56.250878` s cap, exit
`0`, with empty stderr. The exact preimage was restored and re-read at SHA-256
`37abd82bb64926ca392734baf8bacec1a3c3fe559ff26bfd88f230148d4e8675`; the preserved candidate is
SHA-256 `6538e879e5152b919190f31e4b973a035a2e95f575fa3e53f1b5b885c99cc344`. One first attempt to
invoke the ignored leaf-diff helper omitted its required output-path argument and raised before
diffing or restoring; the candidate had already been copied, the corrected invocation produced the
receipt below, and the preimage was then restored byte-for-byte. That helper error is an operational
non-receipt, not a writer result. `[P37: recomputed]`

The accepted reissue is declared to move exactly these `12` scalar leaves and no others:

- `$.comparison_admission_manifest[{0,1}].{action,json_pointer,owner_rule,predicate_provenance}`
  (`8` leaves), where the pointers are respectively
  `/generation_cycle_run/promotion_port/receipts/0` and `/generation_cycle_run/promotion_port/receipts/1`,
  both actions are `project`, both predicate classes are `recomputed`, and both owner rules are
  `polisyos.runtime.quality.promotion_sequence.canonical_promotion_receipt_verification_projection.v1`;
- `$.comparison_content_hash`, `$.comparison_projection_schema_version`, and
  `$.comparison_rule_version` (`3` leaves); and
- `$.contract_content_hash` (`1` dependent leaf).

The complete recursive measurement contains exactly those `12` pointers. Both embedded receipts
remain byte-retained and keep their `shadow`, not-promoted, grounded-abstention, unresolved and
non-consumer-promotable semantics. The positive gate, denominators, fail-closed probes, strangle
state, cycle/front disposition and all `12` behavioral mutation results are byte-identical; there is
no diagnostic-precedence movement. The accept predicate is exact equality with the declared set.
`[P37: recomputed for the measured bytes, exact pointer set and unchanged governing outcomes;
independently_reconciled for the owner-admission classification; not_established for accepted
persistence until the writer and verifications close]`

The accepted generation writer persisted the byte-identical candidate at SHA-256
`6538e879e5152b919190f31e4b973a035a2e95f575fa3e53f1b5b885c99cc344` in `39.428779` s,
exit `0`, under the `56.250878` s cap. The recursive scalar delta is exactly the declared `12/12`
pointers, with no missing or additional leaf. `--check` passed with no issues in `39.391251` s,
and `--rederive-audit` passed with no issues in `39.264501` s. `[P37: recomputed]`

The generation corrupt-field lane completed in `11.803721` s under its declared `300` s hang
ceiling and exited `1`, its contract-defined healthy terminal. It reported
`corrupt_field_drift_detected` and named the expected comparison/content and typed cycle-binding
failures; no mutation survived. All four accepted-run stderr streams are empty. The generation-cycle
reissue is therefore closed. `[P37: recomputed]`

### N10a five-output transition — declared accepted delta (written before the accepted writer)

The non-persisting `--measure-write-transition` action completed with exit `0` in `361.136236` s
under the `852.699146` s cap; its validator wall time was `348.636292` s, its issue set is empty,
and `write_performed` is false. All five canonical output SHA-256 values and the external N8 value
gate contract SHA-256 remained byte-identical to the preimage. The raw stdout includes ordinary
method-registration logging before the final JSON; both the raw stream and the extracted final JSON
are retained. `[P37: recomputed]`

The strict transition manifest is bound to source head
`482c204d957b9537b0db9869faebd2d49dd64a7c`, source/tool-scope identity
`sha256:c3baaf297d763e951f7c7bf6eb44b785c8bff46ba5164d6fb7dd7f4f45a92c35`, and manifest identity
`sha256:7bacae62f93c61f300782249c31187e1fca9dcc7637f19408ecc25a42d1cf4b3`. The accepted writer is
declared to move exactly the following `36` scalar leaves, partitioned over the complete five-output
denominator, and no others:

- `layer3_gy_second_domain_census.json`: `0` leaves; legacy/live content identity is exactly
  `sha256:fb98cc5070e919a140d544c75a640a809d3bcc0bbdc1808b6129ffc8de0cfd0d`.
- `layer3_gy_second_domain_pack.json`: `/cycle_trace_content_hash`,
  `/gap_report_content_hash`, and `/manifest_content_hash` (`3` dependent leaves); legacy/live
  identities are respectively `sha256:2dce1555a6d1eab8e3303f1c86ac6ef3509da9199a308abe230ec1b5fc6251c7`
  and `sha256:a1953ae6a034666600c8f3f3722138fd1348f1133850867615f2c92a2c8e0466`.
- `layer3_gy_second_domain_smoke_design_problem.json`: `0` leaves; legacy/live identity is exactly
  `sha256:d40e3fe557d6d287e549e3a7f0373e2052fd137ae9ce56ba75e9c29c73f770e5`.
- `layer3_gy_second_domain_cycle_entry_trace.json`: the `16` leaves
  `/comparison_admission_manifest/{0,1,2,3}/{action,json_pointer,owner_rule,predicate_provenance}`;
  `/comparison_content_hash`; `/comparison_projection_schema_version`; `/comparison_rule_version`;
  `/gap_triage/5/receipt_ref`; `/gap_triage/6/receipt_ref`;
  `/generation_cycle_run/cycles/0/acquisition_routing_report/generated_at`;
  `/runtime_metrics/aggregate_value_port_wall_time_ms`;
  `/runtime_metrics/cycle_value_port_wall_time_ms/0/value_port_wall_time_ms`; and
  `/trace_content_hash` (`25` leaves total). Its legacy/live identities are respectively
  `sha256:f9be282f0b16720d38440572aeecfc9c47f2566407fa5a68a8402796ef250430` and
  `sha256:83134ef46ed29411bbb4dfa776506f9eec8929a74e3db60810175eabb2dfe2b3`.
- `layer3_gy_second_domain_free_grow_gaps.json`: `/gap_report_content_hash`;
  `/gaps/5/gap_content_hash`;
  `/gaps/5/owner_evidence/stage_2_behavioral_receipt/receipt_ref`;
  `/gaps/5/owner_evidence/stage_2_behavioral_receipt/value_contract_content_hash`;
  `/gaps/6/gap_content_hash`;
  `/gaps/6/owner_evidence/stage_3_behavioral_receipt/receipt_ref`;
  `/gaps/6/owner_evidence/stage_3_behavioral_receipt/run_content_hash`; and
  `/gaps/6/owner_evidence/trace_content_hash` (`8` leaves). Its legacy/live identities are
  respectively `sha256:fe1607f0c29460200df8fa236445d274e4c218683cfe3c50806e8328c5fd0c85`
  and `sha256:34ad1cbf926434a8ab7d91a6b6029304013aeb05377024e0e21dc122aa260e92`.

The N8 content-identity cascade and the four producer-bound comparison admissions explain the
semantic movement. The three clock/runtime leaves remain recorded but are excluded operational
values; the dependent hashes and receipt refs close over those two sources. The complete manifest
names no governed denominator, comparison/admission outcome, transport covariate, N8 proof hash, or
`ambient_discovery.manifest_id`/`provenance_id`, and the census/smoke identities are exact. The
accept predicate is byte-for-byte equality with this source-bound manifest; any different pointer,
count, identity, mode or manifest hash blocks before the first write. `[P37: recomputed for the
source-bound manifest, unchanged preimage denominator and negative changed-path intersection;
independently_reconciled for the N8/comparison-owner causal classification; not_established for
accepted persistence until the gated writer and verifications close]`

The gated accepted writer completed with exit `0` in `352.215048` s under the `852.699146` s cap;
its validator wall time was `338.964431` s and its issue set is empty. The writer returned the exact
measured manifest identity, source head and source-scope identity, with `write_performed: true`.
Independent recursive readback reproduced the declared `0/3/0/25/8` leaf partition exactly, with no
missing or additional pointer. The two zero-delta files remain byte-identical; the accepted byte
SHA-256 values are census `ba20cdb384eb3e00fb6f13b2fad0b6f679f6fd4debc1148e4fe39a567055e74c`,
pack `9b67629da3d141aaae3e9cd3ae0b392b227f8680c5699bd6295fe44412965441`, smoke
`688bd3d8c845ebe99495aecb3b2c10579dbf3f43dd5e8fe0a6686cc6e8b5f76d`, cycle trace
`47a656292885dccddcdea850686ebcfa7d035df3a4d71dc66880a282f22e09f4`, and gaps
`496944b5443784e1cc43cec3d54c02e561d52970650703f18873f0d12fd74941`. The external N8 artifact
remains byte-identical at `c3f131ce4f4729936eb3a639cfc81d5d65edb6545b2562d415f64998331bc303`.
The accept decision is **accept**. `[P37: recomputed]`

The canonical `--check` passed with no issues in `23.402522` s under its `74.272168` s cap. The live
`--rederive-audit` passed with no issues in `358.791583` s under its `726.805376` s cap and reproduced
the frozen N7 capture metadata. The writer and rederive stderr each contain only the two expected
database-connection log lines; check and corrupt stderr are empty. `[P37: recomputed]`

The corrupt-field lane completed in `28.531551` s under its declared `300` s hang ceiling and exited
`1`, its contract-defined healthy terminal. Its first issue is `corrupt_field_drift_detected`; all
five cycle-substrate mutations and both smoke-terminal mutations have nonempty detected-code sets.
This validator emits no `missing` member, so the read result is `missing=null` rather than an
invented empty list; the complete enumerated mutation denominator is detected. The N10a reissue and
its three verification receipts are therefore closed. `[P37: recomputed]`

### Depth-N measurement — semantic stop before an accepted reissue

The canonical Depth-N writer was launched once with the isolation-local `.venv/bin/python`, current-checkout
`PYTHONPATH`, `JAX_PLATFORMS=cpu`, and `PYTHONDONTWRITEBYTECODE=1`. It reached its own terminal in
`873.977626` s under the recomputed `4,942.540412` s cap; the harness did not time out, both child
and wrapper exited `1`, launch error is null, and stderr is empty. Stdout SHA-256 is
`e4bb68a29a12859ae10214b4b7f5b66bb05e50a613493fff2ba49e8518e7d0ea`, metadata SHA-256 is
`dd89ee4336dc92bd58107d5bed031758a054aa95e5a1a96720859db4f4c1db0d`, and empty stderr SHA-256 is
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. The orchestration transcript
placed the launch after the `d15681e5d68e7a1ae28556b45185338e684cecdd` landing and a clean status
read, but the retained harness metadata carries neither Git head/status nor a source-scope manifest;
launch-time source binding is therefore not elevated from that transcript. `[P37: recomputed for
the retained command/environment/timing/terminal; consumer_asserted for transcript ordering;
not_established for immutable launch-source binding]`

The writer stopped before persistence. The complete one-file governed denominator is
`1/1` JSON artifact, `1,841,810` bytes before and after, SHA-256
`acc252579bb92ec1fcc7899ea73cf22a41154ceb68d249c135bca457a153f089` on both sides; the recursive
delta contains `0` leaves. Thus this is a completed semantic rejection/non-receipt, not a timeout,
partial write or accepted Depth reissue. The accepted Depth allowance and the one cold-N11 allowance
remain unused. `[P37: recomputed for the byte boundary and terminal; institutionally_supplied for
the allowance semantics]`

The sole issue is `authority_source_controlled_replay_recording_drift`. The safe DEFC-2 diagnostic
names `recording_role=first_vertical`, `admission_arm=migrated`, expected-frozen identity
`sha256:5be394e2308b33fb9b4907446a54858d11c29be3cabf9cf93bce9d8a06855bdb`, and live-replayed identity
`sha256:655922817cfb98503b1d001a0f3db3edb516f5d5e19cb5a310aed648e08d384c`.
Its complete changed-leaf denominator is `84`: `5` ordinary operational clock leaves and `79`
reported semantic leaves. Of those `79`, `75` are verification-session N9 lineage/check/risk-spend
identities; the remaining four are the enclosing `/compiled_run/content_hash`,
`/compiled_run/recursive_run/content_hash`, `/compiled_run_content_hash`, and
`/recording_content_hash`. Only identity digests, presence, type and paths are retained; no raw
operand value is recorded here. The extracted diagnostic SHA-256 is
`7fd23245404d1caf23088b9c09abb0569191463ab550b2704f7ab4be397a065f`. `[P37: recomputed]`

This failure is upstream of the repaired artifact comparison plan. The source would construct an
outer plan from producer-bound admissions for `10` full canonical promotion receipts and `9`
parent-bound summaries only after all three roles complete. This failed execution minted the live
receipt admissions for its first (`first_vertical`) role, then `_domain_run_and_normalized_recording`
compared that entire controlled recording through `reconcile_gy_operational_leaves` and demanded
exact equality; it never completed the three-role loop, summary admissions or final `19`-entry plan.
That generic comparator owns only field-name operational exclusion; it never consumes the live
session/candidate-bound N9 admissions that the same function has just derived. Consequently it sees
legitimate verification-session lineage as governing, and the enclosing self-identities follow.
Independent frozen review reproduced this ordering and classified the inner controlled-recording
comparison as a second bespoke bridge rather than the already-authorized outer §2 artifact plan.
`[P37: independently_reconciled]`

The smallest correct closure is described, not performed: create a typed recording-level comparison
admission only after strict recording/schema/role validation, full compiled-run validation, and
successful session/candidate-bound admission of every nested canonical promotion receipt. Its
structural projector must delegate nested receipts to the canonical promotion semantic owner,
retain every governing typed field, remove only typed enclosing self-identities plus ordinary
operational fields from the comparison, and preserve the full frozen recording bytes when the
projection is equal. A governed outcome change must fail; a self-rehashed or bare
`authority_provenance=verification` mapping must not mint admission; an unknown typed field must
remain governing or fail validation. No reported leaf-name whitelist, global exit widening,
placeholder normalization, scope weakening or second ledger is acceptable. `[P37: independently_reconciled
for the closure shape; not_established until a separately authorized implementation and witnesses]`

This is the prompt's genuine §6(b) boundary: it needs a second comparison mechanism beyond §2.
Accordingly no source byte was changed after this finding, no replacement Depth
measurement/check/rederive/corrupt lane
was launched, the posture gate was not reached, and the one cold N11 was not launched. The objective
“a cold owner derivation reaches `owner_bundle_loaded`” therefore remains `not_established` in this
wave. `[P37: institutionally_supplied for the stop boundary; recomputed for the current changed-path
set and retained launch receipts; not_established for Depth acceptance, posture and the cold-N11
outcome]`

The retained non-receipt boundary is
`tmp/gy-defc-4/wave/depth/measurement/{before,after,delta.jsonl,write.meta.json,write.stdout.log,write.stderr,comparator-diagnostic.json}`.
Three Terra tracks, and no Sol track, covered the predicate/authority classification,
P35/P37 and timing boundary, and serialized wave/fence. Root alone performed source writes and all
writer-class processes; review tracks were read-only. Their final messages reported no further
predicate or journal blocker after the corrections above, but those messages are not bound as
repository review receipts. `[P37: consumer_asserted for dispatch identity, execution ownership and
review verdicts; not_established for repository-bound independent review receipts]`

The final architecture guardrail ran under the retained `180` s cap and reached its known negative
terminal: exit `1` in `43.703427` s, no timeout, empty stderr, and `5,081` stdout bytes at SHA-256
`73b53d0a9278bcb2acffbac62e925e6ca30ce40caeb0b3588ce5323dfd1559fb`—the same stdout identity as
the prior retained negative. It names only `architecture/baselines/imports/deep_import.json` and the
five pre-existing runtime paths `execution_policy.py`, `routes/runs.py`, `channel_contracts.py`,
`lex_pipeline.py`, and `lex_search_projection.py`. The complete task delta from `c1a89b6cf` has
`27` paths; its exact intersection with those six guardrail paths is empty. The baseline was not
synchronized. Changed-path receipt SHA-256 is
`ebe3eced3200c92e607e994055a1a964d8c01abdc21d117ce3d734aaa3edd29a`. `[P37: recomputed for the
guardrail terminal, complete changed-path denominator and empty intersection; independently_reconciled
for its pre-existing/unrelated classification]`

## GY-DEFC-5 — recording-level comparison owner

This continuation started on attached branch `codex/gy-defc-3-retry`, clean at
`ba18ad7d72236e67a0b8a0f86deb7af03a751920`, exactly `20` commits ahead of
`c1a89b6cf`. The existing worktree is linked and isolated; the unrelated edit in the main
checkout's `src/polisyos/data_forge/read_api/catalog.py` is absent from this worktree's tracked
delta. The session-start timing projection parsed `138` complete records and recomputed Depth-N's
writer/check/rederive ceilings as `4,942.540412` s, `319.661388` s and `1,695.177568` s. The
confidence-ledger writer still has no successful local sample; its catalog fallback is not converted
into a successful-run claim. `[P37: recomputed]`

### Confidence-ledger re-probe — B3 remains selected

Before any source change, the canonical confidence-ledger writer was re-probed against an ignored
scratch output under the task's declared `1,800` s fence. It ran alone with CPython `3.14.0` from
the receipt environment, current-checkout source first in `PYTHONPATH`, `JAX_PLATFORMS=cpu`,
`PYTHONDONTWRITEBYTECODE=1`, and explicit catalog/L5 inputs. The wrapper captured the attached
branch, clean tracked status and `ba18ad7d7…` head both before and after launch. The catalog was
`1,320,693,760` bytes at SHA-256 `4a1eab13…960dd7`, L5 was `2,112` bytes at
`90f341b2…87aff`, and the confidence registry was `f337fc1e…f49942b`. `[P37: recomputed]`

The probe reached its own fail terminal in `76.560691` s without timeout: child/wrapper exit `1`,
`process_group_clean=true`, `byte_stable_passes=0`, `second_pass_started=false`, and first
derivation wall time `47.079297` s. It emitted milestones through
`n10_owner_recomputation_started`, then raised `OwnerProjectionError` with the exact chain
`n10_capstone_invalid -> {comparison_projection_schema_version_invalid,
comparison_rule_version_invalid, comparison_admission_manifest_invalid
(gy_comparison_admission_manifest_invalid)}`. Unlike the pre-N10a probe, this is not
`n8_transport_gap_receipt_drift`; that stale receipt boundary is absent. `[P37: recomputed]`

No scratch candidate was produced. The governed confidence artifact stayed `108,740` bytes at
SHA-256 `a844a0c3…4781`; the N10a pack, cycle trace and gaps stayed respectively
`9b67629d…5441`, `47a65629…09f4` and `496944b5…4941`; every explicit input pin also stayed
byte-identical. The retained receipts are
`tmp/gy-defc-5/confidence-probe/{probe.meta.json,probe.stdout,probe.stderr,terminal.json}` at
SHA-256 `713899ff…c5aa`, `3518c300…8dfe`, `9e4f3725…f5fc` and
`5eff1b5b…337d`. `[P37: recomputed]`

This selects pre-authorized B3: the confidence-ledger member remains blocked, now on its stored N10
capstone validator not accepting the reissued comparison schema/rule/manifest. That validator is a
different owner from the authorized controlled-recording comparator, so it is described and not
repaired here; the batch proceeds with Depth alone. The probe is a measurement/non-receipt and
consumes no accepted confidence reissue. `[P37: institutionally_supplied for B3 and allowance
semantics; recomputed for the observed failure/byte boundary; independently_reconciled for the
different-owner classification]`

### Recording-level comparison contract — frozen before source work

The ordinary recording custody identity remains unchanged: it hashes and retains every serialized
byte, including verification-session lineage, enclosing identities and operational clocks. A second,
versioned comparison identity is opt-in and exists only for controlled replay. It may be minted only
after the canonical recording owner validates the complete recording and the canonical promotion
owner resolves every nested receipt against the live verification session and candidate/value
bindings. A field, manifest action, declaration, shape or self-recomputed hash cannot mint
admission. The deciding predicate is frozen as `recomputed` in an ephemeral admission before the
comparison begins. `[P37: institutionally_supplied for the contract; not_established until the
behavioral witnesses close]`

The comparison projection is structural and producer-owned:

1. Strictly validate the recording schema/version, role, top-level-to-compiled-run identity links,
   the complete compiled recursive run, and the exact nested-receipt denominator.
2. Require one live session/candidate-bound canonical admission for every nested promotion receipt;
   a missing, extra, duplicated, mismatched or forged admission fails closed.
3. Delegate each admitted receipt to the canonical promotion semantic projection already used by
   the artifact layer. Remove only the typed verification-session lineage and typed enclosing
   identities that derive solely from it, plus the existing ordinary operational fields.
4. Preserve every governing typed field. An absent, malformed, mixed or unrecognized declaration,
   an unknown field, or a bare `authority_provenance=verification` mapping remains governing or
   fails strict validation; it is never excluded.
5. If and only if the two admitted comparison projections are equal, return the frozen raw recording
   byte-for-byte. The comparison plan never substitutes live bytes into custody evidence and never
   deletes, truncates or placeholder-normalizes a recorded block.

The inner controlled-recording replay and the outer Depth artifact comparison must route through the
same root recording admission so a child-receipt bypass cannot survive (`P31`). The existing
identity-only DEFC-2 diagnostic remains the red surface for semantic mismatch; raw values remain
absent. Ledger scope identity, per-problem scope semantics and the confidence ledger itself are not
changed. `[P37: institutionally_supplied for the positive/forbidden contract;
independently_reconciled for the one-chokepoint placement; not_established for implementation]`

Five red-first acceptance witnesses bind the repair:

- two otherwise identical recordings whose clocks and producer-admitted verification-session
  lineage differ reconcile to the same comparison identity, both admit, and the returned recording
  is the exact frozen raw object;
- a genuinely governing input change remains red with its named controlled-recording drift code;
- absent, malformed, mixed and unrecognized declarations remain governing/fail closed;
- a detached forged receipt that recomputes its own hashes is rejected before admission; and
- after successful reconciliation the full frozen record, including every verification block and
  its byte-complete serialized form, remains readable.

Each witness must exercise the real owner/bridge; retaining marker strings while removing the live
admission path must turn the behavioral witness red (`P29`/`P32`/`P33`). `[P37:
institutionally_supplied for the witness specification; not_established until RED then GREEN are
retained]`

Two read-only Terra tracks launched for preflight used recursive whole-home `find` commands and were
terminated when the process census showed them consuming both scanner-heavy slots. They produced no
repository change and their partial output is not used as evidence. The sole completed preflight
track independently traced the actual source ordering: live receipt admissions are derived before
the comparison, then discarded by the clock-only generic reconciler. These preflight tracks are not
the three post-freeze independent reviews required by E11. `[P37: recomputed for the observed process
census/termination and current tracked delta; consumer_asserted for dispatch identity;
independently_reconciled for the completed source trace]`

### Late frozen review — the artifact owner also needs a v2 semantic lineage

The post-freeze review found one load-bearing defect in the already-landed artifact comparison
owner before any replacement Depth writer was launched. Its v1 projector removes
`N9PromotionLedgerRow.claim_execution_binding_hash` as though that digest were wholly physical.
The confidence-ledger producer actually binds claim/null/scope/window inputs, the pre-check
filtration/history, schedule position, risk spend, registry, instrument and proof identities into
that digest. Claim/window inputs are independently retained in the canonical promotion owner
projection, but the filtration/history preimage is absent from the narrow N9 receipt once the raw
digest is removed. A new hash over the remaining receipt fields would add no information and cannot
be labelled recomputed. The initial attempted row-field sketch and its two red tests remain a design
measurement only; no such schema change or source byte was committed. `[P37: independently_reconciled
for the producer-field trace; recomputed for the current uncommitted/test-only boundary;
not_established for filtration after the v1 projection]`

A complete walk of `architecture/policy_design_case/*.json` parsed `353/353` JSON artifacts. Raw
`claim_execution_binding_hash` occurs in exactly four governed roots and `114` scalar leaves:
promotion `6`, generation cycle `8`, N10a cycle-entry trace `32`, and Depth-N `68`. The transitive
writer family is six files because N10a pack and free-grow gaps bind the cycle-trace identity;
N10a census and smoke have no such dependency and must remain byte-identical. This is the same
already-authorized artifact comparison family, so B2 extends the batch rather than creating a third
mechanism. No writer-class process has been launched after this census. `[P37: recomputed for the
353-file/114-leaf denominator and dependency graph; institutionally_supplied for B2; not_established
for post-repair movement]`

The corrected artifact-owner contract is versioned and fail-closed:

1. The confidence-ledger producer emits a stable N9 semantic ledger projection from the complete,
   live-session-validated event chain. It carries the claim/window/owner/verifier bindings, semantic
   filtration chain, execution order, spend and outcomes, while the raw receipt continues to retain
   every physical ledger identity and byte.
2. A canonical promotion receipt records that semantic projection beside—not instead of—its raw N9
   projection. The v2 comparison owner removes physical session locators only after the complete
   semantic projection is present and valid. Missing, malformed or self-authored semantic evidence
   is non-comparable and fails closed.
3. Legacy frozen receipts may cross the migration seam only through an ephemeral canonical live
   proof. The owner requires the complete legacy governing projection and frozen owner inputs to
   equal the live replay, then attaches the live producer-derived semantic projection while leaving
   every pre-existing raw frozen leaf unchanged. A manifest, provenance string, detached token or
   recomputed self-hash cannot invoke that migration.
4. Once reissued, persisted validators reconstruct only the stateless v2 projector; the ephemeral
   legacy seam is neither serialized nor available to a check-only caller. The owner-rule and
   comparison-rule versions change, so v1 bytes cannot silently acquire v2 meaning.

This closes the information-loss predicate without rebaselining old raw evidence or trusting an
unresolvable CAS ref: custody identity still binds the raw bytes, while the decisive comparison
identity is produced from a new canonical replay of the frozen owner inputs. It is a correction to
the existing artifact-layer mechanism, not a governed denominator/admission change and not a third
bespoke mechanism. `[P37: independently_reconciled for the structural closure; recomputed is the
required admission label once live replay and comparison complete; not_established until RED→GREEN,
source freeze, reviews and reissue census]`

### GY-DEFC-5 v2 artifact owner — source batch prepared for freeze

Red-first execution established three precise absences before implementation: the two fresh
verification-session receipts had no `confidence_ledger_semantic_projection`, the v2 projector
could not be invoked, and a legacy receipt had no owner-bound migration seam. All three failed on
that missing producer field rather than on setup or a timeout. The generic PDC witness separately
failed because `GyComparisonAdmission` did not yet accept an ephemeral legacy migrator. No governed
artifact was written by these red invocations. `[P37: recomputed]`

The source batch now gives the full confidence-ledger event chain a stable N9 projection. The
projection is emitted only after `validate_confidence_ledger_receipt(..., session=...)`, includes
the complete semantic check/filtration event lineage and current-head denominator, validates every
root/check/event/head/spend hash on parse, and omits only deployment/CAS locators. A canonical
promotion receipt records it beside the untouched raw N9 projection. The comparison owner is
versioned from receipt rule `v1` to `v2`, comparison projection `v1` to `v2`, and verification rule
`v2` to `v3`. Missing or forged semantic lineage fails closed. `[P37: recomputed for the current
source and behavioral tests; not_established for governed reissue bytes]`

The legacy bridge is deliberately ephemeral. A live owner admission first replays and verifies the
complete current receipt, then its closure may add exactly that producer-derived semantic
projection to a legacy frozen receipt only when the complete v1 governing projection matches. All
pre-existing raw receipt leaves remain frozen. The generic comparison plan carries this closure in
memory but omits it from the persisted manifest; a check-only manifest reconstruction therefore
cannot mint a migration. Promotion, generation-cycle and N10a accept an old manifest only after its
stored v1 schema/rule/owner action and comparison hash reproduce exactly; they always emit v2/v3.
Depth composes the same receipt migration inside its one admitted recording root and recomputes the
recursive-run, compiled-run, recording, route and authority-envelope custody identities derived
from the newly added semantic field. `[P37: independently_reconciled for the structural boundary;
recomputed for the focused source witnesses; not_established for the full Depth replay]`

Focused source feedback before freeze:

- the complete promotion-sequence test module passed after the v2 implementation, including two
  fresh sessions with different physical deployment identities and equal semantic projections, a
  governing owner-input change with the named semantic mismatch, forged/detached proof rejection,
  legacy migration, and byte-complete raw-row preservation;
- the generic PDC migration tests, confidence-ledger semantic-lineage tests, and six controlled
  recording authority/fail-closed tests passed;
- generation-cycle's governing mutation remained red, but the prior test expected the generic
  revalidation code while the repaired owner now reports the narrower
  `embedded_promotion_receipt_semantic_projection_drift`; the assertion was corrected to the
  observed owner code;
- a combined downstream test invocation reached a pre-existing N10a historical-N4 assertion which
  expected the refreshed owner projection to differ from the frozen projection. They are now equal,
  so that invocation stopped red after the expensive fixture build. This is a stale test premise,
  not evidence of owner drift, and it is excluded from the final source receipt; the governed
  artifacts remained byte-identical. `[P37: recomputed]`

The expanded same-mechanism family remains the `353/353` JSON census's four raw roots and six
dependent outputs: promotion, generation cycle, N10a trace/pack/gaps, and Depth. The N10a census and
smoke output remain outside the dependency. B2 authorizes this pre-enumerated batch even though the
earlier artifact-layer reissues have already landed; the replacement reissues are required because
their v1 owner discarded a governing filtration predicate. Confidence remains the separate B3
blocked member. `[P37: recomputed for the denominator/dependency; institutionally_supplied for B2
and B3; not_established for post-freeze deltas and accepted reissues]`

### Post-freeze correction — final Depth reconciliation must propagate migrated custody

The first v2 wave review rejected the static recording census before any governed writer ran. That
census called the v2 receipt projector directly on frozen v1 receipts, so its
`promotion_comparison_semantic_ledger_missing` terminal was the new fail-closed rule working, not a
product failure. A source-bound census must instead build a live candidate through the canonical
promotion proofs and their ephemeral v1-to-v2 migrators, then reconcile the frozen artifact. The
static census invocation is a setup/design non-receipt; it wrote only ignored `tmp/**` evidence and
changed no governed byte. `[P37: independently_reconciled for the classification; recomputed for
the retained source/error and current governed-byte boundary]`

That review also found one real propagation defect in the source batch. The per-role live replay
correctly called `_reissue_authority_source_envelopes_after_comparison_migration` after adding the
new nested semantic lineage. The final artifact reconciliation then invoked the root legacy
migrator a second time while preserving frozen custody: it rehashed the recursive run, compiled run
and recording, but retained the old `authority_source_admission`, old
`authority_source_migration_receipt`, and old sibling `domain_runs[role].recording_content_hash`.
Thus the earlier statement that the full Depth path recomputed route and authority-envelope custody
was true for live candidate construction but false at the final frozen-artifact seam. This is the
same authorized recording-level mechanism, not a third one. `[P37: independently_reconciled for
the two-call data-flow trace and same-owner classification]`

A RED-first artifact-level witness used the real `GyComparisonProjectionPlan` root migration over
the frozen `first_vertical` recording. Before the repair, the migrated recording bound
`sha256:763dd44b…d229c0` while its sibling route still bound
`sha256:980bd2f8…e244e4`; the authority owner reported at least
`authority_source_recording_base_binding_mismatch` and
`authority_source_admission_compiled_binding_mismatch`. The focused pytest invocation exited `1`
on that exact hash-equality assertion. No artifact writer ran. `[P37: recomputed]`

The minimal repair adds one final artifact-owner postpass between
`preserve_admitted_blocks(...)` and `_set_artifact_identities(...)`. It derives the affected roots
from the live plan's canonical recording-owner manifest entries; if and only if a preserved root
actually changed through its ephemeral legacy migrator, it calls the existing authority-envelope
owner with the frozen prior admission/receipt and the reconciled live route, then replaces the root
and sibling route together. Missing prior authority or route evidence fails closed with a named
code. It does not copy a live envelope, weaken a validator, or alter ledger scope semantics.
`[P37: independently_reconciled for placement; recomputed for the implemented owner delegation]`

The same focused witness then exited `0`: recording and route hashes matched, the complete
authority-source issue set was empty, and full `validate_payload` returned no issue. The focused
controlled-recording/outer-plan subset also exited `0`; Ruff and `git diff --check` were clean.
These interactive RED/GREEN invocations establish source feedback but are not yet source-bound
post-freeze receipts. No governed artifact, denominator, admission outcome, comparison outcome,
transport covariate, N8 proof hash, or ambient discovery identity changed. `[P37: recomputed for
the observed terminals and current two-path diff; not_established for the post-freeze live census
and reissue wave]`

### Envelope propagation freeze and review

The propagation correction landed append-only as `cd29ca29d` on the attached task branch, `27`
commits ahead of `c1a89b6cf`; the commit contains only the Depth owner, its mirrored test and this
journal. A retained post-freeze suite selected ten controlled-recording, artifact-reconciliation and
outer-plan tests under the receipt interpreter. It exited `0` in `104.065146` s under a `300` s
fence, with empty stderr and unchanged clean head. Its meta/stdout SHA-256 values are
`8e40fb9b…83197` and `7040371a…4103`. `[P37: recomputed]`

Three independent Terra reviews, no Sol review, then inspected the frozen source. The authority
track found no Critical/Important P05/P31/P32/P37 issue: migration remains available only on a live
producer plan, and the postpass recomputes rather than copies the authority envelope. The
correctness track traced the two-pass migrated-receipt/admission/hash loop and repeat-v2 path and
found no Critical/Important defect. The wave track confirmed the live census must remain the real
proof because the fast fixture deliberately substitutes the nested owner proof. The review tracks
were read-only; root alone wrote source. `[P37: consumer_asserted for dispatch identities and
verdicts; independently_reconciled for the source boundary they cite]`

One overlapping focused-test capture was terminated with `SIGTERM` after the process census showed
that a reviewer had independently launched the same test while root's retained run was active. It
ran `123.570699` s, recorded child/wrapper exit `-15`, was not a timeout, and left the clean
`cd29ca29d` head unchanged. Its meta SHA-256 is `cd61cea4…ddd2`. It is a contention/setup
non-receipt and supplies neither correctness nor duration evidence. `[P37: recomputed]`

### Live-census ordering correction — upstream v1 artifacts first

The first ignored live-census harness attempt exited `1` in `150.857683` s with no timeout and no
governed byte change. It called the cached async replay before the canonical synchronous provenance
gate had warmed its cache, so composition validation attempted a nested `asyncio.run` and Python
raised `RuntimeError: asyncio.run() cannot be called from a running event loop`. Meta/stderr hashes
are `6ab8744f…6efc1` and `e34198fb…78aab`. The harness was corrected to match the canonical CLI's
preflight ordering; no source or artifact changed. This is a harness non-receipt. `[P37:
recomputed for the terminal and byte pin; independently_reconciled for the canonical-ordering
classification]`

The corrected second attempt reached that provenance gate and exited `1` in `220.705154` s, again
without timeout and with the `1,841,810`-byte Depth artifact unchanged at
`acc25257…3f089`. Its exact owner issues were the still-v1 N10a comparison schema, rule and manifest,
plus their dependent N6 gap receipt. Meta/stderr hashes are `6fcc4e33…6487` and
`5f2d744c…6304e`. This is expected fail-closed behavior after the v2 source freeze: the Depth
candidate cannot be built until the already-enumerated upstream promotion, generation and N10a
artifacts acquire their v2 projection lineage. It is a provenance-ordering non-receipt, not a third
mechanism. `[P37: recomputed for the issues and byte boundary; independently_reconciled for the
dependency classification]`

This measurement corrects the prompt's order. The batch now runs promotion → generation → N10a,
then re-runs the source-bound all-role Depth census, then accepts Depth. That is the same predeclared
six-file family and obeys B2; it does not discover or repair an artifact one at a time. The live
census remains a hard acceptance gate immediately before the Depth writer. `[P37:
institutionally_supplied for the measurement-wins/B2 authority; recomputed for the dependency that
forces the order; not_established for all four replacement reissues]`

The refreshed timing report parsed `145` records and completed at the clean `cd29ca29d` head. Its
recomputed two-times-p95 caps are promotion write/check/rederive
`52.439504`/`52.486368`/`52.080878` s; generation
`76.199994`/`85.542132`/`75.902086` s; N10a
`852.699146`/`74.272168`/`726.805376` s; and Depth
`4,942.540412`/`319.661388`/`1,695.177568` s. The four corrupt lanes remain under declared hang
fences `300`/`300`/`300`/`600` s because GY-DI4 is registered and unimplemented. The report
meta/output hashes are `2d487f36…5f4bf` and `5659b525…0583`. `[P37: recomputed]`

### GY-DEFC-5 promotion v2 — declared accepted delta

The promotion measurement ran alone from clean head `a64391514`, completed with exit `0` in
`38.846821` s under the recomputed `52.439504` s cap, and emitted empty stderr. The sole canonical
output was copied after the run, then restored byte-for-byte and re-read at preimage SHA-256
`89694280…e01b`; the candidate SHA-256 is `68e05dc3…9577`. The measurement meta, stdout, delta,
summary and complete path-list identities are respectively `2a9b7be9…8f36`,
`7b4f81a1…c714`, `b9f802f8…905ae`, `4a81b595…dbf6e`, and
`2afa02b5…3444`. This invocation is a measurement/non-receipt and consumes no accepted promotion
reissue. `[P37: recomputed for the terminal, cap and exact restore; institutionally_supplied for
the allowance semantics]`

The accepted writer is declared to move exactly `604` scalar leaves, with this complete structural
set and no others:

1. Add `199` scalar leaves below each of the three exact receipt roots
   `$.{contract_lane_anytime_refusal,non_promotable_contract_stamp,production_honest_shadow}.
   confidence_ledger_semantic_projection` (`597` leaves total). Each root has the same complete
   relative leaf set:
   - the `19` direct leaves
     `{authority_provenance,budget_delta_decimal,conditionality_clause,good_event_clause,
     head_event_projection_hash,maintained_assumptions[0],maintained_assumptions[1],projection_hash,
     projection_rule_version,projection_scope,registry_content_hash,root_projection_hash,
     schedule_profile_hash,schedule_profile_id,schedule_projection_hash,schema_version,scope_id,
     total_spend_decimal,within_budget}`;
   - `budget_delta.{denominator,numerator}`, `total_spend.{denominator,numerator}`, and
     `risk_scope.{authority_purpose,epoch_ref,model_ref,owner_projection_hash,owner_scope_key,
     rule_ref,schema_ref,scope_owner_ref}` (`12` leaves);
   - for each `checks[{0,1}]`, the exact `40` leaves
     `{anytime_valid,certificate_class,certificate_ref,certificate_role,certificate_route_hash,
     check_projection_hash,claim_execution_projection_hash,claim_polarity,claim_ref,
     claim_scope_ref,data_window_ref,deterministic_proof,eligible_for_promotion,execution_id,
     execution_ordinal,execution_status,filtration_projection_hash,good_event_id,
     instrument_definition_hash,instrument_family,instrument_id,null_ref,obligation_class,outcome,
     owner_binding,owner_invocation_claim_projection_hash,proof_detail,proof_profile_hash,
     proof_profile_id,refusal_code,registry_content_hash,request_fingerprint,request_key,
     schedule_query_index,schema_version,scope_id,spend.denominator,spend.numerator,spend_decimal,
     supports_obligation}` (`80` leaves); and
   - for each `events[{0,1}]`, `check` has that same exact `40`-leaf set and the event has
     `{event_projection_hash,event_type,parent_event_projection_hash,revision}` (`88` leaves).
2. Move the three existing leaves
   `$.comparison_admission_manifest[{0,1,2}].owner_rule` from the v1 to the v2 canonical promotion
   owner rule.
3. Move the four dependent leaves `$.comparison_content_hash`,
   `$.comparison_projection_schema_version`, `$.comparison_rule_version`, and
   `$.contract_content_hash`.

Arithmetic is `3 × 199 + 3 + 4 = 604`. The machine-readable list contains all `604` concrete JSON
paths and is content-bound by the `expected-leaf-paths.txt` identity above. Removing only the newly
added semantic projection from each candidate receipt reproduces its complete frozen receipt
exactly. No pre-existing `status`, `promoted`, `consumer_promotable`, eligibility,
supports-obligation, budget, terminal, reason, receipt-count or certified-candidate leaf moves; no
denominator, comparison/admission outcome, transport covariate, N8 proof, ledger scope or ambient
identity moves. The accept predicate is exact equality with this `604`-leaf set and candidate byte
identity. `[P37: recomputed for the complete measured set, raw-byte preservation and negative
protected-leaf intersection; not_established for accepted persistence and verifications]`

### GY-DEFC-5 promotion v2 — accepted reissue and verification closure

The canonical accepted writer ran alone from clean head `fef63760d`, exited `0` in
`28.123877` s under the recomputed `52.439504` s cap, did not time out, and emitted empty stderr.
The resulting artifact SHA-256 is `68e05dc3…9577`, byte-identical to the measured candidate.
Its recursive delta has exactly the same `604` changed paths as the predeclared measurement and no
additional or missing path. The accepted write therefore satisfies the exact-set acceptance
predicate; the sole accepted promotion reissue is consumed. The write meta/stdout identities are
`403cebc9…c729` and `7b4f81a1…c714`. `[P37: recomputed]`

The canonical `--check` exited `0` in `28.138446` s under its `52.486368` s cap with
`status: pass`, `issues: []`, validator wall time `16.287970` s, no timeout and empty stderr. The
meta/stdout identities are `193d69a0…058` and `ba9b3bb9…e45f`. The canonical rederive audit exited
`0` in `28.880129` s under its `52.080878` s cap with `status: pass`, `issues: []`, validator wall
time `16.125426` s, no timeout and empty stderr; its meta/stdout identities are
`6aa73ae4…693b` and `64aac030…8ed7`. `[P37: recomputed]`

The corrupt-field lane completed in `11.877764` s under the declared `300` s hang fence, did not
time out, and exited `1`. Its actual validator contract does not emit a `missing` collection: green
is `status: fail` with the leading named issue `corrupt_field_drift_detected`, followed by the
specific missing `conditionality_clause` validation and dependent contract-hash drift. This is the
completed-work terminal proving the mutation was detected, not a failed detection (which the tool
would report as `status: pass` / `corrupt_field_drift_not_detected`). The prompt's generic “empty
missing” wording is therefore corrected to the producer's measured lane contract rather than
inventing an absent field. Meta/stdout identities are `4dbbeb80…3d95` and `e846d442…8354`; stderr
is empty. `[P37: recomputed for the producer return mapping and observed terminal;
institutionally_supplied for the declared hang fence]`

Read-back after all three verifications still gives the accepted `149,504`-byte artifact at
`68e05dc3…9577`; no other governed path is dirty. Promotion's custody bytes retain the full raw N9
receipts, while its opt-in v2 comparison identity now binds the producer-verified semantic event
chain. No denominator, admission/comparison outcome, transport covariate, N8 proof, ledger scope or
ambient discovery identity moved. `[P37: recomputed]`

### Generation v2 measurement — contended cap non-receipt

The first generation-cycle measurement at head `0a288717d` was terminated by the wrapper after
`76.242653` s at the recomputed `76.199994` s cap (`timed_out: true`, child exit `-15`, wrapper
exit `124`). It emitted no stdout or stderr and never wrote the canonical output: the before/after
pins are byte-identical at `107,712` bytes and SHA-256 `6538e879…344`. The meta identity is
`a6c91028…97a4`. This is a killed cap observation with zero output, not a completed lane decision
and not a duration sample. `[P37: recomputed]`

The process census immediately after termination showed a concurrent Atlas DS6 Vitest parent and
eight rotating Node worker processes; the observed workers consumed roughly `27–60%` CPU each and
about `0.13–0.21` GiB RSS each. Their parent elapsed time aligned with the full generation interval.
That is direct contention evidence under B4, so exactly one remeasurement is authorized after the
external lane exits; the cap is not raised. `[P37: recomputed for the observed process census;
institutionally_supplied for B4 and the one-rerun allowance]`

### GY-DEFC-5 generation v2 — serialized candidate and declared accepted delta

The B4 remeasurement at head `64dbb87cb` reached the generator's own completed-work terminal:
its isolated timing record says `status: ok`, exit `0`, duration `70.278092` s, and stdout says
`status: pass`, `issues: []`. It wrote the sole declared output at candidate SHA-256
`7b80bf43…8e30`. The outer wrapper nevertheless killed the still-live process during shutdown at
`76.281514` s against the `76.199994` s cap (child `-15`, wrapper `124`); an Atlas DS6 Vitest
`run2` parent had started at essentially the same time and remained live throughout, although its
rotating workers made the first post-run census look like a final-seconds restart. Because a
harness kill is never an admissible sample, this
invocation remains a measurement/non-receipt and the accepted generation allowance remains unused.
The candidate was preserved before the committed artifact was restored and re-read exactly at
`107,712` bytes / `6538e879…344`. Meta, stdout, isolated timing and candidate identities are
`4a1a589f…e743`, `5ddbb5f2…96b6`, `3ecd7cac…e2e5`, and `7b80bf43…8e30`.
`[P37: recomputed for the producer terminal, wrapper kill, candidate and exact restore;
institutionally_supplied for the non-receipt/allowance rule]`

The accepted generation writer is declared to move exactly `740` scalar leaves, with this complete
structural set and no others:

1. Add `367` scalar leaves below each of the two exact receipt roots
   `$.generation_cycle_run.promotion_port.receipts[{0,1}].
   confidence_ledger_semantic_projection` (`734` leaves total). Each root has the same complete
   relative leaf set:
   - the `19` direct leaves
     `{authority_provenance,budget_delta_decimal,conditionality_clause,good_event_clause,
     head_event_projection_hash,maintained_assumptions[0],maintained_assumptions[1],projection_hash,
     projection_rule_version,projection_scope,registry_content_hash,root_projection_hash,
     schedule_profile_hash,schedule_profile_id,schedule_projection_hash,schema_version,scope_id,
     total_spend_decimal,within_budget}`;
   - `budget_delta.{denominator,numerator}`, `total_spend.{denominator,numerator}`, and
     `risk_scope.{authority_purpose,epoch_ref,model_ref,owner_projection_hash,owner_scope_key,
     rule_ref,schema_ref,scope_owner_ref}` (`12` leaves);
   - for each `checks[{0,1,2,3}]`, the exact `40` leaves already enumerated in the promotion
     declaration (`160` leaves); and
   - for each `events[{0,1,2,3}]`, `check` has that same exact `40`-leaf set and the event has
     `{event_projection_hash,event_type,parent_event_projection_hash,revision}` (`176` leaves).
2. Move the two existing leaves `$.comparison_admission_manifest[{0,1}].owner_rule` from the v1 to
   the v2 canonical promotion owner rule.
3. Move the four dependent leaves `$.comparison_content_hash`,
   `$.comparison_projection_schema_version`, `$.comparison_rule_version`, and
   `$.contract_content_hash`.

Arithmetic is `2 × 367 + 2 + 4 = 740`. The complete machine-readable path list is content-bound by
SHA-256 `d7a46aa8…42184`; the delta and summary identities are `535733d4…54c01` and
`f159bf1b…9af1f`. Removing only the newly added semantic projection from each candidate receipt
reproduces both complete frozen receipts exactly. No other old leaf changes, so the protected set
has empty intersection: no governed denominator, admission/comparison outcome, transport
covariate, N8 proof, ledger scope, ambient discovery identity, or unrelated receipt moves. Accept
only if a fresh canonical writer produces the same candidate byte identity and the identical
`740`-path set. `[P37: recomputed for the complete set, raw preservation and protected-field
intersection; not_established for accepted persistence and verifications]`

The first post-declaration accepted-writer attempt at clean head `38f11fe00` was killed at the
outer cap after `76.314662` s (child `-15`, wrapper `124`). It emitted neither stdout, stderr nor
an isolated timing record and changed zero artifact leaves; before/after remained the exact
`107,712`-byte `6538e879…344` preimage. Meta and zero-delta identities are
`39630faa…f911` and `c5f05b8d…8a64`. Process-tree reconstruction showed an Atlas DS6 component
suite orchestration parent launched about eight seconds after this writer and kept a Vitest parent
plus workers live for the remaining interval. This is a contention non-receipt, not an accepted
generation reissue; its allowance remains unused. The next launch waits for the orchestration
parent itself to exit and for a quiet process interval, not merely for a child PID to rotate.
`[P37: recomputed for the terminal, zero-byte boundary and process-tree overlap;
institutionally_supplied for the allowance rule]`

### GY-DEFC-5 generation v2 — accepted reissue and verification closure

After the external Atlas sequence completed and a `30` s quiet process interval held, the canonical
writer ran alone from clean head `2666f5628`. It exited `0` in `45.148865` s under the unchanged
`76.199994` s cap, did not time out, emitted empty stderr, and wrote candidate SHA-256
`7b80bf43…8e30`. The bytes exactly equal the measured candidate, and the recursive delta has the
identical `740/740` declared path set with no extra or missing leaf. The accepted generation
allowance is therefore consumed. Meta, stdout, isolated timing and accepted-delta identities are
`bee488d0…09a8`, `5ddbb5f2…96b6`, `58836b33…a75c`, and `bb05f4f6…ab6c9`.
`[P37: recomputed]`

The canonical `--check` exited `0` in `42.024739` s under its `85.542132` s cap with
`status: pass`, `issues: []`, validator wall time `29.373727` s, no timeout and empty stderr. Its
meta/stdout identities are `9b42615e…1eaf` and `242094cf…6356`. The rederive audit exited `0` in
`42.188818` s under its `75.902086` s cap with `status: pass`, `issues: []`, validator wall time
`29.746186` s, no timeout and empty stderr; its meta/stdout identities are
`2142216e…f6cb` and `a945b4dd…2a10`. `[P37: recomputed]`

The corrupt-field lane completed in `12.419707` s under the declared `300` s hang fence, did not
time out, and exited `1`. Its producer contract reports `status: fail` with leading issue
`corrupt_field_drift_detected`, followed by the named generation-run and dependent comparison /
contract hash drifts. As with promotion, this proves the lane's one decisive-field mutation was
detected; it does not claim an absent generic `missing` denominator. Meta/stdout identities are
`c630b0ce…f585` and `3740c433…5566`; stderr is empty. `[P37: recomputed for the producer terminal;
institutionally_supplied for the declared hang fence]`

Final read-back keeps the sole `165,398`-byte artifact at `7b80bf43…8e30`; no other governed path
is dirty. Full raw receipt custody remains present while the v2 comparison projection binds the
producer-verified semantic chain. No protected denominator, admission/comparison outcome,
transport covariate, N8 proof, scope or ambient identity moved. `[P37: recomputed]`

### GY-DEFC-5 N10a v2 — measured and declared five-output transition

The canonical non-persisting transition measurement ran alone from clean head `f2aa668e3`, exited
`0` in `459.014245` s under the approved `852.699146` s writer/prewrite envelope, and reported
producer wall time `444.758685` s, `status: pass`, `issues: []`, `write_performed: false`. The only
stderr is two expected database-connection log lines. All five governed outputs remained
byte-identical to their preimages, and the external N8 value-gate artifact remained byte-identical.
Meta, stdout, stderr, parsed-result and manifest-file identities are `76872ee6…1805`,
`4f94dc6c…7d23`, `b57c003e…4e8c`, `dd0bfc96…7f6a`, and `1e576383…04dd5`.
`[P37: recomputed]`

The transition manifest is schema `policyos.gy.n10a.write_transition.v1`, source-bound to
`f2aa668e3` and source-scope identity `sha256:7b49aa64…4839a`; its self identity is
`sha256:fc390e7b…53c3a`. It enumerates exactly five ordered outputs and `2,832` changed scalar
leaves with distribution `0 / 3 / 0 / 2,824 / 5` for census / pack / smoke / cycle trace / gaps.
The complete output-plus-pointer TSV has SHA-256 `b7f7f01c…9537b`. Because this journal declaration
will move HEAD, that first manifest is intentionally measurement-only; after this declaration is
committed, a fresh non-persisting measurement must reproduce the complete structural set and live
content identities while binding a new manifest to the new clean head. No writer may consume the
stale first manifest. `[P37: recomputed for the manifest and complete denominator;
independently_reconciled for the clean-head refresh requirement]`

The accepted N10a writer is declared to move exactly this complete set and no other leaf:

1. Census: zero leaves. Its custody identity remains
   `sha256:fb98cc50…fd0d`. Smoke problem: zero leaves, identity
   `sha256:d40e3fe5…70e5`.
2. Pack: exactly `/cycle_trace_content_hash`, `/gap_report_content_hash`, and
   `/manifest_content_hash`, moving the enclosing live identity from `sha256:a1953ae6…e0466` to
   `sha256:5c57dffd…cb705`.
3. Cycle trace: add exactly `703` scalar leaves below each of the four roots
   `/generation_cycle_run/promotion_port/receipts/{0,1,2,3}/
   confidence_ledger_semantic_projection` (`2,812` leaves). Each root has the same structural set:
   `17` direct leaves; `maintained_assumptions/{0,1}`; two `budget_delta` leaves; two
   `total_spend` leaves; eight `risk_scope` leaves; eight `checks`, each with the canonical
   `40`-leaf semantic-check set; and eight `events`, each with that same `40`-leaf check plus
   `{event_projection_hash,event_type,parent_event_projection_hash,revision}`. Arithmetic per root
   is `17 + 2 + 2 + 2 + 8 + 8×40 + 8×44 = 703`.
4. Cycle trace: move the four existing
   `/comparison_admission_manifest/{0,1,2,3}/owner_rule` leaves from v1 to v2; move
   `/comparison_content_hash`, `/comparison_projection_schema_version`, and
   `/comparison_rule_version`; move dependent `/gap_triage/6/receipt_ref`; move only the three
   ordinary operational leaves
   `/generation_cycle_run/cycles/0/acquisition_routing_report/generated_at`,
   `/runtime_metrics/aggregate_value_port_wall_time_ms`, and
   `/runtime_metrics/cycle_value_port_wall_time_ms/0/value_port_wall_time_ms`; and move enclosing
   `/trace_content_hash`. That is `2,812 + 12 = 2,824` trace leaves, from live identity
   `sha256:83134ef4…e2b3` to `sha256:1e9c67b9…0d95`.
5. Free-grow gaps: exactly `/gap_report_content_hash`, `/gaps/6/gap_content_hash`,
   `/gaps/6/owner_evidence/stage_3_behavioral_receipt/receipt_ref`,
   `/gaps/6/owner_evidence/stage_3_behavioral_receipt/run_content_hash`, and
   `/gaps/6/owner_evidence/trace_content_hash`, moving the enclosing identity from
   `sha256:34ad1cbf…60e92` to `sha256:c7c674e6…044d0`.

The four newly added semantic projections contain producer-recomputed copies of check outcomes,
eligibility, spend denominators, scope and proof-profile commitments; those are new comparison
evidence, not changes to any pre-existing admission or proof leaf. Every pointer containing those
terms lies below one of those four new roots. Outside those roots the transition contains no
denominator, eligibility, supports-obligation, outcome, transport, N8 proof, scope,
`ambient_discovery.manifest_id`, or `ambient_discovery.provenance_id` pointer. The already accepted
N8 content identity does not move in this reissue; gap 5 is absent from the delta. The only
downstream receipt movement is gap 6's trace-dependent N11 verification receipt. Accept only if the
fresh source-bound manifest reproduces this exact set and the writer's observed five-output delta
equals it. `[P37: recomputed for the complete pointer classification and external N8 byte pin;
not_established for fresh-head reproduction, accepted persistence and verifications]`

### GY-DEFC-5 N10a v2 — serialized-host interruption non-receipt

The first post-declaration fresh-head measurement was launched from clean attached head
`13ceb3762` only after six process censuses over a `25` s quiet interval found no matching
writer/scanner-heavy process. A competing Atlas TypeScript scanner then appeared while the
measurement was live (observed PID `19881`, approximately `185%` CPU and `300,832` KiB RSS). To
preserve the one-heavy-process invariant, the N10a child process group was terminated deliberately
after `70.012021` s. The wrapper records child and wrapper terminal `-15`, `timed_out: false`, empty
stdout/stderr, identical attached branch/head before and after, and an empty tracked status before
and after. `[P37: recomputed]`

All five governed before/after pins are byte-identical: census `73,888` bytes /
`ba20cdb3…e74c`, pack `252,598` / `9b67629d…65441`, smoke `4,665` / `688bd3d8…5f76d`,
cycle trace `345,007` / `47a65629…09f4`, and gaps `21,053` / `496944b5…74941`.
The external N8 value-gate remains `c3f131ce…bc303`. The meta/stdout/stderr identities are
`d4ba8d9b…2d1fc`, `e3b0c442…b855`, and `e3b0c442…b855`. This invocation produced no transition
manifest and no changed governed byte, so it is a contention non-receipt; it consumes neither the
fresh measurement nor the accepted N10a reissue. A new quiet interval is required before the next
launch. `[P37: recomputed for the byte/head/status boundary; institutionally_supplied for the
completion/allowance rule]`

The next launch followed a new `30` s quiet interval at clean attached head `c6a26e6fb`, but a
second external scanner sequence again started only after N10a was live. Process-tree read-back
identified Python parent PID `20393` and child `20404` running
`python -m unittest architecture.atlas_surfaces.test_frontend_disposition_register`, with rotating
TypeScript scanner children (one observed at PID `20688`, approximately `127%` CPU and `355,328`
KiB RSS). N10a was therefore terminated deliberately after `55.648199` s rather than allowed to
contend. The wrapper again records `timed_out: false`, terminal `-15`, attached branch/head and an
empty tracked status before/after; all five governed pins are identical. Stdout is empty; stderr is
only the two database-connection information lines emitted before termination. Meta/stdout/stderr
identities are `dbf9d5a4…733a`, `e3b0c442…b855`, and `e93a3ada…32cd`. This is a second
serialized-host non-receipt with no accepted manifest or reissue. The next quiet gate is tied to the
scanner's orchestration parent exiting, not merely to a rotating child disappearing.
`[P37: recomputed for process lineage, terminals and byte boundary; institutionally_supplied for
the completion/allowance rule]`

### GY-DEFC-5 N10a v2 — fresh source-bound manifest and writer contention non-receipt

After the full Atlas enforcement sequence exited and an `85` s / `18`-sample quiet interval held,
the third fresh-head non-persisting measurement ran alone at clean attached head `b4afdf052`. It
exited `0` in `208.203441` s under the `852.699146` s cap, did not time out, and reported producer
wall time `199.050905` s, `status: pass`, `issues: []`, `write_performed: false`. All five governed
pins remained byte-identical and external N8 remained `c3f131ce…bc303`. Meta, stdout, stderr,
parsed-result and manifest-file identities are `14d984f7…d50e`, `69b1512f…03d1`,
`dec9a903…9b02`, `d6be64c1…e8e0`, and `f887c6ed…7341`. `[P37: recomputed]`

The fresh manifest binds source head `b4afdf052`, repeats source-scope identity
`sha256:7b49aa64…4839a`, and has self identity `sha256:7bbe2b28…d24de`. Its complete `2,832`-row
output/pointer TSV is byte-identical to the declaration at SHA-256 `b7f7f01c…9537b`; all five
transition modes, legacy identities, live identities and changed-leaf sets are identical. The only
differences from the measurement-only manifest are the required source head and dependent manifest
self identity. Two fresh independent Terra reviews returned no Critical or Important finding: each
recomputed the manifest/path denominator and source binding, and one independently traversed the
complete `3,286`-file source/tool scope. `[P37: recomputed for the manifest equality and identities;
independently_reconciled for the two review verdicts]`

The accepted writer was then launched from that same clean head only after the host again held an
`85` s quiet interval. It ran alone for about two minutes, after which a new external Atlas DS5
ESLint pass started and overlapped the writer for approximately `83` s. The observed external tree
was `/usr/bin/time corepack pnpm exec eslint` with Node children, including an ESLint child at about
`95%` CPU and `1,233,248` KiB RSS. To preserve the one-heavy-process rule, N10a was terminated
deliberately after `217.754981` s. The wrapper records `timed_out: false`, child/wrapper terminal
`-15`, empty stdout and only the two database-connection information lines on stderr. Meta/stdout/
stderr identities are `ec6d1e74…809d`, `e3b0c442…b855`, and `504fe21c…80ab`.
`[P37: recomputed]`

All five governed outputs and the external N8 pin are byte-identical before/after, and branch,
head and tracked status are unchanged. The invocation therefore produced no reissue and consumed no
accepted N10a allowance. Committing this non-receipt advances HEAD and intentionally expires the
otherwise-valid fresh manifest; another non-persisting source-bound measurement is required after
the external DS5 sequence finishes before the accepted writer can be attempted again.
`[P37: recomputed for the zero-byte boundary; institutionally_supplied for the
completion/allowance rule; independently_reconciled for fresh-HEAD rebinding]`

### GY-DEFC-5 N10a v2 — parallel-execution ruling and accepted reissue

One further clean-head measurement at `d875a2285` was terminated deliberately when the external
Atlas DS5 `check_frontend_disposition_register.py --write-report` sequence began after launch. It
ran `71.708607` s, ended at child/wrapper terminal `-15` without timeout, produced empty stdout and
only the two database-connection information lines on stderr, and kept all five governed pins,
attached head and tracked status exact. Meta/stdout/stderr identities are `b3eb6154…64a3`,
`e3b0c442…b855`, and `7fb70700…ecaf`. No manifest or changed byte was produced, so it is another
non-receipt and consumed no allowance. `[P37: recomputed for the terminal and byte boundary;
institutionally_supplied for the completion/allowance rule]`

The user then explicitly changed the execution condition: external heavy processes may run in
parallel because waiting for host-wide quiescence prevents completion. From this point the chain
keeps only one PolicyOS writer/scanner-heavy process alive at a time, retains every governed cap and
byte fence, but does not abort or defer merely because an external Atlas process overlaps it.
External contention is therefore recorded as an execution covariate, not an admission predicate or
a reason to raise a cap. `[P37: institutionally_supplied]`

Under that condition, the next non-persisting measurement ran from clean attached head
`d875a2285`, completed with exit `0` in `790.361101` s under the unchanged `852.699146` s cap, and
reported producer wall time `753.083612` s, `status: pass`, `issues: []`, and
`write_performed: false`. All five governed pins remained byte-identical. Its manifest binds that
head, repeats source-scope identity `sha256:7b49aa64…4839a`, and has self identity
`sha256:2e58b328…70fb`. Its complete TSV remains byte-identical to the declaration at
`b7f7f01c…9537b`; the five transitions, all legacy/live identities and all `2,832` paths are exact.
Meta/stdout/stderr/result/manifest-file identities are `0a97d218…ffa9`, `d6e9d006…5f1f`,
`6b4f8d0b…ec3a`, `e4cb6a61…01ab`, and `f2bae901…9cb7`. `[P37: recomputed]`

The accepted canonical writer consumed that exact manifest without an intervening source/head
change. It completed with exit `0` in `821.343937` s under the same cap, did not time out, reported
`status: pass`, `issues: []`, `write_performed: true`, and wrote exactly three of its five outputs.
Its observed recursive delta equals the predeclared set exactly: `2,832/2,832` paths, distributed
`0 / 3 / 0 / 2,824 / 5` across census / pack / smoke / cycle trace / gaps, with zero missing and
zero unexpected path. Meta/stdout/stderr/result/delta/audit identities are `fd911f82…e1b1`,
`f90cff61…4f2`, `7a169792…25d7`, `455fd068…d637`, `90f6239b…5d8b`, and
`46da20f2…f441`. `[P37: recomputed]`

Read-back reproduces every expected live content identity: census `sha256:fb98cc50…fd0d`, pack
`sha256:5c57dffd…b705`, smoke `sha256:d40e3fe5…70e5`, cycle trace
`sha256:1e9c67b9…0d95`, and gaps `sha256:c7c674e6…44d0`. The complete raw N9 receipt remains
byte-for-byte present for each of the four promotion receipts after removing only its new
`confidence_ledger_semantic_projection`; the projection is present and readable in every receipt.
The protected-path intersection outside those four new roots is empty, and external N8 remains
`c3f131ce…bc303`. The accepted N10a reissue is therefore consumed. `[P37: recomputed]`

Canonical `--check` completed with exit `0` in `46.919253` s under `74.272168` s, with producer
wall time `16.648031` s, `status: pass`, `issues: []`, unchanged five-output pins and empty stderr.
Its meta/stdout identities are `1679dee4…f3f7` and `d5438ead…cdbb`. Canonical rederive audit
completed with exit `0` in `589.402145` s under `726.805376` s, with producer wall time
`564.062040` s, `status: pass`, `issues: []`, and unchanged pins. Its meta/stdout/stderr identities
are `3e322d18…833a`, `2837172a…9efe`, and `1d34a254…0e51`; stderr contains only expected runtime
information logs. `[P37: recomputed]`

The corrupt-field lane completed in `33.428430` s under the declared `300` s hang fence, did not
time out, and exited `1`. It reported `status: fail` with leading
`corrupt_field_drift_detected` and a detected set of `40` named mutation classes; no mutation was
reported missing or undetected, and all five pins remained exact. The producer does not emit a
generic `missing` field in this lane. Meta/stdout identities are `0eb2c8f7…7ac0` and
`a54991c4…d27a`; stderr is empty. This is the lane's completed-work green terminal, not exit `2`.
`[P37: recomputed for the producer terminal and detection set; institutionally_supplied for the
declared hang fence]`

### GY-DEFC-5 Depth v2 — source-bound census non-receipt and legacy-order closure

The first real-owner Depth census after the accepted N10a reissue ran from clean attached head
`8829bbe9b`. It completed in `1,329.369582` s under the recomputed `1,695.177568` s rederive cap,
exited `1`, and did not time out. The tracked status was empty before and after, and the governed
Depth artifact remained exactly `1,841,810` bytes at SHA-256 `acc252579…f089`. Meta, stdout and
stderr identities are `09f153bc…4f78`, `cb12b347…a272`, and `7424c1f8…a031`. External heavy
processes were permitted to overlap under the user's parallel-execution ruling; no cap was raised
and no second PolicyOS writer/scanner-heavy process was launched. `[P37: recomputed for the
terminal, cap, head/status and byte boundary; institutionally_supplied for the overlap rule]`

The complete retained exception chain is:
`census.main → _build_live_payload_with_plan(lane="cached") →
_complete_payload_from_recordings → _domain_run_and_normalized_recording →
_reconcile_controlled_recording → reconcile_gy_comparison_projection → plan.project(previous) →
_controlled_recording_verification_semantic_projection →
canonical_promotion_receipt_semantic_projection →
ValueError("promotion_comparison_semantic_ledger_missing")`. The frozen v1 receipt intentionally
lacks the new v2 semantic projection, while the ephemeral live plan already owns a canonical
legacy migrator. The generic comparator projected the raw v1 custody bytes before invoking that
migrator, so the owner proof could never align the two versions. This is the same authorized
recording-level comparison mechanism, not a third mechanism and not an artifact reissue. The live
census remains unaccepted and its predicted Depth delta remains `not_established` until a frozen
source batch passes review and the real-owner census closes. `[P37: independently_reconciled for
the causal classification; not_established for the post-repair census and accepted Depth state]`

Red-first work isolated two properties. First, a focused PDC witness supplied a raw v1 admitted
block whose v2 projector fails with `semantic_projection_missing`; before the change,
`reconcile_gy_comparison_projection` failed on that projection instead of running the producer's
legacy migrator. Second, a governing-input mutation caused the migrator itself to raise raw
`legacy_governing_input_mismatch`, bypassing the typed comparator diagnostic. One intended RED
assertion was initially inserted into the older migration test by an ambiguous patch context and
therefore passed without exercising the raw-migrator path; it was rejected as an authoring
non-receipt. After moving it to the dedicated witness, the exact test exited `1` at the raw
migrator error. `[P37: recomputed for the observed test terminals; not_established for a retained
receipt of the two direct RED invocations]`

The minimal source closure keeps the producer-owned vocabulary and custody boundary unchanged:
`reconcile_gy_comparison_projection` now applies the live plan's path-bound legacy migrations to
the frozen value before semantic projection and shape comparison. A migration `ValueError` is
wrapped as named `gy_operational_reconciliation_semantic_projection_mismatch` with the original
owner error retained as its cause. Raw preservation still runs through
`preserve_admitted_blocks(previous, current)`; no receipt is deleted, truncated, self-admitted or
rebaselined. Current source/test identities are `70806b35…0a69` and `5531a101…bc52`, and the
tracked diff contains only those two paths plus this journal. `[P37: recomputed for the diff and
source identities; not_established for frozen-review and live-census acceptance]`

The complete PDC contract file passes `49/49` under the ordinary interpreter in `1.507756` s;
meta/stdout identities are `b9325862…336c` and `34885ca5…164`. The focused Depth owner,
recording, governing-change, envelope-reissue and proof-delegation set passes `10/10` under the
existing receipt interpreter in `55.017483` s; meta/stdout identities are `83d87e2e…b0cb` and
`7040371a…4103`. Both runs exited `0`, did not time out, kept their source pins exact and emitted
empty stderr. Ruff reports `All checks passed!` for the two changed source/test files.
`[P37: recomputed]`

An ordinary-interpreter combined PDC/Depth collection is a setup non-receipt, not a product test:
it exited `2` in `1.900840` s because Depth's executable preflight resolved Homebrew Python rather
than the required receipt-venv prefix. It did not time out or alter either source pin. Meta/stdout
identities are `40676eb9…a45f` and `73de3b5b…e3c3`; stderr is empty. Generic PDC tests therefore
remain ordinary-interpreter evidence, while the Depth executable tests use the already-preserved
receipt interpreter; no environment was rebuilt. `[P37: recomputed]`

The first frozen source commit was `974036d4e`. Three independent Terra tracks reviewed authority,
generic correctness, and live-census readiness. The wave track found the retained harness structurally
ready, but the authority and correctness tracks each independently reproduced two Important generic
contract defects: the legacy migrator ran once during explicit alignment and again inside raw
preservation, so a stateful/single-use owner could reject or leak an untyped second-call error; and
post-migration diagnostics labelled the ephemeral aligned value as `expected_frozen`, giving that
operand role the wrong content identity. The source batch therefore remained frozen but unaccepted,
and no live census was launched from `974036d4e`. `[P37: independently_reconciled for the review
findings; not_established for source acceptance]`

Delta TDD made both findings executable. A call-count migrator that raises on invocation two failed
at the second call, and a post-alignment governing mismatch reported aligned identity
`sha256:8ca8f030…2e96` instead of raw frozen identity `sha256:2f9a7f93…065e`; the two-test RED exited
`1` with both failures. The plan now has one internal aligned-preservation seam: public callers still
receive migrate-then-preserve behavior, while the generic reconciler passes its already-aligned value
to that seam and invokes the owner migrator exactly once. Every typed diagnostic again compares raw
`previous` with raw live `current`, so `expected_frozen` binds the actual custody operand even though
the gate decision uses the producer-aligned projection. No artifact owner, admission rule, receipt or
ledger scope changed. `[P37: recomputed]`

After the delta, the complete PDC contract passes `50/50` in `1.558073` s; meta/stdout identities are
`ea28ca7d…0cda` and `5952b218…8a79`. The same focused Depth set passes `10/10` in `54.003392` s under
the receipt interpreter; meta/stdout identities are `dcd69e46…0bf3` and `7040371a…4103`. Both runs
exited `0`, did not time out, preserved source pins and emitted empty stderr. Ruff and diff hygiene
pass. Final pre-review source/test identities are `82385b5c…dc6d` and `a3013e79…9f2`.
`[P37: recomputed; not_established for delta-only review and live census]`

The delta was frozen at `c1a4df93b`. Authority and generic-correctness delta reviews closed their
prior findings with no remaining Critical or Important issue, but the wave review traced one more
double invocation in the real Depth bridge: `_domain_run_and_normalized_recording` explicitly
migrated the frozen recording, then passed the same raw frozen value to the canonical reconciler,
which correctly migrated it again. This was not exercised by the generic call-count witness and is
the actual `prior_admission` path used by the live census. No census ran from `c1a4df93b`.
`[P37: independently_reconciled; not_established for source acceptance]`

A Depth integration witness now gives its fixture owner a single-use migrator and runs the cached
`_domain_run_and_normalized_recording` bridge. Before the bridge change the selected two-case test
exited `1`: the admissible historical-rederive case reached
`depth_recording_legacy_migrator_called_twice`, wrapped by the named controlled-replay comparator;
the unrelated fail-closed graph-binding case remained green. The bridge now delegates the only
alignment to `reconcile_gy_comparison_projection` and derives the envelope-reissue predicate from
whether that canonical result differs from the raw expected recording. This retains raw diagnostic
identity, canonical projection/shape checks, exact root preservation, and the dependent authority
envelope reissue while removing the second bespoke migration call. `[P37: recomputed]`

The expanded focused set covers `12/12` recording owner, replay bridge, governing-change,
single-call, envelope-reissue and proof-delegation witnesses. It exits `0` in `54.189037` s under
the receipt interpreter, without timeout or pin movement; meta/stdout identities are
`e93b0a46…dd41` and `eb27a136…2663`, stderr empty. Ruff and diff hygiene pass. Bridge/test identities
are `c485c5d3…fe96` and `693429c8…b0ec`. `[P37: recomputed; not_established for final review and
live-census acceptance]`

### GY-DEFC-5 Depth v2 — `live3` proof-source/aligned-current non-receipt

The reviewed bridge batch was frozen at `1f7d549c0`, with all three Terra reviews clear, before the
next real-owner census. `live3` ran from that clean attached head for `1,509.7816475` s under the
unchanged `1,695.177568` s cap, ended at child/wrapper exit `1`, and did not time out. Its governed
Depth pin was byte-identical before and after: `1,841,810` bytes at
`acc252579bb92ec1fcc7899ea73cf22a41154ceb68d249c135bca457a153f089`. Meta/stdout/stderr identities
are `3abaa2ef…897b4`, `6acee51f…c2e`, and `f196ac36…54e8d`. External heavy processes were allowed to
overlap under the user-supplied parallel-execution ruling; no cap was raised and no second
PolicyOS-owned writer/scanner-heavy process was launched. This completed semantic failure changed
zero governed bytes and consumed neither the Depth accepted-reissue allowance nor the cold-N11
allowance. `[P37: recomputed for head/status, cap, terminal and byte boundary;
institutionally_supplied for overlap and allowance semantics]`

The complete failing route is `census.main → _build_live_payload_with_plan(lane="cached") →
_reconcile_artifact_records → comparison_plan.preserve_admitted_blocks →
migrate_legacy_recording → receipt_plan.migrate_admitted_blocks →
canonical promotion migrate_legacy`, which raises `ValueError("live_receipt_drift")`, then
`promotion_legacy_comparison_semantic_mismatch`, then
`controlled_recording_legacy_comparison_semantic_mismatch`, and finally
`UniversalityContractError`. The live per-role bridge snapshots a proof-bound direct-live recording
before reconciliation, then returns an aligned recording that deliberately retains frozen raw
receipt custody plus the newly admitted semantic projection and reissued enclosing identities. The
nested receipt plan is correctly bound to the first value, while the outer recording admission is
correctly exact-bound to the second. Artifact migration incorrectly supplied the aligned receipt as
the nested canonical migrator's current operand, so that owner correctly rejected it as different
from its proof-bound direct-live receipt. Three independent read-only tracks reconciled the same
two-level topology from source and the retained stack. This remains the authorized recording-level
owner mechanism, not a third bespoke mechanism. `[P37: independently_reconciled]`

The minimal closure therefore preserves both bindings rather than choosing one. The outer legacy
migrator first validates and requires its callback current to equal the captured aligned recording,
with named cause `controlled_recording_aligned_current_drift` on mismatch. It then migrates each
frozen nested receipt against the captured, canonical-proof-bound source receipt, and finally
compares the migrated root semantic projection with the captured aligned projection. Migration
still begins from the frozen previous payload, so raw receipt custody is retained; the direct-live
receipt is an owner proof operand, never replacement artifact bytes. No ledger rule, scope,
denominator, admission outcome or promotion-owner check changes. `[P37: recomputed for the code
shape; independently_reconciled for the authority/custody disposition; not_established for frozen
review and live-census acceptance]`

A source-bound pre-fix tree makes the exact topology RED. The focused witness builds strict nested
admissions that accept only their proof-bound live receipts, then gives the outer admission a
distinct aligned frozen-raw recording. Against pre-fix source it exits `1` in `22.996992` s, without
timeout, at the expected nested `live_receipt_drift` wrapped by
`controlled_recording_legacy_comparison_semantic_mismatch`; meta/stdout/stderr identities are
`f515cc92…f3a3`, `3f88f8e6…5f7`, and empty `e3b0c442…b855`. Two preceding isolation-harness attempts
are setup non-receipts: the first extracted no product subtree and exited `4` in `1.342457` s
(`5cc96db0…761b0` / `bcdeed80…1cbb23`); the second extracted the subtree but failed to apply the
dirty witness into it and exited `4` in `22.736805` s (`34c9456c…2961c` /
`29360be9…9a880`). Neither timed out or exercised the property. `[P37: recomputed]`

After the closure, the same witness passes and its forged-aligned-current negative reaches the new
named cause. The expanded focused Depth set passes `13/13` under the receipt interpreter in
`86.176092` s, exits `0`, does not time out, and emits empty stderr. Meta/stdout/stderr identities
are `67ef2103…2c60f`, `cfc14fd2…feb9`, and empty `e3b0c442…b855`. Ruff and diff hygiene pass. The
validator/test identities are `7bdfee3f…c8f3` and `13d8dccc…f29`. `[P37: recomputed;
not_established for frozen-review and replacement-census acceptance]`

The source batch landed at `7a259daa6`. Three independent Terra delta reviews then closed with no
Critical or Important finding: authority/P32, exact two-level correctness, and wave readiness all
recomputed the proof-source/aligned-current split and retained raw-custody boundary. The ignored
live-census harness and cap wrapper identities at launch were `5c747949…fdd8` and
`d0580d1f…b9adf`. `[P37: independently_reconciled for review; recomputed for source and harness
identities]`

Replacement census `live4` started from clean attached `7a259daa6` with the receipt interpreter and
the same exact Depth pin. The cap wrapper terminated it at the governed rederive cap: elapsed
`1,695.388880` s against `1,695.177568` s, `timed_out: true`, child terminal `-15`, wrapper exit
`124`. It had not serialized `candidate.json`, `summary.json`, `artifact-delta.jsonl`, projection
rows or raw-preservation rows. The governed Depth file stayed exactly `1,841,810` bytes at
`acc252579…f089`, and branch/head/status remained attached, unchanged and clean. Meta/stdout/stderr
identities are `803bc800…ae9b2`, `f0849dc8…d591f`, and `8fd09465…78c5`. The retained stdout shows
the process was still inside registry/replay construction at termination rather than a semantic
terminal. This is a cap-measuring non-receipt with zero changed bytes and consumes no accepted
Depth reissue or cold-N11 allowance. `[P37: recomputed for cap, terminal, missing outputs and byte
boundary; institutionally_supplied for allowance semantics; not_established for the cause of the
runtime overrun and for the Depth candidate]`

The user-supplied parallel-execution ruling remains binding: external overlap is an execution
covariate, not a reason to wait indefinitely. The post-terminal process census showed no other
PolicyOS writer/scanner-heavy lane live. The pre-authorized B4 replacement therefore remains one
PolicyOS-owned heavy process under the unchanged cap; it does not infer a larger budget from the
killed duration and does not claim that contention caused `live4`. `[P37: recomputed for the
post-terminal process census; institutionally_supplied for the replacement/parallel-execution
rule; not_established for historical contention during live4]`

### GY-DEFC-5 Depth v2 — B4 terminal and stop

The one authorized B4 replacement, `live5`, ran from clean attached `93a6ba2d8` under the same
receipt posture and unchanged `1,695.177568` s cap. It reached the cap after `1,695.515096` s;
the wrapper recorded `timed_out: true`, child terminal `-15`, wrapper exit `124`, and no launch
error. The tracked status and head were exact before and after, and the governed Depth pin again
remained `1,841,810` bytes at `acc252579…f089`. No `candidate.json`, `summary.json`,
`artifact-delta.jsonl`, `projection-leaves.jsonl` or `raw-receipt-preservation.jsonl` was produced.
Meta/stdout/stderr identities are `28edbd24…56b1a`, `3dbd9d05…15c5e`, and
`ae24c9fc…02659`. `[P37: recomputed]`

The retained stdout ends in registry/replay construction and does not provide a semantic terminal.
Accordingly `live5` is a second cap-measuring non-receipt, not a completed lane sample, source
verdict, candidate verdict, semantic/reconciliation verdict or accepted artifact reissue. The
replacement was launched without waiting for external host-wide quiescence, but there is no
interval-wide process ledger that establishes whether or how contention affected it. `[P37:
recomputed for the missing terminal artifacts; not_established for the overrun cause, interval
contention, source correctness, candidate content/validation/delta and semantic path reached]`

B4 is now exhausted: `live4` was the first alone-at-cap finding and `live5` the single authorized
replacement. No third census and no cap increase are permitted. The smallest next closure is a
separately priced timing/execution slice that obtains a completed source-bound live-owner census
under an architect-ratified fence or changes the census' performance without changing its
comparison semantics; it must preserve the same exact source, 353-artifact byte, 3-role/10-receipt,
6-plan-entry, raw-custody and complete-delta predicates. That closure is described, not performed.
`[P37: institutionally_supplied for B4 exhaustion and next-authority boundary;
not_established for any replacement cap or performance diagnosis]`

Because no Depth candidate exists, the complete expected delta cannot be declared, no canonical
Depth writer or its three verification lanes may be launched, and the accepted Depth reissue
allowance remains unused. The task orders the posture gate and single cold N11 only after Depth
closes; neither was launched. Therefore `owner_bundle_loaded` remains `not_established`, the sole
cold-N11 allowance remains unused, and GY-DEFC-5 stops at the B4 Depth lane rather than paying a
cold run known to lack the prerequisite closure. `[P37: recomputed for output/run absence;
institutionally_supplied for ordering and allowance semantics; not_established for the objective]`

The final governed timing report is `0970d875…8d0e5` and still recommends
`1,695.177568` s for Depth rederive from one admissible successful sample at `847.588784` s; killed
`live4`/`live5` records are absent from that sample set. It continues to recommend
`4,942.540412` s for a canonical Depth writer, but that lane was never entered because the
pre-write source-bound delta gate did not close. `[P37: recomputed]`

Orchestration remained three independent Terra tracks: authority/P32, correctness and wave
readiness. They reviewed the frozen source batch independently, then prepared the live-census
acceptance, Depth verification and one-build N11 protocols while the serialized heavy process ran.
Only one PolicyOS-owned writer/scanner-heavy process was live at a time; no Sol agent was used.
`[P37: consumer_asserted for orchestration history; recomputed for the final live agent/process
state only]`
