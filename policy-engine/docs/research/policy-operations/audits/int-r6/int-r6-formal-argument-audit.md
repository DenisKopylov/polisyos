# INT-R6 Formal Argument Audit

## Method

The audit reconstructed the package’s load-bearing conclusions as arguments rather than treating its decision-shaped prose as earned authority. Premises were checked against package SHA `5e47c868c2c1d4d66fa11fcddcc972dbb55e95d3`, governing records, worked examples and reachable external sources. A conclusion is accepted only to the strength of its weakest premise.

## Argument Map

### ARG-01 — language objects must be separated

1. Product UI strings are authored/translated under D4-A1.
2. Jurisdictional source authority is assigned by the relevant legal regime.
3. System-governance meanings must survive locale rendering through stable identities.
4. Translation and adaptation can fail independently.
5. Therefore one `locale` field cannot govern all language-sensitive objects.

**Disposition:** `confirmed`.

The conclusion follows. The current repository itself demonstrates the failure mode: `ui_locale` is an `en|uk` product preference, yet the launch builders carry it into `locale_preference`, while Lex stores one source-language string and an English-canonical Ukrainian extraction shape.

### ARG-02 — exactly five orthogonal coordinates are required

1. UI locale, authority set, rendition, semantic identity and presentation variant describe different facts.
2. Different facts are orthogonal coordinates.
3. Therefore the target has five orthogonal coordinates.

**Disposition:** `accepted_narrow_scope`.

Premise 2 is too strong. `PresentationVariant` is modelled as a child of a parent proposition/rendition and can itself carry language and translation/adaptation certificates. It is a dependent transformation/presentation layer, not a selector independent in the same sense as UI locale or authority-text-set membership. The package needs five record dimensions/layers, but it has not proved pairwise orthogonality.

The Ukraine and co-authentic examples do not collapse the model: one can change UI locale without changing authority set, select an informative rendition without changing source status, and adapt a presentation without merging semantic IDs. The defect is categorical wording, not failure of the separation.

### ARG-03 — D4-A1 composes without reopening

1. D4-A1 governs only public/product UI locale and explicitly carves out source rendering.
2. MAEP resolves source authority from jurisdiction and authority-text-set evidence, not UI locale.
3. RTL source rendering can be admitted without adding an RTL public UI locale.
4. Therefore D4-A1 need not be reopened to specify the omitted source-content layer.

**Disposition:** `confirmed`.

No protocol step requires `ui_locale` to decide authenticity, precedence, legal scope or concept identity. The repository crossing of UI locale into run context is evidence of implementation debt, not evidence that the architecture needs that coupling.

### ARG-04 — mandatory English legal pivot must be rejected

1. Some regimes designate one source; others make several texts co-authentic.
2. Co-authentic and jurisdiction-specific concepts may lack a controlling English formulation.
3. Forcing them through English introduces an authority relation the jurisdiction did not create.
4. Therefore English cannot be a mandatory legal-semantic pivot.

**Disposition:** `confirmed`.

The protocol’s allowed English uses—UI authoring, indexing, informative gloss and operator aid—are purpose-limited and do not erase local IDs. `SPOCandidate.subject_en` is correctly identified as a present repository adapter/gap rather than adopted as the universal model.

### ARG-05 — stable IDs and glossary releases prevent a second status lattice

1. Display labels are not semantic identities.
2. Existing owner vocabularies already distinguish important states.
3. New rendition/refusal terms must map to registered IDs or route a vocabulary gap.
4. Therefore MAEP need not create another status lattice.

**Disposition:** `confirmed_with_condition`.

The research contract consistently states the condition. Live repository evidence supports it: decision validity keeps `stale`, `superseded` and `withdrawn` distinct; evaluation safety uses versioned namespaced blocker IDs; `limited` belongs to more than one scoped owner; `may_not_use_for` members remain free strings. The example relation modes, risk classes and refusal names are not production vocabulary. Stage 3 must not copy them into a parallel owner.

### ARG-06 — action-profile equality establishes semantic equivalence

1. A target-only permission, lost requirement or lost prohibition is a semantic counterexample.
2. MAEP tests material contexts and fails on any counterexample.
3. If the suite produces no counterexample, source and target are equivalent for the purpose.

**Disposition:** `blocked` in its positive direction.

Premises 1–2 establish a strong falsification procedure. They do not establish premise 3. “Material contexts” has no complete denominator for unrestricted natural-language propositions, and the fixture suite is deliberately finite. Absence of a found counterexample is not universal equality of `Allowed`, `Required` and `Forbidden` sets. A defensible certificate may state the exact bounded proposition, purpose, frame, fixture population, adjudication and residual uncertainty; it may not present finite challenge-set passage as proof of complete semantic equivalence.

This is not an argument against certificates. It is a required narrowing of what the certificate attests.

### ARG-07 — the three binding falsifiers are red-first

1. Existing parity checks compare catalogue paths, placeholders and frozen Russian integrity.
2. Each malicious target can retain the same key and placeholder structure.
3. Each malicious target changes modality, qualification or status injectivity.
4. Therefore existing parity cannot distinguish it while MAEP’s semantic oracle can.

**Disposition:** `confirmed`.

The falsifiers are not accidentally red due to missing keys or variables. FX-003 additionally tests machine ID cardinality; a corrected mechanism must keep the three IDs even if human labels are short.

### ARG-08 — zero-holder deployment works today

1. Role definition, appointment and decision are distinct records.
2. An empty appointment relation can return a typed refusal while leaving explicitly unblocked functions available.
3. Therefore the system works today with zero holders.

**Disposition:** split.

The **record-model argument is confirmed**: zero holder cardinality does not require a schema change, exception or silent pass. The **repository-capability conclusion is refuted**: INT-R6 creates no type, producer, bridge, consumer, verification or surface. Its own conforming capability standing is `absent/unallocated`. “Can represent”, “show”, “run” and “return” must be stated as target behaviour or backed by an implementation chain.

### ARG-09 — jurisdiction N+1 is data-only

1. The proposed records include jurisdiction, authority mode, text members, scripts, concepts, mappings, roles and evidence.
2. A co-authentic or RTL example can be represented by populating those records.
3. Therefore every jurisdiction N+1 needs no model/schema change.

**Disposition:** `accepted_narrow_scope`.

The result holds for the tested classes—single designated, co-authentic, non-authentic rendition, LTR/RTL source content, absent holder—at the conceptual record-model level. It does not prove that every future jurisdiction introduces no new legal relation or semantic category. The package itself partly acknowledges this by routing genuinely new categories to governance; the headline should say “the tested N+1 classes require no language-specific schema branch”.

### ARG-10 — package standing is accepted narrow scope / absent / NO_GO

1. Stage 1 research may be accepted without implementation.
2. No admitted capability chain or public gate exists.
3. Therefore the three values are appropriate.

**Disposition:** values individually defensible, package publication nonconforming.

The appendix argument is sound. The main deliverable’s separate `evidence_standing / decision_standing / implementation_standing` block defeats a claim of package-level conformance until removed or explicitly superseded everywhere.

## Claim-By-Claim Analysis

| claim family | strongest earned statement | overclaim to remove |
|---|---|---|
| authority/text relation | authority attaches to versioned text/member/set under jurisdictional evidence | one universal source relation |
| UI separation | UI locale must not select legal authority | current repository already enforces complete decoupling |
| concept identity | namespaced IDs and mappings are required | an ID proves the mapping true |
| translation semantics | counterexamples can refute purpose-bounded fidelity | finite fixtures prove unrestricted equality |
| adaptation | must be evaluated separately | readability or comprehension confers authority |
| holders | zero eligible holders is representable | typed refusal is already implemented |
| N+1 | tested classes fit the proposed records | no possible jurisdiction can require a new category |
| standing | appendix tokens fit W4-K05 | package is conforming while the main block remains live |

## Countermodels And Boundary Cases

### Co-authentic divergence without adjudicator

English and French members disagree materially. Neither may be designated source. Both remain viewable; the derived use refuses pending the jurisdictional rule/holder. The package handles this without English fallback.

### Ukrainian source, English UI

Ukrainian law remains anchored to Ukrainian text while English chrome and an informative English rendition are displayed. No authority edge arises from UI locale. The package handles this.

### Presentation dependency

An Easy Read Ukrainian variant derives from a Ukrainian rendition which derives from an English-authored UI proposition. Changing the parent digest invalidates both downstream records. This shows dependency, not pairwise orthogonality.

### Unseen context after fixture passage

All declared fixtures pass, but a newly discovered exception changes the allowed action set. The earlier certificate cannot logically have proved all contexts; it can only bind the suite/version and invalidate on the new counterexample. This falsifies ARG-06’s strong reading.

### Future legal relation outside proposed modes

A jurisdiction recognises several official texts with asymmetric effect varying by forum or addressee. A generic `parallel_official_non_equal` label may be too coarse. The admission mechanism must allow a governed vocabulary extension rather than claim schema universality.

## Invalid Or Overbroad Inferences

- “Different object” does not automatically mean “orthogonal coordinate”.
- “No counterexample in the suite” does not entail semantic identity outside its declared denominator.
- “Representable in Markdown pseudocontract” does not entail capability.
- “Route named” does not entail owner assigned.
- “Historical measurement accurately attributed” does not make it current.
- “Appendix corrected” does not supersede contradictory main text.

## Arguments That Survive Audit

- Product UI locale, legal authority and system semantic identity must be separated.
- D4-A1 composes with that separation.
- Co-authentic regimes require authority sets and jurisdiction-specific divergence handling.
- English may assist presentation/indexing without becoming universal legal authority.
- Translation and adaptation require separate evidence.
- Status IDs must survive rendering and projections.
- Counterexample/action-profile tests are strong red-first falsifiers.
- Holder vacancy is a valid governed state in the target record model.

## Residual Band

The audit did not prove that the proposed semantic frame is complete for every speech act, legal doctrine or language; it tested the package’s formal inferences and its own worked classes. The exact probabilistic reliability of human adjudication, NLI, glossary review or challenge sets remains outside the argument audit. External regimes generally allocate authority, procedure and responsibility rather than furnish a mathematical proof of translation equivalence; that limitation is the reason ARG-06 must be narrowed, not a reason to abandon the protocol.
