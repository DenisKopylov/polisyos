# DS17 confidence-ledger risk-spend — C00 execution journal

## Admission identity and scope

- Attached execution branch: `codex/ds17-confidence-ledger-risk-spend-execution`.
- Exact execution base: `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f` (`main`).
- Product coordinate: `git rev-parse --show-prefix` returned `policy-engine/`.
- Required ancestors were re-read before the C00 writes: DS7 `74f26ca2d` ->
  exit `0`; N11 `f41d49071` -> exit `0`; DS11 merge
  `4ff11db52` -> exit `0`.
- C00 mechanism paths: **0/0**. The carried plan, this journal, and the three
  backend red-test companions are the only P39 companions. No production,
  generated, dashboard, Atlas/debt/LEDGER, deep-import, release, or other-slice
  path was written.
- Pattern pass before C00: P01/P02/P03 keep the actual N11 chain distinct from
  its missing DS17 surface; P04/P05/P09/P10/P15 require tagged, fail-closed
  future reasons; P29/P31/P32/P33 make these marker-constant and
  witness/admission reds semantic rather than form checks; P35/P37/P38 require
  complete denominators and the real gate predicate; P39 excludes the mandated
  companions; P41 attributes all observed reds to absent DS17 behavior, not
  inherited failures. The DS17 capability remains `absent/unallocated` at C00:
  a plan and red tests do not create a producer, artifact, bridge, consumer, or
  surface.

## DS11 landed-state receipt

The DS11 merge `4ff11db52` is an ancestor of the exact execution base. Both
required contribution walks against that base agree at **65/65**:

```text
git diff --name-only 4ff11db52^1 4ff11db52 | wc -l                         65
git diff --name-only $(git merge-base 4ff11db52^1 4ff11db52^2) 4ff11db52^2 | wc -l 65
```

The fresh no-writer replay completed exit `0`, `real 0.09`, `user 0.01`, `sys
0.02`, at uptime `21:00` -> `21:00`. Its operational-only ceiling is `30s`
(`2 × (0.01 + 0.02) < 30`). There is no disagreement to normalize.

### Review correction — independent parent walk

The first C00 journal incorrectly wrote the fork-to-merge command (fork →
`4ff11db52`) while recording the second-parent result. A fresh replay showed
that wrong comparison is **374**, not 65. The independent contribution property
is fork → second parent, so the corrected command ends at `4ff11db52^2` above.
This is review-round-1 **NEW P35**: the former receipt compared the wrong
complete set and was numerically false. Cost if wrong: the journal could call a
merge-result delta an independent branch contribution and conceal imported
first-parent changes.

## N11 census and inventory re-derivations

The N11 output census is pinned to `f41d49071`; the registry and persisted
artifact are read from the exact execution-base tree. Both the execution branch
and the clean exact-base `main` worktree report the same counts.

| complete denominator | independent derivations | execution branch | exact-base `main` |
| --- | --- | ---: | ---: |
| N11 projection declarations / public producers | AST class-declaration walk / AST `project_*` function walk over `src/polisyos/runtime/quality/confidence_ledger.py` at `f41d49071` | 3 / 3 | 3 / 3 |
| sole registry TOML | `tomllib` structural parse / whole-file `awk` section-and-role scan | 2 profiles, 7 pools, 5 proof profiles, 13 instruments, 6 routes; roles `1/5/11/1/6` (acquisition/admission/promotion/promotion-conformance/refusal) | same |
| sole persisted N11 JSON | Python `json` structural parse / `jq` complete checks-and-N9 walk | 3 checks = 1 refusal + 2 acquisition; 0 promotion rows | same |

The projection names are
`ConfidenceLedgerSemanticReceiptProjection`,
`N9PromotionCertificateProjection`, and `N12EpochReferenceProjection`; their
producer functions are `project_confidence_ledger_semantic_receipt`,
`project_n9_promotion_certificate`, and `project_n12_epoch_reference`.

The AST projection census completed exit `0`, `real 0.16`, `user 0.10`, `sys
0.03`, uptime `20:34` -> `20:34`; its ceiling is `30s`. The successful `awk`
inventory walk completed exit `0`, `real 0.00`, `user 0.00`, `sys 0.00`, uptime
`20:35` -> `20:35`; the `jq` persisted-instance walk completed exit `0`, `real
0.02`, `user 0.01`, `sys 0.00`, at the same uptime pair. Their ceilings are
`30s`. An initial inventory scanner used `index` as an awk loop variable and
therefore emitted a syntax error; its trailing `jq` succeeded, so it is a
tooling non-receipt and is excluded from these receipts. The corrected scanner
above is the accepted independent walk.

## C00 red witnesses

Collection succeeds for exactly the nine named red tests on the execution
branch: 3 coverage, 5 ledger-surface, and 1 HTTP. The exact-base `main`
worktree has **0/9** named tests (all three C00 companion files are absent).
The collection command completed exit `0`, `real 46.94`, `user 43.89`, `sys
1.82`, uptime `20:37` -> `20:37`; its operational-only ceiling is `91.42s`.

```text
tests/unit/runtime/http/test_confidence_ledger_risk_spend_api.py: 1
tests/unit/runtime/quality/test_confidence_ledger_surface.py: 5
tests/unit/runtime/quality/test_obligation_coverage.py: 3
```

The combined red command was:

```bash
uv run pytest \
  tests/unit/runtime/quality/test_obligation_coverage.py \
  tests/unit/runtime/quality/test_confidence_ledger_surface.py \
  tests/unit/runtime/http/test_confidence_ledger_risk_spend_api.py -q
```

The post-review RED run completed exit `1`, `9 failed`, `real 47.13`, `user
44.89`, `sys 2.09`, uptime `20:56` -> `20:56`; its operational-only no-writer
ceiling is `93.96s`. The initial equivalent RED run was also exit `1`, 9
failed; no RED became green.
All coverage and ledger-surface tests fail through their in-test dynamic module
checks, not during collection/import setup: C01 lacks
`polisyos.runtime.quality.obligation_coverage` and
`polisyos.runtime.quality.confidence_ledger_surface`. They are not import
sentinels: if either module exists, the witnesses call C01's planned concrete
owners, require strict DTO output, and exercise their mutation/falsifier. The
coverage witnesses derive an envelope then require the **surface** (not
coverage) owner to construct and bind `ConditionalDeltaAmount` from the
canonical N11 registry; they remove the ref/riders, move only on a typed
content-bound witness, and prohibit claim narrowing. The surface witnesses load
the canonical registry plus typed runtime N11 semantic ledger, derive C01's
seven available-domain values and C02's five-code allowset without accepting
caller enumerations, reject a typed-but-stale over-spend ledger through C02's
content-bound worker receipt before it can select a source blocker, then require
a test-local injected owner-source adapter to build a coherent content-bound
worker-evidence mutation (markers fixed, current-check sum above δ, allowlisted
non-empty issue set) before it can select
`source_blocked/over_spend`, prove caller Bayesian eligibility cannot create a
certificate, and require the valid-zero register. An empty or
marker-only C01 module therefore fails after dynamic import at the planned call
or assertion, rather than passing on path presence.

Review-round-1 **NEW P29** corrected the former module-existence shells;
the same **P29/ownership** bucket keeps C01 at seven available-domain values
and reserves C02's source-blocked over-spend arm. **P37/P38 owner-input
alignment** keeps reason/allowset derivation and projector authority on the
canonical registry plus typed runtime semantic-ledger source and a content-bound
worker receipt, not caller lists, raw validator strings, or a shaped one-check
dictionary.
Cost if wrong: a future module could echo user input or accept a display marker
as authority while all C00 reds passed.

The HTTP test reaches the real current router and fails its desired `200` typed
review-operation assertion with current **HTTP 422**, not a tooling error.
After self-review it additionally binds the required static-before-dynamic
ordering, `RUNS_REVIEW`, tenant-collection resource binding, analyst admission,
and viewer `403` denial. Its final one-test run remains an intended `422` RED:
exit `1`, `real 46.67`, `user 44.31`, `sys 2.25`, uptime `20:42` -> `20:43`,
with a `93.12s` operational-only ceiling.

The HTTP witness additionally resolves the future static route's
`response_model` with Pydantic `TypeAdapter`, requires a strict DTO/tagged-union
instance and round-trip payload, and rejects an unexpected field. This is
review-round-1 **NEW strict-typing** closure: a static route returning a raw
dictionary cannot satisfy the test once it reaches the desired `200` path.

A complete AST walk over all test Python files finds exactly the nine named
functions in the execution tree's 2,460-file denominator and none in the clean
exact-base main tree's 2,457-file denominator. The three-file denominator delta
is exactly the three C00 test companions. Ruff over those three files completed
exit `0` (`All checks passed!`), `real 1.00`, `user 0.05`, `sys 0.03`, uptime
`20:38` -> `20:38`; its operational-only ceiling is `30s`.

After the review corrections, the same three-file Ruff lane again completed
exit `0` (`All checks passed!`), `real 0.14`, `user 0.04`, `sys 0.04`, uptime
`21:07` -> `21:07`; its operational-only ceiling remains `30s`.

### Ruling — current-main 404 -> 422 route drift

The C00 brief described a missing-operation `404`; exact current main instead
has the generic dynamic route
`GET /api/v1/exports/governed-projections/{projection_id}`. It parses the DS17
slug as the existing `ProjectionId` enum and rejects it with `422` before a
static DS17 operation exists. C00 therefore preserves the semantic red: it
requires `200` from the desired static typed/review-protected operation and
truthfully records the observed dynamic-route `422`.

Cost if wrong: treating this as a manufactured `404` would hide the actual
static-before-dynamic shadowing requirement and could let a future operation
fall through to an unreviewed generic handler; treating the dynamic `422` as
the desired route would falsely declare a typed protected operation present.
No production route, enum, or test environment was altered.

## C00 continuation

The red-test implementation has no production behavior to turn green in this
cluster. C01 owns the two derived-negative domain modules; C02 owns the
protected static HTTP bridge. Reopen the failure/repair register before C06.

## C01 — typed derived-negative coverage and exact risk-spend projection

C01 adds exactly two mechanism paths:
`runtime/quality/obligation_coverage.py` and
`runtime/quality/confidence_ledger_surface.py`. The two C00 quality tests and
nearest runtime-quality README are P39 companions; this journal is the required
record companion. Reserve spend is **0**.

The coverage owner derives only `open_world_unresolved` or
`known_incomplete`. The latter requires a unique exact-key witness resolved
through `FileSystemCAS`, whose bytes, manifest kind/schema, producer/verifier,
scope, owner scope, protected action, and assessment key all bind. The real GY
OM-01 fixture rejects cross-scope; byte corruption, manifest substitution,
wrong key, duplicate refs, and shaped inputs reject. Source provenance remains
separate from searched sources and records canonical-registry admission versus
semantic-source worker admission not established. The closed reason tuple is
derived from the arm plus search/exclusion/independence predicates.

The surface derives 15 class allocation/spent/remaining/overspend rows, one
scope-local total row, 13 definition rows, the complete six-route register,
three instances (one refusal and two acquisition), and an explicit zero-entry
unappointed positive register. Every amount is an exact rational with an exact
canonical decimal, typed class when applicable, the exact scope/owner/envelope,
maintained assumptions, declared-class hash, and both disclosures. Projection
validation recursively binds every nested amount and route to the top-level
scope, resolved envelope, and registry. Domain admission revalidates, canonical
dumps, re-admits, and compares the complete typed projection/hash; missing,
unsupported, and malformed/invariant failures map to the applicable three of
the closed seven safety reasons. Packet/query-only reasons remain structurally
unreachable in C01.

### C01 measured gates

- Initial C00 focused RED: exit `1`, `8 failed` = six C01-owned plus the two
  explicitly C02-owned missing-owner tests; `real 32.26`, `user 28.45`, `sys
  1.54`, uptime `22:01` -> `22:02`.
- Final C01-only branch lane (the two exact C02 names deselected): exit `0`,
  `18 passed`, `real 27.52`, `user 25.64`, `sys 0.97`, uptime `23:11` ->
  `23:11`.
- Final four-path Ruff lane: exit `0`, `All checks passed!`, `real 0.09`,
  `user 0.02`, `sys 0.01`.
- Final branch importer-inclusive lane: exit `1`, `134 passed / 7 failed`,
  `real 1684.72`, `user 1571.40`, `sys 88.35`, uptime `23:11` -> `23:39`.
  Exactly two failures are C02-owned absent
  `runtime.http.services.confidence_ledger_risk_spend_projection`; all 18 C01
  cases are green. The other five are importer failures named below.
- Clean exact-base-main importer lane at `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`:
  exit `1`, `116 passed / 5 failed`, `real 1532.75`, `user 1418.11`, `sys
  66.84`, uptime `23:40` -> `00:05`. The five failures reproduce exactly and
  the C01 companion denominator is `0` because both files are absent at main.

The exact five P41-inherited importer failures are:

1. `test_deployment_identity_manifest_is_complete_and_import_order_independent`
   (`cg_substrate_unavailable:ortools_cp_sat:ModuleNotFoundError`);
2. `test_cross_process_negative_scope_membership_is_never_cached`;
3. `test_unlinked_held_lock_cannot_admit_replacement_writer`;
4. `test_same_process_recovery_cannot_close_a_live_owner_invocation`;
5. `test_cross_process_recovery_cannot_close_a_live_owner_invocation`.

They reproduce on the exact slice base and the C01 changed-path intersection
with their input owner (`confidence_ledger.py`) is empty, so they are inherited
environment/fork-lock reds rather than C01 debt. The only selected future-owner
reds are the two exact C02 names required by the C01 brief.

Two earlier long importer attempts are tooling non-receipts: the first wrapper
lost its stdout/timing capture, and the second was interrupted on controller
request while downstream C04 audited the producer contract. Neither contributes
counts or timings. A later pre-freeze replay was likewise stopped on controller
request before receipt and is excluded. The final branch and exact-main runs
above are the only accepted importer receipts.

Pattern pass: P29/P32 close through actual CAS resolution and canonical domain
re-admission rather than markers; P31 closes nested amount/route binding at the
projection chokepoint; P35 derives all class/instrument/route/reason
denominators from typed source sets; P37/P38 preserve unknown coverage and
worker admission as fail-closed states; P39 counts two mechanism paths; P40
widened the same mechanism to the complete consumer-required quantity; P41
classifies the five importer reds by exact-base replay. Capability state is
`surface_out_of_scope` for HTTP/dashboard/publication until C02/C04; the C01
domain producer, verification, and semantic tests are implemented.

## C01 independent-review correction — authenticated witness replay and recursive basis

The independent review bucketed the witness escape as the same P29/P32 class
and the coherent projection narrowing as a first NEW P35/P38 recursive-
admission class. Both close inside the existing two mechanism paths; mechanism
spend remains **2/2** and reserve remains **0**.

`known_incomplete` now requires two independently resolved CAS objects: the
source-owned omission artifact and its verifier receipt. Both blob/manifest
pairs must carry valid detached Ed25519 signatures under an externally supplied
trusted verifier with strict, exact producer/verifier identity bindings. The
resolver verifies CAS integrity, source kind/schema, actual source-content hash,
exact source scope/owner/action/assessment/issue/instance facts, a deterministic
source replay hash, and a code-owned verifier-provenance hash. A self-authored
manifest/model/hash/verifier string cannot select the arm. The real GY OM-01
source is persisted with its actual risk scope and omission values, then a
receipt relabelled to the DS17 scope is rejected from resolved source facts.
Unresolved, corrupt, content-mismatched, replay-mismatched, provenance-
mismatched, and untrusted-signature variants all fail closed.

The risk-spend projection now carries the exact typed registry and runtime
semantic-ledger bases from which it was built. Its model validator rebuilds the
entire projection body from those bases and canonically compares it before
checking the projection hash. This one recursive invariant covers the complete
15-class denominator and cross-row arithmetic, all 13 definitions, the complete
six-route registry denominator, all semantic instances and role partitions,
grouped/scope totals, blockers, positive-register predicates, good-event refs,
and reason-slot legality. Coherently removing a row while recomputing local
counts/hashes is therefore blocked. The validator does not expose a context or
boolean bypass and does not use `model_construct`.

### Independent-review correction receipts

- TDD RED (matching/source variants plus six coherent narrowing arms): exit
  `1`, `13 failed`; `real 37.09`, `user 35.56`, `sys 1.25`, uptime `00:27` ->
  `00:28`.
- Final C01-owned light lane (the two exact C02 tests deselected): exit `0`,
  `29 passed`; `real 29.27`, `user 28.34`, `sys 0.93`, uptime `00:36` ->
  `00:36`.
- Four-path Ruff: exit `0`, `All checks passed!`; `real 0.04`, `user 0.03`,
  `sys 0.01`, uptime `00:36` -> `00:36`.
- Delta-focused existing confidence-ledger importer lane: execution branch
  exit `0`, `8 passed`, `real 73.01`, `user 70.69`, `sys 1.93`, uptime `00:37`
  -> `00:38`; clean exact-base main exit `0`, `8 passed`, `real 81.94`, `user
  77.45`, `sys 2.85`, uptime `00:38` -> `00:40`.

P40 disposition is class-first: the repeated P29/P32 witness finding widened
the intake to the full signed source+receipt chain rather than another label
check; the first P35/P38 finding widened projection admission to a complete
source-derived body reconstruction rather than enumerating six mutation sites.
C02 remains the owner of governed worker admission, over-spend source blocking,
and HTTP integration; no C02 path or behavior changed.

## C01 P40 widening — downstream witness re-authentication

The C01 re-review classified a forgeable embedded `known_incomplete` envelope
as the SECOND finding of the SAME P29/P32 witness-admission class. Per P40, the
repair does not special-case the forged hash. It widens the existing mechanism
to the complete property: every public C01 boundary that can turn a coverage
arm into a projected or exact-admitted result must re-resolve the authenticated
exact-scope witness chain.

`reauthenticate_coverage_envelope` is the one reusable intake. It recomputes the
assessment key from rule version, exact scope/owner/action, and both source
identities; then re-runs signed CAS source+receipt resolution and requires the
resolved reference tuple to equal the envelope tuple. The public risk-spend
projector calls it before building any surface. Exact domain admission calls it
both before canonical serialization and after canonical re-admission. An open-
world envelope has no witness authority and remains self-contained; a non-empty
witness set requires the external CAS and trusted verifier at every admitting
boundary. The strict projection DTO is explicitly candidate parsing, never the
authority result.

The class-level falsifier substitutes an arbitrary `sha256:ffff…` witness into
an open-world envelope, coherently updates assessment/reasons/TTL/envelope hash,
rebinds every nested amount, updates the positive-register coverage reason, and
recomputes the projection hash. Candidate parsing remains possible, but the
public projector rejects before emission and exact admission blocks. The
positive companion proves one legitimate signed exact-scope witness traverses
builder -> projector -> exact admission, while the existing real GY OM-01
source continues to reject cross-scope.

### P40 widening receipts

- Focused TDD RED: exit `1`, `2 failed`; `real 29.67`, `user 27.29`, `sys
  1.34`, uptime `00:49` -> `00:50`.
- Final C01-owned lane (two exact C02 tests deselected): exit `0`, `31 passed`;
  `real 28.60`, `user 27.69`, `sys 0.93`, uptime `00:52` -> `00:52`.
- Final four-path Ruff: exit `0`, `All checks passed!`; `real 0.04`, `user
  0.03`, `sys 0.01`, uptime `00:53` -> `00:53`.
- Delta-focused existing confidence-ledger importer lane: execution branch
  exit `0`, `8 passed`, `real 73.74`, `user 71.84`, `sys 1.91`, uptime `00:53`
  -> `00:54`; clean exact-base main exit `0`, `8 passed`, `real 72.61`, `user
  68.73`, `sys 2.26`, uptime `00:54` -> `00:55`.

This is the one P40 widening round for the witness-admission class. Mechanism
spend remains **2/2**, reserve remains **0**, and no C02 owner path changed.

## C01 P40 widening verification — complete envelope rederivation

The boundary audit verified the already-declared P29/P32 widening property and
found that witness replay alone still let a coherently authored envelope choose
an arm. This is verification of the SAME widening, not another instance repair.
The structural invariant now admits a coverage arm only when the complete
canonical candidate equals a fresh `build_coverage_envelope` result derived
from the owner-supplied typed registry and semantic-ledger bases. Candidate
models, hashes, and witness presence are never capability tokens.

`rederive_and_admit_coverage_envelope` canonical-dumps and strictly reparses the
candidate, rebuilds it from the real bases and candidate witness references,
replays every non-empty reference through the owner-supplied CAS and trusted
Ed25519 verifier, and compares the complete canonical result. The public
projector, exact domain admission, and direct protected-action evaluator all
use this same intake. Exact domain admission additionally requires its embedded
registry and semantic bases to equal the owner-supplied bases before and after
canonical re-admission. A zero-reference envelope can therefore derive only
`open_world_unresolved`; changing its assessment with `model_copy` or
`model_construct`, or coherently rehashing another envelope member, cannot
acquire authority.

The behavioral falsifiers cover serialized/reparsed signed traversal, absent or
wrong resolver/verifier, coherent fake known-incomplete substitution at all
three arm readers, zero-ref `model_copy` and `model_construct` arm forgery,
rehash-preserving audience and may-not-use changes, and a genuine scope/action-A
witness relabelled to action B. Existing open-world evaluation continues
without resolver dependencies, the real GY source remains cross-scope rejected,
and `bounded_complete` remains structurally absent.

### Complete-rederivation receipts

- Focused TDD RED (signed traversal plus five forged/mutated cases): exit `1`,
  `6 failed`; `real 26.42`, `user 25.52`, `sys 0.93`, uptime `00:59` ->
  `01:00`.
- Final C01-owned lane (two exact C02 tests deselected): exit `0`, `35 passed`,
  `2 deselected`; `real 28.42`, `user 27.09`, `sys 1.35`, uptime `01:11` ->
  `01:11`. The complete unfiltered companion lane is `35` green plus the same
  two C02-owned missing-owner reds.
- Final four-path Ruff: exit `0`, `All checks passed!`; `real 0.03`, `user
  0.02`, `sys 0.00`, uptime `01:12` -> `01:12`.
- Delta-focused existing semantic-ledger importer lane: execution branch exit
  `0`, `8 passed`, `real 69.70`, `user 67.88`, `sys 1.82`, uptime `01:08` ->
  `01:09`; clean exact-base main at
  `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f` exit `0`, `8 passed`, `real
  71.61`, `user 68.56`, `sys 2.09`, uptime `01:09` -> `01:10`.
- A mistakenly widened import-identity selection was not used as a product
  receipt: it selected the known environment-dependent subprocess test and
  returned the already documented `ortools_cp_sat:ModuleNotFoundError` plus
  seven greens (`real 142.50`, `user 136.94`, `sys 5.46`).

Mechanism spend remains **2/2**, reserve remains **0**. C02 still owns worker
admission, source-blocked over-spend, and HTTP integration; no C02 or other
mechanism path changed.
