---
title: "Wave 5 consolidation — routing map"
status: candidate
stage: consolidation
base: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
---

# Wave 5 Routing Map

## Routing law

Every surviving audit row, verifier gap, failed/unrunnable closure test, unmet lift condition and
explicit response-line open question has one row below. A repeated source ID can point to the same
underlying obligation; the edit shape says when it is an alias so the destination receives one
obligation, not duplicate registrations.

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

All seven existing destinations resolved. Their declared owners are respectively team-architecture,
architect, the GY plan's per-task owner (runtime/quality for O1/O3), team-design with
team-architecture runtime co-owner, governance-board, governance-board, and the pipeline architect.

The following proposed documents were separately tested and are absent:

- `docs/plans/active/H2-custody-runtime.md`;
- `docs/plans/active/INT-R3-operator-comprehension-study.md`;
- `docs/plans/active/INT-R6-multilingual-authority-assurance.md`;
- `docs/plans/active/non-data-acquisition-runtime.md`;
- `docs/plans/active/institutional-authority-evidence.md`.

## A. Surviving findings, tests and lift conditions

| Route | Item and source | Exact destination | Shape of edit / owner truth | Exists? | Consuming lane or slice |
|---|---|---|---|---|---|
| W5-S01 | INT-R2 F006 — incomplete S01–S22 replay | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Add Group-D row `W5-SOURCE-REPLAY-R2`; exact source-state/passages or explicit replay-unavailable per row; owner team-architecture as research-backlog custodian. | yes | future non-data acquisition assurance |
| W5-S02 | INT-R2 F007 — ceiling vocabularies lack owners | `docs/plans/active/DEBT-REGISTER.md` | Add §B row `int-r2-ceiling-vocabulary-owners`, `absent/unallocated`; architect must allocate each field owner before implementation. | yes | GY acquisition and Atlas DS15 |
| W5-S03 | INT-R2 F008 — 63-case benchmark absent | `docs/plans/active/layer2-slices/S14-evaluation-redesign-universality-assurance-battery.md` | Add inherited-input subsection and new battery partition for 63 immutable cases, independent oracle, seven mutants and consumer assertion; governance-board owner. | yes | S14 assurance; future acquisition consumer |
| W5-S04 | INT-R3 F001 — false anchors survive in siblings | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Amend INT-R3 Completion Ledger row with G1 sibling-artifact correction obligation; no new finding ID. | yes | INT-R3 research closeout |
| W5-S05 | INT-R3 F002 — false repository zero survives | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Same G1 row as W5-S04; add complete-walk acceptance and remove/qualify every dependent assertion. | yes | INT-R3 research closeout; DS6 limitation input |
| W5-S06 | INT-R3 F003 — source reconstruction incomplete | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Add Group-D row `W5-SOURCE-REPLAY-R3` for the five unresolved EXT families and branch-custodied locators. | yes | operator-study evidence |
| W5-S07 | INT-R3 O05 — supplied `20/24`/zero propagation | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Alias to G1 row W5-S04/W5-S05; record source IDs F001/F002/O05 in one row, not three obligations. | yes | INT-R3 research closeout |
| W5-S08 | R4‖O5 F01 — OPS-R7 fixture discharge incomplete | `docs/plans/active/layer2-slices/S14-evaluation-redesign-universality-assurance-battery.md` | Add version/interference/repeated-look fixture family and sealed oracle subsection; governance-board owner. | yes | S14; GY-O1 evidence admission |
| W5-S09 | R4‖O5 F02 — operation fixtures absent | `no owner exists` | Proposed new `docs/plans/active/H2-custody-runtime.md`; owner must be appointed for durable response state; subject: executable OPS-R5 operation charters; contents: producer/event/state engine/bridge/consumer/e2e fixtures/surfaces. | no; proposed path verified absent | H2; OPS response runtime |
| W5-S10 | R4‖O5 F03 — holdout/oracle/evaluator/results absent | `docs/plans/active/layer2-slices/S14-evaluation-redesign-universality-assurance-battery.md` | Add diagnosis holdout partition, all-unresolved baseline, risk–coverage metrics and independent oracle/evaluator task. | yes | S14; GY-O1 |
| W5-S11 | R4‖O5 F05 — GY-O1 contradiction and invalid token | `docs/plans/active/layer3-slices/GY-engine-subordination.md` | Amend Phase-6 GY-O1 with one explicit decision row: interim no-mutation rule, eight-condition candidate, package contradiction closure test; runtime/quality owner. Vocabulary deviation routes separately to pipeline. | yes | GY-O1 |
| W5-S12 | R4‖O5 F06 — state engine/mutations absent | `no owner exists` | Proposed `docs/plans/active/H2-custody-runtime.md`; same owner decision as W5-S09; add constrained-product state engine, persisted transitions and pairwise/three-way mutations. | no | H2; OPS response runtime |
| W5-S13 | R4‖O5 F07 — diagnosis corpus absent | `docs/plans/active/layer2-slices/S14-evaluation-redesign-universality-assurance-battery.md` | Add 24 immutable packet IDs, sealed oracle records, five independent O3 consumer mutations and adjacent valid controls. | yes | S14; GY-O3 |
| W5-S14 | R4‖O5 F08 — response corpus absent | `no owner exists` | Proposed `docs/plans/active/H2-custody-runtime.md`; add 20 event-sequence packets, transition oracles, evaluator and proxy-divergence pairs. | no | H2; OPS response runtime |
| W5-S15 | INT-R5 A005 — branch replay incomplete | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Add Group-D row `W5-SOURCE-REPLAY-R5`: durable retrievable archive identities plus every load-bearing passage; owner team-architecture for research handoff, not source authority. | yes | future authority-certificate assurance |
| W5-S16 | INT-R3 G1 | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Alias/umbrella for W5-S04/S05/S07; one amended Completion Ledger row lists all three audit sources and one acceptance command. | yes | INT-R3 research closeout |
| W5-S17 | INT-R3 G2 | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Alias to W5-S06; do not register a second source-replay gap. | yes | operator-study evidence |
| W5-S18 | R4‖O5 Internal Consistency Finding | `docs/plans/active/layer3-slices/GY-engine-subordination.md` | Alias to W5-S11; the GY-O1 row must require package-wide one-answer consistency, not select a preferred sibling. | yes | GY-O1 |
| W5-S19 | INT-R5 V-001 | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Alias to W5-S15; distinguish authenticated connector identity from branch replay. | yes | future authority-certificate assurance |
| W5-S20 | R4‖O5 CT-01 FAIL | `docs/plans/active/layer2-slices/S14-evaluation-redesign-universality-assurance-battery.md` **and** `no owner exists` for `docs/plans/active/H2-custody-runtime.md` | Alias INT half to W5-S08 and OPS half to W5-S09; no third obligation. | S14 yes; H2 no | S14 + H2 |
| W5-S21 | R4‖O5 CT-02 FAIL | `docs/plans/active/layer3-slices/GY-engine-subordination.md` | Alias to W5-S11/W5-S18; add package-wide contradictory-answer falsifier. | yes | GY-O1 |
| W5-S22 | R4‖O5 CT-03 UNRUNNABLE | `docs/plans/active/layer2-slices/S14-evaluation-redesign-universality-assurance-battery.md` | Alias to W5-S13; require real posterior-consumer assertion. | yes | S14; GY-O3 |
| W5-S23 | R4‖O5 CT-05 UNRUNNABLE | `docs/plans/active/layer2-slices/S14-evaluation-redesign-universality-assurance-battery.md` | Alias to W5-S10; require holdout/oracle/evaluator/results artifacts. | yes | S14; GY-O1 |
| W5-S24 | R4‖O5 CT-06 UNRUNNABLE | `no owner exists` | Alias to W5-S12 in proposed H2 plan; state-engine execution is the acceptance signal. | no | H2 |
| W5-S25 | R4‖O5 CT-07 UNRUNNABLE | `docs/plans/active/layer2-slices/S14-evaluation-redesign-universality-assurance-battery.md` | Alias to W5-S13; split O3 properties into five independently failing mutations. | yes | S14; GY-O3 |
| W5-S26 | R4‖O5 CT-08 UNRUNNABLE | `no owner exists` | Alias to W5-S14 in proposed H2 plan; execute paired proxy-divergence cases. | no | H2 |
| W5-S27 | R4‖O5 CT-10 UNRUNNABLE | `docs/plans/active/layer2-slices/S13-post-deploy-accountability-learning.md` | Add Contract Dictionary subsection for versioned total SMDV→S13 crosswalk, non-widening projection and complete contributor-combination fixture population; governance-board owner. | yes | S13; Atlas DS17/DS18 |
| W5-S28 | INT-R5 unmet lift 5 — complete executable/authority denominator not rerun | `docs/plans/active/DEBT-REGISTER.md` | Add §B row `int-r5-complete-authority-chain-denominator`; owner team-architecture; derive source-to-consumer closure and corrupt-one-member falsifier before any complete claim. | yes | future INT-R5 runtime; DS20/PAO-R4 consumer |
| W5-S29 | INT-R5 unmet lift 6 — branch-only source replay | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Alias to W5-S15/W5-S19; no second gap. | yes | authority-certificate assurance |
| W5-S30 | INT-R6 unmet lift 3 — current census not independently executed | `docs/plans/active/DEBT-REGISTER.md` | Add §B row `int-r6-independent-current-leaf-identity-census`; owner team-architecture as executing verifier, with two independent parsers and corrupt-field failure. | yes | future MAEP assurance; Atlas multilingual surfaces |

Combined-verifier gap headings reconcile without new routes:

- absorbed fixtures → W5-S08/S09/S20;
- holdout/oracle/results → W5-S10/S23;
- GY-O1 inconsistency/token → W5-S11/S18/S21 plus pipeline W5-P01;
- state engine/mutations → W5-S12/S24;
- diagnosis/response corpora → W5-S13/S14/S22/S25/S26;
- total crosswalk → W5-S27.

## B. Pipeline findings

| Route | Item and source | Exact destination | Shape of edit / owner truth | Exists? | Consuming lane or slice |
|---|---|---|---|---|---|
| W5-P01 | Pipeline §3.3 clarity; 2/5 amendments used outside tokens | `docs/reference/policy-operations-research-pipeline.md` | Amend §3.3 sentence: “closed set; exactly these three values”; add separate `routing_state`/verification-result examples. Pipeline architect owns reference. | yes | every future Stage-3/4 task |
| W5-P02 | Disclosure accuracy; only 2/5 terminal hand-backs branch-assessable, 1/2 inaccurate | `docs/reference/policy-operations-research-pipeline.md` | Amend §3.4 with `disclosure_accuracy ∈ matches_branch/inaccurate/not_established`; amend §5 to require content-bound delivery-disclosure receipt and declared denominator. | yes | every future delivery and verification task |

## C. Explicit response-line open questions — 70 rows

### INT-R2

| Route | Item and source | Exact destination | Shape of edit / owner truth | Exists? | Consumer |
|---|---|---|---|---|---|
| W5-R2-Q01 | common envelope placement | `docs/plans/active/DEBT-REGISTER.md` | New §B owner-placement row; require owner-first census and canonical-artifact decision. | yes | acquisition runtime / DS15 |
| W5-R2-Q02 | residual-shape/generic acquisition owner | `no owner exists` | Proposed `docs/plans/active/non-data-acquisition-runtime.md`; owner must be appointed by architect; subject: generic non-data acquisition chain; contents: eight producers, artifact, orchestration, consumer, verification and surfaces. | no | GY acquisition |
| W5-R2-Q03 | relation/estimand/operation/capacity/assurance vocabulary map | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | New Group-D research row for complete canonical-owner crosswalk. | yes | W5-R2-Q01/Q02 |
| W5-R2-Q04 | causal adjudication/ceilings | `no owner exists` | Proposed `docs/plans/active/institutional-authority-evidence.md`; owner must be appointed human principal; section on causal-adjudicator competence and ceilings. | no | non-data relation acquisition |
| W5-R2-Q05 | social-licence issuer | `no owner exists` | Same proposed institutional plan; new jurisdiction-specific issuer-evidence section, no universal issuer. | no | social-licence acquisition |
| W5-R2-Q06 | capacity threshold/independence/calibration owner | `no owner exists` | Same proposed institutional plan; new capacity-assurance holder section and falsifier. | no | capacity acquisition |
| W5-R2-Q07 | compound gap ordering | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | New Group-D algebra row with mixed-outcome composition tests. | yes | acquisition planner |
| W5-R2-Q08 | 15-row/eight-type reconciliation | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | New Group-D complete-denominator/crosswalk row; forbid inferred ninth type. | yes | gap grammar owner |
| W5-R2-Q09 | INT-R5/GY-PA2/DS9 acquisition seam | `docs/plans/active/DEBT-REGISTER.md` | New §B row `acquisition-authority-bridge`; owner team-architecture; live call/event census and negative E2E. | yes | DS20/PAO-R4/DS9 consumers |
| W5-R2-Q10 | intake-core/audit-provider boundary | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Add Group-D four-way custody-boundary adjudication row, decomposed by plane. | yes | architecture/custody runtime |
| W5-R2-Q11 | union-row runtime readiness | `docs/plans/active/DEBT-REGISTER.md` | New §B capability-chain row; owner team-architecture after W5-R2-Q02 allocation. | yes | acquisition runtime |
| W5-R2-Q12 | one-lattice projection | `docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md` | Amend DS15 detail with typed non-data-gap route/status crosswalk and authority-nonwidening negative. | yes | Atlas DS15 |
| W5-R2-Q13 | signer/provider availability | `no owner exists` | Proposed institutional plan; add domain-specific availability evidence table and typed absence rule. | no | all eight acquisition cases |

### INT-R3

| Route | Item and source | Exact destination | Shape of edit / owner truth | Exists? | Consumer |
|---|---|---|---|---|---|
| W5-R3-Q01 | INT-R5 seam | `docs/plans/active/DEBT-REGISTER.md` | Amend `acquisition-authority-bridge` row from W5-R2-Q09 with comprehension-claim-use consumer and non-substitution test. | yes | INT-R5 runtime |
| W5-R3-Q02 | INT-R6 semantic IDs | `docs/plans/active/DEBT-REGISTER.md` | New §B total semantic-ID crosswalk row; team-design with architecture review. | yes | operator instrument / multilingual surface |
| W5-R3-Q03 | DS9 attempted vs committed | `docs/plans/active/DEBT-REGISTER.md` | New §B event-semantics row; team-runtime owner, DS9 as closed dependency not new owner. | yes | human-decision integrity |
| W5-R3-Q04 | DS16/17/18 consumption | `docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md` | Amend DS16–DS18 detail with explicit `comprehension_not_established` input and projection non-effect. | yes | Atlas DS16/17/18 |
| W5-R3-Q05 | DS15/GY-N13b quarantine authority | `docs/plans/active/DEBT-REGISTER.md` | New §B owner/capability-census row; distinguish advisory, enforcement and event producer. | yes | DS15 / GY-N13b successors |
| W5-R3-Q06 | adjudicator/loss owner | `no owner exists` | Proposed `docs/plans/active/INT-R3-operator-comprehension-study.md`; owner must be appointed; include adjudication and loss governance. | no | operator study |
| W5-R3-Q07 | thresholds | `no owner exists` | Same proposed study plan; preregistered threshold/population/precision section. | no | operator study |
| W5-R3-Q08 | field transport | `docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md` | Add DS16–DS18 typed input/bridge inventory; no local synthesis. | yes | Atlas DS16/17/18 |
| W5-R3-Q09 | AT × uncertainty | `no owner exists` | Proposed operator-study plan; stratified modality/timing protocol and real-AT participant requirement. | no | DS6/Atlas surfaces |
| W5-R3-Q10 | canonical behavioral-contract owner | `no owner exists` | Proposed operator-study plan; owner appointment section and capability-chain acceptance. | no | DS6 successor / INT-R3 |
| W5-R3-Q11 | OPS-R15 capstone event | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Amend OPS-R15 Completion Ledger/input row with exact event/custody question. | yes | OPS-R15 |
| W5-R3-Q12 | demonstrability stop pattern | `no owner exists` | Proposed operator-study plan; add feasibility stop law and `not_executable` outcome. | no | research governance |
| W5-R3-Q13 | training/sealed examples | `no owner exists` | Proposed operator-study plan; sealed/test corpus partition and leakage controls. | no | S14/operator study |
| W5-R3-Q14 | target population | `no owner exists` | Proposed operator-study plan; population/recruitment/ethics/accessibility section. | no | operator study |

### INT-R4

| Route | Item and source | Exact destination | Shape of edit / owner truth | Exists? | Consumer |
|---|---|---|---|---|---|
| W5-R4-Q01 | `expected_variation` under GY-O1 | `docs/plans/active/layer3-slices/GY-engine-subordination.md` | Alias to W5-S11; one principal decision row and interim no-mutation posture. | yes | GY-O1 |
| W5-R4-Q02 | SMDV-1 owner/axis status | `docs/plans/active/DEBT-REGISTER.md` | New §B owner-placement row after live S13/GY owner census; no new type until owner exists. | yes | GY-O1 / S13 |
| W5-R4-Q03 | SMDV→S13 mapping | `docs/plans/active/layer2-slices/S13-post-deploy-accountability-learning.md` | Alias to W5-S27; total versioned crosswalk section. | yes | S13 |
| W5-R4-Q04 | observation causal ancestry | `docs/plans/active/layer3-slices/GY-engine-subordination.md` | Add GY-O1 producer/evidence rider and absent-producer refusal test. | yes | GY-O1 |
| W5-R4-Q05 | mixed-path identification | `docs/plans/active/layer2-slices/S14-evaluation-redesign-universality-assurance-battery.md` | Add multi-label contributor holdout and suppression falsifier. | yes | S14 / GY-O1 |
| W5-R4-Q06 | unresolved-rate tolerance | `docs/plans/active/layer2-slices/S14-evaluation-redesign-universality-assurance-battery.md` | Add consequence-stratified risk–coverage task; threshold remains unset pending evidence. | yes | S14 / GY-O1 |
| W5-R4-Q07 | version-pooling theorem | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | New Group-D sequential-identification row, with no pooling default. | yes | GY-O1 |
| W5-R4-Q08 | diagnosis oracle/adjudicator | `no owner exists` | Proposed institutional plan; section on independent diagnosis competence and conflicts. | no | S14 / GY-O1 |
| W5-R4-Q09 | diagnosis signer | `no owner exists` | Proposed institutional plan; section on claim-changing signature purpose and authority evidence. | no | public causal claims |
| W5-R4-Q10 | independent zero-inclusion channels | `docs/plans/active/layer2-slices/S14-evaluation-redesign-universality-assurance-battery.md` | Add independent-channel census/positive-control task. | yes | S14 |
| W5-R4-Q11 | privacy/minimization | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | New Group-D purpose-limitation/privacy research row. | yes | diagnosis evidence producer |
| W5-R4-Q12 | Atlas projections | `docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md` | Amend DS17/DS18 detail: diagnosis, limitation and destination-accountability are distinct inputs. | yes | Atlas DS17/DS18 |

### OPS-R5

| Route | Item and source | Exact destination | Shape of edit / owner truth | Exists? | Consumer |
|---|---|---|---|---|---|
| W5-O5-Q01 | H2 durable-runtime owner | `no owner exists` | Proposed `docs/plans/active/H2-custody-runtime.md`; owner appointment required; one-sentence subject and full chain specified in W5-S09. | no | H2 |
| W5-O5-Q02 | E/X/V/C projection | `docs/plans/active/DEBT-REGISTER.md` | New §B constrained-product/status-crosswalk row; architecture owner, S13 consumer. | yes | S13 / Atlas DS17 |
| W5-O5-Q03 | continuous-governance reuse/version delta | `no owner exists` | Proposed H2 plan; reuse-map and epoch/delta section, no parallel platform. | no | H2 / GY-N12 successors |
| W5-O5-Q04 | preauthorization families | `no owner exists` | Proposed institutional plan; appointment, scope, expiry and non-substitution evidence section. | no | H2 response decision |
| W5-O5-Q05 | steward/signers/substitutes | `no owner exists` | Proposed institutional plan; domain-specific holder table and lawful-substitution rule. | no | H2 / public claims |
| W5-O5-Q06 | waiting harm/action costs | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | New Group-D decision-analysis row; no default score or utility owner. | yes | OPS response research |
| W5-O5-Q07 | response horizons | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | New Group-D time-role/jurisdiction row. | yes | H2 design input |
| W5-O5-Q08 | subgroup/spillover response | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | New Group-D causal/interference row. | yes | GY-O1 / H2 |
| W5-O5-Q09 | version-change transitions | `docs/plans/active/DEBT-REGISTER.md` | New §B epoch/transition row with GY-N12 as dependency, not owner; team-runtime owner required. | yes | H2 / GY-N12 consumers |
| W5-O5-Q10 | external execution evidence | `no owner exists` | Proposed institutional plan; typed fail-closed execution-evidence contract and verifier provenance. | no | H2 intake |
| W5-O5-Q11 | permanent/reprocessable O3 quarantine | `docs/plans/active/layer3-slices/GY-engine-subordination.md` | Add GY-O3 lifecycle rider and reprocessing/appeal event tests. | yes | GY-O3 |
| W5-O5-Q12 | audit/API/dashboard surfaces | `docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md` | Amend DS17/DS18 surface inputs and authority-nonminting contract. | yes | Atlas DS17/DS18 |
| W5-O5-Q13 | OPS-R15 oracle | `docs/plans/active/layer2-slices/S14-evaluation-redesign-universality-assurance-battery.md` | Add independent-oracle dependency/partition; do not self-score. | yes | OPS-R15 / S14 |

### INT-R5

| Route | Item and source | Exact destination | Shape of edit / owner truth | Exists? | Consumer |
|---|---|---|---|---|---|
| W5-R5-Q01 | graph/certificate owner | `docs/plans/active/DEBT-REGISTER.md` | New §B owner-placement/capability-chain row; architect allocates canonical runtime owner. | yes | INT-R5 runtime |
| W5-R5-Q02 | profile owner | `no owner exists` | Proposed institutional plan; jurisdiction/profile selection and version-signature section. | no | authority certificate |
| W5-R5-Q03 | time/effect producers | `docs/plans/active/DEBT-REGISTER.md` | New §B producer-handshake row; team-runtime candidate owner subject to architecture allocation. | yes | INT-R5 certificate |
| W5-R5-Q04 | applicability resolver | `no owner exists` | Proposed institutional plan; applicability evidence contract, no PolicyOS legal self-appointment. | no | INT-R5 certificate |
| W5-R5-Q05 | status/reason crosswalk | `docs/plans/active/layer2-slices/S13-post-deploy-accountability-learning.md` | Add Contract Dictionary row for candidate-local reasons → canonical lifecycle status, total and non-widening. | yes | S13 / Atlas surfaces |
| W5-R5-Q06 | INT-R5∩PAO-R4∩DS20 evaluator | `docs/plans/active/DEBT-REGISTER.md` | Amend `acquisition-authority-bridge` row with conjunction evaluator, persisted receipt and two-direction negative E2E. | yes | DS20/PAO-R4 effect path |
| W5-R5-Q07 | first effect/pilot case | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | New Group-D bounded-pilot-selection research row, activated only after owners exist. | yes | future certificate chain |
| W5-R5-Q08 | pilot institutions | `no owner exists` | Proposed institutional plan; availability/consent/authority evidence section. | no | bounded pilot |
| W5-R5-Q09 | conflict/cure adjudicator | `no owner exists` | Proposed institutional plan; jurisdiction-specific cure/relation-back adjudication. | no | authority certificate |
| W5-R5-Q10 | amount/materiality owner | `no owner exists` | Proposed institutional plan; rule-versioned threshold authority section. | no | authority certificate |
| W5-R5-Q11 | mass invalidation cascade | `docs/plans/active/DEBT-REGISTER.md` | New §B cascade-integration row reusing GY-N12 epochs; do not reopen/rename GY-N12 ownership. | yes | INT-R5 dependent certificates/effects |
| W5-R5-Q12 | source-byte custody | `docs/research/policy-operations-and-real-world-runtime-backlog.md` | Alias to W5-S15; add durable archive-custody decision and exact passage acceptance. | yes | certificate assurance |

### INT-R6

| Route | Item and source | Exact destination | Shape of edit / owner truth | Exists? | Consumer |
|---|---|---|---|---|---|
| W5-R6-Q01 | relation/result/reason owner | `docs/plans/active/DEBT-REGISTER.md` | New §B semantic-owner/crosswalk row; explicit `unallocated` for every unresolved field. | yes | MAEP / Atlas multilingual surfaces |
| W5-R6-Q02 | EN–UA corpus/ground truth | `no owner exists` | Proposed `docs/plans/active/INT-R6-multilingual-authority-assurance.md`; owner must be appointed; subject: bounded multilingual semantic assurance; contents: corpus, oracle, holder competence, MAEP, replay and surfaces. | no | S14 / multilingual surfaces |
| W5-R6-Q03 | role qualifications/appointments | `no owner exists` | Proposed institutional plan; purpose-scoped competence/appointment evidence, no default holder. | no | MAEP |
| W5-R6-Q04 | co-authentic reconciliation | `no owner exists` | Proposed institutional plan; jurisdiction-specific divergence/reconciliation procedure. | no | source-authority claims |
| W5-R6-Q05 | RTL jurisdiction pack | `no owner exists` | Proposed multilingual-assurance plan; named jurisdiction/source-rendering pack separate from UI locale. | no | MAEP / Atlas |
| W5-R6-Q06 | cryptographic/trust architecture | `no owner exists` | Proposed multilingual-assurance plan; security co-owner must be appointed; content identity, signer, rotation, revocation and replay threat model. | no | MAEP / custody runtime |

The explicit-question arithmetic is:

```text
INT-R2 13 + INT-R3 14 + INT-R4 12 + OPS-R5 13 + INT-R5 12 + INT-R6 6 = 70
```

## GY-N11 load check

Wave 5 routes **nothing** to GY-N11. Its accumulated load remains exactly the two DS17 obligations
already recorded in the Atlas master plan:

1. a Bayesian credible interval without a coverage argument cannot appear as a promotion certificate;
2. the `over_spend` end-to-end witness.

No third obligation and therefore no unscheduled three-item load is created by this map.

## Route arithmetic

```text
surviving audit/verifier/test/lift rows  30
pipeline rows                             2
explicit open-question rows              70
                                         --
route-map rows                           102
```

Aliases are visible in the edit-shape column. They make every source traceable while preventing the
same capability gap from being registered twice under different names.

