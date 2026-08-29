# INT-R6 language-axis partition

## Verdict: `refined`

The proposed three-way partition is directionally correct but too coarse to prevent the central error: treating every text in another language as the same kind of translation. INT-R6 refines it into five orthogonal coordinates. The refinement composes with D4-A1; it does not amend the ratified product-UI posture.

## The five coordinates

### Axis 1 — product UI locale

**Object.** PolicyOS-authored interface chrome: navigation, controls, system explanations, labels, and messages.

**Authority.** D4-A1.

**Current values.** `en` is authored source; `uk` is translated; `ru` is `legacy_continuity_frozen`. A selected `ru` value must not escape into an API contract that admits only `en`/`uk`.

**Invariant.** UI locale may select product strings only. It must not select an authoritative legal text, infer jurisdiction, change a semantic ID, or confer authority on a rendition.

### Axis 2 — authority text set

**Object.** The one or more text/version objects that the competent jurisdiction or instrument recognises as authoritative for the legal act in question.

**Authority.** Jurisdictional source and admission evidence, never D4-A1.

**Relationship modes.** Proposed record vocabulary:

- `single_designated`;
- `multiple_coauthentic`;
- `parallel_official_non_equal`;
- `informative_only`.

These values are architectural candidates and require registration before implementation. They are not labels imported from one jurisdiction.

**Invariant.** A legal source is not a translation merely because another language version exists. In `multiple_coauthentic`, no member has `translated_from` another member unless the jurisdiction explicitly records a drafting relation that does not alter equal authority.

### Axis 3 — source-content rendition

**Object.** A renderable version of source content in a language/script for a declared purpose.

**Examples.** Original official publication; certified translation; official non-authentic translation; commissioned working translation; machine-assisted draft; read-only legacy-language rendering; transliteration.

**Required fields.** Language tag, script, direction, source text/member, rendition status, producer, method, version, purpose, validity interval, certificate, and permitted uses.

**Invariant.** Rendition status is not inferred from language. An English rendition of Ukrainian law remains a rendition unless Ukrainian law or the competent authority gives it another status. A Russian source-content rendering remains separate from the frozen Russian UI catalogue.

### Axis 4 — semantic namespace and concept identifier

**Object.** The language-independent identity used by system logic, MACHINE twins, Lex projections, tests, refusal routing, and registered vocabularies.

**Kinds.**

- `system_semantic_id`: PolicyOS-governed meaning shared across deployments;
- `jurisdiction_concept_id`: a concept anchored to a jurisdiction/instrument;
- `mapping_assertion`: a versioned claim relating two IDs.

**Invariant.** Display strings never serve as primary keys. A mapping does not merge identities. A missing exact mapping is representable and may trigger refusal rather than English-pivot normalisation.

### Axis 5 — presentation variant

**Object.** The communicative form used for a particular audience or task: canonical, plain-language adaptation, summary, explanation, or accessibility alternative.

**Invariant.** Adaptation is assessed separately from translation. A variant retains provenance to the canonical proposition and has its own semantic-preservation result, readability evidence, purpose, and use limits.

## Derived dimensions, not additional semantic axes

Script, text direction, locale-specific number/date formatting, typography, and input method are rendering capabilities derived from the chosen language/script and admission record. They must be explicit, but they do not determine authority.

Jurisdiction is a governing scope attached to authority-text sets and concept namespaces; it is not safely inferred from locale. The same language can serve several jurisdictions with different legal concepts, and one jurisdiction can have several authentic languages.

## Why three axes are insufficient

The original partition combines authoritative source content and its translations under “policy subject-matter language”. That loses three distinctions:

1. one act may have several co-authentic texts, so there may be no singular source language;
2. a language version may be official but non-authentic, certified for a purpose, or merely informative;
3. plain-language adaptation can occur within the same language and therefore cannot be represented by a source/target language pair.

The refined partition retains the original insights while giving each failure a typed location.

## Claim-placement matrix

| claim | default home | permitted jurisdictional component | prohibited collapse |
|---|---|---|---|
| PolicyOS refusal code | `system_semantic_id` | reason evidence may cite a jurisdictional rule or concept | creating a different refusal lattice per locale |
| `limited` standing | existing registered PolicyOS vocabulary | jurisdiction may supply the fact that causes the standing | translating it into an unregistered local status |
| `may_not_use_for` | system use restriction plus governed purpose ID | legal source may independently prohibit a use | weakening either prohibition into advice |
| `stale` / `superseded` / `withdrawn` | existing system vocabulary if already registered | jurisdictional source may define a legally distinct status mapped explicitly | collapsing distinct remedies/reasons into “invalid” |
| δ-bound or uncertainty bound | system namespace when it describes a PolicyOS model/certificate | jurisdiction namespace when imposed by law or a competent decision | assuming mathematical notation makes the claim universal |
| authority ceiling | two claims when both exist: jurisdictional legal ceiling and PolicyOS safety/operational ceiling | each preserves its issuer and basis | one generic ceiling that hides which authority can change it |
| standing label | registered PolicyOS vocabulary | an explicit mapping to a jurisdictional legal status may be attached | a locale string acting as the standing value |
| legal act type | jurisdiction concept ID unless PolicyOS has a registered cross-jurisdiction abstraction | mappings such as narrower/broader/overlap | forcing consultation, recommendation, approval, and decision into one English label |

## Conceptual record model

The following is a research-level data contract, not an implementation schema:

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
  rendition_status
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
  asserted_by_role
  valid_from / valid_to
  status

PresentationVariant
  variant_id
  parent_proposition_id
  language_tag
  variant_kind
  audience / purpose
  translation_certificate_id
  adaptation_certificate_id
  permitted_uses[]
```

Every record type can admit jurisdiction N+1 through data. None requires adding a language-specific column, adding an `is_english_source` invariant, or changing the meaning of UI locale.

## Ukraine first deployment

The abstract model is admissible only if it says something concrete now.

### Current product UI

- `ui_locale=en`: authored PolicyOS UI.
- `ui_locale=uk`: Ukrainian translation of that UI.
- `ui_locale=ru`: unavailable as an active product locale; catalogue remains `legacy_continuity_frozen`.

### Ukrainian legal source content

For a Ukrainian statute or administrative act whose authoritative publication is Ukrainian, the authority-text set is `single_designated` with a Ukrainian member. An English working rendition is a `ContentRendition` with `informative` or another evidenced non-authentic status; it does not become the authority anchor merely because the product UI is English.

An operator may therefore use English UI chrome while viewing the Ukrainian source, an English informative rendition, or both. Changing UI locale does not change the source-content selection.

### Russian source-content rendering

A Russian source document or permitted read-only rendering is represented on Axis 2/3. It does not reactivate the Russian product UI, accrue a catalogue translation obligation, or permit `locale_preference=ru` to enter an `en|uk` UI runtime contract.

### Zero appointed holders

The data model allows `required_role = high_stakes_language_adjudicator` and `holder_count = 0`. For a disputed high-stakes rendition, evaluation returns a typed refusal such as:

```text
reason_id: rendering_contested
missing_role_id: high_stakes_language_adjudicator
resolution_path: appoint_holder_or_supply_competent_decision
```

The exact refusal IDs must map to the existing refusal vocabulary or be routed for registration; the example does not establish a second lattice. Source viewing, low-risk draft comparison, glossary preparation, and red-first fixtures remain demonstrable. The vacancy blocks only the governed decision that needs the role.

## Co-authentic deployment example

For a Canadian federal act represented in English and French as co-authentic:

- `AuthorityTextSet.relationship_mode = multiple_coauthentic`;
- both members carry their own publication anchors and authenticity evidence;
- neither is the universal source and neither is converted through English as a pivot;
- a PolicyOS UI may still be English under D4-A1 without changing the authority set;
- an operator may display either or both members and an explanatory rendition;
- a material divergence creates an `InterpretiveDivergence`/contested state and invokes Canada's competent reconciliation rule or a named human role;
- with no appointed PolicyOS holder, the governed derived claim refuses while the authentic texts remain viewable.

The same model can represent EU instruments, but the admission record and interpretation rule must be EU-specific. “Co-authentic” is not a universal algorithm.

## English-as-pivot decision

### Rejected uses

English must not be a mandatory intermediate representation for:

- defining a jurisdictional legal concept;
- establishing equivalence between co-authentic texts;
- generating an authoritative target text;
- determining the scope of a legal prohibition or power;
- deciding that two local concepts are identical.

The costs are loss of untranslatable distinctions, recursive translation drift, false equivalence, hidden source/target direction, and dependence on an English wording that the competent legal order never adopted.

### Admitted uses

English may be used as:

- the D4-A1 product-UI authored source;
- an informative bridge for operators;
- a search/indexing aid;
- a provisional gloss in a mapping assertion;
- an explanatory or plain-language variant with explicit provenance and use limits.

A pivot rendition never upgrades the source, and high-stakes action cannot rely on it alone unless the relevant authority rule and equivalence certificate permit that purpose.

## RTL and non-Latin scripts

D4-A1 remains honestly `not_supported` for RTL product UI. The refined architecture nevertheless prevents future redesign by making script/direction data-driven on source content and jurisdiction admission.

A named RTL jurisdiction may be admitted only with an evidence pack covering at least:

- authoritative source languages and scripts;
- Unicode normalisation and canonical storage;
- shaping and font fallback without distributing font files;
- Unicode Bidirectional Algorithm handling and isolation for mixed-direction identifiers, numbers, citations, and code;
- logical DOM/focus order, visual mirroring policy, keyboard navigation, and screen-reader order;
- locale-correct line breaking, plural, date, number, and legal citation formatting;
- copy/paste, selection, search, highlighting, and text extraction;
- spoofing/confusable and identifier-display controls;
- PDF, print, export, MACHINE twin, and Lex projection round trips;
- red-first mixed LTR/RTL fixtures and user validation in the named jurisdiction.

Source-content RTL rendering can be admitted separately from a public RTL UI locale if D4-A1's capability boundary is respected and the interface does not claim full RTL support.

## D4-A1 composition verdict

`composes`

D4-A1 governs Axis 1. INT-R6 supplies the records and invariants for Axes 2–5 and prevents Axis 1 from selecting them implicitly. English remains the authored UI source; Ukrainian remains its UI translation; Russian UI remains frozen; source-content rendering remains separate; RTL UI remains `not_supported` until the named evidence trigger is met.

No finding in this pass requires the ratified UI posture itself to change. The early architect stop rule is therefore not triggered. A future request to add a public product UI locale remains a D4-A1 revisit event; admitting a jurisdictional source language or co-authentic authority set does not by itself amend D4-A1.

## Classified findings

| ID | finding | classification |
|---|---|---|
| P-01 | the three-axis proposal needs separate rendition and adaptation coordinates | `architectural_inference` |
| P-02 | UI locale must be non-authoritative for source-content selection | `protocol_requirement` |
| P-03 | authority must attach to text/version/set under a jurisdictional rule | `external_evidence_convergence` |
| P-04 | co-authentic texts require a set, not a source/translation edge | `external_evidence_convergence` |
| P-05 | English pivot is permissible only for explicitly non-authoritative purposes unless separately authorised | `architecture_decision_candidate` |
| P-06 | system and jurisdiction concepts require separate namespaces and explicit mappings | `protocol_requirement` |
| P-07 | script direction is an admission capability, not proof of authority | `architecture_decision_candidate` |
| P-08 | zero role holders must produce a typed refusal without schema change | `phased_deployment_requirement` |
| P-09 | D4-A1 composes with the refined partition | `research_conclusion` |
