---
title: "Wave 5 consolidation — disposition ledger"
status: candidate
stage: consolidation
base: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
---

# Wave 5 Disposition Ledger

## Counting contract

The controlling denominator is **Markdown finding-register table rows**, not ID occurrences,
severity-word occurrences, amendment paragraphs or verifier remarks. The audit-file population is five
`.md` files, one per package. The response cross-check population is six `.md` amendment ledgers
because the combined package has separate INT and OPS ledgers.

| Task | Audit table path at audit head | Audit rows | Blocking | Material | Minor | Commendation | Terminal `closed_or_preserved` | Terminal `carry_and_route` |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| INT-R2 | `audits/int-r2/int-r2-independent-audit.md` @ `dbdb1243…` | 16 | 0 | 9 | 3 | 4 | 13 | 3 |
| INT-R3 | `audits/int-r3/int-r3-independent-audit.md` @ `8e9be1e5…` | 23 | 0 | 13 | 5 | 5 | 19 | 4 |
| INT-R4 ‖ OPS-R5 | `audits/int-r4-ops-r5/int-r4-ops-r5-independent-audit.md` @ `ea2eac55…` | 18 | 0 | 9 | 2 | 7 | 11 | 7 |
| INT-R5 | `audits/int-r5/int-r5-independent-audit.md` @ `247f89f0…` | 18 | 0 | 7 | 2 | 9 | 17 | 1 |
| INT-R6 | `audits/int-r6/int-r6-independent-audit.md` @ `bae4f8c2…` | 14 | 1 | 6 | 3 | 4 | 14 | 0 |
| **Wave** | **5 Markdown audit tables** | **89** | **1** | **44** | **15** | **29** | **74** | **15** |

Reconciliation:

```text
severity:     1 + 44 + 15 + 29 = 89
disposition: 74 + 15           = 89
```

“Closed” below means the terminal verifier found the audit row satisfied, preserved or remediated. It
does not mean a capability exists. “Carry” means the audit closure condition remains incomplete and
the item must appear in the routing map.

## INT-R2 — 16 rows

Sources for every row in this section: audit line `dbdb1243a277f0864cae9af240ff1d13786d99df`;
response line `0afc3779e2894f2793cc40150d6923589bd36ee6`; verifier line
`b48cdb131c2a8d4f9b30ce217dfa3efcd65119fa`.

| Task | Finding ID | Severity | What the audit found | What the response did | What the verifier concluded | Disposition |
|---|---|---|---|---|---|---|
| INT-R2 | INT-R2-AUD-F001 | material | F01–F40 was a list, not a mechanically complete register. | Added kind, standing, evidence, transfer, holder, consequence and non-effect columns. | satisfied | closed_or_preserved |
| INT-R2 | INT-R2-AUD-F002 | material | Six standing cells mixed tokens with prose. | Normalized all six and moved qualifiers to typed columns. | satisfied | closed_or_preserved |
| INT-R2 | INT-R2-AUD-F003 | material | F01 cited the wrong owner/lines. | Removed the false coordinate and cited the canonical refusal owner. | satisfied | closed_or_preserved |
| INT-R2 | INT-R2-AUD-F004 | material | Four repository-wide absence claims rested on samples. | Retained local positives and downgraded unwalked zeroes to `not_established`. | satisfied | closed_or_preserved |
| INT-R2 | INT-R2-AUD-F005 | material | `GapShapeAssessment` recorded a result but did not construct its predicate. | Added eight minimal positives, sibling falsifiers, P37 labels and residual templates. | satisfied at research-contract level | closed_or_preserved |
| INT-R2 | INT-R2-AUD-F006 | material | Many S01–S22 sources lacked durable state/passage replay. | Repaired S04/S13/S14 and retained the transfer ledger. | partially satisfied; several mutable/under-located rows remain | carry_and_route |
| INT-R2 | INT-R2-AUD-F007 | material | Common-ceiling scope relations lacked field semantics and owners. | Added a 12-dimension relation/checkability matrix and fail-closed unknowns. | partially satisfied; vocabulary-owner field remains absent | carry_and_route |
| INT-R2 | INT-R2-AUD-F008 | material | `0/63` was a family specification, not an executable semantic benchmark. | Registered future manifest, oracle and mutant requirements without claiming execution. | correctly carried open; `semantic_test_missing` | carry_and_route |
| INT-R2 | INT-R2-AUD-F009 | material | Several `deeper_terminal` pairs needed an unconstructed no-source proof. | Bounded open-world negatives to a content-bound envelope or route exhaustion at an epoch. | satisfied | closed_or_preserved |
| INT-R2 | INT-R2-AUD-F010 | minor | `owner_writability` hid substantive and technical obligations. | Kept one discriminator with two separately stateful conjuncts. | satisfied | closed_or_preserved |
| INT-R2 | INT-R2-AUD-F011 | minor | HD and IA lacked explicit non-substitution. | Added external-HD≠IA and favourable-IA≠decision invariants. | satisfied | closed_or_preserved |
| INT-R2 | INT-R2-AUD-F012 | minor | The consumer row had no resolvable holder evidence. | Marked it `institutionally_supplied` with explicit non-effect. | satisfied | closed_or_preserved |
| INT-R2 | INT-R2-AUD-C001 | commendation | Holder-aware set-level measurement was strong. | Preserved proposition, denominator, holder and consequence. | preserved as required | closed_or_preserved |
| INT-R2 | INT-R2-AUD-C002 | commendation | The package refused an architect-supplied zero. | Preserved `not_established`; minted no zero. | preserved as required | closed_or_preserved |
| INT-R2 | INT-R2-AUD-C003 | commendation | Eight types were genuinely discriminated across 28 pairs. | Preserved the union and added only authorized refinements. | preserved as required | closed_or_preserved |
| INT-R2 | INT-R2-AUD-C004 | commendation | The source ledger bound transfer and non-effect. | Preserved all 22 rows while repairing selected locators. | preserved as required | closed_or_preserved |

Arithmetic: `13 closed_or_preserved + 3 carry_and_route = 16`.

## INT-R3 — 23 rows

Sources for every row in this section: audit line `8e9be1e5e737312f92579b57a7f011b9b14d3a46`;
response line `32cfebd02354b4d70fbf8beaca168aea6f2e72ee`; verifier line
`81635e8878ec99dd6d9e06fc7c53fb6f13ade434`.

| Task | Finding ID | Severity | What the audit found | What the response did | What the verifier concluded | Disposition |
|---|---|---|---|---|---|---|
| INT-R3 | INT-R3-AUD-F001 | material | Baseline used nonexistent/inaccurate TrustPosture and time anchors. | Added corrected effective baseline while retaining history. | satisfied with gap: false assertions remain in unchanged authoritative siblings (G1) | carry_and_route |
| INT-R3 | INT-R3-AUD-F002 | material | Repository-wide human-evidence/contract zeroes came from named-path search. | Added bounded walks and downgraded unsupported zeroes. | satisfied with gap: propagated false assertions remain (G1) | carry_and_route |
| INT-R3 | INT-R3-AUD-F003 | material | Sixteen EXT rows lacked branch-replayable source locators. | Added survey hashes/windows and a stable ledger. | satisfied with gap: five rows still require uncommitted survey content (G2) | carry_and_route |
| INT-R3 | INT-R3-AUD-F004 | material | Two transfer rules lacked target-workflow bridges. | Constructed time-pressure and weakest-link bridges and narrowed transfer. | satisfied | closed_or_preserved |
| INT-R3 | INT-R3-AUD-F005 | material | Four novel constructs lacked resolving evidence/population/endpoint detail. | Added construct-specific resolution requirements. | satisfied | closed_or_preserved |
| INT-R3 | INT-R3-AUD-F006 | material | Exclusions could absorb 100% of a hard stratum. | Added nonnumeric fail-closed coverage and preregistered targets. | satisfied | closed_or_preserved |
| INT-R3 | INT-R3-AUD-F007 | material | Programme feasibility had no recruitment, ethics, accessibility or precision plan. | Added a bounded feasibility/stop contract without claiming execution. | satisfied | closed_or_preserved |
| INT-R3 | INT-R3-AUD-F008 | material | One stale-state red rejected valid identical affordance cases. | Narrowed it to currentness-dispositive conditions and added controls. | satisfied | closed_or_preserved |
| INT-R3 | INT-R3-AUD-F009 | minor | Twelve reds conflated four property classes; ten could pass without a human. | Partitioned 6/3/3/0 and prohibited a comprehension claim. | satisfied | closed_or_preserved |
| INT-R3 | INT-R3-AUD-F010 | material | `NO_GO` token was attached to local comprehension rather than first-public predicate. | Separated global gate standing from local claim-use restriction. | satisfied | closed_or_preserved |
| INT-R3 | INT-R3-AUD-F011 | minor | Blocker selection could be post-terminal. | Split primary pre-terminal/constitutive evidence from diagnostic post-hoc evidence. | satisfied | closed_or_preserved |
| INT-R3 | INT-R3-AUD-F012 | material | Package called ownership missing while Atlas named stale DS6 ownership. | Classified DS6 allocation stale, current state unowned, route to principal. | satisfied; no appointment made | closed_or_preserved |
| INT-R3 | INT-R3-AUD-C001 | commendation | No human result/literature substitution was explicit. | Preserved. | satisfied | closed_or_preserved |
| INT-R3 | INT-R3-AUD-C002 | commendation | Eligible opportunities, attempt/commit and direct wrong cells were precise. | Preserved. | satisfied | closed_or_preserved |
| INT-R3 | INT-R3-AUD-C003 | commendation | Accessible relation parity and real AT users were core. | Preserved. | satisfied | closed_or_preserved |
| INT-R3 | INT-R3-AUD-C004 | commendation | Set-valued truth and disagreement avoided authority laundering. | Preserved. | satisfied | closed_or_preserved |
| INT-R3 | INT-R3-AUD-C005 | commendation | Source rates and theory disagreement were not flattened. | Preserved. | satisfied | closed_or_preserved |
| INT-R3 | INT-R3-AUD-O01 | material | Audit branch started from pre-research base, violating §2. | Amendment joined research and audit histories. | satisfied at terminal topology | closed_or_preserved |
| INT-R3 | INT-R3-AUD-O02 | minor | Prompt said F001–F010/seven of ten; branch had F001–F018/seven of eighteen. | Used the 18-row denominator and separated literal occurrences. | satisfied | closed_or_preserved |
| INT-R3 | INT-R3-AUD-O03 | minor | Prompt called the task both Wave 5 and Wave 8. | Identified it as Wave 5 and removed dependency on the contradiction. | satisfied | closed_or_preserved |
| INT-R3 | INT-R3-AUD-O04 | material | Prompt presented planned targets as current glass. | Separated current, partial and planned/in-flight targets. | satisfied | closed_or_preserved |
| INT-R3 | INT-R3-AUD-O05 | material | Prompt supplied `20/24` and a repository zero without a walk. | Kept `20/24` institutionally supplied and downgraded the zero. | satisfied with shared G1 artifact gap | carry_and_route |
| INT-R3 | INT-R3-AUD-O06 | minor | “Benchmark closes it” ambiguously followed unrelated DS11 debts. | Limited closure to behavioral comprehension. | satisfied | closed_or_preserved |

Arithmetic: `19 closed_or_preserved + 4 carry_and_route = 23`.

## INT-R4 ‖ OPS-R5 — 18 rows

Sources for every row in this section: audit line `ea2eac5575e5b8fb4a5462c068a37bb913076952`;
response line `329edb60f77867f914581d380acfccf5882d607d`; verifier line
`082ddc26c2f8db55104ccb95518b72d84d94a06b`.

| Task | Finding ID | Severity | What the audit found | What the response did | What the verifier concluded | Disposition |
|---|---|---|---|---|---|---|
| INT-R4 ‖ OPS-R5 | AUD-F01 | material | Absorbed OPS-R7 questions were covered but not discharged. | Added a seven-row estimand/admission/failure/residue matrix. | partially closed; question fixtures absent, CT-01 fails | carry_and_route |
| INT-R4 ‖ OPS-R5 | AUD-F02 | material | OPS-R6 operations were grouped without distinct semantics. | Added operation-level transition charters. | partially closed; operation fixtures absent, CT-01 fails | carry_and_route |
| INT-R4 ‖ OPS-R5 | AUD-F03 | material | `diagnosis_unresolved` had no absorption/risk–coverage bound. | Specified holdouts, metrics, baselines and anti-degeneracy design. | partially closed; holdout/oracle/evaluator/results absent | carry_and_route |
| INT-R4 ‖ OPS-R5 | AUD-F04 | material | Admission order was presented as causal precedence. | Recast it as peer substantive gates and mandatory contributor lanes. | closed at research-contract level; CT-04 passes | closed_or_preserved |
| INT-R4 ‖ OPS-R5 | AUD-F05 | material | `expected_variation` contradicted written GY-O1. | Imposed interim no-mutation rule and routed an eight-condition request. | partially closed; sibling report still contradicts rule; token invalid; CT-02 fails | carry_and_route |
| INT-R4 ‖ OPS-R5 | AUD-F06 | material | E/X/V/C were factored but not orthogonal. | Defined constrained invariants, forbidden tuples and transitions. | partially closed; state engine and mutations absent | carry_and_route |
| INT-R4 ‖ OPS-R5 | AUD-F07 | material | 24-case diagnosis “corpus” had no packets/oracles/consumer tests. | Registered packet/oracle/mutation requirements. | not closed; zero executable artifacts | carry_and_route |
| INT-R4 ‖ OPS-R5 | AUD-F08 | material | 20-scenario response “corpus” had no packets/oracles/evaluator. | Registered response packet and proxy-pair requirements. | not closed; zero executable artifacts | carry_and_route |
| INT-R4 ‖ OPS-R5 | AUD-F09 | material | Prose sketches were mislabeled `contract_only`. | Changed ten cells to `absent/unallocated`; separated description. | closed; CT-09 passes across 36 cells | closed_or_preserved |
| INT-R4 ‖ OPS-R5 | AUD-F10 | minor | “One vocabulary or fork” overclaimed representation monopoly. | Required one governed semantics or total tested crosswalk. | closed as semantic rule; CT-10 artifact still absent | closed_or_preserved |
| INT-R4 ‖ OPS-R5 | AUD-F11 | minor | Registers lacked evidence/transfer/falsifier links. | Added direct evidence, transfer and resolution columns. | closed; sample trace succeeds | closed_or_preserved |
| INT-R4 ‖ OPS-R5 | AUD-F12 | commendation | Package correctly refuted “only greenfield.” | Preserved S13 producer/validator distinction. | closed | closed_or_preserved |
| INT-R4 ‖ OPS-R5 | AUD-F13 | commendation | Package kept repository zero `not_established`. | Preserved. | closed | closed_or_preserved |
| INT-R4 ‖ OPS-R5 | AUD-F14 | commendation | Missing terminal receipt was not fabricated. | Preserved channel labels. | closed | closed_or_preserved |
| INT-R4 ‖ OPS-R5 | AUD-F15 | commendation | Universal linear adaptation ladder was correctly refuted. | Preserved negative. | closed | closed_or_preserved |
| INT-R4 ‖ OPS-R5 | AUD-F16 | commendation | External blockers named real unblockers. | Preserved absent signer/preauthorization. | closed | closed_or_preserved |
| INT-R4 ‖ OPS-R5 | AUD-F17 | commendation | Reuse-first owner boundaries were precise. | Preserved. | closed | closed_or_preserved |
| INT-R4 ‖ OPS-R5 | AUD-F18 | commendation | Protection/learning and source/destination were separated. | Preserved. | closed | closed_or_preserved |

Arithmetic: `11 closed_or_preserved + 7 carry_and_route = 18`.

## INT-R5 — 18 rows

Sources for every row in this section: audit line `247f89f016f71ee603ed76ef6dbb6403f7e651a0`;
response line `70f2db6d3a4330664c981721a9305f16bffe369b`; verifier line
`d9223d12bf7cb4826c6f1f888d84275364c35fe7`.

| Task | Finding ID | Severity | What the audit found | What the response did | What the verifier concluded | Disposition |
|---|---|---|---|---|---|---|
| INT-R5 | INT-R5-A-001 | material | “Theorem” used a false universal inequality. | Replaced it with two-history non-inferability and allowed equality. | closed | closed_or_preserved |
| INT-R5 | INT-R5-A-002 | material | DS20+PA2+DS9 acquisition composition was not live. | Reclassified route as DS20-only and named absent bridge/consumer. | closed | closed_or_preserved |
| INT-R5 | INT-R5-A-003 | material | Ten-file slice was not a complete executable/authority closure. | Narrowed it to selected slice and withdrew repository zeroes. | audit row closed; stricter complete-denominator lift remains unmet | closed_or_preserved |
| INT-R5 | INT-R5-A-004 | material | Decisive time/effect/profile fields lacked independent producers. | Named producer/verifier/requester controls and fail-closed mutations. | closed at research-contract level | closed_or_preserved |
| INT-R5 | INT-R5-A-005 | material | External evidence was not branch-replayable. | Added five source identities, hashes, denominators and paraphrased extracts. | partially closed; private IDs and passage gaps remain (V-001) | carry_and_route |
| INT-R5 | INT-R5-A-006 | material | Bare candidate codes duplicated live semantics. | Added candidate namespace/version and non-widening sibling mapping. | closed | closed_or_preserved |
| INT-R5 | INT-R5-A-007 | material | PAO-R4 was a restriction, not an executable conjunct. | Added conditional conjunct and two-direction non-substitution. | closed | closed_or_preserved |
| INT-R5 | INT-R5-A-008 | minor | Cure lacked explicit relation-back effect coordinate. | Added prospective/relation-back/saved-act/limited/unresolved results. | closed | closed_or_preserved |
| INT-R5 | INT-R5-A-009 | minor | Two closure violations and a feed drift were counted as three closures. | Separated the predicates and counts. | closed | closed_or_preserved |
| INT-R5 | INT-R5-A-C01 | commendation | Delivery/evidence provenance was honest. | Preserved bounded branch text. | closed; conversational errors graded separately | closed_or_preserved |
| INT-R5 | INT-R5-A-C02 | commendation | Measurement holder and no-index-zero rule were explicit. | Preserved. | closed | closed_or_preserved |
| INT-R5 | INT-R5-A-C03 | commendation | 34/34 parity and historical 33 drift were separated. | Preserved. | closed | closed_or_preserved |
| INT-R5 | INT-R5-A-C04 | commendation | Conflict detectability was honestly bounded. | Preserved. | closed | closed_or_preserved |
| INT-R5 | INT-R5-A-C05 | commendation | Collegial validity was profile-relative. | Preserved. | closed | closed_or_preserved |
| INT-R5 | INT-R5-A-C06 | commendation | Fixtures were red-first in shape. | Preserved after reason-code repair. | closed | closed_or_preserved |
| INT-R5 | INT-R5-A-C07 | commendation | Missing holder remained typed without borrowed authority. | Preserved. | closed | closed_or_preserved |
| INT-R5 | INT-R5-A-C08 | commendation | PAO-R4 anti-role boundary was preserved. | Preserved while adding conjunct. | closed | closed_or_preserved |
| INT-R5 | INT-R5-A-C09 | commendation | Replay stayed immutable; no fictional rollback. | Preserved while adding legal-effect projection. | closed | closed_or_preserved |

Arithmetic: `17 closed_or_preserved + 1 carry_and_route = 18`.

## INT-R6 — 14 rows

Sources for every row in this section: audit line `bae4f8c2b5e5ef340dda73f17bfe852c1d0d3cee`;
initial response `8137aa31a4bf5e06c6b1abd4e20458295fd5a506`; initial verifier
`1accee3534befa8ce9bc656a1b35f8eaca7e9b74`; terminal response
`eb9b135089d4a54b648973db02f0312b276ea2ea`; terminal verifier
`24b6813d11e87a30e849bf4a799293e682bd7fed`.

| Task | Finding ID | Severity | What the audit found | What the response did | What the verifier concluded | Disposition |
|---|---|---|---|---|---|---|
| INT-R6 | IR6-A01 | blocking | Two live standing blocks contained non-members. | Delegated all standing to one registered tuple. | closed and held through remediation | closed_or_preserved |
| INT-R6 | IR6-A02 | material | Repair deleted measured predecessor baseline. | Initial grouped recovery missed 2/19; remediation mapped all 19 to 16 rows. | closed by delta verification | closed_or_preserved |
| INT-R6 | IR6-A03 | material | Phase-0 wording exceeded `absent/unallocated`. | Recast present capability claims as target/research model. | closed and held | closed_or_preserved |
| INT-R6 | IR6-A04 | material | No current executable catalogue census existed. | Initial harness could not run; remediation withdrew execution/independence claims and retained supplied figures as non-zero-settling. | audit defect closed by honest withdrawal; independent census remains a lift gap | closed_or_preserved |
| INT-R6 | IR6-A05 | material | Thirty routes named lanes, not accountable holders. | Initial response left two artifact owners; remediation produced 27 unallocated/3 existing-owner-only/0 artifact-owner split. | closed by delta verification | closed_or_preserved |
| INT-R6 | IR6-A06 | material | Unestablished mechanisms were “works now” premises. | Separated repository fact, architecture demonstration and future behavior. | closed and held | closed_or_preserved |
| INT-R6 | IR6-A07 | material | Finite falsifiers were promoted to positive equivalence proof. | Bounded certificate to tested population, purpose, residual and invalidators. | closed and held | closed_or_preserved |
| INT-R6 | IR6-A08 | minor | “Orthogonal” overstated independence. | Used dimensions/layers with dependency edges. | closed and held | closed_or_preserved |
| INT-R6 | IR6-A09 | minor | Wrong SCC item and coarse source anchors. | Corrected to item 2117 and durable paragraph/article/section spans. | closed and held | closed_or_preserved |
| INT-R6 | IR6-A10 | minor | Headings-only scaffold lacked entrypoint/disposition. | Declared navigation/history role and accounted for all eight original files. | closed and held | closed_or_preserved |
| INT-R6 | IR6-C01 | commendation | D4-A1 UI/source separation survived. | Preserved. | closed and held | closed_or_preserved |
| INT-R6 | IR6-C02 | commendation | Falsifiers discriminated beyond parity. | Preserved. | closed and held | closed_or_preserved |
| INT-R6 | IR6-C03 | commendation | Co-authentic/no-mandatory-English model survived. | Preserved. | closed and held | closed_or_preserved |
| INT-R6 | IR6-C04 | commendation | Role/appointment/decision separation represented zero holders. | Preserved without capability claim. | closed and held | closed_or_preserved |

Arithmetic: `14 closed_or_preserved + 0 carry_and_route = 14`. The independent current census is a
terminal lift gap, not an unclosed audit row, and is routed separately.

## Amendment disposition vocabulary

The raw response-line tokens, counted by amendment-ledger table row, are:

| Task | Raw row-token arithmetic | §3.3 mapping used for Wave-5 reconciliation | Mapping provenance |
|---|---|---|---|
| INT-R2 | `11 accepted_corrected + 1 accepted_residual_registered + 4 preserved = 16` | `13 accepted + 3 accepted_with_variation + 0 declined = 16` | published by verifier `b48cdb13…`; variations F006/F007/F008 |
| INT-R3 | `18 accepted + 5 accepted_with_variation + 0 declined = 23` | unchanged | response and verifier conform |
| INT-R4 ‖ OPS-R5 | `14 accepted + 3 accepted_with_variation + 1 routed_pending_principal = 18` | `14 accepted + 4 accepted_with_variation + 0 declined = 18` | **consolidator normalization**, not verifier mapping: F05 accepts the defect/interim rule but closure and principal decision remain incomplete |
| INT-R5 | `16 accepted + 2 accepted_with_variation + 0 declined = 18` | unchanged | response and verifier conform |
| INT-R6 | `13 accepted + 1 accepted_with_variation + 0 declined = 14` | unchanged | response and verifier conform |
| **Wave** | raw values span seven tokens | `74 accepted + 15 accepted_with_variation + 0 declined = 89` | normalized row denominator |

The combined verifier explicitly calls `routed_pending_principal` a §3.3 deviation and does **not**
publish a mapping. That contradicts the brief's implication that both affected verifiers did so and is
recorded in the orientation audit. The normalization above makes no principal ruling; it says only
that an accepted response with incomplete closure is `accepted_with_variation` in the closed
vocabulary. The numerical `74/15` match with terminal closed/carry arithmetic is coincidental:
amendment disposition and verification closure are different axes, and several
`accepted_with_variation` rows are terminally closed.

## Supplemental verifier findings and gaps

These are not inserted into the 89-row audit denominator. They are separately enumerated because they
must be routed.

| Task | Verifier ID/heading | Result at terminal line | Relation to audit denominator | Route status |
|---|---|---|---|---|
| INT-R3 | G1 | false assertions remain in unchanged authoritative siblings | refinement shared by F001/F002/O05 | carry |
| INT-R3 | G2 | five EXT rows still depend on uncommitted surveys | refinement of F003 | carry |
| INT-R4 ‖ OPS-R5 | Internal Consistency Finding | report and ledger give opposite GY-O1 answers | survival of F05 | carry |
| INT-R5 | INT-R5-V-001 | content identity verified privately but branch replay incomplete | refinement of A005 | carry |
| INT-R6 | V-R6-01 | 17/19 predecessor recovery | refinement of A02 | closed by remediation/delta |
| INT-R6 | V-R6-02 | published harness cannot run; parser not independent | refinement of A04 | closed by withdrawal in remediation/delta |
| INT-R6 | V-R6-03 | 2/30 rows use artifact as owner | refinement of A05 | closed by remediation/delta |

Arithmetic: `7 verifier refinements = 4 carried + 3 closed`. This count is distinct from both the 89
audit rows and the 70 explicit response-line open questions.

## Reproducible row-census command

This is the exact shape executed from repository root. It parses Markdown rows, validates one severity
per matched row and rejects duplicate IDs:

```bash
python3 - <<'PY'
import re, subprocess
specs = {
  'INT-R2': ('dbdb1243a277f0864cae9af240ff1d13786d99df', 'policy-engine/docs/research/policy-operations/audits/int-r2/int-r2-independent-audit.md', r'INT-R2-AUD-(?:F|C)\d{3}'),
  'INT-R3': ('8e9be1e5e737312f92579b57a7f011b9b14d3a46', 'policy-engine/docs/research/policy-operations/audits/int-r3/int-r3-independent-audit.md', r'INT-R3-AUD-(?:F|C|O)\d{2,3}'),
  'INT-R4||OPS-R5': ('ea2eac5575e5b8fb4a5462c068a37bb913076952', 'policy-engine/docs/research/policy-operations/audits/int-r4-ops-r5/int-r4-ops-r5-independent-audit.md', r'AUD-F\d{2}'),
  'INT-R5': ('247f89f016f71ee603ed76ef6dbb6403f7e651a0', 'policy-engine/docs/research/policy-operations/audits/int-r5/int-r5-independent-audit.md', r'INT-R5-A-(?:\d{3}|C\d{2})'),
  'INT-R6': ('bae4f8c2b5e5ef340dda73f17bfe852c1d0d3cee', 'policy-engine/docs/research/policy-operations/audits/int-r6/int-r6-independent-audit.md', r'IR6-(?:A|C)\d{2}'),
}
wave = {k: 0 for k in ('blocking','material','minor','commendation')}
for task,(sha,path,id_re) in specs.items():
    body = subprocess.check_output(['git','show',f'{sha}:{path}'], text=True)
    rows = []
    for lineno,line in enumerate(body.splitlines(),1):
        if not line.startswith('|'): continue
        cells = [c.strip().strip('`').strip('*') for c in line.strip().strip('|').split('|')]
        if cells and re.fullmatch(id_re,cells[0]):
            severity = cells[1].lower().strip('`').strip('*')
            assert severity in wave
            rows.append((cells[0],severity,lineno)); wave[severity] += 1
    assert len(rows) == len({r[0] for r in rows})
    print(task, len(rows), {s: sum(r[1] == s for r in rows) for s in wave})
print('WAVE', sum(wave.values()), wave)
PY
```

Observed output:

```text
INT-R2 16 {'blocking': 0, 'material': 9, 'minor': 3, 'commendation': 4}
INT-R3 23 {'blocking': 0, 'material': 13, 'minor': 5, 'commendation': 5}
INT-R4||OPS-R5 18 {'blocking': 0, 'material': 9, 'minor': 2, 'commendation': 7}
INT-R5 18 {'blocking': 0, 'material': 7, 'minor': 2, 'commendation': 9}
INT-R6 14 {'blocking': 1, 'material': 6, 'minor': 3, 'commendation': 4}
WAVE 89 {'blocking': 1, 'material': 44, 'minor': 15, 'commendation': 29}
```

The independent cross-check parsed response-ledger table rows at the terminal response heads: one
ledger each for INT-R2, INT-R3, INT-R5 and INT-R6, two for INT-R4 ‖ OPS-R5. It returned respectively
`16/16`, `23/23`, `18/18`, `18/18`, `14/14` row occurrences/unique IDs, with no duplicate ID. Thus
both the audit-table walk and the independent response-table walk reconcile to 89.
