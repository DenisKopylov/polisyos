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

Checkpoint `87908174d19b4ce08cb1763ca037d9230927feae` preserves those verified
report transitions and their complete deciding outputs. Before committing,
porcelain identities independently matched changed/untracked path identities
and the attached branch was verified; afterward all 82 changed blobs were read
from that branch and matched the worktree byte-for-byte, with a clean tree.

`corr-evidence/shared/final-inventory-sync.json` is RC 0 in 11.282 seconds for
the existing inventory owner with `--skip-deep-import-baseline`. No deep-import
baseline is changed. The normal final architecture check is held until B's
remaining report writes finish: its generated-probe phase snapshots git-visible
files, so that phase and B's report/evidence writes share a real mutable resource.
The expensive verification wave will run once after that writer freeze.

The independent inventory review reconciled the complete touched facade exports
and entrypoints against the generated inventory, checked actual lazy targets,
and matched generated-family ownership, commands and epoch descriptions. Root
read the generated diff back and marked the release fragment's inventory review
complete. This is review of the inventory; it does not substitute for the final
architecture check or for any runtime authority claim.

## Built mechanisms and their falsifiers

- **A — refusal sensitivity, input-only frame, admission budget.** Existing
  CG1/CG2/calibration owners emit and recompute the dated declarations and result;
  the frame derives tiers from input and reconciles independent source clusters.
  The durable CG2 ledger charges admitted bindings, preserves replay identity,
  and degrades to candidate custody when exhausted. Wrong refusal-reason,
  paired-sign, frame-content, candidate-charge, cap, event-binding and synthetic
  authority removals go red with the valid controls retained. A's journal links
  the complete targeted sets and saved-result drift checks. The bound source
  loader also rejects false time/schema/hash declarations through the real owner.
- **B — subject-aware correspondence on independently addressed marked inputs.**
  Foundry's recognition owner and the existing S3 bridge preserve the semantic
  subject dimension before numeric comparison, persist/revalidate the result,
  and carry it to the real credal and atom consumers. Correct source-relative
  pairs pass; real budget/tax transpositions fail; missing subjects remain
  ambiguous before numeric evaluation; synthetic input never authorizes the
  governed surface. Removing comparison or forwarding fails the unchanged
  positive/negative controls. Real authority remains outside this demonstrated
  source-relative result, with both missing requirements explicitly routed below.
- **C — bounded current-rule extraction and N4→N6→N9 custody.** DataForge's
  existing raw, normalization, graph and exact/family/contested owners consume
  declared marked subset data while preserving evidence axes and ancestry.
  N6 retains actual atom/proposal/Trinity objects, shared WMR/substrate and run
  budget through persistence and reentry, then supplies the existing N9 intake.
  Resealed source, wrong profile, changed writer projection, source-epoch and
  ancestry removals fail. The real provider attempt is a refusal, so these
  controls do not claim a newly extracted authentic reference or a protected
  positive. N6/N9 current report checks and actual saved corruption are retained
  separately from their synthetic mechanical controls.

## Findings owned elsewhere, kept separate

- **Accepted-binding calibration:** `delta-ground-composition-and-stratum-budget`
  and `cg2-calibration-observations-per-stratum` retain the missing accepted
  labels/independent calibration evidence (`artifact_missing`). A's frame is a
  campaign input. `adversarial-refusal-sensitivity-is-publishable-today` governs
  the separate publishable sensitivity result; it supplies no correctness bound.
- **Real legal membership:** `CORR-B1` /
  `lever-legal-subject-key-in-the-norm-namespace` needs independently sourced
  real memberships. **Authority verification is a different requirement:**
  Foundry/GY-S3 correspondence admission under S0-K06/P32/P37 still needs an
  accepted-provenance verifier. A narrower owner is explicitly unallocated;
  the architect allocates it. Neither requirement is supplied by self-declaration
  or by relabelling a synthetic source.
- **Authentic Academic reference:** HC-F11–HC-F14 and
  `claim-level-evidence-axis`, with GY-PR1/C2 as consumer, retain current-rule
  confidence withholding and the absent newly yielded source-bearing N4 input.
  **CORR-C1's external quota dependency** prevents measuring the live full-pass
  cost; it requires usable quota on the declared account/model. **CORR-C2's
  protected-admission boundary** independently lacks an authentic protected
  batch. The built preservation chain is not labelled absent because these
  authentic inputs are missing.
- **Original proof-source custody:** GY-S3 / CG2–CG3 proof-input lifecycle,
  P07/P29, owns distribution of the original CAS and referenced registry to
  another station. Equal logical content with a fresh timestamp is insufficient.
- **Existing measurement-removal harness:** GY-PR1's N9 source-flip owner, P38,
  must replace its unqualified `del receipt` proxy with an owner-scoped semantic
  witness. That retained entry has no behavioral credit in this handback.
- **Resolved/historical companions:** the closed
  `evidence-class-normalizer-zeroes-two-canonical-classes` row needs only the
  appended requirement correction already made here; its algorithm is untouched.
  The CG2 tuple/list warning belongs to deliberate invalid attack-control
  construction in `check_grounding_bind_contract`, not a production escape.
  Legacy Academic zero-default USD compatibility bookkeeping has **explicit
  nowhere** in the new actual-cost accounting; it is never used as measured cost.
  Setup failures, timeout ceilings, fixture store locators and helper lint remain
  recorded with their CORR verification owners, not exported as product debt.

These are proposals/routings for architect transcription. Neither forbidden
register file is edited and its debt-ledger checker is not invoked.

The read-only adjacent CG5 report position is now measured in
`corr-evidence/b/cg5-current-position.json` (RC 1, 40.862 seconds). Its actual
canonical reference producer reaches `Academic.require_forwardable_confidence`
and refuses under HC-F11–HC-F14 because the current claim evidence axis is absent.
It does not reach a fresh CG5 payload, so **current CG5 report freshness is
`not_established`**. This is not called an inherited gate failure: no base replay
and disjoint-input proof was performed. The exact CG5 importer tests passed as
recorded in A's journal; the closed CG5 algorithm is not repaired or replaced.
The unmet canonical reference is routed to the existing evidence-axis/C1
requirement above, without crediting the synthetic mechanism frame as its source.

The final own-envelope audit found another present instance of the known
synthetic-emission class: S3's report constructor includes constructed controls
but omits its own synthetic marker. This is CORR's report-owner correction,
not outside debt. A suspected analogous omission in CG2/CG3 is refuted by their
actual constructors and does not authorize an unrelated bump. The appended
execution decision requires a complete changed-output census and an actual red,
preservation of S3's successfully emitted/checked v3 body in Git, then a v4
report-only correction and independent marker validation. Prior passing
behavior/corruption runs remain evidence for their actual properties; they do
not establish the newly tested own-envelope invariant. Final closure remains
pending until that correction and the final architecture wave finish.

The actual v3 S3 artifact and its pre-correction evidence are preserved at
`1fcd5aa53bff08638ffdd4c3b50df0eebf35e757`. The attached branch was verified
before committing; all 22 changed blobs were reread from it and matched the
worktree exactly. The original v3 artifact is Git blob
`adec38a93665c880896b0194458305b2de9d0839`. Its real writer/check passed, and
surgically changing only the saved task-completion claim returned child RC 1
with exactly `intervention_substrate_contract_drift` while behavior stayed valid.
The independent own-envelope red then demonstrated that absent, false and null
markers escaped when saved and live bodies agreed. That newer property is not
credited by the older freshness check. The v4 correction follows this checkpoint.

## Final S3 report correction and frozen-source checks

The v4 report correction passes its exact wrapper tests in
`corr-evidence/b/s3-own-envelope-green.json`. Independent collection and emitted
JUnit reconcile the full five-node set. Removing only the independent marker
predicate produces the intended three failures while both positive controls
stay valid (`s3-own-envelope-removal-final.json` and its identity reconciliation).
The original red's explicit failures are retained; its unreported passing
identity is `not_established`, not inferred from progress dots.

The actual S3 v4 writer/check passes in `s3-v4-write-check.json` (RC 0,
428.741 seconds). The saved task-completion corruption returns child RC 1 with
exactly `intervention_substrate_contract_drift` while live behavior remains valid
(`s3-v4-persisted-corruption.json`, wrapper RC 0, 230.500 seconds). Exact bytes
are restored to SHA-256
`cd59989eb13ebea81f80801da9c13bd22d9e9279bb57a936f578923ca07d6146`.
Independent delta review approves the source/lifecycle change with no blocking
finding; the runtime captures supply its execution evidence.

The complete product JSON census in `report-emission-complete-green.json`
(RC 0, 32.672 seconds) independently reconciles the changed-path and declared
generated-output sets. All six generated report identities agree and have
their required own marker; the formerly suspected CG2/CG3 omission is refuted.
The complete recursive and iterative S3 body comparison changes exactly
`/schema_version`, `/gy_lifecycle_marker` and `/synthetic` from the preserved v3
body. Behavior, coverage, all 16 case identities and all nine removal identities
are unchanged. This report-only epoch bump neither changes runtime law epochs
nor closes the parent GY-S3 authority conjuncts.

Final changed-Python Ruff is RC 0 in
`corr-evidence/shared/final-frozen-python-ruff.json` (0.142 seconds). The exact
argv covers the complete changed `.py` source/test/harness set. Independent
name-only/untracked and numstat/status enumerations agree on 73 paths, identity
hash `85ce6e945bc3ce88c23f5f56f94cc2a941845255049fc1f3c49d85c7234c30dc`.
The final metadata sync is RC 0 in `final-s3-v4-inventory-sync.json`
(9.809 seconds), using `--skip-deep-import-baseline`; readback shows only the
S3 v4 freshness description changed in the generated companion. Normal
architecture guardrails remain the final pending gate after all writer freezes.
