# DS18 holder invocation: decision before source changes

Lane base: `c49449343`. Scope: `ds18-epoch-history-independent-holder-unappointed`.
This decision routes the existing owner; it does not appoint an institution.

## Record versus tree

`UNINVOKED-DS18-01`: the recorded absence of a source **evaluation** consumer still
agrees with the inspected base. `runtime/http/container.py` imports and calls
`build_production_epoch_anchor_custody_provider`, and stores its protocol on
`RuntimeServiceContainer`. Construction alone does not evaluate custody.
`runtime/quality/chronology_custody.py` has the implementation of
`evaluate_acceptance_and_custody` and `evaluate_retained_challenge`; the call sites
found during orientation are in `tests/unit/runtime/quality/test_chronology_custody.py`
and the test helper, not a served route. Root's complete tracked `src/**/*.py` AST
census, independently cross-checked, is the deciding set-level evidence; this
orientation search is not a denominator or a zero proof.

`UNINVOKED-DS18-02`: do not collapse that finding into “the provider is missing.”
The production factory already constructs `EpochAnchorCustodyService`,
`NoEpochAnchorAppointmentResolver`, `EmptyEpochAnchorAuthorityRegistry`, an
unavailable issuance port and an in-memory challenge repository. The provider
produces role-separated `AnchorCustodyVerification`: aggregate `limited`,
acceptance `not_established` with `anchor_acceptance_owner_not_established`, and
retention `not_established` with `anchor_holder_not_established`. Its output is a
typed non-receipt, not independent history evidence. The missing links are
`bridge_missing`, `artifact_missing`, `surface_missing`, `semantic_test_missing`.

The GY-N12 implementation plan, Task 3.1 production-composition requirement,
already names the provider factory as the sole no-argument production root.
It forbids downstream construction/injection of the internal custody service,
resolver or registry. This decision preserves that boundary.

## Decision and production caller

Use a local audit CLI, not a new authority mechanism. Its runnable terminus is:

```text
python -m polisyos.runtime.quality.epoch_custody_audit --request REQUEST.json --cas-root CAS
```

The new non-test module `src/polisyos/runtime/quality/epoch_custody_audit.py`
parses an existing strict `AnchorAcceptanceRequest`, obtains the existing
no-argument provider, calls `evaluate_acceptance_and_custody`, and persists the
request and typed result through `FileSystemCAS`. It reads the saved bytes back
before printing the receipt and its content-addressed reference. The envelope
binds the exact request artifact, rule/schema version, provider identity, UTC
observation time and result. The observation time describes this invocation;
it is neither history validity nor institutional admission time. CLI completion
means an audit result was persisted, not that custody was established.
The wrapper uses the existing generic `canonical_statement_bytes` and
`parse_canonical_statement` codecs for exact typed request/result roundtrips.
It rejects a non-epoch family or disagreement between request and domain
authority purpose before invoking the epoch provider; it does not choose a
replacement scope or purpose.

| Mechanism touched or reused | Non-test production caller / runnable chain |
| --- | --- |
| `build_production_epoch_anchor_custody_provider` | `epoch_custody_audit.audit_epoch_custody`, called by `epoch_custody_audit.main` and its module entry point |
| `EpochAnchorCustodyProvider.evaluate_acceptance_and_custody` | `epoch_custody_audit.audit_epoch_custody` → existing `EpochAnchorCustodyService.accept_retain_and_verify` |
| Existing appointment resolver and empty registry | Existing factory/service above; their authority boundary and implementation remain unchanged |
| Audit request/result persistence and readback | `epoch_custody_audit.audit_epoch_custody` → existing `FileSystemCAS.put_bytes/get_bytes`; `main` emits the saved result |

The request is candidate input. Its history references remain opaque to this
audit wrapper, as the existing `AnchorAcceptanceRequest` contract requires:
only an appointed acceptance owner may resolve them into admitted history.
The wrapper must not equate a well-shaped reference, a readable blob, or the
successful invocation with authentic or complete history. The current result
truthfully records the absent appointments. The CLI is a deliberate audit run;
automatic HTTP invocation and positive independent-holder appointment remain
outside this bounded wiring claim.

Rejected alternatives: changing the closed DS18 temporal projection would
alter an already-closed task; calling the provider only from a helper would
leave a caller without a runnable caller; deferring all invocation on an
appointment would repeat the task-Q finding, because the no-holder arm is
already implementable without appointing anyone.

## Frozen boundaries and transition effects

No edits to existing chronology custody, chronology contracts/security,
semantic-epoch, transition, temporal-service, container or dependency source.
No edits to `DEBT-REGISTER.md` or `LEDGER.md`. Root owns README and any shared
surface edits. The new module is internal and has its own module entry point;
it does not change the public facade, HTTP/OpenAPI/client, generated policy
artifacts, accepted epoch or governed predicate-policy bytes.

Measured transition basis is this lane's merge base `c49449343`, not GY-N12's
start. The planned source delta adds only the audit module; it does not request
an epoch bump or reissue an existing governed artifact. If root's complete
dependency checks establish that a governed aggregate includes the new path,
root coordinates that transition before any reissue. No workstream may silently
change a bound hash. Per-invocation CAS audit artifacts are new observations,
not reissues of authority artifacts.

`UNINVOKED-DS18-03`: the excluded
`ds18-epoch-predicate-policy-signer-unappointed` basis holds in the inspected
path. `dependencies.build_runtime_api_context` constructs
`SemanticEpochService.for_unallocated_policy_query`; the served
`routes/temporal.get_run_epoch_staleness` calls
`TemporalService.build_epoch_staleness_projection`, which calls
`qualify_chronology_query`. That existing factory establishes procedural
`policy_admission_missing` without inventing history owners. No improvement
to this correct refusal is authorized or needed here.

`UNINVOKED-DS18-04`: this work does not change what blocks
`ds18-positive-transition-production-unorchestrated`. It does not provide a
pre-N9 trigger, complete `EpochDependencyDenominatorProvider`, complete
`EpochPerturbationAdjudicationProvider`, or purpose-scoped transition
signer/producer identity. It also does not configure the optional denominator
reconciliation reader or its verifier provenance. Custody audit refusal is
not a positive epoch transition. The GY-CR4 reconciliation mechanism is
inspected as an existing dependency, not reopened.

## Red-first execution and deciding evidence

1. After root commits this decision, add a targeted test invoking the actual
   module CLI on a typed request and temporary CAS. With no module it must fail
   for the missing runnable caller, not an environmental error.
2. Implement the wrapper. The same test loads persisted CAS bytes, revalidates
   the strict envelope and asserts both role negatives, their exact subject and
   query bindings, and the request content reference. A second request with a
   different purpose/query must yield its own bound refusal. Malformed request
   fields must fail without an invocation receipt. A missing/invalid provider
   result must never be serialized as a completed invocation.
3. Removal probe: temporarily replace only the new production evaluation call
   with `None`. Run the unchanged no-holder CLI test. It must become red,
   because there is no valid persisted result, while the existing negative
   expectations remain unchanged. Restore exact bytes and rerun targeted green.
4. Run the existing targeted production no-holder and sole-constructor guard
   tests plus lint of touched Python paths. Root checks the combined architecture
   delta and census. Every gate is the sole command of its invocation.

Only selected test nodes are in scope; no directory suite. Retain complete
deciding output under the gitignored `journals/uninvoked/ds18/raw/` and cite it
by path/hash from the single root completion journal. Do not copy source or
parallel forms of CAS bytes into that journal.

## Pattern pass

Relevant patterns: P01/P02 (built provider without evaluation), P03 (unsurfaced
negative), P05/P32/P37 (appointment absence remains `not_established`; a local
audit is not authority), P08 (observation is not validity), P29/P33 (real module
run, persisted readback, removal probe), P35 (complete AST denominator owned
by root), P38 (construction is not invocation; invocation is not authenticity).
The audit predicate is `recomputed` from the exact live provider call and saved
bytes; institutional predicates remain `not_established`. Acceptance is a
runnable production caller whose unchanged negative test fails on removal,
with both institutional gaps still visible. An issue in this same boundary is
classified as the same class before repair; a second such issue requires a
wider mechanism or a declared, falsified bounded residual per P40.
