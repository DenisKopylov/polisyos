# INT-R6 external-evidence synthesis

This appendix synthesises the five commissioned deep-research surveys. It is external practice, not repository capability and not authority for PolicyOS. Every legal proposition is bounded to its jurisdiction or instrument. Where the surveys disagree, the disagreement is preserved because the architecture must represent both sides.

## Evidence handling rule

A source enters this synthesis with five fields:

1. **regime or jurisdiction** — the legal or institutional system to which the proposition belongs;
2. **text relation** — designated source, co-authentic text, official translation, certified translation, or informative rendition;
3. **claim supported** — no broader than the source;
4. **transfer boundary** — what PolicyOS may learn without importing the regime's authority;
5. **confidence** — `primary_source`, `regulated_practice`, `empirical_study`, `secondary_synthesis`, or `thin`.

No source establishes a universal rule merely because it is prominent. In particular, a designated-source regime cannot be used to prove that co-authentic texts have a source/target direction, and a co-authentic regime cannot be used to make every translation authoritative.

## Survey 1 — authentic text and translation equivalence in regulated regimes

### Designated-source regimes

In a designated-source regime one text is legally controlling and another language version may be official, certified, approved, or routinely relied upon without becoming the legal source. Equivalence work is directional: source meaning constrains the rendition. This pattern maps cleanly to D4-A1 for **product UI** (`en` authored, `uk` translated), and it can describe a jurisdictional source-content record only where that jurisdiction itself designates a source.

The transfer limit is strict. PolicyOS may record that a rendition has a recognised status and purpose; it may not promote the rendition into the authority set. A reliable translation is evidence about the source text unless the competent regime gives it a stronger status.

### Co-authentic regimes

The Vienna Convention on the Law of Treaties, Article 33, addresses treaties authenticated in two or more languages. Unless the treaty provides otherwise, each authentic text is equally authoritative; interpretation presumes the same meaning, and unresolved divergence is reconciled by the meaning that best reconciles the texts in light of object and purpose. That is not a translation workflow with one source. It is a set-valued authority model.

The European Union likewise requires multilingual legal interpretation across official language versions. `CILFIT` (Case 283/81) warns that Community legislation is drafted in several languages and that all language versions are equally authentic; a single-language reading is therefore insufficient. `Skoma-Lux` (Case C-161/06) separately demonstrates that publication in the relevant official language matters to enforceability against individuals. These propositions are EU-law propositions, not a universal hierarchy.

Canada's federal bilingual legislation treats English and French versions as equally authoritative. The shared-meaning approach used in Canadian bilingual interpretation is a method for reconciling co-authentic enactments; it does not designate one version as the source. Canadian bijural drafting adds a second dimension: concept systems may differ as well as languages.

Switzerland's federal multilingual practice similarly demonstrates that several official-language versions can participate in legal interpretation without an English pivot. The exact authority of German, French, Italian, and Romansh materials depends on the instrument and publication regime; therefore a generic `official_language=true` flag is insufficient.

Belgian multilingual legislation provides another warning against flattening: language, territorial competence, publication, and authentic-version rules are not reducible to one global locale list. The architecture must store the jurisdiction's own authority rule rather than infer it from language status.

### Architectural consequence

The external record falsifies a universal `source_language -> translations[]` model. The minimum general object is an **authority text set** whose relation is declared by the competent regime:

- `single_designated`;
- `multiple_coauthentic`;
- `parallel_official_non_equal`;
- `informative_only`.

The names are proposed PolicyOS record values, not imported legal terms. Their semantics must be registered before implementation.

## Survey 2 — entailment, scope, and modality from English into Ukrainian

Structural key parity cannot demonstrate that an English operative proposition and a Ukrainian rendering authorise the same conduct. The relevant object is the proposition under its conditions, exceptions, actors, objects, time, place, and evidentiary qualifiers.

### High-risk transformations

| English source pattern | Ukrainian rendering risk | authority-semantic failure |
|---|---|---|
| `must`, `shall`, `is required to` | `має`, `повинен`, `зобов'язаний`, impersonal obligation, future-tense legal style | obligation weakened, strengthened, or shifted to another actor |
| `may` | `може`, `має право`, permission paraphrase, capability reading | permission confused with physical/technical possibility or entitlement |
| `may not` | `не може`, `не має права`, `заборонено`, `не слід` | prohibition rendered as incapacity, lack of entitlement, or advice |
| `should` | `слід`, `варто`, `повинен` | recommendation upgraded to obligation |
| `only if`, `unless`, `except` | clause movement, punctuation, lexical paraphrase | condition or exception takes wider/narrower scope |
| `not all`, `all ... not`, `no` | negation placement and quantifier order | actor/action set changes |
| `until`, `after`, `while`, `within` | aspect and temporal-boundary choice | authority starts or ends at the wrong instant |
| `at least`, `no more than`, interval notation | lexical or numeric normalisation | threshold reverses or open/closed bound disappears |
| `unknown`, `not established`, `not available` | one generic negative term | epistemic state collapses into absence or falsity |

Ukrainian morphology makes some English interpolation patterns unsafe. A substituted noun may require a different case after a preposition or governing verb; numerals govern different noun forms; adjectives and participles agree; animate/inanimate distinctions affect accusative forms; and aspect can alter whether an act is bounded or ongoing. The protocol therefore tests the rendered proposition, not only each catalogue leaf.

### Operationalisation: action-set preservation

For an operative proposition `p`, define a normalised semantic frame:

```text
actor
act_type
object
modality
conditions[]
exceptions[]
temporal_scope
spatial_scope
quantifiers[]
evidence_qualifiers[]
numeric_constraints[]
consequence
```

Let `A(p, c)` be the set of actions licensed in context `c`, `R(p, c)` the required actions, and `F(p, c)` the forbidden actions. A target rendition passes only if, for all material test contexts:

```text
A(target, c) = A(source, c)
R(target, c) = R(source, c)
F(target, c) = F(source, c)
```

For a designated-source translation, any target that expands `A`, shrinks `F`, removes a condition, or upgrades evidentiary standing fails even if readers judge it fluent. For a co-authentic set there is no privileged source/target equation; the system records an interpretive divergence and applies the jurisdiction's reconciliation rule or refuses pending competent adjudication.

### Evidence limit

The surveys identify strong general linguistic and legal-translation reasons to test modality and scope. Direct, large-sample empirical evidence specifically measuring English-to-Ukrainian authority-semantic error rates is sparse. INT-R6 therefore classifies the detailed Ukrainian hazard inventory as `linguistically_grounded` and the expected error frequencies as `unknown`, not borrowed from another language pair.

## Survey 3 — concept identity, terminology management, and controlled glossaries

Terminology standards distinguish a concept from its designations. ISO 704 and ISO 1087 support concept-oriented terminology work; TBX (ISO 30042) provides an interchange model for terminological data. These standards do not decide PolicyOS authority, but they support three design moves:

- stable concept/semantic identifiers must not be locale strings;
- a concept may have multiple language-specific designations with usage status and context;
- definitions, terms, deprecated terms, sources, and change history must be versioned.

PolicyOS has an additional asymmetry. The system-governance vocabulary is authored under a ratified governance process, while a jurisdictional legal concept is not created by PolicyOS. Therefore the terminology layer must distinguish:

- `system_semantic_id` — a PolicyOS-governed concept such as a refusal or standing value;
- `jurisdiction_concept_id` — a concept anchored to a jurisdictional source and not forced into a universal English definition;
- `mapping_assertion` — an explicit, versioned relationship such as exact, narrower, broader, overlapping, related, or no admitted mapping.

The system must not create a second status lattice. Existing registered vocabularies remain authoritative for PolicyOS status. The glossary supplies designations and constraints for those IDs; it does not replace the IDs with newly invented near-synonyms.

A controlled glossary entry needs at least:

```text
semantic_id / jurisdiction_concept_id
namespace
concept_definition
source_anchor
language_tag
script
term
term_status
part_of_speech
morphology_or_inflection_note
forbidden_synonyms[]
confusable_concepts[]
usage_examples[]
negative_examples[]
valid_from / valid_to
version
review_state
adjudication_role
```

A term match is necessary but not sufficient. The proposition-level gate remains decisive because correct terms can be assembled into a semantically wrong sentence.

## Survey 4 — graded status vocabularies and the upgrade failure

Regulated systems use graded vocabularies because different negative and qualified states lead to different actions. Translation failure often moves a claim upward: qualified evidence becomes confirmed, a prohibition becomes cautionary advice, or distinct reasons for non-use collapse into a generic invalid state.

The safe model is not a single linear confidence score. Some states are ordered; others are categorically distinct. `stale`, `superseded`, and `withdrawn` can all block present reliance while preserving different provenance and remediation:

- `stale`: freshness requirement failed; reacquisition or revalidation may restore use;
- `superseded`: another identified object/version displaced this one; the successor relation matters;
- `withdrawn`: the responsible authority removed the object or claim; reacquisition is not equivalent to freshness renewal.

Those glosses are protocol-level working definitions and must map to the repository's registered vocabulary rather than silently establishing a new one.

The **status-upgrade ban** is directional for D4-A1 UI translation: an `en` authored system status may not become stronger, less conditional, more permissive, or less differentiated in `uk`. A useful machine gate treats each status as an operator-action profile. A translation fails if it admits an action forbidden by the source profile, removes escalation, changes the required remedy, or masks the reason code.

## Survey 5 — plain-language adaptation and human adjudication

Plain-language adaptation is not translation. The two transformations have different source objects and can fail in opposite directions:

1. `en canonical UI -> uk faithful translation` tests cross-language equivalence;
2. `en canonical UI -> en plain-language adaptation` tests same-language simplification;
3. any `uk` plain-language version must declare whether it is translated from the canonical English or adapted from a certified Ukrainian translation, and its provenance must retain both steps.

Readability metrics can identify long sentences, rare words, or syntactic load, but they cannot prove preservation of legal scope. User testing can show comprehension and action, but it does not confer authority. High-stakes adaptation therefore needs separate semantic review and behavioural fixtures.

Real institutions often use bilingual drafters, translation services, terminology boards, language commissions, or judicial/administrative interpretation to settle contested wording. PolicyOS currently has none of those appointed holders. INT-R6 adopts the process shape without borrowing a fictitious institution:

- the required role is named in the protocol;
- holder cardinality may be zero;
- a high-stakes contested rendition with zero qualified holders returns a typed refusal;
- appointing a holder later changes the assignment record, not the schema or refusal model;
- low-stakes demonstrable functionality is not globally gated by the vacant role.

## Cross-survey synthesis

### Finding E-01 — authority is a relation, not a language property

`authoritative=true` cannot safely sit on a language tag alone. Authority belongs to a text/version under a jurisdictional rule and purpose.

**Classification:** `external_evidence_convergence`

### Finding E-02 — English is admissible as UI source, not universal legal pivot

D4-A1's English-authored UI composes with a legal-content architecture that can anchor Ukrainian law in Ukrainian and a future co-authentic regime in several languages. Requiring every legal concept to be defined in English first would add a legally consequential pivot that co-authentic systems do not contain.

**Classification:** `architectural_inference`

### Finding E-03 — semantic IDs need namespaces

A global unqualified ID risks either fragmenting system governance per jurisdiction or forcing local legal concepts into false equivalence. Namespaced system IDs, jurisdiction concept IDs, and explicit mappings avoid both errors.

**Classification:** `protocol_requirement`

### Finding E-04 — proposition testing dominates string testing

Glossaries and catalogue parity are controls, but equivalence is decided at the proposition/action level, including conditions, exceptions, time, and uncertainty.

**Classification:** `external_evidence_convergence`

### Finding E-05 — adaptation needs its own certificate

A translation can be faithful and unreadable; an adaptation can be readable and authority-changing. One boolean cannot represent both.

**Classification:** `protocol_requirement`

### Finding E-06 — missing adjudication capacity is a typed state

The absence of an appointed holder is not a software exception and not permission to pass. It is an operationally explicit refusal with a named missing role.

**Classification:** `phased_deployment_requirement`

## Source register

The following are the principal external anchors used by the surveys and this synthesis. Links are locators, not a claim that the linked body governs PolicyOS.

| source | jurisdiction / regime | use in INT-R6 | evidence class |
|---|---|---|---|
| Vienna Convention on the Law of Treaties, Article 33 | treaty interpretation | model of several authentic texts and divergence reconciliation | `primary_source` |
| Council Regulation No 1 determining the languages to be used by the European Economic Community | European Union | multilingual publication and official-language regime | `primary_source` |
| CJEU, Case 283/81, `CILFIT` | European Union | equally authentic language versions and multilingual interpretation | `primary_source` |
| CJEU, Case C-161/06, `Skoma-Lux` | European Union | consequences of non-publication in the relevant official language | `primary_source` |
| Constitution Act, 1982, section 18; Canadian bilingual interpretation jurisprudence including `R v Daoust`, 2004 SCC 6 | Canada | co-authentic federal legislation and shared-meaning method | `primary_source` |
| Swiss Federal Constitution and federal publication/language framework | Switzerland | multilingual federal texts without an English pivot | `primary_source` |
| Constitution of Ukraine, Article 10, and Law No. 2704-VIII on the functioning of Ukrainian as the State language | Ukraine | state-language and first-deployment jurisdiction context | `primary_source` |
| ISO 704:2022, Terminology work — Principles and methods | international standard | concept-oriented terminology method | `regulated_practice` |
| ISO 1087:2019, Terminology work and terminology science — Vocabulary | international standard | concept/designation vocabulary | `regulated_practice` |
| ISO 30042:2019, TermBase eXchange (TBX) | international standard | versionable terminology interchange | `regulated_practice` |
| ISO 17100:2015, Translation services | international standard | translation workflow roles and review separation | `regulated_practice` |
| ISO 24495-1:2023, Plain language — Governing principles and guidelines | international standard | plain-language adaptation principles | `regulated_practice` |
| W3C Internationalization guidance on bidirectional text; Unicode Bidirectional Algorithm | international technical standards | bounded RTL admission evidence | `regulated_practice` |
| Unicode CLDR | international technical data standard | locale, script, plural, date, number, and display data | `regulated_practice` |

## Evidence gaps retained

- Measured English-to-Ukrainian authority-semantic error rates across a representative governance corpus: `unknown`.
- A validated Ukrainian legal plain-language readability threshold that predicts correct operator action: `unknown`.
- A universal reconciliation rule for co-authentic divergences: `not_applicable`; the rule is jurisdiction-specific.
- A universal equivalence relation between jurisdictional legal concepts and PolicyOS system concepts: `not_applicable`.
- Evidence sufficient to admit a named RTL jurisdiction in PolicyOS today: `not_collected`; D4-A1 remains `not_supported`.
