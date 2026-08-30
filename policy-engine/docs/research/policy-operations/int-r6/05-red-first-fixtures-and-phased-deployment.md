# INT-R6 red-first fixtures, phased deployment, and operational closure

## Fixture discipline

These fixtures are research specifications in Markdown, not implemented tests. Each fixture is
**red first**:

1. source and deliberately defective target have structurally matching catalogue paths/placeholders;
2. the pre-MAEP structural mechanism is expected to pass or be unable to distinguish them;
3. the semantic assertion is expected to fail;
4. after MAEP is implemented, the defective target must fail with a typed reason;
5. a corrected target may pass only for its exact proposition, purpose, versions, complete declared
   context population, and stated residual.

A green result without an observed red failure is not admissible evidence. Fixture evidence must name
executor, pinned baseline SHA, protocol version, source/target digests, catalogue/glossary/vocabulary
versions, the complete context/fixture denominator, exclusions, and exact result.

A counterexample is asymmetric evidence: one material difference refutes a candidate for the governed
purpose. Failure to find a difference in a finite suite does not prove unrestricted equivalence.

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

> Status: limited. It may be used only for planning within the stated interval. It is not a
> confirmed result.

**Defective Ukrainian target (red)**

> Статус: підтверджено із застереженням. Результат можна використовувати для планування.

**Why defective**

- `limited` is upgraded to “confirmed with a caveat”;
- the interval condition and explicit non-confirmation disappear;
- the target licenses planning outside the source condition.

**Required red assertion**

```text
Allowed(target, planning_outside_interval) != Allowed(source, planning_outside_interval)
status_id(target) != limited
qualifier_preservation = false
expected_result = fail
```

**Corrected Ukrainian candidate**

> Статус: обмежений. Результат дозволено використовувати лише для планування в межах зазначеного
> інтервалу. Це не підтверджений результат.

The string is test data, not approved production wording. A later positive result must bind the exact
registered status ID, glossary version, complete fixture population, reviewer basis, and residual.

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

“Not recommended” permits an override based on preference; the source prohibits the use. It may also
change the governed act from authorisation to a looser notion of agreement.

**Required red assertion**

```text
Forbidden(source, authorize_payment) = true
Forbidden(target, authorize_payment) = false
modal_class(source) = prohibition
modal_class(target) = recommendation
expected_result = fail
```

**Corrected Ukrainian candidate**

> Ці докази заборонено використовувати для надання дозволу на виплату.

The act-type designation must bind the intended registered/jurisdiction concept. Lexical fluency does
not settle it, and one reviewed candidate cannot certify another proposition.

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

The operator cannot tell whether to refresh evidence, follow a successor, or stop because the
responsible authority withdrew the item. A label-only machine projection loses the same distinction.

**Required red assertions**

```text
rendered_id_count = 1
source_id_count = 3
remedy_profile(stale) != remedy_profile(superseded)
remedy_profile(superseded) != remedy_profile(withdrawn)
expected_result = fail
```

**Corrected rendering pattern**

- `stale`: states that freshness failed and revalidation/reacquisition is required;
- `superseded`: identifies the replacing version or successor relation;
- `withdrawn`: states that the competent authority removed the item/claim from current use.

The short labels remain glossary candidates. IDs, provenance, and action profiles must stay distinct
in UI, accessibility text, MACHINE, and Lex.

## Required regression-fixture matrix

| ID | dimension | red mutation | semantic oracle | green requirement |
|---|---|---|---|---|
| FX-004 | negation scope | `Not all evidence is admissible` → `No evidence is admissible` | quantified admissible subset | preserve `not all` |
| FX-005 | actor scope | approving-body duty → proposer duty | actor/role ID | same duty-bearer |
| FX-006 | exception | conditional rule + emergency exception → unconditional exception | condition/exception tree | preserve nesting |
| FX-007 | exception-to-exception | proviso moves from exception to main rule | syntax tree + contexts | same rule in each context |
| FX-008 | temporal start | `after publication` → `on publication` | event boundary | no earlier licence |
| FX-009 | temporal end | inclusive date → exclusive | inclusive-bound flag | same last instant |
| FX-010 | duration | working days → calendar days | calendar ID/duration | preserve calendar basis |
| FX-011 | lower bound | `at least 0.20` → `more than 0.20` | closed/open interval | equality boundary preserved |
| FX-012 | upper bound | `no more than 40%` → `less than 40%` | closed/open interval | equality boundary preserved |
| FX-013 | interval | `[0.20,0.40]` → `0.30` | value kind | interval remains interval |
| FX-014 | uncertainty | `unknown` → zero | value kind/epistemic state | unknown is neither zero nor missing |
| FX-015 | missingness | `not reported` → `not applicable` | missing-reason ID | reason identity preserved |
| FX-016 | evidence standing | `not established` → `false` | entailment relation | lack of proof is not disproof |
| FX-017 | modality | permission `may` → capability | action profile | same licence |
| FX-018 | modality | recommendation `should` → obligation | modal class | no stronger duty |
| FX-019 | use restriction | one prohibited purpose omitted | purpose IDs | all restrictions retained |
| FX-020 | conjunction | `A and B` → `A or B` | Boolean frame | same accepted contexts |
| FX-021 | disjunction | inclusive `or` → exclusive | truth table | same accepted contexts |
| FX-022 | Ukrainian case | default nominative after governing preposition | grammatical role | complete pattern/typed inflection |
| FX-023 | numeral morphology | one form for all counts | CLDR/message variants + review | correct forms, same number |
| FX-024 | fragment scope | qualifier attaches to wrong claim | proposition tree + reading order | programmatic binding |
| FX-025 | adaptation | `must not` → `try not to` | adaptation action profile | prohibition retained |
| FX-026 | summary omission | action summary hides exception | purpose profile | retain exception or refuse action purpose |
| FX-027 | co-authentic divergence | English silently becomes source over French | authority-set relation | record divergence; no promotion |
| FX-028 | English pivot | local concept round-trips through broader English gloss | mapping relation | preserve local ID/relation |
| FX-029 | MACHINE | translated status label without ID | schema invariant | reject label-only projection |
| FX-030 | Lex | different negative IDs normalise to one token | ID cardinality | preserve IDs/provenance |
| FX-031 | RTL mixed text | citation/number reorders around Arabic span | bidi oracle | logical and visual order tested |
| FX-032 | confusable | mixed-script identifier appears identical | confusable policy | warning/refusal per admission rule |
| FX-033 | certificate purpose | display-only result reused for authorisation | purpose ID | refuse mismatch |
| FX-034 | certificate freshness | source changes after issue | source digest/version | retain history; block current use |
| FX-035 | vacant role | contested high-stakes target, zero eligible holders | role cardinality | purpose-scoped refusal names role |

## Fixture manifest and proof boundary

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
purpose_id
old_mechanism_expected_result
maep_expected_result
expected_reason_id_or_vocabulary_gap
counterexample_contexts[]
registered_vocabulary_versions[]
glossary_version
accessibility_expectation
machine_projection_expectation
```

Each test run additionally binds:

```text
test_population_id / version / digest
complete_context_count
complete_fixture_count
included_context_classes[]
excluded_context_classes[]
unresolved_context_classes[]
executor
pinned_code_and_data_shas[]
observed_red_result
observed_green_result
reviewer_basis[]
residual_statement
```

The defective target and corrected candidate are test data, not production wording. A human decision
on one fixture cannot be reused for another proposition without an exact certificate link. A finite
passing population licenses no claim outside its stated denominator.

## Phased deployment

### Phase 0 — research package, zero appointed holders

Established now:

- D4-A1 remains `en` authored / `uk` translated / `ru` frozen;
- the package specifies records capable of separating UI locale, authority texts, renditions,
  semantic IDs, and dependent variants;
- the package specifies semantic frames, glossary records, fixture manifests, and a purpose-scoped
  vacant-holder refusal;
- the three binding falsifiers are structurally parity-compatible research fixtures;
- current catalogue measurements and repository seams are recorded in the baseline appendix.

Not established now:

- a MAEP runtime producer, certificate issuer, or consuming gate;
- product surfaces displaying authority texts or informative renditions;
- automated MAEP checks executing in the repository;
- a canonical MAEP vocabulary owner or registered relation/result/reason values;
- a qualified adjudication holder or appointment;
- RTL source-content or product-UI capability.

The current package therefore remains `capability_standing: absent/unallocated`. The model identifies
source viewing, draft comparison, glossary work, and fixture authoring as functions that **could** be
separately admitted; it does not infer their current availability.

### Phase 1 — first real-user implementation without institutional fiction

A later implementation would need, without changing the core separation:

- named real propositions and governed purposes;
- Ukrainian terminology and behavioural fixtures;
- measured comprehension and failure data;
- actual glossary release candidates;
- observed role demand from contested cases;
- source-content/UI-locale decoupling verification;
- registered owner mappings for every relation/result/reason;
- complete population and residual evidence for each claimed certificate.

Institutional absence remains an explicit operational gap. It must neither silently pass a governed
purpose nor be converted into a global block on separately established functions.

### Phase 2 — appointments only through a competent later stage

An appointment record would supply holder identity, competence evidence, jurisdiction/purpose scope,
conflicts, valid interval, and delegation. Stage 3 creates no such appointment. The same target model
can represent zero or one/more eligible holders without changing semantic IDs or fixture shape, but a
real decision additionally requires the surrounding producer, evidence, and authority chain.

### Phase N+1 — bounded record admission

A jurisdiction may be admitted without schema change only when all required facts fit the already
admitted envelope:

1. jurisdiction identity and effective interval;
2. source languages, BCP 47 tags, scripts, and directions;
3. an already admitted authority-text relation;
4. authoritative publishers and authenticity evidence;
5. a jurisdiction-specific interpretation/reconciliation rule;
6. jurisdiction concept namespace and mappings;
7. rendition relations and permitted purposes mapped to canonical owners;
8. glossary evidence and contested-term process;
9. required roles, possibly with zero appointments;
10. direction/script evidence, including RTL pack if applicable;
11. red-first fixtures from real instruments;
12. competent admission decision and review trigger.

A new semantic relation, evidence predicate, or refusal concept is not “data-only”; it remains an
explicit unallocated governance/schema gap. Adding a public UI locale remains governed separately by
D4-A1.

## Why zero-holder state is representable

The model separates:

- **role definition** for a decision class;
- **holder appointment** making an actor eligible;
- **decision record** for a subject.

Cardinality zero is valid for the appointment relation. The target protocol can therefore identify
what is missing without an exception or permissive default:

```text
T0: required_role(high_stakes_language_adjudicator)
    eligible_holders = []
    target_result = refuse(required_role_absent_or_vocabulary_gap)

T1: competent_stage_records_appointment(holder_H, role, scope, interval)
    eligible_holders = [H]
    target_result = pending_decision

T2: competent_decision(H, subject, evidence, outcome)
    target_result = population_bounded_certificate_or_typed_failure
```

This is a record-model proof, not evidence that any current repository component executes the
transition.

## Operational closure addendum

### Ownership

Stage 3 appoints nobody. Every proposed capability or vocabulary object remains explicitly
`unallocated` unless an existing canonical owner is cited in the finding register. A generic lane is
never presented as an owner. Separate ownership is required for semantic vocabulary, jurisdiction
admission, source acquisition, glossary release, certificate validation, and appointments.

### Inputs

- D4-A1 UI capability record;
- jurisdiction admission record;
- authority-text set and immutable source members;
- canonical semantic frame and registered IDs;
- target rendition/variant;
- controlled-glossary release;
- purpose and risk class;
- complete test population, automated/human evidence, and residual;
- role/appointment state.

### Outputs

- population-bounded equivalence certificate;
- typed semantic failure;
- typed refusal with missing evidence/role/authority anchor;
- divergence record for co-authentic texts;
- explicit vocabulary/owner-unallocated gap.

The output names are contract categories; their exact status/reason values must come from existing
registered owners or remain gaps.

### Entry and exit conditions

Entry requires classified subject, established source authority, declared purpose, resolvable
vocabulary versions, stable source/target digests, active jurisdiction admission, and a complete
versioned test population.

A positive exit requires all mandatory checks, complete population execution, status gate, separate
adaptation result where applicable, required adjudication, exclusions, and residual. A refusal exits
with exact missing object/role/evidence and resolution requirement. No unresolved branch returns
success.

### Refusal behaviour

Refusal is fail-closed for the governed purpose. Any function described as unblocked must have a
separate established producer/authorization basis; the refusal itself does not create that function.
UI, MACHINE, and Lex must carry the same reason ID, blocked purpose, and residual when those consumers
are later implemented.

### Freshness, observability, rollback, and containment

Certificates bind source/rendition/population/vocabulary versions and validity. Amendment,
withdrawal, supersession, incompatible glossary/vocabulary change, a new failing fixture, expired
admission evidence, changed population, or reversed adjudication invalidates current use while
preserving history.

Observation records evaluation/certificate IDs, source/rendition digests, purpose/jurisdiction,
complete population denominator, check outcomes, counterexamples, exclusions/residual, required role
and appointment, refusal reason, separately established unblocked functions, invalidation, and
successor. Audit evidence observes a pre-action decision; it does not retroactively create authority.

Rollback may select a prior release only while its source, admission, population, and certificate
remain valid. It cannot reactivate withdrawn source content or ignore a superseding authentic text.

A failed rendition, locale, jurisdiction admission, or appointment is quarantined at its typed
boundary. It does not disable unrelated locales/jurisdictions; a functioning English UI cannot mask a
failed Ukrainian rendition.

### Acceptance evidence for a future implementation

- all three binding falsifiers observed red then green;
- complete versioned regression population executed for each high-stakes message class;
- certificate reports denominator, exclusions, unresolved contexts, and residual;
- no business-logic string comparison for governed semantics;
- source-content selection independent of UI locale;
- MACHINE/Lex round-trip with IDs and certificate provenance;
- zero-holder refusal exercised without inventing a holder;
- Ukraine architecture fixture bound to real implementation evidence;
- a co-authentic admission fitting the existing envelope exercised without schema migration;
- an RTL source-content admission evidenced without claiming RTL UI;
- complete-tree baseline with denominators/coordinates closed.

## Classified findings

| ID | finding | classification |
|---|---|---|
| R-01 | the three falsifiers are action-profile failures invisible to key parity | `red_first_fixture` |
| R-02 | regression covers proposition structure and publishes a complete bounded population | `protocol_requirement` |
| R-03 | zero holders are representable by separating role, appointment, and decision | `phased_deployment_proof` |
| R-04 | N+1 is data-only only inside an admitted relation/vocabulary envelope | `phased_deployment_proof` |
| R-05 | public RTL UI remains a D4-A1 event; RTL source rendering needs separate evidence | `scope_boundary` |
| R-06 | operational closure is purpose-scoped and cannot manufacture unblocked functions | `protocol_requirement` |
