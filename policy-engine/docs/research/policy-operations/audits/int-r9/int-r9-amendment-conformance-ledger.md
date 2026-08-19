---
title: INT-R9 — Amendment Conformance Ledger
status: delivered
kind: amendment-verification
research_task: INT-R9
verification_verdict: CONFORMS_WITH_GAPS
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r9-amendment-verification
verified_branch: research/int-r9-amendment
verified_commit: bb322361eafb5bd8667c35aeedf137dcbfdee1ae
audited_commit: f5ad922377e38ee3ddbecb33293300bca25a9ad7
independent_audit: research/int-r9-independent-audit@a09128e6b914292597054b82bda2701d541b1fea
current_repository_commit: a548a2f939995ad81b4febe3402bdcb35ae11bad
inspection_date: 2026-08-03
authoritative_for:
  - machine-checkable conformance mapping from INT-R9 R1 through R14 to independently verified amended passages
  - audit section-8 acceptance and kill-rule disposition
  - preservation mapping for all nine audit commendations
  - exact fifteen-manifest R13 reproduction ledger
  - residual-gap ledger for consolidation
may_not_use_for:
  - production implementation authorization
  - final code, wire, schema, package, database, evaluator, metric, or serialization contract
  - canonical owner appointment
  - authority grant or capability claim
  - benchmark passage
  - a sequence-level numeric false-promotion claim
  - proof that a positive promotion is achievable
  - automatic consolidation without reading the cited amended text
research_only: true
---

# INT-R9 — Amendment Conformance Ledger

## 1. Ledger conventions

- **executed** — the revision is present in the amended text and changes the operative claim or rule as required.
- **executed_with_cleanup_gap** — the substantive revision is present, but provenance, wording, or preservation cleanup remains.
- **cannot_trigger_claim** — the source condition may still occur, but Option B has removed the proposition it previously falsified.
- **cannot_be_satisfied** — the amended rules make the audit's forbidden state nonconforming.
- **open_by_design** — consolidation or a canonical owner still must supply an operational mapping, and the amendment correctly does not pretend otherwise.
- **survives** — the commendation's substantive property remains in the amended text.
- **survives_weaker** — the property is not contradicted but is retained only in compressed or incomplete form.

This ledger treats the amender's `amendment-ledger.md` as a claim source, not proof. Independent evidence is cited from the primary amended files, current source, exact manifest enumeration, parser output, and diff.

---

## 2. R1–R14 conformance matrix

| Revision | Audit finding(s) | Verdict | Amended evidence | Residual |
| --- | --- | --- | --- | --- |
| **R1 — prove or withdraw single-`delta` family claim** | `C-001`, `D-001` | **executed by withdrawal** | Executive calls result “without a sequence-level risk number”; Option B withdraws every family-wise number; `FP-R01` replays A/B/C and requires no family output; state invariant 9 forbids cumulative scope/spend/ordinal/`delta`/`3 * delta`. Main `int-r9-first-promotion-evaluation-protocol.md:35-90`, `:246-278`, `:365-397`; fixtures `:80-126`, `:151-177`; state `:82-118`. | INT-R10 provenance cleanup only; no INT-R9 risk claim depends on it. |
| **R2 — standing** | `I-003` | **executed** | `result_type: accepted_narrow_scope` is expressly for the nonnumeric custody protocol; current execution is blocked. Same standing appears in primary, census, state, fixtures, YAML comment, and amendment ledger. | none substantive |
| **R3 — adaptive revision** | `C-002`, `D-002` | **executed** | “Every result-informed change is adaptive continuation”; no “general repair” privilege; prior slot not rescored; later positive has no family number. Main `:246-278`; state invariant 8 and `AdaptiveRepairRecord`; fixture `FP-R02`. | none |
| **R4 — prospective materiality** | `D-003` | **executed** | Promotion-critical materiality must have a sealed direction-blind specification, competent existing owner mapping, evidence/conflict/tie/escalation rule, latest decision time; unforeseen/late/conflicted/unavailable => dispute. Main `:303-326`; state `MaterialityDecisionSpecification` / `Record`; fixture `FP-R03`. | operational owner mapping is `open_by_design`, correctly blocking seal |
| **R5 — narrow new-case independence** | `E-002` | **executed** | Answer secrecy, implementation non-access, role separation, and in-pool randomization are distinguished from pool construction; purposive tractability and representativeness remain residual. Main `:221-244`; census `:159-202`; fixture `FP-R09`. | none |
| **R6 — evidence-backed independence** | `F-002` | **executed** | Named people require corroborating contribution/access/employment/funding/compensation evidence; declared-only dimensions remain residual; same-network ties receive explicit disposition. Main `:327-350`; state `IndependenceEvidenceBundle`; fixture `FP-R04`. | exact institutional evidence threshold remains `open_by_design` |
| **R7 — narrow anti-abstention claim** | `G-002` | **executed** | Controls detect mechanical/unsupported refusal only; fully supported refusal of every unseen case remains conforming and ends in public exhaustion. Main `:348-363`; fixture `FP-F12` and `FP-R10`. | none |
| **R8 — useful-design denominator** | `G-003` | **executed by boundary** | INT-R9 records selected/unreached/retired/inspected/void/refused/disputed/promoted chronology but omits denominator membership. Main `:341-351`; state `MetricChronologyProjection`; fixture `FP-R06`. | canonical metric mapping is `open_by_design` |
| **R9 — amended INT-R1 seam** | `H-002` | **executed** | Exact `ObligationCoverageEnvelope`; `known_incomplete` NO-GO; material `open_world_unresolved` NO-GO; current pinned standing unresolved; future `bounded_complete` relative exact scope only; narrower action requires new prospective identity/envelope/protocol/fresh cases. Main `:353-370`; state `:181-211`; fixture `FP-R05`. | none |
| **R10 — S0-GAP-02 supersession-only language** | `H-003` | **executed** | Generic custody remains S0-GAP-02's; replacement only by expressly governed canonical supersession; sibling “equivalent” rejected. Main `:337-345`; state §§1, 9–10; fixture `FP-R08`. | none |
| **R11 — YAML demotion** | `I-001` | **executed_with_cleanup_gap** | 61 lines, all comments; zero non-comment tokens; `yaml.safe_load` returns `None`; no fixed IDs, counts, enum vocabulary, state transitions, blockers, vote rules, or schema-shaped mapping. YAML `:1-61`; fixture `FP-R07`. | stale superseded INT-R10 comment binding |
| **R12 — exact anchors** | `A-001`, `A-002`, `A-005` | **executed** | Every real adjudication uses `:1-120` and line 120 exists; current-state facts use constitution `:382-398`; P29/P33/P34 use failure patterns `:70-78`. Census `:45-100`; fixture doctrine `:32-42`. | none |
| **R13 — exact set facts** | `A-003`, `A-004`, `J-001`, `J-002`, `J-003` | **executed** | Independent fifteen-row aggregation reproduces calibration/topology 4/11, authority 5/6/4, four null-card manifests, and universal expected IDs/labels/votes. Census `:101-158`. | none |
| **R14 — FIPS attribution** | `B-003` | **executed** | FIPS limited to digest/change detection; hiding attributed to commitment construction and predictable-answer threat model. Fixture `FP-F04`, `fixture-specifications.md:145-166`; main external baseline. | none |

### R1 disposition sentence

The exact D-001 trace is **not prohibited as local source behavior**. It is prohibited from yielding an INT-R9 family statement. That is the only interpretation consistent with both the audit's “R1 validated or numeric claim honestly withdrawn/narrowed” acceptance clause and the amendment specification's Option B.

---

## 3. Audit §8 acceptance conditions

| Acceptance condition | Result | Evidence |
| --- | --- | --- |
| R1 independently validated or numeric family claim withdrawn/narrowed | **pass — withdrawn** | Executive/Option B, state invariant 9, `FP-R01`, final answer |
| result standing matches | **pass** | accepted narrow nonnumeric result; current execution blocked throughout |
| material decision rights prospective/checkable | **pass at research level** | sealed materiality specification/evidence/time/conflict/default-dispute; operational owner mapping remains blocker |
| INT-R1 and S0-GAP-02 map to actual artifacts/owners | **pass** | `ObligationCoverageEnvelope`; supersession-only S0-GAP-02 language |
| no parallel ledger/status/oracle | **pass** | local receipts separate; workflow phases custody-only; no sibling oracle |
| exact anchors reproduce facts | **pass** | all 13 line-120 probes; constitution `382-398`; failure patterns `70-78` |
| rule-following actor cannot replay D-001 against claimed property | **pass** | actor can replay local trace, but there is no family probability or cumulative owner property to falsify |

---

## 4. Audit §8 kill-rule matrix

| Kill rule | Classification | Amended disposition | Exact reason |
| --- | --- | --- | --- |
| three distinct case scopes can each start with a fresh `delta` | **cannot_trigger_claim** | local condition remains visible; no sequence-level probability is emitted | `FP-R01` requires three separate local receipts and no family scope/spend/ordinal/bound. The source fact is not disguised. |
| “cumulative” remains an author-written field rather than a recomputed owner property | **cannot_be_satisfied** | no cumulative field/property exists in the accepted protocol | state invalidation rule rejects `cumulative_scope`, `family_ordinal`, `family_delta`, or family spend; YAML has no mapping |
| failed-slot risk disappears merely because next case has new scope | **cannot_be_satisfied as a claimed family disposition** | earlier terminal and local receipt remain; no refund or aggregate statement is made | chronology is append-only; local ledger truth preserved; INT-R9 does not allocate or recycle family risk |
| post-result scope narrowing rescues failed obligation basis | **cannot_be_satisfied** | old slot remains NO-GO; narrower action is new prospective identity/version/cases | main §4.14; state coverage-identity invariant; `FP-R05` |
| unresolved materiality classification made after direction known | **cannot_be_satisfied** | current slot becomes disputed | main §4.7; state materiality-direction invariant; `FP-R03` |
| YAML executable while research questions remain open | **cannot_be_satisfied** | comments-only null document | parser output `None`; no non-comment tokens |

---

## 5. Option-B claim-surface ledger

| Surface | Required Option-B posture | Verified text/result |
| --- | --- | --- |
| primary frontmatter | no family risk claim; positive not promised | deny-list excludes single-`delta`, `3 * delta`, family projection, capability, readiness, and positive promise |
| Executive Finding | procedural claim only | “prospective anti-selection and custody protocol without a sequence-level risk number” |
| attempt order/repair | adaptive, no family number | result-informed change is adaptive; previous slot terminal; no rescore |
| promotion predicates | no family risk conjunct | bounded procedural claim only |
| public record | local receipts and explicit absence of family bound | `family_risk_statement: no_sequence_level_numeric_bound_claimed_by_INT_R9` |
| state machine | local scopes remain distinct | invariant 9 forbids cumulative/family representations |
| fixture battery | D-001 characterized, not hidden | `FP-R01` expects separate local receipts and no public number |
| census | no risk inference from case population | exposure/eligibility only |
| YAML | no machine protocol | comments only, null parse |
| final answer | adaptive and nonnumeric | expressly states no sequence-level false-promotion claim |

No surface reintroduces a rate, family bound, or implication that canonical cross-scope composition exists.

---

## 6. R13 full fifteen-manifest ledger

| # | Manifest | Population | `topology_mode` | `calibration_round_id` | `authority_level` | At least one null `gold_card` | Expected IDs / labels / votes exposed |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | `housing-rent-stabilization-001.adjudication.json` | synthetic | `deep_pilot_overlap` | `deep-pilot-round-1` | `governed` | yes | yes / yes / yes |
| 2 | `public-health-outreach-001.adjudication.json` | synthetic | `partial_disjoint` | `null` | `production` | no | yes / yes / yes |
| 3 | `ua-msme-affordable-loans-2022.adjudication.json` | real | `partial_disjoint` | `null` | `governed` | no | yes / yes / yes |
| 4 | `w11a_berlin_rent_cap_2020.adjudication.json` | real | `deep_pilot_overlap` | `deep-pilot-round-1` | `governed` | no | yes / yes / yes |
| 5 | `w11a_boston_operation_ceasefire_1996.adjudication.json` | real | `deep_pilot_overlap` | `deep-pilot-round-1` | `research` | no | yes / yes / yes |
| 6 | `w11a_eu_temporary_protection_ukraine_2022.adjudication.json` | real | `deep_pilot_overlap` | `deep-pilot-round-1` | `production` | yes | yes / yes / yes |
| 7 | `w11a_ghana_free_shs_2017.adjudication.json` | real | `partial_disjoint` | `null` | `research` | no | yes / yes / yes |
| 8 | `w11a_india_aadhaar_dbt_2016.adjudication.json` | real | `partial_disjoint` | `null` | `production` | yes | yes / yes / yes |
| 9 | `w11a_mexico_ssb_tax_2014.adjudication.json` | real | `partial_disjoint` | `null` | `research` | no | yes / yes / yes |
| 10 | `w11a_netherlands_room_for_river_2007.adjudication.json` | real | `partial_disjoint` | `null` | `research` | no | yes / yes / yes |
| 11 | `w11a_pakistan_ehsaas_cash_2020.adjudication.json` | real | `partial_disjoint` | `null` | `production` | yes | yes / yes / yes |
| 12 | `w11a_uk_levelling_up_fund_2021.adjudication.json` | real | `partial_disjoint` | `null` | `governed` | no | yes / yes / yes |
| 13 | `w11a_uk_mtd_vat_2019.adjudication.json` | real | `partial_disjoint` | `null` | `governed` | no | yes / yes / yes |
| 14 | `w11a_uk_work_programme_2011.adjudication.json` | real | `partial_disjoint` | `null` | `governed` | no | yes / yes / yes |
| 15 | `w11a_us_ppp_2020.adjudication.json` | real | `partial_disjoint` | `null` | `production` | no | yes / yes / yes |

### Programmatic aggregate

```text
manifest_count = 15
population = 13 real / 2 synthetic
calibration = 4 deep-pilot-round-1 / 11 null
topology = 4 deep_pilot_overlap / 11 partial_disjoint
authority = 5 production / 6 governed / 4 research
null-card manifests = housing synthetic, EU, India, Pakistan
all expected IDs exposed = true
all labels exposed = true
all reviewer votes exposed = true
```

This independently confirms the amendment and corrects the original sampled orientation. A null card never restores holdout status because the remaining answer-bearing fields are public.

---

## 7. R12 exact-range ledger

### Thirteen real adjudications

Each amended citation uses `:1-120`, and line 120 was independently fetched at `a548a2f939995ad81b4febe3402bdcb35ae11bad` for:

1. `ua-msme-affordable-loans-2022.adjudication.json`
2. `w11a_berlin_rent_cap_2020.adjudication.json`
3. `w11a_boston_operation_ceasefire_1996.adjudication.json`
4. `w11a_eu_temporary_protection_ukraine_2022.adjudication.json`
5. `w11a_ghana_free_shs_2017.adjudication.json`
6. `w11a_india_aadhaar_dbt_2016.adjudication.json`
7. `w11a_mexico_ssb_tax_2014.adjudication.json`
8. `w11a_netherlands_room_for_river_2007.adjudication.json`
9. `w11a_pakistan_ehsaas_cash_2020.adjudication.json`
10. `w11a_uk_levelling_up_fund_2021.adjudication.json`
11. `w11a_uk_mtd_vat_2019.adjudication.json`
12. `w11a_uk_work_programme_2011.adjudication.json`
13. `w11a_us_ppp_2020.adjudication.json`

### Shared anchors

| Corrected anchor | Verified content |
| --- | --- |
| `policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:382-398` | ua-msme only integrated case; twelve per-slice; all thirteen blockers; `useful_design_rate=0`; B shadow; D3.8 unbuilt |
| `policy-engine/docs/reference/policy-design-case-failure-patterns.md:70-78` | P29 authorial proof, P33 witness-as-specification, P34 premature-green exclusion |

The old bad ranges remain only in audit records describing the original failure and were correctly not rewritten.

---

## 8. Commendation preservation ledger

**Exact count: nine register rows.** The audit prose's count of eight is bookkeeping.

| Finding | Disposition | Quoted surviving fragment | Location |
| --- | --- | --- | --- |
| `A-006` | **survives** | “13 public real regression cases + 2 public synthetic calibration fixtures + 0 sealed decisive cases + 0 adjacent unseen cases” | census §§1 and 10; main current baseline |
| `B-001` | **survives** | external fields supply “procedural mechanisms and warnings, not statistical, legal, or authority proof” | main §3 |
| `C-003` | **survives** | “not proof against covert collusion… population performance, legal compliance, institutional competence, production readiness, or family-risk control” | main Executive Finding |
| `E-001` | **survives** | “ua-msme… remains ineligible as decisive primary and adjacent evidence”; exclusion may end in `exhausted_without_promotion` | main Executive/§2.4; census §5 |
| `F-001` | **survives** | “identified accountable natural person”; “model, agent, synthetic reviewer, or role ID cannot qualify”; raw votes/dissent public | main §4.8 |
| `G-001` | **survives** | observable violations include substitution, hidden reruns, threshold/materiality changes, exclusion, denominator edits, and outcome-contingent rewards | main §4.12 |
| `H-001` | **survives** | S0-GAP-02 owns “canonical serialization; binding and hiding commitment; key/secret management; access control and logging; dual-control reveal; rotation, succession, challenge, incident response, and generic evaluator/reviewer machinery” | main §4.9 |
| `I-002` | **survives** | “workflow states are custody facts, not a second authority lattice”; no research identifier/field/package becomes canonical | state §§1 and 6; additive six-file diff |
| `J-004` | **survives_weaker** | “Remaining verified orientation retained: 13+2, ua integrated depth, 0/13, registry profile counts, GY preregistration gate, malformed frontmatter warning” | amendment ledger finding row; primary/census independently carry only the first, second, third, and GY-gate parts |

`E-001` and `F-001` survive at full strength, including the adjacent-role exclusion, non-convergence cost, named humans, predeclared alternates, raw dissent, and synthetic-reviewer ban.

---

## 9. Added-claim classification ledger

| Added claim | Category | Conformance |
| --- | --- | --- |
| no family number under adaptive Option B | revision-required consequence | conforms |
| D-001 trace admitted locally, not composed | revision-required narrowing | conforms |
| all result-informed repair is adaptive | revision-required consequence | conforms |
| materiality specification before direction, else dispute | revision-required consequence | conforms |
| purposive-pool residual | audit-verified narrowing | conforms |
| corroborated vs declared independence | revision-required consequence | conforms |
| strategic supported refusal remains possible | audit-verified narrowing | conforms |
| chronology without denominator definition | owner-boundary consequence | conforms |
| amended INT-R1 envelope and NO-GO ladder | delivered sibling seam | conforms |
| S0-GAP-02 canonical supersession only | audit-required seam correction | conforms |
| YAML null retirement | scope correction | conforms |
| R12/R13 facts | independently reproduced corrections | conforms |
| FIPS/commitment split | source-attribution correction | conforms |
| typed records/state sketches | noncanonical engineering illustration | conforms; no owner/schema frozen |
| architect Boole/envelope correction | later verified sibling result | not an amendment defect; current narrative corrected |

No added unverified INT-R9 theorem or capability claim was found.

---

## 10. Seam ledger

### S0-GAP-02

| Question | Result |
| --- | --- |
| “equivalent” escape hatch removed? | yes; only expressly governed canonical supersession |
| commitment primitive chosen by INT-R9? | no |
| key/secret store chosen? | no |
| access-control/rotation/challenge platform duplicated? | no |
| evaluator implementation duplicated? | no |
| first-event-specific requirements retained without taking generic ownership? | yes |

### INT-R10

| Question | Result |
| --- | --- |
| withdrawn `3 * delta` asserted as current INT-R9 result? | no |
| `3/100` asserted as current INT-R9 result? | no |
| `1/300` prescribed in amended INT-R9 files? | no |
| withdrawn values retained as struck/correction history? | yes, correctly |
| current narrative says `research/int-r10-revision` supersedes old branch? | yes |
| all frontmatter/comments rebound? | no — finding `INT-R9-V-002` |
| “audit-pending” wording current after revision verification `CONFORMS`? | no — stale wording, finding `INT-R9-V-002` |

---

## 11. Boundary ledger

| Boundary | Result |
| --- | --- |
| amendment files changed | exactly five existing INT-R9 research artifacts plus one new amendment ledger |
| `policy-engine/src/` | unchanged |
| tests | unchanged |
| audit bundle | unchanged |
| outcome corpus and adjudications | unchanged |
| unrelated existing documents | unchanged |
| canonical owner | not appointed |
| package/API/database/schema | not fixed |
| status lattice | one existing lattice; workflow states custody-only |
| confidence ownership | local ledger remains canonical; no parent/family ledger |
| oracle ownership | S0-GAP-02 retained; no sibling |
| S0-K13 | preserved |
| S0-K15 | preserved |
| S0-K16 | preserved |
| `research_only` | true in all Markdown frontmatters; YAML contains comments only |
| positive-promotion promise deny-list | explicit in primary/census/state/fixtures; exact phrase missing from amendment-ledger frontmatter (`INT-R9-V-004`) |

---

## 12. Residual gaps for consolidation

| Gap | Severity | Required disposition |
| --- | --- | --- |
| superseded INT-R10 branch/commit in five frontmatters and YAML comment | material | rebind to verified `research/int-r10-revision` identity |
| stale “Theorem B audit-pending” wording | material bookkeeping | update to the verified revision standing while preserving “no current numeric theorem for outcome-dependent repair” |
| unstruck ledger R1/§7 shorthand saying sharpness/current arithmetic recorded | material bookkeeping | replace with corrected Boole/canonical-envelope wording or state that the old material was withdrawn |
| `J-004` registry-profile and malformed-frontmatter subfacts only in compact ledger assertion | minor | source-anchor them in a retained orientation note or explicitly retire them as non-load-bearing audit history |
| amendment-ledger frontmatter lacks exact positive-promise exclusion | minor | add explicit deny-list phrase for uniformity |

None of these gaps authorizes reopening Option B or the substantive R1–R14 conclusion.

---

## 13. Ledger conclusion

```text
Option B substantive conformance = yes
sequence-level numeric family claim = absent
D-001 forbidden outcome = unavailable
R1-R14 substantive execution = complete
kill-rule closure = complete under withdrawal semantics
current execution readiness = blocked
commendations = 9 total; 8 full + 1 weaker
provenance/bookkeeping cleanup = open
verification verdict = CONFORMS_WITH_GAPS
```

Consolidation may adopt the amended INT-R9 result as a settled **nonnumeric adaptive anti-selection and custody protocol**, while carrying the five cleanup rows in §12 as explicit open items.
