---
title: INT-R9 — Amendment Conformance Verification
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
architect_correction_commit: 01a9ec884a4a3193ebdea7d8431542ac55c47cda
inspection_date: 2026-08-03
authoritative_for:
  - bounded conformance determination for the INT-R9 amendment against R1 through R14 and the audit section-8 rules
  - independent determination that Option B is implemented as a nonnumeric adaptive anti-selection and custody protocol
  - identification of residual provenance and preservation gaps that consolidation must carry
  - independent reproduction of the fifteen-manifest R13 set-level facts and the R11 YAML-null result
may_not_use_for:
  - production implementation authorization
  - final code, wire, schema, package, database, evaluator, metric, or serialization contract
  - canonical owner appointment
  - authority grant or capability claim
  - benchmark passage
  - a sequence-level numeric false-promotion claim
  - proof that a positive promotion is achievable
  - legal compliance, institutional competence, population validity, or production readiness
  - reopening findings outside the published INT-R9 audit and amendment specification
  - replacement of a future consolidation decision
research_only: true
---

# INT-R9 — Amendment Conformance Verification

## Executive verdict

**Verdict: `CONFORMS_WITH_GAPS`.**

The amendment at `bb322361eafb5bd8667c35aeedf137dcbfdee1ae` executed the load-bearing Option-B decision in the amended research text, not merely in its own ledger. The protocol now permits result-informed repair only as **adaptive continuation**, preserves each canonical confidence scope as a separate local owner record, and attaches **no probability** to the event that the reported first positive is false. The strongest permitted statement is a procedural custody claim about prospectivity, firstness, sealing, no substitution, owner receipts, human adjudication, dissent, and publication. The original `INT-R9-C-001` / `INT-R9-D-001` path therefore no longer falsifies an asserted family bound: the A/B/C trace may occur locally, but INT-R9 emits no family scope, family ordinal, cumulative spend, `delta`, `3 * delta`, `3/100`, `1/300`, or other first-positive risk number.

R1–R14 are substantively executed. The amended INT-R1 seam uses `ObligationCoverageEnvelope`, maps `known_incomplete` and materially unresolved `open_world_unresolved` to NO-GO, and forbids post-inspection narrowing of the same protected action. The former 852-line YAML is genuinely retired: the current file has 61 comment-only lines, zero non-comment tokens, and `yaml.safe_load(...) is None`. All thirteen corrected `:1-120` adjudication ranges exist at the pinned baseline; the constitution and failure-pattern anchors resolve at `:382-398` and `:70-78`. Independent re-enumeration of all fifteen manifests reproduces the amendment's 4/11 calibration and topology split, 5/6/4 authority split, universal expected-ID/label/vote exposure, and four manifests containing at least one null gold card.

Two gaps remain, neither reopening Option B:

1. **The architect's INT-R10 rebinding was incomplete across the artifact set.** The main narrative and amendment-ledger narrative correctly say that `research/int-r10-revision` supersedes the original branch, and the withdrawn `3 * delta` / `3/100` statements are explicitly corrected. But the `bound_int_r10_commit` frontmatter in the primary report, census, state-machine file, fixture file, and amendment ledger still points to `research/int-r10-family-wise-risk-composition@317fc9c36...`; the YAML comment does too. The primary and ledger also retain “Theorem B is audit-pending” wording after the INT-R10 revision verification returned `CONFORMS`, and two unstruck ledger summaries still say “sharpness/current arithmetic recorded.” This is a **material provenance/bookkeeping gap**, not a surviving INT-R9 numeric claim.
2. **Audit commendation `INT-R9-J-004` survives unevenly.** Its central facts—13+2, ua-msme integrated depth, 0/13, and the GY pre-inspection gate—are present in the primary report and census. The exact confidence-registry profile count and malformed-frontmatter warning survive only as a compact assertion in the amendment ledger rather than as independently anchored supporting narrative. This is a minor preservation gap, not a protocol defect.

The audit register contains **nine** commendation rows, not eight: `A-006`, `B-001`, `C-003`, `E-001`, `F-001`, `G-001`, `H-001`, `I-002`, and `J-004`. Eight survive fully in substance; `J-004` survives with the weaker preservation just described.

### Consolidation standing

A consolidation pass **may treat the Option-B design choice and the substantive R1–R14 amendment as settled**. It must carry the following open cleanup items rather than silently normalizing them:

- replace every superseded INT-R10 frontmatter/comment binding with the verified `research/int-r10-revision` identity and remove stale “audit-pending” language;
- correct the two remaining amendment-ledger shorthands that still describe withdrawn sharpness/current-arithmetic material as recorded results;
- either preserve the full `J-004` orientation subfacts with source anchors or explicitly record that they are audit-history facts not needed by the amended protocol; and
- add the explicit “promise that a positive promotion is achievable” exclusion to the amendment-ledger frontmatter if consolidation requires uniform deny-lists across every support artifact.

No re-research of INT-R9's Option-B result is required.

---

## Verification object and method

The controlling specification was read before the amender's ledger:

1. `policy-engine/docs/research/policy-operations/audits/int-r9/int-r9-recommended-revision.md` — R1–R14, §7, and §8;
2. `policy-engine/docs/research/policy-operations/audits/int-r9/int-r9-independent-audit.md` — finding register and commendations;
3. `policy-engine/docs/research/policy-operations/audits/int-r9/int-r9-seam-and-crosscheck.md` — S0-GAP-02 and INT-R1 meanings;
4. the five amended research artifacts at `bb322361e...` and their current-main forms at `a548a2f93...`;
5. the amended INT-R1 current text; and
6. the current INT-R10 revision verification and architect correction.

Only after forming the independent result was `policy-engine/docs/research/policy-operations/int-r9/amendment-ledger.md` read and compared with it.

The amendment diff from `978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d` to `bb322361eafb5bd8667c35aeedf137dcbfdee1ae` contains exactly six documentation changes:

| Path | Amendment status |
| --- | --- |
| `policy-engine/docs/research/policy-operations/int-r9-first-promotion-evaluation-protocol.md` | modified |
| `policy-engine/docs/research/policy-operations/int-r9/contamination-census.md` | modified |
| `policy-engine/docs/research/policy-operations/int-r9/first-promotion-evaluation-protocol.yaml` | modified |
| `policy-engine/docs/research/policy-operations/int-r9/fixture-specifications.md` | modified |
| `policy-engine/docs/research/policy-operations/int-r9/state-machine-and-artifact-contracts.md` | modified |
| `policy-engine/docs/research/policy-operations/int-r9/amendment-ledger.md` | added |

No code, test, audit file, outcome-corpus file, adjudication file, or unrelated pre-existing document changed on the amendment branch.

---

## Finding register

| ID | Severity | Disposition | Finding |
| --- | --- | --- | --- |
| `INT-R9-V-001` | commendation | preserve | Option B is implemented substantively: the D-001 three-scope trace remains visible, but every first-positive family-risk claim is withdrawn across the primary report, fixtures, state machine, public-record sketches, and YAML. |
| `INT-R9-V-002` | material | consolidation cleanup | The INT-R10 architect correction landed in the main narrative and struck the two headline ledger bullets, but the old branch/commit remains in five Markdown frontmatters plus the YAML comment; stale “Theorem B audit-pending” and two unstruck “sharpness/current arithmetic recorded” ledger summaries remain. |
| `INT-R9-V-003` | minor | preserve or expressly retire | `J-004` is the ninth commendation. Its core facts survive in primary/census text, but registry-profile counts and malformed-frontmatter warning survive only as amendment-ledger shorthand. |
| `INT-R9-V-004` | minor | deny-list cleanup | The primary report, census, fixture file, and state-machine file expressly exclude a promise that a positive promotion is achievable; the amendment-ledger frontmatter omits that exact phrase, though it grants no capability and denies authority and numeric claims. |
| `INT-R9-V-005` | commendation | preserve | R11 is stronger than a disclaimer: the YAML is comments-only, parses to `None`, and exposes no conformance object. |
| `INT-R9-V-006` | commendation | preserve | R13's full fifteen-manifest facts independently reproduce exactly. |

No blocking finding remains.

---

## Check 1 — Option B and the blocking finding

### 1.1 Search result: no probability is attached to the first-positive event

The primary frontmatter denies both a single-`delta` and a `3 * delta` first-positive claim; the Executive Finding calls the accepted subject a “prospective anti-selection and custody protocol without a sequence-level risk number” and says the current sequence may not assert `P(false first promotion) <= delta` (`policy-engine/docs/research/policy-operations/int-r9-first-promotion-evaluation-protocol.md:1-86`).

The selected position is explicit:

> “Keep result-bearing implementation repair between slots, classify the sequence honestly as adaptive continuation, and withdraw every numeric family-wise claim.”

The cost is equally explicit: local receipts remain local; no `delta`, `3 * delta`, or other probability is attached to the reported first-positive event (`.../int-r9-first-promotion-evaluation-protocol.md:55-88`).

The attempt rule says every result-informed change is adaptive, the prior slot is never rescored, and a later positive “carries no family-risk number” (`.../int-r9-first-promotion-evaluation-protocol.md:246-278`). Promotion predicates require bounded wording with “no family number” (`:281-318`). Counterexamples admit A/B/C local scopes and say “allowed locally; no family number is claimed” (`:365-397`). The formal promotion rule has no family-risk conjunct (`:454-484`). The final answer again says “no sequence-level numeric false-promotion claim” (`:525-545`).

The state-machine invariants prohibit representing separate receipts as one cumulative scope, spend, ordinal, `delta`, or `3 * delta`; the public record sketch fixes `family_risk_statement` to no INT-R9 sequence bound (`policy-engine/docs/research/policy-operations/int-r9/state-machine-and-artifact-contracts.md:82-118`, `:215-268`). The fixture battery's `FP-R01` replays the exact D-001 trace and requires no family object or public number (`policy-engine/docs/research/policy-operations/int-r9/fixture-specifications.md:80-126`, `:151-177`). The contamination census makes no probability claim. The YAML has no executable content.

Searches for `3/100` in the current INT-R9 amendment artifacts find only the architect's explicitly withdrawn correction history in the primary report and struck amendment-ledger bullet. `1/300` does not occur in the amended INT-R9 artifacts. References to `3 * delta` in fixtures/state are prohibitions or falsifiers, not assertions.

### 1.2 Strongest permitted statement

The strongest positive statement is procedural: the earliest qualifying attempt was evaluated under named versions, sealed packages, canonical owners, adjudicators, assumptions, and prior-attempt history, with no prohibited post-result selection found. It expressly denies covert-collusion proof, population validity, legal compliance, institutional competence, readiness, omitted-obligation control, evaluator infallibility, or family risk (`.../int-r9-first-promotion-evaluation-protocol.md:62-91`). No later passage upgrades that statement.

### 1.3 Replay of `INT-R9-D-001`

The amendment does not pretend the source changed:

```text
slot 1 -> design-problem A -> scope A -> local ordinal 0
slot 2 -> design-problem B -> scope B -> local ordinal 0
slot 3 -> design-problem C -> scope C -> local ordinal 0
stop on first positive
```

This remains a valid set of local histories. Under Option B, however, the INT-R9 artifact emits only separate local receipts plus procedural chronology. It has no proposition for that trace to violate. `FP-R01` requires exactly this result. The blocking audit finding is therefore closed by **withdrawal**, not by a fictional cross-scope invariant.

### 1.4 Audit §8 kill-rule walk

| Audit §8 rule | Current source fact | Why it cannot produce the forbidden amended outcome |
| --- | --- | --- |
| three distinct scopes can each start with fresh `delta` | The local-scope fact remains possible. | The accepted subject has no family probability. A fresh local budget cannot be represented as one INT-R9 family guarantee; `FP-R01` requires no family output. The rule is neutralized by the R1-permitted withdrawal, not falsified as a source fact. |
| “cumulative” remains an author-written field | No `cumulative_scope`, family spend, family ordinal, or family bound is admitted in the sketches or YAML. | Local owner receipts stay separate, and any attempt to serialize a cumulative field invalidates the research reading. |
| failed-slot risk disappears because the next case has a new scope | Each earlier terminal and local receipt remains in chronology. | INT-R9 makes no family-risk disposition, refund, or aggregate claim. It neither erases nor reallocates local risk. |
| post-result scope narrowing rescues an obligation gap | The amended INT-R1 mapping says `known_incomplete` and material unresolved are NO-GO. | A narrower action requires a new prospective identity, envelope, protocol version, commitments, and fresh cases; the old scored slot stays nonpositive. |
| unresolved materiality is decided after its direction is known | Late, unforeseen, conflicted, unavailable, or unsealed promotion-critical materiality enters `disputed`. | No friendly assessor may create a favorable materiality rationale after seeing direction. |
| YAML remains executable while questions remain open | The file contains 61 comments and no YAML node. | Independent `yaml.safe_load` returned `None`; zero non-comment, nonblank lines were found. |

The audit's acceptance clause expressly permits R1 closure by honest withdrawal/narrowing. Reading the first keep-blocked bullet as requiring source changes even after withdrawal would contradict that acceptance clause and the amendment specification's Option B.

**Check 1 verdict: conforms.**

---

## Check 2 — result standing

`accepted_narrow_scope` now names the **nonnumeric procedural protocol**, while current execution readiness remains `blocked`. That distinction is consistent in:

- primary frontmatter and Executive Finding (`.../int-r9-first-promotion-evaluation-protocol.md:1-78`);
- the exact result classification and final answer (`:92-126`, `:525-545`);
- census frontmatter (`policy-engine/docs/research/policy-operations/int-r9/contamination-census.md:1-31`);
- state-machine frontmatter and standing section (`.../state-machine-and-artifact-contracts.md:1-48`);
- fixture frontmatter and doctrine (`.../fixture-specifications.md:1-42`);
- the YAML comment header (`.../first-promotion-evaluation-protocol.yaml:1-20`); and
- amendment-ledger frontmatter and chosen-position section (`.../amendment-ledger.md:1-76`).

No handoff or final-answer sentence says that the current repository can execute the protocol, produce a positive, or emit a family bound. Operational prerequisites remain absent and are named as such.

The standing is therefore not the original overstatement. It is accepted only for a research-level, nonnumeric anti-selection/custody result.

**Check 2 verdict: conforms.**

---

## Check 3 — R1 through R14

| Revision | Verification disposition | Independent evidence |
| --- | --- | --- |
| **R1** | executed by withdrawal | No sequence-level risk proposition survives; D-001 trace produces local receipts only. |
| **R2** | executed | `accepted_narrow_scope` is restricted to the nonnumeric protocol; execution remains blocked everywhere. |
| **R3** | executed | Every result-informed repair is adaptive; “general repair” privilege removed; no rescore or family number (`main:246-278`; state invariant 8; `FP-R02`). |
| **R4** | executed as a hard prerequisite | Direction-blind specification, existing competent-owner mapping, evidence/time/conflict/escalation, and default dispute are required; no owner is appointed (`main:303-326`; state materiality sketches; `FP-R03`). |
| **R5** | executed | Secrecy, non-access, role separation, and in-pool randomization are separated from pool-construction independence; purposive tractability remains visible (`main:221-244`; census §§6 and 9; `FP-R09`). |
| **R6** | executed | Corroborating evidence and declared residuals are distinct; same-network/funder/governance ties require explicit disposition (`main:327-350`; state `IndependenceEvidenceBundle`; `FP-R04`). |
| **R7** | executed | Controls detect mechanical/unsupported refusal only; exact supported refusal of every unseen case remains conforming (`main:348-363`; `FP-F12`, `FP-R10`). |
| **R8** | executed by owner boundary | INT-R9 records chronology but defines neither numerator nor denominator; canonical metric mapping remains an open integration interface (`main:341-351`; state `MetricChronologyProjection`; `FP-R06`). |
| **R9** | executed | Exact `ObligationCoverageEnvelope`; `known_incomplete` NO-GO; materially unresolved NO-GO; current baseline unresolved; narrower action requires new prospective identity (`main:353-370`; state §5.3; `FP-R05`). |
| **R10** | executed | Replacement means expressly governed canonical supersession; sibling “equivalent” rejected (`main:337-345`; state §1 and acceptance rules; `FP-R08`). |
| **R11** | executed | 61 comments, zero YAML nodes, no IDs/enums/transitions/vote rules/conformance path; independent parse returned `None`. Stale INT-R10 comment binding remains as finding V-002. |
| **R12** | executed | All thirteen `:1-120` endpoints exist; constitution `:382-398` and failure patterns `:70-78` resolve and support the claims. |
| **R13** | executed | Full roster of fifteen independently read; programmatic aggregation returns 4/11, 5/6/4, four null-card manifests, and universal expected IDs/labels/votes. |
| **R14** | executed | FIPS is limited to digest/change detection; hiding is attributed to commitment construction plus low-entropy threat model (`fixture-specifications.md:145-166`). |

No revision was silently omitted or declined.

### 3.1 R9 cross-check against amended INT-R1

Current amended INT-R1 says PolicyOS cannot issue `bounded_complete` at the pinned baseline, identifies `open_world_unresolved` as the honest steady state, and makes concrete omission/validator failure `known_incomplete` (`policy-engine/docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:35-105`). INT-R9 reproduces those consequences without claiming world completeness or auto-promotion. The old “narrow the criteria and public claim” rung is explicitly withdrawn.

### 3.2 R11 parser result

Transient verification, not committed as code:

```text
line_count 61
non_comment_lines 0 []
yaml_safe_load None
```

The remaining old INT-R10 branch string is inside a comment and cannot make the file executable, but it is stale provenance.

### 3.3 R13 independent enumeration

The exact roster was taken from `outcome-corpus/adjudications/README.md:29-45`. Every one of the fifteen JSON manifests was read at `a548a2f93...`. The extracted rows were aggregated with a transient `Counter` script:

```text
manifest_count 15
role_counts {'synthetic': 2, 'real': 13}
calibration_counts {'deep-pilot-round-1': 4, 'null': 11}
topology_counts {'deep_pilot_overlap': 4, 'partial_disjoint': 11}
authority_counts {'governed': 6, 'production': 5, 'research': 4}
null_gold_manifest_count 4
null_gold_manifests [
  'housing-rent-stabilization-001.adjudication.json',
  'w11a_eu_temporary_protection_ukraine_2022.adjudication.json',
  'w11a_india_aadhaar_dbt_2016.adjudication.json',
  'w11a_pakistan_ehsaas_cash_2020.adjudication.json'
]
all_expected_ids True
all_labels True
all_votes True
```

This exactly matches the census (`policy-engine/docs/research/policy-operations/int-r9/contamination-census.md:101-158`). Housing supplies the synthetic fourth deep-pilot and one semantic-pass null card (`.../housing-rent-stabilization-001.adjudication.json:1-170`). EU, India, and Pakistan supply the three real null-card examples.

### 3.4 R12 range reproduction

Line 120 was fetched successfully in each real manifest named in the census. The corrected current-state block at `universal-policy-design-system-vision-and-organizing-rules.md:382-398` contains one integrated ua-msme case, twelve per-slice cases, all thirteen blockers, zero useful rate, shadow B, and unbuilt D3.8. `policy-design-case-failure-patterns.md:70-78` contains P29, P33, and P34. No amended research file uses the former `:1-170`, `:404-430`, or `failure-patterns.md:200-900` as its current supporting anchor; those strings remain only in immutable audit history where they document the original defect.

**Check 3 verdict: conforms, with the INT-R10 provenance gap carried separately.**

---

## Check 4 — nine commendations

The finding register has nine commendations. The “eight commendations” wording elsewhere is audit bookkeeping, not an amendment defect.

| Commendation | Surviving amended passage | Verification |
| --- | --- | --- |
| `A-006` | “13 public real regression cases + 2 public synthetic calibration fixtures + 0 sealed decisive cases + 0 adjacent unseen cases”; ua remains the only full-loop case and current proving ground is unconverted. | fully survives in census §§1, 3, 10 and main baseline. |
| `B-001` | External work supplies “procedural mechanisms and warnings, not statistical, legal, or authority proof”; the first event is not a randomized trial or population sample. | fully survives in main §3. |
| `C-003` | The custody claim is “not proof against covert collusion… population performance, legal compliance, institutional competence, production readiness, or family-risk control.” | fully survives in Executive Finding and final answer. |
| `E-001` | “ua-msme… remains ineligible as decisive primary and adjacent evidence”; exclusion may produce `exhausted_without_promotion`, which is valid. | fully survives in main Executive/§2.4 and census §5. |
| `F-001` | “identified accountable natural person”; “model, agent, synthetic reviewer, or role ID cannot qualify”; panel and alternates predeclared; raw votes and dissent remain public. | fully survives in main §4.8 and state/fixture evidence. |
| `G-001` | Observable violations include easier-case substitution, hidden reruns, threshold/materiality changes, failed-run exclusion, denominator edits, outcome-contingent rewards, and heldout-case repair. | fully survives in main §4.12. |
| `H-001` | S0-GAP-02 owns serialization, hiding/binding commitment, keys, access, reveal, rotation, succession, challenge, incident response, and generic evaluator/reviewer machinery. | fully survives in main §4.9; sibling equivalent expressly prohibited. |
| `I-002` | “workflow states are custody facts, not a second authority lattice”; no identifier, field, transition, package, or owner becomes canonical by appearing in the research sketch. | fully survives in state-machine §§1, 6 and the six-file additive diff. |
| `J-004` | 13+2, ua integrated depth, 0/13, and GY preregistration gate remain in main/census; the amendment ledger says the registry-profile counts and malformed-frontmatter warning were retained. | survives with weaker preservation: the last two subfacts are not independently re-anchored in the primary/supporting narrative. Finding `INT-R9-V-003`. |

**Check 4 verdict: eight full; one weaker but not contradicted.**

---

## Check 5 — added claims and seams

### 5.1 Classification of substantive additions

| Added substantive claim class | Classification | Audit/revision basis |
| --- | --- | --- |
| Option B, no family number, local receipts remain separate | required consequence / narrowing | R1–R2 and D-001 |
| result-informed repair is adaptive and never rescored | required consequence | R3 / C-002 / D-002 |
| direction-blind materiality or dispute | required consequence | R4 / D-003 |
| purposive-pool residual survives secrecy/randomization | verified narrowing | R5 / E-002 |
| independence evidence/declaration/residual tiers | required consequence | R6 / F-002 |
| mechanical-refusal detection does not solve strategic abstention | verified narrowing | R7 / G-002 |
| chronology recorded, metric membership external | required boundary | R8 / G-003 |
| exact amended-INT-R1 ladder | required seam correction | R9 / H-002 |
| S0-GAP-02 replacement only by canonical supersession | required seam correction | R10 / H-003 |
| comments-only YAML | required scope correction | R11 / I-001 |
| anchor and fifteen-manifest facts | verified factual correction | R12–R13 |
| FIPS/commitment attribution split | verified attribution correction | R14 |
| typed artifact sketches with no canonical standing | narrowed engineering illustration | existing sketch narrowed by R3–R11; explicitly noncanonical |
| architect INT-R10 correction note | later architect correction, not the amender's claim | INT-R10 revision and its `CONFORMS` verification |

No unmarked new substantive INT-R9 theorem, capability, owner, schema, denominator, probability, or production claim was found. Open operational questions—materiality owner mapping, metric mapping, independence threshold, case-frame quality, and future family projection—remain explicitly in §10 rather than being converted into contracts.

### 5.2 S0-GAP-02 seam

The former “consolidation-approved equivalent” escape hatch is gone. The amended text says a replacement is acceptable only if an expressly governed decision **supersedes** S0-GAP-02 as the canonical owner, and that “equivalent” never means a sibling service or schema (`main:337-345`). The state and fixture files repeat the sibling-framework negative.

The amendment states properties needed from commitment/access/evaluator custody but does not choose cryptographic primitives, key stores, access services, rotation systems, challenge platforms, or evaluator implementation. No P27/P28 duplicate owner appears.

### 5.3 INT-R10 seam after architect correction

The architect correction landed in the main narrative: the old sharpness/`3/100` corollary is explicitly identified as refuted and withdrawn, the current paragraph states Boole's inequality without claiming a live family projection, and the narrative says the current binding is `research/int-r10-revision` (`main:45-70`). The amendment ledger strikes the two original bullets and says the same (`amendment-ledger.md:38-65`).

No current INT-R9 passage asserts the withdrawn `3 * delta`, `3/100`, or `1/300` as its result. Occurrences are one of:

- struck or quoted withdrawal history;
- a `may_not_use_for` exclusion;
- a negative fixture/falsifier; or
- a state invariant prohibiting such a claim.

The correction missed artifact-wide provenance cleanup, producing `INT-R9-V-002`:

- old `bound_int_r10_commit` remains in five Markdown frontmatters;
- the YAML comment binds the superseded artifact;
- the ledger R1 row still says “INT-R10 union/sharpness/current arithmetic recorded”;
- the §7 evidence row still says “INT-R10 theorem/sharpness recorded”; and
- primary/ledger text still calls Theorem B “audit-pending” after the revision verification returned `CONFORMS` while preserving the current absence of a numeric theorem for outcome-dependent repair.

These are stale provenance/bookkeeping statements. None feeds a promotion predicate, public family statement, fixture pass, or Option-B conclusion.

**Check 5 verdict: substantive seams conform; INT-R10 provenance cleanup remains open.**

---

## Check 6 — boundaries

| Boundary | Verification result |
| --- | --- |
| source under `policy-engine/src/` | untouched by amendment |
| tests | untouched; none added |
| audit bundle | untouched by amendment; later architect explicitly left audit evidence unchanged |
| outcome corpus/adjudications | inspected only; no amendment modification |
| other pre-existing documents | untouched by amendment |
| canonical owner/package/schema | none appointed or frozen; shapes explicitly research-only and replaceable |
| status lattice | no parallel lattice; workflow states remain custody phases |
| risk accounting | no second ledger, parent scope, family ordinal, or family projection |
| oracle/evaluator custody | no sibling framework; S0-GAP-02 or express canonical supersession only |
| S0-K13 | semantic properties and equivalent implementations preserved; witness never becomes specification |
| S0-K15 | committed packages, adjacent unseen case, dissent, failed-run history, no post-result threshold/fixture exclusion preserved |
| S0-K16 | every permitted statement bounded to named revision/environment/cases/evaluator/assumptions/protocol and explicitly nonnumeric at family level |
| `research_only` | true in every Markdown artifact; YAML is retired comments only |
| positive-result promise exclusion | explicit in primary, census, state, and fixture frontmatter; amendment-ledger frontmatter lacks the exact phrase, finding V-004 |

The amendment branch itself is scope-clean. The later architect commit changed only the primary INT-R9 report and amendment ledger for the sibling-result correction; it did not edit the audit bundle.

**Check 6 verdict: conforms with one minor deny-list omission.**

---

## Final determination

The amendment's core claim is now honest and executable as research guidance:

> It governs observable prospective selection and custody in an adaptive finite sequence, publishes every terminal, and makes no sequence-level probability claim.

A rule-following executor may still open three local scopes and stop on the first positive, but can no longer obtain the forbidden result—an INT-R9 representation that those scopes form one single-`delta` family—without directly violating the amended text, fixtures, state invariants, and public-record boundary.

Therefore:

- **Option B is settled for consolidation.**
- **R1–R14 are substantively closed.**
- **Current operational execution remains blocked**, as the amendment says.
- **No new research question is required.**
- **Consolidation must carry only the provenance, ledger-shorthand, commendation-preservation, and deny-list cleanup gaps identified above.**
