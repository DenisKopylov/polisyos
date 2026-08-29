# MultilingualAuthorityEquivalenceProtocol

## Protocol purpose

`MultilingualAuthorityEquivalenceProtocol` (MAEP) determines whether a particular rendition or presentation variant preserves the authority semantics required for a declared purpose. It does not decide which text is legally authoritative; that comes from the applicable authority-text set and jurisdiction admission evidence. It does not amend D4-A1, appoint institutional holders, or create a second status lattice.

A certificate is always bounded by:

- source authority anchor or co-authentic authority set;
- proposition/version;
- target rendition/variant;
- language and script;
- purpose and operator action;
- glossary and registered-vocabulary versions;
- protocol and fixture versions;
- validity interval and invalidation triggers.

There is no repository-wide boolean “the Ukrainian catalogue is equivalent”.

## Non-negotiable invariants

1. **IDs precede labels.** Logic, certificates, MACHINE twins, Lex projections, and regression fixtures bind canonical semantic IDs and logical roles, never locale strings.
2. **Authority is anchored.** Every high-stakes proposition points to an authority-text member/set and immutable version/digest.
3. **UI locale is orthogonal.** `locale_preference` may select product UI strings only.
4. **No mandatory English legal pivot.** Jurisdiction concepts may remain anchored in their authentic language(s); mappings to English are explicit assertions.
5. **No semantic upgrade.** A target cannot broaden permission, narrow prohibition, remove a qualifier, strengthen evidence, or merge distinct blocking states.
6. **Translation and adaptation are separate transformations.** Each has a separate result and provenance chain.
7. **Whole propositions govern.** Catalogue parity, glossary hits, and fragment correctness cannot issue a certificate.
8. **Co-authentic texts remain co-authentic.** Divergence is recorded and handled by the jurisdiction's rule; no member is silently designated source.
9. **Vacant roles are representable.** A required but unfilled adjudication role yields a typed refusal naming the role.
10. **Certificates expire and revoke.** Source, glossary, vocabulary, rendition, evidence, and competent-decision changes can invalidate prior results.

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

The record does not claim that natural-language meaning can be exhaustively reduced to fields. It creates an auditable test oracle for the operative dimensions that must survive.

### Rendition record

```text
Rendition
  rendition_id
  proposition_id / authority_text_set_id
  rendition_kind
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

`rendition_kind` distinguishes at least authentic text, official non-authentic translation, certified translation, commissioned translation, draft, machine-assisted draft, transliteration, and informative rendering. Exact values require registry review.

### Adaptation record

```text
PresentationVariant
  variant_id
  parent_rendition_id
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

A target-language plain version can point to a certified translation as its parent while retaining the canonical source chain. The graph must reveal both transformations.

## MAEP stages

### MAEP-0 — classify the object and transformation

Before comparing strings, classify the subject:

- product UI string;
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

A misclassified object refuses because the wrong authority and tests would otherwise apply.

### MAEP-1 — bind source authority

For `single_designated`, record the authoritative text member, source span, publication/version, digest, jurisdiction, effective interval, and evidence that establishes its status.

For `multiple_coauthentic`, record the full authority-text set, each member, the instrument-specific equality rule, and the competent reconciliation process. Do not populate a synthetic `source_language`.

For system UI, bind the D4-A1 authored English catalogue version and the system semantic IDs used by the message.

Failure modes:

- source cannot be identified;
- version is ambiguous;
- claimed authority status lacks evidence;
- required co-authentic member is missing;
- effective interval does not cover the use.

Each is a typed refusal, not permission to compare whatever text is available.

### MAEP-2 — normalise the authority-semantic frame

Extract and review the operative frame:

- who may, must, or may not act;
- act type and object;
- conditions and preconditions;
- exceptions and exception-to-exception structure;
- negation and quantifier scope;
- temporal start, end, duration, and event anchors;
- territorial/institutional scope;
- evidence and uncertainty qualifiers;
- numeric bounds, units, inclusivity, tolerances, and unknown states;
- consequence, remedy, escalation, and abstention path.

The frame is versioned evidence. It is not generated and accepted by the same unchecked process. Ambiguity that affects operator action is carried forward as an ambiguity set, not resolved by fluent translation.

### MAEP-3 — bind canonical semantic IDs

Every governed status, refusal, act type, authority ceiling, evidence standing, and purpose binds an ID from the applicable registered vocabulary. Jurisdictional concepts use jurisdiction-scoped IDs. Cross-namespace mappings are explicit records with relation and evidence.

A renderer receives IDs plus language/context and returns labels. Business logic may not:

- compare labels;
- infer status from translated prose;
- use English term equality as concept equality;
- round-trip a translated label into an ID;
- create locale-specific branches for semantic decisions.

If an existing registered ID cannot represent the concept, MAEP records a vocabulary gap and routes it; it does not mint an unreviewed near-duplicate.

### MAEP-4 — apply the versioned controlled glossary

The glossary release is immutable and versioned. Each entry includes namespace, concept definition, source, target designation, term status, forbidden synonyms, usage constraints, confusables, grammatical notes, examples, and effective interval.

Checks include:

- required term present where the concept appears;
- forbidden/upgrading synonym absent;
- one target term not bound to several materially different IDs without disambiguation;
- deprecated designation not used in new high-stakes copy;
- jurisdiction and purpose scope match;
- inflected form remains traceable to the glossary entry;
- glossary version is compatible with the registered vocabulary version.

A glossary pass is necessary but cannot decide proposition equivalence.

### MAEP-5 — produce the rendition as a proposition

High-stakes copy is translated as a whole proposition or as a typed message function. Arbitrary concatenation is non-certifiable.

A typed message function declares semantic and grammatical roles for variables:

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

For Ukrainian, patterns must account for case government, number forms, agreement, animacy where relevant, aspect, prepositions, and word-order effects on information and negation scope. It is acceptable to supply complete locale-specific variants rather than implement runtime inflection. It is not acceptable to splice English-order fragments and call path parity a translation.

Placeholders representing statuses or refusal reasons carry IDs; their localised display strings cannot alter the containing proposition's logical role.

### MAEP-6 — execute automated checks

Automated checks are red-first and include:

- catalogue path and placeholder parity;
- source/target placeholder identity and type;
- canonical ID presence;
- glossary required/forbidden terms;
- negation markers and dependency scope heuristics;
- modal class comparison;
- condition/exception marker comparison;
- temporal expression and boundary comparison;
- number, unit, sign, interval, inequality, and decimal comparison;
- uncertainty qualifier preservation;
- distinct status-ID preservation;
- bidi isolation and script integrity where applicable;
- source/rendition/projection digest consistency;
- no raw label comparison in MACHINE/Lex consumers.

Automated checks may fail or escalate. They may not by themselves certify high-stakes equivalence unless the protocol's risk table explicitly allows automated-only disposition for that proposition class.

### MAEP-7 — test entailment, scope, and action profiles

Construct material contexts, including boundary and counterexample contexts. For a designated source `s` and rendition `t`, evaluate:

```text
Allowed(s,c), Required(s,c), Forbidden(s,c)
Allowed(t,c), Required(t,c), Forbidden(t,c)
```

A semantic pass requires equality for the declared purpose over the material context suite. At minimum, the suite changes one dimension at a time:

- condition true/false/unknown;
- exception present/absent;
- actor inside/outside class;
- time before/on/after boundary;
- number below/on/above threshold;
- evidence fresh/stale/superseded/withdrawn;
- uncertainty known/unknown/interval;
- purpose permitted/prohibited.

The reviewer records any target-only licensed action, source-only required action, or lost prohibition. A single material counterexample fails the rendition for that purpose.

For co-authentic texts, the comparison records aligned meaning and divergence; it does not declare one target wrong merely because it differs from an English wording. Material divergence invokes the admitted jurisdictional reconciliation rule or competent role.

### MAEP-8 — enforce the status-upgrade ban

The hard gate is broader than lexical strength. A target fails when it:

- removes `limited`, its condition, domain, time bound, or consequence;
- turns `may_not_use_for` into preference, caution, or non-binding recommendation;
- maps `stale`, `superseded`, and `withdrawn` to one displayed or machine state;
- changes `unknown` to zero, false, absent, or not applicable;
- converts an interval/set into a point estimate;
- turns `not established` into `disproved`, or the reverse;
- changes who bears the obligation or who may invoke an exception;
- suppresses escalation or abstention required by the source.

The gate compares operator-action profiles associated with registered IDs. It does not invent a second ordinal lattice. When statuses are incomparable, the system preserves incomparability rather than ranking by tone.

### MAEP-9 — assess plain-language adaptation separately

Translation result fields and adaptation result fields are distinct:

```text
translation_semantics
translation_language_quality
adaptation_semantics
adaptation_readability
behavioural_comprehension
```

A faithful but difficult translation may pass translation semantics and fail adaptation/readability. A readable simplification may pass readability and fail adaptation semantics. No aggregate “quality” value may hide the failing dimension.

Adaptation checks include:

- every operative condition, exception, prohibition, and qualifier retained or explicitly linked;
- examples cannot be mistaken for exhaustive rules;
- headings and progressive disclosure do not detach riders from numbers/statuses;
- synonyms map to the same semantic IDs;
- behavioural fixtures measure correct action, not preference;
- the canonical wording remains available for high-stakes reliance.

### MAEP-10 — apply the risk and adjudication table

The risk table is declared before reviewing the specific rendition. Risk rises when copy controls legal authority, prohibits action, reports evidence standing, exposes uncertainty, changes an authority ceiling, or is consumed without source text by a machine or operator.

Conceptual table:

| class | examples | minimum disposition |
|---|---|---|
| `low` | non-operative navigation, decorative copy | automated checks plus ordinary language review |
| `medium` | explanatory UI that may influence workflow but does not itself license action | independent semantic review and regression suite |
| `high` | permission/prohibition, authority, refusal, standing, legal deadline, evidence use restriction, co-authentic divergence | named qualified adjudication role plus independent evidence |

Role definitions may exist with zero holders. If a high-risk item requires `high_stakes_language_adjudicator` and no eligible holder is appointed, MAEP returns a refusal with:

```text
subject_id
required_role_id
holder_count: 0
reason: required_decision_holder_absent
blocked_purpose
unblocked_functions[]
resolution_requirements[]
```

The exact reason and status tokens must be taken from existing registered vocabularies or routed as gaps. The structure, not the example wording, is normative here.

Independence constraints are also explicit: the producer must not be the sole high-stakes adjudicator of their own rendition; a conflicted reviewer cannot silently waive the requirement; an adjudicator cannot redefine the authority-text set.

### MAEP-11 — issue a purpose-bounded certificate

A successful decision issues:

```text
MultilingualAuthorityEquivalenceCertificate
  certificate_id
  protocol_version
  subject_kind
  proposition_id
  source_anchor_ids[]
  source_digests[]
  authority_text_set_mode
  rendition_or_variant_id
  rendition_digest
  language_tag / script / direction
  purpose_ids[]
  semantic_frame_version
  semantic_ids[]
  glossary_version
  registered_vocabulary_versions[]
  automated_check_evidence[]
  counterexample_fixture_results[]
  translation_result
  adaptation_result
  adjudication_decision_id
  adjudication_role_id
  issued_at
  valid_from / valid_until
  invalidation_triggers[]
  supersedes
```

The certificate says “equivalent for these purposes under this evidence”, not “the texts are identical” and not “the target text is legally authentic”. A display-only certificate cannot authorise machine execution; a source-content translation certificate does not certify the product UI catalogue.

### MAEP-12 — enforce at runtime and in projections

Runtime requests carry separate fields:

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

`ui_locale` is validated under D4-A1. Source-content selection is validated against the jurisdiction admission record and authority-text set. The certificate is validated for subject, digest, purpose, time, and vocabulary versions.

MACHINE twins and Lex projections carry IDs, source anchors, status/reason IDs, numeric structures, and certificate references. Human labels are projections. A machine consumer must reject or refuse when:

- only a translated label is supplied;
- an ID is unknown or version-incompatible;
- a prohibited purpose is requested;
- a certificate is absent, expired, revoked, or for another digest/purpose;
- distinct negative states were flattened;
- source and projection disagree on a governed field.

### MAEP-13 — invalidate, revoke, and re-evaluate

A certificate becomes unusable when any declared invalidation trigger fires, including:

- authoritative source amended, corrected, repealed, superseded, or withdrawn;
- source digest or span changes;
- authority-text-set membership or legal status changes;
- rendition/variant changes;
- registered semantic vocabulary changes incompatibly;
- glossary entry changes materially;
- admission evidence expires or is withdrawn;
- adjudication decision is reversed, expires, or is shown conflicted;
- a new failing regression fixture exposes a prior false pass;
- purpose or operator context exceeds certificate scope.

The system preserves the old certificate and its reasoned history but returns the appropriate current non-use state. It does not rewrite history or relabel every invalidation `stale`.

## Decision logic

Illustrative pseudocode:

```text
function evaluate_maep(subject, target, purpose, context):
    classification = classify(subject, target)
    if classification is ambiguous:
        return refuse(reason_id = mapped_reason('object_classification_unresolved'))

    authority = resolve_authority_anchor(subject, context.jurisdiction)
    if authority is not established:
        return refuse(reason_id = mapped_reason('authority_anchor_unestablished'))

    frame = bind_semantic_frame(subject, authority)
    ids = bind_registered_ids(frame)
    if ids.has_unregistered_required_concept:
        return refuse(reason_id = mapped_reason('registered_vocabulary_gap'))

    glossary = select_glossary(ids, target.language, context.jurisdiction, purpose)
    automated = run_automated_checks(subject, target, frame, ids, glossary)
    if automated.material_failure:
        return fail(reason_id = automated.reason_id)

    counterexamples = compare_action_profiles(subject, target, frame, purpose)
    if counterexamples.material_difference:
        return fail(reason_id = mapped_reason('authority_semantics_not_preserved'))

    if status_upgrade_detected(subject, target, ids):
        return fail(reason_id = mapped_reason('semantic_status_upgrade'))

    if target.is_adaptation:
        adaptation = evaluate_adaptation_separately(target, frame, purpose)
        if adaptation.material_failure:
            return fail(reason_id = adaptation.reason_id)

    requirement = risk_table.requirement(subject, purpose)
    holder = eligible_holder(requirement.role, context)
    if requirement.needs_human and holder is none:
        return refuse(
            reason_id = mapped_reason('required_decision_holder_absent'),
            missing_role_id = requirement.role
        )

    decision = adjudicate_if_required(holder, evidence_bundle)
    if decision is contested_or_negative:
        return decision.as_typed_result()

    return issue_purpose_bounded_certificate(evidence_bundle, decision)
```

`mapped_reason(...)` means the implementation must use an existing registered reason where one exists and route a vocabulary gap otherwise. The pseudocode does not register tokens.

## Controlled glossary lifecycle

1. Draft entry binds a concept ID and source definition.
2. Language designation is proposed with context and negative examples.
3. Automated collision/confusable checks run.
4. Required review is determined by risk, not language alone.
5. With no required holder, state remains review-pending and high-stakes use refuses.
6. An approved release is immutable and versioned.
7. Deprecation preserves history and successor links.
8. Certificate invalidation is evaluated when an entry changes.

A glossary can function demonstrably on day one with zero appointed holders: draft entries, machine checks, fixtures, and non-high-stakes display remain available. Approval-dependent uses remain visibly blocked.

## Interface requirements

A high-stakes rendered surface exposes or makes reachable:

- semantic status/reason identity;
- source authority and version;
- rendition status and language;
- certificate purpose and validity;
- qualifications, conditions, and prohibited uses;
- whether wording is canonical, translated, or adapted;
- the source text or a durable route to it;
- contested/missing-role state and resolution path.

Visual adjacency alone is insufficient for assistive technology. The reading order must bind qualifiers and reasons to the governed claim.

## Security and abuse considerations

- Do not permit locale strings to select executable semantics.
- Treat mixed-script confusables and bidi controls as security-sensitive.
- Sign or digest source, rendition, glossary release, and certificate records.
- Log certificate use with purpose and versions without converting the log into post-hoc authority.
- Prevent a producer from self-approving high-stakes copy.
- Preserve withdrawn/superseded renditions for audit while blocking current reliance.
- Do not allow an informative translation to overwrite or masquerade as an authentic text.

## Classified protocol findings

| ID | finding | classification |
|---|---|---|
| M-01 | equivalence is proposition- and purpose-bounded, never catalogue-wide | `protocol_requirement` |
| M-02 | action-profile counterexamples are the decisive no-upgrade oracle | `protocol_requirement` |
| M-03 | canonical semantic IDs and logical roles must precede rendering | `protocol_requirement` |
| M-04 | controlled glossary releases are versioned evidence, not semantic authority by themselves | `external_evidence_supported_inference` |
| M-05 | high-stakes fragment concatenation is non-certifiable | `protocol_requirement` |
| M-06 | translation and adaptation require independent results | `protocol_requirement` |
| M-07 | co-authentic divergence requires jurisdiction-specific handling | `external_evidence_convergence` |
| M-08 | a vacant required role is a normal refusal state | `phased_deployment_requirement` |
| M-09 | MACHINE/Lex projections must reject label-only semantics | `protocol_requirement` |
| M-10 | certificates need explicit invalidation and revocation semantics | `protocol_requirement` |
