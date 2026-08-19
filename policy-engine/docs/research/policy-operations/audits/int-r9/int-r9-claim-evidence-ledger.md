---
title: INT-R9 — Independent Audit Claim/Evidence Ledger
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
  - machine-readable audit mapping from load-bearing INT-R9 claims to verification method, evidence, and disposition
  - evidence base for the independent INT-R9 NO_GO verdict
may_not_use_for:
  - production implementation authorization
  - final code, wire, schema, package, or database contract
  - canonical owner appointment
  - authority grant or capability claim
  - benchmark passage
  - replacement of the audited INT-R9 deliverable
  - automatic acceptance without reading the cited source at the pinned ref
research_only: true
---

# INT-R9 — Claim/Evidence Ledger

## Ledger conventions

- **verified** — the cited evidence supports the claim at the pinned ref.
- **verified_narrower** — the underlying conclusion survives, but the sentence or scope is too
  strong.
- **misanchored** — the repository contains supporting evidence, but not in the cited range.
- **unsupported** — no inspected mechanism establishes the claim.
- **contradicted** — pinned evidence directly conflicts with the claim.
- **blocked** — the research claim depends on a missing result or unresolved owner and cannot be
  used for promotion.
- **commendable** — verified and important enough to preserve explicitly.

The ledger treats a range ending after EOF as non-resolving even when the file's earlier content
supports the sentence. It treats a statistical citation as supporting only the proposition the
source actually proves, not an unargued PolicyOS transfer.

## Core ledger

| Claim ID | Load-bearing claim | Claimed or relevant location | Verification method | Pinned evidence | Verdict | Finding / consequence |
| --- | --- | --- | --- | --- | --- | --- |
| `INT-R9-CL-001` | Audited branch contains five new files, 3,708 insertions, and no modified pre-existing file. | branch shape | compare `d152565d...f5ad9223` file by file | GitHub commit comparison: five additions under the two INT-R9 paths; zero modifications/deletions | verified | `INT-R9-I-002`; scope discipline preserved |
| `INT-R9-CL-002` | Research baseline is exact `d152565dcc11cea457dacd61fadc6e15dc3ecc86`. | frontmatter and §2.1 | resolve commit and compare parent/base | audited branch is five commits ahead of that exact SHA | verified | baseline pin sound |
| `INT-R9-CL-003` | Outcome corpus has thirteen real proving-ground cases. | census §2; report §2.3 | inspect outcome-corpus README and enumerate named case rows | `docs/research/universal-policy-design/outcome-corpus/README.md:1-48` names 13 | verified | denominator 13 survives |
| `INT-R9-CL-004` | Adjudication directory has fifteen manifests: 13 real plus 2 synthetic. | census §2; report §2.3 | enumerate committed manifest list and reconcile case refs | `.../adjudications/README.md:29-52` lists 15; housing and public-health point to synthetic `cases/` paths | verified | denominator reconciliation correct |
| `INT-R9-CL-005` | Every current real case is answer-visible and cannot serve as a sealed holdout. | census table; report §2.4 | inspect all 13 manifests for expected IDs, labels, votes, and answer-bearing metadata | all 13 expose `expected_claim_ids`, adjudication `label`, and `reviewer_votes`; many expose non-null gold cards | verified | `INT-R9-A-006`; sealed-holdout denominator is zero |
| `INT-R9-CL-006` | Every real manifest has a non-null gold card. | census row wording; report §2.4 prose | inspect every adjudication object's `gold_card` value | EU, India, and Pakistan semantic-pass rows have `gold_card: null`; housing also has a null semantic-pass row | contradicted as universal/non-null claim | `INT-R9-A-004`, `INT-R9-J-003`; labels/votes still establish exposure |
| `INT-R9-CL-007` | Thirteen adjudication anchors `:1-170` are exact. | census table | query line 170 for every cited real manifest | line 170 is absent in all thirteen | contradicted as anchor claim | `INT-R9-A-001`; re-anchor exact ranges |
| `INT-R9-CL-008` | Constitution `:404-430` supports “ua only integrated; 12 per-slice; 0/13; D3.8 unbuilt.” | census rows; report §2.2 | fetch exact cited range, then locate sentence | `:404-430` begins in Forward Direction; facts are at `:382-398` | misanchored | `INT-R9-A-002`; repeated load-bearing range is wrong |
| `INT-R9-CL-009` | ua-msme is the only full composed-loop case. | report executive, §2.2, census | inspect constitution current-state block | `universal-policy-design-system-vision-and-organizing-rules.md:382-398` says exactly one integrated case, ua-msme | verified | supports ua exclusion |
| `INT-R9-CL-010` | Other twelve cases have per-slice classification but no integrated loop. | report §2.2; census C2 rows | inspect same current-state block | same `:382-398` statement | verified, but cited at wrong range | `INT-R9-A-002` |
| `INT-R9-CL-011` | Proving ground is 0/13, useful rate 0, B shadow, D3.8 unbuilt. | report §2.2; prompt orientation | inspect constitution current-state block | same `:382-398` states all four | verified, but cited at wrong range | current readiness correctly blocked |
| `INT-R9-CL-012` | ua-msme appears in universality-development evidence. | report executive, §2.6; census | inspect S14 manifest development refs | `layer2_s14_universality_assurance_manifest.json:170-255` names ua in S12, S13, certified delta | verified | `INT-R9-E-001` |
| `INT-R9-CL-013` | Boston, EU, and Netherlands also appear in S14 development evidence. | census case rows | inspect same S14 ranges | Boston in S12 expansion, EU in S13 revision, Netherlands in certified delta | verified | raises those cases above purely untouched public prose, but not integrated depth |
| `INT-R9-CL-014` | N9 input has a ua-msme governed-promotion default. | executive, §2.2, census | inspect exact input model | `promotion_sequence.py:130-180` sets `g4_governed_promotion_ref` to ua-msme string | verified | supports contaminated-default conclusion |
| `INT-R9-CL-015` | ua-msme must be excluded from decisive primary and adjacent roles. | executive, §2.6, §4.7 | combine CL-009, CL-012, CL-014 and public answer exposure | years of integrated case-conditioned development plus visible answer and default | verified as governance disposition | `INT-R9-E-001` commendation |
| `INT-R9-CL-016` | A fresh secret label could cleanse ua-msme. | census reopening paragraph | causal/provenance analysis against prior exposure | no; secrecy cannot reverse already-seen case and implementation history | contradicted, and report itself rejects it | preserve current exclusion; `INT-R9-E-003` |
| `INT-R9-CL-017` | Current reviewer IDs are accountable independent humans. | supplied orientation rejected by report | inspect all reviewer topology records | identifiers are role-shaped strings; no natural-person identity/signature/accountability record | contradicted | current independent adjudication unmet |
| `INT-R9-CL-018` | All 15 manifests have `calibration_round_id: null`. | supplied orientation | enumerate all 15 topology records | four deep-pilot manifests are non-null; eleven are null | contradicted | `INT-R9-J-001` |
| `INT-R9-CL-019` | Exactly three manifests carry `deep-pilot-round-1`. | census §5; report §2.5 | enumerate all 15 records | housing synthetic plus Berlin, Boston, EU = four | contradicted | `INT-R9-A-003`, `INT-R9-J-001` |
| `INT-R9-CL-020` | All 15 manifests have `topology_mode` in exactly two values. | orientation audit | enumerate field values | exact set `{deep_pilot_overlap, partial_disjoint}` | verified | four/eleven split recorded in orientation ledger |
| `INT-R9-CL-021` | All manifests have `authority_level: research`. | supplied orientation | enumerate all 15 top-level values | exact counts: production 5, governed 6, research 4 | contradicted | `INT-R9-J-002` |
| `INT-R9-CL-022` | All reviewer conflict entries use `none_declared`. | report current baseline | inspect every reviewer record | no contrary value found across 15 manifests | verified | still self-declaration, not independent proof |
| `INT-R9-CL-023` | Existing reviewer topology can be used for public calibration but not decisive independence. | §2.5, §4.9 | compare metadata standing with named-human rule | role IDs and public answers are useful development material but cannot sign an irreversible first decision | verified | `INT-R9-F-001` |
| `INT-R9-CL-024` | Live registry has two Basel-square schedule profiles. | §2.2; orientation | inspect entire TOML | `default_basel_square` and `half_mass_basel_square`, both `basel_square_v1` | verified | orientation correct |
| `INT-R9-CL-025` | Proof-profile kernel distribution is 2 ineligible, 1 theorem-unavailable, 1 deterministic-owner, 1 closed e-process. | §2.2; orientation | enumerate `[[proof_profiles]]` | exact distribution in 232-line registry | verified | no positive-existence inference |
| `INT-R9-CL-026` | Registry's `delta` and schedule automatically control family-wise risk over INT-R9's three cases. | §3.6, §4.6, YAML accounting | trace N9 scope derivation, ledger scope identity, event loading, ordinal assignment, and spend sum | canonical scope is one design problem; events and spend are loaded per scope | unsupported | `INT-R9-D-001`, `INT-R9-C-001`; blocking |
| `INT-R9-CL-027` | Canonical N9 risk scope is one scope for an arbitrary three-case queue. | implicit in “same cumulative ledger scope” | inspect `confidence_risk_scope_for_problem` | `promotion_sequence.py:354-370` names only scope for one problem binding and keys it by `design_problem_id` | contradicted | three distinct cases naturally produce three scopes |
| `INT-R9-CL-028` | Confidence scope identity includes the per-problem owner key. | repository mechanism | inspect `ConfidenceRiskBudgetScope.scope_id` | `confidence_ledger.py:158-195` hashes `owner_scope_key` into scope ID | verified | load-bearing basis of D-001 |
| `INT-R9-CL-029` | Execution ordinal is global across all scopes. | implied by cumulative chronology | inspect `start_check` | ordinals are derived from `_current_checks(events)` returned by the current session/scope | contradicted | a new scope starts at ordinal zero |
| `INT-R9-CL-030` | Spend is summed across all case scopes before a check. | implied by no reset | inspect `prior_spend` in `start_check` | sum uses current-scope events only and compares against registry delta | contradicted | fresh case scope obtains fresh budget |
| `INT-R9-CL-031` | Basel-square formula is implemented and predictable inside a scope. | §3.6 | inspect `_schedule_alpha` and projection hash | `delta * weight * mass * coefficient / (query_index+1)^2` | verified_narrower | strong scope-local mechanism, not sequence composition |
| `INT-R9-CL-032` | Three per-slot guarantees each bounded by delta imply first-positive family-wise risk bounded by delta. | final answer and cumulative-accounting language | logical derivation | absent an allocation/composition theorem, union bound gives at most `3 delta` | contradicted | blocking D-001 |
| `INT-R9-CL-033` | A void/refused slot consumes the next slot's canonical ordinal. | §4.6, YAML | trace next case's scope/event history | next design problem has a distinct scope and no prior events | unsupported | “no refund” is not enforceable by current owner |
| `INT-R9-CL-034` | Three-slot queue and stop-on-first-positive are prospectively fixed. | §4.4-4.6, YAML | inspect order, randomness, no-substitution, stopping fields | explicit and internally consistent | verified as governance requirement | ordering multiplicity is visible rather than hidden |
| `INT-R9-CL-035` | Implementation remains fixed across all three slots. | executive sequence description | inspect between-slot rules | general repairs are permitted; each slot gets a new freeze/revision | contradicted | `INT-R9-C-002`, `INT-R9-D-002` |
| `INT-R9-CL-036` | “General” repair is objectively distinguishable from case-targeted repair before outcomes. | §4.6; YAML between-slots rule | inspect definition, owner, classifier, falsifier | no prospective taxonomy or accountable classification owner is supplied | unsupported | material adaptive loophole |
| `INT-R9-CL-037` | Material dispute automatically blocks promotion. | §4.6, §4.9, state machine | inspect quorum/dispute transitions | explicit no-dispute/no-material-dissent rule | verified as property | commendable direction |
| `INT-R9-CL-038` | Materiality itself has a predeclared accountable owner and checkable decision standard. | required by dispute rule | inspect typed sketches and §10 open questions | only `materiality_rule_ref`/generic assessor; report leaves owner open | blocked | `INT-R9-D-003` |
| `INT-R9-CL-039` | New case pool is independent of implementation outputs. | §4.3-4.4 | inspect role separations | case unit barred from implementation/criteria/threshold/reward | verified_narrower | formal role separation exists |
| `INT-R9-CL-040` | Random selection from six independently authored pairs removes upstream tractability selection. | §4.4 implication | adversarial pool-construction analysis | same unit can design the whole pool and answer packages around familiar mechanisms | contradicted as strong claim; report partly disclaims | `INT-R9-E-002` |
| `INT-R9-CL-041` | A synthetic reviewer or role identifier can satisfy decisive adjudication. | potential baseline shortcut | inspect main report and all supporting files | uniformly forbidden | contradicted by protocol, correctly | `INT-R9-F-001` commendation |
| `INT-R9-CL-042` | Named human panel is presently satisfiable from repository evidence. | readiness question | search inspected branch/baseline for named people/signatures | no such panel evidence exists | blocked and honestly reported | current execution readiness correctly blocked |
| `INT-R9-CL-043` | Seven independence dimensions are all externally verified. | §4.9 | map each dimension to required evidence | many are disclosures; no corroboration rule for all dimensions | unsupported as full construction | `INT-R9-F-002` |
| `INT-R9-CL-044` | Positive-seeking insider cannot comply with every rule and retain favorable influence. | §5.2 | construct friendly-panel/favorable-pool/adaptive-repair adversary | actor can comply via pool design, friendly non-conflicted panel, and generalized post-failure repair | contradicted as absolute; residual is partly disclosed | material, not a covert-fraud-only issue |
| `INT-R9-CL-045` | Blame-avoiding insider cannot strategically refuse every unseen real case. | §4.15/§5.3 | construct precise owner-reasoned refusal path | actor can pass public controls and still refuse all novel cases | contradicted as prevention claim | `INT-R9-G-002` |
| `INT-R9-CL-046` | Section 4.14 names observable useful-rate gaming indicators. | §4.14 | inspect protected decisions and detector list | substitutions, reruns, threshold drift, exclusions, denominator edits, rewards, stopping, repairs are all listed | commendable | `INT-R9-G-001` |
| `INT-R9-CL-047` | Deterministic positive control can enter real promotion numerator. | §4.7, §4.15, YAML | search all five files for contrary route | explicitly barred; no contrary route found | contradicted by protocol, correctly | preserve boundary |
| `INT-R9-CL-048` | Narrative and YAML define the same useful-rate denominator. | §4.14 vs YAML | compare exact membership language | prose: slot enters once inspected; YAML: every precommitted slot included | contradicted | `INT-R9-G-003` |
| `INT-R9-CL-049` | INT-R9 builds a second generic oracle-independence framework. | S0-GAP-02 seam | compare ownership lists and mechanism placement | generic commitment/key/access/rotation/challenge mechanics are deferred | contradicted; no substantive duplicate owner found | `INT-R9-H-001` commendation |
| `INT-R9-CL-050` | “Consolidation-approved equivalent” cannot authorize a sibling framework. | §4.3/YAML | adversarial textual reading | word “equivalent” has no supersession/canonicality condition | unsupported | `INT-R9-H-003` |
| `INT-R9-CL-051` | Delivered INT-R1 provides an artifact named `ObligationSetDeclaration`. | §4.3, §4.17, §10.1 | inspect INT-R1 main and support artifacts at `82e136a...` | delivered type is `ObligationCoverageEnvelope`; no declaration with that name found | contradicted | `INT-R9-H-002` |
| `INT-R9-CL-052` | INT-R1 permits arbitrary narrowing of a scored claim when closure is weak. | INT-R9 degradation ladder | compare INT-R1 theorem/lattice mapping | known-incomplete/material unresolved fails closed for affected authority action; scope change requires a new exact declaration/epoch | contradicted as broad rung | consolidation correction required |
| `INT-R9-CL-053` | INT-R1's relative theorem can satisfy INT-R9 in a narrow case. | seam question | compare exact semantic requirements | yes, only `bounded_complete` relative to exact basis/language/cutoff plus visible unknown-world rider and current independent review | verified_narrower | semantic compatibility exists after type/rung correction |
| `INT-R9-CL-054` | Anti-selection record remains meaningful when substantive obligation coverage blocks promotion. | §4.17 | logical separation of custody chronology from owner outcome | prospective chronology can remain historically valid while authority action is NO-GO | verified | `INT-R9-H-003` commendation direction |
| `INT-R9-CL-055` | Workflow states create a second authority lattice. | state-machine documents | inspect standing and mappings | explicitly custody workflow; owner outcome remains canonical | contradicted; no parallel lattice found | `INT-R9-I-002` |
| `INT-R9-CL-056` | YAML is only a loose research sketch. | YAML frontmatter/standing | inspect density and executability | fixed IDs, literals, counts, fields, blockers, transitions, quorum and complete procedure | contradicted in substance | `INT-R9-I-001` |
| `INT-R9-CL-057` | `accepted_narrow_scope` matches the established result. | all artifact frontmatter | propagate D-001 into claim standing | core cumulative guarantee is invalid as written | contradicted | `INT-R9-I-003`; result should be blocked pending research |
| `INT-R9-CL-058` | GY plan requires INT-R9 ratification before candidate inspection. | prompt orientation; report §1.1 | inspect exact Phase-7 note | `GY-engine-subordination.md:2510-2535` states the prerequisite | verified | orientation correct |
| `INT-R9-CL-059` | GY, Atlas, and Wave-2 frontmatter parse as ordinary YAML. | supplied warning | inspect unquoted `revised:` values with embedded colon-rich prose | all three contain unsafe plain scalars; warning correct | contradicted; they do not safely parse | no edit authorized here |
| `INT-R9-CL-060` | P29/P33/P34 are supported by `failure-patterns.md:200-900`. | report §2.2 | fetch exact range and locate rows | definitions occur around `:70-78`, not the cited range | misanchored | `INT-R9-A-005` |
| `INT-R9-CL-061` | Dwork et al. prove a PolicyOS authority claim generalizes from one fresh case. | section 3 transfer risk | inspect source theorem and report caveat | theorem concerns adaptive statistical validity/generalization; report expressly refuses direct transfer | contradicted and correctly rejected | `INT-R9-B-001` |
| `INT-R9-CL-062` | Preregistration alone prevents deviations. | section 3.3 | inspect Claesen et al. and report use | deviations common and often undisclosed; report makes deviations first-class | contradicted and correctly rejected | transfer sound |
| `INT-R9-CL-063` | Pocock/O'Brien-Fleming/Howard supply INT-R9's exact allocation. | section 3.6 | inspect primary sources and report caveat | only aggregate/procedural lesson transfers; no exact PolicyOS allocation imported | contradicted and correctly disclaimed | repository composition still missing |
| `INT-R9-CL-064` | One FDA-style pivotal result legally authorizes PolicyOS. | section 3.7 | inspect FDA drafts and report limits | context-specific, nonbinding drug guidance; report imports corroboration analogy only | contradicted and correctly rejected | transfer sound |
| `INT-R9-CL-065` | Rebuilt benchmarks prove adaptivity caused all score drops. | section 3.8 | inspect Recht et al. | authors note new tests were harder and do not attribute all drop to adaptivity; report preserves caveat | contradicted and correctly rejected | transfer sound |
| `INT-R9-CL-066` | Inter-rater agreement proves adjudicator correctness or independence. | section 3.9 | inspect Cohen/Krippendorff and report use | coefficients diagnose agreement under assumptions; report denies correctness token | contradicted and correctly rejected | transfer sound |
| `INT-R9-CL-067` | A plain unsalted hash hides a predictable answer. | section 3.10 | inspect FIPS plus commitment literature | digest binds/detects change but does not by itself hide low-entropy content | contradicted | report's substantive conclusion correct; attribution should be joint |
| `INT-R9-CL-068` | Negative results receive the same formal publication path as positives. | executive, §4.5, state machine, YAML | trace every terminal | refused, void, disputed, exhausted, no-attempt retained and published | verified as protocol property | important commendation |
| `INT-R9-CL-069` | Current repository can execute the protocol today. | executive/readiness | check fresh cases, S0-GAP-02, named panel, INT-R1 interface, D3.8 | prerequisites absent and multiplicity unresolved | contradicted and honestly reported as blocked | no capability claim |
| `INT-R9-CL-070` | Protocol proves no secret collusion or fabricated records occurred. | §4.1-4.2 | inspect stated residual limits | expressly denied | contradicted and correctly bounded | preserve claim limit |

## Blocking dependency chain

```text
three-slot stop-on-first-positive
  -> selection event is union over three opportunities
  -> each new case is a distinct N9 design_problem binding
  -> canonical scope_id includes design-problem owner_scope_key
  -> ledger ordinal and prior_spend are scope-local
  -> each slot can begin at ordinal 0 with fresh delta
  -> no INT-R9 parent allocation/composition theorem exists
  -> P(any false positive in selected first-positive sequence) <= delta is not established
  -> section 4.2 claim and accepted_narrow_scope standing fail
  -> NO_GO
```

## Ledger conclusion

The evidence supports the research direction but not the ratifiable protocol. The verified
commendations are separable from the blocking defect and should be preserved. The first item for
re-research is the exact relationship between one finite first-positive sequence and the canonical
confidence ledger's per-design-problem scopes. No subsequent prose, panel rule, holdout custody,
or negative-result publication mechanism closes that arithmetic gap.
