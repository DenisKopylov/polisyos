---
title: INT-R1 — Bounded, Checkable, Honest Completeness in an Open World
status: delivered
kind: deep-research
research_task: INT-R1
result_type: accepted_narrow_scope
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r1-amendment
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: 978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d
inspection_date: 2026-08-03
amended_after_audit: research/int-r1-independent-audit@0893a739e4739a6cd31dd95bc0b88526e1ff29ae
authoritative_for:
  - audited research conclusion for INT-R1 at the pinned repository baseline
  - premise-relative impossibility result for an unconditional open-world obligation-completeness certificate
  - conditional relative-inclusion result over a declared closure basis and obligation language
  - research-level governance, challenge, lifecycle, artifact, and benchmark handoff for consolidation
may_not_use_for:
  - production implementation authorization
  - final code or wire contract
  - package placement or canonical owner appointment
  - authority grant
  - capability claim
  - current issuance of bounded_complete
  - legal compliance conclusion
  - benchmark passage
  - evidence that an independent checker, scorer, or governance producer exists
  - unconditional claim that all applicable obligations are known
  - probability bound on the existence of an unknown obligation
  - change to the current obligation denominator, validator, promotion gate, or risk budget
research_only: true
---

# INT-R1 — Bounded, Checkable, Honest Completeness in an Open World

## Executive Finding

**Result: `accepted_narrow_scope`, amended after independent audit.**

Three qualifications are part of the result, not caveats around it.

First, PolicyOS cannot certify global obligation completeness from a finite trace **only where the
admissible world class remains open under an observationally invisible decisive-obligation
extension**. That premise does the substantive work. It must be disposed of separately for every
protected action, scope, purpose, audience, and cutoff as one of:

- `closed_by_competent_basis` — a competent owner supplies an evidenced exhaustive basis for the
  exact scope, interval, and purpose;
- `open_under_unseen_extension` — the source/world model admits a decisive obligation outside the
  observed trace; or
- `closure_not_established` — neither closure nor a positive openness characterization has been
  adequately evidenced.

Only the first defeats the impossibility premise, and only within its stated boundary. The other
two preserve an explicit unknown remainder and fail closed for the affected protected action.
INT-R1 therefore does **not** claim that every PolicyOS domain is necessarily open, or that any
particular domain is closed.

Second, the strongest positive formal result is a **Conditional Relative-Inclusion Theorem**:
under an explicitly fixed basis and language, generic traversal, compiler semantic completeness
relative to the declared basis semantics, and validator soundness relative to declared
predicates, every obligation derivable under those semantics is included and checked. Compiler
semantic completeness and validator soundness are assumptions in that theorem. INT-R1 does not
prove them. Independent reperformance, mutation testing, governance, no-known-defeater review,
and currentness are a separate governed admissibility protocol: they provide fallible evidence
for relying on the assumptions and must turn current use red when they fail; they do not create
semantic truth by themselves.

Third, at `978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d`, **PolicyOS cannot issue
`bounded_complete`**. The independent source-to-obligation checker/scorer, validator-governance
producer, coverage-envelope producer, and N9/N11 bridge do not exist as a complete governed
capability. S0-GAP-02 remains an unresolved independent-oracle dependency. A producer-filled
`independence_record` cannot substitute for actual organizational, implementation, source, and
oracle separation. The honest current steady state is therefore `open_world_unresolved`, mapped
into the one existing fail-closed lattice for the affected action. Atlas DS17 records the same
standing: unresolved is a settled refusal, not a loading placeholder
(`policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:7`).

The requested future assessment `bounded_complete` remains a research-defined possibility with
one narrow meaning:

> Complete inclusion and checking of obligations derivable from the declared immutable basis and
> obligation language for the exact scope and cutoff, under named semantic assumptions and a
> separately admitted governed-evidence protocol, while obligations outside the basis may exist.

It never means world completeness, legal compliance, substantive satisfaction, or promotion. The
public risk statement must remain:

```text
P(false promotion with respect to the declared obligation set
  | maintained assumptions) <= delta
```

and must expose the basis, scope, language/rule versions, exclusions, unknown remainder,
validator-governance standing, cutoff, challenge state, and expiry. `delta` is not a probability
that no obligation was omitted.

A concrete missed obligation or validator fault yields `known_incomplete`. A missing closure
premise, material source/owner/scope gap, absent independent check, or materially common-mode
review yields `open_world_unresolved`. These are evidence assessments feeding the existing N9/PDC
lattice, never a second authority lattice. The authority band fails closed; candidate work may
continue only with the limitation carried forward explicitly
(`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:164-187`).

A later-discovered obligation does not silently edit the old proof. It creates append-only
challenge and perturbation records, suspends or withdraws current reliance through the canonical
claim owner, and requires a new epoch, basis, obligation set, checks, and reissue. The old receipt
may remain historically reproducible relative to its old inputs while becoming unusable as
current authority.

The independent audit also narrowed two repository-facing conclusions. The 15-member
`PromotionObligationClass` is a legitimate governed, versioned denominator vocabulary for a
declared compiler version. The defect is treating it—or its word “Universal”—as the boundary of
all world obligations. The enum must not be opened, dissolved, or made dynamically discoverable
by this research; GY-DEF5 targets the universal claim, not the live waist contract
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:7`). The mandatory
same-class decisive-instance deletion fixture `OM-01` is conceptually valid but is **blocked on
GY-GAP1**, because the current `PromotionObligationRecord` has no obligation-instance identity or
pre-class aggregation layer. This research does not pretend that fixture is runnable today.

Supporting artifacts remain separated for auditability:

- [repository census and anchor ledger](int-r1/repository-census-and-anchor-ledger.md);
- [external primary-source transfer ledger](int-r1/external-primary-source-ledger.md);
- [formal impossibility and conditional inclusion note](int-r1/open-world-impossibility-and-relative-coverage.md);
- [artifact and state-machine sketch](int-r1/artifact-and-state-machine-sketch.md);
- [benchmark and edge-case specification](int-r1/benchmark-and-edge-case-fixtures.md); and
- [post-audit amendment ledger](int-r1/amendment-ledger.md).

## 1. Task And Project Fit

### 1.1 Exact question and the false production claim

INT-R1 asks what honest completeness claim survives when unknown legal, normative, measurement,
implementation, or other obligations may exist. The ledger already states that its inequality is
conditional on `obligation_completeness` and `validator_soundness`
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:37-50`). The task is not to
improve the arithmetic. It is to prevent this false inference:

> “The δ gate passed; therefore every applicable obligation was considered and the policy is
> compliant.”

Five propositions must remain separate:

1. the risk budget partitions the declared class denominator;
2. the receipt contains every declared class;
3. every obligation derivable under declared basis semantics was included and checked;
4. the selected basis and semantics are adequate for the institutional scope; and
5. no other applicable obligation exists in the world.

The repository strongly checks 1 and 2. INT-R1 states a conditional result for 3. Items 4 and 5
require a separately evidenced closure premise or remain institutional/open-world questions.

### 1.2 Why research first

A premature implementation could encode one of four failures: a universal closed-world enum; an
always-unresolved system that paralyses narrow closed scopes; a producer self-attestation; or a
parallel status/authority lattice. Repository instructions instead require boundary discipline,
explicit limitations, and governed contribution checks (`AGENTS.md:20-49`, `:68-96`). The
contributor contract supports architecture, quality, test, and documentation governance for
changes; it does not itself locate or appoint every canonical authority owner
(`policy-engine/CONTRIBUTING.md:84-139`, `:177-201`).

### 1.3 Four-way boundary verdict

| Plane | Verdict | PolicyOS responsibility | Boundary retained |
| --- | --- | --- | --- |
| PolicyOS statement of what it searched, received, compiled, checked, excluded, and could not resolve | **OWN** | Make that statement reproducible, content-bound, time-bounded, audience-aware, challengeable, and correctable while PolicyOS's signature stands. | Ownership is of the custody statement, not of the external obligation source. |
| External law, adjudication, institutional rule, measurement standard, implementation requirement, affected-person claim, or competent closure assertion | **INTEGRATE** | Receive, verify, purpose-admit, bind to scope/time, preserve provenance, and react when evidence changes. | PolicyOS does not become legislature, court, regulator, measurement authority, or delivery operator. |
| Unadmitted interpretations, horizon signals, source-owner succession signals, or challenger allegations before verification | **OBSERVE** | Use as acquisition or review triggers; preserve candidate/limitation posture. | Observation and transport mint neither obligation authority nor a pass. |
| Making law, deciding final external legal effect, administering cases, issuing legally effective notice, paying, delivering, or reversing external acts | **OUT_OF_SCOPE** | Correct PolicyOS claims and emit typed evidence to competent owners. | External execution remains external. |

This applies the ratified custody boundary
(`policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md:52-145`).

## 2. Current Repo Baseline

### 2.1 Pinned baseline and material changes

The amendment is pinned to `978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d`. The research
inspection baseline remains `d152565dcc11cea457dacd61fadc6e15dc3ecc86`; the later pinned
commit contains the delivered research, independent audit, and downstream registration of the
audit findings. The historical Stage-0 baseline remains
`4813b49f6ce14e8debf3aaea096f0967d38d9768`.

The ratified Stage-0 custody kernel and adopted Custody Time Model are load-bearing additions over
the historical baseline. They require band-sensitive fail-closed behavior, no authority by
observation or projection, evidence currentness, bounded passage, distinct receipt/verification/
admission/publication times, and owner-controlled reaction
(`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:43-116`,
`:164-212`; `policy-engine/docs/system-design-decisions/policy-design-custody-time-model.md:1-220`).

### 2.2 Denominator correction: 15, not 14

The supplied orientation said 14 classes. The pinned source has 15, including
`VALUE = "value"` (`policy-engine/src/polisyos/pdc/_impl/gy_waist.py:218-235`). The correction
is retained because it demonstrates why a denominator must be derived from source rather than
trusted from prose. `VALUE` was already present at the historical baseline; this is not recent
growth.

The confidence ledger enforces an exact partition over those classes, rejects duplicate or
missing class membership, requires weights to sum to one, and content-binds the split and
maintained assumptions (`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:337-369`,
`:500-1010`). N9 validates the exact declared denominator and makes mismatch a refusal
(`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:1320-1900`). These checks prove
internal totality relative to the declared version, not completeness of the external world.

### 2.3 Rule-12 disposition: legitimate denominator, defective universal interpretation

Organizing Rule 12 explicitly permits governed vocabularies, schemas, statuses, ports, and rule
versions while forbidding hand-maintained enumerations used as substitutes for an open typed
capability path
(`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:200-222`).
The correct use-sensitive disposition is:

| Use of `PromotionObligationClass` | INT-R1 disposition |
| --- | --- |
| Versioned coarse class vocabulary, routing key, budget stratum, or declared receipt denominator | **Legitimate governed vocabulary.** Gate participation does not remove Rule 12's exemption. |
| Exact totality proof for one declared compiler/denominator version | **Legitimate internal proof.** It proves equality to that version only. |
| Evidence that all applicable world obligations are represented | **Unsupported and defective interpretation.** Exact equality to an owned enum does not close the world. |
| A hard boundary that demonstrably prevents an actual source-derived obligation from representation or challenge | **Potential Rule-12 defect requiring an actual witness.** INT-R1 did not establish such a witness. |
| Choice among adding a class, extension family, instance layer, or another representation | **Not decided by INT-R1.** |

Accordingly, this research neither orders nor licenses a change to the enum. GY-DEF5 records a
claim defect in the docstring's “Universal” wording; it explicitly says the enum must not be
opened or dissolved (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:7`).

### 2.4 Current capability reality

| Capability slice | Standing at the pinned repository |
| --- | --- |
| δ arithmetic, event chain, spend, and conditional clause | `implemented` |
| Exact totality relative to the 15-class denominator | `implemented_relative_to_enum` |
| World-level obligation discovery | `producer_missing` |
| `ObligationCoverageEnvelope` | `contract_missing` |
| `ValidatorGovernanceRecord` | `contract_missing` |
| Independent source-to-obligation checker/scorer | `producer_missing`; S0-GAP-02 unresolved |
| Obligation-instance layer needed by OM-01 | `missing`; registered as GY-GAP1 |
| Mutation/metamorphic battery | `semantic_test_missing` |
| Coverage/governance to N9/N11 bridge | `bridge_missing` |
| Challenge-to-claim reaction chain | `bridge_missing` / pattern only |
| Public conditional chip | `consumer_waiting`; DS17 renders unresolved as current steady state |
| Current `bounded_complete` issuance | **unavailable** |

The aggregate INT-R1 capability is research-only/contract-only. A typed assumption is not its
discharge; a planned chip is not a producer; a field named independence is not independent work.

At the pinned W12.D/G5 proving-ground snapshot, **13 cases remain typed blockers, with zero
grounded conversions and zero useful-design credit**. This is a statement about that pinned
snapshot, not an exhaustive claim about every experimental execution in repository history.
There is no empirical base rate of missed obligations from positive governed promotions.

### 2.5 Reuse-first path

The narrow handoff is to preserve the PDC coarse vocabulary and existing statuses; let N9 remain
the substantive obligation/promotion consumer; bind any later coverage/governance references to
N11 without a second risk ledger; use formal-invariant, assurance-case, evidence-spine, claim-
registry, acquisition-planner, N12/CTM, and Atlas owners for their existing roles; and leave the
source-basis producer and independent scorer unresolved until consolidation. Research appoints no
new canonical owner.

## 3. External Research Baseline

External literature is used only for bounded transfer. Full references and non-transfer limits
are in [external-primary-source-ledger.md](int-r1/external-primary-source-ledger.md).

### 3.1 Normative systems

Alchourrón and Bulygin's *Normative Systems* (Springer-Verlag, 1971, ISBN 0-387-81019-6) is
retained as bibliographic orientation to the legal-theory tradition of normative gaps and
relative system closure. The cited open catalog record verifies the work, not the original
report's detailed page-level attribution. Those details are therefore not load-bearing here. The
formal INT-R1 result stands on its own definitions and indistinguishability argument. The only
transfer retained is the modest orientation that any claim of formal completeness must declare
the universe and closure rule to which it is relative; that statement is not used as proof that
PolicyOS has found every real obligation.

### 3.2 Relative completeness

Cook, “Soundness and Completeness of an Axiom System for Program Verification,” DOI
`10.1137/0207005`, with corrigendum DOI `10.1137/0210045`, supplies the formal shape of
completeness relative to declared semantics. It does not prove that PolicyOS's language captures
the institutional world. The qualification identifies the dependency; it does not discharge it.

### 3.3 Open/closed-world reasoning

W3C RDF Semantics and SHACL support two bounded points: absence is not falsity, and conformance is
to a supplied graph/rule set. Circumscription makes a minimization/default assumption explicit.
None proves that an explicit closure assertion is true. Closure must be scoped, attributable,
versioned, time-bounded, and defeasible.

### 3.4 Safety, assurance, audit, testing, and anytime validity

STPA, IEC 31010, and HSE guidance support systematic, stakes-sensitive diligence, not exhaustive
obligation proof. SACM/GSN and defeater practice make claims, assumptions, evidence, and challenge
visible, but cannot prove no unidentified defeater exists. PCAOB AS 1105/1215 and GAO-24-106786
support sufficiency-versus-appropriateness, reperformance, independence, contradictions, and
append-only post-report work as institutional analogies, not legal standards for PolicyOS.
Mutation testing (DOI `10.1109/C-M.1978.218136`) and NASA/TM-2001-210876 support adequacy relative
to a fault/structural model; they do not prove the model complete. Ramdas et al., DOI
`10.1214/23-STS894`, supports anytime-valid inference within a specified model; it cannot discover
an omitted obligation or make a semantically wrong validator sound.

### 3.5 External-baseline conclusion

No inspected field provides a theorem that every obligation in an open institutional world has
been found. The common defensible pattern is to declare scope/basis/semantics/fault model, prove
mechanical properties relative to them, govern reliance independently, preserve unknowns and
defeaters, expire and challenge the result, and prohibit relative passage from being projected as
universal.

## 4. Result

### 4.1 Conditional impossibility result and per-scope disposition

Let `T` be the finite trace available for protected action `a`, scope `s`, purpose/audience `p`,
and cutoff `t`. Let `O_T` be the obligations compiled and checked and `U(W,a,s,p,t)` the
obligations actually applicable in world `W`.

Assume the admissible world class is open under an unobserved decisive extension: there are
worlds `W0` and `W1` producing the same `T`, with:

```text
U(W0,a,s,p,t) = O_T
U(W1,a,s,p,t) = O_T ∪ {o*}
```

where `o*` is applicable, decisive, and unobserved. A trace-only procedure receives identical
input in both worlds. A positive world-completeness certificate is false in `W1`; uniform refusal
does not positively certify `W0`. Therefore no finite trace can both soundly and positively
certify global obligation completeness while the extension world remains admissible.

This is a **conditional indistinguishability lemma**, not a theorem that all PolicyOS scopes are
open. Every actual use must carry one closure-premise disposition:

| Disposition | Required evidence | Formal consequence | Protected-use consequence |
| --- | --- | --- | --- |
| `closed_by_competent_basis` | competent owner; mandate; exact scope/purpose/interval; exhaustive-register or valid closure semantics; version/currentness; change and challenge route | may rule out the unseen-extension premise for that exact boundary | allows consideration of the conditional inclusion result; grants no promotion by itself |
| `open_under_unseen_extension` | positive reason the source/world model permits a decisive unseen extension | impossibility lemma applies | unknown remainder remains; affected action fails closed |
| `closure_not_established` | closure evidence absent, unresolved, contradictory, stale, or insufficient | no world-completeness certificate available | affected action fails closed; candidate work may continue with limitation |

Search volume, randomization, independent repetition over a shared basis, exact enum equality, and
an unexpired TTL do not independently supply the missing closure premise. They may improve process
evidence while the external remainder remains open.

### 4.2 Conditional Relative-Inclusion Theorem

For a declared immutable basis `B` and obligation language/compiler semantics `L_v`, let
`C_v(B,a,s,p,t)` be the obligations derivable under those semantics.

#### Deductive core

Assume:

- **D1 — fixed proposition:** action, scope, purpose, audience, and CTM cutoffs are explicit;
- **D2 — immutable basis:** every basis member is resolved and content-bound;
- **D3 — generic owned-basis traversal:** all basis members and nested objects are visited with
  only genuine typed exemptions;
- **D4 — compiler semantic completeness assumption:** the compiler is sound and complete
  relative to the declared language and basis semantics;
- **D5 — obligation binding:** every derived obligation binds source, rule, scope, applicability,
  version, predicate, and materiality; and
- **D6 — validator semantic soundness assumption:** each validator correctly decides its declared
  predicate within its declared domain.

Then:

```text
for every o derivable from B under L_v,
o is included in the checked obligation set and evaluated under the declared rules.
```

This is a conditional inclusion result. D4 already contains the semantic source-to-obligation
adequacy needed for inclusion, and D6 already contains validator correctness. **INT-R1 does not
prove D4 or D6.** It makes them explicit, content-bound, reviewable, challengeable, and capable of
turning current use red. It also explicitly denies:

```text
C_v(B,a,s,p,t) = U(W,a,s,p,t).
```

That equality requires a separately evidenced closure premise.

### 4.3 Governed admissibility protocol

A protected action may rely on the conditional theorem only after a separate governed protocol
supplies evidence that is admissible for the stakes and fault classes:

1. actual organizational, implementation, source/data, oracle, incentive, and temporal
   independence is evidenced and common-mode dependencies are disclosed;
2. an independent source-level reperformance and validator oracle test the named properties;
3. mutation and metamorphic probes falsify decisive omission and validator-fault classes;
4. no known material source, scope, compiler, validator, conflict, independence, or provenance
   defeater remains;
5. governance, source competence, basis, and review are current and unsuspended;
6. the closure-premise disposition is explicit; and
7. the public/machine rider preserves relativity, assumptions, remainder, cutoff, and expiry.

These are evidence and admission criteria, not logical truth-generators. A passing test supports
reliance only against its declared fault model. A failed or unavailable criterion refuses current
use; it never silently degrades to a pass.

### 4.4 Current issuance standing

At the pinned repository, the protocol cannot complete. No admitted independent coverage
checker/scorer, governance producer, envelope producer, or gate bridge exists. Consequently:

```text
current bounded_complete issuance = unavailable
current default for an attempted protected use = open_world_unresolved
existing lattice effect = unknown or scope_insufficient
protected action allowed = false
current public green delta claim allowed = false
```

This is a current capability refusal, not a promise that a value will later be produced.
S0-GAP-02 is a dependency, not a metadata field that the producer can self-populate.

### 4.5 The three research-defined assessments

`bounded_complete` is a **future governed assessment only**. It may be considered only when the
conditional theorem's fixed/mechanical premises and the separately admitted evidence protocol
are satisfied for an exact scope, and when either a competent closure premise is evidenced or the
public remainder remains explicitly limited as required by the use. It means relative inclusion;
it never means world completeness. It removes only a coverage-specific blocker and cannot set a
substantive obligation to `satisfied` or mint promotion.

`known_incomplete` requires a concrete witness: a missed applicable obligation, omitted required
source, unauthorized material exclusion, compiler/traversal omission, validator shown unsound,
suppressed conflict, or accepted material challenge. It maps consequence-sensitively to existing
`failed`, `scope_insufficient`, or `unknown` and blocks the affected action.

`open_world_unresolved` applies when bounded reliance is not supportable without needing a
specific omission witness—for example closure not established, competent source ownership
unresolved, a material source family unavailable, independence materially common-mode, or the
remainder too material. It maps to existing `unknown` or `scope_insufficient` and carries the
limitation into candidate work.

The labels are not a total order and are not persisted authority states. Scope expansion, source
change, rule change, new purpose/audience, expiry, or challenge creates a new assessment.

### 4.6 Honest δ statement

For hypothetical future governed envelope `E`, with obligation set `O_E` and maintained
assumptions `A_E`, the maximum honest statement is:

```text
P(false promotion with respect to O_E | A_E) <= delta,
where O_E was compiled relative to declared basis B_E and language L_v;
compiler and validator semantic adequacy remain maintained assumptions;
closure-premise disposition, exclusions, unknown remainder, challenge standing,
cutoff, and expiry are disclosed.
```

Current PolicyOS cannot append `coverage assessment = bounded_complete` because that assessment
is not issuable. `delta` never bounds the probability that `O_E` omitted a world obligation.

### 4.7 Regress stopping taxonomy

| Property | Defensible stopping point | Classification |
| --- | --- | --- |
| Owned schema/object coverage | Generic recursive traversal over the actual owned source of truth, genuine typed exemptions, and review | complete-by-construction |
| Declared-basis source/obligation inclusion | Immutable basis, generic traversal, explicit semantic assumptions, source-to-obligation binding | conditional relative-inclusion theorem |
| Validator behavior | Formal predicate evidence where available, independent oracle/reperformance, version binding, fault injection, and change governance | semantic assumption plus empirical/formal evidence |
| Institutional adequacy of the selected basis | Competent owner assertion where available, independent review/challenge, stakes-based diligence, stopping rule, and TTL | governance judgment |
| Absence of obligations outside the basis | No general finite stopping point while unseen extension remains admissible | explicit unknown remainder / conditional impossibility |

This stops P29 recursion for mechanical properties PolicyOS owns without pretending the external
world is one owned object graph.

### 4.8 Classification of outputs

| Element | Classification | Honest standing |
| --- | --- | --- |
| Indistinguishable-world argument | premise-relative impossibility theorem | valid where unseen decisive extension remains admissible |
| Declared-basis inclusion | conditional theorem | valid under named semantic assumptions; those assumptions are not proved here |
| Independent review, mutation, currentness, no-known-defeater | governed admissibility protocol | evidence for reliance; fallible and unimplemented as a complete chain |
| Envelope, governance record, challenge, perturbation, reissue | design pattern | research sketch only |
| OM-01 and validator mutations | benchmark protocol | OM-01 blocked on GY-GAP1; no benchmark run |
| Exact fields, IDs, serialization, package path | engineering convenience / unresolved | no canonical standing |
| Probability of unknown remainder | blocked at current evidence state | no calibrated quantity exists |

## 5. Counterexamples And Failure Modes

| Mechanism | Adversarial case | Unsafe conclusion | Required reaction |
| --- | --- | --- | --- |
| Per-scope closure disposition | A national register is exhaustive for national rules, but a competent municipal rule applies. | “The register closes the whole action.” | Closure does not extend beyond its owner, scope, interval, and purpose; unresolved or known-incomplete for the local scope. |
| Declared basis | Every listed source was searched, but the required-family manifest omitted local practice. | “All declared sources were searched, therefore complete.” | Basis adequacy remains a governance premise; carry unknown or known gap and block affected use. |
| Compiler semantic assumption | Compiler generically traverses every source object but maps a nested exception to no obligation. | “Traversal totality proves semantic completeness.” | D4 unsupported; proof unusable; mutation/reperformance must turn red. |
| Validator soundness | Validator treats unresolved district evidence as satisfied. | “Typed output proves correctness.” | `known_incomplete`; validator governance suspended; current use false. |
| Independent review | Reviewer calls the same parser/compiler/validator. | “Two components agree.” | Record common mode; `open_world_unresolved`; no current `bounded_complete`. |
| Envelope | Producer fills every diligence field and signs its own assessment. | “Hashed self-attestation is independent evidence.” | P29 failure; actual independent reperformance required. |
| Enum totality | A decisive and nondecisive obligation share a coarse class; decisive instance is absent. | “All 15 classes are present.” | Class totality proves only declared denominator totality; instance comparison is needed, currently blocked by GY-GAP1. |
| TTL | Envelope is unexpired when a retroactive obligation is published. | “Fresh means complete.” | Event trigger suspends current use; append-only review/reissue. |
| Closure by budget | Search stops because budget is exhausted in a rights-bearing scope. | “Reasonable effort closes the world.” | Budget is a limitation unless a competent rule permits closure; otherwise unresolved. |
| Conflict | Two competent obligations require incompatible acts. | “Discovery complete means satisfiable.” | Preserve both and route conflict; no silent priority. |
| Unavailable owner | Facility owner cannot be verified; candidate supplies an estimate. | “No contradiction means pass.” | Candidate firewall; scope insufficient or unresolved. |
| Partial success | Two districts pass, third is unknown; UI displays “mostly complete.” | “Majority implies bounded complete.” | Whole-scope claim blocked; narrower scope needs new identity and envelope. |
| Challenge | Producer rejects a material challenge as release-blocking noise. | “Triage closes merits.” | Independent merits review and retained evidence. |
| Late discovery | Old arithmetic still recomputes for old set. | “Old public claim remains current.” | Historical receipt retained; current assumption standing red; suspend/reissue. |
| Public compression | Backend says relative; public chip says complete. | “A shorter label is harmless.” | Projection fails; remove green claim until qualifier/remainder/expiry are visible. |
| Mutation suite | Oracle is generated by the compiler under test. | “100% killed mutants proves coverage.” | Benchmark invalid as self-oracle; S0-GAP-02 unresolved. |

## 6. Benchmark Or Fixture Proposal

### 6.1 Standing and oracle rule

The benchmark is a research protocol. No benchmark was implemented or run; current standing
remains `semantic_test_missing`. Expected obligations must be authored from an immutable source
corpus by an independent path, frozen before execution, and never generated from the compiler
under test. The scorer and common-mode rules remain dependent on S0-GAP-02.

### 6.2 OM-01 decision: blocked on GY-GAP1

The mandatory property is to delete one decisive obligation **instance** while its source remains
and another instance keeps the same coarse class populated, so class totality stays green but the
authority claim turns red. The current N9 representation creates one
`PromotionObligationRecord` per `PromotionObligationClass`; the record carries
`obligation_class` and `gate_id` but no obligation-instance identity or instance-to-class
aggregation layer. Therefore the selected amendment disposition is:

```text
OM-01 standing = prototype_blocked_on_instance_model
blocking dependency = GY-GAP1
```

A later implementation must provide, without this research freezing a wire schema:

1. a source-derived pre-aggregation obligation-instance collection;
2. a semantic instance key binding source, rule, scope, time, predicate, and version;
3. an aggregation bridge from multiple instances to the existing class-level N9 result; and
4. an independent comparison point between the frozen expected source-to-instance set and the
   implementation output before class aggregation.

Until GY-GAP1 closes, no agent may claim OM-01 is runnable or that the mandated omission
benchmark has passed. The fixture still defeats **class-counting, marker-presence, and generic
accessibility-token checks that do not bind district-level source semantics**. No claim is made
about an undefined arbitrary semantic keyword oracle.

### 6.3 Validator fault and red semantics

`VM-01` mutates a decisive validator to return satisfied for a known negative candidate. An
independent predicate or sealed expected result must detect the fault. “δ proof red” requires:

```text
protected_action_allowed = false
current_public_claim_allowed = false
```

plus a witnessed maintained-assumption breach, existing-lattice `failed`/`unknown`/
`scope_insufficient`, suspension or withdrawal, revalidation/reissue, and immutable historical
replay. A backend red report with a still-green promotion or public chip is benchmark failure.

### 6.4 Metamorphic and edge suite

The suite must preserve these relations: source order does not change semantics; duplicate
evidence does not increase authority; adding an unsatisfied decisive obligation cannot improve
the result; removing a decisive instance while its source remains turns current use red; scope
expansion cannot reuse an envelope; narrowing needs a new identity; TTL expiry cannot upgrade;
identical bytes from an unverified source do not preserve authority; later discovery keeps
historical replay stable while suspending current use; conflicts remain explicit; loss of a
competent owner degrades standing; candidate self-description cannot replace admitted evidence;
and removing the public rider fails projection.

Required edge fixtures remain: happy path; missing decisive obligation; late discovery after
publication; validator later found unsound; conflicting obligations; owner unavailable; degraded
mode; partial success; rollback/suspension/reissue; and historical replay at a declared cutoff.

## 7. Artifact Contract Sketch

These are typed research sketches, not canonical owners, package decisions, or wire contracts.
The detailed forms are in [artifact-and-state-machine-sketch.md](int-r1/artifact-and-state-machine-sketch.md).

### 7.1 `ObligationCoverageEnvelope`

```python
class ObligationCoverageEnvelope(TypedDict):
    schema_name: Literal["ObligationCoverageEnvelope"]
    schema_version: str
    envelope_id: str
    envelope_content_hash: str

    scope: ScopeDescriptor
    protected_action: str
    purpose: str
    audience_classes: tuple[str, ...]

    closure_premise_disposition: Literal[
        "closed_by_competent_basis",
        "open_under_unseen_extension",
        "closure_not_established",
    ]
    closure_assertion_ref: str | None
    closure_assertion_owner_ref: str | None
    closure_authority_scope: str | None
    closure_valid_interval: str | None
    closure_challenge_route_ref: str

    closure_basis_content_hash: str
    searched_sources: tuple[SourceSearchEntry, ...]
    required_source_family_manifest_ref: str
    exclusions: tuple[DeclaredExclusion, ...]
    unknown_remainder: tuple[UnknownRemainder, ...]

    obligation_language_ref: str
    obligation_language_version: str
    compiler_ref: str
    compiler_version: str
    compiler_content_hash: str
    compiled_obligation_set_ref: str
    compiled_obligation_set_hash: str
    traversal_receipt_ref: str

    validator_governance_record_refs: tuple[str, ...]
    independent_review_ref: str | None
    independence_evidence_refs: tuple[str, ...]
    mutation_receipt_ref: str | None
    metamorphic_receipt_ref: str | None

    coverage_assessment: Literal[
        "bounded_complete",
        "known_incomplete",
        "open_world_unresolved",
    ]
    assessment_reason_codes: tuple[str, ...]
    known_material_defeater_refs: tuple[str, ...]

    source_effect_cutoff: str | None
    policyos_receipt_time: str
    verification_time: str | None
    purpose_scoped_admission_time: str | None
    policyos_publication_time: str | None
    review_due_time: str
    expires_at: str
    expiry_rule_ref: str

    active_challenge_refs: tuple[str, ...]
    perturbation_event_refs: tuple[str, ...]
    supersedes_envelope_ref: str | None
    public_rider: str
    authoritative_for: tuple[str, ...]
    may_not_use_for: tuple[str, ...]
    research_only: bool
```

No current producer may issue this as `bounded_complete`. A later admission rule must verify
actual independence evidence rather than accept producer-populated strings.

### 7.2 `ValidatorGovernanceRecord`

```python
class ValidatorGovernanceRecord(TypedDict):
    schema_name: Literal["ValidatorGovernanceRecord"]
    schema_version: str
    governance_record_id: str
    governance_record_content_hash: str

    obligation_language_ref: str
    rule_ref: str
    rule_version: str
    compiler_ref: str
    compiler_version: str
    validator_ref: str
    validator_version: str
    independent_checker_ref: str | None

    rule_owner_ref: str
    compiler_owner_ref: str
    validator_owner_ref: str
    independent_checker_owner_ref: str | None
    change_approver_ref: str
    incident_response_owner_ref: str

    organizational_independence_evidence_ref: str | None
    implementation_independence_evidence_ref: str | None
    source_oracle_independence_evidence_ref: str | None
    shared_component_refs: tuple[str, ...]
    unresolved_common_mode_risks: tuple[str, ...]

    change_process_ref: str
    rollback_and_reissue_rule_ref: str
    mutation_manifest_ref: str
    mutation_receipt_ref: str | None
    independent_oracle_ref: str | None

    verification_time: str | None
    review_due_time: str
    valid_until: str
    governance_assessment: Literal[
        "current",
        "known_unsound",
        "independence_unresolved",
        "expired",
        "suspended",
        "superseded",
    ]
    authoritative_for: tuple[str, ...]
    may_not_use_for: tuple[str, ...]
    research_only: bool
```

### 7.3 One-lattice mapping

```text
missing / unresolved / expired / suspended envelope
  -> existing SCOPE_INSUFFICIENT or UNKNOWN

open_world_unresolved
  -> existing SCOPE_INSUFFICIENT or UNKNOWN

known_incomplete
  -> existing FAILED, SCOPE_INSUFFICIENT, or UNKNOWN according to the witness

future bounded_complete + current + independently admitted
  -> absence of an additional coverage blocker only
  -> never SATISFIED and never promoted by itself
```

`NO_COVERAGE_BLOCKER`, where used in pseudocode, is only shorthand for “no additional coverage
blocker was introduced.” It must not be persisted, exported, ordered, or rendered as a status.
The existing PDC/Atlas lattice remains the only authority lattice.

### 7.4 Challenger and lifecycle

A challenge record carries receipt, evidence, affected scope, reviewer independence, disposition,
and recommended reaction. A perturbation event carries missed-obligation, validator-unsound,
source-competence, source-revision, scope-expansion, conflict, or expiry evidence. Neither mints
the canonical claim reaction.

The lifecycle remains append-only: draft/search/review; future bounded-current or current
known-gap/open-remainder; challenge/expiry/suspension; reissue pending; superseded/withdrawn;
historical only. For one immutable envelope, supersession and withdrawal are terminal. A later
miss creates new events and a new envelope; it does not reopen or mutate the original.

## 8. Later Integration Handoff

| Link | Existing home to prefer | Required later output | Current standing |
| --- | --- | --- | --- |
| Scope and closure disposition | claim/design-problem plus family-native source owners; exact composition unresolved | content-bound scope and one of the three closure-premise dispositions | `producer_missing` |
| Source retrieval | Fabric/Lex/adapters/acquisition planner | immutable family-native snapshots, query hashes, competence, CTM roles | partial/orchestration missing |
| Obligation instances | N9, preserving PDC coarse vocabulary | source-bound instances and derivation receipt before class aggregation | `GY-GAP1` |
| Coverage envelope | existing CAS/audit/artifact patterns; owner unresolved | immutable envelope and supersession links | `contract_missing` |
| Validator governance | existing validator owners plus independent governance to be ratified | immutable governance record and actual independence evidence | `contract_missing` / `producer_missing` |
| Independent scorer | S0-GAP-02 | frozen corpus/oracle, common-mode controls, signed scoring receipt | `producer_missing` |
| Ledger binding | N11 | validated reference to current coverage/governance standing; no new δ | `bridge_missing` |
| Promotion/claim reaction | N9 and canonical claim owner | existing status effect, refusal, suspension, withdrawal, reissue | `bridge_missing` |
| Lifecycle | N12/CTM | append-only challenge, perturbation, revalidation, reissue | pattern present; orchestration missing |
| Projection | Atlas DS12/DS17/DS18 | relative rider, unresolved steady state, basis/remainder/TTL/history | `consumer_waiting` |

No row appoints a new canonical owner. Producer, persisted artifact/event, bridge, consumer,
verification, and surface must all exist before capability can be claimed.

## 9. Promotion And Kill Rules

### 9.1 Maturity standing

| Maturity | INT-R1 condition |
| --- | --- |
| `research_only` | **Current state.** Conditional results and sketches only; no current `bounded_complete`, independent scorer, producer, bridge, or benchmark receipt. |
| `prototype_allowed` | Synthetic, noncanonical, fixture-only work; explicit GY-GAP1/S0-GAP-02 blocks; no authority writes or public positive δ claim. |
| `governed_allowed` | Consolidated owner map; one-lattice mapping; per-scope closure disposition; immutable artifacts; actual independent evidence; mandatory benchmark passage including OM-01 after GY-GAP1; complete N9/N11/N12/claim bridges; verified public rider. |
| `production_candidate` | Governed conditions plus INT-R9 first-promotion resolution, real competence evidence, operations/security/privacy/redaction, incident/reissue drills, comprehension/compression checks, and multi-epoch replay. |
| `blocked` | Known omission; closure not established where required; material source/owner/scope gap; validator unsound/expired; independence absent/common-mode; conflict unresolved; artifact expired/suspended; public rider missing; oracle invalid. |
| `out_of_scope` | Any request that makes PolicyOS legislate, adjudicate, administer, notify, pay, deliver, remedy, or reverse an external act. |

### 9.2 Immediate kill rules

Kill or return to research any implementation that implies world completeness; treats the 15
classes as the external universe; opens/dissolves the enum on INT-R1's authority; allows a
producer-filled independence field to establish passage; introduces a parallel status or risk
ledger; maps absence to not-applicable without a competent closure rule; hides unknown remainder;
assigns an uncalibrated probability to it; treats TTL as completeness; lets relative coverage
auto-satisfy or promote; self-scores the benchmark; claims OM-01 executable before GY-GAP1;
leaves the protected action or public claim green after a decisive omission/fault; silently edits
history; or publishes bare “complete”/unconditional `risk <= delta`.

### 9.3 Reopening rule

The impossibility result may be narrowed for an exact domain only when a competent authority
provides a finite exhaustive register or valid closure rule, its mandate and interval are
verified, exceptions/conflict/change semantics are included, and independent validation shows the
PolicyOS basis is extensionally equal to that register for the exact scope. This yields a
domain-relative closure premise, never a universal PolicyOS claim.

## 10. Open Questions For Consolidation

1. **Source-basis ownership:** which composition of existing family-native and claim owners may
   produce the required-source manifest without creating a universal external-authority owner?
2. **S0-GAP-02:** who authors/signs the independent source-to-obligation oracle, how common-mode
   dependencies are disclosed, and how surviving mutants are adjudicated without self-grading?
3. **GY-GAP1:** what obligation-instance identity and pre-class aggregation layer will make OM-01
   representable while preserving the live coarse denominator?
4. **GY-DEF5:** consolidation must preserve the narrowed claim-defect reading; it must not turn
   this research into authorization to alter the enum.
5. **INT-R9:** first-promotion and sequence-level risk multiplicity remain owned by INT-R9. INT-R1
   does not resolve or redefine that blocking question.
6. **INT-R5:** which canonical decision/claim owner may classify materiality and choose suspension,
   narrower scope, withdrawal, or reissue?
7. **INT-R8:** can public, reviewer, expert, and machine projections preserve relativity,
   remainder, exclusions, currentness, challenge, and the arithmetic-versus-assumption split?
8. **INT-R2:** how do legal, normative, participation, measurement, and implementation gaps extend
   existing acquisition without collapsing into a data-row model?
9. **Conflict/priority:** which competent owner and rule resolve derogation, hierarchy, temporal
   succession, or mutually incompatible obligations? Coverage preserves conflict; it does not
   decide it.
10. **TTL/event triggers:** which owners supply decisive deadlines, and how do unknown deadlines,
    retroactivity, delayed publication, succession, and public cache invalidation behave?
11. **Independence threshold:** what minimum organizational, implementation, source, oracle,
    incentive, and temporal separation is required by stakes/fault class?
12. **Empirical acquisition:** future challenger yield, detection latency, source outages,
    validator incidents, mutation survival, reviewer disagreement, TTL breaches, reissue rate,
    and audience comprehension may improve governance but cannot retroactively calibrate current
    world completeness.

No contradiction with S0-K05, S0-K06, S0-K12, or S0-K16 is introduced. No kernel reopening is
recommended.

## Final Research Verdict

The maximum honest result is not “obligation completeness has been discharged.” It is:

> For an exact scope and cutoff, under explicitly assumed compiler completeness and validator
> soundness relative to a declared immutable basis and language, PolicyOS can prove total owned-
> basis traversal and conditional inclusion/checking of every obligation derivable under those
> semantics. A separate governed protocol may supply evidence for relying on those assumptions,
> but cannot prove the external world complete. Every scope carries a closure-premise
> disposition; unknown remainder remains explicit; passage grants no authority; and later
> material omission suspends current use through append-only reissue.

At the pinned repository, the protocol is incomplete and `bounded_complete` is unavailable.
`open_world_unresolved` is the honest current standing. That refusal, the public relative rider,
the two red booleans, the self-oracle ban, and immutable correction history are as load-bearing as
the conditional theorem itself.
