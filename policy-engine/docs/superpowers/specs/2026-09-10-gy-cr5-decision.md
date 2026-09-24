# GY-CR5 decision: verify the delivered non-producing grade owner

Stage 1, 2026-09-10. Lane merge base: `992aa493f`; worktree branch:
`codex/gy-lattice-and-custody`. This document precedes this lane's source
changes. The user's prompt authorizes Stage 2 after the complete decision set
is committed and read back. No push is authorized.

## Decision and the evidence that changes the implementation plan

**Reuse and verify the existing shared verifier. Do not build a second grade
authority.** The historical defect in `GGA-ADJ-01` is real, but it is not the
current implementation at this lane's supplied base. Reading beyond the initial
investigation in `docs/superpowers/journals/2026-09-07-gy-grade-authority.md`
finds `GGA-ADJ-02`, `GGA-GATE-02`, and the readback at `GGA-PA1-05`:
`d421575d3` delivered substantive authentication, observation recomputation,
promotion-basis replay, and full-subject binding. That commit is an ancestor of
the supplied base. The owning plan's CR5 row still describes the earlier defect.
The task is therefore a fresh behavioral closure of an already delivered
mechanism, not authorization to modify other completed tasks.

The Stage-1 baseline executed the five explicitly named test functions in
`tests/unit/data_forge/domains/academic/batch/test_claim_adjudication_verifier.py`:
signed observations through both intakes; self-issued/incoherent evidence at
both intakes; empty deployment appointments; fabricated execution results; and
producer/evaluator identity equality. Pytest collected 17 parameterized cases,
all passed in 29.62 seconds. The complete output is
`docs/superpowers/journals/gy-lattice/root/raw/cr5-baseline.txt`. This is preliminary
behavioral evidence, not the complete Done-when conclusion or a whole-repository
grade census. The final runner will enumerate its entire selected node set.

Three strategies were considered. A new Runtime verifier duplicates the lower
owner and leaves direct DataForge consumers vulnerable. An unconditional
quarantine closes publication but cannot demonstrate unfavorable/favorable grade
symmetry. Reusing the deployed DataForge verifier preserves both actual callers
and allows destructive-in-memory removal probes to decide whether it is doing
the work. The third strategy is selected.

## Existing owners and production callers

Paths below are relative to `policy-engine/` and pinned to the lane base until
explicitly changed. These are inspected mechanisms, not inferred symbol matches.

| Mechanism | Existing owner | Actual non-test caller and consumed effect |
| --- | --- | --- |
| Authentication and benchmark/execution observation replay | `src/polisyos/data_forge/domains/academic/batch/claim_adjudication_verifier.py::ClaimAdjudicationVerifier` | `scientist/methods/autotune/claim_adjudication_runtime.py::admit_champion` calls `replay_champion`; its `adjudicate` calls `verify_batch` before emitting a batch. |
| Sibling intake authentication | Same verifier | `data_forge/domains/academic/batch/claim_adjudicator.py::load_admitted_claim_adjudication_batch` calls `verify_batch`; `materialize_claim_adjudication_result` enters through that loader before writing compatibility output. |
| Deterministic policy and metrics | `data_forge/domains/academic/batch/claim_adjudication_policy.py` | Scientist evaluator, champion registry, runtime, and non-producing verifier compose the same policy arithmetic. Sharing arithmetic does not supply receipt provenance. CR5 is not AS1's independently implemented oracle. |
| Retained actual predecessor | `scientist/methods/autotune/registry.py` | Verifier `read_claim_promotion_predecessor` resolves the registry-owned checkpoint; missing history cannot be called genesis. |
| Full current subject and revalidated grade access | `data_forge/domains/academic/batch/admitted_claim_adjudications.py::VerifiedClaimAdjudicationRows` | `graph_builder.py` and `conflict_resolve.py` use the owner-minted capability and complete current subject before publication projection. |
| Fresh closure evidence and removal probes | This lane's journal runner and focused tests | The final non-test runner invokes pytest/probes directly and preserves exact exit status/output. It is a development assurance caller, not a new production signer or admission gate. |

The source prefixes omitted in subsequent table cells are `src/polisyos/`.
There is no deferred caller for the repaired publication mechanism: both live
intakes and downstream graph/conflict consumers are already wired. Deployed
institutional appointments remain typed-empty; they are external inputs,
not missing software callers. The default verifier accepts no appointment.

## Authority, standing, and negative outcomes

The claimant's `BenchmarkEvaluation`, its `promotable` flag, a manifest producer
name, and matching lineage are candidate data. The verifier additionally resolves
the deployment-trusted evaluator appointment, authenticates signed benchmark and
execution receipts, binds the appointed producer and corpus, checks validity
times, recomputes the complete observation denominator, policy metrics and
guardrails, and replays the actual champion predecessor. Publication results are
then recomputed from execution observations bound to the exact raw input.

P37 classification: cryptographic/content/policy predicates are `recomputed`;
agreement with independently signed observations is `independently_reconciled`;
actual institutional legitimacy is `not_established`. Configuring a fixture key
does not appoint an institution. P38 limitation: deployment trust and process
integrity are prerequisites. Hostile Python memory rewriting, filesystem
administration, or claimant control of deployment configuration cannot be
authenticated from within that same process. Normal consumer data cannot populate
the trust root. This limitation is carried rather than called proven separation
of real-world organizations.

An unfavorable authentic grade remains an admitted `ClaimAdjudicationResult`
with `publishable_edge=False`, through the same persisted batch, materializer,
graph and conflict interfaces as `True`. Missing or invalid evidence produces a
typed blocked Runtime outcome or a DataForge refusal before output. Rejected
evidence is not converted into a favorable default. A private success-only token
payload need not grow an unfavorable field: the containing result already owns
rejected/unestablished outcomes.

## Done-when conjuncts and deciding falsifiers

| Conjunct | Deciding positive/control | Falsifier and required red |
| --- | --- | --- |
| Consumer-admitted grades come from an independent producer | Separately signed benchmark and execution observations pass both entry points; full current-subject matching passes graph/conflict reads. | Self-issued/unappointed or invalidly signed evidence refuses at both intakes; an authentic receipt with fabricated observations/subject is refused. Remove authentication while keeping signatures and labels: the relevant signature refusal must fail. |
| Unfavorable results are representable wherever favorable ones are | Parameterized positive/negative observations traverse Runtime, persisted batch and materialization; both graph/conflict consumers preserve a negative grade. | Flip a constant receipt's negative projection to positive: both consumers must refuse. Do not accept a blanket missing-owner failure as the favorable/unfavorable proof. |
| A negative test proves self-issued labels are refused | A self-stamped evaluation and an independent direct batch cannot publish; default appointments are empty. | Remove `verify_batch` with all DTO/lineage/receipt markers intact: fabricated execution result must pass incorrectly, making the unchanged negative test red for each intake. |

Additional binding probes retain full-subject transport, current champion
revalidation, required actual incumbent observations, no inferred legacy genesis,
and policy identity. These check the already discovered same-class variants in
`GGA-ADJ-02`; they do not reopen a repair ladder.

## Stage 2 sequence and scope controls

1. Record a final explicit node list from the inspected tests. Independently
   cross-check its identities with pytest collection; unreadable/uncollectable
   nodes are ambiguous, never absent or passing.
2. Run the authentication and observation-recomputation removal probes in fresh
   Python processes. Patching is process-local; no source file is rewritten.
   Keep full stdout/stderr and the actual deciding pytest exit status.
3. Run the unchanged positive, unfavorable, self-issued, sibling-consumer,
   predecessor and subject-binding tests. A new defect, if any, is bucketed before
   proposing a scoped repair; the second same-class finding widens the mechanism
   or records a bounded residual and its executed falsifier (P40).
4. Cross-review the evidence, run only relevant Ruff and the root's full
   architecture guardrails command. No broad test suite, ledger checker, sync,
   governed epoch bump, or generated artifact reissue is implied.
5. Update only CR5's §8.5 standing row with the measured boundary and the single
   completion journal. Do not rewrite the historical journal or completed tasks.

Untouched seams: `dependency_authority.py` and its fieldless success token;
`transitive-runner-closure-unbound`; institutional appointment issuance; Atlas's
client-computed badge repair; historical task-completion census; existing
authority schemas, rule versions, corpus appointments and N11 identities. No
production source delta is planned. If an unforeseen required delta reaches a
governed identity, its transition must be declared from `992aa493f` first.

## Pattern pass and routing

Relevant IDs: P01/P02 (real callers), P05/P15 (claimant authority), P27/P31
(single existing intake), P29/P32 (property removal/content authentication),
P35/P36 (complete selected denominator and findings), P37/P38 (actual predicate
and trust boundary), P40/P41 (bounded review and red attribution). Existing
anti-pattern: the task-standing description is stale relative to a delivered,
wired mechanism. Target pattern: source-traced caller chain plus fresh behavioral
and removal evidence, with status reflecting exactly that scope.

Preliminary capability label is `verification_missing` for this task's fresh
closure receipt, not `producer_missing` for the already delivered verifier.
Institutional deployment evidence remains `absent/unallocated` unless supplied
externally. The stale CR5 narrative routes to this lane's authorized §8.5 row;
`public-decision-verified-badge-is-client-computed` stays in the Atlas surface
lane. Any incidental new finding routes to a named architect-owned debt row or
research backlog in the completion journal; neither DEBT-REGISTER nor LEDGER
is edited here.
