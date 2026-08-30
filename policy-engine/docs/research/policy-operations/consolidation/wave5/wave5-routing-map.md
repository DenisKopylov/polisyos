---
title: "Wave 5 consolidation — routing map"
status: candidate
stage: consolidation
base: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
---

# Wave 5 Routing Map

## Routing law

Every surviving audit row, verifier gap, failed/unrunnable closure test, unmet lift condition and
each of the 73 unique response-line open questions has one row below. A repeated source ID can point
to the same underlying obligation; the edit shape says when it is an alias so the destination
receives one obligation, not duplicate registrations.

Routes do not appoint owners. `no owner exists` is written where the repository has no competent
owner. A proposed document path in such a row is a principal decision, not a file created here.

## Destination verification

From `policy-engine/`, the following exact command was executed:

```bash
for p in \
  docs/research/policy-operations-and-real-world-runtime-backlog.md \
  docs/plans/active/DEBT-REGISTER.md \
  docs/plans/active/layer3-slices/GY-engine-subordination.md \
  docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md \
  docs/plans/active/layer2-slices/S13-post-deploy-accountability-learning.md \
  docs/plans/active/layer2-slices/S14-evaluation-redesign-universality-assurance-battery.md \
  docs/reference/policy-operations-research-pipeline.md; do test -f "$p"; done
```

All seven existing destinations resolved. Their declared record/plan owners are respectively
`team-architecture`, `architect`, **not declared for GY-O1/O3**, `team-design` with
`team-architecture` as runtime co-owner where a task plan names it, `governance-board`,
`governance-board`, and `team-architecture`. Owning a register or plan is not ownership of a missing
capability; every route below preserves that distinction.

The following proposed documents were separately tested and are absent:

- `docs/plans/active/H2-custody-runtime.md`;
- `docs/plans/active/INT-R3-operator-comprehension-study.md`;
- `docs/plans/active/INT-R6-multilingual-authority-assurance.md`;
- `docs/plans/active/non-data-acquisition-runtime.md`;
- `docs/plans/active/institutional-authority-evidence.md`;
- `docs/plans/active/post-deployment-diagnosis-admission.md`.

The absence check used no broader glob or search index:

```bash
for p in \
  docs/plans/active/H2-custody-runtime.md \
  docs/plans/active/INT-R3-operator-comprehension-study.md \
  docs/plans/active/INT-R6-multilingual-authority-assurance.md \
  docs/plans/active/non-data-acquisition-runtime.md \
  docs/plans/active/institutional-authority-evidence.md \
  docs/plans/active/post-deployment-diagnosis-admission.md; do test ! -e "$p"; done
```

Proposed-document specifications, without appointment or creation:

| Proposed path | Owner state | Subject | Required contents |
| --- | --- | --- | --- |
| `docs/plans/active/H2-custody-runtime.md` | `unallocated`; principal appointment required | Durable custody and response state for long-lived policy cases. | producers, events, state engine, idempotency/clocks, orchestration, consumers, recovery, fixtures and surfaces |
| `docs/plans/active/INT-R3-operator-comprehension-study.md` | `unallocated`; principal appointment required | Population-bound behavioral assurance for authority surfaces. | owner/adjudicator, target population, modalities, realistic event, thresholds, sealed corpus, feasibility stop and downstream limitations |
| `docs/plans/active/INT-R6-multilingual-authority-assurance.md` | `unallocated`; principal appointment required | Bounded multilingual semantic and source-authority assurance. | complete baseline, corpus, oracle, qualified holders, MAEP, RTL pack, replay, trust architecture and surfaces |
| `docs/plans/active/non-data-acquisition-runtime.md` | `unallocated`; principal appointment required | Generic runtime chain for the eight non-data acquisition cases. | canonical placement, producers, artifact, re-entry, orchestration, consumers, ceilings, verification and surfaces |
| `docs/plans/active/institutional-authority-evidence.md` | `unallocated`; principal appointment required | Typed external evidence for purpose-specific institutional authority without PolicyOS assuming an anti-role. | signers, adjudicators, competence, profiles, preauthorization, operational outcomes, expiry, provenance and fail-closed absence |
| `docs/plans/active/post-deployment-diagnosis-admission.md` | `unallocated`; principal appointment required | Admitted observation ancestry and diagnosis evidence before O1/O3 consumption. | producer, ancestry/admission artifacts, comparison/context evidence, CAS, O1/O3 bridges, verification and S13/Atlas surfaces |

## A. Surviving findings, tests and lift conditions

| Route | Item and source | Exact destination | Shape of edit / owner truth | Exists? | Consuming lane or slice |
| --- | --- | --- | --- | --- | --- |
| W5-S01 | INT-R2 F006 — incomplete S01–S22 replay | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Add Group-D row `W5-SOURCE-REPLAY-R2`; exact source-state/passages or explicit replay-unavailable per row; owner team-architecture as research-backlog custodian. | yes | future non-data acquisition assurance |
| W5-S02 | INT-R2 F007 — ceiling vocabularies lack owners | `docs/plans/active/DEBT-REGISTER.md` | Add §B row `int-r2-ceiling-vocabulary-owners`, `absent/unallocated`; architect must allocate each field owner before implementation. | yes | GY acquisition and Atlas DS15 |
| W5-S03 | INT-R2 F008 — 63-case benchmark absent | `docs/plans/active/layer2-slices/S14-evaluation-redesign-universality-assurance-battery.md` | Add inherited-input subsection and new battery partition for 63 immutable cases, independent oracle, seven mutants and consumer assertion; governance-board owner. | yes | S14 assurance; future acquisition consumer |
| W5-S04 | INT-R3 F001 — false anchors survive in siblings | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Add a new INT-R3 Completion Ledger row—none exists—recording terminal verification plus the G1 sibling-artifact correction obligation. The row records `accepted_narrow_scope / absent/unallocated / NO_GO`; it does not ratify or close G1. | yes | INT-R3 research closeout |
| W5-S05 | INT-R3 F002 — false repository zero survives | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Same new INT-R3 Completion Ledger row as W5-S04; require a complete walk and removal/qualification of every dependent assertion before G1 closure. | yes | INT-R3 research closeout; DS6 limitation input |
| W5-S06 | INT-R3 F003 — source reconstruction incomplete | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Add Group-D row `W5-SOURCE-REPLAY-R3` for the five unresolved EXT families and branch-custodied locators. | yes | operator-study evidence |
| W5-S07 | INT-R3 O05 — supplied `20/24`/zero propagation | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Alias to the new INT-R3 Completion Ledger row W5-S04/W5-S05; record source IDs F001/F002/O05 in one obligation. | yes | INT-R3 research closeout |
| W5-S08 | R4‖O5 F01 — OPS-R7 fixture discharge incomplete | `docs/plans/active/layer2-slices/S14-evaluation-redesign-universality-assurance-battery.md` | Add version/interference/repeated-look fixture family and sealed oracle subsection; governance-board owner. | yes | S14; GY-O1 evidence admission |
| W5-S09 | R4‖O5 F02 — operation fixtures absent | `no owner exists` | Proposed new `docs/plans/active/H2-custody-runtime.md`; owner must be appointed for durable response state; subject: executable OPS-R5 operation charters; contents: producer/event/state engine/bridge/consumer/e2e fixtures/surfaces. | no; proposed path verified absent | H2; OPS response runtime |
| W5-S10 | R4‖O5 F03 — holdout/oracle/evaluator/results absent | `docs/plans/active/layer2-slices/S14-evaluation-redesign-universality-assurance-battery.md` | Add diagnosis holdout partition, all-unresolved baseline, risk–coverage metrics and independent oracle/evaluator task. | yes | S14; GY-O1 |
| W5-S11 | R4‖O5 F05 — GY-O1 contradiction and invalid token | `no owner exists` **and** `docs/research/policy-operations-and-real-world-runtime-backlog.md` | GY-O1 has no evidenced decision owner: the principal/architect must allocate one before `docs/plans/active/layer3-slices/GY-engine-subordination.md` can receive a decision row. Separately add a new combined-package Completion Ledger row preserving `accepted_narrow_scope / absent/unallocated / NO_GO` and requiring the author—not consolidation—to replace `routed_pending_principal` with a §3.3 disposition. W5-P01 clarifies the pipeline only. | GY owner no; backlog yes | GY-O1; package author |
| W5-S12 | R4‖O5 F06 — state engine/mutations absent | `no owner exists` | Proposed `docs/plans/active/H2-custody-runtime.md`; same owner decision as W5-S09; add constrained-product state engine, persisted transitions and pairwise/three-way mutations. | no | H2; OPS response runtime |
| W5-S13 | R4‖O5 F07 — diagnosis corpus absent | `docs/plans/active/layer2-slices/S14-evaluation-redesign-universality-assurance-battery.md` | Add 24 immutable packet IDs, sealed oracle records, five independent O3 consumer mutations and adjacent valid controls. | yes | S14; GY-O3 |
| W5-S14 | R4‖O5 F08 — response corpus absent | `no owner exists` | Proposed `docs/plans/active/H2-custody-runtime.md`; add 20 event-sequence packets, transition oracles, evaluator and proxy-divergence pairs. | no | H2; OPS response runtime |
| W5-S15 | INT-R5 A005 — branch replay incomplete | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Add Group-D row `W5-SOURCE-REPLAY-R5`: durable retrievable archive identities plus every load-bearing passage; owner team-architecture for research handoff, not source authority. | yes | future authority-certificate assurance |
| W5-S16 | INT-R3 G1 | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Alias/umbrella for W5-S04/S05/S07; the one **new** Completion Ledger row lists all three audit sources and one acceptance command. | yes | INT-R3 research closeout |
| W5-S17 | INT-R3 G2 | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Alias to W5-S06; do not register a second source-replay gap. | yes | operator-study evidence |
| W5-S18 | R4‖O5 Internal Consistency Finding | `no owner exists` | Alias to W5-S11; after a GY-O1 decision owner is appointed, `docs/plans/active/layer3-slices/GY-engine-subordination.md` must require package-wide one-answer consistency rather than selecting a preferred sibling. | no competent owner evidenced | GY-O1 |
| W5-S19 | INT-R5 V-001 | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Alias to W5-S15; distinguish authenticated connector identity from branch replay. | yes | future authority-certificate assurance |
| W5-S20 | R4‖O5 CT-01 FAIL | `docs/plans/active/layer2-slices/S14-evaluation-redesign-universality-assurance-battery.md` **and** `no owner exists` for `docs/plans/active/H2-custody-runtime.md` | Alias INT half to W5-S08 and OPS half to W5-S09; no third obligation. | S14 yes; H2 no | S14 + H2 |
| W5-S21 | R4‖O5 CT-02 FAIL | `no owner exists` | Alias to W5-S11/W5-S18; an appointed GY-O1 decision owner must add the package-wide contradictory-answer falsifier to `docs/plans/active/layer3-slices/GY-engine-subordination.md`. | no competent owner evidenced | GY-O1 |
| W5-S22 | R4‖O5 CT-03 UNRUNNABLE | `docs/plans/active/layer2-slices/S14-evaluation-redesign-universality-assurance-battery.md` | Alias to W5-S13; require real posterior-consumer assertion. | yes | S14; GY-O3 |
| W5-S23 | R4‖O5 CT-05 UNRUNNABLE | `docs/plans/active/layer2-slices/S14-evaluation-redesign-universality-assurance-battery.md` | Alias to W5-S10; require holdout/oracle/evaluator/results artifacts. | yes | S14; GY-O1 |
| W5-S24 | R4‖O5 CT-06 UNRUNNABLE | `no owner exists` | Alias to W5-S12 in proposed H2 plan; state-engine execution is the acceptance signal. | no | H2 |
| W5-S25 | R4‖O5 CT-07 UNRUNNABLE | `docs/plans/active/layer2-slices/S14-evaluation-redesign-universality-assurance-battery.md` | Alias to W5-S13; split O3 properties into five independently failing mutations. | yes | S14; GY-O3 |
| W5-S26 | R4‖O5 CT-08 UNRUNNABLE | `no owner exists` | Alias to W5-S14 in proposed H2 plan; execute paired proxy-divergence cases. | no | H2 |
| W5-S27 | R4‖O5 CT-10 UNRUNNABLE | `docs/plans/active/layer2-slices/S13-post-deploy-accountability-learning.md` | Add Contract Dictionary subsection for versioned total SMDV→S13 crosswalk, non-widening projection and complete contributor-combination fixture population; governance-board owner. | yes | S13; Atlas DS17/DS18 |
| W5-S28 | INT-R5 unmet lift 5 — complete executable/authority denominator not rerun | `docs/plans/active/DEBT-REGISTER.md` | Architect records §B row `int-r5-complete-authority-chain-denominator`; executing owner remains `absent/unallocated`. Require source-to-consumer closure and corrupt-one-member falsifier before any complete claim. | yes | future INT-R5 runtime; DS20/PAO-R4 consumer |
| W5-S29 | INT-R5 unmet lift 6 — branch-only source replay | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Alias to W5-S15/W5-S19; no second gap. | yes | authority-certificate assurance |
| W5-S30 | INT-R6 unmet lift 3 — current census not independently executed | `docs/plans/active/DEBT-REGISTER.md` | Architect records §B row `int-r6-independent-current-leaf-identity-census`; executing verifier remains `absent/unallocated`. Closure requires two independently allocated parsers and a corrupt-field failure. | yes | future MAEP assurance; Atlas multilingual surfaces |
| W5-S31 | INT-R2 verifier minor rationale gap — F012 was imprecisely associated with three consequential orientation errors although it is O-04 | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Add a new INT-R2 Completion Ledger row—none exists—preserving `accepted_narrow_scope / absent/unallocated / NO_GO` and recording the authorial explanation correction owed by verifier `b48cdb13…`; do not edit the package here or reclassify F012. | yes | INT-R2 research closeout |

Combined-verifier gap headings reconcile without new routes:

- absorbed fixtures → W5-S08/S09/S20;
- holdout/oracle/results → W5-S10/S23;
- GY-O1 inconsistency/token → W5-S11/S18/S21 plus pipeline W5-P01;
- state engine/mutations → W5-S12/S24;
- diagnosis/response corpora → W5-S13/S14/S22/S25/S26;
- total crosswalk → W5-S27.

## B. Pipeline findings

| Route | Item and source | Exact destination | Shape of edit / owner truth | Exists? | Consuming lane or slice |
| --- | --- | --- | --- | --- | --- |
| W5-P01 | Pipeline §3.3 clarity; 2/5 amendments used outside tokens | `docs/reference/policy-operations-research-pipeline.md` | `team-architecture` amends §3.3 to say “closed set; exactly these three values” and separates `routing_state`/verification-result examples. | yes | every future Stage-3/4 task |
| W5-P02 | Disclosure accuracy; 0/5 hand-back bodies content-bound to this consolidation and 2/5 only verifier-reported | `docs/reference/policy-operations-research-pipeline.md` | `team-architecture` amends §3.4 with `disclosure_accuracy ∈ matches_branch/inaccurate/not_established`; amend §5 to require a content-bound delivery-disclosure receipt and declared denominator. No independent wave accuracy rate is available. | yes | every future delivery and verification task |

## C. Explicit response-line open questions — 73 unique rows

### INT-R2

| Route | Item and source | Exact destination | Shape of edit / owner truth | Exists? | Consumer |
| --- | --- | --- | --- | --- | --- |
| W5-R2-Q01 | `pdc` + runtime adapters versus keeping the common envelope outside the waist until one producer is proved | `docs/plans/active/DEBT-REGISTER.md` | Architect records a new §B owner-placement/architecture-decision row; capability owner remains unallocated and the two alternatives stay open. | yes | acquisition runtime / DS15 |
| W5-R2-Q02 | residual-shape and generic admission/re-entry owner; CG5 cannot own it | `no owner exists` | Proposed `docs/plans/active/non-data-acquisition-runtime.md`; unallocated owner and full-chain specification are in the proposed-document table. | no | GY acquisition |
| W5-R2-Q03 | relation strength, estimand binding, operation, capacity and assurance vocabulary registration | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Add Group-D research row for complete canonical-owner crosswalk, preserving legal/normative/write distinctions and the rule that citation is not registration. | yes | W5-R2-Q01/Q02 |
| W5-R2-Q04 | domain procedures for relation classification, maximum claim language and open universal threshold | `no owner exists` | Proposed `docs/plans/active/institutional-authority-evidence.md`; owner must be appointed by the human principal; add procedure-specific competence, maximum-language and no-universal-default sections. | no | non-data relation acquisition |
| W5-R2-Q05 | social-licence representation/routing/exclusion and formal issuer | `no owner exists` | Proposed `docs/plans/active/institutional-authority-evidence.md`; add jurisdiction-specific representation choice and issuer-evidence section, with exclusion as the fail-closed branch. | no | social-licence acquisition |
| W5-R2-Q06 | direct capacity evidence, commitment stages, assessor independence and longitudinal calibration | `no owner exists` | Proposed `docs/plans/active/institutional-authority-evidence.md`; add capacity-assurance holder section and anti-checklist-authority falsifier. | no | capacity acquisition |
| W5-R2-Q07 | ordering of relation+writability, mandate+normative authorization and capacity+decision+audit | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Add a Group-D algebra row with all three combinations and mixed-outcome composition tests. | yes | acquisition planner |
| W5-R2-Q08 | reconcile 14 residuals plus one data-shaped member with the eight-type union | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Add a Group-D complete-denominator/crosswalk row; forbid an inferred ninth type. | yes | gap grammar owner |
| W5-R2-Q09 | INT-R5/GY-PA2/DS9 acquisition seam without a second competence certificate | `docs/plans/active/DEBT-REGISTER.md` | Architect records §B row `acquisition-authority-bridge`; executing owner remains unallocated. Require a live call/event census and duplicate-certificate negative E2E. | yes | DS20/PAO-R4/DS9 consumers |
| W5-R2-Q10 | extend `core/audit` packaging/runtime assurance while independent provider stays external | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Add a Group-D four-way custody-boundary adjudication row, decomposed by plane. | yes | architecture/custody runtime |
| W5-R2-Q11 | immutable branch/ref/path admission for the currently institutionally supplied, non-binding union row | `docs/plans/active/DEBT-REGISTER.md` | Architect records a new §B capability-chain/admission row; implementation owner remains unallocated after W5-R2-Q02. | yes | acquisition runtime |
| W5-R2-Q12 | one-lattice projection | `docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md` | Amend DS15 detail with typed non-data-gap route/status crosswalk and authority-nonwidening negative. | yes | Atlas DS15 |
| W5-R2-Q13 | signer/provider availability | `no owner exists` | Proposed `docs/plans/active/institutional-authority-evidence.md`; add domain-specific availability evidence table and typed absence rule. | no | all eight acquisition cases |
| W5-R2-Q14 | eight unregistered/unimplemented ceiling-field relations | `docs/plans/active/DEBT-REGISTER.md` | Alias to W5-S02; the one owner-placement row must cover all eight ceiling algebras and their fail-closed unknowns. | yes | GY acquisition / DS15 |
| W5-R2-Q15 | stable cases, independent oracle and red-proven benchmark mutants | `docs/plans/active/layer2-slices/S14-evaluation-redesign-universality-assurance-battery.md` | Alias to W5-S03; add the inherited 63-case benchmark partition, oracle independence and seven mutants. | yes | S14 / acquisition assurance |

### INT-R3

| Route | Item and source | Exact destination | Shape of edit / owner truth | Exists? | Consumer |
| --- | --- | --- | --- | --- | --- |
| W5-R3-Q01 | action-admissibility policy, role competence and escalation authority without duplicating INT-R5 | `docs/plans/active/DEBT-REGISTER.md` | Architect amends the W5-R2-Q09 owner-placement row to require all three purpose-specific producers and a duplicate-authority-model negative. | yes | INT-R5 runtime / INT-R3 study |
| W5-R3-Q02 | INT-R6 semantic IDs | `docs/plans/active/DEBT-REGISTER.md` | Architect records a new §B total semantic-ID crosswalk row; executing owner remains unallocated. | yes | operator instrument / multilingual surface |
| W5-R3-Q03 | DS9 server-offered modes and attempted override versus committed decision | `docs/plans/active/DEBT-REGISTER.md` | Architect records a new §B event-semantics row; DS9 is a closed dependency, not an owner, and runtime ownership remains unallocated. | yes | human-decision integrity |
| W5-R3-Q04 | DS16/17/18 consumption of red-first predicates before surface freeze | `docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md` | Amend DS16–DS18 detail with the red-first predicate inputs, explicit `comprehension_not_established`, pre-freeze acceptance and projection non-effect. | yes | Atlas DS16/17/18 |
| W5-R3-Q05 | DS15/GY-N13b quarantine authority | `docs/plans/active/DEBT-REGISTER.md` | New §B owner/capability-census row; distinguish advisory, enforcement and event producer. | yes | DS15 / GY-N13b successors |
| W5-R3-Q06 | adjudicator/loss owner | `no owner exists` | Proposed `docs/plans/active/INT-R3-operator-comprehension-study.md`; owner must be appointed; include adjudication and loss governance. | no | operator study |
| W5-R3-Q07 | maximum upper confidence bounds per safety cell and population | `no owner exists` | Proposed `docs/plans/active/INT-R3-operator-comprehension-study.md`; add a preregistered safety-cell/population/precision threshold section. | no | operator study |
| W5-R3-Q08 | operational audit/outcome that validates simulation without making PolicyOS administrator or employer | `no owner exists` | Proposed `docs/plans/active/institutional-authority-evidence.md`; add typed external operational-outcome intake, competence, anti-role boundary and simulation-validation falsifier. | no | operator study / assurance surfaces |
| W5-R3-Q09 | thin-evidence AT × uncertainty item families needing formative co-design | `no owner exists` | Proposed `docs/plans/active/INT-R3-operator-comprehension-study.md`; add stratified modality/timing, formative co-design and real-AT participant requirements. | no | DS6/Atlas surfaces |
| W5-R3-Q10 | reuse-first canonical behavioral-contract owner alternatives | `no owner exists` | Proposed `docs/plans/active/INT-R3-operator-comprehension-study.md`; require census of honest diagnostics and Atlas verification artifacts, an owner decision and a no-local-family negative. | no | DS6 successor / INT-R3 |
| W5-R3-Q11 | realistic operator event with after-hours escalation failure and no unresolved-future dependency | `no owner exists` | Proposed `docs/plans/active/INT-R3-operator-comprehension-study.md`; add the event/custody scenario and independence-from-future-work acceptance. OPS-R15 is only a possible consumer, not the owner; its closed row is untouched. | no | operator study; OPS-R15 consumer only |
| W5-R3-Q12 | demonstrability stop-trigger result pattern | `no owner exists` | Proposed `docs/plans/active/INT-R3-operator-comprehension-study.md`; add feasibility stop semantics without selecting a new outcome token or constitutional claim kind. | no | research governance |
| W5-R3-Q13 | training/sealed examples | `no owner exists` | Proposed `docs/plans/active/INT-R3-operator-comprehension-study.md`; add sealed/test corpus partition and leakage controls. | no | S14/operator study |
| W5-R3-Q14 | target roles, authority levels, tenure bands and operating environments | `no owner exists` | Proposed `docs/plans/active/INT-R3-operator-comprehension-study.md`; add population/recruitment/ethics/accessibility sections covering every named dimension. | no | operator study |

### INT-R4

| Route | Item and source | Exact destination | Shape of edit / owner truth | Exists? | Consumer |
| --- | --- | --- | --- | --- | --- |
| W5-R4-Q01 | `expected_variation` under GY-O1 | `no owner exists` | Alias to W5-S11; the principal/architect must allocate a GY-O1 decision owner before `docs/plans/active/layer3-slices/GY-engine-subordination.md` receives one decision row. The interim no-mutation limitation remains package evidence, not a Stage-6 ruling. | no competent owner evidenced | GY-O1 |
| W5-R4-Q02 | new SMDV-1 vocabulary versus narrow movement-source axis beside S13 | `docs/plans/active/DEBT-REGISTER.md` | Architect records a new §B owner-placement/axis-decision row after live S13/GY census; no new type until a competent owner and decision exist. | yes | GY-O1 / S13 |
| W5-R4-Q03 | SMDV→S13 mapping, including tolerable versus blocking loss | `docs/plans/active/layer2-slices/S13-post-deploy-accountability-learning.md` | Alias to W5-S27; add a total versioned crosswalk and explicitly classify each loss as tolerable or blocking. | yes | S13 |
| W5-R4-Q04 | evidence that constructs observation-process ancestry rather than declaring a DAG/path | `no owner exists` | Proposed `docs/plans/active/post-deployment-diagnosis-admission.md`; owner and full producer/admission chain are unallocated. GY-O1 and GY-O3/Fabric remain downstream consumers only. | no | GY-O1 posterior consumer; GY-O3/Fabric write consumer |
| W5-R4-Q05 | domain-specific identification versus unresolved result for mixed outcome/observation paths | `docs/plans/active/layer2-slices/S14-evaluation-redesign-universality-assurance-battery.md` | Add domain-stratified multi-label contributor holdout, unresolved branch and suppression falsifier. | yes | S14 / GY-O1 |
| W5-R4-Q06 | domain/consequence-specific unresolved rate before accountability-only | `docs/plans/active/layer2-slices/S14-evaluation-redesign-universality-assurance-battery.md` | Add consequence/domain-stratified risk–coverage task; threshold remains unset pending evidence. | yes | S14 / GY-O1 |
| W5-R4-Q07 | version-pooling theorem | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | New Group-D sequential-identification row, with no pooling default. | yes | GY-O1 |
| W5-R4-Q08 | diagnosis oracle/adjudicator | `no owner exists` | Proposed `docs/plans/active/institutional-authority-evidence.md`; add independent diagnosis competence and conflict sections. | no | S14 / GY-O1 |
| W5-R4-Q09 | institutional signers for posterior/world update, reissue, override and withdrawal | `no owner exists` | Proposed `docs/plans/active/institutional-authority-evidence.md`; add four purpose-scoped signer/competence/expiry records and non-substitution tests. Diagnosis remains evidence, not the signature. | no | GY-O1/O3; reissue/override/withdrawal consumers |
| W5-R4-Q10 | mandatory independent channels for people with zero production-channel inclusion | `docs/plans/active/layer2-slices/S14-evaluation-redesign-universality-assurance-battery.md` | Add inclusion-probability census, mandatory independent-channel cases and positive controls. | yes | S14 |
| W5-R4-Q11 | privacy/minimization | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | New Group-D purpose-limitation/privacy research row. | yes | diagnosis evidence producer |
| W5-R4-Q12 | Atlas rendering of unresolved/compound diagnosis without settled-cause projection | `docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md` | Amend DS17/DS18 detail: diagnosis, limitation and destination-accountability are distinct inputs; unresolved/compound cases cannot render as settled cause. | yes | Atlas DS17/DS18 |

### OPS-R5

| Route | Item and source | Exact destination | Shape of edit / owner truth | Exists? | Consumer |
| --- | --- | --- | --- | --- | --- |
| W5-O5-Q01 | H2 owner for durable transition state, clocks, idempotency and recovery | `no owner exists` | Proposed `docs/plans/active/H2-custody-runtime.md`; owner and full chain are specified in the proposed-document table. | no | H2 |
| W5-O5-Q02 | E/X/V/C projection | `docs/plans/active/DEBT-REGISTER.md` | Architect records a new §B constrained-product/status-crosswalk row; implementation owner remains unallocated and S13 is a consumer. | yes | S13 / Atlas DS17 |
| W5-O5-Q03 | continuous-governance actions reused directly and required authority deltas | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Add a new Group-D research row for a complete action-owner reuse map and purpose-specific authority-delta analysis; `team-architecture` owns the research record, not the implementation. | yes | H2 / GY-N12 successors |
| W5-O5-Q04 | preauthorization families, holders and risk classes | `no owner exists` | Proposed `docs/plans/active/institutional-authority-evidence.md`; add appointment, scope, risk class, expiry and non-substitution evidence sections. | no | H2 response decision |
| W5-O5-Q05 | metric steward, transition signer, override signer and after-hours substitute | `no owner exists` | Proposed `docs/plans/active/institutional-authority-evidence.md`; add four purpose-specific holder records and lawful-substitution rules. | no | H2 / public claims |
| W5-O5-Q06 | domain-specific waiting/premature-action model selecting containment intensity | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Add Group-D decision-analysis row; no default score or utility owner. | yes | OPS response research |
| W5-O5-Q07 | KPI maturity and delayed-harm horizons | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Add Group-D time-role/KPI/jurisdiction research row. | yes | H2 design input |
| W5-O5-Q08 | subgroup/spillover guardrails under multiplicity and unknown groups | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Add Group-D causal/interference row retaining multiplicity and unknown-group conditions. | yes | GY-O1 / H2 |
| W5-O5-Q09 | version changes requiring partial/full reissue, downgrade or termination | `docs/plans/active/DEBT-REGISTER.md` | Architect records a new §B epoch/transition row with GY-N12 as dependency, not owner; response-transition owner remains unallocated. | yes | H2 / GY-N12 consumers |
| W5-O5-Q10 | late or contradictory external execution-evidence verification | `no owner exists` | Proposed `docs/plans/active/institutional-authority-evidence.md`; add a typed fail-closed execution-evidence contract, late/contradictory branches and verifier provenance. | no | H2 intake |
| W5-O5-Q11 | protection of permanent O3 quarantine from generic reprocessing | `no owner exists` | GY-O3 has no evidenced task owner. The principal/architect must allocate one before `docs/plans/active/layer3-slices/GY-engine-subordination.md` can receive a lifecycle rider and a generic-reprocessing escape test. | no competent owner evidenced | GY-O3 |
| W5-O5-Q12 | surfaces for unresolved cause, protective action and absent signer | `docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md` | Amend DS17/DS18 surface inputs and authority-nonminting contract, retaining all three distinct facts. | yes | Atlas DS17/DS18 |
| W5-O5-Q13 | OPS-R15 oracle for correct response and replay | `docs/plans/active/DEBT-REGISTER.md` | Architect records an implementation-chain row aliasing the already-complete S0-GAP-02 research input in the Wave-2 backlog. Capability owner stays `absent/unallocated`; OPS-R15 remains blocked and S14 receives no duplicate partition. | yes | OPS-R15 scoring |

### INT-R5

| Route | Item and source | Exact destination | Shape of edit / owner truth | Exists? | Consumer |
| --- | --- | --- | --- | --- | --- |
| W5-R5-Q01 | graph/certificate owner | `docs/plans/active/DEBT-REGISTER.md` | Architect records a new §B owner-placement/capability-chain row; canonical runtime owner remains unallocated. | yes | INT-R5 runtime |
| W5-R5-Q02 | jurisdiction/body/recognition/act-effect profile owner without a private legal engine | `no owner exists` | Proposed `docs/plans/active/institutional-authority-evidence.md`; add canonical profile selection, version/signature and anti-private-engine section. | no | authority certificate |
| W5-R5-Q03 | independent decision-time and effect-class producers | `docs/plans/active/DEBT-REGISTER.md` | Architect records a new §B producer-handshake row; executing producer owner remains unallocated. | yes | INT-R5 certificate |
| W5-R5-Q04 | applicability resolver | `no owner exists` | Proposed `docs/plans/active/institutional-authority-evidence.md`; add applicability evidence contract and no-PolicyOS-legal-self-appointment rule. | no | INT-R5 certificate |
| W5-R5-Q05 | status/reason crosswalk | `docs/plans/active/layer2-slices/S13-post-deploy-accountability-learning.md` | Add Contract Dictionary row for candidate-local reasons → canonical lifecycle status, total and non-widening. | yes | S13 / Atlas surfaces |
| W5-R5-Q06 | INT-R5∩PAO-R4∩DS20 evaluator | `docs/plans/active/DEBT-REGISTER.md` | Amend `acquisition-authority-bridge` row with conjunction evaluator, persisted receipt and two-direction negative E2E. | yes | DS20/PAO-R4 effect path |
| W5-R5-Q07 | first protected effect: acquisition, DS14 or another operation | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Add Group-D bounded-pilot selection among the named alternatives, activated only after owners exist. | yes | future certificate chain |
| W5-R5-Q08 | pilot institutions supplying appointment, meeting and conflict facts | `no owner exists` | Proposed `docs/plans/active/institutional-authority-evidence.md`; add availability, consent and all three evidence-family sections. | no | bounded pilot |
| W5-R5-Q09 | adjudicators for disputed forum, recusal, emergency and cure effect | `no owner exists` | Proposed `docs/plans/active/institutional-authority-evidence.md`; add four purpose-specific, jurisdiction-scoped adjudication sections. | no | authority certificate |
| W5-R5-Q10 | transaction/valuation owner supplying amount authority | `no owner exists` | Proposed `docs/plans/active/institutional-authority-evidence.md`; add rule-versioned amount-authority and valuation-evidence section. | no | authority certificate |
| W5-R5-Q11 | mass invalidation cascade | `docs/plans/active/DEBT-REGISTER.md` | New §B cascade-integration row reusing GY-N12 epochs; do not reopen/rename GY-N12 ownership. | yes | INT-R5 dependent certificates/effects |
| W5-R5-Q12 | admit full survey bytes to repository custody or retain manifest residual | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Alias to W5-S15; record the binary custody decision and exact-passage acceptance without presuming admission. | yes | certificate assurance |

### INT-R6

| Route | Item and source | Exact destination | Shape of edit / owner truth | Exists? | Consumer |
| --- | --- | --- | --- | --- | --- |
| W5-R6-Q01 | complete implementation baseline beyond bounded catalogue path/blob observations | `docs/plans/active/DEBT-REGISTER.md` | Architect records a new §B complete-baseline row covering message composition, certificate producers/consumers and source-content bridge; executing owner remains unallocated. | yes | future MAEP assurance / Atlas multilingual surfaces |
| W5-R6-Q02 | relation/result/reason mapping to registered vocabularies | `docs/plans/active/DEBT-REGISTER.md` | Architect records a new §B semantic-owner/crosswalk row with explicit `unallocated` for every unresolved field. | yes | MAEP / Atlas multilingual surfaces |
| W5-R6-Q03 | Ukrainian high-stakes corpus and behavioral/action ground truth | `no owner exists` | Proposed `docs/plans/active/INT-R6-multilingual-authority-assurance.md`; add versioned corpus, protocol, denominator, reviewer agreement and action-ground-truth sections. | no | S14 / multilingual surfaces |
| W5-R6-Q04 | role qualifications/appointments once real-user evidence exists | `no owner exists` | Proposed `docs/plans/active/institutional-authority-evidence.md`; add purpose-scoped competence/appointment evidence, real-user-evidence prerequisite and no-default-holder rule. | no | MAEP |
| W5-R6-Q05 | jurisdiction-specific co-authentic reconciliation | `no owner exists` | Proposed `docs/plans/active/institutional-authority-evidence.md`; add jurisdiction-specific divergence/reconciliation procedure. | no | source-authority claims |
| W5-R6-Q06 | RTL source-content admission and named jurisdiction pack | `no owner exists` | Proposed `docs/plans/active/INT-R6-multilingual-authority-assurance.md`; add named jurisdiction/source-rendering pack separate from UI locale. | no | MAEP / Atlas |
| W5-R6-Q07 | certificate form, trust roots, key custody, cryptographic architecture and legal effect | `no owner exists` | Proposed `docs/plans/active/INT-R6-multilingual-authority-assurance.md`; a security owner must be appointed; add content identity, signer, trust roots, custody, rotation, revocation, replay and legal-effect threat model. | no | MAEP / custody runtime |

The explicit-question arithmetic is:

```text
INT-R2 15 + INT-R3 14 + INT-R4 12 + OPS-R5 13 + INT-R5 12 + INT-R6 7 = 73
```

## GY-N11 load check

Wave 5 routes **nothing** to GY-N11. Its accumulated load remains exactly the two DS17 obligations
already recorded in the Atlas master plan:

1. a Bayesian credible interval without a coverage argument cannot appear as a promotion certificate;
2. the `over_spend` end-to-end witness.

No third obligation and therefore no unscheduled three-item load is created by this map.

## Route arithmetic

```text
surviving audit/verifier/test/lift rows  31
pipeline rows                             2
explicit open-question rows              73
                                         --
route-map rows                           106
```

The arithmetic above is table-row arithmetic from this one Markdown file, reproduced with:

```bash
python3 - <<'PY'
import re
from pathlib import Path
p=Path('docs/research/policy-operations/consolidation/wave5/wave5-routing-map.md')
ids=[]
for lineno,line in enumerate(p.read_text().splitlines(),1):
    if not line.startswith('| W5-'): continue
    route=line.split('|')[1].strip()
    assert re.fullmatch(r'W5-(?:S\d{2}|P\d{2}|(?:R2|R3|R4|O5|R5|R6)-Q\d{2})',route),(lineno,route)
    ids.append(route)
print('rows',len(ids),'unique',len(set(ids)),'duplicates',len(ids)-len(set(ids)))
for kind,pat in [('surviving',r'W5-S\d{2}'),('pipeline',r'W5-P\d{2}'),('questions',r'W5-(?:R2|R3|R4|O5|R5|R6)-Q\d{2}')]:
    print(kind,sum(bool(re.fullmatch(pat,x)) for x in ids))
PY
```

Observed output: `rows 106`, `unique 106`, `duplicates 0`, then `surviving 31`, `pipeline 2`,
`questions 73`.

Aliases are visible in the edit-shape column. They make every source traceable while preventing the
same capability gap from being registered twice under different names.
