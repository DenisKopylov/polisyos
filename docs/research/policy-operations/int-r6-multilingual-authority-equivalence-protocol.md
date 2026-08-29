# INT-R6 — Multilingual authority equivalence across UI, legal sources, and system semantics

## Research question and decision boundary

### Answer

The commissioned three-axis partition is **refined**, not rejected:

1. **product UI locale** — D4-A1, settled: `en` authored, `uk` translated, `ru` `legacy_continuity_frozen`;
2. **authority text set** — one or more jurisdictionally authoritative text/version members;
3. **source-content rendition** — a language/script rendering with declared status and purpose;
4. **semantic namespace and canonical ID** — system-governance concepts, jurisdiction concepts, and explicit mappings;
5. **presentation variant** — canonical, plain-language, summary, explanatory, or accessibility form.

Script and direction are explicit admission capabilities derived from language/script, not proof of authority. Jurisdiction scopes authority-text sets and concept namespaces and is never inferred from locale.

This architecture composes with D4-A1. It does not amend the product UI posture, appoint an institution, add an RTL UI locale, or make English authoritative for Ukrainian law. The architect early-stop trigger is **not activated**.

### Central invariants

- UI locale selects PolicyOS chrome only.
- A legal source is not a translation merely because another language version exists.
- Co-authentic texts form an authority set; no member is silently promoted to source.
- Display strings never act as semantic identifiers.
- English is not a mandatory legal pivot.
- Translation and plain-language adaptation are independently assessed.
- Missing adjudication capacity yields a typed refusal naming the missing role.
- Jurisdiction N+1 is admitted by evidence and records, not a language-specific schema change.

### Scope boundary

INT-R6 specifies the layer D4-A1 explicitly left separate: source-content rendering and authority-semantic equivalence. It does not revisit `en`/`uk`/`ru` UI governance. A future public UI-locale admission remains a D4-A1 event; admitting a jurisdictional source language does not itself change the UI locale set.

Detailed architecture: [`int-r6/03-language-axis-partition.md`](int-r6/03-language-axis-partition.md).

## Repository baseline

### Measurement identity

The fixed baseline is `dc7bdf79a`. The prior DS0 measurement reported 2,449 primitive string leaves in each of the three catalogues, with 36.26% of `uk` and 80.16% of `ru` byte-identical to `en`. The measurement party for those figures is **DS0**, not INT-R6.

The integer numerators consistent with the rounded shares are a commissioned-researcher calculation:

- `888 / 2,449 = 36.2596978…%`;
- `1,963 / 2,449 = 80.1551654…%`.

These calculations recover likely DS0 numerators; they are not a current-tree remeasurement. Identity has heterogeneous causes: untranslated copy, proper nouns/IDs, deliberate shared terminology, or parity padding. It is a triage metric and cannot prove translation quality.

### What structural parity proves

The contract coordinate `shared/i18n/parity.test.ts` is admitted only as structural evidence: matching catalogue paths and any leaf/placeholder shape it explicitly checks. It cannot prove preservation of modality, negation, exceptions, time, uncertainty, status grade, grammatical composition, or operator action.

### Current baseline limitation

Ordinary Git transport in the execution container failed at DNS resolution. Connector writes were used, but the connector result stream available to this pass did not expose a model-readable complete tracked-tree payload. INT-R6 therefore does **not** relabel DS0 figures as a fresh measurement and does **not** treat code-search misses as repository-wide absence.

The following remain explicit acceptance/next-stage entry conditions:

- exact catalogue coordinates and current leaf/identity counts from a complete walk;
- runtime capability contract and frontend validator coordinates;
- definition-to-use walk for `locale_preference` and whether `ru` still crosses into run requests;
- complete fragment/message-composition inventory;
- definition-to-render coordinates for `limited`, `may_not_use_for`, `stale`, `superseded`, `withdrawn`;
- MACHINE-twin and Lex-projection coordinates;
- source-content rendering/decoupling coordinates;
- tracked-file denominator and executor for every set-level zero.

This is classified as `measurement_limitation`, not as repository absence. The exact command ledger and baseline classification are in [`int-r6/01-repository-baseline.md`](int-r6/01-repository-baseline.md).

## External evidence

Five commissioned surveys were treated as external evidence only. They do not establish repository capability or PolicyOS authority.

### Designated source and co-authentic text are different regimes

Designated-source systems support a directional source-to-rendition protocol: the target is constrained by the source and cannot acquire authority merely by being accurate. Co-authentic regimes falsify a universal source/translation edge. Vienna Convention Article 33, EU multilingual interpretation, Canadian federal bilingual legislation, and Swiss multilingual practice show that several texts may participate in legal authority without an English source.

The disagreement is preserved in the model:

```text
single_designated
multiple_coauthentic
parallel_official_non_equal
informative_only
```

These are candidate record values requiring vocabulary review, not imported universal legal categories.

### English-to-Ukrainian authority semantics

High-risk mappings include obligation/permission/prohibition, negation scope, conditions and exceptions, quantifiers, temporal boundaries, numerical inclusivity, uncertainty, actor identity, and Ukrainian morphology after interpolation. The decisive question is not whether words look equivalent but whether source and target license, require, and forbid the same actions in material contexts.

Direct empirical estimates of English-to-Ukrainian authority-semantic error rates remain `unknown`; evidence from other language pairs is not silently substituted.

### Terminology and status grades

Concept-oriented terminology practice supports IDs separate from designations, versioned glossary releases, usage status, forbidden synonyms, and explicit mappings. It does not authorise a second PolicyOS status lattice. Existing registered statuses and refusals remain the semantic source; local terms render their IDs.

`stale`, `superseded`, and `withdrawn` may all block present reliance but have different provenance and remediation. A generic translated “invalid” destroys operator and machine semantics.

### Adaptation and adjudication

Plain-language adaptation is a separate transformation from translation. A text can be faithful but unreadable, or readable but authority-changing. Separate results and provenance are mandatory.

Real regimes often rely on institutions that PolicyOS deliberately does not yet have. INT-R6 adopts role/process shape without inventing holders: a required high-stakes decision with zero eligible holders refuses, while source viewing, draft comparison, glossary work, and fixtures remain operational.

Full evidence synthesis and jurisdiction limits: [`int-r6/02-external-evidence.md`](int-r6/02-external-evidence.md).

## Findings

The consolidated register contains 30 classified findings. The load-bearing conclusions are:

| ID | conclusion | classification |
|---|---|---|
| F-001 | D4-A1 composes with the target architecture | `research_conclusion` |
| F-002 | the language partition requires five coordinates | `architecture_decision_candidate` |
| F-004 | authority needs a text set, not universal `source_language` | `external_evidence_convergence` |
| F-005 | mandatory English legal pivot is rejected | `architecture_decision_candidate` |
| F-007 | system and jurisdiction concepts need separate namespaces and mappings | `protocol_requirement` |
| F-009 | catalogue parity cannot contribute semantic standing | `bounded_repo_fact` |
| F-011 | high-stakes composition must be proposition-level or typed | `protocol_requirement` |
| F-012 | action-profile counterexamples decide equivalence | `protocol_requirement` |
| F-013 | the five named statuses/restrictions require ID-preserving rendering | `red_first_requirement` |
| F-015 | translation and adaptation require separate decisions | `protocol_requirement` |
| F-016 | MACHINE/Lex must consume IDs and certificate provenance | `protocol_requirement` |
| F-018 | co-authentic divergence remains representable | `protocol_requirement` |
| F-019 | zero-holder adjudication is a typed refusal state | `phased_deployment_proof` |
| F-021 | N+1 can be data-only at the model level | `phased_deployment_proof` |
| F-022 | RTL source rendering is separate from RTL public UI | `scope_boundary` |
| F-024 | Ukraine works now under the refined model | `architecture_demonstration` |
| F-027 | search misses do not establish repository absence | `measurement_limitation` |
| F-030 | no UI-posture early stop is required | `research_conclusion` |

Every finding, evidence basis, classification, and route is recorded in [`int-r6/06-findings-standing-and-pattern-pass.md`](int-r6/06-findings-standing-and-pattern-pass.md).

## Language-axis partition

### Architecture

```text
ui_locale ─────────────── selects PolicyOS-authored chrome

jurisdiction_id
  └─ authority_text_set ─ contains one or more authentic/versioned members
       └─ content_rendition ─ language, script, status, purpose, certificate

semantic_namespace + semantic_id ─ drives logic, status, refusal, MACHINE, Lex

presentation_variant ─ canonical / translated / adapted / explanatory
```

No arrow runs from `ui_locale` to authority selection.

### Claim placement

- A PolicyOS refusal code is a `system_semantic_id`; its evidence may cite a jurisdictional rule.
- A legal act type normally remains a `jurisdiction_concept_id` with explicit mappings.
- A δ-bound is system-governed when it belongs to a PolicyOS model/certificate and jurisdiction-governed when imposed by law or competent decision.
- A legal authority ceiling and a PolicyOS safety ceiling are two claims with different issuers, even when displayed together.
- Registered standing/status labels remain system concepts; a jurisdictional legal status is mapped, not merged.

### Ukraine today

A Ukrainian statute is anchored to its Ukrainian authoritative text. English and Ukrainian UI can both display that source and an explicitly informative English rendition. Russian source content, when admitted for read-only use, sits on the rendition axis and does not reactivate the frozen Russian UI catalogue.

### Co-authentic N+1

A Canadian federal act can be represented with English and French co-authentic members, neither treated as universal source. A material divergence invokes the jurisdiction's reconciliation rule or a named role; with zero eligible holders, the derived governed claim refuses while both authentic texts remain viewable.

### English pivot

Rejected for legal concept definition, co-authentic equivalence, authority generation, or scope decisions. Admitted for D4-A1 UI authoring, informative operator aid, indexing, provisional glosses, and explanatory variants with explicit provenance/use limits.

### RTL

D4-A1 remains `not_supported` for RTL UI. A named RTL jurisdiction can be admitted through an evidence pack covering authoritative scripts, Unicode normalisation, shaping, bidi isolation, logical focus/reading order, locale formatting, copy/search/export, spoofing controls, accessibility, and red-first mixed-direction fixtures. Source-content RTL capability may be admitted separately without claiming RTL UI.

## MultilingualAuthorityEquivalenceProtocol

`MultilingualAuthorityEquivalenceProtocol` (MAEP) issues only proposition-, purpose-, version-, and time-bounded certificates.

### Pipeline

1. classify object and transformation;
2. bind designated source or co-authentic authority set;
3. normalise the authority-semantic frame;
4. bind registered system IDs and jurisdiction concept IDs;
5. select an immutable controlled-glossary release;
6. render the whole proposition or typed message function;
7. run structural, glossary, modal, scope, temporal, numeric, uncertainty, projection, and bidi checks;
8. compare allowed/required/forbidden action profiles in boundary contexts;
9. enforce the semantic status-upgrade ban;
10. assess plain-language adaptation independently;
11. apply predeclared risk and adjudication requirements;
12. issue a purpose-bounded certificate or typed failure/refusal;
13. enforce certificate/source/ID invariants in UI, runtime, MACHINE, and Lex;
14. invalidate on source, rendition, vocabulary, glossary, admission, decision, purpose, or fixture changes.

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

For a designated source `s` and target `t`, material contexts `c` must preserve:

```text
Allowed(s,c)   = Allowed(t,c)
Required(s,c)  = Required(t,c)
Forbidden(s,c) = Forbidden(t,c)
```

A single material target-only permission, lost prohibition, lost condition, actor switch, boundary change, or status upgrade fails the target for that purpose.

### Controlled glossary

Entries bind semantic/concept IDs to language-specific designations, usage status, forbidden synonyms, confusables, grammatical notes, examples, negative examples, sources, version, and effective interval. Term correctness cannot override a proposition-level failure.

### Human adjudication with zero holders

Role definition, appointment, and decision are separate records. A high-risk contested rendering with no eligible holder returns a structured refusal naming `required_role_id`, holder count, blocked purpose, unblocked functions, and resolution requirements. Later appointment changes records, not MAEP's model.

### Certificate

A certificate binds source anchors/digests, rendition digest, authority-set mode, purpose IDs, semantic-frame/ID/glossary/vocabulary versions, fixture evidence, separate translation/adaptation results, adjudication record, validity interval, and invalidators. It does not declare the rendition legally authentic.

Full protocol: [`int-r6/04-multilingual-authority-equivalence-protocol.md`](int-r6/04-multilingual-authority-equivalence-protocol.md).

## Red-first falsifiers and regression fixtures

### Binding falsifier 1 — `limited` upgraded

Source: limited, planning-only, interval-bound, explicitly not confirmed.

Defective target: Ukrainian wording equivalent to “confirmed with a caveat”, with interval and non-confirmation removed.

Required red result: target licenses planning outside the source interval and changes the status/action profile. MAEP must fail it before a corrected candidate can pass.

### Binding falsifier 2 — `may_not_use_for` weakened

Source: evidence may not be used to authorise payment.

Defective target: Ukrainian “not recommended for agreeing a payment”.

Required red result: prohibition becomes recommendation and possibly changes act type. MAEP must detect a target-only licensed action.

### Binding falsifier 3 — negative states collapsed

Source IDs: `stale`, `superseded`, `withdrawn`.

Defective target: one generic “invalid” rendering and one machine state.

Required red result: ID cardinality, provenance, remedy, and successor/withdrawal semantics are lost.

### Regression matrix

The specified suite covers negation and quantifier scope; actor/duty-bearer; nested exceptions; start/end/duration; inclusive/exclusive thresholds; interval-to-point collapse; `unknown` versus zero/missing/not-applicable; evidence standing; modality; conjunction/disjunction; Ukrainian case/numeral morphology; fragment scope and accessibility reading order; plain-language weakening; co-authentic divergence; English-pivot loss; MACHINE/Lex label-only projections; mixed RTL; confusables; certificate purpose/freshness; and zero-holder refusal.

Each fixture stores source frame/IDs, defective and corrected target candidates, purpose, old-mechanism expected result, MAEP expected result/reason, counterexample contexts, vocabulary/glossary versions, accessibility expectation, and machine projection expectation.

Full fixture definitions: [`int-r6/05-red-first-fixtures-and-phased-deployment.md`](int-r6/05-red-first-fixtures-and-phased-deployment.md).

## Phased deployment and operational closure

### Phase 0 — now, zero appointed holders

The system can represent Ukrainian authoritative sources independently of English/Ukrainian UI; show informative renditions with provenance; prepare semantic frames, IDs, glossary drafts, mappings, and red fixtures; run automated checks; and return typed high-stakes vacancy refusals. It cannot attribute adjudication to a fictitious body, promote informative renditions, or claim RTL UI.

### First real-user deployment

Add real propositions, Ukrainian operator fixtures, measured comprehension/error evidence, glossary release candidates, and actual role demand. Institutional absence remains visible and does not gate unrelated low-risk functionality.

### Later appointments

Appointment records add holder identity, competence, scope, conflicts, and validity. A previously vacant role can now receive a decision using the same MAEP records and fixtures. No schema change occurs.

### Jurisdiction N+1

Add a jurisdiction admission record containing source languages/scripts/directions, authority modes, publishers/authenticity evidence, divergence rule, jurisdiction concept namespace/mappings, rendition statuses, role definitions/appointments, RTL evidence where applicable, real-instrument fixtures, and admission decision. Multi-authentic and RTL jurisdictions use existing record shapes.

### Operational closure

- **Inputs:** D4 capability, jurisdiction admission, authority-text set, semantic frame/IDs, rendition/variant, glossary, purpose/risk, evidence, role state.
- **Outputs:** certificate, typed failure/refusal, co-authentic divergence, or routed vocabulary/architect gap.
- **Fail-closed boundary:** the governed purpose only; explicitly listed source-viewing/draft functions may remain available.
- **Freshness:** bind versions/digests/validity; preserve history while blocking current use after invalidation.
- **Observability:** evaluation ID, source/rendition/certificate versions, purpose, checks, counterexamples, role/appointment, reason, unblocked functions, invalidation/successor.
- **Rollback:** cannot reactivate withdrawn source content or a certificate invalidated by semantic defect.
- **Acceptance evidence:** three falsifiers red then green; full regression suite; no governed string comparison; UI/source decoupling; MACHINE/Lex ID round-trip; zero-holder refusal; Ukraine fixture; synthetic co-authentic and RTL source admissions without schema migration; complete-tree baseline closure.

## Standing, classification, and open questions

### W4-K05 standing

| axis | token |
|---|---|
| evidence_standing | `supported` |
| decision_standing | `proposed` |
| implementation_standing | `not_implemented` |

### Classification rule

Findings use explicit classes including `ratified_repo_fact`, `bounded_repo_fact`, `reported_measurement`, `measurement_limitation`, `external_evidence_convergence`, `architectural_inference`, `architecture_decision_candidate`, `protocol_requirement`, `red_first_requirement`, `phased_deployment_proof`, `scope_boundary`, and `evidence_gap`. No unclassified substantive finding remains in the register.

### Open/routed questions

- close the complete-tree baseline with denominators and exact coordinates;
- validate every proposed relation/result/reason against existing registered vocabularies;
- build a real English-to-Ukrainian high-stakes corpus and behavioural ground truth;
- decide role qualifications/appointments only when real-user evidence exists;
- supply per-jurisdiction co-authentic reconciliation rules;
- admit a named RTL jurisdiction only with its evidence pack;
- decide cryptographic certificate/trust details in security architecture.

### Explicit D4 statement

D4-A1 **composes** with INT-R6 and does not require revisit in this pass. The UI posture itself is not widened or reinterpreted.

## Pattern Pass and sources

### Pattern Pass

Run and recorded. Routed candidates:

- Axis-separated language context;
- Authority Text Set;
- Purpose-bounded semantic rendition certificate;
- Vacant-holder typed refusal;
- No-upgrade action-profile gate;
- Translation/adaptation double gate;
- Data-only jurisdiction admission.

Rejected anti-patterns:

- catalogue identity-rate threshold as translation quality;
- universal English canonical legal definition;
- locale-specific duplicate status lattice.

The pattern register was not edited. Review should determine whether several candidates are facets of one broader governed-semantic-rendition pattern.

Full pass: [`int-r6/06-findings-standing-and-pattern-pass.md`](int-r6/06-findings-standing-and-pattern-pass.md).

### Principal external sources

- [Vienna Convention on the Law of Treaties, Article 33](https://legal.un.org/ilc/texts/instruments/english/conventions/1_1_1969.pdf)
- [Council Regulation No 1 determining EEC language use](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:31958R0001)
- [CJEU Case 283/81, CILFIT](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:61981CJ0283)
- [CJEU Case C-161/06, Skoma-Lux](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:62006CJ0161)
- [Canada, Constitution Act, 1982](https://laws-lois.justice.gc.ca/eng/const/)
- [Supreme Court of Canada, R v Daoust, 2004 SCC 6](https://decisions.scc-csc.ca/scc-csc/scc-csc/en/item/2110/index.do)
- [Swiss Federal Constitution](https://www.fedlex.admin.ch/eli/cc/1999/404/en)
- [Constitution of Ukraine](https://zakon.rada.gov.ua/laws/show/254%D0%BA/96-%D0%B2%D1%80#Text)
- [Law of Ukraine No. 2704-VIII](https://zakon.rada.gov.ua/laws/show/2704-19#Text)
- [ISO 704:2022](https://www.iso.org/standard/79077.html)
- [ISO 1087:2019](https://www.iso.org/standard/62330.html)
- [ISO 30042:2019 (TBX)](https://www.iso.org/standard/62510.html)
- [ISO 17100:2015](https://www.iso.org/standard/59149.html)
- [ISO 24495-1:2023](https://www.iso.org/standard/78907.html)
- [Unicode Bidirectional Algorithm](https://www.unicode.org/reports/tr9/)
- [W3C bidirectional text guidance](https://www.w3.org/International/articles/inline-bidi-markup/uba-basics)
- [Unicode CLDR](https://cldr.unicode.org/)

### Delivery inventory

- this ten-section deliverable;
- [`int-r6/01-repository-baseline.md`](int-r6/01-repository-baseline.md);
- [`int-r6/02-external-evidence.md`](int-r6/02-external-evidence.md);
- [`int-r6/03-language-axis-partition.md`](int-r6/03-language-axis-partition.md);
- [`int-r6/04-multilingual-authority-equivalence-protocol.md`](int-r6/04-multilingual-authority-equivalence-protocol.md);
- [`int-r6/05-red-first-fixtures-and-phased-deployment.md`](int-r6/05-red-first-fixtures-and-phased-deployment.md);
- [`int-r6/06-findings-standing-and-pattern-pass.md`](int-r6/06-findings-standing-and-pattern-pass.md).
