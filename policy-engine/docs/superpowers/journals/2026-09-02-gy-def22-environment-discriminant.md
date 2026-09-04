# GY-DEF22 — Foundry environment discriminant implementation

Date: 2026-09-02 through 2026-09-04

Branch: `codex/gy-def22-environment-discriminant`

Entry base: `fac07ffc6`

Synchronized main: `c7becd3a71bb67307229c7c8f23acb60d58f4289`

Synchronization merge: `797d2ad7b`

Final source commit: `09293c195`

Final pre-journal tree: `a255bdf01`

This journal is append-only. The implementation never edited `docs/plans/active/`,
`production_data`, or source under `src/polisyos/runtime/quality/`.

## Outcome

The ratified `ambient_non_decisive` mechanism is implemented. Foundry derives one
dependency-only discriminant from admitted owner data; N8 persists it; N8, N10a and
chronology replay verify the same content-bound bytes; and the Runtime governed
projection exposes the diagnostic and its exact authority boundary. The diagnostic
can report `pass`, `fail`, or `not_established`, but cannot decide N8 admission,
N10a stage-gap closure, chronology acceptance, policy publication, or policy
promotion.

The technical chain is complete, but this journal does **not** claim that the
register row is closed. The final independent Foundry adjudication receipt is
`not_received`: both available reviewer attempts exhausted workspace credits before
returning a SHA-bound verdict, and the installed Codex 0.36.0 read-only fallback
cannot use `gpt-5`, `gpt-5-codex`, or `o3` with this ChatGPT account. The exact
adjudication ask is unchanged from the ratified plan. GY-DEF22 therefore remains
`open` pending that last owner receipt.

## Ordered execution and synchronization

The plan was executed in task order.

- Task 1 established the five acceptance reds in `4c6f68c1d`, strengthened them in
  `8d9eba246`, and pinned the historical fixture in `52c52df32`.
- Task 2 extended the landed Foundry catalog/discovery owner in `48aedf7d6` through
  `3ffb6ad5e`; it did not recreate the N12 design.
- Task 3 made N8 the companion producer and validator in `7825c26df` through
  `43cbe5863`. The separately directed host-dependent `PATH` repair landed in
  `c99dfaea6`: the appointed Git process preserves all non-`GIT_*` caller inputs and
  scrubs only the `GIT_*` family.
- Work stopped at the hard synchronization point. Main, including group A's owner
  validator timeout repair, was merged in `797d2ad7b`; no rebase was used.
- Task 4 wired N10a, chronology, and the transition readback in `6881e4b13`; its one
  bounded correction, `231150674`, required exact three-consumer reconciliation.
- Task 5 registered and surfaced the companion in `6587f3042`; the required
  generated trust-posture refresh landed in `1a1e2101c`.
- Final review found that Task 5 had attached the ambient diagnostic to a pre-existing
  owner-validation cache whose key did not bind ambient-environment state. The
  regression test first observed stale `pass` after the child-visible package state
  moved to a failing value. The single allowed Task 5 repair disables that cache only
  for `value-gate` (`09293c195`); both calls retain governing `passed`, while the
  diagnostic changes from `pass` to `fail`. The mandatory trust-posture owner output
  was then regenerated and checked in `a255bdf01`.

No second same-class, in-scope Task 4 or Task 5 finding was repaired. Generated-output
refreshes required by their registered owners are recorded as lifecycle work, not as
additional review rounds.

## Ratified threat model and declared residual band

The remaining review was bound to the following exact threat model:

> **In scope:** accidental drift — a stale cache, a changed source file, a wrong
> profile, a mismatched environment, a developer running the tool from the wrong
> directory.
>
> **Out of scope:** an actor with write access to the repository working tree or code
> execution in this process. Such an actor edits the checker; hardening the checker
> against them is an unbounded regress, and defending a value that by construction
> decides nothing buys nothing.

The following three findings are the named residual band. They are deliberate
limitations under the second paragraph, not silent omissions and not closure gates:

1. **Sibling mutable, unkeyed candidate-denominator cache.** The earlier repair's
   transport is immutable and its active cache keys include the authority state. The
   separate sibling cache identified by the final Task 3 audit remains unchanged. An
   actor able to mutate it in process is outside the bounded threat model. This is
   distinct from the Task 5 HTTP cache repair above: ordinary ambient package drift
   after a cached diagnostic was in scope and is now forced through a fresh owner
   validation.
2. **Leaf-only `O_NOFOLLOW` follows a symlinked parent.** Redirecting a parent path
   requires worktree manipulation by the excluded actor. Closing it would require a
   component-by-component directory-descent primitive; this task does not build one.
3. **Symlinked Git semantic parent can redirect graft/alternate paths.** Redirecting
   the Git semantic parent likewise requires repository/worktree manipulation by the
   excluded actor. Closing it would require a separately appointed, writer-independent
   Git object-store custody mechanism; this task does not claim one.

The one surviving in-scope authority boundary is preserved: the new logic wraps the
pre-existing governing call and cannot weaken it. The before/after tests exercise the
same governing N8, N10a, and chronology results, not a copied approximation.

## Shared artifact and derivation

The one registered generated-committed artifact is
`architecture/policy_design_case/layer3_gy_n8_dependency_discriminant.json`.
Its recorded identity is:

- schema `polisyos.foundry.n8_dependency_discriminant.v1`;
- rule `polisyos.foundry.dependency_discriminant.v1`;
- producer `tools.quality.validation.check_layer3_gy_value_gate_contract`;
- authority owner `polisyos.foundry.methods.catalog`;
- authority purpose `n8_method_catalog_reconstruction`;
- source freeze `3ffb6ad5ed95d316656bc19946018a4eec52bc3b`;
- predicate class `recomputed`;
- decision role `ambient_non_decisive`;
- 149 resolved distribution rows; and
- artifact content ref
  `sha256:4dcf46b4810471ba8ecfe2931757e7c628fd5339e8044df7a246fe987cde84ec`.

The caller supplies the authority purpose and source freeze, not a profile name.
Foundry resolves purpose to its admitted profile, reads the exact tracked
`pyproject.toml` and `uv.lock` bytes at the freeze, evaluates the used marker inputs,
walks the selected lock graph, sorts the complete closure, and computes the registered
`dependency-discriminant` domain. Profile labels are retained for display/provenance
and are not consulted as compatibility rules. The artifact records no interpreter
path, host identity, machine path, installed environment path, or production-data
reference.

N8 is the sole registered producer. N8, N10a, and chronology independently reopen and
validate the same artifact content ref and discriminant rows. The transition readback
rejects a missing or different copy. Runtime carries the owner result as a strict
related-artifact binding; absent, malformed, corrupt, or exception-producing
diagnostics collapse to typed diagnostic non-receipt without invalidating a valid
governing projection.

## Acceptance clauses and their witnesses

The five clauses below are quoted exactly from the ratified closure basis.

> - **CB-I01 — admitted profile identity:** deployment records bind a
>   reconstructible dependency profile/root/distribution discriminant shared by
>   N8, N10a and chronology replay, while the Foundry catalog/discovery boundary
>   remains its authority owner.

Satisfied by
`test_cb_i01_n8_n10a_and_chronology_share_one_foundry_discriminant`: the actual N8,
N10a and chronology seams return the same content ref, profile, root distribution,
and complete resolved rows. A separate negative rejects consumers bound to different
companion copies.

> - **CB-I02 — research-profile regression:** the documented research environment
>   with `torch==2.10.0` fails and names the decisive discriminant as the first
>   case, never as a special profile/package rule.

Satisfied by `test_cb_i02_research_profile_names_torch_as_first_generic_case`: the
test derives the documented closure from owner data, observes the tracked
`torch==2.10.0` row, and receives diagnostic `fail` with generic coordinate
`distribution:torch:*` first. A complete changed-source scan found no production
`torch` or `research` branch.

> - **CB-I02A — name-invariant incompatibility:** hold the profile label and
>   shaped record constant, substitute an incompatible distribution inside the
>   resolved deployment closure and recompute the discriminant; verification
>   fails. A second incompatible profile generated from data fails without a
>   known-name allowlist or code edit.

Satisfied by
`test_cb_i02a_label_and_shape_cannot_mask_two_data_generated_incompatibilities`: one
case holds the label and DTO shape constant while changing a selected lock row; the
other appends a second scratch TOML profile and resolves it generically. Both produce
diagnostic `fail`; neither changes code or consults a known-name allowlist.

> - **CB-I03 — irrelevant difference:** a package difference outside the resolved
>   deployment closure does not fail the replay.

Satisfied by `test_cb_i03_outside_closure_difference_is_diagnostic_irrelevant`: an
extra installed distribution outside the selected closure leaves both the status
`pass` and first case `None`.

> - **CB-I03A — novel admitted profile:** a novel admitted profile/distribution
>   derives its discriminant and dependency closure from recorded data and
>   verifies without a code edit, machine pin or known-package allowlist.

Satisfied by `test_cb_i03a_novel_admitted_profile_verifies_from_owner_data`: a novel
owner-registry row is added only in scratch, its discriminant/profile are derived from
the recorded TOML and lock data, and the diagnostic verifies `pass` with no case.

The final post-repair acceptance command selected exactly five tests. Result: five
passed, zero failed, zero skipped.

## Diagnostic/governing byte-equivalence proof

For CB-I02 and CB-I02A, `fail` is strictly the diagnostic outcome. The governing
result is serialized independently with canonical JSON from the actual N8, N10a, and
chronology consumers.

- CB-I02 compares the three governing byte strings with the research diagnostic
  removed and with its generic `fail`; the tuples are exactly equal.
- CB-I02A repeats the comparison for both the same-label lock substitution and the
  second data-generated incompatible profile; both equal the diagnostic-free tuple.
- `test_p38_ambient_diagnostic_cannot_govern_shared_consumer_results` independently
  runs all three seams with and without a failing diagnostic and requires exact byte
  equality.
- `test_invalid_and_removed_diagnostics_cannot_govern_shared_consumer_results`
  requires exact governing equality for malformed versus removed diagnostics while
  N10a and chronology report diagnostic `not_established`.
- N8-, N10a-, and chronology-specific tests separately assert their governing/ambient
  channel split. The final HTTP cache regression keeps both governing statuses
  `passed` while forcing the ambient diagnostic to refresh from `pass` to `fail`.

At the Task 3 freeze, the functional wave selected 50 cases: 48 passed, the two
expected N10a-only pre-Task-4 reds failed, zero skipped, and both governed artifacts
were byte-identical. After Task 4 those two seams became green. No test substitutes a
mocked governing result for this byte comparison.

## Red-first and targeted verification receipt

The following evidence was obtained without a directory-wide test run:

- Initial acceptance tests were written and observed red before their producers and
  consumers existed.
- The final cache test was observed red for the intended reason: its second ambient
  diagnostic was stale `pass` instead of expected `fail`. After the one-line source
  repair, the exact node passed.
- The post-repair focused Runtime wave selected 12 cases covering the new cache
  falsifier, existing dependency/source cache behavior, malformed/missing companion
  quarantine, valid research mismatch, and all three worker diagnostic branches. All
  12 passed with zero skips.
- The final five-clause wave passed 5/5 with zero skips.
- The final P29/P33/P38 and consumer wave passed 10/10 with zero skips. It included
  property-removal, label/profile variation, all three governing byte comparisons,
  three-way readback, N8/N10a/chronology channel separation, and the new cache
  falsifier.
- Before the cache repair, the broader exact N8/P29/P33/P38 wave expanded 29 node
  selectors to 51 cases and passed all 51; the Task 4 consumer/readback wave passed
  13/13; and the Task 5 focused surface wave passed 12/12. No skips occurred.
- The companion's registered check returned status `pass` and the content ref above.
  A scratch copy with a changed resolved-distribution version and a recomputed
  outer self-hash failed with `distribution set is not bound to resolved rows` and
  exit 1. The scratch copy was discarded; the governed artifact was not rewritten.
- Ruff passed over all 16 branch-authored Python paths before source freeze. After the
  cache repair, Ruff passed on its two changed Python files. `git diff --check`
  passed.
- The registered Runtime OpenAPI verifier passed, the Runtime TypeScript client
  regenerated in scratch and matched, and
  `corepack pnpm --filter @polisyos/runtime-dashboard run typecheck` passed.
- The trust-posture owner correctly raised `DS11-GENERATED-DRIFT` after each Runtime
  source movement. The registered writer regenerated the one committed output; the
  final exact `--check` returned exit 0, `write_set: []`, source-set digest
  `sha256:19c55247ede51dd7dd2a67e76ba4af657f698a86bab3bb50cf906e2f7753f16f`,
  and payload digest
  `sha256:1b15d5ca402af2039e5eb7d3074629eea8407dcad52216056afacddcc11e11e4`.

Architecture guardrails were not misreported green. On both synchronized main and
the feature tree they report the same three deep-import violations in
`src/polisyos/runtime/http/services/acquisition_admission_bundle.py` and the same
Runtime OpenAPI output-probe attempt to write a uv cache outside its isolation root.
The feature tree's generated artifacts, including Runtime clients and trust posture,
are current; the remaining guardrail findings reproduced on the synchronized base
and are disjoint from all 30 GY-DEF22 implementation paths.

## Review rounds and blast radius

The specification initially supplied no threat model or residual band. Task 2 took
four fix rounds and Task 3 took four fix rounds, each opened by the same class being
found one level deeper. The stop checkpoint therefore contained eight fix rounds and
6,775 insertions for a narrowly stated defect. This is recorded without laundering
the cost: it was the consequence of an unbounded review ratchet, not evidence that
the original task was small.

After the threat model was supplied, Task 4 used one bounded correction and Task 5
used one bounded cache correction. Against synchronized main
`c7becd3a71bb67307229c7c8f23acb60d58f4289`, the final pre-journal tree contains
exactly 30 changed paths, 9,756 insertions, and 202 deletions. The generated
trust-posture artifact is the one mandatory secondary output beyond the plan's
literal mechanism census; its registered owner includes the changed authority
surface in its complete source denominator. This journal is a mandatory companion
record and is outside the P39 mechanism count.

The complete 30-path denominator contains:

- zero paths under `docs/plans/active/`;
- zero paths under `production_data`; and
- zero paths under `src/polisyos/runtime/quality/`.

The test-only changes under `tests/unit/runtime/quality/` do not violate the explicit
source-package stop rule.

## Capability accounting and P38 closeout

The diagnostic capability chain now has a strict contract, a Foundry producer,
persisted registered artifact, N8/N10a/chronology bridges, verification, a governed
machine/audit surface, and negative/end-to-end semantic tests. Its implementation
state is complete, subject only to receipt of the final owner adjudication.

The separate authority-grade admitted-environment chain remains `producer_missing`.
The Foundry authority registry still records all four prerequisites as
`absent/unallocated`:

1. `owner_enforced_runtime_subtree_cutoff`;
2. `owner_resolved_resolution_receipt_store`;
3. `platform_toolchain_admission`; and
4. `production_data_trust_policy`.

No candidate walk was promoted to an authority-grade gate. The P38 property is the
validity of N8 governing evidence and replay; the former proxy was the ambient
package posture of the interpreter executing the checker. The divergent case is the
documented research environment: it produces a generic dependency diagnostic
`fail`, yet the governing N8, N10a, and chronology bytes remain unchanged. The code
now reports that distinction directly and never gates on it. Technical P38 evidence
is complete; the register transition awaits the independent Foundry acceptance
receipt rather than treating implementer self-review as authority.

## Foundry adjudication ask and non-receipt

The reviewer is still asked to accept exactly the six ratified claims, bound to final
source commit `09293c195` and pre-journal tree `a255bdf01`:

1. purpose -> profile remains Foundry-owned and callers cannot select an identity;
2. the dependency-only preimage and new digest domain exclude production data and
   machine identity;
3. the complete closure and first-case ordering are generic over registry/lock data;
4. N8 is the sole producer of the registered companion and all consumers verify the
   same bytes;
5. ambient diagnostic status is structurally barred from N8 admission, N10a closure,
   chronology acceptance, publication, and promotion; and
6. the positive authority capability remains `producer_missing` with the four absent
   owner capabilities named, rather than being promoted by this repair.

The first reviewer verified the pre-fix source identity and reported that claims
1–4 and 6 traced cleanly and claim 5 was explicit in all consumers, but it disappeared
without a final verdict while validating the cache falsifier. The retry and the
post-repair reviewer both returned `workspace is out of credits`. The CLI fallback
returned HTTP 400 model-not-supported responses. None is an accepted review
reference. This is an adjudication non-receipt, not a negative Foundry verdict and
not permission to self-countersign.

## Exact append-only prose for architect transcription

No active plan was edited. These paragraphs describe the current, non-closed state
exactly and require no inference by the architect.

### `GY-DEF22`

**GY-DEF22 IMPLEMENTATION 2026-09-04 — mechanism complete; standing remains `open`
pending the Foundry adjudication receipt.** The ratified `ambient_non_decisive` route
is implemented on final source commit `09293c195` and pre-journal tree `a255bdf01`.
Foundry resolves `n8_method_catalog_reconstruction` to one admitted dependency
profile and derives the complete root/extras/marker/lock distribution closure; N8 is
the sole producer of registered companion
`architecture/policy_design_case/layer3_gy_n8_dependency_discriminant.json`, and N8,
N10a, chronology replay, and the governed machine surface verify its exact
`sha256:4dcf46b4810471ba8ecfe2931757e7c628fd5339e8044df7a246fe987cde84ec`
content ref. CB-I01 through CB-I03A pass with zero skips: the documented research
closure names generic `distribution:torch:*` first, two data-generated in-closure
substitutions fail diagnostically, an outside-closure difference remains irrelevant,
and a novel admitted profile verifies without a code edit, machine pin, or allowlist.
For CB-I02 and CB-I02A, the actual N8/N10a/chronology governing bytes are identical
with the failing diagnostic present or removed. Runtime refreshes the ambient
diagnostic rather than serving it from a cache that lacks environment identity; both
before/after governing statuses remain `passed`. The diagnostic is authoritative
only for dependency-environment diagnosis and is structurally barred from N8
admission, N10a stage-gap closure, chronology acceptance, publication, and promotion.
The separately named authority chain remains `producer_missing` because
`owner_enforced_runtime_subtree_cutoff`,
`owner_resolved_resolution_receipt_store`, `platform_toolchain_admission`, and
`production_data_trust_policy` remain `absent/unallocated`. The three bounded
residuals and exact threat model are recorded in the implementation journal. The
implementation signal is discharged, but the close signal is not: independent
Foundry review could not return a SHA-bound verdict because reviewer capacity was
exhausted, so the adjudication receipt remains `not_received` rather than being
replaced by implementer self-review.

### GY plan `GY-N12` task row

**GY-N12 TASK-STANDING APPEND 2026-09-04 — status remains `executed`; the deferred
GY-DEF22 mechanism is delivered, but the Foundry correctness receipt remains owed.**
Cluster 1's existing execution and Foundry ownership are unchanged. The follow-on
implementation supplies the deferred Foundry-owned dependency discriminant, N8
producer, one-ref N10a/chronology readback, governed machine surface, and exact
CB-I01–CB-I03A semantic witnesses. Diagnostic failure, absence, corruption, and
ambient cache refresh cannot change governing N8/N10a/chronology bytes or acquire
admission, closure, acceptance, publication, or promotion authority. The positive
authority capability and N12 boundaries 6–7 remain exactly as previously recorded;
no new epoch or admitted-environment authority is claimed. Final technical source is
`09293c195`, with registered generated outputs at `a255bdf01`. Do not mark the
deferred Foundry receipt paid until an independent owner review accepts the six
ratified claims against those identities.

## Final bound debt checker receipt — one invocation

The following command was run once after the implementation tree was quiescent,
with stdout and stderr redirected to a fresh absolute scratch file:

```bash
PYTHONPATH=. uv run --frozen --extra test python tools/quality/validation/check_debt_ledger.py \
  --check > /private/tmp/polisyos-gy-def22-bound-check.N1cGMS/bound-check.txt 2>&1
echo "EXIT=$?" >> /private/tmp/polisyos-gy-def22-bound-check.N1cGMS/bound-check.txt
```

The process completed normally with `EXIT=0`. The receipt has 57 lines and 8,315
bytes, SHA-256
`7a08694f245188f829ce418e2b18ac0a972be0d2eb27f74ea2387dc92014c680`.
It reports 189 register IDs, 38 GY IDs, 22 Atlas debt rows, and 44 pytest closure
selections. Collection failures, host-unknown collections, input-unresolvable
selectors, selects-nothing findings, and AST/collection disagreements are all zero.
Nine unresolved identities, nine count/exit disagreements, one unsupported runner,
and the listed source-standing ambiguities are explicitly informational and do not
block this checker. The GY-DEF22 informational row reads exactly:

```text
register_supplies_missing_standing: GY:GY-DEF22: register=open, source=ambiguous
```

No second checker invocation was made. This successful ledger check does not mint
the missing Foundry adjudication receipt or change GY-DEF22's open standing.

## Final Foundry adjudication receipt — 2026-09-04 continuation

Receipt reference: `GY-DEF22-FOUNDRY-ADJUDICATION-2026-09-04-01`.

The independent Foundry catalog/discovery reviewer
`/root/foundry_adjudication_final` resumed successfully and returned the explicit
verdict **ACCEPT — Task 7's six bounded Foundry claims**. This new receipt supersedes
the earlier adjudication non-receipt; the earlier record remains intact as history.
It is a reviewer acceptance, not an implementer self-countersign.

The acceptance is bound to these exact identities:

- technical source `09293c195939f9df73fa49091066b726bf57f33b`;
- registered generated-output tree `a255bdf011183a69f456fe3ceef86df7e2e20b1e`;
- reviewed clean journal HEAD `953a3a066d496cf72a6913f3d10cd815983fdb64`;
- companion
  `architecture/policy_design_case/layer3_gy_n8_dependency_discriminant.json`;
- companion semantic content hash
  `sha256:4dcf46b4810471ba8ecfe2931757e7c628fd5339e8044df7a246fe987cde84ec`;
- companion exact-file SHA-256
  `sha256:5a39c79778ad6878af03516e848b4b10942e3eca5bc6dcec083378675489867a`;
  and
- Foundry dependency source freeze
  `3ffb6ad5ed95d316656bc19946018a4eec52bc3b`.

The reviewer accepted each of the six ratified claims without asking for a changed
adjudication scope:

1. Purpose-to-profile selection remains in Foundry's content-bound registry
   resolver; the N8 producer does not accept caller-selected profile identity.
2. The dependency-only preimage and separate digest domain exclude production data
   and machine identity. Local replay appointment/cache coordinates are not part of
   the persisted preimage.
3. Closure traversal and first-case ordering are generic over owner registry, lock
   rows, and explicit marker inputs.
4. N8 is the registered producer; N8, N10a, chronology, and HTTP use the owner
   verifier. Transition readback requires all three named consumers and one shared
   binding.
5. The diagnostic remains `ambient_non_decisive`, with independently calculated
   governing results. The final `VALUE_GATE` change bypasses both cache reads and
   insertion, so ordinary environment drift cannot retain an old diagnostic.
6. The authority-grade chain remains `producer_missing`; all four separately named
   prerequisites remain `absent/unallocated`.

The authority boundary accepted by this receipt is exactly
`authoritative_for = [dependency_environment_diagnosis]`. It excludes N8 admission,
N10a stage-gap closure, chronology acceptance, policy publication, and policy
promotion. The three declared local-attacker residuals remain outside the acceptance
scope. No new in-scope recurrence was established and no further source repair was
made.

### Independent targeted verification

The reviewer ran one serial, nine-node wave against the frozen source:

```bash
PYTHONPATH=.:src .venv/bin/python -m pytest -q \
  tests/repo_quality/tools/test_execute_gy_n12_artifact_transition.py::test_cb_i01_n8_n10a_and_chronology_share_one_foundry_discriminant \
  tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i02_research_profile_names_torch_as_first_generic_case \
  tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i02a_label_and_shape_cannot_mask_two_data_generated_incompatibilities \
  tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i03_outside_closure_difference_is_diagnostic_irrelevant \
  tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i03a_novel_admitted_profile_verifies_from_owner_data \
  tests/unit/runtime/http/test_governed_projection_service.py::test_value_gate_owner_validation_does_not_cache_an_unbound_ambient_diagnostic \
  tests/repo_quality/tools/test_execute_gy_n12_artifact_transition.py::test_p38_ambient_diagnostic_cannot_govern_shared_consumer_results \
  tests/repo_quality/tools/test_execute_gy_n12_artifact_transition.py::test_invalid_and_removed_diagnostics_cannot_govern_shared_consumer_results \
  tests/repo_quality/tools/test_execute_gy_n12_artifact_transition.py::test_readback_rejects_consumers_bound_to_different_discriminant_copies
```

Result: nine passes, zero failure/skip markers, `[100%]`, exit `0`, execution session
`92814`. The invocation did not retain an exact wall-time measurement: the extra
`-q` combined with repository configuration suppressed pytest's summary. No output
receipt file was created. Neither a duration nor a file receipt is invented here,
and the wave was not repeated merely to obtain them.

The reviewer also rebuilt the companion through its real owner and confirmed
equality with the exact committed bytes. A wrong resolved-distribution version with
all internal hashes recomputed passed strict parsing but failed owner replay with
`dependency discriminant owner replay drifted`. The comparison/replay segment took
`0.860` seconds, excluding imports, and its probe exited `0`; this is not the
nine-test wave's duration.

**CB-I02 witness calibration:** the accepted fixture retains `torch==2.10.0` in the
data-derived research closure and changes its receipt-backed selected source. The
generic diagnostic names `distribution:torch:*` first and fails, while the actual
N8/N10a/chronology governing tuple remains byte-identical to the diagnostic-free
tuple. This is the already-ratified generic incompatibility witness, not a claim that
the version is intrinsically forbidden, a version-only ambient failure, or a fresh
execution of the historical cold-environment replay. CB-I02A independently covers
both the same-label in-closure substitution and the second data-generated
incompatible profile, with the same governing byte-equivalence requirement.

Root read back the frozen branch and exact-file hash, confirmed that only the
registered trust-posture output and journal differ from the final source commit,
and compared all five journal clause quotations to the spec with zero differences.
This continuation changes only the append-only journal. The six-claim acceptance
does not turn the separately documented architecture-guardrail failures into a
whole-repository green. The bound debt check remains the single recorded invocation
above, `EXIT=0`; it was not rerun.

## Final architect transcription — supersedes the earlier open-standing prose

These are the final transcription paragraphs. The implementer has not changed the
active register or GY plan; the architect applies these transitions at merge.

### `GY-DEF22` final close

**GY-DEF22 CLOSED 2026-09-04 — explicit `ambient_non_decisive` close, Foundry
adjudication received.** Receipt
`GY-DEF22-FOUNDRY-ADJUDICATION-2026-09-04-01` accepts the six ratified claims against
technical source `09293c195939f9df73fa49091066b726bf57f33b` and registered
generated-output tree `a255bdf011183a69f456fe3ceef86df7e2e20b1e`. Foundry owns
purpose-to-profile resolution and derives the complete dependency-only discriminant;
N8 produces the registered companion, and N8, N10a, chronology, and the governed
machine surface verify one semantic content ref,
`sha256:4dcf46b4810471ba8ecfe2931757e7c628fd5339e8044df7a246fe987cde84ec`.
CB-I01–CB-I03A are discharged with zero skips. CB-I02's research fixture retains
`torch==2.10.0` and detects a receipt-backed selected-source mismatch as the first
generic distribution case; it does not forbid that version by name. CB-I02A detects
both data-generated incompatibilities without a code edit or allowlist. Both clauses
prove diagnostic `fail` together with byte-identical actual N8/N10a/chronology
governing results when the diagnostic is removed. Outside-closure differences remain
irrelevant and a novel admitted profile verifies from owner data. The diagnostic is
authoritative only for dependency-environment diagnosis and cannot decide admission,
closure, chronology acceptance, publication, or promotion. The diagnostic capability
chain is implemented; the separate admitted-environment authority chain remains
`producer_missing`, with `owner_enforced_runtime_subtree_cutoff`,
`owner_resolved_resolution_receipt_store`, `platform_toolchain_admission`, and
`production_data_trust_policy` still `absent/unallocated`. The bounded threat model,
three accepted residuals, eight earlier repair rounds, final diff size, exact tests,
byte-equivalence evidence, and adjudication are recorded in the implementation
journal. No authority-grade capability is claimed by this close.

### GY plan `GY-N12` task row final append

**GY-N12 TASK-STANDING APPEND 2026-09-04 — status remains `executed`; deferred
GY-DEF22 mechanism and Foundry correctness receipt are now delivered.** Existing
Cluster 1 execution and ownership are unchanged. The follow-on supplies the
Foundry-owned dependency discriminant, N8 producer, one-ref N10a/chronology bridges,
governed machine surface, and CB-I01–CB-I03A semantic witnesses. Independent receipt
`GY-DEF22-FOUNDRY-ADJUDICATION-2026-09-04-01` accepts the six defined claims against
source `09293c195939f9df73fa49091066b726bf57f33b`, generated-output tree
`a255bdf011183a69f456fe3ceef86df7e2e20b1e`, and the exact companion identity recorded
in the implementation journal. Diagnostic failure, absence, corruption, and ambient
cache refresh do not change governing N8/N10a/chronology bytes or acquire admission,
closure, acceptance, publication, or promotion authority. The GY-DEF22 follow-on is
closed by the explicit non-decisive route. The positive authority capability and N12
boundaries 6–7 remain unchanged; no new epoch or admitted-environment authority is
claimed. The active task row itself is left for architect transcription at merge.
