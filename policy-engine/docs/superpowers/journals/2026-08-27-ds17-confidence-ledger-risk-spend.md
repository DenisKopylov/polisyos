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

### C04 post-review structural correction

The correction groups all reviewer examples into three P40 invariants. First,
strict admission derives both negative coverage arms and the complete
search/exclusion/remainder/review/expiry/challenge/source/authority tuple from
the owner basis, and available packets must recompute within delta; a coherent
open-world forgery and coherent `1/50 > 1/100` available packet are both
rejected. Second, the production hook invokes one shared protected-query
preflight over separately capped/admitted generated-candidate and captured-byte
observations; only an exact receipt can render or download, while finite budget
and the seven F21 reasons are real behavior. Third, the twin classifies every
visible root and bound-dialog text node against packet/canonical locale copy,
checks the complete recursively flattened envelope, rejects missing/forged
portals and standard hidden/offscreen variants, and binds the governed honest
zero state. These respectively close P32/P37/P38 owner admission, P01/P02/P29
orchestration, and the complete PV-K04/PV-K06 visible projection rather than
patching the named phrases.

The correction changes seven existing C04 mechanisms (hook, domain,
conditional figure, panel, twin, en and uk) and seven P39 companions. The other
two original mechanism paths remain unchanged; `ru.json`, generated outputs,
the shared exporter, route/navigation registries, second-host/direct-fetch
seams, and DS6/DS11 visual roots remain untouched. Reserve is zero.

Final evidence is 9 focused files / 97 passed: hook 4, domain 30, figure 3,
panel 7, a11y 1, twin 29, Cycle Board page 6, parity 13, census 4. The
correction-entry replay is 80/80. Full dashboard typecheck and production build
are green branch/base; exact focused lint is green branch/base and the final
delta lint is green; correction formatting is 14/14. Active locale leaves move
2688 -> 2692, non-count messages 245 -> 246, and variable uses 361 -> 362.
Branch and correction entry both produce 37/38 i18n with only the identical
legacy expected `67b7…` / actual `afcb…` RU key-set red; frozen `ru.json` is
`5366a250…`. The optional whole-dashboard lint attempt did not complete and is
not claimed. No full suite ran. Planned append-only subject:
`fix(atlas): enforce confidence risk-spend evaluation`; no correction residual
remains and C05 retains Atlas/visual ownership.

### C04 review round 2 — complete generated, arithmetic, and rendered quantities

This round is the SECOND finding in the already-declared P32/P37/P38 owner
admission, F21 bounded-evaluation, and P38 visible-projection classes. Per P40,
the implementation widens each mechanism to the complete quantity instead of
adding checks for the reviewer's named strings, denominator, or CSS examples.
`receiving-code-review` kept that class disposition explicit;
`test-driven-development` put the coherent rehash, aggregate arithmetic,
accessibility relation, concealment, and native-browser falsifiers red first;
`systematic-debugging` separated a browser-harness setup import failure and a
parallel-load test timeout from product behavior; React guidance kept the
controlled Radix trigger/dialog relation stable; and
`verification-before-completion` required the final consolidated, Chromium,
type/build/lint/format, locale, and exact-entry replays below.

#### Complete owner-literal admission

The domain exports one compact `CONFIDENCE_LEDGER_OWNER_LITERAL_RULES` table.
A generic P39 census starts from all four specialized OpenAPI packet roots,
resolves `$ref`, `allOf`, `oneOf`, and `anyOf`, walks properties, array items,
and mapping values recursively, and compares every reachable `const` or
single-value enum path/value against that table. The two complete sets are
exactly 99/99. Production admission selects the packet arm and applies every
matching rule recursively, including wildcard array/mapping members, after
strict shape parse and before the packet can escape. The table covers the
common transport/replay literals, all arm discriminators/absence reasons, and
every nested available owner literal, including all conditional-amount riders
and display versions.

Coherently rehashing the semantic-ledger schema version, conditionality clause,
or good-event clause no longer helps: candidate and captured bytes both block
with `parser_or_schema_failure`. The prior derived coverage classifier,
available-within-budget requirement, typed `source_blocked/over_spend` arm, and
non-leaking blocked surface remain intact. This is generated-contract
completeness for admission, not a browser-side provenance claim; owner
authority still belongs to the protected route.

#### Complete arithmetic work admission

Every direct admission now performs a no-decimal recursive scan first. It
requires finite safe nonnegative numerators, finite safe positive denominators,
and caps numerator, denominator, rational cardinality, conservative period
sum, exact-decimal code units, and display code units. The aggregate caps apply
over the entire packet, so 98 individually acceptable denominators cannot
bypass the bound. The shared protected evaluator cheaply scans the generated
candidate and captured JSON observation separately, charges both complete JSON
and rational workloads plus bytes/schema/nine-query work against one finite
positive safe-integer budget, and only then runs either strict admission. No
`exactDecimal` loop occurs before both evaluator scans.

The full-rehash 151,866-byte denominator `1,000,171` probe blocks as
`unsupported_or_out_of_model` and direct admission rejects it; 98 denominators
of 3,000 reject on aggregate rational work; and a 960,000-step budget that fits
either one-denominator-100,000 observation alone blocks when both observations
are debited. Normal protected-route bytes remain exact. The live finite budget
is 1,100,000 steps; the twin reserves 140,000 for the complete document/DOM
proof and sends 960,000 to the shared dual-observation preflight.

#### Browser-backed complete visible/accessibility projection

The twin accepts either native rendered proof or one factory-created,
WeakSet-registered JSDOM-only test oracle. A caller-created lookalike is not
trusted. Production without `checkVisibility`, bounding rectangles, viewport,
`elementsFromPoint`, scroll APIs, or a provably restorable session returns
`unproved_approximation`. Native proof calls `checkVisibility` with opacity,
visibility, and content-visibility checks, applies a fail-closed CSS grammar,
scrolls each element into a measurable viewport position, requires nonzero
geometry and a painted hit-test, and consumes the DOM work budget. A complete
ancestor chain is cached only after every member was synchronously proven.

The session snapshots focus, window scroll, and every element scroll position
before probing and restores and verifies all of them in `finally`; any failed
restoration returns `unproved_approximation`. Hidden/aria-hidden, display,
visibility, opacity/transparent/font-zero, clipping, zero/collapsed-axis
overflow, scale/matrix zero, opacity filter, zero clip-path, large positive or
negative offsets, and text-indent concealment reject on the governed node or
any ancestor. Unsupported mask/filter/clip/clip-path/transform effects never
produce exact merely by syntax: they require the independent native
geometry/paint proof where allowed, otherwise block.

All 67 figures have one unique controlled trigger. The twin independently
checks each exact packet-derived accessible name, exact ARIA attribute grammar,
amount hash, scope, envelope, declared-class hash, and semantic role. Exactly
one actual trigger must be expanded; its unique `aria-controls` target must be
the unique document portal, and dialog id, trigger id, amount tuple, role,
`aria-labelledby`, `aria-describedby`, canonical title, and canonical
description must all agree. Sibling-valid label swaps, alternate name
relations, dialog/title/description `aria-label` overrides, and portal tuple
forgeries therefore block even when all visible marker values remain.

The honest packet-derived register copy is now exactly:
`Positive promotion certificates`,
`0 issued · institutional authority unappointed in this PolicyOS runtime`, and
`No promotion certificate is currently issuable. This is a governed empty
state, not a load failure.` The Ukrainian catalog carries its canonical
equivalents. The panel renders title, status, and body separately, and the twin
binds all three as governed visible/accessibility leaves.

The bounded rendering residual is deliberately fail-closed: browser effects
outside the supported CSS grammar, an unavailable hit-test/layout API, or any
visibility probe whose scroll/focus restoration cannot be proved yield
`unproved_approximation`, never `exact`. A stronger side-effect-free browser
paint/occlusion primitive is the smallest future capability that could widen
that exact subset; it is not available here. Real Chromium proves the baseline
surface is inside the supported subset.

#### Round-2 paths and falsifiers

Six existing C04 mechanisms change: domain, conditional figure, panel, twin,
and en/uk catalogs. Six P39 companions change: domain, figure, panel, twin,
Cycle Board parity, and i18n parity tests. The hook already contained the live
shared preflight and remains byte-unchanged; page host and query-key mechanisms
also remain unchanged. This tracked journal is the mandatory record. There is
no new mechanism, test file, generated output, `ru.json`, shared exporter,
route/navigation entry, direct fetch, second host, visual/snapshot root, or
reserve path. Reserve remains zero.

Behavioral reds included the 99-literal table disagreement and coherent owner
literal substitutions; the oversized, aggregate-98, and dual-observation
arithmetic probes; forged accessible relation/name and sibling-swap variants;
collapsed-width/height, scale/filter/clip-path/offscreen ancestor variants;
exact-copy drift; and the first real-Chromium visibility run, which returned
`unproved_approximation` when repeated ancestor work exhausted the finite DOM
budget. Complete-chain caching closed that last property without raising the
DOM budget. A generic browser attempt that imported the JSDOM/MSW Node setup
never collected a test and is a harness non-receipt; the self-contained native
configuration is the falsifier reported below. Temporary browser configuration
was deleted after use.

#### Round-2 verification

| Gate | Round-2 branch | Entry `676690f7` | Disposition |
| --- | --- | --- | --- |
| complete nine-file focused Vitest | exit 0; 9 files, 120 passed + 1 native-only skip; duration 52.32s, real 53.64 | exit 0; 9 files, 97/97; duration 103.99s, real 107.34 under concurrent lint | green; +23 structural tests |
| page / parity / census | exit 0; 3 files, 23/23; real 28.88 | exit 0; 3 files, 23/23; real 21.46 after CPU release | green; an earlier exact-base parallel run had 22 pass + one 15.294s timeout and is not the final receipt |
| feature axe test | exit 0; 1/1; real 24.15 | included green in 97/97 | green; the global a11y config excludes feature paths and its no-test result is a harness non-receipt |
| real Chromium visibility/restoration | exit 0; 1 passed + 45 unselected/skipped; duration 2.45s, real 3.24 | not applicable to the pre-oracle entry | exact baseline and restoration green |
| full dashboard typecheck | exit 0; real 27.58, user 48.54, sys 1.85 | exit 0; real 22.37, user 40.48, sys 1.49 | green |
| production build | exit 0; real 43.67, user 72.74, sys 5.69 | exit 0; real 47.98, user 76.55, sys 6.42 | green; normal chunk warning only |
| exact ten-file TS/TSX ESLint | exit 0; real 54.46, user 65.06, sys 9.34 | exit 0; real 32.18, user 46.69, sys 3.89 | green |
| whole-dashboard ESLint | exit 1; 130 errors / 0 warnings; real 1051.85 | exit 1; identical 130 / 0; real 1228.31 | same branch/entry red; no finding path is C04, but the whole gate is not labeled inherited because C04 files are in its input denominator |
| exact twelve-file Prettier | 12/12 matched; real 2.45 | not applicable | green |
| i18n parity | exit 1; 37/38; real 2.87 | exit 1; 37/38; real 2.04 | identical sole legacy RU expected `67b7…` / actual `afcb…` hash red |

Focused totals are hook 4, domain 37, figure 3, panel 7, a11y 1, twin
45 passed + 1 native-only skip, Cycle Board page 6, parity 13, and census 4.
Active en/uk leaves move `2692 -> 2693`, non-count messages `246 -> 245`,
variable uses `362 -> 361`, and the corresponding key-set hash becomes
`791057b29c0cd78eebd831c2f86285316d1a204ebb893f9598df693dff84417d`.
Current en/uk hashes are `2ae387596c20…` and `9c6970522875…`.
`ru.json` remains byte-identical to entry at
`5366a250bd34ec702035c0953348d25e824acf80e75136bb212895cd76c36273`.
No full suite ran. Planned append-only subject:
`fix(atlas): complete confidence risk-spend proof`.

### C04 review round 3 — closed paint, test-authority, and byte-ownership quantities

This round keeps the reviewer buckets explicit. The paint escape is a SECOND
finding in the existing P38 rendered-visibility class, so the implementation
now admits a finite positive paint grammar and fails closed on every checked
non-admitted state instead of adding a transparent-text-fill denylist. The
production-oracle escape is a SECOND P32/P37 finding: the production-callable
twin has no oracle parameter, oracle type, factory, or registered test
capability; the JSDOM platform substitute lives only in a P39 test helper and
does not appear in the production bundle. Mutable transport bytes are a NEW
P05/P37 TOCTOU class and close at one intake: the shared protected-query
preflight synchronously owns the bytes at invocation and exposes only a frozen
fresh-copy closure to the panel and twin.

`receiving-code-review` fixed those class dispositions before editing;
`test-driven-development` required the paint/UA and immediate/microtask/copy
mutation failures before the mechanisms changed; `systematic-debugging` kept
the native-browser harness separate from product behavior; React guidance kept
the existing hook/panel ownership and avoided a second render/download host;
and `verification-before-completion` required the serial native, focused,
type/build, locale, lint, DS10 identity, and exact-main replays below.

#### Structural closures and falsifiers

- `RenderedVisibilitySession` is the only production visibility path. It
  requires native `checkVisibility`, geometry, viewport and hit-test evidence,
  consumes the DOM budget, and snapshots/restores focus, window scroll, and all
  element scroll positions in `finally`. Its finite paint grammar admits only
  explicit default/opaque states plus geometrically proved translations and
  non-inset shadows; unsupported concealment, text, mask, filter, transform,
  compositing, pseudo-content, or inline paint states yield
  `unproved_approximation`.
- The persistent Chromium suite proves the canonical baseline exact and proves
  transparent text fill, text shadow, inset paint, and non-normal compositing
  on both governed leaves and ancestors cannot be exact. Spoofing
  `navigator.userAgent` and passing an arbitrary legacy-shaped object also
  cannot mint a visibility capability.
- `evaluateConfidenceLedgerProtectedQuery` clones the incoming `Uint8Array`
  before its first `await`; all byte limits, decoding, independent admission,
  reconciliation, download, and byte-twin observations use that owned
  snapshot. The frozen capture yields a new `Uint8Array` for each consumer.
  Immediate caller mutation, queued-microtask mutation, mutation of a returned
  copy, and mutation of a prior download copy leave every later byte identical
  to the invocation snapshot.
- The DS17 query key is a sibling export after the governed shared `queryKeys`
  declaration. This retains a distinct never-cache authority key while
  restoring the complete DS10 declaration identity; no peer register or stamp
  moved.

The bounded paint residual remains fail-closed: exact is unavailable when the
browser cannot prove a checked rendering state, the native APIs are absent, or
focus/scroll restoration is not exact. A side-effect-free glyph-level paint and
occlusion primitive, coupled to stylesheet/font integrity, is the smallest
future capability that could safely widen that exact subset; it is not present
here. This residual cannot authorize a positive receipt.

#### Round-3 paths and verification

Five existing mechanisms change: query keys, hook, domain, panel, and twin.
Ten P39 companions change or are added: hook, domain, panel, panel-a11y, twin,
Cycle Board page, and Cycle Board parity tests; the persistent Chromium test,
its Vitest configuration, and the JSDOM-only platform helper. This journal is
the mandatory tracked record. The complete C04 capability still occupies the
original nine mechanism paths; no tenth mechanism, locale, generated client,
route/navigation entry, shared exporter, second host, direct fetch, visual
root, snapshot root, or reserve path is added. `ru.json` remains frozen and
reserve remains zero.

The red receipts were domain 2 failed / 36 passed before byte ownership,
hook/panel/twin 5 failed / 52 passed / one skip before fresh-copy propagation
and oracle removal, and native Chromium one baseline pass / nine intended
failures while the paint and UA-spoof probes still returned `exact`. The DS10
owner validator also failed while the DS17 key remained inside its governed
declaration. All now close for their declared reason.

| Gate | C04 branch | Exact main `dc7bdf79` | Disposition |
| --- | --- | --- | --- |
| complete nine-file focused Vitest | exit 0; 9 files, 123 passed + 1 native-only skip; duration 101.04s, real 101.93 | six C04 test files absent; common Cycle Board denominator below | green; no full suite |
| persistent native Chromium | exit 0; 10/10; duration 3.79s, real 4.60 | C04 twin/browser suite absent | exact baseline plus 9 negative paint/UA probes |
| Cycle Board page/parity/census | exit 0; 23/23; real 27.07 after production staging | exit 0; 14/14; real 34.26 | authorization, sibling isolation, parity, and census green |
| DS10 query-key identity | exit 0; 1/1; real 4.50 | exit 0; 1/1; real 4.65 | governed declaration identity preserved |
| full dashboard typecheck | exit 0; real 34.90 | exit 0; real 25.27 | green |
| production build | exit 0; real 45.54 | exit 0; real 46.32 | green; normal chunk warning only; production oracle strings absent |
| exact 15-file ESLint | exit 0; real 36.71 | C04-only files absent | green ownership gate |
| whole-dashboard ESLint | exit 1; 130 errors / 0 warnings; real 46.97 with warm cache | exit 1; identical 130 / 0; real 988.64 uncached | no C04 finding path; whole gate remains red |
| exact 15-file Prettier | 15/15 matched; real 1.65 | C04-only files absent | green |
| i18n parity | exit 1; 37/38; real 2.35 | exit 1; 36/38; real 2.60 | branch closes main active-count red; both retain only the same RU subject after that delta |

The complete branch catalog has 2,693 English and 2,693 Ukrainian leaves,
versus 2,662/2,662 at exact main. Their branch file hashes are
`2ae387596c20dc593d6af884a6ca7a7d0141bb2ceae065233142cec1bcb5fba6` and
`9c6970522875338aa69ceff172b0e5c4f82de94b984b62db3ab4acdb07fc3615`.
Round 3 changes neither active catalog. `ru.json` is byte-identical branch/main
at `5366a250bd34ec702035c0953348d25e824acf80e75136bb212895cd76c36273`;
both compute the legacy RU key-set hash `afcb2704…` against the frozen expected
`67b7a921…`. The whole lint gate is not called inherited because C04 paths are
inside its denominator even though the exact 130-finding sets match. Planned
append-only subject: `fix(atlas): harden confidence risk-spend ownership`.

### C05 preflight — execution stop at the owner-admission boundary

C05 did not begin. Read-only preflight established that its required real
Bayesian-without-coverage semantic/visual witness cannot reach the sole DS17
HTTP surface through the owner-admitted source chain declared by the plan.
This is the plan's explicit stop condition for a falsifier that cannot fail for
its declared reason; it is not permission to synthesize a packet or add a
second source seam.

The guarded service has exactly four result arms. `artifact_missing` covers an
absent N11 artifact. `invalid_source` covers incomplete resolution, failed
owner admission, non-over-spend validation failures, or a non-exact semantic
projection. `source_blocked/over_spend` requires the exact five owner
diagnostics, source-payload equality, and the independent strict sum test.
`available` requires the N11 owner validator to pass before the semantic
projection is admitted. `coverage_argument_missing` is therefore observable
only as a row inside an owner-admitted `available` packet; neither the service
nor route has persisted-session intake or an overlay path.

Two independent derivations agree that the planned scratch state cannot enter
that arm:

1. Structurally, `_expected_frozen_n9_rows` projects every check whose role is
   `promotion` and polarity is `false_accept`, including a preflight refusal.
   Omitting the resulting row from `n9_promotion_projection` emits
   `n9_projection_owner_binding_drift`; including it makes the validator's
   unconditional nonempty-row predicate emit
   `day_one_positive_promotion_fabricated`. Either issue prevents
   owner-admitted `available` output.
2. Behaviorally, a real exact-N11-scope
   `ConfidenceLedgerSession._for_verification` invocation of
   `bayesian_credible_interval` produced and persisted the canonical
   `coverage_argument_missing` refusal at
   `sha256:94d60c54cac8155fa3da2765a65a6c73157876211d92771cd4e85478e864fbf3`.
   The receipt and semantic projection each contained one check with role
   `promotion`; the N9 projection contained one row, so the live N11
   `day_one_positive_promotion_fabricated` predicate was true. Timing was
   uptime `17:02 -> 17:03`, user `58.80` + sys `2.69` seconds.

Changing the role is not a substitute: the registry permits
`bayesian_credible_interval` only for `promotion`, so another role yields
`certificate_role_not_permitted`. A hand-authored packet, `page.route`, a
second source artifact, a second route or UI host, or a C02 test injection is
forbidden. C05's sole mechanism path is the Atlas writer and cannot close this
producer/bridge boundary.

The missing capability is an N11-owner-issued negative/refusal-attempt
projection plus guarded HTTP bridge that carries a content-bound persisted
refusal for the exact DS17 scope while retaining an honestly empty positive
N9 register. The current capability label is `bridge_missing`; the named owner
is the GY-N11 confidence-ledger contract/validator owner. That work or a plan
amendment is required before C05 can execute.

No C05 path, register byte, generated report, semantic spec, visual spec,
snapshot, mechanism reserve, or commit was created. C06 was not started
because source cannot freeze at a plan-complete C05 boundary. C01/C02/C04
remain at 2/6/9 mechanism paths respectively: 17 implemented mechanism paths,
zero reserve paths spent, below the unchanged 18 declared / 22 hard ceiling;
the unimplemented eighteenth path is C05's Atlas writer.

### C04 round 4 — positive paint and text-frontmost proof

This append resumes C04 only after the independently committed C05 stop. The
first 1,669 lines above remained byte-identical to `cbfd83016` at
`c6eda68c4b23dea089ef48243e7ea4216b920e30667c1f82256cebf29eb1418a`
before this section was added. No C05 mechanism, finding, or conclusion moved.

The review witnesses are a second finding in the already-declared P38 paint
class, so P40 forbids another spelling or overlay-instance patch. The closure
widens the mechanism to two positive quantities. First, computed foreground
and text-fill colors enter exact only through a deliberately narrow,
fully-consumed normalized-color parser. It admits legacy RGB,
`color(srgb ...)`, `color(display-p3 ...)`, Lab/LCH, and OKLab/OKLCH only when
every channel parses as a finite browser-normalized number and the optional
alpha parses to exactly `1` or `100%`; a missing alpha is the normalized opaque
form. Unknown syntax, malformed/partial values, unsupported color spaces, and
every parsed alpha below one yield `unproved_approximation`. There is no list of
transparent spellings.

Second, element-center hit testing no longer carries text visibility. Every
nonempty text node under the complete governed root and its uniquely bound
dialog supplies a native `Range`; every finite nonzero Range rectangle is
bounded at 64 and sampled at its glyph midpoint. The evaluator scrolls an
off-viewport midpoint into view under the existing side-effect-restoration
contract. Exact requires the frontmost `elementsFromPoint` result to contain
that actual text node. An empty descendant or sibling therefore cannot satisfy
the proof. Because pointer-transparent elements disappear from the hit stack,
the session separately walks the already-capped complete document element set,
freezes every computed non-`auto` pointer-event candidate, and conservatively
rejects any independently visible candidate rectangle overlapping the sampled
glyph unless it contains the text node. Missing APIs, changed Range
cardinality, nonfinite geometry, unsupported visibility, work exhaustion, or
failed focus/scroll restoration remain `unproved_approximation`.

The total live evaluator budget remains the finite 1,100,000-unit cap. The DOM
share increases from 140,000 to 160,000 to debit the complete element scan,
Range geometry, hit tests, pointer-transparent overlap work, and restoration;
the independent captured-byte/candidate preflight still receives 940,000 and
the real protected response remains exact. The JSDOM Range and frontmost-hit
substitute exists only in the already test-only P39 helper. Production still
exports no oracle or capability-minting parameter, and a production-build scan
finds none of the test-helper/oracle identifiers.

`receiving-code-review` and the P40 pass fixed this as one deeper P38 class
before editing. `brainstorming` held implementation behind an approved bounded
design. `test-driven-development` required the complete generated color and
overlay matrix to fail before the mechanism changed. `systematic-debugging`
isolated the later route-only failure to honest DOM-work exhaustion rather than
weakening the native proof. `code-work` and React best practices kept ownership
inside the existing evaluator and retained the single hook/panel/download host.
`verification-before-completion` required the final native, focused,
branch/main common, type/build, lint, format, identity, and locale receipts
below.

#### Round-4 falsifiers, paths, and verification

The persistent native matrix is generated across seven normalized color
families, three alpha states, and leaf/ancestor targets: 14 opaque cases must be
exact, while 28 zero/tiny-alpha cases must block. Four additional cases cover
empty descendant/sibling glyph overlays with `pointer-events:auto` and
`pointer-events:none`. Together with the canonical baseline, eight prior paint
effects, and the UA-spoof case, the suite contains 56 native tests.

The exact red run returned **32 failed / 24 passed**: all 28 zero/tiny-alpha
cases and all four overlay cases escaped, while the baseline, every opaque
case, the prior paint refusals, and UA-spoof refusal remained green. After the
structural change the same suite is **56/56**. The first consolidated focused
wave exposed an honest test-platform DOM-work exhaustion at **121 passed / 2
failed / 1 skipped**; funding the new bounded work within the unchanged total
budget restored the route receipt without relaxing paint or frontmost proof.

| Gate | C04 round-4 branch | Exact main `dc7bdf79` | Disposition |
| --- | --- | --- | --- |
| complete nine-file focused Vitest | exit 0; 9 files, 123 passed + 1 native-only skip; duration 93.38s, real 94.33 | six C04 test files absent; common Cycle Board denominator below | green; no full suite |
| persistent native Chromium | exit 0; 56/56; duration 13.19s, real 14.19 | C04 twin/browser suite absent | baseline + 14 opaque exact; 28 nonopaque + 4 overlays + 9 prior negative/UA probes block |
| Cycle Board page/parity/census | exit 0; 23/23; duration 44.72s, real 46.06 | exit 0; 14/14; duration 55.25s, real 56.73 | authorization, sibling isolation, parity, census, and live twin exact |
| DS10 query-key identity | exit 0; 1/1; real 4.18 | exit 0; 1/1; real 5.17 | governed shared declaration remains byte-preserved |
| full dashboard typecheck | exit 0; real 38.87 | exit 0; real 38.03 | green |
| production build | exit 0; real 53.49 | exit 0; real 53.48 | green; normal chunk warning only; test-oracle strings absent on branch |
| scoped ESLint over all three correction TS/TSX paths | exit 0; real 13.10 | C04-only paths absent | green ownership gate |
| scoped Prettier over all three correction TS/TSX paths | 3/3 matched; real 1.04 | C04-only paths absent | green |
| i18n parity | exit 1; 37/38; real 2.83 | exit 1; 36/38; real 2.84 | branch retains only the same RU expected `67b7…` / actual `afcb…` red; main also retains the active-count red C04 closes |

Round 4 changes one existing mechanism:
`apps/runtime-dashboard/src/features/runs/export/confidenceLedgerRiskSpendTwin.ts`.
Its two P39 companions are the persistent native browser test and the existing
test-only JSDOM visibility-platform helper. This append is the mandatory
record. The complete C04 capability remains exactly the original nine
mechanism paths; no tenth mechanism, locale, route, shared exporter, second
host, direct fetch, visual/snapshot root, or C05 path is added. `ru.json`
remains frozen, and reserve remains zero.

### C04 round 5 — complete Range-region proof

This append resumes C04 only after round 4 and the separately committed C05
stop. The first 1,761 lines above remained byte-identical at
`873fb194427e9b2629562e31a31c546f580f4502d330465eece34c9f33f7f631`
before this section was added. No C05 mechanism, finding, or conclusion moved.

The review witness is one final finding in the same P38 text-paint bucket:
midpoint authority and complete glyph-region authority diverge whenever
opaque boxes cover the Range except at that one coordinate. The concrete
witness used two boxes covering 98.24% of a governed Range while leaving the
old midpoint clear. P40 therefore permits only the full bounded quantity, not
more sample points.

The rendered-visibility session now enumerates the complete document element
set admitted by the existing 20,000-node DOM cap. For every independently
native-visible element it reads the complete `getClientRects()` list, caps it
at 64, requires every returned coordinate to be finite and coherent, treats
an explicit zero-area box as a known non-region, and freezes every positive-
area numeric observation. The complete observation set is placed in a
budgeted bounding tree. Tree pruning is authorized only when two complete
rectangles have no strict positive-area intersection; every surviving leaf
box is still compared exactly. This is an exact index over the complete
census, not a sample, hit point, z-order guess, or pointer-event proxy.

Every nonempty governed text node under the root or uniquely bound dialog
still supplies its complete native `Range` rectangle list. For each rectangle,
any computed-visible census box with strict positive-area intersection blocks
unless its element actually contains that exact text node. The rule is
independent of `pointer-events`; a descendant overlay does not contain its
ancestor's text. Zero-area boundary contact is deliberately not intersection,
while any positive sliver is. Changed census membership, missing native APIs,
non-safe cardinality, unavailable/nonfinite/incoherent geometry, incomplete
tree construction, or exhausted work yields `unproved_approximation`.

Generated boxes are not silently omitted. Because pseudo geometry cannot be
bounded independently from its originating element, every computed-visible
element in the complete census must prove `content` is exactly `none` or
`normal` for `::before`, `::after`, and `::marker`; unknown or generated
content blocks before an ancestor exemption. This conservative rule makes a
non-normal pseudo a potentially intersecting box rather than claiming an
unobserved location is safe.

Removing element scrolling and point sampling makes all element and Range
coordinates one stable native observation. The pre-existing focus, window,
and scroll-container snapshots are still restored and verified in `finally`;
no focus or scroll mutation is left behind. The complete index and query work
is debited. The finite live budget moves from 1,100,000 to 1,400,000 units: the
DOM share moves from 160,000 to 420,000 and the two-observation protected
transport preflight receives 980,000. Existing rational/cardinality caps and
the 960,000-unit dual-observation exhaustion falsifier remain green.

The JSDOM native-shaped substitute remains exclusively in the existing P39
test helper. It now installs the platform method on `Element.prototype`,
matching Chromium's complete-element API rather than the narrower
`HTMLElement` test proxy. The production module still exposes no oracle,
factory, caller parameter, UA bypass, or capability-minting surface; the final
production bundle contains zero occurrences of those identifiers or the
removed sample constant.

`receiving-code-review` and the P40 pass classified this as the same P38
quantity before editing. `brainstorming` held the change behind the approved
complete-census design. `test-driven-development` required all nine exact
escapes before implementation. `systematic-debugging` distinguished the
first baseline failure as honest work-budget exhaustion and the JSDOM failure
as a test-only prototype mismatch; neither was fixed by weakening the native
property. `code-work` kept the correction inside existing mechanisms and
companions. `verification-before-completion` required the source-frozen native,
focused, type/build, lint/format, identity, locale, and exact-main receipts
below.

#### Round-5 falsifiers, paths, and verification

The red selector ran four descendant/sibling-by-auto/none cases whose paired
boxes left a hole around every former sample, four equivalent positive-area
edge slivers, and one sibling pseudo-generated box. Before the mechanism
changed, all **9/9** returned `exact`; the filtered run was 9 failed / 56
skipped. After the structural widening all nine return
`unproved_approximation`. The persistent suite grows from 56 to 65 tests and
the final real-Chromium run is **65/65**, including the canonical exact
baseline and every prior color, paint, overlay, and UA-spoof falsifier.

| Gate | C04 round-5 branch | Exact main `dc7bdf79` | Disposition |
| --- | --- | --- | --- |
| complete nine-file focused Vitest | exit 0; 9 files, 123 passed + 1 native-only skip; duration 118.45s, real 119.32 | six C04 test files absent; common Cycle Board denominator below | green; no full suite |
| persistent native Chromium | exit 0; 65/65; duration 14.11s, real 14.97 | C04 twin/browser suite absent | canonical baseline exact; all 64 conservative cases close |
| Cycle Board page/parity/census | exit 0; 23/23; duration 29.43s, real 30.31 | exit 0; 14/14; duration 31.01s, real 32.13 | authorization, sibling isolation, parity, census, and live twin exact |
| DS10 query-key identity | exit 0; 1/1; real 3.81 | exit 0; 1/1; real 3.09 | governed shared declaration remains byte-preserved |
| full dashboard typecheck | exit 0; real 22.39 | exit 0; real 21.86 | green |
| production build | exit 0; real 31.00 | exit 0; real 31.49 | green; normal chunk warning only; production oracle/sample scan is 0 |
| scoped ESLint over four correction TS/TSX paths | exit 0; real 14.36 | C04-only paths absent | green; an initial decision-literal finding was resolved structurally |
| scoped Prettier over four correction TS/TSX paths | 4/4 matched; real 1.24 | C04-only paths absent | green |
| i18n parity | exit 1; 37/38; real 2.30 | exit 1; 36/38; real 2.34 | branch retains only the same RU expected `67b7…` / actual `afcb…` red; main also retains the active-count red C04 closes |

Round 5 changes two existing mechanisms:
`apps/runtime-dashboard/src/features/runs/domain/confidenceLedgerRiskSpend.ts`
and
`apps/runtime-dashboard/src/features/runs/export/confidenceLedgerRiskSpendTwin.ts`.
Its two P39 companions are the persistent native browser test and the existing
test-only JSDOM visibility-platform helper. This append is the mandatory
record. The complete C04 capability remains exactly the original nine
mechanism paths; no tenth mechanism, locale, route, shared exporter, second
host, direct fetch, visual/snapshot root, or C05 path is added. `ru.json`
remains byte-identical at
`5366a250bd34ec702035c0953348d25e824acf80e75136bb212895cd76c36273`,
generated failure attachments were removed before staging, and reserve remains
zero. Planned append-only subject:
`fix(atlas): prove complete confidence text regions`.

### Post-round-5 audit — C04 verification stop

The bounded final replay did not approve C04. This is another worked example
of the already-declared P38 text-paint class, not a new repair round. The
round-5 mechanism proves complete layout rectangles but cannot prove that an
element's paint is contained by those rectangles.

The exact native witness is a fixed 1 x 1 sibling at the viewport origin with
`box-shadow: 0 0 0 1000px black`. Its sole layout rectangle is disjoint from
the governed text Range at `(100,100)-(479.40625,146)`, so the complete
positive-area layout index correctly reports no intersection. Chromium still
paints the shadow across the Range: `checkVisibility` is true, generated
pseudo content is absent, the hit test still resolves to the governed text,
and the screenshot's black-pixel ratio over the Range moves from `0.1800` to
`1.0`. The production twin nevertheless returns `exact`.

Adding `box-shadow` to a denylist would teach the verifier this spelling while
leaving the same property open for outlines, reflections, filter paint, and
future paint-extending effects. The missing quantity is a positive proof that
every admitted element's complete paint is contained by the indexed region,
or a side-effect-free glyph-level paint/occlusion observation bound to
stylesheet and font integrity. The browser DOM/layout APIs used here do not
supply that quantity. Capability state is `verification_missing`; the owner is
the runtime-dashboard/Atlas projection-safety verifier. Closing it requires a
new paint-containment capability or a plan amendment. Until then the native
`exact` arm is not proved and C04 is not closed.

The same audit replayed all 65 committed native cases successfully, including
the prior wide-gamut alpha, holed overlay, edge-sliver, pointer-transparent,
and pseudo-element witnesses; the new shadow-extension witness alone escapes.
No source correction follows this section. The branch remains unpushed and
unmerged for owner adjudication.

## 2026-08-29 — architect rebaseline census and mandatory denominator stop

The byte identity of the complete preceding 1,903-line, 118,368-byte journal
was
`c55326851ade555932a98bc31a5fa4dbe83e577501b0e8e97e391f5f2638965d`.
This append is the first and only local write after the architect rebaseline.

### Rebaseline identity and plan custody

The attached landing branch is
`codex/ds17-confidence-ledger-risk-spend-landing` at
`b752dbbd82706f9542af6dffb05145457910aa41`. Its first parent is the clean
DS17 stop head `7abeac6be7f58d2fe1411ac83c18f5eadfad3dc5`; its second parent and exact
current-main comparison ref is
`df90e10fb48b8df5b959c6b0074d69e255e16cc9`. The earlier execution base was
`dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`.

The architect merge changed the plan blob from
`8f57796755b1983e8414a606e3607f40475c99f6` to
`6c8b53cad6e5b002313563a81122392d91884927`: its diff contains the C05 scope
ruling and the required Explicit non-closure row for the
Bayesian-without-coverage witness, owner GY-N11, including persisted refusal
`sha256:94d60c54cac8155fa3da2765a65a6c73157876211d92771cd4e85478e864fbf3`.
This continuation does not edit the plan.

### Complete 20-row route census

“Old” is the prior DS17 target at its clean C03 boundary, “new base” is the
exact current-main parent, and “new target” is the landing union. Composite
rows preserve the denominator families used by C02; a target is “moved” only
when its old and rebaselined values differ. This produces the required 13
moved / 7 unchanged partition without dropping method or OPA sub-denominators.

| # | complete denominator | old DS17 target | new base | new target | disposition and cause |
| ---: | --- | ---: | ---: | ---: | --- |
| 1 | OpenAPI paths | 102 | 106 | 107 | moved; DS15 adds four acquisition paths and DS18 one epoch-staleness path; DS17's one path is retained |
| 2 | OpenAPI operations | 104 | 108 | 109 | moved; the same DS15 +4 and DS18 +1 operations, with DS17 retained |
| 3 | OpenAPI GET / POST | 72 / 32 | 74 / 34 | 75 / 34 | moved; DS15 adds two GET and two POST, DS18 adds one GET, and DS17's GET is retained |
| 4 | protected operations | 41 | 45 | 46 | moved; every DS15/DS18 addition is protected |
| 5 | protected GET / POST | 9 / 32 | 11 / 34 | 12 / 34 | moved; DS15 adds 2/2, DS18 adds 1/0, and DS17's 1/0 is retained |
| 6 | OpenAPI `runs.review` operations | 8 | 10 | 11 | moved; DS15 adds two review GETs and DS18 one; DS17's review GET is retained |
| 7 | route files / non-WebSocket decorators | 17 / 106 | 18 / 110 | 18 / 111 | moved; DS15 adds `acquisitions.py` and four decorators, DS18 one decorator, DS17 one retained decorator |
| 8 | decorator GET / POST | 74 / 32 | 76 / 34 | 77 / 34 | moved; DS15 +2/+2 and DS18 +1/0, with DS17's +1/0 retained |
| 9 | governed-projection module GET decorators | 5 | 4 | 5 | unchanged in target; current main lacks DS17 and landing restores its one static GET |
| 10 | guarded IDs / definitions / payload models | 1 / 1 / 1 | 0 / 0 / 0 | 1 / 1 / 1 | unchanged in target; this is DS17's separate guarded catalog, not a generic ID |
| 11 | hidden channel registry | 3 | 3 | 3 | unchanged; no slice changes the three WebSocket channels |
| 12 | curated singleton success-example keys | 100 | 104 | 105 | moved; DS15 contributes four distinct keys and DS18 one, with DS17 retained |
| 13 | generated public operation methods | 82 | 87 | 88 | moved; DS15 contributes four, DS18 its GET plus admission of the existing epoch-batch POST, and DS17 retains one |
| 14 | runtime-authz mutating-operation constant | 32 | 34 | 34 | moved; DS15 adds two POST operations; DS17 and DS18 are GET-only |
| 15 | Rego permission vocabulary | 34 | 34 | 34 | unchanged; all additions reuse existing permissions |
| 16 | Rego top-level action contracts | 26 | 26 | 26 | unchanged; no new permission contract is introduced |
| 17 | Rego `runs.review` resource rows | 8 | 9 | 10 | moved; DS15 and DS18 each add one shared resource row, and landing retains DS17's row |
| 18 | Rego distinct resource classes | 40 | 41 | 42 | moved; DS15 and DS18 each add a resource class, and landing retains DS17's class |
| 19 | Rego `runs.view` regex rows | 3 | 3 | 3 | unchanged; no slice changes that grammar |
| 20 | Rego unsafe-method vocabulary | 4 | 4 | 4 | unchanged; it remains exactly DELETE/PATCH/POST/PUT |

Two independent complete walks agree on every value: (A) the tracked OpenAPI
document plus an AST walk over all 18 runtime route files, the canonical
generator, and both generated client sources; (B) live runtime imports plus
semantic OPA evaluation and independent source-set reconciliation. The
OpenAPI walk reports landing/base 107/106 paths, 109/108 operations, 75/74
GET, 34/34 POST, and 46/45 protected operations. The AST walk reports 111/110
non-WebSocket decorators. OPA reports landing/base 42/41 resource classes and
10/9 `runs.review` resource rows. The 11 OpenAPI review operations versus 10
Rego review resources is intentional: DS15's two acquisition GET operations
share one resource.

The curated source has landing/base 106/105 lexical rows but 105/104 distinct
singleton keys because `admit_epoch_validity_batch` is duplicated; the table
uses the semantic distinct-key denominator. Including the separate
multi-example map produces 107/106 distinct covered operation IDs. Canonical
generator extraction and independent enumeration of the TypeScript and
JavaScript client sources agree at landing/base 88/87 public operation
methods (75/74 GET plus the same 13 admitted POSTs). The architect's provisional
91 counts the constructor and two private helpers as well; it is not the
previously pinned public-operation-method denominator, so it is reported, not
adopted.

The main additions are content-bound to DS15 commits `4d02940e`, `989058b2`,
and `25abf5a5`, and DS18 commits `716078d5` and `49e969e1`. The landing-only
route/resource delta is DS17 commit `3551ea02`; its generated method is in
`2ac603ff0`. The architect's provisional Rego review value 10 for current main
also disagrees with both executable walks: exact current main is 9 and landing
is 10. The rebaselined target remains 10, so this measurement disagreement
does not itself move a target.

### Supplemental pinned-denominator contradiction — STOP

The generic governed-projection catalog is outside the route-census grouping
above but is a load-bearing pinned seam. Live import and an independent AST
walk both derive, on exact current main and landing, 14 `ProjectionId` members,
14 definitions, 14 payload models, and 14 projectors. DS15 commit `25abf5a54`
added `ACQUISITION_GROWTH`; DS17 correctly remains in the separate guarded
one-member catalog.

The landing merge nevertheless resurrected two executable pins at 13:

- `tests/unit/runtime/http/test_governed_projection_api.py:90`;
- `tests/unit/runtime/http/test_confidence_ledger_risk_spend_projection.py:191`.

It also retains the stale “generic 13-ID” prose in
`src/polisyos/runtime/http/routes/README.md:22` and
`src/polisyos/runtime/http/services/README.md:28`. Exact current main has no
literal count assertion. The focused real-router test proves the divergence:
landing fails `assert 14 == 13`, exit 1, while the identical test on exact
current main passes, exit 0. Landing timing is real/user/sys
`51.06/44.99/5.22`, uptime `21:08` -> `21:09`; current-main timing is
`48.41/45.36/2.38`, uptime `21:09` -> `21:10`.

This is the prompt's explicit stop condition: a complete re-derivation
contradicts committed pinned constants. It is not repaired inside C04. Owner:
architect rebaseline adjudication, with the substantive catalog addition
owned by DS15 and the stale pins carried by the DS17 merge resolution. C04 was
not resumed, the C05 Atlas-writer path was not spent, and C06 was not started.
The mechanism ledger therefore remains 17 mechanism paths, 17/18 declared,
17/22 hard ceiling, reserve spend 0.

The rebaseline also exposes current-main reds in the synthetic mutating-sibling
test (`35 == 32` against a real base denominator of 34) and the previously
named local-environment lanes. They are not claimed inherited here: the
mandatory pinned-denominator stop occurred before the complete new-base P41
replay, so C00 remains stopped rather than falsely complete.

During preliminary non-mutating exploration, several search-only commands
used a pipe before the upstream exit code was recorded. No load-bearing value
from those invocations is used here; every value in this receipt was rerun
pipe-free with direct exit-code capture and two complete derivations. This is
recorded as a discipline deviation rather than silently normalized away.

## 2026-08-29 — denominator ruling and pin repair

The byte identity of the complete preceding 2,032-line, 127,043-byte journal
was
`fa69eff18668f65e752629d1f814f64a6c33a0678b094dcecd045a3995948924`.
This section corrects the causal wording of the preceding stop receipt and
records the architect-approved repair. The twenty-denominator table in that
receipt remains the baseline of record, including 13 moved / 7 unchanged,
generated public methods main/landing 87/88, and Rego `runs.review` resources
main/landing 9/10.

### Cause correction

There was no textual conflict and no faulty automatic conflict resolution.
DS17 correctly observed a 13-member `ProjectionId` while executing and added a
bare total pin in a different test file. DS15 independently and correctly
added `ACQUISITION_GROWTH`, moving the owner enum to 14 without touching that
test. Git then composed both correct changes faithfully, yielding a semantic
contradiction: a 14-member owner enum beside DS17's stale total of 13. The
defect is the DS17 cross-slice total pin, not DS15's addition and not Git's
merge. A bare total cannot name which legitimate member changed and therefore
cannot safely carry completeness across slice boundaries.

The two companion READMEs now describe the owner as the generic dynamic-ID
surface/service rather than freezing the same stale total in prose. The plan
blob remains exactly
`6c8b53cad6e5b002313563a81122392d91884927`.

### Red-first repair receipts

`test_governed_projection_catalog_is_typed_and_complete` now freezes the 14
explicit `ProjectionId` member names. Its first run deliberately omitted
`ACQUISITION_GROWTH` and failed by naming that exact extra member, exit 1,
real/user/sys `37.01/30.26/2.48`, uptime `22:06` -> `22:07`. Adding the named
member made the same real-router test pass 1/1, exit 0, real/user/sys
`37.63/30.66/2.21`, uptime `22:07` -> `22:08`. The existing payload-versus-enum
set comparison remains as a transport check; because both sides derive from
`ProjectionId`, it is not an independent completeness proof.

Before deleting the second total, the real catalog owner was temporarily
mutated with a second `GuardedProjectionId` and matching
`_GUARDED_DEFINITIONS` row. With the old count moved only to the current 14 so
the semantic assertion could execute, the surviving
`catalog_ids - set(ProjectionId)` assertion failed by naming the temporary
`DELETION_PROBE`, exit 1, real/user/sys `30.83/27.73/1.63`, uptime `22:09` ->
`22:10`. The temporary owner mutation was then reversed exactly; a source diff
against `HEAD` returned exit 0. The redundant total was deleted, leaving the
set-difference invariant that proves DS17 is the sole guarded, non-dynamic
catalog entry.

The final two-test lane passed 2/2, exit 0, real/user/sys
`30.60/27.57/1.66`, uptime `22:10` -> `22:11`. Both tests exercise the real
catalog/router rather than shaped markers.

### Complete changed-type sweep

Independent `git diff --name-only` and `git diff --raw` walks from exact
current main `df90e10fb48b8df5b959c6b0074d69e255e16cc9` agree on 39 DS17-changed
typed files: 15 `.py`, 13 `.ts`, and 11 `.tsx`. A complete added-line lexical
scan over those files considered every `len(...)`, `toHaveLength(...)`,
numeric `toBe(...)`, and numeric `.length` comparison.

Only the two repaired `ProjectionId` totals were DS17-authored totals whose
denominator another slice may legitimately move. Packet literals 15, 13, 67,
99, and 98 are checks over DS17's content-bound packet/schema/falsifier
denominators; zero/one checks are branch or query/cardinality semantics rather
than shared inventory totals. The 45-binding worker assertion belongs to
DS15's merged owner test, not the DS17 contribution. Shared i18n inventory
totals are likewise current-main lines, not DS17-added assertions. No third
cross-slice total was found.

The repair is inside existing C02 test/documentation companions: no mechanism
path or widening reserve is spent. The ledger remains 17 mechanisms used of
18 declared, hard ceiling 22, reserve 0.

## 2026-08-29 — new-base P41 inherited-red replay

The byte identity of the complete preceding 2,107-line, 131,086-byte journal
was
`9e7962e1d11f8b4b72eef8aa7e245df63677c775dc576ba29046b7f7536d6afe`.
Exact current main is the landing merge's second parent
`df90e10fb48b8df5b959c6b0074d69e255e16cc9`; the branch entry for this replay
is pin-repair commit `57c10b7983628f5f9980508c87357b39adad0dd7`.

The fresh exact-main scratch first received
`corepack pnpm install --frozen-lockfile`, exit 0, real/user/sys
`5.36/2.98/10.34`, uptime `22:14` -> `22:14`. This is dependency setup only,
not a product gate or source write.

| exact gate | branch | exact current main | P41 disposition |
| --- | --- | --- | --- |
| dashboard i18n parity, complete 38-test file | exit 1; 12 failed / 26 passed; real/user/sys `2.06/1.74/0.29`; uptime `22:15` -> `22:15` | exit 1; 12 failed / 26 passed; real/user/sys `3.24/1.90/0.30`; uptime `22:14` -> `22:15` | inherited: all 12 failing test identities and the missing semantic keys are identical and exclusively `pages.cycleBoard.acquisition.*`; DS17's own confidence-ledger keys do not occur in the red set |
| Ruff check of `openapi_contract.py` | exit 1; one F601 duplicate `admit_epoch_validity_batch`, branch line 3745; real/user/sys `0.05/0.03/0.01`; uptime `22:15` -> `22:15` | exit 1; the same sole F601, main line 3664; real/user/sys `0.12/0.03/0.02`; uptime `22:15` -> `22:15` | inherited: the two duplicate definitions blame to DS18 `716078d530` and DS15 `4d02940e5b`; DS17 only shifts the later line |
| Ruff format check of `test_governed_projection_validation_worker.py` | exit 1; exactly one file would be reformatted; real/user/sys `0.03/0.02/0.00`; uptime `22:15` -> `22:15` | exit 1; exactly the same one file would be reformatted; real/user/sys `0.11/0.02/0.02`; uptime `22:15` -> `22:15` | inherited: exact current main is already red; no formatter writer is run because it would rewrite main-owned lines rather than isolate a DS17 correction |

The i18n raw assertion's observed leaf total is 2,806 on main and 2,837 on
landing because DS17 legitimately adds 31 translated leaves; that diagnostic
number is not the failure ownership predicate. The failing test set and the
unadmitted acquisition declarations are unchanged. All three reds therefore
reproduce from the exact new base for the same semantic reason. None is
repaired, counted as a DS17 finding, or used to claim a green gate.

## 2026-08-30 — C04 generic paint derivation and mandatory closed-shadow stop

The byte identity of the complete preceding 2,134-line, 133,531-byte journal
was
`eebd6cc75aee52885a4f7a5feb316a0d6cf622615be5b6f8838500f02413f358`.
The bounded C04 implementation and its persistent falsifiers are committed at
`aef9eb09785878e8bbc78f0365f30865eb775ec1`. The plan remains byte-identical at
`6c8b53cad6e5b002313563a81122392d91884927`.

### Architect-directed repair built before disposition

The verifier now derives Chromium's complete computed-property set from each
visible element's own `getComputedStyle` enumeration and derives initial values
from a connected `all: initial` probe. A noninitial property that has no
positive paint-bounded proof returns `unproved_approximation`; a future engine
property therefore enters the denominator automatically and fails closed. The
same transaction:

- censuses pseudo selectors from document/adopted CSSOM rules and blocks
  noninitial unproved pseudo paint;
- rejects generated `::before`, `::after`, and marker paint, and proves the
  stylesheet-derived `::first-letter` shadow witness;
- rejects open shadow roots rather than excluding their descendants silently;
- compares every nonblank direct Text-node Range rectangle with the complete
  `getClientRects()` set of its element, closing the concrete `text-indent`
  overflow found in review;
- restricts appearance to computed `none`, requires marker-free list items,
  and scopes those normalizations to the DS17 Cycle Board page root; and
- preserves finite work through the existing DOM/style/rule/rectangle caps and
  returns typed blocking on every unsupported or incomplete observation.

No denylist was added for the named witness spellings. The mechanism changes
remain inside the already-declared C04 paths
`confidenceLedgerRiskSpendTwin.ts`, `confidenceLedgerRiskSpend.ts`,
`ConditionalDeltaFigure.tsx`, `ConfidenceLedgerRiskSpend.tsx`, and
`CycleBoardPage.tsx`. The native/browser and real-page parity tests plus
`confidenceLedgerVisibilityPlatform.ts` are P39 companions. No tenth C04
mechanism path and no widening reserve were spent.

The required targeted Chromium lane — canonical exact, the four property
extensions (box shadow, offset outline, filter drop shadow, text shadow),
stylesheet-derived first-letter, open shadow root, and text-indent escape —
passed 8/8, exit 0, real/user/sys `13.48/14.93/0.52`, uptime `23:58` ->
`23:58`. Before the final adversarial review, the complete native census
passed 72/72, exit 0, real/user/sys `54.69/59.33/0.94`, uptime `23:58` ->
`23:59`. The canonical text-indent baseline initially exposed a test-fixture
error (a long word already overflowed its one-pixel host); replacing it with
the contained one-glyph baseline made the same test exact before mutation and
blocked after mutation.

The JSDOM test platform originally returned one shared rectangle for every
element and text node. Once element `getClientRects()` joined the production
proof, that proxy made every text range appear covered by every non-ancestor.
The companion now assigns one deterministic rectangle per element and uses the
same rectangle for the element, its Range, and its bounding box. This exercises
the production containment/overlap property without pretending JSDOM has a
layout engine. After that owner fix, the twin plus real-page parity lane passed
62 tests with one intentional native-only skip, exit 0, real/user/sys
`41.53/62.56/1.85`, uptime `00:16` -> `00:16`.

### P29 remove-property/keep-marker receipt

The first literal P29 probe removed the page's list normalization while
retaining `data-ds17-confidence-ledger-page`. The old test helper inferred
`list-style: none` from that marker and the real-page parity baseline remained
green: exit 0, real/user/sys `4.33/5.84/0.45`, uptime `23:50` -> `23:50`.
That is the prohibited form-based result.

The helper was changed to derive list normalization from an actual matching
author CSSOM declaration. Repeating the same property removal with the marker
unchanged made parity fail, exit 1, real/user/sys `2.54/3.78/0.40`, uptime
`23:53` -> `23:53`. A permanent real-page test now removes only the
list-normalization rule, asserts the page marker remains, and requires
`unproved_approximation`; it passes, exit 0, real/user/sys
`2.93/3.95/0.47`, uptime `00:12` -> `00:12`. The reviewer-reported P29 gap is
therefore closed behaviorally, not by a marker assertion.

### Independent-review bucket and actual divergent case

The first frozen review confirmed the property enumeration, direct-text,
scoped normalization, open-root, pseudo, and required extension repairs. Its
remaining finding was classified under P38/P40 as the same paint-containment
class one level deeper: a closed shadow root is deliberately absent from
`element.shadowRoot`, while `document.querySelectorAll("*")`, document CSSOM,
and host `getClientRects()` cannot enumerate the root's descendants, computed
styles, pseudos, or paint.

The property is “all computed-visible paint that can affect the protected DOM
is positively contained by the indexed paint regions.” The implementation
actually observes the light-DOM element/style/rectangle census plus only
observable open roots. The exact present divergent case is:

1. append a fixed one-pixel host whose own rectangle is disjoint from the
   governed leaf and confirm the canonical evaluation is `exact`;
2. attach `host.attachShadow({mode: "closed"})`, append a one-pixel child with
   `box-shadow: 0 0 0 1000px black`, and retain the host marker;
3. prove `host.shadowRoot === null` and independently capture the governed
   leaf before and after; its screenshot bytes change, proving the closed-root
   paint reaches that protected region; and
4. rerun the production twin unchanged. It returns `exact`, including the
   exact byte twin and all nine denied protected-query answers, instead of
   `unproved_approximation`.

The isolated witness failed for precisely that mismatch, exit 1,
real/user/sys `3.18/3.92/0.43`, uptime `00:12` -> `00:12`. The final complete
native census reports exactly 72 prior cases passed and this one new case
failed, exit 1, real/user/sys `57.04/61.84/0.98`, uptime `00:14` -> `00:15`.
Thus none of the architect's required four paint-extension cases regressed;
the red denominator is exactly the new closed-root witness.

A second reviewer proposed italic glyph overhang as another candidate, then
retracted it after the production replay: baseline was `exact`, the mutated
case was already `blocked/unproved_approximation`, and zero painted candidate
pixels intersected the governed Range. It is not recorded as a finding and no
repair was made for it.

### Why this is the mandated stop

Closed mode intentionally makes “no shadow root” and “a closed shadow root”
identical through the standard after-the-fact `shadowRoot` observation. A
module-local denylist or an `attachShadow` monkey patch installed when this
late evaluator is imported cannot establish roots created earlier and would
still not inventory browser-created closed trees. The smallest sufficient
quantity is a provenance-complete shadow-root creation ledger installed before
any relevant tree can be created, or a browser/compositor API that returns
complete painted containment across closed trees. Neither capability exists in
the current runtime-dashboard verifier. Installing an earlier application-wide
observer would cross the declared C04 path set and would still require a new
proof of pre-installation absence; treating a closed host as open would violate
the platform authority boundary.

This is an actual present escape against a generic mechanism, not a
hypothetical future property. P40's second-same-class rule and the architect's
explicit “if generic enumeration provably cannot be made complete” condition
therefore require STOP rather than another spelling repair. Capability state:
`verification_missing`; owner: runtime-dashboard/Atlas projection-safety
verifier plus browser paint-observation substrate.

The eight-file ESLint lane is green, exit 0, real/user/sys
`22.73/33.08/3.10`, uptime `00:16` -> `00:17`; TypeScript is green, exit 0,
real/user/sys `14.37/23.16/1.08`, uptime `00:16` -> `00:17`; `git diff --check`
is green. The broader nine-file C04 lane, before the stop witness was appended,
reported 124 passed, one skipped, and the one already-replayed DS15 acquisition
consumer-census red, exit 1, real/user/sys `43.80/107.64/4.83`, uptime
`00:03` -> `00:04`.

C04 is not closed. C05's eighteenth Atlas-writer mechanism path is not spent,
C05 is not started, and C06 is not started. The ledger remains 17 mechanisms
used of 18 declared, 17/22 hard ceiling, reserve 0. The branch remains attached,
unpushed, and unmerged.

## C04 correction and closure — DS17 executable boundary

Predecessor journal measured before append: 2,285 lines, 142,334 bytes,
SHA-256 `6e6e584e496d9b0b3da60970225084c910ab2a5ec31778299d39c3d327f9f3b4`.

The plan blob changed from `6c8b53cad6e5b002313563a81122392d91884927` to
`b290b70159a5a4d798bc8832b4400d2807d37e40` (+18/−0 lines), committed by the
architect at `66d9b5e16`. The cause was an instruction defect: completeness was
required without a threat model, and five review rounds correctly exposed that
requirement as unsatisfiable by construction. The declared adversary is content
and projection code (packet, stylesheets, rendered DOM), not same-origin script
with privileges equal to the verifier. Closed shadow roots therefore remain a
separate executable `verification_missing` limitation owned by the
runtime-dashboard/Atlas projection-safety verifier plus browser paint-observation
substrate.

Red-before receipt (obsolete blocking expectation): focused native Chromium test
failed with the twin returning `status: "exact"` while the governed leaf
screenshots differed; exit 1, real/user/sys `6.38/6.57/0.92`, uptime `08:36`
→ `08:36`. Green-after receipt: focused test passed (1 passed / 72 skipped),
exit 0, real/user/sys `5.36/6.51/0.69`, uptime `08:37` → `08:37`. Complete
native lane passed exactly 73/73 with 0 failed, exit 0, real/user/sys
`128.19/130.67/3.67`, uptime `08:39` → `08:41`.

C04 is closed for its declared property. The mechanism ledger remains 17/18
declared, 17/22 ceiling, reserve 0. No mechanism source changed; generated
Vitest attachments and screenshots were moved recoverably to
`_build/.tmp/ds17-c04-harness-20260830/`.

## C04 independent admission and C05 representation STOP

Predecessor journal measured before append: 2,314 lines, 144,015 bytes,
SHA-256 `32735fe2fd93cae34a41b99f72b77ff26de989730cbe6f37b31fc509e668dde6`.
The custody plan blob remains
`b290b70159a5a4d798bc8832b4400d2807d37e40`.

The independent C04 review admitted commit `834788fc9`: specification PASS,
quality PASS, no NEW or same-class-deeper finding. It independently confirmed
that the fixture/construction and all three tripwires remain intact, the plan
and production mechanism bytes did not move, the journal append is accurate,
and the complete native receipt is 73 passed / 0 failed. C04 is therefore
closed for the declared content/projection-code adversary; the closed-root
`verification_missing` limitation remains separately executable and visible.

### C05 registration finding

C05 requires one implemented DS17 frontend-disposition unit binding the
governed projection, domain validator, conditional figure, panel, exact twin,
and Cycle Board consumer. The amended Bayesian-without-coverage row is a
different fact: it is already registered in the plan as `bridge_missing`,
owned by GY-N11. Encoding it as a `producer_binding_debt` supplemental finding
would leave the implemented surface unregistered and would falsely project
DS17 as the GY-N11 closure owner. That proposal is rejected under P01/P02,
P05, and P38.

Two independent walks prove the current register has no legal slot for the
required implemented post-DS1 unit:

1. Static contract walk over the complete three extension families:
   `entries` is fixed at exactly 261 DS1 roots; `subunits.scope_kind` admits
   only `dead_subgraph` and `legacy_continuity`; and
   `supplemental_findings.finding_kind` admits debts/declarations, not an
   implemented surface. Landed DS15 extended an existing DS1 root, while DS18
   required its own schema-backed top-level family. The closest Cycle Board
   root is the DS7 successor under `status-inline-explainability`, and C05
   explicitly requires DS7 bytes/semantics to be preserved.
2. Executable in-memory schema/parity probe over the complete current register
   (261 entries) injected the required DS17 ID into each candidate family. A
   new entry produced exact parity `missing=[]`,
   `extra=['ds17-confidence-ledger-risk-spend']`, `same_order=false`, plus the
   schema max-cardinality red. `scope_kind='implemented_surface'` failed the
   complete two-member subunit enum, and
   `finding_kind='implemented_surface'` failed the complete seven-member
   finding enum. The clean repeat exited 0 as a proof-of-rejection,
   real/user/sys `2.76/2.66/0.05`, uptime `08:54` -> `08:54`. An earlier run
   produced the same semantic findings but is discarded as a timing/exit
   receipt because its shell wrapper attempted to assign zsh's read-only
   `status` variable; the repeat used the task-specific `ds17_probe_exit`.

The smallest owner-correct closure is therefore an architect ruling that
either adds a typed post-seed implemented-unit family to the frontend
disposition schema/report/checker and accounts for the hand-authored schema
path, or names an existing DS1 root C05 may extend and explicitly relaxes the
DS7 preservation promise. The schema is the DS19 frontend-disposition
contract; changing it is outside C05's sole declared Atlas-writer mechanism
path and crosses a hand-authored contract owner. A Bayesian debt descriptor is
not a third option.

The semantic/visual source chain has one honest candidate seam—one scratch
repository root selected by `POLISYOS_GOVERNED_ARTIFACT_ROOT`, one canonical
copied N11 path, the existing fixture server/static route, owner worker,
generated client, exact evaluator, and Cycle Board. The existing Playwright
commands do not bind that environment root. Without an amended command or an
explicitly allowed test-harness binding, the over-spend case would require one
of the forbidden workarounds (`page.route`, governed-artifact mutation, C02
dependency injection, or another host). None was attempted.

**STOP:** C05 remains `surface_missing + verification_missing`. No C05 writer,
register, report, semantic spec, visual spec, or snapshot byte was written.
The eighteenth mechanism path was not spent; the ledger remains 17/18
declared, 17/22 ceiling, reserve 0. C06 cannot start because source is not
frozen at a C05-complete boundary. Owner for adjudication: the architect plus
DS19/team-architecture frontend-disposition-register contract; the GY-N11
Bayesian non-closure remains unchanged and is not the cause of this stop.

## C05 bounded source-chain stop receipt — DS17

The predecessor journal is 2,390 lines and 148,584 bytes, with Git blob
`fd03040624bc8d6ab346ff3c655bc1bd82f94355`. The third architect amendment is
commit `cf47ecd10`: plan blob `b290b70159a5a4d798bc8832b4400d2807d37e40` →
`3e2b48dcadcdd692ddeaa36077dbf2cb60a0a1a5` (+29/−0). The architect-ratified
cause is a plan defect: C05 named a register write target without proving that
its schema admitted the written shape. Preflight caught the defect before any
writer bytes changed; the top-level-block ruling is understood and is not the
cause of this stop.

With `POLISYOS_GOVERNED_ARTIFACT_ROOT` unset, both resolver calculations
identify this `policy-engine` worktree root and reach the real canonical
`architecture/policy_design_case/layer3_gy_confidence_ledger_contract.json`;
no environment binding is needed. Real owner-service execution at that root
returned `AvailableConfidenceLedgerRiskSpendPacket`, `availability=available`,
total spend 0, coverage `open_world_unresolved`, 13 instruments, 15 classes,
and 0 positive entries; exit 0, real/user/sys `108.98/100.74/4.75`, uptime
`09:43` → `09:45`.

Owner-artifact census A: recursive parse of all 502 `architecture/**/*.json`
files found exactly one N11-schema document, the canonical contract; independent
literal search also found only that one N11 contract. The sole unrelated
`within_budget:false` JSON is
`architecture/policy_design_case/grounding_active_controller_contract.json`.

Owner-producer census A: complete walk of 4,951 files under `src/`, `tools/`,
`architecture/`, and `apps/`, with suffix denominator
`.js=37,.json=563,.mjs=25,.py=3056,.toml=120,.ts=478,.tsx=672`, found five
target-path references and exactly one writer module:
`tools/quality/validation/check_layer3_gy_confidence_ledger.py`.
Independent owner-producer census B: AST walk of all 3,043 Python files under
`src/**/*.py` and `tools/**/*.py` found exactly one module defining the target
`build_live_contract`/`contract_bytes`/`_write_atomic`/`main` chain, the same
N11 checker.

The owner writer chain is `--write` → `_run_one_process_closeout` →
`_run_closeout_worker` → `build_live_contract` → `contract_bytes` →
`_write_atomic`. It deterministically builds the real N10/N13b accounting run
at zero spend. `validate_payload` rejects non-zero real spend using the owner
diagnostics. `ConfidenceLedgerSession.persist_receipt` writes only CAS session
receipts, not the frozen N11 contract. The HTTP route is consumer-only.

**STOP — C05 remains unstarted.** The remaining non-Bayesian C05 over-spend
semantic scenario is reachable only by direct JSON mutation/test injection or
by adding an owner-controlled over-spend producer. The latest architect ruling
forbids fabricated owner content, C02 injection, hand-authored packets, and
synthetic artifacts. The scenario therefore needs a forbidden source seam. The
smallest missing capability is a legitimate GY-N11-owned producer mode that
derives and persists an exact-scope over-spend fixture/artifact while preserving
provenance and validator custody: `producer_missing + artifact_missing`, owner
GY-N11 confidence-ledger contract/producer.

No checker, register, schema, report, semantic spec, visual spec, or snapshot
byte changed. Mechanisms remain 17/18 declared, 17/22 ceiling, reserve 0. The
twenty-denominator table remains baseline because no denominator input changed.
C06 cannot start. The plan blob remains exactly
`3e2b48dcadcdd692ddeaa36077dbf2cb60a0a1a5`.

## C05 fourth-amendment DS18 census mandatory stop — DS17

The predecessor journal is 2,449 lines and 152,115 bytes, with Git blob
`a1e59aed90f96ff802eef0d96be24f6f3ed09243`. The fourth architect amendment is
commit `bd4d0ca6d`: plan blob
`3e2b48dcadcdd692ddeaa36077dbf2cb60a0a1a5` →
`310198aefe05351ef7fe1c5708256688c6692554`. The latter remains the attached
plan blob at this stop boundary.

The amendment narrowed C05 to the sole owner-produced state: `available`,
total spend `0`, `open_world_unresolved`, 13 instruments, 15 obligation
classes, and zero positive entries/unappointed. The Bayesian-without-coverage
and over-spend end-to-end witnesses remain explicit GY-N11 non-closures. C05
still required the single existing Atlas register-writer mechanism plus its
P39 companions; it did not authorize changing a different slice's census block
or weakening a generic validator.

### C05 red-first and abandoned writer receipts

The initial focused C05 test red was the missing DS17 validator entrypoint
(`AttributeError` for `_validate_ds17_confidence_ledger_risk_spend_surface`).
After the temporary candidate checker was introduced, the same focused path
red by the named condition
`ds17_confidence_ledger_risk_spend_surface_missing`. These were diagnostic
working-tree receipts only, not a landed capability.

The first atomic writer attempt used the broad post-promotion validator. It
entered the existing long generic validation path and restored the temporary
register/report family when that validation did not complete as a promotable
receipt; no durable C05 register/report bytes remained from that attempt. A
bounded candidate writer subsequently produced a six-role/seven-edge candidate
and its immediate repeat was byte-identical for both candidate register and
report. That fact is not a closure: the broad validator was not green on the
landing source state. All temporary checker, schema, register, test, and report
changes have been reversed exactly to HEAD before this journal append.

The long full-validator attempt and the subsequently interrupted generic P29
test are non-receipts, not gates. In particular, neither establishes generic
validation nor a remove-property/keep-marker closure. UI work never started:
no semantic spec, visual spec, snapshot, route, packet seam, or C05 tracked
byte remains.

### Mandatory DS18 generic-census gate

The direct DS18 receipt is decisive. At exact current main `df90e10f`,
`_validate_ds18_time_semantics_coverage` returns zero errors. At this landing
state it returns exactly eight errors:

- four count/manifest drifts;
- one missing-list error containing five DS17 production files;
- two source-hash drifts for `queryKeys` and `CycleBoard`; and
- one `CycleBoard` root-inventory drift.

An independent complete diff/exclusion walk over the 22 changed dashboard
paths finds exactly seven DS18-scan inputs: the same five new files plus
`queryKeys` and `CycleBoard`. The register binding independently derives the
same five missing receipts and two hash drifts. This is not a sampled or
marker-only count.

The cause is structural: DS17's already-closed C04 production paths entered the
shared DS18 frozen census. DS18's own `landing_slice_rule` assigns fresh
reconciliation to the landing slice, while current main is green. Closing this
landing red would require modifying/reconciling the
`ds18_time_semantics_coverage` top-level block and its root classifications, or
weakening/exempting the generic validator. The fourth-amendment C05 boundary
forbids changing another slice's block, and weakening the census is not
allowed.

**MANDATORY STOP:** C05 and C06 remain incomplete. Capability state is
`verification_missing`; owner is the architect plus the DS18/team-architecture
frontend census contract. No C05 mechanism was landed: the ledger stays 17/18
declared, 17/22 ceiling, reserve 0. The twenty route denominators are unchanged
because no C05 tracked source byte remains. A future closure needs an explicit
owner ruling and reconciliation transaction for the DS18 census contract; it
cannot be substituted by a C05-local exemption.

## C05 fifth-amendment temporal-classification mandatory stop — DS17

The predecessor journal is 2,525 lines and 156,231 bytes, with Git blob
`db59b64b5e9c13327a51f1ae64e7c5b378d40ff8`. The fifth architect amendment is
commit `a4a8680bd`: plan blob
`310198aefe05351ef7fe1c5708256688c6692554` →
`9f2a8b0776e60784c17d516466ea86ac1b55ee2b`. The latter remains the attached
plan custody constant at this stop boundary.

The amendment correctly clears the preceding ownership stop: DS18's
`landing_slice_rule` delegates fresh receipts, independent classification and
behavioral proof for post-freeze roots to the landing slice. The cause of the
preceding stop is recorded as the instructed **instruction defect**: the
over-broad prohibition on changing another slice's block also forbade the
designed delegated path. That was not a DS18 defect and not a Git merge defect.

The newly authorized preflight found a different, semantic boundary before any
writer byte changed. DS18-CC07 defines a decision-bearing root as one
communicating a recommendation, decision status, limitation or quantity whose
interpretation can change admissibility, and requires admitted temporal context
plus behavioral `as_of`, epoch and validity rendering. A receipt refresh cannot
change that property.

### Scanner, live checker and main delta

The direct DS18 scanner and the checker's in-process scanner returned byte-equal
objects. The complete landing scan is 621 production source files / 756 render
roots, file manifest
`sha256:3b77d733281e8503762062790fbfc24da5b55ba3646fe29bda19fc93e5e451c9`
and root manifest
`sha256:6d6205ac457950b6a7091b43d215ac06f839d28126ef39c96ef11f44f8a581c1`.
The first equality transaction exited 0 at uptime `11:46` → `11:46`, with
real/user/sys `3.04/5.10/0.19` and user+sys `5.29`.

A fresh focused landing replay at uptime `12:10` → `12:10` returned exactly
eight DS18 errors, exit 0 for the diagnostic harness, real/user/sys
`2.35/3.15/0.16`, user+sys `3.31`:

- four `landing_slice_reconciliation_required` count/manifest fields;
- one grouped missing receipt for the five new DS17 source files;
- stale `source_sha256` receipts for `queryKeys.ts` and `CycleBoardPage.tsx`;
  and
- one `CycleBoardPage.tsx` root-inventory drift.

An exact-current-main archive replay at
`df90e10fb48b8df5b959c6b0074d69e255e16cc9` returned zero errors, exit 0,
uptime `12:11` → `12:11`, real/user/sys `8.09/4.66/3.64`, user+sys `8.30`.
The successful replay used an automatically removed `TemporaryDirectory`, the
exact main archive and the already-provisioned dashboard dependency tree. A
preceding shell cleanup form was rejected before process creation by the
harness; it is a non-receipt and changed nothing. Disposition: branch 8 / main
0, so all eight are DS17-owned landing reds rather than inherited failures.

### Complete DS17 input and root denominator, twice

The scanner walk finds exactly seven DS17 paths in its production denominator:

- four `no_render_root` receipts: `queryKeys.ts`,
  `useConfidenceLedgerRiskSpend.ts`, `confidenceLedgerRiskSpend.ts` and
  `confidenceLedgerRiskSpendTwin.ts`;
- `ConditionalDeltaFigure.tsx`: 3 roots;
- `ConfidenceLedgerRiskSpend.tsx`: 16 roots; and
- `CycleBoardPage.tsx`: 10 roots.

That is 29 roots. Independently, a TypeScript-compiler AST walk over every
PascalCase component return and conditional branch in the three render files
derived the same `3 + 16 + 10 = 29`. The AST transaction exited 0 at uptime
`11:57` → `11:57`, real/user/sys `0.63/0.69/0.05`, user+sys `0.74`.
Both walks derive zero `TimeSemanticsLabel` renders, zero epoch-context reads,
zero epoch-semantics props and zero epoch-provider renders across all 29 roots.
There is no disagreement.

Two independent semantic classifications then agreed on the hard denominator.
Exactly 22 current roots are definitely decision-bearing and unclosed:

- all 3 conditional-figure roots render the governed envelope, local δ amount
  and its two authority-limiting riders;
- all 16 risk-spend panel roots render or compose δ quantities, eligibility,
  execution, anytime-validity, blockers, coverage, budget/appointment posture,
  positive-register absence, source limitations or evaluation refusal; and
- 3 `CycleBoardPage.tsx` roots transitively render the DS17 risk subtree: the
  successful risk query arm, its mixed-surface compositor and the authorized
  page arm.

Six Cycle Board loading/error/access roots are honestly non-decision-bearing.
The legacy Cycle Board success adapter is not needed to settle the stop; even
granting it its strongest plausible existing classification leaves the same 22
DS17 risk roots unclosed.

The current packet carries source time and a nullable scope `epoch_ref`, but
the panel does not construct an admitted `EpochSemantics` or its typed
nonreceipt. Generic replay-key rendering is not the DS18 temporal contract, and
certificate `anytime_valid` is not decision validity. No exact existing
decision-bearing owner covers the DS17 risk DOM, so `inherits_admitted_dom`
cannot apply.

### Why the authorized receipt transaction cannot close

Each register-only spelling would falsify a binding property:

- `non_decision_bearing` would misclassify δ/status/limitation output and create
  a P05/P10/P38 authority leak;
- `decision_bearing` with `direct_ds4` is rejected because every root's actual
  `time_semantics_label_render_count` is zero;
- `inherits_admitted_dom` is rejected because there is no exact admitted
  decision-bearing owner; and
- `strict_non_jsx_projection` would be a false bypass for React roots, not an
  independent classification.

The checker's generic builder can default an undeclared root to
`non_decision_bearing`, but that is precisely the remove-property/keep-marker
false green this slice may not accept. Fresh receipts and matching hashes are
staleness tripwires, not behavioral time-semantics proof.

The smallest correct closure is to reopen C04 and wire one shared canonical
temporal owner into every risk-panel decision branch, using admitted
`EpochSemantics` or its truthful typed nonreceipt, then behaviorally mutate
`as_of`, epoch, validity and staleness while holding the shell constant. Only
then can the figure/helper/page descendants inherit that owner and C05 write
the scanner-derived receipts. The current ruling says C04 is closed at
`834788fc9` and must not be reopened; C05's sole mechanism is the Atlas checker.
Proceeding would therefore exceed the authorized cluster boundary even though
it could reuse an already-counted C04 path.

**MANDATORY STOP:** C05 and C06 remain incomplete. The DS17 surface's DS18
temporal-consumer state is `consumer_missing + semantic_test_missing`; the C05
registration remains `verification_missing`. The required ruling owner is the
DS17 architect/plan owner together with the DS18 runtime-dashboard temporal
surface contract owner. No source, register, schema, report, test, snapshot or
generated byte changed. The plan remains byte-identical at
`9f2a8b0776e60784c17d516466ea86ac1b55ee2b`; mechanisms remain 17/18 declared,
17/22 ceiling, reserve 0; all twenty route denominators remain unchanged.

## C05 sixth-amendment real-DOM-containment mandatory stop — DS17

The predecessor journal is 2,658 lines and 163,383 bytes, with Git blob
`231e47c4c3764e5feff66ecde62c7d183f2d46a2` and file SHA-256
`23be82cb539a52ea4ca53ce2d5f3cb6d4abbfbfff215f81a7ce2b38f1d4a27a7`.
The sixth architect amendment is branch commit `9cd2d028b`: plan blob
`9f2a8b0776e60784c17d516466ea86ac1b55ee2b` →
`460e89cfd896830e1ad081a7ad25901ebf8b1631`. The latter is the attached plan
custody constant at this stop boundary.

The cause of the preceding stop is recorded as the fourth instructed
**instruction defect** on this slice: amendment (5) used “scanner” more broadly
than the artifact it intended to prohibit. The prohibition meant
`architecture/atlas_surfaces/decision_time_semantics_scan.mjs`; it did not mean
the checker's already-delegated content-bound inheritance maps. The reusable
lesson is that a prohibition naming a boundary owes a check on what is already
on the other side of it. DS15's existing entries made that designed seam
visible before this amendment.

The newly authorized third terminal is executable, but its truth condition
does not hold for the DS17 render. `inherits_admitted_dom` requires a named
admitted owner that genuinely contains the inheriting root in the rendered DOM.
The complete static owner walk and a separate executable render agree that no
such owner exists for any of the 22 decision-bearing DS17 roots.

### Fresh scanner denominator and exact root partition

The direct DS18 scanner rerun exited 0 at uptime `12:45` → `12:45`, with
real/user/sys `1.19/2.49/0.08` and user+sys `2.57`. Its executor was
`node architecture/atlas_surfaces/decision_time_semantics_scan.mjs --json`,
captured and decoded without a shell pipe. It reproduces 621 production files /
756 roots, file manifest
`sha256:3b77d733281e8503762062790fbfc24da5b55ba3646fe29bda19fc93e5e451c9`
and root manifest
`sha256:6d6205ac457950b6a7091b43d215ac06f839d28126ef39c96ef11f44f8a581c1`.
The checker's in-process scanner had already returned the byte-equal object, so
there is no scanner/live disagreement.

The exact DS17 render denominator remains 29 roots: 22 decision-bearing plus 7
non-decision-bearing. A second TypeScript component/branch AST walk previously
derived the same `3 + 16 + 10 = 29`; the two classifications below were then
checked independently against the actual component composition. Every one of
the 29 scanner rows has zero `TimeSemanticsLabel` renders, zero epoch-context
reads, zero epoch-semantics props and zero epoch-provider renders.

All 22 decision-bearing selectors have `owner=NONE`:

- `ConditionalDeltaFigure.tsx`: `EnvelopeField:0`
  (`sha256:1493c37a1f57680bf3b11dad8a839ae336827c49a5bd3c3737cd6760f6bd58f0`),
  `ConditionalEnvelopeDetails:0`
  (`sha256:754b7ad94fdf3a4c14c907d5290c49ad204e58cf6f2e285d6f6b7087db766fd5`),
  and `ConditionalDeltaFigure:0`
  (`sha256:748718e147d4256b40dca61829be14f1b3689d40c2bbad6253864c4762c8c0b9`);
- `ConfidenceLedgerRiskSpend.tsx`: `SemanticValue:0`
  (`sha256:e84f94d00c13e2b971d0c01a708f814e2614157ec0a2cd9914fecc3e1209c76d`),
  `SemanticList:0`
  (`sha256:13169587c31967edd0208b4f102386f2623b9cbd9a93d902bdfd2e4c325abe66`),
  `SemanticList:1`
  (`sha256:69cfe95a1938fe2c43fdc72e9b56db0012bdef6dd11fa880207f8da27cac6c2f`),
  `DetailRow:0`
  (`sha256:f5884c37e62cec2ec5a282fd481b005b6d8ebad9be548a9c2dfb186497cc543c`),
  `SemanticSection:0`
  (`sha256:7cbf2bfe00ee858ed45c8bea759f608b692ab9c5f2b85bdd6d493296518ba871`),
  `AmountSet:0`
  (`sha256:32427fce88978a7452005b8ba507af3a144ffe45f00be066222d4b3b2e3061e2`),
  `ActualRow:0`
  (`sha256:f7e815ceabe72c780748b74081a564cad17c4fc76a43953226648c573eed0670`),
  `ClassSpendRow:0`
  (`sha256:6035a94b61cb71e340945a8a8d01b1c0becd8660fcea0985c3d489cff6388c9e`),
  `InstrumentDefinition:0`
  (`sha256:a9903f252be3b0da4a3458daa6b52fa4ecd9cf5f0fa22a847fe8b09c8aa292ca`),
  `CertificateRoute:0`
  (`sha256:c44a949405f17ea948911404cfc3e161e66b506c5f708a9ea86624173b07411c`),
  `AvailableRiskSpend:0`
  (`sha256:6a81e176af77c3580c8e365a24d1dad50cba0666c703c43af2fb231cac164b59`),
  `NonAvailableRiskSpend:0`
  (`sha256:1fd474d9b4f2f2a8d044da416ac519042cf2b065d4857d3361790394bf904603`),
  `NonAvailableRiskSpend:1`
  (`sha256:5387f6b32138bdffaea1e6a62e21d7efc86d06c4de58634c323d9a1e76dce2c5`),
  `ConfidenceLedgerRiskSpend:0`
  (`sha256:3426600483839f6aa629a7a776489eac7b2a595aa2032ada6966a295d5bddd42`),
  `ConfidenceLedgerRiskSpend:1`
  (`sha256:9286376f5d4b75be1d02a776b557c9acb494aa677bed3094682dca75ba2496d3`),
  and `ConfidenceLedgerRiskSpend:2`
  (`sha256:734b39e126fd4ad684a11baf81f3c0822fffd184d75751257b73722b5cf6832c`);
- `CycleBoardPage.tsx`: `ConfidenceLedgerRiskSpendQueryPanel:2`
  (`sha256:0e666c1e9362286bd95dea3bf53743c33b1024be693008c1265bae5eeca4a9ab`),
  `AuthorizedCycleBoardPage:0`
  (`sha256:704ae6abe7c788c389507e87f4198af436146c7c4d6101f4a6c5fdec2bb7738a`),
  and `CycleBoardPage:2`
  (`sha256:d1e9477ee0e65428cfc82390c613852bfbeaeb64ff75d6be06a00d2effa2779b`).

The seven roots independently reaching the builder's
`non_decision_bearing` arm are `CycleBoardQueryPanel:0/1/2`,
`ConfidenceLedgerRiskSpendQueryPanel:0/1`, and `CycleBoardPage:0/1`. They are,
respectively, the legacy loading/error/delegation arms, the risk loading and
transport-error arms, and the authorization-unsettled/access-denied arms. The
builder supplies the reason, rather than accepting an authored one:
“independently reviewed as layout, interaction, editor, diagnostic, or
candidate-only rendering without an admissibility-changing
recommendation/status/limitation/quantity.”

### Real-render containment falsifier

The real jsdom/Vite `CycleBoardPage` render used the existing page providers,
the real depth-N fixture and the OpenAPI-bound risk packet shape. It exited 0 at
uptime `12:44` → `12:44`, with real/user/sys `3.05/4.26/0.51` and user+sys
`4.77`. It returned:

```json
{"page_contains_owner":true,"page_contains_risk":true,"board_contains_owner":true,"board_contains_risk":false,"owner_contains_risk":false,"risk_contains_owner":false}
```

The relevant admitted owner denominator on this standalone route is confined
to the legacy Cycle Board acquisition subtree. Its direct roots are
`LoadedAcquisitionGrowth` and `AcquisitionGrowthBoundary`; neither can contain
the sibling risk panel. In the canonical render the boundary is present at
`SECTION[data-testid=acquisition-growth-boundary]` beneath
`SECTION[data-testid=cycle-board]`, while the risk surface is a sibling at
`DIV[data-confidence-surface=risk-spend]` beneath
`DIV[data-ds17-confidence-ledger-page]`. The outer page contains both but is
not an admitted direct owner. `/runs/cycle-board` is a standalone workspace
route, so `RunDetailLayout` and its epoch provider are not ancestors. The
conditional-envelope detail also uses a portal under `document.body`, which
would require its own admitted containing owner even if a page-local owner
existed.

This is the amendment's required behavioral falsifier: the proposed DS15-style
owner identifiers exist and remain constant, but the actual containment
predicate is false. Adding any of the 22 tuples to
`DS18_TIME_SEMANTICS_ROOT_INHERITANCE` would make the checker green by authored
mapping while asserting a relationship the real DOM disproves. That is a
P05/P08/P10/P29/P38 false closure and is forbidden.

**MANDATORY STOP:** C05 and C06 remain incomplete. The first named failing root
is `EnvelopeField:jsx:72:5`; like the other 21, it has no admitted owner that
contains it. The smallest correct capability is source work for an admitted
page/risk temporal owner plus a portal-local temporal owner, followed by
behavioral `as_of`/epoch/validity/revalidation proof. The current ruling forbids
reopening C04 and permits only the C05 checker mechanism, so that capability is
outside the authorized transaction. No checker, scanner, register, schema,
report, test, snapshot, source or generated byte changed. Mechanisms remain
17/18 declared and 17/22 ceiling, reserve 0; the twenty route denominators are
unchanged. Capability state remains `consumer_missing + semantic_test_missing`,
with C05 registration `verification_missing`.

### Append-only correction — checker terminal wording

The preceding journal content is 2,804 lines and 171,563 bytes, with Git blob
`386fbe2be54c0774f784d4d4eaefb1a0ccde4403` and file SHA-256
`80ebd6eb8f5cae72934b8ea66af42de7c842ed656070a6710e8694c5d5699405`.

The sentence saying that adding the 22 inheritance tuples “would make the
checker green” overstates what those tuples alone do. The current builder also
requires behavioral-evidence bindings for every inherited path; all three DS17
render paths are absent from `DS18_TIME_SEMANTICS_BEHAVIOR_TESTS`, so a
map-only transaction raises rather than turning green. The precise finding is:
supplying the false owner tuples **together with** the behavioral-evidence
bindings needed to complete that authored transaction could make the checker
accept a containment relationship the real DOM disproves. The mandatory stop,
owner absence, capability labels and mechanism ledger are unchanged.

## 2026-08-30 — amendment (7): one omission at six checkpoints; C04 temporal reopening

The preceding journal content is 2,820 lines and 172,514 bytes, with Git blob
`abf14f65da8513aed92f98e5a9d90b7857d812e5` and file SHA-256
`50c66315d184b15712c64cce17727c33f8e3bc53363ab3638cd30e9c3d5310f1`.

The custody chain since the preceding stop is append-only. Architect amendment
(5), commit `a4a8680bd`, moved the plan blob
`310198aefe05351ef7fe1c5708256688c6692554` →
`9f2a8b0776e60784c17d516466ea86ac1b55ee2b`; amendment (6), commit
`9cd2d028b`, moved it to
`460e89cfd896830e1ad081a7ad25901ebf8b1631`; amendment (7), commit
`04825a4f2`, moved it to
`d25f9c79f891cb6b77f5c35cf3168740e74dd9c8`. The last value is the new
plan-custody constant.

The root cause is one omission surfacing at six checkpoints, not six distinct
obstacles. A decision-bearing surface in this repository owes (1) a producer
capable of emitting each state the demonstration promises, surfaced at stops 1
and 3; (2) a schema-admitted registration slot, surfaced at stop 2; and (3)
admitted temporal semantics, surfaced at stops 4, 5, and 6. C04 was correctly
closed on paint containment, but that cluster closure was approved without
checking every other standing obligation on the decision-bearing surface kind
it had built. The reusable rule is: a cluster closure must test all standing
obligations of the thing it creates, not only the local property the cluster is
verifying.

The correction reverses the architect prohibition against reopening C04; it is
not another inheritance or registration workaround. C04 reopens only to render
the packet-owned `as_of`, `freshness.observed_at`,
`freshness.source_as_of`, and `freshness.state` coordinates together with the
canonical admitted-or-nonreceipt epoch/validity/staleness posture, and to add
the red-first state-mutation plus remove-property/keep-markers behavioral proof
required by DS18/P29. The paint verifier, its browser-derived property census,
the 73/0 native lane, the closed-shadow executable boundary, and the declared
threat model remain frozen; a required change to any of them is still a stop.

The temporal work is confined to paths already counted in C04. Mechanisms
remain 17/18 declared, 17/22 ceiling, reserve 0; C05's Atlas checker is still
the eighteenth and final planned mechanism. After C04 temporal closure, DS18
must derive the affected DS17 roots as direct decision-bearing roots, refresh
only the seven-path DS17 receipts and current census/manifests, and use no
inheritance claim. The twenty route denominators remain the baseline and must
not move.

## 2026-08-30 — mandatory stop: direct-root temporal chrome is not a bounded surface change

The preceding journal content is 2,865 lines and 175,120 bytes, with Git blob
`81b2130e2cd362fcd3bcb62e65b78e4d45de02fd` and file SHA-256
`51e44ff6b73aa73c80f7b085b618ce17958fcafff38ed049d61d787d8a138d68`.

Amendment (7) makes two simultaneous requirements: the 22 already-derived
decision-bearing DS17 roots must classify directly through DS18's
`root_id in primary_roots` terminal, and the closure must use no inheritance
claim. Executable preflight proves that this is not the bounded visible-surface
change the amendment assumes.

The complete source-of-truth walk is decisive. The scanner creates a root for
each top-level JSX node and increments direct ownership only for a literal
`TimeSemanticsLabel` syntactically below that root. The checker admits only
roots whose `time_semantics_label_render_count > 0`; reconciled declarations
must equal that exact label-bearing set. Provider renders, context reads and
`epochSemantics` props are recorded but do not enter classification. The four
classification terminals are strict serialized projection, direct root,
declared inheritance and non-decision-bearing. The strict terminal is an
export-only semantic mismatch here, and the last two are expressly unavailable
for these 22 roots. `CycleBoardPage.tsx` is required as well as the two named
components: the complete denominator is 3 figure roots + 16 panel roots + 3
page roots. It is already C04 path 6 of 9, so this finding is not path-budget
arithmetic.

Two independent runtime derivations over the canonical OpenAPI packet agree on
the consequence. A Vite SSR + JSDOM render and a separate structural-arithmetic
walk both derive these active-root multiplicities on the initially closed
surface:

- `ConditionalDeltaFigure` 67;
- `SemanticValue` 418;
- the two `SemanticList` roots 43 empty + 23 nonempty;
- `DetailRow` 363;
- `SemanticSection` 6; `AmountSet` 16; `ActualRow` 3;
- `ClassSpendRow` 15; `InstrumentDefinition` 13; `CertificateRoute` 6;
- `AvailableRiskSpend`, the available `ConfidenceLedgerRiskSpend`, the
  successful query-panel root, `AuthorizedCycleBoardPage` and the authorized
  `CycleBoardPage` root: one each;
- all six inactive/unavailable/dialog roots: zero on the initial render.

The 22 AST identities therefore instantiate **978** times before any envelope
dialog opens. A literal one-label-per-direct-instance implementation renders at
least 978 copies of the canonical label, and each label is a 12-row `<dl>`.
`ConditionalDeltaFigure` alone would add 67 such blocks. This defeats the
surface's standing demonstrability requirement and puts temporal chrome ahead
of the instruments the surface exists to show.

The apparent compact alternatives are false closure. Conditional,
first-instance-only, CSS-hidden, dialog-hidden, alias or marker-only labels let
the scanner see identifiers while runtime instances lack the property; that is
the exact P29 remove-property/keep-markers failure. A shared provider or one
visible packet owner is honest only if the descendants use DS18's
`inherits_admitted_dom` terminal, which amendment (7) forbids. Wholesale root
elimination would be a large non-additive rewrite of the frozen DOM/twin surface.
A new compact canonical binding recognized by DS18 requires changing the shared
temporal primitive and/or the scanner/checker ownership model; that is a
nineteenth mechanism path or a forbidden scanner edit, both explicit stops.

Three independent read-only reviews reached the same result: no existing
compact checker-supported seam exists; a direct-label implementation is
mechanically possible only as unusable repetition; and suppressing that
repetition would be form-based. Current branch and main have byte-identical
scanner, checker and `TimeSemanticsLabel` inputs, so this is not a branch drift.

**MANDATORY STOP:** no C04 source, twin, scanner, checker, register, schema,
report, test, snapshot or generated byte was changed. C05 and C06 remain
incomplete. The architect/DS18 temporal-ownership owner must choose one of two
smallest truthful closures: (1) permit content-proved inheritance from a new
visible DS17 packet owner plus the portal-local owner; or (2) authorize a
compact canonical temporal-binding primitive and teach DS18's owner mechanism
to recognize it, with an explicit path/budget amendment. Until then the
capability state is `consumer_missing + verification_missing`. Mechanisms stay
17/18 declared, 17/22 ceiling, reserve 0; the plan blob remains
`d25f9c79f891cb6b77f5c35cf3168740e74dd9c8`; all twenty route denominators are
unchanged.

## 2026-08-30 — amendment (8): DS18 temporal ownership is per file

The preceding journal content is 2,943 lines and 179,763 bytes, with Git blob
`1261f8c737ac27f0d558fa588641d8b1fe87f462` and file SHA-256
`f3c46540615f661a95387f4d57e91c5c553a53999b756209eab793bc5be4b292`.

Architect amendment (8), commit `18b6a1f7f`, moves the plan blob
`d25f9c79f891cb6b77f5c35cf3168740e74dd9c8` →
`42b37c99069855ff614e558ee2d3a5bd77865233` (+36/−0). The latter is the
new plan-custody constant.

The preceding mandatory stop refused the right implementation: marker-only or
suppressed labels would have been a P29 form gate, and the two independent
runtime walks correctly counted 978 instances under that proposed per-root
interpretation. The premise was nevertheless wrong. The DS18 scanner records
four temporal-binding kinds for each root, while
`_ds18_primary_direct_roots` enforces exactly one label-bearing primary root
for each file named by `DS18_TIME_SEMANTICS_DIRECT_FILES`. `file_owner_for`
then makes that primary root the file's own admitted owner, so the other roots
in that file derive `inherits_admitted_dom`. DS17 therefore owes three real
labels, not 978: one in each of `ConfidenceLedgerRiskSpend.tsx`,
`ConditionalDeltaFigure.tsx`, and `CycleBoardPage.tsx`.

Both causes bind the resumed work. The architect's amendment (7) described the
posture at decision-bearing-root granularity even though DS18's enforcing
invariant is per file. Separately, the executor derived the collision from one
of four scanner binding kinds without first opening the enforcing function and
its `len(matching) != 1` guard. That is the first substantive executor miss in
the seven-stop sequence. The reusable rule is: when a requirement appears
absurd at scale, treat the absurdity as evidence about the reading and inspect
the enforcing function before rigorously costing the absurd version.

The stop is cleared. Reopened C04 will add one runtime-substantive
`TimeSemanticsLabel` per named file, rendering packet-owned `as_of` and
freshness coordinates plus the canonical admitted-or-nonreceipt epoch,
validity, and staleness posture. Present/usable and absent/unusable cases, plus
the P29 remove-derivation/keep-identifiers probe, must fail red before the
mechanism passes. Scanner derivation must then yield exactly one primary root
per file; every remaining decision-bearing root must inherit from its same-file
owner. The paint verifier and scanner remain untouched.

This correction stays within existing DS17 production paths. Mechanisms remain
17/18 declared, 17/22 ceiling, reserve 0; C05's checker is still the eighteenth
and final mechanism. The twenty route denominators remain unchanged.

## 2026-08-30 — Task 9: per-file temporal surface and behavioral proof

The predecessor is the complete 2,988-line / 182,459-byte journal with Git blob
`fd2f52c00a819ea7abd6f7638d92e5c08cadf4bc` and SHA-256
`2e151260444c4c7d20a6ba8ab0f85ef11ba3b034e982f8c7549a0a0e04a2c136`.
The plan-custody blob remains amendment (8),
`42b37c99069855ff614e558ee2d3a5bd77865233`.

**Pattern pass.** P01/P02/P03 use the existing packet -> protected-query
projection -> component/route consumer -> real-page surface chain. P08/P05
keep packet clocks separate from epoch authority: every new label receives
`payloadAsOf={packet.as_of}` and `freshness={packet.freshness}`, while epoch,
validity, and revalidation receive only explicit `epochNonreceipt()`. P10/P29/P38
reject a marker gate: the assertions read the rendered values and the
remove-derivation/keep-identifiers probe is red. Missing risk data carries unknown
source coordinates and the nonreceipt terminal. P39 holds: the three existing C04
production paths changed; four tests and this journal are mandatory companions,
outside the 17/18 mechanism count.

**Red-first and implementation.** The first focused Vitest run failed on missing
temporal DOM output, not an import/harness fault: the new risk-panel and risk-query
assertions could not find `time-semantics-payload-as-of`. The exact OpenAPI
`AvailableConfidenceLedgerRiskSpendPacket` fixture provides
`as_of=2026-02-11T12:00:00Z`, `freshness.observed_at=2026-02-11T12:00:00Z`,
`freshness.source_as_of=2026-02-11T12:00:00Z`, and `freshness.state=observed`.
`ConditionalDeltaFigure.tsx` now exports `ConfidenceLedgerTemporalOwner`, its sole
literal label; `AvailableRiskSpend` renders it once before the conditional amount
collection. It stays outside the frozen `data-confidence-surface="risk-spend"` card,
so the unchanged exact DOM twin still evaluates that card. `ConfidenceLedgerRiskSpend.tsx`
owns one wrapper label around its arms, and `CycleBoardPage.tsx` owns one in the
risk-query panel only. Neither can borrow the legacy Cycle Board's time authority.

**P29 receipt.** A complete focused lane first exited 0 at uptime
`2026-08-30T10:56:54Z` -> `2026-08-30T10:57:18Z`, with
`/usr/bin/time -p real/user/sys=24.16/38.38/2.72`, 4 files / 35 tests pass.
An inverse `apply_patch` then set only all three literal labels' `freshness` and
`payloadAsOf` derivations to `null`, retaining their literal labels and owner ids.
The same lane exited 1 at `2026-08-30T10:57:36Z` -> `2026-08-30T10:58:01Z`,
`real/user/sys=24.82/39.21/2.97`: all four temporal-value tests red, receiving
`Payload as of: unknown` instead of the admitted time. The inverse restore exited 0
at `2026-08-30T10:58:17Z` -> `2026-08-30T10:58:40Z`,
`real/user/sys=22.80/34.72/2.16`, again 4 files / 35 tests pass. The complete
frozen parity file also exits 0 (16/16) at `2026-08-30T10:56:23Z` ->
`2026-08-30T10:56:46Z`, `real/user/sys=22.63/27.61/1.12`.

`corepack pnpm run typecheck` exited 0 at `2026-08-30T10:59:49Z` ->
`2026-08-30T11:00:15Z`, `real/user/sys=25.66/47.13/1.54`. Scoped ESLint over
the three production and four focused tests exited 0 at `2026-08-30T11:00:23Z`
-> `2026-08-30T11:00:55Z`, `real/user/sys=32.05/42.69/3.99`. The final focused
lane exited 0 at `2026-08-30T11:01:03Z` -> `2026-08-30T11:01:27Z`,
`real/user/sys=24.44/38.68/3.07`, 4 files / 35 tests pass.

**DS18 scanner receipt.** The unedited scanner command
`architecture/atlas_surfaces/decision_time_semantics_scan.mjs --repo-root
/Users/deniskopylov/polisyos/.worktrees/ds17-landing/policy-engine --json` exited 0
at `2026-08-30T11:01:40Z` -> `2026-08-30T11:01:41Z`,
`real/user/sys=0.96/1.96/0.08`. Its complete production TS/TSX scan reports one
label-bearing root in every participating file (3 primary roots / 32 roots), and
no second label-bearing root:

- `ConditionalDeltaFigure.tsx` (4): `ConfidenceLedgerTemporalOwner:jsx:46:5=1`
  (`sha256:2039abec9729db2adfb1ab5941d539ba7c47777f93d0c96c3b502cb3d639fd03`),
  `EnvelopeField:jsx:92:5=0`, `ConditionalEnvelopeDetails:jsx:130:5=0`,
  `ConditionalDeltaFigure:jsx:151:5=0`.
- `ConfidenceLedgerRiskSpend.tsx` (17): `SemanticValue:jsx:44:5=0`,
  `SemanticList:jsx:59:12=0`, `SemanticList:jsx:62:5=0`,
  `DetailRow:jsx:81:5=0`, `SemanticSection:jsx:99:5=0`, `AmountSet:jsx:131:5=0`,
  `ActualRow:jsx:165:5=0`, `ClassSpendRow:jsx:272:5=0`,
  `InstrumentDefinition:jsx:312:5=0`, `CertificateRoute:jsx:381:5=0`,
  `AvailableRiskSpend:jsx:411:5=0`, `NonAvailableRiskSpend:jsx:752:7=0`,
  `NonAvailableRiskSpend:jsx:810:5=0`, `ConfidenceLedgerRiskSpend:jsx:829:7=0`,
  `ConfidenceLedgerRiskSpend:jsx:843:7=0`, `ConfidenceLedgerRiskSpend:jsx:848:7=0`,
  `ConfidenceLedgerRiskSpend:jsx:851:5=1`
  (`sha256:3a79faf9de8ff067d1c5f2d1c458f6a48a3dbd61bd79ad4eddd018acff11275a`).
- `CycleBoardPage.tsx` (11): `CycleBoardQueryPanel:jsx:20:7=0`,
  `CycleBoardQueryPanel:jsx:27:7=0`, `CycleBoardQueryPanel:jsx:35:10=0`,
  `ConfidenceLedgerRiskSpendQueryPanel:jsx:44:7=0`,
  `ConfidenceLedgerRiskSpendQueryPanel:jsx:48:7=0`,
  `ConfidenceLedgerRiskSpendQueryPanel:jsx:55:7=0`,
  `ConfidenceLedgerRiskSpendQueryPanel:jsx:58:5=1`
  (`sha256:b35db63a6ddacd8a229c3285e13fa7df52e7e6ebb013c734ea6dbde8472dba8f`),
  `AuthorizedCycleBoardPage:jsx:74:5=0`, `CycleBoardPage:jsx:102:7=0`,
  `CycleBoardPage:jsx:113:7=0`, `CycleBoardPage:jsx:122:10=0`.

Task 10 alone owns the DS18 registration. Scanner, checker/register/schema/report,
shared primitive, generated files, translations, twin, plan bytes, and route-denominator
mechanism inputs are unchanged. Changed mechanism paths are exactly the three named source
files; their test companions are `ConditionalDeltaFigure.test.tsx`,
`ConfidenceLedgerRiskSpend.test.tsx`, `CycleBoardPage.test.tsx`, and
`CycleBoardPage.parity.test.tsx`. The ledger remains 17/18 declared, 17/22 ceiling,
reserve 0, and the twenty route denominators remain unchanged.

## 2026-08-30 — Task 9 review correction: retained exact data on query error

The predecessor is the complete 3,080-line / 188,335-byte journal with Git blob
`d009ee495228ec7e24277706b939aa2485475e92` and SHA-256
`78108fd35ac51929874950f5ea0e6b78d7b0de77e0bd0512e59e57c452645466`.

The review identified a P38 boundary divergence in the page-local temporal owner.
The property is that risk-packet coordinates are visible only for a *current exact*
risk-query result: not loading, not error, and exact. The old code instead accepted
any retained `query.data.status === "exact"`, while the independently rendered surface
already chose the load-error card on `query.isError`. A failed background refetch can
therefore retain an earlier exact packet for one render; the page would display an error
surface beside that stale packet's coordinates. This is a custody failure, not a display
preference: a retained payload clock cannot certify the current error result.

**Red-first.** `CycleBoardPage.test.tsx` now supplies the concrete state
`data={status:"exact", packet}`, `isError=true`, `isLoading=false`. It asserts the real
load-error surface, no risk-spend projection surface, all four packet coordinates unknown,
and the explicit `epochNonreceipt()` epoch. Against commit `d1d30bcb7`, the focused test
failed for the intended property: payload-as-of was retained as
`2026-02-11T12:00:00Z` instead of `unknown` (1 failing / 8 skipped,
`2026-08-30T11:14:27Z` -> `11:14:29Z`, `real/user/sys=2.39/3.08/0.36`).

**Correction and green.** The existing `packet` seam is now a single current-exact
predicate: `!query.isLoading && !query.isError && query.data?.status === "exact"`.
All packet-clock props consume that one value, so loading, error, absent, and non-exact
states receive unknown coordinates while epoch authority remains the separate explicit
nonreceipt. The focused regression then passed (1 passed / 8 skipped,
`2026-08-30T11:15:03Z` -> `11:15:05Z`, `real/user/sys=2.36/3.03/0.36`). The full affected
route suite and canonical available parity passed together (2 files / 25 tests,
`2026-08-30T11:15:11Z` -> `11:15:34Z`, `real/user/sys=22.21/29.53/1.49`), including the
three-visible-owner assertion. This is behavioral P29 evidence: restoring the old
retained-data predicate keeps every label identifier but makes the regression red.
Scoped ESLint over the changed route source and test also passed at
`2026-08-30T11:17:02Z` -> `11:17:23Z` (`real/user/sys=20.53/29.85/2.74`).

The unmodified DS18 scanner also passed at `2026-08-30T11:15:42Z` -> `11:15:43Z`
(`real/user/sys=0.97/2.01/0.09`). Across the complete three-file denominator, it reports
exactly one label-bearing root per file: `ConfidenceLedgerTemporalOwner:jsx:46:5`,
`ConfidenceLedgerRiskSpend:jsx:851:5`, and the updated
`ConfidenceLedgerRiskSpendQueryPanel:jsx:62:5` (the latter's root digest remains
`sha256:b35db63a6ddacd8a229c3285e13fa7df52e7e6ebb013c734ea6dbde8472dba8f`).

Only the existing `CycleBoardPage.tsx` mechanism changed, with its focused test and this
journal as required companions. No twin, scanner, checker/register/schema/report, shared
primitive, generated file, translation, other Task 9 production source, plan, or route
denominator changed. The mechanism count and Task 10 ownership therefore remain unchanged.

## 2026-08-30 — Task 10 preflight stop: post-Task-9 root denominator

The preceding journal content is 3,128 lines and 191,645 bytes, with Git blob
`750c79c5e0cffead0253fade3856bcd0e50d3cb8` and file SHA-256
`8c0e8c592a91ab0e3f064f6905eebf6a45b9adb6fa1f08af83f44d659f4b3828`.

The Task 10 writer correctly stopped before edits because its execution brief
required a frozen 29-root partition of 3 direct + 26 inherited roots. A fresh
post-Task-9 scanner and the checker's live scan were canonical-byte equal at
621 files / 759 roots, with exactly one label-bearing root in each target file.
When the three authorized direct-file/test mappings were applied in process,
the real builder returned 3 `decision_bearing/direct_ds4` roots and 29
`inherits_admitted_dom` roots.

The disagreement is in the execution brief, not the governing plan or runtime.
The brief copied the pre-Task-9 three-file root denominator: 3 + 16 + 10 = 29.
Task 9 intentionally added one temporal owner root to each file, so the fresh
denominator is 4 + 17 + 11 = 32. Two complete derivations agree: the scanner's
per-file sum is 32, and the builder's classification sum is 3 + 29 = 32. The
amendment-(8) property is exactly one primary root per file with every remaining
root classified `inherits_admitted_dom`; it does not freeze the superseded
pre-change total. Thus 3 direct + 29 inherited is the expected post-change
closure.

This is neither route-denominator drift nor a plan-constant contradiction. The
writer's timed stop probe exited 86 at 2026-08-30T11:29:25Z–11:29:28Z with
real/user/sys 2.50/3.76/0.18 and left branch `3586d88f6` clean. The corrected
Task 10 gate is the derived partition over the complete current root set:
exactly three primary roots, all other roots inherited, and no unclassified
root. No source, checker, register, schema, report, test, or generated byte was
changed; mechanisms remain 17/18 declared, 17/22 ceiling, reserve 0.

## 2026-08-30 — Task 10: DS18 reconciliation and DS17 surface registration

The exact predecessor is the complete 3,160-line / 193,584-byte journal with
Git blob `163fad2f722e5bde1c43d45a75f6422ce6a483d6` and SHA-256
`6a96c0aad83cc78ae77bda059d0158da447723b9c3d1bea2513991736eda33e8`.
Task 10 resumed from attached clean HEAD
`4f6b0ae802bd2bde5ba63512250737bdb4a664f0` after the corrected execution
brief replaced the superseded 3 + 26 number with amendment (8)'s actual
property. The governing plan remains byte-identical at Git blob
`42b37c99069855ff614e558ee2d3a5bd77865233`.

### Pattern and boundary pass

P01/P02/P03 register the already-real generated query -> independent validator
-> Cycle Board -> panel -> figure/twin chain rather than inventing another
producer. P05/P10/P15 keep the block a content-bound bounded projection: it
claims no promotion authority, global coverage, family/sequence closure, or
deployment-wide index, and the executor remains `out_of_scope`. P29/P32 require
the checker and hook to run their real validators. P35 derives all roles, edges,
files, roots, and manifests from complete sets. P37/P38 label the predicate
`recomputed` and bind it to TypeScript AST declarations/calls/imports/JSX,
not names or search hits. P39 holds the single checker mechanism apart from
exactly the schema, register, test, report, journal, and ignored task-report
companions. P41 classifies the unrelated C13 red by exact base replay.

The sole mechanism path is
`architecture/atlas_surfaces/check_frontend_disposition_register.py`. Task 10
therefore spends the eighteenth and final declared mechanism: **18/18 declared,
18/22 hard ceiling, reserve 0**. No scanner, inheritance map, seed array,
generated file, runtime-dashboard production/test path, route-denominator input,
or nineteenth mechanism is changed.

### Fresh scanner and red-first receipts

The unedited direct scanner and checker's live scan were canonical-byte equal.
The complete scan was 621 production files / 759 render roots. The three target
files contained 4, 17, and 11 roots and exactly one label-bearing root each. The
real builder partitioned their complete 32-root set as exactly 3
`decision_bearing/direct_ds4` plus all other 29 `inherits_admitted_dom`, with
zero unclassified. Final replay repeats these exact values and derives file/root
manifests
`sha256:07288b815f993f5fb8a8bc3e7875b9ab85ba72f8fcb54ec52b0c4f9949161780`
and
`sha256:ddf1bb17ef140398c65ac5db0575946c7d48383979374115433a1c11dbb259fb`;
real/user/sys `1.84/3.12/0.14`.

The stored pre-write DS18 coverage failed with the complete nine-error landing
set: four header count/manifest drifts; five missing DS17 production rows; the
`queryKeys.ts` receipt drift; and the `CycleBoardPage.tsx` receipt/root drift.
That run was at 2026-08-30T11:34:17Z–11:34:19Z, exit 1,
real/user/sys `2.27/3.26/0.14`. The first focused class was also genuinely red
(7 failed / 1 passed, `4.61/5.20/0.42`): schema/block, roles, edges, transition,
and writer did not exist. After validator wiring but before block materialization,
the real register failed with the DS17-named
`ds17_confidence_ledger_risk_spend_surface_missing`, exit 1,
real/user/sys `2.61/2.33/0.12`. Candidate tests independently rejected a
role/source/edge mismatch and removal of `conditional_figure` or `exact_twin`.

### Schema-backed six-role surface

The strict schema now requires closed top-level block
`ds17_confidence_ledger_risk_spend_surface`. The checker runs an inline
TypeScript compiler AST program from the existing Python mechanism over seven
production sources and six behavioral tests. It derives declarations, stable
hashes/coordinates, imports, calls, JSX reachability, literal bindings, and the
static specialized query key. No source regex, 13-instrument enumeration,
15-class enumeration, helper path, or second scanner is used.

The six exact content-bound roles are `governed_projection` /
`confidenceLedgerRiskSpendQueryOptions`, `domain_validator` /
`evaluateConfidenceLedgerProtectedQuery`, `conditional_figure` /
`ConditionalDeltaFigure`, `panel` / `ConfidenceLedgerRiskSpend`, `exact_twin` /
`evaluateConfidenceLedgerRiskSpendTwin`, and `cycle_board_consumer` /
`ConfidenceLedgerRiskSpendQueryPanel`. The role manifest is 6 rows at
`sha256:f19f97d97d19d347910ed647725c90e410713b3ac1094c3c281ca84955c40f3f`.
The five real edges are query -> validator, validator -> Cycle Board, Cycle
Board -> panel, panel -> figure, and panel -> exact twin; manifest
`sha256:7314850be10f69f37ade210be9c731203d635a989260eda7219f15756236d184`.
Validation before schema early-return names absence, scope drift, role
missing/duplicate/source/evidence/declaration drift, edge drift, manifest/count/
hash drift, bounded-closure drift, and executor drift.

### P29 real-property probes

Two temporary inverse-`apply_patch` probes changed no committed source:

- Removing the actual DS17 validation call from `validate_register` while
  retaining its function/identifiers made
  `test_validate_register_executes_ds17_validator` fail: only
  `schema:test-stop` remained, not the required DS17 edge error. Exact restore
  passed.
- Replacing the hook's actual `evaluateConfidenceLedgerProtectedQuery({...})`
  call with a direct packet cast while retaining the imported identifier made
  the captured-owner-byte independent-admission test fail (1 failed / 3
  skipped): invalid bytes rendered. Exact restore passed first at
  `1.30/1.65/0.22` and finally at `2.10/2.04/0.36` (1 passed / 3 skipped).
  The Task 9 source diff against HEAD is empty.

### Surgical DS18 transaction and preservation

The owner transaction builds the complete fresh DS18 candidate but permits only
the seven declared DS17 production rows plus mechanical header/count/manifests
to move. Every foreign row's raw object bytes are retained; `schema_id`, owner/
provenance, source root, exclusion policy, scanner receipt, frontend freeze
commit, landing rule, and landing checker are frozen. Historical validation is
unchanged.

The exact opening -> written values are: files `616 -> 621`; roots `733 -> 759`;
decision-bearing `45 -> 48`; same-file inherited `49 -> 78`; obligated/covered
`94/94 -> 126/126`; file manifest `sha256:d3db84a9... -> sha256:07288b81...`;
root manifest `sha256:db3923c7... -> sha256:ddf1bb17...`. A complete old/new walk
reports exactly seven changed rows: `queryKeys.ts`, the DS17 hook, figure, panel,
domain, exact twin, and Cycle Board. The preservation oracle is `[]`; every
foreign row/frozen field is unchanged. `entries`, `subunits`, and
`supplemental_findings` are exactly equal and every opening peer block is equal.
Historical replay plus current/direct evidence passed 3/3,
real/user/sys `1.35/1.99/0.09`.

### Atomic writer, report, and byte idempotence

`--write-ds17-confidence-ledger-risk-spend` is the sole new owner action. It
fresh-scans, derives the block, constructs the surgical candidate, validates
schema/DS17/DS18, renders the report from the same candidate, uses the existing
failure-atomic multi-file writer, and rereads/revalidates. It never invokes the
unscoped report writer.

Opening register/report blobs were `53f1bf796d9dcd1d037730346adcdc92258f6204`
and `fca9bfb99ec914b49f7e3e4d2bfe1d3d69cd6a2a`; SHA-256 values
`97a402803c60d6e403c478ecb03203ecc95906468d6a9889dd391a69c45463c9`
and `1312a1225199b80f282e920000aac238bc245f9b1a4e62fc18dc35e4d2c1ac2f`.
First writer succeeded with 6 roles / 5 edges / 621 files / 759 roots at
`3.55/4.94/0.26`; second writer was byte-identical at `3.53/4.95/0.25`.
After the final lint-only correction, another replay retained exact blobs
`80a5a14216d0f0b8e34b394c15f1836247762990` and
`af57e1b4f74f3f2e0329daa9611d45494b262178`, SHA-256
`bbb5998bda21a631231b847076e17c7e49fbf4207b068e3550ab2c7fe3ba2687`
and `b01b6e60124e52e8a99abc1c51026f95257b41e4ed4985c53fabfb21f02339a5`;
real/user/sys `3.57/4.96/0.27`.

### Verification and P41 disposition

- Final DS17 class: 9/9 pass, real/user/sys `8.59/12.13/0.71`. It covers
  candidate mismatches, both role removals, AST bypass, 3 + 29 partition, exact
  seven-row/foreign preservation, historical replay, real validator binding,
  and atomic writer/report behavior.
- Strict schema validation: zero errors, `1.29/1.23/0.03`.
- Focused DS18 checker: 621 files / 759 roots / 126 obligated and covered,
  exit 0, `1.71/2.51/0.12`.
- Final frontend P29 test: 1 passed / 3 skipped, `2.10/2.04/0.36`.
- `git diff --check`: exit 0. Targeted Ruff over every checker/test line added
  since Task 10 base reports zero diagnostics. The whole two legacy files retain
  701 pre-existing diagnostics; no unrelated cleanup was performed.

Required generic `--check` and `--corruption-probes` both stop before terminal
success on the same unrelated error:
`c13_print_receipt_invalid:C13 current evidence drift:`
`apps/runtime-dashboard/src/features/runs/components/AmbientTelemetryHud.tsx`.
Current timings are `79.63/107.25/10.37` and `79.48/107.33/10.14`. These are
not claimed green; DS17-named corruption tests above exercise every new mutation.

P41 replayed exact `--corruption-probes` at clean Task 10 base `4f6b0ae...` in
an isolated archive with its own 1,215 frozen-lockfile workspace links. Base
exits 1 at `77.71/105.33/10.10` with the identical C13 red plus the nine expected
pre-Task10 DS18 reds. Current removes all nine DS18 reds and retains only C13.
The complete C13 file-input denominator is 20: one receipt journal, one
environment producer, 11 `source_bindings`, and seven raw artifacts. Its
intersection with Task 10's changed set is empty. Disposition: inherited and
disjoint; owner is existing C13/DS6 evidence closure. No workaround is taken.

Immediately before this append, the branch was attached to
`codex/ds17-confidence-ledger-risk-spend-landing`, plan blob remained
`42b37c...`, and the exact dirty set was checker, schema, register, checker test,
and writer-owned report. This required journal is the sixth tracked path. None
is an input to the governing twenty-row route denominator, so its 13-moved /
7-unchanged target table remains unchanged. No seed array, foreign DS18 row,
peer block, scanner, inheritance map, generated file, Task 9 source, or
route-denominator byte moved.

## 2026-08-30 — Task 10 review correction: behavioral execution and connected root proof

The exact predecessor is the complete 3,338-line / 203,816-byte journal with
Git blob `b860f7742bf3fc6e0c5bc36ff78f2c1eb22e28c5` and SHA-256
`0c62d8dac440c6c7c5a9efffdd93d250baea2340eb5be5b8822fd2969df5e8aa`.
The correction starts from attached clean HEAD
`36dff74a610e03ae98b1cac6f1bb237dd4fda60a`; the governing plan remains
unchanged.

### Review bucket and property

The independent review's two witnesses are one HIGH P29/P38 proxy-proof class,
not two repair classes. The old role predicate admitted a test file whenever a
configured identifier occurred anywhere. The old panel-to-twin predicate admitted
unlinked module co-occurrence. Neither predicate proved the property it signed:
an imported role must execute or render on an actual `it`/`test` path, and the
exact twin's `root` input must derive from DOM rendered by the registered panel.

The smallest closing mechanism remains the existing inline TypeScript AST scan in
`check_frontend_disposition_register.py`. No new scanner, helper path, schema field,
register shape, runtime-dashboard source/test, inheritance rule, or nineteenth
mechanism is introduced. This is an append-only correction to mechanism 18/18.

### Red-first witnesses

Before the mechanism changed, both new focused tests failed with `DID NOT RAISE`.
The first in-memory override contained only the real
`ConditionalDeltaFigure` import plus `void ConditionalDeltaFigure`; the old
builder still returned six roles and five edges. The second contained the real
panel/twin imports, an unrelated panel render, and a twin call with an unrelated
root; the old builder again returned six roles and five edges.

The final literal review witnesses were also replayed read-only against the
committed `36dff74a6` checker loaded directly from Git: the identifier-only
override and the same-test
`evaluateConfidenceLedgerRiskSpendTwin("<div>forged</div>")` override each printed
`BASE_WRONGLY_ADMITTED 6 5`. No base or runtime-dashboard byte was changed.

### Generic AST execution and dataflow proof

The AST scan now resolves one non-type import from the role's exact relative
source module, retains its local alias, and rejects ambiguous or shadowed bindings.
It identifies real `it`/`test` callbacks (including modifier factories), rejects
`skip`, `todo`, and locally shadowed test runners, and traverses only direct test
statements plus reachable module-local helpers. Imported functions count only on
a call or construction path. Imported JSX roles count only when their JSX value
flows into React Testing Library's imported `render` binding; identifier presence
and unrendered JSX do not count. Static false branches, disabled tests, and paths
after unconditional return/throw fail closed.

For the exact-twin edge, a property-sensitive value flow carries the panel import
alias through JSX -> `render` result -> `.container` -> `querySelector` root,
through local variables, helper arguments/returns, and returned object properties.
The edge is admitted only when that derived root reaches the `root` property of an
invoked twin import on one reachable test execution. Same-module, same-test, or
same-owner co-occurrence without this flow is insufficient. Unsupported or
ambiguous flows produce no fact and therefore fail closed.

The focused class now has 13 tests. It pins the two review falsifiers, named-import
alias acceptance, import-shadow rejection, disabled/static-dead test rejection,
one positive aliased connected root, all previous six-role/five-edge mutations,
the exact 3 + 29 DS18 partition, seven-row preservation, historical replay, real
validator execution, and the failure-atomic writer. Final result: 13/13 passed.

### Writer and unchanged governed facts

After the checker/test correction, the owner writer ran twice consecutively and
returned 6 roles / 5 edges / 621 files / 759 roots both times. Register and report
bytes were identical across the two runs. The register correctly remains
byte-identical at SHA-256
`bbb5998bda21a631231b847076e17c7e49fbf4207b068e3550ab2c7fe3ba2687`:
the six runtime-dashboard behavioral receipts, seven production sources, role
manifest, edge manifest, and DS18 facts did not change. The writer-owned report
changed only by projecting the predecessor Task 10 commit and is now
`e99a1dedd9785d0547ffd89b814623123be03d330cc34c2d4dc87b5bd6e324bc`.
No synthetic register drift was manufactured to make an unchanged derived
artifact appear changed.

### Final verification and inherited disposition

Fresh direct scanner output and the checker's scan are canonical-byte equal at
621 production files / 759 roots. The three owned files remain 4 + 17 + 11 roots,
with exactly one label-bearing root each and an exhaustive partition of 3
`decision_bearing/direct_ds4` + 29 `inherits_admitted_dom`. The focused DS18
checker reports 126/126 obligated roots covered. Strict register schema validation
returns zero errors; changed-line Ruff returns zero diagnostics (the two legacy
files retain 701 pre-existing diagnostics); `git diff --check` is clean.

Post-correction generic `--check` and `--corruption-probes` each completed in about
86 seconds and emitted exactly the previously established inherited/disjoint C13
error for `AmbientTelemetryHud.tsx`, with no DS17 or DS18 error. Their exact final
timings were `85.86/119.34/11.18` and `85.91/119.63/11.07`
real/user/sys. The P41 base replay and zero-intersection denominator recorded in
the predecessor remain valid because this correction touches only the DS17 checker,
its checker test, its writer-owned report projection, and this append-only journal;
none intersects the twenty-path C13 input denominator.

Immediately before this append the branch was attached to
`codex/ds17-confidence-ledger-risk-spend-landing`. The exact dirty set was checker,
checker test, and writer-owned report; this journal is the fourth tracked path.
No register/schema byte, DS18 row/header, seed, foreign row, generated file,
Task 9 source/test, scanner, inheritance map, route denominator, or governing plan
byte moved.
