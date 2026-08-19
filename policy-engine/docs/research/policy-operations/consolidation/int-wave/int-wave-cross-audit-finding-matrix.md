---
title: INT wave — Cross-Audit Finding Matrix
status: delivered
kind: research-consolidation
research_scope: [INT-R1, INT-R9, INT-R10]
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-wave-consolidation
pinned_repository_commit: a548a2f939995ad81b4febe3402bdcb35ae11bad
inspection_date: 2026-08-03
research_only: true
finding_count: 107
disposition_vocabulary: [ratify_now, retain_as_research, revise, defer, repository_fix_separate, additional_research, reject]
int_r9_verification_standing: verified_pending
may_not_use_for:
  - production implementation authorization
  - final code, wire, schema, package, database, serialization, or API contract
  - canonical owner appointment
  - authority grant
  - capability claim
  - benchmark passage
  - automatic amendment of any authoritative backlog, plan, or system-design decision
  - legal compliance or institutional competence conclusion
  - permission to execute, promote, release, or publish a governed result
  - assertion that bounded_complete is currently issuable
  - assertion that a live family declaration, chronology verifier, aggregate projection, or reproduction chain exists
  - numeric family-wise claim for outcome-dependent repair
  - unconditional claim that all applicable obligations are known
  - change to the current obligation denominator, confidence scope identity, risk budget, status lattice, or canonical owner
---

# INT wave cross-audit finding matrix

## Disposition vocabulary

`ratify_now` · `retain_as_research` · `revise` · `defer` · `repository_fix_separate` · `additional_research` · `reject`.

## Count reconciliation

| Register | Rows | True count | Reconciliation |
| --- | ---: | --- | --- |
| INT-R1 audit | 26 | 13 commendation; 8 material-labelled; 5 minor | Prose says 7/6 because the caught orientation row is classified differently; register rows control. |
| INT-R1 verification | 8 | 6 commendation; 2 minor | No discrepancy. |
| INT-R9 audit | 33 | **9 commendation**; 16 material; 5 minor; 3 blocking | Some prose says eight; the explicit register has nine. |
| INT-R9 verification | 0 | none | Not present at the pin; `verified_pending`. |
| INT-R10 audit | 31 | **16 commendation**; **7 material**; 3 minor; 5 blocking | Prose says 15/8; the explicit register has 16/7. |
| INT-R10 verification | 9 | 9 commendation | No discrepancy. |

**Disposition totals:** `ratify_now` 19 · `retain_as_research` 41 · `revise` 34 · `defer` 4 · `repository_fix_separate` 4 · `additional_research` 2 · `reject` 3.

## Source keys

| Key | Exact pinned source range |
| --- | --- |
| `R1-A` | `policy-engine/docs/research/policy-operations/audits/int-r1/int-r1-independent-audit.md:98-129` |
| `R1-V` | `policy-engine/docs/research/policy-operations/audits/int-r1/int-r1-amendment-verification.md:122-135` |
| `R9-A` | `policy-engine/docs/research/policy-operations/audits/int-r9/int-r9-independent-audit.md:108-144` |
| `R10-A` | `policy-engine/docs/research/policy-operations/audits/int-r10/int-r10-independent-audit.md:118-153` |
| `R10-V` | `policy-engine/docs/research/policy-operations/audits/int-r10/int-r10-revision-verification.md:177-450` |

## INT-R1

| ID | Sev. | Disposition | Finding | State | Src. |
| --- | --- | --- | --- | --- | --- |
| `INT-R1-A-001` | `commendation` | `retain_as_research` | All 31 unique census anchor groups resolved… | Preserved | `R1-A` |
| `INT-R1-A-002` | `minor` | `revise` | CONTRIBUTING.md supported general… | Amendment narrowed… | `R1-A` |
| `INT-R1-A-003` | `commendation` | `retain_as_research` | No broken or deceptively adjacent core… | Preserved as source-… | `R1-A` |
| `INT-R1-B-001` | `material` | `revise` | The Normative Systems catalog record did… | Detailed attribution… | `R1-A` |
| `INT-R1-B-002` | `commendation` | `retain_as_research` | External transfers stated their limits and… | Preserved transfer… | `R1-A` |
| `INT-R1-B-003` | `minor` | `revise` | Citations needed stable identifiers and… | Normalized in the… | `R1-A` |
| `INT-R1-C-001` | `material` | `ratify_now` | The unseen-extension premise required a… | Amended result… | `R1-A` |
| `INT-R1-C-002` | `commendation` | `ratify_now` | Search volume, randomization, TTL, review,… | Safe negative… | `R1-A` |
| `INT-R1-D-001` | `material` | `ratify_now` | Compiler completeness and validator… | Central authority-… | `R1-A` |
| `INT-R1-D-002` | `material` | `ratify_now` | Independent review and mutation are… | Theorem/protocol… | `R1-A` |
| `INT-R1-D-003` | `material` | `additional_research` | Independence was specified but not… | Current issuance… | `R1-A` |
| `INT-R1-D-004` | `commendation` | `retain_as_research` | The five-row P29 stopping taxonomy was… | Useful research… | `R1-A` |
| `INT-R1-E-001` | `commendation` | `ratify_now` | The benchmark banned self-oracles and… | Self-oracle… | `R1-A` |
| `INT-R1-E-002` | `commendation` | `retain_as_research` | Benchmark non-passage and… | Preserved negative… | `R1-A` |
| `INT-R1-E-003` | `commendation` | `ratify_now` | Producer-filled independence metadata could… | Self-attestation is… | `R1-A` |
| `INT-R1-F-001` | `commendation` | `ratify_now` | Coverage assessments feed the existing… | One-lattice/no-auto-… | `R1-A` |
| `INT-R1-F-002` | `minor` | `revise` | NO_COVERAGE_BLOCKER had to remain non-… | Amendment made it… | `R1-A` |
| `INT-R1-G-001` | `material` | `repository_fix_separate` | The enum defect was use-conditional; the… | Research was corrected | `R1-A` |
| `INT-R1-H-001` | `commendation` | `retain_as_research` | Required artifacts, lifecycle,… | Preserved without… | `R1-A` |
| `INT-R1-H-002` | `material` | `repository_fix_separate` | OM-01 could not execute without obligation-… | Open as GY-GAP1 | `R1-A` |
| `INT-R1-H-003` | `minor` | `revise` | The benchmark overclaimed generic keyword-… | Amendment narrowed to… | `R1-A` |
| `INT-R1-H-004` | `commendation` | `ratify_now` | A decisive omission or validator fault… | Safe authority-band… | `R1-A` |
| `INT-R1-H-005` | `commendation` | `retain_as_research` | The research diff was additive-only and… | Preserved scope… | `R1-A` |
| `INT-R1-I-001` | `material-orientation` | `revise` | The supplied denominator was 14; full… | Corrected before… | `R1-A` |
| `INT-R1-I-002` | `commendation` | `retain_as_research` | Other material supplied-orientation facts… | Preserved… | `R1-A` |
| `INT-R1-I-003` | `minor` | `revise` | The 0-of-13 statement applied only to the… | Amendment scoped the… | `R1-A` |
| `INT-R1-V-001` | `commendation` | `retain_as_research` | All eleven amendment requirements were… | Verified | `R1-V` |
| `INT-R1-V-002` | `commendation` | `retain_as_research` | All audit consolidation conditions and… | Verified | `R1-V` |
| `INT-R1-V-003` | `commendation` | `retain_as_research` | All thirteen audit commendations survived… | Verified against… | `R1-V` |
| `INT-R1-V-004` | `minor` | `revise` | The amended_after_audit SHA was stale. | Mechanically… | `R1-V` |
| `INT-R1-V-005` | `minor` | `revise` | Atlas and GY claims used revision-line… | Still a source-… | `R1-V` |
| `INT-R1-V-006` | `commendation` | `retain_as_research` | No unmarked new load-bearing claim was… | Verified | `R1-V` |
| `INT-R1-V-007` | `commendation` | `retain_as_research` | Owner boundaries, one lattice, sibling… | Verified | `R1-V` |
| `INT-R1-V-008` | `commendation` | `retain_as_research` | The halving removed repetition and… | Verified | `R1-V` |

## INT-R9

| ID | Sev. | Disposition | Finding | State | Src. |
| --- | --- | --- | --- | --- | --- |
| `INT-R9-A-001` | `material` | `revise` | Thirteen adjudication citations overran end… | Current amended text… | `R9-A` |
| `INT-R9-A-002` | `material` | `revise` | The current-state constitution citation… | Current amended text… | `R9-A` |
| `INT-R9-A-003` | `material` | `revise` | The census undercounted deep-pilot… | Current amended text… | `R9-A` |
| `INT-R9-A-004` | `minor` | `revise` | Gold-card wording conflated visible answer-… | Current amended text… | `R9-A` |
| `INT-R9-A-005` | `material` | `revise` | The failure-pattern citation missed… | Current amended text… | `R9-A` |
| `INT-R9-A-006` | `commendation` | `retain_as_research` | The 13/15 denominator, contamination, ua-… | Preserved | `R9-A` |
| `INT-R9-B-001` | `commendation` | `ratify_now` | Procedural transfer was kept separate from… | Safe authority-claim… | `R9-A` |
| `INT-R9-B-002` | `material` | `additional_research` | Sequential-design citations did not… | Current amended text… | `R9-A` |
| `INT-R9-B-003` | `minor` | `revise` | FIPS digest properties did not by… | Current amended text… | `R9-A` |
| `INT-R9-C-001` | `blocking` | `revise` | The earliest-slot claim depended on… | Current amended text… | `R9-A` |
| `INT-R9-C-002` | `material` | `ratify_now` | Later slots may use outcome-informed… | Adaptive… | `R9-A` |
| `INT-R9-C-003` | `commendation` | `ratify_now` | The protocol denied population validity,… | Safe limit on… | `R9-A` |
| `INT-R9-D-001` | `blocking` | `repository_fix_separate` | No-reset prose did not create a cross-scope… | Underlying missing… | `R9-A` |
| `INT-R9-D-002` | `material` | `ratify_now` | General repair was not prospectively… | Current amended text… | `R9-A` |
| `INT-R9-D-003` | `material` | `defer` | Materiality had outcome-changing force but… | Current amended text… | `R9-A` |
| `INT-R9-E-001` | `commendation` | `retain_as_research` | ua-msme was correctly excluded from… | Case-specific… | `R9-A` |
| `INT-R9-E-002` | `material` | `retain_as_research` | Within-pool randomness did not remove pool-… | Residual selection… | `R9-A` |
| `INT-R9-E-003` | `minor` | `retain_as_research` | ua-msme reopening should be extraordinary,… | Preserved case-… | `R9-A` |
| `INT-R9-F-001` | `commendation` | `retain_as_research` | Named humans, alternates, raw dissent, and… | Strong protocol… | `R9-A` |
| `INT-R9-F-002` | `material` | `defer` | Declared independence still allowed… | Current amended text… | `R9-A` |
| `INT-R9-G-001` | `commendation` | `retain_as_research` | Useful-rate optimization was tied to… | Preserved protocol… | `R9-A` |
| `INT-R9-G-002` | `material` | `defer` | Controls could not rule out a cautious… | No positive-result or… | `R9-A` |
| `INT-R9-G-003` | `material` | `defer` | Narrative and YAML disagreed on metric… | Current amended YAML… | `R9-A` |
| `INT-R9-H-001` | `commendation` | `retain_as_research` | Generic oracle/evaluator custody remained… | Preserved owner reuse… | `R9-A` |
| `INT-R9-H-002` | `material` | `revise` | The INT-R1 artifact and NO-GO ladder were… | Current amended text… | `R9-A` |
| `INT-R9-H-003` | `minor` | `revise` | A consolidation-approved equivalent could… | Current amended text… | `R9-A` |
| `INT-R9-I-001` | `material` | `revise` | The 852-line YAML had hardened into a de… | Current YAML is… | `R9-A` |
| `INT-R9-I-002` | `commendation` | `retain_as_research` | The branch was additive-only and did not… | Preserved scope… | `R9-A` |
| `INT-R9-I-003` | `blocking` | `revise` | accepted_narrow_scope overstated the… | Current amended… | `R9-A` |
| `INT-R9-J-001` | `material` | `revise` | Calibration orientation omitted synthetic… | Current amended text… | `R9-A` |
| `INT-R9-J-002` | `material` | `revise` | authority_level distribution was 5… | Current amended text… | `R9-A` |
| `INT-R9-J-003` | `minor` | `revise` | Answer-bearing key presence was conflated… | Current amended text… | `R9-A` |
| `INT-R9-J-004` | `commendation` | `retain_as_research` | Remaining supplied orientation was verified. | Preserved… | `R9-A` |

## INT-R10

| ID | Sev. | Disposition | Finding | State | Src. |
| --- | --- | --- | --- | --- | --- |
| `INT-R10-A-001` | `commendation` | `ratify_now` | The fixed-family weighted-union theorem was… | Core family-claim… | `R10-A` |
| `INT-R10-A-002` | `commendation` | `ratify_now` | The union step required no common null,… | Safe theorem boundary… | `R10-A` |
| `INT-R10-B-001` | `blocking` | `reject` | The original 3-delta sharpness claim was… | Refuted and withdrawn | `R10-A` |
| `INT-R10-B-002` | `commendation` | `retain_as_research` | Disjoint-event sharpness survives only… | Useful qualified… | `R10-A` |
| `INT-R10-C-001` | `material` | `revise` | The adaptive theorem omitted filtered-space… | Formal premises added | `R10-A` |
| `INT-R10-C-002` | `material` | `revise` | An equivalent selection-aware theorem… | Removed from the… | `R10-A` |
| `INT-R10-C-003` | `commendation` | `retain_as_research` | Pathwise fixed caps and no-refund are… | Preserved as a… | `R10-A` |
| `INT-R10-C-004` | `commendation` | `ratify_now` | Adaptation is not impossible, but… | Load-bearing numeric-… | `R10-A` |
| `INT-R10-D-001` | `commendation` | `retain_as_research` | The external transfer ledger was… | Preserved bounded… | `R10-A` |
| `INT-R10-D-002` | `minor` | `revise` | Independent product control and Gaussian… | Separated in the… | `R10-A` |
| `INT-R10-D-003` | `commendation` | `retain_as_research` | E-values were correctly rejected as an… | Preserved method… | `R10-A` |
| `INT-R10-E-001` | `material` | `revise` | The self-graded matrix conflated theorem,… | Revision separates… | `R10-A` |
| `INT-R10-E-002` | `blocking` | `revise` | Aggregate proof failed under the exact… | Re-derived with the… | `R10-A` |
| `INT-R10-E-003` | `commendation` | `ratify_now` | The current adaptive numeric claim was… | Safe prohibition for… | `R10-A` |
| `INT-R10-E-004` | `commendation` | `ratify_now` | Exact event, canonical scopes, terminal… | Supports preserved… | `R10-A` |
| `INT-R10-E-005` | `commendation` | `retain_as_research` | The mandatory fresh-scope trace was… | Preserved as a… | `R10-A` |
| `INT-R10-E-006` | `material` | `repository_fix_separate` | Positive live family reproduction was… | Open part of GY-GAP2 | `R10-A` |
| `INT-R10-F-001` | `material` | `revise` | GY-GAP2 was cited through frontmatter… | All current citations… | `R10-A` |
| `INT-R10-F-002` | `material` | `revise` | Burn-before-execution citations ended… | Source range corrected | `R10-A` |
| `INT-R10-F-003` | `commendation` | `retain_as_research` | Other repository anchors were substantively… | Preserved source… | `R10-A` |
| `INT-R10-G-001` | `blocking` | `reject` | The allocated=3/100 fixture oracle… | Removed | `R10-A` |
| `INT-R10-G-002` | `material` | `revise` | The 614-line sketch hardened into a de… | Schema and vocabulary… | `R10-A` |
| `INT-R10-G-003` | `commendation` | `ratify_now` | Fixtures tested pre-execution enforcement… | One-owner and… | `R10-A` |
| `INT-R10-G-004` | `commendation` | `retain_as_research` | The positive fixture honestly refused at… | Preserved negative… | `R10-A` |
| `INT-R10-H-001` | `commendation` | `retain_as_research` | Diff and research-only scope discipline… | Preserved | `R10-A` |
| `INT-R10-H-002` | `blocking` | `revise` | accepted_narrow_scope overstated the… | Revision now… | `R10-A` |
| `INT-R10-H-003` | `commendation` | `ratify_now` | Stage-0 band boundaries and INT-R1… | Authority/candidate… | `R10-A` |
| `INT-R10-I-001` | `blocking` | `reject` | The supplied orientation discarded exact… | Refuted and corrected… | `R10-A` |
| `INT-R10-I-002` | `minor` | `revise` | Ordinal zero and fresh root policy were… | Exact language and… | `R10-A` |
| `INT-R10-I-003` | `minor` | `revise` | Five proof profiles were mistaken for five… | Full 13/5/7/2/6… | `R10-A` |
| `INT-R10-I-004` | `commendation` | `retain_as_research` | Remaining orientation facts were accurate. | Preserved | `R10-A` |
| `INT-R10-V-001` | `commendation` | `retain_as_research` | The exact source law and canonical envelope… | Verified pinned-… | `R10-V` |
| `INT-R10-V-002` | `commendation` | `retain_as_research` | Aggregate proof was repaired at research… | Verified | `R10-V` |
| `INT-R10-V-003` | `commendation` | `retain_as_research` | The fixture oracle was repaired without… | Verified | `R10-V` |
| `INT-R10-V-004` | `commendation` | `retain_as_research` | Narrow standing was consistent across all… | Verified | `R10-V` |
| `INT-R10-V-005` | `commendation` | `retain_as_research` | Withdrawn arithmetic was no longer… | Verified | `R10-V` |
| `INT-R10-V-006` | `commendation` | `retain_as_research` | The adaptive theorem received its formal… | Verified theorem… | `R10-V` |
| `INT-R10-V-007` | `commendation` | `retain_as_research` | GY-GAP2 was correctly characterized and all… | Verified | `R10-V` |
| `INT-R10-V-008` | `commendation` | `retain_as_research` | All sixteen audited commendations survived… | Verified against the… | `R10-V` |
| `INT-R10-V-009` | `commendation` | `retain_as_research` | All material/minor repairs and… | Verified | `R10-V` |

## Verification boundary

All 107 audit/verification IDs appear exactly once. No INT-R9 verification finding is synthesized because no such artifact exists at the pin. If it lands before architect action, append its IDs once and re-adjudicate Option B; never infer passage from the amender’s own ledger.
