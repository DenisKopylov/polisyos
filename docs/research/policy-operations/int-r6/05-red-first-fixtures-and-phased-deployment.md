# INT-R6 red-first fixtures, phased deployment, and operational closure

## Fixture discipline

These fixtures are research specifications in Markdown, not implementation edits. Each fixture is **red first**:

1. source and deliberately defective target have structurally matching catalogue paths/placeholders;
2. the pre-MAEP structural mechanism is expected to pass or be unable to distinguish them;
3. the semantic assertion is expected to fail;
4. after MAEP exists, the defective target fails with a typed reason and the corrected target passes only for its declared purpose.

A green result obtained without first recording the red failure is not admissible evidence. Fixture evidence must name executor, baseline ref, protocol version, catalogue/glossary versions, and exact target digest.

## The three binding falsifiers

### FX-001 — qualified claim rendered unqualified

**Source semantic IDs and frame**

```text
status_id: limited
claim_strength: qualified
allowed_purpose: planning
condition: within_stated_interval
negative_assertion: not_confirmed
```

**English authored source**

> Status: limited. It may be used only for planning within the stated interval. It is not a confirmed result.

**Defective Ukrainian target (red)**

> Статус: підтверджено із застереженням. Результат можна використовувати для планування.

**Why it is defective**

- `limited` is upgraded to “confirmed with a caveat”;
- the interval condition is removed;
- the explicit non-confirmation is removed;
- the target licenses planning outside the source condition.

**Required red assertion**

```text
Allowed(target, planning_outside_interval) != Allowed(source, planning_outside_interval)
status_id(target) != limited
qualifier_preservation = false
expected_result = fail
```

**Corrected Ukrainian target candidate (green subject to review)**

> Статус: обмежений. Результат дозволено використовувати лише для планування в межах зазначеного інтервалу. Це не підтверджений результат.

The exact Ukrainian wording remains subject to glossary and qualified review; the fixture's oracle is the semantic frame, not this candidate string.

### FX-002 — prohibition rendered as advice

**Source frame**

```text
modality_id: prohibited
restriction_id: may_not_use_for
prohibited_purpose: authorize_payment
```

**English authored source**

> This evidence may not be used to authorise payment.

**Defective Ukrainian target (red)**

> Ці докази не рекомендується використовувати для погодження виплати.

**Why it is defective**

“Not recommended” permits an override based on preference; the source prohibits the use. It may also change the governed act from authorisation to a looser notion of agreement.

**Required red assertion**

```text
Forbidden(source, authorize_payment) = true
Forbidden(target, authorize_payment) = false
modal_class(source) = prohibition
modal_class(target) = recommendation
expected_result = fail
```

**Corrected Ukrainian target candidate (green subject to review)**

> Ці докази заборонено використовувати для надання дозволу на виплату.

The act-type designation must bind the registered/jurisdiction concept intended by `authorise payment`; lexical fluency alone does not settle it.

### FX-003 — distinct negative states collapsed

**Source IDs**

```text
stale
superseded
withdrawn
```

**Defective Ukrainian target (red)**

All three states render as:

> Недійсне

**Why it is defective**

The operator cannot tell whether to refresh evidence, follow a successor link, or stop because the responsible authority withdrew the item. The machine projection also loses identity.

**Required red assertions**

```text
rendered_id_count = 1
source_id_count = 3
remedy_profile(stale) != remedy_profile(superseded)
remedy_profile(superseded) != remedy_profile(withdrawn)
expected_result = fail
```

**Corrected rendering pattern (green subject to glossary)**

- `stale`: wording that states the freshness condition failed and revalidation/reacquisition is required;
- `superseded`: wording that names or links the replacing version;
- `withdrawn`: wording that states the responsible authority removed the item/claim from current use.

A short label may accompany the explanation, but the three semantic IDs and action profiles remain distinct in UI, accessibility text, MACHINE twin, and Lex projection.

## Required regression fixture matrix

| ID | dimension | red mutation | semantic oracle | green requirement |
|---|---|---|---|---|
| FX-004 | negation scope | `Not all evidence is admissible` becomes `No evidence is admissible` | quantify admissible subset | preserve `not all` rather than universal prohibition |
| FX-005 | actor scope | obligation on approving body becomes obligation on proposer | actor ID and role | same duty-bearer in source and target |
| FX-006 | exception | `only if approved, except during declared emergency` becomes unconditional emergency exception | condition/exception tree | preserve nesting and emergency predicate |
| FX-007 | exception-to-exception | proviso attached to exception moves to main rule | syntax tree plus counterexamples | same rule applies in each boundary context |
| FX-008 | temporal start | `after publication` becomes `on publication` | event boundary | no action licensed before source boundary |
| FX-009 | temporal end | `until 30 June inclusive` becomes end-exclusive | inclusive-bound flag | same last valid instant |
| FX-010 | duration | `within 10 working days` becomes calendar days | calendar ID and duration | preserve calendar basis and count rule |
| FX-011 | lower bound | `at least 0.20` becomes `more than 0.20` | closed/open interval | equality boundary preserved |
| FX-012 | upper bound | `no more than 40%` becomes `less than 40%` | closed/open interval | equality boundary preserved |
| FX-013 | interval | `[0.20, 0.40]` becomes point `0.30` | value kind | set/interval remains set/interval |
| FX-014 | uncertainty | `unknown` becomes zero | value kind and epistemic state | unknown remains neither zero nor missing |
| FX-015 | missingness | `not reported` becomes `not applicable` | missing-reason ID | reason identity preserved |
| FX-016 | evidence standing | `not established` becomes `false` | entailment relation | lack of proof is not disproof |
| FX-017 | modality | `may` permission becomes capability | permission/action profile | same legal licence, not ability claim |
| FX-018 | modality | `should` recommendation becomes obligation | modal class | no stronger duty in target |
| FX-019 | use restriction | one prohibited purpose omitted from a list | purpose IDs | all restrictions retained |
| FX-020 | conjunction | `A and B` becomes `A or B` | Boolean frame | same condition combination |
| FX-021 | disjunction | inclusive `or` becomes exclusive | truth table | same accepted contexts |
| FX-022 | Ukrainian case government | interpolated object takes nominative/default form after governing preposition | grammatical-role fixture | complete grammatical pattern or typed inflection |
| FX-023 | numeral morphology | English plural placeholder maps one Ukrainian form to all counts | CLDR/message variants plus human review | locale-correct forms without changing numeric value |
| FX-024 | fragment scope | qualifier in a separate fragment visually attaches to the wrong claim | proposition tree and accessible reading order | qualifier programmatically bound to governed claim |
| FX-025 | plain-language adaptation | `must not` becomes `try not to` | adaptation action profile | readability gain without prohibition loss |
| FX-026 | summary omission | exception is hidden from summary used for action | purpose profile | summary cannot be certified for action or must retain exception |
| FX-027 | co-authentic divergence | English member is silently treated as source over French member | authority-text-set mode | record divergence; no source promotion |
| FX-028 | English pivot | local concept is mapped through a broader English gloss and back | mapping relation | preserve local ID and mark mapping `broader/overlap/no_exact` |
| FX-029 | MACHINE twin | projection emits translated status label without semantic ID | schema invariant | reject label-only projection |
| FX-030 | Lex projection | different negative IDs normalise to one token | ID cardinality | preserve all registered IDs and provenance |
| FX-031 | RTL mixed text | citation/number reorders around Arabic source span | bidi-isolation oracle | logical and visual order both tested |
| FX-032 | script confusable | mixed-script identifier appears identical | confusable policy | visible warning/refusal according to admission rule |
| FX-033 | certificate purpose | display-only certificate reused for authorisation | purpose ID | runtime refuses purpose mismatch |
| FX-034 | certificate freshness | source amended after certificate issue | source digest/version | previous certificate retained but current use blocked |
| FX-035 | vacant role | contested high-stakes target has zero eligible adjudicators | required-role cardinality | typed refusal names role; no exception/crash/silent pass |

## Fixture manifest

Each implementation fixture stores:

```text
fixture_id
source_text
source_language
source_authority_anchor
source_semantic_frame
source_semantic_ids[]
defective_target
corrected_target_candidate
target_language / script
transformation_kind
purpose
old_mechanism_expected_result
maep_expected_result
expected_reason_id
counterexample_contexts[]
registered_vocabulary_versions[]
glossary_version
accessibility_expectation
machine_projection_expectation
```

The defective target and corrected candidate are test data, not production wording. Human approval of one fixture cannot be reused for another proposition without a certificate link.

## Phased deployment

### Phase 0 — repository research and demonstrable mechanics, zero appointed holders

Available immediately:

- D4-A1 UI posture remains `en` authored / `uk` translated / `ru` frozen;
- Ukrainian authoritative source content can be represented independently of UI locale;
- informative English renditions can be displayed with status and source provenance;
- canonical semantic IDs, semantic frames, glossary drafts, mappings, and fixture manifests can be represented;
- automated parity, ID, glossary, numeric, scope-heuristic, projection, and bidi checks can run;
- low-risk copy can follow its declared review path;
- high-stakes contested copy requiring an unfilled role returns a typed refusal;
- all vacancy and unresolved-equivalence states remain visible.

Unavailable by design:

- high-stakes adjudication attributed to a fictitious commission, board, sworn translator, or panel;
- promotion of an informative rendition to authentic status;
- full RTL product UI;
- certificate issuance where a declared required holder is absent.

### Phase 1 — first real-user deployment without institutional fiction

Evidence added, model unchanged:

- named real propositions and operator purposes;
- Ukrainian terminology and behavioural fixtures;
- measured comprehension and failure data;
- actual glossary release candidates;
- explicit role demand generated by observed contested cases;
- source-content/UI-locale decoupling verification.

The absence of appointed holders remains a measured operational gap. It does not block source viewing, test execution, or low-risk functionality.

### Phase 2 — appoint holders when justified

An appointment record supplies holder identity, competence evidence, jurisdiction/purpose scope, conflicts, valid interval, and delegation. Existing `required_role_id` records resolve to an eligible holder. The same MAEP evaluation that formerly returned `required_decision_holder_absent` can now reach a decision. No schema, semantic ID, fixture, or certificate shape changes.

### Phase N+1 — admit a jurisdiction without model change

Add records, not columns or branches:

1. jurisdiction identity and effective interval;
2. named source languages, BCP 47 tags, scripts, and directions;
3. authority-text-set relationship modes supported by that jurisdiction;
4. authoritative publishers and authenticity evidence;
5. interpretation/reconciliation rule for multiple texts;
6. jurisdiction concept namespace and initial mappings;
7. source-content rendition statuses and permitted purposes;
8. glossary evidence and contested-term process;
9. required roles, possibly with zero holders;
10. direction/script technical evidence, including RTL pack if applicable;
11. red-first fixtures from real instruments;
12. admission decision and review trigger.

A jurisdiction with several co-authentic languages creates one authority-text set with several members. A named RTL source adds an admitted script/direction capability. Neither action adds a new semantic field. Adding a public UI locale remains governed separately by D4-A1.

## Why the model works with zero holders

The protocol separates three things that systems often collapse:

- the **role definition** needed for a class of decision;
- the **holder appointment** that makes a particular actor eligible;
- the **decision record** produced for a subject.

Cardinality zero is valid for the second relation. Evaluation can therefore calculate precisely what is missing. The result is neither a thrown error nor a permissive default. Appointment later changes data only.

Example transition:

```text
T0: required_role(high_stakes_language_adjudicator)
    eligible_holders = []
    result = refuse(required_decision_holder_absent)

T1: appointment(holder_H, role, scope, valid_interval)
    eligible_holders = [H]
    result = pending_decision

T2: decision(H, subject, evidence, outcome)
    result = certificate_or_typed_failure
```

## Operational closure addendum

### Operational owner

The architecture does not appoint an owner. Implementation must name the repository/runtime owner for semantic vocabulary, jurisdiction admission records, source acquisition, glossary release, certificate validation, and role appointment separately. A single implicit “translation owner” is insufficient.

### Inputs

- D4-A1 UI capability record;
- jurisdiction admission record;
- authority-text set and immutable source members;
- canonical semantic frame and registered IDs;
- target rendition/variant;
- controlled-glossary release;
- purpose and risk class;
- automated and human evidence;
- role/appointment state.

### Outputs

- purpose-bounded equivalence certificate;
- typed semantic failure;
- typed refusal with missing evidence/role/authority anchor;
- divergence record for co-authentic texts;
- routed vocabulary or architect gap.

### Entry conditions

- subject classified;
- source authority evidence present;
- requested purpose declared;
- vocabulary versions resolvable;
- source and target digests stable;
- jurisdiction admission active.

### Exit conditions

A pass exits only with all mandatory automated checks, counterexamples, status-upgrade gate, separate adaptation result where applicable, and required adjudication. A refusal exits with exact missing object/role/evidence and resolution path. No unresolved branch returns success.

### Refusal behaviour

Refusal is fail-closed for the governed purpose and fail-open only for explicitly listed unblocked functions such as source viewing or draft comparison. UI labels, MACHINE twins, and Lex projections carry the same reason ID and blocked purpose.

### Freshness and invalidation

Certificates bind versions and validity. Amendment, withdrawal, supersession, glossary/vocabulary incompatibility, new failing fixture, expired admission evidence, or changed adjudication invalidates current use while preserving history.

### Observability

Record:

- evaluation and certificate IDs;
- source/rendition/version digests;
- purpose and jurisdiction;
- automated check outcomes;
- fixture IDs and counterexamples;
- required/selected role and appointment;
- refusal reason and unblocked functions;
- invalidation event and successor.

Audit evidence observes a pre-action decision; it does not retroactively create authority.

### Rollback

Rollback means selecting a prior valid glossary/protocol/rendition release only when its source, admission, and certificate remain valid. It cannot reactivate withdrawn legal source content, ignore a superseding authentic text, or restore a certificate invalidated by a material semantic defect.

### Security and privacy

Appointment/conflict evidence may contain personal data and requires governed access. Source and certificate integrity require immutable digests/signatures. Mixed-script and bidi controls are security inputs. Logs must not expose protected source content beyond purpose.

### Failure containment

A failed rendition, locale, jurisdiction admission, or role appointment is quarantined at its typed boundary. It does not disable unrelated UI locales or jurisdictions. Conversely, a functioning English UI cannot mask a failed Ukrainian legal rendition.

### Acceptance evidence

- all three binding falsifiers recorded red then green;
- complete regression matrix executed for each high-stakes message class;
- no business-logic string comparisons for governed semantics;
- source-content selection independent of UI locale;
- MACHINE/Lex round-trip with IDs and certificate provenance;
- zero-holder refusal exercised;
- Ukraine first-deployment fixture exercised;
- one synthetic co-authentic N+1 admission exercised without schema migration;
- one synthetic RTL source-content admission exercised without claiming RTL UI support;
- complete-tree baseline with denominators and coordinates closed.

## Classified findings

| ID | finding | classification |
|---|---|---|
| R-01 | the three mandatory falsifiers are action-profile failures invisible to key parity | `red_first_fixture` |
| R-02 | regression must cover proposition structure, not only terminology | `protocol_requirement` |
| R-03 | zero-holder operation is achieved by separating roles, appointments, and decisions | `phased_deployment_proof` |
| R-04 | jurisdiction N+1 is data-only when authority modes, scripts, concepts, roles, and evidence are records | `phased_deployment_proof` |
| R-05 | public RTL UI admission remains a D4-A1 event; RTL source rendering can be separately evidenced | `scope_boundary` |
| R-06 | operational closure requires purpose-scoped fail-closed behaviour and explicit unblocked functions | `protocol_requirement` |
