# GY-N12 Epoch Chronology Design

## Status

Research specification, Cycle 3 revision, independently reviewed and
delta-clean. No production code, governed artifact, writer, deployment-bound
artifact or generated surface is authorized by this document. Cycle 4 and its
adversarial delta reviews remain open; the final specification requires user
approval before implementation planning.

## Problem

GY-N12, GY-GAP3, GY-GAP5 and the composition half of GY-GAP6 all need
chronology properties: complete membership, ordered history, scoped heads,
content binding, append-only consistency and offline replay. They consume
different family-native facts:

- fixed-semantic model/rule/data epochs and certificate validity;
- controlled release-family records and verifier dispositions;
- production recursive-cycle runs and resolved terminals; and
- exact per-row acquisition-to-re-entry movement.

The design question is whether one chronology semantic owner can serve those
families without weakening their native identities or rebuilding the refuted
universal `OperationalEventEnvelope`. Cycle 1 establishes that the common
membership/consistency owner does not already exist, while also establishing
that Decision Validity and Claim Ledger already own decision currentness and
claim history and must be extended rather than bypassed.

## Governing decisions

1. **Custody Time Model:** nine sparse roles, relations not clocks, explicit
   query coordinates, family-native persistence; no universal event envelope.
2. **INT-K05:** every `DesignProblem` root remains the primitive identity. A
   family is a reproducible declaration over roots, never a parent scope.
3. **S0-K05/S0-K07:** observation, transport, projection and chronology cannot
   mint authority.
4. **PV-K02:** a present evidence failure may change current validity but never
   erase the authentic historical member.
5. **PV-K07:** prefix discipline remains unissuable until a controlled release
   history can prove deletion/narrowing rather than pass over it.
6. **INT-K08:** refusal, void, dispute and exhaustion are completed governed
   terminals and remain members; quotas cannot turn them into permission.
7. **P37/P38:** every decisive predicate is recomputed or independently
   reconciled by its authority owner; presence, positivity, caller declaration,
   timestamps and exit codes are not substitutes.

## Measured starting state

The complete census and commands live in
`docs/superpowers/journals/2026-08-20-gy-n12-cycle-1-substrate-census.md`.
The decisive classifications are:

- Fabric bitemporal facts/query, L5 regime inputs, L3 amendment inputs, rule
  replay, Decision Validity currentness/lineage and initial Claim Ledger v2
  persistence: `implemented` within their native claims.
- The governance-to-claim lifecycle bridge is
  `implemented_but_not_orchestrated`.
- N13b passport/overlay persistence: `implemented_but_not_orchestrated`; its
  production seam is `bridge_missing` and its caller-supplied epoch stamp has
  no semantic-coordinate producer.
- N7 same-cycle re-entry and a single returned recursive run have real producer
  logic but no independent persistence/query surface: `artifact_missing`.
- N12 chronology, OpenWorldRisk/epoch resolution, GY-GAP3 release transcript,
  GY-GAP5 complete enumeration and GY-GAP6 exact movement:
  `absent/unallocated`.
- The epoch-to-Decision-Validity trigger is `producer_missing`; automatic
  derivation-recipe recomputation remains `absent/unallocated`.
- N11's scope-local CAS/hash-chain/WAL and core audit/security hashing,
  signatures and optional replicas are implemented within their native claims.
  They are reusable proof machinery/precedent, not a generic chronology owner
  or a writer-independent accepted anchor. The common proof protocol and
  accepted-anchor chain remain `absent/unallocated`.

## Non-goals

- No universal persisted event envelope, global clock, synthetic `as_of`, or
  one physical log for unrelated family payloads.
- No new parent `DesignProblem`, merged scope identity, parallel release/run/
  movement ledgers, certificate-validity ledger, decision-currentness head, or
  dashboard-owned truth.
- No assumption of an epoch when regime/amendment data is missing.
- No erasure or rewrite of historical authenticity when evidence becomes
  stale, invalid, superseded or withdrawn.
- No proof of completeness against unknown external copies. Their existence
  limits the claim.
- No implementation or governed artifact during the four research cycles.

## Cycle 3 verdict — one protocol, split semantic authorities

Cycle 3 supports a **qualified unification** as the architecture direction and
refutes the stronger candidate against repository counterexamples. The
specification calls for one shared, policy-free **chronology-proof protocol**,
with four family-native adapters and proof domains. No implementation evidence
yet promotes that `absent/unallocated` capability. There is not one chronology
semantic or authority owner.

The shared protocol owns:

- proof-domain and canonicalization-profile versions;
- scoped content commitments to native records;
- proof append/predecessor relations, explicitly non-semantic;
- family-scoped commitment-head derivation;
- offline inclusion and old-to-new consistency verification;
- accepted-anchor verification and typed limitation results; and
- detection of deletion, substitution, reordering, fork replacement and
  post-hoc basis narrowing.

The family authority supplies and owns:

- native member schema, persistence, scope/root and applicable CTM roles;
- declared basis and complete source-denominator reconciliation;
- semantic eligibility, applicability, correction/fork policy and native
  predecessor/successor relations;
- authority heads/currentness/status/terminal, if the family has them; and
- acceptance of the proof anchor by a competent consumer outside the
  transcript writer's mutation authority.

This is one real protocol, not four ledgers behind a common interface: family
adapters may not reimplement commitment, consistency, anchor verification or
generic mutation dispositions. It is also not a central temporal platform:
the protocol may not require a common payload, timestamp, status, action enum
or physical log, and may not infer any family authority predicate.

The proof layer has a **commitment head**, never an authority head. It proves
only the prefix admitted under a declared basis and accepted earlier head.
It cannot establish that every required release, boundary source or production
run was admitted. Each family owner independently reconciles the committed set
with its complete canonical denominator. Decision Validity remains the sole
owner of packet currentness and lineage heads; Claim Ledger remains the
claim-history owner; generation-cycle producers retain terminals; N13b/N7
retain endpoint evidence.

Acceptance is a separate P37 predicate, not a location or `accepted=true`
field. Every anchor freezes the accepting owner, proof-domain identity,
signature, prior anchor, admission cutoff, witness or consumer-receipt basis,
verifier provenance and admission provenance class. At least one retained
anchor crosses a custody boundary the writer cannot rewrite. The common
contract verifies that receipt; it cannot accept its own head. Until a family
names and implements that consumer/holder chain, the strongest result is
consistency relative to a supplied head and whole-history authenticity is
`not_established`.

The epoch inference is now confirmed within CTM's boundary: an `epoch_ref` is
a content-bound fixed-semantics replay selector at explicit native coordinates,
not a third clock. Valid/effect time and transaction/knowledge time retain
their meanings; the epoch selects an admitted model/rule/schema/data/
interpretation basis. Proof append order cannot select semantic applicability.

The proof contract is algorithm-profiled rather than Merkle-specific.
RFC-style membership and append-only consistency are behavioral properties.
Because offline replay already carries the full native history, a full-prefix
content hash chain over reusable canonical hashing/CAS/signature machinery is
the bounded provisional profile, not a settled scale claim. Before
implementation chooses it, measure per-family cutoff-bound member counts,
canonical bundle bytes, owner latency/storage ceilings and admitted
selective-proof demand. Full replay pays linear verification; exceeding an
owner ceiling or requiring sublinear selective proof selects a Merkle profile.
Either profile must satisfy the same frozen closure basis.

The complete argument, counterexamples and ownership matrix are in
`docs/superpowers/journals/2026-08-20-gy-n12-cycle-3-unification-verdict.md`.

## Family obligations

### Epoch family

Derive epoch boundaries generically from the complete resolved set of every L5
`schema_regime` interval, every applicable L3 amendment window and every
owner-admitted N13b acquisition boundary (dataset version, source watermark or
overlay epoch). The generic boundary-source denominator is owner-declared and
free-growing; engine conditionals cannot enumerate source kinds. The authority
owner resolves at an explicit scope-native coordinate and records the complete
input/basis hashes, rule version and provenance. A new domain regime or valid
novel boundary-source registration added through data alone creates semantics
without engine edits; malformed or unadmitted sources fail closed.
Ukraine v1/prewar and v2/wartime is the first case, never an engine enum.

No applicable regime/amendment basis yields `epoch_scope_unresolved`, not an
assumed baseline. N13b passports must bind the resolved epoch identity and
basis proof; a caller-supplied positive integer is insufficient.

Resolution consumes owner-native valid/effect and visibility coordinates plus
the authority context, and returns a discrete semantic reference with content
and predecessor commitments. The reference is not an independent timestamp;
maximum transaction time, receipt time or chronology position cannot select
the epoch head.

Every certificate binds its issuance epoch, model/rule/schema/data identities,
inputs, derivation recipe, authority purpose and relevant native time
coordinates. A semantic perturbation marks affected current certificates stale
or revalidation-required through Decision Validity and then flows into Claim
Ledger/lifecycle bridge for affected public claims. Recipe recomputation is a
separate missing producer/owner that must be appointed before implementation.
Historical certificates remain verifiable at their original coordinate.
Affected scopes freeze promotion immediately on an admitted revision trigger;
the decision front is revalidated to `current_valid` members only. High
OpenWorldRisk freezes promotion as well as limiting public claims.

Arrival is not adjudication. An incident, appeal, correction, retraction,
discovered bias or other source event is advisory input. Until the canonical
owner resolves, content-binds and adjudicates it, its maximum effect is the
applicable `review_required`, `contested` or annotation band. Only the admitted
owner disposition can select `annotation_only`, `invalidate`, `reissue`,
`supersede` or `withdraw`.

### Controlled release family

Each release member binds the native release record, model and rule versions,
inputs, verifier identity/provenance and disposition. The declared family basis
is immutable after admission except by an appended correction/supersession.
Offline replay proves membership and append-only consistency relative to an
independently accepted head carrying the frozen anchor basis above. The family
owner also reconciles that admitted prefix with the complete release
denominator; an inclusion proof cannot prove a release was required to be
submitted. Deleting, substituting, reordering, whole-history replacement or
narrowing controlled
history fails. Unknown external copies or heads produce a typed limitation
rather than a false globally complete/latest claim.

### Recursive-run family

Each production member binds exact `DesignProblem` content, recursive graph and
cycle content identities, authority scope and owner-derived terminal. The
family enumerates the complete production receipt denominator, orders admitted
runs, derives current heads per existing root from an explicit native
supersession/retry relation and projects resolved terminals. Append position or
maximum timestamp cannot manufacture a native run head; absent that relation,
the head is unresolved rather than guessed.
Recording/projection failure cannot change the completed run or terminal.
Deletion, substitution and basis narrowing fail replay. A best-effort recorder
cannot establish “all production runs”: every production path must cross a
single content-binding receipt-or-gap emission boundary. Durable receipt
failure leaves a run-bound custody gap that the independently complete source
denominator must expose; chronology is incomplete/`not_established` until
reconciled. GY-GAP5—not INT-K08—requires recorder failure never to change the
producer-owned terminal. INT-K08 requires negative terminals to remain
completed members and missing custody never to become permission or green;
recorder success is not permission or terminality.

### Movement family

Movement is a relation over admitted native members, not a new clock or a
Boolean inferred from adjacent counts. Each row binds N13b observation,
passport/raw evidence and resolved epoch to the same `DesignProblem`, recursive
run/cycle, N7 same-cycle re-entry receipt and before/after owner-derived
terminal. Missing any link is absence, never “no movement.”
Movement has a commitment head for proof integrity but requires no independent
native authority head; its query projection consumes endpoint-owner heads and
terminals.

## Authority predicates

Every implementation predicate must freeze one of these provenance classes at
admission: `recomputed`, `independently_reconciled`, `consumer_asserted`,
`institutionally_supplied`, or `not_established`. Authority-grade admission
accepts only the first two. In particular:

- epoch membership is recomputed from complete regime/amendment inputs;
- every generic boundary source is resolved and admitted by its canonical
  owner; an event's declared action is never the gate predicate;
- packet currentness and lineage heads are recomputed by Decision Validity,
  never by the chronology proof layer;
- claim lifecycle is appended by Claim Ledger/lifecycle bridge, never projected
  into authority by chronology;
- release membership is recomputed from the immutable declared family basis;
- release/run completeness is independently reconciled against the family
  owner's source denominator; proof of an admitted leaf is not completeness;
- run membership or an explicit run-bound custody gap is emitted at the single
  production boundary, not discovered later by a dashboard census;
- terminal values are recomputed/validated by their existing owners;
- movement identity is recomputed from exact row/passport/run/re-entry refs;
- chronology consistency is verified from content commitments and predecessor
  relations, not timestamps, list position or an exit code;
- a commitment head proves prefix integrity only; native authority heads are
  recomputed by the applicable owner and cannot be inferred from it;
- accepted-anchor provenance is independently reconciled by the named family
  custody consumer; a writer-retained adjacent copy or self-attested witness
  cannot establish whole-history authenticity.

## Completeness gates (§3.5.6 instantiation)

The decisive property is: **the owner can reproduce the complete admitted
history for a declared native scope and detect any mutation or narrowing that
could manufacture a pass, while preserving historical authenticity**.

The eventual suite must include:

1. **Full denominator:** enumerate every member from the family authority's
   source of truth and reconcile it with the chronology; no fixture list or
   sampled directory. The production-run case additionally derives every live
   production entry path and proves all paths cross the single receipt-or-gap
   boundary. A run that completes while durable receipt is suppressed must
   remain in the source denominator and make the complete-chronology claim fail
   closed rather than disappear.
2. **Fail closed on fake or novel input:** reject a valid-shaped member with a
   wrong content binding, fake verifier provenance, unknown relation, supplied
   epoch, sibling-scope substitution, or undeclared family basis.
3. **Data-only free-grow:** add a synthetic domain's new L5 regime/L3 amendment
   and a valid novel boundary-source registration through data only; epoch
   resolution and stale propagation change with zero engine enumeration/edit.
4. **Contract mutation:** remove the actual decisive content/consistency
   validation while retaining field names and marker strings; the behavioral
   gate must fail.

The complete negative denominator will be frozen in a separate closure-basis
artifact after adversarial review. Until then, it is a draft and cannot be used
to claim completeness.

## GY-DEF22 owner-preserving folded closure

The task explicitly routes GY-DEF22 into this lane, but its canonical authority
stays at the Foundry catalog/discovery boundary, with the N8 tool as producer
and N10a validator as consumer. N12 consumes the resulting identity; it does not
mint or absorb it. One deployment-environment identity must serve that chain
and chronology work. The owner record must name a reconstructible admitted
dependency profile/root/distribution discriminant rather than only an observed
package list. The validation owner compares the decisive profile identity
before backend/package fingerprints. The epoch derivation recipe binds that
profile identity: omitting a tool/environment dependency from the declared
recipe closure is a false-revalidation pass, not an irrelevant packaging gap.

Required falsifiers are:

- the documented `research` environment with `torch==2.10.0` fails and names
  the discriminating profile/root/distribution difference;
- a difference in an irrelevant package outside the deployment closure passes;
- a novel admitted profile/distribution derives its discriminant and closure
  from recorded data and verifies without a code or allowlist edit;
- the admitted GY-DI1 profile reconstructs from the record and replays
  reproducibly.

Machine pinning, package allowlists, backend ignores and prose-only environment
descriptions are forbidden repairs.

## Artifact and replay economics — pre-run price

For this four-cycle phase the mechanism-path count and deployment-bound artifact
count are both zero: only plan companions (journals, specification and closure
basis) may move. No replay is authorized or useful before a mechanism exists.

At current HEAD, the deployment owner still resolves 96 paths (94 Python
modules plus `pyproject.toml` and `uv.lock`) and three deployment-bound frozen
artifacts: promotion, generation-cycle and confidence-ledger contracts. The
accepted GY-DI1 identities match the current tree. Chronology implementation is
likely to touch the 94-module closure and therefore provisionally prices one
reissue of all three artifacts, but this is not yet an artifact-transition
claim. Immediately before implementation replay, the owner must measure the
actual changed deployment intersection and emit the required transition
declaration; zero intersection means zero reissue.

GY-DI1 measured a 5,387-leaf deployment snapshot (67 promotion, 43 generation
cycle, 5,277 confidence ledger), 911 protected preimages / 47,532,401 bytes,
1,220.234 seconds cold, 224.767 seconds cache-hit, and 75.65 seconds for
readback. Under E11, freeze all source and all reviews first, serialize only
the shared deployment snapshot/owner scratch, run one measured replay with an
explicit timeout and uptime pair, then verify all consumers from that result.
These are the current price inputs, not a promise that timings will remain
constant.

## Draft implementation clusters — no authorization

1. **Owner-preserving environment dependency:** close GY-DEF22 at its
   Foundry/N8/N10a owner boundary, consume that identity in N12 and pass its
   research-profile, irrelevant-difference and novel-profile falsifiers.
2. **Single proof protocol and independent anchor contract:** define
   algorithm-profiled canonical commitments, append-only consistency,
   commitment heads, proof-only dispositions and offline verification over
   reusable core canonical/CAS/audit machinery. Reuse the N11 behavior, never
   its confidence scope or private ledger. Add the writer-independent
   consumer/holder contract and prove no universal envelope, authority head,
   second currentness owner or claim-history owner was introduced.
3. **Epoch producer and validity cascade:** generic regime/amendment/acquisition
   boundary resolution, unresolved scope, append-only epochs, current heads,
   N13b semantic stamp, owner-adjudicated perturbations, promotion freeze,
   certificate staleness and recipe recomputation.
4. **Controlled release adapter:** native release member/producer, immutable
   denominator, retained accepted head, verifier dispositions, denominator
   reconciliation, offline membership/consistency replay and prefix discipline.
5. **Recursive-run adapter:** production-boundary content receipt and explicit
   gap reconciliation while preserving GY-GAP5's non-blocking producer-owned
   terminal, complete-denominator reconciliation, per-root native heads/
   resolved terminals and deletion/narrowing detection.
6. **Movement composition:** exact N13b row/passport to N7 re-entry/deeper
   terminal relation and consumer projection.
7. **Surfaces and capstone verification:** audit/API/dashboard projection from
   owner artifacts, full frozen closure basis, negative/e2e semantic suite,
   owner recomputation validators and the single deployment replay.

Each cluster must be independently reviewable and end with a real
producer/artifact/bridge/consumer/verifier chain or retain an exact incomplete
label. Cluster boundaries and order may change after Cycle 4.

## Pattern pass

The active pattern set is `P01`–`P05`, `P07`–`P10`, `P12`–`P15`, `P27`–`P29`,
`P31`–`P33`, and `P35`–`P41`. Cycle 1 found P02 at the N13b and claim-lifecycle
production seams and P37/P38 at the caller-supplied epoch stamp. Its first
review also found a P38 research proxy—literal absence was not semantic-owner
absence—and corrected it by classifying every canonical owner named by the
Custody Time Model. The target pattern is shared
chronology proof semantics with family-native records, complete producers,
content-bound bridges, owner recomputation and external/audit surfaces. The
current capability labels remain those in the measured-state section; no
capability is promoted by this specification.

Cycle 2 found two further P37/P38 traps: treating an inclusion proof as proof
that every required member was submitted, and treating a declared derivation
recipe as complete while an environment/tool dependency is omitted. It also
confirms P27/P28 would be repeated by a universal event-sourcing log or a
shared native authority head. The repair is independent denominator
reconciliation plus a proof-only commitment head, and complete recipe/profile
closure before automatic revalidation.

Cycle 3 found the owner-wording trap: “one delivery lane,” “one proof
protocol,” and “one semantic authority” are three different propositions. The
first two hold; the third fails against native denominators, correction
authority, terminals and anchor custody. It also found a reuse trap: N11's
behavioral hash-chain precedent does not authorize reusing its per-problem
confidence scope. The repair is one policy-free proof protocol with native
semantic owners and writer-independent family acceptance.

## Research and revision log

| cycle | input | result | spec action |
| --- | --- | --- | --- |
| 1 | complete literal + CTM-owner census; independent architecture/census/basis reviews | proof owner absent; Decision Validity and Claim Ledger mandatory; five negative classes added | rewritten after blocking P38/label/basis findings; hypothesis only |
| 2 | transparency, bitemporal, immutable-history, revocation, provenance/recompute and scholarly-correction prior art | proof algebra fits admitted-prefix integrity; CTM reconciliation tentatively makes epoch a projection rather than a third clock; canonical denominator and authority heads stay native | rewritten with commitment/authority-head split, independently accepted anchors, GY-GAP5-attributed run receipt, recipe/profile closure and proposition/use denominators; three return reviews clean |
| 3 | strongest conditional unification versus minimal semantic-owner split; repository head/membership/correction/anchor/run-gap counterexamples | one policy-free proof protocol is the supported direction for four domains; one semantic authority is refuted; hash-chain-first is provisional and N11 owner reuse forbidden | rewritten with protocol/authority split, explicit native-head limits, anchor custody, algorithm-choice measurement and reordered clusters; first and return reviews repaired same-class deeper findings, final delta clean |
| 4 | adversarial record/design/method review | pending | delta-review until clean; freeze basis |
