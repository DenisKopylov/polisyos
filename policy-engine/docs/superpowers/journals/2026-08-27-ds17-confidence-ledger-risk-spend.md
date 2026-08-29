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

## C01 P40 invariant completion — owner-supplied derivation context

The original reviewer verified the SAME P29/P32/P37 widening and found the
remaining zero-witness escape: the rebuild still sourced its protected action
and semantic provenance from the candidate. The correction completes the
declared invariant rather than opening a new repair round.

`CoverageDerivationContext` is a strict, frozen, extra-forbid owner input with
exactly the three non-derived envelope-builder values that are not present in
the typed registry or semantic ledger: `protected_action_id`,
`semantic_source_ref`, and `semantic_source_verifier_ref`. C02 will later
construct this context at its worker/source-owner boundary. C01 does not mint or
infer it.

Complete `build_coverage_envelope` input census:

- owner typed bases: `registry`, `semantic_ledger`;
- owner fixed derivation inputs: `derivation_context` and its three fields;
- owner verification boundary: `witness_store`, `witness_verifier`;
- candidate-carried replay request: `witness_refs`, which remains non-authority
  until every ref resolves through that owner verification boundary.

There are no other non-derived builder inputs. During rederivation the
candidate is used only for strict canonical parse/reparse and its witness-ref
tuple. The builder receives action and both semantic source identity values
only from the independently supplied context. Projector, exact admission, and
direct protected-action evaluation all require and pass the same context.

The complete behavioral census coherently mutates and rehashes each of the
three context-owned fields in a zero-witness candidate while holding the owner
context constant; every arm reader rejects. The inverse falsifier holds the
candidate constant and mutates each owner-context field; every arm reader also
rejects. A matching owner-context open-world envelope traverses without
resolver dependencies. A signed known-incomplete envelope traverses builder ->
projector -> exact admission -> evaluator only with the matching context; a
wrong context blocks. The real GY source and signed cross-action relabel remain
rejected.

### Owner-context receipts

- Focused property RED: exit `1`, `3 failed`; `real 26.14`, `user 25.30`,
  `sys 0.88`. The wrapper did not capture an uptime pair, so RED uptime is
  `not_established` and is not used as a timed green receipt.
- Final C01-owned lane: exit `0`, `39 passed`, `2 deselected`; `real 28.82`,
  `user 27.93`, `sys 0.91`, uptime `01:33` -> `01:33`.
- Honest unfiltered companion lane: exit `1`, `39 passed`, `2` exact C02-owned
  missing-owner failures; `real 28.75`, `user 27.80`, `sys 0.96`, uptime
  `01:36` -> `01:37`.
- Final four-path Ruff: exit `0`, `All checks passed!`; `real 0.03`, `user
  0.02`, `sys 0.00`, uptime `01:33` -> `01:33`.
- Delta-focused semantic-ledger importer lane: execution branch exit `0`, `8
  passed`, `real 69.86`, `user 68.05`, `sys 1.83`, uptime `01:34` -> `01:35`;
  clean exact-base main at `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`
  exit `0`, `8 passed`, `real 73.16`, `user 68.23`, `sys 2.26`, uptime `01:35`
  -> `01:36`.

Mechanism spend remains **2/2**, reserve remains **0**. No C02 or other source
path changed. The unchanged C02 concern is governed worker admission,
source-blocked over-spend, and HTTP integration.

## C02 source freeze — governed confidence-ledger risk-spend bridge

C02 closes its declared backend boundary with exactly six mechanism paths and
reserve spend **0**. The generic governed-projection denominator remains 13;
the N11 source is a separate one-member guarded catalog and the specialized
static GET is its only HTTP emission. The packet is a strict four-arm union
using exactly `available`, `source_blocked`, `artifact_missing`, and
`invalid_source`.

The existing isolated governed-projection worker runs the real N11
`validate_payload`, strict-parses the validator-admitted
`real_ledger_projection`, and requires exact canonical equality to the
requested projection. It resolves the canonical registry through its owner
loader and independently derives source equality, exact check-spend sum, and
registry delta. The service constructs C01's `CoverageDerivationContext` from
fixed owner worker/source facts, never from the candidate.

`source_blocked/over_spend` requires the complete issue set to be a non-empty,
duplicate-free subset of exactly these five normalized owner diagnostics:

- `semantic_forged_spend_row`;
- `semantic_total_spend_drift`;
- `semantic_budget_status_drift`;
- `semantic_deterministic_spend_nonzero`;
- `deterministic_real_run_spend_nonzero`.

It additionally requires validator-admitted source/request equality and an
independent exact `sum(check.spend) > registry.policy.delta`. Persisted
`total_spend` and `within_budget` never gate. Any outside issue, malformed
source, forged dependency/registry identity, or source/request mismatch is
`invalid_source`; the blocked arm leaks no rejected detail.

The single route is
`GET /api/v1/exports/governed-projections/confidence-ledger-risk-spend`,
declared before the dynamic path with `RUNS_REVIEW`, `TENANT_COLLECTION`,
`allow_empty_body=True`, a strict response model, and Rego resource
`runtime.governed_projection.confidence_ledger_risk_spend`.

### C02 denominator and schema receipts

Complete branch / exact-base censuses are: OpenAPI paths 102/101; operations
104/103; GET 72/71; POST 32/32; protected 41/40; `runs.review` 8/7; route
decorators 106/105; decorator GET 74/73; governed GETs 5/4; Rego resource
classes 40/39; Rego `runs.review` rows 8/7; curated success examples 100/99.
The generic projection IDs/definitions/models/projectors remain 13/13/13/13;
the hidden channels remain 3; Rego permissions/action contracts remain 34/26;
mutating operations remain 32; and generated client public methods remain 81
until C03 moves them to 82. The brief's prose value 31 for mutating operations
is stale against the complete executable 32/32 base-and-branch census and was
not used to change a foreign constant.

The canonical OpenAPI exporter produced two independent scratch outputs and
the tracked schema with byte equality in both comparisons. The tracked SHA-256
is `fb1c077387b5f677835c6182425c34b104a2dd506c2d69868e9ab83a2f6cfc5f`.
No client writer ran in C02; the six generated outputs remain an intentional
C03 transaction.

### C02 verification receipts

- Initial carried-owner RED: 3 failures (the two C02 owner tests plus absent
  static route), exit `1`; strict new companions initially failed collection
  on the absent contracts module, exit `2`.
- Final specialized lane: exit `0`, `14 passed`; real `138.45`, user `132.38`,
  sys `5.63`, uptime `02:54` -> `02:56`. The two exact C02-owned carried reds
  alone are `2 passed`, exit `0`; real `26.73`, user `25.75`, sys `0.93`,
  uptime `02:56` -> `02:57`.
- Prescribed six-file lane: `102` collected, exit `1`, `99 passed`, `2
  skipped`, and one Cycle Board red; real `389.21`, user `369.91`, sys `15.81`,
  uptime `03:05` -> `03:11`. Clean exact base lacks the three C02 companions;
  its surviving three files collect `89` and return exit `1`, `86 passed`, `2
  skipped`, and the same Cycle Board red; real `254.43`, user `243.11`, sys
  `10.50`, uptime `03:35` -> `03:39`.
- Targeted Ruff is green. OPA strict compile is branch/base `0/0`; structured
  policy tests are `45/45` on both. Rego parity is `24/24` on both.
- Runtime authz is the exact same branch/base `154 passed, 7 failed`; the new
  operation is GET-only. Schema hardening is branch `19 passed, 3 failed`
  versus base `21 passed, 1 failed`: the shared epoch-example red plus exactly
  two intentional stale-client assertions. Runtime contract likewise adds only
  `runtimeApiClient.ts/.js` drift to the shared epoch-example finding.

The Cycle Board 400 (`historical producer availability owner row is absent`),
seven POST authz reds, and epoch success-example red reproduce on clean exact
base and are not C02 repairs. Clean C02 entry `c8fae70b7` already emits four C01
deep-import findings and `trust-claim-posture-register` drift; C02 does not
baseline or repair them. Current architecture output adds only the six expected
C03 generated-client/dashboard files. Exact slice base passes architecture
guardrails; clean C02 entry and current C02 fail for the separately classified
slice/C03 reasons above.

C02's owner-validated reviewer HTTP sub-capability is `implemented`. The full
DS17 slice remains `consumer_missing` until C03-C05 generate the client and add
the dashboard/twin consumer. No reserve, second route/source/UI, foreign
contract stop, or 23rd mechanism path was encountered.

## C02 append-only correction — owner intake and recursive issue census

The first C02 review result above is superseded. Finding 1 is the **SAME**
P05/P32/P33/P37 owner-context-selection class already identified at C02. It is
closed by one intake invariant before either blocker selection or C01
derivation: the guarded ID, canonical path, source schema, absent source rule,
and validator ID/version come from the owner catalog constants; the service
re-reads and SHA-256 binds the canonical bytes; strict-parses the embedded
`real_ledger_projection`; requires exact equality to the requested semantic
payload; loads the registry through the canonical owner loader; and reconciles
nested/outer validation, worker receipt, artifact, dependency, registry, and
semantic hashes. The `available` arm additionally requires passed validation,
an empty issue set, and owner-derived source/request equality. C01 receives the
fixed owner source/verifier context, never values selected from the candidate.
The strict packet independently fixes the same canonical source/validator
facts, every nested/outer binding, and the exact `authoritative_for` and
`may_not_use_for` tuples even after a coherent packet rehash.

Finding 2 is the first finding of a **NEW** P29/P33/P37/P38 recursive issue-set
class. The worker now walks every descendant of arbitrary mappings and
non-string sequences, collects every issue-object `code`, and performs the
single normalization only after traversal. A real validator wrapper inserts
`outside_diagnostic` under an otherwise allowed issue's nested `detail`; the
real isolated worker retains both codes and worker -> service -> protected API
returns `invalid_source`, never `source_blocked`. No rejected issue detail is
emitted.

The deferred C00 P29/P32 shell is also replaced without a new mechanism. Its
two tests generate coherent and stale-marker N11 artifacts, derive the exact
five-code denominator from actual `validate_payload` emissions, and traverse
the real worker plus `ConfidenceLedgerRiskSpendProjectionService`. They assert
typed `source_blocked/over_spend`, while independently proving exact check
spend exceeds canonical delta even though persisted `total_spend` is zero and
`within_budget` remains true. The duplicated five-code literal and direct
classifier invocation are gone.

### Correction falsifiers and receipts

- The complete coherent-forgery set has 19 variants: nine fully typed source
  resolutions (path, schema, rule, validator ID/version, nested receipt,
  artifact, dependency, and available issue) plus ten strict-JSON packet
  rehashes (source equality, nested receipt, issue, path, schema, rule,
  validator ID/version, empty authority, and empty limitations). The initial
  16 review variants were red before the invariant; the nested real API probe
  specifically returned `source_blocked` instead of `invalid_source`. A final
  source schema/rule audit added three genuine reds. The final 19-variant lane
  is exit `0`; `real 59.88`, `user 55.79`, `sys 4.12`, uptime `04:57` ->
  `04:58`.
- The final correction cluster is exit `0`, **34 passed**; `real 246.88`,
  `user 236.22`, `sys 11.10`, uptime `04:59` -> `05:03`. The C00 real-path pair
  alone is exit `0`, **2 passed**; `real 79.38`, `user 76.40`, `sys 2.60`,
  uptime `04:28` -> `04:29`.
- The full worker lane is branch/base 11 collected, **10 passed, 1 skipped**;
  branch exit `0`, `real 106.05`; exact slice base exit `0`, `real 83.23`.
  The governed-service importer lane is branch/base 69 collected, **68 passed,
  1 skipped**; branch/base exits `0/0`, `real 210.92/211.25`.
- Runtime authz remains the exact same branch/base **154 passed, 7 failed**;
  branch `real 124.23`, exact base `real 94.75`. OpenAPI hardening remains
  branch **19 passed, 3 failed** versus exact base **21 passed, 1 failed**:
  both retain the foreign epoch-example red and branch adds only the two
  intentional C03 stale-client assertions. No C02 correction path intersects
  those inherited/next-cluster failures.
- Targeted Ruff is green. The final canonical OpenAPI scratch A/B exports are
  byte-identical; the canonical tracked writer is byte-identical to them at
  SHA-256
  `97d9ac1a5e12ecaf23efb1d4d6563b6d74f3e3d9b3d7711cba2217dc5f1e0d65`.
  The changed example hashes are owner-derived consequences of the corrected
  validation dependency/receipt; the route/schema denominator is unchanged.
  The six generated client/dashboard outputs remain the intentional C03
  transaction.

The bounded correction changes only four of the already-declared six C02
mechanisms and their existing tests; the canonical schema and this journal are
P39 companions. Generic `ProjectionId` remains 13, and no second route, source,
UI, test adapter outside tests, reserve path, foreign contract, or forbidden
debt repair was added. C02 reserve remains **0**.

## C02 P40 widening — execute the owner, do not accept its attestation

The second C02 review is the **SECOND finding of the SAME P05/P32/P37
owner-attestation class**. Per P40, C02 does not add another equality to the
typed resolution. The supported service seam is widened to the real owner
quantity instead: construction accepts only a repository root, and every
`get()` creates the real `GovernedProjectionService` and executes its isolated
owner worker over the canonical source. A hand-authored
`GuardedProjectionSourceResolution` therefore cannot enter the constructor or
service API. The worker receipt remains the content hash of the complete typed
worker result, including status, issues, source/request equality, recomputed
spend, registry facts, dependency bindings, and validator identity.

Offline packet parsing is now named `ConfidenceLedgerRiskSpendPacketCandidate`
and is explicitly structural/coherence-only. A candidate with coherent
substitutions for artifact, dependency, registry, and worker-receipt identities
strict-parses after its self-hash is refreshed; this is the required proof that
self-hashes do not authenticate provenance. No parsed packet/candidate
parameter exists on the owner service, so its labels and substituted receipts
cannot select `available` or `source_blocked`. The HTTP response alias retains
the same strict four-arm wire schema; no signer, second source, route, or
offline admission capability was invented.

### Widening falsifiers and final receipts

- The exact seam pair was genuinely red before the widening: the coherent
  hand-authored typed resolution entered as `source_blocked` while the coherent
  offline candidate test already demonstrated structural parsing (`1 failed, 1
  passed`, exit `1`; real `53.88`, user `51.70`, sys `2.16`, uptime `05:36` ->
  `05:37`). With the constructor seam removed the same pair is `2 passed`, exit
  `0`; real `53.83`, user `51.69`, sys `2.15`, uptime `05:37` -> `05:38`.
- Six owner-path falsifiers cover canonical scratch `available`, coherent
  scratch `over_spend`, missing/malformed/forged scratch `invalid_source`, the
  forbidden typed-resolution constructor, coherent packet candidate parsing,
  and the nested outside-code API path: `6 passed`, exit `0`; real `182.34`,
  user `176.37`, sys `6.23`, uptime `05:39` -> `05:42`.
- The source-frozen final cluster contains all three specialized test modules
  plus the two C00 real-worker replacements: **26 passed**, exit `0`; real
  `276.26`, user `262.51`, sys `13.01`, uptime `06:04` -> `06:08`. At clean C02
  entry `c8fae70b7`, the exact C00 pair is still exactly two missing-owner-module
  reds, exit `1`; real `31.59`, user `30.13`, sys `1.42`, uptime `06:04` ->
  `06:04`. Exact slice base predates the test pair and therefore collects
  neither; that absence is not classified as a test failure.
- Canonical OpenAPI scratch A/B and tracked writer bytes compare equal at
  SHA-256
  `19cc6ae5a7a46685cb00a87e7b02ebec6e9ea59c2fee7c96ff856c1f3d4ddb41`.
  Schema hardening is branch **19 passed, 3 failed** versus exact slice base
  **21 passed, 1 failed**: both retain the epoch-batch success-example red and
  branch adds only the two intentional C03 generated-client/shared-types reds.
- Runtime authz remains exact branch/base **154 passed, 7 failed**. The static
  governed-route importer remains branch/base **8 passed, 1 failed**, with the
  same inherited Cycle Board 400. Targeted Ruff and `git diff --check` both
  return exit `0`.
- Architecture guardrails return exit `0` on exact slice base. Clean C02 entry
  returns exit `1` with exactly the four C01 deep-import edges and
  `trust-claim-posture-register` drift; current C02 returns those same five
  findings plus only the six intentional C03 generated outputs. The C02-entry
  receipt is real `67.11`, user `59.23`, sys `7.98`, uptime `06:01` -> `06:02`;
  current/exact-base receipts are real `69.96/69.51`.

The widening changes only three already-declared C02 mechanism paths: the
static route's service provider, the specialized packet contracts, and the
specialized projection service. Its existing three test companions, canonical
schema, and this journal are outside the P39 mechanism count. The other three
C02 mechanisms remain unchanged, generic `ProjectionId` remains 13, and every
previous route/Rego/schema denominator remains frozen. Reserve remains **0**.

## C02 cache-currentness correction — owner receipt reuse is not per-GET execution

Review found a **NEW P38 current-execution/cache-proxy class**. This section
supersedes every r2 phrase above that says each `get()` executes the worker, the
result is a fresh execution, or each arm carries a fresh receipt. The r2 commit
subject is historical, not a per-call contract. The owner-correct property is:
each request resolves through `GovernedProjectionService`; the first unique
exact owner identity executes the real isolated worker; an unchanged identity
may reuse only that content-bound passed receipt after current source and every
recorded dependency identity are revalidated; any decisive key/currentness
change executes the worker again and reclassifies. A typed resolution or packet
still cannot enter or seed the cache.

The complete cache/currentness denominator, read from `_run_owner_validation`,
is:

1. pre-lookup guards re-evaluate the current expected source schema and rule;
2. the exact cache key is resolved repository root, projection ID, current
   expected owner-validator ID, current expected owner-validator version,
   source content hash, the complete sorted `(relative path, content hash)`
   component-binding tuple, and the canonical projected-payload hash;
3. a cache hit re-hashes **every** path/identity in the complete dependency
   manifest recorded by the worker (file bytes, directory listing, missing,
   unreadable, or special-file identity); a malformed/outside-root binding or
   any mismatch rejects reuse;
4. only `passed` results are cached, and the locked second lookup repeats the
   same dependency-currentness check;
5. a new worker result is admitted only after strict result parsing and exact
   reconciliation of projection ID, validator ID/version, complete component
   identities and aggregate, projected-payload hash, dependency aggregate, and
   required component dependencies. The worker receipt hash covers the complete
   typed result.

The audit found one decisive omission: current expected validator ID/version
were used to admit a worker result but absent from the cache key. A coherent
validator-version change therefore reused the old receipt and returned
`available`. Both identity members are now part of the generic key; this fixes
the mechanism for every governed projection, not only the C02 instance. The
expected source schema/rule configuration is deliberately a pre-lookup guard
rather than a key member because it is not passed to the worker: a mismatch
blocks before cache lookup, and a current match cannot change the worker
computation over the already-keyed source bytes.

### Cache falsifier and focused receipts

- The specialized test delegates to the unmodified real subprocess and only
  counts executions. Before the key fix it fails at the validator-currentness
  boundary: changed expected validator version returns cached `available`
  (`1 failed`, exit `1`; real `105.90`, user `102.44`, sys `3.44`, uptime
  `06:43` -> `06:45`).
- Final behavior is exact: first plus unchanged request executes once and
  returns the same receipt; coherent canonical source-byte change executes a
  second time and selects `source_blocked/over_spend`; exact source restoration
  reuses the original receipt with the count still two; validator-version and
  validator-ID changes execute the third and fourth workers and both return
  `invalid_source`; an attempted packet candidate changes neither the cache
  snapshot nor the count. The final specialized test is `1 passed`, exit `0`;
  real `131.06`, user `127.19`, sys `3.84`, uptime `07:02` -> `07:04`.
- The focused cache family adds the coherent offline-candidate non-ingress test
  and the generic full-dependency-manifest and exact-payload-key tests: `4
  passed`, exit `0`; real `157.85`, user `152.59`, sys `5.22`, uptime `06:53`
  -> `06:56`.
- The complete governed-service importer denominator is branch/base 69
  collected, **68 passed, 1 skipped**, exit `0/0`; branch real `207.20`, user
  `194.54`, sys `7.80`, uptime `06:56` -> `06:59`; exact slice base real
  `209.96`, user `197.35`, sys `8.15`, uptime `06:56` -> `07:00`. Targeted Ruff
  is exit `0`, `All checks passed!`.

This bounded correction changes three already-declared C02 mechanisms
(`governed_projections.py`, the specialized packet contracts, and the
specialized projection service), the existing specialized service test, and
this journal. No schema, route, Rego, generated client, generic projection ID,
second source, UI, signer, or reserve path changes. All previously frozen route
denominators remain unchanged and C02 reserve remains **0**.

## 2026-08-29 — C02 r4 guarded-cache P40 closure

The next review found the **SECOND SAME P38 cache-currentness class**, one
level below the seven-member cache-key correction above. `DependencyTracker`
is rooted at the configured artifact repository: `_relative` deliberately
drops every loaded module or consulted path outside that root. The supported
worker environment also prepends application source and preserves inherited
`PYTHONPATH`. Therefore a separately rooted validator hook can change while
the artifact-root-relative dependency manifest remains unchanged. Before this
correction, a first `available` receipt was reused after that hook changed; a
cache clear then exposed the real second execution as `invalid_source`.

Per P40, this section supersedes the preceding r3 claim that the recorded
dependency manifest is complete for every supported execution input. It also
supersedes r3's DS17 reuse behavior. No third cache-key/currentness equality was
added. The owner quantity C02 can establish with its existing mechanisms is:
**every request for the fixed guarded confidence-ledger source executes the
real isolated owner worker over the current source and supported environment**.
The generic governed-projection cache remains unchanged for the 13 dynamic
projection IDs.

### Complete cache and guarded-bypass denominator

The current `_run_owner_validation` control flow is complete as follows:

1. Every projection rechecks expected source schema and rule before deriving
   any cache behavior.
2. The generic cache key still has exactly seven quantities: resolved artifact
   repository root; projection ID; expected validator ID; expected validator
   version; source content hash; complete sorted component-binding tuple; and
   canonical projected-payload hash.
3. For the fixed `confidence-ledger-risk-spend` guarded ID,
   `cache_enabled` is derived internally as false. The function performs no
   optimistic lookup, locked lookup, stale-entry pop, or successful-result
   write. There is no caller-controlled bypass flag. Each request proceeds to
   the fixed isolated-worker subprocess and the complete worker-result
   reconciliation.
4. For every generic dynamic projection ID, `cache_enabled` remains true. Both
   lookups re-hash the complete recorded artifact-root-relative dependency
   manifest; the locked path evicts stale entries; only a reconciled `passed`
   result is written. The r3 validator-ID/version key correction remains in
   force for this generic family.
5. A new worker result remains strict-parsed and reconciled against current
   projection ID, validator ID/version, complete component identities and
   aggregate, projected-payload hash, dependency aggregate, and required
   component dependencies. Its receipt hash remains content-bound to the full
   typed worker result. An offline packet or typed resolution remains
   structurally incapable of entering the service or cache API.

The bounded residual is explicit: the generic governed-projection cache cannot
prove currentness for execution code or environment dependencies outside the
single configured artifact root, including application-source modules and
inherited `PYTHONPATH`. The smallest missing future capability is
**governed-projection dependency-tracker multi-root execution provenance**,
covering artifact root, application source, and inherited import roots. Its
future owner is the governed projection dependency tracker; it is absent and
outside C02. C02 does not edit `governed_projection_dependencies.py`, spend a
reserve path, or claim the generic residual is repaired. The residual cannot
stale DS17 because DS17 performs no validation-cache reuse.

### Behavioral falsifiers and receipts

- Exact two-test RED before the bypass: unchanged source executed once rather
  than twice, and a changed separately rooted `sitecustomize.py` validator hook
  still returned cached `available` rather than `invalid_source`: **2 failed**,
  exit `1`; real `79.97`, user `77.35`, sys `2.61`; uptime `07:32` -> `07:33`.
- Exact two-test GREEN after the bypass: unchanged source executes twice through
  the real subprocess and may produce the same content-bound receipt; the
  external hook change causes the second request to execute again and return
  `invalid_source`; the guarded global cache remains empty; a packet-candidate
  argument raises `TypeError` and seeds nothing: **2 passed**, exit `0`; real
  `130.05`, user `126.06`, sys `3.95`; uptime `07:34` -> `07:36`.
- Complete specialized service file plus both existing generic cache
  regressions: **10 passed**, exit `0`; real `260.42`, user `252.32`, sys
  `8.00`; uptime `07:38` -> `07:43`. The generic cases prove unchanged receipt
  reuse plus dependency-byte and projected-payload invalidation remain green.
- Targeted Ruff across the three mechanisms and specialized test: `All checks
  passed!`, exit `0`; real `0.04`, user `0.03`, sys `0.01`; uptime `07:44` ->
  `07:44`.
- Complete governed-service importer at branch and exact slice base
  `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`: both collect 69 and report **68
  passed, 1 identical explicit read-only-witness skip**, exit `0/0`. Branch:
  real `191.62`, user `183.24`, sys `6.85`, uptime `07:44` -> `07:47`. Exact
  base: real `195.54`, user `186.64`, sys `7.26`, uptime `07:48` -> `07:51`.

This correction changes the same three declared C02 mechanisms
(`governed_projections.py`, specialized packet contracts, and specialized
projection service), the existing specialized service test, and this journal.
No dependency-tracker, schema, route, Rego, generated client, generic
`ProjectionId`, second source, UI, signer, or foreign-debt path changes. All
route/schema/authz denominators remain frozen from the approved C02 surface;
C02 reserve remains **0**.

## C01 architecture correction — supported core facades

After C02 approval, a read-only facade audit proved that the supported
`polisyos.core` root already exports `canon` and `artifacts` module objects that
are identity-equal to `polisyos.core.canon` and `polisyos.core.artifacts`.
Therefore the four C01 deep-import edges required no facade addition, baseline,
exception, inventory, or reserve path.

The two existing C01 mechanisms now import only the supported root modules.
`confidence_ledger_surface.py` imports runtime `canon` and type-only
`artifacts`; `obligation_coverage.py` imports both modules at runtime. Every
canonicalization, hashing, CAS/verifier annotation, and runtime `isinstance`
check is module-qualified. No behavior, DTO, test, core facade, public
inventory, generated output, trust register, client output, or C02 path
changed.

### Architecture correction receipts

- Pre-correction deep-edge census found exactly four edges: both C01 importers
  to both `polisyos.core.canon` and `polisyos.core.artifacts`. The architecture
  gate returned exit `1` with those four edges plus six declared C03 generated-
  client drifts and one declared trust-register drift; `real 154.88`, `user
  134.62`, `sys 19.65`, uptime `08:19` -> `08:22`.
- Post-correction deep-edge census over the complete two-importer denominator is
  `0` (`rg` no-match exit `1`; `real 0.01`, `user 0.00`, `sys 0.00`). Public
  root identity probe exit `0`: both `core.canon is polisyos.core.canon` and
  `core.artifacts is polisyos.core.artifacts`; `real 0.56`, `user 0.35`, `sys
  0.08`, uptime `08:31` -> `08:31`.
- C01-owned behavioral lane is unchanged: exit `0`, `39 passed`, `2`
  C02-owned tests deselected; `real 74.00`, `user 69.14`, `sys 2.97`, uptime
  `08:23` -> `08:24`.
- Focused mypy was available and ran over both mechanisms: exit `1`, `30`
  module-semantic errors, with no import/name/facade error; `real 66.83`, `user
  61.19`, `sys 4.32`, uptime `08:25` -> `08:26`. Exact-main comparison is not
  applicable because the C01 modules are absent at the exact slice base; this
  gate is recorded honestly as non-green rather than used as a completion
  receipt.
- Four-path Ruff: exit `0`, `All checks passed!`; `real 0.11`, `user 0.04`,
  `sys 0.02`, uptime `08:31` -> `08:31`.
- Post-correction execution-branch architecture gate: exit `1`, exactly seven
  declared non-C01 drifts remain (six C03 generated-client outputs and one
  trust-register output); `real 157.73`, `user 133.99`, `sys 20.41`, uptime
  `08:26` -> `08:28`. The four C01 deep edges are absent.
- Clean exact-base main `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`
  architecture gate: exit `0`, `Architecture guardrail check passed`; `real
  147.75`, `user 125.79`, `sys 17.24`, uptime `08:29` -> `08:31`.

Mechanism spend remains **2/2**, reserve remains **0**. The remaining
architecture reds are owned outside C01; no exception or baseline was added.

## 2026-08-29 — C02 canonical schema companion refresh

C03 stopped correctly before its six-file client transaction after the C01
public-facade correction changed the guarded validator's byte-dependency
receipt. At clean attached HEAD `a7b12125e`, the tracked runtime schema still
had SHA-256
`19cc6ae5a7a46685cb00a87e7b02ebec6e9ea59c2fee7c96ff856c1f3d4ddb41`.
The runtime contract pre-write receipt was exit `1`; it reported the canonical
OpenAPI drift, the inherited epoch-batch missing-success-example violation,
and the two base runtime-client outputs from the intentionally deferred C03
six-file family. Real `185.12`, user `158.24`, sys `8.79`; uptime `08:58` ->
`09:02`.

The canonical exporter then wrote two independent ignored scratch targets and,
only after their equality was established, the tracked schema:

- scratch A: exit `0`; real `165.30`, user `148.29`, sys `7.40`; uptime
  `09:02` -> `09:06`;
- scratch B: exit `0`; real `175.91`, user `153.79`, sys `8.05`; uptime
  `09:06` -> `09:09`;
- A <-> B: `cmp --silent` exit `0`;
- canonical tracked writer: exit `0`; real `172.73`, user `150.33`, sys
  `8.06`; uptime `09:10` -> `09:14`;
- A <-> tracked and B <-> tracked: both `cmp --silent` exit `0`;
- all three SHA-256 values:
  `bdff039ca63e0f5d6a4afb7e2581a3e8c3278e28873d3b42c6dcbc1905524fc1`.

Before, scratch A, scratch B, and tracked after the write all have the same
complete structural denominator: **102 paths, 104 operations, 72 GET, 32 POST,
and 501 component schemas**. The full source-of-truth diff changes exactly nine
value leaves in the single DS17 available example: outer and replay-pin
projection hashes; replay address; outer, replay-pin, and nested validation
dependency identities; nested and outer worker-receipt hashes; and the outer
worker-receipt ref. No path, operation, response shape, component schema,
route, authorization, Rego, source, or mechanism changed.

Post-write verification separates the intentionally unclosed transactions:

- runtime contract: exit `1`, with **no OpenAPI drift**; only the inherited
  epoch-batch example violation and stale `runtimeApiClient.ts/.js` remain;
  real `166.32`, user `149.54`, sys `7.88`; uptime `09:15` -> `09:19`;
- complete schema-hardening file: 22 collected, **19 passed / 3 failed**, exit
  `1`; the exact failures are the same inherited epoch violation plus the
  committed-runtime-client pipeline and shared-types checks that represent the
  intentional stale six-client C03 transaction; real `246.49`, user `234.74`,
  sys `13.31`; uptime `09:19` -> `09:23`.

No tracked client writer, client, source, release, route, Rego, or mechanism
path was touched. This P39 companion correction has exactly two tracked paths:
`schemas/runtime_api_v1.openapi.json` and this append-only journal. It spends no
C02 mechanism path and reserve remains **0**.

## 2026-08-29 — C03 generated-client completion

C03 consumes the frozen C02 schema without changing it. The cluster has zero
mechanism paths and exactly seven P39 companions: the five generated
`runtime-api-client` files, the generated dashboard API type file, and the
structured release fragment. This journal is the mandatory append-only record
and remains outside the mechanism count. No source, route, Rego, DS11 evidence,
C04 dashboard source, or C05 Atlas register changed.

### Frozen-schema and generator receipts

At entry, two independent canonical schema exports and the tracked schema were
byte-identical at SHA-256
`bdff039ca63e0f5d6a4afb7e2581a3e8c3278e28873d3b42c6dcbc1905524fc1`.
The entry runtime contract checker returned exit `1` with exactly three
findings: the pre-existing epoch-batch missing 2xx example and the intentionally
stale raw `runtimeApiClient.ts` / `.js`; there was no OpenAPI drift or other
stale path. Real `94.06`, user `89.36`, sys `4.23`; uptime `09:35` -> `09:36`.

The registered shared-client writer and dashboard writer were each run into
two fresh full output roots. Each observed root contained exactly the declared
five shared outputs plus one dashboard type output; no seventh generated output
appeared. The five shared outputs were byte-identical A <-> B and A <-> tracked.
The first dashboard scratch comparison under `_build/.tmp` was rejected as a
tooling non-receipt: root `.gitignore` line 10 ignores `_build/`, so the
dashboard script's Prettier step silently skipped that outside-package target.
No generated byte or generator source was hand-edited to compensate.

The same canonical dashboard writer was then rerun into two validated,
nonignored, exact-prefix descendants of `apps/runtime-dashboard/`. Its own
Prettier step named and formatted each target. Each root contained exactly one
`apps/runtime-dashboard/src/api/types.ts`; A <-> B and A <-> tracked were exact,
all at SHA-256
`09f66e848b8ebd42ccf15c47b8a59f54aaeb1d840c4f8824a21e93238b8b65b1`.
Scratch A: exit `0`, real `3.51`, user `5.39`, sys `0.30`, uptime `09:42` ->
`09:43`; scratch B: exit `0`, real `3.46`, user `5.35`, sys `0.27`, uptime
`09:43` -> `09:43`. Both explicit dashboard-local roots and both earlier
client roots were prefix-validated and removed after comparison.

The single tracked canonical transaction returned exit `0` for both writers:
shared client real `3.46`, user `5.17`, sys `0.41`; dashboard types real `4.34`,
user `6.57`, sys `0.35`. The final six output hashes are:

| Generated output | SHA-256 |
| --- | --- |
| `packages/runtime-api-client/types.ts` | `564f69713a1c69cbb0108f66aed190744f23cbba661d51b7a203fcd72463eaba` |
| `packages/runtime-api-client/runtimeApiClient.ts` | `46727680e67745ed24250c17816dae165d018a1b69c05603a00e13a74bba5154` |
| `packages/runtime-api-client/runtimeApiClient.js` | `b4c2e6340beef61ae852988ff6eda479902cb467f06b7bcfe58d03399051083e` |
| `packages/runtime-api-client/canonicalRuntimeApiClient.ts` | `092ab9b9c68b9afeb6cfb9629bb4e298e680f43d298b12fefd768038e04a84fc` |
| `packages/runtime-api-client/canonicalRuntimeApiClient.js` | `06fff79f0a12ff4adc742b9a6646da915d10c26caf73847ea33f260d0e347833` |
| `apps/runtime-dashboard/src/api/types.ts` | `09f66e848b8ebd42ccf15c47b8a59f54aaeb1d840c4f8824a21e93238b8b65b1` |

A closing canonical schema pair proves immobility after every client writer and
verification lane. Scratch A: exit `0`, real `117.29`, user `107.36`, sys
`5.33`, uptime `10:05` -> `10:07`; scratch B: exit `0`, real `118.08`, user
`111.34`, sys `4.71`, uptime `10:07` -> `10:09`. A <-> B, A <-> tracked, B <->
tracked, and the tracked schema diff all return exit `0`; all three hashes remain
`bdff039ca63e0f5d6a4afb7e2581a3e8c3278e28873d3b42c6dcbc1905524fc1`.
Both closing roots and both entry roots were prefix-validated and removed after
the proof.

### ABI denominator and release metadata

The canonical generator's complete operation extraction moves from **81**
public methods at exact slice base `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`
(71 GET / 10 admitted POST) to **82** on the execution branch (72 GET / 10
POST). Both censuses exit `0`; each real `0.08`, user `0.06`, sys `0.01`.
`getConfidenceLedgerRiskSpendProjection` is the one new method. Its generated
return is exactly four named wire arms:
`AvailableConfidenceLedgerRiskSpendPacket`,
`SourceBlockedConfidenceLedgerRiskSpendPacket`,
`ArtifactMissingConfidenceLedgerRiskSpendPacket`, and
`InvalidConfidenceLedgerRiskSpendPacket`; the OpenAPI discriminator literals
are respectively `available`, `source_blocked`, `artifact_missing`, and
`invalid_source`. The method occurs once in each raw/canonical TS/JS client.

`release-fragments/unreleased/2026-08-27-ds17-confidence-ledger-risk-spend.toml`
declares the additive protected operation and separate shared-client/dashboard
compatibility rows. Its SHA-256 is
`968cbe4b2fad788eaebef56df43a8f25c49342cfab537449ab80b90594d868b3`.
The compatibility gate parses the branch as 35 fragments / 54 structured rows,
versus exact base 34 / 51. It introduces no finding for the DS17 fragment. Both
runs retain the same foreign `lex-intervention-ownership` public-surface-review
contract error: branch exit `1`, real `2.16`, user `1.81`, sys `0.11`, uptime
`09:58` -> `09:58`; base exit `1`, real `1.97`, user `1.81`, sys `0.07`, uptime
`09:58` -> `09:58`. Because C03 adds a fragment to the gate's denominator, the
whole red gate is not labeled inherited; the exact subject is merely recorded
as exact-base-reproduced and outside this fragment.

### Focused branch / exact-base verification

- Legacy raw-client contract proxy: branch and base each return exit `1` with
  exactly the epoch-batch missing-success-example finding. Branch real `91.54`,
  user `87.09`, sys `3.28`, uptime `09:48` -> `09:50`; base real `66.30`, user
  `46.78`, sys `2.39`, uptime `09:54` -> `09:55`. The branch's two entry
  stale-client findings are closed. This checker is explicitly only a two-file
  proxy; six-output freshness is established by the canonical A/B proofs and
  architecture family checks above.
- Prescribed generated bridge plus schema-hardening lane: branch and base each
  collect 29 and return **28 passed / 1 failed**, exit `1`, with the identical
  epoch-batch example failure. Branch real `139.52`, user `141.72`, sys `7.14`,
  uptime `09:50` -> `09:52`; base real `93.88`, user `96.35`, sys `5.29`, uptime
  `09:53` -> `09:54`. The finding's complete schema input is unchanged in C03,
  and exact base reproduces it, so the epoch residual is inherited under P41.
- Shared runtime client typecheck / build: branch exits `0/0` at real
  `1.62/1.50`, user `2.48/2.73`, sys `0.09/0.11`; exact base exits `0/0` at
  real `1.61/1.48`, user `2.44/2.69`, sys `0.08/0.10`. All uptime pairs remain
  within `09:56`.
- Dashboard typecheck / production build: branch exits `0/0` at real
  `22.20/33.50`, user `40.37/57.56`, sys `1.25/3.45`, uptime `09:56` -> `09:57`;
  exact base exits `0/0` at real `22.29/33.69`, user `40.64/57.55`, sys
  `1.24/3.56`, uptime `09:57` -> `09:58`.
- Architecture guardrails identify both generated families as fresh on branch:
  five shared plus one dashboard output. The branch then exits `1` solely for
  the already-recorded C05-owned
  `apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json` drift; real
  `118.93`, user `100.77`, sys `15.91`, uptime `09:59` -> `10:01`. Exact base
  reports all three generated families fresh and exits `0`; real `144.54`, user
  `122.74`, sys `19.21`, uptime `10:01` -> `10:03`. This is not exact-base debt:
  the progress ledger already locates it before C03 and assigns the required
  Atlas companion to C05. C03 does not alter that foreign/next-cluster path.

Pattern closeout: C03 avoids P38 by supplementing the two-file checker with the
complete six-output set; honors P39 by keeping all seven generated/release
companions and this record outside a zero mechanism cap; and applies P41 at the
finding's real input denominator. The generated-client sub-capability is
implemented. The full DS17 slice remains `consumer_missing` until C04 wires the
dashboard reviewer experience; C03 does not claim that future surface.

## C04 — conditional reviewer panel and exact MACHINE twin

C04 starts from attached branch
`codex/ds17-confidence-ledger-risk-spend-execution` at entry HEAD
`2ac603ff0d1c8f6a6158e67ec217351eba063fab`. The exact slice-base comparison
remains detached clean `main` at
`dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`; no comparison checkout, merge,
rebase, reset, stash, or publication operation touched the execution branch.

### Skill and pattern discipline

Before React work, the complete `build-web-apps:react-best-practices`,
`codex-engineering-guardrails:code-work`,
`superpowers:test-driven-development`, and
`superpowers:verification-before-completion` instructions were read and used.
The React guidance kept authorization above both query mounts, moved the two
query/render paths into sibling components, avoided effect-driven fetching,
and retained one generated query cache identity. The code-work guidance held
the production fence at exactly nine paths and reused the generated client,
governed query policy, Atlas dialog/error boundary, and shared byte exporter.
TDD made semantic mutations fail before each property repair; verification
discipline required the complete focused wave after formatting and after the
last byte-admission change. `good-tests`, `engineering-decisions`, and
`systematic-debugging` guidance additionally kept falsifiers behavioral,
recorded the no-reserve decisions, and classified the combined-lane a11y
timeout by isolated reproduction rather than changing product behavior.

The closeout pattern pass applies P03/P05/P10/P15 by rendering admitted owner
semantics without promotion/public-authority inference; P29/P32/P37/P38 by
recomputing the packet, decoding visible DOM text, and falsifying marker-
constant changes; P39 by separating ten mandatory test companions and this
journal from the nine mechanisms; P40 by widening the one visible-leaf gap to
the complete ordered leaf/list quantity and the MACHINE gap to byte parsing;
and P41 by replaying common gates at the exact slice base.

### Exact mechanism and companion set

The nine mechanism paths are exactly:

1. `apps/runtime-dashboard/src/features/runs/api/useConfidenceLedgerRiskSpend.ts`
2. `apps/runtime-dashboard/src/features/runs/domain/confidenceLedgerRiskSpend.ts`
3. `apps/runtime-dashboard/src/features/runs/components/ConditionalDeltaFigure.tsx`
4. `apps/runtime-dashboard/src/features/runs/components/ConfidenceLedgerRiskSpend.tsx`
5. `apps/runtime-dashboard/src/features/runs/export/confidenceLedgerRiskSpendTwin.ts`
6. `apps/runtime-dashboard/src/features/runs/routes/CycleBoardPage.tsx`
7. `apps/runtime-dashboard/src/api/queryKeys.ts`
8. `apps/runtime-dashboard/src/shared/i18n/locales/en.json`
9. `apps/runtime-dashboard/src/shared/i18n/locales/uk.json`

The ten P39 test companions are the six new hook/domain/figure/panel/a11y/twin
tests, the three existing Cycle Board page/parity/census tests, and the existing
i18n parity test. The twin test uses `.tsx`, rather than the brief's illustrative
`.ts`, because it renders JSX through the real panel; this is a test companion,
not a tenth mechanism. The tracked journal is the mandatory append-only record.
`ru.json`, DS6/DS11 visual specs, snapshot roots, route/navigation registries,
generated files, and every other production path remain outside the diff.
Reserve spend is **0**.

### Transport and strict admission

The hook calls only generated
`RuntimeApiClient.getConfidenceLedgerRiskSpendProjection`, injects
`authAwareRuntimeFetch`, captures `response.clone().arrayBuffer()` before the
generated decoder consumes the response, strictly admits the decoded result,
and uses the existing `never_cache_authority` policy with a distinct query key.
There is no direct `fetch`, duplicate DTO, second route/UI host, or new download
helper. The available download passes the captured `Uint8Array` object directly
to `exportCapturedResponseBytes`.

Generated types were sufficient for transport but not authority admission. The
domain layer uses a strict four-arm schema and independently recomputes the
available packet's canonical identities, full registry-derived 13-definition
and six-route denominators, 15-class allocation, exact rational spent/
remaining/overspend algebra, producer reference partitions/order, positive
register, source/receipt/replay bindings, and packet/payload/projection hashes.
The other three arms retain distinct freshness and replay rules. Offline packet
parsing is candidate/coherence-only: the hook bytes originate at the already-
protected owner route and C04 adds no new authority ingress.

Negative coverage, unappointed authority, definition/route/instance blockers,
or over-spend each veto aggregate promotion. The positive register remains
visible and honest when its population is zero, its appointment denominator is
recomputed empty, and its sufficiency is not established.

### Human projection and independent failures

The available DOM order is exact:

1. actual refusal rows, then producer-ordered acquisition rows;
2. exact scope-local total, then all 15 obligation-class rows;
3. all 13 definitions, then all six certificate routes;
4. the always-present positive register;
5. good-event, source, validator, receipt, provenance, and replay identities;
6. exact-byte MACHINE download.

All 67 rendered allocation/spent/remaining/overspend values traverse
`ConditionalDeltaFigure`. Each figure has one focusable chip containing both
exact packet disclosures and one accessible controlled dialog containing the
complete resolved envelope. No parent/family/sequence/cross-scope total or
satisfied narrowed claim is emitted. `source_blocked` renders only its typed
blocker plus source/validator/receipt/replay identities; rejected risk and
certificate detail remain absent.

`CycleBoardPage` authorizes before either query mounts, then renders two sibling
query components. Each has a local loading/error card inside its own existing
`PanelErrorBoundary`, so a query failure or render exception cannot blank the
other panel. The final page tests prove unsettled and unauthorized users mount
neither query, while reviewer authorization mounts exactly one of each.

### Exact twin and falsifiers

The production twin parses and strictly admits both the candidate and captured
bytes, requires them to agree, independently decodes every visible governed
leaf value plus every ordered-list identity/count and the six section order,
rejects hidden/`aria-hidden`/CSS-hidden semantics and raw/test-only payload
markers, then compares packet-derived and DOM-derived protected-query answers
equal-or-more-conservative under PV-K04. PV-K06 evaluates exactly these nine
declared queries: promotion authority, publication authority, public audience,
bounded completeness, world completeness, family total, sequence total,
cross-scope total, and narrowed-claim satisfaction.

The only exact result returns the original captured byte object. All other
results select one of the closed seven reasons:
`timeout`, `missing_input_or_incomplete_history`,
`parser_or_schema_failure`, `unsupported_or_out_of_model`,
`empty_consistency_set`, `model_observation_inconsistent`, or
`unproved_approximation`.

Behavioral red receipts include:

- a coherently rehashed derived definition initially survived generated-shape
  admission; full basis re-derivation made the mutation fail while the ordinary
  domain family finishes 15/15 green;
- definition/route/instance blockers were initially omitted from aggregate
  promotion; the row-level negative probe forced the complete veto set;
- eight forged visible leaves (scope, actual/class/definition/route blocker,
  positive authority, coverage posture, and good-event rule) left markers
  fixed and produced exactly 8 failures / 17 passes; after widening to the
  complete ordered semantic leaf/list set, all pass only when unmodified;
- malformed captured bytes paired with an admitted object initially returned
  `exact`: the exact twin red was 1 failed / 28 passed, duration `59.67s`.
  Parsing and admitting the bytes now returns `parser_or_schema_failure`;
- explicit class/definition reorder, honest-zero-register omission, protected
  denial removal, hidden/aria/CSS-hidden leaves, raw JSON/test IDs, finite-
  schema expansion, empty model, missing history, timeout, and sampled-safe
  approximation each fail for their declared closed reason;
- captured-byte download identity, Bayesian/non-anytime refused rows, four-arm
  distinctions, valid zero versus missing source, sibling isolation, and
  unauthorized non-mounting run through real production consumers.

No raw hidden payload, `data-testid`, server-safe marker, caller boolean, or
filename proves parity.

### Locale and consumer censuses

Active en/uk leaves move from the C04 entry count `2652` to `2688`, exactly 36
new leaves per locale. There are no new ICU variables, so interpolation,
non-count, and variable-use hashes/counts do not move. The two authority riders
come from exact packet strings and are not translated paraphrases. `ru.json`
is byte-identical at C04 entry, current worktree, and exact slice base, all
SHA-256
`5366a250bd34ec702035c0953348d25e824acf80e75136bb212895cd76c36273`.

The complete TypeScript consumer census is green at 4/4 and proves exactly one
generated operation intake, one resolved hook call, one Cycle Board page host,
one panel renderer, and one existing filename-bound exact-byte exporter. It
finds zero direct fetches, duplicate clients, second hosts, or second download
helpers.

### Focused branch / exact-base verification

| Gate | Branch | Exact slice base | Disposition |
| --- | --- | --- | --- |
| final prescribed nine-file C04 Vitest | exit 0; 9 files, 80/80; real 77.71, user 155.17, sys 8.44; uptime 12:16 -> 12:17 | C04-only files do not exist | green; no full suite |
| common Cycle Board page/parity/census lane | exit 0; 3 files, 23/23; real 17.80, user 52.95, sys 2.78; uptime 12:08 -> 12:08 | exit 0; 3 files, 14/14; real 35.12, user 59.17, sys 3.83; uptime 12:08 -> 12:09 | exact same selected paths; nine added behavioral cases |
| dashboard full typecheck | exit 0; real 22.95, user 42.21, sys 1.32; uptime 12:10 -> 12:10 | exit 0; real 24.78, user 44.72, sys 1.41; uptime 12:10 -> 12:10 | green |
| dashboard production build | exit 0; final real 31.11, user 56.67, sys 2.99; uptime 12:18 -> 12:19 | exit 0; real 32.36, user 57.71, sys 3.80; uptime 12:11 -> 12:11 | green; only normal chunk-size warning |
| focused ESLint over 17 TS/TSX mechanism/companion files | exit 0; real 57.57, user 77.95, sys 5.81; uptime 12:17 -> 12:18 | not applicable to absent C04 files | green |
| focused Prettier check over all 19 dashboard mechanism/companion files | exit 0; all matched | not applicable | green |
| active-locale parity | exit 1; 37/38; real 2.15, user 2.69, sys 0.32; uptime 12:09 -> 12:09 | exit 1; 36/38; real 2.35, user 2.73, sys 0.35; uptime 12:09 -> 12:09 | branch active count is green; exact RU expected `67b7…`, actual `afcb…` reproduces on both |

The i18n suite as a whole is not labeled inherited because C04 changes its
active-locale denominator. The only branch red is the exact-base-reproduced RU
key-set subject; neither the frozen RU bytes nor its expected hash constant is
changed by C04. The exact base also carries a second active-count red that the
branch's current prior-cluster baseline plus C04 count update closes.

The combined lane initially recorded 77/78 because the axe test took `21.3s`
under parallel load and exceeded Vitest's inherited `15s` test timeout; the
same test passed isolated in `12.59s` with zero violations. Per the measured-
time rule, only that test's ceiling moved to `30s`; the final combined lane is
80/80. No assertion, product behavior, or accessibility finding was changed.

### Capability state

C04 changes the full DS17 state from `consumer_missing` to
`verification_missing`: the protected typed producer/artifact/bridge now has
human and exact MACHINE consumers plus negative semantic/a11y/census/parity
tests, while C05 still owns the surgical Atlas registration and DS17 visual
evidence. Positive certificate issuance and deployment-wide enumeration remain
explicitly unallocated/open-world; the honest zero register does not claim
those capabilities. C04 has no bounded implementation residual and uses no
reserve path.
