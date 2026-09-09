# CORR capability lane — completion journal

Lane `/Users/deniskopylov/polisyos/.worktrees/gy-corr`, attached branch
`codex/corr-capability`, base `9619f6d2d892d7994ae3f29d3230362c41862f2d`.
No auxiliary worktree. No push, GitHub plugin, storage stash or full suite/pass.

The [execution plan](../plans/2026-09-08-corr-capability.md) records the binding
architect decisions and write ownership before production changes. Workstream
journals are [A](2026-09-08-corr-a.md), [B](2026-09-08-corr-b.md), and
[C](2026-09-08-corr-c.md). This initial entry is not a completion claim.

## Station

The lane uses supported framework Python 3.14.0 and the frozen dependency lock.
The first [offline provisioning](corr-evidence/shared/python-provision.json)
failed on an uncached locked wheel. The [cache fill](corr-evidence/shared/python-provision-cache-fill.json)
completed without changing the lock, and [offline replay](corr-evidence/shared/python-provision-offline-verified.json)
then passed. [Workspace installation](corr-evidence/shared/node-provision.json)
uses `corepack pnpm install --frozen-lockfile`. The production-data reference is
read-only by consumer contract; every mutating data step targets lane scratch.

## Final status and handback

Pending implementation and deciding verification. The terminal table will cover
A, B and C independently, naming any critical blocker at its exact step.

Full-pass cost estimate from C1: **`not_established` — the configured provider
returned HTTP 429 `insufficient_quota` before a successful screening measurement.**
This is the result for both the held-abstract campaign and the separately
declared historical-source campaign; it is not a zero-cost estimate. The
[pilot output](corr-evidence/c/official-six.json) records a completed refusal
report, and the [declared diagnostic](corr-evidence/c/provider-diagnostic.json)
establishes the external quota failure. No full pass or provider fallback ran.

Built work/falsifiers and findings owned elsewhere will be listed separately.
DEBT/LEDGER proposals remain journal-only; their files and checker are excluded.

## 2026-09-09 continuation

The lane resumed on the expected attached branch at
`9676c000bcafcda0ccc5f9c2818052c170b67e26`. Source and evidence already produced
remain in this worktree; no replacement lane or auxiliary worktree was created.
The independent N9 delta review found an EFFECT source-body/bridge epoch
misbinding. Its red-first historical-emitter control and sole intake repair
remain pending; the current report transition otherwise passed static review,
which is not runtime verification.

The exact N9 report test file reached the 600-second capture ceiling
(`corr-evidence/shared/n9-current-reissue-wave.json`, child RC -9, capture RC 124).
The retained progress output does not establish a complete executed identity set
or a green gate. The next exact-file invocation will retain verbose test
identities, per-test durations and the existing pytest faulthandler diagnostic,
with a 1,800-second allowance based on this measured lower bound. No gate or
assertion is removed to reduce the cost.

The current C2 fixture correctly refused an incomplete WMR-only CAS replica:
its referenced registry artifact was missing. That run cannot decide the source
behavior. C has verified the exact WMR and registry bytes in the original
composed owner CAS and will use that same immutable input pin for the retry.
This does not change a production input or substitute a fixture denominator.

Lifecycle review also identified N6's stale zero-I/O description and its
scripted report's inability to demonstrate real N4 source custody. The report
companion must state the resulting limitation and retain separate actual-source
tests. N9's lifecycle source list now includes the actual credal-reference owner;
N6's list retains its existing engine, scheduler, horizon and design-search owners.
Final sync, runtime report checks and guardrails remain pending.

The subsequent C core checkpoint is
`51bbfe384ff7ed8ba7eaa1b3cbb093fe0ee949ca`. Before committing, the attached branch
was verified as `refs/heads/codex/corr-capability`; after committing, all 44
changed blobs were read back from that branch and compared byte-for-byte with
the worktree. The actual historical EFFECT producer control now reaches the
specific epoch-mismatch refusal, and the unchanged current-source control and
two historical readers pass. All five C2 property removals fail on their
intended semantic assertions. The complete earlier 24-node invocation retains
its one superseded setup failure; the exact three-node green supplies its
correction. Their collected and executed identity sets reconcile independently
in C's journal, rather than being combined into an invented clean full run.

The CG3 v2 report and its independently observed freshness failure are preserved
in `155645235e5a75b9b4053e83770df609eb26ef94`. Execution over the complete actual
source population isolated the drift to WMR creation time and its downstream
reference epoch, despite equal logical world hashes. The approved shared
CG2/CG3 report v3 repair binds the original declared WMR artifact's exact bytes,
schema, logical hash and time through the existing calibration and world-loader
owners. It does not retime the source. An unavailable original artifact is a
source-custody failure, not permission to substitute a fresh equal-logical-hash
artifact. The new producer-absence red is retained before implementation.

The exact input declaration and source boundary were then committed as
`664f22a3807ecfc7e9d54aad7a7a0bd68aafdd40`; every one of its 27 changed blobs
was reread from the verified attached branch and matched the worktree. This
checkpoint also preserves the current N6 owner-projected transition measurement
before the reissue guard is allowed to admit it. The declared input's content
hash is `sha256:8b8db9c24b9c2b78ec3e90b31ab9baf3156beba0b8a053f9bf32db993638ce08`.
It records the original WMR creation time, `2026-09-08T16:59:01.685331+00:00`;
the official v3 report runs follow this commit.

The observed N9 report/importer wave completed in 323.803 seconds, retaining
its complete output in `corr-evidence/shared/n9-current-reissue-wave-observed.json`.
Both affected production importer tests passed. The report companion failures
were a runtime-attested class method patched by its test, a missing required
comparison-plan argument, and stale source-flip locations. The first repeats
with runtime source frozen in `n9-byte-stability-frozen-source-red.json`; it is
not blamed on another lane or repaired by weakening N11. A checker-local intake
now forwards to the unchanged actual verification owner. The comparison test
supplies the real admitted plan, and the existing source-flip identities follow
the current EFFECT unknown-evidence default and delegated N6 decision-front
owner. `n9-companion-delta-green.json` records their exact green in 142.735
seconds. The unchanged runtime guards remain in place. Complete test identity
reconciliation and the actual retargeted removals are separate pending evidence.

An incidental existing source-flip entry has a separate home and no behavioral
credit in this lane: `source_flip_invented_measurement_marker_reintroduced`
still searches for the unqualified text `del receipt`, which now occurs in
`promotion_sequence._rebind_promotion_receipt_to_ledger_head`, not the
measurement obligation owner. Its structural marker test can therefore pass
while selecting the wrong semantic owner (P38). Route this to GY-PR1's existing
N9 source-flip harness owner, with the required closure being owner-scoped
replacement and a real measurement-authority refusal/removal witness. No full
source-flip suite is claimed by the report's retained mutation-ID index or by
the structural inventory. CORR's new custody and synthetic-authority removals
carry their own actual evidence. The two retargeted companion removals remain
pending until their separate runtime captures decide them.

The source-authority strangle is now an executed counterfactual, retained in
`corr-evidence/shared/n9-source-authority-strangle.json` (wrapper RC 0,
36.466 seconds). The unchanged real resolver refuses the marked source; removing
only its synthetic-ancestry refusal makes the same candidate/problem and source
mechanism established, and the unchanged assertion fails with child RC 1.
The emitted receipt records `default_flipped=true`, the complete matching
bindings, and content hash
`sha256:e753137a5adbf06217e7fa46328e9aa02b7b502623587eaf5cd2458a4cf06d7a`.
`n9-input-identity-removal.json` separately returns RC 1 in 31.961 seconds at
`n9_contract_input_was_authored_after_real_binder_returned` when a fabricated
closed obligation is appended and rehashed after the actual binder returns.
Both retain the markers while removing the deciding property.

Exact proof-world distribution has the explicit home **GY-S3 / CG2–CG3
proof-input lifecycle**, under P07/P29. The declaration addresses held original
CAS bytes and their referenced registry, available in this lane; a fresh station
needs that supplied store. Missing original bytes cause a source-custody refusal.
This is a distribution/custody requirement, not a new dataset acquisition,
authority grant, or permission to rebuild a different timestamp under the same
logical hash. No substitute synthetic artifact repairs this missing pin.

The actual N9 current report writer and its independent check now pass in
`corr-evidence/shared/n9-current-report-write.json` (RC 0, 80.920 seconds) and
`n9-current-report-check.json` (RC 0, 78.029 seconds, empty issue set).
`n9-current-report-persisted-corruption.json` changes only the saved strangle's
`default_flipped` from true to false. The real checker returns RC 1 at
`promotion_legacy_contract_content_hash_drift`; this is the actual complete-body
integrity refusal, not an inferred JSON issue code or a setup exception. The
wrapper returns RC 0 in 71.268 seconds after exact-byte restoration to SHA-256
`0d159ddcf3a2174d4cf6bf32859cd93e70eacb6b2852ea000e636b5f1ecf8484`.
The separate unchanged runtime removal above decides the strangle's semantic
property; this persisted mutation decides the saved report's integrity boundary.

Complete independent pytest collection and emitted JUnit identities reconcile
for the original N9 invocation in `n9-current-reissue-wave-identities.json`:
the complete 26-node sets have identical hash
`1a9356fe5e65310a70408e6a52daacfe1253a776b9e1cdefacf41e040854eef5`, with
the same three explicit companion failures retained. The exact correction set
is independently reconciled by `n9-companion-delta-identities.json`: its three
collected/executed identities agree and all pass. No missing, duplicate,
unexpected or ambiguous execution is hidden by combining those receipts.

The complete changed Python path set, including source, tests and journal
harnesses, is passed as explicit argv to
`corr-evidence/shared/final-changed-python-ruff.json`. Its RC 1 named only the
older B baseline/census helpers. Their lint-only correction preserves the
historical source/output citations; the unchanged complete Ruff invocation then
passes in `final-changed-python-ruff-green.json` (RC 0). No production behavior
or test denominator changes to satisfy this check.

The retargeted source-removal controls are now decided. Their unchanged happy
paths pass in `n9-retargeted-controls-green.json` (RC 0, 66.021 seconds), with
the complete two-node collected/JUnit sets reconciled by
`n9-retargeted-control-identities.json`. The existing real source-flip owner
then runs exclusively with the lane venv first in `PATH`:

- `n9-effect-default-source-removal.json`: RC 1, 85.330 seconds; missing EFFECT
  evidence becomes `satisfied` and the unchanged `UNKNOWN` assertion fails.
- `n9-decision-front-source-removal.json`: RC 1, 93.177 seconds; bypassing N6's
  actual delegated receipt revalidation promotes the forged candidate to
  `decision` and the unchanged `research` assertion fails.

Both retain complete child output and independently read back exact restoration
of the source bytes. These are the two actual semantic reds previously marked
pending, not evidence for the separate unmodified measurement-harness residual.

C's final N6 companion is recorded in the C journal: complete final test
identities reconcile, the actual writer and independent checker pass, and
removing the complete-binding guard admits an unrelated rehashed governing
value while the genuine current control stays valid. Its separate persisted
`/synthetic` corruption returns child RC 1 at
`generation_cycle_legacy_contract_content_hash_drift`, with the original bytes
restored exactly. The report derives its own synthetic marker from the actual
run and leaves scripted source preservation `not_established`. No scripted
report is credited as the authentic N4 input that C1 did not yield.
