---
title: INT-R9 — Anchor and External-Citation Verification
status: delivered
kind: independent-audit
research_task: INT-R9
audit_verdict: NO_GO
repository: https://github.com/DenisKopylov/polisyos
audited_branch: research/int-r9-first-promotion-protocol
audited_commit: f5ad922377e38ee3ddbecb33293300bca25a9ad7
current_repository_commit: d152565dcc11cea457dacd61fadc6e15dc3ecc86
inspection_date: 2026-08-03
authoritative_for:
  - exhaustive verification of every repository anchor in the INT-R9 contamination census
  - adversarial sample verification of load-bearing repository anchors in the main INT-R9 report
  - existence, attribution, and transfer-validity review of every named external source in INT-R9 section 3
may_not_use_for:
  - production implementation authorization
  - final code, wire, schema, package, or database contract
  - canonical owner appointment
  - authority grant or capability claim
  - benchmark passage
  - replacement of primary-source reading for a later changed source or repository ref
research_only: true
---

# INT-R9 — Anchor and External-Citation Verification

## 1. Verification rules

Repository anchors were evaluated at exactly
`d152565dcc11cea457dacd61fadc6e15dc3ecc86`. For each anchor the audit asked:

1. does the path exist at that ref;
2. does every cited line in the stated range exist; and
3. does the content in that range support the sentence that invokes it?

A range whose end exceeds EOF is recorded as **range_overrun**, even when earlier lines support the
claim. A range pointing to the wrong nearby section is **misanchored**. This matters because the
research brief requires checkable `path:line` evidence, not a path that forces a reviewer to
search.

External sources were checked on three axes:

1. **existence** — source and cited identifier resolve to the named work;
2. **attribution** — the report accurately states what the source says; and
3. **transfer** — the claimed PolicyOS lesson survives the difference between the source setting
   and one n=1 authority-bearing first promotion.

## 2. Pass A — Exhaustive contamination-census anchor verification

### 2.1 Count

The 199-line census contains **43 anchor occurrences** collapsing to **25 distinct path/range
pairs**. Every distinct pair and every repeated sentence using it was checked. The repetition
matters because a single bad shared anchor affects most of the case rows.

### 2.2 Distinct-anchor ledger

| # | Census target at baseline | Path exists | Full range exists | Support verdict | Audit note |
| ---: | --- | --- | --- | --- | --- |
| 1 | `docs/research/universal-policy-design/outcome-corpus/README.md:1-48` | yes | yes | supports | Names thirteen real cases and their domains. |
| 2 | `.../outcome-corpus/adjudications/README.md:1-52` | yes | yes | supports | Describes guide and lists fifteen manifests. |
| 3 | `.../adjudications/ua-msme-affordable-loans-2022.adjudication.json:1-170` | yes | **no** | supports before EOF | Expected ID, label, gold card, votes, topology, and authority are present, but line 170 does not exist. |
| 4 | `docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:404-430` | yes | yes | **does not support cited current-state sentence** | Range begins in “Forward Direction.” The one-case/12-case/0-rate/D3.8 facts are at `:382-398`. |
| 5 | `architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json:1-260` | yes | yes | supports | Contains development refs and narrow `may_not_use_for` boundary. |
| 6 | `src/polisyos/runtime/quality/promotion_sequence.py:130-180` | yes | yes | supports | Contains ua-msme default G4 reference. |
| 7 | `.../adjudications/w11a_berlin_rent_cap_2020.adjudication.json:1-170` | yes | **no** | supports before EOF | Public expected answer and deep-pilot topology present; endpoint absent. |
| 8 | `.../adjudications/w11a_boston_operation_ceasefire_1996.adjudication.json:1-170` | yes | **no** | supports before EOF | Public expected answer and deep-pilot topology present; endpoint absent. |
| 9 | `layer2_s14_universality_assurance_manifest.json:170-245` | yes | yes | supports | Names Boston S12 evidence and ua-msme development refs. |
| 10 | `.../adjudications/w11a_eu_temporary_protection_ukraine_2022.adjudication.json:1-170` | yes | **no** | **supports with wording correction** | Expected ID, label, votes, topology visible; `gold_card` is null. |
| 11 | `layer2_s14_universality_assurance_manifest.json:190-250` | yes | yes | supports | Names EU S13 envelope revision. |
| 12 | `.../adjudications/w11a_ghana_free_shs_2017.adjudication.json:1-170` | yes | **no** | supports before EOF | Expected ID, non-null answer metadata, votes; endpoint absent. |
| 13 | `.../adjudications/w11a_india_aadhaar_dbt_2016.adjudication.json:1-170` | yes | **no** | **supports with wording correction** | Expected ID, label, votes visible; `gold_card` is null. |
| 14 | `.../adjudications/w11a_mexico_ssb_tax_2014.adjudication.json:1-170` | yes | **no** | supports before EOF | Expected ID, non-null gold cards, votes; endpoint absent. |
| 15 | `.../adjudications/w11a_netherlands_room_for_river_2007.adjudication.json:1-170` | yes | **no** | supports before EOF | Expected ID, non-null gold cards, votes; endpoint absent. |
| 16 | `layer2_s14_universality_assurance_manifest.json:200-255` | yes | yes | supports | Names Netherlands certified-envelope delta. |
| 17 | `.../adjudications/w11a_pakistan_ehsaas_cash_2020.adjudication.json:1-170` | yes | **no** | **supports with wording correction** | Expected ID, label, votes visible; `gold_card` is null. |
| 18 | `.../adjudications/w11a_uk_levelling_up_fund_2021.adjudication.json:1-170` | yes | **no** | supports before EOF | Expected ID, non-null cards, votes; endpoint absent. |
| 19 | `.../adjudications/w11a_uk_mtd_vat_2019.adjudication.json:1-170` | yes | **no** | supports before EOF | Expected ID, non-null cards, votes; endpoint absent. |
| 20 | `.../adjudications/w11a_uk_work_programme_2011.adjudication.json:1-170` | yes | **no** | supports before EOF | Expected ID, non-null cards, votes; endpoint absent. |
| 21 | `.../adjudications/w11a_us_ppp_2020.adjudication.json:1-170` | yes | **no** | supports before EOF | Expected ID, non-null cards, votes; endpoint absent. |
| 22 | `outcome-corpus/README.md:18-48` | yes | yes | supports | Supports alias/name reconciliation for the real-case list. |
| 23 | `adjudications/README.md:29-52` | yes | yes | supports | Supports committed manifest-name reconciliation and 15 count. |
| 24 | `adjudications/README.md:9-27` | yes | yes | supports guide only | Supports role/expertise/conflict/disagreement guidance and topology modes, not the census's numerical “three deep-pilot manifests.” |
| 25 | `layer2_s14_universality_assurance_manifest.json:1-340` | yes | yes | supports | S14 expressly denies production/recommendation/publication/claim/closeout/gold-label authority. |

### 2.3 Repeated-anchor consequences

The constitution misanchor appears in the ua-msme row and every row whose “no integrated-loop
evidence” assertion relies on the current-state statement. The conclusion is true, but the cited
range is not evidence for it. The exact replacement range is:

```text
policy-engine/docs/system-design-decisions/
  universal-policy-design-system-vision-and-organizing-rules.md:382-398
```

That range states:

- full composed loop only for ua-msme;
- other twelve cases per-slice, not integrated;
- all thirteen remain blockers;
- `useful_design_rate = 0`;
- B is shadow; and
- D3.8 is unbuilt.

The `:1-170` pattern is similarly systematic. It is not enough to say “GitHub ignores the excess”:
the audit contract asks whether the range exists. It does not. Exact end lines should be generated
from the pinned files rather than copied as a uniform convenience.

### 2.4 Factual corrections within the census

1. **Calibration count.** The census sentence “three deep-pilot manifests record
   `deep-pilot-round-1`” is incomplete. Four manifests do: synthetic housing, Berlin, Boston, and
   EU temporary protection.
2. **Gold cards.** EU, India, and Pakistan have public labels/votes/expected IDs but null gold
   cards. They remain contaminated; the exact exposed field list must be case-specific.
3. **Authority levels.** The census does not depend on uniform authority levels, but the supplied
   orientation did. The exact distribution is recorded in the orientation ledger.

### 2.5 Census conclusion

Despite these defects, the census's decisive conclusion is verified:

```text
13 public real regression cases
+ 2 public synthetic adjudication fixtures
+ 0 sealed decisive cases
+ 0 adjacent unseen cases
```

No current case has both answer secrecy and independent case-selection/implementation history.

## 3. Main-deliverable anchor sampling

### 3.1 Sampling rule

The audit used a **judgmental, adversarial, load-bearing sample**. It included:

- every repository anchor used in the Executive Finding;
- every anchor used to state current capability, denominator, or readiness;
- every anchor supporting the ua-msme exclusion;
- every anchor invoked to delegate risk, status, time, oracle, or obligation ownership;
- every anchor supporting the final bounded claim or consolidation handoff;
- at least one anchor from each numbered section; and
- anchors whose very wide ranges made unsupported content easier to hide.

The sample contains **32 anchor claims across 28 distinct repository files**, in addition to the
43 census occurrences audited exhaustively.

### 3.2 Sample ledger

| # | Main-report anchor/claim | Verification | Verdict |
| ---: | --- | --- | --- |
| 1 | `GY-engine-subordination.md:2500-2575` — INT-R9 ratified before candidate inspection; V2 permits positive or honest abstention | exact Phase-7 text inspected | supports; actual key sentences are within the cited neighborhood |
| 2 | constitution `:145-230` — shadow B, Rule 5, one lattice, no hard-code fallback | exact rule block inspected | supports in substance; range is broad but relevant |
| 3 | identity decision `:35-220` — epistemic custodian, not administrator | exact boundary sections inspected | supports |
| 4 | `promotion_sequence.py:1-270` — one canonical N9 sequence and typed receipt | source inspected | supports; broad but accurate |
| 5 | `promotion_sequence.py:130-180` — ua default | exact range inspected | supports precisely |
| 6 | `promotion_sequence.py:354-370` — one risk scope per N9 problem binding | independent audit anchor, absent from INT-R9 reasoning | supports audit's blocking finding |
| 7 | `gy_waist.py:120-310` — obligation classes/status/terminal vocabulary | source inspected | supports, but range is broad |
| 8 | `candidate_firewall.py:1-260` — B cannot fill protected owner slots | source inspected | supports |
| 9 | `confidence_ledger.py:1-230` — conditionality, scope, predictable allocation concepts | source inspected | supports only at model level; not cross-scope composition |
| 10 | `confidence_ledger.py:158-195` — scope identity | exact independent anchor | supports per-problem scope finding |
| 11 | `confidence_ledger.py:1285-1368` — ordinal and prior-spend derivation | exact independent anchor | supports scope-local reset finding |
| 12 | `confidence_ledger.py:4005-4027` — Basel-square formula | exact independent anchor | supports scope-local schedule |
| 13 | registry TOML `:1-232` — two schedules and five proof profiles | complete file enumerated | supports exactly |
| 14 | S14 manifest `:1-340` — narrow assurance and development evidence | complete file inspected | supports |
| 15 | custody kernel `:90-109` — S0-K13/K15/K16 | exact statement block inspected | supports semantic predicates, committed packages, bounded passage |
| 16 | S0-GAP-02 register `:75-210` — oracle/evaluator ownership | exact YAML block inspected | supports delegation and overlap boundary |
| 17 | failure register `:200-900` — P29/P33/P34 | exact range and actual rows inspected | **misanchored**; rows are around `:70-78` |
| 18 | Custody Time Model `:35-240` — temporal roles and canonical reaction | decision inspected | supports; range broad but relevant |
| 19 | Atlas plan `:1000-1280` — unified governed status/public projection | plan inspected | supports handoff direction; not an INT-R9 owner grant |
| 20 | outcome README `:1-48` — 13 real cases | exact range inspected | supports |
| 21 | adjudication README `:1-52` — 15 manifests and guide | exact range inspected | supports |
| 22 | constitution `:404-430` — current 0/13 state | exact range inspected | **misanchored**; support at `:382-398` |
| 23 | ua adjudication `:1-170` — public answer | file inspected and endpoint tested | content supports; range overruns EOF |
| 24 | Berlin/Boston/EU deep-pilot claim | all three files inspected | supports three real deep-pilot cases but not the complete all-15 count |
| 25 | report §2.5 “three deep-pilot manifests” | all 15 files enumerated | false if “manifests” includes synthetic housing; exact count four |
| 26 | report §2.4 universal exposed gold cards | all 13 files inspected | false as non-null universal claim; EU/India/Pakistan null |
| 27 | GY plan frontmatter parse warning | top lines inspected | warning correct; colon-rich plain scalar is unsafe YAML |
| 28 | Atlas plan frontmatter parse warning | top lines inspected | warning correct |
| 29 | Wave-2 backlog frontmatter parse warning | top lines inspected | warning correct |
| 30 | main report §10.1 INT-R1 artifact name | INT-R1 delivered branch inspected | wrong artifact name; delivered shape is `ObligationCoverageEnvelope` |
| 31 | main report §10.2 no duplicate oracle owner | all five INT-R9 files compared to S0-GAP-02 spec | substantially supported, with “equivalent” escape-hatch caveat |
| 32 | main report final “cumulative risk accounting” | source chain traced | unsupported across three design-problem scopes; blocking |

## 4. Pass B — External-source verification

### 4.1 Transfer standard applied

The report's own transfer rule is correct: a PolicyOS first promotion is not a randomized trial,
not an i.i.d. benchmark sample, and not a conventional null-hypothesis rejection. External work
can justify anti-adaptivity mechanisms, preregistration discipline, aggregate accounting,
corroboration, disagreement retention, and publication rules. It cannot establish that one policy
case is representative or that an authority claim is substantively true.

### 4.2 Source ledger

| # | Source as cited | Exists / attribution | Transfer review | Verdict |
| ---: | --- | --- | --- | --- |
| 1 | Dwork et al., “The reusable holdout,” *Science* 2015, [10.1126/science.aaa9375](https://doi.org/10.1126/science.aaa9375) | exists; adaptive holdout reuse/generalization correctly attributed | only structural lesson transfers; report expressly rejects direct authority theorem | verified |
| 2 | Dwork et al., STOC 2015, [10.1145/2746539.2746580](https://doi.org/10.1145/2746539.2746580) | exists; adaptive statistical validity correctly attributed | non-i.i.d. policy cases and semantic authority are outside theorem | verified |
| 3 | ICMJE Clinical Trial Registration Recommendations | official policy exists; prospective registration purpose accurately stated | prospectivity/deviation visibility transfer; trial registration authority does not | verified |
| 4 | SPIRIT 2013 explanation, BMJ 346:e7586, [10.1136/bmj.e7586](https://doi.org/10.1136/bmj.e7586) | exists; dated versions and modification communication correctly attributed | versioned amendment discipline transfers | verified |
| 5 | AEA RCT Registry policy | official policy exists; permits registration during different phases and preserves versions | report correctly treats it as weaker than required pre-inspection sealing | verified |
| 6 | Claesen et al. 2021, [10.1098/rsos.211037](https://doi.org/10.1098/rsos.211037) | exists; 27-study deviation comparison and reported counts accurately stated | does not estimate INT-R9 failure probability; supports first-class deviations | verified |
| 7 | Scientific Reports Registered Reports policy | official policy exists; in-principle acceptance before results and stage-2 adherence checks | result-independent publication and controls transfer; editorial acceptance is not authority | verified |
| 8 | Scheel, Schijen & Lakens 2021, [10.1177/25152459211007467](https://doi.org/10.1177/25152459211007467) | exists; 96% vs 44% sampled positive-result comparison and caveats accurately stated | no causal rate target imported | verified |
| 9 | Simmons, Nelson & Simonsohn 2011, [10.1177/0956797611417632](https://doi.org/10.1177/0956797611417632) | exists; flexible choices and false-positive inflation accurately attributed | numerical simulations do not quantify PolicyOS; report says so | verified |
| 10 | Gelman & Loken 2014, [10.1511/2014.111.460](https://doi.org/10.1511/2014.111.460) | exists; data-dependent forking paths without deliberate fishing accurately attributed | supports binding multiple degrees of freedom, not an authority theorem | verified |
| 11 | Pocock 1977, [10.1093/biomet/64.2.191](https://doi.org/10.1093/biomet/64.2.191) | exists; repeated looks/group-sequential aggregate control accurately attributed | procedural lesson transfers; no exact PolicyOS allocation imported | citation verified; repository bridge incomplete |
| 12 | O'Brien & Fleming 1979, [10.2307/2530245](https://doi.org/10.2307/2530245) | exists; controlled repeated significance testing accurately attributed | same as Pocock | citation verified; repository bridge incomplete |
| 13 | Howard et al. 2021, [10.1214/20-AOS1991](https://doi.org/10.1214/20-AOS1991) | exists; time-uniform confidence sequences accurately attributed | requires exact filtration/assumptions; does not compose unknown PolicyOS scopes automatically | citation verified; repository bridge incomplete |
| 14 | FDA 2023 draft on one adequate investigation plus confirmatory evidence | official draft exists; context-dependent/nonbinding standing accurately stated | corroboration analogy transfers; legal substantial-evidence standard does not | verified |
| 15 | FDA June 2026 revised draft on substantial evidence | official revised draft exists; one pivotal investigation plus confirmatory evidence accurately summarized | same bounded institutional analogy; no PolicyOS authority imported | verified |
| 16 | Recht et al., ICML/PMLR 2019 | primary PMLR paper exists; rebuilt CIFAR/ImageNet and score drops accurately stated | authors caution new sets are harder and do not identify adaptivity alone; report preserves caveat | verified |
| 17 | Yang et al., arXiv:2311.04850 | work exists; paraphrase/translation contamination and fresh one-time exam recommendation accurately attributed | supports semantic/provenance checks, not population validity | verified |
| 18 | Cohen 1960, [10.1177/001316446002000104](https://doi.org/10.1177/001316446002000104) | exists; nominal inter-rater agreement coefficient accurately attributed | diagnostic only; report correctly denies correctness/authority transfer | verified |
| 19 | Krippendorff 2004, [10.1111/j.1468-2958.2004.tb00738.x](https://doi.org/10.1111/j.1468-2958.2004.tb00738.x) | exists; reliability assumptions/misuse review accurately attributed | diagnostic only | verified |
| 20 | Rosenthal 1979, [10.1037/0033-2909.86.3.638](https://doi.org/10.1037/0033-2909.86.3.638) | exists; file-drawer problem accurately attributed | supports result-independent publication, not proof of benign careers | verified |
| 21 | NIST FIPS 180-4, [10.6028/NIST.FIPS.180-4](https://doi.org/10.6028/NIST.FIPS.180-4) | exists; secure hash standard accurately cited | supports digest/change-detection properties; non-hiding conclusion requires threat model/commitment literature | verified with attribution clarification |
| 22 | Damgård, Pedersen & Pfitzmann 1996, [10.7146/brics.v3i45.20047](https://doi.org/10.7146/brics.v3i45.20047) | exists; statistically hiding commitments accurately attributed | binding/hiding distinction directly relevant; exact mechanism properly deferred | verified |
| 23 | RFC 3161, [10.17487/RFC3161](https://doi.org/10.17487/RFC3161) | exists; timestamp proof-of-existence and policy caveats accurately attributed | time evidence transfers; semantic truth and TSA governance do not | verified |

### 4.3 External-citation conclusion

No fabricated source, wrong DOI, or wholesale statistical transfer was found. Section 3 is one of
the deliverable's strongest parts. Its central failure occurs after the citation: INT-R9 invokes
the correct aggregate-risk lesson but never specifies how canonical per-design-problem scopes
compose into the three-slot family.

## 5. Findings from Passes A and B

### `INT-R9-A-001` — material — uniform adjudication ranges overrun EOF

All thirteen `:1-170` endpoint probes returned no line 170. The content exists earlier, so the
substantive contamination result remains. Exact ranges are required before consolidation.

### `INT-R9-A-002` — material — current-state range points to wrong section

The repeated `:404-430` anchor is not merely broad; it begins after the facts it is meant to prove.
Replace with the exact `:382-398` block.

### `INT-R9-A-003` — material — incomplete calibration correction

The prompt's all-null premise was wrong. INT-R9 found three real deep-pilot cases but stated the
count over all manifests as three; synthetic housing makes four.

### `INT-R9-A-004` — minor — gold-card value overstatement

The answer-bearing conclusion survives because expected IDs, labels, votes, evidence/context refs,
and reviewer metadata are visible. The field inventory must distinguish a present key from a
non-null card.

### `INT-R9-A-005` — material — failure-register misanchor

P29/P33/P34 are near lines 70-78. The main report's `:200-900` range does not prove those claims.

### `INT-R9-B-001` — commendation — external transfer boundaries

Preserve section 3's explicit theorem/pattern/governance distinctions and n=1 caveats.

### `INT-R9-B-002` — material — correct literature, missing composition

The sequential-design sources do not make “cumulative ledger” true. A repository-compatible
composition result is still needed.

### `INT-R9-B-003` — minor — hash attribution

State that non-hiding follows from combining the hash standard with predictable-answer threat
analysis and commitment-scheme properties, rather than attributing the whole proposition to FIPS.

## 6. Pass A/B disposition

Anchor corrections alone would support `GO_WITH_REVISIONS`, not `NO_GO`. The `NO_GO` arises because
the correctly cited sequential-design principle exposes an unclosed current-source gap: three
canonical problem scopes are not one controlled family. The anchor and citation record therefore
feeds, but does not independently replace, blocking finding `INT-R9-D-001`.
