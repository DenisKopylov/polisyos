---
title: PAO-R4 repository integration handoff
research_id: PAO-R4
artifact_role: integration-handoff
status: amended_research
research_only: true
repository: DenisKopylov/polisyos
audited_commit: a27c3da9942b03881dbee1005a8a1e44e5ac44b4
audit_commit: 69182c079fb5dc99808d7cd27874d50433efd5a4
pinned_repository_commit: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
result_standing: GO_WITH_REVISIONS
adoption_status: NO_GO_pending_independent_conformance
authoritative_for:
  - amended research-only repository integration handoff
  - prerequisite-safe capability-state classification
  - open consolidation question for policy-to-case emission placement
  - predicate-provenance obligations for a later implementation
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization or API contract
  - canonical owner or vendor appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional compliance conclusion
  - permission to publish or open a gate
  - automatic amendment of any plan, backlog or system-design decision
---

# Repository integration handoff

## 1. Established owners and open placement

PAO-R4 creates no implementation owner and appoints no external case authority.

### 1.1 Established responsibilities

| Needed responsibility | Existing owner or boundary | Pinned evidence | Amended research disposition |
|---|---|---|---|
| Denied-use declaration and bounded consumer rejection | `polisyos.core.contracts` authority envelopes plus existing consumer guards | `policy-engine/src/polisyos/core/contracts/runtime.py:278-329@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`; `policy-engine/src/polisyos/policy_grammar/_impl/consumer.py:53-67@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee` | Extend `may_not_use_for`; do not create a parallel `prohibited_use` mechanism. |
| Projection semantics and restriction monotonicity | `polisyos.runtime.quality.projection_semantics` and projection contracts | `policy-engine/src/polisyos/runtime/quality/projection_semantics.py:46-94,479-523@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`; finding `PV-K04` | Preserve the union of source/derivation denials for all canonical audiences. |
| Public redacted bundle | `polisyos.runtime.quality.public_export` | `policy-engine/src/polisyos/runtime/quality/public_export.py:39-101@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee` | Reuse its facts where applicable; do not infer ownership of every case-system handoff. |
| Access/redaction evidence | Fabric source/access contracts and runtime authorization inputs | `policy-engine/src/polisyos/fabric/connectors/contracts/source_contract.py:34-52,106-142@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`; `policy-engine/src/polisyos/core/security/authz.py:50-90,135-170@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee` | These facts may inform `H`; an anonymization/redaction marker is never permission by itself. |
| Public display consumer | Atlas DS12 | `policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:1330-1445@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee` | DS12 may render a bounded result; it is not a case-system consumer or owner of the individual act. |

### 1.2 Open consolidation decision — policy-to-case emission chokepoint

`public_export.py` is a real adjacent public-bundle producer. No pinned finding establishes that all
non-public, purpose-bound case-system handoffs must flow through it. The original handoff's “no second
exporter” language was authority by adjacency under `P36`.

The canonical emission chokepoint therefore remains an **open consolidation decision**. A competent
architecture decision must compare existing responsibilities, at minimum:

1. extending the public-export owner with a separately bounded non-public mode;
2. placing the gate at an existing authority-envelope/consumer-admission boundary; or
3. approving another canonical boundary that routes all policy-to-case emissions through one
   structural chokepoint.

This list presents alternatives; it appoints none. The decision must preserve the established denied-
use and projection owners and avoid a parallel prohibition system.

## 2. Missing-state vocabulary — prerequisites first

The capability-reality register defines a complete chain as typed artifact + producer + persisted
artifact/event + bridge + consumer + verification + visible surface or explicit out-of-scope +
negative semantic test
(`policy-engine/docs/reference/policy-design-case-failure-patterns.md:12-37@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`).

| Label | Required prerequisite | PAO-R4 evidence at the pin | Use in this handoff |
|---|---|---|---|
| `contract_only` | admitted implementation contract exists but is unused | no admitted E/G/X/S, purpose, gate, or return contract | not used |
| `producer_missing` | named consumer expects a defined artifact/event | no admitted external case-consumer contract | not used |
| `artifact_missing` | producer logic for the defined artifact/event exists | no PAO-R4 return-evidence producer | not used |
| `bridge_missing` | both producer and consumer exist for the same artifact | endpoints absent | not used |
| `consumer_missing` | artifact/event is produced and persisted | no PAO-R4 artifact chain | not used |
| `verification_missing` | producer-artifact-bridge-consumer chain is wired | chain absent | not used |
| `implemented_but_not_orchestrated` | component works in isolation | research only | not used |
| `surface_missing` | internal capability works | no capability | not used |
| `surface_out_of_scope` | internal capability works and surface omission is intentional | no capability | not used |
| `semantic_test_missing` | structural implementation tests already pass | no implementation | not used |

### Present classification

The semantic-class vocabulary, pointwise-recoverability evaluator, predicate-provenance admission,
policy-to-case emission gate, governed external consumer consultation gate, returning-evidence intake,
independent denominator reconciliation, and composition transcript are all
**`absent/unallocated`**.

This is a settled capability-honesty result, not a placeholder for a stronger missing-state label.
The complete source census confirms zero files, zero matching lines, and zero occurrences for the
exact source concepts `individual_decision`, `export_gate`, and `prohibited_use` below
`policy-engine/src`.

## 3. Later capability handoffs

### 3.1 Semantic class and authority-effect classification

**Extends:** existing authority-purpose and evidence/claim contracts after an owner decision.

**Consumes:** E/G/X/S definitions and `individualizable(a,H)` from the amended primary report.

**Required later behavior:**

- classify empirical population claims separately from competent normative rules;
- reclassify singleton/deterministic empirical artifacts as X;
- allow G as candidate-band rule-level input without PolicyOS authority effect;
- refuse unknown/mixed protected crossings; and
- prove behavior over equivalent code, table, tree, prompt, and prose representations.

**Acceptance evidence:** amended F-05 through F-08 run against the real classifier. Artifact C is not
refused merely for executability; the identical-syntax empirical decision tree is refused.

**Present state:** absent/unallocated.

### 3.2 Predicate-provenance admission under `P37`

**Extends:** future chosen emission and consumer admission chokepoints.

**Required later behavior:** every decisive predicate is frozen as exactly one of:

`recomputed` · `independently_reconciled` · `consumer_asserted` ·
`institutionally_supplied` · `not_established`.

A decisive predicate in the last three classes cannot produce an authority-grade positive. The
implementation must distinguish registered-field presence from semantic completeness, request
purpose from actual use, and counterfactual assertion from observable consultation.

**Acceptance evidence:** F-20 and F-21 remain non-positive when declarations are false but markers
remain present.

**Present state:** absent/unallocated.

### 3.3 Artifact-local and export-context gates

**Placement:** open consolidation decision; no owner appointed.

**Input semantics:** artifact bytes, resolved lineage, registered basis obligations, E/G/X/S class,
named history/auxiliary model `H`, behavioral pointwise evaluator, denied-use union, request record,
and predicate-provenance classifications.

**Required verdict effect:**

- explicit individual rows/scores/recommendations and E/S pointwise artifacts are refused;
- unsafe composition is blocked;
- unknown history/class/basis completeness is `NOT_ESTABLISHED` and cannot become a protected
  crossing positive;
- G is not refused merely for executability, but carries no PolicyOS authority/applicability claim.

**Acceptance evidence:** F-03 through F-10 and F-17 through F-20 exercise the real chosen chokepoint.

**Present state:** absent/unallocated.

### 3.4 Governed external consumer consultation gate

**Boundary:** INTEGRATE with a named external case-system consumer. PolicyOS does not implement or own
the case workflow.

**Conservative use predicate:** a resolved subject and protected action plus instrumented consultation,
display, query, invocation, threshold, ranking, recommendation, evidence weighting, explanation, or
routing by the PolicyOS artifact/derivative.

The gate does not ask the consumer whether the artifact “really mattered.” Consultation is enough.
Declared purpose is intake evidence only; action effects determine semantic purpose.

**Acceptance evidence:** F-01 blocks silent planning-to-eligibility drift; removing the real gate while
retaining markers makes F-01 fail; F-14, F-15, F-21, F-22, and F-23 block through actual use/effect.

**Present state:** absent/unallocated.

### 3.5 Returning-evidence intake and reconciliation

**Extends:** a future PolicyOS evidence/custody intake owner after consolidation; no case-system schema
is designed here.

**Required semantics:** issued artifacts, derivatives, consultations, gate attempts, bypasses,
protected actions, exact digests/lineage, effect classes, boundary identity, interval, and frozen
predicate-provenance classes.

**Trust requirement:** content-bound append-only records plus independently reconciled consultation
and protected-action denominators. Self-attested totals and self-reported counterfactuals cannot
support a complete positive.

**Failure behavior:** missing, late, contradictory, sampled, unresolved, or self-attested-only evidence
returns `FIREWALL_CLAIM_NOT_ESTABLISHED` for complete non-use.

**Acceptance evidence:** F-02, F-12, and F-13 distinguish an observed violation, unavailable complete
claim, and the narrow value of an observed voluntary report.

**Present state:** absent/unallocated.

### 3.6 Composition, relay, and outside-boundary residual

**Required semantics:** complete controlled release/query transcript, named `H`, derivative lineage,
relay identity, and explicit boundary exclusions.

**Acceptance evidence:**

- F-03/F-10 block known composition;
- F-04 returns `NOT_ESTABLISHED` for an asserted/incomplete inventory;
- F-11/F-18 honestly return `NOT_DETECTABLE` outside instrumentation;
- F-22 detects reference-class shopping inside the boundary; and
- F-24 refuses an unresolved lineage-stripped relay at governed intake.

**Present state:** absent/unallocated.

## 4. Claim-boundary handoff

A later implementation may make only claims bounded by the primary report's claim-boundary table.
The maximum positive is never institution-wide non-use. It is a content-bound statement about every
recorded protected-action consultation inside a named governed boundary and interval whose
consultation/action denominators independently reconcile.

Voluntary reporting supports no complete non-use claim. It may support only observed-incident,
lower-bound, or valid sampled-frame claims with explicit directional limits. This is claim bounding
under `INT-K08`, not a new status lattice.

## 5. Dependencies and isolation

- **`PAO-R36`:** a corrected/superseding record may not carry a weaker individual-use restriction
  than its predecessor. PAO-R36 owns all correction, notice, and supersession mechanics.
- **`OPS-R14`:** any future durability, recovery, retention, expiry, or legal-hold property for
  firewall evidence is an interface dependency. PAO-R4 sets none.
- **`S0-GAP-02`:** benchmark-oracle architecture is outside PAO-R4. This amendment defines semantic
  falsifiers but no benchmark oracle, evaluator custody, or scoring system.

No sibling artifact is modified and no sibling standing is adjudicated.

## 6. Open questions for consolidation

### Engineering

| ID | Question | Required closure evidence |
|---|---|---|
| `ENG-01` | Which existing responsibility becomes the canonical policy-to-case emission chokepoint? | competent owner decision, complete emission census, one structural route, and no sibling bypass |
| `ENG-02` | How is E/G/X/S classification made representation-independent? | behavioral evaluator over equivalent code/table/tree/prompt/prose artifacts |
| `ENG-03` | What named `H` inventory is complete enough for each non-resolution claim? | independent inventory owner, completeness proof/bound, and falsify-the-declaration test |
| `ENG-04` | How are action effects mapped to canonical denied purposes without string bypass? | effect taxonomy, synonym/adversarial tests, and sibling-consumer coverage |
| `ENG-05` | Which instrumented events prove consultation while minimizing false negatives? | real data-flow evidence, conservative rule, and S-1/S-2 boundary analysis |
| `ENG-06` | How are independent protected-action totals reconciled without PolicyOS owning identity/case data? | scoped references, independent totals, mismatch handling, privacy/security review |
| `ENG-07` | How are lineage-stripped relays refused or bounded? | governed intake resolution rule and multi-hop relay tests |

### Institutional

| ID | Question | Required closure evidence |
|---|---|---|
| `INST-01` | Which external case-system owner accepts mandatory consultation gating and evidence return? | named mandate and operating agreement; this research appoints nobody |
| `INST-02` | Who supplies and is competent for normative rule authority/applicability? | scoped external mandate and procedure; no PolicyOS authority claim |
| `INST-03` | Which independent source supplies protected-action denominators? | non-producing event owner and reconciliation procedure |
| `INST-04` | What consequence makes evidence return mandatory in practice? | enforceable agreement, suspension rule, and audit rights |
| `INST-05` | Which affected-person safeguards apply inside each case procedure? | external hearing/reason/review/recourse procedure; outside PAO-R4 implementation |

### Additional research

| ID | Question | Candidate method |
|---|---|---|
| `RES-01` | What bounded proofs establish non-individualizability under adaptive auxiliary information? | finite reconstruction models and proved conservative approximations |
| `RES-02` | How should uncertain/disputed reference-class membership be represented? | set-valued class membership and abstention analysis |
| `RES-03` | Which adaptive query controls prevent differencing and reference-class shopping? | prospective transcript models and adversarial sequence analysis |
| `RES-04` | What evidence validates causal materiality beyond conservative consultation? | independently governed removal experiments or causal instrumentation |

## 7. Standing

**Research standing: `GO_WITH_REVISIONS`. Adoption status: `NO_GO` pending independent conformance.**

The amendment supplies a narrow formal and falsifier contract. It does not create the missing
capability, choose the emission owner, appoint an external authority, or authorize implementation.
