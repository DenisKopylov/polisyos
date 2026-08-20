# GY-N12 Epoch Chronology Design

## Status

Final research specification for user approval. All four research cycles are
complete; the substantive Cycle-4 design delta and the superseding 128-property
closure-basis packet returned clean. Freeze takes effect only when the final
status/record delta over these exact bytes returns clean and the containing
commit is read back. No production code, governed artifact, writer, deployment-
bound artifact or generated surface is authorized by this document. User
approval is required before implementation planning.

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
- N11's scope-local CAS/hash-chain/WAL is `implemented` within that native
  claim.
- Data Forge's deterministic supplied-ref Merkle root is `implemented` as
  supplied-set identity, not completeness.
- Core security's public `ChainVerifier` is
  `implemented_but_not_orchestrated`: no source
  constructor call exists, and its supplied-segment continuity check cannot
  detect prefix/tail narrowing without an external denominator.
- The reuse decision is to extend/consolidate only those measured native
  behaviors while rejecting their scopes, heads and stores as the common owner.
  None provides family-denominator reconciliation, profile/domain isolation or
  a writer-independent accepted anchor. The common proof protocol and accepted-
  anchor chain remain `absent/unallocated`.

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
native family/scope, canonicalization/hash/signature/schema profiles,
signature, prior anchor, admission cutoff, requested native query coordinate,
witness or consumer-receipt basis, verifier provenance and admission
provenance class. At least one retained anchor crosses a custody boundary the
writer cannot rewrite. The common contract verifies that receipt; it cannot
accept its own head.

A genuine old accepted anchor remains valid for its own historical query. It
cannot satisfy a later/current query merely because its signature and prefix
are authentic. The consumer binds the requested coordinate and expected
accepted-anchor lineage, then independently reconciles that the presented
anchor reaches the required cutoff. An authentic rollback at a later
coordinate fails or returns `not_established`; it never manufactures a narrow
pass. Unknown external heads still limit any global-latest claim.

No writer-independent acceptance chain currently exists for any family:

| family | evidenced native consumer/surface | missing acceptance role and consequence |
| --- | --- | --- |
| epoch | Decision Validity consumes dependency/currentness evidence; Claim Ledger consumes admitted claim transitions | no anchor-admission bridge or independent holder; whole-history authenticity remains `absent/unallocated` and the full cluster is blocked at that claim |
| controlled release | GY-PA3 is the plan-appointed downstream consumer | no admitted anchor consumer/holder contract; PV-K07 issuance remains blocked |
| recursive run | generation-cycle owners supply terminals; Atlas/API/dashboard are projections only | no competent anchor consumer/holder; the surface cannot accept on observation |
| movement | N13b/N7 own endpoints and DS7/Atlas consumes a projection | neither endpoint ownership nor projection appoints anchor custody; full movement-history authenticity remains blocked |

These are named gaps, not future contracts smuggled into the specification.
An implementation may prove consistency relative to a supplied head, but no
family may claim whole-history authenticity until its competent consumer and
writer-independent holder are separately appointed and implemented.

The architecture inference specifies, within CTM's boundary, that an
`epoch_ref` is a content-bound fixed-semantics replay selector at explicit
native coordinates, not a third clock. Valid/effect time and transaction/
knowledge time retain their meanings; the epoch selects the complete owner-
admitted semantic-basis manifest defined below. Proof append order cannot
select semantic applicability.

The proof contract is algorithm-profiled rather than Merkle-specific.
RFC-style membership and append-only consistency are behavioral properties.
Because offline replay already carries the full native history, a full-prefix
content hash chain is a bounded provisional candidate, not a settled scale
claim. The implementation decision starts by measuring per-family cutoff-bound
member counts, canonical bundle bytes, owner latency/storage ceilings and
admitted selective-proof demand. If linear verification exceeds a ceiling or
sublinear selective proof is required, the chosen authenticated profile must
meet that measured property; a Merkle transparency tree is the currently
evidenced candidate, not the unique possible structure.

Reuse-first means extending/consolidating `core.security.ChainVerifier`'s
interior supplied-segment checks, N11's proven rollback/prefix behavior, Data
Forge's supplied-ref commitment and core canonical/CAS/signature primitives
where their contracts fit. It rejects
N11's confidence scope/private ledger, the audit segment's unanchored first
entry and the snapshot root's sorted-set semantics as chronology ownership.
Every selected profile must bind its version plus native proof domain/family/
scope into each commitment, reject unknown profiles without fallback, reject
cross-family/scope replay and satisfy the same frozen closure basis.

The complete argument, counterexamples and ownership matrix are in
`docs/superpowers/journals/2026-08-20-gy-n12-cycle-3-unification-verdict.md`.

## Family obligations

### Epoch family

Derive epoch boundaries generically from the complete resolved set of every L5
`schema_regime` interval, every applicable L3 amendment window and every
owner-admitted N13b acquisition boundary (dataset version, source watermark or
overlay epoch). The generic boundary-source denominator and semantic-facet
registry are owner-declared and free-growing; engine conditionals cannot
enumerate domains, source kinds or facet values. The authority owner resolves
at an explicit scope-native coordinate and records the complete input/basis
hashes, rule version and provenance. A new domain regime or valid novel
boundary/facet registration added through data alone changes semantics without
engine edits; malformed, unknown or unadmitted sources fail closed. Ukraine
v1/prewar and v2/wartime is the first case, never an engine enum.

An epoch identity binds the complete owner-admitted fixed-semantics manifest,
not the shorter model/rule/schema/data shorthand. Its ratified minimum facets
are model class, obligation language and declared obligation set, calibration
scope, measurement semantics, implementation semantics, equilibrium semantics,
validator version, rule logic, schema/data regime and declared interpretation.
Every registered semantic facet participates in the content identity and
predecessor decision. Changing any one while all L3/L5/data rows remain fixed
opens a new epoch and stales exactly its dependent certificates. This is a
generic manifest/registry rule, not a domain or known-facet conditional.

No applicable regime/amendment basis, or any missing, malformed, unknown or
unadmitted mandatory semantic facet, yields `epoch_scope_unresolved`, not an
assumed or partial epoch. N13b passports must bind the resolved epoch identity
and basis proof; a caller-supplied positive integer is insufficient.

“One time semantics” does not mean one scalar. N13b retains its overlay-local
append/revision coordinate as a native transaction relation, while the passport
also binds the N12-resolved semantic `epoch_ref`, complete basis and the same
owner-native valid/effect and visibility coordinates. N13b and N12 independently
recompute the identical semantic reference and basis at those coordinates; the
overlay counter cannot select it. A mismatch refuses semantic admission or
returns `not_established`. Once admitted, the acquisition boundary enters the
same epoch/staleness cascade as an L3 or L5 change.

Resolution consumes owner-native valid/effect and visibility coordinates plus
the authority context, and returns a discrete semantic reference with content
and predecessor commitments. The reference is not an independent timestamp;
maximum transaction time, receipt time or chronology position cannot select
the epoch head.

Every certificate binds its issuance epoch, complete semantic-basis manifest,
inputs, derivation recipe, authority purpose and relevant native time
coordinates. A semantic perturbation marks affected current certificates stale
or revalidation-required through Decision Validity and then flows into Claim
Ledger/lifecycle bridge for affected public claims. N12 owns the content-bound
trigger, not recipe execution: the canonical producer recorded by each derived
artifact owns recomputation, and Decision Validity consumes the resulting
certificate. If that producer/bridge is absent, the artifact remains
`absent/unallocated` or `producer_missing`; chronology cannot execute it by
projection. Historical certificates remain verifiable at their original
coordinate. Affected scopes freeze promotion immediately on an admitted
revision trigger; the decision front is revalidated to `current_valid` members
only.

`OpenWorldRisk` is not a Boolean or caller-authored severity. PolicyOS consumes
typed scope evidence signed by the competent external/deployment owner; it
does not infer actual deployment by observation. Intake resolves and content-
binds the evidence and verifier provenance—signature/presence alone remains
`institutionally_supplied` and cannot carry the gate. The N12 relation producer
compares the owner-resolved authorized-intended scope before deployment, or
actual scope after deployment, with every declared model, obligation and
calibration scope component at the same native coordinate. The deployment
lifecycle/query owner establishes which scope role is required at that
coordinate; callers cannot choose it. Once actual deployment has begun,
intended-only evidence cannot yield `within_scope`: missing actual-scope
evidence is `not_established`, while owner-proven outside actual scope is
`open_world_risk`. The content-bound result preserves each component and
composes as:
`open_world_risk` if any component is independently proven outside;
`within_scope` only if every required component is independently proven
inside; otherwise `not_established`. A supplied `low`/`false`, an unresolved
deployment scope or a missing component cannot carry the gate. Both
`open_world_risk` and `not_established` freeze promotion in the affected scope
and limit the signed claim; no generic numeric severity or unconditional
`risk <= delta` is authorized.

Arrival is not adjudication. An incident, appeal, correction, retraction,
discovered bias or other source event is advisory input. Until the canonical
owner resolves, content-binds and adjudicates it, its maximum effect is the
applicable `review_required`, `contested` or annotation band. Only the admitted
owner disposition can select `annotation_only`, `invalidate`, `reissue`,
`supersede` or `withdraw`.

Chronology never orders those values or composes raw source events. The
executable oracle is an order-independent vector keyed by exact target,
authority purpose and canonical owner. Each owner supplies one content-bound
aggregate disposition for its key. Different targets remain separate; an
`annotation_only` note may coexist with an authority-changing transition but
cannot cancel it. Conflicting aggregates for the same key yield
`contested`/`review_required` and freeze rather than a guessed maximum. Native
Decision Validity, Claim Ledger and lifecycle owners validate and apply their
own transitions.

A newly discovered obligation has a fixed cascade: challenge -> invalidate
current authority -> append a new widened-basis epoch -> recompute through the
artifact's canonical producer -> append a reissued certificate. The old
certificate and arithmetic remain historically reproducible under their own
closure epoch and declared set, while current authority is withdrawn. The
basis-driven delta cannot be projected as a better result, and neither a
same-epoch recompute nor mutation of the old certificate satisfies the rule.

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

GY-GAP3's required transcript “current head” is adjudicated here as the latest
consumer-accepted **commitment head at the requested cutoff**. It says which
declared transcript prefix was accepted; it never says a release is currently
authoritative or preferred. If a native release authority later supplies a
successor/withdrawal relation and currentness snapshot, that separate owner may
project a native release head; none is appointed by GY-GAP3. An annotation-only
append may move the transcript head without changing native release authority,
while a native authority/currentness change cannot be inferred from an
unchanged transcript head.

### Recursive-run family

Every family-native production event binds exact `DesignProblem` content,
recursive graph and cycle content identities and authority scope. Only an event
that the competent producer/lifecycle owner resolves may bind and project a
terminal. Start, receipt and custody-gap events remain members of the complete
chronology without minting terminality. The family enumerates the independently
complete native production-event denominator, orders admitted events by the
owner-native chronology relation, derives current heads per existing root from
an explicit native supersession/retry relation and projects only resolved
terminals. Append position or maximum timestamp cannot manufacture a native run
head; absent that relation, the head is unresolved rather than guessed.
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

At a bound scope/cutoff, the denominator is every N13b row both admitted in the
native overlay and bound by the canonical acquisition receipt to the exact
`DesignProblem`/cycle for consumption. N13b admission plus the producer-owned
receipt recompute eligibility outside the movement adapter; a caller filter
cannot narrow it. The movement owner reconciles each row to exactly one of: a
proved movement relation; an
endpoint-owner-proved `no_movement`; or a typed `movement_not_established` gap.
Silence is never the second case. The complete denominator, reconciliation and
relations pass through the common commitment/verifier/consumer-anchor chain.
Omitting an eligible row before composition therefore fails even when every
remaining relation is valid.

## Authority predicates

Every implementation predicate must freeze one of these provenance classes at
admission: `recomputed`, `independently_reconciled`, `consumer_asserted`,
`institutionally_supplied`, or `not_established`. Authority-grade admission
accepts only the first two. In particular:

- epoch membership is recomputed from the complete owner-admitted boundary-
  source denominator, including L5 regimes, L3 amendments and N13b boundaries,
  together with the complete mandatory semantic-facet manifest; a missing
  boundary or facet makes membership unresolved;
- every generic boundary source is resolved and admitted by its canonical
  owner; an event's declared action is never the gate predicate;
- the OpenWorldRisk producer recomputes the component-wise relation between
  the deployment-lifecycle/query-owner-required scope role, competent-owner
  evidence for that authorized-intended or actual scope, and the complete
  declared model/obligation/calibration scope; observation, caller role/
  severity and missing required-role evidence cannot become a positive;
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
- movement eligibility is independently reconciled against the complete N13b
  row denominator, and movement identity is recomputed from exact row/passport/
  run/re-entry refs;
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
   epoch, unknown proof profile, sibling/cross-family scope substitution,
   authentic-old-anchor rollback at a later query coordinate, or undeclared
   family basis.
3. **Data-only free-grow:** add a synthetic domain's new L5 regime/L3 amendment,
   a valid novel boundary-source registration and a valid novel registered
   semantic facet through data only; mutate every registered facet in turn.
   Epoch resolution and exact stale propagation change with zero engine
   enumeration/edit, while an unknown or missing facet fails closed.
4. **Contract mutation:** remove the actual decisive content/consistency
   validation while retaining field names and marker strings; the behavioral
   gate must fail.

The complete negative denominator is maintained in the separate closure-basis
artifact. It remains a candidate until the Cycle-4 delta returns clean and the
exact reviewed bytes are committed; before that point it cannot support a
completeness claim.

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
  the discriminating profile/root/distribution difference as the first
  regression case, never as a special rule;
- while holding a profile label and shaped record constant, substituting any
  incompatible distribution inside the resolved deployment closure changes the
  recomputed discriminant and fails; a second incompatible profile generated
  from data proves the predicate is closure compatibility rather than the words
  `research` or `torch`;
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

## Implementation cluster decomposition — no authorization

1. **Owner-preserving environment dependency:** the Foundry catalog/discovery
   owner closes GY-DEF22 with N8/N10a and exposes the admitted identity for N12.
   Pass known and generated incompatibility plus irrelevant-difference tests.
   N12 is only a consumer. Current state: GY-DEF22 open; this cluster is not
   executable by a chronology-local substitute.
2. **Policy-free proof profile:** extend/consolidate core canonical/CAS,
   `ChainVerifier`, N11 behavioral checks and Data Forge commitment primitives
   into algorithm/profile/domain-bound membership and consistency verification.
   Measure scale before selecting full-prefix or a sublinear profile. End in a
   persisted family-native proof and offline result explicitly relative to a
   supplied head. Current capability: `absent/unallocated`.
3. **Anchor admission and retention:** for each family, wire a competent
   consumer acceptance receipt and writer-independent holder, including
   requested-coordinate anti-rollback. This is a separate review boundary from
   proof production. All four family chains are currently
   `absent/unallocated`; the table above names the known consumers/surfaces and
   records that no holder is appointed. Whole-history claims and the full
   family closures are blocked here until that external custody decision lands.
4. **Epoch producer and validity cascade:** generic boundary and full semantic-
   facet manifest resolution, unresolved scope, append-only epochs, exact N13b
   stamp/basis reconciliation, component-wise OpenWorldRisk, owner-adjudicated
   target vectors, missed-obligation reissue, promotion freeze and Decision
   Validity/Claim Ledger bridges. N12 emits triggers; each derived artifact's
   canonical producer executes its recipe. Missing producer links retain their
   exact current labels. Current epoch/OpenWorld capability:
   `absent/unallocated`; Decision-Validity trigger: `producer_missing`.
5. **Controlled release adapter:** native release member/producer, immutable
   denominator, proof-only transcript head, verifier dispositions, denominator
   reconciliation and offline replay. GY-PA3 is the named downstream consumer,
   but PV-K07 remains blocked on Cluster 3's acceptance/holder chain. Current
   state: `absent/unallocated`.
6. **Recursive-run adapter:** first establish the live production boundary,
   then bind every family-native run event to exact problem/graph/cycle identity
   and add receipt-or-gap emission without changing producer terminality.
   Reconcile the complete event denominator, project terminals only from
   owner-resolved events, derive per-root native heads and detect deletion/
   narrowing. A bound start followed by recorder failure remains enumerable,
   mints no terminal and fails the completeness claim. The single returned
   artifact remains
   `artifact_missing`; live boundary is `not_established`; enumeration is
   `absent/unallocated`. Full authenticity also depends on Cluster 3.
7. **Movement composition:** reconcile the complete eligible N13b-row
   denominator to proved movement, owner-proved no movement or an explicit gap;
   persist exact row/passport/N7 re-entry/deeper-terminal relations through the
   common proof chain. Current state: `absent/unallocated`; full authenticity
   also depends on Cluster 3.
8. **Surfaces and capstone verification:** audit/API/dashboard projections from
   owner artifacts, the frozen negative/e2e basis, recomputing validators and
   the single deployment replay. Surfaces consume owner results and cannot
   close missing anchor custody or mint authority.

Each cluster is independently reviewable. It must end with a real
producer/artifact/bridge/consumer/verifier/surface chain or retain its exact
incomplete label and named prerequisite; “blocked” is a sequencing status, not
a stronger capability label.

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

Cycle 4 reopened sixteen distinct P40 buckets. The rewrite adds authentic-old-
anchor rollback, a complete movement denominator, owner-proven OpenWorldRisk,
full fixed-semantics identity, missed-obligation reissue, N13b/N12 stamp
reconciliation, unknown-profile/domain isolation and name-invariant GY-DEF22
tests. It resolves transcript-head meaning and target-scoped cascade
composition, routes recipe execution to canonical artifact producers, records
missing anchor principals as blockers, corrects the 4,955-file denominator and
capability labels, and completes the reuse census. Exact targets and packet
receipts are in the Cycle-4 journal; its terminal review receipt is detached to
avoid a self-referential record. The containing commit freezes these bytes only
after that final delta returns clean.

## Research and revision log

| cycle | input | result | spec action |
| --- | --- | --- | --- |
| 1 | complete literal + CTM-owner census; independent architecture/census/basis reviews | proof owner absent; Decision Validity and Claim Ledger mandatory; five negative classes added | rewritten after blocking P38/label/basis findings; hypothesis only |
| 2 | transparency, bitemporal, immutable-history, revocation, provenance/recompute and scholarly-correction prior art | proof algebra fits admitted-prefix integrity; CTM reconciliation tentatively makes epoch a projection rather than a third clock; canonical denominator and authority heads stay native | rewritten with commitment/authority-head split, independently accepted anchors, GY-GAP5-attributed run receipt, recipe/profile closure and proposition/use denominators; three return reviews clean |
| 3 | strongest conditional unification versus minimal semantic-owner split; repository head/membership/correction/anchor/run-gap counterexamples | one policy-free proof protocol is the supported direction for four domains; one semantic authority is refuted; hash-chain-first is provisional and N11 owner reuse forbidden | rewritten with protocol/authority split, explicit native-head limits, anchor custody, algorithm-choice measurement and reordered clusters; first and return reviews repaired same-class deeper findings, final delta clean |
| 4 | content-bound adversarial record/design/method review under the written P40 bucket rule | 16 distinct blocking buckets after duplicate witnesses were folded; later findings stayed in those classes; no cosmetic-only finding | rewritten across design, basis and record; substantive design and superseding 128-property basis packets clean; final status/record delta freezes only on clean receipt plus commit readback |
