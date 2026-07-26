---
title: PAO-R1 Contradiction and Consistency Ledger
status: draft_audit
kind: research-audit
research_task: PAO-R1
source_report_status: delivered
source_report_result_type: accepted_narrow_scope
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
pao_r0_audit_commit: 258aa740efcfb9e6771bfe52d4fdabc6b74f93a7
audit_date: 2026-07-26
audit_branch: research/pao-r1-independent-audit
authoritative_for:
  - repository audit findings at the recorded commits
  - recommended corrections to the PAO-R1 research artifact
may_not_use_for:
  - production capability claim
  - legal or institutional authority allocation
  - final code contract
  - production implementation authorization
  - automatic boundary adjudication
  - direct modification of authoritative plans
  - proof that an external institution performed a function
research_only: true
---

# PAO-R1 Contradiction and Consistency Ledger

Both repository baselines resolve to the same SHA. “Historical” and “current”
verdicts are therefore identical in every repository row below.

## Internal contradictions

| ID | Report locations | Contradiction | Consequence | Severity | Required correction |
| --- | --- | --- | --- | --- | --- |
| IC-01 | Executive Finding vs §§4.3, 7.1 | “At least four” ownership fields expands to operator, owner state, producer, adapter, consumer, reaction, projection, canonical owner, candidate owner and review owners | Ownership, roles and capability completeness are conflated | High | Use the nine-role analytical model in the main audit and remove `owner_state` |
| IC-02 | Four zones; §§4.2, 4.6, 9.6; Appendix C | Appeal, payment, service, procurement, records and other execution is labelled both `I` and an anti-role/OUT execution | `I` can be misread as PolicyOS execution ownership | Critical | Represent external act separately from its evidence interface |
| IC-03 | §§2.10, 4.11 vs §7.3 | “Family-native payloads/common port” and rejection of universal `ExternalEvent` conflict with a universal envelope carrying payload, admission and reaction | P13/P27 gravity well | High | Remove universal envelope; compose by reference |
| IC-04 | §§2.3, 4.7–4.9, 7.1–7.5 | “No second status lattice” conflicts with evidence, boundary-decision, owner and implementation state systems | Parallel authority/governance workflows | Critical | Keep audit labels non-runtime; map canonical states or defer |
| IC-05 | Frontmatter/§9.1 vs Executive, §§4.10, 10, Appendix G | `research_only` and no authority grant conflict with “Stage-0 adjudication baseline,” “freeze now,” mandatory constraints and task reclassifications | Unratified research becomes binding | High | Replace binding/freeze language with proposed guidance requiring acceptance |
| IC-06 | §§1.6, 2.9 vs §§4.3, 7.1, 7.3 | `policy_matter_ref` is an external assumption but is a standard subject/row field | PAO-R0 schema and owner silently pre-decided | High | Keep optional adapter reference pending PAO-R0 consolidation |
| IC-07 | §4.3 steps 7–9 vs §7.3 | External evidence artifact includes affected claims and required reaction | External producer appears to choose PolicyOS consequence | Critical | Separate source artifact, admission receipt and consumer reaction |
| IC-08 | §4.9 mass-impact vs §§2.9, 10 | Mandatory freeze invokes future OPS-R2 before its dependency graph is researched | Active research pre-empted | High | State desired safety property only |
| IC-09 | §4.9 review cadence vs source standing | Quarterly review has no ratified repository or institutional basis | New governance obligation | Medium | Make event-triggered review a recommendation; cadence unresolved |
| IC-10 | §4.5 vs Appendix C states | “Current implementation vocabulary” omits documented/fixture/producer/artifact/consumer/out-of-scope states and C rows introduce undefined aliases | Capability labels are not normalized | High | Use repository capability-reality vocabulary exactly |
| IC-11 | §4.4 vs Appendix C | Owner state says it is separate from implementation state, but `PI`, `MB`, `CO`, `PM`, `SM`, `BM` mix them | Misleading owner conclusions | High | Delete compound abbreviations and record independent dimensions |
| IC-12 | Direct answer 13 vs OPS-R4 | Ten clocks are called required while OPS-R4 owns the clock vocabulary | Premature temporal contract | High | Require semantic role preservation only |
| IC-13 | §4.8/7.4 | Generic absence grammar locates block/recompute/withdraw in evidence contract despite consumer-specific materiality | Overblocking and wrong owner | High | Evidence contract records condition; consumer owns reaction |
| IC-14 | §4.6/Appendix C | One row is declared “normalized” while still combining function, claims, operator, owner state, contract, absence, reaction and surface | Combinatorial duplication | Medium | Normalize into linked objects |
| IC-15 | Appendix E | Deferred review contains active OPS-R14 and active narrow PAO-R36 | Status ledger corruption | High | Move them to an overlap section |
| IC-16 | §2.1 | `honest-diagnostics-substrate.md` described as missing/renamed | False repository fact | Medium | State both files exist |
| IC-17 | Appendix E/backlog premise | Prior Rev-1 is said to be in Git history | Audit source is not reproducible | High | Mark previous revision unavailable |

## Undefined and malformed references

| Reference | Where used | Finding | Disposition |
| --- | --- | --- | --- |
| `E`, `A`, `I`, `PR`, `FIN` lifecycle codes | All Appendix-C rows | No lifecycle legend; `I` collides visually with INTEGRATE | Define only as report shorthand or remove |
| `IBO` | PD-02/08/09/13/14 and other rows | Undefined; appears to mean implemented-but-not-orchestrated | Replace with exact capability state |
| `CO` | PD-20/27, ML-15–17, SEC-19 and others | Undefined; appears to mean contract-only | Replace |
| `PM` | PD-20, ML-15–17, PR-07, SEC-19 | Undefined; appears to mean producer-missing or planned | Split exact state |
| `SM` | PD-12/18, PR-02/03/07 | Undefined; appears to mean surface-missing | Replace |
| `BM` | PD-22/23 | Undefined; appears to mean bridge-missing | Replace |
| `PI/CO`, `CO/PM`, `EI/PI` | Multiple rows | Slash joins unrelated dimensions without semantics | Record independent fields |
| `M31` in failure-pattern column | BND-032 | M31 is a distillation move, not a registered P-number | Cite M31 separately; use P04/P05/P10/P32 as appropriate |
| `policy_matter_ref` | Common envelope/register | No repository symbol at either baseline | Keep external dependency only |
| `BoundaryDecisionChallengeReceipt` | §4.9/7.5 | No repository owner, type, producer or workflow | Research proposal only |
| `accepted_narrow_scope` boundary state | §4.9/7.1 | Research result label imported into proposed runtime/governance workflow | Do not make a runtime state |

## Duplicate and overlapping register rows

These are semantic overlaps, not necessarily textual duplicates. A normalized
register should link one act to multiple views rather than copy it.

| Cluster | Rows | Required action |
| --- | --- | --- |
| Appeal adjudication | LG-16, AP-14, IR-09 | One jurisdiction-scoped external act; link legal, procedure and incident/recourse views |
| Appeal outcome publication/intake | AP-13, AP-22, IR-08 | Separate intake, external publication, evidence receipt and admission |
| Remedy authorization | LG-17, AP-17, IR-12 | One external authorization act with family-specific remedy payload |
| Remedy execution | AP-18, IR-17/19, ML-21 | Separate service/payment execution from status evidence and PolicyOS reaction |
| Legal hold | LG-18, PR-19 | One external hold decision; PolicyOS preservation reaction separate |
| Procurement | IM-06, FIN-10 | Merge act definition; link implementation/fiscal claims |
| Supplier operations | IM-07/08, FIN-13/16–19 | Normalize contract, performance, rights, expiry and exit objects |
| Payment/compensation | IR-13, FIN-05, FIN-09 | One payment-stage model; compensation purpose is not a separate settlement primitive |
| Internal incident intake | ML-10, IR-01 | One DDM/security event with multiple consumers |
| External incident intake | ML-11, IR-02 | One external report plus admission |
| Incident validation/classification | ML-12, IR-03/05 | Split investigator finding, official classification and public-harm finding |
| Public correction/supersession | PD-16/18, PR-03/04/07, IR-10 | Canonical lifecycle event with multiple projections |
| Audit/oversight | ML-08, ORG-15/16/18/19 | Keep family-native evaluation, audit, ombudsman and judicial outcomes separate |
| Hosting/continuity | IM-20–22, SEC-11–13, EC-19 | Split external operating status from internal custody/degradation state |

## Failure-pattern correction table

The actual register is identical at both baselines. “Correct concept?” evaluates
the supplied fixture's unsafe outcome, not merely whether the P-number exists.

| Report usage | Actual historical/current pattern | Correct concept? | Correct ID? | Required correction |
| --- | --- | --- | --- | --- |
| P01 in BND-039 | Contract-only capability | Partly: missing absence behavior is an incomplete chain | Yes, with P10 | Keep P01; add P10/P32 |
| P03 in BND-007/017/034 | Internal richness with poor external surface | BND-034 yes; BND-007/017 primarily authority dilution | Partial | Use P05 for projection minting; retain P03 for stale/absent surface |
| P04 in BND-011/032 | Status enum proliferation | BND-011 broad-function decomposition is not status proliferation; BND-032 averaging outcomes is closer to M31/P04 | Partial | BND-011 use P31/P13; BND-032 use P04/P05/P10 and cite M31 separately |
| P05 in BND-001/004/007/013/017/019/025/036/038 | Authority dilution | Most are correct | Mostly | Keep; add more specific P32/P10 where signature/form is the bypass |
| P07 in BND-030/040 | Schema versioning without rule evolution | Historical replay/supersession is related but broader than schema evolution | Partial | Use P07 with P08 and explicit append-only lifecycle invariant |
| P08 in BND-006/010/022/028/030/040 | Time semantics fragmentation | Correct for vintage/effective/replay; weak for payment reversal and legal hold | Partial | BND-006 add lifecycle/supersession; BND-028 use P10/P32 plus records rule |
| P09 in BND-027 | Implicit soft gates | Expiry-as-silent-runtime-error fits warning lifecycle | Yes | Keep |
| P10 in BND-002/003/005/009/023/029/039 | Structural-only validation | Correct for markers/status without semantic proof | Yes | Keep; combine with P32 for missing/signed/form evidence |
| P13 in BND-001/008/012/015/020/024/035/037 | Contract gravity well | The report uses P13 as “scope inflation”; the exact register concerns disproportionate contract gravity | No/extended | Call scope inflation an identity-decision anti-role; use P13 only where a contract/workflow becomes a gravity well |
| P14 in BND-005/026 | Raw evidence count inflation | Stage collapse/vendor independence are not evidence-count inflation | No | BND-005 use P05/P10; BND-026 use P05/P29/P32 and independence requirement |
| P15 in BND-014 | LLM speculation laundering | Capture signal may be non-LLM; observation laundering is broader | Partial | Use P05/P10; retain P15 only if the producer is LLM |
| P19 in BND-015 | Aggregation laundering | Correct for individual/aggregate scope drift | Yes | Keep |
| P24 in BND-021 | Strategic-response laundering | KPI auto-adaptation is action laundering, not necessarily strategic-response transport | No | Use P05/P10 plus INT-R4 safe-learning rule; P24 only with behavioral response |
| P26 in BND-002 | Responsibility-integrity laundering | Missing forum/recourse can gesture responsibility to a nonexistent human/institution | Yes | Keep with P10 |
| P27 in BND-016 | Canonical-owner bypass | Exact | Yes | Keep |
| P29 in BND-031 | Authorial proof/self-attested artifact | Duplicate-event idempotency is not self-attested proof | No | Use P31 plus idempotency/replay contract; P29 only if the event self-proves execution |
| P31 in BND-011 | Instance patching over structural invariant | Broad-family decomposition can need a shared chokepoint, but P31 is not “broad row” generally | Partial | Use P31 for bypass-proof common intake/emission, not function granularity itself |
| P32 in BND-018/020/028/033 | Trust-by-form | Strong for signed wrong scope and purpose-reused identity; weak for general correction/hold | Partial | Keep for BND-018/033; BND-020 use lifecycle/replay; BND-028 use records semantics |
| M31 in BND-032 | Distillation move: heterogeneous-authority axis separation | Concept relevant | **No: not a failure pattern** | Move to “distillation moves”; use registered P04/P05/P10 |

## Task-status consistency

| Entry | Supplied treatment | Repository treatment | Verdict |
| --- | --- | --- | --- |
| PAO-R31 | Reclassify V/I | Deferred `OBSERVE` | Plausible recommendation; cannot reclassify |
| PAO-R35 | Trigger insufficient; require statutory operator | Deferred trigger is institutional demand | Useful trigger critique; backlog update requires owner acceptance |
| PAO-R40 | V signals/O reaction; refine trigger | Deferred `OWN-adjacent`, post-pilot | Material reclassification; proposed only |
| PAO-R23 | Split OUT execution vs V/I effects | Deferred | Strong decomposition; proposed only |
| PAO-R32 | Split OWN display/custody vs I degraded status | Deferred | Strong decomposition; proposed only |
| PAO-R34 | OWN sealed admission receipt | Deferred | Premature owner decision; security/records facts missing |
| PAO-R38 | OWN minimum / I archive | Deferred residual after INT-R7 | Directionally consistent; exact 10–30-year owner unresolved |
| PAO-R36 | Active core plus deferred misinformation rider | Active PAO-R36 narrow correction; rider deferred | Remove from deferred-row count |
| OPS-R14 | Listed as “overlap” in deferred appendix | Active | Remove from deferred appendix |

## PAO-R0, identity-decision and current-main conflicts

| PAO-R1 statement | Conflict source | Classification | Correction |
| --- | --- | --- | --- |
| PDC is future PolicyMatter owner | PAO-R0 audit finds owner unestablished | `contradicted_by_pao_r0_audit` | Owner unresolved; PDC candidate only |
| Common `policy_matter_ref` | PAO-R0 namespace/tenant/schema unresolved | `requires_pao_r0_consolidation` | Optional external dependency |
| Ten required clocks | PAO-R0 audit and OPS-R4 | `requires_pao_r0_consolidation` | Defer names/placement |
| Common status/envelope | PAO-R0 parallel-lattice/P27 finding | `consistent_with_pao_r0_audit` | Split and map existing owners |
| Act/interface decomposition | Identity §5 | `confirmed` | Preserve |
| “INTEGRATE external act” without explicit execution prohibition | Identity §5 says function is not ours | `partially_supported` | Add separate external-act execution boundary |
| Atlas as all projection owner | Current Atlas plan and distributed API/publication owners | `contradicted` | Atlas renderer; publication owners distributed |
| Honest diagnostics path missing | Current tree | `contradicted` | Both paths exist |

## Claim-to-evidence ledger

Permalink keys: [ID decision](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md#L88-L139);
[W2 backlog](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md#L428-L460);
[PDC boundary](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/pdc/_impl/layer2_readiness.py#L62-L114);
[RQ envelope](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/runtime/quality/authority.py#L471-L605);
[Fabric source contract](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/src/polisyos/fabric/connectors/contracts/source_contract.py#L382-L470);
[ADR-0170](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/docs/adr/0170-contestability-and-recourse-boundaries.md#L51-L91).

| Claim ID | Report location / atomic claim | Class | Historical/current evidence and verdict | Confidence / severity | Owner / capability / boundary consequence | Problem / exact correction | Runtime limit |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CL-001 | Exec: four-way test is ratified | Repo fact | ID; `confirmed` / `confirmed` | High/info | Architecture decision; documented invariant | None | Implementation compliance not universal |
| CL-002 | Exec: correct unit is five-factor product | Architecture inference | No canonical schema; `partially_supported` | High/medium | Missing owner; research-only | Use linked objects, not a denormalized product row | Corpus review needed |
| CL-003 | Exec: PolicyOS owns admission/reaction | Owner claim | ID + ADR-0170; `confirmed_with_qualification` | High/high | Distributed canonical owners; O | Name actual family owner | Partner bridge unproven |
| CL-004 | Exec: Stage-0 can freeze envelope now | Governance proposal | W2 OPS-R4 + existing owners; `authority_overclaim` | High/high | Conflicting owners | “Candidate for consolidation; not frozen” | Ratification required |
| CL-005 | §1.1: PAO-R1 is Stage-0 anchor | Repo fact | W2; `confirmed` as research sequencing | High/info | Research owner | Add “not authority grant” | None |
| CL-006 | §1.3: full capability chain doctrine | Repo fact | AGENTS/vision; `confirmed` | High/info | Repository governance | None | Per-family proof still required |
| CL-007 | §1.5: register is OWN | Normative proposal | ID supports boundary honesty; `partially_supported` | Medium/medium | Governance artifact owner unresolved | PolicyOS owns boundary disclosure, not necessarily one global runtime register | Institutional acceptance |
| CL-008 | §1.6: PAO-R0 supplies matter ref | Dependency claim | PAO-R0 audit; `owner_not_established` | High/high | Missing/conflicting | Keep optional external assumption | PAO-R0 consolidation |
| CL-009 | §2.1: honest-diagnostics path renamed | Repo fact | Both files present; `contradicted` | High/medium | N/A | State both exist | None |
| CL-010 | §2.3: PDC AuthorityBoundary fields/composition | Repo fact | PDC; `confirmed` | High/info | PDC implemented | Qualify scope to this class | Other families differ |
| CL-011 | §2.3: one canonical authority grammar | Owner claim | Multiple local envelopes; `partially_supported` | High/high | Conflicting/partial | “One-lattice rule; several family contracts require mapping” | Cross-repo runtime behavior |
| CL-012 | §2.4: SourceContract field coverage | Repo fact | Fabric; `confirmed` | High/info | Fabric implemented for data | None | External legal families out of scope |
| CL-013 | §2.4: legal sensing largely implemented | Capability | Lex/Data Forge and plans; `confirmed_with_qualification` | Medium/medium | Split owner; incomplete chain | Separate corpus producer, runtime evaluator, continuous bridge | Live jurisdiction partner |
| CL-014 | §2.4: ADR-0170 appeal split | Repo fact | ADR-0170; `confirmed` | High/info | Contestability partial | Preserve | Partner workflow absent |
| CL-015 | §2.4: external appeal wrapper is runtime-owned | Owner claim | Institutional provenance wrappers; `confirmed_with_qualification` | High/high | Wrapper owner only | Say “PolicyOS owns wrapper, not act” | Producer/bridge absent |
| CL-016 | §2.4: decision validity full lifetime state | Capability | DV/local service; `implemented_but_not_orchestrated` | High/medium | Core/Scientist partial | Keep actual label | Fleet fan-out unproven |
| CL-017 | §2.4: KPI owner partial | Capability | DDM/monitoring records; `confirmed_with_qualification` | High/medium | DDM/OPS-R5 partial | Observation/diagnosis split | Partner data flow |
| CL-018 | §2.4: core audit is portable/offline | Capability | Core audit tests; `confirmed` | High/info | Core audit implemented | Add “package, not opinion” | External auditor independent judgment |
| CL-019 | §2.4: auth allow is not execution | Repo fact | Access-audit docstring; `confirmed` | High/info | Runtime HTTP implemented | Preserve unchanged | Handler/external outcome not proved |
| CL-020 | §2.4: Atlas never produces authority | Architecture claim | Constitution yes; active plan records violations; `confirmed_with_qualification` | High/high | Distributed surface owner | Doctrine true; implementation has known debt | Full frontend runtime not run |
| CL-021 | §2.5: named reusable test families exist | Test claim | Exact tests found; `confirmed_with_qualification` | High/medium | Multiple owners | Cite exact symbols; none tests whole boundary register | Blocked runtime suites |
| CL-022 | §2.6: no OperationalBoundaryDecision | Absence | Exact/case-insensitive search, only backlog hit; `confirmed` | High/info | Missing | Add bounded search statement | Hidden deployments |
| CL-023 | §2.6: compensation.py is rollback | Repo fact | File semantics; `confirmed` | High/info | Scientist orchestration | Preserve | UI leak not dynamically tested |
| CL-024 | §2.6: no notification/payment/service operators | Absence | Searches find plans/models/UI only; `confirmed_with_qualification` | Medium/medium | External | Say “no inspected production operator” | Partner code/runtime |
| CL-025 | §2.7: PDC is purpose authority owner | Owner | PDC README/class; `confirmed_with_qualification` | High/medium | PDC narrow owner | Not global register owner | Runtime bridge coverage |
| CL-026 | §2.7: RQ+Fabric own external admission | Owner | RQ/Fabric exist; `partially_supported` | High/high | Partial/conflicting | Candidate components, family owners retain semantics | Cross-family tests absent |
| CL-027 | §2.7: Lex owns legal sensing | Owner | Lex/Data Forge split; `partially_supported` | High/high | Split owner | Name Data Forge production owner | Live cadence |
| CL-028 | §2.7: Atlas public projection owner | Owner | Distributed publication chain; `owner_not_established` | High/high | Conflicting | Atlas renderer/consumer | Surface inventory evolving |
| CL-029 | §2.7: H2 future consumer | Capability | Planned only; `planned_not_implemented` | High/medium | Future | Do not name current owner | No code |
| CL-030 | §2.10: M30 thin port supports envelope | Architecture inference | DIST; `partially_supported` | High/high | Consolidation pending | Common references, not mega-envelope | Owner decision |
| CL-031 | §4.4: five owner states | Contract proposal | No symbols; `premature_contract` | High/medium | Missing | Separate operator grounding/capability | Institutional facts |
| CL-032 | §4.5: implementation vocabulary current | Repo fact | Missing repository labels; `contradicted` | High/high | Audit vocabulary | Use complete capability-reality labels | None |
| CL-033 | §4.7: evidence state list is not lattice | Architecture claim | No mappings; `parallel_lattice_risk` | High/critical | Conflicting state owners | Remove common lifecycle | Transition tests absent |
| CL-034 | §4.8: absence grammar is generic | Contract proposal | Consumer-specific code; `premature_contract` | High/high | Split owners | Condition in receipt; effect in consumer | Materiality/jurisdiction |
| CL-035 | §4.9: boundary governance states | Governance proposal | No owner/workflow; `authority_overclaim` | High/high | Governance missing | Research metadata only | Ratification |
| CL-036 | §4.9: quarterly review | Governance proposal | No basis; `unsupported` | High/medium | Missing | Event triggers recommended; cadence unresolved | Institutional policy |
| CL-037 | §4.9: mass change freezes claims | Capability proposal | OPS-R2 future; `planned_not_implemented` | High/high | Future dependency owner | State desired invariant only | Impact graph absent |
| CL-038 | §4.10: constrains all Wave-2 tasks | Authority claim | Research-only standing; `authority_overclaim` | High/high | Team architecture review only | “Inputs for consolidation” | Acceptance required |
| CL-039 | §7.1: OperationalBoundaryDecision shape | Contract | No implementation; `contract_only` | High/medium | Missing | Research questionnaire only | No producer/consumer |
| CL-040 | §7.3: shared envelope | Contract | RQ/Fabric/PROV overlap; `duplicate_owner_risk` | High/critical | Conflicting | Reject/split | P27 decision |
| CL-041 | §7.4: AbsenceBehavior shape | Contract | No canonical owner; `premature_contract` | High/high | Consumer-specific | Split condition/disposition/reaction | Materiality |
| CL-042 | §7.5: challenge receipt | Governance contract | No workflow; `contract_only` | High/medium | Missing | Optional research comment template | Legal/process authority |
| CL-043 | §7.6: PDC register reference later | Owner inference | PAO-R0 audit; `owner_not_established` | High/high | Conflicting | Defer P27/PAO-R0 | Consolidation |
| CL-044 | §8: artifact routing is existing | Capability | Most bridges/producers missing; `planned_not_implemented` | High/high | Multiple | Label each chain honestly | Partner/runtime |
| CL-045 | §9: governed/production gates | Governance proposal | Not implemented; `research_only` | High/medium | Missing | Keep as candidate promotion criteria | Pilot/ratification |
| CL-046 | Appendix C: 213 rows coherent | Corpus claim | Unique IDs but duplicates/undefined states/mixed planes; `partially_supported` | High/high | Research artifact | Normalize/split/merge per row ledger | Independent adjudication |
| CL-047 | Appendix D: 21 contract families reusable | Architecture claim | Taxonomy useful, contracts duplicate owners; `partially_supported` | High/high | Conflicting | Treat as mapping catalogue | P27/OPS-R4 |
| CL-048 | Appendix E: deferred dispositions faithful | Repo/history claim | Active rows included; Rev-1 absent; `not_reproducible` | High/high | Backlog owner | Advisory crosswalk only | Prior revision unavailable |
| CL-049 | Appendix F: BND fixtures reusable | Fixture claim | No BND symbols; `planned_not_implemented` | High/medium | Future benchmark | Proposal; correct pattern IDs | Runtime corpus absent |
| CL-050 | Appendix G: safe Stage-0 anchor | Governance claim | Small invariant core supported; rest premature; `accepted_narrower_scope` | High/high | Architecture/canonical owners | Freeze only ratified invariant restatements after acceptance | Human review |

External-source claims are audited in the main report. All operator-specific
claims remain `external_verification_required` and usually
`jurisdiction_dependent`/`pilot_dependent`.
