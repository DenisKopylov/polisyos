---
title: INT-R1 — Open-World Impossibility and Conditional Relative Obligation Inclusion
status: delivered
kind: deep-research
research_task: INT-R1
result_type: accepted_narrow_scope
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r1-amendment
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: 978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d
inspection_date: 2026-08-03
amended_after_audit: research/int-r1-independent-audit@887bce985e6797c1a94dba24f33c6424ab09c0a5
authoritative_for:
  - premise-relative impossibility result for unconditional obligation completeness where an unseen decisive extension remains admissible
  - conditional relative-inclusion theorem over a declared closure basis and obligation language
  - separation of deductive premises from governed evidence and admissibility conditions
  - research-level per-scope closure-premise, status, and later-discovery semantics
may_not_use_for:
  - production implementation authorization
  - final code or wire contract
  - authority grant
  - capability claim
  - current issuance of bounded_complete
  - legal compliance conclusion
  - benchmark passage
  - proof that compiler semantic completeness or validator soundness holds
  - proof that a declared source basis is legally or normatively exhaustive
  - numeric calibration of unknown-obligation risk
research_only: true
---

# INT-R1 — Open-World Impossibility and Conditional Relative Obligation Inclusion

## 1. Question, notation, and amendment

The confidence ledger states that
`P(false promotion | maintained assumptions) <= delta` depends on
`obligation_completeness` and `validator_soundness`
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:37-50`). This note separates four
questions that the same word “completeness” can conceal:

1. Did PolicyOS traverse every object/field in an owned artifact?
2. Did it represent every member of a declared denominator version?
3. Did it include and check every obligation derivable under a declared source basis and language?
4. Did it find every obligation that actually applied in the institutional world?

The independent audit confirmed the open-world argument only as a premise-relative result and
required the original relative theorem to be narrowed. Compiler semantic completeness and
validator soundness are not discharged by the theorem; they are assumptions. Independent review,
mutation, no-known-defeater review, and currentness are governed evidence/admissibility conditions,
not logical truth-generators.

Let:

- `W` be a possible institutional world;
- `a` be the protected action or claim;
- `s` be the exact jurisdiction, authority, population, domain, and materiality scope;
- `p` be purpose and audience;
- `t` be the declared Custody Time Model cutoff tuple;
- `U(W,a,s,p,t)` be the obligations actually applicable in world `W`;
- `T` be the finite trace available to PolicyOS: sources, queries, snapshots, unavailable-source
  records, receipts, verifier outputs, review records, and challenges;
- `B` be the declared closure basis represented in `T`;
- `L_v` be the declared obligation language and source-to-obligation compiler semantics at
  version `v`;
- `C_v(B,a,s,p,t)` be the obligations derivable from `B` under those declared semantics;
- `O_T` be the obligation instances actually compiled and checked;
- `V_j` be validator `j` with its declared predicate/domain and governance record; and
- `R(W,T) = U(W,a,s,p,t) \ O_T` be the world-level remainder.

`U` is a semantic object, not a repository object. PolicyOS can hash and traverse `B`, `L_v`,
`O_T`, and governance records. It cannot generally enumerate `U` unless a separately evidenced
closure premise makes that universe finite and authoritative for the exact scope.

## 2. Four distinct predicates

### 2.1 Owned artifact totality

```text
ArtifactTotal(T) :=
  every required field and nested object in the actual owned schema/object graph
  is present, generically traversed, and content-bound,
  except genuine typed exemptions.
```

This may be complete-by-construction under the repository's P29 stopping rule
(`policy-engine/docs/reference/policy-design-case-failure-patterns.md:70-75`).

### 2.2 Declared denominator totality

```text
DenominatorTotal(T,E_v) :=
  classes represented by the receipt equal the declared denominator version E_v,
  and the declared risk partition covers E_v exactly.
```

At the inspected source, `E_v` is the 15-member `PromotionObligationClass`. The ledger and N9
implement this predicate
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:337-369`;
`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:1320-1900`). The enum is a
legitimate governed denominator for this proposition. Its docstring's word “Universal” must not
be read as a theorem that `E_v` is the world obligation universe.

### 2.3 Conditional relative inclusion and checking

```text
RelativeIncludedChecked(T,B,L_v) :=
  under explicit compiler and validator semantic assumptions,
  every obligation derivable from B under L_v is represented in O_T
  and evaluated under its declared predicate/rule.
```

This is the strongest positive formal target established by INT-R1. Its truth is conditional on
semantic assumptions stated below.

### 2.4 World completeness

```text
WorldComplete(T,W) := O_T = U(W,a,s,p,t).
```

This is the proposition asserted by “all applicable obligations were checked.” Neither artifact
totality, denominator totality, nor conditional relative inclusion entails it.

## 3. Theorem 1 — premise-relative open-world non-certifiability

Let `A` be a procedure that receives finite trace `T` and attempts to issue a positive
`world_complete` certificate. Assume the admissible class of worlds is open under an
**unobserved applicable decisive-obligation extension**: for at least one `T` there are worlds
`W0` and `W1`, both admissible and consistent with the trace, such that:

1. `W0` and `W1` produce the same `T` for every source, query, receipt, and check observable to
   `A`;
2. `U(W0,a,s,p,t) = O_T`; and
3. `U(W1,a,s,p,t) = O_T ∪ {o*}`, where `o*` is applicable, decisive, and absent from `T`.

Then no trace-only `A` can be both:

- **sound** — whenever it certifies `world_complete`, the certificate is true for every
  admissible world consistent with `T`; and
- **positively certifying** — it certifies `world_complete` for `W0` on that trace.

### Proof

`A` receives identical input in `W0` and `W1`. A deterministic procedure returns the same output
in both. If it returns `world_complete`, it is false in `W1`, violating soundness. If it refuses,
it does not positively certify `W0`. A randomized procedure has the same conditional output
distribution in both worlds; any positive probability of a certificate in `W0` is the same
positive probability of a false certificate in `W1`, unless an added distribution or closure
premise removes `W1`. Therefore no finite trace positively and soundly certifies global
completeness while the unseen decisive extension remains admissible. ∎

### 3.1 What the theorem establishes

It establishes an indistinguishability consequence **conditional on the extension premise**. It
prevents an inference from a finite trace to world closure while the same trace remains compatible
with an omitted decisive obligation.

### 3.2 What the theorem does not establish

It does not establish that every real PolicyOS scope is open. The premise does the substantive
work and must be disposed of per scope. A competent exhaustive register, deliberately finite
contractual domain, valid source hierarchy/closure rule, or semantically complete oracle may rule
out `W1` for an exact boundary. INT-R1 does not establish that any actual scope has such a premise;
it specifies how to state and challenge one.

## 4. Per-scope closure-premise disposition

Every attempted protected use must carry exactly one research-level disposition for the exact
`a,s,p,t` proposition:

### 4.1 `closed_by_competent_basis`

Required meaning:

```text
A competent external owner, with verified mandate for the exact scope/purpose/interval,
asserts an exhaustive register or valid closure semantics that entails:
  every applicable obligation in the declared domain is represented by B/L_v.
```

Minimum evidence includes owner identity/mandate, exact jurisdiction/population/domain/purpose,
source hierarchy or register identity, effective interval/cutoff, treatment of exceptions and
conflicts, version/change rules, currentness, provenance, and challenge route.

Effect: the evidence may defeat the unseen-extension premise **only within that boundary**. It
does not make obligations satisfied, validate the compiler/validators, grant promotion, or close
adjacent scopes.

### 4.2 `open_under_unseen_extension`

Required meaning: there is a positive, evidenced reason the admissible domain permits a decisive
obligation outside the observed trace—for example distributed institutional practice, incomplete
source ownership, unbounded affected-person claims, or evolving interpretation without a
competent exhaustive register.

Effect: Theorem 1 applies. The unknown remainder remains explicit and the affected protected
action fails closed.

### 4.3 `closure_not_established`

Required meaning: neither a competent closure premise nor a sufficiently evidenced positive
openness characterization is available; closure evidence is missing, stale, contradictory,
unresolved, or outside the claimant's competence.

Effect: no world-completeness certificate is available. This is not evidence that no obligation
applies. The affected action fails closed while candidate work may continue with a typed
limitation under S0-K06
(`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:164-187`).

### 4.4 Scope non-transfer rules

- Closure for one jurisdiction does not close another.
- Closure for one authority or source family does not close informal practice or other owners.
- Closure for one purpose/audience does not automatically close a stronger public claim.
- Closure for one effective interval/cutoff does not survive source, law, mandate, or scope change.
- A narrower closed basis cannot silently support a broader action.
- A producer's self-description of completeness is not a competent closure premise.

## 5. Consequences of Theorem 1

### 5.1 Search quantity is not closure

More search can discover obligations, resolve named gaps, and shrink the set of worlds compatible
with `T`. Quantity alone does not prove absence. Exhaustive traversal of a valid finite closure
basis is different: the **closure premise**, not merely the amount of search, rules out the
extension.

### 5.2 Independent review is not world closure

Independent review may detect omissions and is stronger than producer self-attestation. If all
reviewers share the same finite basis or omitted source, the unseen obligation remains. Review is
admissibility evidence, not an independent proof that the world is closed.

### 5.3 Enum equality is internal totality

Exact equality to `PromotionObligationClass` proves `DenominatorTotal`, not `WorldComplete`.
The enum's legitimate use as a versioned gate denominator does not imply universal external
coverage. GY-DEF5 narrows the repository defect to the universal claim, not the enum itself
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:7`).

### 5.4 TTL is currentness, not completeness

An unexpired TTL supports a bounded freshness proposition under a declared rule. It does not prove
that no obligation was unknown during the interval. Event-triggered revocation, retroactivity,
accepted challenge, or source-authority change may suspend the result before calendar expiry.

### 5.5 Randomization is not observability

Random allocation of search effort cannot distinguish worlds that remain observationally
identical. A Bayesian prior or external distribution adds assumptions; it does not derive
identification from `T` alone.

## 6. Identification limit on numeric unknown-obligation risk

A quantity such as:

```text
P(R(W,T) != empty | T)
```

requires a specified model/prior over worlds, source generation, discovery, materiality, and
misses. Different priors may produce different answers from the same trace. A frequentist
estimate requires a repeatable population with observable misses.

At the pinned W12.D/G5 snapshot there are 13 typed blockers, zero grounded conversions, and zero
useful-design credit. The live confidence registry is a configuration of proof profiles, not a
history of obligation misses. Therefore the repository currently provides no empirical base rate
for unknown-obligation absence. Any present numeric “coverage probability” would be authored, not
calibrated.

Future challenger yield, discovery latency, source outages, reviewer disagreement, mutation
survival, TTL breach, and reissue frequency may improve governance and search allocation. They do
not retroactively identify the current world remainder.

## 7. Declared closure basis

A basis `B` is not a URL list. For the exact `a,s,p,t`, it includes:

- every required source family and competent producer relied upon;
- immutable source snapshots, query/index versions, and retrieval cutoffs;
- source-to-scope applicability rules;
- authority/competence assertions and verification standing;
- required-family manifest and declared exclusions;
- unavailable-source records and stopping rules;
- obligation language/compiler identity and semantics;
- CTM roles and cutoffs;
- provenance and review chain; and
- one per-scope closure-premise disposition.

A basis selected under a governed stopping rule remains different from a basis closed by competent
authority. The former may support disciplined analysis but does not defeat the open-world premise
by itself.

## 8. Theorem 2 — Conditional Relative-Inclusion Theorem

### 8.1 Deductive premises

For a fixed envelope and exact `a,s,p,t`, assume:

- **D1 — fixed proposition:** action, jurisdiction/authority/population/domain, purpose, audience,
  materiality, and temporal cutoffs are explicit and stable;
- **D2 — immutable basis:** every member of `B` is resolved and content-bound;
- **D3 — generic traversal:** every basis member and applicable nested object is enumerated by
  construction, with only genuine typed exemptions;
- **D4 — compiler semantic completeness:** `C_v` is sound and complete relative to declared
  language `L_v` and the semantics represented in `B`;
- **D5 — obligation identity/binding:** each derived obligation binds source, rule, scope,
  applicability, predicate, version, and materiality; and
- **D6 — validator semantic soundness:** each `V_j` correctly decides its declared predicate
  within its declared domain.

### 8.2 Conclusion

Under D1–D6:

```text
forall o:
  Derivable(o | B,L_v,a,s,p,t)
    -> Included(o,O_T) and CheckedUnderDeclaredRules(o,T).
```

No obligation derivable under the assumed basis/language semantics is silently omitted from the
check trace.

### 8.3 Proof sketch

D1 fixes the proposition. D2 makes its basis replayable. D3 establishes total visitation of the
owned basis. D4 supplies the semantic source-to-obligation range `C_v(B,...)`; because D4 assumes
completeness relative to those semantics, every derivable obligation is produced. D5 makes each
produced instance auditable and distinct. D6 supplies correctness of each declared predicate
result. Therefore every member of the declared derivation range is included and checked. ∎

### 8.4 Exact limit

The theorem does **not** prove D4 or D6. D4 contains the source-to-obligation semantic completeness
needed for the inclusion conclusion. D6 contains validator correctness. They are the maintained
semantic assumptions whose reliability requires separately admitted evidence. The theorem also
does not prove:

```text
C_v(B,a,s,p,t) = U(W,a,s,p,t).
```

That equality requires `closed_by_competent_basis` evidence adequate for the exact domain. Where
closure is open or unestablished, world remainder remains unknown even if D1–D6 are true.

## 9. Governed admissibility protocol — separate from the theorem

A protected action may rely on the conditional result only when a governed protocol supplies
current evidence for the assumptions and fails closed when evidence is insufficient.

### 9.1 Independence evidence

The protocol must evidence—not merely name:

- organizational independence;
- implementation independence from the primary compiler/validator path;
- source/data independence sufficient to reperform from immutable sources rather than producer
  outputs;
- oracle independence, including frozen expected results not generated by the implementation;
- economic/incentive conflicts and mitigations; and
- temporal independence after rule, source, or implementation change.

Shared parsers, indexes, ontologies, generators, rule libraries, and validator code must be
disclosed. A second function name importing the same faulty component is not independent.

### 9.2 Reperformance and fault evidence

An independent path must reperform source-to-obligation derivations, verify instance/source/rule
bindings, run the mandatory omission and validator-fault battery, and retain surviving mutant and
common-mode dispositions. Mutation adequacy is relative to a fault model; it does not prove D4 or
D6 universally.

### 9.3 No-known-defeater and currentness

No known material source, scope, exclusion, compiler, validator, conflict, independence,
provenance, or closure-premise defeater may remain. Governance records, source competence, basis,
and review must be current and unsuspended. “No known defeater” is not “no possible defeater.”

### 9.4 Public rider

The public/machine statement must expose relativity, semantic assumptions, basis/scope, closure
disposition, exclusions, remainder, cutoff, governance standing, challenge state, and expiry.
Compression cannot turn “relative to B/L_v” into bare “complete.”

### 9.5 Logical status of the protocol

Independent review, mutation, governance, and currentness are evidence and admissibility
criteria. They may falsify the assumptions or justify bounded reliance under a governed standard.
They do not logically manufacture compiler completeness or validator soundness once those
properties are the theorem's assumptions.

## 10. Current capability consequence

At `978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d`:

- no canonical `ObligationCoverageEnvelope` exists;
- no canonical `ValidatorGovernanceRecord` exists;
- no admitted independent source-to-obligation checker/scorer exists;
- S0-GAP-02 remains unresolved;
- no complete N9/N11/N12/claim bridge consumes coverage standing;
- OM-01 cannot execute because GY-GAP1 leaves obligation-instance identity/aggregation absent;
- no INT-R1 benchmark has been implemented or run; and
- current status remains `semantic_test_missing`.

Therefore the repository cannot issue `bounded_complete`. The honest current attempted-use result
is `open_world_unresolved`, mapped to existing `unknown` or `scope_insufficient`; protected action
and current public positive δ claim remain false. Atlas DS17 treats this as the steady state, not
a loading placeholder
(`policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:7`).

## 11. Coverage assessments as inputs to one lattice

### 11.1 Future `bounded_complete`

Research meaning only:

```text
D1-D6 hold for exact B/L_v/a/s/p/t;
required governed evidence is admitted and current;
no known material internal defeater remains;
and the closure-premise disposition/remainder is disclosed.
```

It means conditional relative inclusion, not `WorldComplete`. It removes only an additional
coverage blocker. It cannot mark a substantive obligation `satisfied`, grant compliance, or mint
promotion. No current producer may issue it.

### 11.2 `known_incomplete`

A concrete witness exists: an omitted applicable obligation, missing required source, unauthorized
material exclusion, compiler/traversal fault, validator unsoundness, collapsed conflict, or
accepted material challenge. The witness maps consequence-sensitively to existing `failed`,
`scope_insufficient`, or `unknown`. The affected protected action is blocked.

### 11.3 `open_world_unresolved`

No concrete omission need be known, but protected reliance cannot be bounded because closure is
unestablished/open, source competence or required ownership is unresolved, a material family is
unavailable, independence is absent/common-mode, or the unknown remainder is material. It maps
to existing `unknown` or `scope_insufficient`. Candidate work may continue only with the limitation
carried forward.

### 11.4 Non-ordering

These assessments are not a total order or authority states. A narrow future
`bounded_complete` cannot dominate a broader unresolved scope. Scope, purpose, audience, source,
rule, version, or time change requires a new assessment, not arithmetic promotion between labels.

## 12. Honest δ statement

For a hypothetical future admitted envelope `E`, obligation set `O_E`, and assumptions `A_E`, the
maximum honest form is:

```text
P(false promotion with respect to O_E | A_E) <= delta,
where O_E is relative to declared B_E and L_v;
compiler semantic completeness and validator soundness remain maintained assumptions;
closure disposition, exclusions, unknown remainder, challenge state, cutoff, and expiry
are disclosed.
```

Prohibited forms include:

- “PolicyOS proved every applicable obligation was found or met.”
- “The policy is compliant because the δ gate passed.”
- “The probability of an omitted obligation is at most δ.”
- “The 15-class enum is the universal obligation set.”
- “An unexpired coverage record proves no unknown obligation exists.”

At the current repository, no positive public statement may add `coverage = bounded_complete`.

## 13. Later-discovered obligation or validator fault

Suppose old envelope `E0`, obligation set `O0`, and receipt `P0` were issued relative to basis
`B0` at cutoff `t0`. At `t1`, a material missed obligation or validator fault is admitted.

Required semantics:

1. `E0/P0` remain immutable historical statements about old inputs and then-recorded assumptions.
2. Current reliance becomes red because a maintained assumption is breached or unsupported.
3. Original bytes and history are not silently edited.
4. The canonical claim owner suspends, withdraws, refuses, revalidates, or opens reissue.
5. A new epoch/basis/obligation set/validator evidence produces a new envelope/receipt if reissue
   is attempted.
6. Current public notice links the old and replacement/suspension records.
7. External legal, administrative, financial, or service reversal remains with competent owners.

Both statements may be true:

- “At `t0`, PolicyOS checked every obligation derivable under declared `B0/L_v`.”
- “At `t1`, that receipt is not current authority because a material omitted obligation or
  validator fault was admitted.”

This preserves the Custody Time Model and S0-K12
(`policy-engine/docs/system-design-decisions/policy-design-custody-time-model.md:1-220`;
`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:97-116`).

## 14. Five-row stopping taxonomy

| Property | Stopping point | Nature of result |
| --- | --- | --- |
| Owned schema/object coverage | Generic traversal over the actual owned source of truth, genuine typed exemptions, and review | complete-by-construction |
| Declared-basis source/obligation inclusion | Immutable basis, generic traversal, explicit compiler semantic assumption, source/rule/instance binding | conditional relative-inclusion theorem; empirical benchmark evidence is separate |
| Validator implementation behavior | Declared formal predicate where available, independent oracle/reperformance, version/hash binding, fault injection, change governance | semantic assumption supported/falsified by formal or empirical evidence |
| Institutional adequacy of selected basis | Competent owner assertion where available, independent challenge, stakes-based stopping, source competence, TTL | governance judgment, not theorem |
| Absence of obligations outside basis | No general finite stopping point while an unseen decisive extension remains admissible | explicit unknown remainder / premise-relative impossibility |

The regress stops mechanically where PolicyOS owns the actual source of truth. It does not stop by
asserting that the external world is complete.

## 15. Output classification

| Output | Classification | Standing |
| --- | --- | --- |
| Theorem 1 | premise-relative impossibility theorem | valid only where unseen decisive extension remains admissible |
| Per-scope closure disposition | governance/evidence protocol | required for every protected use; no actual scope is declared closed by this research |
| Theorem 2 | conditional relative-inclusion theorem | D4/D6 remain assumptions |
| Independent review/mutation/currentness | governed admissibility protocol | evidence, not logical truth; current complete chain missing |
| `bounded_complete` semantics | future research design rule | currently unavailable |
| `known_incomplete` / `open_world_unresolved` | evidence assessments feeding existing lattice | fail-closed for affected protected action |
| Typed artifacts/challenge/reissue | design pattern | no canonical schema/owner/capability established |
| OM-01 | benchmark protocol | conceptually required; blocked on GY-GAP1 |
| Independent benchmark passage | empirical evidence | blocked on S0-GAP-02 and absent implementation |
| Numeric unknown-remainder probability | unidentified at current evidence state | no calibrated quantity |

## 16. Bottom line

INT-R1 did not discharge `obligation_completeness` or `validator_soundness`. It established:

- a valid conditional impossibility result wherever an observationally invisible decisive
  extension remains admissible;
- a per-scope requirement to evidence closure, openness, or unestablished closure;
- a conditional inclusion theorem relative to assumed compiler and validator semantics;
- a separate governed protocol for making those assumptions inspectable, challengeable, and
  fail-closed; and
- append-only correction and replay semantics when an assumption later fails.

At the pinned repository, independence and the complete capability chain are absent. Current
`bounded_complete` issuance is unavailable; `open_world_unresolved` is the honest standing.
