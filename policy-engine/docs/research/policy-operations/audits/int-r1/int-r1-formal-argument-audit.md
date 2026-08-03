---
title: INT-R1 — Formal Argument Audit
status: delivered
kind: independent-audit
research_task: INT-R1
result_type: accepted_narrow_scope
audit_verdict: GO_WITH_REVISIONS
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r1-independent-audit
audited_branch: research/int-r1-obligation-coverage
audited_commit: 82e136a8d528cb24e661973ac1a8ea4fb6f1c80f
current_repository_commit: d152565dcc11cea457dacd61fadc6e15dc3ecc86
inspection_date: 2026-08-03
authoritative_for:
  - independent validity audit of the INT-R1 impossibility and relative-coverage arguments
  - consolidation findings INT-R1-C-* and INT-R1-D-*
may_not_use_for:
  - production implementation authorization
  - final code or wire contract
  - canonical owner appointment
  - authority grant
  - capability claim
  - legal compliance conclusion
  - benchmark passage
  - merger or release approval
research_only: true
---

# INT-R1 — Formal Argument Audit

## 1. Audit question and calibration

This file executes mandatory passes C and D. It asks two different questions:

1. does the indistinguishability construction establish its stated impossibility result; and
2. does the relative-coverage result discharge the repository's maintained assumptions, or only
   expose and relocate them?

The audit applies the ratified P29 stopping rule at
`policy-engine/docs/reference/policy-design-case-failure-patterns.md:70-75`. It does not demand
an infinite verifier tower. It does demand that a claimed stopping point be generic over an
actual source of truth rather than over a hand-authored proxy for the thing being proved.

**Bottom line:** the impossibility lemma is valid under its explicit extension-closure premise.
The relative result is also valid as a conditional inclusion result. It does **not** discharge
world-level obligation completeness or validator semantic soundness. It decomposes those
assumptions into checkable mechanical obligations plus institutional/empirical premises. That is
a useful narrow result, but the theorem language must not imply that the original gap has been
proved away.

## 2. Pass C — impossibility result

### 2.1 Statement audited

The main deliverable defines a finite trace `T`, compiled obligations `O_T`, and the actually
applicable obligation set `U(W,a,s,t)`. It assumes two admissible worlds produce the same `T`,
with `U(W1)=U(W0)∪{o*}`, where `o*` is decisive and unobserved. A procedure using only `T`
therefore returns the same result in both worlds
(`policy-engine/docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:549-586`; supporting formal note
`policy-engine/docs/research/policy-operations/int-r1/open-world-impossibility-and-relative-coverage.md:45-139`).

### 2.2 Step-by-step validity check

| Step | Audited proposition | Audit result | Reason |
| --- | --- | --- | --- |
| C1 | `T` is the complete observation available to the decision procedure. | **valid definition** | The result is explicitly about procedures whose output is a function of the finite trace. Information supplied by an additional competent closure oracle would enlarge `T` or restrict the world class. |
| C2 | `W0` and `W1` are both admissible and observationally identical with respect to `T`. | **substantive premise** | This is the open-world extension premise. It is not derived from finiteness alone. It must be justified for each claimed domain/scope. |
| C3 | The procedure produces the same output in both worlds. | **valid** | Deterministic functions of identical input are identical. For randomized procedures, identical observations induce the same conditional output distribution when the same internal randomness law is used. |
| C4 | A positive global-completeness certificate is false in `W1`. | **valid** | `o*` is applicable, decisive, and absent from `O_T` by construction. |
| C5 | Refusing in both worlds does not positively certify `W0`. | **valid** | A uniformly sound procedure may abstain, but then it has not established the requested positive completeness claim. |
| C6 | Therefore no procedure using only `T` can be both sound and positively complete over that world class. | **valid conditional conclusion** | This is a standard indistinguishability argument. It follows directly from C2-C5. |

### 2.3 Is the premise doing all the work?

**Yes, and the report is mostly honest about that.** The theorem is not an empirical discovery
that every PolicyOS scope is open. It formalizes the consequence of a precise openness
condition: the admissible world class remains closed under adding a decisive obligation that is
invisible to the available trace.

That is still useful. It prevents three invalid inferences:

- finite search volume → proof of absence;
- exact equality to an owned enumeration → equality to the world; and
- independent repetition over a shared source basis → independence from omissions in that basis.

The report expressly says that a competent exhaustive register or a valid closure rule could
rule out `W1` for a narrow scope
(`int-r1-obligation-coverage-and-open-world-completeness.md:570-579`). It therefore does not
present the premise as universally true. However, it does not provide a domain-by-domain
classification showing where PolicyOS currently has evidence for extension-closure and where a
competent exhaustive register might close the scope. The theorem is consequently a **conditional
schema**, not a repository-wide factual conclusion that every legal, normative, measurement, and
implementation domain is open.

### 2.4 PolicyOS-domain applicability

The repository supports the need for the schema but not universal application:

- `PromotionObligationClass` is a finite owned denominator
  (`policy-engine/src/polisyos/pdc/_impl/gy_waist.py:218-235`), so internal denominator closure is
  possible and currently implemented.
- The target specification itself defines a 15-family language and separately tracks
  `ObligationCompletenessRisk_t(x, scope)`
  (`policy-engine/docs/reference/policy-design-search-RACE-HOG-PODS-v3.2-spec.md:774-798`), which
  recognizes a distinction between language coverage and external adequacy.
- The custody kernel permits a declared unknown in the candidate band while requiring the
  affected protected action to fail closed
  (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:77-116`,
  `:164-187`).

What remains missing is a per-scope closure-premise record. Examples that may be closable in
principle include a finite, competent, legally designated register at a declared effective-time
cutoff. Examples likely to retain an open remainder include informal local practice, affected-
person claims not captured by a competent register, implementation constraints distributed
across institutions, or evolving interpretation. INT-R1 may prescribe how to record either
case; it has not proved which case every real PolicyOS domain belongs to.

### 2.5 Audit of the five consequences

| Consequence in §4.1 | Verdict | Qualification required |
| --- | --- | --- |
| More search can shrink known gaps but does not become proof of absence by quantity alone. | **valid** | Holds while the unseen-extension premise remains admissible. Exhaustive traversal of a valid finite closure basis is different: there the closure premise, not quantity alone, does the work. |
| Independent review can detect omissions but cannot see an obligation outside both reviewers' basis. | **valid** | Independence must include source/oracle diversity, not only organizational separation. |
| Enum equality proves denominator totality, not world completeness. | **valid and repository-grounded** | `confidence_ledger.py:337-369` and `promotion_sequence.py:1520-1900` enforce the owned denominator only. |
| A current TTL proves bounded freshness under its rule, not absence of unknown obligations. | **valid** | Event-triggered invalidation can defeat an unexpired TTL; the Custody Time Model requires owner-controlled lifecycle reaction. |
| Randomization cannot distinguish observationally identical worlds without an external distribution or closure assumption. | **valid** | Identical `T` gives the same output distribution. A Bayesian prior may allocate belief but adds assumptions; it does not obtain identification from `T`. |

### 2.6 Pass-C finding

#### INT-R1-C-001 — the impossibility result is valid but not universally discharged

- **Severity:** material
- **Disposition:** revise before consolidation.
- **Finding:** the extension-closure premise is the decisive substantive premise. The report
  acknowledges this, but consolidation must require a per-scope determination: `closed_by_competent_basis`,
  `open_under_unseen_extension`, or `closure_not_established`, with evidence and owner.
- **Unsafe reading prevented:** “INT-R1 proved no PolicyOS domain can ever be complete.”
- **Allowed result:** “Where an unseen decisive extension remains admissible, no finite trace can
  positively and soundly certify global completeness.”

#### INT-R1-C-002 — consequences and randomized extension are correctly bounded

- **Severity:** commendation
- **Disposition:** preserve.
- **Finding:** the report does not claim that more search, review, TTL, randomization, or enum
  equality supplies the missing closure premise.

## 3. Pass D — relative-coverage result

### 3.1 Statement audited

The report defines a declared basis `B`, a versioned compiler/language `v`, and
`C_v(B,a,s,t)`, the obligations derivable from the basis. Under nine premises it concludes that
every obligation derivable from `B` under the declared language is included in `O_T` and checked
under the declared rules
(`int-r1-obligation-coverage-and-open-world-completeness.md:592-647`; formal note
`int-r1/open-world-impossibility-and-relative-coverage.md:140-263`). It explicitly denies the
stronger equality `C_v(B,a,s,t)=U(W,a,s,t)`.

### 3.2 Premise-by-premise audit

| Premise | Role in conclusion | Classification | Audit verdict |
| --- | --- | --- | --- |
| R1. Explicit action, scope, audience, purpose, and temporal cutoffs. | Defines the proposition and prevents scope drift. | semantic well-formedness | **necessary and defensible**. Without it the result is not identity-stable. |
| R2. Every basis member resolved and content-bound. | Makes the basis finite/replayable and blocks dangling evidence. | mechanical admissibility | **necessary for a checkable proof**, but not evidence the chosen basis is institutionally adequate. |
| R3. Generic traversal over actual basis/nested objects with typed exemptions. | Discharges owned-object visitation totality. | complete-by-construction candidate | **principled P29 stopping point** if the basis artifact is the actual source of truth for the mechanical property. |
| R4. Compiler sound and complete relative to declared language and basis semantics. | Directly supplies the obligation-set inclusion property. | semantic adequacy assumption | **load-bearing assumption, not independently proved by the theorem**. This is the principal relocation of the original gap. |
| R5. Each obligation binds source, scope, applicability, rule, version, materiality. | Makes instances distinguishable and reviewable. | artifact integrity/traceability | **necessary for auditability**, not sufficient for semantic completeness. |
| R6. Each validator sound relative to its predicate/domain. | Directly supplies correctness of checked outcomes. | semantic adequacy assumption | **same class as target-spec A4**. It remains empirical/formal evidence-dependent. |
| R7. Appropriately independent checker reperforms bindings and runs probes. | Supplies evidence about R3-R6 and common-mode resistance. | governance/benchmark admissibility | **not constructed by this research**; named dimensions make it inspectable, but no current independent producer/scorer exists. |
| R8. No known material source, compiler, validator, conflict, independence, or provenance defeater remains. | Prevents known counterevidence from being ignored. | bounded assurance-case condition | **defensible as “no known defeater”**, never equivalent to no possible defeater. |
| R9. Envelope/governance records current and unsuspended. | Limits the result to current-use standing. | temporal/lifecycle admissibility | **necessary and consistent with CTM**, but implementation is absent. |

### 3.3 Does the result discharge `obligation_completeness`?

**No. It decomposes it.** The conclusion follows because R4 already states completeness relative
to the selected language and basis semantics. In logical form, R4 contains the core inclusion
claim the theorem later concludes. R3 and R5 make that claim mechanically checkable; R7 and R8
supply evidence-governance requirements; R9 limits time. None proves that the declared language
captures all applicable world obligations.

The result is materially different from a bare A4 string in one useful sense: it identifies
which parts can be discharged mechanically, which need independent evidence, and which remain
institutional/open. But its semantic premises are not weaker than the target specification's
maintained assumptions:

- target-spec A4: deterministic validators are sound relative to declared obligation language
  (`policy-design-search-RACE-HOG-PODS-v3.2-spec.md:1635-1654`);
- INT-R1 R6: each validator is sound relative to its predicate/domain;
- INT-R1 R4: the compiler is sound and complete relative to declared language and basis
  semantics.

R4 adds an explicit compiler-completeness assumption; it does not prove that assumption. The
PolicyOS adoption record already warns that the target theorem “formalizes the contract around
our hardest open problem; it does not close it” and that its teeth are empirical
(`policy-engine/docs/system-design-decisions/policy-design-search-target-spec.md:155-177`). INT-R1
must remain consistent with that warning.

### 3.4 Pure theorem versus governed admissibility protocol

The report's nine-premise presentation combines two layers that should be separated:

1. **Deductive inclusion theorem.** Given a fixed basis/language, generic complete traversal,
   compiler completeness relative to the declared semantics, and sound validators, every
   derivable obligation is visited and checked.
2. **Governed admissibility protocol.** Independent reperformance, mutation/metamorphic evidence,
   no known material defeaters, current governance standing, source competence, and challenge
   determine whether PolicyOS may rely on those semantic assumptions for a protected action.

R7 is not a logical premise needed after R4 and R6 are simply assumed true. It is evidence for
believing them. R8 and R9 likewise govern current admissibility. Conflating these layers makes it
look as though tests create semantic truth rather than provide fallible evidence about it.

### 3.5 Audit of the five stopping points in §4.5

The main report's table appears at
`int-r1-obligation-coverage-and-open-world-completeness.md:700-729`.

| Property | Report classification | Audit verdict | Reason |
| --- | --- | --- | --- |
| Owned schema/object coverage | complete-by-construction | **confirmed** | Generic recursion over the actual owned source, with typed exemptions, is the P29 stopping point. A present missed field or string loophole would be a defect; a hypothetical future field alone is not. |
| Declared-basis source/obligation coverage | relative theorem plus benchmark evidence | **confirmed with narrowing** | Mechanical derivation coverage can be proven relative to the basis. Institutional adequacy of the basis cannot. The benchmark is evidence, not part of the logical theorem. |
| Validator behavior | relative theorem plus empirical tests | **confirmed with narrowing** | A validator may be proved against a formal predicate, tested against a fault model, or reperformed. Soundness outside the formalized domain remains an assumption. |
| Institutional adequacy of selected basis | governance judgment | **confirmed** | Competence, diligence, materiality, and stopping are institutional judgments with evidence and challenge, not a construction theorem. |
| Absence of obligations outside basis | explicit unknown / impossibility | **confirmed under extension-closure premise** | A narrow competent closure premise can defeat the impossibility construction; absent that premise, the unknown must remain. |

The table is the strongest part of the report's regress analysis. It correctly refuses to apply
the P29 mechanical stopping rule to a world that is not represented by one owned object graph.

### 3.6 Is “appropriately independent” constructed?

No. The report identifies useful independence dimensions—organizational, implementation,
source/data, oracle, economic, and temporal—and rejects a second function name or checker sharing
the faulty parser
(`int-r1-obligation-coverage-and-open-world-completeness.md:730-759`; artifact sketch
`int-r1/artifact-and-state-machine-sketch.md:250-390`). These fields make independence
**inspectable**. They do not produce an independent checker, author, scorer, or competent source
owner.

The backlog itself records S0-GAP-02 as the pending independent oracle/scorer dependency, and the
ratification record blocks scoring until that dependency lands
(`policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md:500-640`;
`stage0-custody-kernel-ratification.md:188-212`). Therefore no current repository artifact can
satisfy R7 merely because the research sketch contains an `independence_record` field.

### 3.7 Failure of a premise: pass or refusal?

At the design level, the report consistently maps failed premises to refusal:

- unresolved basis/hash/expiry/suspension → `scope_insufficient` or `unknown`;
- known decisive omission/unsound validator → `failed`, `scope_insufficient`, or `unknown`;
- materially common-mode independence → `open_world_unresolved`;
- candidate work may continue only with a declared limitation;
- no coverage state sets `promoted` automatically
  (`int-r1-obligation-coverage-and-open-world-completeness.md:648-699`, `:1045-1215`).

That is semantically sound. It is not implemented. The current N9 gate does not consume an
`ObligationCoverageEnvelope` or `ValidatorGovernanceRecord`; those capabilities remain
`contract_missing`/`producer_missing`/`bridge_missing` in the report's own census
(`int-r1/repository-census-and-anchor-ledger.md:260-330`). Thus “fails closed” is a proposed
protocol property, not a demonstrated runtime property.

### 3.8 Pass-D findings

#### INT-R1-D-001 — R4 and R6 relocate rather than discharge the maintained assumptions

- **Severity:** material
- **Disposition:** revise theorem claim.
- **Required revision:** call the result a **conditional relative-inclusion theorem** and state
  that compiler semantic completeness and validator soundness remain assumptions whose current
  reliance requires separately admitted evidence. Do not say INT-R1 proved
  `obligation_completeness` or `validator_soundness`.

#### INT-R1-D-002 — theorem and evidence protocol are conflated

- **Severity:** material
- **Disposition:** split before consolidation.
- **Required revision:** place R1-R6 in the formal entailment statement, then state R7-R9 as
  governed admissibility conditions for relying on the result. Mutation and independent review
  can falsify weak implementations; they do not logically manufacture soundness.

#### INT-R1-D-003 — independence is checkable vocabulary, not a constructed capability

- **Severity:** material
- **Disposition:** retain `producer_missing` and block any current `bounded_complete` claim.
- **Required revision:** explicitly state that the pinned repository cannot instantiate
  `bounded_complete` until an independent source-to-obligation checker/scorer and its governance
  evidence are admitted. S0-GAP-02 is a dependency, not a field value.

#### INT-R1-D-004 — stopping-point taxonomy is principled

- **Severity:** commendation
- **Disposition:** preserve.
- **Finding:** the report correctly stops recursion at generic owned-source traversal while
  refusing to infer world closure from that mechanism.

## 4. Formal-result disposition

| Result | Audit disposition | Consolidation-safe wording |
| --- | --- | --- |
| Open-world impossibility | **accepted narrow scope** | If the admissible world class remains open under an unobserved decisive-obligation extension, no finite trace available to PolicyOS can both soundly and positively certify global completeness. |
| Declared-basis coverage | **accepted with material narrowing** | Under explicit semantic assumptions, PolicyOS can prove/check total traversal and inclusion relative to a fixed basis and language. |
| World completeness | **not established** | Requires a separately evidenced, scope-specific closure premise; otherwise the remainder is unknown. |
| Compiler completeness | **not established by the theorem** | Assumed relative to declared semantics; may be supported or falsified by formal proof, independent reperformance, and mutation evidence. |
| Validator soundness | **not established by the theorem** | Same maintained assumption as the target specification, made more governable but not eliminated. |
| Independent checker | **not constructed** | Pending producer/governance/scorer work; no benchmark passage or `bounded_complete` capability at the pinned baseline. |

No blocking refutation of the narrow result was found. The revisions are required because this
result sits directly beneath every future δ claim: a conditional decomposition must not be
consolidated as a discharge of the conditions.