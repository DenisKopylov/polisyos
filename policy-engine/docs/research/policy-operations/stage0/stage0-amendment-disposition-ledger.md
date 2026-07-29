---
title: "Stage-0 Amendment Disposition Ledger"
status: delivered
kind: research-provenance
research_scope:
  - PAO-R0
  - PAO-R1
  - OPS-R15
repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
consolidation_commit: a55d33c7a2ed160fd609b1a9e07d95e0bbb04e19
amendment_branch: research/stage0-anchor-amendments
ledger_date: 2026-07-29
expected_amendment_actions: 60
expected_pao_r0_actions: 20
expected_pao_r1_actions: 18
expected_ops_r15_actions: 22
authoritative_for:
  - disposition of the 60 actions in the Stage-0 research amendment plan
  - source-section compression routing for the three supplied reports
may_not_use_for:
  - acceptance of the Stage-0 consensus kernel
  - production capability claim
  - canonical owner assignment
  - implementation authorization
research_only: true
---

# Stage-0 Amendment Disposition Ledger

## 1. Disposition vocabulary

| Disposition | Meaning |
|---|---|
| `applied_rewrite` | The accepted conclusion was replaced with the audited wording or an equivalent narrower statement |
| `applied_narrowing` | A useful proposition remains after its scope, owner, or capability standing was reduced |
| `retained_as_research` | Material remains useful as a hypothesis, questionnaire, catalogue, or proposed fixture only |
| `deferred_to_owner` | The question was removed from Stage-0 contract standing and routed to its existing or new bounded owner |
| `rejected_from_accepted_result` | The proposed shared contract, state, owner, threshold, or authority claim is not part of the revised result |
| `repository_fix_separate` | A code/test defect is recorded but not turned into a research conclusion or fixed here |
| `historical_source_only` | Detail remains only in the byte-preserved source for research archaeology |

Every action below is implemented in one of the three revised reports. A
disposition does not ratify the revised report; `team-architecture` acceptance
remains required.

## 2. PAO-R0 actions — 20

| ID | Source area | Required correction | Disposition | Revised destination |
|---|---|---|---|---|
| R0-A01 | Frontmatter/result | Replace `accepted_narrow_scope`; add source identity | `applied_rewrite` | Frontmatter and Executive Finding |
| R0-A02 | Executive finding | Separate functional need from owner/schema capability | `applied_rewrite` | Executive Finding |
| R0-A03 | Compatibility freeze | Remove self-granted immediate binding authority | `applied_rewrite` | §1.4 Standing; §9 |
| R0-A04 | PDC canonical owner | Treat PDC as integration neighborhood; owner open | `deferred_to_owner` | Executive; §2.3; §8 S0-GAP-01 |
| R0-A05 | Runtime-quality owner | Downgrade to possible validation bridge | `applied_narrowing` | §2.3 |
| R0-A06 | Core-audit owner | Package canonical events; do not own matter semantics | `applied_narrowing` | §2.3 |
| R0-A07 | PolicyMatter entity/envelope | Keep opaque reference hypothesis; remove accepted schema | `rejected_from_accepted_result` | §4.1–4.2; §7 |
| R0-A08 | Common `support_status` | Separate identity, evidence, authority, resolution, lifecycle | `rejected_from_accepted_result` | §4.3 |
| R0-A09 | Relation semantics | Mark continuity/split/merge adjudication unresolved; no inheritance | `retained_as_research` | §4.4 |
| R0-A10 | Cardinality | Preserve one-to-many and many-to-many compatibility | `applied_rewrite` | Executive; §4.2; §6 |
| R0-A11 | Common envelope | Replace with owner-composition questions | `rejected_from_accepted_result` | §7 |
| R0-A12 | Nine mandatory clocks | Preserve role distinctions; route algebra to OPS-R4 | `deferred_to_owner` | §4.5; §8 |
| R0-A13 | Namespace/tenant | Keep authority scope mandatory; leave namespace/transfer open | `applied_rewrite` | §4.2; §10 |
| R0-A14 | Migration plan | Prohibit reinterpretation; defer production migration | `deferred_to_owner` | §2.2; §4.2; §9 |
| R0-A15 | Sidecar sufficiency | Preserve non-rewrite; sidecar remains unproven candidate | `applied_rewrite` | §4.6 |
| R0-A16 | Public/Atlas capability | Keep renderer doctrine; record incomplete public chain | `repository_fix_separate` | §2.3–2.4; §8 |
| R0-A17 | Lex ownership | Correct to Data Forge legal producer → Lex runtime consumer | `applied_rewrite` | §2.3 |
| R0-A18 | Capability and fixture labels | State missing complete chain; fixtures proposed only | `applied_rewrite` | §2.4; §6 |
| R0-A19 | Failure-pattern mapping | Use exact register concepts | `applied_rewrite` | Pattern pass |
| R0-A20 | External citations | Correct DOI/ARK and use primary official sources | `applied_rewrite` | §3 |

## 3. PAO-R1 actions — 18

| ID | Source area | Required correction | Disposition | Revised destination |
|---|---|---|---|---|
| R1-A01 | Frontmatter/result | Replace Stage-0 baseline standing with `accepted_narrower_scope` | `applied_rewrite` | Frontmatter and Executive Finding |
| R1-A02 | Executive/four zones | Split external act, evidence, admission, reaction, projection | `applied_rewrite` | Executive; §4.1–4.2 |
| R1-A03 | Unit of analysis | Treat planes as linked analytical objects, not one required row | `applied_rewrite` | §1.2; §4.1 |
| R1-A04 | Appendix C, 213 rows | Retain only as non-authoritative census/questionnaire and exemplars | `retained_as_research` | §4.8; frozen source |
| R1-A05 | Owner fields/state | Replace compound owner fields with analytical roles where proven | `applied_rewrite` | §4.4 |
| R1-A06 | Canonical-owner map | Use implemented owner/neighborhood/future/external/unresolved categories | `applied_rewrite` | §2.2; §4.4; §8 |
| R1-A07 | Appendix D EC-01..21 | Recast as research question families | `retained_as_research` | §4.9 |
| R1-A08 | Universal institutional envelope | Replace with family fact + refs + admission + reaction + projection | `rejected_from_accepted_result` | §4.5; §7 |
| R1-A09 | Evidence/boundary/owner workflow states | Remove runtime/canonical implication | `rejected_from_accepted_result` | §2.3; §4.4–4.5 |
| R1-A10 | Ten/five clocks | Require role non-collapse only; defer names to OPS-R4 | `deferred_to_owner` | §4.6; §7–8 |
| R1-A11 | Absence grammar | Split evidence condition/admission from consumer reaction | `applied_rewrite` | §4.6 |
| R1-A12 | OBSERVE transition | Require a new purpose-bound admitted artifact | `applied_rewrite` | §4.7 |
| R1-A13 | Governance/cadence/challenge/freeze | Recast as owner-acceptance proposals | `rejected_from_accepted_result` | §4.10; §9 |
| R1-A14 | `policy_matter_ref` | Remove as common requirement pending S0-GAP-01 | `deferred_to_owner` | §8 |
| R1-A15 | Deferred-task Appendix E | Remove reclassification authority and unreproducible history | `rejected_from_accepted_result` | §8; frozen source |
| R1-A16 | Capability-state vocabulary | Use exact capability-chain reasoning by family | `applied_rewrite` | §2.3 |
| R1-A17 | Failure patterns/fixtures | Correct IDs; mark fixtures proposed and unexecuted | `applied_rewrite` | §6; Pattern pass |
| R1-A18 | External sources | Replace noncanonical W3C/GAO/OECD links and narrow scope | `applied_rewrite` | §3 |

## 4. OPS-R15 actions — 22

| ID | Source area | Required correction | Disposition | Revised destination |
|---|---|---|---|---|
| O15-A01 | Frontmatter/result | Replace executable standing with `blocked_pending_oracle_independence` | `applied_rewrite` | Frontmatter and Executive Finding |
| O15-A02 | Executive finding | Recast 24-month benchmark as scenario catalogue and kernel research | `applied_rewrite` | Executive; §4.5 |
| O15-A03 | Bounded claim | Bind any future pass to revision/environment/fixtures/evaluator | `applied_rewrite` | §1.3 |
| O15-A04 | Frozen calendar | Separate input-only fixtures from sealed expected results | `retained_as_research` | §4.5; §6.1; frozen source |
| O15-A05 | Event vocabulary | Treat names as family discriminators pending machine corpus normalization | `deferred_to_owner` | §2.1; §4.5; §7 |
| O15-A06 | Common event envelope | Permit only input wrapper; remove expected/prohibited/oracle outputs | `rejected_from_accepted_result` | §6.1; §7 |
| O15-A07 | Thirteen clocks | Use family roles/evaluator controls; defer production algebra | `deferred_to_owner` | §4.4 |
| O15-A08 | State machines | Replace exact states with observable predicates | `rejected_from_accepted_result` | §4.1 |
| O15-A09 | Typed wakes | Preserve exact-match/no-authority predicate; defer enum | `applied_narrowing` | CK-02/CK-05 |
| O15-A10 | Twenty resume gates | Require equivalent action-specific protection by phase | `applied_rewrite` | §4.2 |
| O15-A11 | Two graphs/five impact sets | Preserve content/authority distinction; defer physical representation | `applied_narrowing` | §4.3 |
| O15-A12 | `WorldRelease` vector/states | Move to OPS-R8 extension assumptions | `deferred_to_owner` | §4.5; §8 |
| O15-A13 | Matter split/successor truth | Use fixture-local axioms only after S0-GAP-01 | `deferred_to_owner` | §4.5; §8 |
| O15-A14 | External/human outcomes | Mark scenario axioms/contested labels with provenance | `applied_rewrite` | §4.6 |
| O15-A15 | Semantic oracle | Require sealed, independently owned predicates | `rejected_from_accepted_result` | §6.1–6.2 |
| O15-A16 | Clean rebuild | Same-code parity diagnostic; independent declarative evaluator required | `applied_rewrite` | CK-11; §6.2 |
| O15-A17 | Hidden fixtures | Add four-package commitments/access/run model; keep scoring blocked | `applied_rewrite` | §6.1–6.3 |
| O15-A18 | Metrics | Use closed populations; demote efficiency; remove arbitrary cutoffs | `applied_rewrite` | §6.4 |
| O15-A19 | RPO/RTO | Set no Stage-0 production number; route to OPS-R14/deployment evidence | `deferred_to_owner` | §6.4; §8 |
| O15-A20 | Failure-pattern Appendix H | Replace “Detected” with proposed/untested standing | `applied_rewrite` | §5–6; Pattern pass |
| O15-A21 | Contract sketches | Keep benchmark-research artifacts only; no H2 owner/schema | `rejected_from_accepted_result` | §7 |
| O15-A22 | Stage-0 anchor packet | Replace runtime constraints with consensus-aligned semantic kernel | `applied_rewrite` | §4.1; §8–9 |

## 5. Action-count reconciliation

| Report | Planned | Disposed | Unresolved action rows |
|---|---:|---:|---:|
| PAO-R0 | 20 | 20 | 0 |
| PAO-R1 | 18 | 18 | 0 |
| OPS-R15 | 22 | 22 | 0 |
| **Total** | **60** | **60** | **0** |

“Disposed” includes explicit deferral or rejection. It does not mean every open
research question is solved.

## 6. Original-section compression routing

### 6.1 PAO-R0

| Original section family | Revised treatment |
|---|---|
| Executive Finding | Replaced with open-owner result |
| §1 Task and project fit | Compressed; boundary and standing corrected |
| §2 Repository baseline | Retained with owner/capability and defect corrections |
| §3 External research | Compressed to primary-source-supported separations |
| §4 Result | Rewritten as identity hypothesis and compatibility guidance |
| §5 Counterexamples | Retained and narrowed to observable falsifiers |
| §6 Benchmark/fixtures | Retained as proposed, non-executable profiles |
| §7 Artifact sketches | Production-like schemas rejected; questionnaire retained |
| §8 Handoff | Rewritten around S0-GAP-01 and existing task owners |
| §9 Promotion/kill | Rewritten without self-granted freeze authority |
| §10 Open questions | Retained and narrowed |
| Appendices A–C | Evidence and decision tables compressed; full versions remain source-only |
| Appendix D compatibility freeze | Converted from “immediately binding” to research guidance |
| Appendix E fixture catalogue | Compressed to profiles; full catalogue source-only |
| Final posture | Replaced by `research_supported_with_open_owner` |

### 6.2 PAO-R1

| Original section family | Revised treatment |
|---|---|
| Executive/four zones | Replaced by five-plane method |
| §1 Task and project fit | Compressed with narrower standing |
| §2 Repository baseline | Corrected owner and capability roles |
| §3 External research | Corrected canonical sources and jurisdiction scope |
| §4 Result | Rewritten as questionnaire, composition method, and exemplars |
| §5 Counterexamples | Retained as semantic anti-overclaim cases |
| §6 Benchmark/fixtures | Retained as proposed/unexecuted properties |
| §7 Artifact sketches | Universal envelope and runtime schemas rejected |
| §8 Handoff | Rewritten to canonical tasks/owners |
| §9 Promotion/kill | Rewritten without governance authority |
| §10/Open direct answers | Consolidated into result and open questions |
| Appendix A repository evidence | Compressed into corrected baseline |
| Appendix B external sources | Compressed with canonical links |
| Appendix C 213-row register | Historical source plus 15 candidate exemplars |
| Appendix D EC-01..21 | Retained as research family questions |
| Appendix E deferred activation | Task-reclassification authority removed |
| Appendix F fixtures | Proposed/unexecuted status retained |
| Appendix G anchor packet | Replaced by five-plane method and consensus handoff |
| Final posture | Replaced by `accepted_narrower_scope` |

### 6.3 OPS-R15

| Original section family | Revised treatment |
|---|---|
| Executive Finding | Replaced with oracle-independence blocker |
| §1 Task and project fit | Compressed with bounded pass claim |
| §2 Repository baseline | Retained with no-runner/no-oracle capability qualification |
| §3 External research | Compressed to patterns that grant no repository authority |
| §4 Result | Runtime states/contracts replaced by CK-01..CK-16 predicates |
| §5 Counterexamples | Retained as observable failure cases |
| §6 Benchmark/fixtures | Rewritten as independent four-package architecture |
| §7 Artifact sketches | Runtime/H2 schemas rejected; benchmark-research interfaces retained |
| §8 Handoff | Reallocated to task-owned profiles |
| §9 Promotion/kill | Scoring blocked pending independent oracle/evaluator |
| §10 Open questions | Narrowed to benchmark governance and domain dependencies |
| Appendix A repository evidence | Compressed into baseline |
| Appendix B external sources | Compressed into primary-source pattern map |
| Appendix C 24-month calendar | Preserved source-only as scenario catalogue |
| Appendix D actor registry | Scenario axioms; external competence not established |
| Appendix E event dictionary | Normalization deferred to benchmark engineering |
| Appendix F fault matrix | Retained as proposed mutations |
| Appendix G visible expected states | Removed from implementation-visible design; future sealed package |
| Appendix H failure patterns | Corrected to proposed/untested |
| Appendix I Stage-0 packet | Replaced by semantic kernel; runtime prescriptions rejected |
| Appendix J final posture | Replaced by `blocked_pending_oracle_independence` |

## 7. Cross-anchor transitive consistency

| Consolidated decision | PAO-R0 effect | PAO-R1 effect | OPS-R15 effect |
|---|---|---|---|
| Subject owner remains open | No PDC owner freeze | No mandatory matter field | Fixture-local subject only |
| Universal envelope rejected | No support envelope | No institutional envelope | Input-only benchmark wrapper |
| Parallel states rejected | Concepts separated | Analytical roles only | Observable predicates |
| Clock algebra belongs to OPS-R4 | No nine-field bundle | No ten/five-field bundle | No thirteen-field bundle |
| Census is a method | External-evidence distinction only | 213 rows non-authoritative | Census cannot become oracle truth |
| Oracle independence blocked | Fixtures proposed | BND cases proposed | No executable/pass claim |
| Atlas renders upstream state | Public owner remains unresolved | Projection owner distinguished from renderer | Controlled surfaces inspect canonical projections |
| Public correction incomplete | Sidecar not sufficient | Exact public states deferred | CK-13 depends on PAO-R36/Atlas |
| External acts remain external | Continuity evidence may be integrated | Five-plane decomposition | CK-14 forbids anti-role execution |

## 8. Open obligations after amendment

The 60 editorial/research amendments are disposed, but the following remain
deliberately open:

- S0-K01–S0-K16 require acceptance or amendment by `team-architecture`;
- S0-GAP-01 must decide the minimum subject reference and semantic owner;
- S0-GAP-02 must decide oracle/evaluator independence and benchmark governance;
- OPS-R2, OPS-R4, INT-R5, PAO-R36, INT-R7/INT-R8, OPS-R14, and pilot tasks retain
  their existing questions;
- five recorded repository defects require separate engineering ownership;
- external institutional competence and legal effect require jurisdiction and
  partner evidence.
