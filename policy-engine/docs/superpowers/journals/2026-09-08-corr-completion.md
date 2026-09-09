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

The S3 v4 checkpoint is `778d8ce6b3be5a1730bbd3b10b7af5cf72c5aebe`; all 27
changed blobs were reread from the verified attached branch and matched the
worktree, with a clean tree. The first final normal architecture check then
returns RC 1 in 240.193 seconds (`final-architecture-guardrails.json`). Its
complete output reports three new deep imports, one OpenAPI probe CAS write
outside assigned scratch, and stale OpenAPI/trust-posture outputs. These are
owned closeout findings under P27/P29/P41, not a passing check or inherited debt.
The appended plan resolves facades without baseline acceptance and measures
both generated-output deltas before changing their companions.

## Guardrail delta evidence

The three new deep imports are corrected through their declared owners. IR's
existing facade lazily re-exports the unchanged `ArticleExtractionResult` and
`TrinityBundle` classes; C's two imports use it. B uses Core's existing
`artifacts` facade, preserving exact classes and the complete proof-input model
schema. The C and B journals retain independent owned-edge/class-identity
measurements and their passing affected behavior controls. No import baseline
or exception changes.

The real exporter confinement test is red in
`corr-evidence/shared/openapi-output-boundary-red.json` (RC 1, 69.225 seconds):
it produces a valid complete OpenAPI schema but writes the existing
`chronology.open_world_risk_verifier` code artifact and manifest outside assigned
output. The repair passes the existing app factory a temporary CAS beneath
that output, leaving the factory and closed verifier untouched. The same test
is green in `openapi-output-boundary-green.json` (RC 0, 64.455 seconds), with its
complete single-node identity independently reconciled.

`openapi-output-strangle.json` emits a recomputed `StrangleReceipt` (RC 0,
60.560 seconds), content hash
`sha256:34a063dcd37bb5c28a6325d1a41c7cf00afe47061c6a3565f7bbd283ee2a1610`.
Two fresh working directories run the actual exporter. Removing only its CAS
binding restores outside writes; both paths produce the identical valid schema.
Independent rglob/os.walk file identity sets agree, and the current path leaves
only the assigned schema. The default flip is observed, not declared.

IR's existing facade/catalog importer wave initially fails only its generated
catalog freshness check. The complete 24-node identity set is reconciled with
that failure retained. The canonical catalog owner regenerates the two affected
reference documents, changing only the two newly exposed classes' public
classification and derived totals. The unchanged exact importer wave then
passes (RC 0, 5.929 seconds), independently reconciled at the same 24 identities
(`ir-facade-importer-green.json`, `ir-facade-green-identities.json`).

Independent complete comparisons in `trust-posture-companion-measurement.json`
find only source content/line and derived digest changes; all public claim
identities, authority predicates and posture states remain equal. The existing
writer regenerates that companion in `trust-posture-current-write.json`
(RC 0, 37.690 seconds). No closed trust-posture algorithm is changed. The
initial complete OpenAPI comparison (`openapi-complete-initial-delta.json`)
likewise retains every JSON identity and changes only the DS17 negative
example's dependency/receipt bindings. The example must be recomputed again
from the final committed source basis; no value is hand-edited into the schema.

Final source-delta Ruff passes over the complete independently reconciled
changed Python set in `final-guardrail-delta-python-ruff.json` (RC 0, 0.112
seconds). Its 79 paths have identity hash
`5a67577664cddfbaa5d6370c98c98ae81a4bd9cc07c4c5770b888948b8c584b6`.
The no-baseline metadata sync also passes (`final-guardrail-delta-inventory-sync.json`,
RC 0, 8.735 seconds). Independent delta review approves the facade and exporter
changes; root read back the generated inventory and exact two-class catalog diff.
All remaining work is current generated-artifact verification and final normal
guardrails, followed by terminal status/branch delivery.

The trust-posture owner independently checks the regenerated companion in
`trust-posture-current-check.json` (RC 0, 38.836 seconds). The first saved
corruption attempt selected a string digest, which the scalar-only probe rejects
before writing; `trust-posture-persisted-corruption.json` is a harness setup
nonreceipt. The actual numeric-token probe in
`trust-posture-persisted-corruption-numeric.json` returns wrapper RC 0 in 43.008
seconds: changing only `/ast_derivation/scanned_python_count` from 138 to 0
makes the real owner return child RC 1 with `DS11-GENERATED-DRIFT`. Exact bytes
are restored to SHA-256
`9ef1d7d3c72f8fdd2e5a3737666c6fcc1fe40fcf5814d9f6943b6eaeb5205d7f`.
The failure/repair register was reread before this closeout boundary; the
facade, scratch confinement and generated companion findings are resolved here,
not assigned to another lane.

The final source/facade/exporter/trust checkpoint is
`680decaa9a1aab96375cedb1fba109d03e460061`. Its 53 changed blobs were read
back from the verified attached branch, byte-exact, with a clean tree.
The actual OpenAPI exporter then regenerated the canonical schema in
`openapi-current-write.json` (RC 0, 64.652 seconds). Independent recursive and
iterative enumeration in `openapi-complete-final-delta.json` (RC 0, 0.387
seconds) reconciles all 57,290 typed JSON identities before and after. Exactly
ten existing negative-example values change: the current source dependency
count/digests and their bound receipt/projection/replay values. Operations,
DTOs, packet rules, authority states and negative payload semantics are equal.
The current schema SHA-256 is
`ee4f75754f8161dd2ad21360babb944d40f3654e13f0869ad10186145caf07b7`;
the old body is cited at `schemas/runtime_api_v1.openapi.json@680decaa9a1aab96375cedb1fba109d03e460061`,
not copied into a derived artifact. The existing Runtime API contract checker,
including its generated-client comparison, passes in `openapi-current-check.json`
(RC 0, 64.570 seconds). No generated client is hand-edited.

`openapi-persisted-corruption.json` then returns wrapper RC 0 in 65.502
seconds. Changing only the saved example's `bound_dependency_count` from 6352
to 0 makes the unmodified real API checker return child RC 1 for OpenAPI drift;
its full diff names exactly that token. The helper restores the exact current
schema bytes. The exporter confinement removal is the separate runtime
property witness; this saved mutation proves freshness refusal, not authority.
No source changed after the final changed-Python Ruff. Normal architecture
guardrails will now run with every writer frozen and no baseline or exception
acceptance.

## Terminal handback — 2026-09-09

This section supersedes the earlier chronological pending/readiness statements.
The status applies to the requested CORR mechanisms; it does not close the
whole parent GY-S3 or GY-PR1 authority task.

| Workstream | Final status | Deciding evidence and falsifier |
| --- | --- | --- |
| A — refusal sensitivity, pre-outcome frame, admission-only risk ledger | `executed` | The complete declared suite/frame and current CG2/CG3 reports recompute; source-identity, refusal-reason, admission-charge, exhaustion and synthetic-authority removals go red while valid controls remain. Actual N4/controller/reentry forwarding retains the same run budget handle. See A's final mechanism evidence and the saved-report corruption captures. Accepted-binding calibration remains `artifact_missing`; no correctness number is published. |
| B — subject-aware legal correspondence on marked synthetic sources | `executed` | The existing Foundry/S3 owners admit correct source-relative pairs, reject real budget/tax transpositions, and decide missing subject as ambiguous before unit comparison. Comparison/forwarding/ancestry removals and the saved S3 v4 corruption fail. Synthetic or unverified sources cannot grant authority. Real membership and accepted-provenance verification remain separately routed; parent GY-S3 authority acceptance is `not_established`. |
| C — current-rule subset re-extraction and N4→N6→N9 preservation | `blocked` | C1's subset pipeline and synthetic refusal are verified, but the declared live screening provider returns HTTP 429 `insufficient_quota`, before successful token/wall/cost measurement. C2's preservation mechanism is `executed`, including persistence/reentry, historical epochs, actual-owner handoff and removal probes. No authentic new reference or protected-admission batch was manufactured. |

**Full-pass cost estimate from C1: `not_established` for both declared campaigns.**
The quota refusal yielded no successful screening usage; failed-request timing
and synthetic execution are not a full-pass cost estimate. The external change
needed is usable quota on the declared account/model, followed by the already
bounded pilot and its cost calculation. No full pass, fallback provider or
further provider attempt ran. C2's authentic reference/source-bearing N4 input
and authentic protected-admission batch remain distinct missing inputs.

The final normal architecture check is recorded below with its actual status.
No directory-wide test suite, optional full generated-check suite, forbidden
register edit, debt-ledger checker, push, rebase, stash or auxiliary worktree was
used. The earlier setup failures and corrected red gates remain in the record;
they are not aggregated into an invented clean test run.

The separate **Built mechanisms and their falsifiers** and **Findings owned
elsewhere** lists above remain the handback inventory. The final guardrail
corrections add existing-facade wiring and exporter scratch confinement, whose
real removal restores escaped CAS writes with an identical valid schema.
Trust-posture and OpenAPI companions are recomputed by their existing owners;
saved corruption rejects and restores exact bytes. Those resolved CORR findings
do not become another owner's debt. Independent terminal review found no new
status, cost, canonical-authority or unallocated-finding contradiction.

The final normal architecture check in
`corr-evidence/shared/final-architecture-guardrails-replay.json` is **RC 0,
242.686 seconds**, from committed checkpoint
`a18eb663e6476a776a330de9de4b64e40790174a`. All six changed blobs at that
checkpoint were read back from the attached branch, byte-exact and clean.
The check confirms freshness for OpenAPI, the runtime API client, dashboard API
types and trust-claim-posture. Its complete output is retained. No import
baseline, exemption or gate scope was changed. The standalone Atlas retirement
gate is explicitly not part of this normal check and receives no credit here.

The final code Ruff and targeted importer/semantic gates are recorded in the
preceding sections; source did not change after those checks. Only this terminal
journal record and the deciding guardrail capture follow the frozen check.
`git diff --check` and exact branch readback accompany the final local commit.

## Continuation handback — 2026-09-09: resources and operating readiness

**Resource verdict: the isolated live API profiles show low worker CPU/RSS,
suggesting headroom for development; concurrent-workload interference and
unattended week-long stability were not measured.**
The DeepSeek and MiniMax six-input pilots used respectively **0.05292 and
0.07085 observed CPU seconds per wall second**, peaking at **589,021,184 and
595,001,344 bytes RSS**. On the measured eight-logical-CPU, 16-GiB station,
that is 0.66%/0.89% of logical CPU capacity and 3.43%/3.46% of RAM. These live
loops were I/O-bound. Longer constructed runs completed, but their warm RSS
slopes remained positive; a week-long memory plateau cannot be inferred.
The separate graph stage consumes approximately one core and substantial write
I/O, so it must be scheduled separately from the API loop.

This continuation supersedes the earlier C1 account-quota/cost-only handback.
It measures **different models from the original OpenAI declaration**. The
original declaration, both failed attempts, and quota diagnosis remain history.
Original A, B and C2 remain `executed` and closed. No full extraction pass or
graph over the held corpus ran. There was no new lane, worktree, push, GitHub
plugin, stash, rebase, register edit or debt-ledger checker.

Evidence locator: `E` below means
`docs/superpowers/journals/corr-evidence/c1-capacity/` at
**`35889915ebe8598eb1e379e64db82405ddbefbdd`**; a citation such as
`E/synthetic-retention-results.md` means that tracked path at this commit.
Earlier declarations and production owners are also preserved at
`d24655fbfb56317a4c00ca5323fd8201692e0a32`. Both commits were reread from the
attached `codex/corr-capability` branch, comparing every changed blob with the
working bytes (39 and 353 blobs respectively). These are source/evidence
checkpoints, not permission for a full run.

### Local resource measurements and memory trend

| Complete executed frame | Worker wall, seconds | Observed CPU / wall | Sampled peak RSS, bytes | Native write I/O, bytes |
| --- | ---: | ---: | ---: | ---: |
| DeepSeek pilot: original six documents | 117.346 | 0.05292 | 589021184 | 1220608 |
| MiniMax pilot: same original six | 122.444 | 0.07085 | 595001344 | 1224704 |
| DeepSeek direct extraction: 12 at concurrency 1 | 135.934 | 0.02078 | 356532224 | 606208 |
| MiniMax direct extraction: same 12 at concurrency 1 | 730.729 | 0.00392 | 355958784 | 622592 |
| Marked synthetic campaign: 100 documents | 11.166 | 0.96847 | 325386240 | 33923072 |
| Marked synthetic campaign: 1000 documents | 91.373 | 0.98946 | 327319552 | 366669824 |
| Marked synthetic graph finalization and resolution: 100 works | 4.156 | 0.9530 | 315113472 | 145620992 |
| Marked synthetic graph finalization and resolution: 1000 works | 22.029 | 0.9146 | 333103104 | 1460617216 |

CPU and write counters cover observed process lifetimes, including descendants,
and are lower bounds when a process can start and exit between samples. RSS is
the simultaneous sampled sum, not a continuous lifetime maximum. The observer
is excluded. The actual live/constructed workers had no observed descendants;
the separate child-process telemetry falsifier is retained. Native profiles
used 0.25-second sampling and recorded actual gaps and ambiguous observations.
No ambiguity is credited as zero. Source: pilot profile summaries, both
throughput primary archives, `E/synthetic-retention-results.md`, and
`E/graph-finalizer-handoff.md`, with their complete native traces.

Pilot write rates were about 10.4/10.0 kB/s. The constructed 1000-document
campaign wrote about 4.01 MB/s when network waiting was removed; its active
work window used 0.993 core. This is local processing capacity evidence, not
live-provider throughput. Its final logical stored size was 25,216,691 bytes,
while native write I/O was 366,669,824 bytes. APFS allocated blocks, logical
space consumed, and cumulative writes are different quantities. Graph writes
were about 35.0/66.3 MB/s for 100/1000 works; final owned output was
5,789,423/12,109,586 bytes. Do not extrapolate those raw-only graph shapes to
an adjudicated or densely connected graph.

Memory was measured through completed work, with startup, active processing,
final replay and shutdown separated. Removing the active-window property makes
the unchanged gate fail; including process exit incorrectly makes a declining
trace. Across every qualified live throughput sample, warm OLS slopes were
about +517 kB/completion for DeepSeek and +605 kB/completion for MiniMax. These
small live frames do not identify retained state versus warm-up.

The separately predeclared synthetic frames exercise the unchanged campaign,
SDK and local token estimator for **100/1000 complete documents and 300/3000
constructed calls**. Their peak RSS differs by only 1,933,312 bytes, while
active-window OLS slopes are +14,706/+2,035 bytes per completion. The longer
run therefore shows a much smaller positive finite slope, not an established
asymptotic bound. All 44/354 trace records were reconciled independently;
four initial checkpoint observations per run are ambiguous. Unsampled
completion bins are not zero. The inputs, responses, traces and results carry
their own synthetic provenance and grant no authority. Exact traces are
retained once; repetitive derived bins are reproducible scratch, with hashes
and compact interpretations retained in `E/synthetic-retention-results.md`.

### Throughput, failure rates and the unavailable knee

The dated throughput declaration is separate from both six-input pilots. Its
complete eligible frame is 310,710 nonblank abstracts out of 310,829 held work
identities; 119 are blank, with no missing/unreadable case silently counted as
blank. Python and SQL reconcile the complete identities and values. The frame
declares 180 different inputs per model, disjoint from the original six and
between levels, allocated as 12/24/48/96 at concurrency 1/4/16/32. Both models
use the same input identities at each level. Only the first complete level ran.

| Model, concurrency 1 | Typed successes / attempted | All-request median / p95 / p99, seconds | Success-only median / p95, seconds | Successful outputs/active second |
| --- | ---: | --- | --- | ---: |
| DeepSeek-V4-Flash-0731 | 3 / 12 | 0.811 / 56.401 / 61.886 | 50.791 / 62.011 | 0.02241 |
| MiniMax-M2.7 | 10 / 12 | 60.034 / 128.435 / 149.169 | 69.668 / 133.148 | 0.01372 |

The fast DeepSeek median is dominated by refusals; it is not successful service
latency. These are complete observed distributions of the twelve declared
attempts, not population percentile estimates. Both sweeps exceeded the fixed
10% error stop threshold at concurrency 1. **Concurrency 4, 16 and 32, the
operating knee, the chosen full-run model/concurrency and the full-pass wall
clock are `not_established`.** A first-level error stop is not a knee. The old
report's erroneous `knee_established: true` remains historical; both
`E/*-throughput-interpretation-v2.json` files correct its interpretation without
changing selection, stopping rule or outcomes. The removal that accepts an
uncompared first level goes red.

| Failure class | DeepSeek level 1 | MiniMax level 1 | Retry/operating treatment |
| --- | ---: | ---: | --- |
| HTTP 429 (`upstream_rate_limit` adapter label) | 9/12, 75% | 0/12 | Retryable within a newly declared bounded retry policy; origin is not established. |
| Malformed output | 0/12 | 2/12, 16.67% | Retryable transport failure; preserve failure and usage. Do not relax the typed contract. |
| Timeout | 0/12 | 0/12 | Retryable; no observed case here is no guarantee of absence later. |
| Other upstream error | 0/12 | 0/12 | Retryability follows the existing typed transport classification. |
| Parsed output violating the extraction contract | 0/12 | 0/12 | Completed explicit contract refusal; never silently repaired into a design. |

Each failed attempt was classified from the complete persisted attempt set;
archives reconcile filesystem/SQLite identities. The two separately declared
one-request diagnostics are **outside** these denominators. DeepSeek again
returned HTTP 429 without a recognized provider code or Retry-After value.
MiniMax returned HTTP 200 with provider `finish_reason: abort`, zero completion
tokens and a seven-character non-JSON body. Its structure was retained without
the body. The producer/network origin of either failure remains unknown; the
evidence does not establish a billing or proxy-rate-limit cause. This repeatedly
failed external service behavior is the precise C1 operating-measurement block,
not a dataset or appointment absence. See the two error-diagnostic-v2 results
and deciding run captures in `E`.

### Contract and paired model comparison

Live models/pricing/capabilities were read before declarations. The active model
identities matched the requested DeepSeek and MiniMax routes. The live common
token rate changed between the first read and codec-v2 declarations; each rate
is bound to its own measurement epoch. No third model/provider was called.
The designated credential was located in the authorized dotenv and used only
in memory; captures and staged bytes were scanned before writing/committing.

The first contract probe passed for DeepSeek. MiniMax first produced wrapped
JSON that the strict initial transport codec rejected. The repair reused the
existing article extractor's object parser under a new dated declaration and
passed; the extraction DTO and its validators were unchanged. Both the original
red and the corrected contract call remain attributable. The codec strangle and
removal distinguish the real default from marker-only evidence.

Both pilots retain the exact six original IDs, hashes and input-length terciles.
DeepSeek's eight phase calls satisfied their contracts; MiniMax had seven
contract-satisfying returned calls and one malformed screening response among
eight attempts. Complete work dispositions are respectively one extracted plus
five screening refusals, and one extracted plus four screening refusals plus one
provider failure. A screening refusal is not a contract failure.

The predeclared comparison admits five paired screening booleans, with **zero
disagreements out of five comparable documents**; the sixth is `not_established`
because one response is malformed. The corresponding observed document-union
error lower bound is 0/5, and the pooled judgment lower bound is 0/10. Neither
is correctness evidence or a population bound. One jointly extracted document
has structurally different outputs. That descriptive 1/1 difference is not a
contradiction oracle: different claim sets or wording can both be valid. It
cannot honestly become a positive error lower bound without mutually exclusive
judgments. There is no gold standard, quality score or accepted-output accuracy
claim. Complete comparisons, identities, phase contracts and limitations are
in `E/paired-pilot-analysis/analysis.json`.

### Prepared mechanism, actual interruption and scale limits

The existing academic campaign owner now persists input, attempt intent,
response/failure and complete work artifacts through one safe atomic writer and
SQLite checkpoint. A bounded queue streams the source. Completed-work replay
reuses immutable responses; it does not reissue them. **Actual SIGKILL tests**
interrupt both a dispatched extraction and the publication-before-checkpoint
boundary. Restart reconciles the complete expected identity set with no duplicate
completed call or partial record; uncertain in-flight work stays explicitly
unknown. The original campaign evidence and removal are preserved alongside
the current 21-case campaign/recovery wave. V2 adds persistent systemic stops and
exact-stop, quiescent recovery without erasing attempts or resetting budgets;
v1 historical receipts remain readable under their original projection.

The graph path extends the existing `graph_builder`, `edge_synthesize` and
pipeline owners. Disk staging replaces resident corpus collections, carries
synthetic ancestry at the common intake and bounds complete owned outputs at
publication. Its run-emitted StrangleReceipt recomputes actual staging use and
default flip. Separate whole-table/schema/value parity proves migration
equivalence. Removing either record capacity or complete output-budget
enforcement makes the original refusal fail while the valid control remains.

The actual graph interruption is **SIGKILL, child RC -9, after load and before
synthesis**. There is no published completed manifest. Restart rebuilds private
graph state, preserves all completed extraction bytes and the same six provider
calls, and produces equal complete database schema/value projections. The
current finalizer wave reconciles all eight collected/executed identities; graph
owner and importer waves reconcile 30 and 25 respectively. Synthetic processing
reaches the real governed consumer and is refused specifically as
`synthetic_input_candidate_only`; removing that predicate loses the required
refusal. An empty raw L2 graph is not credited as that synthetic-specific proof.

Both original real six-input pilots were subsequently finalized through the
same production owners without a provider client. Every one of each pilot's
43 original files remained byte-identical. Each new graph contains one extracted
work and three raw claims, with zero admitted claims or SKG edges. Every table
identity and row count reconciles independently over the complete 30-table
database. This supplies real candidate graph artifacts, **not an authentic
forwardable reference or manufactured N9 writer input**.
`E/original-pilot-graph-finalization-run.json` is RC0, 3.272 seconds; its report
binds actual graph references and original source hashes.

There is no hard-coded corpus-count limit. A larger source is a new immutable
complete frame and independently authorized campaign; an old campaign cannot
silently expand. Real preparation already walked both complete held selections:
310,710 primary works in 22.776 seconds/341,311,488-byte maximum RSS, and 65,327
distinct claim-bearing source works in 55.002 seconds/387,579,904-byte maximum
RSS, both RC0. These preparations made no provider call or extraction output.
The secondary count is documents, not 137,589 historical claim occurrences.

Actual limits are per work/context/artifact bytes, queue/concurrency, provider
context/output tokens, declared attempt budgets, available disk and graph
aggregate/vocabulary capacities. The prepared templates allow 1-MiB work,
2-MiB context and 8-MiB artifact payloads. Graph defaults allow 1000 rows/8 MiB
per batch, 64-MiB/100,000-contribution groups, 128-MiB/200,000-contribution
pairs, a 16-MiB/100,000-entry resolver vocabulary, and 16 GiB of **current-build**
owned output. Exceeding these refuses rather than silently dropping members.
Serialized limits are not a hard Python RSS guarantee. Immutable campaign
history and abandoned/prior graph builds consume disk outside that per-build
budget; a larger corpus, larger payloads, denser groups, or insufficient disk can
breach these limits. Retention/global disk management remains an operational
requirement, not a claim of a drive-wide quota.

### Operator run plan and terminal disposition

`E/campaign-cli.md` and the exact unauthorized `E/prepared-primary.json` /
`E/prepared-secondary.json` contain working `prepare`, `run`, `recover` and
`finalize` commands. The 24-case CLI wave, source-growth/novel-input controls,
authorization/source-binding removals and actual unauthorized module invocation
prove those boundaries. Neither saved template authorizes spending or selects
a winning model. Their concurrency 1 and two-attempt policy are structural
preparation inputs only.

Before any later full pass, the architect needs a new dated operating declaration
that resolves the repeatable provider failures, establishes an acceptable
concurrency comparison, and chooses model/retry/delay/resource policy on that
evidence. The same held snapshot can then be prepared and explicitly authorized;
source expansion gets a new complete frame with no code change. The run's wall
estimate must use successful end-to-end work throughput under that chosen policy,
including screening/refusal frequencies and finalization. **There is no credible
Monday-to-Friday completion forecast in the current evidence.** Summed request
latency and a first-level error stop cannot supply one.

An authorized operator resumes the identical plan/checkpoint after interruption.
Checkpoint granularity is every intent, returned/failed attempt and completed
work. With `retry_unknown: false`, an uncertain interrupted request is not
silently repeated. Authentication, rejected configuration, reported-model
mismatch or unsafe response causes a durable v2 systemic stop. After repair,
the operator waits for admitted calls to settle and acknowledges the exact stop
through `recover`; previous usage remains spent. Timeouts, 429s and malformed
responses consume the explicitly declared retry budget. Contract refusals and
exhausted failures remain complete dispositions, not successful extractions.
Reprocessing them requires a new declared campaign; unchanged resume skips them.
Read `execution_status`, completed/unknown counts, outcomes and `fatal_stop_ref`:
CLI RC0 alone can describe successful emission of a fatal-stop summary and
does not mean the corpus completed. Graph finalization is a separate resumable
owner stage; schedule its measured CPU/write load independently.

| Requested continuation | Terminal status | Deciding evidence |
| --- | --- | --- |
| C1 bounded measurements and full-pass operating readiness | `blocked` | Both providers exceeded the predeclared error threshold at concurrency 1 and the separate diagnostics reproduced their failure classes. The operating knee, selected full-run configuration and wall forecast remain `not_established`; week-long memory stability is also unestablished. All locally executable preparation, interruption, graph and bounded resource work described above is delivered. |
| Section 2 enlarged constructed adversarial suite | `executed` | The dated complete construction, actual owner replay, independent identity reconciliation and property-removal/saved-corruption probes decide the result below. |
| Original A / B / C2 | `executed`, closed | Their mechanisms were not reopened or improved. |

### Enlarged constructed suite

**Refusal sensitivity: 48 refusals in 48 predeclared deliberate mismatches.**
**A high refusal rate on constructed mismatches is not evidence that accepted
bindings are correct.** The input-only construction is all three actual
categorical sign reversals plus every nonassigned pairing of the three real
assignments with the sixteen held WMR slots: 45 transpositions. Three original
matched structural controls remain outside the negative denominator. There is
one shared support cluster; neither a larger count nor repeated support creates
independent calibration. Controls remain exact/satisfiable structurally while
their authority abstentions remain explicit.

This covers categorical sign and held assignment/target consistency. It cannot
test subtle causal or legal mismatch, effect magnitude/tolerance, or correctness
of accepted bindings. The proposed magnitude grid was rejected before execution
because the real signatures expose domain bounds, not effect magnitudes. The
construction was committed before execution; no outcomes selected its members.
The official producer/checker were RC0 in 150.528/120.735 seconds. Sign,
assignment, binder and emitted-identity removals are intended RC1; actual saved
count corruption makes the owner checker RC1 and restores exact original bytes.
All five independent identity reconciliations preserve the complete case/control
sets. Evidence:
`corr-evidence/a-expansion/2026-09-09-journal.md@7e216d47583eded9ab9ad8f9c0c0e669967d642c`
and its cited complete captures. No original A production owner changed.

### Built mechanisms and their falsifiers

- C1 SDK contract adapter and dated model/input declarations: wrapped-output,
  malformed/typed-contract, unsafe decoded-key and wrong-model removals/refusals
  distinguish attribution and actual contract behavior; no contract relaxation.
- Durable campaign and CLI: actual interruption, fatal-stop/quiescence/WAL,
  completed-call replay, complete-source identity/growth and unauthorized-run
  probes fail at the owning boundary when its property is removed.
- Existing-owner graph staging/finalization: complete parity, synthetic authority
  refusal, actual graph kill/restart, complete artifact membership/bytes and
  shared disk-cap removals; real pilots retain original source bytes.
- Finite resource/throughput/paired-analysis diagnostics and enlarged suite:
  recomputed frames, source-at-finish, missing identity, warm-window, knee and
  decisive mismatch removals. Their limits remain part of their outputs.

### Findings and requirements owned elsewhere

- **GY-PR1 / CORR-C1 provider operating dependency:** repeated DeepSeek HTTP 429
  and MiniMax aborted/non-JSON responses, with exact issuing component unknown.
  A newly declared acceptable provider/retry/concurrency measurement is needed;
  this is not a billing verdict or permission to use another provider.
- **GY-PR1 / CORR-C1 operating acceptance:** long-duration memory stability,
  higher concurrency, dense/adjudicated graph scale and global disk-retention
  policy remain bounded measurement/operations requirements. No synthetic
  result is promoted into the canonical corpus denominator.
- **`historical-confidence-carries-a-withdrawn-contribution`**, in the
  data-capability requirements register: the source bytes and runnable pipeline
  exist, but the full re-extraction remains unauthorized and unrun. The resulting
  raw candidate graph does not supply the separately admitted claim-evidence
  axis or an authentic N9 reference. Existing claim-adjudication/admission owners
  own those inputs; closed C2 preservation is unchanged.
- **`adversarial-refusal-sensitivity-is-publishable-today`:** the expanded
  constructed suite is delivered within its named categorical/assignment limit;
  accepted-binding calibration remains a separate requirement.
- The false first-level knee field, scope-probe contamination from concurrent
  receipt writes, command/module setup failures, uncredited empty-L2 negative,
  archive projection/whitespace and repetitive derived-bin issues are **this
  lane's corrected harness findings**, governed by P29/P35/P38/P40 and receipt
  proportionality. Their home is this journal, not another lane's production
  debt. The failure/repair register was reread at closeout. No new unallocated
  production finding or register change is asserted.

### Final verification checkpoint

The complete Python change set from this continuation's entry commit
`84e633fe53990951b96680295ab66daee60a8af2` to the frozen implementation was
independently derived by `git diff` and two complete `git ls-tree` blob maps.
All 66 identities agree, hash
`99397d724b5ed4fd037de0bee495e528bb31adabab69040d974f7d3de5cd3d5e`;
the exact independent command/output is `final-changed-python-identities.json`
(RC0, 0.212 seconds), targeting the frozen `d24655fbf` implementation.
`E/final-changed-python-ruff.json` is RC0, 0.049 seconds. The subsequently
added archive helper has its separate final Ruff RC0 in
`E/graph-profile-archive-final-ruff-v2.json`. No production source changed
after these checks. Targeted test collections and actual execution identities
are reconciled in the cited owner reports, rather than aggregated into an
invented full-suite result.

The initial normal guardrail capture is RC1, 255.998 seconds. Its complete
output separately names concurrent writes by this lane's still-finishing
receipt/archive authors and the generated OpenAPI example's stale source
binding. That is an owned contaminated output-boundary measurement, not an
inherited production failure. All authors then froze. The existing OpenAPI
exporter regenerated the snapshot in `openapi-final-source-write.json`, RC0,
66.210 seconds. No exporter or closed authority algorithm was changed.

`openapi-final-complete-delta.json` independently walks every typed JSON node
recursively and iteratively: both versions retain exactly 57,290 identities,
and the ten changed values are the existing negative example's recomputed
dependency count/digests and corresponding receipt/projection/replay bindings.
Operations, DTOs, rule epochs and semantic payloads remain equal. The old
snapshot is `schemas/runtime_api_v1.openapi.json@35889915ebe8598eb1e379e64db82405ddbefbdd`;
new byte SHA-256 is
`202c4697556b02b1a033552db57fe86fa89161cbf1deac01fc7c869ef5723684`.
No governed JSON reformat or drive-by receipt edit was used.

`openapi-final-persisted-corruption.json` is wrapper RC0, 74.223 seconds:
changing only the saved `bound_dependency_count` from 6363 to 0 makes the
unmodified API checker return RC1 with exactly that generated-value diff.
The helper restores the exact original bytes. The checker also logged an
optional Prometheus exporter port collision; the schema refusal completed
for its named drift. That incidental station observation is **explicit nowhere
in the product backlog**, uninvestigated and not a claim of product breakage.
The final normal guardrail replay follows this frozen checkpoint. No baseline,
exemption, denominator or gate scope was weakened.

Independent handback review corrected the checkpoint-count ordering and made
the inferred development headroom explicit: these were quiet resource profiles,
not measurements of concurrent development interference. It found no other
substantive contradiction in the inspected status, denominator, quality,
resource and conditional-cost statements. Verification captures in this section
without the `E/` prefix are added after the evidence checkpoint above and are
bound by the subsequent final local verification commit.

### Cost footnote — conditional, not the operating decision

The pilot-v2 live rate was **USD 1.202913e-9 per prompt or completion token**.
DeepSeek used 8316 prompt + 1557 completion = 9873 tokens, computed cost
$0.000011876360049. MiniMax used 8447 + 4987 = 13434 tokens, computed cost
$0.000016159933242. MiniMax's failed screening reply still reported 1100 tokens;
the forecast includes that transport usage rather than treating checkpoint
`unknown` as zero. Provider price times usage is not a billing receipt.

**Conditional full-pass token/cost forecast:** primary 310,710 source works:
DeepSeek 511,273,305 tokens / **$0.6150173051**; MiniMax 695,679,690 /
**$0.8368421429**. Secondary 65,327 claim-bearing source works: DeepSeek
90,573,405.5 / **$0.1089519269**; MiniMax 122,588,143 / **$0.1474628709**.
These point estimates assume exchangeable phase frequencies and token use
within the unchanged input-length terciles, each with only two pilot inputs.
They describe the pilots' one-attempt policy, not the prepared two-attempt
policy, unknown interrupted usage, claim-occurrence extraction or a precision
guarantee. Selective retries do not justify a blanket multiplication by two.

The repository token estimator produced 8324/8316 prompt tokens for
DeepSeek/MiniMax. Provider prompt counts were respectively **8 lower / 131
higher**; provider total tokens were **1549 / 5118 higher** than those local
prompt-only estimates. Completion tokens explain most of that gap. Conditional
serial sums of provider latency are preserved in the analysis but are explicitly
not full-pass wall-clock forecasts. No number is attributed to the old OpenAI
declaration or represented as a grounding/correctness bound.

### Frozen verification closure — 2026-09-09

The final normal architecture guardrail replay is **RC0, 344.481 seconds**,
from the clean attached source/evidence checkpoint
`0713123a94d7ddd603f4b6841a13ab7c4d32b2a5`. Every one of that checkpoint's six
changed blobs was reread from the branch before the replay. All writers stayed
frozen throughout. OpenAPI, runtime API client, dashboard API types and
trust-claim-posture freshness passed. Complete capture:
`corr-evidence/c1-capacity/final-normal-guardrails-frozen.json@sha256:dd9508781ec4b200ac2f0d37a104a700851cec95865f1fcd6e1b6df978cd8a15`.
This credits the normal guardrail only, not its explicitly excluded standalone
Atlas retirement gate or a forbidden full test suite.

`corr-evidence/c1-capacity/final-scope-and-secret-audit.json` is RC0, 7.030
seconds. It independently reconciles all 587 changed tracked identities from
the continuation entry to the frozen checkpoint, inspects every changed blob
and decoded JSON for credential leakage, and confirms that all production
changes are in the academic batch owner and that neither protected register
changed. The final journal/capture additions are separately scanned before
commit. No production source follows the frozen checks.

The terminal statuses and separate built/finding lists above stand: C1 is
`blocked` at the external-service operating measurement; section 2 is
`executed`; original A/B/C2 remain closed. **Cost remains only the conditional
footnote above, not permission to run the full pass.**
