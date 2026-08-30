# INT-R6 language-dimension partition

## Verdict: `refined`

The proposed three-way partition is directionally correct but too coarse to prevent the central
error: treating every text in another language as the same kind of translation. INT-R6 refines it
into five dimensions with explicit dependency edges. They are separable decision variables, but not
pairwise independent: a presentation variant must identify the proposition and rendition it
transforms. The refinement composes with D4-A1 and does not amend the ratified product-UI posture.

## The five dimensions

### Dimension 1 — product UI locale

**Object.** PolicyOS-authored interface chrome: navigation, controls, system explanations, labels,
and messages.

**Authority.** D4-A1.

**Current values.** `en` is authored source; `uk` is translated; `ru` is
`legacy_continuity_frozen`. A `ru` source-content rendition is a different object and must not be
mistaken for an active UI locale.

**Invariant.** UI locale may select product strings only. It must not select an authoritative legal
text, infer jurisdiction, change a semantic ID, or confer authority on a rendition.

### Dimension 2 — authority text set

**Object.** The one or more text/version objects that the competent jurisdiction or instrument
recognises as authoritative for the legal act in question.

**Authority.** Jurisdictional source and admission evidence, never D4-A1.

**Relationship modes.** Proposed record vocabulary:

- `single_designated`;
- `multiple_coauthentic`;
- `parallel_official_non_equal`;
- `informative_only`.

These values are architecture candidates. Before implementation each must map to an existing
canonical owner or remain explicitly unallocated until registration; the list is not a second status
lattice and is not imported from one jurisdiction.

**Invariant.** A legal source is not a translation merely because another language version exists.
In `multiple_coauthentic`, no member is silently demoted to a rendition of another member.

### Dimension 3 — source-content rendition

**Object.** A renderable version of source content in a language/script for a declared purpose.

**Examples.** Original official publication; approved or certified translation; official
non-authentic translation; commissioned working translation; machine-assisted draft; read-only
legacy-language rendering; transliteration.

**Required fields.** Language tag, script, direction, source member/set, rendition relation/status,
producer, method, version, purpose, validity interval, evidence/certificate reference, and permitted
uses.

**Invariant.** Rendition status is not inferred from language. An English rendition of Ukrainian law
remains a rendition unless the competent legal regime gives it another status. A Russian
source-content rendition remains separate from the frozen Russian UI catalogue.

### Dimension 4 — semantic namespace and concept identifier

**Object.** The language-independent identity proposed for system logic, MACHINE twins, Lex
projections, tests, refusal routing, and registered vocabularies.

**Kinds.**

- `system_semantic_id`: PolicyOS-governed meaning shared across deployments;
- `jurisdiction_concept_id`: a concept anchored to a jurisdiction/instrument;
- `mapping_assertion`: a versioned claim relating two IDs.

**Invariant.** Display strings never serve as primary keys. A mapping does not merge identities. A
missing exact mapping is representable and may trigger refusal rather than English-pivot
normalisation.

### Dimension 5 — presentation variant

**Object.** The communicative transformation used for a particular audience or task: canonical,
plain-language adaptation, summary, explanation, or accessibility alternative.

**Dependency.** A variant must bind `parent_proposition_id` and its version. If it transforms a
rendition rather than the canonical proposition directly, it must also bind `parent_rendition_id` and
the transformation chain. It is therefore a dependent layer, not an independent source of meaning.

**Invariant.** Adaptation is assessed separately from translation. A variant retains provenance to
its parents and has its own semantic-preservation result, readability evidence, purpose, and use
limits.

## Derived rendering properties, not authority dimensions

Script, text direction, locale-specific number/date formatting, typography, and input method are
rendering properties derived from the chosen language/script and admission record. They must be
explicit, but they do not determine authority.

Jurisdiction is a governing scope attached to authority-text sets and concept namespaces; it is not
safely inferred from locale. The same language can serve several jurisdictions with different legal
concepts, and one jurisdiction can have several authentic languages.

## Why three dimensions are insufficient

The original partition combines authoritative source content and its renditions under “policy
subject-matter language”. That loses three distinctions:

1. one act may have several co-authentic texts, so there may be no singular source language;
2. a language version may be official but non-authentic, approved for a purpose, or merely
   informative;
3. plain-language adaptation can occur within the same language and therefore cannot be represented
   by a source/target language pair.

The refined partition retains the original insights while giving each failure a typed location and
declaring the dependencies that prevent a variant from becoming a free-standing authority claim.

## Claim-placement matrix

| claim | default home | permitted jurisdictional component | prohibited collapse |
|---|---|---|---|
| PolicyOS refusal code | existing `system_semantic_id` owner | reason evidence may cite a jurisdictional rule/concept | different refusal lattice per locale |
| `limited` standing | existing registered PolicyOS owner, qualified by namespace/version | jurisdiction may supply a causative fact | bare translated word as global status |
| `may_not_use_for` | system use restriction plus governed purpose ID | legal source may independently prohibit use | either prohibition weakened into advice |
| `stale` / `superseded` / `withdrawn` | existing system owner when registered | legally distinct local status mapped explicitly | distinct remedies/reasons collapsed into “invalid” |
| δ-bound or uncertainty bound | system namespace for a PolicyOS model/certificate | jurisdiction namespace when imposed by law/decision | notation treated as universal authority |
| authority ceiling | two claims when both legal and system ceilings exist | each preserves issuer and basis | one ceiling hiding who can change it |
| standing label | registered PolicyOS vocabulary | explicit mapping to local legal status | locale string as standing value |
| legal act type | jurisdiction concept ID unless a cross-jurisdiction abstraction is registered | narrower/broader/overlap mapping | consultation/recommendation/approval/decision forced into one label |

## Conceptual record model

The following is a research-level contract, not an implemented schema:

```text
JurisdictionAdmissionRecord
  jurisdiction_id
  valid_from / valid_to
  admitted_source_languages[]
  scripts[]
  direction_capabilities[]
  authority_modes[]
  authoritative_publishers[]
  authenticity_evidence[]
  divergence_rule
  required_roles[]
  evidence_pack_version

AuthorityTextSet
  authority_text_set_id
  jurisdiction_id
  instrument_id
  relationship_mode
  members[]
  effective_interval
  supersession_links[]
  admission_record_version

AuthorityTextMember
  text_member_id
  language_tag
  script
  publication_version
  source_uri / source_digest
  authenticity_status
  effective_interval

ContentRendition
  rendition_id
  source_member_or_set_id
  language_tag
  script
  direction
  rendition_relation
  purpose_ids[]
  producer / method
  glossary_version
  equivalence_certificate_id
  valid_from / valid_to

SemanticConcept
  namespace
  semantic_id
  version
  definition
  logical_role
  registered_vocabulary_reference

MappingAssertion
  from_id
  to_id
  relation
  jurisdiction_scope
  evidence
  required_role_id
  asserted_by_appointment_id
  valid_from / valid_to
  status

PresentationVariant
  variant_id
  parent_proposition_id
  parent_proposition_version
  parent_rendition_id? 
  transformation_chain[]
  language_tag
  variant_kind
  audience / purpose
  translation_certificate_id?
  adaptation_certificate_id?
  permitted_uses[]
```

A jurisdiction can be admitted without schema change **only if** all of its required authority
relations, source identities, mappings, evidence predicates, and role/refusal semantics fit this
already admitted envelope. A genuinely new semantic category requires governance/schema work and
must not be disguised as another record value merely to preserve a data-only claim.

## Ukraine architecture fixture

The abstract model is useful only if it can describe the initial jurisdiction without changing
D4-A1. The following is an architecture demonstration, not evidence of a current runtime chain.

### Product UI boundary

- `ui_locale=en`: authored PolicyOS UI.
- `ui_locale=uk`: Ukrainian translation of that UI.
- `ui_locale=ru`: unavailable as an active product locale; catalogue remains
  `legacy_continuity_frozen`.

### Ukrainian legal source content

For a Ukrainian statute or administrative act whose authoritative publication is Ukrainian, the
record model represents an authority-text set with a Ukrainian member and the jurisdiction's own
authority relation. An English working rendition is a `ContentRendition` with an evidenced
non-authentic purpose; it does not become the authority anchor merely because the product UI is
English.

The separation allows a future product implementation to use English or Ukrainian chrome without
changing source authority. It does not establish that current product surfaces display the source or
rendition.

### Russian source-content rendering

A Russian source document or read-only rendition, if independently admitted, belongs to Dimensions
2/3. It does not reactivate Russian UI, create an active catalogue obligation, or authorise
`locale_preference=ru` in an `en|uk` product-locale contract.

### Zero appointed holders

The model permits `required_role_id=high_stakes_language_adjudicator` with zero appointments. For a
disputed high-stakes rendition, the proposed protocol would return a purpose-scoped refusal such as:

```text
reason_id: rendering_contested
required_role_id: high_stakes_language_adjudicator
eligible_holder_count: 0
resolution_requirement: appoint_holder_or_supply_competent_decision
```

The exact reason must map to an existing refusal owner or remain unallocated pending registration.
The example does not create a second lattice. Source viewing, draft comparison, glossary preparation,
and fixture authoring are modeled as separately decidable functions; their current implementation is
not inferred from this record model.

## Co-authentic architecture fixture

For a Canadian federal act represented in English and French as co-authentic:

- `AuthorityTextSet.relationship_mode` represents a co-authentic relation;
- both members retain publication anchors and authenticity evidence;
- neither is the universal source and neither is converted through English as pivot;
- D4-A1 UI locale remains separate from the authority set;
- a material divergence records an interpretive divergence and invokes Canada's competent rule or a
  named future role;
- with zero appointed PolicyOS holder, the proposed governed derivation refuses for its purpose.

The same shapes may fit an EU instrument only if the EU-specific admission and interpretation rules
fit the admitted relation envelope. “Co-authentic” is not a universal algorithm.

## English-as-pivot decision

### Rejected uses

English must not be a mandatory intermediate representation for:

- defining a jurisdictional legal concept;
- establishing equivalence between co-authentic texts;
- generating an authoritative target text;
- determining the scope of a legal prohibition or power;
- deciding that two local concepts are identical.

The costs are loss of untranslatable distinctions, recursive drift, false equivalence, hidden
direction, and dependence on wording the competent legal order never adopted.

### Admitted uses

English may be used as:

- the D4-A1 product-UI authored source;
- an informative operator aid;
- a search/indexing aid;
- a provisional gloss in a mapping assertion;
- an explanatory or plain-language variant with explicit provenance and use limits.

A pivot rendition never upgrades the source. High-stakes action cannot rely on it alone unless the
relevant authority rule, purpose-bounded certificate, and appointed decision permit that use.

## RTL and non-Latin scripts

D4-A1 remains honestly `not_supported` for RTL product UI. The refined architecture avoids a
language-specific schema by making script/direction explicit on source-content and admission records.
That is a design property, not runtime proof.

A named RTL jurisdiction may be considered only with evidence covering:

- authoritative source languages and scripts;
- Unicode normalisation and canonical storage;
- shaping and font fallback without distributing font files;
- Unicode Bidirectional Algorithm handling and isolation for mixed-direction identifiers, numbers,
  citations, and code;
- logical DOM/focus order, visual mirroring policy, keyboard navigation, and screen-reader order;
- locale-correct line breaking, plural, date, number, and legal citation formatting;
- copy/paste, selection, search, highlighting, and text extraction;
- spoofing/confusable and identifier-display controls;
- PDF, print, export, MACHINE twin, and Lex projection round trips;
- red-first mixed LTR/RTL fixtures and user validation in the named jurisdiction.

Source-content RTL admission remains a separate future capability from public RTL UI. Neither is
claimed implemented by INT-R6.

## D4-A1 composition verdict

`composes`

D4-A1 governs Dimension 1. INT-R6 proposes records and invariants for Dimensions 2–5 and prevents
Dimension 1 from selecting them implicitly. English remains the authored UI source; Ukrainian
remains its UI translation; Russian UI remains frozen; source-content rendering remains separate;
RTL UI remains `not_supported` until the named evidence trigger is met.

No finding requires the ratified UI posture itself to change. A future public product-UI locale
remains a D4-A1 revisit event; admitting a jurisdictional source language or authority set does not
by itself amend D4-A1.

## Classified findings

| ID | finding | classification |
|---|---|---|
| P-01 | the three-axis proposal needs separate rendition and dependent-variant dimensions | `architectural_inference` |
| P-02 | UI locale must be non-authoritative for source-content selection | `protocol_requirement` |
| P-03 | authority must attach to text/version/set under a jurisdictional rule | `external_evidence_convergence` |
| P-04 | co-authentic texts require a set, not a source/translation edge | `external_evidence_convergence` |
| P-05 | English pivot is permissible only for explicit non-authoritative purposes unless separately authorised | `architecture_decision_candidate` |
| P-06 | system and jurisdiction concepts require separate namespaces and explicit mappings | `protocol_requirement` |
| P-07 | script direction is an admission property, not proof of authority | `architecture_decision_candidate` |
| P-08 | zero role holders are representable as a purpose-scoped refusal without an appointment claim | `phased_deployment_requirement` |
| P-09 | data-only N+1 is bounded by the admitted relation/vocabulary envelope | `architecture_decision_candidate` |
| P-10 | D4-A1 composes with the refined partition | `research_conclusion` |
