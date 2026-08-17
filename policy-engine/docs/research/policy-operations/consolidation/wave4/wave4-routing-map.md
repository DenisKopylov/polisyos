---
title: Wave 4 — routing map
status: delivered_consolidation
kind: research_consolidation_routing_map
research_scope: [OPS-R14, PAO-R36, PAO-R4, S0-GAP-02]
repository_branch: research/wave4-consolidation
orientation_commit: 610e485569da8b5b13afd767ae52b29d3f2c8e95
documentation_pin: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
inspection_date: 2026-08-17
research_only: true
typed_agenda_counts:
  engineering: 27
  institutional: 21
  further_research: 19
pao_r36_shape: owner_first_integration_map_plus_four_dependency_declarations
may_not_use_for:
  - ratification
  - package repair or mutation
  - production implementation authorization
  - owner appointment
  - capability claim
  - permission to publish, sign, score, promote, or open a gate
  - claim that OPS-R15 is unblocked
  - automatic amendment of AGENTS.md, the pattern register, a plan, backlog, or system-design decision
---

# Wave 4 routing map

## 1. Routing rule

A route names the destination that already owns the decision, or states **no owner exists**. A plausible nearby lane is not an owner. This map does not edit the destination and does not appoint anyone.

The typed agenda re-derives exactly:

- OPS-R14: 8 engineering · 7 institutional · 6 further research;
- PAO-R4: 7 engineering · 5 institutional · 4 further research;
- S0-GAP-02: 12 engineering · 9 institutional · 9 further research;
- total: **27 engineering · 21 institutional · 19 further research**.

PAO-R36 is intentionally not forced into those three tables. It contributes an owner-first integration map and four dependency declarations; those are routed separately in §7.

## 2. Destination registry

| Route | Destination | Owner status | What may be decided there |
| --- | --- | --- | --- |
| `RC-CENSUS` | `wave4-ratification-candidates.md` — holder-relative census attribution proposition | later ratification act | Whether consolidation-level recomputation may settle the six zeroes while package-level claims remain `institutionally_supplied`. |
| `RC-P37` | `wave4-ratification-candidates.md` — registered-five/sub-annotation proposition | later ratification act | Five fixed labels; three required sub-annotations; every condition added to preserve a positive becomes a separately classified gate predicate. |
| `RC-STANDING` | `wave4-ratification-candidates.md` — three-axis standing proposition | later ratification act | `research_standing` / `capability_standing` / `gate_standing`, with the gate axis meaning first-public-signature. |
| `RC-F14` | `wave4-ratification-candidates.md` — F-14 disposition proposition | later ratification act | Withdraw `F-14A`; preserve `F-14B`; allow a positive to return only from a genuinely disjoint-custody provenance record. |
| `AGENTS-STANDING` | `AGENTS.md` | root governance owner | Register the three-axis standing shape after ratification. |
| `REGISTER-P37` | `AGENTS.md` and `policy-engine/docs/reference/policy-design-case-failure-patterns.md` beside `P37` | root governance / `team-policyos-runtime` | Register the condition-created-predicate rule and the P37 sub-annotation contract after ratification. |
| `REGISTER-P38` | same register and `AGENTS.md` | root governance / `team-policyos-runtime` | Register `P38`; it is cited by GY and Atlas plans but absent from both canonical registers at the documentation pin. |
| `GY-N12` | `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md` | existing GY currentness/epoch lane | Current head, epoch, stale/revalidation/reissue/withdrawal chronology; no second chronology owner. |
| `ATLAS-DS12` | `policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md` | existing surface consumer | Render governed verification/correction outputs after producer and gate evidence exists; never mint authority. |
| `WAVE2-BACKLOG` | `policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md` | `team-architecture` for research sequencing only | Record non-blocking later research and dependency order; it is not an implementation owner. |
| `INT-R6` | Wave-5 `INT-R6` row in the Wave-2 backlog | research owner not yet executed | Multilingual authority-equivalence research. It is fail-closed and not on the first-milestone path. |
| `INT-R7` | delivered INT-R7 terminal profile and ratification records | delivered research owner | Five public-verification dimensions, latest-snapshot rule, obtainability, succession, and pre-issuance evidence gate. |
| `RULE-EVOLUTION` | canonical `core/contracts/rule_evolution.py` owner, reached through a future implementation plan | existing source owner | Append-only predecessor/successor relation; no parallel correction chronology. |
| `PROJECTION` | canonical `runtime/quality/projection_semantics.py` owner, reached through a future implementation plan | existing source owner | Four-audience correction projection and restriction monotonicity. |
| `PUBLIC-EXPORT` | canonical `runtime/quality/public_export.py` plus HTTP response consumer | bounded existing endpoints | Public bundle producer/consumer relation; generic bridge is missing, correction specialization absent. |
| `H2-PLAN-MISSING` | future H2 custody-runtime implementation plan named by the Wave-2 backlog | **no owner exists; no plan exists** | OPS-R14 durability/hold/replay and most PAO-R4 governed case-handoff implementation work. This route records the missing owner rather than assigning a nearby lane. |
| `S0-OPS15-GAP` | S0-GAP-02 / OPS-R15 scoring dependency in the Wave-2 backlog | research architecture exists; implementation/institutional owners absent | Independent benchmark-oracle implementation and custody evidence. No scoring unblock follows. |
| `INSTITUTION-NONE` | institutional decision record to be created by a competent authority | **no owner exists** | Mandates, competence, legal applicability, institutional custody, signers, reviewer/evaluator bodies, and operating agreements. |
| `LATER-RESEARCH` | Wave-2 backlog under `team-architecture` | named research-sequencing owner; not first-milestone blocking | Empirical/formal studies whose conservative fail-closed alternative is already specified. |

## 3. Deduplicated route clusters

| Cluster | Consolidated subject | Source members | Route |
| --- | --- | --- | --- |
| `C-01` | Census execution, holder-relative attribution, and zero claims | OPS-R14 census; PAO-R36 census; PAO-R4 census; S0-GAP-02 census | `RC-CENSUS`; five package correction sites are recorded, not edited. |
| `C-02` | Gate-predicate provenance, independence, and common-mode evidence | OPS ENG-01/07/08; PAO-R4 ENG-03/06; S0 ENG-02/03/09/11/12; F-14A; `machine_observed` | `RC-P37` → `REGISTER-P37`; implementation portions also need `H2-PLAN-MISSING` or `S0-OPS15-GAP`. |
| `C-03` | Research/capability/gate standing separation | all four package standings | `RC-STANDING` → `AGENTS-STANDING`. |
| `C-04` | Succession provenance and custody independence | OPS ENG-01/08, INST-01/03/07, RES-05; F-14A | `RC-F14`; engineering to `H2-PLAN-MISSING`; institutional decisions to `INSTITUTION-NONE`. |
| `C-05` | One append-only currentness/epoch/reissue chronology | OPS ENG-04; PAO-R36 current-head dependency; correction currentness; historical replay | `GY-N12`; no second owner. |
| `C-06` | Durable event/evidence journal, replay, holds, and recovery | OPS ENG-02/03/06/07; PAO-R4 ENG-05/06/07; PAO-R36 archive/receipt rows | `H2-PLAN-MISSING`, extending canonical owners after the plan exists. |
| `C-07` | Correction transaction, notice, fan-out, surfaces, receipts, and feeds | PAO-R36 owner-first map; OPS↔PAO seam | `RULE-EVOLUTION`, `PROJECTION`, `PUBLIC-EXPORT`, `GY-N12`, `INT-R7`; unbuilt specialization remains absent/unallocated. |
| `C-08` | Policy-to-case semantic firewall and emission chokepoint | PAO-R4 ENG-01..07 and institutional questions | `H2-PLAN-MISSING`; `ENG-01` has **no owner exists** until a separate architecture decision selects the canonical chokepoint. |
| `C-09` | Independent benchmark oracle and specification assurance | S0 ENG-01..12 and INST-Q01..Q09 | `S0-OPS15-GAP`; institutional roles remain `INSTITUTION-NONE`. |
| `C-10` | Multilingual authority parity | PAO-R36 INT-R6 declaration | `INT-R6`; fail closed as `not_established` until researched and implemented. |
| `C-11` | Named institutional mandates, competence, custody, and acceptance | all 21 typed institutional items plus PAO-R36 cohort/parity/publication inputs | `INSTITUTION-NONE`; no owner is invented. |
| `C-12` | Later empirical/formal work with an existing conservative fallback | all 19 typed `RES` items | `LATER-RESEARCH`; none blocks the first milestone. |
| `C-13` | `P38` canonical registration deficit | GY §3.5.14 and Atlas Execution Doctrine citations | `REGISTER-P38`. |
| `C-14` | Cross-package F11 recovery/correction seam | exact six-part conjunction | Preserve; no route for re-adjudication. Implementation dependencies split between `H2-PLAN-MISSING` and PAO-R36 canonical owners. |

## 4. OPS-R14 source-item routing

### 4.1 Engineering — 8/8

| ID | Condensed question | Cluster | Destination and owner result |
| --- | --- | --- | --- |
| `OPS-ENG-01` | Independently governed acknowledgement domains and shared-substrate/key-root detection | `C-02`, `C-04` | `H2-PLAN-MISSING`; **no owner exists**. P37 rule goes to `RC-P37`. |
| `OPS-ENG-02` | Event-journal/reducer preservation across engine change | `C-06` | `H2-PLAN-MISSING`; extend canonical event/replay owners only after a plan exists. |
| `OPS-ENG-03` | Complete-by-construction dependency registration for protected actions | `C-06` | `H2-PLAN-MISSING`; omission must fail closed. |
| `OPS-ENG-04` | Affected-query migration without a second chronology owner | `C-05` | `GY-N12` for chronology; query/replay implementation to `H2-PLAN-MISSING`. |
| `OPS-ENG-05` | Independently reconcile PAO-R36 frozen denominator without owning its protocol | `C-07`, `C-14` | PAO-R36 canonical correction owner plus `H2-PLAN-MISSING`; seam semantics remain fixed. |
| `OPS-ENG-06` | Cross-store hold barriers | `C-06` | `H2-PLAN-MISSING`; **no owner exists**. |
| `OPS-ENG-07` | Long-term verifier dependency retention and anti-substitution | `C-02`, `C-06` | `INT-R7` supplies research profile; implementation to `H2-PLAN-MISSING`. |
| `OPS-ENG-08` | Authenticated/monotonic time against rollback | `C-02`, `C-04` | `H2-PLAN-MISSING`; consume ratified time semantics, do not create a new time owner. |

### 4.2 Institutional — 7/7

| ID | Condensed question | Destination |
| --- | --- | --- |
| `OPS-INST-01` | Roles that create/narrow/review/release holds and succession evidence | `INSTITUTION-NONE` — no competent owner is named. |
| `OPS-INST-02` | Renewal roles and required counterparties/subjects/certifiers/fiscal authorities | `INSTITUTION-NONE`. |
| `OPS-INST-03` | Which copies are independently governed and who may hold them | `INSTITUTION-NONE`. |
| `OPS-INST-04` | Controlled access for public/court/archive/audit/restricted requesters | `INSTITUTION-NONE`. |
| `OPS-INST-05` | Applicable retention/archive/disclosure/procurement/litigation regimes | `INSTITUTION-NONE`. |
| `OPS-INST-06` | Who declares recovery boundaries and accepts miss/retest | `INSTITUTION-NONE`. |
| `OPS-INST-07` | Evidence resolving merger/abolition/scoped split | `INSTITUTION-NONE`; future positive additionally constrained by `RC-F14`. |

### 4.3 Further research — 6/6

| ID | Condensed question | Route | First-milestone effect |
| --- | --- | --- | --- |
| `OPS-RES-01` | Classify expiry/TTL census by right family, action, and consumer | `LATER-RESEARCH` | Non-blocking analysis; census facts already settled at consolidation. |
| `OPS-RES-02` | Make dependency omission fail at build/test time | Reclassify to engineering; `H2-PLAN-MISSING` | No new theory required. |
| `OPS-RES-03` | Model mass-expiry storms | `LATER-RESEARCH` | Non-blocking simulation/performance study. |
| `OPS-RES-04` | Compare long-horizon preservation strategies | `LATER-RESEARCH` | Non-blocking; current capability remains absent. |
| `OPS-RES-05` | Actual-jurisdiction succession/archive-transfer patterns | `LATER-RESEARCH` plus `INSTITUTION-NONE` | Empirical/domain work; fail-closed succession remains available. |
| `OPS-RES-06` | Hold interaction with erasure/minimization/classification/privilege/public verification | `LATER-RESEARCH` plus `INSTITUTION-NONE` | Non-blocking; no universal regime is assumed. |

## 5. PAO-R4 source-item routing

### 5.1 Engineering — 7/7

| ID | Condensed question | Cluster | Destination and owner result |
| --- | --- | --- | --- |
| `PAO-R4-ENG-01` | Canonical policy-to-case emission chokepoint | `C-08` | `H2-PLAN-MISSING`; **no owner exists**. Existing adjacent owners are inputs, not appointment evidence. |
| `PAO-R4-ENG-02` | Representation-independent E/G/X/S classification | `C-08` | `H2-PLAN-MISSING`; extend chosen canonical intake/emission owner after `ENG-01` decision. |
| `PAO-R4-ENG-03` | Completeness/bounds for named auxiliary history `H` | `C-02`, `C-08` | `H2-PLAN-MISSING`; decisive incompleteness stays fail-closed under P37. |
| `PAO-R4-ENG-04` | Canonical denied-purpose mapping without string bypass | `C-08` | Future plan must extend existing authority-envelope/consumer guards; no parallel prohibition owner. |
| `PAO-R4-ENG-05` | Consultation events with minimal false negatives | `C-06`, `C-08` | `H2-PLAN-MISSING` plus external consumer integration; no owner exists. |
| `PAO-R4-ENG-06` | Independent protected-action totals without owning case identity | `C-02`, `C-06` | `H2-PLAN-MISSING` and `INSTITUTION-NONE` for non-producing denominator source. |
| `PAO-R4-ENG-07` | Refusal/bounding of lineage-stripped relays | `C-06`, `C-08` | `H2-PLAN-MISSING`; governed intake owner must be selected first. |

### 5.2 Institutional — 5/5

| ID | Condensed question | Destination |
| --- | --- | --- |
| `PAO-R4-INST-01` | External case-system owner accepts mandatory gating/evidence return | `INSTITUTION-NONE`. |
| `PAO-R4-INST-02` | Competent authority for normative rule applicability | `INSTITUTION-NONE`. |
| `PAO-R4-INST-03` | Independent protected-action denominator source | `INSTITUTION-NONE`. |
| `PAO-R4-INST-04` | Enforceable consequence for evidence return | `INSTITUTION-NONE`. |
| `PAO-R4-INST-05` | Affected-person safeguards in each external procedure | `INSTITUTION-NONE`; PolicyOS remains an anti-role for the individual act. |

### 5.3 Further research — 4/4

| ID | Condensed question | Route | First-milestone effect |
| --- | --- | --- | --- |
| `PAO-R4-RES-01` | Bounded non-individualizability proofs under adaptive auxiliary information | `LATER-RESEARCH` | Non-blocking; current conservative result is `NOT_ESTABLISHED`/refuse. |
| `PAO-R4-RES-02` | Set-valued uncertain reference-class membership | `LATER-RESEARCH` | Non-blocking; abstention/fail-closed path exists. |
| `PAO-R4-RES-03` | Adaptive query controls against differencing/class shopping | `LATER-RESEARCH` | Non-blocking; governed boundary may refuse incomplete history. |
| `PAO-R4-RES-04` | Causal materiality beyond conservative consultation | `LATER-RESEARCH` | Non-blocking; consultation itself remains the safe gate predicate. |

## 6. S0-GAP-02 source-item routing

### 6.1 Engineering — 12/12

| ID | Condensed question | Cluster | Destination and owner result |
| --- | --- | --- | --- |
| `S0-ENG-01` | Minimal raw trace grammar without hidden product verdict | `C-09` | `S0-OPS15-GAP`; implementation owner absent. |
| `S0-ENG-02` | Transitive provenance across source/generated/container/service/model/network | `C-02`, `C-09` | `S0-OPS15-GAP`; apply `RC-P37`. |
| `S0-ENG-03` | Mandatory evaluator diversity dimensions | `C-02`, `C-09` | `S0-OPS15-GAP`; engineering threat model plus institutional competence evidence. |
| `S0-ENG-04` | Canonicalize large unordered traces without semantic loss | `C-09` | `S0-OPS15-GAP`. |
| `S0-ENG-05` | Hidden mutation seed generation/commitment/recovery/rotation | `C-09` | `S0-OPS15-GAP`; custody institution absent. |
| `S0-ENG-06` | Localize evaluator disagreement | `C-09` | `S0-OPS15-GAP`. |
| `S0-ENG-07` | Public commitment construction resistant to small-space disclosure | `C-09` | `S0-OPS15-GAP`; cryptographic review is engineering, not new wave-4 theory. |
| `S0-ENG-08` | Resource policy for semantic failure vs timeout/infrastructure | `C-09` | `S0-OPS15-GAP`; PV-K06 fail-closed outcomes already govern. |
| `S0-ENG-09` | Enforce `AnswerNeutral(z,f)` for every common artifact/family | `C-02`, `C-09` | `S0-OPS15-GAP`; apply `RC-P37`. |
| `S0-ENG-10` | Finite-domain PDL-1 proof-producing compiler | `C-09` | `S0-OPS15-GAP`; research contract is complete, implementation owner absent. |
| `S0-ENG-11` | Maintain discriminator adequacy as families evolve | `C-02`, `C-09` | `S0-OPS15-GAP`; versioned coverage receipts. |
| `S0-ENG-12` | Independently reconcile access heads and exact run effect | `C-02`, `C-09` | `S0-OPS15-GAP`; institutional custody source absent. |

### 6.2 Institutional — 9/9

| ID | Condensed question | Destination |
| --- | --- | --- |
| `S0-INST-Q01` | Second competent team with mandate/funding/time/expertise | `INSTITUTION-NONE`. |
| `S0-INST-Q02` | Authoring/adjudication roles and incompatible combinations | `INSTITUTION-NONE`. |
| `S0-INST-Q03` | Competence standard for jurisdictional/institutional/temporal/custody review | `INSTITUTION-NONE`. |
| `S0-INST-Q04` | Challenger/dissent protection and independent escalation | `INSTITUTION-NONE`. |
| `S0-INST-Q05` | Key/evidence continuity across rotation/compromise/dissolution | `INSTITUTION-NONE`. |
| `S0-INST-Q06` | Conflicts among evaluator, sponsor, funder, and scoring beneficiary | `INSTITUTION-NONE`. |
| `S0-INST-Q07` | Body that accepts evaluator release for scoring | `INSTITUTION-NONE`; no OPS-R15 unblock. |
| `S0-INST-Q08` | Independent or dual-controlled `B`→`O_v` derivation | `INSTITUTION-NONE`. |
| `S0-INST-Q09` | Blind reviewer proficiency/drift administration | `INSTITUTION-NONE`. |

### 6.3 Further research — 9/9

| ID | Condensed question | Route | First-milestone effect |
| --- | --- | --- | --- |
| `S0-RES-01` | Residual correlated semantic error under shared specification/reviewers | `LATER-RESEARCH` | Non-blocking; stronger claim is withheld. |
| `S0-RES-02` | Mutation-adequacy criterion for real custody faults | `LATER-RESEARCH` | Non-blocking; discriminator removal/liveness gates already fail closed. |
| `S0-RES-03` | Partially ordered/incomparable set-valued outcomes | `LATER-RESEARCH` | Non-blocking; finite alternatives and abstention are available. |
| `S0-RES-04` | Hidden-fixture exposure decay | `LATER-RESEARCH` | Non-blocking operational research. |
| `S0-RES-05` | Proof-carrying mutation certificates without product imports | `LATER-RESEARCH` | Non-blocking; unknown certificate blocks. |
| `S0-RES-06` | Drift signals without collapsing dissent | `LATER-RESEARCH` | Non-blocking; raw dissent remains append-only. |
| `S0-RES-07` | Equivocation-resistant commitment/log design | `LATER-RESEARCH` | Non-blocking; split-view risk stays non-positive. |
| `S0-RES-08` | Distinguish coincident independent error from shared provenance | `LATER-RESEARCH` | Non-blocking; provenance uncertainty remains `not_established`. |
| `S0-RES-09` | Bounded assurance over shared axioms/expectations | `LATER-RESEARCH` | Non-blocking; `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED` is a valid terminal. |

## 7. PAO-R36 owner-first map routing

### 7.1 Capability rows

| Owner-first item | Present state | Route | Consolidation result |
| --- | --- | --- | --- |
| Canonical append-only predecessor/successor relation | general owner implemented; correction specialization absent | `RULE-EVOLUTION` | Extend existing owner; no `correction_evolution.py` or second ledger. |
| Current head, `as_of`, epoch, stale/revalidation/reissue/withdrawal | GY-N12 contract-only/undelivered | `GY-N12` | Consume one chronology; do not implement another head. |
| Four-audience correction-notice projection | base projection exists; correction tuple/phase absent | `PROJECTION` | Reuse PUBLIC/REVIEWER/EXPERT/MACHINE and protected-query semantics. |
| Public bundle producer and HTTP consumer boundary | generic `bridge_missing`; correction specialization absent | `PUBLIC-EXPORT` | Reuse endpoints; do not infer signing/correction capability. |
| Terminal issuance/key/currentness/public-verification semantics | delivered research; runtime capability unclaimed | `INT-R7` | Consume terminal Section 18 and five separate dimensions. |
| Durable correction notice producer/reader | absent/unallocated | future plan spanning `RULE-EVOLUTION` + `PROJECTION` + `PUBLIC-EXPORT`; no implementation owner named | Keep absent; not `producer_missing`. |
| Versioned correction retrieval and full observer tuple | absent/unallocated as correction bridge | `GY-N12` + `PROJECTION`; implementation owner not yet named | Enumerate every authority-bearing route before a positive. |
| Correction-scoped surface/cache generation and read probes | absent/unallocated | future correction implementation under canonical owners; no owner exists | Generic cache tokens are not capability. |
| Subscriber registry, obligation freeze, intent, receipt evidence | absent/unallocated | `INSTITUTION-NONE` for cohort/obligation inputs; future correction implementation for runtime | Unknown obligation defaults synchronous; no late downgrade. |
| Public/machine correction feed | absent/unallocated | future correction implementation under canonical owners; no owner exists | No endpoint/media type/service is inferred. |
| Archive correction relation | absent/unallocated | `H2-PLAN-MISSING` for custody + PAO-R36 correction owner | Controlled archives must be enumerated; unknown copies limit claims. |
| Authoritative-language correction parity | `not_established`; mechanism absent | `INT-R6` | Research first; fail closed; no local translation workflow. |
| Effective gate with phase-correct record set | absent/unallocated | `RULE-EVOLUTION` + `GY-N12` + future correction implementation | A declaration/draft/placeholder cannot satisfy the gate. |
| End-to-end correction verification | absent/unallocated | future implementation under the same canonical owners; no owner exists | `verification_missing` is forbidden until the chain is wired. |

### 7.2 Four dependency declarations

| Dependency | Package statement | Route | First-milestone effect |
| --- | --- | --- | --- |
| `INT-R6` | unresearched multilingual authority equivalence | `INT-R6` | **Not first-milestone blocking.** It blocks multilingual authority parity only; the current gate remains `not_established`. |
| `GY-N12` | undelivered currentness/epoch owner | `GY-N12` | Engineering/plan dependency, not new theory. |
| `INT-R7` | delivered research profile | `INT-R7` | No research block; implementation and institutional evidence remain absent. |
| `OPS-R14` | durability/expiring-authority seam | `H2-PLAN-MISSING` plus preserved F11 conjunction | No research re-adjudication; implementation owner absent. |

## 8. Does any agenda item block on new research?

**No item blocks the first milestone on new theory.** The evidence separates three categories:

1. **Engineering wiring:** the complete producer/artifact/bridge/consumer/verification chains are absent. OPS-R14 and most PAO-R4 work additionally lack the future H2 custody-runtime plan, so **no owner exists**. S0-GAP-02 has a complete research contract but no implementation or evaluator institution.
2. **Named institutional facts:** mandates, competent humans, custody bodies, denominator sources, case-system agreements, and release/acceptance authority are absent. These can block a positive operational result, but they are not research questions and cannot be supplied by repository prose.
3. **Later research with a safe fallback:** every typed `RES` item has an existing conservative outcome — `not_established`, refusal, abstention, bounded claim, fail-closed multilingual parity, or specification-assurance withholding. Therefore the item may improve scope or efficiency later without holding the first milestone.

The apparent exception is PAO-R36's `INT-R6` declaration. It is genuinely unresearched, but it is not a first-milestone dependency: until it exists, authoritative multilingual parity remains `not_established` and no multilingual positive may issue. The first-milestone standing is therefore unchanged: **no active research remains on the path; engineering and institutional evidence do.**

## 9. Preserved non-movement

- Every complete package capability chain remains `absent/unallocated`.
- No `contract_only`, `producer_missing`, `bridge_missing`, or `verification_missing` label is borrowed before its prerequisites.
- No capability, owner, gate, publication/signing permission, or OPS-R15 unblock is promoted.
- The F11 seam remains the exact six-part conjunction and is not re-adjudicated.