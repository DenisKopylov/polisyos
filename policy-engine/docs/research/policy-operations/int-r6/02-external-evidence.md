# INT-R6 external-evidence synthesis

This appendix synthesises the five commissioned deep-research surveys. It is external practice, not
repository capability and not authority for PolicyOS. Every legal proposition is bounded to its
jurisdiction or instrument. Where the surveys disagree, the disagreement is preserved because the
architecture must represent both sides.

## Evidence handling rule

A source enters this synthesis with five fields:

1. **regime or jurisdiction** — the legal or institutional system to which the proposition belongs;
2. **text relation** — designated source, co-authentic text, official translation, certified
   translation, or informative rendition;
3. **claim supported** — no broader than the source and its cited article/paragraph/section;
4. **transfer boundary** — what PolicyOS may learn without importing the regime's authority;
5. **confidence** — `primary_source`, `regulated_practice`, `empirical_study`,
   `secondary_synthesis`, or `thin`.

No source establishes a universal rule merely because it is prominent. A designated-source regime
cannot prove that co-authentic texts have a source/target direction, and a co-authentic regime cannot
make every translation authoritative. Source links below retain primary documents and add durable
article, paragraph, clause, table, or standard-section locators; no primary source is replaced by a
secondary one merely to obtain a convenient anchor.

## Survey 1 — authentic text and translation equivalence in regulated regimes

### Designated-source regimes

In a designated-source regime one text is legally controlling and another language version may be
official, certified, approved, or routinely relied upon without becoming the legal source.
Equivalence work is directional: source meaning constrains the rendition. This pattern maps cleanly
to D4-A1 for **product UI** (`en` authored, `uk` translated), and it can describe a jurisdictional
source-content record only where that jurisdiction itself designates a source.

The transfer limit is strict. PolicyOS may record that a rendition has a recognised status and
purpose; it may not promote the rendition into the authority set. A reliable translation is evidence
about the source text unless the competent regime gives it a stronger status.

### Co-authentic regimes

The Vienna Convention on the Law of Treaties, Article 33(1)–(4), addresses treaties authenticated in
two or more languages. Unless the treaty provides otherwise, each authentic text is equally
authoritative; interpretation presumes the same meaning, and unresolved divergence is reconciled by
the meaning that best reconciles the texts in light of object and purpose. That is not a translation
workflow with one source. It is a set-valued authority model.

The European Union likewise requires multilingual legal interpretation across official language
versions. `CILFIT` (Case 283/81), paragraph 18, states the consequence of equally authentic versions:
a single-language reading is insufficient. `Skoma-Lux` (Case C-161/06), paragraphs 37–51,
separately demonstrates that publication in the relevant official language matters to enforceability
against individuals. These are EU-law propositions, not a universal hierarchy.

Canada's federal bilingual legislation treats English and French enactment versions as equally
authoritative: Constitution Act, 1982, section 18, and Official Languages Act, section 13. The
shared-meaning method in *R v Daoust*, 2004 SCC 6, paragraphs 26–30, is a method for reconciling
co-authentic enactments; it does not designate one version as source. The durable SCC locator is item
`2117`, not item `2110`.

Switzerland's Federal Act on the Compilations of Federal Legislation and the Federal Gazette,
SR 170.512, Article 14, demonstrates several equally binding enactment texts while English
translations may remain information-only. The exact status depends on the instrument and publication
regime; a generic `official_language=true` flag is insufficient.

Belgian materials show that linguistic authenticity may be conferred by a later competent
legislative act. They are used only for that bounded institutional distinction, not for a universal
Belgian rule inferred from one parliamentary record.

### Architectural consequence

The external record falsifies a universal `source_language -> translations[]` model. The minimum
general object is an **authority text set** whose relation is declared by the competent regime:

- `single_designated`;
- `multiple_coauthentic`;
- `parallel_official_non_equal`;
- `informative_only`.

The names are proposed relation values, not imported legal terms or a registered second lattice. They
must map to an existing canonical owner or remain explicitly unallocated until a competent later
stage registers them.

## Survey 2 — entailment, scope, and modality from English into Ukrainian

Structural key parity cannot demonstrate that an English operative proposition and a Ukrainian
rendering authorise the same conduct. The relevant object is the proposition under its conditions,
exceptions, actors, objects, time, place, and evidentiary qualifiers.

### High-risk transformations

| English source pattern | Ukrainian rendering risk | authority-semantic failure |
|---|---|---|
| `must`, `shall`, `is required to` | `має`, `повинен`, `зобов'язаний`, impersonal obligation, legal present | obligation weakened, strengthened, or shifted to another actor |
| `may` | `може`, `має право`, permission paraphrase, capability reading | permission confused with physical possibility or entitlement |
| `may not` | `не може`, `не має права`, `заборонено`, `не слід` | prohibition rendered as incapacity, lack of entitlement, or advice |
| `should` | `слід`, `варто`, `повинен` | recommendation upgraded to obligation |
| `only if`, `unless`, `except` | clause movement, punctuation, paraphrase | condition or exception takes wider/narrower scope |
| `not all`, `all ... not`, `no` | negation placement and quantifier order | actor/action set changes |
| `until`, `after`, `while`, `within` | aspect and temporal-boundary choice | authority starts or ends at the wrong instant |
| `at least`, `no more than`, interval notation | lexical or numeric normalisation | threshold reverses or open/closed bound disappears |
| `unknown`, `not established`, `not available` | one generic negative term | epistemic state collapses into absence or falsity |

Ukrainian morphology makes some English interpolation patterns unsafe. A substituted noun may require
a different case after a preposition or governing verb; numerals govern different forms; adjectives
and participles agree; animate/inanimate distinctions affect accusative forms; and aspect can alter
whether an act is bounded or ongoing. The protocol therefore tests the rendered proposition, not
only each catalogue leaf.

### Operationalisation: bounded action-set preservation

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

Let `A(p,c)` be actions licensed in context `c`, `R(p,c)` required actions, and `F(p,c)` forbidden
actions. A candidate may pass only over a **complete, versioned, declared test population** `C_test`:

```text
for every c in C_test:
    A(target,c) = A(source,c)
    R(target,c) = R(source,c)
    F(target,c) = F(source,c)
```

One target-only permission, lost prohibition, condition, qualifier, or status distinction refutes the
candidate for that purpose. No counterexample in finite `C_test` does not prove unrestricted
equivalence. A positive result must publish the population digest/cardinality, exclusions, unresolved
context classes, and residual. For a co-authentic set there is no privileged source/target equation;
the system records divergence and applies the jurisdiction's rule or refuses pending competent
adjudication.

### Evidence limit

The surveys identify strong linguistic and legal-translation reasons to test modality and scope.
Direct, large-sample evidence measuring English-to-Ukrainian authority-semantic error rates is sparse.
The detailed Ukrainian hazard inventory is `linguistically_grounded`; expected frequencies remain
`unknown`, not borrowed from another language pair.

## Survey 3 — concept identity, terminology management, and controlled glossaries

Terminology standards distinguish a concept from its designations. ISO 1087:2019 §§3.2.7, 3.4.1,
and 3.4.2 define concept/designation/term; ISO 704:2022 supplies concept-characteristic,
definition, and concept-system principles; TBX, ISO 30042:2019, uses the
`conceptEntry/langSec/termSec` structure. These standards do not decide PolicyOS authority, but
support three design moves:

- stable concept/semantic identifiers must not be locale strings;
- a concept may have language-specific designations with usage status and context;
- definitions, designations, deprecated forms, sources, and change history must be versioned.

PolicyOS has an additional asymmetry. The system-governance vocabulary is authored under a ratified
process, while a jurisdictional legal concept is not created by PolicyOS. The terminology layer must
distinguish:

- `system_semantic_id` — a PolicyOS-governed concept such as a refusal or standing value;
- `jurisdiction_concept_id` — a concept anchored to a jurisdictional source and not forced into a
  universal English definition;
- `mapping_assertion` — an explicit, versioned relation such as exact, narrower, broader,
  overlapping, related, or no admitted mapping.

The system must not create a second status lattice. Existing registered vocabularies remain
authoritative for PolicyOS status. The glossary supplies designations and constraints for those IDs;
it does not replace IDs with invented near-synonyms.

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
required_role_id
```

A term match is necessary but not sufficient. The proposition-level gate remains decisive because
correct terms can be assembled into a semantically wrong sentence.

## Survey 4 — graded status vocabularies and the upgrade failure

Regulated systems use graded vocabularies because different negative and qualified states lead to
different actions. Translation may strengthen, soften, or collapse a claim. The external record does
not establish a systematic English→Ukrainian direction; the safe invariant forbids all three.

The model is not one linear confidence score. Some states are ordered; others are categorical.
`stale`, `superseded`, and `withdrawn` can all block present reliance while preserving different
provenance and remediation:

- `stale`: freshness requirement failed; reacquisition or revalidation may restore use;
- `superseded`: another identified object/version displaced this one; the successor relation matters;
- `withdrawn`: the responsible authority removed the object or claim; freshness renewal alone is not
  an equivalent remedy.

Those are bounded working interpretations and must map to repository-owned identifiers. They do not
establish a local lifecycle lattice.

The status-upgrade ban is directional for D4-A1 UI translation: an `en` authored system status may
not become stronger, less conditional, more permissive, or less differentiated in `uk`. A machine
gate compares the source status ID/action profile rather than reverse-engineering grade from target
wording.

## Survey 5 — plain-language adaptation and human adjudication

Plain-language adaptation is not translation. The transformations have different sources and can fail
in opposite directions:

1. `en canonical UI -> uk faithful translation` tests cross-language fidelity;
2. `en canonical UI -> en plain-language adaptation` tests same-language simplification;
3. any `uk` plain-language form must preserve provenance for both transformations.

Readability metrics can identify surface load but cannot prove preservation of legal scope. User
testing can show comprehension or behaviour for a tested population; it does not confer authority.
High-stakes adaptation needs separate semantic review and behavioural fixtures.

Real institutions rely on bilingual drafters, translation services, terminology boards, commissions,
or courts. PolicyOS has no appointed holder for these functions. INT-R6 specifies a future process
shape without borrowing a fictitious institution:

- the required role is named;
- holder cardinality may be zero;
- a proposed high-stakes contested rendition with zero qualified holders would refuse for the governed
  purpose;
- appointing a holder later would change an assignment record, not the schema;
- any unblocked low-risk/source-view function must be independently established rather than inferred
  from research prose.

## Cross-survey synthesis

### Finding E-01 — authority is a relation, not a language property

`authoritative=true` cannot safely sit on a language tag alone. Authority belongs to a text/version
under a jurisdictional rule and purpose.

**Classification:** `external_evidence_convergence`

### Finding E-02 — English is admissible as UI source, not universal legal pivot

D4-A1's English-authored UI composes with a legal-content architecture that can anchor Ukrainian law
in Ukrainian and a future co-authentic regime in several languages. Requiring every legal concept to
be defined in English first would add a legally consequential pivot that co-authentic systems do not
contain.

**Classification:** `architectural_inference`

### Finding E-03 — semantic IDs need namespaces

A global unqualified ID risks fragmenting system governance per jurisdiction or forcing local legal
concepts into false equivalence. Namespaced system IDs, jurisdiction concept IDs, and explicit
mappings avoid both errors.

**Classification:** `protocol_requirement`

### Finding E-04 — proposition testing dominates string testing but remains population-bounded

Glossaries and catalogue parity are controls. A counterexample at proposition/action level refutes a
candidate; a finite passing population establishes only its declared bounded result and residual.

**Classification:** `external_evidence_convergence`

### Finding E-05 — adaptation needs its own result

A translation can be faithful and unreadable; an adaptation can be readable and authority-changing.
One boolean cannot represent both.

**Classification:** `protocol_requirement`

### Finding E-06 — missing adjudication capacity is a typed target state

The absence of an appointed holder is not permission to pass. In the target protocol it is a
purpose-scoped refusal naming the missing role. This is a contract requirement, not an implemented
repository capability.

**Classification:** `phased_deployment_requirement`

## Source register with durable locators

Links locate sources; they do not make the linked body a PolicyOS owner.

| source | jurisdiction/regime | exact span used | use in INT-R6 | evidence class |
|---|---|---|---|---|
| [Vienna Convention on the Law of Treaties](https://legal.un.org/ilc/texts/instruments/english/conventions/1_1_1969.pdf) | treaty interpretation | Article 33(1)–(4) | authentic texts, precedence, reconciliation | `primary_source` |
| [Council Regulation No 1](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:31958R0001) | European Union | Articles 1–5 | official-language publication regime | `primary_source` |
| [CJEU, Case 283/81, *CILFIT*](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:61981CJ0283) | European Union | paragraph 18 | equally authentic versions require comparison | `primary_source` |
| [CJEU, Case C-161/06, *Skoma-Lux*](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:62006CJ0161) | European Union | paragraphs 37–51 | official-language publication and enforceability | `primary_source` |
| [Constitution Act, 1982](https://laws-lois.justice.gc.ca/eng/const/) | Canada | section 18 | equal authority of federal enactment versions | `primary_source` |
| [Official Languages Act](https://laws-lois.justice.gc.ca/eng/acts/O-3.01/) | Canada | section 13 | equal authority of bilingual instruments | `primary_source` |
| [SCC, *R v Daoust*, 2004 SCC 6](https://scc-csc.lexum.com/scc-csc/scc-csc/en/item/2117/index.do) | Canada | paragraphs 26–30; item `2117` | shared-meaning method and its contextual limit | `primary_source` |
| [Swiss Compilations Act, SR 170.512](https://www.fedlex.admin.ch/eli/cc/2004/745/en) | Switzerland | Article 14 | equally binding enactment texts | `primary_source` |
| [Constitution of Ukraine](https://zakon.rada.gov.ua/laws/show/254%D0%BA/96-%D0%B2%D1%80#Text) | Ukraine | Article 10 | state-language context | `primary_source` |
| [Law of Ukraine No. 2704-VIII](https://zakon.rada.gov.ua/laws/show/2704-19#Text) | Ukraine | Articles 45–47 | language commission composition, quorum, decisions | `primary_source` |
| [ISO 704:2022](https://www.iso.org/standard/79077.html) | international standard | concept characteristics, definitions, concept systems | concept-oriented method | `regulated_practice` |
| [ISO 1087:2019](https://www.iso.org/standard/62330.html) | international standard | §§3.2.7, 3.4.1, 3.4.2 | concept/designation/term vocabulary | `regulated_practice` |
| [ISO 30042:2019](https://www.iso.org/standard/62510.html) | international standard | `conceptEntry/langSec/termSec` model | terminology interchange | `regulated_practice` |
| [ISO 17100:2015](https://www.iso.org/standard/59149.html) | international standard | published scope and process roles | translation workflow separation | `regulated_practice` |
| [ISO 24495-1:2023](https://www.iso.org/standard/78907.html) | international standard | Clause 4 | plain-language principles | `regulated_practice` |
| [Unicode Bidirectional Algorithm](https://www.unicode.org/reports/tr9/) | technical standard | algorithm and conformance clauses | bounded bidi admission evidence | `regulated_practice` |
| [W3C bidi guidance](https://www.w3.org/International/articles/inline-bidi-markup/uba-basics) | technical guidance | inline bidi isolation/ordering sections | rendered mixed-direction fixtures | `regulated_practice` |
| [Unicode CLDR](https://cldr.unicode.org/) | technical data standard | plural/locale-format data | target-locale grammar and formatting | `regulated_practice` |

## Evidence gaps retained

- Measured English-to-Ukrainian authority-semantic error rates across a representative governance
  corpus: `unknown`.
- A validated Ukrainian legal plain-language threshold predicting correct operator action: `unknown`.
- A universal reconciliation rule for co-authentic divergences: `not_applicable`; rules are
  jurisdiction-specific.
- A universal equivalence relation between jurisdictional legal concepts and PolicyOS system
  concepts: `not_applicable`.
- Evidence sufficient to admit a named RTL jurisdiction in PolicyOS today: `not_collected`; D4-A1
  remains `not_supported`.
