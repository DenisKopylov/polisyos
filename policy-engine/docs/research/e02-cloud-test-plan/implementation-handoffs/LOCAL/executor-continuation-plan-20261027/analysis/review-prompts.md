# Independent review of C01–C11 cloud prompts

Review target: all eleven complete `prompts/C*.md` bodies, the owner table in
`LAUNCH.md` and `COMPOSITION.md`, and their named source/patch/test objects.
Source base was branch `codex/e02-unified-local-20261009`, commit
`ad81c5b826bdfdda6aa2295b8641e9ae2a68b21a`, tree
`df24ff6ff12e7039c0cbfbd47abc8bee82f5332e`. This is a static review, not
execution or acceptance. The prompts were being corrected concurrently; the
specific findings below record both original observations and the delta read back
during review. Reviewer buckets are NEW versus SAME class as required by P40.

## Findings and narrow corrections

1. **NEW — C07 requires a selected decision object that a branch-scoped cloud
   checkout may not have.** C07 says to read Git object `798bd1ab...` (AD04
   and AD06), although `git merge-base --is-ancestor 798bd1ab... ad81...`
   exits 1. It is locally reachable from `origin/codex/e02-integration`, not
   from the selected author topic's ancestry. That does not establish what an
   isolated cloud checkout can resolve. The same ancestry limitation holds for
   `528ec257...` and `14bf6380...`; C08 and C10 already provide an explicit
   inline-law fallback for the latter. **Delta readback:** C07 now makes
   AD04/AD06 a conditional cross-check, supplies the selected law inline, and
   labels the unavailable full-document check `not_established` without
   stopping bounded source/oracle work.

2. **NEW — shared generated-family ownership is ambiguous.** C04's proposed
   SourceContract extension names schema snapshots, recomputing validators and
   public/generated inventory as mandatory companions; C08 names public
   inventory/schema/config companions; C05 originally said C08 owns the whole
   schema/generator/lock family. The composition table assigns the shared
   DTO/OpenAPI/client/dashboard/schema/generator/lock family to one
   root-selected writer. These are required companions, but their presence is
   not authority for multiple cloud authors to regenerate them. **Correction:**
   allow each author to identify exact companion deltas/preimages and test
   dependencies, and reserve shared generation/schema/lock application and
   drift checks for the one named compositor. **Delta readback:** the prompts
   now name the root-selected generated-family owner and reserve C08's source
   scope to codec/IR/profile and its codec registry. Keep direct, exclusively
   owned schema changes clearly differentiated from shared generated projections.

3. **SAME — local environment and input assumptions in C05.** Initially it
   required a specific Mac worktree, an unpublished continuation-analysis file,
   private RAW manifest/review/failure output, a Mac venv/RAW supervisor, local
   two-job limit, and independent review before the author could run the next
   step. That conflicted with a standalone cloud task. The revised C05 read
   back during review makes RAW optional, embeds the known NO-GO, supplies ten
   real source selectors, permits a minimal frozen cloud setup and defers
   independent review. All ten selector function names exist in the two
   tracked test files. **Delta readback:** the C05 delivery now reports
   independent review pending and assigns common generated-family changes to
   the later root-selected writer.

4. **SAME — provisioning an optional backend cannot require an unprovided
   follow-up.** Original C07 forbade installation without separate
   authorization although native `econml` is in the `causal-core` extra,
   not the runtime/test extras. C03 requires real HNSW and its pinned
   `hnswlib==0.8.0` lives in `vector-search`. Their updated text now names
   the appropriate frozen extras, meters actual disk and RAM, and leaves an
   unsupported/missing backend as scoped UNRUN. This is a correction readback,
   not proof those profiles install on the future VM or fit its capacity.

5. **NEW — checkout, hook and transport assumptions needed a common fallback.**
   LAUNCH explicitly allows an exact-base cloud `work` checkout to be
   detached and have no origin, but several original prompts spoke as if an
   attached own topic, commit and publication were prerequisites, and
   C01/C06/C09 lacked explicit failure disposition. A common paragraph has
   since been added with exact commit/tree admission, task-local scope,
   branch-observation, no hook bypass, diff/hashes fallback and deferred review.
   **Delta readback:** C10 now explicitly calls for a report without a diff,
   commit or source writes; C11 allows a source-unchanged oracle. The common
   entry text scopes worktree create/resume admission to commissioned managed
   worktrees and admits an already provisioned cloud checkout by exact identity
   and task isolation. Actual cloud result and output transport are untested.

6. **NEW — launch environment claim is stronger than the prompt bodies.**
   `LAUNCH.md` says every prompt pins `polisyos / 6965429...`. A search
   over all eleven prompt bodies initially found that ID only in C05 and C11.
   **Delta readback:** the environment and ID are now included in each
   standalone body's admission paragraph as well as in the launch command.

## Concrete owner and readset intersections

- **C01/B13:** both concern `runtime/http/services/debug.py`. C01 explicitly
  reserves the exact-view repair and leaves B13 invalidation to later
  composition. This is a real shared writer and is correctly serialized;
  retain B13's separate invalidation/surviving-sibling semantic obligation.
- **C05/C11:** the C05 writer owns `run_lifecycle.py`, where the actual
  `ControlWorker` is constructed around line 4352. C11 owns
  `resilience.py`, `control_worker.py` and the shared async executor; it
  excludes C05's container/lifecycle and calls for a dependency result if the
  real cancellation or integration path needs those files. This is a real
  semantic seam, not an authorization for C11 to create a second lifecycle
  writer. Recheck both integration paths after composition.
- **C05/C07:** C07's existing HTE binding/admission consumer is in the same
  `run_lifecycle.py` C05 owns (including
  `_resolve_search_uncertainty_binding`). The r5 proposed C07 product patch
  itself touches `search/uncertainty.py` and a new HTE source projection, not
  lifecycle. If the actual request transport requires the shared file, return
  an exact proposal to the compositor and report the bounded missing bridge.
- **C06/C07/C08:** C06's six Search/autotune product files and five tests in
  the tracked r13 patch are distinct from the two C07 r5 product paths.
  C07's uncertainty reader imports Core canonical read limits and lifecycle
  uses the Core profile owner; C08 changes shared canonical/profile mechanics.
  These are real dependent readsets and shared representation semantics, not
  proof of a direct overlapping first-wave Search writer. Preserve the
  `.2` law, compose under one owner, and rerun affected consumer tests on
  final source; do not claim a cloud result establishes the composed result.
- **C09/V1:** C09 edits only `tests/_helpers/acquisition_production.py`.
  The local V1 helper `acquisition_served_history.py:771` imports three
  functions from that module. The r4 diagnostic patch changes
  `persist_wdi_route`, rather than those three imported functions. This is a
  same-module/readset requalification on later composition, not demonstrated
  behavioral overlap or a reason to serialize isolated cloud work. Record the
  V1 helper's exact imported source identity and rerun/requalify after merging
  C09's helper delta.

## Evidence and coverage

- `git status --short --untracked-files=no` was empty; the branch/HEAD/tree
  were read back. The worktree has substantial pre-existing untracked material;
  no cleanup, index or reference mutation was performed.
- The twelve named tracked proposal patch SHA-256s match their prompt values:
  G27 r5, I1 r4, I3 r7d/r8b, I4 r2, N7 r4, R3 author-06 product/test,
  S1 r4/r5 and V5 r13 product/test. The checked C01, C07 and C09 source
  preimage hashes also match.
- `git ls-files` confirmed the named existing test files in C01–C11 that were
  checked. The C02 eight existing node functions, C04 three base functions,
  C06 existing GP and work-packet nodes, C10 existing named anchors, C11
  renewal/fencing nodes, and revised C05 ten starting function names were
  verified with source searches. C02's five proposed cases, C03's proposed
  legacy node, and C06's four added classification nodes are present in their
  patch texts. C08 correctly marks its five old RAW overlay test files absent
  from the pinned tracked tree. C11's new dedicated witness and C05's new
  POST/ledger test are proposed, not base test files.
- C01/C02/C03/C04/C05/C06/C07/C08 define positive and adversarial/removal
  paths; C09 is a bounded diagnosis; C10 prepares but must not execute
  temporal/closure oracles; C11 starts with a genuine service-capacity witness.
  None of those descriptions is evidence that the future test passed.
- The failure register was inspected before and again after the review,
  including P01/P02, P05/P10, P27–P29, P31–P33 and P37–P41. No backend,
  product code, test or installation was executed. Runtime behavior,
  cloud filesystem/result transport and native backend availability are
  `not_established` here.

## Final delta verdict

**GO — plan-ready, within the stated first-wave boundaries.** The final C07
delta now calls for a direct owner/resolver witness and an unapplied, UNRUN
ordinary-POST/fresh-reader oracle for later C05/root composition; its first
wave no longer requires that deferred route. The final C08 composition row
also reserves shared schema/generated outputs to the root-selected family
writer. Final reviewed identities for those two delta files are
`prompts/C07-s1-source-binding.md@sha256:6a2b2be267f50789a13f04207da6938584489e25891091413ccc74d6ca7968b3`
and
`COMPOSITION.md@sha256:5a0ea3318217020b9a1439c2e9ed5bf5b6302a959e8a5b8140d655305ca4e3b8`.

This is an assessment of the assignment text only. It does not establish
launch authorization, cloud capacity, backend installability, availability of
task-local outputs to the coordinator, execution of any witness, source
acceptance, G review, or finding closure. Each remains subject to its own
admission and evidence.
