---
title: INT-R1 — Open-World Impossibility and Relative Obligation Coverage
status: delivered
kind: deep-research
research_task: INT-R1
result_type: accepted_narrow_scope
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r1-obligation-coverage
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: d152565dcc11cea457dacd61fadc6e15dc3ecc86
inspection_date: 2026-08-02
authoritative_for:
  - research-level impossibility result for unconditional obligation completeness in an open world
  - formal definition of bounded completeness relative to a declared closure basis
  - separation of theorem, external assumption, empirical rule, governance judgment, and engineering convenience
  - logical interpretation of later-discovered obligations and maintained-assumption failure
may_not_use_for:
  - production implementation authorization
  - final code or wire contract
  - authority grant
  - capability claim
  - legal compliance conclusion
  - benchmark passage
  - proof that a declared source basis is legally or normatively exhaustive
  - numeric calibration of unknown-obligation risk
research_only: true
---

# INT-R1 — Open-World Impossibility and Relative Obligation Coverage

## 1. Question and notation

INT-R1 asks whether PolicyOS can prove that the obligations it checked are the obligations that
actually applied. The mathematical risk ledger is already explicit that
`P(false promotion | maintained assumptions) <= delta` depends on
`obligation_completeness` and `validator_soundness`
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:37-50`). This note isolates
what those words can and cannot mean.

Let:

- `W` be a possible institutional world;
- `a` be a protected action or PolicyOS claim under evaluation;
- `s` be the declared scope: jurisdiction, authority, population, policy domain, purpose,
  materiality/stakes, and temporal applicability;
- `t` be the declared cutoff under the adopted Custody Time Model;
- `U(W, a, s, t)` be the set of obligations that actually apply to `a` in world `W` under
  scope `s` at cutoff `t`;
- `T` be the finite inspection trace available to PolicyOS: source snapshots, queries,
  responses, receipts, verifier outputs, reviewer records, and declared unavailable sources;
- `B` be the **declared closure basis** represented in `T`: the exact source registries,
  source snapshots, competence assertions, search procedures, exclusions, and stopping rules
  selected for the claim;
- `L_v` be the declared obligation language/compiler semantics at version `v`;
- `C_v(B, a, s, t)` be the set of obligation instances derivable from `B` by `L_v` for the
  action and scope;
- `O_T` be the actual obligation-instance set compiled and checked in the trace;
- `V_j` be validator `j`, with a declared rule/version and governance record; and
- `R(W,T) = U(W,a,s,t) \ O_T` be the world-level remainder.

`U` is a semantic object, not a repository object. PolicyOS can hash and traverse `B`, `L_v`,
`O_T`, and the validator records. It cannot ordinarily enumerate `U` because the point of the
open-world problem is that unknown sources, rules, exceptions, facts, interpretations, norms,
or implementation constraints may exist.

## 2. Four different completeness predicates

Conflating the following predicates is the root defect.

### 2.1 Artifact totality

```text
ArtifactTotal(T) := every required field/object in a declared artifact schema is present,
                    traversed, and content-bound, except genuine typed exemptions.
```

This can be complete-by-construction when the schema/object graph is the actual owned source of
truth. It is the valid P29 stopping point
(`policy-engine/docs/reference/policy-design-case-failure-patterns.md:70-75`).

### 2.2 Denominator totality

```text
DenominatorTotal(T, E_v) := classes(O_T) = E_v
                            and the declared risk partition covers E_v exactly.
```

At the pinned baseline `E_v = PromotionObligationClass`, a 15-member enum. The confidence
ledger and promotion receipt implement this predicate
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:337-369`;
`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:1320-1900`).

### 2.3 Relative source/language coverage

```text
RelativeComplete(T, B, L_v) := O_T = C_v(B, a, s, t)
                               and every member of O_T received its required checks,
                               with no unresolved internal traversal or validator fault.
```

This predicate is the strongest generally checkable target for INT-R1. It is relative to the
exact basis and language named in the claim.

### 2.4 Global/world completeness

```text
WorldComplete(T, W) := O_T = U(W, a, s, t).
```

This is what an unqualified phrase such as “all applicable obligations were checked” asserts.
It is not implied by artifact totality, denominator totality, or relative source/language
coverage.

## 3. Impossibility theorem: no finite open-world trace certifies global completeness

### Theorem 1 — Open-world non-certifiability

Let `A` be any procedure that receives a finite inspection trace `T` and returns either
`world_complete` or `not_world_complete`. Assume the admissible class of worlds is open under an
**unobserved applicable-obligation extension**: for at least one trace `T` and world `W0`
consistent with `T`, there exists another world `W1` such that:

1. `W0` and `W1` produce the same trace `T` for every source, query, receipt, and check observed
   by `A`;
2. `U(W0,a,s,t) = O_T`; and
3. `U(W1,a,s,t) = O_T ∪ {o*}`, where `o*` is an applicable decisive obligation not represented
   in `T`.

Then no procedure `A` that depends only on `T` can be both:

- **sound**: whenever `A(T) = world_complete`, `O_T = U(W,a,s,t)` for every admissible world
  consistent with `T`; and
- **positively certifying**: returns `world_complete` on `T` for `W0`.

#### Proof

Because `W0` and `W1` are observationally indistinguishable to `A`, the procedure receives the
same input `T` and must return the same result in both worlds. If it returns
`world_complete`, that result is true in `W0` but false in `W1`, because `o*` is missing from
`O_T`. Soundness is violated. If it refuses to return `world_complete`, it is not positively
certifying in `W0`. Therefore a finite trace cannot soundly certify global completeness while
an indistinguishable applicable-obligation extension remains admissible. ∎

### Scope of the theorem

The theorem is deliberately modest. It does not say that completeness is metaphysically
unknowable. It says that a finite procedure cannot certify it **from the trace alone** when the
world model permits an unobserved decisive extension. A global claim becomes possible only by
adding a premise that rules out `W1`, such as:

- a competent authority supplies a genuinely exhaustive, closed, and current register for the
  exact scope;
- the domain is deliberately finite and contractually closed;
- a law or rule of recognition validly establishes a complete source hierarchy and closure rule;
- or an oracle with the needed semantic completeness is assumed.

Those are closure premises. They are not derived by the search procedure whose completeness is
in question.

### Corollary 1 — More search does not become proof of absence

Expanding `T` can discover obligations, eliminate named defeaters, and shrink the class of worlds
consistent with the trace. Unless the expansion rules out every unobserved applicable-obligation
extension, it cannot entail `WorldComplete`. Search diligence is evidence about process and
known coverage, not a proof that `R(W,T)` is empty.

### Corollary 2 — Independent review does not discharge the open world

An independent reviewer may catch omissions and provide a materially stronger basis than
self-attestation. If both producer and reviewer see the same finite trace and the same closure
basis, an obligation outside both remains indistinguishable. Independence is necessary for
P29 and validator governance; it is not sufficient for global completeness.

### Corollary 3 — A finite enum cannot establish the universe

Exact equality to `PromotionObligationClass` proves `DenominatorTotal`, not `WorldComplete`.
The enum's participation in the gate makes it a capability-gating denominator at the current
baseline, but no property of finite exact set equality rules out `o*` outside the enum.

### Corollary 4 — TTL bounds currentness, not completeness

An unexpired TTL can support the proposition “the declared sources and review were no older than
the governed interval.” It cannot support “no unknown obligation existed during that interval.”
Expiry must downgrade current usability, but non-expiry does not upgrade world coverage.

### Corollary 5 — Randomization does not remove the semantic gap

A randomized procedure has the same distribution of outputs on indistinguishable worlds `W0`
and `W1`. Any positive probability of certifying `world_complete` in `W0` creates the same
positive probability of a false certificate in `W1`, unless an external distribution over
worlds or closure assumption rules out `W1`. Randomness can allocate inspection effort; it
cannot manufacture semantic observability.

## 4. Identification limit on a numeric “unknown obligation risk”

A posterior quantity such as:

```text
P(R(W,T) ≠ ∅ | T)
```

is mathematically definable only after specifying a probability model or prior over possible
worlds, source-generation processes, discovery processes, and obligation materiality. Different
priors can produce different posteriors from the same trace. A frequentist estimate needs a
repeatable population and observable miss outcomes.

At the pinned repository baseline, the confidence registry is not an empirical population of
real positive governed promotions; its profiles are dominated by ineligible, unavailable-owner,
or deterministic routes, with only one admitted closed-constant-unit e-process
(`policy-engine/architecture/production_quality/confidence_ledger.toml:53-89`). The project
therefore lacks the historical misses and positive governed decisions needed to calibrate a
world-level miss model.

**Identification result.** INT-R1 cannot currently supply a calibrated numeric probability of
unknown-obligation absence. A number could be an explicit subjective prior used for exploration,
but it must not be projected as empirical coverage, incorporated into the δ theorem without a
new theorem, or used to turn `open_world_unresolved` into a pass.

This is an identification limitation, not a claim that future data is useless. Future operation
can measure challenger yield, time-to-discovery, source outage frequency, review disagreement,
mutation survival, TTL breach, and reissue frequency. Those observables can improve governance
and search allocation while leaving Theorem 1 intact.

## 5. Relative-coverage theorem

### Definition — Declared closure basis

A declared closure basis `B` is not merely a list of URLs. For a given `a,s,t`, it contains:

- each source family and competent producer/owner relied upon;
- the exact immutable source snapshot, query/index version, and retrieval cutoff;
- the source-to-scope applicability rule;
- the source's authority/competence assertion and its verification standing;
- required source families and declared exclusions;
- unavailable-source records and stopping rules;
- the obligation language/compiler version; and
- the provenance and review chain.

A basis may be **closed by authority** for a narrow domain, or merely **selected under a governed
stopping rule**. The envelope must distinguish those cases.

### Assumptions for a mechanically checkable result

For one envelope `E`, assume:

- **R1 — scope identity:** `a`, `s`, and `t` are explicit and stable for the check;
- **R2 — immutable basis:** every member of `B` is resolved and content-bound to a snapshot;
- **R3 — generic traversal:** the compiler enumerates every member of `B` and every applicable
  subobject by construction, with only genuine typed exemptions;
- **R4 — relative compiler adequacy:** `C_v` is sound and complete relative to the declared
  obligation language `L_v` and the semantics represented in `B`;
- **R5 — obligation binding:** every compiled obligation instance carries source, scope,
  applicability, rule, version, and materiality references;
- **R6 — validator soundness relative to the instance language:** each validator decides the
  declared predicate correctly within its stated domain;
- **R7 — independent check:** a checker sufficiently independent from the producer recomputes
  traversal, compiler/validator bindings, and the mandated mutation/metamorphic probes;
- **R8 — no unresolved internal defeater:** no known source failure, unresolved exclusion,
  compiler fault, validator fault, scope mismatch, stale basis, or material contradiction remains;
- **R9 — currentness:** the envelope has not expired and no accepted perturbation or challenge
  has suspended it; and
- **R10 — honest rider:** the public claim states its relativity and unknown remainder.

### Theorem 2 — Relative mechanical coverage

Under R1–R9, PolicyOS can prove:

```text
∀o (Derivable(o | B, L_v, a, s, t)
    → Included(o, O_T) ∧ CheckedUnderDeclaredRules(o, T))
```

and can prove that no obligation instance derivable from the declared basis and language was
silently omitted from the check trace.

#### Proof sketch

R2 and R3 make `B` a finite or effectively enumerable, immutable traversal domain. R4 defines
the exact source-to-obligation function whose range is `C_v(B,a,s,t)`. R3 and R4 establish that
the produced range is complete relative to that function. R5 provides an injective/auditable
binding from each generated obligation instance to its source and rule derivation. R6 establishes
correct evaluation relative to each declared predicate. R7 independently recomputes the bindings
and falsifies omissions or validator mutations. R8 excludes a known internal defect that would
invalidate the derivation, and R9 establishes current usability. Therefore each obligation in
the range of the declared derivation is included and checked. ∎

### What Theorem 2 does not prove

It does not prove:

```text
C_v(B,a,s,t) = U(W,a,s,t).
```

That equality requires an additional closure premise:

```text
ClosureAdequate(B,L_v,a,s,t,W) :=
  ∀o (ApplicableInWorld(o,W,a,s,t) → Derivable(o | B,L_v,a,s,t)).
```

PolicyOS can record, verify provenance for, and challenge a competent external assertion of
`ClosureAdequate`. It cannot generally mint that assertion from its own search. If no competent
closure assertion exists, the world-level remainder remains `unknown`, even when Theorem 2 is
fully discharged.

## 6. Status semantics derived from the theorems

The requested labels are **coverage assessments**, not a parallel promotion or public status
lattice. The existing per-obligation lattice already contains `satisfied`, `failed`, `unknown`,
`scope_insufficient`, and `not_applicable_data_only`
(`policy-engine/src/polisyos/pdc/_impl/gy_waist.py:248-255`), while Organizing Rule 8 forbids a
second status universe
(`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:184-186`).

### `bounded_complete`

Meaning:

```text
RelativeComplete(T,B,L_v)
and validator governance is current
and no known material internal defeater remains
and the envelope is unexpired.
```

It **does not** mean `WorldComplete`. It permits the coverage-specific blocker to be removed
only for the declared scope and basis. Every substantive obligation must still independently
map to the existing lattice, and the public δ claim must retain its relative rider.

### `known_incomplete`

Meaning: there is a concrete witness of incompleteness, such as:

- an applicable obligation omitted from `O_T`;
- a required source family not searched;
- an unresolved source or owner required by the stopping rule;
- an accepted challenge showing the compiler missed a source rule;
- a decisive exclusion without competent authorization; or
- a validator or traversal fault that makes the coverage claim false.

Mapping to the one existing lattice is consequence-sensitive:

- `failed` when the newly represented obligation is decisively violated;
- `scope_insufficient` when necessary source, owner, mandate, or applicability scope is absent;
- `unknown` when applicability or conflict remains unresolved.

For the affected protected action, promotion is blocked.

### `open_world_unresolved`

Meaning: no specific omitted obligation need be known, but the declared basis cannot support the
bounded result—because closure scope is absent, source competence is unresolved, a material
family has no owner, independent review is missing, or the remainder is too material for the
protected action.

It maps to `unknown` or `scope_insufficient` for the affected protected action. Under the
ratified S0-K06 application, the authority band fails closed while the candidate band may
continue with a typed limitation and acquisition/challenge path
(`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:164-187`).

### Non-ordering rule

The three labels are not a simple ordinal scale:

- `known_incomplete` contains stronger information than `open_world_unresolved` about at least
  one defect, but neither is “higher” or “lower” for all purposes;
- `bounded_complete` is stronger only relative to its exact basis and scope;
- a narrower `bounded_complete` envelope cannot dominate a broader
  `open_world_unresolved` envelope; and
- scope expansion, source change, expiry, or a new challenge requires a new assessment rather
  than arithmetic promotion between labels.

## 7. The honest δ claim

Let `O_E` be the obligation instances bound by coverage envelope `E`, and let `A_E` be the
maintained assumptions bound by the ledger receipt. The mathematically honest public form is:

```text
P(false promotion with respect to O_E | A_E) <= delta,
where O_E was compiled and checked relative to declared closure basis B_E,
coverage status = bounded_complete as of cutoff t_E,
and obligations outside B_E may exist.
```

A shorter public projection may say:

> Risk ≤ δ relative to the declared obligation set and maintained assumptions. The declared
> source scope, exclusions, unknown remainder, validator governance, and expiry are available
> in the linked coverage record.

The following forms are prohibited by the result:

- “PolicyOS proved that every applicable obligation was met.”
- “The policy is compliant because the δ gate passed.”
- “No unknown obligation exists.”
- “The obligation enum is universal.”
- “The probability of an omitted obligation is at most δ.”

The repository's adopted target-spec record already states that the theorem formalizes rather
than closes the hardest open problem and that its teeth are empirical
(`policy-engine/docs/system-design-decisions/policy-design-search-target-spec.md:151-165`).
INT-R1 narrows the missing premise; it does not remove it.

## 8. When a later obligation is discovered

Suppose envelope `E0`, obligation set `O0`, and receipt `P0` were valid relative to the declared
basis at cutoff `t0`. At `t1 > t0`, a challenger supplies a new applicable obligation `o*` that
was outside `O0` and materially affects the claim.

The correct semantics are:

1. `P0` remains an immutable historical statement about `O0` and its then-recorded maintained
   assumptions.
2. The discovery is evidence that the coverage assumption needed for current authority was
   false or insufficient; the current-use projection of `P0` becomes red/suspended.
3. The original bytes, trace, and historical publication are not silently edited.
4. A new basis/epoch/envelope `E1` incorporates the challenge, recompiles obligations, runs
   validators and independent checks, and either refuses, reissues, or supersedes the claim.
5. The actual external action reversal or remedy remains with the competent external owner;
   PolicyOS owns correction/withdrawal/reissue of what PolicyOS signed.

This follows the Custody Time Model's separation of receipt, verification, admission, and
publication and its rule that the canonical claim owner chooses the reaction
(`policy-engine/docs/system-design-decisions/policy-design-custody-time-model.md:1-220`). It
also preserves S0-K12: identical content cannot remain authority-valid when decisive evidence is
missing, stale, contradictory, or revoked
(`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:97-116`).

### Historical-truth proposition

A later challenge can make both of these propositions true:

- “At cutoff `t0`, PolicyOS checked every obligation derivable from declared basis `B0` and
  issued receipt `P0`.”
- “At cutoff `t1`, `P0` is not current authority because an applicable obligation omitted from
  `B0/O0` has been accepted.”

There is no contradiction. The first is a bounded historical provenance claim; the second is a
current authority-validity claim.

## 9. Where the regress defensibly stops

The anti-pattern is to add a field saying `complete: true`, then ask who verifies that field,
then add another verifier indefinitely. INT-R1 stops at different points for different
properties:

| Property | Stopping point | Nature of result |
| --- | --- | --- |
| Schema/object coverage | Generic traversal over actual owned source of truth plus genuine typed exemptions and review | Complete-by-construction |
| Coverage of declared source basis | Content-bound enumeration, generic compiler, independent recomputation, mutation/metamorphic tests | Relative theorem / benchmark evidence |
| Validator implementation behavior | Independent oracle/reperformance, version/hash binding, fault injection, change governance | Relative theorem plus empirical tests |
| Adequacy of source basis for the institution | Competent owner assertion, independent challenge, risk/stakes-based stopping rule, TTL | Governance judgment, not theorem |
| Absence of obligations outside the basis | No general stopping point in an open world | Explicit unknown remainder / impossibility result |

The regress is therefore not solved by pretending the final row is true. It is stopped honestly
by proving the rows PolicyOS can own, independently governing the rows it can evaluate, and
publishing the remainder it cannot close.

## 10. Classification of INT-R1 outputs

| Output | Classification | What may be claimed |
| --- | --- | --- |
| Theorem 1 | impossibility theorem | No finite trace certifies global completeness while an indistinguishable applicable extension is admissible. |
| Theorem 2 | relative theorem | All obligations derivable from the declared basis/language were included and checked, if R1–R9 hold. |
| `bounded_complete` semantics | design rule derived from Theorem 2 | A coverage assessment relative to exact scope/basis/version/currentness; never universal. |
| Source selection, independence, TTL, challenge, stopping rule | empirical/institutional protocol | Governed diligence and currentness; adequacy is reviewable and defeasible. |
| Mutation/metamorphic battery | benchmark protocol | Falsifies specified omission/validator faults; does not prove the fault model complete. |
| Field names, identifiers, serialization, package placement | engineering convenience / unresolved implementation | No authority until later consolidation and implementation. |
| Numeric probability of unknown remainder | blocked at current evidence state | No calibrated quantity is available from repository history. |

### Bottom line

The global claim “the checked set is the complete set of obligations that actually applied” is
**refuted as a generally certifiable PolicyOS claim in an open world**. The viable result is
narrow but useful: prove complete traversal and validation **relative to a declared, immutable,
versioned closure basis and obligation language**; independently govern the basis and
validators; carry the unknown remainder; expire and challenge the result; and fail closed only
for the affected protected action.
