# MultilingualAuthorityEquivalenceProtocol

## Protocol purpose and current status

`MultilingualAuthorityEquivalenceProtocol` (MAEP) is a proposed research contract for evaluating
whether a particular rendition or presentation variant preserves the authority semantics required
for a declared purpose over a declared test population. It does not decide which text is legally
authoritative; that comes from the authority-text set and jurisdiction evidence. It does not amend
D4-A1, appoint institutional holders, register a new vocabulary, or create a second status lattice.

The current package is Markdown research. No MAEP producer, consumer, runtime gate, certificate
issuer, or appointed high-stakes holder is established. Consequently the capability remains
`absent/unallocated`.

A certificate, if later implemented and admitted, is bounded by:

- source authority anchor or co-authentic authority set;
- proposition/version and target rendition/variant digest;
- language and script;
- purpose and operator action;
- glossary and registered-vocabulary versions;
- protocol and fixture versions;
- the complete declared context/fixture population, its digest and cardinality;
- reviewer/adjudication basis;
- exclusions, unresolved context classes, and residual uncertainty;
- validity interval and invalidation triggers.

There is no repository-wide boolean “the Ukrainian catalogue is equivalent”.

## Non-negotiable invariants

1. **IDs precede labels.** Logic, certificates, MACHINE twins, Lex projections, and regression
   fixtures bind canonical semantic IDs and logical roles, never locale strings.
2. **Authority is anchored.** Every high-stakes proposition points to an authority-text member/set
   and immutable version/digest.
3. **UI locale is a non-authoritative selector.** `locale_preference` may select product UI strings
   only; it cannot select source authority or status.
4. **No mandatory English legal pivot.** Jurisdiction concepts may remain anchored in their authentic
   language(s); mappings to English are explicit assertions.
5. **No semantic upgrade, softening, or collapse.** A target cannot broaden permission, narrow
   prohibition, remove a qualifier, strengthen evidence, or merge distinct blocking states.
6. **Translation and adaptation are separate transformations.** Each has a separate result and
   provenance chain.
7. **Whole propositions govern.** Catalogue parity, glossary hits, and fragment correctness cannot
   issue a certificate.
8. **Co-authentic texts remain co-authentic.** Divergence is recorded and handled by the
   jurisdiction's rule; no member is silently designated source.
9. **Vacant roles are representable.** The target contract has a typed, purpose-scoped refusal for a
   required but unfilled adjudication role; this research does not claim a current producer.
10. **Certificates expire and revoke.** Source, glossary, vocabulary, rendition, evidence,
    population, and competent-decision changes can invalidate prior results.
11. **A passing finite population is not universal proof.** One counterexample refutes the candidate
    for the purpose; no counterexample within the declared denominator establishes only that bounded
    result.
12. **History is append-only.** Invalidation changes current usability but does not rewrite the prior
    certificate or source/rendition history.

## Protocol objects

### Canonical proposition record

```text
CanonicalProposition
  proposition_id
  namespace
  source_anchor_id / authority_text_set_id
  source_span
  source_digest
  language_tag
  script
  actor_ids[]
  act_type_id
  object_ids[]
  modality_id
  conditions[]
  exceptions[]
  quantifiers[]
  temporal_scope
  spatial_scope
  numeric_constraints[]
  evidence_qualifiers[]
  status_ids[]
  consequence_ids[]
  purpose_profile
  version
```

The record does not claim that natural-language meaning can be exhaustively reduced to fields. It
creates an auditable oracle for the operative dimensions selected for testing and makes unmodeled
residuals visible.

### Rendition record

```text
Rendition
  rendition_id
  proposition_id / authority_text_set_id
  rendition_relation_id
  language_tag
  script
  text
  digest
  producer_type
  method
  glossary_version
  created_at
  supersedes
  claimed_purposes[]
```

Candidate relation values may distinguish authentic text, official non-authentic translation,
approved/certified translation, commissioned translation, draft, machine-assisted draft,
transliteration, and informative rendering. The strings in this research are not registered values.
Each must map to an existing canonical owner or remain explicitly unallocated until registration.

### Presentation-variant record

```text
PresentationVariant
  variant_id
  parent_proposition_id
  parent_proposition_version
  parent_rendition_id?
  transformation_chain[]
  variant_kind
  audience
  purpose
  text
  digest
  adaptation_method
  readability_evidence
  semantic_review
  behavioural_evidence
```

A target-language plain version can point to a reviewed translation as its parent while retaining the
canonical source chain. The graph must reveal both transformations. `PresentationVariant` is a
dependent layer, not a fifth independent authority source.

### Test-population record

```text
SemanticTestPopulation
  population_id
  population_version
  subject_proposition_id
  purpose_id
  context_schema_version
  contexts[]
  fixture_ids[]
  included_context_classes[]
  excluded_context_classes[]
  unresolved_context_classes[]
  population_digest
  context_count
  fixture_count
  derivation_method
  reviewer_basis
```

No positive certificate may omit this record or substitute a sample description for the complete
versioned denominator.

## MAEP stages

### MAEP-0 — classify the object and transformation

Before comparing strings, classify the subject:

- product UI message;
- system-governance term;
- jurisdictional authoritative text;
- rendition of source content;
- MACHINE twin or Lex projection;
- plain-language/accessibility adaptation.

Classify the transformation:

- authored UI translation (`en -> uk` under D4-A1);
- source-content translation;
- co-authentic comparison;
- transliteration;
- same-language adaptation;
- cross-language adaptation with two-step provenance.

An ambiguous classification refuses because the wrong authority and tests would otherwise apply.

### MAEP-1 — bind source authority

For `single_designated`, bind authoritative text member, source span, publication/version, digest,
jurisdiction, effective interval, and evidence establishing its status.

For a co-authentic relation, bind the full authority-text set, every required member, the
instrument-specific equality rule, and the competent reconciliation process. Do not manufacture a
synthetic `source_language`.

For system UI, bind the D4-A1 authored English catalogue version and the system semantic IDs used by
the message.

Failure modes include unidentified source, ambiguous version, unsupported authority status, missing
required co-authentic member, or an effective interval that excludes the use. Each is a typed target
result whose exact reason must come from an existing owner or remain an explicit vocabulary gap.

### MAEP-2 — normalise the authority-semantic frame

Extract and review:

- who may, must, or may not act;
- act type and object;
- conditions and preconditions;
- exceptions and nested exceptions;
- negation and quantifier scope;
- temporal start, end, duration, and event anchors;
- territorial/institutional scope;
- evidence and uncertainty qualifiers;
- numeric bounds, units, inclusivity, tolerances, and unknown states;
- consequence, remedy, escalation, and abstention path.

The frame is versioned evidence. Ambiguity affecting operator action is retained as an ambiguity set,
not resolved by fluent wording or by the same unchecked process that produced the target.

### MAEP-3 — bind canonical semantic IDs

Every governed status, refusal, act type, authority ceiling, evidence standing, and purpose binds an
ID from the applicable registered owner. Jurisdictional concepts use jurisdiction-scoped IDs.
Cross-namespace mappings are explicit versioned records.

Business logic may not:

- compare labels;
- infer status from translated prose;
- use English term equality as concept equality;
- round-trip a translated label into an ID;
- create locale-specific branches for semantic decisions.

If an existing ID cannot represent a required concept, MAEP records a vocabulary gap and its
unallocated owner state; it does not mint a near-duplicate.

### MAEP-4 — apply the versioned controlled glossary

The glossary release is immutable and versioned. Each entry includes namespace, definition, source,
target designation, term status, forbidden synonyms, usage constraints, confusables, grammatical
notes, examples, and effective interval.

Checks include:

- required term present where the concept appears;
- forbidden/upgrading synonym absent;
- one target term not bound to several materially different IDs without disambiguation;
- deprecated designation not used in new high-stakes copy;
- jurisdiction and purpose scope match;
- inflected form traceable to the entry;
- glossary and registered-vocabulary versions compatible.

A glossary pass is necessary but cannot decide proposition equivalence.

### MAEP-5 — produce the rendition as a proposition

High-stakes copy is translated as a whole proposition or typed message function. Arbitrary
concatenation is non-certifiable.

```text
message_id
semantic_frame_id
variables:
  - id
    semantic_role
    concept_id
    value_type
    grammatical_features
    allowed_renderings
full_locale_patterns
```

For Ukrainian, patterns account for case government, number forms, agreement, animacy where
relevant, aspect, prepositions, and word-order effects on negation/information scope. Complete
locale-specific variants are allowed. English-order fragment splicing cannot be accepted merely
because paths and placeholders match.

Placeholders representing statuses or refusal reasons carry IDs; local labels cannot alter the
containing proposition's role.

### MAEP-6 — execute automated checks

Automated checks are red-first and include:

- catalogue path and placeholder parity;
- source/target placeholder identity and type;
- canonical ID presence;
- glossary required/forbidden terms;
- negation markers and dependency-scope heuristics;
- modal-class comparison;
- condition/exception marker comparison;
- temporal expression and boundary comparison;
- number, unit, sign, interval, inequality, and decimal comparison;
- uncertainty qualifier preservation;
- distinct status-ID preservation;
- bidi isolation and script integrity where applicable;
- source/rendition/projection digest consistency;
- no raw-label comparison in MACHINE/Lex consumers.

Automated checks may refute or escalate. They do not prove high-stakes equivalence by aggregate score.
Any automated-only disposition for a low-risk class must still name its complete declared population
and residual.

### MAEP-7 — test entailment, scope, and action profiles

First freeze `SemanticTestPopulation C_test`. Its declared contexts include boundary and
counterexample cases. For designated source `s` and target `t`, evaluate:

```text
for every c in C_test:
    Allowed(s,c), Required(s,c), Forbidden(s,c)
    Allowed(t,c), Required(t,c), Forbidden(t,c)
```

At minimum the population changes one dimension at a time:

- condition true/false/unknown;
- exception present/absent;
- actor inside/outside class;
- time before/on/after boundary;
- number below/on/above threshold;
- evidence fresh/stale/superseded/withdrawn;
- uncertainty known/unknown/interval;
- purpose permitted/prohibited.

A single target-only licensed action, source-only required action, or lost prohibition refutes the
candidate for that purpose. If no difference is found, the result is only “no prohibited difference
found over `C_test` under these versions.” Excluded and unresolved context classes remain residuals.

For co-authentic texts, comparison records aligned meaning and divergence; it does not declare one
member wrong because it differs from English. Material divergence invokes the admitted jurisdictional
rule or competent role.

### MAEP-8 — enforce the status-upgrade ban

The hard gate is broader than lexical strength. A target fails when it:

- removes `limited`, its condition, domain, time bound, or consequence;
- turns `may_not_use_for` into preference, caution, or recommendation;
- maps `stale`, `superseded`, and `withdrawn` to one displayed or machine state;
- changes `unknown` to zero, false, absent, or not applicable;
- converts an interval/set into a point estimate;
- turns `not established` into `disproved`, or the reverse;
- changes who bears the obligation or may invoke an exception;
- suppresses escalation or abstention required by the source.

The gate compares operator-action profiles associated with registered IDs. It does not invent a
second ordinal lattice. Incomparable states remain incomparable.

### MAEP-9 — assess plain-language adaptation separately

```text
translation_semantics
translation_language_quality
adaptation_semantics
adaptation_readability
behavioural_comprehension
```

A faithful but difficult translation may pass translation semantics and fail readability. A readable
simplification may pass readability and fail adaptation semantics. No aggregate “quality” value may
hide the failing dimension.

Adaptation checks include:

- every operative condition, exception, prohibition, and qualifier retained or linked;
- examples cannot be mistaken for exhaustive rules;
- headings/progressive disclosure do not detach riders from numbers/statuses;
- synonyms map to the same semantic IDs;
- behavioural fixtures measure correct action, not preference;
- canonical wording remains reachable for the governed purpose.

### MAEP-10 — apply the risk and adjudication table

Risk is declared before reviewing a specific rendition. It rises when copy controls authority,
prohibits action, reports evidence standing, exposes uncertainty, changes an authority ceiling, or is
consumed without source text.

| class | examples | minimum proposed disposition |
|---|---|---|
| `low` | non-operative navigation, decorative copy | automated checks plus ordinary language review |
| `medium` | explanatory UI influencing workflow but not licensing action | independent semantic review and complete regression population |
| `high` | permission/prohibition, authority, refusal, standing, deadline, evidence-use restriction, co-authentic divergence | named qualified role plus independent evidence |

Role definitions may exist with zero appointments. If a high-risk item requires
`high_stakes_language_adjudicator` and no eligible holder is appointed, the target contract returns:

```text
subject_id
required_role_id
eligible_holder_count: 0
reason_id: <mapped existing refusal or explicit vocabulary gap>
blocked_purpose
separately_established_unblocked_functions[]
resolution_requirements[]
```

The structure is normative research input; the example does not register a token or claim a current
runtime result. The producer cannot be sole high-stakes adjudicator of its own rendition; a conflicted
reviewer cannot silently waive the role; an adjudicator cannot redefine source authority.

### MAEP-11 — issue a population-bounded certificate

A successful later decision would issue:

```text
MultilingualAuthorityEquivalenceCertificate
  certificate_id
  protocol_version
  subject_kind
  proposition_id
  source_anchor_ids[]
  source_digests[]
  authority_text_set_relation
  rendition_or_variant_id
  rendition_digest
  language_tag / script / direction
  purpose_ids[]
  semantic_frame_version
  semantic_ids[]
  glossary_version
  registered_vocabulary_versions[]
  test_population_id
  test_population_version
  test_population_digest
  context_count
  fixture_count
  included_context_classes[]
  excluded_context_classes[]
  unresolved_context_classes[]
  automated_check_evidence[]
  counterexample_fixture_results[]
  translation_result
  adaptation_result
  reviewer_basis[]
  adjudication_decision_id?
  adjudication_role_id?
  residual_statement
  issued_at
  valid_from / valid_until
  invalidation_triggers[]
  supersedes
```

The certificate means: no prohibited difference was found for the exact proposition, purpose,
versions, and complete declared population, subject to the stated exclusions and residual. It does
not mean the texts are identical, universally equivalent, or legally co-authentic. A display-only
certificate cannot authorise machine execution; a source-content certificate does not certify the
product UI catalogue.

### MAEP-12 — enforce in runtime and projections

A future runtime contract would separate:

```text
ui_locale
jurisdiction_id
authority_text_set_id
selected_source_member_ids[]
content_rendition_id
presentation_variant_id
semantic_namespace_versions[]
equivalence_certificate_id
purpose_id
```

`ui_locale` is validated under D4-A1. Source selection is separately validated against jurisdiction
and authority-set records. The certificate is validated for subject, digest, purpose, time,
population, residual policy, and vocabulary versions.

MACHINE twins and Lex projections carry IDs, source anchors, reason IDs, numeric structures,
population/residual fields, and certificate references. Human labels are projections. A machine
consumer refuses when only a label is supplied; an ID is unknown/version-incompatible; purpose is
prohibited; the certificate is absent/expired/revoked/mismatched; states were flattened; or source and
projection disagree.

### MAEP-13 — invalidate, revoke, and re-evaluate

A certificate becomes unusable when a declared trigger fires, including:

- source amended, corrected, repealed, superseded, or withdrawn;
- source digest/span changes;
- authority-set membership/status changes;
- rendition/variant changes;
- semantic vocabulary changes incompatibly;
- glossary entry changes materially;
- admission evidence expires or is withdrawn;
- adjudication decision is reversed, expires, or is conflicted;
- a new failing fixture exposes a prior false pass;
- purpose/context exceeds scope;
- declared test population or residual policy changes.

The old certificate and reasoned history remain. Current usability changes through a typed owner
state; invalidation is not rewritten as generic `stale`.

## Decision logic

Illustrative pseudocode:

```text
function evaluate_maep(subject, target, purpose, population, context):
    classification = classify(subject, target)
    if classification is ambiguous:
        return refuse(mapped_reason_or_gap('object_classification_unresolved'))

    authority = resolve_authority_anchor(subject, context.jurisdiction)
    if authority is not established:
        return refuse(mapped_reason_or_gap('authority_anchor_unestablished'))

    frame = bind_semantic_frame(subject, authority)
    ids = bind_registered_ids(frame)
    if ids.has_unregistered_required_concept:
        return refuse(vocabulary_gap(ids.unregistered_concepts))

    frozen_population = validate_complete_population(population, subject, purpose, frame)
    if frozen_population is invalid:
        return refuse(mapped_reason_or_gap('test_population_invalid'))

    glossary = select_glossary(ids, target.language, context.jurisdiction, purpose)
    automated = run_automated_checks(subject, target, frame, ids, glossary)
    if automated.material_failure:
        return fail(automated.reason_id)

    comparison = compare_action_profiles(
        subject, target, frame, purpose, frozen_population.contexts
    )
    if comparison.material_difference:
        return fail(mapped_reason_or_gap('authority_semantics_not_preserved'))

    if status_upgrade_detected(subject, target, ids):
        return fail(mapped_reason_or_gap('semantic_status_upgrade'))

    adaptation = evaluate_adaptation_separately_if_present(target, frame, purpose)
    if adaptation.material_failure:
        return fail(adaptation.reason_id)

    requirement = risk_table.requirement(subject, purpose)
    holder = eligible_holder(requirement.role, context)
    if requirement.needs_human and holder is none:
        return refuse(
            reason_id = mapped_reason_or_gap('required_decision_holder_absent'),
            required_role_id = requirement.role,
            eligible_holder_count = 0
        )

    decision = adjudicate_if_required(holder, evidence_bundle)
    if decision is contested_or_negative:
        return decision.as_typed_result()

    return issue_population_bounded_certificate(
        evidence_bundle,
        decision,
        frozen_population,
        exclusions = frozen_population.exclusions,
        residual = derive_residual(frozen_population, evidence_bundle)
    )
```

`mapped_reason_or_gap(...)` means reuse an existing registered reason when available; otherwise
record an explicit vocabulary gap and owner-unallocated state. The pseudocode registers nothing.

## Controlled glossary lifecycle

1. Draft entry binds a concept ID and source definition.
2. Language designation is proposed with context and negative examples.
3. Automated collision/confusable checks run.
4. Required review is determined by risk, not language alone.
5. With no required holder, high-stakes approval remains blocked.
6. An approved release is immutable and versioned.
7. Deprecation preserves history and successor links.
8. Certificate invalidation is evaluated when an entry changes.

The target model represents draft entries, checks, fixtures, and purpose-scoped blocking with zero
holders. This package does not claim that those functions are currently implemented or available.

## Interface requirements

A future high-stakes surface exposes or makes reachable:

- semantic status/reason identity;
- source authority and version;
- rendition relation and language;
- certificate purpose, tested population, residual, and validity;
- qualifications, conditions, and prohibited uses;
- whether wording is canonical, translated, or adapted;
- source text or durable route;
- contested/missing-role state and resolution requirement.

Visual adjacency alone is insufficient for assistive technology. Reading order must bind qualifiers
and reasons to the governed claim.

## Security and abuse considerations

- Do not permit locale strings to select executable semantics.
- Treat mixed-script confusables and bidi controls as security-sensitive.
- Digest source, rendition, glossary release, population, and certificate records.
- Log certificate use with purpose/versions without converting the log into post-hoc authority.
- Prevent producer self-approval for high-stakes copy.
- Preserve withdrawn/superseded renditions for audit while blocking current reliance.
- Do not allow informative translation to overwrite or masquerade as authentic text.

## Classified protocol findings

| ID | finding | classification |
|---|---|---|
| M-01 | equivalence is proposition-, purpose-, version-, and tested-population-bounded | `protocol_requirement` |
| M-02 | action-profile counterexamples are decisive falsifiers, not unrestricted positive proof | `protocol_requirement` |
| M-03 | canonical semantic IDs and logical roles precede rendering | `protocol_requirement` |
| M-04 | controlled glossary releases are evidence, not semantic authority by themselves | `external_evidence_supported_inference` |
| M-05 | high-stakes fragment concatenation is non-certifiable | `protocol_requirement` |
| M-06 | translation and adaptation require independent results | `protocol_requirement` |
| M-07 | co-authentic divergence requires jurisdiction-specific handling | `external_evidence_convergence` |
| M-08 | a vacant required role is representable as a target refusal, not a current capability | `phased_deployment_requirement` |
| M-09 | MACHINE/Lex projections reject label-only semantics and carry residuals | `protocol_requirement` |
| M-10 | certificates need explicit invalidation, population, residual, and revocation semantics | `protocol_requirement` |
