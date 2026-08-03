---
title: INT-R9 — Post-Audit Amendment Ledger
status: delivered
kind: deep-research-support
research_task: INT-R9
result_type: accepted_narrow_scope
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r9-amendment
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: 978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d
inspection_date: 2026-08-03
amended_after_audit: research/int-r9-independent-audit@a09128e6b914292597054b82bda2701d541b1fea
bound_int_r10_commit: research/int-r10-family-wise-risk-composition@317fc9c36e710ac75634096c4d14a714b8bff504
bound_int_r1_amendment_commit: research/int-r1-amendment@66baff37c7f566fc770377ba6c66a8dc7b517ce0
amendment_choice: option_b_keep_adaptive_repair_withdraw_numeric_family_claim
authoritative_for:
  - claim-by-claim disposition of the independent INT-R9 audit findings
  - mapping of R1 through R14 to amended repository artifacts
  - evidence package requested for independent re-audit
  - preservation ledger for audit commendations and ratified-kernel constraints
may_not_use_for:
  - production implementation authorization
  - final code, wire, schema, package, database, evaluator, or metric contract
  - canonical owner appointment
  - authority grant or capability claim
  - benchmark passage
  - a sequence-level numeric false-promotion claim
  - proof that INT-R10 Theorem B has passed independent audit
  - replacement of the independent re-audit
research_only: true
---

# INT-R9 — Post-Audit Amendment Ledger

## 1. Amendment standing and chosen option

The independent audit at `research/int-r9-independent-audit@a09128e6b914292597054b82bda2701d541b1fea` ruled the original INT-R9 `NO_GO`. The blocking defect was not that prospective governance is impossible. It was that the report represented three distinct design-problem confidence scopes as one cumulative single-`delta` family.

INT-R10 at `research/int-r10-family-wise-risk-composition@317fc9c36e710ac75634096c4d14a714b8bff504` subsequently established:

- **Theorem A:** prospectively enforced local caps `alpha_i` compose by the union inequality when `sum_i alpha_i <= delta_F`;
- **sharpness:** ~~three disjoint local `delta` error events can produce family error exactly `3 * delta`~~ — **withdrawn 2026-08-03** (architect, after the INT-R10 audit): the result holds only in the abstract, after coarsening the local owner to `P(V_i) <= delta`; it does not hold for the pinned owner;
- **current arithmetic:** ~~at live `delta=1/100`, three ordinary local scopes generically support `3/100`, not `1/100`~~ — **withdrawn 2026-08-03**: the Basel-square series telescopes, so one scope's pathwise envelope is strictly below `delta * (3/20) * mass` and three scopes sit below `(9/20) * delta`, i.e. below a single `delta`; and
- **current capability:** pre-execution family caps and a canonical family projection are absent.

Neither withdrawal touches an INT-R9 claim: Option B attaches no probability to the first-positive
event. The binding is now `research/int-r10-revision`, superseding
`research/int-r10-family-wise-risk-composition@317fc9c36`.

INT-R10 Theorem B says adaptive continuation may be composable under history-measurable pathwise caps and a selection-valid local theorem. Its independent audit is pending. No numeric INT-R9 claim relies on Theorem B.

### Chosen position

This amendment selects **Option B: keep between-slot repair and withdraw the sequence-level numeric family claim.**

Consequences applied consistently:

1. result-informed repair is explicitly adaptive;
2. local confidence scopes/receipts remain separate and conditional;
3. INT-R9 emits no `P(false first promotion) <= delta`, no protocol-level `3 * delta`, no cumulative scope/spend/ordinal, and no family projection;
4. the accepted subject is the nonnumeric anti-selection/custody protocol;
5. `result_type: accepted_narrow_scope` refers only to that subject;
6. operational readiness remains blocked by cases, custody, human evidence, materiality, and amended INT-R1 standing; and
7. any future numeric family claim requires a separately accepted canonical owner extension and fresh audit.

## 2. R1–R14 execution ledger

| Revision | Required action | Disposition | Amended locations |
| --- | --- | --- | --- |
| **R1** | Prove or withdraw single-`delta` claim. | **Executed by withdrawal.** INT-R10 union/sharpness/current arithmetic recorded; all sequence numeric claims prohibited. | main Executive, §§2.2, 4.1, 4.4, 5, 7–10; state §§1–2, 5; fixtures `FP-R01` |
| **R2** | Align standing everywhere. | **Executed.** Accepted narrow nonnumeric protocol; current execution blocked. Same in every frontmatter, executive, handoff, public shape, kill rule, YAML note, and final answer. | all amended artifacts |
| **R3** | Make adaptive revision explicit. | **Executed.** Every result-informed repair is adaptive even when syntactically general; prior slot is not rescored; no family number follows. | main §4.4; state invariant 8 and `AdaptiveRepairRecord`; fixtures `FP-R02` |
| **R4** | Close materiality right prospectively. | **Executed as hard prerequisite.** Sealed specification, competent existing owner mapping, evidence/conflict/time rules, and default dispute. No owner appointed by research. | main §4.7; state §§2, 5; fixtures `FP-R03` |
| **R5** | Narrow new-case independence. | **Executed.** Secrecy/non-access/role separation/random selection within pool distinguished from pool-construction independence. Purposive-pool bias remains visible. | main §§4.2, 5; census §§6, 9; fixtures `FP-R09` |
| **R6** | Require evidence for independence dimensions. | **Executed.** Documentary evidence required where available; declared-only dimensions remain residual; same-network ties get explicit disposition. | main §4.8; state `IndependenceEvidenceBundle`; fixtures `FP-R04`, §6 |
| **R7** | Narrow anti-abstention claim. | **Executed.** Controls detect mechanical/unsupported refusal only. Supported refusal of every unseen case remains conforming. | main §4.13; fixtures `FP-F12`, `FP-R10` |
| **R8** | Reconcile useful-design denominator without redefining it. | **Executed by owner boundary.** INT-R9 records chronology and omits membership; canonical metric owner mapping remains open. | main §4.12; state `MetricChronologyProjection`; fixtures `FP-R06`; YAML retired |
| **R9** | Bind actual amended INT-R1 output and ladder. | **Executed.** Uses `ObligationCoverageEnvelope`; current `open_world_unresolved` blocks; `known_incomplete` blocks; future bounded completeness is exact-scope relative; no post-result narrowing. | main §4.14; state §5.3; fixtures `FP-F06`, `FP-R05` |
| **R10** | Constrain S0-GAP-02 “equivalent.” | **Executed.** Replacement means expressly governed canonical supersession only; sibling equivalent rejected. | main §4.9; state §§1, 9–10; fixtures `FP-R08` |
| **R11** | Demote executable YAML in substance. | **Executed.** All mappings, IDs, counts, vocabularies, transitions, blockers, and vote rules removed. File contains comments only and parses to null. | `first-promotion-evaluation-protocol.yaml`; fixtures `FP-R07` |
| **R12** | Re-anchor census and failure patterns. | **Executed.** Thirteen adjudication anchors `:1-120`; constitution `:382-398`; failure patterns `:70-78`. | census §3; main §§2–3; fixture doctrine |
| **R13** | Correct calibration, authority, and gold-card facts. | **Executed.** Exact 15-manifest enumeration: 4/11 calibration/topology; authority 5/6/4; expected IDs/labels/votes universal; non-null gold cards not universal. | main §2.3; census §4; §5.2 below |
| **R14** | Clarify FIPS attribution. | **Executed.** FIPS limited to digest/change detection; hiding conclusion attributed to commitment literature and threat model. | main §3; fixture `FP-F04` |

No R-item was declined.

## 3. Finding-by-finding disposition

### Pass A — anchors and census

| Finding | Severity | Disposition and evidence |
| --- | --- | --- |
| `INT-R9-A-001` | material | All thirteen real-manifest citations now use exact valid `:1-120`; former `:1-170` retired. See census §3. |
| `INT-R9-A-002` | material | Current-state facts re-anchored to constitution `:382-398`. See main §2.2 and census §3. |
| `INT-R9-A-003` | material | Correct exact count is four deep-pilot manifests, including synthetic housing. See census §4. |
| `INT-R9-A-004` | minor | Wording now says expected IDs/labels/votes are universally visible; non-null gold cards are not universal. Null examples named. |
| `INT-R9-A-005` | material | P29/P33/P34 re-anchored to `policy-design-case-failure-patterns.md:70-78`. |
| `INT-R9-A-006` | commendation | Preserved 13/15 denominator, public-answer contamination, ua integrated depth, and zero-conversion state. |

### Pass B — external transfer

| Finding | Severity | Disposition and evidence |
| --- | --- | --- |
| `INT-R9-B-001` | commendation | Main §3 preserves procedural-transfer/statistical-proof boundary; no population or legal theorem imported. |
| `INT-R9-B-002` | material | The original rhetorical accounting bridge is removed. INT-R10 supplies union/sharpness; Option B makes no family number. |
| `INT-R9-B-003` | minor | FIPS attribution narrowed to digest/change detection; hiding comes from commitment literature and threat model. |

### Pass C — claimed proposition

| Finding | Severity | Disposition and evidence |
| --- | --- | --- |
| `INT-R9-C-001` | blocking | Closed by withdrawing the false family clause. Exact permitted proposition is procedural and nonnumeric. |
| `INT-R9-C-002` | material | Later revisions are explicitly adaptive continuation; later positive is not described as three looks at one fixed implementation. |
| `INT-R9-C-003` | commendation | Preserved exclusions: population validity, legal compliance, production readiness, competence, covert collusion, and authority grant. |

### Pass D — multiplicity, repair, materiality

| Finding | Severity | Disposition and evidence |
| --- | --- | --- |
| `INT-R9-D-001` | blocking | The A/B/C fresh-scope trace is now explicitly permitted locally and cannot falsify a nonexistent family claim. See `FP-R01` and §5.1. |
| `INT-R9-D-002` | material | “General repair” privilege removed. Every result-informed change is adaptive; repair ancestry/diff/information used are published; no rescore or family theorem. |
| `INT-R9-D-003` | material | Direction-blind materiality specification/evidence required before result; late/unforeseen/conflicted/unavailable classification yields dispute. |

### Pass E — ua-msme and new cases

| Finding | Severity | Disposition and evidence |
| --- | --- | --- |
| `INT-R9-E-001` | commendation | ua-msme remains excluded from both primary and adjacent roles, with possible non-convergence accepted. |
| `INT-R9-E-002` | material | Public claim narrowed: pool secrecy and within-pool randomization do not remove pool-author tractability judgment. |
| `INT-R9-E-003` | minor | ua-msme reopening described as extraordinary causal-isolation burden, not normal path; hidden label alone cannot cleanse lineage. |

### Pass F — adjudicator independence

| Finding | Severity | Disposition and evidence |
| --- | --- | --- |
| `INT-R9-F-001` | commendation | Named accountable natural persons, alternates, raw dissent, and synthetic/role-only ban preserved. |
| `INT-R9-F-002` | material | Evidence/declaration/residual tiers added; same-funder/network/governance ties receive explicit conflict disposition; signatures alone insufficient. |

### Pass G — incentives and metric

| Finding | Severity | Disposition and evidence |
| --- | --- | --- |
| `INT-R9-G-001` | commendation | Observable useful-rate optimization detectors preserved: case substitution, hidden reruns, threshold/materiality edits, exclusion, rewards, and bespoke mechanisms. |
| `INT-R9-G-002` | material | Heading/claim narrowed to mechanical or unsupported refusal. Supported refusal of all unseen cases remains conforming. |
| `INT-R9-G-003` | material | Prose/YAML denominator conflict removed. INT-R9 records chronology; canonical metric owner decides membership. |

### Pass H — seams

| Finding | Severity | Disposition and evidence |
| --- | --- | --- |
| `INT-R9-H-001` | commendation | Generic oracle/evaluator/commitment/access/rotation/challenge machinery still deferred to S0-GAP-02. |
| `INT-R9-H-002` | material | Placeholder replaced by delivered `ObligationCoverageEnvelope`; exact NO-GO ladder and current `open_world_unresolved` standing bound; no post-result narrowing. |
| `INT-R9-H-003` | minor | “Equivalent” escape hatch removed. Only an expressly governed canonical supersession can replace S0-GAP-02. |

### Pass I — scope and YAML

| Finding | Severity | Disposition and evidence |
| --- | --- | --- |
| `INT-R9-I-001` | material | 852-line executable mapping deleted in substance; comments-only file returns YAML `null` and has no conformance vocabulary. |
| `INT-R9-I-002` | commendation | Additive-only research scope, no package owner, no code/tests, and one-lattice custody framing preserved. |
| `INT-R9-I-003` | blocking | Standing corrected: accepted only for nonnumeric procedural protocol, operationally blocked. No false family theorem remains in accepted subject. |

### Pass J — orientation

| Finding | Severity | Disposition and evidence |
| --- | --- | --- |
| `INT-R9-J-001` | material | Exact calibration count corrected to 4 non-null / 11 null, with synthetic housing included. |
| `INT-R9-J-002` | material | Exact authority distribution corrected to 5 production / 6 governed / 4 research. |
| `INT-R9-J-003` | minor | Committed answer-bearing fields distinguished from non-null gold-card values. |
| `INT-R9-J-004` | commendation | Remaining verified orientation retained: 13+2, ua integrated depth, 0/13, registry profile counts, GY preregistration gate, malformed frontmatter warning. |

## 4. Required re-audit evidence from audit §7

| Requested evidence | Delivered evidence |
| --- | --- |
| revised commit and baseline | branch `research/int-r9-amendment`; baseline `978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d`; final HEAD obtainable from branch |
| claim-by-claim audit disposition | §§2–3 of this ledger |
| family-risk derivation or withdrawal | Option B in §1; INT-R10 theorem/sharpness recorded; main Executive/§4.1 |
| three-distinct-problem trace | §5.1 and fixture `FP-R01` |
| refused/void/disputed effects | main §9; state §2; chronology retained, dispute halts, no rescoring |
| adaptive-revision and materiality rules | main §§4.4, 4.7; state invariants; fixtures `FP-R02`/`FP-R03` |
| exact INT-R1 artifact/posture mapping | main §4.14; state §5.3; fixture `FP-R05` |
| useful-rate denominator mapping | explicit unresolved canonical-owner interface; no INT-R9 membership rule |
| exact census ranges | thirteen `:1-120`; constitution `:382-398`; failure patterns `:70-78` |
| structured artifact non-contract evidence | comments-only YAML, null parse, no mappings/IDs/enums/counts/transitions |

## 5. Reproduction evidence

### 5.1 Three-scope falsifier

Expected live-source trace:

```text
slot 1 -> design-problem A -> scope A -> local ordinal 0 -> local delta
slot 2 -> design-problem B -> scope B -> local ordinal 0 -> local delta
slot 3 -> design-problem C -> scope C -> local ordinal 0 -> local delta
```

Amended expected output:

```text
three separate canonical local receipts
complete prior-attempt chronology
no INT-R9 cumulative scope
no INT-R9 family ordinal
no INT-R9 family spend
no P(false first promotion) <= delta
no protocol-level 3 * delta claim
```

A consumer adding a number without a separately accepted canonical family projection violates the amended protocol.

### 5.2 Fifteen-manifest enumeration

The exact manifest roster was enumerated and these fields extracted: filename, real/synthetic role, `authority_level`, `reviewer_topology.topology_mode`, `reviewer_topology.calibration_round_id`, null-card presence, expected IDs, labels, and votes.

Reproduction logic:

```python
import json
from collections import Counter

rows = json.load(open("manifest-field-extract.json"))
assert len(rows) == 15
assert len({row["manifest"] for row in rows}) == 15
print(Counter("null" if row["calibration_round_id"] is None
              else row["calibration_round_id"] for row in rows))
print(Counter(row["topology_mode"] for row in rows))
print(Counter(row["authority_level"] for row in rows))
print([row["manifest"] for row in rows if row["null_gold_card"]])
print(all(row["expected_ids"] for row in rows))
print(all(row["labels"] for row in rows))
print(all(row["votes"] for row in rows))
```

Observed output:

```text
manifest_count 15
calibration {'deep-pilot-round-1': 4, 'null': 11}
topology {'deep_pilot_overlap': 4, 'partial_disjoint': 11}
authority {'governed': 6, 'production': 5, 'research': 4}
null_gold_card_manifests [
  'housing-rent-stabilization-001.adjudication.json',
  'w11a_eu_temporary_protection_ukraine_2022.adjudication.json',
  'w11a_india_aadhaar_dbt_2016.adjudication.json',
  'w11a_pakistan_ehsaas_cash_2020.adjudication.json'
]
all_expected_ids True
all_labels True
all_votes True
```

Transient extraction SHA-256:

```text
0e546b0c362f4861a9acefa8deba859e818f8a562068c6652fd040f0ed71eec1
```

The transient extraction is not committed because this pass may add no code/data artifact; the full fifteen-row result is committed in the census.

### 5.3 YAML demotion verification

```python
from pathlib import Path
import yaml
text = Path("int-r9/first-promotion-evaluation-protocol.yaml").read_text()
assert yaml.safe_load(text) is None
assert not [line for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")]
```

Expected and observed amendment result:

```text
safe_load: None
non_comment_nonblank: []
```

This is substantive demotion, not a disclaimer: the mapping no longer exists.

### 5.4 Anchor verification

All thirteen real manifests were checked for line 120 at the pinned baseline; it exists. Correct ranges are:

```text
adjudications/<each real manifest>.json:1-120
universal-policy-design-system-vision-and-organizing-rules.md:382-398
policy-design-case-failure-patterns.md:70-78
```

## 6. Audit §8 acceptance and kill-rule walk

### Acceptance conditions

| Condition | Amendment evidence |
| --- | --- |
| R1 validated or numeric claim withdrawn/narrowed | withdrawn under Option B; INT-R10 arithmetic recorded |
| standing matches | accepted narrow nonnumeric protocol; operational execution blocked everywhere |
| material decision rights prospective/checkable | specification/evidence/time/conflict/default-dispute rule |
| actual INT-R1 and S0-GAP-02 seams | exact envelope bound; supersession-only replacement language |
| no parallel ledger/status/oracle | explicit owner boundaries; no family field/service |
| exact anchors | corrected ranges and exact fifteen-manifest set facts |
| D-001 cannot falsify claimed property | D-001 trace is admitted; no family property is claimed |

### Keep-blocked rules

| Audit rule | Amended status |
| --- | --- |
| three distinct scopes each start fresh `delta` | may occur locally; no family number follows |
| “cumulative” remains author-written | removed from protocol fields/claims; only historical discussion remains |
| failed-slot risk disappears in next scope | no family-risk disposition is made; chronology and local ledger truth retained |
| post-result narrowing rescues obligation gap | forbidden; new prospective identity/version/cases required |
| unresolved materiality decided after direction | automatic dispute |
| YAML executable while questions open | mapping removed; parse result null |

The finite three-slot chronology survives as an anti-selection/publication engineering convenience, not a family theorem. Consolidation may choose another finite count while preserving the properties.

## 7. Commendation preservation

| Strength to preserve | Amendment evidence |
| --- | --- |
| ua-msme excluded from primary and adjacent roles | main Executive/§2.4; census §5; NO-GO rules |
| public corpus never called holdout | main §§2.3, 4.5; census §§1, 8–9 |
| named natural persons, alternates, raw dissent, synthetic ban | main §4.8; state §5.6; fixtures `FP-R04` |
| negative outcomes publishable, including exhaustion | main Executive/§§4.4, 9; state §2; `FP-F14` |
| sharply bounded positive statement | main Executive, §4.1, Final Answer |
| real useful-rate observables | main §4.12; fixtures `FP-R06` |
| S0-GAP-02 generic custody ownership | main §4.9; state §1; `FP-R08` |
| additive-only, no-second-lattice custody framing | frontmatter; state §§1, 6, 9 |
| procedural transfer distinguished from statistical/legal proof | main §3 |

## 8. Ratified-kernel conformance

- **S0-K13:** fixtures define observable semantic relations and permit equivalent implementations; no YAML enum/topology becomes truth.
- **S0-K15:** committed packages, mutations, adjacent unseen case, failed-run retention, raw labels, abstentions, disputes, corrections, and no post-result threshold/fixture change remain.
- **S0-K16:** every permitted positive is bounded to named revision, environment, cases, evaluator, assumptions, and protocol, and explicitly states absence of a family number.

No reopening candidate is created.

## 9. File disposition

| File | Amendment role |
| --- | --- |
| `../int-r9-first-promotion-evaluation-protocol.md` | amended ten-section deliverable and final answer |
| `contamination-census.md` | exact anchors, complete fifteen-manifest facts, narrowed new-case claim |
| `state-machine-and-artifact-contracts.md` | adaptive/nonnumeric state semantics and research shapes |
| `fixture-specifications.md` | core and audit-specific adversarial probes |
| `first-promotion-evaluation-protocol.yaml` | retired comments-only parse-to-null index |
| `amendment-ledger.md` | finding/re-audit/preservation record |

The audit bundle, INT-R10 branch, amended INT-R1 branch, code, tests, corpus, plans, and all other documents remain untouched.

## 10. Re-audit question

The amendment should be re-audited as:

> Is the nonnumeric anti-selection/custody protocol internally consistent, accurately anchored, correctly bound to amended INT-R1 and INT-R10, and incapable of being read as one family-wise `delta` claim or an executable YAML contract?

It should not be audited as though Option A was chosen. No canonical cap/family projection is claimed or required for the accepted procedural result. Any future numeric family amendment is a new load-bearing change requiring source-backed validation and independent audit.
