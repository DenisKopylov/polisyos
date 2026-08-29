---
title: INT-R2 — Amendment Ledger
status: stage_3_amendment_delivered
research_task: INT-R2
stage: 3
package_head: 5e6a7063da770122155af6300647d0cd2e9c17ea
audit_head: dbdb1243a277f0864cae9af240ff1d13786d99df
audit_verdict: GO_WITH_REVISIONS
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
authoritative_for:
  - stage-3 response to every INT-R2 independent-audit finding
  - corrections and bounded additive clarifications identified in the traceability table
may_not_use_for:
  - independent verification of this amendment
  - ratification
  - capability claim
  - owner, producer, auditor, grantor or signer appointment
  - production admission
  - gate opening
---

# INT-R2 — Amendment Ledger

## 1. Scope And Topology

This is the stage-3 response to the independent audit under
`policy-engine/docs/research/policy-operations/audits/int-r2/`.

- Package head: `5e6a7063da770122155af6300647d0cd2e9c17ea`.
- Audit head: `dbdb1243a277f0864cae9af240ff1d13786d99df`.
- Amendment branch: `research/int-r2-amendment`.
- Branch creation point: the exact audit head, not the original package base.
- Connector comparison before the first write returned `identical` against the audit head and
  `ahead_by: 8`, `behind_by: 0`, with merge base equal to the exact package head against the package.
- First amendment write: headings-only ledger commit
  `9ef45fe906842ad1d35336f004377f434d1330eb`.

No audit artifact is modified. The package remains research-only; this amendment does not ratify the
union, appoint an owner or institutional producer, move capability, implement fixtures, classify the
fourteen residuals or open any gate.

## 2. Denominator And Orientation Reading

The audit's complete severity-bearing finding population is the **16 rows** in
`audits/int-r2/int-r2-independent-audit.md:78-93`: nine `material`, three `minor` and four
`commendation`. Its own arithmetic at `:137-155` says this is the complete finding denominator.

The three accepted orientation errors are **outside that 16-row severity denominator as O-ledger
observations, but they are not three additional amendment findings**. The evidence is the separate
orientation table at `audits/int-r2/int-r2-orientation-error-ledger.md:93-100` and its result at
`:108-118`. Their relationship to the 16 is:

- the institutionally supplied zero is preserved by commendation `INT-R2-AUD-C002`;
- the consumer-row evidentiary defect is already severity-bearing as `INT-R2-AUD-F012`;
- the owner-appointment and “three structural gaps” prompt errors are orientation corrections with no
  separate severity row because the package declined both overclaims.

Accordingly this amendment reconciles **16 finding dispositions** and separately records **three
orientation acknowledgements**. It does not report 19 findings.

| ID | Supplied orientation error | Amendment position | Counted in the 16? |
| --- | --- | --- | --- |
| `INT-R2-AMD-O01` | The package would “turn the routing into an owner”. | Accepted as a prompt error. Stage 1 specifies a candidate boundary and integration contract only; owner appointment remains out of scope. | No separate row. |
| `INT-R2-AMD-O02` | The three capstones were described as structurally classified gaps. | Accepted as a prompt error. Owner evidence establishes three `not_a_data_gap` routes, a negative classification only. | No separate row. |
| `INT-R2-AMD-O03` | The supplied zero structural classifications was usable as a settled zero. | Accepted as a prompt error. The package's `institutionally_supplied` / `not_established` treatment is preserved. | Represented by commendation C002. |

## 3. Correction Criterion

A response is made **in place** when leaving the original sentence, cell or coordinate standing would
leave a factual error, an overbroad repository-zero, an unregistered standing value or an
under-identified source state. In-place corrections therefore cover:

- the false F01 coordinate;
- the F05/F07/F11/F32 sampled-evidence versus repository-zero overclaims;
- all six mixed standing cells;
- the three under-pinned source rows S04/S13/S14; and
- the consumer-row demand statement, which now carries a holder label and non-effect.

A response is made by an **explicit additive amendment** only where the earlier statement remains a
research candidate but lacks the construction, invariant or closure condition needed to evaluate it.
The additive text below names the affected audit finding and governs later reading of the package's
classifier, ceiling, terminal and benchmark proposals. This applies to classifier predicates,
field-level ceiling algebras, open-world terminal coverage, the two T4 refinements and the
uninstantiated benchmark requirements.

A response is **preserved** when the audit commendation or refuted threat found the package correct.
Preservation creates no credit against a defect and changes no standing.

No finding is declined. The four unwalked absence claims are not defended by an unpublished census;
their local positives are retained and their repository-wide components are downgraded
holder-relatively.

## 4. Additive Amendment Contracts

### 4.1 Reproducible `GapShapeAssessment` branch decision — AUD-F005

`GapShapeAssessment` is a decision record only after the following predicates have been constructed
from the frozen demanding gate. A label, case name, document title or proposed producer cannot supply
one of these predicates.

Common preconditions:

1. bind the exact residual, demanding gate, blocked claim/action and rule/reference epoch;
2. state the minimal object whose presence would change the blocked predicate;
3. classify `same_stream_data_effect` as `can_change | cannot_change | not_established`;
4. give every positive predicate and every sibling falsifier a P37 label;
5. allow `one_case` only when the selected branch and at least one nearest sibling falsifier are
   `recomputed` or `independently_reconciled`;
6. use `split_required` when independently necessary predicates select more than one object; and
7. use `not_established` whenever a required predicate is `consumer_asserted`,
   `institutionally_supplied` or `not_established`.

| Case type | Minimal blocked-predicate form | Positive selection evidence | Nearest sibling falsifier | Missing-evidence result |
| --- | --- | --- | --- | --- |
| `grounding_relation` | The gate requires a scoped warrant that changing/intervening on A can change Y; target meaning is already bound. | Exact relation/query, context, evidence regime and assumptions are bound, and the absent object is the relation warrant rather than estimate precision. | An unresolved treatment/population/outcome/contrast selects `estimand_binding`; an identified target with only finite-sample imprecision selects `data_gap`. | `not_established`. |
| `estimand_binding` | The gate cannot state the target quantity unambiguously. | At least one required target attribute—intervention/regime, population, outcome/horizon, intercurrent-event strategy or contrast—is absent or admits incompatible meanings. | If all target attributes are bound and only the relation/identification warrant is absent, rule out this branch in favour of `grounding_relation` or a separately governed method gap. | `not_established`. |
| `owner_writability` | The demanded effect is a mutation of canonical state for an exact object and operation. | The system of record, object/field, operation and purpose are fixed, and either substantive change authority or technical execution grant is independently missing. | If no canonical mutation is demanded and the blocker is lawful competence for an external act, select `legal_mandate`; a data-availability blocker is not writability. | `not_established` or an ordered two-obligation writability case. |
| `legal_mandate` | The actor/body's lawful competence for the exact act is unresolved. | Governing norm/jurisdiction, actor/office, act and relevant delegation chain are fixed and a required competence link is absent. | If lawful competence is present but consent, ethics or regime sanction is absent, select `normative_authorization`; a technical mutation grant is `owner_writability`. | `not_established`. |
| `normative_authorization` | A governing regime requires consent, approval, waiver or other sanction for the exact purpose/version. | The applicable regime and its producer/procedure are established, and the required determination is absent, stale, withdrawn or out of scope. | If no such regime is established and only legal competence is missing, select `legal_mandate`; informal legitimacy with no issuer/procedure stays `not_established`. | `not_established`. |
| `implementation_capacity_evidence` | The gate requires proof that a specified delivery system can deliver the next bounded commitment at a stated scale, environment and horizon. | Delivery entity, intervention version, next commitment, critical prerequisites and evidence threshold are fixed; direct prerequisite evidence is absent or insufficient. | A legal prohibition selects `legal_mandate`; an unresolved causal relation selects `grounding_relation`; generic organisational concern alone does not select capacity. | `not_established`. |
| `competent_human_decision` | The gate requires an attributable case-specific judgment by a competent authorised person. | The decision question, role, competence scope, subject/version and required work record are fixed, and that decision artifact is absent or invalid. | If the demanded product is assurance against stated criteria with relational independence and an assurance level, select `independent_audit`. | `not_established`. |
| `independent_audit` | The gate requires an assurance conclusion over a stated subject, criteria, scope, period and level. | Assurance engagement semantics and independence relationship are fixed, and the valid assurance artifact is absent, limited or conflicted. | A management/professional decision without an assurance engagement selects `competent_human_decision`; `external=true` alone selects nothing. | `not_established`. |

The ordinary `data_gap` outcome requires a separately constructed observable-availability or precision
predicate plus evidence that the proposed acquisition changes that predicate. `binding_gap` and row
count alone never satisfy it.

Capstone application:

- `education` remains a **candidate** `estimand_binding` case until the frozen demanding predicate
  reconstructs the missing target attribute; the route label alone is not the positive predicate;
- `first_vertical` and `unseen` remain `not_established` or `split_required` until evidence separates
  relation warrant from substantive/technical writability; and
- none of the three is positively classified merely by `not_a_data_gap`.

For each of the fourteen later residuals, the required row is:

```yaml
residual_id: <exact later-row identity>
blocked_predicate_ref: <demanding-owner predicate>
minimal_missing_object: <constructed object or null>
same_stream_data_effect: <can_change | cannot_change | not_established>
positive_predicate_refs: []
nearest_sibling_falsifier_refs: []
predicate_provenance: <registered P37 labels>
classification_outcome: <data_gap | one_case | split_required | not_established>
missing_classifier_inputs: []
```

Those later identities and demanding predicates are not present in this holder's pin. The amendment
therefore does not classify the fourteen; it states the evidence required to do so.

### 4.2 Field-level `AuthorityCeiling` checkability — AUD-F007

The former shorthand “subset-testable” denotes a desired consumer property, not a claim that all
relations already have registered algebras. The twelve dimensions are amended as follows.

| Dimension | Relation | Unknown / conflict rule | Relation status today | Runtime status |
| --- | --- | --- | --- | --- |
| exact claim/action refs | exact equality or literal membership in an explicit allow-set | missing/unknown fails; exact deny wins | `checkable_today` | aggregate evaluator `absent/unallocated` |
| exact subject/object refs | content-bound identity equality; a different version is a different object | mismatch or unresolved identity fails | `checkable_today` | aggregate evaluator `absent/unallocated` |
| valid/review time | interval containment plus currentness at use time | missing bound, expiry or contradictory clock evidence fails | `checkable_today` | aggregate evaluator `absent/unallocated` |
| permitted operations / prohibited uses | exact-token membership only; prohibition wins | unknown operation or any exact prohibition fails | `checkable_today` | aggregate evaluator `absent/unallocated` |
| population | registered set containment over a population definition/version | unknown containment fails; no inference from labels | `checkable_after_registered_mapping` | `absent/unallocated` |
| jurisdiction | registered overlap/subordination/competence relation | overlap or precedence not proved fails | `checkable_after_registered_mapping` | `absent/unallocated` |
| purpose / audience | registered purpose and audience subsumption | sibling or broader purpose is not inferred; conflict fails | `checkable_after_registered_mapping` | `absent/unallocated` |
| source → target context | governed compatibility/transport relation | absent transport proof fails | `checkable_after_registered_mapping` | `absent/unallocated` |
| evidence class | registered mapping from evidence class to maximum claim class | unknown class/order fails | `checkable_after_registered_mapping` | `absent/unallocated` |
| maintained assumptions | exact assumption identities plus owner-computed currentness/coverage | missing, changed or unresolved assumption fails | `checkable_after_registered_mapping` | `absent/unallocated` |
| maximum claim strength | registered partial order | incomparable or unknown strength fails | `checkable_after_registered_mapping` | `absent/unallocated` |
| maximum commitment stage | registered stage/load partial order | incomparable or broader stage fails | `checkable_after_registered_mapping` | `absent/unallocated` |

Downstream-gate refs, rule versions and reference epochs remain exact identity/currentness controls;
they do not manufacture the eight missing semantic relations. “Checkable today” above means the
relation can be stated mechanically from exact refs/times/tokens, not that a deployed generic
evaluator exists. Every unknown dimension fails closed.

### 4.3 Benchmark non-vacuity residual — AUD-F008

The arithmetic denominator `8 + 8 + 12 + 16 + 8 + 8 + 3 = 63` remains correct. The package does **not**
instantiate the 63 cases, does not appoint an oracle and does not claim that `0/63` has been earned.
Capability remains `semantic_test_missing`.

A future committed fixture manifest must bind, for every stable case ID:

```text
case_id
case_family + discriminator
exact immutable input bundle
protected property
independent oracle source/adjudicator
expected classification/closure/terminal/ceiling result
volatile fields excluded from comparison
named mutant(s) this case must kill
```

At minimum the manifest must red-prove these wrong implementations:

- `mutant.row_count_auto_closes_relation_estimand_mandate`;
- `mutant.form_or_signature_auto_admits`;
- `mutant.route_or_artifact_auto_closes_without_owner_reentry`;
- `mutant.exact_membership_used_for_hierarchy_or_subset`;
- `mutant.timeout_or_silence_emits_terminal`;
- `mutant.surface_composes_authority`; and
- `mutant.remove_property_keep_markers`, which removes the actual non-closure check while preserving
  labels, IDs and expected-result markers.

An ordinary data-gap positive control must still close after a valid admitted observation changes the
demanding predicate. The oracle must not be the same implementation whose result it judges. Because
neither exact cases nor independent oracle ownership exists, this amendment registers the gap rather
than fabricating a thin fixture pack.

### 4.4 Coverage-bounded `deeper_terminal` — AUD-F009

A terminal based on “no competent source or route exists” requires this admitted envelope:

```yaml
coverage_scope_kind: <finite registry | governing hierarchy | declared delivery alternatives | provider roster | other bounded universe>
universe_ref_and_content_identity: <ref/hash/version>
inclusion_and_exclusion_rule_refs: []
searched_source_or_route_refs: []
search_or_adjudication_procedure_ref: <ref>
valid_at_or_epoch: <time/epoch>
competent_challenger_or_review_route_ref: <ref or explicitly absent under governing rule>
unknown_remainder: <empty | nonempty | not_established>
coverage_result: <complete_for_declared_universe | incomplete | not_established>
```

Rules:

- formal non-identifiability, an ill-defined target, an exact higher-order prohibition or a valid
  competent disapproval may be terminal inside its stated formal/regime scope without an open-world
  actor census;
- `owner_writability` and `legal_mandate` source-absence terminals require a bounded owner/grantor or
  governing-hierarchy universe;
- `implementation_capacity_evidence` requires the decision horizon plus enumerated build, rescope and
  alternative-channel paths;
- `competent_human_decision` requires a bounded competent roster/referral regime; and
- `independent_audit` requires a bounded provider universe and relationship/threat evaluation.

If the envelope is missing or `unknown_remainder` is not empty, the strongest permitted result is
`exhausted_declared_route_at_epoch` or provisional refusal—not universal absence. Falsifying coverage
while retaining a terminal label must make the later fixture red.

### 4.5 Two T4 refinements without union restructuring — AUD-F010/F011

`owner_writability` remains one discriminator but carries two mandatory, separately stateful
sub-obligations:

```text
substantive_change_authority(object, operation, purpose)
AND
technical_execution_grant(actor/system, object, operation, interval)
```

Neither artifact closes the other. A valid token with no substantive right and a valid substantive
order with no executable grant remain blocked for different reasons; either may be routed first, but
closure requires both.

The shared reconstructable-work base does not permit cross-substitution:

```text
external competent human decision != independent audit
favourable independent audit       != underlying management/professional decision
```

The first lacks assurance engagement, criteria, level and relational-independence proof unless those
are separately acquired. The second assesses a subject under its ceiling and does not make the
underlying decision. Legitimate dependency references remain allowed.

### 4.6 Institutionally supplied consumer demand — AUD-F012

Every package citation of `gap_acquisition_case_union` is read as:

```yaml
holder_label: institutionally_supplied
authoritative_for: evidence that the commissioner reports live downstream demand
may_not_use_for:
  - proof that the exact row exists at the package pin
  - registration or merge status
  - owner allocation
  - consumer readiness
  - authority or capability
```

An immutable branch/ref/path may replace that label in a later holder's evidence. Search non-receipt
cannot settle a zero.

## 5. Finding Dispositions

`accepted_corrected` means the amendment changed the package or added a bounded construction.
`accepted_residual_registered` means the defect is accepted but honest closure would require work this
stage did not perform. `preserved` applies only to commendations.

| Audit ID | Severity | Disposition | Audit line | Amendment response | Package effect / remaining limit |
| --- | --- | --- | --- | --- | --- |
| `INT-R2-AUD-F001` | `material` | `accepted_corrected` | `audits/int-r2/int-r2-independent-audit.md:78` | `int-r2/amendment-ledger.md:299`; expanded register at `integration-handoff-and-finding-register.md` §4 | F01–F40 now carries kind, exact standing, evidence, transfer class, holder, consequence and non-effect. |
| `INT-R2-AUD-F002` | `material` | `accepted_corrected` | `audits/int-r2/int-r2-independent-audit.md:79` | `int-r2/amendment-ledger.md:300`; amended register §4 | F13/F27/F29/F31/F34/F39 use exact tokens; suffix content moved to kind/scope/basis. |
| `INT-R2-AUD-F003` | `material` | `accepted_corrected` | `audits/int-r2/int-r2-independent-audit.md:80` | `int-r2/amendment-ledger.md:301`; baseline §3 | False `gy_waist.py:218-255` removed; exact owner coordinate is `gy_waist.py:1318-1325`. |
| `INT-R2-AUD-F004` | `material` | `accepted_corrected` | `audits/int-r2/int-r2-independent-audit.md:81` | `int-r2/amendment-ledger.md:302`; baseline §3; amended register F05/F07/F11/F32 | Local positives retained; four repository-wide zeros are `not_established`. |
| `INT-R2-AUD-F005` | `material` | `accepted_corrected` | `audits/int-r2/int-r2-independent-audit.md:82` | `int-r2/amendment-ledger.md:97-154` | Eight positive predicates, sibling falsifiers, split/P37 rules and fourteen-row template added; no residual classified. |
| `INT-R2-AUD-F006` | `material` | `accepted_corrected` | `audits/int-r2/int-r2-independent-audit.md:83` | `int-r2/amendment-ledger.md:304`; `external-primary-source-ledger.md` S04/S13/S14 | Exact IARC Preamble, IESBA 2025 Code and ISAE 3000 states replace the three weak overview coordinates; 22-row structure preserved. |
| `INT-R2-AUD-F007` | `material` | `accepted_corrected` | `audits/int-r2/int-r2-independent-audit.md:84` | `int-r2/amendment-ledger.md:155-179` | Four literal/identity/time relations marked checkable; eight semantic relations deferred and fail closed; evaluator remains absent. |
| `INT-R2-AUD-F008` | `material` | `accepted_residual_registered` | `audits/int-r2/int-r2-independent-audit.md:85` | `int-r2/amendment-ledger.md:180-214` | No thin instantiation: exact 63 inputs/oracles/mutant failures remain `semantic_test_missing`; required manifest and mutants are registered. |
| `INT-R2-AUD-F009` | `material` | `accepted_corrected` | `audits/int-r2/int-r2-independent-audit.md:86` | `int-r2/amendment-ledger.md:215-246` | Open-world terminal requires bounded coverage; otherwise result narrows to declared-route exhaustion/provisional refusal. |
| `INT-R2-AUD-F010` | `minor` | `accepted_corrected` | `audits/int-r2/int-r2-independent-audit.md:87` | `int-r2/amendment-ledger.md:247-272` | Writability now has separately stateful substantive and technical conjuncts; union discriminator unchanged. |
| `INT-R2-AUD-F011` | `minor` | `accepted_corrected` | `audits/int-r2/int-r2-independent-audit.md:88` | `int-r2/amendment-ledger.md:247-272` | Explicit HD↛IA and IA↛underlying-decision invariants added; shared base remains possible. |
| `INT-R2-AUD-F012` | `minor` | `accepted_corrected` | `audits/int-r2/int-r2-independent-audit.md:89` | `int-r2/amendment-ledger.md:273-290`; amended handoff §§1,3 | Consumer row is `institutionally_supplied` with explicit non-effect; no existence/merge/readiness claim. |
| `INT-R2-AUD-C001` | `commendation` | `preserved` | `audits/int-r2/int-r2-independent-audit.md:90` | `int-r2/amendment-ledger.md:311`; baseline §5 | Proposition/denominator/executor/P37/consequence table preserved. |
| `INT-R2-AUD-C002` | `commendation` | `preserved` | `audits/int-r2/int-r2-independent-audit.md:91` | `int-r2/amendment-ledger.md:312`; baseline §5 | Supplied zero remains unsettled; `not_established` is preserved. |
| `INT-R2-AUD-C003` | `commendation` | `preserved` | `audits/int-r2/int-r2-independent-audit.md:92` | `int-r2/amendment-ledger.md:313`; §4.5 | Eight-type union and all 28 pair distinctions preserved; only two named refinements added. |
| `INT-R2-AUD-C004` | `commendation` | `preserved` | `audits/int-r2/int-r2-independent-audit.md:93` | `int-r2/amendment-ledger.md:314`; external ledger | Source→class→proposition→non-effect→holder structure preserved; only S04/S13/S14 source states strengthened. |

## 6. Package-File Traceability

| Changed package file | Disposition rows | Change class | Why this file changed |
| --- | --- | --- | --- |
| `int-r2/amendment-ledger.md` | all 16; direct contracts for F005/F007/F008/F009/F010/F011/F012 | additive amendment plus ledger | Records denominator, orientation corrections, response criterion, constructions, dispositions, arithmetic and non-effect. |
| `int-r2/repo-baseline-and-source-ledger.md` | F003, F004, C001, C002; O02/O03 | in-place correction | Repairs F01's false coordinate, splits sampled positives from unwalked zeros, preserves denominator discipline and refuses the supplied zero. |
| `int-r2/external-primary-source-ledger.md` | F006, C004 | in-place source-state correction | Pins S04/S13/S14 without flattening or rebuilding the 22-row transfer ledger. |
| `int-r2/integration-handoff-and-finding-register.md` | F001, F002, F004, F010, F011, F012, C003 | in-place structural upgrade | Replaces the three-column list with the ten-column register, normalizes standing, adds the two T4 refinements and holder-labels consumer demand. |

No audit artifact, source file, workflow, `AGENTS.md` or pattern register changed. The main ten-section
report and operational fixture proposal remain intact because T4's package-level charge and T6's
citation-list charge were refuted; the amendment ledger supplies only the surviving classifier,
ceiling, benchmark and terminal constructions. It expressly supersedes any reading that treats all
ceiling dimensions as already enforced or the 63-case denominator as an executed benchmark.

## 7. Standing And Non-Effect

The audit verdict is not lifted by its author. Package axes remain:

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```

This amendment does not:

- ratify or restructure the eight-type union;
- claim exhaustiveness beyond the eight commissioned objects;
- classify the fourteen `shape:not_established` residuals;
- establish a complete repository-wide absence walk;
- appoint the classifier/acquisition owner or any institutional producer, auditor, grantor or signer;
- register external vocabulary;
- instantiate or pass the 63-case battery;
- implement the common ceiling evaluator, producer bridges, consumers or surfaces; or
- open a production or public-signature gate.

`T4` was not “fixed” by changing the union: all 28 pair distinctions remain. `T6` was not “fixed” by
rebuilding the source ledger: its transfer/non-effect structure remains, and only the three weak
source-state coordinates were strengthened.

## 8. Arithmetic And Closure

Audit severity arithmetic remains:

```text
blocking      0
material      9
minor         3
commendation  4
----------------
total        16

0 + 9 + 3 + 4 = 16
```

Amendment disposition arithmetic:

```text
accepted_corrected            11
accepted_residual_registered   1
preserved_commendation          4
---------------------------------
total                          16

11 + 1 + 4 = 16
```

The three orientation acknowledgements are reported separately and add **zero** finding rows. There
are no declines. Independent stage-4 verification decides whether the responses close the audit; this
ledger does not self-verify.
