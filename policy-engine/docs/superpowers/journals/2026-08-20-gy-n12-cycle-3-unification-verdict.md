# GY-N12 Cycle 3 — Unification Verdict

## Receipt, question and result

This cycle tests, rather than assumes, the proposition that one append-only
chronology owner can serve fixed-semantic epochs, controlled release families,
production recursive-cycle enumeration and exact per-row movement.

The repository evidence supports a **qualified split** as an architecture
inference, not an implemented-capability proof:

- **supported direction:** one policy-free chronology-proof protocol should be
  the single shared implementation for all four families. It owns canonical
  commitments, append-proof semantics,
  commitment heads, consistency verification, offline replay and
  mutation/narrowing detection. Four implementations of those properties would
  be P27/P28 duplication.
- **refuted by repository counterexamples:** one chronology semantic or
  authority owner cannot own the four
  native memberships, complete denominators, temporal meanings, correction
  decisions, authority heads, terminals or anchor acceptance. The families
  demonstrably disagree on those predicates.

Thus the programme's intended statement, “one primitive with four consumers,”
is the supported specification direction. The stronger statement, “one
component owns temporal truth for all four,” does not survive. GY-N12 remains
the accountable delivery lane for the shared protocol and adapters; that
accountability does not transfer authority from
Fabric/Data Forge, Lex, Decision Validity, Claim Ledger, generation-cycle or
N13b/N7 owners.

No production code, governed artifact, writer or generated surface moved in
this cycle.

## Evidence and method

The inward evidence is the complete Cycle-1 census; the outward evidence is the
proposition-complete Cycle-2 prior-art artifact. This cycle additionally read
the actual divergence points:

- CTM keeps persistence and admission family-native, assigns integrity to core
  audit/security plus family verifiers, and expressly refutes a universal
  persisted envelope
  (`policy-design-custody-time-model.md:30-35,95-107,120-138,159-174`).
- Decision Validity persists a separate currentness state, dependency-event
  history and per-lineage `head_packet_ref`
  (`scientist/validation/decision_validity.py:51-80,206-243,367`).
- Claim Ledger owns append-only claim actions and transitions
  (`scientist/evidence/claims/lifecycle.py:45-125,227-251`).
- Fabric owns assertion/correction/revocation semantics
  (`fabric/world/store/segments.py:39-47,231-242`), while Rule Evolution
  separately distinguishes unchanged logic, alias-only change and semantic
  revalidation
  (`core/contracts/rule_evolution.py:295-336,603-647`).
- A recursive run already content-binds its graph, nodes, exact
  `DesignProblem` roots and owner-derived terminals
  (`runtime/quality/recursive_generation_cycle.py:103-268`), but the only
  source-defined compile/run function returns the compiled run without durable
  enumeration (`runtime/http/services/control/generation_cycle.py:79-169`).
  A complete `src`/tests symbol census finds only that definition and one
  unit-test call, so a live production ingress/emission boundary is
  `not_established`, not inferred from the function's name or location.
  Two independent complete walkers agree: exact call-pattern text search
  returns those same two locations, while a dependency-free AST walk parsed
  all 4,954 tracked Python files under `src` and `tests` (zero unreadable),
  finding one definition and one call, the latter in the unit test. These
  source-only scanners are admissible under the declared toolchain gate because
  they import no repository/runtime dependency; they make no runtime claim.
- N11 already demonstrates a scope-local CAS/hash-chain/WAL pattern, including
  exact-prefix receipts, fork/unreachable detection and rollback detection
  (`runtime/quality/confidence_ledger.py:714-779,2056-2073,2073-2135,2180-2278`).
  Its tests delete witnessed events, rewrite or shrink a cached prefix and
  present an old valid prefix after the head advances; every case fails closed
  (`test_confidence_ledger.py:495-527,581-620,3205-3221`).
- Core security also has a generic chained audit entry and optional replica
  backends, but no family-accepted signed anchor contract or full denominator
  reconciliation
  (`core/security/audit_models.py:60-112`,
  `core/security/audit_sink.py:24-212`).

Those last two are reuse evidence, not evidence that a generic chronology
capability exists. N11's chain is owned by its non-resettable confidence-risk
scope under INT-K05. Core audit's optional fanout is neither family admission
nor writer-independent acceptance. The shared chronology protocol and accepted
anchor capability therefore remain `absent/unallocated`.

Two independent reviewers were briefed to argue opposite conclusions. The
affirmative reviewer had to construct the strongest possible shared owner; the
negative reviewer had to reduce it to a library and name the minimal split.
The architecture inference below preserves every fact on which both agreed and
resolves their terminology dispute by reserving “semantic authority” for
policy-bearing predicates.

## Strongest case for unification

For a native family (f), native scope (s), admitted basis/cutoff (k), and
ordered native member commitments (M), define:

`Hc(f,s,k) = Commit(proof_domain[f], native_scope[f,s],
basis[f,s,k], ordered_native_member_commitments)`

One implementation can derive and verify this commitment head, member
inclusion, predecessor/append consistency and old-to-new extension for every
family. This responsibility is non-cosmetic:

1. one canonicalization and proof-domain version contract;
2. one append/consistency relation and proof result vocabulary;
3. one offline verifier and bundle encoding;
4. one accepted-anchor verification contract;
5. one mutation, deletion, substitution, fork-replacement and narrowing
   falsifier suite; and
6. one explicit limit: an admitted prefix is not a complete source
   denominator and is not a native authority head.

The specification therefore requires family adapters to map native records and
supply owner decisions without reimplementing hashing, chain validation,
consistency, anchor verification or the generic mutation dispositions. If they
did, the design would be four ledgers behind a hashing facade.

All families benefit from this exact common property:

| family | native input | shared proof result |
| --- | --- | --- |
| epoch | content-bound fixed-semantic basis and predecessor relation | admitted epoch record is in the anchored append-only prefix |
| controlled release | declared family member plus verifier disposition | deletion/narrowing of the admitted controlled prefix fails |
| recursive run | receipt or explicit run-bound custody gap per production root | omission/substitution of an admitted run member fails |
| movement | exact row/passport/re-entry/run/terminal cross-reference | deletion/substitution of any committed endpoint or relation fails |

This construction uses separate proof domains and native roots. It requires no
uniform payload, status, timestamp, action enum or physical log, so it does not
rebuild the refuted `OperationalEventEnvelope`.

## Strongest case against unification

The same construction fails if “owner” is allowed to mean the semantic
authority for its inputs. Seven counterexamples are decisive.

### 1. Commitment and authority heads vary independently

Hold an admitted proof prefix constant, then admit a dependency event that
changes Decision Validity currentness: the authority head changes while the
commitment head does not. Conversely, append an annotation-only rule rename:
the commitment changes while current authority need not. A single head
predicate would be wrong in at least one direction.

### 2. Complete membership is not one predicate

Epoch membership is open and coordinate-relative over an owner-admitted,
free-growing boundary-source registry. A controlled release family is closed
only relative to its immutable declared denominator at a cutoff. Production
run membership is open over executions and begins at a launch/emission
boundary, including receipt failures. Movement is a derived join over admitted
endpoints. Identical inclusion proofs can therefore yield four different
completeness answers.

### 3. Correction vocabulary does not imply correction authority

One external correction signal can legitimately become a Fabric correction,
an annotation-only rule alias, Decision Validity revalidation, a Claim Ledger
reissue/withdrawal, or no authority change. A common owner choosing the
reaction would bypass canonical owners. Only the immutable relation vocabulary
can be consolidated.

### 4. Authenticity needs another custody principal

A transcript writer cannot establish whole-history authenticity by accepting
its own head. Replacing the history plus every writer-held anchor must fail.
The accepting consumer and at least one retained holder must sit outside the
writer's mutation authority. That is a real custody role, not an optional
field in the shared proof.

### 5. INT-K05 forbids a parent risk scope

Confidence remains keyed per `DesignProblem`. A family declaration may
project over existing roots but may not merge, reset or replace them. The
existing N11 hash chain is therefore a behavioral precedent, never the storage
or identity owner for epochs, releases, runs or movement.

### 6. CTM requires native persistence and coordinates

Fabric/Data Forge, Lex, Decision Validity, Claim Ledger and the N13b overlay
have materially different stores and temporal roles. Copying them into a
chronology store creates a parallel world. Requiring them to populate a common
event payload recreates the rejected universal envelope.

### 7. GAP5 separates terminal truth from custody completeness

The recursive producer owns its terminal. Recording is additive and
non-blocking. Suppressing the durable chronology receipt must leave the
terminal unchanged while making chronology completeness `not_established`
and exposing a run-bound gap. A monolithic owner would tend either to make
receipt success a terminal gate or to lose the unreceipted run.

These counterexamples refute a single semantic authority. They are compatible
with, but cannot by themselves prove the eventual adequacy of, a single proof
protocol while that protocol remains `absent/unallocated`.

## Seam adjudication

| seam | fact | verdict |
| --- | --- | --- |
| heads | all families can have a commitment head; native authority heads differ and movement need not have one | share commitment proof only; never infer native currentness |
| membership | inclusion is common; eligibility and complete denominators differ | share commitments; reconcile denominators in family owners |
| open versus closed | every claim is exact only for a declared native scope and cutoff; future/external universes may remain open | bind cutoff/basis and emit limitations |
| PV-K02 | current status can change without deleting authentic history | append correction/status relations; never rewrite proof history |
| INT-K05 | existing per-problem roots are constitutive | include root identity in proof domain; no parent or global risk scope |
| CTM | semantic order and coordinates are native; proof append order is transaction/integrity order only | opaque commitments, sparse refs, family-native persistence |
| anchor | acceptance is a family-consumer authority predicate | common contract verifies; family consumer accepts; independent holder retains |
| recorder failure | terminal remains producer-owned while chronology becomes incomplete | receipt-or-gap boundary plus independent denominator |
| movement | exact relation has no independent causal authority or required native head | commit relation; consume endpoint-owner facts |

## Final ownership decomposition

The accountable GY-N12 lane delivers the common protocol and the four adapters,
but the capability graph has these real semantic owners:

| owner | retained semantics |
| --- | --- |
| Fabric/Data Forge and Lex | native valid/transaction time, source admission, legal publication/effect and corrections |
| GY-N12 epoch resolver — `absent/unallocated` | content-bound `epoch_ref`, complete boundary-source reconciliation and semantic predecessor/applicability |
| Decision Validity — `implemented` | certificate/packet currentness, affected lineage, staleness and lineage heads |
| Claim Ledger plus lifecycle bridge | public claim history and reissue/supersession/withdrawal transitions; bridge remains `implemented_but_not_orchestrated` |
| GY-N12 controlled-release adapter — `absent/unallocated`; GY-PA3 consumer | declared family, required denominator, native release disposition/head and prefix issuance input |
| generation-cycle producer plus GY-N12 run adapter | producer-owned run/terminal; separately, receipt-or-gap enumeration and native run lineage/head |
| N13b/N7 plus GY-N12 movement adapter | endpoint evidence and same-cycle re-entry stay with N13b/N7; N12 binds the exact relation |
| core audit/security plus competent family consumer | canonical integrity/signature mechanics; consumer accepts and a writer-independent holder retains the anchor |

Anchor acceptance is not currently implemented for any of the four families.
Core audit/security is reusable machinery, not proof of independent acceptance.
Until the writer-independent consumer/holder chain exists, whole-history
authenticity is `not_established`.

## Shared protocol boundary

The shared contract may carry only:

- proof-domain and canonicalization profile versions;
- family identifier and immutable native scope/root reference;
- declared-basis reference and cutoff semantics supplied by the family owner;
- native-member reference, content commitment and opaque native relation refs;
- proof append index/predecessor commitment, explicitly non-semantic;
- commitment head, previous accepted commitment head and consistency proof;
- verifier identity/provenance and proof-only disposition;
- accepted-anchor receipt and limitation state.

It may not carry or decide:

- a mandatory wall-clock or universal temporal-role bundle;
- native member eligibility or complete denominator;
- legal effect, source validity or semantic applicability;
- correction action, currentness, publishability or release disposition;
- recursive terminality or causal “deeper” movement;
- native authority head; or
- anchor acceptance on the writer's own assertion.

## Proof algorithm and reuse decision

The semantic contract is algorithm-profiled, not Merkle-specific. RFC-style
inclusion and consistency are required **properties**. For the first offline
reproducible transcript, a full-prefix content hash chain is the bounded
provisional default because:

1. offline replay already needs the complete native records and basis;
2. N11 has behavioral evidence for exact-prefix, rollback, fork and deletion
   detection;
3. core canonical hashing, CAS and signature verification are reusable; and
4. this research phase has no admitted family scale or selective-proof demand
   measurement that could justify a more complex tree or public-log service.

A hash-chain profile pays (O(n)) offline verification and carries the full
prefix. Before implementation chooses the profile, measure each family's
cutoff-bound member cardinality, canonical bundle bytes, owner latency/storage
ceiling and whether any admitted consumer requires selective proof without the
full transcript. A Merkle profile becomes required if full replay exceeds an
owner ceiling or an admitted consumer requires sublinear selective membership/
consistency proofs. Both profiles must satisfy the same behavioral closure
basis; an algorithm name, root field or successful exit code is never the
property.

This is reuse of proven predicates, not reuse of N11's private owner. The first
implementation cluster must extract or build the smallest generic proof
surface over `core.canon`, CAS and audit verification without importing
epoch/release/run/movement state into the confidence ledger.

## Unification falsifiers

The qualified verdict is invalid if any implementation does any of the
following:

1. requires a uniform native payload, timestamp, status, action or physical
   log;
2. uses commitment position/head to select applicability, terminality,
   publishability or current authority;
3. derives completeness from included leaves rather than a family-owner
   reconciliation;
4. replaces existing roots with a global or parent scope;
5. lets adapters reimplement proof/consistency algorithms;
6. claims whole-history authenticity without a writer-independent accepted
   anchor;
7. lets a production run complete invisibly to both a recoverable receipt and
   an independently complete gap denominator;
8. lets the proof protocol adjudicate “deeper terminal” semantics; or
9. requires family-specific reinterpretation inside the common consistency
   verifier.

The semantic-owner split would be falsified only if a policy-free component
could independently derive member eligibility, complete denominators, native
heads and correction/terminal decisions from native records. The repository
shows the opposite. The shared-protocol architecture direction would be
falsified if one of the four could not express
deletion/substitution/narrowing as the same commitment-consistency property
without leaking family policy. No such case was found in the scoped
repository/prior-art evidence; only implementation and the frozen behavioral
basis can establish the capability.

## Capability and pattern pass

No Cycle-1 label is promoted. The common proof protocol, accepted anchors,
epoch resolver, controlled-release transcript, run enumeration and movement
composition remain `absent/unallocated`. The authoritative recursive-run
state split is:

| object/predicate | evidence | state |
| --- | --- | --- |
| single returned `RecursiveGenerationCycleRun` artifact | real constructor returns the content-bound value; no persistence | `artifact_missing` |
| live production ingress/emission boundary | complete source census finds a definition and unit-test call but no production caller | execution/predicate status `not_established` |
| cross-run chronology/enumeration | no admitted chain; GY-GAP5 registration | `absent/unallocated`; deficits `artifact_missing + bridge_missing` |

Retaining only the source-defined function and unit-test call cannot promote
the boundary row or change the enumeration row. N13b remains
`implemented_but_not_orchestrated` with a `bridge_missing` production seam;
the epoch-to-Decision-Validity event remains `producer_missing`.

The decisive pattern findings are:

- **P27/P28:** one shared proof implementation prevents four integrity ledgers;
  family-native persistence prevents a parallel temporal world.
- **P37/P38:** an included member, maximum append position, supplied epoch,
  recorder success or writer-owned anchor cannot stand in for the property the
  gate needs.
- **P31/P32:** use one intake/verifier for content-bound proof artifacts and
  reject self-attested anchor/admission evidence.
- **P35/P36:** family set claims still require complete native denominators;
  proof adjacency supplies no authority.
- **P40:** the affirmative and negative arguments are two depths of one owner-
  boundary class, not two implementation findings. Cycle 4 reviewers receive
  the explicit bucket rule before review.

## Cycle 3 rewrite and first-review receipt

The design specification was rewritten from a provisional “chronology semantic
owner” into the qualified protocol/authority split. The closure basis adds
head-orthogonality, policy-free proof, no-N11-owner-reuse, algorithm-profile
and writer-independent-anchor falsifiers. The implementation clusters are
reordered around the common protocol, then family adapters and independent
anchor consumers.

The P40 bucket rule was sent in writing before three independent delta reviews:
every finding had to be `NEW_CLASS` or
`SAME_CLASS_ONE_LEVEL_DEEPER`, name `design`, `record` or
`research_method`, and state blocking/cosmetic.

- Architecture review returned clean.
- `SAME_CLASS_ONE_LEVEL_DEEPER / design / blocking`: the end-to-end chain
  omitted family source-denominator reconciliation.
- `SAME_CLASS_ONE_LEVEL_DEEPER / design / blocking`: the chain placed an
  independently accepted anchor before the competent family consumer that must
  produce the acceptance receipt.
- `C3-METHOD-01 / SAME_CLASS_ONE_LEVEL_DEEPER / research_method / blocking`:
  the record promoted an architecture inference to “proved” and selected a
  hash-chain default without a declared scale/consumer denominator.
- `C3-RECORD-01 / SAME_CLASS_ONE_LEVEL_DEEPER / record / blocking`: a
  source-defined compile/run function was called the production front door,
  and returned-run `artifact_missing` was conflated with absent production
  enumeration.
- `C3-RECORD-02` / `C3-RETURN-RECORD-01` /
  SAME_CLASS_ONE_LEVEL_DEEPER / record / blocking`: two return reviewers found
  the same remaining escape—live-boundary `not_established` was grouped with
  cross-run `absent/unallocated`. Under P40 this is one finding/class, not two.

The rewrite widens the common capability chain, restores consumer-produced/
independently retained anchor order, labels the verdict as an architecture
inference, adds the algorithm-choice measurement falsifier and separates
the returned-run artifact, not-established live boundary and absent
enumeration in one authoritative inventory with a no-caller falsifier.

Return review then closed clean:

- the basis reviewer found both denominator/anchor-order findings closed and
  no adjacent escape;
- the method/record reviewer reproduced the dual 4,954-file source census,
  accepted the inference/algorithm falsifiers, found the remaining three-state
  summary escape, and returned clean after the inventory repair; and
- the architecture reviewer independently found the same state escape, then
  returned clean after the same repair and found no remaining collapse across
  the journal, design or closure basis.

Cycle 3 is complete and delta-clean. The closure basis remains deliberately
unfrozen until Cycle 4.
