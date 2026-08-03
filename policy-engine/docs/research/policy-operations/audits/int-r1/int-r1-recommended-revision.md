---
title: INT-R1 — Recommended Revision Before Consolidation
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
  - ordered revision requirements for INT-R1 consolidation
  - acceptance checklist derived from the independent audit
may_not_use_for:
  - direct editing of the audited branch
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

# INT-R1 — Recommended Revision Before Consolidation

## 1. Revision disposition

**Overall verdict: `GO_WITH_REVISIONS`.**

There is no blocking refutation of the narrow result. The consolidation may retain:

- the conditional impossibility result under an unseen-extension premise;
- the refusal of unconditional open-world obligation completeness;
- relative coverage over a declared basis/language as the maximum positive claim;
- the explicit public rider that δ is relative to the declared obligation set and maintained
  assumptions;
- one-lattice inputs rather than a parallel authority lattice;
- challenger, suspension, append-only supersession, and reissue semantics; and
- the benchmark requirement that a decisive omission or validator fault blocks protected action
  and current public claim.

The revisions below are mandatory because the present language can be read more strongly than
the evidence permits or cannot yet be implemented without a new design decision.

## 2. Blocking revisions

**None.**

A blocking revision would be required if the relative result claimed world completeness, if the
benchmark self-scored, if `bounded_complete` minted promotion, or if an audited repository anchor
contradicted a core claim. The audit found none of those conditions.

## 3. Material revisions

### R1 — Recast the relative theorem as a conditional inclusion result

**Findings:** `INT-R1-D-001`, `INT-R1-D-002`.

**Affected sections:** main §4.2, §4.5, §4.7; formal supporting note.

**Problem:** premise 4 assumes the compiler is sound and complete relative to the declared
language and basis semantics; premise 6 assumes validator soundness. Those semantic assumptions
perform the same load-bearing work as the target specification's A4 and the repository's typed
maintained assumptions. The result decomposes the gap but does not discharge it.

**Required revision:**

1. Rename the formal result **Conditional Relative-Inclusion Theorem** or equivalent.
2. State the deductive core separately:
   - fixed identified scope/basis/language;
   - generic complete traversal over the owned basis;
   - compiler completeness relative to explicitly declared basis semantics;
   - validator soundness relative to explicitly declared predicates;
   - therefore all obligations derivable under those semantics are included/checked.
3. State independent reperformance, mutation, no-known-defeater, and currentness as a separate
   **governed admissibility protocol** supplying evidence for reliance on the semantic premises.
4. Add an explicit sentence: “INT-R1 does not prove compiler semantic completeness or validator
   soundness; it specifies how evidence for those assumptions must be governed and how failure
   must block current use.”
5. Preserve the denial of `C_v(B,a,s,t)=U(W,a,s,t)`.

**Acceptance evidence:** no passage in the consolidated result says the maintained assumptions
are “discharged” unless it names the exact property and supporting proof/evidence class. Mechanical
traversal may be discharged; world adequacy and validator semantics may not be silently included.

### R2 — Require a per-scope closure-premise disposition

**Finding:** `INT-R1-C-001`.

**Affected sections:** main §4.1, §4.2, §7.1, §9; formal supporting note.

**Problem:** the impossibility construction is valid only while the admissible world class is
open under an unseen decisive-obligation extension. The report says a narrow competent register
may close a scope, but it does not require an explicit disposition for actual scopes.

**Required revision:** add a research-level field or rule, without freezing wire form, that makes
one of these states explicit for each action/scope/cutoff:

- `closed_by_competent_basis` — closure premise, competent owner, authority scope, time interval,
  exhaustive-register semantics, and challenge route are evidenced;
- `open_under_unseen_extension` — the source/world model admits a decisive unseen extension; or
- `closure_not_established` — neither closure nor a positive openness characterization is
  adequately evidenced.

Only the first can defeat the impossibility premise, and only for its exact scope/time/purpose.
The other two preserve an unknown remainder and fail closed for affected protected use.

**Acceptance evidence:** every use of the impossibility theorem names its premise; no text says
all PolicyOS domains are necessarily open or necessarily closable.

### R3 — State that no current `bounded_complete` capability exists

**Finding:** `INT-R1-D-003`.

**Affected sections:** executive result, capability labels, §4.3, §6.2, §7.1-7.4, §8, §9.

**Problem:** independence dimensions and typed fields make a future decision inspectable, but no
independent checker/scorer, source-to-obligation oracle, or governance producer exists at the
pinned baseline. S0-GAP-02 remains a dependency.

**Required revision:** add a prominent current-standing statement:

> At `d152565d`, `bounded_complete` is a research-defined assessment only. It cannot be issued by
> the current repository because the independent coverage checker/scorer, governance record
> producer, envelope producer, and gate bridge are missing. Any current attempt maps to
> `open_world_unresolved`/existing fail-closed status rather than to `bounded_complete`.

Do not permit a producer-filled `independence_record` to satisfy independence. The later
admission rule must require evidence of actual organizational/implementation/source/oracle
separation and disclosed common-mode dependencies.

**Acceptance evidence:** S0-GAP-02 is represented as an unresolved dependency, not as a default
owner or a field that can be self-populated.

### R4 — Make OM-01 executable against the current N9 representation

**Finding:** `INT-R1-H-002`.

**Affected sections:** main §5 class-counting counterexample, §6.3-6.4; benchmark supporting file;
artifact sketch if necessary.

**Problem:** the current N9 compiler creates exactly one `PromotionObligationRecord` per
`PromotionObligationClass`; the record has no obligation-instance identity. The proposed fixture
requires two obligations in `normative`, deletion of one, and preservation of the class row so
class totality stays green. That cannot be built directly without an unprovided instance and
aggregation layer.

**Required revision:** specify, at research level, all four of these elements:

1. **Mutation layer:** the exact source-derived obligation-instance collection that exists before
   class aggregation.
2. **Instance identity:** minimum semantic key binding source/rule/scope/time/predicate, without
   freezing a wire schema.
3. **Aggregation bridge:** how multiple instances map to the existing one-record-per-class N9
   outcome and how an omitted instance can leave class presence unchanged.
4. **Oracle comparison point:** where the frozen independent source-to-instance set is compared
   with the implementation output before class aggregation.

Alternatively, if the benchmark is intended only for a future redesigned compiler, label it
`prototype_blocked_on_instance_model` and supply a current-representation mutation that is
actually executable. Do not claim “another agent can build it without asking a question” until
one of those paths is complete.

**Acceptance evidence:** an implementer can identify the concrete mutation input/output and the
specific current or future artifact whose class totality remains green.

### R5 — Narrow the Rule-12 verdict on `PromotionObligationClass`

**Finding:** `INT-R1-G-001`.

**Affected sections:** census §2.3/§3, main §2.4, counterexamples, promotion/kill rules.

**Problem:** exact class equality participates in promotion, but Rule 12 explicitly exempts
governed vocabularies, schemas, statuses, ports, and rule versions. Participation in a gate does
not alone remove the exemption. The defect arises when the enum is treated as the exhaustive
world universe or when new admissible obligation instances/families cannot enter through a
governed extension path.

**Required revision:** replace the categorical sentence “the enum is currently a
capability-gating enumeration” with this use-sensitive disposition:

- **confirmed legitimate:** versioned coarse class vocabulary, routing/budget stratum, and exact
  totality denominator for a declared compiler version;
- **unsupported/defective use:** evidence that all applicable world obligations are represented,
  or a hard boundary that prevents source-derived obligations from being represented and
  challenged without code enumeration changes;
- **not decided by INT-R1:** whether the future implementation should add a class, extension
  family, instance layer, or other representation.

**Acceptance evidence:** the consolidated result does not characterize the live waist itself as
a ratified Rule-12 defect unless it identifies an actual obligation that cannot be represented or
an actual free-growth path blocked by the enum. It may characterize a **universal interpretation**
of the enum as defective now.

### R6 — Repair primary-source support for *Normative Systems*

**Finding:** `INT-R1-B-001`.

**Affected sections:** main §3.1; external source ledger.

**Problem:** the Berkeley catalog verifies the book's existence but not the report's detailed
substantive attribution.

**Required revision:** provide edition/page-exact primary anchors for the propositions used, or
narrow the paragraph to a non-load-bearing orientation statement. The formal result must stand on
its own definitions and argument rather than on a catalog record.

**Acceptance evidence:** a reader can locate the relevant primary pages without relying on an
uncited secondary summary.

## 4. Minor revisions

### R7 — Narrow the contributor-contract anchor

**Finding:** `INT-R1-A-002`.

Replace “locates typed authority contracts and runtime integration” with “requires architecture,
quality, test, and documentation governance for contributions,” or add a more specific canonical
architecture anchor.

### R8 — Keep `NO_COVERAGE_BLOCKER` non-canonical and derived

**Finding:** `INT-R1-F-002`.

State that `NO_COVERAGE_BLOCKER` in §7.4 is pseudocode for the absence of an additional coverage
blocker. It must not be persisted, exported, ordered, or rendered as an authority status. The
existing PDC/Atlas status lattice remains the only authority lattice.

### R9 — Narrow “defeats keyword tests”

**Finding:** `INT-R1-H-003`.

Replace with “defeats class-counting, marker-presence, and generic accessibility-token checks
that do not bind district-level source semantics.” A semantic keyword oracle must be separately
defined before claiming defeat.

### R10 — Scope the proving-ground statement

**Finding:** `INT-R1-I-003`.

Use: “At the pinned W12.D/G5 proving-ground snapshot, 13 cases remain typed blockers, with zero
grounded conversions and zero useful-design credit.” Do not make this artifact a universal
statement about every experimental execution in repository history.

### R11 — Normalize source identifiers

**Finding:** `INT-R1-B-003`.

Use stable DOI/official report identifiers for Cook/corrigendum, DeMillo et al., NASA MC/DC, and
Ramdas et al. Page ranges should not be load-bearing unless checked against the primary edition.

## 5. Preserve unchanged

The consolidation should preserve these audited strengths:

1. the 15-member correction (`INT-R1-I-001`);
2. the explicit impossibility-premise caveat and narrow-domain escape (`INT-R1-C-002`);
3. the five-row stopping taxonomy (`INT-R1-D-004`);
4. the frozen independent-oracle requirement and S0-GAP-02 deferral (`INT-R1-E-001`);
5. the explicit statement that no benchmark was run (`INT-R1-E-002`);
6. the prohibition on producer self-attestation as `bounded_complete`;
7. the one-lattice mapping and no-auto-promotion rule (`INT-R1-F-001`);
8. red semantics setting both protected action and current public claim false
   (`INT-R1-H-004`);
9. append-only historical preservation with suspension/reissue;
10. external-source non-transfer statements (`INT-R1-B-002`); and
11. the clean research-only diff (`INT-R1-H-005`).

## 6. Consolidation acceptance checklist

INT-R1 is ready for consolidation only when every answer is yes:

| Gate | Required answer |
| --- | --- |
| Does the formal result clearly distinguish deductive inclusion from evidence/admissibility? | yes |
| Does it say R4/R6 remain semantic assumptions rather than proved facts? | yes |
| Does each actual scope carry a closure-premise disposition? | yes |
| Does current standing explicitly deny issuance of `bounded_complete` at the pinned baseline? | yes |
| Is independent scoring/checking an actual dependency rather than self-attested metadata? | yes |
| Is OM-01 tied to an executable instance/aggregation layer or labeled blocked? | yes |
| Is the enum verdict use-sensitive rather than a categorical defect declaration? | yes |
| Are the detailed *Normative Systems* claims primary-page anchored or narrowed? | yes |
| Is `NO_COVERAGE_BLOCKER` expressly non-persisted and non-canonical? | yes |
| Does the public δ rider still expose basis, assumptions, remainder, currentness, and expiry? | yes |
| Does no revised sentence claim benchmark passage, capability, compliance, or authority? | yes |

Meeting these conditions does not authorize implementation. It makes the research result honest
enough to enter the separate consolidation pass.