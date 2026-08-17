---
title: PAO-R4 repository integration handoff
research_id: PAO-R4
artifact_role: integration-handoff
status: research
research_only: true
repository_pin: 1a7a2d05ebba22fae80e9934329e4b880806588e
result_standing: GO_WITH_REVISIONS
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

## 1. Existing owners to extend

PAO-R4 creates no parallel owner.

| Needed capability | Existing owner or boundary to extend | Pinned evidence | Research disposition |
|---|---|---|---|
| Denied-use declaration and consumer rejection | `polisyos.core.contracts` authority envelopes plus bounded consumer guards | `policy-engine/src/polisyos/core/contracts/runtime.py:250-290@1a7a2d05ebba22fae80e9934329e4b880806588e`; `policy-engine/src/polisyos/policy_grammar/_impl/consumer.py:60-77@1a7a2d05ebba22fae80e9934329e4b880806588e` | Extend existing `may_not_use_for`; do not create `prohibited_use`. |
| Public/export-boundary inspection | `polisyos.runtime.quality.public_export` | `policy-engine/src/polisyos/runtime/quality/public_export.py:45-110@1a7a2d05ebba22fae80e9934329e4b880806588e` | Extend the real public/export owner with class, purpose, resolution, executability, and evidence checks. |
| Projection monotonicity and audience semantics | `polisyos.runtime.quality.projection_semantics` and `core.contracts.PolicyDesignCaseProjection` | `policy-engine/src/polisyos/runtime/quality/projection_semantics.py:37-56,522-566@1a7a2d05ebba22fae80e9934329e4b880806588e`; `policy-engine/src/polisyos/core/contracts/policy_design_case_projection.py:12-20@1a7a2d05ebba22fae80e9934329e4b880806588e` | Consume `PV-K04`; deny-use union must survive all four canonical audiences. |
| Data access/redaction facts | Fabric source/access contracts and runtime authorization input | `policy-engine/src/polisyos/fabric/connectors/contracts/source_contract.py:34-52,106-142@1a7a2d05ebba22fae80e9934329e4b880806588e`; `policy-engine/src/polisyos/core/security/authz.py:50-90,135-170@1a7a2d05ebba22fae80e9934329e4b880806588e` | Reuse access facts, but do not equate anonymization/redaction with firewall permission. |
| Release-history/currentness dependency | GY-N12 lane / append-only currentness owner named by the ratified architecture | `policy-engine/docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md:269-302@1a7a2d05ebba22fae80e9934329e4b880806588e`, architect correction `RFR-06` / `GY-GAP3` | Require a controlled transcript interface; do not build a second chronology owner. |
| Public consumer | Atlas DS12 | `policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:1330-1445@1a7a2d05ebba22fae80e9934329e4b880806588e` | DS12 renders the boundary result; it must not invent authority or a case workflow. |

The external case-management system is a named future integration endpoint, not a PolicyOS package.
PolicyOS owns the typed evidence contract and fail-closed absence behavior under the identity ruling;
it does not own the administrative function.

## 2. Missing-state vocabulary—prerequisites first

The project register defines capability as typed artifact + producer + persisted artifact/event +
bridge + consumer + verification + external surface or explicit out-of-scope + semantic negative
test (`policy-engine/docs/reference/policy-design-case-failure-patterns.md:12-37@1a7a2d05ebba22fae80e9934329e4b880806588e`). Labels cannot be borrowed out of order.

| Label | Prerequisite that must already be evidenced | Evidence required before use | PAO-R4 present use |
|---|---|---|---|
| `contract_only` | An admitted implementation type/schema/status exists, unused by producer, consumer, and workflow. | Exact contract path plus complete non-use evidence. | **Not used.** Research prose is not an admitted contract. |
| `producer_missing` | A named existing consumer expects a specific artifact/event. | Consumer path and expected input plus complete producer census. | **Not used.** No accepted case-system consumer contract exists in the repository. |
| `artifact_missing` | Producer logic exists for a defined artifact/event. | Executable producer plus absence of persistence/query/replay. | **Not used.** No PAO-R4 returning-evidence producer is claimed. |
| `bridge_missing` | Both producer and consumer exist for the same bounded artifact. | Both endpoint paths and missing orchestration evidence. | **Not used for the firewall chain.** The external consumer endpoint and returning-evidence producer are not established. |
| `consumer_missing` | An artifact/event is already produced and persisted. | Producer/persistence evidence plus complete consumer census. | **Not used.** No PAO-R4 evidence artifact exists. |
| `verification_missing` | The producer-artifact-bridge-consumer chain is wired. | Executed chain evidence plus absent automated check. | **Not used.** Calling the present state `verification_missing` would presuppose the chain. |
| `implemented_but_not_orchestrated` | A component works in isolation. | Executable component evidence and orchestration absence. | **Not used.** Research design is not implementation. |
| `surface_missing` | An internal capability exists and works. | Internal chain evidence plus absent external surface. | **Not used.** No firewall capability is established. |
| `surface_out_of_scope` | An internal capability exists and external omission is intentional. | Internal chain, rationale, and accountable owner. | **Not used.** There is no internal capability to bound. |
| `semantic_test_missing` | Structural tests pass over an implemented chain. | Passing structural tests plus absence of semantic negatives. | **Not used.** The chain has not reached this stage. |

### Present classification

The PAO-R4-specific vocabulary, export gate, consumer purpose gate, complete returning-evidence
contract, reconciliation owner, and sequence-level composition check are
**`absent/unallocated`**. This phrase is not one of the capability-reality labels; it is used because
the prerequisites for those labels are not met. This follows the architect correction in the
public-verification act, where a proposed but nonexistent controlled transcript was corrected from
`contract_only` to `absent/unallocated`
(`policy-engine/docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md:269-302@1a7a2d05ebba22fae80e9934329e4b880806588e`).

## 3. Capability-by-capability handoff

### 3.1 Individual-use purpose vocabulary

**Extends:** core authority-purpose/denied-use contracts.

**Consumes:** the prohibited-use matrix in the primary report.

**Must produce later:** a canonical, reviewed vocabulary that can express eligibility, amount,
sanction, profiling, priority, investigation, credibility, routing, evidence weighting, reasons,
review intensity, material recommendation, and final determination.

**Acceptance signal:** every carrier and consumer uses the same purpose identity; a synonym cannot
bypass the gate; no denied use shrinks under projection or derivation.

**Present state:** absent/unallocated.

### 3.2 Export classification and refusal gate

**Extends:** `runtime/quality/public_export.py`; no second exporter.

**Input semantics:** artifact class, population basis, subject-resolution surface, executable-rule
surface, denied-use union, declared purpose/consumer, controlled release history, and returning-
evidence requirement.

**Verdicts:** bounded results from the falsifier suite; no new global status lattice.

**Acceptance signal:** F-02, F-03, F-05, F-06, and F-09 exercise the real exporter and fail red.

**Present state:** absent/unallocated. The generic public-export producer exists, but the PAO-R4 gate
does not.

### 3.3 Consumer-side purpose/material-contribution gate

**Extends:** no PolicyOS case-system implementation; this is an INTEGRATE contract with a named
external case-management consumer.

**Input semantics:** exact artifact/derivation digest, subject reference, protected action, declared
purpose, decision stage, and material-contribution test.

**Acceptance signal:** F-01 and F-07 block before the protected action and return the attempt.

**Present state:** absent/unallocated; `producer_missing` is premature because no real consumer
contract is admitted.

### 3.4 Returning-evidence intake and reconciliation

**Extends:** PolicyOS runtime-quality/custody evidence intake; it does not design the case system.

**Evidence semantics:** issued artifacts, imports, derivations, use attempts, protected actions,
consumer verdicts, human/counterfactual reliance, outcome/reason refs, versions, event times,
complete denominators, and independent reconciliation.

**Failure behavior:** absent, late, contradictory, sampled, unresolved, or self-attested-only evidence
returns `FIREWALL_CLAIM_NOT_ESTABLISHED` and blocks any positive application claim.

**Acceptance signal:** the denominator reconciles against a competent independent case-event source;
voluntary silence cannot pass F-06.

**Present state:** absent/unallocated.

### 3.5 Composition and reconstruction boundary

**Extends:** the existing projection/release-history direction; consumes `PV-K06` exact-or-proved-
conservative safety and the controlled transcript dependency, without designing GY-N12.

**Acceptance signal:** F-02 and F-05 fail using the complete controlled history; incomplete history
returns `not_established`.

**Present state:** absent/unallocated; no second chronology owner is authorized.

## 4. Dependencies and isolation

- **`PAO-R36`:** a corrected/superseding record may not carry a weaker individual-use restriction
  than the predecessor. PAO-R36 owns correction, notice, and supersession mechanics.
- **`OPS-R14`:** any durable evidence, recovery, retention, expiry, or legal-hold properties required
  by the future chain are interface dependencies. PAO-R4 sets none.
- **`S0-GAP-02`:** independent benchmark-oracle architecture is outside this task. A later firewall
  verifier may consume its independence principles only after an architecture decision; PAO-R4
  designs no oracle.

No shared wave-4 surface is claimed beyond the restriction-survival interface above.

## 5. Open questions for consolidation

### 5.1 Engineering

| ID | Question | Why open | Closure evidence |
|---|---|---|---|
| `ENG-01` | What is the smallest canonical purpose vocabulary that covers all material individual uses without string/synonym bypass? | The source has no individual-decision concept. | Owner decision, typed values, mapping rules, and synonym/adversarial tests. |
| `ENG-02` | How is non-executability decided across code, tables, trees, prompts, and prose? | Field-name checks invite P29/P33 failure. | Behavioral evaluator over equivalent representations. |
| `ENG-03` | What controlled-history interface lets export and query gates evaluate composition without creating a second GY-N12 owner? | F-02/F-05 need sequence context. | Accepted interface to the canonical transcript and exact/proved-conservative evaluator. |
| `ENG-04` | How are case-event denominators reconciled without exposing identities to PolicyOS or the public? | Completeness and minimization pull in opposite directions. | Privacy/security review, stable scoped references, independent totals, and mismatch tests. |
| `ENG-05` | What event makes material contribution decidable for human-mediated decisions? | “Displayed” is weaker than relied upon; self-report can be circular. | Counterfactual/procedural evidence model and seeded rubber-stamp tests. |
| `ENG-06` | How do uncontrolled copies and screenshots alter the export decision? | Some classes become unobservable once readable. | Explicit channel model and refusal conditions; no unsupported prevention claim. |

### 5.2 Institutional

| ID | Question | Why open | Closure evidence |
|---|---|---|---|
| `INST-01` | Which external case-system owner accepts mandatory purpose gating and complete evidence return? | No technical contract can appoint or compel it. | Named mandate, operating agreement, system boundary, and enforcement evidence. |
| `INST-02` | Who is competent to classify protected action and material contribution for each administrative domain? | Technical labels cannot manufacture legal/administrative competence. | Scoped role, qualifications, abstention/conflict rules, and review path. |
| `INST-03` | Which independent source establishes the denominator of protected case actions? | Consumer self-counting cannot prove completeness. | Independent event owner, reconciliation procedure, and discrepancy handling. |
| `INST-04` | What sanctions or operational consequences attach to missing or false returning evidence? | Mandatory-in-prose can remain voluntary in practice. | Enforceable agreement, audit rights, suspension rule, and incident evidence. |
| `INST-05` | What affected-person review/contestability safeguards apply inside the case system? | Important but outside PolicyOS anti-roles. | External procedure and competence evidence; PolicyOS consumes only bounded implementation evidence. |

### 5.3 Additional research

| ID | Question | Research need | Candidate method |
|---|---|---|---|
| `RES-01` | Which artifact classes are provably non-individually-actionable under realistic auxiliary information? | “Anonymized” and “aggregate” are model-relative. | Reconstruction experiments, exact finite models, and proved no-false-safe abstractions. |
| `RES-02` | Can material contribution be inferred reliably without asking the decision maker? | Self-report and UI events may understate reliance. | Randomized removal studies in synthetic case workflows, causal instrumentation, and bounded error analysis. |
| `RES-03` | What query-sequence controls are sufficient under adaptive consumers? | Local safety does not compose automatically. | Adaptive disclosure models with prospectively enforced transcripts; consume PV-K07/PV-K08 boundaries. |
| `RES-04` | How should reference-class uncertainty be represented when several plausible classes give different base rates? | One chosen class can silently determine an individual score. | Set-valued predictions and decision-theoretic abstention studies. |
| `RES-05` | What evidence distinguishes legitimate general-rule implementation from prohibited statistical generalization in a case? | Both can be mechanically applicable to a person. | Formal rule/basis taxonomy and worked administrative-law cases across jurisdictions. |

## 6. Result standing

**`GO_WITH_REVISIONS`.** The research contract is narrow, checkable, and identifies classes that
must be refused. Revision is required before any capability claim because the purpose vocabulary,
export gate, external consumer contract, returning-evidence chain, and composition transcript are
absent/unallocated. No implementation or owner appointment follows.
