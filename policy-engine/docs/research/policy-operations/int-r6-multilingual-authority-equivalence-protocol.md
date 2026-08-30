# INT-R6 — Multilingual authority equivalence across UI, legal sources, and system semantics

## Research question and decision boundary

### Answer

The commissioned three-axis partition is **refined**, not rejected, into five dimensions with
explicit dependency edges rather than five pairwise-orthogonal coordinates:

1. **product UI locale** — D4-A1, settled: `en` authored, `uk` translated, `ru`
   `legacy_continuity_frozen`;
2. **authority text set** — one or more jurisdictionally authoritative text/version members;
3. **source-content rendition** — a language/script rendering with declared status and purpose;
4. **semantic namespace and canonical ID** — system-governance concepts, jurisdiction concepts,
   and explicit mappings;
5. **presentation variant** — canonical, plain-language, summary, explanatory, or accessibility
   form, always dependent on a named parent proposition and, where applicable, a parent rendition.

Script and direction are explicit admission properties derived from language/script, not proof of
authority. Jurisdiction scopes authority-text sets and concept namespaces and is never inferred from
locale. `PresentationVariant` is not independent of the content it transforms; its parent bindings
are part of its identity and evidence.

This architecture composes with D4-A1. It does not amend the product UI posture, appoint an
institution, add an RTL UI locale, or make English authoritative for Ukrainian law. The architect
early-stop trigger is **not activated**.

### Central invariants

- UI locale selects PolicyOS chrome only.
- A legal source is not a translation merely because another language version exists.
- Co-authentic texts form an authority set; no member is silently promoted to source.
- Display strings never act as semantic identifiers.
- English is not a mandatory legal pivot.
- Translation and plain-language adaptation are independently assessed.
- Missing adjudication capacity is represented by a typed refusal naming the missing role.
- A jurisdiction may be admitted by records only while its requirements fit the already admitted
  relation, vocabulary, evidence, and role envelope; a genuinely new semantic category remains a
  governance/schema question rather than being forced into data.

### Scope boundary

INT-R6 specifies the layer D4-A1 explicitly left separate: source-content rendering and
authority-semantic equivalence. It does not revisit `en`/`uk`/`ru` UI governance. A future public
UI-locale admission remains a D4-A1 event; admitting a jurisdictional source language does not itself
change the UI locale set.

Detailed architecture: [`int-r6/03-language-axis-partition.md`](int-r6/03-language-axis-partition.md).

## Repository baseline

### Measurement identity

The package baseline is `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`; the research package was
measured at `5e47c868c2c1d4d66fa11fcddcc972dbb55e95d3`. The earlier DS0 snapshot
reported 2,449 primitive string leaves in each catalogue, with `888 / 2,449 = 36.26%` of `uk`
and `1,963 / 2,449 = 80.16%` of `ru` byte-identical to `en`. Those values remain historical DS0
facts and are not relabelled as current.

The Stage-3 author-execution and independent-parser assertions are withdrawn. The published harness
is not treated as an executed artifact. The exact catalogue path and file-type denominator is
connector-observed: `3 JSON / 3 total files` under
`policy-engine/apps/runtime-dashboard/src/shared/i18n/locales/`.

The following leaf/identity values are recorded as `institutionally_supplied` under W4-K01:

| catalogue | supplied string leaves | supplied identity to `en` on shared paths |
|---|---:|---:|
| `en.json` | 2,618 | n/a |
| `uk.json` | 2,618 | 894 / 2,618 = 34.15% |
| `ru.json` | 2,449 | 1,936 / 2,449 = 79.05% |

The supplied walk reports 169 `en` paths absent from `ru`, zero `uk`-only paths, and zero `ru`-only
paths. These values are not Stage-3 or Stage-5 execution results, no independent author/auditor
measurement is claimed, and under W4-K01 they settle no zero. Exact path/blob observations and the
evidence boundary are recorded in
[`int-r6/01-repository-baseline.md`](int-r6/01-repository-baseline.md).

The unequal supplied denominators strengthen, rather than weaken, the research conclusion:
structural catalogue parity and semantic equivalence are different predicates. Active `en`/`uk`
path parity can coexist with a deliberately frozen `ru` denominator, while equal path sets still say
nothing about modality, scope, or operator action.

Identity has heterogeneous causes: untranslated copy, proper nouns/IDs, deliberate shared
terminology, or parity padding. It is a triage metric and cannot prove translation quality.

### What structural parity proves

The exact contract coordinate
`policy-engine/apps/runtime-dashboard/src/shared/i18n/parity.test.ts` is admitted only as
structural evidence: matching active catalogue paths and any leaf/placeholder shape it explicitly
checks. It cannot prove preservation of modality, negation, exceptions, time, uncertainty, status
grade, grammatical composition, or operator action.

### Remaining baseline limitations

The exact catalogue path/blob/file denominator is connector-established; independent leaf/identity
execution remains open. The following remain explicit implementation/specification entry conditions
rather than repository absences:

- an independent author/auditor execution of the current catalogue leaf/identity census;
- a complete fragment/message-composition inventory;
- a definition-to-render census for every high-stakes status/restriction family;
- a complete producer-to-render walk for proposed MAEP certificates and refusals;
- source-content rendering/decoupling implementation coordinates;
- a complete typed owner map for every proposed relation, outcome, and refusal reason;
- tracked-file denominators for any future repository-wide zero claim.

The delivery-repair predecessor claims were separately reconciled by restore, recomputation, or
retraction in the predecessor→successor matrix in
[`int-r6/01-repository-baseline.md`](int-r6/01-repository-baseline.md). Code-search misses are not
used as repository-wide absence evidence.
## External evidence

Five commissioned surveys were treated as external evidence only. They do not establish repository
capability or PolicyOS authority.

### Designated source and co-authentic text are different regimes

Designated-source systems support a directional source-to-rendition protocol: the target is
constrained by the source and cannot acquire authority merely by being accurate. Co-authentic regimes
falsify a universal source/translation edge. Vienna Convention Article 33, EU multilingual
interpretation, Canadian federal bilingual legislation, and Swiss multilingual practice show that
several texts may participate in legal authority without an English source.

The disagreement is preserved as proposed record relations:

```text
single_designated
multiple_coauthentic
parallel_official_non_equal
informative_only
```

These are candidate values requiring mapping to an existing owner or explicit registration by a
competent later stage; they are not a second status lattice and are not imported universal legal
categories.

### English-to-Ukrainian authority semantics

High-risk mappings include obligation/permission/prohibition, negation scope, conditions and
exceptions, quantifiers, temporal boundaries, numerical inclusivity, uncertainty, actor identity,
and Ukrainian morphology after interpolation. The decisive question is not whether words look
equivalent but whether source and target license, require, and forbid the same actions in the
**declared test population**.

Direct empirical estimates of English-to-Ukrainian authority-semantic error rates remain `unknown`;
evidence from other language pairs is not silently substituted.

### Terminology and status grades

Concept-oriented terminology practice supports IDs separate from designations, versioned glossary
releases, usage status, forbidden synonyms, and explicit mappings. It does not authorise a second
PolicyOS status lattice. Existing registered statuses and refusals remain the semantic source; local
terms render their IDs.

`stale`, `superseded`, and `withdrawn` may all block present reliance but have different provenance
and remediation. A generic translated “invalid” destroys operator and machine semantics.

### Adaptation and adjudication

Plain-language adaptation is a separate transformation from translation. A text can be faithful but
unreadable, or readable but authority-changing. Separate results and provenance are mandatory.

Real regimes often rely on institutions that PolicyOS deliberately does not yet have. INT-R6 specifies
role/process shape without inventing holders. In the target protocol, a required high-stakes decision
with zero eligible holders would return a typed refusal limited to the governed purpose. This research
does not claim that the current repository already produces that refusal or implements the source,
draft, glossary, and fixture surfaces described by the model.

Full evidence synthesis and jurisdiction limits: [`int-r6/02-external-evidence.md`](int-r6/02-external-evidence.md).

## Findings

The consolidated register contains 30 classified findings. The load-bearing conclusions are:

| ID | conclusion | classification |
|---|---|---|
| F-001 | D4-A1 composes with the target architecture | `research_conclusion` |
| F-002 | the language partition requires five dimensions and explicit dependency edges | `architecture_decision_candidate` |
| F-004 | authority needs a text set, not universal `source_language` | `external_evidence_convergence` |
| F-005 | mandatory English legal pivot is rejected | `architecture_decision_candidate` |
| F-007 | system and jurisdiction concepts need separate namespaces and mappings | `protocol_requirement` |
| F-009 | catalogue parity cannot contribute semantic standing | `bounded_repo_fact` |
| F-011 | high-stakes composition must be proposition-level or typed | `protocol_requirement` |
| F-012 | action-profile counterexamples can refute a candidate inside a declared population | `protocol_requirement` |
| F-013 | the five named statuses/restrictions require ID-preserving rendering | `red_first_requirement` |
| F-015 | translation and adaptation require separate decisions | `protocol_requirement` |
| F-016 | MACHINE/Lex projections must consume IDs and certificate provenance | `protocol_requirement` |
| F-018 | co-authentic divergence remains representable | `protocol_requirement` |
| F-019 | zero-holder adjudication is representable as a typed refusal state | `phased_deployment_proof` |
| F-021 | N+1 can be data-only only inside the admitted model/vocabulary envelope | `phased_deployment_proof` |
| F-022 | RTL source rendering is separate from RTL public UI | `scope_boundary` |
| F-024 | the Ukraine scenario is an architecture fixture, not a present capability claim | `architecture_demonstration` |
| F-027 | search misses do not establish repository absence | `measurement_limitation` |
| F-030 | no UI-posture early stop is required | `research_conclusion` |

Every finding, evidence basis, classification, and accountable-owner disposition is recorded in
[`int-r6/06-findings-standing-and-pattern-pass.md`](int-r6/06-findings-standing-and-pattern-pass.md).

## Language-dimension partition

### Architecture

```text
ui_locale ─────────────── selects PolicyOS-authored chrome

jurisdiction_id
  └─ authority_text_set ─ contains one or more authentic/versioned members
       └─ content_rendition ─ language, script, status, purpose, certificate
            └─ presentation_variant ─ parent proposition/rendition + transformation

semantic_namespace + semantic_id ─ drives logic, status, refusal, MACHINE, Lex
```

No arrow runs from `ui_locale` to authority selection. `presentation_variant` cannot exist without
its parent proposition and, where it transforms a rendition, its parent rendition.

### Claim placement

- A PolicyOS refusal code is a `system_semantic_id`; its evidence may cite a jurisdictional rule.
- A legal act type normally remains a `jurisdiction_concept_id` with explicit mappings.
- A δ-bound is system-governed when it belongs to a PolicyOS model/certificate and
  jurisdiction-governed when imposed by law or competent decision.
- A legal authority ceiling and a PolicyOS safety ceiling are two claims with different issuers,
  even when displayed together.
- Registered standing/status labels remain system concepts; a jurisdictional legal status is mapped,
  not merged.

### Ukraine architecture fixture

The record model represents a Ukrainian statute anchored to its Ukrainian authoritative text.
English and Ukrainian UI are separate selectors that must not alter that authority. An informative
English rendition may be represented with explicit provenance and use limits. A Russian source
rendition, if separately admitted for read-only use, sits on the rendition dimension and cannot
reactivate the frozen Russian UI catalogue. These are architecture claims; runtime production and
rendering remain absent/unallocated.

### Co-authentic N+1 fixture

The record model represents a Canadian federal act with English and French co-authentic members,
neither treated as universal source. A material divergence invokes a jurisdiction-specific rule or a
named role. With zero eligible holders, the proposed governed derivation refuses while the authority
set remains historically representable. Whether current product surfaces display both texts is a
separate implementation fact and is not claimed here.

### English pivot

Rejected for legal concept definition, co-authentic equivalence, authority generation, or scope
decisions. Admitted for D4-A1 UI authoring, informative operator aid, indexing, provisional glosses,
and explanatory variants with explicit provenance/use limits.

### RTL

D4-A1 remains `not_supported` for RTL UI. A named RTL jurisdiction could be considered only through
an evidence pack covering authoritative scripts, Unicode normalisation, shaping, bidi isolation,
logical focus/reading order, locale formatting, copy/search/export, spoofing controls, accessibility,
and red-first mixed-direction fixtures. Source-content RTL admission is a separate future capability
question and does not imply RTL UI.

## MultilingualAuthorityEquivalenceProtocol

`MultilingualAuthorityEquivalenceProtocol` (MAEP) is a proposed contract. If implemented and admitted,
it would issue only proposition-, purpose-, version-, time-, and **tested-population-bounded**
certificates.

### Pipeline

1. classify object and transformation;
2. bind designated source or co-authentic authority set;
3. normalise the authority-semantic frame;
4. bind registered system IDs and jurisdiction concept IDs;
5. select an immutable controlled-glossary release;
6. render the whole proposition or typed message function;
7. run structural, glossary, modal, scope, temporal, numeric, uncertainty, projection, and bidi checks;
8. compare allowed/required/forbidden action profiles over the complete declared fixture/context
   denominator;
9. enforce the semantic status-upgrade ban;
10. assess plain-language adaptation independently;
11. apply predeclared risk and adjudication requirements;
12. issue a population-bounded certificate or typed failure/refusal;
13. project source IDs, residuals, and provenance into UI, runtime, MACHINE, and Lex;
14. invalidate on source, rendition, vocabulary, glossary, admission, decision, purpose, fixture,
   or declared-population changes.

### Canonical semantic frame

```text
actor
act_type
object
modality
conditions[]
exceptions[]
quantifiers[]
temporal_scope
spatial_scope
numeric_constraints[]
evidence_qualifiers[]
status_ids[]
consequence
```

For a designated source `s`, target `t`, and every context `c` in a versioned declared population
`C_test`, the candidate must preserve:

```text
Allowed(s,c)   = Allowed(t,c)
Required(s,c)  = Required(t,c)
Forbidden(s,c) = Forbidden(t,c)
```

A single material target-only permission, lost prohibition, lost condition, actor switch, boundary
change, or status upgrade refutes the candidate for that purpose. Absence of a counterexample within
`C_test` does **not** prove unrestricted semantic equivalence outside `C_test`; the residual and
excluded context classes remain explicit certificate fields.

### Controlled glossary

Entries bind semantic/concept IDs to language-specific designations, usage status, forbidden
synonyms, confusables, grammatical notes, examples, negative examples, sources, version, and
effective interval. Term correctness cannot override a proposition-level failure.

### Human adjudication with zero holders

Role definition, appointment, and decision are separate records. In the proposed protocol, a
high-risk contested rendering with no eligible holder would return a structured refusal naming
`required_role_id`, holder count, blocked purpose, modeled unblocked functions, and resolution
requirements. Later appointment would change institutional records, not the language model. No such
appointment or current producer is asserted by this research.

### Certificate

A positive certificate must bind:

- exact source anchor/digest and target rendition digest;
- proposition and governed purpose IDs;
- authority-set relation and jurisdiction rule version;
- semantic-frame, semantic-ID, glossary, and vocabulary versions;
- the complete declared fixture/context population, its digest and cardinality;
- per-check results and reviewer/adjudication basis;
- separate translation and adaptation results;
- explicit exclusions, unresolved context classes, and residual uncertainty;
- validity interval and invalidators.

It says only that no prohibited difference was found over that declared population under those
versions and evidence. It does not declare legal authenticity, universal equivalence, or correctness
outside the tested denominator.

Full protocol: [`int-r6/04-multilingual-authority-equivalence-protocol.md`](int-r6/04-multilingual-authority-equivalence-protocol.md).

## Red-first falsifiers and regression fixtures

### Binding falsifier 1 — `limited` upgraded

Source: limited, planning-only, interval-bound, explicitly not confirmed.

Defective target: Ukrainian wording equivalent to “confirmed with a caveat”, with interval and
non-confirmation removed.

Required red result: target licenses planning outside the source interval and changes the
status/action profile. MAEP must fail it before a corrected candidate can pass the same declared
fixture.

### Binding falsifier 2 — `may_not_use_for` weakened

Source: evidence may not be used to authorise payment.

Defective target: Ukrainian “not recommended for agreeing a payment”.

Required red result: prohibition becomes recommendation and possibly changes act type. MAEP must
detect a target-only licensed action.

### Binding falsifier 3 — negative states collapsed

Source IDs: `stale`, `superseded`, `withdrawn`.

Defective target: one generic “invalid” rendering and one machine state.

Required red result: ID cardinality, provenance, remedy, and successor/withdrawal semantics are lost.

### Regression matrix

The specified suite covers negation and quantifier scope; actor/duty-bearer; nested exceptions;
start/end/duration; inclusive/exclusive thresholds; interval-to-point collapse; `unknown` versus
zero/missing/not-applicable; evidence standing; modality; conjunction/disjunction; Ukrainian
case/numeral morphology; fragment scope and accessibility reading order; plain-language weakening;
co-authentic divergence; English-pivot loss; MACHINE/Lex label-only projections; mixed RTL;
confusables; certificate purpose/freshness; and zero-holder refusal.

Each fixture stores source frame/IDs, defective and corrected target candidates, purpose,
old-mechanism expected result, MAEP expected result/reason, counterexample contexts,
vocabulary/glossary versions, accessibility expectation, and machine projection expectation. The
fixture suite is a falsification instrument, not a proof of unrestricted equivalence.

Full fixture definitions: [`int-r6/05-red-first-fixtures-and-phased-deployment.md`](int-r6/05-red-first-fixtures-and-phased-deployment.md).

## Phased deployment and operational closure

### Phase 0 — zero appointed holders

At research stage, the target model can describe Ukrainian authority independently of product UI,
informative renditions, semantic frames, IDs, glossary drafts, mappings, red fixtures, and a
vacant-holder refusal. These are contract and fixture specifications. The current capability remains
`absent/unallocated`: this package does not claim that runtime surfaces display, execute, certify, or
return any MAEP object.

The proposed refusal is purpose-scoped. The model records source viewing, draft comparison, glossary
work, and fixture authoring as potentially unblocked functions; their current implementation status
must be established independently rather than inferred from this research.

### First real-user deployment

A later implementation would need real propositions, Ukrainian operator fixtures, measured
comprehension/error evidence, glossary release candidates, and observed role demand. Institutional
absence must remain visible and must not be converted into synthetic approval.

### Later appointments

Appointment records would add holder identity, competence, scope, conflicts, and validity. A
previously vacant role could then receive a decision under the same model. This research neither
appoints the holder nor proves the surrounding capability chain.

### Jurisdiction N+1

A jurisdiction admission record may reuse existing shapes only when the jurisdiction's authority
modes, sources, scripts, concept mappings, rendition relations, roles, and evidence fit the admitted
envelope. A new relation or semantic category is routed to its canonical governance owner or remains
explicitly unallocated; it must not be squeezed into an existing value merely to preserve a
“data-only” claim.

### Operational closure

- **Inputs:** D4 capability, jurisdiction admission, authority-text set, semantic frame/IDs,
  rendition/variant, glossary, purpose/risk, evidence, role state.
- **Outputs:** population-bounded certificate, typed failure/refusal, co-authentic divergence, or
  routed vocabulary/architect gap.
- **Fail-closed boundary:** the governed purpose only; separately established functions may remain
  available.
- **Freshness:** bind versions/digests/validity; preserve history while blocking current use after
  invalidation.
- **Observability:** evaluation ID, source/rendition/certificate versions, purpose, complete tested
  denominator, checks, counterexamples, residual, role/appointment, reason, separately established
  unblocked functions, invalidation/successor.
- **Rollback:** cannot reactivate withdrawn source content or a certificate invalidated by semantic
  defect.
- **Acceptance evidence:** three falsifiers red then green; complete declared regression denominator;
  no governed string comparison; UI/source decoupling; MACHINE/Lex ID round-trip; zero-holder
  refusal; Ukraine fixture; bounded co-authentic and RTL source fixtures; complete-tree baseline
  closure; and explicit residuals.

## Standing, classification, and open questions

### W4-K05 standing authority

This report publishes no parallel standing fields. The package's single W4-K05 tuple is in
[`int-r6/06-findings-standing-and-pattern-pass.md`](int-r6/06-findings-standing-and-pattern-pass.md).
An audit verdict is not a standing value, and Stage 3 does not move any axis.

### Classification rule

Findings use explicit classes including `ratified_repo_fact`, `bounded_repo_fact`,
`reported_measurement`, `measurement_limitation`, `external_evidence_convergence`,
`architectural_inference`, `architecture_decision_candidate`, `protocol_requirement`,
`red_first_requirement`, `phased_deployment_proof`, `scope_boundary`, and `evidence_gap`. No
classification token is presented as a W4-K05 standing value.

### Open/routed questions

- map every proposed relation/result/reason to an existing namespaced owner or leave it explicitly
  unallocated;
- build a real English-to-Ukrainian high-stakes corpus and behavioural ground truth;
- decide role qualifications/appointments only when real-user evidence exists;
- supply per-jurisdiction co-authentic reconciliation rules;
- admit a named RTL jurisdiction only with its evidence pack;
- decide cryptographic certificate/trust details in security architecture.

### Explicit D4 statement

D4-A1 **composes** with INT-R6 and does not require revisit in this pass. The UI posture itself is not
widened or reinterpreted.

## Pattern Pass and sources

### Pattern Pass

Run and recorded. Routed candidates:

- Axis-separated language context;
- Authority Text Set;
- Purpose-bounded semantic rendition certificate;
- Vacant-holder typed refusal;
- No-upgrade action-profile gate;
- Translation/adaptation double gate;
- Bounded data-only jurisdiction admission.

Rejected anti-patterns:

- catalogue identity-rate threshold as translation quality;
- universal English canonical legal definition;
- locale-specific duplicate status lattice.

The pattern register was not edited. Review should determine whether several candidates are facets of
one broader governed-semantic-rendition pattern.

Full pass: [`int-r6/06-findings-standing-and-pattern-pass.md`](int-r6/06-findings-standing-and-pattern-pass.md).

### Principal external sources and durable spans

- [Vienna Convention on the Law of Treaties, Article 33](https://legal.un.org/ilc/texts/instruments/english/conventions/1_1_1969.pdf) — Article 33(1)–(4).
- [Council Regulation No 1 determining EEC language use](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:31958R0001) — Articles 1–5.
- [CJEU Case 283/81, CILFIT](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:61981CJ0283) — paragraph 18.
- [CJEU Case C-161/06, Skoma-Lux](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:62006CJ0161) — paragraphs 37–51.
- [Canada, Constitution Act, 1982](https://laws-lois.justice.gc.ca/eng/const/) — section 18.
- [Supreme Court of Canada, *R v Daoust*, 2004 SCC 6](https://scc-csc.lexum.com/scc-csc/scc-csc/en/item/2117/index.do) — paragraphs 26–30; SCC item `2117`.
- [Swiss Compilations Act, SR 170.512](https://www.fedlex.admin.ch/eli/cc/2004/745/en) — Article 14.
- [Constitution of Ukraine](https://zakon.rada.gov.ua/laws/show/254%D0%BA/96-%D0%B2%D1%80#Text) — Article 10.
- [Law of Ukraine No. 2704-VIII](https://zakon.rada.gov.ua/laws/show/2704-19#Text) — Articles 45–47.
- [ISO 704:2022](https://www.iso.org/standard/79077.html) — concept characteristics, definitions, and concept systems.
- [ISO 1087:2019](https://www.iso.org/standard/62330.html) — §§3.2.7, 3.4.1, 3.4.2.
- [ISO 30042:2019 (TBX)](https://www.iso.org/standard/62510.html) — `conceptEntry`, `langSec`, `termSec` model.
- [ISO 17100:2015](https://www.iso.org/standard/59149.html) — published scope and process requirements.
- [ISO 24495-1:2023](https://www.iso.org/standard/78907.html) — Clause 4 governing principles.
- [Unicode Bidirectional Algorithm](https://www.unicode.org/reports/tr9/) — current algorithm clauses.
- [W3C bidirectional text guidance](https://www.w3.org/International/articles/inline-bidi-markup/uba-basics) — inline-bidi isolation guidance.
- [Unicode CLDR](https://cldr.unicode.org/) — plural and locale-format data.

### Delivery inventory

The original eight-file package consists of this substantive report; the retained navigation scaffold
[`int-r6-multilingual-authority-equivalence.md`](int-r6-multilingual-authority-equivalence.md); and
the six numbered appendices listed below. Stage 3 adds one justified Markdown artifact,
[`int-r6/amendment-ledger.md`](int-r6/amendment-ledger.md), because the closed 14-row disposition
register, preserve-property checks, NO_GO checks, and connector receipts are amendment evidence rather
than Stage-1 research claims.

- [`int-r6/01-repository-baseline.md`](int-r6/01-repository-baseline.md);
- [`int-r6/02-external-evidence.md`](int-r6/02-external-evidence.md);
- [`int-r6/03-language-axis-partition.md`](int-r6/03-language-axis-partition.md);
- [`int-r6/04-multilingual-authority-equivalence-protocol.md`](int-r6/04-multilingual-authority-equivalence-protocol.md);
- [`int-r6/05-red-first-fixtures-and-phased-deployment.md`](int-r6/05-red-first-fixtures-and-phased-deployment.md);
- [`int-r6/06-findings-standing-and-pattern-pass.md`](int-r6/06-findings-standing-and-pattern-pass.md).