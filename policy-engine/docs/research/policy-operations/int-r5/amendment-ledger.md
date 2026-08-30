---
title: "INT-R5 — Stage 3 amendment ledger"
research_id: INT-R5
stage: amendment
status: delivered_amendment
responds_to_audit_head: 247f89f016f71ee603ed76ef6dbb6403f7e651a0
package_head_audited: 02e203de90d51280d569e7f641a158569ae4df39
base: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
branch: research/int-r5-amendment
finding_total: 18
accepted: 16
accepted_with_variation: 2
declined_with_reason: 0
blocking: 0
material: 7
minor: 2
commendation: 9
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
---

# INT-R5 Stage 3 Amendment Ledger

## 1. Scope and method

This amendment responds to every row in the independent audit register and changes the package files
where the audited claims lived. It does not answer a finding only by describing a preferred correction
in this ledger.

All package line ranges below are post-amendment line ranges on `research/int-r5-amendment`. Repository
writes and readbacks in this stage used the authenticated GitHub connector after local DNS failure and
the user's explicit instruction to use that connector. Connector observations are not represented as
terminal command output.

The amendment changes research artifacts only. It does not modify source, workflows, `AGENTS.md`, the
pattern register or any audit artifact.

## 2. Architect ground truth remeasurement

The architect-supplied values were treated as orientation and independently remeasured through GitHub
ref/compare/history reads before amendment writing.

| Ground truth | Architect supplied | Amendment remeasurement | Result |
|---|---|---|---|
| `G1` heads and topology | `package..audit=15`; `base..audit=22`; `base..package=7`; both ancestor checks `0`; both compares `behind_by=0` | package→audit `ahead_by=15`, `behind_by=0`, merge base `02e203de9…`; base→audit `ahead_by=22`, `behind_by=0`; base→package `ahead_by=7`, `behind_by=0`; audit and package were exact ancestors of the newly created amendment branch | **agreement** |
| `G2` package→audit delta | 7 added Markdown files under `audits/int-r5/`; zero non-Markdown; zero package files changed | compare returned exactly seven added `.md` files under `policy-operations/audits/int-r5/` and no package-file modification | **agreement** |
| `G3` package file set | exactly 5 named package files | base→package/package-tree inspection returned the same five files: main UDF plus four files under `int-r5/` | **agreement** |
| `G4` audit register | 18 unique rows: A001–A009 and C01–C09; `0+7+2+9=18` | row-by-row parse returned 9 corrective IDs and 9 commendation IDs, all unique; severity counts 0 blocking, 7 material, 2 minor, 9 commendation | **agreement** |
| `G5` audit history | 7 skeleton + 7 delivery + 1 append-only correction = 15; correction one file, `+11/-9`, no finding/severity/verdict change | package→audit history returned 15 commits; compare from the pre-correction head to `247f89f…` returned one modified audit file with 11 additions and 9 deletions and no package change | **agreement** |

The stage-2 DNS limitation is closed at architect level and is not reopened as a defect. This stage's
connector-derived delivery evidence is reported separately and honestly.

## 3. Disposition register

Closed disposition vocabulary used exactly:

```text
accepted
accepted_with_variation
declined_with_reason
```

| Finding | Severity | Disposition | Audit anchor | Package file(s) and line range changed | What is now true |
|---|---|---|---|---|---|
| `INT-R5-A-001` | material | `accepted` | recommended revision §§2, 4.1; formal audit §2 | `int-r5-decision-authority-validity.md:297-318`; `int-r5/decision-authority-specification.md:76-113`; `int-r5/external-evidence-ledger.md:189-210` | The universal inequality and “theorem” label are withdrawn. Equal-state histories are allowed; the package states a two-history non-inferability proposition. Snapshot/lease/revalidation conclusions remain. |
| `INT-R5-A-002` | material | `accepted` | recommended revision §§2, 4.2; seam audit §5 | `int-r5-decision-authority-validity.md:83-101,180-193,569-580`; `int-r5/repository-baseline.md:140-179,236-272`; `int-r5/adversarial-fixtures.md:433-465` | Acquisition is described as a DS20 permission/resource/step-up route leading to `run_data_ingestion`. The PA2/DS9 institutional-authority bridge and consumer are named **missing**. Adjacency is not called composition. |
| `INT-R5-A-003` | material | `accepted_with_variation` | recommended revision §§2, 4.3; formal audit §4 | `int-r5-decision-authority-validity.md:153-179,204-232`; `int-r5/repository-baseline.md:1-31,54-82,180-219,273-284` | The ten files are narrowed to `int-r5-authority-slice-v1`, not a complete closure. Four fragments and six non-observations are claims about that slice only; repository-wide zeroes are explicitly not established. A future complete closure requires reproducible AST/import plus route/call enumeration. |
| `INT-R5-A-004` | material | `accepted` | recommended revision §§2, 4.4; formal audit §5 | `int-r5-decision-authority-validity.md:331-351`; `int-r5/decision-authority-specification.md:114-155,245-332`; `int-r5/adversarial-fixtures.md:98-164,357-403` | Decision time, issue/as-of time, effect/commit time, effect class, profile applicability and revalidation mode now have named semantic producers/verifiers. Canonicalization is limited to integrity after admission and cannot upgrade caller provenance. Red tests cover backdating, profile shopping, effect downgrade and mode downgrade. |
| `INT-R5-A-005` | material | `accepted_with_variation` | recommended revision §§2, 4.5; anchor audit §3 | `int-r5/survey-source-manifest.md:1-161`; `int-r5/external-evidence-ledger.md:1-40,285-295`; `int-r5-decision-authority-validity.md:244-253` | Exact survey titles, external file/version IDs, line/byte denominators, SHA-256 digests, stable package URNs, claim anchors and branch-local admitted extracts are committed. Branch-only claim-transfer replay is possible. Full original survey bytes remain external and require the artifact matching the digest; that residual is explicit rather than falsely reported closed. |
| `INT-R5-A-006` | material | `accepted` | recommended revision §§2, 4.6; formal audit §6 | `int-r5-decision-authority-validity.md:393-404`; `int-r5/decision-authority-specification.md:493-532`; `int-r5/adversarial-fixtures.md:1-38` | Bare uppercase reason oracle values are withdrawn. Candidate identities use `polisyos.int_r5.reason.<slug>@0.1.0-candidate`; the live eval-safety certificate-stale blocker is a semantic sibling, not an alias. Projection remains owned by the existing status architecture and cannot upgrade a negative. |
| `INT-R5-A-007` | material | `accepted` | recommended revision §§2, 4.7; seam audit §6 | `int-r5-decision-authority-validity.md:130-150,569-580`; `int-r5/decision-authority-specification.md:16-75`; `int-r5/adversarial-fixtures.md:404-432` | For individual-case or pointwise-recoverable effects, the positive predicate conjunctively requires INT-R5 authority, DS20 exact admission and a separate PAO-R4 receipt. Two-direction negatives prove neither receipt substitutes for the other. PAO-R4 remains a separate owner. |
| `INT-R5-A-008` | minor | `accepted` | recommended revision §§2, 4.8; formal audit §8 | `int-r5-decision-authority-validity.md:421-434`; `int-r5/decision-authority-specification.md:559-594`; `int-r5/adversarial-fixtures.md:283-356`; `int-r5/external-evidence-ledger.md:89-123` | A new cure result must state `prospective`, `relation_back`, `saved_act`, `limited` or `unresolved`, with `legally_effective_from` and scope. The original certificate remains immutable. Relation-back regimes are representable and not universalized. |
| `INT-R5-A-009` | minor | `accepted` | recommended revision §§2, 4.9; orientation ledger §3.1 | `int-r5-decision-authority-validity.md:62-82`; `int-r5/repository-baseline.md:32-53` | The ledger now records two closure-order violations (GY-PA2, DS9), DS14 as an unclosed named consumer, DS20 as a missed feed, and acquisition as a missing integration: five relationships of four types, not “three violations.” |
| `INT-R5-A-C01` | commendation | `accepted` | independent audit C01 | `int-r5-decision-authority-validity.md:1-45`; `int-r5/survey-source-manifest.md:1-17` | Exact pins, branch, scope and evidence-custody limitations remain explicit. Connector-derived state is not passed off as terminal output; no transport workaround is used. |
| `INT-R5-A-C02` | commendation | `accepted` | independent audit C02 | `int-r5-decision-authority-validity.md:153-179`; `int-r5/repository-baseline.md:1-31,273-284` | The measurement holder and denominator are named. Search-index zeroes remain orientation only. The correction strengthens the property by refusing a complete-closure claim the measurement did not earn. |
| `INT-R5-A-C03` | commendation | `accepted` | independent audit C03 | `int-r5-decision-authority-validity.md:194-203`; `int-r5/repository-baseline.md:120-139` | Current Python/Rego permission parity remains exactly 34/34; historical 33 remains classified as documentation drift. |
| `INT-R5-A-C04` | commendation | `accepted` | independent audit C04 | `int-r5-decision-authority-validity.md:365-380`; `int-r5/decision-authority-specification.md:400-451`; `int-r5/external-evidence-ledger.md:161-188` | Conflict claims remain bounded to named records, declarations and adjudication. Undisclosed/off-system conflict absence is expressly not provable. |
| `INT-R5-A-C05` | commendation | `accepted` | independent audit C05 | `int-r5-decision-authority-validity.md:351-365`; `int-r5/adversarial-fixtures.md:220-282`; `int-r5/external-evidence-ledger.md:124-160` | Forum, presence, quorum and vote remain jurisdiction/profile and item-time relative. `at_vote`, `throughout_meeting` and `presumptive_until_challenged` variants remain mandatory. |
| `INT-R5-A-C06` | commendation | `accepted` | independent audit C06 | `int-r5-decision-authority-validity.md:435-461`; `int-r5/adversarial-fixtures.md:1-534` | The five mandatory fixtures retain property, Given/When/Then, near-pass and mutation structure. The pack is expanded with producer, PAO-R4 and missing-bridge attacks without weakening the original fixtures. |
| `INT-R5-A-C07` | commendation | `accepted` | independent audit C07 | `int-r5-decision-authority-validity.md:405-420`; `int-r5/decision-authority-specification.md:533-558`; `int-r5/adversarial-fixtures.md:466-475` | Missing institutional holders remain a typed `not_established` result naming the exact role. Candidate/demo and negative replay remain available; no maintainer, team or adjacent signer is borrowed. |
| `INT-R5-A-C08` | commendation | `accepted` | independent audit C08 | `int-r5-decision-authority-validity.md:130-150`; `int-r5/decision-authority-specification.md:16-75`; `int-r5/adversarial-fixtures.md:404-432` | PAO-R4 remains conceptually and operationally non-substitutable. The amendment adds the missing conjunction without absorbing its owner or weakening its individual-use protection. |
| `INT-R5-A-C09` | commendation | `accepted` | independent audit C09 | `int-r5-decision-authority-validity.md:421-434`; `int-r5/decision-authority-specification.md:446-463,559-594`; `int-r5/adversarial-fixtures.md:283-356,480-490` | Historical replay remains immutable; post-effect handling does not claim rollback. Relation-back/current cure effect is appended as a separate profile-qualified result. |

## 4. Reconciliation checks

### 4.1 Disposition count

```text
accepted                 16
accepted_with_variation   2
declined_with_reason      0
---------------------------
total                     18
```

Arithmetic:

```text
16 + 2 + 0 = 18
```

### 4.2 Severity count

```text
blocking      0
material      7
minor         2
commendation  9
----------------
total        18
```

Arithmetic:

```text
0 + 7 + 2 + 9 = 18
```

The register has 18 unique IDs. Counts are table-row counts, never token occurrences.

## 5. Closure-criterion mapping

| Finding | Recommended-revision criterion met | Checkable closure evidence |
|---|---|---|
| `A-001` | §4.1 | Search the amended main/spec for the old universal equation: it is absent. The new text explicitly permits equality in unchanged histories and constructs two indistinguishable-at-`t0` histories that diverge at `t1`. |
| `A-002` | §4.2 | Repository baseline prints the exact `ingest_data -> DS20 -> run_data_ingestion` path and sets `acquisition_to_PA2_DS9_bridge: missing`; fixtures reject proving integration through the separate DS9 route. |
| `A-003` | §4.3 variation allowed by audit/user | Frontmatter and baseline set `complete_executable_closure_claimed: false`. The ten paths are enumerated as a selected slice; known out-of-slice positive controls are named; all six zeroes are narrowed to non-observations. |
| `A-004` | §4.4 | The field-by-field table names producer, verifier, requester control and fail-closed mutation for time, effect class, profile applicability and revalidation mode. Fixtures hold canonical hashes valid while provenance/semantics fail. |
| `A-005` | §4.5 with explicit residual | `survey-source-manifest.md` contains exact survey identity, digest, stable ref, anchor and admitted extract for every load-bearing transfer. Full-byte verification is not claimed branch-local and is routed to the matching external artifact. |
| `A-006` | §4.6 | Every fixture reason is namespaced/versioned. The crosswalk identifies the existing eval-safety sibling and says no alias exists yet; mapping owner and no-upgrade invariant are explicit. |
| `A-007` | §4.7 | `ProtectedEffectAdmissible` contains the conditional PAO-R4 conjunct. Fixtures cover valid INT-R5/missing PAO-R4 and valid PAO-R4/missing INT-R5, both with zero effect. |
| `A-008` | §4.8 | Cure output enumerates all five temporal kinds, includes `legally_effective_from`, effect scope and `historical_certificate_mutated: false`; relation-back has a required fixture. |
| `A-009` | §4.9 | Corrected YAML separates closure violations, unclosed consumer, missed feed and missing integration. No aggregate “three violations” remains in package conclusions. |

## 6. Package-file modification and untouched-file report

### 6.1 Five original package files not modified

```text
none
```

Every original package file carried either an audited claim or a property that had to remain
consistent with the corrections. Therefore all five were modified rather than leaving stale claims in
the reader-facing package.

| Original package file | Why modified |
|---|---|
| `int-r5-decision-authority-validity.md` | owns UDF conclusions, component verdicts, information proposition, standing, handoff and Pattern Pass |
| `int-r5/repository-baseline.md` | owned the false complete-denominator and acquisition-composition claims |
| `int-r5/decision-authority-specification.md` | owned producer, reason, PAO-R4 and cure contracts |
| `int-r5/external-evidence-ledger.md` | owned survey transfer, information-limit wording and cure synthesis |
| `int-r5/adversarial-fixtures.md` | owned bare reason oracles and executable closure tests |

### 6.2 New package artifacts

- `int-r5/survey-source-manifest.md` — added because exact external artifact identity, byte digest,
  source-custody boundary and claim-to-source anchors are a distinct evidence responsibility from the
  semantic synthesis in `external-evidence-ledger.md`. The existing ledger now links to it and states
  the same residual; it was not silently replaced.
- `int-r5/amendment-ledger.md` — required by pipeline §3.3 to reconcile all 18 audit rows. It does not
  substitute for corrections in the package files.

## 7. Orientation errors I made and corrected

1. **I counted unlike dependency relationships as “three ordering violations.”** Corrected to two
   explicit closure-order violations, one unclosed consumer, one missed feed and one missing bridge.
2. **I treated architectural adjacency as a landed acquisition composition.** Direct route/service
   inspection shows DS20-only protection before ingestion; PA2/DS9 institutional consumption is
   missing.
3. **I called a selected ten-file authority slice a complete executable owner closure.** The label is
   withdrawn; no repository-wide zero rests on it.
4. **I promoted an illustrative inequality into an “information-limit theorem.”** The package now
   states non-inferability with correct quantification.
5. **I allowed canonicalization language to obscure missing semantic producers.** Producers and
   verifier/fail-closed tests are now explicit per decisive field.
6. **I used bare local reason tokens as fixture oracles.** They are now namespaced/versioned candidate
   identities with an explicit crosswalk boundary.
7. **I cited PAO-R4 without placing it in the positive effect conjunction.** Both directions are now
   enforced in the research predicate and fixtures.
8. **I preserved cure profiles without requiring temporal legal effect.** Relation back, saving and
   other temporal outcomes are now first-class without rewriting history.

## 8. `NO_GO` condition self-check

| Audit §5.2 condition | Amendment check | Result |
|---|---|---|
| acquisition adjacency retained as call edge | route is DS20-only; bridge explicitly missing | pass |
| universal inequality retained under new heading | equation removed; equality allowed; non-inferability quantified | pass |
| ten-file sample still called complete | selected slice only; complete closure false | pass |
| requester time/effect/profile becomes decisive through hashing | semantic producers and mismatch tests required | pass |
| branch-replayable evidence claimed without source identity | exact identities/digests/anchors committed; full-byte residual explicit | pass |
| second global lattice or duplicate bare reasons | family-local union; namespaced candidate reasons; crosswalk owner retained | pass |
| PAO-R4 absorbed or weakened | separate owner and mandatory conditional conjunct | pass |
| relation-back denied universally | explicit `relation_back` cure kind and fixture | pass |
| capability/gate standing promoted by better prose | standings remain accepted-narrow-scope / absent-unallocated / NO_GO | pass |

No amendment action implements the capability, allocates an owner, appoints a holder, registers final
wire vocabulary, creates a production route, authorizes an individual case or opens a gate.

## 9. Standing after amendment

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```

The amendment makes the research package more accurate. It does not confer authority; only pipeline
stage 7 can do that.
